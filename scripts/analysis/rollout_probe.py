"""Ceiling probe (big-picture review 2026-11-02, rank 3): replays gauntlet
fights with a rollout player, to tell real combat headroom from unwinnable
decks.

The rollout player: at each owner decision, every legal action is tried
`--n` times. Each try copies the combat with a fresh RNG seed
(`Combat.decode(c.encode(), seed)`, so a rollout never sees the real
fight's future draws or rolls), steps the action, and plays the fight to
its end with `--policy` (default the one-turn champion with the HP bonus,
via `sts.play_on`, which plays the copies in parallel in Rust). An action's
value is the mean of won x (1 + 0.01 x HP at the end); the best mean is
played on the real combat, whose own RNG draws the real chance events.
When the policy's own choice ties for the best mean (all rollouts lost,
say), the policy's choice is played; `overrides` counts the decisions where
the rollouts picked something else.
A decision with one legal action is stepped without rollouts.

Fights: the same specs `scripts/gauntlet.py` builds (deck, encounter,
seed `SEED_BASE + i * 100 + floor`), entered at the HP the product player
(`--product`, default the two-turn `@hpe0.01` champion) had there.
`--never-cleared K`: the first K sequences (by index, 0-499) that no
gauntlet player clears (union over every results/gauntlet/*.json with the
standard settings), replaying the product's fatal fight. `--cleared K`: the
first K sequences the product clears, replaying their boss fight (a sanity
check: the rollout player should win nearly all of them). `--plain` plays
the policy itself instead of rollouts (to check the specs reproduce).

    python scripts/analysis/rollout_probe.py --never-cleared 30 --threads 4 --out results/rollout/never30.json
    python scripts/analysis/rollout_probe.py --cleared 30 --threads 4 --out results/rollout/cleared30.json
"""

import argparse
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import gauntlet  # noqa: E402
import sts  # noqa: E402

POLICY = "runs/2026-11-01-burst8hp2-s1-9f89b6f/model.pt@hpb0.01"
PRODUCT = "results/gauntlet/champion-hpe0.01-two.json"
HP_WEIGHT = 0.01  # value = won x (1 + HP_WEIGHT x end HP): win first, HP as a tie-break
TURN_LIMIT = sts.PLAY_TURN_LIMIT  # as play's turn limit: a combat still running is a loss
STANDARD = {"shape": list(gauntlet.SHAPE), "rest": gauntlet.REST, "seed": gauntlet.GAUNTLET_SEED}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def standard_files(root=gauntlet.ROOT):
    """Gauntlet result files with the standard settings, by path."""
    out = {}
    for p in sorted(glob.glob(os.path.join(root, "*.json"))):
        d = load(p)
        if all(d["settings"].get(k) == v for k, v in STANDARD.items()):
            out[p] = d
    return out


def never_cleared(files, first=0, n=500):
    """Indices first..first+n-1 that no file clears (the union of clears)."""
    cleared = set()
    for d in files.values():
        cleared |= {r["i"] for r in d["sequences"] if r["cleared"]}
    return [i for i in range(first, first + n) if i not in cleared]


def fight_specs(product, picks, which):
    """[(sequence i, floor k, spec)]: `which` "fatal" (the product's last,
    lost floor) or "boss" (floor 10, the product's entry HP)."""
    rows = {r["i"]: r for r in product["sequences"]}
    seqs = {s["i"]: s for s in gauntlet.sequences(max(picks) + 1)}
    out = []
    for i in picks:
        floors = rows[i]["floors"]
        k = len(floors) - 1 if which == "fatal" else len(gauntlet.SHAPE) - 1
        if which == "fatal":
            assert not floors[k]["won"], f"sequence {i}: the product's last floor is a win"
        s, f = seqs[i], seqs[i]["fights"][k]
        assert f["encounter"] == floors[k]["encounter"], f"sequence {i} floor {k}: spec differs from the file"
        out.append((i, k, {"encounter": f["encounter"], "deck": s["deck"], "seed": f["seed"],
                           "hp": floors[k]["hp_start"], "character": s["character"], "group": f["group"]}))
    return out


