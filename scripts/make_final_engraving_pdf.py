"""Final T4 engraving: edited straight centreline geometry and 1:1 A4 tiles."""
from __future__ import annotations
import hashlib
import json
import math
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from constellation_lamp.model import compile_layout, read_json
from make_a4_placement_pdf import text, line, rect, ruler, small_map, polygon, segment_distance

OUT = ROOT / 'output/pdf'
PDF = OUT / '星座灯_R1短尾星轨_400mm_A4刻线模板.pdf'
ART = ROOT / 'output/engraving-review-v5-tail/T4-white.png'
GEOM = ROOT / 'output/engraving-final'
PW, PH = A4
COLS = (0, 140, 280, 400)
ROWS = (0, 200, 400)
OVERLAP = 10
FRAME = (24, 23, 1229, 1230)
DESIGN_LABEL = 'R1 棱角风格 · T4 短尾与星轨 · 400 × 400 mm 亚克力'
PDF_TITLE = '射手座 R1短尾星轨 - 400×400 mm A4刻线模板'

# Centreline reconstruction from the approved T4. Deliberately removes tiny
# finger/ankle slivers; these are design paths, never outlines of bitmap strokes.
PATHS_PX = {
 'bow_upper_outer': [(319,234),(316,174),(330,145),(377,109),(424,68),(429,48),(426,32),(437,47),(436,61),(428,80),(351,158),(337,237)],
 'bow_upper_inner': [(337,237),(340,158)],
 'bow_width': [(318,207),(337,213)],
 'bow_lower': [(330,288),(299,333),(306,364),(363,486),(365,503),(350,527),(366,518),(374,495),(371,478),(338,392),(327,352),(330,288)],
 'bow_lower_facet': [(306,364),(326,308)],
 'bow_tip_facet': [(350,527),(366,487)],
 'bow_string': [(436,61),(750,349),(370,505)],
 'arrow_head': [(170,185),(227,188),(211,197),(218,212),(170,185)],
 'arrow_axis': [(211,197),(750,349)],
 'grip': [(319,234),(306,235),(302,247),(304,260),(303,279),(315,285),(330,288),(336,287),(354,294),(362,265),(345,239),(337,237),(319,234)],
 'grip_thumb': [(306,247),(317,244),(324,248),(333,247),(336,257)],
 'grip_fingers': [(304,267),(326,270)],
 'arm_upper': [(354,294),(379,304),(477,362),(526,371),(560,380),(604,401),(638,405),(674,398),(687,394)],
 'arm_top': [(354,267),(377,276),(447,297),(505,308),(546,329),(583,328),(666,343),(710,346),(750,349)],
 'arm_facet': [(505,308),(546,329),(583,328)],
 'face': [(747,214),(736,219),(733,239),(737,248),(731,270),(740,274),(746,300),(754,304),(784,298),(798,266)],
 'hair_front': [(734,219),(733,209),(737,199),(780,192),(807,183),(826,184),(874,222),(825,207),(753,211),(747,214),(734,219)],
 'hair_crown': [(807,183),(821,147),(833,115),(849,109),(879,110),(928,120),(953,149),(976,182),(1006,218.38947368421053)],
 'hair_crown_facet': [(833,115),(843,115),(870,125),(938,203)],
 'hair_rear': [(938,203),(1128,246),(1145,266),(1168,314),(1204,377),(1138,326),(1097,269),(1031,270),(938,203)],
 'hair_lower': [(778,216),(807,244),(862,263),(911,298),(938,307),(1008,333),(1065,370)],
 'hair_main_facet': [(874,222),(938,307),(1008,333)],
 'neck_front': [(784,298),(789,330),(775,337),(753,346)],
 'neck_back': [(842,262),(832,285),(843,334),(871,352)],
 'neck_facet': [(789,330),(787,316),(773,327),(753,343),(750,349)],
 'draw_arm': [(750,349),(752,366),(758,377),(769,383),(782,379),(803,378),(827,375),(870,382),(894,393),(941,418),(962,430),(993,440),(1037,444),(1070,430),(1101,417),(1065,370),(1010,365),(951,363),(880,353),(833,348),(799,332),(785,310)],
 'draw_thumb': [(758,355),(777,342),(799,348)],
 'draw_finger': [(769,383),(780,363),(798,363)],
 'draw_arm_facet': [(798,363),(828,367),(894,393)],
 'torso_front': [(870,382),(896,423),(883,454),(892,562),(909,554),(953,675)],
 'torso_left': [(674,398),(700,451),(736,484),(760,512),(748,548),(731,567),(696,580),(620,576),(536,554),(332,538)],
 'torso_left_facet': [(687,394),(718,419),(742,456),(760,512)],
 'torso_top_facet': [(718,419),(883,454)],
 'torso_diagonal': [(742,456),(892,562)],
 'torso_lower_facet': [(760,512),(825,603),(895,693),(921,729),(953,675)],
 'rump': [(332,538),(250,557),(160,640),(136,711)],
 'tail': [(136,711),(81,744),(112,740),(87,779),(94,803),(99,778),(98,818),(107,841),(116,795),(129,771),(201,749),(278,679),(297,587),(332,538)],
 'tail_main_facet': [(112,740),(165,698),(223,645),(250,595),(332,538)],
 'tail_inner': [(250,595),(202,718),(145,764)],
 'hind_leg_near': [(536,554),(362,637),(334,696),(346,748),(434,831),(416,863),(369,900),(379,920),(445,1006),(451,1037),(468,1053),(472,1078),(463,1100),(496,1122),(525,1125),(520,1078),(492,1018),(437,925),(439,894),(537,807),(572,718),(536,554)],
 'hind_leg_knee_facet': [(346,748),(419,644),(434,831),(439,894)],
 'hind_leg_ankle_facet': [(492,1018),(472,1078),(520,1078)],
 'hind_leg_far': [(572,718),(546,778),(540,810),(584,853),(596,884),(593,926),(647,953),(710,986),(725,1011),(747,1017),(752,1062),(787,1078),(820,1085),(804,1032),(788,1004),(754,967),(655,913),(644,901),(644,853),(651,821),(629,772)],
 'hind_far_facet': [(546,778),(629,772),(729,796),(797,788)],
 'hind_far_hoof': [(747,1017),(752,1030),(804,1032)],
 'body_lower': [(536,554),(658,627),(797,788),(822,816),(966,854)],
 'body_facet': [(658,627),(742,557)],
 'body_front_facet': [(731,567),(825,603)],
 'front_leg_down': [(848,635),(895,693),(889,750),(904,762),(914,767),(1009,841),(1019,861),(1046,979),(1023,1040),(987,1101),(958,1025),(981,1012),(997,1002),(993,980),(1007,951),(998,915),(983,875),(966,854),(822,816),(797,788),(848,635)],
 'front_down_hoof': [(981,1012),(1046,979),(1023,1040),(981,1012)],
 'front_down_facet': [(797,788),(1009,841)],
 'front_leg_up': [(953,675),(997,689),(1073,682),(1100,706),(1105,731),(1140,799),(1159,836),(1151,886),(1133,946),(1109,921),(1095,895),(1092,881),(1117,863),(1110,845),(1117,816),(1089,768),(1068,734),(1037,734),(981,758),(927,771),(914,768),(905,761),(921,729),(953,675)],
 'front_up_facet': [(953,675),(997,702),(1073,682)],
 'front_up_facet2': [(914,768),(997,702)],
 'front_up_hoof': [(1092,881),(1159,836)],
}

