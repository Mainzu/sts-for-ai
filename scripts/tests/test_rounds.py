"""Self-play rounds (every config, Amendment 1) and the deeper teacher
(switch 5): exploration through `sts.run`, datasets joined across rounds,
the sliding window and monotone check, and a smoke run writing per-round
numbers. The softmax pick itself is tested in engine/tests/explore.rs
(temperature 0, frequencies over 10k draws).

    python scripts/tests/test_rounds.py
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
from stsnet import Dataset

SPECS = [("jaw_worm", selfplay.STARTER + ["Cleave", "Inflame"], s) for s in range(8)]


def test_explore_zero_is_default_play():
    a = sts.run("search", SPECS, record=True)
    b = sts.run("search", SPECS, record=True, explore=0.0)
    assert [r["actions"] for r in a] == [r["actions"] for r in b]
    assert [r["score"] for r in a] == [r["score"] for r in b]


def test_explore_is_seeded_and_changes_play():
    a = sts.run("search", SPECS, record=True, explore=0.05)
    b = sts.run("search", SPECS, record=True, explore=0.05)
    plain = sts.run("search", SPECS, record=True)
    assert [r["actions"] for r in a] == [r["actions"] for r in b]
    assert any(r["actions"] != p["actions"] for r, p in zip(a, plain))


def test_concat_keeps_states_and_decisions():
    games = sts.run("search", SPECS, record=True, values=True)
    enc = selfplay.features("effects")
    parts = []
    for half in (games[:4], games[4:]):
        ex = {}
        states, tg, gr = selfplay.sample_states(half, [0] * len(half), np.random.default_rng(0), {"afterstates": True}, ex)
        parts.append(Dataset.from_batches([enc.encode(states, heuristic=True)], tg, gr, ex))
    both = Dataset.concat(parts)
    assert len(both) == len(parts[0]) + len(parts[1])
    k = len(parts[0])
    for f in ("player", "target", "outcome", "option"):
        assert np.array_equal(getattr(both, f)[k:], getattr(parts[1], f))
    i = k + 3
    lo, n = both.card_start[i], both.card_len[i]
    j = parts[1].card_start[3]
    assert np.array_equal(both.cards[lo:lo + n], parts[1].cards[j:j + n])
    lo, n = both.row_start[i], both.row_len[i]
    j = parts[1].row_start[3]
    assert np.array_equal(both.rows[lo:lo + n], parts[1].rows[j:j + n])
    assert set(both.decision[:k]).isdisjoint(both.decision[k:])


def test_one_self_play_search_for_every_round():
    """No deeper-teacher switch: the self-play search is SELFPLAY_SEARCH
    unless a config names its own."""
    assert learn.data_search({}) == learn.SELFPLAY_SEARCH
    assert learn.data_search({"switches": {"deeper_teacher": True}}) == learn.SELFPLAY_SEARCH
    assert learn.data_search({"search": {"limit": 8}}) == {"limit": 8}


def test_take_matches_batch():
    """`Dataset.take` keeps exactly the chosen examples (cards, hook rows,
    extras), in order."""
    games = sts.run("search", SPECS[:3], record=True, values=True)
    ex = {}
    states, tg, gr = selfplay.sample_states(games, [0, 1, 2], np.random.default_rng(0), {"afterstates": True}, ex)
    ds = Dataset.from_batches([selfplay.features("effects").encode(states, heuristic=True)], tg, gr, ex)
    idx = np.array([0, 3, 4, len(ds) - 1])
    a, b = ds.take(idx).batch(np.arange(len(idx))), ds.batch(idx)
    assert set(a) == set(b)
    for k in a:
        assert np.array_equal(a[k], b[k]), k


def test_pool_samples_spread_and_seeded():
    """A sample of the pool is a fraction of its examples drawn across all
    games (examples are stored game by game, ~7 each), fixed by its seed."""
    n = 7000
    a = learn.sample_index(n, 0.5, 11)
    assert len(a) == 3500 and np.array_equal(a, np.unique(a))
    assert len(set((a // 7).tolist())) >= 950  # nearly every game keeps an example
    assert np.array_equal(a, learn.sample_index(n, 0.5, 11))
    assert not np.array_equal(a, learn.sample_index(n, 0.5, 12))
    assert len(learn.sample_index(n, 1 / 6, 11)) == round(n / 6)


FIT_KW = []  # keyword arguments of each mocked fit


class FakeRun:
    def __init__(self, i):
        self.id = self.model_path = f"m{i}"
        self.written = {}

    def _write(self, name, obj):
        self.written[name] = obj

    def finish(self, **k):
        pass


def fights(x, n=600):
    """Mock tight-fight results at win rate ~x: spec i is won when its fixed
    fraction is below x, so a stronger mock wins a superset of the specs."""
    return [int((i * 0.6180339887) % 1 < x) for i in range(n)]


def mocked_learn(cfg, wins, heuristic):
    """learn.learn with self-play, training and the tight fights mocked:
    `wins` {model: (train, held_out)} win rates, `heuristic` the
    heuristic's. Returns (runs, fits, dataset calls, tight_results calls)."""
    calls, fits, data = [], [], []

    def tight_results(ev, search, every, log=None):
        calls.append((ev, search, every))
        w = heuristic if ev == "heuristic" else wins[ev]
        return {h: fights(x) for h, x in zip(("train", "held_out"), w)}

    def dataset(cfg, which, root=None, rnd=0, parent=None, log=None, late=False):
        data.append((which, rnd, None if parent is None else parent.id, late))
        return f"{which}{rnd}"

    def fit(cfg, name, parts, val_id, *a, **k):
        fits.append((name, list(parts), val_id))
        FIT_KW.append(k)
        return FakeRun(len(fits) - 1), 0.1, {d: 0.0 for d, _ in parts}, None

    FIT_KW.clear()
    saved = learn.tight_results, learn.dataset, learn.fit, learn.trusted_zone, learn.solve_step, learn.tight_cells
    learn.tight_results, learn.dataset, learn.fit = tight_results, dataset, fit
    learn.tight_cells = lambda every: None  # mocked fights: each its own cell
    learn.trusted_zone = lambda cfg, model: None  # the puzzles need a real net
    learn.solve_step = lambda *a, **k: None  # the datasets are fake
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:  # clean_stale stays off main's cache/
            runs = learn.learn(cfg, root=root, log=lambda *a: None)
    finally:
        learn.tight_results, learn.dataset, learn.fit, learn.trusted_zone, learn.solve_step, learn.tight_cells = saved
    return runs, fits, data, calls


