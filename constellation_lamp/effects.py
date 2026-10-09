"""Portable LED effects: explicit time, seed, state and an RGB output buffer.

The effect calculations use logical edge progress, never electrical LED order.
Gamma correction is applied before the global brightness multiplier.  A full
intensity channel therefore reaches round(255 * brightness).
"""

from __future__ import annotations

import heapq
import math
from numbers import Integral, Real
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from .model import Runtime

from .effectspec import (EFFECT_NAMES, EFFECT_LABELS, EFFECT_DESCRIPTIONS,
                         EFFECT_DEFAULTS, default_route)


def _number(params: dict[str, Any], name: str, default: float, *, minimum: float,
            maximum: float | None = None, inclusive: bool = True) -> float:
    value = params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value) or (value < minimum if inclusive else value <= minimum):
        operator = ">=" if inclusive else ">"
        raise ValueError(f"{name} must be finite and {operator} {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value




def _mix32(value: int) -> int:
    """Small integer mixer, reproducible in C without a Python RNG."""
    value &= 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 0x7FEB352D) & 0xFFFFFFFF
    value ^= value >> 15
    value = (value * 0x846CA68B) & 0xFFFFFFFF
    return value ^ (value >> 16)


def _prepared(runtime: Runtime, seed: int, state: dict[str, Any]) -> dict[str, Any]:
    cached = state.get("_prepared")
    if isinstance(cached, dict) and cached.get("runtime") is runtime and cached.get("seed") == seed:
        return cached
    count = runtime.led_count
    x = np.empty(count, dtype=float)
    y = np.empty(count, dtype=float)
    owner_index = np.empty(count, dtype=np.int32)
    star_mask = np.zeros(count, dtype=bool)
    edge_mask = np.zeros(count, dtype=bool)
    for led in runtime.leds:
        x[led.index], y[led.index] = led.x_mm, led.y_mm
        owner_index[led.index] = led.owner_index
        star_mask[led.index] = led.owner_type == "star"
        edge_mask[led.index] = led.owner_type == "edge"
    phases = np.zeros(len(runtime.stars))
    rates = np.zeros(len(runtime.stars))
    magnitudes = np.ones(len(runtime.stars))
    for index, star in enumerate(runtime.stars):
        mixed = _mix32(seed ^ int(star.hip))
        phases[index] = mixed / 4294967296.0 * math.tau
        rates[index] = 0.45 + _mix32(mixed) / 4294967296.0 * 0.5
        mag = 3.5 if star.mag_v is None else star.mag_v
        magnitudes[index] = np.clip(1.0 - 0.07 * (mag - 2.0), 0.55, 1.0)
    cached = {
        "runtime": runtime, "seed": seed, "x": x, "y": y,
        "owner_index": owner_index, "stars": star_mask, "edges": edge_mask,
        "visible": star_mask | edge_mask, "phases": phases, "rates": rates,
        "magnitudes": magnitudes, "work": np.zeros((count, 3), dtype=float),
        "seed_phase": _mix32(seed) / 4294967296.0,
    }
    state["_prepared"] = cached
    state.pop("_route", None)
    return cached


def _source_star(runtime: Runtime, params: dict[str, Any]) -> str:
    if not runtime.stars:
        raise ValueError("this effect requires at least one star")
    chosen = params.get("source_star")
    if chosen is None:
        return min(runtime.stars, key=lambda s: (math.inf if s.mag_v is None else s.mag_v, s.hip)).id
    if not isinstance(chosen, str) or chosen not in {star.id for star in runtime.stars}:
        raise ValueError(f"source_star references unknown star {chosen!r}")
    return chosen


def _adjacency(runtime: Runtime) -> dict[str, list[tuple[str, Any, bool]]]:
    result = {star.id: [] for star in runtime.stars}
    for edge in runtime.edges:
        result[edge.start_id].append((edge.end_id, edge, False))
        result[edge.end_id].append((edge.start_id, edge, True))
    for links in result.values():
        links.sort(key=lambda row: (row[0], row[1].id))
    return result


