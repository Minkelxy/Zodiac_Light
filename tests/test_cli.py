"""Exercise offline build commands and failures before output mutation."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from constellation_lamp.__main__ import main
from constellation_lamp.layout import generate_layout
from constellation_lamp.model import read_json
from constellation_lamp.reports import write_json
from constellation_lamp.effects import EFFECT_NAMES


DATA = Path(__file__).resolve().parents[1] / "data"


class CommandTests(unittest.TestCase):
    def test_scaled_build_outputs_and_preserves_author_layout(self):
        original = (DATA / "layout.json").read_bytes()
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            legacy = Path(temp) / "legacy_layout.json"
            write_json(legacy, generate_layout(read_json(DATA / "catalog.json"), read_json(DATA / "constellation.json")))
            directory = Path(temp) / "output"
            self.assertEqual(main(["build", "--layout", str(legacy), "--width-mm", "700", "--output-dir", str(directory)]), 0)
            required = {"layout.json", "runtime.json", "cutting.csv", "wiring.csv", "constellation_data.h",
                        "constellation_compact.h", "compact.json", "effects_gallery.png"}
            required.update(f"preview_{effect}.png" for effect in EFFECT_NAMES)
            self.assertEqual({p.name for p in directory.iterdir()}, required)
            runtime = json.loads((directory / "runtime.json").read_text(encoding="utf-8"))
            self.assertEqual(runtime["led_count"], 586)
            self.assertEqual(runtime["rgb_buffer_bytes"], 586 * 3)
            self.assertEqual(main(["validate", "--layout", str(directory / "layout.json")]), 0)
        self.assertEqual((DATA / "layout.json").read_bytes(), original)

    def test_current_four_led_layout_stays_within_panel(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["build", "--output-dir", temp]), 0)
            runtime = json.loads((Path(temp) / "runtime.json").read_text(encoding="utf-8"))
            self.assertTrue(all(len(star["indices"]) == 4 for star in runtime["stars"]))
            self.assertEqual(len(runtime["pieces"]), 66)

    def test_invalid_build_settings_do_not_write_outputs(self):
        for arguments in (["--width-mm", "100"], ["--brightness", "2"], ["--seed", "-1"],
                          ["--exposure", "nan"], ["--route", "95168,95294"]):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "output"
                with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["build", "--output-dir", str(output), *arguments]), 2)
                self.assertFalse(output.exists())

    def test_effect_discovery_compact_export_and_offline_stream(self):
        from constellation_lamp.seriallink import FrameDecoder
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()) as captured:
            output = Path(temp)
            self.assertEqual(main(["effects"]), 0)
            self.assertIn("aurora", captured.getvalue())
            self.assertEqual(main(["export", "--compact", "--output", str(output / "mcu.h")]), 0)
            self.assertIn("CONSTELLATION_COMPACT_LED_COUNT 268u", (output / "mcu.h").read_text())
            self.assertEqual(main(["stream", "--dry-run", str(output / "demo.clp"), "--effect", "aurora",
                                   "--duration", ".1"]), 0)
            packets = FrameDecoder(268).feed((output / "demo.clp").read_bytes())
            self.assertEqual(len(packets), 4)
            self.assertFalse(packets[-1].frame().any())
            bad = output / "invalid.clp"
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["stream", "--dry-run", str(bad), "--fps", "100"]), 2)
            self.assertFalse(bad.exists())

    def test_config_presets_and_cli_overrides(self):
        from constellation_lamp.__main__ import _effect_params
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "effects.json"
            write_json(path, {"schema_version": 1, "defaults": {"brightness": .3, "seed": 42},
                              "presets": {"breath": {"breath_period_s": 9}}})
            args = SimpleNamespace(effect="breath", effect_config=path, data_dir=DATA, route=None,
                                   brightness=.1, seed=None, speed=None, gamma=None)
            params = _effect_params(args)
            self.assertEqual(params["brightness"], .1)
            self.assertEqual(params["seed"], 42)
            self.assertEqual(params["breath_period_s"], 9)


if __name__ == "__main__":
    unittest.main()
