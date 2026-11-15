"""Learned-play training pipeline: self-play rounds into registry datasets,
a value net trained per round on their replayed features, and one immutable
run per round (model, curves, optional bench results, a line in
runs/index.csv).

Every config plays rounds 0..N (Amendments 1 and 2). Score configs take
curriculum labels (`ladder`, docs/specs/curriculum.md): a state's exact
value from the solved-position database, else from round 1 the playing
net's search number blended with the outcome inside that net's trusted zone
(`trusted_zone`, recorded in its round.json), else the game's real outcome.
No heuristic value is in any label. Before a round trains, its new
dataset's first `solve_games` games (round 0's pool: `solve_games0`) are
walked back into the database (`solve_step`), so rung 1 covers the tails of
the games each net trains on; every score run's config records its label
settings (`label_settings`), and round.json the database's row count
(`db_rows`) and how many examples took each rung (`rungs`, `rung_counts`).
- Round 0: search + heuristic plays; the net trains on those games.
- Round k >= 1: search + round k-1's net plays fresh seeds, picking options
  by softmax over their values (temperature), and a fresh net trains on its
  games and round k-1's, plus round 0's while round 0 is still in. Round 0
  leaves for good from the round after a net reaches the heuristic: its
  tight-fight win rate (one-turn search, the monotone check's specs) at or
  above search + heuristic's by point estimate on both halves (the
  heuristic measured once per config). From then on the window is the last
  2 rounds, and each round plays `n_late` games per group.
- Ranking loss (every config): from round 1, a pairwise term orders each
  sampled decision's options like the playing net's recorded search values;
  every searched option's afterstate becomes an example, labelled with the
  game's real outcome. Round 0's examples carry inert ranking fields.
- Round-0 pool (`d0_sample`, the sweep's setting): round 0's games are a
  large heuristic pool; round 0's net trains on a random fraction of its
  examples (`round0`, drawn across all games with a fixed seed, and trained
  with `round0_seed`, so configs differing only in later rounds share it),
  and while round 0 is in, rounds >= 1 use another fraction (`later`),
  drawn once per `round_seed` and the same in every round. Absent: all of
  round 0's examples everywhere.
- Validation: heuristic games labelled with their real outcomes, every
  round, so validation error is against ground truth.
Every round is its own registry run (`<name>-r<k>`) with `round.json`: its
datasets, the window (datasets, whether round 0 is in), parent run, val MSE,
the label scale check (per training dataset, |mean label - mean real
outcome|, warned over LABEL_SCALE_TOL), from round 1 the tight-fight win
rate of its net with one-turn search (`tight_win`) and its comparison with
the heuristic per half, and from round 2 the monotone check against the
previous round's (ok unless a half's interval lies wholly below the
previous one's), and from round 1 each tight fight's result per player
(`tight_results`) and the deciding gate (`gate`, Amendment 5: per half the
net's paired lead over the heuristic on the same specs, its 95% interval
above 0 on both halves).
- Stop rule (Amendment 3, `rounds.min`): from round `min` on, a run stops
  after the first round whose gate is met, else it goes on to round `n`.
  Without `min`, every round to `n` runs.

A config (configs/*.json) names the run and fixes the data and training:
`mode` (effects | ids), `n_train` / `n_val` games per encounter group,
`train_seed` / `val_seed` (spec seeds, as selfplay.all_sets), optional
`n_round` (games per group of rounds >= 1; default n_train), `n_late`
(games per group of the rounds after round 0 retires; default n_round),
`round_seed`
(added to the spec seeds of rounds >= 1, so seeds of a sweep config play
different later games over the same round-0 data, and seeding their pool
sample; default 0), `d0_sample` ({"round0": f, "later": g}, fractions of
round 0's examples; default all), `round0_seed` (round 0's training seed;
default `seed`), `rounds`
({"n", "temperature", "every", "min"}, defaults 3, 0.05, 1, none; `every`
thins the monotone check's tight fights, `min` turns on the stop rule), `search` (sts.run settings of every
round's self-play search; default SELFPLAY_SEARCH), `seed` (training) and
`switches` (all off when absent):
- `hp_loss` (switch 6): true; self-play runs in no-death mode (unless the
  top-level `no_death` is false: normal self-play, a death labelled a
  non-win; docs/specs/survival-score.md), the net
  predicts a histogram over the HP lost to the end of combat
  (stsnet.N_BINS bins, cross-entropy), and search scores it with the fixed
  external formula (stsnet.external_score). Labels are one-hots of the real
  HP lost (selfplay.hp_target); the ranking term uses the external score.
  The label scale check reads a histogram as its expected HP lost.
- `branches` (switch 7): true; from round 1 each self-play game may get one
  branch game (registry.selfplay, selfplay.pick_branches): forced through
  the main game up to a decision with an option valued below its best by
  more than `branch_gap` (config key; absent: the temperature, as before
  Amendment 4), then that option, and played on; its examples come only
  from after the forced action, with its own outcome.
With every switch off, round 0 is today's selfplay + train pipeline (its
inert ranking fields change nothing).

`setups` (Amendment 3): "varied" (default) starts every self-play and
validation game at a random HP with a 13-25-card deck
(selfplay.VARIED; the dataset config records it, so datasets of the old
setups are never reused for it); "fixed" plays the older full-HP
starter + 5 decks.

`teacher` (docs/specs/distill-two-turn.md; absent: off): from round 1,
up to `states` elite and boss decisions of each round's new dataset are
re-searched two turns deep by the net that played it, and their options'
`rank_value` (the ranking term's order) takes the two-turn values (`teach`;
settings and defaults in TEACHER). round.json records `teacher`.

`hp_weight` (docs/specs/hp-weight.md; absent: off): w > 0; every outcome
label (and finished options' exact part) scores a win 2 - w x HP lost /
100, at least WIN_FLOOR (`weigh_hp`), so the net trades w% of a win per HP.
Search still scores a finished combat unweighted. Not with switch 6,
`teacher` or `rung4`; the solved database isn't used; a reused round 0
must have the same weight.

    python scripts/learn.py --config configs/baseline.json [--bench]
"""

import argparse
import itertools
import json
import os
import shutil
import sys
import time
import types

# The engine's search recurses once per action and chance event of a line
# of play; long turns overflowed the 2 MB default thread stack (job 0975).
os.environ.setdefault("RUST_MIN_STACK", str(64 << 20))

import numpy as np

import registry
import selfplay
import sts
import stsnet
import train
from stsnet import Dataset

# The self-play search of every round (A3: the deepest setting measured
# whose net-guided round fits ~20 min, docs/decisions.md). The evaluated
# agent (bench, monotone check) always plays one-turn search.
SELFPLAY_SEARCH = {"limit": 16}
ROUND_SEED = 100  # round k plays spec seed train_seed + ROUND_SEED * k (+ round_seed)
# Largest |mean label - mean real outcome| of a training dataset before a
# warning: 0.1 on the score scale, 10 HP with switch 6.
LABEL_SCALE_TOL = {False: 0.1, True: 10.0}
RANK_WEIGHT = 1.0  # the ranking loss's weight (every config, Amendment 2)
D0_SAMPLE_SEED = 424242  # round 0's pool samples: round 0 at this seed, later rounds at +1 + round_seed
# Exact examples from the solved-position database (curriculum): at most
# EXACT_CAP examples per training set (decision states and their options'
# afterstates), drawn at EXACT_SEED, weighing EXACT_SHARE of the total value
# loss. Config keys `exact_cap`, `exact_share` override them.
# Amendment 3 raised the cap to A3_CAP (the 2026-10-28 night drew ~9.2k
# decisions under 50,000); `exact_leaves` adds each exact option's paused
# state (End turn's, before the draw) as a value example, and `exact_split`
# (A3_SPLIT) of the drawn decisions come from rows at turns_left >= 1;
# configs without them draw as Amendment 2. Amendment 3 failed its
# one-round check, so the defaults are the night's again (owner away,
# 2026-10-29, docs/decisions.md).
EXACT_CAP = 50_000
EXACT_SHARE = 0.2
EXACT_SEED = 515151
EXACT_LEAVES = False
EXACT_SPLIT = None
A3_CAP = 150_000
A3_SPLIT = 0.5
FETCH = 1000  # database rows read per call
# Rung 3 (curriculum): inside the playing net's trusted zone a label is
# W_NEAR x its search number + (1 - W_NEAR) x the outcome. A horizon of the
# bench puzzles is verified when it has at least MIN_PUZZLES puzzles and the
# net's mean exact regret there is at most REGRET_MAX. Config keys `w_near`,
# `min_puzzles`, `regret_max` override them.
W_NEAR = 0.8
MIN_PUZZLES = 50
REGRET_MAX = 0.01
# Options whose exact values lie within TIE_EPS of each other are tied.
# A decision is dull when every option but End turn is a best one: all
# options tied, or only ending the turn with cards still playable loses
# value. The zone and the exact examples leave dull decisions out
# (Amendment 2).
TIE_EPS = 1e-9


