"""Quantize a compiled scene into portable integer arrays for small MCUs.

The editable JSON and full-precision Runtime remain the source of truth. This
module only produces derived data; it never changes geometry or electrical
order. All arrays use structure-of-arrays storage to avoid struct padding.
"""

from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Runtime


UINT16_MAX = 65535
UINT32_MAX = 4294967295
MAG_MISSING = -32768
POSITION_SCALE = 10
MAGNITUDE_SCALE = 100
U_DENOMINATOR = UINT16_MAX
LED_TYPES = {"hidden": 0, "star": 1, "edge": 2}

# Mapping order is also the deterministic C-header table order.
TABLE_TYPES = {
    "led_x_dm": "int16_t", "led_y_dm": "int16_t",
    "led_owner_type": "uint8_t", "led_owner_index": "uint16_t", "led_u16": "uint16_t",
    "star_hip": "uint32_t", "star_x_dm": "int16_t", "star_y_dm": "int16_t",
    "star_mag_centi": "int16_t", "star_led_offsets": "uint16_t",
    "star_led_counts": "uint16_t", "star_led_indices": "uint16_t",
    "edge_start_star": "uint16_t", "edge_end_star": "uint16_t",
    "edge_length_dm": "uint16_t", "edge_led_offsets": "uint16_t",
    "edge_led_counts": "uint16_t", "edge_led_indices": "uint16_t",
    "adjacency_offsets": "uint16_t", "adjacency_neighbor_star": "uint16_t",
    "adjacency_edge_index": "uint16_t",
}
_TYPE_BYTES = {"uint8_t": 1, "int16_t": 2, "uint16_t": 2, "uint32_t": 4}


def _integer(value, label, minimum=0, maximum=UINT16_MAX):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer in [{minimum}, {maximum}]: {value!r}")
    return value


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number: {value!r}")
    return float(value)


def _quantize(value, scale, minimum, maximum, label):
    value = _finite(value, label)
    scaled = value * scale
    if not math.isfinite(scaled):
        raise ValueError(f"{label} exceeds the quantized storage range")
    # Explicit rule also maps naturally to C round(), unlike Python's ties-even.
    encoded = math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)
    if not minimum <= encoded <= maximum:
        raise ValueError(f"{label} quantizes to {encoded}, outside [{minimum}, {maximum}]")
    return encoded, abs(encoded / scale - value)


