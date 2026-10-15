// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// EPUB reader: configuration from the page and the reading-settings panel.
// Loaded before reader.min.js / epub.js, which read window.calibre and window.themes.
(function () {
  "use strict";
  var cfg = JSON.parse(document.getElementById("reader-config").textContent);
  var root = document.documentElement;

  window.calibre = {
    filePath: cfg.filePath,
    cssPath: cfg.cssPath,
    bookmarkUrl: cfg.bookmarkUrl,
    bookUrl: cfg.bookUrl,
    bookmark: cfg.bookmark || "",
    useBookmarks: cfg.useBookmarks === true,
    kosyncPercent: cfg.kosyncPercent,
    i18n: cfg.i18n || {}
  };
  window.themes = {
    lightTheme: { bgColor: "#ffffff", css_path: cfg.themeCss },
    sepiaTheme: { bgColor: "#f4ecd8", css_path: cfg.themeCss },
    darkTheme: { bgColor: "#1c1c1f", css_path: cfg.themeCss },
    blackTheme: { bgColor: "#000000", css_path: cfg.themeCss }
  };

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* storage blocked */ }
  }
  function mark(groupId, activeId) {
    var group = document.getElementById(groupId);
    if (!group) return;
    Array.prototype.forEach.call(group.querySelectorAll("button"), function (b) {
      b.setAttribute("aria-pressed", b.id === activeId ? "true" : "false");
    });
  }
  function rendition() { return window.reader && window.reader.rendition; }

  window.selectTheme = function (id) {
    if (!window.themes[id]) id = "lightTheme";
    mark("themes", id);
    root.setAttribute("data-reader-theme", id);
    store("calibre.reader.theme", id);
    if (rendition()) rendition().themes.select(id);
  };

  var FONTS = {
    Arial: "Arial, Helvetica, sans-serif",
    Yahei: "\"Microsoft YaHei\", sans-serif",
    SimSun: "SimSun, serif",
    KaiTi: "KaiTi, serif"
  };
  var defaultFont = null;
  window.selectFont = function (id) {
    var r = rendition();
    if (r && defaultFont === null) {
      try { defaultFont = (r.getContents()[0] && r.getContents()[0].css("font-family")) || ""; } catch (e) { defaultFont = ""; }
    }
    mark("font", id);
    store("calibre.reader.font", id);
    if (!r) return;
    r.themes.font(id === "default" ? (defaultFont || "") : (FONTS[id] || id));
  };

  window.spread = function (id) {
    mark("layout", id);
    store("calibre.reader.spread", id);
    if (rendition()) rendition().spread(id === "spread" ? true : "none");
  };

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-reader-theme-set],[data-reader-font],[data-reader-spread]");
    if (!t) return;
    if (t.hasAttribute("data-reader-theme-set")) window.selectTheme(t.getAttribute("data-reader-theme-set"));
    else if (t.hasAttribute("data-reader-font")) window.selectFont(t.getAttribute("data-reader-font"));
    else window.spread(t.getAttribute("data-reader-spread"));
  });

  // Text size
  var fader = document.getElementById("fontSizeFader");
  var faderValue = document.getElementById("fontSizeValue");
  var saved = null;
  try { saved = localStorage.getItem("calibre.reader.fontSize"); } catch (e) { saved = null; }
  if (saved) fader.value = saved;
  faderValue.textContent = fader.value + "%";
  fader.addEventListener("input", function () { faderValue.textContent = fader.value + "%"; });
  fader.addEventListener("change", function () {
    if (rendition()) rendition().themes.fontSize(fader.value + "%");
    store("calibre.reader.fontSize", fader.value);
  });

  // Toolbar "buttons" are anchors bound by the reader library: make them keyboard-operable.
  document.addEventListener("keydown", function (e) {
    var t = e.target;
    if ((e.key === "Enter" || e.key === " ") && t.matches && t.matches("[role='button'][tabindex],[role='tab'][tabindex]")) {
      e.preventDefault();
      t.click();
    }
    if (e.key === "Escape") {
      var modal = document.getElementById("settings-modal");
      if (modal.classList.contains("md-show")) modal.querySelector(".closer").click();
      else if (document.getElementById("sidebar").classList.contains("open")) document.getElementById("slider").click();
    }
  });

  // Apply the saved theme to the chrome right away, before the book loads.
  var theme = null;
  try { theme = localStorage.getItem("calibre.reader.theme"); } catch (e) { theme = null; }
  root.setAttribute("data-reader-theme", window.themes[theme] ? theme : "lightTheme");
  function stored(key, fallback) {
    try { return localStorage.getItem(key) || fallback; } catch (e) { return fallback; }
  }
  mark("themes", root.getAttribute("data-reader-theme"));
  mark("font", stored("calibre.reader.font", "default"));
  mark("layout", stored("calibre.reader.spread", "spread"));
})();
