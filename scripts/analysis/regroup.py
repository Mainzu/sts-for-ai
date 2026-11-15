"""Regroup every stored per-fight tight2 result by fight type and half.

Zero-CPU analysis for the 2026-10-30 big-picture review: for every net with
per-fight results on tight fights v2 (data/bench/tight2.json), the lead over
the heuristic (net win minus heuristic win, paired by fight) per fight type
(hallway / elite / boss) and half (train = strength, held_out =
generalisation), with 95% intervals over cells (fights cluster by cell, so
cells are the unit: per-cell mean of the differences, then mean +- 1.96 sd /
sqrt(cells)).

Sources (read only):
- runs/seed-check/check.json: retrains of the 10-28 night's s1 rounds 2, 4,
  7, 10 at training seeds 1, 101, 201; full tight2, both halves; also the
  heuristic's per-fight results.
- runs/rung4-nightdb/check.json: arms A (= seed check's r10) and B (rung-4
  play-out labels) at the same seeds.
- results/warm-start/cells/*.json: tight2 train half, cells with cell % 4 ==
  0 only (curve.py `tight2_specs`), same search (bench.LIMIT) as above; the
  heuristic is the matching subset of the seed check's heuristic fights.
- runs/tight2/rescore.json: the night's own nets (s0 r5..r10, s1 r1..r10) on
  tight2, aggregate leads only (no per-fight bits stored), so they can't be
  split by type; printed as context.
- runs/2026-10-2[78]-*/round.json: per-round results on tight v1, aggregate
  win rates only (tight_results null); not usable here.

Minimum detectable effect (MDE): 2.8 x sd_seed x sqrt(2 / seeds) for two
independent arms of `seeds` seeds each (80% power, 5% two-sided). sd_seed is
measured per type and half as the pooled within-arm sd of per-seed leads
over the five 3-seed Ironclad arms (seed-check r2, r4, r7, r10; rung-4 B);
the brief's defaults (0.006 train, 0.0075 held-out) are printed beside it.

    OMP_NUM_THREADS=1 .venv/Scripts/python scripts/analysis/regroup.py
Writes scripts/analysis/out/regroup.json.
"""

import glob
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(os.path.dirname(__file__), "out")
Z = 1.959964
T2 = 4.302653  # t(0.975, df 2): interval over 3 seeds
GROUPS = ("hallway", "elite", "boss")
HALVES = ("train", "held_out")
SEEDS = ("1", "101", "201")
SD_DEFAULT = {"train": 0.006, "held_out": 0.0075}


def p(*parts):
    return os.path.join(ROOT, *parts)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bits(s):
    return np.frombuffer(s.encode(), np.uint8) - ord("0")


# --- the set ---------------------------------------------------------------

SPECS = load(p("data", "bench", "tight2.json"))["halves"]
CELL = {h: np.array([s["cell"] for s in SPECS[h]]) for h in HALVES}
NCELL = {h: int(CELL[h].max()) + 1 for h in HALVES}
GROUP_OF = {h: np.empty(NCELL[h], object) for h in HALVES}
for h in HALVES:
    for s in SPECS[h]:
        GROUP_OF[h][s["cell"]] = s["group"]
SUB4 = {"train": CELL["train"] % 4 == 0, "held_out": None}  # warm-start's tight2 subset


def cell_means(x, half, mask=None):
    """Per-cell means of per-fight `x` over the half's (masked) fights:
    (cell ids, means)."""
    c = CELL[half] if mask is None else CELL[half][mask]
    ids, inv = np.unique(c, return_inverse=True)
    return ids, np.bincount(inv, weights=np.asarray(x, float)) / np.bincount(inv)


def interval(m):
    m = np.asarray(m, float)
    if len(m) < 2:
        return [float(m.mean()) if len(m) else float("nan"), float("nan"), float("nan")]
    w = Z * m.std(ddof=1) / np.sqrt(len(m))
    return [float(m.mean()), float(m.mean() - w), float(m.mean() + w)]


def leads(diff, half, mask=None, groups=GROUPS + ("elite+boss", "all")):
    """{group: [mean, lo, hi, cells]} of per-fight `diff` (net - heuristic,
    or arm - arm), intervals over cells."""
    ids, m = cell_means(diff, half, mask)
    g = GROUP_OF[half][ids]
    out = {}
    for name in groups:
        sel = np.ones(len(ids), bool) if name == "all" else np.isin(g, name.split("+"))
        out[name] = interval(m[sel]) + [int(sel.sum())]
    return out


