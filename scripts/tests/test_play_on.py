"""Playing on from stored positions (docs/specs/rung4-check.md, step 1):
`sts.play_on` plays each `Combat` (a decoded position, its RNG the play-out's
chance seed) to the end with the search agent `sts.run` builds.

    python scripts/tests/test_play_on.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import selfplay
import sts

SPECS = [("jaw_worm", selfplay.STARTER + ["Cleave", "Inflame"], s) for s in range(4)]
KEYS = ("won", "score", "hp_end", "turns")


def positions():
    """Codec bytes of every recorded decision state of a few search games."""
    games = sts.run("search", SPECS, record=True, threads=2)
    return [c.encode() for g in games for c in g["states"]]


def outcome(r):
    return tuple(r[k] for k in KEYS)


def test_deterministic_per_seed():
    """The same position and seed give the same game, on any thread count;
    results come back in the order given."""
    pos = positions()[::3]
    a = sts.play_on([sts.Combat.decode(p, seed=7 + i) for i, p in enumerate(pos)], threads=1)
    b = sts.play_on([sts.Combat.decode(p, seed=7 + i) for i, p in enumerate(pos)], threads=4)
    assert [outcome(r) for r in a] == [outcome(r) for r in b] and len(a) == len(pos)
    one = [outcome(sts.play_on([sts.Combat.decode(p, seed=7 + i)], threads=1)[0]) for i, p in enumerate(pos)]
    assert one == [outcome(r) for r in a]
    assert all(set(KEYS) <= set(r) for r in a)


def test_seeds_differ():
    """Different seeds give different games from one stored position."""
    p = positions()[1]
    runs = {outcome(r) for r in sts.play_on([sts.Combat.decode(p, seed=s) for s in range(32)])}
    assert len(runs) > 1


def test_divergent_afterstate_plays():
    """A paused state (End turn before the draw) is advanced with the
    play-out's seed, then played on."""
    c = sts.Combat.decode(positions()[0], seed=3)
    paused = [outs[0][1] for _, kind, outs in c.options() if kind == "divergent"]
    assert paused and not paused[0].awaiting_action() and not paused[0].is_over()
    p = paused[0].encode()
    res = sts.play_on([sts.Combat.decode(p, seed=s) for s in range(8)])
    assert all(r["turns"] >= 1 and (r["won"] == (r["score"] > 0)) for r in res)
    assert len({outcome(r) for r in res}) > 1


def test_finished_state_returns_its_result():
    """A finished combat plays nothing: its own result comes back."""
    c = sts.Combat(SPECS[0][1], SPECS[0][0], seed=0)
    while not c.is_over():
        c.step(sts.search_action(c))
    r = sts.play_on([sts.Combat.decode(c.encode(), seed=5)])[0]
    assert (r["won"], r["score"], r["hp_end"]) == (c.won(), c.score(), c.player_hp())


def test_evaluator_and_settings_like_run():
    """With the same evaluator and search settings, playing on from a game's
    start state plays the game `sts.run` plays (same chance seed)."""
    spec = SPECS[2]
    start = sts.Combat(spec[1], spec[0], seed=spec[2])
    r = sts.run("search", [spec], evaluator="heuristic", limit=8)[0]
    on = sts.play_on([start], evaluator="heuristic", limit=8)[0]
    assert outcome(on) == outcome(r)


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
    print("ok")
