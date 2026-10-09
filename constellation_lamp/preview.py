"""Matplotlib desktop preview and an offscreen, backend-independent renderer."""

from __future__ import annotations

import time
import math
import textwrap
from numbers import Real
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from .effects import EFFECT_DESCRIPTIONS, EFFECT_LABELS, EFFECT_NAMES, render

if TYPE_CHECKING:
    from .hardware import HardwareProfile
    from .model import Runtime

_BACKGROUND = "#081320"
_TEXT = "#dce6ef"


def _preview_exposure(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)) or value <= 0:
        raise ValueError("exposure must be a positive finite number")
    return float(value)


def _display_rgb(frame: np.ndarray, exposure: float = 3.0) -> np.ndarray:
    # LED PWM values are linear light. Encode for a gamma-shaped monitor; this
    # display conversion never changes the RGB bytes sent to the strip.
    return np.power(np.clip(frame / 255.0 * exposure, 0, 1), 1.0 / 2.2)


def _render_params(effect: str, seed: int, brightness: float,
                   route: list[str] | None, params: dict[str, Any] | None) -> dict[str, Any]:
    if params is not None and not isinstance(params, dict):
        raise ValueError("params must be a dictionary or None")
    result = {"effect": effect, "seed": seed, "brightness": brightness, "speed": 1.0, "route": route}
    if params:
        result.update(params)
    return result


