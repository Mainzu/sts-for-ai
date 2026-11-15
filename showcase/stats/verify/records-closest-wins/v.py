import sys
sys.path.insert(0, "scripts")
import os
os.chdir(".")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
stats = {}
rows = []
for i, r in enumerate(runs, 1):
    a = R.asc(r)
    for f in r["fights"]:
        if not f["won"] or f.get("handed_over") is not None or not (1 <= f["floor"] <= 16):
            continue
        stats.setdefault(a, [0, 0])
        stats[a][0] += 1
        mx = r["hp"].get(f["floor"], (None, None))[1]
        if f["hp_end"] <= 13:
            rows.append((a, f["hp_end"], i, f["floor"], f["monsters"], mx, f["hp_start"], f.get("hp_after"), R.setting_tag(r), f["group"]))
        if f["hp_end"] <= 10:
            stats[a][1] += 1
print(stats)
for x in sorted(rows): print(x)
# check handed over act1 low wins and other excluded
for i, r in enumerate(runs, 1):
    for f in r["fights"]:
        if f["won"] and f.get("handed_over") is not None and f["hp_end"] <= 10:
            print("handed", i, R.asc(r), f["floor"], f["monsters"], f["hp_end"], f["handed_over"])
print("act2+ net-finished wins:")
for i, r in enumerate(runs, 1):
    for f in r["fights"]:
        if f["floor"] > 16 and f["won"] and f.get("handed_over") is None:
            print(i, R.asc(r), f["floor"], f["monsters"], f["hp_end"])
