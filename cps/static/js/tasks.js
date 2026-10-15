// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Tasks page: live task list and scheduled items, rendered as text.
(function () {
  "use strict";
  var CWA = window.CWA;
  if (!CWA) return;
  var S = JSON.parse(document.getElementById("tasks-i18n").textContent);
  // 0 waiting, 1 failed, 2 started, 3 finished, 4 ended, 5 cancelled
  var STATUS_CLASS = { 0: "", 1: "badge--danger", 2: "badge--accent", 3: "badge--success", 4: "", 5: "" };

  function td(text, cls) {
    var c = document.createElement("td");
    if (cls) c.className = cls;
    c.textContent = text === undefined || text === null ? "" : String(text);
    return c;
  }
  function decode(text) {
    // Task names are HTML-escaped on the server; show them as plain text.
    var t = document.createElement("textarea");
    t.innerHTML = String(text || "");
    return t.value;
  }
  function emptyRow(tbody, cols, text) {
    tbody.textContent = "";
    var tr = document.createElement("tr");
    var c = td(text, "muted center");
    c.colSpan = cols;
    tr.appendChild(c);
    tbody.appendChild(tr);
  }
  function cancelButton(onClick) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "btn btn-sm btn-danger-ghost";
    b.textContent = S.cancel;
    b.addEventListener("click", onClick);
    return b;
  }

  var tasks = document.getElementById("tasktable");
  var isAdmin = tasks && tasks.hasAttribute("data-cancel-url");
  function loadTasks() {
    CWA.request(tasks.getAttribute("data-url")).then(function (r) { return r.json(); }).then(function (rows) {
      var tbody = tasks.querySelector("tbody");
      var cols = tasks.querySelectorAll("thead th").length;
      if (!rows.length) { emptyRow(tbody, cols, S.none); return; }
      tbody.textContent = "";
      rows.slice().reverse().forEach(function (row) {
        var tr = document.createElement("tr");
        if (isAdmin) tr.appendChild(td(decode(row.user)));
        tr.appendChild(td(decode(row.taskMessage), "cell-strong cell-wrap"));
        var status = td("");
        var badge = document.createElement("span");
        badge.className = "badge " + (STATUS_CLASS[row.stat] || "");
        badge.textContent = row.status || "";
        status.appendChild(badge);
        tr.appendChild(status);
        tr.appendChild(td(row.progress, "num"));
        tr.appendChild(td(row.runtime, "num"));
        tr.appendChild(td(row.starttime, "nowrap"));
        tr.appendChild(td(row.error, "cell-wrap muted"));
        if (isAdmin) {
          var actions = td("");
          if (row.is_cancellable && (row.stat === 0 || row.stat === 2)) {
            actions.appendChild(cancelButton(function () {
              CWA.confirm(S.cancel_task, S.cancel).then(function (ok) {
                if (!ok) return;
                CWA.request(tasks.getAttribute("data-cancel-url"), {
                  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_id: row.task_id })
                }).then(loadTasks);
              });
            }));
          }
          tr.appendChild(actions);
        }
        tbody.appendChild(tr);
      });
    }).catch(function () {});
  }

  function localTime(utc) {
    if (!utc) return "";
    var d = new Date(String(utc).replace(" ", "T") + (/[zZ]|[+-]\d\d:?\d\d$/.test(utc) ? "" : "Z"));
    return isNaN(d.getTime()) ? utc : d.toLocaleString();
  }
  function loadScheduled(table) {
    CWA.request(table.getAttribute("data-url")).then(function (r) { return r.json(); }).then(function (data) {
      var items = (data && data.items) || [];
      var tbody = table.querySelector("tbody");
      var cols = table.querySelectorAll("thead th").length;
      if (!items.length) { emptyRow(tbody, cols, S.none_scheduled); return; }
      tbody.textContent = "";
      items.forEach(function (item) {
        var tr = document.createElement("tr");
        if (table.getAttribute("data-kind") === "ops") tr.appendChild(td(item.job_type));
        tr.appendChild(td(item.title, "cell-strong"));
        tr.appendChild(td(item.username));
        tr.appendChild(td(localTime(item.run_at_utc), "nowrap"));
        tr.appendChild(td(item.state));
        var actions = td("");
        if (item.state === "scheduled") {
          actions.appendChild(cancelButton(function () {
            CWA.confirm(S.cancel_scheduled, S.cancel).then(function (ok) {
              if (!ok) return;
              CWA.request(table.getAttribute("data-cancel-url"), {
                method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: item.id })
              }).then(function (r) {
                if (r.ok) CWA.toast(S.cancelled, "success");
                loadScheduled(table);
              });
            });
          }));
        }
        tr.appendChild(actions);
        tbody.appendChild(tr);
      });
    }).catch(function () {});
  }

  if (tasks) {
    loadTasks();
    setInterval(function () { if (!document.hidden) loadTasks(); }, 4000);
  }
  Array.prototype.forEach.call(document.querySelectorAll("#upcomingtable, #upcomingopstable"), function (t) {
    loadScheduled(t);
    setInterval(function () { if (!document.hidden) loadScheduled(t); }, 15000);
  });
})();
