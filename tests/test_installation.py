"""Run default CLI commands from the layout installed by a wheel."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallationTests(unittest.TestCase):
    def test_bundled_scene_runs_outside_checkout_and_writes_to_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            installed = directory / "site-packages"
            package = installed / "constellation_lamp"
            shutil.copytree(ROOT / "constellation_lamp", package,
                            ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "data", package / "data",
                            ignore=shutil.ignore_patterns("reference.png"))
            working = directory / "working"
            working.mkdir()
            script = ("import sys; sys.path.insert(0, sys.argv[1]); "
                      "from constellation_lamp.__main__ import main; "
                      "raise SystemExit(main(sys.argv[2:]))")
            for arguments in (("validate",), ("export", "--compact"),
                              ("render", "--effect", "aurora"),
                              ("stream", "--dry-run", "capture.clp", "--duration", ".1")):
                with self.subTest(arguments=arguments):
                    completed = subprocess.run([sys.executable, "-I", "-c", script,
                                                str(installed), *arguments], cwd=working,
                                               capture_output=True, text=True,
                                               errors="replace", timeout=30)
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue((working / "build" / "constellation_compact.h").is_file())
            self.assertTrue((working / "build" / "preview.png").is_file())
            self.assertTrue((working / "capture.clp").is_file())
            self.assertFalse((installed / "build").exists())


if __name__ == "__main__":
    unittest.main()
