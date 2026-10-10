"""Prepare an unambiguous local CAM review ZIP from the original EDA export."""
import hashlib
import json
import zipfile
from pathlib import Path
from archive_native_outputs import file_info

ROOT=Path(__file__).resolve().parents[1]
DRAFT=ROOT/'manufacturing/draft'
RAW=DRAFT/'nfc-talisman-panel-draft.zip'

def drill_program(data):
    return [line.strip() for line in data.decode('utf-8').splitlines() if line.strip() and not line.startswith(';')]

def main():
    # Stop if the audit describes an older export, or known geometry checks fail.
    # Passing this guard still does not constitute a manufacturing release.
    audit=json.loads((DRAFT/'cam-audit.json').read_text(encoding='utf-8'))
    copper=json.loads((ROOT/'electrical/native-copper-audit.json').read_text(encoding='utf-8'))
    netlists=json.loads((ROOT/'electrical/native-netlist-audit.json').read_text(encoding='utf-8'))
    stars=json.loads((DRAFT/'star-face-audit.json').read_text(encoding='utf-8'))
    colors=json.loads((DRAFT/'star-color-audit.json').read_text(encoding='utf-8'))
    if stars['summary']['all_checks_pass'] is not True or not all(colors['checks'].values()):
        raise ValueError('Sagittarius aperture, silk or color file audit failed')
    if stars['inputs']['manufacturing_zip_sha256']!=hashlib.sha256(RAW.read_bytes()).hexdigest():
        raise ValueError('Sagittarius audit and raw ZIP do not match')
    if stars['inputs']['native_panel_sha256']!=hashlib.sha256((ROOT/'eda/native/panel-source.jsonl').read_bytes()).hexdigest():
        raise ValueError('Sagittarius audit and native panel do not match')
    for key,path in [('geometry',ROOT/'geometry/design.json'),('artwork',ROOT/'artwork/art_data.json')]:
        semantic=json.dumps(json.loads(path.read_text(encoding='utf-8')),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if hashlib.sha256(semantic).hexdigest()!=stars['inputs'][key+'_semantic_sha256']:
            raise ValueError('Sagittarius audit design/artwork changed: '+key)
    for path,expected in colors['source_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=expected:
            raise ValueError('Color audit source changed: '+path)
    if netlists['all_groups_passed'] is not True:
        raise ValueError('Native netlist audit failed')
    for key,expected in netlists['input_sha256'].items():
        path=ROOT/'eda/native'/(key.replace('_','-')+('.jsonl' if key.endswith('_source') else '.json'))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Netlist audit source changed: '+key)
    checks=json.loads((ROOT/'eda/check-summary.json').read_text(encoding='utf-8'))
    if any(checks['checks'][key]['status']!='completed_clean' for key in ('core_pcb_drc','panel_pcb_drc')):
        raise ValueError('Current native PCB DRC checks must be clean')
    if any(item['type']!='warn' for item in checks['checks']['schematic_erc'].get('erc_findings',[])):
        raise ValueError('Unresolved schematic ERC error')
    for entry in [checks['native_project']]+[p for c in checks['checks'].values() for p in c['source_native']]:
        if entry['status']!='present' or hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Check summary source changed: '+entry['path'])
    if audit['inputs']['zip_sha256']!=hashlib.sha256(RAW.read_bytes()).hexdigest():
        raise ValueError('CAM audit and raw ZIP do not match')
    if audit['inputs']['native_panel_sha256']!=hashlib.sha256((ROOT/'eda/native/panel-source.jsonl').read_bytes()).hexdigest():
        raise ValueError('CAM audit and native panel source do not match')
    if audit['inputs']['component_pads_sha256']!=hashlib.sha256((ROOT/'eda/core-pads.json').read_bytes()).hexdigest():
        raise ValueError('CAM audit and component pad data do not match')
    for path,expected in copper['source_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=expected:
            raise ValueError('Copper audit source changed: '+path)
    if not all(copper['summary'].values()):
        raise ValueError('Native copper audit has unresolved findings')
    if not (audit['inputs']['zip_crc_error_member'] is None
            and audit['outline']['d02_path_count']==22
            and audit['outline']['all_paths_explicitly_closed']
            and audit['outline']['envelope_is_100x100_with_1um_export_rounding']
            and audit['antenna_copper']['all_bottom_antenna_segments_match_within_0_001mm']
            and audit['antenna_copper']['top_fill_max_vertex_delta_mm']<0.001
            and audit['bom_pnp']['bom_pnp_designator_sets_equal']
            and audit['testpoints']['summary']['pass'] is True):
        raise ValueError('Draft CAM geometry or test-point check failed')
    for name,expected in [('Drill_PTH_Through.DRL',10),('Drill_NPTH_Through.DRL',108)]:
        if audit['drill']['files'][name]['hit_count']!=expected:
            raise ValueError('Unexpected drill population: '+name)
        if not audit['drill']['native_source_correspondence'][name]['passes_0_003mm']:
            raise ValueError('Drill coordinates differ from native source: '+name)
    for row in audit['bom_pnp']['native_pnp_checks']:
        if not (row.get('source_match') and row.get('side_matches') and row.get('position_delta_mm',1)<0.001
                and abs(row['rotation_deg']-row['native_rotation_deg'])<0.001):
            raise ValueError('PnP does not match native placement: '+row['designator'])
    target=DRAFT/'nfc-talisman-panel-cam-review.zip'
    keep=['Gerber_TopLayer.GTL','Gerber_BottomLayer.GBL','Gerber_TopSilkscreenLayer.GTO','Gerber_BottomSilkscreenLayer.GBO','Gerber_TopSolderMaskLayer.GTS','Gerber_BottomSolderMaskLayer.GBS','Gerber_TopPasteMaskLayer.GTP','Gerber_BottomPasteMaskLayer.GBP','Gerber_BoardOutlineLayer.GKO','Drill_PTH_Through.DRL','Drill_NPTH_Through.DRL']
    keep += [f['name'] for f in colors['color_export_files']]
    with zipfile.ZipFile(RAW) as original:
        if original.testzip() is not None:
            raise ValueError('Original ZIP integrity failed')
        if drill_program(original.read('Drill_PTH_Through.DRL'))!=drill_program(original.read('Drill_PTH_Through_Via.DRL')):
            raise ValueError('PTH files are not exact duplicate drill programs; cannot deduplicate automatically')
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as review:
            for name in keep:
                review.writestr(original.getinfo(name),original.read(name))
    info=file_info(target)
    info['status']='draft_CAM_review_only'
    info['source_sha256']=hashlib.sha256(RAW.read_bytes()).hexdigest()
    info['excluded_duplicate_drill']='Drill_PTH_Through_Via.DRL'
    info['other_excluded_reference_files']=['Gerber_DocumentLayer.GDL','Gerber_DrillDrawingLayer.GDD','PCB text report']
    info['gerber_and_retained_drill_bytes_unchanged']=True
    info['four_color_files_retained_unchanged']=True
    info['color_pixel_content_and_compositing_CAM_approval']='pending; opaque proprietary fabrication data has not been visually approved'
    (DRAFT/'cam-package-manifest.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest_path=DRAFT/'export-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    additions=[target,DRAFT/'four-led-bom.csv',DRAFT/'four-led-panel-pnp.csv',DRAFT/'two-led-bom.csv',DRAFT/'two-led-panel-pnp.csv',DRAFT/'assembly-variants.json',DRAFT/'cam-audit.json',DRAFT/'cam-package-manifest.json',ROOT/'electrical/native-copper-audit.json',ROOT/'electrical/native-netlist-audit.json',ROOT/'eda/check-summary.json']
    additions += [DRAFT/'star-face-audit.json',DRAFT/'star-color-audit.json',ROOT/'artwork/sagittarius-color-print-candidate.png',ROOT/'artwork/sagittarius-linework-review.json']
    manifest['derived_files']=[file_info(path) for path in additions]
    manifest['cam_drill_note']='The raw EDA ZIP includes duplicate PTH programs. The review ZIP retains exactly one PTH file and one NPTH file; retained manufacturing-layer bytes are unchanged.'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
