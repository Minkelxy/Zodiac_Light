const PROJECT='c051e4069a83472198ecce7729fbd257',CORE='eb14b9eaec4f920c',SCH='293c7786afd689e8';
const ESYS_Unit={MILLIMETER:'mm'};
if((await eda.dmt_Project.getCurrentProjectInfo())?.uuid!==PROJECT)throw Error('Wrong export project');
await eda.dmt_EditorControl.openDocument(SCH);
const schDoc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(schDoc?.uuid!==SCH)throw Error('Wrong schematic');
const erc=await eda.sch_Drc.check(true,false,true),schematicSource=await eda.sys_FileManager.getDocumentSource();
const boards=[];
function encoded(bytes){let s='';for(let i=0;i<bytes.length;i+=16384)s+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(s);}
for(const [variant,uuid,offset] of [['common',CORE,0],['horse-sagittarius','4a4719695b24dc2b',1968.5039],['snake-leo','fe8ee4534ee0b941',1968.5039]]){
 await eda.dmt_EditorControl.openDocument(uuid);
 const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
 if(doc?.uuid!==uuid||doc.parentProjectUuid!==PROJECT)throw Error('Wrong export target');
 if(!await eda.pcb_Document.save())throw Error('Export save failed');
 await eda.dmt_EditorControl.closeDocument(doc.tabId);await eda.dmt_EditorControl.openDocument(uuid);
 await new Promise(r=>setTimeout(r,500));
 const drc=await eda.pcb_Drc.check(true,false,true);
 if(!Array.isArray(drc)||drc.length)throw Error('Export DRC failed '+variant+' '+JSON.stringify(drc));
 const parts=(await eda.pcb_PrimitiveComponent.getAll()).map(c=>({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),x:c.getState_X(),y:c.getState_Y(),layer:c.getState_Layer(),rotation:c.getState_Rotation()}));
 const lineCount=(await eda.pcb_PrimitiveLine.getAll()).length,viaCount=(await eda.pcb_PrimitiveVia.getAll()).length;
 if(parts.length!==15||![125,126].includes(lineCount)||viaCount!==10)throw Error('Unexpected core population '+JSON.stringify({parts:parts.length,lineCount,viaCount}));
 for(const [a,b] of [['D1','D2'],['D3','D4']]){
  const p=parts.find(p=>p.ref===a),q=parts.find(p=>p.ref===b);
  if(Math.abs(p.x+q.x-2*offset)>.003||Math.abs(p.y-offset)>.003||Math.abs(q.y-offset)>.003)throw Error('LED symmetry export mismatch');
 }
 const pads=[];for(const p of parts)pads.push({ref:p.ref,id:p.id,pins:await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(p.id)});
 const item={variant,uuid,pcbInfo:await eda.dmt_Pcb.getCurrentPcbInfo(),drc,savedReopened:true,lineCount,viaCount,parts,pads,source:await eda.sys_FileManager.getDocumentSource(),netlist:await eda.pcb_Net.getNetlist('JLCEDA')};
 if(variant!=='common'){
  const file=await eda.pcb_ManufactureData.getGerberFile(variant+'-symmetric-draft',true,ESYS_Unit.MILLIMETER,{integerNumber:3,decimalNumber:6},{metallicDrillingInformation:true,nonMetallicDrillingInformation:true,drillTable:true,flyingProbeTestingFile:false});
  if(!file?.size)throw Error('Gerber export unavailable');
  const bom=await eda.pcb_ManufactureData.getBomFile(variant+'-bom-all','csv'),pnp=await eda.pcb_ManufactureData.getPickAndPlaceFile(variant+'-pnp-all','csv',ESYS_Unit.MILLIMETER);
  if(!bom?.size||!pnp?.size)throw Error('Tables export unavailable');
  item.files={gerber:{name:file.name,size:file.size,base64:encoded(new Uint8Array(await file.arrayBuffer()))},bom:{name:bom.name,text:await bom.text()},pnp:{name:pnp.name,text:await pnp.text()}};
 }
 boards.push(item);
}
const native=await eda.sys_FileManager.getProjectFileByProjectUuid(PROJECT,'nfc-two-variants',undefined,'epro2');
if(!native?.size)throw Error('Native project export unavailable');
return {status:'two_variants_design_drafts_exported',project:PROJECT,erc,schematicSource,boards,native:{name:native.name,size:native.size,base64:encoded(new Uint8Array(await native.arrayBuffer()))},pcbCatalog:await eda.dmt_Pcb.getAllPcbsInfo(),releaseStatus:'HOLD_CAM_C1_PHYSICAL_VALIDATION_PENDING'};
