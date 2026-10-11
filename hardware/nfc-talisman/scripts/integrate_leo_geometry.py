"""Replace only managed Sagittarius face apertures in the copied Leo panel."""
from pathlib import Path
import json
from shapely.geometry import LineString
from bridge import execute
from audit_native_copper import load_records

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'variants/common/eda/before-two-variants/snake-leo-copied-source.jsonl'
records=load_records(BASE)
audit=json.loads((ROOT/'manufacturing/draft/star-face-audit.json').read_text(encoding='utf-8'))['native_source']
slots=[s['native_id'] for s in audit['slots']]
silk=[s['native_id'] for s in audit['silkscreen_art_matches']]
pads=[m['id'] for m,d in records if m['type']=='PAD' and str(d.get('num','')).startswith('HIP_')]
assert len(slots)==11 and len(silk)==96 and len(pads)==8
managed=set(slots+silk+pads)
expected=[{'type':m['type'],'id':m['id'],'data':d} for m,d in records if m.get('id') in managed]
assert len(expected)==115
leo=json.loads((ROOT/'variants/snake-leo/leo-geometry.json').read_text(encoding='utf-8'))['constellation']
data={'slots_old':slots,'silk_old':silk,'pads_old':pads,'expected':expected,'stars':leo['stars'],'slots':[]}
for s in leo['physical_slots']:
    ring=LineString([s['centerline_start'],s['centerline_end']]).buffer(s['width_mm']/2,resolution=32).exterior.coords
    data['slots'].append({'id':s['id'],'points':[list(v) for v in ring]})
code=r"""
const D=__DATA__,UUID='fe8ee4534ee0b941',PROJECT='c051e4069a83472198ecce7729fbd257';
const EPCB_LayerId={BOARD_OUTLINE:11,MULTI:12},EPCB_PrimitivePadShapeType={ELLIPSE:'ELLIPSE'},EPCB_PrimitivePadHoleType={ROUND:'ROUND'},EPCB_PrimitivePadType={NORMAL:0},MM=1/0.0254;
await eda.dmt_EditorControl.openDocument(UUID);
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.uuid!==UUID||doc.parentProjectUuid!==PROJECT)throw Error('Wrong Leo target');
const source=await eda.sys_FileManager.getDocumentSource();
function parse(s){return s.split(/\r?\n/).filter(v=>v.includes('||')).map(v=>{const i=v.indexOf('||');return [JSON.parse(v.slice(0,i)),JSON.parse(v.slice(i+2).replace(/\|+$/,''))];});}
const stable=v=>Array.isArray(v)?v.map(stable):(v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])])):v);
const rows=parse(source),removed=new Set([...D.slots_old,...D.silk_old,...D.pads_old]);
for(const e of D.expected){const r=rows.find(v=>v[0].id===e.id&&v[0].type===e.type);if(!r||JSON.stringify(stable(r[1]))!==JSON.stringify(stable(e.data)))throw Error('Face feature changed '+e.id);}
const protectedTypes=new Set(['LINE','VIA','FILL','COMPONENT','ATTR','PAD_NET','PAD','POLY','STRING','OBJ']);
const protect=r=>protectedTypes.has(r[0].type)&&!removed.has(r[0].id);
const signature=rs=>rs.filter(protect).map(r=>JSON.stringify([r[0].type,r[0].id,stable(r[1])])).sort().join('\n');
const protectedBefore=signature(rows);
const drcBefore=await eda.pcb_Drc.check(true,false,true);
if(!Array.isArray(drcBefore)||drcBefore.length)throw Error('Baseline DRC failed');
try{
 if(!await eda.pcb_PrimitivePolyline.delete([...D.slots_old,...D.silk_old]))throw Error('Managed polys deletion');
 if(!await eda.pcb_PrimitivePad.delete(D.pads_old))throw Error('Managed stars deletion');
 const created={stars:[],slots:[]};
 for(const s of D.stars){
  const x=(79.5+s.center_mm[0])*MM,y=(23.5-s.center_mm[1])*MM,diameter=s.diameter_mm*MM;
  const p=await eda.pcb_PrimitivePad.create(EPCB_LayerId.MULTI,'LEO_HIP_'+s.hip,x,y,0,[EPCB_PrimitivePadShapeType.ELLIPSE,diameter,diameter],'',[EPCB_PrimitivePadHoleType.ROUND,diameter],0,0,0,false,EPCB_PrimitivePadType.NORMAL,[],null,null,true);
  if(!p)throw Error('New Leo star failed '+s.hip);
  created.stars.push({hip:s.hip,id:p.getState_PrimitiveId()});
 }
 for(const s of D.slots){
  const pts=s.points.map(p=>[(79.5+p[0])*MM,(23.5-p[1])*MM]),path=[pts[0][0],pts[0][1],'L',...pts.slice(1).flat()];
  const polygon=eda.pcb_MathPolygon.createPolygon(path);
  if(!polygon)throw Error('New Leo slot polygon');
  const p=await eda.pcb_PrimitivePolyline.create('',EPCB_LayerId.BOARD_OUTLINE,polygon,.1*MM,true);
  if(!p)throw Error('New Leo slot failed '+s.id);
  created.slots.push({slot:s.id,id:p.getState_PrimitiveId()});
 }
 if(!await eda.pcb_Document.save())throw Error('Save Leo failed');
 await eda.dmt_EditorControl.closeDocument(doc.tabId);await eda.dmt_EditorControl.openDocument(UUID);
 await new Promise(r=>setTimeout(r,500));
 const sourceAfter=await eda.sys_FileManager.getDocumentSource(),after=parse(sourceAfter);
 const newlyCreated=new Set([...created.stars,...created.slots].map(v=>v.id));
 if(signature(after.filter(r=>!newlyCreated.has(r[0].id)))!==protectedBefore)throw Error('Protected copper, parts or mechanical geometry changed');
 const drc=await eda.pcb_Drc.check(true,false,true);
 if(!Array.isArray(drc)||drc.length)throw Error('Leo DRC failed '+JSON.stringify(drc));
 return {status:'leo_geometry_integrated_saved_reopened',uuid:UUID,created,removed:{stars:D.pads_old.length,slots:D.slots_old.length,silkscreen:D.silk_old.length},protectedPrimitivesUnchanged:true,drcBefore,drc,sourceAfter};
}catch(error){
 await eda.dmt_EditorControl.openDocument(UUID);
 const restored=await eda.sys_FileManager.setDocumentSource(source),saved=await eda.pcb_Document.save();
 return {status:'failed_rolled_back',error:String(error),restored,saved};
}
""".replace('__DATA__',json.dumps(data,separators=(',',':')))
(ROOT/'scripts/54-integrate-leo-geometry.js').write_text(code,encoding='utf-8',newline='\n')
r=execute(code,'54-integrate-leo-geometry')
v=r.get('result',{})
if r.get('success') and v.get('status')=='leo_geometry_integrated_saved_reopened':
    n=ROOT/'variants/common/eda/native'
    (n/'snake-leo-panel-source.jsonl').write_text(v['sourceAfter'],encoding='utf-8',newline='\n')
    summary={k:x for k,x in v.items() if k!='sourceAfter'}
    (ROOT/'variants/snake-leo/eda-integration.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
else:summary=v or r
print(json.dumps(summary,ensure_ascii=False))
if v.get('status')!='leo_geometry_integrated_saved_reopened':raise SystemExit(1)
