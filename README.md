# frontend-medslides

> An HTML presentation engine for **academic medical presentations**.
> PowerPoint stays the authoring tool; frontend-medslides reconstructs each deck
> as a **reusable, editable, component-based HTML/CSS presentation** that
> preserves the author's design language — figures, branding, citations, and all.

**PowerPoint is the design language. frontend-medslides is the presentation engine.**

---

## What it does

It treats a PowerPoint deck as a **design system** and rebuilds it in two layers:

- **Layer 1 — Design system.** Extract reusable rules (typography, spacing, brand
  color, the bottom blue line, logo/footer placement, citation style) into CSS
  design tokens. Edit one token → re-theme every slide.
- **Layer 2 — Slide reconstruction.** Every PowerPoint object becomes a **semantic,
  editable** HTML element mapped to a reusable component — never flattened to an image:

  | PowerPoint | HTML component |
  |------------|----------------|
  | Title / Section | `<h1>` / `<h2>` |
  | Body text | `.ds-text` (runs preserve bold/italic/underline) |
  | Scientific figure | `<figure><img>` (click-to-enlarge) |
  | Multi-panel figure | grid of panels, preserved as one unit |
  | Caption / Citation | `<figcaption>` / `<cite>` |
  | Table | `<table>` |
  | Logo / Footer / Bottom line / Background | reusable chrome components |

Figure-first by design: CT, MRI, angiography, echo, pathology, forest plots,
Kaplan–Meier curves, clinical tables. Offline-absolute (no CDN; local fonts).

---

## Architecture — Extraction-first pipeline

The **Extraction Engine is the core**. It extracts, preserves, and reports every
meaningful PowerPoint object as structured data *before* any HTML exists. HTML is
generated only after extraction and validation succeed.

```
PPTX → Extraction Engine → Validation Engine → Slide JSON → HTML Generator → HTML
```

```
extractor/extraction_engine.py   PPTX -> extract/ (per-slide JSON, organized
                                 assets, manifest.json) — the source of truth
validation/validate.py           extract/ -> asset/font/media reports + report.md;
                                 stamps manifest pass/fail
build.py                         validated extract/ -> interactive HTML
                                 (refuses unless validation passed)
run.py                           orchestrates extract → validate → build
engine/  stage.css · components.css · ui.css · interaction.js
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md), [`VISION.md`](VISION.md),
[`REQUIREMENTS.md`](REQUIREMENTS.md).

The `extract/` folder (the source of truth):

```
extract/
├── raw_pptx/                  original PPTX
├── assets/{images,videos,logos,icons,audio,unsupported}/
├── slides/slideNN.json        structured slide (geometry px, paragraphs/runs
│                              with resolved font metadata, bullets, spacing)
├── validation/{asset-report,font-report,media-report}.json + report.md
└── manifest.json              deck · design system · chrome · counts · validation
```

---

## Quick start

```bash
pip install python-pptx pillow

# one command: extract → validate → generate HTML
python run.py "my-deck.pptx" out/
# -> out/extract/  (source of truth + reports)   out/build/presentation.html

# or run the stages individually:
python extractor/extraction_engine.py my-deck.pptx out/extract
python validation/validate.py out/extract          # writes report.md, sets pass/fail
python build.py out/extract out/build              # refuses unless validation passed
```

Generate a representative medical sample deck with
`python samples/make_sample_pptx.py`.

**Navigation:** mouse `‹ › ⛶` controls · arrows/space · `F` fullscreen ·
click a figure to zoom/pan · `#3` deep-links to a slide.

---

## Status

Working prototype. The reconstruction pipeline runs end-to-end and passes its
fidelity checks on the bundled sample deck. A true pixel-diff against PowerPoint
requires PowerPoint/LibreOffice installed; see [`FIDELITY_SPIKE.md`](FIDELITY_SPIKE.md).
Design rationale and the build-vs-reuse analysis are in
[`FRONTEND_SLIDES_DIFF.md`](FRONTEND_SLIDES_DIFF.md).

The skill knowledge base lives in [`SKILL.md`](SKILL.md) and [`docs/`](docs/).
