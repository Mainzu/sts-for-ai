"""One-round check (curriculum Amendment 3): retrains the 2026-10-28 night's
last round (s1 r10: the same window, frontiers and seed) with the
amendment's exact labels (paused states, split draw, `--cap`) against a
copy of the database walked with bounds, and compares the new net with
s1 r10's own net:

- bench puzzles: regret per horizon, paired against s1 r10;
- the bench games' other positions (`db/solved.sqlite`): POSITIONS non-dull
  decisions per turns_left 1 and 2, every option exact, paired against
  s1 r10;
- the tight fights: each net paired against the heuristic (learned-play
  Amendment 5's gate), and the new net paired against s1 r10.

It passes when the new net is at least level with s1 r10 one turn out (the
paired interval of new - s1 r10 reaches 0 or below), better two turns out
(that interval wholly below 0) on the bench games' positions, and its
tight-fight lead over s1 r10 isn't below 0 by more than the paired interval
(the interval reaches 0 or above). The new net is a registry run left
unfinished, so no sweep reuses it.

`--frontier F` labels both datasets as if their players' trusted zones
reached F (rung 3 out to distance F), to test whether the zone's rule holds
the curriculum back.

    python scripts/round_check.py [--db db/bounds-check.sqlite] [--cap 150000] [--frontier F] [--out runs/round-check]
"""

import argparse
import json
import os
import sqlite3
import sys
import time

import numpy as np

import bench
import bench_decisions as bd
import exact_only
import learn
import registry
import sts

NIGHT = "runs/2026-10-28-score+branch-s1-r10-3c58554"
PARTS = [("d77bb12e7cef", 10), ("a205959573dd", 9)]  # its window: its own games, then round 9's
VAL = "eb96eb4a46c3"
POSITIONS = 600
POS_SEED = 7  # the bench games' positions sample
BENCH_DB = "db/solved.sqlite"


def position_rows(path=BENCH_DB, n=POSITIONS, seed=POS_SEED):
    """[(state bytes, options, turns_left)]: up to `n` non-dull decisions per
    turns_left 1 and 2 with every option exact, drawn at `seed` from the
    candidates in id order."""
    db = sts.SolvedDb(path)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rng = np.random.default_rng(seed)
    rows = []
    for tl in (1, 2):
        cand = np.array([r[0] for r in con.execute(
            "select id from states where options is not null and turns_left = ? and version = "
            "(select id from versions where fingerprint = ?) order by id", (tl, db.fingerprint))])
        got = 0
        for code, _, opts in db.fetch([int(i) for i in rng.choice(cand, min(len(cand), 4 * n), replace=False)]):
            if got >= n:
                break
            if any(o[2] for o in opts):
                continue  # regret needs every option exact
            if not learn.dull([o[1] for o in opts], [any(a.is_end_turn for a in o[0]) for o in opts]):
                rows.append((code, opts, tl))
                got += 1
    con.close()
    return rows