def _identifier(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def pack_runtime(runtime: "Runtime") -> dict:
    """Return JSON-serializable integer tables and measured quantization errors.

    Positions/lengths use 0.1 mm; magnitudes use 0.01; u uses a normalized uint16
    with exact endpoints, i.e. u = stored / 65535, not stored / 65536. Rounding
    selects the nearest integer with half-way cases away from zero. Values are
    checked before conversion and never clamped. At most 65535 LEDs/stars/edges
    and adjacency entries are supported. Owner index 65535 means hidden;
    magnitude -32768 means missing. Real magnitudes cannot use that sentinel.

    Membership preserves serial indices and their original list order, including
    multiple disjoint pieces and reversed edges. CSR adjacency is undirected;
    each star's entries follow the original edge order.
    """
    led_count = _integer(runtime.led_count, "LED count")
    if led_count != len(runtime.leds):
        raise ValueError("LED count does not match runtime.leds")
    star_count = _integer(len(runtime.stars), "star count")
    edge_count = _integer(len(runtime.edges), "edge count")
    _integer(edge_count * 2, "adjacency entry count")
    tables = {name: [] for name in TABLE_TYPES}
    expected = {"star": [set() for _ in runtime.stars],
                "edge": [set() for _ in runtime.edges]}
    errors = {"max_abs_position_error_mm": 0.0, "max_position_distance_error_mm": 0.0,
              "max_edge_length_error_mm": 0.0, "max_magnitude_error": 0.0,
              "max_u_error": 0.0}

    def position(owner, prefix, label):
        encoded_x, error_x = _quantize(owner.x_mm, POSITION_SCALE, -32768, 32767, label + " x")
        encoded_y, error_y = _quantize(owner.y_mm, POSITION_SCALE, -32768, 32767, label + " y")
        tables[prefix + "_x_dm"].append(encoded_x)
        tables[prefix + "_y_dm"].append(encoded_y)
        errors["max_abs_position_error_mm"] = max(errors["max_abs_position_error_mm"], error_x, error_y)
        errors["max_position_distance_error_mm"] = max(
            errors["max_position_distance_error_mm"], math.hypot(error_x, error_y))

    for index, led in enumerate(runtime.leds):
        if _integer(led.index, f"LED {index} index") != index:
            raise ValueError("runtime.leds must use contiguous serial LED indices")
        if not isinstance(led.owner_type, str) or led.owner_type not in LED_TYPES:
            raise ValueError(f"LED {index} has an unknown owner type: {led.owner_type!r}")
        kind = led.owner_type
        if kind == "hidden":
            if led.owner_index != -1:
                raise ValueError(f"Hidden LED {index} must have owner_index=-1")
            owner_index = UINT16_MAX
        else:
            owner_index = _integer(led.owner_index, f"LED {index} owner index", maximum=UINT16_MAX - 1)
            if owner_index >= len(expected[kind]):
                raise ValueError(f"LED {index} refers to an invalid {kind} owner")
            expected[kind][owner_index].add(index)
        if kind == "edge":
            u = _finite(led.u, f"Edge LED {index} u")
            if not 0 <= u <= 1:
                raise ValueError(f"Edge LED {index} requires u in [0, 1]")
            encoded_u, error = _quantize(u, U_DENOMINATOR, 0, UINT16_MAX, f"LED {index} u")
            errors["max_u_error"] = max(errors["max_u_error"], error)
        else:
            if led.u is not None:
                raise ValueError(f"Non-edge LED {index} must have u=None")
            encoded_u = 0
        position(led, "led", f"LED {index}")
        tables["led_owner_type"].append(LED_TYPES[kind])
        tables["led_owner_index"].append(owner_index)
        tables["led_u16"].append(encoded_u)

    def members(owner, owner_index, kind):
        indices = list(owner.indices)
        _integer(len(indices), f"{kind} {owner.id} membership count")
        for index in indices:
            _integer(index, f"{kind} {owner.id} member index", maximum=UINT16_MAX - 1)
            if index >= led_count:
                raise ValueError(f"{kind} {owner.id} refers to an invalid LED")
        if len(indices) != len(set(indices)) or set(indices) != expected[kind][owner_index]:
            raise ValueError(f"{kind} {owner.id} membership does not match LED owners")
        flat = tables[kind + "_led_indices"]
        _integer(len(flat) + len(indices), f"{kind} flattened membership count")
        tables[kind + "_led_offsets"].append(len(flat))
        tables[kind + "_led_counts"].append(len(indices))
        flat.extend(indices)

    star_lookup = {}
    hips = set()
    for index, star in enumerate(runtime.stars):
        star_id = _identifier(star.id, "star ID")
        if star_id in star_lookup:
            raise ValueError(f"Duplicate star ID {star_id!r}")
        star_lookup[star_id] = index
        hip = _integer(star.hip, f"Star {star_id} HIP", minimum=1, maximum=UINT32_MAX)
        if hip in hips:
            raise ValueError(f"Duplicate HIP {hip}")
        hips.add(hip)
        tables["star_hip"].append(hip)
        position(star, "star", f"Star {star_id}")
        if star.mag_v is None:
            magnitude = MAG_MISSING
        else:
            magnitude, error = _quantize(star.mag_v, MAGNITUDE_SCALE, -32767, 32767,
                                         f"Star {star_id} magnitude")
            errors["max_magnitude_error"] = max(errors["max_magnitude_error"], error)
        tables["star_mag_centi"].append(magnitude)
        members(star, index, "star")

    adjacency = [[] for _ in runtime.stars]
    edge_ids, endpoint_pairs = set(), set()
    for index, edge in enumerate(runtime.edges):
        edge_id = _identifier(edge.id, "edge ID")
        if edge_id in edge_ids:
            raise ValueError(f"Duplicate edge ID {edge_id!r}")
        edge_ids.add(edge_id)
        _identifier(edge.start_id, f"Edge {edge_id} start ID")
        _identifier(edge.end_id, f"Edge {edge_id} end ID")
        if edge.start_id not in star_lookup or edge.end_id not in star_lookup:
            raise ValueError(f"Edge {edge_id} refers to an invalid star")
        start, end = star_lookup[edge.start_id], star_lookup[edge.end_id]
        pair = frozenset((start, end))
        if start == end or pair in endpoint_pairs:
            raise ValueError(f"Edge {edge_id} has a duplicate pair or identical endpoints")
        endpoint_pairs.add(pair)
        length = _finite(edge.length_mm, f"Edge {edge_id} length")
        if length < 0:
            raise ValueError(f"Edge {edge_id} length must be nonnegative")
        encoded_length, error = _quantize(length, POSITION_SCALE, 0, UINT16_MAX, f"Edge {edge_id} length")
        tables["edge_start_star"].append(start)
        tables["edge_end_star"].append(end)
        tables["edge_length_dm"].append(encoded_length)
        errors["max_edge_length_error_mm"] = max(errors["max_edge_length_error_mm"], error)
        members(edge, index, "edge")
        adjacency[start].append((end, index))
        adjacency[end].append((start, index))

    for neighbours in adjacency:
        tables["adjacency_offsets"].append(len(tables["adjacency_neighbor_star"]))
        for neighbour, edge_index in neighbours:
            tables["adjacency_neighbor_star"].append(neighbour)
            tables["adjacency_edge_index"].append(edge_index)
    tables["adjacency_offsets"].append(len(tables["adjacency_neighbor_star"]))
    counts = {"leds": led_count, "stars": star_count, "edges": edge_count,
              "star_led_indices": len(tables["star_led_indices"]),
              "edge_led_indices": len(tables["edge_led_indices"]),
              "adjacency_entries": len(tables["adjacency_neighbor_star"])}
    table_bytes = {name: len(values) * _TYPE_BYTES[TABLE_TYPES[name]] for name, values in tables.items()}
    c_arrays_bytes = sum(max(1, len(values)) * _TYPE_BYTES[TABLE_TYPES[name]] for name, values in tables.items())
    metadata = {**errors, "table_bytes": sum(table_bytes.values()), "table_bytes_by_name": table_bytes,
                "c_arrays_bytes": c_arrays_bytes, "rgb_frame_bytes": led_count * 3,
                "storage_note": "Array payload only; linker alignment and target flash placement are not included.",
                "coordinate_system": "x_right_y_down_mm"}
    result = {"schema_version": 1, "format": "constellation_compact_soa_v1", "counts": counts,
            "quantization": {"position_unit_mm": 0.1, "length_unit_mm": 0.1, "magnitude_unit": 0.01,
                             "u_denominator": U_DENOMINATOR, "rounding": "nearest_ties_away_from_zero",
                             "owner_none": UINT16_MAX, "mag_missing": MAG_MISSING},
            "table_types": dict(TABLE_TYPES), "tables": tables, "metadata": metadata}
    # Hash what the MCU actually consumes, including serial ordering. Cosmetic
    # names and floating-point authoring precision do not affect this identity.
    identity = {key: result[key] for key in ("format", "counts", "quantization", "tables")}
    metadata["scene_sha256"] = hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()
    return result


def _c_table(name, values):
    ctype = TABLE_TYPES[name]
    entries = values if values else [0]
    suffix = "u" if ctype.startswith("uint") else ""
    rows = [", ".join(f"{value}{suffix}" for value in entries[offset:offset + 12])
            for offset in range(0, len(entries), 12)]
    body = ",\n".join("    " + row for row in rows)
    if not values:
        body += " /* storage sentinel; logical count is zero */"
    return f"static const {ctype} constellation_compact_{name}[{len(entries)}] = {{\n{body}\n}};"


def export_compact_c(runtime: "Runtime", path: str | Path) -> None:
    """Export a checked integer-only C99/C++ header alongside the float header."""
    packed = pack_runtime(runtime)
    counts = packed["counts"]
    macros = {"LED_COUNT": counts["leds"], "STAR_COUNT": counts["stars"], "EDGE_COUNT": counts["edges"],
              "STAR_LED_INDEX_COUNT": counts["star_led_indices"],
              "EDGE_LED_INDEX_COUNT": counts["edge_led_indices"],
              "ADJACENCY_COUNT": counts["adjacency_entries"],
              "ADJACENCY_OFFSET_COUNT": counts["stars"] + 1,
              "POSITION_SCALE": POSITION_SCALE, "LENGTH_SCALE": POSITION_SCALE,
              "MAGNITUDE_SCALE": MAGNITUDE_SCALE, "U_DENOMINATOR": U_DENOMINATOR,
              "TABLE_BYTES": packed["metadata"]["table_bytes"],
              "C_ARRAYS_BYTES": packed["metadata"]["c_arrays_bytes"],
              "RGB_FRAME_BYTES": packed["metadata"]["rgb_frame_bytes"]}
    header = """/* Generated compact scene: structure-of-arrays, checked integer ranges.
 * Positions and lengths: stored / 10 millimetres; magnitude: stored / 100.
 * u: stored / 65535 (both endpoints exact); it is not a /65536 Q0.16 value.
 * Quantization: nearest integer, half-way cases away from zero; no clamping.
 * LED array index is the WS2812 serial address. Members need not be contiguous.
 * CSR neighbours for star s occupy [adjacency_offsets[s], offsets[s+1]).
 * Neighbour entries pair with adjacency_edge_index in original edge order.
 * Non-edge u is unused (0), hidden owner is UINT16_MAX, missing mag is INT16_MIN.
 * Array byte counts exclude linker alignment; flash/RAM placement is target-specific.
 * Empty arrays have one storage sentinel, which must not be iterated.
 * This header can coexist with the original float scene header.
 */
#ifndef CONSTELLATION_LAMP_COMPACT_SCENE_DATA_H
#define CONSTELLATION_LAMP_COMPACT_SCENE_DATA_H

#include <stdint.h>

#define CONSTELLATION_COMPACT_OWNER_NONE UINT16_MAX
#define CONSTELLATION_COMPACT_MAG_MISSING INT16_MIN
#define CONSTELLATION_COMPACT_LED_HIDDEN 0u
#define CONSTELLATION_COMPACT_LED_STAR 1u
#define CONSTELLATION_COMPACT_LED_EDGE 2u
"""
    header += "\n".join(f"#define CONSTELLATION_COMPACT_{name} {value}u" for name, value in macros.items())
    header += f'\n#define CONSTELLATION_COMPACT_SCENE_SHA256 "{packed["metadata"]["scene_sha256"]}"'
    header += "\n\n" + "\n\n".join(_c_table(name, values) for name, values in packed["tables"].items())
    header += "\n\n#endif /* CONSTELLATION_LAMP_COMPACT_SCENE_DATA_H */\n"
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(header, encoding="utf-8", newline="\n")
