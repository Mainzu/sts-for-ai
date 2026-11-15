"""Combat.view and Combat.from_view (docs/specs/real-game-bridge.md, build
step 1): a view turns back into an equal fight, on every encounter, at every
decision of randomly played fights with Act 1 pack cards, relics and potions."""

import json
import os
import random
import zlib
import sys

import pytest

import sts

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import action_text  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ACT1_PACKS = ["act1-ironclad", "act1-colorless", "act1-monsters", "act1-relics", "act1-potions"]
BOSSES = {"slime_boss", "Hexaghost", "Slime Boss", "The Guardian"}
ELITES = {"gremlin_nob", "lagavulin", "three_sentries", "Gremlin Nob", "Lagavulin", "Sentry"}
FIGHTS_PER_ENCOUNTER = 3
STATUS = {"Wound", "Dazed", "Slimed", "Burn"}


@pytest.fixture(scope="module", autouse=True)
def packs():
    for p in ACT1_PACKS:
        sts.load_content(os.path.join(ROOT, "content", "packs", p + ".json"))


def tables():
    with open(os.path.join(ROOT, "content", "game_ids.json"), encoding="utf-8") as f:
        return json.load(f)


def group(encounter):
    return "boss" if encounter in BOSSES else "elite" if encounter in ELITES else "hallway"


def random_fight(rng, encounter, t):
    """A fight against `encounter` (an encounter id, or a monster's name
    fought alone) with a random deck of loaded cards, three relics and two
    potions from the name tables."""
    cards = sorted(n for n in set(t["cards"].values()) if n not in STATUS)
    deck = ["Strike"] * 4 + ["Defend"] * 4 + ["Bash"] + rng.sample(cards, 8)
    deck = [c + "+" if rng.random() < 0.3 and c + "+" in t["upgradable"] else c for c in deck]
    relics = rng.sample(sorted(set(t["relics"].values()) - {"Burning Blood"}), 3)
    potions = rng.sample(sorted(set(t["potions"].values())), 2)
    for _ in range(20):
        try:
            return make(deck, encounter, rng.randrange(1 << 30), relics, potions)
        except ValueError:  # a relic or potion this fight's kind can't hold: draw again
            relics = rng.sample(sorted(set(t["relics"].values()) - {"Burning Blood"}), 3)
            potions = rng.sample(sorted(set(t["potions"].values())), 2)
    return make(deck, encounter, rng.randrange(1 << 30), None, None)


def make(deck, encounter, seed, relics, potions):
    if encounter in sts.encounter_names():
        return sts.Combat(deck, encounter, seed=seed, relics=relics, potions=potions)
    return sts.Combat.versus(deck, [encounter], seed=seed, relics=relics, potions=potions, group=group(encounter))


def texts(c):
    return sorted(action_text.encode_action(a) for a in c.legal_actions())


def check_round_trip(c, encounter, seed):
    v = c.view()
    back = sts.Combat.from_view(v, seed=seed, group=group(encounter))
    assert back.view() == v
    assert texts(back) == texts(c)
    # Every option reaches the same outcomes with the same odds. (Not the
    # same sample for one seed: the rebuilt deck binds pack cards to other
    # ids, so one random number can name another card.)
    assert outcomes(back) == outcomes(c)


def outcomes(c):
    """{option's action texts: sorted [(odds, the child's view or its end)]}."""
    out = {}
    for actions, _, children in c.options(16):
        key = tuple(action_text.encode_action(a) for a in actions)
        rows = []
        for p, child in children:
            if child.is_over():
                state = ("over", child.won(), child.player_hp())
            else:
                try:
                    cv = child.view()
                    # The HP-loss count's cap comes from every card the fight
                    # binds (a potion's offers too), so a rebuild may count
                    # fewer losses; it matters only to a card in the piles
                    # that costs less per loss (Blood for Blood).
                    if not any("Blood for Blood" in n for k in ("hand", "draw", "discard", "exhaust") for n in cv[k]):
                        cv.pop("times_lost_hp")
                    state = json.dumps(cv, sort_keys=True)
                except ValueError:  # at a pick or a paused event: its board, lists sorted
                    b = child.board()  # (it lists cards and powers in binding order)
                    b["hand"] = sorted(json.dumps(h, sort_keys=True) for h in b.get("hand", []))
                    for who in [b["player"]] + b.get("monsters", []):
                        who["powers"] = sorted(json.dumps(p, sort_keys=True) for p in who.get("powers", []))
                    state = json.dumps([b, child.piles()], sort_keys=True, default=str)
            rows.append((round(p, 9), state))
        merged = {}
        for p, state in rows:
            merged[state] = round(merged.get(state, 0.0) + p, 9)
        out[key] = sorted(((p, s) for s, p in merged.items()), key=str)
    return out


@pytest.fixture(scope="module")
def t():
    out = tables()
    upgradable = set()
    for n in set(out["cards"].values()):
        try:
            sts.Combat([n + "+"], "jaw_worm")
            upgradable.add(n + "+")
        except ValueError:
            pass
    out["upgradable"] = upgradable
    return out


def monster_names():
    return sorted({m["engine"] for m in tables()["monsters"].values()})


@pytest.mark.parametrize("encounter", sts.encounter_names() + monster_names())
def test_round_trip(encounter, t):
    rng = random.Random(zlib.crc32(encounter.encode()))
    checked = 0
    for k in range(FIGHTS_PER_ENCOUNTER):
        c = random_fight(rng, encounter, t)
        while not c.is_over() and c.turn() <= 12:
            if c.awaiting_action():
                try:
                    c.view()
                    ok = True
                except ValueError:
                    ok = False
                if ok:
                    check_round_trip(c, encounter, rng.randrange(1 << 30))
                    checked += 1
            c.step(rng.choice(c.legal_actions()))
    assert checked > 0


