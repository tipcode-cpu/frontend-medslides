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
    s = "left:%dpx;top:%dpx;width:%dpx;height:%dpx;" % (o["x"], o["y"], o["width"], o["height"])
    # explicit z-order from PPTX document order, so figures/videos/simulators sit
    # ABOVE the nav zones (z 5) and capture their own clicks. Background stays at 0.
    if "zIndex" in o and o.get("role") != "background":
        s += "z-index:%d;" % (10 + o["zIndex"])
    return s


def family(font):
    # Defense-in-depth: never emit invalid CSS font-family (e.g. theme refs '+mn-lt').
    if not font or not isinstance(font, str):
        return "var(--ds-font-sans)"
    f = font.strip().replace('"', "").replace(";", "")
    if not f or f.startswith("+"):
        return "var(--ds-font-sans)"
    return '"%s", var(--ds-font-sans)' % f


def bullet_px(p, fallback_pt, F):
    """Bullet size = PPT bullet size if specified, else the paragraph text size."""
    if p.get("bulletSizePts"):
        return p["bulletSizePts"] * F
    if p.get("bulletSizePct"):
        return fallback_pt * p["bulletSizePct"] * F
    return fallback_pt * F


def exists(extract_dir, rel):
    return bool(rel) and os.path.exists(os.path.join(extract_dir, rel.replace("/", os.sep)))


def missing_box(o, what):
    return ('<div class="fm-obj" style="%s"><div class="ds-missing">Missing %s: slide %s, %s</div></div>'
            % (box(o), what, o.get("_slide"), o["id"]))


# ---------- text ----------
def run_spans(runs, F, fallback_pt, fit=False):
    out = []
    for r in runs:
        st = ""
        sz = r.get("fontSize") or fallback_pt
        if sz:
            # autofit: size scalable via --fm-fit so JS can shrink overflowing
            # title/body text to fit its box (PowerPoint "shrink text on overflow").
            st += ("font-size:calc(%gpx * var(--fm-fit, 1));" if fit else "font-size:%gpx;") % (sz * F)
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


def render_paras(paras, F, fallback_pt, bullets=True, fit=False):
    html = []
    for p in paras:
        fb = max((r.get("fontSize") for r in p["runs"] if r.get("fontSize")), default=fallback_pt)
        bullet = ""
        if bullets and p.get("bullet") and p["runs"]:
            bsz = bullet_px(p, fb, F)                       # proportional to text, not tiny
            bf = ("font-family:%s;" % family(p["bulletFont"])) if p.get("bulletFont") else ""
            bc = ("color:%s;" % p["bulletColor"]) if p.get("bulletColor") else ""
            bullet = ('<span class="ppt-bullet" style="font-size:calc(%gpx * var(--fm-fit,1));%s%s">%s</span>'
                      % (bsz, bf, bc, escape(p["bullet"])))
        text = '<span class="ppt-bullet-text">%s</span>' % run_spans(p["runs"], F, fb, fit)
        html.append('<div class="ds-para" style="%s">%s%s</div>'
                    % (para_style(p, F), bullet, text))
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
        # interactive HTML simulator embedded inline (runs directly in the slide)
        if role == "simulator" and (o.get("simulatorLocal") or o.get("simulatorUrl")):
            local = o.get("simulatorLocal")
            src = local if (local and exists(extract_dir, local)) else o.get("simulatorUrl")
            live = o.get("simulatorUrl") or src
            return ('<div class="fm-obj ds-sim-box" style="%s" data-id="%s">'
                    '<iframe class="ds-simulator" src="%s" loading="lazy" '
                    'sandbox="allow-scripts allow-same-origin allow-pointer-lock allow-popups"></iframe>'
                    '<div class="ds-sim-tools">'
                    '<button class="ds-sim-full" title="전체화면 시뮬레이터">⛶ 전체화면</button>'
                    '<a class="ds-sim-open" href="%s" target="_blank" rel="noopener" title="새 탭">↗</a>'
                    '<button class="ds-sim-close" title="닫기">✕</button>'
                    '</div></div>'
                    % (box(o), o["id"], escape(src), escape(live)))
        if not exists(extract_dir, o.get("src")):
            return missing_box(o, "image")
        if role == "background":      # full-slide bg image: behind, not zoomable
            return '<div class="fm-obj fm-bg-image" style="%s"><img src="%s" alt=""></div>' % (box(o), escape(o["src"]))
        if role == "logo":
            inner = '<img class="ds-logo" src="%s" alt="logo">' % escape(o["src"])
        else:
            inner = '<figure class="ds-figure"><img class="ds-figure__img" src="%s" alt="figure" data-id="%s"></figure>' % (escape(o["src"]), o["id"])
        return '<div class="fm-obj" style="%s" data-id="%s">%s</div>' % (box(o), o["id"], inner)

    if t == "text":
        paras = o["paragraphs"]
        if role == "title":
            inner = '<h1 class="ds-title">%s</h1>' % render_paras(paras, F, ds.get("titleSizePt") or 40, bullets=False, fit=True)
        elif role == "section-title":
            inner = '<h2 class="ds-section-title">%s</h2>' % render_paras(paras, F, 32, bullets=False, fit=True)
        elif role in ("footer", "citation"):
            cls = "ds-citation" if role == "citation" else "ds-footer-inline"
            inner = '<div class="%s">%s</div>' % (cls, render_paras(paras, F, 13, bullets=False))
        elif role == "annotation":
            inner = '<div class="ds-annotation">%s</div>' % render_paras(paras, F, 18, bullets=False, fit=True)
        else:
            inner = '<div class="ds-body">%s</div>' % render_paras(paras, F, 28, bullets=True, fit=True)
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


