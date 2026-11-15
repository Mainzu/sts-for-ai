import json, os, sys, collections
R = "results/real-game"
def base(a):
    a = a.split("@")[0]
    if a.startswith("gen:"): a = a[4:]
    return a.rstrip("+")
mode = sys.argv[1] if len(sys.argv) > 1 else "prefix"
turns = collections.OrderedDict()
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
                hand = {base(c) for c in v["hand"]}
                t = turns[k] = {"asc": v.get("ascension") or 0, "grp": tuple(sorted({m["name"] for m in v["monsters"]})),
                                "defhand": "Defend" in hand, "decs": []}
            t["decs"].append((v["cards_played_this_turn"], x["line"] or x["options"][x["pick"]]))
for t in turns.values():
    S = D = 0
    ds = t["decs"]
    for i, (c, line) in enumerate(ds):
        if mode == "full" or i == len(ds) - 1: take = line
        else:
            need = ds[i+1][0] - c; take = []
            for a in line:
                if need <= 0: break
                take.append(a)
                if not a.startswith("Potion") and a != "End": need -= 1
        for a in take:
            b = base(a)
            S += b == "Strike"; D += b == "Defend"
    t["S"], t["D"] = S, D
for asc in (0, 20):
    g = collections.defaultdict(lambda: [0, 0, 0, 0, 0, set()])
    for k, t in turns.items():
        if t["asc"] != asc: continue
        r = g[t["grp"]]; r[0] += t["S"]; r[1] += t["D"]; r[2] += 1
        if t["defhand"]: r[3] += 1; r[4] += t["D"] > 0
        r[5].add((k[0], k[1], k[2]))
    print("ASC", asc, "turns", sum(1 for t in turns.values() if t["asc"] == asc))
    for grp, r in sorted(g.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        if r[0] + r[1] < 40 and "Gremlin Nob" not in grp and "Slime Boss" not in grp: continue
        print(f"{'+'.join(grp)[:60]:60s} D{r[1]:4d} S{r[0]:4d} ratio {r[1]/max(r[0],1):.2f} turns {r[2]} defhand {r[3]} played {r[4]} fights {len(r[5])}")
    eh = [0,0]
    for grp, r in g.items():
        if grp in (("Gremlin Nob",),): continue
        if grp in (("Lagavulin",),("Sentry",)) or "Gremlin Nob" in grp: eh[0]+=r[3]; eh[1]+=r[4]
    print("other elites defhand/played", eh)
