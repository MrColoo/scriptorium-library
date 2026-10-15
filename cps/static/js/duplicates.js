// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Duplicates page: scan with live progress, selection, delete/merge, dismiss, auto-resolution.
(function () {
  "use strict";
  var CWA = window.CWA;
  var cfgEl = document.getElementById("duplicates-config");
  if (!CWA || !cfgEl) return;
  var cfg = JSON.parse(cfgEl.textContent);
  var T = cfg.i18n;

  function postJSON(url, payload) {
    return CWA.request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload)
    }).then(function (r) {
      return r.text().then(function (text) {
        var data = {};
        try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
        data.httpStatus = r.status;
        if (!r.ok || data.success === false) {
          var err = new Error(data.message || data.error || (data.errors || []).join(", ") || r.statusText);
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }
  function fail(err) { CWA.toast((err && err.message) || CWA.t("error"), "error"); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  // ---------- Scan ----------
  var scanBtn = document.getElementById("trigger-scan");
  var status = document.getElementById("dup-scan-status");
  var results = document.getElementById("dup-results");
  var setup = document.getElementById("dup-setup-notice");
  var pollTimer = null;
  var scanTaskId = null;
  var scanSeen = false;

  function isScanTask(task) {
    if (scanTaskId && String(task.task_id) === String(scanTaskId)) return true;
    return String(task.taskMessage || "").toLowerCase().indexOf("duplicate scan") !== -1;
  }
  function isRunning(task) { return [1, 3, 4, 5].indexOf(task.stat) === -1; }
  function showStatus(title, message, pct) {
    window.CWADuplicateScanActive = true;
    status.hidden = false;
    if (results) results.hidden = true;
    if (setup) setup.hidden = true;
    status.querySelector("[data-scan-title]").textContent = title;
    status.querySelector("[data-scan-message]").textContent = message || "";
    var bar = status.querySelector("[data-scan-progress]");
    bar.setAttribute("aria-valuenow", String(pct));
    bar.firstElementChild.style.width = pct + "%";
  }
  function poll() {
    CWA.request(cfg.tasks_url).then(function (r) { return r.json(); }).then(function (tasks) {
      var running = (tasks || []).filter(function (t) { return isScanTask(t) && isRunning(t); })[0];
      if (running) {
        scanSeen = true;
        scanTaskId = running.task_id;
        var pct = Math.max(0, Math.min(100, parseInt(running.progress, 10) || 0));
        showStatus(T.scanning, running.taskMessage, pct);
        pollTimer = setTimeout(poll, 2000);
      } else if (scanSeen) {
        showStatus(T.scanning, T.finished, 100);
        setTimeout(function () { window.location.reload(); }, 600);
      }
    }).catch(function () { pollTimer = setTimeout(poll, 5000); });
  }
  poll();

  if (scanBtn) {
    scanBtn.addEventListener("click", function () {
      scanBtn.disabled = true;
      postJSON(cfg.scan_url).then(function (data) {
        if (data.queued) {
          scanTaskId = data.task_id || null;
          scanSeen = true;
          showStatus(T.queued, "", 0);
          clearTimeout(pollTimer);
          poll();
        } else {
          window.location.reload();
        }
      }).catch(function (err) {
        scanBtn.disabled = false;
        CWA.toast(err.data && err.data.blocked ? (err.data.message || T.blocked) : (err.message || T.scan_failed), "error");
      });
    });
  }

  // ---------- Selection ----------
  var bar = document.getElementById("dup-selection");
  function boxes(scope) { return Array.prototype.slice.call((scope || document).querySelectorAll("input[data-book]")); }
  function selected(scope) {
    return boxes(scope).filter(function (b) { return b.checked; }).map(function (b) { return parseInt(b.value, 10); });
  }
  function sync() {
    var ids = selected();
    if (bar) {
      bar.hidden = !ids.length;
      bar.querySelector("[data-selection-count]").textContent = T.selected.replace("%n", ids.length);
    }
    Array.prototype.forEach.call(document.querySelectorAll(".dup-group"), function (group) {
      group.querySelector("[data-merge]").disabled = selected(group).length < 2;
    });
  }
  document.addEventListener("change", function (e) { if (e.target.matches && e.target.matches("input[data-book]")) sync(); });
  Array.prototype.forEach.call(document.querySelectorAll("[data-select]"), function (btn) {
    btn.addEventListener("click", function () {
      var all = btn.getAttribute("data-select") === "duplicates";
      Array.prototype.forEach.call(document.querySelectorAll(".dup-group"), function (group) {
        boxes(group).forEach(function (b, i) { b.checked = all && i > 0; });
      });
      sync();
    });
  });

  var del = document.getElementById("delete-selected");
  if (del) {
    del.addEventListener("click", function () {
      var ids = selected();
      if (!ids.length) return;
      CWA.confirm(T.delete_confirm.replace("%n", ids.length), T["delete"]).then(function (ok) {
        if (!ok) return;
        postJSON(cfg.delete_url, { selections: ids }).then(function () { window.location.reload(); }).catch(fail);
      });
    });
  }

  // ---------- Per group: merge and dismiss ----------
  Array.prototype.forEach.call(document.querySelectorAll(".dup-group"), function (group) {
    group.querySelector("[data-merge]").addEventListener("click", function () {
      var ids = selected(group);
      if (ids.length < 2) return;
      postJSON(cfg.simulate_merge_url, { Merge_books: ids }).then(function (d) {
        // Same titles are the norm here, so name each book by id too.
        var from = (d.from || []).map(function (t, i) { return "“" + t + "” (#" + ids[i + 1] + ")"; }).join(", ");
        var to = (d.to || "") + " (#" + ids[0] + ")";
        return CWA.confirm(T.merge_confirm.replace("%from", from).replace("%to", to), T.merge, false).then(function (ok) {
          if (ok) return postJSON(cfg.merge_url, { Merge_books: ids }).then(function () { window.location.reload(); });
        });
      }).catch(fail);
    });
    var dismiss = group.querySelector("[data-dismiss-group]");
    dismiss.addEventListener("click", function () {
      dismiss.disabled = true;
      postJSON(dismiss.getAttribute("data-dismiss-group")).then(function (d) {
        group.remove();
        CWA.toast(T.dismissed, "success");
        if (window.CWADuplicates && typeof d.count === "number") window.CWADuplicates.updateBadge(d.count);
        sync();
        if (!document.querySelector(".dup-group")) window.location.reload();
      }).catch(function (err) { dismiss.disabled = false; fail(err); });
    });
  });

  // ---------- Auto-resolution ----------
  var strategy = document.getElementById("resolution-strategy");
  var previewBtn = document.getElementById("preview-resolution");
  var dialog = document.getElementById("resolution-dialog");
  var execBtn = document.getElementById("execute-resolution");
  function fmt(text, data) {
    return text.replace("%groups", data.resolved_count || 0).replace("%keep", data.kept_count || 0).replace("%delete", data.deleted_count || 0);
  }
  function line(kind, label, id, timestamp, formats) {
    var row = el("div", "resolution-line");
    row.appendChild(el("span", "badge " + (kind === "keep" ? "badge--success" : "badge--danger"), label));
    row.appendChild(el("span", "mono small", "#" + id));
    row.appendChild(el("span", "muted small", [T.added + " " + (timestamp || "—"), (formats || []).join(", ")].filter(Boolean).join(" · ")));
    return row;
  }
  if (previewBtn) {
    previewBtn.addEventListener("click", function () {
      previewBtn.disabled = true;
      postJSON(cfg.preview_url, { strategy: strategy.value }).then(function (data) {
        var body = dialog.querySelector("[data-preview-body]");
        body.textContent = "";
        var groups = data.preview || [];
        body.appendChild(el("p", "strong", groups.length ? fmt(T.summary, data) : T.nothing));
        groups.forEach(function (g) {
          var box = el("div", "resolution-group");
          var head = el("div");
          head.appendChild(el("strong", "", g.title));
          head.appendChild(el("span", "muted", " · " + (g.author || "")));
          box.appendChild(head);
          box.appendChild(line("keep", T.keep, g.kept_book_id, g.kept_book_timestamp, g.kept_book_formats));
          (g.deleted_books_info || []).forEach(function (b) { box.appendChild(line("delete", T.remove, b.id, b.timestamp, b.formats)); });
          body.appendChild(box);
        });
        execBtn.hidden = !groups.length;
        CWA.openDialog(dialog);
      }).catch(fail).then(function () { previewBtn.disabled = false; });
    });
    execBtn.addEventListener("click", function () {
      CWA.confirm(T.execute_confirm, execBtn.textContent.trim()).then(function (ok) {
        if (!ok) return;
        execBtn.disabled = true;
        postJSON(cfg.execute_url, { strategy: strategy.value }).then(function (data) {
          CWA.closeDialog(dialog);
          CWA.toast(fmt(T.done, data), "success");
          setTimeout(function () { window.location.reload(); }, 1200);
        }).catch(function (err) { execBtn.disabled = false; fail(err); });
      });
    });
  }
  sync();
})();
