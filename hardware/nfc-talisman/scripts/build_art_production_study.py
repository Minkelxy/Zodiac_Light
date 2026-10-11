#!/usr/bin/env python3
"""Build a printable 1:1 artwork study from approved single-ink PNG assets.

This is page composition only. It never edits, filters, rotates, or replaces
the source PNGs and does not create manufacturing geometry.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artwork"
OUT = ART / "production-study-v1"
SINGLE = ART / "reference-collection" / "talisman-single-ink-v1"
MANIFEST = SINGLE / "manifest.json"
HORSE = SINGLE / "horse-single-ink.png"
GEOMETRY = ROOT / "geometry" / "design.json"
OCTAGON_MM = 37.0
WINDOW_MM = 30.0
ANTENNA_MM = 34.0
PAGE_W, PAGE_H = 210.0, 297.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def octagon_points(af: float, cx: float, cy: float, scale: float) -> str:
    # Across-flats regular octagon, with horizontal and vertical flats.
    half = af / 2
    vertex = half * (math.sqrt(2) - 1)
    pts = [(-vertex, -half), (vertex, -half), (half, -vertex),
           (half, vertex), (vertex, half), (-vertex, half),
           (-half, vertex), (-half, -vertex)]
    return " ".join(f"{cx+x*scale:.3f},{cy+y*scale:.3f}" for x, y in pts)


def svg_text(x: float, y: float, content: str, size: float = 3.0,
             fill: str = "#20232a", anchor: str = "start", weight: str = "normal") -> str:
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="Arial, sans-serif" '
            f'font-size="{size:.2f}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{html.escape(content)}</text>')


def make_proof_svg(entries: list[dict], page_num: int, embedded: dict[str, str],
                   placement_mm: float = 37.0, light_window_candidate: bool = False) -> str:
    heading = ("30 mm 光腔适配候选" if light_window_candidate else "37 mm 画布原尺寸基线")
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 {PAGE_W} {PAGE_H}">',
         f'<title>十二生肖 · {heading} · 第 {page_num} 页</title>',
         '<desc>仅用于尺寸与排版审阅，所有源 PNG 按原像素内容内嵌。打印时须选择 A4、100%%、关闭适合页面缩放。</desc>',
         '<rect width="210" height="297" fill="#fff"/>',
         svg_text(12, 12, f"十二生肖单色图案 · {heading} · {page_num}/2", 5.0, weight="bold"),
         svg_text(12, 19, "A4 纵向 | 打印 100% / Actual size | 所有八边形为顶底平边，均是参考定位", 2.7, "#4c5562"),
         svg_text(12, 25, (f"统一置入 {placement_mm:.2f} mm；alpha≥128 主形落在 AF30 内，至少保留 0.5 mm 名义边距。" if light_window_candidate else "37 mm 是 PNG 画布置入尺寸，图案因透明留白小于画布；原像素/颜色/alpha/朝向不变。"), 2.5, "#4c5562")]
    xs = [14.0, 81.0, 148.0]
    ys = [32.0, 151.0]
    for i, item in enumerate(entries):
        col, row = i % 3, i // 3
        x0, y0 = xs[col], ys[row]
        cx, cy = x0 + 21.0, y0 + 26.5
        x, y = cx - placement_mm/2, cy - placement_mm/2
        s.append(f'<g id="{item["id"]}">')
        s.append(f'<rect x="{x0}" y="{y0}" width="58" height="106" rx="1" fill="#fbfbfa" stroke="#d4d8de" stroke-width="0.2"/>')
        s.append(svg_text(x0+3, y0+6, f'{item["animal_zh"]} · {item["animal_en"]}', 3.4, weight="bold"))
        s.append(f'<image x="{x:.3f}" y="{y:.3f}" width="{placement_mm:.3f}" height="{placement_mm:.3f}" preserveAspectRatio="none" href="{embedded[item["id"]]}"/>')
        # Actual production geometry is not defined here; outlines are reference guides only.
        s.append(f'<polygon points="{octagon_points(OCTAGON_MM,cx,cy,1)}" fill="none" stroke="#3a414b" stroke-width="0.22"/>')
        s.append(f'<polygon points="{octagon_points(WINDOW_MM,cx,cy,1)}" fill="none" stroke="#17a6a1" stroke-width="0.22" stroke-dasharray="1.1 0.8"/>')
        s.append(f'<polygon points="{octagon_points(ANTENNA_MM,cx,cy,1)}" fill="none" stroke="#e09037" stroke-width="0.22" stroke-dasharray="1.1 0.8"/>')
        s.append(svg_text(x0+3, y0+49, f"PNG canvas placed {placement_mm:.2f} × {placement_mm:.2f} mm", 2.3))
        s.append(svg_text(x0+3, y0+54, "34 AF outer-coil envelope only / not four-turn geometry", 1.9, "#8c5819"))
        s.append(svg_text(x0+3, y0+58.5, "37 AF board / 30 AF spacer window reference", 1.9, "#16827f"))
        s.append(svg_text(x0+3, y0+63, f'Visual state: {item.get("visual_status", "unlisted")}', 2.2, "#56616d"))
        note = item.get("visual_note", "")
        note = re.sub(r'\s+', ' ', note)
        # Notes are shortened for a legible card; the complete manifest is left untouched.
        if len(note) > 18:
            note = note[:17].rstrip("，。；,; ") + "…"
        s.append(svg_text(x0+3, y0+69, "视觉备注：" + note, 1.9, "#4c5562"))
        # 10 mm calibration bar, measured in SVG user units = mm.
        by = y0 + 80
        s.extend([f'<path d="M {x0+3} {by} h 10 M {x0+3} {by-1.1} v 2.2 M {x0+13} {by-1.1} v 2.2" stroke="#15191f" stroke-width="0.25"/>',
                  svg_text(x0+15, by+0.8, "10 mm", 2.0)])
        s.append('</g>')
    s.extend([svg_text(12, 278, "校样说明：仅用于观察 37 mm 外形内的等比例落位。印刷色受设备、纸张与缩放影响。", 2.35, "#4c5562"),
              svg_text(12, 284, "打印后请用尺检查卡片下方 10 mm 标尺；若不等于 10 mm，请勿据此判断尺寸。", 2.35, "#4c5562"),
              svg_text(12, 291, "黑/青/橙线分别示意外形 / 垫环内窗 / 天线投影定位，不生成任何铜、阻焊、开孔或刀路。", 2.25, "#4c5562"),
              '</svg>'])
    return '\n'.join(s)


def make_optics_svg(horse_uri: str) -> str:
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="148mm" viewBox="0 0 210 148">',
         '<title>马符咒光学分区候选 — 概念讨论</title>',
         '<desc>紫色区域来自原始马图 PNG，白色表示待评估的出光留白。图示不定义开孔或加工数据。</desc>',
         '<rect width="210" height="148" fill="#fff"/>',
         svg_text(8, 10, "马符咒光学分区候选 · 概念讨论", 5, weight="bold"),
         svg_text(8, 17, "紫色 = 原图中印刷岛；白色 = 可评估的透光留白。马图直接使用原始 PNG，左向、不镜像、不重绘。", 2.8, "#4c5562")]
    for idx, (x, title, lines) in enumerate([
        (8, "A · 全 FR-4 去铜 + 去阻焊窗口", ["先评估底层铜面与阻焊开窗；保持外层基材连续。", "光路可由透明/半透明扩散片覆盖，但需实测色彩、", "亮度、散射和层间漏光。细岛/细缝不作去噪处理。"]),
        (108, "B · 实际开孔 + 非金属扩散片", ["仅把独立孔/槽作为工程候选；此图不产生马形铣槽。", "非金属扩散片覆盖可行的窗口，评估亮度与外观。", "具体开孔边界、最小连通宽度及刀具阈值待工艺确认。"])]):
        s.append(f'<rect x="{x}" y="23" width="94" height="112" rx="1" fill="#f8f9fb" stroke="#c6ccd4" stroke-width="0.35"/>')
        s.append(svg_text(x+4, 31, title, 3.1, weight="bold"))
        s.append(f'<polygon points="{octagon_points(37,x+47,66,0.84)}" fill="#454c55" stroke="#222831" stroke-width="0.35"/>')
        s.append(f'<polygon points="{octagon_points(30,x+47,66,0.84)}" fill="#fcfcfa" stroke="#17a6a1" stroke-width="0.3" stroke-dasharray="1 0.6"/>')
        # Preserve source image bytes exactly; placement is an explanatory overlay only.
        s.append(f'<image x="{x+47-15.54}" y="{66-15.54}" width="31.08" height="31.08" preserveAspectRatio="none" href="{horse_uri}"/>')
        s.append(f'<polygon points="{octagon_points(34,x+47,66,0.84)}" fill="none" stroke="#e09037" stroke-width="0.3" stroke-dasharray="1 0.7"/>')
        s.append(svg_text(x+47, 91, "34 AF 外匝包络示意（不是实际四匝线）", 1.7, "#4c5562", "middle"))
        for j, line in enumerate(lines):
            s.append(svg_text(x+4, 101+j*5.2, line, 2.0, "#353c46"))
    s.extend([svg_text(8, 142, "两者都只是参考方案：天线周边不得铺装饰铜或闭合金属框；任何细岛、透明细缝、连通性及可加工阈值须人工视觉/工艺/实体验证。", 2.25, "#a33b32"),
              '</svg>'])
    return '\n'.join(s)


def make_optics_notes() -> str:
    return """# 马符咒光学分区候选（概念）\n\n紫色区域仅表示 approved 单色 PNG 中原有的六个印刷色岛；透明/白色区域表示可讨论的出光留白。PNG 的细散点、细缝和 alpha 原样保留，需在 1:1 校样上人工确认其视觉表现，不自动去噪，也不由单色像素检查推断工艺可行。\n\n- **A：全 FR-4 去铜 + 去阻焊窗口**：优先作为光学样件讨论。板材保持连续，窗口可以搭配透明或半透明非金属扩散片。确认铜净空、阻焊开窗、油墨套印、透光亮度与散射，并做实际样件。\n- **B：独立实际开孔 + 非金属扩散片**：仅讨论独立孔/槽可行性与扩散片覆盖方式；本概念没有马形铣槽，也没有任何开孔尺寸或刀路。\n\n几何定位仅沿用 37 mm 对边距八边形外框、34 mm 对边距四匝线圈的外匝包络示意、30 mm 对边距垫环内窗参考，全部顶底平边。橙线只标线圈外匝包络，不是实际四匝走线。所有边界皆为参考定位；天线区域避免装饰铜和闭合金属框。细岛、窄缝、负形连通以及最小制造特征需要工艺方确认并以实体首件验证。\n\n**非制造文件。** 本页不指定铜层、阻焊层、刀具补偿、扩散片材质或公差，不可导入 EDA 或 CAM 作为加工输入。\n"""


