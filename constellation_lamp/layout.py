"""Create a manufacturable initial layout, separate from the constellation graph."""

from __future__ import annotations

import math
from copy import deepcopy

from .geometry import panel_limits, validate_panel
from .model import ValidationError, count, number, validate_sources


def nearest_neighbor_order(pieces: list[dict], first_piece_id: str) -> list[dict]:
    """Deterministic initial wiring heuristic; this is not an optimal routing claim."""
    remaining = {piece["id"]: piece for piece in pieces}
    first = remaining.pop(first_piece_id)
    order = [{"piece_id": first_piece_id, "reverse": False}]
    output = first["path_mm"][-1]
    while remaining:
        candidates = []
        for piece_id, piece in remaining.items():
            for reverse in (False, True):
                entry = piece["path_mm"][-1] if reverse else piece["path_mm"][0]
                candidates.append((math.dist(output, entry), piece_id, reverse))
        _, piece_id, reverse = min(candidates)
        piece = remaining.pop(piece_id)
        order.append({"piece_id": piece_id, "reverse": reverse})
        output = piece["path_mm"][0] if reverse else piece["path_mm"][-1]
    return order


def _relax_positions(positions, edges, radii, pitch, cut_unit, panel, originals, maximum_shift):
    """Project nearby pairs apart without changing the source-image coordinates."""
    panel_width, panel_height, margin = panel_limits(panel)
    required_pairs = [(e["start"], e["end"], radii[e["start"]] + radii[e["end"]]
                       + pitch * cut_unit + 0.01) for e in edges]
    ids = list(positions)
    # Stars without a connecting line still cannot occupy overlapping regions.
    required_pairs += [(a, b, radii[a] + radii[b]) for i, a in enumerate(ids) for b in ids[i + 1:]]
    for _ in range(300):
        worst = 0.0
        for a, b, required in required_pairs:
            dx, dy = positions[b][0] - positions[a][0], positions[b][1] - positions[a][1]
            distance = math.hypot(dx, dy)
            missing = required - distance
            if missing <= 1e-6:
                continue
            worst = max(worst, missing)
            ux, uy = (dx / distance, dy / distance) if distance > 1e-8 else (1.0, 0.0)
            for star_id, sign in ((a, -1), (b, 1)):
                positions[star_id][0] += sign * ux * missing / 2
                positions[star_id][1] += sign * uy * missing / 2
        for star_id, xy in positions.items():
            radius = radii[star_id]
            xy[0] = min(panel_width - margin - radius, max(margin + radius, xy[0]))
            xy[1] = min(panel_height - margin - radius, max(margin + radius, xy[1]))
        if worst < 1e-6:
            break
    violations = [(a, b) for a, b, required in required_pairs if math.dist(positions[a], positions[b]) < required - 1e-5]
    shifts = {star_id: math.dist(xy, originals[star_id]) for star_id, xy in positions.items()}
    if violations or max(shifts.values()) > maximum_shift + 1e-5:
        raise ValidationError("Size conflict: cannot fit all stars and illuminated edges within panel "
                              f"and max_star_shift_mm={maximum_shift:g}; change the panel or star layout")
    return shifts


