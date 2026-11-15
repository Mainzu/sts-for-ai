"""Start-HP arms read (docs/specs/start-hp.md "The experiment"): pairs two
`ladder.py runhp` records by fight (half, cell, seed) and prints HP saved
(control's HP lost minus the arm's), by fight group, plus deaths. Both
records must cover the same fights (same first block and pairs).

    python scripts/analysis/start_hp_read.py results/ladder/runhp/<arm>.json:results/ladder/runhp/<control>.json ...
"""

import json
import sys

import numpy as np


def load(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d, {(p["half"], p["cell"], p["seed"]): p for p in d["pairs_played"]}


def mean_se(x):
    x = np.asarray(x, float)
    return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else 0.0


for pair in sys.argv[1:]:
    a_path, c_path = pair.split(":")
    a, ar = load(a_path)
    c, cr = load(c_path)
    keys = sorted(set(ar) & set(cr))
    print(f"{a['candidate']}\n  vs {c['candidate']}: {len(keys)} shared fights")
    for g in ("all", "hallway", "elite", "boss"):
        ks = [k for k in keys if g == "all" or ar[k]["group"] == g]
        if not ks:
            continue
        m, se = mean_se([cr[k]["cand_lost"] - ar[k]["cand_lost"] for k in ks])
        deaths = sum(1 - ar[k]["cand_won"] for k in ks) - sum(1 - cr[k]["cand_won"] for k in ks)
        print(f"  {g:8s} n {len(ks):4d} saved {m:+.2f} HP (se {se:.2f})  deaths arm - control {deaths:+d}")
