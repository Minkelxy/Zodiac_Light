# Mechanical geometry

All coordinates are millimetres, panel origin top left and Y increasing downward.

`design.json` is the EDA import source; `validation.json` contains Shapely checks.
For the manufacturing panel, use its single `panel.outer_ring`, enclosed
`panel.route_cutouts`, board internal apertures and all NPTH drills. Outer routes
touching the sheet edges are already stitched into that true exterior. Its
bounding box is still 100×100mm. `panel.nominal_outer_ring` is a size reference
only; `all_routing_regions` is a CAM reference and must not be reimported as
cutouts because some regions touch the exterior. The five closed
`boards[].outer_ring` polygons are depanelled references only.

Every subboard has four 5mm connecting tabs with five Ø0.6mm NPTH holes per tab
on 0.95mm pitch (0.35mm nominal hole-edge spacing). The outer routing band is 2mm wide. Top and bottom rails retain
3mm material. The design has 5 subboards and 4 distinct designs (the spacer is
repeated). External profile routing needs 2mm tooling; the 11 separate constellation
slots require a 1mm cutter. Verify this distinction in supplier CAM review.

The horse cover has no designed aperture or image geometry yet; the user will
manually import the gray-base/purple-horse reference art in EasyEDA. Sagittarius
has 8 Ø0.8mm NPTH and 11 routed capsules. All optical-aperture material webs are
checked against 1mm. Each slot endpoint is optimized independently with a 1.03mm nominal web target.
The shortest slot is about 1.489mm end to end;
its short straight section still requires supplier CAM review. Printed links
on retained material complete the visible constellation between apertures.
The spacer window is 30mm across flats, with R1mm internal corners for a
2mm router. Its nominal octagon is provided as a separate reference.

`*-mechanical.svg` subboard files use local centres (0,0); `panel-mechanical.svg`
shows actual panel material after every cut and NPTH, while `panel-review.svg`
adds labels, subboard edge references and green tab overlays.

Both cover designs are defined as viewed from their exterior. The back-cover
holes are mirrored only in an inner-face visualization, never in manufacturing.
The selected color-print route uses white solder mask and ENIG; verify supplier
panel/SMT constraints and color-art alignment before ordering.

Regenerate: `python hardware/nfc-talisman/scripts/build_mechanical.py`.
Shapely 2.x is required. No application, EDA window, or existing project is mutated.
