const PCB='4a4719695b24dc2b';
await eda.dmt_EditorControl.openDocument(PCB);
await new Promise(r=>setTimeout(r,400));
const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(document?.uuid!==PCB)throw Error('Panel PCB is not active');
const pads=await eda.pcb_PrimitivePad.getAll();
return {document,padCount:pads.length,methods:Object.getOwnPropertyNames(Object.getPrototypeOf(pads[0])).filter(x=>x.startsWith('getState_')),drilled:pads.map(p=>({id:p.getState_PrimitiveId(),primitiveType:p.getState_PrimitiveType(),padNumber:p.getState_PadNumber(),net:p.getState_Net(),hole:p.getState_Hole?.(),x:p.getState_X?.(),y:p.getState_Y?.(),pad:p.getState_Pad?.()})).filter(p=>p.hole)};
