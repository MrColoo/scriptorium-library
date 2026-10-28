// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Update dialog, opened from the top-bar button: stops the button's dot once seen and turns the
// automatic release check on or off.
(function () {
  "use strict";
  var CWA = window.CWA;
  var dialog = document.getElementById("update-dialog");
  if (!CWA || !dialog) return;

  document.addEventListener("click", function (e) {
    var trigger = e.target.closest && e.target.closest(".update-trigger");
    if (!trigger || trigger.dataset.seen) return;
    trigger.dataset.seen = "1";
    var dot = trigger.querySelector(".notify-dot");
    if (dot) dot.remove();
    var url = trigger.getAttribute("data-update-seen-url");
    if (url) CWA.request(url, { method: "POST" }).catch(function () {});
  });

  var auto = dialog.querySelector("[data-update-auto]");
  if (auto) {
    auto.addEventListener("change", function () {
      CWA.request(dialog.getAttribute("data-auto-url"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: auto.checked })
      }).then(function (r) { if (!r.ok) throw new Error(r.status); })
        .catch(function () { auto.checked = !auto.checked; CWA.toast(CWA.t("error", "Something went wrong"), "error"); });
    });
  }
})();
