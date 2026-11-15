"""Independent re-derivation of regroup.py's headline numbers (skeptic pass).

Reads the primary files directly, not regroup.py or its output:
- data/bench/tight2.json: spec order, cell, group per fight.
- runs/seed-check/check.json: heuristic_fights; rounds 2/4/7/10 x seeds
  1/101/201 per-fight bits (spec order, learn.tight_results at every=1).
- runs/rung4-nightdb/check.json: per-seed fights of arms A and B.
- results/warm-start/cells/*.json: tight2 train, cells with cell % 4 == 0.

Checks:
0. alignment: recompute the stored overall leads (learn.gate, cell-averaged)
   from the bits and compare with what the checks stored.
1. per-arm, per-type, per-half leads (seed-averaged fights, interval over
   cells), and the seed sd per type.
2. (a) change from round 2: over cells, and over seeds two ways (pooled
   sd as regroup.py; and paired by training seed, t df 2).
3. (b) rung-4 B - A on held-out elite: over cells, paired seeds, a
   two-level bootstrap (cells and seeds), sign count over cells.
4. (c) best arm / net on train elite+boss.

    OMP_NUM_THREADS=1 .venv/Scripts/python scripts/analysis/check_regroup.py
"""

import glob
import json
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
H = ("train", "held_out")
SEEDS = ("1", "101", "201")
T = {2: 4.302653, 10: 2.228139}


def j(*a):
    with open(os.path.join(ROOT, *a), encoding="utf-8") as f:
        return json.load(f)


def b(s):
    return np.array([int(c) for c in s], float)


spec = j("data", "bench", "tight2.json")["halves"]
cell = {h: np.array([s["cell"] for s in spec[h]]) for h in H}
grp = {h: np.array([s["group"] for s in spec[h]]) for h in H}
sc = j("runs", "seed-check", "check.json")
r4 = j("runs", "rung4-nightdb", "check.json")
heur = {h: b(sc["heuristic_fights"][h]) for h in H}
heur4 = {h: b(r4["heuristic_fights"][h]) for h in H}
assert all((heur[h] == heur4[h]).all() for h in H)

GROUPS = {"hallway": ("hallway",), "elite": ("elite",), "boss": ("boss",),
          "elite+boss": ("elite", "boss"), "all": ("hallway", "elite", "boss")}


def percell(x, h, mask=None):
    c = cell[h] if mask is None else cell[h][mask]
    g = grp[h] if mask is None else grp[h][mask]
    ids = np.unique(c)
    m = np.array([x[c == i].mean() for i in ids])
    gg = np.array([g[c == i][0] for i in ids])
    return m, gg


def iv(m, z=1.959964):
    w = z * m.std(ddof=1) / np.sqrt(len(m))
    return m.mean(), m.mean() - w, m.mean() + w, len(m)


def lead(x, h, g, mask=None):
    m, gg = percell(x, h, mask)
    return iv(m[np.isin(gg, GROUPS[g])])


def f(v):
    return f"{v[0]:+.4f} [{v[1]:+.4f}, {v[2]:+.4f}]" + (f" n{v[3]}" if len(v) > 3 else "")


# nets
net = {}
for k in ("2", "4", "7", "10"):
    for s in SEEDS:
        net[(f"r{k}", s)] = {h: b(sc["rounds"][k]["seeds"][s]["fights"][h]) for h in H}
for s in SEEDS:
    A = {h: b(r4["seeds"][s]["fights"]["A"][h]) for h in H}
    assert all((A[h] == net[("r10", s)][h]).all() for h in H)
    net[("B", s)] = {h: b(r4["seeds"][s]["fights"]["B"][h]) for h in H}
ARMS = ["r2", "r4", "r7", "r10", "B"]

