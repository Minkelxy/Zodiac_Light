#!/usr/bin/env python3
"""Verify the cached catalogue, or explicitly refresh it with --refresh.

No third-party Python packages are required. Downloads stay in memory until all
sources have been checked. Immutable snapshot directories are committed first;
catalog.json is replaced atomically last. A failed refresh leaves the previous
catalogue and all its referenced snapshots intact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SELECTED_HIPS = (
    95168, 94820, 93683, 93085, 92855, 92041, 90496, 89341, 89931,
    88635, 87072, 90185, 89642, 93506, 93864, 96406, 98688, 98412,
    98032, 95347, 95294,
)
STELLARIUM_BASE = (
    "https://raw.githubusercontent.com/Stellarium/stellarium/master/skycultures/modern/"
)
HIPPARCOS_URL = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv?" + urlencode({
    "-source": "I/239/hip_main",
    "-out": "HIP,RAICRS,DEICRS,Vmag",
    "HIP": ",".join(map(str, sorted(SELECTED_HIPS))),
})
SIMBAD_URL = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
SIMBAD_QUERY = (
    "SELECT i.id, b.main_id FROM ident AS i JOIN basic AS b ON i.oidref=b.oid "
    "WHERE i.id IN (" + ",".join(f"'HIP {hip}'" for hip in sorted(SELECTED_HIPS)) + ")"
)
SIMBAD_BODY = urlencode({
    "REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "tsv", "QUERY": SIMBAD_QUERY,
}).encode("ascii")
SPECS = (
    {"id": "hipparcos_i239", "filename": "hipparcos_i239.tsv", "url": HIPPARCOS_URL,
     "license": "CC BY-NC 3.0 IGO; Credit: ESA (ESA catalogue website)",
     "citation": "ESA 1997, The Hipparcos and Tycho Catalogues, ESA SP-1200; 1997HIP...C......0E",
     "license_url": "https://www.cosmos.esa.int/web/hipparcos/catalogues"},
    {"id": "simbad_names", "filename": "simbad_names.tsv", "url": SIMBAD_URL,
     "request_method": "POST", "request_body": SIMBAD_BODY.decode("ascii"),
     "adql": SIMBAD_QUERY,
     "license": "Publicly accessible service; a redistribution licence was not established by this project",
     "citation": "SIMBAD astronomical database, CDS, Strasbourg, France",
     "license_url": "https://cds.unistra.fr/cgi-bin/SimbadBib"},
    {"id": "stellarium_modern", "filename": "stellarium_modern_index.json",
     "url": STELLARIUM_BASE + "index.json", "source_ref": "master (content frozen by SHA-256)",
     "license": "CC BY-SA 4.0 (text and data)",
     "citation": "Stellarium team, Modern sky culture, CON modern Sgr",
     "license_url": STELLARIUM_BASE + "description.md"},
    {"id": "stellarium_license", "filename": "stellarium_modern_description.md",
     "url": STELLARIUM_BASE + "description.md", "license": "CC BY-SA 4.0 (text and data)",
     "citation": "Stellarium team, Modern sky culture description",
     "license_url": STELLARIUM_BASE + "description.md"},
    {"id": "esa_hipparcos_license", "filename": "esa_hipparcos_catalogues.html",
     "url": "https://www.cosmos.esa.int/web/hipparcos/catalogues",
     "license": "Website snapshot retained as evidence of catalogue usage terms; no commercial permission inferred",
     "citation": "European Space Agency, Hipparcos catalogues and usage terms",
     "license_url": "https://www.cosmos.esa.int/web/hipparcos/catalogues"},
)


def decode(data: bytes) -> str:
    return data.decode("utf-8-sig")


def request(spec: dict) -> tuple[str, bytes]:
    body = SIMBAD_BODY if spec["id"] == "simbad_names" else None
    headers = {"User-Agent": "Sagittarius-Lamp/1.0 (small batch catalogue import)"}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    for attempt in range(3):
        try:
            with urlopen(Request(spec["url"], data=body, headers=headers), timeout=45) as response:
                content = response.read(16 * 1024 * 1024 + 1)
            break
        except (URLError, TimeoutError, ConnectionError) as error:
            retryable = not isinstance(error, HTTPError) or error.code in (408, 429, 500, 502, 503, 504)
            if not retryable or attempt == 2:
                raise RuntimeError(f"Could not download {spec['id']}: {error}") from error
            time.sleep(attempt + 1)
    if not content or len(content) > 16 * 1024 * 1024:
        raise ValueError(f"Empty or oversized response: {spec['id']}")
    return spec["id"], content


def parse_hipparcos(data: bytes) -> dict[int, dict]:
    rows = csv.reader((line for line in decode(data).splitlines()
                       if line and not line.startswith("#")), delimiter="\t")
    header = next(rows)
    required = ["HIP", "RAICRS", "DEICRS", "Vmag"]
    if header != required:
        raise ValueError(f"Unexpected Hipparcos columns: {header}")
    result = {}
    for row in rows:
        if not row or not row[0].strip().isdigit():
            continue  # ASU units and separator rows.
        if len(row) != 4:
            raise ValueError("Malformed Hipparcos row")
        hip, ra, dec, mag = int(row[0]), *(float(cell) for cell in row[1:])
        if hip in result or not all(math.isfinite(v) for v in (ra, dec, mag)):
            raise ValueError(f"Duplicate or invalid Hipparcos row: {hip}")
        if not 0 <= ra < 360 or not -90 <= dec <= 90:
            raise ValueError(f"Out-of-range coordinates: {hip}")
        result[hip] = {"ra_deg": ra, "dec_deg": dec, "mag_v": mag}
    if set(result) != set(SELECTED_HIPS):
        raise ValueError("Hipparcos response does not contain exactly the selected 21 stars")
    return result


def parse_names(data: bytes) -> dict[int, str]:
    reader = csv.DictReader(io.StringIO(decode(data)), delimiter="\t")
    if reader.fieldnames != ["id", "main_id"]:
        raise ValueError(f"Unexpected SIMBAD columns: {reader.fieldnames}")
    result = {}
    for row in reader:
        match = re.fullmatch(r"HIP\s+(\d+)", row["id"].strip())
        if match is None or not row["main_id"].strip():
            raise ValueError("Malformed SIMBAD identifier row")
        hip = int(match[1])
        if hip in result:
            raise ValueError(f"Duplicate SIMBAD identity: {hip}")
        result[hip] = row["main_id"].strip()
    if set(result) != set(SELECTED_HIPS):
        raise ValueError("SIMBAD response does not contain exactly the selected 21 stars")
    return result


def validate_downloads(downloads: dict[str, bytes]) -> tuple[dict, dict]:
    positions = parse_hipparcos(downloads["hipparcos_i239"])
    names = parse_names(downloads["simbad_names"])
    modern = json.loads(decode(downloads["stellarium_modern"]))
    figure = next((entry for entry in modern["constellations"]
                   if entry["id"] == "CON modern Sgr"), None)
    if figure is None:
        raise ValueError("Stellarium source has no CON modern Sgr")
    if {hip for line in figure["lines"] for hip in line} != set(SELECTED_HIPS):
        raise ValueError("Stellarium Sagittarius star selection changed; review the source manually")
    if sum(len(line) - 1 for line in figure["lines"]) != 24:
        raise ValueError("Stellarium Sagittarius edge count changed; review the source manually")
    if "Text and data: CC BY-SA 4.0" not in decode(downloads["stellarium_license"]):
        raise ValueError("Stellarium usage terms changed; review before replacing the cache")
    esa = decode(downloads["esa_hipparcos_license"])
    if "CC BY-NC 3.0 IGO" not in esa or "Credit: ESA" not in esa:
        raise ValueError("ESA usage terms could not be verified; existing cache preserved")
    return positions, names


def atomic_json(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def refresh(data_dir: Path) -> dict:
    with ThreadPoolExecutor(max_workers=5) as pool:
        downloads = dict(pool.map(request, SPECS))
    positions, names = validate_downloads(downloads)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    relative_snapshot = Path("sources") / stamp
    sources = [{**spec,
                "snapshot_path": (relative_snapshot / spec["filename"]).as_posix(),
                "retrieved_at_utc": now.isoformat(),
                "sha256": hashlib.sha256(downloads[spec["id"]]).hexdigest()}
               for spec in SPECS]
    catalogue = {"schema_version": 1, "sources": sources, "stars": [
        {"hip": hip, "id": f"hip_{hip}", "name": names[hip], **positions[hip],
         "coordinate_frame": "ICRS", "coordinate_epoch": "J1991.25",
         "source_ids": ["hipparcos_i239", "simbad_names"]} for hip in SELECTED_HIPS
    ]}
    data_dir.mkdir(parents=True, exist_ok=True)
    sources_dir = data_dir / "sources"
    sources_dir.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".download-", dir=sources_dir))
    try:
        for spec in SPECS:
            (stage / spec["filename"]).write_bytes(downloads[spec["id"]])
        os.replace(stage, data_dir / relative_snapshot)
        atomic_json(data_dir / "catalog.json", catalogue)
    finally:
        if stage.exists():
            if stage.resolve().parent != sources_dir.resolve():
                raise ValueError("Refusing to remove a staging directory outside data/sources")
            shutil.rmtree(stage)
    return catalogue


def verify_cache(data_dir: Path) -> dict:
    catalogue = json.loads((data_dir / "catalog.json").read_text(encoding="utf-8"))
    if catalogue.get("schema_version") != 1:
        raise ValueError("Unsupported catalogue schema version")
    if [star["hip"] for star in catalogue["stars"]] != list(SELECTED_HIPS):
        raise ValueError("Cached star selection/order does not match this importer")
    cached = {}
    for source in catalogue["sources"]:
        path = (data_dir / source["snapshot_path"]).resolve()
        if not path.is_relative_to(data_dir.resolve()):
            raise ValueError("Snapshot path escapes the data directory")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != source["sha256"]:
            raise ValueError(f"Snapshot SHA-256 mismatch: {source['id']}")
        cached[source["id"]] = content
    positions, names = validate_downloads(cached)
    for star in catalogue["stars"]:
        hip = star["hip"]
        expected = {"id": f"hip_{hip}", "name": names[hip], **positions[hip],
                    "coordinate_frame": "ICRS", "coordinate_epoch": "J1991.25",
                    "source_ids": ["hipparcos_i239", "simbad_names"]}
        if any(star.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Catalogue does not agree with its snapshots: HIP {hip}")
    return catalogue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Explicitly allow network requests and refresh catalog.json")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args(argv)
    try:
        if args.refresh:
            refresh(args.data_dir)
        catalogue = verify_cache(args.data_dir)
        print(f"Verified {len(catalogue['stars'])} stars and {len(catalogue['sources'])} source snapshots"
              + (" (network refresh complete)" if args.refresh else " (offline; no network requests)"))
        return 0
    except Exception as error:
        print(f"Catalogue import failed: {error}. Existing complete catalogue was not overwritten by a failed download.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
