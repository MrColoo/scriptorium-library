// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Comic reader bootstrap: kthoom reads window.calibre and the global currentImage.
(function () {
  "use strict";
  var cfg = JSON.parse(document.getElementById("reader-config").textContent);
  window.calibre = {
    bookmarkUrl: cfg.bookmarkUrl,
    bookmark: cfg.bookmark || "",
    useBookmarks: cfg.useBookmarks === true
  };
  function start() {
    if (window.calibre.useBookmarks) {
      // Comic bookmarks are page numbers; anything else is ignored (never evaluated).
      var page = parseInt(window.calibre.bookmark, 10);
      window.currentImage = isNaN(page) || page < 0 ? 0 : page;
    }
    window.init(cfg.bookUrl);
  }
  if (document.readyState === "complete") start();
  else window.addEventListener("load", start);
})();