def dull(values, ends, bounded=None):
    """Whether a decision is dull: its options' exact `values`, `ends[k]`
    true for the option that ends the turn; `bounded[k]` true when option
    k's value is only an upper bound (solver bounds), which is never tied."""
    best = max(values)
    bounded = bounded or [False] * len(values)
    return all(best - v <= TIE_EPS and not b for v, e, b in zip(values, ends, bounded) if not e)
# Solve step (curriculum): before a round trains, the first SOLVE_GAMES games
# of its new dataset (round 0: SOLVE_GAMES0) are walked back into the
# database. Counts of games, not time, so runs stay reproducible; sized from
# the bench set's build rate (~3.0 s per game on 6 threads, docs/decisions.md)
# to ~15 min per round and ~60 min for the round-0 pool. Config keys
# `solve_games`, `solve_games0` override them.
SOLVE_GAMES = 300
SOLVE_GAMES0 = 1200


def data_search(cfg):
    """`sts.run` settings of the self-play search."""
    return dict(cfg.get("search", SELFPLAY_SEARCH))


def dataset(cfg, which, root=registry.ROOT, rnd=0, parent=None, log=print, late=False):
    """Train or validation dataset id: reused when already generated. Round
    `rnd` > 0 plays fresh seeds with search + `parent` (a registry run),
    `n_late` games per group when `late` (round 0 retired)."""
    seed = cfg[f"{which}_seed"] + ROUND_SEED * rnd + (cfg.get("round_seed", 0) if rnd > 0 else 0)
    n_round = cfg.get("n_round", cfg["n_train"])
    n = (cfg.get("n_late", n_round) if late else n_round) if rnd > 0 else cfg[f"n_{which}"]
    varied = cfg.get("setups", "varied") == "varied"
    gen = {"set": which, "n_per_group": n, "spec_seed": seed, "decks": "varied_deck" if varied else "train_deck",
           "sample_seed": seed + 12345, "search": data_search(cfg)}
    low = cfg.get("low_hp") if varied and rnd > 0 else None  # lean-loop spec: rounds >= 1 only, round 0's pool stays shared
    if varied:
        gen["setup"] = {k: list(v) for k, v in selfplay.VARIED.items()}
        if low:
            gen["setup"]["low_hp"] = [low["share"], *low["hp"]]
    kinds = sorted(cfg["train_pool"]) if varied and which == "train" and "train_pool" in cfg else None
    if kinds:  # coverage pilot: training decks from these card kinds only; validation stays the full pool
        gen["train_pool"] = kinds
    full = varied and cfg.get("deck_pool") == "all"  # all-content net: held-out cards in train and val decks
    if full:
        if "train_pool" in cfg:
            raise ValueError("deck_pool and train_pool both set")
        gen["deck_pool"] = "all"
    bosses = list(cfg.get("bosses") or [])  # all-content net: the boss group's encounters in turn
    if bosses:
        gen["bosses"] = bosses
    packs = packs_of(cfg)  # pack learn: the packs' cards and encounters in train and val games
    if packs:
        if not full:
            raise ValueError("packs needs setups varied and deck_pool all")
        gen["packs"] = [h for _, h in packs]
    content = content_of(cfg) if varied and which == "train" else None
    if content:  # registry-lite: a share of training decks hold generated train-split power cards
        gen["content"] = {"hash": content[1], "share": float(cfg["content_share"])}
        if content_split(cfg) != "train":  # oracle arm: train on the held-out powers (key absent by default)
            gen["content"]["split"] = content_split(cfg)
    if no_death(cfg):
        gen["no_death"] = True
    asc = cfg.get("ascension", 0)  # the game's level every fight is played at (docs/specs/ascension.md)
    if asc:
        gen["ascension"] = asc
    if parent is not None:
        gen.update(round=rnd, explore=rounds(cfg)["temperature"])
        if cfg.get("switches", {}).get("branches"):
            gen["branches"] = True
            if "branch_gap" in cfg:
                gen["branch_gap"] = cfg["branch_gap"]
    ds = registry.find(gen, parent_model=None if parent is None else parent.id, root=root)
    if ds is None:
        t = time.perf_counter()
        if varied:
            hp_fn = selfplay.low_hp_fn(low["share"], *low["hp"]) if low else selfplay.varied_hp
            deck_fn = selfplay.pool_deck(kinds) if kinds else selfplay.full_pool_deck if full else selfplay.varied_deck
            if packs:
                deck_fn = selfplay.pack_pool_deck([c for p, _ in packs for c in selfplay.pack_cards(p)])
            if content:
                deck_fn = selfplay.content_deck(deck_fn, selfplay.content_cards(content[0], content_split(cfg)),
                                                gen["content"]["share"])
            specs, groups = selfplay.make_specs(gen["n_per_group"], seed, deck_fn, hp_fn=hp_fn, ascension=asc)
        else:
            specs, groups = selfplay.make_specs(gen["n_per_group"], seed, selfplay.train_deck, ascension=asc)
        if bosses:
            specs = selfplay.with_bosses(specs, groups, bosses)
        if packs:
            specs = selfplay.with_pack_encounters(specs, groups, [p for p, _ in packs])
        ev = {} if parent is None else evaluator(parent)
        ds, _ = registry.selfplay(specs, groups, gen, None if parent is None else parent.id, root=root, log=log,
                                  keep_results=False, **ev)
        log(f"dataset {ds} ({which}, round {rnd}): {len(specs)} games, {time.perf_counter() - t:.0f}s")
    return ds


def content_of(cfg):
    """(pack, hash) of the config's generated content (keys `content`,
    `content_share`; registry-lite step 5), loaded into this process; None
    without it or at share 0."""
    if not cfg.get("content") or not cfg.get("content_share", 0) > 0:
        return None
    return selfplay.load_content(cfg["content"])


def packs_of(cfg):
    """[(pack, hash)] of the config's `packs` (pack files, docs/specs/pack-learn.md),
    loaded into this process; [] without them."""
    return [selfplay.load_content(p) for p in cfg.get("packs") or []]


def content_split(cfg):
    """Which split's power cards the training decks get: `content_split`,
    "train" by default; "test" is the oracle arm (does the generated-power
    bench show learning when training sees its own powers?)."""
    split = cfg.get("content_split", "train")
    if split not in ("train", "test"):
        raise ValueError(f"content_split {split!r}: expected 'train' or 'test'")
    return split


def evaluator(run):
    """{"evaluator", "features"} of a run's net, for `sts.run`."""
    import bench
    ev = bench.load_evaluator(run.model_path)
    return {"evaluator": ev.evaluator, "features": ev.features}


def rounds(cfg):
    """The config's round settings."""
    return {"n": 3, "temperature": 0.05, "every": 1, "min": None, **cfg.get("rounds", {})}


def hp_loss(cfg):
    """Switch 6 is on."""
    return bool(cfg.get("switches", {}).get("hp_loss"))


def no_death(cfg):
    """Whether self-play runs in no-death mode: switch 6 with the top-level
    `no_death` key absent or true (as before the survival-score spec);
    `no_death: false` keeps normal self-play (deaths are real games)."""
    return hp_loss(cfg) and bool(cfg.get("no_death", True))


# `hp_weight` (docs/specs/hp-weight.md): a won game's score 2 - HP lost / 100
# becomes 2 - w x HP lost / 100, floored here so a win stays above a loss (0).
WIN_FLOOR = 0.1


def hp_scale(score, w):
    """Scores on the 0-2 scale with HP lost weighted by `w`: a win (score >
    0) 2 - w x (2 - score), at least WIN_FLOOR; a loss stays 0."""
    s = np.asarray(score, np.float64)
    out = np.where(s > 0, np.maximum(2 - w * (2 - s), WIN_FLOOR), s)
    return out.astype(np.asarray(score).dtype)


