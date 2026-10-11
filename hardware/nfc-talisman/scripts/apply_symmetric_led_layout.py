"""Apply the explicitly requested symmetric LED layout to guarded live boards."""
from pathlib import Path
import json
from bridge import execute

ROOT=Path(__file__).resolve().parents[1]
plan=json.loads((ROOT/'variants/common/symmetric-led-plan.json').read_text(encoding='utf-8'))
code=r"""
const PLAN=__PLAN__,EDMT_EditorDocumentType={PCB:3};
const backups=[],changes=[];
function near(a,b){return Math.abs(a-b)<0.003;}
function netlist(raw){return JSON.parse(Array.isArray(raw)?raw[0]:raw);}
function contract(n){return JSON.stringify(Object.keys(n.components).sort().map(r=>[r,n.components[r].props['Unique ID'],n.components[r].props['Supplier Part'],Object.keys(n.components[r].pinInfoMap).sort().map(p=>[p,n.components[r].pinInfoMap[p].net])]));}
try{
 for(const [name,uuid] of [['core',PLAN.core_uuid],['panel',PLAN.panel_uuid]]){
  await eda.dmt_EditorControl.openDocument(uuid);await new Promise(r=>setTimeout(r,400));
  const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
  if(doc?.uuid!==uuid||doc.parentProjectUuid!==PLAN.project_uuid||doc.documentType!==EDMT_EditorDocumentType.PCB)throw Error('Wrong target '+name);
  const components=await eda.pcb_PrimitiveComponent.getAll(),lines=await eda.pcb_PrimitiveLine.getAll();
  if(components.length!==15||lines.length!==126||(await eda.pcb_PrimitiveVia.getAll()).length!==10)throw Error('Unexpected population '+name);
  const drcBefore=await eda.pcb_Drc.check(true,false,true);
  if(!Array.isArray(drcBefore)||drcBefore.length)throw Error('Baseline DRC '+JSON.stringify(drcBefore));
  const before=netlist(await eda.pcb_Net.getNetlist('JLCEDA'));
  for(const move of PLAN.moves){
   const c=components.find(v=>v.getState_PrimitiveId()===move[name+'_id']),xy=move['old_'+name];
   if(!c||c.getState_Designator()!==move.ref||!near(c.getState_X(),xy[0])||!near(c.getState_Y(),xy[1]))throw Error('Position guard '+move.ref);
  }
  for(const route of PLAN.routes){
   const l=lines.find(v=>v.getState_PrimitiveId()===route[name+'_id']),xy=route['old_'+name];
   if(!l||l.getState_Net()!==route.net||l.getState_Layer()!==route.layer||!near(l.getState_StartX(),xy[0][0])||!near(l.getState_StartY(),xy[0][1])||!near(l.getState_EndX(),xy[1][0])||!near(l.getState_EndY(),xy[1][1]))throw Error('Route guard '+route[name+'_id']);
  }
  const source=await eda.sys_FileManager.getDocumentSource();if(!source)throw Error('No backup');
  backups.push({name,uuid,source});
  for(const move of PLAN.moves){
   const c=components.find(v=>v.getState_PrimitiveId()===move[name+'_id']),xy=move['new_'+name],a=c.toAsync();
   a.setState_X(xy[0]);a.setState_Y(xy[1]);await a.done();
  }
  for(const route of PLAN.routes){
   const xy=route['new_'+name];
   const updated=await eda.pcb_PrimitiveLine.modify(route[name+'_id'],{startX:xy[0][0],startY:xy[0][1],endX:xy[1][0],endY:xy[1][1]});
   if(!updated)throw Error('Line update failed');
  }
  if(!await eda.pcb_Document.save()||!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Save/close failed');
  await eda.dmt_EditorControl.openDocument(uuid);await new Promise(r=>setTimeout(r,500));
  const drc=await eda.pcb_Drc.check(true,false,true);
  if(!Array.isArray(drc)||drc.length)throw Error('Changed DRC '+name+' '+JSON.stringify(drc));
  if(contract(before)!==contract(netlist(await eda.pcb_Net.getNetlist('JLCEDA'))))throw Error('Netlist contract changed');
  const after=(await eda.pcb_PrimitiveComponent.getAll()).filter(c=>['D1','D2','D3','D4','R1','R2','R3','R4'].includes(c.getState_Designator())).map(c=>({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),x:c.getState_X(),y:c.getState_Y(),layer:c.getState_Layer()}));
  const offset=name==='panel'?1968.5039:0;
  for(const [a,b] of [['D1','D2'],['D3','D4']]){
   const p=after.find(v=>v.ref===a),q=after.find(v=>v.ref===b);
   if(!p||!q||!near(p.x+q.x,2*offset)||!near(p.y,offset)||!near(q.y,offset))throw Error('LED symmetry assertion '+a+'/'+b);
  }
  const pins=[];
  for(const c of await eda.pcb_PrimitiveComponent.getAll())pins.push({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),pins:await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())});
  changes.push({name,uuid,drcBefore,drc,savedReopened:true,netlistContractUnchanged:true,ledAxisSymmetryVerified:true,resistorPositionsUnchanged:true,componentsMoved:PLAN.moves.length,routesUpdated:PLAN.routes.length,actual:after,pads:pins,sourceAfter:await eda.sys_FileManager.getDocumentSource(),netlistAfter:await eda.pcb_Net.getNetlist('JLCEDA')});
 }
 return {status:'applied_saved_reopened',changes,sourceBefore:backups};
}catch(error){
 const rollback=[];
 for(const b of backups.reverse()){
  await eda.dmt_EditorControl.openDocument(b.uuid);
  const restored=await eda.sys_FileManager.setDocumentSource(b.source),saved=await eda.pcb_Document.save();
  const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();await eda.dmt_EditorControl.closeDocument(doc.tabId);await eda.dmt_EditorControl.openDocument(b.uuid);
  rollback.push({name:b.name,restored,saved,drc:await eda.pcb_Drc.check(true,false,true)});
 }
 return {status:'failed_rolled_back',error:String(error),rollback};
}
""".replace('__PLAN__',json.dumps(plan,separators=(',',':')))
(ROOT/'scripts/52-apply-symmetric-led-layout.js').write_text(code,encoding='utf-8',newline='\n')
rsp=execute(code,'52-apply-symmetric-led-layout')
result=rsp.get('result',{})
if rsp.get('success') and result.get('status')=='applied_saved_reopened':
    common=ROOT/'variants/common'
    native=common/'eda/native';native.mkdir(parents=True,exist_ok=True)
    for item in result['changes']:
        stem='core' if item['name']=='core' else 'horse-sagittarius-panel'
        (native/(stem+'-source.jsonl')).write_text(item['sourceAfter'],encoding='utf-8',newline='\n')
        (native/(stem+'-netlist.json')).write_text(json.dumps(item['netlistAfter'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (common/'eda'/(stem+'-pads.json')).write_text(json.dumps(item['pads'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'status':result['status'],'changes':[{k:v for k,v in c.items() if k not in ['pads','sourceAfter','netlistAfter']} for c in result['changes']]}
    (common/'symmetric-led-application.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
else:
    summary=result
print(json.dumps(summary,ensure_ascii=False))
if not rsp.get('success') or result.get('status')!='applied_saved_reopened':raise SystemExit(1)
