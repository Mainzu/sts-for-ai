import sys, json, os, collections
sys.path.insert(0, "scripts")
import real_game_report as R
RG = R.RECORDS
runs = R.all_runs()
print("runs", len(runs))
# relics per (folder, seed, floor) from states, streaming
relics = {}
for name in sorted(os.listdir(RG)):
    p = os.path.join(RG, name, "states.jsonl")
    if not os.path.isfile(p): continue
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            gs = json.loads(line)["msg"].get("game_state")
            if not gs or gs.get("seed") is None: continue
            if "combat_state" in gs:
                relics[(name, gs["seed"], gs.get("floor"))] = [x.get("id") for x in gs.get("relics", [])]
agg = collections.defaultdict(lambda: [0, 0])
big = []; mob = collections.defaultdict(list); bb = []
for i, r in enumerate(runs, 1):
    a = R.asc(r)
    for f in r["fights"]:
        if not f["won"]: continue
        h = f["hp_after"] - f["hp_end"]
        agg[a][0] += 1; agg[a][1] += h
        rl = relics.get((r["folder"], r["seed"], f["floor"]), [])
        if "Meat on the Bone" in rl: mob[a].append((i, f["floor"], h))
        if "Black Blood" in rl: bb.append((i, a, f["floor"], h))
        if h > 6: big.append((a, i, f["floor"], f["monsters"], f["hp_end"], f["hp_after"], h, f["group"], rl))
for a, (n, s) in sorted(agg.items()): print("A", a, n, s, round(s/n, 2))
for b in big: print(b[:8], [x for x in b[8] if x in ("Meat on the Bone","Black Blood","Burning Blood")])
print("MoB", dict(mob)); print("BB", bb)
# runs ids sanity
print([ (i, R.asc(r), r["run_rules"]) for i, r in enumerate(runs,1) if i in (27,28,77,11,13,23)])
