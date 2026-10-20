"""Read-only, standard-library verification of the four five-cover PCB exports."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import zipfile

S=importlib.util.spec_from_file_location('nfc_archive',Path(__file__).with_name('check_delivery.py'))
BASE=importlib.util.module_from_spec(S);S.loader.exec_module(BASE)
SS=importlib.util.spec_from_file_location('nfc_standard_archive',Path(__file__).with_name('check_standard_delivery.py'))
STANDARD=importlib.util.module_from_spec(SS);SS.loader.exec_module(STANDARD)
FOLDER='variants/twelve-options'
STAR_SET={'aries','taurus','gemini','cancer','leo','virgo','libra','scorpius','sagittarius','capricornus','aquarius','pisces'}
ANIMAL_SET={'rat','ox','tiger','rabbit','dragon','snake','horse','goat','monkey','rooster','dog','pig'}
TALISMAN_COLLECTION='hardware/nfc-talisman/artwork/reference-collection/talisman-single-ink-v1'
ANIMAL_SOURCE_ALIASES={'goat':'sheep'}


def digest(data):return hashlib.sha256(data).hexdigest()


def path_same(a,b,tol=.001):
 if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(path_same(x,y,tol) for x,y in zip(a,b))
 if isinstance(a,(int,float)):return isinstance(b,(int,float)) and abs(a-b)<=tol
 return a==b


def contour_same(a,b):
 def points(p):
  assert p[2]=='L'
  v=p[:2]+p[3:];r=[v[i:i+2] for i in range(0,len(v),2)]
  assert path_same(r[0],r[-1]);return r[:-1]
 a,b=points(a),points(b)
 if len(a)!=len(b):return False
 n=len(a)
 return any(all(path_same(a[i],b[(j+direction*i)%n]) for i in range(n)) for j in range(n) if path_same(a[0],b[j]) for direction in(1,-1))


def trace_paths(trace,center):
 """Map recorded cover-local trace rings to the native paths used for printing."""
 if trace.get('units')!='mm' or trace.get('coordinate_system')!='cover_top_left_x_right_y_down':
  raise ValueError('Unexpected talisman trace coordinate system')
 def ring(points):
  if not isinstance(points,list) or len(points)<3:
   raise ValueError('Talisman trace ring must have at least three points')
  if any(not isinstance(p,list) or len(p)!=2 or any(not isinstance(n,(float,int)) or not math.isfinite(n) for n in p) for p in points):
   raise ValueError('Invalid talisman trace coordinates')
  points=[[(center[0]+x-18.5)/.0254,(center[1]+18.5-y)/.0254] for x,y in points]
  if points[0]!=points[-1]:points.append(points[0])
  return points[0]+['L']+[n for p in points[1:] for n in p]
 polygons=trace.get('polygons')
 if not isinstance(polygons,list) or not polygons:
  raise ValueError('Talisman trace polygons are empty')
 return [[ring(p['exterior']),*[ring(h) for h in p['holes']]] for p in polygons]


def polygon_same(a,b):
 if len(a)!=len(b) or not contour_same(a[0],b[0]):return False
 remaining=list(b[1:])
 for expected in a[1:]:
  matches=[i for i,actual in enumerate(remaining) if contour_same(expected,actual)]
  if not matches:return False
  remaining.pop(matches[0])
 return not remaining


def validate(root):
 root=Path(root).resolve()
 if (root/'hardware/nfc-talisman').exists():root=root/'hardware/nfc-talisman'
 out=root/FOLDER;checks=[];errors=[]
 def check(name,fn):
  try:detail=fn();checks.append({'id':'twelve:'+name,'passed':True,'detail':detail})
  except Exception as e:errors.append(str(e));checks.append({'id':'twelve:'+name,'passed':False,'detail':str(e)})
 def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
 state={}
 def manifest():
  m=load(out/'export-manifest.json');d=load(out/'design-manifest.json')
  assert m['status']=='four_five_cover_pcbs_saved_and_exported'
  assert m['design_manifest_sha256']==digest((out/'design-manifest.json').read_bytes())
  assert len(m['boards'])==len(d['panels'])==4
  assert {b['key']:b['uuid'] for b in m['boards']}==STANDARD.TWELVE_UUIDS,'Twelve-option PCB identities changed'
  assert set(m['existing'])==STANDARD.ORIGINAL_FIVE,'Incorrect original five-PCB scope'
  stars=[n for p in d['panels'] if p['key'].startswith('constellations') for n in p['covers']]
  animals=[n for p in d['panels'] if p['key'].startswith('zodiac') for n in p['covers']]
  assert len(set(stars))==len(stars)==10 and set(stars)|set(d['existing_constellations'])==STAR_SET
  assert len(set(animals))==len(animals)==10 and set(animals)|set(d['existing_zodiac'])==ANIMAL_SET
  assert d['panel_mm']==[100,100] and d['cover_af_mm']==37 and d['process']['color_printing'] is False
  assert 'passive' in m['role'] and m['release_status'].startswith('HOLD')
  for n,v in d['files'].items():
   b=(out/n).read_bytes();assert len(b)==v['size'] and digest(b)==v['sha256'],n
  state.update(m=m,d=d);return '4 x 100 mm PCBs, 5 AF37 covers each; 12 unique constellations and 12 unique zodiac animals including existing options'
 check('coverage-and-source-hashes',manifest)
 if not state:return {'status':'failed','checks':checks,'errors':errors}
 m,d=state['m'],state['d']
 def talisman_sources():
  project=root.parents[1]
  collection_path=project/TALISMAN_COLLECTION/'manifest.json'
  collection=load(collection_path);items={a['id']:a for a in collection['files']}
  seen=[]
  def source(path_name,expected,label):
   if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):
    raise ValueError('Invalid '+label+' SHA-256')
   path=BASE._relative(project,path_name)
   if digest(path.read_bytes())!=expected:raise ValueError(label+' bytes changed: '+path_name)
   return path
  for panel in d['panels']:
   if not panel['key'].startswith('zodiac'):continue
   geometry=load(out/panel['geometry'])
   for cover in geometry['covers']:
    animal=cover['id'];details=cover['details'];canonical=ANIMAL_SOURCE_ALIASES.get(animal,animal)
    expected=items[canonical]
    if details.get('artwork_kind')!='project_talisman_single_ink_trace' or details.get('original_vector_art') is not False:
     raise ValueError('Zodiac cover must trace an existing project talisman: '+animal)
    if details.get('requested_animal_id')!=animal or details.get('source_id')!=canonical or details.get('source_collection')!='talisman-single-ink-v1':
     raise ValueError('Incorrect talisman source mapping: '+animal)
    if details.get('source_manifest')!=(collection_path.relative_to(project).as_posix()):
     raise ValueError('Unexpected talisman source manifest: '+animal)
    source(details['source_manifest'],details['source_manifest_sha256'],'Talisman collection manifest')
    reference_root=project/'hardware/nfc-talisman/artwork/reference-collection'
    for field,record_path,record_digest in [
        ('source_png','path','output_sha256'),
        ('source_candidate_png','candidate_path','candidate_sha256'),
        ('source_original_reference','source_path','source_sha256')]:
     path=(reference_root/expected[record_path]).resolve()
     if details.get(field)!=path.relative_to(project).as_posix() or details.get(field+'_sha256')!=expected[record_digest]:
      raise ValueError('Talisman provenance differs from the source collection: '+animal+' '+field)
     source(details[field],details[field+'_sha256'],field)
    if not re.fullmatch('[0-9a-f]{64}',details.get('source_alpha_sha256','')):
     raise ValueError('Missing alpha fingerprint: '+animal)
    if any(details.get('source_'+field)!=expected[field] for field in ('visual_status','visual_note')):
     raise ValueError('Original visual review status was not retained: '+animal)
    if details.get('trace',{}).get('alpha_threshold')!=128:
     raise ValueError('Unexpected talisman alpha threshold: '+animal)
    trace=details['trace_geometry']
    encoded=json.dumps(trace,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
    if digest(encoded)!=details.get('geometry_sha256'):
     raise ValueError('Recorded talisman trace fingerprint differs: '+animal)
    available=[entry['body']['path'] for entry in geometry['primitives']
               if entry['head']['type']=='FILL' and entry['body']['layerId']==3
               and entry['logical_id'].startswith(animal+':silk:')]
    for expected_path in trace_paths(trace,cover['center_native_mm']):
     matches=[i for i,p in enumerate(available) if polygon_same(expected_path,p)]
     if not matches:raise ValueError('Source talisman contour missing from native import geometry: '+animal)
     available.pop(matches[0])
    if details.get('english_label_on_pcb') is not False or available:
     raise ValueError('Zodiac silk must contain only the traced animal and its separate border, without English labels: '+animal)
    if details.get('star_holes')!=0 or details.get('animal_mask_openings')!=0 or cover.get('mask_polygons')!=0:
     raise ValueError('Animal cover must not add holes or soldermask openings: '+animal)
    seen.append(animal)
   if any(e['head']['type']=='FILL' and e['body']['layerId']==5 for e in geometry['primitives']):
    raise ValueError('Zodiac panel contains unexpected soldermask artwork')
  if len(seen)!=10 or set(seen)!=ANIMAL_SET-{'horse','snake'}:
   raise ValueError('Expected all ten added zodiac talisman sources exactly once')
  return 'Ten existing talisman PNG/candidate/reference SHA chains and visual statuses match; traced contours are bound to printable geometry; goat maps to sheep'
 check('talisman-artwork-provenance',talisman_sources)
 def border_artwork():
  has_border='border_generator' in d
  if not has_border:
   assert not any('border' in c['details'] for p in d['panels'] for c in load(out/p['geometry'])['covers']),'Border geometry lacks its generator source binding'
   return 'Historical cover geometry has no uniform border revision'
  STANDARD._check_border_generator(root,d['border_generator'])
  count=0
  for panel in d['panels']:
   geometry=load(out/panel['geometry'])
   for cover in geometry['covers']:
    entries=[e for e in geometry['primitives'] if e['logical_id'].startswith(cover['id']+':border:')]
    assert all(e['head']['type']=='FILL' and e['body']['layerId']==3 and e['body'].get('netName','')=='' and e['body']['fillStyle'] in(0,'SOLID') for e in entries),'Border must use separate non-net Top-silk fills'
    STANDARD._check_border(cover['details']['border'],[e['body']['path'] for e in entries],cover['center_native_mm'])
    count+=1
  assert count==20,'Uniform border is missing from an added cover'
  STANDARD._check_border_audit(root)
  return 'All 20 added covers use frozen-source separate Top-silk border contours; full 24-face independent clearance/physical audit matches current source hashes'
 check('uniform-border-source-and-contours',border_artwork)
 def slot_optimization():
  project=root.parents[1];report=load(out/'sources/slot-optimization.json')
  if report.get('schema_version')!=1 or report.get('status')!='passed':
   raise ValueError('Slot optimization report is not a passed schema 1 report')
  module='hardware/nfc-talisman/scripts/constellation_slot_layout.py'
  if report.get('module')!=module or digest((project/module).read_bytes())!=report.get('module_sha256'):
   raise ValueError('Slot optimization module differs from the frozen report')
  required_sources={f'hardware/nfc-talisman/{FOLDER}/sources/{name}' for name in ('stellarium-modern-index.json','hipparcos-zodiac.tsv')}
  if set(report.get('source_sha256',{}))!=required_sources:
   raise ValueError('Slot optimization must bind both frozen astronomical inputs')
  for name,expected in report['source_sha256'].items():
   if digest(BASE._relative(project,name).read_bytes())!=expected:
    raise ValueError('Slot optimization source changed: '+name)
  physical=load(out/'slot-layout-geometry-audit.json')
  if physical.get('status')!='passed' or physical.get('errors') or physical.get('design_manifest_sha256')!=digest((out/'design-manifest.json').read_bytes()) or physical.get('slot_optimization_report_sha256')!=digest((out/'sources/slot-optimization.json').read_bytes()):
   raise ValueError('Independent physical slot audit is stale or failed')
  expected_names=STAR_SET-{'sagittarius','leo'}
  if set(report['covers'])!=expected_names:raise ValueError('Expected all ten constellation slot records')
  total_hips=total_edges=before_slots=after_slots=0;before_length=after_length=0.
  for panel in d['panels']:
   if not panel['key'].startswith('constellations'):continue
   geometry=load(out/panel['geometry'])
   for cover in geometry['covers']:
    name=cover['id'];details=cover['details'];record=report['covers'][name];after=record['after'];layout=details['slot_layout']
    if any(layout.get(k)!=v for k,v in after.items()):
     raise ValueError('Slot report differs from final cover metadata: '+name)
    hips=record['hip_ids'];edges={tuple(sorted(e)) for e in record['logical_edges']}
    if hips!=details['hip_ids'] or edges!={tuple(sorted(e)) for e in details['edges']} or record['source_chains']!=details['source_chains']:
     raise ValueError('Constellation source topology changed: '+name)
    if after['hip_count']!=len(hips) or after['logical_edge_count']!=len(edges) or len(edges)!=len(record['logical_edges']):
     raise ValueError('Incorrect constellation node/edge counts: '+name)
    pads=[e for e in geometry['primitives'] if e['head']['type']=='PAD' and e['logical_id'].startswith(name+'_HIP')]
    slots=[e for e in geometry['primitives'] if e['head']['type']=='POLY' and e['logical_id'].startswith(name+':light-slot:')]
    if {e['logical_id'] for e in pads}!={f'{name}_HIP{hip}' for hip in hips} or len(pads)!=after['hip_count'] or len(slots)!=after['physical_slot_count']:
     raise ValueError('Physical star/slot count differs from optimized metadata: '+name)
    for pad in pads:
     hip=pad['logical_id'].split('_HIP',1)[1];x,y=layout['star_positions_final_mm'][hip];cx,cy=cover['center_native_mm'];body=pad['body']
     if abs(body['centerX']-(cx+x-18.5)/.0254)>.001 or abs(body['centerY']-(cy+18.5-y)/.0254)>.001:
      raise ValueError('Optimized star position differs from native import geometry: '+name+' '+hip)
    printed={tuple(sorted(e)) for e in layout['printed_only_edges']}
    routed={tuple(sorted(e['edge'])) for e in layout['slots']}
    if printed|routed!=edges or printed&routed or len(printed)!=after['printed_only_edge_count'] or len(routed)!=after['slotted_edge_count'] or len(layout['slots'])!=len(slots):
     raise ValueError('Printed/routed edge accounting differs: '+name)
    if not after['fr4_single_connected_component'] or not after['all_apertures_inside_board']:
     raise ValueError('Optimized cover is disconnected or has external apertures: '+name)
    for field,threshold in [('minimum_star_to_slot_material_mm',1.),('minimum_slot_to_slot_material_mm',.8),('minimum_slot_to_outer_edge_material_mm',1.),('minimum_slot_overall_length_mm',1.5)]:
     value=after[field];allow_none=len(slots)<(2 if field=='minimum_slot_to_slot_material_mm' else 1)
     if value is None and allow_none:continue
     if not isinstance(value,(int,float)) or not math.isfinite(value) or value<threshold:
      raise ValueError('Optimized material/slot threshold failed: '+name+' '+field)
    total_hips+=len(hips);total_edges+=len(edges);before_slots+=record['before']['physical_slot_count'];after_slots+=len(slots)
    before_length+=record['before']['total_centerline_length_mm'];after_length+=after['total_centerline_length_mm']
  summary=report['summary']
  if total_hips!=113 or total_edges!=109 or summary['hip_nodes']!=total_hips or summary['logical_edges']!=total_edges or summary['before_slots']!=before_slots or summary['after_slots']!=after_slots:
   raise ValueError('Global slot/node/edge totals differ from the per-cover records')
  if abs(summary['before_centerline_mm']-before_length)>1e-6 or abs(summary['after_centerline_mm']-after_length)>1e-6:
   raise ValueError('Global slot centerline lengths differ from the per-cover records')
  return f'Frozen module/source hashes, independent physical audit and 10 final layouts match; {total_hips} HIP nodes/{total_edges} logical edges, physical slots {before_slots} -> {after_slots}; recorded material minima and connected substrates pass'
 check('slot-optimization-source-and-counts',slot_optimization)
 def archive():
  p=root/m['native_project']['path'];b=p.read_bytes();assert len(b)==m['native_project']['size'] and digest(b)==m['native_project']['sha256']
  with zipfile.ZipFile(p) as z:
   assert z.testzip() is None
   js=[n for n in z.namelist() if n.endswith('.epru')];assert len(js)==1
   docs=BASE._replay(z.read(js[0]).decode('utf-8-sig'))
  expected_scope=STANDARD.shared_pcb_scope(root)
  assert {u for u,v in docs.items() if v['head']['docType']=='PCB'}==expected_scope
  ordinary_manifest=load(root/'variants/standard-green-white/export-manifest.json')
  revised='archive_scope' in ordinary_manifest
  assert revised or not any('revision_before' in ev for ev in m['existing'].values()),'Silk revisions require the explicitly shared nine-PCB scope'
  ordinary=None
  if revised:
   ordinary=ordinary_manifest
   scope=ordinary['archive_scope']['pcb_uuids']
   assert len(scope)==len(expected_scope) and set(scope)==expected_scope,'Incorrect shared native archive scope'
   assert all(ordinary['native_project'][key]==m['native_project'][key] for key in ('path','size','sha256')),'Standard/twelve native archives differ'
   ordinary={b['uuid']:b for b in ordinary['boards']}
   assert set(ordinary)==set(STANDARD.STANDARD_UUIDS.values()),'Incorrect ordinary PCB revision set'
  for uuid,ev in m['existing'].items():
   source=BASE._relative(root,ev['path']).read_bytes();assert digest(source)==ev['sha256']
   before=BASE._replay(source.decode())[uuid]['records'];after=docs[uuid]['records']
   assert BASE._design_records(before)==BASE._design_records(after),'Existing current PCB source differs from archive: '+uuid
   assert {k:v for k,v in before.items() if k[0]=='OBJ'}=={k:v for k,v in after.items() if k[0]=='OBJ'}
   if revised and uuid in STANDARD.STANDARD_UUIDS.values():
    board=ordinary[uuid]
    assert ev['uuid']==uuid and ev['path']==board['source'] and ev['sha256']==board['source_sha256'],'Stale ordinary source binding: '+uuid
    assert ev['retention_policy']=='owned_top_silk_revision_physical_and_mask_preserved','Unexpected ordinary retention policy'
    assert ev['revision_before']==board['border_revision']['before'] and board['border_revision']['status']=='saved_reopened','Ordinary revision evidence differs'
    STANDARD._check_silk_revision(root,uuid,ev['revision_before'],after,board['created'])
   else:
    assert 'revision_before' not in ev,'Only the two ordinary PCBs may revise owned Top silk'
  state['docs']=docs;state['standard_revised']=revised
  return f'Native CRC/SHA pass; exact {len(expected_scope)} PCB documents present; original 3 designs/color objects retained; declared ordinary silk/mousebite revisions verified'
 check('native-archive-and-existing-pcbs',archive)
 if state.get('standard_revised'):
  def standard_delivery():
   result=STANDARD.validate(root)
   assert result['status']=='passed','Linked ordinary delivery failed: '+'; '.join(result['errors'])
   return 'Shared ordinary delivery passes its full source/artwork/Gerber, historical-color and owned-silk revision checks'
  check('shared-standard-delivery',standard_delivery)
 for board in m['boards']:
  def native_board(board=board):
   key,uuid=board['key'],board['uuid'];g=load(out/board['geometry']);p=root/board['source']['path'];raw=p.read_bytes()
   assert digest(raw)==board['source']['sha256']
   assert board['name']==g['name'] and board['status']=='saved_reopened' and board['cover_count']==5 and board['drc']==[]
   log=load(out/'eda/logs'/f'drc-{key}.json');assert log['success'] and log['result']['drc']==[]
   source=BASE._replay(raw.decode())[uuid]['records'];archived=state['docs'][uuid]['records']
   assert BASE._design_records(source)==BASE._design_records(archived)
   expected={(e['head']['type'],e['head']['id']):e['body'] for e in g['primitives']}
   found={k:v for k,v in source.items() if k[0] in {'FILL','PAD','POLY'}}
   assert set(found)==set(expected)
   for k,a in expected.items():
    b=found[k];assert a['layerId']==b['layerId'] and b.get('netName','')==''
    if k[0]=='FILL':assert path_same(a['path'],b['path']) and b['layerId'] in(3,5) and b['fillStyle'] in(0,'SOLID')
    elif k[0]=='POLY':assert b['layerId']==11 and contour_same(a['path'],b['path'])
    else:assert not b['plated'] and all(abs(a[f]-b[f])<=.001 for f in ('centerX','centerY')) and abs(a['hole']['width']-b['hole']['width'])<=.001
   assert not any(k[0] in {'COMPONENT','OBJ','LINE','ARC','POUR','VIA'} for k in source)
   assert len(g['covers'])==5
   assert len([e for e in g['primitives'] if '_MB' in e['logical_id']])==100
   assert next(e['body']['path'] for e in g['primitives'] if e['logical_id']=='panel-frame:0')[:2]==[3937.007874,0.0]
   return f"{len(found)} owned primitives match final native source and archive; no decorative copper or image objects; saved/reopened DRC 0"
  check(board['key']+':native',native_board)
  def gerber(board=board):
   ev=board['gerber'];p=root/ev['path'];raw=p.read_bytes();assert digest(raw)==ev['sha256'] and len(raw)==ev['size']
   with zipfile.ZipFile(p) as z:
    assert z.testzip() is None and set(z.namelist())==set(ev['members'])
    assert not any(n.startswith('Fabrication_Colorful') for n in z.namelist())
    for n,v in ev['members'].items():
     b=z.read(n);assert digest(b)==v['sha256'] and len(b)==v['size']
    assert {'Gerber_BoardOutlineLayer.GKO','Gerber_TopSilkscreenLayer.GTO','Drill_NPTH_Through.DRL'}<=set(z.namelist())
    npth=z.read('Drill_NPTH_Through.DRL').decode()
    points=re.findall(r'^X[-\d.]+Y[-\d.]+$',npth,re.M)
    expected=sum(e['head']['type']=='PAD' for e in load(out/board['geometry'])['primitives'])
    assert len(points)==expected,f'NPTH count {len(points)} vs {expected}'
   return f'Ordinary ZIP CRC/member hashes pass; {expected} NPTH coordinates match expected hole count'
  check(board['key']+':gerber',gerber)
 def regions():
  r=load(out/'gerber-geometry-audit.json');assert r['status']=='passed'
  assert r['design_manifest_sha256']==digest((out/'design-manifest.json').read_bytes())
  for b in m['boards']:
   assert r['panels'][b['key']]['gerber_sha256']==b['gerber']['sha256']
  return 'Actual exported silk/mask regions and connected substrate independently checked; source-bound audit hashes match'
 check('gerber-regions-and-mechanics',regions)
 return {'status':'failed' if errors else 'passed','read_only':True,'checks':checks,'errors':errors,'checks_run':len(checks),'release_ready':False,
  'release_status':m['release_status'],'limitations':['Passive covers only; existing NFC core reused.','Supplier CAM, breakaway force, optical performance and stacking/NFC tests remain pending.','Mixed-design panel pricing and board thickness require supplier/order confirmation.']}


if __name__=='__main__':
 r=validate(Path(__file__).resolve().parents[1]);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r['status']=='passed' else 1)
