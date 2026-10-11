
const PLAN={"status":"guarded_candidate_not_yet_applied","units":"mil, native Y-up","placement_rule":"Each face has LEDs at (-6mm,0) and (+6mm,0). All resistors, values and antenna remain unchanged.","rejected_candidate":"Diagonal placement of D3 at (-6mm,+4mm) conflicts with the bottom ANT_LA return. Never apply the superseded diagonal candidate.","core_uuid":"eb14b9eaec4f920c","panel_uuid":"4a4719695b24dc2b","project_uuid":"c051e4069a83472198ecce7729fbd257","source_sha256":{"core-source.jsonl":"4a62f975a598dee9c5e073c2aaaa493e30b0e2d18211538f3b3f76761f0e7f0c","horse-sagittarius-panel-source.jsonl":"f4dd00357f56858fe1baf16f7c644d2c18e86b574757f4108cb4fd7f760d5165"},"moves":[{"ref":"D1","core_id":"40d42f6128be4796","panel_id":"baa90f6e7ff9f45a","old_core":[-236,0],"new_core":[-236.2205,0],"old_panel":[1732.5038999999997,1968.5039000000002],"new_panel":[1732.2834,1968.5039]},{"ref":"D2","core_id":"aa8cc903ac6e55fc","panel_id":"cc333413d98268e4","old_core":[236.2205,157.4803],"new_core":[236.2205,0],"old_panel":[2204.7244,2125.9843],"new_panel":[2204.7244,1968.5039]},{"ref":"D4","core_id":"d95eb73f14ed38ec","panel_id":"83b02f15e0095b5e","old_core":[236.2205,-157.4803],"new_core":[236.2205,0],"old_panel":[2204.7244,1811.0236],"new_panel":[2204.7244,1968.5039]}],"routes":[{"core_id":"cc3b2dc18a2814d1","panel_id":"a1e29333583e68c6","net":"LED1_A","layer":1,"width":8,"old_core":[[-206.5,35],[-206.5,0]],"new_core":[[-206.5,35],[-206.7,0]],"old_panel":[[1762.0039,2003.5039000000002],[1762.0039,1968.5039000000002]],"new_panel":[[1762.0039,2003.5039],[1761.8038999999999,1968.5039]]},{"core_id":"5ebe9313374ea1f3","panel_id":"245cc9e388663c9a","net":"GND","layer":1,"width":8,"old_core":[[-265.5,0],[-265,0]],"new_core":[[-265.7,0],[-265,0]],"old_panel":[[1703.0039,1968.5039000000002],[1703.5039000000002,1968.5039000000002]],"new_panel":[[1702.8038999999999,1968.5039],[1703.5039,1968.5039]]},{"core_id":"64287cda6c26192f","panel_id":"cf2235e90487bb34","net":"LED2_A","layer":1,"width":8,"old_core":[[265.7,195],[265.7,157.5]],"new_core":[[265.7,195],[265.7,0]],"old_panel":[[2234.2039,2163.5039],[2234.2039,2126.0039]],"new_panel":[[2234.2039,2163.5038999999997],[2234.2039,1968.5039]]},{"core_id":"5b446c0a0f0ee4f2","panel_id":"3351e2f584b00e2b","net":"LED4_A","layer":2,"width":8,"old_core":[[265.7,-195],[265.7,-157.5]],"new_core":[[265.7,-195],[265.7,0]],"old_panel":[[2234.2039,1773.5039000000002],[2234.2039,1811.0039000000002]],"new_panel":[[2234.2039,1773.5039],[2234.2039,1968.5039]]},{"core_id":"5e1d88265be10c98","panel_id":"a8d72bce7343be27","net":"GND","layer":1,"width":8,"old_core":[[205,155],[206.7,157.5]],"new_core":[[205,155],[206.7,0]],"old_panel":[[2173.5039,2123.5039],[2175.2039,2126.0039]],"new_panel":[[2173.5038999999997,2123.5038999999997],[2175.2039,1968.5039]]},{"core_id":"c90aea079bbd65d9","panel_id":"f6c985c908a74bba","net":"GND","layer":2,"width":8,"old_core":[[205,-155],[206.7,-157.5]],"new_core":[[205,-155],[206.7,0]],"old_panel":[[2173.5039,1813.5039000000002],[2175.2039,1811.0039000000002]],"new_panel":[[2173.5038999999997,1813.5039],[2175.2039,1968.5039]]},{"core_id":"e5a7c0a94d657bca","panel_id":"62c3f53ab2c03094","net":"GND","layer":1,"width":8,"old_core":[[222.40000000000003,141.7],[235,115]],"new_core":[[205,155],[235,115]],"old_panel":[[2190.9039,2110.2039],[2203.5039,2083.5039]],"new_panel":[[2173.5038999999997,2123.5038999999997],[2203.5038999999997,2083.5038999999997]]}],"reference_vias":[{"net":"VOUT","xy_mil":[-145,0]},{"net":"GND","xy_mil":[-280,-15]},{"net":"GND","xy_mil":[205,155]}]},EDMT_EditorDocumentType={PCB:3};
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
