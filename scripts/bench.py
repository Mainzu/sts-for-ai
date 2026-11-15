"""Evaluation bench runner: scores one evaluator on the bench sets and writes
every metric, per set half, with 95% intervals.

Evaluators: "heuristic", a saved net (path to a .pt from `stsnet.save`), or
"module:callable" (a batch dict -> scores callable, as `sts.search` takes;
an optional `features` attribute gives its `sts.Features`, else effects).

Metrics per half:
- tight (train / held_out):
  - mse: the evaluator's static value of every state of the search +
    heuristic games on the tight fights vs that game's final score (as
    checks 6/8; null for the heuristic, which has no static value in Python);
  - at the saved decisions, on all / contested / uncapped decisions:
    regret (reference value of the best option minus that of the option the
    evaluator's search picks), ranking (share of option pairs with reference
    gap >= CONTESTED that the evaluator's search values order the same way;
    ties count half), mse_search (the search's best option value vs the
    game's final score);
  - win and hp_lost: the evaluator's search playing the tight fights.
- standard (train / held_out / silent_a / silent_b): mse, win, hp_lost at
  the character's starting HP (check 5/6/8 continuity).
- gap: each metric of each other half minus train.
- puzzles (train / held_out): at the bench puzzles (data/bench/puzzles.json,
  scripts/puzzles.py), whose option values are exact (the solver's), on all
  and contested (gap >= PUZZLE_CONTESTED) puzzles: accuracy (share where the
  evaluator's search picks an exactly best option), regret (exact best value
  minus that of the option it picks), ranking (share of option pairs with
  different exact values that its search values order the same way; ties
  count half); accuracy and regret per played horizon (h0, h1, h2+).
- representation: minimal-pair probe pass rate (bench_probes.PROBES) and the
  aliasing audit over the saved decisions (effects features, and a net's own).
Intervals: bootstrap (BOOT resamples, fixed seed; states resampled by game)
for means, Wilson for win rates, normal for win-rate gaps. Search settings
are the agents' (limit LIMIT, one turn, no sampling, the engine's node cap).

    python scripts/bench.py --evaluator heuristic --out results/heuristic.json
    python scripts/bench.py --evaluator models/value_effects.pt --out results/effects.json
"""

import argparse
import importlib
import json
import os
import re
import time

import numpy as np

import bench_decisions
import bench_probes
import bench_sets
import sts
import stsnet

LIMIT = bench_sets.LIMIT
BOOT = 1000
BOOT_SEED = 0
Z = 1.959964
SUBSETS = ("all", "contested", "uncapped")
CHUNK = 4096
QUICK = {"decisions": 20, "tight": 20, "standard": 25, "puzzles": 20}  # keep every n-th
PUZZLE_CONTESTED = 0.05  # a puzzle whose gap (best minus second best) is at least this is contested
EXACT = 1e-9  # exact values this close count as equal
HORIZONS = (("h0", 0, 0), ("h1", 1, 1), ("h2+", 2, None))  # (name, lowest, highest) played horizon
PLAY_TURN_LIMIT = sts.PLAY_TURN_LIMIT  # a result with more turns stalled (lost; its `stalled` flag)


class Evaluator:
    def __init__(self, name, evaluator, features, static):
        self.name, self.evaluator, self.features, self.static = name, evaluator, features, static


