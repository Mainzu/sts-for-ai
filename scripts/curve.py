"""Learning-curve bench of the warm-start workflow (docs/specs/warm-start.md):
how much Silent play a net needs to learn the Silent, for three starting
points on a ladder of new-game counts.

Starting points: warm effects (models/value_effects.pt fine-tuned with
`finetune.finetune`), warm ids (models/value_ids.pt, the same) and fresh
effects (a new effects net on the new games only). Size 0: the parents
unchanged (no widening: a widened ids net moves Silent cards out of
`id_unknown`), and the random floor (`bench.random_evaluator`) for fresh.
Sizes above 0 are nested (the first k games per group of one stored
dataset) and trained with each of the training seeds; size 0 has one cell
per start (seed null).

Metrics per cell: Silent value MSE on fresh test games of each tier
(states sampled as selfplay.generate does, each net in its own layout;
bootstrap over games), win rate and HP lost on `tight_silent` per half
(one-turn search, bench's settings, Rust evaluator; Wilson), and
forgetting: Ironclad MSE on selfplay's test_a specs and win rate on
`tight2`'s train half, every 4th cell.

Gate (the thesis): at every size above 0 and on both tiers, warm effects'
seed-mean Silent MSE minus warm ids' and minus fresh effects' has a paired
bootstrap interval (over test games) wholly below 0; and at size 0 warm
effects' tight_silent lead over the random floor (paired by spec) has its
interval above 0 on both halves. A difference smaller than twice the sd
over seeds of the per-seed differences is flagged "within training luck".
Win rates above size 0 are reported, not gated. Exit 1 when the gate fails.

Resumable: a cell's registry run is reused when one exists with the same
config, parent sha256 and rules version, and its metrics are cached in
`<out dir>/cells/`. `--starts` runs a subset (two processes on disjoint
starts); a run with every start reads the others' cells and writes the gate.

    python scripts/curve.py [--sizes 0,500,2000,10000] [--seeds 0,1,2] [--starts warm_effects,warm_ids]
    python scripts/curve.py --quick --out <dir>     # tiny ladder, for tests
"""

import argparse
import hashlib
import json
import os
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")  # before torch; see stsnet.py
os.environ.setdefault("MKL_DISABLE_FAST_MM", "1")

import numpy as np
import torch

import bench
import bench_sets
import finetune
import registry
import selfplay
import sts
import stsnet

ROOT = registry.ROOT
MODELS = os.path.join(ROOT, "models")
PARENTS = {"warm_effects": os.path.join(MODELS, "value_effects.pt"),
           "warm_ids": os.path.join(MODELS, "value_ids.pt"), "fresh_effects": None}
STARTS = tuple(PARENTS)
TIERS = ("silent_a", "silent_b")
GAME_SEED = 500  # new content's training games (validation: GAME_SEED + finetune.VAL_OFFSET)
TEST_SEEDS = {"silent_a": 600, "silent_b": 700, "ironclad": 3}  # ironclad: selfplay's test_a seed
DEFAULTS = {"sizes": [0, 500, 2000, 10000], "seeds": [0, 1, 2], "test_games": 1000, "tight_every": 1,
            "tight2_every": 4, "share": 0.5, "lr": None, "epochs": None, "n_val": 300, "pool": 10_000}
QUICK = {"sizes": [0, 10], "seeds": [0], "test_games": 5, "tight_every": 50, "tight2_every": 400, "epochs": 1,
         "n_val": 5, "pool": 10}
COMPARE = (("warm_effects", "warm_ids"), ("warm_effects", "fresh_effects"))
OUT = os.path.join(ROOT, "results", "warm-start")
EVAL_VERSION = 1  # bump when a cell's metrics change meaning


# --- test sets ---------------------------------------------------------------

