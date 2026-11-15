"""net-confidence stats: calibration, confident losses, one- vs two-turn picks, card value vs End.
python -I stats.py"""
import os, sys, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import runs, strip, card_of

rs = runs()
def nm(d, a):
    if a.startswith("Potion:"):
        k = int(a.split(":")[1].split("@")[0])
        try: return "potion " + strip(d["view"]["player"]["potions"][k])
        except Exception: return "potion ?"
    return card_of(a)
def tag(a): return "A20" if a else "A0"

# ---- fight-level join
fights = []  # (asc, run, fight, start_score, decisions)
for r in rs:
    byfl = collections.defaultdict(list)
    for d in r["decisions"]:
        if "turn" in d:
            byfl[d["floor"]].append(d)
    for f in r["fights"]:
        ds = byfl.get(f["floor"])
        if not ds:
            continue
        d0 = ds[0]
        s0 = (d0["two"] or d0["one"])[d0["pick"]]
        fights.append(dict(asc=r["asc"], run=r["n"], rules=r["rules"], guard=r["guard"], f=f, s0=s0, ds=ds,
                           out=(2 - max(0, f["hp_start"] - f["hp_after"]) / 100) if f["won"] else 0.0))
print("fights with decisions", collections.Counter(tag(x["asc"]) for x in fights))
print("handed over", collections.Counter(tag(x["asc"]) for x in fights if x["f"]["handed_over"]))

print("\n== 1 calibration (not handed over) ==")
edges = [0, 1.0, 1.5, 1.7, 1.8, 1.85, 1.9, 1.95, 2.01]
for a in (0, 20):
    xs = [x for x in fights if x["asc"] == a and not x["f"]["handed_over"]]
    print(tag(a), "n", len(xs), "losses", sum(1 for x in xs if not x["f"]["won"]))
    for lo, hi in zip(edges, edges[1:]):
        b = [x for x in xs if lo <= x["s0"] < hi]
        if b:
            print("  [%.2f,%.2f) n=%d win=%d/%d (%.1f%%) mean pred %.3f mean actual %.3f" % (
                lo, hi, len(b), sum(x["f"]["won"] for x in b), len(b), 100 * sum(x["f"]["won"] for x in b) / len(b),
                st.mean(x["s0"] for x in b), st.mean(x["out"] for x in b)))
    w = [x for x in xs if x["f"]["won"]]
    # predicted HP loss vs actual for won fights
    print("  won fights: mean predicted HP lost %.1f, actual %.1f, n=%d" % (
        st.mean((2 - x["s0"]) * 100 for x in w), st.mean((2 - x["out"]) * 100 for x in w), len(w)))

print("\n== 2 most confident losses ==")
for a in (0, 20):
    xs = sorted([x for x in fights if x["asc"] == a and not x["f"]["won"]], key=lambda x: -x["s0"])
    print(tag(a), "losses", len(xs))
    for x in xs[:12]:
        f = x["f"]
        print("  run %d fl %d %s %s s0=%.3f hp_start %d handed %s turns %d guard %d rules %d" % (
            x["run"], f["floor"], f["group"], ",".join(f["monsters"]), x["s0"], f["hp_start"], f["handed_over"],
            max(d["turn"] for d in x["ds"]), x["guard"], x["rules"]))
    # lowest-score wins (biggest pleasant surprises)
    ws = sorted([x for x in fights if x["asc"] == a and x["f"]["won"]], key=lambda x: x["s0"])
    print(tag(a), "lowest-score wins")
    for x in ws[:6]:
        f = x["f"]
        print("  run %d fl %d %s %s s0=%.3f hp %d->%d handed %s" % (x["run"], f["floor"], f["group"], ",".join(f["monsters"]),
              x["s0"], f["hp_start"], f["hp_after"], f["handed_over"]))

print("\n== 3 one-turn vs two-turn pick ==")
EPS = 1e-9
for a in (0, 20):
    nd = nch = 0
    swaps = collections.Counter(); from_one = collections.Counter(); to_two = collections.Counter()
    seen_card = collections.Counter()
    biggest = []
    for x in fights:
        if x["asc"] != a: continue
        for d in x["ds"]:
            if len(d["options"]) < 2 or d["two"] is None: continue
            nd += 1
            one, two, p = d["one"], d["two"], d["pick"]
            m1 = max(one)
            best1 = [i for i, v in enumerate(one) if v >= m1 - EPS]
            if p not in best1:
                nch += 1
                o = nm(d, d["options"][best1[0]][0]); t = nm(d, d["options"][p][0])
                if o != t:
                    swaps[(o, t)] += 1
                from_one[o] += 1; to_two[t] += 1
            # option whose rank moved: largest (two-one) gap relative to End? record largest |delta of delta| vs pick
            dd = [two[i] - one[i] for i in range(len(one))]
            spread = max(dd) - min(dd)
            biggest.append((spread, x["run"], d["floor"], d["turn"], ",".join(x["f"]["monsters"]),
                            [(nm(d, o[0]), round(one[i], 3), round(two[i], 3)) for i, o in enumerate(d["options"])], p))
    print(tag(a), "decisions", nd, "changed", nch, "%.1f%%" % (100 * nch / nd))
    print("  one-turn first choice overruled:", from_one.most_common(10))
    print("  two-turn pick instead:", to_two.most_common(10))
    print("  swaps:", swaps.most_common(12))
    biggest.sort(reverse=True)
    for b in biggest[:4]:
        print("  BIG", b[:5], "pick", b[6]); print("     ", b[5])

print("\n== 4 card value vs End (two-turn score minus End's, same decision) ==")
for a in (0, 20):
    gain = collections.defaultdict(list); gain1 = collections.defaultdict(list)
    for x in fights:
        if x["asc"] != a: continue
        for d in x["ds"]:
            if d["two"] is None: continue
            ends = [i for i, o in enumerate(d["options"]) if o == ["End"]]
            if not ends: continue
            e = ends[0]
            best = {}
            for i, o in enumerate(d["options"]):
                if i == e or len(o) != 1: continue
                c = nm(d, o[0])
                # best target per card
                if c not in best or d["two"][i] > d["two"][best[c]]:
                    best[c] = i
            for c, i in best.items():
                gain[c].append(d["two"][i] - d["two"][e]); gain1[c].append(d["one"][i] - d["one"][e])
    rows = [(st.mean(v) * 100, st.median(v) * 100, len(v), st.mean(gain1[c]) * 100, c) for c, v in gain.items() if len(v) >= 20]
    rows.sort(reverse=True)
    print(tag(a), "cards with n>=20:", len(rows))
    for r_ in rows[:14]: print("  %-22s mean %+.2f  median %+.2f  n=%d  one-turn mean %+.2f" % (r_[4], r_[0], r_[1], r_[2], r_[3]))
    print("  ...bottom")
    for r_ in rows[-8:]: print("  %-22s mean %+.2f  median %+.2f  n=%d  one-turn mean %+.2f" % (r_[4], r_[0], r_[1], r_[2], r_[3]))
    # where two-turn view differs most from one-turn: mean(two gain - one gain)
    diff = sorted(((st.mean(gain[c]) - st.mean(gain1[c])) * 100, len(gain[c]), c) for c in gain if len(gain[c]) >= 20)
    print("  lookahead raises most:", [("%s %+.2f n=%d" % (c, v, n)) for v, n, c in diff[::-1][:8]])
    print("  lookahead lowers most:", [("%s %+.2f n=%d" % (c, v, n)) for v, n, c in diff[:8]])
