const PCB='4a4719695b24dc2b';
await eda.dmt_EditorControl.openDocument(PCB);
await new Promise(r=>setTimeout(r,500));
const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(document?.uuid!==PCB)throw Error('Manufacturing panel PCB is not the active document');
const existing=await eda.pcb_PrimitiveLine.getAll();
if(existing.length)throw Error('Panel already contains copper lines; refusing duplicate route import');
const TOP=1,BOTTOM=2,W=8,OFFSET=50/0.0254;
const routes=[
  {net:'SCL',layer:TOP,pts:[[-23.6,-19.7],[-68.8,-70.9]]},
  {net:'SDA',layer:TOP,pts:[[23.6,-19.7],[48,-19.7],[48,-30],[100,-30],[100,-70.9],[128.1,-70.9]]},
  {net:'FD',layer:TOP,pts:[[0,-23.6],[29.7,-137.8]]},
  {net:'LED1_A',layer:TOP,pts:[[-108.1,0],[-108.1,35],[-206.5,35],[-206.5,0]]},
  {net:'LED2_A',layer:TOP,pts:[[167.5,157.5],[167.5,195],[265.7,195],[265.7,157.5]]},
  {net:'LED3_A',layer:BOTTOM,pts:[[-108.1,0],[-108.1,35],[-206.7,35],[-206.7,0]]},
  {net:'LED4_A',layer:BOTTOM,pts:[[167.5,-157.5],[167.5,-195],[265.7,-195],[265.7,-157.5]]}
];
const created=[];
for(const route of routes){
  for(let i=0;i<route.pts.length-1;i++){
    const a=route.pts[i],b=route.pts[i+1];
    const line=await eda.pcb_PrimitiveLine.create(route.net,route.layer,a[0]+OFFSET,a[1]+OFFSET,b[0]+OFFSET,b[1]+OFFSET,W,false);
    if(!line)throw Error('Failed to create panel '+route.net+' segment '+i);
    created.push({net:route.net,layer:route.layer,id:line.getState_PrimitiveId()});
  }
}
const saved=await eda.pcb_Document.save();
if(!saved)throw Error('Panel PCB save failed after route import');
return {pcbUuid:PCB,createdCount:created.length,created,saved,panelOffset_mm:[50,50],width_mil:W,warning:'Panel copper now mirrors only the currently routed core signal/LED branches; antenna and supply/return routing are still absent.'};