# --- the nets --------------------------------------------------------------

sc = load(p("runs", "seed-check", "check.json"))
r4 = load(p("runs", "rung4-nightdb", "check.json"))
HEUR = {h: bits(sc["heuristic_fights"][h]) for h in HALVES}
assert sc["heuristic_fights"] == r4["heuristic_fights"], "heuristic fights differ between checks"
for h in HALVES:
    assert len(HEUR[h]) == len(SPECS[h]), (h, len(HEUR[h]), len(SPECS[h]))

NETS = {}   # name -> {"fights": {half: array}, "mask": {half: mask or None}, "arm": arm name}
ARMS = {}   # arm -> [net names]


def add(name, arm, fights, mask=None):
    NETS[name] = {"fights": fights, "mask": mask or {h: None for h in fights}, "arm": arm}
    ARMS.setdefault(arm, []).append(name)


for k in ("2", "4", "7", "10"):
    for s in SEEDS:
        f = sc["rounds"][k]["seeds"][s]["fights"]
        add(f"sc r{k} s{s}", f"sc r{k}" if k != "10" else "sc r10 = rung4 A", {h: bits(f[h]) for h in HALVES})
for s in SEEDS:
    fa, fb = r4["seeds"][s]["fights"]["A"], r4["seeds"][s]["fights"]["B"]
    assert fa == sc["rounds"]["10"]["seeds"][s]["fights"], f"rung-4 A seed {s} differs from seed check r10"
    add(f"rung4 B s{s}", "rung4 B", {h: bits(fb[h]) for h in HALVES})

for path in sorted(glob.glob(p("results", "warm-start", "cells", "*.json"))):
    c = load(path)
    won = np.array(c["tight2_train"]["won"], np.uint8)
    assert len(won) == SUB4["train"].sum(), (path, len(won))
    seed = "base" if c["size"] == 0 else f"s{c['seed']}"
    add(f"warm {c['start']} {c['size']} {seed}", f"warm {c['start']} {c['size']}",
        {"train": won}, {"train": SUB4["train"]})
    # alignment check: a net agrees with the heuristic on most fights only if specs line up
    agree = float((won == HEUR["train"][SUB4["train"]]).mean())
    assert agree > 0.7, (path, agree)


def net_diff(name, half):
    n = NETS[name]
    m = n["mask"][half]
    return n["fights"][half].astype(float) - (HEUR[half] if m is None else HEUR[half][m]), m


def net_leads(name):
    out = {}
    for h in NETS[name]["fights"]:
        d, m = net_diff(name, h)
        out[h] = leads(d, h, m)
    return out


def arm_leads(arm):
    """Leads of the arm's seed-averaged fights (per fight: mean over seeds)."""
    names = ARMS[arm]
    out = {}
    for h in NETS[names[0]]["fights"]:
        ds = [net_diff(n, h) for n in names]
        out[h] = leads(np.mean([d for d, _ in ds], axis=0), h, ds[0][1])
    return out


# --- seed sd and MDE -------------------------------------------------------

def seed_sd(arms, half, group):
    """Pooled within-arm sd of the per-seed leads (df = sum(seeds - 1))."""
    ss, df = 0.0, 0
    for a in arms:
        x = np.array([PER_NET[n][half][group][0] for n in ARMS[a]])
        ss += ((x - x.mean()) ** 2).sum()
        df += len(x) - 1
    return float(np.sqrt(ss / df)), df


def mde(sd, seeds):
    return 2.8 * sd * np.sqrt(2 / seeds)


def fmt(v, cells=True):
    s = f"{v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]"
    return s + (f" n{v[3]}" if cells and len(v) > 3 else "")


