# Core PCB route helper

`12-core-antenna-route.js` is a self-contained EasyEDA API function body. It runs in preview mode (`APPLY = false`) and returns exact line, via and outline coordinates without changing the document. The unit inputs have been corrected to mm before the output conversion to native mil. Layer IDs are explicit 1/2/11 and through-via type is 0 because this bridge runtime does not expose enum globals. **Do not apply the current baseline route:** its returns/vias have physical copper overlaps. `GEOMETRY_REVIEW_APPROVED = false` blocks accidental application. The independently checked replacement is only a proposal in `../electrical/antenna-geometry-review.json`.

The generated core outline is an octagon 37 mm flat-to-flat, centered on U1 at (0,0) mil. The baseline spiral uses 0.25 mm copper width and 0.5 mm centerline pitch; 129 sample points approximate four inward octagonal revolutions. Because of the inward interpolation its actual minimum inter-turn copper gap is 0.24901979 mm, slightly below the 0.25 mm target. Four 0.20 mm drill / 0.45 mm copper vias return the two spiral endpoints under the coil and break out the two center IC pads. The project mechanical source says the core has no permanent mounting holes; the helper therefore creates none.

## Offline geometric audit

Run `python scripts/validate_antenna_geometry.py` from the NFC project root. It evaluates the preview using a standalone Node AsyncFunction with no EDA or bridge connection, then uses Shapely against the actual pad shapes/layers/rotations saved in `eda/core-pads.json`. The report records both input hashes and every calculated violation.

The original direct Bottom returns overlap by 0.00524916 mm. They also overlap the opposite endpoint/breakout vias; the original LB breakout via overlaps CT2 pad 1 (`ANT_LA`) by 0.02815 mm. These are unintended shortcuts bypassing the spiral, not the expected two-terminal inductive continuity, and cannot be accepted as intentional net ties.

`proposal_geometry` in the report contains complete native-mil track/via coordinates. Its centerline pitch is 0.502 mm, giving a mathematical minimum coil gap of 0.25101153 mm. The opposite Bottom returns are separated above/below the parts: minimum mutual copper gap 1.86162427 mm; minimum track-to-unrelated-pad gap 0.26489 mm. All proposed route/via copper is inside the 37 mm outline. The coil end vias move radially outward/inward 0.10 mm with short Top necks; the outer via expands the winding area locally, leaving approximately 1.3 mm copper-to-board clearance at that point.

The proposal has zero collisions under this review's 0.15 mm new-copper clearance and 0.25 mm winding-gap criteria. It is **not a native DRC pass**: the electrical net-tie model, all VOUT/GND/LED routes, solder-mask rules and component courtyards remain to be checked. No bridge calls, native PCB changes or RF measurements were made for this audit.

## Electrical constraint and bridge-copper path

