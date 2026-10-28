// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// /share: uploads the books the service worker received from "Share → Scriptorium", then forgets them.
(function () {
  "use strict";
  var CWA = window.CWA;
  var box = document.getElementById("share-status");
  if (!CWA || !box) return;
  var T = {};
  try { T = JSON.parse(document.getElementById("share-i18n").textContent); } catch (e) { /* defaults below */ }
  var message = box.querySelector("[data-share-message]");
  var list = box.querySelector("[data-share-list]");
  function say(text) { message.textContent = text; }

  if (new URLSearchParams(window.location.search).has("missed")) { say(T.missed || ""); return; }
  if (!("caches" in window)) { say(T.unsupported || ""); return; }

  caches.open("scriptorium-share").then(function (cache) {
    return cache.keys().then(function (requests) {
      var pending = requests.filter(function (r) { return r.url.indexOf("/share-target/pending/") !== -1; });
      if (!pending.length) { say(T.none || ""); return; }
      if (box.getAttribute("data-can-upload") !== "true") {
        say(T.no_permission || "");
        return Promise.all(pending.map(function (r) { return cache.delete(r); }));
      }
      return Promise.all(pending.map(function (r) {
        return cache.match(r).then(function (response) {
          return response.blob().then(function (blob) {
            var name = decodeURIComponent(r.url.split("/").pop() || "book");
            return new File([blob], name, { type: blob.type });
          });
        });
      })).then(function (files) {
        say((T.found || "%d").replace("%d", files.length));
        files.forEach(function (file) {
          var li = document.createElement("li");
          li.textContent = file.name;
          list.appendChild(li);
        });
        return Promise.all(pending.map(function (r) { return cache.delete(r); })).then(function () {
          CWA.upload(files, document.body.dataset.uploadUrl, { field: "btn-upload" });
        });
      });
    });
  }).catch(function () { say(T.unsupported || ""); });
})();
