"""Tests focus on logical versus electrical direction and deterministic time."""

from __future__ import annotations

import unittest
import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from constellation_lamp.effects import EFFECT_DEFAULTS, EFFECT_DESCRIPTIONS, EFFECT_LABELS, EFFECT_NAMES, default_route, render
from constellation_lamp.model import compile_layout, load_runtime, read_json


def fixture(reverse: bool = False):
    stars = [SimpleNamespace(id=name, hip=100 + i, name=name, x_mm=x, y_mm=y,
                             mag_v=2.0 + i, indices=())
             for i, (name, x, y) in enumerate((("a", 0, 0), ("b", 100, 0), ("c", 100, 100)))]
    leds = []
    for owner, star in enumerate(stars):
        indices = []
        for offset in (-2.5, 2.5):
            index = len(leds)
            leds.append(SimpleNamespace(index=index, piece_id=f"s{owner}", x_mm=star.x_mm + offset,
                y_mm=star.y_mm, owner_type="star", owner_index=owner, u=None))
            indices.append(index)
        star.indices = tuple(indices)
    edges = []
    for owner, (start, end) in enumerate(((stars[0], stars[1]), (stars[1], stars[2]))):
        indices = []
        for progress in np.arange(1, 19) / 20:
            index = len(leds)
            leds.append(SimpleNamespace(index=index, piece_id=f"e{owner}",
                x_mm=start.x_mm + progress * (end.x_mm - start.x_mm),
                y_mm=start.y_mm + progress * (end.y_mm - start.y_mm),
                owner_type="edge", owner_index=owner, u=float(progress)))
            indices.append(index)
        edges.append(SimpleNamespace(id=f"edge{owner}", start_id=start.id, end_id=end.id,
            length_mm=100.0, indices=tuple(indices), path_mm=((start.x_mm, start.y_mm), (end.x_mm, end.y_mm))))
    for _ in range(2):
        leds.append(SimpleNamespace(index=len(leds), piece_id="hidden", x_mm=-30, y_mm=-30,
                                    owner_type="hidden", owner_index=-1, u=None))
    if reverse:
        count = len(leds)
        for led in leds:
            led.index = count - 1 - led.index
        leds.reverse()
        for owner in stars + edges:
            owner.indices = tuple(count - 1 - i for i in owner.indices)
    return SimpleNamespace(leds=tuple(leds), stars=tuple(stars), edges=tuple(edges),
        pieces=(), wire_links=(), led_count=len(leds), pitch_mm=5.0, width_mm=100.0, height_mm=100.0)


