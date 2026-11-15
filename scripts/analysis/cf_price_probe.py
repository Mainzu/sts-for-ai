"""Counterfactual state price probe (docs/specs/counterfactual-state-price.md,
step 1; no games scored): the leaf-numbers probe's fights and leaves, the
`cf_price` term's change for four perturbations against their worths, se
over fights.

    .venv/Scripts/python scripts/analysis/cf_price_probe.py run --threads 3
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import leaf_numbers_probe as lnp  # noqa: E402
import pack_cards_read as pcr  # noqa: E402
import selfplay  # noqa: E402

OUT = "results/cf_price/probe.json"
KEYS = ("str-2", "weak+1", "ritual+2", "demonform+2")
# The charter's strict ranges (measurement/leaf-numbers@probe's worths, set means).
STRICT = {"str-2": (9.9, 13.0), "weak+1": (2.2, 2.7)}
ROLLOUT_ROUNDS, ROLLOUT_SEEDS = 30, 4
PRECISE = 0.25
PREDICTION = {
    "str-2": "inside half to twice its worth (the window plus remaining rounds is the worth's own form): even",
    "weak+1": "inside (Weak 1 is capped at one round): likely",
    "ritual+2": "inside against the greedy rollout: even (growth extrapolated from two rounds)",
    "demonform+2": "inside against the greedy rollout: even",
    "verdict": "go if three of four are inside (not mispriced and precise) on every set",
}


def rollout_worth(leaf, edit):
    """HP worth of `edit` over `leaf` playing the greedy policy to the end
    (at most ROLLOUT_ROUNDS rounds), shared seeds, enemy HP at q."""
    ehp = sum(m[1] for m in leaf.monster_numbers() if m[0])
    q = leaf.heuristic_parts()[1] / ehp if ehp > 0 else 0.0
    v = []
    for i in range(ROLLOUT_SEEDS):
        lw, dw, _ = edit.greedy_rollout(ROLLOUT_ROUNDS, i)
        lo, do, _ = leaf.greedy_rollout(ROLLOUT_ROUNDS, i)
        v.append((lo - lw) + q * (dw - do))
    return float(np.mean(v))


def leaf_rows(leaf, k):
    """{perturbation: (term change, worth)} in HP for one draw or decision
    leaf (None for other forms, as the leaf-numbers probe's Strength/Weak rule)."""
    form = leaf.leaf_form
    if form in ("over", "monster_rolls"):
        return None
    nums = leaf.monster_numbers()
    slot = lnp.first_living(nums)
    if slot is None:
        return None
    rounds = leaf.heuristic_parts()[2]
    base_els = leaf.cf_prices(k)
    base = sum(e[3] for e in base_els)

    def own(e, who, power):
        """Diagnostic: the edited element's own price change (no other element)."""
        get = lambda els: sum(x[3] for x in els if x[0] == who and x[1] == power)  # noqa: E731
        return get(e.cf_prices(k)) - get(base_els)

    out = {}
    for key, power, n in (("str-2", "Strength", -2), ("weak+1", "Weak", 1)):
        e = leaf.with_monster_power(slot, power, n)
        d_intent = nums[slot][3] - e.monster_numbers()[slot][3]
        out[key] = (e.cf_price(k) - base, float(d_intent * (rounds if key == "str-2" else 1.0)), own(e, slot, power))
    for key, who, power, e in (("ritual+2", slot, "Ritual", leaf.with_monster_power(slot, "Ritual", 2)),
                               ("demonform+2", "player", "DemonForm", leaf.with_player_power("DemonForm", 2))):
        out[key] = (e.cf_price(k) - base, rollout_worth(leaf, e), own(e, who, power))
    return out


def summarise(per_set):
    out = {}
    for s, fights in per_set.items():
        row = {"fights": len(fights), "leaves": sum(len(f) for f in fights), "perturbations": {}}
        for key in KEYS:
            col = lambda j: [[x[key][j] for x in f] for f in fights]  # noqa: E731
            term, worth, own = lnp.cluster_mean_se(col(0)), lnp.cluster_mean_se(col(1)), lnp.cluster_mean_se(col(2))
            lo_hi = STRICT.get(key)
            # Precise: the term's se is at most a quarter of the worth, so a
            # pass is not just a wide band.
            precise = term[1] is not None and worth[0] is not None and term[1] <= PRECISE * abs(worth[0])
            row["perturbations"][key] = {
                "term": term, "worth": worth, "mispriced": lnp.mispriced(key, term[:2], worth[:2]), "precise": precise,
                "own": own, "own_mispriced": lnp.mispriced(key, own[:2], worth[:2]),
                "strict_inside": None if lo_hi is None or term[0] is None else bool(lo_hi[0] <= term[0] <= lo_hi[1])}
        out[s] = row
    inside = {k: all(r["perturbations"][k]["mispriced"] is False and r["perturbations"][k]["precise"] for r in out.values())
              for k in KEYS}
    return out, inside


def run(args):
    selfplay.load_content(pcr.PACK)
    with open(pcr.TIGHT2, encoding="utf-8") as f:
        held = json.load(f)["halves"]["held_out"]
    fs = [f for f in pcr.fights(held, list(lnp.SETS[1:])) if f["set"] in lnp.SETS]
    if args.limit:
        keep = set(sorted({f["cell"] for f in fs})[:args.limit])
        fs = [f for f in fs if f["cell"] in keep]
    ev = bench.load_evaluator(args.net)
    search = {"limit": bench.LIMIT, "threads": args.threads}
    per_set, t = {}, time.time()
    for s in lnp.SETS:
        idx = [i for i, f in enumerate(fs) if f["set"] == s]
        res = bench.run_specs([fs[i] for i in idx], ev=ev, record=True, search=search)
        fights = []
        for j, r in enumerate(res):
            rows = [leaf_rows(st.after_end_turn(), args.k) for st, a in zip(r["states"], r["actions"]) if a.is_end_turn]
            fights.append([x for x in rows if x is not None])
            if (j + 1) % 50 == 0:
                print(f"  {s}: {j + 1}/{len(res)} fights ({time.time() - t:.0f}s)", flush=True)
        per_set[s] = fights
        print(f"  {s}: {len(idx)} fights, {sum(map(len, fights))} leaves ({time.time() - t:.0f}s)", flush=True)
    summary, inside = summarise(per_set)
    n_inside = sum(inside.values())
    verdict = "go" if n_inside >= 3 else "fail"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"net": args.net, "pack": pcr.PACK, "k": args.k, "limit": args.limit, "prediction": PREDICTION,
                   "summary": summary, "inside": inside, "verdict": verdict}, f, indent=1)
    fmt = lambda r: "-" if r[0] is None else (f"{r[0]:+.2f}" + (f" ({r[1]:.2f})" if r[1] is not None else ""))  # noqa: E731
    print("| set | perturbation | term HP | worth HP | mispriced | precise | strict range | own price (diagnostic) |")
    print("|---|---|---|---|---|---|---|---|")
    for s, r in summary.items():
        for k, p in r["perturbations"].items():
            print(f"| {s} | {k} | {fmt(p['term'])} | {fmt(p['worth'])} | {p['mispriced']} | {p['precise']} | {p['strict_inside']} | {fmt(p['own'])} |")
    print(f"inside: {inside} -> {verdict}")
    print(f"-> {args.out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--net", default=pcr.NET)
    r.add_argument("--threads", type=int, default=3)
    r.add_argument("--k", type=int, default=4, help="sampled windows per element")
    r.add_argument("--limit", type=int, default=0, help="first N cells only (a check)")
    r.add_argument("--out", default=OUT)
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
