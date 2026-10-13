"""Manufacturing centrelines for the selected U1 short-hair Sagittarius."""
from pathlib import Path
import hashlib
import json
import sys
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import make_final_engraving_pdf as jig

PDF=ROOT/'output/pdf/星座灯_U1短发_400mm_A4刻线模板.pdf'
ART=ROOT/'output/engraving-review-v6-upper/U1-white.png'
GEOM=ROOT/'output/engraving-final-u1'
FRAME=(24,22,1228,1229)

# Keep the already reviewed four-leg and short-tail structure, update its
# foreleg transition to the selected U1. Rebuild all human-body and hair paths.
LOWER_NAMES=(
    'rump','tail','tail_main_facet','tail_inner','hind_leg_near',
    'hind_leg_knee_facet','hind_leg_ankle_facet','hind_leg_far',
    'hind_far_facet','hind_far_hoof',
)
PATHS={k:list(jig.PATHS_PX[k]) for k in LOWER_NAMES}
for name,path in PATHS.items():
    PATHS[name]=[(538,554) if tuple(p)==(536,554) else
                 (778,784) if tuple(p)==(797,788) else tuple(p) for p in path]
PATHS.update({
 'bow_upper':[(319,234),(316,174),(330,145),(377,109),(424,68),(429,48),(426,32),(437,47),(436,61),(428,80),(351,158),(337,237)],
 'bow_upper_inner':[(337,237),(340,158)],
 'bow_width':[(318,207),(337,213)],
 'bow_lower':[(330,288),(301,336),(307,367),(363,486),(368,503),(350,527),(366,518),(374,495),(371,478),(338,392),(327,352),(330,288)],
 'bow_lower_facet':[(307,367),(326,308)],
 'bow_tip_facet':[(350,527),(366,487)],
 'bow_string':[(436,61),(722,341),(368,503)],
 'arrow_head':[(170,185),(227,188),(211,197),(218,212),(170,185)],
 'arrow_axis':[(211,197),(722,341)],
 'grip':[(319,234),(306,235),(302,247),(304,260),(303,279),(315,285),(330,288),(336,287),(354,294),(365,265),(345,239),(337,237),(319,234)],
 'grip_thumb':[(306,247),(320,244),(328,249),(335,247),(339,261)],
 'grip_finger':[(304,267),(328,270)],
 'bow_arm_top':[(365,265),(409,286),(497,311),(533,323),(555,334),(599,335),(625,343),(669,338),(722,341)],
 'bow_arm_lower':[(354,294),(398,309),(470,360),(534,375),(594,398),(652,407)],
 'bow_arm_plane':[(470,360),(555,334),(534,375)],
 'bow_arm_upper_plane':[(625,343),(672,377)],
 'face':[(738,219),(729,239),(733,253),(724,278),(733,282),(735,307),(742,313),(764,307),(778,303),(797,278),(813,263)],
 'hair_outline':[(727,215),(741,205),(767,202),(793,186),(813,185),(835,202),(866,214),(879,233),(911,240),(953,293),(893,273),(919,315),(871,297),(845,305),(829,299),(813,263)],
 'hair_front':[(727,215),(732,228),(738,219),(751,214),(775,225),(794,250),(813,263)],
 'hair_main_plane':[(741,205),(818,214),(859,244),(893,273)],
 'hair_lower_plane':[(813,263),(829,299),(845,305),(871,297)],
 'neck_front':[(764,307),(766,328),(750,331)],
 'neck_back':[(813,263),(825,298),(845,335),(884,359.80645161290323)],
 'draw_hand_arm':[(722,341),(726,335),(750,331),(760,331),(781,347),(805,356),(870,358),(901,362),(925,362),(959,382),(997,393),(1024,434),(965,456),(934,447),(906,438),(893,433),(865,411),(824,386),(794,378),(754,378),(732,376),(724,369),(722,359),(722,341)],
 'draw_thumb':[(726,347),(745,339),(758,339)],
 'draw_finger':[(725,359),(744,351),(760,355)],
 'draw_arm_plane':[(794,378),(805,356),(957,382),(1024,434)],
 'chest_plane':[(672,377),(693,411),(732,444),(840,471),(866,473),(893,433)],
 'chest_to_waist':[(794,378),(813,410),(840,471),(851,512),(860,568)],
 'torso_left':[(652,407),(681,465),(723,499),(746,527),(732,554),(722,567),(685,580),(620,578),(538,554),(332,538)],
 'torso_left_plane':[(693,411),(681,465)],
 'torso_center_plane':[(732,444),(746,527)],
 'torso_diagonal':[(732,444),(762,493),(860,568)],
 'torso_right':[(893,433),(880,456),(892,508),(876,553),(928,677)],
 'waist_plane':[(860,568),(876,553)],
 'body_lower':[(538,554),(658,627),(778,784),(822,817),(966,854)],
 'body_upper_plane':[(658,627),(722,567)],
 'body_front_plane':[(722,567),(817,616)],
 'body_front_axis':[(746,527),(817,616),(885,700)],
 'front_leg_down':[(817,616),(885,700),(882,751),(896,763),(920,770),(1009,843),(1019,861),(1046,980),(1023,1040),(987,1101),(958,1025),(981,1012),(997,1002),(993,980),(1007,951),(998,915),(983,875),(966,854),(822,817),(778,784),(817,616)],
 'front_down_hoof':[(981,1012),(1046,980),(1023,1040),(981,1012)],
 'front_down_plane':[(778,784),(1009,843)],
 'front_leg_up':[(928,677),(978,699),(1032,689),(1082,685),(1106,708),(1111,741),(1143,809),(1159,840),(1151,887),(1133,946),(1109,921),(1095,895),(1092,881),(1117,863),(1110,845),(1117,816),(1089,768),(1068,734),(1037,734),(981,758),(927,771),(896,763),(905,724),(928,677)],
 'front_up_plane':[(928,677),(977,706),(1082,685)],
 'front_up_plane2':[(896,763),(977,706)],
 'front_up_hoof':[(1092,881),(1159,840)],
})

