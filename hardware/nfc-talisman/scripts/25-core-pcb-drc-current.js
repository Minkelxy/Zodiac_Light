const PCB='eb14b9eaec4f920c';
await eda.dmt_EditorControl.openDocument(PCB);
await new Promise(r=>setTimeout(r,500));
const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(document?.uuid!==PCB)throw Error('Target core PCB is not the active document');
const [components,pads,lines,vias,fills]=await Promise.all([
  eda.pcb_PrimitiveComponent.getAll(),
  eda.pcb_PrimitivePad.getAll(),
  eda.pcb_PrimitiveLine.getAll(),
  eda.pcb_PrimitiveVia.getAll(),
  eda.pcb_PrimitiveFill.getAll()
]);
const drc=await eda.pcb_Drc.check(true,false,true);
return {document,counts:{components:components.length,pads:pads.length,lines:lines.length,vias:vias.length,fills:fills.length},drcGroupCount:drc.length,drc};
