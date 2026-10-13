import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_project
import package_project


class TemplateIntegrityTests(unittest.TestCase):
    def test_malformed_template_fields_report_failure_without_traceback(self):
        for manifest in (None, [], {"source_sha256": []},
                         {"source_sha256": {}, "pdf": 42},
                         {"source_sha256": {}, "pdf": "template.pdf", "pdf_sha256": None},
                         {"source_sha256": {}, "art_source": [], "pdf": "template.pdf"}):
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ("output/pdf/placement-template-manifest.json",
                             "output/engraving-final-u1/fabrication-manifest.json"):
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(manifest), encoding="utf-8")
                checks = check_project.template_checks(root)
                self.assertEqual(len(checks), 2)
                self.assertTrue(all(not check["passed"] for check in checks))

    def test_reviewed_source_change_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ("output/pdf", "output/engraving-final-u1"):
                (root / folder).mkdir(parents=True)
            (root / "source.json").write_bytes(b"original")
            (root / "output/pdf/template.pdf").write_bytes(b"pdf")
            manifest = {"source_sha256": {"source.json": hashlib.sha256(b"original").hexdigest()},
                        "pdf": "C:\\author\\output\\pdf\\template.pdf",
                        "pdf_sha256": hashlib.sha256(b"pdf").hexdigest()}
            for name in ("output/pdf/placement-template-manifest.json",
                         "output/engraving-final-u1/fabrication-manifest.json"):
                (root / name).write_text(json.dumps(manifest), encoding="utf-8")
            self.assertTrue(all(item["passed"] for item in check_project.template_checks(root)))
            (root / "source.json").write_bytes(b"modified")
            self.assertTrue(any(not item["passed"] for item in check_project.template_checks(root)))


