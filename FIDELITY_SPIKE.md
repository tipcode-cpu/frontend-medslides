# FIDELITY_SPIKE.md

> **Validation, not implementation.** A concrete plan to answer one question before any code is written:
> **Can PowerPoint → HTML preserve enough visual fidelity for academic medical slides?**
> If the answer is no, the faithful-render architecture (and most of the existing design docs) must change or stop.

---

## 1. What we are actually testing

The architecture assumes a slide can be rendered to a **faithful background** (SVG or high-res raster) that carries branding, typography, citations, and figures exactly as authored. That assumption is **unverified**. This spike verifies it empirically on the hardest real-world cases, **before** committing to it.

We test **two competing import strategies head-to-head**, because the project must choose one:

| Strategy | How | Hypothesis |
|----------|-----|-----------|
| **A — Faithful render** | Export each slide to image/SVG via PowerPoint's own export (ground-truth-grade) and via LibreOffice headless (`soffice --convert-to`) for a portable/CI path. | High fidelity, zero layout control, no live text. |
| **B — Reconstruct** | Extract text + images (e.g. `python-pptx`, as the frontend-slides extractor does) and re-lay-out in HTML. | Low fidelity, full structure, real text. |

Strategy B is included specifically because it is what `frontend-slides` does (see `FRONTEND_SLIDES_DIFF.md`). The spike measures *how much it loses* so the choice is evidence-based, not assumed.

---

## 2. Ground truth & measurement

- **Ground truth** = how **PowerPoint itself renders the slide** (PowerPoint "Export → PDF" or "Save as PNG" at full resolution). This is the highest-fidelity reference available and the bar the author expects to see.
- **Candidate outputs** = Strategy A (PPT export, LibreOffice export) and Strategy B (extract + re-render).
- **Comparison method (per slide):**
  1. **Overlay diff** — superimpose candidate on ground truth at identical resolution; inspect for shift, scale, color, or glyph differences.
  2. **Pixel diff** — automated difference image (e.g. ImageMagick `compare -metric AE`) for a quantitative deviation score where both are raster.
  3. **Targeted checks** — element-specific assertions (font glyph correct? blue line present at correct y? color value exact? smallest label legible?).
- **Environment captured** for every run: OS (Windows vs macOS — exports differ), PowerPoint version, LibreOffice version, fonts installed. Fidelity is only meaningful relative to a pinned environment.

> Tooling note: `frontend-slides/scripts/export-pdf.sh` (headless Playwright screenshot of HTML at 1920×1080) is a ready-made instrument for screenshotting candidate HTML for the diff. We reuse it as a *measurement tool* only.

---

## 3. Scoring rubric

Each test slide gets **PASS / PARTIAL / FAIL** per strategy:

- **PASS** — no perceptible difference from ground truth at presentation distance; all targeted checks pass; smallest authored text legible at intended size and at max zoom.
- **PARTIAL** — minor cosmetic deviation a reviewer must look for; no clinical/scientific information lost.
- **FAIL** — any visible shift/scale/color/glyph error a clinician would notice, OR any loss of scientific information (illegible label, dropped element, wrong color, missing video).

**Per-element targeted checks** (applied where relevant): font glyph correctness (esp. CJK), color exactness (background, blue line, brand), positional accuracy (≤2% of slide dimension), figure native-resolution at max zoom, element presence (logo, line, table, chart, video).

---

## 4. Decision gate (what the result means)

| Outcome | Decision |
|---------|----------|
| **Strategy A PASS/PARTIAL on ≥9/10**, with native-PPT-export PASS on all branding/figure slides | ✅ Faithful-render architecture is **validated**. Pin native PPT export as the renderer; document LibreOffice gaps. Proceed. |
| **Strategy A FAILs on any branding or figure slide** | ⚠️ Faithful render is **not** reliable enough. Stop and reconsider: either fix the export path or change architecture (e.g. SVG-with-live-text hybrid). Do **not** proceed on the current docs. |
| **LibreOffice fails but native PPT export passes** | ⚠️ Build tool requires PowerPoint installed (no CI/Linux). Record this as a hard constraint (see `FRONTEND_SLIDES_DIFF.md` §maintainability). |
| **Strategy B materially better than A on any axis** | Revisit the whole faithful-render premise. |

The spike **must** end with a one-line answer to: *"Can PPT→HTML preserve enough fidelity, and via which export path?"*

---

## 5. The 10-slide test protocol

