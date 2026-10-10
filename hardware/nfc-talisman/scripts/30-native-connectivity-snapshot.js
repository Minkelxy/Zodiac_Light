const PROJECT='c051e4069a83472198ecce7729fbd257';
const DOCS={schematic:'293c7786afd689e8',core:'eb14b9eaec4f920c',panel:'4a4719695b24dc2b'};
const results={};
for(const [name,uuid] of Object.entries(DOCS)){
  await eda.dmt_EditorControl.openDocument(uuid);
  await new Promise(r=>setTimeout(r,500));
  const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
  if(document?.uuid!==uuid||document.parentProjectUuid!==PROJECT)throw Error('Document mismatch: '+name);
  const source=await eda.sys_FileManager.getDocumentSource();
  if(typeof source!=='string'||!source.length)throw Error('Native source unavailable: '+name);
  if(name==='schematic'){
    const file=await eda.sch_ManufactureData.getNetlistFile('nfc-core-schematic','JLCEDA');
    if(!file)throw Error('Schematic netlist unavailable');
    const components=await eda.sch_PrimitiveComponent.getAll();
    results[name]={document,source,netlist:await file.text(),components:components.map(c=>({id:c.getState_PrimitiveId(),ref:c.getState_Designator(),uniqueId:c.getState_UniqueId(),name:c.getState_Name()}))};
  }else{
    const components=await eda.pcb_PrimitiveComponent.getAll();
    results[name]={document,source,netlist:await eda.pcb_Net.getNetlist('JLCEDA'),components:components.map(c=>({id:c.getState_PrimitiveId(),ref:c.getState_Designator(),uniqueId:c.getState_UniqueId(),name:c.getState_Name()}))};
  }
}
return {project:PROJECT,documents:results};
