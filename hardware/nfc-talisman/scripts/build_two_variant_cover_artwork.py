from __future__ import annotations

import base64
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

REPO = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parents[1]
ART = BASE / "artwork"
VARIANTS = BASE / "variants"
SNAKE_OUT = VARIANTS / "snake-leo" / "artwork"
HORSE_OUT = VARIANTS / "horse-sagittarius" / "artwork"
SNAKE_OUT.mkdir(parents=True, exist_ok=True)
HORSE_OUT.mkdir(parents=True, exist_ok=True)

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
PPI = 300
PAGE_PX = 1821  # Sharp's 300 dpi SVG raster for 37mm; the closest integer PNG DPI is 1250.
PNG_DPI = 1250  # Sharp writes integer DPI; 1821px at 1250dpi equals 37.00272mm.
AF = 37.0
HALF = 18.5
BEVEL = HALF * math.tan(math.pi / 8)
OCTAGON_LOCAL = [(-BEVEL, -HALF), (BEVEL, -HALF), (HALF, -BEVEL),
                 (HALF, BEVEL), (BEVEL, HALF), (-BEVEL, HALF),
                 (-HALF, BEVEL), (-HALF, -BEVEL)]
OCTAGON_PAGE = [(x + HALF, y + HALF) for x, y in OCTAGON_LOCAL]
POINTS_PAGE = " ".join(f"{x:.6f},{y:.6f}" for x, y in OCTAGON_PAGE)

SNAKE = ART / "reference-collection" / "talisman-single-ink-v1" / "snake-single-ink.png"
HORSE = ART / "reference-collection" / "talisman-single-ink-v1" / "horse-single-ink.png"
SAG_B = ART / "star-style-study-v1" / "B-soft-type-day.svg"
LEO_SOURCE = VARIANTS / "snake-leo" / "leo-artwork.svg"
DESIGN = BASE / "geometry" / "design.json"
LEO_GEOMETRY = VARIANTS / "snake-leo" / "leo-geometry.json"
GEORGIA = Path(r"C:\Windows\Fonts\georgia.ttf")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def svg_root(title: str, desc: str) -> ET.Element:
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": "37mm", "height": "37mm", "viewBox": "0 0 37 37",
    })
    ET.SubElement(root, f"{{{SVG_NS}}}title").text = title
    ET.SubElement(root, f"{{{SVG_NS}}}desc").text = desc
    defs = ET.SubElement(root, f"{{{SVG_NS}}}defs")
    clip = ET.SubElement(defs, f"{{{SVG_NS}}}clipPath", {"id": "af37", "clipPathUnits": "userSpaceOnUse"})
    ET.SubElement(clip, f"{{{SVG_NS}}}polygon", {"points": POINTS_PAGE})
    return root


def group(root: ET.Element, **attrs: str) -> ET.Element:
    return ET.SubElement(root, f"{{{SVG_NS}}}g", attrs)


def outlined_text(parent: ET.Element, font: TTFont, value: str, *, baseline: float, size: float, letter_spacing: float, ident: str) -> dict:
    """Add centered real Georgia outlines in local mm coordinates (x right, y down)."""
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    units = font["head"].unitsPerEm
    scale = size / units
    metrics = font["hmtx"].metrics
    names = [cmap[ord(ch)] for ch in value]
    widths = [metrics[name][0] * scale for name in names]
    total = sum(widths) + max(0, len(value) - 1) * letter_spacing
    x = -total / 2
    paths = 0
    for index, (char, name, width) in enumerate(zip(value, names, widths)):
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        d = pen.getCommands()
        if d:
            ET.SubElement(parent, f"{{{SVG_NS}}}path", {
                "id": f"{ident}_glyph_{index+1:02d}", "d": d,
                "fill": "#eee8d6", "stroke": "none",
            })
            paths += 1
        x += width + letter_spacing
    return {"text": value, "baseline_mm": baseline, "font_size_mm": size,
            "letter_spacing_mm": letter_spacing, "glyph_paths": paths}


