#!/usr/bin/env python3
"""
build.py — Reconstruct a semantic, component-based HTML presentation from a
design-extract.json (produced by extractor/extract_design_system.py).

Layer 2: every PowerPoint object becomes an EDITABLE semantic HTML element
mapped to a reusable design-system component (Layer 1, components.css).
Nothing is flattened to an image. Geometry is preserved by absolute placement
on the fixed 1920x1080 stage.

Output: <outdir>/presentation.html  (+ copied assets/)
The engine CSS/JS is inlined so the folder is portable and offline (no CDN).

Usage:
    python build.py <design-extract.json> <outdir>
"""
import json
import os
import shutil
import sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "engine")
STAGE_W, STAGE_H = 1920, 1080


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def box(geo):
    """Fractions -> absolute stage px inline style."""
    return "left:%dpx;top:%dpx;width:%dpx;height:%dpx;" % (
        round(geo["xf"] * STAGE_W), round(geo["yf"] * STAGE_H),
        round(geo["wf"] * STAGE_W), round(geo["hf"] * STAGE_H))


def runs_html(paras):
    """Render paragraphs/runs preserving bold/italic/underline."""
    out = []
    for p in paras:
        spans = []
        for r in p["runs"]:
            cls = " ".join(c for c, on in (
                ("fm-run-b", r.get("b")), ("fm-run-i", r.get("i")), ("fm-run-u", r.get("u"))) if on)
            style = ""
            if r.get("size"):
                style += "font-size:%gpx;" % r["size"]
            if r.get("color"):
                style += "color:%s;" % r["color"]
            txt = escape(r["t"]).replace("\n", "<br>")
            attrs = (' class="%s"' % cls if cls else "") + (' style="%s"' % style if style else "")
            spans.append("<span%s>%s</span>" % (attrs, txt) if (cls or style) else txt)
        out.append("<p>%s</p>" % "".join(spans) if spans else "<p></p>")
    return "".join(out)


# ----------------------- role -> semantic component -----------------------
def render_object(o):
    role, kind, geo = o.get("role"), o.get("kind"), o["geo"]
    inner = ""

    if kind == "text":
        if role == "title":
            inner = '<h1 class="ds-title" contenteditable="false">%s</h1>' % runs_html(o["paras"])
        elif role == "section-title":
            inner = '<h2 class="ds-section-title">%s</h2>' % runs_html(o["paras"])
        elif role == "caption":
            inner = '<figcaption class="ds-caption">%s</figcaption>' % runs_html(o["paras"])
        elif role == "citation":
            inner = '<cite class="ds-citation">%s</cite>' % escape(o["plain"])
        elif role == "footer":
            inner = '<footer class="ds-footer-inline ds-citation">%s</footer>' % escape(o["plain"])
        else:
            inner = '<div class="ds-text">%s</div>' % runs_html(o["paras"])

    elif kind == "picture":
        if role == "logo":
            inner = '<img class="ds-logo" src="%s" alt="logo">' % escape(o.get("src") or "")
        else:  # figure
            inner = ('<figure class="ds-figure"><img class="ds-figure__img" src="%s" alt="figure"></figure>'
                     % escape(o.get("src") or ""))

    elif kind == "table":
        rows = o["rows"]
        head = "".join("<th>%s</th>" % escape(c) for c in rows[0]) if rows else ""
        body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % escape(c) for c in r) for r in rows[1:])
        inner = '<table class="ds-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (head, body)

    elif kind == "line" or (kind == "shape" and role == "bottom-line"):
        color = o.get("color") or o.get("fill")
        style = "background:%s;" % color if color else ""
        # Bottom line is a reusable chrome component; render as a full-width rule
        return '<div class="ds-bottom-line" style="%s"></div>' % style

    elif kind == "shape":
        style = "background:%s;" % o["fill"] if o.get("fill") else ""
        inner = '<div class="ds-shape" style="width:100%%;height:100%%;%s"></div>' % style

    return '<div class="fm-obj" style="%s">%s</div>' % (box(geo), inner)


def tokens_css(ds):
    """Override design tokens from the extracted design system (Layer 1)."""
    lines = []
    fonts = ds.get("fonts") or {}
    major = fonts.get("major")
    minor = fonts.get("minor")
    if minor or major:
        fam = minor or major
        lines.append('--ds-font-sans: "%s", "Malgun Gothic", "맑은 고딕", "Noto Sans KR", system-ui, sans-serif;' % fam)
    if ds.get("title_size"):
        lines.append("--ds-title-size: %gpx;" % ds["title_size"])
    if ds.get("body_size"):
        lines.append("--ds-body-size: %gpx;" % ds["body_size"])
    if ds.get("brand_line_color"):
        lines.append("--ds-brand-line: %s;" % ds["brand_line_color"])
        lines.append("--ds-brand: %s;" % ds["brand_line_color"])
    if ds.get("background"):
        lines.append("--ds-bg: %s;" % ds["background"])
    return ":root{%s}" % "".join(lines) if lines else ""


def render_slide(slide):
    bg = slide.get("background")
    bg_layer = '<div class="ds-bg" style="%s"></div>' % (("--ds-slide-bg:%s;" % bg) if bg else "")
    objs = "".join(render_object(o) for o in slide["objects"])
    active = " is-active" if slide["number"] == 1 else ""
    return '<section class="fm-slide%s" data-n="%d">%s%s</section>' % (active, slide["number"], bg_layer, objs)


def main():
    if len(sys.argv) < 3:
        print("Usage: python build.py <design-extract.json> <outdir>")
        sys.exit(1)
    extract_path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    data = json.load(open(extract_path, encoding="utf-8"))
    slides = data["slides"]
    ds = data.get("design_system", {})

    # Copy assets next to the output (relative paths, offline).
    src_assets = os.path.join(os.path.dirname(os.path.abspath(extract_path)), "assets")
    if os.path.isdir(src_assets):
        dst_assets = os.path.join(outdir, "assets")
        if os.path.abspath(src_assets) != os.path.abspath(dst_assets):
            shutil.rmtree(dst_assets, ignore_errors=True)
            shutil.copytree(src_assets, dst_assets)

    css = "\n".join(read(os.path.join(ENGINE, f)) for f in ("stage.css", "components.css", "ui.css"))
    js = read(os.path.join(ENGINE, "interaction.js"))
    slides_html = "\n".join(render_slide(s) for s in slides)

    html = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>frontend-medslides</title>
<style>
{css}
{tokens}
</style>
</head>
<body>
<div class="fm-viewport">
  <div class="fm-stage">
{slides}
  </div>
</div>
<div id="fm-indicator">1 / {n}</div>
<div class="fm-controls">
  <button id="fm-prev" title="Previous (←)">‹</button>
  <button id="fm-next" title="Next (→)">›</button>
  <button id="fm-full" title="Fullscreen (F)">⛶</button>
</div>
<script>
{js}
</script>
</body>
</html>""".format(css=css, tokens=tokens_css(ds),
                  slides=slides_html, n=len(slides), js=js)

    out = os.path.join(outdir, "presentation.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("Built %d slides -> %s" % (len(slides), out))


if __name__ == "__main__":
    main()