def test_set(kind, n, meta, root=ROOT, log=print, threads=None):
    """(dataset, game index per state) of `n` test games per group of
    `kind` (a finetune.DECKS key or "ironclad"), states sampled as
    selfplay.generate does, encoded in `meta`'s layout; cached."""
    ds = finetune.games(kind, n, TEST_SEEDS[kind], threads, log, root)
    key = hashlib.sha256(json.dumps([ds, n, meta["card_repr"], stsnet.layout_of(meta)], sort_keys=True)
                         .encode()).hexdigest()[:16]
    path = os.path.join(registry.cache_dir(root), f"curve-{ds}-{key}.npz")
    if os.path.exists(path):
        return stsnet.Dataset.load(path), np.load(path + ".games.npy")
    feats = stsnet.features_for(meta)
    rng = np.random.default_rng(registry.load_manifest(ds, root)["config"]["seed"] + finetune.SAMPLE_OFFSET)
    parts, targets, grps, game_of, it, j = [], [], [], [], finetune.first_per_group(ds, n, root), 0
    while chunk := [g for _, g in zip(range(registry.CHUNK), it)]:
        states = []
        for g in chunk:
            s, tg, gr = selfplay.sample_states([registry.replay(g)], [g["group"]], rng)
            states += s
            targets += tg
            grps += gr
            game_of += [j] * len(s)
            j += 1
        parts.append(feats.encode(states))
    out = stsnet.Dataset.from_batches(parts, targets, grps)
    os.makedirs(registry.cache_dir(root), exist_ok=True)
    out.save(path)
    np.save(path + ".games.npy", np.asarray(game_of, np.int64))
    return stsnet.Dataset.load(path), np.asarray(game_of, np.int64)


def tight_specs(settings, bench_dir=bench_sets.BENCH):
    """{half: specs} of tight_silent, every `tight_every`-th spec; without the
    file (before its calibration ran), a stand-in: the standard set's
    Silent halves under the same names."""
    path = os.path.join(bench_dir, "tight_silent.json")
    halves = bench_sets.load_set("tight_silent" if os.path.exists(path) else "standard", bench_dir)
    k = settings["tight_every"]
    return {h: halves[h][::k] for h in TIERS}, os.path.exists(path)


def tight2_specs(settings, bench_dir=bench_sets.BENCH):
    """tight2's train half, the specs of every `tight2_every`-th cell."""
    k = settings["tight2_every"]
    return [s for s in bench_sets.load_set("tight2", bench_dir)["train"] if s["cell"] % k == 0]


# --- nets --------------------------------------------------------------------

class Net:
    """A cell's evaluator: a saved net or the random floor."""

    def __init__(self, path=None):
        self.path = path
        if path is None:
            self.meta = {"card_repr": "effects", **selfplay.meta_vocab("effects")}
            self.model = self.norm = None
        else:
            self.model, self.norm, self.meta = stsnet.load(path)

    def predict(self, ds, chunk=4096):
        out = []
        for i in range(0, len(ds), chunk):
            b = ds.batch(np.arange(i, min(i + chunk, len(ds))))
            if self.model is None:
                out.append(bench.random_evaluator(b))
            else:
                with torch.no_grad():
                    out.append(stsnet.score_of(self.model, self.norm.tensors(b)).numpy())
        return np.concatenate(out).astype(np.float64) if out else np.zeros(0)

    def bench_evaluator(self):
        if self.model is None:
            return bench.Evaluator("random", bench.random_evaluator, stsnet.features_for(self.meta), None)
        return bench.Evaluator(self.path, stsnet.rust_evaluator(self.model, self.norm, self.meta),
                               stsnet.features_for(self.meta), None)


def mse_parts(net, kind, n, root, log, threads):
    """Per test game: (sum of squared errors, states)."""
    ds, game = test_set(kind, n, net.meta, root, log, threads)
    err = (net.predict(ds) - ds.target.astype(np.float64)) ** 2
    n_games = int(game.max()) + 1 if len(game) else 0
    return np.bincount(game, err, n_games).tolist(), np.bincount(game, None, n_games).tolist()


def play(net, specs, threads):
    res = bench.run_specs(specs, net.bench_evaluator(), search={"limit": bench.LIMIT, "threads": threads})
    return ([int(r["won"]) for r in res], [int(r["hp_start"] - r["hp_end"]) for r in res],
            [int(r["turns"] > bench.PLAY_TURN_LIMIT) for r in res])


def evaluate(net, settings, root, log, threads):
    """A cell's metrics, with what the comparisons need (per-game error
    sums, per-spec wins)."""
    t = time.perf_counter()
    n = settings["test_games"]
    out = {"mse": {k: dict(zip(("num", "den"), mse_parts(net, k, n, root, log, threads)))
                   for k in TIERS + ("ironclad",)}}
    specs, real = tight_specs(settings)
    out["tight"] = {h: dict(zip(("won", "lost", "stalled"), play(net, s, threads))) for h, s in specs.items()}
    out["tight_real"] = real
    out["tight2_train"] = dict(zip(("won", "lost", "stalled"), play(net, tight2_specs(settings), threads)))
    out["eval_seconds"] = round(time.perf_counter() - t, 1)
    return out


