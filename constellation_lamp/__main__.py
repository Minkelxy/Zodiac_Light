"""Run with python -m constellation_lamp from a checkout or installation."""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from .layout import generate_layout
from .model import ValidationError, compile_layout, read_json
from .reports import summary, write_json, write_reports
from .effects import EFFECT_NAMES, EFFECT_LABELS, EFFECT_DESCRIPTIONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _default_paths():
    # Wheels bundle the authoring data beside the Python modules. Keep checkout
    # commands using the editable source data, but never write installed outputs
    # into site-packages (which may be shared or read-only).
    packaged_data = Path(__file__).resolve().parent / "data"
    if packaged_data.is_dir():
        return packaged_data, Path.cwd() / "build"
    return PROJECT_ROOT / "data", PROJECT_ROOT / "build"


def _runtime(args, *, regenerate=False):
    data = Path(args.data_dir)
    catalog = read_json(data / "catalog.json")
    constellation = read_json(data / "constellation.json")
    layout_path = Path(args.layout) if args.layout else data / "layout.json"
    template = read_json(layout_path) if layout_path.exists() else None
    if args.layout and template is None:
        raise ValidationError(f"Layout does not exist: {layout_path}")
    if regenerate or args.width_mm is not None or template is None:
        layout = generate_layout(catalog, constellation, template, args.width_mm)
    else:
        layout = template
    return compile_layout(catalog, constellation, layout)


def _route(value):
    if value is None:
        return None
    values = [item.strip() for item in value.split(",")]
    if any(not item for item in values):
        raise ValidationError("--route must contain comma-separated star IDs or HIP numbers")
    return [f"hip_{item}" if item.isdigit() else item for item in values]


def _effect_params(args, effect=None):
    effect = effect or args.effect
    params = {"effect": effect, "seed": 1, "brightness": .2, "speed": 1.0, "gamma": 2.2}
    config_path = args.effect_config or Path(args.data_dir) / "effects.json"
    if args.effect_config or config_path.exists():
        config = read_json(config_path)
        defaults = config.get("defaults", {})
        presets = config.get("presets", {})
        if not isinstance(defaults, dict) or not isinstance(presets, dict):
            raise ValidationError("Effect config defaults/presets must be objects")
        if set(presets) - set(EFFECT_NAMES):
            raise ValidationError("Effect config contains an unknown effect ID")
        preset = presets.get(effect, {})
        if not isinstance(preset, dict):
            raise ValidationError(f"Effect preset {effect} must be an object")
        params.update(defaults)
        params.update(preset)
        params["effect"] = effect
    for name in ("seed", "brightness", "speed", "gamma"):
        value = getattr(args, name)
        if value is not None:
            params[name] = value
    if args.route is not None:
        params["route"] = _route(args.route)
    return params


def _hardware_profile(args, runtime, *, transport=True):
    from .hardware import HardwareProfile
    path = args.hardware or Path(args.data_dir) / "hardware.json"
    profile = HardwareProfile.load(path) if args.hardware or path.exists() else HardwareProfile()
    changes = {key: getattr(args, key) for key in ("baud", "fps", "current_limit_ma") if getattr(args, key, None) is not None}
    profile = dataclasses.replace(profile, **changes)
    return profile.validate_runtime(runtime) if transport else profile.validate_power(runtime.led_count)


