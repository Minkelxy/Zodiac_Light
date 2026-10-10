#!/usr/bin/env python3
"""Audit Sagittarius apertures and silkscreen against the exported panel.

Reads the current geometry, artwork, native panel source, and manufacturing
Gerber ZIP. It writes only manufacturing/draft/star-face-audit.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box
from shapely.affinity import scale, translate
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "geometry" / "design.json"
ARTWORK = ROOT / "artwork" / "art_data.json"
PANEL_SOURCE = ROOT / "eda" / "native" / "panel-source.jsonl"
ZIP_PATH = ROOT / "manufacturing" / "draft" / "nfc-talisman-panel-draft.zip"
REPORT = ROOT / "manufacturing" / "draft" / "star-face-audit.json"
MIL_TO_MM = 0.0254
PANEL_SIZE = 100.0
MATCH_TOLERANCE_MM = 0.01
APERTURE_CONTOUR_TOLERANCE_MM = 0.004
SILK_CLEARANCE_MM = 0.18
WEB_MM = 1.0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def semantic_sha256(value) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(canonical)


def read_native_objects(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if "||" not in line:
            continue
        left, right = line.split("||", 1)
        try:
            yield json.loads(left), json.loads(right.rstrip("|\r\n"))
        except (json.JSONDecodeError, TypeError):
            continue


def native_path_points(data: dict) -> list[tuple[float, float]]:
    raw = data.get("path") or []
    nums = [v for v in raw if isinstance(v, (int, float))]
    if len(nums) < 4 or len(nums) % 2:
        return []
    return [(nums[i] * MIL_TO_MM, nums[i + 1] * MIL_TO_MM)
            for i in range(0, len(nums), 2)]


def parse_drill(data: bytes):
    tools, active, holes = {}, None, []
    for line in data.decode("ascii", "replace").splitlines():
        m = re.match(r"T(\d+)C([0-9.]+)", line)
        if m:
            tools[m.group(1)] = float(m.group(2))
            continue
        m = re.fullmatch(r"T(\d+)", line.strip())
        if m:
            active = m.group(1)
            continue
        m = re.match(r"X(-?[0-9.]+)Y(-?[0-9.]+)", line.strip())
        if m and active:
            holes.append({"diameter_mm": tools[active],
                          "center_native_mm": [float(m.group(1)), float(m.group(2))],
                          "tool": active})
    return tools, holes


def parse_gerber_paths(data: bytes):
    paths, current = [], []
    text = data.decode("ascii", "replace")
    for x, y, op in re.findall(r"X(-?\d+)Y(-?\d+)D0([123])", text):
        point, op = (int(x) / 1e6, int(y) / 1e6), int(op)
        if op == 2:
            if current:
                paths.append(current)
            current = [point]
        elif op == 1 and current:
            current.append(point)
        elif op == 3:
            if current:
                paths.append(current)
                current = []
    if current:
        paths.append(current)
    return text, paths


def parse_apertures(text: str):
    result = {}
    for m in re.finditer(r"%ADD(\d+)(C|R|O),([^*%]+)\*%", text):
        code, shape, raw = m.groups()
        values = [float(x) for x in raw.split("X")]
        if shape == "C":
            w = h = values[0]
        else:
            w, h = values[:2]
        result[code] = (shape, w, h)
    return result


def parse_gerber_strokes(data: bytes):
    text = data.decode("ascii", "replace")
    apertures, active, current, current_path, current_width, objects = parse_apertures(text), None, None, [], None, []

    def finish_path():
        nonlocal current_path, current_width
        if len(current_path) >= 2 and current_width:
            line = LineString(current_path)
            objects.append({"geometry": line.buffer(current_width / 2, cap_style="round", join_style="round"),
                            "width_mm": current_width, "centerline": line})
        current_path, current_width = [], None

    for line in text.splitlines():
        select = re.search(r"G54D(\d+)\*", line)
        if select:
            active = select.group(1)
            continue
        cmd = re.search(r"X(-?\d+)Y(-?\d+)D0([123])\*", line)
        if not cmd:
            continue
        pt = (int(cmd.group(1)) / 1e6, int(cmd.group(2)) / 1e6)
        op = int(cmd.group(3))
        if op == 2:
            finish_path()
            current = pt
            current_path = [pt]
        elif op == 1 and current is not None:
            ap = apertures.get(active)
            if ap:
                shape, w, h = ap
                width = max(w, h) if shape in ("R", "O") else w
                if current_path and current_path[-1] != current:
                    finish_path()
                    current_path = [current]
                if current_width is not None and abs(current_width - width) > 1e-9:
                    finish_path()
                    current_path = [current]
                current_width = width
                current_path.append(pt)
            current = pt
        elif op == 3:
            finish_path()
            current = pt
    finish_path()
    return objects


def polygon_from_ring(ring, y_reflect=False):
    points = [(float(p[0]), PANEL_SIZE - float(p[1]) if y_reflect else float(p[1])) for p in ring]
    if points and points[0] != points[-1]:
        points.append(points[0])
    return Polygon(points)


def capsule_path(data: dict, reflect_native_y=False):
    points = native_path_points(data)
    if reflect_native_y:
        points = [(x, PANEL_SIZE - y) for x, y in points]
    explicitly_closed = len(points) > 2 and points[0] == points[-1]
    if points and points[0] != points[-1]:
        points.append(points[0])
    return Polygon(points), explicitly_closed


def nearest(target, candidates, geom_key="geometry"):
    if not candidates:
        return None, None
    pair = min(candidates, key=lambda item: target.hausdorff_distance(item[geom_key]))
    return pair, target.hausdorff_distance(pair[geom_key])


def circle(center, diameter):
    return Point(*center).buffer(diameter / 2, resolution=64)


def rounded(v, n=6):
    if isinstance(v, float):
        return round(v, n)
    return v


def main():
    geometry_bytes, artwork_bytes = GEOMETRY.read_bytes(), ARTWORK.read_bytes()
    native_bytes, zip_bytes = PANEL_SOURCE.read_bytes(), ZIP_PATH.read_bytes()
    design, art = json.loads(geometry_bytes), json.loads(artwork_bytes)
    board = next(b for b in design["boards"] if b.get("id") == "sagittarius5")
    panel_records = list(read_native_objects(PANEL_SOURCE))
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zip_bad_member = zf.testzip()
        members = {name: zf.read(name) for name in zf.namelist()}

    # Source geometry is compared in the design's top-left/Y-down frame.
    source_star_pads = {}
    source_slots = []
    silk_source = []
    for meta, obj in panel_records:
        kind = meta.get("type")
        if kind == "PAD" and str(obj.get("num", "")).startswith("HIP_") and obj.get("hole"):
            name = str(obj["num"]).lower().replace("hip_", "hip_")
            c = [obj["centerX"] * MIL_TO_MM, PANEL_SIZE - obj["centerY"] * MIL_TO_MM]
            source_star_pads[name] = {"diameter_mm": obj["hole"]["width"] * MIL_TO_MM,
                                      "height_mm": obj["hole"]["height"] * MIL_TO_MM,
                                      "hole_type": obj["hole"].get("holeType"),
                                      "native_pad_num": obj["num"],
                                      "plated": obj.get("plated"), "center_mm": c,
                                      "geometry": circle(c, obj["hole"]["width"] * MIL_TO_MM)}
        if kind == "POLY" and obj.get("layerId") == 11:
            poly, explicitly_closed = capsule_path(obj, reflect_native_y=True)
            if not poly.is_empty and poly.area > 0:
                source_slots.append({"id": meta.get("id"), "geometry": poly,
                                     "width_mm": obj.get("width", 0) * MIL_TO_MM,
                                     "vertex_count": len(poly.exterior.coords) - 1,
                                     "explicitly_closed": explicitly_closed})
        if kind == "POLY" and obj.get("layerId") in (3, 4):
            pts = native_path_points(obj)
            if len(pts) >= 2:
                if obj.get("closed") and pts[0] != pts[-1]:
                    pts.append(pts[0])
                silk_source.append({"id": meta.get("id"), "layer_id": obj.get("layerId"),
                                    "line": LineString(pts), "width_mm": obj.get("width", 0) * MIL_TO_MM})
        elif kind == "LINE" and obj.get("layerId") in (3, 4):
            silk_source.append({"id": meta.get("id"), "layer_id": obj.get("layerId"),
                                "line": LineString([(obj["startX"] * MIL_TO_MM, obj["startY"] * MIL_TO_MM),
                                                    (obj["endX"] * MIL_TO_MM, obj["endY"] * MIL_TO_MM)]),
                                "width_mm": obj.get("width", 0) * MIL_TO_MM})

    expected_holes = board.get("drills", [])
    expected_slots = [c for c in board.get("cutouts", []) if c.get("type") == "constellation_slot"]
    hole_source_checks = []
    source_hole_geoms = []
    for hole in expected_holes:
        name = str(hole["id"]).lower()
        target = hole["center"]
        found = source_star_pads.get(name)
        if found:
            delta = math.dist(found["center_mm"], target)
            source_hole_geoms.append(found["geometry"])
            hole_source_checks.append({"id": hole["id"], "native_pad_num": found["native_pad_num"],
                                      "native_hole_type": found["hole_type"], "present": True,
                                      "diameter_mm": found["diameter_mm"], "hole_height_mm": found["height_mm"],
                                      "plated": found["plated"], "center_error_mm": rounded(delta),
                                      "diameter_error_mm": rounded(abs(found["diameter_mm"] - hole["diameter_mm"])),
                                      "round_hole_shape_pass": found["hole_type"] == "ROUND" and abs(found["diameter_mm"] - found["height_mm"]) <= MATCH_TOLERANCE_MM})
        else:
            hole_source_checks.append({"id": hole["id"], "present": False})

    source_slot_checks = []
    source_slot_shapes = []
    used_native_slots = set()
    for slot in expected_slots:
        target = polygon_from_ring(slot["ring"])
        remaining = [p for p in source_slots if p["id"] not in used_native_slots]
        match, delta = nearest(target, remaining)
        if match:
            used_native_slots.add(match["id"])
            source_slot_shapes.append(match["geometry"])
        source_slot_checks.append({"id": slot["id"], "present": match is not None,
                                  "native_id": match["id"] if match else None,
                                  "hausdorff_mm": rounded(delta) if delta is not None else None,
                                  "geometry_width_mm": rounded(slot.get("width_mm", design["parameters"]["slot_width_mm"])),
                                  "native_path_vertex_count": match["vertex_count"] if match else None,
                                  "explicitly_closed": match["explicitly_closed"] if match else False})

    # Manufacturing ZIP is the evidence for actual exported holes, route paths,
    # and silkscreen, not merely the intended geometry.
    _, npth = parse_drill(members["Drill_NPTH_Through.DRL"])
    star_expected_native = [(h["center"][0], PANEL_SIZE - h["center"][1]) for h in expected_holes]
    gerber_star_hits = [h for h in npth if abs(h["diameter_mm"] - 0.8) <= 0.005]
    drill_checks = []
    used_hits = set()
    gerber_hole_geoms = []
    for design_hole, native_center in zip(expected_holes, star_expected_native):
        choices = [(math.dist(native_center, h["center_native_mm"]), i, h)
                   for i, h in enumerate(gerber_star_hits) if i not in used_hits]
        if choices:
            delta, idx, hit = min(choices)
            used_hits.add(idx)
            geom = circle(hit["center_native_mm"], hit["diameter_mm"])
            gerber_hole_geoms.append(geom)
            drill_checks.append({"id": design_hole["id"], "present": True,
                                 "diameter_mm": rounded(hit["diameter_mm"]),
                                 "center_error_mm": rounded(delta),
                                 "diameter_error_mm": rounded(abs(hit["diameter_mm"] - design_hole["diameter_mm"]))})
        else:
            drill_checks.append({"id": design_hole["id"], "present": False})

    _, gko_paths = parse_gerber_paths(members["Gerber_BoardOutlineLayer.GKO"])
    route_candidates = []
    for index, path in enumerate(gko_paths):
        if len(path) < 4:
            continue
        pts = path if path[0] == path[-1] else [*path, path[0]]
        poly = Polygon(pts)
        if poly.is_valid and poly.area > 0:
            route_candidates.append({"id": index, "geometry": poly})
    gerber_slot_checks = []
    gerber_slot_geoms = []
    used_routes = set()
    for slot in expected_slots:
        target = polygon_from_ring(slot["ring"], y_reflect=True)
        choices = [(target.hausdorff_distance(r["geometry"]), r["id"], r)
                   for r in route_candidates if r["id"] not in used_routes]
        if choices:
            delta, _, found = min(choices)
            used_routes.add(found["id"])
            gerber_slot_geoms.append(found["geometry"])
            gerber_slot_checks.append({"id": slot["id"], "present": True, "gko_path_index": found["id"],
                                       "hausdorff_mm": rounded(delta),
                                       "actual_bounds_native_mm": [rounded(v) for v in found["geometry"].bounds],
                                       "area_mm2": rounded(found["geometry"].area),
                                       "explicitly_closed": (len(gko_paths[found["id"]]) > 2
                                                             and gko_paths[found["id"]][0] == gko_paths[found["id"]][-1])})
        else:
            gerber_slot_checks.append({"id": slot["id"], "present": False})

    # Optical window coverage is the union of the manufactured star bores and
    # routed slot contours compared with the intended 19-aperture union.
    expected_window_shapes = [circle(h["center"], h["diameter_mm"]) for h in expected_holes]
    expected_window_shapes += [polygon_from_ring(s["ring"]) for s in expected_slots]
    actual_window_shapes = gerber_hole_geoms + gerber_slot_geoms
    expected_window = unary_union(expected_window_shapes)
    # Reflect actual Gerber windows back into the geometry's Y-down frame.
    def flip_geom_y(g):
        from shapely.affinity import scale
        flipped = scale(g, xfact=1, yfact=-1, origin=(0, PANEL_SIZE / 2))
        return flipped
    actual_window = unary_union([flip_geom_y(g) for g in actual_window_shapes]) if actual_window_shapes else Polygon()
    symmetric_area = expected_window.symmetric_difference(actual_window).area if actual_window else None
    coverage_ratio = (expected_window.intersection(actual_window).area / expected_window.area
                      if actual_window and expected_window.area else 0.0)

    def flip_geom_y(geom):
        return scale(geom, xfact=1, yfact=-1, origin=(0, PANEL_SIZE / 2))

    actual_window_panel = unary_union([flip_geom_y(g) for g in actual_window_shapes]) if actual_window_shapes else Polygon()
    hole_contour_errors = []
    for expected_hole, actual_hole in zip(expected_holes, gerber_hole_geoms):
        expected_shape = circle(expected_hole["center"], expected_hole["diameter_mm"])
        hole_contour_errors.append(expected_shape.hausdorff_distance(flip_geom_y(actual_hole)))
    slot_contour_errors = [r["hausdorff_mm"] for r in gerber_slot_checks if r.get("present")]
    actual_contour_errors = hole_contour_errors + slot_contour_errors
    max_actual_contour_error = max(actual_contour_errors, default=None)
    expected_aperture_perimeter_mm = sum(g.length for g in expected_window_shapes)
    area_delta_budget_mm2 = expected_aperture_perimeter_mm * APERTURE_CONTOUR_TOLERANCE_MM
    sagittarius_outer = polygon_from_ring(board["outer_ring"])
    connected_material = sagittarius_outer.difference(actual_window_panel) if actual_window_panel else Polygon()

    def component_count(geom):
        if geom.is_empty:
            return 0
        if geom.geom_type == "Polygon":
            return 1
        if hasattr(geom, "geoms"):
            return sum(component_count(g) for g in geom.geoms)
        return 0

    material_components = component_count(connected_material)

    # Project manufactured apertures through the spacer windows. The
    # Sagittarius artwork is viewed from its outside-back face, so mirror X in
    # assembly-local coordinates before comparing the actual clear apertures.
    projection_source = unary_union(actual_window_shapes) if actual_window_shapes else Polygon()
    projection_panel = flip_geom_y(projection_source) if projection_source else Polygon()
    sag_cx, sag_cy = board["center"]
    projection_local = translate(projection_panel, xoff=-sag_cx, yoff=-sag_cy)
    projection_mirror_x = scale(projection_local, xfact=-1, yfact=1, origin=(0, 0)) if projection_local else Polygon()
    projection_checks = []
    for spacer in [b for b in design["boards"] if b.get("id") in ("spacer2", "spacer4")]:
        spacer_center = spacer["center"]
        window_data = next((c for c in spacer.get("cutouts", []) if c.get("id") == "inner_window"), None)
        if not window_data:
            projection_checks.append({"spacer": spacer["id"], "window_present": False, "pass": False})
            continue
        window_panel = polygon_from_ring(window_data["ring"])
        window_local = translate(window_panel, xoff=-spacer_center[0], yoff=-spacer_center[1])
        coverage = (projection_mirror_x.intersection(window_local).area / projection_mirror_x.area
                    if projection_mirror_x.area else 0.0)
        outside_area = projection_mirror_x.difference(window_local).area
        min_edge_gap = projection_mirror_x.distance(window_local.boundary) if projection_mirror_x else None
        projection_checks.append({"spacer": spacer["id"], "window_present": True,
                                  "window_across_flats_mm": design["parameters"]["spacer_window_across_flats_mm"],
                                  "projection_x_mirrored": True,
                                  "projection_coverage_ratio": rounded(coverage),
                                  "aperture_area_outside_window_mm2": rounded(outside_area),
                                  "minimum_projected_aperture_to_window_edge_mm": rounded(min_edge_gap) if min_edge_gap is not None else None,
                                  "pass": coverage >= 0.999 and outside_area <= 0.01 and min_edge_gap is not None and min_edge_gap >= 0})

    # Geometric webs use manufactured drill and GKO geometry in native Gerber
    # coordinates so all clearances refer to actual exported paths.
    aperture_actual = gerber_hole_geoms + gerber_slot_geoms
    star_slot_webs, slot_slot_webs = [], []
    for i, hole in enumerate(gerber_hole_geoms):
        for j, slot in enumerate(gerber_slot_geoms):
            star_slot_webs.append((hole.distance(slot), i, j))
    for i in range(len(gerber_slot_geoms)):
        for j in range(i + 1, len(gerber_slot_geoms)):
            slot_slot_webs.append((gerber_slot_geoms[i].distance(gerber_slot_geoms[j]), i, j))
    min_star_slot = min(star_slot_webs, default=(None, None, None))
    min_slot_slot = min(slot_slot_webs, default=(None, None, None))

    # Match the complete artwork path set to native source and exported silk.
    art_paths = art["sagittarius_silkscreen"]
    cx, cy = board["center"]
    expected_silk = []
    for item in art_paths:
        points = [(cx + p[0], PANEL_SIZE - (cy + p[1])) for p in item["points"]]
        if item.get("closed") and points[0] != points[-1]:
            points.append(points[0])
        line = LineString(points)
        expected_silk.append({"id": item["id"], "width_mm": item["width_mm"],
                              "closed": item.get("closed", False), "line": line,
                              "stroke": line.buffer(item["width_mm"] / 2, cap_style="round", join_style="round")})
    native_silk_matches = []
    used_native_silk = set()
    for item in expected_silk:
        candidates = [s for s in silk_source if s["id"] not in used_native_silk]
        if candidates:
            match = min(candidates, key=lambda s: item["line"].hausdorff_distance(s["line"]))
            err = item["line"].hausdorff_distance(match["line"])
            used_native_silk.add(match["id"])
            native_silk_matches.append({"id": item["id"], "present": True,
                                        "native_id": match["id"], "native_layer_id": match["layer_id"],
                                        "hausdorff_mm": rounded(err),
                                        "stroke_width_error_mm": rounded(abs(item["width_mm"] - match["width_mm"]))})
        else:
            native_silk_matches.append({"id": item["id"], "present": False})

    silk_gerber_members = [n for n in ("Gerber_TopSilkscreenLayer.GTO", "Gerber_BottomSilkscreenLayer.GBO") if n in members]
    silk_member_scores = []
    silk_geometries_by_member = {}
    for member in silk_gerber_members:
        _, paths = parse_gerber_paths(members[member])
        strokes = parse_gerber_strokes(members[member])
        silk_geometries_by_member[member] = strokes
        score = 0
        used_stroke_indices = set()
        for item in expected_silk:
            choices = [(item["stroke"].hausdorff_distance(s["geometry"]), i)
                       for i, s in enumerate(strokes) if i not in used_stroke_indices]
            if choices:
                delta, idx = min(choices)
                if delta <= MATCH_TOLERANCE_MM:
                    score += 1
                    used_stroke_indices.add(idx)
        silk_member_scores.append({"member": member, "D02_path_count": len(paths),
                                   "stroke_object_count": len(strokes), "art_paths_matched": score})
    selected_silk = max(silk_member_scores, key=lambda r: r["art_paths_matched"], default=None)
    selected_member = selected_silk["member"] if selected_silk else None
    actual_silk_strokes = silk_geometries_by_member.get(selected_member, []) if selected_member else []
    silk_gerber_matches = []
    matched_gerber_strokes = []
    used_gerber_strokes = set()
    for item in expected_silk:
        remaining = [(i, s) for i, s in enumerate(actual_silk_strokes) if i not in used_gerber_strokes]
        if remaining:
            idx, match = min(remaining, key=lambda pair: item["stroke"].hausdorff_distance(pair[1]["geometry"]))
            err = item["stroke"].hausdorff_distance(match["geometry"])
            if err <= MATCH_TOLERANCE_MM:
                used_gerber_strokes.add(idx)
                matched_gerber_strokes.append(match)
            silk_gerber_matches.append({"id": item["id"], "present": err <= MATCH_TOLERANCE_MM,
                                        "hausdorff_mm": rounded(err),
                                        "actual_width_mm": rounded(match["width_mm"])})
        else:
            silk_gerber_matches.append({"id": item["id"], "present": False})
    if gerber_slot_geoms and gerber_hole_geoms:
        window_union_native = unary_union(gerber_slot_geoms + gerber_hole_geoms)
        clearance_rows = []
        for item in matched_gerber_strokes:
            gap = item["geometry"].distance(window_union_native)
            clearance_rows.append(gap)
        silk_min_clearance = min(clearance_rows, default=None)
    else:
        silk_min_clearance = None

    slot_lengths = []
    for edge in design["constellation"]["edges"]:
        slot_lengths.append({"id": edge["id"], "centerline_mm": rounded(edge["centerline_length_mm"]),
                             "overall_mm": rounded(edge["overall_length_mm"]),
                             "width_mm": design["parameters"]["slot_width_mm"]})
    native_silkscreen_pass = (len(art_paths) == 96
                              and len(native_silk_matches) == 96
                              and all(m.get("present") and m.get("hausdorff_mm", 99) <= MATCH_TOLERANCE_MM
                                      and m.get("stroke_width_error_mm", 99) <= MATCH_TOLERANCE_MM
                                      for m in native_silk_matches))
    native_apertures_pass = (len(source_star_pads) == len(expected_holes) == 8
                             and all(r.get("present") and r.get("center_error_mm", 99) <= MATCH_TOLERANCE_MM
                                     and r.get("diameter_error_mm", 99) <= MATCH_TOLERANCE_MM
                                     and r.get("native_pad_num", "").startswith("HIP_")
                                     and r.get("round_hole_shape_pass") and r.get("plated") is False
                                     for r in hole_source_checks)
                             and len(source_slot_checks) == 11 and len(used_native_slots) == 11
                             and all(r["present"] and r["explicitly_closed"] and r["hausdorff_mm"] <= APERTURE_CONTOUR_TOLERANCE_MM for r in source_slot_checks))
    native_pass = native_apertures_pass and native_silkscreen_pass
    gerber_pass = (len(drill_checks) == 8 and all(r.get("present") and r["center_error_mm"] <= MATCH_TOLERANCE_MM
                                                   and r["diameter_error_mm"] <= MATCH_TOLERANCE_MM for r in drill_checks)
                   and len(gerber_slot_checks) == 11 and len(used_routes) == 11
                   and all(r["present"] and r["explicitly_closed"] and r["hausdorff_mm"] <= APERTURE_CONTOUR_TOLERANCE_MM for r in gerber_slot_checks))
    web_pass = (min_star_slot[0] is not None and min_slot_slot[0] is not None
                and min_star_slot[0] >= WEB_MM and min_slot_slot[0] >= WEB_MM)
    silk_gerber_pass = (len(art_paths) == 96 and selected_silk is not None
                        and selected_silk["art_paths_matched"] == 96
                        and silk_min_clearance is not None and silk_min_clearance >= SILK_CLEARANCE_MM)
    silk_pass = native_silkscreen_pass and silk_gerber_pass
    shortest_slot = min(design["constellation"]["edges"], key=lambda e: e["overall_length_mm"])
    # Rounded polygon chords in the 1 mm routed-slot contours create a small
    # area delta despite sub-0.01 mm boundary agreement; use the Hausdorff
    # checks above as the shape tolerance and a 0.5% union-area guard here.
    window_coverage_pass = (coverage_ratio >= 0.995 and symmetric_area is not None
                            and symmetric_area <= area_delta_budget_mm2
                            and max_actual_contour_error is not None
                            and max_actual_contour_error <= APERTURE_CONTOUR_TOLERANCE_MM)
    assembly_projection_pass = bool(projection_checks) and all(c.get("pass") for c in projection_checks)

    report = {
        "scope": "Read-only audit of Sagittarius geometry against the actual native panel source and manufacturing ZIP. This does not replace supplier CAM approval.",
        "inputs": {
            "geometry_sha256": sha256(geometry_bytes), "artwork_sha256": sha256(artwork_bytes),
            "geometry_semantic_sha256": semantic_sha256(design), "artwork_semantic_sha256": semantic_sha256(art),
            "native_panel_sha256": sha256(native_bytes), "manufacturing_zip_sha256": sha256(zip_bytes),
            "manufacturing_zip_bytes": len(zip_bytes), "zip_crc_error_member": zip_bad_member,
            "zip_members": sorted(members), "native_coordinate_conversion": "mm = mil × 0.0254; design_panel_y = 100 − native_y_mm",
            "gerber_coordinate_conversion": "Native and Gerber use the same upward Y coordinates; design_panel_y = 100 − Gerber_y_mm"},
        "geometry": {"sagittarius_board_center_panel_mm": board["center"],
                     "expected_star_count": len(expected_holes), "expected_slot_count": len(expected_slots),
                     "expected_slot_width_mm": design["parameters"]["slot_width_mm"],
                     "slots": slot_lengths},
        "native_source": {"star_holes": hole_source_checks, "star_holes_present": len(source_star_pads),
                          "slots": source_slot_checks, "layer11_slot_polygon_count": len(source_slots),
                          "silkscreen_native_path_candidates": len(silk_source),
                          "silkscreen_art_matches": native_silk_matches,
                          "apertures_match_geometry": native_apertures_pass,
                          "all_96_silkscreen_paths_match": native_silkscreen_pass,
                          "source_face_pass": native_pass},
        "manufacturing_export": {"npth_tool_sizes_mm": parse_drill(members["Drill_NPTH_Through.DRL"])[0],
                                 "star_drills": drill_checks, "npth_0_8_count": len(gerber_star_hits),
                                 "gko_slot_contours": gerber_slot_checks,
                                 "gko_paths_matched": len(used_routes),
                                 "aperture_geometry_matches": gerber_pass,
                                 "optical_window_coverage": {"expected_aperture_count": len(expected_window_shapes),
                                                              "manufactured_aperture_count": len(actual_window_shapes),
                                                              "intersection_over_expected_area": rounded(coverage_ratio),
                                                              "symmetric_difference_area_mm2": rounded(symmetric_area) if symmetric_area is not None else None,
                                                              "expected_aperture_perimeter_mm": rounded(expected_aperture_perimeter_mm),
                                                              "area_difference_budget_mm2": rounded(area_delta_budget_mm2),
                                                              "max_actual_boundary_hausdorff_mm": rounded(max_actual_contour_error) if max_actual_contour_error is not None else None,
                                                              "boundary_tolerance_mm": APERTURE_CONTOUR_TOLERANCE_MM,
                                                              "pass": window_coverage_pass}},
        "assembly_projection": {"source_face": "Sagittarius outside-back view",
                                "mirror": "X coordinate mirrored in assembly-local coordinates",
                                "spacer_window_checks": projection_checks,
                                "pass": assembly_projection_pass,
                                "note": "The actual exported aperture union is projected through the 30 mm rounded windows after assembly-local X mirroring."},
        "manufactured_webs": {"minimum_star_to_slot_mm": rounded(min_star_slot[0]) if min_star_slot[0] is not None else None,
                              "star_slot_pair_indices": min_star_slot[1:],
                              "minimum_slot_to_slot_mm": rounded(min_slot_slot[0]) if min_slot_slot[0] is not None else None,
                              "slot_pair_indices": min_slot_slot[1:], "required_mm": WEB_MM,
                              "pass": web_pass,
                              "limitation": "Webs are computed from the exported GKO cutout contours and NPTH drills; supplier routing compensation and actual cutter behavior are not represented."},
        "material_connectivity": {"reference_octagon_minus_manufactured_apertures_component_count": material_components,
                                  "pass": material_components == 1,
                                  "note": "Connected-material check subtracts the manufactured apertures from the Sagittarius board outline polygon."},
        "silkscreen": {"expected_art_path_count": len(art_paths),
                       "artwork_categories": {"latin_and_outer_keyline": sum(p["id"].startswith(("latin_", "sagittarius_outer")) for p in art_paths),
                                             "star_rims": sum(p["id"].startswith("star_rim_") for p in art_paths),
                                             "connector_segments": sum(p["id"].startswith("star_link_") for p in art_paths)},
                       "gerber_member_scores": silk_member_scores, "selected_member": selected_member,
                       "actual_path_objects": len(actual_silk_strokes),
                       "matched_art_path_count": sum(m["present"] for m in silk_gerber_matches),
                       "path_matches": silk_gerber_matches,
                       "minimum_edge_clearance_to_apertures_mm": rounded(silk_min_clearance) if silk_min_clearance is not None else None,
                       "required_edge_clearance_mm": SILK_CLEARANCE_MM,
                       "native_all_paths_match": native_silkscreen_pass,
                       "gerber_all_paths_and_clearance_pass": silk_gerber_pass,
                       "pass": silk_pass,
                       "limitation": "Gerber stroke reconstruction uses round-buffered centerline paths; generated line-cap geometry approximates the CAM raster. A supplier preview remains the final check."},
        "summary": {"native_apertures_pass": native_apertures_pass, "export_apertures_pass": gerber_pass,
                    "native_aperture_geometry_pass": native_apertures_pass,
                    "native_silkscreen_pass": native_silkscreen_pass,
                    "actual_webs_pass": web_pass, "window_coverage_pass": window_coverage_pass,
                    "actual_silkscreen_pass": silk_pass,
                    "material_connectivity_pass": material_components == 1,
                    "assembly_projection_pass": assembly_projection_pass,
                    "all_checks_pass": native_pass and gerber_pass and web_pass and window_coverage_pass
                    and silk_pass and material_components == 1 and assembly_projection_pass},
        "manufacturing_limits": [
            f"The shortest routed slot {shortest_slot['id']} is {shortest_slot['overall_length_mm']:.3f} mm end to end ({shortest_slot['centerline_length_mm']:.3f} mm centerline travel); supplier CAM must confirm it can be routed with the nominal {design['parameters']['slot_width_mm']:.3f} mm cutter.",
            "This is a file-level geometry audit. It does not establish color-silkscreen process coverage, optical transmission, or sample performance."]}
    with REPORT.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"report": str(REPORT), "native_sha256": report["inputs"]["native_panel_sha256"],
                      "gerber_zip_sha256": report["inputs"]["manufacturing_zip_sha256"],
                      "native_apertures_pass": native_apertures_pass, "gerber_apertures_pass": gerber_pass,
                      "webs_pass": web_pass, "window_coverage_pass": report["summary"]["window_coverage_pass"],
                      "silkscreen_pass": silk_pass, "silkscreen_member": selected_member}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
