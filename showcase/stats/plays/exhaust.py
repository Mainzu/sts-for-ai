"""Exhaust habits and Gremlin Nob counts.
    python -I exhaust.py <this folder>"""
import sys, collections
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
import common, turns as T

R = common.load()
TT = T.turns(R)
EXHAUSTERS = ("True Grit", "True Grit+", "Fiend Fire", "Fiend Fire+", "Burning Pact", "Burning Pact+", "Second Wind", "Second Wind+", "Sever Soul", "Sever Soul+")
for A in (0, 20):
    lab = "A0 runs 1-27" if A == 0 else "A20 runs 28-90 pooled"
    # last decision view per fight: exhaust pile
    pile = collections.Counter()
    nf = 0
    for r in R:
        if r["asc"] != A:
            continue
        last = {}
        for x in r["dec"]:
            last[x["floor"]] = x
        for fl, x in last.items():
            nf += 1
            for k, n in x["view"]["exhaust"].items():
                pile[T.base(k)] += n
    print(lab, "fights", nf, "exhaust piles at the last decision:", pile.most_common(20))
    plays = collections.Counter(a for t in TT if t["asc"] == A for a in t["acts"] if a.split("+")[0] in [e.split("+")[0] for e in EXHAUSTERS])
    print("  exhauster plays", plays)
    # Nob
    nob = [t for t in TT if t["asc"] == A and "Gremlin Nob" in t["monsters"]]
    c = collections.Counter(a for t in nob for a in t["acts"])
    fights = {(t["run"]["no"], t["floor"]) for t in nob}
    skills = sum(v for k, v in c.items() if k.split("+")[0] in ("Defend", "Shrug It Off", "Armaments", "True Grit", "Ghostly Armor", "Flame Barrier", "Second Wind", "Power Through", "Disarm", "Shockwave", "Spot Weakness", "Intimidate", "Warcry", "Havoc", "Seeing Red", "Dual Wield", "Entrench", "Impervious", "Rage", "Flex", "Bloodletting", "Burning Pact", "Infernal Blade", "Double Tap", "Battle Trance", "Exhume", "Limit Break", "Offering", "Sentinel"))
    print("  Gremlin Nob fights", len(fights), "turns", len(nob), "plays", c.most_common(), "skill plays", skills, "of", sum(c.values()))
    oth = [t for t in TT if t["asc"] == A and t["group"] == "elite" and "Gremlin Nob" not in t["monsters"]]
    c2 = collections.Counter(a for t in oth for a in t["acts"])
    print("  other elites: Defend", c2["Defend"] + c2["Defend+"], "Strike", c2["Strike"] + c2["Strike+"], "turns", len(oth))
    hd = sum(1 for t in nob if t["hand"].get("Defend") or t["hand"].get("Defend+"))
    pdd = sum(1 for t in nob if (t["hand"].get("Defend") or t["hand"].get("Defend+")) and any(a.startswith("Defend") for a in t["acts"]))
    print("  Nob turns holding a Defend", hd, "played one", pdd)
    ho = sum(1 for t in oth if t["hand"].get("Defend") or t["hand"].get("Defend+"))
    po = sum(1 for t in oth if (t["hand"].get("Defend") or t["hand"].get("Defend+")) and any(a.startswith("Defend") for a in t["acts"]))
    print("  other elite turns holding a Defend", ho, "played one", po)
    nobwon = [f for r in R if r["asc"] == A for f in r["fights"] if "GremlinNob" in f["monsters"]]
    print("  Nob fights won", sum(f["won"] for f in nobwon), "of", len(nobwon), "hp lost", [f["hp_start"] - f["hp_end"] for f in nobwon])
