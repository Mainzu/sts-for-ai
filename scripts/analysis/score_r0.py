"""Round-0 nets on tight2 (big-picture review 2026-10-31, Next A): play each
round-0 net's tight fights (`learn.tight_results`, the same call round.json
uses) and save them to results/r0-scores/<run>.json; `--read` prints each
r0 next to its r1 (same name with r1) and the heuristic, per half x fight
type, as leads over the heuristic averaged over the runs of each arm.

    python scripts/analysis/score_r0.py play runs/2026-10-30-cover*-r0-*
    python scripts/analysis/score_r0.py read cover4 cover10 cover21
"""
import glob
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
OUT = "results/r0-scores"
T = json.load(open("data/bench/tight2.json", encoding="utf-8"))["halves"]


def play(dirs):
    import bench
    import learn
    os.makedirs(OUT, exist_ok=True)
    for d in dirs:
        rid = os.path.basename(d.rstrip("/\\"))
        out = os.path.join(OUT, rid + ".json")
        if os.path.exists(out):
            print("have", rid)
            continue
        res = learn.tight_results(os.path.join(d, "model.pt"), {"limit": bench.LIMIT}, 1, print)
        json.dump({"run": rid, "fights": {h: "".join(map(str, x)) for h, x in res.items()}}, open(out, "w"))
        print("saved", rid, {h: round(float(np.mean(x)), 3) for h, x in res.items()})


def bits(s):
    return np.array([c == "1" for c in s], float)


def read(arms):
    for arm in arms:
        rows = []
        for f in sorted(glob.glob(os.path.join(OUT, f"*-{arm}-s*-r0-*.json"))):
            r0 = json.load(open(f))
            m = re.match(rf"(.*-{re.escape(arm)}-s\d+)-r0-", r0["run"])
            name = m.group(1).split("-", 3)[3]  # drop the date
            r1 = glob.glob(f"runs/*-{name}-r1-*/round.json")
            if not r1:
                continue
            d = json.load(open(r1[0]))["tight_results"]
            rows.append({h: (bits(r0["fights"][h]), bits(d["net"][h]), bits(d["heuristic"][h])) for h in T})
        print(f"== {arm}: {len(rows)} runs (r0 lead | r1 lead | r1 - r0, mean over runs)")
        for h in T:
            for k in ("all", "hallway", "elite", "boss"):
                m = np.ones(len(T[h]), bool) if k == "all" else np.array([s["group"] == k for s in T[h]])
                a = [float((r[h][0][m] - r[h][2][m]).mean()) for r in rows]
                b = [float((r[h][1][m] - r[h][2][m]).mean()) for r in rows]
                print(f"  {h:8s} {k:8s} r0 {np.mean(a):+.3f} | r1 {np.mean(b):+.3f} | r1-r0 {np.mean(b) - np.mean(a):+.3f}"
                      f"  [{' '.join(f'{y - x:+.3f}' for x, y in zip(a, b))}]")


if __name__ == "__main__":
    (play if sys.argv[1] == "play" else read)(sys.argv[2:])
