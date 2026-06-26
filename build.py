#!/usr/bin/env python3
"""
build.py — Reconstruct a semantic, component-based HTML presentation from a
design-extract.json (extractor/extract_design_system.py).

Layer 1 (design system) -> CSS tokens + SHARED CHROME auto-inserted on every
slide (white bg, bottom blue line, YUMC logo, footer area).
Layer 2 -> every object becomes an editable semantic component (no flattening),
positioned on the fixed 1920x1080 stage. Font sizes are scaled pt->stage px.
Videos render as <video> (Media Engine); unplayable formats show a poster +
explicit badge (never silently omitted).

Usage: python build.py <design-extract.json> <outdir>
"""
import json
import os
import shutil
import sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "engine")
STAGE_W, STAGE_H = 1920, 1080
ALIGN = {"PP_ALIGN.CENTER (2)": "center", "CENTER (2)": "center",
         "PP_ALIGN.RIGHT (3)": "right", "RIGHT (3)": "right",
         "PP_ALIGN.LEFT (1)": "left", "LEFT (1)": "left"}


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def box(geo):
    return "left:%dpx;top:%dpx;width:%dpx;height:%dpx;" % (
        round(geo["xf"] * STAGE_W), round(geo["yf"] * STAGE_H),
        round(geo["wf"] * STAGE_W), round(geo["hf"] * STAGE_H))


def runs_html(paras, factor, default_pt=None):
    out = []
    for p in paras:
        spans = []
        for r in p["runs"]:
            cls = " ".join(c for c, on in (("fm-run-b", r.get("b")),
                          ("fm-run-i", r.get("i")), ("fm-run-u", r.get("u"))) if on)
            style = ""
            sz = r.get("size") or default_pt
            if sz:
                style += "font-size:%gpx;" % (sz * factor)
            if r.get("color"):
                style += "color:%s;" % r["color"]
            txt = escape(r["t"]).replace("\n", "<br>")
            attrs = (' class="%s"' % cls if cls else "") + (' style="%s"' % style if style else "")
            spans.append("<span%s>%s</span>" % (attrs, txt) if (cls or style) else txt)
        out.append("<p>%s</p>" % "".join(spans) if spans else "<p></p>")
    return "".join(out)


def render_object(o, factor, ds):
    role, kind, geo = o.get("role"), o.get("kind"), o["geo"]
    align = ALIGN.get(str(o.get("align")), None)

    if kind == "video":
        m = o["media"]
        poster = (' poster="%s"' % escape(m["poster_path"])) if m.get("poster_path") else ""
        if m.get("playable") and m.get("display_path"):
            attrs = " controls"
            if m.get("loop"): attrs += " loop"
            if m.get("muted"): attrs += " muted"
            if m.get("autoplay"): attrs += " autoplay playsinline"
            inner = ('<video class="ds-video"%s%s><source src="%s"></video>'
                     % (attrs, poster, escape(m["display_path"])))
        else:
            bg = ("background-image:url('%s');" % escape(m["poster_path"])) if m.get("poster_path") else ""
            badge = "▶ video — %s (브라우저 재생 불가, 원본 보존)" % (m.get("format") or "?")
            inner = ('<div class="ds-video-fallback" style="%s"><span class="ds-video-badge">%s</span></div>'
                     % (bg, escape(badge)))
        return '<div class="fm-obj" style="%s">%s</div>' % (box(geo), inner)

    inner = ""
    if kind == "text":
        if role == "title":
            st = ('text-align:%s;' % align) if align else ""
            tpt = ds.get("title_size_pt")
            inner = '<h1 class="ds-title" style="%s">%s</h1>' % (st, runs_html(o["paras"], factor, tpt))
        elif role == "section-title":
            inner = '<h2 class="ds-section-title">%s</h2>' % runs_html(o["paras"], factor)
        elif role == "caption":
            inner = '<figcaption class="ds-caption">%s</figcaption>' % runs_html(o["paras"], factor)
        elif role == "citation":
            inner = '<cite class="ds-citation">%s</cite>' % escape(o["plain"])
        elif role == "footer":
            inner = '<footer class="ds-footer-inline ds-citation">%s</footer>' % escape(o["plain"])
        else:
            st = ('text-align:%s;' % align) if align else ""
            inner = '<div class="ds-text" style="%s">%s</div>' % (st, runs_html(o["paras"], factor))
    elif kind == "picture":
        if role == "logo":
            inner = '<img class="ds-logo" src="%s" alt="logo">' % escape(o.get("src") or "")
        else:
            inner = ('<figure class="ds-figure"><img class="ds-figure__img" src="%s" alt="figure"></figure>'
                     % escape(o.get("src") or ""))
    elif kind == "table":
        rows = o["rows"]
        head = "".join("<th>%s</th>" % escape(c) for c in rows[0]) if rows else ""
        body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % escape(c) for c in r) for r in rows[1:])
        inner = '<table class="ds-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (head, body)
    elif kind == "line" or (kind == "shape" and role == "bottom-line"):
        color = o.get("color") or o.get("fill")
        return '<div class="ds-bottom-line" style="%s"></div>' % (("background:%s;" % color) if color else "")
    elif kind == "shape":
        return '<div class="fm-obj" style="%s"><div style="width:100%%;height:100%%;%s"></div></div>' % (
            box(geo), ("background:%s;" % o["fill"]) if o.get("fill") else "")

    return '<div class="fm-obj" style="%s">%s</div>' % (box(geo), inner)


