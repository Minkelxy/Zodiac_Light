"""RGB transport and a configurable current estimate, independent of the GUI.

CLP1 contains already brightness/gamma-corrected RGB, in electrical LED order.
The receiver converts RGB to its configured WS2812 channel order.
"""

from __future__ import annotations

import math
import sys
import struct
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .model import ValidationError
from .hardware import HardwareProfile, MAX_LEDS, _finite


MAGIC = b"CLP1"
HEADER = struct.Struct("<4sIHHI")


@dataclass(frozen=True)
class DeviceIdentity:
    """Firmware scene mapping and operating mode, independent of frame ACKs."""

    led_count: int
    scene_sha256: str
    mode: int = 0


@dataclass
class _ReplyState:
    pending: bytearray = field(default_factory=bytearray)
    identity: DeviceIdentity | None = None
    discard_line: bool = False


def _parse_identity(reply: bytes) -> DeviceIdentity:
    fields = reply.split()
    if len(fields) != 5 or fields[:2] != [b"INFO", b"CLP1"]:
        raise ValidationError("Malformed firmware identity; expected INFO CLP1 <LED count> <SHA256> <mode>")
    count, digest, mode = fields[2:]
    if (not count.isdigit() or not 1 <= int(count) <= MAX_LEDS or not mode.isdigit()
            or len(digest) != 64 or any(c not in b"0123456789abcdefABCDEF" for c in digest)):
        raise ValidationError("Malformed firmware identity LED count, SHA256 or mode")
    return DeviceIdentity(int(count), digest.decode("ascii").lower(), int(mode))


def _check_identity(actual: DeviceIdentity, expected: DeviceIdentity) -> None:
    if actual.led_count != expected.led_count:
        raise ValidationError(f"Firmware LED count {actual.led_count} differs from layout {expected.led_count}; rebuild firmware")
    if actual.scene_sha256 != expected.scene_sha256:
        raise ValidationError("Firmware scene mapping SHA256 differs from the current layout; rebuild firmware")
    if actual.mode != expected.mode:
        raise ValidationError(f"Firmware mode {actual.mode} is incompatible with serial streaming; expected mode {expected.mode}")



def _frame(frame):
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 2 or frame.shape[1] != 3:
        raise ValidationError("RGB frame must be a uint8 NumPy array of shape (LED count, 3)")
    if not 1 <= len(frame) <= MAX_LEDS:
        raise ValidationError(f"CLP1 LED count must be 1..{MAX_LEDS}")
    return frame


def encode_frame(frame: np.ndarray, sequence: int) -> bytes:
    _frame(frame)
    if type(sequence) is not int or not 0 <= sequence <= 0xFFFFFFFF:
        raise ValidationError("sequence must be a uint32 integer")
    payload = frame.tobytes(order="C")
    return HEADER.pack(MAGIC, sequence, len(frame), len(payload), zlib.crc32(payload)) + payload


@dataclass(frozen=True)
class Packet:
    sequence: int
    led_count: int
    payload: bytes

    def frame(self):
        return np.frombuffer(self.payload, dtype=np.uint8).reshape(self.led_count, 3).copy()


class FrameDecoder:
    """Incremental offline parser for captures, fuzz tests and host applications."""

    def __init__(self, led_count: int | None = None):
        if led_count is not None and (type(led_count) is not int or not 1 <= led_count <= MAX_LEDS):
            raise ValidationError("Invalid expected LED count")
        self.led_count = led_count
        self.buffer = bytearray()
        self.rejected = 0

    def feed(self, data: bytes) -> list[Packet]:
        self.buffer.extend(data)
        packets = []
        while True:
            position = self.buffer.find(MAGIC)
            if position < 0:
                self.buffer[:] = self.buffer[-3:]
                break
            del self.buffer[:position]
            if len(self.buffer) < HEADER.size:
                break
            _, seq, count, length, crc = HEADER.unpack_from(self.buffer)
            if not 1 <= count <= MAX_LEDS or length != count * 3 or self.led_count is not None and count != self.led_count:
                self.rejected += 1
                del self.buffer[0]
                continue
            total = HEADER.size + length
            if len(self.buffer) < total:
                break
            payload = bytes(self.buffer[HEADER.size:total])
            if zlib.crc32(payload) != crc:
                self.rejected += 1
                del self.buffer[0]
                continue
            packets.append(Packet(seq, count, payload))
            del self.buffer[:total]
        return packets


def estimate_current_ma(frame: np.ndarray, profile: HardwareProfile) -> float:
    _frame(frame)
    return len(frame) * profile.idle_led_ma + float(frame.sum(dtype=np.uint64)) * profile.channel_ma / 255


