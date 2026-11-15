import sys, collections
sys.path.insert(0, "scripts")
import real_game_report as R
c = collections.defaultdict(collections.Counter)
for r in R.all_runs():
    for f in r["fights"]:
        if f["won"]: c[R.asc(r)][f["hp_after"]-f["hp_end"]] += 1
for a in c: print(a, sorted(c[a].items()))