Each slide is a deliberately hard, realistic academic-medical case. Build the source `.pptx` to the described characteristics, then run both strategies and score.

> Coverage map → required dimensions: CJK (S1), English medical typography (S2), hospital logo (S3), background + bottom blue line (S4), citation placement (S5), figure placement + high-res (S6), tables (S7), multi-panel (S8), forest/KM vector + figure comparison (S9), echo/video (S10).

---

### S1 — Korean (CJK) text-heavy slide
- **Purpose:** verify CJK glyph fidelity and line-breaking — the highest font-risk case for a Korean institution.
- **Source PPTX characteristics:** dense Korean body text in an institutional font (e.g. 맑은 고딕 / Noto Sans KR), mixed bold/regular, a Korean title, one Korean–English mixed line.
- **Expected HTML output:** every glyph identical to ground truth; identical line breaks; no tofu (□) or fallback-font substitution; no reflow.
- **Pass/fail criteria:** PASS only if all Korean glyphs render correctly and line breaks match. Any substituted glyph or shifted break = FAIL.
- **Likely failure modes:** font not embedded/available on the render machine → silent fallback → wrong glyph shapes and different line wrapping; LibreOffice substituting a different CJK font; SVG-with-live-text path missing the CJK font entirely.

### S2 — English medical typography
- **Purpose:** verify scientific typographic detail.
- **Source PPTX characteristics:** italic species/gene names, super/subscript (cm², HbA1c, p < 0.001), Greek letters (β-blocker, α), en/em dashes, units, a drug name with a registered mark.
- **Expected HTML output:** all sub/superscripts, italics, Greek, and symbols positioned and rendered exactly.
- **Pass/fail criteria:** any dropped/flattened superscript, lost italic, or wrong symbol = FAIL.
- **Likely failure modes:** Strategy B flattens runs (the frontend-slides extractor returns `shape.text` only — loses italics/superscript entirely); export path rasterizes correctly but loses selectable text.

### S3 — Hospital / university logo fidelity
- **Purpose:** verify immutable branding renders crisply at native quality.
- **Source PPTX characteristics:** a vector (EMF/SVG) hospital logo and a raster university logo, both in the master, plus a small tagline.
- **Expected HTML output:** logos at correct position/size, crisp (vector stays crisp at zoom), exact colors.
- **Pass/fail criteria:** PASS if both logos are pixel-faithful and correctly placed. Blurry vector logo or wrong color = FAIL.
- **Likely failure modes:** vector logo rasterized at low DPI → blurry on 4K projector; Strategy B drops logos that are not `shape_type == 13` (a grouped or placeholder logo is lost); master-placed logos not exported on content slides.

### S4 — Background color + bottom blue line
- **Purpose:** verify institutional chrome (the named immutable elements).
- **Source PPTX characteristics:** exact brand background color; the **bottom blue horizontal line** drawn as an autoshape/line (NOT a picture); a footer text run.
- **Expected HTML output:** exact background hex; blue line present at exact y, thickness, color; footer intact.
- **Pass/fail criteria:** background color must match exactly; the blue line must be present and correctly placed. Missing line = FAIL.
- **Likely failure modes:** **Strategy B drops the blue line entirely** (it is a line shape, not an image — the extractor captures only pictures and text); color-managed background shifting hex on export; footer from master not exported.

### S5 — Citation placement
- **Purpose:** verify small secondary citations stay exactly where authored.
- **Source PPTX characteristics:** a small-font citation in a fixed corner (e.g. "Circulation. 2023;147:1234–45"), superscript reference number elsewhere.
- **Expected HTML output:** citation at exact position, exact small size, legible, secondary.
- **Pass/fail criteria:** position within ≤2% of slide dimension and legible = PASS. Shifted, resized, or illegible = FAIL.
- **Likely failure modes:** Strategy B re-flows the citation into body text (loses placement); export path makes the small text legible but unselectable; downscaling makes it unreadable.

### S6 — Single high-resolution scientific figure (CT/MRI)
- **Purpose:** verify figure placement and native-resolution preservation for zoom.
- **Source PPTX characteristics:** one large CT or MRI image (high native resolution) occupying most of the slide, with a short caption beneath.
- **Expected HTML output:** figure at authored position/size, native resolution available for click-to-enlarge zoom with no quality loss; aspect ratio intact.
- **Pass/fail criteria:** at max zoom the image shows native detail (FIG-02) and aspect ratio is preserved. Blurry-at-zoom or stretched = FAIL.
- **Likely failure modes:** **the figure-asset data-model fork** — if the enlarge asset is cropped from the slide render, zoom is capped at slide DPI (FAIL); if stored separately, verify it is the native-resolution original; export path downsampling the embedded image.

