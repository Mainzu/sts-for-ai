"""The ascension level on the Python side (docs/specs/ascension.md): Combat,
versus, from_view, the run start, the run spec key and the gauntlet's
setting. The engine's A20 numbers are engine/tests/ascension.rs."""

import os
import sys

import pytest

import sts

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def test_combat_takes_the_level():
    a0 = sts.Combat(STARTER, "gremlin_nob", seed=3)
    a20 = sts.Combat(STARTER, "gremlin_nob", seed=3, ascension=20)
    assert (a0.ascension, a20.ascension) == (0, 20)
    assert 82 <= a0.view()["monsters"][0]["hp"] <= 86 and 85 <= a20.view()["monsters"][0]["hp"] <= 90
    assert "ascension" not in a0.view() and a20.view()["ascension"] == 20
    # The run start at A20: 68 of 75 HP.
    p = a20.view()["player"]
    assert (p["hp"], p["max_hp"]) == (68, 75)
    with pytest.raises(ValueError):
        sts.Combat(STARTER, "cultist", ascension=21)


def test_versus_and_from_view_keep_the_level():
    c = sts.Combat.versus(STARTER, ["The Guardian"], seed=2, group="boss", ascension=20)
    v = c.view()
    assert v["monsters"][0]["powers"]["ModeShift"] == 40 and v["monsters"][0]["hp"] == 250
    back = sts.Combat.from_view(v, seed=2, group="boss")
    assert back.ascension == 20 and back.view() == v
    assert sts.Combat.from_view(v, seed=2, group="boss", ascension=0).ascension == 0


def test_run_start():
    assert sts.run_start("ironclad", 0) == {"hp": 80, "max_hp": 80, "potion_slots": 3, "deck_adds": []}
    assert sts.run_start("ironclad", 20) == {"hp": 68, "max_hp": 75, "potion_slots": 2,
                                             "deck_adds": ["gen:Ascender's Bane"]}
    assert sts.run_start("silent", 14)["max_hp"] == 66
    # The deck add binds once a fight at A10 or more was asked for.
    c = sts.Combat(STARTER + ["gen:Ascender's Bane"], "cultist", seed=1, ascension=10)
    assert sum(c.piles()[k].get("gen:Ascender's Bane", 0) for k in ("hand", "draw", "discard", "exhaust")) == 1


def test_run_spec_key():
    spec = {"encounter": "gremlin_nob", "deck": STARTER, "seed": 4}
    r0, r20 = sts.run("greedy", [spec, {**spec, "ascension": 20}], threads=1)
    assert r0["hp_start"] == 80 and r20["hp_start"] == 68


def test_gauntlet_setting():
    import gauntlet
    assert "ascension" in gauntlet.VARY
    ns = gauntlet.players({"player": "heuristic", "ascension": 20}, cells=[])
    assert ns.ascension == 20


def test_make_specs_at_a20():
    """A20 decks hold Ascender's Bane and HP is drawn of 75; the draws match A0's."""
    import selfplay
    a0, _ = selfplay.make_specs(3, 5, selfplay.varied_deck, hp_fn=selfplay.varied_hp)
    a20, _ = selfplay.make_specs(3, 5, selfplay.varied_deck, hp_fn=selfplay.varied_hp, ascension=20)
    assert all("gen:Ascender's Bane" not in s[1] for s in a0)
    assert all(s[1][-1] == "gen:Ascender's Bane" and s[1][:-1] == t[1] for s, t in zip(a20, a0))
    assert max(s[3] for s in a20) <= 75 and all((s[0], s[2]) == (t[0], t[2]) for s, t in zip(a20, a0))


def test_dataset_at_a20_and_mixed_levels(tmp_path):
    """An A20 config plays its fights at 20, the manifest and run.json record
    it, and a pool mixing levels is refused unless the config allows it."""
    import json
    import registry
    import selfplay
    root = str(tmp_path)
    specs, groups = selfplay.make_specs(1, 3, selfplay.train_deck, ascension=20)
    cfg = {"search": {"limit": selfplay.LIMIT}, "ascension": 20}
    ds, _ = registry.selfplay(specs, groups, cfg, root=root)
    assert registry.load_manifest(ds, root)["ascension"] == 20
    games = registry.load_games(ds, root)
    assert all(g["ascension"] == 20 and g["outcome"]["hp_start"] == 68 for g in games)
    registry.replay(games[0])  # replays at its level
    s0, g0 = selfplay.make_specs(1, 3, selfplay.train_deck)
    ds0, _ = registry.selfplay(s0, g0, {"search": {"limit": selfplay.LIMIT}}, root=root)
    assert "ascension" not in registry.load_manifest(ds0, root)
    run = registry.Run.create("a", cfg, [ds], root=root)
    assert json.load(open(os.path.join(run.path, "run.json")))["ascension"] == 20
    with pytest.raises(ValueError, match="mixes levels"):
        registry.Run.create("b", cfg, [ds, ds0], root=root)
    registry.Run.create("c", {**cfg, "mixed_ascension": True}, [ds, ds0], root=root)


def test_choosers_project_at_the_run_max_hp():
    import gauntlet
    assert gauntlet.run_max_hp(0) == 80 and gauntlet.run_max_hp(20) == 75
    assert gauntlet.players({"player": "heuristic", "ascension": 20}, cells=[]).max_hp == 75
    assert gauntlet.players({"player": "heuristic"}, cells=[]).max_hp == 80
