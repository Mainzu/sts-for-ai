"""Varied setups (learned-play Amendment 3, C1): every training game starts
at a random HP (10-100% of max) with the starter deck plus 3-15 random
training-pool cards; `sts.run` takes a fourth spec field, the game's
starting HP; game records keep it and replay uses it; the varied pool's
dataset config differs from the old pool's.

    python scripts/tests/test_setups.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

import learn
import registry
import selfplay
import sts


def varied(n, seed):
    return selfplay.make_specs(n, seed, selfplay.varied_deck, hp_fn=selfplay.varied_hp)


def test_specs_cover_the_hp_and_deck_ranges():
    """Over 3,000 specs, HP lies in [10%, 100%] of max and deck sizes in
    13-25 (starter 10 + 3-15), every value of both ranges drawn."""
    specs, groups = varied(1000, 5)
    assert len(specs) == 3000 and len(groups) == 3000
    top = selfplay.max_hp()
    assert top == 80
    hps = [s[3] for s in specs]
    sizes = [len(s[1]) for s in specs]
    assert set(hps) == set(range(8, 81))
    assert set(sizes) == set(range(13, 26))
    assert all(s[1][:10] == selfplay.STARTER for s in specs)
    assert all(c in selfplay.TRAIN_POOL for s in specs for c in s[1][10:])


def test_same_seed_same_specs():
    assert varied(50, 3) == varied(50, 3)
    assert varied(50, 3) != varied(50, 4)


def test_hp_at_least_one():
    """A tiny max HP still gives a whole HP of at least 1."""
    rng = np.random.default_rng(0)
    assert all(selfplay.varied_hp(rng, 3) >= 1 for _ in range(200))


def test_four_field_spec_starts_at_that_hp():
    deck = selfplay.STARTER + ["Cleave"]
    res = sts.run("search", [("jaw_worm", deck, 1, 23), ("jaw_worm", deck, 2, 61), ("jaw_worm", deck, 3)])
    assert [r["hp_start"] for r in res] == [23, 61, 80]
    # The fourth field overrides the run-wide `hp`; 3-field specs take it.
    res = sts.run("search", [("jaw_worm", deck, 1, 23), ("jaw_worm", deck, 1)], hp=40)
    assert [r["hp_start"] for r in res] == [23, 40]
    # The same game as a Combat at that HP.
    rec = sts.run("search", [("jaw_worm", deck, 1, 23)], record=True)[0]
    assert rec["states"][0].render() == sts.Combat(deck, "jaw_worm", seed=1, hp=23).render()


def test_three_field_specs_unchanged():
    """A 3-field spec plays exactly as a 4-field spec at the default HP."""
    specs = sts.make_specs("hallway", 12, extra=5, seed=1)
    plain = sts.run("search", specs, record=True)
    four = sts.run("search", [(e, d, s, 80) for e, d, s in specs], record=True)
    for a, b in zip(plain, four):
        assert a["actions"] == b["actions"] and a["score"] == b["score"] and a["hp_start"] == 80


def test_records_keep_per_game_hp_and_replay_uses_it():
    specs, groups = varied(2, 11)
    with tempfile.TemporaryDirectory() as root:
        gen = {"set": "train", "search": {"limit": 16}}
        ds, results = registry.selfplay(specs, groups, gen, root=root, keep_states=True)
        games = registry.load_games(ds, root)
        assert [g["hp"] for g in games] == [s[3] for s in specs]
        assert [r["hp_start"] for r in results] == [s[3] for s in specs]
        for g, r in zip(games, results):
            rep = registry.replay(g)
            assert rep["states"][0].player_hp() == g["hp"]
            assert rep["score"] == r["score"] and len(rep["states"]) == len(r["states"])


def test_varied_pool_config_differs_from_the_old_pool():
    """learn.dataset records the variety settings (default), so a dataset
    of the old fixed setups is never found for it, and vice versa."""
    seen = []
    saved = registry.find
    registry.find = lambda gen, **k: seen.append(gen) or "ds"
    try:
        cfg = {"n_train": 5, "n_val": 1, "train_seed": 1, "val_seed": 2}
        learn.dataset(cfg, "train")
        learn.dataset(cfg, "val")
        learn.dataset(dict(cfg, setups="fixed"), "train")
    finally:
        registry.find = saved
    new, val, old = seen
    assert new["setup"] == {"hp": [0.1, 1.0], "extra_cards": [3, 15]} and new["decks"] == "varied_deck"
    assert val["setup"] == new["setup"]
    assert "setup" not in old and old["decks"] == "train_deck"
    assert new != old


def test_varied_dataset_is_played_with_varied_setups():
    """A tiny varied round-0 dataset: its games carry per-game HP and
    13-25-card decks; a fixed dataset of the same seed isn't returned for it."""
    with tempfile.TemporaryDirectory() as root:
        cfg = {"n_train": 3, "n_val": 1, "train_seed": 1, "val_seed": 2, "search": {"limit": 16}}
        old = learn.dataset(dict(cfg, setups="fixed"), "train", root, log=lambda *a: None)
        new = learn.dataset(cfg, "train", root, log=lambda *a: None)
        assert old != new
        games = registry.load_games(new, root)
        assert all(8 <= g["hp"] <= 80 and 13 <= len(g["deck"]) <= 25 for g in games)
        assert all(g["hp"] is None and len(g["deck"]) == 15 for g in registry.load_games(old, root))


