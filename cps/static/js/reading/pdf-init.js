// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// pdf.js viewer options. A classic script, so it runs before the viewer module fires the event.
(function () {
  "use strict";
  var cfg = JSON.parse(document.getElementById("pdf-config").textContent);
  window.addEventListener("webviewerloaded", function () {
    var o = window.PDFViewerApplicationOptions;
    o.set("disableAutoFetch", true);
    o.set("disableRange", false);
    o.set("disableStream", true);
    o.set("disablePreferences", true);
    o.set("sidebarViewOnLoad", 0);
    o.set("cMapUrl", cfg.cMapUrl);
    o.set("imageResourcesPath", cfg.imageResourcesPath);
    o.set("workerSrc", cfg.workerSrc);
    o.set("defaultUrl", cfg.defaultUrl);
  });
})();
