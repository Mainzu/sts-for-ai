"""Rung 4 check (docs/specs/rung4-check.md): do play-out averages make
better labels than a single game's ending?

`precheck` measures, with no training, whether there is an error for rung 4
to fix. It draws POSITIONS valued rung-5 examples (labelled as
`round_check.py` labels s1 r10's window: the database copy, each dataset's
own frontier) from s1 r10's own games, PER_BAND per distance band, and
plays each on PLAYOUTS times (`sts.play_on`) with the net that played the
game and the game's own search settings. Per band and overall:

1. the ending minus the play-out mean (the ending is one more draw from
   the same play, so its interval must reach 0);
2. σ², the play-outs' variance per position: a single ending's noise;
3. err², the playing net's squared error against the play-out mean, less
   the mean's own noise (σ²_i / PLAYOUTS);
4. play-outs per second, and K: the largest K in 4..16 whose play-outs
   over every valued rung-5 example of the window fit BUDGET_S.

Item 1 per band misses 0 by design: the bands come from the game's
realized length, so a band's endings are conditioned on how the game went
on (a paused End turn one turn from the end mostly lost). Only the mix of
all bands is unconditioned, so item 1 is also given weighted by each
band's share of the dataset's valued rung-5 examples (`weighted_item1`),
which must reach 0.

Writes runs/rung4/precheck.json (and the raw numbers, precheck.npz) and
prints a markdown report.

`labels` plays every valued rung-5 example of the window on K times, each
dataset by its own player, and caches the play-out means
(`learn.rung4_path`; a config with `rung4` {"k": K} trains on them). It
saves after every CHUNK examples, and a rerun plays only what's missing.

`check` is the one-round check: s1 r10's round retrained twice against the
database copy, A with its own config and B with `rung4` {"k": K} (the
play-out caches), both left unfinished. It measures the tight fights (B
paired with A per cell, each against the heuristic), each net's err² on
the pre-check's positions, val MSE and rung counts, and passes when B - A
lies above 0 on held-out cards and isn't below 0 on train cards. Rerunning
skips what check.json already holds. Writes runs/rung4/check.json and
prints a markdown report.

`check --seeds [S ...]` (Amendment 1) trains A and B once per training seed
(default SEEDS; the first is the night's) and keeps each seed's results,
with every arm's per-fight tight results, under `seeds` in check.json.
A single-seed check.json already in `--out` at the night's seed counts as
that seed's run (its nets are reused, its fights replayed: they are
deterministic). Over seeds: each fight's B - A averaged across seeds, then
per cell with the interval over cells; the spread of the per-seed B - A and
of A's lead. Passes when every seed's held-out B - A is above 0, the
averaged held-out interval lies above 0 and the averaged train interval
reaches 0 or above.

    python scripts/rung4.py precheck [--db db/bounds-check.sqlite] [--out runs/rung4]
    python scripts/rung4.py labels [--k 12] [--db db/bounds-check.sqlite]
    python scripts/rung4.py check [--k 12] [--db db/bounds-check.sqlite] [--out runs/rung4] [--seeds [S ...]]
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bench  # noqa: E402
import exact_only  # noqa: E402
import learn  # noqa: E402
import registry  # noqa: E402
import round_check  # noqa: E402
import sts  # noqa: E402

POSITIONS = 2000
BANDS = ("1", "2", "3", "4-5", "6+")
PER_BAND = POSITIONS // len(BANDS)
PLAYOUTS = 16
POS_SEED = 41  # the pre-check's positions sample
# Play-out chance seeds: their own range, past tight fights v2's test seeds
# (2 x 10^15 + ...): PLAYOUT_SEED + dataset slot x SLOT + example x
# MAX_PLAYOUTS + play-out, so example i's first K play-outs have the same
# seeds whatever K a run uses.
PLAYOUT_SEED = 3 * 10**15
SLOT = 10**10
MAX_PLAYOUTS = 16
K_RANGE = (4, 16)
BUDGET_S = 3600.0  # the window's play-outs (owner, 2026-10-29)
THREADS = 8
K = 12  # the pre-check's pick at 1 hour (runs/rung4/precheck.json, 2026-10-29)
CHUNK = 2000  # examples played between saves
SEEDS = (1, 101, 201)  # training seeds of `check --seeds` (Amendment 1); the first is the night's


def band(distance):
    """The distance band of an example (turns from the game's last decision
    turn; 0 and 1 share the first band)."""
    d = int(distance)
    return "1" if d <= 1 else "2" if d == 2 else "3" if d == 3 else "4-5" if d <= 5 else "6+"


def playout_seeds(slot, idx, k):
    """[len(idx), k] chance seeds of examples `idx` of the window's dataset
    `slot`."""
    idx = np.asarray(idx, np.int64)
    return PLAYOUT_SEED + slot * SLOT + idx[:, None] * MAX_PLAYOUTS + np.arange(k, dtype=np.int64)[None, :]


def playout_stats(endings, values, scores):
    """The pre-check's items 1-3 over positions: `endings` the game's real
    endings, `values` the net's direct values, `scores` [positions, K]
    play-out scores. Each a [mean, lo, hi] bootstrap (exact_only.boot)."""
    scores = np.asarray(scores, float)
    k = scores.shape[1]
    m = scores.mean(axis=1)
    var = scores.var(axis=1, ddof=1)
    return {"n": len(m),
            "ending_minus_playout": exact_only.boot(np.asarray(endings, float) - m),
            "sigma2": exact_only.boot(var),
            "err2": exact_only.boot((np.asarray(values, float) - m) ** 2 - var / k)}


def weighted_item1(diff, sample_bands, pop_bands, seed=exact_only.SEED):
    """[mean, lo, hi] of item 1 (`diff`: ending - play-out mean per sampled
    position, `sample_bands` their bands) with each band weighted by its
    share of `pop_bands` (the bands of every valued rung-5 example), a 95%
    bootstrap resampling within bands."""
    diff, sample_bands, pop_bands = np.asarray(diff, float), np.asarray(sample_bands), np.asarray(pop_bands)
    share = {b: float((pop_bands == b).mean()) for b in BANDS}
    cells = {b: np.flatnonzero(sample_bands == b) for b in BANDS if share[b] > 0}

    def mean(ix):
        return sum(share[b] * diff[i].mean() for b, i in ix.items())
    rng = np.random.default_rng(seed)
    boot = [mean({b: rng.choice(i, len(i)) for b, i in cells.items()}) for _ in range(exact_only.BOOT)]
    return [float(mean(cells)), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def pick_k(n_examples, rate, budget_s=BUDGET_S, k_range=K_RANGE):
    """The largest K in `k_range` whose `n_examples` x K play-outs at `rate`
    per second fit `budget_s`, else None."""
    fits = [k for k in range(k_range[0], k_range[1] + 1) if n_examples * k / rate <= budget_s]
    return max(fits) if fits else None


def window(cfg):
    """[(dataset id, its round, its labelled examples with codec bytes)]
    of s1 r10's window, labelled as training labels it (`learn.ladder`
    with the database copy and each dataset's frontier)."""
    db = learn.open_db(cfg)
    exact = learn.db_lookup(db) if db is not None else None
    out = []
    for ds, rnd in round_check.PARTS:
        d = registry.examples(ds, learn.feature_mode(cfg), labels=learn.labels(cfg, rnd))
        d = learn.ladder(d, cfg, rnd, exact, learn.dataset_frontier(ds))
        out.append((ds, rnd, d))
    return out


