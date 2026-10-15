"""Trace the project's existing talisman PNGs for ordinary 37 mm PCB covers.

No image generation, live EasyEDA operation or source-image modification occurs.
``build_cover(name)`` returns (white_silk_geometry, empty_mask, provenance).
The public ``goat`` option uses the existing project asset named ``sheep``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity
from shapely.geometry import GeometryCollection, Polygon, box
from shapely.ops import unary_union

import build_standard_layer_artwork as standard


HW = Path(__file__).resolve().parents[1]
PROJECT = HW.parents[1]
COLLECTION = HW / "artwork/reference-collection"
SOURCE_COLLECTION = "talisman-single-ink-v1"
ANIMALS = ("rat", "ox", "tiger", "rabbit", "dragon", "goat", "monkey", "rooster", "dog", "pig")
ALIASES = {"goat": "sheep"}
ALPHA_THRESHOLD = 128
SIMPLIFY_MM = .012
MIN_ISLAND_AREA_MM2 = .005
MIN_HOLE_AREA_MM2 = .003
SOURCE_MIN_ISLAND_AREA_PX2 = 2.
NUMERICAL_FIT_GUARD_MM = .01
NUMERICAL_LABEL_GUARD_MM = .005


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def canonical_ring(points):
    ring = [(round(float(x), 6), round(float(y), 6)) for x, y in points]
    if ring and ring[0] == ring[-1]:
        ring.pop()
    ring = [point for index, point in enumerate(ring) if not index or point != ring[index - 1]]
    if len(ring) < 3:
        raise ValueError("A traced ring has fewer than three distinct vertices")

    def rotate(values):
        first = min(range(len(values)), key=lambda index: values[index])
        return values[first:] + values[:first]

    return [list(point) for point in min(rotate(ring), rotate(list(reversed(ring))))]


def canonical_geometry(geometry):
    """Return the exact stdlib-JSON representation used by geometry_sha256."""
    result = []
    for polygon in standard.polygons(geometry):
        result.append({"exterior": canonical_ring(polygon.exterior.coords),
                       "holes": sorted([canonical_ring(ring.coords) for ring in polygon.interiors], key=compact)})
    return {"units": "mm", "coordinate_system": "cover_top_left_x_right_y_down",
            "polygons": sorted(result, key=compact)}


def load_asset(name: str):
    source_id = ALIASES.get(name, name)
    manifest_path = COLLECTION / SOURCE_COLLECTION / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    matches = [entry for entry in manifest["files"] if entry["id"] == source_id]
    if len(matches) != 1:
        raise ValueError(f"Unknown or ambiguous existing talisman asset: {name}")
    entry = matches[0]
    source = COLLECTION / entry["path"]
    candidate = COLLECTION / entry["candidate_path"]
    original = COLLECTION / entry["source_path"]
    for path, expected in ((source, entry["output_sha256"]),
                           (candidate, entry["candidate_sha256"]),
                           (original, entry["source_sha256"])):
        if digest(path.read_bytes()) != expected:
            raise ValueError(f"Existing talisman provenance hash mismatch: {path}")
    image = Image.open(source).convert("RGBA")
    rgba = np.asarray(image)
    candidate_alpha = np.asarray(Image.open(candidate).convert("RGBA"))[:, :, 3]
    if not np.array_equal(rgba[:, :, 3], candidate_alpha):
        raise ValueError("The single-ink asset no longer retains its candidate alpha bytes")
    intended = np.array([int(entry["ink_hex"][index:index + 2], 16) for index in (1, 3, 5)])
    if not np.all(rgba[:, :, :3][rgba[:, :, 3] > 0] == intended):
        raise ValueError("The existing single-ink asset has an unexpected visible palette")
    relative = lambda path: path.relative_to(PROJECT).as_posix()
    details = {
        "artwork_kind": "project_talisman_single_ink_trace", "original_vector_art": False,
        "requested_animal_id": name, "source_collection": SOURCE_COLLECTION, "source_id": source_id,
        "source_png": relative(source), "source_png_sha256": entry["output_sha256"],
        "source_alpha_sha256": digest(rgba[:, :, 3].tobytes()),
        "source_manifest": relative(manifest_path), "source_manifest_sha256": digest(manifest_bytes),
        "source_candidate_png": relative(candidate), "source_candidate_png_sha256": entry["candidate_sha256"],
        "source_original_reference": relative(original), "source_original_reference_sha256": entry["source_sha256"],
        "source_visual_status": entry.get("visual_status", "reviewed_draft"),
        "source_visual_note": entry.get("visual_note", ""),
        "historical_source_method": manifest["method"],
        "historical_rgb_normalization_approval_date": manifest.get("user_approved_rgb_normalization_date"),
        "source_provenance": entry.get("provenance", {}),
        "new_image_generation": False,
        "source_policy": "Reuse the project's existing single-ink asset family used by the horse/snake covers; historical fidelity notes remain applicable.",
        "star_holes": 0, "animal_mask_openings": 0,
    }
    return image, details


def trace_pixels(image: Image.Image):
    alpha = np.asarray(image)[:, :, 3]
    ink = (alpha >= ALPHA_THRESHOLD).astype(np.uint8)
    contours, hierarchy = cv2.findContours(ink, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    hierarchy = hierarchy[0] if hierarchy is not None else []
    parts = []
    for index, contour in enumerate(contours):
        depth, parent = 0, hierarchy[index][3]
        while parent != -1:
            depth, parent = depth + 1, hierarchy[parent][3]
        if depth % 2 or len(contour) < 3:
            continue
        exterior = contour[:, 0, :].astype(float) + .5
        holes = [(contours[child][:, 0, :].astype(float) + .5).tolist()
                 for child in range(len(contours)) if hierarchy[child][3] == index and len(contours[child]) >= 3]
        for polygon in standard.polygons(Polygon(exterior, holes).buffer(0)):
            if polygon.area >= SOURCE_MIN_ISLAND_AREA_PX2:
                parts.append(polygon)
    geometry = unary_union(parts)
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError("No valid talisman contours were recovered from the existing PNG alpha")
    return geometry, {"source_dimensions_px": list(image.size), "alpha_threshold": ALPHA_THRESHOLD,
                      "contour_method": "OpenCV RETR_TREE / CHAIN_APPROX_SIMPLE; even-depth filled contours, odd-depth negative holes",
                      "source_min_island_area_px2": SOURCE_MIN_ISLAND_AREA_PX2,
                      "source_alpha_contour_components": len(standard.polygons(geometry)),
                      "source_alpha_negative_holes": sum(len(part.interiors) for part in standard.polygons(geometry)),
                      "pixel_coordinate_policy": "Original pixel-center coordinates (x+0.5,y+0.5); no raster resampling"}


def fit_complete_artwork(geometry, allowed):
    bounds = geometry.bounds
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    centered = affinity.translate(geometry, -(bounds[0] + bounds[2]) / 2, -(bounds[1] + bounds[3]) / 2)
    left, top, right, bottom = allowed.bounds
    best_scale, best_y = 0., (top + bottom) / 2

    def search(center_y):
        nonlocal best_scale, best_y
        maximum = min((right - left) / width, 2 * (center_y - top) / height,
                      2 * (bottom - center_y) / height)
        if maximum <= best_scale:
            return
        low, high = best_scale, maximum
        for _ in range(23):
            scale = (low + high) / 2
            candidate = affinity.translate(affinity.scale(centered, scale, scale, origin=(0, 0)), 18.5, center_y)
            if allowed.covers(candidate):
                low = scale
            else:
                high = scale
        if low > best_scale:
            best_scale, best_y = low, center_y

    centers = np.linspace(top + .05, bottom - .05, 61)
    for center_y in centers:
        search(float(center_y))
    step = (bottom - top - .1) / 60
    for center_y in np.linspace(max(top + .05, best_y - step), min(bottom - .05, best_y + step), 25):
        search(float(center_y))
    if best_scale <= 0:
        raise ValueError("The existing talisman cannot fit the complete cover/label-safe region")
    fitted = affinity.translate(affinity.scale(centered, best_scale, best_scale, origin=(0, 0)), 18.5, best_y)
    return fitted, {"scale_mm_per_source_pixel": best_scale, "visible_center_svg_mm": [18.5, best_y],
                    "source_visible_bounds_px": list(bounds), "rotation_degrees": 0, "mirror": False,
                    "uniform_scale": True, "cropped_subject": False,
                    "fit_policy": "Maximize uniform size at fixed horizontal center; 61 vertical candidates plus 25 local refinements, containment bisection. No clipping of subject geometry."}


def build_cover(name: str, *, label_top_mm=32.1, label_clearance_mm=.6, board_margin_mm=1.2):
    image, details = load_asset(name)
    source, trace = trace_pixels(image)
    approved_clip = HW / "variants/horse-sagittarius/artwork/front-horse-37mm.svg"
    import xml.etree.ElementTree as ET
    board = standard.svg_clip(ET.parse(approved_clip).getroot())
    # The approved SVG clip rounds octagon vertices to six decimal places;
    # leave a real geometric guard so the main generator's exact AF37 polygon
    # contains the complete trace without any subsequent clipping/reordering.
    available = board.buffer(-(board_margin_mm + NUMERICAL_FIT_GUARD_MM)).intersection(
        box(0, 0, 37, label_top_mm - label_clearance_mm - NUMERICAL_LABEL_GUARD_MM))
    if available.is_empty:
        raise ValueError("Label clearance leaves no room for the talisman")
    fitted, placement = fit_complete_artwork(source, available)
    parts = []
    for polygon in standard.polygons(fitted):
        if polygon.area < MIN_ISLAND_AREA_MM2:
            continue
        holes = [list(ring.coords) for ring in polygon.interiors if Polygon(ring).area >= MIN_HOLE_AREA_MM2]
        simplified = Polygon(polygon.exterior.coords, holes).simplify(SIMPLIFY_MM, preserve_topology=True)
        parts.extend(standard.polygons(simplified.buffer(0)))
    silk = unary_union(parts)
    if silk.is_empty or not silk.is_valid or silk.difference(available).area > 1e-8:
        raise ValueError("Traced talisman geometry is invalid or enters the reserved label/edge area")
    canonical = canonical_geometry(silk)
    reconstructed = unary_union([Polygon(item["exterior"], item["holes"]) for item in canonical["polygons"]])
    if not reconstructed.is_valid or reconstructed.hausdorff_distance(silk) > 2e-6:
        raise ValueError("Canonical trace geometry does not retain the delivered contours")
    trace.update({"simplify_tolerance_mm": SIMPLIFY_MM, "min_island_area_mm2": MIN_ISLAND_AREA_MM2,
                  "min_negative_hole_area_mm2": MIN_HOLE_AREA_MM2,
                  "morphological_dilation_or_erosion": False,
                  "silk_component_count": len(standard.polygons(silk)),
                  "retained_negative_hole_count": sum(len(part.interiors) for part in standard.polygons(silk)),
                  "silk_area_mm2": round(silk.area, 6),
                  "symmetric_difference_from_fitted_alpha_mm2": round(silk.symmetric_difference(fitted).area, 6),
                  "hausdorff_from_fitted_alpha_mm": round(silk.hausdorff_distance(fitted), 6),
                  "min_feature_claim": "No claim that every original talisman tip/negative detail meets 0.15mm; fine details remain for supplier CAM review."})
    placement.update({"label_top_mm": label_top_mm, "label_clearance_mm": label_clearance_mm,
                      "board_margin_mm": board_margin_mm, "visible_bounds_svg_mm": list(silk.bounds),
                      "numerical_fit_guard_mm": NUMERICAL_FIT_GUARD_MM,
                      "numerical_label_guard_mm": NUMERICAL_LABEL_GUARD_MM,
                      "actual_label_clearance_mm": label_top_mm - silk.bounds[3],
                      "complete_subject_contained": True, "original_alpha_frame_policy": "All source alpha contours above the documented tiny-island threshold retained; no invented or deleted octagonal/bagua frame."})
    details.update({"trace": trace, "placement": placement, "trace_geometry": canonical,
                    "geometry_sha256": digest(compact(canonical).encode("ascii")),
                    "geometry_encoding": "canonical_geometry(): round6 mm; closed duplicate removed; ring rotation/direction canonical; sorted holes/polygons; compact sort_keys ASCII JSON",
                    "cover_clip_source": approved_clip.relative_to(PROJECT).as_posix(),
                    "cover_clip_source_sha256": digest(approved_clip.read_bytes()),
                    "validation": {"geometry_valid": True, "whole_subject_inside_cover": True,
                                   "reserved_label_area_clear": True, "mask_opening_count": 0}})
    return silk, GeometryCollection(), details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animal", action="append", choices=ANIMALS, help="Default: all ten new options")
    parser.add_argument("--output", type=Path, default=PROJECT / "tmp/talisman-cover-artwork-review")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    cards = []
    for name in args.animal or ANIMALS:
        silk, mask, details = build_cover(name)
        label = standard.bold_label(name.upper(), 33.36171875)
        label_bounds = label.bounds
        label = affinity.translate(label, yoff=32.1 - label_bounds[1])
        # Preview only; the main generator retains its existing label function.
        import xml.etree.ElementTree as ET
        board = standard.svg_clip(ET.parse(PROJECT / details["cover_clip_source"]).getroot())
        image = standard.render_face(args.output, f"{name}-project-talisman-37mm", board,
                                     GeometryCollection(), mask, silk.union(label))
        (args.output / f"{name}-trace-provenance.json").write_text(
            json.dumps(details, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        cards.append((name, image))
        records.append({"animal": name, "source_id": details["source_id"], "source_png_sha256": details["source_png_sha256"],
                        "geometry_sha256": details["geometry_sha256"], "components": details["trace"]["silk_component_count"],
                        "holes": details["trace"]["retained_negative_hole_count"],
                        "label_clearance_mm": details["placement"]["actual_label_clearance_mm"]})
    sheet = Image.new("RGB", (1900, 960), "#eff1ed")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(standard.FONT_PATH), 25)
    for index, (name, image) in enumerate(cards):
        x, y = (index % 5) * 380, (index // 5) * 480
        image = image.resize((350, 350), Image.Resampling.LANCZOS)
        sheet.paste(image, (x + 15, y + 30), image)
        draw.text((x + 20, y + 395), name.upper(), font=font, fill="#173e2a")
        draw.text((x + 20, y + 430), "existing project talisman", font=font, fill="#34463b")
    sheet.save(args.output / "project-talisman-ten-options-preview.png")
    summary = {"schema_version": 1, "source_collection": SOURCE_COLLECTION,
               "new_image_generation": False, "covers": records}
    (args.output / "trace-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
