# C1 alternate candidate — fit and sourcing review

**Disposition: HOLD.** No native EasyEDA changes were made. C1 remains Murata GRM155R71C154KA12D / C162182 in the schematic, core PCB and panel PCB. CCTC TCC0402X7R154K160AT / C7393865 is retained only as a Qty 0 candidate. It is electrically same nominal specification in the available product records, but “same 0402” does not establish board fit. Do not use it as an assembly substitute yet.

## Primary component and land data

| Measure | Murata GRM155R71C154KA12D (selected native) | CCTC TCC0402X7R154K160AT (candidate) |
|---|---:|---:|
| Nominal | 150 nF, 16 V, X7R, ±10% | 150 nF, 16 V, X7R, ±10% |
| Body dimensions | 1.0 × 0.5 mm nominal; max thickness 0.55 mm per Murata GRM series datasheet | **0402*2, for capacitance ≥100 nF:** L 0.95–1.20 mm, W 0.45–0.70 mm, T 0.45–0.70 mm; maximum envelope **1.20 × 0.70 × 0.70 mm** |
| Termination | Use Murata drawing for original component | CCTC dimension `e` = 0.15–0.30 mm (p.16) |
| Manufacturer recommended reflow land (0402) | See Murata series land guidance | p.34: A=0.35–0.45, B=0.40–0.50, C=0.45–0.55 mm |

Primary CCTC source: “Specification for Approval”, document DRAAW108K/1-2022, [PDF](https://atta.szlcsc.com/upload/public/pdf/source/20230606/1C21CCC6A1C08E8C3D36DB4723A2CB7D.pdf), p.16 (0402*2 row and note `*2` for 100 nF and above) and p.34 (reflow land table and diagram). Murata primary source: [GRM155R71C154KA12 datasheet](https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM155R71C154KA12-01A.pdf); project copy at `sources/electrical/Murata_GRM155R71C154KA12.pdf`.

The CCTC library footprint is also different from the current land: library pads are approximately 0.600 × 0.600 mm with centers 1.000 mm apart; the original Murata library pads are approximately 0.500 × 0.540 mm with centers 0.841 mm apart. These are library recommendations, not actual board measurements. The actual native C1 land must be evaluated separately below.

## Actual live land geometry and geometric overlap

Read-only EasyEDA API inspection of the current saved core and panel confirms the same C1 land geometry in each: two rectangular pads approximately 19.7 × 21.3 mil (0.5004 × 0.5410 mm), center spacing 33.1 mil (0.8407 mm), hence inner gap 13.4 mil (0.3404 mm). In the CCTC p.34 diagram, A labels the inner pad-to-pad gap, B labels each pad length along the component axis, and C labels pad width. Compared with CCTC reflow recommendations, the measured values are: A=0.3404 mm, 0.0096 mm below the 0.35 mm lower bound; B=0.5004 mm, 0.0004 mm above the 0.50 mm upper bound (measurement rounded to 0.1 mil); C=0.5410 mm, within 0.45–0.55 mm. This is close to the recommended pattern, but not a strict pass on A/B.

Pads are centered at ±0.42035 mm; each extends from about 0.1702 to 0.6705 mm from center on its side. Using the CCTC datasheet envelope L=0.95–1.20 mm and e=0.15–0.30 mm, the simple axial interval intersection between each end termination and pad is about 0.15–0.30 mm (positive overlap over the stated ranges). This is a geometric overlap calculation only: it does not establish solder-joint quality, paste/reflow robustness, board-level reliability, or mechanical clearance. The datasheet gives component width up to 0.70 mm while actual pad width is 0.541 mm; the lead geometry across width and process acceptance still need review.

The increased maximum body height is material: CCTC allows 0.70 mm versus the selected Murata's 0.55 mm maximum (increase 0.15 mm). The available record does not establish clearance to the assembled cover/adhesive or allow us to claim the candidate is cleared for the stack.

## Decision and closure evidence still needed

1. Keep native C1, native land, BOM, and placement unchanged. Candidate stays Qty 0 / HOLD.
2. Obtain mechanical confirmation that a 0.70 mm capacitor body plus solder/placement tolerance clears the actual cover, spacer, and adhesive stack.
3. Have assembly/process owner review the 0.3404 mm gap and 0.5004 mm pad length against the CCTC recommended land ranges and intended stencil/reflow process. If accepted, record the process basis; the datasheet itself does not define a board-specific acceptance criterion.
4. Only after those checks may the native part procurement attributes and variant BOM be synchronized. That later change must preserve footprint geometry and then be saved, reopened, and checked with fresh ERC/DRC and fresh native exports.