def weigh_hp(d, cfg):
    """`d`'s outcome labels (and targets, which are outcomes when loaded)
    with HP lost weighted by the config's `hp_weight`; `d` itself without
    it. An option's finished outcomes (`opt_const`, the sum of prob x
    score) are weighted as one win at their mean score over the finished
    mass (1 - the option's unfinished outcomes' probabilities): exact when
    they are all wins with the same HP lost, which is the usual case."""
    w = cfg.get("hp_weight")
    if not w:
        return d
    for k in ("outcome", "target"):
        if getattr(d, k, None) is not None:
            setattr(d, k, hp_scale(getattr(d, k), w))
    c = getattr(d, "opt_const", None)
    if c is not None and getattr(d, "option", None) is not None and (c > 0).any():
        opt = np.asarray(d.option, np.int64)
        m = opt >= 0
        key = np.where(m, np.asarray(d.decision, np.int64) * (int(opt.max()) + 1) + opt, -1)
        keys, inv = np.unique(key[m], return_inverse=True)
        q = np.zeros(len(keys))
        np.add.at(q, inv, np.asarray(d.prob, np.float64)[m])
        fin = np.zeros(len(c))
        fin[m] = 1 - q[inv]
        c64 = np.asarray(c, np.float64)
        ok = m & (c64 > 0) & (fin > 1e-6)
        out = c64.copy()
        out[ok] = fin[ok] * hp_scale(c64[ok] / fin[ok], w)
        d.opt_const = out.astype(np.asarray(c).dtype)
    return d


def check_hp_weight(cfg):
    """`hp_weight` works on outcome labels only: not with switch 6 (HP
    histograms), the two-turn teacher or rung-4 play-outs (raw-scale
    values); ValueError otherwise."""
    w = cfg.get("hp_weight")
    if w is None:
        return
    if not w > 0:
        raise ValueError(f"hp_weight must be > 0, got {w}")
    for k, on in (("switches.hp_loss", hp_loss(cfg)), ("teacher", "teacher" in cfg), ("rung4", "rung4" in cfg)):
        if on:
            raise ValueError(f"hp_weight doesn't combine with {k}")


def score_rule(cfg):
    """The config's switch-6 score rule (`score`, stsnet.score_rule): None
    for the engine rule, else the survive rule with defaults filled in."""
    return stsnet.score_rule(cfg.get("score"))


def check_score(cfg):
    """A survive `score` rule needs switch 6 in normal self-play
    (`no_death: false`) and doesn't combine with `hp_weight`; ValueError
    otherwise."""
    if score_rule(cfg) is None:
        return
    if not hp_loss(cfg):
        raise ValueError("the survive score rule needs switches.hp_loss")
    if cfg.get("hp_weight") is not None:
        raise ValueError("the survive score rule doesn't combine with hp_weight")
    if no_death(cfg):
        raise ValueError("the survive score rule needs normal self-play (no_death false)")


def check_round0(cfg, round0_cfg):
    """A reused round 0 must have been trained with the same `hp_weight`."""
    if cfg.get("hp_weight") != round0_cfg.get("hp_weight"):
        raise ValueError(f"round 0 was trained with hp_weight {round0_cfg.get('hp_weight')}, "
                         f"this config has {cfg.get('hp_weight')}")


def labels(cfg, rnd=1):
    """`selfplay.sample_states` labels on data from round `rnd`, always real
    outcomes: round 0's examples get inert ranking fields, round >= 1's add
    the options' afterstates for the ranking term (the playing net's search
    order); `rnd=None` gives the validation set's (no ranking fields)."""
    out = {}
    if rnd == 0:
        out["rank"] = True
    elif rnd:
        out["afterstates"] = True
    if hp_loss(cfg):
        out["hp_loss"] = True
        rule = score_rule(cfg)
        if rule is not None:  # only survive configs name it, so engine-rule label keys (and caches) stay
            out["score_rule"] = rule
    return out or None


# Rung 4 (docs/specs/rung4-check.md, a one-round check; no nightly config
# sets it): play-out caches, one per dataset and K, written by
# `scripts/rung4.py labels` (`idx`: example indices, `mean`: the mean of
# K play-out scores per example, `k`, `n`: the dataset's example count).
# Under runs/, not cache/: registry.evict treats cache/'s folders as LRU caches.
RUNG4_DIR = os.path.join(registry.ROOT, "runs", "rung4", "playouts")


def rung4_path(ds, k):
    """Dataset `ds`'s play-out cache at K = `k`."""
    return os.path.join(RUNG4_DIR, f"{ds}-k{k}.npz")


def rung4_playouts(ds, k):
    """(example indices, play-out means, k, example count) of dataset `ds`'s
    play-out cache; FileNotFoundError when there is none (never a
    fallback to the endings)."""
    path = rung4_path(ds, k)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: run scripts/rung4.py labels --k {k}")
    with np.load(path) as z:
        return z["idx"], z["mean"], int(z["k"]), int(z["n"])


def ladder(ds, cfg, rnd, exact=None, frontier=None, playouts=None):
    """Sets the curriculum's labels on a training dataset of round `rnd`
    from its label inputs (docs/specs/curriculum.md): `target` from the
    highest rung that applies, and `weight` (afterstates of options not
    played: 0, ranking only). Switch 6 configs and the validation set
    (`rnd=None`) keep their outcome labels and no weights.
    `exact(list of codec bytes) -> [None or (value, option values or
    None, bounded flags or None)]` looks states up in the solved-position
    database (`db_lookup`): rung 1, and a decision found there ranks its
    options' afterstates by their exact values (a bounded option's by its
    bound, ranking only: `bounded` 2).
    `frontier` is the trusted zone of the net that played the dataset
    (`dataset_frontier`): from round 1, a decision state or the played
    option's afterstate (not divergent) with a search number, at distance
    <= frontier, takes rung 3, `w_near` x search + (1 - `w_near`) x
    outcome. Everything else takes rung 5, the outcome.
    `playouts` (idx, means, k, n) of `rung4_playouts` (a config with
    `rung4`): every valued rung-5 example takes rung 4, (outcome + k x its
    play-out mean) / (k + 1); one missing from the cache, or a cache of
    another example count, raises ValueError."""
    if rnd is None or hp_loss(cfg):
        return ds
    target = ds.outcome.copy()  # rung 5
    rung = np.full(len(ds), 5, np.int8)
    if rnd >= 1 and frontier is not None:  # rung 3; round 0's games are the heuristic's
        w = cfg.get("w_near", W_NEAR)
        near = ((ds.played == 1) & (ds.kind != Dataset.KINDS["divergent"]) & ~np.isnan(ds.search)
                & (ds.distance <= frontier))
        target[near] = (w * ds.search[near].astype(np.float64)
                        + (1 - w) * ds.outcome[near].astype(np.float64)).astype(target.dtype)
        rung[near] = 3
    if exact is not None:  # rung 1
        options = {}
        codes = [ds.codec_bytes(i) for i in range(len(ds))]
        known = [i for i, c in enumerate(codes) if c]  # generated content has no codec bytes
        found = dict(zip(known, exact([codes[i] for i in known])))
        for i in range(len(ds)):
            e = found.get(i)
            if e is not None:
                target[i] = e[0]
                rung[i] = 1
                if ds.option[i] == -1 and e[1] is not None:
                    options[int(ds.decision[i])] = (e[1], e[2])
        if options:
            rank = ds.rank_value.copy()
            bounded = np.zeros(len(ds), np.int8) if ds.bounded is None else ds.bounded.copy()
            for i in np.flatnonzero(ds.option >= 0):
                opts = options.get(int(ds.decision[i]))
                if opts is not None:
                    rank[i] = opts[0][ds.option[i]]
                    bounded[i] = 2 if opts[1] and opts[1][ds.option[i]] else 0
            ds.rank_value = rank
            if bounded.any():
                ds.bounded = bounded
    if playouts is not None:  # rung 4
        idx, mean, k, n = playouts
        if n != len(ds):
            raise ValueError(f"play-out cache for {n} examples, the dataset has {len(ds)}")
        five = np.flatnonzero((rung == 5) & (ds.played == 1))
        pos = np.searchsorted(idx, five)
        found = (pos < len(idx)) & (idx[np.minimum(pos, len(idx) - 1)] == five)
        if not found.all():
            raise ValueError(f"{int((~found).sum())} rung-5 examples have no play-outs in the cache")
        target[five] = ((ds.outcome[five].astype(np.float64) + k * mean[pos].astype(np.float64))
                        / (k + 1)).astype(target.dtype)
        rung[five] = 4
    ds.target = target
    ds.weight = (ds.played == 1).astype(np.float32)
    ds.rung = rung  # for the counts in round.json (`rung_counts`); not stored
    return ds


def rung_counts(parts):
    """{"exact", "search", "outcome", "ranking_only", "exact_drawn"}, and
    "playout" (rung 4) only when above 0:
    how many of a training set's examples took each rung (examples with
    value weight), are ranking only (weight 0), and are database draws
    (`exact_examples`' decision states), over `parts` [(Dataset, its
    `rung` array or None for an exact draw)]; None for switch 6 configs."""
    out = {"exact": 0, "search": 0, "outcome": 0, "ranking_only": 0, "exact_drawn": 0}
    for d, rung in parts:
        valued = d.weight > 0
        out["ranking_only"] += int((~valued).sum())
        if rung is None:
            out["exact_drawn"] += int(valued.sum())
            continue
        for name, r in (("exact", 1), ("search", 3), ("outcome", 5)):
            out[name] += int((valued & (rung == r)).sum())
        n4 = int((valued & (rung == 4)).sum())
        if n4:
            out["playout"] = out.get("playout", 0) + n4
    return out


