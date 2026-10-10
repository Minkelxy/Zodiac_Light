# Core PCB route helper

This note records the current live routing state and the history of `12-core-antenna-route.js`. The earlier preview/proposal and 19-line offline clearance audit are historical snapshots; they are not the current route or a current whole-board audit. Do not use their counts or margins to describe the finished routing.

Historical helper geometry: the generated core outline was an octagon 37 mm flat-to-flat, centered on U1 at (0,0) mil. The baseline spiral used 0.25 mm copper width and 0.5 mm centerline pitch; 129 sample points approximated four inward octagonal revolutions. Its calculated minimum inter-turn copper gap was 0.24901979 mm, slightly below the 0.25 mm target. The earlier helper used four 0.20 mm drill / 0.45 mm copper vias. Those preview values are not the final live geometry; the current 10 vias are 0.30/0.55 mm. The project mechanical source has no permanent core mounting holes.

## Offline geometric audit

Run `python scripts/validate_antenna_geometry.py` from the NFC project root. It evaluates the preview using a standalone Node AsyncFunction with no EDA or bridge connection, then uses Shapely against the actual pad shapes/layers/rotations saved in `eda/core-pads.json`. The report records both input hashes and every calculated violation.

The original direct Bottom returns overlap by 0.00524916 mm. They also overlap the opposite endpoint/breakout vias; the original LB breakout via overlaps CT2 pad 1 (`ANT_LA`) by 0.02815 mm. These are unintended shortcuts bypassing the spiral, not the expected two-terminal inductive continuity, and cannot be accepted as intentional net ties.

`proposal_geometry` in the report contains complete native-mil track/via coordinates. Its centerline pitch is 0.502 mm, giving a mathematical minimum coil gap of 0.25101153 mm. The opposite Bottom returns are separated above/below the parts: minimum mutual copper gap 1.86162427 mm; minimum track-to-unrelated-pad gap 0.26489 mm. All proposed route/via copper is inside the 37 mm outline. The coil end vias move radially outward/inward 0.10 mm with short Top necks; the outer via expands the winding area locally, leaving approximately 1.3 mm copper-to-board clearance at that point.

The live project was subsequently routed and completed; do not assume the historical preview/proposal geometry above is identical to the live copper. Core and panel were saved, closed, reopened, and both native DRC runs returned empty arrays. Current geometry is 126 track lines, 10 vias and 1 fill on each board; core has 15 components/38 pads, panel 15 components/146 pads/88 polylines. This native DRC result does not include RF tuning or physical acceptance.

## Electrical constraint and bridge-copper path

U1 pad 1 is `ANT_LA`, pad 8 is `ANT_LB`, and schematic L1 is the two-terminal PCB spiral. Ordinary track/via APIs accept only one net per primitive, so they cannot describe the spiral as a clean connection between the two nets. However, the official EasyEDA guide documents **bridge copper** for a PCB fill region: the UI can list `ANT_LA` and `ANT_LB` as the only bridged nets; other nets entering that fill should trigger DRC. This preserves the schematic nets and is the preferred implementation for the Top-layer spiral. [Official bridge-copper guide](https://prodocs.lceda.cn/cn/pcb/place-fill-region/)

The bridge-copper field is not exposed by the installed API v1.1.44 `PCB_PrimitiveFill.create(layer, complexPolygon, net, fillMode, lineWidth, primitiveLock)` signature. The coil fill was imported, then configured in the native Properties panel. After save/reopen, the native fields read `isBridgingCopper=true` and `networkList=['ANT_LA','ANT_LB']`. Keep this native setting when revising or regenerating the fill; do not replace it with netless copper or merge the two NFC nets.

## API signatures checked in the installed EasyEDA references

- `eda.pcb_PrimitiveLine.create(net, layer, startX, startY, endX, endY, lineWidth, primitiveLock)` creates track and outline segments. The layer is `EPCB_LayerId.TOP`, `BOTTOM`, or `BOARD_OUTLINE` (11); the core source coordinates and widths are mil.
- `eda.pcb_PrimitiveVia.create(net, x, y, holeDiameter, diameter, viaType, designRuleBlindViaName, solderMaskExpansion, primitiveLock)` creates a via. The current 10 through vias use 0.30/0.55 mm drill/diameter and passed native checks on both core and panel.
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

The earlier signal/LED route pass is recorded in `scripts/20-core-nonantenna-routes.js`; its 19-line snapshot was later superseded. The panel import script `scripts/21-panel-import-nonantenna-routes.js` uses a +50 mm coordinate translation to place corresponding copper at the panel center. This is a translation, not a mirror operation. Later routing completed the power, ground and antenna paths and added the coil fill and ten vias.

Current native result after save/close/reopen: both core and panel DRC arrays are empty; both contain 126 lines, 10 vias and 1 fill. The core is 15 components/38 pads; the panel is 15 components/146 pads/88 polylines. TP1 (VOUT) and TP2 (GND) are Top free pads at core-relative (80,115) and (235,115) mil, each with 0.8 mm copper and 0.9 mm mask, no hole or paste opening, and excluded from BOM/PnP; panel copies use +50 mm X/Y translation. The 10 through vias are 0.30 mm drill / 0.55 mm copper diameter. The native coil fill retains bridge fields `isBridgingCopper=true` and `networkList=['ANT_LA','ANT_LB']`. Current native-copper audit reports 11 nets passing, minimum foreign-net copper clearance 0.18669 mm and 0.20199 mm from a via to the adjacent coil turn. Core and panel copper geometry matches after a +50 mm coordinate translation, not mirroring. The previously recorded offline audit and its clearance distances cover only the former 19 tracks and must not be applied to the completed route.

The panel's original 22 `BOARD_OUTLINE`/GKO polylines were found not to be explicitly closed, which left a fabrication gap in the exported panel outline. The panel import generator and live panel geometry were corrected; after save/close/reopen, the panel DRC remains empty. Read-only CAM precheck now confirms 22/22 explicitly closed GKO paths and copper consistency; formal cutter compensation, slot machining and process review remain pending. The two PTH drill exports repeat the same 10 hits, so CAM must select one only.

Still open: tune the 47 pF starting capacitor against the bare board and complete stack; measure NFC, VOUT and LEDs; complete phone read/write trials; manually import horse artwork; verify optical path; and finish CAM review. The 3 mm rails and narrow star/slot webs need process review. The generated manufacturing package remains a draft.

The pad map is extracted from `eda/core-pads.json`; it reflects native PCB pads, not package pin numbers inferred from schematic symbols.
