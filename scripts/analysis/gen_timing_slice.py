"""Slice a generated-power depth read (`gen_powers_read.py depth`) by when the
swapped test card's power fires (results doc "Novelty cost sits past the
one-turn horizon"): turn start / card played / turn end / lost HP. For each
class: generated twin minus original, per cell and per card, of the net's
depth gain (two-turn minus one-turn) and, with a heuristic read of the same
fights, of net minus heuristic.

    .venv/Scripts/python scripts/analysis/gen_timing_slice.py <net depth json> [<heuristic depth json>]
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import gen_powers_read as g  # noqa: E402

CLASSES = ("turn_start", "card_played", "turn_end", "lost_hp")


def klass(f):
    t = " ".join(f["triggers"])
    if "OwnerTurnStart" in t:
        return "turn_start"
    if "CardPlayed" in t:
        return "card_played"
    if "OwnerTurnEnd" in t:
        return "turn_end"
    return "lost_hp"


def se(x):
    return float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else float("nan")


def main():
    net = json.load(open(sys.argv[1], encoding="utf-8"))
    heu = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else None
    _, fights = g.load_bench(net["bench"])
    sub = [fights[i] for i in net["idx"]]
    gen = {f["cell"]: f for f in sub if f["set"] == "generated"}

    def per_cell(vals):
        d = {}
        for f, v in zip(sub, vals):
            d.setdefault(f["cell"], {}).setdefault(f["set"], []).append(v)
        return {c: np.mean(v["generated"]) - np.mean(v["original"]) for c, v in d.items()}

    series = {"net depth gain": [w - o for w, o in zip(net["two"], net["one"])]}
    if heu:
        assert heu["idx"] == net["idx"], "heuristic read is on other fights"
        series["heur depth gain"] = [w - o for w, o in zip(heu["two"], heu["one"])]
        series["net-heur one-turn"] = [a - h for a, h in zip(net["one"], heu["one"])]
        series["net-heur two-turn"] = [a - h for a, h in zip(net["two"], heu["two"])]
    out = {}
    for name, vals in series.items():
        pc = per_cell(vals)
        out[name] = {}
        print(f"\n{name}, generated minus original:")
        for k in CLASSES:
            cells = [c for c in pc if klass(gen[c]) == k]
            v = np.array([pc[c] for c in cells])
            by_card = {}
            for c in cells:
                by_card.setdefault(gen[c]["gen_card"], []).append(pc[c])
            cv = np.array([np.mean(x) for x in by_card.values()])
            out[name][k] = {"cells": len(cells), "mean": float(v.mean()), "se": se(v),
                            "cards": len(cv), "card_mean": float(cv.mean()), "card_se": se(cv)}
            print(f"  {k:12s} cells {len(cells):3d} {v.mean():+.3f} (se {se(v):.3f})   "
                  f"cards {len(cv):2d} {cv.mean():+.3f} (se {se(cv):.3f})")
        a, c = out[name]["turn_start"], out[name]["card_played"]
        out[name]["ts_minus_cp"] = {"cell": a["mean"] - c["mean"], "cell_se": float(np.hypot(a["se"], c["se"])),
                                    "card": a["card_mean"] - c["card_mean"],
                                    "card_se": float(np.hypot(a["card_se"], c["card_se"]))}
        r = out[name]["ts_minus_cp"]
        print(f"  turn start - card played: cells {r['cell']:+.3f} (se {r['cell_se']:.3f}), "
              f"cards {r['card']:+.3f} (se {r['card_se']:.3f})")
    dst = os.path.splitext(sys.argv[1])[0] + "-timing.json"
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
