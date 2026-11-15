"""Fun stats from the simulated headline runs. Read-only on results/gauntlet."""
import json, os, collections as C
G = "results/gauntlet"
ld = lambda n: json.load(open(os.path.join(G, n)))["sequences"]
prod = ld("net1029-hpe0.01-two-line-step-starter-simboss-a.json") + ld("net1029-hpe0.01-two-line-step-starter-simboss-500.json")
heur = ld("heuristic-starter-simboss.json")
prodA = [s for s in prod if s["i"] < 500]
print("n prod", len(prod), "heur", len(heur), "prodA", len(prodA))

def pickstats(seqs):
    off, took, skips, rewards = C.Counter(), C.Counter(), 0, 0
    for s in seqs:
        for f in s["floors"]:
            if "offer" in f:
                rewards += 1
                for c in set(f["offer"]): off[c] += 1
                if f.get("took"): took[f["took"]] += 1
                else: skips += 1
    return off, took, skips, rewards

for name, seqs in [("PROD 0-999", prod), ("PROD 0-499", prodA), ("HEUR 0-499", heur)]:
    off, took, sk, rw = pickstats(seqs)
    print(f"\n== {name}: rewards {rw}, skips {sk} ({sk/rw:.3f})")
    print(" most taken:", took.most_common(12))
    rate = sorted(((took[c]/off[c], c, took[c], off[c]) for c in off if off[c] >= 30), reverse=True)
    print(" highest take rate:", [(c, round(r,3), t, o) for r,c,t,o in rate[:12]])
    print(" lowest take rate:", [(c, round(r,3), t, o) for r,c,t,o in rate[-12:]])

# disagreement on same runs 0-499 (rate when offered)
po, pt, _, _ = pickstats(prodA); ho, ht, _, _ = pickstats(heur)
d = sorted(((pt[c]/po[c] - ht[c]/ho[c], c, round(pt[c]/po[c],3), po[c], round(ht[c]/ho[c],3), ho[c]) for c in po if po[c]>=30 and ho.get(c,0)>=30))
print("\n== disagreement (prod rate - heur rate), runs 0-499")
for x in d[:8]: print(x)
for x in d[-8:]: print(x)

# same offer on same run+floor? how often identical, and how often different choice
same = diff = 0
for a, b in zip(sorted(prodA, key=lambda s:s["i"]), sorted(heur, key=lambda s:s["i"])):
    for fa, fb in zip(a["floors"], b["floors"]):
        if "offer" in fa and "offer" in fb and fa["offer"] == fb["offer"]:
            same += 1; diff += fa.get("took") != fb.get("took")
print("\nsame offers", same, "different pick", diff)

# clears by pick (product 0-999)
n = len(prod); base = sum(s["cleared"] for s in prod)/n
print("\n== product clear rate", base)
picked = C.defaultdict(list)
cards = set(c for s in prod for f in s["floors"] for c in f.get("offer", []))
rows = []
for c in cards:
    w = [s["cleared"] for s in prod if any(f.get("took") == c for f in s["floors"])]
    wo = [s["cleared"] for s in prod if not any(f.get("took") == c for f in s["floors"])]
    if len(w) >= 40:
        rows.append((sum(w)/len(w) - sum(wo)/len(wo), c, len(w), round(sum(w)/len(w),3), round(sum(wo)/len(wo),3)))
rows.sort()
for r in rows: print(tuple(round(x,3) if isinstance(x,float) else x for x in r))

# deaths
def death(s):
    for k, f in enumerate(s["floors"]):
        if not f["won"]: return k+1, f["encounter"]
for name, seqs in [("PROD 0-999", prod), ("PROD 0-499", prodA), ("HEUR 0-499", heur)]:
    dc = C.Counter(death(s)[1] for s in seqs if death(s))
    fc = C.Counter(death(s)[0] for s in seqs if death(s))
    print(f"\n== deaths {name}: {sum(dc.values())}", dc.most_common(), sorted(fc.items()))
    boss = C.defaultdict(lambda: [0,0])
    for s in seqs:
        if len(s["floors"]) == 11:
            b = s["floors"][10]; boss[b["encounter"]][0] += 1; boss[b["encounter"]][1] += b["won"]
    print(" boss arrivals/wins", dict(boss))
    # fights faced per encounter, loss rate
    ff = C.defaultdict(lambda: [0,0])
    for s in seqs:
        for f in s["floors"]:
            ff[f["encounter"]][0] += 1; ff[f["encounter"]][1] += (not f["won"])
    print(" loss rate per enc:", sorted(((round(l/t,3), e, l, t) for e,(t,l) in ff.items()), reverse=True))
# end HP of cleared runs
eh = [s["floors"][-1]["hp_end"] for s in prod if s["cleared"]]
print("\nprod cleared end hp mean", sum(eh)/len(eh), "min", min(eh), "<=5:", sum(h<=5 for h in eh), "n", len(eh))
hh = [s["floors"][-1]["hp_end"] for s in heur if s["cleared"]]
print("heur cleared end hp mean", sum(hh)/len(hh), "n", len(hh))
# deck size: picks count
pk = [sum(1 for f in s["floors"] if f.get("took")) for s in prod]; hk=[sum(1 for f in s["floors"] if f.get("took")) for s in heur]
print("mean picks prod", sum(pk)/len(pk), "heur", sum(hk)/len(hk))