def to_mm(p):
    l,t,r,b = FRAME
    return ((p[0]-l)*400/(r-l), (p[1]-t)*400/(b-t))

def geometry():
    paths = {name:[to_mm(p) for p in path] for name,path in PATHS_PX.items()}
    segments, seen = [], set()
    for name,path in paths.items():
        for a,b in zip(path,path[1:]):
            key = tuple(sorted((tuple(a),tuple(b))))
            if key not in seen:
                seen.add(key)
                segments.append((a,b))
    assert all(0<x<400 and 0<y<400 for path in paths.values() for x,y in path)
    return paths,segments

def board(c, runtime, segments, origin, scale=1):
    ox,oy = origin
    c.saveState()
    c.translate(ox*mm, PH-oy*mm)
    c.scale(mm*scale, -mm*scale)
    c.setLineJoin(1)
    c.setLineCap(1)
    stars={s.id:(s.x_mm,s.y_mm) for s in runtime.stars}
    # Exact saved constellation, and actual PCB extents, are reference only.
    c.setStrokeGray(.80)
    c.setLineWidth(.16)
    c.setDash([1,1])
    for e in runtime.edges:
        c.line(*stars[e.start_id], *stars[e.end_id])
    c.setDash()
    c.setStrokeGray(.70)
    c.setLineWidth(.16)
    for piece in runtime.pieces:
        corners=polygon(piece,runtime.layout['strip_width_mm'])
        p=c.beginPath();p.moveTo(*corners[0])
        for q in corners[1:]:p.lineTo(*q)
        p.close();c.drawPath(p,stroke=1,fill=0)
    c.setFillGray(.70)
    for s in runtime.stars:
        c.circle(s.x_mm,s.y_mm,.75,stroke=0,fill=1)
    c.setStrokeGray(0)
    c.setLineWidth(.22)
    for a,b in segments:c.line(*a,*b)
    c.restoreState()

