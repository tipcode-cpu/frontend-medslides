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

## Architecture

A one-time **build** produces a portable presentation; a small **runtime**
(mouse-first navigation, fullscreen, figure zoom/pan) plays it — independent of
slide content. See [`ARCHITECTURE.md`](ARCHITECTURE.md), [`VISION.md`](VISION.md),
[`REQUIREMENTS.md`](REQUIREMENTS.md).

```
extractor/extract_design_system.py   PPTX  -> design-extract.json (geometry, runs,
                                              tables, lines, grouped figures)
build.py                             JSON  -> semantic component HTML (Layer 1 + 2)
validate.py                          automated fidelity checks (the "compare" step)
engine/  stage.css · components.css · ui.css · interaction.js
```

---

## Quick start

```bash
pip install python-pptx pillow

# 1. (optional) generate a representative medical sample deck
python samples/make_sample_pptx.py

# 2. extract the design system + slide objects
python extractor/extract_design_system.py samples/sample.pptx samples/extract

# 3. reconstruct as semantic component HTML
python build.py samples/extract/design-extract.json samples/build

# 4. verify fidelity (semantic, geometry, branding, no flattening)
python validate.py samples/extract/design-extract.json samples/build/presentation.html

# open samples/build/presentation.html in a browser
```

Use your own deck by passing its `.pptx` to step 2.

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
