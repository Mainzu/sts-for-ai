import sys, statistics as st, collections
sys.path.insert(0, r"scripts")
import os; os.chdir(r".")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
by = collections.defaultdict(list); dec = collections.defaultdict(list); top=[]
nf=0; ascs=collections.Counter()
for i, r in enumerate(runs, 1):
    a = r.get("ascension") or 0
    ascs[(a, i>=28)] += 1
    if a != 20: continue
    for f in r["fights"]:
        nf += 1
        key = (" + ".join(sorted(f["monsters"])), f["group"])
        t = sum(f.get("think_s") or [])
        by[key].append(t); dec[key].append(f.get("decisions") if f.get("decisions") is not None else len(f.get("think_s") or []))
        top.append((t, i, f["floor"], key))
print(ascs, "A20 fights", nf)
for k, v in sorted(by.items(), key=lambda kv: -st.median(kv[1])):
    if len(v) >= 3: print(f"{st.median(v):7.1f} n={len(v):3d} max={max(v):6.1f} decmed={st.median(dec[k])} {k}")
top.sort(reverse=True)
for t in top[:8]: print(t)
