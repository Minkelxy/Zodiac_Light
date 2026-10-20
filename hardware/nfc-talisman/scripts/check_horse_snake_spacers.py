"""Read-only stdlib checks for the horse/snake/three-hollow-spacer delivery."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import zipfile

SPEC=importlib.util.spec_from_file_location('additional_standard',Path(__file__).with_name('check_standard_delivery.py'))
STANDARD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(STANDARD)
FOLDER='variants/horse-snake-spacers'
IDS=['horse','snake','spacer-1','spacer-2','spacer-3']
CENTERS=[[21,79],[79,79],[50,50],[21,21],[79,21]]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def validate(root):
    root=Path(root).resolve()
    if (root/'hardware/nfc-talisman').is_dir():root=root/'hardware/nfc-talisman'
    project=root.parents[1];out=root/FOLDER;checks=[];errors=[]
    def check(name,fn):
        try:detail=fn();checks.append(dict(id='additional:'+name,passed=True,detail=detail))
        except Exception as e:errors.append(name+': '+str(e));checks.append(dict(id='additional:'+name,passed=False,detail=str(e)))
    holder={}
    def inputs():
        d=load(out/'design-manifest.json');m=load(out/'export-manifest.json');g=load(out/'geometry.json')
        assert d['panel_mm']==[100,100] and d['animal_covers']==['horse','snake'] and d['hollow_spacers']==3
        assert d['english_labels'] is False and d['spacer_window_af_mm']==30 and d['spacer_inner_radius_mm']==1
        assert d['mousebite_outward_offset_mm']==.4 and d['mousebite_diameter_mm']==.4 and d['mousebite_pitch_mm']==.72
        for name,digest in d['sources'].items():
            assert sha(STANDARD._BASE._relative(project,name))==digest,'Additional source changed: '+name
        for name,info in d['files'].items():STANDARD._BASE._file_check(STANDARD._BASE._relative(out,name),info)
        assert m['design_manifest_sha256']==sha(out/'design-manifest.json') and len(m['boards'])==1
        b=m['boards'][0]
        assert b['uuid']==STANDARD.SUPPLEMENT_UUID and b['status']=='saved_reopened' and b['drc']==[] and b['cover_count']==5
        drc=load(out/'eda/logs/drc.json');assert drc['success'] and drc['result']['drc']==[]
        assert load(out/'eda/logs/save-close.json')['result']=={'saved':True,'closed':True}
        assert [c['id'] for c in g['covers']]==IDS and [c['center_native_mm'] for c in g['covers']]==CENTERS
        assert all(c['details']['english_label_on_pcb'] is False for c in g['covers'])
        holder.update(d=d,m=m,g=g,b=b)
        return 'Frozen sources match: 100mm panel, horse + snake + three 30mm R1 hollow spacer rings; no English labels'
    check('design-and-sources',inputs)
    if not holder:return dict(status='failed',checks=checks,errors=errors,checks_run=len(checks))
    d,m,g,b=(holder[k] for k in ('d','m','g','b'))
    def native():
        p=STANDARD._BASE._relative(root,b['source']['path']);assert sha(p)==b['source']['sha256']
        records=STANDARD._records(p,b['uuid']);docs=STANDARD._native_documents(root,m['native_project'])
        assert STANDARD._pcb_uuids(docs)==STANDARD.shared_pcb_scope(root) and len(STANDARD.shared_pcb_scope(root))==10
        assert STANDARD._BASE._design_records(records)==STANDARD._BASE._design_records(docs[b['uuid']]['records'])
        expected={(e['head']['type'],e['head']['id']):e['body'] for e in g['primitives']}
        found={k:v for k,v in records.items() if k[0] in ('FILL','POLY','PAD')}
        assert set(expected)==set(found)
        assert not any(k[0] in ('COMPONENT','OBJ','VIA','POUR','LINE','ARC') for k in records)
        for key,body in expected.items():
            actual=found[key];assert actual['layerId']==body['layerId'] and actual.get('netName','')==''
            if key[0]=='FILL':assert body['layerId']==3 and STANDARD._polygon_same(body['path'],actual['path']) and actual['fillStyle'] in (0,'SOLID')
            elif key[0]=='POLY':assert body['layerId']==11 and STANDARD._contour_same(body['path'],actual['path'])
            else:
                assert body['layerId']==12 and actual['plated'] is False
                assert all(abs(body[a]-actual[a])<.001 for a in ('centerX','centerY'))
                assert abs(actual['hole']['width']*.0254-.4)<.00001
        for kind in ('standard-green-white','twelve-options'):
            other=load(root/f'variants/{kind}/export-manifest.json')
            assert other['native_project']==m['native_project'],'Current archive link differs'
        holder['records']=records
        return 'Exact ten-PCB native archive; saved new PCB matches all owned primitives; no copper/components/images'
    check('native-ten-pcb-archive',native)
    def subject_and_windows():
        mechanical=load(root/'geometry/design.json');spacer=next(p for p in mechanical['boards'] if p['id']=='spacer2')
        for cover in g['covers']:
            name=cover['id'];cx,cy=cover['center_native_mm'];details=cover['details']
            rows=[e for e in g['primitives'] if e['logical_id'].startswith(name+':')]
            if name in ('horse','snake'):
                face=load(project/details['source_artifact'])['faces']['front']
                originals=[p for p in face['silk_polygons'] if p['category']!='textured_octagonal_border_and_inner_divider']
                actual=[e['body']['path'] for e in rows if e['logical_id'].startswith(name+':silk:')]
                assert len(actual)==len(originals)
                for shape in originals:
                    paths=[]
                    for ring in shape['path_mil']:
                        values=ring[:2]+ring[3:]
                        points=[[values[i]+(cx-20.5)/.0254,values[i+1]+(cy-76.5)/.0254] for i in range(0,len(values),2)]
                        paths.append(points[0]+['L']+[n for p in points[1:] for n in p])
                    hits=[i for i,p in enumerate(actual) if STANDARD._polygon_same(paths,p)]
                    assert hits,'Animal differs from the existing front cover';actual.pop(hits[0])
                borders=[e['body']['path'] for e in rows if e['logical_id'].startswith(name+':border:')]
                STANDARD._check_border(details['border'],borders,[cx,cy])
                assert len([e for e in rows if e['head']['type']=='FILL'])==len(originals)+len(borders),'Extra animal annotation'
            else:
                assert details['kind']=='hollow_spacer' and details['window_af_mm']==30 and details['inner_corner_radius_mm']==1
                assert details['minimum_wall_mm']>=3.49999
                assert not any(e['head']['type']=='FILL' for e in rows),'Spacer should remain plain'
                windows=[e for e in rows if ':inner-window:' in e['logical_id']]
                assert len(windows)==1,'Spacer must contain one real routed window'
                points=[[(cx+x-spacer['center'][0])/.0254,(cy+spacer['center'][1]-y)/.0254] for x,y in spacer['cutouts'][0]['ring']]
                points.append(points[0]);path=points[0]+['L']+[n for p in points[1:] for n in p]
                assert STANDARD._contour_same(path,windows[0]['body']['path']),'Spacer window differs from existing R1 part'
        assert sum(':inner-window:' in e['logical_id'] for e in g['primitives'])==3
        assert sum(e['head']['type']=='PAD' for e in g['primitives'])==100
        return 'Existing horse/snake silhouettes retained without labels; both frames closed; three real 30mm R1 windows, minimum ring wall 3.5mm'
    check('animals-and-real-spacer-windows',subject_and_windows)
    def gerbers():
        ev=b['gerber'];p=STANDARD._BASE._relative(root,ev['path']);STANDARD._BASE._file_check(p,ev)
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None and set(z.namelist())==set(ev['members'])
            assert not any(n.startswith('Fabrication_Colorful') for n in z.namelist())
            for name,info in ev['members'].items():
                raw=z.read(name);assert len(raw)==info['size'] and hashlib.sha256(raw).hexdigest()==info['sha256']
            STANDARD._check_npth_drills(root,dict(source=b['source']['path'],uuid=b['uuid']),z.read('Drill_NPTH_Through.DRL'))
        audit=load(out/'gerber-geometry-audit.json')
        assert audit['status']=='passed' and audit['design_manifest_sha256']==sha(out/'design-manifest.json')
        detail=audit['panels']['horse-snake-spacers']
        assert detail['gerber_sha256']==ev['sha256'] and detail['connected_substrate'] and detail['router_contours']['count']==24
        assert detail['npth_positions_and_diameters_verified']==100
        for name,digest in audit['audit_sources'].items():assert sha(project/name)==digest
        return 'Gerber: 24 router contours, 100 matching NPTH; three windows, real silk negative spaces and one connected panel verified'
    check('gerber-and-connected-material',gerbers)
    return dict(status='failed' if errors else 'passed',read_only=True,checks=checks,errors=errors,checks_run=len(checks),release_ready=False,
                release_status='HOLD_CAM_PHYSICAL_VALIDATION_PENDING')

if __name__=='__main__':
    r=validate(Path(__file__).resolve().parents[1]);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(r['status']!='passed')
