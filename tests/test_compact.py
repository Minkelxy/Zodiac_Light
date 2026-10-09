"""Verify integer MCU tables against the full-precision scene and C consumers."""

from __future__ import annotations

import copy
import json
import math
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from constellation_lamp.compact import TABLE_TYPES, export_compact_c, pack_runtime
from constellation_lamp.export import export_c
from constellation_lamp.model import compile_layout, load_runtime, read_json


DATA = Path(__file__).resolve().parents[1] / "data"


def sample_runtime():
    # One hidden pixel; separated star pieces; deliberately reversed edge members.
    stars = (NS(id="a", hip=95168, x_mm=0.0, y_mm=10.125, mag_v=3.125, indices=(0, 4)),
             NS(id="b", hip=98412, x_mm=80.5, y_mm=-2.0, mag_v=None, indices=(5,)))
    edges = (NS(id="ab", start_id="a", end_id="b", length_mm=81.407357, indices=(3, 2)),)
    leds = (
        NS(index=0, x_mm=0.0, y_mm=10.0, owner_type="star", owner_index=0, u=None),
        NS(index=1, x_mm=5.0, y_mm=10.0, owner_type="hidden", owner_index=-1, u=None),
        NS(index=2, x_mm=60.375, y_mm=1.0, owner_type="edge", owner_index=0, u=0.75),
        NS(index=3, x_mm=20.125, y_mm=7.0, owner_type="edge", owner_index=0, u=0.25),
        NS(index=4, x_mm=-5.0, y_mm=10.0, owner_type="star", owner_index=0, u=None),
        NS(index=5, x_mm=80.5, y_mm=-2.0, owner_type="star", owner_index=1, u=None),
    )
    return NS(leds=leds, stars=stars, edges=edges, led_count=len(leds))


def array_values(header, name):
    match = re.search(r"\bconstellation_compact_" + re.escape(name)
                      + r"\[\d+\] = \{\n(.*?)\n\};", header, re.S)
    if match is None:
        raise AssertionError(f"Missing compact array {name}")
    return [int(value.rstrip("u")) for value in re.findall(r"-?\d+u?", match.group(1))]


class CompactTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "compact.h"

    def test_real_runtime_preserves_identity_geometry_and_membership(self):
        runtime = load_runtime(DATA)
        packed = pack_runtime(runtime)
        self.assertEqual(json.loads(json.dumps(packed)), packed)
        tables = packed["tables"]
        counts = packed["counts"]
        self.assertEqual((counts["leds"], counts["stars"], counts["edges"]),
                         (runtime.led_count, len(runtime.stars), len(runtime.edges)))
        roles = {"hidden": 0, "star": 1, "edge": 2}
        for index, led in enumerate(runtime.leds):
            self.assertLessEqual(abs(tables["led_x_dm"][index] / 10 - led.x_mm), 0.05 + 1e-12)
            self.assertLessEqual(abs(tables["led_y_dm"][index] / 10 - led.y_mm), 0.05 + 1e-12)
            self.assertEqual(tables["led_owner_type"][index], roles[led.owner_type])
            self.assertEqual(tables["led_owner_index"][index],
                             65535 if led.owner_type == "hidden" else led.owner_index)
            if led.u is None:
                self.assertEqual(tables["led_u16"][index], 0)
            else:
                self.assertLessEqual(abs(tables["led_u16"][index] / 65535 - led.u),
                                     0.5 / 65535 + 1e-15)
        for kind, objects in (("star", runtime.stars), ("edge", runtime.edges)):
            for index, owner in enumerate(objects):
                offset = tables[kind + "_led_offsets"][index]
                count = tables[kind + "_led_counts"][index]
                self.assertEqual(tables[kind + "_led_indices"][offset:offset + count], list(owner.indices))
                if kind == "star":
                    self.assertEqual(tables["star_hip"][index], owner.hip)
                    self.assertLessEqual(abs(tables["star_x_dm"][index] / 10 - owner.x_mm), 0.05 + 1e-12)
                    self.assertLessEqual(abs(tables["star_y_dm"][index] / 10 - owner.y_mm), 0.05 + 1e-12)
                    if owner.mag_v is None:
                        self.assertEqual(tables["star_mag_centi"][index], -32768)
                    else:
                        self.assertLessEqual(abs(tables["star_mag_centi"][index] / 100 - owner.mag_v),
                                             0.005 + 1e-12)
                else:
                    self.assertLessEqual(abs(tables["edge_length_dm"][index] / 10 - owner.length_mm),
                                         0.05 + 1e-12)
        self.assertLessEqual(packed["metadata"]["max_abs_position_error_mm"], 0.05 + 1e-12)
        self.assertLessEqual(packed["metadata"]["max_position_distance_error_mm"], math.sqrt(2) * 0.05 + 1e-12)

    def test_undirected_csr_contains_each_incident_edge_with_its_neighbor(self):
        runtime = load_runtime(DATA)
        packed = pack_runtime(runtime)
        tables = packed["tables"]
        lookup = {star.id: index for index, star in enumerate(runtime.stars)}
        self.assertEqual(packed["counts"]["adjacency_entries"], len(runtime.edges) * 2)
        self.assertEqual(len(tables["adjacency_offsets"]), len(runtime.stars) + 1)
        self.assertEqual(tables["adjacency_offsets"][0], 0)
        self.assertEqual(tables["adjacency_offsets"][-1], len(runtime.edges) * 2)
        for index, star in enumerate(runtime.stars):
            expected = []
            for edge_index, edge in enumerate(runtime.edges):
                self.assertEqual(tables["edge_start_star"][edge_index], lookup[edge.start_id])
                self.assertEqual(tables["edge_end_star"][edge_index], lookup[edge.end_id])
                if edge.start_id == star.id:
                    expected.append((lookup[edge.end_id], edge_index))
                elif edge.end_id == star.id:
                    expected.append((lookup[edge.start_id], edge_index))
            start, end = tables["adjacency_offsets"][index:index + 2]
            actual = list(zip(tables["adjacency_neighbor_star"][start:end],
                              tables["adjacency_edge_index"][start:end]))
            self.assertEqual(actual, expected)

    def test_disjoint_members_and_reversed_edge_progress_are_preserved(self):
        packed = pack_runtime(sample_runtime())
        tables = packed["tables"]
        self.assertEqual(tables["star_led_indices"], [0, 4, 5])
        self.assertEqual(tables["edge_led_indices"], [3, 2])
        self.assertEqual(tables["led_owner_index"][1], 65535)
        self.assertEqual(tables["star_mag_centi"], [313, -32768])
        self.assertEqual(tables["led_u16"][2:4], [49151, 16384])
        self.assertEqual(tables["adjacency_offsets"], [0, 1, 2])
        self.assertEqual(tables["adjacency_neighbor_star"], [1, 0])
        self.assertEqual(tables["adjacency_edge_index"], [0, 0])

    def test_real_wiring_reverse_changes_serial_order_only(self):
        catalog = read_json(DATA / "catalog.json")
        graph = read_json(DATA / "constellation.json")
        layout = read_json(DATA / "layout.json")
        original = compile_layout(catalog, graph, layout)
        changed = copy.deepcopy(layout)
        changed["wiring"]["order"].reverse()
        for item in changed["wiring"]["order"]:
            item["reverse"] = not item["reverse"]
        reversed_runtime = compile_layout(catalog, graph, changed)

        def positions(packed):
            tables = packed["tables"]
            return sorted(zip(tables["led_x_dm"], tables["led_y_dm"], tables["led_owner_type"],
                              tables["led_owner_index"], tables["led_u16"]))

        self.assertEqual(positions(pack_runtime(original)), positions(pack_runtime(reversed_runtime)))

    def test_boundaries_and_explicit_halfway_rounding(self):
        runtime = sample_runtime()
        runtime.leds[0].x_mm = -3276.8
        runtime.leds[0].y_mm = 3276.7
        runtime.leds[1].x_mm = -0.05
        runtime.leds[1].y_mm = 0.05
        runtime.stars[0].mag_v = -327.67
        runtime.stars[1].mag_v = 327.67
        runtime.stars[0].hip = 4294967295
        runtime.edges[0].length_mm = 6553.5
        runtime.leds[2].u = 0
        runtime.leds[3].u = 1
        tables = pack_runtime(runtime)["tables"]
        self.assertEqual((tables["led_x_dm"][0], tables["led_y_dm"][0]), (-32768, 32767))
        self.assertEqual((tables["led_x_dm"][1], tables["led_y_dm"][1]), (-1, 1))
        self.assertEqual(tables["star_mag_centi"], [-32767, 32767])
        self.assertEqual(tables["star_hip"][0], 4294967295)
        self.assertEqual(tables["edge_length_dm"], [65535])
        self.assertEqual(tables["led_u16"][2:4], [0, 65535])
        runtime.leds[2].u = 10.5 / 65535
        self.assertEqual(pack_runtime(runtime)["tables"]["led_u16"][2], 11)

    def test_out_of_range_and_nonfinite_values_are_rejected_without_writing(self):
        mutations = [
            lambda r: setattr(r.leds[0], "x_mm", 3276.8),
            lambda r: setattr(r.leds[0], "y_mm", -3276.9),
            lambda r: setattr(r.leds[0], "x_mm", float("nan")),
            lambda r: setattr(r.stars[0], "y_mm", float("inf")),
            lambda r: setattr(r.stars[0], "mag_v", -327.68),
            lambda r: setattr(r.stars[0], "mag_v", float("nan")),
            lambda r: setattr(r.stars[0], "hip", 4294967296),
            lambda r: setattr(r.stars[0], "hip", True),
            lambda r: setattr(r.edges[0], "length_mm", 6553.6),
            lambda r: setattr(r.edges[0], "length_mm", -1),
            lambda r: setattr(r.leds[2], "u", -0.0001),
            lambda r: setattr(r.leds[2], "u", 1.0001),
            lambda r: setattr(r.leds[2], "u", None),
        ]
        self.path.write_text("preserve existing export", encoding="utf-8")
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                runtime = sample_runtime()
                mutation(runtime)
                with self.assertRaises(ValueError):
                    export_compact_c(runtime, self.path)
                self.assertEqual(self.path.read_text(encoding="utf-8"), "preserve existing export")

    def test_count_owner_and_membership_overflows_are_rejected(self):
        runtime = sample_runtime()
        runtime.led_count = 65536
        with self.assertRaisesRegex(ValueError, "LED count"):
            pack_runtime(runtime)
        runtime = sample_runtime()
        runtime.stars = runtime.stars[:1] * 65536
        with self.assertRaisesRegex(ValueError, "star count"):
            pack_runtime(runtime)
        runtime = sample_runtime()
        runtime.edges = runtime.edges * 32768
        with self.assertRaisesRegex(ValueError, "adjacency entry count"):
            pack_runtime(runtime)
        mutations = [lambda r: setattr(r.leds[0], "owner_index", 65535),
                     lambda r: setattr(r.leds[0], "owner_index", True),
                     lambda r: setattr(r.leds[1], "owner_index", 0),
                     lambda r: setattr(r.stars[0], "indices", (0, 65535)),
                     lambda r: setattr(r.stars[0], "indices", (0, 0)),
                     lambda r: setattr(r.stars[0], "indices", (0,)),
                     lambda r: setattr(r.leds[2], "index", 3)]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                runtime = sample_runtime()
                mutation(runtime)
                with self.assertRaises(ValueError):
                    pack_runtime(runtime)

    def test_invalid_graph_ids_and_endpoints_are_rejected(self):
        mutations = [lambda r: setattr(r.stars[1], "id", "a"),
                     lambda r: setattr(r.stars[1], "hip", 95168),
                     lambda r: setattr(r.edges[0], "start_id", "missing"),
                     lambda r: setattr(r.edges[0], "end_id", "a")]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                runtime = sample_runtime()
                mutation(runtime)
                with self.assertRaises(ValueError):
                    pack_runtime(runtime)

    def test_metadata_reports_array_payload_and_quantization_errors(self):
        runtime = sample_runtime()
        packed = pack_runtime(runtime)
        metadata = packed["metadata"]
        memberships = sum(len(owner.indices) for owner in (*runtime.stars, *runtime.edges))
        expected_bytes = (9 * runtime.led_count + 14 * len(runtime.stars) + 10 * len(runtime.edges)
                          + 2 * memberships + 2 * (len(runtime.stars) + 1) + 8 * len(runtime.edges))
        self.assertEqual(metadata["table_bytes"], expected_bytes)
        self.assertEqual(metadata["c_arrays_bytes"], expected_bytes)
        self.assertEqual(metadata["rgb_frame_bytes"], 3 * runtime.led_count)
        self.assertEqual(sum(metadata["table_bytes_by_name"].values()), expected_bytes)
        self.assertAlmostEqual(metadata["max_abs_position_error_mm"], 0.025)
        self.assertAlmostEqual(metadata["max_magnitude_error"], 0.005)
        self.assertLessEqual(metadata["max_u_error"], 0.5 / 65535)

    def test_empty_scene_has_logical_zero_counts_and_portable_storage(self):
        runtime = NS(led_count=0, leds=(), stars=(), edges=())
        packed = pack_runtime(runtime)
        self.assertEqual(packed["tables"]["adjacency_offsets"], [0])
        self.assertEqual(packed["metadata"]["table_bytes"], 2)
        self.assertGreater(packed["metadata"]["c_arrays_bytes"], 2)
        self.assertEqual(packed["metadata"]["rgb_frame_bytes"], 0)
        export_compact_c(runtime, self.path)
        header = self.path.read_text(encoding="utf-8")
        self.assertIn("#define CONSTELLATION_COMPACT_LED_COUNT 0u", header)
        self.assertIn("#define CONSTELLATION_COMPACT_ADJACENCY_OFFSET_COUNT 1u", header)
        self.assertNotIn("[0]", header)

    def test_c_header_arrays_and_names_match_packed_data(self):
        runtime = sample_runtime()
        packed = pack_runtime(runtime)
        export_compact_c(runtime, self.path)
        header = self.path.read_text(encoding="utf-8")
        for name, values in packed["tables"].items():
            self.assertEqual(array_values(header, name), values or [0])
            self.assertIn(f"static const {TABLE_TYPES[name]} constellation_compact_{name}", header)
        self.assertNotRegex(header, r"(?m)^\s*(?:static\s+const\s+)?float\s+\w+")
        self.assertIn("#define CONSTELLATION_COMPACT_U_DENOMINATOR 65535u", header)
        self.assertIn("#define CONSTELLATION_COMPACT_OWNER_NONE UINT16_MAX", header)
        self.assertIn("#define CONSTELLATION_COMPACT_MAG_MISSING INT16_MIN", header)
        self.assertEqual(header.count("#ifndef CONSTELLATION_LAMP_COMPACT_SCENE_DATA_H"), 1)

    def test_c99_cpp_compilation_and_payload_size_with_float_header(self):
        candidates = [(shutil.which("gcc") or shutil.which("clang"), "c99", ".c", "gnu"),
                      (shutil.which("g++") or shutil.which("clang++"), "c++11", ".cpp", "gnu"),
                      (shutil.which("cl"), "c11", ".c", "msvc"),
                      (shutil.which("cl"), "c++14", ".cpp", "msvc")]
        available = [candidate for candidate in candidates if candidate[0]]
        if not available:
            self.skipTest("No C/C++ compiler available for host verification")
        runtime = sample_runtime()
        export_compact_c(runtime, self.path)
        export_c(runtime, self.path.parent / "float_scene.h")
        payload = " + ".join(f"sizeof(constellation_compact_{name})" for name in TABLE_TYPES)
        for compiler, standard, suffix, family in available:
            with self.subTest(standard=standard):
                source = self.path.with_suffix(suffix)
                executable = self.path.parent / ("verify_" + standard.replace("+", "p") + ".exe")
                source.write_text(
                    '#include "compact.h"\n#include "float_scene.h"\n#include "compact.h"\n'
                    'int main(void) {\n'
                    f'  if ({payload} != CONSTELLATION_COMPACT_C_ARRAYS_BYTES) return 1;\n'
                    '  if (constellation_compact_led_owner_index[1] != CONSTELLATION_COMPACT_OWNER_NONE) return 2;\n'
                    '  if (constellation_compact_star_mag_centi[1] != CONSTELLATION_COMPACT_MAG_MISSING) return 3;\n'
                    '  if (constellation_compact_led_u16[2] <= constellation_compact_led_u16[3]) return 4;\n'
                    '  if (constellation_compact_adjacency_offsets[2] != 2u) return 5;\n'
                    '  if (constellation_leds[0].owner_type != CONSTELLATION_LED_STAR) return 6;\n'
                    '  return 0;\n}\n', encoding="utf-8")
                if family == "msvc":
                    language = "/TC" if suffix == ".c" else "/TP"
                    obj = self.path.parent / ("verify_" + standard.replace("+", "p") + ".obj")
                    command = [compiler, "/nologo", f"/std:{standard}", language,
                               str(source), f"/Fe:{executable}", f"/Fo:{obj}"]
                else:
                    command = [compiler, f"-std={standard}", "-pedantic-errors",
                               str(source), "-o", str(executable)]
                compiled = subprocess.run(command,
                                          capture_output=True, text=True, check=False)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                ran = subprocess.run([str(executable)], capture_output=True, text=True, check=False)
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


if __name__ == "__main__":
    unittest.main()
