"""Exit 0 when two registry runs trained alike: the same number of epochs
and train and validation curves equal within --tol (curves.json). Each run
is a path or a glob under runs/ (the newest match is taken).

    python scripts/analysis/curves_equal.py runs/2026-11-07-ycards-heur-g400-s1-1dd4e45 "runs/*-ycards-heur-g400-s1-memcheck-*"
"""

import argparse
import glob
import json
import os
import sys


def curves(pattern):
    paths = sorted(glob.glob(pattern), key=os.path.getmtime)
    if not paths:
        sys.exit(f"no run matches {pattern}")
    with open(os.path.join(paths[-1], "curves.json"), encoding="utf-8") as f:
        return paths[-1], json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--tol", type=float, default=1e-6)
    args = ap.parse_args(argv)
    (pa, a), (pb, b) = curves(args.a), curves(args.b)
    worst = 0.0
    for k in ("train", "val"):
        if len(a[k]) != len(b[k]):
            print(f"{k}: {len(a[k])} epochs in {pa}, {len(b[k])} in {pb}")
            return 1
        worst = max([worst] + [abs(x - y) for x, y in zip(a[k], b[k])])
    print(f"{pa} vs {pb}: {len(a['val'])} epochs, largest curve difference {worst:.3g}")
    return 0 if worst <= args.tol else 1


if __name__ == "__main__":
    sys.exit(main())