def add_cutout_mask(root: ET.Element, source_group: ET.Element, *, leo: bool) -> dict:
    """Mask physical apertures plus a 0.20mm clear substrate reveal; no white ink rings."""
    defs = root.find(f"{{{SVG_NS}}}defs")
    assert defs is not None
    mask_id = "physical-apertures-and-020mm-substrate-reveal"
    mask = ET.SubElement(defs, f"{{{SVG_NS}}}mask", {
        "id": mask_id, "maskUnits": "userSpaceOnUse", "maskContentUnits": "userSpaceOnUse",
        "x": "-18.5", "y": "-18.5", "width": "37", "height": "37",
        "style": "mask-type:luminance",
    })
    ET.SubElement(mask, f"{{{SVG_NS}}}rect", {
        "x": "-18.5", "y": "-18.5", "width": "37", "height": "37", "fill": "white",
    })
    openings = group(mask)
    count_slots = count_holes = 0
    if leo:
        geometry = json.loads(LEO_GEOMETRY.read_text(encoding="utf-8"))["constellation"]
        stars = geometry["stars"]
        slots = geometry["physical_slots"]
        for star in stars:
            x, y = star["center_mm"]
            ET.SubElement(openings, f"{{{SVG_NS}}}circle", {
                "cx": str(x), "cy": str(y), "r": "0.6", "fill": "black",
            })
            count_holes += 1
        for slot in slots:
            x1, y1 = slot["centerline_start"]
            x2, y2 = slot["centerline_end"]
            ET.SubElement(openings, f"{{{SVG_NS}}}path", {
                "d": f"M {x1},{y1} L {x2},{y2}", "fill": "none", "stroke": "black",
                "stroke-width": "1.40", "stroke-linecap": "round",
            })
            count_slots += 1
    else:
        for element in source_group.iter():
            ident = element.get("id", "")
            if not ident.endswith("_buffer"):
                continue
            tag = element.tag.rsplit("}", 1)[-1]
            attrs = dict(element.attrib)
            attrs.pop("id", None)
            attrs["fill"] = "black"
            if tag == "path":
                attrs["stroke"] = "black"
                attrs["stroke-width"] = "1.40"
                attrs["stroke-linecap"] = "round"
                attrs["fill"] = "none"
                count_slots += 1
            elif tag == "circle":
                count_holes += 1
            ET.SubElement(openings, f"{{{SVG_NS}}}{tag}", attrs)
    # Keep a machine-readable SVG metadata note as well as the manifest/README explanation.
    return {"mask_id": mask_id, "physical_slots": count_slots, "physical_holes": count_holes,
            "reveal_mm": 0.20, "meaning": "alpha-clear substrate reveal around real apertures; not printed white ink"}


def add_animal_cover(path: Path, title: str, png: Path) -> None:
    root = svg_root(title, "Exact 37mm square print object; art is clipped to the AF37 octagon. Animal image is embedded byte-for-byte from the approved single-ink PNG.")
    g = group(root, **{"clip-path": "url(#af37)"})
    ET.SubElement(g, f"{{{SVG_NS}}}polygon", {"points": POINTS_PAGE, "fill": "#c9c7c0"})
    encoded = base64.b64encode(png.read_bytes()).decode("ascii")
    image = ET.SubElement(g, f"{{{SVG_NS}}}image", {
        "x": "3", "y": "3", "width": "31", "height": "31",
        "preserveAspectRatio": "xMidYMid meet",
        "href": f"data:image/png;base64,{encoded}",
    })
    # Keep an explicit xlink reference for importers that do not yet read SVG2 href.
    image.set("{http://www.w3.org/1999/xlink}href", f"data:image/png;base64,{encoded}")
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")


