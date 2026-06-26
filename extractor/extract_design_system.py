#!/usr/bin/env python3
"""
extract_design_system.py — Layer 1 (design system + chrome) + Layer 2 (objects)
                           + robust image pipeline + media (video) engine.

Preserves what medical slides depend on and what flat dumps lose:
  * geometry, text runs (bold/italic/underline/size/color), tables
  * MASTER/LAYOUT chrome (institutional logo, bottom line, footer, title style)
    — slide.shapes does NOT include these, so they are extracted separately
  * grouped shapes (recursed), lines
  * ALL images incl. high-res; EMF/WMF/WDP rasterized; originals + display copies
  * embedded/linked VIDEO -> reported, extracted, posters, never silently omitted

Outputs:
  <out>/design-extract.json
  <out>/assets/figures/{originals,display}/ , assets/logos/ , assets/media/{originals,posters}/
  <out>/assets/extraction-report.json    (every image + video, with sizes/dims/failures)

Usage: python extract_design_system.py <input.pptx> <output_dir>
Requires: python-pptx, pillow
"""
import json
import os
import shutil
import sys
from collections import Counter

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS = {"a": A[1:-1], "p": P[1:-1], "r": R[1:-1]}

EMU_PER_PT = 12700
RASTER_OK = {"png", "jpg", "jpeg", "gif", "webp"}
NEED_RASTER = {"wmf", "emf", "wdp", "tiff", "tif", "bmp"}
DISPLAY_MAXDIM = 2600          # downscale display copy beyond this (keeps readability)
DISPLAY_BIG_BYTES = 6_000_000  # also make a display copy above this size
VIDEO_EXT = {"mp4", "m4v", "webm", "ogg", "ogv", "mov", "wmv", "avi", "mpg", "mpeg", "mkv"}
BROWSER_VIDEO = {"mp4", "m4v", "webm", "ogg", "ogv"}

REPORT = {"images": [], "videos": [], "logos": [], "failures": []}


# ----------------------------- color / geometry -----------------------------
def rgb_or_none(color):
    try:
        return ("#" + str(color.rgb).lower()) if color is not None else None
    except Exception:
        return None


def frac(left, top, width, height, W, H):
    return {"xf": (left or 0) / W, "yf": (top or 0) / H,
            "wf": (width or 0) / W, "hf": (height or 0) / H}


def shape_frac(sh, W, H):
    try:
        return frac(int(sh.left or 0), int(sh.top or 0), int(sh.width or 0), int(sh.height or 0), W, H)
    except Exception:
        return {"xf": 0, "yf": 0, "wf": 0, "hf": 0}


def group_child_transform(group):
    try:
        xfrm = group._element.find(".//a:xfrm", NS)
        off, ext = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
        choff, chext = xfrm.find("a:chOff", NS), xfrm.find("a:chExt", NS)
        ox, oy, ex, ey = int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy"))
        cox, coy, cex, cey = int(choff.get("x")), int(choff.get("y")), int(chext.get("cx")), int(chext.get("cy"))
        sx, sy = (ex / cex if cex else 1.0), (ey / cey if cey else 1.0)
        return lambda l, t, w, h: (ox + (l - cox) * sx, oy + (t - coy) * sy, w * sx, h * sy)
    except Exception:
        return lambda l, t, w, h: (l, t, w, h)


# ----------------------------- text -----------------------------
def extract_text(tf):
    paras = []
    for p in tf.paragraphs:
        psize = p.font.size.pt if p.font.size is not None else None
        runs = []
        for r in p.runs:
            f = r.font
            runs.append({"t": r.text, "b": bool(f.bold), "i": bool(f.italic),
                         "u": bool(f.underline),
                         "size": float(f.size.pt) if f.size is not None else psize,
                         "color": rgb_or_none(f.color) if r.text else None})
        paras.append({"level": p.level or 0,
                      "align": str(p.alignment) if p.alignment else None, "runs": runs})
    return paras


def para_plain(paras):
    return "\n".join("".join(r["t"] for r in p["runs"]) for p in paras).strip()


def dominant_size(paras):
    sizes = [r["size"] for p in paras for r in p["runs"] if r["size"]]
    return max(sizes) if sizes else None


