"""Create a five-page source-backed catalogue of the four five-cover PCBs."""
from pathlib import Path
import hashlib
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


def main():
 d=json.loads((SOURCE/'design-manifest.json').read_text(encoding='utf-8'))
 m=json.loads((SOURCE/'export-manifest.json').read_text(encoding='utf-8'))
 assert len(d['panels'])==4 and all(b['drc']==[] for b in m['boards'])
 s.DATE='2026.10.15';s.register_fonts();c=canvas.Canvas(str(OUTPUT),pagesize=(s.W,s.H),pageCompression=1)
 c.setTitle('十二星座与十二生肖 - 四块五片 100 mm 绿白 PCB 拼板')
 c.setAuthor('Zodiac Light Project')
 s.header(c,'十二星座 · 十二生肖','原有两款 + 新增十款；绿色阻焊、白色丝印，沿用 37 mm 八边形盖板',1,5,collection='NFC 盖板系列')
 for i,p in enumerate(d['panels']):
  x=36+(i%2)*183;y=71+(1-i//2)*190
  s.image(c,SOURCE/p['preview'],x,y,174,174)
  s.text(c,CN[p['key']],x,y+179,10,'#147442',True)
 s.text(c,'12 星座 / 12 生肖',430,433,24,'#17442D',True)
 s.lines(c,'新增 4 块 100 × 100 mm PCB，\n每块包含 5 个不同的盖板。',430,396,365,15,'#17442D',24)
 s.lines(c,'原有星座：射手座、狮子座。\n原有生肖：马、蛇。\n新增十款分别覆盖其余选项。',430,310,360,12,leading=22)
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
  s.lines(c,'5 片独立盖板，可拆分取用。\n四向连接桥与邮票孔保留。\n无彩色喷印，无装饰铜。',496,294,288,11,leading=23)
  note='星点为 0.8 mm 非金属孔。长连线设透光槽，短连线用丝印保留；实际孔位为便于加工做过记录在案的微调。' if p['key'].startswith('constellations') else '生肖使用原创矢量线稿，白色部分由普通丝印形成；动物图案不做去绿油开窗。'
  s.lines(c,note,482,176,313,10.6,leading=19)
  s.text(c,'已保存重开 · DRC 0 · CAM / 首件待确认',482,80,9,'#785829')
  c.showPage()
 c.save()
 sources=[SOURCE/'design-manifest.json',SOURCE/'export-manifest.json',*[SOURCE/p['preview'] for p in d['panels']]]
 out={'pdf':OUTPUT.relative_to(ROOT).as_posix(),'pages':5,'pdf_sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
  'sources':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
  'status':'design showcase; passive covers; manufacturing HOLD',
  'credits':'Constellation line patterns: Stellarium Modern, CC BY-SA 4.0; positions: ESA Hipparcos I/239. See twelve-options/sources and README.'}
 (OUTPUT.parent/'twelve-options-showcase-manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'pdf':out['pdf'],'pages':5},ensure_ascii=False))


if __name__=='__main__':main()