def chrome_layer(chrome):
    """Shared chrome inserted on EVERY slide: bottom blue line + logo.
    Background and footer-text come from tokens / the slide's own objects."""
    if not chrome:
        return ""
    parts = []
    bl = chrome.get("bottom_line")
    if bl:
        g = bl["geo"]
        y = round(g["yf"] * STAGE_H)
        parts.append('<div class="ds-bottom-line" style="top:%dpx;background:%s;"></div>'
                     % (y, bl.get("color") or "#0070c0"))
    logo = chrome.get("logo")
    if logo and logo.get("src"):
        parts.append('<div class="ds-logo-box" style="%s"><img src="%s" alt="YUMC"></div>'
                     % (box(logo["geo"]), escape(logo["src"])))
    return '<div class="ds-chrome">%s</div>' % "".join(parts)


def tokens_css(ds):
    lines = []
    fonts = ds.get("fonts") or {}
    fam = fonts.get("minor") or fonts.get("major")
    if fam:
        lines.append('--ds-font-sans: "%s", "Malgun Gothic", "맑은 고딕", "Noto Sans KR", system-ui, sans-serif;' % fam)
    if ds.get("title_color"):
        lines.append("--ds-title-color: %s;" % ds["title_color"])
    if ds.get("brand_line_color"):
        lines.append("--ds-brand-line: %s;" % ds["brand_line_color"])
    if ds.get("body_size_pt"):
        lines.append("--ds-body-size: %gpx;" % (ds["body_size_pt"]))  # base; runs scale inline
    return ":root{%s}" % "".join(lines) if lines else ""


def render_slide(slide, factor, ds, chrome):
    bg = '<div class="ds-bg"></div>'
    objs = "".join(render_object(o, factor, ds) for o in slide["objects"])
    active = " is-active" if slide["number"] == 1 else ""
    return '<section class="fm-slide%s" data-n="%d">%s%s%s</section>' % (
        active, slide["number"], bg, objs, chrome_layer(chrome))


def main():
    if len(sys.argv) < 3:
        print("Usage: python build.py <design-extract.json> <outdir>")
        sys.exit(1)
    extract_path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    data = json.load(open(extract_path, encoding="utf-8"))
    slides, ds, chrome = data["slides"], data.get("design_system", {}), data.get("chrome")
    w_pt = data["deck"].get("w_pt") or 960.0
    factor = STAGE_W / w_pt          # pt -> stage px (e.g. 1920/960 = 2.0)

    # copy assets tree (figures/display, logos, media, posters)
    src_assets = os.path.join(os.path.dirname(os.path.abspath(extract_path)), "assets")
    if os.path.isdir(src_assets):
        dst = os.path.join(outdir, "assets")
        if os.path.abspath(src_assets) != os.path.abspath(dst):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src_assets, dst)

    css = "\n".join(read(os.path.join(ENGINE, f)) for f in ("stage.css", "components.css", "ui.css"))
    js = read(os.path.join(ENGINE, "interaction.js"))
    slides_html = "\n".join(render_slide(s, factor, ds, chrome) for s in slides)

    html = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>frontend-medslides</title>
<style>
{css}
{tokens}
</style></head>
<body>
<div class="fm-viewport"><div class="fm-stage">
{slides}
</div></div>
<div id="fm-indicator">1 / {n}</div>
<div class="fm-controls">
  <button id="fm-prev" title="Previous (←)">‹</button>
  <button id="fm-next" title="Next (→)">›</button>
  <button id="fm-full" title="Fullscreen (F)">⛶</button>
</div>
<script>
{js}
</script>
</body></html>""".format(css=css, tokens=tokens_css(ds), slides=slides_html, n=len(slides), js=js)

    out = os.path.join(outdir, "presentation.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("Built %d slides -> %s  (pt->px factor %.3f)" % (len(slides), out, factor))


if __name__ == "__main__":
    main()
