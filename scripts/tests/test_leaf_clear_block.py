"""Tests for the leaf clear block's plumbing (docs/specs/leaf-clear-block.md):
the player setting `@lcb1` loads it; a `NetEvaluator` built with
`leaf_clear_block` changes the leaf values only where turns end with block.
Run with `python scripts/tests/test_leaf_clear_block.py` or with pytest."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
from test_turn_start_leaf import _search  # noqa: E402


def test_leaf_clear_block_player_settings():
    import bench
    assert bench.player_settings("a/m.pt@hpb0.01@lcb1") == ("a/m.pt", {"hp_bonus": 0.01, "leaf_clear_block": 1.0})
    assert bench.player_settings("a/m.pt@hpb0.01@lcb1@tsl1") == (
        "a/m.pt", {"hp_bonus": 0.01, "leaf_clear_block": 1.0, "turn_start_leaf": 1.0})
    for bad in ("a/m.pt@lcb2", "a/m.pt@lcb0", "a/m.pt@lcb1@lcb1"):
        try:
            bench.player_settings(bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass


def test_leaf_clear_block_search():
    deck = ["Defend"] * 6 + ["Strike"] * 4
    plain = _search(deck, "Defend")
    assert plain == _search(deck, "Defend", leaf_clear_block=False)
    cleared = _search(deck, "Defend", leaf_clear_block=True)
    assert [o[0] for o in cleared["options"]] == [o[0] for o in plain["options"]]
    assert [o[1] for o in cleared["options"]] != [o[1] for o in plain["options"]], "leftover block leaves the leaf"


if __name__ == "__main__":
    for name, f in sorted(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print(f"ok  {name}")
