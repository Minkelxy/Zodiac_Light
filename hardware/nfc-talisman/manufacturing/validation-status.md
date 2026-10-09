# Validation status — 2026-10-10

This is a reviewable first-pass design draft, not a manufacturing release.

## EasyEDA checks

- Schematic ERC completed successfully: 0 errors and 1 `ATTRMATCHCODE` library-property warning affecting 11 parts.
- Core PCB DRC: 22 unconnected-pad reports (`VOUT` 10, `GND` 6, `ANT_LA` 3, `ANT_LB` 3), plus 1 schematic/PCB netlist mismatch. The DRC reports no separate short or clearance category.
- Panel PCB DRC after the tab update: 22 unconnected-pad reports for the replicated circuit; no hole-to-hole/clearance category remains.
- Core board currently has 15 components, 36 pads, 19 copper lines, 0 vias and 0 fills. The 19 existing lines passed the separate geometry screen: minimum different-net track-to-pad gap 0.2827 mm and different-net track-to-track gap 0.4019 mm. This screen does not replace native DRC.
- The schematic and PCB each list the same 15 component references. EasyEDA's beta netlist comparison returned no serializable result, so the native netlist mismatch remains unexplained and unresolved.

## Mechanical checks

`python hardware/nfc-talisman/scripts/build_mechanical.py` passes the geometric validation. The 100×100 mm panel is connected as one part, retains 3 mm top/bottom rails, and holds five subboards using twenty 5 mm tabs. Each tab has five Ø0.6 mm NPTH mousebites on 0.95 mm pitch, for 0.35 mm nominal hole-edge spacing. The panel contains 100 mousebites and 8 constellation holes. The eight-star/eleven-slot design retains at least 1.0 mm nominal webs.

The panel preview is `../geometry/panel-review.png`; geometry inputs and the validation measurements are in `../geometry/design.json` and `../geometry/validation.json`.

## Remaining work

- Finish the VOUT/GND routes, antenna endpoints and tuning network; resolve the native netlist mismatch and rerun ERC/DRC after changes.
- The antenna coil proposal passes the current offline geometry screen, but it has not been applied. EasyEDA bridge-copper configuration, native DRC and assembled-stack RF tuning remain unverified.
- The horse cover remains artwork-free by design; the user will manually import the reference horse image. Then determine the final optical window, alignment and light transmission.
- The current 3 mm rails need review if machine assembly is selected; the panel has not been qualified for SMT tooling or fiducials.
- Confirm camera/slot cutter compensation and edge tolerances in CAM; no reviewed Gerber, NC Drill, BOM or pick-and-place package exists yet.
- Complete a five-layer dry fit, measure NFC behavior on the bare core and full stack, and record Android/iPhone read-write and optical tests before bonding.
