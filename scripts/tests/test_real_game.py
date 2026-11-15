"""The real-game bridge's translator and controller (docs/specs/real-game-bridge.md,
build steps 3-4), against a fake game: an engine fight written out as
CommunicationMod's states (its field names, from the mod's GameStateConverter)
that takes CommunicationMod's commands."""

import io
import json
import os
import random
import sys

import pytest

import sts

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import game_ids  # noqa: E402
import real_game  # noqa: E402

ENCOUNTERS = ["jaw_worm", "cultist", "two_louse", "gremlin_nob", "lagavulin", "three_sentries", "slime_boss"]
SOLO = ["Hexaghost", "The Guardian"]


@pytest.fixture(scope="module", autouse=True)
def packs():
    real_game.load_packs()


@pytest.fixture(autouse=True)
def own_run_mark(tmp_path, monkeypatch):
    """No test touches the live run mark (results/real-game/ironclad-run-started):
    end_run removes it, and without it the controller won't replace its own save."""
    mark = str(tmp_path / "ironclad-run-started")
    monkeypatch.setattr(real_game, "run_mark", lambda: mark)
    # nor the game's real Ironclad save
    save = str(tmp_path / "saves" / "IRONCLAD.autosave")
    monkeypatch.setattr(real_game, "ironclad_save", lambda: save)


def game_id(kind, name):
    ids = game_ids.game_ids(kind, name)
    assert ids, "%s %s has no game id" % (kind, name)
    return ids[0]


def game_card(name):
    base = name.split("{")[0]
    up = 1 if base.endswith("+") else 0
    stem = base[:-1] if up else base
    return {"id": game_id("cards", stem), "upgrades": up, "is_playable": True, "name": stem}


def game_powers(powers):
    hidden = real_game.engine_only_powers()
    return [{"id": game_id("powers", p), "amount": n} for p, n in powers.items() if p not in hidden]


def move_byte(game_monster, pos):
    for b, positions in game_ids.moves(game_monster).items():
        if pos in positions:
            return b
    raise AssertionError("%s move %s has no game byte" % (game_monster, pos))


def write_out(c, group="hallway", floor=1, pick=None, hand_order=None):
    """CommunicationMod's message for engine fight `c` (at the player's turn,
    or at a pick with `pick` the offered cards)."""
    v = c.view() if pick is None else None
    b = c.board()
    piles = c.piles()
    hand = hand_order if hand_order is not None else [n for n, k in sorted(piles["hand"].items()) for _ in range(k)]
    monsters = []
    src = v["monsters"] if v else None
    for i, m in enumerate(src or []):
        gid = game_id("monsters", m["name"])
        out = {"id": gid, "name": m["name"], "current_hp": m["hp"], "max_hp": m["max_hp"], "block": m["block"],
               "powers": game_powers(m["powers"]), "is_gone": m["hp"] <= 0 or m["escaped"], "half_dead": False}
        if m["hp"] > 0 and m["moves"][0] is not None:
            out["move_id"] = move_byte(gid, m["moves"][0])
            out["move_base_damage"] = m["rolled_damage"] if "Louse" in m["name"] else -1
        monsters.append(out)
    room = {"boss": "MonsterRoomBoss", "elite": "MonsterRoomElite"}.get(group, "MonsterRoom")
    pl = v["player"] if v else {"powers": {}, "relics": [], "potions": [], "hp": b["player"]["hp"],
                                "max_hp": b["player"]["max_hp"], "block": b["player"]["block"], "energy": b["player"]["energy"]}
    gs = {"screen_type": "NONE" if pick is None else "GRID", "room_type": room, "floor": floor, "room_phase": "COMBAT",
          "current_hp": pl["hp"], "max_hp": pl["max_hp"],
          "relics": [{"id": "Burning Blood", "counter": -1}] + [{"id": game_id("relics", n), "counter": k} for n, k in pl["relics"]],
          "potions": [{"id": game_id("potions", n)} for n in pl["potions"]] + [{"id": "Potion Slot"}],
          "combat_state": {"turn": c.turn(), "monsters": monsters,
                           "player": {"current_hp": pl["hp"], "max_hp": pl["max_hp"], "block": pl["block"],
                                      "energy": pl["energy"], "powers": game_powers(pl["powers"])},
                           "hand": [game_card(n) for n in hand],
                           "draw_pile": [game_card(n) for n, k in sorted(piles["draw"].items()) for _ in range(k)],
                           "discard_pile": [game_card(n) for n, k in sorted(piles["discard"].items()) for _ in range(k)],
                           "exhaust_pile": [game_card(n) for n, k in sorted(piles["exhaust"].items()) for _ in range(k)]}}
    if pick is not None:
        gs["screen_state"] = {"cards": [game_card(n) for n in pick]}
    avail = ["play", "end"] if pick is None else ["choose", "confirm"]
    return {"in_game": True, "ready_for_command": True, "available_commands": avail, "game_state": gs}


def fight(encounter, deck, seed, relics=None, potions=None):
    if encounter in sts.encounter_names():
        return sts.Combat(deck, encounter, seed=seed, relics=relics, potions=potions)
    return sts.Combat.versus(deck, [encounter], seed=seed, relics=relics, potions=potions, group="boss")


DECK = ["Strike"] * 4 + ["Defend"] * 4 + ["Bash", "Inflame", "gen:True Grit", "Pommel Strike", "Shrug It Off"]