def inside_octagon(x: float, y: float, af: float, inset: float = 0.0) -> bool:
    half = af / 2 - inset
    diagonal_bound = (af / 2 - inset) * math.sqrt(2)
    return max(abs(x), abs(y)) <= half and abs(x) + abs(y) <= diagonal_bound


def audit_visible_alpha(path: Path) -> dict:
    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")
    bbox_any = alpha.getbbox()
    bbox_main = alpha.point(lambda a: 255 if a >= 128 else 0).getbbox()
    counts = {"alpha_gt_0": {37: 0, 30: 0}, "alpha_ge_128": {37: 0, 30: 0}}
    mm_bounds = {"alpha_gt_0": [float("inf"), float("inf"), -float("inf"), -float("inf")],
                 "alpha_ge_128": [float("inf"), float("inf"), -float("inf"), -float("inf") ]}
    for py in range(1024):
        row = alpha.crop((0, py, 1024, py+1)).get_flattened_data()
        for px, a in enumerate(row):
            if a == 0:
                continue
            x = ((px + 0.5) / 1024 - 0.5) * OCTAGON_MM
            y = ((py + 0.5) / 1024 - 0.5) * OCTAGON_MM
            for label, include in (("alpha_gt_0", True), ("alpha_ge_128", a >= 128)):
                if not include:
                    continue
                b = mm_bounds[label]
                b[0]=min(b[0],x); b[1]=min(b[1],y); b[2]=max(b[2],x); b[3]=max(b[3],y)
                for af in (37, 30):
                    if not inside_octagon(x, y, af):
                        counts[label][af] += 1
    def bbox_record(box):
        if box is None:
            return None
        x0,y0,x1,y1=box
        return {"xyxy_px":[x0,y0,x1,y1],"size_px":[x1-x0,y1-y0],
                "local_bbox_mm_when_canvas_is_37mm":[round(x0/1024*37-18.5,4),round(y0/1024*37-18.5,4),
                                                       round(x1/1024*37-18.5,4),round(y1/1024*37-18.5,4)]}
    return {"canvas_px":list(image.size),"canvas_placement_mm":[37.0,37.0],
            "alpha_gt_0_bbox":bbox_record(bbox_any),"alpha_ge_128_main_shape_bbox":bbox_record(bbox_main),
            "outside_outline_pixel_counts_at_37mm_canvas":counts,
            "any_alpha_visible_bbox_local_mm":[round(v,4) for v in mm_bounds["alpha_gt_0"]],
            "alpha_ge_128_main_shape_bbox_local_mm":[round(v,4) for v in mm_bounds["alpha_ge_128"]],
            "threshold_note":"Pixel-center point-in-outline audit; alpha>=128 is a review threshold, not a processing step.",
            "audit_is_read_only":True}


