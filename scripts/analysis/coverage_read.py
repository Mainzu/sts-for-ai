"""Coverage pilot read (Next 6): each arm's r1 lead over the heuristic on
tight2, per half x fight type, mean and seed sd over seeds, with the lean
arm's r1 nets (full pool, 20k, shared round 0) beside them. Arms can be
given as arguments (e.g. data5k data20k data40k)."""
import glob
import json
import sys

import numpy as np

from novelty import novelty_slices  # noqa: E402

T = json.load(open("data/bench/tight2.json", encoding="utf-8"))["halves"]
SEEDS = ("s1", "s101", "s201", "s301", "s401")
ARMS = tuple(sys.argv[1:]) or ("cover4", "cover10", "cover21", "lean")


def bits(s):
    return np.array([c == "1" for c in s], float)


def runs(name):
    out = []
    for s in SEEDS:
        g = glob.glob(f"runs/2026-1*-{name}-{s}-r1-*/round.json")
        if not g:
            continue
        d = json.load(open(g[0]))["tight_results"]
        out.append({h: (bits(d["net"][h]), bits(d["heuristic"][h])) for h in T})
    return out


def slices(h):
    sp = T[h]
    out = {"all": np.ones(len(sp), bool)}
    for g in ("hallway", "elite", "boss"):
        out[g] = np.array([s["group"] == g for s in sp])
    if h == "held_out":
        out.update(novelty_slices(sp))
    return out


def main():
    arms = {a: runs(a) for a in ARMS}
    print("seeds per arm:", {a: len(r) for a, r in arms.items()})
    for h in T:
        print(f"== {h}")
        for k, m in slices(h).items():
            row = [f"{k:8s} n{int(m.sum()):5d}"]
            for name, rs in arms.items():
                leads = [float((n[m] - b[m]).mean()) for r in rs for n, b in [r[h]]]
                sd = np.std(leads, ddof=1) if len(leads) > 1 else float("nan")
                row.append(f"{name} {np.mean(leads):+.3f} (sd {sd:.3f}) [{' '.join(f'{x:+.3f}' for x in leads)}]")
            print("  " + " | ".join(row))


if __name__ == "__main__":
    main()
