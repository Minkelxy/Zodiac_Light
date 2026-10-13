"""Render millimetre-native, straight-line-only engraving design candidates."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from constellation_lamp.model import compile_layout, read_json

OUT = ROOT / "output" / "engraving-review"
FONTS = Path("C:/Windows/Fonts")


def candidate_a():
    return {
        "id": "A", "title": "折线弓箭符号", "subtitle": "线条少，适合先试刻",
        "polylines": [
            {"role": "outline", "points": [[245,55],[260,95],[292,155],[310,185],[318,200],
                [310,215],[292,245],[260,305],[245,345],[258,337],[275,303],[307,245],
                [322,219],[328,200],[322,181],[307,155],[275,97],[258,63],[245,55]]},
            {"role": "outline", "points": [[245,55],[115,200],[245,345]]},
            {"role": "outline", "points": [[74,196],[328,196],[328,185],[363,200],
                [328,215],[328,204],[74,204],[74,196]]},
            {"role": "detail", "points": [[74,196],[97,172],[116,177],[98,196]]},
            {"role": "detail", "points": [[74,204],[97,228],[116,223],[98,204]]},
        ],
    }


def stats(candidate):
    lengths = [math.dist(a,b) for p in candidate["polylines"]
               for a,b in zip(p["points"],p["points"][1:])]
    points = [q for p in candidate["polylines"] for q in p["points"]]
    assert lengths and min(lengths) > 0
    assert all(15 <= x <= 385 and 15 <= y <= 385 for x,y in points)
    return {"segments":len(lengths), "min_length_mm":round(min(lengths),2),
            "total_length_mm":round(sum(lengths),1),
            "bounds_mm":[min(p[0] for p in points), min(p[1] for p in points),
                         max(p[0] for p in points), max(p[1] for p in points)]}


def svg(candidate, runtime, overlay=False):
    body = []
    body.append('<rect x="0" y="0" width="400" height="400" fill="white"/>')
    body.append('<rect x=".5" y=".5" width="399" height="399" fill="none" stroke="#bbbbbb" stroke-width=".4"/>')
    if overlay:
        for piece in runtime.pieces:
            a,b = piece.path_mm
            length = math.dist(a,b)
            nx,ny = -(b[1]-a[1])/length*2.5, (b[0]-a[0])/length*2.5
            pts = [(a[0]+nx,a[1]+ny),(b[0]+nx,b[1]+ny),(b[0]-nx,b[1]-ny),(a[0]-nx,a[1]-ny)]
            body.append('<polygon points="'+" ".join(f"{x:.4f},{y:.4f}" for x,y in pts)+'" fill="#d6e8f4" stroke="#86a7be" stroke-width=".25"/>')
    for p in candidate["polylines"]:
        pts=" ".join(f"{x:g},{y:g}" for x,y in p["points"])
        width=.65 if p["role"]=="outline" else .4
        body.append(f'<polyline points="{pts}" fill="none" stroke="#161616" stroke-width="{width}" stroke-linejoin="miter" stroke-linecap="butt"/>')
    title=escape(candidate["title"])
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="400mm" height="400mm" viewBox="0 0 400 400"><title>{title}</title>'+"".join(body)+"</svg>\n"


def panel(candidate,runtime,overlay=False,size=1200):
    s=3
    im=Image.new('RGB',(size*s,(size+135)*s),'white')
    d=ImageDraw.Draw(im)
    title=ImageFont.truetype(str(FONTS/'msyhbd.ttc'),int(40*s))
    small=ImageFont.truetype(str(FONTS/'msyh.ttc'),int(23*s))
    d.text((32*s,20*s),f"{candidate['id']} · {candidate['title']}",font=title,fill='#202020')
    st=candidate['stats']
    d.text((32*s,77*s),f"{st['segments']} 段直线 / 最短 {st['min_length_mm']:g} mm / {candidate['subtitle']}",font=small,fill='#666666')
    margin=32
    scale=(size-margin*2)/400
    def xy(p):
        return ((margin+p[0]*scale)*s,(135+p[1]*scale)*s)
    d.rectangle([xy((0,0)),xy((400,400))],outline='#bbbbbb',width=s)
    if overlay:
        for piece in runtime.pieces:
            a,b=piece.path_mm
            length=math.dist(a,b)
            nx,ny=-(b[1]-a[1])/length*2.5,(b[0]-a[0])/length*2.5
            pts=[(a[0]+nx,a[1]+ny),(b[0]+nx,b[1]+ny),(b[0]-nx,b[1]-ny),(a[0]-nx,a[1]-ny)]
            d.polygon([xy(p) for p in pts],fill='#d6e8f4',outline='#86a7be',width=max(1,round(.25*scale*s)))
    for p in candidate['polylines']:
        width=.65 if p['role']=='outline' else .4
        d.line([xy(q) for q in p['points']],fill='#161616',width=max(1,round(width*scale*s)))
    footer_y=(135+400*scale+11)*s
    label='浅蓝 = 现有灯条区域；黑线 = 待刻线' if overlay else '400 × 400 mm 板面比例示意 · 审图预览'
    d.text((32*s,footer_y),label,font=small,fill='#666666')
    return im.resize((size,size+135),Image.Resampling.LANCZOS)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    apath=OUT/'candidate-a.json'
    apath.write_text(json.dumps(candidate_a(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    runtime=compile_layout(*(read_json(ROOT/'data'/n) for n in ('catalog.json','constellation.json','layout.json')))
    candidates=[]
    for id in 'abcd':
        path=OUT/f'candidate-{id}.json'
        if not path.exists():
            continue
        candidate=json.loads(path.read_text(encoding='utf-8'))
        candidate['stats']=stats(candidate)
        candidates.append(candidate)
        path.write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for overlay in (False,True):
            suffix='-with-leds' if overlay else ''
            (OUT/f'candidate-{id}{suffix}.svg').write_text(svg(candidate,runtime,overlay),encoding='utf-8')
            panel(candidate,runtime,overlay).save(OUT/f'candidate-{id}{suffix}.png')
    for overlay in (False,True):
        sheet=Image.new('RGB',(2400,2670),'#e5e5e5')
        for i,can in enumerate(candidates):
            sheet.paste(panel(can,runtime,overlay),((i%2)*1200,(i//2)*1335))
        sheet.save(OUT/('review-with-leds.png' if overlay else 'review-designs.png'))
    manifest={"board_mm":[400,400],"geometry":"straight polylines only",
              "status":"review candidates, awaiting selection before A4 template",
              "layout_sha256":hashlib.sha256((ROOT/'data/layout.json').read_bytes()).hexdigest(),
              "candidates":[{"id":c['id'],"title":c['title'],**c['stats']} for c in candidates]}
    (OUT/'review-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__':
    main()
