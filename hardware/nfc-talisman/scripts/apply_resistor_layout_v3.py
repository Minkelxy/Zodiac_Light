import json
from pathlib import Path
from bridge import execute

root=Path(__file__).resolve().parents[1]
plan=json.loads((root/'geometry/resistor-layout-candidate-v3.json').read_text(encoding='utf-8'))
payload={k:plan[k] for k in ['component_moves','route_endpoint_updates']}
code=r"""
const PLAN=__PLAN__;
const PROJECT='c051e4069a83472198ecce7729fbd257',DOCS=[['core','eb14b9eaec4f920c'],['panel','4a4719695b24dc2b']];
const backups=[],changes=[];
function near(a,b){return Math.abs(a-b)<0.003;}
function contract(n){return JSON.stringify(Object.keys(n.components).sort().map(r=>[r,n.components[r].props['Unique ID'],n.components[r].props['Supplier Part'],Object.keys(n.components[r].pinInfoMap).sort().map(p=>[p,n.components[r].pinInfoMap[p].net])]));}
try{
  for(const [name,uuid] of DOCS){
    await eda.dmt_EditorControl.openDocument(uuid);await new Promise(r=>setTimeout(r,400));
    const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
    if(doc?.uuid!==uuid||doc.parentProjectUuid!==PROJECT)throw Error('Wrong PCB');
    const components=await eda.pcb_PrimitiveComponent.getAll(),lines=await eda.pcb_PrimitiveLine.getAll();
    if(components.length!==15||lines.length!==126||(await eda.pcb_PrimitiveVia.getAll()).length!==10)throw Error('Population changed '+name);
    const beforeRaw=await eda.pcb_Net.getNetlist('JLCEDA'),before=JSON.parse(Array.isArray(beforeRaw)?beforeRaw[0]:beforeRaw);
    const selected=[];
    for(const move of PLAN.component_moves){
      const c=components.find(v=>v.getState_PrimitiveId()===move[name+'_component_id']),xy=move['old_'+name+'_xy_mil'];
      if(!c||c.getState_Designator()!==move.ref||!near(c.getState_X(),xy[0])||!near(c.getState_Y(),xy[1]))throw Error('Component moved '+move.ref+' '+name);
      selected.push({c,move});
    }
    for(const route of PLAN.route_endpoint_updates){
      const line=lines.find(v=>v.getState_PrimitiveId()===route[name+'_line_id']),o=route['old_'+name];
      if(!line||line.getState_Net()!==route.net||!near(line.getState_StartX(),o.start[0])||!near(line.getState_StartY(),o.start[1])||!near(line.getState_EndX(),o.end[0])||!near(line.getState_EndY(),o.end[1]))throw Error('Route changed '+route[name+'_line_id']);
    }
    const source=await eda.sys_FileManager.getDocumentSource();if(!source)throw Error('Missing backup');
    backups.push({name,uuid,source});
    for(const {c,move} of selected){
      const xy=move['candidate_'+name+'_xy_mil'],a=c.toAsync();a.setState_X(xy[0]);a.setState_Y(xy[1]);await a.done();
    }
    for(const route of PLAN.route_endpoint_updates){
      const n=route['new_'+name];
      if(!await eda.pcb_PrimitiveLine.modify(route[name+'_line_id'],{startX:n.start[0],startY:n.start[1],endX:n.end[0],endY:n.end[1]}))throw Error('Route update failed');
    }
    if(!await eda.pcb_Document.save()||!await eda.dmt_EditorControl.closeDocument(doc.tabId))throw Error('Save/close failed');
    await eda.dmt_EditorControl.openDocument(uuid);await new Promise(r=>setTimeout(r,500));
    const drc=await eda.pcb_Drc.check(true,false,true);if(drc.length)throw Error('DRC '+name+' '+JSON.stringify(drc));
    const raw=await eda.pcb_Net.getNetlist('JLCEDA'),after=JSON.parse(Array.isArray(raw)?raw[0]:raw);
    if(contract(before)!==contract(after))throw Error('Netlist changed '+name);
    const actual=(await eda.pcb_PrimitiveComponent.getAll()).filter(c=>PLAN.component_moves.some(v=>v.ref===c.getState_Designator())).map(c=>({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),x:c.getState_X(),y:c.getState_Y()}));
    changes.push({name,uuid,drc,netlistContractUnchanged:true,actual,movedComponents:4,correctedRoutes:PLAN.route_endpoint_updates.length,savedReopened:true});
  }
  return {status:'applied_saved_reopened',changes,sourceBefore:backups};
}catch(error){
  const rollback=[];
  for(const b of backups.reverse()){
    await eda.dmt_EditorControl.openDocument(b.uuid);
    const restored=await eda.sys_FileManager.setDocumentSource(b.source),saved=await eda.pcb_Document.save();
    const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();await eda.dmt_EditorControl.closeDocument(doc.tabId);await eda.dmt_EditorControl.openDocument(b.uuid);
    rollback.push({name:b.name,restored,saved});
  }
  return {status:'failed_rolled_back',error:String(error),rollback};
}
""".replace('__PLAN__',json.dumps(payload,separators=(',',':')))
(root/'scripts/48-improve-resistor-layout.js').write_text(code,encoding='utf-8',newline='\n')
r=execute(code,'48-improve-resistor-layout')
result=r.get('result',{})
if result.get('status')=='applied_saved_reopened':
    (root/'eda/layout-application-v3.json').write_text(json.dumps({k:result[k] for k in ['status','changes']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in result.items() if k!='sourceBefore'},ensure_ascii=False))
if not r.get('success') or result.get('status')!='applied_saved_reopened':raise SystemExit(1)
