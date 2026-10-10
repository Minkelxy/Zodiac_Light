"""Verify rear color-object registration, native embedded PNG and draft outputs."""
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile
from PIL import Image
from shapely.geometry import LineString, Point
from audit_manufacturing_draft import read_native_objects

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / 'artwork/sagittarius-color-print-candidate.png'
NATIVE = ROOT / 'eda/native/nfc-talisman-current.epro2'
PANEL = ROOT / 'eda/native/panel-source.jsonl'
ZIP = ROOT / 'manufacturing/draft/nfc-talisman-panel-draft.zip'
geometry = json.loads((ROOT / 'geometry/design.json').read_text(encoding='utf-8'))
board = next(b for b in geometry['boards'] if b['id'] == 'sagittarius5')
objects = [(m, d) for m, d in read_native_objects(PANEL) if m.get('type') == 'OBJ'
           and d.get('fileName') == PNG.name]
assert len(objects) == 1, 'Expected one registered rear-face PNG object'
meta, obj = objects[0]
expected = {'startX': 61, 'startY': 42, 'width': 37, 'height': 37}
registration = {key: abs(obj[key]*.0254-value) <= .000003 for key, value in expected.items()}
registration.update(layer=obj['layerId'] == 3, no_rotation=obj['angle'] == 0, no_mirror=obj['mirror'] is False)
reference = obj['path'].removeprefix('blob:')
embedded = None
with zipfile.ZipFile(NATIVE) as z:
    assert z.testzip() is None
    content = z.read(next(n for n in z.namelist() if n.endswith('.epru'))).decode('utf-8')
    for line in content.splitlines():
        if '||' not in line:
            continue
        left, right = line.split('||', 1)
        try:
            m, d = json.loads(left), json.loads(right.rstrip('|'))
        except ValueError:
            continue
        if m.get('type') == 'BLOB' and m.get('id') == reference:
            encoded = d.get('content', d.get('data', ''))
            assert encoded.startswith('data:image/png;base64,')
            embedded = base64.b64decode(encoded.split(',', 1)[1], validate=True)
            break
raw = PNG.read_bytes()
assert embedded == raw, 'Native project must embed exact local color PNG'
image = Image.open(io.BytesIO(embedded)).convert('RGBA')
assert image.size == (3700, 3700)
pixels = image.load()
transparent_checks = []
for star in geometry['constellation']['stars_local']:
    cx, cy = star['center']
    points = [(cx, cy), (cx+.4, cy), (cx-.4, cy), (cx, cy+.4), (cx, cy-.4)]
    transparent_checks += [pixels[round((x+18.5)*100), round((y+18.5)*100)][3] == 0 for x, y in points]
for edge in geometry['constellation']['edges']:
    a, b = edge['endpoint_a'], edge['endpoint_b']
    for fraction in (0, .25, .5, .75, 1):
        x, y = [a[i]+fraction*(b[i]-a[i]) for i in (0, 1)]
        transparent_checks.append(pixels[round((x+18.5)*100),round((y+18.5)*100)][3] == 0)
with zipfile.ZipFile(ZIP) as z:
    assert z.testzip() is None
    names = ['Fabrication_ColorfulTopSilkscreen.FCTS', 'Fabrication_ColorfulBottomSilkscreen.FCBS',
             'Fabrication_ColorfulBoardOutlineLayer.FCBO', 'Fabrication_ColorfulBoardOutlineMark.FCBM']
    files = [{'name': name, 'bytes':len(z.read(name)), 'sha256':hashlib.sha256(z.read(name)).hexdigest()}
             for name in names]
checks = {'registered_37mm_object':all(registration.values()), 'native_png_matches_local_bytes':embedded == raw,
          'all_8_star_and_11_slot_sampling_points_transparent':all(transparent_checks),
          'four_color_export_files_present_nonempty':all(f['bytes'] > 0 for f in files)}
report = {'status':'color_draft_file_checks_pass' if all(checks.values()) else 'fail', 'checks':checks,
          'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (PNG, NATIVE, PANEL, ZIP)},
          'native_object_id':meta['id'], 'native_blob_reference':reference, 'registration':registration,
          'png_pixels':list(image.size), 'size_mm':[37,37], 'transparent_sample_count':len(transparent_checks),
          'aperture_alpha_design_clearance_mm':.2, 'color_export_files':files,
          'limitations':['The proprietary binary color fabrication files were checked for presence and integrity; their pixel content/alpha and compositing order have not been decoded or visually approved.',
                         'Existing vector silk overlaps the color PNG linework. Confirm final light-line color and image/vector stacking in the official fabrication preview.',
                         'Printing tolerance, color, optical transmission and RF performance require CAM/sample acceptance.']}
target = ROOT / 'manufacturing/draft/star-color-audit.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'checks':checks,'color_files':files,'native_png_bytes':len(embedded),'transparent_samples':len(transparent_checks)}))
if not all(checks.values()):
    raise SystemExit(1)