U1 pad 1 is `ANT_LA`, pad 8 is `ANT_LB`, and schematic L1 is the two-terminal PCB spiral. Ordinary track/via APIs accept only one net per primitive, so they cannot describe the spiral as a clean connection between the two nets. However, the official EasyEDA guide documents **bridge copper** for a PCB fill region: the UI can list `ANT_LA` and `ANT_LB` as the only bridged nets; other nets entering that fill should trigger DRC. This preserves the schematic nets and is the preferred implementation for the Top-layer spiral. [Official bridge-copper guide](https://prodocs.lceda.cn/cn/pcb/place-fill-region/)

The bridge-copper field is not exposed by the installed API v1.1.44 `PCB_PrimitiveFill.create(layer, complexPolygon, net, fillMode, lineWidth, primitiveLock)` signature or the reviewed PCB format references. Therefore the proposed spiral fill shape can be generated/imported by API, but the bridge setting must be applied in the native Properties panel (unless a documented API path is later verified), then saved, reopened, rechecked with DRC, and reviewed in Gerber. The bridge fill and its serialized round trip are not yet present or verified. Do not replace this with netless copper or rename the two NFC nets into one.

## API signatures checked in the installed EasyEDA references

- `eda.pcb_PrimitiveLine.create(net, layer, startX, startY, endX, endY, lineWidth, primitiveLock)` creates track and outline segments. The layer is `EPCB_LayerId.TOP`, `BOTTOM`, or `BOARD_OUTLINE` (11); the core source coordinates and widths are mil.
- `eda.pcb_PrimitiveVia.create(net, x, y, holeDiameter, diameter, viaType, designRuleBlindViaName, solderMaskExpansion, primitiveLock)` creates a via. The helper uses `EPCB_PrimitiveViaType.VIA` and a 0.20/0.45 mm drill/diameter.
- `eda.pcb_PrimitivePad.create(layer, padNumber, x, y, rotation, pad, net, hole, holeOffsetX, holeOffsetY, holeRotation, metallization, padType, specialPad, solderMaskAndPasteMaskExpansion, heatWelding, primitiveLock)` creates a pad with a drill. For future NPTH round drills the documented hole tuple is `[EPCB_PrimitivePadHoleType.ROUND, diameter]`, with `metallization=false`; a routed slot uses `[EPCB_PrimitivePadHoleType.SLOT, diameter, length]`. No NPTH drills or slots are specified for this core.
- Board outline and internal routed void paths are closed `BOARD_OUTLINE` polylines/line loops. The API docs do not describe a separate cutout primitive. A closed outline loop is not equivalent to a routed slot with a specific cutter diameter; confirm the CAM representation before assigning tooling.

## Existing pad map (core units: mil)

| Part | Pad and net | Coordinate |
|---|---|---:|
| U1 | 1 ANT_LA | (-23.6, 19.7) |
| U1 | 8 ANT_LB | (0, 23.6) |
| C1 | 1 VOUT / 2 GND | (81.9, 0) / (115, 0) |
| CT1 | 1 ANT_LA / 2 ANT_LB | (-87.4, 98.4) / (-54.3, 98.4) |
| CT2 | 1 ANT_LA / 2 ANT_LB | (-8.7, 98.4) / (24.4, 98.4) |
| R5 | 1 VOUT / 2 SCL | (-128.1, -70.9) / (-68.8, -70.9) |
| R6 | 1 VOUT / 2 SDA | (68.8, -70.9) / (128.1, -70.9) |
| R7 | 1 VOUT / 2 FD | (-29.7, -137.8) / (29.7, -137.8) |
| R1, D1 | R1-1 VOUT, R1-2 LED1_A; D1-1 GND, D1-2 LED1_A | (-167.5,0), (-108.1,0); (-265.5,0), (-206.5,0) |
| R2, D2 | R2-1 VOUT, R2-2 LED2_A; D2-1 GND, D2-2 LED2_A | (108.1,157.5), (167.5,157.5); (206.7,157.5), (265.7,157.5) |
| R3, D3 | same mapping as R1, D1; bottom layer | same coordinates as R1, D1 |
| R4, D4 | same mapping as R2, D2; bottom layer | (108.1,-157.5), (167.5,-157.5); (206.7,-157.5), (265.7,-157.5) |

## Partial routes now present in EasyEDA

On 2026-10-10, `scripts/20-core-nonantenna-routes.js` added and saved 19 copper segments on `PCB1`: SCL, SDA, FD, and the four LED-anode branches. The SDA route intentionally uses a stepped Top-layer path to avoid R6 pad 1 (VOUT) and the FD route. Each track is 8 mil wide. These routes were checked offline against the saved native pad polygons before insertion. The same 19 segments are mirrored to the 100×100 manufacturing PCB at the 50 mm center offset by `scripts/21-panel-import-nonantenna-routes.js`; the panel still lacks power, ground and antenna copper.

The native DRC immediately after this edit reported 22 connection entries and one netlist mismatch. The remaining connection entries are ANT_LA (3), ANT_LB (3), VOUT (10), and GND (6); the LED anode and signal routes are connected. The reported groups contain no separate copper-short or clearance category. This is a partial routing milestone, **not a DRC pass**. VOUT/GND, antenna/tuning connectivity and the missing L1 PCB representation remain open. The DRC log is `../eda/logs/20-core-nonantenna-routes.json`.

The saved native lines were re-read on 2026-10-10 and audited by `scripts/audit_existing_routes.py` against all 19 tracks and the saved native pad polygons. Under a 0.1524 mm (6 mil) different-net clearance screen, no violations were found; the closest track-to-unrelated-pad gap is 0.28269389 mm (FD to U1.5/SDA), and the closest different-net track-to-track gap is 0.40187476 mm (SDA to FD). The audit report is `../electrical/existing-route-audit.json`. This offline geometry check complements, but does not replace, native DRC.

The pad map is extracted from `eda/core-pads.json`; it reflects native PCB pads, not package pin numbers inferred from schematic symbols.