def rung5(d):
    """Indices of a labelled dataset's valued rung-5 examples."""
    return np.flatnonzero((d.rung == 5) & (d.weight > 0))


def player(ds):
    """(model path, search settings) of the net that played dataset `ds`;
    stops when the manifest names neither."""
    m = registry.load_manifest(ds)
    if not m.get("parent_model") or "search" not in m.get("config", {}):
        raise SystemExit(f"dataset {ds}: its manifest names no playing net (parent_model) or search settings")
    return registry.Run(os.path.join(registry.runs_dir(), m["parent_model"])).model_path, dict(m["config"]["search"])


def playouts(d, idx, slot, k, model, search, threads=THREADS):
    """[len(idx), k] play-out scores of examples `idx` of labelled dataset
    `d` (window slot `slot`), played on by `model` with `search`."""
    ev = bench.load_evaluator(model)
    seeds = playout_seeds(slot, idx, k)
    combats = [sts.Combat.decode(d.codec_bytes(int(i)), seed=int(s)) for i, row in zip(idx, seeds) for s in row]
    res = sts.play_on(combats, evaluator=ev.evaluator, features=ev.features, threads=threads, **search)
    return np.array([r["score"] for r in res], float).reshape(len(idx), k)


def precheck(args):
    t0 = time.perf_counter()
    db_file = os.path.abspath(args.db)
    learn.db_path = lambda root=registry.ROOT: db_file  # the check's database copy, as round_check
    cfg = json.load(open(os.path.join(round_check.NIGHT, "config.json")))
    parts = window(cfg)
    n_window = sum(len(rung5(d)) for _, _, d in parts)
    slot = 0  # s1 r10's own games
    ds, _, d = parts[slot]
    model, search = player(ds)
    for other, _, _ in parts[1:]:
        player(other)  # every dataset of the window must name its player
    cand = rung5(d)
    bands = np.array([band(x) for x in d.distance[cand]])
    rng = np.random.default_rng(POS_SEED)
    idx = np.sort(np.concatenate([rng.choice(cand[bands == b], min(PER_BAND, int((bands == b).sum())), replace=False)
                                  for b in BANDS]))
    t = time.perf_counter()
    scores = playouts(d, idx, slot, PLAYOUTS, model, search)
    play_s = time.perf_counter() - t
    rate = scores.size / play_s
    ev = bench.load_evaluator(model)
    values = bench.static_values(ev, [sts.Combat.decode(d.codec_bytes(int(i))) for i in idx])
    endings = d.outcome[idx].astype(float)
    pb = np.array([band(x) for x in d.distance[idx]])
    kinds = {0: "decision", **{v: k for k, v in type(d).KINDS.items()}}
    pk = np.array([kinds[int(x)] for x in d.kind[idx]])
    res = {"dataset": ds, "player": model, "search": search, "positions": len(idx), "playouts": PLAYOUTS,
           "overall": playout_stats(endings, values, scores),
           "ending_minus_playout_weighted": weighted_item1(endings - scores.mean(axis=1), pb, bands),
           "bands": {b: playout_stats(endings[pb == b], values[pb == b], scores[pb == b]) for b in BANDS if (pb == b).any()},
           "kinds": {k: playout_stats(endings[pk == k], values[pk == k], scores[pk == k]) for k in kinds.values()
                     if (pk == k).any()},
           "playout_seconds": play_s, "playouts_per_s": rate, "window_rung5": n_window,
           "k": pick_k(n_window, rate), "budget_s": BUDGET_S, "threads": THREADS}
    res["minutes"] = (time.perf_counter() - t0) / 60
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "precheck.json"), "w") as f:
        json.dump(res, f, indent=1)
    np.savez(os.path.join(args.out, "precheck.npz"), idx=idx, endings=endings, values=values, scores=scores)
    print(report(res))


