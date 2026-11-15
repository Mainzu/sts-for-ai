"""Per-encounter lead of the round-2 seed-check nets (3 seeds, averaged)
over search + heuristic on tight fights v2, and of the champion (ladder
test 0001) per encounter. Zero CPU: reads stored win bits only.

The heuristic averages each monster's damage over its next 4 moves; the
nets see only the current intent. If missing pattern information costs the
nets, their lead should be lowest on encounters whose next moves are
predictable from history but not from the current intent.

Output: scripts/analysis/out/pattern_encounter_lead.json and a table."""
import json, os, sys
from collections import defaultdict
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bench_sets

check = json.load(open(os.path.join(ROOT, "runs", "seed-check", "check.json")))
tight = bench_sets.load_set("tight2")


def cluster_se(diff, cells):
    """Mean of per-fight diffs and its se clustered by cell."""
    diff = np.asarray(diff, float)
    cells = np.asarray(cells)
    ids, inv = np.unique(cells, return_inverse=True)
    sums = np.bincount(inv, weights=diff)
    n = len(diff)
    m = diff.mean()
    resid = sums - np.bincount(inv) * m
    var = (resid ** 2).sum() / n ** 2 * len(ids) / max(len(ids) - 1, 1)
    return m, var ** 0.5, len(ids)


out = {"tight2": {}, "ladder0001": {}}
for rnd in ["2", "4", "7", "10"]:
    seeds = check["rounds"][rnd]["seeds"]
    res = {}
    for half in ["train", "held_out"]:
        specs = tight[half]
        h = np.array([int(c) for c in check["heuristic_fights"][half]], float)
        nets = []
        for s in seeds.values():
            f = s["fights"]
            if isinstance(f, str):
                f = eval(f)  # stored as a repr in check.json
            nets.append(np.array([int(c) for c in f[half]], float))
        net = np.mean(nets, axis=0)
        assert len(net) == len(specs) == len(h), (len(net), len(specs), len(h))
        by = defaultdict(list)
        for i, sp in enumerate(specs):
            by[(sp["group"], sp["encounter"])].append(i)
        for (g, e), idx in sorted(by.items()):
            idx = np.array(idx)
            d = net[idx] - h[idx]
            m, se, nc = cluster_se(d, [specs[i]["cell"] for i in idx])
            res.setdefault(f"{g}/{e}", {})[half] = {
                "n": int(len(idx)), "cells": nc, "heuristic": float(h[idx].mean()),
                "net": float(net[idx].mean()), "lead": m, "se": se}
    out["tight2"][rnd] = res

lad = json.load(open(os.path.join(ROOT, "results", "ladder", "tests", "0001.json")))
by = defaultdict(list)
for p in lad["pairs_played"]:
    if p.get("counted", True):
        by[(p["group"], p["encounter"], p["half"])].append((p["cand"] - p["champ"], p["cell"]))
for (g, e, half), v in sorted(by.items()):
    d, c = zip(*v)
    m, se, nc = cluster_se(d, c)
    out["ladder0001"].setdefault(f"{g}/{e}", {})[half] = {"n": len(d), "lead": m, "se": se}

os.makedirs(os.path.join(os.path.dirname(__file__), "out"), exist_ok=True)
json.dump(out, open(os.path.join(os.path.dirname(__file__), "out", "pattern_encounter_lead.json"), "w"), indent=1)

print("tight2, round-2 nets (mean of 3 seeds) minus heuristic, se clustered by cell")
print(f"{'encounter':34s} {'train lead':>16s} {'n':>5s} {'held-out lead':>16s} {'n':>5s} | r4/r7/r10 train, held-out")
for k, v in out["tight2"]["2"].items():
    t, ho = v.get("train"), v.get("held_out")
    other = []
    for r in ["4", "7", "10"]:
        w = out["tight2"][r].get(k, {})
        other.append(f"{w.get('train', {}).get('lead', float('nan')):+.3f}/{w.get('held_out', {}).get('lead', float('nan')):+.3f}")
    fmt = lambda x: f"{x['lead']:+.3f} ({x['se']:.3f})" if x else "-"
    print(f"{k:34s} {fmt(t):>16s} {t['n'] if t else 0:5d} {fmt(ho):>16s} {ho['n'] if ho else 0:5d} | {' '.join(other)}")
print()
print("ladder 0001, champion (r2 s1) minus heuristic, fresh fights")
for k, v in out["ladder0001"].items():
    s = "  ".join(f"{h} {x['lead']:+.3f} ({x['se']:.3f}, n {x['n']})" for h, x in v.items())
    print(f"{k:34s} {s}")
