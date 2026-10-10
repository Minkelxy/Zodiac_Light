#!/usr/bin/env python3
"""Read-only pixel audit for the 12 restored talisman PNGs.

The only file this script writes is the JSON report selected with --output.
It never modifies source or restored PNG files.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image
from PIL import ImageFilter


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_image(collection_root: Path, entry: dict) -> dict:
    restored_path = collection_root / entry["path"]
    source_path = collection_root / entry["source_path"]
    with Image.open(restored_path) as image:
        source_mode = image.mode
        rgba = image.convert("RGBA")
        width, height = rgba.size
        alpha = rgba.getchannel("A")
        alpha_extrema = list(alpha.getextrema())
        pixels = rgba.load()

        foreground_mask = alpha.point(lambda value: 255 if value >= 8 else 0)
        interior_mask = foreground_mask.filter(ImageFilter.MinFilter(5))
        interior_pixels = interior_mask.load()

        corners = {
            "top_left": pixels[0, 0][3] == 0,
            "top_right": pixels[width - 1, 0][3] == 0,
            "bottom_left": pixels[0, height - 1][3] == 0,
            "bottom_right": pixels[width - 1, height - 1][3] == 0,
        }

        opaque_rgb: Counter[tuple[int, int, int]] = Counter()
        interior_partial_alpha: Counter[int] = Counter()
        visible_quantized: set[tuple[int, int, int]] = set()
        opaque_pixels = 0
        visible_pixels = 0
        partial_alpha_pixels = 0
        interior_foreground_pixels = 0
        for y in range(height):
            for x in range(width):
                red, green, blue, opacity = pixels[x, y]
                if opacity == 255:
                    opaque_pixels += 1
                    opaque_rgb[(red, green, blue)] += 1
                if 1 <= opacity <= 254:
                    partial_alpha_pixels += 1
                if opacity > 0:
                    visible_pixels += 1
                    visible_quantized.add((red // 16, green // 16, blue // 16))
                if interior_pixels[x, y] == 255:
                    interior_foreground_pixels += 1
                    if 1 <= opacity <= 254:
                        interior_partial_alpha[opacity] += 1

    actual_source_sha = sha256(source_path)
    actual_restored_sha = sha256(restored_path)
    common_colors = sorted(opaque_rgb.items(), key=lambda item: (-item[1], item[0]))[:8]
    return {
        "id": entry["id"],
        "animal_zh": entry.get("animal_zh"),
        "source_path": entry["source_path"],
        "restored_path": entry["path"],
        "restored_png": {
            "mode": source_mode,
            "pixel_analysis_mode": "RGBA",
            "size_px": [width, height],
            "alpha_extrema": alpha_extrema,
            "clear_corners_alpha_zero": corners,
            "opaque_pixel_count": opaque_pixels,
            "partial_alpha_pixel_count_alpha_1_to_254": partial_alpha_pixels,
            "interior_alpha_ge_8_mask_eroded_5x5": {
                "interior_foreground_pixel_count": interior_foreground_pixels,
                "partial_alpha_pixel_count_alpha_1_to_254": sum(interior_partial_alpha.values()),
                "partial_alpha_fraction_of_interior_foreground": (
                    sum(interior_partial_alpha.values()) / interior_foreground_pixels
                    if interior_foreground_pixels else None
                ),
                "most_common_partial_alpha_values": [
                    {"alpha": opacity, "pixel_count": count}
                    for opacity, count in sorted(
                        interior_partial_alpha.items(), key=lambda item: (-item[1], item[0])
                    )[:8]
                ],
            },
            "opaque_distinct_rgb_count": len(opaque_rgb),
            "opaque_rgb_top_8": [
                {"rgb": list(rgb), "pixel_count": count}
                for rgb, count in common_colors
            ],
            "visible_pixel_count_alpha_gt_zero": visible_pixels,
            "quantized_rgb_16_levels_per_channel_distinct_count_alpha_gt_zero": len(visible_quantized),
            "sha256": actual_restored_sha,
            "manifest_sha256": entry.get("output_sha256"),
            "manifest_hash_matches": actual_restored_sha == entry.get("output_sha256"),
        },
        "source_png": {
            "sha256": actual_source_sha,
            "manifest_sha256": entry.get("source_sha256"),
            "manifest_hash_matches": actual_source_sha == entry.get("source_sha256"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    collection_root = manifest_path.parent.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest["files"]
    if len(entries) != 12:
        raise SystemExit(f"Expected 12 manifest entries; found {len(entries)}")

    records = [audit_image(collection_root, entry) for entry in entries]
    all_source_hashes_match = all(record["source_png"]["manifest_hash_matches"] for record in records)
    all_restored_hashes_match = all(record["restored_png"]["manifest_hash_matches"] for record in records)
    unique_ids = len({record["id"] for record in records}) == 12
    all_native_rgba = all(record["restored_png"]["mode"] == "RGBA" for record in records)
    all_1024_square = all(record["restored_png"]["size_px"] == [1024, 1024] for record in records)
    all_alpha_extrema_valid = all(record["restored_png"]["alpha_extrema"] == [0, 255] for record in records)
    all_corners_clear = all(
        all(record["restored_png"]["clear_corners_alpha_zero"].values()) for record in records
    )
    all_file_layout_passed = all((
        len(entries) == 12,
        unique_ids,
        all_native_rgba,
        all_1024_square,
        all_alpha_extrema_valid,
        all_corners_clear,
        all_source_hashes_match,
        all_restored_hashes_match,
    ))
    report = {
        "audit": "restored-v1 PNG pixel/color audit",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "manifest_entry_count": len(entries),
        "all_file_layout_passed": all_file_layout_passed,
        "file_layout_checks": {
            "exactly_12_manifest_entries": len(entries) == 12,
            "12_unique_ids": unique_ids,
            "native_png_mode_rgba": all_native_rgba,
            "size_1024_by_1024": all_1024_square,
            "alpha_extrema_0_to_255": all_alpha_extrema_valid,
            "all_four_corners_alpha_zero": all_corners_clear,
            "all_source_hashes_match_manifest": all_source_hashes_match,
            "all_restored_hashes_match_manifest": all_restored_hashes_match,
        },
        "all_source_hashes_match_manifest": all_source_hashes_match,
        "all_restored_hashes_match_manifest": all_restored_hashes_match,
        "partial_alpha_interpretation": (
            "The count of alpha 1..254 pixels includes both edge antialiasing and possible interior "
            "transparency. The interior statistic erodes the alpha>=8 foreground mask with a 5x5 "
            "minimum filter and counts partial-alpha pixels remaining within that eroded mask. "
            "This helps distinguish transparency extending into interiors from edge-only coverage, "
            "but does not establish visual fidelity or intended layer semantics."
        ),
        "color_interpretation": (
            "The restored drafts contain multiple opaque RGB values and, where the counts show it, "
            "many quantized RGB bins from colored fills, shading and gradients. A strict single-ink "
            "output should use one fixed RGB value for every nontransparent pixel; transparency and "
            "partial alpha may preserve negative space and antialiased edges, but must not encode "
            "additional ink colors or gray/color shading."
        ),
        "quantization_definition": (
            "For each visible pixel (alpha > 0), quantize each RGB channel by floor(channel / 16); "
            "the reported count is the number of distinct resulting RGB triplets."
        ),
        "files": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output.resolve()),
        "entries": len(records),
        "all_source_hashes_match_manifest": all_source_hashes_match,
        "all_restored_hashes_match_manifest": all_restored_hashes_match,
        "all_file_layout_passed": all_file_layout_passed,
        "opaque_distinct_rgb_counts": {
            record["id"]: record["restored_png"]["opaque_distinct_rgb_count"]
            for record in records
        },
        "quantized_16_level_color_counts": {
            record["id"]: record["restored_png"]["quantized_rgb_16_levels_per_channel_distinct_count_alpha_gt_zero"]
            for record in records
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