def test_window_and_monotone_from_round_2():
    """While no net reaches the heuristic, round k trains on its own games,
    round k-1's and round 0's (round 0 alone at first); round k >= 1 plays
    with round k-1's net; the tight-fight win rate is measured for rounds
    1..n with the agent's one-turn search only, the heuristic's once; the
    monotone check compares each round with the previous one from round 2."""
    cfg = {"name": "x", "search": {"limit": 16}, "rounds": {"n": 3, "every": 7}, "switches": {}}
    runs, fits, data, calls = mocked_learn(cfg, {"m1": (0.5, 0.5), "m2": (0.2, 0.5), "m3": (0.5, 0.5)}, (0.9, 0.9))
    assert [p for _, p, _ in fits] == [[("train0", 0)], [("train1", 1), ("train0", 0)],
                                       [("train2", 2), ("train1", 1), ("train0", 0)],
                                       [("train3", 3), ("train2", 2), ("train0", 0)]]
    assert [n for n, _, _ in fits] == ["x-r0", "x-r1", "x-r2", "x-r3"] and {v for _, _, v in fits} == {"val0"}
    assert data[1:] == [("train", 0, None, False), ("train", 1, "m0", False), ("train", 2, "m1", False),
                        ("train", 3, "m2", False)]
    assert sorted(ev for ev, _, _ in calls) == ["heuristic", "m1", "m2", "m3"]
    assert all(s == {"limit": 16} and e == 7 for _, s, e in calls)
    mono = [r.written["round.json"]["monotone"] for r in runs]
    assert mono[0] is None and mono[1] is None
    assert mono[2]["ok"] is False and mono[3]["ok"] is True  # 0.2 (+-0.03) lies below 0.5 (+-0.04)
    assert mono[2]["every"] == 7 and mono[3]["halves"]["train"]["previous"] == learn.win_rates({"t": fights(0.2)})["t"]
    assert runs[0].written["round.json"]["tight_win"] is None


