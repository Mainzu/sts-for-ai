"""Tests for threshold and held rows in effects features
(docs/specs/threshold-and-held-rows.md): The Guardian's Mode Shift and the
large slimes' split as `threshold` rows on the monster, Burn's turn-end
damage as a `held` row on the card. Run with
`python scripts/tests/test_threshold_rows.py` (plain asserts; every `test_*`
function runs) or with pytest."""

import os
import sys
import tempfile

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import stsnet  # noqa: E402
from test_contract import both_passes, tiny_trained  # noqa: E402


def rows_of(c, kind):
    """(rows of `kind` as {column: value} dicts, their row_entity / row_card, the batch, column names)."""
    f = sts.Features("effects", row_kinds=[kind])
    b = f.encode([c])
    names = f.row_names
    rows = [dict(zip(names, r)) for r in b["rows"]]
    return rows, b, f


def play_strike(c):
    c.step(next(a for a in c.legal_actions() if a.card == "Strike"))


def test_threshold_rows_guardian():
    """A Guardian start state has one own threshold row (param 30, block 20)
    plus Sharp Hide's hooks granted to itself under the same condition; 12
    damage takes the param to 18; after the shift there is none."""
    c = sts.Combat(["Strike"] * 10, "the_guardian", seed=1)
    rows, b, _ = rows_of(c, "threshold")
    own = [r for r in rows if r["grant_own"] == 1]
    me = [r for r in rows if r["grant_me"] == 1]
    assert len(own) == 1 and len(me) >= 1 and len(own) + len(me) == len(rows)
    assert own[0]["condition_param"] == 30 and own[0]["block"] == 20
    assert own[0]["trigger_OwnerLostHp(Any)"] == 1
    for r in rows:
        assert r["condition_HpLostReaches"] == 1 and r["condition_param"] == 30
    assert any(r["damage_plain"] == 3 and r["damage_plain_self"] == 0 for r in me)  # Sharp Hide 3
    assert list(b["row_entity"]) == [1] * len(rows) and list(b["row_card"]) == [-1] * len(rows)
    play_strike(c)
    play_strike(c)
    rows, _, _ = rows_of(c, "threshold")
    assert [r["condition_param"] for r in rows if r["grant_own"] == 1] == [18]
    while "ModeShift" in c.render() and not c.is_over():
        if any(a.card == "Strike" for a in c.legal_actions()):
            play_strike(c)
        else:
            c.step(next(a for a in c.legal_actions() if a.is_end_turn))
    assert "ModeShift" not in c.render()
    assert rows_of(c, "threshold")[0] == []


def test_threshold_rows_slime():
    """A large slime above half HP has a threshold row with param hp -
    max_hp // 2 and the split effect; once its intent is the split, none. A
    Cultist has none."""
    c = sts.Combat(["Strike"] * 10, "large_slime", seed=3)
    f = sts.Features("effects")
    mon = dict(zip(f.monster_names, f.encode([c])["monsters"][0, 0]))
    hp, max_hp = int(mon["hp"]), int(mon["max_hp"])
    rows, _, _ = rows_of(c, "threshold")
    own = [r for r in rows if r["grant_own"] == 1]
    assert len(own) == 1 and own[0]["condition_param"] == hp - max_hp // 2 and own[0]["split"] == 1
    while "Split" not in c.render() and not c.is_over():
        if any(a.card == "Strike" for a in c.legal_actions()):
            play_strike(c)
        else:
            c.step(next(a for a in c.legal_actions() if a.is_end_turn))
    assert "intent: Split" in c.render(), c.render()
    assert rows_of(c, "threshold")[0] == []
    assert rows_of(sts.Combat(["Strike"] * 10, "cultist", seed=1), "threshold")[0] == []


def test_held_rows():
    """Burn in hand has one held row per card entry (turn end, damage to its
    holder 2, Burn+ 4) and its card vector says so; other plain damage
    (Combust) stays `damage_plain`."""
    for name, dmg in (("Burn", 2), ("Burn+", 4)):
        c = sts.Combat([name] * 10, "cultist", seed=1)
        rows, b, f = rows_of(c, "held")
        assert len(rows) == len(b["cards"]) >= 1
        assert sorted(b["row_card"]) == list(range(len(b["cards"])))
        for r in rows:
            assert r["trigger_OwnerTurnEnd"] == 1 and r["condition_Always"] == 1 and r["grant_own"] == 1
            assert r["damage_plain_self"] == dmg and r["damage_plain"] == 0
        card = dict(zip(f.card_names, b["cards"][0]))
        assert card["damage_plain_self"] == dmg and card["damage_plain"] == 0
    c = sts.Combat(["Combust"] * 10, "cultist", seed=1)
    rows, _, _ = rows_of(c, "triggered")
    assert any(r["damage_plain"] == 5 for r in rows)  # Combust's 5 to every enemy
    assert all(r["damage_plain_self"] == 0 for r in rows)
    assert rows_of(c, "held")[0] == []


def test_new_net_roundtrip():
    """A tiny net under the new layout saves all three row kinds, and after
    save and load scores Guardian, slime and Burn states as before, torch
    and Rust alike."""
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta)
    states = [sts.Combat(["Strike"] * 5 + ["Burn"] * 5, enc, seed=s) for enc in ("the_guardian", "large_slime")
              for s in range(3)]
    assert all(rows_of(c, "threshold")[0] for c in states) and any(rows_of(c, "held")[0] for c in states)
    before = both_passes(model, norm, meta, states)
    assert np.allclose(before[0], before[1], atol=1e-5), before
    path = os.path.join(tempfile.mkdtemp(), "m.pt")
    stsnet.save(path, model, norm, meta)
    assert torch.load(path, weights_only=False)["row_kinds"] == ["triggered", "threshold", "held"]
    after = both_passes(*stsnet.load(path), states)
    for x, y in zip(before, after):
        assert x.tobytes() == y.tobytes()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
