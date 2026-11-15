"""HP bonus at the leaves (start-HP spec's zero-training check): a net plays
the run-HP fights at one turn with its leaf value plus `c` x the player's
HP lost so far: c x (HP - start HP). All leaves of one decision share the
start HP, so among leaves the bonus is the HP price the net is missing (HP
price probe: ~0.001 per HP in hallways against its labels' 0.01-0.02);
centring it on the start HP keeps unfinished leaves on the scale of
finished combats, which search scores with the engine's own score (a bare
c x HP made every unfinished leaf look ~0.5 better than winning now). The
start HP comes from the encoder's `start_hp` column (docs/specs/start-hp.md),
asked for after the net's own player columns and stripped before its
forward pass. Paired by fight
with a `ladder.py runhp` record of the same net (same fights: block 6000
on), which also holds the heuristic's HP lost.

    python scripts/analysis/hp_bonus_runhp.py --net runs/<id>/model.pt --base results/ladder/runhp/0011.json --c 0.01 --out results/probes/hp_bonus-c0.01.json
"""

import argparse
import collections
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import ladder  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import stsnet  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--net", required=True)
ap.add_argument("--base", required=True, help="runhp record of the same net, same fights")
ap.add_argument("--c", type=float, required=True)
ap.add_argument("--scaled", action="store_true", help="bonus x the net's value / 2 (~P(win)): the label's HP price is w / 100 x P(win)")
ap.add_argument("--pairs", type=int, default=2000)
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--out", required=True)
args = ap.parse_args()

base = json.load(open(args.base))
assert os.path.normpath(base["candidate"]).endswith(os.path.normpath(args.net)) or \
    os.path.normpath(args.net).endswith(os.path.normpath(base["candidate"])), (base["candidate"], args.net)
assert base["first_block"] == ladder.RUNHP_BLOCK0 and base.get("cand_search", "one-turn") == "one-turn"
by_seed = {(p["cell"], p["seed"]): p for p in base["pairs_played"]}

model, norm, meta = stsnet.load(args.net)
cols = meta["columns"]
feats = sts.Features(meta["card_repr"], **{k: meta.get(k) for k in stsnet.VOCAB_KEYS},
                     columns={**cols, "player": cols["player"] + ["start_hp"]}, row_kinds=meta.get("row_kinds"),
                     piles=meta.get("piles"), lookahead=bool(meta.get("lookahead")), rates=bool(meta.get("rates")),
                     start_hp=True)
assert feats.player_names[-1] == "start_hp"
net = stsnet.Evaluator(model, norm)
HP = feats.player_names.index("hp")


def bonus(batch):
    p = np.asarray(batch["player"])
    v = net({**batch, "player": np.ascontiguousarray(p[:, :-1])})
    scale = np.clip(v / 2, 0, 1) if args.scaled else 1.0
    return v + args.c * scale * (p[:, HP] - p[:, -1])


bonus.features = feats
ev = bench.Evaluator(f"{args.net}+hp{args.c}{'s' if args.scaled else ''}", bonus, feats, bonus)

cells = ladder.pool_cells()
max_hp = {c["character"]: selfplay.max_hp(c["character"]) for c in cells}
specs, b = [], ladder.RUNHP_BLOCK0
while len(specs) < args.pairs:
    specs += [{**s, "hp": ladder.run_hp(s, max_hp[s["character"]])} for s in ladder.block(b, cells)]
    b += 1
specs = specs[:args.pairs]
t0 = time.time()
res = bench.run_specs(specs, ev=ev, search={"limit": bench.LIMIT, "threads": args.threads})
rows = []
for s, r in zip(specs, res):
    p = by_seed[(s["cell"], s["seed"])]
    assert p["hp"] == s["hp"]
    lost = ladder.hp_lost({"won": bool(r["won"]), "hp_start": r["hp_start"], "hp_end": r["hp_end"]})
    rows.append({"group": s["group"], "encounter": s["encounter"], "half": s["half"], "won": int(r["won"]),
                 "base_won": p["cand_won"], "heur_won": p["opp_won"], "lost": lost, "base_lost": p["cand_lost"],
                 "heur_lost": p["opp_lost"]})
out = {"net": args.net, "c": args.c, "scaled": args.scaled, "base": args.base, "pairs": len(rows), "seconds": round(time.time() - t0), "slices": {}}
by = collections.defaultdict(list)
for r in rows:
    by["all"].append(r)
    by["group=" + r["group"]].append(r)
    by["half=" + r["half"]].append(r)
    by["enc=" + r["encounter"]].append(r)
print(f"c={args.c}{' scaled' if args.scaled else ''}  {len(rows)} fights  {out['seconds']} s")
print(f"{'slice':28s} {'n':>5s} {'lost':>6s} {'base':>6s} {'heur':>6s} {'saved (se)':>13s} {'win':>6s} {'base':>6s} {'heur':>6s}")
for k in sorted(by, key=lambda k: (k != "all", not k.startswith("group"), not k.startswith("half"), k)):
    v = by[k]
    d = np.array([r["base_lost"] - r["lost"] for r in v], float)
    m = {f: float(np.mean([r[f] for r in v])) for f in ("lost", "base_lost", "heur_lost", "won", "base_won", "heur_won")}
    out["slices"][k] = {"n": len(v), **m, "saved": float(d.mean()), "saved_se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None}
    print(f"{k:28s} {len(v):5d} {m['lost']:6.2f} {m['base_lost']:6.2f} {m['heur_lost']:6.2f} "
          f"{d.mean():+6.2f} ({out['slices'][k]['saved_se'] or 0:.2f}) {m['won']:6.3f} {m['base_won']:6.3f} {m['heur_won']:6.3f}")
out["rows"] = rows
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
with open(args.out, "w") as f:
    json.dump(out, f, indent=1)