def common_light_window_size(paths: dict[str, Path]) -> tuple[float, dict[str, dict]]:
    # One uniform canvas size for all animals; keep alpha>=128 ink at least 0.5 mm inside AF30.
    safe_half=WINDOW_MM/2-0.5
    safe_diagonal=safe_half*math.sqrt(2)
    limits=[]
    report={}
    for animal,path in paths.items():
        alpha=Image.open(path).convert("RGBA").getchannel("A")
        max_size=float("inf")
        for py in range(1024):
            for px,a in enumerate(alpha.crop((0,py,1024,py+1)).get_flattened_data()):
                if a<128: continue
                ux=(px+0.5)/1024-0.5; uy=(py+0.5)/1024-0.5
                if max(abs(ux),abs(uy))>0:
                    max_size=min(max_size,safe_half/max(abs(ux),abs(uy)))
                if abs(ux)+abs(uy)>0:
                    max_size=min(max_size,safe_diagonal/(abs(ux)+abs(uy)))
        limits.append(max_size)
        report[animal]={"individual_max_canvas_mm_for_0_5mm_inset":round(max_size,6)}
    shared=math.floor((min(limits)-0.01)*100)/100
    for animal,path in paths.items():
        alpha=Image.open(path).convert("RGBA").getchannel("A")
        xs=[];ys=[];outside=0;min_clearance=float("inf")
        for py in range(1024):
            for px,a in enumerate(alpha.crop((0,py,1024,py+1)).get_flattened_data()):
                if a<128: continue
                x=((px+0.5)/1024-0.5)*shared; y=((py+0.5)/1024-0.5)*shared
                xs.append(x);ys.append(y)
                clearance=min(WINDOW_MM/2-max(abs(x),abs(y)),
                              (WINDOW_MM/2*math.sqrt(2)-(abs(x)+abs(y)))/math.sqrt(2))
                min_clearance=min(min_clearance,clearance)
                if not inside_octagon(x,y,WINDOW_MM,inset=0.5): outside+=1
        report[animal].update({"common_png_canvas_placement_mm":[shared,shared],
            "alpha_ge_128_ink_bbox_local_mm":[round(min(xs),4),round(min(ys),4),round(max(xs),4),round(max(ys),4)],
            "alpha_ge_128_ink_bbox_size_mm":[round(max(xs)-min(xs),4),round(max(ys)-min(ys),4)],
            "minimum_ideal_af30_edge_clearance_mm":round(min_clearance,4),
            "alpha_ge_128_pixels_outside_af30_with_0_5mm_inset":outside,
            "main_shape_inside_af30_with_0_5mm_inset":outside==0})
    return shared,report


