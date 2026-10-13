"""Make a dimensionally exact A4 assembly jig from the saved lamp layout."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from constellation_lamp.model import compile_layout, read_json

OUT = ROOT / "output" / "pdf"
PDF = OUT / "星座灯_400mm_A4拼接定位模板.pdf"
COLS = (0.0, 140.0, 280.0, 400.0)
ROWS = (0.0, 200.0, 400.0)
OVERLAP = 10.0
PW, PH = A4
FONT = "JigChinese"
LABEL_FONT = "Helvetica-Bold"


def text(c, x, y, value, size=9, gray=0.0, align="left", font=FONT):
    """Text in page millimetres measured from the top left."""
    c.setFont(font, size)
    c.setFillGray(gray)
    method = {"left": c.drawString, "center": c.drawCentredString,
              "right": c.drawRightString}[align]
    method(x * mm, PH - y * mm, str(value))


def line(c, x1, y1, x2, y2, gray=0, width=.2, dash=()):
    c.setStrokeGray(gray)
    c.setLineWidth(width * mm)
    c.setDash([n * mm for n in dash])
    c.line(x1 * mm, PH - y1 * mm, x2 * mm, PH - y2 * mm)
    c.setDash()


def rect(c, x, y, w, h, gray=0, width=.2, fill=None, dash=()):
    c.setStrokeGray(gray)
    c.setLineWidth(width * mm)
    c.setDash([n * mm for n in dash])
    if fill is not None:
        c.setFillGray(fill)
    c.rect(x * mm, PH - (y + h) * mm, w * mm, h * mm,
           stroke=1, fill=int(fill is not None))
    c.setDash()


def ruler(c, x, y, length=100, vertical=False):
    if vertical:
        line(c, x, y, x, y + length, width=.22)
    else:
        line(c, x, y, x + length, y, width=.22)
    for n in range(0, length + 1, 5):
        tick = 2 if n % 10 == 0 else 1
        if vertical:
            line(c, x - tick, y + n, x, y + n, width=.15)
            if n % 50 == 0:
                text(c, x - 3, y + n + 1, n, 6.5, align="right", font="Helvetica")
        else:
            line(c, x + n, y, x + n, y - tick, width=.15)
            if n % 10 == 0:
                text(c, x + n, y + 3.2, n, 6.5, align="center", font="Helvetica")


def polygon(piece, width=5):
    a, b = piece.path_mm
    length = math.dist(a, b)
    dx, dy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -dy * width / 2, dx * width / 2
    return [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny),
            (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]


def segment_distance(x, y, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((x - a[0]) * vx + (y - a[1]) * vy) / (vx * vx + vy * vy)))
    return math.hypot(x - a[0] - t * vx, y - a[1] - t * vy)


def rect_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def label_positions(runtime):
    """Place horizontal identifiers with leaders clear of the physical strips."""
    labels = []
    for order, piece in enumerate(runtime.pieces, 1):
        a, b = piece.path_mm
        center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        length = math.dist(a, b)
        tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        nx, ny = -ty, tx
        value = f"P{order:02d}"
        w = pdfmetrics.stringWidth(value, LABEL_FONT, 6.5) / mm + 1.0
        h = 3.0
        candidates = []
        for offset in (5.5, 8, 11, 14, 18, 23):
            for along in (0, -3, 3, -7, 7, -11, 11):
                for side in (1, -1):
                    x = center[0] + nx * offset * side + tx * along
                    y = center[1] + ny * offset * side + ty * along
                    box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                    if min(box[:2]) < 6 or max(box[2:]) > 394:
                        continue
                    samples = [(x, y), (box[0], box[1]), (box[2], box[1]),
                               (box[0], box[3]), (box[2], box[3])]
                    collisions = sum(
                        any(segment_distance(sx, sy, *p.path_mm) < 3.1 for sx, sy in samples)
                        for p in runtime.pieces)
                    label_hits = sum(rect_overlap(box, old[3]) for old in labels)
                    score = collisions * 2000 + label_hits * 3000 + offset + abs(along) * .5
                    candidates.append((score, x, y, box))
        _, x, y, box = min(candidates)
        labels.append((value, (x, y), center, box))
    return labels


def draw_board(c, runtime, labels, origin, scale=1, identifiers=True, grid=True):
    """Render all source geometry with a single uniform mm-to-point transform."""
    ox, oy = origin
    c.saveState()
    c.translate(ox * mm, PH - oy * mm)
    c.scale(mm * scale, -mm * scale)

    if grid:
        for n in range(0, 401, 10):
            c.setStrokeGray(.86 if n % 50 == 0 else .93)
            c.setLineWidth(.11 if n % 50 == 0 else .07)
            c.setDash([.35, 1.3])
            c.line(n, 0, n, 400)
            c.line(0, n, 400, n)
        c.setDash()
        c.setStrokeGray(.55)
        c.setLineWidth(.12)
        c.setDash([2, 2])
        c.rect(5, 5, 390, 390, stroke=1, fill=0)
        c.setDash()

    for piece in runtime.pieces:
        corners = polygon(piece, runtime.layout["strip_width_mm"])
        path = c.beginPath()
        path.moveTo(*corners[0])
        for point in corners[1:]:
            path.lineTo(*point)
        path.close()
        c.setStrokeGray(0)
        c.setFillGray(.96)
        c.setLineWidth(.22)
        c.drawPath(path, stroke=1, fill=1)

        a, b = piece.path_mm
        if piece.reverse:
            a, b = b, a
        length = math.dist(a, b)
        tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        tip = (x + tx * 1.25, y + ty * 1.25)
        tail = (x - tx * 1.25, y - ty * 1.25)
        c.setStrokeGray(0)
        c.setLineWidth(.20)
        c.line(*tail, *tip)
        c.line(*tip, tip[0] - tx * .85 - ty * .55, tip[1] - ty * .85 + tx * .55)
        c.line(*tip, tip[0] - tx * .85 + ty * .55, tip[1] - ty * .85 - tx * .55)
        c.setFillGray(1)
        for index in piece.indices:
            led = runtime.leds[index]
            c.circle(led.x_mm, led.y_mm, .58, stroke=1, fill=1)

    if identifiers:
        for value, (x, y), center, box in labels:
            c.setStrokeGray(.35)
            c.setLineWidth(.12)
            c.line(*center, x, y)
            c.setFillGray(1)
            c.rect(box[0], box[1], box[2] - box[0], box[3] - box[1], fill=1, stroke=0)
            c.saveState()
            c.translate(x, y)
            c.scale(1 / mm, -1 / mm)
            c.setFillGray(0)
            c.setFont(LABEL_FONT, 6.5)
            c.drawCentredString(0, -2.2, value)
            c.restoreState()

    c.setStrokeGray(0)
    c.setLineWidth(.35)
    c.rect(0, 0, 400, 400, stroke=1, fill=0)
    c.restoreState()


def registration_marks(runtime, labels):
    """Use identical global positions in both copies of every overlap band."""
    marks = []
    for seam, x in enumerate((145, 285), 1):
        for row, (low, high) in enumerate(((20, 185), (225, 385)), 1):
            for suffix, start, end in (("a", low, low + 40), ("b", high - 40, high)):
                candidates = range(start, end + 1)
                y = max(candidates, key=lambda y: min(
                    segment_distance(x, y, *p.path_mm) for p in runtime.pieces))
                marks.append((x, y, f"V{seam}{row}{suffix}"))
    for col, (low, high) in enumerate(((20, 120), (160, 260), (300, 380)), 1):
        for suffix, start, end in (("a", low, low + 20), ("b", high - 20, high)):
            x = max(range(start, end + 1), key=lambda x: min(
                segment_distance(x, 205, *p.path_mm) for p in runtime.pieces))
            marks.append((x, 205, f"H{col}{suffix}"))
    return marks


def small_map(c, x, y, selected=None, cell=7):
    for row in range(2):
        for col in range(3):
            value = f"{'AB'[row]}{col + 1}"
            chosen = value == selected
            rect(c, x + col * cell, y + row * cell, cell, cell, width=.15,
                 fill=.80 if chosen else 1)
            text(c, x + (col + .5) * cell, y + row * cell + cell * .66,
                 value, 7.5 if cell > 10 else 6, align="center", font="Helvetica-Bold")


def guide(c, runtime, labels, sha):
    text(c, 15, 20, "星座灯 / A4 拼接定位模板", 19)
    text(c, 15, 29, "400 × 400 mm 亚克力 · 人马座 · 灯条粘贴面视图", 11)
    line(c, 15, 34, 195, 34, width=.4)
    text(c, 15, 44, "打印设置", 12)
    text(c, 15, 52, "A4 纵向、单面、实际大小 / 100%。关闭适合页面、缩放和多页合一。", 9)
    text(c, 15, 59, "第 2-7 页是六张定位纸；本页与第 8-9 页为说明和裁切表。", 9)
    text(c, 15, 66, "先试印第 2 页：横向与纵向 100 mm 尺均应实测为 100 mm。", 9)

    text(c, 15, 79, "拼接顺序", 12)
    small_map(c, 15, 86, cell=21)
    text(c, 86, 92, "上排 A1 → A2 → A3；下排 B1 → B2 → B3。", 9)
    text(c, 86, 101, "沿各页外框实线剪下，保留右侧 / 下侧 10 mm 搭接带。", 8.5)
    text(c, 86, 110, "将右页盖在左页搭接带上，再将下排盖在上排搭接带上。", 8.5)
    text(c, 86, 119, "同编号十字重合、灯条轮廓连续后，用胶带固定纸张。", 8.5)
    text(c, 15, 136, "拼好后外轮廓为 400 × 400 mm。虚线是搭接位置，不沿它剪。", 9)

    text(c, 15, 149, "定位与灯条方向", 12)
    text(c, 15, 157, "将模板放在透明亚克力下方，图案朝向你；在你面对的这一面贴灯条。", 9)
    text(c, 15, 164, "纸张上边对齐板上边；从贴灯条面看本图。翻到板另一面看时图案左右相反。", 9)
    text(c, 15, 171, "矩形外框 = 灯条 PCB 轮廓；圆点 = LED 中心；箭头 = DIN → DOUT。", 9)
    text(c, 15, 178, "P01-P66 是电气串联顺序，按附表裁切；连线两端的留空是布局原值。", 9)
    text(c, 15, 185, "每个星点为两条 10 × 5 mm 灯条，排间净距 2 mm，整体 10 × 12 mm。", 9)

    draw_board(c, runtime, labels, (15, 197), .18, identifiers=False, grid=False)
    text(c, 97, 204, "布局总览（缩小示意）", 10)
    text(c, 97, 215, f"{len(runtime.stars)} 个星点 / {len(runtime.edges)} 条连线 / {len(runtime.pieces)} 段灯条", 9)
    text(c, 97, 224, f"{runtime.led_count} 颗灯 / 灯间距 5 mm / 每 2 灯裁切", 9)
    text(c, 97, 233, "灯条总长 1.340 m；板边安全留量 5 mm。", 9)
    text(c, 97, 244, "实际串联：P01 DOUT → P02 DIN → … → P66。", 8.5)
    text(c, 97, 253, "段与段之间用导线连接，星座分支不能作数据分叉。", 8.5)
    text(c, 97, 262, "坐标原点为板左上角；X 向右，Y 向下，单位 mm。", 8.5)
    text(c, 15, 281, f"布局快照 SHA256: {sha[:20]}  |  制作日期 2026-10-12", 7, gray=.35)
    text(c, 195, 287, "1 / 9", 7, align="right")
    c.showPage()


def tile(c, runtime, labels, marks, row, col):
    name = f"{'AB'[row]}{col + 1}"
    page = 2 + row * 3 + col
    x0, x1 = COLS[col:col + 2]
    y0, y1 = ROWS[row:row + 2]
    w, h = x1 - x0, y1 - y0
    full_w = w + (OVERLAP if col < 2 else 0)
    full_h = h + (OVERLAP if row == 0 else 0)
    left, top = 35.0, 40.0
    text(c, 15, 18, f"{name}  /  {'上' if row == 0 else '下'}排第 {col + 1} 张", 15)
    text(c, 15, 26, "A4 纵向 · 100% 实际大小 · 灯条粘贴面 · 上边 ↑", 8.5)
    text(c, 15, 33, f"板坐标 X {x0:g}-{x1:g} / Y {y0:g}-{y1:g} mm；搭接带另加 10 mm。", 8)
    small_map(c, 175, 12, selected=name, cell=7)

    c.saveState()
    clip = c.beginPath()
    clip.rect(left * mm, PH - (top + full_h) * mm, full_w * mm, full_h * mm)
    c.clipPath(clip, stroke=0, fill=0)
    draw_board(c, runtime, labels, (left - x0, top - y0))
    for x, y, identifier in marks:
        if x0 <= x <= x0 + full_w and y0 <= y <= y0 + full_h:
            px, py = left + x - x0, top + y - y0
            line(c, px - 1.4, py, px + 1.4, py, gray=.15, width=.2)
            line(c, px, py - 1.4, px, py + 1.4, gray=.15, width=.2)
            text(c, px, py - 2.3, identifier, 5.5, align="center", font="Helvetica")
    text(c, left + 5, top + 7, name, 9, gray=.4, font="Helvetica-Bold")
    c.restoreState()

    rect(c, left, top, full_w, full_h, width=.35)
    if col < 2:
        line(c, left + w, top, left + w, top + full_h, gray=.25, width=.2, dash=(2, 1))
        c.saveState()
        c.translate((left + w + 7) * mm, PH - (top + 100) * mm)
        c.rotate(90)
        c.setFont(FONT, 7)
        c.setFillGray(.3)
        c.drawCentredString(0, 0, "10 mm 搭接带 / 保留")
        c.restoreState()
    if row == 0:
        line(c, left, top + h, left + full_w, top + h, gray=.25, width=.2, dash=(2, 1))
        text(c, left + w / 2, top + h + 7, "10 mm 搭接带 / 保留", 7, gray=.3, align="center")

    for x in range(int(x0), int(x1) + 1, 20):
        tick = left + x - x0
        line(c, tick, top - 1.5, tick, top, gray=.25, width=.15)
        text(c, tick, top - 2.5, x, 6, gray=.25, align="center", font="Helvetica")
    for y in range(int(y0), int(y1) + 1, 20):
        tick = top + y - y0
        line(c, left - 1.5, tick, left, tick, gray=.25, width=.15)
        text(c, left - 2.5, tick + .8, y, 6, gray=.25, align="right", font="Helvetica")

    ruler(c, 22, 116, vertical=True)
    text(c, 16, 224, "纵向", 7)
    text(c, 13, 229, "100 mm", 7)
    text(c, 35, 258, "沿外框实线剪下；虚线处叠放相邻纸张，保留搭接带。", 8)
    ruler(c, 35, 266)
    text(c, 144, 268, "横向 100 mm", 8)
    text(c, 35, 278, "矩形 = 灯条外形；圆点 = LED；箭头 = DIN → DOUT。", 8)
    text(c, 35, 285, "两把校准尺均须量得 100 mm，再拼接使用。", 8)
    text(c, 195, 287, f"{page} / 9", 7, align="right")
    c.showPage()


def cutting_pages(c, runtime):
    cols = [15, 28, 73, 83, 100, 119, 156, 193]
    headings = ["段号", "位置 / 归属", "灯数", "切长 mm", "LED 索引", "DIN (X,Y)", "DOUT (X,Y)"]
    for part in range(2):
        text(c, 15, 20, f"灯条裁切与方向表 / {part + 1} of 2", 16)
        text(c, 15, 29, "坐标单位 mm；左上角为 (0,0)。LED 索引从 0 开始，与项目固件一致。", 8.5)
        text(c, 15, 36, "按 P01-P66 串联；每段灯条实物箭头应与定位纸箭头同向。", 8.5)
        table_top = 43
        row_h = 6.7
        rect(c, 15, table_top, 178, 7, fill=.88, width=.18)
        for i, heading in enumerate(headings):
            text(c, (cols[i] + cols[i + 1]) / 2, table_top + 4.8, heading, 7.5, align="center")
        selected = runtime.pieces[part * 33:(part + 1) * 33]
        for local, piece in enumerate(selected):
            order = part * 33 + local + 1
            y = table_top + 7 + local * row_h
            rect(c, 15, y, 178, row_h, gray=.65, width=.1, fill=.96 if local % 2 else 1)
            a, b = piece.path_mm
            din, dout = (b, a) if piece.reverse else (a, b)
            if piece.owner_type == "star":
                owner = f"星 HIP{piece.owner_id.split('_')[-1]} / {'上排' if piece.id.endswith('row0') else '下排'}"
            else:
                owner = f"连线 {piece.owner_id}"
            values = [f"P{order:02d}", owner, piece.led_count,
                      f"{piece.cut_length_mm:g}",
                      f"{piece.first_index}-{piece.first_index + piece.led_count - 1}",
                      f"{din[0]:.1f}, {din[1]:.1f}", f"{dout[0]:.1f}, {dout[1]:.1f}"]
            for i, value in enumerate(values):
                text(c, (cols[i] + cols[i + 1]) / 2, y + 4.5, value,
                     7.2 if i == 1 else 7.6, align="center",
                     font=FONT if i == 1 else "Helvetica")
        for x in cols:
            line(c, x, table_top, x, table_top + 7 + len(selected) * row_h, gray=.5, width=.1)
        text(c, 15, 280, "共 66 段 / 268 灯 / 1340 mm；星点两排之间净距 2 mm。", 8)
        text(c, 193, 287, f"{8 + part} / 9", 7, align="right")
        c.showPage()


def main():
    pdfmetrics.registerFont(TTFont(FONT, "C:/Windows/Fonts/simhei.ttf"))
    data_paths = [ROOT / "data" / n for n in ("catalog.json", "constellation.json", "layout.json")]
    source_hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in data_paths}
    runtime = compile_layout(*(read_json(p) for p in data_paths))
    assert runtime.layout["panel"]["width_mm"] == runtime.layout["panel"]["height_mm"] == 400
    assert runtime.layout["strip_width_mm"] == 5
    assert all(len(p.path_mm) == 2 and abs(math.dist(*p.path_mm) - p.cut_length_mm) < 1e-6 for p in runtime.pieces)
    labels = label_positions(runtime)
    assert all(not rect_overlap(a[3], b[3]) for i, a in enumerate(labels) for b in labels[i + 1:])
    marks = registration_marks(runtime, labels)
    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF), pagesize=A4, pageCompression=1)
    c.setTitle("星座灯 400×400 mm - A4 拼接定位与裁切模板")
    c.setAuthor("Constellation Lamp Project")
    c.setSubject("100% actual size; six A4 jig tiles; 10 mm overlap")
    c.setViewerPreference("PrintScaling", "None")
    guide(c, runtime, labels, source_hashes["data/layout.json"])
    for row in range(2):
        for col in range(3):
            tile(c, runtime, labels, marks, row, col)
    cutting_pages(c, runtime)
    c.save()
    manifest = {
        "pdf": str(PDF), "pages": 9, "template_pdf_pages": [2, 3, 4, 5, 6, 7],
        "page_size_mm": [210, 297], "assembled_board_mm": [400, 400],
        "tile_columns_mm": list(COLS), "tile_rows_mm": list(ROWS), "overlap_mm": OVERLAP,
        "view": "lamp-strip mounting face, no mirror, x right and y down",
        "source_sha256": source_hashes, "strip_width_mm": 5, "led_pitch_mm": 5,
        "pieces": len(runtime.pieces), "leds": runtime.led_count,
        "labels": [{"id": p[0], "center_mm": p[1], "box_mm": p[3]} for p in labels],
        "registration_marks": marks,
        "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
    }
    (OUT / "placement-template-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == source_hashes[p.relative_to(ROOT).as_posix()] for p in data_paths)
    print(json.dumps({"pdf": str(PDF), "pages": 9, "pieces": len(runtime.pieces), "leds": runtime.led_count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
