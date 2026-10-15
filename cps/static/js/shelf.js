// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Shelf page: lock the manual order, and drag-to-reorder on the arrange page.
(function () {
  "use strict";
  var CWA = window.CWA;
  var viewUrl = document.body.getAttribute("data-view-url");

  var lock = document.querySelector("[data-shelf-lock]");
  if (lock && viewUrl) {
    lock.addEventListener("click", function () {
      CWA.request(viewUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shelf: { man: lock.getAttribute("data-shelf-lock") } })
      }).then(function () { window.location.reload(); });
    });
  }

  // Arrange page: native drag and drop plus keyboard (Alt+Arrow) to move items.
  var list = document.querySelector("[data-sortable]");
  if (!list) return;
  var form = list.closest("form");
  var dragging = null;

  function sync() {
    Array.prototype.forEach.call(list.querySelectorAll("[data-book]"), function (item, index) {
      item.querySelector("input").value = String(index + 1);
    });
  }

  list.addEventListener("dragstart", function (e) {
    dragging = e.target.closest("[data-book]");
    if (!dragging) return;
    dragging.classList.add("sortable-ghost");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", dragging.getAttribute("data-book"));
  });
  list.addEventListener("dragend", function () {
    if (dragging) dragging.classList.remove("sortable-ghost");
    dragging = null;
    sync();
  });
  list.addEventListener("dragover", function (e) {
    if (!dragging) return;
    e.preventDefault();
    var over = e.target.closest("[data-book]");
    if (!over || over === dragging) return;
    var rect = over.getBoundingClientRect();
    var after = e.clientY > rect.top + rect.height / 2;
    list.insertBefore(dragging, after ? over.nextSibling : over);
  });
  list.addEventListener("keydown", function (e) {
    var item = e.target.closest("[data-book]");
    if (!item || !e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    if (e.key === "ArrowUp" && item.previousElementSibling) list.insertBefore(item, item.previousElementSibling);
    if (e.key === "ArrowDown" && item.nextElementSibling) list.insertBefore(item.nextElementSibling, item);
    item.focus();
    sync();
  });
  if (form) form.addEventListener("submit", sync);
})();