HP_BONUS = "@hpb"  # `<net>.pt@hpb<c>`: the net with search's HP bonus c (stsnet.rust_evaluator)
SURVIVE_C = "@sc"  # `<net>.pt@sc<c>`: a survive net with its survival value c replaced (docs/specs/survival-score.md)
ENEMY_STRENGTH = "@esp"  # `<net>.pt@hpb<c>@esp<k>`: search's enemy-Strength price k (docs/specs/enemy-strength-price.md)
HP_END = "@hpe"  # `<net>.pt@hpe<c>`: search's end-HP bonus c (docs/specs/end-hp-bonus.md)
DRAW_LEAF = "@dl"  # `<net>.pt@hpb<c>@dl<k>`: end-of-turn leaves scored after k sampled draws (docs/specs/draw-leaf.md)
TURN_START_LEAF = "@tsl"  # `<net>.pt@hpb<c>@tsl1`: end-of-turn leaves scored after the turn-start hooks (docs/specs/turn-start-leaf.md)
LEAF_CLEAR_BLOCK = "@lcb"  # `<net>.pt@hpb<c>@lcb1`: end-of-turn leaves scored with block 0 (docs/specs/leaf-clear-block.md)
STRENGTH_HITS = "@shl"  # `<net>.pt@hpb<c>@shl<k>`: enemy Strength priced by the hits it will still land (docs/specs/strength-hits-price.md)
TIE_BREAK = "@tb"  # `<net>.pt@hpe<c>@tb1`: exact ties broken toward the sooner win, then lower enemy HP (docs/specs/finish-faster-tiebreak.md)
WIN_CAP = "@wc"  # `<net>.pt@hpe<c>@wc1`: an unfinished leaf scores at most a win at the HP it can still reach (backlog 82)
SHOWN_NUMBERS = "@sn"  # `<net>.pt@hpb<c>@sn1`: card damage and block encoded as the game shows them (docs/specs/shown-card-numbers.md)
EXHAUST_HIDDEN = "@xh"  # `<net>.pt@hpb<c>@xh1`: the exhaust pile's card counts encoded as 0 (docs/specs/shown-card-numbers.md)
PROJECTED_DEBUFFS = "@pd"  # `<net>.pt@hpb<c>@tsl1@pl<k>@pd1`: with @pl, monsters' once-a-turn Weak/Frail/Vulnerable on the player too (docs/specs/recurring-debuff-leaf.md)
PROJECTED_LEAF = "@pl"  # `<net>.pt@hpb<c>@tsl1@pl<k>`: once-a-turn Strength/Dexterity hooks k more times at the leaf (docs/specs/projected-leaf.md)
_SETTINGS = {HP_BONUS: "hp_bonus", ENEMY_STRENGTH: "enemy_strength_price", SURVIVE_C: "survive_c", HP_END: "hp_end_bonus",
             DRAW_LEAF: "draw_k", TURN_START_LEAF: "turn_start_leaf", LEAF_CLEAR_BLOCK: "leaf_clear_block",
             PROJECTED_LEAF: "projected_ticks", PROJECTED_DEBUFFS: "projected_debuffs", STRENGTH_HITS: "strength_hits_price", TIE_BREAK: "tie_break", WIN_CAP: "win_cap",
             SHOWN_NUMBERS: "shown_numbers", EXHAUST_HIDDEN: "exhaust_hidden"}
_SETTING = re.compile(r"(@hpb|@hpe|@esp|@shl|@sc|@dl|@tsl|@lcb|@pl|@pd|@tb|@wc|@sn|@xh)([0-9.eE+-]+)")


def player_settings(spec):
    """(net path, rust_evaluator kw) of a player spec: the `.pt` path, then
    any of `@hpb<c>`, `@hpe<c>`, `@esp<k>`, `@shl<k>`, `@sc<c>`, `@dl<k>` (k a whole
    number >= 1), `@tsl1`, `@lcb1`, `@pl<k>` (k whole, 1-9), `@pd1` (with `@pl<k>`), `@tb1`, `@sn1`, `@xh1`, each at most once."""
    i = spec.find(".pt@")
    if i < 0:
        return spec, {}
    base, rest, kw = spec[:i + 3], spec[i + 3:], {}
    pos = 0
    for m in _SETTING.finditer(rest):
        if m.start() != pos or _SETTINGS[m.group(1)] in kw:
            break
        try:
            kw[_SETTINGS[m.group(1)]] = float(m.group(2))
        except ValueError:  # not a number: the check below names the spec
            break
        pos = m.end()
    k = kw.get("draw_k")
    flags = tuple(kw.get(k) for k in ("turn_start_leaf", "leaf_clear_block", "projected_debuffs", "tie_break", "win_cap", "shown_numbers", "exhaust_hidden"))
    pl = kw.get("projected_ticks")
    bad_pl = (pl is not None and (pl != int(pl) or not 1 <= pl <= 9)) or (pl is None and "projected_debuffs" in kw)
    if pos != len(rest) or "+" in base or (k is not None and (k < 1 or k != int(k))) or any(f not in (None, 1) for f in flags) or bad_pl:
        raise ValueError(f"bad player setting (one .pt net, then @hpb<c> / @hpe<c> / @esp<k> / @shl<k> / @sc<c> / @dl<k> / @tsl1 / @lcb1 / @pl<k> / @pd1 / @tb1 / @wc1 / @sn1 / @xh1): {spec}")
    return base, kw