def test_unknown_move_refused():
    with pytest.raises(ValueError):
        sts.Combat.from_view({"player": {"hp": 80, "max_hp": 80, "block": 0, "energy": 3}, "monsters": [{"name": "Jaw Worm", "hp": 40, "max_hp": 40, "block": 0, "moves": [99, None]}]})


def test_unknown_names_refused():
    v = sts.Combat(["Strike"] * 5, "jaw_worm", seed=1).view()
    v["hand"] = {"Not A Card": 1}
    with pytest.raises(ValueError):
        sts.Combat.from_view(v)


def test_burning_elite_regenerate_round_trip():
    """A burning elite with Regenerate (the pack power, game id the same)
    shows it and comes back from its view."""
    c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], "gremlin_nob", seed=3, elite_buff="regenerate")
    assert c.view()["monsters"][0]["powers"]["Regenerate"] == 3
    assert tables()["powers"]["Regenerate"] == "Regenerate"
    check_round_trip(c, "gremlin_nob", 7)


# Run 78 (results/real-game/20261114-203425, decisions row 41, floor 11).
RUN78_VIEW = {"turn": 3, "cards_played_this_turn": 0, "start_hp": 55, "player": {"hp": 40, "max_hp": 82, "block": 0, "energy": 3, "powers": {"Metallicize": 3, "Vulnerable": 2}, "relics": [["gen:Dead Branch", 0]], "potions": [], "just_applied": []}, "hand": {"Thunderclap": 1, "gen:Juggernaut": 1, "Strike": 2, "gen:Ascender's Bane": 1}, "draw": {"Strike": 1, "Defend": 1}, "discard": {"Defend": 3, "Clothesline": 1, "Perfected Strike": 2, "Strike": 2, "Bash": 1}, "exhaust": {}, "monsters": [{"name": "Red Louse", "hp": 11, "max_hp": 11, "block": 0, "powers": {"CurlUp": 11}, "escaped": False, "moves": [1, 0], "rolled_damage": 6, "just_applied": []}, {"name": "gen:Red Slaver", "hp": 33, "max_hp": 51, "block": 0, "powers": {}, "escaped": False, "moves": [0, 1], "rolled_damage": 0, "just_applied": []}], "ascension": 20, "times_lost_hp": 3, "boss_fight": False, "free": {}, "top": [], "top_floaters": []}


def test_run78_search_past_twelve_powers():
    """Run 78: after Thunderclap, the two-turn search (fight seed 30, the
    bridge's sample seed) looks at turns where Dead Branch's random cards
    under Corruption give the player a 13th power. It panicked at the old
    12-power cap; a creature now holds any number, as in the game."""
    c = sts.Combat.from_view(RUN78_VIEW, seed=30, group="hallway")
    c.step(action_text.decode_in(c, "Thunderclap"))
    r = sts.search(c, None, limit=16, turns=2, sample_k=4, max_nodes=400_000, seed=30 * 1009 + 3)
    assert r["nodes"] > 0


def test_thirteen_powers_view():
    """A player holding 12 powers plays Inflame: Strength 2 is the 13th,
    and the view (13 powers) comes back as an equal fight."""
    twelve = ["Metallicize", "Vulnerable", "Juggernaut", "Corruption", "Barricade", "DarkEmbrace", "FeelNoPain", "Evolve",
              "FireBreathing", "Rupture", "DemonForm", "Combust"]
    v = json.loads(json.dumps(RUN78_VIEW))
    v["player"]["powers"] = {p: 1 for p in twelve}
    v["hand"] = {"Inflame": 1}
    c = sts.Combat.from_view(v, seed=1, group="hallway")
    c.step(action_text.decode_in(c, "Inflame"))
    powers = c.view()["player"]["powers"]
    assert len(powers) == 13 and powers["Strength"] == 2, powers
    assert sts.Combat.from_view(c.view(), seed=1, group="hallway").view() == c.view()


def test_runic_dome_hidden_move_from_view():
    """Runic Dome (docs/research/build-plans-2026-11-14/frozen-eye-runic-dome.md):
    a view's "move_hidden" monster, "moves" then its history, rebuilds
    with its roll still to come; one that can only be one move is set and
    shown; the view comes back as an equal fight."""
    v = sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], "jaw_worm", seed=1).view()
    v["player"]["relics"] = [["gen:Runic Dome", 0]]
    v["monsters"][0]["moves"] = [0, None]  # Chomp used
    v["monsters"][0]["move_hidden"] = True
    c = sts.Combat.from_view(v, seed=1, group="hallway")
    w = c.view()
    assert w["monsters"][0]["intent_hidden"] == 1 and w["monsters"][0]["moves"] == (0, None), w["monsters"][0]
    assert sts.Combat.from_view(w, seed=1, group="hallway").view() == w
    # Cultist after Incantation: Dark Strike only, set and shown.
    v = sts.Combat(["Strike"] * 5, "cultist", seed=1).view()
    v["player"]["relics"] = [["gen:Runic Dome", 0]]
    v["monsters"][0]["moves"] = [0, None]
    v["monsters"][0]["move_hidden"] = True
    m = sts.Combat.from_view(v, seed=1, group="hallway").view()["monsters"][0]
    assert m["moves"] == (1, 0) and "intent_hidden" not in m, m
