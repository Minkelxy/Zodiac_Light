# horse + Sagittarius 37mm cover print objects

`front-*.svg` and `rear-*.svg` are exact 37mm × 37mm square SVG print objects. Their clipping path is the existing AF37 octagon; all artwork outside that octagon is transparent. The corresponding PNGs are 1821 × 1821 with 1250 dpi metadata (37.00272mm square by the PNG metadata; set the native image object to exactly 37mm when importing). `cover-review-preview.png` shows the front and rear side by side for visual review.

The warm-gray front cover uses an embedded, unchanged approved single-ink PNG. Rear title text uses outlined Georgia Regular paths to match Sagittarius B's soft serif style; the SVGs contain no live text nodes or font dependency. Sagittarius adapts star-style-study-v1 B, with its fine pale constellation strokes and soft Georgia layout.

Physical holes and slots and a 0.20mm surrounding clear reveal are transparent in the print PNG. They expose the substrate/white soldermask in the native stack; the reveal is not white ink and the openings are not mechanical border artwork. For Sagittarius, the B study's daytime white-soldermask simulation is removed.

Use the SVG as the editable source and import the matching PNG into the native 37mm square color-object layer when image placement is preferred. The PNG remains unmirrored and has transparent outside corners. Verify the native image Y-axis convention during import before final output; the source geometry/artwork itself remains in the documented exterior view. See `manifest.json` for source and generated SHA256 hashes, exact clip coordinates, dimensions, alpha checks and Georgia outline validation. This is a print-object candidate, not a manufacturing or physical color qualification.
