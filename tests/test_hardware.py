"""Budgets and identities at the source-data/firmware boundary."""
import copy
import dataclasses
import tempfile
import unittest
from pathlib import Path

from constellation_lamp.compact import export_compact_c, pack_runtime
from constellation_lamp.hardware import HardwareProfile
from constellation_lamp.model import ValidationError, compile_layout, load_runtime, read_json

DATA = Path(__file__).resolve().parents[1] / "data"


class HardwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(DATA)

    def test_derived_fps_keeps_default_and_adapts_slow_uart(self):
        profile = HardwareProfile()
        self.assertEqual(profile.adapt_fps(268).fps, 30)
        slow = dataclasses.replace(profile, baud=115200).adapt_fps(268)
        self.assertLess(slow.fps, 12)
        self.assertGreater(slow.fps, 10)
        self.assertEqual(slow.fps * 10, round(slow.fps * 10))
        slow.validate(268)
        self.assertEqual(slow.baud, 115200)
        self.assertEqual(profile.fps, 30)
        with self.assertRaises(ValidationError):
            dataclasses.replace(profile, baud=9600).adapt_fps(268)
        with self.assertRaises(ValidationError):
            profile.adapt_fps(268, .1)  # watchdog leaves no feasible cadence

    def test_same_led_count_different_wiring_changes_identity(self):
        original = pack_runtime(self.runtime)["metadata"]["scene_sha256"]
        layout = copy.deepcopy(self.runtime.layout)
        layout["wiring"]["order"].reverse()
        for segment in layout["wiring"]["order"]:
            segment["reverse"] = not segment["reverse"]
        changed = compile_layout(read_json(DATA / "catalog.json"), read_json(DATA / "constellation.json"), layout)
        self.assertEqual(changed.led_count, self.runtime.led_count)
        self.assertNotEqual(pack_runtime(changed)["metadata"]["scene_sha256"], original)
        profile = dataclasses.replace(HardwareProfile(), expected_led_count=268, scene_sha256=original)
        profile.validate_runtime(self.runtime)
        with self.assertRaisesRegex(ValidationError, "mapping differs"):
            profile.validate_runtime(changed)
        with self.assertRaisesRegex(ValidationError, "LED count differs"):
            dataclasses.replace(profile, expected_led_count=270).validate_runtime(self.runtime)

    def test_identity_is_stable_across_cosmetic_names_and_c_header(self):
        packed = pack_runtime(self.runtime)
        renamed = dataclasses.replace(self.runtime, stars=tuple(
            dataclasses.replace(star, name="Display name") for star in self.runtime.stars))
        identity = packed["metadata"]["scene_sha256"]
        self.assertEqual(pack_runtime(renamed)["metadata"]["scene_sha256"], identity)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "scene.h"
            export_compact_c(self.runtime, path)
            self.assertIn(f'#define CONSTELLATION_COMPACT_SCENE_SHA256 "{identity}"', path.read_text())
        self.assertEqual(packed["metadata"]["table_bytes"], 3718)

    def test_malformed_identity_fields_rejected(self):
        for change in ({"require_device_identity": "true"}, {"expected_led_count": True}, {"baud": 2**2000},
                       {"scene_sha256": "x" * 64}, {"scene_sha256": "A" * 64}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                dataclasses.replace(HardwareProfile(), **change).validate(268)


if __name__ == "__main__":
    unittest.main()
