from pathlib import Path
import json, math, hashlib
BASE=Path(__file__).resolve().parents[1]
ROOT=Path(__file__).resolve().parents[3]
OUT=BASE/'variants'/'snake-leo'
OUT.mkdir(parents=True,exist_ok=True)
ref=BASE/'artwork'/'reference-collection'/'zodiac-modern'/'manifest.json'
manifest=json.loads(ref.read_text(encoding='utf-8'))
leo=next(c for c in manifest['charts'] if c['id']=='Leo')
stars=leo['stars']; edges=leo['edges']
# Equal-scale mapping of the archived Stellarium modern chart to the existing 27.5mm constellation envelope.
scale=27.5/(max(s['x_px'] for s in stars)-min(s['x_px'] for s in stars))
cx=(max(s['x_px'] for s in stars)+min(s['x_px'] for s in stars))/2
cy=(max(s['y_px'] for s in stars)+min(s['y_px'] for s in stars))/2
positions={s['hip']:[round((s['x_px']-cx)*scale,6),round((s['y_px']-cy)*scale,6)] for s in stars}
# Each incident capsule endpoint is set back far enough from its drilled star for a 1.03mm web between slots.
SLOT_R=.5; STAR_R=.4; WEB=1.03
cut_edge_indices=set(range(len(edges)))
visual_only=[]
def setbacks_for(edge_indices):
    adjacency={s['hip']:[] for s in stars}
    for i in edge_indices:
        a,b=edges[i];adjacency[a].append((i,b));adjacency[b].append((i,a))
    result={};local_angles={}
    for h,neighbors in adjacency.items():
        rays=[]
        for _,o in neighbors:
            dx=positions[o][0]-positions[h][0];dy=positions[o][1]-positions[h][1]
            l=math.hypot(dx,dy);r=(dx/l,dy/l);rays.append(r)
        local=[]
        for i,u in enumerate(rays):
            for v in rays[i+1:]:
                local.append(math.acos(max(-1,min(1,u[0]*v[0]+u[1]*v[1]))))
        need=STAR_R+SLOT_R+WEB
        if local: need=max(need,max((2*SLOT_R+WEB)/(2*math.sin(a/2)) for a in local))
        result[h]=need;local_angles[h]=[round(math.degrees(a),3) for a in local]
    return result,local_angles,adjacency
# If a source edge is too short to fit two Ø0.8 holes, a 1mm slot and 1.03mm webs,
# keep that true star relation as printed ink and document it as non-aperture art.
while True:
    setback,angles,adj=setbacks_for(cut_edge_indices)
    too_short=[]
    for i in cut_edge_indices:
        a,b=edges[i];length=math.dist(positions[a],positions[b])
        if length <= setback[a]+setback[b]: too_short.append((length-setback[a]-setback[b],i))
    if not too_short: break
    _,idx=min(too_short);cut_edge_indices.remove(idx);visual_only.append(idx)
slots=[]
for i in sorted(cut_edge_indices):
    a,b=edges[i]
    pa=positions[a];pb=positions[b];dx=pb[0]-pa[0];dy=pb[1]-pa[1];length=math.hypot(dx,dy);u=(dx/length,dy/length)
    start=setback[a];end=setback[b]
    center_len=length-start-end
    if center_len <= 0: raise ValueError(f'edge {i} too short after setbacks: {a}-{b} {center_len:.4f} mm')
    p=[round(pa[0]+u[0]*start,6),round(pa[1]+u[1]*start,6)]
    q=[round(pb[0]-u[0]*end,6),round(pb[1]-u[1]*end,6)]
    slots.append({'id':f'leo_{i+1:02d}','source_edge_index':i,'hip_a':a,'hip_b':b,'centerline_start':p,'centerline_end':q,'width_mm':1.0,'centerline_length_mm':round(center_len,6),'overall_length_mm':round(center_len+1.0,6),'endpoint_setback_mm':[round(start,6),round(end,6)]})
try:
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
except Exception as e: raise RuntimeError('Shapely is required for manufacturing-aware validation') from e
slot_shapes=[LineString([s['centerline_start'],s['centerline_end']]).buffer(.5,quad_segs=32,cap_style='round') for s in slots]
slot_shape_by_index={s['source_edge_index']:shape for s,shape in zip(slots,slot_shapes)}
# The distance between capsules touching at a shared star should satisfy the web by construction; measure all pairs.
pair_gaps=[]
for i in range(len(slots)):
    for j in range(i+1,len(slots)):
        if set((slots[i]['hip_a'],slots[i]['hip_b'])) & set((slots[j]['hip_a'],slots[j]['hip_b'])): continue
        pair_gaps.append((slot_shapes[i].distance(slot_shapes[j]),slots[i]['id'],slots[j]['id']))