def _preset_map(presets: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if presets is None:
        return {}
    if not isinstance(presets, dict):
        raise ValueError("presets must be a dictionary or None")
    result = {}
    for effect, values in presets.items():
        if effect not in EFFECT_NAMES or not isinstance(values, dict):
            raise ValueError("presets must map known effect IDs to parameter dictionaries")
        result[effect] = dict(values)
    return result


def _initial_params(effect: str, seed: int, brightness: float, route: list[str] | None,
                    params: dict[str, Any] | None, presets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = _render_params(effect, seed, brightness, route, params)
    selected = result["effect"]
    if not isinstance(selected, str) or selected not in EFFECT_NAMES:
        raise ValueError(f"unknown effect {selected!r}")
    if selected in presets:
        result.update(presets[selected])
        if params:
            result.update(params)
        result["effect"] = selected
    return result


def _power_frame(frame: np.ndarray, profile: HardwareProfile | None) -> tuple[np.ndarray, dict[str, Any]]:
    if profile is None:
        return frame, {}
    # The transport helper only estimates power; it never opens a serial port.
    from .seriallink import limit_current
    return limit_current(frame, profile)


def _power_label(info: dict[str, Any], profile: HardwareProfile | None) -> str:
    if not info or profile is None:
        return ""
    return (f"Estimated current: {info['estimated_before_ma']:.0f} -> {info['estimated_after_ma']:.0f} mA\n"
            f"Budget: {info['limit_ma']:.0f} mA | Output scale: {info['scale']:.3f}\n"
            f"Profile: idle {profile.idle_led_ma:g} mA/LED, channel {profile.channel_ma:g} mA")


def _draw_layout(ax: Any, runtime: Runtime, frame: np.ndarray, exposure: float = 3.0) -> dict[str, Any]:
    ax.set_facecolor(_BACKGROUND)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (mm)", color=_TEXT)
    ax.set_ylabel("y (mm)", color=_TEXT)
    ax.tick_params(colors="#8094a6")
    for spine in ax.spines.values():
        spine.set_color("#263b4e")
    visible = np.array([led.owner_type != "hidden" for led in runtime.leds])
    xy = np.array([(led.x_mm, led.y_mm) for led in runtime.leds], dtype=float)
    visible_indices = np.flatnonzero(visible)
    rgb = _display_rgb(frame[visible], exposure)
    glow = ax.scatter(xy[visible, 0], xy[visible, 1], s=115, c=rgb, alpha=0.18,
                      linewidths=0, zorder=3)
    dots = ax.scatter(xy[visible, 0], xy[visible, 1], s=13, c=rgb,
                      linewidths=0, zorder=4, picker=6)
    labels = []
    for star in runtime.stars:
        labels.append(ax.text(star.x_mm + 7, star.y_mm - 7, star.name or str(star.hip),
                              color="#a9becd", fontsize=8, zorder=6))
    index_labels = [ax.text(led.x_mm + 2, led.y_mm - 2, str(led.index),
                           color="#b8d2e4", fontsize=5, visible=False, zorder=6)
                    for led in runtime.leds if led.owner_type != "hidden"]
    directions = []
    for edge in runtime.edges:
        path = getattr(edge, "path_mm", ())
        if not path:
            lookup = {s.id: s for s in runtime.stars}
            path = ((lookup[edge.start_id].x_mm, lookup[edge.start_id].y_mm),
                    (lookup[edge.end_id].x_mm, lookup[edge.end_id].y_mm))
        # Arrow follows a central path segment; the label spells out direction.
        middle = max(0, (len(path) - 2) // 2)
        start, end = np.array(path[middle]), np.array(path[middle + 1])
        a, b = start * 0.62 + end * 0.38, start * 0.38 + end * 0.62
        directions.append(ax.annotate("", xy=b, xytext=a,
            arrowprops={"arrowstyle": "->", "color": "#719cb7", "lw": 0.9},
            visible=False, zorder=5))
    wires = []
    for link in runtime.wire_links:
        line, = ax.plot([link.from_xy[0], link.to_xy[0]], [link.from_xy[1], link.to_xy[1]],
                        color="#dd8b57", linestyle="--", lw=0.8, alpha=0.65, visible=False, zorder=2)
        wires.append(line)
    if len(xy):
        active_xy = xy[visible] if np.any(visible) else xy
        min_xy, max_xy = active_xy.min(axis=0), active_xy.max(axis=0)
        margin = max(20, max(max_xy - min_xy) * 0.05)
        ax.set_xlim(min_xy[0] - margin, max_xy[0] + margin)
        ax.set_ylim(max_xy[1] + margin, min_xy[1] - margin)
    panel = getattr(runtime, "layout", {}).get("panel")
    if panel:
        from matplotlib.patches import Rectangle
        width, height = panel["width_mm"], panel["height_mm"]
        ax.add_patch(Rectangle((0, 0), width, height, fill=False,
                              edgecolor="#668cab", linewidth=1.1, linestyle="--", zorder=1))
        ax.text(2, -3, f"{width:g} x {height:g} mm panel", color="#9cb3c2", fontsize=8)
        ax.set_xlim(-12, width + 12)
        ax.set_ylim(height + 12, -12)
    ax.grid(alpha=0.07, color="#9cb3c2")
    return {"dots": dots, "glow": glow, "labels": labels, "indices": index_labels,
            "directions": directions, "wires": wires, "visible": visible,
            "visible_indices": visible_indices}


def save_preview(runtime: Runtime, path: str | Path, effect: str = "twinkle",
                 time_ms: float = 1500, seed: int = 1, brightness: float = 0.2,
                 route: list[str] | None = None, exposure: float = 3.0,
                 params: dict[str, Any] | None = None,
                 presets: dict[str, Any] | None = None,
                 hardware_profile: HardwareProfile | None = None) -> None:
    """Save a static PNG without changing Matplotlib's global GUI backend."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    exposure = _preview_exposure(exposure)
    frame = np.zeros((runtime.led_count, 3), dtype=np.uint8)
    render_params = _initial_params(effect, seed, brightness, route, params, _preset_map(presets))
    render(runtime, time_ms, render_params, {}, frame)
    frame, power_info = _power_frame(frame, hardware_profile)
    figure = Figure(figsize=(8, 9), facecolor=_BACKGROUND)
    FigureCanvasAgg(figure)
    ax = figure.add_subplot(111)
    _draw_layout(ax, runtime, frame, exposure)
    ax.set_title(f"Sagittarius | {EFFECT_LABELS[render_params['effect']]} | {runtime.led_count} LEDs\n"
                 f"t = {time_ms:.0f} ms | Preview exposure x{exposure:g}",
                 color=_TEXT, pad=14)
    if power_info:
        figure.text(0.055, 0.025, _power_label(power_info, hardware_profile), color=_TEXT, fontsize=8)
    figure.tight_layout(pad=1.6, rect=(0, 0.08 if power_info else 0, 1, 1))
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=170, facecolor=figure.get_facecolor())


def show(runtime: Runtime, effect: str = "twinkle", seed: int = 1,
         brightness: float = 0.2, route: list[str] | None = None, exposure: float = 3.0,
         params: dict[str, Any] | None = None,
         presets: dict[str, Any] | None = None,
         hardware_profile: HardwareProfile | None = None) -> None:
    """Open a desktop player. Hover a light to inspect its electrical mapping."""
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    from matplotlib.widgets import Button, CheckButtons, RadioButtons, Slider

    exposure = _preview_exposure(exposure)
    preset_values = _preset_map(presets)
    params = _initial_params(effect, seed, brightness, route, params, preset_values)
    base_common = {name: params[name] for name in ("seed", "brightness", "speed", "gamma", "route") if name in params}
    effect_state: dict[str, Any] = {}
    raw_frame = np.zeros((runtime.led_count, 3), dtype=np.uint8)
    frame = np.zeros((runtime.led_count, 3), dtype=np.uint8)
    render(runtime, 0, params, effect_state, raw_frame)
    initial_frame, power_info = _power_frame(raw_frame, hardware_profile)
    frame[:] = initial_frame
    figure = plt.figure(figsize=(13, 9.5), facecolor=_BACKGROUND)
    try:
        figure.canvas.manager.set_window_title("Sagittarius LED simulator")
    except AttributeError:
        pass
    ax = figure.add_axes((0.055, 0.19, 0.67, 0.72))
    artists = _draw_layout(ax, runtime, frame, exposure)
    ax.set_title("Sagittarius LED simulator", color=_TEXT, pad=12)
    figure.text(0.78, 0.935, f"{len(runtime.stars)} stars / {len(runtime.edges)} edges\n"
                f"{runtime.led_count} LEDs / {runtime.led_count * runtime.pitch_mm / 1000:.2f} m\n"
                f"RGB frame: {runtime.led_count * 3} bytes\n"
                f"Preview exposure x{exposure:g}", color=_TEXT, fontsize=10, va="top")
    figure.text(0.78, 0.825, "Effect", color=_TEXT)
    effect_ax = figure.add_axes((0.77, 0.47, 0.215, 0.34), facecolor="#132538")
    labels = tuple(EFFECT_LABELS[name] for name in EFFECT_NAMES)
    label_ids = {label: name for name, label in zip(EFFECT_NAMES, labels)}
    radio = RadioButtons(effect_ax, labels, active=EFFECT_NAMES.index(params["effect"]), activecolor="#58c4ee")
    for label in radio.labels:
        label.set_color(_TEXT)
    description = figure.text(0.775, 0.455, textwrap.fill(EFFECT_DESCRIPTIONS[params["effect"]], 34),
                              color="#92aabd", fontsize=8, va="top")
    check_ax = figure.add_axes((0.77, 0.255, 0.215, 0.15), facecolor="#132538")
    toggles = CheckButtons(check_ax, ("Star labels", "LED indices", "Edge direction", "Back wires"),
                          (True, False, False, False))
    for label in toggles.labels:
        label.set_color(_TEXT)
    speed_ax = figure.add_axes((0.815, 0.208, 0.14, 0.022), facecolor="#21364a")
    initial_speed = float(params["speed"])
    speed = Slider(speed_ax, "Speed", min(0.1, initial_speed), max(4.0, initial_speed),
                   valinit=initial_speed, color="#58c4ee")
    brightness_ax = figure.add_axes((0.815, 0.155, 0.14, 0.022), facecolor="#21364a")
    dimmer = Slider(brightness_ax, "Brightness", 0, 1, valinit=params["brightness"], color="#58c4ee")
    for slider in (speed, dimmer):
        slider.label.set_color(_TEXT)
        slider.valtext.set_color(_TEXT)
        slider.valtext.set_position((1.08, 0.5))
    button_ax = figure.add_axes((0.8, 0.082, 0.16, 0.045))
    pause = Button(button_ax, "Pause", color="#1e3549", hovercolor="#345571")
    pause.label.set_color(_TEXT)
    status = figure.text(0.055, 0.07, "", color=_TEXT, fontsize=9)
    power_text = figure.text(0.055, 0.125, _power_label(power_info, hardware_profile),
                             color="#a9becd", fontsize=8, va="top")
    figure.text(0.78, 0.035, "Space: play / pause\nHover LEDs for details", color="#92aabd", fontsize=9)
    clock = {"playing": True, "last": time.perf_counter(), "ms": 0.0}
    error_state = {"message": "", "restoring_radio": False}
    hover = ax.annotate("", xy=(0, 0), xytext=(14, 14), textcoords="offset points",
                         bbox={"boxstyle": "round,pad=0.5", "fc": "#172b3f", "ec": "#658baa"},
                         color=_TEXT, fontsize=8, visible=False, zorder=20)

    def update_clock() -> None:
        now = time.perf_counter()
        if clock["playing"]:
            clock["ms"] += (now - clock["last"]) * 1000 * params["speed"]
        clock["last"] = now

    def draw_frame() -> None:
        # Player integrates speed so slider changes preserve animation phase.
        render_params = dict(params, speed=1.0)
        render(runtime, clock["ms"], render_params, effect_state, raw_frame)
        output, current_info = _power_frame(raw_frame, hardware_profile)
        frame[:] = output
        power_info.clear()
        power_info.update(current_info)
        power_text.set_text(_power_label(power_info, hardware_profile))
        rgb = _display_rgb(frame[artists["visible"]], exposure)
        artists["dots"].set_facecolors(rgb)
        artists["glow"].set_facecolors(rgb)
        route_text = ""
        if params["effect"] == "flow":
            selected = effect_state["_route"]["ids"]
            route_text = " | Route: " + " > ".join(s.removeprefix("hip_") for s in selected)
        suffix = "\n" + error_state["message"] if error_state["message"] else ""
        status.set_text(f"t = {clock['ms'] / 1000:.2f} s | {params['effect']}" + route_text + suffix)

    def toggle_pause(_event: Any = None) -> None:
        update_clock()
        clock["playing"] = not clock["playing"]
        pause.label.set_text("Pause" if clock["playing"] else "Play")
        figure.canvas.draw_idle()

    def change_effect(selected: str) -> None:
        if error_state["restoring_radio"]:
            return
        update_clock()
        previous_params = dict(params)
        previous = params["effect"]
        selected = label_ids[selected]
        candidate = dict(base_common) if preset_values else dict(params)
        candidate.update(preset_values.get(selected, {}))
        candidate["effect"] = selected
        try:
            # Validate the configured speed before draw_frame normalises it to
            # one; the player owns integration of the effective animation time.
            render(runtime, 0, candidate, {}, np.zeros_like(raw_frame))
            params.clear()
            params.update(candidate)
            error_state["message"] = ""
            draw_frame()
            sync_controls()
        except ValueError as error:
            params.clear()
            params.update(previous_params)
            error_state["message"] = f"Cannot select {selected}: {error}"
            error_state["restoring_radio"] = True
            try:
                radio.set_active(EFFECT_NAMES.index(previous))
            finally:
                error_state["restoring_radio"] = False
            draw_frame()
        description.set_text(textwrap.fill(EFFECT_DESCRIPTIONS[params["effect"]], 34))
        figure.canvas.draw_idle()

    def sync_controls() -> None:
        # Programmatic preset changes update the widgets without their callbacks
        # treating the update as a new manual edit or integrating time twice.
        old_speed_events, old_dimmer_events = speed.eventson, dimmer.eventson
        speed.eventson = dimmer.eventson = False
        try:
            value = float(params["speed"])
            speed.valmin, speed.valmax = min(0.1, value), max(4.0, value)
            speed.ax.set_xlim(speed.valmin, speed.valmax)
            speed.set_val(value)
            dimmer.set_val(params["brightness"])
        finally:
            speed.eventson, dimmer.eventson = old_speed_events, old_dimmer_events

    def change_speed(value: float) -> None:
        update_clock()
        params["speed"] = value

    def change_brightness(value: float) -> None:
        params["brightness"] = value
        try:
            draw_frame()
        except ValueError as error:
            error_state["message"] = str(error)
            status.set_text(error_state["message"])
        figure.canvas.draw_idle()

    def change_overlay(label: str) -> None:
        key = {"Star labels": "labels", "LED indices": "indices",
               "Edge direction": "directions", "Back wires": "wires"}[label]
        for artist in artists[key]:
            artist.set_visible(not artist.get_visible())
        figure.canvas.draw_idle()

    def on_hover(event: Any) -> None:
        if event.inaxes is ax:
            contains, picked = artists["dots"].contains(event)
            if contains and picked["ind"].size:
                index = int(artists["visible_indices"][picked["ind"][0]])
                led = runtime.leds[index]
                if led.owner_type == "star":
                    star = runtime.stars[led.owner_index]
                    owner = f"Star: {star.name} / HIP {star.hip}"
                else:
                    edge = runtime.edges[led.owner_index]
                    owner = f"Edge: {edge.id}\n{edge.start_id} > {edge.end_id}\nu = {led.u:.4f}"
                hover.xy = (led.x_mm, led.y_mm)
                hover.set_text(f"LED {index} / {led.piece_id}\n{owner}\n"
                               f"x = {led.x_mm:.2f}, y = {led.y_mm:.2f} mm\n"
                               f"RGB = {tuple(int(v) for v in frame[index])}")
                hover.set_visible(True)
                figure.canvas.draw_idle()
                return
        if hover.get_visible():
            hover.set_visible(False)
            figure.canvas.draw_idle()

    def tick(_number: int) -> tuple[Any, ...]:
        update_clock()
        try:
            draw_frame()
        except ValueError as error:
            clock["playing"] = False
            status.set_text(str(error))
        return artists["dots"], artists["glow"], status

    pause.on_clicked(toggle_pause)
    radio.on_clicked(change_effect)
    speed.on_changed(change_speed)
    dimmer.on_changed(change_brightness)
    toggles.on_clicked(change_overlay)
    figure.canvas.mpl_connect("motion_notify_event", on_hover)
    figure.canvas.mpl_connect("key_press_event", lambda event: toggle_pause() if event.key == " " else None)
    animation = FuncAnimation(figure, tick, interval=33, blit=False, cache_frame_data=False)
    # Keep the animation and widgets alive throughout the blocking GUI loop.
    figure._constellation_player = (animation, pause, radio, speed, dimmer, toggles)
    # Inspectable controller also lets headless tests exercise real UI callbacks.
    figure._constellation_controller = {"params": params, "state": effect_state, "frame": frame,
        "clock": clock, "artists": artists, "status": status, "hover": hover, "tick": tick,
        "description": description, "raw_frame": raw_frame, "power": power_info,
        "power_text": power_text}
    draw_frame()
    plt.show()
