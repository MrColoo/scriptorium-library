// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Users table: bulk delete for the selected rows.
(function () {
  "use strict";
  var CWA = window.CWA;
  var root = document.getElementById("users");
  var bar = document.getElementById("user-bulk");
  if (!CWA || !root || !bar) return;
  var cfg = JSON.parse(document.getElementById("user-table-config").textContent);
  var ids = [];
  root.addEventListener("datatable:selection", function (e) {
    ids = e.detail.ids;
    bar.hidden = !ids.length;
    bar.querySelector("[data-bulk-count]").textContent = cfg.strings.selected.replace("%n", ids.length);
  });
  document.getElementById("user_delete_selection").addEventListener("click", function () {
    CWA.confirm(cfg.bulk.confirm, cfg.bulk.delete).then(function (ok) {
      if (!ok) return;
      var body = new URLSearchParams();
      ids.forEach(function (id) { body.append("userid[]", id); });
      CWA.request(cfg.bulk.delete_url, { method: "POST", body: body }).then(function (r) { return r.json(); }).then(function (d) {
        CWA.toast(d.message || "", d.type === "danger" ? "error" : "success");
        CWA.tables.users.clearSelection();
        CWA.tables.users.reload();
      });
    });
  });
})();
