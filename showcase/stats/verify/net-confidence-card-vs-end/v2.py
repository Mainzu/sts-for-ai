import json, os, statistics, collections
R = "results/real-game"
def name(x, a):
    a = a.split("@")[0]
    if a.startswith("Potion:"):
        return "potion " + x["view"]["player"]["potions"][int(a.split(":")[1])].replace("gen:", "")
    return a[4:] if a.startswith("gen:") else a
per = {0: collections.defaultdict(list), 20: collections.defaultdict(list)}
runs = {0: collections.defaultdict(set), 20: collections.defaultdict(set)}
nd = collections.Counter()
for d in sorted(os.listdir(R)):
    p = os.path.join(R, d, "decisions.jsonl")
    if not os.path.isfile(p): continue
    k = 0; prev = None
    with open(p, encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            x = json.loads(ln)
            if prev is not None and x["floor"] < prev: k += 1
            prev = x["floor"]
            if "turn" not in x: continue
            a = x["view"].get("ascension") or 0
            firsts = [o[0] for o in x["options"]]
            if "End" not in firsts or x.get("cut"): continue
            nd[a] += 1
            e = x["two"][firsts.index("End")]; best = {}
            for o, s in zip(firsts, x["two"]):
                if o == "End": continue
                n = name(x, o); best[n] = max(best.get(n, -9), s)
            for n, s in best.items():
                per[a][n].append(100 * (s - e)); runs[a][n].add((d, k))
print(nd)
for a in (0, 20):
    rows = sorted(((statistics.median(v), len(v), k, len(runs[a][k])) for k, v in per[a].items() if len(v) >= 20), reverse=True)
    print("A", a, len(rows))
    for r in rows: print("  %-25s %6.1f n=%d runs=%d" % (r[2], r[0], r[1], r[3]))
