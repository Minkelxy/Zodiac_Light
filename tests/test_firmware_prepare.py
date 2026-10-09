"""Exercise scene/config synchronization and profiles consumed by real capture."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from constellation_lamp.compact import pack_runtime
from constellation_lamp.hardware import HardwareProfile
from constellation_lamp.model import ValidationError, load_runtime
from scripts.prepare_firmware import (EFFECT_NAMES, finalize_build, patch_sdkconfig,
                                     prepare_inputs, read_sdkconfig)


ROOT = Path(__file__).resolve().parents[1]


class FirmwarePrepareTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.data = self.project / "data"
        shutil.copytree(ROOT / "data", self.data)
        self.inputs = self.root / "inputs"
        self.config = self.root / "build" / "sdkconfig"
        self.config.parent.mkdir()
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.raw = json.loads((self.data / "hardware.json").read_text(encoding="utf-8-sig"))

    def write_hardware(self, raw=None):
        (self.data / "hardware.json").write_text(json.dumps(raw or self.raw), encoding="utf-8")

    def prepare(self, **kwargs):
        return prepare_inputs(self.project, self.inputs, self.config, **kwargs)

    def built_config(self, manifest):
        self.config.write_text(patch_sdkconfig("CONFIG_FREERTOS_HZ=1000\n", manifest["settings"]), encoding="utf-8")
        (self.artifacts / "constellation_lamp_idf.bin").write_bytes(b"test firmware binary")

    def snapshots(self):
        files = [self.config, *(self.inputs.glob("*")), *(self.artifacts.glob("*.json"))]
        return {str(path): path.read_bytes() for path in files if path.is_file()}

    def test_default_scene_header_defaults_and_metadata_agree(self):
        runtime = load_runtime(self.data)
        result = self.prepare()
        expected = pack_runtime(runtime)
        self.assertEqual(result["scene_sha256"], expected["metadata"]["scene_sha256"])
        self.assertEqual(result["led_count"], runtime.led_count)
        self.assertEqual(result["compact_table_bytes"], expected["metadata"]["table_bytes"])
        self.assertEqual(result["actual_mode"], 0)
        self.assertFalse(self.config.exists())
        header = (self.inputs / "constellation_compact.h").read_text(encoding="utf-8")
        self.assertIn(result["scene_sha256"], header)
        _, defaults = read_sdkconfig(self.inputs / "derived.sdkconfig.defaults")
        self.assertEqual(defaults["LED_COUNT"], runtime.led_count)
        self.assertEqual(defaults["DATA_GPIO"], 18)
        self.assertEqual(defaults["IDLE_LED_UA"], 1000)
        for name, digest in result["source_files_sha256"].items():
            self.assertEqual(digest, hashlib.sha256((self.data / name).read_bytes()).hexdigest())

    def test_stale_cached_hardware_is_synchronized_but_mode_is_retained(self):
        self.config.write_text("CONFIG_CLP_LOCAL_MODE=3\nCONFIG_CLP_NATIVE_EFFECT=7\n"
                               "CONFIG_CLP_LED_COUNT=999\nCONFIG_CLP_DATA_GPIO=19\n"
                               "CONFIG_FREERTOS_HZ=500\nCONFIG_CLP_LOCAL_LEVEL=12\n", encoding="utf-8")
        result = self.prepare()
        text, actual = read_sdkconfig(self.config)
        self.assertEqual((result["actual_mode"], actual["LOCAL_MODE"]), (3, 3))
        self.assertEqual(actual["NATIVE_EFFECT"], 7)
        self.assertEqual(actual["LED_COUNT"], load_runtime(self.data).led_count)
        self.assertEqual(actual["DATA_GPIO"], 18)
        self.assertIn("CONFIG_FREERTOS_HZ=500\n", text)
        self.assertEqual(actual["LOCAL_LEVEL"], 12)

    def test_explicit_mode_updates_existing_config_instead_of_defaults_only(self):
        self.config.write_text("CONFIG_CLP_LOCAL_MODE=3\nCONFIG_CLP_LED_COUNT=4\n", encoding="utf-8")
        result = self.prepare(mode=0)
        self.assertEqual(result["actual_mode"], 0)
        self.assertEqual(read_sdkconfig(self.config)[1]["LOCAL_MODE"], 0)

    def test_all_native_effects_have_stable_index_and_force_mode_four(self):
        self.config.write_text("CONFIG_CLP_LOCAL_MODE=1\n", encoding="utf-8")
        for index, name in enumerate(EFFECT_NAMES):
            with self.subTest(effect=name):
                result = self.prepare(effect=name)
                self.assertEqual(result["actual_mode"], 4)
                self.assertEqual(result["native_effect_index"], index)
                self.assertEqual(read_sdkconfig(self.config)[1]["NATIVE_EFFECT"], index)
        with self.assertRaisesRegex(ValidationError, "cannot be combined"):
            self.prepare(mode=2, effect="aurora")

    def test_same_count_reversed_wiring_changes_header_and_pinned_profile_rejects(self):
        original = load_runtime(self.data)
        first = self.prepare()
        old_profile = HardwareProfile.load(self.inputs / "hardware.json")
        layout_path = self.data / "layout.json"
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        layout["wiring"]["order"][0]["reverse"] = not layout["wiring"]["order"][0]["reverse"]
        layout_path.write_text(json.dumps(layout), encoding="utf-8")
        changed = load_runtime(self.data)
        self.assertEqual(changed.led_count, original.led_count)
        second = self.prepare()
        self.assertNotEqual(first["scene_sha256"], second["scene_sha256"])
        self.assertIn(second["scene_sha256"], (self.inputs / "constellation_compact.h").read_text(encoding="utf-8"))
        with self.assertRaises(ValidationError):
            old_profile.validate_runtime(changed)
        HardwareProfile.load(self.inputs / "hardware.json").validate_runtime(changed)

    def test_unusable_gpio_or_sdk_profile_preserves_all_old_inputs(self):
        self.config.write_text("CONFIG_CLP_LOCAL_MODE=4\n", encoding="utf-8")
        self.prepare()
        before = self.snapshots()
        variations = []
        for pin in (1, 3, 6, 11, 20, 24, 34, True, 18.5):
            raw = copy.deepcopy(self.raw)
            raw["board"]["data_pin"] = pin
            variations.append(raw)
        for field, value in (("framework", "arduino"), ("reference", "esp32-c3")):
            raw = copy.deepcopy(self.raw)
            raw["board"][field] = value
            variations.append(raw)
        for raw in variations:
            with self.subTest(board=raw["board"]):
                self.write_hardware(raw)
                with self.assertRaises(ValidationError):
                    self.prepare()
                self.assertEqual(self.snapshots(), before)

    def test_sdk_integer_and_range_failures_preserve_inputs(self):
        self.prepare()
        before = self.snapshots()
        variations = (("power_estimate", "current_limit_ma", 1999.5),
                      ("power_estimate", "channel_ma", 101),
                      ("ws2812", "reset_us", 299), ("ws2812", "reset_us", 300.5),
                      ("transport", "packet_timeout_ms", 99))
        for section, field, value in variations:
            with self.subTest(field=field, value=value):
                raw = copy.deepcopy(self.raw)
                raw[section][field] = value
                self.write_hardware(raw)
                with self.assertRaises(ValidationError):
                    self.prepare()
                self.assertEqual(self.snapshots(), before)

    def test_failed_header_export_preserves_header_config_and_manifest(self):
        self.config.write_text("CONFIG_CLP_LOCAL_MODE=0\n", encoding="utf-8")
        self.prepare()
        before = self.snapshots()
        with mock.patch("scripts.prepare_firmware.export_compact_c", side_effect=OSError("export failure")):
            with self.assertRaisesRegex(OSError, "export failure"):
                self.prepare(mode=4)
        self.assertEqual(self.snapshots(), before)

    def test_failed_replace_rolls_back_already_committed_files(self):
        self.config.write_text("CONFIG_CLP_LOCAL_MODE=0\n", encoding="utf-8")
        self.prepare()
        before = self.snapshots()
        from scripts import prepare_firmware
        replace = prepare_firmware.os.replace
        calls = 0

        def failing_replace(source, target):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("disk failure")
            replace(source, target)

        with mock.patch("scripts.prepare_firmware.os.replace", side_effect=failing_replace):
            with self.assertRaisesRegex(OSError, "disk failure"):
                self.prepare(mode=4, effect="aurora")
        self.assertEqual(self.snapshots(), before)
        self.assertFalse(list(self.inputs.glob(".clp-input-*")))

    def test_lower_baud_automatically_selects_valid_fps(self):
        self.raw["transport"]["baud"] = 115200
        self.write_hardware()
        result = self.prepare()
        self.assertEqual(result["requested_fps"], 30)
        self.assertGreater(result["actual_fps"], 0)
        self.assertLessEqual(result["actual_fps"], 10.6)
        profile = HardwareProfile.load(self.inputs / "hardware.json")
        profile.validate_runtime(load_runtime(self.data))
        self.assertEqual(profile.baud, 115200)

    def test_microamp_quantization_is_shared_with_emitted_host_profile(self):
        self.raw["power_estimate"].update(idle_led_ma=.1236, channel_ma=6.5434)
        self.write_hardware()
        result = self.prepare()
        self.assertEqual(result["settings"]["IDLE_LED_UA"], 124)
        self.assertEqual(result["settings"]["CHANNEL_UA"], 6543)
        profile = HardwareProfile.load(self.inputs / "hardware.json")
        self.assertEqual((profile.idle_led_ma, profile.channel_ma), (.124, 6.543))

    def test_finalize_profile_matches_actual_config_and_is_usable_for_capture(self):
        result = self.prepare(mode=4, effect="graph_wave")
        self.built_config(result)
        final = finalize_build(self.project, self.inputs, self.config, self.artifacts,
                               sdk_path="sdk", python_path="python", build_directory="build")
        self.assertEqual(final["actual_mode"], 4)
        self.assertEqual(final["native_effect"], "graph_wave")
        for name in ("constellation_compact.h", "native_presets.h"):
            self.assertEqual((self.artifacts / name).read_bytes(), (self.inputs / name).read_bytes())
        self.assertEqual(final["firmware_sha256"], hashlib.sha256(b"test firmware binary").hexdigest())
        profile = HardwareProfile.load(self.artifacts / "hardware.json")
        runtime = load_runtime(self.data)
        self.assertEqual(profile.expected_led_count, runtime.led_count)
        self.assertEqual(profile.scene_sha256, final["scene_sha256"])
        profile.validate_runtime(runtime)
        try:
            from constellation_lamp.seriallink import capture_frames, FrameDecoder
        except ImportError:
            self.skipTest("Capture verification requires NumPy")
        capture = self.root / "actual.clp"
        capture_frames(runtime, capture, {"effect": "aurora", "seed": 42}, profile, duration_s=.1)
        frames = FrameDecoder(runtime.led_count).feed(capture.read_bytes())
        self.assertTrue(frames)
        self.assertEqual(frames[0].led_count, runtime.led_count)

    def test_finalize_rejects_wrong_count_gpio_or_explicit_mode_without_publishing(self):
        result = self.prepare(mode=4)
        self.built_config(result)
        finalize_build(self.project, self.inputs, self.config, self.artifacts)
        before = self.snapshots()
        for key, value in (("LED_COUNT", 2), ("DATA_GPIO", 6), ("LOCAL_MODE", 0)):
            with self.subTest(setting=key):
                self.config.write_text(patch_sdkconfig("", {**result["settings"], key: value}), encoding="utf-8")
                with self.assertRaises(ValidationError):
                    finalize_build(self.project, self.inputs, self.config, self.artifacts)
                for path, contents in before.items():
                    if path != str(self.config):
                        self.assertEqual(Path(path).read_bytes(), contents)

    def test_finalize_rejects_scene_changed_during_build(self):
        result = self.prepare()
        self.built_config(result)
        path = self.data / "layout.json"
        layout = json.loads(path.read_text(encoding="utf-8"))
        layout["wiring"]["order"].reverse()
        path.write_text(json.dumps(layout), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "changed during"):
            finalize_build(self.project, self.inputs, self.config, self.artifacts)
        self.assertFalse((self.artifacts / "hardware.json").exists())

    def test_finalize_rejects_hardware_source_or_generated_header_changes(self):
        result = self.prepare()
        self.built_config(result)
        self.raw["power_estimate"]["current_limit_ma"] = 1500
        self.write_hardware()
        with self.assertRaisesRegex(ValidationError, "hardware.json changed during"):
            finalize_build(self.project, self.inputs, self.config, self.artifacts)
        result = self.prepare()
        self.built_config(result)
        with (self.inputs / "constellation_compact.h").open("a", encoding="utf-8") as stream:
            stream.write("\n/* altered during build */\n")
        with self.assertRaisesRegex(ValidationError, "header changed during"):
            finalize_build(self.project, self.inputs, self.config, self.artifacts)
        self.assertFalse((self.artifacts / "hardware.json").exists())

    def test_finalize_rejects_cached_hardware_drift(self):
        result = self.prepare()
        self.built_config(result)
        text, settings = read_sdkconfig(self.config)
        self.config.write_text(patch_sdkconfig(text, {"CURRENT_LIMIT_MA": 1500}), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "differs from hardware.json"):
            finalize_build(self.project, self.inputs, self.config, self.artifacts)
        self.assertFalse((self.artifacts / "hardware.json").exists())

    def test_cli_runs_without_importing_optional_packages(self):
        script = ROOT / "scripts" / "prepare_firmware.py"
        command = [sys.executable, "-S", str(script), "prepare", "--project-root", str(self.project),
                   "--generated-dir", str(self.inputs), "--sdkconfig", str(self.config), "--effect", "meteor"]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual((result["actual_mode"], result["native_effect_index"]), (4, 8))

    @unittest.skipUnless(os.name == "nt", "Windows junction and PowerShell resolver test")
    def test_sdk_resolver_skips_empty_records_and_failed_export_then_uses_next_sdk(self):
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            self.skipTest("PowerShell is required")
        scripts = self.project / "scripts"
        scripts.mkdir()
        for name in ("build_idf.ps1", "prepare_firmware.py"):
            shutil.copyfile(ROOT / "scripts" / name, scripts / name)
        shutil.copytree(ROOT / "constellation_lamp", self.project / "constellation_lamp",
                        ignore=shutil.ignore_patterns("__pycache__"))
        firmware = self.project / "firmware-idf"
        firmware.mkdir()
        shutil.copyfile(ROOT / "firmware-idf" / "sdkconfig.defaults", firmware / "sdkconfig.defaults")
        fake_tools = self.root / "tools"
        fake_tools.mkdir()
        binaries = fake_tools / "bin"
        binaries.mkdir()
        (binaries / "cmake.cmd").write_text("@echo off\necho FIXTURE_CMAKE_REACHED\nexit /b 9\n", encoding="ascii")
        (binaries / "ninja.cmd").write_text("@echo off\nexit /b 0\n", encoding="ascii")
        broken = self.root / "broken-sdk"
        good = self.root / "good-sdk"
        for sdk in (broken, good):
            (sdk / "tools").mkdir(parents=True)
        (broken / "tools" / "idf_tools.py").write_text(
            "import sys\nprint('fixture tool missing', file=sys.stderr)\nsys.exit(7)\n", encoding="ascii")
        (good / "tools" / "idf_tools.py").write_text(
            "import os\nprint('PATH=' + os.environ['CLP_FIXTURE_BIN'] + os.pathsep + os.environ['PATH'])\n", encoding="ascii")
        home = self.root / "home"
        (home / ".espressif").mkdir(parents=True)
        installation = {"idfSelectedId": "missing-selection", "idfToolsPath": str(fake_tools),
                        "idfInstalled": {"empty": None, "missing-path": {"python": sys.executable},
                            "broken": {"path": str(broken), "python": sys.executable},
                            "good": {"path": str(good), "python": sys.executable}}}
        (home / ".espressif" / "esp_idf.json").write_text(json.dumps(installation), encoding="utf-8")
        cache = self.root / "cache"
        cache.mkdir()
        environment = dict(os.environ, USERPROFILE=str(home), TEMP=str(cache), TMP=str(cache),
                           CLP_FIXTURE_BIN=str(binaries))
        for name in ("IDF_PATH", "IDF_TOOLS_PATH", "IDF_PYTHON_ENV_PATH"):
            environment.pop(name, None)
        completed = subprocess.run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                    str(scripts / "build_idf.ps1")], env=environment,
                                   capture_output=True, text=True, errors="replace", timeout=30)
        output = completed.stdout + completed.stderr
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("trying another installation", " ".join(output.split()))
        self.assertIn("FIXTURE_CMAKE_REACHED", output)
        self.assertNotIn("null-valued expression", output)
        manifests = list(cache.glob("constellation-lamp-idf-*/inputs/scene_manifest.json"))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text(encoding="utf-8"))["led_count"], 268)


if __name__ == "__main__":
    unittest.main()
