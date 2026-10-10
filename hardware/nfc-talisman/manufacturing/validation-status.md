# Validation status — 2026-10-10

This is a reviewable first-pass design draft, not a manufacturing release.

## EasyEDA checks

- Schematic ERC completed successfully: 0 errors and 1 `ATTRMATCHCODE` library-property warning affecting 11 parts.
- After all routing and fill changes were saved, both PCB documents were closed and reopened before fresh DRC. Core PCB and panel DRC each returned an empty `drc` array. The core contains 15 components, 38 pads, 126 copper lines, 10 vias and 1 fill. The panel contains 15 components, 146 pads, 126 copper lines, 10 vias, 1 fill and 88 polylines. TP1 (VOUT) and TP2 (GND) are Top free pads at core-relative (80,115) mil and (235,115) mil; panel copies use +50 mm X/Y translation. Each has 0.8 mm circular copper and 0.9 mm mask opening, with no hole or paste opening, and is excluded from BOM/PnP. The 10 vias have 0.30 mm drill / 0.55 mm copper diameter and pass the native rules on both documents.
- The prior netlist mismatch is resolved. SCH/core each have 15 components and 36 pads with matching nets. Applying the native `setNetlist` dialog's `Population=Fit` and `PCB Side=Top` attributes for U1 and D1 cleared it; copying Channel ID alone did not. L1 is a virtual coil element, not the root cause.
- The coil fill's bridge-copper configuration survived native save/reopen: `isBridgingCopper=true`, `networkList=['ANT_LA','ANT_LB']`. The separate offline clearance audit covered only the old 19-track snapshot; it is not a substitute for the current native DRC or CAM review.
- The native copper audit reports 11 nets passing, minimum different-net copper spacing 0.18669 mm, via-to-adjacent-coil-turn gap 0.20199 mm, and core/panel copper identical after a +50 mm coordinate translation.

## Electrical assembly review

- Verify each LED's physical cathode mark against the EDA library pad mapping during placement; the schematic A/K labels do not imply pad numbers 1/2.
- CT1 is 47 pF C0G as a starting value only. It has not been tuned against the bare board or five-layer stack; record resonance and read range before changing CT1/CT2.
- C1 is the only 150 nF capacitor, shared by VCC decoupling and VOUT storage. Do not add another VCC capacitor in this design revision.
- Native core and panel DRC completed with empty results after save, close and reopen; the antenna bridge setting also survived native round-trip. RF, VOUT/LED load tests, phone read/write and the full physical acceptance remain pending.

## Mechanical checks

`python hardware/nfc-talisman/scripts/build_mechanical.py` passes the geometric validation. The 100×100 mm panel is connected as one part, retains 3 mm top/bottom rails, and holds five subboards using twenty 5 mm tabs. Each tab has five Ø0.6 mm NPTH mousebites on 0.95 mm pitch, for 0.35 mm nominal hole-edge spacing. The panel contains 100 mousebites and 8 constellation holes. The eight-star/eleven-slot design retains at least 1.0 mm nominal webs.

The panel preview is `../geometry/panel-review.png`; geometry inputs and the validation measurements are in `../geometry/design.json` and `../geometry/validation.json`.

## Remaining work

- Review the remaining schematic ERC library warning before release.
- Measure bare-core and assembled-stack resonance/phone read range; CT1 47 pF is not a tuned value, and VOUT/LED load tests remain pending.
- The horse artwork remains for manual user import; the horse cover has no optical window. Confirm image alignment and the final light path on a sample. Current Gerber used `colorSilkscreen=false` and does not contain horse art/color printing.
- The current 3 mm rails need review if machine assembly is selected; the panel has not been qualified for SMT tooling or fiducials.
- Confirm cutter compensation and edge tolerances in CAM, especially 1 mm star/slot webs, the shortest 1.202 mm slot and 3 mm rails. The original 22 panel outline GKO polylines were not explicitly closed, causing a fabrication gap; the generator and live panel were corrected, and the saved/reopened panel DRC is empty. Read-only CAM precheck passed: 22/22 closed GKO paths, 10 PTH and 108 NPTH location checks, coil/lead copper consistency, and TP1/TP2 copper/mask/no-paste checks. Formal cutter compensation, slot machining and process review remain pending. Two PTH drill files contain the same 10 locations; choose one only to prevent duplicate drill operations. See `manufacturing/draft/export-manifest.json` for current export hashes and sizes.
- The raw `bom-all.csv`/`pnp-all.csv` include all 15 parts and are not assembly-ready. Default four-LED filtered files exclude only fixed-DNP CT2 and contain 14 items. Optional two-LED files exclude CT2/D2/D4 and contain 12 items; R2/R4 remain Fit. Default BOM remains four LEDs. Gerber uses `colorSilkscreen=false`; horse art and color print are absent.
- `ATTRMATCHCODE` still affects 11 parts, with no exact triggering attribute established. Values/MPNs match the reviewed BOM; CT2 has a 47 pF/C60137 placeholder while DNP. C1 library Description contains an NRND notice; verify current availability and alternatives before procurement.
- Complete a five-layer dry fit, measure NFC behavior on the bare core and full stack, and record Android/iPhone read-write and optical tests before bonding.
