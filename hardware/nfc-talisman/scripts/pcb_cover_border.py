"""Offline white-silk border for the project's 37 mm AF octagonal covers.

All geometry uses cover-local millimetres, x right and y down.  Nothing in this
module changes source artwork, copper, solder mask, drill/slot or board outline.
``build_border`` returns (silk_geometry, metadata, content_safe_region).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from shapely import affinity
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box
from shapely.ops import linemerge, substring, unary_union

import build_standard_layer_artwork as standard
from talisman_cover_artwork import canonical_geometry, compact


VERSION = "af37-closed-double-contour-ticks-v2"
HW = Path(__file__).resolve().parents[1]
PROJECT = HW.parents[1]
PARAMETERS = {
    "across_flats_mm": 37.0,
    "outer_center_inset_mm": .70, "outer_width_mm": .22,
    "inner_center_inset_mm": 2.10, "inner_width_mm": .24,
    "tick_center_inset_mm": 1.35, "tick_centerline_length_mm": .42,
    "tick_width_mm": .22, "tick_pitch_mm": 2.40,
    "tick_corner_keepout_mm": 1.40, "corner_dot_diameter_mm": .28,
    "content_safe_inset_mm": 3.0,
    "minimum_feature_width_mm": .20, "minimum_feature_gap_mm": .20,
    "minimum_board_edge_gap_mm": .50,
    "existing_art_clearance_mm": .20, "aperture_mask_clearance_mm": .20,
    "numerical_clearance_guard_mm": .01,
    "cardinal_bridge_width_mm": 4.0, "cardinal_bridge_depth_mm": 0.0,
    "bridge_clearance_mm": .30,
    "postage_drill_diameter_mm": .40, "postage_hole_pitch_mm": .72,
    "postage_holes_per_bridge": 5, "postage_hole_clearance_mm": .20,
    "postage_outward_offset_mm": .40,
    "trimmed_endpoint_retreat_mm": .22, "minimum_centerline_fragment_mm": .30,
}


def af37_board():
    """Exact mathematical octagon; source SVG rounded vertices are not used."""
    half = 18.5
    corner = half * (math.sqrt(2) - 1)
    return Polygon([(half - corner, 0), (half + corner, 0),
                    (37, half - corner), (37, half + corner),
                    (half + corner, 37), (half - corner, 37),
                    (0, half + corner), (0, half - corner)])


def _lines(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type in ("LineString", "LinearRing"):
        yield LineString(geometry.coords)
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from _lines(part)


def _geometry_hash(geometry):
    return hashlib.sha256(compact(canonical_geometry(geometry)).encode("ascii")).hexdigest()


def _distance(a, b):
    return None if a.is_empty or b.is_empty else round(a.distance(b), 6)


def _minimum_component_gap(geometry):
    parts = list(standard.polygons(geometry))
    return min((a.distance(b) for i, a in enumerate(parts) for b in parts[i + 1:]), default=None)


def _nominal_mechanical_keepouts(parameters=None):
    """Nominal bridges/postage drilling of the existing 100 mm cover panels.

    These are conservative silk exclusions, not replacement physical geometry.
    Actual supplied mask openings are additionally respected by build_border.
    """
    p = PARAMETERS if parameters is None else parameters
    half_width = p["cardinal_bridge_width_mm"] / 2
    depth = p["cardinal_bridge_depth_mm"]
    middle = 18.5
    bridges = unary_union([
        box(middle - half_width, -1, middle + half_width, depth),
        box(middle - half_width, 37 - depth, middle + half_width, 38),
        box(-1, middle - half_width, depth, middle + half_width),
        box(37 - depth, middle - half_width, 38, middle + half_width),
    ])
    drill_centers = []
    for index in range(p["postage_holes_per_bridge"]):
        offset = (index - (p["postage_holes_per_bridge"] - 1) / 2) * p["postage_hole_pitch_mm"]
        outward = p["postage_outward_offset_mm"]
        drill_centers.extend([(middle + offset, -outward), (middle + offset, 37 + outward),
                              (-outward, middle + offset), (37 + outward, middle + offset)])
    drills = unary_union([Point(x, y).buffer(p["postage_drill_diameter_mm"] / 2, quad_segs=16)
                          for x, y in drill_centers])
    return bridges, drills, drill_centers


def build_border(existing_art=None, aperture_mask=None, *, board=None, standard_panel=False):
    """Build separate silk fills around existing art and actual mask openings.

    Art is never clipped or modified.  Obstructed border centerlines are cut
    before buffering, so trimmed ends remain their specified full silk width.
    A 0.01 mm numerical guard is added to the required 0.20 mm art/mask gap.
    ``content_safe_region`` is the board inset 3 mm (before any art/mask cuts).
    """
    p = dict(PARAMETERS)
    if standard_panel:
        p.update(cardinal_bridge_width_mm=5., postage_drill_diameter_mm=.6, postage_hole_pitch_mm=.95)
    board = af37_board() if board is None else board
    art = GeometryCollection() if existing_art is None else existing_art
    mask = GeometryCollection() if aperture_mask is None else aperture_mask
    if board.geom_type != "Polygon" or not board.is_valid or board.is_empty:
        raise ValueError("A single valid cover polygon is required")
    if any(abs(a - b) > .001 for a, b in zip(board.bounds, (0, 0, 37, 37))):
        raise ValueError("Border coordinates require a local 37 mm cover at (0,0)")
    if not art.is_valid or not mask.is_valid:
        raise ValueError("Existing art and aperture mask must be valid geometry")
    bridges, drills, drill_centers = _nominal_mechanical_keepouts(p)
    padding=p['inner_width_mm']/2+p['existing_art_clearance_mm']+p['numerical_clearance_guard_mm']
    inner_region=unary_union([board.buffer(-p['inner_center_inset_mm'],join_style='mitre'),
                             art.buffer(padding,quad_segs=24),mask.buffer(padding,quad_segs=24)]).convex_hull
    inner_line=LineString(inner_region.exterior.coords)
    inner_silk=inner_line.buffer(p['inner_width_mm']/2,quad_segs=24)
    if inner_silk.geom_type!='Polygon' or len(inner_silk.interiors)!=1:
        raise ValueError('Inner divider must be one closed enclosing ring')
    blocked = unary_union([
        bridges.buffer(p["bridge_clearance_mm"], join_style="mitre"),
        drills.buffer(p["postage_hole_clearance_mm"]),
        art.buffer(p["existing_art_clearance_mm"] + p["numerical_clearance_guard_mm"]),
        mask.buffer(p["aperture_mask_clearance_mm"] + p["numerical_clearance_guard_mm"]),
        inner_silk.buffer(p['minimum_feature_gap_mm']+p['numerical_clearance_guard_mm']),
    ])
    features, counts = [], {}

    def stroke(role, line, width):
        if role=='inner_divider':
            features.append(inner_silk)
            counts[role]={'proposed':1,'accepted_parts':1,'trimmed':0}
            return
        available = line.difference(blocked.buffer(width / 2, quad_segs=24))
        trimmed = not line.equals(available)
        if role == "inner_divider" and (trimmed or not available.is_ring):
            raise ValueError("The inner divider must remain a complete closed ring")
        # A closed ring's arbitrary first vertex is not an actual cut. Join
        # pieces meeting there before retreating genuine obstructed endpoints.
        if available.geom_type == "MultiLineString":
            available = linemerge(available)
        accepted = 0
        for part in _lines(available):
            if trimmed and not part.is_ring:
                retreat = p["trimmed_endpoint_retreat_mm"]
                if part.length <= 2 * retreat + p["minimum_centerline_fragment_mm"]:
                    continue
                part = substring(part, retreat, part.length - retreat)
            if part.length < p["minimum_centerline_fragment_mm"]:
                continue
            features.append(part.buffer(width / 2, quad_segs=24))
            accepted += 1
        item = counts.setdefault(role, {"proposed": 0, "accepted_parts": 0, "trimmed": 0})
        item["proposed"] += 1
        item["accepted_parts"] += accepted
        item["trimmed"] += int(trimmed)

    for role, inset, width in (("outer_contour", p["outer_center_inset_mm"], p["outer_width_mm"]),
                               ("inner_divider", p["inner_center_inset_mm"], p["inner_width_mm"])):
        stroke(role, LineString(board.buffer(-inset, join_style="mitre").exterior.coords), width)

    middle = board.buffer(-p["tick_center_inset_mm"], join_style="mitre")
    vertices = list(middle.exterior.coords)[:-1]
    for index, start in enumerate(vertices):
        end = vertices[(index + 1) % len(vertices)]
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        usable = length - 2 * p["tick_corner_keepout_mm"]
        number = max(1, int(usable // p["tick_pitch_mm"]) + 1)
        beginning = (length - (number - 1) * p["tick_pitch_mm"]) / 2
        for tick_index in range(number):
            along = beginning + tick_index * p["tick_pitch_mm"]
            x, y = start[0] + ux * along, start[1] + uy * along
            normal_x, normal_y = -uy, ux
            half = p["tick_centerline_length_mm"] / 2
            stroke("short_ticks", LineString([(x - normal_x * half, y - normal_y * half),
                                               (x + normal_x * half, y + normal_y * half)]),
                   p["tick_width_mm"])
        dot = Point(start).buffer(p["corner_dot_diameter_mm"] / 2, quad_segs=24)
        counts.setdefault("corner_dots", {"proposed": 0, "accepted_parts": 0, "trimmed": 0})
        counts["corner_dots"]["proposed"] += 1
        if dot.disjoint(blocked):
            features.append(dot)
            counts["corner_dots"]["accepted_parts"] += 1

    silk = unary_union(features)
    if not silk.is_valid or silk.is_empty:
        raise ValueError("Border construction produced invalid or empty silk")
    gap = _minimum_component_gap(silk)
    clearances = {
        "board_edge": _distance(silk, board.boundary),
        "postage_holes": _distance(silk, drills),
        "cardinal_bridges": _distance(silk, bridges),
        "existing_art": _distance(silk, art),
        "aperture_mask": _distance(silk, mask),
        "disconnected_features": None if gap is None else round(gap, 6),
    }
    if not board.covers(silk) or clearances["board_edge"] < p["minimum_board_edge_gap_mm"] - 1e-6:
        raise ValueError("Border violates its board-edge clearance")
    for key, minimum in (("postage_holes", p["postage_hole_clearance_mm"]),
                         ("cardinal_bridges", p["bridge_clearance_mm"]),
                         ("existing_art", p["existing_art_clearance_mm"]),
                         ("aperture_mask", p["aperture_mask_clearance_mm"]),
                         ("disconnected_features", p["minimum_feature_gap_mm"])):
        if clearances[key] is not None and clearances[key] < minimum - 1e-5:
            raise ValueError(f"Border {key} gap {clearances[key]} is below {minimum} mm")
    safe = board.buffer(-p["content_safe_inset_mm"], join_style="mitre")
    metadata = {
        "version": VERSION, "layer_id": 3, "parameters": dict(p),
        "coordinate_system": "cover_top_left_x_right_y_down", "units": "mm",
        "feature_counts": counts, "polygon_count": len(list(standard.polygons(silk))),
        "inner_divider_closed": True,
        "inner_divider_geometry": canonical_geometry(inner_silk),
        "inner_divider_geometry_sha256": _geometry_hash(inner_silk),
        "inner_divider_policy": "Closed convex envelope of nominal 2.10mm inset and complete art/mask padded by 0.33mm; locally steps outward around crowded stars without moving apertures",
        "silk_area_mm2": round(silk.area, 6), "clearances_mm": clearances,
        "geometry": canonical_geometry(silk), "geometry_sha256": _geometry_hash(silk),
        "content_safe_geometry": canonical_geometry(safe),
        "content_safe_geometry_sha256": _geometry_hash(safe),
        "existing_art_geometry_sha256": _geometry_hash(art),
        "aperture_mask_geometry_sha256": _geometry_hash(mask),
        "postage_drill_centers_mm": drill_centers,
        "bridge_exclusion_geometry": canonical_geometry(bridges.buffer(p["bridge_clearance_mm"], join_style="mitre")),
        "mechanical_policy": "Mousebite centers are 0.40 mm outside the nominal cover; original hole diameter/pitch retained. Bridge material lies outside the cover; inner divider is closed.",
        "stroke_policy": "Trim centerlines before full-width round buffering; retreat cut endpoints; reject whole obstructed corner dots; no morphological change to artwork",
        "content_safe_policy": "Exact AF37 polygon inset 3.0 mm for whole-subject fitting; source art is not cropped by this module",
    }
    return silk, metadata, safe


def fit_artwork(art, content_safe_region, *, allow_enlarge=False):
    """Uniformly fit complete existing art; return geometry and affine evidence.

    This is optional. For a provenance-rich new talisman use build_cover with
    board_margin_mm=3.0, which performs fitting directly from the source alpha.
    """
    if art.is_empty or not art.is_valid or content_safe_region.is_empty:
        raise ValueError("Nonempty valid artwork and fit region are required")
    ax0, ay0, ax1, ay1 = art.bounds
    sx0, sy0, sx1, sy1 = content_safe_region.bounds
    art_center = ((ax0 + ax1) / 2, (ay0 + ay1) / 2)
    safe_center = ((sx0 + sx1) / 2, (sy0 + sy1) / 2)
    upper = min((sx1 - sx0) / (ax1 - ax0), (sy1 - sy0) / (ay1 - ay0))
    if not allow_enlarge:
        upper = min(upper, 1.0)
    # The numerical inward guard prevents roundoff changing later native fills.
    target = content_safe_region.buffer(-.01, join_style="mitre")

    def transform(scale):
        return affinity.translate(affinity.scale(art, scale, scale, origin=art_center),
                                  safe_center[0] - art_center[0], safe_center[1] - art_center[1])

    low = 0.0
    for _ in range(54):
        middle = (low + upper) / 2
        if target.covers(transform(middle)):
            low = middle
        else:
            upper = middle
    result = transform(low)
    if low <= 0 or not target.covers(result):
        raise ValueError("Complete source subject could not fit the safe region")
    return result, {
        "method": "uniform_scale_and_translation_no_crop", "scale": low,
        "origin_mm": list(art_center),
        "translation_mm": [safe_center[0] - art_center[0], safe_center[1] - art_center[1]],
        "numerical_fit_guard_mm": .01, "source_geometry_sha256": _geometry_hash(art),
        "final_geometry_sha256": _geometry_hash(result), "final_geometry": canonical_geometry(result),
    }


def _saved_face(path, face):
    value = json.loads(path.read_text(encoding="utf-8"))["faces"][face]
    silk = unary_union([Polygon(p["rings_svg_mm"][0], p["rings_svg_mm"][1:])
                        for p in value["silk_polygons"] if "outer_keyline" not in p["id"]])
    mask = unary_union([Polygon(p["rings_svg_mm"][0], p["rings_svg_mm"][1:])
                        for p in value["mask_opening_polygons"]])
    physical = []
    for entry in value["source_metadata"].get("mechanical_apertures", []):
        if entry["type"] == "star_hole":
            physical.append(Point(entry["center_svg_mm"]).buffer(entry["diameter_mm"] / 2, quad_segs=24))
        else:
            physical.append(LineString(entry["centerline_svg_mm"]).buffer(entry["width_mm"] / 2, quad_segs=24))
    return silk, mask, unary_union(physical)


def render_examples(output):
    """Temporary visual review artifacts only; not production source files."""
    import talisman_cover_artwork as talisman

    output.mkdir(parents=True, exist_ok=True)
    board = af37_board()
    saved = HW / "variants/standard-green-white/artwork/snake-leo-standard-layer-artwork.json"
    leo, mask, physical = _saved_face(saved, "rear")
    tiger, _, provenance = talisman.build_cover("tiger", board_margin_mm=3.0)
    tiger = unary_union([tiger, standard.bold_label("TIGER", 33.3)])
    reports = {}
    for name, art, opening, cutout in (("leo", leo, mask, physical),
                                        ("tiger", tiger, GeometryCollection(), GeometryCollection())):
        border, metadata, _ = build_border(art, opening)
        standard.render_face(output, name + "-border-review", board, cutout, opening,
                             unary_union([art, border]))
        reports[name] = metadata
    reports["leo"]["example_source_file"] = saved.relative_to(PROJECT).as_posix()
    reports["leo"]["example_source_sha256"] = hashlib.sha256(saved.read_bytes()).hexdigest()
    reports["tiger"]["example_source_provenance"] = provenance
    (output / "border-review-metadata.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sheet = Image.new("RGB", (1300, 740), "#e9ece8")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(standard.BOLD_FONT_PATH), 25)
    for index, name in enumerate(("leo", "tiger")):
        im = Image.open(output / (name + "-border-review.png")).convert("RGBA")
        im.thumbnail((610, 610))
        sheet.paste(im, (20 + index * 650, 70), im)
        draw.text((30 + index * 650, 20), name.upper() + " - source artwork + white silk border", fill="#173b2c", font=font)
    sheet.save(output / "border-examples.png")
    return {name: reports[name]["clearances_mm"] for name in ("leo", "tiger")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT / "tmp/pcb-cover-border-review")
    args = parser.parse_args()
    print(json.dumps(render_examples(args.output), indent=2))
