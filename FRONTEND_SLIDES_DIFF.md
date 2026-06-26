# FRONTEND_SLIDES_DIFF.md

> **Validation, not implementation.** Should frontend-medslides be a **plugin/extension**, a **fork**, or an **independent engine** relative to `frontend-slides`?
> Independence is **not** assumed. It must be cost-justified against what `frontend-slides` already provides.
> This analysis is based on **direct inspection of the installed `frontend-slides@frontend-slides` v2.1.0 source** (marketplace cache), not on description.

---

## 1. What frontend-slides actually is (from its source)

`frontend-slides` is a **Claude skill** (a prompt-orchestrated workflow), not a code library with an extensible API. Its job, in its own words: *"Create stunning, animation-rich HTML presentations… Helps non-designers discover their aesthetic through visual exploration."*

Evidence from the source:

- **SKILL.md** — a 6-phase authoring workflow: detect mode → content discovery → **style discovery (pick one of 3 generated aesthetics)** → generate → deliver → share/export. Core principle #3: *"No generic 'AI slop.' Every presentation must feel custom-crafted."*
- **PPT conversion (Phase 4)** — runs `scripts/extract-pptx.py`, then *"Convert to chosen style"* via the same style-discovery path. **It re-authors the deck in a new aesthetic.**
- **scripts/extract-pptx.py** — extracts, per slide: **title text, body text (`shape.text`, flattened), images (`shape_type == 13` only, with width/height but no x/y position), and speaker notes.** Nothing else.
- **viewport-base.css + html-template.md** — a **fixed 1920×1080 stage scaled uniformly to the viewport**, single self-contained HTML, zero dependencies, keyboard/touch/wheel navigation, inline text editing.
- **scripts/export-pdf.sh** — headless Playwright screenshots each `.slide` at 1920×1080 → PDF.
- **Fonts** — *"Use fonts from Fontshare or Google Fonts — never system fonts"* (a **CDN dependency**).

---

## 2. The two philosophies are opposite

