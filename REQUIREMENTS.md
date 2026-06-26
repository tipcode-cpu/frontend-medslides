# REQUIREMENTS.md

> Functional and engineering specification for **frontend-medslides**.
> Derived from VISION.md. This document is the source of truth for *what* the system must do.
> An engineer should be able to implement frontend-medslides from this document alone.

---

## 0. Document conventions

### 0.1 Requirement levels

| Level | Meaning | Build rule |
|-------|---------|-----------|
| **MUST** | Essential. The project cannot exist without it. | Always implemented. A failing MUST blocks release. |
| **SHOULD** | Highly recommended. Implement whenever feasible. | Implemented unless it conflicts with a MUST or with reliability. |
| **NICE TO HAVE** | Future enhancement. | Built only on explicit request; design must not preclude it. |

### 0.2 Requirement IDs

Every requirement has a stable ID: `<AREA>-<NUM>` (e.g. `FIG-03`). IDs never change once assigned; deprecated requirements are marked `[DEPRECATED]` rather than deleted.

### 0.3 Definitions

- **Source slide** — the original PowerPoint slide as authored. The visual *truth*.
- **Rendered slide** — the HTML presentation of a source slide.
- **Usable slide area** — the slide canvas minus locked branding regions (footer, bottom blue line, logos).
- **Immutable element** — branding/identity element that is never altered automatically (see §4).
- **Figure** — a scientific image or graphic: CT, MRI, angiography, echocardiography, pathology, forest plot, Kaplan–Meier curve, clinical table, diagram.
- **Live mode** — fullscreen presentation during a talk. Reliability ceiling.
- **Author** — the clinician/researcher who made the PowerPoint.

### 0.4 Global priority order (tie-breaker for any conflict)

When two requirements conflict, resolve in this order:

1. Preservation of the author's design (§1, §4)
2. Presentation reliability / offline robustness (§11, §13)
3. Figure readability (§5)
4. Citation readability (§7)
5. Overall visual balance
6. Text readability
7. Decorative / experiential enhancements (§9)

> **Reliability outranks visual effects. Preservation outranks creativity.**

---

## 1. Presentation Layout

The HTML rendering must reproduce the source slide, not redesign it.

| ID | Level | Requirement |
|----|-------|-------------|
| LAY-01 | MUST | The rendered slide MUST reproduce the source slide's layout — element positions, sizes, z-order, and proportions — within **≤2% positional deviation** of the slide's width/height relative to the source. |
| LAY-02 | MUST | The slide canvas MUST use a fixed logical aspect ratio matching the source deck (default **16:9**; **4:3** supported). The ratio is read from the source, never assumed. |
| LAY-03 | MUST | The canvas MUST scale to fit the viewport (letterbox/pillarbox as needed) while preserving aspect ratio. No cropping of slide content at any supported viewport. |
| LAY-04 | MUST | The framework MUST NOT reflow, re-justify, or auto-rearrange slide elements. Text does not re-wrap differently from the source beyond what fixed positioning requires. |
| LAY-05 | MUST | The framework MUST NOT auto-generate replacement layouts or "smart" templates that substitute the author's visual language. |
| LAY-06 | MUST | Each slide MUST be addressable and rendered deterministically: the same source produces a byte-identical DOM on every load (no random layout decisions). |
| LAY-07 | SHOULD | Supported viewport range: **1024×768 up to 4K (3840×2160)** without visual breakage. |
| LAY-08 | SHOULD | The system SHOULD assume a fixed design resolution (recommended **1920×1080** logical px) and scale via transform, so 1px in source maps predictably to the canvas. |
| LAY-09 | NICE TO HAVE | Optional "fit width" vs "fit height" user toggle for non-standard projector ratios. |

---

## 2. PowerPoint Import

PowerPoint is the source of truth. Import preserves; it does not interpret.