def report(res):
    """The pre-check as markdown."""
    def f(b):
        return f"{b[0]:+.4f} [{b[1]:+.4f}, {b[2]:+.4f}]"
    out = [f"{res['positions']} positions of {res['dataset']}, {res['playouts']} play-outs each by {res['player']}",
           "", "| | n | ending - play-out mean | σ² | err² |", "|---|---|---|---|---|"]
    rows = [("overall", res["overall"])] + [(f"band {b}", s) for b, s in res["bands"].items()] + [
        (k, s) for k, s in res["kinds"].items()]
    for name, s in rows:
        out.append(f"| {name} | {s['n']} | {f(s['ending_minus_playout'])} | {f(s['sigma2'])} | {f(s['err2'])} |")
    if "ending_minus_playout_weighted" in res:
        out += ["", "ending - play-out mean, bands weighted by their share of the dataset: "
                    + f(res["ending_minus_playout_weighted"])]
    out += ["", f"{res['playouts_per_s']:.0f} play-outs/s on {res['threads']} threads "
                f"({res['playout_seconds']:.0f} s); the window's valued rung-5 examples: {res['window_rung5']}; "
                f"K = {res['k']} in {res['budget_s'] / 3600:.0f} h; total {res['minutes']:.1f} min"]
    return "\n".join(out)


