"""Build an offline solid-fill shape for the 4-turn NFC antenna.

This does not touch EasyEDA. The fill still needs native bridge-copper settings
for ANT_LA/ANT_LB, which the installed API does not expose.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from shapely.geometry import LineString, Point, Polygon

ROOT=Path(__file__).resolve().parents[1]
MM_PER_MIL=0.0254
OUT=ROOT/'electrical/antenna-coil-fill-candidate.json'
SVG=ROOT/'artwork/antenna-coil-preview.svg'

def build() -> dict:
    centerline=[]
    apothem=16.875
    pitch=0.502
    for i in range(4*32+1):
        progress=i/32
        angle=math.pi+progress*math.tau
        a=apothem-pitch*progress
        delta=(angle+math.pi/8)%(math.pi/4)-math.pi/8
        radius=a/math.cos(delta)
        centerline.append((radius*math.cos(angle),radius*math.sin(angle)))
    trace=LineString(centerline)
    copper=trace.buffer(0.125,cap_style=2,join_style=2,mitre_limit=2)
    if copper.geom_type!='Polygon' or not copper.is_valid:
        raise RuntimeError(f'Expected one valid coil polygon, got {copper.geom_type}, valid={copper.is_valid}')
    if copper.interiors:
        raise RuntimeError('Coil buffer unexpectedly contains holes')
    points_mm=[(round(x,7),round(y,7)) for x,y in list(copper.exterior.coords)[:-1]]
    if len(points_mm)<3:
        raise RuntimeError('Coil fill polygon is too small')
    points_mil=[(round(x/MM_PER_MIL,5),round(y/MM_PER_MIL,5)) for x,y in points_mm]
    board_radius=18.5/math.cos(math.pi/8)
    board=Polygon([(board_radius*math.cos(math.pi/8+i*math.pi/4),board_radius*math.sin(math.pi/8+i*math.pi/4)) for i in range(8)])
    if not board.buffer(-0.15).covers(copper):
        raise RuntimeError('Antenna fill violates 0.15mm board-edge inset')
    via_centers=[(-16.975,0.0),(-14.775,0.0)]
    via_checks=[{'x_mm':x,'y_mm':y,'copper_overlap_mm':round(0.225-Point(x,y).distance(copper),7)} for x,y in via_centers]
    if min(v['copper_overlap_mm'] for v in via_checks)<=0:
        raise RuntimeError('A coil terminal via would not overlap the fill polygon')
    return {
        'status':'geometry_candidate_only',
        'layer':'TOP',
        'bridge_nets':['ANT_LA','ANT_LB'],
        'bridge_enabled':False,
        'trace_width_mm':0.25,
        'centerline_pitch_mm':pitch,
        'turns':4,
        'outer_flat_to_flat_mm':34.0,
        'polygon_valid':copper.is_valid,
        'polygon_type':copper.geom_type,
        'vertex_count':len(points_mil),
        'area_mm2':round(copper.area,6),
        'bounds_mm':[round(v,6) for v in copper.bounds],
        'board_edge_min_clearance_mm':round(copper.distance(board.boundary),6),
        'minimum_centerline_pitch_gap_mm':round(pitch-0.25,6),
        'terminal_via_overlap_checks':via_checks,
        'points_native_mil':points_mil,
        'note':'Generated offline from the reviewed spiral centerline. It is not yet an EasyEDA bridge fill and has not been checked against the final full-stack assembly or native DRC.'
    }

def write_svg(data:dict) -> None:
    pts=data['points_native_mil']
    path='M '+' L '.join(f'{x*MM_PER_MIL:.5f},{-y*MM_PER_MIL:.5f}' for x,y in pts)+' Z'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="-19 -19 38 38">
<rect x="-19" y="-19" width="38" height="38" fill="#111820"/>
<polygon points="18.500,-7.654 7.654,-18.500 -7.654,-18.500 -18.500,-7.654 -18.500,7.654 -7.654,18.500 7.654,18.500 18.500,7.654" fill="none" stroke="#a9b2bb" stroke-width="0.25"/>
<path d="{path}" fill="#d7a73e" stroke="#ffdf80" stroke-width="0.035" fill-rule="evenodd"/>
<text x="0" y="0" text-anchor="middle" dominant-baseline="middle" fill="#a9b2bb" font-size="1.1">34 mm · 4 TURNS · 0.25 / 0.25 mm</text>
</svg>'''
    SVG.write_text(svg,encoding='utf-8')

def main()->None:
    data=build()
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_svg(data)
    print(json.dumps({k:v for k,v in data.items() if k!='points_native_mil'},ensure_ascii=False))

if __name__=='__main__':
    main()
