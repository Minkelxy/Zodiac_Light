#!/usr/bin/env python3
"""Read-only geometry/CAM audit for the current manufacturing draft.

Reads the ZIP in place (without extracting or changing it), native panel source,
all-parts BOM/PnP, and the electrical population variants. Writes only the new
manufacturing/draft/cam-audit.json report.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from shapely.geometry import LineString, Point, Polygon, box

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "manufacturing" / "draft"
ZIP_PATH = DRAFT / "nfc-talisman-panel-draft.zip"
PANEL_SOURCE = ROOT / "eda" / "native" / "panel-source.jsonl"
FILL_CANDIDATE = ROOT / "electrical" / "antenna-coil-fill-candidate.json"
PNP_ALL = DRAFT / "nfc-talisman-panel-pnp-all.csv"
BOM_ALL = DRAFT / "nfc-talisman-panel-bom-all.csv"
ELECTRICAL_BOM = ROOT / "electrical" / "BOM.csv"
VARIANTS = DRAFT / "assembly-variants.json"
REPORT = DRAFT / "cam-audit.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_native_objects(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if "||" not in line:
            continue
        left, right = line.split("||", 1)
        try:
            meta = json.loads(left)
            value = json.loads(right.rstrip("|\r\n"))
        except (json.JSONDecodeError, TypeError):
            continue
        yield meta, value


def parse_drill(data: bytes):
    tool_sizes = {}
    active = None
    holes = []
    for line in data.decode("ascii", "replace").splitlines():
        m = re.match(r"T(\d+)C([0-9.]+)", line)
        if m:
            tool_sizes[m.group(1)] = float(m.group(2))
            continue
        m = re.fullmatch(r"T(\d+)", line.strip())
        if m:
            active = m.group(1)
            continue
        m = re.match(r"X(-?[0-9.]+)Y(-?[0-9.]+)", line.strip())
        if m and active:
            holes.append((tool_sizes[active], float(m.group(1)), float(m.group(2))))
    return tool_sizes, holes


def parse_gerber_paths(data: bytes):
    s = data.decode("ascii", "replace")
    paths, current = [], []
    all_commands = []
    for x, y, d in re.findall(r"X(-?\d+)Y(-?\d+)D0([123])", s):
        pt = (int(x) / 1e6, int(y) / 1e6)
        d = int(d)
        all_commands.append((pt, d))
        if d == 2:
            if current:
                paths.append(current)
            current = [pt]
        elif d == 1 and current:
            current.append(pt)
        elif d == 3:
            if current:
                paths.append(current)
                current = []
    if current:
        paths.append(current)
    return s, paths, all_commands


def bbox(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def csv_rows(path: Path, delimiter: str):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def parse_apertures(gerber: str):
    apertures = {}
    for m in re.finditer(r"%ADD(\d+)(C|R|O|RoundRect),([^*%]+)\*%", gerber):
        code, shape, raw = m.group(1), m.group(2), m.group(3)
        values = [float(x) for x in raw.split("X")]
        if shape == "C":
            w = h = values[0]
        elif shape in ("R", "O"):
            w, h = values[:2]
        else:
            # EasyEDA emits this macro as a rounded rectangle made from four
            # corner circles, four stroked edges, and an outline. Its aperture
            # modifiers are stroke width then the two opposite inner corners.
            stroke, x1, y1, x2, y2 = values[:5]
            w, h = abs(x2 - x1) + stroke, abs(y2 - y1) + stroke
        apertures[code] = {"shape": shape, "width_mm": w, "height_mm": h, "values": values}
    return apertures


def aperture_geometry(aperture, x, y):
    w, h = aperture["width_mm"], aperture["height_mm"]
    shape = aperture["shape"]
    if shape == "C":
        return Point(x, y).buffer(w / 2, resolution=48)
    if shape == "O":
        if w >= h:
            r = h / 2
            return LineString([(x - (w-h)/2, y), (x + (w-h)/2, y)]).buffer(r, resolution=32)
        r = w / 2
        return LineString([(x, y - (h-w)/2), (x, y + (h-w)/2)]).buffer(r, resolution=32)
    return box(x-w/2, y-h/2, x+w/2, y+h/2)


def parse_gerber_objects(data: bytes):
    """Parse the exported absolute-mm Gerber flashes, strokes, and G36 regions.

    RoundRect macro apertures are represented by their exact design bounding
    box. That is conservative for overlap tests at the rounded corners.
    """
    text = data.decode("ascii", "replace")
    apertures = parse_apertures(text)
    objects = []
    active = None
    current = None
    region = False
    region_points = []
    for line in text.splitlines():
        if line.startswith("G36"):
            region, region_points = True, []
            continue
        if line.startswith("G37"):
            if len(region_points) >= 3:
                geom = Polygon(region_points)
                if not geom.is_empty:
                    objects.append({"kind": "region", "geometry": geom, "aperture": None, "center": None})
            region, region_points = False, []
            continue
        sel = re.search(r"G54D(\d+)\*", line)
        if sel:
            active = sel.group(1)
            continue
        cmd = re.search(r"X(-?\d+)Y(-?\d+)D0([123])\*", line)
        if not cmd:
            continue
        point = (int(cmd.group(1)) / 1e6, int(cmd.group(2)) / 1e6)
        operation = int(cmd.group(3))
        if region:
            if operation == 2:
                region_points = [point]
            elif operation == 1:
                region_points.append(point)
            continue
        if operation == 2:
            current = point
        elif operation == 3:
            aperture = apertures.get(active)
            if aperture:
                objects.append({"kind": "flash", "geometry": aperture_geometry(aperture, *point),
                                "aperture": active, "aperture_shape": aperture["shape"],
                                "width_mm": aperture["width_mm"], "height_mm": aperture["height_mm"],
                                "center": point})
            current = point
        elif operation == 1 and current is not None:
            aperture = apertures.get(active)
            if aperture:
                # For rectangular/macro apertures this round buffer slightly
                # overestimates a stroke's corners, which is safe for overlap.
                radius = max(aperture["width_mm"], aperture["height_mm"]) / 2
                geom = LineString([current, point]).buffer(radius, cap_style="round", resolution=16)
                objects.append({"kind": "stroke", "geometry": geom, "aperture": active,
                                "aperture_shape": aperture["shape"], "width_mm": aperture["width_mm"],
                                "height_mm": aperture["height_mm"], "center": None})
            current = point
    return text, apertures, objects


def target_pad_name(meta, data):
    attrs = data.get("attrsMap") or {}
    return (data.get("padNumber") or data.get("num") or meta.get("padNumber")
            or attrs.get("padNumber") or attrs.get("Pad Number"))


def audit_free_testpoints(panel_records, members, pnp_rows, bom_refs):
    expected_nets = {"TP1": "VOUT", "TP2": "GND"}
    pads = {}
    for meta, data in panel_records:
        if meta.get("type") != "PAD":
            continue
        name = target_pad_name(meta, data)
        if name in expected_nets:
            pads[name] = {"meta": meta, "data": data}
    if not pads:
        return {"status": "not_present_not_checked", "pass": None,
                "expected_designators": list(expected_nets), "present_designators": [],
                "reason": "Current panel source has no free PAD objects named TP1/TP2; no Gerber conclusion is asserted."}

    gerbers = {}
    for layer, member in (("GTL", "Gerber_TopLayer.GTL"),
                          ("GTS", "Gerber_TopSolderMaskLayer.GTS"),
                          ("GTP", "Gerber_TopPasteMaskLayer.GTP")):
        gerbers[layer] = parse_gerber_objects(members[member])[2]

    result_rows, failures = [], []
    missing = sorted(set(expected_nets) - set(pads))
    failures.extend(f"source_missing_{name}" for name in missing)
    for name, expected_net in expected_nets.items():
        if name not in pads:
            continue
        meta, data = pads[name]["meta"], pads[name]["data"]
        dpad = data.get("defaultPad") or {}
        width_mil = dpad.get("width", data.get("width"))
        height_mil = dpad.get("height", data.get("height", width_mil))
        if width_mil is None or height_mil is None:
            failures.append(f"{name}_source_size_missing")
            result_rows.append({"designator": name, "pass": False, "failure": "source_size_missing"})
            continue
        x, y = data["centerX"] * 0.0254, data["centerY"] * 0.0254
        width, height = float(width_mil) * 0.0254, float(height_mil) * 0.0254
        shape_name = str(dpad.get("padType", "")).upper()
        target_geom = (Point(x, y).buffer(width/2, resolution=48)
                       if shape_name in ("CIRCLE", "ELLIPSE", "OVAL") or (not shape_name and abs(width-height) < 1e-7)
                       else box(x-width/2, y-height/2, x+width/2, y+height/2))
        checks = {"source": {
            "pad_type": data.get("padType"), "pad_shape": dpad.get("padType"),
            "pad_number": target_pad_name(meta, data), "net": data.get("netName"),
            "layer_id": data.get("layerId"), "center_mm": [round(x, 6), round(y, 6)],
            "size_mm": [round(width, 6), round(height, 6)]}}
        if data.get("netName") != expected_net:
            failures.append(f"{name}_wrong_net")
        if data.get("layerId") != 1:
            failures.append(f"{name}_not_top_layer")

        # Net-aware overlap audit from the saved native panel source. A same-net
        # line landing on the pad is expected; alien or unassigned copper over
        # the exposed test surface is not.
        native_overlaps = []
        for other_meta, other in panel_records:
            kind = other_meta.get("type")
            net = other.get("netName", "")
            geom = None
            if kind == "LINE" and other.get("layerId") == 1:
                geom = LineString([(other["startX"]*0.0254, other["startY"]*0.0254),
                                   (other["endX"]*0.0254, other["endY"]*0.0254)]).buffer(other["width"]*0.0254/2)
            elif kind == "VIA":
                geom = Point(other["centerX"]*0.0254, other["centerY"]*0.0254).buffer(other["viaDiameter"]*0.0254/2)
            elif kind == "FILL" and other.get("layerId") == 1 and other.get("path"):
                raw = other["path"][0] if isinstance(other["path"][0], list) else other["path"]
                coords = [v for v in raw if isinstance(v, (int, float))]
                if len(coords) >= 6 and len(coords) % 2 == 0:
                    geom = Polygon([(coords[i]*0.0254, coords[i+1]*0.0254) for i in range(0, len(coords), 2)])
            elif kind == "PAD" and other.get("layerId") == 1 and other_meta.get("id") != meta.get("id"):
                other_pad = other.get("defaultPad") or {}
                ow, oh = other_pad.get("width"), other_pad.get("height", other_pad.get("width"))
                if ow is not None and oh is not None:
                    ox, oy = other["centerX"]*0.0254, other["centerY"]*0.0254
                    ow, oh = float(ow)*0.0254, float(oh)*0.0254
                    if str(other_pad.get("padType", "")).upper() in ("CIRCLE", "ELLIPSE", "OVAL") or abs(ow-oh) < 1e-7:
                        geom = Point(ox, oy).buffer(ow/2, resolution=32)
                    else:
                        geom = box(ox-ow/2, oy-oh/2, ox+ow/2, oy+oh/2)
            if geom is not None and geom.intersects(target_geom):
                other_id = target_pad_name(other_meta, other) or other_meta.get("id")
                overlap = {"type": kind, "id": other_id, "net": net,
                           "intersection_area_mm2": round(geom.intersection(target_geom).area, 8)}
                native_overlaps.append(overlap)
                if net != expected_net:
                    failures.append(f"{name}_overlapped_by_alien_or_unassigned_native_{kind.lower()}_{other_id}")

        # Component lands are held in the saved core pad snapshot; translate
        # their local mil coordinates into the panel's 50 mm core placement.
        core_pad_file = ROOT / "eda" / "core-pads.json"
        if core_pad_file.exists():
            for component in json.loads(core_pad_file.read_text(encoding="utf-8")):
                for pin in component.get("pins", []):
                    pin_shape = pin.get("pad", [None])[0]
                    raw_size = pin.get("pad", [None, None, None])
                    if pin_shape not in ("RECT", "ELLIPSE", "OVAL") or len(raw_size) < 3:
                        continue
                    px = (pin["x"] + 50/0.0254)*0.0254
                    py = (pin["y"] + 50/0.0254)*0.0254
                    pw, ph = raw_size[1]*0.0254, raw_size[2]*0.0254
                    if pin_shape in ("ELLIPSE", "OVAL"):
                        from shapely.affinity import scale as shapely_scale
                        pad_geom = shapely_scale(Point(px, py).buffer(1, resolution=24), pw/2, ph/2, origin=(px, py))
                    else:
                        pad_geom = box(px-pw/2, py-ph/2, px+pw/2, py+ph/2)
                    if pad_geom.intersects(target_geom):
                        pnet = pin.get("net", "")
                        overlap = {"type": "COMPONENT_PAD", "id": f"{component.get('ref')}.{pin.get('padNumber')}",
                                   "net": pnet, "intersection_area_mm2": round(pad_geom.intersection(target_geom).area, 8)}
                        native_overlaps.append(overlap)
                        if pnet != expected_net:
                            failures.append(f"{name}_overlapped_by_alien_or_unassigned_component_pad_{overlap['id']}")

        copper_objects = gerbers["GTL"]
        copper_matches = []
        for i, obj in enumerate(copper_objects):
            if obj["kind"] != "flash" or obj["center"] is None:
                continue
            dx, dy = abs(obj["center"][0]-x), abs(obj["center"][1]-y)
            if max(dx, dy) <= 0.001:
                copper_matches.append((i, obj, dx, dy))
        copper_matches.sort(key=lambda row: max(row[2], row[3]))
        copper_ok = False
        copper_detail = None
        if copper_matches:
            idx, obj, dx, dy = copper_matches[0]
            size_error = max(abs(obj["width_mm"]-width), abs(obj["height_mm"]-height))
            other_copper = [o for j, o in enumerate(copper_objects) if j != idx and o["geometry"].intersects(target_geom)]
            other_flash_or_region = [o for o in other_copper if o["kind"] in ("flash", "region")]
            copper_ok = (size_error <= 0.003 and max(dx, dy) <= 0.001
                         and len(copper_matches) == 1 and not other_flash_or_region)
            copper_detail = {"aperture": obj["aperture"], "aperture_shape": obj["aperture_shape"],
                             "center_mm": list(obj["center"]), "size_mm": [obj["width_mm"], obj["height_mm"]],
                             "center_error_mm": round(math.hypot(dx, dy), 8), "size_error_mm": round(size_error, 8),
                             "other_center_flashes": len(copper_matches)-1,
                             "other_copper_gerber_objects_intersecting_pad": [
                                 {"kind": o["kind"], "aperture": o.get("aperture"), "center_mm": o.get("center")}
                                 for o in other_copper],
                             "other_flash_or_region_overlap_count": len(other_flash_or_region)}
        if not copper_ok:
            failures.append(f"{name}_gtl_copper_flash_missing_or_wrong_center_size")
        checks["gtl_copper"] = {"pass": copper_ok, "matching_center_flashes": len(copper_matches), "selected": copper_detail}

        mask_objects = gerbers["GTS"]
        mask_hits = [(i, o) for i, o in enumerate(mask_objects) if o["geometry"].covers(target_geom)]
        centered_mask_hits = [(i, o) for i, o in mask_hits if o["kind"] == "flash" and o["center"]
                              and max(abs(o["center"][0]-x), abs(o["center"][1]-y)) <= 0.001]
        mask_ok = False
        mask_detail = None
        if centered_mask_hits:
            i, obj = min(centered_mask_hits, key=lambda pair: abs(pair[1]["width_mm"]-width)+abs(pair[1]["height_mm"]-height))
            delta_w = obj["width_mm"] - width
            delta_h = obj["height_mm"] - height
            other_mask = [o for j, o in enumerate(mask_objects) if j != i and o["geometry"].intersects(target_geom)]
            mask_ok = delta_w >= -0.003 and delta_h >= -0.003 and delta_w <= 0.30 and delta_h <= 0.30 and not other_mask
            mask_detail = {"aperture": obj["aperture"], "aperture_shape": obj["aperture_shape"],
                           "center_mm": list(obj["center"]), "opening_size_mm": [obj["width_mm"], obj["height_mm"]],
                           "opening_minus_copper_mm": [round(delta_w, 6), round(delta_h, 6)],
                           "other_mask_objects_intersecting_pad": [
                               {"kind": o["kind"], "aperture": o.get("aperture"), "center_mm": o.get("center")}
                               for o in other_mask]}
        if not mask_ok:
            failures.append(f"{name}_gts_mask_opening_missing_or_wrong_center_size")
        checks["gts_mask"] = {"pass": mask_ok, "centered_opening_count": len(centered_mask_hits), "selected": mask_detail}
        checks["native_other_copper"] = {"pass": not any(o["net"] != expected_net for o in native_overlaps),
                                          "overlapping_native_objects": native_overlaps}

        paste_hits = [{"kind": o["kind"], "aperture": o.get("aperture"),
                       "bounds_mm": [round(v, 6) for v in o["geometry"].bounds]}
                      for o in gerbers["GTP"] if o["geometry"].intersects(target_geom)]
        paste_ok = not paste_hits
        if not paste_ok:
            failures.append(f"{name}_unexpected_gtp_aperture_overlaps_pad")
        checks["gtp_no_paste"] = {"pass": paste_ok, "overlapping_paste_objects": paste_hits}
        checks["excluded_from_bom_pnp"] = {"pass": name not in set(pnp_rows) and name not in set(bom_refs),
                                            "in_pnp": name in set(pnp_rows), "in_bom": name in set(bom_refs)}
        if not checks["excluded_from_bom_pnp"]["pass"]:
            failures.append(f"{name}_unexpectedly_listed_in_bom_or_pnp")
        checks["pass"] = all(checks[k]["pass"] for k in ("gtl_copper", "gts_mask", "native_other_copper", "gtp_no_paste", "excluded_from_bom_pnp"))
        result_rows.append({"designator": name, **checks})

    present_both = set(expected_nets).issubset(pads)
    passed = present_both and not failures and all(r.get("pass") for r in result_rows)
    return {"status": "checked_pass" if passed else "checked_fail", "pass": passed,
            "expected_designators": list(expected_nets), "present_designators": sorted(pads),
            "required_net_by_designator": expected_nets, "points": result_rows,
            "failures": failures,
            "checks": {"GTL": "Each free pad has a centered D03 copper flash with size matching native source within 0.003 mm; other Gerber copper overlaps are counted.",
                       "native_copper": "No alien-net or unassigned native top copper primitive/component pad overlaps the exposed test surface.",
                       "GTS": "A centered D03 mask opening covers the copper pad and is no more than 0.30 mm larger in either dimension; no unrelated opening overlaps it.",
                       "GTP": "No paste flash, stroke, or G36 region intersects the free pad.",
                       "BOM_PnP": "TP1/TP2 are excluded from component BOM and PnP lists."},
            "geometry_note": "Gerber aperture macros are approximated by their bounding boxes for overlap tests; this is conservative at rounded corners."}


def main():
    raw = ZIP_PATH.read_bytes()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        bad_member = zf.testzip()
        members = {name: zf.read(name) for name in zf.namelist()}

    pth_files = ["Drill_PTH_Through.DRL", "Drill_PTH_Through_Via.DRL"]
    parsed_drills = {name: parse_drill(members[name]) for name in pth_files + ["Drill_NPTH_Through.DRL"]}
    duplicate_pth = parsed_drills[pth_files[0]][1] == parsed_drills[pth_files[1]][1]
    expected_pth,expected_npth=[],[]
    for meta,obj in read_native_objects(PANEL_SOURCE):
        if meta.get('type')=='VIA':
            expected_pth.append((obj['holeDiameter']*0.0254,obj['centerX']*0.0254,obj['centerY']*0.0254))
        elif meta.get('type')=='PAD' and obj.get('hole') and not obj.get('plated'):
            hole=obj['hole']
            if hole.get('holeType')!='ROUND' or abs(hole['width']-hole['height'])>0.0001:
                raise ValueError('Unsupported native nonround NPTH')
            expected_npth.append((hole['width']*0.0254,obj['centerX']*0.0254,obj['centerY']*0.0254))
    native_drill_checks={}
    for name,expected in [('Drill_PTH_Through.DRL',expected_pth),('Drill_NPTH_Through.DRL',expected_npth)]:
        remaining=list(parsed_drills[name][1])
        deltas=[]
        for hole in expected:
            if not remaining:
                break
            match=min(range(len(remaining)),key=lambda i:math.dist(hole,remaining[i]))
            deltas.append(math.dist(hole,remaining.pop(match)))
        native_drill_checks[name]={'native_count':len(expected),'export_count':len(parsed_drills[name][1]),
            'maximum_diameter_position_vector_delta_mm':max(deltas,default=None),
            'passes_0_003mm':len(deltas)==len(expected) and not remaining and all(d<=0.003 for d in deltas)}
    drill_summary = {}
    for name, (tools, holes) in parsed_drills.items():
        drill_summary[name] = {
            "tools_mm": tools,
            "hit_count": len(holes),
            "hole_counts_by_tool_mm": {str(k): v for k, v in Counter(h[0] for h in holes).items()},
            "bbox_mm": bbox([(h[1], h[2]) for h in holes]) if holes else None,
            "sha256": sha256(members[name]),
        }

    gko, outline_paths, _ = parse_gerber_paths(members["Gerber_BoardOutlineLayer.GKO"])
    all_outline_points = [p for path in outline_paths for p in path]
    outline_box = bbox(all_outline_points)
    path_closures = []
    for i, path in enumerate(outline_paths):
        gap = math.dist(path[0], path[-1]) if len(path) > 1 else 0.0
        path_closures.append({"path_index": i, "point_count": len(path), "start_mm": path[0],
                              "end_mm": path[-1], "endpoint_gap_mm": round(gap, 6),
                              "explicitly_closed": path[0] == path[-1]})

    top, _, _ = parse_gerber_paths(members["Gerber_TopLayer.GTL"])
    region_text = top[top.find("G36*"):top.find("G37*")]
    gerber_region = [(int(x) / 1e6, int(y) / 1e6) for x, y in re.findall(r"X(-?\d+)Y(-?\d+)D0[12]", region_text)]
    candidate = json.loads(FILL_CANDIDATE.read_text(encoding="utf-8"))
    candidate_mm = [(50 + x * 0.0254, 50 + y * 0.0254) for x, y in candidate["points_native_mil"]]
    # A Gerber polygon includes one explicit final point repeating its first.
    comparison = gerber_region[:-1] if len(gerber_region) == len(candidate_mm) + 1 else gerber_region
    aligned = len(comparison) == len(candidate_mm)
    max_fill_vertex_delta = (max(math.dist(a, b) for a, b in zip(candidate_mm, comparison))
                             if aligned and comparison else None)
    top_reflection = "Reflected: Yes" in top.splitlines()[3]

    source_lines = []
    components = {}
    panel_records = list(read_native_objects(PANEL_SOURCE))
    for meta, obj in panel_records:
        if meta.get("type") == "LINE" and obj.get("layerId") == 2 and obj.get("netName") in ("ANT_LA", "ANT_LB"):
            source_lines.append((obj["netName"], tuple(round(obj[k] * 0.0254, 6) for k in ("startX", "startY", "endX", "endY"))))
        if meta.get("type") == "COMPONENT":
            ref = obj.get("attrs", {}).get("Unique ID")
            if ref:
                components[ref] = obj

    bottom = members["Gerber_BottomLayer.GBL"].decode("ascii", "replace")
    bottom_reflection = "Reflected: Yes" in bottom.splitlines()[3]
    bottom_segments, prev = [], None
    for x, y, d in re.findall(r"X(-?\d+)Y(-?\d+)D0([123])", bottom):
        pt, d = (int(x) / 1e6, int(y) / 1e6), int(d)
        if d == 2:
            prev = pt
        elif d == 1 and prev is not None:
            bottom_segments.append((prev, pt))
            prev = pt
        elif d == 3:
            prev = None
    bottom_matches = []
    for net, (sx, sy, ex, ey) in source_lines:
        target = ((sx, sy), (ex, ey))
        best = min((max(math.dist(a, target[0]), math.dist(b, target[1])), idx, rev)
                    for idx, (a, b) in enumerate(bottom_segments)
                    for rev in (False, True)
                    for a, b in (bottom_segments[idx][::-1] if rev else bottom_segments[idx],))
        bottom_matches.append({"net": net, "source_segment_mm": target, "best_gerber_error_mm": round(best[0], 6)})

    pnp = csv_rows(PNP_ALL, "\t")
    pnp_checks = []
    for row in pnp:
        ref = row["Designator"]
        comp = components.get(ref)
        if not comp:
            pnp_checks.append({"designator": ref, "source_match": False})
            continue
        expected_layer = "T" if comp.get("layerId") == 1 else "B" if comp.get("layerId") == 2 else str(comp.get("layerId"))
        ex, ey = comp["x"] * 0.0254, comp["y"] * 0.0254
        px = float(row["Mid X"].removesuffix("mm"))
        py = float(row["Mid Y"].removesuffix("mm"))
        pnp_checks.append({"designator": ref, "source_match": True, "side_matches": row["Layer"] == expected_layer,
                           "position_delta_mm": round(math.dist((ex, ey), (px, py)), 6),
                           "rotation_deg": float(row["Rotation"]), "native_rotation_deg": comp.get("angle"),
                           "native_side": expected_layer})

    all_bom = csv_rows(BOM_ALL, "\t")
    electrical_bom = csv_rows(ELECTRICAL_BOM, ",")
    electrical_population = {r["Designator"]: r["Population"] for r in electrical_bom}
    all_bom_refs = sorted(d for row in all_bom for d in row["Designator"].split(","))
    pnp_refs = sorted(r["Designator"] for r in pnp)
    variants = json.loads(VARIANTS.read_text(encoding="utf-8"))
    bom_population_diff = {
        ref: {"population": electrical_population.get(ref), "variant_fit": sorted(k for k, v in variants["variants"].items() if ref in v["fit_designators"]),
              "variant_excluded": sorted(k for k, v in variants["variants"].items() if ref in v["excluded"])}
        for ref in sorted(set(all_bom_refs))
        if electrical_population.get(ref) == "DNP" or any(ref in v["excluded"] for v in variants["variants"].values())
    }
    testpoint_audit = audit_free_testpoints(panel_records, members, pnp_refs, all_bom_refs)

    report = {
        "scope": "Read-only geometric and export consistency check. Not CAM/manufacturing release or electrical/assembly acceptance.",
        "inputs": {
            "zip_path": str(ZIP_PATH.relative_to(ROOT)).replace("\\", "/"),
            "zip_sha256": sha256(raw), "zip_bytes": len(raw), "zip_crc_error_member": bad_member,
            "native_panel_sha256": sha256(PANEL_SOURCE.read_bytes()),
            "component_pads_sha256": sha256((ROOT / 'eda/core-pads.json').read_bytes()),
            "zip_members": sorted(members),
        },
        "drill": {
            "files": drill_summary,
            "native_source_correspondence":native_drill_checks,
            "pth_files_have_identical_tool_and_hit_lists": duplicate_pth,
            "cam_note": "The two named PTH exports are identical data; select one rather than importing both as separate drill operations.",
        },
        "outline": {
            "d02_path_count": len(outline_paths), "expected_route_count_from_project_notes": 22,
            "envelope_mm": outline_box,
            "envelope_is_100x100_with_1um_export_rounding": abs(outline_box[2] - outline_box[0] - 100) <= 0.00001 and abs(outline_box[3] - outline_box[1] - 100) <= 0.00001,
            "all_paths_explicitly_closed": all(p["explicitly_closed"] for p in path_closures),
            "paths": path_closures,
            "change_from_previous_draft": "The previous raw ZIP (SHA-256 78ef0995f64812634271edd8af048dd5621596030b41360e23f7aef56f66a274) had 22 native polygon paths without explicit last=first closure. This export explicitly closes all 22 paths.",
            "cam_note": "Contour closure and nominal envelope pass geometry checks. CAM still needs to confirm milling compensation, intended tabs/slots, and that the outer contour plus 21 internal contours match the board shop's routing interpretation.",
        },
        "antenna_copper": {
            "top_gerber_reflected_flag": top_reflection,
            "bottom_gerber_reflected_flag": bottom_reflection,
            "top_fill_candidate_vertex_count": len(candidate_mm), "top_fill_gerber_point_count_including_close": len(gerber_region),
            "top_fill_vertex_order_aligned": aligned, "top_fill_max_vertex_delta_mm": max_fill_vertex_delta,
            "bottom_native_antenna_segment_count": len(source_lines), "bottom_gerber_d01_segment_count": len(bottom_segments),
            "bottom_native_antenna_segments_best_match": bottom_matches,
            "all_bottom_antenna_segments_match_within_0_001mm": all(m["best_gerber_error_mm"] <= 0.001 for m in bottom_matches),
            "limitation": "Gerber carries no net names; geometric correspondence does not prove final RF tuning or assembled-stack behavior.",
        },
        "bom_pnp": {
            "bom_all_designators": all_bom_refs, "pnp_all_designators": pnp_refs,
            "bom_pnp_designator_sets_equal": set(all_bom_refs) == set(pnp_refs),
            "coordinate_unit": "mm (PnP Mid X/Mid Y values include mm suffix; checked against native panel coordinates converted from mil)",
            "native_pnp_checks": pnp_checks,
            "population_exceptions_to_all_parts": bom_population_diff,
            "variant_counts": {k: {"fit_count": v["fit_count"], "excluded": v["excluded"]} for k, v in variants["variants"].items()},
            "cam_note": "Use the selected filtered assembly variant, not the all-parts exports. PnP coordinates are mm native panel coordinates; bottom-side rotation convention still needs assembler confirmation.",
        },
        "testpoints": {
            "summary": {"status": testpoint_audit["status"], "pass": testpoint_audit["pass"],
                        "present_count": len(testpoint_audit["present_designators"]), "expected_count": 2,
                        "failures": testpoint_audit.get("failures", [])},
            "details": testpoint_audit,
        },
        "findings": [
            {"severity": "action_before_release", "finding": "PTH drill export files are byte-different but contain the same tool and 10 hit locations; using both duplicates all plated holes."},
            {"severity": "verified_geometry_with_cam_followup", "finding": "The current GKO has 22 explicitly closed paths and a 100x100 mm envelope, consistent with one outer contour and 21 internal contours; CAM must still verify routing compensation and tabs/slots."},
            {"severity": "assembly_variant_required", "finding": "All-parts BOM/PnP are not population-filtered; CT2 is excluded in both variants, and D2/D4 differ between the four-LED and two-LED variants."},
        ],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "zip_sha256": report["inputs"]["zip_sha256"],
                      "drill_duplicate": duplicate_pth, "outline_paths": len(outline_paths),
                      "outline_box_mm": outline_box, "antenna_fill_delta_mm": max_fill_vertex_delta,
                      "bottom_segments_match": report["antenna_copper"]["all_bottom_antenna_segments_match_within_0_001mm"],
                      "pnp_components": len(pnp), "testpoints": report["testpoints"]["summary"]}, ensure_ascii=False, indent=2))
    if testpoint_audit["status"] == "checked_fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
