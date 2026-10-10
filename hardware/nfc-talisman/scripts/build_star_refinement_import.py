"""Compile a guarded, reversible live update of only Sagittarius slots/ink."""
import json
from pathlib import Path
from shapely.geometry import Polygon
from audit_manufacturing_draft import read_native_objects

ROOT = Path(__file__).resolve().parents[1]
MM = 1 / 0.0254
original = json.loads((ROOT / 'geometry/sagittarius-before-refinement.json').read_text(encoding='utf-8'))
design = json.loads((ROOT / 'geometry/design.json').read_text(encoding='utf-8'))
art = json.loads((ROOT / 'artwork/art_data.json').read_text(encoding='utf-8'))
records = list(read_native_objects(ROOT / 'eda/native/panel-before-star-refinement-source.jsonl'))
outlines = [(m, d) for m, d in records if m.get('type') == 'POLY' and d.get('layerId') == 11]
board = next(b for b in design['boards'] if b['id'] == 'sagittarius5')
assert len(outlines) == 22

def source_shape(path):
    assert path[2] == 'L' and not any(isinstance(v, str) for v in path[3:])
    pairs = [path[:2]] + [path[i:i+2] for i in range(3, len(path), 2)]
    return Polygon([(x * 0.0254, 100-y * 0.0254) for x, y in pairs])

def native_path(points):
    first = [round(points[0][0]*MM, 4), round((100-points[0][1])*MM, 4)]
    path = first + ['L']
    for x, y in points[1:]:
        path += [round(x*MM, 4), round((100-y)*MM, 4)]
    return path

changes = []
for old in original['board']['cutouts']:
    if old['type'] != 'constellation_slot':
        continue
    shape = Polygon(old['ring'])
    distance, meta, data = min((shape.hausdorff_distance(source_shape(d['path'])), m, d)
                               for m, d in outlines)
    if distance > 0.004:
        raise ValueError(f"Old slot not matched: {old['id']} {distance}")
    new = next(c for c in board['cutouts'] if c['id'] == old['id'])
    poly = Polygon(new['ring']).simplify(0.003, preserve_topology=True)
    assert poly.is_valid and len(poly.interiors) == 0
    changes.append({'id': meta['id'], 'edge': old['id'], 'before': data['path'],
                    'after': native_path(list(poly.exterior.coords))})
assert len(changes) == 11 and len({c['id'] for c in changes}) == 11
additions = [s for s in art['sagittarius_silkscreen'] if s['id'].startswith(('star_rim_', 'star_link_'))]
assert len(additions) == 30 and len(art['sagittarius_silkscreen']) == 96
strokes = []
for s in additions:
    points = s['points'] + ([s['points'][0]] if s['closed'] else [])
    pts = [(x+board['center'][0], y+board['center'][1]) for x, y in points]
    strokes.append({'id': s['id'], 'path': native_path(pts), 'width': s['width_mm']*MM})

# All original drawing objects must still match the saved input. This also
# protects any user-added horse art from an obsolete automation update.
types = {'COMPONENT', 'PRIMITIVE', 'ATTR', 'PAD_NET', 'PAD', 'LINE', 'VIA', 'FILL', 'POLY', 'IMAGE'}
expected = [[m, d] for m, d in records if m.get('type') in types]
payload = json.dumps({'changes': changes, 'strokes': strokes, 'expected': expected}, separators=(',', ':'))
code = r'''const D=__PAYLOAD__;
const PANEL='4a4719695b24dc2b',PROJECT='c051e4069a83472198ecce7729fbd257';
const EPCB_LayerId={BOARD_OUTLINE:11,TOP_SILKSCREEN:3};
await eda.dmt_EditorControl.openDocument(PANEL);
await new Promise(r=>setTimeout(r,400));
const info=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(info?.uuid!==PANEL||info.parentProjectUuid!==PROJECT)throw Error('Wrong panel document');
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error('No source backup');
const stable=v=>Array.isArray(v)?v.map(stable):(v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])])):v);
const types=new Set(D.expected.map(r=>r[0].type));
types.add('IMAGE');
const current=source.split(/\r?\n/).filter(s=>s.includes('||')).map(s=>{const i=s.indexOf('||');return [JSON.parse(s.slice(0,i)),JSON.parse(s.slice(i+2).replace(/\|+$/,''))]}).filter(r=>types.has(r[0].type));
const signature=r=>r.map(v=>JSON.stringify(stable(v))).sort().join('\n');
if(signature(current)!==signature(D.expected))throw Error('Original drawing changed; preserve user edits and regenerate review');
const all=await eda.pcb_PrimitivePolyline.getAll();
if(all.length!==88||all.filter(p=>p.getState_Layer()===EPCB_LayerId.BOARD_OUTLINE).length!==22)throw Error('Unexpected panel primitive population');
const created=[];
try{
  for(const c of D.changes){
    const p=await eda.pcb_PrimitivePolyline.get(c.id);
    if(!p||p.getState_Layer()!==EPCB_LayerId.BOARD_OUTLINE)throw Error('Missing slot '+c.edge);
    const a=p.toAsync();
    a.setState_Polygon(eda.pcb_MathPolygon.createPolygon(c.after));
    await a.done();
  }
  for(const s of D.strokes){
    const p=await eda.pcb_PrimitivePolyline.create('',EPCB_LayerId.TOP_SILKSCREEN,eda.pcb_MathPolygon.createPolygon(s.path),s.width,false);
    if(!p)throw Error('Failed ink '+s.id);
    created.push({id:s.id,primitiveId:p.getState_PrimitiveId()});
  }
  if(!await eda.pcb_Document.save())throw Error('Save failed');
  if(!info.tabId||!await eda.dmt_EditorControl.closeDocument(info.tabId))throw Error('Close failed');
  await eda.dmt_EditorControl.openDocument(PANEL);
  await new Promise(r=>setTimeout(r,500));
  const drc=await eda.pcb_Drc.check(true,false,true);
  if(drc.length)throw Error('DRC findings '+JSON.stringify(drc));
  return {status:'applied_saved_reopened',changedSlots:D.changes.map(c=>({edge:c.edge,id:c.id})),created,savedReopened:true,drc,sourceBefore:source};
}catch(error){
  await eda.dmt_EditorControl.openDocument(PANEL);
  const restored=await eda.sys_FileManager.setDocumentSource(source);
  const saved=await eda.pcb_Document.save();
  return {status:'failed_rolled_back',error:String(error),restored,saved,sourceBefore:source};
}
'''.replace('__PAYLOAD__', payload)
target = ROOT / 'scripts/42-refine-star-slots-and-silkscreen.js'
target.write_text(code, encoding='utf-8', newline='\n')
print(json.dumps({'changed_slots': len(changes), 'new_silk_paths': len(strokes), 'bytes': target.stat().st_size}))