def _graph_distances(runtime: Runtime, source: str, state: dict[str, Any]) -> dict[str, Any]:
    cached = state.get("_graph")
    if isinstance(cached, dict) and cached.get("runtime") is runtime and cached.get("source") == source:
        return cached
    adjacency = _adjacency(runtime)
    distances = {star.id: math.inf for star in runtime.stars}
    distances[source] = 0.0
    queue = [(0.0, source)]
    while queue:
        distance, star_id = heapq.heappop(queue)
        if distance > distances[star_id]:
            continue
        for neighbor, edge, _reverse in adjacency[star_id]:
            candidate = distance + edge.length_mm
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    per_led = np.full(runtime.led_count, math.inf)
    for star in runtime.stars:
        per_led[list(star.indices)] = distances[star.id]
    for edge in runtime.edges:
        indices = np.asarray(edge.indices, dtype=np.intp)
        u = np.array([runtime.leds[int(index)].u for index in indices])
        per_led[indices] = np.minimum(distances[edge.start_id] + u * edge.length_mm,
                                      distances[edge.end_id] + (1 - u) * edge.length_mm)
    finite = np.isfinite(per_led)
    cached = {"runtime": runtime, "source": source, "distance": per_led,
              "finite": finite, "max_mm": float(per_led[finite].max()) if finite.any() else 0.0}
    state["_graph"] = cached
    return cached


def _drawing_order(runtime: Runtime, source: str, state: dict[str, Any]) -> dict[str, Any]:
    cached = state.get("_drawing")
    if isinstance(cached, dict) and cached.get("runtime") is runtime and cached.get("source") == source:
        return cached
    adjacency = _adjacency(runtime)
    visited = set()
    order = []

    def visit(star_id: str) -> None:
        for neighbor, edge, reverse in adjacency[star_id]:
            if edge.id not in visited:
                visited.add(edge.id)
                order.append((edge, reverse))
                visit(neighbor)

    visit(source)
    for star_id in sorted(adjacency):
        visit(star_id)
    per_led = np.full(runtime.led_count, math.inf)
    arrivals = {star.id: math.inf for star in runtime.stars}
    arrivals[source] = 0.0
    offset = 0.0
    for edge, reverse in order:
        start, end = (edge.end_id, edge.start_id) if reverse else (edge.start_id, edge.end_id)
        arrivals[start] = min(arrivals[start], offset)
        arrivals[end] = min(arrivals[end], offset + edge.length_mm)
        indices = np.asarray(edge.indices, dtype=np.intp)
        u = np.array([runtime.leds[int(index)].u for index in indices])
        per_led[indices] = offset + (1 - u if reverse else u) * edge.length_mm
        offset += edge.length_mm
    for star in runtime.stars:
        if not math.isfinite(arrivals[star.id]):
            arrivals[star.id] = offset
        per_led[list(star.indices)] = arrivals[star.id]
    cached = {"runtime": runtime, "source": source, "distance": per_led, "length_mm": offset,
              "order": tuple(edge.id for edge, _reverse in order)}
    state["_drawing"] = cached
    return cached


def _prepare_route(runtime: Runtime, route: Any, state: dict[str, Any]) -> dict[str, Any]:
    implicit = route is None
    cached = state.get("_route")
    if (implicit and isinstance(cached, dict) and cached.get("runtime") is runtime
            and cached.get("implicit")):
        return cached
    if route is None:
        route = default_route(runtime)
    if not isinstance(route, (list, tuple)) or len(route) < 2 or not all(isinstance(s, str) for s in route):
        raise ValueError("route must be a list of at least two star IDs")
    route = tuple(route)
    if (isinstance(cached, dict) and cached.get("runtime") is runtime
            and cached.get("ids") == route and cached.get("implicit") == implicit):
        return cached
    stars = {star.id: star for star in runtime.stars}
    for star_id in route:
        if star_id not in stars:
            raise ValueError(f"route references unknown star {star_id!r}")
    edge_lookup = {}
    for edge in runtime.edges:
        edge_lookup[(edge.start_id, edge.end_id)] = (edge, False)
        edge_lookup[(edge.end_id, edge.start_id)] = (edge, True)
    occurrences: list[tuple[np.ndarray, np.ndarray]] = []
    star_occurrences: list[tuple[np.ndarray, float]] = []
    offset = 0.0
    star_occurrences.append((np.asarray(stars[route[0]].indices, dtype=np.intp), offset))
    for start, end in zip(route, route[1:]):
        if (start, end) not in edge_lookup:
            raise ValueError(f"route stars {start!r} and {end!r} have no connecting edge")
        edge, reverse = edge_lookup[(start, end)]
        if edge.length_mm <= 0:
            raise ValueError(f"route edge {edge.id!r} has nonpositive length")
        indices = np.asarray(edge.indices, dtype=np.intp)
        u = np.asarray([runtime.leds[int(index)].u for index in indices], dtype=float)
        if not np.isfinite(u).all() or np.any((u < 0) | (u > 1)):
            raise ValueError(f"route edge {edge.id!r} has invalid LED progress")
        progress = 1.0 - u if reverse else u
        occurrences.append((indices, offset + progress * edge.length_mm))
        offset += edge.length_mm
        star_occurrences.append((np.asarray(stars[end].indices, dtype=np.intp), offset))
    cached = {
        "runtime": runtime, "ids": route, "implicit": implicit, "length_mm": offset,
        "edges": occurrences, "stars": star_occurrences,
    }
    state["_route"] = cached
    return cached


