"""Clear rate by card pick, within the half of runs where the card can be offered."""
import json, os, collections as C
G = "results/gauntlet"
ld = lambda n: json.load(open(os.path.join(G, n)))["sequences"]
prod = ld("net1029-hpe0.01-two-line-step-starter-simboss-a.json") + ld("net1029-hpe0.01-two-line-step-starter-simboss-500.json")
heur = ld("heuristic-starter-simboss.json")
for nm, seqs in [("prod 0-999", prod), ("heur 0-499", heur)]:
    hc = C.defaultdict(lambda: [0, 0])
    for s in seqs: hc[s["half"]][0] += 1; hc[s["half"]][1] += s["cleared"]
    print(nm, dict(hc))
offered_in = C.defaultdict(C.Counter)
for s in prod:
    for f in s["floors"]:
        for c in f.get("offer", []): offered_in[c][s["half"]] += 1
for c, v in sorted(offered_in.items()): print(c, dict(v))
print("\n== clear rate with/without pick, within runs where the card was offered at least once (product 0-999)")
rows = []
for c in offered_in:
    pool = [s for s in prod if any(c in f.get("offer", []) for f in s["floors"])]
    w = [s["cleared"] for s in pool if any(f.get("took") == c for f in s["floors"])]
    wo = [s["cleared"] for s in pool if not any(f.get("took") == c for f in s["floors"])]
    if len(w) >= 40 and len(wo) >= 40:
        rows.append((round(sum(w)/len(w) - sum(wo)/len(wo), 3), c, len(w), sum(w), round(sum(w)/len(w), 3), len(wo), sum(wo), round(sum(wo)/len(wo), 3)))
for r in sorted(rows): print(r)
# Demon Form: heuristic took it vs not, offered runs, heuristic
print("\n== heuristic Demon Form")
pool = [s for s in heur if any("Demon Form" in f.get("offer", []) for f in s["floors"])]
w = [s["cleared"] for s in pool if any(f.get("took") == "Demon Form" for f in s["floors"])]
wo = [s["cleared"] for s in pool if not any(f.get("took") == "Demon Form" for f in s["floors"])]
print(len(pool), len(w), sum(w), len(wo), sum(wo))
# first pick of product: most common floor-1 pick
fp = C.Counter((s["floors"][0].get("took") or "skip") for s in prod)
print("\nfloor 1 product", fp.most_common(8))
# skip rate by floor product vs heur (0-499)
for nm, seqs in [("prod 0-499", [s for s in prod if s["i"] < 500]), ("heur", heur)]:
    sk = C.defaultdict(lambda: [0, 0])
    for s in seqs:
        for k, f in enumerate(s["floors"]):
            if "offer" in f: sk[k+1][0] += 1; sk[k+1][1] += f.get("took") is None
    print(nm, "skip rate by floor", {k: round(b/a, 3) for k, (a, b) in sorted(sk.items())})