| ID | Level | Requirement |
|----|-------|-------------|
| IMP-01 | MUST | The import pipeline MUST accept a PowerPoint-derived source. Accepted form is one of: (a) exported high-resolution slide images, (b) exported SVG per slide, or (c) structured slide assets + a layout manifest. The chosen form MUST preserve visual fidelity per §13. |
| IMP-02 | MUST | Import MUST preserve original slide order and slide count. No slide is dropped, merged, or reordered. |
| IMP-03 | MUST | Import MUST preserve embedded figures at their **native resolution** (no down-sampling below source DPI). |
| IMP-04 | MUST | Import MUST NOT apply business/pitch-deck transformations (auto-icons, stock theming, "design ideas", color remaps). |
| IMP-05 | MUST | A per-deck **manifest** (e.g. `manifest.json`) MUST record: slide count, order, aspect ratio, per-slide asset references, and immutable-element regions. The renderer reads only the manifest + assets. |
| IMP-06 | SHOULD | Import SHOULD detect and tag immutable regions (logos, footer, bottom blue line) so they can be locked (§4). Detection method may be coordinate-based from a template. |
| IMP-07 | SHOULD | Import SHOULD preserve vector content as SVG when available, falling back to raster only when vector is unavailable. |
| IMP-08 | SHOULD | Import SHOULD preserve embedded video and link it for native playback (§10), not flatten it to a thumbnail. |
| IMP-09 | NICE TO HAVE | Direct `.pptx` parsing (OOXML) to extract shapes/text/media without an intermediate export step. |
| IMP-10 | NICE TO HAVE | Round-trip diff report: highlight any slide where rendered output deviates from source beyond LAY-01 tolerance. |

---

## 3. Typography

Typography hierarchy is part of the author's identity and is immutable by default.

| ID | Level | Requirement |
|----|-------|-------------|
| TYP-01 | MUST | The rendered slide MUST preserve the source typography hierarchy: relative font sizes, weights, and emphasis ordering are maintained. |
| TYP-02 | MUST | All fonts MUST be bundled locally (§11). No webfont CDN. If a source font is unavailable, a **documented, visually-matched fallback** is used and recorded in the manifest. |
| TYP-03 | MUST | Text MUST NOT be re-styled, re-colored, or re-spaced automatically. Margins, line spacing, and alignment match the source. |
| TYP-04 | MUST | Large paragraphs MUST NOT be allowed to dominate a slide; where the source already balances text against figures, that balance is preserved (text never grows relative to figures). |
| TYP-05 | SHOULD | Rendered text SHOULD remain selectable/searchable where the source provides real text (improves accessibility, §12), unless preserving fidelity requires rasterization. |
| TYP-06 | SHOULD | Font rendering SHOULD be deterministic across the common conference OSs (Windows, macOS) — same metrics, no substitution surprises. |
| TYP-07 | NICE TO HAVE | Author-opt-in typographic refinement (e.g. kerning/hinting) that never changes hierarchy or layout. |

---

## 4. Branding (Immutable Elements)

These are **locked**. They are never modified, moved, recolored, or removed automatically.

| ID | Level | Requirement |
|----|-------|-------------|
| BRD-01 | MUST | Hospital logo and university logo MUST be preserved exactly: same asset, same position (±0 deviation from source coordinates), same size. |
| BRD-02 | MUST | Slide **background color** MUST be preserved exactly (exact color value from source). |
| BRD-03 | MUST | The **footer** and the **bottom blue horizontal line** MUST be preserved in position, thickness, and color. |
| BRD-04 | MUST | Citation style and citation placement (§7) MUST be preserved as authored. |
| BRD-05 | MUST | No feature, theme, or "enhancement" MUST be permitted to overwrite, overlay, or restyle an immutable element. Immutable regions are non-targetable by automated styling. |
| BRD-06 | MUST | Branding changes are permitted **only** through an explicit, user-initiated action — never as a side effect of any other feature. |
| BRD-07 | SHOULD | The system SHOULD render immutable regions in a dedicated, locked layer that interactive features (zoom/pan) cannot cover or displace. |
| BRD-08 | SHOULD | A validation check SHOULD fail the build if any immutable region's computed position/color diverges from the manifest. |

---

