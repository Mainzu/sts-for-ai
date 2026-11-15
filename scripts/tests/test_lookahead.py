"""Tests for the monster lookahead columns (docs/specs/monster-lookahead.md):
with `lookahead=True` each monster gains `intent_pending`, the 4-move
`look_rate_*` and the expected effects of its next two moves (`next1_*`,
`next2_*`); off (the default) every layout and batch stays as today's. Run
with `python scripts/tests/test_lookahead.py` (plain asserts; every `test_*`
function runs) or with pytest."""

import json
import os
import sys
import tempfile

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import contract_pins as pins  # noqa: E402
import stsnet  # noqa: E402
from test_contract import both_passes, tiny_trained  # noqa: E402

OFF_NAMES = os.path.join(os.path.dirname(__file__), "data", "lookahead_off_names.json")
ON_PIN = os.path.join(os.path.dirname(__file__), "data", "lookahead_rows.npz")
LOOK = ("intent_pending", "look_rate_damage", "look_rate_hits")


def monster(c, slot=0, f=None):
    f = f or sts.Features("effects", lookahead=True)
    return dict(zip(f.monster_names, f.encode([c])["monsters"][0, slot]))


def end_turn(c):
    c.step(next(a for a in c.legal_actions() if a.is_end_turn))


def test_lookahead_off_unchanged():
    """`Features()` (lookahead off) has today's full-layout names and the
    fixed set's pinned batches, in both modes."""
    with open(OFF_NAMES, encoding="utf-8") as fh:
        want = json.load(fh)
    for mode in pins.MODES:
        f = sts.Features(mode)
        got = {"player": f.player_names, "monsters": f.monster_names, "cards": f.card_names, "rows": f.row_names,
               "row_kinds": f.row_kinds, "piles": f.piles}
        assert got == want[mode], mode
        assert not any(n in LOOK or n.startswith(("next1_", "next2_")) for n in f.monster_names), mode
    assert pins.batches() == pins.load_pins()["batches"]


def test_lookahead_names():
    """On: the columns come right after the `intent_*` block, so dropping them
    gives back today's monster names in today's order."""
    for mode in pins.MODES:
        off, on = sts.Features(mode).monster_names, sts.Features(mode, lookahead=True).monster_names
        intents = [n[len("intent_"):] for n in off if n.startswith("intent_") and n != "intent_damage"]
        assert on[:len(off)] == off, mode
        assert on[len(off):] == list(LOOK) + [f"next1_{n}" for n in intents] + [f"next2_{n}" for n in intents], mode


def test_lookahead_columns():
    """Cultist (intent Incantation): next1 = next2 = Dark Strike. Slime Boss
    showing Preparing: next1 = Slam (35). Jaw Worm paused at its own roll:
    intent_pending 1, next1 = the roll's mix. A dead monster: zeros."""
    c = sts.Combat(["Strike"] * 10, "cultist", seed=1)
    m = monster(c)
    assert m["intent_pending"] == 0
    for k in ("next1", "next2"):
        assert m[f"{k}_damage_single"] == 6 and m[f"{k}_hits_single"] == 1, m
    assert m["look_rate_damage"] == 6 and m["look_rate_hits"] == 1, m  # 4 Dark Strikes after Incantation

    c = sts.Combat(["Defend"] * 10, "slime_boss", seed=1)
    for _ in range(4):
        if "Preparing" in c.render():
            break
        end_turn(c)
    assert "Preparing" in c.render(), c.render()
    assert monster(c)["next1_damage_single"] == 35

    c = sts.Combat(["Strike"] * 10, "jaw_worm", seed=2)
    (end,) = [o for o in c.options(16) if o[0][-1].is_end_turn and len(o[0]) == 1]
    assert end[1] == "chance" and len(end[2]) >= 2, end[1:]
    mix = sum(p * monster(x)["intent_damage_single"] for p, x in end[2])
    (paused,) = [o for o in c.options(1) if o[0][-1].is_end_turn and len(o[0]) == 1]
    x = paused[2][0][1]
    m = monster(x)
    assert not x.awaiting_action() and m["intent_pending"] == 1, m
    assert abs(m["next1_damage_single"] - mix) < 1e-4, (m["next1_damage_single"], mix)

    c = sts.Combat(["Strike"] * 10, "cultist", seed=1)
    for _ in range(80):
        if c.is_over():
            break
        a = next((a for a in c.legal_actions() if a.card == "Strike"), None)
        c.step(a) if a is not None else end_turn(c)
    assert c.is_over() and c.won()
    m = monster(c)
    assert all(v == 0 for v in m.values()), m


def test_lookahead_net_roundtrip():
    """A tiny net trained with lookahead saves its columns, and after save and
    load (where its columns turn the option on) scores as before, torch and
    Rust alike."""
    meta = {"card_repr": "effects", "lookahead": True}
    model, norm = tiny_trained(meta)
    states = [sts.Combat(["Strike"] * 10, enc, seed=s) for enc in ("jaw_worm", "cultist", "slime_boss")
              for s in range(3)]
    before = both_passes(model, norm, meta, states)
    assert np.allclose(before[0], before[1], atol=1e-5), before
    path = os.path.join(tempfile.mkdtemp(), "m.pt")
    stsnet.save(path, model, norm, meta)
    assert "next1_damage_single" in torch.load(path, weights_only=False)["columns"]["monsters"]
    m2, n2, meta2 = stsnet.load(path)
    assert "next1_damage_single" in stsnet.features_for({k: v for k, v in meta2.items() if k != "lookahead"}).monster_names
    after = both_passes(m2, n2, meta2, states)
    for x, y in zip(before, after):
        assert x.tobytes() == y.tobytes()


def on_batches():
    """Every 4th golden state's monster array with lookahead on, both modes."""
    import golden
    ss = golden.states()[::4]
    return {f"{mode}_monsters": sts.Features(mode, known_cards=kc, known_powers=kp, lookahead=True).encode(ss)["monsters"]
            for mode, kc, kp in (("effects", None, None), ("ids", golden.KNOWN_CARDS, golden.KNOWN_POWERS))}


def test_lookahead_rows_pinned():
    """The on-layout's monster arrays on golden.py's states, byte for byte as
    pinned (`python scripts/tests/test_lookahead.py pin` rewrites the pin)."""
    want = np.load(ON_PIN)
    got = on_batches()
    assert set(got) == set(want.files)
    for k in want.files:
        assert got[k].dtype == want[k].dtype and got[k].tobytes() == want[k].tobytes(), k


def test_lookahead_config_key():
    """`lookahead: true` in a config trains on "effects+lookahead": its own
    feature-cache layout tag, the same dataset config."""
    import learn
    import registry
    on, off = {"mode": "effects", "lookahead": True}, {"mode": "effects"}
    assert learn.feature_mode(off) == "effects" and learn.feature_mode(on) == "effects+lookahead"
    assert registry.layout_tag("effects") != registry.layout_tag("effects+lookahead")
    assert "next1_damage_single" in learn.selfplay.features("effects+lookahead").monster_names
    assert learn.selfplay.features("effects").monster_names == sts.Features("effects").monster_names


if __name__ == "__main__":
    if sys.argv[1:] == ["pin"]:
        np.savez_compressed(ON_PIN, **on_batches())
        print("pinned", ON_PIN)
        sys.exit()
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