def save_playouts(path, idx, mean, k, n):
    """Writes a play-out cache (learn.rung4_playouts' format): `idx`
    example indices (sorted here), `mean` their play-out means, `k`, `n`
    the dataset's example count; replaced whole, never half written."""
    idx = np.asarray(idx, np.int64)
    order = np.argsort(idx)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp.npz"
    np.savez(tmp, idx=idx[order], mean=np.asarray(mean, np.float64)[order], k=k, n=n)
    os.replace(tmp, path)


def fill(parts, k, limit=None, log=print):
    """Play-out caches at K = `k` for `parts` [(dataset id, round, labelled
    dataset)] (`window`), each dataset by its own player, its slot's seeds
    (`playout_seeds`); keeps what a cache already holds and plays the rest,
    saving every CHUNK examples. `limit`: only each dataset's first
    `limit` valued rung-5 examples (tests)."""
    for slot, (ds, _, d) in enumerate(parts):
        model, search = player(ds)
        want = rung5(d)[:limit]
        path = learn.rung4_path(ds, k)
        if os.path.exists(path):
            idx, mean, k0, n = learn.rung4_playouts(ds, k)
            if (k0, n) != (k, len(d)):
                raise SystemExit(f"{path}: a cache for k {k0} over {n} examples, not k {k} over {len(d)}")
        else:
            idx, mean = np.zeros(0, np.int64), np.zeros(0)
        todo = np.setdiff1d(want, idx)
        log(f"{ds}: {len(want)} rung-5 examples, {len(want) - len(todo)} cached, {len(todo)} to play x {k}")
        t = time.perf_counter()
        for j in range(0, len(todo), CHUNK):
            part = todo[j:j + CHUNK]
            idx = np.append(idx, part)
            mean = np.append(mean, playouts(d, part, slot, k, model, search).mean(axis=1))
            save_playouts(path, idx, mean, k, len(d))
            done = j + len(part)
            rate = done * k / (time.perf_counter() - t)
            log(f"  {ds}: {done}/{len(todo)} examples, {rate:.0f} play-outs/s, "
                f"ETA {(len(todo) - done) * k / rate / 60:.0f} min")


def labels_cmd(args):
    t0 = time.perf_counter()
    db_file = os.path.abspath(args.db)
    learn.db_path = lambda root=registry.ROOT: db_file  # the same labelling as the pre-check and the check
    cfg = json.load(open(os.path.join(round_check.NIGHT, "config.json")))
    fill(window(cfg), args.k, log=lambda m: print(m, flush=True))
    print(f"done in {(time.perf_counter() - t0) / 60:.0f} min")


def verdict(b_vs_a):
    """The check's verdict from `learn.gate(B, A, cells)`: B - A's interval
    above 0 on held-out cards, its upper end at 0 or above on train."""
    h = b_vs_a["halves"]
    v = {"better_held_out": h["held_out"]["lead"][1] > 0, "train_not_worse": h["train"]["lead"][2] >= 0}
    v["passes"] = all(v.values())
    return v


def seeds_average(b, a, cells):
    """{half: [mean, lo, hi]}: each fight's B - A averaged over seeds (lists
    of per-seed `tight_results`), then per cell with the interval over
    cells (`learn.cell_interval`)."""
    return {h: learn.cell_interval(np.mean([np.array(bs[h], float) - np.array(as_[h], float)
                                            for bs, as_ in zip(b, a)], axis=0), cells[h]) for h in cells}


