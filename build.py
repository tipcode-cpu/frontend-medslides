#!/usr/bin/env python3
"""
build.py — Reconstruct semantic, component-based HTML from design-extract.json.

Text fidelity: each paragraph is rendered with its RESOLVED properties (per-run
font-size/weight/color/family, bullet char+indent, line spacing, paragraph
spacing, alignment) — NOT one global body style. Font sizes are pt -> stage px
(factor = 1920 / slide_w_pt; for 16:9 PPT that is exactly 2.0 — a real unit
conversion, not arbitrary doubling).

Asset reliability (P0): every <img>/<video> source is VALIDATED (exists, non-zero,
browser-loadable). Invalid -> a visible "Missing image" placeholder, never a
broken <img>. A per-asset asset-report.json is written.

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
BROWSER_IMG = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
BROWSER_VID = {".mp4", ".webm", ".ogg", ".ogv", ".m4v"}
ASSET_REPORT = []


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def box(geo):
    return "left:%dpx;top:%dpx;width:%dpx;height:%dpx;" % (
        round(geo["xf"] * STAGE_W), round(geo["yf"] * STAGE_H),
        round(geo["wf"] * STAGE_W), round(geo["hf"] * STAGE_H))


# ----------------------------- asset validation (P0) -----------------------------
def validate_asset(src, outdir, slide, obj_id, kind):
    rec = {"slide": slide, "object_id": obj_id, "source_path": src, "exists": False,
           "file_size": 0, "dimensions": None, "status": "missing", "error": ""}
    if not src:
        rec["error"] = "no source extracted from PPTX"
        ASSET_REPORT.append(rec)
        return False
    path = os.path.join(outdir, src.replace("/", os.sep))
    if not os.path.exists(path):
        rec["error"] = "file does not exist"
        ASSET_REPORT.append(rec)
        return False
    rec["exists"] = True
    rec["file_size"] = os.path.getsize(path)
    if rec["file_size"] == 0:
        rec["status"], rec["error"] = "empty", "zero bytes"
        ASSET_REPORT.append(rec)
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext not in (BROWSER_VID if kind == "video" else BROWSER_IMG):
        rec["status"], rec["error"] = "unloadable", "format %s not browser-loadable" % ext
        ASSET_REPORT.append(rec)
        return False
    if kind == "image":
        try:
            from PIL import Image
            with Image.open(path) as im:
                rec["dimensions"] = list(im.size)
        except Exception:
            pass
    rec["status"] = "ok"
    ASSET_REPORT.append(rec)
    return True


def missing_box(geo, slide, obj_id, what):
    return ('<div class="fm-obj" style="%s"><div class="ds-missing">'
            'Missing %s: slide %s, object %s</div></div>'
            % (box(geo), what, slide, obj_id))


# ----------------------------- text rendering -----------------------------
def family(font):
    return ('"%s", var(--ds-font-sans)' % font) if font else "var(--ds-font-sans)"


def run_spans(runs, factor, fallback_pt):
    out = []
    for r in runs:
        st = ""
        sz = r.get("size") or fallback_pt
        if sz:
            st += "font-size:%gpx;" % (sz * factor)
        st += "font-weight:%s;" % ("700" if r.get("bold") else "400")
        if r.get("italic"):
            st += "font-style:italic;"
        if r.get("underline"):
            st += "text-decoration:underline;"
        if r.get("color"):
            st += "color:%s;" % r["color"]
        if r.get("font"):
            st += "font-family:%s;" % family(r["font"])
        txt = escape(r["t"]).replace("\n", "<br>")
        out.append('<span style="%s">%s</span>' % (st, txt))
    return "".join(out) or "&nbsp;"


def para_style(p, factor):
    st = ""
    if p.get("align"):
        st += "text-align:%s;" % p["align"]
    if p.get("line_pct"):
        st += "line-height:%.3f;" % p["line_pct"]
    elif p.get("line_pts"):
        st += "line-height:%gpx;" % (p["line_pts"] * factor)
    if p.get("before_pts") is not None:
        st += "margin-top:%gpx;" % (p["before_pts"] * factor)
    if p.get("after_pts") is not None:
        st += "margin-bottom:%gpx;" % (p["after_pts"] * factor)
    marL = (p.get("marL") or 0) * factor
    indent = (p.get("indent") or 0) * factor
    if marL:
        st += "padding-left:%gpx;" % marL
    if indent:
        st += "text-indent:%gpx;" % indent      # negative => hanging bullet
    return st


def render_paras(paras, factor, fallback_pt, bullets=True):
    html = []
    for p in paras:
        fb = max((r.get("size") for r in p["runs"] if r.get("size")), default=fallback_pt)
        bullet = ""
        if bullets and p.get("bullet") and p["runs"]:
            b = p["bullet"]
            bf = ("font-family:%s;" % family(b["font"])) if b.get("font") else ""
            bullet = '<span class="ds-bullet" style="%s">%s </span>' % (bf, escape(b["char"]))
        html.append('<div class="ds-para" style="%s">%s%s</div>'
                    % (para_style(p, factor), bullet, run_spans(p["runs"], factor, fb)))
    return "".join(html)


# ----------------------------- object rendering -----------------------------
def render_object(o, factor, ds, outdir, slide_no, obj_id):
    role, kind, geo = o.get("role"), o.get("kind"), o["geo"]

    if kind == "video":
        m = o["media"]
        ok = validate_asset(m.get("display_path"), outdir, slide_no, obj_id, "video") if m.get("playable") else False
        poster = (' poster="%s"' % escape(m["poster_path"])) if m.get("poster_path") else ""
        if ok:
            at = " controls" + (" loop" if m.get("loop") else "") + (" muted" if m.get("muted") else "") + \
                 (" autoplay playsinline" if m.get("autoplay") else "")
            inner = '<video class="ds-video"%s%s><source src="%s"></video>' % (at, poster, escape(m["display_path"]))
        else:
            pv = validate_asset(m.get("poster_path"), outdir, slide_no, obj_id, "image")
            if pv:
                bg = "background-image:url('%s');" % escape(m["poster_path"])
                badge = "▶ video — %s (브라우저 재생 불가, 원본 보존)" % (m.get("format") or "?")
                inner = '<div class="ds-video-fallback" style="%s"><span class="ds-video-badge">%s</span></div>' % (bg, escape(badge))
            else:
                return missing_box(geo, slide_no, obj_id, "video")
        return '<div class="fm-obj" style="%s">%s</div>' % (box(geo), inner)

    if kind == "picture":
        ok = validate_asset(o.get("src"), outdir, slide_no, obj_id, "image")
        if not ok:
            return missing_box(geo, slide_no, obj_id, "image")
        if role == "logo":
            inner = '<img class="ds-logo" src="%s" alt="logo">' % escape(o["src"])
        else:
            inner = '<figure class="ds-figure"><img class="ds-figure__img" src="%s" alt="figure"></figure>' % escape(o["src"])
        return '<div class="fm-obj" style="%s">%s</div>' % (box(geo), inner)

    if kind == "text":
        paras = o["paras"]
        if role == "title":
            inner = '<h1 class="ds-title">%s</h1>' % render_paras(paras, factor, ds.get("title_size_pt") or 40, bullets=False)
        elif role == "section-title":
            inner = '<h2 class="ds-section-title">%s</h2>' % render_paras(paras, factor, 32, bullets=False)
        elif role in ("footer", "citation"):
            inner = '<div class="ds-%s">%s</div>' % (
                "citation" if role == "citation" else "footer-inline",
                render_paras(paras, factor, 13, bullets=False))
        elif role == "annotation":
            inner = '<div class="ds-annotation">%s</div>' % render_paras(paras, factor, 18, bullets=False)
        else:  # body
            inner = '<div class="ds-body">%s</div>' % render_paras(paras, factor, 28, bullets=True)
        return '<div class="fm-obj" style="%s">%s</div>' % (box(geo), inner)

    if kind == "table":
        rows = o["rows"]
        head = "".join("<th>%s</th>" % escape(c) for c in rows[0]) if rows else ""
        body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % escape(c) for c in r) for r in rows[1:])
        return '<div class="fm-obj" style="%s"><table class="ds-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (box(geo), head, body)

    if kind == "line" or (kind == "shape" and role == "bottom-line"):
        color = o.get("color") or o.get("fill")
        return '<div class="ds-bottom-line" style="%s"></div>' % (("background:%s;" % color) if color else "")

    if kind == "shape":
        return '<div class="fm-obj" style="%s"><div style="width:100%%;height:100%%;%s"></div></div>' % (
            box(geo), ("background:%s;" % o["fill"]) if o.get("fill") else "")
    return ""


def chrome_layer(chrome):
    if not chrome:
        return ""
    parts = []
    bl = chrome.get("bottom_line")
    if bl:
        parts.append('<div class="ds-bottom-line" style="top:%dpx;background:%s;"></div>'
                     % (round(bl["geo"]["yf"] * STAGE_H), bl.get("color") or "#0070c0"))
    logo = chrome.get("logo")
    if logo and logo.get("src"):
        parts.append('<div class="ds-logo-box" style="%s"><img src="%s" alt="YUMC"></div>'
                     % (box(logo["geo"]), escape(logo["src"])))
    return '<div class="ds-chrome">%s</div>' % "".join(parts)


def tokens_css(ds):
    lines = []
    fam = (ds.get("fonts") or {}).get("minor") or (ds.get("fonts") or {}).get("major")
    if fam:
        lines.append('--ds-font-sans: "%s", "Malgun Gothic", "맑은 고딕", "Noto Sans KR", system-ui, sans-serif;' % fam)
    if ds.get("title_color"):
        lines.append("--ds-title-color: %s;" % ds["title_color"])
    if ds.get("brand_line_color"):
        lines.append("--ds-brand-line: %s;" % ds["brand_line_color"])
    return ":root{%s}" % "".join(lines) if lines else ""


def render_slide(slide, factor, ds, chrome, outdir):
    objs = "".join(render_object(o, factor, ds, outdir, slide["number"], i + 1)
                   for i, o in enumerate(slide["objects"]))
    active = " is-active" if slide["number"] == 1 else ""
    return '<section class="fm-slide%s" data-n="%d"><div class="ds-bg"></div>%s%s</section>' % (
        active, slide["number"], objs, chrome_layer(chrome))


def main():
    if len(sys.argv) < 3:
        print("Usage: python build.py <design-extract.json> <outdir>")
        sys.exit(1)
    extract_path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    data = json.load(open(extract_path, encoding="utf-8"))
    slides, ds, chrome = data["slides"], data.get("design_system", {}), data.get("chrome")
    factor = STAGE_W / (data["deck"].get("w_pt") or 960.0)

    src_assets = os.path.join(os.path.dirname(os.path.abspath(extract_path)), "assets")
    if os.path.isdir(src_assets):
        dst = os.path.join(outdir, "assets")
        if os.path.abspath(src_assets) != os.path.abspath(dst):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src_assets, dst)

    css = "\n".join(read(os.path.join(ENGINE, f)) for f in ("stage.css", "components.css", "ui.css"))
    js = read(os.path.join(ENGINE, "interaction.js"))
    slides_html = "\n".join(render_slide(s, factor, ds, chrome, outdir) for s in slides)

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
    with open(os.path.join(outdir, "asset-report.json"), "w", encoding="utf-8") as f:
        json.dump(ASSET_REPORT, f, ensure_ascii=False, indent=2)

    bad = [a for a in ASSET_REPORT if a["status"] != "ok"]
    print("Built %d slides (pt->px factor %.3f). assets ok=%d, invalid=%d"
          % (len(slides), factor, len(ASSET_REPORT) - len(bad), len(bad)))
    for a in bad:
        print("  MISSING slide %s obj %s: %s (%s)" % (a["slide"], a["object_id"], a["source_path"], a["error"]))


if __name__ == "__main__":
    main()
