"""Skeptic's check of primitive_probe.py's headline numbers.

1. Recompute from primitive_probe's cached per-probe records (its out/
   JSONs), with my own code: violation rates, mean change per probe,
   paired B - A, all with my own cell bootstrap.
2. Re-probe a few nets on a state subset with an independent path: encode
   each state alone, shift the raw card column in that one-state batch, run
   the net. Compare dv record by record with the cache.
3. Baseline: the same sign rule applied to exhaust-pile probes (where any
   change is spurious), per net, against the live-pile rate.
4. Step size in the net's own normaliser units (how far off-distribution
   each probe is), and how many lose_hp +3 probes land on a card that
   already loses HP.
5. Pre-contract (exact-only) nets: correlation of their base scores with a
   contract net's over the same states (column misalignment would show).
6. Leads and Spearman with a permutation p-value; pool context recomputed
   without the hit double count.

Single-threaded.  python scripts/analysis/check_probe.py [--states-sub N]
"""

import argparse
import json
import os
import sys
import time

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.set_num_threads(1)

PP = os.path.join(ROOT, "scripts", "analysis", "out", "primitive_probe")
SIGN = {"damage +3": 1, "damage -3": -1, "block +3": 1, "block -3": -1, "lose_hp +3": -1, "lose_hp -2": 1,
        "cost +1": -1, "cost -1": 1}
COLUMN = {"damage": "damage_single", "block": "block", "lose_hp": "lose_hp", "cost": "cost"}
LIVE = ("hand", "draw", "discard")


def load_cache():
    out = {}
    for f in sorted(os.listdir(PP)):
        if f.endswith("-500.json"):
            with open(os.path.join(PP, f)) as fh:
                d = json.load(fh)
            out[f[:-9].replace("_", " ")] = d
    return out


def cells_of_states(n_per_half=500, seed=0):
    """Same state sample as primitive_probe.load_states, rebuilt from the
    decisions file (rng draw repeated), returned with the decision dicts."""
    with open(os.path.join(ROOT, "data", "bench", "decisions.json")) as fh:
        halves = json.load(fh)["halves"]
    rng = np.random.default_rng(seed)
    ds, cells = [], []
    for half, rows in halves.items():
        pick = np.sort(rng.choice(len(rows), size=min(n_per_half, len(rows)), replace=False))
        for i in pick:
            d = rows[int(i)]
            ds.append(d)
            cells.append(f"{half}:{d['family']}:{d['encounter']}")
    return ds, cells


