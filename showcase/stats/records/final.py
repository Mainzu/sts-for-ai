"""The seven fight-record tables, from records.json (run records.py first).
python -I final.py"""
import json, os, collections, statistics
rows = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "records.json")))
NAME = {"SlimeBoss": "Slime Boss", "TheGuardian": "The Guardian", "GremlinNob": "Gremlin Nob", "JawWorm": "Jaw Worm",
        "FungiBeast": "Fungi Beast", "SlaverBlue": "Blue Slaver", "SlaverRed": "Red Slaver", "SpikeSlime_L": "Large Spike Slime",
        "SpikeSlime_M": "Med. Spike Slime", "SpikeSlime_S": "Small Spike Slime", "AcidSlime_L": "Large Acid Slime",
        "AcidSlime_M": "Med. Acid Slime", "AcidSlime_S": "Small Acid Slime", "FuzzyLouseNormal": "Red Louse",
        "FuzzyLouseDefensive": "Green Louse", "GremlinWarrior": "Mad Gremlin", "GremlinTsundere": "Shield Gremlin",
        "GremlinThief": "Sneaky Gremlin", "GremlinFat": "Fat Gremlin", "GremlinWizard": "Gremlin Wizard", "Sentry": "Sentry"}
def enc(r):
    c = collections.Counter(NAME.get(m, m) for m in r["monsters"])
    return ", ".join(("%d %ss" % (n, k) if n > 1 else k) for k, n in c.items())
def tag(r): return "A%d run %d F%d %s" % (r["asc"], r["run"], r["floor"], enc(r))
act1 = [r for r in rows if r["floor"] <= 16]
net = [r for r in act1 if not r["handed"]]
def show(title, items):
    print("\n##", title)
    for label, value, note in items:
        print("%-60s %6s  %s" % (label, value, note))

# 1 longest fights (turns, from states.jsonl's turn counter)
it = []
for A, k in ((20, 6), (0, 4)):
    for r in sorted([r for r in act1 if r["asc"] == A], key=lambda r: -r["turns"])[:k]:
        it.append((tag(r), r["turns"], "%s, HP %d->%d" % ("won" if r["won"] else "lost", r["hp_start"], r["hp_end"])))
for A in (0, 20):
    t = [r["turns"] for r in act1 if r["asc"] == A]
    print("A%d median turns %s n %d" % (A, statistics.median(t), len(t)))
show("longest", it)

# 2 closest wins (lowest HP at the end of a won fight the net finished)
it = []
for A, k in ((20, 8), (0, 4)):
    for r in sorted([r for r in net if r["asc"] == A and r["won"]], key=lambda r: r["hp_end"])[:k]:
        it.append((tag(r), r["hp_end"], "of %d max, came in at %d" % (r["max_hp"], r["hp_start"])))
show("closest wins", it)
for A in (0, 20):
    w = [r for r in net if r["asc"] == A and r["won"]]
    print("A%d won net-finished act-1 fights %d, ended at <=10 HP: %d" % (A, len(w), sum(r["hp_end"] <= 10 for r in w)))

# 3 biggest HP lost in one won fight
it = []
for A, k in ((20, 7), (0, 4)):
    for r in sorted([r for r in net if r["asc"] == A and r["won"]], key=lambda r: r["hp_end"] - r["hp_start"])[:k]:
        it.append((tag(r), r["hp_start"] - r["hp_end"], "%d->%d in %d turns" % (r["hp_start"], r["hp_end"], r["turns"])))
show("biggest loss in a won fight", it)

# 4 biggest single enemy turn
it = []
for A, k in ((20, 7), (0, 5)):
    h = sorted([(x[0], x[1], x[3], r) for r in act1 if r["asc"] == A for x in r["hits"]], key=lambda x: -x[0])[:k]
    for d, t, det, r in h:
        it.append((tag(r) + " turn %d" % t, d, "%s; %s" % (det, "won" if r["won"] else "lost")))
show("biggest enemy turn", it)

# 5 bosses: fastest win, wins/fights, median turns of wins
it = []
for A in (20, 0):
    for b in ("SlimeBoss", "TheGuardian", "Hexaghost"):
        bf = [r for r in act1 if r["asc"] == A and r["group"] == "boss" and r["monsters"][0] == b]
        w = sorted([r for r in bf if r["won"]], key=lambda r: r["turns"])
        if w:
            it.append(("A%d %s" % (A, NAME.get(b, b)), w[0]["turns"], "fastest: runs %s; won %d of %d; median win %s turns"
                       % (",".join(str(r["run"]) for r in w if r["turns"] == w[0]["turns"]), len(w), len(bf), statistics.median([r["turns"] for r in w]))))
show("bosses", it)

# 6 end-of-fight heals
it = []
for A in (20, 0):
    H = [(r["hp_after"] - r["hp_end"], r) for r in rows if r["asc"] == A and r["won"] and r["hp_after"] is not None]
    for h, r in sorted(H, key=lambda x: (-x[0], x[1]["run"], x[1]["floor"]))[:4 if A == 20 else 5]:
        it.append((tag(r), h, "%d->%d; %s" % (r["hp_end"], r["hp_after"], "+".join(x for x in r["relics"] if x in ("Burning Blood", "Black Blood", "Meat on the Bone")))))
    print("A%d healed %d HP after %d won fights (all floors); Meat on the Bone fights %d, in %d runs" % (
        A, sum(h for h, _ in H), len(H), sum("Meat on the Bone" in r["relics"] for _, r in H), len({r["run"] for _, r in H if "Meat on the Bone" in r["relics"]})))
    m = [h for h, r in H if "Meat on the Bone" in r["relics"]]
    print("   heal>6 with meat", sum(x > 6 for x in m), "of", len(m))
show("heals", it)

# 7 flawless (HP end >= HP start) by encounter, won fights, net-finished, act 1; Smoke Bomb escape excluded
esc = {(65, 13)}
it = []
for A in (20, 0):
    E = collections.defaultdict(list)
    for r in net:
        if r["asc"] == A and r["won"] and (r["run"], r["floor"]) not in esc:
            E[enc(dict(r, monsters=sorted(r["monsters"])))].append(r["hp_end"] >= r["hp_start"])
    for g in ("hallway", "elite", "boss"):
        x = [r["hp_end"] >= r["hp_start"] for r in net if r["asc"] == A and r["won"] and r["group"] == g and (r["run"], r["floor"]) not in esc]
        print("A%d %s flawless %d/%d" % (A, g, sum(x), len(x)))
    if A == 20:
        for k, v in sorted(E.items(), key=lambda kv: (-sum(kv[1]) / len(kv[1]), -len(kv[1]))):
            if len(v) >= 12:
                it.append(("A20 " + k, round(100 * sum(v) / len(v)), "%d of %d" % (sum(v), len(v))))
show("flawless A20 n>=12", it)
for r in net:
    if r["won"] and r["hp_end"] >= r["hp_start"] and r["group"] != "hallway":
        print("flawless", tag(r), r["turns"], "turns", "(smoke bomb)" if (r["run"], r["floor"]) in esc else "")