min_nonincident=min(pair_gaps,default=(float('inf'),None,None))
# Outline in board-local coordinates, AF37.
h=18.5;b=h*math.tan(math.pi/8)
oct=[[-b,-h],[b,-h],[h,-b],[h,b],[b,h],[-b,h],[-h,b],[-h,-b]]
board=Polygon(oct)
b2=15*math.tan(math.pi/8)
inner_nominal=[[-b2,-15],[b2,-15],[15,-b2],[15,b2],[b2,15],[-b2,15],[-15,b2],[-15,-b2]]
inner_window=Polygon(inner_nominal).buffer(-1,join_style=2).buffer(1,quad_segs=32)
slot_union=unary_union(slot_shapes)
holes=[Point(p).buffer(.4,quad_segs=48) for p in positions.values()]
if not board.covers(slot_union) or any(not board.covers(v) for v in holes): raise ValueError('Aperture outside AF37 board')
if not inner_window.covers(slot_union) or any(not inner_window.covers(v) for v in holes): raise ValueError('Optical aperture outside the AF30 spacer window')
min_hole_slot=min((hole.distance(slot),hip_id,s['id']) for (hip_id,hole) in zip(positions,holes) for s,slot in zip(slots,slot_shapes))
if min_hole_slot[0] < WEB-1e-6: raise ValueError(f'Star-hole to slot web below target: {min_hole_slot}')
# Search for the closest slot/slot pair around each common star in the buffered outline; point-distance confirms web.
incident_gaps=[]
for h_id,ns in adj.items():
    sh=[slot_shape_by_index[i] for i,_ in ns]
    for i in range(len(sh)):
        for j in range(i+1,len(sh)):
            incident_gaps.append((sh[i].distance(sh[j]),h_id))
min_incident=min(incident_gaps,default=(float('inf'),None))
# Geometric SVG: board silhouette, all 9 physical Ø0.8 holes and all 10 true 1mm capsules.
def fmtpts(p): return ' '.join(f'{x:.6f},{y:.6f}' for x,y in p)
def capsule_d(p,q,r=.5):
    dx=q[0]-p[0];dy=q[1]-p[1];a=math.atan2(dy,dx); px=-math.sin(a)*r;py=math.cos(a)*r
    p1=(p[0]+px,p[1]+py);q1=(q[0]+px,q[1]+py);q2=(q[0]-px,q[1]-py);p2=(p[0]-px,p[1]-py)
    return f'M {p1[0]:.6f},{p1[1]:.6f} L {q1[0]:.6f},{q1[1]:.6f} A {r:.6f},{r:.6f} 0 0 1 {q2[0]:.6f},{q2[1]:.6f} L {p2[0]:.6f},{p2[1]:.6f} A {r:.6f},{r:.6f} 0 0 1 {p1[0]:.6f},{p1[1]:.6f} Z'
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="37mm" height="37mm" viewBox="-18.5 -18.5 37 37">','<title>Leo constellation apertures, 37mm across-flats</title>','<desc>Stellarium Modern Leo: nine HIP stars and all ten source edges. AF37 board; Ø0.8 stars; 1.0mm independent rounded slots; endpoint setbacks preserve at least 1.03mm nominal webs at shared stars.</desc>',f'<polygon points="{fmtpts(oct)}" fill="none" stroke="#203447" stroke-width="0.15"/>']
for s in slots: svg.append(f'<path id="{s["id"]}" d="{capsule_d(s["centerline_start"],s["centerline_end"])}" fill="#e8ab4f" stroke="none"/>')
for star in stars:
    x,y=positions[star['hip']];svg.append(f'<circle id="HIP{star["hip"]}" cx="{x:.6f}" cy="{y:.6f}" r="0.400000" fill="#e8ab4f"/>')
