# Snake + Leo second variant candidate

This directory contains an isolated review candidate for the reverse face of the shared NFC talisman core. Existing project geometry, source art, PNGs, native project files and manufacturing snapshots are not changed.

## Files

- `leo-geometry.json` — independent Leo physical candidate in board-local millimetres.
- `leo-geometry.svg` — AF37 perimeter reference, nine Ø0.8mm star holes and eight independent 1.0mm rounded slots.
- `leo-artwork.svg` / `leo-artwork-preview.png` — dark ground, pale full Leo lines, vector `LEO` and the existing vector `AD ASTRA` lettering. This is a review image, not released color-print data.
- `leo-geometry-preview.png` — rendered cut geometry review.
- `snake-leo-two-face-preview.png` — side-by-side front/rear appearance preview; the snake PNG is composited from the existing source file without copying or changing it.
- `validation.json` — dimensions, mechanical clearances and source hashes.
- `build_snake_leo_variant.py` — geometry and SVG builder; PNG rasterization uses the configured Sharp runtime.

## Leo graph and geometry

The archived Stellarium Modern `CON modern Leo` chart is used as a mainstream simple line figure. Its complete nine HIP stars and ten edges are retained in artwork, including the familiar sickle/head and connected body loop. The chart coordinates are uniformly scaled to a 27.5mm-wide envelope and centered on the board; no star or edge is hand-selected.

The existing 37mm AF octagon and 30mm AF optical window remain the shared mechanical envelope. Each Leo star is a separate Ø0.8mm hole. Eight source edges become independent 1.0mm rounded slots. HIP 48455–47908 and HIP 50583–50335 remain continuous pale printed relationships in the artwork, but are omitted from physical apertures: their 2.55mm and 3.36mm star separations cannot accommodate a 1mm slot and a 1.03mm web at both holes. Keeping them as printed lines retains the mainstream figure while protecting the requested minimum material. Shared-star endpoint setbacks on the eight cut edges are calculated from their narrowest incident angle; see `leo-geometry.json`. All cutouts are checked against AF37 and the rounded AF30 optical window.

Source chart data is from the local reference snapshot attributed to Stellarium Modern (CC BY-SA 4.0); its coordinates are tied to HIP identifiers and the local Hipparcos I/239 table (Credit: ESA, CC BY-NC 3.0 IGO). Check both licenses for redistribution or commercial use. IAU materials explain that constellations are areas and their stick figures do not have one universally mandated line topology.

## Visual and integration notes

The generated two-face preview uses a warm neutral gray base behind the existing green single-ink snake image. It shows appearance only; the real substrate color and ink opacity need a physical sample. For a first manual import, place the 37mm `leo-artwork.svg` as the rear-side color illustration, then use `leo-geometry.svg` as a geometry review reference and map its circles/slots into the shared stack design. Keep the snake original as the front-side art. Verify rear-face orientation after importing: the current geometry coordinates follow the local Leo chart's screen view; any through-stack optical projection may require a horizontal reflection.

The geometry candidate is not yet integrated into the five-up 100x100 panel, does not model the common core/LED/NFC details, and is not manufacturing release data.