def add_vector_cover(path: Path, title: str, source: Path, *, leo: bool, font: TTFont) -> dict:
    src_root = ET.parse(source).getroot()
    root = svg_root(title, "Exact 37mm square print object; all artwork is clipped to the AF37 octagon. Exterior view at 0 degrees with no mirror, matching the existing outer-face artwork convention.")
    clipped = group(root, **{"clip-path": "url(#af37)"})
    if leo:
        artwork = group(clipped, transform="translate(18.5 18.5)")
        g = group(artwork)
        for child in list(src_root):
            ident = child.get("id", "")
            if child.tag.rsplit("}", 1)[-1] not in {"title", "desc"} and not ident.startswith(("leo_title_", "latin_ad_astra_")):
                g.append(child)
        text_audit = [outlined_text(g, font, "LEO", baseline=-14.20, size=1.52, letter_spacing=0.055, ident="outlined_leo"),
                      outlined_text(g, font, "AD ASTRA", baseline=14.63, size=1.62, letter_spacing=0.09, ident="outlined_ad_astra")]
        mask_info = add_cutout_mask(root, g, leo=True)
        artwork.set("mask", "url(#physical-apertures-and-020mm-substrate-reveal)")
    else:
        source_group = next(el for el in src_root.iter() if el.tag.rsplit("}", 1)[-1] == "g" and el.get("id") == "white-soldermask-and-ink")
        mask_info = add_cutout_mask(root, source_group, leo=False)
        artwork = group(clipped, transform="translate(18.5 18.5)")
        g = group(artwork)
        bg_index = 0
        for child in list(source_group):
            tag = child.tag.rsplit("}", 1)[-1]
            ident = child.get("id", "")
            if tag == "text" or ident.endswith("_buffer") or ident.startswith(("slot_", "hip_")):
                continue
            if tag == "polygon" and child.get("fill", "").lower() == "#ffffff" and bg_index == 0:
                # Omit the white soldermask simulation at the board edge.
                bg_index += 1
                continue
            if tag == "polygon" and child.get("fill", "").lower() == "#17232f" and bg_index <= 1:
                # Expand the dark substrate to the actual AF37 boundary; leave the B linework and soft type intact.
                child.set("points", " ".join(f"{x:.6f},{y:.6f}" for x, y in OCTAGON_LOCAL))
                bg_index = 2
            g.append(child)
        if bg_index != 2:
            raise ValueError("B study SVG background polygons did not match expected white/dark order")
        text_audit = [outlined_text(g, font, "SAGITTARIUS", baseline=-14.20, size=1.52, letter_spacing=0.055, ident="outlined_sagittarius"),
                      outlined_text(g, font, "AD ASTRA", baseline=14.63, size=1.62, letter_spacing=0.09, ident="outlined_ad_astra")]
        artwork.set("mask", "url(#physical-apertures-and-020mm-substrate-reveal)")
    live_text_nodes = sum(1 for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "text")
    if live_text_nodes:
        raise ValueError(f"Live SVG text remains in {path.name}")
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return {"font_file": str(GEORGIA), "font_sha256": sha(GEORGIA),
            "font_family": "Georgia Regular", "live_text_nodes": live_text_nodes,
            "outlined_texts": text_audit, "svg_path_count": sum(1 for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "path"),
            "cutout_mask": mask_info}


NODE = r"C:\Users\20177\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
SHARP = r"C:\Users\20177\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\sharp"


def render(out_dirs: list[Path]) -> None:
    js = r'''const fs=require('fs');const sharp=require(process.argv[1]);const dirs=process.argv.slice(2);(async()=>{for(const dir of dirs){const files=fs.readdirSync(dir).filter(n=>n.endsWith('.svg'));for(const name of files){const stem=name.slice(0,-4);const svg=fs.readFileSync(dir+'/'+name);await sharp(svg,{density:300}).png().withMetadata({density:1250}).toFile(dir+'/'+stem+'.png');}const page=Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1860" height="1000"><rect width="1860" height="1000" fill="#ece9e1"/><text x="480" y="960" text-anchor="middle" font-family="sans-serif" font-size="26" letter-spacing="3" fill="#4c4a45">FRONT</text><text x="1380" y="960" text-anchor="middle" font-family="sans-serif" font-size="26" letter-spacing="3" fill="#4c4a45">REAR</text></svg>`);const fronts=fs.readdirSync(dir).filter(n=>n.startsWith('front-')&&n.endsWith('.png'))[0];const rears=fs.readdirSync(dir).filter(n=>n.startsWith('rear-')&&n.endsWith('.png'))[0];const a=await sharp(dir+'/'+fronts).resize(900,900).png().toBuffer();const b=await sharp(dir+'/'+rears).resize(900,900).png().toBuffer();await sharp(page).composite([{input:a,left:30,top:20},{input:b,left:930,top:20}]).png().toFile(dir+'/cover-review-preview.png');}})();'''
    subprocess.run([NODE, "-e", js, SHARP, *map(str, out_dirs)], check=True)


