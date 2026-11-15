"""Two-turn cost by decision index within the turn (docs/specs/line-seed.md,
step 2; approach review 2026-11-02, approach 1): how much of a turn's
two-turn search cost sits in the turn's first tree? A player that commits
to that tree's line would skip the later searches, so the index-0 share
bounds its saving.

Plays N held-out elite and boss fights single-threaded under the product's
two-turn settings (`ladder.TWO_TURN`, `bench.LIMIT`) with the fallback rule
of `depth_paired.guarded_fight` (one-turn's choice where the two-turn tree
cut, two-turn's otherwise; per-decision seeds, as today). Every two-turn
search is one row: fight, combat turn, index within the turn (0 = the
turn's first decision), nodes, leaves, wall ms, cut.

    python scripts/analysis/line_probe.py --evaluator runs/<net>/model.pt [--fights 20] [--out results/depth/line-probe.json]

Fights: the held-out elite and boss cells of tight2 (`depth_paired.fights`,
one per cell), taken round-robin over encounters so N fights spread evenly
over Gremlin Nob, Lagavulin, Three Sentries and Slime Boss.

`--compare` (docs/specs/line-step.md step 3) plays each fight twice with the
per-turn seed: as the stage-1 player (a search at every decision) and as
the stepping player (each uncut tree's principal line played out), and
reports the decision agreement off cut decisions (decision by decision up
to the first disagreement), the share of fights with identical action
sequences, and the stepping / stage-1 cost ratio for nodes, leaves and ms:

    python scripts/analysis/line_probe.py --compare --evaluator runs/<net>/model.pt [--fights 20] [--out results/depth/line-step-compare.json]
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import ladder  # noqa: E402
import sts  # noqa: E402
from depth_paired import TURN_LIMIT, fights  # noqa: E402


def pick(specs, n):
    """The first n fights round-robin over encounters, in the list's order."""
    by = {}
    for s in specs:
        by.setdefault(s["encounter"], []).append(s)
    out, i = [], 0
    while len(out) < n and any(by.values()):
        for enc in sorted(by):
            if by[enc] and len(out) < n:
                out.append(by[enc].pop(0))
        i += 1
    return out


def fight_rows(fi, s, two, ev):
    """One fight under the fallback two-turn player; one row per two-turn search."""
    c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"])
    rows, n, last_turn, idx = [], 0, None, 0
    while not c.is_over() and c.turn() <= TURN_LIMIT:
        turn = c.turn()
        idx = idx + 1 if turn == last_turn else 0
        last_turn = turn
        r1 = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)
        t = time.time()
        r2 = sts.search(c, ev.evaluator, features=ev.features, seed=(s["seed"] * 1009 + n) % 2**64, **two)
        ms = (time.time() - t) * 1000
        rows.append({"fight": fi, "encounter": s["encounter"], "turn": turn, "idx": idx, "nodes": r2["nodes"],
                     "leaves": r2["leaves"], "ms": ms, "cut": r2["cuts"] > 0})
        if r2["cuts"] > 0:
            pick_i = int(np.argmax([v for _, v in r1["options"]]))
        else:
            pick_i = int(np.argmax([v for _, v in r2["options"]]))
        c.step(r1["options"][pick_i][0][0])
        n += 1
    return rows


def play_decisions(s, two, ev, step):
    """One fight under the fallback two-turn player with the per-turn seed
    (stage 1), or stepping each uncut tree's line (`step`): one row per
    decision: action (as text), whether it was searched, the two-turn tree's
    cut flag, and the searches' nodes, leaves and wall ms (0 for stepped
    decisions)."""
    c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"])
    rows = []
    while not c.is_over() and c.turn() <= TURN_LIMIT:
        t = time.time()
        r1 = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)
        r2 = sts.search(c, ev.evaluator, features=ev.features, seed=(s["seed"] * 1009 + c.turn()) % 2**64, **two)
        ms = (time.time() - t) * 1000
        cut = r2["cuts"] > 0
        if cut:
            pick_i = int(np.argmax([v for _, v in r1["options"]]))
        else:
            pick_i = int(np.argmax([v for _, v in r2["options"]]))
        a = r1["options"][pick_i][0][0]
        rows.append({"action": str(a), "searched": True, "cut": cut, "nodes": r2["nodes"] + r1["nodes"],
                     "leaves": r2["leaves"] + r1["leaves"], "ms": ms})
        c.step(a)
        if step and not cut:
            for b in r2["line"][1:]:
                if c.is_over():
                    break
                rows.append({"action": str(b), "searched": False, "cut": False, "nodes": 0, "leaves": 0, "ms": 0.0})
                c.step(b)
    return rows, {"won": c.is_over() and c.won(), "hp_end": c.player_hp(), "turns": c.turn()}