@pytest.mark.parametrize("encounter", ENCOUNTERS + SOLO)
def test_translate_round_trip(encounter):
    """The game's view of an engine fight, merged with that fight's own view as
    the prior, is that view again; with no prior, every shown part is."""
    rng = random.Random(len(encounter))
    c = fight(encounter, DECK, 5, relics=["gen:Anchor", "gen:Vajra"], potions=["gen:Fire Potion"])
    checked = 0
    while not c.is_over() and c.turn() <= 8:
        try:
            v = c.view()
        except ValueError:
            v = None
        if v is not None and c.awaiting_action():
            f = {"left_out": set(), "played_this_turn": v["cards_played_this_turn"], "start_hp": v["start_hp"]}
            obs = real_game.observed(write_out(c)["game_state"], f)
            assert not f["left_out"]
            v = real_game.plain(v)
            assert real_game.merge(obs, [v], {}, []) == v
            checked += 1
        c.step(rng.choice(c.legal_actions()))
    assert checked


class FakeGame:
    """An engine fight that answers CommunicationMod's commands."""

    def __init__(self, c, group="hallway"):
        self.c, self.group, self.refused = c, group, []
        self.hand = None

    def message(self):
        if self.c.is_over():
            return {"in_game": True, "ready_for_command": True, "available_commands": ["proceed"],
                    "game_state": {"screen_type": "COMBAT_REWARD", "floor": 1, "current_hp": self.c.player_hp()}}
        acts = self.c.legal_actions()
        picks = [a.card for a in acts if a.kind == "choose"]
        if picks:
            self.offer = picks
            return write_out(self.c, self.group, pick=picks)
        piles = self.c.piles()
        self.hand = [n for n, k in sorted(piles["hand"].items(), reverse=True) for _ in range(k)]  # not the engine's order
        return write_out(self.c, self.group, hand_order=self.hand)

    def command(self, cmd):
        t = cmd.split()
        legal = {real_game_text(a): a for a in self.c.legal_actions()}
        if t[0] == "end":
            a = legal.get("End")
        elif t[0] == "play":
            j = int(t[1]) - 1 if t[1] != "0" else 9
            key = self.hand[j] + ("@" + t[2] if len(t) > 2 else "")
            a = legal.get(key)
        elif t[0] == "choose":
            a = legal.get("Choose:" + self.offer[int(t[1])])
        elif t[0] == "wait":  # CommunicationMod sends the state again after some frames
            return
        elif t[0] == "confirm":
            a = legal.get("Done")
            if a is None:
                return
        elif t[0] == "potion":
            v = self.c.view()
            name = game_ids.engine_name("potions", self.message_potions()[int(t[2])])
            slot = v["player"]["potions"].index(name)
            a = legal.get("Potion:%d" % slot + ("@" + t[3] if len(t) > 3 else ""))
        else:
            a = None
        if a is None:
            self.refused.append(cmd)
            return {"error": "refused " + cmd}
        self.c.step(a)

    def message_potions(self):
        return [p["id"] for p in write_out(self.c, self.group)["game_state"]["potions"]]


def real_game_text(a):
    import action_text
    return action_text.encode_action(a)


def run(game, max_steps=400, two=None, relics_unknown=False):
    out = io.StringIO()
    d = os.path.join(os.environ.get("PYTEST_TMP", "."), "rg")
    bridge = real_game.Bridge.__new__(real_game.Bridge)
    import bench
    real_game.setup_paths()
    bridge.ev = bench.load_evaluator("heuristic")
    bridge.two = two or {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 5000}
    bridge.out = out
    bridge.dir = d
    bridge.fight = None
    bridge.runs_left, bridge.run, bridge.card_done, bridge.errors = 0, None, None, 0
    os.makedirs(d, exist_ok=True)
    bridge.files = {k: open(os.path.join(d, k + ".jsonl"), "a", encoding="utf-8") for k in ("states", "decisions", "fights", "runs")}
    for _ in range(max_steps):
        msg = game.message()
        if relics_unknown and "relics" in msg.get("game_state", {}):
            msg["game_state"]["relics"].append({"id": "Not A Relic", "counter": -1})
        before = out.tell()
        bridge.handle(msg)
        if game.c.is_over():
            bridge.handle({"in_game": True, "ready_for_command": True, "game_state": {"floor": 2, "current_hp": game.c.player_hp()}})
            break
        sent = out.getvalue()[before:].strip()
        if not sent:
            break
        err = game.command(sent)
        if err:
            bridge.handle(err)
    for f in bridge.files.values():
        f.close()
    with open(os.path.join(d, "fights.jsonl"), encoding="utf-8") as f:
        return [json.loads(x) for x in f][-1]


@pytest.mark.parametrize("encounter", ["jaw_worm", "gremlin_nob", "three_sentries", "Hexaghost"])
def test_controller_plays_fake_game(encounter, tmp_path, monkeypatch):
    monkeypatch.setenv("PYTEST_TMP", str(tmp_path))
    game = FakeGame(fight(encounter, DECK, 11, potions=["gen:Block Potion"]), "boss" if encounter == "Hexaghost" else "hallway")
    rec = run(game)
    assert game.c.is_over(), "the fight didn't finish: %s" % rec
    assert rec["handed_over"] is None
    assert not game.refused
    assert rec["predicted"] > 0 and rec["matched"] == rec["predicted"], rec["mismatches"]


def test_unknown_relic_plays_and_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTEST_TMP", str(tmp_path))
    game = FakeGame(fight("jaw_worm", DECK, 3))
    rec = run(game, relics_unknown=True)
    assert game.c.is_over() and rec["handed_over"] is None
    assert "relic Not A Relic" in rec["left_out"]


def test_unknown_card_hands_over():
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    msg = write_out(fight("jaw_worm", DECK, 3))
    msg["game_state"]["combat_state"]["hand"].append({"id": "Not A Card", "upgrades": 0})  # never in the content
    with pytest.raises(real_game.HandOver, match="Not A Card"):
        real_game.observed(msg["game_state"], f)


