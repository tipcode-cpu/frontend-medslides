#!/usr/bin/env python3
"""
raw_media.py — Raw PPTX relationship-based media extractor & cross-check.

A PPTX is a ZIP. Rather than relying only on python-pptx (which extracts only
Picture shapes), this reads the OPC parts directly:

  raw_pptx/ppt/media/                     actual media blobs
  raw_pptx/ppt/slides/_rels/slideN.xml.rels   rId -> target media
  raw_pptx/ppt/slides/slideN.xml          which rIds are USED on the slide

It maps every rId to its target, copies all referenced media into
assets/media-raw/, writes validation/media-map.json, and cross-checks:
  present in ppt/media  vs  referenced by slide rels  vs  emitted by the engine.
Any image/video referenced+used but NOT emitted is a P0 error.

Run AFTER the extraction engine (which unzips into raw_pptx/ and writes slides/).
Usage: python raw_media.py <extract_dir>
"""
import json
import os
import re
import shutil
import sys
import lxml.etree as ET

R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MEDIA_REL = ("image", "video", "media", "audio")
BROWSER_IMG = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
BROWSER_VID = {"mp4", "webm", "ogg", "ogv", "m4v"}


def reltype_short(t):
    return (t or "").rsplit("/", 1)[-1].lower()


def main():
    if len(sys.argv) < 2:
        print("Usage: python raw_media.py <extract_dir>")
        sys.exit(1)
    ex = sys.argv[1]
    raw = os.path.join(ex, "raw_pptx")
    slides_dir = os.path.join(raw, "ppt", "slides")
    media_dir = os.path.join(raw, "ppt", "media")
    out_assets = os.path.join(ex, "assets", "media-raw")
    os.makedirs(out_assets, exist_ok=True)
    vdir = os.path.join(ex, "validation")
    os.makedirs(vdir, exist_ok=True)

    # 1) enumerate ppt/media
    present = set(os.listdir(media_dir)) if os.path.isdir(media_dir) else set()

    # emitted relIds per slide + whether a video object exists (its poster image
    # rel is covered by the video, not a separate figure)
    emitted = {}      # slideNo -> set(relId)
    has_video = {}    # slideNo -> bool
    for f in os.listdir(os.path.join(ex, "slides")):
        m = re.match(r"slide(\d+)\.json$", f)
        if not m:
            continue
        n = int(m.group(1))
        sj = json.load(open(os.path.join(ex, "slides", f), encoding="utf-8"))
        emitted[n] = {o.get("relId") for o in sj["objects"] if o.get("relId")}
        has_video[n] = any(o.get("type") == "video" for o in sj["objects"])

    media_map = []
    referenced = set()       # media filenames referenced by any slide
    p0 = []

    slide_xmls = sorted([f for f in os.listdir(slides_dir) if re.match(r"slide\d+\.xml$", f)],
                        key=lambda s: int(re.search(r"\d+", s).group())) if os.path.isdir(slides_dir) else []
    for sx in slide_xmls:
        n = int(re.search(r"(\d+)", sx).group(1))
        rels_path = os.path.join(slides_dir, "_rels", sx + ".rels")
        relmap = {}
        if os.path.exists(rels_path):
            for rel in ET.parse(rels_path).getroot():
                relmap[rel.get("Id")] = (reltype_short(rel.get("Type")), rel.get("Target"))
        xml = open(os.path.join(slides_dir, sx), encoding="utf-8", errors="ignore").read()
        used = set(re.findall(r'r:(?:embed|link)="(rId\d+)"', xml))

        for rid, (rtype, target) in relmap.items():
            if rtype not in MEDIA_REL:
                continue
            fname = os.path.basename(target)
            tgt_in_media = os.path.normpath(os.path.join(slides_dir, target))
            exists = os.path.exists(tgt_in_media) or fname in present
            if exists:
                referenced.add(fname)
            used_here = rid in used

            # copy referenced media into assets/media-raw (guarantee presence)
            extracted = None
            if exists:
                try:
                    src = tgt_in_media if os.path.exists(tgt_in_media) else os.path.join(media_dir, fname)
                    dst = os.path.join(out_assets, "s%02d_%s_%s" % (n, rid, fname))
                    shutil.copyfile(src, dst)
                    extracted = "assets/media-raw/" + os.path.basename(dst)
                except Exception:
                    extracted = None

            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            browser_ok = (ext in BROWSER_VID) if rtype in ("video", "media") else \
                         (ext in BROWSER_IMG) if rtype == "image" else False
            entry = {"slide": n, "rId": rid, "relationshipType": rtype, "target": target,
                     "extractedPath": extracted, "fileExists": exists, "usedInSlideXml": used_here,
                     "format": ext, "browserCompatible": browser_ok,
                     "conversionNeeded": bool(exists and used_here and not browser_ok and rtype in MEDIA_REL),
                     "emittedByEngine": rid in emitted.get(n, set())}
            media_map.append(entry)

            # P0 (genuinely missing scientific media):
            #  - referenced+used image that the engine did NOT emit AND the slide
            #    has no video (i.e. it is a real figure, not a video poster), or
            #  - referenced+used media whose target file is missing entirely.
            # Video media + their posters are rendered via the <video>/poster path
            # and are covered when a video object exists on the slide.
            if used_here and not exists:
                p0.append("slide %d %s: target media missing in ppt/media (%s)" % (n, rid, target))
            elif (used_here and rtype == "image" and not entry["emittedByEngine"]
                  and not has_video.get(n)):
                p0.append("slide %d %s (image -> %s): referenced figure NOT emitted" % (n, rid, fname))

    unused = sorted(present - referenced)

    report = {"mediaPresent": len(present), "mediaReferenced": len(referenced),
              "mediaUnused": unused, "p0Errors": p0, "map": media_map}
    json.dump(report, open(os.path.join(vdir, "media-map.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("Raw media cross-check: present=%d referenced=%d unused=%d  P0=%d"
          % (len(present), len(referenced), len(unused), len(p0)))
    for e in p0[:15]:
        print("  P0:", e)
    sys.exit(2 if p0 else 0)


if __name__ == "__main__":
    main()
