"""Run 83 (A20 r5 g1), floor 5: the Gremlin Gang standoff, from its fight decisions.
    python -I standoff.py <this folder>"""
import sys, collections
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
import common, turns as T
R = common.load()
r = R[82]
assert r["no"] == 83
f = [x for x in r["fights"] if x["floor"] == 5][0]
print("setting", "A%d r%d g%d" % (r["asc"], r["rules"], r["guard"]), "fight", f["monsters"], "hp", f["hp_start"], "->", f["hp_end"], "won", f["won"], "decisions", f["decisions"], "think s %.1f" % sum(f["think_s"]))
ts = [t for t in T.turns([r]) if t["floor"] == 5]
print("turns", len(ts))
tgt = collections.Counter()
shield4 = 0
ex = common.executed(r["dec"])
for x, acts in zip(r["dec"], ex):
    if x["floor"] != 5: continue
    ms = x["view"]["monsters"]
    if ms[1]["hp"] == 4:
        for a in acts:
            if "@" in a and not a.startswith("Potion"):
                i = int(a.split("@")[1]); tgt[(common.card_of(a), ms[i]["name"].replace("gen:", ""), ms[i]["block"] > 0)] += 1
first4 = min(x["turn"] for x in r["dec"] if x["floor"] == 5 and x["view"]["monsters"][1]["hp"] == 4)
print("Shield Gremlin on 4 HP from turn", first4)
print("targeted plays while Shield Gremlin on 4 HP (card, target, target had block):", tgt.most_common())
for t in ts:
    if t["turn"] in (1, 5, 10, 15, 30, 45, 60, 75, 82) or t is ts[-1]:
        print(" turn", t["turn"], "hp", t["hp"])
