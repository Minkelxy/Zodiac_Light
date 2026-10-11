"""Package only this review's deliverables; never rewrite manufacturing exports."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manufacturing/improvement-review-v1"
DIRECTORIES = (
    "artwork/production-study-v1",
    "manufacturing/first-article-v1",
    "manufacturing/bom-erc-closeout-v1",
)
DOCUMENTS = (
    "README.md",
    "artwork/README.md",
    "artwork/horse-import-guide.md",
    "geometry/assembly-notes.md",
    "manufacturing/sample-test-plan.md",
    "manufacturing/material-and-finish-baseline.md",
    "manufacturing/improvement-review-2026-10-11.md",
    "manufacturing/bom-ready.csv",
    "manufacturing/bom-review.md",
    "electrical/assembly.md",
    "scripts/build_art_production_study.py",
    "scripts/build_improvement_review_pack.py",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = []
    for directory in DIRECTORIES:
        parent = ROOT / directory
        if not (parent / "README.md").is_file():
            raise FileNotFoundError(f"Missing deliverable: {directory}/README.md")
        paths.extend(p for p in parent.rglob("*") if p.is_file())
    for relative in DOCUMENTS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        paths.append(path)
    paths = sorted(set(paths))
    baseline = ROOT / "manufacturing/draft/export-manifest.json"
    frozen = json.loads(baseline.read_text(encoding="utf-8-sig"))
    preserved = []
    for item in frozen["files"] + frozen.get("derived_files", []):
        path = ROOT / item["path"]
        preserved.append({"path": item["path"], "sha256": sha(path),
                          "matches_baseline": sha(path) == item["sha256"]})
    if not all(item["matches_baseline"] for item in preserved):
        raise ValueError("Existing manufacturing baseline drifted; review before packaging")
    OUT.mkdir(parents=True, exist_ok=True)
    entry = OUT / "README.md"
    entry.write_text("""# 2026-10-11 NFC 符咒评审归档

本包包含实际尺寸图案校样、马面光路候选、首件装配与测试空模板，以及 C1 / ERC 核对资料。它是现有工程的补充评审包，不是制造下单包，也不包含完整原生工程、全部历史素材或现有 Gerber。关联历史资料的链接需要在 `hardware/nfc-talisman` 工程目录中查看。

- [本轮推进报告](../improvement-review-2026-10-11.md)
- [十二款实际尺寸校样](../../artwork/production-study-v1/index.html)
- [首件装配与测试记录](../first-article-v1/README.md)
- [C1 与 ERC 核对](../bom-erc-closeout-v1/README.md)
- [材料与外观基线](../material-and-finish-baseline.md)

`manifest.json` 记录包内文件字节数和 SHA-256，以及 28 项现有制造基线的只读核对结果。ZIP CRC、成员完整性与磁盘字节一致性记录在同目录的 `validation.json`；该验证文件在 ZIP 外保存，避免对 ZIP 自身哈希形成循环。校样 SVG 内嵌源 PNG 字节，源图没有修改；打印后仍须量 10 mm 标尺。实物结果全部留空。
""", encoding="utf-8")
    paths.append(entry)
    report = {
        "review_date_local": "2026-10-11",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "review_only_not_manufacturing_release",
        "scope": "Actual-size artwork proofs, optical candidates, first-article templates and BOM/ERC review. No physical or supplier acceptance is implied.",
        "manufacturing_baseline_manifest_sha256": sha(baseline),
        "preserved_manufacturing_baseline": preserved,
        "files": [{"path": p.relative_to(ROOT).as_posix(),
                   "bytes": p.stat().st_size, "sha256": sha(p)} for p in paths],
    }
    manifest = OUT / "manifest.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths.append(manifest)
    target = ROOT / "manufacturing/improvement-review-v1.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in paths:
            bundle.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as bundle:
        assert bundle.testzip() is None
        expected = {p.relative_to(ROOT).as_posix(): p for p in paths}
        assert set(bundle.namelist()) == set(expected)
        assert all(bundle.read(name) == path.read_bytes() for name, path in expected.items())
    validation = {"status": "pass", "files": len(paths), "zip_crc_verified": True,
                  "zip_matches_disk": True, "manufacturing_baseline_unchanged": True,
                  "zip_sha256": sha(target), "zip_bytes": target.stat().st_size,
                  "scope": "Package integrity only; no manufacturing, visual fidelity or physical acceptance."}
    (OUT / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False))


if __name__ == "__main__":
    main()
