"""A portable overview of effect colours on actual LED positions."""

from pathlib import Path

import numpy as np

from .effects import EFFECT_LABELS, render
from .preview import _BACKGROUND, _TEXT, _display_rgb


def save_gallery(runtime, path, presets, *, exposure=3.0, time_ms=2200, hardware_profile=None):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    figure = Figure(figsize=(12, 12), facecolor=_BACKGROUND)
    FigureCanvasAgg(figure)
    xy = np.array([(led.x_mm, led.y_mm) for led in runtime.leds])
    visible = np.array([led.owner_type != "hidden" for led in runtime.leds])
    frame = np.zeros((runtime.led_count, 3), np.uint8)
    columns = 3
    rows = (len(presets) + columns - 1) // columns
    for i, params in enumerate(presets):
        ax = figure.add_subplot(rows, columns, i + 1)
        ax.set_facecolor(_BACKGROUND)
        sample_ms = 1250 if params["effect"] in ("sparkle", "meteor") else time_ms
        render(runtime, sample_ms, params, {}, frame)
        if hardware_profile is not None:
            from .seriallink import limit_current
            frame, _ = limit_current(frame, hardware_profile)
        colour = _display_rgb(frame[visible], exposure)
        ax.scatter(xy[visible, 0], xy[visible, 1], c=colour, s=120, alpha=.16, linewidths=0)
        ax.scatter(xy[visible, 0], xy[visible, 1], c=colour, s=12, linewidths=0)
        ax.set_aspect("equal")
        panel = runtime.layout.get("panel")
        if panel:
            ax.set_xlim(-8, panel["width_mm"] + 8)
            ax.set_ylim(panel["height_mm"] + 8, -8)
        else:
            ax.invert_yaxis()
        ax.set_axis_off()
        ax.set_title(f"{params['effect']} | {EFFECT_LABELS[params['effect']]}", color=_TEXT, fontsize=11)
    power_note = f" | {hardware_profile.current_limit_ma:g} mA estimated cap" if hardware_profile else ""
    figure.suptitle(f"Sagittarius | {runtime.led_count} LEDs | {len(presets)} light effects{power_note}\nMonitor exposure x{exposure:g}",
                   color=_TEXT, fontsize=15)
    figure.tight_layout(rect=(0, 0, 1, .95), pad=1.2)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=150, facecolor=_BACKGROUND)
