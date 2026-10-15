// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Batch services (Convert Library, EPUB Fixer): live log and progress, single-book EPUB fixing.
(function () {
  "use strict";
  var CWA = window.CWA;
  var box = document.querySelector("[data-run-status]");
  if (!CWA || !box) return;
  var S = JSON.parse(box.querySelector("[data-run-i18n]").textContent);
  var log = box.querySelector("[data-run-log]");
  var bar = box.querySelector("[data-run-progress]");
  var badge = box.querySelector("[data-run-state]");
  var timer = null;

  function setState(text, cls) { badge.textContent = text; badge.className = "badge " + (cls || ""); }
  function setProgress(pct) {
    bar.setAttribute("aria-valuenow", String(pct));
    bar.firstElementChild.style.width = pct + "%";
  }
  function poll() {
    CWA.request(box.getAttribute("data-run-status")).then(function (r) { return r.json(); }).then(function (data) {
      var status = data.status || "";
      if (status.trim()) {
        var atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 20;
        log.textContent = status;
        if (atBottom) log.scrollTop = log.scrollHeight;
      }
      if (data.progress && data.progress.total > 0) setProgress(Math.round(data.progress.current / data.progress.total * 100));
      if (/TERMINATED BY USER/i.test(status)) { setState(S.cancelled, "badge--danger"); return; }
      if (/Run Ended:/i.test(status)) { setProgress(100); setState(S.done, "badge--success"); return; }
      if (status.trim()) setState(S.running, "badge--accent");
      timer = setTimeout(poll, 1500);
    }).catch(function () { timer = setTimeout(poll, 5000); });
  }
  poll();

  // Single book (EPUB Fixer page)
  var single = document.getElementById("epub-fixer-single");
  if (!single) return;
  var T = JSON.parse(document.getElementById("epub-fixer-i18n").textContent);
  var input = document.getElementById("epub_fixer_book");
  var results = document.getElementById("epub_fixer_results");
  var selected = null;
  var searchTimer = null;
  input.addEventListener("input", function () {
    selected = null;
    clearTimeout(searchTimer);
    var q = input.value.trim();
    if (q.length < 2) { results.hidden = true; return; }
    searchTimer = setTimeout(function () {
      CWA.request(input.getAttribute("data-search-url") + "?limit=8&offset=0&search=" + encodeURIComponent(q))
        .then(function (r) { return r.json(); }).then(function (data) {
          results.textContent = "";
          (data.rows || []).forEach(function (row) {
            var li = document.createElement("li");
            var b = document.createElement("button");
            b.type = "button";
            b.className = "pick-item";
            b.textContent = row.title + (row.authors ? " — " + row.authors : "");
            b.addEventListener("click", function () {
              selected = row.id;
              input.value = b.textContent;
              results.hidden = true;
            });
            li.appendChild(b);
            results.appendChild(li);
          });
          if (!results.children.length) {
            var none = document.createElement("li");
            none.className = "muted small";
            none.textContent = T.none;
            results.appendChild(none);
          }
          results.hidden = false;
        });
    }, 250);
  });
  single.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!selected) { CWA.toast(T.pick, "error"); return; }
    CWA.request(single.getAttribute("data-run-url"), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ book_id: selected })
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); }).then(function (res) {
      if (!res.ok || !res.d.success) throw new Error(res.d.error || "");
      CWA.toast(T.started, "success");
      clearTimeout(timer);
      poll();
    }).catch(function (err) { CWA.toast(err.message || CWA.t("error"), "error"); });
  });
})();