def test_commands():
    c = fight("jaw_worm", DECK, 3)
    msg = write_out(c)
    gs, v = msg["game_state"], c.view()
    assert real_game.command_for(sts.Action(), gs, v) == "end"
    a = [x for x in c.legal_actions() if x.kind == "play" and x.target is not None][0]
    cmd = real_game.command_for(a, gs, v)
    j = int(cmd.split()[1]) - 1
    assert real_game.card_of(gs["combat_state"]["hand"][j]) == a.card and cmd.endswith(" %d" % a.target)


PICK_DECKS = {
    "armaments": DECK[:-3] + ["gen:Armaments", "gen:Armaments", "Shrug It Off"],
    "true_grit_plus": DECK[:-3] + ["gen:True Grit+", "gen:True Grit+", "Shrug It Off"],
    "burning_pact": DECK[:-3] + ["gen:Burning Pact", "gen:Burning Pact", "Shrug It Off"],
}


@pytest.mark.parametrize("deck", sorted(PICK_DECKS))
def test_controller_answers_picks(deck, tmp_path, monkeypatch):
    """Cards that stop at a pick: the line's choice reaches the game as
    `choose`/`confirm`; a pick followed by a draw isn't counted as predicted."""
    monkeypatch.setenv("PYTEST_TMP", str(tmp_path))
    game = FakeGame(fight("jaw_worm", PICK_DECKS[deck], 7))
    rec = run(game)
    assert game.c.is_over() and rec["handed_over"] is None and not game.refused
    assert rec["matched"] == rec["predicted"], rec["mismatches"]


def test_gambling_chip_keeps_the_hand(tmp_path, monkeypatch):
    """A pick before the first turn (Gambling Chip) is confirmed, not handed over."""
    monkeypatch.setenv("PYTEST_TMP", str(tmp_path))
    game = FakeGame(fight("jaw_worm", DECK, 4, relics=["gen:Gambling Chip"]))
    rec = run(game)
    assert game.c.is_over() and rec["handed_over"] is None, rec


def test_relic_that_does_not_act_here():
    """Pantograph acts only in boss fights: a hallway view holding it builds,
    and the translator keeps only the relics the fight holds."""
    c = fight("jaw_worm", DECK, 3)
    v = real_game.plain(c.view())
    v["player"]["relics"] = [["gen:Pantograph", 0], ["gen:Anchor", 0]]
    built = sts.Combat.from_view(v, seed=1, group="hallway")
    kept = [r[0] for r in built.view()["player"]["relics"]]
    assert "gen:Pantograph" not in kept
    msg = write_out(c)
    msg["game_state"]["relics"].append({"id": game_id("relics", "gen:Pantograph"), "counter": -1})
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    obs = real_game.observed(msg["game_state"], f)
    merged = real_game.merge(obs, [real_game.plain(c.view())], {}, [])
    assert "gen:Pantograph" not in [r[0] for r in merged["player"]["relics"]]
    sts.Combat.from_view(merged, seed=1, group="hallway")


def test_split_slot_map():
    """After Slime Boss splits, the game lists [dead boss, halves]: the view
    leaves the boss out and targets go through the slot map."""
    c = fight("Slime Boss", DECK, 3)
    msg = write_out(c)
    gs = msg["game_state"]
    boss = gs["combat_state"]["monsters"][0]
    boss.update({"current_hp": 0, "is_gone": True})
    for gid, move in (("SpikeSlime_L", 1), ("AcidSlime_L", 2)):
        gs["combat_state"]["monsters"].append({"id": gid, "current_hp": 70, "max_hp": 70, "block": 0, "powers": [],
                                               "is_gone": False, "move_id": move, "move_base_damage": -1})
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    obs = real_game.observed(gs, f)
    assert [m["name"] for m in obs["monsters"]] == ["Spike Slime (L)", "Acid Slime (L)"]
    slots = [m["game_index"] for m in obs["monsters"]]
    assert slots == [1, 2]
    view = real_game.merge(obs, [], {}, [])
    built = sts.Combat.from_view(view, seed=1, group="boss")
    a = [x for x in built.legal_actions() if x.kind == "play" and x.target == 1][0]
    assert real_game.command_for(a, gs, view, slots).endswith(" 2")


def test_card_choice_in_a_fight_takes_the_first(tmp_path):
    """A potion's card choice (CARD_REWARD inside a fight): the first card,
    noted; the fight goes on from the game's next state."""
    b = real_game.Bridge.__new__(real_game.Bridge)
    b.dir, b.fight, b.out = str(tmp_path), None, io.StringIO()
    b.runs_left, b.run, b.card_done, b.errors = 0, None, None, 0
    b.files = {k: open(os.path.join(str(tmp_path), k + ".jsonl"), "a", encoding="utf-8") for k in ("states", "decisions", "fights", "runs")}
    msg = write_out(fight("jaw_worm", DECK, 3))
    msg["game_state"]["screen_type"] = "CARD_REWARD"
    msg["game_state"]["screen_state"] = {"cards": [{"id": "Not A Card", "upgrades": 0}, game_card("Strike")]}
    msg["available_commands"] = ["choose", "skip"]
    b.handle(msg)  # a card the engine doesn't load (live run 30: Secret Technique) is passed over
    assert b.fight["handed_over"] is None and b.out.getvalue().strip() == "choose 1"
    assert any("card choice" in x for x in b.fight["left_out"])
    msg["game_state"]["screen_state"] = {"cards": [{"id": "Not A Card", "upgrades": 0}]}
    b.handle(msg)
    assert b.out.getvalue().splitlines()[-1] == "skip"
    for f in b.files.values():
        f.close()


