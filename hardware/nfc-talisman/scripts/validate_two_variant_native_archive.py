"""Replay native export records and verify the saved three-PCB design archive."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'variants/common'
file=COMMON/'eda/native/nfc-two-variants.epro2'
with zipfile.ZipFile(file) as archive:
    payload=archive.read(next(n for n in archive.namelist() if n.endswith('.epru'))).decode('utf-8')
documents={}
current=None
tombstones=0
for line in payload.splitlines():
    if '||' not in line:continue
    a,b=line.split('||',1)
    meta=json.loads(a);body=b.rstrip('|')
    if meta['type']=='DOCHEAD':
        head=json.loads(body)
        current=documents.setdefault(head['uuid'],{'head':head,'records':{}})
        continue
    if current is None:continue
    key=(meta['type'],str(meta.get('id','')))
    if not body:
        current['records'].pop(key,None);tombstones+=1
    else:current['records'][key]=json.loads(body)
checks={}
for name,uuid,offset,stars,slots in [('core','eb14b9eaec4f920c',0,0,1),('horse-sagittarius','4a4719695b24dc2b',1968.5039,8,22),('snake-leo','fe8ee4534ee0b941',1968.5039,9,19)]:
    doc=documents[uuid]
    assert doc['head']['docType']=='PCB'
    rs=doc['records']
    parts={d['attrs']['Unique ID']:d for (kind,_),d in rs.items() if kind=='COMPONENT'}
    led={r:[parts[r]['x']-offset,parts[r]['y']-offset] for r in ['D1','D2','D3','D4']}
    assert len(parts)==15
    assert all(abs(led[r][0]-(-236.2205 if r in ['D1','D3'] else 236.2205))<.003 and abs(led[r][1])<.003 for r in led)
    holes=[d for (kind,_),d in rs.items() if kind=='PAD' and ('HIP_' in str(d.get('num','')))]
    polys=[d for (kind,_),d in rs.items() if kind=='POLY' and d.get('layerId')==11]
    objects=[d for (kind,_),d in rs.items() if kind=='OBJ']
    assert len(holes)==stars and all(d.get('plated') is False and abs(d['hole']['width']*.0254-.8)<.0001 for d in holes)
    assert len(polys)==slots
    if offset:
        assert len(objects)==2 and all(abs(d['width']*.0254-37)<.0001 and abs(d['height']*.0254-37)<.0001 and not d['mirror'] for d in objects)
        expect={'front-horse-37mm.png','rear-sagittarius-37mm.png'} if name=='horse-sagittarius' else {'front-snake-37mm.png','rear-leo-37mm.png'}
        assert {d['fileName'] for d in objects}==expect
    checks[name]={'uuid':uuid,'componentCount':len(parts),'ledAnchorMil':led,'starNpthCount':len(holes),'outlineLoopCount':len(polys),'embeddedCoverFiles':[d['fileName'] for d in objects],'passed':True}
blob_doc=documents.get('BLOB',{}).get('records',{})
referenced=[d.get('path','').removeprefix('blob:') for name,uuid,offset,stars,slots in [('horse','4a4719695b24dc2b',1,0,0),('snake','fe8ee4534ee0b941',1,0,0)] for (kind,_),d in documents[uuid]['records'].items() if kind=='OBJ']
blob_ids={ident for (kind,ident) in blob_doc if kind in ['BLOB','META']}
assert set(referenced).issubset(blob_ids), 'Missing embedded artwork BLOB'
report={'status':'passed','nativeFile':str(file.relative_to(ROOT)),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'size':file.stat().st_size,
        'checks':checks,'nativeJournalTombstonesReplayed':tombstones,'referencedCoverBlobsPresent':True,
        'limitations':['Archive structure and saved primitive checks; not an import round-trip or a fabrication approval.']}
(COMMON/'native-archive-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'pcbCount':len(checks),'embeddedCoverBlobs':len(referenced)}))
