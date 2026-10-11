"""Compile the guarded shared-core LED-only left/right symmetric plan."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'variants/common/eda/before-two-variants'
OUT = ROOT / 'variants/common'
SHIFT = 1968.5039


def main():
    core = json.loads((BASE / 'core-state.json').read_text(encoding='utf-8'))
    panel = json.loads((BASE / 'horse-sagittarius-panel-state.json').read_text(encoding='utf-8'))
    moves = []
    targets = {'D1': [-236.2205, 0], 'D2': [236.2205, 0],
               'D4': [236.2205, 0]}
    for ref, xy in targets.items():
        a = next(c for c in core['parts'] if c['ref'] == ref)
        b = next(c for c in panel['parts'] if c['ref'] == ref)
        assert abs(b['x']-a['x']-SHIFT) < .003 and abs(b['y']-a['y']-SHIFT) < .003
        moves.append({'ref': ref, 'core_id': a['id'], 'panel_id': b['id'],
                      'old_core': [a['x'],a['y']], 'new_core': xy,
                      'old_panel': [b['x'],b['y']], 'new_panel': [v+SHIFT for v in xy]})
    new_lines = {
        'cc3b2dc18a2814d1': [[-206.5,35],[-206.7,0]],
        '5ebe9313374ea1f3': [[-265.7,0],[-265,0]],
        '64287cda6c26192f': [[265.7,195],[265.7,0]],
        '5b446c0a0f0ee4f2': [[265.7,-195],[265.7,0]],
        '5e1d88265be10c98': [[205,155],[206.7,0]],
        'c90aea079bbd65d9': [[205,-155],[206.7,0]],
        'e5a7c0a94d657bca': [[205,155],[235,115]],
    }
    routes = []
    for ident, xy in new_lines.items():
        old = next(l for l in core['lines'] if l['id'] == ident)
        candidates = [l for l in panel['lines'] if l['net']==old['net'] and l['layer']==old['layer']
                      and all(abs(l[k][i]-old[k][i]-SHIFT)<.003 for k in ['start','end'] for i in [0,1])]
        assert len(candidates)==1, (ident, candidates)
        counterpart=candidates[0]
        routes.append({'core_id': ident, 'panel_id': counterpart['id'], 'net': old['net'],
                       'layer': old['layer'], 'width': old['width'],
                       'old_core': [old['start'],old['end']], 'new_core': xy,
                       'old_panel': [counterpart['start'],counterpart['end']],
                       'new_panel': [[v+SHIFT for v in p] for p in xy]})
    plan = {'status':'guarded_candidate_not_yet_applied','units':'mil, native Y-up',
            'placement_rule':'Each face has LEDs at (-6mm,0) and (+6mm,0). All resistors, values and antenna remain unchanged.',
            'rejected_candidate':'Diagonal placement of D3 at (-6mm,+4mm) conflicts with the bottom ANT_LA return. Never apply the superseded diagonal candidate.',
            'core_uuid':core['uuid'],'panel_uuid':panel['uuid'],'project_uuid':core['doc']['parentProjectUuid'],
            'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.glob('*-source.jsonl')},
            'moves':moves,'routes':routes,
            'reference_vias':[{'net':'VOUT','xy_mil':[-145,0]},{'net':'GND','xy_mil':[-280,-15]}, {'net':'GND','xy_mil':[205,155]}]}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'symmetric-led-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'components_to_move':len(moves),'routes_to_update':len(routes),'output':str(OUT/'symmetric-led-plan.json')}))


if __name__=='__main__':
    main()