def split_player(spec):
    """(net spec, HP bonus c) of a player spec; c is 0 without `@hpb<c>`."""
    base, sep, c = spec.partition(HP_BONUS)
    return base, (float(c) if sep else 0.0)


def load_evaluator(spec):
    if ".pt@" in spec:
        base, kw = player_settings(spec)
        import stsnet
        import torch
        torch.set_num_threads(1)
        model, norm, meta = stsnet.load(base)
        return Evaluator(spec, stsnet.rust_evaluator(model, norm, meta, **kw), stsnet.features_for(meta), None)
    if spec == "heuristic":
        return Evaluator(spec, "heuristic", None, None)
    if "+" in spec and all(p.endswith(".pt") for p in spec.split("+")):
        return _load_ensemble(spec)
    if spec.endswith(".pt") or os.path.exists(spec):
        import stsnet
        import torch
        torch.set_num_threads(1)  # many runner threads each call the net
        model, norm, meta = stsnet.load(spec)
        # Search scores leaves in Rust; the prediction metric's static
        # values stay on the PyTorch net.
        return Evaluator(spec, stsnet.rust_evaluator(model, norm, meta), stsnet.features_for(meta),
                         stsnet.Evaluator(model, norm))
    module, _, attr = spec.partition(":")
    fn = getattr(importlib.import_module(module), attr)
    feats = getattr(fn, "features", None) or sts.Features("effects")
    return Evaluator(spec, fn, feats, fn)


def _load_ensemble(spec):
    """`a.pt+b.pt+...`: search scores each leaf with the mean of the nets'
    scores (docs/specs/ensemble-evaluator.md). The nets must share features."""
    members = [load_evaluator(p) for p in spec.split("+")]
    paths = spec.split("+")
    layout = [stsnet_layout(p) for p in paths]
    for p, lay in zip(paths[1:], layout[1:]):
        if lay != layout[0]:
            raise ValueError(f"ensemble members read different features: {paths[0]} and {p}")
    statics = [m.static for m in members]

    def static(batch):
        return np.mean([np.asarray(f(batch), np.float64) for f in statics], axis=0)

    return Evaluator(spec, [m.evaluator for m in members], members[0].features, static)


def stsnet_layout(path):
    """What a saved net reads: its card representation and feature layout."""
    import stsnet
    _, _, meta = stsnet.load(path)
    return meta.get("card_repr"), stsnet.layout_of(meta), {k: meta.get(k) for k in stsnet.VOCAB_KEYS}


_WEIGHTS = {}


def _weights(key, dim):
    if (key, dim) not in _WEIGHTS:
        _WEIGHTS[(key, dim)] = np.random.default_rng([dim, len(key)]).standard_normal(dim)
    return _WEIGHTS[(key, dim)]


