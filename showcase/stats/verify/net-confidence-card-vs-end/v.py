import json, os, statistics, collections, sys
R = "results/real-game"
def name(a):
    a = a.split("@")[0]
    return a[4:] if a.startswith("gen:") else a
per = {0: collections.defaultdict(list), 20: collections.defaultdict(list)}
cnt = collections.Counter(); kinds = collections.Counter(); multi = collections.Counter()
for d in sorted(os.listdir(R)):
    p = os.path.join(R, d, "decisions.jsonl")
    if not os.path.isfile(p): continue
    with open(p, encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            x = json.loads(ln)
            if "options" not in x or "view" not in x: continue
            a = x["view"].get("ascension") or 0
            opts = x["options"]
            firsts = [o[0] if o else None for o in opts]
            if "End" not in firsts: continue
            cnt[(a, "end")] += 1
            if x.get("cut"): continue
            cnt[(a, "uncut")] += 1
            two = x["two"]; e = two[firsts.index("End")]
            best = {}
            for o, s in zip(firsts, two):
                if o is None or o == "End": continue
                kinds[o.split("@")[0]] += 0
                if len(opts[firsts.index(o)]) > 1: multi[1] += 1
                n = name(o)
                best[n] = max(best.get(n, -1e9), s)
            for n, s in best.items():
                per[a][n].append(100 * (s - e))
print(cnt)
print("multi-action options", multi)
for a in (0, 20):
    rows = [(statistics.median(v), len(v), k, statistics.mean(v)) for k, v in per[a].items() if len(v) >= 20]
    rows.sort(reverse=True)
    print("A", a, len(rows))
    for r in rows: print("  %-25s %6.1f n=%d mean=%.1f" % (r[2], r[0], r[1], r[3]))
