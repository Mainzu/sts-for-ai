"""Reads records.json (from records.py) and prints the fight records.
python -I analyse.py"""
import json, os, collections
rows = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "records.json")))
def enc(r): return " + ".join(collections.OrderedDict.fromkeys(r["monsters"])) if len(set(r["monsters"])) < len(r["monsters"]) and len(set(r["monsters"]))==1 and False else ", ".join(r["monsters"])
def tag(r): return "run %d F%d %s %s" % (r["run"], r["floor"], r["group"], enc(r))
for A in (0, 20):
    S = [r for r in rows if r["asc"] == A]
    print("\n===== A%d: %d fights, runs %s-%s" % (A, len(S), min(r["run"] for r in S), max(r["run"] for r in S)))
    print("-- longest (turns)")
    for r in sorted(S, key=lambda r: -(r["turns"] or 0))[:10]:
        print(r["turns"], tag(r), "won" if r["won"] else "LOST", r["hp_start"], "->", r["hp_end"], "handed" if r["handed"] else "")
    tl = [r["turns"] for r in S if r["turns"]]
    print("mean turns", sum(tl) / len(tl), "n", len(tl), "missing", len(S) - len(tl))
    print("-- closest wins")
    for r in sorted([r for r in S if r["won"]], key=lambda r: r["hp_end"])[:10]:
        print(r["hp_end"], "/", r["max_hp"], tag(r), "from", r["hp_start"], "turns", r["turns"], "handed" if r["handed"] else "")
    print("-- biggest loss in won fight")
    for r in sorted([r for r in S if r["won"]], key=lambda r: r["hp_end"] - r["hp_start"])[:10]:
        print(r["hp_start"] - r["hp_end"], tag(r), r["hp_start"], "->", r["hp_end"], "turns", r["turns"])
    print("-- losses", sum(not r["won"] for r in S))
    for r in [r for r in S if not r["won"]]:
        print(" ", tag(r), r["hp_start"], "turns", r["turns"], "handed" if r["handed"] else "")
    print("-- biggest single monster turn")
    hits = [(h[0], h[1], h[2], h[3], r) for r in S for h in r["hits"]]
    for d, t, mon, det, r in sorted(hits, key=lambda x: -x[0])[:12]:
        print(d, "turn", t, "->", t + 1, tag(r), det, "won" if r["won"] else "LOST")
    print("-- fastest boss wins")
    for r in sorted([r for r in S if r["group"] == "boss" and r["won"]], key=lambda r: r["turns"] or 99)[:10]:
        print(r["turns"], tag(r), r["hp_start"], "->", r["hp_end"])
    bw = [r for r in S if r["group"] == "boss"]
    print("boss fights", len(bw), "won", sum(r["won"] for r in bw))
    for b in sorted(set(r["monsters"][0] for r in bw)):
        x = [r["turns"] for r in bw if r["monsters"][0] == b and r["won"]]
        print("  ", b, "won", len(x), "of", sum(r["monsters"][0] == b for r in bw), "turns", sorted(x))
    print("-- end-of-fight heals")
    H = [(r["hp_after"] - r["hp_end"], r) for r in S if r["won"] and r["hp_after"] is not None]
    for h, r in sorted(H, key=lambda x: -x[0])[:10]:
        print(h, tag(r), r["hp_end"], "->", r["hp_after"], "/", r["max_hp"], [x for x in (r["relics"] or []) if x in ("Burning Blood", "Black Blood", "Meat on the Bone")])
    print("total healed", sum(h for h, _ in H), "over", len(H), "won fights; mean", sum(h for h, _ in H) / len(H))
    rel = collections.Counter()
    for h, r in H:
        k = tuple(x for x in (r["relics"] or []) if x in ("Burning Blood", "Black Blood", "Meat on the Bone"))
        rel[k] += 1
    print(rel)
    print("-- flawless by encounter")
    E = collections.defaultdict(list)
    for r in S:
        if r["won"]:
            E[(r["group"], ", ".join(sorted(r["monsters"])))].append(r["hp_end"] >= r["hp_start"])
    for k, v in sorted(E.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        if len(v) >= 3:
            print("%5.2f %d/%d %s" % (sum(v) / len(v), sum(v), len(v), k))
    fl = [r for r in S if r["won"] and r["hp_end"] >= r["hp_start"]]
    print("flawless total", len(fl), "of won", sum(r["won"] for r in S))
    for g in ("hallway", "elite", "boss"):
        x = [r["hp_end"] >= r["hp_start"] for r in S if r["won"] and r["group"] == g]
        print(" ", g, sum(x), "/", len(x))
    for r in fl:
        if r["group"] != "hallway":
            print("   flawless", tag(r), "turns", r["turns"])
