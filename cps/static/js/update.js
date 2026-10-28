// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Update dialog: opened from the top-bar button. Starts a safe update (backup, then the update service)
// and follows it until the new version answers, then reloads.
(function () {
  "use strict";
  var CWA = window.CWA;
  var dialog = document.getElementById("update-dialog");
  if (!CWA || !dialog) return;

  var installed = dialog.getAttribute("data-installed");
  var progress = dialog.querySelector("[data-update-progress]");
  var errorBox = dialog.querySelector("[data-update-error]");
  var startBtn = dialog.querySelector("[data-update-start]");
  var running = false;
  var STEPS = ["backing-up", "updating", "restarting", "done"];
  var POLL_MS = 3000, GIVE_UP_MS = 10 * 60 * 1000;

  // Opening the dialog once stops the dot on the top-bar button for this version.
  document.addEventListener("click", function (e) {
    var trigger = e.target.closest && e.target.closest(".update-trigger");
    if (!trigger || trigger.dataset.seen) return;
    trigger.dataset.seen = "1";
    var dot = trigger.querySelector(".notify-dot");
    if (dot) dot.remove();
    var url = trigger.getAttribute("data-update-seen-url");
    if (url) CWA.request(url, { method: "POST" }).catch(function () {});
  });

  var manualBtn = dialog.querySelector("[data-update-manual-show]");
  if (manualBtn) {
    manualBtn.addEventListener("click", function () {
      var manual = dialog.querySelector("[data-update-manual]");
      if (manual) { manual.hidden = false; manual.scrollIntoView({ block: "nearest" }); }
    });
  }

  var auto = dialog.querySelector("[data-update-auto]");
  if (auto) {
    auto.addEventListener("change", function () {
      CWA.request(dialog.getAttribute("data-auto-url"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: auto.checked })
      }).catch(function () { auto.checked = !auto.checked; CWA.toast(CWA.t("error", "Something went wrong"), "error"); });
    });
  }

  // While updating, the dialog cannot be dismissed by accident.
  dialog.addEventListener("cancel", function (e) { if (running) e.preventDefault(); });

  function step(name) {
    var reached = false;
    STEPS.forEach(function (key) {
      var li = progress.querySelector('[data-step="' + key + '"]');
      if (!li) return;
      li.classList.toggle("is-current", key === name);
      li.classList.toggle("is-done", !reached && key !== name);
      if (key === name) reached = true;
    });
  }

  function fail(message) {
    running = false;
    dialog.removeAttribute("data-static");
    errorBox.hidden = false;
    errorBox.textContent = message;
    Array.prototype.forEach.call(dialog.querySelectorAll("[data-dialog-close]"), function (b) { b.disabled = false; });
    if (startBtn) { startBtn.disabled = false; startBtn.classList.remove("is-loading"); }
  }

  function poll(began) {
    if (Date.now() - began > GIVE_UP_MS) {
      fail(dialog.getAttribute("data-timeout") || "The update is taking longer than expected. Check your server.");
      return;
    }
    fetch(dialog.getAttribute("data-status-url"), { credentials: "same-origin", cache: "no-store", headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) {
        if (!r.ok) throw new Error("status " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (data.version && data.version !== installed) {
          step("done");
          window.setTimeout(function () { window.location.reload(); }, 1500);
          return;
        }
        if (data.state === "failed") { fail(data.error || ""); return; }
        if (data.state === "restarting") step("restarting");
        window.setTimeout(function () { poll(began); }, POLL_MS);
      })
      .catch(function () {
        // The server is down while the container restarts: that is expected.
        step("restarting");
        window.setTimeout(function () { poll(began); }, POLL_MS);
      });
  }

  if (startBtn) {
    startBtn.addEventListener("click", function () {
      if (running) return;
      running = true;
      dialog.setAttribute("data-static", "");
      errorBox.hidden = true;
      progress.hidden = false;
      startBtn.disabled = true;
      startBtn.classList.add("is-loading");
      Array.prototype.forEach.call(dialog.querySelectorAll("[data-dialog-close]"), function (b) { b.disabled = true; });
      step("backing-up");
      CWA.request(dialog.getAttribute("data-start-url"), { method: "POST" })
        .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
        .then(function (res) {
          if (!res.ok || !res.data.ok) { fail(res.data.message || res.data.error || ""); return; }
          step("updating");
          poll(Date.now());
        })
        .catch(function () { fail(CWA.t("error", "Something went wrong")); });
    });
  }
})();
