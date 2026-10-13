"""Exact fixed graph plus an anatomically coherent bow/action guide."""
from pathlib import Path
import sys
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from constellation_lamp.model import compile_layout,read_json
out=ROOT/'output'/'engraving-review-v4';out.mkdir(parents=True,exist_ok=True)
r=compile_layout(*(read_json(ROOT/'data'/n) for n in ['catalog.json','constellation.json','layout.json']))
im=Image.open(ROOT/'output/engraving-review-v2/star-map-exact.png').convert('RGB')
d=ImageDraw.Draw(im)
def xy(p):return(40+p[0]*3.8,40+p[1]*3.8)
s={a.id:(a.x_mm,a.y_mm) for a in r.stars}
nock=s['hip_92041'];grip=s['hip_93683'];tip=s['hip_95168']
axis=(tip[0]-nock[0],tip[1]-nock[1])
arrow=(nock[0]+axis[0]*1.15,nock[1]+axis[1]*1.15)
bow=[(166,25),(147,51),grip,(147,122),(157,157),(173,196)]
cyan='#82dcdf'
d.line([xy(p) for p in bow],fill=cyan,width=8)
d.line([xy(bow[0]),xy(nock),xy(bow[-1])],fill=cyan,width=5)
d.line([xy(arrow),xy(nock)],fill=cyan,width=5)
for p in [nock,grip]:
 x,y=xy(p);d.ellipse((x-14,y-14,x+14,y+14),outline=cyan,width=3)
f=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25)
d.text((xy(nock)[0]+15,xy(nock)[1]+18),'DRAW HAND + NOCK + STRING',fill=cyan,font=f)
d.text((xy(grip)[0]-185,xy(grip)[1]+22),'BOW GRIP',fill=cyan,font=f)
im.save(out/'action-reference.png')
print(out/'action-reference.png')
