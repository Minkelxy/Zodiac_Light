"""Check software, current hardware deliveries, templates and entry-point links."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def template_checks(root: Path) -> list[dict]:
    checks = []
    for name in ("output/pdf/placement-template-manifest.json",
                 "output/engraving-final-u1/fabrication-manifest.json"):
        try:
            manifest = json.loads((root / name).read_text(encoding="utf-8-sig"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("source_sha256"), dict):
                raise ValueError("Template manifest/source_sha256 must be objects")
            sources = dict(manifest["source_sha256"])
            if "art_source" in manifest:
                if not isinstance(manifest["art_source"], str):
                    raise ValueError("Template art_source must be a relative path string")
                sources[manifest["art_source"]] = manifest["art_sha256"]
            # Older placement metadata stores the author's absolute PDF path.
            if not isinstance(manifest.get("pdf"), str) or not manifest["pdf"]:
                raise ValueError("Template pdf must be a path string")
            pdf = root / "output/pdf" / manifest["pdf"].replace("\\", "/").split("/")[-1]
            sources[pdf.relative_to(root).as_posix()] = manifest["pdf_sha256"]
            for source, expected in sources.items():
                if (not isinstance(source, str) or not isinstance(expected, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", expected)):
                    raise ValueError("Template sources must map relative path strings to SHA-256 digests")
                path = root / source.replace("\\", "/")
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError(f"Source leaves the project: {source}")
                passed = sha256(path) == expected
                checks.append({"id": f"template:{source}", "passed": passed,
                               "detail": "SHA-256 matches the reviewed template source" if passed
                                         else "SHA-256 differs from the reviewed template source"})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks.append({"id": f"template:{name}", "passed": False, "detail": str(exc)})
    return checks


def link_checks(root: Path) -> list[dict]:
    """Check local targets in maintained navigation documents, without network access."""
    checks = []
    entries = [root / "README.md", root / "output/README.md",
               root / "hardware/nfc-talisman/README.md", *sorted((root / "docs").glob("*.md"))]
    pattern = re.compile(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)")
    for entry in entries:
        if not entry.is_file():
            checks.append({"id": f"links:{entry.relative_to(root)}", "passed": False,
                           "detail": "Missing navigation document"})
            continue
        source = re.sub(r"```.*?```", "", entry.read_text(encoding="utf-8-sig"), flags=re.S)
        missing = []
        for raw in pattern.findall(source):
            target = raw.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = entry.parent / unquote(parsed.path)
            if not path.exists():
                missing.append(target)
        checks.append({"id": f"links:{entry.relative_to(root).as_posix()}",
                       "passed": not missing, "detail": missing or "All local targets exist"})
    return checks


def validate(root: Path = ROOT, *, run_tests: bool = True) -> dict:
    root = root.resolve()
    checks = template_checks(root) + link_checks(root)
    hardware_path = root / "hardware/nfc-talisman/scripts/check_delivery.py"
    try:
        spec = importlib.util.spec_from_file_location("hardware_delivery", hardware_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        hardware = module.validate(root)
        checks.extend(hardware["checks"])
    except (OSError, ValueError, ImportError, AttributeError) as exc:
        hardware = {"status": "failed", "errors": [str(exc)]}
        checks.append({"id": "hardware-checker", "passed": False, "detail": str(exc)})
    budget_code = (
        "from pathlib import Path; "
        "from constellation_lamp.model import read_json,compile_layout; "
        "from constellation_lamp.hardware import HardwareProfile; "
        "d=Path('data'); "
        "r=compile_layout(read_json(d/'catalog.json'),read_json(d/'constellation.json'),read_json(d/'layout.json')); "
        "p=HardwareProfile.load(d/'hardware.json').validate_runtime(r); "
        "print(f'{r.led_count} LEDs, {p.current_limit_ma} mA budget, {p.fps} FPS: power/transport budgets passed')"
    )
    commands = [("lamp-layout", [sys.executable, "-m", "constellation_lamp", "validate"]),
                ("lamp-hardware-budget", [sys.executable, "-c", budget_code])]
    if run_tests:
        commands.append(("software-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"]))
    env = {**os.environ, "MPLBACKEND": "Agg", "PYTHONUTF8": "1"}
    for name, command in commands:
        print(f"Checking {name}...", flush=True)
        result = subprocess.run(command, cwd=root, env=env, text=True, encoding="utf-8",
                                errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(result.stdout.rstrip(), flush=True)
        checks.append({"id": name, "passed": result.returncode == 0,
                       "detail": result.stdout.strip()})
    errors = [check for check in checks if not check["passed"]]
    return {"status": "passed" if not errors else "failed", "checks": checks, "errors": errors,
            "hardware_release_status": hardware.get("release_status"),
            "limitations": hardware.get("limitations", []), "unittest_run": run_tests}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true", help="Skip unittest; keep all delivery checks")
    parser.add_argument("--output", type=Path, help="Write the JSON report")
    args = parser.parse_args()
    report = validate(run_tests=not args.skip_tests)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Project {report['status']}: {len(report['checks'])} checks, {len(report['errors'])} failures")
    for error in report["errors"]:
        print(f"FAIL {error['id']}: {error['detail']}")
    print(f"Hardware release status: {report['hardware_release_status']}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
