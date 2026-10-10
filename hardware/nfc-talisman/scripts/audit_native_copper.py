"""Offline audit of saved native core and translated panel copper snapshots.

This script reads only JSON/JSONL snapshots and review candidates. It does not
connect to or modify EasyEDA. Distances are computed in millimeters with
Shapely; the native source coordinates are in mil.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box

ROOT = Path(__file__).resolve().parents[1]
MM_PER_MIL = 0.0254
PANEL_OFFSET_MM = 50.0
PANEL_OFFSET_MIL = PANEL_OFFSET_MM / MM_PER_MIL
MIN_COPPER_CLEARANCE_MM = 6 * MM_PER_MIL
MIN_DRILL_TO_COPPER_MM = 6.929 * MM_PER_MIL
EPS = 1e-8


def load_records(path: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    result = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            meta_text, data_text = raw.split("||", 1)
            result.append((json.loads(meta_text), json.loads(data_text.rstrip("|"))))
        except Exception as exc:  # Keep source line handy when a saved file is malformed.
            raise ValueError(f"Cannot parse {path}:{number}: {exc}") from exc
    return result


def path_xy(raw: list[Any]) -> list[tuple[float, float]]:
    values = [v for v in raw if isinstance(v, (int, float))]
    if len(values) < 6 or len(values) % 2:
        raise ValueError("Expected at least three XY pairs in native path")
    return [(values[i] * MM_PER_MIL, values[i + 1] * MM_PER_MIL) for i in range(0, len(values), 2)]


def netset(data: dict[str, Any]) -> frozenset[str]:
    # Bridge copper deliberately belongs to both ANT nets for geometric and
    # per-net connectivity checks. Ordinary primitives have one netName.
    nets = data.get("networkList") or []
    if data.get("isBridgingCopper"):
        return frozenset(nets)
    name = data.get("netName")
    return frozenset([name]) if name else frozenset()


def pad_has_hole(data: dict[str, Any]) -> bool:
    hole = data.get("hole")
    return bool(hole and max(float(hole.get("width", 0) or 0), float(hole.get("height", 0) or 0)) > 0)


def native_pad_shape(data: dict[str, Any]):
    shape = data.get("defaultPad") or {}
    kind = str(shape.get("padType", "")).upper()
    w = float(shape.get("width", 0) or 0) * MM_PER_MIL
    h = float(shape.get("height", 0) or 0) * MM_PER_MIL
    x, y = float(data["centerX"]) * MM_PER_MIL, float(data["centerY"]) * MM_PER_MIL
    if w <= 0 or h <= 0:
        raise ValueError(f"Free PAD has no copper dimensions: {data}")
    if kind in ("ELLIPSE", "OVAL", "CIRCLE"):
        from shapely.affinity import scale
        geom = scale(Point(x, y).buffer(1, resolution=32), w/2, h/2, origin=(x, y))
    elif kind in ("RECT", "ROUNDRECT"):
        geom = box(x-w/2, y-h/2, x+w/2, y+h/2)
    else:
        raise ValueError(f"Unsupported free PAD copper shape {kind!r}")
    return rotate(geom, float(data.get("padAngle", 0) or 0), origin=(x, y))


def source_copper(records: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    lines, vias, fills, outlines, free_pads, ignored_hole_pads = [], [], [], [], [], []
    for meta, data in records:
        kind = meta.get("type")
        item_id = meta.get("id", "")
        if kind == "LINE":
            a = (data["startX"] * MM_PER_MIL, data["startY"] * MM_PER_MIL)
            b = (data["endX"] * MM_PER_MIL, data["endY"] * MM_PER_MIL)
            centerline = LineString([a, b])
            lines.append({"id": item_id, "nets": netset(data), "net": data.get("netName", ""),
                          "layer": data["layerId"], "width_mm": data["width"] * MM_PER_MIL,
                          "centerline": centerline, "geom": centerline.buffer(data["width"] * MM_PER_MIL / 2),
                          "kind": "line"})
        elif kind == "VIA":
            center = Point(data["centerX"] * MM_PER_MIL, data["centerY"] * MM_PER_MIL)
            radius = data["viaDiameter"] * MM_PER_MIL / 2
            ring = center.buffer(radius, resolution=24)
            vias.append({"id": item_id, "nets": netset(data), "net": data.get("netName", ""),
                         "center": center, "geom": ring, "radius_mm": radius,
                         "hole_radius_mm": data["holeDiameter"] * MM_PER_MIL / 2,
                         "hole_mm": data["holeDiameter"] * MM_PER_MIL,
                         "diameter_mm": data["viaDiameter"] * MM_PER_MIL,
                         "layers": (1, 2), "kind": "via"})
        elif kind == "FILL":
            coords = path_xy(data["path"][0])
            shape = Polygon(coords)
            fills.append({"id": item_id, "nets": netset(data), "net": data.get("netName", ""),
                          "layer": data["layerId"], "geom": shape, "kind": "fill",
                          "bridge": bool(data.get("isBridgingCopper")),
                          "networkList": data.get("networkList") or [], "coords": coords,
                          "data": data})
        elif kind == "PAD" and data.get("layerId") in (1, 2):
            # Copper-layer free PADs are included in the geometry audit. A PAD
            # with a positive-diameter hole is not classified as an SMD test
            # point; unplated hole pads are excluded as non-copper, while a
            # plated hole pad contributes its annulus but retains its drill.
            if pad_has_hole(data):
                hole = data["hole"]
                if not data.get("plated", False):
                    ignored_hole_pads.append(item_id)
                    continue
                geom = native_pad_shape(data)
                hx = float(data["centerX"]) * MM_PER_MIL
                hy = float(data["centerY"]) * MM_PER_MIL
                hw = float(hole.get("width", 0) or 0) * MM_PER_MIL
                hh = float(hole.get("height", 0) or 0) * MM_PER_MIL
                from shapely.affinity import scale
                inner = scale(Point(hx, hy).buffer(1, resolution=32), hw/2, hh/2, origin=(hx, hy))
                geom = geom.difference(inner)
            else:
                geom = native_pad_shape(data)
            free_pads.append({"id": item_id, "nets": netset(data), "net": data.get("netName", ""),
                              "layer": data["layerId"], "geom": geom, "kind": "free_pad",
                              "has_hole": pad_has_hole(data), "plated": bool(data.get("plated", False)),
                              "data": data})
        elif kind == "POLY" and data.get("layerId") == 11:
            shape = Polygon(path_xy(data["path"]))
            if shape.is_valid and shape.area > 0:
                outlines.append({"id": item_id, "geom": shape, "coords": path_xy(data["path"])})
    if len(outlines) != 1:
        raise ValueError(f"Expected exactly one closed layer-11 board outline; found {len(outlines)}")
    return {"lines": lines, "vias": vias, "fills": fills, "free_pads": free_pads,
            "ignored_hole_pads": ignored_hole_pads, "outline": outlines[0]}


def native_pads(path: Path) -> list[dict[str, Any]]:
    out = []
    for component in json.loads(path.read_text(encoding="utf-8")):
        for pad in component["pins"]:
            shape = pad["pad"][0]
            x, y = pad["x"] * MM_PER_MIL, pad["y"] * MM_PER_MIL
            if shape == "RECT":
                w, h = pad["pad"][1] * MM_PER_MIL, pad["pad"][2] * MM_PER_MIL
                geom = rotate(box(x-w/2, y-h/2, x+w/2, y+h/2), pad.get("rotation", 0), origin=(x, y))
            elif shape in ("ELLIPSE", "OVAL"):
                w, h = pad["pad"][1] * MM_PER_MIL, pad["pad"][2] * MM_PER_MIL
                geom = scale_ellipse(x, y, w, h)
                geom = rotate(geom, pad.get("rotation", 0), origin=(x, y))
            else:
                raise ValueError(f"Unsupported pad shape {shape}: {component['ref']}.{pad['padNumber']}")
            out.append({"id": f"{component['ref']}.{pad['padNumber']}", "net": pad["net"],
                        "nets": frozenset([pad["net"]]), "layer": pad["layer"],
                        "geom": geom, "kind": "pad", "x_mil": pad["x"], "y_mil": pad["y"]})
    return out


def scale_ellipse(x: float, y: float, w: float, h: float):
    return ellipse_polygon(x, y, w, h)


def ellipse_polygon(x: float, y: float, w: float, h: float):
    from shapely.affinity import scale
    return scale(Point(x, y).buffer(1, resolution=32), w/2, h/2, origin=(x, y))


def copper_items(copper: dict[str, Any], pads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = list(pads) + list(copper["free_pads"]) + list(copper["lines"]) + list(copper["fills"])
    for via in copper["vias"]:
        for layer in via["layers"]:
            items.append({**via, "layer": layer, "kind": "via_ring", "id": f"{via['id']}@L{layer}"})
    return items


def board_edge_checks(items: list[dict[str, Any]], outline: Polygon) -> list[dict[str, Any]]:
    bad = []
    for item in items:
        if not outline.covers(item["geom"]):
            outside_area = item["geom"].difference(outline).area
            outside_dist = item["geom"].distance(outline)
            bad.append({"item": item["id"], "kind": item["kind"], "nets": sorted(item["nets"]),
                        "outside_area_mm2": round(outside_area, 9), "distance_to_outline_mm": round(outside_dist, 9)})
    return bad


def clearance_audit(items: list[dict[str, Any]], vias: list[dict[str, Any]]):
    min_pair = {"gap_mm": math.inf}
    violations = []
    # Coplanar copper shapes include pads, line copper, via annuli and fills.
    for i, a in enumerate(items):
        for b in items[i+1:]:
            if a.get("layer") != b.get("layer") or not a["nets"].isdisjoint(b["nets"]):
                continue
            gap = a["geom"].distance(b["geom"])
            row = {"a": a["id"], "a_kind": a["kind"], "a_nets": sorted(a["nets"]),
                   "b": b["id"], "b_kind": b["kind"], "b_nets": sorted(b["nets"]),
                   "layer": a.get("layer"), "gap_mm": gap}
            if gap < min_pair["gap_mm"]:
                min_pair = row
            if gap < MIN_COPPER_CLEARANCE_MM - EPS:
                violations.append({**row, "gap_mm": round(gap, 9),
                                   "required_mm": MIN_COPPER_CLEARANCE_MM})
    min_drill = {"gap_mm": math.inf}
    drill_violations = []
    for via in vias:
        for item in items:
            if not via["nets"].isdisjoint(item["nets"]):
                continue
            # The via's own annuli are same-net and excluded above. Other-net
            # copper on either copper layer is compared to the physical drill.
            gap = via["center"].distance(item["geom"]) - via["hole_radius_mm"]
            row = {"via": via["id"], "via_net": via["net"], "other_copper": item["id"],
                   "other_nets": sorted(item["nets"]), "layer": item.get("layer"), "gap_mm": gap}
            if gap < min_drill["gap_mm"]:
                min_drill = row
            if gap < MIN_DRILL_TO_COPPER_MM - EPS:
                drill_violations.append({**row, "gap_mm": round(gap, 9),
                                         "required_mm": MIN_DRILL_TO_COPPER_MM})
    if math.isinf(min_pair["gap_mm"]): min_pair = None
    if math.isinf(min_drill["gap_mm"]): min_drill = None
    return min_pair, violations, min_drill, drill_violations


def build_connectivity(copper: dict[str, Any], pads: list[dict[str, Any]], all_nets: list[str]):
    results, via_checks = {}, []
    for net in all_nets:
        nodes = []
        for pad in list(pads) + list(copper["free_pads"]):
            if pad["net"] == net:
                label=pad.get('data',{}).get('padNumber') or pad.get('data',{}).get('num') or pad['id']
                nodes.append({**pad, "layer": pad["layer"], "label": label})
        for line in copper["lines"]:
            if net in line["nets"]:
                nodes.append({**line, "label": line["id"]})
        for fill in copper["fills"]:
            if net in fill["nets"]:
                nodes.append({**fill, "label": fill["id"]})
        for via in copper["vias"]:
            if net in via["nets"]:
                for layer in via["layers"]:
                    nodes.append({**via, "layer": layer, "kind": "via_ring", "label": f"{via['id']}@L{layer}"})
        parent = list(range(len(nodes)))
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb: parent[rb] = ra
        by_layer: dict[int, list[int]] = defaultdict(list)
        for i, node in enumerate(nodes):
            by_layer[node["layer"]].append(i)
        # Touching/overlapping copper on a single layer joins. Via top and
        # bottom annuli are then explicitly united through the plated barrel.
        for layer, ids in by_layer.items():
            for ii, i in enumerate(ids):
                for j in ids[ii+1:]:
                    if nodes[i]["geom"].distance(nodes[j]["geom"]) <= EPS:
                        union(i, j)
        via_layers: dict[str, list[int]] = defaultdict(list)
        for i, node in enumerate(nodes):
            if node["kind"] == "via_ring": via_layers[node["id"]].append(i)
        for via_id, ids in via_layers.items():
            if len(ids) == 2: union(ids[0], ids[1])
        pad_nodes = [(i, n) for i, n in enumerate(nodes) if n["kind"] in ("pad", "free_pad")]
        roots = defaultdict(list)
        for i, n in pad_nodes: roots[find(i)].append(n["label"])
        groups = [sorted(x) for x in roots.values()]
        results[net] = {"pad_count": len(pad_nodes), "copper_node_count": len(nodes),
                        "pad_components": groups,
                        "all_pads_connected": len(groups) <= 1,
                        "unconnected_pads": sorted(x for group in groups[1:] for x in group)}
    # Explicit per-via inspection: ring must have same-net copper contact on
    # both Top and Bottom. Connectivity graph also models the barrel as a link.
    for via in copper["vias"]:
        contacts = {}
        for layer in via["layers"]:
            matches = []
            for item in list(pads) + list(copper["free_pads"]) + copper["lines"] + copper["fills"]:
                if item.get("layer") == layer and via["net"] in item["nets"] and via["geom"].distance(item["geom"]) <= EPS:
                    matches.append(item["id"])
            contacts[str(layer)] = sorted(set(matches))
        via_checks.append({"via": via["id"], "net": via["net"], "top_contacts": contacts.get("1", []),
                           "bottom_contacts": contacts.get("2", []),
                           "has_both_layer_contacts": bool(contacts.get("1")) and bool(contacts.get("2"))})
    return results, via_checks


def line_signature(item: dict[str, Any], offset_mil: float = 0.0):
    pts = [(item["startX"]-offset_mil, item["startY"]-offset_mil),
           (item["endX"]-offset_mil, item["endY"]-offset_mil)]
    pts = sorted(tuple(round(v, 4) for v in p) for p in pts)
    return (item.get("netName", ""), item["layerId"], round(item["width"], 4), *pts[0], *pts[1])


def via_signature(item: dict[str, Any], offset_mil: float = 0.0):
    return (item.get("netName", ""), round(item["centerX"]-offset_mil, 4),
            round(item["centerY"]-offset_mil, 4), round(item["holeDiameter"], 4), round(item["viaDiameter"], 4))


def fill_signature(item: dict[str, Any], offset_mil: float = 0.0):
    coords = path_xy(item["path"][0])
    coords = [(round(x/MM_PER_MIL-offset_mil, 4), round(y/MM_PER_MIL-offset_mil, 4)) for x, y in coords]
    return (item.get("netName", ""), item.get("layerId"), round(item.get("width", 0), 4),
            bool(item.get("isBridgingCopper")), tuple(item.get("networkList") or []), tuple(coords))


def panel_match(core_records, panel_records):
    def has_copper_free_pad(data):
        return data.get("layerId") in (1, 2) and (not pad_has_hole(data) or data.get("plated", False))

    def selected(records):
        return {"LINE": [d for m, d in records if m.get("type") == "LINE"],
                "VIA": [d for m, d in records if m.get("type") == "VIA"],
                "FILL": [d for m, d in records if m.get("type") == "FILL"],
                "PAD": [d for m, d in records if m.get("type") == "PAD" and has_copper_free_pad(d)]}
    c, p = selected(core_records), selected(panel_records)
    mismatches = {}
    def pad_signature(item, offset_mil=0.0):
        default = item.get("defaultPad") or {}
        hole = item.get("hole") or {}
        return (item.get("netName", ""), item.get("layerId"),
                round(float(item["centerX"])-offset_mil, 4), round(float(item["centerY"])-offset_mil, 4),
                round(float(item.get("padAngle", 0) or 0), 4), default.get("padType"),
                round(float(default.get("width", 0) or 0), 4), round(float(default.get("height", 0) or 0), 4),
                bool(item.get("plated", False)), round(float(hole.get("width", 0) or 0), 4),
                round(float(hole.get("height", 0) or 0), 4))

    for typ, signature in (("LINE", line_signature), ("VIA", via_signature), ("FILL", fill_signature), ("PAD", pad_signature)):
        core_counter = Counter(signature(x, 0) for x in c[typ])
        panel_counter = Counter(signature(x, PANEL_OFFSET_MIL) for x in p[typ])
        if core_counter != panel_counter:
            missing = list((core_counter-panel_counter).elements())[:12]
            extra = list((panel_counter-core_counter).elements())[:12]
            mismatches[typ] = {"core_count": len(c[typ]), "panel_count": len(p[typ]),
                               "missing_in_panel_after_translation": missing,
                               "extra_in_panel_after_translation": extra}
    return {"passed": not mismatches, "offset_mm": [PANEL_OFFSET_MM, PANEL_OFFSET_MM],
            "core_counts": {k: len(v) for k, v in c.items()},
            "panel_counts": {k: len(v) for k, v in p.items()}, "mismatches": mismatches,
            "fill_bridge_networks": [d.get("networkList", []) for d in p["FILL"]]}


def coil_audit(copper: dict[str, Any], candidate_path: Path, geometry_review_path: Path):
    fills = copper["fills"]
    data = json.loads(candidate_path.read_text(encoding="utf-8"))
    expected = Polygon([(x*MM_PER_MIL, y*MM_PER_MIL) for x, y in data["points_native_mil"]])
    actual = fills[0]["geom"] if fills else Polygon()
    candidate_bridge = set(data.get("bridge_nets", []))
    actual_bridge = set(fills[0].get("networkList", [])) if fills else set()
    review = json.loads(geometry_review_path.read_text(encoding="utf-8"))
    proposal = review["proposal_geometry"]
    spiral_tracks = [t for t in proposal["trackGeometry"] if "spiral" in t["role"]]
    terminal_vias = [v for v in proposal["vias"] if v["name"] in ("coil_outer_terminal", "coil_inner_terminal")]
    via_turn_gaps = []
    for proposed_via in terminal_vias:
        x = proposed_via["x_mil"] * MM_PER_MIL
        y = proposed_via["y_mil"] * MM_PER_MIL
        point = Point(x, y)
        segment_rows = []
        for index, track in enumerate(spiral_tracks):
            centerline = LineString([(track["a"]["x"]*MM_PER_MIL, track["a"]["y"]*MM_PER_MIL),
                                     (track["b"]["x"]*MM_PER_MIL, track["b"]["y"]*MM_PER_MIL)])
            segment_rows.append((point.distance(centerline), index, track, centerline))
        # The closest segment is the intentional terminal-to-winding overlap;
        # all remaining segments are tested as neighboring/further turns.
        terminal_segment = min(segment_rows, key=lambda row: row[0])
        via = next((v for v in copper["vias"] if v["net"] == proposed_via["semanticNet"] and
                    v["center"].distance(point) <= 0.002), None)
        if via is None:
            via_turn_gaps.append({"via": proposed_via["name"], "found_native_via": False,
                                  "closest_spiral_segment_index": terminal_segment[1]})
            continue
        remaining = []
        for distance, index, track, centerline in segment_rows:
            if index == terminal_segment[1]:
                continue
            gap = distance - via["radius_mm"] - track["width"]*MM_PER_MIL/2
            remaining.append((gap, distance, index))
        closest = min(remaining)
        via_turn_gaps.append({"via": via["id"], "name": proposed_via["name"], "net": via["net"],
                              "native_diameter_mm": round(via["diameter_mm"], 8),
                              "intentional_terminal_segment_index": terminal_segment[1],
                              "closest_other_turn_segment_index": closest[2],
                              "center_distance_mm": round(closest[1], 8),
                              "via_ring_to_other_turn_copper_gap_mm": round(closest[0], 8),
                              "required_gap_mm": MIN_COPPER_CLEARANCE_MM,
                              "passes_6mil_other_turn_gap": closest[0] >= MIN_COPPER_CLEARANCE_MM - EPS})
    actual_vertices = len(fills[0]["coords"]) if fills else 0
    if fills and actual_vertices > 1 and fills[0]["coords"][0] == fills[0]["coords"][-1]:
        actual_vertices -= 1  # Native path repeats the first vertex to close the polygon.
    symdiff = actual.symmetric_difference(expected).area if actual.is_valid and expected.is_valid else None
    return {"fill_count": len(fills), "actual_type": actual.geom_type,
            "actual_valid_simple_polygon": actual.geom_type == "Polygon" and actual.is_valid and not actual.is_empty,
            "actual_is_single_connected_component": actual.geom_type == "Polygon" and actual.is_valid,
            "actual_vertex_count_excluding_closure": actual_vertices,
            "candidate_vertex_count": len(data.get("points_native_mil", [])),
            "candidate_turn_count": data.get("turns"),
            "actual_area_mm2": round(actual.area, 8), "candidate_area_mm2": round(expected.area, 8),
            "symmetric_difference_area_mm2": round(symdiff, 8) if symdiff is not None else None,
            "bridge_enabled": bool(fills[0].get("bridge")) if fills else False,
            "actual_bridge_nets": sorted(actual_bridge), "candidate_bridge_nets": sorted(candidate_bridge),
            "bridge_matches_candidate": actual_bridge == candidate_bridge,
            "simple_polygon_no_self_intersection": actual.geom_type == "Polygon" and actual.is_valid,
            "candidate_spiral_centerline_segment_count": len(spiral_tracks),
            "terminal_via_to_other_turn_clearance": via_turn_gaps,
            "all_terminal_vias_clear_of_other_turns": len(via_turn_gaps) == 2 and all(x.get("passes_6mil_other_turn_gap", False) for x in via_turn_gaps),
            "matches_4turn_candidate_within_native_quantization": actual_vertices == len(data.get("points_native_mil", [])) and data.get("turns") == 4 and symdiff is not None and symdiff < 0.001}


def main() -> None:
    core_file = ROOT / "eda/native/core-source.jsonl"
    panel_file = ROOT / "eda/native/panel-source.jsonl"
    pads_file = ROOT / "eda/core-pads.json"
    candidate_file = ROOT / "electrical/antenna-coil-fill-candidate.json"
    geometry_review_file = ROOT / "electrical/antenna-geometry-review.json"
    core_records, panel_records = load_records(core_file), load_records(panel_file)
    copper = source_copper(core_records)
    pads = native_pads(pads_file)
    items = copper_items(copper, pads)
    edge_violations = board_edge_checks(items, copper["outline"]["geom"])
    min_copper, copper_violations, min_drill, drill_violations = clearance_audit(items, copper["vias"])
    nets = sorted({p["net"] for p in list(pads) + list(copper["free_pads"])})
    connectivity, via_contacts = build_connectivity(copper, pads, nets)
    panel = panel_match(core_records, panel_records)
    coil = coil_audit(copper, candidate_file, geometry_review_file)
    fill_bridges = [f for f in copper["fills"] if f["bridge"]]
    all_bridge_nets = [sorted(f["nets"]) for f in fill_bridges]
    bridge_only_antenna = bool(fill_bridges) and all(set(n) == {"ANT_LA", "ANT_LB"} for n in all_bridge_nets) and len(fill_bridges) == len(copper["fills"])
    report = {
        "status": "draft_native_snapshot_audit",
        "read_only": True,
        "sources": {"core": "eda/native/core-source.jsonl", "panel": "eda/native/panel-source.jsonl",
                    "pads": "eda/core-pads.json", "coil_candidate": "electrical/antenna-coil-fill-candidate.json",
                    "coil_centerline_review": "electrical/antenna-geometry-review.json:proposal_geometry"},
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (core_file, panel_file, pads_file, candidate_file, geometry_review_file)},
        "units": {"native": "mil", "audit": "mm", "panel_offset": [PANEL_OFFSET_MM, PANEL_OFFSET_MM]},
        "native_counts": {"core_lines": len(copper["lines"]), "core_vias": len(copper["vias"]),
                           "core_fills": len(copper["fills"]), "core_component_pads": len(pads),
                           "core_free_pad_copper": len(copper["free_pads"]),
                           "core_ignored_unplated_hole_pads": len(copper["ignored_hole_pads"]), "nets_with_pads": len(nets),
                           "panel_lines": sum(m.get("type") == "LINE" for m, _ in panel_records),
                           "panel_vias": sum(m.get("type") == "VIA" for m, _ in panel_records),
                           "panel_fills": sum(m.get("type") == "FILL" for m, _ in panel_records),
                           "panel_copper_layer_free_pads": sum(m.get("type") == "PAD" and d.get("layerId") in (1, 2) and (not pad_has_hole(d) or d.get("plated", False)) for m, d in panel_records)},
        "check_1_core_boundary_and_clearance": {
            "outline_polygon_valid": copper["outline"]["geom"].is_valid,
            "outline_bounds_mm": [round(v, 8) for v in copper["outline"]["geom"].bounds],
            "all_copper_inside_outline": not edge_violations,
            "outside_items": edge_violations,
            "required_same_layer_alien_net_clearance_mm": MIN_COPPER_CLEARANCE_MM,
            "minimum_same_layer_copper_gap": ({**min_copper, "gap_mm": round(min_copper["gap_mm"], 9)} if min_copper else None),
            "same_layer_clearance_violations": copper_violations,
            "required_drill_edge_to_alien_copper_mm": MIN_DRILL_TO_COPPER_MM,
            "minimum_drill_to_alien_copper": ({**min_drill, "gap_mm": round(min_drill["gap_mm"], 9)} if min_drill else None),
            "drill_clearance_violations": drill_violations,
        },
        "check_2_coil": coil,
        "check_3_panel_translation_and_fill_bridge": {
            "panel_copper_matches_core_after_50mm_xy_translation": panel,
            "all_fill_bridge_nets": all_bridge_nets,
            "fill_bridge_only_ANT_LA_ANT_LB": bridge_only_antenna,
        },
        "check_4_pad_connectivity_by_net": {"nets": connectivity, "via_layer_contacts": via_contacts},
        "summary": {
            "core_outline_clearance_pass": not edge_violations and not copper_violations and not drill_violations,
            "coil_pass": coil["actual_valid_simple_polygon"] and coil["actual_is_single_connected_component"] and coil["simple_polygon_no_self_intersection"] and coil["matches_4turn_candidate_within_native_quantization"] and coil["all_terminal_vias_clear_of_other_turns"],
            "panel_translation_pass": panel["passed"],
            "fill_bridge_pass": bridge_only_antenna,
            "pad_connectivity_pass": all(x["all_pads_connected"] for x in connectivity.values()),
            "all_vias_touch_same_net_top_and_bottom": all(x["has_both_layer_contacts"] for x in via_contacts),
        },
        "limitations": ["Geometric snapshot audit only; native DRC result is reported separately.",
                        "Copper clearances are evaluated between saved copper shapes on the same layer; drill clearances compare each via drill with alien-net copper on either layer.",
                        "The board outline check uses the saved layer-11 polygon as the copper boundary.",
                        "Connectivity uses pad rectangles, buffered line centerlines, via annuli/barrels, and the saved fill polygon; it does not infer electrical behavior beyond these saved geometries."],
    }
    out = ROOT / "electrical/native-copper-audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out), "counts": report["native_counts"], "summary": report["summary"],
                      "min_copper_gap": report["check_1_core_boundary_and_clearance"]["minimum_same_layer_copper_gap"],
                      "min_drill_gap": report["check_1_core_boundary_and_clearance"]["minimum_drill_to_alien_copper"],
                      "panel_mismatches": panel["mismatches"],
                      "disconnected": {n: d["pad_components"] for n, d in connectivity.items() if not d["all_pads_connected"]}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
