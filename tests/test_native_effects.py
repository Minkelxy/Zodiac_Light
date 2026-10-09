"""Compile the portable MCU renderer and compare actual RGB with Python.

The comparisons distinguish integer-scene quantization from math differences.
No SDK, board, serial port or network is needed for these host C++ tests.
"""

import copy
import dataclasses
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from constellation_lamp.compact import export_compact_c, pack_runtime
from constellation_lamp.effects import EFFECT_NAMES, default_route, render
from constellation_lamp.model import load_runtime


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "firmware-idf" / "main"


def quantized_runtime(runtime):
    """Decode exported tables as a Python runtime, without changing originals."""
    table = pack_runtime(runtime)["tables"]
    if not dataclasses.is_dataclass(runtime):
        result = copy.deepcopy(runtime)
        for index, led in enumerate(result.leds):
            led.x_mm = table["led_x_dm"][index] / 10
            led.y_mm = table["led_y_dm"][index] / 10
            if led.u is not None:
                led.u = table["led_u16"][index] / 65535
        for index, star in enumerate(result.stars):
            star.x_mm = table["star_x_dm"][index] / 10
            star.y_mm = table["star_y_dm"][index] / 10
            if star.mag_v is not None:
                star.mag_v = table["star_mag_centi"][index] / 100
        for index, edge in enumerate(result.edges):
            edge.length_mm = table["edge_length_dm"][index] / 10
        return result
    return dataclasses.replace(runtime,
        leds=tuple(dataclasses.replace(led, x_mm=table["led_x_dm"][i] / 10,
                      y_mm=table["led_y_dm"][i] / 10,
                      u=table["led_u16"][i] / 65535 if led.u is not None else None)
                   for i, led in enumerate(runtime.leds)),
        stars=tuple(dataclasses.replace(star, x_mm=table["star_x_dm"][i] / 10,
                       y_mm=table["star_y_dm"][i] / 10,
                       mag_v=table["star_mag_centi"][i] / 100 if star.mag_v is not None else None)
                    for i, star in enumerate(runtime.stars)),
        edges=tuple(dataclasses.replace(edge, length_mm=table["edge_length_dm"][i] / 10)
                    for i, edge in enumerate(runtime.edges)))