def seeds_verdict(per_seed, avg):
    """Amendment 1's verdict from each seed's B - A {half: [mean, lo, hi]}
    and the seed-averaged one (`seeds_average`): every seed's held-out
    point above 0, the averaged held-out interval above 0, the averaged
    train interval's upper end at 0 or above."""
    v = {"every_seed_better": all(p["held_out"][0] > 0 for p in per_seed.values()),
         "better_held_out": avg["held_out"][1] > 0, "train_not_worse": avg["train"][2] >= 0}
    v["passes"] = all(v.values())
    return v


def fit_arm(cfg, arm, k, seed=None):
    """Retrains s1 r10's round as arm A (its own config) or B (plus `rung4`
    {"k": k}), with training seed `seed` (default the night's), left
    unfinished."""
    extra = {"rung4": {"k": k}} if arm == "B" else {}
    name = f"rung4-check-{arm}" + (f"-k{k}" if extra else "") + ("" if seed is None else f"-s{seed}")
    c = {**cfg, **extra, "name": name}
    t = time.perf_counter()
    run, val_mse, _, counts = learn.fit(c, name, round_check.PARTS, round_check.VAL, finish=False,
                                        seed=cfg["seed"] if seed is None else seed)
    return {"model": run.model_path, "val_mse": val_mse, "rungs": counts, "train_min": (time.perf_counter() - t) / 60}


def err2(model, combats, scores):
    """[mean, lo, hi] of a net's err² at the pre-check's positions
    (`combats`, their play-out `scores`), as the pre-check's item 3."""
    values = bench.static_values(bench.load_evaluator(model), combats)
    return playout_stats(np.zeros(len(scores)), values, scores)["err2"]


def check(args):
    t0 = time.perf_counter()
    os.makedirs(args.out, exist_ok=True)
    res_path = os.path.join(args.out, "check.json")
    res = json.load(open(res_path)) if os.path.exists(res_path) else {}
    if res.get("k", args.k) != args.k:
        raise SystemExit(f"{res_path} holds a check at k {res['k']}, not {args.k}")
    res["k"] = args.k

    def save():
        with open(res_path, "w") as f:
            json.dump(res, f, indent=1)

    db_file = os.path.abspath(args.db)
    learn.db_path = lambda root=registry.ROOT: db_file  # the same labelling as the pre-check and the caches
    cfg = json.load(open(os.path.join(round_check.NIGHT, "config.json")))
    for ds, _ in round_check.PARTS:
        learn.rung4_playouts(ds, args.k)  # both caches must exist before any training
    arms = res.setdefault("arms", {})
    for arm in ("A", "B"):
        if arm not in arms:
            arms[arm] = fit_arm(cfg, arm, args.k)
            save()

    if "err2" not in res:
        z = np.load(os.path.join(args.out, "precheck.npz"))
        _, _, d = window(cfg)[0]  # the pre-check's positions are s1 r10's own games
        combats = [sts.Combat.decode(d.codec_bytes(int(i))) for i in z["idx"]]
        res["err2"] = {arm: err2(a["model"], combats, z["scores"]) for arm, a in arms.items()}
        save()

    if "tight" not in res:
        agent = {"limit": bench.LIMIT}
        heur = learn.tight_results("heuristic", agent, 1)
        nets = {arm: learn.tight_results(a["model"], agent, 1) for arm, a in arms.items()}
        cells = learn.tight_cells(1)
        res["tight"] = {arm: learn.gate(r, heur, cells) for arm, r in nets.items()}
        res["tight"]["B_vs_A"] = learn.gate(nets["B"], nets["A"], cells)
        save()

    res["verdict"] = verdict(res["tight"]["B_vs_A"])
    res["minutes"] = res.get("minutes", 0) + (time.perf_counter() - t0) / 60
    save()
    print(check_report(res))


