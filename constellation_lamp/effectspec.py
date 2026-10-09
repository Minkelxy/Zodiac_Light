"""Shared, standard-library effect identifiers, defaults and route selection."""

from __future__ import annotations

import heapq
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Runtime

EFFECT_NAMES = ("twinkle", "flow", "ripple", "breath", "aurora", "sparkle", "graph_wave", "draw", "meteor")
EFFECT_LABELS = {
    "twinkle": "Soft twinkle", "flow": "Path flow", "ripple": "Space ripples",
    "breath": "Warm breathing", "aurora": "Aurora curtains", "sparkle": "Starlight sparks",
    "graph_wave": "Graph pulse", "draw": "Draw the sky", "meteor": "Meteor trail",
}
EFFECT_DESCRIPTIONS = {
    "twinkle": "Independent warm stars above a quiet blue constellation.",
    "flow": "A cyan pulse follows a chosen connected route.",
    "ripple": "Blue and violet rings spread across physical space.",
    "breath": "The whole constellation slowly breathes in warm gold.",
    "aurora": "Green, cyan and violet curtains drift across the sky.",
    "sparkle": "Seeded short flashes brighten individual stars.",
    "graph_wave": "A pulse branches along graph distances from one star.",
    "draw": "Trace every edge, hold the complete figure, then fade.",
    "meteor": "A bright head with a blue tail sweeps through space.",
}
EFFECT_DEFAULTS = {
    "twinkle": {},
    "flow": {"flow_velocity_mm_s": 140.0, "flow_width_mm": 35.0},
    "ripple": {"wavelength_mm": 180.0, "ripple_velocity_mm_s": 90.0},
    "breath": {"breath_period_s": 6.0, "breath_floor": 0.08},
    "aurora": {"aurora_wavelength_mm": 220.0, "aurora_velocity_mm_s": 22.0, "aurora_contrast": 0.65},
    "sparkle": {"sparkle_period_s": 3.2, "sparkle_duration_s": 0.8, "sparkle_density": 0.85},
    "graph_wave": {"source_star": None, "graph_velocity_mm_s": 100.0, "graph_width_mm": 25.0,
                   "graph_period_s": None},
    "draw": {"source_star": None, "draw_velocity_mm_s": 160.0, "draw_hold_s": 2.5,
             "draw_fade_s": 1.5, "draw_head_width_mm": 20.0},
    "meteor": {"meteor_angle_deg": -35.0, "meteor_velocity_mm_s": 220.0,
               "meteor_tail_mm": 80.0, "meteor_width_mm": 45.0, "meteor_interval_s": None},
}



def default_route(runtime: Runtime) -> list[str]:
    """Choose the longest finite shortest path, with stable alphabetical ties.

    This follows the constellation graph rather than the strip wiring.  Custom
    routes remain preferable when the desired animated path is known.
    """
    adjacency: dict[str, list[tuple[str, float]]] = {star.id: [] for star in runtime.stars}
    for edge in runtime.edges:
        adjacency[edge.start_id].append((edge.end_id, edge.length_mm))
        adjacency[edge.end_id].append((edge.start_id, edge.length_mm))
    longest = -1.0
    chosen: list[str] = []
    for start in sorted(adjacency):
        distance = {start: 0.0}
        paths = {start: (start,)}
        queue = [(0.0, (start,), start)]
        while queue:
            dist, path, node = heapq.heappop(queue)
            if dist != distance[node] or path != paths[node]:
                continue
            for neighbor, length in sorted(adjacency[node]):
                candidate = dist + length
                candidate_path = path + (neighbor,)
                old = distance.get(neighbor, math.inf)
                if candidate < old - 1e-9 or (
                    abs(candidate - old) <= 1e-9 and candidate_path < paths.get(neighbor, ("\uffff",))
                ):
                    distance[neighbor] = candidate
                    paths[neighbor] = candidate_path
                    heapq.heappush(queue, (candidate, candidate_path, neighbor))
        for end in sorted(distance):
            if end != start and distance[end] > longest + 1e-9:
                longest = distance[end]
                chosen = list(paths[end])
    if len(chosen) < 2:
        raise ValueError("flow requires at least one connected edge")
    return chosen
