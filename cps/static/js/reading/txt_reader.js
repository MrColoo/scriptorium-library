// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Plain-text reader: themed, resizable, remembers where you stopped.
(function () {
  "use strict";
  var root = document.documentElement;
  var content = document.getElementById("content");
  var loader = document.getElementById("txt-loader");
  var progress = document.getElementById("progress");
  var THEMES = ["lightTheme", "sepiaTheme", "darkTheme", "blackTheme"];
  var key = "calibre.reader.txt." + content.getAttribute("data-key");

  function get(k, fallback) { try { return localStorage.getItem(k) || fallback; } catch (e) { return fallback; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage blocked */ } }

  var theme = get("calibre.reader.theme", "lightTheme");
  root.setAttribute("data-reader-theme", THEMES.indexOf(theme) === -1 ? "lightTheme" : theme);
  var size = parseInt(get("calibre.reader.txtSize", "18"), 10) || 18;
  function applySize() { content.style.fontSize = size + "px"; }
  applySize();

  document.querySelector("[data-txt-theme]").addEventListener("click", function () {
    var next = THEMES[(THEMES.indexOf(root.getAttribute("data-reader-theme")) + 1) % THEMES.length];
    root.setAttribute("data-reader-theme", next);
    set("calibre.reader.theme", next);
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-txt-size]"), function (btn) {
    btn.addEventListener("click", function () {
      var ratio = window.scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight);
      size = Math.min(32, Math.max(12, size + parseInt(btn.getAttribute("data-txt-size"), 10) * 2));
      set("calibre.reader.txtSize", String(size));
      applySize();
      window.scrollTo(0, ratio * (document.documentElement.scrollHeight - innerHeight));
    });
  });

  function ratio() {
    var max = document.documentElement.scrollHeight - innerHeight;
    return max > 0 ? Math.min(1, window.scrollY / max) : 1;
  }
  var ticking = false;
  window.addEventListener("scroll", function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      ticking = false;
      var r = ratio();
      progress.textContent = Math.round(r * 100) + "%";
      set(key, r.toFixed(4));
    });
  }, { passive: true });

  fetch(content.getAttribute("data-load"), { credentials: "same-origin" })
    .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.text(); })
    .then(function (text) {
      content.textContent = text;
      content.hidden = false;
      loader.remove();
      var saved = parseFloat(get(key, "0"));
      if (saved > 0) window.scrollTo(0, saved * (document.documentElement.scrollHeight - innerHeight));
      progress.textContent = Math.round(ratio() * 100) + "%";
    })
    .catch(function () {
      loader.remove();
      content.hidden = false;
      content.className = "reader-error";
      content.textContent = content.getAttribute("data-error");
    });
})();
