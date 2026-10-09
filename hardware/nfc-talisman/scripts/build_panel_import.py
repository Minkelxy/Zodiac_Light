"""Compile mechanical/art data and part placements into EasyEDA bridge scripts.

Source board geometry is millimetres from panel-top-left, Y down. EasyEDA PCB
coordinates use mils, with panel Y transformed by 100 mm - Y. Core components
retain their local EasyEDA +Y placement convention around the panel centre.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEOM = json.loads((ROOT / "geometry" / "design.json").read_text(encoding="utf-8"))
ART = json.loads((ROOT / "artwork" / "art_data.json").read_text(encoding="utf-8"))
NET = json.loads((ROOT / "electrical" / "netlist.json").read_text(encoding="utf-8"))
PANEL_UUID = "4a4719695b24dc2b"


def clean_ring(points):
    pts = [list(map(float, p)) for p in points]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def simplify_ring(points, tolerance=0.003):
    from shapely.geometry import Polygon

    poly = Polygon(clean_ring(points))
    if not poly.is_valid:
        from shapely.validation import explain_validity
        raise ValueError(f"invalid source polygon: {explain_validity(poly)}")
    poly = poly.simplify(tolerance, preserve_topology=True)
    if poly.is_empty or not poly.is_valid or poly.geom_type != "Polygon":
        raise ValueError("polygon simplification changed geometry type")
    return clean_ring(poly.exterior.coords)


def source_panel_geometry():
    panel = GEOM["panel"]
    rings = [{"id": "panel_outer", "points": simplify_ring(panel["outer_ring"])}]
    for i, route in enumerate(panel["route_cutouts"]):
        rings.append({"id": f"panel_route_{i+1}", "points": simplify_ring(route["exterior"])})
        for j, hole in enumerate(route.get("holes", [])):
            rings.append({"id": f"panel_route_{i+1}_hole_{j+1}", "points": simplify_ring(hole)})
    drills = [{"id": x["id"], "xy": x["center"], "diameter": x["diameter_mm"]}
              for x in panel["drills"]]
    for board in GEOM["boards"]:
        for cutout in board.get("cutouts", []):
            rings.append({"id": f"{board['id']}_{cutout['id']}",
                          "points": simplify_ring(cutout["ring"])})
        for drill in board.get("drills", []):
            drills.append({"id": drill["id"], "xy": drill["center"],
                           "diameter": drill["diameter_mm"]})
    return rings, drills


CORE_PARTS = [
    ["U1", "C710403", 0.0, 0.0, 0, "TOP"],
    ["D1", "C5875720", -5.9944, 0.0, 0, "TOP"],
    ["C1", "C162182", 2.5, 0.0, 0, "TOP"],
    ["CT1", "C60137", -1.8, 2.5, 0, "TOP"],
    ["CT2", "C60137", 0.2, 2.5, 0, "TOP"],
    ["R5", "C105579", -2.5, -1.8, 0, "TOP"],
    ["R6", "C105579", 2.5, -1.8, 0, "TOP"],
    ["R7", "C105579", 0.0, -3.5, 0, "TOP"],
    ["R1", "C114662", -3.5, 0.0, 0, "TOP"],
    ["R2", "C114662", 3.5, 4.0, 0, "TOP"],
    ["D2", "C5875720", 6.0, 4.0, 0, "TOP"],
    ["R3", "C114662", -3.5, 0.0, 0, "BOTTOM"],
    ["D3", "C5875720", -6.0, 0.0, 0, "BOTTOM"],
    ["R4", "C114662", 3.5, -4.0, 0, "BOTTOM"],
    ["D4", "C5875720", 6.0, -4.0, 0, "BOTTOM"],
]


def bridge_header(data):
    return """const D=__DATA__;