def test_round_0_stays_until_the_net_reaches_the_heuristic():
    """Round 0's games stay in the window while no round's net reaches the
    heuristic's tight-fight win rate on both halves (one half isn't
    enough); from the round after one does, the window is the last 2
    rounds, those rounds play `n_late` games, and round 0 stays out even
    after a later net falls below the heuristic again."""
    cfg = {"name": "x", "search": {"limit": 16}, "rounds": {"n": 4, "every": 1}, "switches": {}}
    wins = {"m1": (0.45, 0.55),  # one half only: stays
            "m2": (0.5, 0.5),    # both halves at the heuristic's: leaves from round 3
            "m3": (0.3, 0.3), "m4": (0.6, 0.6)}
    runs, fits, data, calls = mocked_learn(cfg, wins, (0.5, 0.5))
    assert [p for _, p, _ in fits] == [[("train0", 0)], [("train1", 1), ("train0", 0)],
                                       [("train2", 2), ("train1", 1), ("train0", 0)],
                                       [("train3", 3), ("train2", 2)], [("train4", 4), ("train3", 3)]]
    assert [late for which, _, _, late in data if which == "train"] == [False, False, False, True, True]
    assert [ev for ev, _, _ in calls].count("heuristic") == 1
    rj = [r.written["round.json"] for r in runs]
    assert [r["window"]["round0_in"] for r in rj] == [True, True, True, False, False]
    assert [r["window"]["datasets"] for r in rj] == [[d for d, _ in p] for _, p, _ in fits]
    assert rj[0]["heuristic"] is None
    assert [r["heuristic"]["reached"] for r in rj[1:]] == [False, True, False, True]
    assert rj[1]["heuristic"]["halves"]["held_out"]["reached"] is True
    assert rj[1]["heuristic"]["halves"]["train"]["reached"] is False
    half = learn.win_rates({"train": fights(0.5)})["train"]
    assert rj[2]["heuristic"]["halves"]["train"]["heuristic"] == half == rj[2]["heuristic"]["halves"]["train"]["net"]
    assert rj[2]["tight_results"]["net"]["train"] == "".join(map(str, fights(0.5)))


