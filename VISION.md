# CLAUDE.md

> Claude Code project guidance for **frontend-medslides**.
> Read this before making any change. The core rule overrides all others:
> **Preserve the author's presentation. Enhance only the presentation experience.**

---

## What this project is

frontend-medslides is an HTML presentation framework for **academic medical presentations**. PowerPoint authors the slides; HTML presents them. The framework adds interactive presentation capabilities (zoom, pan, fullscreen, offline) **without redesigning the original slides**.

- **PowerPoint = source of truth.** Authoring stays in PowerPoint.
- **HTML = presentation environment.** Live delivery, sharing, interaction.
- Slides are **figure-first**, not text-first.

Workflow: `PowerPoint → frontend-medslides → Interactive HTML Presentation`

---

## Non-negotiable rules

1. **Never redesign slides unless the user explicitly requests it.** Preservation always beats creativity.
2. **Never auto-generate layouts** that replace the author's visual language.
3. **Do not alter institutional branding** (see Immutable Elements) unless explicitly asked.
4. **Do not import assumptions** from pitch decks, business, marketing, or generic web-presentation frameworks.
5. When a design decision is uncertain: **preserve rather than redesign**, respect author intent, prioritize scientific communication.

---

## Immutable elements

Treat these as locked unless the user explicitly requests a change:

- Hospital logo, university logo
- Background color
- Footer and the bottom blue horizontal line
- Citation style and citation placement
- Typography hierarchy, spacing, margins, visual balance

These define the author's presentation identity.

---

## Priority order for any design decision

1. Figure readability
2. Citation readability
3. Overall visual balance
4. Text readability
5. Decorative elements

Large paragraphs must never dominate a slide. The framework is built around scientific figures: echocardiography, CT, MRI, angiography, pathology, forest plots, Kaplan–Meier curves, clinical tables.

---

## Features Claude Code may build / extend

HTML enhancements that add capability **without changing slide design**:

- Mouse-first navigation (prev/next with mouse only)
- Fullscreen presentation
- Offline operation
- Click-to-enlarge figures
- Pan and zoom for scientific images
- High-resolution image rendering
- Native video playback
- Interactive SVG support

Future direction (build only when requested): laser pointer mode, annotation mode, figure comparison mode, interactive timelines, embedded medical calculators, medical image viewer, DICOM support, SVG anatomy interaction, AI-assisted figure organization.

---

## Performance & reliability requirements

Prioritize, in order:

- Visual fidelity
- Offline reliability
- Fast loading
- High-resolution figures
- Predictable behavior during live conferences

**Presentation reliability is more important than visual effects.** No feature should risk failure mid-talk.

---

## When studying reference frameworks

frontend-slides (or similar) may be studied for architecture, navigation engine, workflow, and project organization — but frontend-medslides must remain **independent** and must not inherit business/pitch-deck assumptions.

---

## Decision checklist (run before committing any change)

- [ ] Does this preserve the original PowerPoint slide as-is?
- [ ] Are all immutable branding elements untouched?
- [ ] Is figure readability still the top priority?
- [ ] Does this enhance the *experience* without altering the *design*?
- [ ] Will it work offline and reliably during a live conference?
- [ ] If uncertain, did I default to preservation?

---

> **PowerPoint creates the presentation. frontend-medslides elevates the presentation experience.**
