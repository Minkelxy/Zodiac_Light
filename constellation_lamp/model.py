"""Validate authoring data and compile electrical order into physical LED records.

All geometry uses millimetres, x right and y down. Strip paths describe cut
boundaries; LEDs are sampled half a pitch in from those boundaries.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .geometry import footprint_bounds, validate_panel


class ValidationError(ValueError):
    """Invalid source data or an impossible physical layout."""


@dataclass(frozen=True)
class Led:
    index: int
    piece_id: str
    x_mm: float
    y_mm: float
    owner_type: str
    owner_index: int
    u: float | None


@dataclass(frozen=True)
class Star:
    id: str
    hip: int
    name: str
    x_mm: float
    y_mm: float
    mag_v: float | None
    indices: tuple[int, ...]


@dataclass(frozen=True)
class Edge:
    id: str
    start_id: str
    end_id: str
    length_mm: float
    indices: tuple[int, ...]
    path_mm: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Piece:
    id: str
    owner_type: str
    owner_id: str | None
    led_count: int
    path_mm: tuple[tuple[float, float], ...]
    first_index: int
    reverse: bool
    cut_length_mm: float
    indices: tuple[int, ...]


@dataclass(frozen=True)
class WireLink:
    from_piece: str
    to_piece: str
    from_xy: tuple[float, float]
    to_xy: tuple[float, float]
    length_mm: float


@dataclass(frozen=True)
class Runtime:
    leds: tuple[Led, ...]
    stars: tuple[Star, ...]
    edges: tuple[Edge, ...]
    pieces: tuple[Piece, ...]
    wire_links: tuple[WireLink, ...]
    pitch_mm: float
    cut_unit_leds: int
    width_mm: float
    height_mm: float
    layout: dict[str, Any]

    @property
    def led_count(self) -> int:
        return len(self.leds)

    @property
    def density_leds_per_m(self) -> float:
        return 1000.0 / self.pitch_mm

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("layout")
        result["schema_version"] = 1
        result["led_count"] = self.led_count
        result["rgb_buffer_bytes"] = self.led_count * 3
        result["total_strip_length_mm"] = self.led_count * self.pitch_mm
        if self.layout.get("strip_width_mm"):
            result["strip_width_mm"] = self.layout["strip_width_mm"]
            result["pcb_bounds_mm"] = footprint_bounds(self.pieces, self.layout["strip_width_mm"])
        if self.layout.get("panel"):
            result["panel"] = self.layout["panel"]
        return result


def read_json(path: str | Path) -> dict:
    try:
        with Path(path).open(encoding="utf-8-sig") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"Cannot read {path}: {error}") from error
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        raise ValidationError(f"{path}: expected an object with schema_version=1")
    return data


def number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label}: expected a finite number")
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValidationError(f"{label}: expected a {'positive ' if positive else ''}finite number")
    return value


def count(value: Any, label: str, unit: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value % unit:
        raise ValidationError(f"{label}: expected a positive integer divisible by {unit}")
    return value


def records(data: dict, key: str, label: str) -> list[dict]:
    value = data.get(key)
    if not isinstance(value, list) or not value or any(not isinstance(row, dict) for row in value):
        raise ValidationError(f"{label}.{key}: expected a non-empty list of objects")
    return value


def identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label}: expected a non-empty string")
    return value


def point(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValidationError(f"{label}: expected [x, y]")
    return number(value[0], label + ".x"), number(value[1], label + ".y")


def path(value: Any, label: str) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValidationError(f"{label}: expected at least two points")
    result = tuple(point(p, label) for p in value)
    if any(math.dist(a, b) <= 1e-8 for a, b in zip(result, result[1:])):
        raise ValidationError(f"{label}: adjacent path points must differ")
    return result


def path_length(points) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def sample_path(points, distance: float) -> tuple[float, float]:
    remaining = distance
    for a, b in zip(points, points[1:]):
        length = math.dist(a, b)
        if remaining <= length + 1e-9:
            t = min(1.0, max(0.0, remaining / length))
            return a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        remaining -= length
    return tuple(points[-1])


def project_path(points, xy) -> tuple[float, float]:
    """Return arclength and perpendicular distance to the nearest path segment."""
    best = (float("inf"), 0.0)
    offset = 0.0
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        t = min(1.0, max(0.0, ((xy[0] - a[0]) * dx + (xy[1] - a[1]) * dy) / (length * length)))
        projection = (a[0] + t * dx, a[1] + t * dy)
        candidate = (math.dist(xy, projection), offset + t * length)
        if candidate < best:
            best = candidate
        offset += length
    return best[1], best[0]


def validate_sources(catalog: dict, constellation: dict):
    for label, data in (("catalog", catalog), ("constellation", constellation)):
        if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
            raise ValidationError(f"{label}: unsupported schema_version")
    catalog_by_hip = {}
    for row in records(catalog, "stars", "catalog"):
        hip = count(row.get("hip"), "catalog.hip")
        if hip in catalog_by_hip:
            raise ValidationError(f"Duplicate catalog HIP {hip}")
        ra = number(row.get("ra_deg"), f"HIP {hip}.ra_deg")
        dec = number(row.get("dec_deg"), f"HIP {hip}.dec_deg")
        if not 0 <= ra < 360 or not -90 <= dec <= 90:
            raise ValidationError(f"HIP {hip}: sky coordinates out of range")
        if row.get("mag_v") is not None:
            number(row["mag_v"], f"HIP {hip}.mag_v")
        catalog_by_hip[hip] = row
    nodes = records(constellation, "stars", "constellation")
    node_ids = set()
    node_hips = set()
    for row in nodes:
        star_id = identifier(row.get("id"), "star.id")
        hip = count(row.get("hip"), f"{star_id}.hip")
        if star_id in node_ids or hip in node_hips:
            raise ValidationError(f"Duplicate star ID or HIP: {star_id}")
        if hip not in catalog_by_hip:
            raise ValidationError(f"{star_id}: HIP {hip} missing from catalog")
        point(row.get("reference_px"), f"{star_id}.reference_px")
        node_ids.add(star_id)
        node_hips.add(hip)
    edges = records(constellation, "edges", "constellation")
    edge_ids, endpoint_pairs = set(), set()
    for row in edges:
        edge_id = identifier(row.get("id"), "edge.id")
        start = identifier(row.get("start"), f"{edge_id}.start")
        end = identifier(row.get("end"), f"{edge_id}.end")
        if start not in node_ids or end not in node_ids or start == end:
            raise ValidationError(f"{edge_id}: endpoints must be two existing, distinct stars")
        pair = frozenset((start, end))
        if edge_id in edge_ids or pair in endpoint_pairs:
            raise ValidationError(f"Duplicate edge ID or endpoint pair: {edge_id}")
        edge_ids.add(edge_id)
        endpoint_pairs.add(pair)
    return catalog_by_hip, nodes, edges


def compile_layout(catalog: dict, constellation: dict, layout: dict) -> Runtime:
    catalog_by_hip, nodes, edge_rows = validate_sources(catalog, constellation)
    if type(layout.get("schema_version")) is not int or layout.get("schema_version") != 1:
        raise ValidationError("layout: unsupported schema_version")
    density = number(layout.get("density_leds_per_m"), "density_leds_per_m", positive=True)
    pitch = 1000.0 / density
    cut_unit = count(layout.get("cut_unit_leds"), "cut_unit_leds")
    width = number(layout.get("width_mm"), "width_mm", positive=True)
    height = number(layout.get("height_mm"), "height_mm")
    if height < 0:
        raise ValidationError("height_mm must be nonnegative")
    positions = layout.get("star_positions_mm")
    expected_ids = {node["id"] for node in nodes}
    if not isinstance(positions, dict) or set(positions) != expected_ids:
        raise ValidationError("star_positions_mm must contain exactly the selected star IDs")
    positions = {key: point(value, f"{key}.position") for key, value in positions.items()}
    actual_width = max(p[0] for p in positions.values()) - min(p[0] for p in positions.values())
    actual_height = max(p[1] for p in positions.values()) - min(p[1] for p in positions.values())
    if abs(actual_width - width) > 1e-3 or abs(actual_height - height) > 1e-3:
        raise ValidationError("width_mm/height_mm do not match saved star_positions_mm. "
                              "Regenerate with the layout command or update all physical geometry consistently.")
    star_indexes = {row["id"]: i for i, row in enumerate(nodes)}
    edge_indexes = {row["id"]: i for i, row in enumerate(edge_rows)}
    supplied_paths = layout.get("edge_paths_mm", {})
    if not isinstance(supplied_paths, dict) or set(supplied_paths) - set(edge_indexes):
        raise ValidationError("edge_paths_mm contains an unknown edge ID")
    edge_paths = {}
    for row in edge_rows:
        edge_id, a, b = row["id"], positions[row["start"]], positions[row["end"]]
        points = path(supplied_paths.get(edge_id, [a, b]), f"{edge_id}.path")
        if math.dist(points[0], a) > 1e-5 or math.dist(points[-1], b) > 1e-5:
            raise ValidationError(f"{edge_id}: logical path must start and end at its stars")
        edge_paths[edge_id] = points
    piece_rows = records(layout, "pieces", "layout")
    by_piece = {}
    covered = {("star", key): [] for key in star_indexes}
    covered.update({("edge", key): [] for key in edge_indexes})
    for row in piece_rows:
        piece_id = identifier(row.get("id"), "piece.id")
        if piece_id in by_piece:
            raise ValidationError(f"Duplicate piece ID: {piece_id}")
        kind, owner = row.get("owner_type"), row.get("owner_id")
        if kind not in ("star", "edge", "hidden"):
            raise ValidationError(f"{piece_id}: unknown owner_type")
        if kind == "hidden":
            if owner is not None:
                raise ValidationError(f"{piece_id}: hidden pieces must have owner_id=null")
        else:
            owner = identifier(owner, f"{piece_id}.owner_id")
            if (kind, owner) not in covered:
                raise ValidationError(f"{piece_id}: unknown {kind} owner {owner}")
        n = count(row.get("led_count"), f"{piece_id}.led_count", cut_unit)
        points = path(row.get("path_mm"), f"{piece_id}.path_mm")
        if abs(path_length(points) - n * pitch) > 1e-3:
            raise ValidationError(f"{piece_id}: cut-boundary path length must be {n * pitch:g} mm")
        by_piece[piece_id] = (row, n, points)
    wiring = layout.get("wiring", {})
    if not isinstance(wiring, dict):
        raise ValidationError("wiring must be an object")
    order = records(wiring, "order", "wiring")
    order_ids = [identifier(item.get("piece_id"), "wiring.piece_id") for item in order]
    if len(order_ids) != len(by_piece) or len(set(order_ids)) != len(order_ids) or set(order_ids) != set(by_piece):
        raise ValidationError("wiring.order must include every piece exactly once")
    leds, pieces, links = [], [], []
    last_output = None
    last_piece = None
    for item in order:
        piece_id = item["piece_id"]
        reverse = item.get("reverse")
        if not isinstance(reverse, bool):
            raise ValidationError(f"{piece_id}: reverse must be a boolean")
        row, n, points = by_piece[piece_id]
        kind, owner = row["owner_type"], row.get("owner_id")
        first = len(leds)
        indices = tuple(range(first, first + n))
        owner_index = star_indexes[owner] if kind == "star" else edge_indexes[owner] if kind == "edge" else -1
        positions_on_path = list(range(n - 1, -1, -1)) if reverse else range(n)
        for local in positions_on_path:
            xy = sample_path(points, (local + 0.5) * pitch)
            u = None
            if kind == "edge":
                logical_path = edge_paths[owner]
                distance, deviation = project_path(logical_path, xy)
                if deviation > 1e-3:
                    raise ValidationError(f"{piece_id}: edge LEDs must lie on the edge's logical path")
                u = distance / path_length(logical_path)
            index = len(leds)
            leds.append(Led(index, piece_id, *xy, kind, owner_index, u))
            if kind != "hidden":
                covered[kind, owner].append(index)
        input_xy, output_xy = (points[-1], points[0]) if reverse else (points[0], points[-1])
        if last_output is not None:
            links.append(WireLink(last_piece, piece_id, last_output, input_xy, math.dist(last_output, input_xy)))
        pieces.append(Piece(piece_id, kind, owner, n, points, first, reverse, n * pitch, indices))
        last_piece, last_output = piece_id, output_xy
    missing = [owner for owner, indices in covered.items() if not indices]
    if missing:
        raise ValidationError(f"Logical objects without LEDs: {missing}")
    if layout.get("panel") is not None:
        strip_width = number(layout.get("strip_width_mm"), "strip_width_mm", positive=True)
        try:
            validate_panel(pieces, strip_width, layout["panel"])
        except ValueError as error:
            raise ValidationError(str(error)) from error
    stars = []
    for row in nodes:
        source = catalog_by_hip[row["hip"]]
        stars.append(Star(row["id"], row["hip"], str(source.get("name", f"HIP {row['hip']}")),
                          *positions[row["id"]], source.get("mag_v"), tuple(covered["star", row["id"]])))
    edges = tuple(Edge(row["id"], row["start"], row["end"], path_length(edge_paths[row["id"]]),
                       tuple(covered["edge", row["id"]]), edge_paths[row["id"]]) for row in edge_rows)
    return Runtime(tuple(leds), tuple(stars), edges, tuple(pieces), tuple(links), pitch, cut_unit,
                   width, height, layout)


def load_runtime(data_dir: str | Path, layout_path: str | Path | None = None) -> Runtime:
    data_dir = Path(data_dir)
    return compile_layout(read_json(data_dir / "catalog.json"), read_json(data_dir / "constellation.json"),
                          read_json(layout_path or data_dir / "layout.json"))