def test_free_mark_only_where_the_game_shows_cost_0():
    """Liquid Memories on a card still flying to the discard pile: the game's
    animation resets its cost (live run 2026-11-14, floor 10), so the engine's
    free mark is kept only for hand copies the game shows at cost 0."""
    c = fight("jaw_worm", ["Rampage"] * 10, 3)
    prior = real_game.plain(c.view())
    prior["free"] = {"Rampage": 2}
    gs = write_out(c)["game_state"]
    hand = gs["combat_state"]["hand"]
    assert len(hand) == 5
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    # No cost shown (the fake game): the marks stay.
    assert real_game.merge(real_game.observed(gs, f), [prior], {}, [])["free"] == {"Rampage": 2}
    for k, card in enumerate(hand):
        card["cost"] = 0 if k == 0 else 1
    view = real_game.merge(real_game.observed(gs, f), [prior], {}, [])
    assert view["free"] == {"Rampage": 1}
    for card in hand:
        card["cost"] = 1
    view = real_game.merge(real_game.observed(gs, f), [prior], {}, [])
    assert view["free"] == {}
    view["player"]["energy"] = 0
    built = sts.Combat.from_view(view, seed=1, group="hallway")
    assert all(a.kind != "play" for a in built.legal_actions())


def test_rampage_mark_follows_its_uuid():
    """Rampage's combat damage mark is learnt when the controller plays the
    copy and follows the copy's uuid through a shuffle (live run 2026-11-14,
    floor 14: the mark was lost and Rampage was predicted to hit for 8, not
    13); a play of the marked copy picks that copy in the game's hand."""
    c = next(x for x in (fight("jaw_worm", ["Rampage"] * 2 + ["Defend"] * 8, s) for s in range(3, 40))
             if x.piles()["hand"].get("Rampage") == 1)
    a = [x for x in c.legal_actions() if x.kind == "play" and x.card == "Rampage"][0]
    before = c.piles()
    e = c.with_seed(1)
    e.step(a)
    mark = real_game.new_mark(before, e.piles(), "Rampage")
    assert mark == "Rampage{damage=13/combat}"
    assert real_game.new_mark(before, e.piles(), "Defend") is None
    # The marked copy is now in the draw pile, the other in the hand.
    marks = {"r1": mark}
    gs = write_out(c)["game_state"]
    cs = gs["combat_state"]
    cs["hand"] = [dict(game_card("Rampage"), uuid="r2"), dict(game_card("Defend"), uuid="d1")]
    cs["draw_pile"] = [dict(game_card("Rampage"), uuid="r1")] + cs["draw_pile"]
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80, "marks": marks}
    obs = real_game.observed(gs, f)
    assert obs["hand"].get("Rampage") == 1 and obs["draw"].get(mark) == 1
    # Drawn again: the hand holds both; each play picks its own copy.
    cs["hand"].append(cs["draw_pile"].pop(0))
    play = type("A", (), {"kind": "play", "target": 0})
    for name, slot in ((mark, "3"), ("Rampage", "1")):
        p = play()
        p.card = name
        assert real_game.command_for(p, gs, None, None, marks).split()[1] == slot


def test_death_screen_in_combat_ends_the_run(tmp_path):
    """The game shows GAME_OVER while the room is still in combat (live run
    2026-11-14, floor 22): the controller records the run and proceeds."""
    b = real_game.Bridge.__new__(real_game.Bridge)
    b.dir, b.fight, b.out = str(tmp_path), None, io.StringIO()
    b.runs_left, b.card_done, b.errors = 0, None, 0
    b.run = {"seed": 1, "started": "x", "fights": []}
    b.files = {k: open(os.path.join(str(tmp_path), k + ".jsonl"), "a", encoding="utf-8") for k in ("states", "decisions", "fights", "runs")}
    msg = write_out(fight("jaw_worm", DECK, 3))
    b.fight = {"floor": 1, "group": "hallway", "monsters": [], "start_hp": 80, "handed_over": "test", "left_out": set(),
               "decisions": 0, "predicted": 0, "matched": 0, "mismatches": [], "think_s": []}
    gs = msg["game_state"]
    gs.update({"screen_type": "GAME_OVER", "current_hp": 0, "screen_state": {"victory": False, "score": 10}})
    msg["available_commands"] = ["potion", "proceed", "state"]
    b.handle(msg)
    assert b.out.getvalue().strip() == "proceed" and b.fight is None
    for f in b.files.values():
        f.close()
    runs = [json.loads(x) for x in open(os.path.join(str(tmp_path), "runs.jsonl"), encoding="utf-8")]
    fights = [json.loads(x) for x in open(os.path.join(str(tmp_path), "fights.jsonl"), encoding="utf-8")]
    assert len(runs) == 1 and runs[0]["floor"] == 1 and fights[0]["won"] is False


def test_cards_played_this_turn_is_the_engines():
    """Havoc's play counts as a card played this turn (live run 2026-11-14,
    The Guardian); the game doesn't show the count, so the view takes the
    engine's prediction, not the controller's own plays."""
    c = fight("jaw_worm", DECK, 3)
    prior = real_game.plain(c.view())
    prior["cards_played_this_turn"] = 2
    f = {"left_out": set(), "played_this_turn": 1, "start_hp": 80}
    view = real_game.merge(real_game.observed(write_out(c)["game_state"], f), [prior], {}, [])
    assert view["cards_played_this_turn"] == 2


