import json, os, sys, collections
R = "results/real-game"
def base(a):
    a = a.split("@")[0]
    if a.startswith("gen:"): a = a[4:]
    return a.rstrip("+")
mode = sys.argv[1] if len(sys.argv) > 1 else "all"
turns = collections.OrderedDict()  # key (folder,run,floor,turn) -> info
for name in sorted(os.listdir(R)):
    p = os.path.join(R, name, "decisions.jsonl")
    if not os.path.isfile(p): continue
    run, prev = -1, None
    with open(p, encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            x = json.loads(ln)
            if prev is None or x["floor"] < prev: run += 1
            prev = x["floor"]
            if "view" not in x: continue
            v = x["view"]
            k = (name, run, x["floor"], x["turn"])
            t = turns.get(k)
            if t is None:
                ms = v["monsters"]
                if mode == "alive": ms = [m for m in ms if m.get("hp", 1) > 0]
                hand = {base(c) for c in v["hand"]}
                t = turns[k] = {"asc": v.get("ascension") or 0, "grp": tuple(sorted({m["name"] for m in ms})),
                                "defhand": "Defend" in hand, "S": 0, "D": 0}
            pk = x["pick"]
            if pk is None: continue
            for a in x["options"][pk]:
                b = base(a)
                if b == "Strike": t["S"] += 1
                if b == "Defend": t["D"] += 1
fold_runs = {(k[0], k[1]) for k in turns}
for asc in (0, 20):
    g = collections.defaultdict(lambda: [0, 0, 0, 0, 0, set()])
    for k, t in turns.items():
        if t["asc"] != asc: continue
        r = g[t["grp"]]; r[0] += t["S"]; r[1] += t["D"]; r[2] += 1
        if t["defhand"]: r[3] += 1; r[4] += t["D"] > 0
        r[5].add((k[0], k[1], k[2]))
    print("ASC", asc, "turns", sum(1 for t in turns.values() if t["asc"] == asc))
    for grp, r in sorted(g.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        if r[0] + r[1] < 20: continue
        print(f"{'+'.join(grp)[:60]:60s} D{r[1]:4d} S{r[0]:4d} ratio {r[1]/max(r[0],1):.2f} turns {r[2]} defhand {r[3]} played {r[4]} fights {len(r[5])}")
