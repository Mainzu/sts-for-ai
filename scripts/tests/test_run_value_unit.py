"""Tests for the run-value chooser (scripts/run_value_unit.py, gauntlet.py
vrun; docs/specs/run-value-chooser.md). Run with
`python scripts/tests/test_run_value_unit.py` (plain asserts) or pytest."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gauntlet  # noqa: E402
import run_value_unit as rvu  # noqa: E402

CELLS = [{"half": h, "cell": c, "deck": ["Strike"] * 5, "character": "ironclad"}
         for h in gauntlet.HALVES for c in range(5)]
REWARD_CELLS = [{"half": h, "cell": 0, "deck": ["Strike", "Anger", "Flex", "Inflame", "Clash", "Cleave"],
                 "character": "ironclad"} for h in gauntlet.HALVES]


def fit_rows(n=60):
    """Fake fit set: sequence m starts floor 7 (index 6) at HP 30 + m; those
    at >= 50 reach the boss with that HP + 10 after the rest, the rest die
    on floor 8. Floor 4 (index 3): everyone at 80, all reach."""
    rows = []
    for m in range(n):
        h = 30 + m
        fl = [{"encounter": "cultist", "hp_start": 80, "hp_end": 80, "won": True} for _ in range(6)]
        fl.append({"encounter": "looter", "hp_start": h, "hp_end": h, "won": True})
        if h >= 50:
            fl += [{"encounter": "x", "hp_start": h, "hp_end": h, "won": True} for _ in range(3)]
            fl.append({"encounter": "hexaghost", "hp_start": min(80, h + 10), "hp_end": 20, "won": True})
            rows.append({"i": m, "half": "train", "cell": 0, "floors": fl, "cleared": True})
        else:
            fl.append({"encounter": "x", "hp_start": h, "hp_end": 0, "won": False})
            rows.append({"i": m, "half": "train", "cell": 0, "floors": fl, "cleared": False})
    return rows


def test_sim_fights_scores():
    """sim_scores equals the old formula over sim_fights, same spec order."""
    seqs = gauntlet.sequences(2, cells=CELLS)
    items = [(s, 40, list(s["deck"])) for s in seqs]
    decks = [[d] + [d + ["Flex"]] for _, _, d in items]
    seen = []

    def sim_play(specs):
        seen.append([dict(s) for s in specs])
        return [{"won": "Flex" in s["deck"], "hp_start": s["hp"], "hp_end": 55} for s in specs]
    scores = gauntlet.sim_scores(5, items, decks, sim_play, boss=True)
    fights = gauntlet.sim_fights(5, items, decks, sim_play, boss=True)
    assert seen[0] == seen[1]
    assert len(fights) == 2 and all(len(pd) == 2 and all(len(parts) == 2 for parts in pd) for pd in fights)
    assert scores == [[gauntlet.sim_score(parts) for parts in pd] for pd in fights]
    assert scores[0] == [0.0, 2 * 1.55]
    # the own-boss override: every boss-part fight is that encounter, next-floor part unchanged
    own = gauntlet.sim_fights(5, items, decks, sim_play, boss=True, bosses=["the_guardian", "slime_boss"])
    specs = seen[-1]
    per = gauntlet.SIM_FIGHTS
    assert [sp["encounter"] for sp in specs[per:2 * per]] == ["the_guardian"] * per
    assert [sp["encounter"] for sp in specs[:per]] == [sp["encounter"] for sp in seen[0][:per]]
    assert len(own) == 2


def test_unit_values():
    u = rvu.RunValue(fit_rows())
    assert abs(rvu.curve("the_guardian", 55) - 0.60) < 1e-9 and rvu.curve("slime_boss", 10) == 0.62
    assert rvu.curve("hexaghost", 95) == 0.90
    boss_fights = [{"won": w} for w in [1, 1, 1, 1, 0, 0, 0, 0]]
    # the curve at rest(40) = 64 for hexaghost: 0.72 + 0.4 x 0.14 = 0.776; 4.5 / 9 = 0.5 -> delta < 0
    d = u.delta("hexaghost", 40, boss_fights)
    assert d < 0 and abs(u.pwin("hexaghost", 64, d) - 0.5) < 1e-9
    assert u.value(70, rvu.BOSS_FLOOR, "hexaghost", 0.0) == u.pwin("hexaghost", gauntlet.rest(70))
    v30, v45, v60, v75 = (u.value(h, 6, "hexaghost", 0.0) for h in (30, 45, 60, 75))
    assert v30 == 0.0 and v30 < v45 < v60 < v75, (v30, v45, v60, v75)
    assert u.pwin("hexaghost", 75) < v75 <= u.pwin("hexaghost", 80) + 1e-9, v75  # neighbours reach at 75-80
    assert 0 < u.value(80, 3, "hexaghost", 0.0) < u.pwin("hexaghost", 80)  # floor 4: all at 80, 40 of 60 reach


def test_vrun_choose():
    u = rvu.RunValue(fit_rows())
    pools = gauntlet.reward_pools(REWARD_CELLS)
    seqs = gauntlet.sequences(1, cells=CELLS)
    s = seqs[0]
    boss = s["fights"][-1]["encounter"]
    seen = []

    def sim_play(specs):
        seen.append(specs)
        out = []
        for sp in specs:
            if sp["group"] == "boss":
                out.append({"won": "Inflame" in sp["deck"] or sp["hp"] >= 70, "hp_start": sp["hp"], "hp_end": 30})
            else:
                out.append({"won": True, "hp_start": sp["hp"], "hp_end": 70 if "Flex" in sp["deck"] else 40})
        return out
    items = [(s, 40, ["Strike"] * 5)]
    offers = [["Anger", "Flex", "Clash"]]
    out = gauntlet.vrun_choose(5, items, offers, sim_play, u)
    assert out[0][0] == offers[0] and out[0][1] == "Flex", out
    assert out[0][2] == {"took_sim": "Flex"}
    specs = seen[-1]
    per = gauntlet.SIM_FIGHTS
    assert len(specs) == 4 * 2 * per
    assert all(sp["encounter"] == boss and sp["group"] == "boss" for sp in specs[per:2 * per])
    assert all(sp["hp"] == gauntlet.rest(40) for sp in specs[per:2 * per])
    assert [sp["seed"] for sp in specs[per:2 * per]] == [gauntlet.SIM_SEED_BASE + s["i"] * 10_000 + 500 + 90 + m for m in range(per)]
    # the floor before the boss: the boss itself, one part; Inflame wins it
    out = gauntlet.vrun_choose(9, items, [["Anger", "Inflame", "Clash"]], sim_play, u)
    assert out[0][1] == "Inflame" and out[0][2]["took_sim"] == "Inflame"
    assert all(sp["encounter"] == boss for sp in seen[-1]) and len(seen[-1]) == 4 * per
    # ties go to skip
    out = gauntlet.vrun_choose(5, items, [["Anger", "Clash", "Cleave"]], sim_play, u)
    assert out[0][1] is None and out[0][2]["took_sim"] is None
    # through run(): took_sim lands in the row
    hook = gauntlet.chooser("vrun", pools, sim_play, unit=u)

    def play(specs):
        return [{"won": True, "hp_start": sp["hp"], "hp_end": min(80, sp["hp"] - 4)} for sp in specs]
    rows = gauntlet.run(seqs, play, reward=hook)
    assert all("took_sim" in fl and "took" in fl for fl in rows[0]["floors"][:-1])
    assert "took_sim" not in rows[0]["floors"][-1]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