def position_regrets(rows, ev):
    """[(turns_left, regret)] of an evaluator's one-turn search picks."""
    out = []
    for code, opts, tl in rows:
        groups = [frozenset(bd.encode_action(a) for a in o[0]) for o in opts]
        exact = [o[1] for o in opts]
        s = sts.search(sts.Combat.decode(code), ev.evaluator, features=ev.features, limit=bench.LIMIT)
        pick = bd.encode_action(s["action"])
        j = next(g for g, grp in enumerate(groups) if pick in grp)
        out.append((tl, max(exact) - exact[j]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="db/bounds-check.sqlite", help="a copy of db/bounds.sqlite (read only here)")
    ap.add_argument("--cap", type=int, default=learn.A3_CAP)
    ap.add_argument("--frontier", type=int, help="every dataset's frontier, instead of its player's")
    ap.add_argument("--out", default="runs/round-check")
    args = ap.parse_args(argv)
    tag = f"cap{args.cap}" + (f"-f{args.frontier}" if args.frontier is not None else "")
    out_dir = os.path.join(args.out, tag)
    os.makedirs(out_dir, exist_ok=True)
    res_path = os.path.join(out_dir, "results.json")
    res = json.load(open(res_path)) if os.path.exists(res_path) else {}

    def save():
        with open(res_path, "w") as f:
            json.dump(res, f, indent=1)

    t0 = time.perf_counter()
    db_file = os.path.abspath(args.db)
    learn.db_path = lambda root=registry.ROOT: db_file  # the check's database, not the night's
    if args.frontier is not None:
        learn.dataset_frontier = lambda ds, root=registry.ROOT: args.frontier
    cfg = json.load(open(os.path.join(NIGHT, "config.json")))
    cfg = {**cfg, "name": f"round-check-{tag}", "exact_cap": args.cap,
           "exact_leaves": True, "exact_split": learn.A3_SPLIT}
    if "model" not in res:
        t = time.perf_counter()
        run, val_mse, scale, counts = learn.fit(cfg, cfg["name"], PARTS, VAL, finish=False, seed=cfg["seed"])
        res.update(model=run.model_path, val_mse=val_mse, rungs=counts, train_min=(time.perf_counter() - t) / 60)
        save()
    models = {"new": res["model"], "night": os.path.join(NIGHT, "model.pt")}
    evs = {k: bench.load_evaluator(p) for k, p in models.items()}
    evs["heuristic"] = bench.load_evaluator("heuristic")

    if "puzzles" not in res:
        rows = [r for half in bench.load_puzzles()["halves"].values() for r in half]
        picks = {k: bench.search_puzzles(ev, rows)[0] for k, ev in evs.items()}
        res["puzzles"] = exact_only.regret_table(rows, picks, ref="night")
        res["zone"] = learn.trusted_zone(cfg, models["new"])
        save()

    if "positions" not in res:
        rows = position_rows()
        reg = {k: position_regrets(rows, ev) for k, ev in evs.items()}
        res["positions"] = {}
        for tl in (1, 2):
            per = {k: np.array([r for t, r in v if t == tl]) for k, v in reg.items()}
            res["positions"][str(tl)] = {k: {"regret": exact_only.boot(x),
                                        "vs_night": exact_only.boot(x - per["night"]) if k != "night" else None}
                                    for k, x in per.items()}
        save()

    if "tight" not in res:
        agent = {"limit": bench.LIMIT}
        heur = learn.tight_results("heuristic", agent, 1)
        nets = {k: learn.tight_results(p, agent, 1) for k, p in models.items()}
        cells = learn.tight_cells(1)
        res["tight"] = {k: learn.gate(r, heur, cells) for k, r in nets.items()}
        res["tight"]["new_vs_night"] = learn.gate(nets["new"], nets["night"], cells)
        save()

    pos = res["positions"]
    tight = res["tight"]["new_vs_night"]["halves"]
    res["verdict"] = {
        "level_tl1": pos["1"]["new"]["vs_night"][1] <= 0,
        "better_tl2": pos["2"]["new"]["vs_night"][2] < 0,
        "tight_not_worse": all(h["lead"][2] >= 0 for h in tight.values()),
    }
    res["verdict"]["passes"] = all(res["verdict"].values())
    res["minutes"] = res.get("minutes", 0) + (time.perf_counter() - t0) / 60
    save()
    print(report(res))


def report(res):
    """The results as markdown."""
    def f(b):
        return "-" if b is None or b[0] is None else f"{b[0]:.3f} [{b[1]:.3f}, {b[2]:.3f}]"
    out = [f"val MSE {res['val_mse']:.4f}, training {res['train_min']:.0f} min, rungs {res['rungs']}",
           f"new net's frontier {res['zone']['frontier']}", "",
           "| evaluator | h0 | h1 | h2 | h3 | h1 vs night | h2 vs night |", "|---|---|---|---|---|---|---|"]
    for name, hs in res["puzzles"].items():
        hs = {str(k): v for k, v in hs.items()}
        cells = [f(hs[h]["regret"]) if h in hs else "-" for h in ("0", "1", "2", "3")]
        vs = [f(hs[h]["vs"]) if h in hs else "-" for h in ("1", "2")]
        out.append(f"| {name} | " + " | ".join(cells + vs) + " |")
    out += ["", "| bench games' positions | " + " | ".join(res["positions"][next(iter(res["positions"]))]) + " | new vs night |",
            "|---|---|---|---|---|"]
    for tl, per in res["positions"].items():
        out.append(f"| turns_left {tl} | " + " | ".join(f(v["regret"]) for v in per.values())
                   + f" | {f(per['new']['vs_night'])} |")
    out += ["", "| tight fights | lead train | lead held-out |", "|---|---|---|"]
    for name, g in res["tight"].items():
        out.append(f"| {name} | " + " | ".join(f(g["halves"][h]["lead"]) for h in ("train", "held_out")) + " |")
    out += ["", f"verdict: {res['verdict']}"]
    return "\n".join(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
