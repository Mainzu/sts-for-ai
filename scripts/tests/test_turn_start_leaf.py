"""Tests for the turn-start leaf's plumbing (docs/specs/turn-start-leaf.md):
a `NetEvaluator` built with `turn_start_leaf` makes search score end-of-turn
leaves after the player's turn-start hooks; off, or with no such power, it
is search bit for bit; the player setting `@tsl1` loads it.
Run with `python scripts/tests/test_turn_start_leaf.py` or with pytest."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402


def test_turn_start_leaf_player_settings():
    import bench
    assert bench.player_settings("a/m.pt@hpb0.01@tsl1") == ("a/m.pt", {"hp_bonus": 0.01, "turn_start_leaf": 1.0})
    assert bench.player_settings("a/m.pt@hpb0.01@dl4") == ("a/m.pt", {"hp_bonus": 0.01, "draw_k": 4.0})
    for bad in ("a/m.pt@tsl2", "a/m.pt@tsl0", "a/m.pt@tsl1@tsl1"):
        try:
            bench.player_settings(bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass


def _search(deck, play_first, **kw):
    import stsnet
    from test_contract import tiny_trained
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta)
    c = sts.Combat(deck, "jaw_worm", seed=3, hp=60)
    if play_first:
        c.step(next(a for a in c.legal_actions() if not a.is_end_turn and a.card == play_first))
    assert c.awaiting_action()
    return sts.search(c, stsnet.rust_evaluator(model, norm, meta, **kw), features=stsnet.features_for(meta), seed=5)


def test_turn_start_leaf_search():
    deck = ["Demon Form"] * 5 + ["Strike"] * 5
    plain = _search(deck, "Demon Form")
    assert plain == _search(deck, "Demon Form", turn_start_leaf=False)
    ticked = _search(deck, "Demon Form", turn_start_leaf=True)
    assert [o[0] for o in ticked["options"]] == [o[0] for o in plain["options"]]
    assert [o[1] for o in ticked["options"]] != [o[1] for o in plain["options"]], "Strength lands in the leaf"
    starter = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
    assert _search(starter, None) == _search(starter, None, turn_start_leaf=True), "no turn-start power: unchanged"


if __name__ == "__main__":
    for name, f in sorted(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print(f"ok  {name}")
