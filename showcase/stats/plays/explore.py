import sys, collections
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
import common
from common import card_of, strip
R = common.load()
def grp(r, floor):
    for f in r["fights"]:
        if f["floor"] == floor: return f["group"]
    return "?"
for A in (0, 20):
    runs = [r for r in R if r["asc"] == A]
    plays = collections.Counter(); ndec = 0; nturn = 0
    turns = {}
    for r in runs:
        ex = common.executed(r["dec"])
        for x, acts in zip(r["dec"], ex):
            ndec += 1
            key = (r["no"], x["floor"], x["turn"])
            t = turns.setdefault(key, {"hand": None, "played": collections.Counter(), "g": grp(r, x["floor"])})
            if t["hand"] is None: t["hand"] = {strip(k): v for k, v in x["view"]["hand"].items()}; t["energy"]=x["view"]["player"]["energy"]
            for a in acts:
                if a.startswith(("End", "Choose", "Done")): continue
                if a.startswith("Potion"): continue
                plays[card_of(a)] += 1; t["played"][card_of(a)] += 1
    print("=== A", A, "runs", len(runs), "decisions", ndec, "turns", len(turns), "card plays", sum(plays.values()))
    print(plays.most_common(25))
    inh = collections.Counter(); pl = collections.Counter()
    for t in turns.values():
        for c in t["hand"]:
            inh[c] += 1
            if t["played"][c] > 0: pl[c] += 1
    rows = sorted(((pl[c] / inh[c], c, pl[c], inh[c]) for c in inh if inh[c] >= 15))
    for row in rows: print("  %.2f %s %d/%d" % row)
