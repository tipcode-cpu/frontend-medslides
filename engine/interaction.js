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
      case "Escape": if (viewerOpen) closeViewer(); break;
    }
  });

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

  /* init indicator */
  var ind = document.getElementById("fm-indicator");
  if (ind) ind.textContent = (idx + 1) + " / " + slides.length;
})();
