# Validation status — 2026-10-10

This is a reviewable first-pass design draft, not a manufacturing release.

## Current layout and BOM review v3 — 2026-10-10

This section supersedes earlier snapshot and drift notes below. The schematic was reorganized into functional blocks, all 36 pin connections were preserved, and four current-limit resistors were moved about 0.20 mm inward with 10 corrected routes on both core and panel. Save/reopen native checks report schematic ERC 0 errors / 1 existing ATTRMATCHCODE warning, core DRC empty and panel DRC empty. Fresh source, netlist, pad, native project, Gerber and PnP exports were archived together. Native copper audit now reports minimum different-net copper clearance **0.20140041 mm**, all 11 nets connected, and matching +50 mm core/panel copper. Native netlist, CAM, star-aperture and color-file checks pass for this refreshed revision. See `design-review-v3.md`, `draft/export-manifest.json` and `eda/check-summary.json` for current evidence.

`bom-ready.csv` and `bom-review.md` document 14 fitted parts for four LEDs / 12 for two LEDs; CT2 is excluded. C1's specified Murata part is marked NRND in native library metadata; a same-spec CCTC alternative is listed with Qty 0 and has not replaced native C1. Manual horse artwork/window, official color-compositing/process preview and physical RF/phone/optical acceptance remain pending. The entries below retain earlier review history.

## Automation archive review — 2026-10-10 10:52 CST

Re-ran the offline native copper, netlist and manufacturing CAM audits; all reported geometric/connectivity checks passed. `scripts/audit_delivery_integrity.py` verified 39 archived hash/size, check-log/native-source, ZIP CRC and CAM layer-content checks, with no failures; report: `draft/delivery-integrity.json`. Retained CAM layers equal the raw export byte-for-byte, and the review ZIP excludes the duplicate PTH program. This run did not inspect live/unsaved EasyEDA state or execute fresh native ERC/DRC. Added `sample-test-plan.md` to organize the pending physical test matrix and the horse optical decision gate. No physical results or manufacturing release were asserted.

## EasyEDA checks

- Schematic ERC completed successfully: 0 errors and 1 `ATTRMATCHCODE` library-property warning affecting 11 parts.
- After all routing and fill changes were saved, both PCB documents were closed and reopened before fresh DRC. Core PCB and panel DRC each returned an empty `drc` array. The core contains 15 components, 38 pads, 126 copper lines, 10 vias and 1 fill. The earlier panel snapshot contained 15 components, 146 pads, 126 copper lines, 10 vias, 1 fill and 88 polylines; the newer refined panel count is recorded below. TP1 (VOUT) and TP2 (GND) are Top free pads at core-relative (80,115) mil and (235,115) mil; panel copies use +50 mm X/Y translation. Each has 0.8 mm circular copper and 0.9 mm mask opening, with no hole or paste opening, and is excluded from BOM/PnP. The 10 vias have 0.30 mm drill / 0.55 mm copper diameter and pass the native rules on both documents.
- The prior netlist mismatch is resolved. SCH/core each have 15 components and 36 pads with matching nets. Applying the native `setNetlist` dialog's `Population=Fit` and `PCB Side=Top` attributes for U1 and D1 cleared it; copying Channel ID alone did not. L1 is a virtual coil element, not the root cause.
- The coil fill's bridge-copper configuration survived native save/reopen: `isBridgingCopper=true`, `networkList=['ANT_LA','ANT_LB']`. The separate offline clearance audit covered only the old 19-track snapshot; it is not a substitute for the current native DRC or CAM review.
- Before v3, the native copper audit reported minimum different-net copper spacing 0.18669 mm. The current v3 value is 0.20140041 mm; the coil's adjacent-turn gap and +50 mm core/panel relation remain verified.

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
- Horse artwork remains for manual user import; the horse cover has no optical window. Confirm image alignment and the final light path on a sample. The Sagittarius back-cover color OBJ and its dedicated color files are now present as draft output; official CAM preview and sample acceptance are pending.
- The current 3 mm rails need review if machine assembly is selected; the panel has not been qualified for SMT tooling or fiducials.
- Confirm cutter compensation and edge tolerances in CAM, especially 1 mm star/slot webs, the shortest 1.489 mm slot and 3 mm rails. The earlier panel outline closure and CAM precheck results remain historical. Formal cutter compensation, slot machining and process review remain pending. Two PTH drill files contain the same 10 locations; choose one only to prevent duplicate drill operations. Consult the current export manifest when preparing a review; do not copy hashes from an older snapshot.
- The raw `bom-all.csv`/`pnp-all.csv` include all 15 parts and are not assembly-ready. Default four-LED filtered files exclude only fixed-DNP CT2 and contain 14 items. Optional two-LED files exclude CT2/D2/D4 and contain 12 items; R2/R4 remain Fit. Default BOM remains four LEDs. Horse art remains absent; Sagittarius color OBJ and color-print files are draft outputs pending official CAM review.
- `ATTRMATCHCODE` still affects 11 parts, with no exact triggering attribute established. Values/MPNs match the reviewed BOM; CT2 has a 47 pF/C60137 placeholder while DNP. C1 library Description contains an NRND notice; verify current availability and alternatives before procurement.
- Complete a five-layer dry fit, measure NFC behavior on the bare core and full stack, and record Android/iPhone read-write and optical tests before bonding.