def random_evaluator(batch):
    """Pseudo-random scores in [0, 2) from a hash of each state's features:
    unrelated to value, but the same state always gets the same score."""
    p = batch["player"].astype(np.float64)
    m = batch["monsters"].reshape(len(p), -1).astype(np.float64)
    c = batch["cards"].astype(np.float64)
    h = p @ _weights("p", p.shape[1]) + m @ _weights("m", m.shape[1])
    cw = (c @ _weights("c", c.shape[1])) * np.asarray(batch["card_count"]) * (np.asarray(batch["card_pile"]) + 1.5)
    np.add.at(h, np.asarray(batch["card_state"]), cw)
    return (2 * np.modf(np.abs(np.sin(h * 12.9898) * 43758.5453))[0]).astype(np.float32)


# --- intervals ---------------------------------------------------------------

def r6(x):
    return None if x is None else round(float(x), 6)


def ratio_boot(num, den):
    """(point, bootstrap samples) of sum(num) / sum(den) over units."""
    num, den = np.asarray(num, np.float64), np.asarray(den, np.float64)
    n = len(num)
    if n == 0 or den.sum() == 0:
        return None, None
    idx = np.random.default_rng(BOOT_SEED).integers(n, size=(BOOT, n))
    d = den[idx].sum(1)
    s = num[idx].sum(1) / np.where(d > 0, d, 1)
    return num.sum() / den.sum(), s


def interval(point, samples):
    if point is None:
        return None
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return [r6(point), r6(lo), r6(hi)]


def wilson(k, n):
    p = k / n
    c = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    w = Z * np.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return [r6(p), r6(c - w), r6(c + w)]


class Half:
    """Metrics of one set half: {name: [point, lo, hi]}, plus what the gaps
    need (bootstrap samples, win counts)."""

    def __init__(self):
        self.metrics, self.samples, self.wins, self.counts = {}, {}, {}, {}

    def mean(self, name, num, den=None):
        p, s = ratio_boot(num, np.ones(len(num)) if den is None else den)
        self.metrics[name], self.samples[name] = interval(p, s), s

    def rate(self, name, won):
        k, n = int(np.sum(won)), len(won)
        self.metrics[name], self.wins[name] = wilson(k, n), (k, n)


def gap(a, b):
    """Each metric of half `a` minus half `b`, with an interval."""
    out = {}
    for name, m in a.metrics.items():
        if m is None or b.metrics.get(name) is None:
            out[name] = None
        elif name in a.wins:
            (k1, n1), (k2, n2) = a.wins[name], b.wins[name]
            p1, p2 = k1 / n1, k2 / n2
            d, w = p1 - p2, Z * np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
            out[name] = [r6(d), r6(d - w), r6(d + w)]
        else:
            out[name] = interval(m[0] - b.metrics[name][0], a.samples[name] - b.samples[name])
    return out


# --- metrics -----------------------------------------------------------------

def run_specs(specs, ev=None, record=False, search=None):
    """Results of the search agent (heuristic, or `ev`) on bench specs, in
    order. `search`: search settings ({limit, sample_k, turns}; default the
    agents')."""
    out = [None] * len(specs)
    groups = {}
    for i, s in enumerate(specs):
        groups.setdefault((s["hp"], s["character"]), []).append(i)

    def spec(s):
        # A fight at an ascension level (docs/specs/ascension.md) goes keyed.
        t = (s["encounter"], s["deck"], s["seed"])
        return t if not s.get("ascension") else {"encounter": t[0], "deck": t[1], "seed": t[2], "ascension": s["ascension"]}
    kw = {} if ev is None else {"evaluator": ev.evaluator, "features": ev.features}
    if ev is not None and callable(ev.evaluator):  # a Python net takes turns on Python's lock
        kw["threads"] = stsnet.NET_THREADS
    kw.update(search or {"limit": LIMIT})
    kw = stsnet.job_threads(kw)
    for (hp, ch), idx in sorted(groups.items(), key=lambda g: (g[0][0] or 0, g[0][1])):
        res = sts.run("search", [spec(specs[i]) for i in idx],
                      hp=hp, character=ch, record=record, **kw)
        for i, r in zip(idx, res):
            out[i] = r
    return out


