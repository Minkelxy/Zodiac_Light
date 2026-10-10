"""Build a guarded in-place fix for explicit closure of panel routing paths."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
records=[]
# Preserve the open-path input so regeneration does not turn the historical
# correction into a no-op just because the latest panel is already closed.
for line in (ROOT/'eda/native/panel-before-outline-closure-source.jsonl').read_text(encoding='utf-8').splitlines():
    if '||' in line:
        a,b=line.split('||',1)
        records.append((json.loads(a),json.loads(b.rstrip('|'))))
outlines=[{'id':m['id'],'path':d['path']} for m,d in records if m.get('type')=='POLY' and d.get('layerId')==11]
assert len(outlines)==22
for item in outlines:
    assert item['path'][2]=='L' and not any(isinstance(v,str) for v in item['path'][3:])
code='const D='+json.dumps(outlines,separators=(',',':'))+';\n'+r'''
const PANEL='4a4719695b24dc2b';
await eda.dmt_EditorControl.openDocument(PANEL);
await new Promise(r=>setTimeout(r,400));
if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!==PANEL)throw Error('Wrong panel document');
const all=await eda.pcb_PrimitivePolyline.getAll(undefined,11);
const expected=new Set(D.map(x=>x.id.toLowerCase()));
if(all.length!==22||all.some(p=>!expected.has(p.getState_PrimitiveId().toLowerCase())))throw Error('Panel outline population changed');
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error('No panel backup');
try{
  let modified=0;
  for(const o of D){
    const path=[...o.path],first=path.slice(0,2),last=path.slice(-2);
    if(first[0]===last[0]&&first[1]===last[1])continue;
    path.push(...first);
    const p=await eda.pcb_PrimitivePolyline.modify(o.id,{polygon:eda.pcb_MathPolygon.createPolygon(path)});
    if(!p)throw Error('Outline closure failed: '+o.id);
    modified++;
  }
  const saved=await eda.pcb_Document.save();
  if(!saved)throw Error('Save failed');
  return {saved,modified,sourceBefore:source,drc:await eda.pcb_Drc.check(true,false,true)};
}catch(error){
  const restored=await eda.sys_FileManager.setDocumentSource(source);
  await eda.pcb_Document.save();
  return {success:false,error:String(error),restored};
}
'''
(ROOT/'scripts/39-close-panel-routing-outlines.js').write_text(code,encoding='utf-8')
print(json.dumps({'outlines':len(outlines),'explicit_closure':True}))
