"""Render a read-only two-face core PCB layout preview from saved EasyEDA logs."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle
from matplotlib.transforms import Affine2D

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "eda" / "native" / "core-source.jsonl"
PADS = ROOT / "eda" / "core-pads.json"
BOM = ROOT / "electrical" / "BOM.csv"
AUDIT = ROOT / "electrical" / "native-copper-audit.json"
OUT_PNG = ROOT / "geometry" / "core-layout-review-v3.png"
OUT_SVG = ROOT / "geometry" / "core-layout-review-v3.svg"
MM_PER_MIL = 0.0254


def read_latest(path: Path) -> dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]]:
    latest: dict[tuple[str, str], tuple[int, dict[str, Any], dict[str, Any]]] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            meta_text, data_text = raw.split("||", 1)
            meta = json.loads(meta_text)
            data = json.loads(data_text.rstrip("|"))
        except Exception as exc:
            raise ValueError(f"Cannot parse {path}:{number}: {exc}") from exc
        if meta.get("type") == "DOCHEAD":
            continue
        key = (meta.get("type", ""), meta.get("id", meta.get("type", "")))
        ticket = int(meta.get("ticket", 0))
        if key not in latest or ticket >= latest[key][0]:
            latest[key] = (ticket, meta, data)
    return {key: (meta, data) for key, (_, meta, data) in latest.items()}


def numeric_points(raw: Any) -> list[tuple[float, float]]:
    nums = [float(v) for v in raw if isinstance(v, (int, float))]
    if len(nums) < 6 or len(nums) % 2:
        raise ValueError("Expected a closed path containing at least three XY points")
    return [(nums[i] * MM_PER_MIL, nums[i + 1] * MM_PER_MIL) for i in range(0, len(nums), 2)]


def points_from_path(path: Any) -> list[tuple[float, float]]:
    # FILL paths are nested, while layer-11 POLY paths are flat.
    if path and isinstance(path[0], list):
        path = path[0]
    return numeric_points(path)


def view_xy(x: float, y: float, mirrored: bool) -> tuple[float, float]:
    return (-x if mirrored else x, y)


def plot_pad(ax, pad: dict[str, Any], mirrored: bool, color: str) -> None:
    x = float(pad["x"]) * MM_PER_MIL
    y = float(pad["y"]) * MM_PER_MIL
    shape = pad["pad"][0].upper()
    w = float(pad["pad"][1]) * MM_PER_MIL
    h = float(pad["pad"][2]) * MM_PER_MIL
    angle = float(pad.get("rotation", 0) or 0)
    corners = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]
    points = []
    a = math.radians(angle)
    for dx, dy in corners:
        px = x + dx * math.cos(a) - dy * math.sin(a)
        py = y + dx * math.sin(a) + dy * math.cos(a)
        points.append(view_xy(px, py, mirrored))
    if shape in ("ELLIPSE", "OVAL", "CIRCLE"):
        center = view_xy(x, y, mirrored)
        patch = Circle(center, radius=max(w, h)/2, facecolor=color, edgecolor="#342b24", linewidth=0.25, zorder=5)
        ax.add_patch(patch)
    else:
        ax.add_patch(Polygon(points, closed=True, facecolor=color, edgecolor="#342b24", linewidth=0.25, zorder=5))


def body_size(ref: str, bom: dict[str, dict[str, str]]) -> tuple[float, float]:
    row = bom.get(ref, {})
    package = row.get("Package", "")
    if "XQFN8" in package:
        return (1.6, 1.6)
    if "0402" in package:
        return (1.0, 0.5)
    return (1.6, 0.8)


def draw_body(ax, x: float, y: float, angle: float, w: float, h: float, mirrored: bool) -> None:
    x, y = view_xy(x, y, mirrored)
    rect = Rectangle((x-w/2, y-h/2), w, h, facecolor="#fffdf7", edgecolor="#252525", linewidth=0.45, alpha=0.93, zorder=4)
    transform = Affine2D().rotate_deg_around(x, y, -angle if mirrored else angle) + ax.transData
    rect.set_transform(transform)
    ax.add_patch(rect)


def plot_trace(ax, d: dict[str, Any], mirrored: bool, color: str) -> None:
    a = view_xy(float(d["startX"]) * MM_PER_MIL, float(d["startY"]) * MM_PER_MIL, mirrored)
    b = view_xy(float(d["endX"]) * MM_PER_MIL, float(d["endY"]) * MM_PER_MIL, mirrored)
    linewidth = max(0.45, float(d.get("width", 8)) * MM_PER_MIL * 6.5)
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, linewidth=linewidth,
            solid_capstyle="round", zorder=2)


def add_label(ax, text: str, xy: tuple[float, float], offset: tuple[float, float], color: str = "#202020") -> None:
    ax.annotate(text, xy=xy, xytext=(xy[0] + offset[0], xy[1] + offset[1]),
                textcoords="data", ha="center", va="center", fontsize=6.4, color=color,
                bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "#999999", "linewidth": 0.35, "alpha": 0.96},
                arrowprops={"arrowstyle": "-", "color": "#777777", "linewidth": 0.45, "shrinkA": 2, "shrinkB": 2},
                zorder=10)


def main() -> None:
    records = read_latest(NATIVE)
    components = json.loads(PADS.read_text(encoding="utf-8"))
    with BOM.open(encoding="utf-8-sig", newline="") as f:
        bom = {r["Designator"]: r for r in csv.DictReader(f)}
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))

    outline_items = [(m, d) for (kind, _), (m, d) in records.items() if kind == "POLY" and d.get("layerId") == 11]
    if len(outline_items) != 1:
        raise ValueError(f"Expected one saved board outline; got {len(outline_items)}")
    outline = points_from_path(outline_items[0][1]["path"])
    if outline[0] != outline[-1]:
        outline.append(outline[0])

    top_lines = [(m, d) for (kind, _), (m, d) in records.items() if kind == "LINE" and d.get("layerId") == 1]
    bottom_lines = [(m, d) for (kind, _), (m, d) in records.items() if kind == "LINE" and d.get("layerId") == 2]
    fills = [(m, d) for (kind, _), (m, d) in records.items() if kind == "FILL" and d.get("layerId") in (1, 2)]
    vias = [(m, d) for (kind, _), (m, d) in records.items() if kind == "VIA"]
    free_pads = [(m, d) for (kind, _), (m, d) in records.items() if kind == "PAD" and d.get("layerId") in (1, 2)]

    fig, axes = plt.subplots(1, 2, figsize=(14.6, 8.0), constrained_layout=True)
    fig.suptitle("NFC 核心板 · 实际铜层与器件布局", fontsize=16, fontweight="bold")
    views = [
        (axes[0], "顶面 TOP（从顶面观察）", False, 1, top_lines, "#c14e33", "#f1a348"),
        (axes[1], "底面 BOTTOM（从外侧观察，X 镜像 x→−x）", True, 2, bottom_lines, "#315f9b", "#6d93c2"),
    ]
    label_offsets = {
        "U1": (0.0, -1.45), "C1": (3.0, 0.85), "CT1": (-3.0, 0.85), "CT2": (0.4, 1.25),
        "R5": (-3.15, -1.55), "R6": (3.1, -1.55), "R7": (-0.3, -1.55),
        "R1": (-4.0, 0.85), "R2": (3.4, 1.35), "D1": (-6.5, -0.9), "D2": (6.6, 0.3),
        "R3": (3.8, 1.0), "R4": (-3.6, -0.9), "D3": (6.8, -0.8), "D4": (-6.8, 0.3),
    }
    for ax, title, mirrored, layer, lines, copper_color, fill_color in views:
        # Actual layer-11 board profile.
        frame = [view_xy(x, y, mirrored) for x, y in outline]
        ax.add_patch(Polygon(frame, closed=True, fill=False, edgecolor="#222222", linewidth=1.65, zorder=8))

        # 30 mm across-flats internal-window registration reference.
        af30_r = 15.0 / math.cos(math.pi/8)
        win = [(af30_r*math.cos(math.radians(22.5 + k*45)), af30_r*math.sin(math.radians(22.5 + k*45))) for k in range(8)]
        if mirrored:
            win = [(-x, y) for x, y in win]
        ax.add_patch(Polygon(win, closed=True, fill=False, edgecolor="#21806a", linewidth=0.9, linestyle=(0, (3, 2)), zorder=1))
        ax.text(0, 16.0, "30 mm AF 内窗基准", ha="center", va="bottom", fontsize=7.2, color="#176d5c", zorder=9)

        # Copper lines and antenna fill from the current saved source.
        for _, d in lines:
            plot_trace(ax, d, mirrored, copper_color)
        for _, d in fills:
            if int(d.get("layerId", 0)) != layer:
                continue
            pts = points_from_path(d["path"])
            if mirrored:
                pts = [(-x, y) for x, y in pts]
            ax.add_patch(Polygon(pts, closed=True, facecolor=fill_color, edgecolor=copper_color,
                                 linewidth=0.28, alpha=0.78, zorder=1.7))
        for _, d in vias:
            x, y = view_xy(float(d["centerX"])*MM_PER_MIL, float(d["centerY"])*MM_PER_MIL, mirrored)
            dia = float(d["viaDiameter"])*MM_PER_MIL
            drill = float(d["holeDiameter"])*MM_PER_MIL
            ax.add_patch(Circle((x, y), dia/2, facecolor=copper_color, edgecolor="#292929", linewidth=0.25, zorder=3))
            ax.add_patch(Circle((x, y), drill/2, facecolor="white", edgecolor="#333333", linewidth=0.2, zorder=4))

        # Component pads and packages for the face being viewed.
        visible_refs = []
        for comp in components:
            ref = comp["ref"]
            side_layer = comp["pins"][0]["layer"]
            if side_layer != layer:
                continue
            visible_refs.append(ref)
            coords = [(float(p["x"])*MM_PER_MIL, float(p["y"])*MM_PER_MIL) for p in comp["pins"]]
            cx = sum(x for x, _ in coords)/len(coords)
            cy = sum(y for _, y in coords)/len(coords)
            angle = float(comp["pins"][0].get("componentRotation", 0) or 0)
            if ref == "U1":
                w, h = 1.6, 1.6
            else:
                w, h = body_size(ref, bom)
            draw_body(ax, cx, cy, angle, w, h, mirrored)
            for pin in comp["pins"]:
                if int(pin["layer"]) == layer:
                    plot_pad(ax, pin, mirrored, copper_color)
            vx, vy = view_xy(cx, cy, mirrored)
            add_label(ax, ref, (vx, vy), label_offsets[ref])

        # Top-side probe pads are physical top copper and appear only on TOP.
        if layer == 1:
            for _, d in free_pads:
                if int(d.get("layerId", 0)) != 1:
                    continue
                x, y = view_xy(float(d["centerX"])*MM_PER_MIL, float(d["centerY"])*MM_PER_MIL, mirrored)
                shape = d.get("defaultPad", {})
                dia = float(shape.get("width", 31.4961))*MM_PER_MIL
                ax.add_patch(Circle((x, y), dia/2, facecolor=copper_color, edgecolor="#292929", linewidth=0.35, zorder=6))
                ax.add_patch(Circle((x, y), 0.22, facecolor="none", edgecolor="white", linewidth=0.45, zorder=7))
                ax.text(x+0.55, y+0.55, d.get("num", "TP"), fontsize=6.3, color="#202020",
                        bbox={"boxstyle":"round,pad=0.1","facecolor":"white","edgecolor":"#888","linewidth":0.3}, zorder=10)

        ax.set_title(title, fontsize=11, pad=8)
        ax.set_aspect("equal")
        ax.set_xlim(-21.3, 21.3)
        ax.set_ylim(-21.3, 21.3)
        ax.set_xlabel("X (mm)" + (" · 已作 X 镜像" if mirrored else ""), fontsize=8)
        ax.set_ylabel("Y (mm)", fontsize=8)
        ax.grid(color="#d9d9d9", linewidth=0.35, alpha=0.6)
        ax.tick_params(labelsize=7)
        ax.text(0.02, 0.02, f"实际器件 {len(visible_refs)} 个 · 实际 {('L1' if layer == 1 else 'L2')} 铜层",
                transform=ax.transAxes, ha="left", va="bottom", fontsize=7, color="#333333",
                bbox={"boxstyle":"round,pad=0.25","facecolor":"white","edgecolor":"#aaaaaa","alpha":0.9}, zorder=12)

    board_min = audit["check_1_core_boundary_and_clearance"]["minimum_same_layer_copper_gap"]["gap_mm"]
    fig.text(0.5, -0.005,
             "完整器件位号：U1、C1、CT1、CT2、R1–R7、D1–D4；TP1/TP2 为顶层测试点。"
             f"  |  最新铜审计最小异网铜距 {board_min:.5f} mm。",
             ha="center", va="top", fontsize=8.2, color="#303030")
    fig.savefig(OUT_PNG, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT_SVG, bbox_inches="tight", facecolor="white")
    # Normalize generated SVG whitespace for stable Git/archive byte hashes.
    OUT_SVG.write_bytes(("\n".join(line.rstrip() for line in OUT_SVG.read_text(encoding="utf-8").splitlines()) + "\n").encode("utf-8"))
    plt.close(fig)
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_SVG}")
    print(f"Top components: {sum(1 for c in components if c['pins'][0]['layer']==1)}; bottom components: {sum(1 for c in components if c['pins'][0]['layer']==2)}; free pads: {len(free_pads)}")
    print(f"Native lines: top={len(top_lines)}, bottom={len(bottom_lines)}; fills={len(fills)}; vias={len(vias)}")


if __name__ == "__main__":
    main()