def test_havoc_into_a_pick_uses_the_sample_that_reached_it(tmp_path):
    """Havoc plays a random top card; when it is Armaments the game opens a
    pick that the controller's first sample may not have reached (live run
    2026-11-14, run 2 floor 13: "the plan has no pick here"). The sample
    whose pick offers the game's cards answers it."""
    import bench
    c = fight("jaw_worm", ["Strike"] * 5 + ["Defend"] * 4 + ["gen:Havoc+", "gen:Armaments"], 3)
    v = real_game.plain(c.view())
    v["hand"], v["draw"], v["discard"] = {"gen:Havoc+": 1, "Strike": 1, "Defend": 1}, {"gen:Armaments": 1, "Strike": 1}, {}
    c = sts.Combat.from_view(v, seed=1, group="hallway")
    havoc = [a for a in c.legal_actions() if a.kind == "play" and a.card == "gen:Havoc+"][0]
    at_pick, past = None, None
    for k in range(40):
        e = c.with_seed(k)
        e.step(havoc)
        if any(a.kind == "choose" for a in e.legal_actions()):
            at_pick = at_pick or e
        else:
            past = past or e
    assert at_pick is not None and past is not None
    b = real_game.Bridge.__new__(real_game.Bridge)
    real_game.setup_paths()
    b.ev, b.two = bench.load_evaluator("heuristic"), {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 5000}
    b.dir, b.out = str(tmp_path), io.StringIO()
    b.files = {k: open(os.path.join(str(tmp_path), k + ".jsonl"), "a", encoding="utf-8") for k in ("states", "decisions", "fights", "runs")}
    b.fight = {"floor": 13, "engine": past, "samples": [past, at_pick], "queue": [], "seed": 1, "n": 1, "marks": {},
               "handed_over": None, "priors": [], "expected": None}
    gs = write_out(at_pick, pick=[])["game_state"]
    gs["screen_type"] = "HAND_SELECT"
    b.pick(gs, ["choose"])
    assert b.fight["handed_over"] is None and b.out.getvalue().startswith("choose ")
    for f in b.files.values():
        f.close()


def costed(gs, costs, base):
    """Adds the game's cost fields: `costs` per hand card in order, `base`
    {engine name: cost} for the master deck and the other piles."""
    cs = gs["combat_state"]
    for card, cost in zip(cs["hand"], costs):
        card["cost"] = cost
    for k in ("draw_pile", "discard_pile", "exhaust_pile"):
        for card in cs[k]:
            card["cost"] = base[real_game.card_of(card)]
    gs["deck"] = [dict(game_card(n), cost=c) for n, c in base.items()]
    return gs


def test_snecko_oil_costs_come_from_the_game():
    """Snecko Oil rolls each hand card's cost for the fight; the engine's own
    sample rolled others (live run 2026-11-14, run 4 floor 10: "Strike{cost=0/
    combat} not in the game's hand"). The costs the game shows name the copies,
    and a play picks the copy with the engine's cost."""
    c = fight("jaw_worm", ["Strike"] * 5 + ["Defend"] * 5, 3)
    hand = ["Strike", "Strike", "Strike", "Defend", "Defend"]
    gs = costed(write_out(c, hand_order=hand)["game_state"], [3, 2, 1, 0, 3], {"Strike": 1, "Defend": 1})
    prior = real_game.plain(c.view())
    prior["hand"] = {"Strike{cost=0/combat}": 1, "Strike": 2, "Defend{cost=3/combat}": 1, "Defend": 1}
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    view = real_game.merge(real_game.observed(gs, f), [prior], {}, [])
    assert view["hand"] == {"Strike{cost=3/combat}": 1, "Strike{cost=2/combat}": 1, "Strike": 1,
                            "Defend{cost=0/combat}": 1, "Defend{cost=3/combat}": 1}
    built = sts.Combat.from_view(view, seed=1, group="hallway")
    a = [x for x in built.legal_actions() if x.kind == "play" and x.card == "Strike{cost=2/combat}"][0]
    assert real_game.command_for(a, gs, view) == "play 2 0"


def test_cost_marks_left_to_the_engine():
    """A free-this-turn card shows cost 0 and stays a free mark; Corruption's
    skills are the engine's own. Blood for Blood carries the cost the game
    shows on each copy (the engine drops each copy as the game does)."""
    c = fight("jaw_worm", ["Strike"] * 5 + ["Defend"] * 5, 3)
    gs = costed(write_out(c, hand_order=["Strike", "Defend", "Defend"])["game_state"], [0, 0, 1], {"Strike": 1, "Defend": 1})
    prior = real_game.plain(c.view())
    prior["hand"], prior["free"] = {"Strike": 1, "Defend": 2}, {"Strike": 1}
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    view = real_game.merge(real_game.observed(gs, f), [prior], {}, [])
    assert view["hand"] == {"Strike": 1, "Defend{cost=0/combat}": 1, "Defend": 1} and view["free"] == {"Strike": 1}
    for card in gs["combat_state"]["hand"]:
        card["type"] = "SKILL" if card["id"] == game_id("cards", "Defend") else "ATTACK"
    gs["combat_state"]["player"]["powers"] = [{"id": game_id("powers", "Corruption"), "amount": 1}]
    names = real_game.namer(gs)
    assert [names(x) for x in gs["combat_state"]["hand"]] == ["Strike{cost=0/combat}", "Defend", "Defend"]
    bfb = dict(game_card("gen:Blood for Blood"), cost=2)
    gs["deck"].append(dict(game_card("gen:Blood for Blood"), cost=4))
    assert names(bfb) == "gen:Blood for Blood{cost=2/combat}"
    assert names(dict(bfb, cost=4)) == "gen:Blood for Blood"


