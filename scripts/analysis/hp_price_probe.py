"""HP price probe (Next N1, HP efficiency): how much does a net's value drop
when only the player's current HP drops?

The label scores a win 2 - w x (start HP - end HP) / 100, but the encoder
has no start-HP column, so a net can't tell HP already lost from HP it
started without. This plays run-HP pool fights (the `ladder.py runhp`
fights) with the net at one turn, samples decision states, lowers the
player's HP by d (`Combat.with_player_hp`, so start HP stays), and
reads the net's static value. Per HP, the label says the value should
fall by about w / 100 x P(win) (more near death). A net pricing HP well
below that trades HP for tempo.

    python scripts/analysis/hp_price_probe.py --net runs/<id>/model.pt --fights 300 --out results/probes/hp_price.json
"""

import argparse
import collections
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import ladder  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--net", required=True)
ap.add_argument("--fights", type=int, default=300)
ap.add_argument("--per-fight", type=int, default=3)
ap.add_argument("--drops", default="3,6,10")
ap.add_argument("--out", required=True)
args = ap.parse_args()
drops = [int(x) for x in args.drops.split(",")]


ev = bench.load_evaluator(args.net)


def value(states):
    return np.asarray(ev.static(ev.features.encode(states, heuristic=True)), np.float64)


cells = ladder.pool_cells()
max_hp = {c["character"]: selfplay.max_hp(c["character"]) for c in cells}
specs, b = [], ladder.RUNHP_BLOCK0
while len(specs) < args.fights:
    specs += [{**s, "hp": ladder.run_hp(s, max_hp[s["character"]])} for s in ladder.block(b, cells)]
    b += 1
specs = specs[:args.fights]
rng = random.Random(1)
rows = []
for s in specs:
    c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"])
    states = []
    while not c.is_over() and c.turn() <= 30:
        if c.awaiting_action():
            if c.player_hp() > max(drops) + 2:
                states.append(c.clone())
            c.step(sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)["action"])
        else:
            c.advance()
    won = bool(c.is_over() and c.won())
    for st in rng.sample(states, min(args.per_fight, len(states))):
        hp = st.player_hp()
        v = value([st] + [st.with_player_hp(hp - d) for d in drops])
        rows.append({"group": s["group"], "encounter": s["encounter"], "hp": hp, "start_hp": s["hp"],
                     "turn": st.turn(), "won": won, "v0": float(v[0]),
                     **{f"slope{d}": float((v[0] - v[k + 1]) / d) for k, d in enumerate(drops)}})

out = {"net": args.net, "drops": drops, "n": len(rows), "slices": {}}
by = collections.defaultdict(list)
for r in rows:
    by["all"].append(r)
    by["group=" + r["group"]].append(r)
    by["turn=" + ("1" if r["turn"] == 1 else "2-3" if r["turn"] <= 3 else "4+")].append(r)
    by["lost_so_far=" + ("0" if r["hp"] >= r["start_hp"] else "1-9" if r["start_hp"] - r["hp"] < 10 else "10+")].append(r)
print(f"value drop per HP of current HP (label: ~w/100 x P(win)); n={len(rows)}")
print(f"{'slice':22s} {'n':>5s} {'v0':>6s} " + " ".join(f"{'d=' + str(d):>14s}" for d in drops))
for k in sorted(by, key=lambda k: (k != "all", k)):
    v = by[k]
    m = {d: (float(np.mean([r[f"slope{d}"] for r in v])), float(np.std([r[f"slope{d}"] for r in v]) / np.sqrt(len(v))))
         for d in drops}
    out["slices"][k] = {"n": len(v), "v0": float(np.mean([r["v0"] for r in v])), "slope": {str(d): m[d] for d in drops}}
    print(f"{k:22s} {len(v):5d} {out['slices'][k]['v0']:6.3f} " + " ".join(f"{m[d][0]:+.4f}({m[d][1]:.4f})" for d in drops))
out["rows"] = rows
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
with open(args.out, "w") as f:
    json.dump(out, f, indent=1)
