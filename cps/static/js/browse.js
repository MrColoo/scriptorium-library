// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Index pages (authors, series, tags…): text filter, initial filter, sort direction, view switch.
(function () {
  "use strict";
  var CWA = window.CWA;
  var list = document.querySelector("[data-list]");
  var viewUrl = document.body.getAttribute("data-view-url");

  function saveView(key, values) {
    if (!viewUrl) return Promise.resolve();
    var payload = {};
    payload[key] = values;
    return CWA.request(viewUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  }

  function fold(text) {
    return (text || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  if (list) {
    var items = Array.prototype.slice.call(list.querySelectorAll("[data-item]"));
    var empty = document.querySelector("[data-list-empty]");
    var filterInput = document.querySelector("[data-list-filter]");
    var letter = "";

    var apply = function () {
      var q = fold(filterInput ? filterInput.value.trim() : "");
      var shown = 0;
      items.forEach(function (item) {
        var key = item.getAttribute("data-key") || "";
        var text = fold(item.textContent + " " + key);
        var ok = (!q || text.indexOf(q) !== -1) && (!letter || key.toUpperCase().indexOf(letter) === 0);
        item.hidden = !ok;
        if (ok) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    };

    if (filterInput) filterInput.addEventListener("input", apply);

    document.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-letter]");
      if (!btn) return;
      letter = btn.getAttribute("data-letter");
      Array.prototype.forEach.call(document.querySelectorAll("[data-letter]"), function (b) {
        b.classList.toggle("is-active", b === btn);
      });
      apply();
    });
  }

  // Sort direction: reverse in place, remember the choice for next time.
  var sortBtn = document.querySelector("[data-sort-dir]");
  if (sortBtn && list) {
    sortBtn.addEventListener("click", function () {
      var dir = sortBtn.getAttribute("data-sort-dir") === "asc" ? "desc" : "asc";
      sortBtn.setAttribute("data-sort-dir", dir);
      sortBtn.querySelector("span").textContent = dir === "asc" ? "A–Z" : "Z–A";
      var nodes = Array.prototype.slice.call(list.querySelectorAll("[data-item]"));
      nodes.reverse().forEach(function (n) { list.appendChild(n); });
      saveView(sortBtn.getAttribute("data-sort-key"), { dir: dir });
    });
  }

  // Authors: show "Last, First" instead of "First Last".
  var nameBtn = document.querySelector("[data-author-name-toggle]");
  if (nameBtn && list) {
    nameBtn.addEventListener("click", function () {
      var sorted = nameBtn.getAttribute("aria-pressed") !== "true";
      nameBtn.setAttribute("aria-pressed", sorted ? "true" : "false");
      Array.prototype.forEach.call(list.querySelectorAll("[data-name]"), function (item) {
        item.querySelector(".grow").textContent = sorted ? item.getAttribute("data-sortname") : item.getAttribute("data-name");
      });
    });
  }

  // Series: grid of covers or a plain list.
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-series-view]");
    if (!btn || btn.getAttribute("aria-pressed") === "true") return;
    saveView("series", { series_view: btn.getAttribute("data-series-view") }).then(function () {
      window.location.reload();
    });
  });
})();