# ----------------------------- image pipeline -----------------------------
def _ensure(d):
    os.makedirs(d, exist_ok=True)
    return d


def save_image(blob, ext, slide_no, idx, assets_dir, kind="figure"):
    """Save original (always) + a browser-ready display copy when needed.
    Returns a record dict (also appended to REPORT). Never raises."""
    ext = (ext or "bin").lower()
    base = "s%02d_%s%02d" % (slide_no, "img" if kind == "figure" else kind, idx)
    orig_dir = _ensure(os.path.join(assets_dir, "figures", "originals"))
    disp_dir = _ensure(os.path.join(assets_dir, "figures", "display"))
    orig_name = base + "." + ext
    orig_path = os.path.join(orig_dir, orig_name)
    with open(orig_path, "wb") as f:
        f.write(blob)
    nbytes = len(blob)
    rec = {"slide": slide_no, "kind": kind, "format": ext, "original_bytes": nbytes,
           "original_path": "assets/figures/originals/" + orig_name,
           "display_path": "assets/figures/originals/" + orig_name,
           "width": None, "height": None, "resized": False, "note": ""}

    needs_conv = ext in NEED_RASTER
    too_big = nbytes > DISPLAY_BIG_BYTES
    if _HAS_PIL and (needs_conv or too_big):
        try:
            im = Image.open(orig_path)
            im.load()
            rec["width"], rec["height"] = im.size
            out_im, fmt = im, ("png" if (im.mode in ("RGBA", "P", "LA") or needs_conv) else "jpg")
            if max(im.size) > DISPLAY_MAXDIM:               # downscale, never aggressive
                ratio = DISPLAY_MAXDIM / max(im.size)
                out_im = im.resize((int(im.width * ratio), int(im.height * ratio)), Image.LANCZOS)
                rec["resized"] = True
            disp_name = base + "." + fmt
            disp_path = os.path.join(disp_dir, disp_name)
            if fmt == "jpg":
                out_im.convert("RGB").save(disp_path, quality=92)
            else:
                out_im.save(disp_path)
            rec["display_path"] = "assets/figures/display/" + disp_name
            rec["note"] = ("rasterized %s->%s" % (ext, fmt)) if needs_conv else "optimized display copy"
        except Exception as e:
            rec["note"] = "display-copy FAILED (%s); original kept" % type(e).__name__
            REPORT["failures"].append({"slide": slide_no, "what": orig_name, "error": str(e)})
    elif _HAS_PIL:
        try:
            with Image.open(orig_path) as im:
                rec["width"], rec["height"] = im.size
        except Exception:
            pass
    REPORT["images"].append(rec)
    return rec


# ----------------------------- media (video) engine -----------------------------
def video_attrs(pic_el, slide_el):
    """Best-effort loop/mute/autoplay. PPTX stores play settings in the timing
    tree (complex); default to medical-clip sensible values and note it."""
    loop = autoplay = mute = None
    try:
        xml = slide_el  # search slide timing for this media's loop/autoplay
        for ctn in slide_el.iter(P + "cTn"):
            if ctn.get("repeatCount") == "indefinite":
                loop = True
        # videoFile/extLst rarely carries explicit mute; leave None -> default
    except Exception:
        pass
    return loop, autoplay, mute


