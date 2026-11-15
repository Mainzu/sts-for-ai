"""Lean loop read (Next 5): each arm's r2 lead over the heuristic on tight2,
per half x fight type, averaged over seeds, against the seed check's r2
nets (same fights); and lowhp vs lean on fights starting at 1-8 HP.
More arms by run name as arguments: `lean_read.py lean-thr`. Each
arm's leads are also printed paired against lean, seed by seed."""
import glob
import json
import sys

import numpy as np

from novelty import novelty_slices  # noqa: E402

T = json.load(open("data/bench/tight2.json", encoding="utf-8"))["halves"]
SEEDS = ("s1", "s101", "s201")


def bits(s):
    return np.array([c == "1" for c in s], float)


def heur():
    d = json.load(open(glob.glob("runs/2026-10-30-lean-s1-r2-*/round.json")[0]))
    return {h: bits(d["tight_results"]["heuristic"][h]) for h in T}


def arm(name):
    out = []
    for s in SEEDS:
        d = json.load(open(sorted(glob.glob(f"runs/2026-1*-{name}-{s}-r2-*/round.json"))[-1]))
        out.append({h: bits(d["tight_results"]["net"][h]) for h in T})
    return out


def seed_check():
    c = json.load(open("runs/seed-check/check.json"))["rounds"]["2"]["seeds"]
    return [{h: bits(v["fights"][h]) for h in T} for v in c.values()]


def slices(h):
    sp = T[h]
    out = {"all": np.ones(len(sp), bool)}
    for g in ("hallway", "elite", "boss"):
        out[g] = np.array([s["group"] == g for s in sp])
    out["hp<=8"] = np.array([(s["hp"] or 99) <= 8 for s in sp])
    if h == "held_out":
        out.update(novelty_slices(sp))
    return out


def main():
    H = heur()
    extra = sys.argv[1:]  # more arms by run name, e.g. lean-thr lean-look
    arms = {"seedcheck-r2": seed_check(), "lean": arm("lean"), "lean-lowhp": arm("lean-lowhp"),
            **{a: arm(a) for a in extra}}
    for h in T:
        print(f"== {h}")
        for k, m in slices(h).items():
            row = [f"{k:8s} n{int(m.sum()):5d}"]
            for name, runs in arms.items():
                leads = [float((r[h][m] - H[h][m]).mean()) for r in runs]
                row.append(f"{name} {np.mean(leads):+.3f} (sd {np.std(leads, ddof=1):.3f})")
                if name in extra:
                    d = [float((r[h][m] - b[h][m]).mean()) for r, b in zip(runs, arms["lean"])]
                    row.append(f"{name}-lean {np.mean(d):+.3f} [{' '.join(f'{x:+.3f}' for x in d)}]")
            print("  " + " | ".join(row))


if __name__ == "__main__":
    main()