# --- cells -------------------------------------------------------------------

def cell_config(start, size, seed, settings):
    cfg = {"name": f"curve-{start}-{size}-s{seed}", "content": "both", "games": size,
           "top": max(settings["sizes"]), "game_seed": GAME_SEED, "seed": seed,
           "start": "fresh" if start == "fresh_effects" else "warm", "share": settings["share"],
           "n_val": settings["n_val"], "pool": settings["pool"]}
    for k in ("lr", "epochs"):
        if settings[k] is not None:
            cfg[k] = settings[k]
    return cfg


def cell_settings(start, size, seed, settings):
    """What a cell's metrics depend on besides its net: the evaluation
    settings and its training config (None at size 0). Stored in the cell;
    `_cached` reuses another process's cell only when they match."""
    return {"eval": [EVAL_VERSION, {k: settings[k] for k in ("test_games", "tight_every", "tight2_every")},
                     tight_specs(settings)[1], registry.rules_version()],
            "train": None if size == 0 else cell_config(start, size, seed, settings)}


def find_run(cfg, parent_sha, root=ROOT):
    """A finished registry run with this config, parent and rules version."""
    d = registry.runs_dir(root)
    if not os.path.isdir(d):
        return None
    rules = registry.rules_version()
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        try:
            with open(os.path.join(p, "config.json"), encoding="utf-8") as f:
                c = json.load(f)
            with open(os.path.join(p, "run.json"), encoding="utf-8") as f:
                info = json.load(f)
        except (OSError, ValueError):
            continue
        if (c == cfg and info.get("rules_version") == rules and (info.get("parent") or {}).get("sha256") == parent_sha
                and os.path.exists(os.path.join(p, "model.pt"))):
            return registry.Run(p)
    return None


def cells(settings, starts):
    """Every (start, size, seed) of the ladder; size 0 has seed None."""
    return [(s, z, None if z == 0 else k) for s in starts for z in settings["sizes"]
            for k in ([None] if z == 0 else settings["seeds"])]


def cell_key(start, size, seed):
    return f"{start}-{size}-s{seed}"


def run_cell(start, size, seed, settings, root, out_dir, log, threads):
    """The cell's metrics, from its cache or by training (or reusing its
    run) and evaluating."""
    parent = PARENTS[start]
    sha = finetune.sha256(parent) if parent else None
    t = time.perf_counter()
    run_id, train_s = None, 0.0
    if size == 0:
        path = parent
    else:
        cfg = cell_config(start, size, seed, settings)
        run = find_run(cfg, sha, root)
        if run is None:
            run = finetune.finetune(parent, cfg, root=root, log=log, threads=threads)
            train_s = time.perf_counter() - t
        path, run_id = run.model_path, run.id
    eval_key = hashlib.sha256(json.dumps([EVAL_VERSION, path and os.path.relpath(path, root), sha,
                                          {k: settings[k] for k in ("test_games", "tight_every", "tight2_every")},
                                          tight_specs(settings)[1], registry.rules_version()], sort_keys=True)
                              .encode()).hexdigest()[:16]
    cache = os.path.join(out_dir, "cells", f"{cell_key(start, size, seed)}-{eval_key}.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    m = evaluate(Net(path), settings, root, log, threads)
    cell = {"start": start, "size": size, "seed": seed, "run": run_id, "train_seconds": round(train_s, 1),
            "settings": cell_settings(start, size, seed, settings), **m}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cell, f)
    log(f"  cell {cell_key(start, size, seed)}: train {train_s:.0f}s, eval {m['eval_seconds']:.0f}s")
    return cell


# --- summaries and the gate --------------------------------------------------

def seed_mean_mse(group, kind):
    """(per-game seed-mean error sums, states per game, per-seed MSEs)."""
    num = np.mean([c["mse"][kind]["num"] for c in group], 0)
    den = np.asarray(group[0]["mse"][kind]["den"], np.float64)
    return num, den, [float(np.sum(c["mse"][kind]["num"]) / np.sum(den)) for c in group]


def mse_diff(a, b, kind):
    """Seed-mean MSE of cells `a` minus `b` on test set `kind`: [point, lo,
    hi] (paired bootstrap over test games: ratio_boot draws the same games
    for both), and the sd over seed indices of the per-seed differences."""
    na, den, sa = seed_mean_mse(a, kind)
    nb, _, sb = seed_mean_mse(b, kind)
    pa, xa = bench.ratio_boot(na, den)
    pb, xb = bench.ratio_boot(nb, den)
    diff = bench.interval(pa - pb, xa - xb)
    k = min(len(sa), len(sb))
    sd = float(np.std(np.subtract(sa[:k], sb[:k]), ddof=1)) if k >= 2 else None
    return diff, sd


