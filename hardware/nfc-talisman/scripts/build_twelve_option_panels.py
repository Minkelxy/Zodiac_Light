"""Build four 100 mm panels of five interchangeable AF37 covers, offline.

The ten new constellations use frozen Stellarium Modern/Hipparcos inputs. Ten
original animal line drawings are defined here as editable vector paths.
No live EasyEDA calls are made by this generator.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import secrets

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MPath
from matplotlib.textpath import TextPath
from shapely import affinity
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box
from shapely.ops import unary_union

import build_standard_layer_artwork as art
import create_standard_layer_pcbs as native

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


def curve(d):
 """Flatten absolute M/L/Q/C/Z path commands into editable vector polylines."""
 ts=re.findall(r'[MLCQZ]|[-+]?(?:\d*\.\d+|\d+)',d)
 i=0;cmd=None;parts=[];pts=[];cur=None;start=None
 while i<len(ts):
  if ts[i].isalpha():
   cmd=ts[i];i+=1
   if cmd=='Z':
    pts.append(start);cur=start;parts.append(pts);pts=[];continue
  n={'M':2,'L':2,'Q':4,'C':6}[cmd]
  v=list(map(float,ts[i:i+n]));i+=n
  if cmd=='M':
   if pts:parts.append(pts)
   cur=tuple(v);start=cur;pts=[cur];cmd='L'
  elif cmd=='L':cur=tuple(v);pts.append(cur)
  else:
   p=np.array(cur);end=np.array(v[-2:]);a=np.array(v[:2])
   for t in np.linspace(0,1,32)[1:]:
    point=(1-t)**2*p+2*(1-t)*t*a+t*t*end if cmd=='Q' else (1-t)**3*p+3*(1-t)**2*t*a+3*(1-t)*t*t*np.array(v[2:4])+t**3*end
    pts.append(tuple(point))
   cur=tuple(end)
 if pts:parts.append(pts)
 return parts


def stroke(d,w=.48):
 return unary_union([LineString(p).buffer(w/2,quad_segs=8) for p in curve(d)])


def solid(d):
 return unary_union([Polygon(p).buffer(0) for p in curve(d) if len(p)>3])


def ellipse(x,y,rx,ry):
 return affinity.scale(Point(x,y).buffer(1,quad_segs=32),rx,ry)


def animal(name):
 """Original single-ink line drawings, in a 24 x 24 mm design square."""
 S=stroke;E=ellipse
 if name=='rat':
  g=S('M 6 16 C 5 10 8 8 12 9 C 13 5 18 6 18 10 L 21 14 L 17 16 C 14 21 7 21 6 16 M 6 17 C 0 21 0 11 3 13 M 11 19 L 9 21 L 13 21 M 17 15 L 22 14 M 17 16 L 22 17')
  g=g.union(E(14.8,11.5,.55,.55)).union(S('M 14 9 C 16 8 18 10 16 11',.35))
 elif name=='ox':
  g=S('M 7 8 C 3 7 2 3 3 2 C 5 6 7 5 9 6 M 17 8 C 21 7 22 3 21 2 C 19 6 17 5 15 6 M 7 7 C 8 4 16 4 17 7 L 17 16 C 17 21 7 21 7 16 Z M 7 9 L 3 8 L 5 12 L 7 12 M 17 9 L 21 8 L 19 12 L 17 12 M 8 15 C 10 12 14 12 16 15 M 9 10 L 10.5 11 M 15 10 L 13.5 11')
  g=g.union(E(10,16,.55,.7)).union(E(14,16,.55,.7))
 elif name=='tiger':
  g=S('M 6 7 C 2 5 3 1 6 3 L 9 5 M 18 7 C 22 5 21 1 18 3 L 15 5 M 6 6 C 8 3 16 3 18 6 C 22 13 18 20 12 21 C 6 20 2 13 6 6 Z M 7 10 L 10 11 M 17 10 L 14 11 M 9 16 C 10 18 12 17 12 15 C 12 17 14 18 15 16 M 5 10 L 8 12 M 4 14 L 8 14 M 19 10 L 16 12 M 20 14 L 16 14 M 9 6 L 15 6 M 10 8 L 14 8 M 12 5 L 12 9',.5)
  g=g.union(solid('M 10.7 13 L 13.3 13 L 12 15 Z'))
 elif name=='rabbit':
  g=S('M 9 10 C 6 4 8 0 10 3 L 12 9 M 12 9 C 12 1 16 0 16 4 L 15 11 C 20 13 19 18 16 20 L 7 20 C 3 20 3 15 7 14 L 9 10 Z M 8 17 C 10 14 15 16 13 20 M 7 20 L 3 21 M 18 16 L 21 16')
  g=g.union(E(14.8,12.4,.5,.5)).union(S('M 9 4 L 10.5 9 M 14.5 4 L 13.5 9',.32))
 elif name=='dragon':
  g=S('M 8 8 L 5 3 L 10 5 L 12 1 L 13 6 L 17 5 L 16 8 L 21 10 L 19 13 L 14 13 C 11 16 19 16 18 20 C 17 24 6 23 5 19 C 3 15 7 12 8 8 M 10 14 C 6 18 10 21 14 20 M 16 9 L 18 10 M 20 12 L 22 15 L 17 15 M 13 8 L 15 9 M 8 9 L 4 10 L 7 12 M 6 13 L 2 14 L 5 16 M 5 17 L 2 19 L 6 20 M 14 16 L 12 18 M 13 22 L 11 20',.5)
  g=g.union(S('M 18 12 C 24 9 24 17 20 18',.32)).union(E(15.5,10.4,.45,.45))
 elif name=='goat':
  g=S('M 11 8 C 3 5 4 0 10 2 C 14 3 15 7 12 9 M 11 7 C 7 6 7 3 10 4 C 12 5 12 6 11 7 M 12 9 L 17 10 L 20 14 L 17 15 L 15 19 L 11 22 L 10 18 C 6 15 7 11 11 8 M 14 10 L 17 7 L 18 10 M 10 18 L 13 20 M 16 14 L 18 14')
  g=g.union(E(14.8,12.3,.45,.45))
 elif name=='monkey':
  g=S('M 5 8 C 1 5 0 13 5 14 M 19 8 C 23 5 24 13 19 14 M 5 11 C 4 3 9 1 12 4 C 15 1 20 3 19 11 C 21 16 18 21 12 21 C 6 21 3 16 5 11 Z M 12 8 C 8 5 6 10 8 13 C 4 18 9 20 12 18 C 15 20 20 18 16 13 C 18 10 16 5 12 8 Z M 9 15 C 11 17 13 17 15 15',.48)
  g=g.union(E(9.3,10.8,.5,.6)).union(E(14.7,10.8,.5,.6)).union(E(12,13.3,.7,.45))
 elif name=='rooster':
  g=S('M 13 8 C 11 4 12 1 14 3 C 15 0 17 2 17 4 C 21 3 20 7 18 8 L 22 10 L 18 12 C 18 18 15 20 10 19 C 5 18 5 13 8 11 C 5 7 2 4 2 8 C 0 8 2 14 6 15 M 8 12 C 4 8 4 3 6 6 L 10 10 M 10 13 C 15 10 17 15 12 17 M 10 19 L 9 23 L 6 23 M 14 19 L 15 23 L 18 23 M 17 12 C 20 16 16 16 16 13',.5)
  g=g.union(E(16.5,8.5,.45,.45))
 elif name=='dog':
  g=S('M 7 9 L 8 2 L 13 6 L 17 4 L 17 10 L 22 13 L 20 16 L 15 16 L 14 21 L 5 21 L 8 16 C 4 15 4 11 7 9 Z M 8 4 L 10 7 L 8 11 M 8 17 L 14 18 M 16 13 L 20 13',.5)
  g=g.union(E(15.5,10.8,.5,.5)).union(E(21,13.4,.6,.6))
 elif name=='pig':
  g=S('M 6 8 C 8 6 13 5 17 8 L 20 9 L 21 14 L 19 17 L 17 17 L 17 21 L 14 21 L 13 18 L 10 18 L 9 21 L 6 21 L 6 17 C 2 14 3 10 6 8 Z M 6 8 L 7 3 L 11 6 M 16 8 L 17 4 L 19 9 M 4 11 C 0 12 0 7 2 8 C 4 10 1 11 1 9 M 18 11 C 15 10 15 15 19 15',.5)
  g=g.union(E(18.5,12.7,.35,.6)).union(E(14.3,9.8,.45,.5))
 else:raise KeyError(name)
 # Drawings use y-down local coordinates, exactly as the cover SVG.
 return affinity.translate(affinity.scale(g,1.1,1.1,origin=(12,12)),6.5,4)


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
 holes=unary_union([Point(v).buffer(.4,quad_segs=24) for v in positions.values()])
 slots=[];printed=[];edges=sorted({tuple(sorted((a,b))) for chain in chains for a,b in zip(chain,chain[1:]) if a!=b})
 silk=unary_union([Point(v).buffer(1,quad_segs=32).difference(Point(v).buffer(.8,quad_segs=32)) for v in positions.values()])
 for a,b in edges:
  a1=np.array(positions[a]);b1=np.array(positions[b]);d=float(np.linalg.norm(b1-a1));u=(b1-a1)/d
  silk=silk.union(LineString([a1,b1]).buffer(.11,quad_segs=8))
  if d>=5.1:
   slot=LineString([a1+u*1.9,b1-u*1.9]).buffer(.5,quad_segs=16)
   # Avoid cutting through a nearby third star, intersecting other slots or
   # leaving isolated material. Crowded links retain their white print only.
   others=unary_union([Point(v).buffer(.9) for h,v in positions.items() if h not in (a,b)])
   if not slot.intersects(others) and not any(slot.distance(s)<.8 for s in slots):slots.append(slot);continue
  printed.append([a,b])
 aperture=unary_union([holes,*slots]);mask=aperture.buffer(.2,quad_segs=12)
 silk=silk.difference(mask.buffer(.16,quad_segs=12))
 return silk,mask,positions,slots,{'hip_ids':hips,'source_chains':chains,'edges':edges,'printed_only_edges':printed,
  'maximum_layout_adjustment_mm':float(np.linalg.norm(p-before,axis=1).max()),
  'minimum_star_spacing_mm':min(float(np.linalg.norm(p[i]-p[j])) for i in range(len(p)) for j in range(i)),
  'star_hole_diameter_mm':.8,'slot_width_mm':1.,'slot_end_inset_from_star_center_mm':1.9,
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
    silk=animal(name).union(label(name.upper(),32.1,1.6));mask=GeometryCollection();details={'original_vector_art':True,'minimum_nominal_stroke_mm':.32,'star_holes':0,'animal_mask_openings':0}
   clip=affinity.translate(OCT,18.5,18.5).buffer(-1.2)
   silk=silk.intersection(clip)
   assert silk.is_valid and not silk.is_empty and silk.intersection(mask).area<1e-8
   if not mask.is_empty:assert silk.distance(mask)>.149
   for kind,g,layer in [('silk',silk,3),('mask',mask,5)]:
    for i,p in enumerate(art.polygons(g)):
     add('FILL',{'partitionId':'','groupId':0,'netName':'','layerId':layer,'width':.2,'fillStyle':'SOLID','path':native_path(p,center),'locked':True,'zIndex':-1},f'{name}:{kind}:{i}')
   covers.append({'id':name,'name_zh':zh,'center_native_mm':center,'details':details,'silk_polygons':len(art.polygons(silk)),'mask_polygons':len(art.polygons(mask))})
   # Exterior view of entire PCB: SVG y increases downward.
   cx,cy=center[0]-18.5,100-center[1]-18.5
   svg_parts.append(f'<g transform="translate({cx},{cy})">'+svg_geometry(affinity.translate(OCT,18.5,18.5),'#147442')+svg_geometry(mask,'#c6ad78')+svg_geometry(silk,'#fafaf3')+'</g>')
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
 manifest['files']={p.relative_to(OUT).as_posix():{'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for folder in ('geometry','artwork','sources') for p in (OUT/folder).glob('*') if p.is_file()}
 write(OUT/'design-manifest.json',manifest)
 print(json.dumps({'panels':manifest['panels'],'cover_gap_mm':manifest['minimum_cover_to_cover_gap_mm']},ensure_ascii=False,indent=2))


if __name__=='__main__':generate()
