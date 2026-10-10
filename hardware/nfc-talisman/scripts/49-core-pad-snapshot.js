await eda.dmt_EditorControl.openDocument('eb14b9eaec4f920c');await new Promise(r=>setTimeout(r,400));
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.uuid!=='eb14b9eaec4f920c'||doc.parentProjectUuid!=='c051e4069a83472198ecce7729fbd257')throw Error('Wrong core');
const components=await eda.pcb_PrimitiveComponent.getAll(),pads=[];
for(const c of components)pads.push({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),pins:await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())});
if(pads.length!==15||pads.reduce((n,c)=>n+c.pins.length,0)!==36)throw Error('Unexpected pad population');
return {doc,pads};
