// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Server log viewer: loads the selected log as plain text.
(function () {
  "use strict";
  var box = document.getElementById("renderer");
  var CWA = window.CWA;
  if (!box || !CWA) return;
  function load() {
    var radio = document.querySelector("#log_group input:checked");
    if (!radio) return;
    box.textContent = "…";
    CWA.request(radio.getAttribute("data-log-url")).then(function (r) { return r.text(); }).then(function (text) {
      box.textContent = text;
      box.scrollTop = box.scrollHeight;
    }).catch(function () { box.textContent = CWA.t("error"); });
  }
  document.addEventListener("change", function (e) { if (e.target.name === "log_radio") load(); });
  load();
})();