def lead(a, b, half):
    """Seed-mean win of `a` minus `b` per tight_silent spec: [mean, lo, hi]
    (normal interval over specs)."""
    wa = np.mean([c["tight"][half]["won"] for c in a], 0)
    wb = np.mean([c["tight"][half]["won"] for c in b], 0)
    d = wa - wb
    w = bench.Z * (d.std(ddof=1) if len(d) > 1 else 0.0) / np.sqrt(max(1, len(d)))
    return [bench.r6(d.mean()), bench.r6(d.mean() - w), bench.r6(d.mean() + w)]


def comparisons(by, sizes):
    """The gate's inputs from cells grouped by (start, size)."""
    rows, floor = [], {}
    for z in sizes:
        for a, b in COMPARE:
            if (a, z) not in by or (b, z) not in by:
                continue
            for half in TIERS:
                row = {"size": z, "pair": f"{a} - {b}", "tier": half, "win_lead": lead(by[(a, z)], by[(b, z)], half)}
                if z > 0:
                    row["mse_diff"], row["seed_sd"] = mse_diff(by[(a, z)], by[(b, z)], half)
                rows.append(row)
                if z == 0 and b == "fresh_effects":
                    floor[half] = row["win_lead"]
    return rows, floor


def gate(rows, floor, sizes):
    """{"pass": bool | None (incomplete), "rows": [...], "floor": {...}}.
    Each MSE row passes when its interval lies wholly below 0; `luck` marks
    a difference smaller than twice its seed sd. The floor passes when the
    size-0 lead over the random floor is above 0 on both halves."""
    out, ok = [], True
    for r in rows:
        if "mse_diff" not in r:
            continue
        d, sd = r["mse_diff"], r.get("seed_sd")
        r = {**r, "pass": d is not None and d[2] < 0,
             "luck": bool(d is not None and sd is not None and abs(d[0]) < 2 * sd)}
        ok &= r["pass"]
        out.append(r)
    floor_ok = {h: floor[h] is not None and floor[h][1] > 0 for h in floor}
    need = {(z, p, t) for z in sizes if z > 0 for p in (f"{a} - {b}" for a, b in COMPARE) for t in TIERS}
    have = {(r["size"], r["pair"], r["tier"]) for r in out}
    complete = need <= have and set(floor) == set(TIERS)
    return {"pass": (ok and all(floor_ok.values())) if complete else None, "rows": out,
            "floor": {h: {"lead": floor[h], "pass": floor_ok[h]} for h in floor}}


def summary(cell):
    """A cell's headline numbers (no per-game arrays)."""
    out = {k: cell[k] for k in ("start", "size", "seed", "run", "train_seconds", "eval_seconds")}
    out["mse"] = {k: bench.r6(np.sum(v["num"]) / max(1, np.sum(v["den"]))) for k, v in cell["mse"].items()}
    out["tight"] = {h: {"win": bench.wilson(sum(v["won"]), len(v["won"])), "hp_lost": bench.r6(np.mean(v["lost"])),
                        "stalled": sum(v.get("stalled", []))} for h, v in cell["tight"].items()}
    t2 = cell["tight2_train"]
    out["tight2_train"] = {"win": bench.wilson(sum(t2["won"]), len(t2["won"])), "stalled": sum(t2.get("stalled", []))}
    return out


def table(result):
    lines = [f"{'start':<14} {'size':>6} {'seed':>4} {'mse a':>7} {'mse b':>7} {'mse ic':>7} "
             f"{'win a':>6} {'win b':>6} {'win ic':>6} {'train s':>8} {'eval s':>6}"]
    for c in result["cells"]:
        lines.append(f"{c['start']:<14} {c['size']:>6} {str(c['seed']):>4} {c['mse']['silent_a']:>7.4f} "
                     f"{c['mse']['silent_b']:>7.4f} {c['mse']['ironclad']:>7.4f} "
                     f"{c['tight']['silent_a']['win'][0]:>6.3f} {c['tight']['silent_b']['win'][0]:>6.3f} "
                     f"{c['tight2_train']['win'][0]:>6.3f} {c['train_seconds']:>8.0f} {c['eval_seconds']:>6.0f}")
    g = result["gate"]
    lines.append("\ngate rows (MSE difference, seed-mean; interval must lie below 0):")
    for r in g["rows"]:
        d = r["mse_diff"]
        sd = "n/a" if r["seed_sd"] is None else f"{r['seed_sd']:.4f}"
        lines.append(f"  size {r['size']:>6} {r['pair']:<28} {r['tier']:<9} {d[0]:+.4f} [{d[1]:+.4f}, {d[2]:+.4f}]"
                     f" seed sd {sd}  {'pass' if r['pass'] else 'FAIL'}{'  (within training luck)' if r['luck'] else ''}")
    for h, f in g["floor"].items():
        lines.append(f"  size 0 warm_effects - random floor, tight win {h}: {f['lead']}  {'pass' if f['pass'] else 'FAIL'}")
    verdict = {True: "pass", False: "FAIL", None: "incomplete (not every start ran)"}[g["pass"]]
    lines.append(f"gate: {verdict}")
    return "\n".join(lines)


