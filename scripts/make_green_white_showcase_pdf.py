"""Create the ordinary green-mask/white-silk NFC showcase without changing older PDFs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import make_showcase_pdfs as style

OUT = ROOT / 'output/pdf'
PDF = OUT / 'NFC符咒_绿白普通工艺展示.pdf'
VARIANTS = ROOT / 'hardware/nfc-talisman/variants'
STANDARD = VARIANTS / 'standard-green-white'
W, H = landscape(A4)
INK = '#163D2D'
MUTED = '#5E756B'
GREEN = '#157344'
SOFT = '#F0F5F0'
DATE = '2026.10.20'
TOTAL = 3
USED = []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_inputs() -> dict[str, str]:
    """Use current artifact/native checks before displaying their DRC results."""
    manifest_path = STANDARD / 'export-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    artwork_path = STANDARD / 'artwork/manifest.json'
    artwork = json.loads(artwork_path.read_text(encoding='utf-8'))
    sources = [Path(__file__).resolve(), STANDARD / 'README.md', manifest_path, artwork_path,
               ROOT / 'hardware/nfc-talisman/scripts/pcb_cover_border.py',
               ROOT / 'hardware/nfc-talisman/scripts/audit_cover_borders.py',
               VARIANTS / 'twelve-options/border-artwork-audit.json',
               STANDARD / 'artwork/README.md',
               ROOT / 'hardware/nfc-talisman' / manifest['artwork_file'],
               *(VARIANTS / variant / 'artwork/cover-review-preview.png'
                 for variant in ('horse-sagittarius', 'snake-leo'))]
    native = ROOT / 'hardware/nfc-talisman' / manifest['native_project']['path']
    if not native.resolve().is_relative_to((VARIANTS / 'twelve-options/eda/native').resolve()):
        raise ValueError('Current green-white artwork requires the shared nine-PCB native archive')
    sources.append(native)
    for name, expected in artwork['files'].items():
        path = (STANDARD / 'artwork' / name).resolve()
        if not path.is_relative_to((STANDARD / 'artwork').resolve()):
            raise ValueError('Artwork source leaves the green-white artwork directory')
        raw = path.read_bytes()
        if len(raw) != expected['size'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('Green-white preview or geometry differs from the artwork manifest: ' + name)
        sources.append(path)
    spec = importlib.util.spec_from_file_location(
        'green_white_showcase_delivery', ROOT / 'hardware/nfc-talisman/scripts/check_standard_delivery.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    report = checker.validate(ROOT)
    if report['status'] != 'passed':
        raise ValueError('Current native/artwork/Gerber checks must pass before creating the PDF: ' + str(report['errors']))
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in sources}


def art(variant: str, face: str) -> Path:
    path = STANDARD / f'artwork/{variant}-{face}-standard-green-white-37mm.png'
    USED.append(path)
    return path


def picture(c, path: Path, x: float, y: float, w: float, h: float):
    USED.append(path)
    style.image(c, path, x, y, w, h)


def page(c, title: str, subtitle: str, number: int):
    style.header(c, title, subtitle, number, TOTAL, collection='NFC 普通工艺设计展示')
    style.text(c, '效果示意，非实物照片；不是制造放行文件。', 36, 48, 8, MUTED)


def front_page(c):
    page(c, '绿白普通工艺双款', '绿色阻焊作底色，白色丝印呈现动物、星图、纹理边框与内外分界线。', 1)
    for variant, title, x, details in [
        ('horse-sagittarius', '马 + 射手座', 36, '8 个星孔 / 11 条光槽'),
        ('snake-leo', '蛇 + 狮子座', 431, '9 个星孔 / 8 条光槽 / 2 条仅印刷短边'),
    ]:
        style.box(c, x, 209, 375, 264, SOFT, 10)
        style.text(c, title, x + 14, 447, 17, INK, True)
        style.text(c, '正面 / 动物', x + 14, 423, 9, MUTED)
        style.text(c, '背面 / 星座', x + 195, 423, 9, MUTED)
        picture(c, art(variant, 'front'), x + 13, 242, 169, 169)
        picture(c, art(variant, 'rear'), x + 195, 242, 169, 169)
        style.text(c, details, x + 14, 224, 10.5, INK)
    style.metric(c, '37 mm', '八角形对边尺寸', 48, 160)
    style.metric(c, '两款独立', '各自 100 × 100 mm 五片拼板', 260, 160)
    style.metric(c, '绿色 + 白色', '普通阻焊与丝印', 558, 160)
    style.lines(c, '原彩色版与核心板保留，两款绿白 PCB 同步边缘纹理框与内外分界线。\n新增边框使用白色丝印；原孔槽、铜、天线和电路沿用保护基线，边框不新增阻焊开窗。',
                48, 98, 735, 11, INK, leading=18)
    c.showPage()


def comparison_page(c):
    page(c, '原彩色与绿白，对照看变化', '保留动物轮廓与星图结构，采用不同的外观工艺。', 2)
    style.text(c, '原彩色版 / 独立保留', 52, 451, 16, INK, True)
    style.text(c, '新增绿白版 / 普通 PCB 工艺', 443, 451, 16, INK, True)
    for variant, title, y in [
        ('horse-sagittarius', '马 + 射手座', 278),
        ('snake-leo', '蛇 + 狮子座', 101),
    ]:
        style.box(c, 36, y, 770, 160, SOFT, 8)
        style.text(c, title, 50, y + 142, 11.5, INK, True)
        picture(c, VARIANTS / f'{variant}/artwork/cover-review-preview.png', 50, y + 14, 356, 119)
        picture(c, art(variant, 'front'), 454, y + 13, 125, 125)
        picture(c, art(variant, 'rear'), 636, y + 13, 125, 125)
    style.text(c, '白色纹理边框与分界线形成边缘层次；白环与印线避开孔槽开窗。实际颜色须看样件。',
               48, 78, 10, MUTED)
    c.showPage()


def process_page(c):
    page(c, '工艺与交付边界', '图案清楚，制造状态也清楚。', 3)
    rows = [
        ('绿色底色', '未开窗的绿色阻焊。阻焊层开窗表示去绿油，不是“涂绿色”。'),
        ('白色图案', '动物、星图、文字与纹理边框使用白色丝印；不用彩色喷印，不新增装饰铜。'),
        ('孔槽开窗', '沿原孔槽周围外扩名义 0.20 mm；丝印让开开窗名义 0.16 mm。'),
        ('预览棕色', '仅示意去绿油后露出的基材；不代表露铜，也不新增动物形状开窗。'),
    ]
    for i, (label, description) in enumerate(rows):
        y = 407 - i * 60
        style.box(c, 36, y, 770, 51, SOFT, 7)
        style.text(c, label, 51, y + 18, 14, INK, True)
        style.lines(c, description, 175, y + 20, 610, 11.2, INK, leading=16)
    style.box(c, 36, 93, 770, 105, '#FFF3DF', 8)
    style.text(c, '制造状态保持 HOLD', 51, 171, 15, '#785829', True)
    style.lines(c, '两款 PCB 已保存重开，DRC 均为 0；共用全 9 PCB 工程，普通 Gerber 与图案区域检查通过。\nC1 采购/适配、正式 CAM、RF/NFC 与实物光效待验收；细节与阻焊/丝印套准仍须 CAM 评审。',
                51, 146, 735, 11, '#785829', leading=18)
    style.text(c, 'HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING', 51, 105, 9, '#785829')
    style.text(c, '两块独立 PCB：Horse-Sagittarius-GreenWhite-100-v1 / Snake-Leo-GreenWhite-100-v1',
               48, 74, 8.5, MUTED)
    c.showPage()


def main():
    snapshot = verified_inputs()
    USED.clear()
    OUT.mkdir(parents=True, exist_ok=True)
    style.DATE = DATE
    style.INK = INK
    style.MUTED = MUTED
    style.register_fonts()
    c = canvas.Canvas(str(PDF), pagesize=(W, H), pageCompression=1)
    c.setTitle('NFC 符咒 - 绿色阻焊与白色丝印普通工艺展示')
    c.setAuthor('Zodiac Light Project')
    c.setSubject('2026-10-20 white textured borders; design preview only; manufacturing HOLD')
    front_page(c)
    comparison_page(c)
    process_page(c)
    for name, expected in snapshot.items():
        if sha256(ROOT / name) != expected:
            raise ValueError('Showcase source changed during generation: ' + name)
    c.save()
    evidence = [STANDARD / 'artwork/README.md', STANDARD / 'artwork/manifest.json',
                STANDARD / 'export-manifest.json',
                *(STANDARD / f'artwork/{variant}-standard-layer-artwork.json'
                  for variant in ('horse-sagittarius', 'snake-leo'))]
    manifest = {
        'created_date': '2026-10-20', 'pdf': PDF.relative_to(ROOT).as_posix(), 'pages': TOTAL,
        'purpose': 'design comparison and ordinary process explanation; not a physical sample',
        'manufacturing_release_status': 'HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING',
        'sources': {**snapshot, **{p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted(set(USED))}},
        'process_evidence': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in evidence},
        'pdf_sha256': hashlib.sha256(PDF.read_bytes()).hexdigest(),
    }
    (OUT / 'green-white-showcase-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'pdf': manifest['pdf'], 'pages': TOTAL}, ensure_ascii=False))


if __name__ == '__main__':
    main()
