import sys, collections
sys.path.insert(0, "scripts")
import real_game_report as g
runs = g.all_runs()
print(len(runs))
c = collections.Counter()
for i, r in enumerate(runs, 1):
    for f in r["fights"]:
        if any("Nob" in m for m in f["monsters"]):
            c[(g.asc(r), f["won"], f.get("handed_over") is not None)] += 1
            if not f["won"] or f.get("handed_over") is not None: print(i, g.setting(r), f["floor"], f["won"], f.get("handed_over"))
print(c)
