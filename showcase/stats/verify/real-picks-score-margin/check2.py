import json, os, sys
from collections import defaultdict
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R

runs = R.all_runs()
print("runs", len(runs))
byfolder = defaultdict(list)
for i, r in enumerate(runs, 1):
    r["n"] = i
    byfolder[r["folder"]].append(r)

def strip(c):
    return c[4:] if isinstance(c, str) and c.startswith("gen:") else c

rec = os.path.join(ROOT, "results", "real-game")
rewards = []  # (run_no, asc, rules, d)
unmapped = 0
seen_asc = defaultdict(set)
for folder, rs in byfolder.items():
    path = os.path.join(rec, folder, "decisions.jsonl")
    if not os.path.exists(path):
        continue
    k, prev = -1, None
    seg_asc = {}
    segs = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            fl = d.get("floor")
            if prev is None or (fl is not None and fl < prev):
                k += 1
            if fl is not None:
                prev = fl
            if "view" in d and d["view"].get("ascension") is not None:
                seen_asc[(folder, k)].add(d["view"]["ascension"])
            if "card_reward" in d:
                segs[k].append(d)
    nseg = k + 1
    if nseg != len(rs):
        print("segment mismatch", folder, nseg, [r["n"] for r in rs])
    for s, ds in segs.items():
        if s >= len(rs):
            unmapped += len(ds); continue
        r = rs[s]
        va = seen_asc.get((folder, s))
        if va and va != {R.asc(r)}:
            print("asc mismatch", folder, s, va, R.asc(r))
        for d in ds:
            rewards.append((r["n"], R.asc(r), r["run_rules"], d))
print("unmapped", unmapped)

a20 = [x for x in rewards if x[1] == 20]
print("A20 rewards", len(a20), "runs", min(x[0] for x in a20), max(x[0] for x in a20))
print("A0 rewards", sum(1 for x in rewards if x[1] == 0))
print("floor0 A20", sum(1 for x in a20 if x[3]["floor"] == 0))
m = defaultdict(list); picks = defaultdict(int); noskip = 0
for n, a, rr, d in a20:
    opts = d["options"]
    if None not in opts:
        noskip += 1; continue
    sk = d["scores"][opts.index(None)]
    pk = strip(d.get("pick"))
    for o, s in zip(opts, d["scores"]):
        if o is None: continue
        m[strip(o)].append((s - sk, n, d["floor"]))
        if strip(o) == pk: picks[strip(o)] += 1
print("noskip", noskip)
rows = sorted(((sum(v[0] for v in l)/len(l), c, len(l)) for c, l in m.items() if len(l) >= 8), reverse=True)
for mean, c, k in rows:
    print(f"{c:22s} {mean:+.3f} n={k} picked={picks[c]}")

for n,a,rr,d in a20:
    for o in d["options"]:
        if o and "Barricade" in o: print("BARR", n, d["floor"], o, d["card_reward"])
        if o and "+" in o: print("PLUS", o)
fb=[]
for n,a,rr,d in a20:
    opts=d["options"]; sk=d["scores"][opts.index(None)]
    sc=sorted(((s, strip(o) or "SKIP") for o,s in zip(opts,d["scores"])), reverse=True)
    fb.append((round(sc[0][0]-sc[1][0],3), sc[0][1], n, d["floor"], strip(d.get("pick"))))
fb.sort(reverse=True); print("best-second", fb[:8])
fb2=sorted(((round(max(d["scores"])-d["scores"][d["options"].index(None)],3), str(strip(d.get("pick"))), n, d["floor"]) for n,a,rr,d in a20), reverse=True)
print("best-skip", fb2[:8])
fb3=sorted(((round(s-d["scores"][d["options"].index(None)],3), strip(o), n, d["floor"], str(strip(d.get("pick")))) for n,a,rr,d in a20 for o,s in zip(d["options"],d["scores"]) if o), reverse=True)
print("card-skip", fb3[:8])
