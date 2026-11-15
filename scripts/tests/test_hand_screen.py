"""Tests for the hand-count puzzle screen (scripts/analysis/hand_screen.py):
the adaptive rule and the summary on hand-made cells, and one real puzzle
with the heuristic (seconds)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import bench  # noqa: E402
import hand_screen  # noqa: E402


def cell(regret, nodes=100, cut=False, seconds=1.0):
    return {"regret": regret, "nodes": nodes, "cut": cut, "seconds": seconds}


def test_adaptive_reruns_small_uncut_trees_only():
    four = [cell(0.1, nodes=100), cell(0.1, nodes=30_000), cell(0.1, nodes=100, cut=True), cell(0.1, nodes=100)]
    sixteen = [cell(0.0), cell(0.0), cell(0.0), cell(0.0, cut=True)]
    got = hand_screen.adaptive(four, sixteen, 25_000)
    assert [g["regret"] for g in got] == [0.0, 0.1, 0.1, 0.1]  # big, cut at 4, cut at 16: keep 4's pick
    assert [g["rerun"] for g in got] == [True, False, False, True]
    assert [g["seconds"] for g in got] == [2.0, 1.0, 1.0, 2.0]


def test_summary_pairs_by_puzzle():
    rows = [{"arms": {"4": [cell(0.02), cell(0.0)], "16": [cell(0.0), cell(0.0)]}},
            {"arms": {"4": [cell(0.04), cell(0.04)], "16": [cell(0.02), cell(0.02)]}}]
    s = hand_screen.summary(rows, ["4", "16"])
    assert abs(s["4"]["regret"] - 0.025) < 1e-12
    assert abs(s["16"]["minus_4"] - (-0.015)) < 1e-12
    assert abs(s["4"]["regret_share_noisy"] - 0.2) < 1e-12  # puzzle 0 is right on one seed: 0.01 of 0.05


def test_one_puzzle_runs():
    pz = bench.load_puzzles()
    row = next(r for r in pz["halves"]["train"] if r["horizon"] >= 1)
    out = hand_screen.puzzle((row, "heuristic", [4, 16], 2, 2000))
    assert set(out) == {"4", "16"} and all(len(v) == 2 for v in out.values())
    best = max(o[1] for o in row["options"])
    assert all(0.0 <= c["regret"] <= best - min(o[1] for o in row["options"]) + 1e-9 for v in out.values() for c in v)


def test_guarded_rerun_rule():
    """The adaptive rule in depth_paired.guarded_fight: below 0 nodes it never
    re-searches (the plain player's fight); re-searching with the same hand
    count changes nothing but the count and the nodes searched (the rerun's
    tree adds its own)."""
    import depth_paired
    spec = depth_paired.fights("held_out", ("hallway",), 1)[0]
    two = {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 20_000}
    job = lambda t: (spec, t, -1.0, "heuristic", 0, 3, True, True)  # noqa: E731
    plain = depth_paired.guarded_fight(job(two))
    never = depth_paired.guarded_fight(job({**two, "rerun": {"k": 16, "below": 0}}))
    same = depth_paired.guarded_fight(job({**two, "rerun": {"k": 2, "below": 10**9}}))
    assert never.pop("reruns") == 0 and never == plain
    assert same.pop("reruns") > 0 and same.pop("nodes") > plain["nodes"]
    assert same == {k: v for k, v in plain.items() if k != "nodes"}


def test_read_require_save(tmp_path):
    """depth_probe read --require-save: exit 0 at or past the bar, 1 under it."""
    import json
    import depth_probe
    import pytest
    f = {"i": 0, "floor": 8, "hp_start": 50, "won_obs": True, "hp_end_obs": 30, "won": True, "hp_end": 31}
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"settings": {}, "fights": [f, {**f, "i": 1}]}))
    depth_probe.main(["read", str(path), "--require-save", "1"])
    with pytest.raises(SystemExit):
        depth_probe.main(["read", str(path), "--require-save", "1.5"])
