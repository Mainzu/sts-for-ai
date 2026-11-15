"""Tests for the power-rate columns (docs/specs/rate-features.md): with
`rates=True` the player and each monster gain `rate_<HookRates field>` and
`rate_strength_x_turns` / `rate_block_x_turns`, the player `turns_left_est`,
and effects-mode cards `grant_rate_<field>`; off (the default) every layout
and batch stays as today's. Run with `python scripts/tests/test_rates.py`
(plain asserts; every `test_*` function runs) or with pytest."""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import contract_pins as pins  # noqa: E402

OFF_NAMES = os.path.join(os.path.dirname(__file__), "data", "lookahead_off_names.json")
FIELDS = ("block", "block_once", "strength", "strength_once", "strength_per_skill", "strength_per_self_loss",
          "self_loss", "self_losses", "countdown_loss", "damage_all", "draw")
ENTITY = [f"rate_{x}" for x in FIELDS] + ["rate_strength_x_turns", "rate_block_x_turns"]


def on():
    return sts.Features("effects", rates=True)


def player(c, f=None):
    f = f or on()
    return dict(zip(f.player_names, f.encode([c])["player"][0]))


def card_rows(c, f=None):
    """Every card entry's vector, as a dict by column name."""
    f = f or on()
    return [dict(zip(f.card_names, r)) for r in f.encode([c])["cards"]]


def play(c, name):
    c.step(next(a for a in c.legal_actions() if a.card == name))


def test_rates_off_unchanged():
    """`Features()` (rates off) has today's full-layout names and the fixed
    set's pinned batches, in both modes."""
    with open(OFF_NAMES, encoding="utf-8") as fh:
        want = json.load(fh)
    for mode in pins.MODES:
        f = sts.Features(mode)
        assert not f.rates
        got = {"player": f.player_names, "monsters": f.monster_names, "cards": f.card_names, "rows": f.row_names,
               "row_kinds": f.row_kinds, "piles": f.piles}
        assert got == want[mode], mode
    assert pins.batches() == pins.load_pins()["batches"]


def test_rates_names():
    """On: each path's columns are today's, then the rate block at the end
    (on the card path before the draw position columns, which stay last)."""
    for mode in pins.MODES:
        off, f = sts.Features(mode), sts.Features(mode, rates=True)
        assert f.rates
        assert f.player_names == off.player_names + ENTITY + ["turns_left_est"], mode
        assert f.monster_names == off.monster_names + ENTITY, mode
        grant = [f"grant_rate_{x}" for x in FIELDS] if mode == "effects" else []
        assert f.card_names == off.card_names[:-2] + grant + off.card_names[-2:], mode
        assert f.row_names == off.row_names, mode
        # Rows and piles are untouched, so the batch's rows are the same.
        c = sts.Combat(["Strike"] * 4 + ["Demon Form"], "cultist", seed=1)
        a, b = off.encode([c]), f.encode([c])
        assert np.array_equal(a["rows"], b["rows"]) and np.array_equal(a["card_pile"], b["card_pile"]), mode


def test_rates_values():
    """Demon Form 2 on the player: rate_strength 2; Metallicize 3: rate_block
    3; the card in hand carries the same as grant_rate_*; the products are
    the rate times turns_left_est."""
    for name, field, amount in (("Demon Form", "strength", 2), ("Metallicize", "block", 3)):
        c = sts.Combat(["Strike"] * 4 + [name], "cultist", seed=1)
        rows = card_rows(c)
        granted = [r for r in rows if r[f"grant_rate_{field}"]]
        assert len(granted) == 1 and granted[0][f"grant_rate_{field}"] == amount, (name, granted)
        assert all(r[f"grant_rate_{x}"] == 0 for r in rows for x in FIELDS if x != field), name
        assert player(c)[f"rate_{field}"] == 0
        play(c, name)
        p = player(c)
        assert p[f"rate_{field}"] == amount, (name, p)
        assert p["turns_left_est"] > 0
        assert np.isclose(p[f"rate_{field}_x_turns"], amount * p["turns_left_est"]), p


def test_monster_rates():
    """Cultist after Incantation has Ritual: its monster rate_strength is
    Ritual's per-turn Strength; a dead slot is zeros."""
    c = sts.Combat(["Defend"] * 10, "cultist", seed=1)
    f = on()
    c.step(next(a for a in c.legal_actions() if a.is_end_turn))
    m = dict(zip(f.monster_names, f.encode([c])["monsters"][0, 0]))
    assert m["rate_strength"] > 0, m
    empty = dict(zip(f.monster_names, f.encode([c])["monsters"][0, 1]))
    assert all(v == 0 for v in empty.values())


