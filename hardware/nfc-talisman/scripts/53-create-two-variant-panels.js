const PROJECT='c051e4069a83472198ecce7729fbd257',HORSE='4a4719695b24dc2b',CORE='eb14b9eaec4f920c';
if((await eda.dmt_Project.getCurrentProjectInfo())?.uuid!==PROJECT)throw Error('Wrong project');
await eda.dmt_EditorControl.openDocument(HORSE);
if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!==HORSE)throw Error('Wrong source');
if(!await eda.pcb_Document.save())throw Error('Save source failed');
const existing=(await eda.dmt_Pcb.getAllPcbsInfo()).filter(p=>p.name.toLowerCase()==='snake-leo-100');
if(existing.length>1)throw Error('Duplicate second panel');
const previousCopy=(await eda.dmt_Pcb.getAllPcbsInfo()).find(p=>p.uuid==='fe8ee4534ee0b941');
const SNAKE=existing[0]?.uuid||previousCopy?.uuid||await eda.dmt_Pcb.copyPcb(HORSE);
if(!SNAKE||SNAKE===HORSE||SNAKE===CORE)throw Error('Copy failed');
await new Promise(r=>setTimeout(r,1500));
const names=[[HORSE,'Horse-Sagittarius-100'],[SNAKE,'Snake-Leo-100'],[CORE,'NFC-Core-37']];
const naming=[];
for(const [uuid,name] of names){
 await eda.dmt_EditorControl.openDocument(uuid);
 await new Promise(r=>setTimeout(r,500));
 if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!==uuid)throw Error('Wrong rename target');
 const currentName=(await eda.dmt_Pcb.getAllPcbsInfo()).find(p=>p.uuid===uuid)?.name;
 const renameAttempt=currentName?.toLowerCase()===name.toLowerCase()||await eda.dmt_Pcb.modifyPcbName(uuid,name);
 if(!await eda.pcb_Document.save())throw Error('Save renamed target failed');
 let verified=false;
 for(let attempt=0;attempt<3;attempt++){
  await new Promise(r=>setTimeout(r,1000));
  if((await eda.dmt_Pcb.getAllPcbsInfo()).find(p=>p.uuid===uuid)?.name.toLowerCase()===name.toLowerCase()){verified=true;break;}
 }
 naming.push({uuid,requested:name,renameAttempt,verified,actual:(await eda.dmt_Pcb.getAllPcbsInfo()).find(p=>p.uuid===uuid)?.name});
}
await eda.dmt_EditorControl.openDocument(SNAKE);
const drc=await eda.pcb_Drc.check(true,false,true);
if(!Array.isArray(drc)||drc.length)throw Error('Copied panel DRC failed '+JSON.stringify(drc));
return {status:'two_panel_documents_created',project:PROJECT,core:CORE,horse:HORSE,snake:SNAKE,naming,names:await eda.dmt_Pcb.getAllPcbsInfo(),drc,source:await eda.sys_FileManager.getDocumentSource()};
