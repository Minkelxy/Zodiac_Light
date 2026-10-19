"""Build four 100 mm panels of five interchangeable AF37 covers, offline.

The ten new constellations use frozen Stellarium Modern/Hipparcos inputs with
web-constrained light slots. Zodiac covers trace the existing project talismans.
No live EasyEDA calls are made by this generator.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely import affinity
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box
from shapely.ops import unary_union

import build_standard_layer_artwork as art
import create_standard_layer_pcbs as native
from constellation_slot_layout import optimize_slot_layout
import talisman_cover_artwork
from pcb_cover_border import build_border

HW = Path(__file__).resolve().parents[1]
OUT = HW/'variants/twelve-options'
CENTERS = [(21,79),(79,79),(50,50),(21,21),(79,21)]
H=18.5
Q=H*(math.sqrt(2)-1)
OCT=Polygon([(-Q,H),(Q,H),(H,Q),(H,-Q),(Q,-H),(-Q,-H),(-H,-Q),(-H,Q)])
GROUPS = {
 'constellations-a': [('aries','白羊座','Ari'),('taurus','金牛座','Tau'),('gemini','双子座','Gem'),('cancer','巨蟹座','Cnc'),('virgo','处女座','Vir')],
 'constellations-b': [('libra','天秤座','Lib'),('scorpius','天蝎座','Sco'),('capricornus','摩羯座','Cap'),('aquarius','水瓶座','Aqr'),('pisces','双鱼座','Psc')],
 'zodiac-a': [('rat','鼠',''),('ox','牛',''),('tiger','虎',''),('rabbit','兔',''),('dragon','龙','')],
 'zodiac-b': [('goat','羊',''),('monkey','猴',''),('rooster','鸡',''),('dog','狗',''),('pig','猪','')],
}
NAMES={k:('Constellations' if k.startswith('constellations') else 'Zodiac')+'-'+k[-1].upper()+'-5x37-GreenWhite-100' for k in GROUPS}


def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def label(value,y,size=1.55):
 t=TextPath((0,0),value,size=size,prop=FontProperties(family='DejaVu Sans',weight='bold'))
 rings=t.to_polygons();parts=[]
 # Matplotlib nonzero contours: negative exterior and positive counters.
 for ring in rings:
  p=Polygon(ring)
  area=sum(ring[i][0]*ring[i+1][1]-ring[i+1][0]*ring[i][1] for i in range(len(ring)-1))
  parts.append((p,area))
 g=unary_union([p for p,a in parts if a<0]).difference(unary_union([p for p,a in parts if a>0]))
 if g.is_empty:raise ValueError('Text outline orientation')
 g=affinity.scale(g,1,-1,origin=(0,0));b=g.bounds
 return affinity.translate(g,18.5-(b[0]+b[2])/2,y-b[1])


def load_stars():
 src=OUT/'sources';data=json.loads((src/'stellarium-modern-index.json').read_text())
 catalog={}
 for line in (src/'hipparcos-zodiac.tsv').read_text().splitlines():
  cols=line.split('\t')
  if len(cols)==4 and cols[0].strip().isdigit():
   hip=int(cols[0]);catalog[hip]=tuple(map(float,cols[1:]))
 wanted={x[2] for k,g in GROUPS.items() if k.startswith('constellations') for x in g}
 patterns={c['id'].split()[-1]:c['lines'] for c in data['constellations'] if c['id'].split()[-1] in wanted}
 assert len(catalog)==113 and len(patterns)==10
 return catalog,patterns


def star_cover(abbr,catalog,patterns):
 chains=patterns[abbr];hips=sorted({h for l in chains for h in l})
 ra=np.radians([catalog[h][0] for h in hips]);dec=np.radians([catalog[h][1] for h in hips])
 r0=math.atan2(np.sin(ra).mean(),np.cos(ra).mean());d0=float(dec.mean())
 dra=(ra-r0+np.pi)%(2*np.pi)-np.pi
 denom=np.sin(dec)*math.sin(d0)+np.cos(dec)*math.cos(d0)*np.cos(dra)
 p=np.column_stack((-np.cos(dec)*np.sin(dra)/denom,-(np.sin(dec)*math.cos(d0)-np.cos(dec)*math.sin(d0)*np.cos(dra))/denom))
 p-=p.mean(axis=0);scale=min(25/np.ptp(p[:,0]),20/max(np.ptp(p[:,1]),1e-6));p*=scale
 p+=np.array([18.5,18.8]);before=p.copy()
 # Preserve all HIP nodes/edges while easing crowded double stars for PCB holes.
 for iteration in range(250):
  force=(before-p)*.018
  for i in range(len(p)):
   for j in range(i):
    v=p[i]-p[j];d=float(np.linalg.norm(v))
    if d<2.35:
     if d<1e-9:v=np.array([1.,0]);d=1
     f=v/d*(2.35-d)*.28;force[i]+=f;force[j]-=f
  p+=force;p[:,0]=np.clip(p[:,0],4.2,32.8);p[:,1]=np.clip(p[:,1],8.2,29.4)
 positions={h:tuple(p[i]) for i,h in enumerate(hips)}
 edges=sorted({tuple(sorted((a,b))) for chain in chains for a,b in zip(chain,chain[1:]) if a!=b})
 layout=optimize_slot_layout(positions,edges)
 positions,slots=layout.positions,layout.slots
 p=np.array([positions[h] for h in hips])
 holes=unary_union([Point(v).buffer(.4,quad_segs=24) for v in positions.values()])
 silk=unary_union([Point(v).buffer(1,quad_segs=32).difference(Point(v).buffer(.8,quad_segs=32)) for v in positions.values()])
 for a,b in edges:silk=silk.union(LineString([positions[a],positions[b]]).buffer(.11,quad_segs=8))
 printed=layout.metadata['printed_only_edges']
 aperture=unary_union([holes,*slots]);mask=aperture.buffer(.2,quad_segs=12)
 silk=silk.difference(mask.buffer(.16,quad_segs=12))
 return silk,mask,positions,slots,{'hip_ids':hips,'source_chains':chains,'edges':edges,'printed_only_edges':printed,
  'maximum_layout_adjustment_mm':float(np.linalg.norm(p-before,axis=1).max()),
  'minimum_star_spacing_mm':min(float(np.linalg.norm(p[i]-p[j])) for i in range(len(p)) for j in range(i)),
  'star_hole_diameter_mm':.8,'slot_width_mm':1.,'slot_layout':layout.metadata,
  'coordinate_policy':'Hipparcos ICRS -> tangent plane, north up / east left; fit and recorded hole-spacing adjustment'}


def native_path(poly,center):
 def convert(ring):
  pts=[((center[0]+x-18.5)/.0254,(center[1]+18.5-y)/.0254) for x,y in ring.coords]
  return [round(pts[0][0],6),round(pts[0][1],6),'L',*[round(n,6) for pt in pts[1:] for n in pt]]
 # orient in native (y-up) direction: outer CW, holes CCW.
 p=art.orient(poly,sign=1.)
 return [convert(p.exterior),*[convert(r) for r in p.interiors]]


def physical_path(poly):
 pts=list(poly.exterior.coords)
 return [round(pts[0][0]/.0254,6),round(pts[0][1]/.0254,6),'L',*[round(n/.0254,6) for pt in pts[1:] for n in pt]]


def svg_geometry(g,color):
 return f'<path d="{art.svg_path(g)}" fill="{color}" fill-rule="evenodd"/>' if not g.is_empty else ''


def generate():
 OUT.mkdir(parents=True,exist_ok=True);catalog,patterns=load_stars()
 source=HW/'variants/standard-green-white/eda/native/horse-sagittarius-source.jsonl'
 hole_template=next(b for h,b in native.rows(source.read_text()) if h['type']=='PAD' and b.get('hole') and not b.get('plated'))
 manifest={'schema_version':1,'process':{'mask':'green','silk':'white','color_printing':False,'decorative_copper':False},
  'existing_constellations':['sagittarius','leo'],'existing_zodiac':['horse','snake'],'panels':[],
  'cover_af_mm':37,'panel_mm':[100,100],'routing_gap_mm':1.,'tab_width_mm':4.,'mousebite_diameter_mm':.4,
  'release_status':'HOLD_CAM_PHYSICAL_VALIDATION_PENDING','role':'interchangeable passive covers; reuse existing NFC core'}
 for key,entries in GROUPS.items():
  primitives=[];covers=[];counter=0
  def add(kind,body,logical):
   nonlocal counter
   counter+=1;ident=hashlib.sha256(f'{key}:{logical}:{counter}'.encode()).hexdigest()[:16]
   primitives.append({'head':{'type':kind,'ticket':1000+counter,'id':ident},'body':body,'logical_id':logical})
  def poly(g,logical):
   for i,p in enumerate(art.polygons(g)):
    add('POLY',{'partitionId':'','groupId':0,'netName':'','layerId':11,'width':3.937,'path':physical_path(p),'locked':True,'zIndex':-1},logical+f':{i}')
  def hole(x,y,d,name):
   b=copy.deepcopy(hole_template);b.update(num=name,centerX=x/.0254,centerY=y/.0254,locked=True)
   b['hole'].update(width=d/.0254,height=d/.0254,cornerRadius=d/2/.0254);b['defaultPad'].update(width=d/.0254,height=d/.0254)
   add('PAD',b,name)
  poly(box(0,0,100,100),'panel-frame')
  svg_parts=['<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><rect width="100" height="100" fill="#0a482b"/>']
  route_all=[]
  for (name,zh,abbr),center in zip(entries,CENTERS):
   shape=affinity.translate(OCT,*center)
   corridors=unary_union([box(center[0]-2,center[1]-21,center[0]+2,center[1]+21),box(center[0]-21,center[1]-2,center[0]+21,center[1]+2)])
   routing=shape.buffer(1,quad_segs=12).difference(shape).difference(corridors)
   poly(routing,name+':routing');route_all.append(routing)
   for edge in ('N','S','E','W'):
    for j,v in enumerate((-1.44,-.72,0,.72,1.44)):
     x,y=(center[0]+v,center[1]+(18.5 if edge=='N' else -18.5)) if edge in('N','S') else (center[0]+(18.5 if edge=='E' else -18.5),center[1]+v)
     hole(x,y,.4,f'{name}_{edge}_MB{j+1}')
   if abbr:
    silk,mask,positions,slots,details=star_cover(abbr,catalog,patterns)
    for hip,(x,y) in positions.items():hole(center[0]+x-18.5,center[1]+18.5-y,.8,f'{name}_HIP{hip}')
    for i,slot in enumerate(slots):poly(affinity.translate(affinity.scale(slot,1,-1,origin=(0,0)),center[0]-18.5,center[1]+18.5),name+f':light-slot:{i}')
    silk=silk.union(label(name.upper(),3.7)).union(label('AD ASTRA',32.1,1.45))
   else:
    silk,mask,details=talisman_cover_artwork.build_cover(name,board_margin_mm=3.0)
    silk=silk.union(label(name.upper(),32.1,1.6))
   clip=affinity.translate(OCT,18.5,18.5).buffer(-1.2)
   if not abbr and silk.difference(clip).area>1e-8:raise ValueError('Talisman/label would be cropped')
   silk=silk.intersection(clip)
   assert silk.is_valid and not silk.is_empty and silk.intersection(mask).area<1e-8
   if not mask.is_empty:assert silk.distance(mask)>.149
   border,border_meta,_=build_border(silk,mask,board=affinity.translate(OCT,18.5,18.5))
   details['border']=border_meta
   for kind,g,layer in [('silk',silk,3),('mask',mask,5)]:
    for i,p in enumerate(art.polygons(g)):
     add('FILL',{'partitionId':'','groupId':0,'netName':'','layerId':layer,'width':.2,'fillStyle':'SOLID','path':native_path(p,center),'locked':True,'zIndex':-1},f'{name}:{kind}:{i}')
   for i,p in enumerate(art.polygons(border)):
    add('FILL',{'partitionId':'','groupId':0,'netName':'','layerId':3,'width':.2,'fillStyle':'SOLID','path':native_path(p,center),'locked':True,'zIndex':-1},f'{name}:border:{i}')
   covers.append({'id':name,'name_zh':zh,'center_native_mm':center,'details':details,'silk_polygons':len(art.polygons(silk))+len(art.polygons(border)),'mask_polygons':len(art.polygons(mask))})
   # Exterior view of entire PCB: SVG y increases downward.
   cx,cy=center[0]-18.5,100-center[1]-18.5
   svg_parts.append(f'<g transform="translate({cx},{cy})">'+svg_geometry(affinity.translate(OCT,18.5,18.5),'#147442')+svg_geometry(mask,'#c6ad78')+svg_geometry(silk.union(border),'#fafaf3')+'</g>')
  svg_parts.append('</svg>')
  (OUT/'artwork').mkdir(exist_ok=True);svg=OUT/'artwork'/f'{key}-100mm.svg';svg.write_text(''.join(svg_parts),encoding='utf-8')
  from PIL import Image
  image=Image.new('RGBA',(2800,2800),'#147442')
  def exterior(g):return affinity.translate(affinity.scale(g,1,-1,origin=(0,0)),0,100)
  for layer,color in [(5,'#c6ad78'),(3,'#fafaf3')]:
   for entry in primitives:
    b=entry['body']
    if entry['head']['type']=='FILL' and b['layerId']==layer:
     rings=[]
     for ring in b['path']:
      values=ring[:2]+ring[3:];rings.append([(values[i]*.0254,values[i+1]*.0254) for i in range(0,len(values),2)])
     art.draw_geometry(image,exterior(Polygon(rings[0],rings[1:])),color,28)
  for entry in primitives:
   b=entry['body'];g=None
   if entry['head']['type']=='PAD':g=Point(b['centerX']*.0254,b['centerY']*.0254).buffer(b['hole']['width']*.0254/2,quad_segs=16)
   elif entry['head']['type']=='POLY' and not entry['logical_id'].startswith('panel-frame'):
    r=b['path'];v=r[:2]+r[3:];g=Polygon([(v[i]*.0254,v[i+1]*.0254) for i in range(0,len(v),2)])
   if g is not None:
    art.draw_geometry(image,exterior(g),'#e9eee9',28)
    svg_parts.insert(-1,svg_geometry(exterior(g),'#e9eee9'))
  svg.write_text(''.join(svg_parts),encoding='utf-8')
  image.resize((1400,1400),Image.Resampling.LANCZOS).save(svg.with_suffix('.png'))
  geometry={'key':key,'name':NAMES[key],'cover_count':5,'covers':covers,'primitives':primitives}
  write(OUT/'geometry'/f'{key}.json',geometry)
  manifest['panels'].append({'key':key,'name':NAMES[key],'covers':[x[0] for x in entries],'geometry':f'geometry/{key}.json','preview':f'artwork/{key}-100mm.png','primitive_count':len(primitives)})
 assert len({n for k in GROUPS for n,z,a in GROUPS[k]})==20
 shapes=[affinity.translate(OCT,*c) for c in CENTERS]
 manifest['minimum_cover_to_cover_gap_mm']=min(a.distance(b) for i,a in enumerate(shapes) for b in shapes[i+1:])
 manifest['minimum_outer_rail_mm']=1.5
 border_module=Path(__file__).with_name('pcb_cover_border.py')
 manifest['border_generator']={'path':border_module.relative_to(HW.parents[1]).as_posix(),'sha256':hashlib.sha256(border_module.read_bytes()).hexdigest()}
 manifest['files']={p.relative_to(OUT).as_posix():{'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for folder in ('geometry','artwork','sources') for p in (OUT/folder).glob('*') if p.is_file()}
 write(OUT/'design-manifest.json',manifest)
 print(json.dumps({'panels':manifest['panels'],'cover_gap_mm':manifest['minimum_cover_to_cover_gap_mm']},ensure_ascii=False,indent=2))


if __name__=='__main__':generate()
