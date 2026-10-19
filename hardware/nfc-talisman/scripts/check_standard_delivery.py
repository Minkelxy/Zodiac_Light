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
ORIGINAL_UUIDS = {"core": "eb14b9eaec4f920c", "horse-sagittarius": "4a4719695b24dc2b",
                  "snake-leo": "fe8ee4534ee0b941"}
STANDARD_UUIDS = {"horse-sagittarius": "7b9104396cd59877", "snake-leo": "8bb2139a68d10671"}
TWELVE_UUIDS = {"constellations-a": "da4d85d9f04979eb", "constellations-b": "9883f07d70af99ab",
                "zodiac-a": "abc3d3a5e6e4793c", "zodiac-b": "215baefd4debbd14"}
ORIGINAL_FIVE = set(ORIGINAL_UUIDS.values()) | set(STANDARD_UUIDS.values())
SHARED_NINE = ORIGINAL_FIVE | set(TWELVE_UUIDS.values())
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


def _native_documents(root: Path, native: dict[str, Any]) -> dict[str, Any]:
    path = _BASE._relative(root, native["path"])
    _BASE._file_check(path, native)
    with _BASE._archive(path) as archive:
        journals = [name for name in archive.namelist() if name.endswith(".epru")]
        _BASE._require(len(journals) == 1, "Expected one native journal")
        return _BASE._replay(archive.read(journals[0]).decode("utf-8-sig"))


def _pcb_uuids(documents: dict[str, Any]) -> set[str]:
    return {uuid for uuid, doc in documents.items() if doc["head"]["docType"] == "PCB"}


def _canonical_hash(geometry: Any) -> str:
    return _BASE._digest(json.dumps(geometry, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=True, allow_nan=False).encode("ascii"))


def _ring_points(path: list[Any]) -> list[list[float]]:
    _BASE._require(len(path) >= 9 and path[2] == "L" and len(path) % 2 == 1,
                   "Expected a closed straight-line artwork contour")
    values = path[:2] + path[3:]
    points = [values[index:index + 2] for index in range(0, len(values), 2)]
    _BASE._require(all(type(value) in (float, int) and math.isfinite(value) for value in values)
                   and _same_path(points[0], points[-1]), "Invalid or unclosed artwork contour")
    return points[:-1]


def _contour_same(first: list[Any], second: list[Any]) -> bool:
    left, right = _ring_points(first), _ring_points(second)
    if len(left) != len(right):
        return False
    size = len(left)
    return any(all(_same_path(left[index], right[(start + direction * index) % size]) for index in range(size))
               for start in range(size) if _same_path(left[0], right[start]) for direction in (1, -1))


def _polygon_same(first: list[Any], second: list[Any]) -> bool:
    if len(first) != len(second) or not _contour_same(first[0], second[0]):
        return False
    remaining = list(second[1:])
    for hole in first[1:]:
        matching = [index for index, actual in enumerate(remaining) if _contour_same(hole, actual)]
        if not matching:
            return False
        remaining.pop(matching[0])
    return not remaining


def _border_paths(geometry: dict[str, Any], center: list[float]) -> list[Any]:
    _BASE._require(geometry["units"] == "mm" and geometry["coordinate_system"] == "cover_top_left_x_right_y_down",
                   "Unexpected border coordinate system")

    def ring(points: list[list[float]]) -> list[Any]:
        _BASE._require(isinstance(points, list) and len(points) >= 3
                       and all(isinstance(point, list) and len(point) == 2
                               and all(type(value) in (float, int) and math.isfinite(value) for value in point)
                               for point in points), "Invalid border polygon coordinates")
        transformed = [[(center[0] + x - 18.5) / .0254, (center[1] + 18.5 - y) / .0254] for x, y in points]
        if transformed[0] != transformed[-1]:
            transformed.append(transformed[0])
        return transformed[0] + ["L"] + [number for point in transformed[1:] for number in point]

    return [[ring(polygon["exterior"]), *[ring(hole) for hole in polygon["holes"]]]
            for polygon in geometry["polygons"]]