def make_overview(entries: list[dict], paths: dict[str, Path], output: Path) -> None:
    w, h = 1800, 1350
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 30)
        small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    except OSError:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 30)
            small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
        except OSError:
            font = small = ImageFont.load_default()
    d.text((44, 25), "十二生肖 · 37 mm 实际尺寸落位一览（缩略排版）", fill="#20232a", font=font)
    d.text((44, 68), "用于整体浏览；请用两页 A4 SVG / print.html 的 10 mm 标尺检查实际打印尺寸。", fill="#4c5562", font=small)
    cellw, cellh = 580, 285
    for i, item in enumerate(entries):
        c, r = i % 3, i // 3
        x, y = 20+c*590, 110+r*300
        d.rounded_rectangle((x, y, x+cellw-18, y+cellh-18), 8, fill="#fbfbfa", outline="#d4d8de", width=2)
        d.text((x+16, y+12), f'{item["animal_zh"]} · {item["animal_en"]}', fill="#20232a", font=small)
        src = Image.open(paths[item["id"]]).convert("RGBA")
        thumb = src.resize((210, 210), Image.Resampling.LANCZOS)
        alpha = thumb.getchannel("A")
        # This is a layout thumbnail; source remains unmodified.
        im.paste(thumb, (x+12, y+48), alpha)
        for af, color, width in [(37, "#333c46", 2), (34, "#e09037", 2), (30, "#17a6a1", 2)]:
            half = 105 * af / 37
            vertex = half * (math.sqrt(2) - 1)
            points = [(x+117-vertex, y+153-half), (x+117+vertex, y+153-half),
                      (x+117+half, y+153-vertex), (x+117+half, y+153+vertex),
                      (x+117+vertex, y+153+half), (x+117-vertex, y+153+half),
                      (x+117-half, y+153+vertex), (x+117-half, y+153-vertex)]
            d.line(points + [points[0]], fill=color, width=width, joint="curve")
        d.text((x+245, y+58), "置入尺寸：37 × 37 mm", fill="#252b33", font=small)
        d.text((x+245, y+94), "外框：AF 37 mm", fill="#39424d", font=small)
        d.text((x+245, y+130), "线圈 AF34 外匝包络参考", fill="#a05d17", font=small)
        d.text((x+245, y+166), "内窗：AF 30 mm 参考", fill="#16827f", font=small)
        d.text((x+245, y+202), "37mm为画布，图案含透明留白", fill="#56616d", font=small)
    im.save(output, quality=95)