def handle_video(pic, slide, slide_no, idx, assets_dir):
    """Detect/extract one video pic. Returns object record or None. Never silent."""
    vf = pic.find(".//" + A + "videoFile")
    if vf is None:
        return None
    rid = vf.get(R + "link") or vf.get(R + "embed")
    rel = slide.part.rels.get(rid) if rid else None
    media_dir = _ensure(os.path.join(assets_dir, "media", "originals"))
    poster_dir = _ensure(os.path.join(assets_dir, "media", "posters"))

    rec = {"slide": slide_no, "linked": False, "format": None,
           "original_path": None, "display_path": None, "poster_path": None,
           "playable": False, "loop": True, "muted": True, "autoplay": False, "note": ""}

    # extract media bytes (embedded) or record link (external)
    src_rel = None
    try:
        if rel is None:
            rec["note"] = "video relationship missing"
        elif rel.is_external:
            rec["linked"] = True
            tgt = rel.target_ref
            rec["note"] = "LINKED (external): " + tgt
            if os.path.exists(tgt):
                ext = tgt.rsplit(".", 1)[-1].lower()
                name = "s%02d_vid%02d.%s" % (slide_no, idx, ext)
                shutil.copyfile(tgt, os.path.join(media_dir, name))
                src_rel = "assets/media/originals/" + name
                rec["format"] = ext
            else:
                REPORT["failures"].append({"slide": slide_no, "what": "linked video",
                                           "error": "external file not found: " + tgt})
        else:
            part = rel.target_part
            ext = (part.partname.ext or "bin").lower()
            name = "s%02d_vid%02d.%s" % (slide_no, idx, ext)
            with open(os.path.join(media_dir, name), "wb") as f:
                f.write(part.blob)
            src_rel = "assets/media/originals/" + name
            rec["format"] = ext
    except Exception as e:
        rec["note"] = "extraction FAILED: " + type(e).__name__
        REPORT["failures"].append({"slide": slide_no, "what": "video", "error": str(e)})

    rec["original_path"] = src_rel
    if rec["format"] in BROWSER_VIDEO and src_rel:
        rec["playable"] = True
        rec["display_path"] = src_rel
    elif src_rel:
        rec["playable"] = False
        rec["note"] = (rec["note"] + " | " if rec["note"] else "") + \
            "format '%s' not browser-playable (no transcoder); showing poster" % rec["format"]

    # poster frame from the pic's display image (blipFill)
    try:
        blip = pic.find(".//" + A + "blip")
        prid = blip.get(R + "embed") if blip is not None else None
        prel = slide.part.rels.get(prid) if prid else None
        if prel is not None and not prel.is_external:
            pext = (prel.target_part.partname.ext or "png").lower()
            if pext in NEED_RASTER and _HAS_PIL:
                pext2 = "png"
            else:
                pext2 = pext
            pname = "s%02d_poster%02d.%s" % (slide_no, idx, pext2)
            ppath = os.path.join(poster_dir, pname)
            if pext in NEED_RASTER and _HAS_PIL:
                im = Image.open(__import__("io").BytesIO(prel.target_part.blob)); im.load(); im.save(ppath)
            else:
                with open(ppath, "wb") as f:
                    f.write(prel.target_part.blob)
            rec["poster_path"] = "assets/media/posters/" + pname
    except Exception:
        pass

    lo, ap, mu = video_attrs(pic, slide.element)
    if lo is not None: rec["loop"] = lo
    if ap is not None: rec["autoplay"] = ap
    if mu is not None: rec["muted"] = mu

    REPORT["videos"].append(rec)
    return rec


# ----------------------------- classification -----------------------------
def classify(kind, role_hint, geo, text, fsize):
    if role_hint:
        return role_hint
    yf, xf, wf, hf = geo["yf"], geo["xf"], geo["wf"], geo["hf"]
    if kind == "picture":
        return "logo" if (wf < 0.18 and hf < 0.18 and yf < 0.14) else "figure"
    if kind == "line":
        return "bottom-line" if yf > 0.85 else "rule"
    if kind == "table":
        return "table"
    if kind == "text":
        low, tiny = yf > 0.86, (fsize or 99) <= 16
        if low and tiny:
            if any(c.isdigit() for c in text) and (";" in text or ":" in text or "et al" in text.lower()):
                return "citation"
            return "footer"
        return "caption" if tiny else "body"
    return "generic"


