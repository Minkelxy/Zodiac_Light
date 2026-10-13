"""Detect broken or mismatched NFC deliverables without touching live EasyEDA."""
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile


REPO = Path(__file__).resolve().parents[1]
HARDWARE = REPO / "hardware/nfc-talisman"
SPEC = importlib.util.spec_from_file_location("nfc_delivery", HARDWARE / "scripts/check_delivery.py")
DELIVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DELIVERY)


class HardwareDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "nfc-talisman"
        paths = {"variants/common/export-manifest.json", "variants/common/assembly-review-manifest.json",
                 "variants/common/native-copper-audit.json"}
        for manifest in ("export-manifest.json", "assembly-review-manifest.json"):
            data = json.loads((HARDWARE / "variants/common" / manifest).read_text(encoding="utf-8"))
            paths.update(name.replace("\\", "/") for name in data["files"])
        for variant in DELIVERY.VARIANTS:
            folder = f"variants/{variant}/artwork"
            paths.add(f"{folder}/manifest.json")
            data = json.loads((HARDWARE / folder / "manifest.json").read_text(encoding="utf-8"))
            paths.add(f"{folder}/{data['preview']['file']}")
            for name in data["files"]:
                paths.add(f"{folder}/{name}")
                paths.add(f"{folder}/{Path(name).with_suffix('.svg').as_posix()}")
        for name in paths:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(HARDWARE / name, target)

    def result(self):
        return DELIVERY.validate(self.root)

    def check_failed(self, result, ident):
        self.assertEqual(result["status"], "failed")
        check = next(item for item in result["checks"] if item["id"] == ident)
        self.assertFalse(check["passed"], result["errors"])
        return check["detail"]

    def rehash(self, name, manifest="export-manifest.json"):
        path = self.root / "variants/common" / manifest
        data = json.loads(path.read_text(encoding="utf-8"))
        key = next(key for key in data["files"] if key.replace("\\", "/") == name)
        content = (self.root / name).read_bytes()
        data["files"][key] = {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_current_archive_passes_and_preserves_manufacturing_hold(self):
        result = self.result()
        self.assertEqual(result["status"], "passed", result["errors"])
        self.assertGreaterEqual(result["checks_run"], 40)
        self.assertTrue(result["read_only"])
        self.assertTrue(result["release_status"].startswith("HOLD"))
        self.assertFalse(result["release_ready"])

    def test_missing_manufacturing_file_is_reported(self):
        name = "variants/snake-leo/manufacturing-draft/two-led-pnp-review.csv"
        (self.root / name).unlink()
        result = self.result()
        self.check_failed(result, f"assembly_file:{name}")
        self.check_failed(result, "assembly:snake-leo")

    def test_raw_export_byte_change_breaks_manifest_hash(self):
        name = "variants/horse-sagittarius/manufacturing-draft/bom-all.csv"
        with (self.root / name).open("ab") as handle:
            handle.write(b"\n")
        self.assertIn("SHA-256 mismatch", self.check_failed(self.result(), f"export_file:{name}"))

    def test_ct2_fit_is_rejected_even_if_profile_manifest_is_rewritten(self):
        path = self.root / "variants/common/assembly-review-manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["profiles"]["two-led"]["fit_designators"].append("CT2")
        data["profiles"]["two-led"]["fit_count"] += 1
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("wrong fit designators", self.check_failed(self.result(), "assembly:horse-sagittarius"))

    def test_wrong_bom_quantity_is_rejected_after_rehash(self):
        name = "variants/snake-leo/manufacturing-draft/four-led-bom-review.csv"
        path = self.root / name
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
        rows[0]["Quantity"] = "2"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        self.rehash(name, "assembly-review-manifest.json")
        self.assertIn("wrong fitted quantity", self.check_failed(self.result(), "assembly:snake-leo"))

    def test_rehashed_pnp_side_change_still_fails_native_anchor_check(self):
        name = "variants/horse-sagittarius/manufacturing-draft/pnp-all.csv"
        path = self.root / name
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")), delimiter="\t"))
        next(row for row in rows if row["Designator"] == "D3")["Layer"] = "T"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
        self.rehash(name)
        self.assertIn("PnP side differs", self.check_failed(self.result(), "assembly:horse-sagittarius"))

    def test_valid_crc_with_changed_gerber_member_fails_member_hash(self):
        name = "variants/snake-leo/manufacturing-draft/snake-leo-gerber.zip"
        path = self.root / name
        with zipfile.ZipFile(path) as archive:
            members = {info.filename: archive.read(info.filename) for info in archive.infolist()}
        members["Gerber_TopLayer.GTL"] += b"\nG04 altered export*\n"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for filename, data in members.items():
                archive.writestr(filename, data)
        self.rehash(name)
        self.assertIn("layer hash/size mismatch", self.check_failed(self.result(), "gerber:snake-leo"))

    def test_corrupt_zip_crc_is_reported(self):
        name = "variants/snake-leo/manufacturing-draft/snake-leo-gerber.zip"
        path = self.root / name
        with zipfile.ZipFile(path) as archive:
            members = {info.filename: archive.read(info.filename) for info in archive.infolist()}
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
            for filename, data in members.items():
                archive.writestr(filename, data)
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo("Gerber_TopLayer.GTL")
            start = info.header_offset
        data = bytearray(path.read_bytes())
        name_len = int.from_bytes(data[start + 26:start + 28], "little")
        extra_len = int.from_bytes(data[start + 28:start + 30], "little")
        data[start + 30 + name_len + extra_len] ^= 1
        path.write_bytes(data)
        self.rehash(name)
        self.assertIn("CRC", self.check_failed(self.result(), "gerber:snake-leo"))

    def test_manifest_path_cannot_escape_delivery_directory(self):
        path = self.root / "variants/common/export-manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["files"]["../outside.json"] = {"sha256": "0" * 64, "size": 1}
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("Invalid manifest path", self.check_failed(self.result(), "export_file:../outside.json"))

    def test_native_journal_tickets_and_tombstones(self):
        def line(meta, body):
            return json.dumps(meta) + "||" + json.dumps(body) + "|"
        payload = "\n".join([
            line({"type": "DOCHEAD"}, {"uuid": "board", "docType": "PCB", "client": "b"}),
            line({"type": "LINE", "id": "route", "ticket": 9}, {"x": 9}),
            line({"type": "LINE", "id": "route", "ticket": 3}, {"x": 3}),
            line({"type": "LINE", "id": "deleted", "ticket": 4}, {"x": 4}),
            line({"type": "LINE", "id": "deleted", "ticket": 5}, ""),
            line({"type": "LINE", "id": "deleted", "ticket": 2}, {"x": 2}),
            line({"type": "DOCHEAD"}, {"uuid": "board", "docType": "PCB", "client": "a"}),
            line({"type": "LINE", "id": "route", "ticket": 9}, {"x": 10}),
            line({"type": "DOCHEAD"}, {"uuid": "board", "docType": "PCB", "client": "c"}),
            line({"type": "LINE", "id": "route", "ticket": 9}, {"x": 11}),
        ])
        records = DELIVERY._replay(payload)["board"]["records"]
        self.assertEqual(records[("LINE", "route")], {"x": 10})
        self.assertNotIn(("LINE", "deleted"), records)


if __name__ == "__main__":
    unittest.main()
