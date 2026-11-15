"""Backlog 82/85 probe: replay recorded real-game decisions through the
product's two-turn search with and without a leaf fix, and report the
decisions where the plain search passes a winning option and the fixed one
doesn't.

    python scripts/analysis/stall_probe.py <record dir>... [--fix @wc1] [--only floor:turn,...] [--out file.json]

Each decision's view becomes a Combat (`Combat.from_view`, as the bridge's
search does) and both players search it with `depth_paired.decide` (the
bridge's own call). A winning option is one whose first action wins the
fight at once (`real_game.winning_options`). Output: one line per decision
where the plain pick isn't a win but a winning option exists (the strict
cases), with the fixed player's pick. Scratch output: only `--out`.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]

import bench  # noqa: E402
import ladder  # noqa: E402
import real_game  # noqa: E402
import depth_paired  # noqa: E402
import sts  # noqa: E402

ELITES = {"Lagavulin", "Gremlin Nob", "GremlinNob", "Sentry"}


def group_of(view):
    if view.get("boss_fight"):
        return "boss"
    names = {m["name"] for m in view["monsters"]}
    return "elite" if names & ELITES else "hallway"


def kills_this_turn(c, d, seed):
    """Whether decision `d`'s planned actions (the bridge's play) end the fight
    before the turn ends: a pick that isn't a win itself can still play on
    to the kill (Defend+, then Rampage)."""
    e = c.with_seed(seed)
    for a in depth_paired.planned(d, True):
        if a.kind == "end_turn" or str(a) == "EndTurn":
            break
        e.step(a)
        if e.is_over():
            return e.won()
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--player", default=None, help="default: configs/product.json's player")
    ap.add_argument("--fix", default="@wc1", help="setting suffix appended to the player for the fixed arm")
    ap.add_argument("--only", default=None, help="floor:turn,... (default: every decision)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(HERE))
    player = a.player or json.load(open(os.path.join(root, "configs", "product.json")))["player"]
    real_game.load_packs()
    plain = bench.load_evaluator(player)
    fixed = bench.load_evaluator(player + a.fix)
    two = {"limit": bench.LIMIT, **ladder.TWO_TURN}
    only = {tuple(map(int, x.split(":"))) for x in a.only.split(",")} if a.only else None
    rows = []
    for d in a.dirs:
        for n, line in enumerate(open(os.path.join(d, "decisions.jsonl"), encoding="utf-8")):
            r = json.loads(line)
            if "view" not in r:
                continue
            if only and (r["floor"], r["view"]["turn"]) not in only:
                continue
            view = r["view"]
            try:
                c = sts.Combat.from_view(view, seed=n, group=group_of(view))
            except Exception as e:  # a state the engine can't rebuild
                rows.append({"dir": d, "n": n, "floor": r["floor"], "turn": r["view"]["turn"], "error": str(e)[:80]})
                continue
            p = depth_paired.decide(c, plain, two, None, n, 0, 3, -1.0)
            wins = real_game.winning_options(c, p["r1"]["options"], n)
            if not wins or p["pick"] in wins:
                continue
            f = depth_paired.decide(c, fixed, two, None, n, 0, 3, -1.0)
            row = {"dir": os.path.basename(d), "n": n, "floor": r["floor"], "turn": r["view"]["turn"], "wins": wins, "plain_pick": p["pick"],
                   "fixed_pick": f["pick"], "fixed_wins": f["pick"] in wins, "plain_kills": kills_this_turn(c, p, n), "fixed_kills": kills_this_turn(c, f, n), "recorded_pick": r["pick"]}
            rows.append(row)
            print(json.dumps(row), flush=True)
    cases = [r for r in rows if "wins" in r]
    took = sum(1 for r in cases if r["fixed_kills"] and not r["plain_kills"])
    lost = sum(1 for r in cases if r["plain_kills"] and not r["fixed_kills"])
    print(f"cases {len(cases)} (a first-action win exists, plain pick isn't one); plain plays on to the kill in {sum(r['plain_kills'] for r in cases)}, "
          f"fixed in {sum(r['fixed_kills'] for r in cases)}; fixed newly kills {took}, newly stops killing {lost}; unbuildable {sum(1 for r in rows if 'error' in r)}")
    if a.out:
        json.dump(rows, open(a.out, "w"), indent=1)


main()
