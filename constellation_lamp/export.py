"""Export compiled scene data as standalone C99/C++ constant tables."""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Runtime


_UINT32_MAX = (1 << 32) - 1
_FLOAT32_MAX = 3.4028234663852886e38
_LED_TYPES = {"hidden": 0, "star": 1, "edge": 2}


def _u32(value: int, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _UINT32_MAX:
        raise ValueError(f"{label} must fit uint32_t: {value!r}")
    return f"{value}u"


def _float(value: float, label: str) -> str:
    number = float(value)
    if not math.isfinite(number) or abs(number) > _FLOAT32_MAX:
        raise ValueError(f"{label} must be a finite float32 value: {value!r}")
    literal = format(number, ".9g")
    if "." not in literal and "e" not in literal.lower():
        literal += ".0"
    return literal + "f"


def _table(ctype: str, name: str, rows: list[str], empty: str) -> str:
    # C99 and standard C++ forbid zero-length arrays. Counts remain zero; the
    # one-element sentinel is storage only and must never be iterated.
    body = rows if rows else [empty + " /* unused sentinel: logical count is zero */"]
    return (
        f"static const {ctype} {name}[{max(1, len(rows))}] = {{\n"
        + "\n".join(f"    {row}," for row in body)
        + "\n};"
    )


def _validate_members(runtime: "Runtime") -> None:
    if runtime.led_count != len(runtime.leds):
        raise ValueError("runtime.led_count does not match runtime.leds")
    _u32(runtime.led_count, "LED count")
    _u32(len(runtime.stars), "star count")
    _u32(len(runtime.edges), "edge count")
    for index, led in enumerate(runtime.leds):
        if led.index != index:
            raise ValueError("runtime.leds must be ordered by contiguous LED index")
        if led.owner_type not in _LED_TYPES:
            raise ValueError(f"Unknown LED owner type: {led.owner_type!r}")
        if led.owner_type == "hidden":
            continue
        owners = runtime.stars if led.owner_type == "star" else runtime.edges
        if not isinstance(led.owner_index, int) or not 0 <= led.owner_index < len(owners):
            raise ValueError(f"LED {index} refers to an invalid owner")
        if led.owner_type == "edge":
            if led.u is None or not math.isfinite(led.u) or not 0.0 <= led.u <= 1.0:
                raise ValueError(f"Edge LED {index} requires u in [0, 1]")
    for role, owners in (("star", runtime.stars), ("edge", runtime.edges)):
        for owner_index, owner in enumerate(owners):
            indices = owner.indices
            for index in indices:
                _u32(index, f"{role} {owner.id} membership index")
                if index >= runtime.led_count:
                    raise ValueError(f"{role} {owner.id} refers to an invalid LED")
            expected = {
                led.index for led in runtime.leds
                if led.owner_type == role and led.owner_index == owner_index
            }
            if len(set(indices)) != len(indices) or set(indices) != expected:
                raise ValueError(f"{role} {owner.id} membership does not match LED owners")


def export_c(runtime: "Runtime", path: str | Path) -> None:
    """Write runtime geometry and membership tables to a portable header.

    LED indices and table offsets use uint32_t. Membership arrays preserve the
    runtime's ordering and support multiple, reversed, or interleaved pieces.
    HIP IDs are required. Missing magnitudes are encoded as 0 with a validity
    flag, so firmware does not need to handle NaN values.
    """
    _validate_members(runtime)
    star_indices: list[int] = []
    edge_indices: list[int] = []
    star_rows: list[str] = []
    edge_rows: list[str] = []
    led_rows: list[str] = []
    star_lookup = {star.id: index for index, star in enumerate(runtime.stars)}
    if len(star_lookup) != len(runtime.stars):
        raise ValueError("Star IDs must be unique")

    for star in runtime.stars:
        offset = len(star_indices)
        star_indices.extend(star.indices)
        magnitude = "0.0f" if star.mag_v is None else _float(star.mag_v, "magnitude")
        fields = [
            _u32(star.hip, "HIP ID"),
            _float(star.x_mm, "star x"), _float(star.y_mm, "star y"),
            magnitude, "0u" if star.mag_v is None else "1u",
            _u32(offset, "star membership offset"),
            _u32(len(star.indices), "star membership count"),
        ]
        star_rows.append("{ " + ", ".join(fields) + " }")

    for edge in runtime.edges:
        if edge.start_id not in star_lookup or edge.end_id not in star_lookup:
            raise ValueError(f"Edge {edge.id} refers to an invalid star")
        offset = len(edge_indices)
        edge_indices.extend(edge.indices)
        fields = [
            _u32(star_lookup[edge.start_id], "edge start star"),
            _u32(star_lookup[edge.end_id], "edge end star"),
            _float(edge.length_mm, "edge length"),
            _u32(offset, "edge membership offset"),
            _u32(len(edge.indices), "edge membership count"),
        ]
        edge_rows.append("{ " + ", ".join(fields) + " }")

    for led in runtime.leds:
        fields = [
            _float(led.x_mm, "LED x"), _float(led.y_mm, "LED y"),
            _u32(_LED_TYPES[led.owner_type], "LED owner type"),
            "UINT32_MAX" if led.owner_type == "hidden" else _u32(led.owner_index, "LED owner"),
            _float(led.u if led.owner_type == "edge" else 0.0, "LED u"),
        ]
        led_rows.append("{ " + ", ".join(fields) + " }")

    tables = [
        _table("ConstellationLedInfo", "constellation_leds", led_rows,
               "{ 0.0f, 0.0f, CONSTELLATION_LED_HIDDEN, UINT32_MAX, 0.0f }"),
        _table("ConstellationStarInfo", "constellation_stars", star_rows,
               "{ 0u, 0.0f, 0.0f, 0.0f, 0u, 0u, 0u }"),
        _table("ConstellationEdgeInfo", "constellation_edges", edge_rows,
               "{ 0u, 0u, 0.0f, 0u, 0u }"),
        _table("uint32_t", "constellation_star_led_indices",
               [_u32(index, "star LED index") for index in star_indices], "0u"),
        _table("uint32_t", "constellation_edge_led_indices",
               [_u32(index, "edge LED index") for index in edge_indices], "0u"),
    ]
    header = """/* Generated constellation scene. All dimensions are millimetres.
 * LED array position is the physical WS2812 serial address.
 * Membership is addressed through offset/count and explicit index tables.
 * mag_v_valid == 0 means magnitude is unknown; non-edge u is unused (0).
 * Render into RGB[CONSTELLATION_LED_COUNT][3]; wire colour order belongs
 * in the hardware driver. Do not iterate storage sentinels when count is 0.
 * static const is safe to include in multiple C99/C++ translation units.
 * Actual flash/RAM placement depends on the target compiler and linker.
 */
#ifndef CONSTELLATION_LAMP_SCENE_DATA_H
#define CONSTELLATION_LAMP_SCENE_DATA_H

#include <stdint.h>

enum {
    CONSTELLATION_LED_HIDDEN = 0,
    CONSTELLATION_LED_STAR = 1,
    CONSTELLATION_LED_EDGE = 2
};

typedef struct {
    float x_mm;
    float y_mm;
    uint32_t owner_type;
    uint32_t owner_index;
    float u;
} ConstellationLedInfo;

typedef struct {
    uint32_t hip;
    float x_mm;
    float y_mm;
    float mag_v;
    uint8_t mag_v_valid;
    uint32_t led_offset;
    uint32_t led_count;
} ConstellationStarInfo;

typedef struct {
    uint32_t start_star;
    uint32_t end_star;
    float length_mm;
    uint32_t led_offset;
    uint32_t led_count;
} ConstellationEdgeInfo;

"""
    counts = {
        "CONSTELLATION_LED_COUNT": runtime.led_count,
        "CONSTELLATION_STAR_COUNT": len(runtime.stars),
        "CONSTELLATION_EDGE_COUNT": len(runtime.edges),
        "CONSTELLATION_STAR_LED_INDEX_COUNT": len(star_indices),
        "CONSTELLATION_EDGE_LED_INDEX_COUNT": len(edge_indices),
    }
    header += "\n".join(f"#define {name} {_u32(count, name)}" for name, count in counts.items())
    header += "\n\n" + "\n\n".join(tables) + "\n\n#endif /* CONSTELLATION_LAMP_SCENE_DATA_H */\n"
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(header, encoding="utf-8", newline="\n")