# ----------------------------- shape walk -----------------------------
def walk(shapes, W, H, out, assets_dir, slide, slide_no, abs_xform=None, counters=None):
    counters = counters if counters is not None else {"img": 0, "vid": 0}
    for sh in shapes:
        st = getattr(sh, "shape_type", None)

        if st == MSO_SHAPE_TYPE.GROUP:
            walk(sh.shapes, W, H, out, assets_dir, slide, slide_no,
                 group_child_transform(sh), counters)
            continue

        l, t, w, h = (int(sh.left or 0), int(sh.top or 0), int(sh.width or 0), int(sh.height or 0)) \
            if _has_geo(sh) else (0, 0, 0, 0)
        if abs_xform:
            l, t, w, h = abs_xform(l, t, w, h)
        geo = frac(l, t, w, h, W, H)

        # ---- VIDEO (a p:pic carrying a:videoFile) — handle before picture ----
        if sh._element.tag == P + "pic" and sh._element.find(".//" + A + "videoFile") is not None:
            counters["vid"] += 1
            rec = handle_video(sh._element, slide, slide_no, counters["vid"], assets_dir)
            if rec is not None:
                out.append({"kind": "video", "role": "video", "geo": geo, "media": rec})
            continue

        role_hint = None
        try:
            if sh.is_placeholder:
                ph = str(sh.placeholder_format.type)
                if "SUBTITLE" in ph:
                    role_hint = "section-title"
                elif "TITLE" in ph:
                    role_hint = "title"
        except Exception:
            pass

        if st == MSO_SHAPE_TYPE.PICTURE:
            counters["img"] += 1
            try:
                img = sh.image
                rec = save_image(img.blob, img.ext, slide_no, counters["img"], assets_dir)
                src = rec["display_path"]
            except Exception as e:
                src = None
                REPORT["failures"].append({"slide": slide_no, "what": "picture", "error": str(e)})
            out.append({"kind": "picture", "role": classify("picture", role_hint, geo, "", None),
                        "geo": geo, "src": src})
            continue

        if getattr(sh, "has_table", False):
            rows = [[c.text for c in row.cells] for row in sh.table.rows]
            out.append({"kind": "table", "role": "table", "geo": geo, "rows": rows})
            continue

        if st == MSO_SHAPE_TYPE.LINE or sh.__class__.__name__ == "Connector":
            color = None
            try:
                color = rgb_or_none(sh.line.color)
            except Exception:
                pass
            out.append({"kind": "line", "role": classify("line", None, geo, "", None),
                        "geo": geo, "color": color})
            continue

        if getattr(sh, "has_text_frame", False) and sh.text_frame.text.strip():
            paras = extract_text(sh.text_frame)
            text = para_plain(paras)
            fsize = dominant_size(paras)
            out.append({"kind": "text", "role": classify("text", role_hint, geo, text, fsize),
                        "geo": geo, "paras": paras, "plain": text, "size": fsize,
                        "align": paras[0]["align"] if paras else None})
            continue

        if st == MSO_SHAPE_TYPE.AUTO_SHAPE:
            fill = None
            try:
                fill = rgb_or_none(sh.fill.fore_color)
            except Exception:
                pass
            role = "bottom-line" if (geo["yf"] > 0.85 and geo["hf"] < 0.03) else "generic"
            out.append({"kind": "shape", "role": role, "geo": geo, "fill": fill})


def _has_geo(sh):
    try:
        return sh.left is not None
    except Exception:
        return False


# ----------------------------- chrome (master/layout) -----------------------------
def line_color(sh):
    el = sh._element
    srgb = el.find(".//a:ln//a:srgbClr", NS)
    if srgb is not None:
        return "#" + srgb.get("val").lower()
    return None


def master_title_style(master):
    ts = master.element.find(".//p:txStyles", NS)
    style = {"size_pt": None, "bold": None, "color": None}
    try:
        title = ts.find(".//p:titleStyle", NS)
        lvl = next(iter(title), None)
        df = lvl.find("a:defRPr", NS)
        if df is not None:
            style["size_pt"] = int(df.get("sz")) / 100.0 if df.get("sz") else None
            style["bold"] = df.get("b") == "1"
            srgb = df.find(".//a:srgbClr", NS)
            style["color"] = "#" + srgb.get("val").lower() if srgb is not None else None
    except Exception:
        pass
    return style


