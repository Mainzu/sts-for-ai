"""Run value by floor (Next Q4, review 2026-11-02b rank 4): what is one HP
at the start of gauntlet floor k worth in Act-clear probability?

For each floor k, over the sequences alive at its start, fits
P(clear | HP at floor start) by logistic regression (numpy Newton), once
plain and once with a deck-strength covariate (the logit of the sequence's
cell's clear rate over the *other* sequences of that cell in the pool), and
reports dP/dHP at the floor's median HP with a bootstrap se over sequence
indices (files sharing a sequence resample together). "price" divides the
adjusted slope by P(clear | alive at floor k): what one more HP at the end
of the fight before floor k is worth relative to winning that fight, the
same units as the search's flat HP price c = 0.01.

    python scripts/analysis/run_value.py [--boot 200]
"""

import argparse
import glob
import json
import os

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "results", "gauntlet")
KINDS = ("easy",) * 3 + ("hard",) * 2 + ("elite",) + ("hard",) * 2 + ("elite",) + ("hard",) + ("boss",)

# Pools (stated so the read is reproducible). Cell start, no rewards, one turn,
# search HP bonus; duplicates (champion-hpb0.01-b500 = bd6d62) and subsets dropped.
POOLS = {
    "one-turn cell @hpb": [
        "2026-11-01-burst8hp2-s1-9f89b6f-hpb0.005-ce0087.json",
        "2026-11-01-burst8hp2-s1-9f89b6f-hpb0.01-bd6d62.json",
        "2026-11-01-burst8hp2-s1-9f89b6f-hpb0.02-fbc89f.json",
        "2026-11-01-burst8hp2-s1-9f89b6f-hpb0.04-1bb4e0.json",
        "net1029-hpb0.005.json", "net1029-hpb0.01.json", "net1029-hpb0.02.json"],
    "two-turn cell @hpe": [
        "champion-hpe0.01-two.json", "champion-hpe0.01-two-c.json",
        "net1029-hpe0.01-two-a.json", "net1029-hpe0.01-two-c.json"],
    "one-turn starter + rewards": [
        "net1029-hpb0.01-starter-random.json", "net1029-hpb0.01-starter-sim.json",
        "net1029-hpb0.01-starter-simboss.json"],
}


def load(names):
    rows = []  # (file j, sequence i, cell, floors, cleared)
    for j, n in enumerate(names):
        with open(os.path.join(ROOT, n), encoding="utf-8") as f:
            d = json.load(f)
        for r in d["sequences"]:
            rows.append((j, r["i"], (r["half"], r["cell"]), r["floors"], bool(r["cleared"])))
    return rows


def logit_fit(X, y, iters=50):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w)))
        g = X.T @ (y - p)
        H = (X * (p * (1 - p))[:, None]).T @ X + 1e-6 * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    return w


def floor_data(rows, k):
    """HP at floor k's start, cleared, sequence index, deck-strength covariate."""
    by_cell = {}
    for _, _, c, _, cl in rows:
        by_cell.setdefault(c, []).append(cl)
    hp, y, idx, z = [], [], [], []
    for _, i, c, fl, cl in rows:
        if len(fl) <= k:
            continue
        s = by_cell[c]
        loo = (sum(s) - cl + 0.5) / (len(s) - 1 + 1.0)  # other sequences of this cell, smoothed
        hp.append(fl[k]["hp_start"]), y.append(float(cl)), idx.append(i), z.append(np.log(loo / (1 - loo)))
    return np.array(hp, float), np.array(y), np.array(idx), np.array(z)


def slope(hp, y, z, adjust, price=False):
    """dP/dHP at the median HP (and mean covariate); with `price`, divided by
    P(clear | alive here): one HP's worth in units of being alive at this
    floor, i.e. of winning the fight before it (the search's c is 0.01)."""
    h0 = np.median(hp)
    X = np.column_stack([np.ones_like(hp), (hp - h0) / 10] + ([z - z.mean()] if adjust else []))
    w = logit_fit(X, y)
    p = 1 / (1 + np.exp(-w[0]))
    d = w[1] / 10 * p * (1 - p)
    return d / y.mean() if price else d


def read(name, files, boot, rng):
    rows = load(files)
    all_ids = np.unique([i for _, i, _, _, _ in rows])
    draws = [rng.choice(all_ids, len(all_ids)) for _ in range(boot)]  # shared by every floor, so ratios pair
    out = []
    for k in range(1, len(KINDS)):
        hp, y, idx, z = floor_data(rows, k)
        if len(hp) < 30 or hp.std() == 0 or y.min() == y.max():
            continue
        est = [slope(hp, y, z, a) for a in (False, True)] + [slope(hp, y, z, True, True)]
        pos = {i: np.flatnonzero(idx == i) for i in np.unique(idx)}
        bs = []
        for d in draws:
            pick = np.concatenate([pos[i] for i in d if i in pos])
            bs.append([slope(hp[pick], y[pick], z[pick], a) for a in (False, True)]
                      + [slope(hp[pick], y[pick], z[pick], True, True)])
        se = np.std(bs, axis=0, ddof=1)
        out.append({"k": k, "kind": KINDS[k], "n": len(hp), "median_hp": float(np.median(hp)),
                    "p_clear": float(y.mean()), "dpdhp": est[0], "se": float(se[0]),
                    "dpdhp_adj": est[1], "se_adj": float(se[1]), "price": est[2], "se_price": float(se[2]),
                    "boot": np.array(bs)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=200)
    args = ap.parse_args()
    rng = np.random.default_rng(0)
    for name, files in POOLS.items():
        res = read(name, files, args.boot, rng)
        print(f"\n{name}: {len(files)} files")
        # floors 1-3 start at (nearly) 80 HP every time: no spread to fit, so the
        # reference is floor 4, the first with HP spread
        ref = next(r for r in res if r["k"] == 4)
        print(" k kind      n  medHP  P(clear)  dP/dHP (se)        adj dP/dHP (se)    price (se)        price rel. k=4 (se)")
        for r in res:
            rel = r["boot"][:, 2] / ref["boot"][:, 2]
            rs = f"{r['price'] / ref['price']:.2f} ({np.std(rel, ddof=1):.2f})"
            print(f"{r['k']:2d} {r['kind']:6s} {r['n']:5d} {r['median_hp']:5.0f}  {r['p_clear']:.3f}   "
                  f"{r['dpdhp']:.4f} ({r['se']:.4f})   {r['dpdhp_adj']:.4f} ({r['se_adj']:.4f})   "
                  f"{r['price']:.4f} ({r['se_price']:.4f})   {rs}")


if __name__ == "__main__":
    main()
