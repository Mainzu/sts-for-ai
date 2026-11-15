"""Tests for `sts.Combat.versus` (docs/specs/monsters-from-packs.md): a
combat from monster names, official or from a loaded content pack. Run
with `python scripts/tests/test_versus.py` (plain asserts; every `test_*`
function runs) or with pytest. A second or less."""

import json
from pathlib import Path

import sts

DECK = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]

PACK = {
    "version": 1,
    "monsters": [
        {
            "id": "test_versus_brute",
            "hp": [20, 24],
            "start_powers": [{"power": "Strength", "amount": 1}],
            "moves": [
                {"name": "Hit", "effects": [{"Damage": {"amount": 6, "hits": 1, "target": "Opponent"}}]},
                {"name": "Guard", "effects": [{"Block": 5}]},
            ],
            "pattern": [
                {"when": [{"LastMove": 0}], "then": {"Move": 1}},
                {"when": [], "then": {"Move": 0}},
            ],
        }
    ],
}


def play_out(c):
    for _ in range(500):
        if c.is_over():
            return
        c.step(c.legal_actions()[0])
    raise AssertionError("no end")


def test_official_names_equal_the_encounter():
    for seed in range(5):
        a = sts.Combat(DECK, "cultist", seed=seed)
        b = sts.Combat.versus(DECK, ["Cultist"], seed=seed)
        assert a.encode() == b.encode(), seed
    a = sts.Combat(DECK, "three_sentries", seed=3)
    b = sts.Combat.versus(DECK, ["Sentry"] * 3, seed=3)
    assert a.encode() == b.encode()


def test_pack_monster_plays_and_refuses_encoding():
    sts.load_content(json.dumps(PACK))
    c = sts.Combat.versus(DECK, ["gen:test_versus_brute", "Jaw Worm"], seed=1)
    assert "gen:test_versus_brute" in c.render()
    try:
        c.encode()
    except ValueError:
        pass
    else:
        raise AssertionError("a pack monster's state encoded")
    play_out(c)


def test_bad_lists_are_refused():
    for monsters in ([], ["Cultist"] * 6, ["Nobody"], ["gen:never_loaded"], ["Slime Boss", "Cultist", "Cultist"]):
        try:
            sts.Combat.versus(DECK, monsters)
        except ValueError:
            continue
        raise AssertionError(f"{monsters} accepted")


ACT1_MONSTERS = Path(__file__).resolve().parents[2] / "content" / "packs" / "act1-monsters.json"


def test_pack_monster_with_a_pack_power():
    # The Mad Gremlin starts with the pack power Angry (block M5).
    sts.load_content(ACT1_MONSTERS.read_text(encoding="utf-8"))
    c = sts.Combat.versus(DECK, ["gen:Mad Gremlin"], seed=2)
    assert "Angry" in c.render()
    play_out(c)
    # 24 pack powers in the deck leave no slot for Angry.
    powers = [{"id": f"test_versus_p{i}"} for i in range(24)]
    cards = [
        {"id": f"test_versus_c{i}", "cost": 1, "type": "Skill", "effects": [{"Apply": {"power": f"test_versus_p{i}", "amount": 1, "target": "Me"}}]}
        for i in range(24)
    ]
    sts.load_content(json.dumps({"version": 1, "powers": powers, "cards": cards}))
    deck = DECK + [f"gen:test_versus_c{i}" for i in range(24)]
    sts.Combat.versus(deck, ["Jaw Worm"], seed=1)
    try:
        sts.Combat.versus(deck, ["gen:Mad Gremlin"], seed=1)
    except ValueError:
        pass
    else:
        raise AssertionError("25 pack powers accepted")


def test_pack_encounter_by_name():
    # encounters-as-data: a pack's encounter plays by name in Combat and sts.run.
    sts.load_content(ACT1_MONSTERS.read_text(encoding="utf-8"))
    c = sts.Combat(DECK, "gen:Blue Slaver", seed=2)
    assert "gen:Blue Slaver" in c.render()
    play_out(c)
    res = sts.run("greedy", [("gen:Blue Slaver", DECK, 3)], threads=1)
    assert len(res) == 1
    assert "gen:Blue Slaver" not in sts.encounter_names()
    assert sts.encounter_group("gen:Blue Slaver") == "hallway"
    assert sts.encounter_group("lagavulin") == "elite"
    assert sts.encounter_group("the_guardian") == "boss"
    try:
        sts.encounter_group("gen:no_such_encounter")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown encounter had a group")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
