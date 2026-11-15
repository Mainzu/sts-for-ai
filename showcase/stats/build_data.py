"""Turn the checked statistics (final.json) into showcase/stats-data.js."""
import json, re, sys

root = sys.argv[1]
d = json.load(open(sys.argv[2], encoding="utf-8"))
S = {s["id"]: s for s in d["kept"]}

DROP = {"plays-gremlin-standoff",          # same fight as records-longest-fight
        "run-level-potions-drunk",         # overlaps plays-potions, counted differently
        "net-confidence-powers-need-lookahead",  # its own checker: reason unclear
        "run-level-endings",               # pools r5 with and without the guard; main page has per-setting tables
        "run-level-gold-hoard", "run-level-gold-sinks",  # the bot ignores gold on purpose
        "run-level-events", "run-level-campfires"}       # fixed rules choose these: the stat would restate the rule
TITLES = {"plays-nob-no-defend": "It rarely Defends against Gremlin Nob",
          "net-confidence-misjudged-monsters": "Hexaghost and Lagavulin fool it; The Guardian scares it more than it should"}
SECTIONS = [
    ("thinking", "What it thinks hardest about", ["thinking-blink-or-ponder", "thinking-slime-boss-headache", "thinking-slowest-monsters", "thinking-crowded-board", "thinking-cards-in-hand", "thinking-node-cap", "thinking-hardest-moves"]),
    ("picks", "What it picks in the real game", ["real-picks-a20-favourites", "real-picks-a20-snubs", "real-picks-a0-loves-and-snubs", "real-picks-score-margin", "real-picks-skip-rate", "real-picks-rarity", "real-picks-boss-deck"]),
    ("hurts", "What hurts", ["trouble-hexaghost-a20", "trouble-killers-a20", "trouble-encounters-a20", "trouble-a0-vs-a20", "trouble-monster-powers-a20", "trouble-debuffs-a20"]),
    ("plays", "How it plays", ["plays-most-played", "plays-hand-rate", "plays-bash-turn1", "plays-nob-no-defend", "plays-potions", "run-level-empty-belt", "plays-energy-left"]),
    ("records", "Records", ["records-longest-fight", "records-closest-wins", "records-biggest-hit", "records-biggest-loss", "records-boss-speed", "records-heals", "records-flawless"]),
    ("net", "What the net believes", ["net-confidence-calibration", "net-confidence-misjudged-monsters", "net-confidence-confident-losses", "net-confidence-second-turn-saves", "net-confidence-overrules", "net-confidence-card-vs-end"]),
    ("sim", "In the 1,000 simulated test runs", ["sim-picks-product-favourites", "sim-picks-demon-form", "sim-picks-clear-correlation", "sim-picks-boss-nemesis", "sim-picks-how-runs-end", "sim-picks-deadliest-fights"]),
]
# The repeat audit (workflow stats-redundancy-audit, audit.json): three critics per statistic.
AUDIT = json.load(open(sys.argv[2].replace("final.json", "audit.json"), encoding="utf-8"))
DROP |= {"thinking-slowest-monsters", "thinking-cards-in-hand", "real-picks-score-margin", "trouble-hexaghost-a20",
         "trouble-monster-powers-a20", "trouble-debuffs-a20", "records-biggest-loss", "net-confidence-confident-losses"}
TRIM_LENS = {  # whose rewording to use; rows to remove are the union over the critics
    "thinking-blink-or-ponder": 1, "thinking-crowded-board": 2, "thinking-node-cap": 2, "sim-picks-deadliest-fights": 0,
    "trouble-encounters-a20": 1, "trouble-a0-vs-a20": 1, "plays-hand-rate": 2, "plays-nob-no-defend": 2,
    "records-boss-speed": 0, "records-heals": 2, "net-confidence-misjudged-monsters": 2,
    "net-confidence-second-turn-saves": 2, "net-confidence-card-vs-end": 2}
for m in AUDIT["merged"]:
    i = m["id"]
    if i in TRIM_LENS:
        s = S[i]
        v = [x for x in m["votes"] if x["lens"] == TRIM_LENS[i]][0]
        if v["claim"]:
            s["claim"] = v["claim"]
        rm = set(m["remove_rows"])
        s["rows"] = [r for r in s["rows"] if r["label"] not in rm]
        s["subset"] = s["subset"].replace(" (see plays-gremlin-standoff)", " (one 84-turn fight, run 83)")
for w in AUDIT["rewrites"]:
    if w.get("check") and w["check"]["verdict"] != "refuted":
        st = w["check"]["stat"]
        S[w["id"]].update({k: st[k] for k in ("title", "claim", "subset", "n", "rows", "unit", "caveat")})
        S[w["id"]]["verdict"] = "rewritten after the repeat audit, then " + w["check"]["verdict"]
