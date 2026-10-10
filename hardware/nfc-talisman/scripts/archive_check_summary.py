#!/usr/bin/env python3
"""Write a versioned, source-hashed snapshot of the current ERC/DRC logs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from summarize_checks import CHECKS, LOGS, one_check  # noqa: E402

OUTPUT = ROOT / "eda" / "check-summary.json"
NATIVE_SOURCES = {
    "schematic_erc": ("eda/native/schematic-source.jsonl", "eda/native/schematic-netlist.json"),
    "core_pcb_drc": ("eda/native/core-source.jsonl", "eda/native/core-netlist.json"),
    "panel_pcb_drc": ("eda/native/panel-source.jsonl", "eda/native/panel-netlist.json"),
}
NATIVE_PROJECT = "eda/native/nfc-talisman-current.epro2"
SNAPSHOT_NOTE = (
    "Current native/log snapshot for review; this is not manufacturing release. "
    "Regenerate after any source, native project, or check-log change."
)


def file_record(path: Path) -> dict:
    if not path.is_file():
        return {"path": path.relative_to(ROOT).as_posix(), "status": "missing"}
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "status": "present",
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def current_log(stem: str) -> Path | None:
    candidates = list(LOGS.glob(stem + ".json"))
    return max(candidates, key=lambda item: item.stat().st_mtime_ns) if candidates else None


def check_record(key: str, stem: str, expected_uuid: str) -> dict:
    result = one_check(key, stem, expected_uuid)
    log_path = current_log(stem)
    result["source_log"] = file_record(log_path) if log_path else {
        "path": (LOGS / f"{stem}.json").relative_to(ROOT).as_posix(), "status": "missing"
    }
    result["source_native"] = [file_record(ROOT / path) for path in NATIVE_SOURCES[key]]

    if key == "schematic_erc" and log_path and result.get("status", "").startswith("completed"):
        try:
            payload = json.loads(log_path.read_text(encoding="utf-8"))
            findings = payload["result"].get("errors", [])
            details = []
            for finding in findings:
                primitives = finding.get("primitives", [])
                refs = sorted({p.get("name", "").split("(", 1)[0] for p in primitives if p.get("name")})
                details.append({
                    "type": finding.get("type", "unknown"),
                    "rule": finding.get("rule", "unknown"),
                    "primitive_count": len(primitives),
                    "references": refs,
                })
            result["erc_findings"] = details
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            result["erc_findings"] = []
    return result


def main() -> None:
    checks = {key: check_record(key, stem, uuid) for key, (stem, uuid) in CHECKS.items()}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    archive = {
        "schema": "easyeda-check-summary/v1",
        "snapshot_status": "current_draft",
        "snapshot_note": SNAPSHOT_NOTE,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": checks,
        "native_project": file_record(ROOT / NATIVE_PROJECT),
    }
    OUTPUT.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": OUTPUT.relative_to(ROOT).as_posix(), "schema": archive["schema"],
                      "snapshot_status": archive["snapshot_status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