def check_seeds(args, seeds):
    """`check --seeds`: the one-round check once per training seed, and
    the summary over seeds (Amendment 1)."""
    t0 = time.perf_counter()
    os.makedirs(args.out, exist_ok=True)
    res_path = os.path.join(args.out, "check.json")
    res = json.load(open(res_path)) if os.path.exists(res_path) else {}
    if res.get("k", args.k) != args.k:
        raise SystemExit(f"{res_path} holds a check at k {res['k']}, not {args.k}")
    res["k"] = args.k

    def save():
        with open(res_path, "w") as f:
            json.dump(res, f, indent=1)

    def enc(results):
        return {h: "".join(map(str, x)) for h, x in results.items()}

    def dec(fights):
        return {h: [int(c) for c in x] for h, x in fights.items()}

    db_file = os.path.abspath(args.db)
    learn.db_path = lambda root=registry.ROOT: db_file
    cfg = json.load(open(os.path.join(round_check.NIGHT, "config.json")))
    for ds, _ in round_check.PARTS:
        learn.rung4_playouts(ds, args.k)
    runs = res.setdefault("seeds", {})
    if str(seeds[0]) not in runs and "arms" in res and seeds[0] == cfg["seed"]:
        # a single-seed check at the night's seed is that seed's run: its nets are reused
        runs[str(seeds[0])] = {key: res[key] for key in ("arms", "err2", "tight") if key in res}
        save()
    agent = {"limit": bench.LIMIT}
    cells = learn.tight_cells(1)
    if "heuristic_fights" not in res:
        res["heuristic_fights"] = enc(learn.tight_results("heuristic", agent, 1))
        save()
    heur = dec(res["heuristic_fights"])
    pos = []

    def positions():
        if not pos:
            z = np.load(os.path.join(args.out, "precheck.npz"))
            _, _, d = window(cfg)[0]
            pos.extend([[sts.Combat.decode(d.codec_bytes(int(i))) for i in z["idx"]], z["scores"]])
        return pos

    for s in seeds:
        r = runs.setdefault(str(s), {})
        arms = r.setdefault("arms", {})
        for arm in ("A", "B"):
            if arm not in arms:
                arms[arm] = fit_arm(cfg, arm, args.k, s)
                save()
        if "err2" not in r:
            r["err2"] = {arm: err2(a["model"], *positions()) for arm, a in arms.items()}
            save()
        fights = r.setdefault("fights", {})
        for arm, a in arms.items():
            if arm not in fights:
                fights[arm] = enc(learn.tight_results(a["model"], agent, 1))
                save()
        if "tight" not in r:
            nets = {arm: dec(f) for arm, f in fights.items()}
            r["tight"] = {arm: learn.gate(x, heur, cells) for arm, x in nets.items()}
            r["tight"]["B_vs_A"] = learn.gate(nets["B"], nets["A"], cells)
            save()

    per = {s: {h: v["lead"] for h, v in runs[str(s)]["tight"]["B_vs_A"]["halves"].items()} for s in seeds}
    avg = seeds_average([dec(runs[str(s)]["fights"]["B"]) for s in seeds],
                        [dec(runs[str(s)]["fights"]["A"]) for s in seeds], cells)

    def spread(x):
        return float(np.std(x, ddof=1)) if len(x) > 1 else 0.0
    res["over_seeds"] = {
        "seeds": list(seeds), "B_vs_A": avg,
        "spread_B_vs_A": {h: spread([per[s][h][0] for s in seeds]) for h in cells},
        "spread_A": {h: spread([runs[str(s)]["tight"]["A"]["halves"][h]["lead"][0] for s in seeds]) for h in cells},
        "verdict": seeds_verdict(per, avg)}
    res["minutes"] = res.get("minutes", 0) + (time.perf_counter() - t0) / 60
    save()
    print(seeds_report(res))


