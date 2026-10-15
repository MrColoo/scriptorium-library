// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
// Book metadata editor: identifiers, cover preview, description preview, metadata search.
// All provider data is inserted with textContent / attributes, never as HTML.
(function () {
  "use strict";
  var CWA = window.CWA;
  var form = document.getElementById("book_edit_frm");
  if (!CWA || !form) return;
  var cfg = {};
  try { cfg = JSON.parse(document.getElementById("book-edit-data").textContent); } catch (e) { cfg = { strings: {} }; }
  var S = cfg.strings || {};

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function setValue(id, value) {
    var input = $(id);
    if (!input || value === undefined || value === null) return;
    input.value = value;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // ---------- Swap title and author ----------
  var swap = $("xchange");
  if (swap) {
    swap.addEventListener("click", function () {
      var title = $("title"), authors = $("authors");
      var tmp = title.value;
      title.value = authors.value;
      authors.value = tmp;
    });
  }

  // ---------- Identifiers ----------
  var idList = $("identifier-list");
  var idTemplate = $("identifier-template");
  function addIdentifier(type, value) {
    var key = Math.floor(Math.random() * 1e9).toString(36);
    var row = idTemplate.content.firstElementChild.cloneNode(true);
    var inputs = row.querySelectorAll("input");
    inputs[0].name = "identifier-type-" + key;
    inputs[1].name = "identifier-val-" + key;
    inputs[0].value = type || "";
    inputs[1].value = value || "";
    idList.appendChild(row);
    return row;
  }
  function setIdentifier(type, value) {
    var match = Array.prototype.find.call(idList.querySelectorAll(".identifier-row"), function (row) {
      return row.querySelector(".identifier-type").value.trim().toLowerCase() === type.toLowerCase();
    });
    if (match) match.querySelector(".identifier-val").value = value;
    else addIdentifier(type, value);
  }
  if (idList && idTemplate) {
    $("add-identifier-line").addEventListener("click", function () {
      addIdentifier().querySelector("input").focus();
    });
    idList.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-identifier-remove]");
      if (btn) btn.closest(".identifier-row").remove();
    });
  }

  // ---------- Cover ----------
  var cover = $("detailcover");
  var sizeLabel = $("cover-size");
  function showSize() {
    if (cover && cover.naturalWidth && sizeLabel) sizeLabel.textContent = cover.naturalWidth + " × " + cover.naturalHeight + " px";
  }
  if (cover) {
    if (cover.complete) showSize();
    cover.addEventListener("load", showSize);
  }
  var coverFile = $("btn-upload-cover");
  if (coverFile) {
    coverFile.addEventListener("change", function () {
      var file = coverFile.files && coverFile.files[0];
      $("upload-cover").textContent = file ? file.name : (S.choose_image || "");
      if (file && cover) cover.src = URL.createObjectURL(file);
    });
  }
  var coverUrl = $("cover_url");
  if (coverUrl) {
    coverUrl.addEventListener("change", function () {
      if (/^https?:\/\//i.test(coverUrl.value) && cover) cover.src = coverUrl.value;
    });
  }

  // ---------- Description preview (sandboxed iframe: no scripts, no same-origin access) ----------
  var comments = $("comments");
  var preview = $("comments-preview");
  Array.prototype.forEach.call(document.querySelectorAll("[data-desc-tab]"), function (tab) {
    tab.addEventListener("click", function () {
      var showPreview = tab.getAttribute("data-desc-tab") === "preview";
      Array.prototype.forEach.call(document.querySelectorAll("[data-desc-tab]"), function (t) {
        var on = t === tab;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.setAttribute("aria-pressed", on ? "true" : "false");
      });
      if (showPreview) {
        preview.srcdoc = "<!doctype html><meta charset=utf-8><style>body{font:17px/1.6 Georgia,serif;color:#2A2A30;margin:16px;}</style>" + comments.value;
      }
      preview.hidden = !showPreview;
      comments.hidden = showPreview;
    });
  });

  // ---------- Fetch metadata ----------
  var dialog = $("meta-dialog");
  var providersBox = $("metadata_provider");
  var status = $("meta-status");
  var results = $("book-list");
  var keyword = $("keyword");
  var providersLoaded = false;
  var lastQuery = "";
  var selectionsKey = "cwa-meta-selection";
  var selections = {};
  try { selections = JSON.parse(localStorage.getItem(selectionsKey) || "{}") || {}; } catch (e) { selections = {}; }

  function rememberSelection(key, checked) {
    selections[key] = checked;
    try { localStorage.setItem(selectionsKey, JSON.stringify(selections)); } catch (e) { /* storage blocked */ }
  }

  function loadProviders() {
    if (providersLoaded) return;
    providersLoaded = true;
    CWA.request(cfg.provider_url).then(function (r) { return r.json(); }).then(function (data) {
      providersBox.textContent = "";
      var disabled = [];
      data.forEach(function (p) {
        if (Object.prototype.hasOwnProperty.call(p, "globally_enabled") && !p.globally_enabled) { disabled.push(p.name); return; }
        var label = el("label", "chip provider-chip");
        var box = document.createElement("input");
        box.type = "checkbox";
        box.checked = !!p.active;
        box.dataset.provider = p.id;
        box.dataset.initial = p.initial ? "1" : "";
        box.addEventListener("change", function () { toggleProvider(box); });
        label.appendChild(box);
        label.appendChild(document.createTextNode(p.name));
        providersBox.appendChild(label);
      });
      if (disabled.length) providersBox.appendChild(el("span", "tiny muted", (S.disabled || "") + " " + disabled.join(", ")));
    }).catch(function () { providersLoaded = false; });
  }

  function toggleProvider(box) {
    var params = { id: box.dataset.provider, value: box.checked };
    if (!box.dataset.initial && box.checked && lastQuery) {
      params.initial = false;
      params.query = lastQuery;
    }
    CWA.request(cfg.provider_change_url.replace("__id__", encodeURIComponent(box.dataset.provider)), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params)
    }).then(function (r) { return r.json(); }).then(function (data) {
      box.dataset.initial = "1";
      if (Array.isArray(data)) data.forEach(function (book) { results.appendChild(renderResult(book)); });
    }).catch(function () {});
  }

  function search(q) {
    if (!q) return;
    lastQuery = q;
    status.textContent = S.loading || "";
    results.textContent = "";
    CWA.request(cfg.search_url, { method: "POST", body: new URLSearchParams({ query: q }) })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (data) {
        status.textContent = data.length ? "" : (S.no_result || "");
        data.forEach(function (book) { results.appendChild(renderResult(book)); });
      })
      .catch(function () { status.textContent = S.search_error || ""; });
  }

  function textOf(html) {
    var doc = new DOMParser().parseFromString(String(html || ""), "text/html");
    return (doc.body.textContent || "").trim();
  }

  function renderResult(book) {
    var li = el("li", "meta-result");
    var boxes = [];
    function field(dl, key, label, value, clamp) {
      if (value === undefined || value === null || value === "" || (Array.isArray(value) && !value.length)) return;
      var dt = el("dt");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.dataset.key = key;
      box.checked = Object.prototype.hasOwnProperty.call(selections, key) ? !!selections[key] : true;
      box.setAttribute("aria-label", label);
      box.addEventListener("change", function () { rememberSelection(key, box.checked); });
      boxes.push(box);
      dt.appendChild(box);
      dt.appendChild(document.createTextNode(label));
      var dd = el("dd", clamp ? "clamp" : "", Array.isArray(value) ? value.join(key === "authors" ? " & " : ", ") : String(value));
      dl.appendChild(dt);
      dl.appendChild(dd);
      return dd;
    }

    var side = el("div", "meta-result-cover");
    var img = document.createElement("img");
    img.alt = "";
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    img.src = /^https?:\/\//i.test(book.cover || "") ? book.cover : cfg.fallback_cover;
    var dims = el("span", "tiny muted");
    img.addEventListener("load", function () { if (img.naturalWidth > 1) dims.textContent = img.naturalWidth + " × " + img.naturalHeight; });
    side.appendChild(img);
    side.appendChild(dims);
    if (book.cover) {
      var coverPick = el("label", "row tiny");
      var coverBox = document.createElement("input");
      coverBox.type = "checkbox";
      coverBox.dataset.key = "cover";
      coverBox.checked = Object.prototype.hasOwnProperty.call(selections, "cover") ? !!selections.cover : true;
      coverBox.addEventListener("change", function () { rememberSelection("cover", coverBox.checked); });
      boxes.push(coverBox);
      coverPick.appendChild(coverBox);
      coverPick.appendChild(document.createTextNode(S.cover || "Cover"));
      side.appendChild(coverPick);
    }

    var body = el("div", "meta-result-body");
    var head = el("div", "row-between");
    var title = el("strong", "", book.title || "");
    var source = book.source || {};
    var sourceLink = el("a", "tiny", source.description || "");
    if (/^https?:\/\//i.test(book.url || source.link || "")) {
      sourceLink.href = book.url || source.link;
      sourceLink.target = "_blank";
      sourceLink.rel = "noopener noreferrer";
    }
    head.appendChild(title);
    head.appendChild(sourceLink);
    body.appendChild(head);

    var dl = el("dl", "meta-fields");
    field(dl, "title", S.title, book.title);
    field(dl, "authors", S.authors, book.authors);
    field(dl, "publisher", S.publisher, book.publisher);
    field(dl, "pubDate", S.pubDate, book.publishedDate);
    field(dl, "series", S.series, book.series);
    field(dl, "seriesIndex", S.seriesIndex, book.series_index);
    field(dl, "rating", S.rating, book.rating ? book.rating + " / 5" : "");
    field(dl, "description", S.description, textOf(book.description), true);
    field(dl, "tags", S.tags, book.tags);
    Object.keys(book.identifiers || {}).forEach(function (key) {
      var value = book.identifiers[key];
      if (value === "") return;
      var dd = field(dl, key, (S.identifier || "") + " · " + key, value);
      if (dd && key === "hardcover-id" && lastQuery.indexOf("hardcover-id") === -1) {
        var editions = el("button", "btn btn-link tiny", " " + (S.editions || ""));
        editions.type = "button";
        editions.addEventListener("click", function () {
          keyword.value = "hardcover-id:" + value;
          search(keyword.value);
        });
        dd.appendChild(editions);
      }
    });
    body.appendChild(dl);

    var apply = el("button", "btn btn-sm btn-primary", S.apply || "Apply");
    apply.type = "button";
    apply.addEventListener("click", function () {
      var chosen = {};
      boxes.forEach(function (b) { chosen[b.dataset.key] = b.checked; });
      applyBook(book, chosen);
    });
    var actions = el("div", "row");
    actions.appendChild(apply);
    if (book.format) actions.appendChild(el("span", "tiny muted", book.format));
    body.appendChild(actions);

    li.appendChild(side);
    li.appendChild(body);
    return li;
  }

  function mergeList(id, values) {
    var input = $(id);
    if (!input || !values || !values.length) return;
    var present = input.value.split(",").map(function (v) { return v.trim(); }).filter(Boolean);
    values.forEach(function (v) { if (present.indexOf(v) === -1) present.push(v); });
    input.value = present.join(", ");
  }

  function applyBook(book, chosen) {
    if (chosen.title) setValue("title", book.title);
    if (chosen.authors && book.authors) setValue("authors", book.authors.join(" & "));
    if (chosen.publisher) setValue("publisher", book.publisher);
    if (chosen.pubDate && book.publishedDate) setValue("pubdate", String(book.publishedDate).slice(0, 10));
    if (chosen.series && book.series !== undefined) setValue("series", book.series);
    if (chosen.seriesIndex && book.series_index !== undefined) setValue("series_index", book.series_index);
    if (chosen.rating && book.rating) setValue("rating", String(Math.max(1, Math.min(5, Math.round(book.rating)))));
    if (chosen.description) setValue("comments", book.description || "");
    if (chosen.tags) mergeList("tags", book.tags);
    mergeList("languages", book.languages);
    if (chosen.cover && /^https?:\/\//i.test(book.cover || "")) {
      setValue("cover_url", book.cover);
      if (cover) cover.src = book.cover;
    }
    Object.keys(book.identifiers || {}).forEach(function (key) {
      if (chosen[key] && book.identifiers[key] !== "") setIdentifier(key, String(book.identifiers[key]));
    });
    CWA.closeDialog(dialog);
    CWA.toast(S.applied || "", "success");
  }

  if (dialog) {
    var opener = $("get_meta");
    opener.addEventListener("click", function () {
      loadProviders();
      if (!keyword.value) {
        var authors = $("authors").value.split("&")[0].trim();
        keyword.value = ($("title").value + " " + authors).trim();
      }
      setTimeout(function () { keyword.focus(); keyword.select(); }, 50);
      if (!results.children.length && keyword.value) search(keyword.value.trim());
    });
    $("meta-search").addEventListener("submit", function (e) {
      e.preventDefault();
      search(keyword.value.trim());
    });
  }
})();
