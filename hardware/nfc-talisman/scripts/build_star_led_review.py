"""Read-only optical positioning review; no EDA or manufacturing edits."""
from pathlib import Path
import base64
import csv
import hashlib
import itertools
import json
import math
import xml.etree.ElementTree as ET
from html import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'manufacturing/star-led-review-v1'
PNP = ROOT / 'manufacturing/draft/four-led-panel-pnp.csv'
GEOMETRY = ROOT / 'geometry/design.json'
HORSE = ROOT / 'artwork/reference-collection/talisman-single-ink-v1/horse-single-ink.png'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mec(points):
    """Exact finite-point minimum enclosing circle via 1/2/3-point candidates."""
    candidates = [(p, 0.0) for p in points]
    for a, b in itertools.combinations(points, 2):
        candidates.append((((a[0]+b[0])/2, (a[1]+b[1])/2), math.dist(a, b)/2))
    for a, b, c in itertools.combinations(points, 3):
        d = 2*(a[0]*(b[1]-c[1])+b[0]*(c[1]-a[1])+c[0]*(a[1]-b[1]))
        if abs(d) < 1e-10:
            continue
        aa, bb, cc = [p[0]**2+p[1]**2 for p in (a,b,c)]
        center = ((aa*(b[1]-c[1])+bb*(c[1]-a[1])+cc*(a[1]-b[1]))/d,
                  (aa*(c[0]-b[0])+bb*(a[0]-c[0])+cc*(b[0]-a[0]))/d)
        candidates.append((center, math.dist(center, a)))
    return min((v for v in candidates if all(math.dist(v[0], p) <= v[1]+1e-8 for p in points)), key=lambda v:v[1])


def two_center(points):
    # Last point is fixed in group B, removing equivalent swapped partitions.
    candidates = []
    for mask in range(1, 1 << (len(points)-1)):
        groups = [[p for i,p in enumerate(points) if bool(mask >> i & 1) == flag] for flag in (True, False)]
        circles = [mec(group) for group in groups]
        candidates.append((max(c[1] for c in circles), circles, mask))
    return min(candidates, key=lambda v:v[0])


def text(x,y,s,size=3,fill='#263348',anchor='start'):
    return f'<text x="{x}" y="{y}" font-family="Microsoft YaHei,Arial,sans-serif" font-size="{size}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>'


def octagon(af):
    h=af/2; k=h*(math.sqrt(2)-1)
    return [(-k,-h),(k,-h),(h,-k),(h,k),(k,h),(-k,h),(-h,k),(-h,-k)]


def polygon(points,fill,stroke='none',width=.15,dash=''):
    return f'<polygon points="'+ ' '.join(f'{x:.5f},{y:.5f}' for x,y in points)+f'" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-dasharray="{dash}"/>'


