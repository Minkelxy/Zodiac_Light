"""Build an offline draft route candidate for VOUT, GND, and CT1/CT2.

This script reads only saved geometry snapshots. Its JSON output is a review
artifact for manual import; it does not call or modify EasyEDA.
"""
from __future__ import annotations

import heapq
import json
import math
from pathlib import Path

from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
MM_PER_MIL = 0.0254
CLEARANCE = 0.1524
ROUTE_CLEARANCE = 0.20
TRACE_WIDTH = 8 * MM_PER_MIL
VIA_DRILL = 0.20
VIA_DIAMETER = 0.45
STEP = 0.127  # 5 mil occupancy grid; emitted routes are polygon-checked.
TARGETS = {
    "VOUT": ["U1.6", "U1.7", "C1.1", "R1.1", "R2.1", "R3.1", "R4.1", "R5.1", "R6.1", "R7.1"],
    "GND": ["U1.2", "C1.2", "D1.1", "D2.1", "D3.1", "D4.1"],
    "ANT_LA": ["U1.1", "CT1.1", "CT2.1"],
    "ANT_LB": ["U1.8", "CT1.2", "CT2.2"],
}


def read_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def milpoint(x, y):
    return (x * MM_PER_MIL, y * MM_PER_MIL)


def pad_snapshot():
    result = {}
    all_pads = []
    for comp in read_json("eda/core-pads.json"):
        for raw in comp["pins"]:
            if raw["pad"][0] != "RECT":
                raise ValueError(f"Unsupported pad shape {comp['ref']}.{raw['padNumber']}")
            x, y = milpoint(raw["x"], raw["y"])
            w, h = raw["pad"][1] * MM_PER_MIL, raw["pad"][2] * MM_PER_MIL
            geom = rotate(box(x - w / 2, y - h / 2, x + w / 2, y + h / 2), raw["rotation"], origin=(x, y))
            item = {"id": f"{comp['ref']}.{raw['padNumber']}", "net": raw["net"], "layer": raw["layer"], "center": (x, y), "geom": geom}
            result[item["id"]] = item
            all_pads.append(item)
    return result, all_pads


def snapshot_tracks():
    live = read_json("eda/native/core-initial-tracks.json")
    if not live.get("success") or len(live["result"]["lines"]) != 19:
        raise ValueError("Expected the reviewed successful 19-track snapshot")
    tracks = []
    for t in live["result"]["lines"]:
        tracks.append({"id": t["id"], "net": t["net"], "layer": t["layer"], "width": t["width"] * MM_PER_MIL,
                       "geom": LineString([milpoint(*t["start"]), milpoint(*t["end"])]), "source": "existing"})
    return tracks


def antenna_geometry():
    plan = read_json("electrical/antenna-geometry-review.json")["proposal_geometry"]
    tracks = []
    for i, t in enumerate(plan["trackGeometry"]):
        a, b = milpoint(t["a"]["x"], t["a"]["y"]), milpoint(t["b"]["x"], t["b"]["y"])
        tracks.append({"id": f"antenna-{i}", "net": t["semanticNet"], "layer": t["layer"], "width": t["width"] * MM_PER_MIL,
                       "geom": LineString([a, b]), "source": "antenna_candidate", "role": t["role"]})
    vias = []
    for v in plan["vias"]:
        vias.append({"id": v["name"], "net": v["semanticNet"], "point": Point(*milpoint(v["x_mil"], v["y_mil"])), "radius": v["diameter_mm"] / 2, "source": "antenna_candidate"})
    fill_raw = read_json("electrical/antenna-coil-fill-candidate.json")
    fill = Polygon([milpoint(x, y) for x, y in fill_raw["points_native_mil"]])
    if not fill.is_valid:
        raise ValueError("Antenna coil-fill candidate polygon is invalid")
    outline_pts = [milpoint(s["a"]["x"], s["a"]["y"]) for s in plan["outlineSegments"]]
    return tracks, vias, Polygon(outline_pts), plan, fill


