"""Check 6: do effect-based card features generalise to held-out cards where
id-based ones can't?

Generates (or loads from data/) self-play data, trains (or loads from
models/) the effects net and the ids net on the same states, then reports
value-prediction MSE on (a) training-pool decks and (b) decks with ≥ 2
held-out cards. Pass: on (b) the effects net's MSE is ≥ 20% lower than the
ids net's. Also reports (not gated) Search win rate and HP lost on held-out
decks with the heuristic and with each net. Exits 1 if the bar isn't met.

    python scripts/generalise.py [--retrain] [--n-games 300]
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


def load_or_train(mode, sets, retrain):
    path = train.model_path(mode)
    if retrain or not os.path.exists(path):
        t = time.perf_counter()
        train.train_and_save(mode, sets)
        print(f"trained {mode} net in {time.perf_counter() - t:.0f}s")
    return stsnet.load(path)


def win_table(nets, n, seed=5, specs=None):
    """Search on held-out decks (or on `specs`, a (specs, groups) pair) with
    each evaluator: {name: {group: (win, hp_lost)}}."""
    specs, groups = specs or selfplay.make_specs(n, seed, selfplay.held_out_deck)
    groups = np.array(groups)
    torch.set_num_threads(1)  # many runner threads each call the net
    out = {}
    evals = [("heuristic", "heuristic", None)] + [
        (name, stsnet.rust_evaluator(m, nm, meta), stsnet.features_for(meta)) for name, (m, nm, meta) in nets.items()]
    for name, ev, feats in evals:
        t = time.perf_counter()
        res = sts.run("search", specs, evaluator=ev, features=feats, limit=selfplay.LIMIT)
        won = np.array([r["won"] for r in res])
        lost = np.array([r["hp_start"] - r["hp_end"] for r in res])
        out[name] = {g: (won[groups == i].mean(), lost[groups == i].mean()) for i, g in enumerate(GROUPS)}
        out[name]["all"] = (won.mean(), lost.mean())
        print(f"  search + {name}: {time.perf_counter() - t:.0f}s")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retrain", action="store_true", help="ignore saved models")
    ap.add_argument("--n-games", type=int, default=300, help="win-rate combats per group")
    args = ap.parse_args()

    t0 = time.perf_counter()
    sets = selfplay.all_sets()
    nets = {m: load_or_train(m, sets, args.retrain) for m in ("effects", "ids")}

    mean = float(sets["train"]["effects"].target.mean())
    print("\nvalue MSE vs. final score (0-2 scale); 'const' predicts the training mean")
    print(f"{'test set':<26} {'states':>7} {'const':>7} {'effects':>8} {'ids':>8} {'effects vs ids':>15}")
    res = {}
    for key, label in (("test_a", "(a) training-pool decks"), ("test_b", "(b) held-out decks")):
        e = train.mse(nets["effects"][0], nets["effects"][1], sets[key]["effects"])
        i = train.mse(nets["ids"][0], nets["ids"][1], sets[key]["ids"])
        c = float(((sets[key]["effects"].target - mean) ** 2).mean())
        res[key] = (e, i)
        print(f"{label:<26} {len(sets[key]['effects']):>7} {c:>7.4f} {e:>8.4f} {i:>8.4f} {(1 - e / i) * 100:>+14.1f}%")
    for g, name in enumerate(GROUPS):
        ds = {m: sets["test_b"][m] for m in nets}
        idx = np.nonzero(ds["effects"].group == g)[0]
        e = train.mse(nets["effects"][0], nets["effects"][1], ds["effects"].subset(idx))
        i = train.mse(nets["ids"][0], nets["ids"][1], ds["ids"].subset(idx))
        print(f"{'    (b) ' + name:<26} {len(idx):>7} {'':>7} {e:>8.4f} {i:>8.4f} {(1 - e / i) * 100:>+14.1f}%")

    print(f"\nSearch on held-out decks, {args.n_games} combats per group (reported, not gated)")
    wt = win_table(nets, args.n_games)
    print(f"{'evaluator':<10} " + " ".join(f"{g + ' win%':>12} {'HP lost':>8}" for g in GROUPS + ["all"]))
    for name, row in wt.items():
        print(f"{name:<10} " + " ".join(f"{row[g][0] * 100:>12.1f} {row[g][1]:>8.1f}" for g in GROUPS + ["all"]))

    e, i = res["test_b"]
    ok = e <= 0.8 * i
    print(f"\ncheck 6: effects MSE {e:.4f} vs ids {i:.4f} on held-out decks "
          f"({(1 - e / i) * 100:.1f}% lower, need >= 20%): {'pass' if ok else 'FAIL'}")
    print(f"total {time.perf_counter() - t0:.0f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
