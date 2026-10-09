"""Export authoritative offline effect parameters without NumPy or hardware."""

from __future__ import annotations

import hashlib
import heapq
import math
from pathlib import Path

from .compact import pack_runtime
from .effectspec import EFFECT_DEFAULTS, EFFECT_NAMES, default_route
from .model import ValidationError, read_json


COMMON_DEFAULTS = {"seed": 1, "brightness": 0.2, "speed": 1.0, "gamma": 2.2}
_NUMERIC_DEFAULTS = {key: value for values in EFFECT_DEFAULTS.values()
                     for key, value in values.items() if key != "source_star"}
_EXTRA_KEYS = {"route", "source_star", "center_x_mm", "center_y_mm"}
_UNIT_FIELDS = {"brightness", "breath_floor", "aurora_contrast", "sparkle_density"}
_ZERO_FIELDS = {"draw_hold_s"}
_OPTIONAL_PERIODS = {"graph_period_s", "meteor_interval_s"}
_ENUM_NAMES = ("Twinkle", "Flow", "Ripple", "Breath", "Aurora", "Sparkle", "GraphWave", "Draw", "Meteor")


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f"{name} must be a finite number")
    return float(value)


def _validate_params(params, effect):
    allowed = set(COMMON_DEFAULTS) | set(_NUMERIC_DEFAULTS) | _EXTRA_KEYS
    extra = set(params) - allowed
    if extra:
        raise ValidationError(f"{effect}: unsupported native preset parameters {sorted(extra)!r}")
    seed = params.get("seed", 1)
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise ValidationError(f"{effect}: seed must be a uint32 integer")
    result = {"seed": seed}
    for name, value in params.items():
        if name in _EXTRA_KEYS or name == "seed":
            continue
        if name in _OPTIONAL_PERIODS and value is None:
            result[name] = None
            continue
        value = _number(value, name)
        if name in _UNIT_FIELDS:
            if not 0 <= value <= 1:
                raise ValidationError(f"{name} must be 0..1")
        elif name in _ZERO_FIELDS:
            if value < 0:
                raise ValidationError(f"{name} must be nonnegative")
        elif name == "meteor_angle_deg":
            if not -1e9 <= value <= 1e9:
                raise ValidationError("meteor_angle_deg must be -1e9..1e9")
        elif value <= 0:
            raise ValidationError(f"{name} must be positive")
        result[name] = value
    for name in ("center_x_mm", "center_y_mm"):
        if name in params:
            value = _number(params[name], name)
            if value < -1e9:
                raise ValidationError(f"{name} must be >= -1e9")
            result[name] = value
    result["source_star"] = params.get("source_star")
    result["route"] = params.get("route")
    return result


def _source(runtime, value):
    lookup = {star.id: index for index, star in enumerate(runtime.stars)}
    if value is None:
        value = min(runtime.stars, key=lambda row: (math.inf if row.mag_v is None else row.mag_v, row.hip)).id
    if not isinstance(value, str) or value not in lookup:
        raise ValidationError(f"source_star references unknown star {value!r}")
    if lookup[value] > 32767:
        raise ValidationError("source_star index exceeds native int16 capacity")
    return lookup[value], value


def _route(runtime, value):
    route = default_route(runtime) if value is None else value
    if (not isinstance(route, (list, tuple)) or not 2 <= len(route) <= 2 * len(runtime.stars)
            or not all(isinstance(star_id, str) for star_id in route)):
        raise ValidationError(f"route must contain 2..{2 * len(runtime.stars)} connected star IDs")
    lookup = {star.id: index for index, star in enumerate(runtime.stars)}
    for star_id in route:
        if star_id not in lookup:
            raise ValidationError(f"route references unknown star {star_id!r}")
    edges = {frozenset((edge.start_id, edge.end_id)): edge for edge in runtime.edges}
    length = 0.0
    for start, end in zip(route, route[1:]):
        edge = edges.get(frozenset((start, end)))
        if edge is None or start == end:
            raise ValidationError(f"route stars {start!r} and {end!r} have no connecting edge")
        if edge.length_mm <= 0:
            raise ValidationError("route edge must have positive length")
        length += edge.length_mm
    return [lookup[star_id] for star_id in route], list(route), length


def _graph_max(runtime, source):
    adjacency = {star.id: [] for star in runtime.stars}
    for edge in runtime.edges:
        adjacency[edge.start_id].append((edge.end_id, edge.length_mm))
        adjacency[edge.end_id].append((edge.start_id, edge.length_mm))
    distances = {star_id: math.inf for star_id in adjacency}
    distances[source] = 0.0
    queue = [(0.0, source)]
    while queue:
        distance, star_id = heapq.heappop(queue)
        if distance > distances[star_id]:
            continue
        for neighbor, length in sorted(adjacency[star_id]):
            candidate = distance + length
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    maximum = 0.0
    for led in runtime.leds:
        if led.owner_type == "star":
            distance = distances[runtime.stars[led.owner_index].id]
        elif led.owner_type == "edge":
            edge = runtime.edges[led.owner_index]
            distance = min(distances[edge.start_id] + led.u * edge.length_mm,
                           distances[edge.end_id] + (1 - led.u) * edge.length_mm)
        else:
            continue
        if math.isfinite(distance):
            maximum = max(maximum, distance)
    return maximum