def test_pick_of_one_card_the_engine_took_itself(tmp_path):
    """Armaments with two Defends in hand: the engine upgrades one without a
    pick (one option), but the game opens its pick (live run 2026-11-14,
    run 8 floor 12: "the plan has no pick here"). Any copy will do."""
    import bench
    c = fight("jaw_worm", ["Strike"] * 5 + ["Defend"] * 4 + ["gen:Armaments"], 3)
    v = real_game.plain(c.view())
    v["hand"], v["draw"], v["discard"] = {"gen:Armaments": 1, "Defend": 2}, {"Strike": 5}, {}
    c = sts.Combat.from_view(v, seed=1, group="hallway")
    arm = [a for a in c.legal_actions() if a.kind == "play" and a.card == "gen:Armaments"][0]
    e = c.with_seed(1)
    e.step(arm)
    assert not any(a.kind == "choose" for a in e.legal_actions())  # the engine took the one option
    b = real_game.Bridge.__new__(real_game.Bridge)
    real_game.setup_paths()
    b.ev, b.two = bench.load_evaluator("heuristic"), {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 5000}
    b.dir, b.out = str(tmp_path), io.StringIO()
    b.files = {k: open(os.path.join(str(tmp_path), k + ".jsonl"), "a", encoding="utf-8") for k in ("states", "decisions", "fights", "runs")}
    b.fight = {"floor": 12, "engine": e, "samples": [e], "queue": [], "seed": 1, "n": 1, "marks": {},
               "handed_over": None, "priors": [], "expected": None}
    gs = write_out(c, hand_order=["Defend", "Defend"])["game_state"]
    gs["screen_type"] = "HAND_SELECT"
    b.pick(gs, ["choose"])
    assert b.fight["handed_over"] is None and b.out.getvalue().strip() == "choose 0"
    for f in b.files.values():
        f.close()


def test_free_copy_played_keeps_its_name_in_the_discard():
    """A Strike made free by Liquid Memories and played shows cost 0 in the
    discard pile until its flight there lands (live run 2026-11-14, run 10
    floor 5: discard.Strike{cost=0/combat}). The controller remembers the
    copies it played free this turn and ignores their cost out of the hand."""
    c = fight("jaw_worm", ["Strike"] * 5 + ["Defend"] * 5, 3)
    gs = costed(write_out(c, hand_order=["Strike", "Defend"])["game_state"], [1, 1], {"Strike": 1, "Defend": 1})
    played = dict(game_card("Strike"), cost=0, uuid="s9")
    gs["combat_state"]["discard_pile"].append(played)
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    assert real_game.observed(gs, f)["discard"].get("Strike{cost=0/combat}") == 1  # without the memory
    f["turn_free"] = {"s9"}
    obs = real_game.observed(gs, f)
    assert "Strike{cost=0/combat}" not in obs["discard"] and obs["discard"]["Strike"] >= 1


def test_relic_counter_the_game_hides_is_the_engines():
    """Art of War's flag is a counter the game doesn't show (-1); the view
    keeps the engine's value instead of 0 (live run 2026-11-14, run 12,
    Lagavulin: player.relics[0].value)."""
    c = fight("jaw_worm", DECK, 3, relics=["gen:Art of War"])
    prior = real_game.plain(c.view())
    prior["player"]["relics"] = [["gen:Art of War", 1]]
    gs = write_out(c)["game_state"]
    for r in gs["relics"]:
        if r["id"] == game_id("relics", "gen:Art of War"):
            r["counter"] = -1
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    view = real_game.merge(real_game.observed(gs, f), [prior], {}, [])
    assert view["player"]["relics"] == [["gen:Art of War", 1]]
    assert real_game.merge(real_game.observed(gs, f), [], {}, [])["player"]["relics"] == [["gen:Art of War", 0]]
    sts.Combat.from_view(view, seed=1, group="hallway")


def test_card_made_free_by_a_potion_is_free():
    """A Skill Potion's card (not in the master deck) shows cost 0 this turn;
    the engine's own sample made another card (live run 2026-11-14, run 13,
    The Guardian: Seeing Red played for 0, the engine said 1). It gets the
    engine's free-this-turn mark."""
    c = fight("jaw_worm", ["Strike"] * 5 + ["Defend"] * 5, 3)
    gs = costed(write_out(c, hand_order=["Strike", "Defend"])["game_state"], [1, 1], {"Strike": 1, "Defend": 1})
    gs["combat_state"]["hand"].append(dict(game_card("gen:Seeing Red"), cost=0))
    prior = real_game.plain(c.view())
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    view = real_game.merge(real_game.observed(gs, f), [prior], {}, [])
    assert view["hand"].get("gen:Seeing Red") == 1 and view["free"] == {"gen:Seeing Red": 1}
    view["player"]["energy"] = 0
    built = sts.Combat.from_view(view, seed=1, group="hallway")
    assert any(a.kind == "play" and a.card == "gen:Seeing Red" for a in built.legal_actions())


def test_power_without_an_amount():
    """The game shows a power without an amount as -1 (Barricade from a Power
    Potion, live run 2026-11-14, run 14); the engine holds it as 1. A real -1
    (Strength after Disarm) stays."""
    left = set()
    got = real_game.powers_of([{"id": game_id("powers", "Barricade"), "amount": -1},
                               {"id": game_id("powers", "Strength"), "amount": -1}], left, "player")
    assert got == {"Barricade": 1, "Strength": -1} and not left


