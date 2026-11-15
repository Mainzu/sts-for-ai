import sys, collections
sys.path.insert(0, r"scripts")
import real_game_report as R
runs = R.all_runs()
print("total runs", len(runs))
a20 = [(i+1, r) for i, r in enumerate(runs) if r.get("ascension") == 20]
print("a20", len(a20), a20[0][0], a20[-1][0])
deaths = collections.Counter(); met = collections.Counter(); ndeath = 0
other = []
def name(f): return "+".join(f["monsters"])
for i, r in a20:
    seen = set()
    for f in r["fights"]:
        met[name(f)] += 1
    lost = [f for f in r["fights"] if not f["won"]]
    died = r["end"] is not None and not r["end"].get("victory")
    if died:
        ndeath += 1
        if lost:
            f = lost[-1]; deaths[name(f)] += 1
            other.append((i, name(f), f["floor"], f["hp_start"], f.get("handed_over"), len(lost)))
        else:
            other.append((i, "NOLOSTFIGHT", r.get("last_monsters"), r["last"].get("floor")))
    elif lost:
        print("lost fight but no death", i, [name(f) for f in lost])
    if r["end"] is None:
        print("no end", i, r["last"].get("floor"), R.stopped(r))
print("deaths", ndeath)
for k, v in deaths.most_common(): print(v, k, "met", met[k])
for o in other: print(o)
print("rules", collections.Counter((r["run_rules"], r["fight_guard"]) for i, r in a20))
