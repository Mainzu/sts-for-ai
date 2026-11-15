/* Charts for the sts-for-ai showcase. Data: window.SHOWCASE (data.js, written by extract.py).
   Every chart draws one setting; prose numbers are in index.html. */
(function () {
  "use strict";
  var S = window.SHOWCASE || null;
  var NS = "http://www.w3.org/2000/svg";

  // ---------- helpers ----------
  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function txt(parent, x, y, s, attrs) {
    var t = el("text", Object.assign({ x: x, y: y }, attrs || {}), parent);
    t.textContent = s;
    return t;
  }
  function h(tag, cls, text, parent) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function svgIn(id, w, hgt, label) {
    var host = document.getElementById(id);
    if (!host) return null;
    host.textContent = "";
    var s = el("svg", { viewBox: "0 0 " + w + " " + hgt, role: "img", "aria-label": label || "" }, host);
    return s;
  }
  function sgn(x, d) { var v = Number(x).toFixed(d); return (Number(v) > 0 ? "+" : Number(v) < 0 ? "−" : "") + v.replace("-", ""); }
  var BOSS_ICON = [["i-boss-hexaghost", "var(--hexa)"], ["i-boss-slime", "var(--slime)"], ["i-boss-guardian", "var(--guardian)"]];
  function bosses(parent, x, y, size, tri) {
    BOSS_ICON.forEach(function (b, i) {
      var dx = tri ? (i === 0 ? 0 : (i === 1 ? -1 : 1) * (size / 2 + 1)) : (i - 1) * (size + 3);
      var dy = tri ? (i === 0 ? -size / 2 - 1 : size / 2 + 1) : 0;
      use(parent, b[0], x + dx, y + dy, size, b[1]);
    });
  }
  function fmt(x, d) { return (x === null || x === undefined) ? "–" : Number(x).toFixed(d === undefined ? 3 : d); }
  function use(parent, id, x, y, size, color) {
    if (id === "i-elite") size *= 1.55;
    var w = id === "i-boss" ? size * 3 : size;
    var u = el("use", { href: "#" + id, x: x - w / 2, y: y - size / 2, width: w, height: size }, parent);
    u.style.color = color;
    return u;
  }

  // ---------- tooltip ----------
  var tip = document.getElementById("tip");
  var tipOwner = null;
  function tipShow(build, x, y, owner) {
    tipOwner = owner || null;
    tip.textContent = "";
    build(tip);
    tip.classList.add("on");
    var r = tip.getBoundingClientRect();
    var vw = window.innerWidth, vh = window.innerHeight;
    var left = x + 14, top = y + 14;
    if (left + r.width > vw - 8) left = Math.max(8, x - r.width - 14);
    if (top + r.height > vh - 8) top = Math.max(8, y - r.height - 14);
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }
  function tipHide(owner) { if (!owner || owner === tipOwner) { tip.classList.remove("on"); tipOwner = null; } }
  function line(parent, value, label, color) {
    var row = h("div", "row", null, parent);
    if (color) { var i = h("i", null, null, row); i.style.background = color; }
    var b = h("b", null, value, row);
    if (label) h("span", "tk", label, row);
    return row;
  }
  // a mark (svg element or html element) with hover/focus tooltip
  function hover(node, build) {
    node.setAttribute("tabindex", "0");
    node.style.cursor = "default";
    node.addEventListener("pointermove", function (e) { tipShow(build, e.clientX, e.clientY, node); });
    node.addEventListener("pointerleave", function () { tipHide(node); });
    node.addEventListener("focus", function () { var r = node.getBoundingClientRect(); tipShow(build, r.left + r.width / 2, r.bottom, node); });
    node.addEventListener("blur", function () { tipHide(node); });
  }
  // setting tags
  Array.prototype.forEach.call(document.querySelectorAll("[data-tip]"), function (t) {
    var build = function (box) {
      h("span", "tk", "Setting", box);
      var c = h("div", null, null, box);
      var code = h("code", null, t.getAttribute("data-tip"), c);
      code.style.whiteSpace = "normal";
    };
    t.addEventListener("pointerenter", function (e) { tipShow(build, e.clientX, e.clientY, t); });
    t.addEventListener("pointermove", function (e) { if (tipOwner === t) tipShow(build, e.clientX, e.clientY, t); });
    t.addEventListener("pointerleave", function () { tipHide(t); });
    t.addEventListener("focus", function () { var r = t.getBoundingClientRect(); tipShow(build, r.left, r.bottom, t); });
    t.addEventListener("blur", function () { tipHide(t); });
    t.addEventListener("click", function (e) { var r = t.getBoundingClientRect(); tipShow(build, r.left, r.bottom, t); e.stopPropagation(); });
  });
  document.addEventListener("click", function () { tipHide(); });
  window.addEventListener("scroll", function () { tipHide(); }, { passive: true });

  var FLOORS = ["easy", "easy", "easy", "hard", "hard", "elite", "hard", "hard", "elite", "hard", "boss"];
  var FLOOR_NAME = { easy: "Easy hallway", hard: "Hard hallway", elite: "Elite", boss: "Boss" };
  var FLOOR_POOL = {
    easy: "Cultist, Jaw Worm, two Louses or small slimes",
    hard: "Looter, Large Slime, Lots of Slimes, three Louses, two Fungi Beasts, Exordium Thugs or Exordium Wildlife",
    elite: "Gremlin Nob, Lagavulin or three Sentries",
    boss: "Slime Boss, The Guardian or Hexaghost"
  };
  var ICON = { easy: "i-easy", hard: "i-monster", elite: "i-elite", boss: "i-boss", rest: "i-rest" };
  var BOSS = {
    slime_boss: { name: "Slime Boss", color: "var(--slime)" },
    the_guardian: { name: "The Guardian", color: "var(--guardian)" },
    hexaghost: { name: "Hexaghost", color: "var(--hexa)" }
  };

  // ---------- hero strip: where 500 runs end ----------
  function heroStrip() {
    if (!S) return;
    var P = S.product;
    var W = 1000, H = 342, L = 64, R = 120;
    var s = svgIn("hero-strip", W, H, "Average HP entering each fight and runs that ended there, product, runs 0-499");
    if (!s) return;
    var slots = 12; // 10 floors, campfire, boss
    var sw = (W - L - R) / slots;
    var cx = function (k) { return L + sw * (k + 0.5); };
    var floorSlot = function (f) { return f < 10 ? f : 11; }; // f = 0..10
    // HP row
    var hy0 = 150, hy1 = 34; // y for 0 HP and 80 HP
    var hyy = function (v) { return hy0 - (hy0 - hy1) * v / 80; };
    var g = el("g", { class: "grid" }, s);
    [0, 20, 40, 60, 80].forEach(function (v) {
      el("line", { x1: L, x2: W - R + 10, y1: hyy(v), y2: hyy(v) }, g);
      txt(s, L - 10, hyy(v) + 4, String(v), { class: "axis", "text-anchor": "end" });
    });
    txt(s, L - 10, hy1 - 14, "HP", { class: "axis", "text-anchor": "end" });
    var pts = P.mean_hp_start.map(function (v, f) { return [cx(floorSlot(f)), hyy(v)]; });
    var d = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
    var area = d + " L" + pts[pts.length - 1][0].toFixed(1) + " " + hy0 + " L" + pts[0][0].toFixed(1) + " " + hy0 + " Z";
    el("path", { d: area, style: "fill:var(--prod);opacity:.09" }, s);
    el("path", { d: d, style: "fill:none;stroke:var(--prod);stroke-width:2;stroke-linejoin:round;stroke-linecap:round" }, s);
    pts.forEach(function (p, f) {
      el("circle", { cx: p[0], cy: p[1], r: 4.5, style: "fill:var(--prod);stroke:var(--surface);stroke-width:2" }, s);
    });
    // label first, the elites' low point and the boss arrival
    [[0, "80"], [9, fmt(P.mean_hp_start[9], 1)], [10, fmt(P.mean_hp_start[10], 1)]].forEach(function (a) {
      var p = pts[a[0]];
      txt(s, p[0], p[1] - 12, a[1], { "text-anchor": "middle", style: "font-size:13px;font-weight:700;fill:var(--ink)" });
    });
    // node row
    var ny = 190;
    el("line", { x1: cx(0), x2: cx(11), y1: ny, y2: ny, style: "stroke:var(--line-2);stroke-width:2;stroke-dasharray:2 5;stroke-linecap:round" }, s);
    for (var k = 0; k < slots; k++) {
      var type = k < 10 ? FLOORS[k] : (k === 10 ? "rest" : "boss");
      var col = type === "elite" ? "var(--gold)" : type === "boss" ? "var(--accent)" : type === "rest" ? "var(--gold)" : "var(--ink-2)";
      if (type === "boss") bosses(s, cx(k), ny, 44, true); else use(s, ICON[type], cx(k), ny, 24, col);
      txt(s, cx(k), type === "boss" ? ny + 56 : ny + 32, k < 10 ? String(k + 1) : (k === 10 ? "rest" : "11"), { class: "axis", "text-anchor": "middle" });
    }
    txt(s, cx(10), ny - 24, "+24 HP", { "text-anchor": "middle", style: "font-size:12px;fill:var(--gold);font-weight:700" });
    // deaths row
    var dy0 = 330, dh = 62, dmax = 70;
    el("line", { x1: L, x2: W - R + 10, y1: dy0, y2: dy0, class: "base" }, s);
    txt(s, L - 10, dy0 - dh + 4, "died", { class: "axis", "text-anchor": "end" });
    txt(s, L - 10, dy0 - dh + 18, "here", { class: "axis", "text-anchor": "end" });
    P.deaths_by_floor.forEach(function (v, f) {
      if (!v) return;
      var x = cx(floorSlot(f)), bh = dh * v / dmax, bw = Math.min(24, sw * 0.5);
      el("path", { d: "M" + (x - bw / 2) + " " + dy0 + " V" + (dy0 - bh + 4) + " q0 -4 4 -4 H" + (x + bw / 2 - 4) + " q4 0 4 4 V" + dy0 + " Z", style: "fill:var(--prod)" }, s);
      txt(s, x, dy0 - bh - 6, String(v), { "text-anchor": "middle", style: "font-size:13px;font-weight:700;fill:var(--ink)" });
    });
    // cleared
    var ex = W - R + 34;
    txt(s, ex, 196, String(P.clears), { style: "font-size:34px;font-weight:700;fill:var(--ink)" });
    txt(s, ex, 216, "of " + P.n + " cleared", { style: "font-size:13px;fill:var(--muted)" });
    // hit areas
    for (var j = 0; j < slots; j++) (function (k) {
      var r = el("rect", { x: cx(k) - sw / 2, y: 20, width: sw, height: H - 20, style: "fill:transparent" }, s);
      var f = k < 10 ? k : (k === 11 ? 10 : null);
      hover(r, function (box) {
        if (f === null) {
          h("span", "tv", "Campfire", box);
          h("div", "tk", "Rests before the boss: heals 30% of max HP (24 of 80). The product's runs arrive at the boss with " + fmt(P.mean_hp_start[10], 1) + " HP on average.", box);
          return;
        }
        var type = FLOORS[f];
        h("span", "tv", "Floor " + (f + 1) + " · " + FLOOR_NAME[type], box);
        h("div", "tk", FLOOR_POOL[type], box);
        line(box, fmt(P.mean_hp_start[f], 1), "average HP walking in");
        line(box, sgn(-P.mean_hp_lost_won[f], 1), "HP change when it won");
        line(box, String(P.deaths_by_floor[f]), "runs ended here");
        function line(b, v, l) { var row = h("div", "row", null, b); h("b", null, v, row); h("span", "tk", l, row); }
      });
    })(j);
  }

  // ---------- content rows ----------
  function contentRows() {
    var host = document.getElementById("content-rows");
    if (!host) return;
    var rows = [
      { name: "Curated cards and monsters (the headline)", tag: "headline · runs 0–499 · 11-03", tip: "Headline setting, runs 0–499, n 500: heuristic one turn (0.534), 10-29 net @hpb0.01 one turn (0.680), product two turns (0.834).",
        v: [[null, 0.534], [null, 0.680], [null, 0.834]] },
      { name: "+ 27 real Act 1 Ironclad cards in the offers", tag: "pack offers · runs 0–499 · 11-07", tip: "--pack content/packs/act1-ironclad.json: 27 pack cards added to both halves' reward pools; each player against its own control on the same runs, n 500 (jobs 0463–0466). Read 2026-11-07.",
        v: [[0.534, 0.428], [0.680, 0.522], [0.834, 0.684]] },
      { name: "+ the real Act 1 hallway encounters", tag: "real hallways · runs 0–249 · 11-09", tip: "--pack content/packs/act1-monsters.json: its hallway encounters join the hard floors; runs 0–249 at fixed n 250 (the product's read, job 0600). Read 2026-11-09.",
        v: [[0.532, 0.504], [0.688, 0.608], [0.836, 0.756]] }
    ];
    var colors = ["var(--heur)", "var(--net)", "var(--prod)"];
    var names = ["Hand-written, one turn", "Net, one turn", "Net, two turns"];
    host.textContent = "";
    var grid = h("div", "content-rows", null, host);
    rows.forEach(function (row) {
      var r = h("div", "crow", null, grid);
      var lab = h("div", null, null, r);
      h("div", null, row.name, lab).style.cssText = "font-size:14.5px;color:var(--ink);font-weight:700;line-height:1.3";
      var tg = h("span", "tag", row.tag, lab);
      tg.setAttribute("tabindex", "0");
      tg.style.marginTop = "6px";
      (function (t, tipText) {
        var build = function (box) { h("span", "tk", "Setting", box); h("div", null, null, box).appendChild(h("code", null, tipText)); };
        t.addEventListener("pointerenter", function (e) { tipShow(build, e.clientX, e.clientY, t); });
        t.addEventListener("pointerleave", function () { tipHide(t); });
        t.addEventListener("focus", function () { var b = t.getBoundingClientRect(); tipShow(build, b.left, b.bottom, t); });
        t.addEventListener("blur", function () { tipHide(t); });
      })(tg, row.tip);
      var holder = h("div", "chart narrow", null, r);
      var W = 560, H = 70, L = 16, Rm = 16;
      var s = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": row.name }, holder);
      var x = function (v) { return L + (W - L - Rm) * (v - 0.4) / 0.5; };
      var g = el("g", { class: "grid" }, s);
      [0.4, 0.5, 0.6, 0.7, 0.8, 0.9].forEach(function (t) {
        el("line", { x1: x(t), x2: x(t), y1: 14, y2: 50 }, g);
        txt(s, x(t), 66, t.toFixed(1), { class: "axis", "text-anchor": "middle" });
      });
      row.v.forEach(function (pair, i) {
        var y = 32;
        if (pair[0] !== null) {
          el("line", { x1: x(pair[0]), x2: x(pair[1]) + 6, y1: y, y2: y, style: "stroke:" + colors[i] + ";stroke-width:2;opacity:.45" }, s);
          el("circle", { cx: x(pair[0]), cy: y, r: 5, style: "fill:var(--surface);stroke:" + colors[i] + ";stroke-width:2;opacity:.7" }, s);
        }
        el("circle", { cx: x(pair[1]), cy: y, r: 6.5, style: "fill:" + colors[i] + ";stroke:var(--surface);stroke-width:2" }, s);
        txt(s, x(pair[1]), y - 12, pair[1].toFixed(3), { "text-anchor": "middle", style: "font-size:12.5px;font-weight:700;fill:var(--ink)" });
        var hit = el("circle", { cx: x(pair[1]), cy: y, r: 14, style: "fill:transparent" }, s);
        hover(hit, function (box) {
          h("span", "tv", pair[1].toFixed(3) + " clears", box);
          h("div", "tk", names[i] + (pair[0] !== null ? " · " + pair[0].toFixed(3) + " on its usual test, the same runs (" + (pair[1] - pair[0] >= 0 ? "+" : "") + (pair[1] - pair[0]).toFixed(3) + ")" : ""), box);
        });
      });
    });
  }

  // ---------- how it plays: search tree ----------
  function tree() {
    var W = 1000, H = 350;
    var s = svgIn("tree", W, H, "Illustration of a two-turn search for one decision");
    if (!s) return;
    s.classList.add("tree");
    var parts = {};
    function reg(step, node) { (parts[step] = parts[step] || []).push(node); return node; }
    function box(x, y, w, hh, lines, steps, cls) {
      var g = el("g", { class: "node" + (cls ? " " + cls : "") }, s);
      el("rect", { x: x, y: y, width: w, height: hh, rx: 8 }, g);
      lines.forEach(function (l, i) { txt(g, x + 10, y + 19 + i * 15, l[0], { class: l[1] || "" }); });
      steps.forEach(function (st) { reg(st, g); });
      return g;
    }
    function edge(d, steps) { var p = el("path", { d: d, class: "edge" }, s); steps.forEach(function (st) { reg(st, p); }); return p; }
    var stages = [[20, "POSITION"], [196, "OPTIONS"], [372, "AFTER ONE OPTION"], [556, "END OF TURN"], [716, "CHANCE"], [800, "TURN TWO"], [912, "SCORE"]];
    var sg = el("g", { class: "stage" }, s);
    stages.forEach(function (a) { txt(sg, a[0], 16, a[1]); });
    // root
    box(20, 112, 156, 112, [["Your turn", "h"], ["Energy 3 · HP 62", "m"], ["Bash, Strike ×2,", ""], ["Defend ×2", ""], ["Jaw Worm, 42 HP", ""], ["intends 11 damage", "m"]], [7]);
    // options
    var opts = [["Bash → Jaw Worm", 44], ["Strike → Jaw Worm", 98], ["Defend", 152], ["End turn", 206]];
    opts.forEach(function (o, i) {
      edge("M176 168 C186 168, 186 " + (o[1] + 17) + ", 196 " + (o[1] + 17), i === 0 ? [1, 7] : [1]);
      box(196, o[1], 150, 34, [[o[0], ""]], [1].concat(i === 0 ? [7] : []));
    });
    txt(s, 196, 270, "two Strikes, one option", { class: "m" });
    txt(s, 196, 284, "two Defends, one option", { class: "m" });
    reg(1, s.lastChild); reg(1, s.lastChild.previousSibling);
    // afterstate of Bash
    edge("M346 61 C358 61, 358 74, 372 74", [2, 7]);
    box(372, 44, 160, 64, [["Jaw Worm 34 HP", ""], ["Vulnerable 2", "m"], ["Energy 1, hand 4", "m"]], [2, 7]);
    txt(s, 372, 128, "searched again from here:", { class: "m" });
    txt(s, 372, 142, "Strike → 25 HP (×1.5), …", { class: "m" });
    reg(2, s.lastChild); reg(2, s.lastChild.previousSibling);
    // end of turn
    edge("M532 76 C546 76, 546 150, 556 150", [4, 7]);
    edge("M346 223 C450 223, 470 170, 556 170", [4]);
    box(556, 122, 148, 84, [["Monsters act", "h"], ["Chomp: 11 damage", ""], ["you 62 → 51", "m"], ["stop before the draw", "m"]], [4, 7]);
    // one-turn leaf mark
    var lf = el("g", null, s);
    el("circle", { cx: 630, cy: 240, r: 15, style: "fill:var(--surface-2);stroke:var(--line-2)" }, lf);
    txt(lf, 630, 244, "1.58", { class: "v", "text-anchor": "middle" });
    txt(lf, 630, 272, "one turn deep:", { class: "m", "text-anchor": "middle" });
    txt(lf, 630, 286, "score it here", { class: "m", "text-anchor": "middle" });
    el("path", { d: "M630 206 V225", class: "edge" }, s);
    reg(4, lf); reg(4, s.lastChild);
    // chance
    edge("M704 164 H724", [3, 5, 7]);
    var cg = el("g", { class: "node" }, s);
    el("path", { d: "M742 146 L760 164 L742 182 L724 164 Z", class: "box" }, cg);
    txt(cg, 742, 169, "?", { class: "h", "text-anchor": "middle" });
    reg(3, cg); reg(5, cg); reg(7, cg);
    txt(s, 704, 300, "4 sampled hands", { class: "m" });
    txt(s, 704, 314, "of 5 from the bag", { class: "m" });
    reg(3, s.lastChild); reg(3, s.lastChild.previousSibling);
    // turn two
    var ys = [70, 126, 182, 238];
    var vals = ["1.71", "1.66", "1.62", "1.69"];
    ys.forEach(function (y, i) {
      edge("M760 164 C780 164, 780 " + (y + 14) + ", 800 " + (y + 14), [5]);
      box(800, y, 88, 28, [["search turn 2", "m"]], [5]);
      edge("M888 " + (y + 14) + " H912", [6]);
      var sc = el("g", null, s);
      el("circle", { cx: 930, cy: y + 14, r: 15, style: "fill:var(--surface-2);stroke:var(--line-2)" }, sc);
      txt(sc, 930, y + 18, vals[i], { class: "v", "text-anchor": "middle" });
      reg(6, sc);
    });
    txt(s, 990, 296, "average: 1.67", { class: "v", "text-anchor": "end" });
    txt(s, 990, 312, "the net scores each leaf", { class: "m", "text-anchor": "end" });
    reg(6, s.lastChild); reg(6, s.lastChild.previousSibling);
    txt(s, 20, 336, "Illustration with made-up scores, not a recorded game.", { class: "m" });
    // hook steps
    var lis = document.querySelectorAll("#steps li");
    function lite(step, on) {
      (parts[step] || []).forEach(function (n) { n.classList.toggle("lit", on); });
      Array.prototype.forEach.call(lis, function (li) { li.classList.toggle("on", on && li.getAttribute("data-step") === String(step)); });
    }
    Array.prototype.forEach.call(lis, function (li) {
      var st = li.getAttribute("data-step");
      li.setAttribute("tabindex", "0");
      li.addEventListener("pointerenter", function () { lite(st, true); });
      li.addEventListener("pointerleave", function () { lite(st, false); });
      li.addEventListener("focus", function () { lite(st, true); });
      li.addEventListener("blur", function () { lite(st, false); });
    });
  }

  // ---------- finding 1: boss curve ----------
  function bossCurve() {
    if (!S) return;
    var B = S.boss_curve;
    var W = 640, H = 300, L = 44, R = 20, T = 14, Bm = 36;
    var s = svgIn("boss-curve", W, H, "Chance to beat each boss by entry HP");
    if (!s) return;
    var x = function (hp) { return L + (W - L - R) * (hp - 30) / 50; };
    var y = function (p) { return T + (H - T - Bm) * (1 - p); };
    var g = el("g", { class: "grid" }, s);
    [0, 0.25, 0.5, 0.75, 1].forEach(function (p) {
      el("line", { x1: L, x2: W - R, y1: y(p), y2: y(p) }, g);
      txt(s, L - 8, y(p) + 4, p === 0 ? "0" : p.toFixed(2).replace(/0$/, ""), { class: "axis", "text-anchor": "end" });
    });
    B.hp.forEach(function (hp) { txt(s, x(hp), H - Bm + 18, String(hp), { class: "axis", "text-anchor": "middle" }); });
    txt(s, (W + L) / 2, H - 4, "HP walking into the boss (of 80)", { class: "axis", "text-anchor": "middle" });
    var order = [["pooled", "var(--pooled)", "all three"], ["the_guardian", "var(--guardian)", "The Guardian"], ["hexaghost", "var(--hexa)", "Hexaghost"], ["slime_boss", "var(--slime)", "Slime Boss"]];
    order.forEach(function (o) {
      var c = B.curves[o[0]];
      var d = c.map(function (p, i) { return (i ? "L" : "M") + x(B.hp[i]).toFixed(1) + " " + y(p).toFixed(1); }).join(" ");
      el("path", { d: d, style: "fill:none;stroke:" + o[1] + ";stroke-width:" + (o[0] === "pooled" ? 1.6 : 2) + ";stroke-linejoin:round;stroke-linecap:round" }, s);
      c.forEach(function (p, i) { el("circle", { cx: x(B.hp[i]), cy: y(p), r: o[0] === "pooled" ? 3 : 4, style: "fill:" + o[1] + ";stroke:var(--surface);stroke-width:2" }, s); });
    });
    // direct labels at 40 HP (lines are apart there)
    var lab = { slime_boss: [40, 10, -10, "start"], hexaghost: [80, 0, 24, "end"], pooled: [40, -10, -8, "end"], the_guardian: [40, 10, 18, "start"] };
    order.forEach(function (o) {
      var a = lab[o[0]], p = B.curves[o[0]][B.hp.indexOf(a[0])];
      txt(s, x(a[0]) + a[1], y(p) + a[2], o[2], { "text-anchor": a[3], style: "font-size:12.5px;font-weight:700;fill:var(--ink-2)" });
    });
    // the guardian's cliff note
    txt(s, x(50) + 8, y(0.493) + 30, "the cliff", { style: "font-size:12px;fill:var(--muted);font-style:italic" });
    // crosshair
    var cross = el("line", { x1: 0, x2: 0, y1: T, y2: H - Bm, style: "stroke:var(--line-2);stroke-width:1;opacity:0" }, s);
    var hit = el("rect", { x: L, y: T, width: W - L - R, height: H - T - Bm, style: "fill:transparent" }, s);
    function at(clientX) {
      var r = s.getBoundingClientRect();
      var vx = (clientX - r.left) * W / r.width;
      var best = 0;
      B.hp.forEach(function (hp, i) { if (Math.abs(x(hp) - vx) < Math.abs(x(B.hp[best]) - vx)) best = i; });
      return best;
    }
    function show(i, cx, cy) {
      cross.setAttribute("x1", x(B.hp[i])); cross.setAttribute("x2", x(B.hp[i])); cross.style.opacity = 1;
      tipShow(function (box) {
        h("span", "tk", B.hp[i] + " HP walking in", box);
        order.slice().reverse().forEach(function (o) { line(box, B.curves[o[0]][i].toFixed(2), o[2], o[1]); });
      }, cx, cy, hit);
    }
    hit.setAttribute("tabindex", "0");
    hit.addEventListener("pointermove", function (e) { show(at(e.clientX), e.clientX, e.clientY); });
    hit.addEventListener("pointerleave", function () { cross.style.opacity = 0; tipHide(hit); });
    var kb = 2;
    hit.addEventListener("focus", function () { var r = hit.getBoundingClientRect(); show(kb, r.left + r.width / 2, r.top); });
    hit.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { kb = Math.max(0, Math.min(5, kb + (e.key === "ArrowRight" ? 1 : -1))); var r = hit.getBoundingClientRect(); show(kb, r.left + r.width / 2, r.top); e.preventDefault(); }
    });
    hit.addEventListener("blur", function () { cross.style.opacity = 0; tipHide(hit); });
  }

  function bossBars() {
    if (!S) return;
    var a = S.product.boss, b = S.product_b.boss;
    var rows = ["slime_boss", "the_guardian", "hexaghost"].map(function (k) {
      var arr = a[k][0] + b[k][0], win = a[k][1] + b[k][1];
      return { k: k, arr: arr, win: win, p: win / arr };
    });
    var notes = {
      slime_boss: "13 deaths; 12 of them walked in under 50 HP.",
      the_guardian: "57 deaths; 48 of them walked in under 60 HP.",
      hexaghost: "70 deaths; 44 of them walked in with 50 HP or more. Win 0.69 at 50–59 HP, 0.93 at 70+."
    };
    var W = 640, H = 118, L = 110, R = 54;
    var s = svgIn("boss-bars", W, H, "Boss wins per arrival, product, 1,000 runs");
    if (!s) return;
    var x = function (p) { return L + (W - L - R) * p; };
    var g = el("g", { class: "grid" }, s);
    [0, 0.25, 0.5, 0.75, 1].forEach(function (p) { el("line", { x1: x(p), x2: x(p), y1: 4, y2: H - 20 }, g); txt(s, x(p), H - 4, p === 0 ? "0" : String(p), { class: "axis", "text-anchor": "middle" }); });
    rows.forEach(function (r, i) {
      var y = 10 + i * 32, bh = 18;
      txt(s, L - 10, y + 13, BOSS[r.k].name, { "text-anchor": "end", style: "font-size:13px;fill:var(--ink-2)" });
      el("path", { d: "M" + x(0) + " " + y + " H" + (x(r.p) - 4) + " q4 0 4 4 V" + (y + bh - 4) + " q0 4 -4 4 H" + x(0) + " Z", style: "fill:" + BOSS[r.k].color }, s);
      txt(s, x(r.p) + 8, y + 14, r.p.toFixed(3), { style: "font-size:13px;font-weight:700;fill:var(--ink)" });
      var hit = el("rect", { x: L, y: y - 4, width: W - L - R + 50, height: bh + 8, style: "fill:transparent" }, s);
      hover(hit, function (box) {
        h("span", "tv", r.win + " of " + r.arr + " arrivals won", box);
        h("div", "tk", BOSS[r.k].name + ". " + notes[r.k], box);
      });
    });
  }

  // ---------- finding 2: HP change per won fight ----------
  function hpLoss() {
    if (!S) return;
    var P = S.product.mean_hp_lost_won;
    var W = 640, H = 270, L = 40, R = 10, T = 14, Bm = 92;
    var s = svgIn("hp-loss", W, H, "Mean HP change per won fight by floor, product");
    if (!s) return;
    var min = -35;
    var bw = (W - L - R) / 11;
    var y = function (v) { return T + (H - T - Bm) * (v / min); };
    var g = el("g", { class: "grid" }, s);
    [0, -10, -20, -30].forEach(function (v) { el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v) }, g); txt(s, L - 8, y(v) + 4, v ? "−" + Math.abs(v) : "0", { class: "axis", "text-anchor": "end" }); });
    P.forEach(function (lost, f) {
      var v = -lost, type = FLOORS[f], cx = L + bw * (f + 0.5), vv = Math.min(0, v), w = Math.min(24, bw * 0.6);
      var color = type === "elite" ? "var(--prod)" : type === "boss" ? "var(--ink-2)" : "var(--heur)";
      if (vv < -0.05) el("path", { d: "M" + (cx - w / 2) + " " + y(0) + " V" + (y(vv) - 4) + " q0 4 4 4 H" + (cx + w / 2 - 4) + " q4 0 4 -4 V" + y(0) + " Z", style: "fill:" + color }, s);
      if (type === "elite" || type === "boss") txt(s, cx, y(vv) + 16, sgn(vv, 1), { "text-anchor": "middle", style: "font-size:13px;font-weight:700;fill:var(--ink)" });
      if (type === "boss") bosses(s, cx, H - Bm + 44, 32, true); else use(s, ICON[type], cx, H - Bm + 22, 20, type === "elite" ? "var(--gold)" : "var(--ink-2)");
      txt(s, cx, H - 4, String(f + 1), { class: "axis", "text-anchor": "middle" });
      var hit = el("rect", { x: cx - bw / 2, y: T, width: bw, height: H - T, style: "fill:transparent" }, s);
      hover(hit, function (box) {
        h("span", "tv", sgn(v, 2) + " HP", box);
        h("div", "tk", "Floor " + (f + 1) + " · " + FLOOR_NAME[type] + " · average HP change in fights it won, after Burning Blood" + (v > 0 ? " (the heal outpaced the damage)" : ""), box);
      });
    });
    el("line", { x1: L, x2: W - R, y1: y(0), y2: y(0), class: "base" }, s);
  }

  // ---------- finding 3: rest tally ----------
  function restTally() {
    var W = 640, H = 64;
    var s = svgIn("rest-tally", W, H, "48 of 50 runs rested, 2 upgraded");
    if (!s) return;
    var cw = (W - 20) / 25;
    for (var i = 0; i < 50; i++) {
      var r = Math.floor(i / 25), c = i % 25;
      var smith = i >= 48;
      el("rect", { x: 10 + c * cw + 1, y: 4 + r * 26, width: cw - 2, height: 22, rx: 4, style: "fill:" + (smith ? "var(--prod)" : "var(--cell-all)") }, s);
    }
    var hit = el("rect", { x: 0, y: 0, width: W, height: H, style: "fill:transparent" }, s);
    hover(hit, function (box) { h("span", "tv", "48 rested · 2 upgraded", box); h("div", "tk", "Choices of the careful chooser at the campfire before the boss, runs 0–49. Order here is a tally, not run order.", box); });
    var host = document.getElementById("rest-tally");
    var lg = h("div", "legend", null, host);
    var a = h("span", null, null, lg); h("i", null, null, a).style.background = "var(--cell-all)"; a.appendChild(document.createTextNode("Rested (48)"));
    var b = h("span", null, null, lg); h("i", null, null, b).style.background = "var(--prod)"; b.appendChild(document.createTextNode("Upgraded a card (2)"));
  }

  // ---------- finding 4: waffle ----------
  var wMode = "three";
  function waffle() {
    if (!S) return;
    var rows = S.sequences; // [i, h, n, p, deathFloor, deathEnc, boss, arrivalHP, picks, pNew]
    var cats = wMode === "three" ? [
      { key: "all", name: "All three clear", color: "var(--cell-all)", f: function (r) { return r[1] && r[2] && r[3]; } },
      { key: "gain", name: "Two-turn clears, another player doesn't", color: "var(--prod)", f: function (r) { return r[3] && !(r[1] && r[2]); } },
      { key: "loss", name: "Two-turn loses, another player clears", color: "var(--net)", f: function (r) { return !r[3] && (r[1] || r[2]); } },
      { key: "none", name: "Nobody clears", color: "var(--cell-none)", f: function (r) { return !r[1] && !r[2] && !r[3]; } }
    ] : [
      { key: "all", name: "Both products clear", color: "var(--cell-all)", f: function (r) { return r[3] && r[9]; } },
      { key: "new", name: "Only the 13 Nov product clears", color: "var(--prod)", f: function (r) { return r[9] && !r[3]; } },
      { key: "old", name: "Only the 3 Nov product clears", color: "var(--net)", f: function (r) { return r[3] && !r[9]; } },
      { key: "none", name: "Both lose", color: "var(--cell-none)", f: function (r) { return !r[3] && !r[9]; } }
    ];
    var ordered = [];
    cats.forEach(function (c) { c.n = 0; rows.forEach(function (r) { if (c.f(r)) { ordered.push([r, c]); c.n++; } }); });
    var cols = 50, cw = 12, gap = 2;
    var W = cols * cw, H = Math.ceil(ordered.length / cols) * cw;
    var s = svgIn("waffle", W, H, "500 runs coloured by who clears them");
    if (!s) return;
    ordered.forEach(function (rc, k) {
      var r = rc[0], c = rc[1];
      var cell = el("rect", { x: (k % cols) * cw + gap / 2, y: Math.floor(k / cols) * cw + gap / 2, width: cw - gap, height: cw - gap, rx: 2, style: "fill:" + c.color }, s);
      cell.addEventListener("pointermove", function (e) {
        tipShow(function (box) {
          h("span", "tv", "Run " + r[0] + (r[6] ? " · " + BOSS[r[6]].name : ""), box);
          h("div", "tk", c.name, box);
          var mk = function (v) { return v ? "cleared" : "lost"; };
          if (wMode === "three") {
            line(box, mk(r[1]), "hand-written, one turn", "var(--heur)");
            line(box, mk(r[2]), "net, one turn", "var(--net)");
            line(box, mk(r[3]), "net, two turns" + (!r[3] && r[5] ? " (died on floor " + r[4] + ")" : ""), "var(--prod)");
          } else {
            line(box, mk(r[3]), "3 Nov product", "var(--net)");
            line(box, mk(r[9]), "13 Nov product", "var(--prod)");
          }
          if (r[8]) h("div", "tk", "Two-turn picks: " + r[8].split("|").join(", "), box);
        }, e.clientX, e.clientY, cell);
      });
      cell.addEventListener("pointerleave", function () { tipHide(cell); });
    });
    var lg = document.getElementById("waffle-legend");
    lg.textContent = "";
    cats.forEach(function (c) { var sp = h("span", null, null, lg); h("i", null, null, sp).style.background = c.color; sp.appendChild(document.createTextNode(c.name + " · " + c.n)); });
  }
  function waffleToggle() {
    var a = document.getElementById("w-three"), b = document.getElementById("w-two");
    if (!a || !b) return;
    function set(m) { wMode = m; a.setAttribute("aria-pressed", String(m === "three")); b.setAttribute("aria-pressed", String(m === "two")); waffle(); }
    a.addEventListener("click", function () { set("three"); });
    b.addEventListener("click", function () { set("two"); });
  }

  // ---------- finding 5: deaths by floor, three players ----------
  function deaths() {
    if (!S) return;
    var P = [["heuristic", "var(--heur)", "Hand-written, one turn"], ["net_one_turn", "var(--net)", "Net, one turn"], ["product", "var(--prod)", "Net, two turns"]];
    var floors = [5, 6, 7, 8, 9, 10];
    var W = 640, H = 282, L = 40, R = 10, T = 24, Bm = 92, max = 140;
    var s = svgIn("deaths", W, H, "Runs that ended on each floor, three players");
    if (!s) return;
    var gw = (W - L - R) / floors.length;
    var y = function (v) { return T + (H - T - Bm) * (1 - v / max); };
    var g = el("g", { class: "grid" }, s);
    [0, 40, 80, 120].forEach(function (v) { el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v) }, g); txt(s, L - 8, y(v) + 4, String(v), { class: "axis", "text-anchor": "end" }); });
    floors.forEach(function (f, gi) {
      var gx = L + gw * gi, bw = Math.min(22, (gw - 18) / 3);
      var type = FLOORS[f];
      P.forEach(function (p, pi) {
        var v = S[p[0]].deaths_by_floor[f];
        var x = gx + gw / 2 - (bw * 3 + 4) / 2 + pi * (bw + 2);
        if (v > 0) el("path", { d: "M" + x + " " + y(0) + " V" + (y(v) + Math.min(4, (y(0) - y(v)))) + " q0 -" + Math.min(4, y(0) - y(v)) + " " + Math.min(4, bw / 2) + " -" + Math.min(4, y(0) - y(v)) + " H" + (x + bw - Math.min(4, bw / 2)) + " q" + Math.min(4, bw / 2) + " 0 " + Math.min(4, bw / 2) + " " + Math.min(4, y(0) - y(v)) + " V" + y(0) + " Z", style: "fill:" + p[1] }, s);
        if (f === 8 || f === 10) txt(s, x + bw / 2, y(v) - 5, String(v), { "text-anchor": "middle", style: "font-size:11.5px;font-weight:700;fill:var(--ink)" });
      });
      if (type === "boss") bosses(s, gx + gw / 2, H - Bm + 44, 34, true); else use(s, ICON[type], gx + gw / 2, H - Bm + 22, 20, type === "elite" ? "var(--gold)" : "var(--ink-2)");
      txt(s, gx + gw / 2, H - 6, (f === 10 ? "Boss" : "Floor " + (f + 1)), { class: "axis", "text-anchor": "middle" });
      var hit = el("rect", { x: gx, y: T, width: gw, height: H - T, style: "fill:transparent" }, s);
      hover(hit, function (box) {
        h("span", "tk", (f === 10 ? "Boss" : "Floor " + (f + 1) + " · " + FLOOR_NAME[type]) + " · runs that ended here, of 500", box);
        P.forEach(function (p) { line(box, String(S[p[0]].deaths_by_floor[f]), p[2], p[1]); });
      });
    });
    el("line", { x1: L, x2: W - R, y1: y(0), y2: y(0), class: "base" }, s);
    txt(s, L, 12, "Floors 1–5: no runs ended there for any player.", { class: "axis" });
  }

  // ---------- finding 6: novelty bars ----------
  function novelty() {
    var rows = [
      ["Deals 20% less damage", -1.01, 0.08, 0],
      ["+1 Strength", 0.01, 0.05, 0],
      ["+2 Strength", 0.16, 0.07, 0],
      ["20% less HP", 0.35, 0.16, 0],
      ["25% more HP", 1.18, 0.15, 0],
      ["Ritual 2: +2 Strength each turn", 2.25, 0.21, 1],
      ["Sharp Hide 2: hurts you per Attack", 6.29, 0.31, 1]
    ];
    var W = 640, H = 34 + rows.length * 30, L = 232, R = 16, T = 10;
    var s = svgIn("novelty", W, H, "The net's HP change per elite fight against the hand-written player, by change");
    if (!s) return;
    rows = rows.map(function (r) { return [r[0], -r[1], r[2], r[3]]; });
    var lo = -8, hi = 2;
    var x = function (v) { return L + (W - L - R) * (v - lo) / (hi - lo); };
    var g = el("g", { class: "grid" }, s);
    [-8, -6, -4, -2, 0, 2].forEach(function (v) { el("line", { x1: x(v), x2: x(v), y1: T, y2: H - 22 }, g); txt(s, x(v), H - 6, (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v) + " HP", { class: "axis", "text-anchor": "middle" }); });
    el("line", { x1: x(0), x2: x(0), y1: T, y2: H - 22, class: "base" }, s);
    rows.forEach(function (r, i) {
      var y = T + 6 + i * 30, bh = 16, color = r[3] ? "var(--prod)" : "var(--heur)";
      txt(s, L - 12, y + 12, r[0], { "text-anchor": "end", style: "font-size:13px;fill:var(--ink-2)" });
      var x0 = x(Math.min(0, r[1])), x1 = x(Math.max(0, r[1]));
      if (x1 - x0 > 1) el("rect", { x: x0, y: y, width: x1 - x0, height: bh, rx: 3, style: "fill:" + color }, s);
      el("line", { x1: x(r[1] - 2 * r[2]), x2: x(r[1] + 2 * r[2]), y1: y + bh / 2, y2: y + bh / 2, style: "stroke:var(--ink);stroke-width:1.5;opacity:.6" }, s);
      var lx = r[1] >= 0 ? Math.max(x1, x(r[1] + 2 * r[2])) + 6 : Math.min(x0, x(r[1] - 2 * r[2])) - 6;
      txt(s, lx, y + 12, sgn(r[1], 2), { "text-anchor": r[1] >= 0 ? "start" : "end", style: "font-size:12.5px;font-weight:700;fill:var(--ink)" });
      var hit = el("rect", { x: 0, y: y - 6, width: W, height: 28, style: "fill:transparent" }, s);
      hover(hit, function (box) {
        h("span", "tv", sgn(r[1], 2) + " HP (se " + r[2].toFixed(2) + ")", box);
        h("div", "tk", r[0] + " on Gremlin Nob, Lagavulin and the Sentries: the net's HP change per fight, on top of what the change does to the hand-written player. " + (r[1] < 0 ? "Negative: the net loses more HP." : "Positive: the net copes better than the hand-written player."), box);
      });
    });
  }

  // ---------- timeline: commits per day ----------
  function commits() {
    var days = [["10-23", 8], ["10-24", 53], ["10-25", 33], ["10-26", 41], ["10-27", 23], ["10-28", 13], ["10-29", 25], ["10-30", 96], ["10-31", 98], ["11-01", 100], ["11-02", 136], ["11-03", 87], ["11-04", 118], ["11-05", 135], ["11-06", 174], ["11-07", 205], ["11-08", 240], ["11-09", 144], ["11-10", 182], ["11-11", 146], ["11-12", 103], ["11-13", 169], ["11-14", 247]];
    var bands = [[0, 1, "The engine"], [2, 5, "Self-play"], [6, 8, "Owner leaves"], [9, 10, "An Act"], [11, 13, "AI roles"], [14, 17, "Real Act 1"], [18, 20, "New nets"], [21, 22, "Real game"]];
    var events = { "10-29": "The owner steps away; the AI-run setup starts (20:46)", "11-02": "First headline number: 0.804", "11-03": "AI roles take over", "11-09": "The owner starts on Act 1 content directly", "11-13": "The game is installed; the bridge is built", "11-14": "Whole real runs from 06:02 to 22:00" };
    var W = 1000, H = 250, L = 40, R = 10, T = 44, Bm = 30, max = 250;
    var s = svgIn("commits", W, H, "Commits per day, 23 October to 14 November");
    if (!s) return;
    var cw = (W - L - R) / days.length;
    var y = function (v) { return T + (H - T - Bm) * (1 - v / max); };
    bands.forEach(function (b, i) {
      var x0 = L + cw * b[0], x1 = L + cw * (b[1] + 1);
      el("rect", { x: x0, y: 4, width: x1 - x0, height: H - Bm - 4, style: "fill:" + (i % 2 ? "var(--bg-2)" : "transparent") + ";opacity:.7" }, s);
      txt(s, x0 + 6, 18, String(i + 1), { style: "font-family:var(--f-display);font-size:15px;font-weight:700;fill:var(--accent)" });
      if (x1 - x0 > 80) txt(s, x0 + 20, 18, b[2], { style: "font-size:11.5px;fill:var(--muted)" });
    });
    var g = el("g", { class: "grid" }, s);
    [0, 100, 200].forEach(function (v) { el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v) }, g); txt(s, L - 8, y(v) + 4, String(v), { class: "axis", "text-anchor": "end" }); });
    days.forEach(function (d, i) {
      var cx = L + cw * (i + 0.5), bw = Math.min(24, cw * 0.62);
      var band = bands.filter(function (b) { return i >= b[0] && i <= b[1]; })[0];
      var bi = bands.indexOf(band);
      el("path", { d: "M" + (cx - bw / 2) + " " + y(0) + " V" + (y(d[1]) + 4) + " q0 -4 4 -4 H" + (cx + bw / 2 - 4) + " q4 0 4 4 V" + y(0) + " Z", style: "fill:" + (i >= 7 ? "var(--prod)" : "var(--heur)") + ";opacity:" + (i === 22 ? .5 : 1) }, s);
      if (events[d[0]]) el("circle", { cx: cx, cy: y(d[1]) - 9, r: 3.5, style: "fill:var(--gold)" }, s);
      if (i % 2 === 0 || i === 22) txt(s, cx, H - 10, d[0].replace("10-", "Oct ").replace("11-", "Nov ").replace(/ 0/, " "), { class: "axis", "text-anchor": "middle", style: "font-size:10.5px" });
      var hit = el("rect", { x: cx - cw / 2, y: 4, width: cw, height: H - 4, style: "fill:transparent" }, s);
      hover(hit, function (box) {
        h("span", "tv", d[1] + " commits", box);
        h("div", "tk", d[0].replace("10-", "October ").replace("11-", "November ").replace(/ 0/, " ") + " · stretch " + (bi + 1) + ": " + band[2], box);
        if (events[d[0]]) h("div", null, events[d[0]], box);
      });
    });
    el("line", { x1: L, x2: W - R, y1: y(0), y2: y(0), class: "base" }, s);
    // owner-away marker
    var ox = L + cw * 6.86;
    el("line", { x1: ox, x2: ox, y1: 26, y2: y(0), style: "stroke:var(--gold);stroke-width:1.5" }, s);
    txt(s, ox + 5, 36, "owner away →", { style: "font-size:11.5px;fill:var(--gold);font-weight:700" });
  }

  // ---------- Act 1 coverage ----------
  function coverage() {
    var host = document.getElementById("coverage");
    if (!host) return;
    var snaps = ["before 6 Nov", "9 Nov", "12 Nov", "14 Nov"];
    var rows = [["Monsters", 25, [18, 25, 25, 25]], ["Ironclad cards", 75, [35, 66, 67, 75]], ["Relics", 141, [0, 0, 52, 82]], ["Potions", 33, [0, 0, 25, 33]]];
    host.textContent = "";
    h("div", "h", "", host);
    snaps.forEach(function (sn) { h("div", "h", sn, host); });
    rows.forEach(function (r) {
      h("div", null, r[0], host).style.color = "var(--ink-2)";
      r[2].forEach(function (v) {
        var c = h("div", "cov-cell", null, host);
        var m = h("div", "meter" + (v === r[1] ? " full" : ""), null, c);
        h("span", null, null, m).style.width = (100 * v / r[1]) + "%";
        h("em", null, v + " / " + r[1], c);
      });
    });
  }

  // ---------- real game ----------
  // Hand-written notes per run, keyed "<record folder>#<run in that folder>"; the fights come from data.js.
  var RUN_NOTES = {
    "20261114-060511#1": {
      title: "Run 1 · started 06:05", outcome: "Died on floor 22 in Act 2",
      died: { floor: 22, monsters: "Centurion + Healer" },
      text: "The first whole run the controller played by itself. The map rule kept it on monster paths, so Act 1 had no elite, and it reached The Guardian with 71 HP. That fight took 15 turns and long thinking, up to 42 seconds a move. While the Guardian attacked, the AI hit back hard: Shockwave on turn 1 for Weak and Vulnerable, then Bash+ and Strikes, and it broke Mode Shift three times. In defensive mode, where Sharp Hide costs 3 HP per Attack, it mostly blocked and used True Grit+ to exhaust Strikes before the next opening. It won at 44 HP (50 after Burning Blood). Act 2 is beyond the engine, so the simple fallback rule fought on and died on floor 22 to a Centurion and a Healer. Relics by then: Ornamental Fan and Runic Pyramid."
    },
    "20261114-062806#2": {
      title: "Run 3 · started 06:47", outcome: "Left at floor 2 by a game restart", left: true,
      text: "The game was restarted to load the morning's fixes, and this run was left on floor 2. It is left out of the counts above."
    },
    "20261114-064924#1": {
      title: "Run 4 · started 06:49",
      text: "Heavier going. A Gremlin Gang on floor 5 took 15 HP, and the map led through three elites: Sentries, Lagavulin, Sentries again. By floor 14 it was down to 36 HP. After the campfire it met Slime Boss with 70 HP and lost 1 HP in the whole fight. A slime splits into two that start with the HP it had when it split, and the AI played to that: it took the Spike Slime (L) down to 1 HP before it split, so the two halves had 1 HP each, and split the Acid Slime (L) low too (3 HP each). It blocked the turns the slimes attacked. All 139 chance-free steps matched the game. Lagavulin went to the fallback rule after 5 engine moves, because Snecko Oil had rolled card costs the engine's picture didn't share (fixed since). Relics on the way: Golden Idol, Centennial Puzzle, Gremlin Horn, Du-Vu Doll, Eternal Feather. In Act 2 the fallback rule beat a Chosen, a Spheric Guardian and a Snake Plant, and died on floor 23 to a Sentry and a Spheric Guardian (score 217)."
    },
    "20261114-064924#2": {
      title: "Run 5 · started 07:14", outcome: "Left at floor 4 by a game restart", left: true,
      text: "The game was restarted again to load fixes, and this run was left on floor 4. It is left out of the counts above."
    },
    "20261114-072137#1": {
      title: "Run 6 · started 07:22",
      text: "The fastest of the morning's runs that got past Act 1: six minutes from Neow to the death screen. The path held no elite, and all 106 chance-free steps matched the game. The Guardian took it from 80 to 43 HP (49 after Burning Blood). The deck by then had Perfected Strike+, Flame Barrier+, Double Tap, two Twin Strikes and Evolve. Its boss relic was Runic Dome, which hides every enemy intent. Without the intents the controller can't rebuild any fight, so even three Cultists on floor 21, monsters the engine knows, went to the fallback rule, and they killed it. The run layer now skips Runic Dome."
    },
    "20261114-072137#2": {
      title: "Run 7 · started 07:28",
      text: "Slime Boss without losing a single HP. On turn 1 the AI played Wild Strike, Perfected Strike, Evolve and Fire Breathing+. From then on every Status card it drew, the Wounds Wild Strike shuffles in and the Slimed from the boss's Goop Spray, drew another card and hit every slime for 10. It split the boss at 41 HP, finished both Large slimes the same way, and was never hit. In Act 2 the fallback rule beat three Byrds, a Chosen and the Centurion and Healer that ended runs 1 and 2, then died on floor 23 to a Gremlin Leader and its gang (score 253)."
    },
    "20261114-074035#1": {
      title: "Run 8 · started 07:40",
      text: "The first loss. The path held two elites: three Sentries took it from 84 to 53 HP and Lagavulin from 58 to 27, and it was down to 20 by floor 12. After the campfire it met The Guardian with 51 HP and a thin deck: four Strikes, four Defends, Bash+, Anger+, Heavy Blade, Clothesline and few other attacks. It played Combust on turn 2, which cost 1 HP on each of the fight's 15 turns, spent several turns upgrading Defends with Armaments, and died with the Guardian on 64 HP. It walked into the Guardian's cliff: on our boss replays that fight is won about half the time from 50 HP."
    },
    "20261114-074750#1": {
      title: "Run 9 · started 07:48",
      text: "No elite on the path, and it walked into The Guardian with 80 HP. It won at 55 (61 after Burning Blood), with all 26 chance-free steps matched. Its boss relic was Pandora's Box, which turns every Strike and Defend into a random card, so its Act 2 deck had none left: two Whirlwinds, two Shockwave+, Immolate, Brutality and more. On floor 29 the engine played three Cultists itself, since they are Act 1 monsters, and won. The fallback rule carried it to floor 31, the deepest run of the day, where a Cultist and a Chosen ended it (score 237)."
    },
    "20261114-074750#2": {
      title: "Run 10 · started 08:01",
      text: "Slime Boss without losing a single HP: it walked in with 62 and walked out with 62 (68 after Burning Blood). Pandora's Box again among its relics. The fallback rule died on floor 21 to a Cultist and a Chosen."
    },
    "20261114-080956#1": {
      title: "Run 11 · started 08:10",
      text: "Not one miss all run: the game matched all 78 chance-free steps. Slime Boss took it from 74 to 39, and Meat on the Bone healed it to 57 afterwards. Act 2 ended on floor 21 against a Shelled Parasite and a Fungi Beast."
    },
    "20261114-081755#1": {
      title: "Run 12 · started 08:18",
      text: "Slime Boss for 4 HP (85 to 81). Its 4 misses came from two quirks it found: Art of War's counter, which the game doesn't show, and Regeneration healing before Combust at the end of a turn. Act 2 ended on floor 22 against a Cultist and a Chosen."
    },
    "20261114-082949#1": {
      title: "Run 13 · started 08:30",
      text: "Three Sentries on floor 6 took it from 80 to 13 HP, the closest call of the day, and it still reached The Guardian with 64 and won at 40. Its boss relic was Black Blood, Burning Blood's upgrade, which heals 12 after each fight. One miss in 172 chance-free steps: a Skill Potion's free Seeing Red. Act 2 ended on floor 21 against a Chosen."
    },
    "20261114-084142#1": {
      title: "Run 14 · started 08:42",
      text: "Three Sentries on floor 8 took it from 76 to 30 HP. It reached The Guardian with 70 and won at 34. Act 2 ended on floor 22 against a Centurion and a Healer."
    },
    "20261114-085507#1": {
      title: "Run 15 · started 08:55",
      text: "No elite on the path. The Guardian from 80 HP, won at 45. Act 2 ended on floor 20 against a Centurion and a Healer."
    },
    "20261114-090728#1": {
      title: "Run 16 · started 09:07",
      text: "The second boss loss, and a controller bug's fault. The Guardian's Sharp Hide hit the AI for 3 just as it played Blood for Blood+. In the game that card is in limbo while the damage lands, so its cost doesn't drop; the engine thought the card was 1 cheaper, and its planned play was refused. The fallback rule took over on turn 4 at 75 HP and lost a fight the engine had well in hand. The controller now reads Blood for Blood's cost from the game, and the engine's rule for a card in limbo is queued for a fix."
    },
    "20261114-090728#2": {
      title: "Run 17 · started 09:13",
      text: "The day's first Hexaghost, after Lagavulin had taken it from 76 to 16 HP on floor 6. It met the Hexaghost with 52. Bronze Scales gave it 3 Thorns, and it played Metallicize+ on turn 1, so every hit of the Hexaghost's multi-hit attacks cost the boss HP. Then it raced the boss's 250 HP in 11 turns with Flex-boosted Strikes, Twin Strikes and Rampage, blocking only as needed, and won at 27. All 33 chance-free steps matched. With this, all three Act 1 bosses have fallen to it at least once. Act 2 ended on floor 21 against a Snake Plant."
    },
    "20261114-112420#1": {
      title: "Run 18 · started 11:24",
      text: "Lagavulin on floor 6 took it from 73 to 42 HP. It reached The Guardian with 78 and won at 47. Act 2 ended on floor 18."
    },
    "20261114-112420#2": {
      title: "Run 19 · started 11:36",
      text: "The closest boss win of the morning: Hexaghost took it from 72 HP down to 7 before it fell. Act 2 ended on floor 21."
    },
    "20261114-112420#3": {
      title: "Run 20 · started 11:42",
      text: "The Guardian for only 8 HP (70 to 62). Act 2 ended on floor 21."
    },
    "20261114-112420#4": {
      title: "Run 21 · started 11:53", outcome: "Stopped by a game restart on floor 18",
      text: "Two elites, Lagavulin and three Sentries, then Hexaghost from 78 HP, won at 29. A game restart stopped the run in its first Act 2 fight."
    },
    "20261114-120336#1": {
      title: "Run 22 · started 12:04",
      text: "Three Sentries took it from 78 to 64 HP, and it reached The Guardian with only 41. It won at 29 (35 after Burning Blood). From this run on, a run stops when Act 2 starts, on purpose."
    },
    "20261114-122134#1": {
      title: "Run 23 · started 12:21",
      text: "Gremlin Nob took it from 80 to 66 HP. The Guardian from 68, won at 40, and Meat on the Bone healed it to 58 afterwards."
    },
    "20261114-124125#1": {
      title: "Run 24 · started 12:41",
      text: "Not one miss on a chance-free step all run. Gremlin Nob cost it 6 HP; Slime Boss from 85, won at 53."
    },
    "20261114-125346#1": {
      title: "Run 25 · started 12:54",
      text: "Not one miss on a chance-free step all run. Lagavulin took it from 71 to 53 HP; The Guardian from 59, won at 46."
    },
    "20261114-130922#1": {
      title: "Run 26 · started 13:09",
      text: "The first Ascension 0 run that never reached the boss. Three Sentries on floor 6 took it from 72 to 19 HP, and the next hallway, two Sneaky Gremlins with a Mad Gremlin and a Gremlin Wizard, killed it on floor 7."
    },
    "20261114-131518#1": {
      title: "Run 27 · started 13:15",
      text: "Lagavulin took it from 88 to 62 HP. Slime Boss cost it nothing: it walked in with 81 HP and ended the fight on 82."
    },
    "20261114-132234#1": {
      title: "Run 28 · started 13:23 · Ascension 20", ascension: 20,
      text: "The first Ascension 20 run: 75 max HP at the start, Ascender's Bane in the deck, and every Act 1 monster with its A20 numbers, moves and AI, which the engine got today from the game's own code. The net never trained against A20 monsters. Gremlin Nob took it from 87 to 43 HP. The Guardian took it from 87 down to 16, and it won. 127 of 130 chance-free steps matched the game; the 3 misses were one bridge case (Anger+ and Rage+ upgraded in the fight, read as free), fixed since, and none came from the ascension rules."
    },
    "20261114-133230#1": {
      title: "Run 29 · started 13:33 · Ascension 20", ascension: 20,
      text: "Not one miss on a chance-free step all run. Gremlin Nob on floor 8 took it from 82 to 51 HP. Hexaghost at A20 took it from 71 down to 14, and it won."
    },
    "20261114-134302#1": {
      title: "Run 30 · started 13:43 · Ascension 20", ascension: 20,
      text: "Lost on floor 7 to Lagavulin, walking in with 44 HP and a deck that was still almost the starter (Sword Boomerang, Wild Strike and Metallicize added). The simple map rule took it into that elite at 44 HP: a weakness of the run rules outside fights, not of the fighter, which matched all 77 chance-free steps."
    },
    "20261114-135010#1": {
      title: "Run 31 · started 13:50 · Ascension 20", ascension: 20,
      text: "Hexaghost at A20 from 73 HP, won at 31, with all 132 chance-free steps matching the game."
    },
    "20261114-135634#1": {
      title: "Run 32 · started 13:57 · Ascension 20", ascension: 20,
      text: "Three Sentries took it from 69 to 24 HP. It reached Slime Boss with 64 HP and a near-starter deck of 14 cards (Perfected Strike, Infernal Blade, Clothesline and Blood for Blood added), and lost."
    },
    "20261114-140235#1": {
      title: "Run 33 · started 14:03 · Ascension 20", ascension: 20, rules: 1,
      text: "Three Sentries on floor 8 cost it 42 HP (50 to 8). On floor 11, at 10 HP, the map offered a rest site or a fight; the old map rule took the fight, and the run died on floor 12. This loss led to run rules 2: below half HP, a rest site first."
    },
    "20261114-140928#1": {
      title: "Run 34 · started 14:10 · Ascension 20", ascension: 20, rules: 1,
      text: "Three Sentries (64 to 39 HP), then floors 11 to 14 spent low, down to 3 HP after three Fungi Beasts, under the old map rule. It met Slime Boss with 49 HP and lost."
    },
    "20261114-141930#1": {
      title: "Run 35 · started 14:20 · Ascension 20", ascension: 20, rules: 2,
      text: "The first run under run rules 2. A clean Act 1, a Gremlin Nob elite and nine hallway fights with all 138 chance-free steps matched, then Hexaghost from 70 HP, and it lost."
    },
    "20261114-142823#1": {
      title: "Run 36 · started 14:28 · Ascension 20", ascension: 20, rules: 2,
      text: "Three Sentries took it from 64 to 24 HP. It reached Slime Boss with 64 and lost."
    },
    "20261114-144115#1": {
      title: "Run 37 · started 14:41 · Ascension 20", ascension: 20, rules: 2,
      text: "Two elites in a row, each the only node the map offered (the map rule looks one node ahead). Gremlin Nob took it from 57 to 6 HP, and Lagavulin finished it on floor 8."
    },
    "20261114-144639#1": {
      title: "Run 38 · started 14:47 · Ascension 20", ascension: 20, rules: 2,
      text: "Gremlin Nob on floor 13 took it from 61 to 30 HP. It lost to The Guardian from 61."
    },
    "20261114-145619#1": {
      title: "Run 39 · started 14:56 · Ascension 20", ascension: 20, rules: 2,
      text: "The first Ascension 20 Slime Boss win, after three losses. Immolate on turn 1, Reaper, then Evolve and Fire Breathing, so every Slimed or Burn card it drew drew another card and hit all the slimes. It walked in with 68 HP and won at 34, every chance-free step matched."
    },
    "20261114-150850#1": {
      title: "Run 40 · started 15:10 · Ascension 20", ascension: 20, rules: 2,
      text: "Lagavulin on floor 13 took it from 48 to 18 HP. The Guardian from 54 HP, won with 8 left."
    },
    "20261114-151903#1": {
      title: "Run 41 · started 15:19 · Ascension 20", ascension: 20, rules: 2,
      text: "Lagavulin (67 to 46 HP), then Slime Boss from 85, won at 33."
    },
    "20261114-152744#1": {
      title: "Run 42 · started 15:28 · Ascension 20", ascension: 20, rules: 2,
      text: "Three Sentries (75 to 50 HP), then The Guardian from 66, won at 37."
    },
    "20261114-153733#1": {
      title: "Run 43 · started 15:38 · Ascension 20", ascension: 20, rules: 2,
      text: "Two elites, three Sentries (78 to 39 HP) and Gremlin Nob (45 to 14). It reached The Guardian with 50 HP and lost."
    },
    "20261114-154828#1": {
      title: "Run 44 · started 15:49 · Ascension 20", ascension: 20, rules: 2,
      text: "Lagavulin on floor 7 took it from 68 to 12 HP. It reached Slime Boss with 66 and won with 3 HP left."
    },
    "20261114-062806#1": {
      title: "Run 2 · started 06:28",
      text: "Neow gave 8 max HP. This time the map led through two elites: three Sentries on floor 6 (88 to 55 HP, all 16 chance-free steps matched the game) and Lagavulin on floor 8 (56 to 52). By floor 11 it was back at 78 HP. The Guardian fell to a Demon Form build: on turn 1 Armaments upgraded Demon Form and it went down, then Disarm and Metallicize. By turn 8 it had 21 Strength, single Strikes and Iron Waves did the rest, and the Guardian's 240 HP were gone on turn 10. It walked in with 83 HP and ended on 61 (67 after Burning Blood). One decision on floor 11 took 111 seconds, the slowest of the day, slowed by a build running beside the game. The deck picked up Demon Form, Metallicize and two Armaments. Bottled Flame and Tiny Chest are relics the engine doesn't load, so they were left out of its picture and recorded. In Act 2 the fallback rule beat a Shelled Parasite, a Spheric Guardian, Byrds with a Chosen and a Snecko, and got to floor 27 on 20 HP, where a Centurion and a Healer ended it (score 256)."
    }
  };
  function realGame() {
    var host = document.getElementById("runs");
    if (!host || !S) return;
    host.textContent = "";
    var RG = S.real_game || { runs: [], empty_folders: 0 };
    var all = RG.runs;
    var skipped = RG.empty_folders;
    // one table per ascension level; the levels' numbers are never pooled
    var asc = function (r) { return (r.run && r.run.ascension) || (RUN_NOTES[r.key] || {}).ascension || 0; };
    var isLeft = function (r) { return !!(RUN_NOTES[r.key] || {}).left; };
    function summarize(runs, box) {
      var fights = [].concat.apply([], runs.map(function (r) { return r.fights; }));
      var sum = function (k) { return fights.reduce(function (a, f) { return a + (f[k] || 0); }, 0); };
      var pred = sum("predicted"), match = sum("matched");
      var played = runs.filter(function (r) { return !isLeft(r); });
      var left = runs.length - played.length;
      var stopped = played.filter(function (r) { return r.run && r.run.stopped; }).length;
      var reached = runs.filter(function (r) { return r.fights.some(function (f) { return f.group === "boss" && f.floor <= 17; }); }).length;
      var beaten = runs.filter(function (r) { return r.fights.some(function (f) { return f.group === "boss" && f.won && f.floor <= 17; }); }).length;
      box.textContent = "";
      [[String(played.length), (played.length === 1 ? "run" : "runs") + " played (" + played.filter(function (r) { return !r.live; }).length + " finished" + (stopped ? ", " + stopped + " stopped at Act 2 on purpose" : "") + (left ? "; " + left + " more left early by a restart" : "") + ")"],
       [beaten + " of " + reached, "Act 1 bosses beaten, of those reached"],
       [fights.filter(function (f) { return f.won; }).length + " / " + fights.length, "recorded fights won"],
       [String(fights.filter(function (f) { return !f.handed_over; }).length), "fights the engine played to the end"],
       [match + " / " + pred, "chance-free steps matched the game (" + (pred ? (100 * match / pred).toFixed(1) : "–") + "%; steps with chance aren't compared)"]].forEach(function (a) {
        var d = h("div", null, null, box); h("b", "num", a[0], d); h("span", null, a[1], d);
      });
      // per boss: beaten of reached, the setting's own fights only
      var BN = { SlimeBoss: "Slime Boss", TheGuardian: "The Guardian", Hexaghost: "Hexaghost" }, per = {};
      runs.forEach(function (r) { r.fights.forEach(function (f) { if (f.group !== "boss" || f.floor > 17) return; var b = BN[(f.monsters || [])[0]] || (f.monsters || [])[0]; per[b] = per[b] || [0, 0]; per[b][1]++; if (f.won) per[b][0]++; }); });
      var names = Object.keys(per).sort();
      if (names.length) { var d = h("div", null, null, box); h("b", "num", names.map(function (b) { return per[b][0] + "/" + per[b][1]; }).join(" · "), d); h("span", null, "by boss: " + names.join(" · ") + ", beaten of reached", d); }
      return [beaten, reached];
    }
    // one table per setting: ascension and the run layer's rules version (1: fights before
    // rest sites at any HP; 2: below half HP a rest site first). Settings are never pooled.
    var rules = function (r) { return (r.run && r.run.run_rules) || (RUN_NOTES[r.key] || {}).rules || 1; };
    // the setting as the bridge reads it (extract.py): ascension, run rules, fight guard
    var setting = function (r, ri) {
      if (r.setting) return r.setting.ascension * 100 + r.setting.rules * 10 + (r.setting.guard ? 1 : 0);
      if (r.live && !r.run && ri > 0) return setting(all[ri - 1], ri - 1);  // a live run has no line yet: its predecessor's setting
      return asc(r) * 100 + rules(r) * 10;
    };
    var RULES = { 1: "run rules 1: fights before rest sites at any HP", 2: "run rules 2: below half HP, a rest site first", 3: "run rules 3: the map looks ahead to the next rest site", 4: "run rules 4: rules 3, and event words match whole words", 5: "run rules 5: rules 4, and elites last again" };
    var levels = [];
    all.forEach(function (r, ri) { var a = setting(r, ri); if (levels.indexOf(a) < 0) levels.push(a); });
    levels.sort(function (a, b) { return a - b; });
    if (!levels.length) levels = [10];
    var stamp = document.getElementById("real-stamp");
    if (stamp && S.written) stamp.textContent = "Ascension 0, run rules 1 · runs 1-27 · records read at " + S.written.slice(11) + " on 14 November";
    var groupHost = {};
    var section = host.parentNode, after = host.nextSibling;  // setting panels go right after the A0 runs, outside any folded list
    // a setting's run cards sit folded under its table, so the page shows the tables first
    function fold(list, n) {
      var det = document.createElement("details");
      det.className = "runs-fold";
      list.parentNode.insertBefore(det, list);
      h("summary", null, n === 1 ? "Show the 1 run in this setting" : "Show all " + n + " runs in this setting", det);
      det.appendChild(list);
    }
    levels.forEach(function (lv) {
      var runs = all.filter(function (r, ri) { return setting(r, ri) === lv; });
      var a = Math.floor(lv / 100), rl = Math.floor(lv / 10) % 10, gd = lv % 10;
      if (lv === 10) {
        var sm = document.getElementById("real-summary");
        var bc = sm ? summarize(runs, sm) : [0, 0];
        var hr = document.getElementById("hero-real");
        if (hr && bc[1]) hr.textContent = bc[0] + " of " + bc[1];
        groupHost[lv] = host;
        fold(host, runs.length);
      } else {
        var panel = h("div", "panel");
        section.insertBefore(panel, after);
        panel.style.marginTop = "26px";
        var ph = h("div", "panel-head", null, panel);
        h("h3", null, "Ascension " + a + ", " + (RULES[rl] || "run rules " + rl) + (gd ? "; fight guard 1" : ""), ph);
        h("span", "panel-note", "Its own table: never pooled with another setting", ph);
        if (gd) h("p", "panel-note", "Fight guard 1: when the search passes over a move that wins the fight outright, the bridge takes that move instead.", panel).style.margin = "0 0 10px";
        if (a === 20 && rl === 1) h("p", "panel-note", "Engine support for ascension was built today from the game's code. The net has never trained against A20 monsters: everything it knows comes from Ascension 0 games.", panel).style.margin = "0 0 10px";
        if (a === 20 && rl === 3) h("p", "panel-note", "Rules 3: the map looks ahead to the next rest site.", panel).style.margin = "0 0 10px";
        if (a === 20 && rl === 4) h("p", "panel-note", "Rules 4: rules 3, and event choices match whole words.", panel).style.margin = "0 0 10px";
        if (a === 20 && rl === 5) h("p", "panel-note", "Rules 5: rules 4, and elites last again on the map.", panel).style.margin = "0 0 10px";
        if (a === 20 && rl === 2) h("p", "panel-note", "From run 35 on, the map takes a rest site first when HP is below half, after run 33 died fighting at 10 HP when it could have rested.", panel).style.margin = "0 0 10px";
        var res = summarize(runs, h("div", "stats-row", null, panel));
        var ha = document.getElementById("hero-real-a20");
        if (ha && a === 20 && rl === 5 && gd && res[1]) { ha.textContent = res[0] + " of " + res[1]; ha.parentNode.parentNode.hidden = false; }
        groupHost[lv] = h("div", "runs", null, panel);
        fold(groupHost[lv], runs.length);
      }
    });
    all.forEach(function (r, ri) {
      var gh = groupHost[setting(r, ri)] || host;
      var lvA = Math.floor(setting(r, ri) / 100);
      var note = RUN_NOTES[r.key] || { title: "Run " + (ri + 1) + (r.run && r.run.started ? " · started " + r.run.started.slice(11, 16) : "") + (lvA ? " · Ascension " + lvA : ""), text: "" };
      var card = h("article", "run", null, gh);
      var head = h("div", "run-head", null, card);
      h("h4", null, note.title, head);
      var bossWon = r.fights.some(function (f) { return f.group === "boss" && f.won && f.floor <= 17; });
      var pills = h("div", null, null, head);
      pills.style.cssText = "display:flex;gap:6px;flex-wrap:wrap";
      if (bossWon) h("span", "pill win", "Act 1 boss beaten", pills);
      if (r.fights.some(function (f) { return f.group === "boss" && !f.won && f.floor <= 17; })) h("span", "pill loss", "Act 1 boss lost", pills);
      var outcome = r.run ? (r.run.victory ? "Won the run" : r.run.stopped ? "Stopped at Act 2, on purpose" : "Died on floor " + r.run.floor + " in Act " + r.run.act) : (note.outcome || "finished");
      h("span", r.live ? "pill live" : "pill", r.live ? "live · " + r.status : outcome, pills);
      var rp = r.fights.reduce(function (a, f) { return a + (f.predicted || 0); }, 0);
      var rm = r.fights.reduce(function (a, f) { return a + (f.matched || 0); }, 0);
      var maxFloor = Math.max(note.died ? note.died.floor : 0, r.fights.reduce(function (a, f) { return Math.max(a, f.floor); }, 0));
      var st = h("div", "stats-row", null, card);
      [[String(maxFloor), "highest floor"], [r.fights.filter(function (f) { return f.won; }).length + " / " + r.fights.length, "recorded fights won"], [rm + " / " + rp, "chance-free steps matched the game"], [String(r.fights.filter(function (f) { return f.handed_over; }).length), "fights left to the fallback rule"]].forEach(function (a) {
        var d = h("div", null, null, st); h("b", "num", a[0], d); h("span", null, a[1], d);
      });
      // who played which fight, in words
      var full = r.fights.filter(function (f) { return !f.handed_over; }).map(function (f) { return f.floor; });
      var part = r.fights.filter(function (f) { return f.handed_over && f.decisions > 0; });
      var fb = r.fights.filter(function (f) { return f.handed_over && !(f.decisions > 0); });
      var pretty = function (m) { return m.replace(/_[SML]$/, "").replace(/([a-z])([A-Z])/g, "$1 $2"); };
      var why = function (f) {
        var s0 = f.handed_over || "", mons = f.monsters.map(pretty).join(" + ");
        var moves = "after " + f.decisions + " engine move" + (f.decisions === 1 ? "" : "s");
        if (/not in the game's hand/.test(s0) && !/cost=/.test(s0)) return "floor " + f.floor + " (" + moves + ": the engine's card didn't match the game's)";
        if (/cost=/.test(s0) && /not in the game's hand/.test(s0)) return "floor " + f.floor + " (" + moves + ": Snecko Oil had rolled costs the engine didn't share)";
        if (/no pick here/.test(s0)) return "floor " + f.floor + " (" + moves + ": a card choice its plan didn't cover)";
        if (f.decisions > 0) return "floor " + f.floor + " (" + moves + ": " + s0 + ")";
        return "floor " + f.floor + " (" + mons + (f.floor > 17 ? ", Act 2" : "") + (f.won ? "" : ", lost") + ")";
      };
      var who = h("p", null, null, card);
      who.style.cssText = "font-size:14px;color:var(--ink-2)";
      var addPart = function (label, text) { if (!text) return; var b = h("b", null, label + " ", who); b.style.color = "var(--ink)"; who.appendChild(document.createTextNode(text + ". ")); };
      addPart("The engine played to the end:", full.length ? "floors " + full.join(", ") : "");
      addPart("Engine, then the fallback rule:", part.map(why).join("; "));
      addPart("The fallback rule only:", fb.map(why).concat(note.died ? ["floor " + note.died.floor + " (" + note.died.monsters + ", where it died)"] : []).join("; "));
      // strip: HP before and after each fight, by floor
      var W = 1000, H = 196, L = 40, R = 20;
      var hallSeen = {};
      var holder = h("div", "chart", null, card);
      var s = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "HP through the run's fights" }, holder);
      var last = Math.max(17, maxFloor);
      var top = r.fights.reduce(function (a, f) { return Math.max(a, f.hp_start, f.hp_end, f.hp_after || 0); }, 80);
      var x = function (fl) { return L + (W - L - R) * (fl - 1) / (last - 1); };
      var y = function (hp) { return 24 + 80 * (1 - hp / top); };
      var g = el("g", { class: "grid" }, s);
      [0, 40, 80].forEach(function (v) { el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v) }, g); txt(s, L - 8, y(v) + 4, String(v), { class: "axis", "text-anchor": "end" }); });
      var ax = (x(16) + x(17)) / 2;
      el("line", { x1: ax, x2: ax, y1: 8, y2: 118, style: "stroke:var(--line-2);stroke-width:1" }, s);
      txt(s, ax - 6, 14, "Act 1", { class: "axis", "text-anchor": "end" });
      if (last > 17) txt(s, ax + 6, 14, "Act 2", { class: "axis" });
      r.fights.forEach(function (f) {
        var x0 = x(f.floor);
        el("line", { x1: x0, x2: x0, y1: y(f.hp_start), y2: y(f.hp_end), style: "stroke:var(--prod);stroke-width:2;stroke-linecap:round" }, s);
        el("circle", { cx: x0, cy: y(f.hp_end), r: 4.5, style: "fill:var(--prod);stroke:var(--surface);stroke-width:2" }, s);
        if (f.won && f.hp_after !== null && f.hp_after !== undefined && f.hp_after > f.hp_end) el("path", { d: "M" + (x0 + 6) + " " + y(f.hp_end) + " V" + y(f.hp_after) + " h5", style: "fill:none;stroke:var(--slime);stroke-width:1.5" }, s);
        // the game draws an act's first normal fights from its easy pool: 3 in Act 1, 2 after
        var act = f.floor <= 17 ? 1 : f.floor <= 34 ? 2 : 3;
        if (f.group === "hallway") hallSeen[act] = (hallSeen[act] || 0) + 1;
        var type = f.group === "boss" ? "boss" : f.group === "elite" ? "elite" : (hallSeen[act] <= (act === 1 ? 3 : 2) ? "easy" : "hard");
        var bossIcon = { SlimeBoss: "i-boss-slime", TheGuardian: "i-boss-guardian", Hexaghost: "i-boss-hexaghost" }[(f.monsters || [])[0]];
        var fall = !!f.handed_over;
        var big = type === "boss" && bossIcon;
        var ic = big ? use(s, bossIcon, x0, 146, 52, fall ? "var(--muted)" : BOSS_ICON.filter(function (b) { return b[0] === bossIcon; })[0][1])
                     : use(s, ICON[type], x0, 146, 22, fall ? "var(--muted)" : (type === "elite" ? "var(--gold)" : "var(--ink-2)"));
        if (fall) ic.style.opacity = ".5";
        txt(s, x0, 190, String(f.floor), { class: "axis", "text-anchor": "middle", style: "font-size:10.5px" });
        var hit = el("rect", { x: x0 - 14, y: 0, width: 28, height: H, style: "fill:transparent" }, s);
        hover(hit, function (box) {
          h("span", "tv", "Floor " + f.floor + " · " + f.monsters.join(", "), box);
          line(box, f.hp_start + " → " + f.hp_end + (f.hp_after !== null && f.hp_after !== undefined && f.hp_after !== f.hp_end ? " (" + f.hp_after + " after)" : ""), f.won ? "HP at the start and end, won" : "HP at the start and end, lost");
          var after = (f.won && f.hp_after !== null && f.hp_after !== undefined) ? f.hp_after : f.hp_end;
          line(box, sgn(after - f.hp_start, 0) + " HP", "HP change" + (after !== f.hp_end ? ", after the end-of-fight heal" : ""));
          if (f.decisions) line(box, String(f.decisions), "decisions by the engine");
          if (f.predicted) line(box, f.matched + " / " + f.predicted, "chance-free steps matched the game");
          if (f.think_max !== null && f.think_max !== undefined) line(box, f.think_max + " s", "longest think");
          if (f.handed_over) h("div", "tk", "Fallback: " + f.handed_over, box);
          if (f.left_out && f.left_out.length) h("div", "tk", "Left out: " + f.left_out.join(", "), box);
        });
      });
      if (note.died) {
        var dx = x(note.died.floor);
        el("path", { d: "M" + (dx - 7) + " " + (y(0) - 7) + " L" + (dx + 7) + " " + (y(0) + 7) + " M" + (dx + 7) + " " + (y(0) - 7) + " L" + (dx - 7) + " " + (y(0) + 7), style: "stroke:var(--prod);stroke-width:2.5;stroke-linecap:round" }, s);
        txt(s, dx, 190, String(note.died.floor), { class: "axis", "text-anchor": "middle", style: "font-size:10.5px" });
        var dh = el("rect", { x: dx - 14, y: 0, width: 28, height: H, style: "fill:transparent" }, s);
        hover(dh, function (box) { h("span", "tv", "Floor " + note.died.floor + " · " + note.died.monsters, box); h("div", "tk", "Died here, fought by the fallback rule. A death-screen bug kept this fight out of the record.", box); });
      }
      if (note.text) h("p", null, note.text, card);
    });
    var nt = document.getElementById("real-note");
    if (nt) nt.textContent = all.length ? ("Updated as runs finish. Bright icons: fights the engine played; faded grey: fights left to the fallback rule, which plays the first playable card on the first living monster." + (skipped ? " One earlier session at 05:53 stopped before its first fight." : "")) : "The first real runs are in progress.";
  }

  function run(f) { try { f(); } catch (e) { if (window.console) console.error(e); } }
  [heroStrip, contentRows, tree, bossCurve, bossBars, hpLoss, restTally, waffle, waffleToggle, deaths, novelty, commits, coverage, realGame].forEach(run);
})();
