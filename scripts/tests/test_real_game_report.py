"""scripts/real_game_report.py: runs per game seed from states.jsonl, fights
split where the floor goes back down, the doc's hand-written parts kept."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import real_game_report  # noqa: E402


def state(t, seed, floor, screen="NONE", combat=False, hp=80, **extra):
    gs = {"seed": seed, "floor": floor, "act": 1, "act_boss": "The Guardian", "screen_type": screen,
          "current_hp": hp, "max_hp": 80, "deck": [{"id": "Strike_R", "upgrades": 0}], "relics": [{"id": "Burning Blood"}]}
    if combat:
        gs["combat_state"] = {"monsters": [{"id": "JawWorm"}], "player": {"current_hp": max(hp - 10, 0)}}
    gs.update(extra)
    return {"t": t, "msg": {"game_state": gs}}


def fight(floor, won=True, handed=None, matched=3, predicted=3):
    return {"floor": floor, "group": "boss" if floor == 16 else "hallway", "monsters": ["JawWorm"], "hp_start": 80,
            "hp_end": 70 if won else 0, "won": won, "handed_over": handed, "left_out": [], "decisions": 2,
            "predicted": predicted, "matched": matched, "mismatches": [] if matched == predicted else [{"turn": 2, "keys": ["monsters[0].hp"]}],
            "think_s": [0.5, 2.0]}


def write(folder, name, rows):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(r) + "\n" for r in rows))


def test_report(tmp_path):
    folder = tmp_path / "20261114-060000"
    folder.mkdir()
    write(folder, "states.jsonl", [
        state(1, 11, 1, combat=True), state(2, 11, 16, combat=True, hp=70),
        state(3, 11, 18, screen="GAME_OVER", combat=True, hp=0, screen_state={"victory": False, "score": 99}),
        state(4, 22, 1, combat=True), state(5, 22, 2)])
    write(folder, "fights.jsonl", [fight(1), fight(16, matched=2), fight(18, won=False, handed="monster Chosen not loaded"), fight(1)])
    runs = real_game_report.all_runs(str(tmp_path))
    assert [len(r["fights"]) for r in runs] == [3, 1]
    text = real_game_report.render(runs)
    assert "died on floor 18 to JawWorm (score 99)" in text and "not finished (floor 2)" in text
    assert "11 of 12 chance-free steps matched" in text and "monster not loaded (Act 2 and later): 1 fight(s), floors 18" in text
    assert "| Act 1 bosses beaten | 1 |" in text and "### Ascension 0" in text and "- Ascension 0, run rules 1. Reached floor 18" in text
    # Old records: hp_end was the HP after the fight; the fight's own end
    # comes from its last state in states.jsonl.
    assert "| 1 | A0 r1 | 16 | boss | JawWorm | 80 -> 60 (70 after) |" in text and "| 1 | A0 r1 | 18 | hallway | JawWorm | 80 -> 0 |" in text
    doc = tmp_path / "doc.md"
    doc.write_text("intro\n" + real_game_report.BEGIN + "\nOLD-TEXT\n" + real_game_report.END + "\nnotes\n", encoding="utf-8")
    real_game_report.write(text, str(doc))
    out = doc.read_text(encoding="utf-8")
    assert out.startswith("intro\n") and out.endswith("\nnotes\n") and "OLD-TEXT" not in out and "Run 2" in out


def test_levels_are_not_pooled(tmp_path):
    folder = tmp_path / "20261114-070000"
    folder.mkdir()
    write(folder, "states.jsonl", [state(1, 11, 2, combat=True), state(2, 22, 1, combat=True, ascension_level=20)])
    write(folder, "fights.jsonl", [fight(2), fight(1, won=False)])
    text = real_game_report.render(real_game_report.all_runs(str(tmp_path)))
    a0 = text[text.index("### Ascension 0"):text.index("### Ascension 20")]
    a20 = text[text.index("### Ascension 20"):text.index("## Runs")]
    assert "| Fights | 1 (1 won)" in a0 and "| Fights | 1 (0 won)" in a20


def test_run_stopped_when_act_2_started(tmp_path):
    folder = tmp_path / "20261114-080000"
    folder.mkdir()
    write(folder, "states.jsonl", [state(1, 11, 16, combat=True), state(2, 11, 17, screen="MAP", act=2)])
    write(folder, "fights.jsonl", [fight(16)])
    text = real_game_report.render(real_game_report.all_runs(str(tmp_path)))
    assert "stopped when Act 2 started" in text and "| Runs | 1 (1 finished, 1 of them stopped when Act 2 started) |" in text


def test_rules_versions_are_not_pooled(tmp_path):
    """A20 runs before 8d7d529a (rules 1) and after it (rules 2, recorded in
    runs.jsonl or read from the folder's start time) get separate tables."""
    early, late = tmp_path / "20261114-135000", tmp_path / "20261114-150000"
    for folder, seed in ((early, 11), (late, 22)):
        folder.mkdir()
        write(folder, "states.jsonl", [state(1, seed, 1, combat=True, ascension_level=20)])
        write(folder, "fights.jsonl", [fight(1)])
    write(late, "runs.jsonl", [{"seed": 22, "run_rules": 2, "commit": "abc1234"}])
    text = real_game_report.render(real_game_report.all_runs(str(tmp_path)))
    assert "### Ascension 20, run rules 1" in text and "### Ascension 20, run rules 2" in text
    assert "run rules 2, controller abc1234." in text and "| 2 | A20 r2 | 1 |" in text