def test_round_0_pool_is_sampled():
    """With `d0_sample`, round 0's net trains on a half of the pool (a fixed
    sample and training seed, so both seeds of a sweep share it); while
    round 0 is in, later rounds use a sixth drawn once per seed: the same in
    every round, other for another `round_seed`. Without it, no sampling."""
    def run(round_seed):
        cfg = {"name": "x", "search": {"limit": 16}, "rounds": {"n": 3, "every": 1}, "switches": {},
               "d0_sample": {"round0": 0.5, "later": 1 / 6}, "round_seed": round_seed, "seed": 1,
               "round0_seed": 0}
        runs, fits, _, _ = mocked_learn(cfg, {f"m{i}": (0.1, 0.1) for i in (1, 2, 3)}, (0.5, 0.5))
        return [dict(k) for k in FIT_KW], [r.written["round.json"]["window"] for r in runs]
    kw_a, win_a = run(1000)
    kw_b, _ = run(2000)
    (f0, s0), = kw_a[0]["samples"].values()
    assert list(kw_a[0]["samples"]) == ["train0"] and f0 == 0.5 and kw_a[0]["seed"] == 0
    later = [k["samples"]["train0"] for k in kw_a[1:]]
    assert len(set(later)) == 1 and later[0][0] == 1 / 6 and later[0][1] != s0
    assert [k["seed"] for k in kw_a[1:]] == [1, 1, 1]
    assert kw_b[0]["samples"] == kw_a[0]["samples"] and kw_b[1]["samples"] != kw_a[1]["samples"]
    assert [w["round0_sample"] for w in win_a] == [0.5, 1 / 6, 1 / 6, 1 / 6]
    mocked_learn({"name": "x", "search": {"limit": 16}, "rounds": {"n": 2, "every": 1}, "switches": {}},
                 {"m1": (0.1, 0.1), "m2": (0.1, 0.1)}, (0.5, 0.5))
    assert all(not k["samples"] for k in FIT_KW)


def test_late_rounds_play_n_late_games():
    """`n_late` games per group after round 0 retires (default `n_round`)."""
    seen = []
    saved = registry.find
    registry.find = lambda gen, **k: seen.append(gen["n_per_group"]) or "ds"
    try:
        cfg = {"n_train": 50, "n_val": 5, "n_round": 7, "train_seed": 1, "val_seed": 2}
        learn.dataset(cfg, "train", rnd=2)
        learn.dataset(dict(cfg, n_late=11), "train", rnd=2, late=True)
        learn.dataset(cfg, "train", rnd=2, late=True)
        learn.dataset(cfg, "train", rnd=0)
    finally:
        registry.find = saved
    assert seen == [7, 11, 7, 50]


def test_label_scale():
    """|mean label - mean real outcome| of a dataset."""
    ds = Dataset.from_batches([selfplay.features("effects").encode([sts.Combat(selfplay.STARTER, "cultist", seed=1)] * 4)],
                              [1.0, 1.2, 1.4, 1.6], extra={"outcome": [1.5, 1.5, 1.5, 1.5]})
    assert abs(learn.label_scale(ds) - 0.2) < 1e-6


