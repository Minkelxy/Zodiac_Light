from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from constellation_lamp.export import export_c


def sample_runtime():
    # Star A has two separated pieces; the edge's geometric order is opposite
    # its serial addresses. A hidden LED occupies the unused serial slot.
    stars = (
        NS(id="a", hip=95168, name="A", x_mm=0.0, y_mm=10.125,
           mag_v=3.125, indices=(0, 4)),
        NS(id="b", hip=98412, name="B", x_mm=80.5, y_mm=-2.0,
           mag_v=None, indices=(5,)),
    )
    edges = (
        NS(id="ab", start_id="a", end_id="b", length_mm=81.407357,
           indices=(3, 2)),
    )
    leds = (
        NS(index=0, piece_id="a0", x_mm=0.0, y_mm=10.0,
           owner_type="star", owner_index=0, u=None),
        NS(index=1, piece_id="hidden", x_mm=5.0, y_mm=10.0,
           owner_type="hidden", owner_index=-1, u=None),
        NS(index=2, piece_id="edge", x_mm=60.375, y_mm=1.0,
           owner_type="edge", owner_index=0, u=0.75),
        NS(index=3, piece_id="edge", x_mm=20.125, y_mm=7.0,
           owner_type="edge", owner_index=0, u=0.25),
        NS(index=4, piece_id="a1", x_mm=-5.0, y_mm=10.0,
           owner_type="star", owner_index=0, u=None),
        NS(index=5, piece_id="b", x_mm=80.5, y_mm=-2.0,
           owner_type="star", owner_index=1, u=None),
    )
    return NS(leds=leds, stars=stars, edges=edges, led_count=len(leds),
              pieces=(), wire_links=(), pitch_mm=5.0, width_mm=80.5, height_mm=12.125)


def array_body(header: str, name: str) -> str:
    match = re.search(r"\b" + re.escape(name) + r"\[\d+\] = \{\n(.*?)\n\};", header, re.S)
    if match is None:
        raise AssertionError(f"Missing array {name}")
    return match.group(1)


def table_rows(header: str, name: str) -> list[list[str]]:
    body = array_body(header, name)
    return [row.split(", ") for row in re.findall(r"\{ ([^{}]+) \}", body)]


def integer(token: str) -> int:
    return (1 << 32) - 1 if token == "UINT32_MAX" else int(token.rstrip("u"))


