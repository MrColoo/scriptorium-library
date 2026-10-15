// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Automation settings: schedule pickers, metadata provider order, duplicate format ranking.
(function () {
  "use strict";
  var CWA = window.CWA;
  var form = document.getElementById("cwa-settings-form");
  if (!CWA || !form) return;

  function parse(text, fallback) {
    try { var v = JSON.parse(text); return v === null || v === undefined ? fallback : v; } catch (e) { return fallback; }
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  // ---------- Schedules: only the day field that matches the schedule is posted ----------
  Array.prototype.forEach.call(form.querySelectorAll("[data-schedule]"), function (box) {
    var select = box.querySelector("select[name='" + box.getAttribute("data-schedule") + "']");
    function sync() {
      Array.prototype.forEach.call(box.querySelectorAll("[data-schedule-part]"), function (part) {
        var on = part.getAttribute("data-schedule-part") === select.value;
        part.hidden = !on;
        Array.prototype.forEach.call(part.querySelectorAll("input, select"), function (i) { i.disabled = !on; });
      });
    }
    select.addEventListener("change", sync);
    sync();
  });

  // ---------- Sortable lists ----------
  function makeSortable(list, onChange) {
    var dragging = null;
    list.addEventListener("dragstart", function (e) {
      dragging = e.target.closest("[data-key]");
      if (!dragging) return;
      dragging.classList.add("sortable-ghost");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", dragging.getAttribute("data-key"));
    });
    list.addEventListener("dragend", function () {
      if (dragging) dragging.classList.remove("sortable-ghost");
      dragging = null;
      onChange();
    });
    list.addEventListener("dragover", function (e) {
      if (!dragging) return;
      e.preventDefault();
      var over = e.target.closest("[data-key]");
      if (!over || over === dragging) return;
      var r = over.getBoundingClientRect();
      list.insertBefore(dragging, e.clientY > r.top + r.height / 2 ? over.nextSibling : over);
    });
    list.addEventListener("keydown", function (e) {
      var item = e.target.closest("[data-key]");
      if (!item || !e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
      e.preventDefault();
      if (e.key === "ArrowUp" && item.previousElementSibling) list.insertBefore(item, item.previousElementSibling);
      if (e.key === "ArrowDown" && item.nextElementSibling) list.insertBefore(item.nextElementSibling, item);
      item.focus();
      onChange();
    });
  }
  function item(key, label) {
    var li = el("li", "sortable-item");
    li.setAttribute("draggable", "true");
    li.tabIndex = 0;
    li.setAttribute("data-key", key);
    li.appendChild(CWA.icon("drag", "faint"));
    li.appendChild(el("span", "grow", label));
    return li;
  }

  // ---------- Metadata providers ----------
  var providers = document.getElementById("provider-list");
  if (providers) {
    var hierarchyInput = document.getElementById("metadata_provider_hierarchy_hidden");
    var enabledInput = document.getElementById("metadata_providers_enabled_hidden");
    var hierarchy = parse(providers.getAttribute("data-hierarchy"), []);
    var enabled = parse(providers.getAttribute("data-enabled"), {});
    var write = function () {
      var keys = Array.prototype.map.call(providers.querySelectorAll("[data-key]"), function (li) { return li.getAttribute("data-key"); });
      hierarchyInput.value = JSON.stringify(keys);
      var map = {};
      Array.prototype.forEach.call(providers.querySelectorAll("[data-key]"), function (li) {
        map[li.getAttribute("data-key")] = li.querySelector("input").checked;
      });
      enabledInput.value = JSON.stringify(map);
    };
    CWA.request(providers.getAttribute("data-url")).then(function (r) { return r.json(); }).then(function (list) {
      var byId = {};
      list.forEach(function (p) { byId[p.id] = p; });
      var order = hierarchy.filter(function (id) { return byId[id]; });
      list.forEach(function (p) { if (order.indexOf(p.id) === -1) order.push(p.id); });
      order.forEach(function (id) {
        var p = byId[id];
        var li = item(id, p.name);
        var box = el("input", "switch");
        box.type = "checkbox";
        box.checked = Object.prototype.hasOwnProperty.call(enabled, id) ? !!enabled[id] : p.globally_enabled !== false;
        box.setAttribute("aria-label", p.name);
        box.addEventListener("change", write);
        li.appendChild(box);
        providers.appendChild(li);
      });
      write();
    }).catch(function () {});
    makeSortable(providers, write);
  }

  // ---------- Duplicate format priority ----------
  var formats = document.getElementById("format-priority-list");
  if (formats) {
    var input = document.getElementById("duplicate_format_priority");
    var ranking = parse(formats.getAttribute("data-value"), {});
    Object.keys(ranking).sort(function (a, b) { return ranking[b] - ranking[a]; }).forEach(function (fmt) {
      formats.appendChild(item(fmt, fmt));
    });
    var writeFormats = function () {
      var result = {};
      var items = formats.querySelectorAll("[data-key]");
      Array.prototype.forEach.call(items, function (li, i) {
        // Keep scores in the 100…10 range the server expects, highest first.
        result[li.getAttribute("data-key")] = Math.max(10, 100 - i * 5);
      });
      input.value = JSON.stringify(result);
    };
    makeSortable(formats, writeFormats);
  }

  // ---------- The target format is always kept and never ignored ----------
  var target = document.getElementById("auto_convert_target_format");
  function syncTarget() {
    Array.prototype.forEach.call(form.querySelectorAll("[data-format]"), function (box) {
      var isTarget = box.getAttribute("data-format") === target.value;
      var retained = box.name.indexOf("convert_retained_") === 0;
      box.disabled = isTarget;
      if (isTarget) box.checked = retained;
    });
  }
  if (target) { target.addEventListener("change", syncTarget); syncTarget(); }

  // ---------- Reset confirmation ----------
  form.addEventListener("submit", function (e) {
    var btn = e.submitter;
    if (!btn || !btn.hasAttribute("data-defaults-confirm") || form.dataset.resetConfirmed) return;
    e.preventDefault();
    CWA.confirm(btn.getAttribute("data-defaults-confirm"), btn.textContent.trim()).then(function (ok) {
      if (!ok) return;
      form.dataset.resetConfirmed = "1";
      var hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "submit_button";
      hidden.value = btn.value;
      form.appendChild(hidden);
      form.submit();
    });
  });
})();
