"""Tests for the leaf numbers probe (docs/specs/leaf-blind-numbers.md): the
`Combat` leaf and edit methods, and the probe's se and mispricing rule. Run
with `python scripts/tests/test_leaf_numbers_probe.py` or pytest. A few
seconds."""

import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "analysis"))
os.chdir(ROOT)
import sts  # noqa: E402

import leaf_numbers_probe as lnp  # noqa: E402

DECK = ["Defend"] * 6 + ["Strike"] * 4  # mixed: the draw is a chance event


def end_turn_leaf(monster, turns):
    """The plain leaf after defending `turns` turns against `monster`."""
    c = sts.Combat.versus(DECK, [monster], seed=3, hp=80)
    for t in range(turns):
        if t:
            c.step(sts.Action())
        while any(a.card == "Defend" for a in c.legal_actions()):
            c.step(next(a for a in c.legal_actions() if a.card == "Defend"))
    return c, c.after_end_turn()


def test_after_end_turn_forms():
    # Jaw Worm's moves after its first are random: the leaf waits on its roll,
    # holding the block left after its attack.
    c, leaf = end_turn_leaf("Jaw Worm", 2)
    assert leaf.leaf_form == "monster_rolls"
    block, _ = leaf.player_block_energy
    assert block > 0
    assert leaf.with_player_block(0).player_block_energy[0] == 0
    assert leaf.player_block_energy[0] == block  # the edit made a copy
    # Cultist's moves are fixed: StartTurn ran, the draw waits, block is 0.
    _, leaf = end_turn_leaf("Cultist", 2)
    assert leaf.leaf_form == "draw"
    assert leaf.player_block_energy[0] == 0
    assert c.awaiting_action()  # after_end_turn left the combat as it was


def test_with_monster_power():
    _, leaf = end_turn_leaf("Cultist", 1)
    before = leaf.monster_numbers()[0]
    e = leaf.with_monster_power(0, "Strength", -2)
    assert e.monster_numbers()[0][4] == before[4] - 2
    assert leaf.monster_numbers()[0] == before
    w = leaf.with_monster_power(0, "Weak", 1)
    assert w.monster_numbers()[0][5] == before[5] + 1
    try:
        leaf.with_monster_power(3, "Strength", -2)
    except ValueError:
        pass
    else:
        raise AssertionError("a dead slot must raise")
    est, loss, rounds = leaf.heuristic_parts()
    assert 0 <= est <= 2 and loss >= 0 and rounds >= 0


def test_leaf_rows_skip_stale_intent():
    # At a monster_rolls leaf the rolling monster shows its last move: no
    # str-2/weak+1 there, only the block edits; a draw leaf gets both.
    score = lambda cs: [c.heuristic_parts()[0] for c in cs]  # noqa: E731
    _, leaf = end_turn_leaf("Jaw Worm", 2)
    assert set(lnp.leaf_rows(leaf, score)["edits"]) == {"block0", "block+10", "block+20", "block+30"}
    _, leaf = end_turn_leaf("Cultist", 2)
    assert set(lnp.leaf_rows(leaf, score)["edits"]) == {"str-2", "weak+1"}


def test_cluster_se():
    m, se, n = lnp.cluster_mean_se([[1.0, 3.0], [], [4.0], [6.0, 6.0]])
    assert n == 3 and abs(m - 4.0) < 1e-9
    assert abs(se - (((2 - 4) ** 2 + 0 + (6 - 4) ** 2) / 2) ** 0.5 / 3 ** 0.5) < 1e-9
    assert lnp.cluster_mean_se([[], []]) == (None, None, 0)


def test_mispriced():
    assert lnp.mispriced("block0", (5.0, 1.0), (0.0, 0.0)) is True
    assert lnp.mispriced("block0", (3.0, 1.0), (0.0, 0.0)) is False
    assert lnp.mispriced("str-2", (-2.0, 0.5), (4.0, 0.5)) is True  # wrong sign
    assert lnp.mispriced("str-2", (0.5, 0.2), (4.0, 0.5)) is True  # under half
    assert lnp.mispriced("str-2", (3.0, 0.5), (4.0, 0.5)) is False
    assert lnp.mispriced("weak+1", (20.0, 1.0), (4.0, 0.5)) is True  # over twice


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
    print("ok")
