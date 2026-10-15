// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Magic link: poll until another device approves this login, then go to the library.
(function () {
  "use strict";
  var el = document.getElementById("verify_url");
  if (!el || !window.CWA) return;
  var timer = setInterval(function () {
    window.CWA.request(el.getAttribute("data-verify-url"), {
      method: "POST",
      body: new URLSearchParams({ token: el.getAttribute("data-token") })
    }).then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    }).then(function (r) {
      if (r.ok && r.data.status === "success") {
        clearInterval(timer);
        window.location.href = el.getAttribute("data-home-url") || "/";
      } else if (!r.ok) {
        clearInterval(timer);
        window.CWA.toast(r.data.message || window.CWA.t("error"), "error", 0);
      }
    }).catch(function () {});
  }, 4000);
})();
