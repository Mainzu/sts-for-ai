"""Training-seed sd of the net's win rate per encounter on tight fights v2,
pooled within round over the seed check's rounds 2, 4, 7, 10 (3 seeds each,
8 degrees of freedom), and the minimum detectable effect of a 3-vs-3 seed
comparison per encounter: MDE = 2.8 x sd x sqrt(2/3). Zero CPU.
Output: scripts/analysis/out/pattern_encounter_sd.json and a table."""
import json
import os
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bench_sets

check = json.load(open(os.path.join(ROOT, "runs", "seed-check", "check.json")))
tight = bench_sets.load_set("tight2")
out = {}
for half in ["train", "held_out"]:
    specs = tight[half]
    groups = defaultdict(list)
    for i, sp in enumerate(specs):
        groups[sp["encounter"]].append(i)
        groups["type:" + sp["group"]].append(i)
    groups["all"] = list(range(len(specs)))
    for key, idx in groups.items():
        idx = np.array(idx)
        ss, df = 0.0, 0
        for rnd, r in check["rounds"].items():
            rates = []
            for s in r["seeds"].values():
                f = s["fights"]
                f = eval(f) if isinstance(f, str) else f
                rates.append(np.array([int(c) for c in f[half]], float)[idx].mean())
            rates = np.array(rates)
            ss += ((rates - rates.mean()) ** 2).sum()
            df += len(rates) - 1
        sd = (ss / df) ** 0.5
        out.setdefault(key, {})[half] = {"sd": sd, "df": df, "n": int(len(idx)), "mde_3v3": 2.8 * sd * (2 / 3) ** 0.5}
json.dump(out, open(os.path.join(os.path.dirname(__file__), "out", "pattern_encounter_sd.json"), "w"), indent=1)
print(f"{'encounter':22s} {'sd train':>9s} {'MDE':>6s} {'sd held':>9s} {'MDE':>6s}  (3 vs 3 seeds, 8 df)")
for k in sorted(out):
    t, h = out[k]["train"], out[k]["held_out"]
    print(f"{k:22s} {t['sd']:9.4f} {t['mde_3v3']:6.3f} {h['sd']:9.4f} {h['mde_3v3']:6.3f}")
