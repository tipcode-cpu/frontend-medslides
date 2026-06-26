#!/usr/bin/env python3
"""
validate.py — Validation Engine (pipeline stage 2 of 3).

   PPTX -> Extraction Engine -> [Validation Engine] -> HTML Generator

Consumes an extract/ folder and verifies the extraction BEFORE any HTML is
generated. Produces validation/{asset-report,font-report,media-report}.json and
report.md, and stamps manifest.validation with pass/fail. The HTML Generator
refuses to run unless status == "passed".

Hard failures (block HTML): a referenced image/video/logo file is missing or
zero bytes; an object lacks geometry; slide count != source.
Risks (reported, non-blocking): unsupported objects, non-browser-playable video
(conversion needed), missing font metadata.

Usage: python validate.py <extract_dir>
"""
import json
import os
import sys

IMG_TYPES = {"image"}
VID_TYPES = {"video"}


def load(extract_dir):
    manifest = json.load(open(os.path.join(extract_dir, "manifest.json"), encoding="utf-8"))
    slides = []
    for rel in manifest["slides"]:
        slides.append(json.load(open(os.path.join(extract_dir, rel), encoding="utf-8")))
    return manifest, slides


def fsize(extract_dir, rel):
    if not rel:
        return None
    p = os.path.join(extract_dir, rel.replace("/", os.sep))
    return os.path.getsize(p) if os.path.exists(p) else None


