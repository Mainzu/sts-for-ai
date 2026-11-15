"""Write showcase/llms.md and llms-full.md: the showcase page as plain Markdown for LLM readers.

llms.md is the page itself; llms-full.md adds every real-game fight, the whole
"everything tried" list and the statistics tab's settings and data.

The page (index.html) shows much of its content as charts, hover tips and folded
lists drawn by JavaScript. This script keeps the page's prose (index.html, as
Markdown), puts every setting tag's hover text inline, and replaces each chart
with the numbers it draws, read from the same data the page loads: data.js,
tried.js, history.js, stats-data.js, and the literals inside app.js and story.js
(Node evaluates them, so nothing here is copied by hand).

    python showcase/llm.py             # writes showcase/llms.md and llms-full.md
    python showcase/llm.py --check     # exits 1 if either file is stale

It only reads the showcase files and writes those two files; rerun it after any page edit.
"""
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTS = {False: HERE / "llms.md", True: HERE / "llms-full.md"}

# ---------------------------------------------------------------- data

# Literals the page keeps inside its scripts: [file, anchor text, variable name].
LITERALS = [
    ["app.js", "function contentRows", "rows"], ["app.js", "function novelty", "rows"],
    ["app.js", "function commits", "days"], ["app.js", "function commits", "bands"],
    ["app.js", "function commits", "events"], ["app.js", "function coverage", "snaps"],
    ["app.js", "function coverage", "rows"], ["app.js", "function bossBars", "notes"],
    ["app.js", "var RUN_NOTES", "RUN_NOTES"], ["app.js", "function realGame", "RULES"],
    ["app.js", "var FLOORS", "FLOORS"], ["story.js", "var STRETCHES", "STRETCHES"],
    ["story.js", "var KINDS", "KINDS"], ["story.js", "var OUT", "OUT"],
]

DUMP_JS = r"""
global.window = {};
const fs = require('fs'), vm = require('vm'), dir = process.argv[1];
for (const f of ['data.js', 'tried.js', 'history.js', 'stats-data.js']) require(dir + '/' + f);
const lits = JSON.parse(process.argv[2]), L = {};
for (const [file, anchor, name] of lits) {
  const src = fs.readFileSync(dir + '/' + file, 'utf8');
  let i = src.indexOf(anchor); if (i < 0) throw new Error('no ' + anchor);
  i = src.indexOf('var ' + name + ' =', i); if (i < 0) throw new Error('no ' + name + ' after ' + anchor);
  let s = src.indexOf('=', i) + 1; while (/\s/.test(src[s])) s++;
  const open = src[s], close = open === '[' ? ']' : '}';
  let d = 0, e = s, q = null;
  for (; e < src.length; e++) {
    const c = src[e];
    if (q) { if (c === '\\') e++; else if (c === q) q = null; continue; }
    if (c === '"' || c === "'") q = c;
    else if (c === open) d++;
    else if (c === close && !--d) break;
  }
  L[anchor + '/' + name] = vm.runInNewContext('(' + src.slice(s, e + 1) + ')');
}
process.stdout.write(JSON.stringify({S: window.SHOWCASE, H: window.HISTORY, STATS: window.STATS, L}));
"""


