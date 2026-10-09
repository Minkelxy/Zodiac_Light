#!/usr/bin/env python3
"""Generate and validate the NFC talisman's panel geometry, all dimensions in mm.

The manufacturing panel has ONE 100 x 100 exterior and routed voids.  The five
closed octagons are depanelled references; importing them as five additional
panel board outlines would turn attached boards into unintended islands.
Requires Shapely 2.x; no project dependencies are changed by this script.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "geometry"
HALF = 18.5
STAR_RADIUS = 0.4
SLOT_RADIUS = 0.5
WEB = 1.0
ROUTE_WIDTH = 2.0
TAB_WIDTH = 5.0
MOUSEBITE_COUNT = 5
MOUSEBITE_DIAMETER = 0.6
MOUSEBITE_PITCH = 0.95
HIP_IDS = (88635, 89931, 90185, 93506, 90496, 92041, 92855, 93864)
STAR_NAMES = {88635: "gamma2", 89931: "delta", 90185: "epsilon", 93506: "zeta",
              90496: "lambda", 92041: "phi", 92855: "sigma", 93864: "tau"}
BOARD_SPECS = (("horse", 1, (20.5, 23.5)), ("spacer2", 2, (79.5, 23.5)),
               ("core", 3, (50.0, 50.0)), ("spacer4", 4, (20.5, 76.5)),
               ("sagittarius5", 5, (79.5, 76.5)))


def octagon(across_flats: float, center=(0.0, 0.0)) -> Polygon:
    h = across_flats / 2
    b = h * math.tan(math.pi / 8)
    cx, cy = center
    return Polygon([(cx - b, cy - h), (cx + b, cy - h),
                    (cx + h, cy - b), (cx + h, cy + b),
                    (cx + b, cy + h), (cx - b, cy + h),
                    (cx - h, cy + b), (cx - h, cy - b)])


def ring(coords):
    """Return an implicitly closed, rounded ring without duplicate end point."""
    pts = list(coords)
    if pts[0] == pts[-1]:
        pts.pop()
    return [[round(x, 6), round(y, 6)] for x, y in pts]


def polygons(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for p in g.geoms if p.geom_type == "Polygon"]


def encode_polygons(g):
    return [{"exterior": ring(p.exterior.coords),
             "holes": [ring(i.coords) for i in p.interiors]} for p in polygons(g)]


def path_of(g):
    result = []
    for p in polygons(g):
        for r in [p.exterior, *p.interiors]:
            pts = ring(r.coords)
            result.append("M" + " L".join(f"{x:.6f},{y:.6f}" for x, y in pts) + " Z")
    return " ".join(result)


def svg_document(bounds, body, title):
    x0, y0, x1, y1 = bounds
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{x1-x0}mm" '
            f'height="{y1-y0}mm" viewBox="{x0} {y0} {x1-x0} {y1-y0}">\n'
            f'<title>{escape(title)}</title>\n{body}\n</svg>\n')


def raster_preview(out, panel_material, board_shapes, boards, tabs, drills):
    """Render native geometry as a local review aid without editing any image."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    img = Image.new("RGB", (1200, 1200), "#f4f1ec")
    draw = ImageDraw.Draw(img)
    scale, margin = 11.52, 24
    def px(coords):
        return [(x*scale+margin, y*scale+margin) for x, y in coords]
    def draw_geometry(g, fill):
        for p in polygons(g):
            draw.polygon(px(p.exterior.coords), fill=fill)
            for hole in p.interiors:
                draw.polygon(px(hole.coords), fill="#f4f1ec")
    draw_geometry(panel_material, "#28252b")
    for b in boards:
        draw_geometry(board_shapes[b["id"]]["material"], "#49434f")
        draw.line(px(board_shapes[b["id"]]["outer"].exterior.coords), fill="#ffa83f", width=2)
    for t in tabs:
        draw_geometry(t["shape"].intersection(box(0, 0, 100, 100)), "#69b888")
    for d in drills:
        x, y = px([d["center"]])[0]
        r = .25*scale
        draw.ellipse((x-r, y-r, x+r, y+r), fill="#f4f1ec")
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for b in boards:
        x, y = b["center"]
        if b["id"] == "sagittarius5":
            y += 12
        elif b["id"].startswith("spacer"):
            y += 16.75
        draw.text(px([(x, y)])[0], f'{b["layer_index"]} {b["id"]}', anchor="mm", font=font, fill="#eee")
    img.save(out / "panel-review.png")