def _check_border(metadata: dict[str, Any], native_paths: list[Any], center: list[float]) -> str:
    """Bind a border's recorded local contours to separate Top-silk fills."""
    _BASE._require(metadata["version"] == "af37-double-contour-ticks-v1" and metadata["layer_id"] == 3
                   and metadata["units"] == "mm" and metadata["coordinate_system"] == "cover_top_left_x_right_y_down",
                   "Unexpected uniform border version/layer/coordinates")
    expected_parameters = {"across_flats_mm": 37., "outer_center_inset_mm": .7, "outer_width_mm": .22,
                           "inner_center_inset_mm": 2.1, "inner_width_mm": .24, "tick_center_inset_mm": 1.35,
                           "tick_centerline_length_mm": .42, "tick_width_mm": .22, "tick_pitch_mm": 2.4,
                           "corner_dot_diameter_mm": .28, "content_safe_inset_mm": 3.,
                           "cardinal_bridge_width_mm": 4., "postage_drill_diameter_mm": .4,
                           "postage_hole_pitch_mm": .72, "postage_holes_per_bridge": 5}
    _BASE._require(all(metadata["parameters"].get(key) == value for key, value in expected_parameters.items()),
                   "Uniform border manufacturing/design parameters changed")
    for geometry, fingerprint in (("geometry", "geometry_sha256"), ("content_safe_geometry", "content_safe_geometry_sha256")):
        _BASE._require(_canonical_hash(metadata[geometry]) == metadata[fingerprint], "Border canonical geometry fingerprint differs")
    expected = _border_paths(metadata["geometry"], center)
    _BASE._require(len(expected) == len(native_paths) == metadata["polygon_count"] and bool(expected),
                   "Border polygon count differs from its separate native silk fills")
    remaining = list(native_paths)
    for polygon in expected:
        matches = [index for index, actual in enumerate(remaining) if _polygon_same(polygon, actual)]
        _BASE._require(bool(matches), "Border contour missing from the native artwork geometry")
        remaining.pop(matches[0])
    for key, minimum in (("board_edge", .5), ("postage_holes", .2), ("cardinal_bridges", .3),
                         ("existing_art", .2), ("aperture_mask", .2), ("disconnected_features", .2)):
        value = metadata["clearances_mm"][key]
        _BASE._require(value is None and key in ("aperture_mask", "existing_art")
                       or type(value) in (float, int) and math.isfinite(value) and value >= minimum - .00001,
                       "Reported border clearance failed: " + key)
    return f"{len(expected)} separate Top-silk border polygons match canonical geometry; uniform parameters/recorded clearances pass"


def _check_border_generator(root: Path, evidence: dict[str, Any]) -> str:
    expected = "hardware/nfc-talisman/scripts/pcb_cover_border.py"
    _BASE._require(evidence["path"] == expected, "Unexpected uniform border generator")
    _BASE._file_check(_BASE._relative(root.parents[1], expected), {"sha256": evidence["sha256"]})
    return "Uniform border generator SHA matches its frozen source"


