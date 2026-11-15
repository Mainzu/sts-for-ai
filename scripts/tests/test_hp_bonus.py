"""Tests for search's HP bonus (results doc "HP bonus at the leaves"): a
`NetEvaluator` with `hp_bonus` c scores c x clamp(score / 2, 0, 1) x (HP -
start HP) above the net; c 0 is the net bit for bit; the player spec
`<net>.pt@hpb<c>` loads it, and ladder caches tell it from the bare net.
The enemy-Strength price (`enemy_strength_price` k, `@esp<k>`;
docs/specs/enemy-strength-price.md) subtracts k x clamp(score / 2, 0, 1) x
living monsters' Strength, beside the HP bonus. The end-HP bonus
(`hp_end_bonus` c, `@hpe<c>`; docs/specs/end-hp-bonus.md) prices HP after
the coming heal, c x clamp(score / 2, 0, 1) x (min(HP + 6, max HP) - start
HP), and can't be combined with `hp_bonus`.
Run with `python scripts/tests/test_hp_bonus.py` or with pytest."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402


def states():
    out = []
    for enc in ("jaw_worm", "cultist", "exordium_thugs"):
        c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4, enc, seed=3, hp=60)
        while not c.is_over() and c.turn() < 4:
            out.append(c.clone())
            c.step(next(a for a in c.legal_actions() if a.is_end_turn)) if c.awaiting_action() else c.advance()
    return [s for s in out if not s.is_over()]


def test_bonus_values():
    import stsnet
    from test_contract import tiny_trained
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta)
    st = states()
    lost = np.array([60 - s.player_hp() for s in st], np.float32)
    assert (lost > 0).any(), "some state should have lost HP"
    base = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(st))
    zero = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.0).score(st))
    assert base.tobytes() == zero.tobytes()
    got = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01).score(st))
    want = base + 0.01 * np.clip(base / 2, 0, 1) * -lost
    assert np.allclose(got, want, atol=1e-6), (got, want)


def test_enemy_strength_values():
    import stsnet
    from test_contract import tiny_trained
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta)
    st = states()
    c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4, "gremlin_nob", seed=3, hp=60)
    while not c.is_over() and c.turn() < 3:  # Nob's Enrage: Strength per Skill played
        a = next((a for a in c.legal_actions() if a.card == "Defend"), None) if c.awaiting_action() else None
        if c.awaiting_action():
            c.step(a or next(a for a in c.legal_actions() if a.is_end_turn))
        else:
            c.advance()
        if not c.is_over():
            st.append(c.clone())
    lost = np.array([60 - s.player_hp() for s in st], np.float32)
    hp = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01).score(st))
    zero = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01, enemy_strength_price=0.0).score(st))
    assert hp.tobytes() == zero.tobytes()
    base = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(st))
    got = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01, enemy_strength_price=0.05).score(st))
    diff = hp - got  # k x clamp(base / 2) x Strength
    f = np.clip(base / 2, 0, 1)
    assert np.allclose(hp, base + 0.01 * f * -lost, atol=1e-6)
    assert (diff >= -1e-6).all() and (diff > 1e-4).any(), "Nob should have gained Strength in some state"
    strength = diff / np.where(f > 0, 0.05 * f, 1)
    assert np.allclose(strength[f > 1e-3], np.round(strength[f > 1e-3]), atol=1e-3), strength


def test_strength_hits_values():
    # docs/specs/strength-hits-price.md: k 0 is bit-identical; Nob's Enrage
    # Strength costs a positive amount, and a larger k costs more.
    import stsnet
    from test_contract import tiny_trained
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta)
    st = []
    c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4, "gremlin_nob", seed=3, hp=60)
    while not c.is_over() and c.turn() < 3:
        a = next((a for a in c.legal_actions() if a.card == "Defend"), None) if c.awaiting_action() else None
        if c.awaiting_action():
            c.step(a or next(a for a in c.legal_actions() if a.is_end_turn))
        else:
            c.advance()
        if not c.is_over():
            st.append(c.clone())
    hp = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01).score(st))
    zero = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01, strength_hits_price=0.0).score(st))
    assert hp.tobytes() == zero.tobytes()
    one = hp - np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01, strength_hits_price=0.01).score(st))
    two = hp - np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01, strength_hits_price=0.02).score(st))
    assert (one >= -1e-6).all() and (one > 1e-4).any(), "Nob should have gained Strength in some state"
    assert np.allclose(two, 2 * one, atol=1e-5)


def test_end_hp_values():
    import stsnet
    from test_contract import tiny_trained
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta)
    st = states()
    end = np.array([min(s.player_hp() + 6, 80) - 60 for s in st], np.float32)
    assert (end < 0).any() and (end > 0).any(), "states should both lose more than the heal and less"
    base = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(st))
    zero = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_end_bonus=0.0).score(st))
    assert base.tobytes() == zero.tobytes()
    got = np.asarray(stsnet.rust_evaluator(model, norm, meta, hp_end_bonus=0.01).score(st))
    assert np.allclose(got, base + 0.01 * np.clip(base / 2, 0, 1) * end, atol=1e-6), (got, base, end)
    try:
        stsnet.rust_evaluator(model, norm, meta, hp_bonus=0.01, hp_end_bonus=0.01)
    except ValueError as e:
        assert "hp_end_bonus" in str(e)
    else:
        raise AssertionError("hp_bonus with hp_end_bonus should be refused")


def test_settings_parse():
    import bench
    assert bench.player_settings("a/m.pt") == ("a/m.pt", {})
    assert bench.player_settings("a/m.pt@hpb0.01") == ("a/m.pt", {"hp_bonus": 0.01})
    assert bench.player_settings("a/m.pt@hpb0.01@esp0.02") == ("a/m.pt", {"hp_bonus": 0.01, "enemy_strength_price": 0.02})
    assert bench.player_settings("a/m.pt@esp0.02") == ("a/m.pt", {"enemy_strength_price": 0.02})
    assert bench.player_settings("a/m.pt@hpe0.01@esp0.02") == ("a/m.pt", {"hp_end_bonus": 0.01, "enemy_strength_price": 0.02})
    assert bench.player_settings("a/m.pt@hpb0.01@shl0.01@tsl1") == ("a/m.pt", {"hp_bonus": 0.01, "strength_hits_price": 0.01, "turn_start_leaf": 1.0})
    for bad in ("a/m.pt@hpb0.01@hpb0.02", "a/m.pt@foo1", "a/m.pt@hpb0.01x", "a.pt+b.pt@hpb0.01",
                "a/m.pt@hpb0.01+", "a/m.pt@hpb1e", "a/m.pt@hpe0.01@hpe0.02", "a/m.pt@shl0.01@shl0.02", "a/m.pt@shlx"):
        try:
            bench.player_settings(bad)
        except ValueError as e:
            assert bad in str(e)
        else:
            raise AssertionError(f"{bad} should be refused")


def test_player_spec():
    import bench
    import ladder
    assert bench.split_player("a/m.pt@hpb0.01") == ("a/m.pt", 0.01)
    assert bench.split_player("a/m.pt") == ("a/m.pt", 0.0)
    champ = ladder.champion()["player"].split("@")[0]  # the bare net; the champion may carry a bonus
    assert ladder.player_files(champ + "@hpb0.01") == [champ]
    assert ladder.player_key(champ + "@hpb0.01") != ladder.player_key(champ)
    assert not ladder.same_player(champ, champ + "@hpb0.01")
    assert ladder.same_player(champ + "@hpb0.01", champ + "@hpb0.01")
    ev = bench.load_evaluator(champ + "@hpb0.01")
    assert ev.static is None
    try:
        bench.load_evaluator(champ + "+" + champ + "@hpb0.01")
    except ValueError:
        pass
    else:
        raise AssertionError("an ensemble with a bonus should be refused")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
