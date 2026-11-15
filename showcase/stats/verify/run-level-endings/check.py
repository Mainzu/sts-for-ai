import sys, collections
sys.path.insert(0, "scripts")
import real_game_report as R
runs = R.all_runs()
print("n", len(runs))
rows = collections.defaultdict(list)
for i, r in enumerate(runs, 1):
    last = r["last"]
    bossw = any(f["group"] == "boss" and f["won"] and f["floor"] <= 17 for f in r["fights"])
    bossfight = [f for f in r["fights"] if f["group"]=="boss" and f["floor"]<=17]
    deathf = None
    if r["end"] is not None and not r["end"].get("victory"):
        deathf = last.get("floor")
    kind = ("beat" if bossw else
            "boss-death" if deathf is not None and bossfight and not bossfight[-1]["won"] else
            "death" if deathf is not None else "other")
    rr = r["run_rules"]; grp = "A%d r%s" % (R.asc(r), "3-4" if rr in (3,4) else rr)
    rows[grp].append((i, kind, deathf, last.get("act"), last.get("floor"), R.stopped(r), r["fight_guard"]))
    print(i, grp, "g%d"%r["fight_guard"], kind, "act", last.get("act"), "fl", last.get("floor"), "death", deathf, "stop", R.stopped(r), "bosses", [(f["floor"], f["won"], f.get("handed_over") is not None) for f in r["fights"] if f["group"]=="boss"])
for g, L in rows.items():
    c = collections.Counter(k for _, k, *x in L)
    print(g, len(L), (L[0][0], L[-1][0]), dict(c), "beat%%=%.1f" % (100*c["beat"]/len(L)))
    print("   death floors", sorted(x[2] for x in L if x[2] is not None))
