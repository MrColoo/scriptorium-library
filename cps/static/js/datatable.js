// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
//
// Server-side table with search, sort, paging, column picker, inline editing and selection.
// Replaces bootstrap-table + x-editable for the books and users tables.
//
// Markup: <div data-datatable="config-script-id"></div> with a JSON config script:
//   { url, pageSize, selectable, settingsUrl, visibility: {field: "true"|"false"},
//     columns: [{ field, label, type: text|number|select|bool|bit|html|link|actions,
//                 sortable, hideable, hidden, edit: {url, extra: {}, extraFrom: {name: "#checkbox"}},
//                 options: [[value, text]], bit, trueValue, falseValue, href, actions: [...] }],
//     strings: {...} }
// Every value is written with textContent; nothing from the server is parsed as HTML.
(function () {
  "use strict";
  var CWA = window.CWA;
  if (!CWA) return;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function stripHtml(html) {
    return (new DOMParser().parseFromString(String(html || ""), "text/html").body.textContent || "").trim();
  }

  function DataTable(root, cfg) {
    this.root = root;
    this.cfg = cfg;
    this.S = cfg.strings || {};
    this.page = 0;
    this.pageSize = cfg.pageSize || 25;
    this.sort = cfg.sort || "";
    this.order = cfg.order || "";
    this.search = "";
    this.selected = new Set();
    this.rows = [];
    this.total = 0;
    this.visibility = {};
    var self = this;
    cfg.columns.forEach(function (c) {
      var v = cfg.visibility && cfg.visibility[c.field] !== undefined ? cfg.visibility[c.field] : !c.hidden;
      self.visibility[c.key || c.field] = v === true || v === "true";
    });
    this.build();
    this.load();
  }

  DataTable.prototype.columns = function () {
    var self = this;
    return this.cfg.columns.filter(function (c) { return self.visibility[c.key || c.field] !== false; });
  };

  DataTable.prototype.build = function () {
    var self = this;
    var toolbar = el("div", "toolbar datatable-toolbar");
    var search = el("label", "search-box search-box--sm");
    search.appendChild(CWA.icon("search"));
    var input = el("input");
    input.type = "search";
    input.placeholder = this.S.search || "Search";
    input.setAttribute("aria-label", this.S.search || "Search");
    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { self.search = input.value.trim(); self.page = 0; self.load(); }, 250);
    });
    search.appendChild(input);
    toolbar.appendChild(search);
    this.selectionInfo = el("span", "small muted");
    toolbar.appendChild(this.selectionInfo);
    toolbar.appendChild(el("span", "grow"));

    // Column picker
    var hideable = this.cfg.columns.filter(function (c) { return c.hideable !== false && c.label; });
    if (hideable.length) {
      var menu = el("details", "menu");
      var summary = el("summary", "btn btn-sm");
      summary.appendChild(CWA.icon("sliders"));
      summary.appendChild(document.createTextNode(this.S.columns || "Columns"));
      menu.appendChild(summary);
      var panel = el("div", "menu-panel");
      hideable.forEach(function (c) {
        var key = c.key || c.field;
        var row = el("label", "menu-item");
        row.setAttribute("data-keep-open", "");
        var box = el("input");
        box.type = "checkbox";
        box.checked = self.visibility[key] !== false;
        box.addEventListener("change", function () {
          self.visibility[key] = box.checked;
          self.saveVisibility();
          self.render();
        });
        row.appendChild(box);
        row.appendChild(el("span", "grow", c.label));
        panel.appendChild(row);
      });
      menu.appendChild(panel);
      toolbar.appendChild(menu);
    }
    var size = el("select", "select datatable-size");
    size.setAttribute("aria-label", this.S.per_page || "Rows per page");
    [10, 25, 50, 100].forEach(function (n) {
      var o = el("option", "", String(n));
      o.value = n;
      if (n === self.pageSize) o.selected = true;
      size.appendChild(o);
    });
    size.addEventListener("change", function () { self.pageSize = parseInt(size.value, 10); self.page = 0; self.load(); });
    toolbar.appendChild(size);

    this.wrap = el("div", "table-wrap");
    this.table = el("table", "table datatable");
    this.wrap.appendChild(this.table);
    this.footer = el("div", "row-between datatable-footer");
    this.root.appendChild(toolbar);
    this.root.appendChild(this.wrap);
    this.root.appendChild(this.footer);
  };

  DataTable.prototype.saveVisibility = function () {
    if (!this.cfg.settingsUrl) return;
    var payload = {};
    var self = this;
    Object.keys(this.visibility).forEach(function (k) { payload[k] = self.visibility[k] ? "true" : "false"; });
    CWA.request(this.cfg.settingsUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).catch(function () {});
  };

  DataTable.prototype.load = function () {
    var self = this;
    var params = new URLSearchParams({ offset: this.page * this.pageSize, limit: this.pageSize });
    if (this.search) params.set("search", this.search);
    if (this.sort) { params.set("sort", this.sort); params.set("order", this.order || "asc"); }
    this.root.setAttribute("aria-busy", "true");
    CWA.request(this.cfg.url + (this.cfg.url.indexOf("?") === -1 ? "?" : "&") + params.toString())
      .then(function (r) { return r.json(); })
      .then(function (data) {
        self.rows = data.rows || [];
        self.total = data.total || 0;
        self.root.removeAttribute("aria-busy");
        self.render();
      })
      .catch(function () {
        self.root.removeAttribute("aria-busy");
        CWA.toast(CWA.t("error"), "error");
      });
  };

  DataTable.prototype.reload = function () { this.load(); };

  DataTable.prototype.render = function () {
    var self = this;
    var cols = this.columns();
    this.table.textContent = "";
    var thead = el("thead");
    var hr = el("tr");
    if (this.cfg.selectable) {
      var th = el("th", "datatable-check");
      var all = el("input");
      all.type = "checkbox";
      all.setAttribute("aria-label", this.S.select_page || "Select all on this page");
      all.checked = this.rows.length > 0 && this.rows.every(function (r) { return self.selected.has(r.id); });
      all.addEventListener("change", function () {
        self.rows.forEach(function (r) { if (all.checked) self.selected.add(r.id); else self.selected.delete(r.id); });
        self.render();
        self.emitSelection();
      });
      th.appendChild(all);
      hr.appendChild(th);
    }
    cols.forEach(function (c) {
      var th = el("th", c.type === "number" ? "num" : "");
      if (c.sortable) {
        var b = el("button", "datatable-sort", c.label || "");
        b.type = "button";
        var active = self.sort === (c.sortField || c.field);
        if (active) {
          th.setAttribute("aria-sort", self.order === "desc" ? "descending" : "ascending");
          b.appendChild(CWA.icon(self.order === "desc" ? "chevron-down" : "chevron-up", "icon-sm"));
        }
        b.addEventListener("click", function () {
          var field = c.sortField || c.field;
          if (self.sort === field) self.order = self.order === "asc" ? "desc" : "asc";
          else { self.sort = field; self.order = "asc"; }
          self.load();
        });
        th.appendChild(b);
      } else {
        th.textContent = c.label || "";
      }
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    this.table.appendChild(thead);

    var tbody = el("tbody");
    if (!this.rows.length) {
      var tr = el("tr");
      var td = el("td", "muted center", this.S.empty || "Nothing found");
      td.colSpan = cols.length + (this.cfg.selectable ? 1 : 0);
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
    this.rows.forEach(function (row) {
      var tr = el("tr");
      if (self.selected.has(row.id)) tr.className = "is-selected";
      if (self.cfg.selectable) {
        var td = el("td", "datatable-check");
        var box = el("input");
        box.type = "checkbox";
        box.checked = self.selected.has(row.id);
        box.setAttribute("aria-label", (self.S.select || "Select") + " " + (row[self.cfg.labelField || "title"] || row.name || row.id));
        box.addEventListener("change", function () {
          if (box.checked) self.selected.add(row.id); else self.selected.delete(row.id);
          tr.classList.toggle("is-selected", box.checked);
          self.emitSelection();
        });
        td.appendChild(box);
        tr.appendChild(td);
      }
      cols.forEach(function (c) { tr.appendChild(self.cell(c, row)); });
      tbody.appendChild(tr);
    });
    this.table.appendChild(tbody);
    this.renderFooter();
    this.emitSelection();
  };

  DataTable.prototype.renderFooter = function () {
    var self = this;
    this.footer.textContent = "";
    var pages = Math.max(1, Math.ceil(this.total / this.pageSize));
    var from = this.total ? this.page * this.pageSize + 1 : 0;
    var to = Math.min(this.total, (this.page + 1) * this.pageSize);
    this.footer.appendChild(el("span", "small muted tabular", (this.S.range || "%from–%to of %total").replace("%from", from).replace("%to", to).replace("%total", this.total)));
    var nav = el("div", "row");
    var prev = el("button", "btn btn-sm btn-icon");
    prev.type = "button";
    prev.setAttribute("aria-label", this.S.previous || "Previous");
    prev.appendChild(CWA.icon("chevron-left"));
    prev.disabled = this.page === 0;
    prev.addEventListener("click", function () { self.page--; self.load(); });
    var next = el("button", "btn btn-sm btn-icon");
    next.type = "button";
    next.setAttribute("aria-label", this.S.next || "Next");
    next.appendChild(CWA.icon("chevron-right"));
    next.disabled = this.page >= pages - 1;
    next.addEventListener("click", function () { self.page++; self.load(); });
    nav.appendChild(prev);
    nav.appendChild(el("span", "small tabular", (this.page + 1) + " / " + pages));
    nav.appendChild(next);
    this.footer.appendChild(nav);
  };

  DataTable.prototype.emitSelection = function () {
    var n = this.selected.size;
    this.selectionInfo.textContent = n ? (this.S.selected || "%n selected").replace("%n", n) : "";
    this.root.dispatchEvent(new CustomEvent("datatable:selection", { bubbles: true, detail: { ids: Array.from(this.selected) } }));
  };

  DataTable.prototype.clearSelection = function () {
    this.selected.clear();
    this.render();
  };

  DataTable.prototype.post = function (c, row, value, extra) {
    var body = new URLSearchParams();
    body.set("pk", row.id);
    body.set("value", value);
    var e = Object.assign({}, c.edit.extra || {}, extra || {});
    Object.keys(e).forEach(function (k) { body.set(k, e[k]); });
    Object.keys(c.edit.extraFrom || {}).forEach(function (k) {
      var box = document.querySelector(c.edit.extraFrom[k]);
      if (box) body.set(k, box.checked ? "true" : "false");
    });
    return CWA.request(c.edit.url, { method: "POST", body: body }).then(function (r) {
      return r.text().then(function (t) {
        if (!r.ok) throw new Error(t || r.statusText);
        var data = null;
        try { data = t ? JSON.parse(t) : null; } catch (err) { data = null; }
        if (data && (data.success === false || data.type === "danger")) throw new Error(data.msg || data.message || "");
        return data;
      });
    });
  };

  DataTable.prototype.cell = function (c, row) {
    var self = this;
    var td = el("td", c.type === "number" ? "num" : (c.cls || ""));
    var value = row[c.field];

    if (c.type === "link") {
      var a = el("a", "", c.text || value);
      a.href = c.href.replace("__id__", encodeURIComponent(row.id));
      td.appendChild(a);
      return td;
    }
    if (c.type === "actions") {
      (c.actions || []).forEach(function (act) { td.appendChild(self.action(act, row)); });
      return td;
    }
    if (c.type === "bool" || c.type === "bit") {
      var box = el("input", "switch");
      box.type = "checkbox";
      box.checked = c.type === "bit" ? ((parseInt(value, 10) || 0) & c.bit) === c.bit : value === true || value === 1 || value === "1";
      box.setAttribute("aria-label", (c.label || c.field) + " – " + (row[self.cfg.labelField || "name"] || row.title || row.id));
      if (!c.edit) box.disabled = true;
      box.addEventListener("change", function () {
        var v = box.checked ? (c.trueValue || "true") : (c.falseValue || "false");
        var extra = c.type === "bit" ? { field_index: c.bit } : {};
        self.post(c, row, v, extra).then(function () {
          if (c.type === "bit") row[c.field] = box.checked ? (row[c.field] | c.bit) : (row[c.field] & ~c.bit);
          else row[c.field] = box.checked;
        }).catch(function (err) {
          box.checked = !box.checked;
          CWA.toast(err.message || CWA.t("error"), "error");
        });
      });
      td.appendChild(box);
      return td;
    }

    var display = value;
    if (c.type === "select" && c.options) {
      c.options.forEach(function (o) { if (String(o[0]) === String(value)) display = o[1]; });
      if (c.displayField) display = row[c.displayField];
    }
    if (c.type === "html") display = stripHtml(value);
    var text = el("span", c.type === "html" ? "datatable-clamp" : "", display === null || display === undefined || display === "" ? "—" : String(display));
    if (display === null || display === undefined || display === "") text.classList.add("faint");
    if (!c.edit) { td.appendChild(text); return td; }

    var trigger = el("button", "datatable-edit");
    trigger.type = "button";
    trigger.title = self.S.edit || "Edit";
    trigger.appendChild(text);
    td.appendChild(trigger);
    trigger.addEventListener("click", function () { self.editCell(c, row, td); });
    return td;
  };

  DataTable.prototype.editCell = function (c, row, td) {
    var self = this;
    var input;
    if (c.type === "select") {
      input = el("select", "select");
      c.options.forEach(function (o) {
        var opt = el("option", "", o[1]);
        opt.value = o[0];
        if (String(o[0]) === String(row[c.field])) opt.selected = true;
        input.appendChild(opt);
      });
    } else if (c.type === "html") {
      input = el("textarea", "textarea");
      input.value = row[c.field] || "";
      input.rows = 4;
    } else {
      input = el("input", "input");
      input.type = c.type === "number" ? "number" : "text";
      if (c.type === "number") input.step = "0.01";
      input.value = row[c.field] === null || row[c.field] === undefined ? "" : row[c.field];
    }
    input.setAttribute("aria-label", c.label || c.field);
    if (c.suggest) { input.setAttribute("data-suggest", c.suggest); if (c.separator) input.setAttribute("data-separator", c.separator); }
    td.textContent = "";
    td.appendChild(input);
    if (c.suggest && CWA.enhanceSuggest) CWA.enhanceSuggest(input);
    input.focus();
    if (input.select) input.select();
    var done = false;
    function finish(save) {
      if (done) return;
      done = true;
      if (!save || String(input.value) === String(row[c.field] === null || row[c.field] === undefined ? "" : row[c.field])) {
        td.replaceWith(self.cell(c, row));
        return;
      }
      input.disabled = true;
      self.post(c, row, input.value).then(function (data) {
        row[c.field] = c.type === "number" ? parseFloat(input.value) : input.value;
        if (data && typeof data === "object") {
          Object.keys(data).forEach(function (k) { if (k in row) row[k] = data[k]; });
          if (data.newValue !== undefined) row[c.field] = data.newValue;
        }
        self.render();
      }).catch(function (err) {
        CWA.toast(err.message || CWA.t("error"), "error");
        self.render();
      });
    }
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (c.type !== "html" || e.metaKey || e.ctrlKey)) { e.preventDefault(); finish(true); }
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(false); }
    });
    input.addEventListener(c.type === "select" ? "change" : "blur", function () { setTimeout(function () { finish(true); }, 120); });
  };

  DataTable.prototype.action = function (act, row) {
    var self = this;
    var b = el(act.href ? "a" : "button", "btn btn-sm " + (act.cls || "btn-ghost"));
    if (act.href) b.href = act.href.replace("__id__", encodeURIComponent(row.id));
    else b.type = "button";
    if (act.icon) b.appendChild(CWA.icon(act.icon));
    if (act.label && !act.iconOnly) b.appendChild(document.createTextNode(act.label));
    if (act.iconOnly) { b.classList.add("btn-icon"); b.setAttribute("aria-label", act.label); b.title = act.label; }
    if (act.post) {
      b.addEventListener("click", function () {
        var label = row[self.cfg.labelField || "name"] || row.title || "";
        CWA.confirm((act.confirm || "").replace("%s", label), act.label).then(function (ok) {
          if (!ok) return;
          var body = new URLSearchParams();
          body.set(act.idParam || "pk", row.id);
          CWA.request(act.post, { method: "POST", body: body }).then(function (r) { return r.json().catch(function () { return {}; }); })
            .then(function (d) {
              if (d && d.type === "danger") CWA.toast(d.message, "error");
              else if (d && d.message) CWA.toast(d.message, "success");
              self.selected.delete(row.id);
              self.load();
            });
        });
      });
    }
    return b;
  };

  var instances = {};
  Array.prototype.forEach.call(document.querySelectorAll("[data-datatable]"), function (root) {
    var cfg = JSON.parse(document.getElementById(root.getAttribute("data-datatable")).textContent);
    instances[root.id || root.getAttribute("data-datatable")] = new DataTable(root, cfg);
  });
  window.CWA.tables = instances;
})();
