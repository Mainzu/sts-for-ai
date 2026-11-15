/* The statistics tab: window.STATS (stats-data.js), by period, each statistic drawn with the chart that fits it
   (bars, line, scatter, bignum, slope, tally, heat, timeline). A chart never mixes settings: bar rows labelled
   A0 / A20 (or a rules version) get a chart each; other kinds hold one setting by construction (see build_data.py). */
(function () {
  "use strict";
  var host = document.getElementById("stat-groups");
  if (!host || !window.STATS) return;
  var NS = "http://www.w3.org/2000/svg";
  var CAT = ["var(--prod)", "var(--net)", "var(--heur)", "var(--gold)", "var(--slime)", "var(--hexa)", "var(--guardian)", "var(--pooled)"];
  function h(tag, cls, text, parent) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function txt(parent, x, y, s, attrs) { var t = el("text", Object.assign({ x: x, y: y }, attrs || {}), parent); t.textContent = s; return t; }
  function tip(node, s) { var t = el("title", {}, node); t.textContent = s; }
  function num(v) {
    if (v === null || v === undefined || isNaN(v)) return "–";
    var a = Math.abs(v);
    var s = a >= 100 ? Math.round(v).toLocaleString("en-US") : a >= 10 ? (Math.round(v * 10) / 10).toString() : (Math.round(v * 100) / 100).toString();
    return s.replace("-", "−");
  }
  function axisNum(v) { var a = Math.abs(v); return a >= 1e6 ? num(v / 1e6) + "M" : a >= 1e4 ? num(v / 1e3) + "k" : num(v); }
  function short(t, n) { return t.length > n ? t.slice(0, n - 1) + "…" : t; }
  function svgBox(parent, w, hh, label) {
    var wrap = h("div", "schart", null, parent);
    return el("svg", { viewBox: "0 0 " + w + " " + hh, role: "img", "aria-label": label || "" }, wrap);
  }
  function scale(lo, hi, a, b) { var d = (hi - lo) || 1; return function (v) { return a + (b - a) * (v - lo) / d; }; }
  function ticks(lo, hi, n) {
    var span = hi - lo || 1, step = Math.pow(10, Math.floor(Math.log10(span / n)));
    [1, 2, 5, 10].some(function (m) { if (span / (step * m) <= n) { step *= m; return true; } return false; });
    var out = [];
    for (var v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Math.round(v * 1e6) / 1e6);
    return out;
  }

  // ---------- bars ----------
  var SET = /\b(A0|A20)(\s+r[\d-]+)?\b/;
  function group(label) { var m = SET.exec(label); return m ? m[0] : ""; }
  function strip(label, g) {
    if (!g) return label;
    var t = label.replace(g, "").replace(/\s{2,}/g, " ").replace(/^[\s:,]+|[\s:,]+$/g, "");
    return t || label;
  }
  function bars(parent, v, def) {
    var rows = v.rows || [], groups = [], by = {};
    var named = rows.some(function (r) { return SET.test(r.label); }) ? def : "";
    rows.forEach(function (r) { var g = group(r.label) || named; if (!(g in by)) { by[g] = []; groups.push(g); } by[g].push(r); });
    groups.forEach(function (g) {
      var box = h("div", "sbars", null, parent);
      if (g) h("div", "sbars-head", g.indexOf("A20") === 0 ? "Ascension 20" + g.slice(3) : "Ascension 0" + g.slice(2), box);
      var rs = by[g];
      var lo = Math.min(0, Math.min.apply(null, rs.map(function (r) { return r.value; })));
      var hi = Math.max(0, Math.max.apply(null, rs.map(function (r) { return r.value; })));
      var span = (hi - lo) || 1;
      rs.forEach(function (r) {
        var row = h("div", "sbar", null, box);
        var base = /^(All |Overall)|baseline/.test(r.label + " " + (r.note || ""));
        h("div", "sbar-label", strip(r.label, g), row);
        var track = h("div", "sbar-track", null, row);
        var zero = (0 - lo) / span * 100, w = Math.abs(r.value) / span * 100;
        var bar = h("i", base ? "base" : (r.value < 0 ? "neg" : ""), null, track);
        bar.style.left = (r.value < 0 ? zero - w : zero) + "%";
        bar.style.width = Math.max(w, 0.6) + "%";
        if (lo < 0) { var z = h("b", "zero", null, track); z.style.left = zero + "%"; }
        h("div", "sbar-val", num(r.value), row);
        if (r.note) h("div", "sbar-note", r.note, row);
      });
    });
  }

  // ---------- line ----------
  function line(parent, v) {
    var series = v.series || [];
    var xs = [];
    series.forEach(function (s) { s.points.forEach(function (p) { if (xs.indexOf(p.x) < 0) xs.push(p.x); }); });
    var ys = [].concat.apply([], series.map(function (s) { return s.points.map(function (p) { return p.y; }); }));
    var lo = Math.min(0, Math.min.apply(null, ys)), hi = Math.max.apply(null, ys);
    var W = 560, H = 230, L = 52, R = 20, T = 14, B = 34;
    var s = svgBox(parent, W, H, v.unit);
    var x = function (k) { return L + (W - L - R) * (xs.length > 1 ? k / (xs.length - 1) : 0.5); };
    var y = scale(lo, hi, H - B, T);
    ticks(lo, hi, 4).forEach(function (t) {
      el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t), class: "sgrid" }, s);
      txt(s, L - 6, y(t) + 4, axisNum(t), { class: "saxis", "text-anchor": "end" });
    });
    var every = Math.ceil(xs.length / 8);
    xs.forEach(function (lab, k) { var last = k === xs.length - 1; if ((k % every === 0 && (last || xs.length - 1 - k >= every)) || last) txt(s, x(k), H - B + 18, lab, { class: "saxis", "text-anchor": "middle" }); });
    series.forEach(function (se, i) {
      var c = CAT[i % CAT.length];
      var pts = se.points.map(function (p) { return [x(xs.indexOf(p.x)), y(p.y), p]; });
      el("path", { d: pts.map(function (p, k) { return (k ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" "), style: "fill:none;stroke:" + c + ";stroke-width:2;stroke-linejoin:round" }, s);
      pts.forEach(function (p) { var d = el("circle", { cx: p[0], cy: p[1], r: 3.5, style: "fill:" + c + ";stroke:var(--surface);stroke-width:1.5" }, s); tip(d, se.name + " · " + p[2].x + ": " + num(p[2].y)); });
    });
    if (series.length > 1) {
      var lg = h("div", "legend", null, parent);
      series.forEach(function (se, i) { var sp = h("span", null, null, lg); var k = h("i", "line", null, sp); k.style.background = CAT[i % CAT.length]; sp.appendChild(document.createTextNode(se.name)); });
    }
  }

  // ---------- scatter ----------
  function scatter(parent, v) {
    var P = v.points || [];
    var W = 560, H = 280, L = 56, R = 20, T = 14, B = 42;
    var xl = Math.min.apply(null, P.map(function (p) { return p.x; })), xh = Math.max.apply(null, P.map(function (p) { return p.x; }));
    var yl = Math.min(0, Math.min.apply(null, P.map(function (p) { return p.y; }))), yh = Math.max.apply(null, P.map(function (p) { return p.y; }));
    if (v.y_label) h("div", "sunit", "Up: " + v.y_label, parent).style.marginTop = "8px";
    var s = svgBox(parent, W, H, (v.x_label || "") + " against " + (v.y_label || ""));
    var x = scale(Math.min(0, xl), xh, L, W - R), y = scale(yl, yh, H - B, T);
    ticks(yl, yh, 4).forEach(function (t) { el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t), class: "sgrid" }, s); txt(s, L - 6, y(t) + 4, axisNum(t), { class: "saxis", "text-anchor": "end" }); });
    ticks(Math.min(0, xl), xh, 5).forEach(function (t) { txt(s, x(t), H - B + 16, num(t), { class: "saxis", "text-anchor": "middle" }); });
    if (v.x_label) txt(s, (L + W - R) / 2, H - 6, v.x_label, { class: "saxis", "text-anchor": "middle" });
    var top = P.slice().sort(function (a, b) { return b.y - a.y; }).slice(0, 3), placed = [];
    P.forEach(function (p) {
      var d = el("circle", { cx: x(p.x), cy: y(p.y), r: 4.5, style: "fill:var(--prod);fill-opacity:.75;stroke:var(--surface);stroke-width:1.5" }, s);
      tip(d, (p.label ? p.label + " · " : "") + num(p.x) + ", " + num(p.y));
      if (p.label && top.indexOf(p) >= 0) {
        var right = x(p.x) > W * 0.6;
        var lab = short(p.label, 30), wdt = lab.length * 6.4, ly = y(p.y) < T + 16 ? y(p.y) + 16 : y(p.y) - 6;
        var bx = right ? x(p.x) - 7 - wdt : x(p.x) + 7, b = { x: bx, y: ly - 11, width: wdt, height: 14 };
        if (!placed.some(function (q) { return b.x < q.x + q.width && q.x < b.x + b.width && b.y < q.y + q.height && q.y < b.y + b.height; })) { placed.push(b); txt(s, x(p.x) + (right ? -7 : 7), ly, lab, { class: "slab", "text-anchor": right ? "end" : "start" }); }
      }
    });
  }

  // ---------- bignum ----------
  function bignum(parent, v) {
    var g = h("div", "sbig", null, parent);
    (v.rows || []).forEach(function (r) {
      var d = h("div", null, null, g);
      h("b", null, num(r.value), d);
      h("span", null, r.label, d);
      if (r.note) h("small", null, r.note, d);
    });
  }

  // ---------- slope ----------
  function slope(parent, v) {
    var R = v.rows || [];
    var vals = [].concat.apply([], R.map(function (r) { return [r.a, r.b]; }));
    var W = 560, H = Math.max(160, 40 + R.length * 26), L = 190, Rm = 190, T = 26, B = 14 + R.length * 6;
    var s = svgBox(parent, W, H, (v.a_label || "") + " to " + (v.b_label || ""));
    var y = scale(Math.min.apply(null, vals), Math.max.apply(null, vals), H - B, T);
    txt(s, L, 14, v.a_label || "before", { class: "saxis", "text-anchor": "middle" });
    txt(s, W - Rm, 14, v.b_label || "after", { class: "saxis", "text-anchor": "middle" });
    el("line", { x1: L, x2: L, y1: T - 4, y2: H - B + 4, class: "sgrid" }, s);
    el("line", { x1: W - Rm, x2: W - Rm, y1: T - 4, y2: H - B + 4, class: "sgrid" }, s);
    function spread(vals) {
      var idx = vals.map(function (v, i) { return i; }).sort(function (i, j) { return vals[i] - vals[j]; }), out = vals.slice(), last = -1e9;
      idx.forEach(function (i) { out[i] = Math.max(vals[i], last + 14); last = out[i]; });
      return out;
    }
    var la = spread(R.map(function (r) { return y(r.a); })), lb = spread(R.map(function (r) { return y(r.b); }));
    R.forEach(function (r, i) {
      var c = r.b >= r.a ? "var(--prod)" : "var(--net)";
      el("line", { x1: L, x2: W - Rm, y1: y(r.a), y2: y(r.b), style: "stroke:" + c + ";stroke-width:2" }, s);
      el("circle", { cx: L, cy: y(r.a), r: 4, style: "fill:" + c }, s);
      el("circle", { cx: W - Rm, cy: y(r.b), r: 4, style: "fill:" + c }, s);
      var lt = txt(s, L - 8, la[i] + 4, short(r.label, 22) + "  " + num(r.a), { class: "slab", "text-anchor": "end" }); tip(lt, r.label);
      txt(s, W - Rm + 8, lb[i] + 4, num(r.b), { class: "slab" });
    });
  }

  // ---------- tally ----------
  function tally(parent, v) {
    var R = (v.rows || []).filter(function (r) { return r.value > 0; });
    var total = R.reduce(function (a, r) { return a + r.value; }, 0) || 1;
    var bar = h("div", "stally", null, parent);
    R.forEach(function (r, i) {
      var seg = h("i", null, null, bar);
      seg.style.width = (100 * r.value / total) + "%";
      seg.style.background = CAT[i % CAT.length];
      seg.title = r.label + ": " + num(r.value) + " (" + Math.round(100 * r.value / total) + "%)";
    });
    var lg = h("div", "legend", null, parent);
    R.forEach(function (r, i) { var sp = h("span", null, null, lg); h("i", null, null, sp).style.background = CAT[i % CAT.length]; sp.appendChild(document.createTextNode(r.label + " · " + num(r.value))); });
  }

  // ---------- heat ----------
  function heat(parent, v) {
    var xs = v.xs || [], ys = v.ys || [], C = v.cells || [];
    var all = [].concat.apply([], C), hi = Math.max.apply(null, all.concat([0])) || 1;
    var wrap = h("div", "sheat-wrap", null, parent);
    var t = h("table", "sheat", null, wrap);
    var hr = h("tr", null, null, t); h("th", null, "", hr);
    xs.forEach(function (x) { h("th", null, x, hr); });
    ys.forEach(function (yl, j) {
      var tr = h("tr", null, null, t); h("th", null, yl, tr);
      xs.forEach(function (x, i) {
        var val = (C[j] || [])[i] || 0, td = h("td", null, null, tr);
        td.style.background = val ? "color-mix(in srgb, var(--prod) " + Math.round(12 + 80 * val / hi) + "%, transparent)" : "transparent";
        td.title = yl + " · " + x + ": " + num(val);
      });
    });
  }

  // ---------- timeline ----------
  function timeline(parent, v) {
    var ol = h("ol", "stime", null, parent);
    (v.events || []).forEach(function (e) {
      var li = h("li", null, null, ol);
      h("span", "sdate", e.x, li);
      h("span", null, e.label, li);
      if (e.value !== undefined && e.value !== null) h("b", null, num(e.value), li);
    });
  }

  var KIND = { bars: bars, line: line, scatter: scatter, bignum: bignum, slope: slope, tally: tally, heat: heat, timeline: timeline };
  function card(grid, it) {
    var c = h("article", "panel stat", null, grid);
    c.id = "stats-" + it.id;
    h("h4", null, it.title, c);
    var tg = h("span", "tag", it.tag, c);
    tg.setAttribute("tabindex", "0");
    tg.setAttribute("data-tip", it.setting + (it.checked === "corrected" ? " · Corrected by its independent check." : " · Confirmed by an independent check."));
    h("p", "stat-claim", it.claim, c);
    var v = it.viz;
    if (v && KIND[v.kind]) {
      try { KIND[v.kind](c, v, (SET.exec(it.setting) || [""])[0]); } catch (e) { /* a chart that can't draw leaves the text */ }
      if (v.unit && v.kind !== "bignum" && v.kind !== "timeline") h("div", "sunit", v.unit, c);
    }
    if (it.caveat) {
      var det = h("details", "stat-more", null, c);
      h("summary", null, "How it was counted", det);
      h("p", null, it.caveat, det);
    }
  }
  var nav = h("div", "chips stat-jump", null, host);
  window.STATS.forEach(function (per) {
    var n = per.parts.reduce(function (a, p) { return a + p.items.length; }, 0);
    if (!n) return;
    var a = h("a", "chip", per.name + " · " + n, nav);
    a.href = "#stats-" + per.key;
  });
  window.STATS.forEach(function (per) {
    if (!per.parts.some(function (p) { return p.items.length; })) return;
    var g = h("div", "stat-sec", null, host);
    g.id = "stats-" + per.key;
    var hd = h("h3", null, per.name, g);
    if (per.dates) h("small", null, per.dates, hd);
    per.parts.forEach(function (part) {
      if (!part.items.length) return;
      if (part.name) h("h5", "stat-part", part.name, g);
      var grid = h("div", "stat-grid", null, g);
      part.items.forEach(function (it) { card(grid, it); });
    });
  });
})();
