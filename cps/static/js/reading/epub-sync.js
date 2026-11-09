/* Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later */
/* The built-in EPUB reader as a reading device, like the Kobo and KOReader:
 *  - it opens where you last were, on any device (the server sends the newest position),
 *  - it saves its own position, so the Kobo, KOReader and the book page follow it,
 *  - selected text can be highlighted, with a colour and a note, for the Highlights page,
 *  - the time spent on each page goes to the reading statistics.
 */
(function () {
  "use strict";
  var cfg = window.calibre || {};
  var reader = window.reader;
  var book = reader && reader.book;
  var rendition = reader && reader.rendition;
  if (!book || !rendition) return;

  var i18n = cfg.i18n || {};
  var token = (document.querySelector("meta[name='csrf-token']") || {}).content || "";
  var progressDiv = document.getElementById("progress");
  var ready = false;  // true once the start position is shown; nothing is saved before that

  function post(url, data, keepalive) {
    if (!url || !cfg.signedIn) return Promise.resolve(null);
    return fetch(url, {
      method: "POST", credentials: "same-origin", keepalive: !!keepalive,
      headers: { "Content-Type": "application/json", "X-CSRFToken": token },
      body: JSON.stringify(data)
    }).then(function (response) { return response.ok ? response : Promise.reject(response.status); });
  }

  var toastTimer = null;
  function toast(text) {
    var box = document.getElementById("reader-toast");
    if (!box || !text) return;
    box.textContent = text;
    box.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { box.hidden = true; }, 4500);
  }

  function located() { return book.locations && book.locations.length() > 0; }
  function percentOf(cfi) { return located() ? book.locations.percentageFromCfi(cfi) * 100 : null; }

  // ---------- Position ----------

  var saveTimer = null;
  var lastSaved = null;
  function savePosition(keepalive) {
    var location = rendition.currentLocation();
    if (!ready || !location || !location.start) return;
    var cfi = location.start.cfi;
    var percent = percentOf(cfi);
    if (percent === null || cfi === lastSaved) return;
    lastSaved = cfi;
    post(cfg.positionUrl, { cfi: cfi, percent: Math.round(percent * 100) / 100, format: cfg.format }, keepalive)
      .catch(function () { lastSaved = null; });
  }

  var locationsReady = book.ready.then(function () { return book.locations.generate(1600); });

  book.ready.then(function () {
    var start = cfg.start;
    function announce() {
      if (!start || start.source === "web") return;
      var message = start.source === "koreader" ? i18n.from_koreader : i18n.from_kobo;
      if (message) toast(message.replace("{percent}", Math.round(start.percent) + "%"));
    }
    if (start && start.cfi) {  // an exact position: the reader's own, or KOReader's translated
      return rendition.display(start.cfi).then(announce, function () { return null; }).then(function () { return locationsReady; });
    }
    return locationsReady.then(function () {
      if (!start || !(start.percent > 0.5)) return null;
      var cfi = book.locations.cfiFromPercentage(Math.min(start.percent, 100) / 100);
      if (!cfi) return null;
      return rendition.display(cfi).then(announce);
    });
  }).catch(function (error) {
    try { console.warn("Could not restore the reading position", error); } catch (e) {}
  }).then(function () {
    ready = true;
    var location = rendition.currentLocation();
    // Opening a book is not reading it: only a move from here is saved.
    if (location && location.start) lastSaved = location.start.cfi;
    showProgress(location);
    startPage(location);
  });

  function showProgress(location) {
    if (!progressDiv || !location || !location.end) return;
    var percent = percentOf(location.end.cfi);
    if (percent !== null) progressDiv.textContent = Math.round(percent) + "%";
  }

  // ---------- Reading time, page by page ----------

  var current = null;   // the page on screen: {page, total, since (ms)}
  var pending = [];     // [page, start (s), seconds, total pages]
  function pageOf(location) {
    if (!located() || !location || !location.start) return null;
    var index = book.locations.locationFromCfi(location.start.cfi);
    return index >= 0 ? { page: index + 1, total: book.locations.length() } : null;
  }
  function startPage(location) {
    var page = pageOf(location);
    current = page && !document.hidden ? { page: page.page, total: page.total, since: Date.now() } : null;
  }
  function closePage() {
    if (!current) return;
    var seconds = Math.round((Date.now() - current.since) / 1000);
    if (seconds >= 3) pending.push([current.page, Math.round(current.since / 1000), Math.min(seconds, 120), current.total]);
    current = null;
  }
  function flush(keepalive) {
    if (!pending.length) return;
    var batch = pending;
    pending = [];
    post(cfg.pagesUrl, { pages: batch }, keepalive).catch(function () { pending = batch.concat(pending).slice(-300); });
  }
  setInterval(function () { flush(false); }, 60000);

  function away() {
    closePage();
    clearTimeout(saveTimer);
    savePosition(true);
    flush(true);
  }
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) away();
    else if (ready) startPage(rendition.currentLocation());
  });
  window.addEventListener("pagehide", away);

  rendition.on("relocated", function (location) {
    showProgress(location);
    hideBar();
    if (!ready) return;
    closePage();
    startPage(location);
    if (pending.length >= 20) flush(false);
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () { savePosition(false); }, 2500);
  });

  // ---------- Highlights ----------

  var COLORS = { yellow: "#F2C230", green: "#6CC070", blue: "#5B9BE0", pink: "#E07AA8" };
  var marks = {};   // cfi -> {color, note, text}
  (cfg.highlights || []).forEach(function (item) { marks[item.cfi] = item; });

  function draw(cfi) {
    var color = COLORS[marks[cfi].color] || COLORS.yellow;
    try { rendition.annotations.remove(cfi, "highlight"); } catch (e) {}
    try { rendition.annotations.remove(cfi, "underline"); } catch (e) {}
    rendition.annotations.highlight(cfi, {}, function (event) { openBar(cfi, event && event.target); }, "sc-highlight",
      { fill: color, "fill-opacity": "0.38", "mix-blend-mode": "multiply" });
    if (marks[cfi].note) {
      // A passage with a note also gets a line under it, so notes can be spotted while reading.
      rendition.annotations.underline(cfi, {}, function (event) { openBar(cfi, event && event.target); }, "sc-note",
        { stroke: color, "stroke-width": "2", "stroke-opacity": "0.9" });
    }
  }
  book.ready.then(function () { Object.keys(marks).forEach(draw); });

  var bar = document.getElementById("hl-bar");
  var noteForm = bar && bar.querySelector("[data-hl-note-form]");
  var noteText = noteForm && noteForm.querySelector("textarea");
  var deleteButton = bar && bar.querySelector("[data-hl-delete]");
  var editRow = bar && bar.querySelector("[data-hl-edit]");
  var fromBox = bar && bar.querySelector("[data-hl-from]");
  var fromNote = fromBox && fromBox.querySelector("[data-hl-from-note]");

  // Highlights made on a Kobo or in KOReader are shown with where they come from, and changed there.
  function showFrom(mark) {
    var device = mark && mark.source;
    fromBox.hidden = !device;
    editRow.hidden = !!device;
    if (!device) return;
    fromBox.querySelector("[data-hl-from-label]").textContent =
      device === "kobo" ? i18n.highlight_from_kobo : i18n.highlight_from_koreader;
    fromNote.textContent = mark.note || "";
    fromNote.hidden = !mark.note;
  }
  var active = null;   // {cfi, text, contents (only for a fresh selection)}

  function chapter() {
    var location = rendition.currentLocation();
    var href = location && location.start && location.start.href;
    var item = href && book.navigation && book.navigation.get(href);
    if (!item && href && book.navigation) {
      book.navigation.forEach(function (entry) { if (!item && entry.href && entry.href.split("#")[0] === href) item = entry; });
    }
    return item && item.label ? item.label.trim() : "";
  }

  function place(rect) {
    if (!bar || !rect) return;
    bar.hidden = false;
    var width = bar.offsetWidth, height = bar.offsetHeight;
    var left = Math.max(8, Math.min(window.innerWidth - width - 8, rect.left + rect.width / 2 - width / 2));
    var top = rect.top - height - 12;
    if (top < 8) top = rect.bottom + 12;
    bar.style.left = left + "px";
    bar.style.top = Math.min(top, window.innerHeight - height - 8) + "px";
  }

  function selectionRect(contents) {
    try {
      var range = contents.window.getSelection().getRangeAt(0).getBoundingClientRect();
      var frame = contents.window.frameElement.getBoundingClientRect();
      return { left: frame.left + range.left, top: frame.top + range.top, bottom: frame.top + range.bottom, width: range.width };
    } catch (e) {
      return null;
    }
  }

  var openedAt = 0;
  function openBar(cfi, element) {
    if (!bar || !cfg.signedIn) return;
    openedAt = Date.now();
    active = { cfi: cfi, text: marks[cfi] ? marks[cfi].text : "" };
    showFrom(marks[cfi]);
    deleteButton.hidden = false;
    noteText.value = (marks[cfi] && marks[cfi].note) || "";
    noteForm.hidden = !noteText.value || !!(marks[cfi] && marks[cfi].source);
    markColor(marks[cfi] && marks[cfi].color);
    place(element && element.getBoundingClientRect ? element.getBoundingClientRect() : null);
  }

  function hideBar() {
    if (bar) bar.hidden = true;
    active = null;
  }

  function markColor(color) {
    Array.prototype.forEach.call(bar.querySelectorAll("[data-hl-color]"), function (button) {
      button.setAttribute("aria-pressed", button.getAttribute("data-hl-color") === color ? "true" : "false");
    });
  }

  rendition.on("selected", function (cfiRange, contents) {
    if (!cfg.signedIn || !bar) return;
    book.getRange(cfiRange).then(function (range) {
      var text = range ? range.toString().replace(/\s+/g, " ").trim() : "";
      if (!text) return;
      active = { cfi: cfiRange, text: text.slice(0, 20000), contents: contents };
      showFrom(null);
      deleteButton.hidden = !marks[cfiRange];
      noteForm.hidden = true;
      noteText.value = "";
      markColor(null);
      openedAt = Date.now();
      place(selectionRect(contents));
    });
  });

  function clearSelection() {
    try { if (active && active.contents) active.contents.window.getSelection().removeAllRanges(); } catch (e) {}
  }

  function save(changes) {
    if (!active || (marks[active.cfi] && marks[active.cfi].source)) return;
    var cfi = active.cfi;
    var mark = marks[cfi] = Object.assign({ color: "yellow", note: "", text: active.text }, marks[cfi], changes);
    draw(cfi);
    clearSelection();
    post(cfg.highlightUrl, { cfi: cfi, text: mark.text, color: mark.color, note: mark.note, chapter: chapter() })
      .catch(function () { toast(i18n.highlight_failed); });
  }

  if (bar) {
    bar.addEventListener("mousedown", function (event) { event.preventDefault(); });  // keep the selection
    bar.addEventListener("click", function (event) {
      var color = event.target.closest("[data-hl-color]");
      if (color) {
        save({ color: color.getAttribute("data-hl-color") });
        hideBar();
        return;
      }
      if (event.target.closest("[data-hl-note]")) {
        noteForm.hidden = false;
        place(bar.getBoundingClientRect());
        noteText.focus();
        return;
      }
      if (event.target.closest("[data-hl-delete]") && active && marks[active.cfi] && !marks[active.cfi].source) {
        var cfi = active.cfi;
        delete marks[cfi];
        try { rendition.annotations.remove(cfi, "highlight"); } catch (e) {}
        try { rendition.annotations.remove(cfi, "underline"); } catch (e) {}
        post(cfg.highlightDeleteUrl, { cfi: cfi }).catch(function () { toast(i18n.highlight_failed); });
        hideBar();
      }
    });
    noteForm.addEventListener("submit", function (event) {
      event.preventDefault();
      save({ note: noteText.value.trim() });
      hideBar();
    });
    document.addEventListener("keydown", function (event) { if (event.key === "Escape") hideBar(); });
    // A click in the page, outside a highlight and without selecting text, closes the toolbar.
    rendition.on("click", function () { if (Date.now() - openedAt > 400) hideBar(); });
    document.addEventListener("mousedown", function (event) {
      if (!bar.hidden && !bar.contains(event.target)) hideBar();
    });
  }
})();
