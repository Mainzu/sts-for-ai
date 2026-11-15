"""Gauntlet promotion protocol replay (big-picture review 2026-11-02, rank 2):
would a sequential test on paired end-HP, with a clears guard, reach the
same verdicts as fixed-n clears on the gauntlet files we have?

End-HP of a sequence is the boss floor's HP left if it cleared, else 0.
For a pair of files (A = candidate, B = control) sharing sequences, d_i =
endHP_A - endHP_B in sequence index order. A normal SPRT (H0 mean 0, H1
mean +D1 HP, variance re-estimated each step, ALPHA = BETA = 0.05, first
look after MIN_N sequences) passes or fails A; at the stop, the clears
guard fails a pass whose paired clears difference so far has z <= -2.
Fixed-n verdict for comparison: clears over all shared sequences, "better"
at z >= 2, "worse" at z <= -2, else "level".

    python scripts/analysis/gauntlet_protocol.py [--d1 1.5] [--min-n 50]
"""

import argparse
import glob
import itertools
import json
import math
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "results", "gauntlet")
ALPHA = BETA = 0.05
UPPER, LOWER = math.log((1 - BETA) / ALPHA), math.log(BETA / (1 - ALPHA))


def load(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    rows = {r["i"]: r for r in d["sequences"]}
    return d["settings"], rows


def end_hp(r):
    return r["floors"][-1]["hp_end"] if r["cleared"] else 0


def z(ds):
    n = len(ds)
    m = sum(ds) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in ds) / (n - 1)) if n > 1 else 0.0
    return m, (m / (sd / math.sqrt(n)) if sd > 0 else 0.0)


def sprt(dh, dc, d1, min_n):
    """(verdict, n at stop) for end-HP differences dh with clears guard dc."""
    for n in range(min_n, len(dh) + 1):
        xs = dh[:n]
        m = sum(xs) / n
        var = max(sum((x - m) ** 2 for x in xs) / (n - 1), 1e-6)
        llr = n * d1 / var * (m - d1 / 2)
        if llr >= UPPER:
            return ("fail-guard" if z(dc[:n])[1] <= -2 else "pass"), n
        if llr <= LOWER:
            return "fail", n
    return "open", len(dh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d1", type=float, default=1.5)
    ap.add_argument("--min-n", type=int, default=50)
    a = ap.parse_args()
    files = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "*.json"))):
        s, rows = load(p)
        files[os.path.basename(p)] = (s, rows)
    print(f"H1 +{a.d1} HP, alpha = beta = {ALPHA}, first look at {a.min_n}")
    print(f"{'A (candidate)':44} {'B (control)':44} {'n':>4} {'clears':>7} {'z':>5} {'endHP':>6} {'z':>5}  fixed-n  sprt (n)")
    agree = total = 0
    for (na, (sa, ra)), (nb, (sb, rb)) in itertools.permutations(files.items(), 2):
        if sa["seed"] != sb["seed"] or sa["shape"] != sb["shape"]:
            continue
        keys = sorted(k for k in set(ra) & set(rb) if ra[k]["cell"] == rb[k]["cell"])
        if len(keys) < 200:
            continue
        dc = [float(ra[k]["cleared"]) - float(rb[k]["cleared"]) for k in keys]
        dh = [end_hp(ra[k]) - end_hp(rb[k]) for k in keys]
        mc, zc = z(dc)
        mh, zh = z(dh)
        if mc < 0 and mh < 0:
            continue  # each pair once, with A the better-by-clears side or the mixed case
        fixed = "better" if zc >= 2 else ("worse" if zc <= -2 else "level")
        v, n = sprt(dh, dc, a.d1, a.min_n)
        ok = (fixed == "better") == (v == "pass")
        agree += ok
        total += 1
        print(f"{na[:44]:44} {nb[:44]:44} {len(keys):4} {mc:+7.3f} {zc:5.1f} {mh:+6.2f} {zh:5.1f}  {fixed:7}  {v} ({n}){'' if ok else '  <- differs'}")
    print(f"verdicts agree (pass <-> fixed-n better): {agree} / {total}")


if __name__ == "__main__":
    main()