def static_values(ev, states):
    vals = []
    for i in range(0, len(states), CHUNK):
        vals.append(np.asarray(ev.static(ev.features.encode(states[i:i + CHUNK], heuristic=True)), np.float64))
    return np.concatenate(vals) if vals else np.zeros(0)


def prediction(h, ev, labels):
    """Static-value MSE over the label games' states, resampled by game."""
    if ev.static is None:
        h.metrics["mse"] = None
        return
    states = [s for r in labels for s in r["states"]]
    v = static_values(ev, states)
    sq, k = [], 0
    for r in labels:
        n = len(r["states"])
        sq.append(float(((v[k:k + n] - r["score"]) ** 2).sum()))
        k += n
    h.mean("mse", sq, [len(r["states"]) for r in labels])
    h.counts["states"] = len(states)


def strength(h, ev, specs):
    res = run_specs(specs, ev)
    h.rate("win", [r["won"] for r in res])
    h.mean("hp_lost", [r["hp_start"] - r["hp_end"] for r in res])
    h.counts["games"] = len(res)


def ranked_pairs(ref_values, ev_values):
    """(concordant, pairs) over option pairs with reference gap >= CONTESTED."""
    good = pairs = 0.0
    n = len(ref_values)
    for i in range(n):
        for j in range(i + 1, n):
            dr = ref_values[i] - ref_values[j]
            if abs(dr) < bench_decisions.CONTESTED or ev_values[i] is None or ev_values[j] is None:
                continue
            de = ev_values[i] - ev_values[j]
            pairs += 1
            good += 0.5 if de == 0 else float((de > 0) == (dr > 0))
    return good, pairs


def regret(row, pick):
    """Reference best value minus that of the option holding `pick` (an
    encoded action)."""
    i = next(i for i, acts in enumerate(row["options"]) if pick in acts)
    return max(row["values"]) - row["values"][i]


def in_subset(row, sub):
    return sub == "all" or (sub == "contested" and row["contested"]) or (sub == "uncapped" and not row["capped"])


def decision_halves(rows, picks, values, preds, targets):
    """{subset: Half} of regret, ranking and mse_search over reference rows,
    given per decision the evaluator's pick (an encoded action), its value
    per reference option (None where it has no such option), its best value
    (None: no mse_search) and the game's final score."""
    out = {}
    for sub in SUBSETS:
        keep = [i for i, r in enumerate(rows) if in_subset(r, sub)]
        h = Half()
        h.mean("regret", [regret(rows[i], picks[i]) for i in keep])
        rp = [ranked_pairs(rows[i]["values"], values[i]) for i in keep]
        h.mean("ranking", [g for g, _ in rp], [p for _, p in rp])
        if all(preds[i] is not None for i in keep):
            h.mean("mse_search", [(preds[i] - targets[i]) ** 2 for i in keep])
        h.counts["decisions"] = len(keep)
        out[sub] = h
    return out


def decision_metrics(rows, picks, values, preds, targets):
    """{subset: {name: [point, lo, hi]}} (see decision_halves)."""
    return {sub: h.metrics for sub, h in decision_halves(rows, picks, values, preds, targets).items()}


def search_decisions(ev, decisions, rows, search=None):
    """The evaluator's search at each decision: (pick, values aligned with
    the reference options, best value). `search` as in run_specs."""
    picks, values, best = [], [], []
    for d, r in zip(decisions, rows):
        s = sts.search(bench_decisions.replay(d), ev.evaluator, features=ev.features, **(search or {"limit": LIMIT}))
        opts = [(set(bench_decisions.encode_action(a) for a in acts), float(v)) for acts, v in s["options"]]
        # Ranking pairs reference options by their evaluator values; a
        # different grouping would score two reference options as one.
        if sorted(map(sorted, (a for a, _ in opts))) != sorted(map(sorted, r["options"])):
            raise ValueError(f"evaluator options group differently from the reference at decision {r['index']}")
        picks.append(bench_decisions.encode_action(s["action"]))
        values.append([next((v for acts, v in opts if acts & set(ro)), None) for ro in r["options"]])
        best.append(max(v for _, v in opts))
    return picks, values, best


