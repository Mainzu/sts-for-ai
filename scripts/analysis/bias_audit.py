"""Bias audit, first slice (docs/specs/bias-audit.md; review 2026-11-02
rank 5): does the net's leaf price enemy Strength and Poison as the
outcome does?

Decision states come from gauntlet elite and boss fights, entered at the
product player's HP there and played with the one-turn champion. Each state
gets variants with one living enemy's Strength or Poison raised
(`Combat.with_monster_power`). Per variant: the net's static value change (leaf delta) and the change in the play-out outcome
(K play-outs per variant with the one-turn champion, the same K seeds for
every variant: common random numbers), on the label's scale (`hp_scale`
with the net's `hp_weight`). Ratio leaf / play-out far from 1 names a bias.

    python scripts/analysis/bias_audit.py --states 300 --threads 3 --out results/probes/bias_audit.json
"""

import argparse
import collections
import json
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import gauntlet  # noqa: E402
import sts  # noqa: E402

NET = "runs/2026-11-01-burst8hp2-s1-9f89b6f/model.pt"
POLICY = NET + "@hpb0.01"
PRODUCT = "results/gauntlet/champion-hpe0.01-two.json"
WIN_FLOOR = 0.1  # learn.WIN_FLOOR
PERTURB = (("Strength", 2), ("Strength", 4), ("Poison", 3), ("Poison", 6))


def hp_scale(score, w):
    """learn.hp_scale: a win 2 - w x (2 - score), at least WIN_FLOOR; a loss 0."""
    s = np.asarray(score, np.float64)
    return np.where(s > 0, np.maximum(2 - w * (2 - s), WIN_FLOOR), s)


def fights(product, n_fights):
    """[(spec, group)] of elite and boss fights the product reached, in
    sequence order, at the product's entry HP."""
    rows = {r["i"]: r for r in product["sequences"]}
    out = []
    for s in gauntlet.sequences(len(rows)):
        if s["i"] not in rows:
            continue
        floors = rows[s["i"]]["floors"]
        for k, f in enumerate(s["fights"]):
            if f["kind"] in ("elite", "boss") and k < len(floors):
                assert floors[k]["encounter"] == f["encounter"]
                out.append({"encounter": f["encounter"], "deck": s["deck"], "seed": f["seed"],
                            "hp": floors[k]["hp_start"], "character": s["character"], "group": f["group"],
                            "i": s["i"], "floor": k})
                if len(out) == n_fights:
                    return out
    return out


def mean_se(xs):
    xs = np.asarray(xs, np.float64)
    return float(xs.mean()), float(xs.std(ddof=1) / np.sqrt(len(xs))) if len(xs) > 1 else 0.0


