/* History views for the sts-for-ai showcase: the timeline of everything tried,
   the per-stretch lists, and the scorecard of the AI-run research.
   Data: window.HISTORY (history.js, hand-written). */
(function () {
  "use strict";
  var H = window.HISTORY || {};
  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function txt(parent, x, y, s, attrs) { var t = el("text", Object.assign({ x: x, y: y }, attrs || {}), parent); t.textContent = s; return t; }
  function h(tag, cls, text, parent) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.textContent = text; if (parent) parent.appendChild(e); return e; }
  var tip = document.getElementById("tip"), owner = null;
  function show(build, x, y, o) {
    owner = o; tip.textContent = ""; build(tip); tip.classList.add("on");
    var r = tip.getBoundingClientRect(), L = x + 14, T = y + 14;
    if (L + r.width > innerWidth - 8) L = Math.max(8, x - r.width - 14);
    if (T + r.height > innerHeight - 8) T = Math.max(8, y - r.height - 14);
    tip.style.left = L + "px"; tip.style.top = T + "px";
  }
  function hide(o) { if (!o || o === owner) { tip.classList.remove("on"); owner = null; } }
  function hover(node, build) {
    node.setAttribute("tabindex", "0");
    node.addEventListener("pointermove", function (e) { show(build, e.clientX, e.clientY, node); });
    node.addEventListener("pointerleave", function () { hide(node); });
    node.addEventListener("focus", function () { var r = node.getBoundingClientRect(); show(build, r.left + r.width / 2, r.bottom, node); });
    node.addEventListener("blur", function () { hide(node); });
  }

  var KINDS = [
    ["engine", "Engine"], ["content", "Act 1 content"], ["search", "Search"], ["learning", "Training the net"],
    ["run-layer", "Run choices"], ["goal1", "Unseen content"], ["measuring", "Tests and rulers"], ["tooling", "Tools and process"]
  ];
  var KIND_NAME = {}; KINDS.forEach(function (k) { KIND_NAME[k[0]] = k[1]; });
  var OUT = {
    worked: { name: "Worked", color: "var(--ok)" },
    failed: { name: "Didn't work", color: "var(--bad)" },
    mixed: { name: "Partly", color: "var(--meh)" },
    built: { name: "Built", color: "var(--net)" },
    dropped: { name: "Dropped", color: "var(--muted)" }
  };
  // a mark per outcome: shape and colour both say it
  function mark(parent, kind, x, y, r) {
    var c = OUT[kind] ? OUT[kind].color : "var(--muted)";
    if (kind === "failed") {
      var g = el("g", null, parent);
      el("path", { d: "M" + (x - r) + " " + (y - r) + " L" + (x + r) + " " + (y + r) + " M" + (x + r) + " " + (y - r) + " L" + (x - r) + " " + (y + r), style: "stroke:" + c + ";stroke-width:2.4;stroke-linecap:round" }, g);
      return g;
    }
    if (kind === "built") return el("rect", { x: x - r, y: y - r, width: 2 * r, height: 2 * r, rx: 1.5, style: "fill:" + c }, parent);
    if (kind === "mixed") {
      var m = el("g", null, parent);
      el("circle", { cx: x, cy: y, r: r, style: "fill:var(--surface);stroke:" + c + ";stroke-width:1.8" }, m);
      el("path", { d: "M" + x + " " + (y - r) + " A" + r + " " + r + " 0 0 0 " + x + " " + (y + r) + " Z", style: "fill:" + c }, m);
      return m;
    }
    if (kind === "dropped") return el("circle", { cx: x, cy: y, r: r - 0.5, style: "fill:none;stroke:" + c + ";stroke-width:1.6" }, parent);
    return el("circle", { cx: x, cy: y, r: r, style: "fill:" + c }, parent);
  }
  function badge(parent, kind) {
    var s = el("svg", { viewBox: "-7 -7 14 14", width: 14, height: 14, "aria-hidden": "true", class: "obadge" });
    mark(s, kind, 0, 0, 5);
    parent.appendChild(s);
    return s;
  }

  // ---------- all items ----------
  function dayIndex(md) { var p = md.split("-"); var m = +p[0], d = +p[1]; return m === 10 ? d - 23 : 8 + d; } // 10-23 -> 0, 10-31 -> 8, 11-01 -> 9
  function items() {
    var out = [];
    (H.tried || []).forEach(function (t, i) {
      var d = (t.date || "").slice(5), e = (t.end || t.date || "").slice(5);
      if (!d) return;
      out.push({ id: "t" + i, date: d, end: e || d, title: t.title, kind: t.kind, outcome: t.outcome, text: t.sentence, who: t.who, lane: false });
    });
    (H.lanes || []).forEach(function (l) {
      out.push({ id: "l-" + l.name, date: l.open, end: l.close, title: "Lane " + l.name, kind: l.kind, outcome: l.outcome, text: l.text, who: "ai", lane: true, pred: l.pred, cpu: l.cpu });
    });
    (H.openLanes || []).forEach(function (l) {
      out.push({ id: "l-" + l.name, date: l.open, end: "11-14", title: "Lane " + l.name + " (open)", kind: l.kind, outcome: "open", text: l.text, who: "ai", lane: true });
    });
    out.sort(function (a, b) { return dayIndex(a.date) - dayIndex(b.date) || dayIndex(a.end) - dayIndex(b.end); });
    return out;
  }
  var ALL = items();
  (function () { var e = document.getElementById("hero-tried"); if (e) e.textContent = String(ALL.length); })();
  var shown = { worked: true, failed: true, mixed: true, built: true, dropped: true, open: true };

  // ---------- the timeline ----------
  function timeline() {
    var host = document.getElementById("tried-timeline");
    if (!host) return;
    host.textContent = "";
    var days = 23, W = 1100, L = 128, R = 12, top = 58, rowH = 11, gapK = 10;
    var dw = (W - L - R) / days;
    var x = function (i) { return L + dw * i; };
    // pack items per kind into rows: a span takes its days whole; one-day
    // items sit side by side inside their day, up to `per` to a row
    var per = Math.max(1, Math.floor((dw - 8) / 9));
    var lanes = KINDS.map(function (k) {
      var rows = [];
      ALL.filter(function (t) { return t.kind === k[0] && shown[t.outcome]; }).forEach(function (t) {
        var a = dayIndex(t.date), b = dayIndex(t.end), r = 0;
        for (;; r++) {
          var row = rows[r] = rows[r] || { spans: [], count: {}, items: [] };
          var clash = row.spans.some(function (s) { return !(b < s[0] || a > s[1]); });
          if (a === b) { if (!clash && (row.count[a] || 0) < per) break; }
          else { var busy = false; for (var d = a; d <= b; d++) if (row.count[d]) busy = true; if (!clash && !busy) break; }
        }
        var row2 = rows[r];
        if (a === b) { row2.items.push([a, b, t, row2.count[a] || 0]); row2.count[a] = (row2.count[a] || 0) + 1; }
        else { row2.spans.push([a, b]); row2.items.push([a, b, t, -1]); }
      });
      return { k: k, rows: rows.map(function (rw) { return rw.items; }) };
    });
    var Htot = top + lanes.reduce(function (s, ln) { return s + Math.max(1, ln.rows.length) * rowH + gapK + 8; }, 0) + 24;
    var s = el("svg", { viewBox: "0 0 " + W + " " + Htot, role: "img", "aria-label": "Everything tried, by day and kind" }, host);
    s.style.minWidth = "760px";
    // who ran the project
    var eras = [[0, 6.86, "Owner at the desk with Claude", "var(--heur)"], [6.86, 11, "Claude as manager", "var(--gold)"], [11, 21, "AI roles: steward, navigator, lane workers", "var(--prod)"], [21, 23, "Real game", "var(--net)"]];
    eras.forEach(function (e) {
      el("rect", { x: x(e[0]), y: 6, width: x(e[1]) - x(e[0]) - 2, height: 16, rx: 3, style: "fill:" + e[3] + ";opacity:.22" }, s);
      el("rect", { x: x(e[0]), y: 6, width: 3, height: 16, style: "fill:" + e[3] }, s);
      txt(s, x(e[0]) + 8, 18, e[2], { style: "font-size:11.5px;fill:var(--ink-2)" });
    });
    txt(s, L - 10, 18, "who ran it", { class: "axis", "text-anchor": "end" });
    // day ticks
    for (var i = 0; i <= days; i++) {
      el("line", { x1: x(i), x2: x(i), y1: top - 12, y2: Htot - 20, style: "stroke:var(--line);stroke-width:" + ((i === 9 || i === 0) ? 1 : 0.6) }, s);
      if (i < days && (i % 2 === 0)) {
        var md = i < 9 ? "Oct " + (23 + i) : "Nov " + (i - 8);
        txt(s, x(i) + dw / 2, top - 18, md, { class: "axis", "text-anchor": "middle", style: "font-size:10.5px" });
      }
    }
    var y0 = top;
    lanes.forEach(function (ln) {
      var hgt = Math.max(1, ln.rows.length) * rowH;
      el("rect", { x: L, y: y0 - 4, width: W - L - R, height: hgt + 8, rx: 4, style: "fill:var(--bg-2);opacity:.45" }, s);
      txt(s, L - 10, y0 + Math.min(hgt, 14) / 2 + 6, ln.k[1], { "text-anchor": "end", style: "font-size:12px;fill:var(--ink-2);font-weight:500" });
      var n = ln.rows.reduce(function (a, r) { return a + r.length; }, 0);
      txt(s, L - 10, y0 + Math.min(hgt, 14) / 2 + 19, n + " tried", { class: "axis", "text-anchor": "end", style: "font-size:10px" });
      ln.rows.forEach(function (row, ri) {
        row.forEach(function (it) {
          var t = it[2], cy = y0 + ri * rowH + rowH / 2;
          var xa = x(it[0]) + dw / 2, xb = x(it[1]) + dw / 2;
          if (it[3] >= 0) { xa = xb = x(it[0]) + 6 + it[3] * 9; }
          if (xb > xa) el("line", { x1: xa, x2: xb, y1: cy, y2: cy, style: "stroke:" + (OUT[t.outcome] ? OUT[t.outcome].color : "var(--line-2)") + ";stroke-width:2;opacity:.55;stroke-linecap:round" }, s);
          if (t.outcome === "open") el("circle", { cx: xa, cy: cy, r: 3.6, style: "fill:none;stroke:var(--ink-2);stroke-width:1.4;stroke-dasharray:2 1.5" }, s);
          else mark(s, t.outcome, xb, cy, 3.8);
          var hit = el("rect", { x: Math.min(xa, xb) - 6, y: cy - rowH / 2, width: Math.abs(xb - xa) + 12, height: rowH, style: "fill:transparent;cursor:pointer" }, s);
          hover(hit, function (box) {
            h("span", "tv", t.title, box);
            h("div", "tk", (OUT[t.outcome] ? OUT[t.outcome].name : "Still open") + " · " + KIND_NAME[t.kind] + " · " + fmtDates(t), box);
            h("div", null, t.text, box);
          });
          hit.addEventListener("click", function () { openItem(t.id); });
        });
      });
      y0 += hgt + gapK + 8;
    });
  }
  function fmtDate(md) { var p = md.split("-"); return (+p[1]) + (p[0] === "10" ? " Oct" : " Nov"); }
  function fmtDates(t) { return t.date === t.end ? fmtDate(t.date) : fmtDate(t.date) + " to " + fmtDate(t.end); }

  function filters() {
    var host = document.getElementById("tried-filters");
    if (!host) return;
    host.textContent = "";
    var counts = {};
    ALL.forEach(function (t) { counts[t.outcome] = (counts[t.outcome] || 0) + 1; });
    ["worked", "failed", "mixed", "built", "dropped", "open"].forEach(function (k) {
      if (!counts[k]) return;
      var b = h("button", "chip", null, host);
      b.type = "button";
      b.setAttribute("aria-pressed", "true");
      if (k === "open") { var sv = el("svg", { viewBox: "-7 -7 14 14", width: 14, height: 14 }); el("circle", { cx: 0, cy: 0, r: 4.5, style: "fill:none;stroke:var(--ink-2);stroke-width:1.4;stroke-dasharray:2 1.5" }, sv); b.appendChild(sv); }
      else badge(b, k);
      b.appendChild(document.createTextNode((k === "open" ? "Still open" : OUT[k].name) + " · " + counts[k]));
      b.addEventListener("click", function () { shown[k] = !shown[k]; b.setAttribute("aria-pressed", String(shown[k])); timeline(); });
    });
    var total = h("span", "panel-note", ALL.length + " things tried in all", host);
    total.style.marginLeft = "6px";
  }

  // ---------- per-stretch summaries and the full list (its own view) ----------
  var STRETCHES = [
    ["10-23", "10-24", "The engine and the first question"],
    ["10-25", "10-28", "Self-play, with the owner at the desk"],
    ["10-29", "10-31", "Claude runs the lab day to day"],
    ["11-01", "11-02", "From single fights to an Act"],
    ["11-03", "11-05", "The AI roles take over"],
    ["11-06", "11-09", "Real Act 1 goes in"],
    ["11-10", "11-12", "New nets for new content; relics and potions"],
    ["11-13", "11-14", "The product changes; the real game"]
  ];
  var listShown = { worked: true, failed: true, mixed: true, built: true, dropped: true, open: true };
  function inRange(t, a, b) { var d = dayIndex(t.date); return d >= dayIndex(a) && d <= dayIndex(b); }
  function counts(box, mine) {
    var cnt = {}; mine.forEach(function (t) { cnt[t.outcome] = (cnt[t.outcome] || 0) + 1; });
    ["worked", "failed", "mixed", "built", "dropped", "open"].forEach(function (k) {
      if (!cnt[k]) return;
      var sp = h("span", "tried-count", null, box);
      if (OUT[k]) badge(sp, k); else openBadge(sp);
      sp.appendChild(document.createTextNode((OUT[k] ? OUT[k].name : "Still open") + " " + cnt[k]));
    });
  }
  function openBadge(parent) { var sv = el("svg", { viewBox: "-7 -7 14 14", width: 14, height: 14, class: "obadge", "aria-hidden": "true" }); el("circle", { cx: 0, cy: 0, r: 4.5, style: "fill:none;stroke:var(--ink-2);stroke-width:1.4;stroke-dasharray:2 1.5" }, sv); parent.appendChild(sv); }
  function summaries() {
    Array.prototype.forEach.call(document.querySelectorAll(".tried-sum"), function (box) {
      var mine = ALL.filter(function (t) { return inRange(t, box.getAttribute("data-from"), box.getAttribute("data-to")); });
      box.textContent = "";
      h("b", null, mine.length + " things tried", box).style.color = "var(--ink)";
      counts(box, mine);
      var a = h("a", null, "See every one", box);
      a.href = "#everything-" + box.getAttribute("data-n");
    });
  }
  function groups() {
    var host = document.getElementById("tried-groups");
    if (!host) return;
    host.textContent = "";
    STRETCHES.forEach(function (st, i) {
      var mine = ALL.filter(function (t) { return inRange(t, st[0], st[1]); });
      var g = h("div", "stretch-group", null, host);
      g.id = "everything-" + (i + 1);
      var h3 = h("h3", null, null, g);
      h("span", "pn", String(i + 1), h3);
      h3.appendChild(document.createTextNode(st[2]));
      h("small", null, fmtDate(st[0]) + " to " + fmtDate(st[1]), h3);
      var head = h("div", "tried-head", null, g);
      h("b", null, mine.length + " things tried", head);
      counts(head, mine);
      KINDS.forEach(function (k) {
        var ks = mine.filter(function (t) { return t.kind === k[0] && listShown[t.outcome]; });
        if (!ks.length) return;
        h("h5", null, k[1], g);
        var ul = h("ul", "tried", null, g);
        ks.forEach(function (t) {
          var li = h("li", null, null, ul);
          li.id = t.id;
          if (t.outcome === "open") openBadge(li); else badge(li, t.outcome);
          var body = h("span", null, null, li);
          h("b", null, t.title + ". ", body);
          body.appendChild(document.createTextNode(t.text));
          h("span", "tmeta", " " + fmtDates(t) + (t.lane && t.pred ? " · rated " + t.pred + " beforehand" : "") + (t.lane && t.cpu && t.cpu[1] ? " · " + t.cpu[1] + " CPU-hours" : "") + (t.who === "owner" ? " · the owner's call" : ""), body);
        });
      });
    });
  }
  function listFilters() {
    var host = document.getElementById("list-filters");
    if (!host) return;
    host.textContent = "";
    var cnt = {}; ALL.forEach(function (t) { cnt[t.outcome] = (cnt[t.outcome] || 0) + 1; });
    ["worked", "failed", "mixed", "built", "dropped", "open"].forEach(function (k) {
      if (!cnt[k]) return;
      var b = h("button", "chip", null, host);
      b.type = "button";
      b.setAttribute("aria-pressed", "true");
      if (OUT[k]) badge(b, k); else openBadge(b);
      b.appendChild(document.createTextNode((OUT[k] ? OUT[k].name : "Still open") + " · " + cnt[k]));
      b.addEventListener("click", function () { listShown[k] = !listShown[k]; b.setAttribute("aria-pressed", String(listShown[k])); groups(); });
    });
    h("span", "panel-note", ALL.length + " in all", host).style.marginLeft = "6px";
  }
  // two views on one page: the highlights (main) and the full list (#everything)
  var pendingItem = null;
  function route() {
    var hash = location.hash.slice(1);
    var main = document.querySelector("main"), ev = document.getElementById("everything");
    if (!main || !ev) return;
    // views: the highlights (main), the full list (#everything), the statistics (#stats)
    var stats = /^stats(-[\w-]+)?$/.test(hash), st = document.getElementById("stats");
    var detail = /^everything(-\d)?$/.test(hash);
    main.hidden = detail || stats;
    ev.hidden = !detail;
    if (st) st.hidden = !stats;
    Array.prototype.forEach.call(document.querySelectorAll(".nav a.tab-link"), function (a) {
      var on = a.getAttribute("href") === "#stats" ? stats : detail;
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    var target = null;
    if (stats) target = hash === "stats" ? null : document.getElementById(hash);
    else if (detail && pendingItem) target = document.getElementById(pendingItem);
    else if (detail) target = hash === "everything" ? ev : document.getElementById(hash);
    else if (hash) target = document.getElementById(hash);
    pendingItem = null;
    if (target) {
      target.scrollIntoView({ block: target.tagName === "LI" ? "center" : "start" });
      if (target.tagName === "LI") { target.classList.add("flash"); setTimeout(function () { target.classList.remove("flash"); }, 1800); }
    } else if (detail || stats) window.scrollTo(0, 0);
  }
  function openItem(id) {
    pendingItem = id;
    if (location.hash === "#everything") route(); else location.hash = "everything";
  }
  window.addEventListener("hashchange", route);

  // ---------- scorecard ----------
  function calibration() {
    var host = document.getElementById("calibration");
    if (!host) return;
    var L = H.lanes || [];
    var cats = [["likely", "Rated likely"], ["even", "Rated even"], ["long shot", "Rated a long shot"]];
    var order = ["worked", "built", "mixed", "failed"];
    var W = 460, rowH = 40, Lm = 120, R = 104, Hh = cats.length * rowH + 20;
    var s = el("svg", { viewBox: "0 0 " + W + " " + Hh, role: "img", "aria-label": "Lane outcomes by the chance each lane gave itself" }, host);
    var max = 31, x = function (n) { return Lm + (W - Lm - R) * n / max; };
    cats.forEach(function (c, i) {
      var ls = L.filter(function (l) { return l.pred === c[0]; }), y = 18 + i * rowH, cx = Lm;
      txt(s, Lm - 10, y + 15, c[1], { "text-anchor": "end", style: "font-size:13px;fill:var(--ink-2)" });
      order.forEach(function (o) {
        var n = ls.filter(function (l) { return l.outcome === o; }).length;
        if (!n) return;
        var w = x(n) - Lm;
        var r = el("rect", { x: cx + 1, y: y, width: Math.max(1, w - 2), height: 22, rx: 3, style: "fill:" + OUT[o].color }, s);
        // every count shows: inside the bar when it fits, just above it when not
        if (w > 18) txt(s, cx + w / 2, y + 15, String(n), { "text-anchor": "middle", style: "font-size:12px;font-weight:700;fill:#fff" });
        else txt(s, cx + w / 2, y - 4, String(n), { "text-anchor": "middle", style: "font-size:11px;font-weight:700;fill:var(--ink-2)" });
        hover(r, function (box) { h("span", "tv", n + " " + OUT[o].name.toLowerCase(), box); h("div", "tk", c[1] + ": " + ls.filter(function (l) { return l.outcome === o; }).map(function (l) { return l.name; }).join(", "), box); });
        cx += w;
      });
      var worked = ls.filter(function (l) { return l.outcome === "worked" || l.outcome === "built"; }).length;
      txt(s, cx + 8, y + 15, worked + " of " + ls.length + " worked", { style: "font-size:12.5px;fill:var(--ink)" });
    });
    var lg = h("div", "legend", null, host);
    order.forEach(function (o) { var sp = h("span", null, null, lg); badge(sp, o); sp.appendChild(document.createTextNode(" " + OUT[o].name)); });
  }
  function cpuScatter() {
    var host = document.getElementById("cpu-scatter");
    if (!host) return;
    var pts = (H.lanes || []).filter(function (l) { return l.cpu[0] && l.cpu[1]; });
    var W = 460, Hh = 330, Lm = 46, R = 12, T = 12, B = 40;
    var s = el("svg", { viewBox: "0 0 " + W + " " + Hh, role: "img", "aria-label": "CPU estimate against actual per lane" }, host);
    var lo = Math.log10(0.1), hi = Math.log10(120);
    var x = function (v) { return Lm + (W - Lm - R) * (Math.log10(v) - lo) / (hi - lo); };
    var y = function (v) { return T + (Hh - T - B) * (1 - (Math.log10(v) - lo) / (hi - lo)); };
    [0.1, 1, 10, 100].forEach(function (v) {
      el("line", { x1: x(v), x2: x(v), y1: T, y2: Hh - B, style: "stroke:var(--line)" }, s);
      el("line", { x1: Lm, x2: W - R, y1: y(v), y2: y(v), style: "stroke:var(--line)" }, s);
      txt(s, x(v), Hh - B + 16, String(v), { class: "axis", "text-anchor": "middle" });
      txt(s, Lm - 8, y(v) + 4, String(v), { class: "axis", "text-anchor": "end" });
    });
    txt(s, (W + Lm) / 2, Hh - 6, "CPU-hours the lane estimated", { class: "axis", "text-anchor": "middle" });
    txt(s, 14, (Hh - B) / 2, "CPU-hours it used", { class: "axis", "text-anchor": "middle", transform: "rotate(-90 14 " + (Hh - B) / 2 + ")" });
    el("line", { x1: x(0.1), y1: y(0.1), x2: x(120), y2: y(120), style: "stroke:var(--ink-2);stroke-width:1;opacity:.5" }, s);
    txt(s, x(70), y(70) - 8, "on estimate", { class: "axis", "text-anchor": "end" });
    pts.forEach(function (l) {
      var cx = x(l.cpu[0]), cy = y(l.cpu[1]);
      mark(s, l.outcome, cx, cy, 4.5);
      var hit = el("circle", { cx: cx, cy: cy, r: 11, style: "fill:transparent" }, s);
      hover(hit, function (box) { h("span", "tv", l.name, box); h("div", "tk", "estimated " + l.cpu[0] + ", used " + l.cpu[1] + " CPU-hours (" + (l.cpu[1] / l.cpu[0]).toFixed(1) + "x) · " + OUT[l.outcome].name, box); });
    });
  }
  function machine() {
    var host = document.getElementById("machine-use");
    if (!host || !H.machine) return;
    var d = H.machine, W = 460, Hh = 240, Lm = 40, R = 8, T = 16, B = 34, cap = 384;
    var s = el("svg", { viewBox: "0 0 " + W + " " + Hh, role: "img", "aria-label": "Thread-hours of queued work per day against a full day of every thread" }, host);
    var bw = (W - Lm - R) / d.length, y = function (v) { return T + (Hh - T - B) * (1 - v / cap); };
    [0, 96, 192, 288, 384].forEach(function (v) { el("line", { x1: Lm, x2: W - R, y1: y(v), y2: y(v), style: "stroke:var(--line)" }, s); txt(s, Lm - 8, y(v) + 4, String(v), { class: "axis", "text-anchor": "end" }); });
    txt(s, W - R, y(cap) - 4, "all threads, all day", { class: "axis", "text-anchor": "end" });
    d.forEach(function (p, i) {
      var cx = Lm + bw * (i + 0.5), w = Math.min(22, bw * 0.62);
      el("path", { d: "M" + (cx - w / 2) + " " + y(0) + " V" + (y(p[1]) + 3) + " q0 -3 3 -3 H" + (cx + w / 2 - 3) + " q3 0 3 3 V" + y(0) + " Z", style: "fill:var(--net);opacity:" + (p[0] === "11-14" ? .45 : 1) }, s);
      if (i % 3 === 0) txt(s, cx, Hh - 14, p[0].replace("10-", "Oct ").replace("11-", "Nov ").replace(/ 0/, " "), { class: "axis", "text-anchor": "middle", style: "font-size:10.5px" });
      var hit = el("rect", { x: cx - bw / 2, y: T, width: bw, height: Hh - T - B, style: "fill:transparent" }, s);
      hover(hit, function (box) { h("span", "tv", Math.round(p[1]) + " thread-hours", box); h("div", "tk", p[0] + ": " + p[2] + " jobs ended, " + Math.round(100 * p[1] / cap) + "% of the machine", box); });
    });
  }

  function run(f) { try { f(); } catch (e) { if (window.console) console.error(e); } }
  [filters, timeline, summaries, listFilters, groups, calibration, cpuScatter, machine, route].forEach(run);
})();
