"""GSPRT replay (big-picture review 2026-11-01b, direction 6): would the
ladder's verdicts change under a trinomial generalised SPRT?

The ladder (`ladder.py`) scores each pair d = cand - champ in {-1, 0, +1}
and runs a normal-form SPRT (H0 mean 0, H1 mean D1) after MIN_FIGHTS pairs.
Its variance estimate is clamped at 1e-6, so a run of identical pairs (a
near-clone candidate: the HP bonus, any search-time constant) gives an LLR
of -5000 and an instant "fail". The trinomial GSPRT (as fishtest's, with
pairs instead of pentanomial game pairs) fits the three outcome shares
under each hypothesis by maximum likelihood with the mean held at mu0 or
mu1, and its LLR is n x sum p_hat log(p1 / p0). With few discordant pairs
it stays near 0 instead of deciding.

Replays every `results/ladder/tests/*.json` in its recorded pair order
(counted pairs only) with the ladder's bounds (ALPHA = BETA = 0.05, D1),
under three rules: the ladder's own (normal form, min 200 pairs), GSPRT
from pair 1, GSPRT plus a minimum count of discordant pairs; and, where the
test played fixed-n pairs after it stopped, the GSPRT carried on through
them (same fights in the same order) to see where it would stop. Then the
gauntlet c sweep: each c (and the bare net) against c = 0.01, per sequence
cleared difference in index order, H1 mean +0.04 (the sweep's
pre-registered bar), and the c = 0.01 champion against the heuristic over
both 500-sequence blocks (H1 +0.03).

    python scripts/analysis/gsprt_replay.py [--min-disc 30] [--out results/ladder/gsprt-replay.json]
"""

import argparse
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ladder  # noqa: E402

UPPER, LOWER = ladder.UPPER, ladder.LOWER
EPS = 1e-3  # pseudo-count per outcome, as fishtest regularises its GSPRT
X = (-1.0, 0.0, 1.0)


def mle(p_hat, mu):
    """Outcome shares closest in likelihood to `p_hat` with mean `mu`:
    p_i = p_hat_i / (1 + lam (x_i - mu)), lam found by bisection."""
    def f(lam):
        return sum(p * (x - mu) / (1 + lam * (x - mu)) for p, x in zip(p_hat, X))
    lo, hi = -1 / (1 - mu) + 1e-12, 1 / (1 + mu) - 1e-12  # keep every denominator positive
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    lam = (lo + hi) / 2
    return [p / (1 + lam * (x - mu)) for p, x in zip(p_hat, X)]


def gsprt_llr(counts, mu0, mu1):
    n = sum(counts)
    c = [k + EPS for k in counts]
    p_hat = [k / sum(c) for k in c]
    p0, p1 = mle(p_hat, mu0), mle(p_hat, mu1)
    return n * sum(p * math.log(a / b) for p, a, b in zip(p_hat, p1, p0))


def run_gsprt(ds, mu1, min_n=0, min_disc=0, mu0=0.0, cap=None):
    """("pass" | "fail" | None, pairs used, llr) for outcomes `ds` in order."""
    counts = [0, 0, 0]
    v = 0.0
    for n, d in enumerate(ds, 1):
        counts[int(d) + 1] += 1
        if n >= min_n and counts[0] + counts[2] >= min_disc:
            v = gsprt_llr(counts, mu0, mu1)
            if v >= UPPER:
                return "pass", n, v
            if v <= LOWER:
                return "fail", n, v
        if cap and n >= cap:
            return "cap", n, v
    return None, len(ds), v


def ladder_tests(min_disc):
    rows = []
    for f in sorted(glob.glob(os.path.join(ladder.ROOT, "tests", "*.json"))):
        t = json.load(open(f, encoding="utf-8"))
        d1 = t.get("d1", ladder.D1)
        ds = [p["cand"] - p["champ"] for p in t["pairs_played"] if p.get("counted")]
        more = ds + [p["cand"] - p["champ"] for p in t["pairs_played"] if not p.get("counted")]  # fixed-n pairs played after the stop, same order
        normal, (n, s, _) = ladder.decide(ds, d1)
        rows.append({
            "id": t["id"], "candidate": t["candidate"], "recorded": t["verdict"], "recorded_pairs": t["pairs"],
            "replayed_normal": [normal, n], "discordant": sum(d != 0 for d in ds), "lead": sum(ds) / len(ds),
            "gsprt": list(run_gsprt(ds, d1)[:2]),
            "gsprt_min200": list(run_gsprt(ds, d1, min_n=ladder.MIN_FIGHTS)[:2]),
            "gsprt_disc": list(run_gsprt(ds, d1, min_disc=min_disc)[:2]),
            "pairs_available": len(more),
            "gsprt_on": list(run_gsprt(more, d1, min_disc=min_disc, cap=ladder.CAP)[:2]),
        })
    return rows


def gauntlet_pairs(a_paths, b_paths):
    ra, rb = {}, {}
    for p in a_paths:
        ra.update({r["i"]: r["cleared"] for r in json.load(open(p))["sequences"]})
    for p in b_paths:
        rb.update({r["i"]: r["cleared"] for r in json.load(open(p))["sequences"]})
    return [int(ra[i]) - int(rb[i]) for i in sorted(set(ra) & set(rb))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-disc", type=int, default=30)
    ap.add_argument("--out", default=os.path.join(ladder.ROOT, "gsprt-replay.json"))
    a = ap.parse_args()
    rows = ladder_tests(a.min_disc)
    for r in rows:
        print(f"{r['id']} rec {r['recorded']:>5} @{r['recorded_pairs']:>5}  disc {r['discordant']:>3}  lead {r['lead']:+.4f}  "
              f"normal {r['replayed_normal']}  gsprt {r['gsprt']}  gsprt disc>={a.min_disc} {r['gsprt_disc']}  "
              f"on to {r['pairs_available']}: {r['gsprt_on']}")
    g = os.path.join(ladder.ROOT, "..", "gauntlet")
    ref = glob.glob(os.path.join(g, "*-hpb0.01-bd6d62.json"))
    gaunt = []
    for name, pat in [("bare", "*s1-9f89b6f-4bf8ef.json"), ("c0.005", "*hpb0.005-*.json"), ("c0.02", "*hpb0.02-*.json"),
                      ("c0.04", "*hpb0.04-*.json")]:
        ds = gauntlet_pairs(glob.glob(os.path.join(g, pat)), ref)
        v = run_gsprt(ds, 0.04)
        gaunt.append({"cand": name, "vs": "c0.01", "mu1": 0.04, "n": len(ds), "discordant": sum(d != 0 for d in ds),
                      "lead": sum(ds) / len(ds), "gsprt": list(v[:2])})
    ds = gauntlet_pairs(ref + glob.glob(os.path.join(g, "champion-hpb0.01-b500.json")),
                        glob.glob(os.path.join(g, "heuristic-bcbb0e.json")) + glob.glob(os.path.join(g, "heuristic-b500.json")))
    gaunt.append({"cand": "c0.01", "vs": "heuristic", "mu1": 0.03, "n": len(ds), "discordant": sum(d != 0 for d in ds),
                  "lead": sum(ds) / len(ds), "gsprt": list(run_gsprt(ds, 0.03)[:2])})
    for r in gaunt:
        print(f"gauntlet {r['cand']} vs {r['vs']} (H1 +{r['mu1']}): n {r['n']} disc {r['discordant']} lead {r['lead']:+.3f}  gsprt {r['gsprt']}")
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"min_disc": a.min_disc, "ladder": rows, "gauntlet": gaunt}, f, indent=1)


if __name__ == "__main__":
    main()