def _check_border_audit(root: Path) -> str:
    report = _BASE._json(root / "variants/twelve-options/border-artwork-audit.json")
    _BASE._require(report["schema_version"] == 1 and report["status"] == "passed" and not report["errors"],
                   "Independent border/physical revision audit failed")
    _BASE._require(report["auditor"]["path"] == "hardware/nfc-talisman/scripts/audit_cover_borders.py",
                   "Unexpected independent border auditor")
    _BASE._file_check(_BASE._relative(root.parents[1], report["auditor"]["path"]), report["auditor"])
    _check_border_generator(root, report["border_generator"])
    design = _BASE._json(root / "variants/twelve-options/design-manifest.json")
    artwork = _BASE._json(root / STANDARD / "artwork/manifest.json")
    _BASE._require(report["border_generator"] == design["border_generator"] == artwork["border_generator"],
                   "Border generator source bindings differ between deliveries")
    required_inputs = {"variants/twelve-options/design-manifest.json", STANDARD + "/artwork/manifest.json"}
    expected_metadata = {}
    for variant in VARIANTS:
        name = STANDARD + "/artwork/" + artwork["variants"][variant]["geometry_json"]
        required_inputs.add(name)
        artifact = _BASE._json(_BASE._relative(root, name))
        for face, value in artifact["faces"].items():
            expected_metadata[f"standard/{variant}/{face}"] = value["source_metadata"]["border"]
    for panel in design["panels"]:
        name = "variants/twelve-options/" + panel["geometry"]
        required_inputs.add(name)
        for cover in _BASE._json(_BASE._relative(root, name))["covers"]:
            expected_metadata["twelve/" + cover["id"]] = cover["details"]["border"]
    _BASE._require(required_inputs <= set(report["inputs"]), "Independent border audit omits current design inputs")
    for name, metadata in report["inputs"].items():
        _BASE._file_check(_BASE._relative(root, name), metadata)
    expected = {f"standard/{variant}/{face}" for variant in VARIANTS for face in ("front", "rear")}
    expected |= {"twelve/" + cover for panel in design["panels"] for cover in panel["covers"]}
    _BASE._require(set(report["covers"]) == expected and len(expected) == 24,
                   "Independent border audit does not cover all 24 product faces")
    for key, evidence in report["covers"].items():
        _BASE._require(evidence["passed"] is True and evidence["native_border_paths_match"] is True
                       and evidence["geometry_sha256"] == expected_metadata[key]["geometry_sha256"],
                       "Independent border geometry check failed: " + key)
    _BASE._require(set(report["physical_retention"]) == set(TWELVE_UUIDS) | set(VARIANTS)
                   and all(evidence["passed"] is True for evidence in report["physical_retention"].values()),
                   "Independent audit did not retain all six panel physical/mask baselines")
    _BASE._require(all(evidence["baseline"] in report["inputs"] and evidence["current"] in report["inputs"]
                       for evidence in report["physical_retention"].values()),
                   "Independent physical audit omits a before/current native source fingerprint")
    return "Independent 24-face border/clearance and six-panel physical/mask retention audit is source-hash bound"