def local_constellation(source):
    selected = {s["id"]: s for s in source["stars"] if s["hip"] in HIP_IDS}
    assert len(selected) == 8
    edges = [e for e in source["edges"] if e["start"] in selected and e["end"] in selected]
    assert len(edges) == 11
    xs = [s["reference_px"][0] for s in selected.values()]
    ys = [s["reference_px"][1] for s in selected.values()]
    mid = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    scale = 27.5 / (max(xs) - min(xs))
    positions = {k: tuple((s["reference_px"][i] - mid[i]) * scale for i in (0, 1))
                 for k, s in selected.items()}
    neighbors = {k: [] for k in selected}
    for e in edges:
        neighbors[e["start"]].append(e["end"])
        neighbors[e["end"]].append(e["start"])
    setbacks, angles = {}, {}
    for key, ns in neighbors.items():
        p = positions[key]
        theta = []
        for n1, n2 in itertools.combinations(ns, 2):
            u = (positions[n1][0]-p[0], positions[n1][1]-p[1])
            v = (positions[n2][0]-p[0], positions[n2][1]-p[1])
            cosine = sum(u[i]*v[i] for i in (0, 1)) / (math.hypot(*u)*math.hypot(*v))
            theta.append(math.acos(max(-1, min(1, cosine))))
        # Capsule-to-hole: t >= hole R + slot R + desired material.
        # Incident capsules: 2*t*sin(theta/2) - 2*slot R >= material.
        setbacks[key] = max(STAR_RADIUS + SLOT_RADIUS + WEB,
                            max(((2*SLOT_RADIUS+WEB)/(2*math.sin(t/2)) for t in theta),
                                default=0))
        angles[key] = [math.degrees(t) for t in theta]
    slots = []
    for e in edges:
        a, b = positions[e["start"]], positions[e["end"]]
        length = math.dist(a, b)
        u = ((b[0]-a[0])/length, (b[1]-a[1])/length)
        p = tuple(a[i] + u[i]*setbacks[e["start"]] for i in (0, 1))
        q = tuple(b[i] - u[i]*setbacks[e["end"]] for i in (0, 1))
        assert length > setbacks[e["start"]] + setbacks[e["end"]]
        capsule = LineString([p, q]).buffer(SLOT_RADIUS, quad_segs=32)
        slots.append({"id": e["id"], "start": e["start"], "end": e["end"],
                      "endpoint_a": p, "endpoint_b": q, "shape": capsule,
                      "centerline_length_mm": math.dist(p, q),
                      "overall_length_mm": math.dist(p, q) + 2*SLOT_RADIUS})
    stars = [{"id": k, "hip": s["hip"], "name": STAR_NAMES[s["hip"]],
              "center": positions[k], "diameter_mm": 0.8,
              "endpoint_setback_mm": setbacks[k], "incident_angles_deg": angles[k]}
             for k, s in selected.items()]
    return stars, slots, scale


