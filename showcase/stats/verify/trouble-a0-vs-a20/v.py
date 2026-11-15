import sys, statistics as st, collections
sys.path.insert(0, "scripts")
import os; os.chdir(".")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
d = collections.defaultdict(list); d2=collections.defaultdict(list); ids=collections.Counter()
for i, r in enumerate(runs, 1):
    a = r.get("ascension") or 0
    for f in r["fights"]:
        if f["group"] not in ("elite","boss"): continue
        key = "+".join(sorted(set(f["monsters"])))
        ids[(f["group"],tuple(f["monsters"]))]+=1
        loss = f["hp_start"] - f["hp_end"]
        d[(key,a)].append((loss, i, f["won"], f.get("handed_over"), f["floor"]))
for k,v in sorted(ids.items()): print(k,v)
for k in sorted(d):
    L=[x[0] for x in d[k]]
    print(k, len(L), round(st.mean(L),1), st.median(L), sorted(L), "runs", sorted(set(x[1] for x in d[k])), "lost", sum(not x[2] for x in d[k]), "handed", sum(x[3] is not None for x in d[k]))
print([ (i,r.get("ascension"),r.get("run_rules")) for i,r in enumerate(runs,1) if i in (1,27,28,90)])
