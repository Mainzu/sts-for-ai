"""Potions from Python (docs/specs/potions.md): giving them to fights (build
step 2: `sts.Combat(..., potions=)`, `sts.Combat.versus(..., potions=)`,
`sts.run`'s dict-spec key `"potions"`, `Combat.potions`) and using them
(step 4: `sts.Action.potion`, its text `Potion:<slot>[@<target>]`, the
board, replays, the explorer's words)."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402

PACK = json.dumps({"version": 2, "powers": [
    {"id": "PyPotFade", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": ["RemoveSelf"]}]},
], "potions": [
    {"id": "py_pot_fire", "rarity": "common", "potency": 20, "effects": [{"Damage": {"amount": 20, "target": "Opponent"}}]},
    {"id": "py_pot_swift", "rarity": "common", "potency": 3, "effects": [{"Draw": 3}]},
    {"id": "py_pot_fade", "rarity": "rare", "potency": 1,
     "effects": [{"Apply": {"power": "PyPotFade", "amount": 1, "target": "Me"}}]},
]})

DECK = None


@pytest.fixture(scope="module", autouse=True)
def pack():
    global DECK
    sts.load_content(PACK)
    DECK = list(sts.starter_deck("ironclad"))


def test_no_potions_is_the_default():
    plain = sts.Combat(DECK, "jaw_worm", seed=3)
    assert plain.potions == []
    for kw in ({"potions": None}, {"potions": []}):
        assert sts.Combat(DECK, "jaw_worm", seed=3, **kw) == plain


def test_combat_potions_sorted():
    a = sts.Combat(DECK, "jaw_worm", seed=3, potions=["gen:py_pot_swift", "gen:py_pot_fire", "gen:py_pot_fire"])
    b = sts.Combat(DECK, "jaw_worm", seed=3, potions=["gen:py_pot_fire", "gen:py_pot_swift", "gen:py_pot_fire"])
    assert a == b
    assert a.potions == ["gen:py_pot_fire", "gen:py_pot_fire", "gen:py_pot_swift"]
    assert a != sts.Combat(DECK, "jaw_worm", seed=3)
    with pytest.raises(ValueError, match='unknown potion "gen:py_pot_nope"'):
        sts.Combat(DECK, "jaw_worm", potions=["gen:py_pot_nope"])
    with pytest.raises(ValueError, match="POTION_CAP"):
        sts.Combat(DECK, "jaw_worm", potions=["gen:py_pot_fire"] * 6)


def test_versus_potions():
    c = sts.Combat.versus(DECK, ["Jaw Worm"], seed=3, potions=["gen:py_pot_fade"])
    assert c.potions == ["gen:py_pot_fade"]


def test_run_spec_key():
    base = {"encounter": "jaw_worm", "deck": DECK, "seed": 11, "hp": 40}
    plain, none, held = sts.run("greedy", [base, {**base, "potions": None}, {**base, "potions": ["gen:py_pot_fire"]}], threads=1)
    assert plain == none
    # Since step 3 a held potion is an action the agent may take.
    assert isinstance(held["won"], bool) and held["hp_end"] >= 0
    with pytest.raises(ValueError, match="unknown potion"):
        sts.run("greedy", [{**base, "potions": ["Nope"]}], threads=1)


def test_potion_action():
    a, b = sts.Action.potion(1, 0), sts.Action.potion(2)
    assert (a.kind, a.slot, a.target, a.card, a.is_end_turn) == ("potion", 1, 0, None, False)
    assert (b.kind, b.slot, b.target) == ("potion", 2, None)
    assert a == sts.Action.potion(1, 0) and a != sts.Action.potion(1, 1) and a != b
    assert sts.Action("Strike", 0).slot is None
    assert sts.action_name(a) == "Potion 1 -> slot 0" and sts.action_name(b) == "Potion 2"


def test_potion_text_roundtrip():
    """Every legal potion use encodes to `Potion:...` and decodes back to the
    same action."""
    import action_text as at
    c = sts.Combat.versus(DECK, ["Red Louse", "Green Louse"], seed=5,
                          potions=["gen:py_pot_fire", "gen:py_pot_swift"])
    uses = [a for a in c.legal_actions() if a.kind == "potion"]
    texts = [at.encode_action(a) for a in uses]
    assert texts == ["Potion:0@0", "Potion:0@1", "Potion:1"], texts
    for a, t in zip(uses, texts):
        assert at.decode_action(t) == a and at.decode_in(c, t) == a


def test_board_and_render_show_potions():
    c = sts.Combat(DECK, "jaw_worm", seed=3, potions=["gen:py_pot_swift", "gen:py_pot_fire"])
    assert c.board()["player"]["potions"] == ["gen:py_pot_fire", "gen:py_pot_swift"]
    assert "Potions 0:gen:py_pot_fire, 1:gen:py_pot_swift" in c.render().splitlines()
    plain = sts.Combat(DECK, "jaw_worm", seed=3)
    assert plain.board()["player"]["potions"] == [] and "Potions" not in plain.render()


def test_recorded_potion_game_replays():
    """A game whose record uses a potion replays to its recorded outcome."""
    import action_text as at
    import registry
    rec = {"encounter": "jaw_worm", "deck": DECK, "seed": 7, "hp": 40, "potions": ["gen:py_pot_fire"]}
    c = at.combat_of(rec)
    actions, k = [], 0
    while not c.is_over() and c.turn() < 60:
        if not c.awaiting_action():
            c.advance()
            continue
        a = next(x for x in c.legal_actions() if x.kind == "potion") if k == 0 else sts.random_action(c, k)
        k += 1
        actions.append(at.encode_action(a))
        c.step(a)
    assert actions[0] == "Potion:0@0"
    rec.update(actions=actions, outcome={"won": c.won(), "score": c.score(), "turns": c.turn(),
                                         "hp_start": 40, "hp_end": c.player_hp()})
    out = registry.replay(rec)
    assert out["won"] == c.won() and out["hp_end"] == c.player_hp()
    assert out["actions"][0] == sts.Action.potion(0, 0)


def test_explorer_words_potions():
    import explore
    q = {"id": "py_pot_fire", "rarity": "common", "potency": 20,
         "effects": [{"Damage": {"amount": 20, "target": "Opponent"}}]}
    d = explore.describe_potion(q)
    assert d["head"] == "py_pot_fire · Common potion"
    assert d["lines"][-1] == "Potency 20 (Sacred Bark doubles it)."
    assert any("20" in ln and "damage" in ln.lower() for ln in d["lines"][:-1]), d
    assert explore.describe_potion({"id": "x", "rarity": "rare", "effects": []})["lines"] == ["No effect when used."]
    # A triggered potion (Fairy in a Bottle, docs/specs/would-die.md) says
    # it can't be drunk, before its heal.
    fairy = {"id": "Fairy in a Bottle", "rarity": "rare", "potency": 30, "trigger": "OwnerDied",
             "effects": [{"HealOf": {"base": 0, "k": "3/10", "of": "OwnMaxHp"}}]}
    explore.UNWORDED.clear()
    lines = explore.describe_potion(fairy)["lines"]
    assert lines[0].startswith("Can't be drunk") and "Potency 30" in lines[-1], lines
    assert not explore.UNWORDED, explore.UNWORDED


def test_explorer_words_sacred_bark():
    import explore
    d = explore.describe_relic({"id": "Sacred Bark", "rarity": "boss", "potion_potency": 2}, {})
    assert d["lines"] == ["Potions with a potency act 2 times as strongly."], d
    assert explore.describe_relic({"id": "x", "rarity": "boss"}, {})["lines"] == ["No effect in a fight."]


def test_escaped():
    """Smoke Bomb's `Escape` (docs/specs/act1-singles.md): the fight ends as
    won and `Combat.escaped` says so; held in a boss fight."""
    sts.load_content(json.dumps({"version": 2, "potions": [
        {"id": "py_pot_smoke", "rarity": "rare", "fights": ["hallway", "elite"], "effects": ["Escape"]}]}))
    c = sts.Combat(DECK, "jaw_worm", seed=3, potions=["gen:py_pot_smoke"])
    assert not c.escaped
    c.step(sts.Action.potion(0))
    assert c.is_over() and c.won() and c.escaped
    boss = sts.Combat(DECK, "slime_boss", seed=3, potions=["gen:py_pot_smoke"])
    assert not any(a.kind == "potion" for a in boss.legal_actions())