def make_readme(common_size: float, audits: dict, candidate_report: dict) -> str:
    outside_37=[k for k,v in audits.items() if v["outside_outline_pixel_counts_at_37mm_canvas"]["alpha_ge_128"][37]>0]
    outside_30=[k for k,v in audits.items() if v["outside_outline_pixel_counts_at_37mm_canvas"]["alpha_ge_128"][30]>0]
    fit=[k for k,v in candidate_report.items() if v["main_shape_inside_af30_with_0_5mm_inset"]]
    outside_37_text=', '.join(f'{k}（{audits[k]["outside_outline_pixel_counts_at_37mm_canvas"]["alpha_ge_128"][37]} 个像素中心）' for k in outside_37) if outside_37 else '无'
    return f"""# 图案实际尺寸校样与光路候选

本目录只做版面校样和定位示意，读取现有单色 PNG 与 manifest。所有校样 SVG 都直接内嵌原始 PNG 字节；没有裁切、镜像、去噪、阈值化、换色或改动图形。overview-12up.jpg 是缩小的一览图，只用于浏览。

## 打印与比较

- index.html 是导航入口，含两套校样、光路概念图、说明和打印入口。
- print.html / proof-a4-page-1.svg / proof-a4-page-2.svg：两页 A4 纵向的 37 mm 画布原尺寸基线。每个 PNG 正方形画布置入尺寸为 **37×37 mm**，不是可见图案的宽高；透明留白使图案小于 37 mm。
- light-window-candidate/index.html：30 mm 光腔适配候选两页，十二图统一使用 **{common_size:.2f}×{common_size:.2f} mm** 画布置入尺寸；alpha≥128 主形像素中心全部位于理想 AF30 八边形内，并保留至少 0.5 mm 名义边距（{len(fit)}/12 款通过）。逐款主形包围盒见 validation.json。该候选只缩放 SVG 中 PNG 的置入宽高，源 PNG 字节不变。
- 两套校样每页都带 10 mm 校准尺。打印时选择 A4 纵向、Actual size / 100%，关闭“适合页面”或类似缩放。打印后用尺量校准线：必须正好 10 mm；否则该页不可用作实际尺寸判断。
- overview-12up.jpg：三列四行缩略一览，不按打印尺寸。
- horse-optical-zones-concept.svg / horse-optical-zones-concept.png：光路候选示意；optical-zones-notes.md 有文字说明。

## 定位线与越界审阅

所有八边形均为顶底平边：深灰实线表示 AF37 板框，橙色虚线表示 AF34 四匝天线的**外匝包络示意**，青色虚线表示 AF30 垫环内窗。橙线只表示包络，不是实际四匝走线。三者均为参考定位，不是铜、阻焊或加工几何；天线范围避免装饰铜与闭合金属框。

37 mm 画布基线中，alpha≥128 主形超过 AF37 理想八边形的图案为：{outside_37_text}；超过 AF30 内窗参考的图案为：{', '.join(outside_30) if outside_30 else '无'}。validation.json 逐款记录 alpha>0 可见范围、alpha≥128 主形包围盒，以及落在 AF37 / AF30 参考边界外的像素计数。该阈值仅用于只读审阅，不改 PNG，也不表示加工能力。

猪图 alpha≥128 主形有少量像素落在 AF37 八边形之外；狗腿、鸡冠、猪耳等边缘也应在两套校样上人工放大检查。马图周边有少量细散点，细岛、透明窄缝的视觉与连通情况也需人工核对。不得自动去噪或把单色校验通过解释成图形保真/制造可行。

28.17 mm 统一画布候选以像素中心审计的 alpha≥128 主形为准，预留理想 AF30 边界至少 0.5 mm 的名义余量；没有按动物分别缩放，也没有裁剪。灰底图案可以印到窗口以外，实际印刷与光学窗口的关系仍须看样件。此缩放建议供具体比较，不自动写入 EDA。

## 光路工艺讨论与限制

概念图对比 A：FR-4 板材保持连续，对相关区域评估去铜与去阻焊窗口，搭配非金属扩散片；B：另行评估彼此独立、可加工的实际孔/槽，再由非金属扩散片覆盖。马图按原图左向显示，不镜像、不重绘、不生成马形铣槽。实际开孔边界、铜净空、阻焊、套印、扩散、亮度、RF 和最小加工特征需要供应商/工艺确认与实体首件测试。

本资料不是 EDA、CAM、Gerber 或生产文件，不定义铜层、阻焊、刀补、公差、扩散片材料或最小线宽/间距。制造结论需基于工艺评估和实物验证。validation.json 同时记录源 PNG 生成前后的 SHA-256；校验应保持一致。
"""


