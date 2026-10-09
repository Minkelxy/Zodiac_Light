"""Inspectable manufacturing and runtime exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .model import Runtime
from .geometry import footprint_bounds


def write_json(path: str | Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_reports(runtime: Runtime, output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "runtime.json", runtime.to_dict())
    with (output / "cutting.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["chain_order", "piece_id", "owner_type", "owner_id", "led_count", "cut_length_mm",
                         "first_index", "last_index", "reverse", "DIN_x_mm", "DIN_y_mm", "DOUT_x_mm", "DOUT_y_mm"])
        for order, piece in enumerate(runtime.pieces):
            din, dout = (piece.path_mm[-1], piece.path_mm[0]) if piece.reverse else (piece.path_mm[0], piece.path_mm[-1])
            writer.writerow([order, piece.id, piece.owner_type, piece.owner_id, piece.led_count,
                             f"{piece.cut_length_mm:.3f}", piece.first_index,
                             piece.first_index + piece.led_count - 1, piece.reverse,
                             *(f"{value:.3f}" for value in (*din, *dout))])
    with (output / "wiring.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["from_piece_DOUT", "to_piece_DIN", "from_x_mm", "from_y_mm", "to_x_mm", "to_y_mm",
                         "straight_distance_mm"])
        for link in runtime.wire_links:
            writer.writerow([link.from_piece, link.to_piece, *(f"{value:.3f}" for value in (*link.from_xy, *link.to_xy)),
                             f"{link.length_mm:.3f}"])


def summary(runtime: Runtime) -> str:
    physical = ""
    if runtime.layout.get("strip_width_mm"):
        a, b, c, d = footprint_bounds(runtime.pieces, runtime.layout["strip_width_mm"])
        physical = f"PCB footprint: {c - a:.1f} x {d - b:.1f} mm\n"
        if runtime.layout.get("panel"):
            panel = runtime.layout["panel"]
            physical += f"Panel limit: {panel['width_mm']:g} x {panel['height_mm']:g} mm\n"
        shift = runtime.layout.get("generation", {}).get("max_star_shift_mm", 0)
        physical += f"Maximum star-position adjustment: {shift:.2f} mm\n"
    return (f"{len(runtime.stars)} stars, {len(runtime.edges)} edges, {len(runtime.pieces)} strip pieces\n"
            f"{runtime.led_count} LEDs | pitch {runtime.pitch_mm:g} mm | cut unit {runtime.cut_unit_leds} LEDs\n"
            f"Star-centre bounds: {runtime.width_mm:g} x {runtime.height_mm:.1f} mm\n"
            + physical +
            f"Total strip: {runtime.led_count * runtime.pitch_mm / 1000:.3f} m\n"
            f"RGB frame buffer: {runtime.led_count * 3} bytes\n"
            f"Backside wire links: {len(runtime.wire_links)} "
            f"(straight-distance total {sum(link.length_mm for link in runtime.wire_links) / 1000:.3f} m; allow routing slack)")
