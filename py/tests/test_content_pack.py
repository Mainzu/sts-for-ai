"""Registry-lite through Python (docs/specs/registry-lite.md): a generated
copy of Demon Form loads from a pack, plays and encodes like Demon Form in
effects mode, and as unknown in ids mode. Run with
`python py/tests/test_content_pack.py` (plain asserts) or pytest.

Written in step 1 against the API step 3 builds; it fails until then:
`sts.load_content(str) -> str` (content hash), decks name generated cards
`gen:<id>`, and an action's `card` is that name.
"""

import json

import numpy as np
import sts

PACK = {
    "version": 1,
    "powers": [{"id": "gp_df", "debuff": False, "hooks": [
        {"trigger": "OwnerTurnStart", "condition": "Always",
         "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]}]}],
    "cards": [{"id": "gc_df", "cost": 3, "type": "Power", "exhaust": False, "ethereal": False,
               "effects": [{"Apply": {"power": "gp_df", "amount": 2, "target": "Me"}}]}],
}
COPY = "gen:gc_df"
# Five cards: all drawn on turn 1, so the hand is the same whichever id the
# Demon Form card has.
DECK = ["Strike"] * 4


def load():
    h = sts.load_content(json.dumps(PACK))
    assert isinstance(h, str) and h
    assert sts.load_content(json.dumps(PACK)) == h, "loading the same pack again is a no-op"
    return h


def pair(encounter="cultist", seed=1):
    a = sts.Combat(DECK + ["Demon Form"], encounter, seed=seed)
    b = sts.Combat(DECK + [COPY], encounter, seed=seed)
    return a, b


def play_power(c, name):
    act = next(x for x in c.legal_actions() if x.card == name)
    c.step(act)


def same_batch(x, y):
    assert x.keys() == y.keys()
    for k in x:
        assert np.array_equal(np.asarray(x[k]), np.asarray(y[k])), k


def test_effects_rows_match_demon_form():
    load()
    f = sts.Features("effects")
    a, b = pair()
    assert b.piles()["hand"] == {"Strike": 4, COPY: 1}
    same_batch(f.encode([a]), f.encode([b]))  # the card in hand: granted rows
    play_power(a, "Demon Form")
    play_power(b, COPY)
    same_batch(f.encode([a]), f.encode([b]))  # the power on the player: power rows


def test_plays_like_demon_form():
    load()
    for turns, seeds in ((1, 5), (2, 2)):  # one-turn and two-turn search
        for enc in ("cultist", "gremlin_nob", "hexaghost"):
            for seed in range(seeds):
                plays_alike(enc, seed, turns)


def plays_alike(enc, seed, turns):
    a, b = pair(enc, seed)
    play_power(a, "Demon Form")
    play_power(b, COPY)
    while not a.is_over():
        r = sts.search(a, "heuristic", turns=turns)
        assert sts.search(b, "heuristic", turns=turns)["action"] == r["action"], (enc, seed, turns)
        a.step(r["action"])
        b.step(r["action"])
        assert a.player_hp() == b.player_hp()
    assert b.is_over() and a.won() == b.won() and a.score() == b.score()


def test_ids_mode_sees_unknown():
    load()
    ids = sts.Features("ids")
    _, b = pair()
    batch = ids.encode([b])
    hand = batch["card_pile"] == sts.PILES.index("hand")
    unknown = ids.card_names.index("id_unknown")
    cols = batch["cards"][hand].argmax(axis=1)
    assert unknown in cols, "the generated card is the unknown card"
    play_power(b, COPY)
    p = ids.encode([b])["player"][0]
    assert p[ids.player_names.index("power_unknown")] == 2


def test_name_lists_stay_official():
    load()
    assert not any(n.startswith("gen:") for n in sts.all_card_names())
    assert not any(n.startswith("gen") or n.startswith("Gen") for n in sts.power_names())


def test_run_specs_with_generated_cards():
    load()
    deck = DECK + ["Demon Form"]
    copy = DECK + [COPY]
    specs = [("cultist", deck, s) for s in range(4)] + [{"encounter": "cultist", "deck": copy, "seed": s} for s in range(4)]
    res = sts.run("search", specs, threads=2, record=True)
    assert res[4]["deck"] == copy
    for a, b in zip(res[:4], res[4:]):
        assert (a["won"], a["hp_end"], a["turns"]) == (b["won"], b["hp_end"], b["turns"])
    names = {x.card for r in res[4:] for x in r["actions"] if x.card}
    assert names <= {"Strike", COPY}


def test_bound_state_has_no_encoding():
    load()
    a, b = pair()
    a.encode()
    try:
        b.encode()
        raise AssertionError("a bound state encoded")
    except ValueError:
        pass


def test_action_from_another_combat_refused():
    load()
    _, b = pair()
    act = next(x for x in b.legal_actions() if x.card == COPY)
    assert repr(act) == f"Action({COPY})" and sts.action_name(act) == COPY
    try:
        sts.Action(COPY)
        raise AssertionError("a generated card named without a combat")
    except ValueError:
        pass
    a, _ = pair()
    try:
        a.step(act)  # slot id means nothing in a combat without generated cards
        raise AssertionError("a generated action stepped in another combat")
    except ValueError:
        pass


def test_loaded_content_lists_the_hash():
    h = load()
    assert h in sts.loaded_content()


def test_many_generated_cards():
    # No card-slot cap past 40 any more (docs/specs/sparse-piles.md): 41
    # pack cards play, and 70 (past the old 52: the piles spill past 64
    # entries).
    cards = [{"id": f"gc_m{i}", "cost": 1, "type": "Skill", "exhaust": False, "ethereal": False,
              "effects": [{"Block": i + 1}]} for i in range(70)]
    sts.load_content(json.dumps({"version": 1, "powers": [], "cards": cards}))
    sts.Combat([f"gen:gc_m{i}" for i in range(41)], "cultist", seed=1)
    c = sts.Combat([f"gen:gc_m{i}" for i in range(70)], "cultist", seed=1)
    for _ in range(3):
        c.step(c.legal_actions()[0])


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