def decision_quality(ev, decisions, reference, targets, halves=False):
    """{half: {subset: metrics}} (or {subset: Half} with `halves`) at the
    saved decisions. `targets`: {half: [final score per reference row]}
    (missing: no mse_search)."""
    out = {}
    for half, rows in reference["halves"].items():
        picks, values, best = search_decisions(ev, [decisions[half][r["index"]] for r in rows], rows)
        t = targets.get(half)
        none = [None] * len(rows)
        hs = decision_halves(rows, picks, values, best if t else none, t or none)
        out[half] = hs if halves else {sub: h.metrics for sub, h in hs.items()}
    return out


def load_puzzles(bench_dir=bench_sets.BENCH):
    with open(os.path.join(bench_dir, "puzzles.json"), encoding="utf-8") as f:
        return json.load(f)


def exact_pairs(exact, ev_values):
    """(concordant, pairs) over option pairs whose exact values differ."""
    good = pairs = 0.0
    for i in range(len(exact)):
        for j in range(i + 1, len(exact)):
            dx = exact[i] - exact[j]
            if abs(dx) <= EXACT:
                continue
            de = ev_values[i] - ev_values[j]
            pairs += 1
            good += 0.5 if de == 0 else float((de > 0) == (dx > 0))
    return good, pairs


def puzzle_half(rows, picks, values):
    """Half of accuracy, regret and ranking over puzzle rows (all /
    contested), and accuracy and regret per horizon, given per puzzle the
    index of the option the evaluator picks and its value per option."""
    exact = [[o[1] for o in r["options"]] for r in rows]
    best = [max(x) for x in exact]
    acc = [float(x[p] >= b - EXACT) for x, b, p in zip(exact, best, picks)]
    reg = [b - x[p] for x, b, p in zip(exact, best, picks)]
    rp = [exact_pairs(x, v) for x, v in zip(exact, values)]
    subsets = [("all", lambda r: True), ("contested", lambda r: r["gap"] >= PUZZLE_CONTESTED)]
    subsets += [(name, lambda r, lo=lo, hi=hi: lo <= r["horizon"] and (hi is None or r["horizon"] <= hi))
                for name, lo, hi in HORIZONS]
    h = Half()
    for sub, inside in subsets:
        keep = [i for i, r in enumerate(rows) if inside(r)]
        h.mean(f"accuracy.{sub}", [acc[i] for i in keep])
        h.mean(f"regret.{sub}", [reg[i] for i in keep])
        if sub in ("all", "contested"):
            h.mean(f"ranking.{sub}", [rp[i][0] for i in keep], [rp[i][1] for i in keep])
        h.counts[f"puzzles.{sub}"] = len(keep)
    return h


def search_puzzles(ev, rows, search=None):
    """The evaluator's search at each puzzle: (index of the option it picks,
    its value per puzzle option). `search` as in run_specs."""
    picks, values = [], []
    for r in rows:
        s = sts.search(bench_decisions.replay(r), ev.evaluator, features=ev.features, **(search or {"limit": LIMIT}))
        found = {frozenset(bench_decisions.encode_action(a) for a in acts): float(v) for acts, v in s["options"]}
        groups = [frozenset(o[0]) for o in r["options"]]
        if sorted(map(sorted, found)) != sorted(map(sorted, groups)):
            raise ValueError(f"search options group differently from the puzzle at spec {r['spec']}, step {r['step']}")
        pick = bench_decisions.encode_action(s["action"])
        picks.append(next(i for i, g in enumerate(groups) if pick in g))
        values.append([found[g] for g in groups])
    return picks, values


