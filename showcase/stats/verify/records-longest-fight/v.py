import sys, os, json, statistics
REPO = "."
sys.path.insert(0, REPO + "/scripts")
import real_game_report as R
runs = R.all_runs(REPO + "/results/real-game")
print("runs", len(runs))
num = {r["seed"]: i + 1 for i, r in enumerate(runs)}
# stream states for turn counter per (seed, floor)
T = {}
for name in sorted(os.listdir(REPO + "/results/real-game")):
    p = os.path.join(REPO, "results/real-game", name, "states.jsonl")
    if not os.path.isfile(p): continue
    with open(p, encoding="utf-8") as f:
        for l in f:
            if not l.strip(): continue
            g = json.loads(l)["msg"].get("game_state")
            if not g or "combat_state" not in g: continue
            c = g["combat_state"]; k = (g.get("seed"), g.get("floor"))
            d = T.setdefault(k, {"turn": 0, "mons": [m["name"] for m in c["monsters"]], "hp0": c["player"]["current_hp"]})
            d["turn"] = max(d["turn"], c.get("turn") or 0)
            d["hp1"] = c["player"]["current_hp"]
rows = {0: [], 20: []}
for r in runs:
    a = R.asc(r)
    for f in r["fights"]:
        if f["floor"] > 16: continue
        t = T.get((r["seed"], f["floor"]))
        if not t: print("missing", num[r["seed"]], f["floor"]); continue
        rows[a].append((t["turn"], num[r["seed"]], f["floor"], f["group"], t["mons"], f["won"], f["hp_start"], f["hp_end"], R.setting_tag(r)))
for a in (0, 20):
    xs = rows[a]; print("A%d fights %d median %s runs %s-%s" % (a, len(xs), statistics.median(x[0] for x in xs), min(x[1] for x in xs), max(x[1] for x in xs)))
    for x in sorted(xs, reverse=True)[:8]: print(x)
