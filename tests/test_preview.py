"""Exercise the real player widgets using Agg, without opening a desktop window."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backend_bases import KeyEvent, MouseEvent

from constellation_lamp.model import load_runtime
from constellation_lamp.effects import EFFECT_DESCRIPTIONS, EFFECT_LABELS, EFFECT_NAMES, render
from constellation_lamp.preview import _display_rgb, save_preview, show


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(Path(__file__).resolve().parents[1] / "data")

    def tearDown(self):
        plt.close("all")

    def _open(self, **kwargs):
        captured = {}

        def draw_window():
            figure = plt.gcf()
            figure.canvas.draw()
            captured["figure"] = figure

        with patch.object(plt, "show", side_effect=draw_window):
            show(self.runtime, **kwargs)
        return captured["figure"]

    def test_exposure_is_display_only(self):
        frame = np.array([[0, 20, 255]], dtype=np.uint8)
        copy = frame.copy()
        normal, brighter = _display_rgb(frame, 1), _display_rgb(frame, 3)
        np.testing.assert_array_equal(frame, copy)
        self.assertTrue(np.all(brighter >= normal))
        self.assertEqual(brighter[0, 0], 0)
        self.assertEqual(brighter[0, 2], 1)

    def test_offline_export_and_exposure_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "nested" / "preview.png"
            save_preview(self.runtime, output, effect="ripple", exposure=3)
            image = plt.imread(output)
            self.assertGreater(image.shape[0], 100)
            self.assertGreater(image.shape[1], 100)
        for exposure in (0, -1, float("nan"), float("inf"), "3"):
            with self.subTest(exposure=exposure), self.assertRaisesRegex(ValueError, "exposure"):
                save_preview(self.runtime, "unused.png", exposure=exposure)

    def test_player_controls_pause_speed_brightness_overlays_and_hover(self):
        figure = self._open(exposure=3)
        controller = figure._constellation_controller
        _animation, pause, radio, speed, dimmer, toggles = figure._constellation_player
        self.assertIn("Preview exposure x3", "\n".join(t.get_text() for t in figure.texts))
        figure.canvas.callbacks.process("key_press_event", KeyEvent("key_press_event", figure.canvas, key=" "))
        self.assertFalse(controller["clock"]["playing"])
        self.assertEqual(pause.label.get_text(), "Play")
        frozen = controller["clock"]["ms"]
        controller["tick"](1)
        self.assertEqual(controller["clock"]["ms"], frozen)
        speed.set_val(2.5)
        self.assertEqual(controller["params"]["speed"], 2.5)
        radio.set_active(1)
        self.assertEqual(controller["params"]["effect"], "flow")
        radio.set_active(2)
        self.assertEqual(controller["params"]["effect"], "ripple")
        dimmer.set_val(0)
        self.assertFalse(np.any(controller["frame"]))
        dimmer.set_val(0.2)
        self.assertTrue(np.any(controller["frame"]))
        toggles.set_active(0)
        self.assertFalse(any(a.get_visible() for a in controller["artists"]["labels"]))
        for toggle_index, group in ((1, "indices"), (2, "directions"), (3, "wires")):
            toggles.set_active(toggle_index)
            self.assertTrue(controller["artists"][group])
            self.assertTrue(all(a.get_visible() for a in controller["artists"][group]))
        figure.canvas.draw()
        led = self.runtime.leds[0]
        x, y = figure.axes[0].transData.transform((led.x_mm, led.y_mm))
        figure.canvas.callbacks.process("motion_notify_event", MouseEvent("motion_notify_event", figure.canvas, x, y))
        self.assertTrue(controller["hover"].get_visible())
        self.assertIn("LED 0", controller["hover"].get_text())
        figure.canvas.callbacks.process("motion_notify_event", MouseEvent("motion_notify_event", figure.canvas, 0, 0))
        self.assertFalse(controller["hover"].get_visible())

    def test_invalid_flow_selection_recovers_and_other_controls_continue(self):
        figure = self._open(route=["hip_95168", "missing"])
        controller = figure._constellation_controller
        _animation, _pause, radio, _speed, dimmer, _toggles = figure._constellation_player
        radio.set_active(1)
        self.assertEqual(controller["params"]["effect"], "twinkle")
        self.assertEqual(radio.value_selected, EFFECT_LABELS["twinkle"])
        self.assertIn("Cannot select flow", controller["status"].get_text())
        dimmer.set_val(0.4)
        controller["tick"](0)
        self.assertIn("Cannot select flow", controller["status"].get_text())
        radio.set_active(2)
        self.assertEqual(controller["params"]["effect"], "ripple")
        self.assertNotIn("Cannot select", controller["status"].get_text())
        with self.assertRaisesRegex(ValueError, "unknown star"):
            show(self.runtime, effect="flow", route=["hip_95168", "missing"])

    def test_all_nine_effects_can_be_selected_with_descriptions(self):
        figure = self._open()
        controller = figure._constellation_controller
        _animation, _pause, radio, _speed, _dimmer, _toggles = figure._constellation_player
        for index, effect in enumerate(EFFECT_NAMES):
            with self.subTest(effect=effect):
                radio.set_active(index)
                self.assertEqual(controller["params"]["effect"], effect)
                self.assertEqual(radio.value_selected, EFFECT_LABELS[effect])
                self.assertEqual(controller["description"].get_text().replace("\n", " "),
                                 EFFECT_DESCRIPTIONS[effect])
                self.assertTrue(np.any(controller["frame"]))
        # The nine-choice list has its own vertical space above the overlays.
        self.assertGreaterEqual(figure.axes[1].get_position().y0, figure.axes[2].get_position().y1)

    def test_config_parameters_and_speed_pass_through_without_double_speed(self):
        supplied = {"effect": "breath", "breath_period_s": 2.5, "speed": 6.0,
                    "brightness": 0.4, "gamma": 1.5, "seed": 9}
        figure = self._open(params=supplied)
        controller = figure._constellation_controller
        _animation, _pause, radio, speed, dimmer, _toggles = figure._constellation_player
        self.assertEqual(radio.value_selected, EFFECT_LABELS["breath"])
        self.assertEqual(speed.val, 6)
        self.assertGreaterEqual(speed.valmax, 6)
        self.assertEqual(dimmer.val, 0.4)
        self.assertEqual(controller["params"]["breath_period_s"], 2.5)
        self.assertEqual(supplied["speed"], 6)  # Caller-owned config is untouched.
        figure.canvas.callbacks.process("key_press_event", KeyEvent("key_press_event", figure.canvas, key=" "))
        controller["clock"]["ms"] = 1000
        controller["tick"](0)
        expected = np.zeros_like(controller["frame"])
        render(self.runtime, 1000, dict(supplied, speed=1), {}, expected)
        np.testing.assert_array_equal(controller["frame"], expected)
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / "first.png"
            second = Path(folder) / "second.png"
            save_preview(self.runtime, first, params=supplied)
            save_preview(self.runtime, second, params=dict(supplied, gamma=2.2))
            self.assertFalse(np.array_equal(plt.imread(first), plt.imread(second)))

    def test_effect_presets_replace_fields_and_update_sliders_without_phase_jump(self):
        presets = {
            "twinkle": {"seed": 1, "brightness": 0.2, "speed": 1, "gamma": 2.2},
            "breath": {"seed": 6, "brightness": 0.8, "speed": 0.5, "gamma": 1.6, "breath_period_s": 2},
            "aurora": {"seed": 3, "brightness": 0.3, "speed": 6, "aurora_wavelength_mm": 110},
        }
        with patch("constellation_lamp.preview.time.perf_counter", return_value=0) as timer:
            figure = self._open(presets=presets)
            controller = figure._constellation_controller
            _animation, _pause, radio, speed, dimmer, _toggles = figure._constellation_player
            timer.return_value = 2
            controller["tick"](0)
            timer.return_value = 2.5
            radio.set_active(EFFECT_NAMES.index("breath"))
            self.assertEqual(controller["clock"]["ms"], 2500)
            self.assertEqual(controller["params"]["breath_period_s"], 2)
            self.assertEqual(controller["params"]["seed"], 6)
            self.assertEqual(speed.val, 0.5)
            self.assertEqual(dimmer.val, 0.8)
            expected = np.zeros_like(controller["frame"])
            render(self.runtime, 2500, dict(controller["params"], speed=1), {}, expected)
            np.testing.assert_array_equal(controller["frame"], expected)
            timer.return_value = 4.5
            controller["tick"](0)
            self.assertEqual(controller["clock"]["ms"], 3500)
            # Paused manual changes remain active on subsequent frames.
            figure.canvas.callbacks.process("key_press_event", KeyEvent("key_press_event", figure.canvas, key=" "))
            timer.return_value = 30
            speed.set_val(2)
            dimmer.set_val(0.42)
            controller["tick"](0)
            self.assertEqual(controller["clock"]["ms"], 3500)
            self.assertEqual(controller["params"]["speed"], 2)
            self.assertEqual(controller["params"]["brightness"], 0.42)
            timer.return_value = 50
            figure.canvas.callbacks.process("key_press_event", KeyEvent("key_press_event", figure.canvas, key=" "))
            timer.return_value = 51
            controller["tick"](0)
            self.assertEqual(controller["clock"]["ms"], 5500)
            radio.set_active(EFFECT_NAMES.index("aurora"))
            self.assertEqual(controller["clock"]["ms"], 5500)
            self.assertNotIn("breath_period_s", controller["params"])
            self.assertEqual(speed.val, 6)
            self.assertEqual(speed.valmax, 6)
            self.assertEqual(dimmer.val, 0.3)
            timer.return_value = 52
            controller["tick"](0)
            self.assertEqual(controller["clock"]["ms"], 11500)
            self.assertEqual(presets["breath"]["brightness"], 0.8)
            self.assertEqual(presets["breath"]["speed"], 0.5)

    def test_invalid_preset_recovers_previous_settings_and_slider_values(self):
        figure = self._open(presets={"twinkle": {"speed": 2, "brightness": 0.4},
                                    "breath": {"speed": 0, "brightness": 0.8}})
        controller = figure._constellation_controller
        _animation, _pause, radio, speed, dimmer, _toggles = figure._constellation_player
        radio.set_active(EFFECT_NAMES.index("breath"))
        self.assertEqual(controller["params"]["effect"], "twinkle")
        self.assertEqual(controller["params"]["speed"], 2)
        self.assertEqual(speed.val, 2)
        self.assertEqual(dimmer.val, 0.4)
        self.assertIn("Cannot select breath", controller["status"].get_text())
        for invalid in ([], {"wrong": {}}, {"breath": 7}):
            with self.subTest(presets=invalid), self.assertRaisesRegex(ValueError, "presets"):
                show(self.runtime, presets=invalid)


if __name__ == "__main__":
    unittest.main()
