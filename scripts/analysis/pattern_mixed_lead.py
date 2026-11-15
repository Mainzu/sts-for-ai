"""Net-minus-heuristic lead on tight fights v2 split by the monsters an
encounter rolled (mixed encounters: exordium_thugs, exordium_wildlife,
three_louse, two_louse, small_slimes, large_slime). Rolls each fight's
monsters by creating the combat (no play). Round-2 seed-check nets, mean of
3 seeds. Output: scripts/analysis/out/pattern_mixed_lead.json."""
import json, os, re, sys
from collections import defaultdict
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bench_sets
import sts

check = json.load(open(os.path.join(ROOT, "runs", "seed-check", "check.json")))
tight = bench_sets.load_set("tight2")
MIXED = {"exordium_thugs", "exordium_wildlife", "three_louse", "two_louse", "small_slimes", "large_slime"}
NAME = re.compile(r"^\s+\[\d\] (.+?)  HP", re.M)


def cluster_se(diff, cells):
    diff = np.asarray(diff, float)
    ids, inv = np.unique(np.asarray(cells), return_inverse=True)
    m = diff.mean()
    resid = np.bincount(inv, weights=diff) - np.bincount(inv) * m
    return m, ((resid ** 2).sum() / len(diff) ** 2 * len(ids) / max(len(ids) - 1, 1)) ** 0.5, len(ids)


out = {}
rnd = "2"
for half in ["train", "held_out"]:
    specs = tight[half]
    h = np.array([int(c) for c in check["heuristic_fights"][half]], float)
    nets = []
    for s in check["rounds"][rnd]["seeds"].values():
        f = s["fights"]
        f = eval(f) if isinstance(f, str) else f
        nets.append(np.array([int(c) for c in f[half]], float))
    net = np.mean(nets, axis=0)
    by = defaultdict(list)
    for i, sp in enumerate(specs):
        if sp["encounter"] not in MIXED:
            continue
        c = sts.Combat(sp["deck"], sp["encounter"], sp["seed"], sp["hp"], None, sp["character"], False)
        names = NAME.findall(c.render())
        key = sp["encounter"] + ": " + " + ".join(sorted(set(n.replace("Red ", "").replace("Green ", "") for n in names)))
        by[key].append(i)
    for k, idx in sorted(by.items()):
        idx = np.array(idx)
        m, se, nc = cluster_se(net[idx] - h[idx], [specs[i]["cell"] for i in idx])
        out.setdefault(k, {})[half] = {"n": int(len(idx)), "cells": nc, "heuristic": float(h[idx].mean()), "lead": m, "se": se}

json.dump(out, open(os.path.join(os.path.dirname(__file__), "out", "pattern_mixed_lead.json"), "w"), indent=1)
print(f"{'encounter: monsters':52s} {'train lead (se, n)':>24s} {'held-out lead (se, n)':>24s}")
for k, v in out.items():
    f = lambda x: f"{x['lead']:+.3f} ({x['se']:.3f}, {x['n']})" if x else "-"
    print(f"{k:52s} {f(v.get('train')):>24s} {f(v.get('held_out')):>24s}")
