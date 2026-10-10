"""Verify archived draft hashes and unchanged CAM-review layer contents."""
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'manufacturing/draft/export-manifest.json').read_text(encoding='utf-8'))
    checks = []
    for item in manifest['files'] + manifest.get('derived_files', []):
        path = ROOT / item['path']
        data = path.read_bytes() if path.is_file() else None
        checks.append({'path': item['path'], 'passed': data is not None
                       and len(data) == item['bytes']
                       and hashlib.sha256(data).hexdigest() == item['sha256']})
    summary = json.loads((ROOT / 'eda/check-summary.json').read_text(encoding='utf-8'))
    for check in summary['checks'].values():
        for item in [check['source_log']] + check.get('source_native', []):
            path = ROOT / item['path']
            data = path.read_bytes() if path.is_file() else None
            checks.append({'path': item['path'], 'passed': data is not None
                           and len(data) == item['size_bytes']
                           and hashlib.sha256(data).hexdigest() == item['sha256']})
    cam = json.loads((ROOT / 'manufacturing/draft/cam-package-manifest.json').read_text(encoding='utf-8'))
    raw_path = ROOT / manifest['files'][0]['path']
    checks.append({'path': 'CAM source ZIP hash', 'passed': hashlib.sha256(raw_path.read_bytes()).hexdigest() == cam['source_sha256']})
    with zipfile.ZipFile(raw_path) as raw, zipfile.ZipFile(ROOT / cam['path']) as review:
        checks.append({'path': 'ZIP CRC', 'passed': raw.testzip() is None and review.testzip() is None})
        checks.append({'path': 'CAM member list', 'passed': sorted(review.namelist()) == sorted(cam['zip_entries'])})
        checks.append({'path': 'Duplicate PTH excluded', 'passed': cam['excluded_duplicate_drill'] not in review.namelist()})
        for name in review.namelist():
            checks.append({'path': name, 'passed': name in raw.namelist() and review.read(name) == raw.read(name)})
    passed = all(item['passed'] for item in checks)
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'archived_draft_integrity_pass' if passed else 'integrity_failure',
              'passed': passed, 'checks': checks,
              'limitations': ['Checks archived files only; does not inspect unsaved live EasyEDA changes.',
                              'No new native ERC/DRC run, CAM process approval or physical acceptance.']}
    target = ROOT / 'manufacturing/draft/delivery-integrity.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': passed, 'checks': len(checks), 'failures': [x for x in checks if not x['passed']]}))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
