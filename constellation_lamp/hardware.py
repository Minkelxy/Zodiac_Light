"""Standard-library-only hardware budgets and scene compatibility checks."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

from .model import ValidationError, read_json

FRAME_HEADER_BYTES = 16
MAX_LEDS = 65535 // 3


def _finite(value, name, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f"{name} must be finite")
    if positive and value <= 0 or nonnegative and value < 0:
        raise ValidationError(f"{name} is outside its allowed range")
    return float(value)


@dataclass(frozen=True)
class HardwareProfile:
    baud: int = 460800
    fps: float = 30.0
    current_limit_ma: float = 2000.0
    idle_led_ma: float = 1.0
    channel_ma: float = 20.0
    reset_us: float = 300.0
    packet_timeout_ms: float = 250.0
    stream_timeout_ms: float = 1000.0
    expected_led_count: int | None = None
    scene_sha256: str | None = None
    require_device_identity: bool = True

    def validate_power(self, led_count: int):
        if type(led_count) is not int or not 1 <= led_count <= MAX_LEDS:
            raise ValidationError(f"CLP1 LED count must be 1..{MAX_LEDS}")
        _finite(self.current_limit_ma, "current_limit_ma", positive=True)
        _finite(self.idle_led_ma, "idle_led_ma", nonnegative=True)
        _finite(self.channel_ma, "channel_ma", positive=True)
        if self.current_limit_ma < led_count * self.idle_led_ma:
            raise ValidationError("Current budget is below the estimated standby current")
        return self

    def validate(self, led_count: int):
        self.validate_power(led_count)
        if type(self.baud) is not int or not 1 <= self.baud <= 0xFFFFFFFF:
            raise ValidationError("baud must be a positive uint32 integer")
        _finite(self.fps, "fps", positive=True)
        _finite(self.reset_us, "reset_us", nonnegative=True)
        _finite(self.packet_timeout_ms, "packet_timeout_ms", positive=True)
        _finite(self.stream_timeout_ms, "stream_timeout_ms", positive=True)
        if self.reset_us < 280:
            raise ValidationError("Reference WS2812 timing reserves at least 280 us reset")
        if type(self.require_device_identity) is not bool:
            raise ValidationError("require_device_identity must be a boolean")
        if self.expected_led_count is not None and (type(self.expected_led_count) is not int
                                                   or not 1 <= self.expected_led_count <= MAX_LEDS):
            raise ValidationError("scene.led_count must be a valid integer LED count")
        if self.scene_sha256 is not None and (not isinstance(self.scene_sha256, str)
                or len(self.scene_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.scene_sha256)):
            raise ValidationError("scene.sha256 must be a lowercase SHA256 hex string")
        # UART 8N1 uses ten bits per byte; leave headroom for ACK and scheduling.
        serial_bits_s = (FRAME_HEADER_BYTES + led_count * 3) * 10 * self.fps
        if serial_bits_s > self.baud * 0.85:
            raise ValidationError("FPS exceeds 85% of the UART bandwidth; reduce FPS or increase baud")
        if self.fps * (led_count * 30.0 + self.reset_us) > 1_000_000:
            raise ValidationError("FPS exceeds the WS2812 800 kbit/s frame-time budget")
        # This transport waits for show() + ACK before starting the next packet.
        round_trip_s = ((FRAME_HEADER_BYTES + led_count * 3 + 14) * 10 / self.baud
                        + (led_count * 30 + self.reset_us) / 1_000_000)
        if self.fps * round_trip_s > .85:
            raise ValidationError("FPS exceeds the UART + WS2812 + ACK budget; reduce FPS")
        if (FRAME_HEADER_BYTES + led_count * 3) * 10 / self.baud * 1000 > self.packet_timeout_ms * .85:
            raise ValidationError("UART packet duration exceeds the firmware packet timeout")
        if 1000 / self.fps + round_trip_s * 1000 > self.stream_timeout_ms * .85:
            raise ValidationError("FPS is too low for the firmware valid-frame timeout")
        return self

    def adapt_fps(self, led_count: int, requested: float | None = None):
        """Return a feasible profile, lowering FPS with transport headroom.

        This is for derived build profiles. An explicit stream --fps remains
        strict, so a user-requested invalid cadence never changes silently.
        """
        self.validate_power(led_count)
        target = _finite(self.fps if requested is None else requested, "fps", positive=True)
        if type(self.baud) is not int or not 1 <= self.baud <= 0xFFFFFFFF:
            raise ValidationError("baud must be a positive uint32 integer")
        reset = _finite(self.reset_us, "reset_us", nonnegative=True)
        wire_s = (FRAME_HEADER_BYTES + led_count * 3) * 10 / self.baud
        led_s = (led_count * 30 + reset) / 1_000_000
        round_trip_s = wire_s + 140 / self.baud + led_s
        maximum = min(.85 / wire_s, 1 / led_s, .85 / round_trip_s)
        fps = target if target <= maximum else math.floor(maximum * 10) / 10
        if fps <= 0:
            raise ValidationError("No feasible FPS at this baud and LED count")
        return replace(self, fps=fps).validate(led_count)

    def validate_runtime(self, runtime):
        self.validate(runtime.led_count)
        if self.expected_led_count is not None and self.expected_led_count != runtime.led_count:
            raise ValidationError("Hardware profile LED count differs from the current layout; rebuild firmware")
        if self.scene_sha256 is not None:
            from .compact import pack_runtime
            if self.scene_sha256 != pack_runtime(runtime)["metadata"]["scene_sha256"]:
                raise ValidationError("Hardware profile scene mapping differs from the current layout; rebuild firmware")
        return self

    @classmethod
    def load(cls, path: str | Path):
        raw = read_json(path)
        transport = raw.get("transport", {})
        power = raw.get("power_estimate", {})
        timing = raw.get("ws2812", {})
        scene = raw.get("scene", {})
        if not all(isinstance(item, dict) for item in (transport, power, timing, scene)):
            raise ValidationError("Hardware profile transport/power_estimate/ws2812 must be objects")
        supported = ((transport, "protocol", "CLP1"), (transport, "frame_order", "RGB"),
                     (timing, "wire_order", "GRB"), (timing, "bit_rate_hz", 800000))
        for section, name, expected in supported:
            if section.get(name, expected) != expected:
                raise ValidationError(f"Hardware profile {name} must be {expected!r} for this reference firmware")
        return cls(baud=transport.get("baud", 460800), fps=transport.get("fps", 30),
                   current_limit_ma=power.get("current_limit_ma", 2000),
                   idle_led_ma=power.get("idle_led_ma", 1), channel_ma=power.get("channel_ma", 20),
                   reset_us=timing.get("reset_us", 300), packet_timeout_ms=transport.get("packet_timeout_ms", 250),
                   stream_timeout_ms=timing.get("timeout_ms", 1000),
                   expected_led_count=scene.get("led_count"), scene_sha256=scene.get("sha256"),
                   require_device_identity=transport.get("require_device_identity", True))
