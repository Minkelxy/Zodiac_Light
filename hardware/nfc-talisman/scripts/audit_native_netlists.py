"""Read-only comparison of saved schematic/core/panel native netlists."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NETLIST_DIR = ROOT / "eda/native"
SOURCE_DIR = ROOT / "eda/native"
PANEL_OFFSET_MIL = 50.0 / 0.0254
EXPECTED_TESTPOINTS = {
    "TP1": {"net": "VOUT", "x": 80.0, "y": 115.0},
    "TP2": {"net": "GND", "x": 235.0, "y": 115.0},
}
COORD_TOL_MIL = 0.001


def read_netlist(name: str) -> tuple[dict[str, Any], bytes]:
    path = NETLIST_DIR / f"{name}-netlist.json"
    raw_bytes = path.read_bytes()
    outer = json.loads(raw_bytes.decode("utf-8"))
    if name == "schematic":
        if not isinstance(outer, dict):
            raise ValueError("schematic-netlist.json must contain the native JSON object")
        native = outer
    else:
        if not (isinstance(outer, list) and len(outer) == 2 and isinstance(outer[0], str)):
            raise ValueError(f"{name}-netlist.json must be the two-string PCB export envelope")
        # The first string is the native PCB netlist. The second string is a
        # companion export and is intentionally not used for this audit.
        native = json.loads(outer[0])
    if not isinstance(native, dict) or not isinstance(native.get("components"), dict):
        raise ValueError(f"{name} native netlist has no components map")
    return native, raw_bytes


def included_components(netlist: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    included, excluded = {}, []
    for ref, component in netlist["components"].items():
        flag = str(component.get("props", {}).get("Convert to PCB", "")).strip().lower()
        if flag == "no":
            excluded.append(ref)
        else:
            included[ref] = component
    return included, sorted(excluded)


def pin_net_map(netlist: dict[str, Any]) -> tuple[dict[str, str | None], dict[str, Any]]:
    components, excluded = included_components(netlist)
    mapping: dict[str, str | None] = {}
    duplicates = []
    missing_net = []
    for ref, component in components.items():
        for pin_key, pin in (component.get("pinInfoMap") or {}).items():
            number = str(pin.get("number", pin_key))
            key = f"{ref}.{number}"
            if key in mapping:
                duplicates.append(key)
            mapping[key] = pin.get("net")
            if not pin.get("net"):
                missing_net.append(key)
    summary = {"component_count": len(components), "pin_count": len(mapping),
               "excluded_convert_to_pcb_no": excluded,
               "net_count": len({n for n in mapping.values() if n}),
               "duplicate_pin_keys": sorted(set(duplicates)), "pins_without_net": sorted(missing_net)}
    return mapping, summary


def compare_netlists(left_name: str, left: dict[str, Any], right_name: str, right: dict[str, Any]) -> dict[str, Any]:
    left_map, left_summary = pin_net_map(left)
    right_map, right_summary = pin_net_map(right)
    left_keys, right_keys = set(left_map), set(right_map)
    diffs = {
        "components_only_in_left": sorted(set(included_components(left)[0]) - set(included_components(right)[0])),
        "components_only_in_right": sorted(set(included_components(right)[0]) - set(included_components(left)[0])),
        "pins_only_in_left": sorted(left_keys - right_keys),
        "pins_only_in_right": sorted(right_keys - left_keys),
        "net_mismatches": [{"pin": key, "left_net": left_map[key], "right_net": right_map[key]}
                           for key in sorted(left_keys & right_keys) if left_map[key] != right_map[key]],
    }
    passed = (not any(diffs.values()) and not left_summary["duplicate_pin_keys"] and
              not right_summary["duplicate_pin_keys"] and not left_summary["pins_without_net"] and
              not right_summary["pins_without_net"])
    return {"group": f"{left_name}_vs_{right_name}", "passed": passed,
            "left": left_summary, "right": right_summary, "diffs": diffs}


def read_source_pads(path: Path) -> dict[str, list[dict[str, Any]]]:
    found = {ref: [] for ref in EXPECTED_TESTPOINTS}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "||" not in raw:
            continue
        try:
            meta_text, data_text = raw.split("||", 1)
            meta = json.loads(meta_text)
            if meta.get("type") != "PAD":
                continue
            data = json.loads(data_text.rstrip("|"))
        except Exception as exc:
            raise ValueError(f"Cannot parse {path}:{line_no}: {exc}") from exc
        num = data.get("num")
        if num in found:
            found[num].append({"id": meta.get("id"), **data})
    return found


def verify_testpoints(core_path: Path, panel_path: Path) -> dict[str, Any]:
    core, panel = read_source_pads(core_path), read_source_pads(panel_path)
    entries, errors = {}, []
    def check_one(ref: str, data: dict[str, Any], expected: dict[str, Any], label: str):
        reasons = []
        if data.get("netName") != expected["net"]: reasons.append("wrong_net")
        if data.get("layerId") != 1: reasons.append("not_top_layer")
        if data.get("hole") not in (None, {}): reasons.append("has_hole")
        shape = data.get("defaultPad") or {}
        if shape.get("padType") != "ELLIPSE": reasons.append("not_ellipse")
        for axis in ("width", "height"):
            if abs(float(shape.get(axis, 0) or 0) * 0.0254 - 0.8) > 0.0001:
                reasons.append(f"{axis}_not_0.8mm")
        if float(data.get("topPasteExpansion", 0) or 0) <= -999: paste_disabled = True
        else: paste_disabled = False
        if not paste_disabled: reasons.append("solder_paste_not_disabled")
        offset = PANEL_OFFSET_MIL if label == "panel" else 0.0
        expected_xy = [expected["x"] + offset, expected["y"] + offset]
        actual_xy = [float(data.get("centerX", float("nan"))), float(data.get("centerY", float("nan")))]
        center_matches = all(abs(actual_xy[i] - expected_xy[i]) <= COORD_TOL_MIL for i in (0, 1))
        if not center_matches: reasons.append("center_coordinate_mismatch")
        return {"id": data.get("id"), "net": data.get("netName"), "layerId": data.get("layerId"),
                "center_mil": actual_xy, "expected_center_mil": expected_xy,
                "center_matches_expected": center_matches,
                "pad_shape": shape.get("padType"), "pad_size_mil": [shape.get("width"), shape.get("height")],
                "hole": data.get("hole"), "topPasteExpansion": data.get("topPasteExpansion"),
                "passed": not reasons, "errors": reasons, "source": label}

    for ref, expected in EXPECTED_TESTPOINTS.items():
        if len(core[ref]) != 1:
            errors.append(f"core_{ref}_count_{len(core[ref])}")
        if len(panel[ref]) != 1:
            errors.append(f"panel_{ref}_count_{len(panel[ref])}")
        cinfo = check_one(ref, core[ref][0], expected, "core") if len(core[ref]) == 1 else None
        pinfo = check_one(ref, panel[ref][0], expected, "panel") if len(panel[ref]) == 1 else None
        if cinfo and not cinfo["passed"]: errors.extend(f"core_{ref}_{e}" for e in cinfo["errors"])
        if pinfo and not pinfo["passed"]: errors.extend(f"panel_{ref}_{e}" for e in pinfo["errors"])
        translation = None
        if cinfo and pinfo:
            dx = float(pinfo["center_mil"][0]) - float(cinfo["center_mil"][0])
            dy = float(pinfo["center_mil"][1]) - float(cinfo["center_mil"][1])
            translation = {"dx_mil": dx, "dy_mil": dy,
                           "matches_50mm_xy_panel_offset": abs(dx-PANEL_OFFSET_MIL) <= COORD_TOL_MIL and abs(dy-PANEL_OFFSET_MIL) <= COORD_TOL_MIL}
            if not translation["matches_50mm_xy_panel_offset"]:
                errors.append(f"{ref}_panel_translation_mismatch")
        entries[ref] = {"expected": expected, "core_source": cinfo, "panel_source": pinfo,
                        "panel_translation": translation}
    return {"passed": not errors, "entries": entries, "errors": errors,
            "note": "Free PAD test points are checked from PCB source and are intentionally not treated as BOM components."}


def main() -> int:
    names = ("schematic", "core", "panel")
    loaded, input_bytes = {}, {}
    for name in names:
        loaded[name], input_bytes[name] = read_netlist(name)
    comparisons = [compare_netlists("schematic", loaded["schematic"], "core", loaded["core"]),
                   compare_netlists("core", loaded["core"], "panel", loaded["panel"])]
    source_files = {"core_source": SOURCE_DIR / "core-source.jsonl",
                    "panel_source": SOURCE_DIR / "panel-source.jsonl"}
    testpoints = verify_testpoints(source_files["core_source"], source_files["panel_source"])
    input_paths = {**{f"{n}_netlist": NETLIST_DIR / f"{n}-netlist.json" for n in names}, **source_files}
    hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in input_paths.items()}
    summaries = {name: pin_net_map(loaded[name])[1] for name in names}
    expected_inventory = {"component_count": 15, "pin_count": 36}
    inventory_checks = {name: {"expected": expected_inventory,
                               "actual": {"component_count": value["component_count"], "pin_count": value["pin_count"]},
                               "passed": value["component_count"] == 15 and value["pin_count"] == 36 and
                                        not value["duplicate_pin_keys"] and not value["pins_without_net"]}
                        for name, value in summaries.items()}
    passed = all(x["passed"] for x in comparisons) and testpoints["passed"] and all(
        check["passed"] for check in inventory_checks.values())
    report = {"status": "native_netlist_audit", "read_only": True,
              "filter": "Include components where props['Convert to PCB'] != 'no' (case-insensitive).",
              "pcb_envelope_rule": "For core and panel, parse the first native JSON string only.",
              "input_sha256": hashes,
              "groups": {"schematic": summaries["schematic"], "core": summaries["core"], "panel": summaries["panel"]},
              "expected_inventory_checks": inventory_checks,
              "comparisons": {x["group"]: x for x in comparisons},
              "free_testpoints_from_native_source": testpoints,
              "all_groups_passed": passed}
    out = ROOT / "electrical/native-netlist-audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out), "all_groups_passed": passed,
                      "counts": {k: {"components": v["component_count"], "pins": v["pin_count"]} for k, v in summaries.items()},
                      "comparison_diffs": {k: v["diffs"] for k, v in report["comparisons"].items()},
                      "testpoint_errors": testpoints["errors"]}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
