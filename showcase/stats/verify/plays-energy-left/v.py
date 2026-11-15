import json, os, sys
from collections import Counter, defaultdict
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
REC = ROOT + "/results/real-game"
runs = R.all_runs()
print("runs", len(runs))
info = {}
for i, r in enumerate(runs, 1):
    ho = {f["floor"] for f in r["fights"] if f.get("handed_over")}
    info[r["seed"]] = (i, r.get("ascension"), ho, r["folder"])
tot = defaultdict(Counter); hit = defaultdict(Counter); el = defaultdict(Counter); cards = defaultdict(Counter)
fightc = defaultdict(Counter)
seen_seed_floor = set()
for name in sorted(os.listdir(REC)):
    p = os.path.join(REC, name, "states.jsonl")
    if not os.path.isdir(os.path.join(REC, name)) or not os.path.exists(p): continue
    cur = None; last = None  # key=(seed,floor), turn, gs
    def flush_turn(prev, nxt):
        pass
    ends = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            gs = json.loads(line)["msg"].get("game_state")
            if not gs or "combat_state" not in gs: continue
            key = (gs["seed"], gs["floor"]); t = gs["combat_state"]["turn"]
            if last is not None and last[0] == key and t == last[1] + 1:
                ends.append(last)
            last = (key, t, gs)
    for key, t, gs in ends:
        if key[0] not in info: continue
        run, asc, ho, fold = info[key[0]]
        if key[1] in ho: continue
        cs = gs["combat_state"]; e = cs["player"]["energy"]
        mons = tuple(sorted({m["name"] for m in cs["monsters"] if not m.get("is_gone") and m["current_hp"] > 0}))
        g = " + ".join(mons)
        tot[asc][g] += 1; tot[asc]["ALL"] += 1
        if e > 0:
            el[asc]["ALL"] += 1
            aff = [c["name"] for c in cs["hand"] if c.get("is_playable") and 0 <= c["cost"] <= e]
            if aff:
                hit[asc][g] += 1; hit[asc]["ALL"] += 1
                fightc[asc][(run, key[1], g)] += 1
                for c in set(aff): cards[asc][c] += 1
for a in tot:
    print("ASC", a, "ends", tot[a]["ALL"], "energy", el[a]["ALL"], round(100*el[a]["ALL"]/tot[a]["ALL"],1), "aff", hit[a]["ALL"], round(100*hit[a]["ALL"]/tot[a]["ALL"],1))
    for g, n in tot[a].most_common(25):
        print("   %-45s %4d %4d %5.1f" % (g, n, hit[a][g], 100*hit[a][g]/n))
    print("  cards", cards[a].most_common(8))
    print("  top fights", fightc[a].most_common(5))
