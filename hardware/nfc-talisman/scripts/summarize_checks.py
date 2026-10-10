#!/usr/bin/env python3
"""Summarize the latest saved EasyEDA ERC/DRC check logs as JSON."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "eda" / "logs"
CHECKS = {
    "schematic_erc": ("24-schematic-erc-current", "293c7786afd689e8"),
    "core_pcb_drc": ("25-core-pcb-drc-current", "eb14b9eaec4f920c"),
    "panel_pcb_drc": ("26-panel-pcb-drc-current", "4a4719695b24dc2b"),
}


def one_check(key: str, stem: str, expected_uuid: str) -> dict:
    candidates = list(LOGS.glob(stem + ".json"))
    if not candidates:
        return {"status": "missing", "error": f"No {stem}.json in {LOGS}", "document_uuid": expected_uuid}
    path = max(candidates, key=lambda item: item.stat().st_mtime_ns)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "failed", "file": path.name, "error": f"Cannot read JSON: {exc}", "document_uuid": expected_uuid}

    if data.get("success") is not True or not isinstance(data.get("result"), dict):
        return {"status": "failed", "file": path.name, "error": data.get("error", "Log has no successful result"), "document_uuid": expected_uuid}
    result = data["result"]
    actual_uuid = result.get("document", {}).get("uuid")
    if actual_uuid != expected_uuid:
        return {"status": "failed", "file": path.name, "error": f"Unexpected document UUID: {actual_uuid!r}", "document_uuid": expected_uuid}

    if key == "schematic_erc":
        errors = result.get("errors")
        if not isinstance(errors, list):
            return {"status": "failed", "file": path.name, "error": "ERC errors array missing", "document_uuid": expected_uuid}
        counts = result.get("counts", {})
        return {"status": "completed_with_findings" if errors else "completed_clean", "file": path.name,
                "raw_count": result.get("rawCount", len(errors)), "counts": counts, "document_uuid": actual_uuid}

    drc = result.get("drc")
    if not isinstance(drc, list):
        return {"status": "failed", "file": path.name, "error": "DRC result array missing", "document_uuid": expected_uuid}
    counts = result.get("counts", {})
    def leaf_count(group: dict) -> int:
        children = group.get("list")
        if not isinstance(children, list):
            return 1
        return sum(leaf_count(item) for item in children if isinstance(item, dict))

    groups = [{"name": item.get("name", "unknown"), "items": leaf_count(item)}
              for item in drc if isinstance(item, dict)]
    return {"status": "completed_with_findings" if drc else "completed_clean", "file": path.name,
            "drc_group_count": result.get("drcGroupCount", len(drc)), "finding_groups": groups, "counts": counts,
            "document_uuid": actual_uuid}


def main() -> None:
    summary = {key: one_check(key, stem, uuid) for key, (stem, uuid) in CHECKS.items()}
    print(json.dumps({"logs_dir": str(LOGS), "checks": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