def load():
    r = subprocess.run(["node", "-e", DUMP_JS, str(HERE), json.dumps(LITERALS)],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(r.stderr)
    d = json.loads(r.stdout)
    short = {"function contentRows/rows": "contentRows.rows", "function novelty/rows": "novelty.rows",
             "function coverage/snaps": "coverage.snaps", "function coverage/rows": "coverage.rows"}
    d["L"] = {short.get(k, k.split("/")[-1]): v for k, v in d["L"].items()}
    return d


# ---------------------------------------------------------------- html -> markdown

SKIP = {"script", "style", "svg", "dialog", "button", "template"}


class ToMd(HTMLParser):
    """A small HTML to Markdown pass over the page body. Elements with an id in
    `fills` become {{FILL:id}} markers; legends (colour keys) are dropped."""

    def __init__(self, fills):
        super().__init__(convert_charrefs=True)
        self.out, self.fills, self.skip = [], fills, []
        self.lists, self.spans = [], []

    def w(self, s):
        self.out.append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if self.skip:
            if tag not in ("br", "img", "input", "use", "i"): self.skip.append(tag)
            return
        if tag in SKIP or "legend" in cls:
            self.skip.append(tag); return
        if a.get("id") in self.fills:
            self.w("\n\n{{FILL:%s}}\n\n" % a["id"])
        if "tried-sum" in cls:
            self.w("\n\n{{SUM:%s:%s}}\n\n" % (a["data-from"], a["data-to"]))
        if tag in ("h1", "h2", "h3", "h4", "h5"):
            self.w("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "div", "section", "figure", "details", "summary", "dd", "dt", "article"):
            self.w("\n\n")
        elif tag in ("ul", "ol"):
            self.lists.append([tag, 0]); self.w("\n")
        elif tag == "li":
            k, n = self.lists[-1] if self.lists else ["ul", 0]
            if self.lists: self.lists[-1][1] += 1
            self.w("\n" + "  " * max(0, len(self.lists) - 1) + ("%d. " % (n + 1) if k == "ol" else "- "))
        elif tag == "br": self.w("\n")
        elif tag in ("b", "strong"): self.w("**")
        elif tag in ("em",): self.w("*")
        elif tag == "code": self.w("`")
        if tag == "span":
            if "tag" in cls:
                self.w(" [setting: "); self.spans.append("]" if not a.get("data-tip") else " | " + a["data-tip"] + "]")
            else:
                if "pn" in cls: self.w("Stretch ")
                self.spans.append("\x00")  # a boundary: tidy() puts " · " where two spans' text would touch
        if tag == "a" and a.get("href", "").startswith("http"):
            self.spans.append(None); self._href = a["href"]

    def handle_endtag(self, tag):
        if self.skip:
            if tag in ("br", "img", "input", "use", "i"): return
            self.skip.pop(); return
        if tag in ("b", "strong"): self.w("** ")
        elif tag == "em": self.w("*")
        elif tag == "code": self.w("`")
        elif tag in ("ul", "ol"):
            if self.lists: self.lists.pop()
            self.w("\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "p", "li", "summary", "dt", "dd"): self.w("\n")
        elif tag == "span" and self.spans:
            self.w(self.spans.pop() or "")
        elif tag == "a" and getattr(self, "_href", None):
            self.w(" (" + self._href + ")"); self._href = None

    def handle_data(self, d):
        if not self.skip:
            self.w(re.sub(r"\s+", " ", d))


def tidy(md):
    md = re.sub("(?<=[^\\s–—-])\x00+(?=[\\w+\u2212(*])", " · ", md).replace("\x00", "")
    md = re.sub(r"(?<=\S)  +", " ", md)
    md = re.sub(r"\*\*\s*\*\* ?", "", md)
    md = re.sub(r"\*\* +([.,:;)])", r"**\1", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n[ \t]+(?=[^\s\-\d])", "\n", md)
    # instructions for the mouse mean nothing here
    md = md.replace("Hover or tap any tag like this one for the full setting", "FULL-SETTING-EXAMPLE")
    md = re.sub(r"\| FULL-SETTING-EXAMPLE: ([^\]]*?)\.?\]", r"| the full setting: \1]", md)
    md = re.sub(r" ?(Hover|Click)[^.]*\.", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


# ---------------------------------------------------------------- tables

def table(head, rows):
    t = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    t += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(t)


def f3(x): return "–" if x is None else "%.3f" % x
def sg(x, d=1): return ("+" if round(x, d) > 0 else "") + ("%.*f" % (d, x)).replace("-", "−")


def day_index(md):
    m, d = (int(x) for x in md.split("-"))
    return d - 23 if m == 10 else 8 + d


def fmt_date(md):
    m, d = md.split("-")
    return "%d %s" % (int(d), "Oct" if m == "10" else "Nov")


BOSS = {"slime_boss": "Slime Boss", "the_guardian": "The Guardian", "hexaghost": "Hexaghost"}
FLOOR_NAME = {"easy": "Easy hallway", "hard": "Hard hallway", "elite": "Elite", "boss": "Boss"}


class Page:
    def __init__(self, d, full):
        self.full = full
        self.S, self.H, self.STATS, self.L = d["S"], d["H"], d["STATS"], d["L"]
        self.items = self.tried_items()

    # every thing tried, as story.js builds it
    def tried_items(self):
        out = []
        for i, t in enumerate(self.H.get("tried", [])):
            dd = (t.get("date") or "")[5:]
            if not dd: continue
            out.append(dict(id="t%d" % i, date=dd, end=(t.get("end") or t["date"])[5:], title=t["title"],
                            kind=t["kind"], outcome=t["outcome"], text=t["sentence"], who=t.get("who"),
                            source=t.get("source"), lane=False))
        for l in self.H.get("lanes", []):
            out.append(dict(id="l-" + l["name"], date=l["open"], end=l["close"], title="Lane " + l["name"],
                            kind=l["kind"], outcome=l["outcome"], text=l["text"], who="ai", lane=True,
                            pred=l.get("pred"), cpu=l.get("cpu")))
        for l in self.H.get("openLanes", []):
            out.append(dict(id="l-" + l["name"], date=l["open"], end="11-14", title="Lane %s (open)" % l["name"],
                            kind=l["kind"], outcome="open", text=l["text"], who="ai", lane=True))
        out.sort(key=lambda t: (day_index(t["date"]), day_index(t["end"])))
        return out

    def outcome_name(self, o):
        return self.L["OUT"][o]["name"] if o in self.L["OUT"] else "Still open"

    def counts(self, mine):
        c = {}
        for t in mine: c[t["outcome"]] = c.get(t["outcome"], 0) + 1
        return ", ".join("%s %d" % (self.outcome_name(k), c[k])
                         for k in ["worked", "failed", "mixed", "built", "dropped", "open"] if c.get(k))

    def in_range(self, t, a, b):
        return day_index(a) <= day_index(t["date"]) <= day_index(b)

    def summary(self, a, b):
        mine = [t for t in self.items if self.in_range(t, a, b)]
        n = [i + 1 for i, s in enumerate(self.L["STRETCHES"]) if s[0] == a][0]
        return "**%d things tried in this stretch:** %s. (Every one is listed under \"Everything tried\", stretch %d.)" % (
            len(mine), self.counts(mine), n)

    # ---- charts, in page order
    def fill(self, cid):
        f = getattr(self, "c_" + cid.replace("-", "_"), None)
        return f() if f else ""

    def c_tried_timeline(self):
        rows = []
        for i, s in enumerate(self.L["STRETCHES"]):
            mine = [t for t in self.items if self.in_range(t, s[0], s[1])]
            rows.append([i + 1, s[2], fmt_date(s[0]) + " to " + fmt_date(s[1]), len(mine), self.counts(mine)])
        return ("Chart (timeline of every thing tried; here as counts per stretch, %d in all):\n\n" % len(self.items)
                + table(["Stretch", "Name", "Dates", "Things tried", "Outcomes"], rows))

    def c_commits(self):
        bands, ev = self.L["bands"], self.L["events"]
        rows = []
        for i, (dd, n) in enumerate(self.L["days"]):
            b = [k for k, x in enumerate(bands) if x[0] <= i <= x[1]][0]
            rows.append([fmt_date(dd), n, "%d (%s)" % (b + 1, bands[b][2]), "AI roles day to day" if i >= 7 else "owner at the desk", ev.get(dd, "")])
        return "Chart data (commits per day; from the evening of 29 Oct the AI roles ran the day-to-day while the owner was mostly away; 14 Nov was still in progress):\n\n" + \
            table(["Day", "Commits", "Stretch", "Who ran the day", "Event"], rows)

    def c_coverage(self):
        snaps = self.L["coverage.snaps"]
        return table(["Content", "Total in Act 1"] + snaps,
                     [[r[0], r[1]] + ["%d / %d" % (v, r[1]) for v in r[2]] for r in self.L["coverage.rows"]])

    def c_calibration(self):
        lanes, rows = self.H["lanes"], []
        for key, name in [["likely", "Rated likely"], ["even", "Rated even"], ["long shot", "Rated a long shot"]]:
            ls = [l for l in lanes if l.get("pred") == key]
            by = {o: [l["name"] for l in ls if l["outcome"] == o] for o in ["worked", "built", "mixed", "failed"]}
            rows.append([name, len(ls)] + ["%d (%s)" % (len(by[o]), ", ".join(by[o])) if by[o] else "0" for o in by]
                        + ["%d of %d" % (len(by["worked"]) + len(by["built"]), len(ls))])
        return "Chart data (closed lanes by the chance they gave themselves before running):\n\n" + \
            table(["Prediction", "Lanes", "Worked", "Built", "Partly", "Didn't work", "Worked or built"], rows)

    def c_cpu_scatter(self):
        pts = [l for l in self.H["lanes"] if l.get("cpu") and l["cpu"][0] and l["cpu"][1]]
        pts.sort(key=lambda l: l["cpu"][1] / l["cpu"][0])
        return "Chart data (CPU-hours each lane estimated against what it used, %d lanes, sorted by ratio):\n\n" % len(pts) + \
            table(["Lane", "Estimated", "Used", "Used / estimated", "Outcome"],
                  [[l["name"], l["cpu"][0], l["cpu"][1], "%.1fx" % (l["cpu"][1] / l["cpu"][0]), self.outcome_name(l["outcome"])] for l in pts])

    def c_machine_use(self):
        return "Chart data (thread-hours of queued work per day, by the day each job ended; 14 Nov was a partial day):\n\n" + \
            table(["Day", "Thread-hours", "Jobs ended", "Share of the machine"],
                  [[fmt_date(p[0]), round(p[1]), p[2], "%d%%" % round(100 * p[1] / 384)] for p in self.H["machine"]])

    def c_content_rows(self):
        names = ["Hand-written, one turn", "Net, one turn", "Net, two turns (product)"]
        rows = []
        for r in self.L["contentRows.rows"]:
            cells = []
            for (a, b) in r["v"]:
                cells.append(f3(b) if a is None else "%s (usual test %s, %s)" % (f3(b), f3(a), sg(b - a, 3)))
            rows.append([r["name"], "%s | %s" % (r["tag"], r["tip"])] + cells)
        return "Chart data (clears; each row is its own read, compare within a row only):\n\n" + \
            table(["Content", "Setting"] + names, rows)

    def c_hero_strip(self):
        P, F = self.S["product"], self.L["FLOORS"]
        rows = [[f + 1, FLOOR_NAME[F[f]], "%.1f" % P["mean_hp_start"][f], sg(-P["mean_hp_lost_won"][f], 1), P["deaths_by_floor"][f]]
                for f in range(11)]
        rows.insert(10, ["campfire", "Rest: heals 30% of max HP (24 of 80)", "", "", ""])
        return ("Chart data (the product, %d runs, %d cleared; HP walking in is the mean over runs still alive; "
                "HP change is the mean over fights it won, after Burning Blood's heal of 6):\n\n" % (P["n"], P["clears"])) + \
            table(["Floor", "Fight", "Mean HP walking in", "HP change when won", "Runs that ended here"], rows)

    def c_boss_curve(self):
        bc = self.S["boss_curve"]
        rows = [[BOSS.get(k, "All three (pooled)"), bc["fights"].get(k, bc["decks"])] + [f3(v) for v in bc["curves"][k]]
                for k in ["slime_boss", "the_guardian", "hexaghost", "pooled"]]
        return "Chart data (chance to beat the boss by HP walking in; %d replayed fights over %d decks):\n\n" % (
            bc["replayed_fights"], bc["decks"]) + table(["Boss", "Decks"] + ["%d HP" % h for h in bc["hp"]], rows)

    def c_boss_bars(self):
        a, b, notes = self.S["product"]["boss"], self.S["product_b"]["boss"], self.L["notes"]
        rows = []
        for k in ["slime_boss", "the_guardian", "hexaghost"]:
            arr, win = a[k][0] + b[k][0], a[k][1] + b[k][1]
            rows.append([BOSS[k], arr, win, f3(win / arr), notes[k]])
        return table(["Boss", "Arrivals", "Won", "Win rate", "Note"], rows)

    def c_hp_loss(self):
        P, F = self.S["product"]["mean_hp_lost_won"], self.L["FLOORS"]
        return "Chart data:\n\n" + table(["Floor", "Fight", "Mean HP change per won fight"],
                                         [[f + 1, FLOOR_NAME[F[f]], sg(-P[f], 2)] for f in range(11)])

    def c_rest_tally(self):
        return "Chart data: of 50 runs (0–49), the careful chooser rested in 48 and upgraded a card in 2."

    def c_waffle(self):
        rows = self.S["sequences"]  # [i, heuristic, net, product, deathFloor, deathEnc, boss, arrivalHP, picks, product 13 Nov]
        three = [("All three clear", lambda r: r[1] and r[2] and r[3]),
                 ("Two-turn product clears, another player doesn't", lambda r: r[3] and not (r[1] and r[2])),
                 ("Two-turn product loses, another player clears", lambda r: not r[3] and (r[1] or r[2])),
                 ("Nobody clears", lambda r: not r[1] and not r[2] and not r[3])]
        two = [("Both products clear", lambda r: r[3] and r[9]), ("Only the 13 Nov product clears", lambda r: r[9] and not r[3]),
               ("Only the 3 Nov product clears", lambda r: r[3] and not r[9]), ("Both lose", lambda r: not r[3] and not r[9])]
        out = ["Chart data (each of the %d runs coloured by who clears it). View \"Three players\" (hand-written one turn, net one turn, product two turns):" % len(rows), "",
               table(["Category", "Runs"], [[n, sum(1 for r in rows if f(r))] for n, f in three]), "",
               "View \"Two products\" (3 Nov product against 13 Nov product):", "",
               table(["Category", "Runs"], [[n, sum(1 for r in rows if f(r))] for n, f in two])]
        diff = [r for r in rows if r[3] != r[9]]
        out += ["", "The runs where the two products differ: " + "; ".join(
            "run %d %s" % (r[0], "only 13 Nov clears" if r[9] else "only 3 Nov clears") for r in diff) + "."]
        return "\n".join(out)

    def c_deaths(self):
        F, P = self.L["FLOORS"], ["heuristic", "net_one_turn", "product"]
        rows = [["Boss" if f == 10 else "%d (%s)" % (f + 1, FLOOR_NAME[F[f]])] + [self.S[p]["deaths_by_floor"][f] for p in P]
                for f in range(5, 11)]
        rows.append(["Cleared (of 500)"] + [self.S[p]["clears"] for p in P])
        return "Chart data (runs that ended on each floor; floors 1–5 had none for any player):\n\n" + \
            table(["Floor", "Hand-written, one turn", "Net, one turn", "Net, two turns"], rows)

    def c_novelty(self):
        return "Chart data (the net's HP change per elite fight on top of what the change does to the hand-written player; negative = the net loses more; se = standard error):\n\n" + \
            table(["Change to the official elites", "Kind", "Net's HP change", "se"],
                  [[r[0], "new mechanic" if r[3] else "number change", sg(-r[1], 2), "%.2f" % r[2]] for r in self.L["novelty.rows"]])

    def c_stat_groups(self): return self.stats()
    def c_tried_groups(self): return self.everything()

    def c_tree(self):
        return ""  # an illustration of the steps listed next

    # ---- the real game
    def setting(self, runs, ri):
        r = runs[ri]
        if r.get("setting"):
            s = r["setting"]; return (s["ascension"], s["rules"], 1 if s.get("guard") else 0)
        if r.get("live") and not r.get("run") and ri > 0: return self.setting(runs, ri - 1)
        note = self.L["RUN_NOTES"].get(r["key"], {})
        return ((r.get("run") or {}).get("ascension") or note.get("ascension") or 0,
                (r.get("run") or {}).get("run_rules") or note.get("rules") or 1, 0)

    def c_runs(self):
        runs, notes, RULES = self.S["real_game"]["runs"], self.L["RUN_NOTES"], self.L["RULES"]
        levels = sorted({self.setting(runs, i) for i in range(len(runs))})
        out = ["Per-run data from the bridge's records (read %s on 14 November). Each setting (ascension, run rules, fight guard) "
               "is its own table and is never pooled with another. A fight \"left to the fallback rule\" was played by a simple rule "
               "(first playable card on the first living monster), not by the AI. Floors above 17 are Act 2, which the engine does not model; "
               "from run 22 on a run stops when Act 2 starts, on purpose, and those endings are not deaths." % self.S["written"][11:]]
        for lv in levels:
            mine = [(i, r) for i, r in enumerate(runs) if self.setting(runs, i) == lv]
            a, rl, gd = lv
            if lv != (0, 1, 0):  # the page's own heading names the first setting
                out.append("\n### Setting: Ascension %d, %s%s\n" % (a, RULES.get(str(rl), "run rules %d" % rl), "; fight guard 1" if gd else ""))
            if gd: out.append("Fight guard 1: when the search passes over a move that wins the fight outright, the bridge takes that move instead.\n")
            if a == 20 and rl == 1: out.append("The net has never trained against A20 monsters: everything it knows comes from Ascension 0 games.\n")
            out.append("\n" + self.real_summary([r for _, r in mine]) + "\n")
            for i, r in mine:
                out.append(self.run_card(i, r, notes.get(r["key"])))
        return "\n".join(out)

    def boss_tally(self, runs):
        BN = {"SlimeBoss": "Slime Boss", "TheGuardian": "The Guardian", "Hexaghost": "Hexaghost"}
        per = {}
        for r in runs:
            for f in r["fights"]:
                if f["group"] != "boss" or f["floor"] > 17: continue
                b = BN.get((f.get("monsters") or [""])[0], (f.get("monsters") or [""])[0])
                per.setdefault(b, [0, 0]); per[b][1] += 1; per[b][0] += bool(f["won"])
        return per

    def real_summary(self, runs):
        notes = self.L["RUN_NOTES"]
        fights = [f for r in runs for f in r["fights"]]
        left = [r for r in runs if notes.get(r["key"], {}).get("left")]
        played = [r for r in runs if r not in left]
        stopped = sum(1 for r in played if (r.get("run") or {}).get("stopped"))
        reached = sum(1 for r in runs if any(f["group"] == "boss" and f["floor"] <= 17 for f in r["fights"]))
        beaten = sum(1 for r in runs if any(f["group"] == "boss" and f["won"] and f["floor"] <= 17 for f in r["fights"]))
        pred, match = sum(f.get("predicted") or 0 for f in fights), sum(f.get("matched") or 0 for f in fights)
        per = self.boss_tally(runs)
        rows = [["Runs played", "%d (%d finished%s%s)" % (len(played), sum(1 for r in played if not r.get("live")),
                                                           ", %d stopped at Act 2 on purpose" % stopped if stopped else "",
                                                           "; %d more left early by a restart" % len(left) if left else "")],
                ["Act 1 bosses beaten, of those reached", "%d of %d" % (beaten, reached)],
                ["By boss (beaten of reached)", "; ".join("%s %d/%d" % (b, *per[b]) for b in sorted(per))],
                ["Recorded fights won", "%d / %d" % (sum(1 for f in fights if f["won"]), len(fights))],
                ["Fights the engine played to the end", sum(1 for f in fights if not f.get("handed_over"))],
                ["Chance-free steps matched the game", "%d / %d (%s%%; steps with chance aren't compared)" % (
                    match, pred, "%.1f" % (100 * match / pred) if pred else "–")]]
        return table(["Summary", "Value"], rows)

    def run_card(self, i, r, note):
        if not self.full: return self.run_line(i, r, note)
        run = r.get("run") or {}
        note = note or {"title": self.default_title(i, r), "text": ""}
        fights = r["fights"]
        outcome = ("Won the run" if run.get("victory") else "Stopped at Act 2, on purpose" if run.get("stopped")
                   else "Died on floor %s in Act %s" % (run.get("floor"), run.get("act"))) if run else note.get("outcome", "finished")
        pills = []
        if any(f["group"] == "boss" and f["won"] and f["floor"] <= 17 for f in fights): pills.append("Act 1 boss beaten")
        if any(f["group"] == "boss" and not f["won"] and f["floor"] <= 17 for f in fights): pills.append("Act 1 boss lost")
        pills.append("live · " + r["status"] if r.get("live") else outcome)
        rp, rm = sum(f.get("predicted") or 0 for f in fights), sum(f.get("matched") or 0 for f in fights)
        top = max([f["floor"] for f in fights] + [note.get("died", {}).get("floor", 0)])
        hall, lines, seen_out = {}, [], []
        for f in fights:
            act = 1 if f["floor"] <= 17 else 2 if f["floor"] <= 34 else 3
            if f["group"] == "hallway": hall[act] = hall.get(act, 0) + 1
            kind = f["group"] if f["group"] != "hallway" else ("easy" if hall[act] <= (3 if act == 1 else 2) else "hard")
            mons = {}
            for m in f["monsters"]: mons[m] = mons.get(m, 0) + 1
            hp = "%d→%d" % (f["hp_start"], f["hp_end"])
            if f["won"] and f.get("hp_after") not in (None, f["hp_end"]): hp += " (%d after)" % f["hp_after"]
            bits = ["F%d %s%s" % (f["floor"], kind, " (Act 2)" if act > 1 else ""),
                    " + ".join(m + (" ×%d" % n if n > 1 else "") for m, n in mons.items()),
                    hp + " " + ("won" if f["won"] else "lost")]
            if not f.get("handed_over"): bits.append("engine" + (" %d/%d steps matched" % (f.get("matched") or 0, f["predicted"]) if f.get("predicted") else ""))
            elif f.get("decisions"): bits.append("engine %d moves%s, then fallback: %s" % (
                f["decisions"], " (%d/%d steps matched)" % (f.get("matched") or 0, f["predicted"]) if f.get("predicted") else "", f["handed_over"]))
            else: bits.append("fallback: " + f["handed_over"])
            new = [x for x in (f.get("left_out") or []) if x not in seen_out]
            if new:
                seen_out += new; bits.append("engine's picture leaves out " + ", ".join(new))
            lines.append("- " + " · ".join(bits))
        if note.get("died"):
            lines.append("- F%d %s · died · fallback (a death-screen bug kept this fight out of the record)" % (note["died"]["floor"], note["died"]["monsters"]))
        head = "\n#### %s\n\n%s. Highest floor %d; recorded fights won %d / %d; chance-free steps matched %d / %d; fights left to the fallback rule %d.\n" % (
            note["title"], " · ".join(pills), top, sum(1 for f in fights if f["won"]), len(fights), rm, rp, sum(1 for f in fights if f.get("handed_over")))
        return head + ("\n" + note["text"] + "\n" if note.get("text") else "") + "\nFights (F = floor; HP at start→end; \"after\" = after end-of-fight heals):\n\n" + "\n".join(lines) + "\n"

    def default_title(self, i, r):
        # the page's own title for a run with no note, plus its level, as the noted A20 runs carry it
        run, a = r.get("run") or {}, self.setting(self.S["real_game"]["runs"], i)[0]
        return "Run %d%s%s" % (i + 1, " · started " + run["started"][11:16] if run.get("started") else "", " · Ascension %d" % a if a else "")

    def run_line(self, i, r, note):
        run = r.get("run") or {}
        title = (note or {}).get("title") or self.default_title(i, r)
        outcome = ("won the run" if run.get("victory") else "stopped at Act 2 on purpose" if run.get("stopped")
                   else "died on floor %s in Act %s" % (run.get("floor"), run.get("act"))) if run else (note or {}).get("outcome", "finished")
        boss = [f for f in r["fights"] if f["group"] == "boss" and f["floor"] <= 17]
        outcome = outcome[:1].lower() + outcome[1:]
        BN = {"SlimeBoss": "Slime Boss", "TheGuardian": "The Guardian", "Hexaghost": "Hexaghost"}
        bits = ["%s %s from %d HP%s" % (BN.get(f["monsters"][0], f["monsters"][0]), "beaten" if f["won"] else "lost", f["hp_start"], " to %d" % f["hp_end"] if f["won"] else "") for f in boss]
        line = "- **%s:** %s%s." % (title, "; ".join(bits) + "; " if bits else "no Act 1 boss; ", outcome)
        return line + (" " + note["text"] if note and note.get("text") else "")

    def c_real_note(self):
        return "One earlier session at 05:53 stopped before its first fight." if self.S["real_game"].get("empty_folders") else ""

    # ---- the long lists
    def everything(self):
        if not self.full:
            return ("This edition leaves the list out: all %d entries, one line each, with outcome, dates, the lane's prediction and CPU-hours, and its source, "
                    "are in llms-full.md. Counts per stretch are in the story above.\n" % len(self.items))
        out = ["Outcome words: Worked, Didn't work, Partly, Built, Dropped, Still open. "
               "Lanes say how likely they rated themselves before they ran and the CPU-hours they used. %d entries.\n" % len(self.items)]
        for i, st in enumerate(self.L["STRETCHES"]):
            mine = [t for t in self.items if self.in_range(t, st[0], st[1])]
            out.append("\n### Stretch %d: %s (%s to %s)\n\n%d things tried: %s.\n" % (i + 1, st[2], fmt_date(st[0]), fmt_date(st[1]), len(mine), self.counts(mine)))
            for key, name in self.L["KINDS"]:
                ks = [t for t in mine if t["kind"] == key]
                if not ks: continue
                out.append("\n#### %s\n" % name)
                for t in ks:
                    dates = fmt_date(t["date"]) if t["date"] == t["end"] else fmt_date(t["date"]) + " to " + fmt_date(t["end"])
                    meta = [dates, self.outcome_name(t["outcome"])]
                    if t["lane"] and t.get("pred"): meta.append("rated %s beforehand" % t["pred"])
                    if t["lane"] and t.get("cpu") and t["cpu"][1]: meta.append("%s CPU-hours" % t["cpu"][1])
                    if t["who"] == "owner": meta.append("the owner's call")
                    if t.get("source"): meta.append("source: " + t["source"])
                    out.append("- **%s.** %s (%s)" % (t["title"], t["text"], "; ".join(meta)))
        return "\n".join(out) + "\n"

    def viz(self, v):
        k, unit = v.get("kind"), v.get("unit") or "value"
        num = lambda x: ("{:,}".format(x) if isinstance(x, int) else str(x)) if x is not None else "–"
        if k in ("bars", "bignum", "tally"):
            rows = v["rows"]
            notes = any(r.get("note") for r in rows)
            return table(["Item", unit] + (["Note"] if notes else []),
                         [[r["label"], num(r["value"])] + ([r.get("note", "")] if notes else []) for r in rows])
        if k == "heat":
            return table([unit] + v["xs"], [[y] + [num(c) for c in row] for y, row in zip(v["ys"], v["cells"])])
        if k == "line":
            xs = []
            for s in v["series"]:
                for p in s["points"]:
                    if p["x"] not in xs: xs.append(p["x"])
            head = [v.get("x_label") or "x"] + [s["name"] for s in v["series"]]
            return "Values in %s.\n\n" % unit + table(head, [[x] + [num(next((p["y"] for p in s["points"] if p["x"] == x), None)) for s in v["series"]] for x in xs])
        if k == "scatter":
            return table(["Point", v.get("x_label") or "x", v.get("y_label") or "y"], [[p.get("label", ""), num(p["x"]), num(p["y"])] for p in v["points"]])
        if k == "slope":
            return "Values in %s.\n\n" % unit + table(["Item", v["a_label"], v["b_label"]], [[r["label"], num(r["a"]), num(r["b"])] for r in v["rows"]])
        if k == "timeline":
            return table(["When", "Event", unit], [[e["x"], e["label"], num(e.get("value"))] for e in v["events"]])
        return "```json\n" + json.dumps({x: y for x, y in v.items() if x != "kind"}, ensure_ascii=False) + "\n```"

    def stats(self):
        n = sum(len(p["items"]) for g in self.STATS for p in g["parts"])
        out = [("" if self.full else "Titles and claims only; each statistic's full setting, how it was counted and its chart data are in llms-full.md. ") +
               "%d statistics. Each was mined by one script and recomputed by an independent second script; \"corrected\" means the check changed it. "
               "Each names its setting; numbers from different settings are not comparable.\n" % n]
        for g in self.STATS:
            if not any(p["items"] for p in g["parts"]): continue
            out.append("\n### %s%s\n" % (g["name"], " (%s)" % g["dates"] if g.get("dates") else ""))
            for p in g["parts"]:
                if not p["items"]: continue
                if p["name"]: out.append("\n#### %s\n" % p["name"])
                for it in p["items"]:
                    if not self.full:
                        out.append("- **%s** [%s] %s" % (it["title"], it["tag"], it["claim"])); continue
                    out.append("\n**%s** [%s]\n\n%s\n\n- Setting: %s\n- Check: %s\n- How it was counted: %s\n" % (
                        it["title"], it["tag"], it["claim"], it["setting"],
                        "corrected by its independent check" if it.get("checked") == "corrected" else "confirmed by an independent check",
                        it.get("caveat") or ""))
                    if it.get("viz"):
                        out.append("Chart (%s) data:\n\n%s\n" % (it["viz"]["kind"], self.viz(it["viz"])))
        return "\n".join(out) + "\n"


EDITIONS = {
    False: "This is the core edition: the whole page, with one line per real-game run and the statistics as titles and claims. llms-full.md (same folder) adds every real-game fight, the full list of everything tried, and each statistic's setting and data.",
    True: "This is the full edition: everything in llms.md plus every real-game fight, the full list of everything tried, and each statistic's setting, counting notes and data.",
}

PREAMBLE = """# sts-for-ai showcase, text edition for language models

{edition}

This is the showcase page of sts-for-ai (a home-built Slay the Spire combat engine and an AI that plays it) as one Markdown file. The web page is showcase/index.html in this repository; this file holds the same content with every chart written out as a table and every hover tip written inline. It was generated by `showcase/llm.py` from the hand-written page and its data files (data written {written}).

How to read it:

- **Every number belongs to a setting.** The project changed its tests, players and rules many times in 23 days. A number is tagged `[setting: short tag | full setting]`; two numbers with different settings must not be compared or pooled.
- **Ascension 0 and Ascension 20 results are separate.** So are the real-game run settings (run rules 1 to 5, fight guard). Real-game boss counts come in two forms: "of those reached" (runs that got to the Act 1 boss) and "of runs" (all runs in that setting), so 22 of 24 and 22 of 27 describe the same Ascension 0 runs.
- **Players:** "hand-written player" (a formula, the baseline), "net, one turn deep", and "the product" (the 29 October net searching two turns deep with an HP price and line step). From 13 November the product also prices turn-start powers and leftover block.
- **The gauntlet** is the project's own Act 1 test (11 fights, starter deck, no relics beyond Burning Blood, no potions); it is not the real game. "Clears" = share of runs that beat the Act 1 boss. "se" = standard error.
- **Sections:** the story in eight stretches; how the work was done; a verdict on the AI-run research; results and six findings; how the AI plays; the real game on 14 November, run by run; what's next; every thing tried; the statistics tab; glossary.

"""


def build(d, full):
    pg = Page(d, full)
    fills = {n[2:].replace("_", "-") for n in dir(pg) if n.startswith("c_")}
    src = (HERE / "index.html").read_text(encoding="utf-8")
    body = src[src.index("<main"):src.index('<div id="tip"')]
    p = ToMd(fills)
    p.feed(body)
    md = tidy("".join(p.out))
    # the hero numbers the page's scripts fill in
    md = md.replace("**318** things tried", "**%d** things tried" % len(pg.items))
    runs = pg.S["real_game"]["runs"]
    for lv, label in [((0, 1, 0), "in the real game today at Ascension 0"), ((20, 5, 1), "at Ascension 20")]:
        mine = [r for i, r in enumerate(runs) if pg.setting(runs, i) == lv]
        reached = sum(1 for r in mine if any(f["group"] == "boss" and f["floor"] <= 17 for f in r["fights"]))
        beaten = sum(1 for r in mine if any(f["group"] == "boss" and f["won"] and f["floor"] <= 17 for f in r["fights"]))
        if reached:
            md = re.sub(r"\*\*\d+ of \d+\*\* (Act 1 bosses beaten %s)" % re.escape(label), "**%d of %d** \\1" % (beaten, reached), md)
    md = re.sub(r"\{\{SUM:([\d-]+):([\d-]+)\}\}", lambda m: pg.summary(m.group(1), m.group(2)), md)
    md = re.sub(r"\{\{FILL:([\w-]+)\}\}", lambda m: pg.fill(m.group(1)), md)
    # the two hidden tabs: their lists come from scripts, so write them out here
    # links and credits that only make sense on the web page
    md = md.replace("Back to the highlights", "").replace("Map icons from Slay the Spire, by Mega Crit.", "")
    md = re.sub(r"\n{3,}", "\n\n", md)
    return PREAMBLE.format(written=pg.S["written"], edition=EDITIONS[full]) + md


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    d, stale = load(), []
    for full, out in OUTS.items():
        text = build(d, full)
        if "--check" in sys.argv:
            if not out.exists() or out.read_text(encoding="utf-8") != text: stale.append(out.name)
            continue
        out.write_text(text, encoding="utf-8", newline=chr(10))
        print("wrote %s (%d KB, about %d k tokens)" % (out.relative_to(HERE.parent), len(text.encode()) // 1024, len(text) // 4000))
    if stale: sys.exit("stale: %s; run python showcase/llm.py" % ", ".join(stale))
