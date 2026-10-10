const PROJECT='c051e4069a83472198ecce7729fbd257';
const SCH='293c7786afd689e8',CORE='eb14b9eaec4f920c';
await eda.dmt_EditorControl.openDocument(SCH);
await new Promise(r=>setTimeout(r,400));
const sf=await eda.sch_ManufactureData.getNetlistFile('nfc-schematic','JLCEDA');
if(!sf)throw Error('Schematic netlist unavailable');
const schematic=JSON.parse(await sf.text());
await eda.dmt_EditorControl.openDocument(CORE);
await new Promise(r=>setTimeout(r,400));
const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(document?.uuid!==CORE||document.parentProjectUuid!==PROJECT)throw Error('Target PCB mismatch');
const raw=await eda.pcb_Net.getNetlist('JLCEDA');
const pcb=JSON.parse(Array.isArray(raw)?raw[0]:raw);
const components=await eda.pcb_PrimitiveComponent.getAll();
if(components.length!==15||Object.keys(schematic.components).length!==15)throw Error('Unexpected component set');
for(const comp of components){
  const ref=comp.getState_Designator(),a=schematic.components[ref],b=pcb.components[ref];
  if(!a||!b||comp.getState_UniqueId()!==a.props['Unique ID'])throw Error('Component identity mismatch: '+ref);
  for(const [pin,value] of Object.entries(a.pinInfoMap))if(value.net!==b.pinInfoMap?.[pin]?.net)throw Error('Pin net mismatch: '+ref+'.'+pin);
}
const updated=[];
for(const comp of components){
  const ref=comp.getState_Designator(),channel=schematic.components[ref].props['Channel ID'];
  if(typeof channel!=='string'||!channel)throw Error('Missing schematic channel: '+ref);
  const before=comp.getState_OtherProperty()||{};
  const modified=await eda.pcb_PrimitiveComponent.modify(comp,{otherProperty:{...before,'Channel ID':channel}});
  if(!modified)throw Error('Identity update failed: '+ref);
  updated.push({ref,channel});
}
const save=await eda.pcb_Document.save();
if(!save)throw Error('Core save failed');
const afterRaw=await eda.pcb_Net.getNetlist('JLCEDA');
const after=JSON.parse(Array.isArray(afterRaw)?afterRaw[0]:afterRaw);
const verified=updated.every(x=>after.components[x.ref]?.props['Channel ID']===x.channel);
const drc=await eda.pcb_Drc.check(true,false,true);
return {document,updated,verified,save,drc,source:await eda.sys_FileManager.getDocumentSource()};