svg.append('</svg>')
(OUT/'leo-geometry.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')
# Review artwork is an appearance guide; mechanical cuts are separately represented above.
art=['<svg xmlns="http://www.w3.org/2000/svg" width="37mm" height="37mm" viewBox="-18.5 -18.5 37 37">','<title>Leo side, dark background and pale constellation lines</title>','<rect x="-18.5" y="-18.5" width="37" height="37" fill="#17232f"/>',f'<polygon points="{fmtpts(oct)}" fill="none" stroke="#59616a" stroke-width="0.14"/>']
# Vector title LEO with simple keyline strokes.
def line(a,b,ident,w=.18,color='#eee8d6'): art.append(f'<path id="{ident}" d="M {a[0]:.3f},{a[1]:.3f} L {b[0]:.3f},{b[1]:.3f}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>')
# title at the top in a compact 1.2mm-high stroke alphabet
for k,(x0,x1) in enumerate([(-1.9,-1.1),(-.4,.4),(1.1,1.9)]):
    y0=-17.0;y1=-15.8
    if k==0: seg=[((x0,y0),(x0,y1)),((x0,y1),(x1,y1))]
    elif k==1: seg=[((x0,y1),(x0,y0)),((x0,y0),(x1,y0)),((x0,y0+.6),(x1,y0+.6)),((x0,y1),(x1,y1))]
    else: seg=[((x0+.12,y0),(x1-.12,y0)),((x1,y0+.12),(x1,y1-.12)),((x1-.12,y1),(x0+.12,y1)),((x0,y1-.12),(x0,y0+.12))]
    for j,(a,bp) in enumerate(seg):line(a,bp,f'leo_title_{k}_{j}')
# Reuse the existing AD ASTRA vector keyline paths, shifted to the lower inscription row.
artdata=json.loads((BASE/'artwork'/'art_data.json').read_text(encoding='utf-8'))
for p in artdata['sagittarius_silkscreen']:
    if p['id'].startswith('latin_ad_astra_'):
        pts=p['points'];art.append(f'<polyline id="{p["id"]}" points="{fmtpts(pts)}" fill="none" stroke="#eee8d6" stroke-width="0.18" stroke-linecap="round" stroke-linejoin="round"/>')
# Plot source edges and star dots. Geometry SVG carries cut shapes; this print rendering makes the sky figure legible.
for i,(a,bp) in enumerate(edges):
    x1,y1=positions[a];x2,y2=positions[bp]
    art.append(f'<path id="constellation_edge_{i+1:02d}" d="M {x1:.6f},{y1:.6f} L {x2:.6f},{y2:.6f}" fill="none" stroke="#eee8d6" stroke-width="0.22" stroke-linecap="round"/>')
for s in stars:
    x,y=positions[s['hip']];r=.28+(3.9-s['mag_v'])*.04
    art.append(f'<circle id="constellation_star_HIP{s["hip"]}" cx="{x:.6f}" cy="{y:.6f}" r="{r:.3f}" fill="#eee8d6"/>')