| | frontend-slides | frontend-medslides |
|---|-----------------|--------------------|
| **Goal of PPT import** | **Re-author** the deck into a new, distinctive aesthetic | **Preserve** the author's deck exactly |
| **Design authority** | The tool redesigns ("avoid AI slop," "custom-crafted") | The author; the tool must never redesign |
| **Layout on import** | **Reflows** to density limits ("max 4–6 bullets, split slides") | Never reflow; pixel-faithful |
| **Branding** | Restyled to the chosen theme | Immutable, byte-for-byte |
| **Fonts** | Google Fonts / Fontshare (online) | Bundled local; **offline-absolute** |
| **Figure interaction** | None (it's a design tool) | Click-to-enlarge zoom/pan is a core MUST |

> This is not a gap to close — it is a **direct contradiction at the most important layer**. frontend-slides' flagship capability (restyle) is precisely what medslides forbids. You cannot "extend" a restyler into a preserver; the extension would have to *override the core behavior*.

---

## 3. Capability diff (against medslides requirements)

Legend: ✅ usable as-is · 🟡 partial / needs work · ❌ absent or contradictory.

| medslides need | frontend-slides today | Verdict | Evidence |
|----------------|----------------------|---------|----------|
| **PPTX import fidelity** | Text + images only; **drops positions, fonts, colors, lines, tables, charts, video, grouped shapes**; then restyles | ❌ | `extract-pptx.py` captures `title`, `shape.text`, pictures (`type 13`) + size; no geometry. Tables/charts (GraphicFrame), the bottom blue line (autoshape), and video are silently dropped. |
| **HTML presentation engine** | Fixed 1920×1080 stage, uniform scaling, single-file, zero-dep | ✅ | `viewport-base.css`, html-template.md — matches medslides LAY-02/03/08 closely. |
| **Navigation** | Keyboard (arrows/space/pgup-dn), touch swipe, mouse **wheel** | 🟡 | html-template.md `setupKeyboardNav/setupTouchNav` + wheel. No on-screen mouse prev/next buttons; "mouse-first" is partial. |
| **Mouse control** | Wheel + swipe; click used for inline **edit**, not nav | 🟡 | No accident-prevention model; no defined click-to-advance targets. |
| **Figure zoom / pan** | **None** | ❌ | No zoom/pan/lightbox anywhere in the engine. medslides' #1 interactive MUST is absent. |
| **Fullscreen** | **None** (no Fullscreen API use) | ❌ | Not present in engine files. |
| **Offline operation** | **Online fonts (CDN)**; otherwise self-contained | 🟡 | "Use Google Fonts/Fontshare." Violates offline-absolute until fonts are localized. |
| **Asset bundling** | Single-file inline + ad-hoc deploy bundling; **no budget/tiling/dedupe** | 🟡 | `deploy.sh` bundles `src=` assets; no native-res/tiling/memory model. |
| **CJK support** | None special; relies on Google Fonts | 🟡 | Works only if a CJK webfont is loaded online — fails offline. |
| **Medical figure support** (forest/KM/CT/echo/tables) | None; these are dropped on import | ❌ | Charts/tables/video not extracted; no medical patterns. |
| **Citation preservation** | Not preserved (text reflowed) | ❌ | Citations become body text; placement lost. |
| **Branding lock** | Opposite — branding is restyled | ❌ | Core philosophy conflict (§2). |
| **PDF export** | Playwright screenshot → PDF | ✅ | `export-pdf.sh` — directly reusable; also a spike measurement tool. |
| **Maintainability (as a dependency)** | It's a **skill/workflow**, not a versioned code API | ❌ | Nothing to import or subclass; "extending" means re-prompting its workflow. |
| **Extension cost** | High — must override its core, add the entire missing core | ❌ | See §4. |

**Coverage summary:** frontend-slides supplies **roughly 30–40% of the runtime/engine infrastructure** (fixed-stage scaling, single-file model, nav scaffold, PDF export) and **~0% of the core differentiator** (faithful preservation import, figure zoom, offline branding) — and its headline feature actively **contradicts** medslides at the import layer.

This is well below the "70–80% solved → build on it wholesale" threshold the task set.

---

## 4. The three options, evaluated

### Option 1 — Plugin / extension of frontend-slides ❌ Reject
- frontend-slides is a **skill (prompt workflow)**, not a library with an extension API. There is no seam to plug into.
- The only thing to "extend" is its style-discovery/redesign workflow — which is the exact behavior medslides must **suppress**. An extension that disables the host's core purpose is not an extension.
- Its import path destroys the very data medslides preserves (§3). No amount of plugin code recovers dropped positions/tables/charts/video.

### Option 2 — Fork (wholesale) 🟡 Reject as a wholesale fork; adopt selectively
- Forking the **skill** means inheriting the redesign workflow, the lossy extractor, and the CDN-font assumption — then ripping out the majority. Net negative: you'd delete more than you keep.
- **But** specific *engine assets* are worth vendoring (copying with attribution), not forking wholesale:
  - `viewport-base.css` — the fixed-stage uniform-scaling model (matches LAY-02/03/08).
  - `scripts/export-pdf.sh` — Playwright slide→PDF (fills medslides' missing EXPORT need; also the spike's measurement tool).
  - The keyboard/touch/wheel **nav scaffold** in `html-template.md` as a starting point (then add mouse-first, fullscreen, accident-prevention, and viewer coordination).

### Option 3 — Independent engine ✅ Recommended (with vendored primitives)
- The medslides **core** — faithful-render import, figure zoom/pan, offline-absolute bundling, immutable branding, medical patterns — has **no counterpart** in frontend-slides and is partly **contradicted** by it. This core is the whole product, and it must be built fresh.
- Independence here is **cost-justified by evidence**, not by preference: the reference framework solves none of the hard part and opposes it at the import layer.
- Avoid reinventing the *easy, proven* parts: vendor the three primitives above.

---

## 5. Recommendation

**Build frontend-medslides as an independent engine that vendors a few proven `frontend-slides` primitives.** Concretely:

| Decision | Detail |
|----------|--------|
| **Import** | Build fresh (faithful render + thin overlay). frontend-slides' extractor is unusable for preservation — keep it only as the **Strategy B baseline** in `FIDELITY_SPIKE.md` to quantify loss. |
| **Engine/stage** | **Vendor `viewport-base.css`'s fixed-1920×1080 uniform-scaling model.** It already implements medslides' layout scaling correctly. Do not reinvent it. |
| **Navigation** | Start from frontend-slides' keyboard/touch/wheel scaffold; **add** mouse-first prev/next, fullscreen, accident-prevention, and figure-viewer coordination (all absent today). |
| **Figure zoom/pan, offline bundling, branding lock, medical patterns** | Build fresh — no reusable counterpart exists. |
| **Export** | **Vendor `export-pdf.sh`** for the EXPORT need and as the spike's measurement instrument. |
| **Fonts** | Reject the CDN-font assumption outright; bundle locally (offline-absolute). |
| **Attribution** | Honor the frontend-slides LICENSE for any vendored file. |

**Why not "independent from scratch, ignore frontend-slides entirely":** that would waste the fixed-stage scaling and PDF-export work, which are genuinely solved. **Why not "build on frontend-slides":** it solves <40% of the infrastructure, 0% of the core, and contradicts preservation at the import layer.

---

## 6. Hard constraints this analysis surfaces (carry into design)

1. **The import layer must be net-new.** This is the project's real engineering cost; frontend-slides does not reduce it.
2. **CDN fonts are disqualifying** for medslides; any vendored frontend-slides guidance assuming Google Fonts/Fontshare must be changed to local bundling.
3. **frontend-slides confirms the lossy-reconstruction failure mode concretely** — its extractor is the canonical example of why Strategy B (in `FIDELITY_SPIKE.md`) loses tables, charts, lines, video, positions, and grouped figures. This is strong corroboration for the faithful-render direction — *pending* the spike confirming faithful render itself is achievable.
4. **This recommendation is conditional on the Fidelity Spike.** If the spike shows faithful render is **not** achievable, neither this engine nor frontend-slides solves the problem, and the direction must change. Run `FIDELITY_SPIKE.md` first.

---

## 7. Answer to the gating question

> **Should this be built on frontend-slides or independently?**

**Independently — as a new engine that vendors three proven primitives (`viewport-base.css` scaling, `export-pdf.sh`, the nav scaffold).** frontend-slides is a *redesign* tool whose import path discards exactly what medslides must preserve; it cannot be extended or forked into a *preservation* tool. Independence is cost-justified by direct source evidence, not assumed. Proceed only after the Fidelity Spike confirms faithful PPT→HTML rendering is achievable.
