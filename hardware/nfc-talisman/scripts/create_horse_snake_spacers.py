"""Guarded live creation of the additional horse/snake/three-spacer PCB."""
import argparse
import base64
import json
import shutil
import zipfile
import create_standard_layer_pcbs as api
import create_twelve_option_pcbs as original
import build_horse_snake_spacers as design

HW=design.HW
OUT=design.OUT
api.OUT=OUT

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):api.write_json(p,v)

def prepare():
    path=OUT/'pcb-state.json'
    if path.exists():raise ValueError('Additional PCB already prepared; resume its recorded state')
    existing=api.execute('return await eda.dmt_Pcb.getAllPcbsInfo();','before-catalog')
    if len(existing)!=9 or any(p['name']==design.NAME for p in existing):raise ValueError('Unexpected project scope')
    backup=OUT/'eda/native/before-additional-panel.epro2'
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HW/'variants/twelve-options/eda/native/nfc-twelve-options.epro2',backup)
    state=dict(status='preparing',existing_catalog=[dict(uuid=p['uuid'],name=p['name']) for p in existing],
               before_native=dict(path=backup.relative_to(HW).as_posix(),sha256=design.sha(backup)))
    write(path,state)
    created=api.execute("const uuid=await eda.dmt_Pcb.createPcb();if(!uuid)throw Error('Creation failed');return {uuid};",'create')
    state['uuid']=created['uuid'];state['status']='blank_created';write(path,state)
    api.execute(api.active(state['uuid'])+f"if(!await eda.dmt_Pcb.modifyPcbName({json.dumps(state['uuid'])},{json.dumps(design.NAME)}))throw Error('Rename failed');return {{renamed:true}};",'rename')
    current=api.execute('return await eda.dmt_Pcb.getAllPcbsInfo();','after-catalog')
    names={p['uuid']:p['name'] for p in current}
    if any(names.get(p['uuid'])!=p['name'] for p in state['existing_catalog']):raise ValueError('PCB naming affected an unexpected document')
    p,r=api.snapshot_source(state['uuid'],'blank','eda/native/blank.jsonl')
    state.update(name=names[state['uuid']],requested_name=design.NAME,display_name='马、蛇盖板与三片空心隔层',blank_source=dict(path=p.relative_to(HW).as_posix(),sha256=design.sha(p)))
    write(path,state)
    print(json.dumps({'uuid':state['uuid'],'name':state['name']}))

def finish_prepare():
    state=load(OUT/'pcb-state.json')
    if state['status']!='blank_created' or state.get('blank_source'):raise ValueError('Unexpected preparation state')
    current=api.execute('return await eda.dmt_Pcb.getAllPcbsInfo();','resume-catalog')
    names={p['uuid']:p['name'] for p in current}
    if set(names)!={p['uuid'] for p in state['existing_catalog']}|{state['uuid']} or any(names[p['uuid']]!=p['name'] for p in state['existing_catalog']):raise ValueError('Project catalog changed unexpectedly')
    p,r=api.snapshot_source(state['uuid'],'blank','eda/native/blank.jsonl')
    state.update(name=names[state['uuid']],requested_name=design.NAME,display_name='马、蛇盖板与三片空心隔层',blank_source=dict(path=p.relative_to(HW).as_posix(),sha256=design.sha(p)))
    write(OUT/'pcb-state.json',state)

def apply():
    state=load(OUT/'pcb-state.json')
    if state['status']!='blank_created':raise ValueError('Expected untouched new PCB')
    geometry=load(OUT/'geometry.json');uuid=state['uuid']
    before=(HW/state['blank_source']['path']).read_text(encoding='utf-8')
    if design.sha(HW/state['blank_source']['path'])!=state['blank_source']['sha256']:raise ValueError('Blank source changed')
    records=api.rows(before)
    if any(h['type'] in ('PAD','POLY','FILL','COMPONENT','OBJ') for h,b in records):raise ValueError('New PCB is not empty')
    for h,b in records:
        if h['type']=='SILK_OPTS':b.update(defaultColor='#FFFFFF',baseColor='#147442')
        if h['type']=='D3_ATTRIBUTE':b.update(boardColor='green',silkTechnology='standardSilk')
    rows=[json.dumps(h,separators=(',',':'))+'||'+json.dumps(b,separators=(',',':'))+'|' for h,b in records]
    rows.extend(json.dumps(e['head'],separators=(',',':'))+'||'+json.dumps(e['body'],separators=(',',':'))+'|' for e in geometry['primitives'])
    source='\n'.join(rows)+'\n'
    api.execute(api.active(uuid)+f"if(!await eda.sys_FileManager.setDocumentSource({json.dumps(source)}))throw Error('Import failed');return {{imported:true}};",'apply')
    api.fresh_snapshot(uuid,'stable',lambda text:original.verify_board(text,uuid,geometry))
    api.execute(api.active(uuid)+"if(!await eda.pcb_Document.save())throw Error('Save failed');if(!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Close failed');return {saved:true,closed:true};",'save-close')
    p,r=api.snapshot_source(uuid,'reopened','eda/native/horse-snake-spacers-source.jsonl')
    original.verify_board(r['source'],uuid,geometry)
    state.update(status='saved_reopened',source=dict(path=p.relative_to(HW).as_posix(),sha256=design.sha(p)),geometry='geometry.json',key=design.KEY,cover_count=5)
    write(OUT/'pcb-state.json',state)
    print('Additional panel saved, closed and reopened')

def export():
    state=load(OUT/'pcb-state.json');uuid=state['uuid']
    if state['status']!='saved_reopened':raise ValueError('Unsaved supplemental PCB')
    state['drc']=api.execute(api.active(uuid)+'return {drc:await eda.pcb_Drc.check(true,false,true)};','drc')['drc']
    if state['drc']!=[]:raise ValueError('Supplemental PCB DRC findings')
    code=api.active(uuid)+api.ENCODE+"const f=await eda.pcb_ManufactureData.getGerberFile('horse-snake-spacers',false,'mm',{integerNumber:3,decimalNumber:6},{metallicDrillingInformation:true,nonMetallicDrillingInformation:true,drillTable:true,flyingProbeTestingFile:false});if(!f?.size)throw Error('No Gerber');return {base64:encoded(new Uint8Array(await f.arrayBuffer()))};"
    result=api.execute(code,'gerber')
    p=OUT/'manufacturing-draft/horse-snake-spacers-green-white-gerber.zip'
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(result['base64']))
    with zipfile.ZipFile(p) as z:
        if z.testzip() or any(n.startswith('Fabrication_Colorful') for n in z.namelist()):raise ValueError('Invalid ordinary Gerber')
        members={n:dict(size=len(z.read(n)),sha256=__import__('hashlib').sha256(z.read(n)).hexdigest()) for n in z.namelist()}
    state['gerber']=dict(path=p.relative_to(HW).as_posix(),size=p.stat().st_size,sha256=design.sha(p),members=members)
    write(OUT/'pcb-state.json',state)
    current=load(HW/'variants/twelve-options/export-manifest.json')
    state['native_project']=current['native_project']
    write(OUT/'pcb-state.json',state)
    manifest=dict(schema_version=1,status='additional_panel_saved_exported',boards=[state],native_project=state['native_project'],
                  design_manifest_sha256=design.sha(OUT/'design-manifest.json'),release_status='HOLD_CAM_PHYSICAL_VALIDATION_PENDING')
    write(OUT/'export-manifest.json',manifest)
    print('Supplemental DRC 0, ordinary Gerber exported and native archive linked')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','finish_prepare','apply','export']);a=p.parse_args()
    globals()[a.stage]()
