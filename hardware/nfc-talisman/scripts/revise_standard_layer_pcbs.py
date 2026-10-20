"""Guarded artwork-only revisions of the two existing green/white PCBs."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import copy
import shutil
from pathlib import Path
import zipfile
import create_standard_layer_pcbs as api
import check_standard_delivery as checker

HW=Path(__file__).resolve().parents[1]
OUT=HW/'variants/standard-green-white'
TWELVE=HW/'variants/twelve-options'
api.OUT=OUT


def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):api.write_json(p,v)
def strip(source,ids):
 return '\n'.join(json.dumps(h,separators=(',',':'))+'||'+json.dumps(b,separators=(',',':'))+'|' for h,b in api.rows(source) if not(h['type']=='FILL' and h.get('id') in ids))+'\n'


def prepare():
 state=load(OUT/'pcb-state.json')
 if any('border_revision' in b for b in state['boards']):raise ValueError('Border revision already prepared')
 old_manifest=OUT/'eda/native/before-border-export-manifest.json'
 if old_manifest.exists():raise ValueError('Preserve the existing revision baseline')
 old_manifest.write_bytes((OUT/'export-manifest.json').read_bytes())
 for b in state['boards']:
  v,u=b['variant'],b['uuid'];old=(HW/b['source']).read_text(encoding='utf-8')
  base=(HW/b['base_copy_source']).read_text(encoding='utf-8')
  p,r=api.snapshot_source(u,'before-border-'+v,'eda/native/before-border-'+v+'-source.jsonl')
  api.verify_created_fills(r['source'],b['created'],old,base)
  b['border_revision']={'status':'prepared','before':{'path':p.relative_to(HW).as_posix(),'sha256':sha(p),
    'owned_silk_ids':[x['id'] for x in b['created'] if x['kind']=='silk'],
    'manifest_path':old_manifest.relative_to(HW).as_posix(),'manifest_sha256':sha(old_manifest)},
    'old_owned_ids':[x['id'] for x in b['created']]}
 write(OUT/'pcb-state.json',state)
 print('Two standard artwork revision baselines saved')


def prepare_depanel():
 state=load(OUT/'pcb-state.json')
 if any('depanel_revision' in b for b in state['boards']):raise ValueError('Depanel revision already prepared')
 snapshot=TWELVE/'eda/native/before-depanel-20261020.epro2'
 if snapshot.exists():raise ValueError('Preserve the existing depanel baseline')
 shutil.copyfile(HW/state['native_project']['path'],snapshot)
 prior=OUT/'eda/native/before-depanel-export-manifest.json'
 prior.write_bytes((OUT/'export-manifest.json').read_bytes())
 for b in state['boards']:
  v,u=b['variant'],b['uuid']
  old=(HW/b['source']).read_text(encoding='utf-8')
  p,r=api.snapshot_source(u,'before-depanel-'+v,'eda/native/before-depanel-'+v+'-source.jsonl')
  if checker._BASE._design_records(checker._BASE._replay(old)[u]['records'])!=checker._BASE._design_records(checker._BASE._replay(r['source'])[u]['records']):raise ValueError('Live board changed before depanel revision')
  b['depanel_revision']={'status':'prepared','outward_offset_mm':.4,'before':{'path':p.relative_to(HW).as_posix(),'sha256':sha(p)},
   'before_manifest':{'path':prior.relative_to(HW).as_posix(),'sha256':sha(prior)},
   'before_native':{'path':snapshot.relative_to(HW).as_posix(),'sha256':sha(snapshot)}}
  b['border_revision'].update(status='prepared',old_owned_ids=[x['id'] for x in b['created']])
  b['border_revision']['before']['depanel_offset_mm']=.4
 write(OUT/'pcb-state.json',state)
 print('Current standard sources and nine-PCB archive backed up for depanel revision')


def apply():
 state=load(OUT/'pcb-state.json');art=api.load_final_artwork()
 for b in state['boards']:
  revision=b['border_revision']
  if revision['status']=='saved_reopened':continue
  if revision['status']!='prepared':raise ValueError('Unexpected revision state')
  v,u=b['variant'],b['uuid'];ev=b.get('depanel_revision',{}).get('before',revision['before']);p=HW/ev['path']
  if sha(p)!=ev['sha256']:raise ValueError('Revision baseline changed')
  before=p.read_text(encoding='utf-8');old_owned=set(revision['old_owned_ids'])
  current=api.execute(api.active(u)+'return {source:await eda.sys_FileManager.getDocumentSource()};','border-guard-'+v)['source']
  if checker._BASE._design_records(checker._BASE._replay(current)[u]['records'])!=checker._BASE._design_records(checker._BASE._replay(before)[u]['records']):raise ValueError('Live standard board changed since baseline')
  baseline=strip(before,old_owned)
  moved=[]
  if b.get('depanel_revision'):
   transformed=[]
   for h,body in api.rows(baseline):
    body=copy.deepcopy(body)
    delta=checker._mousebite_delta(body) if h['type']=='PAD' else None
    if delta is not None:
     body['centerX']=round(body['centerX']+delta[0]/.0254,4);body['centerY']=round(body['centerY']+delta[1]/.0254,4);moved.append(h['id'])
     for axis in ('centerX','centerY'):
      if body[axis]==int(body[axis]):body[axis]=int(body[axis])
    transformed.append(json.dumps(h,separators=(',',':'))+'||'+json.dumps(body,separators=(',',':'))+'|')
   if len(moved)!=100:raise ValueError('Expected 100 owned mousebites')
   baseline='\n'.join(transformed)+'\n'
  imported,created=api.native_artwork_source(baseline,v,art['variants'][v])
  try:
   api.execute(api.active(u)+f"if(!await eda.pcb_PrimitiveFill.delete({json.dumps(sorted(old_owned))}))throw Error('Old artwork delete failed');return {{deleted:true}};",'border-delete-'+v)
   if moved:api.execute(api.active(u)+f"if(!await eda.pcb_PrimitivePad.delete({json.dumps(moved)}))throw Error('Mousebite delete failed');return {{deleted:true}};",'depanel-delete-'+v)
   api.execute(api.active(u)+f"if(!await eda.sys_FileManager.setDocumentSource({json.dumps(imported)}))throw Error('Import failed');return {{imported:true}};",'border-import-'+v)
   api.fresh_snapshot(u,'border-stable-'+v,lambda s:api.verify_created_fills(s,created,imported,baseline))
   api.execute(api.active(u)+"if(!await eda.pcb_Document.save())throw Error('Save failed');if(!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Close failed');return {saved:true,closed:true};",'border-save-'+v)
   p,r=api.snapshot_source(u,'border-reopened-'+v,'eda/native/'+v+'-source.jsonl')
   api.verify_created_fills(r['source'],created,imported,baseline)
  except Exception:
   ids=[x['id'] for x in created]
   api.execute(api.active(u)+f"const own=new Set({json.dumps(ids)});const ids=(await eda.pcb_PrimitiveFill.getAll()).map(f=>f.getState_PrimitiveId()).filter(id=>own.has(id));if(ids.length&&!await eda.pcb_PrimitiveFill.delete(ids))throw Error('Rollback delete failed');if(!await eda.sys_FileManager.setDocumentSource({json.dumps(before)}))throw Error('Rollback restore failed');return {{restored:true}};",'border-rollback-'+v)
   if moved:
    api.execute(api.active(u)+f"const wanted=new Set({json.dumps(moved)});const pads=(await eda.pcb_PrimitivePad.getAll()).map(p=>p.getState_PrimitiveId()).filter(id=>wanted.has(id));if(pads.length)await eda.pcb_PrimitivePad.delete(pads);if(!await eda.sys_FileManager.setDocumentSource({json.dumps(before)}))throw Error('Pad rollback failed');return {{restored:true}};",'depanel-rollback-'+v)
   api.fresh_snapshot(u,'border-rollback-stable-'+v,lambda s:api.verify_rollback(before,s,created))
   api.execute(api.active(u)+"if(!await eda.pcb_Document.save())throw Error('Rollback save failed');return {saved:true};",'border-rollback-save-'+v)
   raise
  b.update(created=created,source=p.relative_to(HW).as_posix(),source_sha256=sha(p),artwork_source=art['source_files'][v],
   import_geometry_sha256=sha(OUT/'artwork/import-geometry.json'),actual_width_mil=sorted({x['actual_width_mil'] for x in created}),
   import_method='guarded_owned_top_silk_revision_mask_geometry_and_physical_primitives_preserved')
  revision['status']='saved_reopened'
  if b.get('depanel_revision'):b['depanel_revision']['status']='saved_reopened'
  write(OUT/'pcb-state.json',state)
 print('Two standard artwork revisions saved and reopened')


def gerbers():
 state=load(OUT/'pcb-state.json')
 for b in state['boards']:
  v,u=b['variant'],b['uuid']
  if b['border_revision']['status']!='saved_reopened':raise ValueError('Unsaved revision')
  result=api.execute(api.active(u)+"const drc=await eda.pcb_Drc.check(true,false,true);return {drc};",'drc-'+v)
  b['drc']=result['drc'];write(OUT/'pcb-state.json',state)
  if b['drc']!=[]:raise ValueError('DRC findings: '+v)
  result=api.execute(api.active(u)+api.ENCODE+f"const f=await eda.pcb_ManufactureData.getGerberFile({json.dumps(v+'-green-white')},false,'mm',{{integerNumber:3,decimalNumber:6}},{{metallicDrillingInformation:true,nonMetallicDrillingInformation:true,drillTable:true,flyingProbeTestingFile:false}});if(!f?.size)throw Error('Missing Gerber');return {{base64:encoded(new Uint8Array(await f.arrayBuffer()))}};",'gerber-'+v)
  p=HW/b['gerber'];p.write_bytes(base64.b64decode(result['base64']))
  with zipfile.ZipFile(p) as z:
   if z.testzip() or any(n.startswith('Fabrication_Colorful') for n in z.namelist()):raise ValueError('Invalid ordinary Gerber')
   members=[{'name':n,'size':len(z.read(n)),'sha256':hashlib.sha256(z.read(n)).hexdigest()} for n in z.namelist()]
  write(HW/b['gerber_members'],members)
  p,r=api.snapshot_source(u,'border-export-source-'+v,'eda/native/'+v+'-source.jsonl');b['source_sha256']=sha(p)
  write(OUT/'pcb-state.json',state)
 print('Two standard DRC checks and ordinary Gerber exports completed')


def bind_twelve():
 state=load(OUT/'pcb-state.json');twelve=load(TWELVE/'pcb-state.json')
 for b in state['boards']:
  if b['border_revision']['status']!='saved_reopened' or b['drc']!=[]:raise ValueError('Standard revision not ready')
  twelve['existing'][b['uuid']]={'path':b['source'],'sha256':b['source_sha256'],'uuid':b['uuid'],
   'revision_before':b['border_revision']['before'],'retention_policy':'owned_top_silk_revision_physical_and_mask_preserved'}
 write(TWELVE/'pcb-state.json',twelve)
 print('Twelve-option baseline linked to explicit standard silk revisions')


def bind_native():
 state=load(OUT/'pcb-state.json');twelve=load(TWELVE/'export-manifest.json')
 state['native_project']=twelve['native_project']
 state['archive_scope']={'pcb_uuids':sorted(set(twelve['existing'])|{b['uuid'] for b in twelve['boards']})}
 if (HW/'variants/horse-snake-spacers/export-manifest.json').exists():
  state['archive_scope']['pcb_uuids']=sorted(checker.shared_pcb_scope(HW))
 state['files']={p.relative_to(HW).as_posix():{'size':p.stat().st_size,'sha256':sha(p)} for folder in ('eda/native','manufacturing-draft') for p in (OUT/folder).glob('*') if p.is_file()}
 state['artwork_file']='variants/standard-green-white/artwork/import-geometry.json'
 state['historical_five_pcb_snapshot']='variants/standard-green-white/eda/native/nfc-color-and-green-white.epro2'
 write(OUT/'pcb-state.json',state);write(OUT/'export-manifest.json',state)
 print('Both current deliveries reference the same nine-PCB native archive')


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','prepare-depanel','apply','gerbers','bind-twelve','bind-native']);a=p.parse_args()
 globals()[a.stage.replace('-','_')]()
