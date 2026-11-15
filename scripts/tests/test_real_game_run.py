"""The real-game bridge's run layer (scripts/real_game_run.py and the
controller's outside-fight handling): one command per screen, in
CommunicationMod's state format."""

import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import real_game  # noqa: E402
import real_game_run as R  # noqa: E402


@pytest.fixture(autouse=True)
def own_run_mark(tmp_path, monkeypatch):
    """No test touches the live run mark (results/real-game/ironclad-run-started):
    end_run removes it, and without it the controller won't replace its own save."""
    mark = str(tmp_path / "ironclad-run-started")
    monkeypatch.setattr(real_game, "run_mark", lambda: mark)
    # nor the game's real Ironclad save
    save = str(tmp_path / "saves" / "IRONCLAD.autosave")
    monkeypatch.setattr(real_game, "ironclad_save", lambda: save)
    # nor the live loop's stop file
    stop = str(tmp_path / "stop-loop")
    monkeypatch.setattr(real_game, "stop_loop_file", lambda: stop)


def test_neow_prefers_max_hp_and_avoids_drawbacks():
    gs = {"screen_state": {"options": [
        {"text": "[ Lose 8 Max HP Obtain a rare card ]", "label": "lose max hp", "choice_index": 0},
        {"text": "[ Max HP +8 ]", "label": "max hp", "choice_index": 1},
        {"text": "[ Obtain 100 Gold ]", "label": "gold", "choice_index": 2},
        {"text": "[ Lose your starting Relic Obtain a random boss Relic ]", "label": "boss relic", "choice_index": 3}]}}
    assert R.event_command(gs) == "choose 1"


def test_event_with_only_bad_options_still_chooses():
    gs = {"screen_state": {"options": [{"text": "Fight", "label": "fight", "choice_index": 0},
                                       {"text": "Lose 5 HP", "label": "lose", "choice_index": 1, "disabled": False}]}}
    assert R.event_command(gs) in ("choose 0", "choose 1")
    assert R.event_command({"screen_state": {"options": [{"text": "x", "disabled": True}]}}) is None


def test_map_avoids_elites_and_takes_the_boss():
    gs = {"screen_state": {"next_nodes": [{"x": 0, "y": 5, "symbol": "E"}, {"x": 2, "y": 5, "symbol": "R"},
                                          {"x": 4, "y": 5, "symbol": "M"}]}}
    assert R.map_command(gs, ["x=0", "x=2", "x=4"]) == "choose 2"
    assert R.map_command({"screen_state": {"next_nodes": [{"symbol": "E"}]}}, ["x=3"]) == "choose 0"
    assert R.map_command({}, ["boss"]) == "choose 0"


def test_rewards_take_gold_card_once_then_proceed():
    rewards = [{"reward_type": "CARD"}, {"reward_type": "GOLD", "gold": 12}, {"reward_type": "POTION"}]
    full = [{"id": "Fire Potion"}] * 3
    gs = {"screen_state": {"rewards": rewards}, "potions": full}
    assert R.reward_command(gs, card_done=False) == "choose 0"
    assert R.reward_command(gs, card_done=True) == "choose 1"
    gs2 = {"screen_state": {"rewards": [{"reward_type": "CARD"}, {"reward_type": "POTION"}]}, "potions": full}
    assert R.reward_command(gs2, card_done=True) == "proceed"
    gs2["potions"] = [{"id": "Potion Slot"}]
    assert R.reward_command(gs2, card_done=True) == "choose 1"


def test_rest_by_hp():
    assert R.rest_command({"current_hp": 30, "max_hp": 80, "floor": 8}, ["rest", "smith"]) == "choose 0"
    assert R.rest_command({"current_hp": 70, "max_hp": 80, "floor": 8}, ["rest", "smith"]) == "choose 1"
    assert R.rest_command({"current_hp": 55, "max_hp": 80, "floor": 15}, ["rest", "smith"]) == "choose 0"
    assert R.rest_command({"current_hp": 80, "max_hp": 80, "floor": 8}, []) == "proceed"


