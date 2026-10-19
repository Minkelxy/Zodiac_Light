"""An artwork revision must not weaken the ordinary PCB physical baseline."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "standard_delivery_revision", REPO / "hardware/nfc-talisman/scripts/check_standard_delivery.py")
STANDARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STANDARD)


def journal(uuid, records):
    rows = [(dict(type="DOCHEAD"), dict(uuid=uuid, docType="PCB", client="test"))]
    rows += [(dict(type=kind, id=ident, ticket=index), body)
             for index, ((kind, ident), body) in enumerate(records.items(), 1)]
    return "\n".join(json.dumps(head) + "||" + json.dumps(body) + "|" for head, body in rows) + "\n"


class StandardSilkRevisionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.uuid = STANDARD.STANDARD_UUIDS["horse-sagittarius"]
        shape = [[0, 0, "L", 10, 0, 10, 10, 0, 0]]
        fill = dict(layerId=3, netName="", fillStyle="SOLID", width=.2,
                    path=shape, locked=True, refs=None)
        self.before = {
            ("FILL", "old-silk"): copy.deepcopy(fill),
            ("FILL", "old-mask"): dict(fill, layerId=5),
            ("FILL", "antenna"): dict(fill, layerId=1, netName="ANT"),
            ("PAD", "drill"): dict(layerId=12, centerX=10, centerY=20, hole=dict(width=1), plated=False),
            ("STRING", "factory-label"): dict(layerId=3, text="LRY"),
        }
        old_created = [dict(id="old-silk", kind="silk", layer=3), dict(id="old-mask", kind="mask", layer=5)]
        native = self.root / "historical.epro2"
        payload = "".join(journal(uuid, self.before if uuid == self.uuid else {})
                          for uuid in sorted(STANDARD.ORIGINAL_FIVE))
        with zipfile.ZipFile(native, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("project.epru", payload)
        old = dict(boards=[dict(uuid=uuid, created=old_created if uuid == self.uuid else [])
                           for uuid in STANDARD.STANDARD_UUIDS.values()],
                   native_project=dict(path=native.name, size=native.stat().st_size,
                                       sha256=hashlib.sha256(native.read_bytes()).hexdigest()))
        manifest = self.root / "before-manifest.json"
        manifest.write_text(json.dumps(old), encoding="utf-8")
        source = self.root / "before-source.jsonl"
        source.write_text(journal(self.uuid, self.before), encoding="utf-8")
        self.evidence = dict(path=source.name, sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                             owned_silk_ids=["old-silk"], manifest_path=manifest.name,
                             manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
        self.current = copy.deepcopy(self.before)
        self.current[("FILL", "new-silk")] = self.current.pop(("FILL", "old-silk"))
        self.current[("FILL", "new-silk")]["path"][0][0] = 2
        self.current[("FILL", "new-mask")] = self.current.pop(("FILL", "old-mask"))
        self.current[("FILL", "new-mask")]["refs"] = [None]
        self.created = [dict(id="new-silk", kind="silk", layer=3), dict(id="new-mask", kind="mask", layer=5)]

    def validate(self):
        return STANDARD._check_silk_revision(self.root, self.uuid, self.evidence, self.current, self.created)

    def test_owned_silk_can_change_and_equal_mask_can_receive_a_new_id(self):
        self.assertIn("1 -> 1 Top-silk", self.validate())

    def test_mask_contour_change_is_rejected(self):
        self.current[("FILL", "new-mask")]["path"][0][0] += .02
        with self.assertRaisesRegex(ValueError, "mask geometry/properties changed"):
            self.validate()

    def test_mask_property_change_is_rejected(self):
        self.current[("FILL", "new-mask")]["width"] = 0
        with self.assertRaisesRegex(ValueError, "mask geometry/properties changed"):
            self.validate()

    def test_copper_and_drill_changes_are_rejected(self):
        for key, field, value in [(("FILL", "antenna"), "netName", ""),
                                  (("PAD", "drill"), "centerX", 11)]:
            with self.subTest(key=key):
                original = self.current[key][field]
                self.current[key][field] = value
                with self.assertRaisesRegex(ValueError, "protected artwork"):
                    self.validate()
                self.current[key][field] = original

    def test_unowned_top_silk_is_not_exempt(self):
        del self.current[("STRING", "factory-label")]
        with self.assertRaisesRegex(ValueError, "protected artwork"):
            self.validate()

    def test_ownership_cannot_be_expanded_to_cover_the_antenna(self):
        self.evidence["owned_silk_ids"].append("antenna")
        with self.assertRaisesRegex(ValueError, "ownership differs"):
            self.validate()

    def test_new_mask_opening_is_rejected(self):
        self.current[("FILL", "extra-mask")] = copy.deepcopy(self.current[("FILL", "new-mask")])
        self.created.append(dict(id="extra-mask", kind="mask", layer=5))
        with self.assertRaisesRegex(ValueError, "Additional mask opening"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
