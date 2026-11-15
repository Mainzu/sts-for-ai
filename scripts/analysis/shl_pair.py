"""Paired read of gen batch 1 files against the zero-shot bench (lane
strength-by-hits-left, docs/research/strength-hits-price.md): the charter's
cells (AttackLoss-Damage x Nob, AttackLoss-Strength x each parent, ladder
controls as read-gen picks them) and the parent rows' net HP lost, each
paired by start and seed against the first 4 seeds of
results/mutate/gen-enemies-b1.json; 0472 (@esp0.04) always included.

    .venv/Scripts/python.exe scripts/analysis/shl_pair.py shl0.005 shl0.01   # in the main checkout
"""
import json, sys, math
def load(p):
    return {(r["i"], r["floor"], r["encounter"]): r for r in json.load(open(p))["rows"]}
Z = load("results/mutate/gen-enemies-b1.json")
files = {"esp0.04": "results/mutate/gen-b1-esp0.04.json"}
for a in sys.argv[1:]:
    files[a] = f"results/mutate/gen-b1-{a}.json"
F = {k: load(v) for k, v in files.items()}
def lost(r, e, who, s):  # HP lost, entry HP on a loss
    w, hp = e[who][s]
    return r["hp"] - hp if w else r["hp"]
def cost(r, mech, ctl, who="one"):
    out = []
    for s in range(4):
        m = r["mods"][mech]; c = r["mods"][ctl]
        out.append((lost(r, m, who, s) - lost(r, m, "heuristic", s)) - (lost(r, c, who, s) - lost(r, c, "heuristic", s)))
    return sum(out) / 4
def ms(x):
    n = len(x); m = sum(x) / n
    return m, math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1) / n)
CTL = {("GE-AttackLoss-Damage", "gremlin_nob"): "c-hp1.25", ("GE-AttackLoss-Strength", "gremlin_nob"): "c-hp1.25-str1",
       ("GE-AttackLoss-Strength", "lagavulin"): "c-hp1.25-str1", ("GE-AttackLoss-Strength", "three_sentries"): "c-hp1.25"}
any_f = next(iter(F.values()))
mism = sum(1 for i, r in any_f.items() for k, f in F.items() if F[k][i]["parent"]["heuristic"] != Z[i]["parent"]["heuristic"][:4])
print("heuristic parent rows differing from zero-shot's first 4 seeds:", mism)
for (mech, enc), ctl in CTL.items():
    ids = [i for i, r in any_f.items() if r["encounter"] == enc]
    z = [cost({**Z[i], "mods": {k: {w: v[:4] for w, v in Z[i]["mods"][k].items()} for k in (mech, ctl)}}, mech, ctl) for i in ids]
    line = f"{mech} x {enc} ({len(ids)}, ctl {ctl}): zero {ms(z)[0]:+.2f} ({ms(z)[1]:.2f})"
    for k, f in F.items():
        c = [cost(f[i], mech, ctl) for i in ids]
        d = [a - b for a, b in zip(c, z)]
        wins = sum(e for i in ids for e, _ in f[i]["mods"][mech]["one"]) / (4 * len(ids))
        line += f" | {k} {ms(c)[0]:+.2f} ({ms(c)[1]:.2f}) diff {ms(d)[0]:+.2f} ({ms(d)[1]:.2f}) win {wins:.3f}"
    print(line)
for enc in ("gremlin_nob", "lagavulin", "three_sentries"):
    ids = [i for i, r in any_f.items() if r["encounter"] == enc]
    line = f"parent {enc} net HP lost vs zero-shot:"
    for k, f in F.items():
        d = [sum(lost(f[i], f[i]["parent"], "one", s) - lost(Z[i], Z[i]["parent"], "one", s) for s in range(4)) / 4 for i in ids]
        line += f" | {k} {ms(d)[0]:+.2f} ({ms(d)[1]:.2f})"
    print(line)