## 5. Figures

The framework is figure-first. This section is the most detailed by design.

### 5.1 Sizing & fidelity

| ID | Level | Requirement |
|----|-------|-------------|
| FIG-01 | MUST | Figures MUST be the primary visual focus. On figure-centric slides, the principal figure SHOULD occupy **70–90% of the usable slide area** (preserving the source proportion when the source already does this; never shrinking it below source scale). |
| FIG-02 | MUST | Figures MUST render at their **native resolution** and MUST NOT be upscaled-blurry or downscaled below the source. Target: **no perceptible quality loss vs. source at 100% and at max zoom**. |
| FIG-03 | MUST | Aspect ratio of every figure MUST be preserved. No stretching, squashing, or auto-crop. |
| FIG-04 | MUST | Figures MUST be served from locally bundled assets (§11), full quality, no lossy re-compression beyond source. |
| FIG-05 | SHOULD | The pipeline SHOULD support high-DPI/retina assets (e.g. 2× source) so figures stay crisp on 4K projectors. |

### 5.2 Zoom & pan (click-to-enlarge)

| ID | Level | Requirement |
|----|-------|-------------|
| FIG-06 | MUST | **Click-to-enlarge** MUST be available on every figure: a single click/tap enlarges the figure to an overlay viewer. |
| FIG-07 | MUST | The enlarged viewer MUST support **zoom** (in/out) and **pan** for inspecting scientific detail. Zoom range MUST be at least **1× to 4×**; SHOULD reach **8×** for high-DPI assets. |
| FIG-08 | MUST | Zoom MUST be smooth and MUST keep the figure within the viewer bounds (no losing the image off-screen). Pan MUST be clamped so the image cannot be dragged completely out of view. |
| FIG-09 | MUST | Exiting the enlarged viewer MUST return to the exact slide state (same slide, same scroll/zoom of the slide) with a single, obvious action (click outside, `Esc`, or close control). |
| FIG-10 | MUST | While a figure is enlarged, slide-navigation clicks MUST NOT fire (no accidental slide change while inspecting a figure — see NAV-06). |
| FIG-11 | SHOULD | Zoom SHOULD support mouse wheel and double-click-to-zoom, centered on the cursor. |
| FIG-12 | SHOULD | The viewer SHOULD show a subtle zoom-level indicator and a "reset to fit" control. |
| FIG-13 | NICE TO HAVE | Pinch-to-zoom for touch displays / tablets used at the podium. |

### 5.3 Multi-panel, comparison & tables

