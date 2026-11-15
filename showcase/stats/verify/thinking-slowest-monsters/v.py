import json, os, sys, statistics as st
from collections import defaultdict
R = "results/real-game"
sys.path.insert(0, "scripts")
import real_game_report as rg
runs = rg.all_runs(R)
print("runs", len(runs))
# map (folder, k-th run with combat) -> run number
num = {}
byfolder = defaultdict(list)
for i, r in enumerate(runs, 1):
    if r["combat"]:
        byfolder[r["folder"]].append(i)
info = {i: r for i, r in enumerate(runs, 1)}
per = defaultdict(list); runsof = defaultdict(set); allsec = []; mism = 0; nview_asc = defaultdict(int)
for name in sorted(os.listdir(R)):
    p = os.path.join(R, name, "decisions.jsonl")
    if not os.path.isfile(p): continue
    k, prev = -1, None
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            d = json.loads(line)
            if prev is None or d["floor"] < prev: k += 1
            prev = d["floor"]
            if "view" not in d: continue
            lst = byfolder.get(name, [])
            rn = lst[k] if k < len(lst) else None
            a = info[rn].get("ascension") or 0 if rn else None
            va = d["view"].get("ascension")
            nview_asc[(a, va)] += 1
            if a != 20: continue
            if not (28 <= rn <= 90): print("odd run", rn)
            s = d["seconds"]; allsec.append(s)
            names = {m["name"] for m in d["view"]["monsters"] if m.get("hp", 0) > 0 and not m.get("escaped")}
            for n in names:
                per[n].append(s); runsof[n].add(rn)
print(nview_asc)
print("A20 decisions", len(allsec), "mean", st.mean(allsec), "median", st.median(allsec))
rows = sorted(((st.mean(v), n, len(v), len(runsof[n]), st.median(v)) for n, v in per.items()), reverse=True)
for m, n, c, r, md in rows:
    print(f"{n:25s} mean {m:6.2f} n {c:4d} runs {r:3d} median {md:6.3f}" + ("" if c >= 30 and r >= 4 else "  (small)"))
