"""Audit current LED-symmetric snapshots without overwriting historical audits."""
import hashlib
import json
from pathlib import Path
import audit_native_copper as audit

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'variants/common'
NATIVE=COMMON/'eda/native'

def main():
    core_file=NATIVE/'core-source.jsonl'
    pads_file=COMMON/'eda/core-pads.json'
    records=audit.load_records(core_file)
    copper=audit.source_copper(records)
    pads=audit.native_pads(pads_file)
    items=audit.copper_items(copper,pads)
    edges=audit.board_edge_checks(items,copper['outline']['geom'])
    minimum,violations,drill,drill_violations=audit.clearance_audit(items,copper['vias'])
    nets=sorted({p['net'] for p in pads+copper['free_pads']})
    connectivity,contacts=audit.build_connectivity(copper,pads,nets)
    coil=audit.coil_audit(copper,ROOT/'electrical/antenna-coil-fill-candidate.json',ROOT/'electrical/antenna-geometry-review.json')
    panels={}
    for stem in ['horse-sagittarius-panel','snake-leo-panel']:
        path=NATIVE/(stem+'-source.jsonl')
        if path.exists():panels[stem]=audit.panel_match(records,audit.load_records(path))
    files=[core_file,pads_file]+[NATIVE/(s+'-source.jsonl') for s in panels]
    result={'status':'current_two_variant_snapshot_audit','units':'mm','read_only':True,
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            'minimum_copper_gap':minimum,'copper_violations':violations,
            'minimum_drill_gap':drill,'drill_violations':drill_violations,
            'outside_copper':edges,'connectivity':connectivity,'via_contacts':contacts,'coil':coil,'panels':panels,
            'summary':{'copper_and_drill_clearance_pass':not violations and not drill_violations,
                       'board_boundary_pass':not edges,'all_pads_connected':all(n['all_pads_connected'] for n in connectivity.values()),
                       'all_vias_contact_both_layers':all(v['has_both_layer_contacts'] for v in contacts),
                       'coil_unchanged':coil['matches_4turn_candidate_within_native_quantization'],
                       'panels_match_core':all(v['passed'] for v in panels.values())},
            'limitations':['Geometry and saved network connectivity only. Native DRC is recorded separately.',
                           'Neither LED brightness nor NFC reading performance has been physically measured.']}
    (COMMON/'native-copper-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['summary']))
    if not all(result['summary'].values()):raise SystemExit(1)

if __name__=='__main__':main()
