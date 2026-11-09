// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// First start: how strong the new password is, and which of the password rules it meets.
// Guidance only: the server checks the rules again.
(function () {
  "use strict";
  var input = document.querySelector("[data-setup-password]");
  var meter = document.querySelector("[data-strength]");
  var label = document.querySelector("[data-strength-label]");
  if (!input || !meter || !label) return;

  var text = {};
  try { text = JSON.parse(document.getElementById("setup-i18n").textContent || "{}"); } catch (e) { text = {}; }

  var COMMON = ["password", "passwort", "123456", "qwerty", "azerty", "admin", "letmein", "welcome", "iloveyou",
                "scriptorium", "calibre", "library", "books", "abc123", "111111", "000000"];
  var rules = {
    length: function (v, li) { return v.length >= parseInt(li.getAttribute("data-min") || "0", 10); },
    number: function (v) { return /\d/.test(v); },
    lower: function (v) { return /\p{Ll}/u.test(v); },
    upper: function (v) { return /\p{Lu}/u.test(v); },
    letter: function (v) { return /\p{L}/u.test(v); },
    special: function (v) { return /[^\p{L}\s0-9]/u.test(v); }
  };
  var minimum = 8;
  var lengthRule = document.querySelector('[data-rule="length"]');
  if (lengthRule) minimum = parseInt(lengthRule.getAttribute("data-min") || "8", 10) || 8;

  // A rough estimate of how hard the password is to guess: the length, the kinds of characters,
  // and less for repeats, runs like "abcd" or "1234", and well-known passwords.
  function score(v) {
    if (!v) return { value: 0, key: "empty" };
    if (v.length < minimum) return { value: 1, key: "too_short" };
    var lower = v.toLowerCase();
    for (var i = 0; i < COMMON.length; i++) {
      if (lower.indexOf(COMMON[i]) !== -1 && lower.length - COMMON[i].length < 4) return { value: 1, key: "common" };
    }
    var pool = 0;
    if (/[a-z]/.test(v)) pool += 26;
    if (/[A-Z]/.test(v)) pool += 26;
    if (/\d/.test(v)) pool += 10;
    if (/[^A-Za-z0-9]/.test(v)) pool += 33;
    var unique = 0, seen = {}, runs = 0;
    for (var j = 0; j < v.length; j++) {
      if (!seen[v[j]]) { seen[v[j]] = true; unique++; }
      if (j > 0 && Math.abs(v.charCodeAt(j) - v.charCodeAt(j - 1)) <= 1) runs++;
    }
    var effective = Math.min(v.length, unique * 2) - runs / 2;
    var bits = Math.max(0, effective) * Math.log(Math.max(pool, 10)) / Math.LN2;
    if (bits < 40) return { value: 1, key: "weak" };
    if (bits < 60) return { value: 2, key: "fair" };
    if (bits < 80) return { value: 3, key: "good" };
    return { value: 4, key: "strong" };
  }

  function update() {
    var v = input.value;
    var result = score(v);
    meter.setAttribute("data-score", String(result.value));
    label.textContent = text[result.key] || "";
    label.setAttribute("data-score", String(result.value));
    Array.prototype.forEach.call(document.querySelectorAll("[data-rule]"), function (li) {
      var check = rules[li.getAttribute("data-rule")];
      li.classList.toggle("is-met", !!(check && check(v, li)));
    });
  }
  input.addEventListener("input", update);
  update();

  // One submit only: creating the account takes a moment.
  var form = document.querySelector("[data-setup-form]");
  var button = document.querySelector("[data-setup-submit]");
  if (form && button) {
    form.addEventListener("submit", function () {
      setTimeout(function () { button.disabled = true; }, 0);
    });
  }
})();
