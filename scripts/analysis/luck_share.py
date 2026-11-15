"""Step 1a of lane luck-corrected-labels (docs/specs/luck-corrected-labels.md):
how much of the training labels' noise the luck correction removes.

Builds (or reuses) the one-turn dataset of the ycards-net-g1600 recipe with
each game's luck logged, samples its rows exactly as finetune.encoded does
(selfplay.sample_states, same seed), and per row takes the raw label y
(the game's score), the corrected label c = y - the luck drawn after the
row's decision, and the luck net's value v of the row's state. The label
noise, E[Var(y | state)], is measured directly: ROLLOUT_ROWS rows per deck
slice (Demon Form decks or not) are each played on ROLLOUT_K times from
their state with fresh chance seeds by the same player. Per slice (Demon
Form decks or not, elite or boss):
  noise_share = (Var(y) - Var(c)) / noise variance   (the fail-fast reads this)
  bound_share = (Var(y) - Var(c)) / mean((y - v)^2)  (a lower bound needing no replays)
  label_share = 1 - Var(c) / Var(y)
Var(y) - Var(c) is the noise variance removed (the luck terms have mean 0
given the state). se by bootstrap over games, and over replayed rows for
the noise. Pass: noise_share on Demon Form decks >= 0.50.

    python scripts/analysis/luck_share.py [--n-per-group 1600] [--threads 3] [--out results/luck/luck-share-g1600.json]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np  # noqa: E402

import finetune  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import stsnet  # noqa: E402
import two_turn_games  # noqa: E402

NET = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt"  # the 10-29 net (the recipe's parent)
PLAYER = NET + "@hpb0.01"  # configs/ycards-net-g1600-s*.json's source player
GAME_SEED = 51  # the recipe's game_seed
PASS = 0.50
BOOT = 1000
ROLLOUT_ROWS = 600  # replayed rows per deck slice (Demon Form decks, other decks)
ROLLOUT_K = 8  # replays per row
ROLLOUT_SEED = 9001


def rows(game, rng):
    """(decision index, paused state or None) of each row
    selfplay.sample_states takes from a replayed game with `rng` (labels
    None), drawing from `rng` as it does."""
    lo = selfplay.first_sampled(game)
    n = len(game["states"]) - lo
    out = []
    for i in sorted(lo + rng.choice(n, min(n, selfplay.STATES_PER_GAME), replace=False)):
        s, a = game["states"][i], game["actions"][i]
        out.append((int(i), None))
        for acts, kind, outs in s.options(selfplay.LIMIT):
            if a in acts and kind == "divergent":
                paused = outs[0][1]
                if not paused.is_over():
                    out.append((int(i), paused))
    return out


def table(ds, k, net=NET, root=registry.ROOT, states=None):
    """Per row: (game number, raw label, corrected label, net value, Demon
    Form deck, group) of the first `k` games per group of `ds`, rows drawn
    as finetune.encoded draws them; `states`, a list, gets each row's state."""
    import torch
    torch.set_num_threads(1)
    model, norm, meta = stsnet.load(net)
    feats, value = stsnet.features_for(meta), stsnet.Evaluator(model, norm)
    m = registry.load_manifest(ds, root)
    rng = np.random.default_rng(m["config"]["seed"] + finetune.SAMPLE_OFFSET)
    out, it, gno = [], finetune.first_per_group(ds, k, root), 0
    while True:
        chunk = [g for _, g in zip(range(registry.CHUNK), it)]
        if not chunk:
            return out
        got, info = [], []
        for g in chunk:
            r = registry.replay(g)
            if "luck" not in r:
                raise ValueError(f"{ds}: games carry no luck (built without --luck)")
            after = np.cumsum(np.asarray(r["luck"], float)[::-1])[::-1]  # luck drawn from decision i on
            df = "Demon Form" in g["deck"]
            for i, paused in rows(r, rng):
                got.append(r["states"][i] if paused is None else paused)
                info.append((gno, r["score"], r["score"] - after[i], df, int(g["group"])))
            gno += 1
        v = np.asarray(value(feats.encode(got)), float).reshape(-1)
        out += [(*x[:3], float(val), *x[3:]) for x, val in zip(info, v)]
        if states is not None:
            states += got


def rollout_vars(states, player, k=ROLLOUT_K, threads=3, seed=ROLLOUT_SEED):
    """Per state, the variance (ddof 1) of the final score over `k` plays
    on from it by `player` with fresh chance seeds (sts.play_on)."""
    import bench
    import sts
    ev = bench.load_evaluator(player)
    combats = [s.with_seed(seed * 1_000_003 + i * 131 + j) for i, s in enumerate(states) for j in range(k)]
    res = sts.play_on(combats, evaluator=ev.evaluator, features=ev.features, limit=selfplay.LIMIT, threads=threads)
    sc = np.array([r["score"] for r in res], float).reshape(len(states), k)
    return sc.var(axis=1, ddof=1)


def pick_rollouts(t, n=ROLLOUT_ROWS, seed=ROLLOUT_SEED):
    """Row indices to replay: `n` per deck slice (Demon Form or not), one
    row per game, games drawn at random."""
    rng = np.random.default_rng(seed)
    out = []
    for df in (True, False):
        by = {}
        for i, r in enumerate(t):
            if r[4] == df:
                by.setdefault(r[0], []).append(i)
        games = sorted(by)
        for g in rng.choice(games, min(n, len(games)), replace=False):
            out.append(int(rng.choice(by[int(g)])))
    return sorted(out)