def grid_index(point):
    return (round(point[0] / STEP), round(point[1] / STEP))


def grid_point(node):
    return (node[0] * STEP, node[1] * STEP)


def quantize_mm(value):
    """Quantize a coordinate to the native 0.1 mil grid before any audit."""
    return round(value / MM_PER_MIL * 10) / 10 * MM_PER_MIL


def quantize_linework(tracks, vias):
    for t in tracks:
        t["geom"] = LineString([(quantize_mm(x), quantize_mm(y)) for x, y in t["geom"].coords])
    for v in vias:
        v["point"] = Point(quantize_mm(v["point"].x), quantize_mm(v["point"].y))


def merge_collinear_tracks(tracks):
    """Dissolve duplicates and merge degree-two collinear endpoint pairs."""
    merged = []
    for net in sorted({t["net"] for t in tracks}):
        for layer in (1, 2):
            group = [t for t in tracks if t["net"] == net and t["layer"] == layer]
            if not group:
                continue
            # Coordinates are already on the 0.1 mil grid; this canonical key
            # also collapses duplicate same-net segments from retraced paths.
            edges = {}
            for t in group:
                a, b = tuple(t["geom"].coords[0]), tuple(t["geom"].coords[-1])
                key = tuple(sorted((a, b)))
                edges[key] = None
            changed = True
            while changed:
                changed = False
                incident = {}
                for edge in edges:
                    incident.setdefault(edge[0], []).append(edge)
                    incident.setdefault(edge[1], []).append(edge)
                for vertex, touching in incident.items():
                    for i, e1 in enumerate(touching):
                        other1 = e1[1] if e1[0] == vertex else e1[0]
                        v1 = (other1[0] - vertex[0], other1[1] - vertex[1])
                        for e2 in touching[i + 1:]:
                            other2 = e2[1] if e2[0] == vertex else e2[0]
                            v2 = (other2[0] - vertex[0], other2[1] - vertex[1])
                            cross = v1[0] * v2[1] - v1[1] * v2[0]
                            dot = v1[0] * v2[0] + v1[1] * v2[1]
                            if abs(cross) <= 1e-10 and dot < 0:
                                edges.pop(e1); edges.pop(e2)
                                edges[tuple(sorted((other1, other2)))] = None
                                changed = True
                                break
                        if changed:
                            break
                    if changed:
                        break
            for edge in edges:
                merged.append({"id": f"{net}_L{layer}_{len(merged)+1}", "net": net, "layer": layer,
                               "width": TRACE_WIDTH, "geom": LineString(edge), "source": "candidate_merged"})
    return merged


