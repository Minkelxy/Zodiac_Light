"""Create three Chinese project showcase PDFs from the saved project evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from constellation_lamp.model import compile_layout, read_json
from constellation_lamp.effects import render
from constellation_lamp.preview import _display_rgb, _initial_params, _power_frame
from constellation_lamp.hardware import HardwareProfile

OUT = ROOT / 'output/pdf'
W, H = landscape(A4)
INK = '#142230'
BG = '#0D1524'
MUTED = '#64717E'
PAPER = '#F6F4EF'
CYAN = '#62D5DA'
GOLD = '#EEC27B'
RELEASE = 'https://github.com/Minkelxy/Zodiac_Light/releases/tag/project-2026-10-14'
REPO = 'https://github.com/Minkelxy/Zodiac_Light'
DATE = '2026.10.14'
FILES = ['星座灯项目_一页成果速览.pdf', '星座灯_40cm成果展示册.pdf', 'NFC符咒_双款设计展示册.pdf']
DATA = ROOT / 'data'
RUNTIME = compile_layout(*(read_json(DATA / name) for name in ('catalog.json', 'constellation.json', 'layout.json')))
EFFECTS = read_json(DATA / 'effects.json')
HARDWARE = HardwareProfile.load(DATA / 'hardware.json').validate_runtime(RUNTIME)
GEOMETRY = json.loads((ROOT / 'output/engraving-final-u1/fabrication-manifest.json').read_text(encoding='utf-8-sig'))
HARDWARE_ROOT = ROOT / 'hardware/nfc-talisman'
ASSET_ROOT = HARDWARE_ROOT / 'variants'
FONT = 'ShowcaseZH'
BOLD = 'ShowcaseZHBold'


def register_fonts():
    for name, file in ((FONT, 'msyh.ttc'), (BOLD, 'msyhbd.ttc')):
        pdfmetrics.registerFont(TTFont(name, 'C:/Windows/Fonts/' + file, subfontIndex=0))


def color(value):
    return colors.HexColor(value)


def text(c, value, x, y, size=13, fill=INK, bold=False):
    c.setFillColor(color(fill))
    c.setFont(BOLD if bold else FONT, size)
    c.drawString(x, y, str(value))


def lines(c, value, x, y, width, size=13, fill=INK, leading=None):
    leading = leading or size * 1.65
    for paragraph in value.split('\n'):
        line = ''
        for char in paragraph:
            if pdfmetrics.stringWidth(line + char, FONT, size) > width and line:
                text(c, line, x, y, size, fill)
                y -= leading
                line = char
            else:
                line += char
        if line:
            text(c, line, x, y, size, fill)
        y -= leading
    if y < 49:
        raise ValueError('Body text entered footer area')
    return y


def box(c, x, y, w, h, fill=PAPER, radius=10, stroke=None):
    c.setFillColor(color(fill))
    c.setStrokeColor(color(stroke or fill))
    c.roundRect(x, y, w, h, radius, fill=1, stroke=bool(stroke))


def image(c, path, x, y, w, h):
    c.drawImage(ImageReader(str(path)), x, y, width=w, height=h,
                preserveAspectRatio=True, anchor='c', mask='auto')


def header(c, title, subtitle, number, total, dark=False, collection='项目成果'):
    c.setFillColor(color(BG if dark else '#FFFFFF'))
    c.rect(0, 0, W, H, fill=1, stroke=0)
    fg = '#F5F4ED' if dark else INK
    text(c, collection + '  /  ' + DATE, 36, H - 29, 9, CYAN if dark else MUTED)
    text(c, title, 36, H - 76, 29, fg, True)
    text(c, subtitle, 36, H - 104, 11, '#AEC0D0' if dark else MUTED)
    footer(c, number, total, dark)


def footer(c, page, total, dark=False):
    fg = '#93A6B7' if dark else MUTED
    c.setStrokeColor(color('#263548' if dark else '#DFE4E5'))
    c.setLineWidth(.5)
    c.line(36, 37, W - 36, 37)
    text(c, '星座灯与 NFC 符咒  |  设计、仿真与数字交付', 36, 22, 8, fg)
    c.setFillColor(color(fg))
    c.setFont(FONT, 8)
    c.drawRightString(W - 36, 22, f'{page:02d} / {total:02d}')


def sources(c, value, dark=False):
    text(c, '依据：' + value, 36, 48, 7.2, '#8297AB' if dark else MUTED)


def metric(c, value, label, x, y, width=130, dark=False):
    text(c, value, x, y, 29, GOLD if dark else INK, True)
    text(c, label, x, y - 25, 10, '#AAC0D2' if dark else MUTED)


def qr(c, x, y, size=68):
    box(c, x - 5, y - 5, size + 10, size + 10, '#FFFFFF', 4)
    widget = QrCodeWidget(RELEASE)
    bounds = widget.getBounds()
    d = Drawing(size, size, transform=[size / (bounds[2]-bounds[0]), 0, 0,
        size / (bounds[3]-bounds[1]), 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, x, y)
    c.linkURL(RELEASE, (x, y, x + size, y + size), relative=0)


def download(c, x, y, w=300, dark=False):
    box(c, x, y, w, 42, '#244251' if dark else INK, 6)
    text(c, '打开完整项目与制作资料', x + 14, y + 15, 13, '#FFFFFF', True)
    c.linkURL(RELEASE, (x, y, x + w, y + 42), relative=0)


def line_art(c, x, y, size, *, dark=True, stars=True):
    box(c, x, y, size, size, BG if dark else PAPER, 3)
    c.setStrokeColor(color('#E8F0F1' if dark else '#263742'))
    c.setLineWidth(.45)
    for path in GEOMETRY['paths_mm'].values():
        for a, b in zip(path, path[1:]):
            c.line(x + a[0]/400*size, y + size - a[1]/400*size,
                   x + b[0]/400*size, y + size - b[1]/400*size)
    if stars:
        c.setStrokeColor(color(GOLD if dark else '#BF9443'))
        c.setLineWidth(.6)
        lookup = {s.id: s for s in RUNTIME.stars}
        for edge in RUNTIME.edges:
            a, b = lookup[edge.start_id], lookup[edge.end_id]
            c.line(x+a.x_mm/400*size, y+size-a.y_mm/400*size,
                   x+b.x_mm/400*size, y+size-b.y_mm/400*size)
        c.setFillColor(color(GOLD if dark else '#A17830'))
        for star in RUNTIME.stars:
            c.circle(x+star.x_mm/400*size, y+size-star.y_mm/400*size, 1.4, fill=1, stroke=0)


def effect_plot(c, effect, x, y, size, time=2400):
    box(c, x, y, size, size, BG, 6)
    frame = np.zeros((RUNTIME.led_count, 3), dtype=np.uint8)
    params = _initial_params(effect, 1, .2, None, EFFECTS['defaults'], EFFECTS['presets'])
    render(RUNTIME, time, params, {}, frame)
    frame, _ = _power_frame(frame, HARDWARE)
    rgb = _display_rgb(frame, 8)
    for led, light in zip(RUNTIME.leds, rgb):
        if led.owner_type == 'hidden':
            continue
        px, py = x + (led.x_mm+6)/412*size, y+size-(led.y_mm+6)/412*size
        c.setFillColor(colors.Color(*[float(v) for v in light]))
        c.saveState()
        c.setFillAlpha(.18)
        c.circle(px, py, max(2, size*.012), fill=1, stroke=0)
        c.restoreState()
        c.circle(px, py, max(.65, size*.003), fill=1, stroke=0)


def tile_grid(c, x, y, w=260, h=260):
    c.setFillColor(color('#FFFFFF'))
    c.setStrokeColor(color('#9BABB6'))
    c.setLineWidth(.7)
    cols, rows = [0, 140, 280, 400], [0, 200, 400]
    for r in range(2):
        for col in range(3):
            a, b = cols[col], cols[col+1]
            xx, yy = x+a/400*w, y+h-(r+1)*h/2
            c.rect(xx, yy, (b-a)/400*w, h/2, fill=0)
            text(c, f'{"AB"[r]}{col+1}', xx+5, yy+h/2-18, 9, '#607C89')
    c.setStrokeColor(color('#324C5E'))
    c.setLineWidth(.4)
    for path in GEOMETRY['paths_mm'].values():
        for a, b in zip(path, path[1:]):
            c.line(x+a[0]/400*w, y+h-a[1]/400*h, x+b[0]/400*w, y+h-b[1]/400*h)


def new_pdf(name, title):
    c = canvas.Canvas(str(OUT/name), pagesize=(W, H), pageCompression=1)
    c.setTitle(title)
    c.setAuthor('Zodiac Light Project')
    c.setSubject('2026-10-14 saved project showcase; design and simulation, physical validation pending')
    c.setKeywords('星座灯 NFC 射手座 U1 项目成果 设计展示')
    return c


def overview():
    c = new_pdf(FILES[0], '星座灯与 NFC 符咒 - 一页成果速览')
    header(c, '星座灯与 NFC 符咒', '从星图、造型到制作文件：一件星座灯，两款双面符咒。', 1, 1)
    line_art(c, 36, 156, 300)
    text(c, '40 cm 射手座星座灯', 352, 442, 17, INK, True)
    lines(c, 'U1 短发与肩胸造型\n四腿、短尾与星轨延伸\n可编程灯效 + 实尺寸刻线稿', 352, 415, 440, 12)
    text(c, '21 星  /  268 灯  /  9 种灯效', 352, 334, 16, '#247583', True)
    for variant, yy, label in [('horse-sagittarius', 226, '马 + 射手座'), ('snake-leo', 128, '蛇 + 狮子座')]:
        image(c, ASSET_ROOT/variant/'artwork/cover-review-preview.png', 352, yy, 188, 101)
        text(c, label, 554, yy+69, 14, INK, True)
        text(c, '37 mm 双面 NFC 设计', 554, yy+46, 11, MUTED)
        text(c, '外观设计预览，非实物照片', 554, yy+24, 9, MUTED)
    box(c, 36, 67, 648, 56)
    text(c, '已归档：源码、打印模板、原生工程与装配审阅资料', 50, 104, 12, INK, True)
    text(c, '已验证：185 项测试、63 项检查、Windows / Linux 自动检查', 50, 84, 10, MUTED)
    text(c, '当前为设计与数字交付成果；灯带实测、NFC 的 C1 / CAM / 实物验收待完成。', 36, 57, 8.4, MUTED)
    qr(c, 723, 74, 62)
    text(c, '完整项目', 728, 58, 8, MUTED)
    c.save()


def lamp_book():
    c = new_pdf(FILES[1], '40 cm 射手座星座灯 - 成果展示册')
    header(c, '把星图变成一件作品', '40 cm 射手座星座灯  |  U1 刻线造型与可编程灯效', 1, 6, True, '星座灯成果展示')
    line_art(c, 390, 100, 368)
    text(c, '射手座 · U1', 36, 403, 34, '#F5F4ED', True)
    lines(c, '用直线切面整理人物与马的轮廓，\n保留短发、肩胸、四腿与短尾，\n让下方的星链继续延伸成星轨。', 36, 359, 319, 15, '#C4D5E3')
    metric(c, '400 mm', '方形亚克力面板', 36, 213, dark=True)
    metric(c, '290', '最终刻线直线段', 220, 213, dark=True)
    text(c, '设计示意，非实物点亮照片。', 36, 117, 10, '#97B0C4')
    sources(c, 'U1 fabrication-manifest.json；data/layout.json', True)
    c.showPage()

    header(c, '从恒星资料到制作布局', '真实恒星身份、星座图形与实际制作位置分别保存。', 2, 6, collection='星座灯成果展示')
    effect_plot(c, 'twinkle', 36, 103, 350, 1500)
    metric(c, '21', '颗恒星', 421, 420)
    metric(c, '24', '条星座连接', 594, 420)
    lines(c, '保存 HIP 身份、名称、天球坐标与资料来源。\n把星图转换成面板中的毫米位置，保留可追溯的原始数据。', 421, 336, 367, 14)
    box(c, 421, 117, 366, 104)
    text(c, '原星图关系得到保留', 437, 191, 14, INK, True)
    lines(c, '实体灯条需保留间距；当前制作坐标最大微调约 4.67 mm。', 437, 165, 331, 12)
    text(c, '微闪灯效的静态软件仿真，显示曝光 ×8。', 36, 77, 9, MUTED)
    sources(c, 'catalog.json；constellation.json；layout.json')
    c.showPage()

    header(c, '把灯珠变成可制作的路径', '每个星点采用四灯结构，星座连接分解成灯条裁切段。', 3, 6, collection='星座灯成果展示')
    box(c, 36, 114, 394, 354)
    scale = 336/400
    ox, oy = 65, 123
    c.setStrokeColor(color('#B8C4C8'))
    c.setLineWidth(.6)
    c.rect(ox, oy, 336, 336, fill=0)
    for led in RUNTIME.leds:
        c.setFillColor(color('#A67B34' if led.owner_type == 'star' else '#2A8892'))
        c.circle(ox+led.x_mm*scale, oy+336-led.y_mm*scale, 1.12, fill=1, stroke=0)
    metric(c, '268', '颗灯珠', 460, 418)
    metric(c, '66', '个裁切段', 648, 418)
    metric(c, '1.340 m', '灯带总长', 460, 325)
    metric(c, '400 × 400', '面板尺寸 / mm', 460, 232)
    lines(c, '电气串接顺序独立保存。\n裁切表给出段号、灯数与 DIN / DOUT；接线表用于背面导线连接。', 460, 164, 330, 12)
    text(c, '毫米坐标中的灯珠位置示意。', 36, 85, 9, MUTED)
    sources(c, 'data/layout.json；build/cutting.csv；build/wiring.csv')
    c.showPage()

    header(c, '九种灯效，同一张星图', '时间、速度、亮度与随机种子显式控制，可在电脑预览或编译至参考固件。', 4, 6, True, '星座灯成果展示')
    names = [('twinkle','微闪'), ('flow','流光'), ('ripple','波纹'), ('breath','呼吸'),
             ('aurora','极光'), ('sparkle','闪耀'), ('graph_wave','图波'), ('draw','勾勒'), ('meteor','流星')]
    for i, (effect, label) in enumerate(names):
        col, row = i%3, i//3
        x, y = 36+col*259, 338-row*128
        effect_plot(c, effect, x, y, 116)
        text(c, label, x+133, y+86, 17, '#F4F6EF', True)
        text(c, effect, x+133, y+61, 10, '#AEC6D6')
    text(c, '静态软件仿真 / t=2400 ms / 显示曝光 ×8；不表示实物亮度、光通量或扩散效果。', 36, 66, 9, '#AEC0D0')
    sources(c, 'data/effects.json；effects.render；data/hardware.json', True)
    c.showPage()

    header(c, '从构图到实际尺寸的刻线稿', 'U1 定稿已整理为直线中心线，可用普通 A4 打印后拼接。', 5, 6, collection='星座灯成果展示')
    tile_grid(c, 36, 145, 320, 320)
    text(c, '六张 A4 拼成 400 × 400 mm', 36, 116, 13, INK, True)
    text(c, '本页为拼接示意，不是 1:1 加工模板。', 36, 92, 10, MUTED)
    metric(c, '290', '条直线刻画路径', 401, 421)
    metric(c, '6 张', 'A4 实尺寸拼接纸', 614, 421)
    lines(c, '刻线 PDF 共 7 页，第 2-7 页用于拼接。\n灯条定位 PDF 共 9 页，第 8-9 页包含裁切表。\n打印采用实际大小 / 100%，先实测横纵 100 mm 校准尺。', 401, 338, 381, 14)
    box(c, 401, 97, 383, 70)
    text(c, '刻线、灯条位置与数据方向各有对应资料', 415, 141, 12, INK, True)
    text(c, '对外展示用本册；实际制作使用正式模板。', 415, 118, 11, MUTED)
    sources(c, 'U1 fabrication-manifest.json；placement-template-manifest.json')
    c.showPage()

    header(c, '成果已经形成可交接的资料', '从视觉设计到运行数据，同一套文件可以继续复现和制作。', 6, 6, collection='星座灯成果展示')
    cards = [('数据与布局', '恒星资料、21 星 / 24 边关系、毫米布局、裁切与串接映射。'),
             ('造型与制作', 'U1 SVG 母图、实尺寸刻线 PDF、灯条定位与裁切表。'),
             ('预览与固件', 'Python 九种灯效、ESP32 参考固件、离线导出与串口协议。')]
    for i, (title, body) in enumerate(cards):
        x = 36+i*259
        box(c, x, 235, 242, 220)
        text(c, f'0{i+1}', x+18, 421, 13, '#33838A', True)
        text(c, title, x+18, 384, 20, INK, True)
        lines(c, body, x+18, 344, 204, 13)
    text(c, '185 项测试通过  ·  63 项项目检查通过  ·  Windows / Linux 自动检查通过', 36, 207, 12, INK, True)
    lines(c, '下一步：实际裁切与安装、ESP32 烧录、色序与供电检查、面板整体点亮和实物光效验收。', 36, 172, 658, 12)
    download(c, 36, 83, 365)
    qr(c, 714, 99)
    text(c, '扫码下载', 720, 80, 9, MUTED)
    sources(c, 'build/project-check.json；GitHub Actions；project-2026-10-14')
    c.save()


def nfc_book():
    c = new_pdf(FILES[2], '37 mm NFC 符咒 - 双款设计展示册')
    header(c, '小尺寸，双面主题', '马 + 射手座 / 蛇 + 狮子座  |  37 mm 八角 NFC 符咒设计', 1, 4, collection='NFC 双款设计展示')
    for i, (variant, label) in enumerate([('horse-sagittarius','马 + 射手座'), ('snake-leo','蛇 + 狮子座')]):
        x = 36+i*395
        box(c, x, 149, 375, 310, '#EEEAE2')
        image(c, ASSET_ROOT/variant/'artwork/cover-review-preview.png', x+12, 195, 351, 207)
        text(c, label, x+18, 425, 21, INK, True)
        text(c, '左：动物主题正面   右：星座背面', x+18, 172, 10, MUTED)
    lines(c, '两款共用核心电路，各自保留独立外观与拼板。\n本册为设计预览，图案、孔槽和颜色的最终效果需要以加工样件确认。', 36, 119, 765, 12)
    sources(c, '两款 artwork/manifest.json；variants/common/export-manifest.json')
    c.showPage()

    header(c, '星孔、槽线与五层结构', '主题外观与电路分层组织，保留实际加工和装配的检查入口。', 2, 4, collection='NFC 双款设计展示')
    labels = ['动物主题盖板', '前间隔层', '共用核心电路', '后间隔层', '星座主题盖板']
    for i, label in enumerate(labels):
        x, y = 63+i*16, 361-i*49
        c.setFillColor(color(['#DAD4C8','#E7ECEC','#98B8AD','#E7ECEC','#223646'][i]))
        c.setStrokeColor(color('#647884'))
        path=c.beginPath()
        path.moveTo(x,y); path.lineTo(x+188,y); path.lineTo(x+224,y+32); path.lineTo(x+36,y+32); path.close()
        c.drawPath(path,fill=1,stroke=1)
        text(c, f'{i+1:02d}  {label}', x+243, y+10, 12, INK)
    text(c, '五层结构示意 / 非装配实拍 / 不按比例', 63, 102, 9, MUTED)
    box(c, 561, 272, 245, 169)
    text(c, '射手座背面', 577, 411, 19, INK, True)
    metric(c, '8 孔 / 11 槽', '星孔 0.8 mm；槽宽 1.0 mm', 577, 358)
    box(c, 561, 85, 245, 169)
    text(c, '狮子座背面', 577, 224, 19, INK, True)
    metric(c, '9 孔 / 8 槽', '另有 2 条短边仅印刷连线', 577, 171)
    text(c, '孔槽的加工与透光表现待实物确认。', 577, 112, 9, MUTED)
    sources(c, 'geometry/design.json；variants/common/design-review.md')
    c.showPage()

    header(c, '共用核心，独立款式', '一个核心设计，两块独立的款式拼板；每款都是自己的 100 × 100 mm 五片拼板。', 3, 4, collection='NFC 双款设计展示')
    image(c, ASSET_ROOT/'common/layout-review/symmetric-core-layout-review.png', 36, 119, 490, 333)
    box(c, 553, 262, 253, 190)
    text(c, '两面 LED 成对对称', 570, 417, 18, INK, True)
    lines(c, '每一面各两颗 LED，\n位于中心左右 ±6 mm。\nR1-R4 保持原布局。', 570, 378, 218, 13)
    box(c, 553, 104, 253, 141)
    text(c, '3 个 PCB 文档', 570, 212, 20, INK, True)
    lines(c, '1 个共用核心 + 2 个款式拼板。\n版图与导出数据已同版归档。', 570, 180, 218, 12)
    text(c, '布局叠图用于位置审阅，不能据此认定亮度、均匀性或读写性能。', 36, 82, 10, MUTED)
    sources(c, 'layout-review/validation.json；export-manifest.json')
    c.showPage()

    header(c, '设计资料已归档，实体验证继续推进', '可以展示工程进展，也可以把明确的下一步交给制作与测试环节。', 4, 4, collection='NFC 双款设计展示')
    box(c, 36, 248, 372, 212)
    text(c, '已经形成', 54, 425, 21, INK, True)
    lines(c, '两款正反面图案与源文件\n共用原生工程与三块 PCB 快照\n各款 Gerber、BOM 与 PnP 审阅表\n42 项只读硬件归档检查通过', 54, 384, 333, 14)
    box(c, 432, 248, 374, 212, '#FFF2DE')
    text(c, '仍需完成', 450, 425, 21, INK, True)
    lines(c, 'C1 选料与装配适配\n供应商 CAM：颜色、孔槽与钻孔程序\nRF / NFC 调谐、手机读写与点亮\n首件装配、透光与光效验收', 450, 384, 333, 14)
    text(c, '当前制造状态：HOLD', 36, 215, 16, '#8D6230', True)
    lines(c, '归档记录中三块 PCB 的保存重开 DRC 为空，ERC 保留已有属性警告。\n本次展示依据保存记录；没有宣称本轮重新完成实时 ERC / DRC 或制造放行。', 36, 185, 661, 11.8)
    download(c, 36, 77, 365)
    qr(c, 714, 105)
    text(c, '工程与资料', 714, 85, 9, MUTED)
    sources(c, 'check_delivery.py；export-manifest.json；GitHub 项目交付包')
    c.save()


def main():
    if RUNTIME.led_count != 268 or len(RUNTIME.stars) != 21 or len(RUNTIME.edges) != 24 or GEOMETRY['segment_count'] != 290:
        raise ValueError('The saved project changed; review and update showcase captions before regenerating')
    register_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    overview()
    lamp_book()
    nfc_book()
    result = []
    for name, count in zip(FILES, [1, 6, 4]):
        path = OUT/name
        result.append({'path': path.relative_to(ROOT).as_posix(), 'pages': count,
                       'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUT/'showcase-manifest.json').write_text(json.dumps({'date': DATE, 'source_commit': '91f0d9ed2dd4956cb88227d0ff1929c1583bdf27',
        'kind': 'project showcase; not 1:1 production templates', 'files': result}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