def load_examples(cfg, ds, rnd, root=registry.ROOT, exact=None, frontier=None, log=None):
    """Dataset `ds`'s examples as round `rnd` trains on them (`rnd=None`:
    the validation set): the cached label inputs, labelled by `ladder`,
    without their codec bytes. A config with `rung4` {"k": K} labels
    rounds >= 1 from `ds`'s play-out cache (rung 4)."""
    d = weigh_hp(registry.examples(ds, feature_mode(cfg), root=root, labels=labels(cfg, rnd), log=log), cfg)
    if cfg.get("teacher") and rnd and not hp_loss(cfg):
        teach(cfg, ds, rnd, root=root, log=log or print)  # labels it if a resumed round didn't
        d = apply_teacher(d, teacher_labels(cfg, ds, root))
    r4 = cfg.get("rung4")
    playouts = rung4_playouts(ds, r4["k"]) if r4 and rnd and not hp_loss(cfg) else None
    d = ladder(d, cfg, rnd, exact, frontier, playouts)
    d.drop_codec()
    return d


# Distillation (docs/specs/distill-two-turn.md): config key `teacher`
# re-searches drawn decisions of a round >= 1 dataset two turns deep with
# the net that played it, and their options' `rank_value` takes the
# two-turn values. A cut search keeps the one-turn values (the fallback
# player's rule, scripts/analysis/depth_paired.py). Labels are cached in
# the dataset's folder per (playing net, settings).
TEACHER = {"turns": 2, "states": 10000, "groups": ["elite", "boss"], "max_nodes": 400000, "sample_k": 4,
           "seed": 0, "threads": stsnet.NET_THREADS}
TEACHER_LOG_S = 300  # a progress line every 5 minutes, so the job queue's stall check stays quiet
# The labels finished so far are saved (`<teacher file>.partial.npz`) every
# this many decisions or seconds, so a run that dies part way resumes.
TEACHER_PARTIAL_N = 500
TEACHER_PARTIAL_S = 600


def teacher_settings(cfg):
    return {**TEACHER, **cfg["teacher"]}


def teacher_path(cfg, ds, root=registry.ROOT):
    """The cache of dataset `ds`'s teacher labels: keyed by its playing net
    and the settings (threads aside) and feature mode (example indices)."""
    t = {k: v for k, v in teacher_settings(cfg).items() if k != "threads"}
    key = registry._hash({"player": registry.load_manifest(ds, root)["parent_model"], "mode": feature_mode(cfg),
                          "labels": labels(cfg, 1), **t})[:12]
    return os.path.join(registry.datasets_dir(root), ds, f"teacher-{key}.npz")


def teacher_draw(d, t):
    """Example indices of the decision states drawn for the teacher: in
    groups `t["groups"]`, with codec bytes, whose decision has rows for >= 2
    options; up to `t["states"]`, seeded, in dataset order."""
    names = [selfplay.GROUPS.index(g) for g in t["groups"]]
    opt = d.option >= 0
    dec, first = np.unique(d.decision[opt], return_index=True)
    n_opt = np.array([len(set(o.tolist())) for o in np.split(d.option[opt], first[1:])]) if len(dec) else []
    many = set(dec[np.asarray(n_opt) >= 2].tolist())
    cand = [i for i in np.flatnonzero((d.option == -1) & np.isin(d.group, names))
            if int(d.decision[i]) in many and d.codec_len[i] > 0]
    rng = np.random.default_rng(t["seed"])
    pick = rng.choice(len(cand), min(len(cand), t["states"]), replace=False) if cand else []
    return np.sort(np.asarray(cand, np.int64)[np.asarray(pick, np.int64)])


_TEACH_EV = {}  # per worker process


def _teach_one(job):
    """(two-turn option values, cut) of one decision state."""
    import bench
    model, code, seed, t = job
    if model not in _TEACH_EV:
        _TEACH_EV[model] = bench.load_evaluator(model)
    ev = _TEACH_EV[model]
    c =sts.Combat.decode(code, seed=seed)
    r = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT, turns=t["turns"],
                   sample_k=t["sample_k"], seed=seed, max_nodes=t["max_nodes"])
    return [v for _, v in r["options"]], r["cuts"] > 0


def _load_teacher_partial(part):
    """({example index: (values, cut)}, minutes spent) of a teacher run that
    stopped part way, or ({}, 0) without one."""
    if not os.path.exists(part):
        return {}, 0.0
    with np.load(part) as z:
        vals = np.split(z["values"], np.cumsum(z["len"])[:-1])
        return ({int(i): (v.tolist(), bool(c)) for i, c, v in zip(z["idx"], z["cut"], vals)},
                float(z["minutes"]))


def _save_teacher_partial(part, done, minutes):
    ks = sorted(done)
    tmp = f"{part}.tmp{os.getpid()}.npz"
    np.savez(tmp, idx=np.array(ks, np.int64), cut=np.array([done[k][1] for k in ks], bool),
             len=np.array([len(done[k][0]) for k in ks], np.int64),
             values=np.array([x for k in ks for x in done[k][0]], np.float64), minutes=minutes)
    os.replace(tmp, part)


def teach(cfg, ds, rnd, root=registry.ROOT, log=print):
    """Labels dataset `ds` (round `rnd`) with its teacher values unless
    cached; returns the round.json record ({drawn, searched, cut, no_state,
    override, minutes, cached}), None without a `teacher` key, before round
    1, or with switch 6."""
    if not cfg.get("teacher") or not rnd or hp_loss(cfg):
        return None
    t = teacher_settings(cfg)
    path = teacher_path(cfg, ds, root)
    if os.path.exists(path):
        with np.load(path) as z:
            return {**json.loads(str(z["record"])), "cached": True}
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.perf_counter()
    d = registry.examples(ds, feature_mode(cfg), root=root, labels=labels(cfg, rnd))
    m = registry.load_manifest(ds, root)
    model = registry.Run(os.path.join(registry.runs_dir(root), m["parent_model"])).model_path
    idx = teacher_draw(d, t)
    no_state = int(sum(1 for i in np.flatnonzero((d.option == -1)
                                                 & np.isin(d.group, [selfplay.GROUPS.index(g) for g in t["groups"]]))
                       if d.codec_len[i] == 0))
    # the partial file sits beside the final one, whose name holds the teacher key
    part = path + ".partial.npz"
    done, before = _load_teacher_partial(part)
    drawn = set(idx.tolist())
    done = {i: r for i, r in done.items() if i in drawn}
    todo = [k for k, i in enumerate(idx) if int(i) not in done]
    jobs = [(model, d.codec_bytes(int(idx[k])), (t["seed"] * 1009 + int(idx[k])) % 2**64, t) for k in todo]
    log(f"teacher {ds}: {len(idx)} decisions ({len(done)} from a partial run), {t['threads']} threads")
    last = saved_t = time.perf_counter()
    saved = len(done)
    if t["threads"] <= 1:
        it = map(_teach_one, jobs)
    else:
        # not multiprocessing.Pool: a worker that dies (a search out of memory) loses its tasks there and
        # the run hangs; the executor raises BrokenProcessPool instead
        pool = ProcessPoolExecutor(t["threads"])
        it = pool.map(_teach_one, jobs, chunksize=4)
    try:
        for k, r in zip(todo, it):
            done[int(idx[k])] = r
            now = time.perf_counter()
            if len(done) - saved >= TEACHER_PARTIAL_N or now - saved_t >= TEACHER_PARTIAL_S:
                _save_teacher_partial(part, done, before + (now - t0) / 60)
                saved, saved_t = len(done), now
            if now - last >= TEACHER_LOG_S:
                last = now
                log(f"teacher {ds}: {len(done)}/{len(idx)} in {(last - t0) / 60:.1f} min")
    finally:
        if t["threads"] > 1:
            pool.shutdown(cancel_futures=True)
        if saved < len(done) < len(idx):  # stopped part way: keep what finished
            _save_teacher_partial(part, done, before + (time.perf_counter() - t0) / 60)
    res = [done[int(i)] for i in idx]
    vals = [v for v, _ in res]
    cut = np.array([c for _, c in res], bool)
    over = 0
    for i, v, c in zip(idx, vals, cut):
        if c:
            continue
        rows = np.flatnonzero((d.decision == d.decision[i]) & (d.option >= 0))
        one = {int(d.option[j]): float(d.rank_value[j]) for j in rows}
        ks = sorted(one)
        over += int(max(ks, key=lambda k: one[k]) != max(ks, key=lambda k: v[k]))
    searched = int((~cut).sum())
    rec = {"drawn": len(idx), "searched": searched, "cut": int(cut.sum()), "no_state": no_state,
           "override": over / searched if searched else None, "minutes": before + (time.perf_counter() - t0) / 60,
           "player": m["parent_model"], "settings": {k: v for k, v in t.items() if k != "threads"}}
    lens = np.array([len(v) for v in vals], np.int64)
    tmp = f"{path}.tmp{os.getpid()}.npz"
    np.savez(tmp, idx=idx, cut=cut, len=lens, start=np.concatenate([[0], np.cumsum(lens)[:-1]]).astype(np.int64),
             values=np.array([x for v in vals for x in v], np.float32), record=json.dumps(rec))
    os.replace(tmp, path)
    if os.path.exists(part):
        os.remove(part)
    log(f"teacher {ds}: {searched} searched, {rec['cut']} cut, override {rec['override']}, "
        f"{rec['minutes']:.1f} min")
    return {**rec, "cached": False}


