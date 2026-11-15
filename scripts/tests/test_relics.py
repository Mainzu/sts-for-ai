"""Giving relics to fights from Python (docs/specs/relics.md, build step 4):
`sts.Combat(..., relics=)`, `sts.Combat.versus(..., relics=, group=)` and
`sts.run`'s dict-spec key `"relics"`."""

import json
import os

import pytest

import sts

PACK = json.dumps({"version": 1, "powers": [
    {"id": "py_rel_anchor", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always",
                                       "effects": [{"Block": 10}, "RemoveSelf"]}]},
    {"id": "py_rel_energy", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"GainEnergy": 1}]}]},
], "relics": [
    {"id": "py_rel_anchor", "rarity": "common", "powers": [{"power": "py_rel_anchor", "amount": 1}]},
    {"id": "py_rel_collar", "rarity": "boss", "powers": [{"power": "py_rel_energy", "amount": 1}], "fights": ["elite", "boss"]},
    {"id": "py_rel_heal", "rarity": "rare", "win_heal": 5},
]})

DECK = None
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module", autouse=True)
def pack():
    global DECK
    sts.load_content(PACK)
    DECK = list(sts.starter_deck("ironclad"))


def heal(c):
    return float(sts.Features("effects").encode([c], heuristic=True)["win_heal"][0])


def test_no_relics_is_the_default():
    for kw in ({}, {"relics": None}, {"relics": []}):
        assert sts.Combat(DECK, "jaw_worm", seed=3, **kw) == sts.Combat(DECK, "jaw_worm", seed=3)


def test_combat_relics():
    c = sts.Combat(DECK, "jaw_worm", seed=3, relics=["gen:py_rel_anchor", "gen:py_rel_heal"])
    assert c.player_block_energy == (10, 3)
    assert heal(c) == 11
    assert heal(sts.Combat(DECK, "jaw_worm", seed=3, relics=["Burning Blood"])) == 12
    with pytest.raises(ValueError, match='unknown relic "gen:py_rel_nope"'):
        sts.Combat(DECK, "jaw_worm", relics=["gen:py_rel_nope"])


def test_many_relic_powers_play():
    # 16 Act 1 relics (RELIC_CAP) fit one fight (no helper powers,
    # docs/specs/relic-entity.md); so do 14 relics with distinct starting
    # buffs: a creature holds any number of powers, as the game's ArrayList.
    text = open(os.path.join(ROOT, "content", "packs", "act1-relics.json"), encoding="utf-8").read()
    sts.load_content(text)
    sts.Combat(DECK, "gremlin_nob", relics=["gen:" + r["id"] for r in json.loads(text)["relics"]][:16])
    powers = ["Strength", "Dexterity", "Thorns", "Artifact", "Ritual", "Metallicize", "Combust", "DemonForm", "Brutality",
              "Rage", "Rupture", "Accuracy", "Enrage", "Burst"]
    sts.load_content(json.dumps({"version": 2, "relics": [
        {"id": f"py_cap_{p}", "rarity": "common", "powers": [{"power": p, "amount": 1}]} for p in powers]}))
    c = sts.Combat(DECK, "gremlin_nob", relics=[f"gen:py_cap_{p}" for p in powers])
    assert len(c.view()["player"]["powers"]) >= 13


def test_fight_kind_from_the_encounter():
    assert sts.Combat(DECK, "jaw_worm", seed=4, relics=["gen:py_rel_collar"]) == sts.Combat(DECK, "jaw_worm", seed=4)
    assert sts.Combat(DECK, "gremlin_nob", seed=4, relics=["gen:py_rel_collar"]).player_block_energy[1] == 4


def test_versus_group():
    def energy(**kw):
        return sts.Combat.versus(DECK, ["Jaw Worm"], seed=5, relics=["gen:py_rel_collar"], **kw).player_block_energy[1]
    assert energy() == 3
    assert energy(group="hallway") == 3
    assert energy(group="boss") == 4
    with pytest.raises(ValueError, match="unknown group"):
        energy(group="shop")


def test_run_spec_key():
    base = {"encounter": "jaw_worm", "deck": DECK, "seed": 11, "hp": 40}
    plain, none, held = sts.run("greedy", [base, {**base, "relics": None}, {**base, "relics": ["gen:py_rel_heal"]}], threads=1)
    assert plain == none
    assert plain["won"] and held["won"]
    assert held["hp_end"] == min(80, plain["hp_end"] + 5)
    with pytest.raises(ValueError, match="unknown relic"):
        sts.run("greedy", [{**base, "relics": ["Nope"]}], threads=1)


HALLWAYS = ["cultist", "jaw_worm", "two_louse", "small_slimes", "large_slime", "lots_of_slimes", "three_louse",
            "two_fungi_beasts", "looter", "exordium_thugs", "exordium_wildlife"]


def test_act1_relics_end_to_end():
    """Build step 5's sanity check: the written Act 1 relics (Vajra, Anchor)
    play through every hallway encounter from sts.run and cost less HP on
    average than none (not a measurement)."""
    sts.load_content(os.path.join(ROOT, "content", "packs", "act1-relics.json"))
    specs = [{"encounter": e, "deck": DECK, "seed": s} for e in HALLWAYS for s in range(4)]
    plain = sts.run("search", specs, threads=4)
    held = sts.run("search", [{**sp, "relics": ["gen:Vajra", "gen:Anchor"]} for sp in specs], threads=4)
    assert len(held) == len(specs)

    def lost(rs):
        return sum(r["hp_start"] - r["hp_end"] for r in rs) / len(rs)
    assert sum(r["won"] for r in held) >= sum(r["won"] for r in plain)
    assert lost(held) < lost(plain), (lost(held), lost(plain))