class DeliveryPackageTests(unittest.TestCase):
    def manifest(self, **changes):
        return {"format_version": 1, "project": "Zodiac_Light", "commit": "a" * 40,
                "files": {}, **changes}

    def git(self, root, *args):
        subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def fixture(self, root):
        self.git(root, "init")
        self.git(root, "config", "user.name", "Delivery Test")
        self.git(root, "config", "user.email", "delivery@example.invalid")
        (root / ".gitignore").write_text("build/\n", encoding="utf-8")
        (root / "README.md").write_bytes(b"project source\n")
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", "Fixture")

    @patch.object(check_project, "validate", return_value={"status": "passed", "checks": [],
                  "hardware_release_status": "HOLD", "limitations": []})
    def test_commit_bound_package_and_tamper_detection(self, validate):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path, result = package_project.package(root, run_tests=False)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["files"], 2)
            self.assertTrue(path.with_suffix(".zip.sha256").is_file())
            original = path.read_bytes()
            package_project.package(root, run_tests=False)
            self.assertEqual(original, path.read_bytes())
            with zipfile.ZipFile(path) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
            members["Zodiac_Light/README.md"] = b"tampered\n"
            with zipfile.ZipFile(path, "w") as archive:
                for name, data in members.items():
                    archive.writestr(name, data)
            with self.assertRaisesRegex(ValueError, "hash/size failed"):
                package_project.verify_archive(path)
            (root / "README.md").write_bytes(b"uncommitted\n")
            with self.assertRaisesRegex(ValueError, "Commit project changes"):
                package_project.package(root, run_tests=False)

    def test_extra_and_unsafe_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.zip"
            manifest = self.manifest()
            for name, message in (("Zodiac_Light/extra.txt", "members do not match"),
                                  ("../outside.txt", "Unsafe ZIP")):
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(package_project.MANIFEST, json.dumps(manifest))
                    archive.writestr(name, "unexpected")
                with self.assertRaisesRegex(ValueError, message):
                    package_project.verify_archive(path)

    def test_windows_unsafe_and_noncanonical_paths_are_rejected(self):
        for name in ("C:/outside", "README.md:stream", "folder//file.txt", "folder/./file.txt",
                     "nul.txt", "folder/file.", "file?name", "folder/file "):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "package.zip"
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(package_project.MANIFEST, json.dumps(self.manifest()))
                    archive.writestr(package_project.PREFIX + name, b"unexpected")
                with self.assertRaisesRegex(ValueError, "Unsafe ZIP"):
                    package_project.verify_archive(path)

    def test_case_collisions_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(package_project.MANIFEST, json.dumps(self.manifest()))
                archive.writestr(package_project.PREFIX + "README.md", b"first")
                archive.writestr(package_project.PREFIX + "readme.md", b"second")
            with self.assertRaisesRegex(ValueError, "collide on Windows"):
                package_project.verify_archive(path)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(package_project.MANIFEST, json.dumps(self.manifest()))
                entry = zipfile.ZipInfo(package_project.PREFIX + "link")
                entry.create_system = 3
                entry.external_attr = 0o120777 << 16
                archive.writestr(entry, "../../outside")
            with self.assertRaisesRegex(ValueError, "not a regular file"):
                package_project.verify_archive(path)

    def test_malformed_manifest_is_rejected_with_clean_cli_error(self):
        bad = (None, [], {}, self.manifest(files=[]), self.manifest(commit="fixture"),
               self.manifest(files={"README.md": []}),
               self.manifest(files={"README.md": {"size": True, "sha256": "a" * 64}}),
               self.manifest(files={"README.md": {"size": 1, "sha256": None}}))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.zip"
            for manifest in bad:
                with self.subTest(manifest=manifest):
                    with zipfile.ZipFile(path, "w") as archive:
                        archive.writestr(package_project.MANIFEST, json.dumps(manifest))
                    with self.assertRaises(ValueError):
                        package_project.verify_archive(path)
            completed = subprocess.run([sys.executable, str(Path(package_project.__file__)),
                                        "--verify", str(path)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("Package failed:", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_duplicate_manifest_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.zip"
            manifest = json.dumps(self.manifest()).removesuffix("}") + ', "files": {}}'
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(package_project.MANIFEST, manifest)
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                package_project.verify_archive(path)

    @patch.object(check_project, "validate", return_value={"status": "passed", "checks": [],
                  "hardware_release_status": "HOLD", "limitations": []})
    def test_hidden_working_tree_changes_are_rejected(self, validate):
        for flag in ("--skip-worktree", "--assume-unchanged"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root)
                self.git(root, "update-index", flag, "README.md")
                (root / "README.md").write_bytes(b"hidden uncommitted modification\n")
                self.assertFalse(package_project.git(root, "status", "--porcelain").strip())
                with self.assertRaisesRegex(ValueError, "skip-worktree/assume-unchanged"):
                    package_project.package(root, run_tests=False)

    @patch.object(check_project, "validate")
    def test_head_change_during_validation_is_rejected(self, validate):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)

            def change_commit(*args, **kwargs):
                self.git(root, "commit", "--allow-empty", "-m", "Concurrent commit")
                return {"status": "passed", "checks": [], "hardware_release_status": "HOLD",
                        "limitations": []}

            validate.side_effect = change_commit
            with self.assertRaisesRegex(ValueError, "HEAD changed"):
                package_project.package(root, run_tests=False)

    @patch.object(check_project, "validate", return_value={"status": "passed", "checks": [],
                  "hardware_release_status": "HOLD", "limitations": []})
    def test_archive_uses_committed_bytes_and_preserves_executable_mode(self, validate):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / ".gitattributes").write_text("* text eol=crlf\n", encoding="utf-8")
            (root / "README.md").write_bytes(b"project source\r\n")
            (root / "run.sh").write_bytes(b"#!/bin/sh\necho test\n")
            self.git(root, "add", ".")
            self.git(root, "update-index", "--chmod=+x", "run.sh")
            self.git(root, "commit", "-m", "Text normalization and executable")
            # Git for POSIX notices a mode mismatch; match the committed mode.
            (root / "run.sh").chmod(0o755)
            path, result = package_project.package(root, run_tests=False)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.read(package_project.PREFIX + "README.md"),
                                 package_project.git(root, "show", "HEAD:README.md"))
                self.assertNotEqual(archive.read(package_project.PREFIX + "README.md"),
                                    (root / "README.md").read_bytes())
                self.assertEqual(archive.getinfo(package_project.PREFIX + "run.sh").external_attr >> 16,
                                 0o100755)


if __name__ == "__main__":
    unittest.main()