def test_grid_upgrade_bash_removal_strike():
    cards = [{"name": "Strike"}, {"name": "Defend"}, {"name": "Bash"}, {"name": "Pommel Strike"}]
    up = {"screen_state": {"cards": cards, "for_upgrade": True}}
    assert R.grid_command(up, ["strike", "defend", "bash", "pommel strike"]) == "choose 2"
    rm = {"screen_state": {"cards": cards, "for_purge": True}}
    assert R.grid_command(rm, ["strike", "defend", "bash", "pommel strike"]) == "choose 0"
    assert R.grid_command({"screen_state": {"confirm_up": True}}, []) == "confirm"


def test_fallback_plays_first_playable_on_a_living_monster():
    gs = {"screen_type": "NONE", "combat_state": {
        "monsters": [{"current_hp": 0, "is_gone": True}, {"current_hp": 20, "is_gone": False}],
        "hand": [{"is_playable": False}, {"is_playable": True, "has_target": True}]}}
    assert R.fallback_command(gs, ["play", "end"], []) == "play 2 1"
    gs["combat_state"]["hand"] = [{"is_playable": False}]
    assert R.fallback_command(gs, ["play", "end"], []) == "end"
    gs["combat_state"]["hand"] = [{"is_playable": True, "has_target": False}] * 10
    assert R.fallback_command(gs, ["play", "end"], []) == "play 1"


def bridge(tmp_path, runs=1):
    b = real_game.Bridge.__new__(real_game.Bridge)
    b.dir, b.fight, b.out = str(tmp_path), None, io.StringIO()
    b.files = {k: open(os.path.join(str(tmp_path), k + ".jsonl"), "a", encoding="utf-8")
               for k in ("states", "decisions", "fights", "runs")}
    b.runs_left, b.run, b.card_done, b.errors = runs, None, None, 0
    return b


def sent(b):
    return b.out.getvalue().split()


def test_main_menu_starts_one_run_then_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(real_game, "ROOT", str(tmp_path))  # the run mark goes under the test's folder
    monkeypatch.setattr(real_game.os.path, "exists", lambda p: False if p.endswith("IRONCLAD.autosave") else os.path.isdir(p))
    b = bridge(tmp_path, runs=1)
    menu = {"in_game": False, "ready_for_command": True, "available_commands": ["start", "state"]}
    b.handle(menu)
    assert b.out.getvalue() == "start ironclad 0\n"
    b.handle(menu)
    assert b.out.getvalue() == "start ironclad 0\n"  # no runs left: nothing more
    assert "done" in open(os.path.join(str(tmp_path), "status.txt")).read()


def test_never_starts_over_a_saved_run(tmp_path, monkeypatch):
    monkeypatch.setattr(real_game, "ROOT", str(tmp_path))
    monkeypatch.setattr(real_game.os.path, "exists", lambda p: p.endswith("IRONCLAD.autosave") or os.path.isdir(p))
    b = bridge(tmp_path, runs=3)
    b.handle({"in_game": False, "ready_for_command": True, "available_commands": ["start"]})
    assert b.out.getvalue() == ""


def test_refused_command_asks_for_the_state_and_tries_another_way(tmp_path):
    b = bridge(tmp_path)
    gs = {"screen_type": "SHOP_ROOM", "floor": 5, "choice_list": ["shop"], "room_phase": "COMPLETE"}
    msg = {"in_game": True, "ready_for_command": True, "available_commands": ["choose", "proceed", "leave"], "game_state": gs}
    b.handle(msg)
    assert sent(b)[-1] == "proceed"
    b.handle({"error": "Invalid command: proceed"})
    assert sent(b)[-1] == "state"
    b.handle(msg)
    assert sent(b)[-1] in ("proceed", "leave")


def test_game_over_records_the_run_and_proceeds(tmp_path):
    b = bridge(tmp_path)
    b.run = {"seed": 1, "fights": []}
    gs = {"screen_type": "GAME_OVER", "floor": 12, "act": 1, "screen_state": {"victory": False, "score": 99}, "room_phase": "COMPLETE"}
    b.handle({"in_game": True, "ready_for_command": True, "available_commands": ["proceed"], "game_state": gs})
    assert sent(b)[-1] == "proceed"
    for f in b.files.values():
        f.close()
    assert '"floor": 12' in open(os.path.join(str(tmp_path), "runs.jsonl")).read()


