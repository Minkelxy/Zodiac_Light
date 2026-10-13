"""Build or verify a checked, commit-bound ZIP of the complete tracked project."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

import check_project

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "Zodiac_Light/"
MANIFEST = PREFIX + "delivery-manifest.json"


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_relative(name: str) -> None:
    """Require a regular path that extracts consistently on Windows and POSIX."""
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
    if not isinstance(name, str):
        raise ValueError("Unsafe ZIP member: path must be a string")
    parts = PurePosixPath(name).parts
    if (not parts or name != "/".join(parts) or name.startswith("/")
            or any(char in '<>:"\\|?*' for char in name) or ".." in parts
            or any(ord(char) < 32 for char in name)
            or any(part.endswith((".", " ")) or part.split(".", 1)[0].casefold() in reserved
                   for part in parts)):
        raise ValueError(f"Unsafe ZIP member: {name}")


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def checked_manifest(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Delivery manifest must be an object")
    if type(raw.get("format_version")) is not int or raw["format_version"] != 1:
        raise ValueError("Unsupported delivery manifest format_version")
    if raw.get("project") != "Zodiac_Light":
        raise ValueError("Delivery manifest project must be Zodiac_Light")
    commit = raw.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise ValueError("Delivery manifest commit must be a full Git object ID")
    files = raw.get("files")
    if not isinstance(files, dict):
        raise ValueError("Delivery manifest files must be an object")
    for name, info in files.items():
        safe_relative(name)
        if name == "delivery-manifest.json":
            raise ValueError("The generated manifest name is reserved")
        if not isinstance(info, dict) or type(info.get("size")) is not int or info["size"] < 0:
            raise ValueError(f"Invalid manifest file size: {name}")
        if not isinstance(info.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", info["sha256"]):
            raise ValueError(f"Invalid manifest file SHA-256: {name}")
    return raw


def verify_archive(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("ZIP contains duplicate member names")
        if len(names) != len({name.casefold() for name in names}):
            raise ValueError("ZIP contains names that collide on Windows")
        for name in names:
            if not name.startswith(PREFIX):
                raise ValueError(f"Unsafe ZIP member: {name}")
            safe_relative(name[len(PREFIX):])
            entry = archive.getinfo(name)
            if stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG):
                raise ValueError(f"ZIP member is not a regular file: {name}")
            if entry.flag_bits & 1:
                raise ValueError(f"Encrypted ZIP member is unsupported: {name}")
        if MANIFEST not in names:
            raise ValueError("ZIP lacks delivery-manifest.json")
        if archive.getinfo(MANIFEST).file_size > 16 * 1024 * 1024:
            raise ValueError("Delivery manifest exceeds 16 MiB")
        manifest = checked_manifest(json.loads(archive.read(MANIFEST), object_pairs_hook=unique_json_object))
        expected = {PREFIX + name for name in manifest["files"]} | {MANIFEST}
        if set(names) != expected:
            raise ValueError("ZIP members do not match the delivery manifest")
        for name, info in manifest["files"].items():
            if archive.getinfo(PREFIX + name).file_size != info["size"]:
                raise ValueError(f"ZIP content hash/size failed: {name}")
            with archive.open(PREFIX + name) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != info["sha256"]:
                raise ValueError(f"ZIP content hash/size failed: {name}")
    return {"status": "passed", "commit": manifest["commit"], "files": len(manifest["files"]),
            "sha256": file_digest(path)}


def clean_commit(root: Path, expected: str | None = None, *, allowed_untracked=()) -> str:
    records = iter(git(root, "status", "--porcelain", "-z", "--untracked-files=all").split(b"\0"))
    for record in records:
        if not record:
            continue
        status, name = record[:2], record[3:].decode("utf-8")
        if status == b"??" and name in allowed_untracked:
            continue
        raise ValueError("Commit project changes before packaging; the package must identify an exact commit")
    # These index flags hide working-tree changes from git status. A complete
    # project delivery requires an ordinary checkout of every committed file.
    hidden = [item[2:].decode("utf-8") for item in git(root, "ls-files", "-v", "-z").split(b"\0")
              if item and (item[:1] == b"S" or item[:1].islower())]
    if hidden:
        raise ValueError(f"Clear skip-worktree/assume-unchanged flags before packaging: {hidden}")
    commit = git(root, "rev-parse", "HEAD").decode().strip()
    if expected is not None and commit != expected:
        raise ValueError("HEAD changed while validation or packaging ran; retry the delivery")
    return commit


def committed_files(root: Path, commit: str) -> list[tuple[str, int, str]]:
    files = []
    for record in git(root, "ls-tree", "--full-tree", "-r", "-z", commit).split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        name = name.decode("utf-8")
        safe_relative(name)
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError(f"Expected a regular committed file: {name}")
        if (root / name).is_symlink() or not (root / name).is_file():
            raise ValueError(f"Expected a regular tracked file: {name}")
        files.append((name, int(mode, 8), oid))
    return sorted(files)


def package(root: Path, output: Path | None = None, *, run_tests: bool = True) -> tuple[Path, dict]:
    root = root.resolve()
    commit = clean_commit(root)
    report = check_project.validate(root, run_tests=run_tests)
    if report["status"] != "passed":
        raise ValueError(f"Project checks failed: {report['errors']}")
    clean_commit(root, commit)
    output = output or root / "build/releases" / f"Zodiac_Light-{commit[:12]}.zip"
    output = output.resolve()
    entries = committed_files(root, commit)
    names = [name for name, _, _ in entries]
    checksum = output.with_suffix(output.suffix + ".sha256")
    for destination in (output, checksum):
        if destination.is_relative_to(root) and destination.relative_to(root).as_posix() in names:
            raise ValueError("Output would overwrite a tracked source file")
    if "delivery-manifest.json" in names:
        raise ValueError("The generated manifest name is reserved")
    files = {}
    manifest = {"format_version": 1, "project": "Zodiac_Light", "commit": commit,
                "files": files, "validation": {"status": report["status"],
                    "checks": len(report["checks"]), "unittest_run": run_tests},
                "hardware_release_status": report["hardware_release_status"],
                "limitations": report["limitations"]}
    stamp = datetime.fromtimestamp(int(git(root, "show", "-s", "--format=%ct", commit)), timezone.utc)
    date = (min(2107, max(1980, stamp.year)), stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".clp-release-", suffix=".tmp", dir=output.parent,
                                     delete=False) as staging:
        temporary = Path(staging.name)
    staged_paths = {temporary.relative_to(root).as_posix()} if temporary.is_relative_to(root) else set()
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            # Read the fixed commit's blobs, so Git's checkout EOL conversion or
            # a concurrent working-tree edit cannot change committed ZIP bytes.
            with subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE) as reader:
                try:
                    for name, mode, oid in entries:
                        reader.stdin.write(oid.encode("ascii") + b"\n")
                        reader.stdin.flush()
                        header = reader.stdout.readline().decode("ascii").split()
                        if len(header) != 3 or header[:2] != [oid, "blob"]:
                            raise ValueError(f"Cannot read committed file: {name}")
                        size = int(header[2])
                        data = reader.stdout.read(size)
                        if len(data) != size or reader.stdout.read(1) != b"\n":
                            raise ValueError(f"Incomplete committed file: {name}")
                        files[name] = {"size": size, "sha256": digest(data)}
                        entry = zipfile.ZipInfo(PREFIX + name, date_time=date)
                        entry.create_system = 3
                        entry.external_attr = mode << 16
                        entry.compress_type = zipfile.ZIP_DEFLATED
                        archive.writestr(entry, data)
                finally:
                    reader.stdin.close()
                if reader.wait() != 0:
                    raise ValueError("Git could not read the committed project")
            entry = zipfile.ZipInfo(MANIFEST, date_time=date)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
        verified = verify_archive(temporary)
        clean_commit(root, commit, allowed_untracked=staged_paths)
        temporary.replace(output)
        checksum.write_text(
            f"{verified['sha256']}  {output.name}\n", encoding="utf-8")
    finally:
        temporary.unlink(missing_ok=True)
    return output, verified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Destination ZIP (default: build/releases/<commit>.zip)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip unittest; keep delivery checks")
    parser.add_argument("--verify", type=Path, help="Verify an existing delivery ZIP without extracting it")
    args = parser.parse_args()
    try:
        if args.verify:
            print(json.dumps(verify_archive(args.verify), indent=2))
        else:
            path, verified = package(ROOT, args.output, run_tests=not args.skip_tests)
            print(f"Package: {path}\nFiles: {verified['files']}\nSHA-256: {verified['sha256']}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile, KeyError) as exc:
        print(f"Package failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