def test_low_hp_slice():
    """Lean-loop spec: `low_hp_fn(0.25, 1, 8)` starts about a quarter of
    3,000 specs at 1-8 HP (every value drawn) and the rest over the varied
    range; a share of 0 gives only varied HPs."""
    specs, _ = selfplay.make_specs(1000, 5, selfplay.varied_deck, hp_fn=selfplay.low_hp_fn(0.25, 1, 8))
    hps = [s[3] for s in specs]
    assert all(1 <= h <= 80 for h in hps)
    assert set(range(1, 8)) <= set(hps)
    assert 0.25 < sum(h <= 8 for h in hps) / len(hps) < 0.32  # the slice plus varied draws of 8
    specs, _ = selfplay.make_specs(200, 5, selfplay.varied_deck, hp_fn=selfplay.low_hp_fn(0.0, 1, 8))
    assert min(s[3] for s in specs) >= 8


def test_low_hp_only_in_later_rounds():
    """The `low_hp` key changes the dataset config of rounds >= 1 only, so
    round 0's pool is shared with configs without it."""
    cfg = {"name": "t", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 1, "val_seed": 2,
           "search": {"limit": 4}, "setups": "varied"}
    seen = []
    orig = registry.find
    registry.find = lambda gen, **kw: seen.append(gen) or "ds"
    try:
        for c in (cfg, {**cfg, "low_hp": {"share": 0.25, "hp": [1, 8]}}):
            learn.dataset(c, "train", rnd=0)
            learn.dataset(c, "train", rnd=1, parent=type("P", (), {"id": "p"})())
    finally:
        registry.find = orig
    assert seen[0] == seen[2] and "low_hp" not in seen[0]["setup"]
    assert seen[3]["setup"]["low_hp"] == [0.25, 1, 8] and "low_hp" not in seen[1]["setup"]


def test_train_pool_restricts_training_decks():
    """Coverage pilot: `train_pool` draws extra cards from those kinds and
    their upgrades only, enters the training set's dataset config, and
    leaves the validation set's config alone."""
    deck = selfplay.pool_deck(["Anger", "Cleave"])
    rng = np.random.default_rng(0)
    extras = {c for _ in range(200) for c in deck(rng)[10:]}
    assert extras == {"Anger", "Anger+", "Cleave", "Cleave+"}
    cfg = {"name": "t", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 1, "val_seed": 2,
           "search": {"limit": 4}, "setups": "varied"}
    seen = []
    orig = registry.find
    registry.find = lambda gen, **kw: seen.append(gen) or "ds"
    try:
        for c in (cfg, {**cfg, "train_pool": ["Cleave", "Anger"]}):
            learn.dataset(c, "train")
            learn.dataset(c, "val")
    finally:
        registry.find = orig
    assert "train_pool" not in seen[0] and seen[1] == seen[3]
    assert seen[2]["train_pool"] == ["Anger", "Cleave"]


BOSSES = ["slime_boss", "hexaghost", "the_guardian"]


def test_bosses_swap_boss_group_encounters():
    """All-content net: the boss group's encounters come from the list in
    turn, everything else unchanged; an unknown name raises."""
    specs, groups = varied(3, 7)
    swapped = selfplay.with_bosses(specs, groups, BOSSES)
    boss = [i for i, g in enumerate(groups) if selfplay.GROUPS[g] == "boss"]
    assert [swapped[i][0] for i in boss] == BOSSES
    assert all(swapped[i][1:] == specs[i][1:] for i in boss)
    assert all(swapped[i] == specs[i] for i in range(len(specs)) if i not in boss)
    try:
        selfplay.with_bosses(specs, groups, ["no_such_boss"])
    except Exception:
        pass
    else:
        raise AssertionError("unknown boss accepted")


def test_full_pool_deck_draws_held_out_cards():
    """All-content net: extra cards span check 6's and check 9's held-out
    cards; decks keep 13-25 cards."""
    rng = np.random.default_rng(0)
    decks = [selfplay.full_pool_deck(rng) for _ in range(300)]
    extras = {c for d in decks for c in d[10:]}
    assert extras & selfplay.HELD_OUT_ALL and extras & set(sts.held_out_card_names())
    assert all(13 <= len(d) <= 25 for d in decks)