def test_fallback_after_hand_over(tmp_path):
    b = bridge(tmp_path)
    gs = {"screen_type": "NONE", "floor": 30, "room_phase": "COMBAT", "room_type": "MonsterRoom",
          "combat_state": {"turn": 1, "player": {"current_hp": 50, "max_hp": 80, "block": 0, "energy": 3, "powers": []},
                           "monsters": [{"id": "Byrd", "current_hp": 30, "max_hp": 30, "block": 0, "powers": [], "move_id": 1}],
                           "hand": [{"id": "Strike_R", "upgrades": 0, "is_playable": True, "has_target": True}],
                           "draw_pile": [], "discard_pile": [], "exhaust_pile": []}}
    b.handle({"in_game": True, "ready_for_command": True, "available_commands": ["play", "end"], "game_state": gs})
    assert b.fight["handed_over"] and "Byrd" in b.fight["handed_over"]
    assert sent(b)[-1] in ("1", "0") or b.out.getvalue().strip().endswith("play 1 0")


def test_multi_card_grid_skips_picked_cards():
    """Empty Cage / Astrolabe / Neow's remove 2: the grid keeps picked cards in
    its list and a second choose unpicks one; the next pick is another card,
    and confirm once none is left (review of 93cd5661)."""
    cards = [{"name": "Strike", "uuid": "s1"}, {"name": "Strike", "uuid": "s2"}, {"name": "Defend", "uuid": "d1"}]
    gs = {"screen_type": "GRID", "screen_state": {"cards": cards, "for_purge": True, "num_cards": 2, "selected_cards": []}}
    choices = ["strike", "strike", "defend"]
    assert R.grid_command(gs, choices) == "choose 0"
    gs["screen_state"]["selected_cards"] = [cards[0]]
    assert R.grid_command(gs, choices) == "choose 1"
    assert R.fallback_command(gs, ["choose", "confirm"], choices) == "choose 1"
    gs["screen_state"]["selected_cards"] = cards
    assert R.grid_command(gs, choices) == "confirm"
    assert R.fallback_command(gs, ["choose", "confirm"], choices) == "confirm"


def test_fallback_proceeds_on_the_death_screen():
    gs = {"screen_type": "GAME_OVER", "combat_state": {"hand": [], "monsters": []}}
    assert R.fallback_command(gs, ["potion", "proceed"], []) == "proceed"


def test_run_end_removes_the_mark_and_card_done(tmp_path, monkeypatch):
    """A later Ironclad save of the owner's must never count as ours: the mark
    goes when our run ends; the next run's card rewards start fresh."""
    monkeypatch.setattr(real_game, "ROOT", str(tmp_path))
    mark = real_game.run_mark()
    os.makedirs(os.path.dirname(mark), exist_ok=True)
    open(mark, "w").write("x\n")
    b = bridge(tmp_path)
    b.run, b.card_done = {"seed": 1, "fights": []}, 7
    gs = {"screen_type": "GAME_OVER", "floor": 7, "act": 1, "screen_state": {"victory": False, "score": 5}, "room_phase": "COMPLETE"}
    b.handle({"in_game": True, "ready_for_command": True, "available_commands": ["proceed"], "game_state": gs})
    assert not os.path.exists(mark) and b.card_done is None and sent(b)[-1] == "proceed"


def test_controller_error_still_answers(tmp_path, monkeypatch):
    """Any exception, not only HandOver, leaves the game waiting: outside a
    fight the error counts and the other ways out come next (the failing
    command isn't tried again); in a fight the fallback answers."""
    b = bridge(tmp_path)
    gs = {"screen_type": "CARD_REWARD", "floor": 5, "choice_list": ["anger"], "room_phase": "COMPLETE",
          "screen_state": {"cards": [{"id": "Anger", "upgrades": 0}]}}
    msg = {"in_game": True, "ready_for_command": True, "available_commands": ["choose", "skip", "proceed"], "game_state": gs}

    def boom(*a):
        raise RuntimeError("chooser failed")
    monkeypatch.setattr(b, "card_pick", boom, raising=False)
    try:
        b.handle(msg)
    except RuntimeError as e:
        b.answer_error(msg, e)
    assert sent(b)[-1] == "state" and b.errors == 1
    b.handle(msg)  # the same screen again: another way out, not the chooser
    assert sent(b)[-1] in ("skip", "proceed")
    f = bridge(tmp_path)
    f.fight = {"floor": 9, "handed_over": None}
    fight = {"screen_type": "NONE", "combat_state": {"monsters": [{"current_hp": 5}], "hand": [{"is_playable": False}]}}
    f.answer_error({"ready_for_command": True, "available_commands": ["end"], "game_state": fight}, ValueError("x"))
    assert f.fight["handed_over"].startswith("controller error") and sent(f)[-1] == "end"


