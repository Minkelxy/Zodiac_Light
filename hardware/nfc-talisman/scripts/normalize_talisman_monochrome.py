"""Lay out native one-hue drafts and audit them; never recolor or redraw art.

Pillow only crops transparent margins, scales uniformly, centers canvases and
builds a labelled preview. Native RGB/alpha are preserved apart from resizing.
Strict palette checks are reported honestly, independently of layout checks.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1] / 'artwork' / 'reference-collection'
OUT = ROOT / 'talisman-monochrome-v1'
CANVAS, EXTENT, BOUND_ALPHA = 1024, 820, 8


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(alpha):
    return alpha.point(lambda value: 255 if value >= BOUND_ALPHA else 0).getbbox()


def palette_audit(image, ink_hex):
    expected = tuple(int(ink_hex[i:i+2], 16) for i in (1, 3, 5))
    pixels = image.get_flattened_data() if hasattr(image, 'get_flattened_data') else list(image.getdata())
    visible = Counter(pixel[:3] for pixel in pixels if pixel[3] > 0)
    alpha = image.getchannel('A')
    interior = alpha.point(lambda a: 255 if a >= 8 else 0).filter(ImageFilter.MinFilter(5))
    interior_colors = Counter()
    interior_count = interior_low_alpha = 0
    masks = interior.get_flattened_data() if hasattr(interior, 'get_flattened_data') else list(interior.getdata())
    for pixel, mask in zip(pixels, masks):
        if mask:
            interior_count += 1
            interior_colors[pixel[:3]] += 1
            interior_low_alpha += pixel[3] < 250
    return {
        'intended_ink_hex': ink_hex,
        'strict_all_nontransparent_rgb_equal_intended_ink': set(visible) == {expected},
        'distinct_visible_rgb_count': len(visible),
        'visible_pixel_count': sum(visible.values()),
        'exact_intended_rgb_pixel_count': visible[expected],
        'interior_eroded_5x5_pixel_count': interior_count,
        'interior_alpha_below_250_pixel_count': interior_low_alpha,
        'interior_rgb_top_5': [{'rgb': list(color), 'pixels': count}
                               for color, count in interior_colors.most_common(5)],
        'interpretation': 'Read-only analysis. RGB variation and interior alpha can include native rendering artifacts; visual review is separate. No palette quantization has been applied.',
    }


def normalize(spec, source):
    ident = spec['id']
    native_path, prompt_path = ROOT/spec['native'], ROOT/spec['prompt_path']
    generation_path = OUT/'raw'/f'{ident}-generation.json'
    for path in (native_path, prompt_path, generation_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    generation = read(generation_path)
    if 'prompt' in generation:
        assert prompt_path.read_text(encoding='utf-8-sig').strip() == generation['prompt'].strip(), f'Prompt provenance differs: {ident}'
    original = Image.open(native_path)
    assert original.mode == 'RGBA', f'Native must retain transparency: {ident}'
    assert original.getchannel('A').getextrema()[0] == 0
    core = bounds(original.getchannel('A'))
    assert core, f'Empty artwork: {ident}'
    crop_box = (max(0, core[0]-2), max(0, core[1]-2),
                min(original.width, core[2]+2), min(original.height, core[3]+2))
    crop = original.crop(crop_box)
    scale = EXTENT/max(crop.size)
    size = tuple(max(1, round(v*scale)) for v in crop.size)
    resized = crop.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
    offset = tuple((CANVAS-v)//2 for v in size)
    canvas.alpha_composite(resized, offset)
    path = OUT/f'{ident}-monochrome.png'
    canvas.save(path)
    alpha = canvas.getchannel('A')
    final = bounds(alpha)
    nonzero = alpha.getbbox()
    assert alpha.getextrema()[0] == 0 and alpha.getextrema()[1] >= 250
    assert all(alpha.getpixel(p) == 0 for p in ((0, 0), (0, 1023), (1023, 0), (1023, 1023)))
    assert nonzero[0] >= 100 and nonzero[1] >= 100 and nonzero[2] <= 924 and nonzero[3] <= 924
    assert abs(max(final[2]-final[0], final[3]-final[1])-EXTENT) <= 8
    assert abs((final[0]+final[2])/2-512) <= 3 and abs((final[1]+final[3])/2-512) <= 3
    assert sha(ROOT/source['path']) == source['sha256'], f'Source changed: {ident}'
    return {
        'id': ident, 'animal_zh': source['animal_zh'], 'animal_en': source['animal_en'],
        'ink_hex': spec['ink_hex'], 'path': path.relative_to(ROOT).as_posix(),
        'dimensions': [CANVAS, CANVAS], 'bytes': path.stat().st_size,
        'output_sha256': sha(path), 'source_path': source['path'],
        'source_sha256': source['sha256'], 'source_page': source['file_page'],
        'inputs': [{'path': name, 'sha256': sha(ROOT/name)} for name in spec['inputs']],
        'native_path': spec['native'], 'native_sha256': sha(native_path),
        'native_dimensions': list(original.size), 'prompt_path': spec['prompt_path'],
        'prompt_sha256': sha(prompt_path),
        'generation_path': generation_path.relative_to(ROOT).as_posix(),
        'generation_sha256': sha(generation_path),
        'visible_bounds_xyxy': list(final), 'alpha_nonzero_bounds_xyxy': list(nonzero),
        'normalization': {'crop_bounds_xyxy': list(crop_box), 'uniform_scale': scale,
                          'resized_dimensions': list(size), 'placement_xy': list(offset)},
        'palette_audit': palette_audit(canvas, spec['ink_hex']),
        'visual_status': 'native_draft_pending_review',
        'visual_note': generation.get('visual_note', generation.get('visual_notes', generation.get('observations', 'See native generation record and visual review.'))),
    }


def contact_sheet(records):
    sheet = Image.new('RGB', (1600, 1320), '#18202b')
    draw = ImageDraw.Draw(sheet)
    font_path = Path('C:/Windows/Fonts/msyh.ttc')
    font = ImageFont.truetype(str(font_path), 22) if font_path.is_file() else ImageFont.load_default()
    for index, record in enumerate(records):
        x, y = index % 4*400, index//4*440
        tile = Image.new('RGBA', (380, 380), '#eceef2')
        checker = ImageDraw.Draw(tile)
        for cy in range(0, 380, 20):
            for cx in range(0, 380, 20):
                if (cx//20+cy//20) % 2:
                    checker.rectangle((cx, cy, cx+19, cy+19), fill='#d9dde5')
        tile.alpha_composite(Image.open(ROOT/record['path']).resize(tile.size, Image.Resampling.LANCZOS))
        sheet.paste(tile.convert('RGB'), (x+10, y+10))
        draw.text((x+16, y+394), f"{record['animal_zh']} · {record['animal_en']}", font=font, fill='#f0f3f8')
    sheet.save(OUT/'monochrome-contact-sheet.jpg', quality=93)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-partial', action='store_true', help='Layout available candidates only, explicitly mark partial set')
    args = parser.parse_args()
    spec = read(OUT/'generation-spec.json')
    sources = {s['id']: s for s in read(ROOT/'source-talisman/source_manifest.json')['files']}
    selected = [s for s in spec['files'] if (ROOT/s['native']).is_file()]
    if args.allow_partial:
        selected = [s for s in selected if (ROOT/s['prompt_path']).is_file()
                    and (OUT/'raw'/f"{s['id']}-generation.json").is_file()]
    if not args.allow_partial:
        assert len(selected) == 12, f'Only {len(selected)}/12 native drafts exist'
    assert selected, 'No native drafts available'
    records = [normalize(s, sources[s['id']]) for s in selected]
    review_path = OUT/'visual-review.json'
    if review_path.is_file():
        reviews = {r['id']: r for r in read(review_path)['files']}
        for record in records:
            if record['id'] in reviews:
                record.update(visual_status=reviews[record['id']]['status'],
                              visual_note=reviews[record['id']]['note'])
    stamp = datetime.now(timezone.utc).isoformat()
    strict_pass = [r['id'] for r in records if r['palette_audit']['strict_all_nontransparent_rgb_equal_intended_ink']]
    manifest = {
        'title': '十二符咒 · 原生单色风格重绘候选 · v1', 'generated_utc': stamp,
        'tool': 'Native ImageGen', 'set_complete': len(records) == 12,
        'candidate_count': len(records), 'canvas_px': [CANVAS, CANVAS],
        'target_longest_extent_px': EXTENT, 'strict_single_ink_pass_count': len(strict_pass),
        'method': 'Native reference-guided redraw. Pillow only crops transparent margins, resizes uniformly, centers canvases and assembles a preview. No recoloring, alpha thresholding or geometry edits.',
        'visual_release_status': 'Candidates pending fidelity/palette review; not pixel-exact one-ink manufacturing artwork.',
        'files': records,
    }
    write(OUT/'manifest.json', manifest)
    write(OUT/'prompts.json', {r['id']: (ROOT/r['prompt_path']).read_text(encoding='utf-8-sig') for r in records})
    write(OUT/'validation.json', {
        'generated_utc': stamp, 'files_checked': len(records), 'set_complete': len(records) == 12,
        'file_layout_passed': True, 'source_hashes_unchanged': True,
        'scope': 'RGBA/transparency/dimensions/margins/uniform scaling/centering/provenance only. Visual fidelity and strict one-ink palette are separate.',
        'visual_final_approval': False, 'strict_single_ink_pass_ids': strict_pass,
        'strict_single_ink_pass_count': len(strict_pass),
    })
    contact_sheet(records)
    spec.update(title='十二符咒单色阴影重绘规范与原生候选', status='native_candidates_generated_review_pending',
                successful_native_generations=len(records), successful_monochrome_images=len(strict_pass),
                client_date='2026-10-11')
    write(OUT/'generation-spec.json', spec)
    status = read(OUT/'service-status.json')
    status.update(client_date='2026-10-11', status='native_service_recovered_candidates_in_review',
                  successful_monochrome_images=len(strict_pass), native_candidate_count=len(records),
                  layout_candidate_count=len(records), strict_single_ink_pass_count=len(strict_pass),
                  error_summary=None, previous_error_summary='2026-10-10: two HTTP 403 Forbidden attempts',
                  note='Native service recovered. Available one-hue candidates are laid out and audited; strict palette/fidelity are not approved. No Python recoloring or redraw fallback has been used.')
    final_manifest = ROOT/'talisman-single-ink-v1/manifest.json'
    if final_manifest.is_file():
        final_set = read(final_manifest)
        final_count = final_set.get('strict_single_ink_pass_count', 0)
        status.update(status='native_service_recovered_rgb_normalization_completed',
                      successful_monochrome_images=final_count,
                      strict_single_ink_candidate_pass_count=len(strict_pass),
                      strict_single_ink_final_count=final_count,
                      single_ink_manifest='talisman-single-ink-v1/manifest.json',
                      note='Twelve native one-hue candidates remain unchanged. The user approved RGB-only palette normalization on 2026-10-11; strict-color finals are saved separately with identical alpha. Visual fidelity remains draft; no programmatic redraw or alpha edits.')
    write(OUT/'service-status.json', status)
    zip_files = [ROOT/r['path'] for r in records]
    zip_files += [OUT/name for name in ('README.md', 'manifest.json', 'prompts.json', 'validation.json',
                                       'monochrome-contact-sheet.jpg') if (OUT/name).is_file()]
    for name in ('visual-review.md', 'visual-review.json'):
        if (OUT/name).is_file():
            zip_files.append(OUT/name)
    target = ROOT.parent/'talisman-monochrome-v1.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in zip_files:
            bundle.write(path, path.relative_to(OUT).as_posix())
    with zipfile.ZipFile(target) as bundle:
        assert bundle.testzip() is None
        assert set(bundle.namelist()) == {p.relative_to(OUT).as_posix() for p in zip_files}
        assert all(bundle.read(p.relative_to(OUT).as_posix()) == p.read_bytes() for p in zip_files)
    print(json.dumps({'candidates': len(records), 'file_layout_passed': True,
                      'strict_single_ink_pass_count': len(strict_pass), 'zip_matches_disk': True,
                      'zip_path': str(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
