#!/usr/bin/env python3
"""
extract_design_system.py — Layer 1 (design system) + Layer 2 (slide objects)

Unlike a text+image dump, this extractor PRESERVES what medical slides depend on:
geometry (x/y/w/h), text runs with emphasis, fonts, colors, tables, lines
(incl. the bottom blue line), and GROUPED shapes (recursed, never dropped).

Output: design-extract.json  (consumed by build.py -> semantic component HTML)

Usage:
    python extract_design_system.py <input.pptx> <output_dir>

Requires: pip install python-pptx
"""
import json
import os
import sys
from collections import Counter

from pptx import Presentation
from pptx.util import Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE
try:
    from pptx.enum.dml import MSO_COLOR_TYPE
except Exception:  # pragma: no cover
    MSO_COLOR_TYPE = None

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


# ----------------------------- color helpers -----------------------------
def rgb_or_none(color):
    """Return '#rrggbb' for an explicit RGB color, else None (let tokens apply)."""
    try:
        if color is None:
            return None
        if MSO_COLOR_TYPE is not None and color.type == MSO_COLOR_TYPE.RGB:
            return "#" + str(color.rgb).lower()
        # Some files expose .rgb even for theme colors; try, but tolerate failure.
        return "#" + str(color.rgb).lower()
    except Exception:
        return None


def slide_background(slide):
    for src in (slide, slide.slide_layout, slide.slide_layout.slide_master):
        try:
            fill = src.background.fill
            if fill.type is not None:
                c = rgb_or_none(fill.fore_color)
                if c:
                    return c
        except Exception:
            continue
    return None


# ----------------------------- geometry -----------------------------
def frac(shape, W, H):
    """Absolute geometry as fractions of the slide (0..1). Defensive on None."""
    try:
        l = int(shape.left or 0); t = int(shape.top or 0)
        w = int(shape.width or 0); h = int(shape.height or 0)
        return {"xf": l / W, "yf": t / H, "wf": w / W, "hf": h / H}
    except Exception:
        return {"xf": 0, "yf": 0, "wf": 0, "hf": 0}


def group_child_transform(group):
    """Return a function mapping a child shape's EMU box to absolute EMU,
    honoring the group's child coordinate space (chOff/chExt vs off/ext).
    This is what makes grouped multi-panel figures survive."""
    try:
        xfrm = group._element.find(".//a:xfrm", NS)
        off = xfrm.find("a:off", NS); ext = xfrm.find("a:ext", NS)
        choff = xfrm.find("a:chOff", NS); chext = xfrm.find("a:chExt", NS)
        ox, oy = int(off.get("x")), int(off.get("y"))
        ex, ey = int(ext.get("cx")), int(ext.get("cy"))
        cox, coy = int(choff.get("x")), int(choff.get("y"))
        cex, cey = int(chext.get("cx")), int(chext.get("cy"))
        sx = ex / cex if cex else 1.0
        sy = ey / cey if cey else 1.0

        def fn(l, t, w, h):
            return (ox + (l - cox) * sx, oy + (t - coy) * sy, w * sx, h * sy)
        return fn
    except Exception:
        return lambda l, t, w, h: (l, t, w, h)


# ----------------------------- text -----------------------------
def extract_text(tf):
    """Paragraphs -> runs, preserving bold/italic/underline/size/color."""
    paras = []
    for p in tf.paragraphs:
        runs = []
        psize = p.font.size.pt if p.font.size is not None else None  # paragraph fallback
        for r in p.runs:
            f = r.font
            runs.append({
                "t": r.text,
                "b": bool(f.bold),
                "i": bool(f.italic),
                "u": bool(f.underline),
                "size": float(f.size.pt) if f.size is not None else psize,
                "color": rgb_or_none(f.color) if r.text else None,
                "name": f.name,
            })
        paras.append({"level": p.level or 0, "align": str(p.alignment) if p.alignment else None, "runs": runs})
    return paras


def para_plain(paras):
    return "\n".join("".join(r["t"] for r in p["runs"]) for p in paras).strip()


def dominant_size(paras):
    sizes = [r["size"] for p in paras for r in p["runs"] if r["size"]]
    return max(sizes) if sizes else None


# ----------------------------- classification -----------------------------
def classify(kind, role_hint, geo, text, font_size, slidew_frac_mid=0.5):
    """Best-effort role inference. The author can correct in the editable HTML;
    classification only chooses which semantic component to emit."""
    if role_hint:
        return role_hint
    yf, xf, wf, hf = geo["yf"], geo["xf"], geo["wf"], geo["hf"]
    if kind == "picture":
        small = wf < 0.18 and hf < 0.18
        top = yf < 0.14
        if small and top:
            return "logo"
        return "figure"
    if kind == "line":
        return "bottom-line" if yf > 0.85 else "rule"
    if kind == "table":
        return "table"
    if kind == "text":
        low = yf > 0.86
        tiny = (font_size or 99) <= 16
        if low and tiny:
            # citation vs footer: citations usually carry digits/journal punctuation
            if any(ch.isdigit() for ch in text) and (";" in text or ":" in text or "et al" in text.lower()):
                return "citation"
            return "footer"
        if tiny and not low:
            return "caption"
        return "body"
    return "generic"


