"""Energy left when it ends a turn, from the game's own states (states.jsonl, streamed):
the last combat state of turn T before a state of turn T+1 on the same floor is the one
the controller answered with "end". Fights the fallback rule finished are left out.
    python -I energy.py <this folder>"""
import sys, os, json, collections
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
import common

R = common.load()
byseed = {(r["folder"], r["seed"]): r for r in R}
ends = []  # (run, floor, group, energy, playable-and-affordable cards in hand, hand names)
for name in sorted(os.listdir(common.rg.RECORDS)):
    folder = os.path.join(common.rg.RECORDS, name)
    p = os.path.join(folder, "states.jsonl")
    if not (os.path.isdir(folder) and name[:1].isdigit() and os.path.exists(p)):
        continue
    prev = None
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            gs = json.loads(line)["msg"].get("game_state")
            if not gs or "combat_state" not in gs:
                prev = None
                continue
            cs = gs["combat_state"]
            cur = (gs.get("seed"), gs.get("floor"), cs.get("turn"), cs)
            if prev and prev[0] == cur[0] and prev[1] == cur[1] and cur[2] == prev[2] + 1:
                r = byseed.get((name, prev[0]))
                if r:
                    fl = [x for x in r["fights"] if x["floor"] == prev[1]]
                    if fl and fl[0].get("handed_over") is None:
                        pc = prev[3]
                        en = pc["player"]["energy"]
                        hand = pc["hand"]
                        aff = [c["name"] for c in hand if c.get("is_playable") and 0 <= c["cost"] <= en]
                        ends.append((r, prev[1], fl[0]["group"], en, aff, [c["name"] for c in hand], pc["player"].get("powers", []), "+".join(sorted({m["name"] for m in pc["monsters"] if not m.get("is_gone")})), prev[2]))
            prev = cur

for A in (0, 20):
    e = [x for x in ends if x[0]["asc"] == A]
    lab = "A0 runs 1-27" if A == 0 else "A20 runs 28-90 pooled"
    n = len(e)
    left = [x for x in e if x[3] > 0]
    withcard = [x for x in left if x[4]]
    print(lab, "turn ends", n, "energy left >0:", len(left), "%.1f%%" % (100 * len(left) / n),
          "with an affordable playable card:", len(withcard), "%.1f%%" % (100 * len(withcard) / n))
    print("  energy left dist", sorted(collections.Counter(x[3] for x in e).items()))
    for g in ("hallway", "elite", "boss"):
        eg = [x for x in e if x[2] == g]
        print("  ", g, len(eg), "left", sum(x[3] > 0 for x in eg), "with card", sum(1 for x in eg if x[3] > 0 and x[4]))
    held = collections.Counter(c for x in withcard for c in set(x[4]))
    print("  cards left affordable", held.most_common(15))
    # Ice Cream / conserve relics?
    tot = collections.Counter(x[7] for x in e)
    wc = collections.Counter(x[7] for x in withcard)
    print("  by monsters (turn ends with energy and an affordable card / turn ends):")
    for k, v in sorted(tot.items(), key=lambda kv: -wc[kv[0]])[:12]:
        print("    %s %d/%d" % (k, wc[k], v))
    print("  Havoc ends:", collections.Counter(x[7] for x in withcard if "Havoc" in x[4]).most_common(6))
    print("  Strike ends:", collections.Counter(x[7] for x in withcard if "Strike" in x[4]).most_common(8))
    print("  sample", [(x[0]["no"], x[1], x[3], x[4]) for x in withcard[:8]])

if len(sys.argv) > 2:
    key = sys.argv[2]
    sel = [x for x in ends if x[7] == key and x[3] > 0 and x[4]]
    print(key, collections.Counter((x[0]["no"], x[1]) for x in sel))
    allk = [x for x in ends if x[7] == key]
    print("all turn ends by fight", collections.Counter((x[0]["no"], x[1]) for x in allk))