def registration(runtime, segments):
    def clearance(x,y):
        return min(segment_distance(x,y,a,b) for a,b in segments)
    marks=[]
    for seam,x in enumerate((145,285),1):
        for row,(lo,hi) in enumerate(((20,185),(225,385)),1):
            for suffix,start,end in (('a',lo,lo+40),('b',hi-40,hi)):
                y=max(range(start,end+1),key=lambda y:clearance(x,y))
                marks.append((x,y,f'V{seam}{row}{suffix}'))
    for col,(lo,hi) in enumerate(((20,120),(160,260),(300,380)),1):
        for suffix,start,end in (('a',lo,lo+20),('b',hi-20,hi)):
            x=max(range(start,end+1),key=lambda x:clearance(x,205))
            marks.append((x,205,f'H{col}{suffix}'))
    return marks

def guide(c,runtime,segments):
    text(c,15,20,'射手座 / 400 mm 刻线拼接模板',18)
    text(c,15,29,DESIGN_LABEL,10)
    line(c,15,34,195,34,width=.4)
    text(c,15,45,'打印：只需第 2-7 页，共六张 A4',12)
    text(c,15,54,'A4 纵向、单面、实际大小 / 100%；关闭适合页面与多页合一。',9)
    text(c,15,63,'先试印第 2 页，横、纵两把校准尺都应量得 100 mm，再打印其余页。',9)
    text(c,15,78,'拼接与定位',12)
    small_map(c,15,86,cell=20)
    for y,s in [(92,'按左图排列：上排 A1-A3，下排 B1-B3。'),
                (101,'沿外框实线裁纸，保留右侧 / 下侧 10 mm 搭接带。'),
                (110,'右页盖住左页搭接带，下排盖住上排搭接带。'),
                (119,'同编号十字重合、线条连续后，用胶带固定。')]:
        text(c,82,y,s,8.5)
    text(c,15,136,'拼好后量外框为 400 × 400 mm；放在透明亚克力下方，纸张上边对齐板上边。',8.5)
    board(c,runtime,segments,(15,147),.30)
    rect(c,15,147,120,120,width=.2)
    text(c,145,154,'线条说明',11)
    line(c,145,162,185,162,width=.22)
    text(c,145,170,'黑线：沿线轻划。',9)
    text(c,145,177,'只有直线与折线，',8.5)
    text(c,145,184,'不需刻画填色区域。',8.5)
    line(c,145,194,185,194,gray=.70,width=.2)
    text(c,145,203,'浅灰：星图 / 灯条参考。',9)
    text(c,145,210,'用来核对布局，不划线。',8.5)
    text(c,145,225,'方向',11)
    text(c,145,234,'从当前划线面看本图，',8.5)
    text(c,145,241,'箭指向左上；无镜像。',8.5)
    text(c,145,248,'先检查板面方向与',8.5)
    text(c,145,255,'星图位置，再开始划线。',8.5)
    text(c,15,280,'总览为缩小示意；第 2-7 页是 1:1 刻线模板。',8,gray=.3)
    text(c,195,287,'1 / 7',7,align='right')
    c.showPage()

