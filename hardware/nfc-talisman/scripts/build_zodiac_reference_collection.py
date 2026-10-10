#!/usr/bin/env python3
"""Build source-faithful Stellarium Modern zodiac star charts.

The script reads the frozen Stellarium Modern index and the retained raw
Hipparcos VizieR response. It does not contact the network or modify EDA files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
ASSET_DIR = ROOT / "hardware/nfc-talisman/artwork/reference-collection/zodiac-modern"
SOURCE_DIR = ROOT / "hardware/nfc-talisman/artwork/reference-collection/source-zodiac"
STELLARIUM_INDEX = ROOT / "data/sources/20261008T150844925832Z/stellarium_modern_index.json"
TEAPOT_GEOMETRY = ROOT / "hardware/nfc-talisman/geometry/sagittarius-before-refinement.json"
HIP_FILE = SOURCE_DIR / "hipparcos-zodiac.tsv"

ZODIACS = (
    ("Ari", "Aries", "白羊座"),
    ("Tau", "Taurus", "金牛座"),
    ("Gem", "Gemini", "双子座"),
    ("Cnc", "Cancer", "巨蟹座"),
    ("Leo", "Leo", "狮子座"),
    ("Vir", "Virgo", "处女座"),
    ("Lib", "Libra", "天秤座"),
    ("Sco", "Scorpius", "天蝎座"),
    ("Sgr", "Sagittarius", "射手座"),
    ("Cap", "Capricornus", "摩羯座"),
    ("Aqr", "Aquarius", "水瓶座"),
    ("Psc", "Pisces", "双鱼座"),
)
W = H = 1024
MARGIN = 112.0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_hipparcos(path: Path) -> dict[int, dict[str, float]]:
    rows = csv.reader((line for line in path.read_text(encoding="utf-8-sig").splitlines()
                       if line and not line.startswith("#")), delimiter="\t")
    header = next(rows, None)
    if header != ["HIP", "RAICRS", "DEICRS", "Vmag"]:
        raise ValueError(f"Unexpected Hipparcos fields: {header}")
    result: dict[int, dict[str, float]] = {}
    for row in rows:
        if not row or not row[0].strip().isdigit():
            continue  # VizieR unit and separator rows.
        hip = int(row[0])
        if hip in result:
            raise ValueError(f"Duplicate HIP row {hip}")
        ra, dec, mag = (float(value) for value in row[1:])
        if not (math.isfinite(ra) and math.isfinite(dec) and math.isfinite(mag)
                and 0 <= ra < 360 and -90 <= dec <= 90):
            raise ValueError(f"Invalid Hipparcos coordinate or magnitude for HIP {hip}")
        result[hip] = {"ra_deg": ra, "dec_deg": dec, "mag_v": mag}
    return result


def constellation_source(index: dict, code: str) -> dict:
    item = next((entry for entry in index["constellations"]
                 if entry.get("id") == f"CON modern {code}"), None)
    if item is None:
        raise ValueError(f"Missing Stellarium source entry for {code}")
    if not item.get("lines") or any(len(line) < 2 for line in item["lines"]):
        raise ValueError(f"Malformed source lines for {code}")
    return item


def project_gnomonic(stars: list[dict]) -> dict[int, tuple[float, float]]:
    """Return tangent-plane degrees with celestial east left and north up."""
    vectors = []
    for star in stars:
        ra = math.radians(star["ra_deg"])
        dec = math.radians(star["dec_deg"])
        vectors.append((math.cos(dec) * math.cos(ra),
                        math.cos(dec) * math.sin(ra), math.sin(dec)))
    c = tuple(sum(v[i] for v in vectors) for i in range(3))
    norm = math.sqrt(sum(value * value for value in c))
    if norm < 1e-12:
        raise ValueError("Cannot determine spherical centre")
    c = tuple(value / norm for value in c)
    ra0 = math.atan2(c[1], c[0])
    dec0 = math.asin(c[2])
    east = (-math.sin(ra0), math.cos(ra0), 0.0)
    north = (-math.sin(dec0) * math.cos(ra0),
             -math.sin(dec0) * math.sin(ra0), math.cos(dec0))
    result: dict[int, tuple[float, float]] = {}
    for star, vector in zip(stars, vectors):
        denominator = sum(a * b for a, b in zip(c, vector))
        if denominator <= 0:
            raise ValueError(f"Star outside gnomonic hemisphere: HIP {star['hip']}")
        # Return sky-chart coordinates: east is left (negative x) and north is up (positive y).
        x = -sum(a * b for a, b in zip(east, vector)) / denominator
        y = sum(a * b for a, b in zip(north, vector)) / denominator
        result[star["hip"]] = (math.degrees(x), math.degrees(y))
    return result


def layout(stars: list[dict], xy_degrees: dict[int, tuple[float, float]]) -> dict[int, tuple[float, float]]:
    xs = [xy_degrees[star["hip"]][0] for star in stars]
    ys = [xy_degrees[star["hip"]][1] for star in stars]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span <= 0:
        raise ValueError("Degenerate chart")
    scale = (min(W, H) - 2 * MARGIN) / span
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    result = {star["hip"]: (W / 2 + (xy_degrees[star["hip"]][0] - cx) * scale,
                            H / 2 - (xy_degrees[star["hip"]][1] - cy) * scale)
              for star in stars}
    for hip, (x, y) in result.items():
        if not (MARGIN - 1e-6 <= x <= W - MARGIN + 1e-6
                and MARGIN - 1e-6 <= y <= H - MARGIN + 1e-6):
            # The smaller dimension may have more than the minimum margin, never less.
            raise ValueError(f"HIP {hip} was clipped by equal-aspect layout")
    return result


def f(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def radius_for_mag(mag: float) -> float:
    # A small, bounded brightness cue keeps the map legible without labels.
    return max(2.6, min(5.5, 4.3 - 0.42 * (mag - 2.0)))


def svg_document(title: str | None, code: str, english: str, stars: list[dict],
                 positions: dict[int, tuple[float, float]], edges: list[tuple[int, int]],
                 dark: bool) -> str:
    bg = '<rect width="1024" height="1024" fill="#08111f"/>' if dark else ""
    ink = "#ecf3ff" if dark else "#111827"
    line_w = 2.7 if dark else 3.2
    chunks = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">']
    if title:
        chunks.extend([f"<title>{title}</title>",
                       '<desc>Source-faithful Stellarium Modern constellation; Hipparcos star positions, gnomonic projection, east left and north up.</desc>'])
    chunks.append(bg)
    chunks.append(f'<g fill="none" stroke="{ink}" stroke-width="{line_w}" stroke-linecap="round" stroke-linejoin="round">')
    for a, b in edges:
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        chunks.append(f'<path d="M {f(x1)} {f(y1)} L {f(x2)} {f(y2)}"/>')
    chunks.append("</g>")
    chunks.append(f'<g fill="{ink}">')
    for star in stars:
        x, y = positions[star["hip"]]
        chunks.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(radius_for_mag(star["mag_v"]))}"/>')
    chunks.append("</g></svg>")
    return "\n".join(chunks) + "\n"


def find_node_and_sharp() -> tuple[str, str] | None:
    roots = []
    env_modules = os.environ.get("CODEX_NODE_MODULES")
    if env_modules:
        roots.append(Path(env_modules))
    roots.extend((Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
                  Path("C:/Users/20177/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules")))
    node_candidates = [os.environ.get("CODEX_NODE"), shutil.which("node"),
                       str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"),
                       "C:/Users/20177/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"]
    node = next((candidate for candidate in node_candidates if candidate and Path(candidate).is_file()), None)
    sharp = next((root / "sharp" for root in roots if (root / "sharp").is_dir()), None)
    if node and sharp:
        return str(node), str(sharp)
    return None


def render_png(svg: Path, output: Path) -> str:
    try:
        import cairosvg  # type: ignore
        cairosvg.svg2png(url=str(svg), write_to=str(output), output_width=1024, output_height=1024)
        return "CairoSVG"
    except ImportError:
        found = find_node_and_sharp()
        if not found:
            raise RuntimeError("PNG rendering requires CairoSVG or Node.js with the bundled sharp package")
        node, sharp = found
        js = "const sharp=require(process.argv[1]); sharp(process.argv[2]).png().toFile(process.argv[3]).catch(e=>{console.error(e);process.exit(1)});"
        subprocess.run([node, "-e", js, sharp, str(svg), str(output)], check=True)
        return "sharp"


def output_chart(code: str, english: str, chinese: str, item: dict, hip_data: dict,
                 source_sha: str, index_sha: str, out_root: Path, renderer: str | None) -> dict:
    segments = [(int(a), int(b)) for line in item["lines"] for a, b in zip(line, line[1:])]
    hips = sorted({hip for edge in segments for hip in edge})
    missing = sorted(set(hips) - set(hip_data))
    if missing:
        raise ValueError(f"{code}: missing HIP rows {missing}")
    if len(set(tuple(sorted(edge)) for edge in segments)) != len(segments):
        raise ValueError(f"{code}: source contains duplicate undirected edges")
    stars = [{"hip": hip, **hip_data[hip]} for hip in hips]
    projected = project_gnomonic(stars)
    positions = layout(stars, projected)
    out = out_root / code
    out.mkdir(parents=True, exist_ok=True)
    dark_name = f"{code.lower()}-modern-dark.svg"
    png_name = f"{code.lower()}-modern-dark.png"
    import_name = f"{code.lower()}-modern-import.svg"
    title_name = f"{code.lower()}-modern-import-titled.svg"
    (out / dark_name).write_text(svg_document(f"{english} constellation chart | Stellarium Modern", code,
                                              english, stars, positions, segments, dark=True), encoding="utf-8")
    (out / import_name).write_text(svg_document(None, code, english, stars, positions, segments, dark=False), encoding="utf-8")
    (out / title_name).write_text(svg_document(f"{english} constellation | Stellarium Modern", code,
                                                english, stars, positions, segments, dark=False), encoding="utf-8")
    render_tool = render_png(out / dark_name, out / png_name)
    star_manifest = []
    for star in stars:
        x, y = positions[star["hip"]]
        e, n = projected[star["hip"]]
        star_manifest.append({"hip": star["hip"], "ra_deg": star["ra_deg"], "dec_deg": star["dec_deg"],
                              "mag_v": star["mag_v"], "gnomonic_east_left_deg": e,
                              "gnomonic_north_up_deg": n, "x_px": round(x, 3), "y_px": round(y, 3)})
    files = {"svg": f"{code}/{dark_name}", "png": f"{code}/{png_name}",
             "import_svg": f"{code}/{import_name}", "import_titled_svg": f"{code}/{title_name}"}
    return {"id": code, "english": english, "chinese": chinese,
            "source_constellation_id": item["id"], "stars": star_manifest,
            "star_count": len(stars), "edges": segments, "edge_count": len(segments),
            "projection": "gnomonic; spherical-vector-mean centre; equal scale; celestial east left and north up",
            "files": files, "svg": files["svg"], "png": files["png"],
            "import_svg": files["import_svg"], "import_titled_svg": files["import_titled_svg"],
            "source_sha256": {"stellarium_modern_index": index_sha,
                              "hipparcos_zodiac_tsv": source_sha},
            "rendered_with": render_tool}


def output_teapot(out_root: Path) -> dict:
    geometry_bytes = TEAPOT_GEOMETRY.read_bytes()
    design = json.loads(geometry_bytes)
    constellation = design["constellation"]
    stars = constellation["stars_local"]
    edges = constellation["edges"]
    if len(stars) != 8 or len(edges) != 11:
        raise ValueError("Expected the retained Sagittarius PCB geometry to have 8 stars and 11 edges")
    centers = {star["id"]: star["center"] for star in stars}
    projected = {star["hip"]: tuple(star["center"]) for star in stars}
    xs = [p[0] for p in projected.values()]
    ys = [p[1] for p in projected.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    scale = (1024 - 2 * MARGIN) / span
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    positions = {star["hip"]: (512 + (star["center"][0] - cx) * scale,
                              512 + (star["center"][1] - cy) * scale) for star in stars}
    hip_by_id = {star["id"]: star["hip"] for star in stars}
    segments = [(hip_by_id[edge["start"]], hip_by_id[edge["end"]]) for edge in edges]
    chart_stars = [{"hip": star["hip"], "ra_deg": 0.0, "dec_deg": 0.0, "mag_v": 2.0} for star in stars]
    chart = out_root / "Sgr" / "sagittarius-pcb-8star-11edge"
    chart.mkdir(parents=True, exist_ok=True)
    names = {"svg": "sgr-pcb-teapot-dark.svg", "png": "sgr-pcb-teapot-dark.png",
             "import_svg": "sgr-pcb-teapot-import.svg"}
    (chart / names["svg"]).write_text(svg_document("Sagittarius PCB teapot scheme | local design geometry", "Sgr",
                                                    "Sagittarius PCB teapot scheme", chart_stars, positions, segments, True), encoding="utf-8")
    (chart / names["import_svg"]).write_text(svg_document(None, "Sgr", "Sagittarius PCB teapot scheme",
                                                           chart_stars, positions, segments, False), encoding="utf-8")
    renderer = render_png(chart / names["svg"], chart / names["png"])
    files = {"svg": f"Sgr/sagittarius-pcb-8star-11edge/{names['svg']}",
             "png": f"Sgr/sagittarius-pcb-8star-11edge/{names['png']}",
             "import_svg": f"Sgr/sagittarius-pcb-8star-11edge/{names['import_svg']}"}
    return {"id": "Sgr-PCB-teapot", "english": "Sagittarius PCB teapot scheme", "chinese": "射手座 PCB 茶壶简化版",
            "stars": [{"hip": star["hip"], "x_local_mm": star["center"][0], "y_local_mm": star["center"][1],
                       "x_px": round(positions[star["hip"]][0], 3), "y_px": round(positions[star["hip"]][1], 3)} for star in stars],
            "star_count": 8, "edges": segments, "edge_count": 11,
            "projection": "local PCB geometry in mm; equal scale; source design orientation retained",
            "files": files, "svg": files["svg"], "png": files["png"], "import_svg": files["import_svg"],
            "source_sha256": {"sagittarius_before_refinement_geometry": sha256(geometry_bytes)},
            "rendered_with": renderer}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-teapot", action="store_true", help="Skip the optional retained 8-star Sagittarius PCB scheme")
    parser.add_argument("--output-dir", type=Path, default=ASSET_DIR)
    args = parser.parse_args()
    try:
        index_bytes = STELLARIUM_INDEX.read_bytes()
        index = json.loads(index_bytes)
        hip_bytes = HIP_FILE.read_bytes()
        hip_data = load_hipparcos(HIP_FILE)
        required_codes = {code for code, _, _ in ZODIACS}
        expected_hips = {int(hip) for entry in index["constellations"]
                         if entry.get("id", "").startswith("CON modern ")
                         and entry["id"].split()[-1] in required_codes
                         for line in entry["lines"] for hip in line}
        if set(hip_data) != expected_hips:
            missing, extra = sorted(expected_hips - set(hip_data)), sorted(set(hip_data) - expected_hips)
            raise ValueError(f"Hipparcos selection mismatch: missing={missing}, extra={extra}")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        charts = []
        for code, english, chinese in ZODIACS:
            item = constellation_source(index, code)
            charts.append(output_chart(code, english, chinese, item, hip_data,
                                       sha256(hip_bytes), sha256(index_bytes), args.output_dir, None))
        if not args.skip_teapot:
            charts.append(output_teapot(args.output_dir))
        manifest = {
            "schema_version": 1,
            "collection": "zodiac-modern",
            "canvas_px": [W, H],
            "source_policy": "Use Stellarium CON modern line arrays verbatim as adjacent HIP pairs; no hand-selected or removed edges.",
            "sources": [
                {"id": "stellarium_modern", "path": "data/sources/20261008T150844925832Z/stellarium_modern_index.json",
                 "sha256": sha256(index_bytes), "license": "CC BY-SA 4.0",
                 "attribution": "Stellarium team, Modern sky culture, CON modern zodiac entries",
                 "url": "https://github.com/Stellarium/stellarium/tree/master/skycultures/modern"},
                {"id": "hipparcos_i239", "path": "../source-zodiac/hipparcos-zodiac.tsv",
                 "sha256": sha256(hip_bytes), "table": "CDS VizieR I/239/hip_main",
                 "fields": ["HIP", "RAICRS", "DEICRS", "Vmag"],
                 "license": "CC BY-NC 3.0 IGO", "attribution": "Credit: ESA",
                 "citation": "ESA 1997, The Hipparcos and Tycho Catalogues, ESA SP-1200; 1997HIP...C......0E",
                 "url": "https://www.cosmos.esa.int/web/hipparcos/catalogues",
                 "coordinate_frame": "ICRS", "coordinate_epoch": "J1991.25"}
            ],
            "licensing_note": "Local reference use only. Stellarium source data is CC BY-SA 4.0. Hipparcos catalogue data is CC BY-NC 3.0 IGO and requires Credit: ESA. No commercial permission is inferred; check both source terms before redistribution or commercial use.",
            "charts": charts,
        }
        path = args.output_dir / "manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(f"Wrote {len(charts)} charts to {args.output_dir}; {sum(c['star_count'] for c in charts)} star entries, {sum(c['edge_count'] for c in charts)} edges")
        return 0
    except Exception as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