def test_negative_powers_cover_the_packs():
    """Every power a content pack applies with a negative amount (Disarm's
    Strength -2) is in NEGATIVE_POWERS: for any other power the game's -1
    means "no amount" (real_game.game_number)."""
    negative = set()

    def walk(x):
        if isinstance(x, dict):
            a = x.get("Apply")
            if isinstance(a, dict) and isinstance(a.get("amount"), int) and a["amount"] < 0:
                negative.add(a["power"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for name in real_game.ACT1_PACKS:
        with open(os.path.join(real_game.ROOT, "content", "packs", name + ".json"), encoding="utf-8") as f:
            walk(json.load(f))
    assert "Strength" in negative  # the walk finds Disarm
    assert negative <= real_game.NEGATIVE_POWERS, negative - real_game.NEGATIVE_POWERS


def test_pick_uses_the_sample_that_drew_the_games_cards(tmp_path):
    """Warcry+ draws two cards, then puts one back. A sample that drew two
    Defends offers only cards the game offers too (live run 2026-11-14, run
    15 floor 14: its plan put a Defend back where the engine meant
    Armaments); the controller takes the sample whose piles are the game's."""
    import bench
    c = fight("jaw_worm", ["Strike"] * 5 + ["Defend"] * 4 + ["gen:Warcry+", "gen:Armaments"], 3)
    v = real_game.plain(c.view())
    v["hand"], v["draw"], v["discard"] = {"gen:Warcry+": 1, "Bash+": 1}, {"gen:Armaments": 1, "Defend": 2}, {}
    c = sts.Combat.from_view(v, seed=1, group="hallway")
    war = [a for a in c.legal_actions() if a.kind == "play" and a.card == "gen:Warcry+"][0]
    two_defends, mixed = None, None
    for k in range(60):
        e = c.with_seed(k)
        e.step(war)
        hand = e.piles()["hand"]
        if hand.get("Defend") == 2:
            two_defends = two_defends or e
        elif hand.get("Defend") == 1 and hand.get("gen:Armaments") == 1:
            mixed = mixed or e
    assert two_defends is not None and mixed is not None
    b = real_game.Bridge.__new__(real_game.Bridge)
    real_game.setup_paths()
    b.ev, b.two = bench.load_evaluator("heuristic"), {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 5000}
    b.dir, b.out = str(tmp_path), io.StringIO()
    b.files = {k: open(os.path.join(str(tmp_path), k + ".jsonl"), "a", encoding="utf-8") for k in ("states", "decisions", "fights", "runs")}
    b.fight = {"floor": 14, "engine": two_defends, "samples": [two_defends, mixed], "queue": [], "seed": 1, "n": 1,
               "marks": {}, "handed_over": None, "priors": [], "expected": None}
    gs = write_out(mixed, pick=[])["game_state"]
    gs["screen_type"] = "HAND_SELECT"
    offered = real_game.pick_offer(gs)
    assert real_game.offers(two_defends, offered) and real_game.offers(mixed, offered)
    assert real_game.pick_sample(two_defends, [two_defends, mixed], gs, offered) is mixed
    b.pick(gs, ["choose"])
    assert b.fight["handed_over"] is None
    j = int(b.out.getvalue().split()[1])
    assert real_game.card_of(gs["combat_state"]["hand"][j]) in ("gen:Armaments", "Defend", "Bash+")
    for f in b.files.values():
        f.close()


def test_blood_for_blood_cost_from_the_game():
    """Sharp Hide's thorns hit while Blood for Blood+ was in play, so that
    copy's cost didn't drop (live run 2026-11-14, run 16, The Guardian: the
    engine counted 2 HP losses, the copy showed one; its planned play was
    refused). Each copy carries the cost the game shows; the count only
    sets the cost of copies made in the fight."""
    deck = ["Strike"] * 5 + ["Defend"] * 4 + ["gen:Blood for Blood+"]
    c = fight("jaw_worm", deck, 3)
    v = real_game.plain(c.view())
    v["hand"], v["draw"], v["discard"] = {"gen:Blood for Blood+": 1, "Defend": 1}, {"Strike": 5, "Defend": 3}, {}
    c = sts.Combat.from_view(v, seed=1, group="hallway")
    prior = real_game.plain(c.view())
    prior["times_lost_hp"] = 2
    gs = costed(write_out(c, hand_order=["gen:Blood for Blood+", "Defend"])["game_state"], [2, 1], {"Strike": 1, "Defend": 1})
    gs["deck"].append(dict(game_card("gen:Blood for Blood+"), cost=3))
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    view = real_game.merge(real_game.observed(gs, f), [prior], {}, [])
    assert view["times_lost_hp"] == 2 and "gen:Blood for Blood+{cost=2/combat}" in view["hand"]
    view["player"]["energy"] = 1
    built = sts.Combat.from_view(view, seed=1, group="hallway")
    assert not any(a.kind == "play" and a.card.startswith("gen:Blood for Blood+") for a in built.legal_actions())
    view["player"]["energy"] = 2
    built = sts.Combat.from_view(view, seed=1, group="hallway")
    assert any(a.kind == "play" and a.card == "gen:Blood for Blood+{cost=2/combat}" for a in built.legal_actions())


def test_fresh_priors_keep_relic_powers_the_game_hides():
    """Tungsten Rod is a power in the engine that the game doesn't show
    (live run 2026-11-14, run 23 floor 12: Hemokinesis took 1 HP in the
    game, the engine predicted 2): the turn-1 priors keep it from the fresh
    fight's start, so every later view does."""
    c = fight("jaw_worm", DECK, 3, relics=["gen:Tungsten Rod"])
    assert real_game.plain(c.view())["player"]["powers"].get("TungstenRod") == 1
    gs = write_out(c)["game_state"]
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80, "seed": 5, "group": "hallway"}
    assert "TungstenRod" not in real_game.observed(gs, f)["player"]["powers"]
    priors = real_game.Bridge.fresh_priors(None, gs, f)
    assert all(p["player"]["powers"].get("TungstenRod") == 1 for p in priors)


def test_power_shown_as_a_flag_keeps_the_engines_count():
    """The game shows No Draw as a flag (-1) however many Battle Trances
    were played; the engine counts them (live run 2026-11-14, run 23: a miss
    on player.powers.NoDraw). The view keeps the engine's count."""
    c = fight("jaw_worm", DECK, 3)
    prior = real_game.plain(c.view())
    prior["player"]["powers"] = {"NoDraw": 2}
    gs = write_out(c)["game_state"]
    gs["combat_state"]["player"]["powers"] = [{"id": game_id("powers", "NoDraw"), "amount": -1}]
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    assert real_game.merge(real_game.observed(gs, f), [prior], {}, [])["player"]["powers"] == {"NoDraw": 2}
    prior["player"]["powers"] = {}
    assert real_game.merge(real_game.observed(gs, f), [prior], {}, [])["player"]["powers"] == {"NoDraw": 1}


def test_view_carries_the_games_ascension():
    """At A20 the view names the level (from_view then plays the monsters'
    A20 numbers); at A0 it has no key, as the engine's own views."""
    c = fight("jaw_worm", DECK, 3)
    gs = write_out(c)["game_state"]
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    assert "ascension" not in real_game.merge(real_game.observed(gs, f), [real_game.plain(c.view())], {}, [])
    gs["ascension_level"] = 20
    view = real_game.merge(real_game.observed(gs, f), [real_game.plain(c.view())], {}, [])
    assert view["ascension"] == 20 and sts.Combat.from_view(view, seed=1, group="hallway").view()["ascension"] == 20


def test_splitter_killed_outright_stays_dead():
    """A Large slime killed outright by an attack on all doesn't split (live
    run 2026-11-14, run 27, Slime Boss): the game's list doesn't grow, and
    the view keeps it as a dead monster, as the engine does; one that split
    (the list grew since it lived) is left out."""
    c = fight("Slime Boss", DECK, 3)
    gs = write_out(c)["game_state"]
    cs = gs["combat_state"]
    cs["monsters"][0].update({"current_hp": 0, "is_gone": True})
    for gid, hp in (("SpikeSlime_L", 31), ("AcidSlime_L", 0)):
        cs["monsters"].append({"id": gid, "current_hp": hp, "max_hp": 70, "block": 0, "powers": [],
                               "is_gone": hp == 0, "move_id": 1, "move_base_damage": -1})
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80, "alive_len": {0: 1, 1: 3, 2: 3}}
    obs = real_game.observed(gs, f)
    assert [(m["name"], m["hp"]) for m in obs["monsters"]] == [("Spike Slime (L)", 31), ("Acid Slime (L)", 0)]
    assert [m["game_index"] for m in obs["monsters"]] == [1, 2]