def test_hold_file_waits_at_the_main_menu(tmp_path, monkeypatch):
    """results/real-game/hold keeps the controller at the main menu, so the
    game can be restarted between runs without starting a run to abandon."""
    monkeypatch.setattr(real_game, "ROOT", str(tmp_path))
    monkeypatch.setattr(real_game.os.path, "exists", lambda p: False if p.endswith("IRONCLAD.autosave") else os.path.isdir(p) or os.path.isfile(p))
    os.makedirs(os.path.join(str(tmp_path), "results", "real-game"))
    hold = os.path.join(str(tmp_path), "results", "real-game", "hold")
    open(hold, "w").close()
    b = bridge(tmp_path, runs=2)
    menu = {"in_game": False, "ready_for_command": True, "available_commands": ["start", "state"]}
    b.handle(menu)
    assert b.out.getvalue() == "" and b.runs_left == 2
    assert "held" in open(os.path.join(str(tmp_path), "status.txt")).read()
    os.remove(hold)
    b.handle(menu)
    assert b.out.getvalue() == "start ironclad 0\n"


def test_fight_record_has_hp_at_the_end_and_after(tmp_path):
    """hp_end is the HP in the fight's last state, before end-of-fight relics
    (Burning Blood's +6, which the game's first state after the fight already
    holds); hp_after includes them; a lost fight ends at 0."""
    b = bridge(tmp_path)
    b.run = {"seed": 1, "fights": []}
    gs = {"screen_type": "NONE", "floor": 16, "room_phase": "COMBAT", "room_type": "MonsterRoomBoss", "current_hp": 44,
          "combat_state": {"turn": 9, "player": {"current_hp": 44, "max_hp": 80, "block": 0, "energy": 3, "powers": []},
                           "monsters": [{"id": "Byrd", "current_hp": 6, "max_hp": 30, "block": 0, "powers": [], "move_id": 1}],
                           "hand": [], "draw_pile": [], "discard_pile": [], "exhaust_pile": []}}
    b.handle({"in_game": True, "ready_for_command": False, "game_state": gs})
    after = {"screen_type": "COMBAT_REWARD", "floor": 16, "room_phase": "COMPLETE", "current_hp": 50,
             "screen_state": {"rewards": []}}
    b.handle({"in_game": True, "ready_for_command": True, "available_commands": ["proceed"], "game_state": after})
    for f in b.files.values():
        f.close()
    row = [json.loads(x) for x in open(os.path.join(str(tmp_path), "fights.jsonl"))][-1]
    assert (row["hp_start"], row["hp_end"], row["hp_after"], row["won"]) == (44, 44, 50, True)
    assert b.run["fights"][-1]["hp_end"] == 44 and b.run["fights"][-1]["hp_after"] == 50


def test_boss_relic_skips_runic_dome():
    """Runic Dome hides every enemy move, so the translator can't rebuild any
    fight after it (live run 2026-11-14, run 6: three Cultists, all modelled,
    went to the fallback): the next relic offered is taken instead."""
    relics = [{"id": "Runic Dome"}, {"id": "Pandora's Box"}, {"id": "Empty Cage"}]
    gs = {"screen_state": {"relics": relics}}
    assert R.boss_relic_command(gs, ["runic dome", "pandora's box", "empty cage"]) == "choose 1"
    assert R.boss_relic_command({"screen_state": {"relics": relics[:1]}}, ["runic dome"]) == "choose 0"
    assert R.boss_relic_command(gs, []) == "proceed"


