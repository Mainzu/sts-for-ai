"""random_world.py's pure parts (docs/specs/random-world-bench.md); no engine play."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import random_world as rw  # noqa: E402

NAMES = [f"GE-T{t}-E{e}" for t in range(4) for e in range(6)][:21] + list(rw.COLLAPSE)


def test_items_nested():
    main, side = rw.pools(NAMES)
    assert len(main) == 21 and not set(rw.COLLAPSE) & set(main)
    k2, k4, k8 = (rw.items(3, k, main) for k in (2, 4, 8))
    assert k4[:2] == k2 and k8[:4] == k4 and len(set(k8)) == 8
    side_items = {m for w in range(rw.SIDE_OFFSET, rw.SIDE_OFFSET + 30) for m in rw.items(w, 8, side)}
    assert set(rw.COLLAPSE) <= side_items


def test_items_deterministic():
    main, _ = rw.pools(NAMES)
    assert rw.items(5, 4, main) == rw.items(5, 4, main)
    assert rw.items(5, 4, main) != rw.items(6, 4, main)


def _row(i, hp, par_loss, raw):
    """A base row: the net loses par_loss on the parent, par_loss + raw[m] with m."""
    seeds = 4
    mk = lambda l: [[True, hp - l]] * seeds  # noqa: E731
    return {"i": i, "floor": 0, "group": "elite", "hp": hp,
            "parent": {"one": mk(par_loss), "heuristic": mk(par_loss)},
            "mods": {m: {"one": mk(par_loss + c), "heuristic": mk(par_loss + c)} for m, c in raw.items()}}


def test_eligible_starts():
    rows = [_row(0, 50, 10, {"a": 35, "b": 10}), _row(1, 50, 10, {"a": 1, "b": 1}), _row(2, 50, 10, {"a": 1, "b": 1})]
    assert [r["i"] for r in rw.eligible(rows, ["a", "b"])] == [1, 2]
    assert [r["i"] for r in rw.eligible(rows, ["a"])] == [0, 1, 2]


def _world(row, its, net_loss, heur_loss, s=4):
    return {"items": its, "starts": [[row["i"], 0]],
            "res": {"one": [[[True, row["hp"] - net_loss]] * s], "heuristic": [[[True, row["hp"] - heur_loss]] * s]}}


def test_world_stats_paired():
    # singles: net pays 3 on a, 2 on b beyond the heuristic (heuristic pays 1 on each)
    row = {"i": 0, "floor": 0, "group": "elite", "hp": 60,
           "parent": {"one": [[True, 50]] * 4, "heuristic": [[True, 50]] * 4},
           "mods": {"a": {"one": [[True, 46]] * 4, "heuristic": [[True, 49]] * 4},
                    "b": {"one": [[True, 47]] * 4, "heuristic": [[True, 49]] * 4}}}
    st = rw.world_stats(_world(row, ["a", "b"], net_loss=20, heur_loss=12), {(0, 0): row})
    assert st["S"] == 5.0 and st["cost"] == (20 - 10) - (12 - 10)


def _table(ratio, noise, n=20, ks=(2, 4, 8), seed=0):
    rng = np.random.default_rng(seed)
    stats = []
    for k in ks:
        for _ in range(n):
            S = 2.0 * k + rng.normal(0, 1)
            stats.append(("main", k, {"cost": ratio * S + rng.normal(0, noise), "S": S, "deaths_net": 0,
                                      "deaths_heur": 0, "deaths_pred": 0, "n_starts": 50}))
    return rw.summarise(stats)


def test_read_additive_go_open():
    add = _table(1.0, 0.5)
    assert rw.verdict(add) == "additive" and add[("main", 4)]["g"][0] < 0 and rw.check_passes(add)
    go = _table(2.0, 0.5)
    assert rw.verdict(go) == "go" and rw.check_passes(go)
    assert rw.verdict(_table(1.5, 30.0)) == "open" and not rw.check_passes(_table(1.5, 30.0))
    assert not rw.check_passes(_table(1.0, 0.5, n=5))  # too few worlds
    assert "verdict (main): additive" in rw.table_text(add)


def _nd_file(world_factor, seeds=3):
    """Two starts at 60 HP; the net loses 10 on the parent, the heuristic 8;
    each single costs the net 2 HP more than the heuristic; one k 2 world."""
    hp = 60
    res = lambda l: [[[True, hp - l]] * seeds] * 2  # noqa: E731
    cells = [{"kind": "parent", "pool": "-", "w": -1, "k": 0, "items": [], "res": {"one": res(10), "heuristic": res(8)}}]
    for m, c in (("a", 5), ("b", 3)):
        cells.append({"kind": "single", "pool": "-", "w": -1, "k": 1, "items": [m],
                      "res": {"one": res(10 + c + 2), "heuristic": res(8 + c)}})
    extra = world_factor * 4  # the summed singles' cost beyond the heuristic is 4
    cells.append({"kind": "world", "pool": "main", "w": 0, "k": 2, "items": ["a", "b"],
                  "res": {"one": res(10 + 8 + 4 + extra - 4), "heuristic": res(8 + 8)}})
    return {"starts": [[0, 0], [1, 0]], "start_hp": [hp, hp], "cells": cells}


def test_nd_world_stats():
    (pool, k, s), = rw.nd_world_stats(_nd_file(1))
    assert (pool, k) == ("main", 2)
    assert s["S"] == 4 and s["cost"] == 4 and s["deaths_net"] == 0
    (_, _, s2), = rw.nd_world_stats(_nd_file(2))
    assert s2["cost"] == 8 and s2["cost"] - 1.5 * s2["S"] > 0


def test_nd_world_stats_below_zero():
    f = _nd_file(20)  # the world costs the net 80 HP more: hp_end far below 0
    (_, _, s), = rw.nd_world_stats(f)
    assert s["cost"] == 80 and s["deaths_net"] == 1 and s["deaths_heur"] == 0


def test_nd_plan_and_resume():
    cells = rw.nd_plan(NAMES, 2, [2, 4], 1)
    assert cells[0]["kind"] == "parent" and sum(c["kind"] == "single" for c in cells) == len(NAMES)
    assert sum(c["kind"] == "world" for c in cells) == 2 * 2 + 1 * 2
    done = [dict(c, res={}) for c in cells[:5]]
    assert rw.nd_todo(cells, done) == cells[5:]


def test_nd_starts_fixed():
    rows = [{"i": i, "floor": 0, "group": "elite" if i % 2 else "hallway"} for i in range(40)]
    a = rw.nd_starts(rows, 5)
    assert a == rw.nd_starts(rows, 5) and len(a) == 5 and all(i % 2 for i, _ in a)
    assert rw.nd_starts(rows, 3) == a[:3]
