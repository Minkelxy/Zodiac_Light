"""Create separate green-mask/white-silk PCB copies via the EasyEDA bridge.

Run prepare, then build_standard_layer_artwork.py, then apply and export.
Original PCB documents and historical exports are never rewritten by this tool.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import secrets
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'variants/standard-green-white'
PROJECT = 'c051e4069a83472198ecce7729fbd257'
TARGETS = [('horse-sagittarius', '4a4719695b24dc2b', 'Horse-Sagittarius-GreenWhite-100-v1'),
           ('snake-leo', 'fe8ee4534ee0b941', 'Snake-Leo-GreenWhite-100-v1')]
GUARD = f"const PROJECT={json.dumps(PROJECT)}; if((await eda.dmt_Project.getCurrentProjectInfo())?.uuid!==PROJECT)throw Error('Wrong project');"
ENCODE = "function encoded(bytes){let s='';for(let i=0;i<bytes.length;i+=16384)s+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(s);}"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(code, name):
    health = json.load(urllib.request.urlopen('http://127.0.0.1:49620/health', timeout=3))
    if health.get('service') != 'easyeda-bridge' or not health.get('edaConnected'):
        raise RuntimeError('A verified EasyEDA bridge connection is required')
    if health.get('edaWindowCount') != 1:
        raise RuntimeError('Select one EasyEDA window before using this delivery tool')
    request = urllib.request.Request('http://127.0.0.1:49620/execute',
        data=json.dumps({'code': GUARD+code, 'windowId': health['activeWindowId']}).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        response = json.load(urllib.request.urlopen(request, timeout=45))
    except urllib.error.HTTPError as error:
        response = json.loads(error.read())
    write_json(OUT/'eda/logs'/f'{name}.json', response)
    if not response.get('success'):
        raise RuntimeError(f"{name}: {response.get('error')}")
    return response['result']


def active(uuid):
    return f"if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=={json.dumps(uuid)})await eda.dmt_EditorControl.openDocument({json.dumps(uuid)}); const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo(); if(doc?.uuid!=={json.dumps(uuid)}||doc.documentType!==3||doc.parentProjectUuid!==PROJECT)throw Error('Wrong PCB document');"


def rows(source):
    result=[]
    for line in source.splitlines():
        if '||' not in line:
            continue
        head, body = line.split('||', 1)
        result.append((json.loads(head), json.loads(body.rstrip('|'))))
    return result


def protected(source):
    types={'COMPONENT','ATTR','PAD_NET','PAD','LINE','ARC','VIA','POLY','FILL','POUR','REGION','STRING','NET'}
    values=[]
    for meta, body in rows(source):
        if meta['type'] not in types:
            continue
        if meta['type'] in {'LINE','ARC','POLY','FILL','REGION','STRING'} and body.get('layerId') in (3,4,5,6):
            continue
        values.append(json.dumps([meta['type'],meta.get('id'),body],sort_keys=True,separators=(',',':')))
    return sorted(values)


def snapshot_source(uuid, name, relative):
    result=execute(active(uuid)+"return {info:await eda.dmt_Pcb.getCurrentPcbInfo(),source:await eda.sys_FileManager.getDocumentSource()};",name)
    path=OUT/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(result['source'],encoding='utf-8',newline='\n')
    return path,result


def native_export(name):
    result=execute(ENCODE+f"const f=await eda.sys_FileManager.getProjectFileByProjectUuid(PROJECT,{json.dumps(name)},undefined,'epro2');if(!f?.size)throw Error('Native export unavailable');return {{name:f.name,size:f.size,base64:encoded(new Uint8Array(await f.arrayBuffer()))}};",name)
    path=OUT/'eda/native'/f'{name}.epro2'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(base64.b64decode(result['base64']))
    if path.stat().st_size!=result['size']:
        raise ValueError('Native export size mismatch')
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError('Native archive CRC failed')
    return path


def prepare():
    state_path=OUT/'pcb-state.json'
    if state_path.exists():
        raise ValueError('Preparation already exists; inspect saved PCB state before repeating')
    state={'project':PROJECT,'soldermask':'green','silkscreen':'white','boards':[],'original_baselines':{}}
    for variant,source_uuid,name in TARGETS:
        execute(active(source_uuid)+"if(!await eda.pcb_Document.save())throw Error('Could not save source');return {saved:true};",f'prepare-save-{variant}')
        path,result=snapshot_source(source_uuid,f'before-{variant}',f'eda/native/before-{variant}-source.jsonl')
        objects=[body for head,body in rows(result['source']) if head['type']=='OBJ']
        if len(objects)!=2:
            raise ValueError('Unexpected color artwork: preserve user changes')
        state['original_baselines'][variant]={'uuid':source_uuid,'source':str(path.relative_to(ROOT)).replace('\\','/'),'sha256':sha(path)}
    path,result=snapshot_source('eb14b9eaec4f920c','before-core','eda/native/before-core-source.jsonl')
    state['original_baselines']['core']={'uuid':'eb14b9eaec4f920c','source':str(path.relative_to(ROOT)).replace('\\','/'),'sha256':sha(path)}
    native=native_export('nfc-before-standard-copies')
    state['project_before']=str(native.relative_to(ROOT)).replace('\\','/')
    write_json(state_path,state)
    for variant,source_uuid,name in TARGETS:
        result=execute(f"const existing=await eda.dmt_Pcb.getAllPcbsInfo();if(existing.some(p=>p.name.toLowerCase()==={json.dumps(name.lower())}))throw Error('PCB name already exists');const uuid=await eda.dmt_Pcb.copyPcb({json.dumps(source_uuid)});if(!uuid||uuid==={json.dumps(source_uuid)})throw Error('Copy failed');await new Promise(r=>setTimeout(r,1200));return {{uuid}};",f'copy-{variant}')
        uuid=result['uuid']
        board={'variant':variant,'source_pcb':source_uuid,'uuid':uuid,'requested_name':name,'status':'copied'}
        state['boards'].append(board)
        write_json(state_path,state)
        # The desktop client's rename API has affected the wrong document in a
        # live probe. Leave the default copy name and let the operator rename it
        # through the UI; apply verifies that exact name before modifying art.
        result=execute(active(uuid)+f"if(!await eda.pcb_Document.save())throw Error('Copy save failed');await new Promise(r=>setTimeout(r,1000));return {{info:await eda.dmt_Pcb.getPcbInfo({json.dumps(uuid)})}};",f'copy-info-{variant}')
        board['name']=result['info']['name']
        board['copy_default_name']=result['info']['name']
        board['rename_policy']='UI rename required; apply verifies the requested name'
        path,snapshot=snapshot_source(uuid,f'base-copy-{variant}',f'eda/native/base-copy-{variant}-source.jsonl')
        baseline=ROOT/state['original_baselines'][variant]['source']
        if protected(snapshot['source'])!=protected(baseline.read_text(encoding='utf-8')):
            raise ValueError('Copied physical primitives differ from the original PCB')
        board['base_copy_source']=str(path.relative_to(ROOT)).replace('\\','/')
        board['base_copy_sha256']=sha(path)
        write_json(state_path,state)
    print(json.dumps({'prepared':state['boards']},ensure_ascii=False,indent=2))


def load_final_artwork():
    """Bind the import bundle to the two independently validated final JSONs."""
    directory=OUT/'artwork'
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    bundle={'schema_version':1,'version':'ordinary-green-white-v1','variants':{},'source_files':{}}
    for variant,_,_ in TARGETS:
        path=directory/f'{variant}-standard-layer-artwork.json'
        expected=manifest['files'][path.name]
        if sha(path)!=expected['sha256'] or path.stat().st_size!=expected['size']:
            raise ValueError(f'Final artwork manifest mismatch: {variant}')
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version')!=1 or data.get('variant')!=variant or set(data['faces'])!={'front','rear'}:
            raise ValueError(f'Unexpected artwork schema: {variant}')
        for face_name,face in data['faces'].items():
            if face['validation']['status']!='passed':
                raise ValueError(f'Artwork native geometry is not validated: {variant}/{face_name}')
            if face['silk_layer_id']!=3 or face['mask_layer_id']!=5:
                raise ValueError('Ordinary cover artwork must use Top silk/mask layers')
            if face['validation']['rounded_native_silk_mask_overlap_mm2']!=0:
                raise ValueError('Art contains a silk/mask overlap')
            if face_name=='rear' and face['validation']['rounded_native_minimum_silk_mask_gap_mm']<.15:
                raise ValueError('Art violates the 0.15 mm silk/mask clearance')
        bundle['variants'][variant]=data
        bundle['source_files'][variant]={'path':str(path.relative_to(ROOT)).replace('\\','/'),
                                         'size':path.stat().st_size,'sha256':sha(path)}
    write_json(directory/'import-geometry.json',bundle)
    return bundle


def native_artwork_source(current, variant, artwork):
    """Append canonical FILL source records without the complex-fill API."""
    parsed=rows(current)
    used={head.get('id') for head,_ in parsed if head.get('id') is not None}
    ticket=max((int(head.get('ticket',0)) for head,_ in parsed),default=0)
    records=[]
    for head,body in parsed:
        if head['type']=='OBJ':
            continue
        if head['type']=='SILK_OPTS':
            body['defaultColor']='#FFFFFF'
            body['baseColor']='#187C43'
            ticket+=1
            head['ticket']=ticket
        records.append(json.dumps(head,separators=(',',':'))+'||'+json.dumps(body,separators=(',',':'))+'|')
    created=[]
    for face_name in ('front','rear'):
        face=artwork['faces'][face_name]
        for kind,key,layer in (('silk','silk_polygons',3),('mask','mask_opening_polygons',5)):
            for index,polygon in enumerate(face[key],1):
                ident=secrets.token_hex(8)
                while ident in used:
                    ident=secrets.token_hex(8)
                used.add(ident)
                ticket+=1
                body={'partitionId':'','groupId':0,'netName':'','layerId':layer,
                      'width':0,'fillStyle':'SOLID','path':polygon['path_mil'],
                      'locked':True,'zIndex':-1}
                head={'type':'FILL','ticket':ticket,'id':ident}
                records.append(json.dumps(head,separators=(',',':'))+'||'+json.dumps(body,separators=(',',':'))+'|')
                created.append({'id':ident,'logical_id':f'{variant}:{face_name}:{kind}:{index:03d}',
                                'source_id':polygon['id'],'face':face_name,'kind':kind,'layer':layer})
    source='\n'.join(records)+'\n'
    if protected(source)!=protected(current):
        raise ValueError('Artwork source generation altered protected geometry')
    return source,created


def fill_ids(source):
    return {head['id'] for head,body in rows(source) if head['type']=='FILL'}


def object_records(source):
    return {head['id']:body for head,body in rows(source) if head['type']=='OBJ'}


def same_path(expected, actual, tolerance=.001):
    if isinstance(expected,list):
        return isinstance(actual,list) and len(expected)==len(actual) and all(
            same_path(left,right,tolerance) for left,right in zip(expected,actual))
    if isinstance(expected,(int,float)) and not isinstance(expected,bool):
        return isinstance(actual,(int,float)) and not isinstance(actual,bool) and math.isfinite(actual) and abs(expected-actual)<=tolerance
    return expected==actual


def verify_created_fills(source, created, expected_source=None, original_source=None):
    effective={}
    for head,body in rows(source):
        ident=head.get('id')
        if head['type']=='OBJ':
            raise ValueError('Color objects remain in the standard copy')
        if head['type']=='FILL' and ident is not None:
            effective[ident]=body
    for item in created:
        body=effective.get(item['id'])
        if body is None or body.get('layerId')!=item['layer'] or body.get('fillStyle') not in ('SOLID',0) or type(body.get('width')) not in (int,float) or body['width'] not in (0,.2):
            raise ValueError(f'Imported ordinary FILL did not persist: {item["logical_id"]}')
        item['requested_width_mil']=0
        item['actual_width_mil']=body['width']
    if expected_source is not None:
        expected={head['id']:body for head,body in rows(expected_source) if head['type']=='FILL'}
        for item in created:
            if not same_path(expected[item['id']]['path'],effective[item['id']]['path']):
                raise ValueError(f'Native path changed beyond 0.001 mil: {item["logical_id"]}')
    if original_source is not None:
        if fill_ids(source)!=fill_ids(original_source)|{item['id'] for item in created}:
            raise ValueError('Unexpected extra or missing native fill after importing artwork')
        if protected(source)!=protected(original_source):
            raise ValueError('Protected geometry changed during ordinary artwork import')


def fresh_snapshot(uuid, name, validate, attempts=8):
    """Read in separate requests after asynchronous source/delete operations."""
    last_error=None
    for attempt in range(attempts):
        result=execute(active(uuid)+f"return {{info:await eda.dmt_Pcb.getPcbInfo({json.dumps(uuid)}),source:await eda.sys_FileManager.getDocumentSource()}};",f'{name}-{attempt:02d}')
        try:
            if not isinstance(result.get('source'),str) or not result['source']:
                raise ValueError('Document source is not ready')
            validate(result['source'])
            return result
        except ValueError as error:
            last_error=error
            if attempt+1<attempts:
                time.sleep(.25)
    raise ValueError(f'Source did not settle after {name}: {last_error}') from last_error


def verify_rollback(before, after, created):
    if protected(after)!=protected(before) or fill_ids(after)!=fill_ids(before):
        raise ValueError('Rollback did not restore the protected geometry/original fill set')
    if object_records(after)!=object_records(before):
        raise ValueError('Rollback did not restore the original color objects')
    if fill_ids(after)&{item['id'] for item in created}:
        raise ValueError('Rollback left newly imported artwork fills in the copy')


def apply():
    state_path=OUT/'pcb-state.json'
    state=json.loads(state_path.read_text(encoding='utf-8'))
    artwork=load_final_artwork()
    names={variant:name for variant,_,name in TARGETS}
    for board in state['boards']:
        if board['status']!='copied':
            raise ValueError('PCB has already been applied; refusing to duplicate artwork')
        variant,uuid=board['variant'],board['uuid']
        base=(ROOT/board['base_copy_source']).read_text(encoding='utf-8')
        before=execute(active(uuid)+f"return {{info:await eda.dmt_Pcb.getPcbInfo({json.dumps(uuid)}),source:await eda.sys_FileManager.getDocumentSource()}};",f'apply-before-{variant}')
        if not before.get('info') or before['info'].get('name')!=names[variant]:
            raise ValueError(f'Use the UI to name {variant} copy exactly {names[variant]} before applying artwork')
        board['name']=before['info']['name']
        board['requested_name']=names[variant]
        board.pop('rename_result',None)
        board['rename_method']='desktop_tree_UI_verified_by_getPcbInfo'
        current=before['source']
        if protected(current)!=protected(base):
            raise ValueError('Protected copy geometry changed before artwork import')
        extras=fill_ids(current)-fill_ids(base)
        if extras or fill_ids(current)!=fill_ids(base):
            raise ValueError(f'Copy has a non-baseline native fill set; clean the earlier import before retrying: {sorted(extras)}')
        original_objects=object_records(current)
        if len(original_objects)!=2 or original_objects!=object_records(base):
            raise ValueError('Expected the two original color objects before ordinary artwork import')
        imported,created=native_artwork_source(current,variant,artwork['variants'][variant])
        pending=OUT/'eda/native'/f'{variant}-pending-standard-source.jsonl'
        pending.parent.mkdir(parents=True,exist_ok=True)
        pending.write_text(imported,encoding='utf-8',newline='\n')
        try:
            ids=list(original_objects)
            execute(active(uuid)+f"if(!await eda.pcb_PrimitiveObject.delete({json.dumps(ids)}))throw Error('Cannot remove original color objects');return {{deleted:{json.dumps(ids)}}};",f'apply-delete-objects-{variant}')
            def no_objects(source):
                if object_records(source):
                    raise ValueError('Color object deletion has not settled')
            fresh_snapshot(uuid,f'apply-after-object-delete-{variant}',no_objects)
            execute(active(uuid)+f"if(!await eda.sys_FileManager.setDocumentSource({json.dumps(imported)}))throw Error('Cannot import native ordinary artwork source');return {{import_requested:true}};",f'apply-native-source-{variant}')
            fresh_snapshot(uuid,f'apply-stable-import-{variant}',
                           lambda source:verify_created_fills(source,created,imported,current))
            result=execute(active(uuid)+"if((await eda.pcb_PrimitiveObject.getAll()).length)throw Error('Color objects remain');if(!await eda.pcb_Document.save())throw Error('Artwork save failed');if(!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Close failed');return {saved:true,closed:true};",f'apply-save-{variant}')
            snapshot=fresh_snapshot(uuid,f'after-{variant}',
                                    lambda source:verify_created_fills(source,created,imported,current))
            path=OUT/'eda/native'/f'{variant}-source.jsonl'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(snapshot['source'],encoding='utf-8',newline='\n')
            if protected(snapshot['source'])!=protected(base):
                raise ValueError('Protected geometry changed while importing ordinary artwork')
            if snapshot['info']['name']!=names[variant]:
                raise ValueError('Standard copy name changed after saving/reopening')
            verify_created_fills(snapshot['source'],created,imported,current)
            board.update({'status':'applied_saved_reopened','created':created,'source':str(path.relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(path),'protected_geometry_unchanged':True,'saved_reopened':True,
                          'artwork_source':artwork['source_files'][variant],
                          'import_geometry_sha256':sha(OUT/'artwork/import-geometry.json'),
                          'import_method':'delete_exact_color_OBJs_then_validated_native_FILL_JSONL_setDocumentSource',
                          'actual_width_mil':sorted({item['actual_width_mil'] for item in created}),
                          'native_width_policy':'Requested width 0; runtime may normalize SOLID width to known 0.2 mil. Exported Gerber contours require independent verification.'})
            write_json(state_path,state)
        except Exception:
            owned=[item['id'] for item in created]
            execute(active(uuid)+f"const OWNED=new Set({json.dumps(owned)});const ids=(await eda.pcb_PrimitiveFill.getAll()).map(f=>f.getState_PrimitiveId()).filter(id=>OWNED.has(id));if(ids.length&&!await eda.pcb_PrimitiveFill.delete(ids))throw Error('Rollback fill deletion failed');return {{deleted:ids}};",f'rollback-delete-owned-{variant}')
            execute(active(uuid)+f"if(!await eda.sys_FileManager.setDocumentSource({json.dumps(current)}))throw Error('Rollback source restore failed');return {{restore_requested:true}};",f'rollback-restore-source-{variant}')
            fresh_snapshot(uuid,f'rollback-stable-{variant}',lambda source:verify_rollback(current,source,created))
            execute(active(uuid)+"if(!await eda.pcb_Document.save())throw Error('Rollback save failed');return {saved:true};",f'rollback-save-{variant}')
            fresh_snapshot(uuid,f'rollback-saved-{variant}',lambda source:verify_rollback(current,source,created))
            raise
    print(json.dumps({'applied':[{k:v for k,v in b.items() if k!='created'} for b in state['boards']]},ensure_ascii=False,indent=2))


def export():
    state=json.loads((OUT/'pcb-state.json').read_text(encoding='utf-8'))
    for board in state['boards']:
        if board['status']!='applied_saved_reopened':
            raise ValueError('Only saved/reopened ordinary PCBs may be exported')
        variant,uuid=board['variant'],board['uuid']
        result=execute(active(uuid)+"const drc=await eda.pcb_Drc.check(true,false,true);if(!Array.isArray(drc))throw Error('Invalid DRC result');return {drc};",f'drc-{variant}')
        board['drc']=result['drc']
        write_json(OUT/'pcb-state.json',state)
        if board['drc']:
            raise ValueError(f'{variant} DRC has findings; inspect before exporting')
        result=execute(active(uuid)+ENCODE+f"const ESYS_Unit={{MILLIMETER:'mm'}};const f=await eda.pcb_ManufactureData.getGerberFile({json.dumps(variant+'-green-white')},false,ESYS_Unit.MILLIMETER,{{integerNumber:3,decimalNumber:6}},{{metallicDrillingInformation:true,nonMetallicDrillingInformation:true,drillTable:true,flyingProbeTestingFile:false}});if(!f?.size)throw Error('Gerber export unavailable');return {{size:f.size,base64:encoded(new Uint8Array(await f.arrayBuffer()))}};",f'gerber-{variant}')
        path=OUT/'manufacturing-draft'/f'{variant}-green-white-gerber.zip'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(base64.b64decode(result['base64']))
        members=[]
        with zipfile.ZipFile(path) as archive:
            if archive.testzip():
                raise ValueError('Gerber archive CRC failed')
            for item in archive.infolist():
                if item.filename.startswith('Fabrication_Colorful'):
                    raise ValueError('Unexpected colored fabrication data')
                members.append({'name':item.filename,'size':item.file_size,'sha256':hashlib.sha256(archive.read(item)).hexdigest()})
        member_path=path.with_suffix('.members.json')
        write_json(member_path,members)
        board.update({'gerber':str(path.relative_to(ROOT)).replace('\\','/'),'gerber_members':str(member_path.relative_to(ROOT)).replace('\\','/'),'color_silkscreen_export':False})
        path,snapshot=snapshot_source(uuid,f'export-source-{variant}',f'eda/native/{variant}-source.jsonl')
        board['source_sha256']=sha(path)
        write_json(OUT/'pcb-state.json',state)
    for variant,baseline in state['original_baselines'].items():
        result=execute(active(baseline['uuid'])+"return {source:await eda.sys_FileManager.getDocumentSource()};",f'original-retained-{variant}')
        before=(ROOT/baseline['source']).read_text(encoding='utf-8')
        if protected(before)!=protected(result['source']):
            raise ValueError('Original PCB protected geometry changed')
        before_obj=[body for head,body in rows(before) if head['type']=='OBJ']
        after_obj=[body for head,body in rows(result['source']) if head['type']=='OBJ']
        if before_obj!=after_obj:
            raise ValueError('Original color artwork changed')
        baseline['live_retained']=True
    native=native_export('nfc-color-and-green-white')
    state['native_project']={'path':str(native.relative_to(ROOT)).replace('\\','/'),'size':native.stat().st_size,'sha256':sha(native)}
    state['artwork_file']='variants/standard-green-white/artwork/import-geometry.json'
    state['release_status']='HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING'
    state['status']='ordinary_green_white_pcbs_saved_and_exported'
    state['files']={str(path.relative_to(ROOT)).replace('\\','/'):{'size':path.stat().st_size,'sha256':sha(path)}
                    for path in (OUT/'eda/native').glob('*') if path.is_file()}
    state['files'].update({str(path.relative_to(ROOT)).replace('\\','/'):{'size':path.stat().st_size,'sha256':sha(path)}
                          for path in (OUT/'manufacturing-draft').glob('*') if path.is_file()})
    write_json(OUT/'export-manifest.json',state)
    write_json(OUT/'pcb-state.json',state)
    print(json.dumps({'status':state['status'],'boards':[{k:b[k] for k in ('variant','uuid','name','drc')} for b in state['boards']],'native':state['native_project']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','apply','export'])
    args=parser.parse_args()
    {'prepare':prepare,'apply':apply,'export':export}[args.stage]()
