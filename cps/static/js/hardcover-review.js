// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Hardcover match review: accept a candidate, skip, reject, or reject everything.
(function () {
  "use strict";
  var CWA = window.CWA;
  var list = document.getElementById("hc-matches");
  if (!CWA || !list) return;
  var T = JSON.parse(document.getElementById("hc-i18n").textContent);
  var remaining = document.getElementById("hc-remaining");

  function post(url, payload) {
    return CWA.request(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload || {}) })
      .then(function (r) {
        return r.text().then(function (text) {
          var d = {};
          try { d = JSON.parse(text); } catch (e) { d = {}; }
          if (!r.ok || !d.success) throw new Error(d.error || r.statusText);
          return d;
        });
      });
  }
  function updateCount() {
    var n = list.querySelectorAll(".hc-match").length;
    if (!n) { window.location.reload(); return; }
    remaining.textContent = remaining.getAttribute("data-template").replace("%n", n);
  }

  list.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-hc-action]");
    if (!btn) return;
    var card = btn.closest(".hc-match");
    var action = btn.getAttribute("data-hc-action");
    var buttons = card.querySelectorAll("button");
    Array.prototype.forEach.call(buttons, function (b) { b.disabled = true; });
    post(list.getAttribute("data-action-url"), {
      queue_id: parseInt(card.getAttribute("data-queue-id"), 10),
      action: action,
      selected_result_id: btn.getAttribute("data-result-id") || undefined
    }).then(function () {
      CWA.toast(action === "accept" ? T.accepted : action === "reject" ? T.rejected : T.skipped, "success");
      card.remove();
      updateCount();
    }).catch(function (err) {
      Array.prototype.forEach.call(buttons, function (b) { b.disabled = false; });
      CWA.toast(err.message || CWA.t("error"), "error");
    });
  });

  var all = document.getElementById("hc-reject-all");
  if (all) {
    all.addEventListener("click", function () {
      CWA.confirm(T.reject_all_confirm, T.reject_all).then(function (ok) {
        if (!ok) return;
        post(all.getAttribute("data-url")).then(function () { window.location.reload(); })
          .catch(function (err) { CWA.toast(err.message || CWA.t("error"), "error"); });
      });
    });
  }
})();
