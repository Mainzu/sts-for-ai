"""Go check for a candidate's gauntlet reads (a job's --check): paired end-HP
(gauntlet_protocol.end_hp) of candidate against control files, by sequence
index, over the sequences both hold with the same cell.

`--gain A B` passes when mean(A - B) / se >= --z (default 2).
`--keep A B` passes when mean(A - B) >= -(--drop) HP (default 1.5).
`--gain-pooled B A1 A2 ...` and `--keep-pooled B A1 A2 ...` pool seeds: per
sequence, the mean of A1, A2, ... minus B, over the sequences all hold with
the same cell; the same pass rules.
Every pair given must pass; exit 0 on a pass, 1 on a fail. Prints each
pair's n, mean end-HP difference, se, z and clears difference.

    python scripts/analysis/paired_go.py --gain cand.json ctrl.json --keep cand-cells.json ctrl-cells.json
"""

import argparse
import math
import sys

import gauntlet_protocol as gp


def paired(a, b):
    """a: a candidate file or a list of seed files pooled per sequence."""
    ras = [gp.load(x)[1] for x in ([a] if isinstance(a, str) else a)]
    _, rb = gp.load(b)
    ks = sorted(k for k in rb if all(k in ra and ra[k]["cell"] == rb[k]["cell"] for ra in ras))
    dh = [sum(gp.end_hp(ra[k]) for ra in ras) / len(ras) - gp.end_hp(rb[k]) for k in ks]
    dc = [sum(float(ra[k]["cleared"]) for ra in ras) / len(ras) - float(rb[k]["cleared"])
          for k in ks]
    n = len(dh)
    m = sum(dh) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in dh) / (n - 1))
    se = sd / math.sqrt(n)
    return n, m, se, (m / se if se > 0 else 0.0), sum(dc) / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gain", nargs=2, action="append", default=[])
    ap.add_argument("--keep", nargs=2, action="append", default=[])
    ap.add_argument("--gain-pooled", nargs="+", action="append", default=[],
                    metavar="FILE", help="control, then two or more seed files")
    ap.add_argument("--keep-pooled", nargs="+", action="append", default=[],
                    metavar="FILE", help="control, then two or more seed files")
    ap.add_argument("--z", type=float, default=2.0)
    ap.add_argument("--drop", type=float, default=1.5)
    args = ap.parse_args()
    for lst in args.gain_pooled + args.keep_pooled:
        if len(lst) < 3:
            ap.error("a pooled pair needs a control and at least two seed files")
    ok = True
    for kind, pairs in (("gain", args.gain), ("keep", args.keep),
                        ("gain", [(l[1:], l[0]) for l in args.gain_pooled]),
                        ("keep", [(l[1:], l[0]) for l in args.keep_pooled])):
        for a, b in pairs:
            n, m, se, z, dc = paired(a, b)
            good = z >= args.z if kind == "gain" else m >= -args.drop
            ok &= good
            name = a if isinstance(a, str) else "mean(" + ", ".join(a) + ")"
            print(f"{kind} {'pass' if good else 'FAIL'}: {name} vs {b}: n {n}, end-HP {m:+.2f} "
                  f"(se {se:.2f}, z {z:+.2f}), clears {dc:+.3f}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
