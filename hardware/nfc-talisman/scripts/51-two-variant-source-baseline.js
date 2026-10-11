const PROJECT='c051e4069a83472198ecce7729fbd257';
const boards=[];
for(const [name,uuid] of [['core','eb14b9eaec4f920c'],['horse-sagittarius','4a4719695b24dc2b']]){
  await eda.dmt_EditorControl.openDocument(uuid);
  await new Promise(r=>setTimeout(r,400));
  const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
  if(doc?.uuid!==uuid||doc.parentProjectUuid!==PROJECT)throw Error('Unexpected document');
  const components=await eda.pcb_PrimitiveComponent.getAll();
  const parts=components.map(c=>({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),x:c.getState_X(),y:c.getState_Y(),layer:c.getState_Layer()}));
  const lines=(await eda.pcb_PrimitiveLine.getAll()).map(c=>({id:c.getState_PrimitiveId(),net:c.getState_Net(),layer:c.getState_Layer(),width:c.getState_LineWidth(),start:[c.getState_StartX(),c.getState_StartY()],end:[c.getState_EndX(),c.getState_EndY()]}));
  const pads=[];
  for(const c of components)pads.push({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),pins:await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())});
  const source=await eda.sys_FileManager.getDocumentSource();
  const netlist=await eda.pcb_Net.getNetlist('JLCEDA');
  boards.push({name,uuid,doc,parts,lines,pads,source,netlist});
}
return {project:PROJECT,boards};