print("== 0. alignment: recomputed overall lead vs stored ==")
for k in ("2", "4", "7", "10"):
    for s in SEEDS:
        for h in H:
            mine = lead(net[(f"r{k}", s)][h] - heur[h], h, "all")
            st = sc["rounds"][k]["seeds"][s]["gate"]["halves"][h]["lead"]
            assert abs(mine[0] - st[0]) < 1e-5 and abs(mine[1] - st[1]) < 1e-5, (k, s, h, mine, st)
    for h in H:
        avg = np.mean([net[(f"r{k}", s)][h] for s in SEEDS], 0)
        st = sc["rounds"][k]["averaged"]["halves"][h]["lead"]
        assert abs(lead(avg - heur[h], h, "all")[0] - st[0]) < 1e-5
for s in SEEDS:
    for h in H:
        st = r4["seeds"][s]["tight"]["B_vs_A"]["halves"][h]["lead"]
        mine = lead(net[("B", s)][h] - net[("r10", s)][h], h, "all")
        assert abs(mine[0] - st[0]) < 1e-5, (s, h, mine, st)
print("all stored per-seed, averaged and B_vs_A overall leads reproduce to 1e-5")
print("cells:", {g: [int(len(np.unique(cell[h][grp[h] == g]))) for h in H] for g in ("hallway", "elite", "boss")})

# 1. per-arm leads
print("\n== 1. seed-averaged arm leads vs heuristic (interval over cells) ==")
per_seed = {}
for a in ARMS:
    for h in H:
        avg = np.mean([net[(a, s)][h] for s in SEEDS], 0)
        row = []
        for g in GROUPS:
            row.append(f"{g} {f(lead(avg - heur[h], h, g)[:3])}")
            per_seed[(a, h, g)] = np.array([lead(net[(a, s)][h] - heur[h], h, g)[0] for s in SEEDS])
        print(f"{a:4s} {h:8s} " + " | ".join(row))

print("\n== seed sd (pooled within arm, df 10) ==")
sd = {}
for h in H:
    for g in GROUPS:
        x = [per_seed[(a, h, g)] for a in ARMS]
        sd[(h, g)] = np.sqrt(sum(((v - v.mean()) ** 2).sum() for v in x) / 10)
        print(f"{h:8s} {g:10s} sd {sd[(h, g)]:.4f}  MDE 3v3 unpaired {2.8 * sd[(h, g)] * np.sqrt(2 / 3):.3f}")

# 2. (a)
print("\n== 2. (a) change from r2, elite+boss ==")
for h in H:
    avg = {a: np.mean([net[(a, s)][h] for s in SEEDS], 0) for a in ARMS}
    for a in ("r4", "r7", "r10", "later"):
        x = (np.mean([avg[r] for r in ("r4", "r7", "r10")], 0) if a == "later" else avg[a]) - avg["r2"]
        c = lead(x, h, "elite+boss")
        # seed level, pooled sd as regroup.py
        se = sd[(h, "elite+boss")] * np.sqrt(1 / 3 + (1 / 9 if a == "later" else 1 / 3))
        # paired by training seed (same seed across rounds), t df 2
        if a == "later":
            d = np.mean([per_seed[(r, h, "elite+boss")] for r in ("r4", "r7", "r10")], 0) - per_seed[("r2", h, "elite+boss")]
        else:
            d = per_seed[(a, h, "elite+boss")] - per_seed[("r2", h, "elite+boss")]
        wp = T[2] * d.std(ddof=1) / np.sqrt(3)
        print(f"{h:8s} {a:5s}-r2 cells {f(c)}  pooled-seed [{c[0] - T[10] * se:+.4f}, {c[0] + T[10] * se:+.4f}]"
              f"  paired-seed {d.mean():+.4f} [{d.mean() - wp:+.4f}, {d.mean() + wp:+.4f}] per seed "
              + "/".join(f"{v:+.3f}" for v in d))
    print(f"{h:8s} round leads e+b: " + " / ".join(f"{a} {per_seed[(a, h, 'elite+boss')].mean():+.4f}" for a in ARMS))
