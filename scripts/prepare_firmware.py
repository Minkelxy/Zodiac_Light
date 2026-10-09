"""Validate and synchronize authoring data with an ESP-IDF build, using stdlib.

Generated inputs live in the ASCII build cache. No checked-in scene header is
changed. Validation and header generation finish before any existing input or
sdkconfig is replaced.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from constellation_lamp.compact import export_compact_c, pack_runtime
from constellation_lamp.hardware import HardwareProfile
from constellation_lamp.model import ValidationError, load_runtime, read_json
from constellation_lamp.native_export import build_native_presets
from constellation_lamp.effectspec import EFFECT_NAMES


ESP32_OUTPUT_GPIOS = frozenset((0, 2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19,
                              21, 22, 23, 25, 26, 27, 32, 33))
SDK_RANGES = {
    "LED_COUNT": (1, 1024), "BAUD": (9600, 2000000),
    "CURRENT_LIMIT_MA": (1, 100000), "IDLE_LED_UA": (0, 100000),
    "CHANNEL_UA": (1, 100000), "STREAM_TIMEOUT_MS": (100, 60000),
    "PACKET_TIMEOUT_MS": (100, 5000), "RESET_US": (300, 1000),
    "LOCAL_MODE": (0, 4), "NATIVE_EFFECT": (0, len(EFFECT_NAMES) - 1),
}
_SETTING = re.compile(r"^CONFIG_CLP_([A-Z_]+)=(-?\d+)\s*$")


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _integer(value, label, bounds=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f"{label} must be a finite integer")
    if int(value) != value:
        raise ValidationError(f"{label} must be an integer for ESP-IDF Kconfig")
    value = int(value)
    if bounds is not None and not bounds[0] <= value <= bounds[1]:
        raise ValidationError(f"{label} must be {bounds[0]}..{bounds[1]}")
    return value


def _microamps(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f"{label} must be finite")
    if value < 0:
        raise ValidationError(f"{label} must be nonnegative")
    # Firmware stores integer microamps. The emitted host profile uses the same
    # rounded coefficients, so the host and MCU always estimate identical power.
    return int(math.floor(value * 1000.0 + 0.5))


def read_sdkconfig(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    values = {}
    for line in text.splitlines():
        match = _SETTING.match(line)
        if match:
            values[match[1]] = int(match[2])
    return text, values


def patch_sdkconfig(text, updates):
    """Replace only owned settings, keeping unrelated menuconfig choices."""
    remaining = dict(updates)
    lines = []
    for line in text.splitlines():
        match = re.match(r"^(?:# )?CONFIG_CLP_([A-Z_]+)(?:=| is not set)", line)
        key = match[1] if match else None
        if key in updates:
            if key in remaining:
                lines.append(f"CONFIG_CLP_{key}={remaining.pop(key)}")
            continue  # Remove a duplicate stale setting if one exists.
        lines.append(line)
    lines.extend(f"CONFIG_CLP_{key}={value}" for key, value in remaining.items())
    return "\n".join(lines) + "\n"


def _commit_files(files):
    """Stage on destination volumes, then replace; roll back a failed commit."""
    staged, backups, replaced = {}, {}, []
    try:
        for path, contents in files.items():
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            backups[path] = path.read_bytes() if path.exists() else None
            descriptor, name = tempfile.mkstemp(prefix=".clp-input-", dir=path.parent)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(contents)
            staged[path] = Path(name)
        for path, temporary in staged.items():
            os.replace(temporary, path)
            replaced.append(path)
    except BaseException:
        for path in reversed(replaced):
            old = backups[path]
            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(old)
        raise
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)


def _board_gpio(raw):
    board = raw.get("board", {})
    if not isinstance(board, dict):
        raise ValidationError("Hardware profile board must be an object")
    if board.get("framework", "esp-idf") != "esp-idf":
        raise ValidationError("Native firmware requires board.framework='esp-idf'")
    if board.get("reference", "esp32") not in ("esp32", "esp32dev", "esp32-devkit-v1", "esp32-wroom-32"):
        raise ValidationError("This native build targets a classic ESP32 board")
    pin = _integer(board.get("data_pin", 18), "board.data_pin")
    if pin not in ESP32_OUTPUT_GPIOS:
        raise ValidationError("board.data_pin must be an ESP32 output GPIO; GPIO1/3 are reserved for UART0 and GPIO6..11 for flash")
    return pin


def _settings(profile, led_count, gpio):
    values = {
        "LED_COUNT": led_count, "DATA_GPIO": gpio, "BAUD": profile.baud,
        "CURRENT_LIMIT_MA": profile.current_limit_ma,
        "IDLE_LED_UA": _microamps(profile.idle_led_ma, "idle_led_ma"),
        "CHANNEL_UA": _microamps(profile.channel_ma, "channel_ma"),
        "STREAM_TIMEOUT_MS": profile.stream_timeout_ms,
        "PACKET_TIMEOUT_MS": profile.packet_timeout_ms, "RESET_US": profile.reset_us,
    }
    return {key: _integer(value, key, SDK_RANGES.get(key)) for key, value in values.items()}


def _profile_from_settings(values, requested_fps):
    profile = HardwareProfile(baud=values["BAUD"], fps=requested_fps,
        current_limit_ma=values["CURRENT_LIMIT_MA"], idle_led_ma=values["IDLE_LED_UA"] / 1000,
        channel_ma=values["CHANNEL_UA"] / 1000, reset_us=values["RESET_US"],
        packet_timeout_ms=values["PACKET_TIMEOUT_MS"], stream_timeout_ms=values["STREAM_TIMEOUT_MS"])
    return profile.adapt_fps(values["LED_COUNT"], requested_fps)


def _hardware_json(profile, settings, sha256):
    return {
        "schema_version": 1,
        "board": {"reference": "esp32", "framework": "esp-idf", "data_pin": settings["DATA_GPIO"],
                  "hardware_tested": False},
        "scene": {"led_count": settings["LED_COUNT"], "sha256": sha256},
        "transport": {"protocol": "CLP1", "baud": profile.baud, "fps": profile.fps, "frame_order": "RGB",
                      "packet_timeout_ms": profile.packet_timeout_ms,
                      "require_device_identity": profile.require_device_identity},
        "ws2812": {"wire_order": "GRB", "bit_rate_hz": 800000, "reset_us": profile.reset_us,
                   "timeout_ms": profile.stream_timeout_ms},
        "power_estimate": {"supply_voltage_v": 5, "current_limit_ma": profile.current_limit_ma,
                           "idle_led_ma": profile.idle_led_ma, "channel_ma": profile.channel_ma},
    }


def prepare_inputs(project_root, generated_dir, sdkconfig_path, *, hardware_path=None, mode=-1, effect=None):
    """Generate checked scene/config inputs and synchronize a cached sdkconfig."""
    project_root, generated_dir, sdkconfig_path = map(Path, (project_root, generated_dir, sdkconfig_path))
    mode = _integer(mode, "mode", (-1, 4))
    if effect is not None:
        if effect not in EFFECT_NAMES:
            raise ValidationError(f"Unknown native effect {effect!r}")
        if mode not in (-1, 4):
            raise ValidationError("--effect requires mode 4; it cannot be combined with mode 0..3")
        mode = 4
    data_dir = project_root / "data"
    hardware_path = Path(hardware_path) if hardware_path else data_dir / "hardware.json"
    runtime = load_runtime(data_dir)
    packed = pack_runtime(runtime)
    sha256 = packed["metadata"]["scene_sha256"]
    native_header, native_metadata = build_native_presets(runtime, data_dir / "effects.json")
    raw = read_json(hardware_path)
    profile = HardwareProfile.load(hardware_path)
    requested_fps = profile.fps
    profile = profile.adapt_fps(runtime.led_count, requested_fps)
    # Validate scene identity on profiles pinned to a built firmware.
    profile.validate_runtime(runtime)
    settings = _settings(profile, runtime.led_count, _board_gpio(raw))
    profile = _profile_from_settings(settings, profile.fps)
    profile = dataclasses.replace(profile, expected_led_count=runtime.led_count, scene_sha256=sha256,
                                  require_device_identity=HardwareProfile.load(hardware_path).require_device_identity)
    profile.validate_runtime(runtime)
    config_text, cached = read_sdkconfig(sdkconfig_path)
    actual_mode = mode if mode >= 0 else cached.get("LOCAL_MODE", 0)
    actual_mode = _integer(actual_mode, "LOCAL_MODE", SDK_RANGES["LOCAL_MODE"])
    effect_index = EFFECT_NAMES.index(effect) if effect is not None else cached.get("NATIVE_EFFECT", 0)
    effect_index = _integer(effect_index, "NATIVE_EFFECT", SDK_RANGES["NATIVE_EFFECT"])
    updates = dict(settings)
    if mode >= 0:
        updates["LOCAL_MODE"] = mode
    if effect is not None:
        updates["NATIVE_EFFECT"] = effect_index
    defaults = {**settings, "LOCAL_MODE": actual_mode, "NATIVE_EFFECT": effect_index}
    hashes = {name: hashlib.sha256((data_dir / name).read_bytes()).hexdigest()
              for name in ("catalog.json", "constellation.json", "layout.json", "effects.json")}
    hashes["hardware.json"] = hashlib.sha256(hardware_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1, "target": "esp32", "scene_sha256": sha256,
        "scene_fingerprint_source": "compact_scene_and_electrical_wiring_v1",
        "source_files_sha256": hashes, "hardware_source": str(hardware_path.resolve()),
        "mode_override": mode, "actual_mode": actual_mode, "native_effect_index": effect_index,
        "native_effect": EFFECT_NAMES[effect_index], "led_count": runtime.led_count,
        "data_gpio": settings["DATA_GPIO"], "requested_fps": requested_fps,
        "actual_fps": profile.fps, "fps_source": "hardware.json adapted to UART + WS2812 + ACK timing",
        "hardware_profile": dataclasses.asdict(profile), "settings": defaults,
        "native_presets": native_metadata,
        "compact_table_bytes": packed["metadata"]["table_bytes"], "hardware_tested": False,
    }
    # Even a header-export error leaves the old config and metadata untouched.
    with tempfile.TemporaryDirectory(prefix="clp-scene-stage-") as temporary:
        header = Path(temporary) / "constellation_compact.h"
        export_compact_c(runtime, header)
        manifest["generated_header_sha256"] = hashlib.sha256(header.read_bytes()).hexdigest()
        files = {
            generated_dir / "constellation_compact.h": header.read_bytes(),
            generated_dir / "native_presets.h": native_header.encode("utf-8"),
            generated_dir / "derived.sdkconfig.defaults": patch_sdkconfig("", defaults).encode("utf-8"),
            generated_dir / "scene_manifest.json": _json_bytes(manifest),
            generated_dir / "hardware.json": _json_bytes(_hardware_json(profile, settings, sha256)),
        }
        if sdkconfig_path.exists():
            files[sdkconfig_path] = patch_sdkconfig(config_text, updates).encode("utf-8")
        _commit_files(files)
    return manifest


def finalize_build(project_root, generated_dir, sdkconfig_path, artifact_dir, *, sdk_path=None,
                   python_path=None, source_alias=None, build_directory=None):
    """Publish a hardware profile that describes the actual built configuration."""
    generated_dir, artifact_dir = Path(generated_dir), Path(artifact_dir)
    manifest = read_json(generated_dir / "scene_manifest.json")
    runtime = load_runtime(Path(project_root) / "data")
    sha256 = pack_runtime(runtime)["metadata"]["scene_sha256"]
    if manifest["scene_sha256"] != sha256:
        raise ValidationError("Scene changed during the build; prepare and rebuild before publishing")
    data_dir = Path(project_root) / "data"
    for name, digest in manifest["source_files_sha256"].items():
        source = Path(manifest["hardware_source"]) if name == "hardware.json" else data_dir / name
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValidationError(f"Authoring input {name} changed during the build; prepare and rebuild")
    if hashlib.sha256((generated_dir / "constellation_compact.h").read_bytes()).hexdigest() != manifest["generated_header_sha256"]:
        raise ValidationError("Generated scene header changed during the build; prepare and rebuild")
    if hashlib.sha256((generated_dir / "native_presets.h").read_bytes()).hexdigest() != manifest["native_presets"]["header_sha256"]:
        raise ValidationError("Generated native preset header changed during the build; prepare and rebuild")
    _, settings = read_sdkconfig(sdkconfig_path)
    required = ("LED_COUNT", "DATA_GPIO", "BAUD", "CURRENT_LIMIT_MA", "IDLE_LED_UA", "CHANNEL_UA",
                "STREAM_TIMEOUT_MS", "PACKET_TIMEOUT_MS", "RESET_US", "LOCAL_MODE", "NATIVE_EFFECT")
    for key in required:
        if key not in settings:
            raise ValidationError(f"Built sdkconfig lacks CONFIG_CLP_{key}")
        _integer(settings[key], key, SDK_RANGES.get(key))
    if settings["LED_COUNT"] != runtime.led_count:
        raise ValidationError("Built LED count does not match the generated scene")
    _board_gpio({"board": {"data_pin": settings["DATA_GPIO"]}})
    if manifest["mode_override"] >= 0 and settings["LOCAL_MODE"] != manifest["mode_override"]:
        raise ValidationError("Built mode does not match the explicit requested mode")
    for key in ("LED_COUNT", "DATA_GPIO", "BAUD", "CURRENT_LIMIT_MA", "IDLE_LED_UA", "CHANNEL_UA",
                "STREAM_TIMEOUT_MS", "PACKET_TIMEOUT_MS", "RESET_US"):
        if settings[key] != manifest["settings"][key]:
            raise ValidationError(f"Built CONFIG_CLP_{key} differs from hardware.json; synchronize and rebuild")
    profile = _profile_from_settings(settings, manifest["requested_fps"])
    profile = dataclasses.replace(profile, expected_led_count=runtime.led_count, scene_sha256=sha256,
                                  require_device_identity=manifest["hardware_profile"]["require_device_identity"])
    profile.validate_runtime(runtime)
    hardware = _hardware_json(profile, settings, sha256)
    binary = artifact_dir / "constellation_lamp_idf.bin"
    if not binary.is_file():
        raise ValidationError(f"Missing built firmware binary: {binary}")
    manifest.update({"actual_mode": settings["LOCAL_MODE"], "native_effect_index": settings["NATIVE_EFFECT"],
        "native_effect": EFFECT_NAMES[settings["NATIVE_EFFECT"]], "settings": settings,
        "data_gpio": settings["DATA_GPIO"], "actual_fps": profile.fps,
        "hardware_profile": dataclasses.asdict(profile), "sdk_path": sdk_path, "python_path": python_path,
        "source_alias": source_alias, "build_directory": build_directory,
        "firmware_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
    _commit_files({artifact_dir / "hardware.json": _json_bytes(hardware),
                   artifact_dir / "build_manifest.json": _json_bytes(manifest),
                   artifact_dir / "constellation_compact.h": (generated_dir / "constellation_compact.h").read_bytes(),
                   artifact_dir / "native_presets.h": (generated_dir / "native_presets.h").read_bytes()})
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "finalize"))
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--sdkconfig", type=Path, required=True)
    parser.add_argument("--hardware", type=Path)
    parser.add_argument("--mode", type=int, default=-1)
    parser.add_argument("--effect", choices=EFFECT_NAMES)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--sdk-path")
    parser.add_argument("--python-path")
    parser.add_argument("--source-alias")
    parser.add_argument("--build-directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_inputs(args.project_root, args.generated_dir, args.sdkconfig,
                                    hardware_path=args.hardware, mode=args.mode, effect=args.effect)
        else:
            if args.artifact_dir is None:
                parser.error("finalize requires --artifact-dir")
            result = finalize_build(args.project_root, args.generated_dir, args.sdkconfig, args.artifact_dir,
                sdk_path=args.sdk_path, python_path=args.python_path, source_alias=args.source_alias,
                build_directory=args.build_directory)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"Firmware input error: {error}\n")


if __name__ == "__main__":
    main()
