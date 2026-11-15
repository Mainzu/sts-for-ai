"""Turn-level table for both ascensions: per (run, floor, turn) the hand at the turn's first
decision, the cards and potions actually sent, the fight group, HP."""
import sys, collections
import common
from common import card_of, strip


def base(n):
    return strip(n.split("{")[0])


def turns(R):
    out = []
    for r in R:
        groups = {f["floor"]: f for f in r["fights"]}
        ex = common.executed(r["dec"])
        cur = None
        for x, acts in zip(r["dec"], ex):
            key = (r["no"], x["floor"], x["turn"])
            if cur is None or cur["key"] != key:
                v = x["view"]
                f = groups.get(x["floor"], {})
                cur = {"key": key, "run": r, "asc": r["asc"], "floor": x["floor"], "turn": x["turn"],
                       "group": f.get("group", "?"), "boss": v.get("boss_fight"),
                       "hand": collections.Counter(),
                       "hp": v["player"]["hp"], "max_hp": v["player"]["max_hp"], "energy": v["player"]["energy"],
                       "potions": list(v["player"]["potions"]), "monsters": [m["name"] for m in v["monsters"]],
                       "acts": [], "pots": [], "decs": 0, "seconds": 0.0}
                for k, n in v["hand"].items():
                    cur["hand"][base(k)] += n
                out.append(cur)
            cur["decs"] += 1
            cur["seconds"] += x.get("seconds") or 0
            pots = x["view"]["player"]["potions"]
            for a in acts:
                if a.startswith("Potion:"):
                    slot = int(a[7:].split("@")[0])
                    name = strip(pots[slot]) if slot < len(pots) else "?"
                    cur["pots"].append((name, x["view"]["player"]["hp"], x["view"]["player"]["max_hp"]))
                elif not a.startswith(("End", "Choose", "Done")):
                    cur["acts"].append(card_of(a))
    return out
