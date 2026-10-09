const PCB='eb14b9eaec4f920c';
await eda.dmt_EditorControl.openDocument(PCB);
await new Promise(r=>setTimeout(r,400));
const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(document?.uuid!==PCB)throw Error('Core PCB is not the active document');
const lines=await eda.pcb_PrimitiveLine.getAll();
return {
  pcbUuid:PCB,
  lineCount:lines.length,
  lines:lines.map(l=>({
    id:l.getState_PrimitiveId(),
    net:l.getState_Net(),
    layer:l.getState_Layer(),
    start:[l.getState_StartX(),l.getState_StartY()],
    end:[l.getState_EndX(),l.getState_EndY()],
    width:l.getState_LineWidth()
  }))
};
