"""net-confidence: per card, median two-turn score gain of playing it over ending the turn (x100), and lookahead shift. python -I cards.py"""
import os, sys, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.py")).read().split('print("fights with decisions"')[0])
for a in (0, 20):
    gain = collections.defaultdict(list); gain1 = collections.defaultdict(list); nd = 0
    for x in fights:
        if x["asc"] != a: continue
        for d in x["ds"]:
            if d["two"] is None: continue
            ends = [i for i, o in enumerate(d["options"]) if o == ["End"]]
            if not ends: continue
            nd += 1; e = ends[0]; best = {}
            for i, o in enumerate(d["options"]):
                if i == e or len(o) != 1: continue
                c = nm(d, o[0])
                if c not in best or d["two"][i] > d["two"][best[c]]: best[c] = i
            for c, i in best.items():
                gain[c].append(d["two"][i] - d["two"][e]); gain1[c].append(d["one"][i] - d["one"][e])
    print(tag(a), "decisions with End and two-turn scores:", nd)
    rows = sorted(((st.median(v) * 100, len(v), c) for c, v in gain.items() if len(v) >= 20), reverse=True)
    for m, n, c in rows[:12]: print("  top %-22s median %+.1f n=%d" % (c, m, n))
    for m, n, c in rows[-6:]: print("  bot %-22s median %+.1f n=%d" % (c, m, n))
    sh = sorted(((st.median([t - o for t, o in zip(gain[c], gain1[c])]) * 100, st.mean(gain[c]) * 100 - st.mean(gain1[c]) * 100,
                  sum(t > o for t, o in zip(gain[c], gain1[c])), len(gain[c]), c) for c in gain if len(gain[c]) >= 20), reverse=True)
    for r_ in sh[:8]: print("  shift+ %-20s median %+.2f mean %+.2f raised in %d of %d" % (r_[4], r_[0], r_[1], r_[2], r_[3]))
    for r_ in sh[-5:]: print("  shift- %-20s median %+.2f mean %+.2f raised in %d of %d" % (r_[4], r_[0], r_[1], r_[2], r_[3]))