def route_one_target(net, target, connected, pads, obstacles, via_obstacles, board):
    start_pad = pads[target]
    start_xy = start_pad["center"]
    start_node = (*grid_index(start_xy), start_pad["layer"])
    start_grid = grid_point(start_node[:2])
    start_connect = LineString([start_xy, start_grid])
    if not board.buffer(-TRACE_WIDTH / 2).covers(start_connect):
        raise RuntimeError(f"Pad snap leaves board for {target}")

    # A* from the unconnected target toward any node already on this net.
    start = start_node
    heap = [(0.0, 0.0, start)]
    came = {}
    best = {start: 0.0}
    goal = None
    seed_xy = start_xy
    while heap:
        _, cost, node = heapq.heappop(heap)
        if cost != best.get(node):
            continue
        if node in connected:
            goal = node
            break
        i, j, layer = node
        x, y = grid_point((i, j))
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nxt = (i + di, j + dj, layer)
            p = grid_point(nxt[:2])
            if not board.buffer(-TRACE_WIDTH / 2).covers(Point(*p)):
                continue
            if obstacles[layer].covers(Point(*p)):
                continue
            if di and dj:
                if obstacles[layer].covers(Point(x + di * STEP, y)) or obstacles[layer].covers(Point(x, y + dj * STEP)):
                    continue
            move = STEP * (math.sqrt(2) if di and dj else 1)
            nc = cost + move
            if nc < best.get(nxt, 1e99):
                best[nxt] = nc
                came[nxt] = node
                heuristic = Point(*p).distance(Point(*seed_xy))
                heapq.heappush(heap, (nc + heuristic, nc, nxt))
        # Layer changes are plated vias. Their 0.45 mm copper must clear all
        # unrelated pads, tracks, and vias on both copper layers.
        other = 2 if layer == 1 else 1
        if not via_obstacles.covers(Point(x, y)) and board.buffer(-VIA_DIAMETER / 2).covers(Point(x, y)):
            nxt = (i, j, other)
            nc = cost + 6.0
            if nc < best.get(nxt, 1e99):
                best[nxt] = nc
                came[nxt] = node
                heuristic = Point(x, y).distance(Point(*seed_xy))
                heapq.heappush(heap, (nc + heuristic, nc, nxt))
    if goal is None:
        raise RuntimeError(f"No route found for {target} ({net})")
    path = [goal]
    while path[-1] != start:
        path.append(came[path[-1]])
    path.reverse()

    # Keep exact pad center as a short copper stub and compress straight grid runs.
    points = [start_xy]
    layers = [start_pad["layer"]]
    points.append(start_grid)
    layers.append(start_pad["layer"])
    for k, node in enumerate(path[1:], 1):
        p = grid_point(node[:2])
        if node[2] != path[k - 1][2]:
            points.append(p)
            layers.append(node[2])
        else:
            points.append(p)
            layers.append(node[2])
    # Remove duplicate points while retaining layer transition boundaries.
    cleaned = []
    for p, layer in zip(points, layers):
        if cleaned and p == cleaned[-1][0] and layer == cleaned[-1][1]:
            continue
        cleaned.append((p, layer))
    compact = []
    for item in cleaned:
        compact.append(item)
        while len(compact) >= 3:
            (a, la), (b, lb), (c, lc) = compact[-3:]
            if la == lb == lc and abs((b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])) < 1e-10:
                compact.pop(-2)
            else:
                break
    return path, compact