for sec in SECTIONS:
    sec[2][:] = [i for i in sec[2] if i not in DROP]
used = {i for _, _, ids in SECTIONS for i in ids}
missing = set(S) - used - DROP
assert not missing, missing
assert not (used - set(S)), used - set(S)

def clean(t):
    return re.sub(r"\s*Suggested title:.*$", "", t.strip())

def tag(s):
    sub = s["subset"]
    if sub.lower().startswith("simulated"):
        m = re.search(r"runs? (\d+)-(\d+)", sub)
        return "simulated test" + (" · runs %s–%s" % m.groups() if m else "")
    labels = " ".join(r["label"] for r in s["rows"])
    both = re.search(r"\bA0\b", labels) and re.search(r"\bA20\b", labels)
    if both:
        return "real game · A0 and A20, shown apart"
    a20 = "A20" in sub
    t = "real game · " + ("A20" if a20 else "A0")
    if a20 and "pooled" in sub:
        t += " · rule versions pooled"
    return t

PERIODS = [  # the story's eight stretches (story.js STRETCHES)
    ("all", "Across the whole project", "23 October to 14 November"),
    ("p1", "Period 1 (P1): The engine and the first question", "23 to 24 October"),
    ("p2", "Period 2 (P2): Self-play, with the owner at the desk", "25 to 28 October"),
    ("p3", "Period 3 (P3): Claude runs the lab day to day", "29 to 31 October"),
    ("p4", "Period 4 (P4): From single fights to an Act", "1 to 2 November"),
    ("p5", "Period 5 (P5): The AI roles take over", "3 to 5 November"),
    ("p6", "Period 6 (P6): Real Act 1 goes in", "6 to 9 November"),
    ("p7", "Period 7 (P7): New nets for new content; relics and potions", "10 to 12 November"),
    ("p8", "Period 8 (P8): The product changes; the real game", "13 to 14 November"),
]
# today's real-game sections sit in period 8; the 1,000-run test of the product was read on 3 and 5 November (period 5)
PART_PERIOD = {"sim": "p5"}

def item(i, s):
    return {"id": i, "title": TITLES.get(i, s["title"]), "claim": clean(s["claim"]), "tag": tag(s),
            "setting": s["subset"] + " · n: " + s["n"], "caveat": s["caveat"].strip(), "checked": s["verdict"],
            "viz": {"kind": "bars", "rows": s["rows"], "unit": s["unit"]}}

parts = {k: [] for k, _, _ in PERIODS}
for key, name, ids in SECTIONS:
    per = PART_PERIOD.get(key, "p8")
    nm = name if per == "p8" else "The 1,000-run test of the product"
    parts[per].append({"name": nm, "items": [item(i, S[i]) for i in ids]})
# the history statistics (workflow sts-history-stats, history.json), when present
import os
hp = sys.argv[2].replace("final.json", "history.json")
if os.path.exists(hp):
    H = json.load(open(hp, encoding="utf-8"))
    hist = {k: [] for k, _, _ in PERIODS}
    for st in H["kept"]:
        per = "p" + str(st["period"]).strip() if str(st["period"]).strip() in "12345678" else "all"
        dates = [d for k, n, d in PERIODS if k == per][0]
        hist[per].append({"id": st["id"], "title": st["title"], "claim": st["claim"],
                          "tag": "project history · " + (dates if per != "all" else "all 23 days"),
                          "setting": st["subset"] + " · n: " + st["n"], "caveat": st["caveat"].strip(),
                          "checked": st["verdict"], "viz": st["viz"]})
    for k in hist:
        if hist[k]:
            parts[k].insert(0, {"name": "Behind the scenes" if k == "p8" else "", "items": hist[k]})
out = [{"key": k, "name": n, "dates": d, "parts": parts[k]} for k, n, d in PERIODS]
js = ("/* The statistics tab's data, by period: each statistic mined by one script and recomputed by an independent\n"
      "   second one (workflows sts-fun-stats and sts-history-stats, 2026-11-14; scripts in showcase/stats/);\n"
      "   written by stats/build_data.py, don't edit by hand. */\n"
      "window.STATS = " + json.dumps(out, ensure_ascii=False, indent=1) + ";\n")
open(root + "/showcase/stats-data.js", "w", encoding="utf-8", newline="\n").write(js)
print(sum(len(p["items"]) for x in out for p in x["parts"]), "statistics in", sum(1 for x in out if any(p["items"] for p in x["parts"])), "periods;", len(js), "bytes")