def test_death_screen_twice_records_the_run_once(tmp_path):
    """The game sent the death screen twice (live run 2026-11-14, run 16);
    the second must not start and record an empty run."""
    b = bridge(tmp_path)
    b.run = {"seed": 1, "fights": []}
    gs = {"screen_type": "GAME_OVER", "floor": 16, "act": 1, "seed": 1, "screen_state": {"victory": False, "score": 9},
          "room_phase": "COMPLETE"}
    msg = {"in_game": True, "ready_for_command": True, "available_commands": ["proceed"], "game_state": gs}
    b.handle(msg)
    b.handle(msg)
    for f in b.files.values():
        f.close()
    assert len(open(os.path.join(str(tmp_path), "runs.jsonl")).read().splitlines()) == 1


def test_ascension_starts_and_is_recorded(tmp_path, monkeypatch):
    """--ascension N starts each run at that level (CommunicationMod takes
    0-20 without unlocks) and the run's record carries the game's level."""
    monkeypatch.setattr(real_game, "ROOT", str(tmp_path))
    monkeypatch.setattr(real_game.os.path, "exists", lambda p: False if p.endswith("IRONCLAD.autosave") else os.path.isdir(p))
    b = bridge(tmp_path, runs=1)
    b.ascension = 20
    b.handle({"in_game": False, "ready_for_command": True, "available_commands": ["start", "state"]})
    assert b.out.getvalue() == "start ironclad 20\n" and "ascension 20" in open(os.path.join(str(tmp_path), "status.txt")).read()
    gs = {"screen_type": "GAME_OVER", "floor": 3, "act": 1, "seed": 5, "ascension_level": 20,
          "screen_state": {"victory": False, "score": 1}, "room_phase": "COMPLETE"}
    b.run = None
    b.handle({"in_game": True, "ready_for_command": True, "available_commands": ["proceed"],
              "game_state": dict(gs, screen_type="MAP", screen_state={"next_nodes": []})})
    b.handle({"in_game": True, "ready_for_command": True, "available_commands": ["proceed"], "game_state": gs})
    for f in b.files.values():
        f.close()
    run = json.loads(open(os.path.join(str(tmp_path), "runs.jsonl")).read().splitlines()[-1])
    assert run["ascension"] == 20


def test_ascension_option(monkeypatch):
    got = {}
    monkeypatch.setattr(real_game, "play", lambda player, **kw: got.update(kw, player=player))
    monkeypatch.setattr(real_game.os, "chdir", lambda p: None)
    real_game.main(["play", "model.pt@hpe0.01", "--runs", "3", "--ascension", "20"])
    assert got == {"player": "model.pt@hpe0.01", "runs": 3, "ascension": 20, "act1_only": False}
    real_game.main(["play", "m", "--act1-only", "--runs", "2"])
    assert got["act1_only"] is True and got["player"] == "m" and got["runs"] == 2
    with pytest.raises(SystemExit):
        real_game.main(["play", "m", "--ascension", "21"])


def test_act1_only_stops_the_run_when_act_2_starts(tmp_path, monkeypatch):
    """--act1-only: Act 2 isn't modelled, so the run stops when it starts,
    recorded as stopped (the save stays ours: the mark is kept), and the
    game is closed once no runs are left, for an outer loop to relaunch."""
    closed = []
    monkeypatch.setattr(real_game, "close_game", lambda: closed.append(1))
    monkeypatch.setattr(real_game, "ROOT", str(tmp_path))
    monkeypatch.setattr(real_game, "run_mark", lambda: os.path.join(str(tmp_path), "results", "real-game", "ironclad-run-started"))
    mark = real_game.run_mark()
    os.makedirs(os.path.dirname(mark), exist_ok=True)
    open(mark, "w").write("x")
    b = bridge(tmp_path, runs=0)
    b.act1_only = True
    b.run = {"seed": 3, "fights": []}
    gs = {"screen_type": "MAP", "floor": 17, "act": 2, "seed": 3, "ascension_level": 0, "room_phase": "COMPLETE",
          "screen_state": {"next_nodes": [{"symbol": "M"}]}, "choice_list": ["x=0"]}
    b.handle({"in_game": True, "ready_for_command": True, "available_commands": ["choose"], "game_state": gs})
    for f in b.files.values():
        f.close()
    run = json.loads(open(os.path.join(str(tmp_path), "runs.jsonl")).read().splitlines()[-1])
    assert run["stopped"].startswith("after the Act 1 boss") and run["act"] == 2 and b.run is None
    assert closed == [1] and not os.path.exists(mark) and b.out.getvalue() == ""
    b.handle({"in_game": False, "ready_for_command": True, "available_commands": ["start"]})
    assert closed == [1, 1]  # no runs left at the main menu: closed again


