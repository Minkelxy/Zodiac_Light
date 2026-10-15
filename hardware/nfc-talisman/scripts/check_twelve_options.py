"""Read-only, standard-library verification of the four five-cover PCB exports."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import zipfile

S=importlib.util.spec_from_file_location('nfc_archive',Path(__file__).with_name('check_delivery.py'))
BASE=importlib.util.module_from_spec(S);S.loader.exec_module(BASE)
FOLDER='variants/twelve-options'
STAR_SET={'aries','taurus','gemini','cancer','leo','virgo','libra','scorpius','sagittarius','capricornus','aquarius','pisces'}
ANIMAL_SET={'rat','ox','tiger','rabbit','dragon','snake','horse','goat','monkey','rooster','dog','pig'}


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
 def archive():
  p=root/m['native_project']['path'];b=p.read_bytes();assert len(b)==m['native_project']['size'] and digest(b)==m['native_project']['sha256']
  with zipfile.ZipFile(p) as z:
   assert z.testzip() is None
   js=[n for n in z.namelist() if n.endswith('.epru')];assert len(js)==1
   docs=BASE._replay(z.read(js[0]).decode('utf-8-sig'))
  expected=set(m['existing'])|{b['uuid'] for b in m['boards']}
  assert {u for u,v in docs.items() if v['head']['docType']=='PCB'}==expected and len(expected)==9
  for uuid,ev in m['existing'].items():
   source=(root/ev['path']).read_bytes();assert digest(source)==ev['sha256']
   before=BASE._replay(source.decode())[uuid]['records'];after=docs[uuid]['records']
   assert BASE._design_records(before)==BASE._design_records(after),'Existing PCB geometry changed: '+uuid
   assert {k:v for k,v in before.items() if k[0]=='OBJ'}=={k:v for k,v in after.items() if k[0]=='OBJ'}
  state['docs']=docs;return 'Native CRC/SHA pass; 9 PCB documents present; previous 5 PCB designs and color objects retained'
 check('native-archive-and-existing-pcbs',archive)
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
