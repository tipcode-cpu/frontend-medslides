#!/usr/bin/env python3
"""
validate.py — Automated fidelity checks on the reconstructed HTML.

This is the "compare" step of the build->test->compare->improve loop. It does
NOT need a browser: it parses the emitted body (ignoring inlined CSS/JS) and
asserts the structural-fidelity invariants the brief requires:

  * every slide reconstructed (count matches the extract)
  * objects are SEMANTIC + EDITABLE (h1/h2/figure/figcaption/cite/table/img),
    never flattened to a full-slide image
  * geometry preserved (every object box lies within the 1920x1080 stage)
  * inline emphasis preserved (italic run survives)
  * institutional chrome present on content slides (logo, footer, bottom line)

Usage: python validate.py <design-extract.json> <presentation.html>
"""
import json
import sys
from collections import Counter
from html.parser import HTMLParser


class BodyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.tags = Counter()
        self.classes = Counter()
        self.imgs = []          # (w,h) px from inline style
        self.boxes = []         # (left,top,width,height)
        self.italic = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("style", "script"):
            self.skip += 1
            return
        if self.skip:
            return
        self.tags[tag] += 1
        cls = a.get("class", "")
        for c in cls.split():
            self.classes[c] += 1
        if "fm-run-i" in cls:
            self.italic = True
        style = a.get("style", "")
        if tag == "div" and "fm-obj" in cls:
            self.boxes.append(_box(style))
        if tag == "img":
            # find nearest object box later; just record presence
            pass

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self.skip:
            self.skip -= 1


def _box(style):
    d = {}
    for part in style.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            d[k.strip()] = v.strip()
    def px(k):
        try: return float(d.get(k, "0").replace("px", ""))
        except: return 0.0
    return (px("left"), px("top"), px("width"), px("height"))


def main():
    extract_path, html_path = sys.argv[1], sys.argv[2]
    data = json.load(open(extract_path, encoding="utf-8"))
    html = open(html_path, encoding="utf-8").read()
    p = BodyParser(); p.feed(html)

    n_slides = len(data["slides"])
    roles = Counter(o["role"] for s in data["slides"] for o in s["objects"])

    checks = []
    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # 1. all slides reconstructed
    check("slides reconstructed", p.classes.get("fm-slide", 0) == n_slides,
          "html=%d extract=%d" % (p.classes.get("fm-slide", 0), n_slides))

    # 2. semantic, editable elements present (no flattening)
    check("titles -> <h1>", p.tags.get("h1", 0) >= roles.get("title", 0))
    check("section title -> <h2>", p.tags.get("h2", 0) >= roles.get("section-title", 0))
    check("figures -> <figure>", p.tags.get("figure", 0) >= roles.get("figure", 0),
          "figure=%d expected>=%d" % (p.tags.get("figure", 0), roles.get("figure", 0)))
    check("captions -> <figcaption>", p.tags.get("figcaption", 0) >= roles.get("caption", 0))
    check("citations -> <cite>", p.tags.get("cite", 0) >= roles.get("citation", 0))
    check("tables -> <table>", p.tags.get("table", 0) >= roles.get("table", 0))

    # 3. NOT flattened: no single object covers (almost) the whole stage as an image-only slide
    full = [b for b in p.boxes if b[2] >= 1900 and b[3] >= 1040]
    check("no full-slide flatten", len(full) == 0, "full-bleed boxes=%d" % len(full))

    # 4. geometry within stage bounds
    oob = [b for b in p.boxes if b[0] < -2 or b[1] < -2 or b[0] + b[2] > 1930 or b[1] + b[3] > 1090]
    check("geometry within stage", len(oob) == 0, "out-of-bounds=%d" % len(oob))

    # 5. inline emphasis preserved (italic 'Agatston' run)
    check("italic run preserved", p.italic)

    # 6. chrome present
    check("bottom blue line present", p.classes.get("ds-bottom-line", 0) >= n_slides - 1)
    check("logos present", p.classes.get("ds-logo", 0) >= 2)
    check("footer present", p.classes.get("ds-footer-inline", 0) >= n_slides - 1)

    print("Fidelity validation: %s\n" % html_path)
    ok = 0
    for name, passed, detail in checks:
        print("  [%s] %s%s" % ("PASS" if passed else "FAIL", name,
                               ("  (%s)" % detail) if detail else ""))
        ok += passed
    print("\n%d/%d checks passed" % (ok, len(checks)))
    sys.exit(0 if ok == len(checks) else 1)


if __name__ == "__main__":
    main()
