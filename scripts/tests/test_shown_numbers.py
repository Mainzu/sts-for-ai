"""Tests for the shown-numbers and exhaust-hidden flags' plumbing
(docs/specs/shown-card-numbers.md): the player settings `@sn1` and `@xh1`
parse, `sts.Features` and `NetEvaluator` take the flags, and off is today.
The flags are the net's: its meta records them (missing = off), the
encoders read them from there, and a player setting that disagrees is
refused (engine audit entry 1). Per-hit shown damage: py/src/lib.rs tests.
Run with `python scripts/tests/test_shown_numbers.py` or with pytest."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np  # noqa: E402
import sts  # noqa: E402


def test_player_settings():
    import bench
    assert bench.player_settings("a/m.pt@hpb0.01@sn1@xh1") == (
        "a/m.pt", {"hp_bonus": 0.01, "shown_numbers": 1.0, "exhaust_hidden": 1.0})
    for bad in ("a/m.pt@sn2", "a/m.pt@xh0", "a/m.pt@sn1@sn1"):
        try:
            bench.player_settings(bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass


def test_features_flags():
    f = sts.Features(shown_numbers=True, exhaust_hidden=True)
    assert f.shown_numbers and f.exhaust_hidden
    plain = sts.Features()
    assert not plain.shown_numbers and not plain.exhaust_hidden
    c = sts.Combat(["Twin Strike", "Defend", "Inflame", "Strike"] * 3, "jaw_worm", seed=3, hp=80)
    a, b = plain.encode([c]), sts.Features(shown_numbers=False, exhaust_hidden=False).encode([c])
    for k in a:
        assert np.array_equal(a[k], b[k]), k


def test_meta_keys_and_refusal():
    import stsnet
    from test_contract import tiny_trained
    old = {"card_repr": "effects"}
    on = {"card_repr": "effects", "shown_numbers": True, "exhaust_hidden": True}
    assert stsnet.encoder_flags(old) == {"shown_numbers": False, "exhaust_hidden": False}
    assert stsnet.encoder_flags(on, shown_numbers=1.0, exhaust_hidden=None) == {"shown_numbers": True, "exhaust_hidden": True}
    f = stsnet.features_for(on)
    assert f.shown_numbers and f.exhaust_hidden
    g = stsnet.features_for(old)
    assert not g.shown_numbers and not g.exhaust_hidden
    model, norm = tiny_trained(old)
    for bad in (dict(shown_numbers=1.0), dict(exhaust_hidden=True)):
        try:
            stsnet.rust_evaluator(model, norm, old, **bad)
            raise AssertionError(f"accepted {bad} on a net without the keys")
        except ValueError as e:
            assert "disagrees with the net's meta" in str(e)
    try:
        stsnet.rust_evaluator(model, norm, on, shown_numbers=False)
        raise AssertionError("accepted shown_numbers off on a net trained with it")
    except ValueError:
        pass
    # A net trained with the flags loads with or without the setting.
    stsnet.rust_evaluator(model, norm, on)
    stsnet.rust_evaluator(model, norm, on, shown_numbers=1.0, exhaust_hidden=1.0)


def test_training_mode_flags():
    import learn
    import selfplay
    assert learn.feature_mode({"start_hp": True, "shown_numbers": True, "exhaust_hidden": True}) == "effects+start+shown+xhid"
    assert learn.feature_mode({}) == "effects"
    assert selfplay.split_mode("effects+lookahead+rates+start+shown+xhid") == ("effects", True, True, True)
    assert selfplay.split_flags("effects+rates+xhid") == ("effects+rates", False, True)
    f = selfplay.features("effects+shown")
    assert f.shown_numbers and not f.exhaust_hidden
    assert not selfplay.features("effects").shown_numbers


if __name__ == "__main__":
    for name, f in sorted(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
    print("ok")
