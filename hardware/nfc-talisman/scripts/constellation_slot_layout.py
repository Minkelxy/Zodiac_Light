"""Offline, deterministic constellation slot planning; no EasyEDA operations.

Keep every HIP node and logical edge. Maximize physical edge coverage by fitting
straight 1 mm capsules to legal portions of those edges, with rounded cutter
ends, bounded uniform chart enlargement and explicit material-web checks.
Dense links retain their complete ordinary-silkscreen relationship.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Hashable, Mapping, Sequence

from shapely import affinity
from shapely.geometry import GeometryCollection, LineString, Point, Polygon
from shapely.ops import unary_union


@dataclass(frozen=True)
class SlotPolicy:
    slot_width_mm: float = 1.0
    star_hole_diameter_mm: float = .8
    star_to_slot_web_mm: float = 1.0
    slot_to_slot_web_mm: float = .8
    slot_to_board_web_mm: float = 1.0
    minimum_slot_overall_mm: float = 1.5
    numerical_guard_mm: float = .005
    max_uniform_scale: float = 1.10
    chart_center_mm: tuple[float, float] = (18.5, 18.8)
    star_center_y_limits_mm: tuple[float, float] = (7.2, 30.4)
    scale_steps: int = 4
    random_order_trials: int = 8
    maximum_fragments_per_edge: int = 2

    def __post_init__(self):
        for value in (self.slot_width_mm, self.star_hole_diameter_mm,
                      self.star_to_slot_web_mm, self.slot_to_slot_web_mm,
                      self.slot_to_board_web_mm, self.minimum_slot_overall_mm):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Slot dimensions and material webs must be positive")
        if self.minimum_slot_overall_mm <= self.slot_width_mm:
            raise ValueError("A routed slot needs a nonzero centerline")
        if not 1 <= self.max_uniform_scale <= 1.10:
            raise ValueError("Uniform enlargement must stay within 10 percent")


@dataclass
class SlotLayout:
    positions: dict[Hashable, tuple[float, float]]
    slots: list[Polygon]
    slot_records: list[dict[str, Any]]
    metadata: dict[str, Any]


def af37_board() -> Polygon:
    half = 18.5
    bevel = half * (math.sqrt(2) - 1)
    return Polygon([(18.5 + x, 18.5 + y) for x, y in
                    [(-bevel, -half), (bevel, -half), (half, -bevel), (half, bevel),
                     (bevel, half), (-bevel, half), (-half, bevel), (-half, -bevel)]])


def _edges(edges: Sequence[Sequence[Hashable]]) -> list[tuple[Hashable, Hashable]]:
    return sorted({tuple(sorted((a, b))) for a, b in edges if a != b})


def _line_parts(geometry) -> list[LineString]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    return [line for item in getattr(geometry, "geoms", []) for line in _line_parts(item)]


def _holes(positions, policy):
    return {hip: Point(xy).buffer(policy.star_hole_diameter_mm / 2, quad_segs=32)
            for hip, xy in positions.items()}


def _measure(positions, edges, slots, records, board, policy) -> dict[str, Any]:
    holes = list(_holes(positions, policy).values())
    apertures = unary_union([*holes, *slots])
    material = board.difference(apertures)
    routed = {tuple(item["edge"]) for item in records}
    centerline = sum(item["centerline_length_mm"] for item in records)
    overall = sum(item["overall_length_mm"] for item in records)
    logical_length = sum(math.dist(positions[a], positions[b]) for a, b in edges)
    star_gap = min((slot.distance(hole) for slot in slots for hole in holes), default=None)
    slot_gap = min((first.distance(second) for i, first in enumerate(slots) for second in slots[i + 1:]), default=None)
    board_gap = min((slot.distance(board.boundary) for slot in slots), default=None)
    return {"hip_count": len(positions), "logical_edge_count": len(edges),
            "slotted_edge_count": len(routed), "physical_slot_count": len(slots),
            "printed_only_edge_count": len(edges) - len(routed),
            "printed_only_edges": [list(edge) for edge in edges if edge not in routed],
            "total_logical_edge_length_mm": logical_length,
            "total_centerline_length_mm": centerline, "total_slot_overall_length_mm": overall,
            "logical_edge_coverage_fraction": len(routed) / len(edges) if edges else 1.0,
            "physical_line_coverage_fraction": overall / logical_length if logical_length else 0.0,
            "minimum_star_to_slot_material_mm": star_gap,
            "minimum_slot_to_slot_material_mm": slot_gap,
            "minimum_slot_to_outer_edge_material_mm": board_gap,
            "minimum_all_apertures_to_outer_edge_mm": apertures.distance(board.boundary),
            "minimum_star_to_star_material_mm": min((a.distance(b) for i, a in enumerate(holes) for b in holes[i + 1:]), default=None),
            "fr4_single_connected_component": material.is_valid and material.geom_type == "Polygon",
            "all_apertures_inside_board": board.covers(apertures),
            "slot_width_mm": policy.slot_width_mm,
            "minimum_slot_overall_length_mm": min((r["overall_length_mm"] for r in records), default=None)}


def legacy_layout(positions: Mapping[Hashable, Sequence[float]], edges: Sequence[Sequence[Hashable]],
                  *, board: Polygon | None = None) -> SlotLayout:
    """Exact prior star_cover selection policy, for an honest comparison."""
    positions = {hip: tuple(map(float, xy)) for hip, xy in positions.items()}
    edges = _edges(edges)
    slots, records = [], []
    for a, b in edges:
        distance = math.dist(positions[a], positions[b])
        if distance < 5.1:
            continue
        unit = tuple((positions[b][i] - positions[a][i]) / distance for i in (0, 1))
        start = tuple(positions[a][i] + unit[i] * 1.9 for i in (0, 1))
        end = tuple(positions[b][i] - unit[i] * 1.9 for i in (0, 1))
        slot = LineString([start, end]).buffer(.5, quad_segs=16)
        others = unary_union([Point(xy).buffer(.9) for hip, xy in positions.items() if hip not in (a, b)])
        if slot.intersects(others) or any(slot.distance(old) < .8 for old in slots):
            continue
        slots.append(slot)
        records.append({"edge": [a, b], "start_mm": start, "end_mm": end,
                        "centerline_length_mm": distance - 3.8, "overall_length_mm": distance - 2.8})
    metrics = _measure(positions, edges, slots, records, board or af37_board(), SlotPolicy())
    return SlotLayout(positions, slots, records, {"strategy": "legacy_fixed_5.1mm_threshold", **metrics})


def _base_parts(positions, edges, board, policy):
    half = policy.slot_width_mm / 2
    radius = policy.star_hole_diameter_mm / 2
    setback = radius + half + policy.star_to_slot_web_mm + policy.numerical_guard_mm
    permitted = board.buffer(-(half + policy.slot_to_board_web_mm + policy.numerical_guard_mm))
    minimum = policy.minimum_slot_overall_mm - policy.slot_width_mm
    result = {}
    for a, b in edges:
        distance = math.dist(positions[a], positions[b])
        if distance < 2 * setback + minimum:
            result[(a, b)] = []
            continue
        u = [(positions[b][i] - positions[a][i]) / distance for i in (0, 1)]
        start = [positions[a][i] + u[i] * setback for i in (0, 1)]
        end = [positions[b][i] - u[i] * setback for i in (0, 1)]
        line = LineString([start, end]).intersection(permitted)
        obstacles = unary_union([Point(xy).buffer(setback, quad_segs=32)
                                 for hip, xy in positions.items() if hip not in (a, b)])
        result[(a, b)] = [part for part in _line_parts(line.difference(obstacles))
                          if part.length >= minimum - 1e-9]
    return result


def _trial(positions, edges, board, policy, base, order):
    slots, records = [], []
    forbidden = GeometryCollection()
    holes = _holes(positions, policy)
    minimum = policy.minimum_slot_overall_mm - policy.slot_width_mm
    exclusion = policy.slot_width_mm / 2 + policy.slot_to_slot_web_mm + policy.numerical_guard_mm
    for edge in order:
        parts = [part for line in base[edge] for part in _line_parts(line.difference(forbidden)) if part.length >= minimum - 1e-9]
        parts.sort(key=lambda p: (-p.length, p.bounds))
        used = 0
        for part in parts:
            if used >= policy.maximum_fragments_per_edge:
                break
            slot = part.buffer(policy.slot_width_mm / 2, quad_segs=32)
            if any(slot.distance(hole) < policy.star_to_slot_web_mm - 1e-7 for hole in holes.values()):
                continue
            if any(slot.distance(other) < policy.slot_to_slot_web_mm - 1e-7 for other in slots):
                continue
            if slot.distance(board.boundary) < policy.slot_to_board_web_mm - 1e-7:
                continue
            slots.append(slot)
            records.append({"edge": list(edge), "start_mm": list(part.coords[0]), "end_mm": list(part.coords[-1]),
                            "centerline_length_mm": part.length,
                            "overall_length_mm": part.length + policy.slot_width_mm})
            forbidden = forbidden.union(slot.buffer(exclusion, quad_segs=24))
            used += 1
    return SlotLayout(positions, slots, records, _measure(positions, edges, slots, records, board, policy))


def _orders(edges, base, positions, count):
    length = {edge: sum(part.length for part in base[edge]) for edge in edges}
    degrees = {hip: sum(hip in edge for edge in edges) for hip in positions}
    orders = [edges, sorted(edges, key=lambda e: (-length[e], e)),
              sorted(edges, key=lambda e: (length[e] == 0, length[e], e)),
              sorted(edges, key=lambda e: (-(degrees[e[0]] + degrees[e[1]]), -length[e], e))]
    rng = random.Random(370110)
    for _ in range(count):
        candidate = list(edges)
        rng.shuffle(candidate)
        orders.append(candidate)
    return orders


def optimize_slot_layout(positions: Mapping[Hashable, Sequence[float]], edges: Sequence[Sequence[Hashable]],
                         *, board: Polygon | None = None, policy: SlotPolicy | None = None,
                         allow_uniform_scale: bool = True) -> SlotLayout:
    """Return final star positions, 1mm slot polygons, and JSON-safe evidence.

    Call this before creating HIP holes or printed edges. Use returned positions
    for both; the only layout movement is a common scale about chart_center_mm.
    No individual node adjustment or new logical connection is introduced.
    """
    policy = policy or SlotPolicy()
    board = board if board is not None else af37_board()
    original = {hip: tuple(map(float, xy)) for hip, xy in positions.items()}
    edges = _edges(edges)
    if not original or any(hip not in original for edge in edges for hip in edge):
        raise ValueError("Every edge endpoint must identify an existing HIP star")
    if any(not all(math.isfinite(v) for v in xy) or len(xy) != 2 for xy in original.values()):
        raise ValueError("Finite two-dimensional star positions are required")
    baseline = legacy_layout(original, edges, board=board)
    scales = [1.0] if not allow_uniform_scale else [1 + (policy.max_uniform_scale - 1) * i / policy.scale_steps
                                                 for i in range(policy.scale_steps + 1)]
    best = None
    trials = 0
    for scale in scales:
        center = policy.chart_center_mm
        placed = {hip: tuple(center[i] + scale * (xy[i] - center[i]) for i in (0, 1)) for hip, xy in original.items()}
        if any(not policy.star_center_y_limits_mm[0] <= xy[1] <= policy.star_center_y_limits_mm[1] for xy in placed.values()):
            continue
        if any(not board.buffer(-policy.slot_to_board_web_mm).covers(hole) for hole in _holes(placed, policy).values()):
            continue
        base = _base_parts(placed, edges, board, policy)
        candidates = _orders(edges, base, placed, policy.random_order_trials)
        for order in candidates:
            current = _trial(placed, edges, board, policy, base, order)
            trials += 1
            if not current.metadata["fr4_single_connected_component"] or not current.metadata["all_apertures_inside_board"]:
                continue
            score = (current.metadata["slotted_edge_count"], current.metadata["total_centerline_length_mm"],
                     -len(current.slots), -scale)
            if best is None or score > best[0]:
                best = (score, scale, current)
    if best is None:
        raise ValueError("No valid slot layout fits the board and label keepouts")
    _, scale, result = best
    result.metadata.update({"strategy": "uniform_scale_and_obstacle_trimmed_capsules",
        "uniform_scale": scale, "maximum_star_shift_mm": max(math.dist(original[hip], xy) for hip, xy in result.positions.items()),
        "preserved_hip_ids": sorted(original), "preserved_logical_edges": [list(edge) for edge in edges],
        "star_positions_before_mm": {str(hip): list(xy) for hip, xy in original.items()},
        "star_positions_final_mm": {str(hip): list(xy) for hip, xy in result.positions.items()},
        "policy": dict(policy.__dict__), "trial_count": trials,
        "legacy": baseline.metadata,
        "delta_slotted_edges": result.metadata["slotted_edge_count"] - baseline.metadata["slotted_edge_count"],
        "delta_centerline_length_mm": result.metadata["total_centerline_length_mm"] - baseline.metadata["total_centerline_length_mm"],
        "slots": result.slot_records,
        "limitations": ["Short or crowded logical links remain fully printed; not every edge can be milled at these webs.",
                        "Minimum 1.5mm overall capsule requires supplier confirmation for a 1mm cutter.",
                        "Uniform layout enlargement preserves all node relationships; it does not validate astronomical source coordinates or physical optical uniformity.",
                        "Geometry and single-component FR-4 checks do not replace supplier CAM, depanelization or sample acceptance."]})
    return result
