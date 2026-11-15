"""Turn 1's order from Python (docs/specs/turn-start-draw.md, build step 3):
`sts.Combat(..., turn1_pre_draw=)`, `sts.Combat.versus(..., turn1_pre_draw=)`
and `sts.run`'s dict-spec key `"turn1_pre_draw"`. A pre-draw hook adding 6
Wounds to the hand leaves room for 4 drawn cards when it runs before the
draw (turn 2 on, or turn 1 with the option), 5 when after (turn 1's
default, the game's order)."""

import json

import pytest

import sts

PACK = json.dumps({"version": 2, "powers": [
    {"id": "py_t1_wounds", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always",
                                      "effects": [{"AddCard": {"card": "Wound", "n": 6, "pile": "Hand"}}]}]},
], "relics": [
    # The power before the opening draw (a `powers` list lands at CombatStart,
    # after it: docs/specs/relic-entity.md), so turn 1's hooks see it.
    {"id": "py_t1_wounds", "rarity": "common", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always",
     "effects": [{"Apply": {"power": "py_t1_wounds", "amount": 1, "target": "Me"}}]}]},
]})

DECK = None
RELICS = ["gen:py_t1_wounds"]


@pytest.fixture(scope="module", autouse=True)
def pack():
    global DECK
    sts.load_content(PACK)
    DECK = list(sts.starter_deck("ironclad"))


def drawn(c):
    hand = c.piles()["hand"]
    return sum(hand.values()) - hand.get("Wound", 0)


def test_combat_option():
    assert drawn(sts.Combat(DECK, "cultist", seed=1, relics=RELICS)) == 5
    assert drawn(sts.Combat(DECK, "cultist", seed=1, relics=RELICS, turn1_pre_draw=False)) == 5
    assert drawn(sts.Combat(DECK, "cultist", seed=1, relics=RELICS, turn1_pre_draw=True)) == 4
    # Without turn-start hooks the option changes nothing.
    assert sts.Combat(DECK, "cultist", seed=1, turn1_pre_draw=True) == sts.Combat(DECK, "cultist", seed=1)


def test_versus_option():
    def d(**kw):
        return drawn(sts.Combat.versus(DECK, ["Cultist"], seed=2, relics=RELICS, **kw))
    assert (d(), d(turn1_pre_draw=True)) == (5, 4)


def test_run_spec_key():
    base = {"encounter": "cultist", "deck": DECK, "seed": 3, "relics": RELICS}
    plain, off, on = sts.run("greedy", [base, {**base, "turn1_pre_draw": False}, {**base, "turn1_pre_draw": True}],
                             threads=1, record=True)
    assert plain == off
    assert plain["states"][0] != on["states"][0]
    assert drawn(plain["states"][0]) == 5 and drawn(on["states"][0]) == 4