def compare_fights(fights_rows):
    """`fights_rows`: per fight (stage-1 rows, stepping rows, outcomes). The
    agreement off cut decisions, the share of identical fights and the cost
    ratios (stepping / stage 1)."""
    agreed = compared = identical = 0
    tot = {"nodes": [0.0, 0.0], "leaves": [0.0, 0.0], "ms": [0.0, 0.0]}
    for base, step, _ in fights_rows:
        same = [r["action"] for r in base] == [r["action"] for r in step]
        identical += same
        for rb, rs in zip(base, step):
            if not rb["cut"]:
                compared += 1
                agreed += rb["action"] == rs["action"]
            if rb["action"] != rs["action"]:
                break
        for k in tot:
            tot[k][0] += sum(r[k] for r in base)
            tot[k][1] += sum(r[k] for r in step)
    return {"fights": len(fights_rows), "identical_share": identical / len(fights_rows) if fights_rows else None,
            "agreement": agreed / compared if compared else None, "compared": compared,
            "ratio": {k: (v[1] / v[0] if v[0] else None) for k, v in tot.items()},
            "totals": {k: {"stage1": v[0], "step": v[1]} for k, v in tot.items()},
            "decisions": {"stage1": sum(len(b) for b, _, _ in fights_rows),
                          "step": sum(len(s) for _, s, _ in fights_rows),
                          "searched_step": sum(sum(r["searched"] for r in s) for _, s, _ in fights_rows)}}


def compare(specs, two, ev, out, args):
    t = time.time()
    fights_rows = []
    for fi, s in enumerate(specs):
        base, ob = play_decisions(s, two, ev, False)
        step, os_ = play_decisions(s, two, ev, True)
        fights_rows.append((base, step, {"stage1": ob, "step": os_}))
        same = [r["action"] for r in base] == [r["action"] for r in step]
        print(f"  {fi + 1}/{len(specs)} {s['encounter']}: {len(base)} vs {len(step)} decisions, "
              f"{'identical' if same else 'DIFFER'}, {time.time() - t:.0f}s", flush=True)
    summary = compare_fights(fights_rows)
    r = summary["ratio"]
    print(f"fights {summary['fights']}, identical {summary['identical_share']:.3f}, "
          f"agreement off cut decisions {summary['agreement']:.4f} ({summary['compared']} compared)")
    print(f"cost ratio step / stage 1: nodes {r['nodes']:.3f}  leaves {r['leaves']:.3f}  ms {r['ms']:.3f}; "
          f"searches {summary['decisions']['searched_step']} of {summary['decisions']['step']} decisions")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"args": vars(args), "two": two, "wall_s": time.time() - t, "summary": summary,
                   "fights": [{"spec": s, "stage1": b, "step": st, "outcome": o}
                              for s, (b, st, o) in zip(specs, fights_rows)]}, f, indent=1)
    return summary


def summarize(rows):
    """Per-index rows and index-0 shares of a turn's nodes / leaves / ms."""
    by_idx = {}
    for r in rows:
        by_idx.setdefault(r["idx"], []).append(r)
    per_index = [{"idx": i, "n": len(q), "nodes": float(np.mean([r["nodes"] for r in q])),
                  "leaves": float(np.mean([r["leaves"] for r in q])), "ms": float(np.mean([r["ms"] for r in q])),
                  "cut_share": float(np.mean([r["cut"] for r in q]))} for i, q in sorted(by_idx.items())]
    tot = {k: float(sum(r[k] for r in rows)) for k in ("nodes", "leaves", "ms")}
    first = {k: float(sum(r[k] for r in rows if r["idx"] == 0)) for k in ("nodes", "leaves", "ms")}
    turns = {(r["fight"], r["turn"]) for r in rows}
    return {"searches": len(rows), "turns": len(turns),
            "decisions_per_turn": len(rows) / len(turns) if turns else None,
            "index0_share": {k: first[k] / tot[k] if tot[k] else None for k in tot},
            "per_index": per_index}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evaluator", required=True)
    ap.add_argument("--fights", type=int, default=20)
    ap.add_argument("--out", default=None)
    ap.add_argument("--compare", action="store_true",
                    help="stage-1 player vs the stepping player on each fight (docs/specs/line-step.md)")
    args = ap.parse_args()
    specs = pick(fights("held_out", ["elite", "boss"], 1), args.fights)
    two = {"limit": bench.LIMIT, **ladder.TWO_TURN}
    ev = bench.load_evaluator(args.evaluator)
    print(f"{len(specs)} fights; two-turn {two}", flush=True)
    if args.compare:
        compare(specs, two, ev, args.out or os.path.join("results", "depth", "line-step-compare.json"), args)
        return
    args.out = args.out or os.path.join("results", "depth", "line-probe.json")
    rows, t = [], time.time()
    for fi, s in enumerate(specs):
        rows += fight_rows(fi, s, two, ev)
        print(f"  {fi + 1}/{len(specs)} {s['encounter']}: {len(rows)} searches, {time.time() - t:.0f}s", flush=True)
    summary = summarize(rows)
    print(f"searches {summary['searches']}, turns {summary['turns']}, "
          f"decisions per turn {summary['decisions_per_turn']:.2f}")
    print(" idx    n     nodes    leaves      ms  cut")
    for p in summary["per_index"]:
        print(f" {p['idx']:3d} {p['n']:4d} {p['nodes']:9.0f} {p['leaves']:9.0f} {p['ms']:7.0f}  {p['cut_share']:.2f}")
    sh = summary["index0_share"]
    print(f"index-0 share: nodes {sh['nodes']:.3f}  leaves {sh['leaves']:.3f}  ms {sh['ms']:.3f}")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"args": vars(args), "two": two, "wall_s": time.time() - t, "summary": summary, "rows": rows},
                  f, indent=1)


if __name__ == "__main__":
    main()
