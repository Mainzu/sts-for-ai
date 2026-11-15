"""Tests for the depth probe (scripts/analysis/depth_probe.py,
docs/specs/depth-probe.md): fight selection, deck rebuild and the paired
read, on hand-made rows (no engine play)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import depth_probe  # noqa: E402
import gauntlet  # noqa: E402

STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
SETTINGS = {"start": "starter", "rewards": "sim", "sim_boss": True}


def floors(elite, boss=None, tooks=()):
    """11 floors (10 without `boss`): floor 8 is (hp_start, hp_end, won) `elite`."""
    out = [{"encounter": "cultist", "hp_start": 80, "hp_end": 80, "won": True, "took": tooks[k] if k < len(tooks) else None}
           for k in range(8)]
    hs, he, won = elite
    out.append({"encounter": "lagavulin", "hp_start": hs, "hp_end": he, "won": won, "took": "Late"})
    if boss is not None:
        out.append({"encounter": "jaw_worm", "hp_start": 70, "hp_end": 70, "won": True, "took": "Later"})
        out.append({"encounter": "hexaghost", "hp_start": boss, "hp_end": 0, "won": False})
    return out


ROWS = [
    {"i": 2, "floors": floors((60, 46, True), 69, ("Cleave", None, "Inflame"))},  # lost 14: no elite; boss 69: in
    {"i": 0, "floors": floors((50, 35, True), 49)},  # lost 15: elite; boss 49: out
    {"i": 1, "floors": floors((30, 0, False))},  # a loss counts as all HP: elite; no boss floor
    {"i": 3, "floors": floors((70, 40, True), 50)},  # elite; boss 50: in
]
SEQS = {i: {"i": i, "character": "ironclad", "deck": ["Strike"] * 3,
            "fights": [{"group": "boss" if k == 10 else "elite" if k in (5, 8) else "hallway"} for k in range(11)]}
        for i in range(4)}


def starter(_):
    return STARTER


def test_select_elite():
    got = depth_probe.select(ROWS, SETTINGS, SEQS, "elite", starter=starter)
    assert [(i, k) for i, k, _, _ in got] == [(0, 8), (1, 8), (3, 8)]
    i, k, spec, f = got[0]
    assert spec["deck"] == STARTER and spec["hp"] == 50 and spec["encounter"] == "lagavulin"
    assert spec["seed"] == gauntlet.SEED_BASE + 8 and spec["group"] == "elite"
    assert [x[0] for x in depth_probe.select(ROWS, SETTINGS, SEQS, "elite", limit=2, starter=starter)] == [0, 1]
    rest = depth_probe.select(ROWS, SETTINGS, SEQS, "elite-rest", starter=starter)
    assert [(i, k) for i, k, _, _ in rest] == [(2, 8)]
    every = depth_probe.select(ROWS, SETTINGS, SEQS, "elite-all", starter=starter)
    assert [i for i, _, _, _ in every] == [0, 1, 2, 3]
    assert every[2][2] == rest[0][2]


def test_select_boss_and_deck():
    got = depth_probe.select(ROWS, SETTINGS, SEQS, "boss", starter=starter)
    assert [i for i, _, _, _ in got] == [2, 3]
    spec = got[0][2]
    # tooks of earlier floors only: floor 8's and 9's tooks are in, the boss floor has none
    assert spec["deck"] == STARTER + ["Cleave", "Inflame", "Late", "Later"]
    assert spec["hp"] == 69 and spec["seed"] == gauntlet.SEED_BASE + 200 + 10 and spec["group"] == "boss"
    elite = depth_probe.select(ROWS, SETTINGS, SEQS, "elite", starter=starter)[2][2]
    assert "Late" not in elite["deck"]  # the elite's own took comes after the fight
    cell = depth_probe.select(ROWS, {}, SEQS, "boss")[0][2]
    assert cell["deck"] == ["Strike"] * 3 + ["Cleave", "Inflame", "Late", "Later"]


def test_refused_settings():
    for key in depth_probe.REFUSE:
        try:
            depth_probe.select(ROWS, {**SETTINGS, key: "x"}, SEQS, "elite", starter=starter)
            assert False, key
        except SystemExit:
            pass


def fight(i, hp_start, hp_end, won, obs=None, **kw):
    ho, wo = obs if obs else (hp_end, won)
    return {"i": i, "floor": 8, "hp_start": hp_start, "hp_end": hp_end, "won": won, "hp_end_obs": ho,
            "won_obs": wo, **kw}


def test_read_pairs():
    a = {"fights": [fight(0, 50, 30, True, decisions=10, cut=0), fight(1, 40, 0, False, decisions=10, cut=0),
                    fight(5, 60, 60, True)]}
    b = {"fights": [fight(0, 50, 35, True, (30, True), decisions=10, cut=5),
                    fight(1, 40, 10, True, (0, False), decisions=10, cut=0)]}
    r = depth_probe.read(a, b)
    assert r["n"] == 2
    assert r["hp_lost"] == (-5 + -10) / 2 and r["wins"] == 0.5
    assert r["cut_a"] == 0 and r["cut_b"] == 0.25
    assert r["reproduced_a"] == 2 and r["reproduced_b"] == 0


def test_load_merges(tmp_path=None):
    import json
    import tempfile
    d = tmp_path or tempfile.mkdtemp()
    p, q = os.path.join(d, "p.json"), os.path.join(d, "q.json")
    for path, i in ((p, 0), (q, 1)):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"settings": {}, "fights": [fight(i, 50, 40, True)]}, fh)
    assert [r["i"] for r in depth_probe.load(p + "+" + q)["fights"]] == [0, 1]
    try:
        depth_probe.load(p + "+" + p)
        assert False
    except SystemExit:
        pass


def test_read_against_control():
    b = {"fights": [fight(0, 50, 35, True, (30, True), decisions=10, cut=5)]}
    r = depth_probe.read(depth_probe.observed(b), b)
    assert r["n"] == 1 and r["hp_lost"] == -5 and r["reproduced_a"] == 1 and r["reproduced_b"] == 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
