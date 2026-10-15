// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Smart (magic) shelf editor: nested AND/OR rule groups, preview, save, delete, duplicate.
// Produces the same JSON as jQuery QueryBuilder did: {condition, rules: [{id, operator, value} | group]}.
(function () {
  "use strict";
  var CWA = window.CWA;
  var root = document.getElementById("rule-builder");
  if (!CWA || !root) return;
  var cfg = JSON.parse(document.getElementById("magic-shelf-data").textContent);
  var S = cfg.strings;

  var STRING_OPS = ["contains", "not_contains", "equal", "not_equal", "begins_with", "not_begins_with", "ends_with", "not_ends_with", "is_empty", "is_not_empty"];
  var NUMBER_OPS = ["equal", "not_equal", "less", "less_or_equal", "greater", "greater_or_equal", "between", "not_between", "is_empty", "is_not_empty"];
  var DATE_OPS = ["newer_than", "older_than", "equal", "less", "greater", "between", "not_between", "is_null", "is_not_null"];
  var NO_VALUE = ["is_empty", "is_not_empty", "is_null", "is_not_null"];
  var TWO_VALUES = ["between", "not_between"];

  var FIELDS = {
    title: { type: "string", ops: STRING_OPS },
    author: { type: "string", ops: STRING_OPS },
    tag: { type: "string", ops: STRING_OPS },
    series: { type: "string", ops: STRING_OPS },
    publisher: { type: "string", ops: STRING_OPS },
    comments: { type: "string", ops: ["contains", "not_contains", "is_empty", "is_not_empty"] },
    language: { type: "string", ops: ["equal", "not_equal", "is_empty", "is_not_empty"], values: cfg.languages },
    rating: { type: "integer", ops: NUMBER_OPS, values: (function () {
      var v = {};
      for (var i = 1; i <= 10; i++) v[i] = (i / 2) + " ★";
      return v;
    })() },
    series_index: { type: "double", ops: NUMBER_OPS },
    pubdate: { type: "date", ops: DATE_OPS },
    timestamp: { type: "date", ops: DATE_OPS },
    last_modified: { type: "date", ops: DATE_OPS },
    read_status: { type: "integer", ops: ["equal", "not_equal"], values: { 0: S.unread, 2: S.reading, 1: S.read } },
    has_cover: { type: "integer", ops: ["equal"], values: { 1: S.yes, 0: S.no } },
    hardcover_id: { type: "integer", ops: ["equal"], values: { 1: S.yes, 0: S.no } }
  };
  var FIELD_ORDER = ["title", "author", "tag", "series", "publisher", "language", "rating", "read_status", "series_index",
                     "pubdate", "timestamp", "last_modified", "comments", "has_cover", "hardcover_id"];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function select(options, value, label) {
    var s = el("select", "select");
    if (label) s.setAttribute("aria-label", label);
    options.forEach(function (o) {
      var opt = el("option", "", o[1]);
      opt.value = o[0];
      if (String(o[0]) === String(value)) opt.selected = true;
      s.appendChild(opt);
    });
    return s;
  }
  function iconButton(name, label, cls) {
    var b = el("button", "btn btn-ghost btn-icon btn-sm" + (cls ? " " + cls : ""));
    b.type = "button";
    b.setAttribute("aria-label", label);
    b.title = label;
    b.appendChild(CWA.icon(name));
    return b;
  }

  // ---------- Model <-> DOM ----------
  function newRule() { return { id: "title", operator: "contains", value: "" }; }
  function newGroup() { return { condition: "AND", rules: [newRule()] }; }

  function renderGroup(group, depth) {
    var box = el("div", "rule-group" + (depth ? " rule-group--nested" : ""));
    var head = el("div", "rule-group-head");
    var seg = el("div", "segmented");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", S.match);
    ["AND", "OR"].forEach(function (c) {
      var b = el("button", "", c === "AND" ? S.all : S.any);
      b.type = "button";
      b.setAttribute("aria-pressed", group.condition === c ? "true" : "false");
      b.addEventListener("click", function () {
        group.condition = c;
        Array.prototype.forEach.call(seg.children, function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      });
      seg.appendChild(b);
    });
    head.appendChild(el("span", "small muted", S.match_label));
    head.appendChild(seg);
    head.appendChild(el("span", "grow"));
    var addRule = el("button", "btn btn-sm", "+ " + S.add_rule);
    addRule.type = "button";
    var addGroup = el("button", "btn btn-sm btn-ghost", "+ " + S.add_group);
    addGroup.type = "button";
    head.appendChild(addRule);
    if (depth < 3) head.appendChild(addGroup);
    if (depth) {
      var removeGroup = iconButton("trash", S.remove_group);
      removeGroup.addEventListener("click", function () { group._remove(); });
      head.appendChild(removeGroup);
    }
    box.appendChild(head);
    var list = el("div", "rule-list");
    box.appendChild(list);

    function draw() {
      list.textContent = "";
      group.rules.forEach(function (item, index) {
        var node;
        if (item.condition) {
          item._remove = function () { group.rules.splice(index, 1); draw(); };
          node = renderGroup(item, depth + 1);
        } else {
          node = renderRule(item, function () { group.rules.splice(index, 1); draw(); });
        }
        list.appendChild(node);
      });
      if (!group.rules.length) list.appendChild(el("p", "small muted", S.empty_group));
      updateHint();
    }
    addRule.addEventListener("click", function () { group.rules.push(newRule()); draw(); });
    addGroup.addEventListener("click", function () { group.rules.push(newGroup()); draw(); });
    draw();
    return box;
  }

  function renderRule(rule, onRemove) {
    var row = el("div", "rule-row");
    if (!FIELDS[rule.id]) rule.id = "title";
    var fieldSel = select(FIELD_ORDER.map(function (f) { return [f, S.fields[f] || f]; }), rule.id, S.field);
    var opSel = el("select", "select");
    opSel.setAttribute("aria-label", S.operator);
    var valueBox = el("div", "rule-value");
    var removeBtn = iconButton("x", S.remove_rule);
    removeBtn.addEventListener("click", onRemove);

    function fillOps() {
      var def = FIELDS[rule.id];
      opSel.textContent = "";
      if (def.ops.indexOf(rule.operator) === -1) rule.operator = def.ops[0];
      def.ops.forEach(function (op) {
        var o = el("option", "", S.operators[op] || op);
        o.value = op;
        if (op === rule.operator) o.selected = true;
        opSel.appendChild(o);
      });
    }
    function valueInput(def, v, index) {
      var input;
      if (def.values) {
        input = select(Object.keys(def.values).map(function (k) { return [k, def.values[k]]; }), v, S.value);
      } else {
        input = el("input", "input");
        input.type = def.type === "date" ? "text" : (def.type === "string" ? "text" : "number");
        if (def.type === "double") input.step = "0.01";
        if (def.type === "date") {
          input.placeholder = (rule.operator === "newer_than" || rule.operator === "older_than" || rule.operator === "equal") ? S.date_or_days : "YYYY-MM-DD";
          input.inputMode = "numeric";
        }
        input.value = v === undefined || v === null ? "" : v;
        input.setAttribute("aria-label", S.value);
      }
      input.addEventListener("input", function () { setValue(index, input.value); validate(input); });
      input.addEventListener("change", function () { setValue(index, input.value); validate(input); });
      return input;
    }
    function setValue(index, raw) {
      var def = FIELDS[rule.id];
      var v = raw;
      if (def.type === "integer" && raw !== "") v = parseInt(raw, 10);
      if (def.type === "double" && raw !== "") v = parseFloat(raw);
      if (TWO_VALUES.indexOf(rule.operator) !== -1) {
        if (!Array.isArray(rule.value)) rule.value = ["", ""];
        rule.value[index] = v;
      } else {
        rule.value = v;
      }
    }
    function validate(input) {
      var def = FIELDS[rule.id];
      if (def.type !== "date") return;
      var ok = isValidDate(input.value, ["newer_than", "older_than", "equal"].indexOf(rule.operator) !== -1);
      input.setAttribute("aria-invalid", input.value && !ok ? "true" : "false");
    }
    function fillValue() {
      var def = FIELDS[rule.id];
      valueBox.textContent = "";
      if (NO_VALUE.indexOf(rule.operator) !== -1) { rule.value = null; return; }
      if (TWO_VALUES.indexOf(rule.operator) !== -1) {
        if (!Array.isArray(rule.value)) rule.value = [rule.value === null || rule.value === undefined ? "" : rule.value, ""];
        valueBox.appendChild(valueInput(def, rule.value[0], 0));
        valueBox.appendChild(el("span", "small muted", S.and));
        valueBox.appendChild(valueInput(def, rule.value[1], 1));
      } else {
        if (Array.isArray(rule.value)) rule.value = rule.value[0];
        var input = valueInput(def, rule.value, 0);
        if (def.values && (rule.value === "" || rule.value === undefined || rule.value === null)) setValue(0, input.value);
        valueBox.appendChild(input);
      }
    }
    fieldSel.addEventListener("change", function () {
      rule.id = fieldSel.value;
      rule.value = "";
      fillOps();
      fillValue();
      updateHint();
    });
    opSel.addEventListener("change", function () { rule.operator = opSel.value; fillValue(); });
    fillOps();
    fillValue();
    row.appendChild(fieldSel);
    row.appendChild(opSel);
    row.appendChild(valueBox);
    row.appendChild(removeBtn);
    return row;
  }

  function isValidDate(value, allowDays) {
    value = String(value || "").trim();
    if (allowDays && /^[0-9]+$/.test(value)) return true;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.indexOf("0000-") === 0) return false;
    var d = new Date(value);
    return !isNaN(d.getTime()) && d.toISOString().indexOf(value) === 0;
  }

  // Serialise without the helper properties and with QueryBuilder's extra keys.
  function serialise(group) {
    return {
      condition: group.condition,
      rules: group.rules.map(function (item) {
        if (item.condition) return serialise(item);
        var def = FIELDS[item.id];
        return { id: item.id, field: item.id, type: def.type, input: def.values ? "select" : "text", operator: item.operator, value: item.value };
      }),
      valid: true
    };
  }
  function problems(group) {
    var errs = [];
    if (!group.rules.length) errs.push(S.empty_group);
    group.rules.forEach(function (item) {
      if (item.condition) { errs = errs.concat(problems(item)); return; }
      var def = FIELDS[item.id];
      if (NO_VALUE.indexOf(item.operator) !== -1) return;
      var values = Array.isArray(item.value) ? item.value : [item.value];
      values.forEach(function (v) {
        if (v === "" || v === null || v === undefined || (typeof v === "number" && isNaN(v))) errs.push(S.missing_value.replace("%s", S.fields[item.id]));
        else if (def.type === "date" && !isValidDate(v, ["newer_than", "older_than", "equal"].indexOf(item.operator) !== -1)) errs.push(S.bad_date);
      });
    });
    return errs;
  }

  var hint = document.getElementById("date-hint");
  function usesDates(group) {
    return group.rules.some(function (r) { return r.condition ? usesDates(r) : FIELDS[r.id] && FIELDS[r.id].type === "date"; });
  }
  function updateHint() { if (hint) hint.hidden = !usesDates(model); }

  var model = cfg.rules && cfg.rules.rules ? JSON.parse(JSON.stringify(cfg.rules)) : newGroup();
  (function clean(g) {
    g.condition = (g.condition || "AND").toUpperCase() === "OR" ? "OR" : "AND";
    g.rules = (g.rules || []).filter(Boolean).map(function (r) {
      if (r.condition) { clean(r); return r; }
      return { id: r.id || r.field, operator: r.operator, value: r.value };
    });
  })(model);
  root.appendChild(renderGroup(model, 0));
  updateHint();

  // ---------- Icon picker ----------
  var iconInput = document.getElementById("shelf-icon");
  var iconGrid = document.getElementById("icon-picker-grid");
  if (iconGrid) {
    iconGrid.addEventListener("click", function (e) {
      var b = e.target.closest("[data-icon]");
      if (!b) return;
      iconInput.value = b.getAttribute("data-icon");
      Array.prototype.forEach.call(iconGrid.querySelectorAll("[data-icon]"), function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
    });
  }
  var nameInput = document.getElementById("shelf-name");
  var count = document.getElementById("char-count");
  if (nameInput && count) {
    var updateCount = function () { count.textContent = nameInput.value.length; };
    nameInput.addEventListener("input", updateCount);
    updateCount();
  }

  // ---------- Preview / save / delete / duplicate ----------
  var preview = document.getElementById("preview-results");
  function showProblems(errs) {
    preview.hidden = false;
    preview.className = "alert alert--danger";
    preview.textContent = "";
    var ul = el("ul", "");
    errs.slice(0, 5).forEach(function (m) { ul.appendChild(el("li", "", m)); });
    preview.appendChild(ul);
  }
  function json(url, body) {
    return CWA.request(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { return r.json().catch(function () { return { success: false }; }); });
  }

  document.getElementById("preview-btn").addEventListener("click", function () {
    var errs = problems(model);
    if (errs.length) { showProblems(errs); return; }
    var btn = this;
    btn.classList.add("is-loading");
    json(cfg.preview_url, { rules: serialise(model) }).then(function (res) {
      btn.classList.remove("is-loading");
      preview.hidden = false;
      preview.textContent = "";
      if (!res.success) { preview.className = "alert alert--danger"; preview.textContent = res.message || S.error; return; }
      preview.className = "alert alert--success";
      var body = el("div", "alert-body");
      body.appendChild(el("strong", "", S.matches.replace("%s", res.count)));
      if (res.sample_books && res.sample_books.length) {
        var ul = el("ul", "");
        res.sample_books.forEach(function (t) { ul.appendChild(el("li", "", t)); });
        body.appendChild(ul);
      }
      preview.appendChild(body);
    });
  });

  document.getElementById("magic-shelf-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var errs = problems(model);
    if (!nameInput.value.trim()) errs.unshift(S.name_required);
    if (errs.length) { showProblems(errs); return; }
    var kobo = document.getElementById("shelf-kobo-sync");
    var pub = document.getElementById("shelf-is-public");
    var submit = document.getElementById("save-shelf-btn");
    submit.classList.add("is-loading");
    json(cfg.save_url, {
      name: nameInput.value.trim(),
      icon: iconInput.value,
      rules: serialise(model),
      kobo_sync: !!(kobo && kobo.checked),
      is_public: !!(pub && pub.checked)
    }).then(function (res) {
      submit.classList.remove("is-loading");
      if (res.success) {
        var id = res.shelf_id || cfg.shelf_id;
        window.location.href = id ? cfg.view_url.replace("999999999", String(id)) : cfg.done_url;
      } else {
        CWA.toast(res.message || S.error, "error");
      }
    });
  });

  var del = document.getElementById("delete-shelf-btn");
  if (del && !del.disabled) {
    del.addEventListener("click", function () {
      CWA.confirm(S.delete_confirm, S.delete).then(function (ok) {
        if (!ok) return;
        json(cfg.delete_url).then(function (res) {
          if (res.success) window.location.href = cfg.done_url;
          else CWA.toast(res.message || S.error, "error");
        });
      });
    });
  }
  var dup = document.getElementById("duplicate-shelf-btn");
  if (dup) {
    dup.addEventListener("click", function () {
      dup.classList.add("is-loading");
      json(cfg.duplicate_url).then(function (res) {
        dup.classList.remove("is-loading");
        if (res.success) window.location.href = cfg.edit_url.replace("999999999", String(res.shelf_id));
        else CWA.toast(res.message || S.error, "error");
      });
    });
  }
})();