def play_rollout(spec, ev, n, threads, seed):
    """One fight with the rollout player: {won, hp_start, hp_end, turns,
    decisions, playouts, seconds}."""
    t0 = time.perf_counter()
    c = sts.Combat(spec["deck"], spec["encounter"], seed=spec["seed"], hp=spec["hp"], character=spec["character"])
    hp_start = c.player_hp()
    rng = np.random.default_rng([seed, spec["seed"]])
    decisions = playouts = overrides = 0
    while not c.is_over() and c.turn() <= TURN_LIMIT:
        acts = c.legal_actions()
        if len(acts) > 1:
            data = c.encode()
            starts = []
            for a in acts:
                for _ in range(n):
                    x = sts.Combat.decode(data, seed=int(rng.integers(2**63)))
                    x.step(a)
                    starts.append(x)
            res = sts.play_on(starts, evaluator=ev.evaluator, features=ev.features, limit=bench.LIMIT,
                              threads=threads)
            vals = np.array([float(r["won"]) * (1 + HP_WEIGHT * max(0, r["hp_end"])) for r in res])
            means = vals.reshape(len(acts), n).mean(axis=1)
            top = np.flatnonzero(means == means.max())
            pol = acts.index(sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)["action"])
            best = pol if pol in top else int(top[0])  # ties (all rollouts lost, say) keep the policy's choice
            overrides += best != pol
            playouts += len(starts)
            decisions += 1
        else:
            best = 0
        c.step(acts[best])
    return {"won": bool(c.is_over() and c.won()), "hp_start": hp_start, "hp_end": c.player_hp(),
            "turns": c.turn(), "decisions": decisions, "overrides": int(overrides), "playouts": playouts,
            "seconds": round(time.perf_counter() - t0, 1)}


def play_plain(spec, ev, threads):
    """The policy itself on the fight, through the engine's runner (as the
    gauntlet plays one-turn players)."""
    t0 = time.perf_counter()
    r = bench.run_specs([spec], ev=ev, search={"limit": bench.LIMIT, "threads": threads})[0]
    return {"won": bool(r["won"]), "hp_start": r["hp_start"], "hp_end": r["hp_end"],
            "seconds": round(time.perf_counter() - t0, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--never-cleared", type=int, metavar="K", help="first K sequences no player clears (fatal fight)")
    g.add_argument("--cleared", type=int, metavar="K", help="first K sequences the product clears (boss fight)")
    ap.add_argument("--product", default=PRODUCT)
    ap.add_argument("--policy", default=POLICY, help="rollout policy (a player spec); one-turn search")
    ap.add_argument("--n", type=int, default=16, help="rollouts per legal action")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0, help="rollout seed")
    ap.add_argument("--plain", action="store_true", help="play the policy itself (reproducibility check)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    product = load(args.product)
    if args.never_cleared:
        picks = never_cleared(standard_files())[:args.never_cleared]
        which = "fatal"
    else:
        picks = sorted(r["i"] for r in product["sequences"] if r["cleared"])[:args.cleared]
        which = "boss"
    fights = fight_specs(product, picks, which)
    ev = bench.load_evaluator(args.policy)
    done = {}
    if os.path.exists(args.out):  # resume: keep fights already played with these settings
        old = load(args.out)
        if old["settings"] == {k: v for k, v in vars(args).items() if k != "out"}:
            done = {(r["i"], r["floor"]): r for r in old["fights"]}
    settings = {k: v for k, v in vars(args).items() if k != "out"}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    rows = []
    for i, k, spec in fights:
        if (i, k) in done:
            rows.append(done[(i, k)])
            continue
        r = play_plain(spec, ev, args.threads) if args.plain else play_rollout(spec, ev, args.n, args.threads, args.seed)
        rows.append({"i": i, "floor": k, "encounter": spec["encounter"], **r})
        print(f"seq {i} floor {k} {spec['encounter']} hp {spec['hp']}: {'won' if r['won'] else 'lost'} "
              f"hp_end {r['hp_end']} ({r['seconds']} s)", flush=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"settings": settings, "fights": rows}, f, indent=1)
    wins = sum(r["won"] for r in rows)
    print(f"{args.out}: {wins} / {len(rows)} won, mean {np.mean([r['seconds'] for r in rows]):.0f} s per fight")


if __name__ == "__main__":
    main()