def teacher_labels(cfg, ds, root=registry.ROOT):
    """Dataset `ds`'s cached teacher labels: {idx, cut, start, len, values}
    (each drawn decision's two-turn option values, ragged)."""
    with np.load(teacher_path(cfg, ds, root)) as z:
        return {k: z[k] for k in ("idx", "cut", "start", "len", "values")}


def apply_teacher(d, lab):
    """Sets the taught decisions' option rows' `rank_value` to their
    two-turn values (cut decisions keep theirs); returns `d`."""
    rank = d.rank_value.copy()
    for i, c, s, n in zip(lab["idx"], lab["cut"], lab["start"], lab["len"]):
        if c:
            continue
        v = lab["values"][s:s + n]
        rows = np.flatnonzero((d.decision == d.decision[i]) & (d.option >= 0))
        assert d.option[rows].max() < n, "two-turn search lists fewer options than the dataset's rows"
        rank[rows] = v[d.option[rows]]
    d.rank_value = rank
    return d


def frontier(per_horizon, min_puzzles=MIN_PUZZLES, regret_max=REGRET_MAX):
    """The trusted zone's edge from {horizon: (puzzles, mean exact regret)}:
    the last horizon of the unbroken run of verified horizons from 0, plus
    1; None when horizon 0 isn't verified."""
    h = 0
    while h in per_horizon and per_horizon[h][0] >= min_puzzles and per_horizon[h][1] <= regret_max:
        h += 1
    return h if h > 0 else None


def horizon_regrets(rows, picks):
    """({horizon: [exact regret]}, {horizon: dull puzzles}) over bench puzzle
    rows and the picked option's index per row; dull puzzles are left out."""
    per, tied = {}, {}
    for r, p in zip(rows, picks):
        exact = [o[1] for o in r["options"]]
        h = int(r["horizon"])
        if dull(exact, ["End" in o[0] for o in r["options"]]):
            tied[h] = tied.get(h, 0) + 1
        else:
            per.setdefault(h, []).append(max(exact) - exact[p])
    return per, tied


def trusted_zone(cfg, model_path):
    """A net's scores at the bench puzzles per played horizon (both halves
    together; its one-turn search, as the bench scores it; tied puzzles
    left out) and its frontier, for round.json."""
    import bench
    ev = bench.load_evaluator(model_path)
    rows = [r for half in bench.load_puzzles()["halves"].values() for r in half]
    per, tied = horizon_regrets(rows, bench.search_puzzles(ev, rows)[0])
    scores = {h: (len(v), float(np.mean(v))) for h, v in sorted(per.items())}
    lo, hi = cfg.get("min_puzzles", MIN_PUZZLES), cfg.get("regret_max", REGRET_MAX)
    per_horizon = {str(h): {"n": n, "tied": tied.get(h, 0), "regret": r} for h, (n, r) in scores.items()}
    for h in sorted(set(tied) - set(per)):
        per_horizon[str(h)] = {"n": 0, "tied": tied[h], "regret": None}
    return {"per_horizon": per_horizon, "min_puzzles": lo, "regret_max": hi, "frontier": frontier(scores, lo, hi)}


def dataset_frontier(ds, root=registry.ROOT):
    """The frontier of the net that played dataset `ds` (its parent run's
    round.json), or None (heuristic games, or no trusted zone recorded)."""
    parent = registry.load_manifest(ds, root)["parent_model"]
    if parent is None:
        return None
    rec = registry.Run(os.path.join(registry.runs_dir(root), parent))._read("round.json") or {}
    return (rec.get("trusted") or {}).get("frontier")


def label_settings(cfg):
    """The curriculum's label settings a score config records (`labels`:
    "curriculum", `w_near`, `exact_cap`, `exact_share`, `exact_leaves`,
    `exact_split` and the frontier
    rule's `min_puzzles`, `regret_max`), `cfg`'s values else the defaults;
    {} for switch 6 (outcome labels). They join sweep.ROUND0_KEYS."""
    if hp_loss(cfg):
        return {}
    return {"labels": "curriculum", "w_near": cfg.get("w_near", W_NEAR), "exact_cap": cfg.get("exact_cap", EXACT_CAP),
            "exact_share": cfg.get("exact_share", EXACT_SHARE), "exact_leaves": cfg.get("exact_leaves", EXACT_LEAVES),
            "exact_split": cfg.get("exact_split", EXACT_SPLIT), "min_puzzles": cfg.get("min_puzzles", MIN_PUZZLES),
            "regret_max": cfg.get("regret_max", REGRET_MAX)}


def solve_step(cfg, ds, rnd, root=registry.ROOT, log=print, **kw):
    """Walks back the first `solve_games` games of dataset `ds` (round 0:
    `solve_games0`) into the database under `root`, positions sourced to
    `ds` (puzzles.solve_dataset; `kw` goes to the finder; its threads are
    the config's `solve_threads`, the sweep's share of memory, else the
    finder's default from free memory). Returns the
    database's current-version row count after, or None for switch 6 (no
    solve step)."""
    if hp_loss(cfg):
        return None
    import puzzles
    n = cfg.get("solve_games0", SOLVE_GAMES0) if rnd == 0 else cfg.get("solve_games", SOLVE_GAMES)
    if n and content_of(cfg):
        raise ValueError("the solve step doesn't take generated content (no state encoding): "
                         "set solve_games and solve_games0 to 0 in a config with content")
    path = db_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t = time.perf_counter()
    db = sts.SolvedDb(path, max_gb=puzzles.MAX_GB)
    kw.setdefault("threads", cfg.get("solve_threads"))
    kw.setdefault("log", log)
    games, found = puzzles.solve_dataset(ds, db, root, n, **kw)
    db.evict()
    rows = sts.SolvedDb(path, max_gb=puzzles.MAX_GB).rows
    log(f"solve step {ds} (round {rnd}): {games} games, {found} puzzles, {rows} rows, "
        f"{time.perf_counter() - t:.0f}s")
    return rows


def db_path(root=registry.ROOT):
    """Training's own solved-position database under `root`. Not the bench
    puzzle build's `db/solved.sqlite`: its rows are the puzzles' tails, and
    training on them would inflate the trusted zone they measure."""
    return os.path.join(root, "db", "train.sqlite")


def open_db(cfg, root=registry.ROOT):
    """Training's database under `root` (only read here), or None when it
    doesn't exist or the config keeps outcome labels (switch 6, or
    `hp_weight`: the database's values are unweighted expected scores)."""
    path = db_path(root)
    return sts.SolvedDb(path) if os.path.exists(path) and not hp_loss(cfg) and not cfg.get("hp_weight") else None


def db_lookup(db):
    """`ladder`'s `exact` over a database (its rows as it was opened)."""
    return db.lookup


def exact_order(cfg, db, seed=EXACT_SEED, path=None):
    """The database's decision row ids in the order `exact_examples` draws
    them: one fixed random order (`seed`). With `exact_split` (Amendment 3)
    rows at turns_left >= 1 and at 0 each get their own fixed random order
    and are merged so that `exact_split` of any prefix comes from the first
    side; when one side runs out, the other's rest follows. The split reads
    turns_left from the database file at `path`."""
    ids = db.decision_ids()
    rng = np.random.default_rng(seed)
    split = cfg.get("exact_split")
    if not split:
        return ids[rng.permutation(len(ids))]
    import sqlite3
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        (version,), = con.execute("select id from versions where fingerprint = ?", (db.fingerprint,))
        far_ids = np.array([r[0] for r in con.execute(
            "select id from states where version = ? and options is not null and turns_left >= 1", (version,))],
            np.int64)
    finally:
        con.close()
    far = np.isin(ids, far_ids)
    sides = [ids[far], ids[~far]]
    sides = [x[rng.permutation(len(x))] for x in sides]
    # Row k of a side sits at (k + 0.5) / its share: the sides interleave
    # in proportion, and a side that runs out leaves the other's rest last.
    keys = [(np.arange(len(x)) + 0.5) / f for x, f in zip(sides, (split, 1 - split))]
    keys = np.concatenate(keys)
    return np.concatenate(sides)[np.argsort(keys, kind="stable")]


