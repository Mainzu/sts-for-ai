"""Games for the two-turn self-play round (docs/specs/two-turn-round.md):
elite and boss fights on varied training decks at run-like HP, played by a
net player either two turns deep (the product's play mode: the stepped
fallback player of depth_paired, one sample seed per turn, principal line
stepped) or one turn deep (`sts.run` search with the same evaluator), and
stored as a registry dataset with real-outcome labels and no search values.

    python scripts/two_turn_games.py --player runs/<id>/model.pt@hpe0.01 --n-per-group 1500 --seed 41 \\
        [--depth two|one] [--threads 3] [--max-nodes M]

Prints the dataset id; a dataset whose config matches is reused. A
stopped two-turn run resumes from its partial file under cache/.
"""

import argparse
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "analysis"))
import depth_paired  # noqa: E402
import ladder  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import stsnet  # noqa: E402

GROUPS = ["elite", "boss"]  # selfplay.GROUPS[1:]: the hallway group is generated and dropped
HP = [0.4, 1.0]  # run-like HP: whole HP uniform over this share of max HP
CHUNK = 200  # fights per run_guarded call: a pace line early, resumable in between
PLAY_CHUNK = 400  # one-turn games per sts.run, as finetune.games
# Deck kinds (`decks`): the training pool, or decks holding the held-out cards.
DECKS = {"varied": selfplay.varied_deck, "held-out": selfplay.varied_held_out_deck}


def run_like_hp(rng, top=None):
    """A whole HP uniform over HP of `top` (default the Ironclad's max HP):
    selfplay.varied_hp's form with a floor at 40%."""
    top = selfplay.max_hp() if top is None else top
    lo, hi = HP
    return int(rng.integers(max(1, math.ceil(lo * top)), max(1, round(hi * top)) + 1))


LUCK = {"limit": 64, "samples": 16}  # luck logging's settings (sts.run's luck_limit, luck_samples)


def config_of(player, n_per_group, seed, depth, max_nodes=None, encounters=None, decks="varied", luck=None):
    """The dataset's identity (registry.find matches on it); `encounters`
    (boss fights only, `specs_for`) is part of it only when given, `decks`
    (a DECKS key) as `setups`; `luck` (a net path: the luck net,
    docs/specs/luck-corrected-labels.md; one-turn games only) only when
    given."""
    if decks not in DECKS:
        raise ValueError(f"decks must be one of {sorted(DECKS)}, not {decks!r}")
    if depth == "two":
        search = {"limit": selfplay.LIMIT, **ladder.TWO_TURN, "line_seed": True, "step_line": True}
        if max_nodes is not None:
            search["max_nodes"] = int(max_nodes)
    elif depth == "one":
        search = {"limit": selfplay.LIMIT}
    else:
        raise ValueError(f"depth must be 'two' or 'one', not {depth!r}")
    config = {"kind": "two-turn games", "player": player, "depth": depth, "search": search,
              "groups": list(GROUPS), "setups": decks, "hp": list(HP),
              "n_per_group": int(n_per_group), "seed": int(seed), "character": "ironclad"}
    if encounters:
        config.update(groups=["boss"], encounters=[str(e) for e in encounters])
    if luck:
        if depth != "one":
            raise ValueError("luck logging plays one-turn games only")
        config["luck"] = {"net": str(luck), **LUCK}
    return config


def specs_for(n_per_group, seed, encounters=None, decks="varied"):
    """(specs, groups) of the elite and boss groups: selfplay.make_specs with
    varied decks and run-like HP, the hallway group dropped after generation
    so the kept groups' decks and seeds are the full call's. With
    `encounters` (boss encounters the training groups lack, e.g. the_guardian
    and hexaghost): the boss group only, its fights' encounters taken from
    the list in turn, decks, seeds and HP unchanged; an unknown name raises.
    `decks`: the DECKS kind the decks are drawn from."""
    specs, groups = selfplay.make_specs(n_per_group, seed, DECKS[decks], hp_fn=run_like_hp)
    keep_groups = ["boss"] if encounters else GROUPS
    keep = [i for i, g in enumerate(groups) if selfplay.GROUPS[g] in keep_groups]
    specs, groups = [specs[i] for i in keep], [groups[i] for i in keep]
    if encounters:
        for e in encounters:
            sts.Combat(selfplay.STARTER, e, seed=0, character="ironclad")  # raises on an unknown encounter
        specs = [(encounters[j % len(encounters)], *s[1:]) for j, s in enumerate(specs)]
    return specs, groups


def as_dict(spec):
    enc, deck, seed, hp = spec
    return {"deck": [str(c) for c in deck], "encounter": enc, "seed": int(seed), "hp": int(hp), "character": "ironclad"}