# correlation of per-seed e+b leads across rounds (same training seed)
for h in H:
    M = np.array([per_seed[(a, h, "elite+boss")] - per_seed[(a, h, "elite+boss")].mean() for a in ARMS[:4]])
    print(f"{h}: seed effects by round (rows r2,r4,r7,r10; cols seeds 1/101/201):\n{np.round(M, 4)}")

# 3. (b)
print("\n== 3. (b) B - A ==")
rng = np.random.default_rng(0)
for h in H:
    for g in ("elite", "boss", "elite+boss", "hallway", "all"):
        D = [net[("B", s)][h] - net[("r10", s)][h] for s in SEEDS]
        c = lead(np.mean(D, 0), h, g)
        ps = np.array([lead(d, h, g)[0] for d in D])
        wp = T[2] * ps.std(ddof=1) / np.sqrt(3)
        line = (f"{h:8s} {g:10s} cells {f(c)}  per seed " + "/".join(f"{v:+.3f}" for v in ps)
                + f"  seed-t [{ps.mean() - wp:+.4f}, {ps.mean() + wp:+.4f}]  paired MDE(z) {2.8 * ps.std(ddof=1) / np.sqrt(3):.3f}")
        if g == "elite" and h == "held_out":
            # two-level bootstrap: resample cells, then seeds
            cm = np.array([percell(d, h)[0] for d in D])          # seeds x cells
            gg = percell(D[0], h)[1]
            cm = cm[:, gg == "elite"]
            nc = cm.shape[1]
            bs = [cm[rng.integers(0, 3, 3)][:, rng.integers(0, nc, nc)].mean() for _ in range(20000)]
            line += f"\n   two-level bootstrap (cells+seeds) 95% [{np.percentile(bs, 2.5):+.4f}, {np.percentile(bs, 97.5):+.4f}]"
            cmean = cm.mean(0)
            line += f"\n   cells B>A {int((cmean > 0).sum())}, B<A {int((cmean < 0).sum())}, tie {int((cmean == 0).sum())} of {nc}"
        print(line)

# 4. (c)
print("\n== 4. (c) train elite+boss ==")
rows = []
for a in ARMS:
    avg = np.mean([net[(a, s)]["train"] for s in SEEDS], 0)
    rows.append((lead(avg - heur["train"], "train", "elite+boss"), a, per_seed[(a, "train", "elite+boss")]))
for v, a, ps in sorted(rows, key=lambda r: -r[0][0]):
    print(f"arm {a:4s} {f(v)}  per seed " + "/".join(f"{x:+.4f}" for x in ps)
          + f"  seed-t [{ps.mean() - T[2] * ps.std(ddof=1) / np.sqrt(3):+.4f}, {ps.mean() + T[2] * ps.std(ddof=1) / np.sqrt(3):+.4f}]")
best = max(((lead(net[k]["train"] - heur["train"], "train", "elite+boss"), k) for k in net), key=lambda r: r[0][0])
print("best single net", best[1], f(best[0]))
d = np.mean([net[("r2", s)]["train"] for s in SEEDS], 0) - np.mean([net[("B", s)]["train"] for s in SEEDS], 0)
print("r2 - B train e+b, paired by fight, cells:", f(lead(d, "train", "elite+boss")))

# 5. warm start alignment
print("\n== 5. warm-start alignment (cell % 4 == 0) ==")
mask = cell["train"] % 4 == 0
for p in sorted(glob.glob(os.path.join(ROOT, "results", "warm-start", "cells", "*.json"))):
    c = j(p)
    w = np.array(c["tight2_train"]["won"], float)
    agree = (w == heur["train"][mask]).mean()
    shift = (w == np.roll(heur["train"][mask], 20)).mean()
    out = {g: lead(w - heur["train"][mask], "train", g, mask)[0] for g in ("hallway", "elite+boss", "boss")}
    print(f"{os.path.basename(p)[:34]:34s} agree {agree:.3f} shifted {shift:.3f} " + " ".join(f"{g} {v:+.3f}" for g, v in out.items()))
