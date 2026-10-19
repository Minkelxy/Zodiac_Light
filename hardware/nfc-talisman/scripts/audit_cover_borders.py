"""Independently audit imported border geometry and retained physical baselines.

This offline entry point reads saved files only. It does not generate artwork,
contact EasyEDA, or modify source/manufacturing manifests. Shapely is required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import GeometryCollection, Point, Polygon, box
from shapely.ops import unary_union

import check_standard_delivery as standard


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fingerprint(path):
    raw = path.read_bytes()
    return dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [polygon for part in geometry.geoms for polygon in polygons(part)]


def canonical_geometry(value):
    return unary_union([Polygon(item["exterior"], item["holes"]) for item in value["polygons"]])


def native_polygon(path, center):
    rings = []
    for contour in path:
        assert contour[2] == "L"
        numbers = contour[:2] + contour[3:]
        rings.append([(numbers[index] * .0254 - center[0] + 18.5,
                       center[1] + 18.5 - numbers[index + 1] * .0254)
                      for index in range(0, len(numbers), 2)])
    return Polygon(rings[0], rings[1:])


def almost_equal(left, right, tolerance=.001):
    if isinstance(left, dict):
        return isinstance(right, dict) and set(left) == set(right) and all(almost_equal(value, right[key], tolerance) for key, value in left.items())
    if isinstance(left, list):
        return isinstance(right, list) and len(left) == len(right) and all(almost_equal(a, b, tolerance) for a, b in zip(left, right))
    if type(left) in (float, int):
        return type(right) in (float, int) and math.isfinite(right) and abs(left - right) <= tolerance
    return left == right


def manufacturing_equal(before, after):
    """Compare saved-native manufacturing semantics despite regenerated IDs."""
    remaining = list(after.items())
    for (kind, ident), expected in before.items():
        def matches(item):
            (actual_kind, _), actual = item
            if kind != actual_kind:
                return False
            if not isinstance(expected, dict) or "path" not in expected:
                return almost_equal(expected, actual)
            if not almost_equal({key: value for key, value in expected.items() if key != "path"},
                                {key: value for key, value in actual.items() if key != "path"}):
                return False
            if kind == "POLY":
                return standard._contour_same(expected["path"], actual["path"])
            if kind == "FILL":
                return standard._polygon_same(expected["path"], actual["path"])
            return almost_equal(expected["path"], actual["path"])
        choices = [index for index, item in enumerate(remaining) if matches(item)]
        if not choices:
            return False, "Unmatched baseline primitive " + kind + " " + ident
        remaining.pop(choices[0])
    return not remaining, "Additional manufacturing primitives" if remaining else "One-to-one semantic match"


def audit(root):
    root = root.resolve()
    if (root / "hardware/nfc-talisman").is_dir():
        root = root / "hardware/nfc-talisman"
    project = root.parents[1]
    twelve = root / "variants/twelve-options"
    ordinary = root / standard.STANDARD
    design = load(twelve / "design-manifest.json")
    exported = load(twelve / "export-manifest.json")
    art_manifest = load(ordinary / "artwork/manifest.json")
    state = load(ordinary / "pcb-state.json")
    evidence = dict(schema_version=1, status="passed", read_only=True,
                    border_generator=design["border_generator"],
                    auditor=dict(path=Path(__file__).relative_to(project).as_posix(), **fingerprint(Path(__file__))),
                    inputs={}, covers={}, physical_retention={}, errors=[],
                    native_path_scope="Offline import contours; standard saved native sources also checked. Final delivery checkers bind all import contours to reopened sources and shared native archive.",
                    limitations=["Independent geometry evidence is separate from supplier CAM and physical sample acceptance.",
                                 "Clearance values describe the added border. Existing source animal fine tips remain subject to CAM review."])

    def input_file(path):
        evidence["inputs"][path.relative_to(root).as_posix()] = fingerprint(path)
        return path

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    input_file(twelve / "design-manifest.json")
    input_file(ordinary / "artwork/manifest.json")
    standard._check_border_generator(root, evidence["border_generator"])
    require(design["border_generator"] == art_manifest["border_generator"], "The two border source bindings differ")
    parameters = None
    half = 18.5
    corner = half * (math.sqrt(2) - 1)
    exact_board = Polygon([(half - corner, 0), (half + corner, 0), (37, half - corner),
                           (37, half + corner), (half + corner, 37), (half - corner, 37),
                           (0, half + corner), (0, half - corner)])
    bridges = unary_union([box(16.5, -1, 20.5, 2.3), box(16.5, 34.7, 20.5, 38),
                           box(-1, 16.5, 2.3, 20.5), box(34.7, 16.5, 38, 20.5)])
    drill_centers = [(x, y) for offset in (-1.44, -.72, 0, .72, 1.44)
                     for x, y in ((18.5 + offset, 0), (18.5 + offset, 37), (0, 18.5 + offset), (37, 18.5 + offset))]

    def cover(key, metadata, border_paths, art_paths, mask_paths, center, board):
        nonlocal parameters
        standard._check_border(metadata, border_paths, center)
        if parameters is None:
            parameters = metadata["parameters"]
        require(metadata["parameters"] == parameters, "Nonuniform border parameters: " + key)
        actual = unary_union([native_polygon(path, center) for path in border_paths])
        recorded = canonical_geometry(metadata["geometry"])
        art = unary_union([native_polygon(path, center) for path in art_paths]) if art_paths else GeometryCollection()
        mask = unary_union([native_polygon(path, center) for path in mask_paths]) if mask_paths else GeometryCollection()
        require(actual.is_valid and not actual.is_empty and art.is_valid and mask.is_valid, "Invalid geometry: " + key)
        require(board.buffer(.00001).covers(actual), "Border outside physical octagon: " + key)
        delta = actual.symmetric_difference(recorded).area
        hausdorff = actual.hausdorff_distance(recorded)
        require(hausdorff < .00002 and delta < .0002, "Canonical/import border shape differs: " + key)
        parts = polygons(actual)
        clearances = dict(board_edge=actual.distance(board.boundary),
                          postage_holes=min(actual.distance(Point(point)) - .2 for point in drill_centers),
                          cardinal_bridges=actual.distance(bridges),
                          existing_art=None if art.is_empty else actual.distance(art),
                          aperture_mask=None if mask.is_empty else actual.distance(mask),
                          disconnected_features=min((left.distance(right) for index, left in enumerate(parts)
                                                     for right in parts[index + 1:]), default=None))
        for field, minimum in (("board_edge", .5), ("postage_holes", .2), ("cardinal_bridges", .3),
                               ("existing_art", .2), ("aperture_mask", .2), ("disconnected_features", .2)):
            value = clearances[field]
            require(value is None or value >= minimum - .00001, "Actual border clearance failed: " + key + " " + field)
            reported = metadata["clearances_mm"][field]
            require(value is None and reported is None or value is not None and reported is not None
                    and abs(value - reported) < (.0003 if field == "postage_holes" else .00002),
                    "Recorded border clearance differs: " + key + " " + field + " " + str((value, reported)))
        require(actual.intersection(art).area < 1e-8 and actual.intersection(mask).area < 1e-8,
                "Border overlaps existing art/mask: " + key)
        evidence["covers"][key] = dict(passed=True, native_border_paths_match=True,
                                      geometry_sha256=metadata["geometry_sha256"], polygon_count=len(parts),
                                      native_polygon_count=len(border_paths), border_area_mm2=round(actual.area, 8),
                                      holes=sum(len(part.interiors) for part in parts),
                                      canonical_symmetric_difference_mm2=round(delta, 10),
                                      canonical_hausdorff_mm=round(hausdorff, 10),
                                      actual_clearances_mm={name: None if value is None else round(value, 8)
                                                            for name, value in clearances.items()})

    for variant in standard.VARIANTS:
        artifact_path = input_file(ordinary / "artwork" / art_manifest["variants"][variant]["geometry_json"])
        artifact = load(artifact_path)
        board = next(value for value in state["boards"] if value["variant"] == variant)
        before = board["border_revision"]["before"]
        current = standard._records(input_file(root / board["source"]), board["uuid"])
        input_file(root / before["path"])
        input_file(root / before["manifest_path"])
        detail = standard._check_silk_revision(root, board["uuid"], before, current, board["created"])
        evidence["physical_retention"][variant] = dict(passed=True, detail=detail,
                                                       baseline=before["path"], current=board["source"])
        for face_name, face in artifact["faces"].items():
            center = [20.5, 76.5] if face_name == "front" else [79.5, 23.5]
            border = [value for value in face["silk_polygons"] if value["category"] == "textured_octagonal_border_and_inner_divider"]
            ids = {value["id"] for value in border}
            actual_paths = [current[("FILL", value["id"])]["path"] for value in board["created"]
                            if value["face"] == face_name and value["source_id"] in ids]
            standard._check_border(face["source_metadata"]["border"], actual_paths, center)
            cover(f"standard/{variant}/{face_name}", face["source_metadata"]["border"],
                  [value["path_mil"] for value in border],
                  [value["path_mil"] for value in face["silk_polygons"] if value["id"] not in ids],
                  [value["path_mil"] for value in face["mask_opening_polygons"]], center,
                  Polygon(face["board_clip_svg_mm"]))

    for panel in design["panels"]:
        key = panel["key"]
        geometry_path = input_file(twelve / panel["geometry"])
        geometry = load(geometry_path)
        baseline = input_file(twelve / "eda/native" / ("revision-border-20261020-" + key + ".jsonl"))
        old = standard._records(baseline, standard.TWELVE_UUIDS[key])
        final = next(value for value in exported["boards"] if value["key"] == key)
        current_path = input_file(root / final["source"]["path"])
        new = standard._records(current_path, standard.TWELVE_UUIDS[key])
        def protected(records):
            return {key: value for key, value in standard._protected(records).items()
                    if not (key[0] == "FILL" and value["layerId"] == 3)}
        before, after = protected(old), protected(new)
        same, detail = manufacturing_equal(before, after)
        require(same, "Physical/mask primitive changes on " + key + ": " + detail)
        require(not standard._objects(old) and not standard._objects(new), "Color image present on " + key)
        counts = {kind: sum(record[0] == kind for record in after) for kind in ("PAD", "POLY", "FILL")}
        evidence["physical_retention"][key] = dict(passed=True, baseline=baseline.relative_to(root).as_posix(),
                                                   current=current_path.relative_to(root).as_posix(),
                                                   preserved_primitive_counts=counts,
                                                   native_coordinate_tolerance_mil=.001,
                                                   detail="All non-Top-silk manufacturing primitives retain their properties and one-to-one geometry; generated IDs and closed-contour start/direction may differ; saved-native serialization tolerance 0.001mil")
        for value in geometry["covers"]:
            prefix = value["id"] + ":"
            def paths(role):
                return [entry["body"]["path"] for entry in geometry["primitives"]
                        if entry["logical_id"].startswith(prefix + role + ":")]
            cover("twelve/" + value["id"], value["details"]["border"], paths("border"), paths("silk"),
                  paths("mask"), value["center_native_mm"], exact_board)

    require(len(evidence["covers"]) == 24 and len(evidence["physical_retention"]) == 6,
            "Expected all 24 faces and all six revised panels")
    evidence["summary"] = dict(faces=24, panels=6, separate_border_polygons=sum(value["native_polygon_count"] for value in evidence["covers"].values()),
                               minimum_clearances_mm={name: min(value["actual_clearances_mm"][name] for value in evidence["covers"].values()
                                                                if value["actual_clearances_mm"][name] is not None)
                                                      for name in next(iter(evidence["covers"].values()))["actual_clearances_mm"]},
                               physical_changes="Owned Top silk only; mask, copper, pads, holes, slots, board outlines and breakaway geometry retained")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if (root / "hardware/nfc-talisman").is_dir():
        root = root / "hardware/nfc-talisman"
    output = args.output or root / "variants/twelve-options/border-artwork-audit.json"
    result = audit(root)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