def curve(settings, starts=STARTS, root=ROOT, out_dir=OUT, log=print, threads=None):
    """Runs (or reuses) every cell of `starts`, then summarises every
    cached cell of the ladder (other processes' too) and the gate; writes
    `<out_dir>/curve.json` and returns the result."""
    t = time.perf_counter()
    for s, z, k in cells(settings, starts):
        run_cell(s, z, k, settings, root, out_dir, log, threads)
    by, found = {}, []
    for s, z, k in cells(settings, STARTS):
        c = run_cell(s, z, k, settings, root, out_dir, log, threads) if s in starts else _cached(s, z, k, out_dir,
                                                                                                    settings)
        if c is not None:
            by.setdefault((s, z), []).append(c)
            found.append(c)
    rows, floor = comparisons(by, settings["sizes"])
    result = {"settings": settings, "starts": list(starts), "tight_real": tight_specs(settings)[1],
              "cells": [summary(c) for c in found], "comparisons": rows, "gate": gate(rows, floor, settings["sizes"]),
              "seconds": round(time.perf_counter() - t, 1)}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "curve.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=1)
        f.write("\n")
    return result


def _cached(start, size, seed, out_dir, settings):
    """Another process's cached cell made with these settings
    (`cell_settings`), else None."""
    d = os.path.join(out_dir, "cells")
    if not os.path.isdir(d):
        return None
    prefix = cell_key(start, size, seed) + "-"
    want = json.loads(json.dumps(cell_settings(start, size, seed, settings)))  # as stored (lists, not tuples)
    for name in sorted(os.listdir(d)):
        if name.startswith(prefix) and name[len(prefix):-len(".json")].isalnum():
            with open(os.path.join(d, name), encoding="utf-8") as f:
                cell = json.load(f)
            if cell.get("settings") == want:
                return cell
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ints = lambda s: [int(x) for x in s.split(",")]  # noqa: E731
    ap.add_argument("--sizes", type=ints, help="new games per group (default 0,500,2000,10000)")
    ap.add_argument("--seeds", type=ints, help="training seeds (default 0,1,2)")
    ap.add_argument("--starts", default=",".join(STARTS), help="subset of " + ",".join(STARTS))
    ap.add_argument("--test-games", type=int, help="test games per group and tier (default 1000)")
    for k in ("share", "lr"):
        ap.add_argument(f"--{k}", type=float)
    for k in ("epochs", "n_val", "pool", "tight_every", "tight2_every"):
        ap.add_argument(f"--{k.replace('_', '-')}", dest=k, type=int)
    ap.add_argument("--quick", action="store_true", help="tiny ladder and sets, for tests")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--root", default=ROOT, help="registry root (datasets, runs, cache)")
    ap.add_argument("--threads", type=int, default=None, help="search threads")
    args = ap.parse_args(argv)
    settings = {**DEFAULTS, **(QUICK if args.quick else {})}
    for k in ("sizes", "seeds", "test_games", "share", "lr", "epochs", "n_val", "pool", "tight_every", "tight2_every"):
        if getattr(args, k) is not None:
            settings[k] = getattr(args, k)
    starts = tuple(s for s in args.starts.split(",") if s)
    bad = [s for s in starts if s not in PARENTS]
    if bad:
        ap.error(f"unknown start(s) {bad}; choose from {list(PARENTS)}")
    if args.threads:
        torch.set_num_threads(min(4, args.threads))
    result = curve(settings, starts, args.root, args.out, threads=args.threads)
    print(table(result))
    print(f"total {result['seconds']:.0f}s")
    return 1 if result["gate"]["pass"] is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
