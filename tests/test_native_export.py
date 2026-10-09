"""Validate authoritative offline parameters against Python and C++ consumers."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from constellation_lamp.compact import export_compact_c, pack_runtime
from constellation_lamp.effectspec import EFFECT_NAMES
from constellation_lamp.model import ValidationError, load_runtime
from constellation_lamp.native_export import build_native_presets
from scripts.prepare_firmware import prepare_inputs


ROOT = Path(__file__).resolve().parents[1]


class NativePresetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.runtime = load_runtime(ROOT / "data")
        self.raw = json.loads((ROOT / "data" / "effects.json").read_text(encoding="utf-8"))
        self.effects = self.directory / "effects.json"
        self.write_effects()

    def write_effects(self):
        self.effects.write_text(json.dumps(self.raw), encoding="utf-8")

    def test_periods_match_independent_full_precision_python_effect_caches(self):
        import numpy as np
        from constellation_lamp.effects import render
        _, metadata = build_native_presets(self.runtime, self.effects)
        frame = np.zeros((self.runtime.led_count, 3), dtype=np.uint8)
        state = {}
        render(self.runtime, 0, {"effect": "flow"}, state, frame)
        flow = metadata["presets"]["flow"]
        self.assertEqual(tuple(flow["route_star_ids"]), state["_route"]["ids"])
        self.assertAlmostEqual(flow["params"]["flow_period_s"], state["_route"]["length_mm"] / 140, places=13)
        state = {}
        render(self.runtime, 0, {"effect": "graph_wave"}, state, frame)
        graph = metadata["presets"]["graph_wave"]
        self.assertAlmostEqual(graph["graph_max_mm"], state["_graph"]["max_mm"], places=13)
        self.assertAlmostEqual(graph["params"]["graph_period_s"], state["_graph"]["max_mm"] / 100 + 2, places=13)
        state = {}
        render(self.runtime, 0, {"effect": "draw"}, state, frame)
        draw = metadata["presets"]["draw"]
        self.assertAlmostEqual(draw["params"]["draw_period_s"], state["_drawing"]["length_mm"] / 160 + 4, places=13)
        meteor = metadata["presets"]["meteor"]
        angle = math.radians(-35)
        visible = [led for led in self.runtime.leds if led.owner_type in ("star", "edge")]
        projection = np.array([led.x_mm for led in visible]) * math.cos(angle) + np.array([led.y_mm for led in visible]) * math.sin(angle)
        expected = (float(np.ptp(projection)) + 20 + 3 * 80) / 220 + .8
        self.assertAlmostEqual(meteor["params"]["meteor_interval_s"], expected, places=13)

    def test_metadata_has_repeatable_source_and_header_fingerprints(self):
        first = build_native_presets(self.runtime, self.effects)
        self.assertEqual(first, build_native_presets(self.runtime, self.effects))
        header, metadata = first
        self.assertEqual(metadata["effects_sha256"], hashlib.sha256(self.effects.read_bytes()).hexdigest())
        self.assertEqual(metadata["header_sha256"], hashlib.sha256(header.encode("utf-8")).hexdigest())
        self.assertEqual(tuple(metadata["presets"]), EFFECT_NAMES)
        self.raw["presets"]["aurora"]["aurora_contrast"] = .3
        self.write_effects()
        new_header, changed = build_native_presets(self.runtime, self.effects)
        self.assertNotEqual(header, new_header)
        self.assertNotEqual(metadata["header_sha256"], changed["header_sha256"])

    def test_automatic_source_is_pinned_before_magnitude_quantization_changes_tie(self):
        stars = list(self.runtime.stars)
        stars[0] = dataclasses.replace(stars[0], mag_v=1.003)
        stars[1] = dataclasses.replace(stars[1], mag_v=1.004)
        runtime = dataclasses.replace(self.runtime, stars=tuple(stars))
        packed = pack_runtime(runtime)
        self.assertEqual(packed["tables"]["star_mag_centi"][:2], [100, 100])
        self.assertGreater(stars[0].hip, stars[1].hip)
        _, metadata = build_native_presets(runtime, self.effects)
        for row in metadata["presets"].values():
            self.assertTrue(row["source_was_automatic"])
            self.assertEqual(row["params"]["source_star"], 0)
            self.assertEqual(row["source_star_id"], stars[0].id)

    def test_custom_common_route_source_center_and_explicit_periods_are_preserved(self):
        edge = self.runtime.edges[0]
        route = [edge.start_id, edge.end_id, edge.start_id, edge.end_id]
        self.raw["defaults"] = {"seed": 0xFFFFFFFF, "brightness": .31, "speed": 1.75, "gamma": 1.4}
        self.raw["presets"]["flow"] = {"route": route, "flow_velocity_mm_s": 77, "flow_width_mm": 19}
        self.raw["presets"]["ripple"] = {"center_x_mm": -42.123456, "center_y_mm": 51.125}
        self.raw["presets"]["graph_wave"] = {"source_star": edge.end_id, "graph_period_s": 13.123456789123}
        self.raw["presets"]["meteor"]["meteor_interval_s"] = 17.123456789123
        self.write_effects()
        _, metadata = build_native_presets(self.runtime, self.effects)
        presets = metadata["presets"]
        for row in presets.values():
            self.assertEqual(tuple(row["params"][key] for key in ("seed", "brightness", "speed", "gamma")),
                             (0xFFFFFFFF, .31, 1.75, 1.4))
            self.assertEqual(row["params"]["pitch_mm"], self.runtime.pitch_mm)
        self.assertEqual(presets["flow"]["route_star_ids"], route)
        self.assertAlmostEqual(presets["flow"]["params"]["flow_period_s"], edge.length_mm * 3 / 77)
        self.assertEqual(presets["graph_wave"]["params"]["source_star"],
                         [star.id for star in self.runtime.stars].index(edge.end_id))
        self.assertEqual(presets["graph_wave"]["params"]["graph_period_s"], 13.123456789123)
        self.assertEqual(presets["meteor"]["params"]["meteor_interval_s"], 17.123456789123)
        self.assertEqual(presets["ripple"]["params"]["center_x_mm"], -42.123456)
        self.assertEqual(presets["ripple"]["params"]["center_y_mm"], 51.125)

    def test_illegal_presets_are_rejected_before_existing_input_files_change(self):
        project = self.directory / "project"
        shutil.copytree(ROOT / "data", project / "data")
        inputs = self.directory / "inputs"
        config = self.directory / "sdkconfig"
        config.write_text("CONFIG_CLP_LOCAL_MODE=0\n", encoding="utf-8")
        prepare_inputs(project, inputs, config)
        original = {path: path.read_bytes() for path in inputs.iterdir()}
        original[config] = config.read_bytes()
        edge = self.runtime.edges[0]
        variants = (("flow", {"route": [edge.start_id]}),
                    ("flow", {"route": [edge.start_id, "unknown"]}),
                    ("flow", {"route": [edge.start_id, edge.start_id]}),
                    ("flow", {"route": [edge.start_id, edge.end_id] * 22}),
                    ("graph_wave", {"source_star": 0}),
                    ("ripple", {"center_x_mm": float("nan")}),
                    ("aurora", {"aurora_contrast": 1.1}),
                    ("sparkle", {"sparkle_period_s": .2, "sparkle_duration_s": .5}),
                    ("meteor", {"meteor_interval_s": .01}),
                    ("twinkle", {"typo_brightness": .1}),
                    ("draw", {"draw_velocity_mm_s": 0}))
        for effect, params in variants:
            with self.subTest(effect=effect, params=params):
                raw = copy.deepcopy(self.raw)
                raw["presets"][effect] = params
                (project / "data" / "effects.json").write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaises(ValidationError):
                    prepare_inputs(project, inputs, config, effect=effect)
                self.assertEqual(original, {path: path.read_bytes() for path in original})

    def test_generated_cpp_initializes_and_renders_each_effect(self):
        compiler = shutil.which("cl") or shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("A host C++ compiler is required")
        header, metadata = build_native_presets(self.runtime, self.effects)
        (self.directory / "native_presets.h").write_text(header, encoding="utf-8")
        export_compact_c(self.runtime, self.directory / "constellation_compact.h")
        source = self.directory / "verify.cpp"
        source.write_text('''#include "native_presets.h"
#include <iostream>
#include <iomanip>
static clp::RenderContext context;
static uint8_t rgb[CONSTELLATION_COMPACT_RGB_FRAME_BYTES];
int main() {
  std::cout << std::setprecision(17);
  for (unsigned effect = 0; effect != 9; ++effect) {
    clp::NativeParams p = clp::generatedNativeParams(effect);
    if (static_cast<unsigned>(p.effect) != effect) return 1;
    if (clp::initNativeEffects(context, p) != clp::RenderError::Ok) return 2;
    if (clp::renderNativeEffects(context, 86400000, p, rgb, sizeof(rgb)) != clp::RenderError::Ok) return 3;
    std::cout << p.flow_period_s << ' ' << p.draw_period_s << ' '
              << p.graph_period_s << ' ' << p.meteor_interval_s << '\\n';
  }
}
''', encoding="utf-8")
        main = ROOT / "firmware-idf" / "main"
        executable = self.directory / "verify.exe"
        if Path(compiler).stem.lower() == "cl":
            command = [compiler, "/nologo", "/EHsc", "/std:c++14", "/I" + str(self.directory),
                       "/I" + str(main), str(source), str(main / "native_effects.cpp"),
                       "/Fe:" + str(executable)]
        else:
            command = [compiler, "-std=c++14", "-I", str(self.directory), "-I", str(main),
                       str(source), str(main / "native_effects.cpp"), "-o", str(executable)]
        completed = subprocess.run(command, capture_output=True, text=True, cwd=self.directory)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = subprocess.run([str(executable)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = result.stdout.splitlines()
        self.assertEqual(len(rows), len(EFFECT_NAMES))
        for effect, row in zip(EFFECT_NAMES, rows):
            expected = metadata["presets"][effect]["params"]
            self.assertEqual(list(map(float, row.split())),
                             [expected[key] for key in ("flow_period_s", "draw_period_s", "graph_period_s", "meteor_interval_s")])


if __name__ == "__main__":
    unittest.main()
