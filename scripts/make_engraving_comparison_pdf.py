"""Two A4 landscape review plates: complete composition and head closeups."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'output'/'engraving-review-v3'
OUT=ROOT/'output'/'pdf'/'星座灯_E动作_划线方案对比.pdf'
W,H=landscape(A4)
pdfmetrics.registerFont(TTFont('CN','C:/Windows/Fonts/simhei.ttf'))
NAMES=[('E1','清爽侧脸 · 束发'),('E2','简洁头盔 · 冠羽'),
       ('E3','纯侧脸轮廓 · 发带'),('E4','几何侧脸 · 大块分发'),
       ('E5','大切面 · 星骨射手'),('E6','带状留白 · 流线射手')]

def text(c,x,y,value,size=10,color=.1):
 c.setFont('CN',size)
 c.setFillGray(color)
 c.drawString(x*mm,H-y*mm,value)

def main():
 OUT.parent.mkdir(parents=True,exist_ok=True)
 c=canvas.Canvas(str(OUT),pagesize=(W,H))
 c.setTitle('星座灯 E动作 - 六版划线艺术方案对比')
 c.setViewerPreference('PrintScaling','None')
 for page in range(2):
  text(c,10,12,'E 动作 / 六版划线风格对比' if page==0 else 'E 动作 / 面部与头发局部对比',15)
  text(c,10,19,'保留回首拉弓与长尾构图，比较写实程度、头部复杂度与刻线节奏。',8.5,.3)
  for i,(id,title) in enumerate(NAMES):
   col,row=i%3,i//3
   x,y=10+col*94,25+row*86
   text(c,x,y+3,f'{id}  {title}',9)
   boxx,boxy,bw,bh=x,y+7,87,77
   path=ART/f'{id}.png'
   if page==0:
    side=77
    c.drawImage(str(path),(boxx+5)*mm,H-(boxy+side)*mm,
                width=side*mm,height=side*mm,mask='auto')
   else:
    # Crop by PDF clipping and positioning; original raster files remain intact.
    iw,ih=Image.open(path).size
    left,top,right,bottom=.54*iw,.04*ih,.82*iw,.31*ih
    sx=bw*mm/(right-left)
    sy=bh*mm/(bottom-top)
    scale=min(sx,sy)
    clip=c.beginPath()
    clip.rect(boxx*mm,H-(boxy+bh)*mm,bw*mm,bh*mm)
    c.saveState()
    c.clipPath(clip,stroke=0,fill=0)
    dx=boxx*mm+(bw*mm-(right-left)*scale)/2-left*scale
    dy=H-boxy*mm-(bh*mm-(bottom-top)*scale)/2+top*scale-ih*scale
    c.drawImage(str(path),dx,dy,width=iw*scale,height=ih*scale,mask='auto')
    c.restoreState()
  text(c,10,205,'缩略审查图。定稿后按原星图坐标制作直线刻画稿与 1:1 A4 拼接模板。',7.7,.35)
  text(c,278,205,f'{page+1}/2',7.7,.35)
  c.showPage()
 c.save()
 print(OUT)

if __name__=='__main__':main()
