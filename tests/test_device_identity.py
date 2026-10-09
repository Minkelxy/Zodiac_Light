"""No effect RGB is sent until firmware has confirmed the exact scene mapping."""

from __future__ import annotations

import copy
import dataclasses
import tempfile
import unittest
from pathlib import Path

import numpy as np

from constellation_lamp.compact import pack_runtime
from constellation_lamp.hardware import HardwareProfile as CanonicalHardwareProfile
from constellation_lamp.model import ValidationError, compile_layout, load_runtime, read_json
from constellation_lamp.seriallink import (DeviceIdentity, HardwareProfile, _ReplyState, _ack, _handshake,
                                          capture_frames, stream_frames)
from test_seriallink import DATA, PartialSerial


class AckBeforeInfoSerial(PartialSerial):
    def write(self, data):
        before = len(self.packets)
        written = super().write(data)
        if len(self.packets) > before and self.packets[-1].sequence == 0:
            self.replies[-2:] = self.replies[-2:][::-1]
        return written


class ChangedModeSerial(PartialSerial):
    def write(self, data):
        before = len(self.packets)
        written = super().write(data)
        if len(self.packets) > before and self.packets[-1].sequence == 1:
            info = self.identity_line.replace(b" 0\n", b" 1\n")
            self.replies.insert(max(0, len(self.replies) - 1), info)
        return written


class DeviceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(DATA)
        cls.digest = pack_runtime(cls.runtime)["metadata"]["scene_sha256"]
        cls.profile = HardwareProfile()

    def _stream(self, port, *, runtime=None, profile=None):
        return stream_frames(runtime or self.runtime, "mock-port", {"effect": "twinkle"}, profile or self.profile,
                             duration_s=.005, progress=lambda _: None, serial_factory=lambda **_: port)

    def _assert_only_black_and_closed(self, port):
        self.assertFalse(port.is_open)
        self.assertGreaterEqual(len(port.packets), 2)
        self.assertTrue(all(not packet.frame().any() for packet in port.packets))

    def test_hardware_profile_reexport_and_matching_identity_allow_effect_frames(self):
        self.assertIs(HardwareProfile, CanonicalHardwareProfile)
        port = PartialSerial()
        result = self._stream(port)
        self.assertTrue(result["device_identity_verified"])
        self.assertEqual(result["scene_sha256"], self.digest)
        self.assertEqual(result["device_mode"], 0)
        self.assertTrue(result["blackout_confirmed"])
        self.assertTrue(any(packet.frame().any() for packet in port.packets))

    def test_wrong_count_hash_and_mode_reject_before_any_color(self):
        cases = ((267, self.digest, 0, "LED count"),
                 (268, "0" * 64, 0, "SHA256"),
                 (268, self.digest, 1, "mode"))
        for count, digest, mode, message in cases:
            with self.subTest(message=message):
                port = PartialSerial()
                port.identity_line = f"INFO CLP1 {count} {digest} {mode}\n".encode()
                with self.assertRaisesRegex(ValidationError, message):
                    self._stream(port)
                self._assert_only_black_and_closed(port)

    def test_ack_without_identity_and_identity_after_ack_are_not_verified(self):
        for port in (PartialSerial(), AckBeforeInfoSerial()):
            if type(port) is PartialSerial:
                port.identity_line = None
            with self.subTest(port=type(port).__name__), self.assertRaisesRegex(ValidationError, "without device identity"):
                self._stream(port)
            self._assert_only_black_and_closed(port)

    def test_fragmented_info_and_ack_are_verified_and_wrong_fragmented_info_is_rejected(self):
        good = PartialSerial()
        good.reply_fragment_size = 1
        self.assertTrue(self._stream(good)["device_identity_verified"])
        bad = PartialSerial()
        bad.reply_fragment_size = 2
        bad.identity_line = f"INFO CLP1 268 {'f' * 64} 0\r\n".encode()
        with self.assertRaisesRegex(ValidationError, "SHA256"):
            self._stream(bad)
        self._assert_only_black_and_closed(bad)

    def test_partial_identity_survives_ack_timeout_for_black_retry(self):
        from types import SimpleNamespace
        identity_line = f"INFO CLP1 268 {self.digest} 0\n".encode()
        pieces = [identity_line[:35]]
        port = SimpleNamespace(readline=lambda: pieces.pop(0) if pieces else b"")
        state = _ReplyState()
        expected = DeviceIdentity(268, self.digest)
        with self.assertRaises(OSError):
            _ack(port, 0, timeout_s=.001, expected_identity=expected, require_identity=True, response_state=state)
        self.assertEqual(bytes(state.pending), identity_line[:35])
        pieces.extend((identity_line[35:], b"OK 0\r\n"))
        self.assertEqual(_ack(port, 0, timeout_s=.1, expected_identity=expected,
                              require_identity=True, response_state=state), expected)

    def test_long_boot_noise_cannot_be_truncated_into_fake_identity(self):
        from types import SimpleNamespace
        info = f"INFO CLP1 268 {self.digest} 0".encode()
        pieces = [b"x" * 400 + info, b"\nOK 0\n"]
        port = SimpleNamespace(readline=lambda: pieces.pop(0) if pieces else b"")
        with self.assertRaisesRegex(ValidationError, "without device identity"):
            _ack(port, 0, timeout_s=.1, expected_identity=DeviceIdentity(268, self.digest), require_identity=True)

    def test_malformed_info_never_satisfies_identity_check(self):
        for info in (b"INFO CLP2 268 " + self.digest.encode() + b" 0\n",
                     b"INFO CLP1 268 not-a-hash 0\n", b"INFO CLP1 268\n",
                     b"INFO CLP1 268 " + self.digest.encode() + b" serial\n"):
            with self.subTest(info=info):
                port = PartialSerial()
                port.identity_line = info
                with self.assertRaisesRegex(ValidationError, "Malformed"):
                    self._stream(port)
                self._assert_only_black_and_closed(port)

    def test_legacy_requires_explicit_opt_out_and_wrong_info_still_rejects(self):
        legacy = dataclasses.replace(self.profile, require_device_identity=False)
        port = PartialSerial()
        port.identity_line = None
        result = self._stream(port, profile=legacy)
        self.assertFalse(result["device_identity_verified"])
        self.assertTrue(any(packet.frame().any() for packet in port.packets))
        port = PartialSerial()
        port.identity_line = f"INFO CLP1 268 {'0' * 64} 0\n".encode()
        with self.assertRaisesRegex(ValidationError, "SHA256"):
            self._stream(port, profile=legacy)
        self._assert_only_black_and_closed(port)

    def test_handshake_forces_black_even_when_caller_supplies_color(self):
        port = PartialSerial()
        identity = _handshake(port, np.full((268, 3), 255, np.uint8),
                              expected_identity=DeviceIdentity(268, self.digest))
        self.assertEqual(identity, DeviceIdentity(268, self.digest))
        self.assertTrue(all(not packet.frame().any() for packet in port.packets))

    def test_mode_change_info_stops_stream_and_preserves_blackout_cleanup(self):
        port = ChangedModeSerial()
        with self.assertRaisesRegex(ValidationError, "mode"):
            self._stream(port)
        self.assertFalse(port.is_open)
        self.assertEqual(sum(bool(packet.frame().any()) for packet in port.packets), 1)
        self.assertFalse(port.packets[-1].frame().any())

    def test_same_count_different_wiring_hash_is_rejected(self):
        layout = copy.deepcopy(self.runtime.layout)
        item = layout["wiring"]["order"][0]
        item["reverse"] = not item["reverse"]
        changed = compile_layout(read_json(DATA / "catalog.json"), read_json(DATA / "constellation.json"), layout)
        self.assertEqual(changed.led_count, self.runtime.led_count)
        self.assertNotEqual(pack_runtime(changed)["metadata"]["scene_sha256"], self.digest)
        port = PartialSerial()
        with self.assertRaisesRegex(ValidationError, "SHA256"):
            self._stream(port, runtime=changed)
        self._assert_only_black_and_closed(port)

    def test_runtime_profile_mismatch_is_rejected_before_open_or_capture_replace(self):
        mismatch = dataclasses.replace(self.profile, expected_led_count=267)
        calls = []
        with self.assertRaisesRegex(ValidationError, "profile LED count"):
            stream_frames(self.runtime, "mock-port", {"effect": "twinkle"}, mismatch,
                          serial_factory=lambda **kwargs: calls.append(kwargs))
        self.assertEqual(calls, [])
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "capture.clp"
            output.write_bytes(b"previous capture")
            mismatch = dataclasses.replace(self.profile, scene_sha256="0" * 64)
            with self.assertRaisesRegex(ValidationError, "profile scene mapping"):
                capture_frames(self.runtime, output, {"effect": "twinkle"}, mismatch)
            self.assertEqual(output.read_bytes(), b"previous capture")
            self.assertFalse(output.with_suffix(".clp.tmp").exists())


if __name__ == "__main__":
    unittest.main()
