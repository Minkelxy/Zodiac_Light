"""Verify the on-wire contract and current limiter before connecting hardware."""

import dataclasses
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np

from constellation_lamp.model import ValidationError, load_runtime
from constellation_lamp.compact import pack_runtime
from constellation_lamp.seriallink import (HEADER, FrameDecoder, HardwareProfile, capture_frames,
                                          encode_frame, estimate_current_ma, limit_current, stream_frames)


DATA = Path(__file__).resolve().parents[1] / "data"


class PartialSerial:
    def __init__(self, **kwargs):
        self.settings = kwargs
        self.is_open = False
        self.decoder = FrameDecoder(268)
        self.packets = []
        self.replies = []
        digest = pack_runtime(load_runtime(DATA))["metadata"]["scene_sha256"]
        self.identity_line = f"INFO CLP1 268 {digest} 0\n".encode("ascii")
        self.reply_fragment_size = None

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def reset_input_buffer(self):
        self.replies.clear()

    def write(self, data):
        # Exercise partial UART writes, not only a perfect write-all transport.
        size = min(len(data), 23)
        for packet in self.decoder.feed(data[:size]):
            self.packets.append(packet)
            if packet.sequence == 0 and self.identity_line is not None:
                self.replies.append(self.identity_line)
            self.replies.append(f"OK {packet.sequence}\n".encode())
        return size

    def readline(self):
        if not self.replies:
            return b""
        reply = self.replies.pop(0)
        if self.reply_fragment_size and len(reply) > self.reply_fragment_size:
            self.replies.insert(0, reply[self.reply_fragment_size:])
            return reply[:self.reply_fragment_size]
        return reply

    def flush(self):
        pass


class SerialLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(DATA)
        cls.profile = HardwareProfile.load(DATA / "hardware.json")

    def test_protocol_exact_bytes_and_fragmented_rgb_order(self):
        frame = np.array([[1, 2, 3], [250, 128, 0]], dtype=np.uint8)
        packet = encode_frame(frame, 0x12345678)
        self.assertEqual(packet[:12], b"CLP1\x78\x56\x34\x12\x02\x00\x06\x00")
        decoder = FrameDecoder(2)
        found = []
        for byte in packet:
            found.extend(decoder.feed(bytes([byte])))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].sequence, 0x12345678)
        np.testing.assert_array_equal(found[0].frame(), frame)
        self.assertEqual(found[0].payload, bytes([1, 2, 3, 250, 128, 0]))

    def test_crc_corruption_noise_wrong_count_and_resynchronization(self):
        frame = np.arange(12, dtype=np.uint8).reshape(4, 3)
        bad = bytearray(encode_frame(frame, 1))
        bad[-1] ^= 0xFF
        wrong = encode_frame(frame[:2], 2)
        invalid_length = bytearray(encode_frame(frame, 3))
        invalid_length[10:12] = b"\xff\xff"
        good = encode_frame(frame, 4)
        decoder = FrameDecoder(4)
        found = decoder.feed(b"garbage\0" + bytes(bad) + wrong + bytes(invalid_length) + good)
        self.assertEqual([p.sequence for p in found], [4])
        self.assertEqual(decoder.rejected, 3)
        decoder.feed(b"x" * 100_000)
        self.assertLessEqual(len(decoder.buffer), 3)

    def test_magic_in_valid_payload_is_not_a_new_frame(self):
        values = np.frombuffer(b"CLP1xx", dtype=np.uint8).reshape(2, 3)
        found = FrameDecoder().feed(encode_frame(values, 8) + encode_frame(values, 9))
        self.assertEqual([p.sequence for p in found], [8, 9])

    def test_fragmented_ack_and_boot_messages(self):
        from constellation_lamp.seriallink import _ack
        from types import SimpleNamespace
        fragments = iter([b"boot message\nOK ", b"0\n", b"OK ", b"123", b"\r\n"])
        _ack(SimpleNamespace(readline=lambda: next(fragments)), 123, timeout_s=.1)

    def test_current_limit_conserves_hue_without_mutating_input(self):
        frame = np.tile(np.array([255, 128, 64], np.uint8), (268, 1))
        original = frame.copy()
        limited, result = limit_current(frame, self.profile)
        self.assertGreater(result["estimated_before_ma"], 2000)
        self.assertLessEqual(result["estimated_after_ma"], 2000)
        self.assertLess(result["scale"], 1)
        np.testing.assert_array_equal(frame, original)
        np.testing.assert_array_equal(limited, np.floor(original * result["scale"]).astype(np.uint8))
        self.assertEqual(estimate_current_ma(np.zeros_like(frame), self.profile), 268)
        dim = np.ones_like(frame)
        np.testing.assert_array_equal(limit_current(dim, self.profile)[0], dim)
        # Current estimates also serve offline rendering; UART cadence is only
        # checked when capturing/streaming through the transport boundary.
        slow = dataclasses.replace(self.profile, fps=.5)
        np.testing.assert_array_equal(limit_current(frame, slow)[0], limited)

    def test_invalid_profile_protocol_values_are_rejected(self):
        changes = ({"baud": 115200}, {"fps": 60}, {"fps": 45}, {"fps": .5}, {"current_limit_ma": 100},
                   {"channel_ma": 0}, {"idle_led_ma": -1}, {"reset_us": float("nan")},
                   {"fps": True}, {"baud": 1.5}, {"packet_timeout_ms": 1}, {"reset_us": 0})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                dataclasses.replace(self.profile, **change).validate(268)
        for sequence in (-1, 2**32, True):
            with self.assertRaises(ValidationError):
                encode_frame(np.zeros((2, 3), np.uint8), sequence)
        with self.assertRaises(ValidationError):
            encode_frame(np.zeros((2, 3), np.float32), 0)

    def test_offline_capture_reproducible_limited_and_ends_black(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "a.clp", Path(temp) / "b.clp"
            kwargs = {"params": {"effect": "ripple", "seed": 42, "brightness": 1},
                      "profile": self.profile, "duration_s": .1}
            result = capture_frames(self.runtime, a, **kwargs)
            capture_frames(self.runtime, b, **kwargs)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(a.stat().st_size, result["bytes"])
            packets = FrameDecoder(268).feed(a.read_bytes())
            self.assertEqual(len(packets), 4)
            self.assertEqual([p.sequence for p in packets], [0, 1, 2, 3])
            self.assertTrue(all(estimate_current_ma(p.frame(), self.profile) <= 2000 for p in packets))
            self.assertFalse(packets[-1].frame().any())
            self.assertEqual(len(packets[0].payload) + HEADER.size, 820)

    def test_live_transport_ack_partial_writes_and_blackout(self):
        port = PartialSerial()
        result = stream_frames(self.runtime, "mock-port", {"effect": "twinkle", "seed": 1}, self.profile,
                               duration_s=.005, progress=lambda _: None, serial_factory=lambda **_: port)
        self.assertFalse(port.is_open)
        self.assertEqual(port.port, "mock-port")
        self.assertFalse(port.dtr)
        self.assertFalse(port.rts)
        self.assertGreaterEqual(result["frames"], 1)
        self.assertFalse(port.packets[0].frame().any())
        self.assertFalse(port.packets[-1].frame().any())
        self.assertTrue(any(p.frame().any() for p in port.packets[1:-1]))
        self.assertTrue(result["blackout_confirmed"])

    def test_black_frame_handshake_retries_and_cleanup_preserves_original_error(self):
        from constellation_lamp.seriallink import _handshake
        port = PartialSerial()
        with patch("constellation_lamp.seriallink._ack", side_effect=[OSError("booting"), None]):
            _handshake(port, np.zeros((268, 3), np.uint8), require_device_identity=False)
        self.assertEqual([p.sequence for p in port.packets], [0, 0])
        port = PartialSerial()
        with patch("constellation_lamp.seriallink._ack", side_effect=[None, OSError("original failure"),
                                                                     OSError("cleanup failure"), OSError("cleanup failure")]) as ack:
            with self.assertRaisesRegex(OSError, "original failure"):
                stream_frames(self.runtime, "mock-port", {"effect": "twinkle"},
                              dataclasses.replace(self.profile, require_device_identity=False),
                              duration_s=.005, progress=lambda _: None, serial_factory=lambda **_: port)
            self.assertEqual([call.args[1] for call in ack.call_args_list], [0, 1, 2, 2])
        self.assertFalse(port.is_open)

    def test_unsupported_hardware_protocol_and_malformed_sections(self):
        from constellation_lamp.reports import write_json
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "hardware.json"
            for section, key, value in (("transport", "protocol", "OTHER"), ("transport", "frame_order", "GRB"),
                                        ("ws2812", "wire_order", "RGB"), ("ws2812", "bit_rate_hz", 400000)):
                write_json(path, {"schema_version": 1, section: {key: value}})
                with self.assertRaises(ValidationError):
                    HardwareProfile.load(path)
            write_json(path, {"schema_version": 1, "transport": None})
            with self.assertRaises(ValidationError):
                HardwareProfile.load(path)


if __name__ == "__main__":
    unittest.main()
