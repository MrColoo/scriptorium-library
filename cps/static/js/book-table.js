// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Books table: bulk actions on the selected rows.
(function () {
  "use strict";
  var CWA = window.CWA;
  var root = document.getElementById("books");
  var bar = document.getElementById("book-bulk");
  if (!CWA || !root || !bar) return;
  var cfg = JSON.parse(document.getElementById("book-table-config").textContent);
  var B = cfg.bulk;
  var ids = [];

  function table() { return CWA.tables.books; }
  function json(url, payload) {
    return CWA.request(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
      .then(function (r) {
        return r.text().then(function (t) {
          var d = null;
          try { d = t ? JSON.parse(t) : {}; } catch (e) { d = {}; }
          if (!r.ok || (d && (d.success === false || d.status === "error"))) throw new Error((d && (d.msg || d.message)) || r.statusText);
          return d;
        });
      });
  }
  function done(message) {
    CWA.toast(message || B.done, "success");
    table().clearSelection();
    table().reload();
  }
  function fail(err) { CWA.toast((err && err.message) || CWA.t("error"), "error"); }

  root.addEventListener("datatable:selection", function (e) {
    ids = e.detail.ids;
    bar.hidden = !ids.length;
    bar.querySelector("[data-bulk-count]").textContent = B.selected.replace("%n", ids.length);
    Array.prototype.forEach.call(bar.querySelectorAll("[data-min]"), function (b) {
      b.disabled = ids.length < parseInt(b.getAttribute("data-min"), 10);
    });
  });

  var editDialog = document.getElementById("bulk-edit-dialog");
  var editForm = document.getElementById("bulk-edit-form");
  var shelfDialog = document.getElementById("bulk-shelf-dialog");
  var shelfForm = document.getElementById("bulk-shelf-form");

  editForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var payload = { selections: ids, checkA: document.getElementById("autoupdate_authorsort").checked ? "true" : "false" };
    new FormData(editForm).forEach(function (value, key) { if (String(value).trim()) payload[key] = String(value).trim(); });
    json(B.edit_url, payload).then(function () { CWA.closeDialog(editDialog); editForm.reset(); done(); }).catch(fail);
  });
  shelfForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var shelf = parseInt(document.getElementById("bulk_shelf").value, 10);
    json(B.shelf_url, { shelf_id: shelf, book_ids: ids }).then(function (d) { CWA.closeDialog(shelfDialog); done(d.message); }).catch(fail);
  });

  bar.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-bulk]");
    if (!btn || !ids.length) return;
    var action = btn.getAttribute("data-bulk");
    var n = String(ids.length);
    if (action === "clear") { table().clearSelection(); return; }
    if (action === "edit") { CWA.openDialog(editDialog); return; }
    if (action === "shelf") { CWA.openDialog(shelfDialog); return; }
    if (action === "read" || action === "unread") {
      json(B.read_url, { selections: ids, markAsRead: action === "read" }).then(function () { done(); }).catch(fail);
    } else if (action === "archive" || action === "unarchive") {
      json(B.archive_url, { selections: ids, archive: action === "archive" }).then(function () { done(); }).catch(fail);
    } else if (action === "xchange") {
      CWA.confirm(B.xchange_confirm.replace("%n", n), B.xchange, false).then(function (ok) {
        if (ok) json(B.xchange_url, { xchange: ids }).then(function () { done(); }).catch(fail);
      });
    } else if (action === "delete") {
      CWA.confirm(B.delete_confirm.replace("%n", n), B.delete).then(function (ok) {
        if (ok) json(B.delete_url, { selections: ids }).then(function () { done(); }).catch(fail);
      });
    } else if (action === "merge") {
      json(B.simulate_merge_url, { Merge_books: ids }).then(function (d) {
        var from = (d.from || []).map(function (t) { return "“" + t + "”"; }).join(", ");
        return CWA.confirm(B.merge_confirm.replace("%from", from).replace("%to", d.to || ""), B.merge).then(function (ok) {
          if (ok) return json(B.merge_url, { Merge_books: ids }).then(function () { done(); });
        });
      }).catch(fail);
    }
  });
})();