### S7 — Clinical table
- **Purpose:** verify dense tabular data renders and stays legible.
- **Source PPTX characteristics:** a baseline-characteristics table (~6 columns × ~10 rows), small cell text, header shading, merged header cells.
- **Expected HTML output:** table visually identical, all cells legible at zoom, no reflow.
- **Pass/fail criteria:** every cell legible at zoom and layout identical = PASS.
- **Likely failure modes:** **Strategy B drops the table completely** (a PPTX table is a GraphicFrame, not a picture or text frame — the extractor captures neither); export path renders it but small cells need zoom to read; merged cells mis-rendered by LibreOffice.

### S8 — Multi-panel figure (2×2 composite)
- **Purpose:** verify composite figures preserved as one authored unit.
- **Source PPTX characteristics:** four sub-images arranged 2×2 with "A/B/C/D" labels, possibly grouped as one shape.
- **Expected HTML output:** the composite exactly as authored, panels not separated or rearranged, labels intact, zoom into any panel.
- **Pass/fail criteria:** panel arrangement, spacing, and A–D labels identical = PASS. Any panel moved/relabeled/dropped = FAIL.
- **Likely failure modes:** **Strategy B drops grouped shapes** (the extractor does not recurse into groups → whole composite lost); export path fine; panel labels (text boxes) lost if not exported.

### S9 — Forest plot / Kaplan–Meier (vector chart)
- **Purpose:** verify vector chart fidelity and small-label legibility — the evidence of the talk.
- **Source PPTX characteristics:** a forest plot or KM curve as a native PPT chart or vector graphic, with confidence intervals, axis labels, and a small risk table.
- **Expected HTML output:** crisp vector (SVG) at all zoom; CIs, axis ticks, and risk-table numbers legible at zoom.
- **Pass/fail criteria:** PASS if vector stays crisp and the smallest CI/risk-table label is legible at zoom. Rasterized-blurry or illegible = FAIL.
- **Likely failure modes:** **Strategy B drops the chart entirely** (a chart is a GraphicFrame); export path rasterizes the vector (loses crispness) unless SVG export preserves it; SVG export converting text to paths (no selectable text — feeds the SVG-text decision).

### S10 — Echocardiography / video slide
- **Purpose:** verify embedded clinical video survives and behaves offline.
- **Source PPTX characteristics:** an embedded echo loop (MP4) sized to a region, set to loop, plus a label.
- **Expected HTML output:** native inline playback from a **local** file, loop preserved, correct position, offline (no streaming).
- **Pass/fail criteria:** video plays offline at the authored position and loops = PASS. Missing video, broken playback, or any network dependency = FAIL.
- **Likely failure modes:** **export-to-image strategy turns the video into a static frame** (faithful render of a *moving* element is fundamentally lossy — this is a known architectural gap: video cannot be "a faithful background"); **Strategy B drops the video** (not a picture/text); codec unsupported on the venue browser.

---

## 6. Special findings to record (regardless of pass/fail)

These surfaced from inspecting the candidate import code and must be explicitly answered by the spike:

1. **Video breaks the faithful-render model.** A slide with motion cannot be "a faithful background image." S10 will confirm video must be a *separate tracked asset over a still background* — a structural exception the architecture must name.
2. **SVG: live-text vs outlined.** S2/S9 reveal whether the SVG export keeps `<text>` (needs fonts, selectable, reflow risk) or outlines it (faithful, no text). This decides TYP-02/TYP-05 and accessibility.
3. **Native PPT export vs LibreOffice gap.** If LibreOffice diverges on any slide, the build is PowerPoint-dependent (no CI). Record per-slide.
4. **Figure-asset native resolution (S6).** Confirms whether enlarge needs figures stored separately from the slide render (bundle-size impact).

---

## 7. Deliverable of the spike

A short results table — 10 slides × {Strategy A (PPT export), Strategy A (LibreOffice), Strategy B} × {PASS/PARTIAL/FAIL + notes} — plus the §4 decision and the §6 findings. **No code beyond throwaway test scripts.** If the gate is not met, the recommendation is to change or halt the current architecture, not to proceed to implementation.
