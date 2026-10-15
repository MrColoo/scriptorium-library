// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Statistics dashboard: tabs, period filter and ECharts charts styled from the CSS tokens.
// All server data is rendered as text or passed to ECharts as values.
(function () {
  "use strict";
  var CWA = window.CWA;
  var dataEl = document.getElementById("stats-data");
  if (!CWA || !dataEl || !window.echarts) return;
  var D = JSON.parse(dataEl.textContent);
  var S = D.strings;
  var charts = [];

  // ---------- Tabs and filters ----------
  var tabInput = document.querySelector("[data-tab-input]");
  var exportLink = document.querySelector("[data-export]");
  function showTab(key, push) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-tab]"), function (t) {
      var on = t.getAttribute("data-tab") === key;
      t.setAttribute("aria-selected", on ? "true" : "false");
      document.getElementById("panel-" + t.getAttribute("data-tab")).hidden = !on;
    });
    if (tabInput) tabInput.value = key;
    var url = new URL(window.location.href);
    url.searchParams.set("tab", key);
    if (push) window.history.replaceState({}, "", url);
    if (exportLink) exportLink.href = exportLink.href.replace(/\/cwa-stats-export-csv\/[^/?]+/, "/cwa-stats-export-csv/" + key).split("?")[0] + "?" + url.searchParams.toString();
    renderVisible();
  }
  Array.prototype.forEach.call(document.querySelectorAll("[data-tab]"), function (t) {
    t.addEventListener("click", function () { showTab(t.getAttribute("data-tab"), true); });
  });
  var period = document.querySelector("[data-period]");
  var custom = document.querySelector("[data-custom-range]");
  if (period) {
    period.addEventListener("change", function () {
      var isCustom = period.value === "custom";
      custom.hidden = !isCustom;
      Array.prototype.forEach.call(custom.querySelectorAll("input"), function (i) { i.disabled = !isCustom; });
      period.disabled = isCustom;
      if (!isCustom) period.form.submit();
      else period.disabled = false;
    });
    period.form.addEventListener("submit", function () {
      if (period.value === "custom") period.disabled = true;
    });
  }

  // ---------- Theme ----------
  function token(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function palette() {
    return {
      text: token("--text"), muted: token("--text-muted"), faint: token("--text-faint"), border: token("--border"),
      surface: token("--surface"), accent: token("--accent"),
      series: [token("--accent"), "#C2410C", "#2C8C5A", "#B07D10", "#7C5BC4", "#C2185B", "#0E7C86", "#6B7280"]
    };
  }
  function base(p) {
    return {
      color: p.series,
      textStyle: { fontFamily: getComputedStyle(document.body).fontFamily, color: p.muted },
      tooltip: { backgroundColor: p.surface, borderColor: p.border, textStyle: { color: p.text }, confine: true },
      grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
      animationDuration: 400
    };
  }
  function axis(p, type, data) {
    return {
      type: type, data: data,
      axisLine: { lineStyle: { color: p.border } }, axisTick: { show: false },
      axisLabel: { color: p.muted, hideOverlap: true }, splitLine: { lineStyle: { color: p.border, type: "dashed" } }
    };
  }
  function pie(p, rows) {
    return Object.assign(base(p), {
      tooltip: Object.assign(base(p).tooltip, { trigger: "item", formatter: "{b}: {c} ({d}%)" }),
      legend: { bottom: 0, type: "scroll", textStyle: { color: p.muted } },
      series: [{
        type: "pie", radius: ["48%", "72%"], center: ["50%", "44%"], itemStyle: { borderColor: p.surface, borderWidth: 2, borderRadius: 4 },
        label: { show: false }, data: rows.map(function (r) { return { name: String(r[0]), value: r[1] }; })
      }]
    });
  }
  function bars(p, labels, values, horizontal) {
    var o = base(p);
    o.tooltip.trigger = "axis";
    o.xAxis = horizontal ? axis(p, "value") : axis(p, "category", labels);
    o.yAxis = horizontal ? axis(p, "category", labels) : axis(p, "value");
    if (horizontal) o.yAxis.inverse = true;
    o.series = [{ type: "bar", data: values, barMaxWidth: 28, itemStyle: { borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] } }];
    return o;
  }

  var builders = {
    timeline: function (p) {
      var dates = [], events = [], map = {};
      D.timeline.forEach(function (r) {
        if (dates.indexOf(r[0]) === -1) dates.push(r[0]);
        if (events.indexOf(r[1]) === -1) events.push(r[1]);
        map[r[0] + "|" + r[1]] = r[2];
      });
      dates.sort();
      var o = base(p);
      o.tooltip.trigger = "axis";
      o.legend = { top: 0, type: "scroll", textStyle: { color: p.muted } };
      o.grid.top = 36;
      o.xAxis = axis(p, "category", dates);
      o.yAxis = axis(p, "value");
      o.series = events.map(function (e) {
        return { name: e, type: "line", smooth: true, showSymbol: dates.length < 20, stack: "events", areaStyle: { opacity: .12 },
                 data: dates.map(function (d) { return map[d + "|" + e] || 0; }) };
      });
      return o;
    },
    heatmap: function (p) {
      var max = 1;
      var cells = D.heatmap.map(function (r) { max = Math.max(max, r[2]); return [r[1], r[0], r[2]]; });
      var o = base(p);
      o.tooltip = Object.assign(o.tooltip, { formatter: function (x) { return S.days[x.data[1]] + " " + String(x.data[0]).padStart(2, "0") + ":00 · " + x.data[2]; } });
      o.grid.bottom = 48;
      o.xAxis = axis(p, "category", Array.from({ length: 24 }, function (_, h) { return String(h).padStart(2, "0"); }));
      o.yAxis = axis(p, "category", S.days);
      o.xAxis.splitArea = { show: false };
      o.visualMap = { min: 0, max: max, calculable: false, orient: "horizontal", left: "center", bottom: 0, itemHeight: 120,
                      inRange: { color: [token("--bg-sunken"), p.accent] }, textStyle: { color: p.muted } };
      o.series = [{ type: "heatmap", data: cells, itemStyle: { borderColor: p.surface, borderWidth: 2, borderRadius: 3 } }];
      return o;
    },
    events: function (p) { return pie(p, D.events); },
    formats: function (p) { return pie(p, D.formats); },
    discovery: function (p) { return pie(p, D.discovery); },
    devices: function (p) { return pie(p, D.devices); },
    apiUsage: function (p) { return pie(p, D.apiUsage); },
    libraryFormats: function (p) { return pie(p, D.libraryFormats); },
    formatPreferences: function (p) {
      var users = [], formats = [], map = {};
      D.formatPreferences.forEach(function (r) {
        if (users.indexOf(r[0]) === -1) users.push(r[0]);
        if (formats.indexOf(r[1]) === -1) formats.push(r[1]);
        map[r[0] + "|" + r[1]] = r[2];
      });
      var o = base(p);
      o.tooltip.trigger = "axis";
      o.legend = { top: 0, textStyle: { color: p.muted } };
      o.grid.top = 36;
      o.xAxis = axis(p, "category", users);
      o.yAxis = axis(p, "value");
      o.series = formats.map(function (f) { return { name: f, type: "bar", stack: "f", barMaxWidth: 28, data: users.map(function (u) { return map[u + "|" + f] || 0; }) }; });
      return o;
    },
    velocity: function (p) {
      var o = bars(p, D.velocity.map(function (r) { return r[0]; }), D.velocity.map(function (r) { return r[1]; }));
      o.series[0].type = "line";
      o.series[0].smooth = true;
      o.series[0].areaStyle = { opacity: .15 };
      return o;
    },
    sessionDuration: function (p) {
      var dist = (D.sessionDuration && D.sessionDuration.distribution) || [];
      return bars(p, dist.map(function (r) { return r[0] + "+ " + S.minutes; }), dist.map(function (r) { return r[1]; }));
    },
    apiTiming: function (p) {
      var hours = Array.from({ length: 24 }, function () { return 0; });
      D.apiTiming.forEach(function (r) { hours[r[1]] = (hours[r[1]] || 0) + r[2]; });
      return bars(p, hours.map(function (_, h) { return String(h).padStart(2, "0"); }), hours);
    },
    growth: function (p) {
      var total = 0;
      var o = bars(p, D.growth.map(function (r) { return r[0]; }), D.growth.map(function (r) { total += r[1]; return total; }));
      o.series[0].type = "line";
      o.series[0].areaStyle = { opacity: .15 };
      o.series[0].showSymbol = false;
      return o;
    },
    ratings: function (p) { return bars(p, D.ratings.map(function (r) { return r[0] + " ★"; }), D.ratings.map(function (r) { return r[1]; })); },
    publicationYears: function (p) { return bars(p, D.publicationYears.map(function (r) { return r[0]; }), D.publicationYears.map(function (r) { return r[1]; })); },
    series: function (p) { return bars(p, D.series.map(function (r) { return r[0]; }), D.series.map(function (r) { return r[1]; }), true); },
    importFlows: function (p) {
      var rows = D.importFlows.filter(function (r) { return r[0] && r[1] && r[0] !== r[1]; });
      var nodes = [];
      rows.forEach(function (r) {
        [r[0] + " ", " " + r[1]].forEach(function (n) { if (nodes.indexOf(n) === -1) nodes.push(n); });
      });
      var o = base(p);
      o.tooltip.trigger = "item";
      o.series = [{ type: "sankey", left: 8, right: 60, data: nodes.map(function (n) { return { name: n }; }),
                    links: rows.map(function (r) { return { source: r[0] + " ", target: " " + r[1], value: r[2] }; }),
                    label: { color: p.text }, lineStyle: { color: "gradient", opacity: .35 } }];
      return o;
    }
  };
  var sizes = { timeline: D.timeline, heatmap: D.heatmap, events: D.events, formats: D.formats, discovery: D.discovery, devices: D.devices,
                apiUsage: D.apiUsage, libraryFormats: D.libraryFormats, formatPreferences: D.formatPreferences, velocity: D.velocity,
                sessionDuration: (D.sessionDuration && D.sessionDuration.distribution) || [], apiTiming: D.apiTiming, growth: D.growth,
                ratings: D.ratings, publicationYears: D.publicationYears, series: D.series, importFlows: D.importFlows };

  function renderChart(box) {
    var name = box.getAttribute("data-chart");
    if (box.dataset.rendered || !builders[name]) return;
    box.dataset.rendered = "1";
    if (!sizes[name] || !sizes[name].length) {
      box.classList.add("chart-box--empty");
      box.textContent = S.empty;
      return;
    }
    var chart = window.echarts.init(box, null, { renderer: "svg" });
    chart.setOption(builders[name](palette()));
    charts.push({ chart: chart, name: name });
  }
  function renderVisible() {
    Array.prototype.forEach.call(document.querySelectorAll("[role=tabpanel]:not([hidden]) [data-chart]"), renderChart);
    charts.forEach(function (c) { c.chart.resize(); });
  }
  window.addEventListener("resize", function () { charts.forEach(function (c) { c.chart.resize(); }); });
  new MutationObserver(function () {
    charts.forEach(function (c) { c.chart.setOption(builders[c.name](palette()), true); });
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // ---------- Ranked lists ----------
  function li(main, side, href) {
    var item = document.createElement("li");
    var a = document.createElement(href ? "a" : "span");
    a.className = "grow truncate";
    a.textContent = main;
    if (href) a.href = href;
    var s = document.createElement("span");
    s.className = "small muted tabular nowrap";
    s.textContent = side;
    item.appendChild(a);
    item.appendChild(s);
    return item;
  }
  var lists = {
    topUsers: function (r) { return D.singleUser ? li(r[0], r[1]) : li(r[1], r[2]); },
    topBooks: function (r) { return li(r[0], r[2], D.bookUrl.replace("999999999", r[1])); },
    recentSearches: function (r) { return li(r[0], (r[2] ? r[2] + " · " : "") + String(r[1] || "").slice(0, 10)); },
    shelfActivity: function (r) { return li(r[0], "+" + r[1] + " / −" + r[2] + " · " + r[4] + " " + S.views); },
    failedLogins: function (r) { return li((r[1] || "?") + " · " + r[0], r[3] + " · " + String(r[2] || "").slice(0, 16)); },
    topEnforced: function (r) { return li(r[1], r[2], D.bookUrl.replace("999999999", r[0])); },
    mostFixed: function (r) { return li(r[0], r[1]); }
  };
  Array.prototype.forEach.call(document.querySelectorAll("[data-list]"), function (ul) {
    var name = ul.getAttribute("data-list");
    var rows = D[name] || [];
    if (!rows.length) {
      var empty = document.createElement("li");
      empty.className = "muted small";
      empty.textContent = S.empty;
      ul.appendChild(empty);
      return;
    }
    rows.slice(0, 15).forEach(function (r) { ul.appendChild(lists[name](r)); });
  });

  showTab(document.querySelector("[data-tab][aria-selected=true]").getAttribute("data-tab"), false);
})();