def test_smoke_run_rounds_0_to_2():
    """Rounds 0..2 (ranking always on): one registry run per round, the
    window of datasets (round 0's kept while no net reaches the heuristic),
    parents and exploration in the manifests, labels exactly on the outcome
    scale except through rungs 1 and 3, per-round numbers (the trusted zone
    and the database's rows after the solve step included) written."""
    cfg = {"name": "smoke-r", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 61, "val_seed": 62,
           "search": {"limit": selfplay.LIMIT}, "seed": 0, "rounds": {"n": 2, "temperature": 0.05, "every": 100},
           "switches": {}}
    with tempfile.TemporaryDirectory() as root:
        runs = learn.learn(cfg, root=root, log=lambda *_: None)
        assert len(runs) == 3
        rounds = [json.load(open(os.path.join(r.path, "round.json"))) for r in runs]
        assert [r["round"] for r in rounds] == [0, 1, 2]
        r0, r1, r2 = rounds
        assert r0["parent_run"] is None and r1["parent_run"] == runs[0].id and r2["parent_run"] == runs[1].id
        assert r0["datasets"]["train"] == [r0["new_dataset"]]
        assert r1["datasets"]["train"] == [r1["new_dataset"], r0["new_dataset"]]
        d2 = [r2["new_dataset"], r1["new_dataset"]] + ([] if r1["heuristic"]["reached"] else [r0["new_dataset"]])
        assert r2["datasets"]["train"] == d2 == r2["window"]["datasets"]
        assert r2["window"]["round0_in"] is (not r1["heuristic"]["reached"])
        assert set(r1["heuristic"]["halves"]) == {"train", "held_out"}
        for k, r in ((1, r1), (2, r2)):
            m = registry.load_manifest(r["new_dataset"], root)
            assert m["parent_model"] == runs[k - 1].id and m["config"]["explore"] == 0.05
            assert m["config"]["round"] == k
        assert registry.load_manifest(r0["new_dataset"], root)["parent_model"] is None
        assert set(r0["label_scale"]["per_dataset"]) == {r0["new_dataset"]}
        # Off the outcome only through rungs 1 and 3: without the database,
        # round 0's games and games whose playing net has no trusted zone
        # keep their outcomes exactly.
        frontier = {run.id: r["trusted"]["frontier"] for run, r in zip(runs, rounds)}
        rnd = {r["new_dataset"]: r["round"] for r in rounds}
        for r in rounds:
            assert r["db_rows"] > 0
            for d in r["label_scale"]["per_dataset"]:
                if frontier.get(registry.load_manifest(d, root)["parent_model"]) is None:
                    assert learn.label_scale(learn.load_examples(cfg, d, rnd[d], root=root)) == 0.0, d
            assert set(r["trusted"]) == {"per_horizon", "min_puzzles", "regret_max", "frontier"}
            assert r["trusted"]["per_horizon"]["0"]["n"] >= learn.MIN_PUZZLES
        for r in rounds:
            assert set(r["label_scale"]["per_dataset"]) == set(r["datasets"]["train"])
            assert r["val_mse"] > 0
        assert r0["tight_win"] is None and r0["monotone"] is None and r1["monotone"] is None
        assert isinstance(r2["monotone"]["ok"], bool)
        for half in ("train", "held_out"):
            assert len(r2["monotone"]["halves"][half]["net"]) == 3
            assert r2["monotone"]["halves"][half]["previous"] == r1["tight_win"][half]
        with open(os.path.join(registry.runs_dir(root), "index.csv"), encoding="utf-8") as f:
            assert len(f.read().strip().splitlines()) == 4  # header + one line per round
        # A restart resumes after the last finished round: rounds 1-2 are
        # reused (no solve step, training or tight fights), round 0 as the
        # sweep passes it; a round without its `finished` mark trains again.
        assert all(r["finished"] for r in rounds)
        saved = learn.fit, learn.solve_step, learn.tight_results

        def refuse(*a, **k):
            raise AssertionError("trained again")
        learn.fit = learn.solve_step = learn.tight_results = refuse
        try:
            again = learn.learn(cfg, root=root, log=lambda *_: None, round0=runs[0])
            assert [r.id for r in again] == [r.id for r in runs]
            rec = dict(rounds[2])
            del rec["finished"]
            runs[2]._write("round.json", rec)
            try:
                learn.learn(cfg, root=root, log=lambda *_: None, round0=runs[0])
                raise RuntimeError("round 2 was reused")
            except AssertionError as e:
                assert str(e) == "trained again"
            full = {**cfg, **learn.label_settings(cfg)}  # as learn stores it
            assert learn.find_round(full, 1, rounds[1]["datasets"]["train"], runs[0], root).id == runs[1].id
            assert learn.find_round({**full, "solve_threads": 5}, 1, rounds[1]["datasets"]["train"], runs[0],
                                    root).id == runs[1].id
            assert learn.find_round({**full, "seed": 1}, 1, rounds[1]["datasets"]["train"], runs[0], root) is None
            # a round whose tight fights were another set's (older rounds record none) isn't reused
            assert rounds[1]["tight_set"] == learn.TIGHT_SET
            for other in ({k: v for k, v in rounds[1].items() if k != "tight_set"}, {**rounds[1], "tight_set": "tight"}):
                runs[1]._write("round.json", other)
                assert learn.find_round(full, 1, rounds[1]["datasets"]["train"], runs[0], root) is None
            runs[1]._write("round.json", rounds[1])
        finally:
            learn.fit, learn.solve_step, learn.tight_results = saved


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
