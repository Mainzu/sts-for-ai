import sys, statistics as st
sys.path.insert(0, r"scripts")
import os; os.chdir(r".")
import real_game_report as R
for i, r in enumerate(R.all_runs(), 1):
    if (r.get("ascension") or 0)!=20: continue
    for f in r["fights"]:
        if any("Gremlin" in m for m in f["monsters"]) and "GremlinNob" not in f["monsters"]:
            print(i, f["floor"], f["group"], f["monsters"], round(sum(f["think_s"] or []),1), f.get("decisions"))