def build_native_presets(runtime, effects_path):
    """Return (C++ header, JSON metadata) for all nine configured presets.

    Automatic cycles are computed from the full-precision authored scene and
    serialized with round-trip double precision, preventing accumulated phase
    drift caused by the MCU's 0.1 mm position/length quantization.
    """
    effects_path = Path(effects_path)
    raw = read_json(effects_path)
    defaults, presets = raw.get("defaults", {}), raw.get("presets", {})
    if not isinstance(defaults, dict) or not isinstance(presets, dict):
        raise ValidationError("Effect config defaults/presets must be objects")
    if set(presets) - set(EFFECT_NAMES):
        raise ValidationError("Effect config contains an unknown effect ID")
    if not runtime.stars:
        raise ValidationError("Native presets require at least one star")
    scene_sha256 = pack_runtime(runtime)["metadata"]["scene_sha256"]
    base = {**COMMON_DEFAULTS, **_NUMERIC_DEFAULTS}
    center = (sum(star.x_mm for star in runtime.stars) / len(runtime.stars),
              sum(star.y_mm for star in runtime.stars) / len(runtime.stars))
    output, metadata = [], {}
    for index, effect in enumerate(EFFECT_NAMES):
        preset = presets.get(effect, {})
        if not isinstance(preset, dict):
            raise ValidationError(f"Effect preset {effect} must be an object")
        params = _validate_params({**base, **defaults, **preset}, effect)
        source_index, source_id = _source(runtime, params["source_star"])
        route_indices, route_ids, route_length = _route(runtime, params["route"])
        if params["sparkle_duration_s"] >= params["sparkle_period_s"]:
            raise ValidationError("sparkle_duration_s must be less than sparkle_period_s")
        fields = {name: value for name, value in params.items() if name not in _EXTRA_KEYS}
        fields["source_star"] = source_index
        fields["pitch_mm"] = runtime.pitch_mm
        fields["custom_center"] = True  # Authoritative full-precision mean, or custom axes.
        fields["center_x_mm"] = params.get("center_x_mm", center[0])
        fields["center_y_mm"] = params.get("center_y_mm", center[1])
        fields["flow_period_s"] = route_length / params["flow_velocity_mm_s"]
        draw_length = sum(edge.length_mm for edge in runtime.edges)
        fields["draw_period_s"] = draw_length / params["draw_velocity_mm_s"] + params["draw_hold_s"] + params["draw_fade_s"]
        graph_max = _graph_max(runtime, source_id)
        if fields["graph_period_s"] is None:
            fields["graph_period_s"] = (graph_max / params["graph_velocity_mm_s"]
                                        + 4 * params["graph_width_mm"] / params["graph_velocity_mm_s"] + 1)
        angle = math.radians(params["meteor_angle_deg"])
        projection = [led.x_mm * math.cos(angle) + led.y_mm * math.sin(angle)
                      for led in runtime.leds if led.owner_type in ("star", "edge")]
        travel = ((max(projection) - min(projection) + 20 + 3 * params["meteor_tail_mm"])
                  / params["meteor_velocity_mm_s"])
        if fields["meteor_interval_s"] is None:
            fields["meteor_interval_s"] = travel + .8
        if fields["meteor_interval_s"] < travel:
            raise ValidationError(f"meteor_interval_s must be >= its travel time ({travel:.3f} s)")
        for name, value in fields.items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValidationError(f"Derived {name} is not finite")
        output.append(f"    case {index}u: {{ // {effect}\n        params.effect = Effect::{_ENUM_NAMES[index]};")
        for name, value in fields.items():
            if isinstance(value, bool):
                literal = "true" if value else "false"
            elif isinstance(value, int):
                literal = str(value) + ("u" if name == "seed" else "")
            else:
                literal = format(value, ".17g")
            output.append(f"        params.{name} = {literal};")
        # Explicit routes also prevent graph-diameter changes from quantized lengths.
        output.append(f"        params.route_count = {len(route_indices)}u;")
        output.extend(f"        params.route[{offset}] = {star_index}u;"
                      for offset, star_index in enumerate(route_indices))
        output.append("        break;\n    }")
        metadata[effect] = {"index": index, "params": fields, "route_indices": route_indices,
                            "route_star_ids": route_ids, "route_length_mm": route_length,
                            "route_was_automatic": params["route"] is None,
                            "source_was_automatic": params["source_star"] is None,
                            "source_star_id": source_id, "graph_max_mm": graph_max,
                            "draw_length_mm": draw_length, "meteor_travel_s": travel}
    header = ("/* Generated from full-precision scene and data/effects.json. */\n"
              "#ifndef CONSTELLATION_LAMP_GENERATED_NATIVE_PRESETS_H\n"
              "#define CONSTELLATION_LAMP_GENERATED_NATIVE_PRESETS_H\n"
              '#include "native_effects.h"\n\nnamespace clp {\n'
              "inline NativeParams generatedNativeParams(unsigned effect_index) {\n"
              "    NativeParams params;\n    switch (effect_index) {\n"
              + "\n".join(output)
              + "\n    default: return generatedNativeParams(0u);\n    }\n    return params;\n}\n"
              "} // namespace clp\n#endif\n")
    return header, {"schema_version": 1, "scene_sha256": scene_sha256,
                    "effects_source": str(effects_path.resolve()),
                    "effects_sha256": hashlib.sha256(effects_path.read_bytes()).hexdigest(),
                    "header_sha256": hashlib.sha256(header.encode("utf-8")).hexdigest(),
                    "period_source": "full_precision_authoring_scene",
                    "presets": metadata}