# ----------------------------- shape walk -----------------------------
def walk(shapes, W, H, out, assets_dir, slide_no, abs_xform=None, counters=None):
    counters = counters if counters is not None else {"img": 0}
    for sh in shapes:
        try:
            st = sh.shape_type
        except Exception:
            st = None

        # Recurse groups WITH transform so children keep correct absolute geometry.
        if st == MSO_SHAPE_TYPE.GROUP:
            child_xform = group_child_transform(sh)
            walk(sh.shapes, W, H, out, assets_dir, slide_no, child_xform, counters)
            continue

        # Compute absolute geometry (apply parent group transform if any).
        try:
            l = int(sh.left or 0); t = int(sh.top or 0)
            w = int(sh.width or 0); h = int(sh.height or 0)
        except Exception:
            l = t = w = h = 0
        if abs_xform:
            l, t, w, h = abs_xform(l, t, w, h)
        geo = {"xf": l / W, "yf": t / H, "wf": w / W, "hf": h / H}

        role_hint = None
        try:
            if sh.is_placeholder:
                ph = str(sh.placeholder_format.type)
                if "SUBTITLE" in ph:          # check SUBTITLE before TITLE (substring!)
                    role_hint = "section-title"
                elif "TITLE" in ph:
                    role_hint = "title"
        except Exception:
            pass

        # Pictures
        if st == MSO_SHAPE_TYPE.PICTURE:
            counters["img"] += 1
            try:
                img = sh.image
                name = "s%02d_img%02d.%s" % (slide_no, counters["img"], img.ext)
                with open(os.path.join(assets_dir, name), "wb") as f:
                    f.write(img.blob)
                px = img.size  # (w,h) native pixels
            except Exception:
                name, px = None, None
            out.append({"kind": "picture", "role": classify("picture", role_hint, geo, "", None),
                        "geo": geo, "src": ("assets/" + name) if name else None,
                        "native": px})
            continue

        # Tables
        if getattr(sh, "has_table", False):
            tbl = sh.table
            rows = [[cell.text for cell in row.cells] for row in tbl.rows]
            out.append({"kind": "table", "role": "table", "geo": geo, "rows": rows})
            continue

        # Lines / connectors (the bottom blue line lives here)
        if st in (MSO_SHAPE_TYPE.LINE,) or (sh.__class__.__name__ == "Connector"):
            color = None
            try:
                color = rgb_or_none(sh.line.color)
            except Exception:
                pass
            out.append({"kind": "line", "role": classify("line", None, geo, "", None),
                        "geo": geo, "color": color})
            continue

        # Text-bearing shapes (placeholders, text boxes, autoshapes with text)
        if getattr(sh, "has_text_frame", False) and sh.text_frame.text.strip():
            paras = extract_text(sh.text_frame)
            text = para_plain(paras)
            fsize = dominant_size(paras)
            role = classify("text", role_hint, geo, text, fsize)
            out.append({"kind": "text", "role": role, "geo": geo,
                        "paras": paras, "plain": text, "size": fsize})
            continue

        # Autoshape with a fill but no text (rules, banners) — keep, don't drop.
        if st == MSO_SHAPE_TYPE.AUTO_SHAPE:
            fill = None
            try:
                fill = rgb_or_none(sh.fill.fore_color)
            except Exception:
                pass
            role = "bottom-line" if (geo["yf"] > 0.85 and geo["hf"] < 0.03) else "generic"
            out.append({"kind": "shape", "role": role, "geo": geo, "fill": fill})
            continue


# ----------------------------- design system -----------------------------
def infer_design_system(prs, slides):
    """Layer 1: distill reusable tokens from the deck."""
    theme_major = theme_minor = None
    try:
        master = prs.slide_masters[0]
        fonts = master.element.find(".//a:fontScheme", NS)
        if fonts is not None:
            mj = fonts.find(".//a:majorFont/a:latin", NS)
            mn = fonts.find(".//a:minorFont/a:latin", NS)
            theme_major = mj.get("typeface") if mj is not None else None
            theme_minor = mn.get("typeface") if mn is not None else None
    except Exception:
        pass

    titles = [o["size"] for s in slides for o in s["objects"]
              if o.get("role") == "title" and o.get("size")]
    bodies = [o["size"] for s in slides for o in s["objects"]
              if o.get("role") == "body" and o.get("size")]
    brand_colors = [(o.get("color") or o.get("fill")) for s in slides for o in s["objects"]
                    if o.get("role") == "bottom-line" and (o.get("color") or o.get("fill"))]
    brand = Counter([c for c in brand_colors if c]).most_common(1)
    bgs = Counter([s["background"] for s in slides if s.get("background")]).most_common(1)

    return {
        "fonts": {"major": theme_major, "minor": theme_minor},
        "title_size": max(titles) if titles else None,
        "body_size": max(bodies) if bodies else None,
        "brand_line_color": brand[0][0] if brand else None,
        "background": bgs[0][0] if bgs else None,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_design_system.py <input.pptx> <output_dir>")
        sys.exit(1)
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    assets_dir = os.path.join(outdir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    prs = Presentation(src)
    W, H = int(prs.slide_width), int(prs.slide_height)
    aspect = "16:9" if abs(W / H - 16 / 9) < 0.02 else ("4:3" if abs(W / H - 4 / 3) < 0.02 else "%d:%d" % (W, H))

    slides = []
    for i, slide in enumerate(prs.slides):
        objs = []
        walk(slide.shapes, W, H, objs, assets_dir, i + 1)
        slides.append({"number": i + 1, "background": slide_background(slide), "objects": objs})

    extract = {
        "deck": {"w_emu": W, "h_emu": H, "aspect": aspect, "slides": len(slides)},
        "design_system": infer_design_system(prs, slides),
        "slides": slides,
    }
    out_path = os.path.join(outdir, "design-extract.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(extract, f, ensure_ascii=False, indent=2)

    print("Extracted %d slides -> %s" % (len(slides), out_path))
    for s in slides:
        roles = Counter(o["role"] for o in s["objects"])
        print("  Slide %d: %s" % (s["number"], dict(roles)))


if __name__ == "__main__":
    main()