def _area(o):
    return max(0, o.get("width", 0)) * max(0, o.get("height", 0))


def _overlap(a, b):
    ox = max(0, min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]))
    oy = max(0, min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]))
    return ox * oy


def layout_report(slides):
    """Detect text↔figure/video overlaps. A small text fully inside a figure is an
    intentional label; larger intersections are flagged as unintended."""
    rep = []
    for s in slides:
        n = s["slideNumber"]
        texts = [o for o in s["objects"] if o.get("type") == "text" and o.get("role") not in ("footer", "citation")]
        figs = [o for o in s["objects"] if o.get("type") in ("image", "video") and o.get("role") in ("figure", "video")]
        for t in texts:
            for fobj in figs:
                ov = _overlap(t, fobj)
                if ov <= 0:
                    continue
                ratio = ov / max(1, min(_area(t), _area(fobj)))
                inside = (t["x"] >= fobj["x"] - 4 and t["y"] >= fobj["y"] - 4 and
                          t["x"] + t["width"] <= fobj["x"] + fobj["width"] + 4 and
                          t["y"] + t["height"] <= fobj["y"] + fobj["height"] + 4)
                label = inside and _area(t) < 0.25 * _area(fobj)
                if ratio < 0.08:
                    continue
                rep.append({"slide": n, "textId": t["id"], "figureId": fobj["id"],
                            "overlapPx": int(ov), "ratio": round(ratio, 3),
                            "classification": "label (intentional)" if label else "unintended"})
    return rep


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
    # Simulator = interactive first-class content -> occupy (almost) the whole slide.
    has_title = any(o.get("type") == "text" and o.get("role") == "title"
                    and (o.get("plainText") or "").strip() for o in slide["objects"])
    for o in slide["objects"]:
        o["_slide"] = n
        if o.get("role") == "simulator":
            if has_title:
                o["x"], o["y"], o["width"], o["height"] = 40, 120, 1840, 860
            else:                       # no title -> full usable canvas above footer
                o["x"], o["y"], o["width"], o["height"] = 0, 0, 1920, 1020
    objs = "".join(render_object(o, F, ds, extract_dir) for o in slide["objects"])
    active = " is-active" if n == 1 else ""
    # invisible nav zones: above bg, below figures/videos (text passes clicks through)
    zones = ('<div class="fm-nav-zone fm-nav-zone-left" data-nav="prev"></div>'
             '<div class="fm-nav-zone fm-nav-zone-right" data-nav="next"></div>')
    return ('<section class="fm-slide%s" data-n="%d"><div class="ds-bg"></div>%s%s%s</section>'
            % (active, n, zones, objs, chrome_layer(chrome)))


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

    lr = layout_report(slides)
    json.dump(lr, open(os.path.join(outdir, "layout-report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    unintended = [x for x in lr if x["classification"] == "unintended"]
    print("HTML generated -> %s/presentation.html  (%d slides, validation=%s)"
          % (outdir, len(slides), vstatus))
    print("  layout-report: %d overlaps (%d unintended)" % (len(lr), len(unintended)))


if __name__ == "__main__":
    main()
