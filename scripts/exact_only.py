"""Exact-only experiment (docs/specs/exact-only.md): can the net learn the
values one turn from the end? Two nets trained from scratch on exact values
from the training database only:

- A, decisions: decision states with their exact values, their options'
  afterstates ranking-only (`learn.exact_examples`, no cap);
- B, decisions + leaves: A plus, per option paused at a random event (End
  turn's state before the draw, which one-turn search scores), that state
  with the option's exact value.

Rows: the current version's decision rows at `turns_left` 1-3 (up to ROWS,
drawn uniformly) and as many at 0; rows whose key hash is 0 mod HOLD are
held out (validation and the fit check). Both nets, the night's final net
(REFERENCE) and the heuristic are then scored: bench puzzle regret per
horizon (bootstrap intervals, paired against the heuristic), static value
MSE per state kind and `turns_left` on training and held-out rows (nets
only: the heuristic has no static value in Python), and the tight fights
paired against the heuristic (learned-play Amendment 5's gate).

    python scripts/exact_only.py [--db db/train.sqlite] [--out runs/exact-only] [--rows N]
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time

import numpy as np

import bench
import learn
import selfplay
import sts
import stsnet
import train

HOLD = 10
# Rows per side (turns_left 1-3, and 0): measured 2026-10-28, ~5.4 examples
# per row (6-7 with leaves) and ~27 s per training epoch per ~300k examples,
# so 60k + 60k rows train in ~20 min per arm.
ROWS = 60_000
FIT_ROWS = 5_000  # rows per split and side for the fit check
SEED = 616161
BOOT = 2000
REFERENCE = "runs/2026-10-28-score+branch-s1-r10-3c58554/model.pt"
MODE = "effects"


def select_rows(path, n=ROWS, seed=SEED):
    """{"train": ids, "held_out": ids} of the database's current-version
    decision rows: up to `n` drawn uniformly at `turns_left` 1-3 and as many
    at 0, per split (held out: key hash 0 mod HOLD); and {id: turns_left}."""
    fp = sts.SolvedDb(path).fingerprint
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    (version,), = con.execute("select id from versions where fingerprint = ?", (fp,))
    rows = np.array(con.execute("select id, key_hash, turns_left from states where version = ? "
                                "and options is not null and turns_left <= 3", (version,)).fetchall(), np.int64)
    con.close()
    rng = np.random.default_rng(seed)
    out = {}
    for split, keep in (("train", rows[:, 1] % HOLD != 0), ("held_out", rows[:, 1] % HOLD == 0)):
        far = rows[keep & (rows[:, 2] >= 1), 0]
        near = rows[keep & (rows[:, 2] == 0), 0]
        k = min(n, len(far), len(near))
        out[split] = np.concatenate([rng.choice(far, k, replace=False), rng.choice(near, k, replace=False)])
    return out, dict(zip(rows[:, 0].tolist(), rows[:, 2].tolist()))


def build(db, ids, leaves, out=None):
    """One arm's examples over rows `ids` (every value example weight 1)."""
    return learn.exact_examples({"mode": MODE, "exact_cap": 1 << 62}, db, None, ids=ids, leaves=leaves, out=out)


