// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Welcome tour for a new account: a few steps in a dialog. Closing it, however, marks it as seen.
(function () {
  "use strict";
  var CWA = window.CWA;
  var dialog = document.getElementById("welcome-dialog");
  if (!CWA || !dialog) return;

  var steps = Array.prototype.slice.call(dialog.querySelectorAll("[data-welcome-step]"));
  var dots = Array.prototype.slice.call(dialog.querySelectorAll(".welcome-dots i"));
  var next = dialog.querySelector("[data-welcome-next]");
  var back = dialog.querySelector("[data-welcome-back]");
  var skip = dialog.querySelector("[data-welcome-skip]");
  var current = 0;
  var reported = false;

  function show(index, direction) {
    current = Math.max(0, Math.min(steps.length - 1, index));
    steps.forEach(function (step, i) {
      step.hidden = i !== current;
      step.classList.toggle("is-back", i === current && direction < 0);
    });
    dots.forEach(function (dot, i) { dot.classList.toggle("is-active", i === current); });
    back.hidden = current === 0;
    skip.hidden = current === steps.length - 1;
    var last = current === steps.length - 1;
    next.textContent = next.getAttribute(current === 0 ? "data-label-start" : (last ? "data-label-done" : "data-label-next"));
    next.focus();
  }

  function done() {
    if (reported) return;
    reported = true;
    var url = dialog.getAttribute("data-done-url");
    if (url) CWA.request(url, { method: "POST", keepalive: true }).catch(function () { /* shown again next time */ });
  }

  next.addEventListener("click", function () {
    if (current === steps.length - 1) CWA.closeDialog(dialog);
    else show(current + 1, 1);
  });
  back.addEventListener("click", function () { show(current - 1, -1); });
  skip.addEventListener("click", function () { CWA.closeDialog(dialog); });
  dialog.addEventListener("close", done);
  dialog.addEventListener("keydown", function (event) {
    if (event.key === "ArrowRight" && current < steps.length - 1) { event.preventDefault(); show(current + 1, 1); }
    if (event.key === "ArrowLeft" && current > 0) { event.preventDefault(); show(current - 1, -1); }
  });

  function open() {
    show(0, 1);
    CWA.openDialog(dialog);
    next.focus();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", open);
  else open();
})();
