"""Offline antenna route review against the native core-pads snapshot.

Uses Node only to evaluate the APPLY=false helper. Does not access the bridge
or change a native EDA document. Shapely verifies geometry in millimeters.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess
import shutil

from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box

ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'scripts/12-core-antenna-route.js'
PAD_FILE=ROOT/'eda/core-pads.json'
MM_PER_MIL=0.0254
NODE=shutil.which('node') or 'C:/Users/20177/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
NODE_EVAL="const fs=require('fs');const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;new AsyncFunction(fs.readFileSync(process.argv[1],'utf8'))().then(x=>console.log(JSON.stringify(x))).catch(e=>{console.error(e);process.exit(1)});"

def evaluate(source=HELPER):
    text=source.read_text(encoding='utf-8')
    if 'const APPLY = false;' not in text:
        raise RuntimeError('Offline evaluator refuses a non-preview helper')
    return json.loads(subprocess.check_output([NODE,'-e',NODE_EVAL,str(source)],text=True,encoding='utf-8'))

def pmm(p):
    return (p['x']*MM_PER_MIL,p['y']*MM_PER_MIL)

def track(a,b,layer,role,net):
    return {'a':{'x':a[0]/MM_PER_MIL,'y':a[1]/MM_PER_MIL},'b':{'x':b[0]/MM_PER_MIL,'y':b[1]/MM_PER_MIL},'layer':layer,'width':0.25/MM_PER_MIL,'role':role,'semanticNet':net}

def normalized(plan):
    ts=[]
    for t in plan['trackGeometry']:
        role=t['role']
        net=t.get('semanticNet') or ('L1_INTERNAL' if ('spiral' in role or 'terminal via neck' in role) else 'ANT_LA' if ('LA pad' in role or 'outer-end' in role) else 'ANT_LB')
        ts.append({'geom':LineString([pmm(t['a']),pmm(t['b'])]),'width':t['width']*MM_PER_MIL,'layer':t['layer'],'net':net,'role':role})
    vs=[]
    for v in plan['vias']:
        net=v.get('semanticNet') or ('ANT_LA' if ('LA_' in v['name'] or 'outer' in v['name']) else 'ANT_LB')
        vs.append({'point':Point(v['x_mil']*MM_PER_MIL,v['y_mil']*MM_PER_MIL),'radius':v['diameter_mm']/2,'net':net,'name':v['name']})
    return ts,vs

def pads():
    out=[]
    for c in json.loads(PAD_FILE.read_text(encoding='utf-8')):
        for p in c['pins']:
            if p['pad'][0]!='RECT':
                raise ValueError('Unsupported actual pad shape '+str(p['pad']))
            x,y=pmm(p);w,h=p['pad'][1]*MM_PER_MIL,p['pad'][2]*MM_PER_MIL
            geom=rotate(box(x-w/2,y-h/2,x+w/2,y+h/2),p['rotation'],origin=(x,y))
            out.append({'id':c['ref']+'.'+p['padNumber'],'net':p['net'],'layer':p['layer'],'geom':geom})
    return out

def existing_routes():
    snapshot=ROOT/'eda/native/core-initial-tracks.json'
    raw=json.loads(snapshot.read_text(encoding='utf-8'))
    if not raw.get('success'):
        raise RuntimeError('Native core-track snapshot is not a successful bridge result')
    out=[]
    for t in raw['result']['lines']:
        out.append({'geom':LineString([pmm({'x':t['start'][0],'y':t['start'][1]}),pmm({'x':t['end'][0],'y':t['end'][1]})]),'width':t['width']*MM_PER_MIL,'layer':t['layer'],'net':t['net'],'role':'existing '+t['id']})
    return out

def review(plan, live_tracks=None):
    ts,vs=normalized(plan);ps=pads();all_ts=ts+(live_tracks or [])
    outline=Polygon([pmm(t['a']) for t in plan['outlineSegments']])
    issues=[];checks=[]
    def issue(kind,a,b,gap,required):
        if gap<required-1e-8:
            issues.append({'kind':kind,'a':a,'b':b,'copper_gap_mm':round(gap,8),'required_mm':required,'physical_overlap':gap<0})
    coil=[t for t in ts if 'spiral' in t['role']]
    best=(1e9,None)
    for i,a in enumerate(coil):
        for j in range(i+8,len(coil)):
            b=coil[j];gap=a['geom'].distance(b['geom'])-(a['width']+b['width'])/2
            if gap<best[0]:best=(gap,[i,j])
    issue('coil_turn_gap',*['coil_segment_'+str(x) for x in best[1]],best[0],0.25)
    checks.append({'check':'coil minimum non-neighbor copper gap','value_mm':round(best[0],8),'segments':best[1],'required_mm':0.25})
    # The native U1's fine-pitch pads are intentionally exempt from a global
    # pad-pad 0.15mm rule. This review concerns newly proposed route copper.
    minimum_pad_clearance=(1e9,None)
    for i,t in enumerate(all_ts):
        for p in ps:
            if t['layer']!=p['layer'] or t['net']==p['net']:continue
            gap=t['geom'].distance(p['geom'])-t['width']/2
            if gap<minimum_pad_clearance[0]:minimum_pad_clearance=(gap,[t['role'],p['id']])
            issue('track_to_unrelated_pad',t['role'],p['id'],gap,0.15)
    for v in vs:
        for p in ps:
            if v['net']==p['net']:continue
            gap=v['point'].distance(p['geom'])-v['radius']
            issue('via_to_unrelated_pad',v['name'],p['id'],gap,0.15)
    checks.append({'check':'minimum track to unrelated native pad','value_mm':round(minimum_pad_clearance[0],8),'pair':minimum_pad_clearance[1],'required_mm':0.15})
    bottom=[t for t in ts if t['layer']==2]
    bottom_min=(1e9,None)
    for i,a in enumerate(bottom):
        for j,b in enumerate(bottom[i+1:],i+1):
            if a['net']==b['net']:continue
            gap=a['geom'].distance(b['geom'])-(a['width']+b['width'])/2
            if gap<bottom_min[0]:bottom_min=(gap,[i,j])
            issue('opposite_bottom_returns',a['role'],b['role'],gap,0.15)
    checks.append({'check':'minimum opposite bottom return gap','value_mm':round(bottom_min[0],8),'pair':bottom_min[1],'required_mm':0.15})
    line_min=(1e9,None)
    for i,a in enumerate(all_ts):
        for b in all_ts[i+1:]:
            if a['layer']!=b['layer'] or a['net']==b['net']:continue
            gap=a['geom'].distance(b['geom'])-(a['width']+b['width'])/2
            if gap<line_min[0]:line_min=(gap,[a['role'],b['role']])
            issue('different_net_track_clearance',a['role'],b['role'],gap,0.15)
    checks.append({'check':'minimum different-net track gap including current live tracks','value_mm':round(line_min[0],8),'pair':line_min[1],'required_mm':0.15})
    for v in vs:
        for i,t in enumerate(all_ts):
            # A via may intentionally join its own breakout/return. The coil
            # may touch the matching winding endpoint, but no other turn.
            if t['net']==v['net']:continue
            if t['net']=='L1_INTERNAL' and min(v['point'].distance(Point(t['geom'].coords[0])),v['point'].distance(Point(t['geom'].coords[-1])))<0.101:
                continue
            gap=v['point'].distance(t['geom'])-v['radius']-t['width']/2
            issue('via_to_other_route',v['name'],t['role'],gap,0.15)
    for i,a in enumerate(vs):
        for b in vs[i+1:]:
            if a['net']==b['net']:continue
            gap=a['point'].distance(b['point'])-a['radius']-b['radius']
            issue('different_net_via_clearance',a['name'],b['name'],gap,0.15)
    outside=[]
    for i,t in enumerate(ts):
        if not outline.covers(t['geom'].buffer(t['width']/2)):outside.append('track_'+str(i))
    for v in vs:
        if not outline.covers(v['point'].buffer(v['radius'])):outside.append(v['name'])
    checks.append({'check':'all new copper is inside 37mm outline','passed':not outside,'outside':outside})
    pad_endpoints=[]
    for pin,name in [('1','U1_LA'),('8','U1_LB')]:
        raw=next(p for c in json.loads(PAD_FILE.read_text()) if c['ref']=='U1' for p in c['pins'] if p['padNumber']==pin)
        endpoint=next(t for t in ts if f'U1 {"LA" if pin=="1" else "LB"} pad breakout' in t['role']).get('geom').coords[0]
        pad_endpoints.append({'endpoint':name,'pad_net':raw['net'],'position_mm':pmm(raw),'matches_native_center':math.dist(endpoint,pmm(raw))<1e-8})
    return {'geometry_safe_under_stated_rules':not issues and not outside,'checks':checks,'native_endpoint_checks':pad_endpoints,'violations':sorted(issues,key=lambda x:x['copper_gap_mm']),'limits':['Pad source is a saved native snapshot, not live EDA state.','Copper shape and spacing only; no native DRC or RF simulation.','Only the current 19 native tracks are included; future VOUT/GND tracks must be re-audited.','L1 intentional ANT_LA/ANT_LB copper continuity still requires native bridge-copper property.']}

def review_fill(live_tracks=None):
    data=json.loads((ROOT/'electrical/antenna-coil-fill-candidate.json').read_text(encoding='utf-8'))
    shape=Polygon([(x*MM_PER_MIL,y*MM_PER_MIL) for x,y in data['points_native_mil']])
    if not shape.is_valid:raise RuntimeError('Antenna fill candidate polygon is invalid')
    ps=[p for p in pads() if p['layer']==1]
    tracks=[t for t in (live_tracks or []) if t['layer']==1]
    pad_gaps=[{'pad':p['id'],'net':p['net'],'gap_mm':shape.distance(p['geom'])} for p in ps]
    track_gaps=[{'track':t['role'],'net':t['net'],'gap_mm':shape.distance(t['geom'])} for t in tracks]
    min_pad=min(pad_gaps,key=lambda x:x['gap_mm'])
    min_track=min(track_gaps,key=lambda x:x['gap_mm']) if track_gaps else None
    # Fill is still an offline candidate. Terminal vias are intentional overlaps
    # and are checked separately by the candidate builder.
    return {'polygon_valid':shape.is_valid,'vertex_count':len(data['points_native_mil']),'bridge_nets':data['bridge_nets'],'bridge_enabled':data['bridge_enabled'],'minimum_fill_to_top_pad_copper_gap_mm':round(min_pad['gap_mm'],8),'closest_top_pad':min_pad['pad'],'minimum_fill_to_existing_top_track_copper_gap_mm':round(min_track['gap_mm'],8) if min_track else None,'closest_top_track':min_track['track'] if min_track else None,'required_clearance_mm':0.15,'passes_existing_top_copper_screen':min_pad['gap_mm']>=0.15 and (min_track is None or min_track['gap_mm']>=0.15),'terminal_via_overlap_checks':data['terminal_via_overlap_checks'],'note':'This checks the fill polygon against current Top pads/tracks only. It does not validate bridge-copper properties, proposed necks/vias, bottom return routes, native DRC or RF behavior.'}

def proposal(base):
    # Small +2um pitch correction makes the sampled inward spiral meet >=0.25
    # mathematical clearance. Keep the original nominal width and outer AF.
    pitch=0.502;apothem=16.875
    pts=[]
    for i in range(129):
        progress=i/32;angle=math.pi+progress*math.pi*2;a=apothem-pitch*progress
        delta=(angle+math.pi/8)%(math.pi/4)-math.pi/8;r=a/math.cos(delta)
        pts.append((r*math.cos(angle),r*math.sin(angle)))
    outer=pts[0];inner=pts[-1]
    # Move the LA breakout via inward to avoid both existing LED1/LED3 copper
    # branches while retaining >0.15mm clearance to the U1 GND pad.
    ov=(outer[0]-0.10,outer[1]);iv=(inner[0]+0.10,inner[1]);av=(-1.524,1.2);bv=(1.0,1.2)
    ts=[track(a,b,1,'4-turn octagonal spiral','L1_INTERNAL') for a,b in zip(pts,pts[1:])]
    for path,layer,role,net in [([(-23.6*MM_PER_MIL,19.7*MM_PER_MIL),av],1,'U1 LA pad breakout','ANT_LA'),([(0,23.6*MM_PER_MIL),(0,1.2),bv],1,'U1 LB pad breakout','ANT_LB'),([outer,ov],1,'outer terminal via neck','L1_INTERNAL'),([inner,iv],1,'inner terminal via neck','L1_INTERNAL'),([ov,(-15.6,4.5),(-4.0,4.5),av],2,'outer-end return','ANT_LA'),([iv,(-13.0,-4.5),(1.0,-4.5),bv],2,'inner-end return','ANT_LB')]:
        ts.extend(track(a,b,layer,role,net) for a,b in zip(path,path[1:]))
    vs=[{'name':name,'x_mil':p[0]/MM_PER_MIL,'y_mil':p[1]/MM_PER_MIL,'drill_mm':0.20,'diameter_mm':0.45,'semanticNet':net} for name,p,net in [('U1_LA_breakout',av,'ANT_LA'),('U1_LB_breakout',bv,'ANT_LB'),('coil_outer_terminal',ov,'ANT_LA'),('coil_inner_terminal',iv,'ANT_LB')]]
    result=dict(base);result['trackGeometry']=ts;result['vias']=vs;result['pitch_mm']=pitch;result['proposal_only']=True
    result['note']='Geometry-only proposal. +0.002mm pitch corrects sampled geometry; shifting the LA breakout via to (-60,47.244) mil clears current LED branches. EasyEDA provides bridge copper for a FILL region via the native UI, but the installed API does not expose that property; VOUT/GND routing, bridge setting, full-stack DRC and RF tests remain.'
    return result

def main():
    base=evaluate();suggested=proposal(base);live=existing_routes()
    report={'helper_sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest(),'core_pads_sha256':hashlib.sha256(PAD_FILE.read_bytes()).hexdigest(),'live_routes_sha256':hashlib.sha256((ROOT/'eda/native/core-initial-tracks.json').read_bytes()).hexdigest(),'offline_JS_preview_valid':True,'apply':base['apply'],'layer_ids':[1,2,11],'coordinate_units':'geometry evaluated in mm; proposal track/via outputs remain native mil','baseline':review(base,live),'proposal':review(suggested,live),'proposal_geometry':suggested,'coil_fill_geometry':review_fill(live)}
    dest=ROOT/'electrical/antenna-geometry-review.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(dest),'baseline_violation_count':len(report['baseline']['violations']),'proposal_violation_count':len(report['proposal']['violations']),'baseline_safe':report['baseline']['geometry_safe_under_stated_rules'],'proposal_geometry_safe':report['proposal']['geometry_safe_under_stated_rules'],'baseline_checks':report['baseline']['checks'],'proposal_checks':report['proposal']['checks']}))

if __name__=='__main__':main()
