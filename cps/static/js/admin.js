// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Admin page: restart the server and reload once it answers again.
(function () {
  "use strict";
  var CWA = window.CWA;
  var btn = document.querySelector("[data-admin-restart]");
  if (!CWA || !btn) return;
  var S = JSON.parse(document.getElementById("admin-i18n").textContent);
  btn.addEventListener("click", function () {
    CWA.confirm(S.restart_confirm, S.restart, false).then(function (ok) {
      if (!ok) return;
      btn.classList.add("is-loading");
      CWA.request(btn.getAttribute("data-url"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ parameter: 0 })
      }).then(function () {
        CWA.toast(S.restarting, "info", 0);
        var started = Date.now();
        var poll = setInterval(function () {
          fetch(window.location.href, { credentials: "same-origin", cache: "no-store" }).then(function (r) {
            if (r.ok && Date.now() - started > 3000) { clearInterval(poll); window.location.reload(); }
          }).catch(function () {});
        }, 2000);
      }).catch(function () { btn.classList.remove("is-loading"); });
    });
  });
})();
