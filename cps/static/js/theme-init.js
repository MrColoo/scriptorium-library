// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Loaded synchronously in <head> so the page never flashes the wrong theme.
(function () {
  var stored = null;
  try { stored = localStorage.getItem("cwa-theme"); } catch (e) { /* storage blocked */ }
  var mode = stored === "light" || stored === "dark" ? stored : "system";
  var dark = mode === "dark" || (mode === "system" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme-mode", mode);
})();