def make_index_html(common_size: float) -> str:
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>37 mm 校样与光路</title>
<style>body{{font:16px/1.5 "Microsoft YaHei",sans-serif;max-width:980px;margin:2rem auto;padding:0 1.2rem;color:#20232a}}li{{margin:.65rem 0}}a{{color:#155e9b}}.note{{background:#f2f5f7;padding:.8rem 1rem;border-left:4px solid #e09037}}</style><body>
<h1>37 mm 校样与光路</h1><p class="note">打印校样：A4 纵向、Actual size / 100%、关闭“适合页面”。量每页 10 mm 校准尺；若不是 10 mm，打印比例不合格。各图的尺寸均按对应 PNG 正方形画布计算，实际图案因透明边距小于画布。</p>
<h2>可查看的校样</h2><ul><li><a href="proof-a4-page-1.svg">37 mm 画布原尺寸基线 · 第 1 页</a></li><li><a href="proof-a4-page-2.svg">37 mm 画布原尺寸基线 · 第 2 页</a></li><li><a href="light-window-candidate/index.html">30 mm 光腔适配候选 · {common_size:.2f} mm 统一画布置入尺寸（两页打印入口）</a></li><li><a href="horse-optical-zones-concept.svg">马符咒光学分区候选 SVG</a> · <a href="horse-optical-zones-concept.png">PNG 预览</a></li><li><a href="overview-12up.jpg">十二款 12-up 浏览图（非打印尺寸）</a></li></ul>
<h2>打印入口</h2><ul><li><a href="print.html">37 mm 原尺寸基线两页</a></li><li><a href="light-window-candidate/index.html">30 mm 光腔适配候选两页</a></li></ul>
<p>八边形均为顶底平边：37 mm 板框、34 mm 四匝线圈外匝包络参考、30 mm 垫环内窗。此处为排版及可视化审阅资料，不是 EDA/CAM/制造数据。细散点与细缝保留原样，待人工视觉检查。更多说明见 <a href="README.md">README</a>；数字审计见 <a href="validation.json">validation.json</a>。</p></body></html>'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    geo = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    entries = raw["files"]
    if len(entries) != 12:
        raise ValueError(f"Expected 12 manifest PNGs, got {len(entries)}")
    before = {e["id"]: sha(SINGLE / Path(e["path"]).name) for e in entries}
    pngs = {e["id"]: (SINGLE / Path(e["path"]).name) for e in entries}
    horse_sha_before = sha(HORSE)
    horse_img = Image.open(HORSE)
    if horse_img.size != (1024, 1024) or horse_img.mode != "RGBA":
        raise ValueError(f"Horse source must remain RGBA 1024x1024; got {horse_img.mode} {horse_img.size}")
    horse_uri = data_uri(HORSE)
    uris = {e["id"]: data_uri(pngs[e["id"]]) for e in entries}
    alpha_audits={e["id"]:audit_visible_alpha(pngs[e["id"]]) for e in entries}
    common_size,candidate_report=common_light_window_size(pngs)
    pages = [entries[:6], entries[6:]]
    page_paths = []
    for n, group in enumerate(pages, 1):
        p = OUT / f"proof-a4-page-{n}.svg"
        p.write_text(make_proof_svg(group, n, uris), encoding="utf-8")
        page_paths.append(p)
    candidate_dir=OUT/"light-window-candidate"
    candidate_dir.mkdir(exist_ok=True)
    candidate_paths=[]
    for n,group in enumerate(pages,1):
        p=candidate_dir/f"proof-a4-page-{n}.svg"
        p.write_text(make_proof_svg(group,n,uris,placement_mm=common_size,light_window_candidate=True),encoding="utf-8")
        candidate_paths.append(p)
    candidate_html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>十二生肖 30mm 光腔适配候选</title><style>@page{size:A4 portrait;margin:0}html,body{margin:0;padding:0;background:#e8eaed}.sheet{width:210mm;height:297mm;margin:8mm auto;background:white;page-break-after:always}.sheet img{display:block;width:210mm;height:297mm}@media print{html,body{background:white}.sheet{margin:0;break-after:page}.sheet:last-child{break-after:auto}}</style><body><div class="sheet"><img src="proof-a4-page-1.svg"></div><div class="sheet"><img src="proof-a4-page-2.svg"></div></body></html>'''
    (candidate_dir/"index.html").write_text(candidate_html,encoding="utf-8")
    (candidate_dir/"README.md").write_text(f"""# 30 mm 光腔适配候选\n\n全部十二张原始 1024×1024 PNG 统一置入尺寸为 {common_size:.2f}×{common_size:.2f} mm。alpha≥128 主形像素中心均落在理想 AF30 八边形内，保留至少 0.5 mm 名义余量。每款主形包围盒与只读越界统计见上级目录 validation.json。PNG 原始字节、颜色、alpha、朝向和造型均未改动。本页只是尺寸对比，不是制造文件。\n""",encoding="utf-8")
    optics = OUT / "horse-optical-zones-concept.svg"
    optics.write_text(make_optics_svg(horse_uri), encoding="utf-8")
    (OUT / "optical-zones-notes.md").write_text(make_optics_notes(), encoding="utf-8")
    make_overview(entries, pngs, OUT / "overview-12up.jpg")
    html_doc = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>十二生肖 37 mm 1:1 尺寸校样</title>
<style>@page{size:A4 portrait;margin:0}html,body{margin:0;padding:0;background:#e8eaed;font-family:Arial,sans-serif}.sheet{display:block;width:210mm;height:297mm;margin:8mm auto;background:white;box-shadow:0 2px 12px #0003;page-break-after:always}.sheet:last-child{page-break-after:auto}.sheet img{display:block;width:210mm;height:297mm}@media print{html,body{background:white}.sheet{margin:0;box-shadow:none;break-after:page}.sheet:last-child{break-after:auto}}</style>
<body><div class="sheet"><img src="proof-a4-page-1.svg"></div><div class="sheet"><img src="proof-a4-page-2.svg"></div></body></html>"""
    (OUT / "print.html").write_text(html_doc, encoding="utf-8")
    (OUT / "index.html").write_text(make_index_html(common_size), encoding="utf-8")
    (candidate_dir/"print.html").write_text(candidate_html,encoding="utf-8")
    (OUT / "README.md").write_text(make_readme(common_size,alpha_audits,candidate_report),encoding="utf-8")

    checks = []
    embedded_image_bytes_exact = True
    proof_image_dimensions_exact = True
    proof_files=[(p,37.0) for p in page_paths]+[(p,common_size) for p in candidate_paths]
    image_sources={sha(p):p for p in pngs.values()}
    for p,expected_placement in proof_files+[(optics,None)]:
        doc = ET.parse(p).getroot()
        images = [e for e in doc.iter() if e.tag.endswith("image")]
        refs = [e.attrib.get("href", "") for e in images]
        image_bytes_ok = True
        for image_el in images:
            href = image_el.attrib.get("href", "")
            try:
                payload = base64.b64decode(href.split(",", 1)[1], validate=True)
                source = HORSE if p == optics else image_sources[hashlib.sha256(payload).hexdigest()]
                image_bytes_ok &= payload == source.read_bytes()
            except Exception:
                image_bytes_ok = False
        dimensions_ok = (p == optics or all(
            float(el.attrib.get("width", "nan")) == expected_placement
            and float(el.attrib.get("height", "nan")) == expected_placement for el in images))
        embedded_image_bytes_exact &= image_bytes_ok
        proof_image_dimensions_exact &= dimensions_ok
        a4_size_ok=(doc.attrib.get("width")=="210mm" and doc.attrib.get("height")=="297mm") if p in page_paths+candidate_paths else None
        checks.append({"file": str(p.relative_to(OUT)).replace("\\","/"), "xml_well_formed": True,
                       "embedded_png_count": len(refs), "all_images_data_uri": all(v.startswith("data:image/png;base64,") for v in refs),
                       "embedded_png_bytes_exact_source": image_bytes_ok,
                       "A4_portrait_page_size": a4_size_ok,
                       "proof_placement_expected_mm": expected_placement,
                       "proof_placements_match_expected_square": dimensions_ok})
    html_audits=[]
    for html_path in [OUT/"index.html",OUT/"print.html",candidate_dir/"index.html",candidate_dir/"print.html"]:
        refs=re.findall(r'(?:href|src)="([^"]+)"',html_path.read_text(encoding="utf-8"))
        local_refs=all(not ref.startswith(("http:","https:","//","data:")) for ref in refs)
        exist=all((html_path.parent/ref).exists() for ref in refs if not ref.startswith(("http:","https:","//","data:")))
        html_audits.append({"file":str(html_path.relative_to(OUT)).replace("\\","/"),
                            "references_are_local":local_refs,"all_references_exist":exist})
    # One 37 mm image square per zodiac; keep a mathematical non-overlap audit.
    cards = []
    for page_no in range(2):
        for i, e in enumerate(pages[page_no]):
            x = [14.0, 81.0, 148.0][i % 3] + 2.5
            y = [32.0, 151.0][i // 3] + 8.0
            cards.append({"id": e["id"], "page": page_no+1, "placement_mm": [x, y, 37.0, 37.0],
                          "card_box_mm": [x-2.5, y-8.0, 58.0, 106.0]})
    no_overlaps = True
    for i, a in enumerate(cards):
        ax, ay, aw, ah = a["card_box_mm"]
        for b in cards[i+1:]:
            if a["page"] != b["page"]:
                continue
            bx, by, bw, bh = b["card_box_mm"]
            overlap = ax < bx+bw and ax+aw > bx and ay < by+bh and ay+ah > by
            if overlap:
                no_overlaps = False
    final_hashes = {e["id"]: sha(pngs[e["id"]]) for e in entries}
    horse_sha_after = sha(HORSE)
    result = {
        "generated_local_date": "2026-10-11",
        "scope": "layout and visual-size study only; not manufacturing output",
        "source_manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "source_geometry": str(GEOMETRY.relative_to(ROOT)).replace("\\", "/"),
        "reference_dimensions_mm": {"outer_octagon_across_flats": 37.0,
                                     "antenna_outer_coil_envelope_across_flats": 34.0,
                                     "spacer_window_across_flats": 30.0,
                                     "orientation":"flat top and bottom",
                                     "values_checked_against_geometry_parameters": {
                                         "outer": geo["parameters"]["across_flats_mm"],
                                         "inner": geo["parameters"]["spacer_window_across_flats_mm"]}},
        "proof_layout": {"pages": 2, "paper": "A4 portrait", "animals": 12,
                         "raster_placement_mm_each": [37.0, 37.0], "print_scale": "100% / actual size",
                         "tile_overlap": not no_overlaps, "tile_boxes_mm": cards,
                         "all_embedded_image_bytes_match_original": embedded_image_bytes_exact,
                         "all_proof_rasters_37mm_square": proof_image_dimensions_exact,
                         "print_svg_checks": [c for c in checks if c["file"].startswith("proof-a4-page-") or c["file"].startswith("light-window-candidate/")],
                         "portable_html_checks":html_audits},
        "alpha_visibility_audit_read_only": alpha_audits,
        "light_window_candidate": {"uniform_canvas_placement_mm": [common_size,common_size],
                                   "target":"all alpha>=128 pixel centers within ideal AF30 with at least 0.5 mm nominal inset",
                                   "animals_inside":sum(1 for x in candidate_report.values() if x["main_shape_inside_af30_with_0_5mm_inset"]),
                                   "per_animal_alpha_ge_128_ink_bbox_and_containment":candidate_report,
                                   "pages":[str(p.relative_to(OUT)).replace("\\","/") for p in candidate_paths],
                                   "source_png_bytes_modified":False},
        "optics_concept": {"file": optics.name, "planar_comparison": [
            "full FR-4 with copper and solder-mask windows, optionally paired with non-metal diffuser",
            "separate practical apertures plus non-metal diffuser"],
            "horse_shaped_milling_created": False, "manufacturing_geometry_created": False,
            "process_thresholds": "pending supplier/process review and physical samples"},
        "horse_png": {"path": str(HORSE.relative_to(ROOT)).replace("\\", "/"),
                      "mode": horse_img.mode, "dimensions_px": list(horse_img.size),
                      "sha256_before": horse_sha_before, "sha256_after": horse_sha_after,
                      "unchanged": horse_sha_before == horse_sha_after,
                      "visual_manual_review_required": ["small scattered alpha pixels around primary contour",
                                                        "fine transparent gaps and narrow islands"]},
        "single_ink_source_hashes_before": before,
        "single_ink_source_hashes_after": final_hashes,
        "all_single_ink_sources_unchanged": before == final_hashes,
        "checks_pass": (len(entries) == 12 and no_overlaps and all(c["all_images_data_uri"] for c in checks)
                        and embedded_image_bytes_exact and proof_image_dimensions_exact
                        and all(x["A4_portrait_page_size"] for x in checks if x["A4_portrait_page_size"] is not None)
                        and all(x["references_are_local"] and x["all_references_exist"] for x in html_audits)
                        and all(v["main_shape_inside_af30_with_0_5mm_inset"] for v in candidate_report.values())
                        and horse_sha_before == horse_sha_after and before == final_hashes
                        and geo["parameters"]["across_flats_mm"] == 37
                        and geo["parameters"]["spacer_window_across_flats_mm"] == 30)
    }
    (OUT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    if not result["checks_pass"]:
        raise RuntimeError("Validation did not pass; see validation.json")
    print(json.dumps({"output": str(OUT), "checks_pass": result["checks_pass"],
                      "proof_pages": [p.name for p in page_paths], "other": [optics.name, "print.html", "overview-12up.jpg"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
