import sys, collections
sys.path.insert(0, r"scripts")
import os; os.chdir(r".")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
agg = collections.defaultdict(list)
for i, r in enumerate(runs, 1):
    a = r.get("ascension") or 0
    for f in r["fights"]:
        if f.get("group") == "boss":
            lost = f["hp_start"] - f["hp_end"]
            agg[(a, tuple(f["monsters"]))].append((i, f["won"], lost, f.get("handed_over"), r.get("run_rules"), r.get("fight_guard"), f["hp_start"], f["hp_end"]))
for k, v in sorted(agg.items()):
    w = sum(1 for x in v if x[1]); print(k, len(v), w, round(100*w/len(v)), round(sum(x[2] for x in v)/len(v),1))
    for x in v: print("   ", x)
