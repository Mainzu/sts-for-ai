"""Leaf numbers probe (docs/specs/leaf-blind-numbers.md): the pack read's
fights for `without`, Disarm, Impervious and Intimidate, played by the 10-29
net; at every played EndTurn the plain leaf search scores, its form
(step 1) and the net's and the heuristic's value change for perturbations of
its numbers against their true worth (step 2), se over fights.

    .venv/Scripts/python scripts/analysis/leaf_numbers_probe.py run --threads 3
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
import pack_cards_read as pcr  # noqa: E402
import selfplay  # noqa: E402

SETS = (pcr.WITHOUT, "Disarm", "Impervious", "Intimidate")
OUT = "results/leaf_numbers/probe.json"
BLOCKS = (10, 20, 30)
PERTURBATIONS = ("block0",) + tuple(f"block+{b}" for b in BLOCKS) + ("str-2", "weak+1")
# Written before the run (the spec's Predictions).
PREDICTION = {
    "forms": "draw leaves outnumber monster_rolls; monster_rolls 20-50%",
    "impervious_block": "Impervious monster_rolls leaves hold mean block over 10, without under 5",
    "block0": "net pays about +2 HP for 20 leftover block; even odds mispriced",
    "str-2": "net change positive but under half the true-worth estimate: mispriced, likely",
    "weak+1": "within the factor of two: priced right",
}


def first_living(nums):
    return next((i for i, m in enumerate(nums) if m[0]), None)


def leaf_rows(leaf, score):
    """{perturbation: (net change, heuristic change, true worth)} in HP for
    one leaf (absent when it doesn't apply), plus the leaf's own numbers.
    `score(combats)` is what search sees."""
    form = leaf.leaf_form
    block, energy = leaf.player_block_energy
    nums = leaf.monster_numbers()
    edits, worth = {}, {}
    if form == "monster_rolls":
        edits["block0"], worth["block0"] = leaf.with_player_block(0), 0.0
        for b in BLOCKS:
            edits[f"block+{b}"], worth[f"block+{b}"] = leaf.with_player_block(block + b), 0.0
    # At monster_rolls the rolling monster still shows the move it just used
    # (agent.rs intent_known), so its intent is no true worth: draw and
    # decision leaves only.
    slot = first_living(nums) if form not in ("over", "monster_rolls") else None
    if slot is not None:
        rounds = leaf.heuristic_parts()[2]
        for key, power, n in (("str-2", "Strength", -2), ("weak+1", "Weak", 1)):
            e = leaf.with_monster_power(slot, power, n)
            d_intent = nums[slot][3] - e.monster_numbers()[slot][3]
            edits[key], worth[key] = e, float(d_intent * (rounds if key == "str-2" else 1.0))
    keys = list(edits)
    combats = [leaf] + [edits[k] for k in keys]
    v = np.asarray(score(combats), np.float64)
    h = np.array([c.heuristic_parts()[0] for c in combats], np.float64)
    sign = {k: (-1.0 if k == "block0" else 1.0) for k in keys}  # block0: price of the leftover block
    out = {k: (100 * sign[k] * (v[i + 1] - v[0]), 100 * sign[k] * (h[i + 1] - h[0]), worth[k])
           for i, k in enumerate(keys)}
    return {"form": form, "block": int(block), "energy": int(energy),
            "neg_strength": any(m[0] and m[4] < 0 for m in nums),
            "weak": any(m[0] and m[5] > 0 for m in nums), "edits": out}


def cluster_mean_se(groups):
    """(mean, se, units) over clusters: each non-empty list's mean is one unit."""
    m = np.array([np.mean(g) for g in groups if len(g)], np.float64)
    if len(m) == 0:
        return None, None, 0
    return float(m.mean()), (float(m.std(ddof=1) / np.sqrt(len(m))) if len(m) > 1 else None), len(m)


def mispriced(key, net, worth):
    """The spec's rule on (mean, se) pairs: wrong sign by 2 se; `block*` more
    than 2 HP from 0 by 2 se; `str-2`/`weak+1` outside half to twice the
    true worth by 2 se."""
    d, se = net
    w = worth[0]
    if d is None or se is None:
        return None
    if key.startswith("block"):
        return bool(abs(d) - 2.0 > 2 * se)
    if w is None or w == 0:
        return bool(abs(d) > 2 * se)
    a = d * float(np.sign(w))
    if a < -2 * se:
        return True
    return bool(a + 2 * se < 0.5 * abs(w) or a - 2 * se > 2.0 * abs(w))


def summarise(per_set):
    """Per set: form shares, block at monster_rolls, flag shares, and per
    perturbation net/heuristic change and true worth (se over fights)."""
    out = {}
    for s, fights in per_set.items():
        leaves = [x for f in fights for x in f]
        n = len(leaves)
        forms = {}
        for x in leaves:
            forms[x["form"]] = forms.get(x["form"], 0) + 1
        row = {"fights": len(fights), "leaves": n, "forms": {k: v / n for k, v in sorted(forms.items())},
               "mr_block": cluster_mean_se([[x["block"] for x in f if x["form"] == "monster_rolls"] for f in fights]),
               "mr_energy": cluster_mean_se([[x["energy"] for x in f if x["form"] == "monster_rolls"] for f in fights]),
               "neg_strength_share": sum(x["neg_strength"] for x in leaves) / n if n else None,
               "weak_share": sum(x["weak"] for x in leaves) / n if n else None, "perturbations": {}}
        for k in PERTURBATIONS:
            col = lambda j: [[x["edits"][k][j] for x in f if k in x["edits"]] for f in fights]  # noqa: E731
            net, heur, worth = cluster_mean_se(col(0)), cluster_mean_se(col(1)), cluster_mean_se(col(2))
            by_form = {}
            for form in ("monster_rolls", "draw"):
                fc = lambda j: [[x["edits"][k][j] for x in f if k in x["edits"] and x["form"] == form]  # noqa: E731
                                for f in fights]
                by_form[form] = {"net": cluster_mean_se(fc(0)), "worth": cluster_mean_se(fc(2))}
            row["perturbations"][k] = {"net": net, "heuristic": heur, "worth": worth,
                                       "mispriced": mispriced(k, net[:2], worth[:2]), "by_form": by_form}
        out[s] = row
    return out


def run(args):
    selfplay.load_content(pcr.PACK)
    with open(pcr.TIGHT2, encoding="utf-8") as f:
        held = json.load(f)["halves"]["held_out"]
    fs = [f for f in pcr.fights(held, list(SETS[1:])) if f["set"] in SETS]
    if args.limit:
        keep = set(sorted({f["cell"] for f in fs})[:args.limit])
        fs = [f for f in fs if f["cell"] in keep]
    ev = bench.load_evaluator(args.net)
    score = ev.evaluator.score
    search = {"limit": bench.LIMIT, "threads": args.threads}
    per_set, t = {}, time.time()
    for s in SETS:
        idx = [i for i, f in enumerate(fs) if f["set"] == s]
        res = bench.run_specs([fs[i] for i in idx], ev=ev, record=True, search=search)
        per_set[s] = [[leaf_rows(st.after_end_turn(), score) for st, a in zip(r["states"], r["actions"])
                       if a.is_end_turn] for r in res]
        print(f"  {s}: {len(idx)} fights, {sum(map(len, per_set[s]))} leaves ({time.time() - t:.0f}s)", flush=True)
    summary = summarise(per_set)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"net": args.net, "pack": pcr.PACK, "limit": args.limit, "prediction": PREDICTION,
                   "summary": summary}, f, indent=1)
    print_table(summary)
    print(f"-> {args.out}")


def print_table(summary):
    fmt = lambda r: "-" if r[0] is None else (f"{r[0]:+.2f}" + (f" ({r[1]:.2f})" if r[1] is not None else ""))  # noqa: E731
    print("| set | leaves | monster_rolls | draw | block at monster_rolls | Str<0 | Weak>0 |")
    print("|---|---|---|---|---|---|---|")
    for s, r in summary.items():
        print(f"| {s} | {r['leaves']} | {r['forms'].get('monster_rolls', 0):.2f} | {r['forms'].get('draw', 0):.2f} | "
              f"{fmt(r['mr_block'])} | {r['neg_strength_share']:.2f} | {r['weak_share']:.2f} |")
    print("\n| set | perturbation | net HP | heuristic HP | true worth | mispriced |")
    print("|---|---|---|---|---|---|")
    for s, r in summary.items():
        for k, p in r["perturbations"].items():
            print(f"| {s} | {k} | {fmt(p['net'])} | {fmt(p['heuristic'])} | {fmt(p['worth'])} | {p['mispriced']} |")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--net", default=pcr.NET)
    r.add_argument("--threads", type=int, default=3)
    r.add_argument("--limit", type=int, default=0, help="first N cells only (a check)")
    r.add_argument("--out", default=OUT)
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
