"""net-confidence: decisions where two-turn and one-turn scores of the chosen option differ most, with the fight's outcome. python -I swing.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.py")).read().split('print("fights with decisions"')[0])
for a in (0, 20):
    rows = []; n = 0
    for x in fights:
        if x["asc"] != a: continue
        for d in x["ds"]:
            if d["two"] is None or len(d["options"]) < 2: continue
            n += 1
            p = d["pick"]
            rows.append((d["two"][p] - max(d["one"]), x["run"], d["floor"], d["turn"], ",".join(x["f"]["monsters"]), nm(d, d["options"][p][0]),
                         round(max(d["one"]), 3), round(d["two"][p], 3), d["view"]["player"]["hp"], x["f"]["won"], x["f"]["hp_after"], x["f"]["handed_over"]))
    rows.sort()
    print(tag(a), n)
    for r_ in rows[-6:][::-1]: print("  up", r_)
    for r_ in rows[:6]: print("  down", r_)
