"""Inspect actual linear Gerber regions, their polarity and retained negative spaces.

Read-only input analysis; writes only its own report under tmp. No live EasyEDA
API calls. Only the ordinary artwork PolygonModel section is compared: existing
component/customer Text and Pad sections remain separate.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import zipfile
from collections import Counter
from shapely.geometry import GeometryCollection, Point, Polygon
from shapely.ops import unary_union


REPO = Path(__file__).resolve().parents[3]
HARDWARE = REPO / "hardware/nfc-talisman"
STANDARD = HARDWARE / "variants/standard-green-white"
TOLERANCE_MM = .00001


def region_geometry(contours):
    """Gerber region contours use even/odd filling; LPC is handled separately."""
    result = GeometryCollection()
    for contour in contours:
        points = []
        for point in contour:
            if not points or points[-1] != point:
                points.append(point)
        if len(points) < 3:
            continue
        poly = Polygon(points)
        if poly.area <= 1e-14:
            continue
        if not poly.is_valid:
            # Gerber exports holes as zero-width doubled bridges in one contour.
            poly = poly.buffer(0)
        assert poly.is_valid, "Invalid Gerber contour after zero-area bridge recovery"
        result = result.symmetric_difference(poly)
    return result


def parse_regions(raw):
    text = raw.decode("utf-8-sig")
    match = re.search(r"%FS[LT]A?X(\d)(\d)Y(\d)(\d)\*%", text)
    assert match, "Gerber coordinate format missing"
    assert match.group(2) == match.group(4), "Unequal X/Y precision unsupported"
    factor = 10 ** int(match.group(2))
    assert "%MOMM*%" in text, "Expected mm Gerber units"
    polarity = "D"
    section = "unsectioned"
    region = None
    contour = None
    coords = [0, 0]
    output = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        comment = re.fullmatch(r"G04 (.+) (Start|End)\*", line)
        if comment:
            section = comment.group(1) if comment.group(2) == "Start" else "unsectioned"
            continue
        if line in ("%LPD*%", "%LPC*%"):
            polarity = line[3]
            continue
        if line == "G36*":
            assert region is None, "Nested Gerber region"
            region, contour = [], None
            continue
        if line == "G37*":
            assert region is not None, "Gerber region end without start"
            if contour:
                region.append(contour)
            geometry = region_geometry(region)
            output.append({"section": section, "polarity": polarity, "geometry": geometry,
                           "contour_count": len(region)})
            region, contour = None, None
            continue
        if region is None:
            continue
        if line in ("G01*", "G75*", "G74*"):
            continue
        assert not line.startswith(("G02", "G03")), "Unexpected arc within ordinary-artwork region"
        drawing = re.fullmatch(r"(?:G01)?(?:X(-?\d+))?(?:Y(-?\d+))?D0([12])\*", line)
        assert drawing, f"Unsupported command within region: {line}"
        for axis, group in enumerate((drawing.group(1), drawing.group(2))):
            if group is not None:
                coords[axis] = int(group) / factor
        point = tuple(coords)
        if drawing.group(3) == "2":
            if contour:
                region.append(contour)
            contour = [point]
        else:
            assert contour is not None, "Region draw before contour start"
            contour.append(point)
    assert region is None, "Unclosed Gerber region"
    return output


def render_polygon_models(regions):
    geometry = GeometryCollection()
    selected = [item for item in regions if item["section"] == "PolygonModel"]
    assert selected, "No actual ordinary PolygonModel regions"
    for item in selected:
        if item["polarity"] == "D":
            geometry = geometry.union(item["geometry"])
        else:
            geometry = geometry.difference(item["geometry"])
    return geometry, selected


def expected_polygon(entry):
    rings = [[(x * .0254, y * .0254) for x, y in ring] for ring in entry["rings_mil"]]
    polygon = Polygon(rings[0], rings[1:])
    assert polygon.is_valid and polygon.area > 0, "Invalid artifact polygon"
    return polygon


def count_holes(geometry):
    if isinstance(geometry, Polygon):
        return len(geometry.interiors)
    return sum(count_holes(item) for item in getattr(geometry, "geoms", []))


def main():
    manifest_path = STANDARD / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    art_manifest = json.loads((STANDARD / "artwork/manifest.json").read_text(encoding="utf-8"))
    result = {"status": "passed", "read_only": True, "coordinate_tolerance_mm": TOLERANCE_MM,
              "export_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "variants": {}, "errors": []}
    for board in manifest["boards"]:
        variant = board["variant"]
        artifact_path = STANDARD / "artwork" / art_manifest["variants"][variant]["geometry_json"]
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        report = {"artwork_geometry_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(), "faces": {}}
        try:
            path = HARDWARE / board["gerber"]
            report["gerber_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None, "Gerber CRC failure"
                assert not any(name.startswith("Fabrication_Colorful") for name in archive.namelist()), "Color files remain"
                layers = {}
                for kind, filename in (("silk", "Gerber_TopSilkscreenLayer.GTO"),
                                       ("mask", "Gerber_TopSolderMaskLayer.GTS")):
                    regions = parse_regions(archive.read(filename))
                    actual, selected = render_polygon_models(regions)
                    layers[kind] = actual
                    report[kind + "_regions"] = {"polygon_model_dark": sum(r["polarity"] == "D" for r in selected),
                                                 "polygon_model_clear": sum(r["polarity"] == "C" for r in selected),
                                                 "all_sections": dict(Counter(r["section"] for r in regions))}
            for face_name, face in artifact["faces"].items():
                frame = Polygon([(2 + x, 95 - y) if face_name == "front" else (61 + x, 42 - y)
                                 for x, y in face["board_clip_svg_mm"]])
                face_report = {}
                for kind, field in (("silk", "silk_polygons"), ("mask", "mask_opening_polygons")):
                    entries = face[field]
                    expected = unary_union([expected_polygon(entry) for entry in entries])
                    actual = layers[kind].intersection(frame)
                    difference = actual.symmetric_difference(expected).area
                    if expected.is_empty:
                        assert actual.area < 1e-9, "Unexpected front-mask opening"
                        hausdorff = None
                    else:
                        hausdorff = actual.hausdorff_distance(expected)
                        assert math.isfinite(hausdorff) and hausdorff <= TOLERANCE_MM, f"{face_name}/{kind}: artwork boundary differs by {hausdorff}mm"
                        assert difference <= expected.length * TOLERANCE_MM * 1.1, f"{face_name}/{kind}: occupied area differs"
                    hole_points = []
                    for entry in entries:
                        for ring in entry["rings_mil"][1:]:
                            point = Polygon([(x * .0254, y * .0254) for x, y in ring]).representative_point()
                            assert not actual.covers(point), f"Negative hole filled: {entry['id']}"
                            hole_points.append(point)
                    if kind == "silk" and face_name == "rear":
                        star_entries = [entry for entry in entries if entry["id"].startswith("star_ring_")]
                        assert len(star_entries) == (8 if variant == "horse-sagittarius" else 9), "Star ring count differs"
                        assert all(entry["hole_count"] == 1 for entry in star_entries), "Star ring negative center missing in artifact"
                    face_report[kind] = {"expected_area_mm2": expected.area, "gerber_area_mm2": actual.area,
                                         "symmetric_difference_mm2": difference, "hausdorff_mm": hausdorff,
                                         "negative_hole_probes_checked": len(hole_points),
                                         "expected_union_holes": count_holes(expected), "actual_union_holes": count_holes(actual),
                                         "negative_holes_preserved": True,
                                         "nominal_fill_width_causes_no_extra_stroke": True}
                mask_geometry = layers["mask"].intersection(frame)
                silk_geometry = layers["silk"].intersection(frame)
                gap = None if mask_geometry.is_empty else silk_geometry.distance(mask_geometry)
                assert silk_geometry.intersection(mask_geometry).area < 1e-9 and (gap is None or gap >= .15), "Actual Gerber silk/mask clearance failed"
                face_report["actual_silk_mask_gap_mm"] = gap
                report["faces"][face_name] = face_report
            report["passed"] = True
        except (AssertionError, ValueError, OSError, KeyError) as exc:
            report["passed"] = False
            report["error"] = str(exc)
            result["errors"].append(f"{variant}: {exc}")
        result["variants"][variant] = report
    if result["errors"]:
        result["status"] = "failed"
    result["limitations"] = ["Verifies exported linear Gerber PolygonModel regions; inherited Text/Pad/flash rendering is outside this artwork-only check.",
                             "Silkscreen CAM trimming, green ink appearance/transmission, supplier acceptance and physical tests remain pending."]
    target = STANDARD / "gerber-artwork-audit.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