## Sagittarius artwork update — 2026-10-10

The eight Ø0.8 mm NPTH star holes and eleven 1.0 mm routed slots remain unchanged. Slot endpoints use an independent setback per edge. The earlier offline optimization values (1.029003 mm quantized web and 1.488858 mm shortest slot) are candidate-stage figures; current saved/exported measurements are recorded below.

The exterior-facing artwork has 96 paths: 65 Latin paths, one outer keyline, eight fine star rings and twenty-two fine connector lines at 0.18 mm stroke width. Printed connector lines do not transmit light; the eleven routed slots remain isolated by material webs. The user-selected dark-background/light-line color draft is imported as a back-cover color OBJ. The dark SVG preview remains an appearance reference; official CAM preview is still needed to confirm dedicated color-file pixel/alpha compositing and stacking order. Horse art remains a manual user import.

**Superseded optimization-stage values:** 1.029003 mm quantized minimum web and 1.488858 mm shortest overall slot describe the candidate-stage report above. Current saved/exported geometry measurements follow below.

## Earlier automation consistency review — 2026-10-10 (historical snapshot)

The findings below describe the cross-version snapshot at that review time; the refreshed native source and reports are recorded in the following section.

The 11:39 client logs report clean core and panel DRC; panel polylines are now 118. The 42-refine-star-slots-and-silkscreen log reports applied_saved_reopened. These newer logs do not establish that the existing native snapshots and manufacturing ZIP were refreshed.

Re-running audit_delivery_integrity.py failed one of 39 checks: the panel DRC log no longer matches the hash in eda/check-summary.json. The archived manufacturing file hashes and ZIP checks still pass. The summary has deliberately not been rehashed to imply a matching new source revision.

Read-only audit_star_face.py produced draft/star-face-audit.json: native aperture, Gerber aperture, window coverage and silkscreen comparisons do not pass against current offline geometry/artwork. Web geometry passes. Treat these as unresolved cross-version comparisons, not proof of a defect in the saved live panel. Do not use the archived ZIP as the refined design's manufacturing output.

At that point, the next work was to recover/export a source-aligned revision and rerun the audits. That cross-version finding is superseded by the saved/reopened source and current audit results below; do not apply it to the current panel. Horse manual import, official color preview, RF tuning, phone read/write and optical acceptance remain pending. No external action was taken.

## Latest Sagittarius source and export review — 2026-10-10

After the refined panel was saved and reopened, the latest core and panel DRC each reported 0 issues. SCH ERC reported 0 errors and 1 warning. The current panel has 118 polylines (22 outline plus 96 silk paths) and one separate colorful OBJ. The 96 silk paths comprise 65 Latin paths, one outer keyline, eight star rings and twenty-two connector lines.

The current `draft/star-face-audit.json` passes all checks against native apertures, actual Gerber apertures, exported outline and artwork: 8 star holes and 11 closed routed slots match; minimum exported star-to-slot web is 1.030017 mm, slot-to-slot web is 1.030699 mm, minimum silk-to-aperture clearance is 0.199165 mm, all apertures fit within the mirrored 30 mm spacer window with 0.85 mm minimum edge clearance, and board material remains connected. The shortest routed slot is 1.489 mm overall with 0.489 mm centerline length. Supplier tool compensation and cutter behavior are outside this geometric audit.

The selected dark-background/light-line Sagittarius image is imported as a 3700×3700 RGBA color OBJ for a 37×37 mm cover. After save/reopen, the native export BLOB and local PNG match byte-for-byte at 119729 bytes, and all 95 aperture sampling points are transparent. The four dedicated color files (FCTS, FCBS, FCBO and FCBM) pass the current presence/integrity audit in `draft/star-color-audit.json`. The proprietary binary pixel/alpha content, color compositing and layer order still require review in the official CAM preview. Horse art is not imported and remains a manual user task.

The project remains a manufacturing draft. Official CAM preview, 1 mm slot cutter/compensation acceptance, color-print appearance and transmission, physical sample, RF/NFC tests, and final release review remain pending. No supplier manufacturing approval is claimed.
