"""Normalize ImageGen restorations onto equal transparent canvases.

Artwork reconstruction is performed by the native ImageGen tool. This script
only crops transparent margins, uniformly resizes and centers the selected
images. The full native outputs and prompts are retained alongside the finals.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / 'artwork' / 'reference-collection'
OUT = ROOT / 'talisman-restored-v1'
CANVAS = 1024
EXTENT = 820
BOUND_ALPHA = 8
REVIEW_NOTES = {
    'rat': '保留右向奔跑、弯尾和肢体留白；曲线比低分辨率源图更规整。',
    'ox': '保留蓝色正面牛头、双角双耳；已去掉生成初稿新增的大鼻孔。',
    'tiger': '双虎和相对朝向保留；部分黑白碎笔扩大成连续形体，条纹与小细节仍需精修。',
    'rabbit': '右向单兔、耳头和分段腿脚保留；小眼标记的大小仍是重建解释。',
    'dragon': '主要红色片段与环绕关系保留；尖端、内扇形与下方片段仍比源图夸张，多次生成后尚未精确匹配。',
    'snake': '保留左上头部、S形颈部和分开的盘绕笔画；色带更宽、曲线更规整。',
    'horse': '保留左向紫色六块主分段；面部紫块来自源图着色片段，大块未着色头颈内部透明。',
    'sheep': '2026-10-10 修正：恢复原有连续薄荷绿羊头、尖耳/鼻梁/颊侧及两道空心耳线；背线接回头后，中央躯干透明。环线、轮廓曲率与右腿内缝仍有重建差异。',
    'monkey': '坐姿、左侧卷尾及肢体空隙保留；卷尾和躯干笔画仍明显偏粗。',
    'rooster': '单鸡、右上头冠/左尾/右下身体/下方脚保留；部分红块扩大。',
    'dog': '右向站姿、四腿、卷尾及透明躯干保留；胸颈小片和线宽需对照。',
    'pig': '上耳带、左侧鼻口片、右侧弧及下方弧保持参考相对位置，未做整体镜像；描线与填色更规整。',
}
REFINE_IDS = {'dragon', 'tiger', 'monkey'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(alpha):
    return alpha.point(lambda value: 255 if value >= BOUND_ALPHA else 0).getbbox()


def normalize(item):
    ident = item['id']
    native_path = OUT / 'raw' / f'{ident}-native.png'
    prompt_path = OUT / 'raw' / f'{ident}-prompt.txt'
    if not native_path.is_file() or not prompt_path.is_file():
        raise FileNotFoundError(f'Missing selected native image or prompt: {ident}')
    original = Image.open(native_path)
    if original.mode != 'RGBA':
        raise ValueError(f'Native image has no RGBA transparency: {ident}')
    alpha = original.getchannel('A')
    if alpha.getextrema()[0] != 0:
        raise ValueError(f'Native image lacks fully transparent pixels: {ident}')
    core = bounds(alpha)
    if not core:
        raise ValueError(f'Empty native image: {ident}')
    # Only very faint alpha (<8/255) outside this padded bounding rectangle is
    # excluded. Interior alpha, disconnected pieces and antialiasing are kept.
    crop_box = (max(0, core[0]-2), max(0, core[1]-2),
                min(original.width, core[2]+2), min(original.height, core[3]+2))
    crop = original.crop(crop_box)
    scale = EXTENT / max(crop.size)
    resized_size = tuple(max(1, round(value * scale)) for value in crop.size)
    resized = crop.resize(resized_size, Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
    offset = tuple((CANVAS-value)//2 for value in resized_size)
    canvas.alpha_composite(resized, offset)
    output = OUT / f'{ident}-restored.png'
    canvas.save(output)
    final_alpha = canvas.getchannel('A')
    final_bounds = bounds(final_alpha)
    full_bounds = final_alpha.getbbox()
    assert canvas.mode == 'RGBA' and canvas.size == (CANVAS, CANVAS)
    assert final_alpha.getextrema() == (0, 255)
    assert all(final_alpha.getpixel(point) == 0 for point in
               ((0, 0), (0, CANVAS-1), (CANVAS-1, 0), (CANVAS-1, CANVAS-1)))
    assert full_bounds[0] >= 100 and full_bounds[1] >= 100
    assert full_bounds[2] <= 924 and full_bounds[3] <= 924
    width, height = final_bounds[2]-final_bounds[0], final_bounds[3]-final_bounds[1]
    assert abs(max(width, height)-EXTENT) <= 8
    assert abs((final_bounds[0]+final_bounds[2])/2-CANVAS/2) <= 3
    assert abs((final_bounds[1]+final_bounds[3])/2-CANVAS/2) <= 3
    source_path = ROOT / item['path']
    assert sha(source_path) == item['sha256'], f'Source bytes changed: {ident}'
    record = {
        'id': ident, 'animal_en': item['animal_en'], 'animal_zh': item['animal_zh'],
        'path': output.relative_to(ROOT).as_posix(),
        'source_path': item['path'], 'source_page': item['file_page'],
        'source_sha256': item['sha256'],
        'native_path': native_path.relative_to(ROOT).as_posix(),
        'native_sha256': sha(native_path), 'native_dimensions': list(original.size),
        'prompt_path': prompt_path.relative_to(ROOT).as_posix(),
        'prompt_sha256': sha(prompt_path),
        'output_sha256': sha(output), 'dimensions': [CANVAS, CANVAS],
        'bytes': output.stat().st_size, 'visible_bounds_xyxy': list(final_bounds),
        'visual_status': 'needs_refinement' if ident in REFINE_IDS else 'reviewed_draft',
        'visual_note': REVIEW_NOTES[ident],
        'alpha_nonzero_bounds_xyxy': list(full_bounds),
        'normalization': {'native_core_bounds_alpha_ge_8': list(core),
                          'crop_bounds_xyxy': list(crop_box),
                          'uniform_scale': scale, 'resized_dimensions': list(resized_size),
                          'placement_xy': list(offset)},
    }
    revision_path = OUT / 'raw' / f'{ident}-revision.json'
    if revision_path.is_file():
        revision = json.loads(revision_path.read_text(encoding='utf-8'))
        for step in revision['steps']:
            for key in ('inputs', 'output', 'prompt'):
                paths = step[key] if isinstance(step[key], list) else [step[key]]
                for path in paths:
                    assert (ROOT / path).is_file(), f'Missing revision provenance: {path}'
        record['revision_path'] = revision_path.relative_to(ROOT).as_posix()
        record['revision_sha256'] = sha(revision_path)
        record['revision_label'] = revision['label']
    return record


def contact_sheet(items):
    cell_w, cell_h = 400, 440
    sheet = Image.new('RGB', (cell_w*4, cell_h*3), '#18202b')
    draw = ImageDraw.Draw(sheet)
    font_path = Path('C:/Windows/Fonts/msyh.ttc')
    font = ImageFont.truetype(str(font_path), 24) if font_path.is_file() else ImageFont.load_default()
    small = ImageFont.truetype(str(font_path), 16) if font_path.is_file() else ImageFont.load_default()
    for index, item in enumerate(items):
        x, y = index % 4*cell_w, index//4*cell_h
        tile = Image.new('RGBA', (cell_w-20, cell_w-20), '#eceef2')
        checker = ImageDraw.Draw(tile)
        for cy in range(0, tile.height, 20):
            for cx in range(0, tile.width, 20):
                if (cx//20+cy//20) % 2:
                    checker.rectangle((cx, cy, cx+19, cy+19), fill='#d9dde5')
        motif = Image.open(ROOT / item['path']).convert('RGBA')
        motif = motif.resize(tile.size, Image.Resampling.LANCZOS)
        tile.alpha_composite(motif)
        sheet.paste(tile.convert('RGB'), (x+10, y+10))
        draw.text((x+16, y+394), f"{item['animal_zh']} · {item['animal_en']}", fill='#f0f3f8', font=font)
    sheet.save(OUT / 'restored-contact-sheet.jpg', quality=93)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='*', help='Normalize a subset without rebuilding the set manifest')
    args = parser.parse_args()
    source = json.loads((ROOT / 'source-talisman/source_manifest.json').read_text(encoding='utf-8-sig'))
    selected = [item for item in source['files'] if not args.ids or item['id'] in args.ids]
    if args.ids and len(selected) != len(set(args.ids)):
        raise ValueError('Unknown animal id')
    records = [normalize(item) for item in selected]
    if args.ids:
        print(json.dumps({'normalized': [item['id'] for item in records]}, ensure_ascii=False))
        return
    assert len(records) == 12
    stamp = datetime.now(timezone.utc).isoformat()
    report = {
        'generated_utc': stamp, 'title': '十二符咒 · 修复正视透明 PNG · v1',
        'tool': 'Native ImageGen; separate reference-guided restoration for each animal',
        'method': 'Reconstruct original motif, rectify the talisman face plane; preserve animal pose. Pillow performs transparent-margin crop, uniform resize and canvas placement only.',
        'limitations': 'Reference-based restoration from 200×141 originals, not an exact recovery of lost pixels or authoritative animation production art. No change to PCB or manufacturing geometry.',
        'canvas_px': [CANVAS, CANVAS], 'target_longest_extent_px': EXTENT,
        'alpha_bbox_threshold': BOUND_ALPHA, 'files': records,
        'visual_release_status': 'Reference-guided restoration drafts; Dragon, Tiger and Monkey need finer fidelity work. Not approved as exact final reproductions.',
    }
    (OUT / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    prompts = {item['id']: (ROOT/item['prompt_path']).read_text(encoding='utf-8-sig') for item in records}
    (OUT / 'prompts.json').write_text(json.dumps(prompts, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    validation = {
        'generated_utc': stamp, 'passed': True, 'files_checked': len(records),
        'checks': ['All twelve unique animal ids', 'Original-source hashes unchanged',
                   'RGBA PNG, 1024×1024, true alpha transparency',
                   'Transparent corners and at least 100 px margins',
                   'Uniform scaling only, 820 px longest content extent within 8 px',
                   'Centered content bounding boxes within 3 px',
                   'Selected native outputs and exact prompts archived'],
        'scope': 'File/layout checks only. Visual fidelity remains draft; details in visual-review.md and per-image manifest notes.',
        'visual_final_approval': False,
        'needs_refinement': sorted(REFINE_IDS),
    }
    (OUT / 'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    contact_sheet(records)
    # A compact download contains the twelve finals and their review metadata;
    # full native outputs remain in the complete reference-collection archive.
    final_zip = ROOT.parent / 'talisman-restored-v1.zip'
    zip_files = [OUT/f"{item['id']}-restored.png" for item in records]
    zip_files += [OUT/name for name in ('README.md', 'manifest.json', 'prompts.json',
                                       'validation.json', 'visual-review.md', 'restored-contact-sheet.jpg')]
    with zipfile.ZipFile(final_zip, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in zip_files:
            bundle.write(path, path.relative_to(OUT).as_posix())
    with zipfile.ZipFile(final_zip) as bundle:
        assert bundle.testzip() is None
        assert set(bundle.namelist()) == {p.relative_to(OUT).as_posix() for p in zip_files}
        for path in zip_files:
            assert bundle.read(path.relative_to(OUT).as_posix()) == path.read_bytes()
    print(json.dumps({'normalized': len(records), 'manifest': str(OUT/'manifest.json'),
                      'final_zip': str(final_zip), 'zip_matches_disk': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
