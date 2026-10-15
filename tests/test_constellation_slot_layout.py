"""Manufacturing invariants for the offline HIP-edge slot planner."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

try:
    from shapely.geometry import Point
    from shapely.ops import unary_union
except ImportError:
    Point = None


@unittest.skipIf(Point is None, "Optional hardware geometry checks require Shapely")
class ConstellationSlotLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "hardware/nfc-talisman/scripts/constellation_slot_layout.py"
        spec = importlib.util.spec_from_file_location("constellation_slot_layout_tested", path)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def assert_material(self, result):
        module = self.module
        holes = [Point(xy).buffer(.4, quad_segs=32) for xy in result.positions.values()]
        for slot in result.slots:
            self.assertTrue(slot.is_valid)
            self.assertGreaterEqual(slot.distance(module.af37_board().boundary), 1 - 1e-7)
            self.assertTrue(all(slot.distance(hole) >= 1 - 1e-7 for hole in holes))
        for i, first in enumerate(result.slots):
            self.assertTrue(all(first.distance(second) >= .8 - 1e-7 for second in result.slots[i + 1:]))
        material = module.af37_board().difference(unary_union([*holes, *result.slots]))
        self.assertTrue(material.is_valid)
        self.assertEqual(material.geom_type, "Polygon")

    def test_short_link_gets_slot_without_reducing_material_web(self):
        positions = {11: (10, 18.8), 12: (14.6, 18.8)}
        self.assertEqual(len(self.module.legacy_layout(positions, [(11, 12)]).slots), 0)
        result = self.module.optimize_slot_layout(positions, [(11, 12)], allow_uniform_scale=False)
        self.assertEqual(len(result.slots), 1)
        self.assertGreaterEqual(result.slot_records[0]["overall_length_mm"], 1.5)
        self.assertEqual(result.positions, positions)
        self.assert_material(result)

    def test_crossing_edges_keep_separate_machinable_segments(self):
        positions = {1: (9, 10), 2: (28, 27), 3: (9, 27), 4: (28, 10)}
        result = self.module.optimize_slot_layout(positions, [(1, 2), (3, 4)])
        self.assertEqual(result.metadata["preserved_logical_edges"], [[1, 2], [3, 4]])
        self.assertEqual(result.metadata["slotted_edge_count"], 2)
        self.assert_material(result)

    def test_nearby_third_star_is_not_cut_through(self):
        positions = {1: (7, 18.8), 2: (30, 18.8), 3: (18.5, 18.8)}
        result = self.module.optimize_slot_layout(positions, [(1, 2)], allow_uniform_scale=False)
        self.assertEqual(set(result.positions), set(positions))
        self.assertEqual(len(result.slots), 2)
        self.assert_material(result)

    def test_enlargement_preserves_all_relative_star_coordinates(self):
        positions = {1: (9, 12), 2: (27, 24), 3: (20, 28)}
        result = self.module.optimize_slot_layout(positions, [(1, 2), (2, 3)])
        scale = result.metadata["uniform_scale"]
        self.assertGreaterEqual(scale, 1)
        self.assertLessEqual(scale, 1.10)
        for a, b in ((1, 2), (1, 3), (2, 3)):
            for axis in (0, 1):
                self.assertAlmostEqual(result.positions[b][axis] - result.positions[a][axis],
                                       scale * (positions[b][axis] - positions[a][axis]))
        self.assert_material(result)


if __name__ == "__main__":
    unittest.main()
