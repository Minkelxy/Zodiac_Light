"""Compile a guarded live API operation from reviewed test-point geometry."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
candidate = json.loads((ROOT / 'electrical/testpoint-candidate.json').read_text(encoding='utf-8'))
if not candidate['audit']['candidate_checks_passed'] or {p['ref'] for p in candidate['pads']} != {'TP1', 'TP2'}:
    raise ValueError('Expected two reviewed test-point candidates')
payload = json.dumps(candidate['pads'], ensure_ascii=False, separators=(',', ':'))
code = """// Creates free copper test pads, not purchased components. Read before executing.
const POINTS=__POINTS__;
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
""".replace('__POINTS__', payload)
target=ROOT / 'scripts/40-add-reviewed-testpoints.js'
target.write_text(code, encoding='utf-8')
print(target)
