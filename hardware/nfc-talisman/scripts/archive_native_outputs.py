"""Archive bridge exports locally and check ZIP integrity, without publishing."""
import base64
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def result(name):
    data=json.loads((ROOT/'eda/logs'/f'{name}.json').read_text(encoding='utf-8'))
    if not data.get('success'):
        raise RuntimeError(f'Bridge export failed: {name}')
    return data['result']

def file_info(path):
    info={'path':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f'Invalid ZIP: {path}')
            info['zip_entries']=archive.namelist()
    return info

def main():
    draft=ROOT/'manufacturing/draft'
    draft.mkdir(parents=True,exist_ok=True)
    snapshot=result('30-native-connectivity-snapshot')
    for name,document in snapshot['documents'].items():
        (ROOT/'eda/native'/f'{name}-source.jsonl').write_text(document['source'],encoding='utf-8')
        # Preserve the API's native shape: PCB netlist is two JSON strings;
        # schematic netlist is a single JSON string decoded for inspection.
        netlist=document['netlist']
        if isinstance(netlist,str):
            netlist=json.loads(netlist)
        (ROOT/'eda/native'/f'{name}-netlist.json').write_text(json.dumps(netlist,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=result('38-export-manufacturing-draft')['files']
    paths=[]
    for key,name in [('gerber','nfc-talisman-panel-draft.zip'),('bom','nfc-talisman-panel-bom-all.csv'),('pnp','nfc-talisman-panel-pnp-all.csv')]:
        payload=files[key]
        path=draft/name
        if 'base64' in payload:
            path.write_bytes(base64.b64decode(payload['base64'],validate=True))
        else:
            path.write_text(payload['text'],encoding='utf-8-sig',newline='')
        paths.append(path)
    project=result('31-export-native-project')
    path=ROOT/'eda/native/nfc-talisman-current.epro2'
    path.write_bytes(base64.b64decode(project['base64'],validate=True))
    if path.stat().st_size!=project['size']:
        raise ValueError('Native project length mismatch')
    paths.append(path)
    manifest={'date':'2026-10-10','status':'draft_not_released','project_uuid':project['project'],'files':[file_info(p) for p in paths],'pending':['Manual faithful horse artwork and front optical window design','CAM review of slots, tabs and 3 mm assembly rails','LED physical polarity and rotation review','Bare-core and five-layer RF tuning, VOUT, Android/iPhone and optical acceptance']}
    (draft/'export-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
