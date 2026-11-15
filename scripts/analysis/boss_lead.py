"""Boss lead per boss (docs/specs/tight-bosses.md step 3): the seed-check
round-2 retrains (3 training seeds) against the heuristic on tight_bosses
(Hexaghost, The Guardian) and on tight2's Slime Boss cells, paired by
fight, per boss and half. Intervals are over cells (fights cluster by
cell): per-cell mean of net minus heuristic, then mean +- 1.96 sd /
sqrt(cells). The new bosses are outside Encounter::ALL, so no net has
trained on them.

    .venv/Scripts/python scripts/analysis/boss_lead.py --threads 6 --out results/bosses/lead.json

`--nets` replaces the default nets: each a run name such as `lean-thr-s1`
(resolved at start to the newest `runs/*-<name>-r2-*/model.pt`; `--round`
picks another round) or a `.pt` path.
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
import bench_sets  # noqa: E402

NETS = {
    "r2 s1": "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt",
    "r2 s101": "runs/2026-10-29-seed-check-r2-s101-d1c75ff/model.pt",
    "r2 s201": "runs/2026-10-29-seed-check-r2-s201-875c528/model.pt",
}


def specs_by_half(bench_dir):
    """{half: specs}: tight_bosses' cells then tight2's Slime Boss cells."""
    new = bench_sets.load_set("tight_bosses", bench_dir)
    old = bench_sets.load_set("tight2")
    return {h: new[h] + [s for s in old[h] if s["encounter"] == "slime_boss"] for h in ("train", "held_out")}


def lead(specs, base, net):
    """{encounter: {fights, cells, heuristic, net, lead, lo, hi}}."""
    out = {}
    for enc in sorted({s["encounter"] for s in specs}):
        idx = [i for i, s in enumerate(specs) if s["encounter"] == enc]
        cells = {}
        for i in idx:
            cells.setdefault(specs[i]["cell"], []).append(float(net[i]) - float(base[i]))
        m = np.array([np.mean(v) for v in cells.values()])
        half = 1.96 * m.std(ddof=1) / np.sqrt(len(m)) if len(m) > 1 else float("nan")
        out[enc] = {"fights": len(idx), "cells": len(m), "heuristic": float(np.mean([base[i] for i in idx])),
                    "net": float(np.mean([net[i] for i in idx])), "lead": float(m.mean()),
                    "lo": float(m.mean() - half), "hi": float(m.mean() + half)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default=bench_sets.BENCH, help="folder holding tight_bosses.json")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--nets", nargs="*", help="run names or .pt paths (default: the seed-check r2 nets)")
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.nets:
        NETS.clear()
        for n in args.nets:
            if n.endswith(".pt"):
                NETS[n] = n
                continue
            g = sorted(glob.glob(f"runs/*-{n}-r{args.round}-*/model.pt"))
            if not g:
                sys.exit(f"no run matches {n} r{args.round}")
            NETS[n] = g[-1].replace("\\", "/")
    print("nets:", NETS, flush=True)
    halves = specs_by_half(args.bench)
    search = {"limit": bench.LIMIT, "threads": args.threads}
    res = {}
    for h, specs in halves.items():
        t = time.time()
        base = [r["won"] for r in bench.run_specs(specs, search=search)]
        res[h] = {"heuristic": base, "nets": {}}
        print(f"{h}: {len(specs)} fights, heuristic {np.mean(base):.3f} ({time.time() - t:.0f}s)", flush=True)
        for name, path in NETS.items():
            t = time.time()
            won = [r["won"] for r in bench.run_specs(specs, ev=bench.load_evaluator(path), search=search)]
            res[h]["nets"][name] = won
            print(f"  {name}: {np.mean(won):.3f} ({time.time() - t:.0f}s)", flush=True)
    summary = {}
    for h, specs in halves.items():
        base = res[h]["heuristic"]
        mean_net = np.mean([res[h]["nets"][n] for n in NETS], 0)
        summary[h] = {"mean of nets": lead(specs, base, mean_net),
                      **{n: lead(specs, base, res[h]["nets"][n]) for n in NETS}}
        for enc, r in summary[h]["mean of nets"].items():
            per = " ".join(f"{summary[h][n][enc]['lead']:+.3f}" for n in NETS)
            print(f"{h:8s} {enc:13s} cells {r['cells']:3d} heur {r['heuristic']:.3f} net {r['net']:.3f} "
                  f"lead {r['lead']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]  per seed {per}")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"nets": NETS, "summary": summary,
                   "fights": {h: [{"cell": s["cell"], "encounter": s["encounter"], "seed": s["seed"]} for s in sp]
                              for h, sp in halves.items()},
                   "won": res}, f, indent=1)


if __name__ == "__main__":
    main()
