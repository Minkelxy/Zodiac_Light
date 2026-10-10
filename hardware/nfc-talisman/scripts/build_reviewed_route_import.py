"""Build a guarded live API import from the independently audited candidates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
power = json.loads((ROOT / 'electrical/power-route-candidate.json').read_text(encoding='utf-8'))
antenna = json.loads((ROOT / 'electrical/antenna-geometry-review.json').read_text(encoding='utf-8'))['proposal_geometry']
fill = json.loads((ROOT / 'electrical/antenna-coil-fill-candidate.json').read_text(encoding='utf-8'))
assert power['geometry_audit']['all_checked_clearances_meet_route_target']
assert power['geometry_audit']['all_candidate_copper_inside_outline']
assert all(c['connected'] for c in power['connectivity'].values())
assert fill['polygon_valid']

tracks = [{'net': t['net'], 'layer': t['layer'], 'a': t['start_native_mil'], 'b': t['end_native_mil'], 'w': t['width_mm']/0.0254} for t in power['tracks']]
tracks += [{'net': t['semanticNet'], 'layer': t['layer'], 'a': [t['a']['x'], t['a']['y']], 'b': [t['b']['x'], t['b']['y']], 'w': t['width']} for t in antenna['trackGeometry'] if t['semanticNet'] != 'L1_INTERNAL']
vias = [{'net': v['net'], 'x': v['x_native_mil'], 'y': v['y_native_mil'], 'hole': v['drill_mm']/0.0254, 'diameter': v['diameter_mm']/0.0254} for v in power['vias']]
vias += [{'net': v['semanticNet'], 'x': v['x_mil'], 'y': v['y_mil'], 'hole': v['drill_mm']/0.0254, 'diameter': v['diameter_mm']/0.0254} for v in antenna['vias']]
outline = [[s['a']['x'], s['a']['y']] for s in antenna['outlineSegments']]
data = {'tracks': tracks, 'vias': vias, 'fill': fill['points_native_mil'], 'outline': outline}
code = 'const D='+json.dumps(data, separators=(',', ':'))+';\n'+r'''
const CORE='eb14b9eaec4f920c';
await eda.dmt_EditorControl.openDocument(CORE);
await new Promise(r=>setTimeout(r,400));
if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!==CORE)throw Error('Wrong core document');
const oldLines=await eda.pcb_PrimitiveLine.getAll(),oldVias=await eda.pcb_PrimitiveVia.getAll(),oldFills=await eda.pcb_PrimitiveFill.getAll(),oldOutline=await eda.pcb_PrimitivePolyline.getAll(undefined,11);
if(oldLines.length!==19||oldVias.length||oldFills.length||oldOutline.length)throw Error('Unexpected state; refusing duplicate or destructive import');
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error('Missing source backup');
const polygon=pts=>eda.pcb_MathPolygon.createPolygon([pts[0][0],pts[0][1],'L',...pts.slice(1).flat(),pts[0][0],pts[0][1]]);
const created={lines:[],vias:[],fills:[],outlines:[]};
try{
  for(const t of D.tracks){
    const p=await eda.pcb_PrimitiveLine.create(t.net,t.layer,...t.a,...t.b,t.w,false);
    if(!p)throw Error('Line creation failed');
    created.lines.push(p.getState_PrimitiveId());
  }
  for(const v of D.vias){
    const p=await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false);
    if(!p)throw Error('Via creation failed');
    created.vias.push(p.getState_PrimitiveId());
  }
  const coil=await eda.pcb_PrimitiveFill.create(1,polygon(D.fill),'ANT_LA',0,0,false);
  if(!coil)throw Error('Coil fill creation failed');
  created.fills.push(coil.getState_PrimitiveId());
  const outline=await eda.pcb_PrimitivePolyline.create('',11,polygon(D.outline),1,false);
  if(!outline)throw Error('Outline creation failed');
  created.outlines.push(outline.getState_PrimitiveId());
  const saved=await eda.pcb_Document.save();
  if(!saved)throw Error('Save failed');
  await eda.pcb_SelectControl.doSelectPrimitives(created.fills);
  return {created,saved,bridgeConfigured:false,requiresNativeUiBridge:true,sourceBefore:source};
}catch(error){
  const restored=await eda.sys_FileManager.setDocumentSource(source);
  await eda.pcb_Document.save();
  return {success:false,error:String(error),restored,created};
}
'''
path = ROOT / 'scripts/34-import-reviewed-core-routes.js'
path.write_text(code, encoding='utf-8')
print(json.dumps({'script':str(path),'new_lines':len(tracks),'new_vias':len(vias),'fills':1,'outline':1}))
