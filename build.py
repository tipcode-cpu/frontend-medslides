#!/usr/bin/env python3
"""
build.py — HTML Generator (pipeline stage 3 of 3).

   PPTX -> Extraction Engine -> Validation Engine -> [HTML Generator]

Consumes a VALIDATED extract/ folder (manifest.json + slides/*.json) and emits
the interactive HTML presentation. It reads NO PPTX and makes NO guesses — it
renders the structured slide JSON the Extraction Engine produced.

REFUSES to run unless manifest.validation.status == "passed" (pass --force to
override for debugging). Geometry is already in stage px; text metrics (fontSize,
indent, margins, spacing) are in points and scaled by manifest.deck.ptToPx.

Usage: python build.py <extract_dir> <out_dir> [--force]
"""
import json
import os
import shutil
import sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "engine")
BROWSER_IMG = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
BROWSER_VID = {".mp4", ".webm", ".ogg", ".ogv", ".m4v"}


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def box(o):
    return "left:%dpx;top:%dpx;width:%dpx;height:%dpx;" % (o["x"], o["y"], o["width"], o["height"])


def family(font):
    return ('"%s", var(--ds-font-sans)' % font) if font else "var(--ds-font-sans)"


def exists(extract_dir, rel):
    return bool(rel) and os.path.exists(os.path.join(extract_dir, rel.replace("/", os.sep)))


def missing_box(o, what):
    return ('<div class="fm-obj" style="%s"><div class="ds-missing">Missing %s: slide %s, %s</div></div>'
            % (box(o), what, o.get("_slide"), o["id"]))


# ---------- text ----------
def run_spans(runs, F, fallback_pt):
    out = []
    for r in runs:
        st = ""
        sz = r.get("fontSize") or fallback_pt
        if sz:
            st += "font-size:%gpx;" % (sz * F)
        st += "font-weight:%s;" % (r.get("fontWeight") or 400)
        if r.get("italic"):
            st += "font-style:italic;"
        if r.get("underline"):
            st += "text-decoration:underline;"
        if r.get("color"):
            st += "color:%s;" % r["color"]
        if r.get("fontFamily"):
            st += "font-family:%s;" % family(r["fontFamily"])
        out.append('<span style="%s">%s</span>' % (st, escape(r.get("text", "")).replace("\n", "<br>")))
    return "".join(out) or "&nbsp;"


def para_style(p, F):
    st = ""
    if p.get("align"):
        st += "text-align:%s;" % p["align"]
    if p.get("lineSpacingPct"):
        st += "line-height:%.3f;" % p["lineSpacingPct"]
    elif p.get("lineSpacingPts"):
        st += "line-height:%gpx;" % (p["lineSpacingPts"] * F)
    if p.get("spaceBeforePts") is not None:
        st += "margin-top:%gpx;" % (p["spaceBeforePts"] * F)
    if p.get("spaceAfterPts") is not None:
        st += "margin-bottom:%gpx;" % (p["spaceAfterPts"] * F)
    if p.get("marginLeft"):
        st += "padding-left:%gpx;" % (p["marginLeft"] * F)
    if p.get("indent"):
        st += "text-indent:%gpx;" % (p["indent"] * F)
    return st


def render_paras(paras, F, fallback_pt, bullets=True):
    html = []
    for p in paras:
        fb = max((r.get("fontSize") for r in p["runs"] if r.get("fontSize")), default=fallback_pt)
        bullet = ""
        if bullets and p.get("bullet") and p["runs"]:
            bf = ("font-family:%s;" % family(p["bulletFont"])) if p.get("bulletFont") else ""
            bullet = '<span class="ds-bullet" style="%s">%s </span>' % (bf, escape(p["bullet"]))
        html.append('<div class="ds-para" style="%s">%s%s</div>'
                    % (para_style(p, F), bullet, run_spans(p["runs"], F, fb)))
    return "".join(html)


