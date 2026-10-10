// Creates free copper test pads, not purchased components. Read before executing.
const POINTS=[{"ref":"TP1","net":"VOUT","xy":[80.0,115.0],"anchor":"R2.1","segment_mil":[[92.2,140.5],[80.0,115.0]],"layer":"TOP","pad":{"shape":"round","copper_diameter_mm":0.8,"center_mil":[80.0,115.0],"solder_paste":false,"drill":false},"route":{"width_mm":0.2032,"segments_mil":[[[92.2,140.5],[80.0,115.0]]]},"audit":{"coordinate_grid_mil":0.1,"center_radius_from_origin_mm":3.558267134,"entire_pad_within_30mm_diameter_inner_circle":true,"pad_inside_37mm_outline":true,"route_inside_37mm_outline":true,"minimum_pad_to_all_existing_top_copper_mm":0.2604,"closest_existing_copper_to_pad":{"id":"4f30b77742823283","kind":"line","nets":["VOUT"]},"minimum_pad_to_alien_top_component_pad_mm":0.771843769,"closest_alien_pad":{"id":"CT2.2","net":"ANT_LB"},"minimum_route_to_alien_top_copper_mm":1.070246471,"closest_alien_copper_to_route":{"id":"CT2.2","kind":"pad","nets":["ANT_LB"]},"minimum_route_to_alien_component_pad_mm":1.070246471,"closest_alien_pad_to_route":{"id":"CT2.2","net":"ANT_LB"},"route_touches_intended_same_net_anchor":true,"route_overlapping_existing_copper":[{"id":"R2.1","kind":"pad","nets":["VOUT"],"gap_mm":0.0}],"passes_required_0_2mm_clearance":true}},{"ref":"TP2","net":"GND","xy":[235.0,115.0],"anchor":"D2.1","segment_mil":[[222.4,141.7],[235.0,115.0]],"layer":"TOP","pad":{"shape":"round","copper_diameter_mm":0.8,"center_mil":[235.0,115.0],"solder_paste":false,"drill":false},"route":{"width_mm":0.2032,"segments_mil":[[[222.4,141.7],[235.0,115.0]]]},"audit":{"coordinate_grid_mil":0.1,"center_radius_from_origin_mm":6.64538953,"entire_pad_within_30mm_diameter_inner_circle":true,"pad_inside_37mm_outline":true,"route_inside_37mm_outline":true,"minimum_pad_to_all_existing_top_copper_mm":0.350515008,"closest_existing_copper_to_pad":{"id":"D2.1","kind":"pad","nets":["GND"]},"minimum_pad_to_alien_top_component_pad_mm":0.378369335,"closest_alien_pad":{"id":"D2.2","net":"LED2_A"},"minimum_route_to_alien_top_copper_mm":0.531784325,"closest_alien_copper_to_route":{"id":"D2.2","kind":"pad","nets":["LED2_A"]},"minimum_route_to_alien_component_pad_mm":0.531784325,"closest_alien_pad_to_route":{"id":"D2.2","net":"LED2_A"},"route_touches_intended_same_net_anchor":true,"route_overlapping_existing_copper":[{"id":"D2.1","kind":"pad","nets":["GND"],"gap_mm":0.0}],"passes_required_0_2mm_clearance":true}}];
const PROJECT='c051e4069a83472198ecce7729fbd257',MM=1/0.0254;
const DOCS=[['core','eb14b9eaec4f920c',0,36],['panel','4a4719695b24dc2b',50*MM,144]];
const backups=[],changes=[];
try{
  for(const [name,uuid,offset,expectedPads] of DOCS){
    await eda.dmt_EditorControl.openDocument(uuid);
    await new Promise(r=>setTimeout(r,400));
    const info=await eda.dmt_SelectControl.getCurrentDocumentInfo();
    if(info?.uuid!==uuid||info.parentProjectUuid!==PROJECT)throw Error('Wrong document '+name);
    const [pads,lines,vias,components]=await Promise.all([eda.pcb_PrimitivePad.getAll(),eda.pcb_PrimitiveLine.getAll(),eda.pcb_PrimitiveVia.getAll(),eda.pcb_PrimitiveComponent.getAll()]);
    if(pads.length!==expectedPads||lines.length!==124||vias.length!==10||components.length!==15)throw Error('Unexpected reviewed document population: '+name);
    if(pads.some(p=>['TP1','TP2'].includes(p.getState_PadNumber())))throw Error('Test pads already exist');
    const source=await eda.sys_FileManager.getDocumentSource();
    if(!source)throw Error('Backup failed: '+name);
    backups.push({name,uuid,source});
    const created=[];
    for(const tp of POINTS){
      const [x,y]=tp.xy;
      const p=await eda.pcb_PrimitivePad.create(1,tp.ref,x+offset,y+offset,0,['ELLIPSE',0.8*MM,0.8*MM],tp.net,null,0,0,0,false,1,[],{topSolderMask:0.05*MM,topPasteMask:-1000},null,false);
      if(!p)throw Error('Test pad creation failed: '+tp.ref);
      created.push({ref:tp.ref,net:tp.net,padId:p.getState_PrimitiveId()});
      for(const [[sx,sy],[ex,ey]] of tp.route.segments_mil){
        const line=await eda.pcb_PrimitiveLine.create(tp.net,1,sx+offset,sy+offset,ex+offset,ey+offset,tp.route.width_mm*MM,false);
        if(!line)throw Error('Test pad trace creation failed: '+tp.ref);
      }
    }
    if(!await eda.pcb_Document.save())throw Error('Save failed: '+name);
    // This client requires the returned tabId (uuid@project); bare UUID returns false.
    if(!info.tabId||!await eda.dmt_EditorControl.closeDocument(info.tabId))throw Error('Close failed: '+name);
    await eda.dmt_EditorControl.openDocument(uuid);
    await new Promise(r=>setTimeout(r,500));
    const drc=await eda.pcb_Drc.check(true,false,true);
    if(drc.length)throw Error('New DRC findings: '+name+' '+JSON.stringify(drc));
    changes.push({name,uuid,created,savedReopened:true,drc});
  }
  return {status:'applied_and_saved_reopened',changes,sourceBefore:backups};
}catch(error){
  const rollback=[];
  for(const backup of backups.reverse()){
    await eda.dmt_EditorControl.openDocument(backup.uuid);
    rollback.push({name:backup.name,restored:await eda.sys_FileManager.setDocumentSource(backup.source),saved:await eda.pcb_Document.save()});
  }
  return {status:'failed_rolled_back',error:String(error),rollback,sourceBefore:backups};
}
