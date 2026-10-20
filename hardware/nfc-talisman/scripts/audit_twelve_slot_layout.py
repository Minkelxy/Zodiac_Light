"""Independent physical-primitive checks for generated four-panel options."""
import hashlib
import json
import math
from pathlib import Path
import re
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HW = Path(__file__).resolve().parents[1]
ROOT = HW.parents[1]
OUT = HW / "variants/twelve-options"
CENTERS = [(21, 79), (79, 79), (50, 50), (21, 21), (79, 21)]
half = 18.5
bevel = half * (math.sqrt(2) - 1)
OCT = Polygon([(-bevel, half), (bevel, half), (half, bevel), (half, -bevel),
               (bevel, -half), (-bevel, -half), (-half, -bevel), (-half, bevel)])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def polygon(body):
    path = body["path"]
    assert path[2] == "L" and all(isinstance(v, (float, int)) for v in path[3:])
    values = path[:2] + path[3:]
    p = Polygon([(values[i] * .0254, values[i + 1] * .0254) for i in range(0, len(values), 2)])
    assert p.is_valid and p.area > 0
    return p


def main():
    manifest_file = OUT / "design-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    comparison_file = OUT / "sources/slot-optimization.json"
    comparison = json.loads(comparison_file.read_text(encoding="utf-8"))
    result = {"status": "passed", "read_only": True, "design_manifest_sha256": sha(manifest_file),
              "slot_optimization_report_sha256": sha(comparison_file), "panels": {}, "errors": []}
    for panel in manifest["panels"]:
        report = {"covers": {}}
        try:
            path = OUT / panel["geometry"]
            data = json.loads(path.read_text(encoding="utf-8"))
            report["geometry_sha256"] = sha(path)
            assert data["cover_count"] == len(data["covers"]) == 5
            prim = data["primitives"]
            frames = [p for p in prim if p["logical_id"].startswith("panel-frame")]
            assert len(frames) == 1 and polygon(frames[0]["body"]).symmetric_difference(box(0, 0, 100, 100)).area < 1e-7
            all_routing, all_apertures = [], []
            for index, cover in enumerate(data["covers"]):
                name = cover["id"]
                cx, cy = cover["center_native_mm"]
                assert (cx, cy) == CENTERS[index]
                board = affinity.translate(OCT, cx, cy)
                routing = [polygon(p["body"]) for p in prim if p["logical_id"].startswith(name + ":routing:")]
                actual_routing = unary_union(routing)
                corridors = unary_union([box(cx - 2, cy - 21, cx + 2, cy + 21), box(cx - 21, cy - 2, cx + 21, cy + 2)])
                expected_routing = board.buffer(1, quad_segs=12).difference(board).difference(corridors)
                assert expected_routing.hausdorff_distance(actual_routing) < 1e-6
                assert expected_routing.symmetric_difference(actual_routing).area < 1e-5
                all_routing += routing
                mb = [p for p in prim if re.fullmatch(re.escape(name) + r"_[NSEW]_MB[1-5]", p["logical_id"])]
                assert len(mb) == 20
                for item in mb:
                    body = item["body"]
                    edge, number = re.search(r"_([NSEW])_MB([1-5])$", item["logical_id"]).groups()
                    offset = (-1.44, -.72, 0, .72, 1.44)[int(number) - 1]
                    if edge in ("N", "S"):
                        expected_xy = (cx + offset, cy + (18.9 if edge == "N" else -18.9))
                    else:
                        expected_xy = (cx + (18.9 if edge == "E" else -18.9), cy + offset)
                    xy = (body["centerX"] * .0254, body["centerY"] * .0254)
                    assert math.dist(xy, expected_xy) < 1e-7
                    assert body["plated"] is False and abs(body["hole"]["width"] * .0254 - .4) < 1e-7
                    all_apertures.append(Point(xy).buffer(.2, quad_segs=32))
                cover_report = {"mousebites": 20, "bridge_width_mm": 4, "mousebite_diameter_mm": .4,
                                "mousebite_pitch_mm": .72, "routing_unchanged": True}
                if name in comparison["covers"]:
                    details = cover["details"]["slot_layout"]
                    reference = comparison["covers"][name]
                    for field, expected in reference["after"].items():
                        assert details[field] == expected, f"{name}: optimized metadata differs: {field}"
                    positions = details["star_positions_final_mm"]
                    stars = [p for p in prim if p["logical_id"].startswith(name + "_HIP")]
                    assert len(stars) == len(positions) == len(reference["hip_ids"])
                    actual_holes = []
                    for item in stars:
                        hip = str(int(item["logical_id"].split("_HIP")[1]))
                        assert hip in positions
                        body = item["body"]
                        assert body["plated"] is False and abs(body["hole"]["width"] * .0254 - .8) < 1e-7
                        x, y = positions[hip]
                        expected_xy = (cx + x - 18.5, cy + 18.5 - y)
                        native_xy = (body["centerX"] * .0254, body["centerY"] * .0254)
                        assert math.dist(native_xy, expected_xy) < 1e-7
                        actual_holes.append(Point(native_xy).buffer(.4, quad_segs=32))
                    slot_entries = [p for p in prim if p["logical_id"].startswith(name + ":light-slot:")]
                    slot_entries.sort(key=lambda item: tuple(map(int, item["logical_id"].split(":")[-2:])))
                    records = details["slots"]
                    assert len(slot_entries) == len(records) == reference["after"]["physical_slot_count"]
                    physical_slots = []
                    allowed_edges = {tuple(edge) for edge in reference["logical_edges"]}
                    for item, slot in zip(slot_entries, records):
                        assert tuple(slot["edge"]) in allowed_edges
                        start, end = slot["start_mm"], slot["end_mm"]
                        expected = LineString([start, end]).buffer(.5, quad_segs=32)
                        expected = affinity.translate(affinity.scale(expected, 1, -1, origin=(0, 0)), cx - 18.5, cy + 18.5)
                        actual = polygon(item["body"])
                        assert expected.hausdorff_distance(actual) < 1e-6
                        assert expected.symmetric_difference(actual).area < 1e-5
                        assert slot["overall_length_mm"] >= 1.5 - 1e-9
                        physical_slots.append(actual)
                    minimum_star = min(s.distance(h) for s in physical_slots for h in actual_holes)
                    minimum_pair = min((a.distance(b) for i, a in enumerate(physical_slots) for b in physical_slots[i + 1:]), default=None)
                    minimum_board = min(s.distance(board.boundary) for s in physical_slots)
                    material = board.difference(unary_union([*actual_holes, *physical_slots]))
                    assert minimum_star >= 1 - 1e-6
                    assert minimum_pair is None or minimum_pair >= .8 - 1e-6
                    assert minimum_board >= 1 - 1e-6
                    assert material.is_valid and material.geom_type == "Polygon"
                    cover_report.update({"hip_holes": len(stars), "physical_slots": len(physical_slots),
                        "minimum_star_to_slot_material_mm": minimum_star,
                        "minimum_slot_to_slot_material_mm": minimum_pair,
                        "minimum_slot_to_outer_edge_material_mm": minimum_board,
                        "hip_positions_match_final": True, "slot_shapes_and_HIP_edges_match": True,
                        "fr4_single_connected_component": True})
                    all_apertures += actual_holes + physical_slots
                report["covers"][name] = cover_report
            panel_material = box(0, 0, 100, 100).difference(unary_union([*all_routing, *all_apertures]))
            assert panel_material.is_valid and panel_material.geom_type == "Polygon", "Panel material disconnected"
            report.update({"passed": True, "frame_mm": [100, 100], "mousebites": 100,
                           "panel_fr4_single_connected_component": True})
        except Exception as exc:
            report["passed"] = False
            report["error"] = str(exc)
            result["errors"].append(f"{panel['key']}: {exc}")
        result["panels"][panel["key"]] = report
    if result["errors"]:
        result["status"] = "failed"
    result["limitations"] = ["Offline generated physical primitives only; saved native documents and actual exported Gerber are checked separately.",
                             "No supplier cutter compensation, depanelization, FR-4 strength or optical acceptance is asserted."]
    target = OUT / "slot-layout-geometry-audit.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "errors": result["errors"], "report": str(target)}, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
