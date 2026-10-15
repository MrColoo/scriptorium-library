// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Customize page: live preview of personal styles, presets and random mixes.
(function () {
  "use strict";
  var form = document.getElementById("ap-form");
  var cfgEl = document.getElementById("ap-config");
  if (!form || !cfgEl) return;
  var cfg = JSON.parse(cfgEl.textContent);
  var OPTS = cfg.options;
  var KEYS = Object.keys(OPTS);
  var root = document.documentElement;
  var stage = document.getElementById("ap-stage");
  var presetInput = document.getElementById("ap-preset");
  var savebar = form.querySelector("[data-ap-savebar]");
  var status = form.querySelector("[data-ap-status]");
  var presetButtons = Array.prototype.slice.call(form.querySelectorAll("[data-ap-preset]"));

  var saved = cfg.stock ? null : copy(cfg.current);
  var state = saved ? copy(saved) : null;   // null = the classic (stock) look

  function copy(o) { return JSON.parse(JSON.stringify(o)); }
  function same(a, b) {
    if (!a || !b) return a === b;
    return KEYS.concat(["hue", "hue2"]).every(function (k) { return String(a[k]) === String(b[k]); });
  }

  // ---------- Apply a style to a scope element ----------
  function applyTo(el, s) {
    Array.prototype.slice.call(el.attributes).forEach(function (a) {
      if (a.name === "data-ap" || a.name.indexOf("data-ap-") === 0 && a.name !== "data-ap-preset") el.removeAttribute(a.name);
    });
    el.style.removeProperty("--ap-h");
    el.style.removeProperty("--ap-h2");
    if (!s) {
      if (el !== root) el.classList.add("ap-reset");
      return;
    }
    el.classList.remove("ap-reset");
    el.setAttribute("data-ap", "");
    KEYS.forEach(function (k) { el.setAttribute("data-ap-" + k, s[k]); });
    el.style.setProperty("--ap-h", s.hue);
    el.style.setProperty("--ap-h2", s.hue2);
  }

  function render() {
    applyTo(root, state);
    if (stage) applyTo(stage, state);
    var shown = state || copy(cfg.current);
    // Swatches preview each option in the current colours.
    Array.prototype.forEach.call(form.querySelectorAll(".ap-swatch"), function (sw) {
      sw.style.setProperty("--ap-h", shown.hue);
      sw.style.setProperty("--ap-h2", shown.hue2);
      sw.setAttribute("data-ap-vibrancy", shown.vibrancy);
    });
    Array.prototype.forEach.call(form.querySelectorAll("[data-hue-dot]"), function (dot) {
      dot.style.setProperty("--dot-h", shown[dot.getAttribute("data-hue-dot")]);
    });
    presetButtons.forEach(function (btn) {
      var key = btn.getAttribute("data-ap-preset");
      var values = cfg.presets[cfg.presetKeys.indexOf(key)];
      var match = key === "stock" ? state === null : same(state, values);
      btn.setAttribute("aria-pressed", match ? "true" : "false");
    });
    presetInput.value = state === null ? "stock" : "";
    var dirty = !same(state, saved);
    savebar.hidden = !dirty;
    status.textContent = dirty ? cfg.i18n.unsaved : cfg.i18n.saved;
  }

  // ---------- Keep the form controls in step with the state ----------
  function fill(s) {
    if (!s) return;
    KEYS.forEach(function (k) {
      var input = form.querySelector("input[name='" + k + "'][value='" + s[k] + "']");
      if (input) input.checked = true;
    });
    form.querySelector("input[name='hue']").value = s.hue;
    form.querySelector("input[name='hue2']").value = s.hue2;
  }
  function readForm() {
    var s = {};
    KEYS.forEach(function (k) {
      var checked = form.querySelector("input[name='" + k + "']:checked");
      s[k] = checked ? checked.value : OPTS[k][0];
    });
    s.hue = parseInt(form.querySelector("input[name='hue']").value, 10) || 0;
    s.hue2 = parseInt(form.querySelector("input[name='hue2']").value, 10) || 0;
    return s;
  }

  form.addEventListener("input", function (e) {
    if (!e.target.name || e.target.type === "hidden") return;
    state = readForm();
    render();
  });
  form.addEventListener("change", function (e) {
    if (e.target.type === "radio") { state = readForm(); render(); }
  });

  // ---------- Presets, random mix, undo ----------
  presetButtons.forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var key = btn.getAttribute("data-ap-preset");
      if (key === "stock") {
        state = null;
      } else {
        state = copy(cfg.presets[cfg.presetKeys.indexOf(key)]);
        fill(state);
      }
      render();
    });
  });

  function pick(list) { return list[Math.floor(Math.random() * list.length)]; }
  form.querySelector("[data-ap-random]").addEventListener("click", function () {
    var s = {};
    KEYS.forEach(function (k) { s[k] = pick(OPTS[k]); });
    // Lean towards the more colourful choices: a random mix should feel like one.
    if (Math.random() < 0.75) s.header = pick(["gradient", "mesh", "aurora", "dots", "grid", "waves", "stripes", "topo"]);
    s.hue = Math.floor(Math.random() * 360);
    var offset = 40 + Math.floor(Math.random() * 120);
    s.hue2 = (s.hue + (Math.random() < 0.5 ? -offset : offset) + 360) % 360;
    state = s;
    fill(s);
    render();
    if (window.CWA && !form.dataset.randomHint) {  // explain once, not on every roll
      form.dataset.randomHint = "1";
      window.CWA.toast(cfg.i18n.random, "info", 4000);
    }
  });

  form.querySelector("[data-ap-revert]").addEventListener("click", function () {
    state = saved ? copy(saved) : null;
    fill(state || cfg.current);
    render();
  });

  // Saving the classic look clears the custom style.
  form.addEventListener("submit", function () { presetInput.value = state === null ? "stock" : ""; });

  window.addEventListener("beforeunload", function (e) {
    if (!savebar.hidden && !form.dataset.submitting) { e.preventDefault(); e.returnValue = ""; }
  });
  form.addEventListener("submit", function () { form.dataset.submitting = "1"; });

  fill(state || cfg.current);
  render();
})();
