"""Branch rollouts (learned-play switch 7, Amendment 2): forced openings in
`sts.run`, the choice of branch (an option outside the exploration
temperature), branch games in a round's dataset and their labels (only
states after the forced action, with the branch's own outcome).

    python scripts/tests/test_branches.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

import learn
import registry
import selfplay
import sts

SPECS = [("jaw_worm", selfplay.STARTER + ["Cleave", "Inflame"], s) for s in range(8)]
TEMP = 0.05


def key(c):
    """A state's identity for comparisons: its render and effect features."""
    b = sts.Features("effects").encode([c])
    return c.render(), b["player"].tobytes(), b["monsters"].tobytes(), b["cards"].tobytes()


def test_forced_openings_reproduce_the_game():
    """A game given the first n actions of a recorded game reproduces its
    first n states (and the state after them) exactly; forced decisions
    record no search values."""
    main = sts.run("search", SPECS, record=True, values=True)
    n = [len(r["actions"]) // 2 for r in main]
    forced = [r["actions"][:k] for r, k in zip(main, n)]
    got = sts.run("search", SPECS, record=True, values=True, forced=forced)
    for r, g, k in zip(main, got, n):
        assert g["actions"][:k] == r["actions"][:k]
        assert [key(s) for s in g["states"][:k + 1]] == [key(s) for s in r["states"][:k + 1]]
        assert all(v == [] for v in g["values"][:k])
        assert all(v for v in g["values"][k:])


def test_no_forced_actions_leave_output_unchanged():
    plain = sts.run("search", SPECS, record=True, values=True)
    empty = sts.run("search", SPECS, record=True, values=True, forced=[[] for _ in SPECS])
    for a, b in zip(plain, empty):
        assert a["actions"] == b["actions"] and a["score"] == b["score"]
        assert [[(list(x), v) for x, v in d] for d in a["values"]] == [[(list(x), v) for x, v in d] for d in b["values"]]


def test_illegal_forced_action_is_an_error():
    try:
        sts.run("search", SPECS[:1], forced=[[sts.Action("Bash", 3)]])
    except ValueError as e:
        assert "forced" in str(e)
    else:
        raise AssertionError("an illegal forced action must raise")


def fake(values):
    return {"values": [[([sts.Action("Strike", 0) if i == 0 else sts.Action()], v) for i, v in enumerate(d)]
                       for d in values]}


def test_branch_options_lie_outside_the_temperature():
    """Only options valued below their decision's best by more than the
    temperature can be forced; a game with none gets no branch."""
    close = fake([[1.0, 0.97], [0.5, 0.48, 0.46]])          # every option within 0.05
    far = fake([[1.0, 0.99], [0.8, 0.70], [0.6, 0.59]])      # only decision 1 has one
    rng = np.random.default_rng(0)
    for _ in range(50):
        picks = selfplay.pick_branches([close, far], TEMP, rng)
        assert [(g, i) for g, i, _ in picks] == [(1, 1)]
        assert picks[0][2] == sts.Action()  # the 0.70 option of decision 1


def test_branch_games_deviate_outside_the_temperature():
    """Every stored branch game replays its main game up to the branch point
    and then forces an option valued below that decision's best by more
    than the temperature."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        specs, groups = selfplay.make_specs(4, 71, selfplay.train_deck)
        cfg = {"search": {"limit": selfplay.LIMIT}, "explore": TEMP, "branches": True, "sample_seed": 5}
        ds, _ = registry.selfplay(specs, groups, cfg, root=root)
        games = registry.load_games(ds, root)
        main = [g for g in games if "branch_at" not in g]
        branches = [g for g in games if "branch_at" in g]
        assert len(main) == len(specs) and branches
        assert games[:len(main)] == main  # branch games come after every main game
        for b in branches:
            m, i = main[b["branch_of"]], b["branch_at"]
            assert b["actions"][:i] == m["actions"][:i] and b["seed"] == m["seed"]
            vals = m["values"][i]
            best = max(v for _, v in vals)
            forced = [v for acts, v in vals if b["actions"][i] == acts[0]]
            assert forced and forced[0] < best - TEMP
            assert b["values"][i] == [] and all(b["values"][j] for j in range(i + 1, len(b["actions"])))


def branch_dataset(root, branches, explore=TEMP):
    """A dataset with or without branch games; at temperature 0 (Amendment
    4's greedy self-play) branches come from `branch_gap`."""
    specs, groups = selfplay.make_specs(4, 73, selfplay.train_deck)
    cfg = {"search": {"limit": selfplay.LIMIT}, "explore": explore, "sample_seed": 9,
           **({"branches": True, **({"branch_gap": TEMP} if explore == 0 else {})} if branches else {})}
    return registry.selfplay(specs, groups, cfg, root=root)[0]


def test_branch_examples_come_after_the_branch_point():
    """A branch game's examples are states after its forced action, all
    labelled with the branch game's own outcome (plain and ranking
    sampling)."""
    for explore in (TEMP, 0.0):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
            check_branch_examples(registry.load_games(branch_dataset(root, True, explore), root))


def check_branch_examples(games):
    assert any("branch_at" in g for g in games)
    for b in (g for g in games if "branch_at" in g):
        r = registry.replay(b)
        before = {key(s) for s in r["states"][:b["branch_at"] + 1]}
        for labels in (None, {"rank": True}, {"afterstates": True}):
            states, target, _ = selfplay.sample_states([r], [b["group"]], np.random.default_rng(0), labels, {})
            if len(r["states"]) > b["branch_at"] + 1:
                assert states
            assert all(key(s) not in before for s in states)
            assert all(t == b["outcome"]["score"] for t in target)


def test_main_game_labels_unchanged_by_branches():
    for explore in (TEMP, 0.0):
        check_main_labels(explore)


def check_main_labels(explore):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        plain = registry.examples(branch_dataset(root, False, explore), "effects", root=root, labels={"afterstates": True})
        both = registry.examples(branch_dataset(root, True, explore), "effects", root=root, labels={"afterstates": True})
        n = len(plain)
        assert len(both) > n
        assert np.array_equal(plain.target, both.target[:n])
        assert np.array_equal(plain.player, both.player[:n]) and np.array_equal(plain.rank_value, both.rank_value[:n])


def test_greedy_self_play_with_branches():
    """Amendment 4: at temperature 0, branches still come from `branch_gap`
    (not the temperature); every main game's recorded action is its
    decision's first best option, and a branch game is greedy after its
    forced option; every forced option lies more than `branch_gap` below
    its decision's best."""
    gap = 0.05
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        specs, groups = selfplay.make_specs(4, 75, selfplay.varied_deck, hp_fn=selfplay.varied_hp)
        cfg = {"search": {"limit": selfplay.LIMIT}, "explore": 0.0, "branches": True, "branch_gap": gap,
               "sample_seed": 5}
        games = registry.load_games(registry.selfplay(specs, groups, cfg, root=root)[0], root)
        main = [g for g in games if "branch_at" not in g]
        branches = [g for g in games if "branch_at" in g]
        assert len(main) == len(specs) and branches

        def first_best(acts, vals):
            best = max(v for _, v in vals)
            return next(a for a, v in vals if v == best)[0] == acts

        for m in main:
            assert all(first_best(a, v) for a, v in zip(m["actions"], m["values"]) if v)
        for b in branches:
            i = b["branch_at"]
            vals = main[b["branch_of"]]["values"][i]
            forced = [v for acts, v in vals if b["actions"][i] == acts[0]]
            assert forced and forced[0] < max(v for _, v in vals) - gap
            assert all(first_best(a, v) for a, v in list(zip(b["actions"], b["values"]))[i + 1:] if v)


def test_branch_gap_is_the_threshold():
    """pick_branches takes the gap: with a gap above every option's
    shortfall, no branch; with a smaller one, branches only past it."""
    r = {"values": [[(["a"], 1.0), (["b"], 0.97), (["c"], 0.90)], [(["d"], 1.0), (["e"], 0.99)]]}
    rng = np.random.default_rng(0)
    assert selfplay.pick_branches([r], 0.2, rng) == []
    picks = [selfplay.pick_branches([r], 0.05, rng)[0] for _ in range(50)]
    assert {p[1:] for p in picks} == {(0, "c")}


def test_learn_with_branches():
    """A tiny run with switch 7: rounds >= 1 store branch games, round 0
    none, and every round trains."""
    cfg = {"name": "smoke-b", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 81, "val_seed": 82,
           "search": {"limit": selfplay.LIMIT}, "seed": 0, "rounds": {"n": 1, "temperature": TEMP, "every": 100},
           "switches": {"branches": True}}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        runs = learn.learn(cfg, root=root, log=lambda *_: None)
        rounds = [json.load(open(os.path.join(r.path, "round.json"))) for r in runs]
        g0 = registry.load_games(rounds[0]["new_dataset"], root)
        g1 = registry.load_games(rounds[1]["new_dataset"], root)
        assert not any("branch_at" in g for g in g0)
        assert any("branch_at" in g for g in g1)
        assert registry.load_manifest(rounds[1]["new_dataset"], root)["config"]["branches"] is True
        assert all(r["val_mse"] > 0 for r in rounds)


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok ", name)
            n += 1
    print(f"{n} passed")