def exact_examples(cfg, db, w_self, seed=EXACT_SEED, out=None, ids=None, leaves=False):
    """Up to `exact_cap` examples from the database's decision rows, read in
    `exact_order`'s order (`seed`) until the next row's examples wouldn't
    fit: each decision state labelled with its exact value, and its options'
    afterstates as ranking-only examples (weight 0) ordered by the options'
    exact values. Dull decisions (`dull`: all options tied, or only End
    turn worse; Amendment 2) are skipped.
    The decision states' value weights together make up
    `exact_share` of the total beside `w_self` (the other examples' total
    weight). None when nothing was drawn. With `out` (a directory path) the
    examples are written there per fetch (stsnet.DatasetWriter) and come
    back memory-mapped (Amendment 1), the same arrays as in RAM.
    A bounded option (solver bounds) ranks with `bounded` 1: its afterstates
    take the bound as target with a value example's weight, so the value
    loss keeps them under it.
    For the exact-only experiment (docs/specs/exact-only.md): `ids` reads
    those rows in that order instead; `leaves` adds, per option whose state
    right after it is paused at a random event (End turn's, before the
    draw: what one-turn search scores), that state as a value example of
    its own labelled with the option's exact value; `w_self` None gives
    every value example weight 1."""
    cap = cfg.get("exact_cap", EXACT_CAP)
    share = cfg.get("exact_share", EXACT_SHARE)
    order = exact_order(cfg, db, seed) if ids is None else np.asarray(ids, np.int64)
    states, target, batches = [], [], []
    ex = {k: [] for k in ("outcome", "decision", "option", "prob", "opt_const", "rank_value", "kind", "played",
                          "bounded")}
    enc = selfplay.features(feature_mode(cfg))

    def note(s, value, decision, option, prob, const, kind, bounded=0):
        states.append(s)
        target.append(value)
        for k, v in zip(ex, (value, decision, option, prob, const, value, kind, int(option == -1), bounded)):
            ex[k].append(v)

    writer = stsnet.DatasetWriter(out) if out is not None else None
    written = 0
    full, d = False, 0
    for at in range(0, len(order), FETCH):
        for code, value, exact_opts in db.fetch(order[at:at + FETCH].tolist()):
            if dull([o[1] for o in exact_opts], [any(a.is_end_turn for a in o[0]) for o in exact_opts],
                    [o[2] for o in exact_opts]):
                continue
            s = sts.Combat.decode(code)
            opts = s.options(selfplay.LIMIT)
            assert [list(a) for a, _, _ in opts] == [list(o[0]) for o in exact_opts], "options differ from the solver's"
            after = sum(not x.is_over() for _, _, outs in opts for _, x in outs)
            paused = []
            if leaves:  # limit 1: every random event pauses, as search's End turn leaf
                unresolved = s.options(1)
                assert [list(a) for a, _, _ in unresolved] == [list(a) for a, _, _ in opts]
                paused = [(x, o[1]) for (_, _, outs), o in zip(unresolved, exact_opts) if not o[2]
                          for _, x in outs if not x.is_over() and not x.awaiting_action()]
            if len(target) + 1 + after + len(paused) > cap:
                full = True
                break
            note(s, value, d, -1, 0.0, 0.0, 0)
            for k, ((_, kind, outs), o) in enumerate(zip(opts, exact_opts)):
                const = sum(p * x.score() for p, x in outs if x.is_over())
                for p, x in outs:
                    if not x.is_over():
                        note(x, o[1], d, k, p, const, Dataset.KINDS[kind], int(o[2]))
            d += 1
            for x, value in paused:
                note(x, value, d, -1, 0.0, 0.0, 0)
                d += 1
        if states:  # encoded per fetch: all decoded states at once held ~1 GB at the cap
            batches.append(enc.encode(states, heuristic=True))
            states = []
            if writer is not None:  # this fetch's examples go to disk
                n = len(target)
                writer.append(Dataset.from_batches(batches, target[written:], np.zeros(n - written, np.int64),
                                                   {**{k: v[written:] for k, v in ex.items()},
                                                    "search": np.full(n - written, np.nan),
                                                    "distance": np.full(n - written, -1)}))
                batches, written = [], n
        if full:
            break
    if writer is not None:
        if not written:
            writer.abandon()
            return None
        writer.close()
        out = Dataset.load(out)
    elif not batches:
        return None
    else:
        n = len(target)
        out = Dataset.from_batches(batches, target, np.zeros(n, np.int64),
                                   {**ex, "search": np.full(n, np.nan), "distance": np.full(n, -1)})
    dec = out.option == -1
    w = 1.0 if w_self is None else share * w_self / ((1 - share) * dec.sum())
    out.weight = np.where(dec | (out.bounded == 1), w, 0.0).astype(np.float32)
    return out


def training_set(cfg, parts, root=registry.ROOT, samples=None, view=True, log=None):
    """(the examples a round trains on, {dataset id: label scale}, the
    examples per rung (`rung_counts`)): `parts`
    [(dataset id, its round)] labelled by `ladder` against the database and
    joined, plus the database's exact examples (`exact_examples`).
    `samples` {dataset id: (fraction, seed)} keeps only a random fraction
    of a part's examples. By default the result is a stsnet.DatasetView
    over the parts' mapped caches (Amendment 1: nothing copied; the exact
    examples are a temporary cache, deleted by its `close`); `view=False`
    joins them in RAM (Dataset.concat), the same examples."""
    db = open_db(cfg, root)
    exact = db_lookup(db) if db is not None else None
    loaded, idxs, rungs = [], [], []
    for ds, rnd in parts:
        d = load_examples(cfg, ds, rnd, root=root, exact=exact,
                          frontier=dataset_frontier(ds, root) if rnd else None, log=log)
        rung = getattr(d, "rung", None)
        idx = None
        if ds in (samples or {}):
            idx = sample_index(len(d), *samples[ds])
            rung = None if rung is None else rung[idx]
            if not view:
                d, idx = d.take(idx), None
        loaded.append(d)
        idxs.append(idx)
        rungs.append(rung)
    small = [_picked(d, i) for d, i in zip(loaded, idxs)]
    scale = {ds: label_scale(s) for (ds, _), s in zip(parts, small)}
    tmp = []
    if db is not None:
        out = None
        if view:
            tmp.append(os.path.join(registry.cache_dir(root), f"exact.tmp{os.getpid()}-{next(_EXACT_TMP)}"))
            out = os.path.join(tmp[-1], "exact")
            os.makedirs(tmp[-1], exist_ok=True)
        try:
            extra = exact_examples(cfg, db, float(sum(s.weight.sum(dtype="float64") for s in small)), out=out,
                                   ids=exact_order(cfg, db, path=db_path(root)),
                                   leaves=cfg.get("exact_leaves", False))
        except BaseException:
            for t in tmp:  # the writer's half-built files are inside
                shutil.rmtree(t, ignore_errors=True)
            raise
        if extra is not None:
            loaded.append(extra)
            idxs.append(None)
            small.append(extra)
            rungs.append(None)
    counts = None if hp_loss(cfg) else rung_counts(zip(small, rungs))
    if view:
        return stsnet.DatasetView(list(zip(loaded, idxs)), tmp), scale, counts
    return (loaded[0] if len(loaded) == 1 else Dataset.concat(loaded)), scale, counts


_EXACT_TMP = itertools.count()


def _picked(d, idx):
    """A part's per-example labels (target, outcome, weight) at its sampled
    indices, for the label scale and rung counts."""
    if idx is None:
        return d
    return types.SimpleNamespace(target=d.target[idx], outcome=d.outcome[idx],
                                 weight=None if d.weight is None else d.weight[idx])


def sample_index(n, frac, seed):
    """Sorted indices of a random `frac` of n examples (drawn across all
    games, not whole games)."""
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n, round(n * frac), replace=False))


