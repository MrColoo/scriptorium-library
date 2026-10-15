// Scriptorium – based on Calibre-Web Automated · Copyright (C) 2026 Mrcoloo · SPDX-License-Identifier: GPL-3.0-or-later
//
// Behaviour shared by every page. No framework and no inline handlers: elements opt in with
// data-* attributes, so the Content-Security-Policy can forbid inline scripts.
//
//   data-nav-toggle                 opens/closes the sidebar drawer on small screens
//   data-dialog-open="id"           opens <dialog id>; data-dialog-close closes the enclosing one
//   form[data-confirm="message"]    asks before submitting (data-confirm-action for the button label)
//   data-post="url"                 POSTs (with CSRF token) on click; data-reload / data-redirect / data-remove-closest
//   data-copy="text" / data-copy-target="#id"
//   data-password-toggle            shows/hides the password in the same .password-field
//   data-autosubmit                 submits the form (or follows the option value) on change
//   data-theme-set="light|dark|system"
//   data-action="library-refresh"   triggers the CWA ingest refresh
//   data-upload-input               file input that uploads straight away
//   data-clamp-toggle="#id"         expands a clamped block of text
//   data-dismiss                    removes the closest .alert
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;
  var body = doc.body;

  var I18N = {};
  try {
    var i18nEl = doc.getElementById("app-i18n");
    if (i18nEl) I18N = JSON.parse(i18nEl.textContent || "{}");
  } catch (e) { I18N = {}; }
  function t(key, fallback) { return I18N[key] || fallback || key; }

  function csrfToken() {
    var meta = doc.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function request(url, options) {
    options = options || {};
    var headers = new Headers(options.headers || {});
    var method = (options.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") headers.set("X-CSRFToken", csrfToken());
    headers.set("X-Requested-With", "XMLHttpRequest");
    return fetch(url, {
      method: method,
      headers: headers,
      body: options.body,
      credentials: "same-origin",
      redirect: options.redirect || "follow"
    });
  }

  function icon(name, extraClass) {
    var ns = "http://www.w3.org/2000/svg";
    var svg = doc.createElementNS(ns, "svg");
    svg.setAttribute("class", "icon" + (extraClass ? " " + extraClass : ""));
    svg.setAttribute("aria-hidden", "true");
    var use = doc.createElementNS(ns, "use");
    use.setAttribute("href", (body.dataset.iconSprite || "") + "#" + name);
    svg.appendChild(use);
    return svg;
  }

  // ---------- Toasts ----------
  var toaster = doc.querySelector(".toaster");
  function toast(message, kind, timeout) {
    if (!toaster) return;
    kind = kind || "info";
    var el = doc.createElement("div");
    el.className = "toast toast--" + kind;
    el.setAttribute("role", kind === "error" ? "alert" : "status");
    el.appendChild(icon(kind === "error" ? "alert" : kind === "success" ? "check-circle" : "info"));
    var text = doc.createElement("div");
    text.className = "toast-body";
    text.textContent = message;
    el.appendChild(text);
    var close = doc.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost btn-icon btn-sm";
    close.setAttribute("aria-label", t("close", "Close"));
    close.appendChild(icon("x"));
    close.addEventListener("click", function () { dismissToast(el); });
    el.appendChild(close);
    toaster.appendChild(el);
    if (timeout !== 0) setTimeout(function () { dismissToast(el); }, timeout || (kind === "error" ? 9000 : 5000));
    return el;
  }
  function dismissToast(el) {
    if (!el || !el.parentNode) return;
    el.classList.add("is-leaving");
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 200);
  }
  // Server-rendered toasts (flashed messages) dismiss themselves too.
  if (toaster) {
    Array.prototype.forEach.call(toaster.querySelectorAll(".toast"), function (el) {
      var btn = el.querySelector("button");
      if (btn) btn.addEventListener("click", function () { dismissToast(el); });
      if (!el.classList.contains("toast--error")) setTimeout(function () { dismissToast(el); }, 6000);
    });
  }

  // ---------- Theme ----------
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  function applyTheme(mode) {
    var dark = mode === "dark" || (mode === "system" && media && media.matches);
    root.setAttribute("data-theme", dark ? "dark" : "light");
    root.setAttribute("data-theme-mode", mode);
    Array.prototype.forEach.call(doc.querySelectorAll("[data-theme-set]"), function (btn) {
      btn.setAttribute("aria-checked", btn.getAttribute("data-theme-set") === mode ? "true" : "false");
    });
  }
  function currentMode() { return root.getAttribute("data-theme-mode") || "system"; }
  if (media && media.addEventListener) {
    media.addEventListener("change", function () { if (currentMode() === "system") applyTheme("system"); });
  }
  applyTheme(currentMode());

  // ---------- Menus (details.menu) ----------
  function closeMenus(except) {
    Array.prototype.forEach.call(doc.querySelectorAll("details.menu[open]"), function (d) {
      if (d !== except && !d.contains(except)) d.removeAttribute("open");
    });
  }
  doc.addEventListener("toggle", function (e) {
    var d = e.target;
    if (d.matches && d.matches("details.menu") && d.open) {
      closeMenus(d);
      var panel = d.querySelector(".menu-panel");
      if (panel) {
        panel.classList.remove("menu-panel--up");
        var rect = panel.getBoundingClientRect();
        if (rect.bottom > window.innerHeight - 8 && rect.height < d.getBoundingClientRect().top) panel.classList.add("menu-panel--up");
      }
    }
  }, true);
  doc.addEventListener("click", function (e) {
    if (!e.target.closest("details.menu")) closeMenus(null);
    var item = e.target.closest(".menu-panel a, .menu-panel button");
    if (item && !item.hasAttribute("data-keep-open")) {
      var menu = item.closest("details.menu");
      if (menu) setTimeout(function () { menu.removeAttribute("open"); }, 0);
    }
  });

  // ---------- Sidebar drawer ----------
  var app = doc.querySelector(".app");
  function setNav(open) {
    if (!app) return;
    app.classList.toggle("nav-open", open);
    Array.prototype.forEach.call(doc.querySelectorAll("[data-nav-toggle]"), function (b) {
      b.setAttribute("aria-expanded", open ? "true" : "false");
    });
    if (open) {
      var first = app.querySelector(".sidebar a, .sidebar button");
      if (first) first.focus({ preventScroll: true });
    }
  }

  // ---------- Dialogs ----------
  function openDialog(dialog) {
    if (!dialog || dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }
  function closeDialog(dialog) {
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }
  // Click on the backdrop closes the dialog.
  doc.addEventListener("click", function (e) {
    if (e.target.tagName === "DIALOG" && e.target.classList.contains("modal") && !e.target.hasAttribute("data-static")) {
      var r = e.target.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeDialog(e.target);
    }
  });

  var confirmDialog = doc.getElementById("confirm-dialog");
  function confirmAction(message, actionLabel, danger) {
    return new Promise(function (resolve) {
      if (!confirmDialog) { resolve(window.confirm(message)); return; }
      confirmDialog.querySelector("[data-confirm-message]").textContent = message;
      var ok = confirmDialog.querySelector("[data-confirm-ok]");
      ok.textContent = actionLabel || t("confirm", "Confirm");
      ok.className = "btn " + (danger === false ? "btn-primary" : "btn-danger");
      var done = false;
      function finish(result) {
        if (done) return;
        done = true;
        ok.removeEventListener("click", onOk);
        confirmDialog.removeEventListener("close", onClose);
        closeDialog(confirmDialog);
        resolve(result);
      }
      function onOk() { finish(true); }
      function onClose() { finish(false); }
      ok.addEventListener("click", onOk);
      confirmDialog.addEventListener("close", onClose);
      openDialog(confirmDialog);
      ok.focus();
    });
  }

  // ---------- Click delegation ----------
  doc.addEventListener("click", function (e) {
    var el;

    if ((el = e.target.closest("[data-nav-toggle]"))) {
      e.preventDefault();
      setNav(!app.classList.contains("nav-open"));
      return;
    }
    if (e.target.closest(".nav-scrim")) { setNav(false); return; }

    if ((el = e.target.closest("[data-dialog-open]"))) {
      e.preventDefault();
      openDialog(doc.getElementById(el.getAttribute("data-dialog-open")));
      return;
    }
    if ((el = e.target.closest("[data-dialog-close]"))) {
      e.preventDefault();
      closeDialog(el.closest("dialog"));
      return;
    }

    if ((el = e.target.closest("[data-theme-set]"))) {
      e.preventDefault();
      var mode = el.getAttribute("data-theme-set");
      try { localStorage.setItem("cwa-theme", mode); } catch (err) { /* storage blocked */ }
      applyTheme(mode);
      return;
    }

    if ((el = e.target.closest("[data-copy], [data-copy-target]"))) {
      e.preventDefault();
      var text = el.getAttribute("data-copy");
      if (text === null) {
        var target = doc.querySelector(el.getAttribute("data-copy-target"));
        text = target ? (target.value !== undefined && target.tagName !== "CODE" ? target.value : target.textContent) : "";
      }
      copyText(text.trim()).then(function () {
        toast(t("copied", "Copied to clipboard"), "success", 2500);
      }, function () {
        toast(t("copy_failed", "Could not copy, select the text and copy it manually"), "error");
      });
      return;
    }

    if ((el = e.target.closest("[data-password-toggle]"))) {
      e.preventDefault();
      var input = el.closest(".password-field").querySelector("input");
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      el.setAttribute("aria-pressed", show ? "true" : "false");
      el.setAttribute("aria-label", show ? t("hide_password", "Hide password") : t("show_password", "Show password"));
      var use = el.querySelector("use");
      if (use) use.setAttribute("href", use.getAttribute("href").replace(/#.*$/, show ? "#eye-off" : "#eye"));
      return;
    }

    if ((el = e.target.closest("[data-clamp-toggle]"))) {
      e.preventDefault();
      var block = doc.querySelector(el.getAttribute("data-clamp-toggle"));
      if (!block) return;
      var clamped = block.classList.toggle("is-clamped");
      el.textContent = clamped ? t("show_more", "Show more") : t("show_less", "Show less");
      el.setAttribute("aria-expanded", clamped ? "false" : "true");
      return;
    }

    if ((el = e.target.closest("[data-dismiss]"))) {
      e.preventDefault();
      var alertEl = el.closest(".alert");
      if (alertEl) {
        var url = el.getAttribute("data-dismiss-url");
        if (url) request(url, { method: "POST" }).catch(function () {});
        alertEl.parentNode.removeChild(alertEl);
      }
      return;
    }

    if ((el = e.target.closest('[data-action="library-refresh"]'))) {
      e.preventDefault();
      libraryRefresh(el);
      return;
    }

    if ((el = e.target.closest("[data-post]"))) {
      e.preventDefault();
      postAction(el);
    }
  });

  doc.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (app && app.classList.contains("nav-open")) setNav(false);
      closeMenus(null);
    }
    var tag = (e.target.tagName || "").toLowerCase();
    var typing = tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable;
    if (((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) {
      var search = doc.getElementById("query");
      if (search) { e.preventDefault(); search.focus(); search.select(); }
    }
  });

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      var area = doc.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      body.appendChild(area);
      area.select();
      try { doc.execCommand("copy") ? resolve() : reject(); } catch (err) { reject(err); }
      body.removeChild(area);
    });
  }

  // ---------- Confirmed forms ----------
  doc.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.hasAttribute("data-confirm") && !form.dataset.confirmed) {
      e.preventDefault();
      confirmAction(form.getAttribute("data-confirm"), form.getAttribute("data-confirm-action"),
                    form.getAttribute("data-confirm-danger") !== "false").then(function (ok) {
        if (!ok) return;
        form.dataset.confirmed = "1";
        if (e.submitter && e.submitter.name) {
          var hidden = doc.createElement("input");
          hidden.type = "hidden";
          hidden.name = e.submitter.name;
          hidden.value = e.submitter.value;
          form.appendChild(hidden);
        }
        form.submit();
      });
      return;
    }
    var submit = form.querySelector('[type="submit"]:not([formnovalidate])');
    if (submit && form.hasAttribute("data-loading")) submit.classList.add("is-loading");
  }, true);

  // ---------- POST actions ----------
  function postAction(el) {
    var run = function () {
      el.classList.add("is-loading");
      var bodyData = null;
      var headers = {};
      if (el.hasAttribute("data-json")) {
        bodyData = el.getAttribute("data-json");
        headers["Content-Type"] = "application/json";
      } else if (el.hasAttribute("data-body")) {
        bodyData = new URLSearchParams(JSON.parse(el.getAttribute("data-body")));
      }
      request(el.getAttribute("data-post"), { method: "POST", body: bodyData, headers: headers }).then(function (res) {
        el.classList.remove("is-loading");
        var type = res.headers.get("content-type") || "";
        var parse = type.indexOf("json") !== -1 ? res.json() : res.text().then(function (txt) { return { text: txt }; });
        return parse.then(function (data) {
          // Some endpoints answer with a one-item list of {type, message}.
          if (Array.isArray(data)) data = data[0] || {};
          if (!res.ok || (data && (data.success === false || data.type === "danger"))) {
            throw new Error((data && (data.message || data.msg || data.error || data.text)) || res.statusText);
          }
          return data;
        });
      }).then(function (data) {
        var msg = el.getAttribute("data-success") || (data && (data.message || data.msg || data.text)) || "";
        if (el.hasAttribute("data-redirect")) { window.location.href = el.getAttribute("data-redirect"); return; }
        if (data && data.location) { window.location.href = data.location; return; }
        if (el.hasAttribute("data-reload")) { window.location.reload(); return; }
        if (el.hasAttribute("data-remove-closest")) {
          var gone = el.closest(el.getAttribute("data-remove-closest"));
          if (gone) gone.parentNode.removeChild(gone);
        }
        if (el.hasAttribute("data-toggle-hidden")) {
          Array.prototype.forEach.call(doc.querySelectorAll(el.getAttribute("data-toggle-hidden")), function (n) { n.hidden = !n.hidden; });
        }
        if (msg) toast(msg, "success");
        el.dispatchEvent(new CustomEvent("cwa:posted", { bubbles: true, detail: data }));
      }).catch(function (err) {
        el.classList.remove("is-loading");
        toast(err && err.message ? err.message : t("error", "Something went wrong"), "error");
      });
    };
    if (el.hasAttribute("data-confirm")) {
      confirmAction(el.getAttribute("data-confirm"), el.getAttribute("data-confirm-action"),
                    el.getAttribute("data-confirm-danger") !== "false").then(function (ok) { if (ok) run(); });
    } else {
      run();
    }
  }

  // ---------- Auto-submit controls ----------
  doc.addEventListener("change", function (e) {
    var el = e.target;
    if (!el.hasAttribute || !el.hasAttribute("data-autosubmit")) return;
    if (el.tagName === "SELECT" && el.getAttribute("data-autosubmit") === "navigate") {
      if (el.value) window.location.href = el.value;
      return;
    }
    if (el.form) {
      if (typeof el.form.requestSubmit === "function") el.form.requestSubmit();
      else el.form.submit();
    }
  });

  // ---------- Library refresh ----------
  var refreshTimer = null;
  function libraryRefresh(btn) {
    var url = body.dataset.refreshUrl;
    if (!url) return;
    btn.classList.add("is-loading");
    request(url, { method: "POST" }).then(function (res) {
      if (!res.ok) throw new Error(res.statusText);
      return res.json();
    }).then(function (data) {
      toast(data.message, "info");
      var started = Date.now();
      clearInterval(refreshTimer);
      refreshTimer = setInterval(function () {
        request(body.dataset.refreshMessagesUrl).then(function (r) { return r.json(); }).then(function (d) {
          if (d.messages && d.messages.length) {
            clearInterval(refreshTimer);
            btn.classList.remove("is-loading");
            d.messages.forEach(function (m) { toast(m, /error|⛔/i.test(m) ? "error" : "success", 8000); });
          } else if (Date.now() - started > 10 * 60 * 1000) {
            clearInterval(refreshTimer);
            btn.classList.remove("is-loading");
          }
        }).catch(function () {});
      }, 1500);
    }).catch(function () {
      btn.classList.remove("is-loading");
      toast(t("error", "Something went wrong"), "error");
    });
  }

  // ---------- Uploads ----------
  var uploadDialog = doc.getElementById("upload-dialog");
  function uploadFiles(files, url, extra) {
    if (!files || !files.length || !url) return;
    var form = new FormData();
    var field = (extra && extra.field) || "btn-upload";
    Array.prototype.forEach.call(files, function (f) { form.append(field, f, f.name); });
    if (extra && extra.data) Object.keys(extra.data).forEach(function (k) { form.append(k, extra.data[k]); });
    form.append("csrf_token", csrfToken());

    var list = uploadDialog ? uploadDialog.querySelector(".upload-list") : null;
    var bar = null;
    var label = null;
    if (uploadDialog && list) {
      list.textContent = "";
      var item = doc.createElement("div");
      item.className = "upload-item";
      var head = doc.createElement("div");
      head.className = "upload-item-head";
      var name = doc.createElement("span");
      name.className = "upload-item-name";
      name.textContent = files.length === 1 ? files[0].name : t("files_count", "%d files").replace("%d", files.length);
      label = doc.createElement("span");
      label.className = "muted tabular";
      label.textContent = "0%";
      head.appendChild(name);
      head.appendChild(label);
      var progress = doc.createElement("div");
      progress.className = "progress progress--lg";
      bar = doc.createElement("span");
      bar.style.width = "0%";
      progress.appendChild(bar);
      item.appendChild(head);
      item.appendChild(progress);
      list.appendChild(item);
      openDialog(uploadDialog);
    }

    var xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("X-CSRFToken", csrfToken());
    xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    xhr.upload.addEventListener("progress", function (e) {
      if (!e.lengthComputable || !bar) return;
      var pct = Math.round((e.loaded / e.total) * 100);
      bar.style.width = pct + "%";
      label.textContent = pct === 100 ? t("processing", "Processing…") : pct + "%";
    });
    xhr.addEventListener("load", function () {
      var data = null;
      try { data = JSON.parse(xhr.responseText); } catch (err) { data = null; }
      if (xhr.status >= 200 && xhr.status < 300 && data && data.location) {
        window.location.href = data.location;
      } else {
        if (uploadDialog) closeDialog(uploadDialog);
        toast(t("upload_failed", "Upload failed"), "error");
      }
    });
    xhr.addEventListener("error", function () {
      if (uploadDialog) closeDialog(uploadDialog);
      toast(t("upload_failed", "Upload failed"), "error");
    });
    xhr.send(form);
  }

  doc.addEventListener("change", function (e) {
    var input = e.target;
    if (!input.matches || !input.matches("[data-upload-input]")) return;
    var extra = { field: input.name };
    if (input.dataset.bookId) extra.data = { book_id: input.dataset.bookId };
    uploadFiles(input.files, input.getAttribute("data-upload-url") || body.dataset.uploadUrl, extra);
    input.value = "";
  });

  // Drag & drop anywhere on the page uploads to the library.
  var dropOverlay = doc.querySelector(".dropzone-overlay");
  if (dropOverlay && body.dataset.uploadUrl) {
    var depth = 0;
    var hasFiles = function (e) { return e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], "Files") !== -1; };
    window.addEventListener("dragenter", function (e) { if (!hasFiles(e)) return; depth++; dropOverlay.classList.add("is-active"); });
    window.addEventListener("dragleave", function (e) { if (!hasFiles(e)) return; depth = Math.max(0, depth - 1); if (!depth) dropOverlay.classList.remove("is-active"); });
    window.addEventListener("dragover", function (e) { if (hasFiles(e)) e.preventDefault(); });
    window.addEventListener("drop", function (e) {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      dropOverlay.classList.remove("is-active");
      uploadFiles(e.dataTransfer.files, body.dataset.uploadUrl, { field: "btn-upload" });
    });
  }

  // ---------- Multi-select: <select multiple data-multiselect> ----------
  // Keeps the native <select> as the form field and mirrors it with a searchable checkbox list.
  function enhanceMultiselect(select) {
    if (select.dataset.enhanced) return;
    select.dataset.enhanced = "1";
    var wrap = doc.createElement("details");
    wrap.className = "menu multiselect";
    var summary = doc.createElement("summary");
    summary.className = "select multiselect-summary";
    var label = select.id ? doc.querySelector('label[for="' + select.id + '"]') : null;
    if (label) summary.setAttribute("aria-label", label.textContent.trim());
    var panel = doc.createElement("div");
    panel.className = "menu-panel menu-panel--left multiselect-panel";
    var filter = doc.createElement("input");
    filter.type = "search";
    filter.className = "input";
    filter.placeholder = select.getAttribute("data-filter-placeholder") || t("filter", "Filter");
    filter.setAttribute("aria-label", filter.placeholder);
    var optionsBox = doc.createElement("div");
    optionsBox.className = "multiselect-options";
    if (select.options.length > 8) panel.appendChild(filter);
    panel.appendChild(optionsBox);
    Array.prototype.forEach.call(select.options, function (opt) {
      var row = doc.createElement("label");
      row.className = "menu-item";
      var box = doc.createElement("input");
      box.type = "checkbox";
      box.checked = opt.selected;
      box.addEventListener("change", function () { opt.selected = box.checked; render(); select.dispatchEvent(new Event("change", { bubbles: true })); });
      var text = doc.createElement("span");
      text.className = "grow";
      text.textContent = opt.textContent;
      row.appendChild(box);
      row.appendChild(text);
      row.setAttribute("data-keep-open", "");
      optionsBox.appendChild(row);
    });
    filter.addEventListener("input", function () {
      var q = filter.value.toLowerCase();
      Array.prototype.forEach.call(optionsBox.children, function (row) {
        row.hidden = q && row.textContent.toLowerCase().indexOf(q) === -1;
      });
    });
    function render() {
      var chosen = Array.prototype.filter.call(select.options, function (o) { return o.selected; }).map(function (o) { return o.textContent; });
      summary.textContent = chosen.length ? (chosen.length > 2 ? chosen.slice(0, 2).join(", ") + " +" + (chosen.length - 2) : chosen.join(", "))
        : (select.getAttribute("data-placeholder") || t("any", "Any"));
      summary.classList.toggle("is-placeholder", !chosen.length);
    }
    render();
    if (select.form) {
      select.form.addEventListener("reset", function () {
        setTimeout(function () {
          Array.prototype.forEach.call(optionsBox.querySelectorAll("input"), function (box, i) { box.checked = select.options[i].selected; });
          render();
        }, 0);
      });
    }
    wrap.appendChild(summary);
    wrap.appendChild(panel);
    select.hidden = true;
    select.parentNode.insertBefore(wrap, select.nextSibling);
  }
  Array.prototype.forEach.call(doc.querySelectorAll("select[multiple][data-multiselect]"), enhanceMultiselect);

  // ---------- Suggestions: <input data-suggest="url" [data-separator=","]> ----------
  // Completes the last token of the field from a JSON list of {name}.
  var suggestCounter = 0;
  function enhanceSuggest(input) {
    if (input.dataset.suggestReady) return;
    input.dataset.suggestReady = "1";
    var sep = input.getAttribute("data-separator");
    var listId = "suggest-" + (++suggestCounter);
    var box = doc.createElement("ul");
    box.className = "suggest-list";
    box.id = listId;
    box.setAttribute("role", "listbox");
    box.hidden = true;
    var wrap = doc.createElement("div");
    wrap.className = "suggest";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.appendChild(box);
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", listId);
    input.setAttribute("aria-expanded", "false");
    var timer = null;
    var active = -1;
    var lastQuery = null;

    function tokens() {
      if (!sep) return { head: "", current: input.value };
      var parts = input.value.split(sep);
      var current = parts.pop();
      return { head: parts.length ? parts.join(sep) + sep + " " : "", current: current };
    }
    function close() {
      box.hidden = true;
      box.textContent = "";
      active = -1;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }
    function choose(value) {
      // No trailing separator: an empty last entry would become an empty author or tag.
      input.value = sep ? tokens().head + value : value;
      close();
      input.focus();
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    function highlight(index) {
      var items = box.querySelectorAll("[role=option]");
      if (!items.length) return;
      active = (index + items.length) % items.length;
      Array.prototype.forEach.call(items, function (el, i) { el.setAttribute("aria-selected", i === active ? "true" : "false"); });
      input.setAttribute("aria-activedescendant", items[active].id);
      items[active].scrollIntoView({ block: "nearest" });
    }
    function show(names) {
      box.textContent = "";
      names.slice(0, 12).forEach(function (name, i) {
        var li = doc.createElement("li");
        li.id = listId + "-" + i;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.textContent = name;
        li.addEventListener("mousedown", function (e) { e.preventDefault(); choose(name); });
        box.appendChild(li);
      });
      box.hidden = !names.length;
      input.setAttribute("aria-expanded", names.length ? "true" : "false");
      active = -1;
    }
    input.addEventListener("input", function () {
      var q = tokens().current.trim();
      clearTimeout(timer);
      if (q.length < 1) { close(); return; }
      timer = setTimeout(function () {
        if (q === lastQuery) return;
        lastQuery = q;
        var url = input.getAttribute("data-suggest");
        request(url + (url.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q)).then(function (r) { return r.json(); })
          .then(function (data) {
            if (tokens().current.trim() !== q) return;
            var existing = sep ? input.value.split(sep).map(function (x) { return x.trim().toLowerCase(); }) : [];
            show((data || []).map(function (d) { return typeof d === "string" ? d : d.name; })
              .filter(function (n) { return n && (sep ? existing.indexOf(n.toLowerCase()) === -1 || n.toLowerCase() === q.toLowerCase() : true); }));
          }).catch(close);
      }, 150);
    });
    input.addEventListener("keydown", function (e) {
      if (box.hidden) return;
      if (e.key === "ArrowDown") { e.preventDefault(); highlight(active + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); highlight(active - 1); }
      else if (e.key === "Enter" && active >= 0) { e.preventDefault(); choose(box.querySelectorAll("[role=option]")[active].textContent); }
      else if (e.key === "Escape") { e.stopPropagation(); close(); }
    });
    input.addEventListener("blur", function () { setTimeout(close, 100); });
  }
  Array.prototype.forEach.call(doc.querySelectorAll("input[data-suggest]"), enhanceSuggest);

  // ---------- Conditional fields: data-show-if="checkboxId" or "selectId:value1,value2" ----------
  function updateShowIf() {
    Array.prototype.forEach.call(doc.querySelectorAll("[data-show-if]"), function (el) {
      var spec = el.getAttribute("data-show-if");
      var negate = spec.charAt(0) === "!";
      if (negate) spec = spec.slice(1);
      var parts = spec.split(":");
      var control = doc.getElementById(parts[0]);
      if (!control) return;
      var show;
      if (parts.length > 1) show = parts[1].split(",").indexOf(control.value) !== -1;
      else show = control.type === "checkbox" ? control.checked : !!control.value;
      if (negate) show = !show;
      el.hidden = !show;
    });
  }
  doc.addEventListener("change", function (e) {
    if (e.target.id && doc.querySelector('[data-show-if*="' + e.target.id + '"]')) updateShowIf();
  });
  updateShowIf();

  // ---------- AJAX settings forms: form[data-ajax-form] ----------
  // Handles the {result: [{type, message}], reboot} answers of the admin configuration endpoints.
  doc.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.hasAttribute || !form.hasAttribute("data-ajax-form") || e.defaultPrevented) return;
    e.preventDefault();
    var submit = form.querySelector('[type="submit"]');
    if (submit) submit.classList.add("is-loading");
    request(form.getAttribute("action") || window.location.href, { method: "POST", body: new URLSearchParams(new FormData(form)) })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (submit) submit.classList.remove("is-loading");
        (data.result || []).forEach(function (item) {
          toast(item.message, item.type === "danger" ? "error" : (item.type === "success" ? "success" : "info"));
        });
        if (data.config_upload !== undefined) {
          var formats = doc.getElementById("config_upload_formats");
          if (formats) formats.value = data.config_upload;
        }
        if (data.reboot && form.getAttribute("data-alive-url")) {
          toast(t("restarting", "Restarting…"), "info", 0);
          var alive = setInterval(function () {
            fetch(form.getAttribute("data-alive-url"), { credentials: "same-origin", cache: "no-store" }).then(function (r) {
              if (r.status < 400) { clearInterval(alive); window.location.reload(); }
            }).catch(function () {});
          }, 1500);
        }
      })
      .catch(function () {
        if (submit) submit.classList.remove("is-loading");
        toast(t("error", "Something went wrong"), "error");
      });
  });

  // ---------- Test buttons: data-test-url + data-test-source="#input" ----------
  doc.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-test-url]");
    if (!btn) return;
    e.preventDefault();
    var source = doc.querySelector(btn.getAttribute("data-test-source"));
    var value = source ? source.value.trim() : "";
    if (!value) { toast(t("enter_url", "Enter a URL first"), "error"); return; }
    btn.classList.add("is-loading");
    request(btn.getAttribute("data-test-url"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: value }) })
      .then(function (r) { return r.json(); })
      .then(function (d) { btn.classList.remove("is-loading"); toast(d.message || "", d.success ? "success" : "error", 8000); })
      .catch(function () { btn.classList.remove("is-loading"); toast(t("error", "Something went wrong"), "error"); });
  });

  window.CWA = {
    t: t,
    toast: toast,
    request: request,
    csrfToken: csrfToken,
    confirm: confirmAction,
    openDialog: openDialog,
    closeDialog: closeDialog,
    icon: icon,
    upload: uploadFiles,
    enhanceMultiselect: enhanceMultiselect,
    enhanceSuggest: enhanceSuggest
  };
})();