def test_launch_loop_relaunches_until_the_stop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(real_game, "ROOT", str(tmp_path))
    os.makedirs(os.path.join(str(tmp_path), "results", "real-game"))
    calls = []

    class Launcher:
        running = [True, False]  # the closing game is still listed once

        def list_processes(self):
            return []

        def running_game(self, procs):
            return [1] if self.running and self.running.pop(0) else []

        def main(self, argv):
            calls.append(argv)
            if len(calls) == 3:
                open(real_game.stop_loop_file(), "w").close()
    real_game.launch_loop(Launcher(), ["m.pt", "--runs", "1", "--act1-only"], wait=lambda s: None)
    assert calls == [["launch", "m.pt", "--runs", "1", "--act1-only"]] * 3


def write_save(path, seed):
    import base64
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = json.dumps({"seed": seed, "floor_num": 17}).encode()
    open(path, "wb").write(base64.b64encode(bytes(b ^ b"key"[i % 3] for i, b in enumerate(raw))))


def test_clear_own_save_deletes_only_this_runs_save():
    """After a stop at Act 2 the bot's own Ironclad save goes (its seed is
    this run's), with its .backUp; another save stays; the mark goes either
    way (a temp saves folder, never the game's)."""
    save, mark = real_game.ironclad_save(), real_game.run_mark()
    assert "saves" in save and os.path.dirname(os.path.dirname(save)) == os.path.dirname(mark)  # the temp one
    for seed, other, gone in ((-849, -849, True), (-849, 1234, False)):
        write_save(save, other)
        open(save + ".backUp", "w").close()
        open(mark, "w").close()
        assert real_game.save_seed(save) == other
        msg = real_game.clear_own_save(seed)
        assert os.path.exists(save) is not gone and os.path.exists(save + ".backUp") is not gone
        assert not os.path.exists(mark) and ("deleted" if gone else "kept") in msg


def test_map_takes_a_rest_site_below_half_hp():
    """Run 33 (A20) took a fight at 10 of 75 HP over a rest site and died;
    below half HP the map takes the rest site, above it the fight first."""
    nodes = [{"symbol": "R"}, {"symbol": "M"}]
    low = {"current_hp": 10, "max_hp": 75, "screen_state": {"next_nodes": nodes}}
    assert R.map_command(low, ["x=0", "x=1"]) == "choose 0"
    high = {"current_hp": 60, "max_hp": 75, "screen_state": {"next_nodes": nodes}}
    assert R.map_command(high, ["x=0", "x=1"]) == "choose 1"


def map_state(y0, rows, hp, nexts, mx=75):
    """A map state from rows "<x><symbol><children's x>..." starting at row
    y0, at `hp`, offered the nodes `nexts` [(x, y)]."""
    nodes = []
    for y, row in enumerate(rows, y0):
        for tok in row.split():
            nodes.append({"x": int(tok[0]), "y": y, "symbol": tok[1],
                          "children": [{"x": int(c), "y": y + 1} for c in tok[2:]]})
    at = {(n["x"], n["y"]): n for n in nodes}
    offered = [{"x": x, "y": y, "symbol": at[(x, y)]["symbol"]} for x, y in nexts]
    return {"current_hp": hp, "max_hp": mx, "map": nodes, "screen_state": {"next_nodes": offered}}


RUN37_MAP = ["0M0 1?12 3M3 6M6", "0E0 1R0 2E13 3E4 6R6", "0M0 1R0 3M3 4$4 6E6", "0E01 3?2 4R4 6M5",
             "0T0 1T1 2T3 4T4 5T6", "0M0 1?1 3?3 4R3 6M6", "0M0 1$0 3M34 6M6", "0M01 3R3 4?5 6M6",
             "0?0 1R1 3E4 5M4 6E5", "0?0 1?02 4M4 5M4", "0R 2R 4R"]
