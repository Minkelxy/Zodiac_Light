"""Build isolated Sagittarius face style proofs from the current reviewed SVG.

This script only writes to artwork/star-style-study-v1/. It never edits the
active artwork, geometry, EasyEDA project, or manufacturing outputs.
"""
from __future__ import annotations

import json
import hashlib
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artwork" / "star-style-study-v1"
SOURCE = ROOT / "artwork" / "sagittarius_face.svg"
NODE = Path(r"C:\Users\20177\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")
SHARP = Path(r"C:\Users\20177\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\sharp")
NS = "http://www.w3.org/2000/svg"
INK = "#eee8d6"
DARK = "#17232f"
WHITE = "#ffffff"
WARM = "#fff1c5"


def tag(name: str) -> str:
    return f"{{{NS}}}{name}"


def coord_pairs(points: str) -> list[tuple[float, float]]:
    nums = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", points)]
    return list(zip(nums[::2], nums[1::2]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_sha_before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    root = ET.parse(SOURCE).getroot()
    children = list(root)
    board_points: list[tuple[float, float]] = []
    ink_elements: list[ET.Element] = []
    slots: list[tuple[str, tuple[float, float], tuple[float, float], str, float]] = []
    stars: list[tuple[str, float, float, float]] = []
    for el in children:
        ident = el.attrib.get("id", "")
        if el.tag == tag("polygon") and not ident:
            board_points = coord_pairs(el.attrib["points"])
        elif ident.startswith("slot_"):
            vals = [float(v) for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)", el.attrib["d"])]
            slots.append((ident.removeprefix("slot_"), (vals[0], vals[1]), (vals[2], vals[3]), el.attrib["d"], float(el.attrib["stroke-width"])))
        elif el.tag == tag("circle") and ident.startswith("hip_"):
            stars.append((ident, float(el.attrib["cx"]), float(el.attrib["cy"]), float(el.attrib["r"])))
        elif ident.startswith("latin_") or ident.startswith("sagittarius_outer_keyline") or ident.startswith("star_rim_") or ident.startswith("star_link_"):
            ink_elements.append(el)

    if len(board_points) < 8 or len(stars) != 8 or len(slots) != 11:
        raise ValueError(f"Expected board polygon + 8 stars + 11 slots; found {len(board_points)}, {len(stars)}, {len(slots)}")

    def fmt_pts(points: list[tuple[float, float]]) -> str:
        return " ".join(f"{x:.6f},{y:.6f}" for x, y in points)

    def dark_field() -> str:
        # A 0.20 mm inset leaves white soldermask visible at the board edge, matching
        # the actual transparent print-registration margin used at apertures.
        inset_shape = Polygon(board_points).buffer(-0.2, join_style="mitre")
        if inset_shape.is_empty or not inset_shape.is_valid or inset_shape.geom_type != "Polygon":
            raise ValueError("The 0.20 mm board inset did not produce one valid polygon")
        inset = [(float(x), float(y)) for x, y in inset_shape.exterior.coords]
        return f'<polygon points="{fmt_pts(board_points)}" fill="{WHITE}"/><polygon points="{fmt_pts(inset)}" fill="{DARK}"/>'

    def copy_ink(style_b: bool) -> str:
        parts: list[str] = []
        for el in ink_elements:
            ident = el.attrib.get("id", "")
            if style_b and ident.startswith("latin_"):
                continue
            clone = ET.fromstring(ET.tostring(el, encoding="unicode"))
            clone.attrib["stroke"] = INK
            clone.attrib["fill"] = "none"
            parts.append(ET.tostring(clone, encoding="unicode"))
        if style_b:
            # Typography remains live SVG text in the study only. Any final
            # manufacturing art must convert it to outlines and be rechecked.
            parts.append(f'<text x="0" y="-14.20" text-anchor="middle" fill="{INK}" font-family="Georgia, serif" font-size="1.52" font-weight="500" letter-spacing="0.055">SAGITTARIUS</text>')
            parts.append(f'<text x="0" y="14.63" text-anchor="middle" fill="{INK}" font-family="Georgia, serif" font-size="1.62" font-weight="500" letter-spacing="0.09">AD ASTRA</text>')
        return "".join(parts)

    def cutouts(night: bool) -> str:
        pieces: list[str] = []
        lumen = WARM if night else DARK
        for slot_id, (x1, y1), (x2, y2), source_d, _ in slots:
            d = source_d
            # White substrate reveal expands the nominal 1.00 mm slot to
            # 1.40 mm in daytime print mockups; the 1.00 mm core is dark.
            pieces.append(f'<path id="slot_{slot_id}_buffer" d="{d}" fill="none" stroke="{WHITE}" stroke-width="1.40" stroke-linecap="round"/>')
            pieces.append(f'<path id="slot_{slot_id}" d="{d}" fill="none" stroke="{lumen}" stroke-width="1.00" stroke-linecap="round"/>')
        for star_id, x, y, r in stars:
            pieces.append(f'<circle id="{star_id}_buffer" cx="{x!r}" cy="{y!r}" r="{r + 0.20:.12g}" fill="{WHITE}"/>')
            pieces.append(f'<circle id="{star_id}" cx="{x!r}" cy="{y!r}" r="{r!r}" fill="{lumen}"/>')
        return "".join(pieces)

    def svg_doc(name: str, variant: str, *, night: bool = False) -> str:
        style_b = variant == "B"
        label = "Night-time aperture shape schematic; brightness is not predicted." if night else "Daytime appearance proof on white soldermask; aperture interiors are shown dark and a 0.20 mm white soldermask reveal surrounds every cutout."
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="{NS}" width="37mm" height="37mm" viewBox="-18.5 -18.5 37 37">'
            f'<title>{name}</title><desc>{label} Exterior rear view, 0 degrees, not mirrored. Mechanical apertures are 8 stars and 11 isolated slots.</desc>'
            f'<g id="white-soldermask-and-ink">{dark_field()}{copy_ink(style_b)}{cutouts(night)}</g>'
            '</svg>\n'
        )

    docs = {
        "A-current-day.svg": svg_doc("A — current lettering, daytime proof", "A"),
        "B-soft-type-day.svg": svg_doc("B — gentle type candidate, daytime proof", "B"),
        "night-shape-only.svg": svg_doc("Night-time shape schematic", "B", night=True),
    }
    for filename, content in docs.items():
        (OUT / filename).write_text(content, encoding="utf-8", newline="\n")

    def nested(svg: str, x: float, y: float, label: str) -> str:
        inner = svg[svg.index("><title"):]
        inner = inner[inner.index("<g id="):inner.rindex("</svg>")]
        # The sheet uses 1 user unit = 1 mm. Keep nested viewport dimensions
        # unitless so a face occupies exactly 37 page units (37 mm).
        return f'<g transform="translate({x} {y})"><svg x="0" y="0" width="37" height="37" viewBox="-18.5 -18.5 37 37">{inner}</svg><text x="18.5" y="-3" text-anchor="middle" font-family="Arial, sans-serif" font-size="3.2" fill="#17232f">{label}</text><path d="M 0 41 H 10" stroke="#17232f" stroke-width="0.35"/><path d="M 0 40.2 V 41.8 M 10 40.2 V 41.8" stroke="#17232f" stroke-width="0.25"/><text x="5" y="44" text-anchor="middle" font-family="Arial, sans-serif" font-size="1.8" fill="#17232f">10 mm</text></g>'

    views = [nested(docs["A-current-day.svg"], 19.0, 27.0, "A 当前字样 · 日间"),
             nested(docs["B-soft-type-day.svg"], 112.0, 27.0, "B 柔和字样 · 日间"),
             nested(docs["night-shape-only.svg"], 19.0, 106.0, "夜间形状示意")]
    page = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="{NS}" width="210mm" height="297mm" viewBox="0 0 210 297">',
        '<title>Sagittarius style study — A4 at 1:1</title><desc>All board instances are exactly 37 by 37 millimeters. Print this SVG at 100 percent on A4 paper. Each view has an independent 10 mm scale bar.</desc>',
        '<rect width="210" height="297" fill="#ffffff"/>',
        '<rect x="0.5" y="0.5" width="209" height="296" fill="none" stroke="#aeb4ba" stroke-width="0.2"/>',
        '<text x="15" y="13" font-family="Microsoft YaHei, sans-serif" font-size="4.6" font-weight="600" fill="#17232f">射手座 · 37 mm 背面风格校样</text>',
        '<text x="15" y="20" font-family="Microsoft YaHei, sans-serif" font-size="2.5" fill="#4c5661">候选工艺：白色阻焊底＋彩色丝印 · 深色底浅色线 · 非铜边框</text>',
        *views,
        '<text x="19" y="158" font-family="Microsoft YaHei, sans-serif" font-size="2.45" fill="#17232f">日间图：孔槽内部为深色；开口周围模拟 0.20 mm 白色阻焊露底。</text>',
        '<text x="19" y="165" font-family="Microsoft YaHei, sans-serif" font-size="2.45" fill="#17232f">每面沿用原有 8 个星孔与 11 条相互独立的 1.00 mm 槽。</text>',
        '<text x="19" y="172" font-family="Microsoft YaHei, sans-serif" font-size="2.45" fill="#17232f">夜间图仅示孔槽形状，不预测光强或均匀性；夜间辨识度仍待实测。</text>',
        '<text x="19" y="179" font-family="Microsoft YaHei, sans-serif" font-size="2.45" fill="#17232f">B 仅改印刷文字；须先转轮廓，再检查字形、丝印和 CAM。</text>',
        '<text x="19" y="186" font-family="Microsoft YaHei, sans-serif" font-size="2.45" fill="#17232f">图纸尺寸单位为 mm。A4 请按 100% 实际大小打印，不要适配页面。</text>',
        '</svg>\n',
    ]
    sheet = "\n".join(page)
    (OUT / "A4-style-study-1to1.svg").write_text(sheet, encoding="utf-8", newline="\n")

    source_star_geometry = {name: (x, y, r) for name, x, y, r in stars}
    source_slot_geometry = {name: (d, width) for name, _, _, d, width in slots}
    geometry_results = {}
    for filename, content in docs.items():
        candidate = ET.fromstring(content)
        candidate_stars = {
            el.attrib["id"]: (float(el.attrib["cx"]), float(el.attrib["cy"]), float(el.attrib["r"]))
            for el in candidate.iter(tag("circle"))
            if el.attrib.get("id", "").startswith("hip_") and not el.attrib.get("id", "").endswith("_buffer")
        }
        candidate_slots = {
            el.attrib["id"].removeprefix("slot_"): (el.attrib["d"], float(el.attrib["stroke-width"]))
            for el in candidate.iter(tag("path"))
            if el.attrib.get("id", "").startswith("slot_") and not el.attrib.get("id", "").endswith("_buffer")
        }
        geometry_results[filename] = {
            "star_hole_count": len(candidate_stars),
            "slot_count": len(candidate_slots),
            "star_centers_and_diameters_match": candidate_stars == source_star_geometry,
            "slot_centerlines_and_widths_match": candidate_slots == source_slot_geometry,
        }
    if not all(result["star_centers_and_diameters_match"] and result["slot_centerlines_and_widths_match"] for result in geometry_results.values()):
        raise ValueError(f"A generated variant changed source aperture geometry: {geometry_results}")

    sheet_root = ET.parse(OUT / "A4-style-study-1to1.svg").getroot()
    nested_faces = list(sheet_root.iter(tag("svg")))[1:]
    a4_size_is_1to1 = sheet_root.attrib.get("width") == "210mm" and sheet_root.attrib.get("height") == "297mm"
    nested_faces_are_37mm = len(nested_faces) == 3 and all(face.attrib.get("width") == "37" and face.attrib.get("height") == "37" for face in nested_faces)
    source_sha_after = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    source_unchanged = source_sha_before == source_sha_after
    if not a4_size_is_1to1 or not nested_faces_are_37mm or not source_unchanged:
        raise ValueError("A4 page scale or source-artwork SHA check failed")

    validation = {
        "status": "geometry_and_source_hash_pass",
        "source": "artwork/sagittarius_face.svg",
        "source_sha256_before_generation": source_sha_before,
        "source_sha256_after_generation": source_sha_after,
        "source_artwork_unchanged": source_unchanged,
        "output_scope": "artwork/star-style-study-v1/ only",
        "board_size_mm": [37, 37],
        "orientation": "exterior rear view; 0 degrees; not mirrored",
        "star_holes": len(stars),
        "isolated_slots": len(slots),
        "slot_width_mm": 1.0,
        "daytime_clearance_mm": 0.2,
        "daytime_aperture_fill": DARK,
        "board_substrate": "white soldermask is simulated where 0.20 mm transparent print buffers reveal the base; candidate finish route: white soldermask plus colored silkscreen",
        "geometry_comparison": geometry_results,
        "variants": {
            "A-current-day.svg": "existing AD ASTRA / FORTIS ET LIBER vector lettering",
            "B-soft-type-day.svg": "printing candidate only; SAGITTARIUS / AD ASTRA live text; requires outline conversion and print validation",
            "night-shape-only.svg": "shape schematic only; no light-intensity prediction",
        },
        "page": {"file": "A4-style-study-1to1.svg", "size_mm": [210, 297], "root_size_is_1to1": a4_size_is_1to1, "three_nested_faces_are_37mm": nested_faces_are_37mm, "each_scale_bar_mm": 10},
        "design_checks": {
            "all_variants_have_source_star_count": all(r["star_hole_count"] == len(stars) for r in geometry_results.values()),
            "all_variants_have_source_slot_count": all(r["slot_count"] == len(slots) for r in geometry_results.values()),
            "added_stars": max(r["star_hole_count"] for r in geometry_results.values()) - len(stars),
            "animal_raster_images_in_candidate_svg": sum(el.tag == tag("image") for el in ET.fromstring(docs["B-soft-type-day.svg"]).iter()),
            "active_artwork_source_sha_unchanged": source_unchanged,
            "copper_layer_geometry_in_candidates": sum("copper" in el.attrib.get("id", "").lower() for el in ET.fromstring(docs["B-soft-type-day.svg"]).iter()),
        },
        "limitations": [
            "Daytime white reveals approximate a 0.20 mm transparent print buffer around apertures; production ink spreading and registration are not represented.",
            "The standard font in B is live SVG text and can render differently across systems until converted to outlines.",
            "Night schematic indicates aperture geometry, not NFC output, optical transmission, brightness or uniformity.",
            "This study is not manufacturing release or supplier CAM approval.",
        ],
    }
    (OUT / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    readme = """# 射手座 37 mm 独立风格校样

本目录只放美观候选校样，来自现有 `artwork/sagittarius_face.svg` 的矢量坐标；未修改原图、机械几何、EDA 工程或任何动物 PNG。两个白天方案都保留 8 个星孔、11 条独立 1.00 mm 槽的原中心线和轮廓；无新增星、人马图案或铜边框。方向为从背面外侧观看，0°，不镜像。

## 预览

- [A：当前字样，日间 SVG](A-current-day.svg) · [PNG](A-current-day.png)
- [B：柔和常规字体候选，日间 SVG](B-soft-type-day.svg) · [PNG](B-soft-type-day.png)
- [夜间孔槽形状示意 SVG](night-shape-only.svg) · [PNG](night-shape-only.png)
- [A4 毫米制 1:1 校样页 SVG](A4-style-study-1to1.svg) · [PNG](A4-style-study-1to1.png)
- [尺寸与范围校验](validation.json)

A 保留现有 `AD ASTRA / FORTIS ET LIBER` 折线字。B 仅替换印刷文字：上方 `SAGITTARIUS`，下方 `AD ASTRA`，用较柔和的衬线字并留出更多字间距。B 仍是印刷候选，文字目前保留为 SVG 文本；用于制造前须转为轮廓，并复查字宽、笔画、油墨覆盖和官方 CAM 输出。

## 白色阻焊底与日夜示意

本候选采用“白色阻焊底＋彩色丝印”路线作为视觉参考；白色露底仅代表白色阻焊底的模拟显示。

白色露底在图中模拟白色阻焊底。日间图把孔、槽内部画成深色；在槽周围按 0.20 mm 透明印刷缓冲露出白色阻焊，因此槽口周围能看到加宽的白边。星孔也按同样的 0.20 mm 环形缓冲显示。这只是本候选的视觉模拟，不代表真实板材或油墨颜色，也不代表最终油墨铺展或丝印套准。

夜间图只强调孔槽所在形状，暖白只是位置标记，不预测 NFC 供电、透光量、亮度或均匀性。孔槽之间补齐断口的细连接线是印刷，不是发光开口；十一条独立槽与八孔才是透光结构。最终观感需要官方 CAM 预览与实物首件确认。

## 尺寸与既有审查依据

单件 SVG 画板和八边形外形均为 37 × 37 mm。A4 校样页定义为 210 × 297 mm，并给每个图案配 10 mm 标尺；打印 SVG 时选择 A4、100% 或“实际大小”，不要“适合页面”。PNG 由 sharp 直接将完整 SVG 画布渲染为正方形单面图和 A4 比例页面，没有浏览器视口截图边距；像素尺寸和约当 dpi 见 `validation.json`，毫米尺寸以 SVG 定义为准。

已审查的布局为 8 个 Ø0.8 mm 星孔、11 条 1.0 mm 机械槽，星图中心范围约 27.5 × 17.6 mm。星图左右端星孔外缘离 37 mm 八边形直边约 4.35 mm，上下约 9.3 mm；文字落在星图外的上下留白区。最新制造文件审计记录最小孔到槽实材 1.030 mm、槽到槽 1.031 mm；最短槽总长 1.489 mm，中心直线段 0.489 mm。孔槽保留茶壶主轮廓；夜间辨识度仍待实测。孔槽之间补齐断口的细连接线是印刷，不是发光开口；十一条独立槽与八孔才是透光结构。常规字有机会改善阅读，但 37 mm 尺度下仍需看实际印刷样件。

上述结论来自 [现有源图](../sagittarius_face.svg)、[星图数据](../../../../data/constellation.json)、[图形审查记录](../sagittarius-linework-review.json) 与 [制造几何审计](../../manufacturing/draft/star-face-audit.json)。几何通过不等于供应商 CAM、油墨、透光或实体观感验收。
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    index_html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>射手座 37 mm 风格校样</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, "Microsoft YaHei", sans-serif; color: #202b36; background: #f4f5f6; }
    body { margin: 0 auto; max-width: 1120px; padding: 24px; }
    h1 { margin: 0 0 8px; font-size: 1.55rem; }
    p { line-height: 1.6; }
    .notice { padding: 12px 16px; background: #fff7dc; border-left: 4px solid #c7953d; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 18px; align-items: start; }
    article { background: white; border: 1px solid #d9dee3; border-radius: 10px; padding: 14px; }
    article img { display: block; width: 100%; height: auto; background: #eee; }
    h2 { margin: 2px 0 8px; font-size: 1.08rem; }
    .links { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }
    a { color: #075ca8; }
    .wide { margin-top: 18px; }
    .wide img { max-width: 720px; border: 1px solid #d9dee3; }
    footer { margin-top: 20px; font-size: .93rem; }
  </style>
</head>
<body>
  <h1>射手座 · 37 mm 独立风格校样</h1>
  <p>白色阻焊底示意、深色底、浅色线；复用现有 8 个星孔和 11 条分离槽。屏幕图用于比较排版，不代表实物透光或供应商 CAM 结果。</p>
  <p class="notice"><strong>B 版仅为印刷候选。</strong>目前 SAGITTARIUS / AD ASTRA 仍是系统字体文字；正式使用前须转成矢量轮廓并核对字号、笔画、丝印、alpha 与 CAM。该候选尚未制造验证。</p>
  <section class="grid">
    <article><h2>A · 当前字样 · 日间</h2><img src="A-current-day.png" alt="当前折线字样与深色日间星图校样"><div class="links"><a href="A-current-day.svg">打开 37 mm SVG</a><a href="A-current-day.png">打开 PNG</a></div></article>
    <article><h2>B · 柔和字体候选 · 日间</h2><img src="B-soft-type-day.png" alt="SAGITTARIUS 与 AD ASTRA 柔和字体候选"><div class="links"><a href="B-soft-type-day.svg">打开 37 mm SVG</a><a href="B-soft-type-day.png">打开 PNG</a></div></article>
    <article><h2>夜间形状示意</h2><img src="night-shape-only.png" alt="标示星孔和槽形状的夜间示意"><p>浅色表示开口位置；不表示亮度或均匀性。</p><div class="links"><a href="night-shape-only.svg">打开 SVG</a><a href="night-shape-only.png">打开 PNG</a></div></article>
  </section>
  <section class="wide"><h2>A4 · 210 × 297 mm · 1:1 校样页</h2><p>三个图案各有 10 mm 标尺。打印 SVG 时选 A4 与 100% / 实际大小，不要“适合页面”。</p><a href="A4-style-study-1to1.svg">打开 A4 SVG</a> · <a href="A4-style-study-1to1.png">打开 A4 PNG</a><img src="A4-style-study-1to1.png" alt="包含三个毫米尺寸校样和标尺的A4页面"></section>
  <footer><a href="README.md">中文审查说明</a> · <a href="validation.json">尺寸与范围校验</a></footer>
</body>
</html>
"""
    (OUT / "index.html").write_text(index_html, encoding="utf-8", newline="\n")

    if not NODE.exists() or not SHARP.exists():
        raise FileNotFoundError("The configured Node.js and sharp runtime is required to render proof PNGs; the SVG proofs are already written.")
    renders = [
        ("A-current-day.svg", "A-current-day.png", 300, 1600, 1600),
        ("B-soft-type-day.svg", "B-soft-type-day.png", 300, 1600, 1600),
        ("night-shape-only.svg", "night-shape-only.png", 300, 1600, 1600),
        ("A4-style-study-1to1.svg", "A4-style-study-1to1.png", 150, 2480, 3508),
    ]
    png_sizes = {}
    render_js = """const sharp=require(process.argv[1]); const [src,dst,density,width,height]=process.argv.slice(2); sharp(src,{density:Number(density)}).resize(Number(width),Number(height),{fit:'fill'}).png({compressionLevel:9}).toFile(dst).catch(e=>{console.error(e);process.exit(1)});"""
    for svg_name, png_name, density, width, height in renders:
        png_path = OUT / png_name
        subprocess.run([str(NODE), "-e", render_js, str(SHARP), str(OUT / svg_name), str(png_path), str(density), str(width), str(height)], check=True, timeout=120, capture_output=True, text=True)
        from PIL import Image
        with Image.open(png_path) as im:
            png_sizes[png_name] = list(im.size)
    validation["png_renders"] = {
        "rasterizer": "sharp",
        "individual_target_dpi": round(1600 / 37 * 25.4, 1),
        "a4_target_dpi": round(2480 / 210 * 25.4, 1),
        "dimensions_px": png_sizes,
    }
    (OUT / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"out": str(OUT), "stars": len(stars), "slots": len(slots), "files": sorted(p.name for p in OUT.iterdir())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
