"""Tests for the tie break's plumbing (docs/specs/finish-faster-tiebreak.md):
the player setting `@tb1` loads it; a `NetEvaluator` built with
`tie_break` keeps every option's value.
Run with `python scripts/tests/test_tie_break.py` or with pytest."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402,F401
from test_turn_start_leaf import _search  # noqa: E402


def test_tie_break_player_settings():
    import bench
    assert bench.player_settings("a/m.pt@hpe0.01@tb1") == ("a/m.pt", {"hp_end_bonus": 0.01, "tie_break": 1.0})
    assert bench.player_settings("a/m.pt@hpb0.01@lcb1@tb1") == (
        "a/m.pt", {"hp_bonus": 0.01, "leaf_clear_block": 1.0, "tie_break": 1.0})
    for bad in ("a/m.pt@tb2", "a/m.pt@tb0", "a/m.pt@tb1@tb1"):
        try:
            bench.player_settings(bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass


def test_tie_break_keeps_values():
    starter = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
    plain = _search(starter, None)
    assert plain == _search(starter, None, tie_break=False)
    broken = _search(starter, None, tie_break=True)
    assert broken["options"] == plain["options"], "the tie break changes no value"
    assert broken["nodes"] == plain["nodes"]


if __name__ == "__main__":
    for name, f in sorted(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print(f"ok  {name}")