def validate(extract_dir):
    manifest, slides = load(extract_dir)
    asset_report, font_report, media_report = [], [], []
    hard_failures, risks = [], []

    # ---- per-slide objects ----
    for s in slides:
        n = s["slideNumber"]
        for o in s["objects"]:
            oid, otype = o.get("id"), o.get("type")
            # geometry present?
            if otype in ("text", "image", "video", "table", "shape", "chart") and \
               any(k not in o for k in ("x", "y", "width", "height")):
                hard_failures.append("slide %d %s: missing geometry" % (n, oid))

            if otype in IMG_TYPES:
                rel = o.get("src")
                sz = fsize(extract_dir, rel)
                status = o.get("status", "ok")
                err = o.get("error", "")
                if status == "failed" or not rel:
                    status, err = "failed", err or "no extracted src"
                    if o.get("role") == "figure":
                        hard_failures.append("slide %d %s: image extraction failed (%s)" % (n, oid, err))
                elif sz is None:
                    status, err = "missing", "file not found: %s" % rel
                    hard_failures.append("slide %d %s: %s" % (n, oid, err))
                elif sz == 0:
                    status, err = "empty", "zero bytes"
                    hard_failures.append("slide %d %s: zero-byte image %s" % (n, oid, rel))
                asset_report.append({"slide": n, "objectId": oid, "sourceRelId": o.get("relId"),
                                     "originalName": o.get("originalName"), "extractedPath": rel,
                                     "fileSize": sz if sz is not None else o.get("fileSize", 0),
                                     "dimensions": o.get("dimensions"), "type": "image",
                                     "status": status, "error": err})

            elif otype in VID_TYPES:
                rel = o.get("src")
                sz = fsize(extract_dir, rel)
                status = o.get("status", "ok")
                err = o.get("error", "")
                compat = bool(o.get("playable"))
                if status == "failed" or not rel:
                    status, err = "failed", err or "no extracted src"
                    hard_failures.append("slide %d %s: video extraction failed (%s)" % (n, oid, err))
                elif sz is None:
                    status, err = "missing", "file not found: %s" % rel
                    hard_failures.append("slide %d %s: %s" % (n, oid, err))
                elif sz == 0:
                    status, err = "empty", "zero bytes"
                    hard_failures.append("slide %d %s: zero-byte video" % (n, oid))
                elif not compat:
                    status = "needs-conversion"
                    risks.append("slide %d %s: video '%s' not browser-playable (poster shown)" % (n, oid, o.get("format")))
                asset_report.append({"slide": n, "objectId": oid, "sourceRelId": o.get("relId"),
                                     "originalName": o.get("originalName"), "extractedPath": rel,
                                     "fileSize": sz if sz is not None else o.get("fileSize", 0),
                                     "dimensions": None, "type": "video", "status": status, "error": err})
                media_report.append({"slide": n, "objectId": oid, "mediaType": "video",
                                     "embedded": o.get("embedded", True), "extractedPath": rel,
                                     "poster": o.get("poster"), "browserCompatible": compat,
                                     "conversionNeeded": bool(o.get("conversionNeeded")),
                                     "status": status, "error": err})

            elif otype == "text":
                for p in o.get("paragraphs", []):
                    for r in p.get("runs", []):
                        if not r.get("text", "").strip():
                            continue
                        miss = r.get("fontSize") is None
                        if miss:
                            risks.append("slide %d %s: run missing fontSize metadata" % (n, oid))
                        font_report.append({"slide": n, "objectId": oid, "role": o.get("role"),
                                            "level": p.get("level"),
                                            "fontFamily": r.get("fontFamily"),
                                            "fontSize": r.get("fontSize"),
                                            "fontWeight": r.get("fontWeight"),
                                            "color": r.get("color"),
                                            "fontMetadataComplete": not miss})

            elif otype == "chart" or o.get("status") == "unsupported":
                risks.append("slide %d %s: unsupported object (%s)" % (n, oid, o.get("type")))

    # ---- chrome / branding ----
    chrome = manifest.get("chrome") or {}
    if not chrome.get("logo"):
        risks.append("master logo not detected")
    else:
        if fsize(extract_dir, chrome["logo"].get("src")) in (None, 0):
            hard_failures.append("master logo file missing/empty")
        asset_report.append({"slide": "master", "objectId": "logo-001", "sourceRelId": None,
                             "originalName": None, "extractedPath": chrome["logo"].get("src"),
                             "fileSize": fsize(extract_dir, chrome["logo"].get("src")),
                             "dimensions": chrome["logo"].get("dimensions"), "type": "logo",
                             "status": "ok" if fsize(extract_dir, chrome["logo"].get("src")) else "missing",
                             "error": ""})
    if not chrome.get("bottomLine"):
        risks.append("bottom blue line not detected on master")

    # ---- counts ----
    src = manifest.get("source_counts", {})
    if src.get("slideCount") != manifest["deck"]["slideCount"]:
        hard_failures.append("slide count mismatch")
    extracted_vids = sum(1 for a in asset_report if a["type"] == "video")
    if src.get("videoLike", 0) != extracted_vids:
        risks.append("video count: source media has %s, extracted %s (some master/unused?)"
                     % (src.get("videoLike"), extracted_vids))

    # ---- write reports ----
    vdir = os.path.join(extract_dir, "validation")
    os.makedirs(vdir, exist_ok=True)
    json.dump(asset_report, open(os.path.join(vdir, "asset-report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(font_report, open(os.path.join(vdir, "font-report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(media_report, open(os.path.join(vdir, "media-report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    status = "passed" if not hard_failures else "failed"
    n_img = sum(1 for a in asset_report if a["type"] == "image")
    n_vid = sum(1 for a in asset_report if a["type"] == "video")
    missing = [a for a in asset_report if a["status"] in ("missing", "empty", "failed")]
    write_report_md(vdir, manifest, slides, status, n_img, n_vid, missing, hard_failures, risks, font_report)

    manifest["validation"] = {"status": status, "hardFailures": len(hard_failures),
                              "risks": len(risks), "images": n_img, "videos": n_vid,
                              "missingAssets": len(missing)}
    json.dump(manifest, open(os.path.join(extract_dir, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("Validation: %s  (images=%d videos=%d missing=%d hardFailures=%d risks=%d)"
          % (status.upper(), n_img, n_vid, len(missing), len(hard_failures), len(risks)))
    for f in hard_failures[:10]:
        print("  FAIL:", f)
    return status == "passed"


def write_report_md(vdir, manifest, slides, status, n_img, n_vid, missing, hard, risks, font_report):
    L = []
    L.append("# Extraction & Validation Report\n")
    L.append("**Source:** `%s`  " % manifest["source"])
    L.append("**Status:** %s\n" % ("✅ PASSED" if status == "passed" else "❌ FAILED"))
    d = manifest["deck"]
    L.append("## Deck")
    L.append("- Slides: **%d** (%s, %.0f×%.0f pt, stage %d×%d, pt→px %.2f)"
             % (d["slideCount"], d["aspect"], d["slideWidthPt"], d["slideHeightPt"],
                d["stageWidth"], d["stageHeight"], d["ptToPx"]))
    ds = manifest["designSystem"]
    L.append("- Title: %spt, color %s · brand line %s"
             % (ds.get("titleSizePt"), ds.get("titleColor"), ds.get("brandLineColor")))
    L.append("- Body levels: %s" % ", ".join("L%s=%spt/%s" % (k, v["fontSize"], v["bullet"])
                                             for k, v in (ds.get("bodyLevels") or {}).items()))
    L.append("")
    L.append("## Counts")
    sc = manifest["source_counts"]
    L.append("- Images extracted: **%d** (source media images ≈ %d)" % (n_img, sc.get("imageLike", 0)))
    L.append("- Videos extracted: **%d** (source media videos = %d)" % (n_vid, sc.get("videoLike", 0)))
    L.append("- Object totals: %s" % manifest.get("objectTotals"))
    L.append("- Master chrome: logo=%s, bottom blue line=%s"
             % (bool((manifest.get("chrome") or {}).get("logo")),
                bool((manifest.get("chrome") or {}).get("bottomLine"))))
    L.append("")
    L.append("## Missing / failed assets")
    if not missing:
        L.append("- None ✅ — every referenced image/video exists and is non-zero.")
    else:
        for m in missing:
            L.append("- slide %s `%s` (%s): %s — %s" % (m["slide"], m["objectId"], m["type"],
                                                        m["status"], m["error"]))
    L.append("")
    L.append("## Unsupported objects & fidelity risks")
    if not risks:
        L.append("- None.")
    else:
        for r in risks:
            L.append("- ⚠️ %s" % r)
    incomplete = sum(1 for f in font_report if not f["fontMetadataComplete"])
    L.append("")
    L.append("## Typography")
    L.append("- Text runs with font metadata: **%d/%d** complete"
             % (len(font_report) - incomplete, len(font_report)))
    L.append("")
    L.append("## Hard failures (block HTML generation)")
    if not hard:
        L.append("- None ✅")
    else:
        for h in hard:
            L.append("- ❌ %s" % h)
    L.append("")
    L.append("## Next recommended fixes")
    nxt = []
    if any("not browser-playable" in r for r in risks):
        nxt.append("Transcode WMV/AVI videos to MP4 (needs ffmpeg) for in-browser playback.")
    if any("unsupported" in r for r in risks):
        nxt.append("Implement chart rendering (currently reported as unsupported).")
    if incomplete:
        nxt.append("Resolve remaining inherited font sizes for %d runs." % incomplete)
    if not nxt:
        nxt.append("None — extraction is complete and HTML generation may proceed.")
    for x in nxt:
        L.append("- %s" % x)
    open(os.path.join(vdir, "report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate.py <extract_dir>")
        sys.exit(1)
    ok = validate(sys.argv[1])
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