def _twinkle(prepared: dict[str, Any], seconds: float) -> None:
    work = prepared["work"]
    edge_mask, star_mask = prepared["edges"], prepared["stars"]
    line_level = 0.38 + 0.035 * np.sin(seconds * 0.6)
    work[edge_mask] = np.array((0.38, 0.63, 1.0)) * line_level
    phases, rates = prepared["phases"], prepared["rates"]
    levels = (0.79 + 0.13 * np.sin(seconds * rates + phases)
              + 0.06 * np.sin(seconds * rates * 1.7 + phases * 0.71))
    levels *= prepared["magnitudes"]
    work[star_mask] = levels[prepared["owner_index"][star_mask], None] * np.array((1.0, 0.90, 0.78))


def _flow(runtime: Runtime, prepared: dict[str, Any], seconds: float,
          params: dict[str, Any], state: dict[str, Any]) -> None:
    route = _prepare_route(runtime, params.get("route"), state)
    velocity = _number(params, "flow_velocity_mm_s", 140.0, minimum=0.0, inclusive=False)
    width = _number(params, "flow_width_mm", 35.0, minimum=0.0, inclusive=False)
    length = route["length_mm"]
    head = (seconds * velocity) % length
    work = prepared["work"]
    work[prepared["edges"]] = np.array((0.08, 0.12, 0.22))
    work[prepared["stars"]] = np.array((0.26, 0.20, 0.13))

    def strength(positions: np.ndarray | float) -> np.ndarray:
        # Periodic distance makes the end-to-start restart continuous in time.
        delta = (head - positions + length / 2.0) % length - length / 2.0
        return np.exp(-0.5 * np.square(delta / width))

    for indices, positions in route["edges"]:
        color = strength(positions)[:, None] * np.array((0.26, 0.81, 1.0))
        work[indices] = np.maximum(work[indices], color)
    for indices, position in route["stars"]:
        color = strength(position) * np.array((1.0, 0.79, 0.43))
        work[indices] = np.maximum(work[indices], color)


def _ripple(runtime: Runtime, prepared: dict[str, Any], seconds: float,
            params: dict[str, Any]) -> None:
    visible = prepared["visible"]
    x, y = prepared["x"], prepared["y"]
    center_x = _number(params, "center_x_mm", float(np.mean([s.x_mm for s in runtime.stars])), minimum=-1e9)
    center_y = _number(params, "center_y_mm", float(np.mean([s.y_mm for s in runtime.stars])), minimum=-1e9)
    wavelength = _number(params, "wavelength_mm", 180.0, minimum=0.0, inclusive=False)
    velocity = _number(params, "ripple_velocity_mm_s", 90.0, minimum=0.0, inclusive=False)
    radius = np.hypot(x[visible] - center_x, y[visible] - center_y)
    phase = math.tau * (radius - seconds * velocity) / wavelength
    wave = np.square(0.5 + 0.5 * np.cos(phase))
    channels = np.column_stack((
        0.35 + 0.25 * np.cos(phase + 0.5),
        0.52 + 0.28 * np.cos(phase - 1.5),
        np.ones_like(phase),
    ))
    prepared["work"][visible] = channels * (0.15 + 0.85 * wave[:, None])
    prepared["work"][prepared["stars"]] = np.maximum(
        prepared["work"][prepared["stars"]], np.array((0.32, 0.28, 0.22)))


