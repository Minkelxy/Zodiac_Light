#!/usr/bin/env python3
"""Offline source-level mechanical audit for the Leo and Sagittarius face panels.

Reads only saved JSON geometry, saved EDA source snapshots and cover manifests.
Writes only variants/common/face-geometry-audit.json; it does not open or edit a
live EDA project or any existing audit snapshot.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ROOT / "variants"
COMMON = VARIANTS / "common"
NATIVE = COMMON / "eda" / "native"
LEO_SOURCE = NATIVE / "snake-leo-panel-source.jsonl"
SAG_SOURCE = NATIVE / "horse-sagittarius-panel-source.jsonl"
LEO_GERBER = VARIANTS / "snake-leo" / "manufacturing-draft" / "snake-leo-gerber.zip"
SAG_GERBER = VARIANTS / "horse-sagittarius" / "manufacturing-draft" / "horse-sagittarius-gerber.zip"
LEO_GEOMETRY = VARIANTS / "snake-leo" / "leo-geometry.json"
LEO_INTEGRATION = VARIANTS / "snake-leo" / "eda-integration.json"
DESIGN = ROOT / "geometry" / "design.json"
LEO_MANIFEST = VARIANTS / "snake-leo" / "artwork" / "manifest.json"
SAG_MANIFEST = VARIANTS / "horse-sagittarius" / "artwork" / "manifest.json"
REPORT = COMMON / "face-geometry-audit.json"

MIL_TO_MM = 0.0254
MATCH_TOLERANCE_MM = 0.01
HOLE_DIAMETER_TOLERANCE_MM = 0.005
POLYGON_HAUSDORFF_TOLERANCE_MM = 0.01
WEB_ACCEPTANCE_MM = 1.0
PANEL_SIDE_MM = 100.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def round_mm(value: float | None, digits: int = 6):
    return round(value, digits) if value is not None else None


def read_source(path: Path) -> list[tuple[dict, dict]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "||" not in line:
            continue
        meta_raw, object_raw = line.split("||", 1)
        try:
            meta = json.loads(meta_raw)
            obj = json.loads(object_raw.rstrip("|\r\n"))
        except (json.JSONDecodeError, TypeError):
            continue
        meta["_source_line"] = line_number
        records.append((meta, obj))
    return records


def path_polygon(obj: dict, *, reflect_y: bool = False) -> Polygon:
    raw = obj.get("path") or []
    numbers = [value for value in raw if isinstance(value, (int, float))]
    if len(numbers) < 6 or len(numbers) % 2:
        return Polygon()
    points = []
    for i in range(0, len(numbers), 2):
        x, y = numbers[i] * MIL_TO_MM, numbers[i + 1] * MIL_TO_MM
        points.append((x, PANEL_SIDE_MM - y if reflect_y else y))
    if points and points[0] != points[-1]:
        points.append(points[0])
    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon


def capsule(start: tuple[float, float], end: tuple[float, float], width: float) -> Polygon:
    return LineString([start, end]).buffer(width / 2, cap_style="round", join_style="round", quad_segs=32)


def nearest_distinct(expected: list[tuple[str, Polygon]], actual: list[tuple[str, Polygon]]) -> list[dict]:
    pairs = []
    for target_id, target in expected:
        for native_id, geometry in actual:
            if not target.is_empty and not geometry.is_empty:
                pairs.append((target.hausdorff_distance(geometry), target_id, native_id, target, geometry))
    pairs.sort(key=lambda row: row[0])
    used_targets, used_native, matches = set(), set(), []
    for error, target_id, native_id, target, geometry in pairs:
        if target_id in used_targets or native_id in used_native:
            continue
        used_targets.add(target_id)
        used_native.add(native_id)
        matches.append({"source_slot_id": target_id, "native_id": native_id,
                        "hausdorff_error_mm": error, "area_difference_mm2": abs(target.area - geometry.area),
                        "expected_area_mm2": target.area, "native_area_mm2": geometry.area})
    return sorted(matches, key=lambda item: item["source_slot_id"])


def web_summary(apertures: list[tuple[str, Polygon]]) -> dict:
    candidates = []
    for index, (name, shape) in enumerate(apertures):
        for other_name, other_shape in apertures[index + 1:]:
            candidates.append((shape.distance(other_shape), name, other_name))
    web, first, second = min(candidates) if candidates else (None, None, None)
    return {
        "minimum_clear_material_web_mm": round_mm(web),
        "limiting_apertures": [first, second] if first is not None else [],
        "minimum_web_acceptance_mm": WEB_ACCEPTANCE_MM,
        "minimum_web_pass": web is not None and web + 1e-8 >= WEB_ACCEPTANCE_MM,
        "apertures_used": len(apertures),
    }


def parse_npth(data: bytes) -> tuple[list[dict], dict[str, float]]:
    text = data.decode("ascii", "replace")
    tools = {match.group(1): float(match.group(2)) for match in re.finditer(r"T(\d+)C([0-9.]+)", text)}
    active, holes = None, []
    for line in text.splitlines():
        match = re.fullmatch(r"T(\d+)", line.strip())
        if match:
            active = match.group(1)
            continue
        match = re.match(r"X(-?[0-9.]+)Y(-?[0-9.]+)", line.strip())
        if match and active in tools:
            holes.append({"diameter_mm": tools[active], "center_mm": [float(match.group(1)), float(match.group(2))], "tool": active})
    return holes, tools


def parse_gko_polygons(data: bytes) -> list[tuple[int, Polygon]]:
    text = data.decode("ascii", "replace")
    paths, current = [], []
    for x, y, op_text in re.findall(r"X(-?\d+)Y(-?\d+)D0([123])\*", text):
        point, op = (int(x) / 1_000_000, int(y) / 1_000_000), int(op_text)
        if op == 2:
            if len(current) > 1:
                paths.append(current)
            current = [point]
        elif op == 1 and current:
            current.append(point)
        elif op == 3 and current:
            paths.append(current)
            current = []
    if len(current) > 1:
        paths.append(current)
    polygons = []
    for index, points in enumerate(paths):
        if len(points) < 4:
            continue
        ring = points if points[0] == points[-1] else [*points, points[0]]
        polygon = Polygon(ring)
        if polygon.is_valid and polygon.area > 0:
            polygons.append((index, polygon))
    return polygons


def audit_gerber_export(zip_path: Path, variant: str, expected_holes: list[tuple[str, tuple[float, float]]],
                        expected_slots: list[tuple[str, Polygon]]) -> dict:
    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"Corrupt archive member {bad_member} in {zip_path}")
        npth_data = archive.read("Drill_NPTH_Through.DRL")
        gko_data = archive.read("Gerber_BoardOutlineLayer.GKO")
    npth, tool_diameters = parse_npth(npth_data)
    hole_candidates = [hole for hole in npth if abs(hole["diameter_mm"] - 0.8) <= HOLE_DIAMETER_TOLERANCE_MM]
    hole_checks, drill_apertures, used_holes = [], [], set()
    for ident, target in expected_holes:
        choices = [(math.dist(target, hole["center_mm"]), index, hole)
                   for index, hole in enumerate(hole_candidates) if index not in used_holes]
        if not choices:
            hole_checks.append({"id": ident, "present": False})
            continue
        error, index, hole = min(choices)
        used_holes.add(index)
        aperture = Point(*hole["center_mm"]).buffer(hole["diameter_mm"] / 2, quad_segs=64)
        drill_apertures.append((ident, aperture))
        hole_checks.append({"id": ident, "present": True, "tool": hole["tool"],
                            "diameter_mm": round_mm(hole["diameter_mm"]),
                            "center_error_mm": round_mm(error),
                            "center_pass": error <= MATCH_TOLERANCE_MM,
                            "diameter_pass": abs(hole["diameter_mm"] - 0.8) <= HOLE_DIAMETER_TOLERANCE_MM})

    route_candidates = parse_gko_polygons(gko_data)
    pairings = []
    for slot_id, target in expected_slots:
        for native_index, actual in route_candidates:
            pairings.append((target.hausdorff_distance(actual), slot_id, native_index, target, actual))
    pairings.sort(key=lambda item: item[0])
    used_slots, used_routes, slot_checks, route_apertures = set(), set(), [], []
    for error, slot_id, native_index, target, actual in pairings:
        if slot_id in used_slots or native_index in used_routes:
            continue
        used_slots.add(slot_id)
        used_routes.add(native_index)
        route_apertures.append((slot_id, actual))
        slot_checks.append({"id": slot_id, "present": True, "gko_path_index": native_index,
                            "polygon_hausdorff_error_mm": round_mm(error),
                            "polygon_area_difference_mm2": round_mm(abs(target.area - actual.area)),
                            "polygon_match_pass": error <= POLYGON_HAUSDORFF_TOLERANCE_MM})
    for slot_id, _ in expected_slots:
        if slot_id not in used_slots:
            slot_checks.append({"id": slot_id, "present": False})
    slot_checks.sort(key=lambda item: item["id"])
    slot_apertures = [(item["id"], next(geometry for ident, geometry in route_apertures if ident == item["id"]))
                      for item in slot_checks if item.get("present")]
    web = web_summary(drill_apertures + slot_apertures)
    holes_pass = len(hole_candidates) == len(expected_holes) and len(used_holes) == len(expected_holes) and all(
        item.get("present") and item["center_pass"] and item["diameter_pass"] for item in hole_checks)
    slots_pass = len(used_routes) == len(expected_slots) and all(item.get("present") and item["polygon_match_pass"] for item in slot_checks)
    passed = holes_pass and slots_pass and web["minimum_web_pass"]
    return {
        "status": "pass" if passed else "fail", "gerber_zip": str(zip_path.relative_to(ROOT)),
        "gerber_zip_sha256": sha(zip_path), "npth_member_sha256": hashlib.sha256(npth_data).hexdigest(),
        "gko_member_sha256": hashlib.sha256(gko_data).hexdigest(), "npth_tool_diameters_mm": tool_diameters,
        "npth_0_8mm_holes": {"expected": len(expected_holes), "candidate_count": len(hole_candidates), "matched": len(used_holes), "checks": hole_checks},
        "gko_cutout_routes": {"expected": len(expected_slots), "candidate_closed_polygons": len(route_candidates),
                              "matched": len(used_routes), "checks": slot_checks},
        "exported_geometry_material_web": web,
        "scope_note": "Matches NPTH drill coordinates and closed GKO route contours to intended face apertures; does not infer additional CAM/manufacturing properties.",
    }


def audit_leo() -> dict:
    geometry_doc = json.loads(LEO_GEOMETRY.read_text(encoding="utf-8"))
    integration = json.loads(LEO_INTEGRATION.read_text(encoding="utf-8"))
    constellation = geometry_doc["constellation"]
    records = read_source(LEO_SOURCE)
    records_by_id = {meta.get("id"): (meta, obj) for meta, obj in records}
    star_native_ids = {int(item["hip"]): item["id"] for item in integration["created"]["stars"]}
    slot_native_ids = {item["slot"]: item["id"] for item in integration["created"]["slots"]}

    star_checks, apertures = [], []
    for star in constellation["stars"]:
        hip = int(star["hip"])
        native_id = star_native_ids.get(hip)
        pair = records_by_id.get(native_id)
        local_x, local_y = star["center_mm"]
        target_x = (79.5 + local_x) / MIL_TO_MM
        target_y = (23.5 - local_y) / MIL_TO_MM
        if pair is None:
            star_checks.append({"hip": hip, "native_id": native_id, "present": False})
            continue
        _, obj = pair
        hole = obj.get("hole") or {}
        center_error = math.dist((target_x, target_y), (float(obj.get("centerX", 0)), float(obj.get("centerY", 0)))) * MIL_TO_MM
        diameter = float(hole.get("width", 0)) * MIL_TO_MM
        height = float(hole.get("height", 0)) * MIL_TO_MM
        circle = Point(float(obj["centerX"]) * MIL_TO_MM, float(obj["centerY"]) * MIL_TO_MM).buffer(diameter / 2, quad_segs=64)
        apertures.append((f"HIP_{hip}", circle))
        star_checks.append({
            "hip": hip, "native_id": native_id, "native_pad_num": obj.get("num"), "present": True,
            "native_center_mil": [obj.get("centerX"), obj.get("centerY")],
            "center_error_mm": round_mm(center_error), "hole_type": hole.get("holeType"),
            "diameter_mm": round_mm(diameter), "height_mm": round_mm(height), "plated": obj.get("plated"),
            "center_pass": center_error <= MATCH_TOLERANCE_MM,
            "round_0_8mm_npth_pass": hole.get("holeType") == "ROUND" and obj.get("plated") is False
                and abs(diameter - 0.8) <= HOLE_DIAMETER_TOLERANCE_MM
                and abs(height - 0.8) <= HOLE_DIAMETER_TOLERANCE_MM,
        })

    leo_slots, actual_slots = [], []
    for slot in constellation["physical_slots"]:
        slot_id = slot["id"]
        native_id = slot_native_ids.get(slot_id)
        pair = records_by_id.get(native_id)
        start_x, start_y = slot["centerline_start"]
        end_x, end_y = slot["centerline_end"]
        expected = capsule((79.5 + start_x, 23.5 - start_y), (79.5 + end_x, 23.5 - end_y), slot["width_mm"])
        if pair is None:
            leo_slots.append({"source_slot_id": slot_id, "native_id": native_id, "present": False})
            continue
        _, obj = pair
        native = path_polygon(obj)
        error = expected.hausdorff_distance(native)
        width = float(obj.get("width", 0)) * MIL_TO_MM
        actual_slots.append((slot_id, native))
        apertures.append((slot_id, native))
        leo_slots.append({
            "source_slot_id": slot_id, "native_id": native_id, "present": True,
            "native_path_closed": bool(native.is_valid and native.area > 0),
            "native_path_points": len(native.exterior.coords) - 1 if not native.is_empty else 0,
            "nominal_slot_width_mm": slot["width_mm"], "native_polygon_object_width_mm": round_mm(width),
            "expected_polygon_area_mm2": round_mm(expected.area), "native_polygon_area_mm2": round_mm(native.area),
            "polygon_hausdorff_error_mm": round_mm(error),
            "polygon_match_pass": error <= POLYGON_HAUSDORFF_TOLERANCE_MM,
        })

    web = web_summary(apertures)
    expected_count = len(constellation["stars"])
    print_only_edges = constellation.get("print_only_edge_indices", [])
    all_checks_pass = (
        len(star_checks) == expected_count and all(item.get("present") and item["center_pass"] and item["round_0_8mm_npth_pass"] for item in star_checks)
        and len(leo_slots) == len(constellation["physical_slots"]) and all(item.get("present") and item["polygon_match_pass"] for item in leo_slots)
        and web["minimum_web_pass"]
    )
    return {
        "status": "pass" if all_checks_pass else "fail",
        "panel_source": str(LEO_SOURCE.relative_to(ROOT)), "panel_source_sha256": sha(LEO_SOURCE),
        "geometry_sha256": sha(LEO_GEOMETRY), "integration_map_sha256": sha(LEO_INTEGRATION),
        "native_orientation_transform": "x_mil=(79.5+localX_mm)/0.0254; y_mil=(23.5-localY_mm)/0.0254",
        "native_stars": {"expected": expected_count, "matched": sum(bool(x.get("present")) for x in star_checks),
                         "all_0_8mm_round_npth": all(x.get("round_0_8mm_npth_pass") for x in star_checks),
                         "checks": star_checks},
        "native_slots": {"expected": len(constellation["physical_slots"]), "matched": sum(bool(x.get("present")) for x in leo_slots),
                         "polygon_hausdorff_tolerance_mm": POLYGON_HAUSDORFF_TOLERANCE_MM, "checks": leo_slots},
        "logical_constellation_edges": len(constellation.get("logical_edges_all", [])),
        "print_only_edges_without_physical_slot": [
            {"edge_index": index, "hip_a": edge["hip_a"], "hip_b": edge["hip_b"]}
            for index in print_only_edges
            for edge in constellation.get("logical_edges_all", [])
            if constellation.get("logical_edges_all", []).index(edge) == index
        ],
        "native_mechanical_web": web,
    }


def audit_sagittarius(design: dict) -> dict:
    board = next(board for board in design["boards"] if board.get("id") == "sagittarius5")
    source = read_source(SAG_SOURCE)
    pads = {}
    polygons = []
    for meta, obj in source:
        if meta.get("type") == "PAD" and str(obj.get("num", "")).startswith("HIP_") and obj.get("hole"):
            pads[str(obj["num"]).upper()] = (meta, obj)
        if meta.get("type") == "POLY" and obj.get("layerId") == 11:
            polygons.append((meta.get("id"), path_polygon(obj, reflect_y=True)))

    hole_checks, apertures = [], []
    for hole in board["drills"]:
        ident = str(hole["id"]).upper()
        pair = pads.get(ident)
        expected_x, expected_y = hole["center"][0], PANEL_SIDE_MM - hole["center"][1]
        if pair is None:
            hole_checks.append({"id": ident, "present": False})
            continue
        _, obj = pair
        data = obj["hole"]
        center = (float(obj["centerX"]) * MIL_TO_MM, float(obj["centerY"]) * MIL_TO_MM)
        delta = math.dist((expected_x, expected_y), center)
        diameter = float(data.get("width", 0)) * MIL_TO_MM
        height = float(data.get("height", 0)) * MIL_TO_MM
        aperture = Point(*center).buffer(diameter / 2, quad_segs=64)
        apertures.append((ident, aperture))
        hole_checks.append({"id": ident, "present": True, "native_id": _["id"], "native_pad_num": obj.get("num"),
                            "center_error_mm": round_mm(delta), "diameter_mm": round_mm(diameter), "height_mm": round_mm(height),
                            "hole_type": data.get("holeType"), "plated": obj.get("plated"),
                            "center_pass": delta <= MATCH_TOLERANCE_MM,
                            "round_0_8mm_npth_pass": data.get("holeType") == "ROUND" and obj.get("plated") is False
                                and abs(diameter - 0.8) <= HOLE_DIAMETER_TOLERANCE_MM
                                and abs(height - 0.8) <= HOLE_DIAMETER_TOLERANCE_MM})

    expected_slots = [(str(slot["id"]), Polygon(slot["ring"])) for slot in board["cutouts"] if slot.get("type") == "constellation_slot"]
    matches = nearest_distinct(expected_slots, polygons)
    match_by_id = {item["source_slot_id"]: item for item in matches}
    slot_checks = []
    for slot_id, expected in expected_slots:
        item = match_by_id.get(slot_id)
        if item:
            native = next(geometry for ident, geometry in polygons if ident == item["native_id"])
            apertures.append((slot_id, native))
            slot_checks.append({**item, "present": True, "polygon_hausdorff_error_mm": round_mm(item["hausdorff_error_mm"]),
                                "area_difference_mm2": round_mm(item["area_difference_mm2"]),
                                "polygon_match_pass": item["hausdorff_error_mm"] <= POLYGON_HAUSDORFF_TOLERANCE_MM,
                                "nominal_slot_width_mm": round_mm(next(s["width_mm"] for s in board["cutouts"] if str(s.get("id")) == slot_id))})
        else:
            slot_checks.append({"source_slot_id": slot_id, "present": False})

    web = web_summary(apertures)
    passed = (len(hole_checks) == 8 and all(x.get("present") and x["center_pass"] and x["round_0_8mm_npth_pass"] for x in hole_checks)
              and len(slot_checks) == 11 and all(x.get("present") and x["polygon_match_pass"] for x in slot_checks)
              and web["minimum_web_pass"])
    return {
        "status": "pass" if passed else "fail", "board_id": board["id"],
        "panel_source": str(SAG_SOURCE.relative_to(ROOT)), "panel_source_sha256": sha(SAG_SOURCE),
        "design_sha256": sha(DESIGN), "native_coordinates_to_design": "source x_mm unchanged; source y_mm reflects to design y_down as 100-sourceY_mm",
        "native_stars": {"expected": 8, "matched": sum(bool(x.get("present")) for x in hole_checks),
                         "all_0_8mm_round_npth": all(x.get("round_0_8mm_npth_pass") for x in hole_checks), "checks": hole_checks},
        "native_slots": {"expected": 11, "matched": sum(bool(x.get("present")) for x in slot_checks),
                         "candidate_layer_11_polygons": len(polygons), "polygon_hausdorff_tolerance_mm": POLYGON_HAUSDORFF_TOLERANCE_MM,
                         "checks": slot_checks},
        "native_mechanical_web": web,
    }


def audit_cover_sources() -> dict:
    manifests = {"snake_leo": json.loads(LEO_MANIFEST.read_text(encoding="utf-8")),
                 "horse_sagittarius": json.loads(SAG_MANIFEST.read_text(encoding="utf-8"))}
    integrations = {
        "snake_leo": VARIANTS / "snake-leo" / "artwork-eda-integration.json",
        "horse_sagittarius": VARIANTS / "horse-sagittarius" / "artwork-eda-integration.json",
    }
    checks = []
    expected_sources = [
        ("snake", ROOT / "artwork" / "reference-collection" / "talisman-single-ink-v1" / "snake-single-ink.png", manifests["snake_leo"]["input_sha256"]["approved_snake_single_ink_png"]),
        ("horse", ROOT / "artwork" / "reference-collection" / "talisman-single-ink-v1" / "horse-single-ink.png", manifests["horse_sagittarius"]["input_sha256"]["approved_horse_single_ink_png"]),
        ("Leo source SVG", VARIANTS / "snake-leo" / "leo-artwork.svg", manifests["snake_leo"]["input_sha256"]["leo_artwork_source_svg"]),
        ("Sagittarius B source SVG", ROOT / "artwork" / "star-style-study-v1" / "B-soft-type-day.svg", manifests["horse_sagittarius"]["input_sha256"]["sagittarius_B_soft_type_source_svg"]),
    ]
    for label, path, expected in expected_sources:
        current = sha(path)
        checks.append({"label": label, "path": str(path.relative_to(ROOT)), "sha256": current,
                       "manifest_sha256": expected, "unchanged_from_artwork_manifest": current == expected})
    cover_png_checks = []
    for key, manifest, folder in [
        ("snake_leo", manifests["snake_leo"], VARIANTS / "snake-leo" / "artwork"),
        ("horse_sagittarius", manifests["horse_sagittarius"], VARIANTS / "horse-sagittarius" / "artwork"),
    ]:
        for filename, details in manifest["files"].items():
            path = folder / filename
            current = sha(path)
            cover_png_checks.append({"variant": key, "file": filename, "sha256": current,
                                     "manifest_sha256": details["sha256"], "unchanged_from_render_manifest": current == details["sha256"]})
    placement_checks = []
    for key, path in integrations.items():
        integration = json.loads(path.read_text(encoding="utf-8"))
        manifest = manifests[key]
        created_by_id = {item.get("id"): item for item in integration.get("created", [])}
        for item in integration.get("actual", []):
            expected_hash = manifest["files"].get(item["fileName"], {}).get("sha256")
            created_record = created_by_id.get(item.get("id"), {})
            placement_checks.append({"variant": key, "native_id": item.get("id"), "file": item.get("fileName"),
                                     "rotation_degrees": item.get("rotation"), "mirror": item.get("mirror"),
                                     "native_blob_sha256": item.get("blob"),
                                     "import_input_sha256": created_record.get("inputSha256"),
                                     "matches_rendered_cover_png_sha256": created_record.get("inputSha256") == expected_hash,
                                     "unmirrored_zero_rotation": item.get("mirror") is False and item.get("rotation") == 0})
    all_pass = (all(x["unchanged_from_artwork_manifest"] for x in checks)
                and all(x["unchanged_from_render_manifest"] for x in cover_png_checks)
                and len(placement_checks) == 4
                and all(x["matches_rendered_cover_png_sha256"] and x["unmirrored_zero_rotation"] for x in placement_checks))
    return {"status": "pass" if all_pass else "fail", "original_art_inputs": checks,
            "four_cover_pngs": cover_png_checks, "native_cover_placements": placement_checks,
            "integration_hashes": {key: sha(path) for key, path in integrations.items()}}


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    leo_doc = json.loads(LEO_GEOMETRY.read_text(encoding="utf-8"))
    leo_constellation = leo_doc["constellation"]
    sag_board = next(board for board in design["boards"] if board.get("id") == "sagittarius5")
    leo_gerber = audit_gerber_export(
        LEO_GERBER,
        "snake-leo",
        [(f"HIP_{star['hip']}", (79.5 + star["center_mm"][0], 23.5 - star["center_mm"][1]))
         for star in leo_constellation["stars"]],
        [(slot["id"], capsule((79.5 + slot["centerline_start"][0], 23.5 - slot["centerline_start"][1]),
                               (79.5 + slot["centerline_end"][0], 23.5 - slot["centerline_end"][1]), slot["width_mm"]))
         for slot in leo_constellation["physical_slots"]],
    )
    sag_gerber = audit_gerber_export(
        SAG_GERBER,
        "horse-sagittarius",
        [(str(hole["id"]).upper(), (hole["center"][0], PANEL_SIDE_MM - hole["center"][1])) for hole in sag_board["drills"]],
        [(str(slot["id"]), Polygon([(x, PANEL_SIDE_MM - y) for x, y in slot["ring"]]))
         for slot in sag_board["cutouts"] if slot.get("type") == "constellation_slot"],
    )
    results = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "read-only audit of saved native source snapshots, source geometry and cover PNG hashes; no live project access",
        "leo": audit_leo(),
        "horse_sagittarius": audit_sagittarius(design),
        "gerber_exports": {"snake_leo": leo_gerber, "horse_sagittarius": sag_gerber},
        "cover_source_integrity": audit_cover_sources(),
        "tolerances": {"native_center_error_mm": MATCH_TOLERANCE_MM,
                       "hole_diameter_error_mm": HOLE_DIAMETER_TOLERANCE_MM,
                       "slot_polygon_hausdorff_mm": POLYGON_HAUSDORFF_TOLERANCE_MM,
                       "minimum_material_web_mm": WEB_ACCEPTANCE_MM},
    }
    overall = all(results[key]["status"] == "pass" for key in ("leo", "horse_sagittarius", "cover_source_integrity")) \
        and all(item["status"] == "pass" for item in results["gerber_exports"].values())
    results["status"] = "pass" if overall else "fail"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": results["status"], "report": str(REPORT),
                      "leo_minimum_web_mm": results["leo"]["native_mechanical_web"]["minimum_clear_material_web_mm"],
                      "sagittarius_minimum_web_mm": results["horse_sagittarius"]["native_mechanical_web"]["minimum_clear_material_web_mm"],
                      "leo_gerber_web_mm": results["gerber_exports"]["snake_leo"]["exported_geometry_material_web"]["minimum_clear_material_web_mm"],
                      "sagittarius_gerber_web_mm": results["gerber_exports"]["horse_sagittarius"]["exported_geometry_material_web"]["minimum_clear_material_web_mm"]}, ensure_ascii=False))
    if not overall:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
