"""Archive fresh native/PCB drafts separately from frozen prior exports."""
from pathlib import Path
import base64
import hashlib
import json
import zipfile
from bridge import execute

ROOT=Path(__file__).resolve().parents[1]
script=ROOT/'scripts/56-export-two-variant-drafts.js'
r=execute(script.read_text(encoding='utf-8'),'56-export-two-variant-drafts',timeout=180)
v=r.get('result',{})
if not r.get('success') or v.get('status')!='two_variants_design_drafts_exported':
    print(json.dumps(r,ensure_ascii=False)[:2200]);raise SystemExit(1)
common=ROOT/'variants/common'
native=common/'eda/native'
native.mkdir(parents=True,exist_ok=True)
native_file=native/'nfc-two-variants.epro2'
native_file.write_bytes(base64.b64decode(v['native']['base64']))
assert native_file.stat().st_size==v['native']['size']
(native/'schematic-source.jsonl').write_text(v['schematicSource'],encoding='utf-8',newline='\n')
summary={'status':v['status'],'project':v['project'],'erc':v['erc'],'pcbCatalog':v['pcbCatalog'],'releaseStatus':v['releaseStatus'],'boards':[],'files':{}}
written=[native_file,native/'schematic-source.jsonl']
for b in v['boards']:
    stem='core' if b['variant']=='common' else b['variant']+'-panel'
    source=native/(stem+'-source.jsonl')
    source.write_text(b['source'],encoding='utf-8',newline='\n')
    pads=common/'eda'/(stem+'-pads.json');pads.write_text(json.dumps(b['pads'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    netlist=native/(stem+'-netlist.json');netlist.write_text(json.dumps(b['netlist'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    written.extend([source,pads,netlist])
    summary['boards'].append({k:x for k,x in b.items() if k not in ['source','pads','netlist','files']})
    if b['variant']!='common':
        out=ROOT/'variants'/b['variant']/'manufacturing-draft';out.mkdir(parents=True,exist_ok=True)
        gerber=out/(b['variant']+'-gerber.zip');gerber.write_bytes(base64.b64decode(b['files']['gerber']['base64']))
        assert gerber.stat().st_size==b['files']['gerber']['size']
        bom=out/'bom-all.csv';bom.write_text(b['files']['bom']['text'],encoding='utf-8',newline='')
        pnp=out/'pnp-all.csv';pnp.write_text(b['files']['pnp']['text'],encoding='utf-8',newline='')
        members=[]
        with zipfile.ZipFile(gerber) as z:
            for info in z.infolist():
                members.append({'name':info.filename,'size':info.file_size,'sha256':hashlib.sha256(z.read(info)).hexdigest()})
        member_file=out/'gerber-members.json';member_file.write_text(json.dumps(members,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        written.extend([gerber,bom,pnp,member_file])
for path in written:
    summary['files'][str(path.relative_to(ROOT))]={'size':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(common/'export-manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':summary['status'],'releaseStatus':summary['releaseStatus'],'pcbCatalog':summary['pcbCatalog'],'nativeBytes':native_file.stat().st_size,'fileCount':len(written),'erc':v['erc']},ensure_ascii=False)[:5500])
