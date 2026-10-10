"""Copy the reviewed core copper into the central panel unit, without its outline."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
records=[]
# Stage 37 precedes the free test points introduced by stage 40. Use its
# preserved stage input instead of the mutable latest native snapshot.
for line in (ROOT/'eda/native/core-after-routing-before-testpoints-source.jsonl').read_text(encoding='utf-8').splitlines():
    if '||' in line:
        meta,body=line.split('||',1)
        records.append((json.loads(meta),json.loads(body.rstrip('|'))))
baseline=(ROOT/'eda/native/core-before-routing-source.jsonl').read_text(encoding='utf-8')
old_ids={json.loads(line.split('||',1)[0]).get('id') for line in baseline.splitlines() if '||' in line}
# EasyEDA splits same-net intersections into new IDs when creating tracks.
# Compare the saved source against the original 19 unchanged signal branches.
tracks=[d for m,d in records if m.get('type')=='LINE' and m.get('id') not in old_ids and d['layerId'] in (1,2)]
vias=[d for m,d in records if m.get('type')=='VIA']
fills=[d for m,d in records if m.get('type')=='FILL']
assert len(tracks)==105 and len(vias)==10 and len(fills)==1
assert fills[0]['isBridgingCopper'] and set(fills[0]['networkList'])=={'ANT_LA','ANT_LB'}
data={'tracks':tracks,'vias':vias,'fill':fills[0]}
code='const D='+json.dumps(data,separators=(',',':'))+';\n'+r'''
const PANEL='4a4719695b24dc2b',OFFSET=50/0.0254;
await eda.dmt_EditorControl.openDocument(PANEL);
await new Promise(r=>setTimeout(r,400));
if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!==PANEL)throw Error('Wrong panel document');
const lines=await eda.pcb_PrimitiveLine.getAll(),vias=await eda.pcb_PrimitiveVia.getAll(),fills=await eda.pcb_PrimitiveFill.getAll();
if(lines.length!==19||vias.length||fills.length)throw Error('Unexpected panel copper; refusing duplicate import');
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error('No panel backup');
const created={lines:[],vias:[],fills:[]};
try{
  for(const t of D.tracks){
    const p=await eda.pcb_PrimitiveLine.create(t.netName,t.layerId,t.startX+OFFSET,t.startY+OFFSET,t.endX+OFFSET,t.endY+OFFSET,t.width,false);
    if(!p)throw Error('Panel line creation failed');
    created.lines.push(p.getState_PrimitiveId());
  }
  for(const v of D.vias){
    const p=await eda.pcb_PrimitiveVia.create(v.netName,v.centerX+OFFSET,v.centerY+OFFSET,v.holeDiameter,v.viaDiameter,0,null,null,false);
    if(!p)throw Error('Panel via creation failed');
    created.vias.push(p.getState_PrimitiveId());
  }
  const path=D.fill.path[0].map(v=>typeof v==='number'?v+OFFSET:v);
  const p=await eda.pcb_PrimitiveFill.create(1,eda.pcb_MathPolygon.createPolygon(path),'ANT_LA',0,D.fill.width,false);
  if(!p)throw Error('Panel coil creation failed');
  created.fills.push(p.getState_PrimitiveId());
  const saved=await eda.pcb_Document.save();
  if(!saved)throw Error('Panel save failed');
  await eda.pcb_SelectControl.doSelectPrimitives(created.fills);
  return {created,saved,panelOffset_mm:[50,50],bridgeConfigured:false,requiresNativeUiBridge:true,sourceBefore:source};
}catch(error){
  const restored=await eda.sys_FileManager.setDocumentSource(source);
  await eda.pcb_Document.save();
  return {success:false,error:String(error),restored,created};
}
'''
(ROOT/'scripts/37-sync-reviewed-panel-copper.js').write_text(code,encoding='utf-8')
print(json.dumps({'new_lines':len(tracks),'new_vias':len(vias),'new_fills':len(fills)}))