def test_generated_copy_same_columns():
    """A generated copy of Demon Form (registry-lite pack) gives the same
    columns as Demon Form, in hand and on the player."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "py", "tests"))
    import test_content_pack as tcp
    tcp.load()
    f = on()
    a, b = tcp.pair()
    tcp.same_batch(f.encode([a]), f.encode([b]))
    tcp.play_power(a, "Demon Form")
    tcp.play_power(b, tcp.COPY)
    tcp.same_batch(f.encode([a]), f.encode([b]))
    assert player(b, f)["rate_strength"] == 2


def test_rates_with_lookahead():
    """Both options on: the column sets are disjoint and each option adds
    what it adds alone."""
    off, both = sts.Features("effects"), sts.Features("effects", rates=True, lookahead=True)
    look, rates = sts.Features("effects", lookahead=True), on()
    for k in ("player_names", "monster_names", "card_names"):
        o, b, l, r = (getattr(x, k) for x in (off, both, look, rates))
        added_l, added_r = set(l) - set(o), set(r) - set(o)
        assert not added_l & added_r, k
        assert set(b) == set(o) | added_l | added_r and len(b) == len(set(b)), k
    c = sts.Combat(["Strike"] * 4 + ["Demon Form"], "jaw_worm", seed=3)
    bb, br = both.encode([c]), rates.encode([c])
    pb = dict(zip(both.monster_names, bb["monsters"][0, 0]))
    pr = dict(zip(rates.monster_names, br["monsters"][0, 0]))
    assert all(pb[n] == pr[n] for n in pr), "rate columns don't depend on lookahead"


def test_rates_net_roundtrip():
    """A tiny net trained with rates saves their columns, and after save and
    load (where its columns turn the option on) scores as before, torch and
    Rust alike."""
    import tempfile
    import torch
    import stsnet
    from test_contract import both_passes, tiny_trained
    meta = {"card_repr": "effects", "rates": True}
    model, norm = tiny_trained(meta)
    states = [sts.Combat(["Strike"] * 4 + ["Demon Form", "Metallicize"], enc, seed=s)
              for enc in ("jaw_worm", "cultist", "hexaghost") for s in range(3)]
    before = both_passes(model, norm, meta, states)
    assert np.allclose(before[0], before[1], atol=1e-5), before
    path = os.path.join(tempfile.mkdtemp(), "m.pt")
    stsnet.save(path, model, norm, meta)
    cols = torch.load(path, weights_only=False)["columns"]
    assert "turns_left_est" in cols["player"] and "grant_rate_strength" in cols["cards"]
    m2, n2, meta2 = stsnet.load(path)
    assert stsnet.features_for({k: v for k, v in meta2.items() if k != "rates"}).rates
    after = both_passes(m2, n2, meta2, states)
    for x, y in zip(before, after):
        assert x.tobytes() == y.tobytes()


def test_rates_config_key():
    """`rates: true` in a config trains on "effects+rates" (after
    "+lookahead" when both are on): its own feature-cache layout tag, the
    same dataset config."""
    import learn
    import registry
    sp = learn.selfplay
    assert learn.feature_mode({"mode": "effects", "rates": True}) == "effects+rates"
    assert learn.feature_mode({"mode": "effects", "lookahead": True, "rates": True}) == "effects+lookahead+rates"
    assert learn.feature_mode({"mode": "effects"}) == "effects"
    for mode, want in (("effects", ("effects", False, False, False)), ("effects+lookahead", ("effects", True, False, False)),
                       ("effects+rates", ("effects", False, True, False)),
                       ("ids+lookahead+rates", ("ids", True, True, False))):
        assert sp.split_mode(mode) == want, mode
    tags = {registry.layout_tag(m) for m in ("effects", "effects+rates", "effects+lookahead", "effects+lookahead+rates")}
    assert len(tags) == 4
    f = sp.features("effects+lookahead+rates")
    assert f.rates and f.lookahead
    assert sp.features("effects").player_names == sts.Features("effects").player_names
    for s in (1, 101, 201):
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "configs", f"lean-rates-s{s}.json")) as fh:
            on = json.load(fh)
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "configs", f"lean-thr-s{s}.json")) as fh:
            off = json.load(fh)
        assert {k: v for k, v in on.items() if k not in ("name", "rates")} == {k: v for k, v in off.items() if k != "name"}
        assert on["rates"] is True


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