def tile(c,runtime,segments,marks,row,col):
    name=f"{'AB'[row]}{col+1}"
    page=2+row*3+col
    x0,x1=COLS[col:col+2];y0,y1=ROWS[row:row+2]
    w,h=x1-x0,y1-y0
    fw=w+(OVERLAP if col<2 else 0)
    fh=h+(OVERLAP if row==0 else 0)
    left,top=35,40
    text(c,15,18,f'{name} / 射手座刻线模板',15)
    text(c,15,26,'A4 纵向 · 100% 实际大小 · 从划线面看 · 上边 ↑',8.5)
    tabs=[]
    if col<2:tabs.append('右侧 10 mm')
    if row==0:tabs.append('下侧 10 mm')
    tab_note='、'.join(tabs)+' 搭接带' if tabs else '本页无新增搭接带'
    text(c,15,33,f'板坐标 X {x0}-{x1} / Y {y0}-{y1} mm；{tab_note}。',8)
    small_map(c,175,12,selected=name,cell=7)
    c.saveState()
    p=c.beginPath();p.rect(left*mm,PH-(top+fh)*mm,fw*mm,fh*mm)
    c.clipPath(p,stroke=0,fill=0)
    board(c,runtime,segments,(left-x0,top-y0))
    for x,y,key in marks:
        if x0<=x<=x0+fw and y0<=y<=y0+fh:
            px,py=left+x-x0,top+y-y0
            line(c,px-1.4,py,px+1.4,py,gray=.35,width=.16)
            line(c,px,py-1.4,px,py+1.4,gray=.35,width=.16)
            text(c,px,py-2.3,key,5.5,gray=.35,align='center',font='Helvetica')
    text(c,left+5,top+7,name,9,gray=.5,font='Helvetica-Bold')
    c.restoreState()
    rect(c,left,top,fw,fh,width=.35)
    if col<2:
        line(c,left+w,top,left+w,top+fh,gray=.35,width=.18,dash=(2,1))
        # Labels stay in the exterior page footer, keeping artwork unobstructed.
    if row==0:
        line(c,left,top+h,left+fw,top+h,gray=.35,width=.18,dash=(2,1))
    for x in range(x0,x1+1,20):
        px=left+x-x0
        line(c,px,top-1.5,px,top,gray=.3,width=.15)
        text(c,px,top-2.5,x,6,gray=.3,align='center',font='Helvetica')
    for y in range(y0,y1+1,20):
        py=top+y-y0
        line(c,left-1.5,py,left,py,gray=.3,width=.15)
        text(c,left-2.5,py+.8,y,6,gray=.3,align='right',font='Helvetica')
    ruler(c,22,116,vertical=True)
    text(c,16,224,'纵向',7);text(c,13,229,'100 mm',7)
    text(c,35,258,'沿外框实线裁纸；虚线是搭接位置，右侧 / 下侧搭接带保留。',7.7)
    ruler(c,35,266)
    text(c,144,268,'横向 100 mm',8)
    text(c,35,278,'黑线 = 刻线；浅灰 = 星图与灯条位置参考，不划线。',8)
    text(c,35,285,'两把校准尺均量得 100 mm，再拼接使用。',8)
    text(c,195,287,f'{page} / 7',7,align='right')
    c.showPage()

def svg(runtime,segments):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="400mm" height="400mm" viewBox="0 0 400 400">',
         '<rect width="400" height="400" fill="white"/>',
         '<g id="engraving" fill="none" stroke="black" stroke-width="0.22" stroke-linecap="round" stroke-linejoin="round">']
    for a,b in segments:
        out.append(f'<path d="M {a[0]:.6f},{a[1]:.6f} L {b[0]:.6f},{b[1]:.6f}"/>')
    out+=['</g></svg>']
    (GEOM/'engraving-master.svg').write_text('\n'.join(out),encoding='utf-8')

def main():
    pdfmetrics.registerFont(TTFont('JigChinese','C:/Windows/Fonts/simhei.ttf'))
    source_paths=[ROOT/'data'/n for n in ('catalog.json','constellation.json','layout.json')]
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    runtime=compile_layout(*(read_json(p) for p in source_paths))
    assert len(runtime.stars)==21 and len(runtime.edges)==24
    assert runtime.layout['panel']['width_mm']==runtime.layout['panel']['height_mm']==400
    paths,segments=geometry()
    marks=registration(runtime,segments)
    OUT.mkdir(parents=True,exist_ok=True);GEOM.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(PDF),pagesize=A4,pageCompression=1)
    c.setTitle(PDF_TITLE)
    c.setAuthor('Constellation Lamp Project')
    c.setSubject('Six A4 portrait tiles; 100% actual size; 10 mm overlap; black engraving, grey alignment guides')
    c.setViewerPreference('PrintScaling','None')
    guide(c,runtime,segments)
    for row in range(2):
        for col in range(3):tile(c,runtime,segments,marks,row,col)
    c.save()
    svg(runtime,segments)
    manifest={
        'pdf':str(PDF),'pages':7,'print_pages':[2,3,4,5,6,7],
        'page_mm':[210,297],'assembled_mm':[400,400],
        'columns_mm':COLS,'rows_mm':ROWS,'overlap_mm':OVERLAP,
        'view':'working face, x right, y down, not mirrored',
        'art_source':str(ART),'art_sha256':hashlib.sha256(ART.read_bytes()).hexdigest(),
        'registration_frame_px':FRAME,'geometry_method':'manually edited straight centreline paths; no bitmap stroke outlines',
        'paths_mm':paths,'segments_mm':segments,'segment_count':len(segments),
        'engraving_stroke_mm':.22,'reference_stars':len(runtime.stars),
        'reference_edges':len(runtime.edges),'reference_strip_pieces':len(runtime.pieces),
        'source_sha256':hashes,'registration_marks_mm':marks,
        'pdf_sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),
        'ruler_mm':100,'template_origin_on_page_mm':[35,40],
    }
    (GEOM/'fabrication-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[p.relative_to(ROOT).as_posix()] for p in source_paths)
    print(json.dumps({'pdf':str(PDF),'pages':7,'straight_segments':len(segments)},ensure_ascii=False))

if __name__=='__main__':main()
