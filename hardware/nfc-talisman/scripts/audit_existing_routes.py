"""Audit saved live-route snapshot against native pads and distinct nets."""
from __future__ import annotations
import json
import math
from pathlib import Path

from shapely.affinity import rotate
from shapely.geometry import LineString, box

ROOT = Path(__file__).resolve().parents[1]
MM_PER_MIL = 0.0254
CLEARANCE_MM = 0.1524  # 6 mil


def main() -> None:
    live = json.loads((ROOT / "eda/logs/22-audit-core-tracks.json").read_text(encoding="utf-8"))
    routes = live["result"]["lines"]
    components = json.loads((ROOT / "eda/core-pads.json").read_text(encoding="utf-8"))
    pads = []
    for comp in components:
        for pad in comp["pins"]:
            if pad["pad"][0] != "RECT":
                raise ValueError(f"Unsupported native pad geometry: {comp['ref']}.{pad['padNumber']}")
            x, y = pad["x"] * MM_PER_MIL, pad["y"] * MM_PER_MIL
            w, h = pad["pad"][1] * MM_PER_MIL, pad["pad"][2] * MM_PER_MIL
            geom = rotate(box(x - w/2, y - h/2, x + w/2, y + h/2), pad["rotation"], origin=(x, y))
            pads.append({"id": f"{comp['ref']}.{pad['padNumber']}", "net": pad["net"], "layer": pad["layer"], "geom": geom})

    lines = []
    for item in routes:
        a = tuple(v * MM_PER_MIL for v in item["start"])
        b = tuple(v * MM_PER_MIL for v in item["end"])
        lines.append({**item, "geom": LineString([a, b]), "width_mm": item["width"] * MM_PER_MIL})

    pad_checks = []
    for line in lines:
        for pad in pads:
            if line["layer"] != pad["layer"] or line["net"] == pad["net"]:
                continue
            gap = line["geom"].distance(pad["geom"]) - line["width_mm"] / 2
            pad_checks.append({"line_id": line["id"], "line_net": line["net"], "pad": pad["id"], "pad_net": pad["net"], "gap_mm": gap})

    line_checks = []
    for i, a in enumerate(lines):
        for b in lines[i+1:]:
            if a["layer"] != b["layer"] or a["net"] == b["net"]:
                continue
            gap = a["geom"].distance(b["geom"]) - (a["width_mm"] + b["width_mm"]) / 2
            line_checks.append({"line_a": a["id"], "net_a": a["net"], "line_b": b["id"], "net_b": b["net"], "gap_mm": gap})

    closest_pad = min(pad_checks, key=lambda x: x["gap_mm"])
    closest_line = min(line_checks, key=lambda x: x["gap_mm"])
    violations = [x for x in pad_checks if x["gap_mm"] < CLEARANCE_MM - 1e-9] + [x for x in line_checks if x["gap_mm"] < CLEARANCE_MM - 1e-9]
    summary = {
        "snapshot": "eda/logs/22-audit-core-tracks.json",
        "pad_source": "eda/core-pads.json",
        "route_count": len(lines),
        "different_net_track_to_pad_pairs_checked": len(pad_checks),
        "different_net_track_pairs_checked": len(line_checks),
        "required_clearance_mm": CLEARANCE_MM,
        "closest_track_to_different_net_pad": {**closest_pad, "gap_mm": round(closest_pad["gap_mm"], 8)},
        "closest_different_net_track_pair": {**closest_line, "gap_mm": round(closest_line["gap_mm"], 8)},
        "violations": [{**x, "gap_mm": round(x["gap_mm"], 8)} for x in violations],
        "note": "Geometry-only screening of current 19 routes; excludes net connectivity, solder-mask, via, antenna and native EasyEDA DRC checks."
    }
    out = ROOT / "electrical/existing-route-audit.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("route_count", "required_clearance_mm", "closest_track_to_different_net_pad", "closest_different_net_track_pair", "violations")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