def extract_chrome(prs, W, H, assets_dir):
    """Pull institution chrome from master+layout: logo, bottom line, footer area,
    title style. Rendered on every slide by the builder."""
    chrome = {"logo": None, "bottom_line": None, "footer_area": None, "title_style": None}
    logo_dir = _ensure(os.path.join(assets_dir, "logos"))
    # Use the first master + a representative content layout
    master = prs.slide_masters[0]
    sources = list(master.shapes)
    for lay in master.slide_layouts:
        sources += [(s, lay) for s in lay.shapes]

    for item in master.shapes:
        st = getattr(item, "shape_type", None)
        if st == MSO_SHAPE_TYPE.PICTURE and chrome["logo"] is None:
            try:
                img = item.image
                name = "logo." + img.ext
                with open(os.path.join(logo_dir, name), "wb") as f:
                    f.write(img.blob)
                chrome["logo"] = {"src": "assets/logos/" + name, "geo": shape_frac(item, W, H)}
                REPORT["logos"].append({"src": "assets/logos/" + name, "native": list(img.size)})
            except Exception as e:
                REPORT["failures"].append({"slide": "master", "what": "logo", "error": str(e)})
        if (st == MSO_SHAPE_TYPE.LINE or item.__class__.__name__ == "Connector") and chrome["bottom_line"] is None:
            g = shape_frac(item, W, H)
            if g["yf"] > 0.8:
                chrome["bottom_line"] = {"geo": g, "color": line_color(item) or "#0070c0"}

    # footer placeholder area from a content layout
    for lay in master.slide_layouts:
        for ph in lay.placeholders:
            try:
                if "TITLE" not in str(ph.placeholder_format.type):
                    g = shape_frac(ph, W, H)
                    if g["yf"] > 0.9 and chrome["footer_area"] is None:
                        chrome["footer_area"] = {"geo": g}
            except Exception:
                pass
    chrome["title_style"] = master_title_style(master)
    return chrome


# ----------------------------- design system -----------------------------
def infer_design_system(prs, slides, chrome):
    theme_major = theme_minor = None
    try:
        fonts = prs.slide_masters[0].element.find(".//a:fontScheme", NS)
        mj = fonts.find(".//a:majorFont/a:latin", NS)
        mn = fonts.find(".//a:minorFont/a:latin", NS)
        theme_major = mj.get("typeface") if mj is not None else None
        theme_minor = mn.get("typeface") if mn is not None else None
    except Exception:
        pass
    bodies = [o["size"] for s in slides for o in s["objects"] if o.get("role") == "body" and o.get("size")]
    ts = chrome.get("title_style") or {}
    return {
        "fonts": {"major": theme_major, "minor": theme_minor},
        "title_size_pt": ts.get("size_pt"),
        # master title color is often a theme ref (tx2); use sampled navy as fallback
        "title_color": ts.get("color") if (ts.get("color") and ts.get("color") != "#000000") else "#1f3864",
        "body_size_pt": max(bodies) if bodies else None,
        "brand_line_color": (chrome.get("bottom_line") or {}).get("color"),
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_design_system.py <input.pptx> <output_dir>")
        sys.exit(1)
    src, outdir = sys.argv[1], sys.argv[2]
    assets_dir = _ensure(os.path.join(outdir, "assets"))
    prs = Presentation(src)
    W, H = int(prs.slide_width), int(prs.slide_height)
    aspect = "16:9" if abs(W / H - 16 / 9) < 0.02 else ("4:3" if abs(W / H - 4 / 3) < 0.02 else "%d:%d" % (W, H))

    chrome = extract_chrome(prs, W, H, assets_dir)

    slides = []
    for i, slide in enumerate(prs.slides):
        objs = []
        walk(slide.shapes, W, H, objs, assets_dir, slide, i + 1)
        slides.append({"number": i + 1, "background": None, "objects": objs})

    extract = {
        "deck": {"w_emu": W, "h_emu": H, "w_pt": W / EMU_PER_PT, "aspect": aspect, "slides": len(slides)},
        "chrome": chrome,
        "design_system": infer_design_system(prs, slides, chrome),
        "slides": slides,
    }
    with open(os.path.join(outdir, "design-extract.json"), "w", encoding="utf-8") as f:
        json.dump(extract, f, ensure_ascii=False, indent=2)
    with open(os.path.join(assets_dir, "extraction-report.json"), "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=2)

    print("Extracted %d slides." % len(slides))
    print("  chrome: logo=%s line=%s" % (bool(chrome["logo"]), bool(chrome["bottom_line"])))
    print("  images: %d  videos: %d  failures: %d"
          % (len(REPORT["images"]), len(REPORT["videos"]), len(REPORT["failures"])))
    for v in REPORT["videos"]:
        print("  VIDEO slide %d  fmt=%s playable=%s  %s"
              % (v["slide"], v["format"], v["playable"], v["note"]))
    for fl in REPORT["failures"]:
        print("  FAILURE: slide %s %s -> %s" % (fl["slide"], fl["what"], fl["error"]))


if __name__ == "__main__":
    main()