HARNESS = r'''
#include "native_effects.h"
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <new>
#include <sstream>
#include <string>

static bool trackHeap = false;
static unsigned heapAllocations = 0;
void* operator new(std::size_t size) {
  if (trackHeap) ++heapAllocations;
  void* result = std::malloc(size);
  if (!result) throw std::bad_alloc();
  return result;
}
void operator delete(void* value) noexcept { std::free(value); }
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete[](void* value) noexcept { ::operator delete(value); }

static clp::RenderContext contexts[2];
static uint8_t rgb[CONSTELLATION_COMPACT_RGB_FRAME_BYTES];

int main() {
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line == "META") {
      clp::NativeParams defaults;
      trackHeap = true;
      const clp::RenderError result = clp::initNativeEffects(contexts[0], defaults);
      trackHeap = false;
      if (result != clp::RenderError::Ok || heapAllocations) return 8;
      std::cout << "META " << sizeof(clp::RenderContext) << ' ' << sizeof(clp::NativeParams)
                << ' ' << contexts[0].route_size << ' ' << std::setprecision(17)
                << contexts[0].route_length << ' ' << contexts[0].draw_length << ' ' << contexts[0].graph_max;
      for (size_t i = 0; i < contexts[0].route_size; ++i)
        std::cout << ' ' << constellation_compact_star_hip[contexts[0].route_stars[i]];
      std::cout << '\n';
      continue;
    }
    std::istringstream input(line);
    unsigned slot, effect;
    uint64_t time;
    int source;
    clp::NativeParams p;
    if (!(input >> slot >> effect >> time >> p.seed >> p.brightness >> p.speed >> p.gamma >> source)) return 1;
    if (slot > 1) return 2;
    p.effect = static_cast<clp::Effect>(effect);
    p.source_star = static_cast<int16_t>(source);
    std::string option;
    while (input >> option) {
      const size_t delimiter = option.find('=');
      if (delimiter == std::string::npos) return 3;
      const std::string key = option.substr(0, delimiter), value = option.substr(delimiter + 1);
      const double number = std::strtod(value.c_str(), NULL);
      if (key == "route") {
        std::istringstream route(value);
        std::string star;
        while (std::getline(route, star, ',')) {
          if (p.route_count == clp::kNativeRouteCapacity) return 4;
          p.route[p.route_count++] = static_cast<uint16_t>(std::strtoul(star.c_str(), NULL, 10));
        }
      } else if (key == "center_x_mm") { p.custom_center = true; p.center_x_mm = number; }
      else if (key == "center_y_mm") { p.custom_center = true; p.center_y_mm = number; }
#define PARAM(name) else if (key == #name) p.name = number;
      PARAM(pitch_mm) PARAM(flow_velocity_mm_s) PARAM(flow_width_mm) PARAM(wavelength_mm)
      PARAM(flow_period_s) PARAM(draw_period_s)
      PARAM(ripple_velocity_mm_s) PARAM(breath_period_s) PARAM(breath_floor)
      PARAM(aurora_wavelength_mm) PARAM(aurora_velocity_mm_s) PARAM(aurora_contrast)
      PARAM(sparkle_period_s) PARAM(sparkle_duration_s) PARAM(sparkle_density)
      PARAM(graph_velocity_mm_s) PARAM(graph_width_mm) PARAM(graph_period_s)
      PARAM(draw_velocity_mm_s) PARAM(draw_hold_s) PARAM(draw_fade_s) PARAM(draw_head_width_mm)
      PARAM(meteor_angle_deg) PARAM(meteor_velocity_mm_s) PARAM(meteor_tail_mm)
      PARAM(meteor_width_mm) PARAM(meteor_interval_s)
#undef PARAM
      else return 5;
    }
    clp::RenderContext& context = contexts[slot];
    for (uint8_t& byte : rgb) byte = 0xa5;
    trackHeap = true;
    clp::RenderError error = context.initialized ?
        clp::renderNativeEffects(context, time, p, rgb, sizeof(rgb)) : clp::RenderError::RequiresInit;
    if (error == clp::RenderError::RequiresInit) {
      error = clp::initNativeEffects(context, p);
      if (error == clp::RenderError::Ok) error = clp::renderNativeEffects(context, time, p, rgb, sizeof(rgb));
    }
    trackHeap = false;
    if (heapAllocations) return 6;
    if (error != clp::RenderError::Ok) {
      for (uint8_t byte : rgb) if (byte != 0xa5) return 7;
      std::cout << "ERR " << clp::renderErrorName(error) << '\n';
      continue;
    }
    for (uint8_t byte : rgb)
      std::cout << std::hex << std::setfill('0') << std::setw(2) << static_cast<unsigned>(byte);
    std::cout << std::dec << '\n';
  }
  return 0;
}
'''


class NativeEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requested = os.environ.get("CXX")
        cls.compiler = (shutil.which(requested) if requested else None) or next(
            (path for name in ("cl", "g++", "clang++") if (path := shutil.which(name))), None)
        if cls.compiler is None:
            raise unittest.SkipTest("Host C++ compiler unavailable; scripts/run_checks.cmd initializes MSVC")
        cls.temporary = tempfile.TemporaryDirectory(prefix="clp-effects-")
        cls.directory = Path(cls.temporary.name)
        cls.runtime = load_runtime(ROOT / "data")
        cls.quantized = quantized_runtime(cls.runtime)
        cls.executable = cls.compile_scene(cls.runtime, "sagittarius")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @classmethod
    def compile_scene(cls, runtime, name):
        directory = cls.directory / name
        directory.mkdir(exist_ok=True)
        export_compact_c(runtime, directory / "constellation_compact.h")
        source = directory / "harness.cpp"
        source.write_text(HARNESS, encoding="utf-8")
        executable = directory / ("effects.exe" if os.name == "nt" else "effects")
        if Path(cls.compiler).name.lower() in ("cl", "cl.exe"):
            command = [cls.compiler, "/nologo", "/EHsc", "/std:c++14", "/W4", "/O2",
                       "/I" + str(directory), "/I" + str(NATIVE), "/Fe:" + str(executable),
                       str(source), str(NATIVE / "native_effects.cpp")]
        else:
            command = [cls.compiler, "-std=c++14", "-O2", "-Wall", "-Wextra", "-pedantic",
                       "-I", str(directory), "-I", str(NATIVE), str(source),
                       str(NATIVE / "native_effects.cpp"), "-o", str(executable)]
        result = subprocess.run(command, cwd=directory, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60)
        if result.returncode:
            raise AssertionError("Native effects compile failed:\n" + result.stdout + result.stderr)
        return executable

    def frames(self, samples, *, executable=None, runtime=None):
        runtime = self.runtime if runtime is None else runtime
        commands = []
        for time, params in samples:
            source = params.get("source_star")
            source_index = next(i for i, star in enumerate(runtime.stars) if star.id == source) if source else -1
            values = [str(params.get("slot", 0)), str(EFFECT_NAMES.index(params.get("effect", "twinkle"))),
                      str(time), str(params.get("seed", 1)), str(params.get("brightness", 0.2)),
                      str(params.get("speed", 1)), str(params.get("gamma", 2.2)), str(source_index)]
            for key, value in params.items():
                if key in ("slot", "effect", "seed", "brightness", "speed", "gamma", "source_star"):
                    continue
                if key == "route":
                    value = ",".join(str(next(i for i, star in enumerate(runtime.stars) if star.id == star_id)) for star_id in value)
                values.append(f"{key}={value}")
            commands.append(" ".join(values))
        result = subprocess.run([str(executable or self.executable)], input="\n".join(commands) + "\n",
                                capture_output=True, text=True, encoding="ascii", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), len(samples))
        return [line if line.startswith("ERR ") else np.frombuffer(bytes.fromhex(line), np.uint8).reshape(runtime.led_count, 3)
                for line in lines]

    @staticmethod
    def python_frame(runtime, time, params):
        frame = np.zeros((runtime.led_count, 3), np.uint8)
        render(runtime, time, {key: value for key, value in params.items() if key not in ("slot", "pitch_mm")}, {}, frame)
        return frame

    def test_all_nine_defaults_match_python_and_quantization_budget(self):
        times = (0, 1, 123, 999, 1500, 3199, 3200, 9999, 12000, 42000, 86400000)
        samples = [(time, {"effect": effect}) for effect in EFFECT_NAMES for time in times]
        frames = self.frames(samples)
        maxima = {effect: 0 for effect in EFFECT_NAMES}
        for (time, params), actual in zip(samples, frames):
            with self.subTest(effect=params["effect"], time=time):
                quantized = self.python_frame(self.quantized, time, params)
                original = self.python_frame(self.runtime, time, params)
                math_error = np.abs(actual.astype(int) - quantized.astype(int))
                self.assertLessEqual(int(math_error.max()), 1)
                error = int(np.abs(actual.astype(int) - original.astype(int)).max())
                maxima[params["effect"]] = max(maxima[params["effect"]], error)
                if time <= 42000:
                    self.assertLessEqual(error, 2)
                self.assertLessEqual(int(actual.max()), 51)
        print("Native auto-period max RGB difference (includes 24h drift):", json.dumps(maxima, sort_keys=True))

    def test_authoritative_cycle_periods_remove_long_term_quantization_drift(self):
        from constellation_lamp.effects import _graph_distances, _source_star

        route = default_route(self.runtime)
        by_pair = {(edge.start_id, edge.end_id): edge.length_mm for edge in self.runtime.edges}
        by_pair.update({(end, start): value for (start, end), value in list(by_pair.items())})
        route_length = sum(by_pair[(a, b)] for a, b in zip(route, route[1:]))
        graph = _graph_distances(self.runtime, _source_star(self.runtime, {}), {})
        angle = np.deg2rad(-35)
        along = np.array([led.x_mm * np.cos(angle) + led.y_mm * np.sin(angle)
                          for led in self.runtime.leds if led.owner_type != "hidden"])
        periods = {"flow": {"flow_period_s": route_length / 140},
                   "graph_wave": {"graph_period_s": graph["max_mm"] / 100 + 4 * 25 / 100 + 1},
                   "draw": {"draw_period_s": sum(edge.length_mm for edge in self.runtime.edges) / 160 + 2.5 + 1.5},
                   "meteor": {"meteor_interval_s": (float(along.max() - along.min()) + 20 + 80 * 3) / 220 + 0.8}}
        samples = [(time, {"effect": effect, **values}) for effect, values in periods.items()
                   for time in (86400000, 604800000, 4294967296)]
        maxima = {}
        for (time, params), actual in zip(samples, self.frames(samples)):
            expected = self.python_frame(self.runtime, time, params)
            error = int(np.abs(actual.astype(int) - expected.astype(int)).max())
            maxima[params["effect"]] = max(maxima.get(params["effect"], 0), error)
            self.assertLessEqual(error, 2, (params["effect"], time))
        print("Native fixed-period long-time max RGB difference:", json.dumps(maxima, sort_keys=True))

    def test_custom_params_seed_source_and_full_brightness(self):
        samples = [
            (2345, {"effect": "twinkle", "seed": 0xFFFFFFFF, "brightness": 1, "gamma": 1.7, "speed": 1.4}),
            (1100, {"effect": "flow", "route": default_route(self.runtime)[::-1], "flow_width_mm": 14, "brightness": 1}),
            (4500, {"effect": "ripple", "center_x_mm": 100, "center_y_mm": 200, "wavelength_mm": 200, "brightness": 1}),
            (2200, {"effect": "breath", "breath_period_s": 7, "breath_floor": 0.2, "gamma": 1, "brightness": 1}),
            (9876, {"effect": "aurora", "seed": 33, "aurora_contrast": 0.9, "aurora_wavelength_mm": 170, "brightness": 1}),
            (17800, {"effect": "sparkle", "seed": 67, "sparkle_period_s": 4, "sparkle_duration_s": 1.7, "brightness": 1}),
            (6500, {"effect": "graph_wave", "source_star": self.runtime.stars[0].id, "graph_period_s": 7, "graph_width_mm": 12, "brightness": 1}),
            (7100, {"effect": "draw", "source_star": self.runtime.stars[-1].id, "draw_velocity_mm_s": 100, "draw_head_width_mm": 13, "brightness": 1}),
            (9200, {"effect": "meteor", "meteor_angle_deg": 72, "meteor_tail_mm": 60, "meteor_interval_s": 9, "seed": 71, "brightness": 1}),
        ]
        for (time, params), actual in zip(samples, self.frames(samples)):
            expected = self.python_frame(self.quantized, time, params)
            with self.subTest(effect=params["effect"]):
                self.assertLessEqual(int(np.abs(actual.astype(int) - expected.astype(int)).max()), 1)
                self.assertLessEqual(int(actual.max()), 255)

    def test_contexts_are_independent_and_time_has_no_history(self):
        samples = [(time, {"effect": effect, "seed": 559, "slot": slot})
                   for effect in EFFECT_NAMES for slot, time in ((0, 2400), (1, 10000), (0, 99000), (0, 2400), (1, 2400))]
        frames = self.frames(samples)
        for index in range(0, len(frames), 5):
            np.testing.assert_array_equal(frames[index], frames[index + 3])
            np.testing.assert_array_equal(frames[index], frames[index + 4])

    def test_electrical_reversal_hidden_leds_and_repeated_flow_route(self):
        from test_effects import fixture

        runtime = fixture()
        reversed_runtime = fixture(reverse=True)
        normal = self.compile_scene(runtime, "fixture")
        reverse = self.compile_scene(reversed_runtime, "fixture-reversed")
        samples = [(720, {"effect": effect, "brightness": 1, "route": ["c", "b", "a", "b", "c"]}) for effect in EFFECT_NAMES]
        a = self.frames(samples, executable=normal, runtime=runtime)
        b = self.frames(samples, executable=reverse, runtime=reversed_runtime)
        for params, first, second in zip(samples, a, b):
            with self.subTest(effect=params[1]["effect"]):
                np.testing.assert_array_equal(first, second[::-1])
                self.assertFalse(first[-2:].any())
                expected = self.python_frame(quantized_runtime(runtime), params[0], params[1])
                self.assertLessEqual(int(np.abs(first.astype(int) - expected.astype(int)).max()), 1)

    def test_validation_and_derived_overflow_leave_output_unchanged(self):
        samples = [(1, {"brightness": -1}), (1, {"gamma": 0}), (1, {"speed": 0}),
                   (1, {"effect": "sparkle", "sparkle_duration_s": 4}),
                   (1, {"effect": "meteor", "meteor_interval_s": 0.01}),
                   (1, {"effect": "flow", "route": [self.runtime.stars[0].id, self.runtime.stars[-1].id]}),
                   (1000, {"effect": "aurora", "speed": 1e308}),
                   (18446744073709551615, {"effect": "twinkle", "speed": 1e308})]
        results = self.frames(samples)
        self.assertEqual(results, ["ERR invalid_params"] * 5 + ["ERR invalid_route", "ERR time_overflow", "ERR time_overflow"])

    def test_zero_brightness_and_speed_equivalence(self):
        samples = [(1234, {"effect": effect, "brightness": 0}) for effect in EFFECT_NAMES]
        self.assertTrue(all(not frame.any() for frame in self.frames(samples)))
        samples = [(time, {"effect": effect, "speed": speed}) for effect in EFFECT_NAMES
                   for time, speed in ((1234, 2), (2468, 1))]
        frames = self.frames(samples)
        for index in range(0, len(frames), 2):
            np.testing.assert_array_equal(frames[index], frames[index + 1])

    def test_ties_to_even_at_full_flow_peak(self):
        from test_effects import fixture

        runtime = fixture()
        executable = self.compile_scene(runtime, "ties-even")
        samples = [(0, {"effect": "flow", "route": ["a", "b"], "brightness": 0.3, "gamma": 1})]
        actual = self.frames(samples, executable=executable, runtime=runtime)[0]
        expected = self.python_frame(quantized_runtime(runtime), *samples[0])
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(int(actual[runtime.stars[0].indices[0], 0]), 76)

    def test_fixed_workspace_size_and_default_route(self):
        result = subprocess.run([str(self.executable)], input="META\n", capture_output=True,
                                text=True, encoding="ascii", timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        fields = result.stdout.split()
        self.assertEqual(fields[0], "META")
        self.assertLess(int(fields[1]), 20000)
        expected_hips = [star.hip for star_id in default_route(self.quantized)
                         for star in self.quantized.stars if star.id == star_id]
        self.assertEqual([int(value) for value in fields[7:]], expected_hips)
        self.assertEqual(int(fields[3]), len(expected_hips))
        print(f"Native fixed workspace {fields[1]} B, params {fields[2]} B, default route {expected_hips}")


if __name__ == "__main__":
    unittest.main()
