"""Tests for check 9's gain computation. Run with
`python scripts/tests/test_granting.py` or with pytest."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import granting  # noqa: E402

E = sts.Action()


def play(card, target=None):
    return sts.Action(card, target)


def test_gain_per_card():
    options = [
        ([play("Strike", 0)], 1.50),
        ([play("Demon Form")], 1.70),
        ([play("Go for the Eyes", 0)], 1.40),
        ([play("Go for the Eyes", 1)], 1.55),
        ([E], 1.20),
    ]
    g = granting.gains(options, {"Demon Form", "Go for the Eyes"})
    assert abs(g["Demon Form"] - (1.70 - 1.55)) < 1e-6
    # Best target of the card minus the best option that doesn't play it.
    assert abs(g["Go for the Eyes"] - (1.55 - 1.70)) < 1e-6


def test_merged_option_counts_as_playing_the_card():
    options = [([play("Rage"), play("Defend")], 1.6), ([E], 1.0)]
    g = granting.gains(options, {"Rage"})
    assert abs(g["Rage"] - 0.6) < 1e-6


def test_mad_gate():
    ref = [0.1, -0.2, 0.3]
    eff = [0.1, -0.1, 0.3]   # MAD 0.0333
    ids = [0.0, 0.0, 0.0]    # MAD 0.2
    assert abs(granting.mad(eff, ref) - 0.1 / 3) < 1e-9
    assert granting.passes(granting.mad(eff, ref), granting.mad(ids, ref))
    assert not granting.passes(0.9, 1.0)


def test_check9_deck_has_two_held_out_cards():
    import numpy as np
    rng = np.random.default_rng(0)
    for _ in range(50):
        d = granting.check9_deck(rng)
        assert sum(c in granting.HELD9 for c in d) >= 2
        assert not any(c in granting.selfplay.HELD_OUT_ALL for c in d)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
