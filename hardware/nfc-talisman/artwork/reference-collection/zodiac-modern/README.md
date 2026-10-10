# Zodiac constellation reference charts

This folder contains the twelve Stellarium **Modern** zodiac line figures as
dark preview PNG/SVG files and transparent import SVGs. Each chart uses the
source `CON modern <code>` line arrays verbatim: every adjacent HIP pair is one
edge, with no hand-picked additions or removals. The supplied alternative
Sagittarius PCB “teapot” chart is listed separately and does not replace the
complete Stellarium Sagittarius figure.

The 1024 × 1024 charts use a gnomonic projection centered on the spherical
mean of each constellation's listed stars. Celestial east points left, north
points up, and the chart uses equal scale in both directions. HIP star
positions, V magnitudes, projected coordinates, source edge pairs, file paths,
and source SHA-256 values are in `manifest.json`.

`<code>/<code>-modern-dark.png` is the dark preview. `*-modern-dark.svg` is its
editable vector source. `*-modern-import.svg` is a transparent, title-free
line-art SVG for import; `*-modern-import-titled.svg` is the same geometry with
an ASCII English title. The import art contains only the star dots and straight
segments.

Sources and attribution:

- Stellarium team, Modern sky culture, zodiac `CON modern` entries. The source
  index snapshot is at `data/sources/20261008T150844925832Z/stellarium_modern_index.json`.
  Its sky-culture text and data are marked **CC BY-SA 4.0**. Source project:
  <https://github.com/Stellarium/stellarium/tree/master/skycultures/modern>.
- Star positions and magnitudes: CDS VizieR `I/239/hip_main`, fields
  `HIP, RAICRS, DEICRS, Vmag`. The unmodified query response used here is
  `../source-zodiac/hipparcos-zodiac.tsv`. ESA 1997, *The Hipparcos and Tycho
  Catalogues*, ESA SP-1200, bibcode `1997HIP...C......0E`. The catalogue is
  distributed under **CC BY-NC 3.0 IGO** and requires **Credit: ESA**; see
  <https://www.cosmos.esa.int/web/hipparcos/catalogues>.

These assets are retained for local reference. The two source licences have
different terms; this project does not infer permission for commercial use.
Check the original source terms before redistribution or commercial use.

Regenerate offline with:

```powershell
python hardware/nfc-talisman/scripts/build_zodiac_reference_collection.py
```
