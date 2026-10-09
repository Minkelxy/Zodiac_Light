"""Preview pixels and hover values match the actual current-limited RGB frame."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backend_bases import MouseEvent

from constellation_lamp.effects import render
from constellation_lamp.model import load_runtime
from constellation_lamp.preview import _display_rgb, _draw_layout, save_preview, show
from constellation_lamp.seriallink import HardwareProfile, limit_current


class PreviewPowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(Path(__file__).resolve().parents[1] / "data")
        cls.profile = HardwareProfile(current_limit_ma=2000)

    def tearDown(self):
        plt.close("all")

    def _open(self, **kwargs):
        def draw_window():
            plt.gcf().canvas.draw()
        with patch.object(plt, "show", side_effect=draw_window):
            show(self.runtime, **kwargs)
        return plt.gcf()

    def test_bright_frame_is_limited_before_exposure_and_hover(self):
        figure = self._open(effect="breath", brightness=1, exposure=1, hardware_profile=self.profile)
        controller = figure._constellation_controller
        controller["clock"]["playing"] = False
        controller["clock"]["ms"] = 3000
        controller["tick"](0)
        raw = np.zeros((self.runtime.led_count, 3), np.uint8)
        render(self.runtime, 3000, {"effect": "breath", "brightness": 1}, {}, raw)
        limited, power = limit_current(raw, self.profile)
        self.assertLess(power["scale"], 0.4)
        self.assertLessEqual(power["estimated_after_ma"], 2000)
        np.testing.assert_array_equal(controller["raw_frame"], raw)
        np.testing.assert_array_equal(controller["frame"], limited)
        self.assertEqual(controller["power"], power)
        self.assertIn("Budget: 2000 mA", controller["power_text"].get_text())
        self.assertIn("Output scale:", controller["power_text"].get_text())
        visible = controller["artists"]["visible"]
        np.testing.assert_allclose(controller["artists"]["dots"].get_facecolors()[:, :3], _display_rgb(limited[visible], 1))
        figure.canvas.draw()
        led = self.runtime.leds[0]
        x, y = figure.axes[0].transData.transform((led.x_mm, led.y_mm))
        figure.canvas.callbacks.process("motion_notify_event", MouseEvent("motion_notify_event", figure.canvas, x, y))
        self.assertIn(f"RGB = {tuple(int(v) for v in limited[0])}", controller["hover"].get_text())

    def test_power_info_tracks_manual_brightness_without_resetting_it(self):
        figure = self._open(brightness=1, hardware_profile=self.profile)
        controller = figure._constellation_controller
        controller["clock"]["playing"] = False
        dimmer = figure._constellation_player[4]
        self.assertLess(controller["power"]["scale"], 1)
        dimmer.set_val(0.1)
        self.assertEqual(controller["power"]["scale"], 1)
        controller["tick"](0)
        self.assertEqual(controller["params"]["brightness"], 0.1)
        np.testing.assert_array_equal(controller["raw_frame"], controller["frame"])

    def test_optional_power_profile_keeps_legacy_behavior_and_ignores_transport_budget(self):
        # Deliberately invalid serial timing should not prevent an offline power preview.
        profile = HardwareProfile(fps=0.01, baud=300, packet_timeout_ms=5, stream_timeout_ms=1)
        self._open(hardware_profile=profile)
        figure = self._open(hardware_profile=None)
        controller = figure._constellation_controller
        np.testing.assert_array_equal(controller["frame"], controller["raw_frame"])
        self.assertEqual(controller["power"], {})
        self.assertEqual(controller["power_text"].get_text(), "")

    def test_static_preview_uses_the_same_limited_output(self):
        raw = np.zeros((self.runtime.led_count, 3), np.uint8)
        render(self.runtime, 3000, {"effect": "breath", "brightness": 1}, {}, raw)
        expected, _power = limit_current(raw, self.profile)
        with tempfile.TemporaryDirectory() as folder, patch("constellation_lamp.preview._draw_layout", wraps=_draw_layout) as draw:
            output = Path(folder) / "preview.png"
            save_preview(self.runtime, output, effect="breath", time_ms=3000, brightness=1,
                         hardware_profile=self.profile)
            self.assertTrue(output.exists())
            np.testing.assert_array_equal(draw.call_args.args[2], expected)
        with self.assertRaisesRegex(ValueError, "standby"):
            show(self.runtime, hardware_profile=HardwareProfile(current_limit_ma=100))


if __name__ == "__main__":
    unittest.main()