def main():
    os.makedirs(OUT, exist_ok=True)
    global PER_NET
    PER_NET = {n: net_leads(n) for n in NETS}
    PER_ARM = {a: arm_leads(a) for a in ARMS}
    res = {"per_net": PER_NET, "per_arm": PER_ARM}

    print("cells per group (train / held_out):",
          {g: [int((GROUP_OF[h] == g).sum()) for h in HALVES] for g in GROUPS})

    # 1. per-arm table (seed-averaged fights), every group and half
    print("\n== Lead over the heuristic, seed-averaged fights per arm; 95% interval over cells ==")
    for a in ARMS:
        for h, v in PER_ARM[a].items():
            sub = " (every 4th cell)" if NETS[ARMS[a][0]]["mask"][h] is not None else ""
            print(f"{a:22s} {h:8s}{sub} " + " | ".join(f"{g} {fmt(v[g], False)}" for g in v))

    # 2. seed sd and MDE
    ic_arms = ["sc r2", "sc r4", "sc r7", "sc r10 = rung4 A", "rung4 B"]
    sd = {}
    print("\n== Seed sd (pooled within-arm over 5 three-seed Ironclad arms, df 10) and MDE ==")
    for h in HALVES:
        for g in GROUPS + ("elite+boss", "all"):
            s, df = seed_sd(ic_arms, h, g)
            sd[f"{h}/{g}"] = {"sd_seed": s, "df": df, "mde_1v1": mde(s, 1), "mde_3v3": mde(s, 3),
                              "mde_3v3_default_sd": mde(SD_DEFAULT[h], 3)}
            print(f"{h:8s} {g:10s} sd_seed {s:.4f}  MDE 1v1 {mde(s, 1):.3f}  3v3 {mde(s, 3):.3f}  "
                  f"5v5 {mde(s, 5):.3f}  (default sd {SD_DEFAULT[h]}: 3v3 {mde(SD_DEFAULT[h], 3):.3f})")
    res["seed_sd"] = sd

    # 3. (a) rounds over the night: seed-check r2/r4/r7/r10 (s1 lineage)
    print("\n== (a) Seed-check rounds (night s1 lineage, 3 retrains each): per-seed and averaged ==")
    rounds = ["sc r2", "sc r4", "sc r7", "sc r10 = rung4 A"]
    a_out = {}
    for h in HALVES:
        for g in GROUPS + ("elite+boss",):
            row = []
            for a in rounds:
                per_seed = [PER_NET[n][h][g][0] for n in ARMS[a]]
                m, s = float(np.mean(per_seed)), float(np.std(per_seed, ddof=1))
                row.append({"arm": a, "avg_fights": PER_ARM[a][h][g], "per_seed": per_seed,
                            "seed_interval": [m, m - T2 * s / np.sqrt(3), m + T2 * s / np.sqrt(3)]})
            a_out[f"{h}/{g}"] = row
            print(f"{h:8s} {g:10s} " + " | ".join(
                f"{r['arm'].split(' =')[0]} {fmt(r['avg_fights'], False)} seeds "
                + "/".join(f"{x:+.3f}" for x in r["per_seed"]) for r in row))
    # paired-by-fight change vs round 2 (seed-averaged fights)
    print("\n   change vs round 2, paired by fight (seed-averaged), 95% interval over cells:")
    chg = {}
    for h in HALVES:
        avg = {a: np.mean([NETS[n]["fights"][h].astype(float) for n in ARMS[a]], axis=0) for a in rounds}
        later = np.mean([avg[a] for a in rounds[1:]], axis=0)
        for g in GROUPS + ("elite+boss",):
            cols = {a: leads(avg[a] - avg["sc r2"], h, groups=(g,))[g] for a in rounds[1:]}
            cols["mean(r4,r7,r10)"] = leads(later - avg["sc r2"], h, groups=(g,))[g]
            # seed-level interval: per-seed leads are independent nets across rounds;
            # pooled within-arm seed sd (df 10), t(0.975, 10) = 2.228
            sd_s = res["seed_sd"][f"{h}/{g}"]["sd_seed"]
            seed_iv = {}
            for a, v in cols.items():
                se = sd_s * np.sqrt(1 / 3 + (1 / 9 if a.startswith("mean") else 1 / 3))
                seed_iv[a] = [v[0] - 2.228 * se, v[0] + 2.228 * se]
            chg[f"{h}/{g}"] = {"cells": cols, "seeds": seed_iv}
            print(f"   {h:8s} {g:10s} " + " | ".join(
                f"{a.split(' =')[0]}-r2 {fmt(v, False)} seed-t [{seed_iv[a][0]:+.3f}, {seed_iv[a][1]:+.3f}]"
                for a, v in cols.items()))
    res["a_rounds"] = {"per_round": a_out, "change_vs_r2": chg}

    # the night's own nets: aggregate only (rescore.json)
    rs = load(p("runs", "tight2", "rescore.json"))["nets"]
    print("\n   night nets on tight2 (runs/tight2/rescore.json, aggregate only, no per-fight bits):")
    night = {}
    for lin in ("s0", "s1"):
        for k in range(1, 11):
            key = f"{lin} r{k}"
            if key in rs:
                night[key] = rs[key]["lead"]
                print(f"   {key:7s} train {fmt(rs[key]['lead']['train'])}  held_out {fmt(rs[key]['lead']['held_out'])}")
    res["a_night_aggregate"] = night

    # 4. (b) rung-4 B vs A
    print("\n== (b) rung-4 B minus A (paired by fight and seed) ==")
    b_out = {}
    nb = len(GROUPS) * len(HALVES)
    zb = 2.638  # two-sided 0.05/6 (Bonferroni over 3 groups x 2 halves)
    for h in HALVES:
        A = [NETS[f"sc r10 s{s}"]["fights"][h].astype(float) for s in SEEDS]
        B = [NETS[f"rung4 B s{s}"]["fights"][h].astype(float) for s in SEEDS]
        dav = np.mean(B, axis=0) - np.mean(A, axis=0)
        for g in GROUPS + ("elite+boss", "all"):
            v = leads(dav, h, groups=(g,))[g]
            per_seed = [leads(b - a, h, groups=(g,))[g][0] for a, b in zip(A, B)]
            ids, m = cell_means(dav, h)
            sel = np.ones(len(ids), bool) if g == "all" else np.isin(GROUP_OF[h][ids], g.split("+"))
            wb = zb * m[sel].std(ddof=1) / np.sqrt(sel.sum())
            sd_p = float(np.std(per_seed, ddof=1))
            b_out[f"{h}/{g}"] = {"avg": v, "per_seed": per_seed, "bonferroni6": [v[0] - wb, v[0] + wb],
                                 "sd_paired_seed": sd_p, "mde_paired_3": 2.8 * sd_p / np.sqrt(3),
                                 "seed_interval": [float(np.mean(per_seed)) - T2 * sd_p / np.sqrt(3),
                                                   float(np.mean(per_seed)) + T2 * sd_p / np.sqrt(3)]}
            r = b_out[f"{h}/{g}"]
            print(f"{h:8s} {g:10s} B-A {fmt(v)}  Bonf/{nb} [{r['bonferroni6'][0]:+.3f}, {r['bonferroni6'][1]:+.3f}]"
                  f"  seeds " + "/".join(f"{x:+.3f}" for x in per_seed)
                  + f"  seed-t [{r['seed_interval'][0]:+.3f}, {r['seed_interval'][1]:+.3f}]"
                  + f"  sd(B-A) {sd_p:.4f}")
        # B's and A's own leads
    for g in ("elite",):
        for arm in ("sc r10 = rung4 A", "rung4 B"):
            print(f"   {arm:18s} held_out {g}: {fmt(PER_ARM[arm]['held_out'][g])}  train {fmt(PER_ARM[arm]['train'][g])}")
    res["b_rung4"] = b_out

    # 5. (c) best net on train-half elite+boss
    print("\n== (c) Train half, elite+boss cells: every net and arm ==")
    rows = []
    for n in NETS:
        if "train" in PER_NET[n]:
            full = NETS[n]["mask"]["train"] is None
            d, m = net_diff(n, "train")
            sub = leads(d[SUB4["train"]] if full else d, "train", SUB4["train"], groups=("elite+boss",))["elite+boss"]
            rows.append((n, "net", PER_NET[n]["train"]["elite+boss"] if full else None, sub))
    for a in ARMS:
        ds = [net_diff(n, "train") for n in ARMS[a]]
        dav = np.mean([d for d, _ in ds], axis=0)
        full = ds[0][1] is None
        sub = leads(dav[SUB4["train"]] if full else dav, "train", SUB4["train"], groups=("elite+boss",))["elite+boss"]
        rows.append((a, "arm", PER_ARM[a]["train"]["elite+boss"] if full else None, sub))
    rows.sort(key=lambda r: -(r[2] if r[2] else r[3])[0])  # all cells where played, else the every-4th subset
    c_out = []
    for n, kind, full, sub in rows:
        c_out.append({"name": n, "kind": kind, "all_cells": full, "every4_cells": sub})
        print(f"{kind:3s} {n:26s} all cells {fmt(full) if full else '-':38s} every-4th cells {fmt(sub)}")
    res["c_best"] = c_out

    with open(os.path.join(OUT, "regroup.json"), "w") as f:
        json.dump(res, f, indent=1, default=float)
    print(f"\nwrote {os.path.join(OUT, 'regroup.json')}")


if __name__ == "__main__":
    sys.exit(main())
