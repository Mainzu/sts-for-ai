"""Check 8 (Amendment 2): do nets trained only on Ironclad games transfer to
the Silent?

Loads the two nets from generalise.py unchanged (no retraining; run generalise.py first
if models/ is empty), plays seeded Silent games with Search + heuristic to
label states with their final score, and reports value MSE for both nets:
- tier A: Silent starter + 5 cards built from primitives Ironclad training
  uses (gated: effects-net MSE >= 20% lower than ids-net MSE);
- tier B: + Poison cards, at least 2 per deck (reported, not gated).
Also reports (not gated) Search win rate and HP lost with the heuristic and
with each net. Exits 1 if the gate isn't met.

    python scripts/transfer.py [--n-games 300] [--n-states 1000]
"""

import argparse
import os
import sys
import time

import numpy as np
import torch

import selfplay
import stsnet
import sts
import train

GROUPS = selfplay.GROUPS
STARTER = sts.starter_deck("silent")
TIER_A = ["Neutralize", "Sucker Punch", "Leg Sweep", "Quick Slash", "Backflip", "Deflect", "Slice", "Dagger Spray",
          "Blade Dance", "Cloak and Dagger"]
TIER_B = ["Deadly Poison", "Poisoned Stab", "Bouncing Flask"]
POOL_A = TIER_A + [n + "+" for n in TIER_A]
POOL_B = TIER_B + [n + "+" for n in TIER_B]


def deck_a(rng):
    return STARTER + list(rng.choice(POOL_A, 5))


def deck_b(rng):
    """Starter + 5 cards from tiers A and B, at least 2 of them Poison cards."""
    pool = POOL_A + POOL_B
    while True:
        extra = list(rng.choice(pool, 5))
        if sum(c in POOL_B for c in extra) >= 2:
            return STARTER + extra


TIERS = {"A": deck_a, "B": deck_b}


def load_nets():
    nets = {}
    for mode in ("effects", "ids"):
        path = train.model_path(mode)
        if not os.path.exists(path):
            sys.exit(f"{path} missing: run scripts/generalise.py first (this check never trains)")
        nets[mode] = stsnet.load(path)
    return nets


def mse_by_group(nets, ds):
    """{'all' | group: {mode: mse}}, plus state counts."""
    out = {}
    for key, idx in [("all", np.arange(len(ds["effects"])))] + [
            (g, np.nonzero(ds["effects"].group == i)[0]) for i, g in enumerate(GROUPS)]:
        out[key] = {m: train.mse(nets[m][0], nets[m][1], ds[m].subset(idx)) for m in nets}
        out[key]["n"] = len(idx)
        out[key]["target"] = ds["effects"].target[idx]
    return out


def win_table(nets, n, tier, seed):
    specs, groups = selfplay.make_specs(n, seed, TIERS[tier], character="silent")
    groups = np.array(groups)
    torch.set_num_threads(1)  # many runner threads each call the net
    evals = [("heuristic", "heuristic", None)] + [
        (name, stsnet.rust_evaluator(m, nm, meta), stsnet.features_for(meta)) for name, (m, nm, meta) in nets.items()]
    out = {}
    for name, ev, feats in evals:
        t = time.perf_counter()
        res = sts.run("search", specs, evaluator=ev, features=feats, limit=selfplay.LIMIT, character="silent")
        won = np.array([r["won"] for r in res])
        lost = np.array([r["hp_start"] - r["hp_end"] for r in res])
        out[name] = {g: (won[groups == i].mean(), lost[groups == i].mean()) for i, g in enumerate(GROUPS)}
        out[name]["all"] = (won.mean(), lost.mean())
        print(f"  tier {tier}, search + {name}: {time.perf_counter() - t:.0f}s")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-games", type=int, default=300, help="win-rate combats per group and tier")
    ap.add_argument("--n-states", type=int, default=1000, help="labelled games per group and tier")
    args = ap.parse_args()

    t0 = time.perf_counter()
    nets = load_nets()
    for mode, (_, _, meta) in nets.items():
        assert meta.get("format") == selfplay.FORMAT, "stale net: retrain with scripts/generalise.py --retrain"

    # The constant baseline predicts the Ironclad training mean, as in check 6.
    train_path = os.path.join(selfplay.DATA, f"train_effects_{selfplay.FORMAT}.npz")
    mean = float(np.load(train_path)["target"].mean()) if os.path.exists(train_path) else None

    data = {tier: selfplay.generate(f"silent_{tier.lower()}", args.n_states, 20 + i, fn, character="silent")
            for i, (tier, fn) in enumerate(TIERS.items())}

    print("\nSilent transfer: value MSE vs. final score (0-2 scale), nets trained on Ironclad only")
    print(f"{'test set':<22} {'states':>7} {'const':>7} {'effects':>8} {'ids':>8} {'effects vs ids':>15}")
    res = {}
    for tier, ds in data.items():
        r = mse_by_group(nets, ds)
        res[tier] = r["all"]
        for key in ["all"] + GROUPS:
            e, i, n = r[key]["effects"], r[key]["ids"], r[key]["n"]
            c = f"{float(((r[key]['target'] - mean) ** 2).mean()):>7.4f}" if mean is not None else f"{'n/a':>7}"
            label = f"tier {tier}" + ("" if key == "all" else f"  {key}")
            print(f"{label:<22} {n:>7} {c} {e:>8.4f} {i:>8.4f} {(1 - e / i) * 100:>+14.1f}%")

    print(f"\nSearch on Silent decks, {args.n_games} combats per group (reported, not gated)")
    for i, tier in enumerate(TIERS):
        wt = win_table(nets, args.n_games, tier, 30 + i)
        print(f"tier {tier}")
        print(f"{'evaluator':<10} " + " ".join(f"{g + ' win%':>12} {'HP lost':>8}" for g in GROUPS + ["all"]))
        for name, row in wt.items():
            print(f"{name:<10} " + " ".join(f"{row[g][0] * 100:>12.1f} {row[g][1]:>8.1f}" for g in GROUPS + ["all"]))

    e, i = res["A"]["effects"], res["A"]["ids"]
    ok = e <= 0.8 * i
    print(f"\ncheck 8: tier A effects MSE {e:.4f} vs ids {i:.4f} "
          f"({(1 - e / i) * 100:.1f}% lower, need >= 20%): {'pass' if ok else 'FAIL'}")
    print(f"total {time.perf_counter() - t0:.0f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
