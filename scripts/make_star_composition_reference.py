"""Create exact project geometry references for engraving art direction."""
from pathlib import Path
import sys, json
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from constellation_lamp.model import compile_layout,read_json
OUT=ROOT/'output'/'engraving-review-v2'
OUT.mkdir(parents=True,exist_ok=True)
r=compile_layout(*(read_json(ROOT/'data'/n) for n in ['catalog.json','constellation.json','layout.json']))
SIZE=1600
M=40
SC=(SIZE-2*M)/400
def xy(p): return (M+p[0]*SC,M+p[1]*SC)
for labeled in [False,True]:
 im=Image.new('RGB',(SIZE,SIZE),'#101521')
 d=ImageDraw.Draw(im)
 d.rectangle((M,M,SIZE-M,SIZE-M),outline='#485367',width=2)
 for e in r.edges:
  a=(next(s for s in r.stars if s.id==e.start_id).x_mm,next(s for s in r.stars if s.id==e.start_id).y_mm)
  b=(next(s for s in r.stars if s.id==e.end_id).x_mm,next(s for s in r.stars if s.id==e.end_id).y_mm)
  d.line([xy(a),xy(b)],fill='#b99855',width=4)
 font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',23)
 for s in r.stars:
  x,y=xy((s.x_mm,s.y_mm))
  d.ellipse((x-8,y-8,x+8,y+8),fill='#ffe3a0')
  if labeled:
   d.text((x+10,y+9),str(s.hip),font=font,fill='#e1e6f0')
 im.save(OUT/('star-map-labeled.png' if labeled else 'star-map-exact.png'))
print(OUT)
