// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Duplicate badge in the sidebar, plus a one-off notice when new duplicate groups show up.
(function () {
  "use strict";
  var CWA = window.CWA;
  var boot = document.getElementById("duplicate-notification-data");
  if (!CWA || !boot) return;

  var STATUS_URL = boot.getAttribute("data-status-url");
  var PAGE_URL = boot.getAttribute("data-page-url");
  var SEEN_KEY = "cwa_duplicates_last_count";
  var POLL_MS = 5000, POLL_MAX = 60, FOCUS_MIN_MS = 30000, BACKGROUND_MS = 5 * 60 * 1000;
  var pollTimer = null, polls = 0, lastFetch = 0;
  var onDuplicatesPage = window.location.pathname.replace(/\/+$/, "") === PAGE_URL.replace(/\/+$/, "");

  function storage(key, value) {
    try {
      if (value === undefined) return window.sessionStorage.getItem(key);
      window.sessionStorage.setItem(key, value);
    } catch (e) { return null; }
  }
  function updateBadge(count) {
    var badge = document.getElementById("duplicate-count-badge");
    if (!badge) return;
    badge.hidden = !(count > 0);
    badge.textContent = count > 99 ? "99+" : String(count || 0);
  }
  function notify(count) {
    var seen = parseInt(storage(SEEN_KEY) || "0", 10);
    storage(SEEN_KEY, String(count));
    if (onDuplicatesPage || count <= seen) return;
    var t = CWA.toast(CWA.t("duplicates_found", "Possible duplicates found: %d groups.").replace("%d", count), "info", 10000);
    if (!t) return;
    var link = document.createElement("a");
    link.href = PAGE_URL;
    link.textContent = " " + CWA.t("review", "Review");
    t.querySelector(".toast-body").appendChild(link);
  }
  function handle(data) {
    if (!data || data.success === false) return;
    if (!window.CWADuplicateScanActive) updateBadge(data.count);
    document.dispatchEvent(new CustomEvent("cwa:duplicates-status", { detail: data }));
    if (data.enabled && !data.needs_full_scan) notify(data.count || 0);
    // A pending refresh (e.g. after an import) changes the results soon; a full scan only runs on demand.
    var pending = data.stale && !data.needs_full_scan;
    if ((pending || window.CWADuplicateScanActive) && polls < POLL_MAX) {
      clearTimeout(pollTimer);
      pollTimer = setTimeout(function () { polls += 1; fetchStatus(); }, POLL_MS);
    } else {
      pollTimer = null;
    }
  }
  function fetchStatus() {
    lastFetch = Date.now();
    return CWA.request(STATUS_URL).then(function (r) { return r.ok ? r.json() : null; }).then(handle).catch(function () {});
  }

  var initial = {};
  try { initial = JSON.parse(boot.textContent) || {}; } catch (e) { initial = {}; }
  if (initial.cached) handle({ success: true, enabled: !!initial.enabled, count: Number(initial.count || 0), stale: !!initial.stale });
  else fetchStatus();

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && Date.now() - lastFetch >= FOCUS_MIN_MS) fetchStatus();
  });
  setInterval(function () {
    if (!document.hidden && !pollTimer && Date.now() - lastFetch >= BACKGROUND_MS) fetchStatus();
  }, BACKGROUND_MS);

  window.CWADuplicates = { updateBadge: updateBadge, fetchStatus: fetchStatus };
})();
