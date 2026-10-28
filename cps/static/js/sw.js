// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Service worker: makes Scriptorium installable, keeps static files for fast loads, shows a page when
// offline, and receives books shared from other apps ("Share → Scriptorium") without exposing a
// CSRF-free upload endpoint: the files wait in a cache until the signed-in page uploads them.
// Served from /sw.js so its scope is the whole site. HTML pages and covers are never cached.
"use strict";

var VERSION = new URL(self.location.href).searchParams.get("v") || "1";
var STATIC_CACHE = "scriptorium-static-" + VERSION;
var SHARE_CACHE = "scriptorium-share";
var SCOPE = self.registration.scope;  // ends with "/"
var OFFLINE_URL = SCOPE + "offline";
var SHARE_PAGE = SCOPE + "share";
var PENDING = SCOPE + "share-target/pending/";

self.addEventListener("install", function (event) {
  event.waitUntil(caches.open(STATIC_CACHE).then(function (cache) { return cache.add(OFFLINE_URL); }));
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (key) {
      return key.indexOf("scriptorium-static-") === 0 && key !== STATIC_CACHE;
    }).map(function (key) { return caches.delete(key); }));
  }).then(function () { return self.clients.claim(); }));
});

function receiveShare(request) {
  return request.formData().then(function (form) {
    var files = form.getAll("file").filter(function (f) { return f && typeof f === "object" && f.size; });
    return caches.open(SHARE_CACHE).then(function (cache) {
      var stamp = Date.now();
      return Promise.all(files.map(function (file, i) {
        var key = PENDING + stamp + "-" + i + "/" + encodeURIComponent(file.name || "book");
        return cache.put(key, new Response(file, { headers: { "Content-Type": file.type || "application/octet-stream" } }));
      }));
    });
  }).catch(function () { /* the share page explains when nothing arrived */ })
    .then(function () { return Response.redirect(SHARE_PAGE, 303); });
}

self.addEventListener("fetch", function (event) {
  var request = event.request;
  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.method === "POST" && url.href.split("?")[0] === SCOPE + "share-target") {
    event.respondWith(receiveShare(request));
    return;
  }
  if (request.method !== "GET") return;

  // Static files: answer from the cache, refresh in the background (URLs carry a content hash).
  if (url.href.indexOf(SCOPE + "static/") === 0) {
    event.respondWith(caches.open(STATIC_CACHE).then(function (cache) {
      return cache.match(request).then(function (hit) {
        var fresh = fetch(request).then(function (response) {
          if (response.ok) cache.put(request, response.clone());
          return response;
        }).catch(function () { return hit; });
        return hit || fresh;
      });
    }));
    return;
  }

  // Pages: always from the network; the offline page only when there is no network at all.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(function () {
      return caches.match(OFFLINE_URL);
    }));
  }
});