def number(token: str) -> float:
    return float(token.rstrip("f"))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "scene_data.h"

    def render(self, runtime=None):
        export_c(sample_runtime() if runtime is None else runtime, self.path)
        return self.path.read_text(encoding="utf-8")

    def test_geometry_and_owners_match_runtime(self):
        runtime = sample_runtime()
        header = self.render(runtime)
        rows = table_rows(header, "constellation_leds")
        self.assertEqual(len(rows), runtime.led_count)
        roles = {"hidden": 0, "star": 1, "edge": 2}
        for row, led in zip(rows, runtime.leds):
            self.assertAlmostEqual(number(row[0]), led.x_mm, places=6)
            self.assertAlmostEqual(number(row[1]), led.y_mm, places=6)
            self.assertEqual(integer(row[2]), roles[led.owner_type])
            self.assertEqual(integer(row[3]), (1 << 32) - 1 if led.owner_type == "hidden" else led.owner_index)
            self.assertAlmostEqual(number(row[4]), led.u if led.u is not None else 0.0, places=6)
        self.assertIn("#define CONSTELLATION_LED_COUNT 6u", header)

    def test_noncontiguous_and_reversed_membership_is_preserved(self):
        runtime = sample_runtime()
        header = self.render(runtime)
        star_members = [int(value) for value in re.findall(r"(\d+)u", array_body(header, "constellation_star_led_indices"))]
        edge_members = [int(value) for value in re.findall(r"(\d+)u", array_body(header, "constellation_edge_led_indices"))]
        star_rows = table_rows(header, "constellation_stars")
        for star, row in zip(runtime.stars, star_rows):
            offset, count = integer(row[5]), integer(row[6])
            self.assertEqual(star_members[offset:offset + count], list(star.indices))
            self.assertEqual(integer(row[0]), star.hip)
            self.assertAlmostEqual(number(row[1]), star.x_mm, places=6)
            self.assertAlmostEqual(number(row[2]), star.y_mm, places=6)
            self.assertEqual(integer(row[4]), int(star.mag_v is not None))
            self.assertAlmostEqual(number(row[3]), star.mag_v if star.mag_v is not None else 0.0, places=6)
        edge_rows = table_rows(header, "constellation_edges")
        for edge, row in zip(runtime.edges, edge_rows):
            self.assertEqual(integer(row[0]), 0)
            self.assertEqual(integer(row[1]), 1)
            self.assertAlmostEqual(number(row[2]), edge.length_mm, places=6)
            offset, count = integer(row[3]), integer(row[4])
            self.assertEqual(edge_members[offset:offset + count], list(edge.indices))
        self.assertEqual(star_members, [0, 4, 5])
        self.assertEqual(edge_members, [3, 2])

    def test_empty_scene_has_storage_sentinels_and_zero_counts(self):
        runtime = NS(leds=(), stars=(), edges=(), led_count=0)
        header = self.render(runtime)
        self.assertIn("#define CONSTELLATION_LED_COUNT 0u", header)
        self.assertIn("#define CONSTELLATION_STAR_COUNT 0u", header)
        self.assertIn("#define CONSTELLATION_EDGE_COUNT 0u", header)
        self.assertNotIn("[0]", header)
        self.assertEqual(len(table_rows(header, "constellation_leds")), 1)
        self.assertNotIn("NAN", header)

    def test_float_literals_are_valid_c_and_indices_are_uint32(self):
        header = self.render()
        self.assertNotRegex(header, r"(?<![\w.])\d+f\b")
        self.assertIn("0.0f", header)
        self.assertIn("uint32_t owner_index;", header)
        self.assertIn("static const uint32_t constellation_star_led_indices", header)
        self.assertIn("95168u", header)  # A valid ID exceeds uint16_t.
        self.assertEqual(header.count("#ifndef CONSTELLATION_LAMP_SCENE_DATA_H"), 1)

    def test_rejects_uint32_overflow_and_inconsistent_membership(self):
        runtime = sample_runtime()
        runtime.stars[0].hip = 1 << 32
        with self.assertRaisesRegex(ValueError, "uint32_t"):
            self.render(runtime)
        runtime = sample_runtime()
        runtime.stars[0].indices = (0,)
        with self.assertRaisesRegex(ValueError, "membership"):
            self.render(runtime)

    def test_rejects_nonfinite_geometry_and_missing_edge_endpoint(self):
        runtime = sample_runtime()
        runtime.leds[0].x_mm = float("inf")
        with self.assertRaisesRegex(ValueError, "finite"):
            self.render(runtime)
        runtime = sample_runtime()
        runtime.edges[0].start_id = "missing"
        with self.assertRaisesRegex(ValueError, "invalid star"):
            self.render(runtime)

    def test_documented_sample_compiles_and_exports(self):
        import json
        from constellation_lamp.model import compile_layout

        document = (Path(__file__).resolve().parents[1] / "docs" / "data-model.md").read_text(encoding="utf-8")
        examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", document, re.S)]
        self.assertEqual(len(examples), 3)
        runtime = compile_layout(*examples)
        self.assertEqual(runtime.led_count, 12)
        header = self.render(runtime)
        self.assertEqual(len(table_rows(header, "constellation_leds")), runtime.led_count)
        # Reverse the physical edge while preserving the geometric u values.
        examples[2]["wiring"]["order"][1]["reverse"] = True
        reversed_runtime = compile_layout(*examples)
        self.assertAlmostEqual(reversed_runtime.leds[2].u, runtime.leds[9].u)
        self.assertAlmostEqual(reversed_runtime.leds[9].u, runtime.leds[2].u)

    def test_default_scene_export_matches_compiler(self):
        from constellation_lamp.model import load_runtime

        data_dir = Path(__file__).resolve().parents[1] / "data"
        if not all((data_dir / name).is_file() for name in ("catalog.json", "constellation.json", "layout.json")):
            self.skipTest("Default scene data has not been generated")
        runtime = load_runtime(data_dir)
        header = self.render(runtime)
        rows = table_rows(header, "constellation_leds")
        self.assertEqual(len(rows), runtime.led_count)
        for row, led in zip(rows, runtime.leds):
            self.assertAlmostEqual(number(row[0]), led.x_mm, places=4)
            self.assertAlmostEqual(number(row[1]), led.y_mm, places=4)
            self.assertEqual(integer(row[3]), (1 << 32) - 1 if led.owner_type == "hidden" else led.owner_index)
            self.assertAlmostEqual(number(row[4]), led.u if led.u is not None else 0.0, places=6)

    def test_c99_and_cpp_header_syntax_when_compilers_are_available(self):
        compilers = [
            (shutil.which("gcc") or shutil.which("clang"), "c99", ".c"),
            (shutil.which("g++") or shutil.which("clang++"), "c++11", ".cpp"),
        ]
        if shutil.which("cl"):
            compilers += [(shutil.which("cl"), "c11", ".c"), (shutil.which("cl"), "c++14", ".cpp")]
        available = [entry for entry in compilers if entry[0] is not None]
        if not available:
            self.skipTest("No C/C++ compiler available for syntax verification")
        self.render()
        for compiler, standard, suffix in available:
            with self.subTest(standard=standard):
                source = self.path.with_suffix(suffix)
                source.write_text(
                    '#include "scene_data.h"\n#include "scene_data.h"\n'
                    'int main(void) { return constellation_leds[0].owner_type == CONSTELLATION_LED_STAR ? 0 : 1; }\n',
                    encoding="utf-8",
                )
                if Path(compiler).stem.lower() == "cl":
                    command = [compiler, "/nologo", "/W4", f"/std:{standard}", "/Zs", str(source)]
                else:
                    command = [compiler, f"-std={standard}", "-pedantic-errors", "-fsyntax-only", str(source)]
                result = subprocess.run(
                    command,
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