def limit_current(frame: np.ndarray, profile: HardwareProfile) -> tuple[np.ndarray, dict]:
    """Scale RGB once, rounding down so the *estimated* budget is respected."""
    _frame(frame)
    profile.validate_power(len(frame))
    idle = len(frame) * profile.idle_led_ma
    demand = estimate_current_ma(frame, profile)
    scale = 1.0 if demand <= profile.current_limit_ma else (profile.current_limit_ma - idle) / (demand - idle)
    limited = frame.copy() if scale >= 1 else np.floor(frame.astype(np.float64) * scale).astype(np.uint8)
    return limited, {"estimated_before_ma": demand, "estimated_after_ma": estimate_current_ma(limited, profile),
                     "scale": scale, "limit_ma": profile.current_limit_ma}


def capture_frames(runtime, path: str | Path, params: dict, profile: HardwareProfile, *, duration_s=2.0) -> dict:
    """Render a deterministic CLP1 recording without opening a serial port."""
    from .effects import render
    profile.validate_runtime(runtime)
    duration_s = _finite(duration_s, "duration_s", positive=True)
    if duration_s > 3600:
        raise ValidationError("Capture duration must be at most 3600 seconds")
    count = math.ceil(duration_s * profile.fps)
    frame = np.zeros((runtime.led_count, 3), np.uint8)
    state = {}
    # Validate before opening/replacing output.
    render(runtime, 0, params, state, frame)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    maximum = 0.0
    minimum_scale = 1.0
    with temporary.open("wb") as stream:
        for i in range(count):
            render(runtime, i * 1000 / profile.fps, params, state, frame)
            limited, power = limit_current(frame, profile)
            maximum = max(maximum, power["estimated_after_ma"])
            minimum_scale = min(minimum_scale, power["scale"])
            stream.write(encode_frame(limited, i))
        # A recording always ends in an explicit blackout, just like live output.
        stream.write(encode_frame(np.zeros_like(frame), count))
    temporary.replace(output)
    return {"frames": count, "packets": count + 1, "bytes": (count + 1) * (HEADER.size + runtime.led_count * 3),
            "max_estimated_current_ma": maximum, "minimum_scale": minimum_scale,
            "blackout_packet": True, "fps": profile.fps}


def _write_all(port, packet: bytes, *, timeout_s=1.0):
    offset = 0
    deadline = time.monotonic() + timeout_s
    while offset < len(packet):
        if time.monotonic() >= deadline:
            raise OSError("Serial packet write exceeded its deadline")
        written = port.write(packet[offset:])
        if not written:
            raise OSError("Serial write returned zero bytes")
        offset += written


def _ack(port, sequence: int, *, timeout_s=.75,
         expected_identity: DeviceIdentity | None = None, require_identity=False,
         response_state: _ReplyState | None = None):
    deadline = time.monotonic() + timeout_s
    state = response_state if response_state is not None else _ReplyState()
    pending = state.pending
    expected = f"OK {sequence}".encode("ascii")
    while time.monotonic() < deadline:
        pending.extend(port.readline())
        acknowledged = False
        while b"\n" in pending:
            reply, _, remaining = pending.partition(b"\n")
            pending[:] = remaining
            if state.discard_line:
                state.discard_line = False
                continue
            reply = reply.strip()
            if reply == b"INFO" or reply.startswith(b"INFO "):
                if len(reply) > 256:
                    raise ValidationError("Firmware identity line is too long")
                identity = _parse_identity(reply)
                if expected_identity is not None:
                    _check_identity(identity, expected_identity)
                state.identity = identity
            elif reply == expected:
                if require_identity and state.identity is None:
                    raise ValidationError("Firmware ACK arrived without device identity INFO; update firmware or explicitly disable identity checks for legacy firmware")
                if require_identity and expected_identity is not None:
                    _check_identity(state.identity, expected_identity)
                acknowledged = True
        if acknowledged:
            return state.identity
        if len(pending) > 256:
            if pending.lstrip().startswith(b"INFO "):
                raise ValidationError("Firmware identity line is too long")
            pending.clear()
            state.discard_line = True  # Never turn a truncated boot log suffix into a valid INFO/ACK.
    raise OSError(f"No valid firmware ACK for frame {sequence}; check LED count, baud and firmware")


def _handshake(port, frame, *, timeout_s=3.0,
               expected_identity: DeviceIdentity | None = None, require_device_identity=True,
               response_state: _ReplyState | None = None):
    if require_device_identity and expected_identity is None:
        raise ValidationError("Expected device identity is required for the readiness handshake")
    state = response_state if response_state is not None else _ReplyState()
    # Even a mistaken caller cannot use the handshake to send colour before verification.
    black_packet = encode_frame(np.zeros_like(_frame(frame)), 0)
    deadline = time.monotonic() + timeout_s
    last_error = None
    while time.monotonic() < deadline:
        _write_all(port, black_packet)
        try:
            identity = _ack(port, 0, timeout_s=min(.3, max(0, deadline - time.monotonic())),
                            expected_identity=expected_identity, require_identity=require_device_identity,
                            response_state=state)
            if require_device_identity and identity is None:
                raise ValidationError("Firmware did not provide device identity INFO before the black-frame ACK")
            return identity
        except OSError as error:
            last_error = error
    raise OSError("Firmware readiness handshake failed after black-frame retries") from last_error