def build(out: Path):
    source = json.loads((ROOT / "data" / "constellation.json").read_text(encoding="utf-8"))
    stars, slots, scale = local_constellation(source)
    from shapely.affinity import translate
    boards, board_shapes, tabs, drills = [], {}, [], []
    for board_id, layer, center in BOARD_SPECS:
        outer = octagon(37, center)
        cutouts, board_drills = [], []
        if board_id.startswith("spacer"):
            nominal_inner = octagon(30, center)
            # A 2mm router cannot make perfectly sharp internal octagon corners.
            # Round the eight convex window corners to R1 while retaining exactly
            # 30mm between opposing flat faces and >=3.5mm peripheral material.
            inner = nominal_inner.buffer(-1, join_style=2).buffer(1, quad_segs=32)
            cutouts.append({"id": "inner_window", "type": "routed_window",
                            "ring": ring(inner.exterior.coords), "tool_diameter_mm": 2.0,
                            "corner_radius_mm": 1.0,
                            "nominal_ring": ring(nominal_inner.exterior.coords)})
        if board_id == "sagittarius5":
            for s in slots:
                shape = translate(s["shape"], *center)
                cutouts.append({"id": s["id"], "type": "constellation_slot",
                                "ring": ring(shape.exterior.coords), "width_mm": 1.0,
                                "tool_diameter_mm": 1.0,
                                "centerline": [[round(s[p][0]+center[0], 6), round(s[p][1]+center[1], 6)]
                                               for p in ("endpoint_a", "endpoint_b")],
                                "overall_length_mm": s["overall_length_mm"]})
            for s in stars:
                board_drills.append({"id": s["id"], "type": "npth_star", "diameter_mm": 0.8,
                                     "center": [round(s["center"][0]+center[0], 6),
                                                round(s["center"][1]+center[1], 6)]})
        shapes = [Polygon(c["ring"]) for c in cutouts]
        shapes += [Point(d["center"]).buffer(d["diameter_mm"]/2, quad_segs=32) for d in board_drills]
        material = outer.difference(unary_union(shapes))
        board_shapes[board_id] = {"outer": outer, "material": material, "voids": shapes}
        # Four robust tabs at the middles of axis-aligned octagon faces.
        # Each 5mm tab bridges the 2mm routing gap, with 0.3mm overlap for union.
        cx, cy = center
        for side, tangent, normal in (("top", (1, 0), (0, -1)), ("right", (0, 1), (1, 0)),
                                      ("bottom", (1, 0), (0, 1)), ("left", (0, 1), (-1, 0))):
            edge = (cx+normal[0]*HALF, cy+normal[1]*HALF)
            pts = []
            for width, depth in ((-TAB_WIDTH/2, -.3), (TAB_WIDTH/2, -.3),
                                 (TAB_WIDTH/2, ROUTE_WIDTH+.3), (-TAB_WIDTH/2, ROUTE_WIDTH+.3)):
                pts.append((edge[0]+tangent[0]*width+normal[0]*depth,
                            edge[1]+tangent[1]*width+normal[1]*depth))
            tabs.append({"id": f"{board_id}_{side}", "board_id": board_id, "side": side,
                         "shape": Polygon(pts), "edge_center": edge,
                         "nominal_width_mm": TAB_WIDTH})
            for i in range(MOUSEBITE_COUNT):
                offset = (i-(MOUSEBITE_COUNT-1)/2)*MOUSEBITE_PITCH
                d = {"id": f"{board_id}_{side}_mb{i+1}", "board_id": board_id,
                     "type": "npth_mousebite", "diameter_mm": MOUSEBITE_DIAMETER,
                     "center": [round(edge[0]+tangent[0]*offset, 6),
                                round(edge[1]+tangent[1]*offset, 6)]}
                drills.append(d)
        boards.append({"id": board_id, "layer_index": layer, "center": list(center),
                       "thickness_mm": 1.0, "outer_ring": ring(outer.exterior.coords),
                       "local_outer_ring": ring(octagon(37).exterior.coords),
                       "cutouts": cutouts, "drills": board_drills,
                       "material_rings": encode_polygons(material),
                       "orientation": "viewed_from_assembly_outside_y_down"})
    panel = box(0, 0, 100, 100)
    route_union = unary_union([v["outer"].buffer(ROUTE_WIDTH, quad_segs=32).difference(v["outer"])
                               for v in board_shapes.values()])
    tab_union = unary_union([t["shape"] for t in tabs])
    routes = route_union.difference(tab_union).intersection(panel)
    board_internal_voids = unary_union([c for b in board_shapes.values() for c in b["voids"]])
    postal_voids = unary_union([Point(d["center"]).buffer(MOUSEBITE_DIAMETER/2, quad_segs=32)
                                for d in drills])
    routed_panel = panel.difference(routes)
    assert routed_panel.geom_type == "Polygon"
    # Exterior-touching routes must be stitched into the single panel outline.
    # Only wholly internal routes are imported as additional closed cutouts.
    enclosed_routes = [Polygon(i.coords) for i in routed_panel.interiors]
    material = routed_panel.difference(unary_union([board_internal_voids, postal_voids]))
    waste = panel.difference(unary_union([v["outer"] for v in board_shapes.values()])).difference(routes)
    design = {
        "schema_version": 1, "units": "mm", "coordinate_system": "panel_top_left_x_right_y_down",
        "parameters": {"panel_size_mm": [100, 100], "across_flats_mm": 37,
                       "board_thickness_mm": 1, "spacer_window_across_flats_mm": 30,
                       "spacer_window_corner_radius_mm": 1,
                       "outer_route_width_mm": 2, "rail_width_mm": 3,
                       "tab_width_mm": TAB_WIDTH, "mousebite_diameter_mm": MOUSEBITE_DIAMETER,
                       "mousebite_pitch_mm": MOUSEBITE_PITCH,
                       "mousebites_per_tab": MOUSEBITE_COUNT,
                       "constellation_width_mm": 27.5, "star_diameter_mm": .8,
                       "slot_width_mm": 1, "minimum_constellation_web_mm": 1,
                       "slot_geometry_segments_per_semicircle": 64},
        "panel": {"nominal_outer_ring": ring(panel.exterior.coords),
                  "outer_ring": ring(routed_panel.exterior.coords),
                  "route_cutouts": encode_polygons(unary_union(enclosed_routes)),
                  "all_routing_regions": encode_polygons(routes),
                  "material_rings": encode_polygons(material),
                  "drills": drills,
                  "tabs": [{k: (ring(v.exterior.coords) if k == "shape" else v)
                            for k, v in t.items()} for t in tabs],
                  "board_outline_import_policy": "Use only panel.outer_ring as the panel exterior; "
                      "it already stitches exterior-touching routing mouths into one closed contour. "
                      "Import panel.route_cutouts and boards[].cutouts as closed routed voids. "
                      "Import all NPTH drills. panel.nominal_outer_ring and boards[].outer_ring are references only. "
                      "Do not import all_routing_regions as cutouts because some touch the exterior.",
                  "tooling_note": "2.0mm outer profile/router; 1.0mm cutter required for separate constellation slots. "
                      "0.8mm stars and 0.6mm mousebites are non-plated drills."},
        "boards": boards,
        "constellation": {"source": "data/constellation.json", "scale_mm_per_reference_px": scale,
                          "stars_local": stars,
                          "edges": [{k: v for k, v in s.items() if k != "shape"} for s in slots]},
        "assembly": {"stack": ["horse", "spacer2", "core", "spacer4", "sagittarius5"],
                     "total_nominal_thickness_mm": 5,
                     "glue_region": "peripheral spacer material only; keep 30mm internal windows clear",
                     "registration": "all five octagon centers and faces aligned; no permanent mounting holes",
                     "sagittarius_view": "Artwork and local star coordinates are the outside-back view. "
                         "Mirror across assembly local X when checking through-stack projection onto the core."},
        "manufacturing": {"substrate": "FR-4", "copper_weight_oz": 1,
                          "copper_layers": 2, "mask": "white",
                          "silkscreen": "JLCPCB multicolor color-silkscreen process",
                          "finish": "ENIG", "subboards_count": 5, "unique_designs_count": 4,
                          "color_silkscreen": {"enabled": True, "base_color": "gray",
                              "horse_symbol_color": "purple", "status": "planned; user image import and Gerber review required"},
                          "appearance_note": "Color artwork is a separate manufacturer output, not ordinary white silk or solder-mask color.",
                          "routing_order": "internal apertures, panel routing and NPTH, retain tabs; manually depanel after assembly"},
    }
    # Measurements deliberately use actual polygons rather than just formulas.
    star_shapes = [(s["id"], Point(s["center"]).buffer(.4, quad_segs=32)) for s in stars]
    slot_shapes = [(s["id"], s["shape"]) for s in slots]
    star_slot = min((a.distance(b), an, bn) for an, a in star_shapes for bn, b in slot_shapes)
    slot_slot = min((a.distance(b), an, bn) for (an, a), (bn, b) in itertools.combinations(slot_shapes, 2))
    star_star = min((a.distance(b), an, bn) for (an, a), (bn, b) in itertools.combinations(star_shapes, 2))
    board_gap = min((a["outer"].distance(b["outer"]), an, bn)
                    for (an, a), (bn, b) in itertools.combinations(board_shapes.items(), 2))
    board_tests = {k: {"is_valid": v["material"].is_valid,
                      "connected": v["material"].geom_type == "Polygon",
                      "area_mm2": v["material"].area,
                      "internal_void_count": len(v["voids"]),
                      "minimum_aperture_to_outer_mm": min((c.distance(v["outer"].boundary) for c in v["voids"]), default=None)}
                   for k, v in board_shapes.items()}
    rail_ok = material.covers(box(0, 0, 100, 3)) and material.covers(box(0, 97, 100, 100))
    checks = {"all_subboards_valid_and_connected": all(v["is_valid"] and v["connected"] for v in board_tests.values()),
              "whole_panel_material_connected": material.geom_type == "Polygon" and material.is_valid,
              "panel_bounds_exact_100mm": tuple(material.bounds) == (0., 0., 100., 100.),
              "top_bottom_3mm_rails_intact": rail_ok,
              "constellation_hole_slot_web_ge_1mm": star_slot[0] >= WEB - 1e-6,
              "constellation_slot_slot_web_ge_1mm": slot_slot[0] >= WEB - 1e-6,
              "constellation_slots_are_11_separate_closed_polygons": len(slots) == 11 and len(polygons(unary_union([s["shape"] for s in slots]))) == 11,
              "minimum_interboard_clearance_ge_2mm": board_gap[0] >= 2.0,
              "manufacturing_exterior_and_internal_routes_do_not_share_edges": all(c.distance(routed_panel.exterior) > 0 for c in enclosed_routes),
              "all_tabs_intersect_board_and_waste": all(t["shape"].intersection(board_shapes[t["board_id"]]["outer"]).area > 0
                   and t["shape"].intersection(waste).area > 0 for t in tabs)}
    validation = {"schema_version": 1, "status": "pass" if all(checks.values()) else "fail",
                  "checks": checks, "boards": board_tests,
                  "measurements": {"star_count": 8, "slot_count": 11,
                      "minimum_star_to_slot_web_mm": star_slot[0], "star_to_slot_pair": star_slot[1:],
                      "minimum_slot_to_slot_web_mm": slot_slot[0], "slot_to_slot_pair": slot_slot[1:],
                      "minimum_star_to_star_web_mm": star_star[0],
                      "minimum_slot_overall_length_mm": min(s["overall_length_mm"] for s in slots),
                      "minimum_slot_centerline_length_mm": min(s["centerline_length_mm"] for s in slots),
                      "minimum_interboard_clearance_mm": board_gap[0], "closest_board_pair": board_gap[1:],
                      "panel_material_components": len(polygons(material)),
                      "panel_route_cutout_components": len(polygons(routes)),
                      "panel_enclosed_route_cutouts": len(enclosed_routes),
                      "tabs_count": len(tabs), "mousebite_drill_count": len(drills),
                      "panel_material_area_mm2": material.area},
                  "limitations": ["Geometric validation is not a supplier production approval.",
                      "The 1.0mm slots require a 1.0mm router; external panel cuts use 2.0mm routing.",
                      "Horse light window is a clear FR-4 optical/mask feature, not a mechanical cutout.",
                      "Mousebites produce 0.25mm edge scallops before dressing; sand only tabs, protect antenna copper."]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "design.json").write_text(json.dumps(design, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (out / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    mechanical_body = f'<path d="{path_of(material)}" fill="#28252b" fill-rule="evenodd" stroke="#111" stroke-width="0.1"/>'
    (out / "panel-mechanical.svg").write_text(svg_document((0, 0, 100, 100), mechanical_body,
            "100x100mm mechanical material: connected panel, five boards, routing and NPTH"), encoding="utf-8")
    review_body = mechanical_body
    for b in boards:
        shape = board_shapes[b["id"]]["material"]
        review_body += f'\n<path d="{path_of(shape)}" fill="#49434f" fill-rule="evenodd" stroke="#ffa83f" stroke-width="0.13"/>'
        cx, cy = b["center"]
        label_y = cy+12 if b["id"] == "sagittarius5" else (cy+16.75 if b["id"].startswith("spacer") else cy)
        review_body += f'\n<text x="{cx}" y="{label_y}" fill="#eee" text-anchor="middle" font-family="Arial" font-size="2">{b["layer_index"]} {b["id"]}</text>'
    for t in tabs:
        review_body += f'\n<path d="{path_of(t["shape"].intersection(panel))}" fill="#69b888" opacity="0.6"/>'
    for d in drills:
        review_body += f'\n<circle cx="{d["center"][0]}" cy="{d["center"][1]}" r="0.25" fill="white"/>'
    (out / "panel-review.svg").write_text(svg_document((0, 0, 100, 100), review_body,
            "NFC talisman panel, five boards and four tabs per board"), encoding="utf-8")
    raster_preview(out, material, board_shapes, boards, tabs, drills)
    for b in boards:
        local = translate(board_shapes[b["id"]]["material"], -b["center"][0], -b["center"][1])
        body = f'<path d="{path_of(local)}" fill="#28252b" fill-rule="evenodd" stroke="#111" stroke-width="0.08"/>'
        (out / f'{b["id"]}-mechanical.svg').write_text(svg_document((-18.5, -18.5, 18.5, 18.5), body,
                f'{b["id"]} depanelled 37mm octagon'), encoding="utf-8")
    silhouette = octagon(37)
    star_voids = unary_union([g for _, g in star_shapes] + [g for _, g in slot_shapes])
    body = f'<path d="{path_of(silhouette.difference(star_voids))}" fill="#202026" fill-rule="evenodd"/>'
    for s in stars:
        body += f'<text x="{s["center"][0]}" y="{s["center"][1]+1.9}" font-size="1.15" fill="#ddd" text-anchor="middle">{s["name"]}</text>'
    (out / "sagittarius-stars-review.svg").write_text(svg_document((-18.5, -18.5, 18.5, 18.5), body,
            "Sagittarius eight stars and eleven isolated 1mm rounded slots"), encoding="utf-8")
    readme = """# Mechanical geometry\n\nAll coordinates are millimetres, panel origin top left and Y increasing downward.\n\n`design.json` is the EDA import source; `validation.json` contains Shapely checks.\nFor the manufacturing panel, use its single 100×100mm exterior, route cutouts,\nboard internal apertures and all NPTH drills. The five closed `boards[].outer_ring`\npolygons are depanelled references only. Do not import them as panel cutouts.\n\nEvery subboard has four 5mm connecting tabs with five Ø0.6mm NPTH holes per tab\non 0.95mm pitch (0.35mm nominal hole-edge spacing). The outer routing band is 2mm wide. Top and bottom rails retain\n3mm material. The design has 5 subboards and 4 distinct designs (the spacer is\nrepeated). External profile routing needs 2mm tooling; the 11 separate constellation\nslots require a 1mm cutter. Verify this distinction in supplier CAM review.\n\nThe horse cover has no designed aperture or image geometry yet; the user will\nmanually import the gray-base/purple-horse reference art in EasyEDA. Sagittarius\nhas 8 Ø0.8mm NPTH and 11 routed capsules. All optical-aperture material webs are\nchecked against 1mm. The shortest slot is only about 1.202mm end to end.\nThe spacer window is a regular octagon, 30mm across flats.\n\n`*-mechanical.svg` subboard files use local centres (0,0); `panel-mechanical.svg`\nshows actual panel material after every cut and NPTH, while `panel-review.svg`\nadds labels, subboard edge references and green tab overlays.\n\nBoth cover designs are defined as viewed from their exterior. The back-cover\nholes are mirrored only in an inner-face visualization, never in manufacturing.\nThe selected color-print route uses white solder mask and ENIG; verify supplier\npanel/SMT constraints and color-art alignment before ordering.\n\nRegenerate: `python hardware/nfc-talisman/scripts/build_mechanical.py`.\nShapely 2.x is required. No application, EDA window, or existing project is mutated.\n"""
    readme = readme.replace("For the manufacturing panel, use its single 100×100mm exterior, route cutouts,\nboard internal apertures and all NPTH drills. The five closed `boards[].outer_ring`\npolygons are depanelled references only. Do not import them as panel cutouts.",
        "For the manufacturing panel, use its single `panel.outer_ring`, enclosed\n"
        "`panel.route_cutouts`, board internal apertures and all NPTH drills. Outer routes\n"
        "touching the sheet edges are already stitched into that true exterior. Its\n"
        "bounding box is still 100×100mm. `panel.nominal_outer_ring` is a size reference\n"
        "only; `all_routing_regions` is a CAM reference and must not be reimported as\n"
        "cutouts because some regions touch the exterior. The five closed\n"
        "`boards[].outer_ring` polygons are depanelled references only.")
    readme = readme.replace("The spacer window is a regular octagon, 30mm across flats.",
        "The spacer window is 30mm across flats, with R1mm internal corners for a\n2mm router. Its nominal octagon is provided as a separate reference.")
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({"output": str(out), "status": validation["status"],
                      "checks": checks, "measurements": validation["measurements"]}, ensure_ascii=False, indent=2))
    if validation["status"] != "pass":
        raise SystemExit("Mechanical validation failed")


def build_assembly_preview(out: Path):
    """Export independent assembly aids without rewriting design.json."""
    from PIL import Image, ImageDraw, ImageFont
    from shapely.affinity import translate
    art = json.loads((OUT.parent / "artwork" / "art_data.json").read_text(encoding="utf-8"))
    design = json.loads((OUT / "design.json").read_text(encoding="utf-8"))

    class Drawing:
        def __init__(self, width, height):
            self.width, self.height = width, height
            self.parts = [f'<rect width="{width}" height="{height}" fill="#f7f5f0"/>']
            self.scale = 6
            self.image = Image.new("RGB", (width*self.scale, height*self.scale), "#f7f5f0")
            self.draw = ImageDraw.Draw(self.image)
        def xy(self, pts):
            return [(x*self.scale, y*self.scale) for x, y in pts]
        def polygon(self, pts, fill, stroke=None, width=.15, opacity=1):
            points = " ".join(f'{x:.4f},{y:.4f}' for x, y in pts)
            opacity_attr = "" if opacity >= 1 else f' fill-opacity="{opacity:.3f}" stroke-opacity="{opacity:.3f}"'
            self.parts.append(f'<polygon points="{points}" fill="{fill}" stroke="{stroke or fill}" stroke-width="{width}"{opacity_attr}/>')
            target = self.image if opacity >= 1 else self.image.copy()
            target_draw = self.draw if opacity >= 1 else ImageDraw.Draw(target)
            target_draw.polygon(self.xy(pts), fill=fill)
            if stroke:
                target_draw.line(self.xy([*pts, pts[0]]), fill=stroke, width=max(1, round(width*self.scale)))
            if opacity < 1:
                self.image = Image.blend(self.image, target, opacity)
                self.draw = ImageDraw.Draw(self.image)
        def area(self, outer, holes, fill, stroke=None):
            contours = [outer, *holes]
            path = " ".join("M"+" L".join(f'{x:.4f},{y:.4f}' for x, y in r)+" Z" for r in contours)
            self.parts.append(f'<path d="{path}" fill="{fill}" fill-rule="evenodd" stroke="{stroke or fill}" stroke-width="0.12"/>')
            overlay = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.polygon(self.xy(outer), fill=fill)
            for r in holes:
                odraw.polygon(self.xy(r), fill=(0, 0, 0, 0))
            self.image.paste(overlay, (0, 0), overlay)
            if stroke:
                for r in contours:
                    self.draw.line(self.xy([*r, r[0]]), fill=stroke, width=1)
        def line(self, pts, color="#6e6b65", width=.2, dashed=False):
            points = " ".join(f'{x:.4f},{y:.4f}' for x, y in pts)
            dash = ' stroke-dasharray="1.2 1.2"' if dashed else ""
            self.parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{width}"{dash} stroke-linecap="round"/>')
            if dashed:
                for a, b in zip(pts, pts[1:]):
                    length = math.dist(a, b)
                    if length == 0:
                        continue
                    for s in range(int(length/2.4)+1):
                        t0, t1 = min(1, s*2.4/length), min(1, (s*2.4+1.2)/length)
                        p = tuple(a[i]+(b[i]-a[i])*t0 for i in (0, 1))
                        q = tuple(a[i]+(b[i]-a[i])*t1 for i in (0, 1))
                        self.draw.line(self.xy([p, q]), fill=color, width=max(1, round(width*self.scale)))
            else:
                self.draw.line(self.xy(pts), fill=color, width=max(1, round(width*self.scale)))
        def text(self, x, y, value, size=3, color="#28252b", anchor="start"):
            self.parts.append(f'<text x="{x}" y="{y}" font-family="Microsoft YaHei,Arial,sans-serif" font-size="{size}" fill="{color}" text-anchor="{anchor}">{escape(value)}</text>')
            font_path = Path("C:/Windows/Fonts/msyh.ttc")
            try:
                font = ImageFont.truetype(str(font_path), round(size*self.scale))
            except OSError:
                font = ImageFont.truetype("arial.ttf", round(size*self.scale))
            self.draw.text((x*self.scale, y*self.scale), value, font=font, fill=color,
                           anchor={"start": "ls", "middle": "ms", "end": "rs"}[anchor])
        def save(self, name, title):
            (out / f'{name}.svg').write_text(svg_document((0, 0, self.width, self.height), "\n".join(self.parts), title), encoding="utf-8")
            self.image.save(out / f'{name}.png')

    fig = Drawing(260, 205)
    fig.text(10, 12, "37 mm NFC 符咒 · 五层叠装示意", size=5)
    fig.text(10, 20, "单片 FR-4 1 mm；爆炸间距仅用于展示；颜色与光效为示意。", size=3)
    cx, base_y, scale = 70, 160, 1.6
    def project(p, z):
        x, y = p
        return (cx+scale*.8660254*(x-y), base_y+scale*.5*(x+y)-scale*z)
    def horse_cover_base(move):
        """Reference-faithful blank base; the user will import the horse image."""
        fig.polygon([move(p) for p in ring(octagon(37).exterior.coords)],
                    "#858b8e", "#c0c3c3", .22)
        fig.polygon([move(p) for p in ring(octagon(33).exterior.coords)],
                    "#a5aaab", "#555b60", .18)
        fig.polygon([move(p) for p in ring(octagon(30).exterior.coords)],
                    "#151d27", "#c0c3c3", .22)
    outer = ring(octagon(37).exterior.coords)
    board_by_id = {b["id"]: b for b in design["boards"]}
    levels = {"sagittarius5": 0, "spacer4": 11, "core": 22, "spacer2": 33, "horse": 44}
    names = {"horse": "1  灰底马符咒盖板 · 紫马图待手动导入", "spacer2": "2  正面垫环 · 30 mm 内窗",
             "core": "3  NFC 核心 · 双面 LED", "spacer4": "4  背面垫环 · 30 mm 内窗",
             "sagittarius5": "5  拉丁文背盖 · Top 朝下"}
    for p in (outer[1], outer[5]):
        fig.line([project(p, -2), project(p, 48)], color="#bab4a7", dashed=True)
    for board_id in ("sagittarius5", "spacer4", "core", "spacer2", "horse"):
        z = levels[board_id]
        board = board_by_id[board_id]
        for a, b in zip(outer, outer[1:]+outer[:1]):
            fig.polygon([project(a, z), project(b, z), project(b, z+1), project(a, z+1)], "#817b6b", "#46433d", .1)
        holes = []
        if board_id.startswith("spacer"):
            hole = board["cutouts"][0]["ring"]
            holes.append([project((x-board["center"][0], y-board["center"][1]), z+1) for x, y in hole])
        elif board_id == "sagittarius5":
            for c in board["cutouts"]:
                # This exploded view looks down onto the rear cover's INNER
                # face; the source cutouts describe its OUTSIDE-back view.
                holes.append([project((-(x-board["center"][0]), y-board["center"][1]), z+1) for x, y in c["ring"]])
            for d in board["drills"]:
                pos = (-(d["center"][0]-board["center"][0]), d["center"][1]-board["center"][1])
                holes.append([project(p, z+1) for p in ring(Point(pos).buffer(.4, quad_segs=12).exterior.coords)])
        fill = "#858b8e" if board_id in ("horse", "sagittarius5") else ("#303032" if board_id == "core" else "#636569")
        fig.area([project(p, z+1) for p in outer], holes, fill, "#363332")
        if board_id == "horse":
            horse_cover_base(lambda p: project(p, z+1.015))
        if board_id == "sagittarius5":
            # The colored background is a visual process preview only; the
            # exposed constellation geometry remains the actual machined path.
            fig.polygon([project(p, z+1.015) for p in ring(octagon(33).exterior.coords)],
                        "#a5aaab", "#555b60", .18)
            fig.polygon([project(p, z+1.018) for p in ring(octagon(30).exterior.coords)],
                        "#151d27", "#c0c3c3", .22)
        if board_id == "core":
            for turn in range(4):
                pts = ring(octagon(34-turn).exterior.coords)
                fig.line([project(p, z+1.02) for p in pts+[pts[0]]], "#e4bc68", .25*scale)
            chip = [(-.8,-.8),(.8,-.8),(.8,.8),(-.8,.8)]
            fig.polygon([project(p, z+1.03) for p in chip], "#0c0d0e", "#aaa", .1)
            for lx, ly in ((-6, 0), (6, 4)):
                led = [(lx-.8,ly-.4),(lx+.8,ly-.4),(lx+.8,ly+.4),(lx-.8,ly+.4)]
                fig.polygon([project(p, z+1.04) for p in led], "#f4cb6f")
        label_y = project((0,0), z+1)[1]+2
        fig.line([project((18.5,0),z+1), (116,label_y)], "#8b8374", .15)
        fig.text(118, label_y+1, names[board_id], size=3.1)
    fig.text(12, 184, "胶层仅位于 3.5 mm 外围垫环实材；中央光路、器件和内窗保持清空。", 3.1)
    fig.text(12, 192, "核心电路位置为示意，实际以嘉立创EDA工程与贴片坐标为准。", 3)
    fig.text(12, 200, "马图按用户原图导入（灰底紫马）；预览暂留空，彩色丝印/透光需样件确认。", 2.8, "#6e6b65")

    # Exterior front/back views are independent of the exploded inner-face view.
    def face_inset(center, side):
        mx, my = center
        s = .95
        def move(p):
            return (mx+s*p[0], my+s*p[1])
        fig.polygon([move(p) for p in outer], "#1b2020", "#a49b83", .2)
        if side == "front":
            horse_cover_base(move)
        else:
            lines = art["sagittarius_silkscreen"]
            for slot in design["constellation"]["edges"]:
                fig.line([move(slot["endpoint_a"]),move(slot["endpoint_b"])], "#e7bf63", .95)
            for star in design["constellation"]["stars_local"]:
                fig.polygon([move(p) for p in ring(Point(star["center"]).buffer(.4, quad_segs=12).exterior.coords)], "#e7bf63")
        if side == "rear":
            for line in lines:
                pts = line["points"] + ([line["points"][0]] if line["closed"] else [])
                fig.line([move(p) for p in pts], "#eee8d6", line["width_mm"]*s)
    face_inset((232, 59), "front")
    fig.text(232, 35, "正面：从外侧看", 3, anchor="middle")
    face_inset((232, 116), "rear")
    fig.text(232, 92, "背面：从外侧看", 3, anchor="middle")

    # Real-thickness cross section, separate from the exploded illustration.
    left, right, sy = 195, 249, 165
    colors = ["#303032", "#77797a", "#303032", "#77797a", "#303032"]
    for i, col in enumerate(colors):
        yy = sy+i*2.2
        fig.polygon([(left,yy),(right,yy),(right,yy+2),(left,yy+2)],col)
        if i in (1,3):
            fig.polygon([(left+5.1,yy),(right-5.1,yy),(right-5.1,yy+2),(left+5.1,yy+2)], "#f7f5f0")
        if i<4:
            fig.line([(left,yy+2.1),(left+5.1,yy+2.1)], "#ddad58", .2)
            fig.line([(right-5.1,yy+2.1),(right,yy+2.1)], "#ddad58", .2)
    fig.text(222, 158, "侧视：5 mm＋4 个胶界面", 3, anchor="middle")
    fig.text(222, 180, "示意胶厚 0.1 mm / 界面", 2.6, anchor="middle")
    fig.save("stack-preview", "37mm NFC talisman assembly exploded view and exterior orientation")

    jig = Drawing(205, 145)
    jig.text(10, 12, "叠装定位夹具 · FDM 打印尺寸示意", 5)
    jig.text(10, 20, "尺寸 mm；属于辅助工具，口袋间隙需先试装；无需修改 PCB。", 3)
    jig_outer, pocket = octagon(50), octagon(37.4)
    finger = unary_union([Point(-24,0).buffer(6,quad_segs=24), Point(24,0).buffer(6,quad_segs=24)])
    wall = jig_outer.difference(unary_union([pocket, finger]))
    jig.polygon([[x+54,y+62] for x,y in ring(jig_outer.exterior.coords)], "#d7e2e6", "#425a68")
    for p in polygons(wall):
        jig.area([[x+54,y+62] for x,y in ring(p.exterior.coords)],
                 [[[x+54,y+62] for x,y in ring(i.coords)] for i in p.interiors], "#91a6b1", "#425a68")
    jig.line([(35.3,35),(72.7,35)], "#4d6573", .15)
    jig.line([(35.3,33),(35.3,37)], "#4d6573", .15)
    jig.line([(72.7,33),(72.7,37)], "#4d6573", .15)
    jig.text(54,31,"口袋对边距 37.4",3,anchor="middle")
    jig.line([(29,96),(79,96)], "#4d6573", .15)
    jig.line([(29,94),(29,98)], "#4d6573", .15)
    jig.line([(79,94),(79,98)], "#4d6573", .15)
    jig.text(54,103,"外形对边距 50",3,anchor="middle")
    jig.text(54,92,"俯视：两侧 Ø12 取件口",3,anchor="middle")
    # Section through solid faces, excluding the two finger access slots.
    jig.polygon([(117,63),(167,63),(167,71),(117,71)],"#91a6b1","#425a68")
    jig.polygon([(123.3,62.8),(160.7,62.8),(160.7,69),(123.3,69)],"#f7f5f0")
    for i in range(5):
        yy=68.8-i*1.08
        jig.polygon([(123.5,yy),(160.5,yy),(160.5,yy+.98),(123.5,yy+.98)],colors[i])
    jig.text(142,48,"剖面：对齐未开取件口的平边",3,anchor="middle")
    jig.text(142,81,"总高 8 · 底厚 2 · 口袋深 6",3,anchor="middle")
    jig.text(142,90,"37 mm 板单边名义间隙 0.2",3,anchor="middle")
    jig.text(142,99,"胶合时使用平压板，均匀轻压外围",3,anchor="middle")
    jig.text(10,117,"建议：PLA / PETG；层高 0.2 mm；无需金属定位件。",3)
    jig.text(10,125,"先放单片检查松紧和基准平边，再试叠装；取件口底部保留 2 mm 底板。",3)
    jig.text(10,133,"assembly-jig.scad 包含夹具和独立 37 mm 压板；STL 导出前核验打印机尺寸。",3)
    jig.text(10,141,"辅助夹具未实物打印，尺寸与装配间隙尚未实测。",3,"#6e6b65")
    jig.save("assembly-jig", "NFC talisman 3D-printable assembly alignment jig dimension drawing")
    scad = '''// NFC talisman assembly jig. Dimensions mm; print fit is unverified.
// Tray: 50mm across flats, 8mm high, 37.4mm pocket, 6mm deep, 2mm floor.
// Two 12mm finger openings leave the floor intact. Press plate is separate.
$fn = 72;
function octagon(af) = let(h=af/2,b=h*tan(22.5))
    [[-b,-h],[b,-h],[h,-b],[h,b],[b,h],[-b,h],[-h,b],[-h,-b]];
module tray() {
    difference() {
        linear_extrude(8) polygon(octagon(50));
        translate([0,0,2]) linear_extrude(6.1) polygon(octagon(37.4));
        for (x=[-24,24]) translate([x,0,2]) cylinder(h=6.1,d=12);
    }
}
module press_plate() {
    linear_extrude(2) polygon(octagon(37));
    translate([0,0,2]) cylinder(h=6,d=12);
}
tray();
translate([60,0,0]) press_plate();
'''
    (out/"assembly-jig.scad").write_text(scad,encoding="utf-8")
    notes = '''# 五层硬币装配与图案方向

五片双层 FR-4 各厚 1 mm，裸板叠装约 5 mm，另加胶层。马头图片尚未放入设计，爆炸预览只表示灰色八边形底座和空置图像范围；芯片、线圈、光效及颜色均须在样件上验证。

## 试装顺序

1. 先焊核心板，单独检查 NFC 读写、VOUT 与两面 LED；修整邮票孔毛边时避开外围线圈。
2. 夹具内放第 5 层射手座盖板，外侧图案朝下；放第 4 层垫环、核心板（Top 朝马面）、第 2 层垫环，最后放第 1 层马盖板，马面朝上。逐层对齐同一条基准平边。
3. 先干式试装，确认器件不顶盖、两个 30 mm 光腔无遮挡；可比较非金属扩散片，但要避开芯片、LED、天线和胶区。
4. NFC 读写与两面光效通过后，再逐层少量涂非导电胶。胶只落在垫环外围 3.5 mm 实材，不得挤入内窗、星孔、光槽、器件区或天线区。
5. 均匀压合并按胶厂要求固化。胶合会改变谐振；成品需重新记录读距、VOUT、灯光和调谐电容。

## 图案面与工艺

- 马符咒照用户附件：灰色八边形底座、暗色内场、紫色马首侧影，方向与参考一致，不镜像、不增添其他装饰。用户在 `ManufacturingPanel100` 中手动导入，中心 `(20.5,23.5) mm`；独立马盖板中心为 `(0,0)`。
- 射手座外侧只有八星孔、十一条透光槽和拉丁文 `AD ASTRA`、`FORTIS ET LIBER`；不加人马丝印。背面文字从外侧左至右可读。
- 两片外盖图案都在各自 PCB Top，导入时使用外侧方向。装配时马盖 Top 朝外，射手座盖 Top 朝外；不要对图像或星孔额外镜像。
- 灰底紫马采用嘉立创彩色丝印工艺路线：白色阻焊、沉金、双层板并输出彩色丝印文件。彩色印刷是否遮挡暖光尚待试样；需先检查彩印预览、Gerber 与实物透光，再最终胶合。
- 夹具口袋对边距 37.4 mm，名义单边间隙 0.2 mm；打印收缩、板边公差和邮票孔残边尚未实测，先做单片试配。

## 尚未测量

没有实测 FR-4 透光率、彩色油墨透光、胶厚、器件顶高、夹具尺寸、成品谐振与手机读距。当前预览不是加工或装配验收结果。
'''
    (out/"assembly-notes.md").write_text(notes,encoding="utf-8")
    print(json.dumps({"status":"generated_unmeasured", "outputs":["stack-preview.svg","stack-preview.png","assembly-jig.svg","assembly-jig.png","assembly-jig.scad","assembly-notes.md"],"design_json_modified":False},ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--assembly-only", action="store_true", help="Export assembly aids without rewriting existing geometry design")
    args = parser.parse_args()
    if args.assembly_only:
        build_assembly_preview(args.output)
    else:
        build(args.output)