def generate_layout(catalog: dict, constellation: dict, template: dict | None = None,
                    width_mm: float | None = None) -> dict:
    """Regenerate straight segments from source image positions and layout settings.

    Explicitly regenerating resets manually edited paths/wiring. To compile a
    completed physical assembly, load its saved layout without regenerating.
    """
    _, nodes, edges = validate_sources(catalog, constellation)
    settings = deepcopy(template or {})
    density = number(settings.get("density_leds_per_m", 200), "density_leds_per_m", positive=True)
    pitch = 1000 / density
    cut_unit = count(settings.get("cut_unit_leds", 2), "cut_unit_leds")
    strip_width = number(settings.get("strip_width_mm", 0), "strip_width_mm")
    if strip_width < 0:
        raise ValidationError("strip_width_mm must be nonnegative")
    panel = settings.get("panel")
    if panel is not None and strip_width <= 0:
        raise ValidationError("A panel constraint requires the actual positive strip_width_mm")
    clearance = number(settings.get("star_clearance_mm", 1), "star_clearance_mm")
    if clearance < 0:
        raise ValidationError("star_clearance_mm must be nonnegative")
    defaults = settings.get("star_defaults", {"led_count": 2, "angle_deg": 0, "shape": "straight"})
    overrides = settings.get("star_overrides", {})
    if not isinstance(defaults, dict) or not isinstance(overrides, dict):
        raise ValidationError("star_defaults and star_overrides must be objects")
    node_ids = {row["id"] for row in nodes}
    if set(overrides) - node_ids:
        raise ValidationError(f"Unknown star overrides: {set(overrides) - node_ids}")
    xs = [row["reference_px"][0] for row in nodes]
    ys = [row["reference_px"][1] for row in nodes]
    span = max(xs) - min(xs)
    if span <= 0:
        raise ValidationError("Source star positions must have a positive horizontal span")
    configs, radii = {}, {}
    for row in nodes:
        star_id = row["id"]
        override = overrides.get(star_id, {})
        if not isinstance(override, dict):
            raise ValidationError(f"{star_id}: override must be an object")
        config = {"led_count": 2, "angle_deg": 0, "shape": "straight", "row_gap_mm": 2,
                  **defaults, **override}
        n = count(config["led_count"], f"{star_id}.led_count", cut_unit)
        number(config["angle_deg"], f"{star_id}.angle_deg")
        if config["shape"] == "grid_2x2":
            if n != 4 or 2 % cut_unit or strip_width <= 0:
                raise ValidationError(f"{star_id}: grid_2x2 requires 4 LEDs, two-LED cuts and strip_width_mm")
            gap = number(config["row_gap_mm"], f"{star_id}.row_gap_mm")
            if gap < 0:
                raise ValidationError("row_gap_mm must be nonnegative")
            config["row_pitch_mm"] = strip_width + gap
            radius = math.hypot(pitch, strip_width + gap / 2)
        elif config["shape"] == "straight":
            radius = math.hypot(n * pitch / 2, strip_width / 2)
        else:
            raise ValidationError(f"{star_id}: unsupported star shape {config['shape']!r}")
        configs[star_id] = config
        radii[star_id] = radius + clearance
    if panel is not None:
        try:
            panel_width, panel_height, margin = panel_limits(panel)
        except ValueError as error:
            raise ValidationError(str(error)) from error
        max_radius = max(radii.values())
        vertical_span = max(ys) - min(ys)
        usable_width, usable_height = panel_width - 2 * (margin + max_radius), panel_height - 2 * (margin + max_radius)
        if usable_width <= 0 or usable_height <= 0:
            raise ValidationError("Panel size conflict: star footprints are larger than the usable panel")
        max_scale = min(usable_width / span, usable_height / vertical_span if vertical_span > 0 else math.inf)
        width = number(width_mm, "width_mm", positive=True) if width_mm is not None else max_scale * span
        if width > max_scale * span + 1e-6:
            raise ValidationError(f"Panel size conflict: width_mm={width:g} exceeds the maximum "
                                  f"star-centre width {max_scale * span:.3f} for this panel")
        scale = width / span
        offset_x = (panel_width - width) / 2
        offset_y = (panel_height - vertical_span * scale) / 2
        border = margin
    else:
        width = number(width_mm if width_mm is not None else settings.get("width_mm", 500),
                       "width_mm", positive=True)
        scale = width / span
        border = 10.0
        offset_x = offset_y = border
    positions = {row["id"]: [(row["reference_px"][0] - min(xs)) * scale + offset_x,
                             (row["reference_px"][1] - min(ys)) * scale + offset_y] for row in nodes}
    originals = deepcopy(positions)
    shifts = {key: 0.0 for key in positions}
    adjust = settings.get("adjust_nearby_stars", panel is not None)
    if not isinstance(adjust, bool):
        raise ValidationError("adjust_nearby_stars must be a boolean")
    maximum_shift = number(settings.get("max_star_shift_mm", 20), "max_star_shift_mm", positive=True)
    if panel is not None and adjust:
        shifts = _relax_positions(positions, edges, radii, pitch, cut_unit, panel, originals, maximum_shift)
    pieces = []
    for row in nodes:
        star_id = row["id"]
        config = configs[star_id]
        n = config["led_count"]
        angle = math.radians(config["angle_deg"])
        x, y = positions[star_id]
        if config["shape"] == "grid_2x2":
            half_row = config["row_pitch_mm"] / 2
            local_paths = [[[-pitch, -half_row], [pitch, -half_row]],
                           [[-pitch, half_row], [pitch, half_row]]]
        else:
            local_paths = [[[-n * pitch / 2, 0], [n * pitch / 2, 0]]]
        for i, local in enumerate(local_paths):
            rotated = [[x + a * math.cos(angle) - b * math.sin(angle),
                        y + a * math.sin(angle) + b * math.cos(angle)] for a, b in local]
            suffix = f"_row{i}" if len(local_paths) > 1 else ""
            pieces.append({"id": f"star_{star_id}{suffix}", "owner_type": "star", "owner_id": star_id,
                           "led_count": n // len(local_paths), "path_mm": rotated})
    edge_paths = {}
    conflicts = []
    for row in edges:
        start, end = positions[row["start"]], positions[row["end"]]
        distance = math.dist(start, end)
        edge_paths[row["id"]] = [start, end]
        available = distance - radii[row["start"]] - radii[row["end"]]
        n = math.floor((available + 1e-8) / (pitch * cut_unit)) * cut_unit
        if n < cut_unit:
            conflicts.append(f"{row['id']} ({row['start']} -> {row['end']}): "
                             f"{available:.2f} mm available, need {pitch * cut_unit:g} mm")
            continue
        segment_length = n * pitch
        # Centre in the AVAILABLE interval, accounting for differently sized stars.
        inset = radii[row["start"]] + (available - segment_length) / 2
        ux, uy = (end[0] - start[0]) / distance, (end[1] - start[1]) / distance
        a = [start[0] + ux * inset, start[1] + uy * inset]
        b = [a[0] + ux * segment_length, a[1] + uy * segment_length]
        pieces.append({"id": f"edge_{row['id']}", "owner_type": "edge", "owner_id": row["id"],
                       "led_count": n, "path_mm": [a, b]})
    if conflicts:
        raise ValidationError("Size conflict: enlarge width_mm or reduce star sizes.\n" + "\n".join(conflicts))
    if panel is not None:
        try:
            validate_panel(pieces, strip_width, panel)
        except ValueError as error:
            raise ValidationError(str(error)) from error
    result = {
        "schema_version": 1,
        "density_leds_per_m": density,
        "cut_unit_leds": cut_unit,
        "width_mm": (max(p[0] for p in positions.values()) - min(p[0] for p in positions.values())) if panel is not None else width,
        "height_mm": max(p[1] for p in positions.values()) - min(p[1] for p in positions.values()),
        "coordinate_system": "x_right_y_down_mm",
        "star_defaults": {"led_count": 2, "angle_deg": 0, "shape": "straight", **defaults},
        "star_overrides": overrides,
        "star_clearance_mm": clearance,
        "star_positions_mm": positions,
        "edge_paths_mm": edge_paths,
        "pieces": pieces,
        "wiring": {"order": nearest_neighbor_order(pieces, pieces[0]["id"])},
        "generation": {"method": "image_scale_strip_segments", "scale_mm_per_px": scale,
                       "border_mm": border, "wiring_method": "nearest_neighbor_heuristic",
                       "original_scaled_positions_mm": originals,
                       "star_shift_mm": shifts,
                       "max_star_shift_mm": max(shifts.values()),
                       "note": "Generated initial wiring; confirm actual DIN/DOUT during assembly."},
    }
    if strip_width > 0:
        result["strip_width_mm"] = strip_width
    if panel is not None:
        result["panel"] = deepcopy(panel)
        result["adjust_nearby_stars"] = adjust
        result["max_star_shift_mm"] = maximum_shift
    return result
