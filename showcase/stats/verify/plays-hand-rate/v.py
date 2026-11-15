import json, os, sys, collections
sys.path.insert(0,"scripts")
import real_game_report as rg
RUNS=rg.all_runs()
byf=collections.defaultdict(list)
for i,r in enumerate(RUNS):
    if r["combat"]: byf[r["folder"]].append((i+1,r))
print(len(RUNS))
R = "results/real-game"
def nm(s): return s[4:] if s.startswith("gen:") else s
def act_card(a):
    if a == "End" or a.startswith("Potion") or a.startswith("potion"): return None
    return nm(a.split("@")[0])
held = {0: collections.Counter(), 20: collections.Counter()}
played = {0: collections.Counter(), 20: collections.Counter()}
turns = collections.Counter(); runs = collections.Counter(); odd = collections.Counter()
mode = sys.argv[1] if len(sys.argv) > 1 else "cpt"
for name in sorted(os.listdir(R)):
    p = os.path.join(R, name, "decisions.jsonl")
    if not os.path.isfile(p): continue
    fd = []; k = -1
    prevfloor = None
    with open(p, encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            d = json.loads(ln)
            if prevfloor is None or d["floor"] < prevfloor: k = k+1 if prevfloor is not None else 0
            prevfloor = d["floor"]
            num, rr = byf[name][k]
            d["_run"] = num; d["_asc"] = rr.get("ascension")
            if d.get("view") and d["view"].get("ascension") is not None and d["view"]["ascension"] != d["_asc"]: odd["ascmismatch"] += 1
            if "view" not in d: continue
            fd.append(d)
    # group into turns: consecutive decisions with same floor & turn
    groups = []
    for d in fd:
        if groups and groups[-1][0]["floor"] == d["floor"] and groups[-1][0]["turn"] == d["turn"] and d["view"]["cards_played_this_turn"] >= groups[-1][-1]["view"]["cards_played_this_turn"]:
            groups[-1].append(d)
        else: groups.append([d])
    for g in groups:
        asc = g[0]["_asc"]; runs[asc,] += 0; runs.setdefault("r%d"%asc, set()).add(g[0]["_run"]) if False else None
        runs[g[0]["_run"]] = asc
        hand = collections.Counter()
        for k, v in g[0]["view"]["hand"].items(): hand[nm(k)] += v
        pl = set()
        for i, d in enumerate(g):
            line = d["line"] or [ ]
            if mode == "pick":
                acts = d["options"][d["pick"]]
            elif i + 1 < len(g):
                n = g[i+1]["view"]["cards_played_this_turn"] - d["view"]["cards_played_this_turn"]
                acts = []; c = 0
                for a in line:
                    if c >= n: break
                    acts.append(a)
                    if act_card(a): c += 1
                if c < n: odd["short"] += 1
            else: acts = line
            for a in acts:
                c = act_card(a)
                if c: pl.add(c)
        turns[asc] += 1
        for c in hand:
            held[asc][c] += 1
            if c in pl: played[asc][c] += 1
print(turns, runs, odd)
for asc in (20, 0):
    print("asc", asc)
    for c, h in sorted(held[asc].items(), key=lambda x: -played[asc][x[0]]/x[1]):
        if h >= 20: print("  %-16s %4d/%4d %3.0f%%" % (c, played[asc][c], h, 100*played[asc][c]/h))