def _breath(prepared: dict[str, Any], seconds: float, params: dict[str, Any]) -> None:
    defaults = EFFECT_DEFAULTS["breath"]
    period = _number(params, "breath_period_s", defaults["breath_period_s"], minimum=0, inclusive=False)
    floor = _number(params, "breath_floor", defaults["breath_floor"], minimum=0, maximum=1)
    rise = 0.5 - 0.5 * math.cos(math.tau * (seconds % period) / period)
    level = floor + (1 - floor) * rise
    prepared["work"][prepared["edges"]] = np.array((1.0, 0.43, 0.12)) * (0.12 + 0.62 * level)
    star_mask = prepared["stars"]
    star_levels = (0.22 + 0.78 * level) * prepared["magnitudes"][prepared["owner_index"][star_mask]]
    prepared["work"][star_mask] = star_levels[:, None] * np.array((1.0, 0.86, 0.60))


def _aurora(prepared: dict[str, Any], seconds: float, params: dict[str, Any]) -> None:
    defaults = EFFECT_DEFAULTS["aurora"]
    wavelength = _number(params, "aurora_wavelength_mm", defaults["aurora_wavelength_mm"], minimum=0, inclusive=False)
    velocity = _number(params, "aurora_velocity_mm_s", defaults["aurora_velocity_mm_s"], minimum=0, inclusive=False)
    contrast = _number(params, "aurora_contrast", defaults["aurora_contrast"], minimum=0, maximum=1)
    visible = prepared["visible"]
    x, y = prepared["x"][visible], prepared["y"][visible]
    drift = seconds * velocity / wavelength
    curtain = x / wavelength + 0.23 * np.sin(math.tau * y / wavelength + drift * 2.0)
    phase = (curtain - drift + prepared["seed_phase"]) % 1.0
    palette = np.array(((0.08, 0.95, 0.40), (0.08, 0.75, 1.0),
                        (0.68, 0.15, 1.0), (0.14, 0.28, 1.0), (0.08, 0.95, 0.40)))
    scaled = phase * 4
    index = np.floor(scaled).astype(int)
    fraction = (scaled - index)[:, None]
    colors = palette[index] * (1 - fraction) + palette[index + 1] * fraction
    wave = 0.5 + 0.5 * np.sin(math.tau * (y / wavelength * 0.7 + curtain * 0.3) + drift * 3.2)
    level = 0.85 * ((1 - contrast) + contrast * (0.2 + 0.8 * wave))
    prepared["work"][visible] = colors * level[:, None]
    prepared["work"][prepared["stars"]] += np.array((0.23, 0.20, 0.24))


