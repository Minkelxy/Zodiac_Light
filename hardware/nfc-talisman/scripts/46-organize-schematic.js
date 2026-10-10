const SCH='293c7786afd689e8',PROJECT='c051e4069a83472198ecce7729fbd257';
const ESCH_PrimitiveTextAlignMode={CENTER_BOTTOM:6,LEFT_BOTTOM:3};
const N=['ANT_LA','ANT_LB','VOUT','GND','SCL','SDA','FD','LED1_A','LED2_A','LED3_A','LED4_A'];
const L={U1:[400,550,0],C1:[600,555,0],CT1:[160,560,0],CT2:[160,450,0],R5:[400,340,0],R6:[400,270,0],R7:[400,200,0],R1:[760,610,0],D1:[920,610,180],R2:[760,510,0],D2:[920,510,180],R3:[760,410,0],D3:[920,410,180],R4:[760,310,0],D4:[920,310,180]};
function contract(n){return JSON.stringify(Object.keys(n.components).sort().map(ref=>{const c=n.components[ref];return [ref,c.props['Unique ID'],c.props.Device,c.props.Footprint,c.props['Supplier Part'],Object.keys(c.pinInfoMap).sort().map(p=>[p,c.pinInfoMap[p].name,c.pinInfoMap[p].net])]}));}
await eda.dmt_EditorControl.openDocument(SCH);
await new Promise(r=>setTimeout(r,500));
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.uuid!==SCH||doc.parentProjectUuid!==PROJECT)throw Error('Wrong document');
const sourceBefore=await eda.sys_FileManager.getDocumentSource();
const netlistBefore=JSON.parse(await (await eda.sch_ManufactureData.getNetlistFile('before-layout','JLCEDA')).text());
const components=await eda.sch_PrimitiveComponent.getAll();
const physical=components.filter(c=>c.getState_Designator());
const ports=components.filter(c=>!c.getState_Designator()&&N.includes(c.getState_Name()));
const wires=await eda.sch_PrimitiveWire.getAll(),texts=await eda.sch_PrimitiveText.getAll();
const oldWireIds=new Set(sourceBefore.split('\n').map(v=>{try{return JSON.parse(v.split('||')[0])}catch{return null}}).filter(v=>v?.type==='WIRE').map(v=>v.id));
if(physical.length!==15||ports.length!==40||oldWireIds.size!==36||texts.length!==4||Object.keys(L).some(ref=>!physical.some(c=>c.getState_Designator()===ref)))throw Error('Schematic changed since baseline; refusing overwrite');
const beforeErc=await eda.sch_Drc.check(true,false,true);
const created=[];
try{
  const cleared=sourceBefore.split('\n').filter(row=>{
    const m=row.trim().match(/^(\{.*?\})\|\|(\{.*\})\|$/);
    if(!m)return true;
    const h=JSON.parse(m[1]),v=JSON.parse(m[2]);
    return !oldWireIds.has(h.id)&&!oldWireIds.has(v.parentId)&&!oldWireIds.has(v.lineGroup);
  }).join('\n');
  if(!await eda.sys_FileManager.setDocumentSource(cleared)||!await eda.sch_Document.save())throw Error('Old wire removal failed');
  await eda.dmt_EditorControl.closeDocument(doc.tabId);await eda.dmt_EditorControl.openDocument(SCH);await new Promise(r=>setTimeout(r,400));
  if(!await eda.sch_PrimitiveComponent.delete(ports.map(c=>c.getState_PrimitiveId())))throw Error('Port deletion failed');
  if(!await eda.sch_PrimitiveText.delete(texts.map(c=>c.getState_PrimitiveId())))throw Error('Text deletion failed');
  for(const c of physical){
    const ref=c.getState_Designator(),[x,y,rotation]=L[ref],a=c.toAsync();
    a.setState_X(x);a.setState_Y(y);a.setState_Rotation(rotation);await a.done();
    const attrs=await eda.sch_PrimitiveAttribute.getAll(c.getState_PrimitiveId());
    for(const attr of attrs){
      if(attr.getState_Key()==='Designator')await eda.sch_PrimitiveAttribute.modify(attr,{x,y:y+25,rotation:0,fontSize:12,alignMode:ESCH_PrimitiveTextAlignMode.CENTER_BOTTOM,keyVisible:false,valueVisible:true});
      else if(attr.getState_ValueVisible())await eda.sch_PrimitiveAttribute.modify(attr,{valueVisible:false});
    }
  }
  if(!await eda.sch_Document.save())throw Error('Placement save failed');
  if(!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Placement close failed');
  await eda.dmt_EditorControl.openDocument(SCH);await new Promise(r=>setTimeout(r,500));
  const pins={};
  for(const c of await eda.sch_PrimitiveComponent.getAll())if(c.getState_Designator()){
    const p=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
    pins[c.getState_Designator()]=Object.fromEntries(p.map(v=>[v.pinNumber,[Math.round(v.x*1e6)/1e6,Math.round(v.y*1e6)/1e6]]));
  }
  if(pins.D1['2'][0]!==900||pins.D1['1'][0]!==940)throw Error('LED rotated pin coordinates differ '+JSON.stringify(pins.D1));
  const wireLabels={},labelPositions={};
  async function wire(net,points){
    const w=await eda.sch_PrimitiveWire.create(points.flat(),net);
    if(!w)throw Error('Wire creation failed '+net);
    created.push(w.getState_PrimitiveId());
    wireLabels[net]=w.getState_PrimitiveId();
  }
  async function label(net,x,y){
    const a=wireLabels[net];
    if(!a)throw Error('Wire net attribute missing '+net);
    labelPositions[a]={x,y};
  }
  async function text(x,y,value,size=10,bold=false,center=false){
    const t=await eda.sch_PrimitiveText.create(x,y,value,0,null,null,size,bold,false,false,center?ESCH_PrimitiveTextAlignMode.CENTER_BOTTOM:ESCH_PrimitiveTextAlignMode.LEFT_BOTTOM);
    if(!t)throw Error('Text creation failed');
  }
  await text(80,780,'NFC TALISMAN / 37 mm / REV A',20,true);
  await text(80,745,'Passive RF energy harvesting / no battery',11);
  await text(80,700,'ANTENNA / TUNING',13,true);
  await text(310,700,'NTAG / ENERGY',13,true);
  await text(700,700,'FOUR LED BRANCHES',13,true);
  await text(310,390,'I2C / FD PULL-UPS',13,true);
  await wire('ANT_LA',[[80,620],[80,420]]);
  await wire('ANT_LB',[[240,620],[240,420]]);
  for(const ref of ['CT1','CT2']){
    const [a,b]=[pins[ref]['1'],pins[ref]['2']];
    await wire('ANT_LA',[[80,a[1]],a]);await wire('ANT_LB',[b,[240,b[1]]]);
  }
  await label('ANT_LA',80,620);await label('ANT_LB',240,620);
  await text(160,530,'47 pF C0G / 50 V',10,false,true);
  await text(160,420,'TUNE / DNP',10,false,true);
  await text(80,355,'L1: PCB copper antenna');
  await text(80,335,'34 mm / 4 turns');
  await text(80,315,'CT2: leave unpopulated');
  await wire('ANT_LA',[pins.U1['1'],[310,565],[310,625],[280,625]]);await label('ANT_LA',280,625);
  await wire('ANT_LB',[pins.U1['8'],[490,565],[490,625],[520,625]]);await label('ANT_LB',500,625);
  await wire('GND',[pins.U1['2'],[260,555],[260,535]]);
  await eda.sch_PrimitiveComponent.createNetFlag('Ground','GND',260,535);
  await wire('SCL',[pins.U1['3'],[320,545],[320,515],[280,515]]);await label('SCL',280,515);
  await wire('FD',[pins.U1['4'],[330,535],[330,455],[280,455]]);await label('FD',280,455);
  await wire('SDA',[pins.U1['5'],[470,535],[470,480],[510,480]]);await label('SDA',490,480);
  await wire('VOUT',[pins.U1['6'],[460,545],[460,555],[540,555]]);
  await wire('VOUT',[pins.U1['7'],[460,555]]);
  await wire('VOUT',[[540,555],[540,610]]);await eda.sch_PrimitiveComponent.createNetFlag('Power','VOUT',540,610);
  await wire('VOUT',[[540,555],pins.C1['1']]);
  await wire('GND',[pins.C1['2'],[650,555],[650,510]]);await eda.sch_PrimitiveComponent.createNetFlag('Ground','GND',650,510);
  await text(400,665,'NT3H2111W0FHKH',11,false,true);
  await text(600,535,'150 nF / 16 V / X7R',10,false,true);
  await text(545,455,'VCC tied to VOUT');
  await text(545,435,'C1 is the only EH capacitor');
  await text(545,415,'TP1: VOUT / TP2: GND');
  await wire('VOUT',[[320,355],[320,180]]);await eda.sch_PrimitiveComponent.createNetFlag('Power','VOUT',320,355);
  for(const [ref,net] of [['R5','SCL'],['R6','SDA'],['R7','FD']]){
    const a=pins[ref]['1'],b=pins[ref]['2'];await wire('VOUT',[[320,a[1]],a]);await wire(net,[b,[490,b[1]]]);await label(net,460,b[1]);await text(400,a[1]-20,'47 kOhm',10,false,true);
  }
  await text(310,145,'No external I2C host in this build',10);
  await wire('VOUT',[[680,650],[680,290]]);await eda.sch_PrimitiveComponent.createNetFlag('Power','VOUT',680,650);
  await wire('GND',[[1000,630],[1000,270]]);await eda.sch_PrimitiveComponent.createNetFlag('Ground','GND',1000,270);
  for(let n=1;n<=4;n++){
    const r='R'+n,d='D'+n,a=pins[r]['1'],b=pins[r]['2'];
    await wire('VOUT',[[680,a[1]],a]);await wire('LED'+n+'_A',[b,pins[d]['2']]);await wire('GND',[pins[d]['1'],[1000,a[1]]]);
    await text(a[0]+20,a[1]-20,'2.2 kOhm',10,false,true);
    await text(920,a[1]-20,'590 nm yellow',10,false,true);
    await text(1040,a[1],n<=2?'FRONT':'BACK',10);
    if(n===2||n===4)await text(1040,a[1]-20,'Optional DNP',10);
  }
  await text(700,230,'D2 / D4 DNP: low-load build',11,true);
  await text(700,205,'CT1 is a starting value; tune the full stack',10);
  await text(700,185,'Verify VOUT and read/write with LEDs fitted',10);
  if(!await eda.sch_Document.save())throw Error('Wire save failed');
  if(!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Wire close failed');
  await eda.dmt_EditorControl.openDocument(SCH);await new Promise(r=>setTimeout(r,500));
  const wireSet=new Set(created),captionSource=await eda.sys_FileManager.getDocumentSource();
  let captionCount=0,visibleCount=0;const captionSeen=new Set();
  const normalized=captionSource.split('\n').map(row=>{
    const match=row.trim().match(/^(\{.*?\})\|\|(\{.*\})\|$/);
    if(!match)return row;
    const h=JSON.parse(match[1]),v=JSON.parse(match[2]);
    if(h.type!=='ATTR'||v.key!=='NET'||!wireSet.has(v.parentId))return row;
    captionCount++;
    if(captionSeen.has(v.parentId))return null;
    captionSeen.add(v.parentId);v.keyVisible=false;v.valueVisible=false;
    const p=labelPositions[v.parentId];
    if(p){visibleCount++;v.x=p.x;v.y=-p.y;v.rotation=0;v.fontSize=10;v.align='LEFT_BOTTOM';v.valueVisible=true;}
    return JSON.stringify(h)+'||'+JSON.stringify(v)+'|';
  }).filter(row=>row!==null).join('\n');
  if(captionCount!==created.length||visibleCount!==Object.keys(labelPositions).length)throw Error('Native wire caption schema mismatch '+JSON.stringify({captionCount,visibleCount,created:created.length,labels:Object.keys(labelPositions).length,sample:captionSource.split('\n').filter(v=>v.includes('"key":"NET"')).slice(0,2),ids:created.slice(0,2)}));
  if(!await eda.sys_FileManager.setDocumentSource(normalized))throw Error('Caption normalization failed');
  if(!await eda.sch_Document.save())throw Error('Save failed');
  if(!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Close failed');
  await eda.dmt_EditorControl.openDocument(SCH);await new Promise(r=>setTimeout(r,500));
  const erc=await eda.sch_Drc.check(true,false,true);
  const netlistAfter=JSON.parse(await (await eda.sch_ManufactureData.getNetlistFile('after-layout','JLCEDA')).text());
  if(contract(netlistBefore)!==contract(netlistAfter)){
    const a=JSON.parse(contract(netlistBefore)),b=JSON.parse(contract(netlistAfter));
    throw Error('Electrical or library identity changed '+JSON.stringify(a.map((v,i)=>({before:v,after:b[i]})).filter(v=>JSON.stringify(v.before)!==JSON.stringify(v.after))));
  }
  if(erc.length>beforeErc.length)throw Error('New ERC finding '+JSON.stringify(erc));
  const svg=await eda.sch_ManufactureData.getSvgFile('nfc-talisman-schematic');
  return {status:'applied_saved_reopened',sourceBefore,sourceAfter:await eda.sys_FileManager.getDocumentSource(),netlistAfter,netlistContractUnchanged:true,positions:L,pins,erc,svg:svg?await svg.text():null};
}catch(error){
  const sourceAtFailure=await eda.sys_FileManager.getDocumentSource();
  await eda.dmt_EditorControl.openDocument(SCH);
  const restored=await eda.sys_FileManager.setDocumentSource(sourceBefore),saved=await eda.sch_Document.save();
  await eda.dmt_EditorControl.closeDocument(doc.tabId);await eda.dmt_EditorControl.openDocument(SCH);
  return {status:'failed_rolled_back',error:String(error),restored,saved,sourceBefore,sourceAtFailure,created};
}