def main(argv=None) -> int:
    data_dir, output_dir = _default_paths()
    parser = argparse.ArgumentParser(description="Sagittarius WS2812 layout and light-effect simulator")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", type=Path, default=data_dir)
    common.add_argument("--layout", type=Path, help="Use a saved physical layout")
    common.add_argument("--width-mm", type=float, help="Regenerate geometry/wiring at this star-centre width")
    effect_args = argparse.ArgumentParser(add_help=False)
    effect_args.add_argument("--effect", choices=EFFECT_NAMES, default="twinkle")
    effect_args.add_argument("--seed", type=int)
    effect_args.add_argument("--brightness", type=float)
    effect_args.add_argument("--speed", type=float)
    effect_args.add_argument("--gamma", type=float)
    effect_args.add_argument("--effect-config", type=Path, help="Versioned JSON defaults and effect presets")
    effect_args.add_argument("--exposure", type=float, default=3.0, help="Monitor preview exposure; does not change RGB bytes")
    effect_args.add_argument("--route", help="Flow route, comma-separated HIP numbers or star IDs")
    effect_args.add_argument("--hardware", type=Path, help="Hardware/current/transport JSON profile")
    effect_args.add_argument("--current-limit-ma", type=float, help="Override the estimated current budget")
    commands.add_parser("validate", parents=[common], help="Read and validate the physical layout")
    layout_parser = commands.add_parser("layout", parents=[common], help="Regenerate an initial physical layout")
    layout_parser.add_argument("--output", type=Path, default=output_dir / "layout.json")
    build_parser = commands.add_parser("build", parents=[common, effect_args], help="Export full/compact tables, reports and all effect previews")
    build_parser.add_argument("--output-dir", type=Path, default=output_dir)
    preview_parser = commands.add_parser("preview", parents=[common, effect_args], help="Open the interactive simulator")
    render_parser = commands.add_parser("render", parents=[common, effect_args], help="Save an offline preview PNG")
    render_parser.add_argument("--time-ms", type=float, default=1500)
    render_parser.add_argument("--output", type=Path, default=output_dir / "preview.png")
    export_parser = commands.add_parser("export", parents=[common], help="Export MCU C constant tables")
    export_parser.add_argument("--compact", action="store_true", help="Export quantized SoA MCU tables")
    export_parser.add_argument("--output", type=Path)
    commands.add_parser("effects", help="List available effects")
    commands.add_parser("ports", help="List serial ports; never opens or sends to them")
    stream_parser = commands.add_parser("stream", parents=[common, effect_args], help="Send RGB to ESP32, or save an offline CLP1 capture")
    destination = stream_parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--port", help="Explicit serial port, e.g. COM3")
    destination.add_argument("--dry-run", type=Path, help="Write deterministic packets without opening hardware")
    stream_parser.add_argument("--duration", type=float, default=10, help="Seconds of playback/capture")
    stream_parser.add_argument("--baud", type=int)
    stream_parser.add_argument("--fps", type=float)
    args = parser.parse_args(argv)
    try:
        if args.command == "effects":
            for name in EFFECT_NAMES:
                print(f"{name:12} {EFFECT_LABELS[name]}: {EFFECT_DESCRIPTIONS[name]}")
            return 0
        if args.command == "ports":
            try:
                from serial.tools import list_ports
            except ImportError as error:
                raise ValidationError('Install serial support: python -m pip install "pyserial>=3.5"') from error
            ports = sorted(list_ports.comports(), key=lambda item: item.device)
            for port in ports:
                print(f"{port.device}: {port.description}")
            if not ports:
                print("No serial ports detected")
            return 0
        runtime = _runtime(args, regenerate=args.command == "layout")
        if args.command == "layout":
            write_json(args.output, runtime.layout)
            print(summary(runtime))
            print(f"Generated layout: {args.output.resolve()}")
            return 0
        if args.command == "validate":
            print(summary(runtime))
            return 0
        if args.command == "export":
            if args.compact:
                from .compact import export_compact_c, pack_runtime
                output = args.output or output_dir / "constellation_compact.h"
                export_compact_c(runtime, output)
                print(f"Compact table storage: {pack_runtime(runtime)['metadata']['c_arrays_bytes']} bytes")
            else:
                from .export import export_c
                output = args.output or output_dir / "constellation_data.h"
                export_c(runtime, output)
            print(summary(runtime))
            print(f"C tables: {output.resolve()}")
            return 0
        params = _effect_params(args)
        from .effects import render
        import math
        import numpy as np
        if not math.isfinite(args.exposure) or args.exposure <= 0:
            raise ValidationError("--exposure must be a positive finite number")
        # Validate effect settings before writing any build outputs.
        frame = np.zeros((runtime.led_count, 3), dtype=np.uint8)
        validation_effects = EFFECT_NAMES if args.command in ("build", "preview") else (args.effect,)
        presets = {name: _effect_params(args, name) for name in validation_effects}
        for selected in validation_effects:
            render(runtime, args.time_ms if args.command == "render" else 0,
                   presets[selected], {}, frame)
        if args.command == "stream":
            from .seriallink import capture_frames, stream_frames
            profile = _hardware_profile(args, runtime)
            if args.dry_run:
                result = capture_frames(runtime, args.dry_run, params, profile, duration_s=args.duration)
                print(f"Offline packets: {args.dry_run.resolve()}")
            else:
                result = stream_frames(runtime, args.port, params, profile, duration_s=args.duration)
            print(result)
            return 0
        profile = _hardware_profile(args, runtime, transport=False)
        if args.command == "preview":
            from .preview import show
            print(summary(runtime))
            show(runtime, effect=args.effect, seed=params["seed"], brightness=params["brightness"], route=params.get("route"),
                 exposure=args.exposure, params=params, presets=presets, hardware_profile=profile)
        else:
            # Select a noninteractive backend before importing pyplot.
            import matplotlib
            matplotlib.use("Agg")
            from .preview import save_preview
            if args.command == "render":
                save_preview(runtime, args.output, effect=args.effect, time_ms=args.time_ms,
                             seed=params["seed"], brightness=params["brightness"], route=params.get("route"), exposure=args.exposure,
                             params=params, hardware_profile=profile)
                print(f"Preview: {args.output.resolve()}")
            else:
                from .export import export_c
                from .compact import export_compact_c, pack_runtime
                packed = pack_runtime(runtime)
                output = args.output_dir
                write_json(output / "layout.json", runtime.layout)
                write_reports(runtime, output)
                export_c(runtime, output / "constellation_data.h")
                export_compact_c(runtime, output / "constellation_compact.h")
                write_json(output / "compact.json", packed)
                for effect in EFFECT_NAMES:
                    effect_params = presets[effect]
                    save_preview(runtime, output / f"preview_{effect}.png", effect=effect, time_ms=1500,
                                 seed=effect_params["seed"], brightness=effect_params["brightness"],
                                 route=effect_params.get("route"), exposure=args.exposure, params=effect_params,
                                 hardware_profile=profile)
                from .gallery import save_gallery
                save_gallery(runtime, output / "effects_gallery.png", [presets[name] for name in EFFECT_NAMES],
                             exposure=args.exposure, hardware_profile=profile)
                print(f"Compact tables: {packed['metadata']['c_arrays_bytes']} bytes; RGB frame: {runtime.led_count * 3} bytes")
                print(f"Build output: {output.resolve()}")
            print(summary(runtime))
        return 0
    except (ValidationError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Stopped; serial stream attempted blackout and closed the port", file=sys.stderr)
        return 130


if __name__ == "__main__":
    # Redirected Windows output otherwise follows the system ANSI code page.
    # The app and generated logs use UTF-8, including Chinese project paths.
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure") and not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
