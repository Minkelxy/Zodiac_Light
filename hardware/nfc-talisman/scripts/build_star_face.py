"""Build manufacture-aware Sagittarius linework and vector review previews.

No copper is added. The mechanical holes/slots come from geometry/design.json;
ink stays on the retained material and the two existing Latin inscriptions stay.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from build_mechanical import octagon

ROOT=Path(__file__).resolve().parents[1]
WIDTH=0.18
CLEARANCE=0.20


def main():
    geometry=json.loads((ROOT/'geometry/design.json').read_text(encoding='utf-8'))
    art_path=ROOT/'artwork/art_data.json'
    art=json.loads(art_path.read_text(encoding='utf-8'))
    stars=geometry['constellation']['stars_local']
    edges=geometry['constellation']['edges']
    centers={s['id']:s['center'] for s in stars}
    additions=[]
    for star in stars:
        radius=star['diameter_mm']/2+CLEARANCE+WIDTH/2
        cx,cy=star['center']
        points=[[round(cx+radius*math.cos(2*math.pi*i/64),6),round(cy+radius*math.sin(2*math.pi*i/64),6)] for i in range(64)]
        additions.append({'id':'star_rim_'+star['id'],'width_mm':WIDTH,'points':points,'closed':True})
    for edge in edges:
        for key,endpoint,label in [('start','endpoint_a','a'),('end','endpoint_b','b')]:
            center=centers[edge[key]]
            cap=edge[endpoint]
            dx,dy=cap[0]-center[0],cap[1]-center[1]
            length=math.hypot(dx,dy)
            near=0.4+CLEARANCE+WIDTH/2
            far=length-0.5-CLEARANCE-WIDTH/2
            if far<=near:
                raise ValueError('No safe printed connector segment: '+edge['id'])
            points=[[round(center[0]+dx/length*t,6),round(center[1]+dy/length*t,6)] for t in (near,far)]
            additions.append({'id':f"star_link_{edge['id']}_{label}",'width_mm':WIDTH,'points':points,'closed':False})
    base=[s for s in art['sagittarius_silkscreen'] if not s['id'].startswith(('star_rim_','star_link_'))]
    art['sagittarius_silkscreen']=base+additions
    art['implementation_notes']=[n for n in art['implementation_notes'] if not n.startswith('Sagittarius retains eight')]
    art['implementation_notes'].append('Sagittarius uses eight star rims and 22 fine printed connector segments on retained material, eight drilled stars and eleven isolated light slots. AD ASTRA / FORTIS ET LIBER remain; no centaur art or decorative copper.')
    art['sagittarius_linework']={'stroke_width_mm':WIDTH,'nominal_aperture_clearance_mm':CLEARANCE,
        'star_rim_count':8,'connector_segment_count':22,
        'requested_appearance':'Dark background with light linework, confirmed by user.',
        'appearance_note':'Dark background/light linework is the confirmed color-print direction. The dedicated color-object import/output is verified separately; final ink compositing, alpha and sample appearance require manufacturing preview and physical acceptance.'}
    voids=[Point(s['center']).buffer(0.4,quad_segs=48) for s in stars]
    voids += [LineString([e['endpoint_a'],e['endpoint_b']]).buffer(0.5,quad_segs=48) for e in edges]
    apertures=unary_union(voids)
    strokes=[]
    for s in art['sagittarius_silkscreen']:
        pts=s['points']+([s['points'][0]] if s['closed'] else [])
        strokes.append((s['id'],LineString(pts).buffer(s['width_mm']/2,cap_style='round',join_style='round')))
    min_gap=min((shape.distance(apertures),name) for name,shape in strokes)
    outside=[name for name,shape in strokes if not octagon(37).covers(shape)]
    if min_gap[0]<0.18 or outside:
        raise ValueError(f'Ink clearance/edge violation: {min_gap}, {outside}')
    board=next(b for b in geometry['boards'] if b['id']=='sagittarius5')
    cx,cy=board['center']
    spacer=next(b for b in geometry['boards'] if b['id']=='spacer4')
    sx,sy=spacer['center']
    window=Polygon([[x-sx,y-sy] for x,y in spacer['cutouts'][0]['ring']])
    # Optical projection reflects the exterior-back X coordinate across the stack.
    from shapely.affinity import scale
    projected=scale(apertures,xfact=-1,yfact=1,origin=(0,0))
    window_gap=projected.distance(window.boundary)
    if not window.covers(projected):
        raise ValueError('Rear holes/slots fall outside the spacer optical window')
    report={'status':'geometry_and_ink_pass','star_count':len(stars),'slot_count':len(edges),
        'star_rims':8,'printed_connectors':22,'existing_latin_keyline_paths':len(base),
        'total_silkscreen_paths':len(art['sagittarius_silkscreen']),
        'minimum_ink_to_aperture_mm':min_gap[0],'closest_ink_path':min_gap[1],
        'all_ink_within_board':not outside,'all_optical_apertures_within_mirrored_spacer_window':True,
        'minimum_aperture_to_window_edge_mm':window_gap,
        'source_constellation_semantic_sha256':hashlib.sha256(json.dumps(geometry['constellation'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'appearance_note':art['sagittarius_linework']['appearance_note'],
        'limitations':['Printed connectors do not transmit light; isolated machined slots remain separated by material webs.','Geometric preview does not establish actual NFC illumination, print contrast or manufacturing approval.']}
    art_path.write_text(json.dumps(art,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (ROOT/'artwork/sagittarius-linework-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    # The SVG is editable and importable; the PNG only illustrates the geometry.
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="42mm" height="42mm" viewBox="-21 -21 42 42">',
        '<title>Sagittarius exterior view: physical holes/slots and printed connecting links</title>',
        '<desc>Dark appearance reference. Current fabrication substrate is white; contrasting print remains to be qualified. Amber indicates optical apertures, not measured light.</desc>']
    outline=list(octagon(37).exterior.coords)
    svg.append('<polygon points="'+ ' '.join(f'{x:.6f},{y:.6f}' for x,y in outline)+'" fill="#17232f"/>')
    image=Image.new('RGB',(1260,1260),'#f2efe9')
    draw=ImageDraw.Draw(image)
    def xy(points):return [((x+21)*30,(y+21)*30) for x,y in points]
    draw.polygon(xy(outline),fill='#17232f')
    for s in art['sagittarius_silkscreen']:
        pts=s['points']+([s['points'][0]] if s['closed'] else [])
        svg.append(f'<polyline id="{escape(s["id"])}" points="'+ ' '.join(f'{x:.6f},{y:.6f}' for x,y in pts)+f'" fill="none" stroke="#eee8d6" stroke-width="{s["width_mm"]}" stroke-linecap="round" stroke-linejoin="round"/>')
        draw.line(xy(pts),fill='#eee8d6',width=round(s['width_mm']*30),joint='curve')
    for edge in edges:
        a,b=edge['endpoint_a'],edge['endpoint_b']
        svg.append(f'<path id="slot_{edge["id"]}" d="M {a[0]},{a[1]} L {b[0]},{b[1]}" fill="none" stroke="#e9bb63" stroke-width="1" stroke-linecap="round"/>')
        draw.line(xy([a,b]),fill='#e9bb63',width=30)
        for x,y in xy([a,b]):draw.ellipse((x-15,y-15,x+15,y+15),fill='#e9bb63')
    for star in stars:
        x,y=star['center']
        svg.append(f'<circle id="{star["id"]}" cx="{x}" cy="{y}" r="0.4" fill="#e9bb63"/>')
        px,py=xy([(x,y)])[0]
        draw.ellipse((px-12,py-12,px+12,py+12),fill='#e9bb63')
    svg.append('</svg>')
    (ROOT/'artwork/sagittarius_face.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')
    image.save(ROOT/'artwork/sagittarius-face-review.png')
    # Separate full-size color-print candidate: no review canvas or amber light.
    # Register as 37x37mm. A 0.20mm clear border around cuts leaves room for
    # print registration; the actual holes and slots come from mechanical CAM.
    ppm=100
    color=Image.new('RGBA',(3700,3700),(0,0,0,0))
    cd=ImageDraw.Draw(color)
    def cxy(points):return [((x+18.5)*ppm,(y+18.5)*ppm) for x,y in points]
    cd.polygon(cxy(outline),fill='#17232f')
    for s in art['sagittarius_silkscreen']:
        pts=s['points']+([s['points'][0]] if s['closed'] else [])
        cd.line(cxy(pts),fill='#eee8d6',width=round(s['width_mm']*ppm),joint='curve')
    clip=Image.new('L',color.size,0)
    cl=ImageDraw.Draw(clip)
    cl.polygon(cxy(list(octagon(37).buffer(-CLEARANCE).exterior.coords)),fill=255)
    for cut in apertures.buffer(CLEARANCE).geoms:
        cl.polygon(cxy(list(cut.exterior.coords)),fill=0)
    color.putalpha(clip)
    color.save(ROOT/'artwork/sagittarius-color-print-candidate.png',dpi=(2540,2540))
    color_note={'status':'color_print_candidate_not_manufacturing_release',
        'file':'artwork/sagittarius-color-print-candidate.png','size_mm':[37,37],
        'pixels':[3700,3700],'pixels_per_mm':ppm,'background_rgb':'#17232f','line_rgb':'#eee8d6',
        'transparent_border_mm':CLEARANCE,'transparent_aperture_expansion_mm':CLEARANCE,
        'panel_design_center_mm':board['center'],'native_bbox_top_left_mm':[61,42],
        'orientation':'Exterior rear view; 0deg and no horizontal mirror. Verify API image Y convention after import.',
        'contains_horse_art':False,'limitations':['Import and dedicated color-silkscreen output must be verified separately.','Color and light appearance require a physical sample.']}
    (ROOT/'artwork/sagittarius-color-print-candidate.json').write_text(json.dumps(color_note,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