def _sparkle(runtime: Runtime, prepared: dict[str, Any], seconds: float, params: dict[str, Any]) -> None:
    defaults = EFFECT_DEFAULTS["sparkle"]
    period = _number(params, "sparkle_period_s", defaults["sparkle_period_s"], minimum=0, inclusive=False)
    duration = _number(params, "sparkle_duration_s", defaults["sparkle_duration_s"], minimum=0, inclusive=False)
    density = _number(params, "sparkle_density", defaults["sparkle_density"], minimum=0, maximum=1)
    if duration >= period:
        raise ValueError("sparkle_duration_s must be less than sparkle_period_s")
    # Each event lives entirely inside its numbered time slot.  The sin^4
    # envelope is zero at either boundary, so changing the hash is seamless.
    event = int(seconds // period)
    local = seconds % period
    strengths = np.zeros(len(runtime.stars))
    colors = np.zeros((len(runtime.stars), 3))
    for index, star in enumerate(runtime.stars):
        hashed = _mix32(prepared["seed"] ^ int(star.hip) ^ (event * 0x9E3779B9))
        start = _mix32(hashed) / 4294967296.0 * (period - duration)
        phase = (local - start) / duration
        active = hashed / 4294967296.0 < density
        if active and 0 < phase < 1:
            strengths[index] = math.sin(math.pi * phase) ** 4
        warmth = _mix32(hashed ^ 0xA511E9B3) / 4294967296.0
        colors[index] = (0.70 + 0.30 * warmth, 0.88 + 0.12 * warmth, 1.0 - 0.12 * warmth)
    work = prepared["work"]
    work[prepared["edges"]] = np.array((0.15, 0.25, 0.43))
    star_mask = prepared["stars"]
    owners = prepared["owner_index"][star_mask]
    work[star_mask] = np.maximum(np.array((0.30, 0.38, 0.49)), strengths[owners, None] * colors[owners])


def _graph_wave(runtime: Runtime, prepared: dict[str, Any], seconds: float,
                params: dict[str, Any], state: dict[str, Any]) -> None:
    defaults = EFFECT_DEFAULTS["graph_wave"]
    graph = _graph_distances(runtime, _source_star(runtime, params), state)
    velocity = _number(params, "graph_velocity_mm_s", defaults["graph_velocity_mm_s"], minimum=0, inclusive=False)
    width = _number(params, "graph_width_mm", defaults["graph_width_mm"], minimum=0, inclusive=False)
    auto_period = graph["max_mm"] / velocity + 4 * width / velocity + 1.0
    period_params = params if params.get("graph_period_s") is not None else dict(params, graph_period_s=auto_period)
    period = _number(period_params, "graph_period_s", auto_period, minimum=0, inclusive=False)
    finite = graph["finite"]
    arrival = graph["distance"][finite] / velocity
    delta = (seconds % period - arrival + period / 2) % period - period / 2
    strength = np.exp(-0.5 * np.square(delta / (width / velocity)))
    far = graph["distance"][finite] / max(graph["max_mm"], 1.0)
    colors = np.column_stack((0.10 + 0.65 * far, 0.92 - 0.60 * far, np.ones_like(far)))
    work = prepared["work"]
    work[prepared["edges"]] = np.array((0.10, 0.18, 0.30))
    work[prepared["stars"]] = np.array((0.28, 0.25, 0.20))
    work[finite] = np.maximum(work[finite], colors * strength[:, None])
    star_finite = prepared["stars"][finite]
    star_color = strength[star_finite, None] * np.array((1.0, 0.89, 0.68))
    indices = np.flatnonzero(finite)[star_finite]
    work[indices] = np.maximum(work[indices], star_color)


def _draw(runtime: Runtime, prepared: dict[str, Any], seconds: float,
          params: dict[str, Any], state: dict[str, Any]) -> None:
    defaults = EFFECT_DEFAULTS["draw"]
    drawing = _drawing_order(runtime, _source_star(runtime, params), state)
    velocity = _number(params, "draw_velocity_mm_s", defaults["draw_velocity_mm_s"], minimum=0, inclusive=False)
    hold = _number(params, "draw_hold_s", defaults["draw_hold_s"], minimum=0)
    fade = _number(params, "draw_fade_s", defaults["draw_fade_s"], minimum=0, inclusive=False)
    width = _number(params, "draw_head_width_mm", defaults["draw_head_width_mm"], minimum=0, inclusive=False)
    travel = drawing["length_mm"] / velocity
    local = seconds % (travel + hold + fade)
    head = min(local * velocity, drawing["length_mm"] + width)
    opacity = 1.0
    if local > travel + hold:
        opacity = 0.5 + 0.5 * math.cos(math.pi * (local - travel - hold) / fade)
    visible = prepared["visible"]
    progress = drawing["distance"][visible]
    painted = np.clip((head - progress) / runtime.pitch_mm + 0.5, 0, 1) * opacity
    pulse = np.exp(-0.5 * np.square((head - progress) / width)) * opacity
    work = prepared["work"]
    work[prepared["edges"]] = np.array((0.08, 0.12, 0.19))
    work[prepared["stars"]] = np.array((0.18, 0.19, 0.23))
    colors = np.maximum(painted[:, None] * np.array((0.12, 0.65, 0.94)),
                        pulse[:, None] * np.array((0.80, 0.94, 1.0)))
    colors[prepared["stars"][visible]] = np.maximum(
        colors[prepared["stars"][visible]], painted[prepared["stars"][visible], None] * np.array((1.0, 0.86, 0.58)))
    work[visible] = np.maximum(work[visible], colors)


def _meteor(prepared: dict[str, Any], seconds: float, params: dict[str, Any]) -> None:
    defaults = EFFECT_DEFAULTS["meteor"]
    angle = _number(params, "meteor_angle_deg", defaults["meteor_angle_deg"], minimum=-1e9, maximum=1e9)
    velocity = _number(params, "meteor_velocity_mm_s", defaults["meteor_velocity_mm_s"], minimum=0, inclusive=False)
    tail = _number(params, "meteor_tail_mm", defaults["meteor_tail_mm"], minimum=0, inclusive=False)
    width = _number(params, "meteor_width_mm", defaults["meteor_width_mm"], minimum=0, inclusive=False)
    visible = prepared["visible"]
    if not np.any(visible):
        return
    radians = math.radians(angle)
    x, y = prepared["x"][visible], prepared["y"][visible]
    along = x * math.cos(radians) + y * math.sin(radians)
    across = -x * math.sin(radians) + y * math.cos(radians)
    start = float(along.min()) - 20
    travel = (float(along.max()) - start + tail * 3) / velocity
    auto_interval = travel + 0.8
    interval_params = params if params.get("meteor_interval_s") is not None else dict(params, meteor_interval_s=auto_interval)
    interval = _number(interval_params, "meteor_interval_s", auto_interval, minimum=0, inclusive=False)
    if interval < travel:
        raise ValueError(f"meteor_interval_s must be >= its travel time ({travel:.3f} s)")
    event, local = int(seconds // interval), seconds % interval
    hashed = _mix32(prepared["seed"] ^ (event * 0x9E3779B9) ^ 0xB5297A4D)
    track = float(across.min()) + (0.25 + 0.5 * hashed / 4294967296.0) * float(np.ptp(across))
    head = start + local * velocity
    delta = head - along
    longitudinal = np.exp(-np.maximum(delta, 0) / tail) * np.exp(-0.5 * np.square(np.minimum(delta, 0) / 11))
    cross_strength = np.exp(-0.5 * np.square((across - track) / width))
    envelope = max(0.0, min(1.0, local / 0.15, (travel - local) / 0.6))
    intensity = longitudinal * cross_strength * envelope
    warmth = np.exp(-np.maximum(delta, 0) / 28)
    colors = np.column_stack((0.13 + 0.87 * warmth, 0.35 + 0.56 * warmth, np.ones_like(warmth)))
    work = prepared["work"]
    work[prepared["edges"]] = np.array((0.13, 0.15, 0.28))
    work[prepared["stars"]] = np.array((0.28, 0.25, 0.40))
    work[visible] = np.maximum(work[visible], colors * intensity[:, None])


def render(runtime: Runtime, time_ms: float, params: dict[str, Any],
           state: dict[str, Any], frame: np.ndarray) -> np.ndarray:
    """Write one uint8 RGB frame in place and return that same array.

    State only caches geometry and derived parameters; calling frames out of
    order produces the same values as sequential playback.
    """
    if not isinstance(params, dict) or not isinstance(state, dict):
        raise ValueError("params and state must be dictionaries")
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.shape != (runtime.led_count, 3):
        raise ValueError(f"frame must be a uint8 array with shape ({runtime.led_count}, 3)")
    if not frame.flags.writeable:
        raise ValueError("frame must be writable")
    time_ms = _number({"time_ms": time_ms}, "time_ms", 0, minimum=0)
    brightness = _number(params, "brightness", 0.2, minimum=0, maximum=1)
    speed = _number(params, "speed", 1.0, minimum=0, inclusive=False)
    gamma = _number(params, "gamma", 2.2, minimum=0, inclusive=False)
    seed = params.get("seed", 1)
    if isinstance(seed, bool) or not isinstance(seed, Integral) or not 0 <= int(seed) <= 0xFFFFFFFF:
        raise ValueError("seed must be an integer between 0 and 4294967295")
    effect = params.get("effect", "twinkle")
    if effect not in EFFECT_NAMES:
        raise ValueError(f"unknown effect {effect!r}; choose from {', '.join(EFFECT_NAMES)}")
    prepared = _prepared(runtime, int(seed), state)
    prepared["work"].fill(0)
    seconds = time_ms / 1000.0 * speed
    if not math.isfinite(seconds):
        raise ValueError("time_ms * speed exceeds the supported time range")
    if effect == "twinkle":
        _twinkle(prepared, seconds)
    elif effect == "flow":
        _flow(runtime, prepared, seconds, params, state)
    elif effect == "ripple":
        _ripple(runtime, prepared, seconds, params)
    elif effect == "breath":
        _breath(prepared, seconds, params)
    elif effect == "aurora":
        _aurora(prepared, seconds, params)
    elif effect == "sparkle":
        _sparkle(runtime, prepared, seconds, params)
    elif effect == "graph_wave":
        _graph_wave(runtime, prepared, seconds, params, state)
    elif effect == "draw":
        _draw(runtime, prepared, seconds, params, state)
    else:
        _meteor(prepared, seconds, params)
    np.clip(prepared["work"], 0, 1, out=prepared["work"])
    np.power(prepared["work"], gamma, out=prepared["work"])
    frame[:] = np.rint(prepared["work"] * (255.0 * brightness)).astype(np.uint8)
    return frame
