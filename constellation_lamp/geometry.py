"""Physical strip footprints, including PCB width rather than just LED centres."""

import math


def panel_limits(panel):
    if not isinstance(panel, dict):
        raise ValueError("panel must be an object")
    values = []
    for key, default in (("width_mm", None), ("height_mm", None), ("margin_mm", 5.0)):
        value = panel.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"panel.{key} must be a finite number")
        values.append(float(value))
    width, height, margin = values
    if width <= 0 or height <= 0 or margin < 0 or 2 * margin >= min(width, height):
        raise ValueError("panel must have positive dimensions and a nonnegative usable margin")
    return width, height, margin


def footprint_bounds(pieces, strip_width_mm):
    """Bounding box of straight strip rectangles along each path segment."""
    corners = []
    half_width = strip_width_mm / 2
    for piece in pieces:
        points = piece["path_mm"] if isinstance(piece, dict) else piece.path_mm
        for a, b in zip(points, points[1:]):
            length = math.dist(a, b)
            if length <= 0:
                raise ValueError("PCB footprint path segments must have positive length")
            nx = -(b[1] - a[1]) / length * half_width
            ny = (b[0] - a[0]) / length * half_width
            corners.extend((p[0] + sign * nx, p[1] + sign * ny) for p in (a, b) for sign in (-1, 1))
    if not corners:
        raise ValueError("Cannot bound an empty strip layout")
    return (min(p[0] for p in corners), min(p[1] for p in corners),
            max(p[0] for p in corners), max(p[1] for p in corners))


def validate_panel(pieces, strip_width_mm, panel):
    width, height, margin = panel_limits(panel)
    bounds = footprint_bounds(pieces, strip_width_mm)
    if (bounds[0] < margin - 1e-5 or bounds[1] < margin - 1e-5
            or bounds[2] > width - margin + 1e-5 or bounds[3] > height - margin + 1e-5):
        raise ValueError(f"Panel size conflict: PCB footprint {tuple(round(v, 3) for v in bounds)} "
                         f"does not fit {width:g} x {height:g} mm with {margin:g} mm margin")
    return bounds