class EffectTests(unittest.TestCase):
    def setUp(self):
        self.runtime = fixture()
        self.frame = np.zeros((self.runtime.led_count, 3), dtype=np.uint8)

    def test_in_place_and_hidden_dark(self):
        for effect in EFFECT_NAMES:
            self.assertIs(render(self.runtime, 1000, {"effect": effect}, {}, self.frame), self.frame)
            self.assertTrue(np.any(self.frame))
            self.assertFalse(np.any(self.frame[-2:]))

    def test_time_and_seed_are_reproducible_without_history(self):
        params = {"effect": "twinkle", "seed": 555, "brightness": 0.8}
        first = render(self.runtime, 2400, params, {}, self.frame).copy()
        state = {}
        render(self.runtime, 10000, params, state, self.frame)
        render(self.runtime, 2400, params, state, self.frame)
        np.testing.assert_array_equal(first, self.frame)
        changed = render(self.runtime, 2400, dict(params, seed=556), state, self.frame).copy()
        self.assertFalse(np.array_equal(first, changed))

    def test_electrical_reversal_preserves_all_physical_colors(self):
        reversed_runtime = fixture(reverse=True)
        for effect in EFFECT_NAMES:
            params = {"effect": effect, "route": ["c", "b", "a"], "brightness": 1.0}
            a = render(self.runtime, 720, params, {}, self.frame).copy()
            b = np.zeros_like(a)
            render(reversed_runtime, 720, params, {}, b)
            np.testing.assert_array_equal(a, b[::-1])

    def test_flow_route_reverse_changes_geometric_direction(self):
        params = {"effect": "flow", "flow_width_mm": 8.0, "brightness": 1.0}
        forward = render(self.runtime, 300, dict(params, route=["a", "b", "c"]), {}, self.frame).copy()
        backward = render(self.runtime, 300, dict(params, route=["c", "b", "a"]), {}, self.frame).copy()
        forward_peak = int(np.argmax(forward[:, 2]))
        backward_peak = int(np.argmax(backward[:, 2]))
        self.assertEqual(self.runtime.leds[forward_peak].owner_index, 0)
        self.assertEqual(self.runtime.leds[backward_peak].owner_index, 1)
        self.assertAlmostEqual(self.runtime.leds[forward_peak].x_mm, 40, delta=5)
        self.assertAlmostEqual(self.runtime.leds[backward_peak].y_mm, 60, delta=5)

    def test_cache_invalidates_on_seed_route_and_runtime(self):
        state = {}
        render(self.runtime, 100, {"effect": "flow", "route": ["a", "b"]}, state, self.frame)
        old = state["_route"]
        render(self.runtime, 100, {"effect": "flow", "route": ["b", "c"]}, state, self.frame)
        self.assertIsNot(old, state["_route"])
        for effect in EFFECT_NAMES:
            params = {"effect": effect, "seed": 100, "route": ["c", "b"]}
            actual = render(self.runtime, 1120, params, state, self.frame).copy()
            expected = render(self.runtime, 1120, params, {}, self.frame).copy()
            np.testing.assert_array_equal(actual, expected)

    def test_brightness_and_speed(self):
        for effect in EFFECT_NAMES:
            params = {"effect": effect, "brightness": 0}
            render(self.runtime, 1234, params, {}, self.frame)
            self.assertFalse(np.any(self.frame))
            params["brightness"] = 0.2
            params["speed"] = 2
            a = render(self.runtime, 1234, params, {}, self.frame).copy()
            b = render(self.runtime, 2468, dict(params, speed=1), {}, self.frame).copy()
            np.testing.assert_array_equal(a, b)
            self.assertLessEqual(int(a.max()), 51)

    def test_default_route_follows_graph(self):
        self.assertEqual(default_route(self.runtime), ["a", "b", "c"])

    def test_invalid_routes_are_clear(self):
        for route, message in ((["a", "c"], "no connecting edge"),
                               (["a", "unknown"], "unknown star"),
                               (["a"], "at least two"),
                               (["a", "a"], "no connecting edge")):
            with self.subTest(route=route), self.assertRaisesRegex(ValueError, message):
                render(self.runtime, 0, {"effect": "flow", "route": route}, {}, self.frame)

    def test_invalid_parameters(self):
        for params in ({"effect": "bad"}, {"seed": -1}, {"seed": 1.5}, {"brightness": 1.1},
                       {"speed": 0}, {"gamma": -1}, {"brightness": float("nan")},
                       {"effect": "flow", "flow_width_mm": 0},
                       {"effect": "ripple", "wavelength_mm": 0},
                       {"effect": "breath", "breath_period_s": 0},
                       {"effect": "breath", "breath_floor": 1.1},
                       {"effect": "aurora", "aurora_wavelength_mm": 0},
                       {"effect": "aurora", "aurora_contrast": -1},
                       {"effect": "sparkle", "sparkle_duration_s": 4},
                       {"effect": "sparkle", "sparkle_density": 1.1},
                       {"effect": "graph_wave", "source_star": "unknown"},
                       {"effect": "graph_wave", "graph_width_mm": 0},
                       {"effect": "graph_wave", "graph_period_s": 0},
                       {"effect": "draw", "draw_velocity_mm_s": 0},
                       {"effect": "draw", "draw_fade_s": 0},
                       {"effect": "draw", "draw_hold_s": -1},
                       {"effect": "meteor", "meteor_interval_s": 0.01},
                       {"effect": "meteor", "meteor_tail_mm": 0},
                       {"effect": "meteor", "meteor_angle_deg": float("nan")}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                render(self.runtime, 0, params, {}, self.frame)
        with self.assertRaisesRegex(ValueError, "time_ms"):
            render(self.runtime, -1, {}, {}, self.frame)
        with self.assertRaisesRegex(ValueError, "uint8"):
            render(self.runtime, 0, {}, {}, self.frame.astype(float))

    def test_graph_wave_uses_graph_distance_instead_of_spatial_radius(self):
        params = {"effect": "graph_wave", "source_star": "a", "graph_velocity_mm_s": 100,
                  "graph_width_mm": 5, "graph_period_s": 5, "brightness": 1}
        spatial_arrival = render(self.runtime, np.sqrt(2) * 1000, params, {}, self.frame).copy()
        graph_arrival = render(self.runtime, 2000, params, {}, self.frame).copy()
        c_index = self.runtime.stars[2].indices[0]
        self.assertLess(spatial_arrival[c_index].max(), 30)
        self.assertGreater(graph_arrival[c_index].max(), 240)

    def test_graph_and_draw_source_changes_invalidate_geometry_cache(self):
        state = {}
        for effect, key in (("graph_wave", "_graph"), ("draw", "_drawing")):
            render(self.runtime, 750, {"effect": effect, "source_star": "a"}, state, self.frame)
            previous = state[key]
            params = {"effect": effect, "source_star": "c"}
            actual = render(self.runtime, 750, params, state, self.frame).copy()
            self.assertIsNot(previous, state[key])
            expected = render(self.runtime, 750, params, {}, self.frame).copy()
            np.testing.assert_array_equal(actual, expected)

    def test_draw_covers_edges_and_fades_after_hold(self):
        state = {}
        params = {"effect": "draw", "source_star": "a", "draw_velocity_mm_s": 100,
                  "draw_hold_s": 1, "draw_fade_s": 1, "brightness": 1}
        render(self.runtime, 0, params, state, self.frame)
        self.assertEqual(set(state["_drawing"]["order"]), {"edge0", "edge1"})
        full = render(self.runtime, 2500, params, state, self.frame).copy()
        faded = render(self.runtime, 3999, params, state, self.frame).copy()
        self.assertGreater(int(full[list(self.runtime.edges[1].indices), 2].min()), 200)
        self.assertLess(float(faded.mean()), float(full.mean()) / 4)


class DefaultLayoutEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = Path(__file__).resolve().parents[1] / "data"
        cls.runtime = load_runtime(cls.data)

    def test_metadata_defaults_match_every_effect(self):
        self.assertEqual(len(EFFECT_NAMES), 9)
        for metadata in (EFFECT_LABELS, EFFECT_DESCRIPTIONS, EFFECT_DEFAULTS):
            self.assertEqual(set(metadata), set(EFFECT_NAMES))
        self.assertEqual(len(set(EFFECT_LABELS.values())), len(EFFECT_NAMES))
        frame = np.zeros((self.runtime.led_count, 3), dtype=np.uint8)
        for effect in EFFECT_NAMES:
            with self.subTest(effect=effect):
                render(self.runtime, 1500, {"effect": effect, **EFFECT_DEFAULTS[effect]}, {}, frame)
                self.assertTrue(np.any(frame))

    def test_real_scene_is_valid_dynamic_and_visually_distinct(self):
        self.assertEqual(self.runtime.led_count, 268)
        self.assertEqual(self.runtime.layout["panel"]["width_mm"], 400)
        self.assertEqual(self.runtime.layout["panel"]["height_mm"], 400)
        frame = np.zeros((self.runtime.led_count, 3), dtype=np.uint8)
        examples = []
        for effect in EFFECT_NAMES:
            with self.subTest(effect=effect):
                params = {"effect": effect, "brightness": 0.5, "seed": 12}
                first = render(self.runtime, 1400, params, {}, frame).copy()
                second = render(self.runtime, 2800, params, {}, frame).copy()
                self.assertTrue(np.any(first))
                self.assertTrue(np.any(second))
                self.assertFalse(np.array_equal(first, second))
                examples.append(first.tobytes())
        self.assertEqual(len(set(examples)), len(EFFECT_NAMES))

    def test_all_effects_ignore_frame_history_including_random_events(self):
        frame = np.zeros((self.runtime.led_count, 3), dtype=np.uint8)
        for effect in EFFECT_NAMES:
            params = {"effect": effect, "seed": 33}
            state = {}
            for time_ms in (1500, 9000, 0, 27000, 3200, 100, 1500):
                with self.subTest(effect=effect, time_ms=time_ms):
                    actual = render(self.runtime, time_ms, params, state, frame).copy()
                    expected = render(self.runtime, time_ms, params, {}, frame).copy()
                    np.testing.assert_array_equal(actual, expected)

    def test_real_wiring_order_and_din_reversal_do_not_change_physical_colors(self):
        layout = copy.deepcopy(self.runtime.layout)
        layout["wiring"]["order"].reverse()
        for piece in layout["wiring"]["order"]:
            piece["reverse"] = not piece["reverse"]
        changed = compile_layout(read_json(self.data / "catalog.json"),
                                 read_json(self.data / "constellation.json"), layout)

        def by_position(runtime, frame):
            return {(led.piece_id, round(led.x_mm, 6), round(led.y_mm, 6)): tuple(frame[led.index])
                    for led in runtime.leds}

        frame = np.zeros((self.runtime.led_count, 3), dtype=np.uint8)
        for effect in EFFECT_NAMES:
            with self.subTest(effect=effect):
                params = {"effect": effect, "seed": 8}
                a = render(self.runtime, 1700, params, {}, frame).copy()
                b = render(changed, 1700, params, {}, frame).copy()
                self.assertEqual(by_position(self.runtime, a), by_position(changed, b))

    def test_random_appearance_responds_to_seed(self):
        frame = np.zeros((self.runtime.led_count, 3), dtype=np.uint8)
        for effect in ("twinkle", "aurora", "sparkle", "meteor"):
            with self.subTest(effect=effect):
                a = render(self.runtime, 1500, {"effect": effect, "seed": 1}, {}, frame).copy()
                b = render(self.runtime, 1500, {"effect": effect, "seed": 2}, {}, frame).copy()
                self.assertFalse(np.array_equal(a, b))


if __name__ == "__main__":
    unittest.main()
