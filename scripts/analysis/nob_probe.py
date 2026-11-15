"""Nob probe (manager, 2026-11-01): the HP bonus makes the champion die to
Gremlin Nob at high HP on the gauntlet's first elite (floor 6). Nob gains
Strength whenever the player plays a skill, so blocking is punished: does
the bonus make the net play more skills against Nob?

Fights: every gauntlet sequence (first 500) whose first elite is
gremlin_nob, at a fixed start HP (default 70, about where these fights
start). Each player plays every fight with one-turn search; per fight:
won, turns, end HP, skills / attacks / powers played, Nob's damage taken by
the player.

    python scripts/analysis/nob_probe.py --players heuristic <net.pt> <net.pt>@hpb0.01 --threads 4 --out results/probes/nob-probe.json
"""

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import gauntlet  # noqa: E402
import sts  # noqa: E402
from decision_diff import card_type  # noqa: E402

TURN_LIMIT = sts.PLAY_TURN_LIMIT  # as play's turn limit
_EV = {}


def ev(spec):
    if spec not in _EV:
        _EV[spec] = bench.load_evaluator(spec)
    return _EV[spec]


def play(job):
    s, player = job
    c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"])
    kinds = {"attack": 0, "skill": 0, "power": 0}
    while not c.is_over() and c.turn() <= TURN_LIMIT:
        kw = {} if player == "heuristic" else {"evaluator": ev(player).evaluator, "features": ev(player).features}
        r = sts.search(c, limit=bench.LIMIT, **kw)
        t = card_type(r["action"].card)
        if t in kinds:
            kinds[t] += 1
        c.step(r["action"])
    won = bool(c.is_over() and c.won())
    return {"won": won, "turns": c.turn(), "hp_end": c.player_hp() if won else 0, **kinds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", nargs="+", required=True)
    ap.add_argument("--hp", type=int, default=70)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    specs = []
    for s in gauntlet.sequences(500):
        f = s["fights"][5]
        if f["encounter"] == "gremlin_nob":
            specs.append({"i": s["i"], "half": s["half"], "encounter": f["encounter"], "deck": s["deck"],
                          "seed": f["seed"], "hp": a.hp, "character": s["character"]})
    out = {"hp": a.hp, "fights": len(specs), "players": {}}
    with ProcessPoolExecutor(a.threads) as pool:
        for p in a.players:
            rs = list(pool.map(play, [(s, p) for s in specs], chunksize=4))
            agg = {k: float(np.mean([r[k] for r in rs])) for k in ("won", "turns", "hp_end", "attack", "skill", "power")}
            agg["skills_per_turn"] = float(np.mean([r["skill"] / max(1, r["turns"]) for r in rs]))
            out["players"][p] = {**agg, "rows": rs}
            print(p, {k: round(v, 3) for k, v in agg.items()}, flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