const PANEL=__PANEL__;
const MM=1/0.0254;
const L={TOP:1,BOTTOM:2,TOP_SILK:3,BOTTOM_SILK:4,TOP_MASK:5,BOTTOM_MASK:6,OUTLINE:11,MULTI:12};
const xy=(x,y)=>[x*MM,(100-y)*MM];
const poly=(pts,center=[0,0])=>{
  if(!Array.isArray(pts)||pts.length<3)throw Error('polygon needs >=3 points');
  const first=xy(pts[0][0]+center[0],pts[0][1]+center[1]);
  const src=[first[0],first[1],'L'];
  for(const p of pts.slice(1)){const q=xy(p[0]+center[0],p[1]+center[1]);src.push(q[0],q[1]);}
  const result=eda.pcb_MathPolygon.createPolygon(src);
  if(!result)throw Error('createPolygon failed');
  return result;
};
const active=await eda.dmt_EditorControl.openDocument(PANEL);
await new Promise(r=>setTimeout(r,800));
const info=await eda.dmt_Pcb.getCurrentPcbInfo();
if(info?.uuid!==PANEL)throw Error('active PCB mismatch: '+JSON.stringify(info));
""".replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))).replace(
        "__PANEL__", json.dumps(PANEL_UUID))


def main():
    rings, drills = source_panel_geometry()
    # Outline and plated-parameter-free drill import. Holes use MULTI pads with
    # matching round pad/drill diameter and metallization=false (NPTH).
    data = {"rings": rings, "drills": drills}
    script = bridge_header(data) + r'''const oldPolys=await eda.pcb_PrimitivePolyline.getAll(undefined,L.OUTLINE);
const allPads=await eda.pcb_PrimitivePad.getAll();
const drilled=allPads.filter(p=>{const h=p.getState_Hole();return h!==undefined&&h!==null;});
const expectedDrills=new Set(D.drills.map(d=>String(d.id).toUpperCase()));
const managedDrills=drilled.filter(p=>expectedDrills.has(String(p.getState_PadNumber()).toUpperCase()));
if(oldPolys.length||drilled.length){
  if(oldPolys.length!==D.rings.length||drilled.length!==D.drills.length||managedDrills.length!==drilled.length)
    throw Error('Existing panel geometry does not exactly match the managed outline/drill set; refusing partial replacement: '+JSON.stringify({outlines:oldPolys.length,expectedOutlines:D.rings.length,drills:drilled.length,expectedDrills:D.drills.length,managedDrills:managedDrills.length}));
  await eda.pcb_PrimitivePolyline.delete(oldPolys.map(p=>p.getState_PrimitiveId()));
  await eda.pcb_PrimitivePad.delete(managedDrills.map(p=>p.getState_PrimitiveId()));
}
const made={outline:[],npth:[]};
for(const item of D.rings){
  const obj=await eda.pcb_PrimitivePolyline.create('',L.OUTLINE,poly(item.points),0.1*MM,false);
  if(!obj)throw Error('board-outline loop failed: '+item.id);
  made.outline.push({id:item.id,primitiveId:obj.getState_PrimitiveId()});
}
for(const d of D.drills){
  const [x,y]=xy(d.xy[0],d.xy[1]),diameter=d.diameter*MM;
  const obj=await eda.pcb_PrimitivePad.create(L.MULTI,d.id,x,y,0,['ELLIPSE',diameter,diameter],'',['ROUND',diameter],0,0,0,false,0,[],null,null,false);
  if(!obj)throw Error('NPTH drill failed: '+d.id);
  made.npth.push({id:d.id,primitiveId:obj.getState_PrimitiveId(),diameter_mm:d.diameter});
}
const save=await eda.pcb_Document.save();
return {uuid:info.uuid,replacedCounts:{outline:oldPolys.length,npth:managedDrills.length},createdCounts:{outline:made.outline.length,npth:made.npth.length},made,save};'''
    (ROOT / "scripts" / "17a-import-panel-outline.js").write_text(script, encoding="utf-8")

    # The horse artwork is intentionally left for manual image import in
    # EasyEDA, per the user's direction. Only the Sagittarius Latin lettering
    # is generated here; it is imported as Top Silkscreen vector polylines.
    sagittarius_silk = ART["sagittarius_silkscreen"]
    artdata = {"sagittarius_silkscreen": sagittarius_silk}
    script = bridge_header(artdata) + r'''const oldImages=await eda.pcb_PrimitiveImage.getAll();
const oldTopPolylines=await eda.pcb_PrimitivePolyline.getAll(undefined,L.TOP_SILK);
if(oldImages.length||oldTopPolylines.length)throw Error('Panel already contains image/Top Silkscreen artwork; refusing duplicate import');
const made=[];
async function addStrokes(records,cx,cy){
  for(const rec of records){
    const pts=rec.points.slice();
    if(rec.closed&&pts.length>2&&(pts[0][0]!==pts[pts.length-1][0]||pts[0][1]!==pts[pts.length-1][1]))pts.push(pts[0]);
    const first=xy(cx+pts[0][0],cy+pts[0][1]),src=[first[0],first[1],'L'];
    for(const p of pts.slice(1)){const q=xy(cx+p[0],cy+p[1]);src.push(q[0],q[1]);}
    const path=eda.pcb_MathPolygon.createPolygon(src);
    if(!path)throw Error('silkscreen path failed: '+rec.id);
    const obj=await eda.pcb_PrimitivePolyline.create('',L.TOP_SILK,path,rec.width_mm*MM,false);
    if(!obj)throw Error('silkscreen polyline failed: '+rec.id);
    made.push({id:rec.id,primitiveId:obj.getState_PrimitiveId(),vertexCount:pts.length});
  }
}
await addStrokes(D.sagittarius_silkscreen,79.5,76.5);
const save=await eda.pcb_Document.save();
return {uuid:info.uuid,createdCount:made.length,created:made,save,horseArt:'intentionally omitted for manual image import'};'''
    (ROOT / "scripts" / "17b-import-panel-art.js").write_text(script, encoding="utf-8")

    # Real library footprints in the panel core region, with schematic-matched
    # pad nets. The antenna remains a separately reviewed net-tie geometry task.
    net_components = {c["reference"]: c["pins"] for c in NET["components"]}
    coredata = {"parts": CORE_PARTS, "nets": net_components}
    script = bridge_header(coredata) + r'''const oldComponents=await eda.pcb_PrimitiveComponent.getAll();
if(oldComponents.length)throw Error('Panel already contains components; refusing duplicate placement');
const lib=await eda.lib_LibrariesList.getSystemLibraryUuid(),byCode={},created=[];
for(const [ref,code,dx,dy,rot,side] of D.parts){
  if(!byCode[code]){
    const found=await eda.lib_Device.searchByProperties({supplierId:code},undefined,undefined,undefined,5,1);
    if(!found?.length)throw Error('device not found: '+code);
    byCode[code]=found[0];
  }
  const x=(50+dx)*MM,y=(50+dy)*MM;
  const comp=await eda.pcb_PrimitiveComponent.create({libraryUuid:lib,uuid:byCode[code].uuid},side==='BOTTOM'?L.BOTTOM:L.TOP,x,y,rot,false);
  if(!comp)throw Error('component placement failed: '+ref);
  await eda.pcb_PrimitiveComponent.modify(comp,{designator:ref,name:ref==='CT2'?'TUNE C0G DNP':byCode[code].name,uniqueId:ref,otherProperty:{Population:ref==='CT2'?'DNP':'Fit','PCB Side':side}});
  const pins=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(comp.getState_PrimitiveId()),expected=D.nets[ref];
  for(const pin of pins){
    const number=String(pin.getState_PadNumber()),key=ref.startsWith('D')?({'1':'K','2':'A'}[number]):number,net=expected?.[key];
    if(!net)throw Error('net mapping missing for '+ref+'.'+number);
    pin.setState_Net(net);await pin.done();
  }
  created.push({ref,id:comp.getState_PrimitiveId(),padCount:pins.length});
}
const save=await eda.pcb_Document.save();
return {uuid:info.uuid,createdCount:created.length,created,save,warning:'PCB antenna spiral bridge-fill is not yet imported; VOUT/GND routing remains incomplete.'};'''
    (ROOT / "scripts" / "17c-import-panel-core.js").write_text(script, encoding="utf-8")

    print(json.dumps({
        "scripts": [
            {"file": "17a-import-panel-outline.js", "bytes": (ROOT / "scripts" / "17a-import-panel-outline.js").stat().st_size},
            {"file": "17b-import-panel-art.js", "bytes": (ROOT / "scripts" / "17b-import-panel-art.js").stat().st_size},
            {"file": "17c-import-panel-core.js", "bytes": (ROOT / "scripts" / "17c-import-panel-core.js").stat().st_size},
        ],
        "outline_loops": len(rings), "npth_drills": len(drills),
        "horse_art": "manual import by user",
        "sagittarius_silk_strokes": len(sagittarius_silk),
        "core_components": len(CORE_PARTS),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
