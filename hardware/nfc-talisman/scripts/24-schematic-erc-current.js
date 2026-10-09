const SCHEMATIC='293c7786afd689e8';
await eda.dmt_EditorControl.openDocument(SCHEMATIC);
await new Promise(r=>setTimeout(r,500));
const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(document?.uuid!==SCHEMATIC)throw Error('Target schematic is not the active document');
const errors=await eda.sch_Drc.check(true,false,true);
const counts={};
for(const item of errors){const key=item.type||item.rule||'unknown';counts[key]=(counts[key]||0)+1;}
return {document,rawCount:errors.length,counts,errors};
