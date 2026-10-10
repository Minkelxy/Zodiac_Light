const SCH='293c7786afd689e8',PROJECT='c051e4069a83472198ecce7729fbd257';
const obsolete=new Set(['dd637db419e89c42','defe2a1e6e74f6da','d1cac70625a38b36','0375267b02432be5']);
await eda.dmt_EditorControl.openDocument(SCH);await new Promise(r=>setTimeout(r,400));
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.uuid!==SCH||doc.parentProjectUuid!==PROJECT)throw Error('Wrong schematic');
const sourceBefore=await eda.sys_FileManager.getDocumentSource();
const before=JSON.parse(await (await eda.sch_ManufactureData.getNetlistFile('before-style','JLCEDA')).text());
function pins(n){return JSON.stringify(Object.keys(n.components).sort().map(r=>[r,Object.keys(n.components[r].pinInfoMap).sort().map(p=>[p,n.components[r].pinInfoMap[p].net])]));}
const parents=new Set((await eda.sch_PrimitiveComponent.getAll()).filter(c=>c.getState_Designator()).map(c=>c.getState_PrimitiveId()));
let changed=0,removed=0;
try{
  const updated=sourceBefore.split('\n').map(row=>{
    const m=row.trim().match(/^(\{.*?\})\|\|(\{.*\})\|?$/);if(!m)return row;
    const h=JSON.parse(m[1]),v=JSON.parse(m[2]);
    if(obsolete.has(h.id)){removed++;return null;}
    if(h.type==='ATTR'&&v.key==='Designator'&&parents.has(v.parentId)){v.fontSize=12;changed++;}
    if(h.type==='TEXT'&&v.value==='Verify VOUT and read/write with LEDs fitted'){v.value='Bench check: LED load and read/write stability';v.y=-250;}
    if(h.type==='TEXT'&&v.value==='590 nm yellow'){
      const ledY=[610,510,410,310].find(y=>Math.abs(v.y+y-20)<0.1);
      if(ledY!==undefined)v.y=-ledY+30;
    }
    if(h.type==='TEXT'&&v.value==='CT1 is a starting value; tune the full stack'){v.value='Tune CT1 and verify VOUT / NFC on the full stack';v.y=-210;}
    if(h.type==='TEXT'&&v.value==='No external I2C host in this build')v.value='No I2C host fitted';
    return JSON.stringify(h)+'||'+JSON.stringify(v)+'|';
  }).filter(v=>v!==null).join('\n').replace(/\|$/,'');
  if(changed!==15)throw Error('Unexpected designator count');
  if(!await eda.sys_FileManager.setDocumentSource(updated)||!await eda.sch_Document.save())throw Error('Appearance save failed');
  await eda.dmt_EditorControl.closeDocument(doc.tabId);await eda.dmt_EditorControl.openDocument(SCH);await new Promise(r=>setTimeout(r,400));
  const erc=await eda.sch_Drc.check(true,false,true);
  const after=JSON.parse(await (await eda.sch_ManufactureData.getNetlistFile('after-style','JLCEDA')).text());
  if(pins(before)!==pins(after)||erc.some(v=>v.type==='error')||erc.some(v=>v.rule!=='ATTRMATCHCODE'))throw Error('Verification failed');
  const svg=await eda.sch_ManufactureData.getSvgFile('nfc-talisman-schematic');
  return {status:'applied_saved_reopened',designators:changed,removed,netlistContractUnchanged:true,erc,sourceAfter:await eda.sys_FileManager.getDocumentSource(),svg:await svg.text()};
}catch(error){
  const restored=await eda.sys_FileManager.setDocumentSource(sourceBefore),saved=await eda.sch_Document.save();
  await eda.dmt_EditorControl.closeDocument(doc.tabId);await eda.dmt_EditorControl.openDocument(SCH);
  return {status:'failed_rolled_back',error:String(error),restored,saved,sourceBefore};
}
