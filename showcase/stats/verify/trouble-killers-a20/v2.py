import sys, collections
sys.path.insert(0, r"scripts")
import real_game_report as R
runs = R.all_runs()
a20 = [(i+1, r) for i, r in enumerate(runs) if r.get("ascension") == 20]
runsmet = collections.Counter()
for i, r in a20:
    for k in {"+".join(f["monsters"]) for f in r["fights"]}: runsmet[k] += 1
for k in ["Hexaghost","Lagavulin","SlimeBoss","TheGuardian","GremlinNob","Sentry+Sentry+Sentry","SpikeSlime_L","AcidSlime_L","Looter"]:
    print(k, runsmet[k])
# boss per run in a20 (act1_boss)
print(collections.Counter(r.get("act1_boss") for i,r in a20))
# Hexaghost by rules
for i,r in a20:
    hx=[f for f in r["fights"] if f["monsters"]==["Hexaghost"]]
    if hx: print(i, r["run_rules"], r["fight_guard"], hx[0]["won"], hx[0]["hp_start"])
