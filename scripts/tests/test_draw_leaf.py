"""Tests for the sampled-draw leaf's plumbing (docs/specs/draw-leaf.md): a
`NetEvaluator` built with `draw_k` k makes search score end-of-turn leaves
after k sampled draws; k 0 is search bit for bit; the player setting
`@dl<k>` loads it, and ladder caches tell it from the plain player.
Run with `python scripts/tests/test_draw_leaf.py` or with pytest."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402


def test_draw_leaf_player_settings():
    import bench
    import ladder
    assert bench.player_settings("a/m.pt@hpb0.01@dl4") == ("a/m.pt", {"hp_bonus": 0.01, "draw_k": 4.0})
    for bad in ("a/m.pt@dl4@dl2", "a/m.pt@dl0", "a/m.pt@dl2.5"):
        try:
            bench.player_settings(bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
    with tempfile.TemporaryDirectory() as d:
        net = os.path.join(d, "m.pt")
        with open(net, "wb") as f:
            f.write(b"net")
        assert ladder.player_key(net + "@hpb0.01@dl4") != ladder.player_key(net + "@hpb0.01")


def test_draw_leaf_search():
    import stsnet
    from test_contract import tiny_trained
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta)
    c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4, "jaw_worm", seed=3, hp=60)
    c.step(next(a for a in c.legal_actions() if a.is_end_turn))
    assert c.awaiting_action()
    feats = stsnet.features_for(meta)
    run = lambda ev: sts.search(c, ev, features=feats, seed=5)  # noqa: E731
    plain, zero = run(stsnet.rust_evaluator(model, norm, meta)), run(stsnet.rust_evaluator(model, norm, meta, draw_k=0))
    assert plain == zero
    drawn = run(stsnet.rust_evaluator(model, norm, meta, draw_k=4))
    assert [o[0] for o in drawn["options"]] == [o[0] for o in plain["options"]]
    assert [o[1] for o in drawn["options"]] != [o[1] for o in plain["options"]]
    assert drawn["leaves"] > plain["leaves"]


if __name__ == "__main__":
    for name, f in sorted(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print(f"ok  {name}")