RUN49_MAP = ["0R1 1R1 2E3 3?3 4M4", "1M12 3?23 4M45", "1?1 2$23 3?4 4M5 5E5", "1?2 2M2 3R2 4M5 5$6",
             "2E23 5M4 6E56", "2R 3R 4R 5R 6R"]


def test_map_looks_ahead_to_the_next_rest_site():
    """Runs 37 and 49 (A20, rules 2) took a fight one node ahead into a path
    of fights and elites with no rest site, and died. The look-ahead takes
    the other branch: run 37 at 58 HP on floor 4 the event (a rest site or
    one elite next), run 49 at 67 HP on floor 9 the event (fights then an
    elite on the fight branch cost more than its HP)."""
    run37 = map_state(4, RUN37_MAP, 58, [(0, 4), (1, 4)])
    assert R.map_command(run37, ["x=0", "x=1"]) == "choose 1"
    run49 = map_state(9, RUN49_MAP, 67, [(3, 9), (4, 9)])
    assert R.map_command(run49, ["x=3", "x=4"]) == "choose 0"


def test_map_look_ahead_keeps_fights_when_healthy_and_cuts_cost_when_all_die():
    """Healthy, a fight before the rest site beats an event (a card pick);
    when every path dies at the pessimistic costs, the cheapest path wins
    (run 49 at 12 HP: the fight, not the elite); a rest site below half HP
    still comes first."""
    assert R.map_command(map_state(13, ["0M0 1?1", "0R 1R"], 75, [(1, 13), (0, 13)]), ["x=1", "x=0"]) == "choose 1"
    assert R.map_command(map_state(9, RUN49_MAP, 12, [(4, 11), (5, 11)]), ["x=4", "x=5"]) == "choose 0"
    assert R.map_command(map_state(9, RUN49_MAP, 30, [(2, 13), (5, 13)]), ["x=2", "x=5"]) == "choose 1"
    low = map_state(13, ["0M0 1R1", "0R 1R"], 30, [(0, 13), (1, 13)])
    assert R.map_command(low, ["x=0", "x=1"]) == "choose 1"
    assert R.segments({"x": 4, "y": 9, "symbol": "M", "children": [{"x": 4, "y": 10}]},
                      {(n["x"], n["y"]): n for n in map_state(9, RUN49_MAP, 1, [])["map"]}, {}) == {(3, 1), (2, 2)}


def options(*texts):
    return {"screen_state": {"options": [{"text": t, "label": t.split("]")[0].strip("[ ").lower(), "choice_index": i}
                                         for i, t in enumerate(texts)]}}


def test_event_leaves_the_golden_idol():
    """Run 52 (A20) took the Golden Idol: "golden" scored as gold and
    "[Take]" slipped past the bad word "take ", and the trap cost 8 max HP.
    Words now match whole and "trap" is bad, so it leaves; inside the trap
    it still takes the max HP loss (as before)."""
    assert R.event_command(options("[Take] Obtain Golden Idol. Trigger a trap.", "[Leave]")) == "choose 1"
    trap = options("[Outrun] Become Cursed - Injury.", "[Smash] Take 28 Damage.", "[Hide] Lose 8 Max HP.")
    assert R.event_command(trap) == "choose 2"


def test_event_words_match_whole_words():
    assert R.says("[hide] lose 8 max hp.", "lose") and R.says("become cursed - injury.", "curse")
    assert R.says("card2", "card") and R.says("upgrade 2 random cards.", "card")
    assert not R.says("obtain golden idol.", "gold") and not R.says("cleave", "leave")
    assert not R.says("close the door", "lose") and R.says("[take] obtain", "take")
    # Match and Keep: a face-down card, not a known one whose name holds "leave".
    assert R.event_command(options("Flame Barrier", "Cleave", "card2")) == "choose 2"


