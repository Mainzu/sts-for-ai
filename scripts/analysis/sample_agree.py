"""Sample-size check for two-turn search (prior-art report, Rubin's PIMC check;
Next 0): on decisions from real fights, run two-turn search twice with
different sample seeds at `--sample-k`, once at `--big-k`, and count how
often the chosen option differs. A high disagreement rate at sample_k 4 means
two-turn search is under-sampled and its overrides are partly noise.

Each row also keeps one-turn's top-2 value gap and whether two-turn overrides
one-turn, so the same data reads as an offline depth gate (framing 2): how
many of the overrides sit on decisions where one-turn's top two are close.

    python scripts/analysis/sample_agree.py --evaluator runs/<champion>/model.pt --threads 2 --out results/depth/sample-agree.json

Fights are played by one-turn search (the net); every `--every`-th decision
with two or more options is probed. Decisions where any two-turn tree cut
are skipped (the fallback player uses one-turn there).
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import sts  # noqa: E402
from depth_paired import TURN_LIMIT, fights  # noqa: E402

_EV = {}


def fight_rows(job):
    s, two, big_k, every, evaluator = job
    if evaluator not in _EV:
        _EV[evaluator] = bench.load_evaluator(evaluator)
    ev = _EV[evaluator]
    c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"])
    rows, n = [], 0
    while not c.is_over() and c.turn() <= TURN_LIMIT:
        r1 = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)
        if n % every == 0 and len(r1["options"]) > 1:
            t = time.time()
            base = s["seed"] * 1009 + n
            ra, rb, rc = (sts.search(c, ev.evaluator, features=ev.features, seed=(base + off) % 2**64,
                                     **{**two, "sample_k": k})
                          for off, k in ((0, two["sample_k"]), (7919, two["sample_k"]), (104729, big_k)))
            if not (ra["cuts"] or rb["cuts"] or rc["cuts"]):
                v1 = np.array([v for _, v in r1["options"]])
                srt = np.sort(v1)[::-1]
                va = np.array([v for _, v in ra["options"]])
                best = [int(np.argmax([v for _, v in r["options"]])) for r in (ra, rb, rc)]
                b1 = int(np.argmax(v1))
                # d1: what one-turn loses by seed a's pick (0 when the override only breaks a tie);
                # dab: seed a's own value gap between its pick and seed b's
                rows.append({"encounter": s["encounter"], "group": s["group"], "n_opts": len(v1),
                             "b1": b1, "a": best[0], "b": best[1], "big": best[2],
                             "gap1": float(srt[0] - srt[1]), "d1": float(v1[b1] - v1[best[0]]),
                             "dab": float(va[best[0]] - va[best[1]]), "s": time.time() - t})
        c.step(r1["action"])
        n += 1
    return rows


def share(rows, f):
    return float(np.mean([f(r) for r in rows])) if rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--half", default="held_out")
    ap.add_argument("--groups", default="elite,boss")
    ap.add_argument("--per-cell", type=int, default=1)
    ap.add_argument("--every", type=int, default=3)
    ap.add_argument("--sample-k", type=int, default=4)
    ap.add_argument("--big-k", type=int, default=16)
    ap.add_argument("--max-nodes", type=int, default=400_000)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--evaluator", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    specs = fights(args.half, args.groups.split(","), args.per_cell)
    two = {"limit": bench.LIMIT, "turns": 2, "sample_k": args.sample_k, "max_nodes": args.max_nodes}
    print(f"{len(specs)} fights; two-turn {two}, big_k {args.big_k}", flush=True)
    rows, t = [], time.time()
    with ProcessPoolExecutor(args.threads) as pool:
        futs = [pool.submit(fight_rows, (s, two, args.big_k, args.every, args.evaluator)) for s in specs]
        for i, fut in enumerate(as_completed(futs)):
            rows += fut.result()
            print(f"  {i + 1}/{len(specs)} fights, {len(rows)} decisions, {time.time() - t:.0f}s", flush=True)

    bins = []
    edges = [1e-9, 0.01, 0.05]  # one-turn's top two tied, close, apart, far apart
    for lo, hi in zip([-np.inf, *edges], [*edges, np.inf]):
        q = [r for r in rows if lo < r["gap1"] <= hi]
        bins.append({"gap_hi": hi, "n": len(q), "override": share(q, lambda r: r["a"] != r["b1"]),
                     "real_override": share(q, lambda r: r["d1"] > 1e-9),
                     "k_disagree": share(q, lambda r: r["a"] != r["b"]),
                     "real_k_disagree": share(q, lambda r: abs(r["dab"]) > 1e-9)})
    summary = {
        "decisions": len(rows),
        "k_disagree": share(rows, lambda r: r["a"] != r["b"]),  # same k, two seeds
        "override": share(rows, lambda r: r["a"] != r["b1"]),  # two-turn (seed a) vs one-turn
        "real_override": share(rows, lambda r: r["d1"] > 1e-9),  # to an option one-turn values lower
        "real_k_disagree": share(rows, lambda r: abs(r["dab"]) > 1e-9),
        "real_override_kept_by_b": share([r for r in rows if r["d1"] > 1e-9], lambda r: r["b"] == r["a"]),
        "override_b": share(rows, lambda r: r["b"] != r["b1"]),
        "big_vs_a": share(rows, lambda r: r["big"] != r["a"]),
        "big_override": share(rows, lambda r: r["big"] != r["b1"]),
        "override_kept_by_b": share([r for r in rows if r["a"] != r["b1"]], lambda r: r["b"] == r["a"]),
        "override_kept_by_big": share([r for r in rows if r["a"] != r["b1"]], lambda r: r["big"] == r["a"]),
        "mean_s": share(rows, lambda r: r["s"]),
        "by_gap1": bins,
    }
    print(json.dumps(summary, indent=1))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"args": vars(args), "summary": summary, "rows": rows}, f, indent=1)


if __name__ == "__main__":
    main()
