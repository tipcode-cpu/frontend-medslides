#!/usr/bin/env python3
"""
run.py — Pipeline orchestrator for frontend-medslides.

   PPTX -> Extraction Engine -> Validation Engine -> HTML Generator -> HTML

Enforces order: HTML is generated ONLY after extraction and validation succeed.
The Extraction Engine is the source of truth; the generator never reads the PPTX.

Usage: python run.py <input.pptx> <work_dir> [--force-html]
  <work_dir>/extract/   extraction + validation output (source of truth)
  <work_dir>/build/     interactive HTML presentation
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def step(title, cmd):
    print("\n=== %s ===" % title)
    return subprocess.run(cmd).returncode


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force-html" in sys.argv
    if len(args) < 2:
        print("Usage: python run.py <input.pptx> <work_dir> [--force-html]")
        sys.exit(1)
    pptx, work = args[0], args[1]
    extract_dir = os.path.join(work, "extract")
    build_dir = os.path.join(work, "build")

    if step("1/4 Extraction Engine", [PY, os.path.join(HERE, "extractor", "extraction_engine.py"), pptx, extract_dir]):
        print("Extraction failed; stopping."); sys.exit(1)

    rc = step("2/4 Raw media cross-check", [PY, os.path.join(HERE, "extractor", "raw_media.py"), extract_dir])
    if rc == 2 and not force:
        print("\nRaw media cross-check found P0 errors (referenced media not emitted).")
        print("See %s/validation/media-map.json" % extract_dir)
        sys.exit(2)

    rc = step("3/4 Validation Engine", [PY, os.path.join(HERE, "validation", "validate.py"), extract_dir])
    if rc not in (0, 2):
        print("Validation errored; stopping."); sys.exit(1)
    if rc == 2 and not force:
        print("\nValidation FAILED. HTML not generated. See %s/validation/report.md" % extract_dir)
        print("(re-run with --force-html to override)")
        sys.exit(2)

    gen = [PY, os.path.join(HERE, "build.py"), extract_dir, build_dir]
    if force:
        gen.append("--force")
    if step("4/4 HTML Generator", gen):
        print("HTML generation refused/failed."); sys.exit(1)

    print("\nDone. Open %s/presentation.html" % build_dir)
    print("Reports: %s/validation/report.md" % extract_dir)


if __name__ == "__main__":
    main()
