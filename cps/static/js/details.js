// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Book page: rating, inline tags, send to eReader, description expander.
(function () {
  "use strict";
  var CWA = window.CWA;
  var page = document.querySelector(".detail");
  if (!CWA || !page) return;
  var bookId = page.getAttribute("data-book-id");

  function post(url, params) {
    return CWA.request(url, { method: "POST", body: new URLSearchParams(params) }).then(function (res) {
      if (!res.ok) return res.text().then(function (t) { throw new Error(t || res.statusText); });
      var type = res.headers.get("content-type") || "";
      return type.indexOf("json") !== -1 ? res.json() : res.text();
    });
  }

  // Description: only offer "show more" when the text is actually cut off.
  var description = document.getElementById("book-description");
  if (description) {
    var toggle = document.querySelector('[data-clamp-toggle="#book-description"]');
    if (toggle && description.scrollHeight > description.clientHeight + 4) toggle.hidden = false;
  }

  // Rating
  var stars = document.querySelector(".star-input");
  if (stars) {
    var paint = function (value) {
      Array.prototype.forEach.call(stars.querySelectorAll("button"), function (b) {
        var v = parseInt(b.getAttribute("data-value"), 10);
        b.setAttribute("aria-checked", v === value ? "true" : "false");
        var svg = b.querySelector(".icon");
        svg.classList.toggle("is-on", v <= value);
        svg.classList.toggle("is-off", v > value);
      });
    };
    stars.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-value]");
      if (!btn) return;
      var previous = parseInt(stars.getAttribute("data-value"), 10) || 0;
      var value = parseInt(btn.getAttribute("data-value"), 10);
      if (value === previous) value = 0; // clicking the current rating clears it
      paint(value);
      post(stars.getAttribute("data-rating-url"), { pk: bookId, value: value ? String(value) : "" }).then(function () {
        stars.setAttribute("data-value", String(value));
      }).catch(function () {
        paint(previous);
        CWA.toast(CWA.t("error"), "error");
      });
    });
  }

  // Tags
  var tags = document.getElementById("book-tags");
  if (tags && tags.hasAttribute("data-tags-url")) {
    var currentTags = function () {
      return Array.prototype.map.call(tags.querySelectorAll("[data-tag]"), function (el) { return el.getAttribute("data-tag"); });
    };
    var saveTags = function (list) {
      return post(tags.getAttribute("data-tags-url"), { pk: bookId, value: list.join(",") })
        .then(function () { window.location.reload(); })
        .catch(function (err) { CWA.toast(err.message || CWA.t("error"), "error"); });
    };
    tags.addEventListener("click", function (e) {
      var remove = e.target.closest("[data-tag-remove]");
      if (!remove) return;
      e.preventDefault();
      var name = remove.closest("[data-tag]").getAttribute("data-tag");
      saveTags(currentTags().filter(function (t) { return t !== name; }));
    });
    var addForm = tags.querySelector("[data-tag-add]");
    if (addForm) {
      addForm.addEventListener("click", function () { addForm.querySelector("input").focus(); });
      addForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var input = addForm.querySelector("input");
        var added = input.value.split(",").map(function (t) { return t.trim(); }).filter(Boolean);
        if (!added.length) return;
        var list = currentTags();
        added.forEach(function (t) { if (list.indexOf(t) === -1) list.push(t); });
        saveTags(list);
      });
    }
  }

  // Send to eReader
  var sendForm = document.querySelector("[data-send-form]");
  if (sendForm) {
    sendForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var emails = Array.prototype.filter.call(sendForm.querySelectorAll('input[name="selected_email"]'), function (c) { return c.checked; })
        .map(function (c) { return c.value; });
      var extra = sendForm.querySelector('input[name="custom_emails"]');
      if (extra && extra.value.trim()) {
        extra.value.split(",").forEach(function (m) { if (m.trim()) emails.push(m.trim()); });
      }
      if (!emails.length) {
        CWA.toast(CWA.t("no_email", "Choose at least one address"), "error");
        return;
      }
      var choice = sendForm.querySelector('select[name="format_selection"]').value.split("|");
      var submit = sendForm.querySelector('[type="submit"]');
      submit.classList.add("is-loading");
      post(sendForm.getAttribute("action"), { selected_emails: emails.join(","), book_format: choice[0], convert: choice[1] || "0" })
        .then(function (data) {
          submit.classList.remove("is-loading");
          var result = Array.isArray(data) ? data[0] : data;
          if (result && result.type === "success") {
            CWA.closeDialog(sendForm.closest("dialog"));
            CWA.toast(result.message, "success");
          } else {
            CWA.toast((result && result.message) || CWA.t("error"), "error");
          }
        })
        .catch(function () {
          submit.classList.remove("is-loading");
          CWA.toast(CWA.t("error"), "error");
        });
    });
  }
})();
