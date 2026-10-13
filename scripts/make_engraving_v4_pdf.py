"""Review art with the authoritative constellation applied as native PDF vectors."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from constellation_lamp.model import compile_layout,read_json
ART=ROOT/'output/engraving-review-v4'
OUT=ROOT/'output/pdf/星座灯_E动作_优化对比_v4.pdf'
W,H=landscape(A4)
NAMES=[('R1','平衡切面'),('R2','流动留白'),('R3','星网留白')]
pdfmetrics.registerFont(TTFont('CN4','C:/Windows/Fonts/simhei.ttf'))
runtime=compile_layout(*(read_json(ROOT/'data'/n) for n in ['catalog.json','constellation.json','layout.json']))
STARS={s.id:(s.x_mm,s.y_mm) for s in runtime.stars}
frames={}
def frame(id):
 if id in frames:return frames[id]
 a=np.asarray(Image.open(ART/f'{id}-white.png').convert('RGB')).astype(int)
 n=int(a.shape[1]*.07)
 mask=(a[:,:,0]>70)&(abs(a[:,:,0]-a[:,:,1])<35)&(abs(a[:,:,1]-a[:,:,2])<40)
 sx,sy=mask.sum(axis=0),mask.sum(axis=1)
 h,w=a.shape[:2]
 f=[int(sx[:n].argmax()),int(sy[:n].argmax()),int(w-n+sx[-n:].argmax()),int(h-n+sy[-n:].argmax())]
 frames[id]=(f,w,h)
 return frames[id]
def text(c,x,y,s,size=10,gray=.05):
 c.setFont('CN4',size);c.setFillGray(gray);c.drawString(x*mm,H-y*mm,s)
def board(c,id,x,y,size,gold=True):
 (l,t,r,b),iw,ih=frame(id)
 sx,sy=size*mm/(r-l),size*mm/(b-t)
 c.saveState()
 p=c.beginPath();p.rect(x*mm,H-(y+size)*mm,size*mm,size*mm);c.clipPath(p,stroke=0,fill=0)
 c.drawImage(str(ART/f'{id}-white.png'),x*mm-l*sx,H-y*mm+t*sy-ih*sy,width=iw*sx,height=ih*sy,mask='auto')
 if gold:
  c.setStrokeColor(HexColor('#DCB86B'));c.setFillColor(HexColor('#FFE1A1'))
  c.setLineWidth(.5*size/400*mm)
  def xy(p):return((x+p[0]*size/400)*mm,H-(y+p[1]*size/400)*mm)
  for e in runtime.edges:
   c.line(*xy(STARS[e.start_id]),*xy(STARS[e.end_id]))
  for s in runtime.stars:
   c.circle(*xy((s.x_mm,s.y_mm)),1.8*size/400*mm,stroke=0,fill=1)
 c.restoreState()
 c.setStrokeGray(.5);c.setLineWidth(.15*mm)
 c.rect(x*mm,H-(y+size)*mm,size*mm,size*mm,stroke=1,fill=0)
def region(c,id,x,y,w,h,bounds):
 left,top,right,bottom=bounds
 scale=min(w/(right-left),h/(bottom-top))
 c.saveState();p=c.beginPath();p.rect(x*mm,H-(y+h)*mm,w*mm,h*mm);c.clipPath(p,stroke=0,fill=0)
 c.setFillColor(HexColor('#101521'));c.rect(x*mm,H-(y+h)*mm,w*mm,h*mm,fill=1,stroke=0)
 ox=x+(w-(right-left)*scale)/2-left*scale
 oy=y+(h-(bottom-top)*scale)/2-top*scale
 board(c,id,ox,oy,400*scale)
 c.restoreState()
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True)
 c=canvas.Canvas(str(OUT),pagesize=(W,H));c.setTitle('星座灯 E动作优化 - 三版与固定星网对比');c.setViewerPreference('PrintScaling','None')
 text(c,10,12,'E 动作优化 / 三版整体对比',15)
 text(c,10,19,'金色星网直接使用项目毫米坐标；白色为艺术刻线结构。',8.8,.3)
 desc=[['大切面与宽阔留白，结构感更强。','头部无五官，发冠仅保留大块面。'],
       ['带状边界有宽窄变化，动势舒展。','马腹留白，减少与星线竞争的内线。'],
       ['人物轮廓更轻，内部结构更克制。','让胸肩、马背和长尾的星网更醒目。']]
 for i,(id,name) in enumerate(NAMES):
  x=10+i*94;text(c,x,29,f'{id}  {name}',11)
  board(c,id,x,34,87)
  for j,s in enumerate(desc[i]):text(c,x,133+j*8,s,8.8,.2)
  text(c,x,158,'原图：21 星 / 24 连线 / 400×400 mm',8.3,.35)
 text(c,10,184,'本轮重点：统一弓弦与箭尾汇聚，简化手与弓梢，协调白线和固定星网。',9,.2)
 text(c,10,199,'构图审查缩略图。白线选定后整理为纯直线矢量稿与 1:1 A4 拼接模板。',8,.4)
 text(c,278,205,'1/2',7.5,.4);c.showPage()
 text(c,10,12,'E 动作优化 / 头部与握弓局部',15)
 text(c,10,19,'比较头部留白、手部简化及星线与刻线的关系。',8.8,.3)
 for i,(id,name) in enumerate(NAMES):
  x=10+i*94;text(c,x,29,f'{id}  {name}',11)
  region(c,id,x,34,87,71,(185,22,295,134))
  text(c,x,115,'头部与拉弦手',8.5,.2)
  region(c,id,x,121,87,70,(72,45,172,137))
  text(c,x,199,'握弓、箭杆与左上星链',8.5,.2)
 text(c,278,205,'2/2',7.5,.4);c.showPage();c.save()
 manifest={'pdf':str(OUT),'stars':21,'edges':24,'board_mm':[400,400],
           'layout_sha256':hashlib.sha256((ROOT/'data/layout.json').read_bytes()).hexdigest(),
           'art_registration_frames':{k:frame(k)[0] for k,_ in NAMES},
           'graph_layer':'native PDF vectors from saved JSON, identical coordinates in every variant',
           'art_status':'bitmap art for review; exact straight vector fabrication paths pending selection'}
 (ART/'registration-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(OUT)
if __name__=='__main__':main()
