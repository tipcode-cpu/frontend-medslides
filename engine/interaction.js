/* ============================================================================
   interaction.js — Presentation interaction, INDEPENDENT of slide content
   ----------------------------------------------------------------------------
   Owns: stage scaling, mouse-first navigation, fullscreen, and figure
   zoom/pan (click-to-enlarge lightbox). Nothing here mutates slide content —
   the zoom viewer is a transient overlay that restores exact prior state.

   Reliability first: every feature is wrapped so a failure never blocks
   navigation (REQUIREMENTS PERF/INT fail-safe).
   ========================================================================== */
(function () {
  "use strict";

  /* ---- Stage scaling: fit the fixed 1920×1080 stage to the viewport ---- */
  var stage = document.querySelector(".fm-stage");
  function fitStage() {
    if (!stage) return;
    var W = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--stage-w")) || 1920;
    var H = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--stage-h")) || 1080;
    var s = Math.min(window.innerWidth / W, window.innerHeight / H);
    document.documentElement.style.setProperty("--scale", s);
  }
  window.addEventListener("resize", fitStage);
  fitStage();

  /* ---- Navigation state ---- */
  var slides = Array.prototype.slice.call(document.querySelectorAll(".fm-slide"));
  var idx = Math.max(0, slides.findIndex(function (s) { return s.classList.contains("is-active"); }));
  if (idx < 0) idx = 0;
  var viewerOpen = false;

  function show(i) {
    if (i < 0 || i >= slides.length) return;
    slides[idx].classList.remove("is-active");
    idx = i;
    slides[idx].classList.add("is-active");
    var ind = document.getElementById("fm-indicator");
    if (ind) ind.textContent = (idx + 1) + " / " + slides.length;
  }
  function next() { if (!viewerOpen) show(idx + 1); }
  function prev() { if (!viewerOpen) show(idx - 1); }

  /* Deep-link: open at #<n> (e.g. presentation.html#3). Useful for review. */
  (function () {
    var h = parseInt((location.hash || "").replace("#", ""), 10);
    if (h >= 1 && h <= slides.length) show(h - 1);
  })();
  window.addEventListener("hashchange", function () {
    var h = parseInt((location.hash || "").replace("#", ""), 10);
    if (h >= 1 && h <= slides.length) show(h - 1);
  });

  /* ---- Mouse-first controls (explicit targets = accident-resistant) ---- */
  bind("fm-next", "click", next);
  bind("fm-prev", "click", prev);
  bind("fm-full", "click", toggleFullscreen);

  /* ---- Keyboard fallback ---- */
  document.addEventListener("keydown", function (e) {
    if (e.target && /^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
    switch (e.key) {
      case "ArrowRight": case " ": case "PageDown": next(); break;
      case "ArrowLeft": case "PageUp": prev(); break;
      case "Home": show(0); break;
      case "End": show(slides.length - 1); break;
      case "f": case "F": toggleFullscreen(); break;
      case "d": case "D": toggleDebug(); break;
      case "Escape": if (viewerOpen) closeViewer(); else if (simFs) exitSimFs(); break;
    }
  });

  /* ---- PowerPoint-like mouse navigation via invisible zones ----
     Text has pointer-events:none so its clicks fall through to the zone beneath;
     figures/videos capture their own clicks. Disabled while the viewer is open. */
  var simFs = false, simBox = null;
  function exitSimFs() {
    if (simBox) simBox.classList.remove("fm-sim-fs");
    simFs = false; simBox = null;
  }
  document.addEventListener("click", function (e) {
    // simulator fullscreen / close (buttons live above figures, capture first)
    var full = e.target.closest && e.target.closest(".ds-sim-full");
    if (full) { simBox = full.closest(".ds-sim-box"); if (simBox) { simBox.classList.add("fm-sim-fs"); simFs = true; } return; }
    var close = e.target.closest && e.target.closest(".ds-sim-close");
    if (close) { exitSimFs(); return; }
    if (viewerOpen || simFs) return;                 // nav disabled while overlay open
    // navigate ONLY from empty background (nav zones). Figures/videos/simulators
    // sit above the zones and capture their own clicks, so they never advance.
    var zone = e.target.closest && e.target.closest(".fm-nav-zone");
    if (zone) { zone.getAttribute("data-nav") === "prev" ? prev() : next(); }
  });

  /* auto-hide bottom controls unless the mouse is near the bottom edge */
  window.addEventListener("mousemove", function (e) {
    document.body.classList.toggle("fm-show-controls", e.clientY > window.innerHeight * 0.86);
  });

  /* ---- Debug overlay (press D) ---- */
  var dbg = document.createElement("div");
  dbg.id = "fm-debug-info";
  document.body.appendChild(dbg);
  function toggleDebug() {
    document.body.classList.toggle("fm-debug");
    markOverlaps();
  }
  function markOverlaps() {
    var on = document.body.classList.contains("fm-debug");
    var slide = slides[idx];
    var objsEl = slide ? slide.querySelectorAll(".fm-obj") : [];
    var figs = [], texts = [], miss = 0;
    Array.prototype.forEach.call(objsEl, function (el) {
      el.classList.remove("fm-overlap");
      if (el.querySelector(".ds-figure__img, .ds-video, .ds-video-fallback")) figs.push(el);
      else if (el.querySelector(".ds-body, .ds-title, .ds-annotation, .ds-para")) texts.push(el);
      if (el.querySelector(".ds-missing")) miss++;
    });
    var overlaps = 0;
    texts.forEach(function (t) {
      var a = t.getBoundingClientRect();
      figs.forEach(function (f) {
        var b = f.getBoundingClientRect();
        var ox = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
        var oy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
        if (ox * oy > 0.08 * Math.min(a.width * a.height, b.width * b.height)) {
          overlaps++; t.classList.add("fm-overlap"); f.classList.add("fm-overlap");
        }
      });
    });
    if (on) dbg.textContent = "slide " + (idx + 1) + " / " + slides.length +
      "\nobjects: " + objsEl.length + "  figures: " + figs.length + "  texts: " + texts.length +
      "\noverlaps: " + overlaps + "  missing: " + miss;
  }
  var _origShow = show;
  show = function (i) { _origShow(i); if (document.body.classList.contains("fm-debug")) markOverlaps(); };

  function toggleFullscreen() {
    try {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen();
      else document.exitFullscreen();
    } catch (_) { /* fail-safe: ignore */ }
  }

  /* ---- Figure zoom/pan: click-to-enlarge lightbox (transient overlay) ----
     Navigation is suspended while open; first dismiss closes the viewer. */
  var viewer, viewerImg, vScale = 1, vx = 0, vy = 0, dragging = false, lastX = 0, lastY = 0;

  function ensureViewer() {
    if (viewer) return;
    viewer = document.createElement("div");
    viewer.id = "fm-viewer";
    viewer.innerHTML =
      '<div class="fm-viewer__bar">' +
        '<button data-z="out">−</button><span id="fm-zlevel">100%</span><button data-z="in">+</button>' +
        '<button data-z="reset">Reset</button><button data-z="close">✕</button>' +
      '</div><img class="fm-viewer__img" alt="">';
    document.body.appendChild(viewer);
    viewerImg = viewer.querySelector(".fm-viewer__img");

    viewer.addEventListener("click", function (e) {
      var z = e.target.getAttribute && e.target.getAttribute("data-z");
      if (z === "in") setZoom(vScale * 1.25);
      else if (z === "out") setZoom(vScale / 1.25);
      else if (z === "reset") resetView();
      else if (z === "close") closeViewer();
      else if (e.target === viewer) closeViewer(); /* click backdrop */
    });
    viewer.addEventListener("wheel", function (e) {
      e.preventDefault();
      setZoom(vScale * (e.deltaY < 0 ? 1.1 : 1 / 1.1));
    }, { passive: false });
    viewerImg.addEventListener("dblclick", resetView);
    viewerImg.addEventListener("mousedown", function (e) {
      dragging = true; lastX = e.clientX; lastY = e.clientY; e.preventDefault();
    });
    window.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      vx += e.clientX - lastX; vy += e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY; applyView();
    });
    window.addEventListener("mouseup", function () { dragging = false; });
  }

  function openViewer(src) {
    ensureViewer();
    viewerImg.src = src;
    viewerOpen = true;
    viewer.classList.add("is-open");
    resetView();
  }
  function closeViewer() {
    if (!viewer) return;
    viewer.classList.remove("is-open");
    viewerOpen = false;
  }
  function setZoom(s) {
    vScale = Math.min(8, Math.max(1, s));
    var lvl = document.getElementById("fm-zlevel");
    if (lvl) lvl.textContent = Math.round(vScale * 100) + "%";
    applyView();
  }
  function resetView() { vScale = 1; vx = 0; vy = 0; setZoom(1); }
  function applyView() {
    if (viewerImg) viewerImg.style.transform =
      "translate(" + vx + "px," + vy + "px) scale(" + vScale + ")";
  }

  /* Delegate clicks on any zoomable figure image to the viewer. */
  document.addEventListener("click", function (e) {
    var img = e.target.closest && e.target.closest(".ds-figure__img, .ds-figure--multipanel img");
    if (img && img.src) { e.stopPropagation(); openViewer(img.src); }
  });

  /* ---- helpers ---- */
  function bind(id, ev, fn) {
    var el = document.getElementById(id);
    if (el) el.addEventListener(ev, function (e) { try { fn(e); } catch (_) {} });
  }

  /* ---- Title auto-fit: shrink an overflowing (e.g. 3-line) title to fit its
     box, like PowerPoint "shrink text on overflow". Layout is at the fixed 1920
     design size, so this is viewport-independent — fit once after fonts load. */
  function fitTitles() {
    var titles = document.querySelectorAll(".ds-title");
    for (var i = 0; i < titles.length; i++) {
      var t = titles[i], boxEl = t.closest(".fm-obj");
      if (!boxEl) continue;
      t.style.setProperty("--ds-title-fit", "1");
      var max = boxEl.clientHeight, fit = 1, g = 0;
      while (t.scrollHeight > max + 1 && fit > 0.5 && g < 20) {
        fit -= 0.05; g++;
        t.style.setProperty("--ds-title-fit", fit.toFixed(2));
      }
    }
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitTitles);
  window.addEventListener("load", fitTitles);
  setTimeout(fitTitles, 500);

  /* init indicator */
  var ind = document.getElementById("fm-indicator");
  if (ind) ind.textContent = (idx + 1) + " / " + slides.length;
})();
