const CORE='eb14b9eaec4f920c',MM=1/0.0254;
await eda.dmt_EditorControl.openDocument(CORE);
await new Promise(r=>setTimeout(r,400));
if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!==CORE)throw Error('Wrong core document');
const vias=await eda.pcb_PrimitiveVia.getAll();
if(vias.length!==10)throw Error('Unexpected via population');
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error('No source backup');
const before=vias.map(v=>({id:v.getState_PrimitiveId(),net:v.getState_Net(),x:v.getState_X(),y:v.getState_Y(),drill:v.getState_HoleDiameter(),diameter:v.getState_Diameter()}));
if(before.some(v=>Math.abs(v.drill-0.2*MM)>0.11||Math.abs(v.diameter-0.45*MM)>0.11))throw Error('Expected unmodified 0.2/0.45 mm vias (state getters round to 0.1 mil)');
try{
  for(const v of vias){
    const p=await eda.pcb_PrimitiveVia.modify(v,{holeDiameter:0.3*MM,diameter:0.55*MM});
    if(!p)throw Error('Via modification failed');
  }
  const saved=await eda.pcb_Document.save();
  return {saved,before,drill_mm:0.3,diameter_mm:0.55,drc:await eda.pcb_Drc.check(true,false,true),sourceBefore:source};
}catch(error){
  const restored=await eda.sys_FileManager.setDocumentSource(source);
  await eda.pcb_Document.save();
  return {success:false,error:String(error),restored};
}
