#!/usr/bin/env python3
"""Create strict single-ink PNGs while preserving source alpha and geometry."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "artwork" / "reference-collection"
SOURCE_DIR = COLLECTION / "talisman-monochrome-v1"
OUT_DIR = COLLECTION / "talisman-single-ink-v1"
ARTWORK_DIR = ROOT / "artwork"
ZIP_PATH = ARTWORK_DIR / "talisman-single-ink-v1.zip"
MANIFEST_PATH = SOURCE_DIR / "manifest.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    if len(value) != 6:
        raise ValueError(f"Expected six-digit ink color, got {value!r}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def bbox_from_alpha(alpha: bytes, width: int, height: int) -> list[int] | None:
    im = Image.frombytes("L", (width, height), alpha)
    box = im.getbbox()
    return list(box) if box else None


def make_contact_sheet(entries: list[dict[str, Any]], path: Path) -> None:
    cols, rows = 4, (len(entries) + 3) // 4
    cell_w, image_h, label_h, pad = 270, 270, 42, 18
    sheet = Image.new("RGB", (pad + cols * (cell_w + pad), pad + rows * (image_h + label_h + pad)), "#f3f1ed")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
    for index, entry in enumerate(entries):
        image = Image.open(OUT_DIR / Path(entry["path"]).name).convert("RGBA")
        image.thumbnail((cell_w, image_h), Image.Resampling.LANCZOS)
        x = pad + (index % cols) * (cell_w + pad) + (cell_w - image.width) // 2
        y = pad + (index // cols) * (image_h + label_h + pad) + (image_h - image.height) // 2
        sheet.paste(image, (x, y), image.getchannel("A"))
        label_y = pad + (index // cols) * (image_h + label_h + pad) + image_h + 4
        draw.text((pad + (index % cols) * (cell_w + pad), label_y), f"{entry['animal_zh']}  {entry['animal_en']}  {entry['ink_hex']}", fill="#242424", font=font)
    sheet.save(path, format="JPEG", quality=92, subsampling=0)


def main() -> int:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(MANIFEST_PATH)
    source_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    source_entries = source_manifest.get("files", [])
    if len(source_entries) != 12:
        raise ValueError(f"Expected 12 source entries, got {len(source_entries)}")
    originals = json.loads((COLLECTION / 'source-talisman/source_manifest.json').read_text(encoding='utf-8-sig'))
    if {entry['id'] for entry in source_entries} != {entry['id'] for entry in originals['files']}:
        raise ValueError('Candidate ids do not match the twelve original talismans')
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "title": "十二符咒 · 严格单色候选 · v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "user_approved_rgb_normalization_date": "2026-10-11",
        "method": "Native ImageGen redraw followed by layout candidate normalization; Python changes RGB only for pixels with alpha > 0 to the specified ink_hex. Alpha bytes, geometry, transparent gaps, hatch lines and framing are preserved. No programmatic drawing, denoising, thresholding, resizing or rotation.",
        "canvas_px": [1024, 1024],
        "candidate_count": 12,
        "strict_single_ink_pass_count": 0,
        "visual_release_status": "Draft pending human visual fidelity review; RGB normalization does not establish visual fidelity.",
        "files": [],
    }
    validation_files: list[dict[str, Any]] = []
    source_snapshots: dict[Path, str] = {}

    for entry in source_entries:
        animal_id = entry["id"]
        candidate_rel = entry["path"]
        candidate_path = COLLECTION / candidate_rel
        candidate_hash = file_sha256(candidate_path)
        if candidate_hash != entry["output_sha256"]:
            raise ValueError(f"Candidate hash mismatch for {animal_id}: manifest {entry['output_sha256']} vs actual {candidate_hash}")
        original_path = COLLECTION / entry["source_path"]
        original_hash = file_sha256(original_path)
        if original_hash != entry["source_sha256"]:
            raise ValueError(f"Original source hash mismatch for {animal_id}: manifest {entry['source_sha256']} vs actual {original_hash}")
        source_snapshots[candidate_path] = candidate_hash
        source_snapshots[original_path] = original_hash

        ink_hex = entry["ink_hex"].upper()
        ink = hex_rgb(ink_hex)
        with Image.open(candidate_path) as opened:
            if opened.mode != "RGBA":
                raise ValueError(f"{animal_id}: expected RGBA, found {opened.mode}")
            if opened.size != (1024, 1024):
                raise ValueError(f"{animal_id}: expected 1024x1024, found {opened.size}")
            original_bytes = opened.tobytes()
        alpha_before = bytes(original_bytes[3::4])
        bbox_before = bbox_from_alpha(alpha_before, 1024, 1024)
        out_bytes = bytearray(original_bytes)
        for p in range(0, len(out_bytes), 4):
            if out_bytes[p + 3] != 0:
                out_bytes[p] = ink[0]
                out_bytes[p + 1] = ink[1]
                out_bytes[p + 2] = ink[2]
        output_path = OUT_DIR / f"{animal_id}-single-ink.png"
        Image.frombytes("RGBA", (1024, 1024), bytes(out_bytes)).save(output_path, format="PNG", optimize=False)

        with Image.open(output_path) as result:
            if result.mode != "RGBA" or result.size != (1024, 1024):
                raise AssertionError(f"{animal_id}: output format/dimensions mismatch")
            result_bytes = result.tobytes()
        alpha_after = bytes(result_bytes[3::4])
        bbox_after = bbox_from_alpha(alpha_after, 1024, 1024)
        visible_rgb = {tuple(result_bytes[p : p + 3]) for p in range(0, len(result_bytes), 4) if result_bytes[p + 3] > 0}
        alpha_same = alpha_before == alpha_after
        rgb_pass = visible_rgb == {ink}
        bbox_same = bbox_before == bbox_after
        if not (alpha_same and rgb_pass and bbox_same):
            raise AssertionError(f"{animal_id}: validation failed (alpha={alpha_same}, rgb={rgb_pass}, bbox={bbox_same})")
        validation_files.append({
            "id": animal_id,
            "mode_rgba_1024": True,
            "alpha_bytes_unchanged": alpha_same,
            "all_nontransparent_rgb_equals_ink": rgb_pass,
            "visible_bbox_unchanged": bbox_same,
            "visible_bbox_xyxy": bbox_after,
            "distinct_nontransparent_rgb_count": len(visible_rgb),
        })
        manifest["files"].append({
            "id": animal_id,
            "animal_zh": entry["animal_zh"],
            "animal_en": entry["animal_en"],
            "path": f"talisman-single-ink-v1/{output_path.name}",
            "dimensions": [1024, 1024],
            "output_sha256": file_sha256(output_path),
            "source_path": entry["source_path"],
            "source_sha256": original_hash,
            "candidate_path": candidate_rel,
            "candidate_sha256": candidate_hash,
            "ink_hex": ink_hex,
            "canvas_px": [1024, 1024],
            "provenance": {
                "prompt_ref": entry.get("prompt_path"),
                "generation_ref": entry.get("generation_path"),
                "native_ref": entry.get("native_path"),
                "method_ref": "talisman-monochrome-v1/manifest.json",
            },
            "visual_status": entry.get("visual_status", "native_draft_pending_review"),
            "visual_note": entry.get("visual_note", ""),
        })

    manifest["strict_single_ink_pass_count"] = len(validation_files)
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    contact_path = OUT_DIR / "contact-sheet.jpg"
    make_contact_sheet(manifest["files"], contact_path)

    readme_lines = [
        "# 十二符咒严格单色候选 v1",
        "",
        "2026-10-11：用户批准仅统一可见像素 RGB 为每张指定主色。处理顺序为原生 ImageGen 重绘 → 布局候选 → 固定 RGB。Python 仅替换 alpha > 0 像素的 RGB；alpha、轮廓、留白、排线和画布位置逐字节保留。这是色值归一化，不是程序重绘。",
        "",
        "已逐张检查主体、朝向、主要分段与透明负形；造型仍是参考修复稿。牛脸、龙角、虎条纹、猴的笔画及其他局部差异见 [逐张复核](../talisman-monochrome-v1/visual-review.md)。颜色通过不代表图形已获最终视觉批准。原生绘制来源与完整提示词见 [候选清单](../talisman-monochrome-v1/manifest.json)、[提示词](../talisman-monochrome-v1/prompts.json)。",
        "",
        "## PNG 下载",
        "",
    ]
    for entry in manifest["files"]:
        readme_lines.append(f"- [{entry['animal_zh']} {entry['animal_en']}（{entry['ink_hex']}）]({Path(entry['path']).name})")
    readme_lines += ["", "Contact sheet: [contact-sheet.jpg](contact-sheet.jpg)", ""]
    readme_path = OUT_DIR / "README.md"
    readme_path.write_text("\n".join(readme_lines), encoding="utf-8")

    source_unchanged = all(file_sha256(path) == digest for path, digest in source_snapshots.items())
    validation = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "files_checked": len(validation_files),
        "exact_rgb_pass_count": sum(f["all_nontransparent_rgb_equals_ink"] for f in validation_files),
        "alpha_unchanged_count": sum(f["alpha_bytes_unchanged"] for f in validation_files),
        "visible_bbox_unchanged_count": sum(f["visible_bbox_unchanged"] for f in validation_files),
        "source_hashes_unchanged": source_unchanged,
        "validation_scope": "RGBA mode and 1024x1024 dimensions, exact per-pixel alpha byte equality, specified RGB for every alpha>0 pixel, unchanged nontransparent bounding box, and unchanged source hashes.",
        "files": validation_files,
    }
    if not source_unchanged:
        raise AssertionError("At least one source file changed during processing")
    if validation["exact_rgb_pass_count"] != 12 or validation["alpha_unchanged_count"] != 12 or validation["visible_bbox_unchanged_count"] != 12:
        raise AssertionError("Expected all 12 images to pass strict single-ink validation")
    validation_path = OUT_DIR / "validation.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    archive_members = [*(OUT_DIR / f"{e['id']}-single-ink.png" for e in manifest["files"]), manifest_path, validation_path, readme_path, contact_path]
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in archive_members:
            zf.write(path, arcname=path.name)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise AssertionError(f"ZIP CRC failure at {bad}")
        if set(zf.namelist()) != {p.name for p in archive_members}:
            raise AssertionError("ZIP member set differs from expected files")
        for path in archive_members:
            if zf.read(path.name) != path.read_bytes():
                raise AssertionError(f"ZIP byte-for-byte verification failed for {path.name}")
    validation["zip_crc_pass"] = True
    validation["zip_byte_for_byte_pass"] = True
    validation["zip_path"] = str(ZIP_PATH)
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Refresh the ZIP after recording its successful verification in validation.json.
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in archive_members:
            zf.write(path, arcname=path.name)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        if zf.testzip() is not None or any(zf.read(path.name) != path.read_bytes() for path in archive_members):
            raise AssertionError("Refreshed ZIP failed CRC or byte-for-byte verification")
    print(json.dumps({
        "output_dir": str(OUT_DIR),
        "zip_path": str(ZIP_PATH),
        "exact_rgb_pass_count": validation["exact_rgb_pass_count"],
        "alpha_unchanged_count": validation["alpha_unchanged_count"],
        "visible_bbox_unchanged_count": validation["visible_bbox_unchanged_count"],
        "source_hashes_unchanged": source_unchanged,
        "zip_crc_pass": True,
        "zip_byte_for_byte_pass": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
