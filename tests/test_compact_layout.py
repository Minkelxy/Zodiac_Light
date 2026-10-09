"""Check the real 21-star design against its four-LED and panel constraints."""

import copy
import math
import unittest
from pathlib import Path

from constellation_lamp.layout import generate_layout
from constellation_lamp.model import ValidationError, compile_layout, path_length, read_json


DATA = Path(__file__).resolve().parents[1] / "data"


def compact_template():
    return {
        "density_leds_per_m": 200,
        "cut_unit_leds": 2,
        "panel": {"width_mm": 400, "height_mm": 400, "margin_mm": 5},
        "strip_width_mm": 5,
        "star_defaults": {"led_count": 4, "shape": "grid_2x2",
                          "row_gap_mm": 2, "angle_deg": 0},
        "star_overrides": {},
        "star_clearance_mm": 1,
        "adjust_nearby_stars": True,
        "max_star_shift_mm": 20,
    }


def footprint_corners(piece, strip_width):
    """Independent PCB-boundary check, including width perpendicular to each path."""
    half_width = strip_width / 2
    for start, end in zip(piece["path_mm"], piece["path_mm"][1:]):
        length = math.dist(start, end)
        offset_x = -(end[1] - start[1]) * half_width / length
        offset_y = (end[0] - start[0]) * half_width / length
        for x, y in (start, end):
            for sign in (-1, 1):
                yield x + sign * offset_x, y + sign * offset_y


def strip_rectangle(piece, strip_width):
    """Ordered rectangle vertices for the generator's straight PCB strips."""
    start, end = piece["path_mm"]
    distance = math.dist(start, end)
    offset_x = -(end[1] - start[1]) * strip_width / (2 * distance)
    offset_y = (end[0] - start[0]) * strip_width / (2 * distance)
    return [(start[0] + offset_x, start[1] + offset_y),
            (end[0] + offset_x, end[1] + offset_y),
            (end[0] - offset_x, end[1] - offset_y),
            (start[0] - offset_x, start[1] - offset_y)]


def rectangles_overlap(first, second):
    """Separating-axis check; touching boundaries have no overlapping area."""
    for rectangle in (first, second):
        for start, end in zip(rectangle, rectangle[1:] + rectangle[:1]):
            axis = (start[1] - end[1], end[0] - start[0])
            projections = [[x * axis[0] + y * axis[1] for x, y in polygon]
                           for polygon in (first, second)]
            a, b = projections
            if min(max(a), max(b)) <= max(min(a), min(b)) + 1e-8:
                return False
    return True


