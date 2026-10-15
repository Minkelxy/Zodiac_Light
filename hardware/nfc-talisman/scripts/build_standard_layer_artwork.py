"""Trace approved cover art into ordinary green-mask / white-silk PCB fills.

This writes only variants/standard-green-white/artwork. It neither connects to
EasyEDA nor changes the original cover art, physical holes, slots, or copper.
Run with Python, NumPy, Pillow, OpenCV, Shapely and Matplotlib installed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import cv2
import matplotlib
import numpy as np
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from PIL import Image, ImageDraw, ImageFont
import shapely
from shapely import affinity
from shapely.geometry import GeometryCollection, LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union


HARDWARE = Path(__file__).resolve().parents[1]
PROJECT = HARDWARE.parents[1]
OUTPUT = HARDWARE / "variants/standard-green-white/artwork"
NAMESPACE = "{http://www.w3.org/2000/svg}"
MM_PER_MIL = .0254
MASK_REVEAL_MM = .20
SILK_MASK_GAP_MM = .16
SILK_STROKE_MM = .22
SIMPLIFY_MM = .02
MIN_ISLAND_AREA_MM2 = .04
GREEN = "#147442"
WHITE = "#fafaf3"
SUBSTRATE = "#c6ad78"
CONFIG = {
    "horse-sagittarius": {"animal": "horse", "constellation": "sagittarius",
                           "geometry": "geometry/design.json"},
    "snake-leo": {"animal": "snake", "constellation": "leo",
                  "geometry": "variants/snake-leo/leo-geometry.json"},
}
FONT_PATH = Path(font_manager.findfont("DejaVu Sans", fontext="ttf"))
BOLD_FONT_PATH = Path(font_manager.findfont(FontProperties(family="DejaVu Sans", weight="bold")))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [polygon for part in geometry.geoms for polygon in polygons(part)]


def coordinates(value: str) -> list[tuple[float, float]]:
    numbers = [float(number) for number in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", value)]
    if len(numbers) % 2:
        raise ValueError("Uneven SVG coordinate list")
    return list(zip(numbers[::2], numbers[1::2]))


def linear_svg_path(value: str) -> list[tuple[float, float]]:
    # Current mask and star-line source paths are absolute M/L paths. Reject
    # unsupported curves rather than accidentally treating control points as a
    # mechanical contour. Outlined serif text is intentionally replaced below.
    commands = re.findall(r"[A-DF-Za-df-z]", value)
    if any(command not in ("M", "L") for command in commands):
        raise ValueError(f"Unsupported SVG line command: {commands}")
    points = coordinates(value)
    if len(points) < 2:
        raise ValueError("SVG line needs at least two points")
    return points


def svg_clip(root: ET.Element) -> Polygon:
    clip = root.find(f".//{NAMESPACE}clipPath[@id='af37']/{NAMESPACE}polygon")
    if clip is None:
        raise ValueError("Approved AF37 octagon clip is missing")
    result = Polygon(coordinates(clip.attrib["points"]))
    if not result.is_valid or abs(result.bounds[2] - 37) > 1e-6:
        raise ValueError("Unexpected AF37 clip geometry")
    return result


def clean_polygon_parts(geometry, *, min_area=MIN_ISLAND_AREA_MM2):
    result = []
    for part in polygons(geometry.buffer(0)):
        if part.area < min_area:
            continue
        holes = [list(ring.coords) for ring in part.interiors if Polygon(ring).area >= min_area]
        rebuilt = Polygon(part.exterior.coords, holes).simplify(SIMPLIFY_MM, preserve_topology=True)
        result.extend(polygons(rebuilt.buffer(0)))
    return unary_union(result) if result else GeometryCollection()


def trace_alpha(image: Image.Image, bounds: tuple[float, float, float, float]):
    alpha = np.asarray(image.convert("RGBA"))[:, :, 3]
    ink = (alpha >= 128).astype(np.uint8)
    contours, hierarchy = cv2.findContours(ink, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    hierarchy = hierarchy[0] if hierarchy is not None else []
    left, top, width, height = bounds

    def points(contour):
        result = contour[:, 0, :].astype(float) + .5
        result[:, 0] = left + result[:, 0] * width / image.width
        result[:, 1] = top + result[:, 1] * height / image.height
        return result.tolist()

    parts = []
    for index, contour in enumerate(contours):
        depth, parent = 0, hierarchy[index][3]
        while parent != -1:
            depth, parent = depth + 1, hierarchy[parent][3]
        if depth % 2 or len(contour) < 3:
            continue
        holes = [points(contours[child]) for child in range(len(contours))
                 if hierarchy[child][3] == index and len(contours[child]) >= 3]
        parts.extend(polygons(Polygon(points(contour), holes).buffer(0)))
    raw = unary_union(parts)
    cleaned = clean_polygon_parts(raw)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    valid_components = sum(stats[index, cv2.CC_STAT_AREA] * width * height / image.width / image.height
                           >= MIN_ISLAND_AREA_MM2 for index in range(1, count))
    return cleaned, {
        "alpha_threshold": 128, "source_dimensions_px": list(image.size),
        "image_placement_svg_mm": list(bounds), "pixel_pitch_mm": width / image.width,
        "original_opaque_components": int(valid_components),
        "silk_components": len(polygons(cleaned)),
        "retained_negative_holes": sum(len(part.interiors) for part in polygons(cleaned)),
        "simplify_tolerance_mm": SIMPLIFY_MM, "removed_island_or_hole_area_below_mm2": MIN_ISLAND_AREA_MM2,
        "morphological_dilation_or_erosion": False,
        "raw_opaque_area_mm2": round(raw.area, 6), "silk_area_mm2": round(cleaned.area, 6),
        "symmetric_difference_area_mm2": round(raw.symmetric_difference(cleaned).area, 6),
        "hausdorff_distance_mm": round(raw.hausdorff_distance(cleaned), 6),
        "thin_tip_policy": "Original sharp animal tips retained; local tips may be below 0.15 mm. CAM review required.",
    }


def front_geometry(source: Path, output: Path, animal: str):
    root = ET.parse(source).getroot()
    board = svg_clip(root)
    images = list(root.iter(f"{NAMESPACE}image"))
    if len(images) != 1:
        raise ValueError("Animal cover must contain exactly one approved embedded PNG")
    node = images[0]
    href = node.attrib.get("href", node.attrib.get("{http://www.w3.org/1999/xlink}href", ""))
    if not href.startswith("data:image/png;base64,"):
        raise ValueError("Animal PNG must be embedded in the approved SVG")
    png = base64.b64decode(href.split(",", 1)[1], validate=True)
    approved = HARDWARE / f"artwork/reference-collection/talisman-single-ink-v1/{animal}-single-ink.png"
    if png != approved.read_bytes():
        raise ValueError("Embedded animal PNG differs from the approved single-ink source")
    source_copy = output / f"source-{animal}-single-ink.png"
    source_copy.write_bytes(png)
    bounds = tuple(float(node.attrib[key]) for key in ("x", "y", "width", "height"))
    image = Image.open(io.BytesIO(png))
    traced, trace = trace_alpha(image, bounds)
    traced = traced.intersection(board.buffer(-.2))
    features = [(f"animal_{animal}", "animal_white_silhouette", traced)]
    return board, GeometryCollection(), GeometryCollection(), features, {
        "embedded_png_sha256": sha256(png), "approved_png": approved.relative_to(PROJECT).as_posix(),
        "embedded_png_copy": source_copy.name, "trace": trace,
        "mask_openings": "none; this front cover has no physical apertures",
    }


def bold_label(text: str, baseline: float):
    path = TextPath((0, 0), text, size=1.7, prop=FontProperties(fname=BOLD_FONT_PATH))
    outer, holes = [], []
    # The approved font has clockwise filled contours and counterclockwise
    # counters. Union filled contours so kerned glyphs do not erase each other.
    for ring in path.to_polygons(closed_only=True):
        if len(ring) >= 3:
            signed = sum(x * next_y - next_x * y for (x, y), (next_x, next_y)
                         in zip(ring, ring[1:])) / 2
            (outer if signed < 0 else holes).append(Polygon(ring).buffer(0))
    geometry = unary_union(outer).difference(unary_union(holes))
    bounds = geometry.bounds
    geometry = affinity.scale(geometry, xfact=1, yfact=-1, origin=(0, 0))
    return affinity.translate(geometry, xoff=18.5 - (bounds[0] + bounds[2]) / 2, yoff=baseline)


def rear_geometry(source: Path, constellation: str):
    root = ET.parse(source).getroot()
    board = svg_clip(root)
    source_mask = root.find(f".//{NAMESPACE}mask[@id='physical-apertures-and-020mm-substrate-reveal']")
    if source_mask is None:
        raise ValueError("Physical aperture / 0.20 mm reveal mask is missing")
    opening_parts, physical_parts, circles, mechanical = [], [], [], []
    for index, node in enumerate(source_mask.iter()):
        tag = node.tag.removeprefix(NAMESPACE)
        if node.attrib.get("fill") == "black" and tag == "circle":
            x, y, radius = (float(node.attrib[key]) for key in ("cx", "cy", "r"))
            x, y = x + 18.5, y + 18.5
            circles.append((x, y, radius))
            opening_parts.append(Point(x, y).buffer(radius, quad_segs=24))
            physical_parts.append(Point(x, y).buffer(radius - MASK_REVEAL_MM, quad_segs=24))
            mechanical.append({"type": "star_hole", "center_svg_mm": [x, y],
                               "diameter_mm": round((radius - MASK_REVEAL_MM) * 2, 6)})
        elif node.attrib.get("stroke") == "black" and tag == "path":
            points = [(x + 18.5, y + 18.5) for x, y in linear_svg_path(node.attrib["d"])]
            radius = float(node.attrib["stroke-width"]) / 2
            line = LineString(points)
            opening_parts.append(line.buffer(radius, quad_segs=24))
            physical_parts.append(line.buffer(radius - MASK_REVEAL_MM, quad_segs=24))
            mechanical.append({"type": "milled_slot", "centerline_svg_mm": points,
                               "width_mm": round((radius - MASK_REVEAL_MM) * 2, 6)})
    mask = unary_union(opening_parts).intersection(board)
    physical = unary_union(physical_parts).intersection(board)
    allowed_silk = board.buffer(-.2).difference(mask.buffer(SILK_MASK_GAP_MM, quad_segs=24))
    features = []
    for node in root.iter():
        if node.attrib.get("stroke") != "#eee8d6":
            continue
        ident = node.attrib.get("id", "")
        if ident.startswith("star_rim_"):
            continue  # Rebuilt outside the enlarged mask+silk keepout below.
        tag = node.tag.removeprefix(NAMESPACE)
        if tag == "polyline":
            points = coordinates(node.attrib["points"])
        elif tag == "path":
            points = linear_svg_path(node.attrib["d"])
        else:
            raise ValueError(f"Unsupported white source stroke: {tag}")
        points = [(x + 18.5, y + 18.5) for x, y in points]
        width = max(SILK_STROKE_MM, float(node.attrib.get("stroke-width", 0)))
        geometry = LineString(points).buffer(width / 2, quad_segs=12).intersection(allowed_silk)
        if not geometry.is_empty:
            features.append((ident, "constellation_or_border_white_stroke", geometry))
    for index, (x, y, radius) in enumerate(circles, 1):
        inner = radius + SILK_MASK_GAP_MM
        geometry = Point(x, y).buffer(inner + SILK_STROKE_MM, quad_segs=24).difference(
            Point(x, y).buffer(inner, quad_segs=24)).intersection(allowed_silk)
        features.append((f"star_ring_{index:02}", "physical_star_white_ring", geometry))
    for text, baseline in ((constellation.upper(), 4.3), ("AD ASTRA", 33.13)):
        features.append(("label_" + text.lower().replace(" ", "_"), "ordinary_silk_bold_text",
                         bold_label(text, baseline).intersection(allowed_silk)))
    return board, physical, mask, features, {
        "mechanical_apertures": mechanical,
        "physical_star_holes": len(circles), "physical_slots": sum(item["type"] == "milled_slot" for item in mechanical),
        "mask_reveal_mm": MASK_REVEAL_MM, "silk_to_mask_gap_mm": SILK_MASK_GAP_MM,
        "silk_to_actual_hole_or_slot_gap_mm": MASK_REVEAL_MM + SILK_MASK_GAP_MM,
        "source_stroke_policy": f"Existing white source edges/border retained with minimum {SILK_STROKE_MM} mm stroke",
        "star_marker_policy": "Visible 0.22 mm white rings around original physical hole centers; no change to hole centers or diameters",
        "text_policy": "Same text and baselines; original fine serif outlines replaced by DejaVu Sans Bold 1.7 mm native fill outlines",
        "font": {"family": "DejaVu Sans Bold", "file": BOLD_FONT_PATH.name,
                 "sha256": sha256(BOLD_FONT_PATH.read_bytes()), "nominal_size_mm": 1.7},
    }


def native_entry(polygon: Polygon, ident: str, category: str, face: str, layer: int):
    local = orient(polygon, sign=1)  # Local SVG y-down winding is reversed by mapping.
    left, top = (2., 95.) if face == "front" else (61., 42.)
    native = affinity.affine_transform(local, [1 / MM_PER_MIL, 0, 0, -1 / MM_PER_MIL,
                                             left / MM_PER_MIL, top / MM_PER_MIL])
    native = orient(native, sign=-1)  # EasyEDA: clockwise outer, counterclockwise holes.
    rings_local = [list(local.exterior.coords), *(list(ring.coords) for ring in local.interiors)]
    rings_native = [list(native.exterior.coords), *(list(ring.coords) for ring in native.interiors)]
    def rounded(rings):
        return [[[round(x, 6), round(y, 6)] for x, y in ring] for ring in rings]
    paths = []
    for ring in rings_native:
        ring = [(round(x, 6), round(y, 6)) for x, y in ring]
        paths.append([*ring[0], "L", *(coordinate for point in ring[1:] for coordinate in point)])
    return {"id": ident, "category": category, "layer_id": layer,
            "native_fill_width_mil": 0,
            "rings_svg_mm": rounded(rings_local), "rings_mil": rounded(rings_native),
            "path_mil": paths, "area_mm2": round(polygon.area, 6),
            "hole_count": len(polygon.interiors), "vertices": sum(len(ring) for ring in rings_native)}


def validate_native_entries(silk_entries, mask_entries, face: str):
    """Independently reconstruct rounded exported mil rings before delivery."""
    def signed_area(ring):
        return sum(x * next_y - next_x * y for (x, y), (next_x, next_y)
                   in zip(ring, ring[1:])) / 2
    left, top = (2., 95.) if face == "front" else (61., 42.)
    local_groups = []
    maximum_error = 0.
    for entries in (silk_entries, mask_entries):
        reconstructed = []
        for entry in entries:
            rings = entry["rings_mil"]
            if signed_area(rings[0]) >= 0 or any(signed_area(ring) <= 0 for ring in rings[1:]):
                raise ValueError(f"Wrong native winding: {entry['id']}")
            native = Polygon(rings[0], rings[1:])
            if not native.is_valid or native.area <= 0:
                raise ValueError(f"Invalid rounded native polygon: {entry['id']}")
            for path, ring in zip(entry["path_mil"], rings):
                if path[2] != "L" or path[:2] != ring[0] or path[3:] != [value for point in ring[1:] for value in point]:
                    raise ValueError("Native path differs from the exported polygon rings")
            local = affinity.affine_transform(native, [MM_PER_MIL, 0, 0, -MM_PER_MIL, -left, top])
            saved = Polygon(entry["rings_svg_mm"][0], entry["rings_svg_mm"][1:])
            error = local.hausdorff_distance(saved)
            maximum_error = max(maximum_error, error)
            if error > 2e-6:
                raise ValueError(f"Native/local coordinate round trip failed: {entry['id']}")
            reconstructed.append(local)
        local_groups.append(unary_union(reconstructed))
    silk, mask = local_groups
    gap = None if mask.is_empty else silk.distance(mask)
    overlap = silk.intersection(mask).area
    if overlap > 1e-9 or gap is not None and gap < .15:
        raise ValueError("Rounded native silk violates the 0.15 mm mask clearance")
    return {"status": "passed", "native_polygons_valid": True,
            "outer_clockwise_inner_counterclockwise": True,
            "complex_paths_match_rings": True,
            "maximum_native_local_round_trip_error_mm": round(maximum_error, 9),
            "rounded_native_silk_mask_overlap_mm2": round(overlap, 9),
            "rounded_native_minimum_silk_mask_gap_mm": None if gap is None else round(gap, 6)}


def svg_path(geometry):
    commands = []
    for polygon in polygons(geometry):
        for ring in [polygon.exterior, *polygon.interiors]:
            points = list(ring.coords)
            commands.append(f"M{points[0][0]:.6f},{points[0][1]:.6f} L" + " ".join(
                f"{x:.6f},{y:.6f}" for x, y in points[1:]) + " Z")
    return " ".join(commands)


def draw_geometry(canvas: Image.Image, geometry, color: str, scale: float):
    mask = Image.new("L", canvas.size)
    for polygon in polygons(geometry):
        # Build each polygon independently: a large ring's interior must not
        # erase disconnected glyphs or star rings already drawn inside it.
        part = Image.new("L", canvas.size)
        draw = ImageDraw.Draw(part)
        draw.polygon([(x * scale, y * scale) for x, y in polygon.exterior.coords], fill=255)
        for ring in polygon.interiors:
            draw.polygon([(x * scale, y * scale) for x, y in ring.coords], fill=0)
        mask.paste(255, (0, 0), part)
    canvas.alpha_composite(Image.composite(Image.new("RGBA", canvas.size, color),
                                         Image.new("RGBA", canvas.size), mask))


def render_face(output: Path, stem: str, board, physical, mask, silk):
    layers = [(board.difference(physical), GREEN), (mask.difference(physical), SUBSTRATE), (silk, WHITE)]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="37mm" height="37mm" viewBox="0 0 37 37">'
           '<title>Ordinary green soldermask and white silkscreen; exterior face, not mirrored</title>'
           '<desc>Native polygon geometry preview. Tan is substrate exposed by 0.20mm mask clearance; '
           'real holes/slots are transparent. No decorative copper or colour printing.</desc>')
    svg += "".join(f'<path fill="{color}" fill-rule="evenodd" d="{svg_path(geometry)}"/>'
                   for geometry, color in layers if not geometry.is_empty) + "</svg>"
    (output / f"{stem}.svg").write_text(svg, encoding="utf-8")
    size = 1821
    supersample = 2
    canvas = Image.new("RGBA", (size * supersample, size * supersample))
    for geometry, color in layers:
        draw_geometry(canvas, geometry, color, size * supersample / 37)
    canvas = canvas.resize((size, size), Image.Resampling.LANCZOS)
    canvas.save(output / f"{stem}.png", dpi=(1250, 1250))
    return canvas


def generate_variant(variant: str, output: Path):
    config = CONFIG[variant]
    source_dir = HARDWARE / "variants" / variant / "artwork"
    source_front = source_dir / f"front-{config['animal']}-37mm.svg"
    source_rear = source_dir / f"rear-{config['constellation']}-37mm.svg"
    geometry_source = HARDWARE / config["geometry"]
    output.mkdir(parents=True, exist_ok=True)
    sources = {path.relative_to(PROJECT).as_posix(): sha256(path.read_bytes())
               for path in (source_front, source_rear, geometry_source)}
    result = {"schema_version": 1, "variant": variant, "version": "ordinary-green-white-v1",
              "process": {"soldermask_color": "green", "silkscreen_color": "white",
                          "color_printing": False, "decorative_copper": False,
                          "mask_layer_polarity": "filled mask polygon = opening/removal of green soldermask",
                          "animal_mask_opening": False},
              "source_files_sha256": sources, "canvas_mm": [37, 37],
              "coordinate_policy": "37mm exterior-view SVG x right/y down; no horizontal mirror on either face",
              "native_polygon_winding": "outer clockwise, each inner hole counterclockwise in native mil x/y",
              "faces": {},
              "limitations": ["Animal sharp tips can be locally narrower than 0.15mm; verify CAM without automatic wholesale art distortion.",
                              "Green and white previews are source-backed design simulations; not photographs or fabrication approval.",
                              "Mask and silk are newly generated ordinary PCB artwork; original copper, electrical and physical aperture geometry are unchanged."],
              "generator_dependencies": {"opencv": cv2.__version__, "shapely": shapely.__version__,
                                         "matplotlib": matplotlib.__version__}}
    images = []
    for face, source in (("front", source_front), ("rear", source_rear)):
        if face == "front":
            board, physical, mask, features, metadata = front_geometry(source, output, config["animal"])
        else:
            board, physical, mask, features, metadata = rear_geometry(source, config["constellation"])
        silk = unary_union([geometry for _, _, geometry in features])
        if not board.covers(silk) or not mask.is_empty and not board.covers(mask):
            raise ValueError("Generated artwork exceeds the original octagon")
        overlap = silk.intersection(mask).area
        gap = None if mask.is_empty else silk.distance(mask)
        if overlap > 1e-8 or gap is not None and gap < SILK_MASK_GAP_MM - 1e-4:
            raise ValueError(f"Silk/mask clearance failed: overlap={overlap}, gap={gap}")
        silk_entries = []
        for ident, category, geometry in features:
            for index, polygon in enumerate(polygons(geometry)):
                if polygon.area < .001:
                    continue
                silk_entries.append(native_entry(polygon, f"{ident}_{index + 1:02}", category, face, 3))
        mask_entries = [native_entry(polygon, f"mask_opening_{index + 1:02}", "physical_aperture_mask_opening", face, 5)
                        for index, polygon in enumerate(polygons(mask))]
        validation = validate_native_entries(silk_entries, mask_entries, face)
        # Preview exactly the delivered polygons after the tiny-fragment filter.
        silk = unary_union([Polygon(entry["rings_svg_mm"][0], entry["rings_svg_mm"][1:])
                            for entry in silk_entries])
        mask = unary_union([Polygon(entry["rings_svg_mm"][0], entry["rings_svg_mm"][1:])
                            for entry in mask_entries])
        stem = f"{variant}-{face}-standard-green-white-37mm"
        images.append(render_face(output, stem, board, physical, mask, silk))
        left, top = (2, 95) if face == "front" else (61, 42)
        result["faces"][face] = {"silk_layer_id": 3, "mask_layer_id": 5,
            "mapping": {"native_x_mm": f"{left} + svg_x_mm", "native_y_mm": f"{top} - svg_y_mm",
                        "mm_per_mil": MM_PER_MIL, "mirror": False},
            "board_clip_svg_mm": [list(point) for point in board.exterior.coords],
            "silk_polygons": silk_entries, "mask_opening_polygons": mask_entries,
            "silk_area_mm2": round(silk.area, 6), "mask_opening_area_mm2": round(mask.area, 6),
            "silk_mask_overlap_mm2": round(overlap, 9),
            "minimum_silk_mask_gap_mm": None if gap is None else round(gap, 6),
            "preview_svg": stem + ".svg", "preview_png": stem + ".png", "source_metadata": metadata,
            "validation": validation}
    preview = Image.new("RGB", (1900, 1080), "#eff1ed")
    draw = ImageDraw.Draw(preview)
    font = ImageFont.truetype(str(FONT_PATH), 32)
    small = ImageFont.truetype(str(FONT_PATH), 24)
    draw.text((70, 30), variant + " | green soldermask / white silkscreen", font=font, fill="#173e2a")
    for index, image in enumerate(images):
        image = image.resize((830, 830), Image.Resampling.LANCZOS)
        preview.paste(image, (70 + index * 960, 125), image)
        draw.text((70 + index * 960, 85), "FRONT / animal" if index == 0 else "REAR / constellation", font=small, fill="#173e2a")
    draw.text((70, 995), "37 mm AF octagon | exterior view | not mirrored | geometry preview, CAM pending", font=small, fill="#34463b")
    preview.save(output / f"{variant}-standard-green-white-two-face-preview.png")
    target = output / f"{variant}-standard-layer-artwork.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    results = [generate_variant(variant, args.output) for variant in CONFIG]
    manifest = {"schema_version": 1, "version": "ordinary-green-white-v1",
                "generator": Path(__file__).relative_to(PROJECT).as_posix(),
                "generator_sha256": sha256(Path(__file__).read_bytes()),
                "variants": {result["variant"]: {
                    "geometry_json": result["variant"] + "-standard-layer-artwork.json",
                    "silk_polygon_count": {face: len(data["silk_polygons"]) for face, data in result["faces"].items()},
                    "mask_opening_polygon_count": {face: len(data["mask_opening_polygons"]) for face, data in result["faces"].items()},
                    "minimum_rear_silk_mask_gap_mm": result["faces"]["rear"]["minimum_silk_mask_gap_mm"],
                } for result in results},
                "files": {path.name: {"sha256": sha256(path.read_bytes()), "size": path.stat().st_size}
                          for path in sorted(args.output.iterdir()) if path.is_file() and path.name != "manifest.json"}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "variants": manifest["variants"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
