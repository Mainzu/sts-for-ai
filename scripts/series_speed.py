"""Rules-engine series speed check (docs/specs/rules-engine-upgrade.md,
"Speed checks"): H1 (`bench`) and H2 (`search_speed`) from two builds, run
interleaved so background load hits both alike, with the order swapped on
every other run (old-new, new-old, ...) so a position effect (the run after
an all-thread search is slower on the dev machine) cancels instead of landing on
one build; medians and the median of per-run new/old ratios compared.

    python scripts/series_speed.py <old dir> <new dir> [runs=5] [h1|h2|both]

Each dir holds `bench.exe` and `search_speed.exe` (copied out of
target/release/examples so later builds can't change them).
"""

import os
import re
import statistics
import subprocess
import sys

H1 = [("random combats/min", re.compile(r"= (\d+) per minute")), ("clone ns", re.compile(r"clone[^0-9]*([\d.]+) ns"))]
H2 = [(f"search {t} thr games/s", re.compile(rf"^\s*{t} threads:\s+([\d.]+) games/s", re.M)) for t in (1, 16)]


def run(exe, pats):
    out = subprocess.run([exe], capture_output=True, text=True, check=True).stdout
    vals = {}
    for name, rx in pats:
        m = rx.search(out)
        vals[name] = float(m.group(1)) if m else None
    return vals, out


def main(old, new, runs=5, which="both"):
    jobs = []
    if which in ("h1", "both"):
        jobs.append(("bench.exe", H1))
    if which in ("h2", "both"):
        jobs.append(("search_speed.exe", H2))
    res = {d: {} for d in (old, new)}
    for i in range(runs):
        for exe, pats in jobs:
            for d in ((old, new) if i % 2 == 0 else (new, old)):
                vals, out = run(os.path.join(d, exe), pats)
                for k, v in vals.items():
                    res[d].setdefault(k, []).append(v)
                print(f"run {i + 1} {os.path.basename(d.rstrip('/'))} {exe}: {vals}", flush=True)
    print()
    for k in res[old]:
        a = [x for x in res[old][k] if x is not None]
        b = [x for x in res[new][k] if x is not None]
        if not a or not b:
            print(f"{k}: not parsed")
            continue
        ma, mb = statistics.median(a), statistics.median(b)
        lower_better = k.endswith("ns")
        change = (ma / mb - 1) if lower_better else (mb / ma - 1)
        pairs = [(x, y) for x, y in zip(res[old][k], res[new][k]) if x is not None and y is not None]
        ratio = statistics.median((x / y) if lower_better else (y / x) for x, y in pairs) - 1
        print(f"{k}: old {ma:.1f} new {mb:.1f} -> {change:+.1%} {'(faster)' if change >= 0 else '(slower)'};"
              f" per-run ratio median {ratio:+.1%}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    main(a[0], a[1], int(a[2]) if len(a) > 2 else 5, a[3] if len(a) > 3 else "both")
