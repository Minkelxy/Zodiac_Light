#!/usr/bin/env python3
"""Offline endpoint setback optimizer for the 8-star Sagittarius geometry.

Import optimize_slots(stars, slots, web=1.03) from other Python code. Running
this module writes only electrical/star-slot-optimization.json. It has no EDA
connection and does not edit build_mechanical.py or existing geometry files.
Requires Shapely 2.x; no SciPy dependency.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
HARDWARE = HERE.parent
ROOT = HARDWARE.parents[1]
MECHANICAL = HERE / "build_mechanical.py"
SOURCE = ROOT / "data" / "constellation.json"
OUTPUT = HARDWARE / "electrical" / "star-slot-optimization.json"
STAR_RADIUS = 0.4
SLOT_RADIUS = 0.5
TARGET_WEB = 1.03
SIMPLIFY_TOLERANCE = 0.003
NATIVE_GRID = 0.00254  # 0.1 mil; coordinates are then rounded to 4 decimals in mm.


def _capsule(a, b):
    return LineString([a, b]).buffer(SLOT_RADIUS, quad_segs=32)


def _polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [part for part in geometry.geoms if part.geom_type == "Polygon"]


def _native_point(point):
    return tuple(round(round(float(value) / NATIVE_GRID) * NATIVE_GRID, 4)
                 for value in point)


def _measure(positions, edges, setbacks, board, web):
    capsules = []
    for edge in edges:
        a, b = positions[edge["start"]], positions[edge["end"]]
        length = math.dist(a, b)
        unit = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        sa, sb = setbacks[(edge["id"], "start")], setbacks[(edge["id"], "end")]
        if sa + sb >= length:
            raise ValueError(f"Endpoint setbacks consume slot {edge['id']}")
        p = (a[0] + unit[0] * sa, a[1] + unit[1] * sa)
        q = (b[0] - unit[0] * sb, b[1] - unit[1] * sb)
        if math.dist(p, q) <= 0:
            raise ValueError(f"Collapsed slot {edge['id']}")
        shape = _capsule(p, q)
        capsules.append({"id": edge["id"], "start": edge["start"], "end": edge["end"],
                         "endpoint_a": p, "endpoint_b": q, "shape": shape,
                         "centerline_length_mm": math.dist(p, q),
                         "overall_length_mm": math.dist(p, q) + 1.0})

    holes = {key: Point(pos).buffer(STAR_RADIUS, quad_segs=32)
             for key, pos in positions.items()}
    hole_slot = [(hole.distance(slot["shape"]), star_id, slot["id"])
                 for star_id, hole in holes.items() for slot in capsules]
    slot_slot = [(a["shape"].distance(b["shape"]), a["id"], b["id"])
                 for a, b in itertools.combinations(capsules, 2)]
    min_hole_slot, min_slot_slot = min(hole_slot), min(slot_slot)

    native_holes = {key: Point(_native_point(pos)).buffer(STAR_RADIUS, quad_segs=32)
                    for key, pos in positions.items()}
    native_capsules = []
    for slot in capsules:
        p, q = _native_point(slot["endpoint_a"]), _native_point(slot["endpoint_b"])
        native_capsules.append({**slot, "shape": _capsule(p, q).simplify(
            SIMPLIFY_TOLERANCE, preserve_topology=True)})
    native_holes = {key: shape.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
                    for key, shape in native_holes.items()}
    native_hole_slot = min((hole.distance(slot["shape"]), sid, slot["id"])
                           for sid, hole in native_holes.items() for slot in native_capsules)
    native_slot_slot = min((a["shape"].distance(b["shape"]), a["id"], b["id"])
                           for a, b in itertools.combinations(native_capsules, 2))
    slot_union = unary_union([slot["shape"] for slot in capsules])
    void_union = unary_union([*holes.values(), *(slot["shape"] for slot in capsules)])
    components = len(_polygons(board.difference(void_union)))
    count = len(_polygons(slot_union))
    valid = all(slot["shape"].is_valid for slot in capsules)
    min_web = min(min_hole_slot[0], min_slot_slot[0])
    native_web = min(native_hole_slot[0], native_slot_slot[0])
    feasible = (min_web >= web - 1e-8 and native_web >= 1.0 - 1e-8
                and count == 11 and components == 1 and valid)
    return {"slots": capsules, "min_hole_slot": min_hole_slot,
            "min_slot_slot": min_slot_slot, "min_web": min_web,
            "native_hole_slot": native_hole_slot,
            "native_slot_slot": native_slot_slot, "native_web": native_web,
            "slot_count": count, "material_components": components,
            "all_valid": valid, "feasible": feasible}


def optimize_slots(stars, slots, web=1.03):
    """Return optimized copies of slots plus a Shapely validation report.

    The input records use build_mechanical.local_constellation's in-memory
    format. Inputs are not mutated. Per-edge setback values are independent.
    """
    min_setback = STAR_RADIUS + SLOT_RADIUS + float(web)
    positions = {star["id"]: tuple(star["center"]) for star in stars}
    edges = [{"id": slot["id"], "start": slot["start"], "end": slot["end"]}
             for slot in slots]
    octagon_half = 37 / 2
    bevel = octagon_half * math.tan(math.pi / 8)
    board = Polygon([(-bevel, -octagon_half), (bevel, -octagon_half),
                     (octagon_half, -bevel), (octagon_half, bevel),
                     (bevel, octagon_half), (-bevel, octagon_half),
                     (-octagon_half, bevel), (-octagon_half, -bevel)])
    initial = {}
    for slot in slots:
        initial[(slot["id"], "start")] = math.dist(positions[slot["start"]], slot["endpoint_a"])
        initial[(slot["id"], "end")] = math.dist(positions[slot["end"]], slot["endpoint_b"])
    before = _measure(positions, edges, initial, board, web)

    neighbors = {key: [] for key in positions}
    for edge in edges:
        neighbors[edge["start"]].append(edge["end"])
        neighbors[edge["end"]].append(edge["start"])
    original_star_setback = {star["id"]: float(star.get("endpoint_setback_mm", 0)) for star in stars}
    star_setback = {}
    for sid, adjacent in neighbors.items():
        origin = positions[sid]
        angles = []
        for n1, n2 in itertools.combinations(adjacent, 2):
            u = (positions[n1][0] - origin[0], positions[n1][1] - origin[1])
            v = (positions[n2][0] - origin[0], positions[n2][1] - origin[1])
            cosine = sum(u[i] * v[i] for i in (0, 1)) / (math.hypot(*u) * math.hypot(*v))
            angles.append(math.acos(max(-1.0, min(1.0, cosine))))
        local_safe = max(((2 * SLOT_RADIUS + web) / (2 * math.sin(theta / 2))
                          for theta in angles), default=0.0)
        star_setback[sid] = max(min_setback, local_safe, original_star_setback.get(sid, 0.0))
    setbacks = {(slot["id"], side): star_setback[slot["start" if side == "start" else "end"]]
                for slot in slots for side in ("start", "end")}
    if not _measure(positions, edges, setbacks, board, web)["feasible"]:
        raise RuntimeError("The requested web has no feasible seed for these slots")

    original_lengths = {slot["id"]: float(slot["centerline_length_mm"]) for slot in slots}
    endpoint_order = [(slot["centerline_length_mm"], slot["id"], side)
                      for slot in slots for side in ("start", "end")]
    passes = 0
    while passes < 40:
        passes += 1
        changed = False
        current = _measure(positions, edges, setbacks, board, web)
        lengths = {slot["id"]: slot["centerline_length_mm"] for slot in current["slots"]}
        for _, edge_id, side in sorted(endpoint_order,
                                       key=lambda x: (lengths[x[1]], x[1], x[2])):
            key = (edge_id, side)
            old = setbacks[key]
            if old <= min_setback + 1e-8:
                continue
            low, high = min_setback, old
            trial = dict(setbacks)
            trial[key] = low
            if _measure(positions, edges, trial, board, web)["feasible"]:
                setbacks[key] = low
                changed = True
                continue
            for _ in range(34):
                middle = (low + high) / 2
                trial[key] = middle
                if _measure(positions, edges, trial, board, web)["feasible"]:
                    high = middle
                else:
                    low = middle
            reduced = min(old, high + 0.0002)
            if reduced < old - 1e-7:
                setbacks[key] = reduced
                changed = True
        if not changed:
            break

    after = _measure(positions, edges, setbacks, board, web)
    if not after["feasible"]:
        raise RuntimeError("Optimizer result failed the geometry checks")
    after_by_id = {slot["id"]: slot for slot in after["slots"]}
    optimized = []
    for original in slots:
        measured = after_by_id[original["id"]]
        optimized.append({**original, "endpoint_a": measured["endpoint_a"],
                          "endpoint_b": measured["endpoint_b"], "shape": measured["shape"],
                          "centerline_length_mm": measured["centerline_length_mm"],
                          "overall_length_mm": measured["overall_length_mm"],
                          "start_setback_mm": setbacks[(original["id"], "start")],
                          "end_setback_mm": setbacks[(original["id"], "end")]})
    report = {
        "algorithm": "deterministic shortest-slot-first coordinate descent with binary search",
        "target_nominal_web_mm": web,
        "minimum_endpoint_setback_mm": min_setback,
        "native_coordinate_grid_mm": NATIVE_GRID,
        "native_coordinate_decimal_places": 4,
        "post_rounding_simplification_tolerance_mm": SIMPLIFY_TOLERANCE,
        "passes": passes,
        "before": {"minimum_actual_web_mm": before["min_web"],
                   "minimum_centerline_length_mm": min(original_lengths.values()),
                   "minimum_overall_length_mm": min(original_lengths.values()) + 1,
                   "total_centerline_length_mm": sum(original_lengths.values()),
                   "all_11_slots_closed_and_isolated": before["slot_count"] == 11,
                   "remaining_board_material_connected": before["material_components"] == 1},
        "after": {"minimum_actual_web_mm": after["min_web"],
                  "minimum_hole_slot_web_mm": after["min_hole_slot"][0],
                  "minimum_slot_slot_web_mm": after["min_slot_slot"][0],
                  "minimum_web_pair": (list(after["min_hole_slot"][1:])
                                       if after["min_hole_slot"][0] <= after["min_slot_slot"][0]
                                       else list(after["min_slot_slot"][1:])),
                  "native_simplified_minimum_web_mm": after["native_web"],
                  "native_simplified_minimum_hole_slot_web_mm": after["native_hole_slot"][0],
                  "native_simplified_minimum_slot_slot_web_mm": after["native_slot_slot"][0],
                  "minimum_centerline_length_mm": min(slot["centerline_length_mm"] for slot in optimized),
                  "minimum_overall_length_mm": min(slot["overall_length_mm"] for slot in optimized),
                  "total_centerline_length_mm": sum(slot["centerline_length_mm"] for slot in optimized),
                  "all_11_slots_closed_and_isolated": after["slot_count"] == 11,
                  "remaining_board_material_connected": after["material_components"] == 1,
                  "all_slot_polygons_valid": after["all_valid"],
                  "slot_count": after["slot_count"],
                  "remaining_material_components": after["material_components"],
                  "constraints_pass": after["feasible"]},
    }
    return optimized, report


def _build_candidate():
    spec = importlib.util.spec_from_file_location("star_slot_mechanical", MECHANICAL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load geometry source: {MECHANICAL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    stars, slots, scale = module.local_constellation(source, optimize=False)
    optimized, report = optimize_slots(stars, slots, web=TARGET_WEB)
    baseline = {slot["id"]: slot for slot in slots}
    output_slots = []
    for slot in optimized:
        original = baseline[slot["id"]]
        output_slots.append({
            "id": slot["id"], "start": slot["start"], "end": slot["end"],
            "endpoint_a_mm": [round(v, 6) for v in slot["endpoint_a"]],
            "endpoint_b_mm": [round(v, 6) for v in slot["endpoint_b"]],
            "start_setback_mm": round(slot["start_setback_mm"], 6),
            "end_setback_mm": round(slot["end_setback_mm"], 6),
            "centerline_length_before_mm": round(original["centerline_length_mm"], 6),
            "centerline_length_after_mm": round(slot["centerline_length_mm"], 6),
            "overall_length_before_mm": round(original["overall_length_mm"], 6),
            "overall_length_after_mm": round(slot["overall_length_mm"], 6),
        })
    return {"status": "offline_geometry_candidate",
            "source": {"script": "scripts/build_mechanical.py:local_constellation",
                       "constellation": "data/constellation.json",
                       "scale_mm_per_reference_px": scale},
            "method": {key: report[key] for key in (
                "algorithm", "target_nominal_web_mm", "minimum_endpoint_setback_mm",
                "native_coordinate_grid_mm", "native_coordinate_decimal_places",
                "post_rounding_simplification_tolerance_mm", "passes")},
            "before": report["before"],
            "after": {**report["after"],
                      "total_centerline_length_before_mm": report["before"]["total_centerline_length_mm"],
                      "slots": output_slots},
            "scope": "offline candidate only; no live EDA connection or existing geometry writes"}


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(_build_candidate(), ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print(OUTPUT)
