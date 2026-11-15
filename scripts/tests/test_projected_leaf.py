"""The projected leaf's player setting (docs/specs/projected-leaf.md)."""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import bench  # noqa: E402
import sts  # noqa: E402

NET = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt"


def _net():
    here = os.path.join(os.path.dirname(__file__), "..", "..", NET)
    if os.path.exists(here):
        return here
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True,
                            text=True, cwd=os.path.dirname(__file__)).stdout.strip()
    return os.path.join(os.path.dirname(common), NET)


def test_setting_parses():
    base, kw = bench.player_settings("x.pt@hpb0.01@tsl1@pl2")
    assert base == "x.pt" and kw["projected_ticks"] == 2 and kw["turn_start_leaf"] == 1
    for bad in ("x.pt@pl0", "x.pt@pl10", "x.pt@pl1.5", "x.pt@pl2@pl2"):
        try:
            bench.player_settings(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert "projected_ticks" not in bench.player_settings("x.pt@hpb0.01@tsl1")[1]


def test_debuff_setting_parses():
    """`@pd1` (docs/specs/recurring-debuff-leaf.md) needs `@pl<k>`."""
    base, kw = bench.player_settings("x.pt@hpb0.01@tsl1@pl2@pd1")
    assert kw["projected_ticks"] == 2 and kw["projected_debuffs"] == 1
    for bad in ("x.pt@pd1", "x.pt@tsl1@pd1", "x.pt@pl2@pd2", "x.pt@pl2@pd1@pd1"):
        try:
            bench.player_settings(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_projection_changes_a_demon_form_decision():
    net = _net()
    if not os.path.exists(net):
        return  # no net here or in the main checkout
    ev0 = bench.load_evaluator(net + "@hpb0.01@tsl1")
    ev2 = bench.load_evaluator(net + "@hpb0.01@tsl1@pl2")
    deck = ["Demon Form", "Strike", "Strike", "Strike", "Defend", "Defend", "Bash", "Strike", "Defend", "Defend"]
    changed = 0
    for seed in range(12):
        c = sts.Combat(deck, "gremlin_nob", seed=seed, hp=50)
        while not c.is_over() and not c.awaiting_action():
            c.advance()
        a = sts.search(c, ev0.evaluator, features=ev0.features, limit=bench.LIMIT)
        b = sts.search(c, ev2.evaluator, features=ev2.features, limit=bench.LIMIT)
        changed += a["action"] != b["action"] or a["options"] != b["options"]
    assert changed > 0, "the projection moved no score on Demon Form openings"
    res = sts.play_on([sts.Combat(deck, "gremlin_nob", seed=3, hp=50)], evaluator=ev2.evaluator, features=ev2.features,
                      limit=bench.LIMIT, threads=1)
    assert res[0]["turns"] > 0
