import json,pathlib
R=pathlib.Path(__file__).resolve().parents[1]
parts=[]
for f in ['05-place-library','08-core-place']:parts+=json.loads((R/'eda/logs'/f'{f}.json').read_text(encoding='utf-8'))['result']['placed']
spec={c['reference']:c for c in json.loads((R/'electrical/netlist.json').read_text(encoding='utf-8'))['components']}
for c in parts:
 for p in c['pins']:
  n=p['padNumber']
  if c['ref'].startswith('D'):n={'1':'K','2':'A'}[n]
  p['net']=spec[c['ref']]['pins'][n]
(R/'eda/core-pads.json').write_text(json.dumps(parts,ensure_ascii=False,indent=2),encoding='utf-8')
code='const parts='+json.dumps(parts,ensure_ascii=False)+';for(const c of parts){const pins=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.id);for(const p of pins){const expected=c.pins.find(x=>x.padNumber===p.getState_PadNumber());p.setState_Net(expected.net);await p.done();}}return {saved:await eda.pcb_Document.save(),source:await eda.sys_FileManager.getDocumentSource()};'
(R/'scripts/09-core-nets.js').write_text(code,encoding='utf-8')