def ratio_se(a, b):
    """Mean(a) / mean(b) with a delta-method se (paired rows)."""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    ma, mb = a.mean(), b.mean()
    if len(a) < 2 or mb == 0:
        return None, None
    r = ma / mb
    cov = np.cov(a, b)
    var = (cov[0, 0] - 2 * r * cov[0, 1] + r * r * cov[1, 1]) / (len(a) * mb * mb)
    return float(r), float(np.sqrt(max(var, 0)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--states", type=int, default=300)
    ap.add_argument("--per-fight", type=int, default=2)
    ap.add_argument("--k", type=int, default=16, help="play-outs per variant")
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--net", default=NET)
    ap.add_argument("--policy", default=POLICY)
    ap.add_argument("--product", default=PRODUCT)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    with open(os.path.join(os.path.dirname(args.net), "config.json"), encoding="utf-8") as f:
        w = json.load(f).get("hp_weight") or 1
    with open(args.product, encoding="utf-8") as f:
        product = json.load(f)
    leaf = bench.load_evaluator(args.net)
    pol = bench.load_evaluator(args.policy)
    specs = fights(product, -(-args.states // args.per_fight))
    rng = random.Random(1)
    seeds = np.random.default_rng(20261102)
    rows, t0 = [], time.perf_counter()
    for spec in specs:
        c = sts.Combat(spec["deck"], spec["encounter"], seed=spec["seed"], hp=spec["hp"], character=spec["character"])
        states = []
        while not c.is_over() and c.turn() <= sts.PLAY_TURN_LIMIT:
            if c.awaiting_action():
                states.append(c.clone())
                c.step(sts.search(c, pol.evaluator, features=pol.features, limit=bench.LIMIT)["action"])
            else:
                c.advance()
        for st in rng.sample(states, min(args.per_fight, len(states))):
            alive = [m["slot"] for m in st.board()["monsters"]]
            if not alive:
                continue
            slot = rng.choice(alive)
            variants = [bytes(x.encode()) for x in [st] + [st.with_monster_power(slot, n, a) for n, a in PERTURB]]
            v = np.asarray(leaf.static(leaf.features.encode([sts.Combat.decode(x) for x in variants],
                                                            heuristic=True)), np.float64)
            ks = [int(x) for x in seeds.integers(2**63, size=args.k)]
            res = sts.play_on([sts.Combat.decode(x, seed=s) for x in variants for s in ks],
                              evaluator=pol.evaluator, features=pol.features, limit=bench.LIMIT,
                              threads=args.threads)
            out = hp_scale([r["score"] for r in res], w).reshape(len(variants), args.k)
            row = {"i": spec["i"], "floor": spec["floor"], "encounter": spec["encounter"], "group": spec["group"],
                   "turn": st.turn(), "hp": st.player_hp(), "slot": slot,
                   "leaf0": float(v[0]), "play0": float(out[0].mean())}
            for j, (n, a) in enumerate(PERTURB, 1):
                row[f"{n}+{a}"] = {"leaf": float(v[j] - v[0]), "play": float((out[j] - out[0]).mean())}
            rows.append(row)
            if len(rows) >= args.states:
                break
        print(f"{len(rows)} states, {time.perf_counter() - t0:.0f} s", flush=True)
        if len(rows) >= args.states:
            break

    keys = [f"{n}+{a}" for n, a in PERTURB]
    by = collections.defaultdict(list)
    for r in rows:
        by["all"].append(r)
        by["group=" + r["group"]].append(r)
        by["enc=" + r["encounter"]].append(r)
    summary = {}
    print(f"leaf delta vs play-out delta (label scale, w {w}); ratio = leaf / play-out")
    print(f"{'slice':26s} {'n':>4s} {'leaf0':>6s} {'play0':>6s}  " + "  ".join(f"{k:>30s}" for k in keys))
    for name in sorted(by, key=lambda k: (k != "all", k)):
        rs = by[name]
        s = {"n": len(rs), "leaf0": mean_se([r["leaf0"] for r in rs]), "play0": mean_se([r["play0"] for r in rs])}
        cells = []
        for k in keys:
            lv, pv = [r[k]["leaf"] for r in rs], [r[k]["play"] for r in rs]
            ratio = ratio_se(lv, pv)
            s[k] = {"leaf": mean_se(lv), "play": mean_se(pv), "ratio": ratio}
            rt = f"{ratio[0]:+.2f}({ratio[1]:.2f})" if ratio[0] is not None else "-"
            cells.append(f"{s[k]['leaf'][0]:+.3f} {s[k]['play'][0]:+.3f}({s[k]['play'][1]:.3f}) {rt:>12s}")
        summary[name] = s
        print(f"{name:26s} {len(rs):4d} {s['leaf0'][0]:6.3f} {s['play0'][0]:6.3f}  " + "  ".join(f"{c:>30s}" for c in cells))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"settings": {k: v for k, v in vars(args).items() if k != "out"}, "hp_weight": w,
                   "summary": summary, "rows": rows}, f, indent=1)
    print(f"{args.out}: {len(rows)} states, {time.perf_counter() - t0:.0f} s")


if __name__ == "__main__":
    main()