RUN55_MAP = ["0R0 1E01 3R3 6E5", "0M01 1R2 3M2 5?6", "0R1 1M12 2M2 6R6", "1T02 2T23 6T6", "0M0 2R123 3E4 6M6",
             "0$1 1?1 2E3 3M3 4?5 6?6", "1M1 3R2 5M4 6?6", "1M01 2M12 4M4 6?6", "0E0 1?01 2E3 4E4 6E6",
             "0R 1R 3R 4R 6R"]
RUN52_MAP = ["1M1 2R2 4M5 6E6", "1M12 2E3 5M4 6M6", "1E0 2$3 3?3 4E3 6R56", "0R0 3M234 5$5 6E6",
             "0M0 2M2 3E4 4M4 5M4 6M6", "0R 2R 4R 6R"]


def test_map_takes_an_elite_only_when_every_node_is_one():
    """Rules 3 and 4 counted an elite as two card picks and took four by
    choice at A20: run 55 took three Sentries over a rest site at 73 of 75
    HP and died; run 52 took Gremlin Nob over a fight at 52 HP (no path
    survived, the elite's was cheapest) and died. An elite is taken only when
    every next node is one."""
    assert R.map_command(map_state(5, RUN55_MAP, 73, [(0, 5), (1, 5)]), ["x=0", "x=1"]) == "choose 0"
    assert R.map_command(map_state(9, RUN52_MAP, 52, [(4, 9), (6, 9)], mx=74), ["x=4", "x=6"]) == "choose 0"
    assert R.map_command(map_state(9, RUN52_MAP, 52, [(6, 9)], mx=74), ["x=6"]) == "choose 0"
    assert R.path_key({(1, 0), (0, 1)}, 75) == (1, 1, -15)  # an elite's path picks no card


def test_main_menu_keeps_the_game_after_a_death_and_closes_it_on_stop_loop(tmp_path, monkeypatch):
    """After a death the game is back at the main menu: the next run starts
    there (no restart, which takes a while). Once stop-loop exists the
    controller starts nothing and closes the game, so the outer loop ends."""
    closed = []
    monkeypatch.setattr(real_game, "close_game", lambda: closed.append(1))
    monkeypatch.setattr(real_game, "ROOT", str(tmp_path))
    monkeypatch.setattr(real_game.os.path, "exists", lambda p: False if p.endswith("IRONCLAD.autosave") else os.path.isdir(p) or os.path.isfile(p))
    b = bridge(tmp_path, runs=3)
    b.act1_only = True
    menu = {"in_game": False, "ready_for_command": True, "available_commands": ["start", "state"]}
    b.handle(menu)
    b.handle(menu)  # back at the menu after the first run died
    assert b.out.getvalue() == "start ironclad 0\n" * 2 and closed == []
    open(real_game.stop_loop_file(), "w").close()
    b.handle(menu)
    assert b.out.getvalue() == "start ironclad 0\n" * 2 and closed == [1] and b.runs_left == 1
    assert "stop-loop" in open(os.path.join(str(tmp_path), "status.txt")).read()


def test_a_state_from_before_the_potion_gets_wait(tmp_path):
    """Run 70: after "potion use 0" the game answered with a state still
    showing Snecko Oil and the same hand, the controller planned again and
    sent the potion twice (refused, fallback). Such a state gets "wait 30",
    at most POTION_WAITS times, then "state"; a changed state is played."""
    b = bridge(tmp_path, runs=1)
    gs = {"potions": [{"id": "SneckoOil"}, {"id": "Potion Slot"}],
          "combat_state": {"hand": [{"name": "Defend", "uuid": "a"}], "player": {"energy": 0}}}
    b.fight = {"potion_sent": {"snap": real_game.potion_snapshot(gs), "waits": 0}}
    for _ in range(real_game.POTION_WAITS):
        assert b.potion_unresolved(gs)
    assert b.potion_unresolved(gs) and "potion_sent" not in b.fight
    assert b.out.getvalue() == "wait 30\n" * real_game.POTION_WAITS + "state\n"
    b.fight = {"potion_sent": {"snap": real_game.potion_snapshot(gs), "waits": 0}}
    after = dict(gs, potions=[{"id": "Potion Slot"}, {"id": "Potion Slot"}])
    assert not b.potion_unresolved(after) and "potion_sent" not in b.fight
