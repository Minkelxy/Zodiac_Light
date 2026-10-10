"""Create the reviewed full-color rear-face object in the live panel."""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'artwork/sagittarius-color-print-candidate.png'
note = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
assert note['size_mm'] == [37, 37] and note['transparent_aperture_expansion_mm'] >= .2
payload = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
code = r'''const DATA=__DATA__;
const PANEL='4a4719695b24dc2b',PROJECT='c051e4069a83472198ecce7729fbd257',MM=1/0.0254;
const EPCB_LayerId={TOP_SILKSCREEN:3};
await eda.dmt_EditorControl.openDocument(PANEL);
await new Promise(r=>setTimeout(r,400));
const info=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(info?.uuid!==PANEL||info.parentProjectUuid!==PROJECT)throw Error('Wrong panel');
if(typeof eda.pcb_PrimitiveObject?.create!=='function')throw Error('Color object API unavailable');
const old=await eda.pcb_PrimitiveObject.getAll();
const silk=await eda.pcb_PrimitivePolyline.getAll(undefined,EPCB_LayerId.TOP_SILKSCREEN);
if(old.length||silk.length!==96)throw Error('Preserve existing user color objects or unexpected source');
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error('No backup');
try{
  const obj=await eda.pcb_PrimitiveObject.create(EPCB_LayerId.TOP_SILKSCREEN,61*MM,42*MM,DATA,37*MM,37*MM,0,false,'sagittarius-color-print-candidate.png',true);
  if(!obj)throw Error('Color object creation failed');
  const id=obj.getState_PrimitiveId();
  if(!await eda.pcb_Document.save())throw Error('Save failed');
  if(!info.tabId||!await eda.dmt_EditorControl.closeDocument(info.tabId))throw Error('Close failed');
  await eda.dmt_EditorControl.openDocument(PANEL);
  await new Promise(r=>setTimeout(r,500));
  const p=await eda.pcb_PrimitiveObject.get(id);
  if(!p)throw Error('Color object absent after reopen');
  const state={id,layer:p.getState_Layer(),x:p.getState_TopLeftX(),y:p.getState_TopLeftY(),width:p.getState_Width(),height:p.getState_Height(),fileName:p.getState_FileName(),dataReference:p.getState_BinaryData()};
  const drc=await eda.pcb_Drc.check(true,false,true);
  if(drc.length)throw Error('DRC findings '+JSON.stringify(drc));
  return {status:'color_object_saved_reopened',state,drc,sourceBefore:source};
}catch(error){
  await eda.dmt_EditorControl.openDocument(PANEL);
  const restored=await eda.sys_FileManager.setDocumentSource(source);
  const saved=await eda.pcb_Document.save();
  return {status:'failed_rolled_back',error:String(error),restored,saved,sourceBefore:source};
}
'''.replace('__DATA__', json.dumps(payload))
target = ROOT / 'scripts/43-import-sagittarius-color-object.js'
target.write_text(code, encoding='utf-8', newline='\n')
print(json.dumps({'path':target.name,'png_bytes':path.stat().st_size,'bbox_native_mm':[61,42,37,37]}))