def main():
    pads, all_pads = pad_snapshot()
    existing = snapshot_tracks()
    antenna, antenna_vias, board, antenna_plan, coil_fill = antenna_geometry()
    if antenna_plan["vias"][0]["x_mil"] != -60.0 or abs(antenna_plan["vias"][0]["y_mil"] - 47.2440944882) > 1e-6:
        raise ValueError("Expected reviewed LA breakout via at (-60, 47.244) mil")

    all_tracks = existing + antenna
    candidate_tracks = []
    candidate_vias = []
    records = []
    # ANT launch nets join the reviewed antenna breakouts and are routed first,
    # so their proposed tuning-pad traces become obstacles for power routes.
    for net in ("ANT_LA", "ANT_LB", "VOUT", "GND"):
        targets = TARGETS[net]
        seeds = [targets[0]]
        connected = {(*grid_index(pads[targets[0]]["center"]), pads[targets[0]]["layer"])}
        pin_records = [{"pin": targets[0], "role": "seed"}]
        remaining = targets[1:]
        while remaining:
            # Route short targets first to reduce the chance that a later net
            # segment partitions the central component cluster.
            target = min(remaining, key=lambda p: pads[p]["geom"].distance(unary_union([Point(*grid_point(n[:2])) for n in connected if n[2] == pads[p]["layer"]]) if any(n[2] == pads[p]["layer"] for n in connected) else Point(*pads[targets[0]]["center"])))
            remaining.remove(target)

            obstacles = {}
            for layer in (1, 2):
                shapes = []
                if layer == 1:
                    # The pending bridged-fill area is treated as occupied for
                    # candidate routes until its native bridge behavior is set.
                    shapes.append(coil_fill.buffer(ROUTE_CLEARANCE + TRACE_WIDTH / 2))
                for p in all_pads:
                    if p["layer"] == layer and p["net"] != net:
                        shapes.append(p["geom"].buffer(ROUTE_CLEARANCE + TRACE_WIDTH / 2))
                for t in all_tracks + candidate_tracks:
                    if t["layer"] == layer and t["net"] != net:
                        shapes.append(t["geom"].buffer(ROUTE_CLEARANCE + (TRACE_WIDTH + t["width"]) / 2))
                for v in antenna_vias + candidate_vias:
                    if v["net"] != net:
                        shapes.append(v["point"].buffer(ROUTE_CLEARANCE + VIA_DIAMETER / 2 + TRACE_WIDTH / 2))
                obstacles[layer] = unary_union(shapes) if shapes else Polygon()
            via_shapes = []
            via_shapes.append(coil_fill.buffer(ROUTE_CLEARANCE + VIA_DIAMETER / 2))
            for p in all_pads:
                if p["net"] != net:
                    via_shapes.append(p["geom"].buffer(ROUTE_CLEARANCE + VIA_DIAMETER / 2))
            for t in all_tracks + candidate_tracks:
                via_shapes.append(t["geom"].buffer(ROUTE_CLEARANCE + VIA_DIAMETER / 2 + t["width"] / 2))
            for v in antenna_vias + candidate_vias:
                if v["net"] != net:
                    via_shapes.append(v["point"].buffer(ROUTE_CLEARANCE + VIA_DIAMETER / 2 + v["radius"]))
            via_obstacles = unary_union(via_shapes) if via_shapes else Polygon()

            path, compact = route_one_target(net, target, connected, pads, obstacles, via_obstacles, board)
            for k in range(1, len(path)):
                a, b = path[k - 1], path[k]
                if a[2] != b[2]:
                    pt = Point(*grid_point(a[:2]))
                    candidate_vias.append({"id": f"{net}_via_{len(candidate_vias)+1}", "net": net, "point": pt, "radius": VIA_DIAMETER / 2, "source": "candidate"})
            # Emit the compact route points; a layer transition shares its via center.
            for k in range(1, len(compact)):
                a, la = compact[k - 1]
                b, lb = compact[k]
                if la != lb:
                    continue
                geom = LineString([a, b])
                if geom.length < 1e-8:
                    continue
                item = {"id": f"{net}_route_{len(candidate_tracks)+1}", "net": net, "layer": la, "width": TRACE_WIDTH, "geom": geom, "source": "candidate", "to_pin": target}
                candidate_tracks.append(item)
            connected.update(path)
            pin_records.append({"pin": target, "role": "routed", "path_nodes": len(path), "layer_changes": sum(path[i][2] != path[i-1][2] for i in range(1, len(path)))})
        records.append({"net": net, "pins": pin_records})

    # Quantize the actual candidate geometry first, then merge continuous
    # same-net, same-layer collinear segments before auditing/export.
    unmerged_track_count = len(candidate_tracks)
    quantize_linework(candidate_tracks, candidate_vias)
    candidate_tracks = merge_collinear_tracks(candidate_tracks)

    # Full geometry audit: each proposed trace and via is copper, and every
    # unlike-net pair must preserve the required 0.1524 mm edge-to-edge gap.
    checks = {"track_to_pad": [], "track_to_track": [], "via_to_pad": [], "via_to_track": [], "via_to_via": [], "track_to_coil_fill": [], "via_to_coil_fill": []}
    def check(item_type, a, b, gap, ids):
        checks[item_type].append({**ids, "gap_mm": round(gap, 8)})
    for t in candidate_tracks:
        if t["layer"] == 1:
            gap = t["geom"].distance(coil_fill) - t["width"] / 2
            check("track_to_coil_fill", t, {"id": "antenna-coil-fill"}, gap, {"track": t["id"], "fill": "antenna-coil-fill", "net": t["net"], "fill_net": "ANT_LA|ANT_LB bridge candidate"})
        for p in all_pads:
            if t["layer"] == p["layer"] and t["net"] != p["net"]:
                gap = t["geom"].distance(p["geom"]) - t["width"] / 2
                check("track_to_pad", t, p, gap, {"track": t["id"], "pad": p["id"], "net": t["net"], "pad_net": p["net"]})
        for other in existing + antenna + candidate_tracks:
            if other is t or other["layer"] != t["layer"] or other["net"] == t["net"]:
                continue
            gap = t["geom"].distance(other["geom"]) - (t["width"] + other["width"]) / 2
            check("track_to_track", t, other, gap, {"track": t["id"], "other": other["id"], "net": t["net"], "other_net": other["net"]})
        for v in antenna_vias + candidate_vias:
            if t["net"] != v["net"]:
                gap = v["point"].distance(t["geom"]) - v["radius"] - t["width"] / 2
                check("via_to_track", v, t, gap, {"via": v["id"], "track": t["id"], "net": v["net"], "track_net": t["net"]})
    all_vias = antenna_vias + candidate_vias
    for v in candidate_vias:
        gap = v["point"].distance(coil_fill) - v["radius"]
        check("via_to_coil_fill", v, {"id": "antenna-coil-fill"}, gap, {"via": v["id"], "fill": "antenna-coil-fill", "net": v["net"], "fill_net": "ANT_LA|ANT_LB bridge candidate"})
        for p in all_pads:
            if v["net"] != p["net"]:
                check("via_to_pad", v, p, v["point"].distance(p["geom"]) - v["radius"], {"via": v["id"], "pad": p["id"], "net": v["net"], "pad_net": p["net"]})
        for t in existing + antenna:
            if v["net"] != t["net"]:
                gap = v["point"].distance(t["geom"]) - v["radius"] - t["width"] / 2
                check("via_to_track", v, t, gap, {"via": v["id"], "track": t["id"], "net": v["net"], "track_net": t["net"]})
        for other in all_vias:
            if v is not other and v["net"] != other["net"]:
                check("via_to_via", v, other, v["point"].distance(other["point"]) - v["radius"] - other["radius"], {"via": v["id"], "other_via": other["id"], "net": v["net"], "other_net": other["net"]})
    all_copper = []
    for t in candidate_tracks:
        all_copper.append((t["id"], t["geom"].buffer(t["width"] / 2)))
    for v in candidate_vias:
        all_copper.append((v["id"], v["point"].buffer(v["radius"])))
    outside = [name for name, shape in all_copper if not board.covers(shape)]
    minimums = {k: min((x["gap_mm"] for x in rows), default=None) for k, rows in checks.items()}
    minimum_pairs = {k: min(rows, key=lambda x: x["gap_mm"]) if rows else None for k, rows in checks.items()}
    violations = {k: [x for x in rows if x["gap_mm"] < CLEARANCE - 1e-8] for k, rows in checks.items()}
    native_coords = [z / MM_PER_MIL for t in candidate_tracks for p in (t["geom"].coords[0], t["geom"].coords[-1]) for z in p]
    native_coords += [z / MM_PER_MIL for v in candidate_vias for z in (v["point"].x, v["point"].y)]
    coords_on_native_grid = all(abs(v * 10 - round(v * 10)) < 1e-8 for v in native_coords)

    # Connectivity is checked as a same-net copper graph through target pads,
    # existing route endpoints, the reviewed antenna geometry, and candidates.
    connectivity = {}
    for net, pins in TARGETS.items():
        items = []
        for p in all_pads:
            if p["net"] == net:
                items.append((p["id"], p["geom"], p["layer"]))
        for t in existing + antenna + candidate_tracks:
            if t["net"] == net:
                items.append((t["id"], t["geom"].buffer(t["width"] / 2), t["layer"]))
        for v in all_vias:
            if v["net"] == net:
                items.append((v["id"], v["point"].buffer(v["radius"]), 0))
        adj = {i: set() for i in range(len(items))}
        for i, a in enumerate(items):
            for j in range(i + 1, len(items)):
                b = items[j]
                if a[2] == b[2] and a[1].intersects(b[1]):
                    adj[i].add(j); adj[j].add(i)
                elif a[2] == 0 or b[2] == 0:
                    if a[1].intersects(b[1]):
                        adj[i].add(j); adj[j].add(i)
        lookup = {name: i for i, (name, _, _) in enumerate(items)}
        start = lookup[pins[0]]
        seen = {start}; todo = [start]
        while todo:
            for j in adj[todo.pop()]:
                if j not in seen:
                    seen.add(j); todo.append(j)
        connectivity[net] = {"connected": all(lookup[p] in seen for p in pins), "pins": pins, "disconnected": [p for p in pins if lookup[p] not in seen]}

    def emit_track(t):
        a, b = list(t["geom"].coords)
        return {"id": t["id"], "net": t["net"], "layer": t["layer"], "width_mm": round(t["width"], 6),
                "start_mm": [round(a[0], 6), round(a[1], 6)], "end_mm": [round(b[0], 6), round(b[1], 6)],
                "start_native_mil": [round(a[0]/MM_PER_MIL, 4), round(a[1]/MM_PER_MIL, 4)],
                "end_native_mil": [round(b[0]/MM_PER_MIL, 4), round(b[1]/MM_PER_MIL, 4)], "to_pin": t.get("to_pin")}
    result = {
        "status": "draft_offline_route_candidate",
        "draft": True,
        "sources": ["eda/core-pads.json", "eda/native/core-initial-tracks.json", "electrical/antenna-geometry-review.json:proposal_geometry", "electrical/antenna-coil-fill-candidate.json"],
        "constraints": {"required_clearance_mm": CLEARANCE, "route_clearance_target_mm": ROUTE_CLEARANCE,
                        "coordinate_grid_mil": 0.1, "coordinates_quantized_before_audit": True,
                        "trace_width_mm": TRACE_WIDTH, "via_drill_mm": VIA_DRILL, "via_diameter_mm": VIA_DIAMETER,
                        "board_outline": "reviewed 37 mm octagon"},
        "connectivity": connectivity,
        "routing_records": records,
        "tracks": [emit_track(t) for t in candidate_tracks],
        "vias": [{"id": v["id"], "net": v["net"], "x_mm": round(v["point"].x, 6), "y_mm": round(v["point"].y, 6), "x_native_mil": round(v["point"].x/MM_PER_MIL, 4), "y_native_mil": round(v["point"].y/MM_PER_MIL, 4), "drill_mm": VIA_DRILL, "diameter_mm": VIA_DIAMETER} for v in candidate_vias],
        "geometry_audit": {"all_candidate_copper_inside_outline": not outside, "outside_copper": outside,
                           "minimum_edge_clearance_mm_by_pair_type": minimums, "required_clearance_mm": CLEARANCE,
                           "minimum_pair_by_type": minimum_pairs,
                           "route_clearance_target_mm": ROUTE_CLEARANCE,
                           "all_checked_clearances_meet_route_target": all(v is None or v >= ROUTE_CLEARANCE - 1e-8 for v in minimums.values()),
                           "coordinates_on_native_0_1_mil_grid": coords_on_native_grid,
                           "violations": violations, "minimum_overall_checked_gap_mm": min((v for v in minimums.values() if v is not None), default=None)},
        "segment_merge": {"before": unmerged_track_count, "after": len(candidate_tracks), "merged_count_reduction": unmerged_track_count - len(candidate_tracks)},
        "notes": ["Draft geometry only; no live EDA operation or API assumptions were used.",
                  "The antenna coil fill remains a geometry candidate with bridge_enabled=false; this report checks the reviewed launch and bottom-return geometry.",
                  "Connectivity is geometric against saved snapshots and candidates; native DRC, bridge-fill semantics, RF behavior, and final live-board state remain unverified."]
    }
    out = ROOT / "electrical/power-route-candidate.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "pins_connected": {k:v["connected"] for k,v in connectivity.items()},
                      "track_count_before_merge": unmerged_track_count, "track_count": len(candidate_tracks), "via_count": len(candidate_vias), "all_inside_outline": not outside,
                      "minimums": minimums, "violation_counts": {k:len(v) for k,v in violations.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
