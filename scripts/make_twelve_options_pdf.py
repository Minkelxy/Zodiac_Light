"""Create a five-page source-backed catalogue of the four five-cover PCBs."""
from pathlib import Path
import hashlib
import importlib.util
import json
from reportlab.pdfgen import canvas
import make_showcase_pdfs as s

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'hardware/nfc-talisman/variants/twelve-options'
OUTPUT=ROOT/'output/pdf/十二星座与生肖_拼板展示.pdf'
CN={'constellations-a':'星座 A','constellations-b':'星座 B','zodiac-a':'生肖 A','zodiac-b':'生肖 B'}
GROUPS={
 'constellations-a':'白羊座、金牛座、双子座、巨蟹座、处女座',
 'constellations-b':'天秤座、天蝎座、摩羯座、水瓶座、双鱼座',
 'zodiac-a':'鼠、牛、虎、兔、龙',
 'zodiac-b':'羊、猴、鸡、狗、猪',
}


def verified_inputs():
 """Refuse to label a new preview with checks belonging to an older export."""
 design_path=SOURCE/'design-manifest.json';export_path=SOURCE/'export-manifest.json'
 d=json.loads(design_path.read_text(encoding='utf-8'))
 m=json.loads(export_path.read_text(encoding='utf-8'))
 if m.get('design_manifest_sha256')!=hashlib.sha256(design_path.read_bytes()).hexdigest():
  raise ValueError('Design changed after native export; refresh and validate the native delivery before creating the PDF')
 if len(d.get('panels',[]))!=4 or {p['key'] for p in d['panels']}!=set(CN):
  raise ValueError('Expected the four reviewed cover panels')
 native=(ROOT/'hardware/nfc-talisman'/m['native_project']['path']).resolve()
 if not native.is_relative_to((SOURCE/'eda/native').resolve()):
  raise ValueError('Current showcase requires the shared nine-PCB archive in twelve-options/eda/native')
 sources=[design_path,export_path,Path(__file__).resolve(),SOURCE/'README.md',
          native,
          ROOT/'hardware/nfc-talisman/scripts/pcb_cover_border.py',
          ROOT/'hardware/nfc-talisman/scripts/audit_cover_borders.py',
          SOURCE/'border-artwork-audit.json',
          ROOT/'hardware/nfc-talisman/variants/standard-green-white/export-manifest.json',
          ROOT/'hardware/nfc-talisman/variants/standard-green-white/artwork/manifest.json']
 for name in d['files']:
  path=(SOURCE/name).resolve()
  if not path.is_relative_to(SOURCE.resolve()):
   raise ValueError('Declared design source leaves the twelve-options directory')
  sources.append(path)
 for panel in d['panels']:
  for field in ('preview','geometry'):
   path=(SOURCE/panel[field]).resolve()
   if not path.is_relative_to(SOURCE.resolve()):
    raise ValueError('Showcase source leaves the twelve-options directory')
   record=d['files'][panel[field]];raw=path.read_bytes()
   if len(raw)!=record['size'] or hashlib.sha256(raw).hexdigest()!=record['sha256']:
    raise ValueError('Preview or geometry differs from the exported design: '+panel[field])
   sources.append(path)
  if panel['key'].startswith('zodiac'):
   geometry=json.loads((SOURCE/panel['geometry']).read_text(encoding='utf-8'))
   for cover in geometry['covers']:
    for field in ('source_png','source_candidate_png','source_original_reference','source_manifest'):
     path=(ROOT/cover['details'][field]).resolve()
     if not path.is_relative_to(ROOT.resolve()):
      raise ValueError('Talisman source leaves the project')
     sources.append(path)
 sources.extend([SOURCE/'sources/slot-optimization.json',SOURCE/'slot-layout-geometry-audit.json'])
 spec=importlib.util.spec_from_file_location('showcase_twelve_delivery',ROOT/'hardware/nfc-talisman/scripts/check_twelve_options.py')
 checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
 report=checker.validate(ROOT)
 if report['status']!='passed':
  raise ValueError('Native/source/Gerber checks must pass before creating the PDF: '+str(report['errors']))
 snapshot={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
 return d,m,snapshot


def main():
 d,m,snapshot=verified_inputs()
 s.DATE='2026.10.20';s.register_fonts();c=canvas.Canvas(str(OUTPUT),pagesize=(s.W,s.H),pageCompression=1)
 c.setTitle('十二星座与十二生肖 - 四块五片 100 mm 绿白 PCB 拼板')
 c.setAuthor('Zodiac Light Project')
 s.header(c,'十二星座 · 十二生肖','绿色阻焊、白色丝印；动物与星图加入纹理边框和内外分界线',1,5,collection='NFC 盖板系列')
 for i,p in enumerate(d['panels']):
  x=36+(i%2)*183;y=71+(1-i//2)*190
  s.image(c,SOURCE/p['preview'],x,y,174,174)
  s.text(c,CN[p['key']],x,y+179,10,'#147442',True)
 s.text(c,'12 星座 / 12 生肖',430,433,24,'#17442D',True)
 s.lines(c,'新增 4 块 100 × 100 mm PCB，\n每块包含 5 个不同的盖板。',430,396,365,15,'#17442D',24)
 s.lines(c,'原有星座：射手座、狮子座。\n原有生肖：马、蛇。\n六块绿白 PCB 同步边缘纹理与分界线。',430,310,360,12,leading=22)
 s.box(c,430,119,370,99,'#EEF4EF',8)
 s.lines(c,'盖板共用现有 NFC 核心设计。\n四块新 PCB 均已保存重开，DRC 为 0。\n效果图为几何预览，未制造或完成实物验收。',444,192,341,11,leading=22)
 s.text(c,'图示为展示比例，不是 1:1 加工或下单文件。',430,89,9,s.MUTED)
 c.showPage()
 for i,p in enumerate(d['panels'],2):
  s.header(c,CN[p['key']]+' · 五款盖板','100 × 100 mm 拼板 | 单片 37 mm AF | 绿色阻焊 + 白色丝印',i,5,collection='NFC 盖板系列')
  s.image(c,SOURCE/p['preview'],36,63,420,420)
  s.text(c,'本板包含',482,444,17,'#17442D',True)
  s.lines(c,GROUPS[p['key']],482,412,313,16,'#17442D',leading=30)
  s.box(c,482,209,320,111,'#EEF4EF',8)
  mechanical_note='连接桥、邮票孔与光槽保留。' if p['key'].startswith('constellations') else '连接桥与邮票孔保留。'
  s.lines(c,'白色纹理边框与内外分界线。\n'+mechanical_note+'\n无彩色喷印，无装饰铜。',496,294,288,11,leading=23)
  note='星点为 0.8 mm 非金属孔。开槽按孔槽间实材和连通要求优化，其余连线保留为白丝印；孔位调整与加工数据见各款几何记录。' if p['key'].startswith('constellations') else '生肖沿用项目归档符咒图，按源图透明轮廓转换为白色丝印；原图与处理参数可追溯，动物图案不做去绿油开窗。'
  s.lines(c,note,482,176,313,10.6,leading=19)
  if p['key'].startswith('constellations'):
   report=json.loads((SOURCE/'sources/slot-optimization.json').read_text(encoding='utf-8'))
   before=sum(report['covers'][name]['before']['slotted_edge_count'] for name in p['covers'])
   after=sum(report['covers'][name]['after']['slotted_edge_count'] for name in p['covers'])
   old_slots=sum(report['covers'][name]['before']['physical_slot_count'] for name in p['covers'])
   new_slots=sum(report['covers'][name]['after']['physical_slot_count'] for name in p['covers'])
   s.text(c,f'本板开槽连线：{before} → {after}；实体槽：{old_slots} → {new_slots}。',482,105,9,s.MUTED)
  else:
   s.text(c,'沿用项目原有符咒，保留姿态、方向和留白。',482,105,9,s.MUTED)
  s.text(c,'已保存重开 · DRC 0 · CAM / 首件待确认',482,80,9,'#785829')
  c.showPage()
 for name,expected in snapshot.items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
   raise ValueError('Showcase source changed during generation: '+name)
 c.save()
 out={'pdf':OUTPUT.relative_to(ROOT).as_posix(),'pages':5,'pdf_sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
  'sources':snapshot,
  'status':'design showcase; passive covers; manufacturing HOLD',
  'credits':'Constellation line patterns: Stellarium Modern, CC BY-SA 4.0; positions: ESA Hipparcos I/239. Zodiac art: existing project talisman-single-ink-v1 images traced into white silkscreen; see per-cover source metadata and README.'}
 (OUTPUT.parent/'twelve-options-showcase-manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'pdf':out['pdf'],'pages':5},ensure_ascii=False))


if __name__=='__main__':main()
