// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Allowed/denied tags and custom column values (admin). Talks to /ajax/{list,add,delete}restriction.
(function () {
  "use strict";
  var CWA = window.CWA;
  var dialog = document.getElementById("restrictions-dialog");
  if (!CWA || !dialog) return;
  var strings = {};
  try { strings = JSON.parse(document.getElementById("restrictions-i18n").textContent); } catch (e) { strings = {}; }
  var list = dialog.querySelector("[data-restrictions-list]");
  var empty = dialog.querySelector("[data-restrictions-empty]");
  var form = dialog.querySelector("[data-restrictions-form]");
  var state = { type: 0, user: 0 };

  function url(kind) {
    return dialog.getAttribute("data-" + kind + "-url") + "/" + state.type + "/" + state.user;
  }

  function render(items) {
    list.textContent = "";
    items.forEach(function (item) {
      var li = document.createElement("li");
      li.className = "restriction-item";
      var badge = document.createElement("span");
      var allowed = String(item.id).charAt(0) === "a";
      badge.className = "badge " + (allowed ? "badge--success" : "badge--danger");
      badge.textContent = allowed ? (strings.allow || "Allow") : (strings.deny || "Deny");
      var text = document.createElement("span");
      text.className = "grow break";
      text.textContent = item.Element;
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn-ghost btn-icon btn-sm";
      remove.setAttribute("aria-label", (strings.remove || "Remove") + " " + item.Element);
      remove.appendChild(CWA.icon("x"));
      remove.addEventListener("click", function () {
        var body = new URLSearchParams({ id: item.id, Element: item.Element, type: item.type });
        CWA.request(url("delete"), { method: "POST", body: body }).then(load);
      });
      li.appendChild(badge);
      li.appendChild(text);
      li.appendChild(remove);
      list.appendChild(li);
    });
    empty.hidden = items.length !== 0;
  }

  function load() {
    return CWA.request(url("list")).then(function (r) { return r.json(); }).then(render)
      .catch(function () { CWA.toast(CWA.t("error"), "error"); });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-restrictions-open]");
    if (!btn) return;
    e.preventDefault();
    state.type = parseInt(btn.getAttribute("data-restrictions-open"), 10) || 0;
    state.user = parseInt(btn.getAttribute("data-restrictions-user"), 10) || 0;
    dialog.querySelector("#restrictions-title").textContent = btn.getAttribute("data-restrictions-title") || btn.textContent.trim();
    list.textContent = "";
    CWA.openDialog(dialog);
    load();
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var input = form.querySelector("input[name=add_element]");
    if (!input.value.trim()) return;
    var body = new URLSearchParams({ add_element: input.value.trim() });
    body.set(e.submitter && e.submitter.name === "submit_deny" ? "submit_deny" : "submit_allow", "1");
    CWA.request(url("add"), { method: "POST", body: body }).then(function (r) {
      if (!r.ok) throw new Error(r.statusText);
      input.value = "";
      return load();
    }).catch(function () { CWA.toast(CWA.t("error"), "error"); });
  });
})();