def seeds_report(res):
    """`check --seeds` as markdown: a row per seed, then the summary over
    seeds and the verdict."""
    def f(b):
        return f"{b[0]:+.4f} [{b[1]:+.4f}, {b[2]:+.4f}]"

    def lead(r, arm, h):
        return f"{r['tight'][arm]['halves'][h]['lead'][0]:+.4f}"
    o = res["over_seeds"]
    out = [f"One-round check over training seeds, rung 4 at K = {res['k']}", "",
           "| seed | val MSE A / B | training A / B | err² A / B | lead A train / held-out | "
           "lead B train / held-out | B - A train | B - A held-out |", "|---|---|---|---|---|---|---|---|"]
    for s, r in res["seeds"].items():
        a, b = r["arms"]["A"], r["arms"]["B"]
        ba = r["tight"]["B_vs_A"]["halves"]
        out.append(f"| {s} | {a['val_mse']:.4f} / {b['val_mse']:.4f} | {a['train_min']:.0f} / {b['train_min']:.0f} min | "
                   f"{r['err2']['A'][0]:.4f} / {r['err2']['B'][0]:.4f} | {lead(r, 'A', 'train')} / {lead(r, 'A', 'held_out')} | "
                   f"{lead(r, 'B', 'train')} / {lead(r, 'B', 'held_out')} | {f(ba['train']['lead'])} | {f(ba['held_out']['lead'])} |")
    v = o["verdict"]
    out += ["", f"B - A averaged over seeds, per cell: train {f(o['B_vs_A']['train'])}, held-out {f(o['B_vs_A']['held_out'])}",
            f"spread over seeds (sd): B - A train {o['spread_B_vs_A']['train']:.4f}, held-out "
            f"{o['spread_B_vs_A']['held_out']:.4f}; A's lead train {o['spread_A']['train']:.4f}, held-out "
            f"{o['spread_A']['held_out']:.4f}",
            f"verdict: {'passes' if v['passes'] else 'fails'} (every seed better on held-out: {v['every_seed_better']}, "
            f"averaged better on held-out: {v['better_held_out']}, train not worse: {v['train_not_worse']}); "
            f"{res['minutes']:.0f} min"]
    return "\n".join(out)


def check_report(res):
    """The one-round check as markdown."""
    def f(b):
        return f"{b[0]:+.4f} [{b[1]:+.4f}, {b[2]:+.4f}]"
    out = [f"One-round check, rung 4 at K = {res['k']}", "",
           "| arm | val MSE | training | err² (pre-check positions) | lead train | lead held-out | rungs |",
           "|---|---|---|---|---|---|---|"]
    for arm, a in res["arms"].items():
        lead = res["tight"][arm]["halves"]
        out.append(f"| {arm} | {a['val_mse']:.4f} | {a['train_min']:.0f} min | {f(res['err2'][arm])} | "
                   f"{f(lead['train']['lead'])} | {f(lead['held_out']['lead'])} | {a['rungs']} |")
    ba = res["tight"]["B_vs_A"]["halves"]
    v = res["verdict"]
    out += ["", f"B - A, paired per cell: train {f(ba['train']['lead'])}, held-out {f(ba['held_out']['lead'])}",
            f"verdict: {'passes' if v['passes'] else 'fails'} (better on held-out: {v['better_held_out']}, "
            f"train not worse: {v['train_not_worse']}); {res['minutes']:.0f} min"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("precheck", help="the pre-check (no training)")
    p.add_argument("--db", default="db/bounds-check.sqlite", help="a copy of db/bounds.sqlite (read only here)")
    p.add_argument("--out", default="runs/rung4")
    p = sub.add_parser("labels", help="the window's play-out caches")
    p.add_argument("--k", type=int, default=K)
    p.add_argument("--db", default="db/bounds-check.sqlite", help="a copy of db/bounds.sqlite (read only here)")
    p = sub.add_parser("check", help="the one-round check: A (endings) and B (rung 4) retrained and compared")
    p.add_argument("--k", type=int, default=K)
    p.add_argument("--db", default="db/bounds-check.sqlite", help="a copy of db/bounds.sqlite (read only here)")
    p.add_argument("--out", default="runs/rung4")
    p.add_argument("--seeds", type=int, nargs="*",
                   help=f"training seeds, one A and B each (no values: {' '.join(map(str, SEEDS))})")
    args = ap.parse_args(argv)
    if args.cmd == "precheck":
        precheck(args)
    elif args.cmd == "labels":
        labels_cmd(args)
    elif args.cmd == "check" and args.seeds is not None:
        check_seeds(args, args.seeds or list(SEEDS))
    elif args.cmd == "check":
        check(args)


if __name__ == "__main__":
    main()
