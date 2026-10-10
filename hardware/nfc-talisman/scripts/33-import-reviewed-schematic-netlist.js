const SCH='293c7786afd689e8',CORE='eb14b9eaec4f920c';
await eda.dmt_EditorControl.openDocument(SCH);
await new Promise(r=>setTimeout(r,400));
const file=await eda.sch_ManufactureData.getNetlistFile('nfc-schematic','JLCEDA');
if(!file)throw Error('Schematic netlist unavailable');
const text=await file.text(),schematic=JSON.parse(text);
await eda.dmt_EditorControl.openDocument(CORE);
await new Promise(r=>setTimeout(r,400));
if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!==CORE)throw Error('Core PCB mismatch');
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error('Cannot back up active core source');
const snapshot=async()=>{
  const comps=await eda.pcb_PrimitiveComponent.getAll(),lines=await eda.pcb_PrimitiveLine.getAll();
  const pads=await eda.pcb_PrimitivePad.getAll(),vias=await eda.pcb_PrimitiveVia.getAll();
  return {components:comps.map(c=>({id:c.getState_PrimitiveId(),ref:c.getState_Designator(),x:c.getState_X(),y:c.getState_Y(),layer:c.getState_Layer(),rotation:c.getState_Rotation()})).sort((a,b)=>a.id.localeCompare(b.id)),pads:pads.map(p=>({id:p.getState_PrimitiveId(),n:p.getState_PadNumber(),net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y()})).sort((a,b)=>a.id.localeCompare(b.id)),lineIds:lines.map(x=>x.getState_PrimitiveId()).sort(),viaIds:vias.map(x=>x.getState_PrimitiveId()).sort()};
};
const before=await snapshot();
if(before.components.length!==15||before.lineIds.length!==19||Object.keys(schematic.components).length!==15)throw Error('Unexpected pre-sync board state');
const raw=await eda.pcb_Net.getNetlist('JLCEDA'),pcb=JSON.parse(Array.isArray(raw)?raw[0]:raw);
for(const [ref,c] of Object.entries(schematic.components))for(const [pin,v] of Object.entries(c.pinInfoMap))if(v.net!==pcb.components[ref]?.pinInfoMap?.[pin]?.net)throw Error('Pin assignment differs: '+ref+'.'+pin);
const imported=await eda.pcb_Net.setNetlist('JLCEDA',text);
const after=await snapshot();
if(JSON.stringify(before)!==JSON.stringify(after)){
  const restored=await eda.sys_FileManager.setDocumentSource(source);
  if(!restored)throw Error('Import changed geometry and source restoration failed');
  await eda.pcb_Document.save();
  return {imported,geometryPreserved:false,restored,before,after};
}
const saved=await eda.pcb_Document.save();
const drc=await eda.pcb_Drc.check(true,false,true);
return {dialogOpened:imported,requiresNativeUiApply:true,geometryPreservedBeforeUiApply:true,saved,drcBeforeUiApply:drc,sourceBeforeUiApply:await eda.sys_FileManager.getDocumentSource()};
