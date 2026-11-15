"""Tests for fine-tuning on generated content (docs/specs/adaptation-burst.md).
Run with `python scripts/tests/test_finetune_gen.py` (plain asserts; every
`test_*` function runs) or with pytest. No games are played."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import finetune  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import stsnet  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
PACK = "data/bench/gen_powers_pack.json"


class Found(Exception):
    pass


def config_of(kind, n, seed, **kw):
    """The dataset config `finetune.games` looks up, caught at registry.find."""
    seen = []

    def find(config, root=None, **_):
        seen.append(config)
        raise Found

    old, registry.find = registry.find, find
    try:
        finetune.games(kind, n, seed, **kw)
    except Found:
        pass
    finally:
        registry.find = old
    return seen[0]


def test_string_kinds_unchanged():
    """The Silent and Ironclad kinds' dataset configs stay as they were, so
    their stored games keep their ids."""
    for kind, character in [("silent_a", "silent"), ("silent_b", "silent"), ("both", "silent"),
                            ("ironclad", "ironclad")]:
        assert config_of(kind, 300, 7) == {"kind": "warm-start games", "content": kind, "n_per_group": 300,
                                           "seed": 7, "character": character}


def test_varied_kind():
    """The "varied" kind (generated content's pool and validation) is an
    Ironclad dataset of its own."""
    assert config_of("varied", 300, 1) == {"kind": "warm-start games", "content": "varied", "n_per_group": 300,
                                           "seed": 1, "character": "ironclad"}


def test_gen_decks():
    """Every deck of generated content is a varied deck plus 1-2 of its cards."""
    kind = {"pack": os.path.join(ROOT, PACK), "cards": ["gc1_082", "gc1_050"]}
    _, cards = finetune.generated(kind)
    assert cards == ["gen:gc1_082", "gen:gc1_050"]
    seen = []

    def make_specs(n, seed, deck_fn, character="ironclad", hp_fn=None):
        seen.append((deck_fn, hp_fn, character))
        raise Found

    old = registry.find, selfplay.make_specs
    registry.find, selfplay.make_specs = (lambda *a, **k: None), make_specs
    try:
        finetune.games(kind, 5, 1, player="heuristic")
    except Found:
        pass
    finally:
        registry.find, selfplay.make_specs = old
    deck_fn, hp_fn, character = seen[0]
    assert hp_fn is selfplay.varied_hp and character == "ironclad"
    rng, ref = np.random.default_rng(3), np.random.default_rng(3)
    for _ in range(50):
        d, base = deck_fn(rng), selfplay.varied_deck(ref)
        extra = d[len(base):]
        assert d[:len(base)] == base and 1 <= len(extra) <= 2 and set(extra) <= set(cards)
        ref.random(), ref.integers(1, 3), ref.choice(cards, len(extra))  # keep the twin in step


def test_unknown_card():
    """A card id the pack lacks raises before any play, naming it."""
    try:
        finetune.generated({"pack": os.path.join(ROOT, PACK), "cards": ["gc1_082", "nope_1"]})
    except ValueError as e:
        assert "nope_1" in str(e)
    else:
        raise AssertionError("no error")


def test_gen_config():
    """Generated content's dataset config names the pack hash, the sorted
    cards and the player."""
    c = config_of({"pack": os.path.join(ROOT, PACK), "cards": ["gc1_082", "gc1_050"]}, 20, 1, player="heuristic")
    assert c["content"]["cards"] == ["gc1_050", "gc1_082"] and c["player"] == "heuristic"
    assert c["content"]["hash"] and c["character"] == "ironclad"


def test_effects_vocab_unchanged():
    """An effects parent keeps its vocabularies and layout for generated
    content; another card representation is refused."""
    meta = {"card_repr": "effects", **selfplay.meta_vocab("effects")}
    meta["known_conditions"] = meta["known_conditions"][:-1]  # an older net's shorter list stays short
    kept = finetune.kept_vocab(meta)
    assert all(kept[k] == meta.get(k) for k in stsnet.VOCAB_KEYS)
    assert stsnet.layout_of(kept) == stsnet.layout_of(meta)
    try:
        finetune.kept_vocab({"card_repr": "ids", **selfplay.meta_vocab("ids")})
    except ValueError:
        pass
    else:
        raise AssertionError("ids parent accepted")


def test_mutated_parent_is_unpatched():
    """"parent" in `mutated` plays the unmodified fight: no power added."""
    deck = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
    spec = {"deck": deck, "encounter": "three_sentries", "seed": 7, "hp": 60, "character": "ironclad",
            "group": "elite", "i": 7, "floor": 5}
    res, _ = finetune.mutated_games([spec], ["parent", "GE-AttackLoss-Damage"], 3, "heuristic")
    first = [r["states"][0].render() for r in res]
    assert "GE-AttackLoss-Damage" not in first[0] and first[1].count("GE-AttackLoss-Damage") == 3
    assert finetune.mutated_fights({"mutated": ["parent"], "skip": 0, "val_fights": 1}, 1,
                                   [{"i": 0}, {"i": 1}])[0] == [{"i": 0}]


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)


def test_hp_weight_targets():
    """`hp_weight` weighs a fine-tune's targets as learn.py's key does."""
    import types
    d = types.SimpleNamespace(target=np.array([0, 2.0, 1.9, 1.5, 1.2], np.float32))
    finetune.weigh_targets(d, 3)
    assert np.allclose(d.target, [0, 2, 1.7, 0.5, 0.1]) and d.target.dtype == np.float32


def test_mutated_unknown_mod():
    """Mutated content refuses an unknown modifier and training fights that
    reach the validation fights, before any play."""
    fights = [{"i": i} for i in range(20)]
    for kind, games in [({"mutated": ["sharp2", "nope"]}, 2), ({"mutated": ["sharp2"], "skip": 10, "val_fights": 5}, 6)]:
        try:
            finetune.mutated_fights(kind, games, fights)
        except ValueError as e:
            assert "nope" in str(e) or "validation" in str(e)
        else:
            raise AssertionError(f"no error for {kind}, {games}")
    train, val = finetune.mutated_fights({"mutated": ["sharp2"], "skip": 10, "val_fights": 5}, 5, fights)
    assert [f["i"] for f in train] == list(range(10, 15)) and [f["i"] for f in val] == list(range(15, 20))


def test_mutated_games():
    """Recorded mutated games start with the patched monsters and carry the
    end state's score."""
    deck = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
    specs = [{"deck": deck, "encounter": "three_sentries", "seed": s, "hp": 60, "character": "ironclad",
              "group": "elite", "i": s, "floor": 5} for s in (7, 8)]
    res, groups = finetune.mutated_games(specs, ["sharp2"], 3, "heuristic")
    assert len(res) == 2 and groups == [selfplay.GROUPS.index("elite")] * 2
    for r in res:
        assert len(r["states"]) == len(r["actions"]) > 0
        assert r["states"][0].render().count("SharpHide 2") == 3
        last = r["states"][-1].clone()
        last.step(r["actions"][-1])
        while not last.is_over() and not last.awaiting_action():
            last.advance()
        assert r["score"] == (last.score() if last.is_over() else 0.0)


def test_mutated_encounters():
    """`encounters` keeps the parent's fights (validation their last ones,
    training from position `skip`); `repeat` cycles them with repeat
    indices; without `repeat` too few fights refuse."""
    fights = [{"i": i, "floor": 1, "encounter": "a" if i % 2 else "b"} for i in range(20)]
    kind = {"mutated": ["GE-AttackLoss-Damage"], "encounters": ["a"], "skip": 4, "val_fights": 3}
    train, val = finetune.mutated_fights(kind, 4, fights)
    assert [f["i"] for f in val] == [15, 17, 19] and [f["i"] for f in train] == [5, 7, 9, 11]
    try:
        finetune.mutated_fights(kind, 6, fights)
    except ValueError as e:
        assert "validation" in str(e)
    else:
        raise AssertionError("no error without repeat")
    train, _ = finetune.mutated_fights({**kind, "repeat": True}, 13, fights)
    assert [f["i"] for f in train] == [5, 7, 9, 11, 13] * 2 + [5, 7, 9]
    assert [f.get("rep", 0) for f in train] == [0] * 5 + [1] * 5 + [2] * 3
    assert "rep" not in fights[5]


def test_mutated_gen_games():
    """A generated mechanic's game starts with the pack power on every
    monster; a repeat plays from a different seed."""
    deck = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
    spec = {"deck": deck, "encounter": "three_sentries", "seed": 7, "hp": 60, "character": "ironclad",
            "group": "elite", "i": 7, "floor": 5}
    res, _ = finetune.mutated_games([spec, {**spec, "rep": 1}], ["GE-AttackLoss-Damage"], 3, "heuristic")
    assert res[0]["states"][0].render().count("GE-AttackLoss-Damage") == 3
    assert [r["actions"] for r in res[:1]] != [r["actions"] for r in res[1:]] or res[0]["score"] != res[1]["score"] \
        or [s.render() for s in res[0]["states"]] != [s.render() for s in res[1]["states"]]


def test_mutated_ident_unchanged():
    """An older mutated dict keeps the cache identity it had before the
    generated-mechanics keys."""
    meta = {"card_repr": "effects"}
    kind = {"mutated": ["sharp2", "ritual2"], "skip": 200, "val_fights": 100}
    old = {"mutated": kind["mutated"], "skip": 200, "val_fights": 100, "which": "train", "games": 133, "seed": 41,
           "parent": "abc", "card_repr": "effects", "layout": stsnet.layout_of(meta), "rules": registry.rules_version()}
    assert finetune.mutated_ident(kind, "train", 133, 41, meta, "abc") == old
    new = finetune.mutated_ident({**kind, "mutated": ["GE-AttackLoss-Damage"], "encounters": ["gremlin_nob"]},
                                 "train", 99, 41, meta, "abc", "heuristic")
    assert new["encounters"] == ["gremlin_nob"] and new["player"] == "heuristic" and len(new["pack"]) > 0
