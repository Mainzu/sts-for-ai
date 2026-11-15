"""Draw-leaf screen (docs/specs/draw-leaf.md, build step 3): one-turn
search with the product net at the exact puzzles of horizon 1 or more,
plain and with the sampled-draw leaf `@dl<k>`: regret against the exact
option values (overall, by horizon, paired against plain) and search time
per puzzle on one thread.

Pass: regret falls by at least 0.01 from plain's at some k whose time is
at most 1.5x plain's.

    python scripts/analysis/draw_leaf_screen.py --net <main>/runs/<net>/model.pt --out <main>/results/probes/draw_leaf_screen.json
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402

PRICE = "@hpb0.01"  # the one-turn control's price (yardstick/one-turn-controls)
BAR_REGRET = 0.01
BAR_COST = 1.5


def regrets(rows, picks):
    exact = [[o[1] for o in r["options"]] for r in rows]
    return np.array([max(x) - x[p] for x, p in zip(exact, picks)])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--net", required=True)
    ap.add_argument("--ks", default="0,1,2,4")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    rows = [r for h in bench.load_puzzles()["halves"].values() for r in h if r["horizon"] >= 1]
    horizon = np.array([r["horizon"] for r in rows])
    out = {"net": args.net, "price": PRICE, "puzzles": len(rows), "arms": {}}
    base = None
    for k in [int(x) for x in args.ks.split(",")]:
        player = args.net + PRICE + (f"@dl{k}" if k else "")
        ev = bench.load_evaluator(player)
        t = time.perf_counter()
        picks, _ = bench.search_puzzles(ev, rows)
        sec = (time.perf_counter() - t) / len(rows)
        reg = regrets(rows, picks)
        arm = {"player": player, "regret": float(reg.mean()), "regret_h1": float(reg[horizon == 1].mean()),
               "regret_h2+": float(reg[horizon >= 2].mean()), "sec_per_puzzle": sec}
        if base is None:
            base = (reg, sec)
        else:
            d = base[0] - reg
            arm.update(gain=float(d.mean()), gain_se=float(d.std(ddof=1) / np.sqrt(len(d))), cost=sec / base[1])
        out["arms"][str(k)] = arm
        print(json.dumps({k: arm}), flush=True)
    passing = [k for k, a in out["arms"].items() if a.get("gain", 0) >= BAR_REGRET and a.get("cost", 99) <= BAR_COST]
    out["verdict"] = {"pass": bool(passing), "passing_k": passing, "bar_regret": BAR_REGRET, "bar_cost": BAR_COST}
    print(json.dumps(out["verdict"]))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
