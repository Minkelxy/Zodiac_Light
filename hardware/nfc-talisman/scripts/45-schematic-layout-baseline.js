const SCH='293c7786afd689e8',PROJECT='c051e4069a83472198ecce7729fbd257';
await eda.dmt_EditorControl.openDocument(SCH);
await new Promise(r=>setTimeout(r,400));
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.uuid!==SCH||doc.parentProjectUuid!==PROJECT)throw Error('Wrong schematic');
const source=await eda.sys_FileManager.getDocumentSource();
const components=await eda.sch_PrimitiveComponent.getAll();
const pins=[];
for(const c of components){
  if(!c.getState_Designator())continue;
  pins.push({id:c.getState_PrimitiveId(),ref:c.getState_Designator(),x:c.getState_X(),y:c.getState_Y(),rotation:c.getState_Rotation(),pins:await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())});
}
const file=await eda.sch_ManufactureData.getNetlistFile('layout-baseline','JLCEDA');
const bounds=await eda.dmt_EditorControl.zoomToAllPrimitives(doc.tabId);
await new Promise(r=>setTimeout(r,400));
const blob=await eda.dmt_EditorControl.getCurrentRenderedAreaImage(doc.tabId);
let base64=null;
if(blob){const bytes=new Uint8Array(await blob.arrayBuffer());let s='';for(let i=0;i<bytes.length;i+=16384)s+=String.fromCharCode(...bytes.subarray(i,i+16384));base64=btoa(s);}
return {doc,source,pins,netlist:await file.text(),bounds,base64};