def test_deck_card_upgraded_in_the_fight_is_not_made_free():
    """Armaments made Anger+ in the fight; Anger costs 0 anyway and is in the
    deck, so it gets no free mark (live run 2026-11-14, run 28: free.Anger+)."""
    c = fight("jaw_worm", ["Strike"] * 5 + ["Defend"] * 4 + ["Anger"], 3)
    gs = costed(write_out(c, hand_order=["Strike", "Defend"])["game_state"], [1, 1], {"Strike": 1, "Defend": 1, "Anger": 0})
    gs["combat_state"]["hand"].append(dict(game_card("Anger+"), cost=0))
    f = {"left_out": set(), "played_this_turn": 0, "start_hp": 80}
    view = real_game.merge(real_game.observed(gs, f), [real_game.plain(c.view())], {}, [])
    assert view["hand"].get("Anger+") == 1 and view["free"] == {}


def test_potion_right_after_a_play_waits_first(tmp_path):
    """A card just played is still flying to the discard pile, and its landing
    resets its cost, so Liquid Memories on it would be wasted (live runs 1 and
    38): the controller sends "wait 30" first, then the potion."""
    c = fight("jaw_worm", DECK, 3, potions=["gen:Fire Potion"])
    view = real_game.plain(c.view())
    gs = write_out(c)["game_state"]
    potion = [a for a in c.legal_actions() if a.kind == "potion"][0]
    b = real_game.Bridge.__new__(real_game.Bridge)
    b.dir, b.out = str(tmp_path), io.StringIO()
    b.fight = {"queue": [potion], "just_played": True, "slots": None, "marks": {}, "n": 0, "played_this_turn": 1,
               "seed": 1, "priors": [], "expected": None, "engine": None}
    b.act(c, gs, view)
    assert b.out.getvalue().splitlines() == ["wait 30"] and b.fight["queue"] == [potion] and b.fight["waited"]
    b.act(c, gs, view)
    assert b.out.getvalue().splitlines()[-1].startswith("potion use") and not b.fight["queue"]


def test_guard_takes_the_win_the_search_passed():
    """The search passed immediate wins when the net's score for carrying on
    beat them: run 56 floor 14 left a Blue Slaver at 6 HP (Rampage on turn
    9, Twin Strike on turn 10 would kill it), run 52 floor 5 a gremlin
    (Perfected Strike on turn 12). The guard (FIGHT_GUARD 1) plays the
    winning option; when the search's own pick wins, it stands."""
    import action_text
    recs = json.load(open(os.path.join(os.path.dirname(__file__), "data", "real_game_guard.json"), encoding="utf-8"))
    kills = {(56, 9): 2, (56, 10): 2, (52, 12): 1}
    for r in recs:
        c = sts.Combat.from_view(r["view"], seed=1, group=r["group"])
        options = [([action_text.decode_in(c, t) for t in texts], v) for texts, v in zip(r["options"], r["two"])]
        d = {"r1": {"options": options}, "v1": r["one"], "v2": r["two"], "pick": r["pick"]}
        want = kills[(r["run"], r["turn"])]
        assert real_game.winning_options(c, options, 1) == [want], (r["run"], r["turn"])
        assert r["pick"] != want and real_game.guard_pick(c, d, 1) == want
        assert real_game.guard_pick(c, dict(d, pick=want), 1) is None
