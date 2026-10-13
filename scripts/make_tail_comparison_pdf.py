"""R1 tail alternatives with the original constellation drawn as vectors."""
from pathlib import Path
import sys,hashlib,json
from reportlab.pdfgen import canvas
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import make_engraving_v4_pdf as shared
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4,landscape
OUT=ROOT/'output/pdf/星座灯_R1_马尾优化对比.pdf'
ART=ROOT/'output/engraving-review-v5-tail'
OLD=shared.ART
W,H=landscape(A4)
NAMES=[('R1','原 R1 尾形'),('T1','单束垂尾'),('T2','双束飘尾'),('T3','窄尾与星芒')]
def text(c,x,y,s,size=9,gray=.1):shared.text(c,x,y,s,size,gray)
def configure(id):
 shared.ART=OLD if id=='R1' else ART
 shared.frames.clear()
def main():
 c=canvas.Canvas(str(OUT),pagesize=(W,H));c.setTitle('星座灯 R1 - 马尾三种优化方案');c.setViewerPreference('PrintScaling','None')
 text(c,10,12,'R1 马尾优化 / 原稿与尾形对比',15)
 text(c,10,20,'保留选定的 R1 造型，比较尾根连接、毛束收细和末端星链关系。',9,.3)
 notes=[['宽尾根与封闭折板末梢。','作为修改前的参照。'],
        ['单束逐渐收细，轮廓更轻。','末梢取消宽大的封闭尖角。'],
        ['较早分为长短两束。','不在最低处形成硬质叉口。'],
        ['白色尾形收尖，星链继续延伸。','以开放的星芒表现尾迹。']]
 for i,(id,name) in enumerate(NAMES):
  configure(id)
  x=10+i*69.5;text(c,x,32,f'{id}  {name}',10)
  shared.board(c,id,x,38,65)
  for j,s in enumerate(notes[i]):text(c,x,118+j*8,s,8.4,.2)
  text(c,x,146,'固定原星图：21 星 / 24 线',8,.35)
 text(c,10,181,'新方案削弱折板感，强调尾巴从臀部向下生长、随风分束与渐细。',9,.2)
 text(c,10,199,'构图审查缩略图。白线定稿后整理为直线刻画稿与 1:1 A4 拼接模板。',8,.4)
 text(c,278,205,'1/3',7.5,.4);c.showPage()
 shared.W,shared.H=A4
 c.setPageSize(A4)
 text(c,10,12,'R1 马尾优化 / 尾部放大对比',15)
 text(c,10,20,'金色星点与连线均按项目保存坐标绘制。',9,.3)
 for i,(id,name) in enumerate(NAMES):
  configure(id)
  x=10+(i%2)*100;y=32+(i//2)*130
  text(c,x,y,f'{id}  {name}',10)
  shared.region(c,id,x,y+6,90,108,(15,150,235,400))
 text(c,10,290,'尾根、毛束与原星图末梢的关系。',8,.4)
 text(c,190,290,'2/3',7.5,.4);c.showPage()
 shared.W,shared.H=landscape(A4)
 c.setPageSize(landscape(A4))
 text(c,10,12,'T4 / 短尾与星轨',15)
 text(c,10,20,'马尾按自然比例收短，下方固定星链作为跃起后的光迹。',9,.3)
 configure('T4')
 shared.board(c,'T4',10,31,145)
 text(c,170,37,'更自然的尾形比例',11)
 text(c,170,46,'保留 R1 的棱角与主体动作。',9,.2)
 text(c,170,55,'尾根窄接，毛束向左下收尖。',9,.2)
 text(c,170,64,'下方星链开放延伸，形成尾迹。',9,.2)
 shared.region(c,'T4',170,75,112,112,(15,150,235,400))
 text(c,10,199,'金色仍为原有 21 星 / 24 连线；构图审查图，后续整理成直线刻画稿。',8,.4)
 text(c,278,205,'3/3',7.5,.4);c.showPage();c.save()
 manifest={'pdf':str(OUT),'base':'R1','scope':'tail alternatives only',
           'layout_sha256':hashlib.sha256((ROOT/'data/layout.json').read_bytes()).hexdigest(),
           'stars_per_variant':21,'edges_per_variant':24,
           'status':'art review; exact vector carving geometry follows selection'}
 (ART/'review-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(OUT)
if __name__=='__main__':main()