def d0_samples(cfg, k, d0):
    """{round 0's dataset: (fraction, seed)} for round k's training under
    `d0_sample` (empty without it)."""
    f = cfg.get("d0_sample")
    if not f:
        return {}
    if k == 0:
        return {d0: (f["round0"], D0_SAMPLE_SEED)}
    return {d0: (f["later"], D0_SAMPLE_SEED + 1 + cfg.get("round_seed", 0))}


def label_scale(ds):
    """|mean label - mean real outcome| over a dataset's examples; a
    histogram label (switch 6) counts as its expected HP lost."""
    t = ds.target @ stsnet.BIN_REP if ds.target.ndim == 2 else ds.target
    return abs(float(t.mean(dtype="float64")) - float(ds.outcome.mean(dtype="float64")))


def feature_mode(cfg):
    """The feature mode a config trains on: `mode` (effects | ids), plus
    `selfplay.LOOKAHEAD` when its `lookahead` key is true (monster lookahead
    columns, docs/specs/monster-lookahead.md), then `selfplay.RATES` when its
    `rates` key is (power-rate columns, docs/specs/rate-features.md), then
    `selfplay.START` when its `start_hp` key is (docs/specs/start-hp.md),
    then `selfplay.SHOWN` / `selfplay.XHID` when its `shown_numbers` /
    `exhaust_hidden` keys are (encoder value flags, saved in the net's meta).
    Feature caches are keyed by it and by its layout; datasets are not."""
    mode = cfg.get("mode", "effects")
    mode += selfplay.LOOKAHEAD if cfg.get("lookahead") else ""
    mode += selfplay.RATES if cfg.get("rates") else ""
    mode += selfplay.START if cfg.get("start_hp") else ""
    mode += selfplay.SHOWN if cfg.get("shown_numbers") else ""
    return mode + selfplay.XHID if cfg.get("exhaust_hidden") else mode


def net_meta(cfg, mode):
    """The meta a net trained by `fit` on config `cfg` in feature `mode`
    saves, less its run, datasets and val MSE."""
    card_repr, look, rates, start = selfplay.split_mode(mode)
    return {"card_repr": card_repr, **({"lookahead": True} if look else {}), **({"rates": True} if rates else {}),
            **({"start_hp": True} if start else {}),
            **{k: True for k, on in zip(stsnet.ENCODER_FLAGS, selfplay.split_flags(mode)[1:]) if on},
            **({"score_rule": score_rule(cfg)} if score_rule(cfg) else {}),
            **selfplay.meta_vocab(mode),
            "held_out": selfplay.HELD_OUT,
            "held_out_check9": sts.held_out_card_names(), "format": selfplay.FORMAT,
            "switches": cfg.get("switches", {})}


def fit(cfg, name, parts, val_id, root=registry.ROOT, log=print, bench=False, finish=True, samples=None, seed=None):
    """Trains one net on `parts`, [(dataset id, its round)] joined, into a
    new registry run; returns (run, best val MSE, {dataset id: label
    scale}, examples per rung). `samples` {dataset id: (fraction, seed)} keeps only a random
    fraction of a part's examples; `seed` is the training seed (default the
    config's)."""
    mode = feature_mode(cfg)
    train_ds, scale, counts = training_set(cfg, parts, root, samples, log=log)  # a view over the mapped caches
    train_ids = [ds for ds, _ in parts]
    curves = {}
    try:
        val_ds = load_examples(cfg, val_id, None, root=root, log=log)
        run = registry.Run.create(name, cfg, train_ids + [val_id], root=root)
        model, norm, hist = train.train(mode, train_ds, val_ds, cfg.get("seed", 0) if seed is None else seed, log,
                                        curves, rank_weight=RANK_WEIGHT, hp_loss=hp_loss(cfg),
                                        score_rule=score_rule(cfg))
    finally:
        train_ds.close()  # its exact examples' temporary cache
        del train_ds
    ids = {"train": train_ids[0] if len(train_ids) == 1 else train_ids, "val": val_id}
    meta = {**net_meta(cfg, mode), "val_mse": min(hist), "run": run.id, "datasets": ids}
    run.save_model(model, norm, meta)
    run.save_curves(curves)
    if bench:
        import bench as bench_mod
        run.save_bench(bench_mod.bench(bench_mod.load_evaluator(run.model_path), quick=bench == "quick"))
    if finish:
        run.finish(val_mse=min(hist), feature_format=mode)
    log(f"run {run.id}: val MSE {min(hist):.4f}")
    return run, min(hist), scale, counts


# The rounds' tight fights: tight fights v2 (docs/specs/tight-fights-v2.md),
# many calibrated cells with SEEDS2 seeds each; intervals are taken over
# cells (`gate`, `win_rates` with `cells`), since a cell's fights share deck,
# encounter and HP.
TIGHT_SET = "tight2"


def tight_specs(every, ascension=0):
    """{half: specs} of the rounds' tight fights, every `every`-th seed of
    each cell (thinning never drops a cell), in set order; at an `ascension`
    level each is played at it, with the run start's deck additions and its
    HP capped at that level's max HP."""
    import bench_sets
    out = {}
    for h, specs in bench_sets.load_set(TIGHT_SET).items():
        k, prev, out[h] = 0, None, []
        for sp in specs:
            k = k + 1 if sp["cell"] == prev else 0
            prev = sp["cell"]
            if k % every == 0:
                out[h].append(at_ascension(sp, ascension) if ascension else sp)
    return out


def at_ascension(sp, ascension):
    """Bench spec `sp` played at `ascension` (docs/specs/ascension.md)."""
    rs = sts.run_start(sp["character"], ascension)
    hp = sp["hp"] if sp["hp"] is None else min(sp["hp"], rs["max_hp"])
    return {**sp, "deck": list(sp["deck"]) + rs["deck_adds"], "hp": hp, "ascension": ascension}


def tight_cells(every):
    """{half: [cell index per result]} of `tight_results` at `every`."""
    return {h: [sp["cell"] for sp in specs] for h, specs in tight_specs(every).items()}


def tight_results(ev_spec, search, every, log=None, ascension=0):
    """{half: [1 won / 0 lost per spec]} of search with an evaluator (a
    model path, or "heuristic") on the rounds' tight fights (`tight_specs`
    at `every`), in spec order, played registry.PLAY_CHUNK at a time for
    the progress line (`log`)."""
    import bench
    from progress import Progress
    ev = None if ev_spec == "heuristic" else bench.load_evaluator(ev_spec)
    halves = tight_specs(every, ascension)
    p = Progress("tight fights" + (" (heuristic)" if ev is None else ""), sum(map(len, halves.values())), log)
    out = {}
    for half, specs in halves.items():
        res = []
        for i in range(0, len(specs), registry.PLAY_CHUNK):
            res += bench.run_specs(specs[i:i + registry.PLAY_CHUNK], ev, search=search)
            p.update(len(specs[i:i + registry.PLAY_CHUNK]))
        out[half] = [int(r["won"]) for r in res]
        stalled = sum(r["turns"] > bench.PLAY_TURN_LIMIT for r in res)
        if stalled and log:
            log(f"tight fights {half}: {stalled} of {len(res)} stalled past {bench.PLAY_TURN_LIMIT} turns")
    p.close()
    return out


def cell_means(x, cells):
    """Per-cell means of `x` (cells in sorted order); `cells` None: every
    value its own cell."""
    x = np.asarray(x, float)
    if cells is None:
        return x
    ids, inv = np.unique(np.asarray(cells), return_inverse=True)
    return np.bincount(inv, weights=x) / np.bincount(inv)


def cell_interval(x, cells):
    """[mean, lo, hi]: the mean of `x`'s per-cell means with its 95%
    interval mean +- Z * sd / sqrt(cells) (sd over cells, n - 1)."""
    import bench
    m = cell_means(x, cells)
    w = bench.Z * m.std(ddof=1) / np.sqrt(len(m))
    return [bench.r6(m.mean()), bench.r6(m.mean() - w), bench.r6(m.mean() + w)]


def win_rates(results, cells=None):
    """{half: [win, lo, hi]} of `tight_results`: with `cells`
    (`tight_cells`) the per-cell interval (tight fights v2), else Wilson."""
    import bench
    if cells is None:
        return {h: bench.wilson(sum(r), len(r)) for h, r in results.items()}
    return {h: cell_interval(r, cells[h]) for h, r in results.items()}


def gate(net, heur, cells=None):
    """The deciding gate on the tight fights (Amendment 5), from both
    players' `tight_results` on the same specs: per half, the net's lead
    over the heuristic, mean(net - heuristic), with its 95% interval mean
    +- Z * sd / sqrt(n); a half passes when the interval lies above 0, the
    gate when both do. With `cells` (`tight_cells`; tight fights v2) the
    differences are averaged per cell first and n counts cells."""
    halves = {}
    for h in net:
        d = np.array(net[h], float) - np.array(heur[h], float)
        c = None if cells is None else cells[h]
        lead = cell_interval(d, c)
        rates = win_rates({"net": net[h], "heuristic": heur[h]}, None if c is None else {"net": c, "heuristic": c})
        halves[h] = {**rates, "lead": lead, "n": len(d), "cells": len(cell_means(d, c)), "above": bool(lead[1] > 0)}
    return {"halves": halves, "met": all(v["above"] for v in halves.values())}


