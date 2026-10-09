const PCB='eb14b9eaec4f920c';
await eda.dmt_EditorControl.openDocument(PCB);
await new Promise(r=>setTimeout(r,500));
const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(document?.uuid!==PCB)throw Error('Core PCB is not the active document');
const existing=await eda.pcb_PrimitiveLine.getAll();
const existingVias=await eda.pcb_PrimitiveVia.getAll();
if(existing.length||existingVias.length)throw Error('Core PCB already contains tracks or vias; refusing duplicate route import');
const TOP=1,BOTTOM=2,W=8;
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
    const line=await eda.pcb_PrimitiveLine.create(route.net,route.layer,a[0],a[1],b[0],b[1],W,false);
    if(!line)throw Error('Failed to create '+route.net+' segment '+i);
    created.push({net:route.net,layer:route.layer,id:line.getState_PrimitiveId(),a,b,width_mil:W});
  }
}
const saved=await eda.pcb_Document.save();
if(!saved)throw Error('Core PCB save failed after route creation');
const report=await eda.pcb_Drc.check(true,false,true);
const drcSummary=report.map(group=>({name:group.name,count:group.count,title:group.title,subgroups:group.list?.map(item=>({name:item.name,count:item.count}))}));
return {pcbUuid:PCB,createdCount:created.length,created,saved,drcGroupCount:report.length,drcSummary,limitations:['Candidate traces were checked offline against saved pad polygons before insertion.', 'Native DRC still includes unconnected VOUT/GND and antenna/net-tie issues; this is not a complete board pass.', 'LED polarity comes from the current library pad map and must be verified at assembly.']};
