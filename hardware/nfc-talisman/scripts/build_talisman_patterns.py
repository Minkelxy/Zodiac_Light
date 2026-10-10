"""Extract the twelve animal motifs with reviewed source-pixel alpha masks.

No resampling, tracing, colour replacement, or generative image editing is used.
The archived masks are row runs on each original 200 x 141 pixel canvas.
"""
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1] / 'artwork' / 'reference-collection'
PATTERNS = ROOT / 'talisman-patterns'
MASKS = PATTERNS / 'pixel-masks.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def sources():
    items = json.loads((ROOT / 'source-talisman/source_manifest.json').read_text(encoding='utf-8-sig'))['files']
    assert len(items) == 12 and len({item['id'] for item in items}) == 12
    for item in items:
        path = ROOT / item['path']
        if sha(path) != item['sha256']:
            raise ValueError('Source bytes changed: ' + item['id'])
    return items


def freeze_reviewed_masks(items):
    """Archive binary masks from visually reviewed, original-size candidates."""
    records = []
    for item in items:
        source = Image.open(ROOT / item['path']).convert('RGBA')
        target = Image.open(PATTERNS / (item['id'] + '-pattern.png')).convert('RGBA')
        if source.size != target.size:
            raise ValueError('Canvas changed: ' + item['id'])
        src, dst = source.load(), target.load()
        runs = []
        for y in range(source.height):
            start = None
            for x in range(source.width + 1):
                selected = x < source.width and dst[x, y][3] > 0
                if selected:
                    if dst[x, y] != src[x, y]:
                        raise ValueError(f'Visible source pixel changed: {item["id"]} ({x},{y})')
                    if start is None:
                        start = x
                elif start is not None:
                    runs.append([y, start, x])
                    start = None
        if not runs:
            raise ValueError('Empty mask: ' + item['id'])
        records.append({'id': item['id'], 'source_path': item['path'],
                        'source_sha256': item['sha256'], 'dimensions': list(source.size),
                        'runs': runs})
    write_json(MASKS, {'schema_version': 1,
                      'encoding': '[y, x_start_inclusive, x_end_exclusive]',
                      'method': 'Manually reviewed original-pixel selection; binary alpha mask only.',
                      'files': records})


def mask_for(item, record, size):
    if record['source_sha256'] != item['sha256'] or tuple(record['dimensions']) != size:
        raise ValueError('Mask/source mismatch: ' + item['id'])
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    previous = None
    for y, start, end in record['runs']:
        if not (0 <= y < size[1] and 0 <= start < end <= size[0]):
            raise ValueError('Mask run out of bounds: ' + item['id'])
        if previous is not None and (y, start) < (previous[0], previous[2]):
            raise ValueError('Mask runs overlap or are unsorted: ' + item['id'])
        draw.line((start, y, end - 1, y), fill=255)
        previous = (y, start, end)
    return mask


