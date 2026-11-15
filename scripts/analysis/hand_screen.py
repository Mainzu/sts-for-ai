"""Hand-count puzzle screen (docs/research/hands-where-small.md): the product's
decision (one-turn search, two-turn search with K sampled hands; the
one-turn pick where the two-turn tree cut, else the two-turn pick) at the
deeper exact puzzles (data/bench/puzzles.json, horizon >= 1), over several
sample seeds, for each K and for the adaptive rule (K 4; where the 4-hand
tree is uncut and under `--small` nodes, search again with 16 and take that
pick unless it cut). Regret is exact best minus the exact value of the pick.

    python scripts/analysis/hand_screen.py --threads 4 --out results/hands/puzzle-screen.json
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import bench_decisions  # noqa: E402
import sts  # noqa: E402

PLAYER = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01"
MAX_NODES = 400_000
SMALL = 25_000
_EV = {}


def seed_of(row, j):
    return (row["seed"] * 1009 + row["step"] * 31 + 7919 * j) % 2**64


def decide(c, ev, k, seed, max_nodes):
    """(option index in r1's order, nodes, cut) of the product's choice at
    two-turn sample count k."""
    r1 = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)
    r2 = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT, turns=2, sample_k=k, seed=seed,
                    max_nodes=max_nodes)
    v1 = [v for _, v in r1["options"]]
    v2 = [v for _, v in r2["options"]]
    assert len(v1) == len(v2), "one- and two-turn search list different root options"
    cut = r2["cuts"] > 0
    pick = int(np.argmax(v1)) if cut else int(np.argmax(v2))
    return r1["options"][pick][0], int(r2["nodes"]), cut


def puzzle(job):
    """One puzzle: per K, per seed, {regret, nodes, cut}."""
    row, player, ks, seeds, max_nodes = job
    if player not in _EV:
        _EV[player] = bench.load_evaluator(player)
    ev = _EV[player]
    exact = [o[1] for o in row["options"]]
    best = max(exact)
    groups = [frozenset(o[0]) for o in row["options"]]
    out = {}
    for k in ks:
        cells = []
        for j in range(seeds):
            t = time.perf_counter()
            acts, nodes, cut = decide(bench_decisions.replay(row), ev, k, seed_of(row, j), max_nodes)
            code = bench_decisions.encode_action(acts[0])
            g = next(i for i, grp in enumerate(groups) if code in grp)
            cells.append({"regret": best - exact[g], "nodes": nodes, "cut": cut,
                          "seconds": round(time.perf_counter() - t, 4)})
        out[str(k)] = cells
    return out


def adaptive(cells4, cells16, small):
    """Per seed {regret, rerun, seconds} of the adaptive rule."""
    out = []
    for a, b in zip(cells4, cells16):
        rerun = not a["cut"] and a["nodes"] < small
        use = b if rerun and not b["cut"] else a
        out.append({"regret": use["regret"], "rerun": rerun,
                    "seconds": a["seconds"] + (b["seconds"] if rerun else 0.0)})
    return out


def summary(rows, arms, base="4"):
    """{arm: {regret, se, minus_base, minus_base_se, nodes, seconds, ...}} with
    puzzle as the unit (each puzzle's mean over seeds)."""
    se = (lambda v: float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else float("nan"))
    per = {a: np.array([np.mean([c["regret"] for c in r["arms"][a]]) for r in rows]) for a in arms}
    out = {}
    for a in arms:
        d = per[a] - per[base]
        cells = [c for r in rows for c in r["arms"][a]]
        out[a] = {"n": len(rows), "regret": float(per[a].mean()), "se": se(per[a]),
                  "minus_" + base: float(d.mean()), "minus_" + base + "_se": se(d),
                  "seconds": float(np.mean([c["seconds"] for c in cells]))}
        if "nodes" in cells[0]:
            out[a]["nodes_mean"] = float(np.mean([c["nodes"] for c in cells]))
            out[a]["cut_share"] = float(np.mean([c["cut"] for c in cells]))
        if "rerun" in cells[0]:
            out[a]["rerun_share"] = float(np.mean([c["rerun"] for c in cells]))
    # the share of base regret on puzzles the base gets right on some seed
    noisy = [r for r in rows if min(c["regret"] for c in r["arms"][base]) <= bench.EXACT]
    tot = per[base].sum()
    out[base]["regret_share_noisy"] = (float(sum(np.mean([c["regret"] for c in r["arms"][base]]) for r in noisy) / tot)
                                       if tot > 0 else None)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--player", default=PLAYER)
    ap.add_argument("--ks", default="4,16", help="sample counts (must hold 4 and 16 for the adaptive arm)")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--small", type=int, default=SMALL, help="adaptive: re-search where the 4-hand tree is under this")
    ap.add_argument("--max-nodes", type=int, default=MAX_NODES)
    ap.add_argument("--min-horizon", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None, help="first n puzzles per half (smoke runs)")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    ks = [int(x) for x in a.ks.split(",")]
    pz = bench.load_puzzles()
    rows = []
    for half, hr in pz["halves"].items():
        keep = [r for r in hr if r["horizon"] >= a.min_horizon][:a.limit]
        rows += [(half, r) for r in keep]
    t0 = time.perf_counter()
    jobs = [(r, a.player, ks, a.seeds, a.max_nodes) for _, r in rows]
    with ProcessPoolExecutor(a.threads) as pool:
        res = list(pool.map(puzzle, jobs, chunksize=4))
    out_rows = []
    for (half, r), arms in zip(rows, res):
        if "4" in arms and "16" in arms:
            arms["adaptive"] = adaptive(arms["4"], arms["16"], a.small)
        out_rows.append({"half": half, "spec": r["spec"], "step": r["step"], "horizon": r["horizon"],
                         "gap": r["gap"], "arms": arms})
    arms = list(out_rows[0]["arms"]) if out_rows else []
    result = {"settings": {"player": a.player, "ks": ks, "seeds": a.seeds, "small": a.small, "max_nodes": a.max_nodes,
                           "min_horizon": a.min_horizon, "limit": a.limit, "fingerprint": pz["fingerprint"],
                           "seconds": round(time.perf_counter() - t0, 1)},
              "summary": {"all": summary(out_rows, arms),
                          **{h: summary([r for r in out_rows if r["half"] == h], arms) for h in pz["halves"]}},
              "rows": out_rows}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print(json.dumps(result["settings"]))
    print(json.dumps(result["summary"]["all"], indent=1))


if __name__ == "__main__":
    main()