def shares(t, boot=BOOT, seed=0, noise=None):
    """Shares of rows `t` (table's tuples) with bootstrap se over games;
    `noise`, the replayed variances of this slice's rows (None: no
    noise_share)."""
    g = np.array([r[0] for r in t])
    y, c, v = (np.array([r[i] for r in t], float) for i in (1, 2, 3))

    def f(idx):
        yy, cc, vv = y[idx], c[idx], v[idx]
        removed, ms, vy = float(np.var(yy) - np.var(cc)), float(np.mean((yy - vv) ** 2)), float(np.var(yy))
        return removed, removed / ms if ms > 0 else float("nan"), 1 - float(np.var(cc)) / vy if vy > 0 else float("nan")

    removed, bound, label = f(np.arange(len(t)))
    games = np.unique(g)
    by = {x: np.flatnonzero(g == x) for x in games}
    rng = np.random.default_rng(seed)
    bs = np.array([f(np.concatenate([by[x] for x in rng.choice(games, len(games))])) for _ in range(boot)])
    out = {"removed_var": removed, "removed_se": float(np.std(bs[:, 0])), "bound_share": bound,
           "bound_se": float(np.std(bs[:, 1])), "label_share": label, "label_se": float(np.std(bs[:, 2])),
           "rows": len(t), "games": int(len(games)), "label_var": float(np.var(y)), "corrected_var": float(np.var(c)),
           "residual_ms": float(np.mean((y - v) ** 2))}
    if noise is not None and len(noise) > 1:
        nv = np.asarray(noise, float)
        den, den_se = float(nv.mean()), float(nv.std(ddof=1) / np.sqrt(len(nv)))
        share = removed / den if den > 0 else float("nan")
        rel = np.hypot(out["removed_se"] / removed, den_se / den) if removed and den else float("nan")
        out.update(noise_var=den, noise_var_se=den_se, noise_rows=int(len(nv)), noise_share=share,
                   noise_se=float(abs(share) * rel))
    return out


def report(t, boot=BOOT, noise=None):
    """Shares per slice and the pass; `noise` maps a row index to its
    replayed variance."""
    noise = noise or {}
    names = dict(enumerate(selfplay.GROUPS))
    keep = {"all": lambda r: True, "demon_form": lambda r: r[4], "other": lambda r: not r[4]}
    for gi in sorted({r[5] for r in t}):
        name = names.get(gi, str(gi))
        keep[name] = lambda r, gi=gi: r[5] == gi
        keep[f"demon_form_{name}"] = lambda r, gi=gi: r[5] == gi and r[4]
    out = {}
    for k, f in keep.items():
        sel = [r for r in t if f(r)]
        if len({r[0] for r in sel}) > 1:
            out[k] = shares(sel, boot, noise=[x for i, x in noise.items() if f(t[i])] or None)
    df = out.get("demon_form", {}).get("noise_share", float("nan"))
    return {"slices": out, "pass": bool(df >= PASS), "rule": f"noise_share on Demon Form decks >= {PASS}"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-per-group", type=int, default=1600)
    ap.add_argument("--seed", type=int, default=GAME_SEED)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--player", default=PLAYER)
    ap.add_argument("--net", default=NET, help="the luck net (a plain net path)")
    ap.add_argument("--boot", type=int, default=BOOT)
    ap.add_argument("--rollout-rows", type=int, default=ROLLOUT_ROWS, help="replayed rows per deck slice")
    ap.add_argument("--rollout-k", type=int, default=ROLLOUT_K)
    ap.add_argument("--out", default="results/luck/luck-share-g1600.json")
    args = ap.parse_args(argv)
    ds = two_turn_games.dataset(args.player, args.n_per_group, args.seed, "one", args.threads,
                                decks="held-out", luck=args.net)
    states = []
    t = table(ds, args.n_per_group, args.net, states=states)
    picked = pick_rollouts(t, args.rollout_rows)
    print(f"{len(t)} rows; replaying {len(picked)} rows x {args.rollout_k}", flush=True)
    var = rollout_vars([states[i] for i in picked], args.player, args.rollout_k, args.threads)
    res = {"dataset": ds, "player": args.player, "luck_net": args.net, "n_per_group": args.n_per_group,
           "rollout_rows": len(picked), "rollout_k": args.rollout_k,
           **report(t, args.boot, dict(zip(picked, var.tolist())))}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(f"dataset {ds}; {res['rule']}: {'PASS' if res['pass'] else 'FAIL'}")
    print(f"{'slice':<22}{'games':>7}{'rows':>7}{'noise':>8}{'(se)':>7}{'bound':>8}{'label':>8}"
          f"{'removed':>9}{'noise var':>10}")
    nan = float("nan")
    for k, s in res["slices"].items():
        print(f"{k:<22}{s['games']:>7}{s['rows']:>7}{s.get('noise_share', nan):>8.3f}{s.get('noise_se', nan):>7.3f}"
              f"{s['bound_share']:>8.3f}{s['label_share']:>8.3f}{s['removed_var']:>9.4f}{s.get('noise_var', nan):>10.4f}")
    return res


if __name__ == "__main__":
    main()
