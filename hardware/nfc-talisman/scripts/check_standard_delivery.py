"""Read-only validation of the separate ordinary green-mask/white-silk PCBs.

Archive integrity is distinct from supplier CAM and physical acceptance. This
entry point does not contact EasyEDA or rewrite sources and historical audits.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any, Callable


_SPEC = importlib.util.spec_from_file_location("_nfc_original_delivery", Path(__file__).with_name("check_delivery.py"))
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
VARIANTS = _BASE.VARIANTS
STANDARD = "variants/standard-green-white"
PHYSICAL_KINDS = {"COMPONENT", "ATTR", "PAD_NET", "PAD", "LINE", "ARC", "VIA", "POLY",
                  "FILL", "POUR", "REGION", "STRING", "NET", "TRACK", "RECT", "CIRCLE", "TEXT"}
PRESERVED_GERBER = {
    "Gerber_TopLayer.GTL", "Gerber_BottomLayer.GBL", "Gerber_BoardOutlineLayer.GKO",
    "Gerber_TopPasteMaskLayer.GTP", "Gerber_BottomPasteMaskLayer.GBP",
    "Gerber_BottomSolderMaskLayer.GBS", "Gerber_BottomSilkscreenLayer.GBO",
    "Drill_PTH_Through.DRL", "Drill_PTH_Through_Via.DRL", "Drill_NPTH_Through.DRL",
}


def _records(source: Path, uuid: str) -> dict[tuple[str, str], Any]:
    documents = _BASE._replay(source.read_text(encoding="utf-8-sig"))
    _BASE._require(uuid in documents and documents[uuid]["head"]["docType"] == "PCB", "Incorrect PCB source UUID")
    return documents[uuid]["records"]


def _protected(records: dict[tuple[str, str], Any], excluded: set[str] | None = None) -> dict[tuple[str, str], Any]:
    excluded = excluded or set()
    result = {}
    normalized = _BASE._design_records(records)
    for key, body in records.items():
        if key[0] not in PHYSICAL_KINDS or key[1] in excluded:
            continue
        result[key] = normalized.get(key, body)
    return result


def _objects(records: dict[tuple[str, str], Any]) -> dict[tuple[str, str], Any]:
    return {key: body for key, body in records.items() if key[0] == "OBJ"}


def _same_path(expected: Any, actual: Any, tolerance: float = .001) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(
            _same_path(left, right, tolerance) for left, right in zip(expected, actual))
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual) and abs(expected - actual) <= tolerance
    return expected == actual


def _gerber_commands(data: bytes, *, remove_color_image: bool = False) -> list[str]:
    """Bind used apertures, ignoring unused definitions and region apertures.

    EasyEDA assigns fresh aperture numbers and unused random circular sizes on
    each export. Region boundaries use coordinates, rather than the selected
    aperture width. Only the old color-OBJ Image section on bottom mask may be
    removed when comparing the ordinary finish; original pads remain checked.
    """
    text = data.decode("utf-8-sig")
    result, apertures = [], {}
    active, region, image = None, False, False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "G04 Image Start*":
            image = True
        if line == "G04 Image End*":
            image = False
            continue
        if remove_color_image and image:
            continue
        if not line or line.startswith(("G04", ";")):
            continue
        definition = re.fullmatch(r"%ADD(\d+)(.+)\*%", line)
        if definition:
            apertures[definition[1]] = definition[2]
            continue
        selection = re.fullmatch(r"(?:G54)?D(\d+)\*", line)
        if selection and int(selection[1]) >= 10:
            active = selection[1]
            continue
        if line == "G36*":
            region = True
        elif line == "G37*":
            region = False
        elif not region and re.search(r"D0[13]\*$", line):
            _BASE._require(active in apertures, "Drawing aperture is undefined")
            result.append("APERTURE:" + apertures[active])
        result.append(line)
    return result


def _check_gerber(root: Path, board: dict[str, Any]) -> str:
    variant = board["variant"]
    path = _BASE._relative(root, board["gerber"])
    members = _BASE._json(_BASE._relative(root, board["gerber_members"]))
    expected = {item["name"]: item for item in members}
    _BASE._require(len(expected) == len(members), "Duplicate Gerber member records")
    _BASE._require(not any(name.startswith("Fabrication_Colorful") or name.endswith((".FCTS", ".FCBS", ".FCBO", ".FCBM"))
                           for name in expected), "Color fabrication members remain")
    _BASE._require(PRESERVED_GERBER | {"Gerber_TopSilkscreenLayer.GTO", "Gerber_TopSolderMaskLayer.GTS"} <= set(expected),
                   "Required ordinary Gerber/drill layer missing")
    original = root / "variants" / variant / "manufacturing-draft" / f"{variant}-gerber.zip"
    with _BASE._archive(path) as archive, _BASE._archive(original) as before:
        _BASE._require(set(archive.namelist()) == set(expected), "ZIP members differ from manifest")
        for name, metadata in expected.items():
            data = archive.read(name)
            _BASE._require(len(data) == metadata["size"] and _BASE._digest(data) == metadata["sha256"],
                           f"Gerber member SHA/size differs: {name}")
        for name in PRESERVED_GERBER:
            # Color OBJ images generated a bottom-mask Image proxy in the old
            # colored export. Ordinary PCB copies intentionally remove that
            # image section; all original pad openings still compare exactly.
            _BASE._require(_gerber_commands(archive.read(name)) == _gerber_commands(
                before.read(name), remove_color_image=name == "Gerber_BottomSolderMaskLayer.GBS"),
                           f"Protected Gerber/drill commands changed: {name}")
        for name in ("Gerber_TopSilkscreenLayer.GTO", "Gerber_TopSolderMaskLayer.GTS"):
            after_commands = _gerber_commands(archive.read(name))
            _BASE._require(after_commands != _gerber_commands(before.read(name)), f"New ordinary artwork not exported: {name}")
            _BASE._require("G36*" in after_commands and "G37*" in after_commands, f"Native fill regions missing from {name}")
        # Preserve the original raw drill duplicates as evidence, while retaining
        # their separate CAM selection requirement in the result limitations.
        _BASE._require(_gerber_commands(archive.read("Drill_PTH_Through.DRL")) ==
                       _gerber_commands(archive.read("Drill_PTH_Through_Via.DRL")),
                       "The two PTH programs no longer describe identical drill locations")
    return f"CRC and {len(expected)} hashes match; effective copper/paste/outline/drill/pad-mask commands unchanged; color Image mask proxy removed"


def _check_board(root: Path, board: dict[str, Any], artifact: dict[str, Any],
                 archive_records: dict[tuple[str, str], Any], baseline: dict[str, Any]) -> str:
    variant, uuid = board["variant"], board["uuid"]
    _BASE._require(board["status"] == "applied_saved_reopened" and board["saved_reopened"] is True,
                   "PCB is not saved/reopened after import")
    _BASE._require(board["drc"] == [] and board["color_silkscreen_export"] is False,
                   "Clean native DRC or ordinary export evidence missing")
    source = _BASE._relative(root, board["source"])
    _BASE._file_check(source, {"sha256": board["source_sha256"]})
    current = _records(source, uuid)
    _BASE._require(not _objects(current) and not _objects(archive_records), "New PCB still references a colored OBJ")
    base_path = _BASE._relative(root, board["base_copy_source"])
    _BASE._file_check(base_path, {"sha256": board["base_copy_sha256"]})
    copied = _records(base_path, uuid)
    original = _records(_BASE._relative(root, baseline["source"]), baseline["uuid"])
    _BASE._require(_protected(copied) == _protected(original), "Copied physical primitives differ from colored source")
    shapes = []
    for face_name, face in artifact["faces"].items():
        _BASE._require(face_name in ("front", "rear"), "Unexpected artwork face")
        _BASE._require(face["silk_layer_id"] == 3 and face["mask_layer_id"] == 5, "Artwork target layers differ")
        if face_name == "front":
            _BASE._require(not face["mask_opening_polygons"], "Front animal must not create a mask opening")
        else:
            _BASE._require(face["minimum_silk_mask_gap_mm"] >= .15 and face["silk_mask_overlap_mm2"] == 0,
                           "Reported ordinary silk/mask clearance failed")
        shapes += [("silk", shape) for shape in face["silk_polygons"]]
        shapes += [("mask", shape) for shape in face["mask_opening_polygons"]]
    made = board["created"]
    _BASE._require(len(made) == len(shapes) and len({entry["id"] for entry in made}) == len(made),
                   "Imported artwork has missing or duplicate primitive IDs")
    added = {entry["id"] for entry in made}
    _BASE._require(_protected(current, added) == _protected(copied), "Copper, components, net/pads, drilling or outlines changed")
    _BASE._require(_protected(archive_records, added) == _protected(copied), "epro2 protected primitives differ from saved copy")
    _BASE._require({key for key in current if key[0] == "FILL" and current[key].get("layerId") in (3, 5)} ==
                   {("FILL", ident) for ident in added}, "Unexpected or missing silk/mask decorations")
    _BASE._require(_BASE._design_records(current) == _BASE._design_records(archive_records),
                   "epro2 physical primitives differ from final source")
    for item, (kind, expected) in zip(made, shapes):
        body = current.get(("FILL", item["id"]))
        _BASE._require(item["kind"] == kind and isinstance(body, dict), "Imported native fill kind differs from artwork")
        _BASE._require(body["layerId"] == expected["layer_id"] == (3 if kind == "silk" else 5), "Fill on wrong manufacturing layer")
        _BASE._require(body["netName"] == "" and type(body["width"]) in (int, float)
                       and body["width"] in (0, .2) and body["fillStyle"] in (0, "SOLID"),
                       "Decoration is not a non-net SOLID fill with known 0/0.2mil native width")
        _BASE._require(item["requested_width_mil"] == 0 and item["actual_width_mil"] == body["width"],
                       "Recorded native width differs from the saved source")
        _BASE._require(_same_path(expected["path_mil"], body["path"]), f"Native artwork path differs: {expected['id']}")
    count = Counter(kind for kind, _ in shapes)
    widths = sorted({current[("FILL", item["id"])]["width"] for item in made})
    _BASE._require(board["actual_width_mil"] == widths, "Board native width summary differs from source")
    return f"{count['silk']} silk / {count['mask']} mask SOLID fills match artifact paths within 0.001mil; reported native widths {widths}mil; protected primitives unchanged"


def validate(root: Path) -> dict[str, Any]:
    """Validate a repository root or its hardware/nfc-talisman directory."""
    root = Path(root).resolve()
    if (root / "hardware/nfc-talisman").is_dir():
        root = root / "hardware/nfc-talisman"
    checks, errors = [], []

    def check(ident: str, action: Callable[[], str]) -> None:
        try:
            checks.append({"id": ident, "passed": True, "detail": action()})
        except Exception as exc:
            errors.append(f"{ident}: {exc}")
            checks.append({"id": ident, "passed": False, "detail": str(exc)})

    holder = {}

    def load_manifest() -> str:
        manifest = _BASE._json(root / STANDARD / "export-manifest.json")
        _BASE._require(manifest["status"] == "ordinary_green_white_pcbs_saved_and_exported", "Incomplete standard export")
        _BASE._require(manifest["soldermask"] == "green" and manifest["silkscreen"] == "white", "Incorrect process finish")
        _BASE._require(manifest["release_status"].startswith("HOLD"), "Manufacturing HOLD must remain")
        _BASE._require(len(manifest["boards"]) == 2 and {b["variant"] for b in manifest["boards"]} == set(VARIANTS),
                       "Expected two independent ordinary variant PCBs")
        holder["manifest"] = manifest
        return f"Two variants; {len(manifest['files'])} recorded files; {manifest['release_status']}"

    check("standard_manifest", load_manifest)
    manifest = holder.get("manifest")
    if manifest is not None:
        for name, metadata in manifest["files"].items():
            check(f"standard_file:{name}", lambda name=name, metadata=metadata: _BASE._file_check(_BASE._relative(root, name), metadata))

        def artwork_sources() -> str:
            folder = root / STANDARD / "artwork"
            art_manifest = _BASE._json(folder / "manifest.json")
            for name, metadata in art_manifest["files"].items():
                _BASE._file_check(_BASE._relative(folder, name), metadata)
            artifacts = {}
            for variant in VARIANTS:
                artifact = _BASE._json(folder / art_manifest["variants"][variant]["geometry_json"])
                for name, digest in artifact["source_files_sha256"].items():
                    # Artwork manifests are repository-relative, not hardware-relative.
                    _BASE._file_check(_BASE._relative(root.parents[1], name), {"sha256": digest})
                _BASE._require(artifact["process"]["color_printing"] is False and artifact["process"]["decorative_copper"] is False,
                               "Artwork process adds colored printing or decorative copper")
                artifacts[variant] = artifact
            imported = _BASE._json(_BASE._relative(root, manifest["artwork_file"]))
            for variant in VARIANTS:
                _BASE._require(imported["variants"][variant]["faces"] == artifacts[variant]["faces"], "Import geometry differs from current artifact")
            holder["artifacts"] = artifacts
            return "Artwork hashes/source hashes match; import geometry equals both generated artifacts"

        check("ordinary_artwork_sources", artwork_sources)

        def load_archive() -> str:
            native = manifest["native_project"]
            path = _BASE._relative(root, native["path"])
            _BASE._file_check(path, native)
            with _BASE._archive(path) as archive:
                journals = [name for name in archive.namelist() if name.endswith(".epru")]
                _BASE._require(len(journals) == 1, "Expected one native journal")
                documents = _BASE._replay(archive.read(journals[0]).decode("utf-8-sig"))
            pcbs = {uuid for uuid, doc in documents.items() if doc["head"]["docType"] == "PCB"}
            expected = {board["uuid"] for board in manifest["boards"]} | {b["uuid"] for b in manifest["original_baselines"].values()}
            _BASE._require(len(expected) == 5 and pcbs == expected, "Native archive must contain original three and two new PCB documents")
            holder["documents"] = documents
            return "ZIP CRC and SHA/size pass; original core/color PCBs plus two ordinary PCBs present"

        check("five_pcb_native_archive", load_archive)
        documents = holder.get("documents")
        if documents is not None:
            def original_retained() -> str:
                blobs = documents.get("BLOB", {}).get("records", {})
                for variant, baseline in manifest["original_baselines"].items():
                    source = _BASE._relative(root, baseline["source"])
                    _BASE._file_check(source, {"sha256": baseline["sha256"]})
                    records = _records(source, baseline["uuid"])
                    archived = documents[baseline["uuid"]]["records"]
                    _BASE._require(_protected(records) == _protected(archived) and _objects(records) == _objects(archived),
                                   f"Original {variant} physical/color artwork changed in full archive")
                    for body in _objects(archived).values():
                        blob = blobs[("BLOB", body["path"].removeprefix("blob:"))]
                        content = base64.b64decode(blob["content"].split(",", 1)[1], validate=True)
                        _BASE._require(content == (root / "variants" / variant / "artwork" / body["fileName"]).read_bytes(),
                                       f"Original {variant} embedded PNG changed")
                historical = _BASE.validate(root)
                _BASE._require(historical["status"] == "passed", "Historical colored delivery integrity failed: " + "; ".join(historical["errors"]))
                return "Three original PCB primitive/OBJ baselines and four colored PNG bytes unchanged; colored delivery still passes"
            check("original_color_pcbs_retained", original_retained)
            artifacts = holder.get("artifacts")
            for board in manifest["boards"]:
                variant = board["variant"]
                check(f"ordinary_gerber:{variant}", lambda board=board: _check_gerber(root, board))
                if artifacts is not None:
                    check(f"ordinary_native:{variant}", lambda board=board, variant=variant: _check_board(
                        root, board, artifacts[variant], documents[board["uuid"]]["records"], manifest["original_baselines"][variant]))
    return {"status": "failed" if errors else "passed", "read_only": True, "checks": checks,
            "checks_run": len(checks), "errors": errors, "release_ready": False,
            "release_status": manifest["release_status"] if manifest else "HOLD_UNVERIFIED_DELIVERY",
            "limitations": ["Archived files and recorded DRC only; no live calls or new ERC/DRC run from this checker.",
                            "Both identical PTH programs remain in raw Gerber; select one during formal supplier CAM.",
                            "C1 sourcing/fit, supplier processing/color/slot approval and physical RF/NFC/optical acceptance remain pending.",
                            "Artwork requests zero outline width; this client normalizes native SOLID width to 0.2mil (0.00508mm). Verify final Gerber region contours independently before CAM approval.",
                            "Animal fine tips may be narrower than 0.15mm; ordinary green/white previews are design simulations."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    result = validate(parser.parse_args().root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