def extract_and_validate(items, build):
    data = json.loads(MASKS.read_text(encoding='utf-8-sig'))
    masks = {entry['id']: entry for entry in data['files']}
    if set(masks) != {entry['id'] for entry in items}:
        raise ValueError('The archive must contain exactly twelve masks')
    manifest, checks = [], []
    for item in items:
        source_path = ROOT / item['path']
        source = Image.open(source_path).convert('RGBA')
        mask = mask_for(item, masks[item['id']], source.size)
        # RGB stays unchanged on the entire canvas, including invisible pixels.
        alpha = Image.new('L', source.size, 0)
        alpha.paste(source.getchannel('A'), (0, 0), mask)
        expected = source.copy()
        expected.putalpha(alpha)
        relative = 'talisman-patterns/' + item['id'] + '-pattern.png'
        path = ROOT / relative
        if build:
            expected.save(path, optimize=True)
        actual = Image.open(path).convert('RGBA')
        if actual.size != source.size or actual.tobytes() != expected.tobytes():
            raise ValueError('Output does not match the archived source-pixel mask: ' + item['id'])
        visible = sum(value > 0 for value in alpha.get_flattened_data())
        original_visible = sum(value > 0 for value in source.getchannel('A').get_flattened_data())
        strong_colour = [(s, a) for s, a in zip(source.get_flattened_data(), alpha.get_flattened_data())
                         if s[3] > 0 and max(s[:3]) - min(s[:3]) >= 40]
        lost_colour = sum(a == 0 for _, a in strong_colour)
        if lost_colour:
            raise ValueError(f'Animal pigment pixels were removed: {item["id"]} ({lost_colour})')
        bounds = alpha.getbbox()
        if not bounds or visible >= original_visible:
            raise ValueError('No background removed: ' + item['id'])
        if not (0 < bounds[0] < bounds[2] < source.width and 0 < bounds[1] < bounds[3] < source.height):
            raise ValueError('Motif touches the canvas edge: ' + item['id'])
        manifest.append({'id': item['id'], 'animal_en': item['animal_en'],
                         'animal_zh': item['animal_zh'], 'path': relative,
                         'source_path': item['path'], 'source_sha256': item['sha256'],
                         'source_page': item['file_page'], 'output_sha256': sha(path),
                         'dimensions': list(source.size), 'bytes': path.stat().st_size,
                         'visible_pixels': visible, 'visible_bounds_xyxy': list(bounds),
                         'method': 'Original source RGB with reviewed binary alpha mask',
                         'mask_file': 'talisman-patterns/pixel-masks.json'})
        checks.append({'id': item['id'], 'source_hash_matches': True,
                       'canvas_unchanged': True, 'all_rgb_pixels_unchanged': True,
                       'alpha_matches_source_or_zero': True, 'matches_archived_mask': True,
                       'strong_chromatic_source_pixels': len(strong_colour),
                       'strong_chromatic_pixels_removed': lost_colour,
                       'visible_pixels': visible, 'removed_visible_pixels': original_visible - visible,
                       'visible_bounds_xyxy': list(bounds)})
    if build:
        write_json(PATTERNS / 'manifest.json', {
            'generated_utc': datetime.now(timezone.utc).isoformat(),
            'title': '十二符咒独立动物图案 · 原像素透明 PNG',
            'method': 'Deterministic source-pixel alpha masking; no redraw, resampling, or mirroring.',
            'limitations': '200×141 source canvas with original perspective. These are raster references, not orthographic manufacturing vectors. Antialiased source edge pixels retain their original colour.',
            'files': manifest})
        write_json(PATTERNS / 'validation.json', {
            'status': 'pass', 'count': len(checks),
            'scope': 'Source hash, canvas, full RGB equality, source-or-zero alpha, mask equality, bounds, and preservation of every opaque source pixel with RGB channel spread >= 40. This pigment check does not assess gray/white motifs; visual completeness is reviewed separately in README.md.',
            'files': checks})
    return manifest


def review_sheet(items, target):
    """Enlarged nearest-neighbour comparisons for inspection, not final assets."""
    scale, margin = 3, 12
    width, height = 200 * scale, 141 * scale
    sheet = Image.new('RGB', (2 * width + 3 * margin, len(items) * (height + 28 + margin)), '#26303b')
    draw = ImageDraw.Draw(sheet)
    for i, item in enumerate(items):
        y = i * (height + 28 + margin)
        draw.text((margin, y + 4), item['animal_en'] + ' / original', fill='white')
        draw.text((width + 2 * margin, y + 4), 'source-pixel transparent pattern', fill='white')
        for col, path in enumerate((ROOT / item['path'], PATTERNS / (item['id'] + '-pattern.png'))):
            checker = Image.new('RGB', (width, height), '#f0f0f0')
            grid = ImageDraw.Draw(checker)
            for cy in range(0, height, 18):
                for cx in range(0, width, 18):
                    if (cx // 18 + cy // 18) % 2:
                        grid.rectangle((cx, cy, cx + 17, cy + 17), fill='#d1d1d1')
            image = Image.open(path).convert('RGBA').resize((width, height), Image.Resampling.NEAREST)
            checker.paste(image, (0, 0), image)
            sheet.paste(checker, (margin + col * (width + margin), y + 28))
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-reviewed-masks', action='store_true', help='Archive alpha selections after reviewing candidate PNGs')
    parser.add_argument('--check', action='store_true', help='Verify existing files without writing them')
    parser.add_argument('--review-sheet', type=Path, help='Write a temporary enlarged original/pattern comparison')
    args = parser.parse_args()
    items = sources()
    if args.freeze_reviewed_masks:
        if args.check:
            parser.error('--check cannot modify the mask archive')
        freeze_reviewed_masks(items)
    results = extract_and_validate(items, build=not args.check)
    if args.review_sheet:
        review_sheet(items, args.review_sheet)
    print(json.dumps({'count': len(results), 'checks': 'pass', 'manifest': str(PATTERNS / 'manifest.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