def boot(num, den, B=2000, seed=5):
    """Ratio of sums over cells, 95% percentile interval over cells resampled."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    rng = np.random.default_rng(seed)
    k = len(num)
    p = rng.integers(0, k, (B, k))
    bs = num[p].sum(1) / den[p].sum(1)
    return num.sum() / den.sum(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)


def per_cell(values, mask, cell_idx, k):
    return (np.bincount(cell_idx[mask], weights=values[mask], minlength=k),
            np.bincount(cell_idx[mask], minlength=k).astype(float))


def fmt(t):
    return f"{t[0]:+.3f} [{t[1]:+.3f},{t[2]:+.3f}]"


def part1(cache, cells, tol):
    ucells = sorted(set(cells))
    code = np.array([ucells.index(c) for c in cells])
    k = len(ucells)
    print(f"\n== Part 1: recompute from cache, tol {tol}; {len(cells)} states, {k} cells")
    rows = {}
    for name, d in cache.items():
        r = d["recs"]
        st, pile, probe, dv = (np.asarray(r[x]) for x in ("state", "pile", "probe", "dv"))
        sg = np.array([SIGN[p] for p in probe])
        ci = code[st]
        live = np.isin(pile, LIVE)
        exh = pile == "exhaust"
        viol = (sg * dv < -tol).astype(float)
        res = {}
        for prim in ("damage", "block", "lose_hp", "cost", "all"):
            m = live & (np.char.startswith(probe.astype(str), prim + " ") if prim != "all" else True)
            res[prim] = boot(*per_cell(viol, m, ci, k))
            me = exh & (np.char.startswith(probe.astype(str), prim + " ") if prim != "all" else True)
            res[prim + "_exh"] = viol[me].mean() if me.any() else float("nan")
            res[prim + "_exh_n"] = int(me.sum())
        for p in SIGN:
            m = live & (probe == p)
            res["mean " + p] = (SIGN[p] * dv[m]).mean() if m.any() else float("nan")
            res["n " + p] = int(m.sum())
        # lose_hp +3 split by whether the card already loses HP: needs the
        # raw column, which the cache lacks; part 4 does that.
        rows[name] = res
    print(f"{'net':20s} {'all':>24s} {'lose_hp':>24s} {'cost':>24s}  exh-rate(all) dmg+3  blk+3  lhp+3  lhp-2  cost+1 cost-1")
    for n, r in rows.items():
        print(f"{n:20s} {fmt(r['all']):>24s} {fmt(r['lose_hp']):>24s} {fmt(r['cost']):>24s}  {r['all_exh']:.3f}"
              f"  {r['mean damage +3']:+.4f} {r['mean block +3']:+.4f} {r['mean lose_hp +3']:+.4f}"
              f" {r['mean lose_hp -2']:+.4f} {r['mean cost +1']:+.4f} {r['mean cost -1']:+.4f}")
    any_ = next(iter(rows.values()))
    print("n probes (live):", {p: any_["n " + p] for p in SIGN}, " exhaust n all:", any_["all_exh_n"])
    for key in ("mean lose_hp +3", "mean cost -1", "mean damage +3", "mean block +3", "mean lose_hp -2", "mean cost +1"):
        neg = [n for n, r in rows.items() if r[key] < 0]
        print(f"  {key}: wrong-way mean for {len(neg)}/{len(rows)}")
    for prim in ("damage", "block", "lose_hp", "cost", "all"):
        v = [r[prim][0] for r in rows.values()]
        print(f"  {prim}: violation rate range {min(v):.3f}-{max(v):.3f}")
    # Paired B - A
    pairs = [("exact A bounds", "exact B bounds"), ("exact A first", "exact B first"),
             ("rung4 A s1", "rung4 B s1"), ("rung4 A s101", "rung4 B s101"), ("rung4 A s201", "rung4 B s201"),
             ("night s1 r10", "night s0 r10")]
    print("paired (second - first), all primitives, live piles; and the same on exhaust probes")
    for a, b in pairs:
        ra, rb = cache[a]["recs"], cache[b]["recs"]
        assert ra["state"] == rb["state"] and ra["probe"] == rb["probe"] and ra["pile"] == rb["pile"]
        st, pile, probe = np.asarray(ra["state"]), np.asarray(ra["pile"]), np.asarray(ra["probe"])
        sg = np.array([SIGN[p] for p in probe])
        va = (sg * np.asarray(ra["dv"]) < -tol).astype(float)
        vb = (sg * np.asarray(rb["dv"]) < -tol).astype(float)
        ci = code[st]
        live = np.isin(pile, LIVE)
        cost = live & np.char.startswith(probe.astype(str), "cost ")
        print(f"  {b} - {a}: all {fmt(boot(*per_cell(vb - va, live, ci, k)))}"
              f"  cost {fmt(boot(*per_cell(vb - va, cost, ci, k)))}"
              f"  exhaust {fmt(boot(*per_cell(vb - va, pile == 'exhaust', ci, k)))}")
    return rows


def leads():
    def jl(p):
        with open(os.path.join(ROOT, p)) as fh:
            return json.load(fh)
    rs = jl("runs/tight2/rescore.json")["nets"]
    ck = jl("runs/rung4-nightdb/check.json")["seeds"]
    out = {}
    for n in ("s1 r2", "s1 r4", "s1 r7", "s1 r10", "s0 r7", "s1 r9", "s0 r10"):
        out["night " + n] = rs[n]["lead"]["held_out"]
    for s in ("1", "101", "201"):
        for a in "AB":
            out[f"rung4 {a} s{s}"] = ck[s]["tight"][a]["halves"]["held_out"]["lead"]
    return out


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return np.corrcoef(rx, ry)[0, 1]


def part6(rows_by_tol):
    print("\n== Part 6: leads and Spearman")
    ld = leads()
    names = list(ld)
    x = np.array([ld[n][0] for n in names])
    rng = np.random.default_rng(3)
    for tol, rows in rows_by_tol.items():
        y = np.array([rows[n]["all"][0] for n in names])
        rho = spearman(x, y)
        perm = np.array([spearman(x, rng.permutation(y)) for _ in range(20000)])
        print(f"  tol {tol}: Spearman(held-out lead, all-violation rate) n={len(names)}: {rho:+.3f},"
              f" two-sided permutation p = {(np.abs(perm) >= abs(rho) - 1e-12).mean():.3f}")
    for n in ("night s0 r10", "night s1 r10"):
        print(f"  {n}: lead {ld[n]}")


def part2(nets, cache, sub, seed=11):
    """Independent re-probe: one state at a time, through Features.encode and
    Normalizer.tensors only (no Dataset)."""
    import stsnet
    import bench_decisions
    print(f"\n== Part 2: independent re-probe on {sub} states")
    decs, cells = cells_of_states()
    rng = np.random.default_rng(seed)
    pick = np.sort(rng.choice(len(decs), size=sub, replace=False))
    states = {int(i): bench_decisions.replay(decs[int(i)]) for i in pick}
    elig = {
        "damage +3": lambda c: (c["type_attack"] > 0) & (c["damage_single"] > 0),
        "lose_hp +3": lambda c: (c["unplayable"] == 0) & (c["type_status"] == 0) & (c["cost"] >= 0),
        "cost -1": lambda c: (c["unplayable"] == 0) & (c["type_status"] == 0) & (c["cost"] >= 1),
    }
    delta = {"damage +3": ("damage_single", 3), "lose_hp +3": ("lose_hp", 3), "cost -1": ("cost", -1)}
    for name in nets:
        path = os.path.join(ROOT, cache[name]["path"])
        try:
            model, norm, meta = stsnet.load(path)
        except ValueError:
            model, norm, meta = stsnet.load_pre_contract(path)
            meta = {**meta, **stsnet.layout_of(meta)}
        f = stsnet.features_for(meta)
        cols = list(meta["columns"]["cards"])
        ix = {c: i for i, c in enumerate(cols)}
        piles = list(meta["piles"])
        mine = {p: [] for p in elig}
        lh_already = []
        t0 = time.time()
        for i, s in states.items():
            b = f.encode([s], heuristic=True)
            with torch.no_grad():
                base = float(stsnet.score_of(model, norm.tensors(b))[0])
            X = b["cards"]
            c = {k: X[:, j] for k, j in ix.items()}
            pn = np.array(piles)[np.asarray(b["card_pile"], np.int64)]
            for p, fn in elig.items():
                col, dl = delta[p]
                rws = np.nonzero(fn(c) & np.isin(pn, LIVE + ("exhaust",)))[0]
                if len(rws) == 0:
                    continue
                vals = []
                for r in rws:
                    b2 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in b.items()}
                    b2["cards"][r, ix[col]] += dl
                    with torch.no_grad():
                        vals.append(float(stsnet.score_of(model, norm.tensors(b2))[0]))
                for r, v in zip(rws, vals):
                    mine[p].append((i, pn[r], v - base))
                    if p == "lose_hp +3" and pn[r] in LIVE:
                        lh_already.append(c["lose_hp"][r] > 0)
        rec = cache[name]["recs"]
        st, pl, pr, dv = (np.asarray(rec[x]) for x in ("state", "pile", "probe", "dv"))
        for p in elig:
            m = (pr == p) & np.isin(st, pick)
            theirs = list(zip(st[m].tolist(), pl[m].tolist(), dv[m].tolist()))
            ok = len(theirs) == len(mine[p]) and all(a[0] == b_[0] and a[1] == b_[1] for a, b_ in zip(theirs, mine[p]))
            err = max((abs(a[2] - b_[2]) for a, b_ in zip(theirs, mine[p])), default=float("nan"))
            print(f"  {name:16s} {p:10s} records {len(mine[p])} vs cache {len(theirs)}  aligned {ok}  max|dv diff| {err:.2e}")
        print(f"  {name}: lose_hp +3 live probes on a card already losing HP: {np.mean(lh_already):.3f}"
              f" ({time.time() - t0:.0f}s)")


def part45(cache):
    import stsnet
    import sts
    print("\n== Part 4: probe step in each net's normaliser sd units (card columns)")
    for name in ("night s1 r10", "night s0 r10", "rung4 A s1", "exact A bounds"):
        path = os.path.join(ROOT, cache[name]["path"])
        try:
            model, norm, meta = stsnet.load(path)
        except ValueError:
            model, norm, meta = stsnet.load_pre_contract(path)
            meta = {**meta, **stsnet.layout_of(meta)}
        cols = list(meta["columns"]["cards"])
        m, s = norm.stats["cards"]
        print(f"  {name:16s} " + "  ".join(
            f"{c}: step {st}/sd {s[cols.index(c)]:.2f} = {st / s[cols.index(c)]:.1f} sd (mean {m[cols.index(c)]:.2f})"
            for c, st in (("damage_single", 3), ("block", 3), ("lose_hp", 3), ("cost", 1))))
    print("\n== Part 5: base-score agreement across nets (pre-contract column check)")
    # Base scores are not cached: correlate dv vectors on identical records
    # instead (a net reading misaligned columns would not track the others).
    ref = np.asarray(cache["night s1 r10"]["recs"]["dv"])
    for n, d in cache.items():
        v = np.asarray(d["recs"]["dv"])
        print(f"  corr(dv, night s1 r10 dv) {n:20s} {np.corrcoef(v, ref)[0, 1]:+.3f}   base mean {d['base_mean']:.3f}")
    print("\n== Pool context (no hit double count)")
    model, norm, meta = stsnet.load(os.path.join(ROOT, cache["night s1 r10"]["path"]))
    names = sts.deck_card_names()
    b = stsnet.features_for(meta).encode([sts.Combat(names, "jaw_worm", seed=1)])
    ix = {k: i for i, k in enumerate(meta["columns"]["cards"])}
    X = b["cards"]
    dmg = X[:, ix["damage_single"]] + X[:, ix["damage_all"]]
    cost = X[:, ix["cost"]]
    print(f"  {len(names)} names, {len(X)} rows, lose_hp>0 rows {int((X[:, ix['lose_hp']] > 0).sum())}:",
          [n for n in names if any(k in n.lower() for k in ("blood", "hemo", "offer", "combust", "brutal"))])
    for k in np.unique(cost):
        mk = cost == k
        print(f"  cost {int(k)}: {int(mk.sum())} cards, mean damage_single+damage_all {dmg[mk].mean():.2f},"
              f" mean block {X[mk, ix['block']].mean():.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states-sub", type=int, default=120)
    ap.add_argument("--skip-reprobe", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    cache = load_cache()
    decs, cells = cells_of_states()
    assert all(len(set(d["recs"]["state"])) <= len(cells) for d in cache.values())
    rows = {tol: part1(cache, cells, tol) for tol in (1e-3, 1e-2)}
    part6(rows)
    part45(cache)
    if not args.skip_reprobe:
        part2(["night s0 r10", "exact A bounds"], cache, args.states_sub)
    print(f"\n{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
