"""Check actual exported ordinary Gerber artwork and connected panel material."""
from pathlib import Path
import hashlib
import json
import re
import zipfile
from shapely.geometry import GeometryCollection, Point, Polygon, box
from shapely.ops import unary_union
import audit_standard_gerber_artwork as gerber

HW=Path(__file__).resolve().parents[1]
OUT=HW/'variants/twelve-options'


def outline_contours(raw):
 """Read the exporter's closed G01 router contours, without buffering stroke."""
 text=raw.decode('utf-8-sig')
 assert '%FSLAX36Y36*%' in text and '%MOMM*%' in text
 assert not re.search(r'^G0[23]',text,re.M),'Unexpected arc interpolation'
 contours=[];points=[]
 for line in text.splitlines():
  m=re.fullmatch(r'G01X(-?\d+)Y(-?\d+)D0([12])\*',line.strip())
  if not m:continue
  x,y=int(m[1])/1e6,int(m[2])/1e6
  if m[3]=='2':
   if points:
    assert points[0]==points[-1] and len(points)>=4
    contours.append(Polygon(points))
   points=[(x,y)]
  else:
   assert points,'Router line without initial move'
   points.append((x,y))
 if points:
  assert points[0]==points[-1] and len(points)>=4
  contours.append(Polygon(points))
 assert contours and all(p.is_valid for p in contours)
 return contours


def shape(path,complex=False):
 def ring(p):
  assert p[2]=='L';v=p[:2]+p[3:]
  return [(v[i]*.0254,v[i+1]*.0254) for i in range(0,len(v),2)]
 if complex:return Polygon(ring(path[0]),[ring(p) for p in path[1:]])
 return Polygon(ring(path))


def audit():
 manifest=json.loads((OUT/'export-manifest.json').read_text(encoding='utf-8'))
 result={'status':'passed','coordinate_tolerance_mm':.00001,'design_manifest_sha256':hashlib.sha256((OUT/'design-manifest.json').read_bytes()).hexdigest(),'panels':{},'errors':[]}
 for board in manifest['boards']:
  key=board['key'];record={'gerber_sha256':board['gerber']['sha256']}
  try:
   g=json.loads((OUT/board['geometry']).read_text(encoding='utf-8'))
   expected={layer:unary_union([shape(e['body']['path'],True) for e in g['primitives'] if e['head']['type']=='FILL' and e['body']['layerId']==layer]) for layer in(3,5)}
   actual={}
   with zipfile.ZipFile(HW/board['gerber']['path']) as z:
    assert z.testzip() is None
    actual_routes=outline_contours(z.read('Gerber_BoardOutlineLayer.GKO'))
    expected_routes=[(e,shape(e['body']['path'])) for e in g['primitives'] if e['head']['type']=='POLY']
    assert len(actual_routes)==len(expected_routes),'Router contour count changed'
    unmatched=actual_routes.copy();matched_routes={};route_error=0.
    for entry,expected_route in expected_routes:
     selected=min(unmatched,key=lambda p:expected_route.boundary.hausdorff_distance(p.boundary))
     error=expected_route.boundary.hausdorff_distance(selected.boundary)
     assert error<.00001 and expected_route.symmetric_difference(selected).area<expected_route.length*.00001,'Gerber router contour differs'
     route_error=max(route_error,error);matched_routes[entry['logical_id']]=selected
     unmatched.remove(selected)
    record['router_contours']={'count':len(actual_routes),'maximum_boundary_error_mm':route_error,'all_expected_contours_matched':True}
    for layer,file in[(3,'Gerber_TopSilkscreenLayer.GTO'),(5,'Gerber_TopSolderMaskLayer.GTS')]:
     regions=gerber.parse_regions(z.read(file));actual[layer]=GeometryCollection()
     for r in regions:
      if r['section']=='PolygonModel':actual[layer]=actual[layer].union(r['geometry']) if r['polarity']=='D' else actual[layer].difference(r['geometry'])
     a,b=expected[layer],actual[layer]
     if a.is_empty:assert b.is_empty;hd=None
     else:
      hd=a.boundary.hausdorff_distance(b.boundary)
      assert hd<.00001 and a.symmetric_difference(b).area<a.length*.00001
     record['silk' if layer==3 else 'mask']={'boundary_error_mm':hd,'area_mm2':b.area,'negative_holes':gerber.count_holes(b),'nominal_width_has_no_extra_stroke':True}
    # Excellon numeric output uses metric, explicit decimals in this client.
    text=z.read('Drill_NPTH_Through.DRL').decode();tool=None;diameters={};holes=[]
    for line in text.splitlines():
     line=line.strip();m=re.fullmatch(r'T(\d+)C([\d.]+)',line)
     if m:diameters[m[1]]=float(m[2]);continue
     m=re.fullmatch(r'T(\d+)',line)
     if m:tool=m[1];continue
     m=re.fullmatch(r'X(-?[\d.]+)Y(-?[\d.]+)',line)
     if m:holes.append((float(m[1]),float(m[2]),diameters[tool]))
    pad_points=[(e['body']['centerX']*.0254,e['body']['centerY']*.0254,e['body']['hole']['width']*.0254) for e in g['primitives'] if e['head']['type']=='PAD']
    assert len(holes)==len(pad_points)
    # The exporter may output leading-zero suppressed fixed coordinates;
    # determine the scale from the frame extent, then require every drill.
    xy_scale=1e6 if max(abs(n) for h in holes for n in h[:2])>101 else 1
    holes=[(x/xy_scale,y/xy_scale,d) for x,y,d in holes]
    for p in pad_points:
     assert any(max(abs(a-b) for a,b in zip(p,h))<.00002 for h in holes),'Excellon position/diameter differs'
   cuts=[p for logical,p in matched_routes.items() if not logical.startswith('panel-frame')]
   cuts.extend(Point(x,y).buffer(d/2,quad_segs=24) for x,y,d in holes)
   slots=[p for logical,p in matched_routes.items() if ':light-slot:' in logical]
   if slots:
    drilled=[Point(x,y).buffer(d/2,quad_segs=32) for x,y,d in holes]
    star_slot=min(s.distance(h) for s in slots for h in drilled)
    slot_slot=min(a.distance(b) for i,a in enumerate(slots) for b in slots[i+1:])
    assert star_slot>=1.-.00001 and slot_slot>=.8-.00001,'Exported light slots violate material webs'
    record['slot_material']={'actual_slot_count':len(slots),'minimum_slot_to_any_npth_mm':star_slot,'minimum_slot_to_slot_mm':slot_slot,'required_hole_web_mm':1.,'required_slot_web_mm':.8}
   substrate=box(0,0,100,100).difference(unary_union(cuts))
   assert substrate.is_valid and substrate.geom_type=='Polygon','Floating material island or broken panel connection'
   gap=None if actual[5].is_empty else actual[3].distance(actual[5])
   assert gap is None or gap>=.15
   record.update(status='passed',connected_substrate=True,substrate_area_mm2=substrate.area,actual_silk_mask_gap_mm=gap,npth_positions_and_diameters_verified=len(pad_points),cover_count=5)
  except Exception as e:record.update(status='failed',error=str(e));result['errors'].append(key+': '+str(e))
  result['panels'][key]=record
 if result['errors']:result['status']='failed'
 result['limitations']=['Ideal geometry and export consistency only. Router corner treatment, mousebite breakout force, laminate thickness and optical/stacking acceptance require supplier CAM and samples.']
 (OUT/'gerber-geometry-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2));return result


if __name__=='__main__':raise SystemExit(0 if audit()['status']=='passed' else 1)