# Config keys that only size the run's machine use (not its result): a
# restarted sweep may plan them differently and still reuse finished rounds.
RESUME_IGNORE = ("solve_threads", "solve_games", "solve_games0")


def find_round(cfg, k, train_ids, prev, root=registry.ROOT):
    """A finished round-k run (model saved, `finished` in its round.json,
    same rules version, tight fights played on TIGHT_SET) with `cfg`'s
    config (RESUME_IGNORE aside), the same training datasets and the same
    parent run, else None: a restarted
    sweep resumes after the last round it finished. Training is
    deterministic, so that run is what this round would train again."""
    def key(c):
        return {a: b for a, b in c.items() if a not in RESUME_IGNORE}
    d = registry.runs_dir(root)
    if prev is None or not os.path.isdir(d):
        return None
    for name in sorted(os.listdir(d), reverse=True):
        run = registry.Run(os.path.join(d, name))
        rec = run._read("round.json")
        if (not rec or not rec.get("finished") or rec.get("round") != k or rec.get("parent_run") != prev.id
                or rec.get("tight_set") != TIGHT_SET  # older rounds (no key) played v1's tight fights
                or rec["datasets"]["train"] != list(train_ids) or not os.path.exists(run.model_path)):
            continue
        if run._read("run.json").get("rules_version") != registry.rules_version():
            continue
        if key(run._read("config.json")) == key(json.loads(json.dumps(cfg))):
            return run
    return None


def learn(cfg, bench=False, root=registry.ROOT, log=print, bench_last_only=False, round0=None):
    """Rounds 0..N (see the module docstring); returns the per-round runs.
    `bench_last_only` benches only the final round (the stop rule's, or N). `round0`, a run whose
    round 0 had the same data, sample, labels and training seed (sweep
    configs of one target), is reused instead of retraining round 0 (it is
    the first run returned; no new run or round.json is written for it)."""
    import bench as bench_mod
    check_hp_weight(cfg)
    check_score(cfg)
    if round0 is not None:
        check_round0(cfg, round0._read("config.json") or {})
    cfg = {**cfg, **label_settings(cfg)}
    registry.clean_stale(registry.cache_dir(root))
    registry.clean_stale(registry.datasets_dir(root))  # a crashed self-play stream's folder
    r = rounds(cfg)
    val_id = dataset(cfg, "val", root, log=log)
    agent = {"limit": bench_mod.LIMIT}
    tol = LABEL_SCALE_TOL[hp_loss(cfg)]
    runs, prev, prev_new, prev_win, d0, d0_in, heur = [], None, None, None, None, True, None  # heur: tight_results
    for k in range(r["n"] + 1):
        new = dataset(cfg, "train", root, rnd=k, parent=prev, log=log, late=not d0_in)
        d0 = d0 or new
        if k == 0 and round0 is not None:
            log(f"round 0: reusing {round0.id}")
            runs.append(round0)
            prev, prev_new = round0, new
            continue
        parts = [(new, k)] + ([(prev_new, k - 1)] if prev_new else []) + ([(d0, 0)] if d0_in and k >= 2 else [])
        done = None if k == 0 else find_round(cfg, k, [d for d, _ in parts], prev, root)
        if done is not None:
            run, rec = done, done._read("round.json")
            log(f"round {k}: reusing finished {done.id}")
            net_win, vs_heur, gate_k = rec["tight_win"], rec["heuristic"], rec["gate"]
        else:
            at = {"ascension": cfg["ascension"]} if cfg.get("ascension") else {}  # the tight fights' level
            db_rows = solve_step(cfg, new, k, root, log)
            taught = teach(cfg, new, k, root, log)
            samples = d0_samples(cfg, k, d0) if d0_in or k == 0 else {}
            seed = cfg.get("round0_seed", cfg.get("seed", 0)) if k == 0 else cfg.get("seed", 0)
            run, val_mse, scale, counts = fit(cfg, f"{cfg['name']}-r{k}", parts, val_id, root, log, False,
                                              finish=False, samples=samples, seed=seed)
            scale_ok = all(v <= tol for v in scale.values())
            if not scale_ok:
                log(f"round {k}: WARNING labels off the outcome scale: "
                    + ", ".join(f"{d} {v:.3f}" for d, v in scale.items()))
            net_res = tight_results(run.model_path, agent, r["every"], log, **at) if k >= 1 else None
            cells = tight_cells(r["every"]) if net_res else None
            net_win = win_rates(net_res, cells) if net_res else None
            trusted = None if hp_loss(cfg) else trusted_zone(cfg, run.model_path)
            if trusted is not None:
                log(f"round {k}: trusted zone frontier {trusted['frontier']}")
            vs_heur = gate_k = fights = None
            window = {"datasets": [d for d, _ in parts], "round0_in": d0_in,
                      "round0_sample": samples[d0][0] if d0 in samples else None}
            if net_win is not None:
                heur = heur or tight_results("heuristic", agent, r["every"], log, **at)
                heur_win = win_rates(heur, cells)
                halves = {h: {"net": net_win[h], "heuristic": heur_win[h], "reached": net_win[h][0] >= heur_win[h][0]}
                          for h in net_win}
                vs_heur = {"halves": halves, "reached": all(v["reached"] for v in halves.values())}
                gate_k = gate(net_res, heur, cells)
                fights = {who: {h: "".join(map(str, x)) for h, x in res.items()}
                          for who, res in (("net", net_res), ("heuristic", heur))}
            mono = None
            if prev_win is not None:
                halves = {h: {"net": net_win[h], "previous": prev_win[h]} for h in net_win}
                mono = {"every": r["every"], "halves": halves,
                        "ok": all(v["net"][2] >= v["previous"][1] for v in halves.values())}
                log(f"round {k}: monotone {'ok' if mono['ok'] else 'FAIL'}; " + ", ".join(
                    f"{h} net {v['net'][0]:.3f} vs previous {v['previous'][0]:.3f}" for h, v in halves.items()))
            rec = {"round": k, "parent_run": None if prev is None else prev.id,
                   "new_dataset": new, "datasets": {"train": [d for d, _ in parts], "val": val_id},
                   "val_mse": val_mse, "explore": None if prev is None else r["temperature"],
                   "label_scale": {"tolerance": tol, "per_dataset": scale, "ok": scale_ok},
                   "tight_set": TIGHT_SET, "tight_win": net_win, "tight_results": fights, "heuristic": vs_heur,
                   "window": window,
                   "monotone": mono, "gate": gate_k, "trusted": trusted,
                   "db_rows": db_rows, "rungs": counts}
            if taught is not None:
                rec["teacher"] = taught
            content = content_of(cfg)
            if content:
                rec["content_hash"] = content[1]
                run._write("content.json", content[0])
                registry.store_pack(content[1], root)
            if packs_of(cfg):
                rec["content_hashes"] = [h for _, h in packs_of(cfg)]
            run._write("round.json", rec)
        if d0_in and vs_heur is not None and vs_heur["reached"]:
            d0_in = False
            log(f"round {k}: the net reaches the heuristic on both halves; round 0 leaves the window")
        last = k == r["n"] or (r["min"] is not None and k >= r["min"] and gate_k is not None and gate_k["met"])
        if last and k < r["n"]:
            log(f"round {k}: the net clearly beats the heuristic on both halves; stopping")
        if bench and (last or not bench_last_only) and not (done and os.path.exists(run.bench_path)):
            run.save_bench(bench_mod.bench(bench_mod.load_evaluator(run.model_path), quick=bench == "quick"))
        if done is None:
            run.finish(val_mse=val_mse, feature_format=feature_mode(cfg))
            run._write("round.json", {**rec, "finished": True})  # find_round reuses it
        runs.append(run)
        prev, prev_new, prev_win = run, new, net_win
        if last:
            break
    return runs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--bench", action="store_true", help="bench the final round's net into its run")
    ap.add_argument("--round0", help="a registry run id to reuse as round 0 (same pool, sample, labels, seed)")
    args = ap.parse_args(argv)
    with open(args.config, encoding="utf-8") as f:
        learn(json.load(f), args.bench, bench_last_only=True,
              round0=registry.Run(os.path.join(registry.runs_dir(), args.round0)) if args.round0 else None)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # progress reaches a redirected log as it happens
    main()
