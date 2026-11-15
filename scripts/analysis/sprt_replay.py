"""Replay a fishtest-style sequential test (SPRT) on stored paired fights.

Question: can an SPRT on paired fights decide cheaply, with a controlled
false-pass rate, whether a candidate net beats a champion?

A pair is the same fight spec (same deck, encounter, hp and seed) played by
two players; its outcome is d = won_A - won_B in {+1, 0, -1} (a tie, 0, is
both won or both lost). The lead is mean(d) = P(+1) - P(-1).

The test is the generalised SPRT fishtest uses, in its normal form: after n
pairs with mean dbar and variance s2 (plug-in, from the pairs seen so far),
    LLR = n * (d1 - d0) / s2 * (dbar - (d0 + d1) / 2),
H0: lead <= d0 = 0, H1: lead >= d1 (0.01 or 0.02). Stop with a pass (H1)
when LLR >= log((1 - beta) / alpha), with a fail (H0) when LLR <=
log(beta / (1 - alpha)), else go on until the fight cap (inconclusive).
alpha = beta = 0.05.

Two ways to draw fights:
  fight - single fights in a random order without replacement from the
          decision set (the set is fixed; order varies over shuffles);
  cell  - whole cells (all ~20 seeds of one deck x encounter x hp) in a
          random order; the unit is the cell's mean d, so the variance the
          test uses includes the between-cell spread (the clustering).

Data (per-fight win bits, same spec order as data/bench/tight2.json or
data/bench/tight_silent.json):
  runs/seed-check/check.json   - heuristic + 4 rounds x 3 seeds (tight2, both halves)
  runs/rung4-nightdb/check.json - arms A/B x 3 seeds (A == seed-check round 10)
  results/warm-start/cells/*.json - 14 nets on tight_silent (both halves) and
                                    tight2 train every 4th cell

Each pair is decided on one half (tight2 train / silent_a) and checked on
the other half (tight2 held_out / silent_b; different cells): a pass is
"reproduced" when the full other half's lead is > 0 (point) and "confirmed"
when its 95% cell interval is above 0. A second check pools both halves and
splits cells at random into a decision half and a check half.

Usage: .venv/Scripts/python scripts/analysis/sprt_replay.py [--shuffles 100] [--splits 40]
Writes scripts/analysis/out/sprt_replay.json. Single-threaded, numpy only.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import argparse
import glob
import itertools
import json
import math
import time

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(os.path.dirname(__file__), "out")
ALPHA = BETA = 0.05
UPPER = math.log((1 - BETA) / ALPHA)   # +2.944
LOWER = math.log(BETA / (1 - ALPHA))   # -2.944
Z = 1.959964
MIN_FIGHTS = 200   # no decision before this many pairs (plug-in variance settles)
MIN_CELLS = 20


def load(p):
    with open(os.path.join(ROOT, p)) as f:
        return json.load(f)


def bits(s):
    return np.frombuffer(s.encode(), np.uint8) - 48 if isinstance(s, str) else np.array(s, np.int8)


# --- data -------------------------------------------------------------------

def load_sets():
    """{set: cell index per fight}: tight2 halves, tight2 train every 4th
    cell, silent halves."""
    t2 = load("data/bench/tight2.json")["halves"]
    si = load("data/bench/tight_silent.json")["halves"]
    cells = {"t2_train": np.array([s["cell"] for s in t2["train"]]),
             "t2_held": np.array([s["cell"] for s in t2["held_out"]]),
             "silent_a": np.array([s["cell"] for s in si["silent_a"]]),
             "silent_b": np.array([s["cell"] for s in si["silent_b"]])}
    groups = {"t2_train": np.array([s["group"] for s in t2["train"]]),
              "t2_held": np.array([s["group"] for s in t2["held_out"]])}
    cells["t2_train_q"] = cells["t2_train"][cells["t2_train"] % 4 == 0]
    return cells, groups


def load_players():
    """{player: {set: win bits}} and {player: family label}."""
    sc = load("runs/seed-check/check.json")
    r4 = load("runs/rung4-nightdb/check.json")
    P, fam = {}, {}
    hf = sc["heuristic_fights"]
    P["heur"] = {"t2_train": bits(hf["train"]), "t2_held": bits(hf["held_out"])}
    fam["heur"] = "heuristic"
    for r, rnd in sc["rounds"].items():
        for s, rec in rnd["seeds"].items():
            n = f"night_r{r}_s{s}"
            P[n] = {"t2_train": bits(rec["fights"]["train"]), "t2_held": bits(rec["fights"]["held_out"])}
            fam[n] = f"night_r{r}"   # retrain of night round r's data at seed s (r10 == rung4 arm A)
    for s, rec in r4["seeds"].items():
        n = f"rung4B_s{s}"
        P[n] = {"t2_train": bits(rec["fights"]["B"]["train"]), "t2_held": bits(rec["fights"]["B"]["held_out"])}
        fam[n] = "rung4B"
    for f in sorted(glob.glob(os.path.join(ROOT, "results", "warm-start", "cells", "*.json"))):
        c = json.load(open(f))
        n = f"{c['start']}_{c['size']}_s{c['seed']}"
        P[n] = {"silent_a": bits(c["tight"]["silent_a"]["won"]), "silent_b": bits(c["tight"]["silent_b"]["won"]),
                "t2_train_q": bits(c["tight2_train"]["won"])}
        fam[n] = f"{c['start']}_{c['size']}"
    return P, fam


# --- statistics -------------------------------------------------------------

def cell_means(x, cells):
    u, inv = np.unique(cells, return_inverse=True)
    return np.bincount(inv, x) / np.bincount(inv)


def cell_interval(d, cells):
    m = cell_means(d, cells)
    w = Z * m.std(ddof=1) / math.sqrt(len(m))
    return [float(m.mean()), float(m.mean() - w), float(m.mean() + w)]


def anova_icc(d, cells):
    """One-way ANOVA ICC of d within cells, the average cell size m, the
    design effect 1 + (m - 1) ICC and the between-cell sd of the true lead."""
    u, inv = np.unique(cells, return_inverse=True)
    k = len(u)
    n_i = np.bincount(inv)
    N = len(d)
    mi = np.bincount(inv, d) / n_i
    gm = d.mean()
    ssb = float((n_i * (mi - gm) ** 2).sum())
    ssw = float(((d - mi[inv]) ** 2).sum())
    msb, msw = ssb / (k - 1), ssw / (N - k)
    n0 = (N - (n_i ** 2).sum() / N) / (k - 1)
    sb2 = max((msb - msw) / n0, 0.0)
    icc = sb2 / (sb2 + msw) if sb2 + msw > 0 else 0.0
    m = N / k
    return {"icc": icc, "m": m, "deff": 1 + (m - 1) * icc, "sd_between": math.sqrt(sb2), "sd_within": math.sqrt(msw)}


def describe(d, cells):
    return {"n": int(len(d)), "cells": int(len(np.unique(cells))), "lead": cell_interval(d, cells),
            "fight_lead": float(d.mean()), "discordant": float(np.mean(d != 0)), "var": float(d.var()),
            **anova_icc(d, cells)}


def sprt_paths(x, d1, n_min):
    """Decision of the SPRT along each row of x (rows = shuffles, columns =
    units in draw order). Returns (decision +1 pass / -1 fail / 0 none,
    stopping index (1-based units), for each row), for both orientations:
    x and -x (the other player as candidate)."""
    n = np.arange(1, x.shape[1] + 1)
    S = np.cumsum(x, axis=1)
    Q = np.cumsum(x * x, axis=1)
    out = []
    for sign in (1, -1):
        mean = sign * S / n
        var = Q / n - mean ** 2
        var = np.maximum(var, 1e-6)
        llr = n * d1 / var * (mean - d1 / 2)
        llr[:, :n_min - 1] = 0.0
        up = llr >= UPPER
        lo = llr <= LOWER
        hit = up | lo
        any_hit = hit.any(axis=1)
        first = np.where(any_hit, hit.argmax(axis=1), x.shape[1] - 1)
        rows = np.arange(x.shape[0])
        dec = np.where(any_hit, np.where(up[rows, first], 1, -1), 0)
        out.append((dec, first + 1))
    return out


def replay(d, cells, d1, caps, shuffles, rng, unit):
    """SPRT replays on one decision set (the whole set in a random order;
    a cap in fights truncates the same paths). Returns {cap: [orientation a,
    orientation b]} with decision rates, stopping-time quantiles in fights
    (a run that never stops counts as the cap) and the per-shuffle
    decisions."""
    if unit == "fight":
        X = np.stack([d[rng.permutation(len(d))] for _ in range(shuffles)])
        res = sprt_paths(X, d1, MIN_FIGHTS)
        fights_at = lambda stop: stop
    else:
        m = cell_means(d, cells)
        size = np.bincount(np.unique(cells, return_inverse=True)[1])
        perms = np.stack([rng.permutation(len(m)) for _ in range(shuffles)])
        res = sprt_paths(m[perms], d1, MIN_CELLS)
        csize = np.cumsum(size[perms], axis=1)
        fights_at = lambda stop: csize[np.arange(shuffles), stop - 1]
    out = {}
    for cap in caps:
        out[cap] = []
        for dec, stop in res:
            f = fights_at(stop)
            dc = np.where((dec != 0) & (f <= cap), dec, 0)
            fc = np.where(dc != 0, f, min(cap, len(d)))
            out[cap].append({"pass": float(np.mean(dc == 1)), "fail": float(np.mean(dc == -1)),
                             "none": float(np.mean(dc == 0)),
                             "stop_q": [float(np.percentile(fc, q)) for q in (10, 50, 90)],
                             "stop_mean": float(fc.mean()), "dec": dc})
    return out


# --- the pairs --------------------------------------------------------------

def pairs(P, fam):
    """(label, kind, a, b, decide set, check set)."""
    out = []
    by_fam = {}
    for n, f in fam.items():
        by_fam.setdefault(f, []).append(n)
    for f, names in sorted(by_fam.items()):
        if f == "heuristic" or len(names) < 2:
            continue
        for a, b in itertools.combinations(sorted(names), 2):
            if "silent_a" in P[a]:
                out.append((f"{a} vs {b}", "same recipe", a, b, "silent_a", "silent_b"))
            else:
                out.append((f"{a} vs {b}", "same recipe", a, b, "t2_train", "t2_held"))
    for n, f in sorted(fam.items()):
        if f.startswith("night") or f == "rung4B":
            out.append((f"{n} vs heur", "net vs heuristic", n, "heur", "t2_train", "t2_held"))
            out.append((f"{n} vs heur [held decides]", "net vs heuristic (held decides)", n, "heur",
                        "t2_held", "t2_train"))
    for s in ("1", "101", "201"):
        out.append((f"rung4B_s{s} vs night_r10_s{s}", "rung4 B vs A", f"rung4B_s{s}", f"night_r10_s{s}",
                    "t2_train", "t2_held"))
        out.append((f"night_r2_s{s} vs night_r10_s{s}", "round 2 vs round 10", f"night_r2_s{s}",
                    f"night_r10_s{s}", "t2_train", "t2_held"))
    for start in ("warm_effects", "warm_ids"):
        for size in (500, 2000):
            for s in range(3):
                out.append((f"{start}_{size}_s{s} vs {start}_0", "warm trained vs start", f"{start}_{size}_s{s}",
                            f"{start}_0_sNone", "silent_a", "silent_b"))
                out.append((f"{start}_{size}_s{s} vs {start}_0 [b decides]", "warm trained vs start (b decides)",
                            f"{start}_{size}_s{s}", f"{start}_0_sNone", "silent_b", "silent_a"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--shuffles", type=int, default=100)
    ap.add_argument("--splits", type=int, default=40, help="random cell splits for the pooled check")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--report", action="store_true", help="only print the report of the saved json")
    args = ap.parse_args(argv)
    if args.report:
        with open(os.path.join(OUT, "sprt_replay.json")) as f:
            return report(json.load(f))
    t0 = time.time()
    rng = np.random.default_rng(args.seed)
    cells, groups = load_sets()
    P, fam = load_players()
    for n, sets in P.items():
        for s, x in sets.items():
            assert len(x) == len(cells[s]), (n, s, len(x), len(cells[s]))
    PL = pairs(P, fam)
    caps = {"t2_train": [4000, 8000, 12320], "t2_held": [4000, 8000, 12200], "silent_a": [1440], "silent_b": [2080]}
    res = {"settings": {"alpha": ALPHA, "beta": BETA, "upper": UPPER, "lower": LOWER, "min_fights": MIN_FIGHTS,
                        "min_cells": MIN_CELLS, "shuffles": args.shuffles, "seed": args.seed}, "pairs": []}
    for label, kind, a, b, ds, cs in PL:
        d = P[a][ds].astype(np.float64) - P[b][ds]
        dc = P[a][cs].astype(np.float64) - P[b][cs]
        rec = {"label": label, "kind": kind, "a": a, "b": b, "decide": ds, "check": cs,
               "decide_stats": describe(d, cells[ds]), "check_stats": describe(dc, cells[cs]), "runs": []}
        chk = rec["check_stats"]["lead"]
        for d1 in (0.01, 0.02):
            for unit in ("fight", "cell"):
                allo = replay(d, cells[ds], d1, caps[ds], args.shuffles, rng, unit)
                for cap, o in allo.items():
                    either = float(np.mean((o[0]["dec"] == 1) | (o[1]["dec"] == 1)))
                    for orient, r in zip(("a", "b"), o):
                        r["either_passes"] = either
                        sgn = 1 if orient == "a" else -1
                        dec = r.pop("dec")
                        npass = int((dec == 1).sum())
                        r.update({"d1": d1, "unit": unit, "cap": cap, "candidate": a if orient == "a" else b,
                                  "check_lead_for_candidate": [sgn * chk[0]] + sorted([sgn * chk[1], sgn * chk[2]]),
                                  "passes": npass})
                        r["reproduced"] = bool(sgn * chk[0] > 0) if npass else None
                        r["confirmed"] = bool(min(sgn * chk[1], sgn * chk[2]) > 0) if npass else None
                        rec["runs"].append(r)
        res["pairs"].append(rec)

    # pooled tight2 halves, random cell splits: decide on one half of the
    # cells, check the lead on the other half (fresh cells), fight unit,
    # d1 = 0.01 and 0.02, cap = all fights of the decision half.
    pooled = []
    t2c = np.concatenate([cells["t2_train"], cells["t2_held"] + 10_000])
    for label, kind, a, b, ds, cs in PL:
        if ds != "t2_train":
            continue
        d = np.concatenate([P[a]["t2_train"], P[a]["t2_held"]]).astype(np.float64) - \
            np.concatenate([P[b]["t2_train"], P[b]["t2_held"]])
        u = np.unique(t2c)
        rows = {0.01: [], 0.02: []}
        for _ in range(args.splits):
            pick = rng.permutation(len(u))[:len(u) // 2]
            inA = np.isin(t2c, u[pick])
            dA, dB = d[inA], d[~inA]
            leadB = cell_interval(dB, t2c[~inA])
            for d1 in rows:
                X = np.stack([dA[rng.permutation(len(dA))] for _ in range(4)])
                for sign, (dec, stop) in zip((1, -1), sprt_paths(X, d1, MIN_FIGHTS)):
                    for k in range(len(dec)):
                        rows[d1].append((sign, int(dec[k]), int(stop[k]), sign * leadB[0],
                                         min(sign * leadB[1], sign * leadB[2])))
        summ = {}
        for d1, r in rows.items():
            r = np.array(r, float)
            p = r[:, 1] == 1
            summ[str(d1)] = {"runs": int(len(r)), "pass_rate": float(p.mean()),
                             "fail_rate": float((r[:, 1] == -1).mean()), "none_rate": float((r[:, 1] == 0).mean()),
                             "pass_rate_a": float(p[r[:, 0] == 1].mean()), "pass_rate_b": float(p[r[:, 0] == -1].mean()),
                             "passes_reproduced": float((r[p, 3] > 0).mean()) if p.any() else None,
                             "passes_confirmed": float((r[p, 4] > 0).mean()) if p.any() else None,
                             "stop_median": float(np.median(r[:, 2]))}
        pooled.append({"label": label, "kind": kind, "lead_all": cell_interval(d, t2c), **summ})
    res["pooled_splits"] = pooled

    # calibration: sign-flip each pair's outcome at random (true lead 0 on
    # the set) and shift to exact lead d1 (flip a share of ties/-1 to +1
    # would change the variance; instead draw i.i.d. trinomials with the
    # observed discordance), to check alpha, beta and ASN of this SPRT.
    calib = []
    for disc in (0.10, 0.20, 0.30):
        for d1 in (0.01, 0.02):
            for true in (0.0, d1 / 2, d1):
                pp, pm = (disc + true) / 2, (disc - true) / 2
                X = rng.choice([1.0, 0.0, -1.0], p=[pp, 1 - disc, pm], size=(200, 30_000))
                dec, stop = sprt_paths(X, d1, MIN_FIGHTS)[0]
                calib.append({"discordant": disc, "d1": d1, "true_lead": true, "pass": float(np.mean(dec == 1)),
                              "fail": float(np.mean(dec == -1)), "none_at_30000": float(np.mean(dec == 0)),
                              "stop_q": [float(np.percentile(stop, q)) for q in (10, 50, 90)],
                              "wald_asn": wald_asn(disc, d1, true)})
    res["calibration"] = calib
    res["minutes"] = (time.time() - t0) / 60
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "sprt_replay.json"), "w") as f:
        json.dump(res, f, indent=1)
    report(res)


def wald_asn(var, d1, true):
    """Wald's approximate average sample number for the normal SPRT with
    variance `var` (~ discordance at small leads) and true lead `true`."""
    a, b = UPPER, LOWER
    mu = d1 / var * (true - d1 / 2)          # mean LLR increment per pair
    if abs(mu) < 1e-12:
        return -a * b / (d1 * d1 / var)     # E[LLR^2 increment] = d1^2/var
    # P(pass) by Wald: (1 - e^{h b}) / (e^{h a} - e^{h b}), h = -2 mu / s^2
    s2 = d1 * d1 / var
    h = -2 * mu / s2
    pa = (1 - math.exp(h * b)) / (math.exp(h * a) - math.exp(h * b))
    return (pa * a + (1 - pa) * b) / mu


def report(res):
    f3 = lambda x: f"{x:+.4f}"
    print(f"minutes {res['minutes']:.1f}")
    print("\n== per pair: lead on decide / check set (cell 95% CI), ICC, deff ==")
    for p in res["pairs"]:
        ds, cs = p["decide_stats"], p["check_stats"]
        print(f"{p['label']:<44} {p['kind']:<26} dec {f3(ds['lead'][0])} [{f3(ds['lead'][1])},{f3(ds['lead'][2])}] "
              f"chk {f3(cs['lead'][0])} [{f3(cs['lead'][1])},{f3(cs['lead'][2])}] disc {ds['discordant']:.3f} "
              f"icc {ds['icc']:.3f} deff {ds['deff']:.2f} sdB {ds['sd_between']:.3f}")
    print("\n== SPRT replays (pass rate per orientation a/b, none, median stop) ==")
    for p in res["pairs"]:
        for r in p["runs"]:
            if r["cap"] not in (12320, 1440):
                continue
            print(f"{p['label']:<44} d1={r['d1']} {r['unit']:<5} cand={r['candidate']:<18} pass {r['pass']:.2f} "
                  f"fail {r['fail']:.2f} none {r['none']:.2f} stop50 {r['stop_q'][1]:>6.0f} "
                  f"repro {r['reproduced']} conf {r['confirmed']}")
    print("\n== aggregate by kind (decide on one half, check on the other half) ==")
    print("kind | d1 | unit | cap | pairs | mean P(some side passes) | share of passes reproduced (check lead > 0) | "
          "confirmed (check CI > 0) | mean of median stop")
    for kind in sorted({p["kind"] for p in res["pairs"]}):
        ps = [p for p in res["pairs"] if p["kind"] == kind]
        for d1 in (0.01, 0.02):
            for unit in ("fight", "cell"):
                for cap in sorted({r["cap"] for p in ps for r in p["runs"]}):
                    rs = [r for p in ps for r in p["runs"] if r["d1"] == d1 and r["unit"] == unit and r["cap"] == cap]
                    if not rs:
                        continue
                    either = np.mean([r["either_passes"] for r in rs[::2]])
                    w = sum(r["passes"] for r in rs)
                    rep = sum(r["passes"] for r in rs if r["reproduced"]) / w if w else float("nan")
                    con = sum(r["passes"] for r in rs if r["confirmed"]) / w if w else float("nan")
                    print(f"{kind:<32} {d1} {unit:<5} {cap:>6} {len(rs) // 2:>3} {either:.3f} {rep:.3f} {con:.3f} "
                          f"{np.mean([r['stop_q'][1] for r in rs]):.0f}")
    print("\n== pooled random cell splits ==")
    for p in res["pooled_splits"]:
        print(p["label"], p["kind"], [round(x, 4) for x in p["lead_all"]],
              {k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in p[k].items()} for k in ("0.01", "0.02")})
    print("\n== pooled splits, aggregate by kind (fight unit, cap = decision half) ==")
    for kind in sorted({p["kind"] for p in res["pooled_splits"]}):
        ps = [p for p in res["pooled_splits"] if p["kind"] == kind]
        for d1 in ("0.01", "0.02"):
            w = [p[d1]["pass_rate"] * p[d1]["runs"] for p in ps]
            rep = sum(wi * (p[d1]["passes_reproduced"] or 0) for wi, p in zip(w, ps)) / max(sum(w), 1e-9)
            con = sum(wi * (p[d1]["passes_confirmed"] or 0) for wi, p in zip(w, ps)) / max(sum(w), 1e-9)
            print(f"{kind:<22} d1={d1} pairs {len(ps):>2} pass rate (per orientation) "
                  f"{np.mean([p[d1]['pass_rate'] for p in ps]):.3f} passes reproduced {rep:.3f} "
                  f"confirmed {con:.3f} median stop {np.median([p[d1]['stop_median'] for p in ps]):.0f}")
    # seed-to-seed spread of a single net's lead: same-recipe pair leads on
    # all 24,520 tight2 fights; Var(pair diff) = 2 sd_net^2 + noise.
    sr = [p for p in res["pooled_splits"] if p["kind"] == "same recipe"]
    diffs = np.array([p["lead_all"][0] for p in sr])
    noise = np.array([((p["lead_all"][2] - p["lead_all"][1]) / (2 * Z)) ** 2 for p in sr])
    sd_net = math.sqrt(max((diffs ** 2 - noise).mean(), 0) / 2)
    print(f"\nseed-to-seed sd of one net's tight2 lead: {sd_net:.4f} (from {len(sr)} same-recipe pairs, "
          f"RMS pair diff {math.sqrt((diffs ** 2).mean()):.4f}, mean noise var {noise.mean():.2e})")
    print("\n== calibration (iid trinomial) ==")
    for c in res["calibration"]:
        print(c)


if __name__ == "__main__":
    main()