def star_geometry(c, leds, annotation=True):
    s=[polygon(octagon(37),'#17232f','#344559')]
    s.append(polygon(octagon(30),'none','#43b5b1',.15,'1 0.6'))
    for e in c['edges']:
        a,b=e['endpoint_a'],e['endpoint_b']
        s.append(f'<path d="M {a[0]} {a[1]} L {b[0]} {b[1]}" stroke="#afb9c3" stroke-width="1" stroke-linecap="round"/>')
    for star in c['stars_local']:
        x,y=star['center']
        s.append(f'<circle cx="{x}" cy="{y}" r=".4" fill="#e1e7ed"/>')
    for name,(x,y) in leds.items():
        # Reference ray angle only, with assumed h=1mm, not a beam cutoff.
        s.append(f'<circle cx="{x}" cy="{y}" r="{math.sqrt(3)}" fill="#58cfbd" fill-opacity=".08" stroke="#58cfbd" stroke-width=".12" stroke-dasharray=".4 .4"/>')
        s.append(f'<rect x="{x-.8}" y="{y-.4}" width="1.6" height=".8" fill="#ed7957" stroke="#ffe4b9" stroke-width=".12"/>')
        if annotation:
            s.append(text(x,y-1.0,name,1.3,'#ffd4b5','middle'))
    return ''.join(s)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sources=[GEOMETRY,PNP,HORSE,ROOT/'scripts/build_panel_import.py']
    source_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sources}
    geometry=json.loads(GEOMETRY.read_text(encoding='utf-8-sig'))
    c=geometry['constellation']
    with PNP.open(encoding='utf-8-sig',newline='') as stream:
        pnp={r['Designator']:r for r in csv.DictReader(stream)}
    native={ref:tuple(float(pnp[ref][axis].removesuffix('mm'))-50 for axis in ('Mid X','Mid Y')) for ref in ('D1','D2','D3','D4')}
    rear={ref:(-native[ref][0],-native[ref][1]) for ref in ('D3','D4')}
    front={ref:(native[ref][0],-native[ref][1]) for ref in ('D1','D2')}
    distances=[]
    for star in c['stars_local']:
        all_distances={ref:math.dist(star['center'],p) for ref,p in rear.items()}
        nearest=min(all_distances,key=all_distances.get)
        distances.append({'name':star['name'],'hip':star['hip'],'center_exterior_mm':star['center'],
                          'source_distances_mm':all_distances,'nearest_source':nearest,'nearest_distance_mm':all_distances[nearest]})
    pts=[tuple(s['center']) for s in c['stars_local']]
    radius,circles,mask=two_center(pts)
    star_area=len(pts)*math.pi*.4**2
    slot_area=sum(e['centerline_length_mm']*1+math.pi*.5**2 for e in c['edges'])
    worst=max(d['nearest_distance_mm'] for d in distances)
    metrics={
        'date':'2026-10-11','status':'optical_geometry_review_only_not_manufacturing_or_photometric_validation',
        'coordinate_convention':'Exterior face X right, Y down; front=(native X,-native Y), rear=(-native X,-native Y), flip about common vertical datum. Native core is mil/Y-up; geometry is mm/Y-down.',
        'native_core_centers_mm':native,'rear_exterior_centers_mm':rear,'front_exterior_centers_mm':front,
        'star_nearest_source_distances':distances,
        'current_star_nearest_min_mm':min(d['nearest_distance_mm'] for d in distances),
        'current_star_nearest_max_mm':worst,
        'unconstrained_star_only_two_center_minimax':{'radius_mm':radius,'centers_and_cluster_radius_mm':circles,'mask':mask,
            'worst_distance_reduction_percent':(1-radius/worst)*100,'scope':'Eight star centers only. No pads, resistors, traces, antenna, slots, die geometry, materials or brightness constraints. Not an approved placement.'},
        'opening_area_mm2':{'stars':star_area,'slots':slot_area,'slot_to_star_ratio':slot_area/star_area,'slots_fraction':slot_area/(star_area+slot_area)},
        'point_source_straight_bore_model':{'equation':'d_max=R*(1+2*h/t)','R_mm':.4,'t_mm_nominal':1,
            'h_mm_example':.75,'d_max_mm_example':1,'h_mm_alternative_example':1,'d_max_mm_alternative_example':1.2,
            'limitations':'Ideal point source and straight cylindrical bore only; finite luminous area, optical center, adhesive/actual gap, thickness tolerance, chamfers, FR-4 and bore scattering, diffuser/guide, reflection and phone RF are not modeled.'},
        'led_primary_source':'https://www.kingbrightusa.com/images/catalog/SPEC/APG1608SYKC-T.pdf',
        'led_source_revision':'V15B, 2025-03-13; p1: 120deg full half-intensity viewing angle, not cutoff; nominal height .25mm, tolerance .1mm.',
        'source_sha256':source_hashes,
        'no_native_or_manufacturing_changes':True,
    }
    (OUT/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210">',
       '<title>射手座与马面 LED 定位及孔道遮挡评审</title>',
       '<desc>定位图放大1.5倍，形状与距离示意，不预测亮度或实物颜色。</desc>',
       '<rect width="297" height="210" fill="#f5f7fa"/>',
       text(10,12,'射手座 / 马面：LED 位置与浅光腔复核',5),
       text(10,20,'定位图放大 1.5 倍；距离均为 mm。不是光照仿真，也不是可导入的 PCB / CAM 文件。',2.8)]
    for x,title in [(8,'背面 · 当前星图与 D3 / D4'),(106,'正面 · 马图放置基线与 D1 / D2'),(204,'侧面 · 直壁星孔的遮挡示意')]:
        s.append(f'<rect x="{x}" y="28" width="85" height="171" rx="2" fill="white" stroke="#d5dce5" stroke-width=".3"/>')
        s.append(text(x+4,36,title,3.1))
    s.append('<g transform="translate(50.5 72) scale(1.5)">'+star_geometry(c,rear)+'</g>')
    s.extend([text(12,108,'外侧 X 向右、Y 向下；背面按同一基准边翻转。',2.4),
              text(12,114,'绿虚圆：h=1 mm 的 ±60°射线投影参考。',2.4),
              text(12,120,'它不是光束边界，孔/槽未模拟发光。',2.4)])
    for i,d in enumerate(sorted(distances,key=lambda d:d['nearest_distance_mm'])):
        s.append(text(12,130+i*5.8,f"{d['name']:7s}  → {d['nearest_source']}   {d['nearest_distance_mm']:.2f} mm",2.65))
    s.append(text(12,183,f'槽/星孔总面积 = {slot_area/star_area:.1f} 倍（不是光强比）。',2.5))
    s.append(text(12,190,'最远近源距约 10 mm，均匀性仍需导光/扩散验证。',2.4))
    horse_uri='data:image/png;base64,'+base64.b64encode(HORSE.read_bytes()).decode('ascii')
    s.append('<g transform="translate(148.5 72) scale(1.5)">'+polygon(octagon(37),'#eceff3','#33455b')+
             f'<image x="-18.5" y="-18.5" width="37" height="37" href="{horse_uri}"/>'+polygon(octagon(30),'none','#43b5b1',.15,'1 .6'))
    for ref,(x,y) in front.items():
        s.append(f'<rect x="{x-.8}" y="{y-.4}" width="1.6" height=".8" fill="#ed7957" stroke="#67372e" stroke-width=".12"/>')
        s.append(text(x,y-1,ref,1.3,'#9d321a','middle'))
    s.append('</g>')
    s.extend([text(110,109,'马 PNG 仅作位置对照，仍未写入原生盖板。',2.4),
              text(110,116,'整幅画布 37 mm；图案透明留白保持原样。',2.4),
              text(110,129,'前后各两颗顶发光 LED，各自面向对应盖板。',2.6),
              text(110,137,'平面旋转 0°/90°不会将顶发光变成侧发光。',2.5),
              text(110,148,'当前前盖连续 FR-4，最终出光区域尚未定义。',2.5),
              text(110,158,'先定实际透光分区，再评价前面灯的覆盖。',2.5),
              text(110,172,'两个光腔分别验证，前灯不计为背面光源。',2.5),
              text(110,184,'元件高度、焊锡、胶层与扩散材料需实测。',2.4)])
    # Cross section is enlarged and has an explicitly hypothetical h=.75mm.
    origin_x,origin_y,k=247,85,13
    def xy(x,z):return origin_x+x*k,origin_y-z*k
    R,h,t=.4,.75,1
    for left,right in [(-2.4,-R),(R,2.4)]:
        x,y=xy(left,h+t)
        s.append(f'<rect x="{x}" y="{y}" width="{(right-left)*k}" height="{t*k}" fill="#8e9aad"/>')
    axis_x=origin_x
    s.append(f'<path d="M {axis_x} {origin_y+2} V {origin_y-(h+t)*k-3}" stroke="#78909c" stroke-width=".15" stroke-dasharray="1 .7"/>')
    for d,color,end in [(1,'#278d82',.4),(1.579,'#c95c49',0)]:
        a=xy(-d,0);b=xy(end,h+t)
        s.append(f'<path d="M {a[0]} {a[1]} L {b[0]} {b[1]}" stroke="{color}" stroke-width=".45"/>')
        s.append(f'<circle cx="{a[0]}" cy="{a[1]}" r=".7" fill="{color}"/>')
    s.extend([text(208,47,'示例：R=0.4、t=1、h=0.75 mm（非实测）。',2.4),
              text(208,55,'灰区为板材；孔内两端都必须有通视路径。',2.4),
              text(208,99,'绿线：d=1.0 mm 的理想极限射线。',2.5),
              text(208,106,'红线：d=1.58 mm，瞄准出口仍被孔壁挡住。',2.4),
              text(208,119,'点源直壁孔：d ≤ R × (1 + 2h/t)',2.9),
              text(208,128,'假设 h=1 mm 时，d 上限为 1.2 mm。',2.5),
              text(208,142,'有限发光面、倒角、胶厚、FR-4 散射和',2.5),
              text(208,149,'扩散/导光片会改变结果；不能据此判必暗。',2.5),
              text(208,163,'120°是 LED 半强度全角，不是孔道通视角。',2.5),
              text(208,177,'优先做孔槽盖板与非金属导光/扩散的样件。',2.4),
              text(208,189,'单靠移动两颗灯，尚不能保证八星均匀。',2.5),'</svg>'])
    svg=OUT/'led-overlay-review.svg'
    svg.write_text('\n'.join(s)+'\n',encoding='utf-8')
    ET.parse(svg)
    assert all(sha(ROOT/rel)==value for rel,value in source_hashes.items())
    validation={'status':'pass','checks':['SVG XML valid','PNP centers read without mutation','source hashes unchanged'],
                'svg_dimensions_mm':[297,210],'rendering_and_visual_review':'pending','scope':'Artifact/source integrity only, no optical or PCB validation.'}
    (OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(svg),'nearest_star_min_mm':metrics['current_star_nearest_min_mm'],
                      'nearest_star_max_mm':worst,'star_only_minimax_lower_bound_mm':radius,'source_files_unchanged':True},ensure_ascii=False))


if __name__=='__main__':
    main()
