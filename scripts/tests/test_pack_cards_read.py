"""Tests for the pack cards zero-shot read (docs/specs/act1-cards-zero-shot.md):
the fights, the heuristic's play counts, the paired table, and the turn-start
leaf leaving decks without a turn-start power unchanged. Run with
`python scripts/tests/test_pack_cards_read.py` or pytest. About 10 s."""

import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "analysis"))
os.chdir(ROOT)
import pack_cards_read as pcr  # noqa: E402

DECK = ["Defend", "Strike", "Strike", "Defend", "Bash"]


def fake_held():
    out = []
    for cell, group in ((0, "hallway"), (1, "elite"), (2, "boss")):
        for k in range(4):
            out.append({"cell": cell, "group": group, "deck": DECK, "seed": 10 * cell + k, "encounter": "x",
                        "hp": 1, "character": "ironclad"})
    return out


def test_fights():
    fs = pcr.fights(fake_held(), ["A", "B"], seeds=2, copies=3)
    assert {f["cell"] for f in fs} == {1, 2}
    assert len(fs) == 2 * 2 * 3
    assert [f["seed"] for f in fs if f["set"] == "A"] == [10, 11, 20, 21]
    a = next(f for f in fs if f["set"] == "A")
    assert a["deck"] == ["gen:A", "gen:A", "gen:A", "Defend", "Bash"]  # Strikes first, then Defends
    assert next(f for f in fs if f["set"] == pcr.WITHOUT)["deck"] == DECK


class St:
    def __init__(self, hand):
        self.hand = hand

    def __str__(self):
        return f"Turn 1  HP 1/80\nHand: {self.hand}\nDraw 1"


class Act:
    def __init__(self, text):
        self.text, self.is_end_turn = text, text == "Action(EndTurn)"

    def __str__(self):
        return self.text


def test_play_stats():
    states = [St("Defend, gen:Fiend Fire x2"), St("Defend, gen:Fiend Fire"), St("Defend"),  # turn 1: played
              St("Strike, gen:Fiend Fire+"), St("Strike"),  # turn 2: in hand, not played
              St("Strike"), St("gen:Fiend Fire")]  # turn 3: drawn mid-turn, fight ends
    actions = [Act("Action(gen:Fiend Fire -> slot 0)"), Act("Action(Defend)"), Act("Action(EndTurn)"),
               Act("Action(Strike -> slot 0)"), Act("Action(EndTurn)"), Act("Action(Strike -> slot 0)"),
               Act("Action(gen:Fiend Fire+ -> slot 0)")]
    assert pcr.play_stats(states, actions, "Fiend Fire") == (3, 2)
    assert pcr.play_stats(states, actions, "Fiend") == (0, 0)  # a name's prefix is another card


def test_table(tmp_path=None):
    import tempfile
    d = tmp_path or tempfile.mkdtemp()
    keys = [[c, s, k] for c in (1, 2) for s in (pcr.WITHOUT, "A") for k in (0, 1)]
    heur = [0, 0, 0, 0, 1, 1, 0, 0]
    plain = [1, 0, 0, 0, 1, 1, 1, 1]  # cell 1: A 0 - without 0.5 -> -0.5; cell 2: 1 - 0 -> +1
    tsl = [None, None, 1, 1, None, None, None, None]  # cell 1 A: +1 - 0.5 -> +0.5
    base = {"content_hash": "h", "seeds": 2, "keys": keys, "groups": ["elite"] * 4 + ["boss"] * 4}
    files = {"heuristic": {**base, "won": heur, "hp_end": heur, "in_hand": [None, None, 2, 2] * 2,
                           "played": [None, None, 1, 0] * 2},
             pcr.player_name(pcr.NET): {**base, "won": plain, "hp_end": plain},
             pcr.player_name(pcr.NET + "@tsl1"): {**base, "won": tsl, "hp_end": tsl}}
    for n, r in files.items():
        with open(os.path.join(d, n + ".json"), "w", encoding="utf-8") as f:
            json.dump(r, f)
    import argparse
    pcr.table(argparse.Namespace(out_dir=d, net=pcr.NET))
    row = json.load(open(os.path.join(d, "table.json"), encoding="utf-8"))["rows"]["A"]
    assert row["heur_play_rate"] == 0.25
    p = row["plain_won"]["all"]
    assert p["cells"] == 2 and p["d"] == 0.25 and np.isclose(p["se"], np.std([-0.5, 1], ddof=1) / np.sqrt(2))
    assert row["tsl1_won"]["all"]["d"] == 0.75  # (0.5 + 1) / 2
    assert row["plain_won"]["elite"]["d"] == -0.5 and row["plain_won"]["boss"]["d"] == 1.0


def test_tsl_same_on_plain_decks():
    import pytest
    if not os.path.exists(pcr.NET.split("@")[0]):
        pytest.skip("runs/ lives in the main checkout")
    import bench
    import selfplay
    selfplay.load_content(pcr.PACK)
    held = json.load(open(pcr.TIGHT2, encoding="utf-8"))["halves"]["held_out"]
    fs = [f for f in pcr.fights(held, ["Double Tap"], seeds=1) if f["set"] != pcr.WITHOUT
          and not pcr.turn_start(f["deck"])][:8:]
    assert len(fs) == 8
    one = [(r["won"], r["hp_end"]) for r in
           bench.run_specs(fs, ev=bench.load_evaluator(pcr.NET), search={"limit": bench.LIMIT, "threads": 2})]
    two = [(r["won"], r["hp_end"]) for r in
           bench.run_specs(fs, ev=bench.load_evaluator(pcr.NET + "@tsl1"), search={"limit": bench.LIMIT, "threads": 2})]
    assert one == two


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "ok")