def test_all_content_keys_enter_dataset_config():
    """`bosses` and `deck_pool` enter train and val dataset configs; without
    them the config is today's; with `train_pool` beside `deck_pool` it
    raises."""
    cfg = {"name": "t", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 1, "val_seed": 2,
           "search": {"limit": 4}, "setups": "varied"}
    seen = []
    orig = registry.find
    registry.find = lambda gen, **kw: seen.append(gen) or "ds"
    try:
        allc = {**cfg, "bosses": BOSSES, "deck_pool": "all"}
        for c in (cfg, allc):
            learn.dataset(c, "train")
            learn.dataset(c, "val")
        try:
            learn.dataset({**allc, "train_pool": ["Anger"]}, "train")
        except ValueError:
            pass
        else:
            raise AssertionError("two pools accepted")
    finally:
        registry.find = orig
    assert "bosses" not in seen[0] and "deck_pool" not in seen[1]
    for g in seen[2:4]:
        assert g["bosses"] == BOSSES and g["deck_pool"] == "all"


def test_all_content_dataset_plays_all_three_bosses():
    """End to end: a tiny all-content round-0 dataset holds boss games at
    all three bosses."""
    with tempfile.TemporaryDirectory() as root:
        cfg = {"n_train": 3, "n_val": 1, "train_seed": 1, "val_seed": 2, "search": {"limit": 4},
               "bosses": BOSSES, "deck_pool": "all"}
        ds = learn.dataset(cfg, "train", root, log=lambda *a: None)
        encs = {g["encounter"] for g in registry.load_games(ds, root)}
        assert set(BOSSES) <= encs


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
PACKS = [os.path.join(ROOT, "content", "packs", f) for f in ("act1-ironclad.json", "act1-monsters.json")]
ALLC = {"name": "t", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 1, "val_seed": 2,
        "search": {"limit": 4}, "setups": "varied", "deck_pool": "all"}


def test_pack_keys_enter_dataset_config():
    """Pack learn: `packs` puts both packs' hashes, in order, in train and
    val dataset configs; without it no `packs` key; without deck_pool all it
    raises."""
    seen = []
    orig = registry.find
    registry.find = lambda gen, **kw: seen.append(gen) or "ds"
    try:
        for c in (ALLC, {**ALLC, "packs": PACKS}):
            learn.dataset(c, "train")
            learn.dataset(c, "val")
        try:
            learn.dataset({**ALLC, "deck_pool": None, "packs": PACKS}, "train")
        except ValueError:
            pass
        else:
            raise AssertionError("packs without deck_pool all accepted")
    finally:
        registry.find = orig
    hashes = [selfplay.load_content(p)[1] for p in PACKS]
    assert "packs" not in seen[0] and "packs" not in seen[1]
    assert seen[2]["packs"] == hashes and seen[3]["packs"] == hashes


def test_pack_pool_deck_draws_pack_cards():
    """Extra cards span pack cards and official held-out cards; decks keep 13-25."""
    pack = selfplay.load_content(PACKS[0])[0]
    cards = selfplay.pack_cards(pack)
    rng = np.random.default_rng(0)
    decks = [selfplay.pack_pool_deck(cards)(rng) for _ in range(300)]
    extras = {c for d in decks for c in d[10:]}
    assert extras & set(cards) and extras & set(sts.held_out_card_names())
    assert "gen:Disarm+" in cards and all(13 <= len(d) <= 25 for d in decks)


def test_with_pack_encounters():
    """Hallway specs take the monster pack's 3 added encounters at about
    3 / 14; exordium_thugs becomes its pack version; elite and boss specs,
    decks, seeds and HP unchanged."""
    pack = selfplay.load_content(PACKS[1])[0]
    specs, groups = varied(2000, 3)
    out = selfplay.with_pack_encounters(specs, groups, [pack])
    hall = [i for i, g in enumerate(groups) if selfplay.GROUPS[g] == "hallway"]
    added = {"gen:Blue Slaver", "gen:Gremlin Gang", "gen:Red Slaver"}
    share = sum(out[i][0] in added for i in hall) / len(hall)
    assert abs(share - 3 / 14) < 0.04, share
    assert "exordium_thugs" not in {out[i][0] for i in hall} and "gen:Exordium Thugs" in {out[i][0] for i in hall}
    assert all(out[i] == specs[i] for i in range(len(specs)) if i not in hall)
    assert all(o[1:] == s[1:] for o, s in zip(out, specs))


def test_pack_dataset_plays_pack_content():
    """End to end: a tiny round-0 dataset with both Act 1 packs holds pack
    cards and a pack hallway encounter, its manifest names both hashes, and
    it encodes."""
    with tempfile.TemporaryDirectory() as root:
        cfg = {**ALLC, "n_train": 30, "packs": PACKS}
        ds = learn.dataset(cfg, "train", root, log=lambda *a: None)
        games = registry.load_games(ds, root)
        assert any(c.startswith("gen:") for g in games for c in g["deck"])
        assert any(g["encounter"].startswith("gen:") for g in games)
        hashes = [selfplay.load_content(p)[1] for p in PACKS]
        assert registry.load_manifest(ds, root)["content_hashes"] == hashes
        assert len(registry.examples(ds, "effects", root)) > 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
