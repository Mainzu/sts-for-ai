"""Skeptic's re-derivation of sprt_replay.py's headline numbers.

Written independently of sprt_replay.py (own loaders, own SPRT loop).
Checks:
  1. data alignment: heuristic bits identical in both check files, rung4
     arm A == seed-check round 10, every bit string the length of its half;
  2. per-pair lead on each tight2 half with a 95% interval over cells, and
     discordance (share of pairs that differ);
  3. the SPRT replay on same-recipe tight2 pairs (decide on train, check
     on held-out), H1 0.01 / 0.02, fights drawn singly, plus the same with
     a different test (Bernoulli SPRT on the discordant pairs only, i.e. a
     sequential sign test) to see whether the stop times depend on the
     variance plug-in;
  4. the seed-to-seed sd of one net's tight2 lead, two ways, with a rough
     interval;
  5. net-vs-heuristic leads on each half; warm-start silent_a / silent_b.
Writes scripts/analysis/out/check_sprt.txt. Single-threaded, numpy only.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import glob
import itertools
import json
import math
import sys

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
A = B = 0.05
UP, LO = math.log((1 - B) / A), math.log(B / (1 - A))
lines = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    lines.append(s)


def J(p):
    with open(os.path.join(ROOT, p)) as f:
        return json.load(f)


def b(s):
    return np.array([int(ch) for ch in s], dtype=np.int64) if isinstance(s, str) else np.array(s, dtype=np.int64)


def ci_cells(d, cell):
    """mean of cell means, 95% t-ish (normal) interval over cells."""
    keys = np.unique(cell)
    m = np.array([d[cell == k].mean() for k in keys])
    se = m.std(ddof=1) / math.sqrt(len(m))
    return m.mean(), m.mean() - 1.96 * se, m.mean() + 1.96 * se


# ---- 1. data -----------------------------------------------------------
t2 = J("data/bench/tight2.json")["halves"]
cell = {"train": np.array([s["cell"] for s in t2["train"]]), "held": np.array([s["cell"] for s in t2["held_out"]])}
sc, r4 = J("runs/seed-check/check.json"), J("runs/rung4-nightdb/check.json")
say("heuristic bits identical in both files:", sc["heuristic_fights"] == r4["heuristic_fights"])
say("rung4 A == seed-check r10 (all seeds):",
    all(sc["rounds"]["10"]["seeds"][s]["fights"] == r4["seeds"][s]["fights"]["A"] for s in ("1", "101", "201")))
W = {"heur": {"train": b(sc["heuristic_fights"]["train"]), "held": b(sc["heuristic_fights"]["held_out"])}}
fam = {}
for r, rnd in sc["rounds"].items():
    for s, rec in rnd["seeds"].items():
        W[f"r{r}_s{s}"] = {"train": b(rec["fights"]["train"]), "held": b(rec["fights"]["held_out"])}
        fam.setdefault(f"r{r}", []).append(f"r{r}_s{s}")
for s, rec in r4["seeds"].items():
    W[f"B_s{s}"] = {"train": b(rec["fights"]["B"]["train"]), "held": b(rec["fights"]["B"]["held_out"])}
    fam.setdefault("B", []).append(f"B_s{s}")
for n, h in W.items():
    for k in ("train", "held"):
        assert len(h[k]) == len(cell[k]), (n, k)
say("cells:", len(np.unique(cell["train"])), "train,", len(np.unique(cell["held"])), "held; fights",
    len(cell["train"]), "+", len(cell["held"]), "=", len(cell["train"]) + len(cell["held"]))

# ---- 2. same-recipe pairs ---------------------------------------------
SR = [(a, c) for f in sorted(fam) for a, c in itertools.combinations(sorted(fam[f]), 2)]
say(f"\n== same-recipe pairs ({len(SR)}): lead train | held (95% over cells), discordance on train ==")
disc = []
for a, c in SR:
    dt = W[a]["train"] - W[c]["train"]
    dh = W[a]["held"] - W[c]["held"]
    lt, lh = ci_cells(dt, cell["train"]), ci_cells(dh, cell["held"])
    disc.append(np.mean(dt != 0))
    say(f"{a:>8} vs {c:<8} {lt[0]:+.4f} [{lt[1]:+.4f},{lt[2]:+.4f}] | {lh[0]:+.4f} [{lh[1]:+.4f},{lh[2]:+.4f}]  disc {disc[-1]:.3f}")
say(f"discordance median {np.median(disc):.3f} range {min(disc):.3f}-{max(disc):.3f}")


# ---- 3. SPRT replays ---------------------------------------------------
def sprt_normal(x, d1, nmin=200):
    """run one path; return (decision, n)."""
    S = Q = 0.0
    for i, v in enumerate(x, 1):
        S += v
        Q += v * v
        if i < nmin:
            continue
        m = S / i
        var = max(Q / i - m * m, 1e-6)
        llr = i * d1 / var * (m - d1 / 2)
        if llr >= UP:
            return 1, i
        if llr <= LO:
            return -1, i
    return 0, len(x)


def sprt_sign(x, d1, disc_prior):
    """Bernoulli SPRT on discordant pairs: p = P(+1 | discordant); H0 p=.5,
    H1 p = .5 + d1 / (2 * disc_prior). Returns (decision, fights used)."""
    p1 = 0.5 + d1 / (2 * disc_prior)
    wp, wm = math.log(p1 / 0.5), math.log((1 - p1) / 0.5)
    llr = 0.0
    for i, v in enumerate(x, 1):
        if v > 0:
            llr += wp
        elif v < 0:
            llr += wm
        if llr >= UP:
            return 1, i
        if llr <= LO:
            return -1, i
    return 0, len(x)


rng = np.random.default_rng(777)
SH = 60
say(f"\n== SPRT replay on same-recipe pairs, train half, fights drawn singly, {SH} shuffles, cap = whole half ==")
for d1 in (0.01, 0.02):
    tot_pass = rep = con = 0
    either = []
    meds, meds_sign, meds_cand = [], [], []
    per_pair = []
    for a, c in SR:
        dt = (W[a]["train"] - W[c]["train"]).astype(float)
        lh = ci_cells((W[a]["held"] - W[c]["held"]).astype(float), cell["held"])
        dprior = float(np.mean(dt != 0))
        stops = {1: [], -1: []}
        stops_s = []
        npass = {1: 0, -1: 0}
        ei = 0
        for _ in range(SH):
            x = dt[rng.permutation(len(dt))]
            got = False
            for sg in (1, -1):
                dec, n = sprt_normal(sg * x, d1)
                stops[sg].append(n)
                if dec == 1:
                    npass[sg] += 1
                    got = True
            ei += got
            stops_s.append(sprt_sign(x, d1, dprior)[1])
        either.append(ei / SH)
        for sg in (1, -1):
            if npass[sg]:
                tot_pass += npass[sg]
                rep += npass[sg] * (sg * lh[0] > 0)
                con += npass[sg] * (min(sg * lh[1], sg * lh[2]) > 0)
            meds.append(np.median(stops[sg]))
        meds_sign.append(np.median(stops_s))
        per_pair.append((a, c, npass[1] / SH, npass[-1] / SH, lh[0], lh[1], lh[2]))
    say(f"H1 {d1}: either side passes {np.mean(either):.3f}; passes {tot_pass}, held-out lead same sign {rep / tot_pass:.3f}, "
        f"held-out CI above 0 {con / tot_pass:.3f}; mean over pair-orientations of median stop {np.mean(meds):.0f} "
        f"(range {min(meds):.0f}-{max(meds):.0f}); sign-test SPRT median stop mean {np.mean(meds_sign):.0f}")
    strong = [p for p in per_pair if max(p[2], p[3]) >= 0.5]
    say(f"   pairs passing in >= half the shuffles: {len(strong)}; their held-out CI excludes 0 in the winner's favour: "
        f"{sum(1 for p in strong if (p[5] > 0 if p[2] >= p[3] else p[6] < 0))}")
    for p in per_pair:
        say(f"   {p[0]:>8} vs {p[1]:<8} pass a {p[2]:.2f} b {p[3]:.2f}  held {p[4]:+.4f} [{p[5]:+.4f},{p[6]:+.4f}]")

say(f"\ncost ratio: 24,520 / 2,945 = {24520 / 2945:.1f}; train-half-only gate 12,320 / 2,945 = {12320 / 2945:.1f}")

# ---- 4. seed-to-seed sd ------------------------------------------------
say("\n== seed-to-seed sd of one net's tight2 lead (both halves pooled, 1,226 cells) ==")
call = np.concatenate([cell["train"], cell["held"] + 100000])
ests = []
for f in sorted(fam):
    nets = sorted(fam[f])
    leads, noises = [], []
    for a, c in itertools.combinations(nets, 2):
        d = np.concatenate([W[a]["train"] - W[c]["train"], W[a]["held"] - W[c]["held"]]).astype(float)
        m, lo, hi = ci_cells(d, call)
        leads.append(m)
        noises.append(((hi - lo) / (2 * 1.96)) ** 2)
    # 3 nets: mean of squared pair diffs = 2 * s^2 (ddof 1) of net values
    s2 = (np.mean(np.square(leads)) - np.mean(noises)) / 2
    ests.append(s2)
    say(f"{f}: pair leads {[round(x, 4) for x in leads]}, seed var {s2:.2e} (sd {math.sqrt(max(s2, 0)):.4f})")
s2 = float(np.mean(ests))
dfree = 2 * len(ests)
# rough chi-square interval, ignoring noise-subtraction uncertainty
lo_, hi_ = s2 * dfree / 20.48, s2 * dfree / 3.25   # chi2_10 0.975 / 0.025 quantiles
say(f"pooled seed sd {math.sqrt(s2):.4f}, rough 95% [{math.sqrt(lo_):.4f}, {math.sqrt(hi_):.4f}] (chi-square, {dfree} df)")
s2_wo = float(np.mean([e for f, e in zip(sorted(fam), ests) if f != "B"]))
say(f"without the rung4B family: sd {math.sqrt(s2_wo):.4f}")
# which seed loses
say("seed with the lowest pooled win rate in each family:",
    {f: min(fam[f], key=lambda n: np.concatenate([W[n]["train"], W[n]["held"]]).mean()) for f in sorted(fam)})

# ---- 5. net vs heuristic; warm-start ------------------------------------
say("\n== net vs heuristic, lead train | held (95% over cells) ==")
for n in sorted(k for k in W if k != "heur"):
    lt = ci_cells((W[n]["train"] - W["heur"]["train"]).astype(float), cell["train"])
    lh = ci_cells((W[n]["held"] - W["heur"]["held"]).astype(float), cell["held"])
    say(f"{n:>8} {lt[0]:+.4f} [{lt[1]:+.4f},{lt[2]:+.4f}] | {lh[0]:+.4f} [{lh[1]:+.4f},{lh[2]:+.4f}]")

si = J("data/bench/tight_silent.json")["halves"]
scell = {h: np.array([s["cell"] for s in si[h]]) for h in ("silent_a", "silent_b")}
warm = {}
for fpath in sorted(glob.glob(os.path.join(ROOT, "results", "warm-start", "cells", "*.json"))):
    c = json.load(open(fpath))
    warm[(c["start"], c["size"], c["seed"])] = c
say("\n== warm-start: trained vs its start net, silent_a | silent_b; training content ==")
for (st, size, seed), c in sorted(warm.items(), key=lambda k: (k[0][0], k[0][1], str(k[0][2]))):
    if size in (0, 10000):
        continue
    base = warm[(st, 0, None)]
    out = []
    for h in ("silent_a", "silent_b"):
        d = b(c["tight"][h]["won"]) - b(base["tight"][h]["won"])
        out.append(ci_cells(d.astype(float), scell[h]))
    say(f"{st} {size} s{seed}: {out[0][0]:+.4f} [{out[0][1]:+.4f},{out[0][2]:+.4f}] | "
        f"{out[1][0]:+.4f} [{out[1][1]:+.4f},{out[1][2]:+.4f}]  content={c['settings']['train']['content']}")

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "check_sprt.txt"), "w") as f:
    f.write("\n".join(lines) + "\n")
