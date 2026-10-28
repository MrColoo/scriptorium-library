// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Your year in books: story navigation (tap, keys, swipe, auto-advance), counters, calendar and the shareable image.
(function () {
  "use strict";
  var doc = document;
  var slides = Array.prototype.slice.call(doc.querySelectorAll(".yr-slide"));
  var bar = doc.querySelector(".yr-progress");
  if (!slides.length || !bar || !doc.getElementById("yr-slides")) return;

  function json(id) {
    var el = doc.getElementById(id);
    try { return el ? JSON.parse(el.textContent) : {}; } catch (e) { return {}; }
  }
  var DATA = json("year-data");
  var T = json("year-i18n");
  var DURATION = 7000;
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var index = -1, timer = null, started = 0, remaining = DURATION, paused = false;
  var pauseBtn = doc.querySelector("[data-yr-pause]");

  // Progress segments
  slides.forEach(function () {
    var seg = doc.createElement("span");
    seg.appendChild(doc.createElement("i"));
    bar.appendChild(seg);
  });
  var segments = bar.children;

  function holds(slide) { return slide.hasAttribute("data-hold"); }

  function countUp(slide) {
    Array.prototype.forEach.call(slide.querySelectorAll("[data-count]"), function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10) || 0;
      if (reduced || target < 2) { el.textContent = target.toLocaleString(); return; }
      var t0 = null, span = Math.min(1600, 600 + target * 20);
      function step(ts) {
        if (t0 === null) t0 = ts;
        var p = Math.min(1, (ts - t0) / span);
        el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString();
        if (p < 1) window.requestAnimationFrame(step);
      }
      el.textContent = "0";
      window.requestAnimationFrame(step);
    });
  }

  function fill(i, ratio) {
    var inner = segments[i] && segments[i].firstChild;
    if (inner) inner.style.width = (ratio * 100) + "%";
  }

  function schedule(ms) {
    window.clearTimeout(timer);
    var slide = slides[index];
    if (paused || holds(slide)) return;
    started = Date.now();
    remaining = ms;
    var inner = segments[index].firstChild;
    inner.style.transition = "none";
    inner.style.width = ((1 - ms / DURATION) * 100) + "%";
    void inner.offsetWidth;
    inner.style.transition = "width " + ms + "ms linear";
    inner.style.width = "100%";
    timer = window.setTimeout(next, ms);
  }

  function show(i) {
    if (i < 0 || i >= slides.length || i === index) return;
    if (index >= 0) slides[index].classList.remove("is-active");
    index = i;
    var slide = slides[index];
    slide.classList.add("is-active");
    for (var k = 0; k < segments.length; k++) {
      segments[k].classList.toggle("is-done", k < index);
      var inner = segments[k].firstChild;
      inner.style.transition = "none";
      inner.style.width = k < index ? "100%" : (k === index && holds(slide) ? "100%" : "0");
    }
    var stage = doc.getElementById("yr-stage");
    if (stage) stage.classList.toggle("is-last", index === slides.length - 1);
    countUp(slide);
    schedule(DURATION);
  }
  function next() { if (index < slides.length - 1) show(index + 1); }
  function prev() { if (index > 0) show(index - 1); }

  function setPaused(value) {
    if (value === paused) return;
    paused = value;
    if (pauseBtn) {
      pauseBtn.setAttribute("aria-label", paused ? (T.play || "Play") : (T.pause || "Pause"));
      pauseBtn.classList.toggle("is-paused", paused);
    }
    var inner = segments[index] && segments[index].firstChild;
    if (paused) {
      window.clearTimeout(timer);
      remaining = Math.max(0, remaining - (Date.now() - started));
      if (inner) { var w = getComputedStyle(inner).width; inner.style.transition = "none"; inner.style.width = w; }
    } else {
      schedule(remaining || DURATION);
    }
  }

  // Input
  doc.addEventListener("click", function (e) {
    if (e.target.closest("[data-yr-next]")) { next(); return; }
    if (e.target.closest("[data-yr-prev]")) { prev(); return; }
    if (e.target.closest("[data-yr-pause]")) { setPaused(!paused); return; }
    if (e.target.closest("[data-yr-replay]")) { show(0); return; }
    if (e.target.closest("[data-yr-save]")) { saveImage(); }
  });
  doc.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") { e.preventDefault(); next(); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); prev(); }
    else if (e.key === "p" || e.key === "P") { setPaused(!paused); }
  });
  var touchX = null;
  doc.addEventListener("touchstart", function (e) { touchX = e.touches[0].clientX; }, { passive: true });
  doc.addEventListener("touchend", function (e) {
    if (touchX === null) return;
    var dx = e.changedTouches[0].clientX - touchX;
    touchX = null;
    if (Math.abs(dx) > 60) { if (dx < 0) next(); else prev(); }
  }, { passive: true });
  doc.addEventListener("visibilitychange", function () { if (doc.hidden) setPaused(true); });

  // Year calendar on the streak slide
  Array.prototype.forEach.call(doc.querySelectorAll(".yr-calendar"), function (cal) {
    var year = parseInt(cal.getAttribute("data-year"), 10);
    var on = {};
    (cal.getAttribute("data-days") || "").split(",").forEach(function (d) { if (d) on[d] = true; });
    var first = new Date(Date.UTC(year, 0, 1));
    var offset = (first.getUTCDay() + 6) % 7; // Monday first
    var frag = doc.createDocumentFragment();
    for (var p = 0; p < offset; p++) { var pad = doc.createElement("i"); pad.style.visibility = "hidden"; frag.appendChild(pad); }
    for (var d = new Date(first), n = 0; d.getUTCFullYear() === year; d.setUTCDate(d.getUTCDate() + 1), n++) {
      var cell = doc.createElement("i");
      if (on[d.toISOString().slice(0, 10)]) { cell.className = "is-on"; cell.style.setProperty("--d", n); }
      frag.appendChild(cell);
    }
    cal.appendChild(frag);
  });

  // Shareable image (1080 × 1920)
  function loadImage(src) {
    return new Promise(function (resolve) {
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = function () { resolve(null); };
      img.src = src;
    });
  }
  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  function fitText(ctx, text, max, size, weight, family) {
    var s = size;
    do { ctx.font = weight + " " + s + "px " + family; s -= 2; } while (ctx.measureText(text).width > max && s > 18);
  }
  function saveImage() {
    var W = 1080, H = 1920, serif = '"Newsreader", Georgia, serif', sans = '"Geist", system-ui, sans-serif';
    var canvas = doc.createElement("canvas");
    canvas.width = W; canvas.height = H;
    var ctx = canvas.getContext("2d");
    var covers = (DATA.covers || []).map(function (id) { return (DATA.cover_url || "").replace("/0/", "/" + id + "/"); });
    var logo = doc.querySelector(".yr-brand img");
    Promise.all([doc.fonts ? doc.fonts.ready : Promise.resolve()].concat(covers.map(loadImage)).concat([loadImage(logo ? logo.src : "")]))
      .then(function (loaded) {
        var images = loaded.slice(1, 1 + covers.length).filter(Boolean);
        var icon = loaded[loaded.length - 1];
        // Background
        var g = ctx.createLinearGradient(0, 0, W, H);
        g.addColorStop(0, "#1B1530"); g.addColorStop(.55, "#3B1E2B"); g.addColorStop(1, "#151022");
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
        [["#8E5572", 160, 220, 520], ["#E9B44C", 940, 1500, 560], ["#2E6F95", 900, 300, 380]].forEach(function (b) {
          var r = ctx.createRadialGradient(b[1], b[2], 0, b[1], b[2], b[3]);
          r.addColorStop(0, b[0] + "88"); r.addColorStop(1, b[0] + "00");
          ctx.fillStyle = r; ctx.fillRect(0, 0, W, H);
        });
        // Shelf of spines
        var palette = ["#C8553D", "#E9B44C", "#2E6F95", "#5B8E7D", "#8E5572", "#D98E73", "#3D5A80", "#B5838D", "#6D597A", "#81B29A"];
        for (var i = 0; i < 22; i++) {
          var h = 120 + (i * 37) % 70, x = 90 + i * 41;
          ctx.fillStyle = palette[(i * 3) % palette.length];
          roundRect(ctx, x, 360 - h, 36, h, 4); ctx.fill();
          ctx.fillStyle = "rgba(255,255,255,.3)"; ctx.fillRect(x + 4, 360 - h + 18, 28, 3); ctx.fillRect(x + 4, 340, 28, 3);
        }
        ctx.fillStyle = "#6B4426"; ctx.fillRect(70, 360, W - 140, 14);
        // Header
        if (icon) { ctx.save(); roundRect(ctx, 90, 110, 64, 64, 14); ctx.clip(); ctx.drawImage(icon, 90, 110, 64, 64); ctx.restore(); }
        ctx.fillStyle = "#F6EEDD"; ctx.font = "600 34px " + sans; ctx.textBaseline = "middle";
        ctx.fillText("Scriptorium", 172, 143);
        ctx.textBaseline = "alphabetic";
        fitText(ctx, T.title || "", W - 180, 92, "600", serif);
        ctx.fillText(T.title || "", 90, 500);
        ctx.font = "500 40px " + sans; ctx.globalAlpha = .75; ctx.fillText(DATA.name || "", 90, 560); ctx.globalAlpha = 1;
        // Covers
        var cw = 220, chh = 330, total = images.length;
        images.forEach(function (img, k) {
          var cx = W / 2 + (k - (total - 1) / 2) * 150;
          ctx.save(); ctx.translate(cx, 880); ctx.rotate((k - (total - 1) / 2) * .09);
          ctx.shadowColor = "rgba(0,0,0,.45)"; ctx.shadowBlur = 40; ctx.shadowOffsetY = 20;
          roundRect(ctx, -cw / 2, -chh / 2, cw, chh, 8); ctx.fillStyle = "#000"; ctx.fill();
          ctx.shadowColor = "transparent"; ctx.clip();
          var scale = Math.max(cw / img.width, chh / img.height);
          ctx.drawImage(img, -img.width * scale / 2, -img.height * scale / 2, img.width * scale, img.height * scale);
          ctx.restore();
        });
        // Stats card
        var top = 1140;
        ctx.fillStyle = "#F6EEDD"; roundRect(ctx, 70, top, W - 140, 600, 40); ctx.fill();
        var stats = [[DATA.finished, T.books], [DATA.hours, T.hours], [DATA.streak, T.streak], [DATA.highlights, T.highlights]]
          .filter(function (s) { return s[0] > 0; }).slice(0, 4);
        stats.forEach(function (s, k) {
          var col = k % 2, row = Math.floor(k / 2), x = 130 + col * 440, y = top + 150 + row * 190;
          ctx.fillStyle = "#120F1C"; ctx.font = "700 112px " + serif; ctx.fillText(String(s[0]), x, y);
          ctx.font = "600 30px " + sans; ctx.globalAlpha = .6; ctx.fillText(String(s[1] || "").toUpperCase(), x, y + 46); ctx.globalAlpha = 1;
        });
        var line = top + 540;
        ctx.fillStyle = "#120F1C";
        var tops = [[T.top_author, DATA.author], [T.top_genre, DATA.genre]].filter(function (t) { return t[1]; });
        tops.forEach(function (t, k) {
          var x = 130 + k * 440;
          ctx.font = "600 24px " + sans; ctx.globalAlpha = .6; ctx.fillText(String(t[0]).toUpperCase(), x, line - 44); ctx.globalAlpha = 1;
          fitText(ctx, t[1], 400, 40, "600", serif); ctx.fillText(t[1], x, line);
        });
        if (T.style) {
          ctx.fillStyle = "#F6EEDD"; ctx.textAlign = "center"; fitText(ctx, T.style, W - 200, 64, "600", serif);
          ctx.fillText(T.style, W / 2, 1830); ctx.textAlign = "left";
        }
        canvas.toBlob(function (blob) {
          if (!blob) return;
          var file = new File([blob], T.file || "scriptorium-year.png", { type: "image/png" });
          if (navigator.canShare && navigator.canShare({ files: [file] })) {
            navigator.share({ files: [file], title: T.title }).catch(function () { download(blob); });
          } else {
            download(blob);
          }
        }, "image/png");
      });
  }
  function download(blob) {
    var a = doc.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = T.file || "scriptorium-year.png";
    doc.body.appendChild(a); a.click(); a.remove();
    window.setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  }

  show(0);
})();
