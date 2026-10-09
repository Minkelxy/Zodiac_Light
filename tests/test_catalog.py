"""Check authoritative cached inputs and the offline/failed-refresh contract."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SPEC = importlib.util.spec_from_file_location("fetch_catalog", ROOT / "scripts" / "fetch_catalog.py")
fetch_catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_catalog)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog_bytes = (DATA / "catalog.json").read_bytes()
        self.catalog = json.loads(self.catalog_bytes)
        self.downloads = {
            source["id"]: (DATA / source["snapshot_path"]).read_bytes()
            for source in self.catalog["sources"]
        }
        self.snapshot_paths = sorted(str(path) for path in (DATA / "sources").rglob("*") if path.is_file())

    def assert_cache_unchanged(self):
        self.assertEqual((DATA / "catalog.json").read_bytes(), self.catalog_bytes)
        self.assertEqual(sorted(str(path) for path in (DATA / "sources").rglob("*") if path.is_file()),
                         self.snapshot_paths)
        for source in self.catalog["sources"]:
            self.assertEqual((DATA / source["snapshot_path"]).read_bytes(), self.downloads[source["id"]])

    def test_default_cli_is_offline_and_verifies_snapshot_hashes(self):
        output = io.StringIO()
        with patch.object(fetch_catalog, "urlopen", side_effect=AssertionError("Offline command used network")), \
                contextlib.redirect_stdout(output):
            self.assertEqual(fetch_catalog.main(["--data-dir", str(DATA)]), 0)
        self.assertIn("offline; no network requests", output.getvalue())
        self.assert_cache_unchanged()

    def test_reference_selection_and_edges_match_the_frozen_source(self):
        verified = fetch_catalog.verify_cache(DATA)
        graph = json.loads((DATA / "constellation.json").read_text(encoding="utf-8"))
        self.assertEqual([star["hip"] for star in verified["stars"]], list(fetch_catalog.SELECTED_HIPS))
        self.assertEqual([star["hip"] for star in graph["stars"]], list(fetch_catalog.SELECTED_HIPS))
        modern = json.loads(self.downloads["stellarium_modern"])
        figure = next(row for row in modern["constellations"] if row["id"] == "CON modern Sgr")
        expected_edges = [(f"hip_{a}", f"hip_{b}")
                          for line in figure["lines"] for a, b in zip(line, line[1:])]
        self.assertEqual([(row["start"], row["end"]) for row in graph["edges"]], expected_edges)
        self.assertEqual([row["id"] for row in graph["edges"]], [f"e{i:02d}" for i in range(1, 25)])
        self.assertEqual(len({frozenset(pair) for pair in expected_edges}), 24)

    def test_failed_download_does_not_start_persistence(self):
        with patch.object(fetch_catalog, "request", side_effect=URLError("Simulated connection failure")), \
                patch.object(fetch_catalog, "atomic_json") as atomic_write, \
                patch.object(fetch_catalog.Path, "mkdir") as mkdir:
            with self.assertRaises(URLError):
                fetch_catalog.refresh(DATA)
            atomic_write.assert_not_called()
            mkdir.assert_not_called()
        self.assert_cache_unchanged()

    def test_incomplete_response_does_not_start_persistence(self):
        incomplete = self.downloads.copy()
        lines = incomplete["hipparcos_i239"].decode("utf-8").splitlines(keepends=True)
        incomplete["hipparcos_i239"] = "".join(
            line for line in lines if not line.startswith(" 95168\t")
        ).encode("utf-8")
        self.assertNotEqual(incomplete["hipparcos_i239"], self.downloads["hipparcos_i239"])
        with patch.object(fetch_catalog, "request", side_effect=lambda spec: (spec["id"], incomplete[spec["id"]])), \
                patch.object(fetch_catalog, "atomic_json") as atomic_write, \
                patch.object(fetch_catalog.Path, "mkdir") as mkdir:
            with self.assertRaisesRegex(ValueError, "exactly the selected 21 stars"):
                fetch_catalog.refresh(DATA)
            atomic_write.assert_not_called()
            mkdir.assert_not_called()
        self.assert_cache_unchanged()


if __name__ == "__main__":
    unittest.main()
