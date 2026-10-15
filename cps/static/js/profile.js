// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Profile / user settings: reorderable lists, password strength, profile picture.
(function () {
  "use strict";

  // ---------- Reorderable lists that write into a hidden input ----------
  function setupOrderList(list) {
    var input = document.getElementById(list.getAttribute("data-order-list"));
    var hiddenInput = list.hasAttribute("data-hidden-input") ? document.getElementById(list.getAttribute("data-hidden-input")) : null;
    var modeSelect = list.hasAttribute("data-order-mode") ? document.getElementById(list.getAttribute("data-order-mode")) : null;
    var dragging = null;

    function write() {
      var items = Array.prototype.slice.call(list.querySelectorAll("[data-key]"));
      if (input) input.value = items.map(function (i) { return i.getAttribute("data-key"); }).join(",");
      if (hiddenInput) {
        hiddenInput.value = items.filter(function (i) {
          var box = i.querySelector("[data-visible]");
          return box && !box.checked;
        }).map(function (i) { return i.getAttribute("data-key"); }).join(",");
      }
    }
    function enabled() { return !modeSelect || modeSelect.value === "manual"; }
    function syncMode() {
      var on = enabled();
      list.classList.toggle("is-disabled", !on);
      Array.prototype.forEach.call(list.querySelectorAll("[data-key]"), function (i) { i.setAttribute("draggable", on ? "true" : "false"); });
    }

    list.addEventListener("dragstart", function (e) {
      if (!enabled()) { e.preventDefault(); return; }
      dragging = e.target.closest("[data-key]");
      if (!dragging) return;
      dragging.classList.add("sortable-ghost");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", dragging.getAttribute("data-key"));
    });
    list.addEventListener("dragend", function () {
      if (dragging) dragging.classList.remove("sortable-ghost");
      dragging = null;
      write();
    });
    list.addEventListener("dragover", function (e) {
      if (!dragging) return;
      e.preventDefault();
      var over = e.target.closest("[data-key]");
      if (!over || over === dragging) return;
      var rect = over.getBoundingClientRect();
      list.insertBefore(dragging, e.clientY > rect.top + rect.height / 2 ? over.nextSibling : over);
    });
    list.addEventListener("keydown", function (e) {
      var item = e.target.closest("[data-key]");
      if (!item || !enabled() || !e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
      e.preventDefault();
      if (e.key === "ArrowUp" && item.previousElementSibling) list.insertBefore(item, item.previousElementSibling);
      if (e.key === "ArrowDown" && item.nextElementSibling) list.insertBefore(item.nextElementSibling, item);
      item.focus();
      write();
    });
    list.addEventListener("change", write);
    if (modeSelect) modeSelect.addEventListener("change", syncMode);
    syncMode();
    write();
  }
  Array.prototype.forEach.call(document.querySelectorAll("[data-order-list]"), setupOrderList);

  // ---------- Password strength (guidance only; the server enforces the policy) ----------
  var password = document.querySelector("[data-password-strength]");
  var meter = document.querySelector("[data-strength]");
  if (password && meter) {
    password.addEventListener("input", function () {
      var v = password.value;
      var score = 0;
      if (v.length >= 8) score++;
      if (v.length >= 12) score++;
      if (/[a-z]/.test(v) && /[A-Z]/.test(v)) score++;
      if (/\d/.test(v) && /[^A-Za-z0-9]/.test(v)) score++;
      meter.setAttribute("data-score", v ? String(Math.max(1, score)) : "0");
    });
  }

  // ---------- Custom profile picture (CWA user_profiles.json) ----------
  var avatar = document.getElementById("user-profile-picture");
  var picturesUrl = document.body.getAttribute("data-profile-pictures-url");
  if (avatar && picturesUrl) {
    fetch(picturesUrl, { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : {}; }).then(function (profiles) {
      var src = profiles && profiles[avatar.getAttribute("data-username")];
      if (typeof src !== "string" || !/^data:image\/(png|jpe?g|gif|webp);base64,/.test(src)) return;
      var img = document.createElement("img");
      img.src = src;
      img.alt = "";
      avatar.textContent = "";
      avatar.appendChild(img);
    }).catch(function () {});
  }
})();