def fit_net(name, train_ds, val_ds, out_dir, log=print):
    """Trains a net as the night's rounds do (score target, ranking term);
    returns its model path."""
    curves = {}
    model, norm, hist = train.train(MODE, train_ds, val_ds, 0, log, curves, rank_weight=learn.RANK_WEIGHT)
    meta = {"card_repr": MODE, **selfplay.meta_vocab(MODE), "held_out": selfplay.HELD_OUT,
            "held_out_check9": sts.held_out_card_names(), "val_mse": min(hist), "format": selfplay.FORMAT,
            "run": name, "switches": {}}
    path = os.path.join(out_dir, name, "model.pt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stsnet.save(path, model, norm, meta)
    with open(os.path.join(out_dir, name, "curves.json"), "w") as f:
        json.dump(curves, f)
    return path


def fit_states(db, ids, turns):
    """[(state, exact value, kind, turns_left)] over rows `ids`: each
    non-dull decision state ("decision") and its options' states paused at
    a random event ("leaf"), as the arms build them."""
    out = []
    for i, (code, value, opts) in zip(ids, db.fetch([int(i) for i in ids])):
        if learn.dull([o[1] for o in opts], [any(a.is_end_turn for a in o[0]) for o in opts], [o[2] for o in opts]):
            continue
        s = sts.Combat.decode(code)
        out.append((s, value, "decision", turns[int(i)]))
        for (_, _, outs), o in zip(s.options(1), opts):
            if o[2]:
                continue  # a bounded option's value is only an upper bound (solver bounds)
            out += [(x, o[1], "leaf", turns[int(i)]) for _, x in outs if not x.is_over() and not x.awaiting_action()]
    return out


def fit_table(ev, states):
    """{"kind tl": [mse, n]} of a net's static values over `fit_states`."""
    v = bench.static_values(ev, [s for s, _, _, _ in states])
    err = (v - np.array([x for _, x, _, _ in states])) ** 2
    out = {}
    for key in sorted({f"{k} {t}" for _, _, k, t in states}):
        m = np.array([f"{k} {t}" == key for _, _, k, t in states])
        out[key] = [float(err[m].mean()), int(m.sum())]
    return out


def boot(x, seed=SEED):
    """[mean, lo, hi] of `x`'s mean, 95% bootstrap (BOOT resamples)."""
    x = np.asarray(x, float)
    if not len(x):
        return [None, None, None]
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), (BOOT, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def regret_table(rows, picks, ref="heuristic"):
    """{evaluator: {horizon: {"regret": boot, "vs": boot of the paired
    difference against `ref`}}} from bench puzzle rows and each evaluator's
    picks (dull puzzles skipped, as the zone does)."""
    per = {name: learn.horizon_regrets(rows, p)[0] for name, p in picks.items()}
    out = {}
    for name, hs in per.items():
        out[name] = {}
        for h in sorted(hs):
            d = np.array(hs[h]) - np.array(per[ref][h])
            out[name][h] = {"n": len(hs[h]), "regret": boot(hs[h]), "vs": boot(d) if name != ref else None}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="db/train.sqlite")
    ap.add_argument("--out", default="runs/exact-only")
    ap.add_argument("--rows", type=int, default=ROWS)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    res_path = os.path.join(args.out, "results.json")
    res = json.load(open(res_path)) if os.path.exists(res_path) else {}

    def save():
        with open(res_path, "w") as f:
            json.dump(res, f, indent=1)

    t0 = time.perf_counter()
    ids, turns = select_rows(args.db, args.rows)
    db = sts.SolvedDb(args.db)
    res["rows"] = {k: len(v) for k, v in ids.items()}
    models = {}
    for arm, leaves in (("A", False), ("B", True)):
        path = os.path.join(args.out, arm, "model.pt")
        if not os.path.exists(path):
            t = time.perf_counter()
            data = os.path.join(args.out, arm, "data")
            os.makedirs(data, exist_ok=True)
            tr = build(db, ids["train"], leaves, os.path.join(data, "train"))
            va = build(db, ids["held_out"], leaves, os.path.join(data, "held_out"))
            va = va.take(np.flatnonzero(va.option == -1))  # validation MSE on the value examples
            res.setdefault("examples", {})[arm] = {"train": len(tr), "train_valued": int((tr.option == -1).sum()),
                                                   "held_out": len(va)}
            print(f"arm {arm}: {len(tr)} examples ({res['examples'][arm]['train_valued']} valued), "
                  f"built in {time.perf_counter() - t:.0f}s", flush=True)
            t = time.perf_counter()
            fit_net(arm, tr, va, args.out)
            res["examples"][arm]["train_min"] = (time.perf_counter() - t) / 60
            del tr, va
            shutil.rmtree(data, ignore_errors=True)
            save()
        models[arm] = path
    models["night"] = REFERENCE
    evs = {k: bench.load_evaluator(p) for k, p in models.items()}
    evs["heuristic"] = bench.load_evaluator("heuristic")

    rows = [r for half in bench.load_puzzles()["halves"].values() for r in half]
    picks = {k: bench.search_puzzles(ev, rows)[0] for k, ev in evs.items()}
    res["regret"] = regret_table(rows, picks)
    save()

    rng = np.random.default_rng(SEED + 1)
    fit = {}
    for split in ("train", "held_out"):
        half = len(ids[split]) // 2  # far rows first, then near
        pick = np.concatenate([rng.choice(ids[split][:half], min(FIT_ROWS, half), replace=False),
                               rng.choice(ids[split][half:], min(FIT_ROWS, half), replace=False)])
        states = fit_states(db, pick, turns)
        fit[split] = {k: fit_table(ev, states) for k, ev in evs.items() if ev.static is not None}
    res["fit"] = fit
    save()

    agent = {"limit": bench.LIMIT}
    heur = learn.tight_results("heuristic", agent, 1)
    cells = learn.tight_cells(1)
    res["tight"] = {k: learn.gate(learn.tight_results(p, agent, 1), heur, cells) for k, p in models.items()}
    res["minutes"] = (time.perf_counter() - t0) / 60
    save()
    print(report(res))


def report(res):
    """The results as markdown tables."""
    out = ["| evaluator | " + " | ".join(f"h{h} regret" for h in ("0", "1", "2", "3")) + " | h1 vs heuristic | h2 vs heuristic |",
           "|---|---|---|---|---|---|---|"]

    def f(b):
        return "-" if b is None or b[0] is None else f"{b[0]:.3f} [{b[1]:.3f}, {b[2]:.3f}]"
    for name, hs in res["regret"].items():
        hs = {str(k): v for k, v in hs.items()}
        cells = [f(hs[h]["regret"]) + f" (n {hs[h]['n']})" if h in hs else "-" for h in ("0", "1", "2", "3")]
        vs = [f(hs[h]["vs"]) if h in hs else "-" for h in ("1", "2")]
        out.append(f"| {name} | " + " | ".join(cells + vs) + " |")
    out += ["", "| net | split | " + " | ".join(sorted(next(iter(res["fit"]["train"].values())))) + " |"]
    keys = sorted(next(iter(res["fit"]["train"].values())))
    out.append("|---|---|" + "---|" * len(keys))
    for split, nets in res["fit"].items():
        for name, t in nets.items():
            out.append(f"| {name} | {split} | " + " | ".join(f"{t[k][0]:.4f}" if k in t else "-" for k in keys) + " |")
    out += ["", "| net | tight lead train | tight lead held-out |", "|---|---|---|"]
    for name, g in res["tight"].items():
        out.append(f"| {name} | " + " | ".join(f(g["halves"][h]["lead"]) for h in ("train", "held_out")) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