def alpha_corners(path: Path) -> list[int]:
    js = r'''const sharp=require(process.argv[1]);(async()=>{const {data,info}=await sharp(process.argv[2]).ensureAlpha().raw().toBuffer({resolveWithObject:true});const pts=[[0,0],[info.width-1,0],[0,info.height-1],[info.width-1,info.height-1]];console.log(JSON.stringify(pts.map(([x,y])=>data[(y*info.width+x)*4+3])));})();'''
    r = subprocess.run([NODE, "-e", js, SHARP, str(path)], check=True, capture_output=True, text=True)
    return json.loads(r.stdout)


def write_manifest(out: Path, name: str, inputs: dict[str, Path], orientation: str, files: list[str], outline_audit: dict) -> None:
    before = {label: sha(p) for label, p in inputs.items()}
    pngs = [out / f.replace(".svg", ".png") for f in files]
    manifest = {
        "status": "37mm_cover_objects_rendered",
        "variant": name,
        "canvas_mm": [37, 37],
        "canvas_pixels": [PAGE_PX, PAGE_PX],
        "png_dpi": round(PNG_DPI, 3),
        "octagon_across_flats_mm": 37,
        "octagon_clip_points_mm_from_top_left": [[round(x, 6), round(y, 6)] for x, y in OCTAGON_PAGE],
        "outside_octagon": "transparent, antialiased at the edge",
        "orientation": orientation,
        "input_sha256": before,
        "files": {
            png.name: {
                "sha256": sha(png),
                "svg_sha256": sha(out / png.name.replace(".png", ".svg")),
                "dimensions_px": [PAGE_PX, PAGE_PX],
                "dpi": round(PNG_DPI, 3),
                "physical_size_mm_from_png_metadata": [round(PAGE_PX * 25.4 / PNG_DPI, 6)] * 2,
                "alpha_at_four_corners": alpha_corners(png),
                "transparent_outside_af37": all(a == 0 for a in alpha_corners(png)),
            }
            for png in pngs
        },
        "preview": {
            "file": "cover-review-preview.png",
            "sha256": sha(out / "cover-review-preview.png"),
            "dimensions_px": [1860, 1000],
        },
        "render": "Configured Sharp runtime at 300 input DPI; embedded approved animal PNG is preserved as source bytes inside SVG and composited without raster edits.",
        "font_outline_validation": outline_audit,
        "aperture_rendering": "Physical holes and slots plus 0.20mm reveal are alpha clear; the reveal exposes substrate/white soldermask and is not printed white ink or a mechanical border.",
    }
    if any(not x["transparent_outside_af37"] for x in manifest["files"].values()):
        raise ValueError(f"Corner alpha check failed for {name}")
    if before != {label: sha(p) for label, p in inputs.items()}:
        raise ValueError(f"Input source hash changed while generating {name}")
    manifest["input_unchanged_after_render"] = True
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    boards = {b["id"]: b for b in design["boards"]}
    if boards["horse"]["orientation"] != "viewed_from_assembly_outside_y_down":
        raise ValueError("Horse outer-face orientation changed; review before import")
    if boards["sagittarius5"]["orientation"] != "viewed_from_assembly_outside_y_down":
        raise ValueError("Sagittarius outer-face orientation changed; review before import")
    if boards.get("leo", {}).get("orientation", "viewed_from_assembly_outside_y_down") != "viewed_from_assembly_outside_y_down":
        raise ValueError("Leo outer-face orientation changed; review before import")

    snake_svg = SNAKE_OUT / "front-snake-37mm.svg"
    leo_svg = SNAKE_OUT / "rear-leo-37mm.svg"
    horse_svg = HORSE_OUT / "front-horse-37mm.svg"
    sag_svg = HORSE_OUT / "rear-sagittarius-37mm.svg"
    add_animal_cover(snake_svg, "Snake outer face, 37mm AF37 print object", SNAKE)
    font = TTFont(str(GEORGIA))
    leo_audit = add_vector_cover(leo_svg, "Leo outer face, 37mm AF37 print object", LEO_SOURCE, leo=True, font=font)
    add_animal_cover(horse_svg, "Horse outer face, 37mm AF37 print object", HORSE)
    sag_audit = add_vector_cover(sag_svg, "Sagittarius B soft type, 37mm AF37 print object", SAG_B, leo=False, font=font)

    render([SNAKE_OUT, HORSE_OUT])
    write_manifest(SNAKE_OUT, "snake-leo", {
        "approved_snake_single_ink_png": SNAKE,
        "leo_artwork_source_svg": LEO_SOURCE,
        "leo_physical_geometry_json": LEO_GEOMETRY,
        "snake_geometry_design_json": DESIGN,
    }, "exterior view of the snake outer face, 0 degrees, not mirrored; image orientation kept byte-exact from the approved source", [snake_svg.name, leo_svg.name], leo_audit)
    write_manifest(HORSE_OUT, "horse-sagittarius", {
        "approved_horse_single_ink_png": HORSE,
        "sagittarius_B_soft_type_source_svg": SAG_B,
        "sagittarius_geometry_design_json": DESIGN,
    }, "horse viewed from assembly outside, y-down, not mirrored; Sagittarius exterior rear view, 0 degrees, not mirrored", [horse_svg.name, sag_svg.name], sag_audit)

    for out, source_labels in [(SNAKE_OUT, "snake + Leo"), (HORSE_OUT, "horse + Sagittarius")]:
        rear_description = ("Leo uses the project's Stellarium Modern star chart and original screen orientation, with the simplified 9-star structure." if out == SNAKE_OUT else "Sagittarius adapts star-style-study-v1 B, with its fine pale constellation strokes and soft Georgia layout.")
        (out / "README.md").write_text(f'''# {source_labels} 37mm cover print objects\n\n`front-*.svg` and `rear-*.svg` are exact 37mm × 37mm square SVG print objects. Their clipping path is the existing AF37 octagon; all artwork outside that octagon is transparent. The corresponding PNGs are {PAGE_PX} × {PAGE_PX} with {PNG_DPI:.0f} dpi metadata (37.00272mm square by the PNG metadata; set the native image object to exactly 37mm when importing). `cover-review-preview.png` shows the front and rear side by side for visual review.\n\nThe warm-gray front cover uses an embedded, unchanged approved single-ink PNG. Rear title text uses outlined Georgia Regular paths to match Sagittarius B's soft serif style; the SVGs contain no live text nodes or font dependency. {rear_description}\n\nPhysical holes and slots and a 0.20mm surrounding clear reveal are transparent in the print PNG. They expose the substrate/white soldermask in the native stack; the reveal is not white ink and the openings are not mechanical border artwork. For Sagittarius, the B study's daytime white-soldermask simulation is removed.\n\nUse the SVG as the editable source and import the matching PNG into the native 37mm square color-object layer when image placement is preferred. The PNG remains unmirrored and has transparent outside corners. Verify the native image Y-axis convention during import before final output; the source geometry/artwork itself remains in the documented exterior view. See `manifest.json` for source and generated SHA256 hashes, exact clip coordinates, dimensions, alpha checks and Georgia outline validation. This is a print-object candidate, not a manufacturing or physical color qualification.\n''', encoding="utf-8")

    print(json.dumps({
        "snake_leo": str(SNAKE_OUT), "horse_sagittarius": str(HORSE_OUT),
        "canvas_mm": [37, 37], "pixels": [PAGE_PX, PAGE_PX],
        "dpi": round(PNG_DPI, 3), "af37_transparent_corners_pass": True,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
