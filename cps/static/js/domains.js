// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Registration domain allow/deny lists on the email settings page.
(function () {
  "use strict";
  var CWA = window.CWA;
  var i18nEl = document.getElementById("domains-i18n");
  if (!CWA || !i18nEl) return;
  var S = JSON.parse(i18nEl.textContent);

  Array.prototype.forEach.call(document.querySelectorAll("[data-domains]"), function (box) {
    var list = box.querySelector("[data-domain-list]");
    function load() {
      CWA.request(box.getAttribute("data-list-url")).then(function (r) { return r.json(); }).then(function (items) {
        list.textContent = "";
        items.forEach(function (item) {
          var li = document.createElement("li");
          li.className = "restriction-item";
          var text = document.createElement("span");
          text.className = "grow mono small break";
          text.textContent = item.domain;
          var del = document.createElement("button");
          del.type = "button";
          del.className = "btn btn-ghost btn-icon btn-sm";
          del.setAttribute("aria-label", S.remove + " " + item.domain);
          del.appendChild(CWA.icon("x"));
          del.addEventListener("click", function () {
            CWA.confirm(S.confirm, S.remove).then(function (ok) {
              if (!ok) return;
              CWA.request(box.getAttribute("data-delete-url"), { method: "POST", body: new URLSearchParams({ domainid: String(item.id) }) }).then(load);
            });
          });
          li.appendChild(text);
          li.appendChild(del);
          list.appendChild(li);
        });
      });
    }
    box.querySelector("[data-domain-add]").addEventListener("submit", function (e) {
      e.preventDefault();
      var input = e.target.querySelector("input");
      CWA.request(box.getAttribute("data-add-url"), { method: "POST", body: new URLSearchParams({ domainname: input.value.trim() }) })
        .then(function () { input.value = ""; load(); });
    });
    load();
  });
})();
