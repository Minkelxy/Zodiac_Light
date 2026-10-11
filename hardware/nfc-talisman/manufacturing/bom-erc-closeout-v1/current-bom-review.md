# BOM review — NFC constellation talisman

**Checked:** 2026-10-10 (LCSC product-page stock snapshots; inventory may change). **Default assembly:** four LEDs, 14 fitted components. **Alternate assembly:** two LEDs, 12 fitted components.

## BOM disposition

The EasyEDA native data and the draft variants agree on a 14-piece four-LED build and a 12-piece two-LED build. Both configurations fit U1, C1, CT1, R1–R4, and R5–R7. The two-LED variant leaves D2 and D4 unpopulated; R2 and R4 remain fitted. L1 is the printed PCB antenna and TP1/TP2 are test pads, so they are not purchasable BOM items.

The key source conflict is CT2: `electrical/BOM.csv` marks it DNP with no selected MPN, and `assembly-variants.json` excludes it for both builds; however, `nfc-talisman-panel-bom-all.csv` exports a library placeholder as a 47pF YAGEO C60137 purchase line. Exclude CT2 entirely from procurement. Do not treat the panel-wide all-parts export as the assembly BOM.

The specified 47pF part is valid for CT1: YAGEO CC0402JRNPO9BN470 / LCSC C60137 is 0402, 47pF, C0G/NP0, 50V, ±5%. It is only the initial antenna tuning value; do not assume 47pF is the final tuned value. CT2 must stay DNP until the complete antenna/assembly stack is measured and tuning is approved.

C1's specified MPN/LCSC pairing is internally consistent: Murata GRM155R71C154KA12D / C162182, 150nF, 16V, X7R, ±10%, 0402. The native EasyEDA component metadata flags this MPN as NRND. A same-electrical-spec candidate is listed for evaluation: CCTC TCC0402X7R154K160AT / LCSC C7393865 (0402, 150nF, 16V, X7R, ±10%). It is **not fit-cleared or native-synchronized**. The CCTC primary approval specification DRAAW108K/1-2022 p.16 gives the ≥100 nF 0402*2 maximum body envelope as 1.20 × 0.70 × 0.70 mm (including 0.70 mm max height), versus 0.55 mm max height for the specified Murata. Its p.34 reflow land diagram recommends A=0.35–0.45 mm and B=0.40–0.50 mm; the actual native C1 land measures approximately A=0.3404 mm and B=0.5004 mm. The geometric overlap is positive, but this does not establish process compatibility or cover clearance. Keep CCTC at Qty 0 / HOLD; the Murata native line remains unchanged. See [C1 对照](c1-alternative-comparison.md) before any future switch.

## Assembly quantities

| Item | Four LED | Two LED | Notes |
|---|---:|---:|---|
| U1, C1, CT1 | 3 | 3 | C1 currently has sourcing hold; use alternate only after source synchronization. |
| R5–R7 | 3 | 3 | R5=SCL pull-up, R6=SDA pull-up, R7=FD pull-up; all 47kΩ ±1%. |
| R1–R4 | 4 | 4 | Each 2.2kΩ ±1%; R2 and R4 stay fitted in two-LED build. |
| D1, D3 | 2 | 2 | Baseline LEDs. |
| D2, D4 | 2 | 0 | Optional LEDs, DNP in two-LED build. |
| **Total fitted** | **14** | **12** | The alternate C1 row is Qty 0 and excluded from the totals. |

## Procurement and source checks

LCSC stock values are page snapshots, not a stock guarantee. The product pages also show minimum sales quantities; these can exceed this board's per-build demand. The listed LCSC part number, MPN, and key characteristics were checked against each LCSC product page on 2026-10-10. C1 NRND comes from the native EasyEDA component metadata; its LCSC page confirms the part identity/specification but does not display an in-stock count in the captured listing.

| Designator(s) | Selected source part | Checked LCSC listing | Snapshot and order constraint |
|---|---|---|---|
| U1 | NXP NT3H2111W0FHKH / C710403 | [LCSC C710403](https://www.lcsc.com/product-detail/C710403.html) | 49,730 in stock; minimum 1. |
| C1 specified | Murata GRM155R71C154KA12D / C162182 | [LCSC C162182](https://www.lcsc.com/pl/product-detail/Multilayer-Ceramic-Capacitors-MLCC-SMD-SMT_Murata-Electronics_C162182.html) | Native library metadata marks MPN NRND. No live stock count captured. |
| C1 candidate under evaluation (Qty 0 / HOLD; not a direct substitute) | CCTC TCC0402X7R154K160AT / C7393865 | [LCSC C7393865](https://www.lcsc.com/product-detail/C7393865.html), [CCTC datasheet](https://www.lcsc.com/datasheet/C7393865.pdf) | 243,600 in stock; minimum 50. Same nominal electrical specification; physical fit and assembly-process compatibility are not established. Do not replace C1 directly; see closeout fit review. |
| CT1 | YAGEO CC0402JRNPO9BN470 / C60137 | [LCSC C60137](https://www.lcsc.com/product-detail/C60137.html) | 3,898,100 in stock; minimum 100. 47pF C0G/NP0, 50V, ±5%. |
| R5–R7 | YAGEO RC0603FR-0747KL / C105579 | [LCSC C105579](https://www.lcsc.com/product-detail/C105579.html) | 210,900 in stock; minimum 100. 47kΩ ±1%, 0603. |
| R1–R4 | YAGEO RC0603FR-072K2L / C114662 | [LCSC C114662](https://www.lcsc.com/product-detail/C114662.html) | 2,691,300 in stock; minimum 100. 2.2kΩ ±1%, 0603. |
| D1–D4 | Kingbright APG1608SYKC/T / C5875720 | [LCSC C5875720](https://www.lcsc.com/product-detail/C5875720.html) | 200 in stock; minimum 5. 0603 metric LED, yellow 590nm. |

The source files do not provide enough evidence to claim an original-manufacturer lifecycle status for every part. No LCSC page reviewed here marked U1, LED, resistor, or CT1 NRND; their current LCSC listings were in stock. Confirm stock and lifecycle again before placing an order.

## Release blockers and assembly notes

- Resolve C1 sourcing: the CCTC same-electrical-spec row remains Qty 0 / HOLD. Before adopting it, close the 0.70 mm max-height cover-clearance check and review the actual 0.3404 mm pad gap / 0.5004 mm pad length against CCTC reflow guidance and assembly process. No native synchronization has occurred; do not order the candidate as the fitted line.
- Keep CT2 out of the purchase BOM. Its placeholder must not be converted into a fixed 47pF selection.
- Maintain the per-LED 2.2kΩ resistors. Never replace R1–R4 with shorts or a single shared resistor.
- Confirm APG1608SYKC/T pad polarity against the actual footprint/library and placement rotation before assembly. Native variant notes already call out polarity/rotation for physical review.
- This is a prepared, reviewable BOM, not an order record. No order was placed.