art.append('</svg>')
(OUT/'leo-artwork.svg').write_text('\n'.join(art)+'\n',encoding='utf-8')
# Variants metadata and validation record.
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
snake=BASE/'artwork'/'reference-collection'/'talisman-single-ink-v1'/'snake-single-ink.png'
hip=BASE/'artwork'/'reference-collection'/'source-zodiac'/'hipparcos-zodiac.tsv'
source_index=ROOT/'data'/'sources'/'20261008T150844925832Z'/'stellarium_modern_index.json'
report={'status':'candidate_geometry_checked_with_documented_print_only_edges' if visual_only else 'candidate_geometry_checked','constellation':'Leo','source':'Stellarium Modern CON modern Leo archived in zodiac-modern manifest','star_count':len(stars),'source_edge_count':len(edges),'physical_slot_count':len(slots),'print_only_source_edges':[{'edge_index':i,'hip_a':edges[i][0],'hip_b':edges[i][1],'star_distance_mm':round(math.dist(positions[edges[i][0]],positions[edges[i][1]]),6),'reason':'1mm capsule plus Ø0.8 star holes cannot leave the requested 1.03mm material webs at this chart scale'} for i in visual_only],'chart_coordinate_scale_mm_per_px':round(scale,9),'constellation_bbox_mm':[round(max(x for x,y in positions.values())-min(x for x,y in positions.values()),6),round(max(y for x,y in positions.values())-min(y for x,y in positions.values()),6)],'nominal_board_across_flats_mm':37,'inner_window_across_flats_mm':30,'star_hole_diameter_mm':.8,'slot_width_mm':1.0,'target_shared_star_web_mm':1.03,'star_local_setbacks_mm':{str(k):round(v,6) for k,v in setback.items()},'star_incident_angles_deg':{str(k):angles[k] for k in angles},'minimum_shared_star_slot_separation_mm':round(min_incident[0],6),'minimum_nonincident_slot_gap_mm':round(min_nonincident[0],6) if min_nonincident[0]!=float('inf') else None,'minimum_hole_to_slot_web_mm':round(min_hole_slot[0],6),'minimum_hole_to_slot_pair':[min_hole_slot[1],min_hole_slot[2]],'all_cutouts_inside_AF37':True,'all_cutouts_inside_AF30_window':True,'snake_png_sha256_before_build':sha(snake),'source_sha256':{'zodiac_modern_manifest':sha(ref),'stellarium_modern_index':sha(source_index),'hipparcos_zodiac_tsv':sha(hip),'snake_single_ink_png':sha(snake)},'source_manifest_recorded_sha256':leo['source_sha256'],'notes':['The complete 9-star, 10-edge Stellarium Modern Leo topology is retained in the artwork; physical apertures include only edges that satisfy the requested material webs.','Slots are independent rounded 1.0mm capsules; Ø0.8mm holes remain separate.','Shared-star endpoint setbacks are computed from the narrowest incident angle, preserving >=1.03mm nominal webs for physical slots.','Review artwork is a presentation candidate, not a manufacturing release.','Original snake PNG is used byte-for-byte as a composite input and is not copied or altered.']}
(OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'leo-geometry.json').write_text(json.dumps({'schema_version':1,'units':'mm','panel_face':'leo','coordinate_system':'board_center_origin_x_right_y_down','board':{'across_flats_mm':37,'inner_window_across_flats_mm':30},'constellation':{'source_id':'CON modern Leo','projection':'uniform scale from archived 1024x1024 gnomonic chart; no rotation or edge selection','stars':[{'hip':s['hip'],'mag_v':s['mag_v'],'center_mm':positions[s['hip']],'diameter_mm':.8,'endpoint_setback_mm':round(setback[s['hip']],6),'incident_angles_deg':angles[s['hip']]} for s in stars],'logical_edges_all':[{'hip_a':a,'hip_b':b,'physical_slot_id':next((sl['id'] for sl in slots if sl['hip_a']==a and sl['hip_b']==b),None),'printed_in_artwork':True} for a,b in edges],'physical_slots':slots,'print_only_edge_indices':visual_only}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
readme='''# Snake + Leo second variant candidate\n\nThis directory contains an isolated review candidate for the reverse face of the shared NFC talisman core. Existing project geometry, source art, PNGs, native project files and manufacturing snapshots are not changed.\n\n## Files\n\n- `leo-geometry.json` — independent Leo physical candidate in board-local millimetres.\n- `leo-geometry.svg` — AF37 perimeter reference, nine Ø0.8mm star holes and eight independent 1.0mm rounded slots.\n- `leo-artwork.svg` / `leo-artwork-preview.png` — dark ground, pale full Leo lines, vector `LEO` and the existing vector `AD ASTRA` lettering. This is a review image, not released color-print data.\n- `leo-geometry-preview.png` — rendered cut geometry review.\n- `snake-leo-two-face-preview.png` — side-by-side front/rear appearance preview; the snake PNG is composited from the existing source file without copying or changing it.\n- `validation.json` — dimensions, mechanical clearances and source hashes.\n- `build_snake_leo_variant.py` — geometry and SVG builder; PNG rasterization uses the configured Sharp runtime.\n\n## Leo graph and geometry\n\nThe archived Stellarium Modern `CON modern Leo` chart is used as a mainstream simple line figure. Its complete nine HIP stars and ten edges are retained in artwork, including the familiar sickle/head and connected body loop. The chart coordinates are uniformly scaled to a 27.5mm-wide envelope and centered on the board; no star or edge is hand-selected.\n\nThe existing 37mm AF octagon and 30mm AF optical window remain the shared mechanical envelope. Each Leo star is a separate Ø0.8mm hole. Nine source edges become independent 1.0mm rounded slots. HIP 48455–47908 and HIP 50583–50335 remain continuous pale printed relationships in the artwork, but are omitted from physical apertures: their 2.55mm and 3.36mm star separations cannot accommodate a 1mm slot and a 1.03mm web at both holes. Keeping them as printed lines retains the mainstream figure while protecting the requested minimum material. Shared-star endpoint setbacks on the nine cut edges are calculated from their narrowest incident angle; see `leo-geometry.json`. All cutouts are checked against AF37 and the rounded AF30 optical window.\n\nSource chart data is from the local reference snapshot attributed to Stellarium Modern (CC BY-SA 4.0); its coordinates are tied to HIP identifiers and the local Hipparcos I/239 table (Credit: ESA, CC BY-NC 3.0 IGO). Check both licenses for redistribution or commercial use. IAU materials explain that constellations are areas and their stick figures do not have one universally mandated line topology.\n\n## Visual and integration notes\n\nThe generated two-face preview uses a warm neutral gray base behind the existing green single-ink snake image. It shows appearance only; the real substrate color and ink opacity need a physical sample. For a first manual import, place the 37mm `leo-artwork.svg` as the rear-side color illustration, then use `leo-geometry.svg` as a geometry review reference and map its circles/slots into the shared stack design. Keep the snake original as the front-side art. Verify rear-face orientation after importing: the current geometry coordinates follow the local Leo chart's screen view; any through-stack optical projection may require a horizontal reflection.\n\nThe geometry candidate is not yet integrated into the five-up 100x100 panel, does not model the common core/LED/NFC details, and is not manufacturing release data.\n'''
(OUT/'README.md').write_text(readme,encoding='utf-8')
# Raster previews are rendered with the configured Sharp runtime, never by editing a PNG in Python.
import subprocess
node=r'C:\Users\20177\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
sharp=r'C:\Users\20177\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\sharp'
js=r'''const fs=require('fs');const sharp=require(process.argv[1]);const dir=process.argv[2];(async()=>{const art=await sharp(fs.readFileSync(dir+'/leo-artwork.svg'),{density:300}).png().toBuffer();await sharp(art).png().toFile(dir+'/leo-artwork-preview.png');await sharp(fs.readFileSync(dir+'/leo-geometry.svg'),{density:300}).png().toFile(dir+'/leo-geometry-preview.png');const size=900;const oct=`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900"><polygon points="219,0 681,0 900,219 900,681 681,900 219,900 0,681 0,219" fill="#c9c7c0"/></svg>`;const octMask=Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900"><polygon points="219,0 681,0 900,219 900,681 681,900 219,900 0,681 0,219" fill="white"/></svg>`);const mask=await sharp(octMask).png().toBuffer();const snakeArt=await sharp(dir+'/../../artwork/reference-collection/talisman-single-ink-v1/snake-single-ink.png').resize(756,756).png().toBuffer();let snakeCanvas=await sharp({create:{width:size,height:size,channels:4,background:{r:0,g:0,b:0,alpha:0}}}).composite([{input:snakeArt,left:72,top:72}]).png().toBuffer();snakeCanvas=await sharp(snakeCanvas).composite([{input:mask,blend:'dest-in'}]).png().toBuffer();const darkOct=Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900"><polygon points="219,0 681,0 900,219 900,681 681,900 219,900 0,681 0,219" fill="#17232f"/></svg>`);let leo=await sharp(art).resize(900,900).png().toBuffer();leo=await sharp(leo).composite([{input:mask,blend:'dest-in'}]).png().toBuffer();const page=Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1860" height="1000"><rect width="1860" height="1000" fill="#ece9e1"/><polygon points="249,20 711,20 930,239 930,681 711,900 249,900 30,681 30,239" fill="#c9c7c0"/><polygon points="1149,20 1611,20 1830,239 1830,681 1611,900 1149,900 930,681 930,239" fill="#17232f"/><text x="480" y="960" text-anchor="middle" font-family="sans-serif" font-size="26" letter-spacing="4" fill="#4c4a45">SNAKE</text><text x="1380" y="960" text-anchor="middle" font-family="sans-serif" font-size="26" letter-spacing="4" fill="#4c4a45">LEO</text></svg>`);await sharp(page).composite([{input:snakeCanvas,left:30,top:20},{input:leo,left:930,top:20}]).png().toFile(dir+'/snake-leo-two-face-preview.png');})();'''
subprocess.run([node,'-e',js,sharp,str(OUT)],check=True)
snake_after=sha(snake)
if snake_after != report['snake_png_sha256_before_build']:
    raise RuntimeError('The source snake PNG changed during preview rendering')
report['snake_png_sha256_after_build']=snake_after
report['snake_input_unchanged']=True
(OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(OUT),'status':report['status'],'stars':len(stars),'source_edges':len(edges),'physical_slots':len(slots),'print_only_edges':visual_only,'min_shared_web':round(min_incident[0],6),'min_nonincident_gap':round(min_nonincident[0],6) if min_nonincident[0]!=float('inf') else None,'snake_sha256':sha(snake)},ensure_ascii=False))
