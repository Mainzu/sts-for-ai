"""Tests for the start-HP column (docs/specs/start-hp.md): with
`start_hp=True` the player path ends with `start_hp`, the HP the combat
started at; off (the default) every layout and batch stays as today's.
Run with `python scripts/tests/test_start_hp.py` (plain asserts; every
`test_*` function runs) or with pytest."""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import contract_pins as pins  # noqa: E402

OFF_NAMES = os.path.join(os.path.dirname(__file__), "data", "lookahead_off_names.json")
CONFIGS = os.path.join(os.path.dirname(__file__), "..", "..", "configs")


def player(c, f):
    return dict(zip(f.player_names, f.encode([c])["player"][0]))


def test_off_unchanged():
    """`Features()` (start HP off) has today's full-layout names and the
    fixed set's pinned batches, in both modes."""
    with open(OFF_NAMES, encoding="utf-8") as fh:
        want = json.load(fh)
    for mode in pins.MODES:
        f = sts.Features(mode)
        assert not f.start_hp
        got = {"player": f.player_names, "monsters": f.monster_names, "cards": f.card_names, "rows": f.row_names,
               "row_kinds": f.row_kinds, "piles": f.piles}
        assert got == want[mode], mode
    assert pins.batches() == pins.load_pins()["batches"]


def test_names_and_value():
    """On: the player path gains `start_hp` at the end, nothing else
    changes; it reads the start HP, also after the player took damage."""
    for mode in pins.MODES:
        off, f = sts.Features(mode), sts.Features(mode, start_hp=True)
        assert f.start_hp
        assert f.player_names == off.player_names + ["start_hp"], mode
        for k in ("monster_names", "card_names", "row_names"):
            assert getattr(f, k) == getattr(off, k), (mode, k)
    f = sts.Features("effects", start_hp=True)
    c = sts.Combat(["Strike"] * 5, "jaw_worm", seed=1, hp=50)
    assert player(c, f)["start_hp"] == 50
    while c.player_hp() == 50 and not c.is_over():
        c.step(next(a for a in c.legal_actions() if a.is_end_turn)) if c.awaiting_action() else c.advance()
    p = player(c, f)
    assert p["hp"] < 50 and p["start_hp"] == 50, p
    a, b = sts.Features("effects").encode([c]), f.encode([c])
    assert np.array_equal(a["player"][0], b["player"][0][:-1])
    assert np.array_equal(a["monsters"], b["monsters"]) and np.array_equal(a["rows"], b["rows"])


def test_with_rates():
    """Both on: `start_hp` comes after the rate block; rate columns as alone."""
    rates, both = sts.Features("effects", rates=True), sts.Features("effects", rates=True, start_hp=True)
    assert both.player_names == rates.player_names + ["start_hp"]
    c = sts.Combat(["Strike"] * 4 + ["Demon Form"], "cultist", seed=1, hp=40)
    assert np.array_equal(rates.encode([c])["player"][0], both.encode([c])["player"][0][:-1])
    assert player(c, both)["start_hp"] == 40


def test_roundtrip():
    """A tiny net trained with the column saves it, and after save and load
    (where its columns alone turn the option on) scores as before, torch
    and Rust alike."""
    import tempfile
    import torch
    import stsnet
    from test_contract import both_passes, tiny_trained
    meta = {"card_repr": "effects", "start_hp": True}
    model, norm = tiny_trained(meta)
    states = [sts.Combat(["Strike"] * 4 + ["Defend"] * 4, enc, seed=s, hp=hp)
              for enc in ("jaw_worm", "cultist") for s in range(3) for hp in (20, 70)]
    before = both_passes(model, norm, meta, states)
    assert np.allclose(before[0], before[1], atol=1e-5), before
    path = os.path.join(tempfile.mkdtemp(), "m.pt")
    stsnet.save(path, model, norm, meta)
    assert "start_hp" in torch.load(path, weights_only=False)["columns"]["player"]
    m2, n2, meta2 = stsnet.load(path)
    bare = {k: v for k, v in meta2.items() if k != "start_hp"}
    assert stsnet.features_for(bare).start_hp
    after = both_passes(m2, n2, bare, states)
    for x, y in zip(before, after):
        assert x.tobytes() == y.tobytes()


def test_config_key():
    """`start_hp: true` trains on mode "...+start" (last suffix): its own
    feature-cache layout tag, the same dataset config; the lean-start
    configs are their twins plus the key."""
    import learn
    import registry
    sp = learn.selfplay
    assert learn.feature_mode({"mode": "effects", "start_hp": True}) == "effects+start"
    assert learn.feature_mode({"mode": "effects", "rates": True, "start_hp": True}) == "effects+rates+start"
    assert learn.feature_mode({"mode": "effects"}) == "effects"
    for mode, want in (("effects+start", ("effects", False, False, True)),
                       ("ids+lookahead+rates+start", ("ids", True, True, True)),
                       ("effects+rates", ("effects", False, True, False))):
        assert sp.split_mode(mode) == want, mode
    assert registry.layout_tag("effects+start") != registry.layout_tag("effects")
    assert sp.features("effects+start").start_hp and not sp.features("effects").start_hp
    for arm, twin in (("lean-start", "lean-thr"), ("lean-start-hpw2", "lean-hpw2")):
        for s in (1, 101):
            with open(os.path.join(CONFIGS, f"{arm}-s{s}.json")) as fh:
                on = json.load(fh)
            with open(os.path.join(CONFIGS, f"{twin}-s{s}.json")) as fh:
                off = json.load(fh)
            assert {k: v for k, v in on.items() if k not in ("name", "start_hp")} == \
                {k: v for k, v in off.items() if k != "name"}
            assert on["start_hp"] is True and on["name"] == f"{arm}-s{s}"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