class CompactLayoutTests(unittest.TestCase):
    def setUp(self):
        self.catalog = read_json(DATA / "catalog.json")
        self.constellation = read_json(DATA / "constellation.json")
        self.template = compact_template()

    def generate(self, template=None, width_mm=None):
        return generate_layout(self.catalog, self.constellation,
                               self.template if template is None else template,
                               width_mm=width_mm)

    def test_full_constellation_has_four_leds_per_star(self):
        layout = self.generate()
        runtime = compile_layout(self.catalog, self.constellation, layout)
        self.assertEqual((len(runtime.stars), len(runtime.edges), len(runtime.pieces)),
                         (21, 24, 66))
        self.assertIn(94820, [star.hip for star in runtime.stars])
        self.assertTrue(all(len(star.indices) == 4 for star in runtime.stars))
        self.assertTrue(all(len(edge.indices) >= 2 for edge in runtime.edges))
        for star in runtime.stars:
            pieces = [piece for piece in runtime.pieces
                      if piece.owner_type == "star" and piece.owner_id == star.id]
            self.assertEqual(len(pieces), 2)
            self.assertEqual([piece.led_count for piece in pieces], [2, 2])

    def test_complete_pcb_footprints_fit_within_panel_margin(self):
        layout = self.generate()
        compile_layout(self.catalog, self.constellation, layout)
        self.assertEqual(layout["panel"], self.template["panel"])
        points = [point for piece in layout["pieces"]
                  for point in footprint_corners(piece, layout["strip_width_mm"])]
        for x, y in points:
            self.assertGreaterEqual(x, 5 - 1e-6)
            self.assertLessEqual(x, 395 + 1e-6)
            self.assertGreaterEqual(y, 5 - 1e-6)
            self.assertLessEqual(y, 395 + 1e-6)

    def test_grid_keeps_pcb_rows_separate_and_fixed_led_pitch(self):
        layout = self.generate()
        runtime = compile_layout(self.catalog, self.constellation, layout)
        self.assertEqual(runtime.pitch_mm, 5)
        for star in runtime.stars:
            leds = [runtime.leds[index] for index in star.indices]
            xs = sorted(set(round(led.x_mm, 6) for led in leds))
            ys = sorted(set(round(led.y_mm, 6) for led in leds))
            self.assertEqual((len(xs), len(ys)), (2, 2))
            self.assertAlmostEqual(xs[1] - xs[0], 5, places=5)
            self.assertAlmostEqual(ys[1] - ys[0], 7, places=5)
        for piece in runtime.pieces:
            self.assertEqual(piece.led_count % 2, 0)
            self.assertAlmostEqual(path_length(piece.path_mm), piece.led_count * 5)
            leds = [runtime.leds[index] for index in piece.indices]
            for start, end in zip(leds, leds[1:]):
                self.assertAlmostEqual(math.hypot(end.x_mm - start.x_mm,
                                                end.y_mm - start.y_mm), 5)

    def test_no_pair_of_star_or_edge_pcbs_overlap(self):
        layout = self.generate()
        rectangles = [(piece["id"], strip_rectangle(piece, layout["strip_width_mm"]))
                      for piece in layout["pieces"]]
        for index, (first_id, first) in enumerate(rectangles):
            for second_id, second in rectangles[index + 1:]:
                with self.subTest(first=first_id, second=second_id):
                    self.assertFalse(rectangles_overlap(first, second))

    def test_local_adjustment_is_deterministic_and_preserves_source_coordinates(self):
        catalog_before = copy.deepcopy(self.catalog)
        constellation_before = copy.deepcopy(self.constellation)
        template_before = copy.deepcopy(self.template)
        first = self.generate()
        self.assertEqual(first, self.generate())
        self.assertEqual(self.catalog, catalog_before)
        self.assertEqual(self.constellation, constellation_before)
        self.assertEqual(self.template, template_before)
        # User permits changes only to the physical layout, not the reference image.
        self.assertEqual(len(first["star_positions_mm"]), 21)
        self.assertEqual(len(first["edge_paths_mm"]), 24)

    def test_grid_requires_exactly_four_leds(self):
        template = copy.deepcopy(self.template)
        template["star_defaults"]["led_count"] = 6
        with self.assertRaises(ValidationError):
            self.generate(template)

    def test_position_changes_respect_and_report_the_shift_limit(self):
        layout = self.generate()
        originals = layout["generation"]["original_scaled_positions_mm"]
        observed = {star_id: math.dist(position, originals[star_id])
                    for star_id, position in layout["star_positions_mm"].items()}
        self.assertGreater(max(observed.values()), 0)
        self.assertLessEqual(max(observed.values()), self.template["max_star_shift_mm"])
        for star_id, displacement in observed.items():
            self.assertAlmostEqual(layout["generation"]["star_shift_mm"][star_id], displacement)
        self.assertAlmostEqual(layout["generation"]["max_star_shift_mm"], max(observed.values()))
        template = copy.deepcopy(self.template)
        template["max_star_shift_mm"] = 0.001
        with self.assertRaises(ValidationError):
            self.generate(template)

    def test_panel_limit_cannot_be_bypassed_by_explicit_width(self):
        with self.assertRaises(ValidationError):
            self.generate(width_mm=700)

    def test_impossible_panel_and_parameters_raise_validation_errors(self):
        panels = [
            {"width_mm": 0, "height_mm": 400, "margin_mm": 5},
            {"width_mm": 400, "height_mm": 400, "margin_mm": -1},
            {"width_mm": 10, "height_mm": 10, "margin_mm": 5},
            "400x400",
        ]
        for panel in panels:
            with self.subTest(panel=panel):
                template = copy.deepcopy(self.template)
                template["panel"] = panel
                with self.assertRaises(ValidationError):
                    self.generate(template)

    def test_disabling_adjustment_reports_short_edges(self):
        template = copy.deepcopy(self.template)
        template["adjust_nearby_stars"] = False
        with self.assertRaises(ValidationError):
            self.generate(template)

    def test_compiler_checks_saved_pcb_bounds_after_manual_edits(self):
        layout = self.generate()
        # Translation preserves lengths, centre extents and edge endpoints, so
        # only the panel constraint should reject this otherwise valid layout.
        points = list(layout["star_positions_mm"].values())
        points += [point for path in layout["edge_paths_mm"].values() for point in path]
        points += [point for piece in layout["pieces"] for point in piece["path_mm"]]
        translated = set()
        for point in points:
            if id(point) not in translated:
                point[0] += 400
                translated.add(id(point))
        with self.assertRaises(ValidationError):
            compile_layout(self.catalog, self.constellation, layout)

    def test_legacy_template_without_panel_keeps_500mm_two_led_layout(self):
        layout = generate_layout(self.catalog, self.constellation)
        runtime = compile_layout(self.catalog, self.constellation, layout)
        self.assertAlmostEqual(runtime.width_mm, 500)
        self.assertEqual(runtime.led_count, 406)
        self.assertEqual(len(runtime.pieces), 45)
        self.assertTrue(all(len(star.indices) == 2 for star in runtime.stars))


if __name__ == "__main__":
    unittest.main()