def play_two(specs, player, search, threads, partial, log):
    """The stepped fallback two-turn player on every spec, CHUNK fights at a
    time, actions recorded; logs the first chunk's pace."""
    two = {k: v for k, v in search.items() if k not in ("line_seed", "step_line")}
    out, t0 = [], time.perf_counter()
    for i in range(0, len(specs), CHUNK):
        part = [as_dict(s) for s in specs[i:i + CHUNK]]
        t = time.perf_counter()
        out += depth_paired.run_guarded(part, two, -1.0, player, threads, partial=partial,
                                        seed_per_turn=True, step_line=True, record=True)
        dt = (time.perf_counter() - t) / 60
        if i == 0 and dt > 0:
            log(f"  first {len(part)} fights: {len(part) / max(dt * threads, 1e-9):.1f} fights per thread-minute"
                f" ({dt:.1f} min at {threads} threads)")
        log(f"  {len(out)} / {len(specs)} fights, {(time.perf_counter() - t0) / 60:.0f} min")
    return out


def luck_net(path):
    """The unpriced `sts.NetEvaluator` of the net at `path` (a player
    string's settings are refused: the luck net carries no price)."""
    if "@" in str(path):
        raise ValueError(f"the luck net is a plain net path, not a player string: {path}")
    import torch
    torch.set_num_threads(1)
    model, norm, meta = stsnet.load(path)
    return stsnet.rust_evaluator(model, norm, meta)


def play_one(specs, player, search, threads, log, luck=None):
    """One-turn search games with the player's evaluator (its price
    included); `luck` (the config's luck dict) logs each game's luck."""
    import bench
    ev = bench.load_evaluator(player)
    lk = {} if not luck else {"luck": luck_net(luck["net"]), "luck_limit": luck["limit"],
                              "luck_samples": luck["samples"]}
    out, t0 = [], time.perf_counter()
    for i in range(0, len(specs), PLAY_CHUNK):
        res = sts.run("search", specs[i:i + PLAY_CHUNK], evaluator=ev.evaluator, features=ev.features, record=True,
                      limit=search["limit"], character="ironclad", **lk, **stsnet.job_threads({"threads": threads}))
        for r in res:
            r.pop("states", None)
        out += res
        log(f"  {len(out)} / {len(specs)} games, {(time.perf_counter() - t0) / 60:.0f} min")
    return out


def dataset(player, n_per_group, seed, depth, threads, root=registry.ROOT, log=print, max_nodes=None,
            encounters=None, decks="varied", luck=None):
    """The registry dataset id of `n_per_group` elite and `n_per_group` boss
    games by `player` at `depth` ("two": the stepped fallback player; "one":
    one-turn search), stored once and reused; with `encounters`, only the
    `n_per_group` boss games on those encounters (`specs_for`); `decks`: a
    DECKS kind; `luck`, a net path, logs each game's luck (config_of)."""
    config = config_of(player, n_per_group, seed, depth, max_nodes, encounters, decks, luck)
    ds = registry.find(config, root=root)
    if ds is not None:
        return ds
    specs, groups = specs_for(n_per_group, seed, encounters, decks)
    log(f"two-turn games: {len(specs)} {depth}-turn fights by {player}")
    if depth == "two":
        os.makedirs(registry.cache_dir(root), exist_ok=True)
        partial = os.path.join(registry.cache_dir(root), f"twoturn-{registry._hash(config)[:16]}.partial.jsonl")
        res = play_two(specs, player, config["search"], threads, partial, log)
    else:
        res = play_one(specs, player, config["search"], threads, log, config.get("luck"))
    recs = registry.records(specs, groups, res, {"character": "ironclad"})
    ds = registry.write_dataset(recs, config, root=root)
    if depth == "two" and os.path.exists(partial):
        os.remove(partial)  # the resume log: registry.find answers from now on
    return ds


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--player", required=True, help="player string, e.g. runs/<id>/model.pt@hpe0.01")
    ap.add_argument("--n-per-group", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--depth", choices=("two", "one"), default="two")
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--max-nodes", type=int, default=None, help="smoke runs only: a smaller two-turn node cap")
    ap.add_argument("--encounters", default="", help="comma list of boss encounters: boss fights only, these in turn")
    ap.add_argument("--decks", choices=sorted(DECKS), default="varied")
    ap.add_argument("--luck", default=None, help="a net path: log each game's luck with it (one-turn games)")
    args = ap.parse_args(argv)
    ds = dataset(args.player, args.n_per_group, args.seed, args.depth, args.threads, max_nodes=args.max_nodes,
                 encounters=[e for e in args.encounters.split(",") if e] or None, decks=args.decks, luck=args.luck)
    print(ds)
    return ds


if __name__ == "__main__":
    main()
