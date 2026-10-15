// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Calibre library location: validate the new path, confirm a change, then submit.
(function () {
  "use strict";
  var CWA = window.CWA;
  var form = document.getElementById("db-config-form");
  if (!CWA || !form) return;
  var S = JSON.parse(document.getElementById("db-config-i18n").textContent);
  var confirmed = false;
  form.addEventListener("submit", function (e) {
    if (confirmed) return;
    e.preventDefault();
    var body = new URLSearchParams({ config_calibre_dir: form.querySelector("#config_calibre_dir").value });
    CWA.request(form.getAttribute("data-check-url"), { method: "POST", body: body })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.change) { confirmed = true; form.submit(); return; }
        if (!data.valid) { CWA.toast(S.invalid, "error"); return; }
        CWA.confirm(S.change, S.ok).then(function (ok) {
          if (ok) { confirmed = true; form.submit(); }
        });
      })
      .catch(function () { CWA.toast(CWA.t("error"), "error"); });
  });
})();