# ---------- objects ----------
def render_object(o, F, ds, extract_dir):
    t, role = o.get("type"), o.get("role")

    if t == "video":
        ok = o.get("playable") and exists(extract_dir, o.get("src"))
        poster = (' poster="%s"' % escape(o["poster"])) if o.get("poster") else ""
        if ok:
            at = " controls" + (" loop" if o.get("loop") else "") + (" muted" if o.get("muted") else "") + \
                 (" autoplay playsinline" if o.get("autoplay") else "")
            inner = '<video class="ds-video"%s%s><source src="%s"></video>' % (at, poster, escape(o["src"]))
        elif exists(extract_dir, o.get("poster")):
            badge = "▶ video — %s (브라우저 재생 불가, 원본 보존)" % (o.get("format") or "?")
            inner = ('<div class="ds-video-fallback" style="background-image:url(\'%s\');">'
                     '<span class="ds-video-badge">%s</span></div>' % (escape(o["poster"]), escape(badge)))
        else:
            return missing_box(o, "video")
        return '<div class="fm-obj" style="%s">%s</div>' % (box(o), inner)

    if t == "image":
        if not exists(extract_dir, o.get("src")):
            return missing_box(o, "image")
        if role == "logo":
            inner = '<img class="ds-logo" src="%s" alt="logo">' % escape(o["src"])
        else:
            inner = '<figure class="ds-figure"><img class="ds-figure__img" src="%s" alt="figure"></figure>' % escape(o["src"])
        return '<div class="fm-obj" style="%s">%s</div>' % (box(o), inner)

    if t == "text":
        paras = o["paragraphs"]
        if role == "title":
            inner = '<h1 class="ds-title">%s</h1>' % render_paras(paras, F, ds.get("titleSizePt") or 40, bullets=False)
        elif role == "section-title":
            inner = '<h2 class="ds-section-title">%s</h2>' % render_paras(paras, F, 32, bullets=False)
        elif role in ("footer", "citation"):
            cls = "ds-citation" if role == "citation" else "ds-footer-inline"
            inner = '<div class="%s">%s</div>' % (cls, render_paras(paras, F, 13, bullets=False))
        elif role == "annotation":
            inner = '<div class="ds-annotation">%s</div>' % render_paras(paras, F, 18, bullets=False)
        else:
            inner = '<div class="ds-body">%s</div>' % render_paras(paras, F, 28, bullets=True)
        return '<div class="fm-obj" style="%s">%s</div>' % (box(o), inner)

    if t == "table":
        rows = o["rows"]
        head = "".join("<th>%s</th>" % escape(c) for c in rows[0]) if rows else ""
        body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % escape(c) for c in r) for r in rows[1:])
        return '<div class="fm-obj" style="%s"><table class="ds-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (box(o), head, body)

    if t == "chart":
        return ('<div class="fm-obj" style="%s"><div class="ds-missing">Unsupported: chart on slide %s</div></div>'
                % (box(o), o.get("_slide")))

    if t == "line" or (t == "shape" and role == "bottom-line"):
        color = o.get("color") or o.get("fill")
        return '<div class="ds-bottom-line" style="%s"></div>' % (("background:%s;" % color) if color else "")

    if t == "shape":
        return '<div class="fm-obj" style="%s"><div style="width:100%%;height:100%%;%s"></div></div>' % (
            box(o), ("background:%s;" % o["fill"]) if o.get("fill") else "")
    return ""


def chrome_layer(chrome):
    if not chrome:
        return ""
    parts = []
    bl = chrome.get("bottomLine")
    if bl:
        parts.append('<div class="ds-bottom-line" style="top:%dpx;background:%s;"></div>'
                     % (bl["y"], bl.get("color") or "#0070c0"))
    logo = chrome.get("logo")
    if logo and logo.get("src"):
        parts.append('<div class="ds-logo-box" style="%s"><img src="%s" alt="logo"></div>'
                     % (box(logo), escape(logo["src"])))
    return '<div class="ds-chrome">%s</div>' % "".join(parts)


def tokens_css(ds):
    lines = []
    fam = (ds.get("fonts") or {}).get("minor") or (ds.get("fonts") or {}).get("major")
    if fam:
        lines.append('--ds-font-sans: "%s", "Malgun Gothic", "맑은 고딕", "Noto Sans KR", system-ui, sans-serif;' % fam)
    if ds.get("titleColor"):
        lines.append("--ds-title-color: %s;" % ds["titleColor"])
    if ds.get("brandLineColor"):
        lines.append("--ds-brand-line: %s;" % ds["brandLineColor"])
    return ":root{%s}" % "".join(lines) if lines else ""


def render_slide(slide, F, ds, chrome, extract_dir):
    n = slide["slideNumber"]
    for o in slide["objects"]:
        o["_slide"] = n
    objs = "".join(render_object(o, F, ds, extract_dir) for o in slide["objects"])
    active = " is-active" if n == 1 else ""
    return '<section class="fm-slide%s" data-n="%d"><div class="ds-bg"></div>%s%s</section>' % (
        active, n, objs, chrome_layer(chrome))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if len(args) < 2:
        print("Usage: python build.py <extract_dir> <out_dir> [--force]")
        sys.exit(1)
    extract_dir, outdir = args[0], args[1]
    manifest = json.load(open(os.path.join(extract_dir, "manifest.json"), encoding="utf-8"))

    vstatus = (manifest.get("validation") or {}).get("status")
    if vstatus != "passed" and not force:
        print("REFUSING to generate HTML: validation status = %r." % vstatus)
        print("Run the Validation Engine first:  python validation/validate.py %s" % extract_dir)
        print("(or pass --force to override for debugging)")
        sys.exit(3)

    os.makedirs(outdir, exist_ok=True)
    F = manifest["deck"]["ptToPx"]
    ds, chrome = manifest["designSystem"], manifest.get("chrome")

    # copy assets
    src_assets = os.path.join(extract_dir, "assets")
    dst = os.path.join(outdir, "assets")
    if os.path.isdir(src_assets):
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src_assets, dst)

    slides = [json.load(open(os.path.join(extract_dir, rel), encoding="utf-8")) for rel in manifest["slides"]]
    css = "\n".join(read(os.path.join(ENGINE, f)) for f in ("stage.css", "components.css", "ui.css"))
    js = read(os.path.join(ENGINE, "interaction.js"))
    slides_html = "\n".join(render_slide(s, F, ds, chrome, outdir) for s in slides)

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

    with open(os.path.join(outdir, "presentation.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML generated -> %s/presentation.html  (%d slides, validation=%s)"
          % (outdir, len(slides), vstatus))


if __name__ == "__main__":
    main()
