"""net-confidence extras: per-encounter over/under-confidence; size of one-turn gap on overrules. python -I extra.py"""
import os, sys, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.py")).read().split('print("fights with decisions"')[0])
NAMES = {"FuzzyLouseNormal": "Louse", "FuzzyLouseDefensive": "Louse"}
def enc(f):
    m = f["monsters"]
    if f["group"] != "hallway" or len(set(m)) == 1:
        return f["group"] + ": " + " + ".join(sorted(set(m)))
    return "hallway: " + " + ".join(sorted(set(NAMES.get(x, x) for x in m)))
for a in (0, 20):
    g = collections.defaultdict(list)
    for x in fights:
        if x["asc"] == a and not x["f"]["handed_over"]:
            g[enc(x["f"])].append(x)
    rows = []
    for k, xs in g.items():
        if len(xs) >= 6:
            rows.append((st.mean(x["s0"] - x["out"] for x in xs) * 100, len(xs), sum(not x["f"]["won"] for x in xs),
                         st.mean(x["s0"] for x in xs), st.mean(x["out"] for x in xs), k,
                         st.mean((2 - x["s0"]) * 100 for x in xs if x["f"]["won"]) if any(x["f"]["won"] for x in xs) else None,
                         st.mean(x["f"]["hp_start"] - x["f"]["hp_after"] for x in xs if x["f"]["won"]) if any(x["f"]["won"] for x in xs) else None))
    rows.sort(reverse=True)
    print(tag(a))
    for r_ in rows:
        print("  %-55s over %+6.1f n=%d lost=%d pred %.3f act %.3f | won: pred HP lost %s actual %s" % (r_[5], r_[0], r_[1], r_[2], r_[3], r_[4],
              "%.1f" % r_[6] if r_[6] is not None else "-", "%.1f" % r_[7] if r_[7] is not None else "-"))
# Lagavulin detail
for a in (0, 20):
    xs = [x for x in fights if x["asc"] == a and "Lagavulin" in x["f"]["monsters"]]
    print(tag(a), "Lagavulin", len(xs), "lost", sum(not x["f"]["won"] for x in xs), [("r%d" % x["run"], round(x["s0"], 2), x["f"]["hp_start"], x["f"]["hp_after"] if x["f"]["won"] else 0) for x in xs])
# overrule gap
for a in (0, 20):
    gaps = []; dts = []
    for x in fights:
        if x["asc"] != a: continue
        for d in x["ds"]:
            if len(d["options"]) < 2 or d["two"] is None: continue
            one, two, p = d["one"], d["two"], d["pick"]
            if one[p] < max(one) - 1e-9:
                gaps.append((max(one) - one[p]) * 100)
                b = max(range(len(one)), key=lambda i: one[i])
                dts.append((two[p] - two[b]) * 100)
    gaps.sort()
    print(tag(a), "overrules", len(gaps), "one-turn gap median %.2f, >1 HP-equiv: %d, >5: %d" % (st.median(gaps), sum(g > 1 for g in gaps), sum(g > 5 for g in gaps)),
          "two-turn gain median %.2f" % st.median(dts))
# cut rate
for a in (0, 20):
    n = c = 0
    for x in fights:
        if x["asc"] != a: continue
        for d in x["ds"]:
            n += 1; c += d.get("cut", False)
    print(tag(a), "decisions", n, "cut", c)
