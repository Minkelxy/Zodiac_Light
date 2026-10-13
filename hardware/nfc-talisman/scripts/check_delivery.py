"""Read-only checks for the current two-variant NFC design delivery.

This standard-library entry point deliberately does not run the numbered live
EasyEDA scripts or rewrite historical audits. ``passed`` means archive integrity,
not CAM approval, procurement approval, or successful physical tests.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Callable
import zipfile


VARIANTS = ("horse-sagittarius", "snake-leo")
EXPECTED_REFS = {"U1", "C1", "CT1", "CT2", *(f"R{i}" for i in range(1, 8)),
                 *(f"D{i}" for i in range(1, 5))}
EXPECTED_PROFILES = {
    "four-led": EXPECTED_REFS - {"CT2"},
    "two-led": EXPECTED_REFS - {"CT2", "D2", "D4"},
}
NATIVE_PATH = "variants/common/eda/native/nfc-two-variants.epro2"
GERBER_NAMES = {
    "Gerber_TopLayer.GTL", "Gerber_BottomLayer.GBL",
    "Gerber_TopSilkscreenLayer.GTO", "Gerber_BottomSilkscreenLayer.GBO",
    "Gerber_TopSolderMaskLayer.GTS", "Gerber_BottomSolderMaskLayer.GBS",
    "Gerber_TopPasteMaskLayer.GTP", "Gerber_BottomPasteMaskLayer.GBP",
    "Gerber_BoardOutlineLayer.GKO", "Gerber_DocumentLayer.GDL",
    "Gerber_DrillDrawingLayer.GDD", "Drill_PTH_Through.DRL",
    "Drill_NPTH_Through.DRL", "Drill_PTH_Through_Via.DRL",
    "Fabrication_ColorfulTopSilkscreen.FCTS",
    "Fabrication_ColorfulBottomSilkscreen.FCBS",
    "Fabrication_ColorfulBoardOutlineLayer.FCBO",
    "Fabrication_ColorfulBoardOutlineMark.FCBM", "PCB下单必读.txt",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _relative(root: Path, name: str) -> Path:
    """Support Windows-authored manifests on other operating systems too."""
    name = name.replace("\\", "/")
    parts = PurePosixPath(name)
    _require(not parts.is_absolute() and ".." not in parts.parts
             and ":" not in name, f"Invalid manifest path: {name}")
    path = root.joinpath(*parts.parts).resolve()
    _require(path.is_relative_to(root.resolve()), f"Path escapes delivery: {name}")
    return path


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_check(path: Path, metadata: dict[str, Any]) -> str:
    data = path.read_bytes()
    _require(isinstance(metadata.get("sha256"), str), "Missing SHA-256")
    _require(_digest(data) == metadata["sha256"], f"SHA-256 mismatch: {path.name}")
    if "size" in metadata:
        _require(len(data) == metadata["size"], f"Size mismatch: {path.name}")
    return f"{len(data)} bytes; SHA-256 matches"


def _netlist(path: Path) -> dict[str, Any]:
    data = _json(path)
    if isinstance(data, list):
        _require(bool(data) and isinstance(data[0], str), "Malformed PCB netlist envelope")
        data = json.loads(data[0])
    _require(isinstance(data, dict) and isinstance(data.get("components"), dict),
             "Missing native components map")
    return data


def _pin_map(net: dict[str, Any]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for ref, component in net["components"].items():
        if str(component.get("props", {}).get("Convert to PCB", "")).lower() == "no":
            continue
        for key, pin in component.get("pinInfoMap", {}).items():
            ident = f"{ref}.{pin.get('number', key)}"
            _require(ident not in pins and bool(pin.get("net")), f"Invalid pin/net: {ident}")
            pins[ident] = pin["net"]
    return pins


def _rows(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")), delimiter=delimiter)
    _require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)),
             f"Missing or duplicate columns: {path.name}")
    rows = list(reader)
    _require(bool(rows), f"Empty table: {path.name}")
    _require(all(None not in row and None not in row.values() for row in rows),
             f"Malformed table row: {path.name}")
    return rows


def _indexed(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result = {}
    for row in rows:
        ref = row["Designator"].strip()
        _require(bool(ref) and ref not in result, f"Empty or duplicate designator: {ref}")
        result[ref] = row
    return result


def _expanded_bom(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result = {}
    for row in rows:
        refs = [ref.strip() for ref in row["Designator"].split(",")]
        _require(int(row["Quantity"]) == len(refs), "Raw BOM quantity differs from designators")
        for ref in refs:
            _require(ref and ref not in result, f"Duplicate raw BOM designator: {ref}")
            result[ref] = row
    return result


def _bom_identity(row: dict[str, str], props: dict[str, Any], ref: str) -> None:
    for column, prop in (("Value", "Value"), ("Manufacturer Part", "Manufacturer Part"),
                         ("Supplier Part", "Supplier Part"), ("Footprint", "FootprintName")):
        _require(row[column] == str(props.get(prop, "")), f"{ref}: BOM {column} differs from netlist")


def _mm(value: str) -> float:
    _require(value.endswith("mm"), f"PnP coordinate missing mm unit: {value}")
    number = float(value[:-2])
    _require(math.isfinite(number), f"Nonfinite PnP coordinate: {value}")
    return number


def _replay(payload: str) -> dict[str, dict[str, Any]]:
    """Resolve journal records by ticket, then smaller client ID, including deletes."""
    documents: dict[str, dict[str, Any]] = {}
    current = None
    client = ""
    for number, line in enumerate(payload.splitlines(), 1):
        if not line.strip():
            continue
        _require("||" in line, f"Invalid native journal line {number}")
        meta_text, body = line.split("||", 1)
        meta = json.loads(meta_text)
        body = body.removesuffix("|")
        data = json.loads(body) if body else None
        if meta["type"] == "DOCHEAD":
            _require(isinstance(data, dict) and bool(data.get("uuid")), "Missing DOCHEAD UUID")
            client = str(data.get("client", ""))
            current = documents.setdefault(data["uuid"], {"head": data, "records": {}, "clocks": {}})
            continue
        _require(current is not None, f"Native record before DOCHEAD at line {number}")
        key = (meta["type"], str(meta.get("id", "")))
        ticket = int(meta.get("ticket", 0))
        clock = current["clocks"].get(key)
        if clock is not None and (ticket < clock[0] or (ticket == clock[0] and client > clock[1])):
            continue
        current["clocks"][key] = (ticket, client)
        # Both an empty body and a JSON empty-string body represent a tombstone.
        if data is None or data == "":
            current["records"].pop(key, None)
        else:
            current["records"][key] = data
    return documents


def _archive(path: Path) -> zipfile.ZipFile:
    archive = zipfile.ZipFile(path)
    try:
        names = archive.namelist()
        _require(len(names) == len(set(names)), f"Duplicate ZIP members: {path.name}")
        _require(archive.testzip() is None, f"ZIP CRC failure: {path.name}")
        return archive
    except Exception:
        archive.close()
        raise


def _design_records(records: dict[tuple[str, str], Any]) -> dict[tuple[str, str], Any]:
    """Compare physical primitives, excluding exporter-specific UI settings.

    The epro2 exporter adds placeholder/display records and nullable FILL refs.
    A top-only, undrilled test pad has no bottom solder-mask opening, so its
    null/zero bottom expansion serialization has no physical meaning.
    """
    kinds = {"COMPONENT", "LINE", "VIA", "PAD", "FILL", "POLY", "ARC", "STRING",
             "OBJ", "POUR", "REGION", "RECT", "CIRCLE", "ATTR", "TEXT", "TRACK"}
    result = {}
    for key, body in records.items():
        if key[0] not in kinds:
            continue
        data = dict(body)
        if key[0] == "FILL" and data.get("refs") in (None, [None]):
            data.pop("refs", None)
        if key[0] == "PAD" and data.get("layerId") == 1 and data.get("hole") is None:
            if data.get("bottomSolderExpansion") in (None, 0):
                data.pop("bottomSolderExpansion", None)
        result[key] = data
    return result


def _check_gerber(root: Path, variant: str) -> str:
    folder = root / "variants" / variant / "manufacturing-draft"
    members = _json(folder / "gerber-members.json")
    _require(isinstance(members, list), "Invalid Gerber member manifest")
    expected = {item["name"]: item for item in members}
    _require(len(expected) == len(members) and set(expected) == GERBER_NAMES,
             "Gerber manifest has missing, unexpected, or duplicate layers")
    with _archive(folder / f"{variant}-gerber.zip") as archive:
        _require(set(archive.namelist()) == set(expected), "ZIP members differ from Gerber manifest")
        for name, metadata in expected.items():
            data = archive.read(name)
            _require(len(data) == metadata["size"] and _digest(data) == metadata["sha256"],
                     f"Gerber layer hash/size mismatch: {name}")
    return f"CRC and {len(expected)} member hashes/sizes match; raw CAM draft"


def _check_assembly(root: Path, variant: str, assembly: dict[str, Any],
                    net: dict[str, Any], board: dict[str, Any]) -> str:
    folder = root / "variants" / variant / "manufacturing-draft"
    parts = net["components"]
    _require(set(parts) == EXPECTED_REFS, "Native PCB must contain the 15 expected components")
    bom = _expanded_bom(_rows(folder / "bom-all.csv", "\t"))
    pnp = _indexed(_rows(folder / "pnp-all.csv", "\t"))
    _require(set(bom) == set(pnp) == EXPECTED_REFS, "Raw BOM/PnP components differ from netlist")
    anchors = {part["ref"]: part for part in board["parts"]}
    _require(len(anchors) == len(board["parts"]) and set(anchors) == EXPECTED_REFS,
             "Native export manifest has duplicate or missing component anchors")
    for ref, component in parts.items():
        props, row, anchor = component["props"], pnp[ref], anchors[ref]
        _bom_identity(bom[ref], props, ref)
        for field, prop in (("Device", "DeviceName"), ("Footprint", "FootprintName"), ("Value", "Value")):
            _require(row[field] == props.get(prop, ""), f"{ref}: raw PnP {field} differs from netlist")
        for axis in ("X", "Y"):
            _require(abs(_mm(row[f"Mid {axis}"]) - anchor[axis.lower()] * .0254) <= .0006,
                     f"{ref}: PnP {axis} differs from saved component anchor")
        _require(row["Layer"] == {1: "T", 2: "B"}.get(anchor["layer"]),
                 f"{ref}: PnP side differs from saved native side")
        angle = float(row["Rotation"])
        _require(math.isfinite(angle) and abs((angle - anchor["rotation"] + 180) % 360 - 180) <= .001,
                 f"{ref}: PnP rotation differs from native rotation")
        _require(int(row["Pins"]) == len(component["pinInfoMap"]), f"{ref}: PnP pin count differs")
    _require(parts["CT2"]["props"].get("Population") == "DNP", "CT2 must remain DNP")
    _require(set(assembly["profiles"]) == set(EXPECTED_PROFILES), "Unexpected assembly profiles")
    for profile, expected in EXPECTED_PROFILES.items():
        spec = assembly["profiles"][profile]
        fit = spec["fit_designators"]
        _require(len(fit) == len(set(fit)) and set(fit) == expected and spec["fit_count"] == len(expected),
                 f"{profile}: wrong fit designators/count")
        _require(set(spec["excluded"]) == EXPECTED_REFS - expected,
                 f"{profile}: wrong excluded designators")
        reviewed_bom = _indexed(_rows(folder / f"{profile}-bom-review.csv"))
        reviewed_pnp = _indexed(_rows(folder / f"{profile}-pnp-review.csv"))
        _require(set(reviewed_bom) == set(reviewed_pnp) == expected,
                 f"{profile}: review BOM/PnP must exactly match fitted refs; exclude CT2")
        for ref in expected:
            row, props = reviewed_bom[ref], parts[ref]["props"]
            _bom_identity(row, props, ref)
            _require(row["Quantity"] == "1" and row["Population"] == props.get("Population") == "Fit",
                     f"{ref}: wrong fitted quantity/population")
            _require(reviewed_pnp[ref] == pnp[ref], f"{profile}/{ref}: reviewed PnP differs from raw row")
        _require("HOLD" in reviewed_bom["C1"]["Sourcing"], "C1 sourcing hold must remain explicit")
    return "15 raw parts; four-LED 14 and two-LED 12; identity, coordinates, side, rotation and DNP match"


def _check_native(root: Path, export: dict[str, Any]) -> str:
    with _archive(root / NATIVE_PATH) as archive:
        journals = [name for name in archive.namelist() if name.endswith(".epru")]
        _require(len(journals) == 1 and "project2.json" in archive.namelist(), "Invalid epro2 structure")
        documents = _replay(archive.read(journals[0]).decode("utf-8-sig"))
    pcb_docs = {uuid for uuid, doc in documents.items() if doc["head"]["docType"] == "PCB"
                and not doc["records"].get(("DELETE_DOC", ""), {}).get("isDelete", False)}
    _require(pcb_docs == {board["uuid"] for board in export["boards"]},
             "epro2 PCB documents differ from export manifest")
    blobs = documents.get("BLOB", {}).get("records", {})
    cover_count = 0
    for board in export["boards"]:
        variant = board["variant"]
        records = documents[board["uuid"]]["records"]
        component_records = [data for (kind, _), data in records.items() if kind == "COMPONENT"]
        parts = {data["attrs"]["Unique ID"]: data for data in component_records}
        _require(len(component_records) == len(parts) == 15 and set(parts) == EXPECTED_REFS,
                 f"{variant}: epro2 missing or duplicate components")
        for anchor in board["parts"]:
            part = parts[anchor["ref"]]
            _require(all(abs(part[key] - anchor[key]) < .0001 for key in ("x", "y"))
                     and part["layerId"] == anchor["layer"] and part["angle"] == anchor["rotation"],
                     f"{variant}/{anchor['ref']}: epro2 component differs from export manifest")
        stem = "core" if variant == "common" else f"{variant}-panel"
        source = root / f"variants/common/eda/native/{stem}-source.jsonl"
        source_records = _replay(source.read_text(encoding="utf-8-sig"))[board["uuid"]]["records"]
        _require(_design_records(source_records) == _design_records(records),
                 f"{variant}: epro2 physical primitives differ from saved source snapshot")
        objects = [data for (kind, _), data in records.items() if kind == "OBJ"]
        if variant == "common":
            _require(not objects, "Core must not contain cover objects")
            continue
        expected_covers = ({"front-horse-37mm.png", "rear-sagittarius-37mm.png"}
                           if variant == "horse-sagittarius" else {"front-snake-37mm.png", "rear-leo-37mm.png"})
        _require(len(objects) == 2 and {data["fileName"] for data in objects} == expected_covers,
                 f"{variant}: incorrect embedded cover files")
        for data in objects:
            _require(not data["mirror"] and all(abs(data[key] * .0254 - 37) < .0001
                                               for key in ("width", "height")),
                     f"{variant}: cover mirror/size differs")
            ident = data["path"].removeprefix("blob:")
            blob = blobs.get(("BLOB", ident))
            _require(isinstance(blob, dict), f"Missing artwork BLOB: {ident}")
            content = blob["content"]
            _require(content.startswith("data:image/png;base64,"), "Cover BLOB is not a PNG data URL")
            image = base64.b64decode(content.split(",", 1)[1], validate=True)
            _require(image == (root / "variants" / variant / "artwork" / data["fileName"]).read_bytes(),
                     f"{variant}: embedded {data['fileName']} differs from cover PNG")
            cover_count += 1
    return f"CRC; journal physical primitives match three PCB snapshots and {cover_count} embedded cover PNGs"


def validate(root: Path) -> dict[str, Any]:
    """Validate a repository root or its ``hardware/nfc-talisman`` directory."""
    root = Path(root).resolve()
    if (root / "hardware/nfc-talisman").is_dir():
        root = root / "hardware/nfc-talisman"
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(ident: str, action: Callable[[], str]) -> None:
        try:
            detail = action()
            checks.append({"id": ident, "passed": True, "detail": detail})
        except (OSError, ValueError, KeyError, TypeError, IndexError, zipfile.BadZipFile,
                RuntimeError, csv.Error, StopIteration, AttributeError, OverflowError) as exc:
            error = f"{ident}: {exc}"
            errors.append(error)
            checks.append({"id": ident, "passed": False, "detail": str(exc)})

    export_path = root / "variants/common/export-manifest.json"
    assembly_path = root / "variants/common/assembly-review-manifest.json"
    manifests: dict[str, Any] = {}

    def read_manifest(label: str, path: Path) -> str:
        data = _json(path)
        _require(isinstance(data, dict) and isinstance(data.get("files"), dict), "Missing files map")
        _require(str(data.get("releaseStatus", "")).startswith("HOLD"), "Manufacturing release HOLD missing")
        manifests[label] = data
        return f"{len(data['files'])} recorded files; {data['releaseStatus']}"

    check("export_manifest", lambda: read_manifest("export", export_path))
    check("assembly_manifest", lambda: read_manifest("assembly", assembly_path))
    for label, manifest in manifests.items():
        for name, metadata in manifest["files"].items():
            check(f"{label}_file:{name.replace(chr(92), '/')}",
                  lambda name=name, metadata=metadata: _file_check(_relative(root, name), metadata))

    export, assembly = manifests.get("export"), manifests.get("assembly")
    if export is not None:
        def export_scope() -> str:
            files = {name.replace("\\", "/") for name in export["files"]}
            required = {NATIVE_PATH, "variants/common/eda/native/schematic-source.jsonl",
                        "variants/common/eda/native/core-source.jsonl", "variants/common/eda/core-pads.json",
                        "variants/common/eda/native/core-netlist.json"}
            for variant in VARIANTS:
                required.update({f"variants/common/eda/native/{variant}-panel-source.jsonl",
                                 f"variants/common/eda/native/{variant}-panel-netlist.json",
                                 f"variants/common/eda/{variant}-panel-pads.json"})
                required.update(f"variants/{variant}/manufacturing-draft/{name}" for name in
                                (f"{variant}-gerber.zip", "bom-all.csv", "pnp-all.csv", "gerber-members.json"))
            _require(files == required, "Export manifest has missing or unexpected files")
            boards = export["boards"]
            _require(len(boards) == 3 and {b["variant"] for b in boards} == {"common", *VARIANTS},
                     "Expected common core and two variant panels")
            _require(len({b["uuid"] for b in boards}) == 3 and all(b["savedReopened"] and b["drc"] == [] for b in boards),
                     "Saved/reopened clean DRC evidence missing")
            return "Three saved/reopened PCB records and complete 19-file export scope"
        check("export_scope", export_scope)
        check("native_archive", lambda: _check_native(root, export))

    core: dict[str, Any] | None = None
    try:
        core = _netlist(root / "variants/common/eda/native/core-netlist.json")
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        check("core_netlist", lambda: (_ for _ in ()).throw(ValueError(str(exc))))
    if core is not None:
        def netlists() -> str:
            _require(set(core["components"]) == EXPECTED_REFS, "Core component identities differ")
            pins = _pin_map(core)
            _require(len(pins) == 36 and len(set(pins.values())) == 11, "Expected 36 component pins on 11 nets")
            for variant in VARIANTS:
                panel = _netlist(root / f"variants/common/eda/native/{variant}-panel-netlist.json")
                _require(set(panel["components"]) == EXPECTED_REFS and _pin_map(panel) == pins,
                         f"{variant}: saved PCB pin/net assignments differ from common core")
                for ref in EXPECTED_REFS:
                    for prop in ("Value", "Manufacturer Part", "Supplier Part", "FootprintName", "Population", "PCB Side"):
                        panel_prop = panel["components"][ref]["props"].get(prop)
                        core_prop = core["components"][ref]["props"].get(prop)
                        if prop == "PCB Side":
                            panel_prop, core_prop = str(panel_prop).casefold(), str(core_prop).casefold()
                        _require(panel_prop == core_prop,
                                 f"{variant}/{ref}: native {prop} differs from core")
            return "Three PCB netlists: 15 components, 36 pins, 11 nets and matching part identities"
        check("pcb_netlists", netlists)

    if assembly is not None:
        def assembly_scope() -> str:
            _require(assembly["source"] == "variants/common/eda/native/core-netlist.json", "Unexpected assembly source")
            required = {f"variants/{variant}/manufacturing-draft/{name}" for variant in VARIANTS
                        for name in ("README.md", *(f"{profile}-{table}-review.csv"
                                                    for profile in EXPECTED_PROFILES for table in ("bom", "pnp")))}
            _require({name.replace("\\", "/") for name in assembly["files"]} == required,
                     "Assembly manifest has missing or unexpected files")
            return "Both assembly profiles for each variant and their README files are hashed"
        check("assembly_scope", assembly_scope)

    for variant in VARIANTS:
        check(f"gerber:{variant}", lambda variant=variant: _check_gerber(root, variant))
        if core is not None and assembly is not None and export is not None:
            check(f"assembly:{variant}", lambda variant=variant: _check_assembly(
                root, variant, assembly, core, next(board for board in export["boards"] if board["variant"] == variant)))
        def artwork(variant: str = variant) -> str:
            folder = root / "variants" / variant / "artwork"
            manifest = _json(folder / "manifest.json")
            _require(manifest["variant"] == variant and manifest["canvas_mm"] == [37, 37], "Incorrect artwork variant/size")
            for name, metadata in manifest["files"].items():
                _file_check(_relative(folder, name), metadata)
                _file_check(_relative(folder, name).with_suffix(".svg"), {"sha256": metadata["svg_sha256"]})
            _file_check(_relative(folder, manifest["preview"]["file"]), manifest["preview"])
            return "Cover PNG/SVG and preview SHA-256 match artwork manifest"
        check(f"artwork:{variant}", artwork)

    def saved_copper_evidence() -> str:
        report = _json(root / "variants/common/native-copper-audit.json")
        _require(report["summary"] and all(v is True for v in report["summary"].values()), "Saved copper audit has failed checks")
        for name, digest in report["source_sha256"].items():
            _file_check(_relative(root, name), {"sha256": digest})
        return "Saved copper audit passes and matches current source/pad snapshots"
    check("saved_copper_evidence", saved_copper_evidence)
    return {
        "status": "failed" if errors else "passed", "read_only": True,
        "checks": checks, "errors": errors, "checks_run": len(checks),
        "release_status": export.get("releaseStatus") if export else "HOLD_UNVERIFIED_DELIVERY",
        "release_ready": False,
        "limitations": [
            "Archive integrity only; this check does not inspect unsaved live EasyEDA changes or run native ERC/DRC.",
            "Raw Gerber archives retain both PTH drill programs; supplier CAM must select the correct program.",
            "C1 procurement/fit, official CAM including color/slot processing, and physical RF/NFC/optical acceptance remain pending.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = validate(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