def _check_silk_revision(root: Path, uuid: str, evidence: dict[str, Any],
                         current: dict[tuple[str, str], Any], created: list[dict[str, Any]]) -> str:
    """Permit an owned Top-silk revision; retain mask and every other primitive.

    Ownership is bound to the archived pre-revision manifest and five-PCB
    snapshot, rather than inferred from layer numbers in a mutable new source.
    Mask IDs may be regenerated by the importer, but their paths and all other
    normalized manufacturing properties must still match one for one.
    """
    _BASE._require(uuid in STANDARD_UUIDS.values(), "Only the two ordinary PCBs may revise owned silk")
    source = _BASE._relative(root, evidence["path"])
    _BASE._file_check(source, {"sha256": evidence["sha256"]})
    before = _records(source, uuid)
    old_path = _BASE._relative(root, evidence["manifest_path"])
    _BASE._file_check(old_path, {"sha256": evidence["manifest_sha256"]})
    old = _BASE._json(old_path)
    _BASE._require(not old.get("archive_scope"), "Revision baseline must be the historical five-PCB delivery")
    old_boards = {board["uuid"]: board for board in old["boards"]}
    _BASE._require(set(old_boards) == set(STANDARD_UUIDS.values()), "Incorrect historical ordinary PCB set")
    old_docs = _native_documents(root, old["native_project"])
    _BASE._require(_pcb_uuids(old_docs) == ORIGINAL_FIVE, "Historical five-PCB snapshot changed scope")
    _BASE._require(_BASE._design_records(before) == _BASE._design_records(old_docs[uuid]["records"]),
                   "Revision source differs from the historical five-PCB snapshot")
    old_created = old_boards[uuid]["created"]

    def owned(records: dict[tuple[str, str], Any], entries: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
        _BASE._require(len({item["id"] for item in entries}) == len(entries), "Duplicate owned artwork IDs")
        silk, mask = set(), set()
        for item in entries:
            _BASE._require(item["kind"] in ("silk", "mask"), "Unexpected owned artwork kind")
            layer = 3 if item["kind"] == "silk" else 5
            body = records.get(("FILL", item["id"]))
            _BASE._require(isinstance(body, dict) and body.get("layerId") == item["layer"] == layer
                           and body.get("netName") == "" and body.get("fillStyle") in (0, "SOLID")
                           and type(body.get("width")) in (int, float) and body["width"] in (0, .2),
                           "Invalid owned non-net silk/mask fill")
            (silk if layer == 3 else mask).add(item["id"])
        actual = {key[1] for key, body in records.items() if key[0] == "FILL" and body.get("layerId") in (3, 5)}
        _BASE._require(actual == silk | mask, "Unowned or missing ordinary artwork fill")
        return silk, mask

    old_silk, old_mask = owned(before, old_created)
    new_silk, new_mask = owned(current, created)
    declared = evidence["owned_silk_ids"]
    _BASE._require(len(declared) == len(set(declared)) and set(declared) == old_silk,
                   "Revision ownership differs from the historical manifest")
    old_normal, new_normal = _BASE._design_records(before), _BASE._design_records(current)
    remaining = [new_normal[("FILL", ident)] for ident in sorted(new_mask)]
    for ident in sorted(old_mask):
        expected = old_normal[("FILL", ident)]
        properties = {key: value for key, value in expected.items() if key != "path"}
        matches = [index for index, actual in enumerate(remaining)
                   if properties == {key: value for key, value in actual.items() if key != "path"}
                   and _same_path(expected["path"], actual["path"])]
        _BASE._require(bool(matches), "Ordinary mask geometry/properties changed during the silk revision")
        remaining.pop(matches[0])
    _BASE._require(not remaining, "Additional mask opening introduced during the silk revision")
    _BASE._require(_protected(before, old_silk | old_mask) == _protected(current, new_silk | new_mask),
                   "Silk revision changed copper, pads, components, drilling, outlines or other protected artwork")
    _BASE._require(_objects(before) == _objects(current), "Silk revision changed color objects")
    return f"Historical ownership verified; {len(old_silk)} -> {len(new_silk)} Top-silk fills; {len(old_mask)} mask fills and all other physical primitives retained"


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
        _BASE._require({b["variant"]: b["uuid"] for b in manifest["boards"]} == STANDARD_UUIDS
                       and {key: value["uuid"] for key, value in manifest["original_baselines"].items()} == ORIGINAL_UUIDS,
                       "Ordinary/original PCB identities differ from the fixed delivery")
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
            border_required = "archive_scope" in manifest or "border_generator" in art_manifest
            if border_required:
                _check_border_generator(root, art_manifest["border_generator"])
            artifacts = {}
            for variant in VARIANTS:
                artifact = _BASE._json(folder / art_manifest["variants"][variant]["geometry_json"])
                for name, digest in artifact["source_files_sha256"].items():
                    # Artwork manifests are repository-relative, not hardware-relative.
                    _BASE._file_check(_BASE._relative(root.parents[1], name), {"sha256": digest})
                _BASE._require(artifact["process"]["color_printing"] is False and artifact["process"]["decorative_copper"] is False,
                               "Artwork process adds colored printing or decorative copper")
                if border_required:
                    for face_name, face in artifact["faces"].items():
                        border = [shape for shape in face["silk_polygons"]
                                  if shape["category"] == "textured_octagonal_border_and_inner_divider"]
                        _BASE._require(all(shape["layer_id"] == 3 and shape["id"].startswith("cover_border_") for shape in border),
                                       "Ordinary border is not separate owned Top silk")
                        center = [20.5, 76.5] if face_name == "front" else [79.5, 23.5]
                        _check_border(face["source_metadata"]["border"], [shape["path_mil"] for shape in border], center)
                artifacts[variant] = artifact
            imported = _BASE._json(_BASE._relative(root, manifest["artwork_file"]))
            for variant in VARIANTS:
                _BASE._require(imported["variants"][variant]["faces"] == artifacts[variant]["faces"], "Import geometry differs from current artifact")
            holder["artifacts"] = artifacts
            return "Artwork hashes/source hashes match; import geometry equals both generated artifacts"

        check("ordinary_artwork_sources", artwork_sources)
        if "archive_scope" in manifest:
            check("uniform_border_independent_audit", lambda: _check_border_audit(root))

        def load_archive() -> str:
            documents = _native_documents(root, manifest["native_project"])
            if "archive_scope" in manifest:
                scope = manifest["archive_scope"]["pcb_uuids"]
                _BASE._require(len(scope) == 9 and set(scope) == SHARED_NINE and _pcb_uuids(documents) == SHARED_NINE,
                               "Shared native archive must contain exactly the fixed nine PCB documents")
                _BASE._require(manifest["native_project"]["path"] == "variants/twelve-options/eda/native/nfc-twelve-options.epro2"
                               and manifest["historical_five_pcb_snapshot"] == STANDARD + "/eda/native/nfc-color-and-green-white.epro2",
                               "Current shared archive and historical five-PCB snapshot paths differ")
                twelve = _BASE._json(root / "variants/twelve-options/export-manifest.json")
                _BASE._require({b["key"]: b["uuid"] for b in twelve["boards"]} == TWELVE_UUIDS
                               and set(twelve["existing"]) == ORIGINAL_FIVE, "Incorrect linked twelve-option PCB scope")
                _BASE._require(all(manifest["native_project"][key] == twelve["native_project"][key]
                                   for key in ("path", "sha256", "size")), "Current deliveries do not share the same nine-PCB archive")
                for board in manifest["boards"]:
                    linked = twelve["existing"][board["uuid"]]
                    _BASE._require(linked["path"] == board["source"] and linked["sha256"] == board["source_sha256"]
                                   and linked["uuid"] == board["uuid"], "Twelve-option ordinary source link is stale")
                    _BASE._require(linked["retention_policy"] == "owned_top_silk_revision_physical_and_mask_preserved"
                                   and linked["revision_before"] == board["border_revision"]["before"]
                                   and board["border_revision"]["status"] == "saved_reopened",
                                   "Explicit saved ordinary silk-revision evidence is missing")
                for board in twelve["boards"]:
                    source = _BASE._relative(root, board["source"]["path"])
                    _BASE._file_check(source, {"sha256": board["source"]["sha256"]})
                    _BASE._require(_BASE._design_records(_records(source, board["uuid"])) ==
                                   _BASE._design_records(documents[board["uuid"]]["records"]),
                                   "Shared archive differs from a current twelve-option PCB source")
                holder["twelve"] = twelve
                detail = "original three, two revised ordinary and four added PCB documents share the exact nine-PCB archive"
            else:
                _BASE._require(_pcb_uuids(documents) == ORIGINAL_FIVE,
                               "Historical native archive must contain the original three and two ordinary PCB documents")
                detail = "historical original core/color PCBs plus two ordinary PCBs present"
            holder["documents"] = documents
            return "ZIP CRC and SHA/size pass; " + detail

        check("shared_nine_pcb_native_archive" if "archive_scope" in manifest else "five_pcb_native_archive", load_archive)
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
                if "twelve" in holder:
                    check(f"ordinary_silk_revision:{variant}", lambda board=board: _check_silk_revision(
                        root, board["uuid"], holder["twelve"]["existing"][board["uuid"]]["revision_before"],
                        documents[board["uuid"]]["records"], board["created"]))
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