| ID | Level | Requirement |
|----|-------|-------------|
| FIG-14 | MUST | Multi-panel figures (e.g. A/B/C/D composites, before/after) MUST be preserved as a single composite exactly as authored; panels are not separated or rearranged automatically. |
| FIG-15 | SHOULD | The enlarged viewer SHOULD allow zoom/pan within a multi-panel figure so a single panel can be inspected without splitting the composite. |
| FIG-16 | SHOULD | Clinical **tables** and dense plots (forest plots, Kaplan–Meier curves) MUST remain legible: zoom MUST make the smallest authored text/labels readable at no worse than the source's intended reading size. |
| FIG-17 | NICE TO HAVE | **Comparison layout / figure comparison mode**: view two figures (or two slides' figures) side by side with synchronized zoom/pan. Build only on request. |
| FIG-18 | NICE TO HAVE | Saved "regions of interest" (preset zoom targets) an author can step through during a talk. |

### 5.4 Interactive figures

| ID | Level | Requirement |
|----|-------|-------------|
| FIG-19 | SHOULD | **Interactive SVG** figures MUST be supported: vector figures render as SVG and stay crisp at all zoom levels. |
| FIG-20 | NICE TO HAVE | SVG anatomy interaction (hover/click regions), AI-assisted figure organization, medical image viewer, DICOM support — all future, request-only, and must not require redesign to add (§14). |

---

## 6. Captions

| ID | Level | Requirement |
|----|-------|-------------|
| CAP-01 | MUST | Captions/labels authored on a figure MUST be preserved verbatim, in position, and MUST NOT be auto-generated, rewritten, or relocated. |
| CAP-02 | MUST | When a figure is enlarged, its authored caption MUST remain associated and readable (shown with the figure or in the viewer). |
| CAP-03 | SHOULD | Caption typography SHOULD remain visually secondary to the figure and consistent with the source. |
| CAP-04 | NICE TO HAVE | Optional toggle to hide/show captions in the enlarged viewer for clean inspection. |

---

## 7. Citations

Citations are immutable identity elements (§4) and must behave with perfect consistency.

| ID | Level | Requirement |
|----|-------|-------------|
| CIT-01 | MUST | Citation **style** (font, size, color, format) MUST be preserved exactly as authored. |
| CIT-02 | MUST | Citation **placement** MUST be preserved exactly and MUST be **consistent and stable**: a citation MUST NOT move, reflow, or change position between renders, navigations, or viewport sizes. |
| CIT-03 | MUST | Citations MUST remain **visually secondary** — never enlarged, emphasized, or promoted above figure/content readability — while staying legible. |
| CIT-04 | MUST | Interactive features (zoom, pan, fullscreen) MUST NOT displace, cover, or alter citations on the base slide. |
| CIT-05 | SHOULD | Citation alignment and spacing relative to its anchor (figure/slide edge) SHOULD be preserved within ≤2% positional deviation across all viewports. |
| CIT-06 | NICE TO HAVE | Optional citation-to-reference linking (click a citation → jump to a references slide), opt-in, without changing visible placement. |

---

## 8. Navigation

Primarily **mouse-first**. Reliable and accident-resistant.

| ID | Level | Requirement |
|----|-------|-------------|
| NAV-01 | MUST | **Next slide** and **previous slide** MUST be operable with the mouse alone (e.g. left-click / on-screen prev-next controls). |
| NAV-02 | MUST | Navigation MUST be reliable and immediate: slide change responds in **≤100 ms** on conference-grade hardware. |
| NAV-03 | MUST | **Fullscreen presentation** mode MUST be available and toggleable, entering true fullscreen with no browser chrome. |
| NAV-04 | MUST | Slide order in navigation MUST exactly match source order (§2). |
| NAV-05 | MUST | **Accidental click prevention**: navigation MUST distinguish intent — e.g. only a defined click target / region advances; clicks on figures, links, or controls do not advance the slide. |
| NAV-06 | MUST | **Interaction while enlarged**: when a figure viewer is open, slide navigation is suspended (FIG-10); the first dismiss action closes the viewer, not advances the slide. |
| NAV-07 | SHOULD | Keyboard support SHOULD be provided as a secondary path: `→`/`Space` next, `←` prev, `F` fullscreen, `Esc` exit viewer/fullscreen, `Home`/`End` first/last slide. |
| NAV-08 | SHOULD | A slide position indicator (e.g. `12 / 40`) SHOULD be available and unobtrusive, hideable during the talk. |
| NAV-09 | SHOULD | Transitions between slides SHOULD be smooth but minimal; a transition MUST never delay readiness of the next slide (reliability > effect). |
| NAV-10 | NICE TO HAVE | Slide overview/grid (thumbnail jump), presenter notes view, jump-to-slide-by-number. |

---

## 9. Interactive Features

Enhancements to the *experience* that never change the *design*. Each must degrade gracefully.

| ID | Level | Requirement |
|----|-------|-------------|
| INT-01 | MUST | All interactive features MUST be additive overlays/layers that never modify, cover, or restyle immutable elements (§4) or alter source layout (§1). |
| INT-02 | MUST | Any interactive feature MUST fail safe: if it errors, the slide still renders and navigation still works (no feature can break the talk — §11/§13). |
| INT-03 | SHOULD | Smooth zoom/pan transitions (§5.2) SHOULD feel responsive (≥30 fps interaction, target 60 fps). |
| INT-04 | SHOULD | High-resolution image rendering and native video (§10) and interactive SVG (FIG-19) are the recommended interactive baseline. |
| INT-05 | NICE TO HAVE | **Laser pointer mode** (mouse-driven highlight). |
| INT-06 | NICE TO HAVE | **Annotation mode** (draw/markup over a slide, non-destructive, never saved into the source). |
| INT-07 | NICE TO HAVE | Interactive timelines, embedded medical calculators, figure comparison mode (FIG-17). All request-only. |

---

## 10. Video Support

| ID | Level | Requirement |
|----|-------|-------------|
| VID-01 | SHOULD | **Native video playback** MUST be supported for embedded clinical media (e.g. echocardiography loops, angiography runs) using locally bundled files (§11). |
| VID-02 | SHOULD | Video MUST play inline at its slide position with the author's framing preserved; controls (play/pause/seek) available, autoplay off by default. |
| VID-03 | SHOULD | Supported formats SHOULD include at least **MP4 (H.264)**; the bundle MUST contain a format playable offline by the conference browser. |
| VID-04 | SHOULD | Video MUST loop when the source loops (echo loops), and MUST be muted-capable for silent clinical clips. |
| VID-05 | SHOULD | Video MUST NOT depend on any network/streaming source. No YouTube/Vimeo/CDN embeds in live mode. |
| VID-06 | NICE TO HAVE | Frame-step controls and click-to-enlarge for video (zoom/pan a paused frame). |

---

## 11. Offline Operation

Everything required to present MUST work with **no internet**. No CDN, ever.

| ID | Level | Requirement |
|----|-------|-------------|
| OFF-01 | MUST | A presentation MUST be fully functional offline. With networking disabled, every slide, figure, font, icon, video, and feature works identically to online. |
| OFF-02 | MUST | All assets MUST be bundled locally: CSS, JavaScript, fonts, images, icons, videos. **Zero external requests** at present time. |
| OFF-03 | MUST | The deliverable MUST be self-contained and portable (a folder or single bundle) that runs by opening the entry HTML — no build step or server required at the venue. |
| OFF-04 | MUST | No runtime dependency MUST resolve to a remote URL. A build check SHOULD fail if any `http(s)://` external reference exists in shipped code/markup. |
| OFF-05 | SHOULD | The bundle SHOULD run from `file://` and from a simple local static server identically. |
| OFF-06 | SHOULD | Total bundle SHOULD be transferable via USB/email-sized chunks where feasible; large media documented separately. |
| OFF-07 | NICE TO HAVE | Optional service worker for cache resilience when served over a local server. |

---

## 12. Accessibility

Within the hard constraint that fidelity and preservation come first.

| ID | Level | Requirement |
|----|-------|-------------|
| ACC-01 | SHOULD | Navigation and core controls SHOULD be keyboard-operable (NAV-07) and focus-visible. |
| ACC-02 | SHOULD | Controls SHOULD have accessible labels (ARIA) for screen readers; figures expose their authored captions/alt where available (CAP-01). |
| ACC-03 | SHOULD | Contrast of *framework-added* UI (controls, indicators) SHOULD meet WCAG AA; source slide content is preserved as-authored and is out of scope for recoloring. |
| ACC-04 | SHOULD | Zoom (§5.2) SHOULD double as a low-vision aid for inspecting small figure detail. |
| ACC-05 | NICE TO HAVE | Reduced-motion mode honoring `prefers-reduced-motion` (disables transitions). |

---

## 13. Performance & Reliability

Reliability during a live talk outranks every visual effect.

| ID | Level | Requirement |
|----|-------|-------------|
| PERF-01 | MUST | The presentation MUST load to first interactive slide in **≤3 s** on conference-grade hardware (mid-range laptop) from local storage. |
| PERF-02 | MUST | Slide navigation MUST respond in **≤100 ms** (NAV-02); no perceptible stall on next/prev. |
| PERF-03 | MUST | Behavior MUST be predictable and stable for the full duration of a talk — no memory growth that degrades performance, no feature that can crash the presentation. |
| PERF-04 | MUST | High-resolution figures MUST be presented without blocking navigation: large assets load/decoded such that the slide remains responsive (lazy-decode/preload adjacent slides). |
| PERF-05 | SHOULD | Adjacent slides (n±1) SHOULD be preloaded so forward/back navigation is instant. |
| PERF-06 | SHOULD | Slide transitions SHOULD hold a smooth **60 fps**, degrading gracefully to no-transition rather than dropping frames. |
| PERF-07 | SHOULD | The system SHOULD be verified on the realistic worst case: a deck with many full-resolution CT/MRI/pathology images and echo videos. |
| PERF-08 | MUST | **Reliability ranking** is explicit: when a visual effect risks instability, the effect is dropped, not the reliability. |

---

## 14. Future Extensibility

The architecture must accommodate future modules without redesign.

| ID | Level | Requirement |
|----|-------|-------------|
| EXT-01 | MUST | The renderer and feature layer MUST be modular: interactive features are plug-in overlays registered against slides/figures, addable/removable without touching the import or layout core. |
| EXT-02 | MUST | The data model (manifest, §2) MUST be versioned and extensible so new asset/feature types can be added backward-compatibly. |
| EXT-03 | SHOULD | A stable extension API SHOULD expose: slide lifecycle hooks, the figure viewer, and the immutable-layer boundary (so extensions cannot violate §4). |
| EXT-04 | SHOULD | The following future modules MUST be addable without major redesign: medical image viewer, DICOM support, laser pointer (INT-05), annotation (INT-06), interactive/anatomy SVG (FIG-20), embedded medical calculators, AI-assisted figure organization. |
| EXT-05 | MUST | No future module may weaken a MUST in §1, §4, §7, or §11. Extensions are sandboxed by the global priority order (§0.4). |
| EXT-06 | NICE TO HAVE | A reference framework (e.g. frontend-slides) MAY be studied for architecture/navigation/workflow, but frontend-medslides MUST remain independent and MUST NOT inherit business/pitch-deck assumptions. |

---

## 15. Acceptance & Decision Checklist

A change is acceptable only if all of the following hold (mirrors VISION.md, made testable):

- [ ] **Preservation** — Rendered slide reproduces the source within LAY-01 tolerance; no auto-redesign (§1).
- [ ] **Branding** — All immutable elements untouched; BRD-08 validation passes (§4).
- [ ] **Figures** — Figure readability is top priority; native resolution; zoom/pan within bounds (§5).
- [ ] **Citations** — Style and placement preserved and stable across renders/viewports (§7).
- [ ] **Experience-not-design** — The change enhances experience without altering design (§9, INT-01).
- [ ] **Offline** — Works with networking disabled; zero external requests (§11).
- [ ] **Reliability** — No feature can fail the talk; load ≤3 s, nav ≤100 ms (§13).
- [ ] **Default to preservation** — If uncertain, the change preserved rather than redesigned (§0.4).

---

## Appendix A — Requirement summary by level

**MUST (release-blocking):**
LAY-01..06, IMP-01..05, TYP-01..04, BRD-01..06, FIG-01..04, FIG-06..10, FIG-14, FIG-16, CAP-01..02, CIT-01..04, NAV-01..06, INT-01..02, OFF-01..04, PERF-01..04, PERF-08, EXT-01..02, EXT-05.

**SHOULD:**
LAY-07..08, IMP-06..08, TYP-05..06, BRD-07..08, FIG-05, FIG-11..12, FIG-15, FIG-19, CAP-03, CIT-05, NAV-07..09, INT-03..04, VID-01..05, OFF-05..06, ACC-01..04, PERF-05..07, EXT-03..04.

**NICE TO HAVE (request-only, must not be precluded):**
LAY-09, IMP-09..10, TYP-07, FIG-13, FIG-17..18, FIG-20, CAP-04, CIT-06, NAV-10, INT-05..07, VID-06, OFF-07, ACC-05, EXT-06.

---

> **PowerPoint creates the presentation. frontend-medslides elevates the presentation experience — measurably, reliably, and without ever redesigning the author's work.**