def stream_frames(runtime, port_name: str, params: dict, profile: HardwareProfile, *, duration_s=10.0,
                  progress: Callable[[str], None] = print, serial_factory=None) -> dict:
    """Send only to an explicitly supplied port, and verify every accepted frame."""
    from .effects import render
    from .compact import pack_runtime
    profile.validate_runtime(runtime)
    expected_identity = DeviceIdentity(runtime.led_count, pack_runtime(runtime)["metadata"]["scene_sha256"])
    duration_s = _finite(duration_s, "duration_s", positive=True)
    if not isinstance(port_name, str) or not port_name.strip():
        raise ValidationError("A serial port must be explicitly specified")
    frame = np.zeros((runtime.led_count, 3), np.uint8)
    state = {}
    render(runtime, 0, params, state, frame)
    if serial_factory is None:
        try:
            import serial
        except ImportError as error:
            raise ValidationError('Install serial support: python -m pip install "pyserial>=3.5"') from error
        serial_factory = serial.Serial
    # Avoid asserting DTR/RTS on creation; some development boards reset on it.
    port = serial_factory(port=None, baudrate=profile.baud, timeout=.05, write_timeout=.5)
    sequence = 0
    maximum = 0.0
    minimum_scale = 1.0
    slow = 0
    result = {}
    replies = _ReplyState()
    try:
        port.dtr = False
        port.rts = False
        port.port = port_name
        port.open()
        port.reset_input_buffer()
        # Readiness handshake: first payload is black, never an unverified effect.
        device = _handshake(port, np.zeros_like(frame), expected_identity=expected_identity,
                            require_device_identity=profile.require_device_identity, response_state=replies)
        sequence += 1
        started = time.monotonic()
        next_frame = started
        last_progress = started
        while time.monotonic() - started < duration_s:
            now = time.monotonic()
            if now < next_frame:
                time.sleep(min(next_frame - now, .05))
                continue
            render(runtime, (now - started) * 1000, params, state, frame)
            limited, power = limit_current(frame, profile)
            maximum = max(maximum, power["estimated_after_ma"])
            minimum_scale = min(minimum_scale, power["scale"])
            _write_all(port, encode_frame(limited, sequence))
            _ack(port, sequence, expected_identity=expected_identity,
                 require_identity=profile.require_device_identity, response_state=replies)
            sequence = (sequence + 1) & 0xFFFFFFFF
            next_frame += 1 / profile.fps
            after = time.monotonic()
            if after > next_frame + 1 / profile.fps:
                slow += 1
                next_frame = after + 1 / profile.fps  # Drop missed deadlines, never queue stale frames.
            if after - last_progress >= 1:
                progress(f"Accepted {sequence - 1} effect frames; estimated {power['estimated_after_ma']:.0f} mA; scale {power['scale']:.3f}")
                last_progress = after
        result.update(frames=sequence - 1, max_estimated_current_ma=maximum, minimum_scale=minimum_scale,
                      late_frames=slow, fps=profile.fps, device_identity_verified=device is not None,
                      scene_sha256=expected_identity.scene_sha256,
                      device_mode=None if device is None else device.mode)
        return result
    finally:
        original_error = sys.exc_info()[0] is not None
        cleanup_error = None
        if port.is_open:
            # Never reuse the last attempted effect sequence: its delayed ACK
            # must not be mistaken for confirmation of the blackout packet.
            blackout_sequence = (sequence + 1) & 0xFFFFFFFF
            try:
                for attempt in range(2):
                    _write_all(port, encode_frame(np.zeros_like(frame), blackout_sequence))
                    try:
                        # A black packet is allowed after an identity failure;
                        # cleanup must not let that failure mask its original diagnostic.
                        _ack(port, blackout_sequence, timeout_s=.4, response_state=replies)
                        result["blackout_confirmed"] = True
                        break
                    except (OSError, ValidationError):
                        if attempt == 1:
                            raise
            except (OSError, ValidationError) as error:
                cleanup_error = error
                progress("Blackout was not acknowledged; the firmware's valid-frame timeout will blank the output")
            finally:
                try:
                    port.close()
                except OSError as error:
                    cleanup_error = cleanup_error or error
        else:
            try:
                port.close()
            except OSError as error:
                cleanup_error = error
        if cleanup_error is not None and not original_error:
            raise cleanup_error
