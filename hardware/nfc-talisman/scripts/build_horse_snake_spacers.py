"""Build one passive 100 mm panel: horse, snake and three real routed spacer rings."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from PIL import Image
from shapely import affinity
from shapely.geometry import GeometryCollection, Point, Polygon, box
from shapely.ops import unary_union
import build_twelve_option_panels as panel
import build_standard_layer_artwork as art
from pcb_cover_border import build_border
from audit_cover_borders import native_polygon

HW=Path(__file__).resolve().parents[1]
OUT=HW/'variants/horse-snake-spacers'
KEY='horse-snake-spacers'
NAME='Horse-Snake-3Spacers-GreenWhite-100'
PARTS=[('horse','马'),('snake','蛇'),('spacer-1','隔层一'),('spacer-2','隔层二'),('spacer-3','隔层三')]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):panel.write(path,data)

def generate():
    OUT.mkdir(parents=True,exist_ok=True)
    primitives=[];covers=[];sources={};counter=0
    def source(path):
        sources[path.relative_to(HW.parents[1]).as_posix()]=sha(path)
        return json.loads(path.read_text(encoding='utf-8'))
    mechanical=source(HW/'geometry/design.json')
    spacer=next(b for b in mechanical['boards'] if b['id']=='spacer2')
    window=affinity.translate(Polygon(spacer['cutouts'][0]['ring']),18.5-spacer['center'][0],18.5-spacer['center'][1])
    assert all(abs(a-b)<.000001 for a,b in zip(window.bounds,(3.5,3.5,33.5,33.5)))
    template=next(b for h,b in panel.native.rows((HW/'variants/standard-green-white/eda/native/horse-sagittarius-source.jsonl').read_text(encoding='utf-8')) if h['type']=='PAD' and b.get('hole') and b.get('plated') is False)
    def add(kind,body,logical):
        nonlocal counter
        counter+=1
        primitives.append({'head':{'type':kind,'ticket':1000+counter,'id':hashlib.sha256(f'{KEY}:{logical}'.encode()).hexdigest()[:16]},'body':body,'logical_id':logical})
    def route(shape,logical):
        for i,p in enumerate(art.polygons(shape)):
            add('POLY',dict(partitionId='',groupId=0,netName='',layerId=11,width=3.937,path=panel.physical_path(p),locked=True,zIndex=-1),logical+f':{i}')
    route(box(0,0,100,100),'panel-frame')
    frame=affinity.translate(panel.OCT,18.5,18.5)
    for (name,zh),(cx,cy) in zip(PARTS,panel.CENTERS):
        outer=affinity.translate(panel.OCT,cx,cy)
        corridors=unary_union([box(cx-2,cy-21,cx+2,cy+21),box(cx-21,cy-2,cx+21,cy+2)])
        route(outer.buffer(1,quad_segs=12).difference(outer).difference(corridors),name+':routing')
        for edge in 'NSEW':
            for i,v in enumerate((-1.44,-.72,0,.72,1.44),1):
                x,y=(cx+v,cy+(18.9 if edge=='N' else -18.9)) if edge in 'NS' else (cx+(18.9 if edge=='E' else -18.9),cy+v)
                body=copy.deepcopy(template)
                body.update(num=f'{name}_{edge}_MB{i}',centerX=x/.0254,centerY=y/.0254,locked=True)
                body['hole'].update(width=.4/.0254,height=.4/.0254,cornerRadius=.2/.0254)
                body['defaultPad'].update(width=.4/.0254,height=.4/.0254)
                add('PAD',body,body['num'])
        details={'english_label_on_pcb':False}
        if name in ('horse','snake'):
            variant='horse-sagittarius' if name=='horse' else 'snake-leo'
            path=HW/f'variants/standard-green-white/artwork/{variant}-standard-layer-artwork.json'
            artifact=source(path)
            for path_name,expected in artifact['source_files_sha256'].items():
                p=HW.parents[1]/path_name
                assert sha(p)==expected
                sources[path_name]=expected
            original=artifact['faces']['front']
            ink=unary_union([native_polygon(p['path_mil'],(20.5,76.5)) for p in original['silk_polygons'] if p['category']!='textured_octagonal_border_and_inner_divider'])
            border,metadata,_=build_border(ink,GeometryCollection(),board=frame)
            for role,geometry in [('silk',ink),('border',border)]:
                for i,p in enumerate(art.polygons(geometry)):
                    add('FILL',dict(partitionId='',groupId=0,netName='',layerId=3,width=.2,fillStyle='SOLID',path=panel.native_path(p,(cx,cy)),locked=True,zIndex=-1),f'{name}:{role}:{i}')
            details.update(kind='animal_cover',source_artifact=path.relative_to(HW.parents[1]).as_posix(),source_face='front',source_face_metadata=original['source_metadata'],border=metadata)
        else:
            physical=affinity.translate(affinity.scale(window,1,-1,origin=(0,0)),cx-18.5,cy+18.5)
            route(physical,name+':inner-window')
            details.update(kind='hollow_spacer',outer_af_mm=37,window_af_mm=30,inner_corner_radius_mm=1,minimum_wall_mm=round(frame.boundary.distance(window),6),source_part='geometry/design.json#spacer2',window_local_mm=list(window.exterior.coords))
        covers.append(dict(id=name,name_zh=zh,center_native_mm=[cx,cy],details=details))
    geometry=dict(key=KEY,name=NAME,cover_count=5,covers=covers,primitives=primitives)
    write(OUT/'geometry.json',geometry)
    image=Image.new('RGBA',(2800,2800),'#147442')
    def view(g):return affinity.translate(affinity.scale(g,1,-1,origin=(0,0)),0,100)
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><rect width="100" height="100" fill="#147442"/>']
    for entry in primitives:
        kind,b=entry['head']['type'],entry['body']
        if kind=='FILL':
            rings=[]
            for ring in b['path']:
                v=ring[:2]+ring[3:];rings.append([(v[i]*.0254,v[i+1]*.0254) for i in range(0,len(v),2)])
            g=view(Polygon(rings[0],rings[1:]));color='#fafaf3'
        elif kind=='PAD':g=view(Point(b['centerX']*.0254,b['centerY']*.0254).buffer(.2,quad_segs=16));color='#e9eee9'
        elif entry['logical_id']!='panel-frame:0':
            v=b['path'][:2]+b['path'][3:];g=view(Polygon([(v[i]*.0254,v[i+1]*.0254) for i in range(0,len(v),2)]));color='#e9eee9'
        else:continue
        art.draw_geometry(image,g,color,28);svg.append(panel.svg_geometry(g,color))
    svg.append('</svg>')
    (OUT/'panel-preview.svg').write_text(''.join(svg),encoding='utf-8')
    image.resize((1400,1400),Image.Resampling.LANCZOS).save(OUT/'panel-preview.png')
    sources[Path(__file__).relative_to(HW.parents[1]).as_posix()]=sha(Path(__file__))
    sources[(HW/'scripts/pcb_cover_border.py').relative_to(HW.parents[1]).as_posix()]=sha(HW/'scripts/pcb_cover_border.py')
    for module in ('build_twelve_option_panels.py','build_standard_layer_artwork.py','audit_cover_borders.py'):
        p=HW/'scripts'/module;sources[p.relative_to(HW.parents[1]).as_posix()]=sha(p)
    manifest=dict(schema_version=1,key=KEY,name=NAME,panel_mm=[100,100],cover_af_mm=37,animal_covers=['horse','snake'],hollow_spacers=3,
        spacer_window_af_mm=30,spacer_inner_radius_mm=1,mousebite_outward_offset_mm=.4,mousebite_diameter_mm=.4,mousebite_pitch_mm=.72,
        english_labels=False,sources=sources,files={p.name:dict(size=p.stat().st_size,sha256=sha(p)) for p in [OUT/'geometry.json',OUT/'panel-preview.svg',OUT/'panel-preview.png']},
        release_status='HOLD_CAM_PHYSICAL_VALIDATION_PENDING')
    write(OUT/'design-manifest.json',manifest)
    print(json.dumps({'status':'generated','parts':[x[0] for x in PARTS],'window_mm':30,'minimum_ring_wall_mm':covers[2]['details']['minimum_wall_mm']}))

if __name__=='__main__':generate()
