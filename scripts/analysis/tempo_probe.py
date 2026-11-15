"""Tempo probe (Next N1, HP efficiency): a net and the heuristic at one turn
on the run-HP pool's fights (the same fights as `ladder.py runhp`), with
turns per fight; by group and encounter: HP lost, turns, HP lost per turn.
Reading: if the net takes more turns where it loses more HP, it drags
fights out (tempo); if turns match and HP per turn is higher, it blocks
too little.

    python scripts/analysis/tempo_probe.py --net runs/<id>/model.pt --pairs 2000 --threads 4 --out results/probes/tempo.json
"""

import argparse
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import ladder  # noqa: E402
import selfplay  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--net", required=True)
ap.add_argument("--pairs", type=int, default=2000)
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--out", required=True)
args = ap.parse_args()

cells = ladder.pool_cells()
max_hp = {c["character"]: selfplay.max_hp(c["character"]) for c in cells}
specs, b = [], ladder.RUNHP_BLOCK0
while len(specs) < args.pairs:
    specs += [{**s, "hp": ladder.run_hp(s, max_hp[s["character"]])} for s in ladder.block(b, cells)]
    b += 1
specs = specs[:args.pairs]
search = {"limit": bench.LIMIT, "threads": args.threads}
res = {"heuristic": bench.run_specs(specs, ev=None, search=search),
       "net": bench.run_specs(specs, ev=bench.load_evaluator(args.net), search=search)}
rows = [{"group": s["group"], "encounter": s["encounter"], "cell": s["cell"], "seed": s["seed"], "hp": s["hp"],
         **{f"{k}_{f}": (ladder.hp_lost(r[i]) if f == "lost" else r[i][f]) for k, r in res.items()
            for f in ("won", "turns", "lost")}} for i, s in enumerate(specs)]
out = {}
by = collections.defaultdict(list)
for r in rows:
    by["all"].append(r)
    by["group=" + r["group"]].append(r)
    by["enc=" + r["encounter"]].append(r)
print(f"{'slice':28s} {'n':>5s} {'lost h/n':>13s} {'turns h/n':>11s} {'won turns h/n':>14s} {'lost/turn h/n':>14s}")
for k in sorted(by, key=lambda k: (k != "all", not k.startswith("group"), k)):
    v = by[k]
    m = {f: float(np.mean([r[f] for r in v])) for f in v[0] if f.endswith(("_lost", "_turns"))}
    both = [r for r in v if r["heuristic_won"] and r["net_won"]]
    wt = {p: float(np.mean([r[f"{p}_turns"] for r in both])) if both else None for p in ("heuristic", "net")}
    lpt = {p: float(np.mean([r[f"{p}_lost"] / max(1, r[f"{p}_turns"]) for r in both])) if both else None
           for p in ("heuristic", "net")}
    out[k] = {"n": len(v), **m, "won_turns": wt, "lost_per_turn": lpt}
    print(f"{k:28s} {len(v):5d} {m['heuristic_lost']:6.2f}/{m['net_lost']:6.2f} {m['heuristic_turns']:5.2f}/{m['net_turns']:5.2f}"
          f" {wt['heuristic'] or 0:6.2f}/{wt['net'] or 0:6.2f} {lpt['heuristic'] or 0:6.2f}/{lpt['net'] or 0:6.2f}")
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
with open(args.out, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"net": args.net, "pairs": len(rows), "slices": out, "rows": rows}, f, indent=1)
