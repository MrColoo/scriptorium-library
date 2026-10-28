// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Shows the release notes of the installed version once: opening the dialog marks them as seen.
(function () {
  "use strict";
  var CWA = window.CWA;
  var dialog = document.getElementById("whats-new-dialog");
  if (!CWA || !dialog) return;

  function show() {
    CWA.openDialog(dialog);
    var url = dialog.getAttribute("data-seen-url");
    if (url) CWA.request(url, { method: "POST" }).catch(function () { /* shown again next time */ });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", show);
  else show();
})();
