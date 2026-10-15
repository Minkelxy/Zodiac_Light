"""Create/apply/export the four additional passive cover PCBs in live EasyEDA.

prepare creates blank documents; name them through the document-tree UI before
apply. Existing documents are snapshotted and compared again before export.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import build_twelve_option_panels as design
import create_standard_layer_pcbs as bridge

HW=Path(__file__).resolve().parents[1]
OUT=HW/'variants/twelve-options'
bridge.OUT=OUT
SPEC=importlib.util.spec_from_file_location('delivery_base',Path(__file__).with_name('check_delivery.py'))
BASE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(BASE)


def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(uuid,name):
 p,r=bridge.snapshot_source(uuid,name,f'eda/native/{name}.jsonl')
 return {'path':p.relative_to(HW).as_posix(),'sha256':digest(p),'uuid':uuid},r


def records(text,uuid):return BASE._replay(text)[uuid]['records']


def prepare():
 state_path=OUT/'pcb-state.json'
 if state_path.exists():raise ValueError('Existing prepared state: do not duplicate documents')
 existing=bridge.execute('return await eda.dmt_Pcb.getAllPcbsInfo();','before-catalog')
 if len(existing)!=5:raise ValueError('Expected the original core, two colored and two ordinary PCBs')
 state={'project':bridge.PROJECT,'role':'passive interchangeable covers; reuse existing NFC core','existing':{},'boards':[]}
 for item in existing:
  evidence,r=snapshot(item['uuid'],'before-'+item['uuid']);state['existing'][item['uuid']]=evidence
 write(state_path,state)
 for key,name in design.NAMES.items():
  r=bridge.execute("const uuid=await eda.dmt_Pcb.createPcb();if(!uuid)throw Error('PCB creation failed');await new Promise(r=>setTimeout(r,1400));return {uuid};",'create-'+key)
  board={'key':key,'uuid':r['uuid'],'requested_name':name,'status':'blank_created'}
  state['boards'].append(board);write(state_path,state)
  evidence,r=snapshot(board['uuid'],'blank-'+key);board['blank_source']=evidence;board['name']=r['info']['name'];write(state_path,state)
 print(json.dumps(state['boards'],ensure_ascii=False,indent=2))


def verify_board(source,uuid,geometry):
 actual=records(source,uuid)
 kinds={'FILL','PAD','POLY'}
 owned={(r['head']['type'],r['head']['id']):r['body'] for r in geometry['primitives']}
 found={k:v for k,v in actual.items() if k[0] in kinds}
 if set(found)!=set(owned):raise ValueError('Generated primitives did not persist or unexpected geometry exists')
 for key,before in owned.items():
  after=found[key]
  if after['layerId']!=before['layerId'] or after.get('netName','')!='':raise ValueError('Wrong manufacturing layer or unexpected copper net')
  if key[0] in ('FILL','POLY'):
   if key[0]=='FILL':
    if not bridge.same_path(before['path'],after['path']):raise ValueError('Artwork path mismatch')
   else:
    # The client reverses closed routing contours to its canonical winding.
    # Compare the whole closed boundary, including rounded router corners.
    from shapely.geometry import Polygon
    def contour(path):
     v=path[:2]+path[3:]
     return Polygon([(v[i],v[i+1]) for i in range(0,len(v),2)])
    a,b=contour(before['path']),contour(after['path'])
    if not b.is_valid or a.boundary.hausdorff_distance(b.boundary)>.001 or a.symmetric_difference(b).area>a.length*.001:raise ValueError('Routing boundary changed')
    if abs(before['width']-after['width'])>.001:raise ValueError('Routing width changed')
   if key[0]=='FILL' and after['fillStyle'] not in(0,'SOLID'):raise ValueError('Not a solid ordinary fill')
  else:
   for field in ('centerX','centerY'):
    if abs(before[field]-after[field])>.001:raise ValueError('Hole location changed')
   if after['plated'] or abs(before['hole']['width']-after['hole']['width'])>.001:raise ValueError('NPTH diameter/plating changed')
 if any(k[0] in {'COMPONENT','OBJ','VIA','LINE','POUR'} for k in actual):raise ValueError('Passive cover PCB contains unexpected electrical/image primitives')


def apply():
 path=OUT/'pcb-state.json';state=json.loads(path.read_text(encoding='utf-8'))
 for board in state['boards']:
  if board['status']=='saved_reopened':continue
  if board['status'] not in ('blank_created','revision_pending'):raise ValueError('This board has already been applied')
  key,uuid=board['key'],board['uuid'];geometry=json.loads((OUT/'geometry'/f'{key}.json').read_text(encoding='utf-8'))
  baseline=(HW/board['blank_source']['path']).read_text(encoding='utf-8')
  info=bridge.execute(bridge.active(uuid)+f"return await eda.dmt_Pcb.getPcbInfo({json.dumps(uuid)});",'name-check-'+key)
  if info['name']!=board['requested_name']:raise ValueError('Name the new PCB in the UI: '+board['requested_name'])
  if any(h['type'] in('PAD','POLY','FILL','COMPONENT','OBJ') for h,b in bridge.rows(baseline)):raise ValueError('Blank PCB is not empty')
  original=[]
  for h,b in bridge.rows(baseline):
   if h['type']=='SILK_OPTS':b.update(defaultColor='#FFFFFF',baseColor='#147442')
   if h['type']=='D3_ATTRIBUTE':b.update(boardColor='green',silkTechnology='standardSilk')
   original.append(json.dumps(h,separators=(',',':'))+'||'+json.dumps(b,separators=(',',':'))+'|')
  for entry in geometry['primitives']:
   original.append(json.dumps(entry['head'],separators=(',',':'))+'||'+json.dumps(entry['body'],separators=(',',':'))+'|')
  source='\n'.join(original)+'\n'
  bridge.execute(bridge.active(uuid)+f"if(!await eda.sys_FileManager.setDocumentSource({json.dumps(source)}))throw Error('Cover import failed');return {{imported:true}};",'apply-'+key)
  bridge.fresh_snapshot(uuid,'stable-'+key,lambda text:verify_board(text,uuid,geometry))
  bridge.execute(bridge.active(uuid)+"if(!await eda.pcb_Document.save())throw Error('Save failed');if(!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Close failed');return {saved:true,closed:true};",'save-close-'+key)
  evidence,r=snapshot(uuid,key+'-source');verify_board(r['source'],uuid,geometry)
  board.update(status='saved_reopened',name=r['info']['name'],source=evidence,geometry=f'geometry/{key}.json',cover_count=5)
  write(path,state)
 print(json.dumps({'status':'four_cover_panels_saved_reopened','boards':[{'name':b['name'],'uuid':b['uuid']} for b in state['boards']]},indent=2))


def export():
 state_path=OUT/'pcb-state.json';state=json.loads(state_path.read_text(encoding='utf-8'))
 for board in state['boards']:
  if board['status']!='saved_reopened':raise ValueError('Unsaved cover PCB')
  key,uuid=board['key'],board['uuid']
  r=bridge.execute(bridge.active(uuid)+"const drc=await eda.pcb_Drc.check(true,false,true);return {drc};",'drc-'+key)
  board['drc']=r['drc'];write(state_path,state)
  if board['drc']!=[]:raise ValueError(key+' has DRC findings')
  code=bridge.active(uuid)+bridge.ENCODE+f"const f=await eda.pcb_ManufactureData.getGerberFile({json.dumps(key)},false,'mm',{{integerNumber:3,decimalNumber:6}},{{metallicDrillingInformation:true,nonMetallicDrillingInformation:true,drillTable:true,flyingProbeTestingFile:false}});if(!f?.size)throw Error('No Gerber file');return {{size:f.size,base64:encoded(new Uint8Array(await f.arrayBuffer()))}};"
  r=bridge.execute(code,'gerber-'+key);p=OUT/'manufacturing-draft'/f'{key}-green-white-gerber.zip';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(r['base64']))
  with zipfile.ZipFile(p) as z:
   if z.testzip():raise ValueError('Gerber CRC failed')
   if any(n.startswith('Fabrication_Colorful') for n in z.namelist()):raise ValueError('Unexpected color-print fabrication files')
   members={n:{'size':len(z.read(n)),'sha256':hashlib.sha256(z.read(n)).hexdigest()} for n in z.namelist()}
  board['gerber']={'path':p.relative_to(HW).as_posix(),'size':p.stat().st_size,'sha256':digest(p),'members':members}
  write(state_path,state)
 for uuid,before in state['existing'].items():
  baseline=(HW/before['path']).read_text(encoding='utf-8');r=bridge.execute(bridge.active(uuid)+'return {source:await eda.sys_FileManager.getDocumentSource()};','retained-'+uuid)
  a=records(baseline,uuid);b=records(r['source'],uuid)
  if BASE._design_records(a)!=BASE._design_records(b) or {k:v for k,v in a.items() if k[0]=='OBJ'}!={k:v for k,v in b.items() if k[0]=='OBJ'}:raise ValueError('Existing PCB changed')
  before['live_retained']=True
 p=bridge.native_export('nfc-twelve-options')
 state.update(status='four_five_cover_pcbs_saved_and_exported',native_project={'path':p.relative_to(HW).as_posix(),'size':p.stat().st_size,'sha256':digest(p)},
  release_status='HOLD_CAM_PHYSICAL_VALIDATION_PENDING',design_manifest_sha256=digest(OUT/'design-manifest.json'))
 write(state_path,state);write(OUT/'export-manifest.json',state)
 print(json.dumps({'status':state['status'],'native_project':state['native_project'],'boards':[{'name':b['name'],'drc':b['drc']} for b in state['boards']]},indent=2))


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','apply','export']);a=p.parse_args();globals()[a.stage]()