def puzzle_quality(ev, puzzles, n=None):
    """{half: Half} at the bench puzzles (every n-th)."""
    out = {}
    for half, rows in puzzles["halves"].items():
        rows = every(rows, n)
        out[half] = puzzle_half(rows, *search_puzzles(ev, rows))
    return out


def every(xs, n):
    return xs[::n] if n else xs


def bench(ev, quick=False):
    q = QUICK if quick else {}
    decisions = bench_decisions.load_decisions()
    reference = bench_decisions.load_reference()
    ref = {"halves": {h: every(rows, q.get("decisions")) for h, rows in reference["halves"].items()}}
    out = {}

    tight = bench_sets.load_set("tight")
    halves, targets = {}, {}
    for half, specs in tight.items():
        labels = run_specs(specs, record=True)
        targets[half] = [labels[decisions[half][r["index"]]["spec"]]["score"] for r in ref["halves"][half]]
        h = Half()
        prediction(h, ev, every(labels, q.get("tight")))
        strength(h, ev, every(specs, q.get("tight")))
        halves[half] = h
    for half, subs in decision_quality(ev, decisions, ref, targets, halves=True).items():
        for sub, sh in subs.items():
            for name, m in sh.metrics.items():
                halves[half].metrics[f"{name}.{sub}"] = m
                halves[half].samples[f"{name}.{sub}"] = sh.samples[name]
            halves[half].counts[f"decisions.{sub}"] = sh.counts["decisions"]
    out["tight"] = halves

    standard = bench_sets.load_set("standard")
    halves = {}
    for half, specs in standard.items():
        specs = every(specs, q.get("standard"))
        h = Half()
        prediction(h, ev, run_specs(specs, record=True))
        strength(h, ev, specs)
        halves[half] = h
    out["standard"] = halves

    puzzles = load_puzzles()
    out["puzzles"] = puzzle_quality(ev, puzzles, q.get("puzzles"))

    result = {"evaluator": ev.name, "version": bench_sets.VERSION, "quick": quick,
              "settings": {"limit": LIMIT, "turns": 1, "sample_k": 0, "boot": BOOT, "boot_seed": BOOT_SEED,
                           "contested": bench_decisions.CONTESTED, "reference": reference_settings(reference)},
              "sets": {}}
    for name, halves in out.items():
        base = halves["train"]
        result["sets"][name] = {
            "halves": {h: {"counts": dict(sorted(x.counts.items())), "metrics": dict(sorted(x.metrics.items()))}
                       for h, x in halves.items()},
            "gaps": {h: dict(sorted(gap(x, base).items())) for h, x in halves.items() if h != "train"},
        }
    result["sets"]["puzzles"]["settings"] = {
        "contested": PUZZLE_CONTESTED, "exact": EXACT,
        **{k: puzzles[k] for k in ("fingerprint", "max_nodes", "per_half", "seed", "seed_skip")}}
    result["representation"] = representation(ev, decisions, ref)
    return result


def representation(ev, decisions, ref):
    """Probe pass rate, and the aliasing audit on effects features (plus the
    evaluator's own features for a saved net)."""
    audits = {"effects": bench_probes.aliasing(sts.Features("effects"), decisions, ref, "effects")}
    if ev.name.endswith(".pt"):
        audits["own"] = bench_probes.aliasing(ev.features, decisions, ref, ev.features.card_repr)
    return {"probes": bench_probes.probe_results(ev), "aliasing": audits}


def reference_settings(reference):
    return {k: reference[k] for k in ("settings", "seeds", "max_nodes", "decisions_sha256")}


def write(path, result):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=1, sort_keys=True)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evaluator", required=True, help='"heuristic", a .pt model path, or module:callable')
    ap.add_argument("--out", required=True, help="results JSON path (e.g. results/<name>.json)")
    ap.add_argument("--quick", action="store_true", help="a small subset of every set (for tests)")
    args = ap.parse_args(argv)
    t = time.time()
    write(args.out, bench(load_evaluator(args.evaluator), args.quick))
    print(f"{args.evaluator}: wrote {args.out} in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main()
