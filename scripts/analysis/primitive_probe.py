"""Primitive probe: do value nets respond to card primitives the way a
sensible player would, or do they value card bundles they have seen?

For a fixed set of real decision states (the bench's `data/bench/decisions.json`,
replayed), each net's encoded batch is copied once per probe, one card row's
raw feature (before the net's normaliser) is shifted by a small amount, and
the change in the net's score is recorded. A sensible player's value can only
go one way for each shift:

  damage_single  +d on an attack that already deals damage  -> value up (or same)
  block          +d on a card that already blocks           -> value up (or same)
  lose_hp        +d self-damage on a playable card          -> value down (or same)
  cost           +1 on a playable card costing 0-2          -> value down (or same)

and the same shifts downwards (where the card has room) the other way. A
"sign violation" is a change the wrong way larger than TOL. Cards in the
exhaust pile are a control: nothing there is played again (no exhume-type
cards in the Ironclad pool the nets see), so any change there is spurious.

Single-threaded, a few seconds per net. Writes one JSON per net under
scripts/analysis/out/primitive_probe/ (cached: reruns skip nets done with
the same state set) and prints the tables.

    python scripts/analysis/primitive_probe.py [--states N] [--nets name ...] [--boot B]
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

import stsnet  # noqa: E402  (sets torch to one thread too)
import bench_decisions  # noqa: E402

torch.set_num_threads(1)

OUT = os.path.join(ROOT, "scripts", "analysis", "out", "primitive_probe")
TOL = 1e-3  # score scale is [0, 2]; a change smaller than this is "no change"
CHUNK = 4096

# name -> (path, group). Night rounds (win rate can't tell them apart on the
# tight gate), the exact-only arms (bounds rerun and first run), the rung-4
# arms over three seeds, and the generalise.py reference net.
NETS = {
    "night s1 r2": ("runs/2026-10-28-score+branch-s1-r2-e250964/model.pt", "night"),
    "night s1 r4": ("runs/2026-10-28-score+branch-s1-r4-23bbdd3/model.pt", "night"),
    "night s1 r7": ("runs/2026-10-28-score+branch-s1-r7-6f12351/model.pt", "night"),
    "night s1 r10": ("runs/2026-10-28-score+branch-s1-r10-3c58554/model.pt", "night"),
    "night s0 r7": ("runs/2026-10-28-score+branch-s0-r7-bc161d5/model.pt", "night"),
    "night s1 r9": ("runs/2026-10-28-score+branch-s1-r9-1db1425/model.pt", "night"),
    "night s0 r10": ("runs/2026-10-28-score+branch-s0-r10-2614609/model.pt", "night"),
    "exact A bounds": ("runs/exact-only-bounds/A/model.pt", "exact-only"),
    "exact B bounds": ("runs/exact-only-bounds/B/model.pt", "exact-only"),
    "exact A first": ("runs/exact-only/A/model.pt", "exact-only"),
    "exact B first": ("runs/exact-only/B/model.pt", "exact-only"),
    "rung4 A s1": ("runs/2026-10-29-rung4-check-A-b0089ff/model.pt", "rung4"),
    "rung4 B s1": ("runs/2026-10-29-rung4-check-B-k12-d8518f0/model.pt", "rung4"),
    "rung4 A s101": ("runs/2026-10-29-rung4-check-A-s101-a254424/model.pt", "rung4"),
    "rung4 B s101": ("runs/2026-10-29-rung4-check-B-k12-s101-e0f85e8/model.pt", "rung4"),
    "rung4 A s201": ("runs/2026-10-29-rung4-check-A-s201-e4c40d5/model.pt", "rung4"),
    "rung4 B s201": ("runs/2026-10-29-rung4-check-B-k12-s201-4401b2a/model.pt", "rung4"),
    "generalise effects": ("models/value_effects.pt", "reference"),
}

# (probe name, column, delta, expected sign of the value change, eligibility)
# Eligibility gets the raw card-column dict `c` (arrays over card rows).
def _playable(c):
    return (c["unplayable"] == 0) & (c["type_status"] == 0) & (c["cost"] >= 0)


PROBES = [
    ("damage +3", "damage_single", +3, +1, lambda c: (c["type_attack"] > 0) & (c["damage_single"] > 0)),
    ("damage -3", "damage_single", -3, -1, lambda c: (c["type_attack"] > 0) & (c["damage_single"] >= 3)),
    ("block +3", "block", +3, +1, lambda c: c["block"] > 0),
    ("block -3", "block", -3, -1, lambda c: c["block"] >= 3),
    ("lose_hp +3", "lose_hp", +3, -1, _playable),
    ("lose_hp -2", "lose_hp", -2, +1, lambda c: c["lose_hp"] >= 2),
    ("cost +1", "cost", +1, -1, lambda c: _playable(c) & (c["cost"] <= 2)),
    ("cost -1", "cost", -1, +1, lambda c: _playable(c) & (c["cost"] >= 1)),
]
PRIMITIVES = ("damage", "block", "lose_hp", "cost")
LIVE_PILES = ("hand", "draw", "discard")
CONTROL_PILE = "exhaust"


def load_states(n_per_half, seed=0):
    """[Combat], [cluster id], [half] for n_per_half decisions per half,
    sampled without replacement (all of them at 1000)."""
    halves = bench_decisions.load_decisions()
    states, clusters, half_of = [], [], []
    rng = np.random.default_rng(seed)
    for h, (half, rows) in enumerate(halves.items()):
        pick = np.sort(rng.choice(len(rows), size=min(n_per_half, len(rows)), replace=False))
        for i in pick:
            d = rows[int(i)]
            states.append(bench_decisions.replay(d))
            # Cell = (half, deck family, encounter): states in one cell share
            # the deck, so the same card rows, and the encounter (the bench
            # has 5 decks per half, ~58 encounters each).
            clusters.append(f"{half}:{d['family']}:{d['encounter']}")
            half_of.append(half)
    return states, clusters, half_of


def probe_net(path, states):
    """Per probe record: state index, pile name, probe name, dv. Plus base scores."""
    full = os.path.join(ROOT, path)
    converted = True
    try:
        model, norm, meta = stsnet.load(full)
    except ValueError as e:
        if "no converted" not in str(e):
            raise
        # A pre-contract net with no <name>.contract.pt (the exact-only arms).
        # Load it as saved and give it the layout today's full encoder writes:
        # the same thing convert_net.py does in memory (it then checks the
        # outputs match bit for bit, which holds by construction here). No
        # file is written beside the net.
        model, norm, meta = stsnet.load_pre_contract(full)
        meta = {**meta, **stsnet.layout_of(meta)}
        for k, d in zip(stsnet.Normalizer.KEYS, ("player", "monster", "card", "row")):
            if model.dims[d] != len(meta["columns"][k]):
                raise ValueError(f"{path}: {k} width {model.dims[d]} != encoder {len(meta['columns'][k])}")
        converted = False
    if getattr(model, "hp_loss", False):
        raise ValueError(f"{path}: HP-histogram net; probe only handles score nets")
    if meta["card_repr"] != "effects":
        raise ValueError(f"{path}: not an effects net")
    b = stsnet.features_for(meta).encode(states, heuristic=True)
    ds = stsnet.Dataset.from_batches([b], np.zeros(len(states), np.float32))
    names = list(meta["columns"]["cards"])
    col = {n: i for i, n in enumerate(names)}
    piles = list(meta["piles"])
    cards = ds.cards.astype(np.float32)
    c = {n: cards[:, i] for n, i in col.items()}
    card_state = np.repeat(np.arange(len(states)), ds.card_len)
    card_local = np.arange(len(cards)) - np.repeat(ds.card_start, ds.card_len)
    pile_name = np.array(piles)[ds.card_pile.astype(np.int64)]

    def score(idx, shifts):
        """Scores of states idx, with card (local k, column j) += delta per entry."""
        out = np.empty(len(idx), np.float32)
        for s in range(0, len(idx), CHUNK):
            ii = idx[s:s + CHUNK]
            bt = ds.batch(ii)
            if shifts is not None:
                k, j, dlt = (a[s:s + CHUNK] for a in shifts)
                coffs = np.concatenate([[0], np.cumsum(ds.card_len[ii])[:-1]])
                bt["cards"][coffs + k, j] += dlt
            with torch.no_grad():
                out[s:s + CHUNK] = stsnet.score_of(model, norm.tensors(bt)).numpy()
        return out

    base = score(np.arange(len(states)), None)
    recs = {"state": [], "pile": [], "probe": [], "dv": []}
    for name, column, delta, _, elig in PROBES:
        sel = np.nonzero(elig(c) & np.isin(pile_name, LIVE_PILES + (CONTROL_PILE,)))[0]
        if len(sel) == 0:
            continue
        idx = card_state[sel]
        dv = score(idx, (card_local[sel], np.full(len(sel), col[column]), np.full(len(sel), delta, np.float32))) - base[idx]
        recs["state"] += idx.tolist()
        recs["pile"] += pile_name[sel].tolist()
        recs["probe"] += [name] * len(sel)
        recs["dv"] += dv.astype(float).tolist()
    return base, recs


def cluster_boot(values_by_cluster, B, rng):
    """95% interval of the pooled mean over clusters resampled with
    replacement. values_by_cluster: list of (sum, count)."""
    sums = np.array([s for s, _ in values_by_cluster], float)
    cnts = np.array([n for _, n in values_by_cluster], float)
    k = len(sums)
    if k == 0 or cnts.sum() == 0:
        return [float("nan")] * 3
    est = sums.sum() / cnts.sum()
    pick = rng.integers(0, k, size=(B, k))
    bs = sums[pick].sum(1) / np.maximum(cnts[pick].sum(1), 1e-9)
    return [float(est), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def _codes(clusters, st):
    """Per record cluster code, and the number of clusters."""
    names = sorted(set(clusters))
    code = np.array([names.index(c) for c in clusters])
    return code[st], len(names)


def _per_cluster(v, m, cl, k):
    """[(sum of v over masked records, count)] per cluster."""
    m = np.broadcast_to(m, cl.shape)
    sums = np.bincount(cl[m], weights=np.asarray(v, float)[m], minlength=k)
    cnts = np.bincount(cl[m], minlength=k)
    return list(zip(sums.tolist(), cnts.tolist()))


def summarise(recs, clusters, B, rng, tol=TOL):
    """Per primitive: sign-violation counts and rates (live piles), with cluster
    intervals; mean expected-direction change; control |dv| in exhaust."""
    st = np.asarray(recs["state"])
    pile = np.asarray(recs["pile"])
    probe = np.asarray(recs["probe"])
    dv = np.asarray(recs["dv"])
    exp = {p[0]: p[3] for p in PROBES}
    sign = np.array([exp[p] for p in probe])
    cl, ucl = _codes(clusters, st)
    out = {}
    live = np.isin(pile, LIVE_PILES)
    for prim in PRIMITIVES + ("all",):
        m = live & (np.char.startswith(probe.astype(str), prim + " ") if prim != "all" else True)
        viol = (sign * dv < -tol) & m
        good = sign * dv
        per = _per_cluster(viol, m, cl, ucl)
        per_dir = _per_cluster(good, m, cl, ucl)
        r = {"n": int(m.sum()), "violations": int(viol.sum()),
             "rate": cluster_boot(per, B, rng),
             "mean_right_way": cluster_boot(per_dir, B, rng),
             # Direction only: of the probes that moved the value by more than
             # tol either way, the share that moved it the wrong way (removes
             # a net's overall sensitivity from the count).
             "wrong_share": float(viol.sum() / max(int(((np.abs(dv) > tol) & m).sum()), 1))}
        for p in LIVE_PILES:
            mp = m & (pile == p)
            r[f"rate_{p}"] = float((viol & mp).sum() / mp.sum()) if mp.sum() else None
        mc = (pile == CONTROL_PILE) & (np.char.startswith(probe.astype(str), prim + " ") if prim != "all" else True)
        r["control_n"] = int(mc.sum())
        r["control_mean_abs"] = float(np.abs(dv[mc]).mean()) if mc.sum() else None
        r["control_over_tol"] = float((np.abs(dv[mc]) > tol).mean()) if mc.sum() else None
        out[prim] = r
    for name, *_ in PROBES:
        m = live & (probe == name)
        out["probe " + name] = {"n": int(m.sum()), "violations": int(((sign * dv < -tol) & m).sum()),
                                "mean_dv": float(dv[m].mean()) if m.sum() else None,
                                "median_dv": float(np.median(dv[m])) if m.sum() else None}
    return out


def paired_diff(ra, rb, clusters, B, rng, tol=TOL):
    """Violation rate of b minus a over the same probe records (live piles),
    cluster-bootstrapped. Both nets see the same states and card rows, but
    eligibility is by raw features, which are the same encoder columns for
    all nets here, so records line up one to one (checked)."""
    if ra["probe"] != rb["probe"] or ra["state"] != rb["state"] or ra["pile"] != rb["pile"]:
        return None
    st = np.asarray(ra["state"])
    pile = np.asarray(ra["pile"])
    probe = np.asarray(ra["probe"])
    exp = {p[0]: p[3] for p in PROBES}
    sign = np.array([exp[p] for p in probe])
    live = np.isin(pile, LIVE_PILES)
    va = ((sign * np.asarray(ra["dv"]) < -tol) & live).astype(float)
    vb = ((sign * np.asarray(rb["dv"]) < -tol) & live).astype(float)
    cl, ucl = _codes(clusters, st)
    out = {}
    for prim in PRIMITIVES + ("all",):
        m = live & (np.char.startswith(probe.astype(str), prim + " ") if prim != "all" else True)
        per = _per_cluster(vb - va, m, cl, ucl)
        out[prim] = cluster_boot(per, B, rng)
    return out


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def gate_lead(name):
    """[lead, lo, hi] on the tight gate's held-out half against the heuristic,
    from the file that scored the net (paired, intervals as stored there)."""
    def jl(p):
        with open(os.path.join(ROOT, p)) as fh:
            return json.load(fh)
    group = NETS[name][1]
    if group == "night":
        return jl("runs/tight2/rescore.json")["nets"][name.replace("night ", "")]["lead"]["held_out"]
    if group == "rung4":
        _, arm, seed = name.split()
        return jl("runs/rung4-nightdb/check.json")["seeds"][seed[1:]]["tight"][arm]["halves"]["held_out"]["lead"]
    if group == "exact-only":
        _, arm, which = name.split()
        f = "runs/exact-only-bounds/results.json" if which == "bounds" else "runs/exact-only/results.json"
        return jl(f)["tight"][arm]["halves"]["held_out"]["lead"]
    return None


def pool_context():
    """How the probed primitives co-occur in the Ironclad deck pool the nets
    trained on (one row per card in `sts.deck_card_names()`): which bundles
    carry lose_hp, and damage by cost."""
    import sts
    model, norm, meta = stsnet.load(os.path.join(ROOT, NETS["night s1 r10"][0]))
    names = sts.deck_card_names()
    b = stsnet.features_for(meta).encode([sts.Combat(names, "jaw_worm", seed=1)])
    ix = {k: i for i, k in enumerate(meta["columns"]["cards"])}
    X = b["cards"]
    dmg = X[:, ix["damage_single"]] * np.maximum(X[:, ix["hits_single"]], 1) + X[:, ix["damage_all"]]
    lh = X[:, ix["lose_hp"]] > 0
    out = {"pool_cards": len(names), "rows": int(len(X)),
           "lose_hp_rows": [{"lose_hp": float(X[i, ix["lose_hp"]]), "energy": float(X[i, ix["energy"]]),
                             "damage": float(dmg[i]), "cost": float(X[i, ix["cost"]])} for i in np.nonzero(lh)[0]],
           "damage_by_cost": {int(k): [int((X[:, ix["cost"]] == k).sum()), float(dmg[X[:, ix["cost"]] == k].mean())]
                              for k in np.unique(X[:, ix["cost"]])}}
    print(f"\nPool context ({out['pool_cards']} Ironclad deck cards): lose_hp rows {out['lose_hp_rows']}")
    print(f"  cards and mean damage per hit-sum by cost: {out['damage_by_cost']}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", type=int, default=150, help="decision states per bench half")
    ap.add_argument("--nets", nargs="*", default=None, help="names from NETS (default all)")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--tol", type=float, default=TOL, help="wrong-way change counted as a violation above this")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    states, clusters, half_of = load_states(args.states)
    print(f"{len(states)} states from {len(set(clusters))} cells ({time.time() - t0:.1f}s)")
    rng = np.random.default_rng(1)
    names = args.nets or list(NETS)
    results = {}
    for name in names:
        path, group = NETS[name]
        f = os.path.join(OUT, name.replace(" ", "_") + f"-{args.states}.json")
        if os.path.exists(f) and not args.redo:
            with open(f) as fh:
                results[name] = json.load(fh)
            continue
        t = time.time()
        base, recs = probe_net(path, states)
        r = {"path": path, "group": group, "states": args.states, "base_mean": float(base.mean()),
             "recs": recs, "seconds": time.time() - t}
        with open(f, "w") as fh:
            json.dump(r, fh)
        results[name] = r
        print(f"  {name}: {len(recs['dv'])} probes in {r['seconds']:.1f}s")
    summary = {}
    print(f"\nSign violations (wrong-way change > {args.tol}), hand+draw+discard; rate [95% over {len(set(clusters))} cells]")
    print(f"{'net':22s} " + " ".join(f"{p:>22s}" for p in PRIMITIVES + ("all",)) + "   exhaust |dv|")
    for name in names:
        s = summarise(results[name]["recs"], clusters, args.boot, rng, args.tol)
        summary[name] = s
        cells = []
        for p in PRIMITIVES + ("all",):
            rate = s[p]["rate"]
            cells.append(f"{s[p]['violations']:5d} {rate[0]:.3f}[{rate[1]:.2f},{rate[2]:.2f}]")
        print(f"{name:22s} " + " ".join(f"{x:>22s}" for x in cells) + f"   {s['all']['control_mean_abs']:.4f}")
    print("\nMean change in the expected direction (score units, positive = sensible)")
    print(f"{'net':22s} " + " ".join(f"{p:>8s}" for p in [q[0] for q in PROBES]))
    for name in names:
        s = summary[name]
        print(f"{name:22s} " + " ".join(
            f"{(s['probe ' + p[0]]['mean_dv'] or 0) * p[3]:8.4f}" for p in PROBES))
    print(f"{'probes (n, first net)':22s} " + " ".join(f"{summary[names[0]]['probe ' + p[0]]['n']:8d}" for p in PROBES))
    print("\nViolation rate per pile (all primitives): hand / draw / discard; n probes")
    for name in names:
        a = summary[name]["all"]
        print(f"{name:22s} {a['rate_hand']:.3f} / {a['rate_draw']:.3f} / {a['rate_discard']:.3f}   n={a['n']}")
    pairs = [("night s1 r10", "night s1 r9"), ("night s1 r2", "night s0 r10"), ("night s1 r7", "night s0 r7"),
             ("exact A bounds", "exact B bounds"), ("exact A first", "exact B first"),
             ("rung4 A s1", "rung4 B s1"), ("rung4 A s101", "rung4 B s101"), ("rung4 A s201", "rung4 B s201"),
             ("night s1 r10", "exact B bounds"), ("night s1 r10", "rung4 B s1")]
    diffs = {}
    print("\nPaired difference in violation rate (second minus first), 95% over cells")
    for a, b in pairs:
        if a in results and b in results:
            d = paired_diff(results[a]["recs"], results[b]["recs"], clusters, args.boot, rng, args.tol)
            diffs[f"{b} - {a}"] = d
            if d:
                print(f"  {b:16s} - {a:16s} " + "  ".join(
                    f"{p}: {d[p][0]:+.3f}[{d[p][1]:+.3f},{d[p][2]:+.3f}]" for p in PRIMITIVES + ("all",)))
    leads = {n: gate_lead(n) for n in names}
    print("\nTight gate held-out lead over the heuristic (from the files named in gate_lead) vs violation rate")
    for n in names:
        ld = leads[n]
        txt = "n/a" if ld is None else f"{ld[0]:+.3f} [{ld[1]:+.3f}, {ld[2]:+.3f}]"
        print(f"  {n:22s} lead {txt:28s} violations all {summary[n]['all']['rate'][0]:.3f}"
              f"  lose_hp {summary[n]['lose_hp']['rate'][0]:.3f}  cost {summary[n]['cost']['rate'][0]:.3f}"
              f"  wrong share of moved {summary[n]['all']['wrong_share']:.3f}")
    comp = [n for n in names if leads[n] is not None and NETS[n][1] in ("night", "rung4")]
    corr = {}
    if len(comp) >= 4:
        x = np.array([leads[n][0] for n in comp])
        for prim in PRIMITIVES + ("all",):
            y = np.array([summary[n][prim]["rate"][0] for n in comp])
            corr[prim] = spearman(x, y)
        print(f"  Spearman(held-out lead, violation rate) over {len(comp)} night + rung-4 nets: "
              + "  ".join(f"{k} {v:+.2f}" for k, v in corr.items()))
        y = np.array([summary[n]["all"]["wrong_share"] for n in comp])
        corr["all_wrong_share"] = spearman(x, y)
        print(f"  Spearman(held-out lead, wrong share of moved, all): {corr['all_wrong_share']:+.2f}")
    with open(os.path.join(OUT, f"summary-{args.states}-tol{args.tol:g}.json"), "w") as fh:
        json.dump({"tol": args.tol, "states": len(states), "clusters": len(set(clusters)), "summary": summary,
                   "paired": diffs, "nets": {n: NETS[n] for n in names}, "leads": leads,
                   "spearman_lead_vs_rate": corr, "pool": pool_context()}, fh, indent=1)
    print(f"\n{time.time() - t0:.1f}s total")


if __name__ == "__main__":
    main()
