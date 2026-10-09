const D={"parts":[["U1","C710403",0.0,0.0,0,"TOP"],["D1","C5875720",-5.9944,0.0,0,"TOP"],["C1","C162182",2.5,0.0,0,"TOP"],["CT1","C60137",-1.8,2.5,0,"TOP"],["CT2","C60137",0.2,2.5,0,"TOP"],["R5","C105579",-2.5,-1.8,0,"TOP"],["R6","C105579",2.5,-1.8,0,"TOP"],["R7","C105579",0.0,-3.5,0,"TOP"],["R1","C114662",-3.5,0.0,0,"TOP"],["R2","C114662",3.5,4.0,0,"TOP"],["D2","C5875720",6.0,4.0,0,"TOP"],["R3","C114662",-3.5,0.0,0,"BOTTOM"],["D3","C5875720",-6.0,0.0,0,"BOTTOM"],["R4","C114662",3.5,-4.0,0,"BOTTOM"],["D4","C5875720",6.0,-4.0,0,"BOTTOM"]],"nets":{"U1":{"1":"ANT_LA","2":"GND","3":"SCL","4":"FD","5":"SDA","6":"VOUT","7":"VOUT","8":"ANT_LB"},"L1":{"1":"ANT_LA","2":"ANT_LB"},"C1":{"1":"VOUT","2":"GND"},"CT1":{"1":"ANT_LA","2":"ANT_LB"},"CT2":{"1":"ANT_LA","2":"ANT_LB"},"R5":{"1":"VOUT","2":"SCL"},"R6":{"1":"VOUT","2":"SDA"},"R7":{"1":"VOUT","2":"FD"},"TP1":{"1":"VOUT"},"TP2":{"1":"GND"},"R1":{"1":"VOUT","2":"LED1_A"},"D1":{"A":"LED1_A","K":"GND"},"R2":{"1":"VOUT","2":"LED2_A"},"D2":{"A":"LED2_A","K":"GND"},"R3":{"1":"VOUT","2":"LED3_A"},"D3":{"A":"LED3_A","K":"GND"},"R4":{"1":"VOUT","2":"LED4_A"},"D4":{"A":"LED4_A","K":"GND"}}};
const PANEL="4a4719695b24dc2b";
const MM=1/0.0254;
const L={TOP:1,BOTTOM:2,TOP_SILK:3,BOTTOM_SILK:4,TOP_MASK:5,BOTTOM_MASK:6,OUTLINE:11,MULTI:12};
const xy=(x,y)=>[x*MM,(100-y)*MM];
const poly=(pts,center=[0,0])=>{
  if(!Array.isArray(pts)||pts.length<3)throw Error('polygon needs >=3 points');
  const first=xy(pts[0][0]+center[0],pts[0][1]+center[1]);
  const src=[first[0],first[1],'L'];
  for(const p of pts.slice(1)){const q=xy(p[0]+center[0],p[1]+center[1]);src.push(q[0],q[1]);}
  const result=eda.pcb_MathPolygon.createPolygon(src);
  if(!result)throw Error('createPolygon failed');
  return result;
};
const active=await eda.dmt_EditorControl.openDocument(PANEL);
await new Promise(r=>setTimeout(r,800));
const info=await eda.dmt_Pcb.getCurrentPcbInfo();
if(info?.uuid!==PANEL)throw Error('active PCB mismatch: '+JSON.stringify(info));
const oldComponents=await eda.pcb_PrimitiveComponent.getAll();
if(oldComponents.length)throw Error('Panel already contains components; refusing duplicate placement');
const lib=await eda.lib_LibrariesList.getSystemLibraryUuid(),byCode={},created=[];
for(const [ref,code,dx,dy,rot,side] of D.parts){
  if(!byCode[code]){
    const found=await eda.lib_Device.searchByProperties({supplierId:code},undefined,undefined,undefined,5,1);
    if(!found?.length)throw Error('device not found: '+code);
    byCode[code]=found[0];
  }
  const x=(50+dx)*MM,y=(50+dy)*MM;
  const comp=await eda.pcb_PrimitiveComponent.create({libraryUuid:lib,uuid:byCode[code].uuid},side==='BOTTOM'?L.BOTTOM:L.TOP,x,y,rot,false);
  if(!comp)throw Error('component placement failed: '+ref);
  await eda.pcb_PrimitiveComponent.modify(comp,{designator:ref,name:ref==='CT2'?'TUNE C0G DNP':byCode[code].name,uniqueId:ref,otherProperty:{Population:ref==='CT2'?'DNP':'Fit','PCB Side':side}});
  const pins=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(comp.getState_PrimitiveId()),expected=D.nets[ref];
  for(const pin of pins){
    const number=String(pin.getState_PadNumber()),key=ref.startsWith('D')?({'1':'K','2':'A'}[number]):number,net=expected?.[key];
    if(!net)throw Error('net mapping missing for '+ref+'.'+number);
    pin.setState_Net(net);await pin.done();
  }
  created.push({ref,id:comp.getState_PrimitiveId(),padCount:pins.length});
}
const save=await eda.pcb_Document.save();
return {uuid:info.uuid,createdCount:created.length,created,save,warning:'PCB antenna spiral bridge-fill is not yet imported; VOUT/GND routing remains incomplete.'};