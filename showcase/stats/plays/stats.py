"""Card-play statistics from the real-game records.
    python -I stats.py <this folder> [t1|pot|ds|rate|ex|all]"""
import sys, collections, statistics
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
import common, turns as T

R = common.load()
TT = T.turns(R)
which = sys.argv[2] if len(sys.argv) > 2 else "all"


def label(a):
    return "A0 (runs 1-27)" if a == 0 else "A20 (runs 28-90, rule versions pooled)"


def isbash(a):
    return a.startswith("Bash")


if which in ("all", "t1"):
    print("## turn 1: first card played; Bash first when Bash in opening hand")
    for A in (0, 20):
        t1 = [t for t in TT if t["asc"] == A and t["turn"] == 1]
        first = collections.Counter(t["acts"][0] if t["acts"] else "(nothing)" for t in t1)
        print(label(A), "fights with turn-1 decisions", len(t1))
        print(first.most_common(12))
        hb = [t for t in t1 if t["hand"].get("Bash", 0) or t["hand"].get("Bash+", 0)]
        bf = sum(1 for t in hb if t["acts"] and isbash(t["acts"][0]))
        bp = sum(1 for t in hb if any(isbash(a) for a in t["acts"]))
        print("  Bash in opening hand", len(hb), "Bash first", bf, "Bash played turn1", bp)
        for g in ("hallway", "elite", "boss"):
            h = [t for t in hb if t["group"] == g]
            print("   ", g, len(h), "first", sum(1 for t in h if t["acts"] and isbash(t["acts"][0])),
                  "played", sum(1 for t in h if any(isbash(a) for a in t["acts"])))
        print("  first when Bash held but not first:",
              collections.Counter(t["acts"][0] if t["acts"] else "-" for t in hb if not (t["acts"] and isbash(t["acts"][0]))).most_common(6))
        by = collections.defaultdict(lambda: [0, 0])
        for t in hb:
            k = "+".join(sorted(set(t["monsters"])))
            by[k][1] += 1
            by[k][0] += any(isbash(a) for a in t["acts"])
        for k, v in sorted(by.items(), key=lambda kv: -kv[1][1])[:14]:
            print("    %s: played %d of %d" % (k, v[0], v[1]))

if which in ("all", "pot"):
    print("## potions")
    for A in (0, 20):
        ts = [t for t in TT if t["asc"] == A]
        uses = [(p, t) for t in ts for p in t["pots"]]
        print(label(A), "uses", len(uses))
        print(" by potion", collections.Counter(p[0] for p, t in uses).most_common(15))
        print(" by group", collections.Counter(t["group"] for p, t in uses))
        print(" turn", collections.Counter(min(t["turn"], 5) for p, t in uses))
        hp = [p[1] / p[2] for p, t in uses]
        if hp:
            print(" HP frac median %.2f below half %d" % (statistics.median(hp), sum(h < .5 for h in hp)))
        held = collections.Counter()
        for t in ts:
            for p in t["potions"]:
                held[common.strip(p)] += 1
        print(" turns held", held.most_common(15))
        fights = collections.Counter(f["group"] for r in R if r["asc"] == A for f in r["fights"])
        print(" fights by group", fights)
        print(" uses by potion x group", sorted(collections.Counter((p[0], t["group"]) for p, t in uses).items()))

if which in ("all", "ds"):
    print("## Defend vs Strike by group")
    for A in (0, 20):
        for g in ("hallway", "elite", "boss"):
            ts = [t for t in TT if t["asc"] == A and t["group"] == g]
            c = collections.Counter(a for t in ts for a in t["acts"])
            d = c["Defend"] + c["Defend+"]
            s = c["Strike"] + c["Strike+"]
            print(label(A), g, "turns", len(ts), "Defend", d, "Strike", s, "ratio %.2f" % (d / s if s else 0))
    for A in (0, 20):
        ts = [t for t in TT if t["asc"] == A]
        by = collections.defaultdict(collections.Counter)
        for t in ts:
            k = "+".join(sorted(set(t["monsters"])))
            for a in t["acts"]:
                if a in ("Defend", "Defend+"):
                    by[k]["d"] += 1
                if a in ("Strike", "Strike+"):
                    by[k]["s"] += 1
            by[k]["turns"] += 1
        print(label(A), "per monster set (>=40 Strike+Defend plays)")
        rows = sorted(((v["d"] / max(1, v["s"]), k, v["d"], v["s"], v["turns"]) for k, v in by.items() if v["d"] + v["s"] >= 40), reverse=True)
        for row in rows:
            print("  %.2f %s D%d S%d turns%d" % row)

if which in ("all", "rate"):
    print("## play rate when in the turn's starting hand")
    for A in (0, 20):
        ts = [t for t in TT if t["asc"] == A]
        inh = collections.Counter()
        pl = collections.Counter()
        for t in ts:
            for c in t["hand"]:
                inh[c] += 1
                if c in t["acts"]:
                    pl[c] += 1
        print(label(A), "turns", len(ts))
        for row in sorted(((pl[c] / inh[c], c, pl[c], inh[c]) for c in inh if inh[c] >= 20)):
            print("  %.2f %s %d/%d" % row)

if which in ("all", "most"):
    print("## most played")
    for A in (0, 20):
        ts = [t for t in TT if t["asc"] == A]
        c = collections.Counter(a for t in ts for a in t["acts"])
        nf = sum(len(r["fights"]) for r in R if r["asc"] == A)
        print(label(A), "plays", sum(c.values()), "fights", nf, "turns", len(ts))
        print(c.most_common(14))
