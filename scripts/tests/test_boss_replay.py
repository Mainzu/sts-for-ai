"""Tests for the boss replays (scripts/analysis/boss_replay.py,
docs/specs/boss-replay.md). Run with `python scripts/tests/test_boss_replay.py`
(plain asserts) or with pytest."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import boss_replay  # noqa: E402
import gauntlet  # noqa: E402

STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
HPS = [30, 40, 50, 60, 70, 80]


def floors(n, boss, hp, won, tooks=()):
    out = [{"encounter": "cultist", "hp_start": 80, "hp_end": 80, "won": True,
            "offer": ["A", "B", "C"], "took": tooks[k] if k < len(tooks) else None} for k in range(n - 1)]
    out.append({"encounter": boss, "hp_start": hp, "hp_end": hp if won else 0, "won": won})
    return out


ROWS = [
    {"i": 0, "half": "train", "cell": 1, "cleared": True, "floors": floors(11, "slime_boss", 55, True, ("Cleave", None, "Inflame"))},
    {"i": 1, "half": "held_out", "cell": 2, "cleared": False, "floors": floors(10, "lagavulin", 20, False)},
    {"i": 2, "half": "train", "cell": 3, "cleared": False, "floors": floors(11, "hexaghost", 35, False, (None, "Combust"))},
]
SEQS = {i: {"i": i, "character": "ironclad", "deck": ["Strike"] * 3} for i in range(3)}
SETTINGS = {"start": "starter", "rewards": "sim", "sim_boss": True}


def fake_play(specs):
    return [{"won": s["hp"] >= 50, "hp_start": s["hp"], "hp_end": s["hp"] if s["hp"] >= 50 else 0} for s in specs]


def test_deck_rebuild():
    decks, skipped = boss_replay.rebuild(ROWS, SETTINGS, SEQS)
    assert skipped == 1 and [d["i"] for d in decks] == [0, 2]
    assert decks[0]["deck"] == STARTER + ["Cleave", "Inflame"] and decks[0]["boss"] == "slime_boss"
    assert decks[0]["hp_obs"] == 55 and decks[0]["won_obs"] is True
    assert decks[1]["deck"] == STARTER + ["Combust"] and decks[1]["won_obs"] is False
    assert decks[0]["seed"] == gauntlet.SEED_BASE + 10
    cell, _ = boss_replay.rebuild(ROWS, {}, SEQS)
    assert cell[0]["deck"] == ["Strike"] * 3 + ["Cleave", "Inflame"]
    for k in boss_replay.REFUSE:
        try:
            boss_replay.rebuild(ROWS, {**SETTINGS, k: "x"}, SEQS)
            assert False, k
        except SystemExit:
            pass


def test_seeds_common():
    decks, _ = boss_replay.rebuild(ROWS, SETTINGS, SEQS)
    specs = boss_replay.specs_for(decks[1], HPS, 4)
    assert len(specs) == 24 and all(s["encounter"] == "hexaghost" and s["group"] == "boss" for s in specs)
    by_j = {}
    for n, s in enumerate(specs):
        by_j.setdefault(n % 4, set()).add(s["seed"])
    assert all(len(v) == 1 for v in by_j.values()) and len({next(iter(v)) for v in by_j.values()}) == 4
    assert next(iter(by_j[0])) == gauntlet.SEED_BASE + 2 * 100 + 10
    block = gauntlet.SEED_BASE + 2 * 100
    floor_seeds = {block + k for k in range(11)}
    for j in (1, 2, 3):
        s = next(iter(by_j[j]))
        assert block < s < block + 100 and s not in floor_seeds
    assert sorted({s["hp"] for s in specs}) == HPS


def test_read_curves():
    decks, _ = boss_replay.rebuild(ROWS, SETTINGS, SEQS)
    rows = [r for block in boss_replay.play_blocks(decks, HPS, 4, fake_play, block=1) for r in block]
    assert len(rows) == 2 and rows[0]["won"]["40"] == [0, 0, 0, 0] and rows[0]["won"]["50"] == [1, 1, 1, 1]
    cz = boss_replay.causal(rows, HPS)
    assert [cz[hp][0] for hp in HPS] == [0, 0, 1, 1, 1, 1]
    for r in rows:
        x, w = boss_replay.step(r, HPS)
        assert abs(x - 45) < 1e-9 and abs(w - 5) < 1e-9
    assert boss_replay.step({"won": {str(hp): [0] for hp in HPS}}, HPS) == (None, None)
    assert boss_replay.step({"won": {str(hp): [1] for hp in HPS}}, HPS) == (30.0, 0.0)
    obs = boss_replay.observational(ROWS)
    assert obs == {30: (0.0, 1), 50: (1.0, 1)}


def test_resume():
    decks, skipped = boss_replay.rebuild(ROWS, SETTINGS, SEQS)
    rows = [r for block in boss_replay.play_blocks(decks, HPS, 2, fake_play) for r in block]
    settings = {"file": "x.json", "player": "p", "hp": HPS, "seeds": 2}
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "r.json")
        assert boss_replay.load_done(out, settings) == {}
        boss_replay.write(out, settings, skipped, rows)
        done = boss_replay.load_done(out, settings)
        assert sorted(done) == [0, 2] and done[0] == rows[0]
        with open(out, encoding="utf-8") as f:
            assert json.load(f)["skipped"] == 1
        try:
            boss_replay.load_done(out, {**settings, "hp": [30, 50]})
            assert False
        except SystemExit:
            pass


def test_arrival_mode():
    """docs/specs/boss-replay-score.md: each deck replays at its own arrival
    HP on common seeds; rows hold won and hp_end per seed."""
    decks, _ = boss_replay.rebuild(ROWS, SETTINGS, SEQS)
    seen = []

    def play(specs):
        seen.extend(specs)
        return fake_play(specs)
    rows = [r for block in boss_replay.play_blocks(decks, "arrival", 3, play) for r in block]
    assert [s["hp"] for s in seen] == [55] * 3 + [35] * 3
    assert [s["seed"] for s in seen[:3]] == [boss_replay.seed_of(decks[0], j) for j in range(3)]
    assert rows[0]["won"] == {"arrival": [1, 1, 1]} and rows[0]["hp_end"] == [55, 55, 55]
    assert rows[1]["won"] == {"arrival": [0, 0, 0]} and rows[1]["hp_end"] == [0, 0, 0]
    sweep = [r for block in boss_replay.play_blocks(decks, HPS, 2, fake_play) for r in block]
    assert "hp_end" not in sweep[0]


def test_pair_scores():
    """pair: sequence score = mean replay result, 0 if it died before the boss."""
    import numpy as np
    ra = [{"i": 0, "won": {"arrival": [1, 0]}, "hp_end": [40, 0]},
          {"i": 2, "won": {"arrival": [0, 0]}, "hp_end": [0, 0]}]
    gb = [{**ROWS[0], "cleared": False, "floors": floors(11, "slime_boss", 55, False)},
          {**ROWS[1], "cleared": True, "floors": floors(11, "lagavulin", 60, True)}, ROWS[2]]
    rb = [{"i": 0, "won": {"arrival": [1, 1]}, "hp_end": [30, 50]},
          {"i": 1, "won": {"arrival": [1, 0]}, "hp_end": [20, 0]},
          {"i": 2, "won": {"arrival": [0, 1]}, "hp_end": [0, 10]}]
    got = boss_replay.pair_scores(ROWS, ra, gb, rb)
    for name, d in (("clears", [-1, 1, 0]), ("end_hp", [-55, 60, 0]), ("replay_win", [0.5, 0.5, 0.5]),
                    ("replay_hp", [20, 10, 5])):
        n, mean, sd = got[name]
        assert n == 3 and abs(mean - np.mean(d)) < 1e-9 and abs(sd - np.std(d, ddof=1)) < 1e-9, (name, got[name])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
