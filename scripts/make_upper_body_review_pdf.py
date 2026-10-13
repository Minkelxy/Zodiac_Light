"""Compare upper-body and hair revisions against the unchanged constellation."""
from pathlib import Path
import sys
import json
import hashlib
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import make_engraving_v4_pdf as shared

ART=ROOT/'output/engraving-review-v6-upper'
OLD=ROOT/'output/engraving-review-v5-tail'
OUT=ROOT/'output/pdf/星座灯_上半身与头发重构对比_v6.pdf'
W,H=landscape(A4)
NAMES=[('T4','上一轮'),('U1','紧凑后掠'),('U2','单束飘发'),('U4','低束发重构')]

def configure(id):
    shared.ART=OLD if id=='T4' else ART
    shared.frames.clear()

def text(c,x,y,s,size=9,gray=.1):
    shared.text(c,x,y,s,size,gray)

def main():
    shared.W,shared.H=W,H
    c=canvas.Canvas(str(OUT),pagesize=(W,H))
    c.setTitle('射手座 - 上半身与头发重构对比 U1 U2 U4')
    c.setViewerPreference('PrintScaling','None')
    text(c,10,12,'射手座 / 上半身与头发重构',15)
    text(c,10,20,'白色为造型审查；金色为原 21 星 / 24 条连线，按保存的毫米坐标叠加。',9,.3)
    notes=[['保留作比例、头发和肩胸参照。','原大切面、四腿与短尾为本轮基础。'],
           ['紧贴头骨的短发，减轻右上压迫感。','肩胸清楚，留白更完整。'],
           ['发根收紧，以单束发流延续动势。','重建颈肩与拉弓时的身体扭转。'],
           ['低束发与两束细发，头部更安静。','弓略收拢，重建肩胸与后扬肘部。']]
    for i,(id,name) in enumerate(NAMES):
        configure(id)
        x=10+i*69.5
        text(c,x,32,f'{id}  {name}',10)
        shared.board(c,id,x,38,65)
        for j,s in enumerate(notes[i]):text(c,x,118+j*8,s,8.1,.2)
    text(c,10,155,'本轮重点：发根与后脑相连、肩胸有扭转、双臂比例自然、刻线与星线互相配合。',9,.2)
    text(c,10,176,'图像仅用于造型审查；选择方向后，再整理直线母图和新的 1:1 A4 拼接模板。',8.5,.35)
    text(c,278,205,'1/2',7.5,.4)
    c.showPage()
    text(c,10,12,'上半身与头发 / 放大比较',15)
    text(c,10,20,'比较侧脸留白、发根连接、颈肩转折与拉弓的受力关系。',9,.3)
    for i,(id,name) in enumerate(NAMES[1:]):
        configure(id)
        x=10+i*94
        text(c,x,32,f'{id}  {name}',11)
        shared.region(c,id,x,39,87,100,(190,5,390,235))
        text(c,x,145,'发型与侧脸',8.5,.2)
        shared.region(c,id,x,150,87,42,(225,45,385,125))
    text(c,10,199,'侧脸保留少量外轮廓转折；最终矢量整理时去除指节碎线和近距离重复线。',8.5,.3)
    text(c,278,205,'2/2',7.5,.4)
    c.showPage()
    c.save()
    manifest={
        'pdf':OUT.relative_to(ROOT).as_posix(),
        'status':'upper body and hair art review; fabrication revision pending selection',
        'preserved_design':'R1 angular style, four horse legs and T4 short tail',
        'stars':21,'edges':24,'board_mm':[400,400],
        'layout_sha256':hashlib.sha256((ROOT/'data/layout.json').read_bytes()).hexdigest(),
        'art_registration_frames':{},
        'graph_layer':'native PDF vectors from the saved layout; same star and edge coordinates in every panel',
    }
    for id,_ in NAMES:
        configure(id)
        manifest['art_registration_frames'][id]=shared.frame(id)[0]
    (ART/'review-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(OUT)

if __name__=='__main__':main()