def configure():
    jig.PDF=PDF
    jig.ART=ART
    jig.GEOM=GEOM
    jig.FRAME=FRAME
    jig.PATHS_PX=PATHS
    jig.DESIGN_LABEL='U1 紧凑短发 · R1 棱角与短尾 · 400 × 400 mm 亚克力'
    jig.PDF_TITLE='射手座 U1短发 - 400×400 mm A4刻线模板'

def poster(runtime,segments):
    """Native vector preview, never a modified raster of the concept art."""
    tmp=ROOT/'tmp/pdfs/u1-vector-preview.pdf'
    tmp.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(tmp),pagesize=(400*mm,400*mm))
    c.setFillColorRGB(16/255,21/255,33/255)
    c.rect(0,0,400*mm,400*mm,fill=1,stroke=0)
    c.translate(0,400*mm);c.scale(mm,-mm)
    c.setStrokeColorRGB(.94,.96,.98);c.setLineWidth(.35)
    c.setLineCap(1);c.setLineJoin(1)
    for a,b in segments:c.line(*a,*b)
    points={s.id:(s.x_mm,s.y_mm) for s in runtime.stars}
    c.setStrokeColorRGB(.86,.72,.42);c.setLineWidth(.38)
    for e in runtime.edges:c.line(*points[e.start_id],*points[e.end_id])
    c.setFillColorRGB(1,.89,.65)
    for s in runtime.stars:c.circle(s.x_mm,s.y_mm,1.6,fill=1,stroke=0)
    c.setStrokeColorRGB(.4,.45,.5);c.setLineWidth(.22)
    c.rect(0,0,400,400,fill=0,stroke=1)
    c.showPage();c.save()

def main():
    configure()
    jig.main()
    manifest_path=GEOM/'fabrication-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update({
        'design':'U1 compact short hair, selected by user 2026-10-14',
        'pdf':PDF.relative_to(ROOT).as_posix(),
        'art_source':ART.relative_to(ROOT).as_posix(),
        'reconstruction_scope':'U1 human upper body and hair; selected four-leg and short-tail structure retained, foreleg transition coordinated with U1',
        'cleanup':'centreline strokes, simplified finger seams and neck connections, one arrow axis, no tiny side-waist needle triangle',
        'source_pixels_px':PATHS,
    })
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    runtime=jig.compile_layout(*(jig.read_json(ROOT/'data'/n) for n in ('catalog.json','constellation.json','layout.json')))
    _,segments=jig.geometry()
    poster(runtime,segments)

if __name__=='__main__':main()
