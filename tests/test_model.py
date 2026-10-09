"""Verify geometry, routing and editable multi-piece ownership."""

import copy
import math
import unittest
from pathlib import Path

from constellation_lamp.layout import generate_layout
from constellation_lamp.model import ValidationError, compile_layout, load_runtime, path_length, read_json


DATA = Path(__file__).resolve().parents[1] / "data"


def sources():
    return read_json(DATA / "catalog.json"), read_json(DATA / "constellation.json")


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.catalog, self.constellation = sources()
        self.layout = generate_layout(self.catalog, self.constellation)

    def compile(self, layout=None):
        return compile_layout(self.catalog, self.constellation, layout or self.layout)

    def test_reference_counts_and_weak_star(self):
        runtime = self.compile()
        self.assertEqual((len(runtime.stars), len(runtime.edges), len(runtime.pieces)), (21, 24, 45))
        self.assertIn(94820, [star.hip for star in runtime.stars])
        self.assertEqual(runtime.pitch_mm, 5)
        self.assertEqual(runtime.cut_unit_leds, 2)
        self.assertEqual([led.index for led in runtime.leds], list(range(runtime.led_count)))
        memberships = [index for obj in (*runtime.stars, *runtime.edges) for index in obj.indices]
        self.assertEqual(sorted(memberships), list(range(runtime.led_count)))

    def test_cut_length_and_led_centres(self):
        runtime = self.compile()
        for piece in runtime.pieces:
            self.assertEqual(piece.led_count % 2, 0)
            self.assertAlmostEqual(path_length(piece.path_mm), piece.led_count * 5)
            pixels = [runtime.leds[index] for index in piece.indices]
            for a, b in zip(pixels, pixels[1:]):
                self.assertAlmostEqual(math.hypot(a.x_mm - b.x_mm, a.y_mm - b.y_mm), 5)
            self.assertAlmostEqual(math.dist((pixels[0].x_mm, pixels[0].y_mm),
                                            (pixels[-1].x_mm, pixels[-1].y_mm)), (piece.led_count - 1) * 5)

    def test_reverse_preserves_geometry_and_progress(self):
        original = self.compile()
        changed = copy.deepcopy(self.layout)
        changed["wiring"]["order"].reverse()
        for item in changed["wiring"]["order"]:
            item["reverse"] = not item["reverse"]
        reversed_runtime = self.compile(changed)
        def signatures(runtime):
            return sorted((led.piece_id, round(led.x_mm, 6), round(led.y_mm, 6), led.owner_type,
                           led.owner_index, None if led.u is None else round(led.u, 6)) for led in runtime.leds)
        self.assertEqual(signatures(original), signatures(reversed_runtime))

    def test_scale_keeps_density_and_quantization(self):
        small = self.compile()
        large = self.compile(generate_layout(self.catalog, self.constellation, width_mm=800))
        self.assertGreater(large.led_count, small.led_count)
        self.assertEqual(large.pitch_mm, small.pitch_mm)
        for piece in large.pieces:
            self.assertAlmostEqual(piece.cut_length_mm % 10, 0)

    def test_size_conflict_identifies_edges(self):
        with self.assertRaisesRegex(ValidationError, "Size conflict.*") as caught:
            generate_layout(self.catalog, self.constellation, width_mm=100)
        self.assertIn("hip_94820", str(caught.exception))

    def test_differently_sized_stars_clearance(self):
        template = {"star_overrides": {"hip_95168": {"led_count": 4}}}
        layout = generate_layout(self.catalog, self.constellation, template, width_mm=800)
        runtime = self.compile(layout)
        star = next(star for star in runtime.stars if star.hip == 95168)
        self.assertEqual(len(star.indices), 4)
        edge = next(edge for edge in runtime.edges if star.id in (edge.start_id, edge.end_id))
        piece = next(piece for piece in runtime.pieces if piece.owner_type == "edge" and piece.owner_id == edge.id)
        self.assertGreaterEqual(min(math.dist((star.x_mm, star.y_mm), p) for p in piece.path_mm), 11 - 1e-6)

    def test_wiring_must_cover_all_pieces_once(self):
        for mode in ("missing", "duplicate", "unknown"):
            layout = copy.deepcopy(self.layout)
            if mode == "missing":
                layout["wiring"]["order"].pop()
            elif mode == "duplicate":
                layout["wiring"]["order"][0] = layout["wiring"]["order"][1].copy()
            else:
                layout["wiring"]["order"][0]["piece_id"] = "nonexistent"
            with self.subTest(mode=mode), self.assertRaises(ValidationError):
                self.compile(layout)

    def test_invalid_piece_count_and_geometry(self):
        for mutation in (lambda p: p.update(led_count=3), lambda p: p.update(owner_id="no-star"),
                         lambda p: p.update(path_mm=[[0, 0], [1, 1]])):
            layout = copy.deepcopy(self.layout)
            mutation(layout["pieces"][0])
            with self.assertRaises(ValidationError):
                self.compile(layout)

    def test_logical_references_and_duplicate_edges(self):
        for mutation in (lambda c: c["edges"][0].update(start="absent"),
                         lambda c: c["edges"].append({**c["edges"][0], "id": "other"})):
            graph = copy.deepcopy(self.constellation)
            mutation(graph)
            with self.assertRaises(ValidationError):
                compile_layout(self.catalog, graph, self.layout)

    def test_multi_piece_owner_noncontiguous(self):
        layout = copy.deepcopy(self.layout)
        # Two separate minimum-cut pieces may belong to the same star.
        star_piece = layout["pieces"][0]
        extra = copy.deepcopy(star_piece)
        extra["id"] += "_extra"
        extra["path_mm"] = [[x, y + 10] for x, y in extra["path_mm"]]
        layout["pieces"].append(extra)
        layout["wiring"]["order"].append({"piece_id": extra["id"], "reverse": True})
        runtime = self.compile(layout)
        owner = next(star for star in runtime.stars if star.id == star_piece["owner_id"])
        self.assertEqual(len(owner.indices), 4)
        self.assertGreater(max(owner.indices) - min(owner.indices), 3)

    def test_multi_piece_edge_progress(self):
        layout = copy.deepcopy(self.layout)
        piece = next(p for p in layout["pieces"] if p["owner_type"] == "edge" and p["led_count"] >= 8)
        a, b = piece["path_mm"]
        middle = [(x + y) / 2 for x, y in zip(a, b)]
        # Choose a split on an even cut unit, not necessarily at the midpoint.
        half = (piece["led_count"] // 4) * 2
        t = half / piece["led_count"]
        middle = [x + (y - x) * t for x, y in zip(a, b)]
        extra = {**piece, "id": piece["id"] + "_extra", "led_count": piece["led_count"] - half,
                 "path_mm": [middle, b]}
        piece["led_count"], piece["path_mm"] = half, [a, middle]
        layout["pieces"].append(extra)
        layout["wiring"]["order"].append({"piece_id": extra["id"], "reverse": True})
        runtime = self.compile(layout)
        edge_index = next(i for i, edge in enumerate(runtime.edges) if edge.id == piece["owner_id"])
        u = [led.u for led in runtime.leds if led.owner_type == "edge" and led.owner_index == edge_index]
        self.assertEqual(len(u), len(set(round(value, 6) for value in u)))
        self.assertTrue(all(0 < value < 1 for value in u))

    def test_source_coordinates_and_missing_magnitude(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["stars"][0]["ra_deg"] = 400
        with self.assertRaises(ValidationError):
            compile_layout(catalog, self.constellation, self.layout)
        catalog = copy.deepcopy(self.catalog)
        catalog["stars"][0]["mag_v"] = None
        compile_layout(catalog, self.constellation, self.layout)

    def test_edited_scale_requires_regeneration(self):
        layout = copy.deepcopy(self.layout)
        layout["width_mm"] = 700
        with self.assertRaisesRegex(ValidationError, "Regenerate"):
            self.compile(layout)

    def test_malformed_identifiers_raise_validation_errors(self):
        for mutation in (lambda l: l["wiring"]["order"][0].update(piece_id=[]),
                         lambda l: l["pieces"][0].update(owner_id=[]),
                         lambda l: l.update(schema_version=True)):
            layout = copy.deepcopy(self.layout)
            mutation(layout)
            with self.assertRaises(ValidationError):
                self.compile(layout)


if __name__ == "__main__":
    unittest.main()
