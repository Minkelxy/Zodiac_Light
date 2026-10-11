"""Render a read-only review of the saved symmetric core and two aperture layouts."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle
from matplotlib.transforms import Affine2D
from shapely.geometry import LineString

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "variants" / "common"
NATIVE = COMMON / "eda" / "native" / "core-source.jsonl"
PADS = COMMON / "eda" / "core-pads.json"
BOM = ROOT / "electrical" / "BOM.csv"
SAG_GEOMETRY = ROOT / "geometry" / "design.json"
LEO_GEOMETRY = ROOT / "variants" / "snake-leo" / "leo-geometry.json"
OUT = COMMON / "layout-review"
OUT_PNG = OUT / "symmetric-core-layout-review.png"
OUT_SVG = OUT / "symmetric-core-layout-review.svg"
OUT_VALIDATION = OUT / "validation.json"
MM_PER_MIL = 0.0254


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_latest(path: Path) -> dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]]:
    latest: dict[tuple[str, str], tuple[int, dict[str, Any], dict[str, Any]]] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            meta_text, data_text = raw.split("||", 1)
            meta = json.loads(meta_text)
            data = json.loads(data_text.rstrip("|"))
        except Exception as exc:
            raise ValueError(f"Cannot parse {path}:{line_no}: {exc}") from exc
        if meta.get("type") == "DOCHEAD":
            continue
        key = (str(meta.get("type", "")), str(meta.get("id", meta.get("type", ""))))
        ticket = int(meta.get("ticket", 0))
        if key not in latest or ticket >= latest[key][0]:
            latest[key] = (ticket, meta, data)
    return {key: (meta, data) for key, (_, meta, data) in latest.items()}


def numeric_points(raw: Any) -> list[tuple[float, float]]:
    if raw and isinstance(raw[0], list):
        raw = raw[0]
    nums = [float(v) for v in raw if isinstance(v, (int, float))]
    if len(nums) < 6 or len(nums) % 2:
        raise ValueError("Expected a flat path containing at least three XY points")
    return [(nums[i] * MM_PER_MIL, nums[i + 1] * MM_PER_MIL) for i in range(0, len(nums), 2)]


def view_xy(x: float, y: float, mirror_x: bool) -> tuple[float, float]:
    return (-x if mirror_x else x, y)


def octagon(af: float) -> list[tuple[float, float]]:
    h = af / 2
    k = h * (math.sqrt(2) - 1)
    return [(-k, -h), (k, -h), (h, -k), (h, k), (k, h), (-k, h), (-h, k), (-h, -k)]


def center_of(comp: dict[str, Any]) -> tuple[float, float]:
    pins = comp["pins"]
    return (sum(float(p["x"]) for p in pins) / len(pins) * MM_PER_MIL,
            sum(float(p["y"]) for p in pins) / len(pins) * MM_PER_MIL)


def package_size(ref: str, bom: dict[str, dict[str, str]]) -> tuple[float, float]:
    package = bom.get(ref, {}).get("Package", "")
    if "XQFN8" in package:
        return 1.6, 1.6
    if "0402" in package:
        return 1.0, 0.5
    return 1.6, 0.8


def draw_body(ax, x: float, y: float, angle: float, w: float, h: float, mirror_x: bool) -> None:
    x, y = view_xy(x, y, mirror_x)
    rect = Rectangle((x - w / 2, y - h / 2), w, h, facecolor="#fffdf7", edgecolor="#252525",
                     linewidth=0.45, alpha=0.94, zorder=4)
    rect.set_transform(Affine2D().rotate_deg_around(x, y, -angle if mirror_x else angle) + ax.transData)
    ax.add_patch(rect)


def draw_pad(ax, pad: dict[str, Any], mirror_x: bool, color: str) -> None:
    x, y = view_xy(float(pad["x"]) * MM_PER_MIL, float(pad["y"]) * MM_PER_MIL, mirror_x)
    shape = str(pad["pad"][0]).upper()
    w, h = float(pad["pad"][1]) * MM_PER_MIL, float(pad["pad"][2]) * MM_PER_MIL
    angle = -float(pad.get("rotation", 0) or 0) if mirror_x else float(pad.get("rotation", 0) or 0)
    if shape in ("ELLIPSE", "OVAL", "CIRCLE"):
        ax.add_patch(Circle((x, y), max(w, h) / 2, facecolor=color, edgecolor="#342b24", linewidth=0.25, zorder=5))
        return
    corners = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]
    a = math.radians(angle)
    pts = [(x + dx*math.cos(a) - dy*math.sin(a), y + dx*math.sin(a) + dy*math.cos(a)) for dx, dy in corners]
    ax.add_patch(Polygon(pts, closed=True, facecolor=color, edgecolor="#342b24", linewidth=0.25, zorder=5))


def draw_trace(ax, d: dict[str, Any], mirror_x: bool, color: str) -> None:
    a = view_xy(float(d["startX"]) * MM_PER_MIL, float(d["startY"]) * MM_PER_MIL, mirror_x)
    b = view_xy(float(d["endX"]) * MM_PER_MIL, float(d["endY"]) * MM_PER_MIL, mirror_x)
    lw = max(0.42, float(d.get("width", 8)) * MM_PER_MIL * 6.5)
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, linewidth=lw, solid_capstyle="round", zorder=2)


def draw_led_anchor(ax, x: float, y: float, ref: str, marker: str, face: str, edge: str, text_offset: tuple[float, float]) -> None:
    ax.scatter([x], [y], s=46, marker=marker, c=[face], edgecolors=[edge], linewidths=1.0, zorder=9)
    ax.annotate(ref, (x, y), xytext=(x + text_offset[0], y + text_offset[1]), textcoords="data",
                fontsize=7, ha="center", va="center", color="#171717",
                bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "#888", "linewidth": 0.35, "alpha": 0.95},
                arrowprops={"arrowstyle": "-", "color": "#777", "linewidth": 0.45}, zorder=10)


def draw_core_view(ax, title: str, layer: int, lines: list[dict[str, Any]], fills: list[dict[str, Any]],
                   vias: list[dict[str, Any]], components: list[dict[str, Any]], bom: dict[str, dict[str, str]],
                   outline: list[tuple[float, float]], free_pads: list[dict[str, Any]], led_positions: dict[str, tuple[float, float]]) -> None:
    mirror_x = layer == 2
    color = "#bf523d" if layer == 1 else "#315f9b"
    fill_color = "#f2a54e" if layer == 1 else "#799ac5"
    edge = [view_xy(x, y, mirror_x) for x, y in outline]
    ax.add_patch(Polygon(edge, closed=True, fill=False, edgecolor="#202020", linewidth=1.6, zorder=8))
    af30 = [view_xy(x, y, mirror_x) for x, y in octagon(30)]
    ax.add_patch(Polygon(af30, closed=True, fill=False, edgecolor="#17806d", linewidth=0.85,
                         linestyle=(0, (3, 2)), zorder=1))
    for d in lines:
        draw_trace(ax, d, mirror_x, color)
    for d in fills:
        if int(d.get("layerId", 0)) != layer:
            continue
        pts = numeric_points(d["path"])
        if mirror_x:
            pts = [(-x, y) for x, y in pts]
        ax.add_patch(Polygon(pts, closed=True, facecolor=fill_color, edgecolor=color, linewidth=0.28, alpha=0.75, zorder=1.5))
    for d in vias:
        x, y = view_xy(float(d["centerX"]) * MM_PER_MIL, float(d["centerY"]) * MM_PER_MIL, mirror_x)
        dia = float(d["viaDiameter"]) * MM_PER_MIL
        drill = float(d["holeDiameter"]) * MM_PER_MIL
        ax.add_patch(Circle((x, y), dia/2, facecolor=color, edgecolor="#222", linewidth=0.25, zorder=3))
        ax.add_patch(Circle((x, y), drill/2, facecolor="white", edgecolor="#333", linewidth=0.2, zorder=4))
    visible = []
    for comp in components:
        ref = comp["ref"]
        side = int(comp["pins"][0]["layer"])
        if side != layer:
            continue
        visible.append(ref)
        x, y = center_of(comp)
        angle = float(comp["pins"][0].get("componentRotation", 0) or 0)
        w, h = (1.6, 1.6) if ref == "U1" else package_size(ref, bom)
        draw_body(ax, x, y, angle, w, h, mirror_x)
        for pin in comp["pins"]:
            if int(pin["layer"]) == layer:
                draw_pad(ax, pin, mirror_x, color)
        vx, vy = view_xy(x, y, mirror_x)
        offsets = {"U1": (0, -1.55), "C1": (2.7, 0.85), "CT1": (-2.7, 0.9), "CT2": (0.0, 1.3),
                   "R1": (-3.4, 0.9), "R2": (2.9, 1.2), "R3": (-3.4, -0.9), "R4": (2.9, -1.0),
                   "R5": (-3.0, -1.4), "R6": (3.0, -1.4), "R7": (0.0, -1.4),
                   "D1": (-5.0, -0.65), "D2": (5.0, -0.65), "D3": (-5.0, -0.65), "D4": (5.0, -0.65)}
        if not ref.startswith("D"):
            ax.annotate(ref, (vx, vy), xytext=(vx + offsets.get(ref, (0, 1))[0], vy + offsets.get(ref, (0, 1))[1]),
                        textcoords="data", fontsize=6, ha="center", va="center",
                        bbox={"boxstyle": "round,pad=0.1", "facecolor": "white", "edgecolor": "#888", "linewidth": 0.3, "alpha": 0.96},
                        arrowprops={"arrowstyle": "-", "color": "#777", "linewidth": 0.4}, zorder=10)
    if layer == 1:
        for d in free_pads:
            if int(d.get("layerId", 0)) != 1:
                continue
            x, y = view_xy(float(d["centerX"]) * MM_PER_MIL, float(d["centerY"]) * MM_PER_MIL, False)
            dia = float(d.get("defaultPad", {}).get("width", 31.4961)) * MM_PER_MIL
            ax.add_patch(Circle((x, y), dia/2, facecolor=color, edgecolor="#222", linewidth=0.35, zorder=6))
            ax.text(x+0.55, y+0.55, d.get("num", "TP"), fontsize=5.9,
                    bbox={"boxstyle": "round,pad=0.1", "facecolor": "white", "edgecolor": "#888", "linewidth": 0.3}, zorder=10)
    # Physical exterior view: bottom X is mirrored relative to native core coordinates.
    if layer == 1:
        for ref in ("D1", "D2"):
            x, y = view_xy(*led_positions[ref], False)
            draw_led_anchor(ax, x, y, f"{ref} ({x:+.2f}, {y:+.2f})", "o" if ref == "D1" else "^", "#f18b44", "#7f351a", (-4.2 if ref == "D1" else 4.2, -2.0))
    else:
        for ref in ("D3", "D4"):
            x, y = view_xy(*led_positions[ref], True)
            draw_led_anchor(ax, x, y, f"{ref} ({x:+.2f}, {y:+.2f})", "s" if ref == "D3" else "D", "#78a8e0", "#234b78", (-4.2 if ref == "D4" else 4.2, 2.0))
    ax.set_title(title, fontsize=11, pad=7)
    ax.set_aspect("equal")
    ax.set_xlim(-20.8, 20.8)
    ax.set_ylim(-20.8, 20.8)
    ax.set_xlabel("Physical-view X (mm)" + (" · bottom X mirrored" if mirror_x else ""), fontsize=7.5)
    ax.set_ylabel("Native Y-up (mm)", fontsize=7.5)
    ax.grid(color="#d9d9d9", linewidth=0.35, alpha=0.6)
    ax.tick_params(labelsize=6.5)
    population_note = " (CT2 DNP)" if layer == 1 else ""
    ax.text(0.02, 0.02, f"{len(visible)} placed footprints{population_note} · actual L{layer} copper", transform=ax.transAxes,
            ha="left", va="bottom", fontsize=6.7, color="#333",
            bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": "#aaa", "alpha": 0.92}, zorder=12)


def draw_constellation(ax, title: str, stars: list[dict[str, Any]], slots: list[dict[str, Any]], *, y_inverted: bool) -> None:
    ax.add_patch(Polygon(octagon(37), closed=True, fill=False, edgecolor="#222", linewidth=1.3, zorder=5))
    ax.add_patch(Polygon(octagon(30), closed=True, fill=False, edgecolor="#17806d", linewidth=0.8,
                         linestyle=(0, (3, 2)), zorder=1))
    for slot in slots:
        a = slot.get("centerline_start", slot.get("endpoint_a"))
        b = slot.get("centerline_end", slot.get("endpoint_b"))
        if a is None or b is None:
            raise ValueError(f"Aperture record lacks a centerline: {slot.get('id', '<unnamed>')}")
        width = float(slot.get("width_mm", 1.0))
        shape = LineString([tuple(a), tuple(b)]).buffer(width/2, cap_style="round", join_style="round", quad_segs=12)
        ax.add_patch(Polygon(list(shape.exterior.coords), closed=True, facecolor="#e4ad57", edgecolor="#996b29", linewidth=0.3, zorder=3))
    for i, star in enumerate(stars, 1):
        x, y = star.get("center", star.get("center_mm"))
        dia = float(star.get("diameter_mm", 0.8))
        ax.add_patch(Circle((x, y), dia/2, facecolor="#334b67", edgecolor="white", linewidth=0.45, zorder=4))
        ax.text(x + 0.45, y - 0.45, str(i), fontsize=5.3, color="#25364a", ha="center", va="center", zorder=6)
    # LED markers are physical-side projection positions only; these rings encode side and do not imply light output.
    for x, y, ref, marker, color in [(-6, 0, "D1 Top", "o", "#e57532"), (6, 0, "D2 Top", "^", "#e57532"),
                                     (6, 0, "D3 Bottom", "s", "#3f76b5"), (-6, 0, "D4 Bottom", "D", "#3f76b5")]:
        ax.scatter([x], [y], s=30, marker=marker, facecolors="none", edgecolors=color, linewidths=1.1, zorder=9)
    ax.set_title(title, fontsize=10, pad=6)
    ax.set_aspect("equal")
    ax.set_xlim(-20.7, 20.7)
    ax.set_ylim((20.7, -20.7) if y_inverted else (-20.7, 20.7))
    ax.set_xlabel("Rear exterior X right (mm)", fontsize=7.2)
    ax.set_ylabel("Rear exterior Y down (mm)", fontsize=7.2)
    ax.grid(color="#d9d9d9", linewidth=0.35, alpha=0.55)
    ax.tick_params(labelsize=6.2)
    ax.text(0.02, 0.02, f"{len(stars)} × Ø0.8 holes · {len(slots)} × 1.0 slots · position overlay only",
            transform=ax.transAxes, fontsize=6.5, ha="left", va="bottom",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "edgecolor": "#aaa", "alpha": 0.95}, zorder=12)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = [NATIVE, PADS, BOM, SAG_GEOMETRY, LEO_GEOMETRY]
    input_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
    records = read_latest(NATIVE)
    components = json.loads(PADS.read_text(encoding="utf-8"))
    with BOM.open(encoding="utf-8-sig", newline="") as stream:
        bom = {row["Designator"]: row for row in csv.DictReader(stream)}
    sag = json.loads(SAG_GEOMETRY.read_text(encoding="utf-8"))
    leo = json.loads(LEO_GEOMETRY.read_text(encoding="utf-8"))

    outlines = [(m, d) for (kind, _), (m, d) in records.items() if kind == "POLY" and int(d.get("layerId", 0)) == 11]
    if len(outlines) != 1:
        raise ValueError(f"Expected one core AF37 outline, found {len(outlines)}")
    outline = numeric_points(outlines[0][1]["path"])
    if outline[0] != outline[-1]:
        outline.append(outline[0])
    top_lines = [d for (kind, _), (_, d) in records.items() if kind == "LINE" and int(d.get("layerId", 0)) == 1]
    bottom_lines = [d for (kind, _), (_, d) in records.items() if kind == "LINE" and int(d.get("layerId", 0)) == 2]
    fills = [d for (kind, _), (_, d) in records.items() if kind == "FILL" and int(d.get("layerId", 0)) in (1, 2)]
    vias = [d for (kind, _), (_, d) in records.items() if kind == "VIA"]
    free_pads = [d for (kind, _), (_, d) in records.items() if kind == "PAD" and int(d.get("layerId", 0)) in (1, 2)]
    by_ref = {c["ref"]: c for c in components}
    led_native_mils: dict[str, tuple[float, float]] = {}
    for (kind, _), (_, d) in records.items():
        if kind != "COMPONENT":
            continue
        ref = d.get("attrs", {}).get("Unique ID")
        if ref in ("D1", "D2", "D3", "D4"):
            if ref in led_native_mils:
                raise ValueError(f"Duplicate saved component anchor for {ref}")
            led_native_mils[ref] = (float(d["x"]), float(d["y"]))
    if set(led_native_mils) != {"D1", "D2", "D3", "D4"}:
        raise ValueError(f"Missing saved component anchors: {sorted(led_native_mils)}")
    led_positions = {ref: (x * MM_PER_MIL, y * MM_PER_MIL) for ref, (x, y) in led_native_mils.items()}
    pad_centroids = {ref: center_of(by_ref[ref]) for ref in ("D1", "D2", "D3", "D4")}
    expected_native_x = {"D1": -236.2205 * MM_PER_MIL, "D2": 236.2205 * MM_PER_MIL,
                         "D3": -236.2205 * MM_PER_MIL, "D4": 236.2205 * MM_PER_MIL}
    placement_checks = {ref: {"native_mm": [x, y], "expected_native_mm": [expected_native_x[ref], 0.0],
                              "pass": abs(x - expected_native_x[ref]) <= 1e-6 and abs(y) <= 1e-9}
                        for ref, (x, y) in led_positions.items()}
    if not all(v["pass"] for v in placement_checks.values()):
        raise ValueError(f"Saved core is not the requested symmetric LED layout: {placement_checks}")
    pad_centroid_checks = {ref: {"pad_centroid_native_mm": list(pad_centroids[ref]),
                                 "component_anchor_delta_mm": [pad_centroids[ref][0] - led_positions[ref][0],
                                                                pad_centroids[ref][1] - led_positions[ref][1]]}
                           for ref in led_positions}
    physical_leds = {"top": {"D1": [-6.0, 0.0], "D2": [6.0, 0.0]},
                     "bottom_exterior": {"D3": [6.0, 0.0], "D4": [-6.0, 0.0]}}
    sag_stars = sag["constellation"]["stars_local"]
    sag_slots = sag["constellation"]["edges"]
    leo_stars = leo["constellation"]["stars"]
    leo_slots = leo["constellation"]["physical_slots"]

    fig, axs = plt.subplots(2, 2, figsize=(14.2, 10.4), gridspec_kw={
        "left": 0.075, "right": 0.97, "bottom": 0.095, "top": 0.90, "wspace": 0.22, "hspace": 0.25})
    fig.suptitle("双面核心板：LED 对称位置与两种星图开孔叠装检查", fontsize=15, fontweight="bold", y=0.985)
    fig.text(0.5, 0.952,
             "上排为实际保存的Top/Bottom铜与器件；下排为射手座/狮子座孔槽位置叠图。仅核对位置，不预测亮度。",
             ha="center", va="top", fontsize=9, color="#394552")
    draw_core_view(axs[0, 0], "顶面 TOP 外侧视图 · 原生 X/Y", 1, top_lines, fills, vias, components, bom, outline, free_pads, led_positions)
    draw_core_view(axs[0, 1], "底面 BOTTOM 外侧视图 · X 镜像", 2, bottom_lines, fills, vias, components, bom, outline, free_pads, led_positions)
    draw_constellation(axs[1, 0], "马 + 射手座 · 外侧后盖孔槽位置", sag_stars, sag_slots, y_inverted=True)
    draw_constellation(axs[1, 1], "蛇 + 狮子座 · 外侧后盖孔槽位置", leo_stars, leo_slots, y_inverted=True)
    fig.text(0.5, 0.018,
             "LED中心：Top D1/D2 = (−6,0)/(+6,0) mm；Bottom 原生 D3/D4 = (−6,0)/(+6,0) mm，外侧视图 X 翻转。"
             " AF37 为板外形；虚线 AF30 是叠装窗基准。星图与LED仅作平面位置叠图，不含光学/亮度模型。",
             ha="center", va="bottom", fontsize=8.1, color="#303942")
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT_SVG, bbox_inches="tight", facecolor="white")
    OUT_SVG.write_bytes(("\n".join(x.rstrip() for x in OUT_SVG.read_text(encoding="utf-8").splitlines()) + "\n").encode("utf-8"))
    plt.close(fig)

    validation = {
        "status": "passed",
        "purpose": "Read-only visual review of saved symmetric core, AF37/AF30 references, and Sagittarius/Leo aperture locations; not a brightness prediction.",
        "source_hashes_sha256": input_hashes,
        "saved_led_centers_native_core_mm": led_positions,
        "pad_centroid_led_centers_native_core_mm": pad_centroids,
        "pad_centroid_vs_component_anchor": pad_centroid_checks,
        "symmetric_led_checks": placement_checks,
        "physical_view_led_centers_mm": physical_leds,
        "core_counts": {"component_footprints": len(components), "top_footprints": sum(1 for c in components if int(c["pins"][0]["layer"]) == 1),
                        "bottom_footprints": sum(1 for c in components if int(c["pins"][0]["layer"]) == 2),
                        "dnp_top_footprints": ["CT2"], "top_lines": len(top_lines), "bottom_lines": len(bottom_lines),
                        "fills": len(fills), "vias": len(vias), "free_pads": len(free_pads)},
        "aperture_counts": {"sagittarius_stars": len(sag_stars), "sagittarius_slots": len(sag_slots),
                            "leo_stars": len(leo_stars), "leo_slots": len(leo_slots)},
        "coordinate_convention": {
            "core_native": "mil, +X right and +Y up; top physical view is direct, bottom physical exterior view mirrors X.",
            "constellation": "board-center origin, mm, rear exterior view +X right and +Y down.",
            "window": "AF37 is the saved core outline; dashed AF30 is an overlay registration reference, not a core cutout.",
        },
        "outputs_sha256": {OUT_PNG.relative_to(ROOT).as_posix(): sha(OUT_PNG), OUT_SVG.relative_to(ROOT).as_posix(): sha(OUT_SVG)},
        "source_pngs_modified": False,
        "limitations": ["Position overlays show physical openings and nominal LED centers only.",
                        "No irradiance, material transmission, diffuser, or brightness uniformity is modeled."],
    }
    OUT_VALIDATION.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs} != input_hashes:
        raise RuntimeError("An input changed while rendering; review outputs and rerun against a stable snapshot")
    print(json.dumps({"status": validation["status"], "outputs": [str(OUT_PNG), str(OUT_SVG), str(OUT_VALIDATION)],
                      "checks": placement_checks, "counts": validation["aperture_counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
