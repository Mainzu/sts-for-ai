"""Learned-play sweep runner: Amendment 3's plan (one config x 2 seeds,
rounds 6-10 with the stop rule, round 0 trained before the night, the
night sized for --jobs 2), the machinery kept from Amendment 2 (several
configs, round 0 shared and reused, b4_plan()), the printed projection and
budget refusal, the random-floor guard, the watcher's files, and dry runs
on tiny data that write runs and the sweep table.

    python scripts/tests/test_sweep.py
"""

import contextlib
import datetime
import io
import itertools
import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bench
import learn
import registry
import sweep

# The sizes follow the memory free when the sweep plans; tests size for a
# fixed amount (a night with other programs closed).
TEST_FREE = 14.0
sweep.free_gb = lambda: TEST_FREE


@contextlib.contextmanager
def b4_plan():
    """Amendment 2's plan: target x branches = 4 configs."""
    saved = sweep.CONFIGS
    sweep.CONFIGS = [(hp, br) for hp in (False, True) for br in (False, True)]
    try:
        yield
    finally:
        sweep.CONFIGS = saved


def test_plan_is_one_config_with_two_seeds():
    """Amendment 4: score target with branch rollouts x 2 seeds; greedy
    self-play (temperature 0), branches at BRANCH_GAP."""
    p = sweep.plan()
    assert [r["name"] for r in p] == ["score+branch-s0", "score+branch-s1"]
    assert all(not r["hp"] and r["branches"] for r in p) and [r["seed"] for r in p] == [0, 1]
    cfg = sweep.config("x", False, True, 0, 10, 2, 2)
    assert cfg["rounds"]["temperature"] == 0.0 and cfg["branch_gap"] == 0.05


def test_plan_of_four_configs_still_works():
    """CONFIGS of all four: 4 configs x 2 seeds, seed-major, each branch
    config right after its twin."""
    with b4_plan():
        p = sweep.plan()
    assert [r["name"] for r in p] == ["score-s0", "score+branch-s0", "hp-s0", "hp+branch-s0",
                                      "score-s1", "score+branch-s1", "hp-s1", "hp+branch-s1"]
    assert {(r["hp"], r["branches"]) for r in p} == set(itertools.product((False, True), repeat=2))
    assert [r["seed"] for r in p] == [0] * 4 + [1] * 4


def test_config_switches_and_seeds():
    cfg = sweep.config("x", hp=True, branches=True, seed=1, n=50, n_round=7, n_late=9, every=9)
    assert cfg["switches"] == {"hp_loss": True, "branches": True}
    assert cfg["rounds"] == {"n": 10, "min": 6, "temperature": 0.0, "every": 9}
    assert cfg["setups"] == "varied"
    assert sweep.config("x", False, False, 0, 5, 2, 2, rounds=(1, 2))["rounds"]["n"] == 2
    assert cfg["n_train"] == 50 and cfg["n_val"] == 5 and cfg["n_round"] == 7 and cfg["n_late"] == 9
    assert cfg["search"] == learn.SELFPLAY_SEARCH and cfg["seed"] == 1
    assert sweep.config("b", hp=False, branches=False, seed=0, n=10, n_round=2, n_late=2)["switches"] == {}
    big = sweep.config("p", hp=False, branches=False, seed=1, n=sweep.FULL_N, n_round=7, n_late=9)
    assert sweep.FULL_N == 20_000 and big["n_val"] == 1000  # the pool grows, validation doesn't
    assert big["d0_sample"] == {"round0": 0.5, "later": 1 / 6} and big["round0_seed"] == 0


def test_round_0_trained_once_per_target():
    """Every run of a target after the first (other seed, branch twin)
    reuses that target's round-0 run; the projection counts round 0's
    training once per target."""
    with b4_plan():
        given, rows = [], sweep.projection()[0]

    class Fake:
        def __init__(self, name):
            self.id = name

        def _read(self, _):
            return fake_bench(0.5, 0.9)

    def fake_learn(cfg, round0=None, **k):
        given.append((cfg["name"], None if round0 is None else round0.id))
        return [Fake(cfg["name"] + "-r0")] + [Fake(cfg["name"] + f"-r{i}") for i in range(1, sweep.ROUNDS + 1)]
    real_learn, real_report = sweep.learn.learn, sweep.report
    sweep.learn.learn, sweep.report = fake_learn, lambda *a: ""
    try:
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(registry.runs_dir(root))
            sweep.run_sweep(rows, root, log=lambda *_: None)
    finally:
        sweep.learn.learn, sweep.report = real_learn, real_report
    assert given == [("score-s0", None), ("score+branch-s0", "score-s0-r0"), ("hp-s0", None),
                     ("hp+branch-s0", "hp-s0-r0"), ("score-s1", "score-s0-r0"), ("score+branch-s1", "score-s0-r0"),
                     ("hp-s1", "hp-s0-r0"), ("hp+branch-s1", "hp-s0-r0")]


def test_seeds_share_round_0_and_differ_later():
    """The two seeds of a target play the same round-0 games and validation
    set; later rounds play other games per seed."""
    seeds = {}

    def capture(gen, parent_model=None, root=None):
        seeds.setdefault(gen["set"] + str(gen.get("round", 0)), set()).add(gen["spec_seed"])
        return "x"
    real = registry.find
    registry.find = capture
    try:
        for s in (0, 1):
            cfg = sweep.config("x", hp=False, branches=False, seed=s, n=10, n_round=2, n_late=2)
            learn.dataset(cfg, "train", rnd=0)
            learn.dataset(cfg, "val", rnd=0)
            learn.dataset(cfg, "train", rnd=1, parent=registry.Run("r"))
    finally:
        registry.find = real
    assert len(seeds["train0"]) == 1 and len(seeds["val0"]) == 1 and len(seeds["train1"]) == 2


def test_sizes_fit_the_night():
    """With --jobs 2 (the night's), every run has the same sizes; n_late >=
    n_round; ROUNDS (6) rounds of each run fit the night, worst case (round
    0 in every round's training, n_late from round 2); n_late is the
    largest that fits; round 0 (pool, validation, net) is before the night;
    each row also has its ROUNDS_MAX (10) worst case and the cumulative
    minutes per round."""
    rows, before, total = sweep.projection(jobs=2)
    assert len(rows) == 2 and len({(r["n"], r["n_round"], r["n_late"], r["every"]) for r in rows}) == 1
    n_round, n_late = rows[0]["n_round"], rows[0]["n_late"]
    assert rows[0]["n"] == sweep.FULL_N and 1 <= n_round <= n_late <= sweep.FULL_N
    assert total <= sweep.NIGHT_MIN
    assert (sweep.projection(n_round + 1, n_round + 1, jobs=2)[2] > sweep.NIGHT_MIN  # n_round is the largest
            or any(sweep.round_min(r, n_round + 1) > sweep.ROUND_MIN for r in rows)
            or any(sweep.train_examples(r, n_round + 1, n_round + 1) > sweep.max_train_examples(2) for r in rows)
            or sweep.play_peak_gb(n_round + 1) > sweep.run_budget_gb(2))
    assert all(sweep.round_min(r, n_late) <= sweep.ROUND_MIN for r in rows)
    assert all(sweep.train_examples(r, n_round, n_late) <= sweep.max_train_examples(2) for r in rows)
    if n_late < sweep.FULL_N:
        assert (sweep.projection(n_round, n_late + 1, jobs=2)[2] > sweep.NIGHT_MIN
                or any(sweep.round_min(r, n_late + 1) > sweep.ROUND_MIN for r in rows)
                or any(sweep.train_examples(r, n_round, n_late + 1) > sweep.max_train_examples(2) for r in rows)
                or sweep.play_peak_gb(n_late + 1) > sweep.run_budget_gb(2))
    assert abs(total - max(r["minutes"] for r in rows) * sweep.slowdown(2)) < 1e-6  # side by side, no waiting
    assert abs(before - sweep.round0_min(False, sweep.FULL_N)
               - sweep.round0_train_min(False, sweep.FULL_N, sweep.solve_threads(1))) < 1e-9
    for r in rows:
        cum = r["cumulative"]
        assert len(cum) == sweep.ROUNDS_MAX + 1 and cum == sorted(cum)
        assert abs(cum[sweep.ROUNDS] - r["minutes"]) < 1e-9 and abs(cum[-1] - r["minutes_max"]) < 1e-9
        assert 1.3 < r["minutes_max"] / r["minutes"] < 2.0  # rounds 7-10: up to ~70% longer
    # the largest training set learn.learn builds: round 0's sixth + 2 rounds at n_round while round 0 is
    # in, or 2 rounds at n_late after (branch examples included)
    ex = sweep.ROUND_EXAMPLES * (1 + sweep.BRANCH_EXAMPLES)
    assert abs(sweep.train_examples(rows[0], 100, 500) - max(3 * 20_000 * 7 / 6 + 2 * 3 * 100 * ex, 2 * 3 * 500 * ex)) < 1e-6
    assert abs(sweep.train_examples(rows[0], 100, 120) - (3 * 20_000 * 7 / 6 + 2 * 3 * 100 * ex)) < 1e-6
    with b4_plan():
        by = {r["name"]: r for r in sweep.projection(n_round, n_late)[0]}
    # the score target solves each round's tails (the HP target doesn't); without that it is the cheaper one
    solve = sweep.solve_min(by["score-s0"], learn.SOLVE_GAMES, by["score-s0"]["solve_threads"])
    assert solve > 0 and sweep.solve_min(by["hp-s0"], learn.SOLVE_GAMES) == 0
    assert by["score-s0"]["minutes"] - sweep.ROUNDS * solve < by["hp-s0"]["minutes"]
    # branches cost more; a branch twin skips round 0's training
    assert sweep.project(by["score+branch-s0"], 100, 500) > sweep.project(by["score-s0"], 100, 500)
    assert sweep.project(by["score+branch-s0"], 100, 500, reuse0=True) < sweep.project(by["score+branch-s0"], 100, 500)
    # worst case: a bigger n_late costs more even with round 0 in training
    assert sweep.project(by["hp-s0"], 100, 600) > sweep.project(by["hp-s0"], 100, 500)


def test_train_examples_is_what_learn_builds():
    """sweep.train_examples equals the largest training set learn.learn
    really builds (self-play, training and tight fights mocked; sizes from
    the sweep's per-game example counts), with round 0 retired after round
    1 and never."""
    row = sweep.projection()[0][0]
    cfg = sweep.row_config(row)

    def size(ds, samples):
        rnd, n = ds
        ex = sweep.GROUPS * n * sweep.ROUND0_EXAMPLES if rnd == 0 else sweep.round_examples(row, n)
        return ex * (samples[ds][0] if ds in samples else 1.0)

    class Run:
        model_path = id = "run"

        def _write(self, *a):
            pass

        def finish(self, **k):
            pass

    built = {}
    saved = learn.dataset, learn.fit, learn.tight_results, learn.trusted_zone, learn.solve_step, learn.tight_cells
    learn.tight_cells = lambda every: None  # mocked fights: each its own cell
    learn.trusted_zone = lambda c, model: None  # the puzzles need a real net
    learn.solve_step = lambda *a, **k: None  # the datasets are fake
    try:
        for retire in (1, None):
            sizes = []

            def dataset(c, which, root=None, rnd=0, parent=None, log=None, late=False):
                return ("val", 0) if which == "val" else (rnd, (c["n_late"] if late else c["n_round"]) if rnd else c["n_train"])

            def fit(c, name, parts, val_id, *a, samples=None, **k):
                sizes.append(sum(size(d, samples or {}) for d, _ in parts))
                return Run(), 0.1, {}, None

            def tight_results(ev, search, every, log=None):
                k = len(sizes) - 1
                v = 0.5 if ev == "heuristic" else (0.6 if retire is not None and k >= retire else 0.4)
                return {h: [int((i * 0.6180339887) % 1 < v) for i in range(600)] for h in ("train", "held_out")}
            learn.dataset, learn.fit, learn.tight_results = dataset, fit, tight_results
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:  # clean_stale stays off main's cache/
                learn.learn({**cfg, "rounds": {**cfg["rounds"], "min": None, "n": 6}}, root=root, log=lambda *a: None)
            built[retire] = max(sizes)
    finally:
        learn.dataset, learn.fit, learn.tight_results, learn.trusted_zone, learn.solve_step, learn.tight_cells = saved
    assert abs(max(built.values()) - sweep.train_examples(row, row["n_round"], row["n_late"])) < 1e-6
    assert built[1] != built[None]  # the two window states build different sets


def test_projection_printed_and_over_budget_refused():
    calls = []
    real = sweep.run_sweep
    sweep.run_sweep = lambda *a, **k: calls.append(a)
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                sweep.main(["--budget", "10"])
                raise AssertionError("not refused")
            except SystemExit as e:
                assert e.code == 2
        text = out.getvalue()
        assert "projected total" in text and "refusing" in text and "n_late" in text
        assert not calls
        with contextlib.redirect_stdout(io.StringIO()), tempfile.TemporaryDirectory() as root:
            sweep.main(["--budget", "10", "--force", "--root", root])
        assert len(calls) == 1
    finally:
        sweep.run_sweep = real


def fake_bench(win, ranking):
    halves = {h: {"metrics": {"win": [win, 0, 1], "ranking.contested": [ranking, 0, 1]}} for h in ("held_out", "train")}
    return {"sets": {"tight": {"halves": halves}}}


def test_below_floor():
    assert sweep.below_floor(fake_bench(0.3, 0.8)) == []
    assert sweep.below_floor(fake_bench(0.184, 0.744)) == []  # at the floor is not below
    assert len(sweep.below_floor(fake_bench(0.1, 0.8))) == 2  # win, both halves
    b = fake_bench(0.3, 0.8)
    b["sets"]["tight"]["halves"]["train"]["metrics"]["ranking.contested"][0] = 0.70
    assert sweep.below_floor(b) == ["train ranking.contested 0.700 < random 0.701"]


class AntiHeuristic:
    """An evaluator that prefers what the heuristic thinks worst (search
    passes it the heuristic's estimate): deliberately worse than random."""

    wants_heuristic = True

    def __call__(self, batch):
        return 2 - np.asarray(batch["heuristic"], np.float32)


def test_guard_stops_a_config_worse_than_random():
    """Dry run through the CLI: the first config is benched with an inverted
    heuristic in place of its net, so it ranks below the random evaluator;
    the sweep writes the table, says why and exits 3 without training the
    second config. `--no-guard` is refused without `--tiny` before anything
    runs."""
    real_load, real_rows, real_rounds, real_learn = bench.load_evaluator, sweep.tiny_rows, sweep.TINY_ROUNDS, learn.learn
    learned = []

    def inverted(spec):
        anti = AntiHeuristic()
        return bench.Evaluator(spec, anti, real_load(spec).features, anti)

    def counting(cfg, **k):
        learned.append(cfg["name"])
        return real_learn(cfg, **k)

    for argv in (["--no-guard"], ["--no-guard", "--force"]):  # never on a real sweep
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                sweep.main(argv)
                raise AssertionError("--no-guard accepted without --tiny")
            except SystemExit as e:
                assert e.code == 2
        assert "--no-guard is only for --tiny" in out.getvalue() and "projected" not in out.getvalue()
    bench.load_evaluator = inverted
    with b4_plan():
        rows = [r for r in real_rows() if r["name"] in ("score-s0", "hp-s0")]
    sweep.tiny_rows = lambda: [dict(r, rounds=(0, 0)) for r in rows]
    learn.learn = counting
    try:
        with tempfile.TemporaryDirectory() as root:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                try:
                    sweep.main(["--tiny", "--root", root])
                    raise AssertionError("not stopped")
                except SystemExit as e:
                    assert e.code == 3
            assert learned == ["score-s0"]
            assert "random-floor guard" in out.getvalue() and "< random" in out.getvalue()
            tables = [f for f in os.listdir(registry.runs_dir(root)) if f.startswith("sweep-")]
            assert len(tables) == 1
            assert "| score-s0 |" in open(os.path.join(registry.runs_dir(root), tables[0]), encoding="utf-8").read()
    finally:
        bench.load_evaluator, sweep.tiny_rows, sweep.TINY_ROUNDS, learn.learn = real_load, real_rows, real_rounds, real_learn


def test_tiny_dry_run_writes_runs_and_table():
    """A config and its branch twin: the twin reuses round 0 (no second
    round-0 run), every other round is a run up to the tiny maximum (tiny
    nets never clear the gate), the last rounds are benched, and the table
    has both runs, the per-config mean over seeds and every round's win
    rate against the heuristic's."""
    with b4_plan():
        rows = [r for r in sweep.tiny_rows() if r["name"] in ("score-s0", "score+branch-s0")]
    last = sweep.TINY_ROUNDS[1]
    with tempfile.TemporaryDirectory() as root:
        ids, path = sweep.run_sweep(rows, root, quick=True, log=lambda *_: None, guard=False)  # tiny nets
        assert len(ids) == 2
        runs = registry.runs_dir(root)
        folders = [f for f in os.listdir(runs) if os.path.isdir(os.path.join(runs, f))]
        assert len(folders) == (1 + last) + last
        assert not any("-score+branch-s0-r0-" in f for f in folders)
        for i in ids:
            assert f"-r{last}-" in i  # the last round is benched
            assert os.path.exists(os.path.join(runs, i, "bench.json"))
        twin_r1 = [f for f in folders if "-score+branch-s0-r1-" in f][0]
        with open(os.path.join(runs, twin_r1, "round.json"), encoding="utf-8") as f:
            assert "-score-s0-r0-" in json.load(f)["parent_run"]
        with open(os.path.join(runs, "index.csv"), encoding="utf-8") as f:
            assert len(f.read().strip().splitlines()) == 1 + len(folders)
        text = open(path, encoding="utf-8").read()
        assert all(i in text for i in ids) and "## tight / held_out" in text
        assert "## mean over seeds" in text and "| score+branch |" in text
        assert "## rounds" in text and all(f"| score-s0 | {k} |" in text for k in range(1, last + 1))
        assert "| score-s0 | 0 |" not in text


def test_fast_first_order():
    rows, _, _ = sweep.projection()
    fast = sweep.fast_first(rows)
    assert sorted(r["name"] for r in fast) == sorted(r["name"] for r in rows)
    keys = [r["minutes"] for r in fast]
    assert keys == sorted(keys)


def test_run_times_compare_across_timezones():
    """Colab stamps runs in UTC, the laptop in its local time: run.json's
    `created` carries its UTC offset, and `created` orders runs by the real
    moment (a Colab run at 09:00 UTC is newer than a laptop run at 11:00
    +05:00). Old stamps without an offset are read as local time."""
    with tempfile.TemporaryDirectory() as root:
        run = registry.Run.create("t", {"name": "t"}, [], root=root)
        stamp = run._read("run.json")["created"]
        assert datetime.datetime.fromisoformat(stamp).utcoffset() is not None, stamp

        def fake(stamp):
            r = registry.Run.create("f", {"name": "f"}, [], root=root)
            info = r._read("run.json")
            r._write("run.json", {**info, "created": stamp})
            return r
        laptop, colab = fake("2026-10-25T11:00:00+05:00"), fake("2026-10-25T09:00:00+00:00")
        assert sweep.created(colab) > sweep.created(laptop)
        old = fake("2026-10-25T11:00:00")
        assert sweep.created(old) == datetime.datetime(2026, 10, 25, 11).astimezone()


def test_table_never_overwrites_an_earlier_sweep():
    """A second sweep on the same day writes a new table (B4's crashed run
    overwrote the committed A4 table, both dated 2026-10-25)."""
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(registry.runs_dir(root))
        first = sweep.table_path(root)
        open(first, "w").close()
        second = sweep.table_path(root)
        assert second != first and not os.path.exists(second)
        assert os.path.dirname(second) == os.path.dirname(first)


def test_table_written_after_each_config():
    """An interrupted sweep still leaves the table of the configs it finished."""
    with b4_plan():
        rows = [dict(r, rounds=(0, 0)) for r in sweep.tiny_rows() if r["name"] in ("score-s0", "hp-s0")]
    real, calls = sweep.learn.learn, []

    def learn_then_stop(cfg, **k):
        calls.append(cfg["name"])
        if len(calls) > 1:
            raise KeyboardInterrupt
        return real(cfg, **k)

    sweep.learn.learn = learn_then_stop
    try:
        with tempfile.TemporaryDirectory() as root:
            try:
                sweep.run_sweep(rows, root, quick=True, log=lambda *_: None, guard=False)
                raise AssertionError("not interrupted")
            except KeyboardInterrupt:
                pass
            tables = [f for f in os.listdir(registry.runs_dir(root)) if f.startswith("sweep-")]
            assert len(tables) == 1
            text = open(os.path.join(registry.runs_dir(root), tables[0]), encoding="utf-8").read()
            assert "| score-s0 |" in text and "| hp-s0 |" not in text
    finally:
        sweep.learn.learn = real


def test_only_runs_the_named_rows_at_the_plans_sizes():
    """Colab runs one plan row per session: --only runs just those rows, at
    the night plan's sizes (not re-fitted), without the budget refusal;
    an unknown name is refused."""
    calls = []
    real = sweep.run_sweep
    sweep.run_sweep = lambda rows, *a, **k: calls.append(rows)
    try:
        with contextlib.redirect_stdout(io.StringIO()), b4_plan(), tempfile.TemporaryDirectory() as root:
            sweep.main(["--only", "hp-s0", "score+branch-s1", "--budget", "1", "--root", root])
            try:
                sweep.main(["--only", "nope"])
                raise AssertionError("not refused")
            except SystemExit as e:
                assert e.code == 2
    finally:
        sweep.run_sweep = real
    assert len(calls) == 1
    with b4_plan():
        n_round, n_late = sweep.fit_sizes()
    assert [r["name"] for r in calls[0]] == ["hp-s0", "score+branch-s1"]
    assert all(r["n_round"] == n_round and r["n_late"] == n_late and r["n"] == sweep.FULL_N for r in calls[0])


def fake_run(root, cfg, rnd, bench=None, created=None):
    """A registry run folder like learn.learn writes for round `rnd`."""
    run = registry.Run.create(f"{cfg['name']}-r{rnd}", cfg, [], root=root)
    run._write("round.json", {"round": rnd})
    open(run.model_path, "wb").close()
    if bench is not None:
        run.save_bench(bench)
    if created is not None:
        info = run._read("run.json")
        run._write("run.json", {**info, "created": created})
    return run


def tiny_cfg(name):
    with b4_plan():
        r = next(r for r in sweep.tiny_rows() if r["name"] == name)
    return sweep.row_config(r)


def test_round_0_reused_from_the_registry_across_processes():
    """A later process (another Colab session) reuses a finished round-0 run
    of the same target and round-0 inputs found in the registry; other
    inputs or the other target train their own."""
    with tempfile.TemporaryDirectory() as root:
        first = fake_run(root, tiny_cfg("score-s0"), 0)
        found = sweep.find_round0(tiny_cfg("score+branch-s1"), root)
        assert found is not None and found.id == first.id
        assert sweep.find_round0(tiny_cfg("hp-s0"), root) is None
        assert sweep.find_round0({**tiny_cfg("score-s1"), "n_train": 3}, root) is None
        assert sweep.find_round0({**tiny_cfg("score-s1"), "setups": "fixed"}, root) is None
        given = []

        def fake_learn(cfg, round0=None, **k):
            given.append(None if round0 is None else round0.id)

            class R:
                id = cfg["name"] + "-last"

                def _read(self, _):
                    return fake_bench(0.5, 0.9)
            return [round0 or R()] + [R()] * sweep.ROUNDS
        real_learn, real_report = sweep.learn.learn, sweep.report
        sweep.learn.learn, sweep.report = fake_learn, lambda *a: ""
        try:
            with b4_plan():
                rows = [r for r in sweep.tiny_rows() if r["name"] in ("score+branch-s0", "hp-s0")]
            sweep.run_sweep(rows, root, log=lambda *_: None)
        finally:
            sweep.learn.learn, sweep.report = real_learn, real_report
        assert given == [first.id, None]


def test_round0_not_reused():
    """Score configs record the curriculum's label settings, which join the
    round-0 key: an outcome-labelled round-0 run (Amendment 3, no label
    settings) and curriculum ones with another `exact_share`,
    `exact_leaves` or `exact_split` are not reused for a curriculum config, a matching one is, and the round-0
    pool dataset is the same for all of them."""
    cur = tiny_cfg("score-s0")
    assert cur["labels"] == "curriculum" and cur["exact_share"] == learn.EXACT_SHARE
    assert cur["exact_leaves"] is learn.EXACT_LEAVES and cur["exact_split"] == learn.EXACT_SPLIT
    assert "labels" not in tiny_cfg("hp-s0")
    outcome = {k: v for k, v in cur.items() if k not in learn.label_settings({})}
    with tempfile.TemporaryDirectory() as root:
        fake_run(root, outcome, 0)
        fake_run(root, {**cur, "exact_share": 0.5}, 0)
        fake_run(root, {**cur, "exact_leaves": not learn.EXACT_LEAVES}, 0)
        fake_run(root, {**cur, "exact_split": learn.A3_SPLIT}, 0)  # curriculum Amendment 3's split
        assert sweep.find_round0(cur, root) is None
        same = fake_run(root, cur, 0)
        assert sweep.find_round0(tiny_cfg("score-s1"), root).id == same.id
    gens = []
    real = registry.find
    registry.find = lambda gen, parent_model=None, root=None: gens.append((gen, parent_model)) or "pool"
    try:
        assert [learn.dataset(c, "train", "unused") for c in (outcome, {**cur, "exact_share": 0.5}, cur)] == ["pool"] * 3
    finally:
        registry.find = real
    assert gens[0] == gens[1] == gens[2]


def test_table_from_the_registry():
    """--table: the newest finished final-round run (benched, any round
    from 1: the stop rule's) of each plan row under the root; unfinished
    runs (no bench) are skipped, missing rows listed."""
    got = []
    real = sweep.report
    sweep.report = lambda rows, ids, timings, root: got.append(([r["name"] for r in rows], ids, timings)) or "x"
    try:
        with tempfile.TemporaryDirectory() as root:
            cfg = tiny_cfg("score-s0")
            fake_run(root, cfg, 9, fake_bench(0.4, 0.8), created="2026-10-26T01:00:00")
            newest = fake_run(root, cfg, 7, fake_bench(0.5, 0.8), created="2026-10-26T02:00:00")
            fake_run(root, cfg, 8, None, created="2026-10-26T03:00:00")  # unfinished
            fake_run(root, cfg, 0, fake_bench(0.5, 0.8))  # round 0 is never a final round
            hp = fake_run(root, tiny_cfg("hp+branch-s1"), 6, fake_bench(0.5, 0.8))
            with b4_plan():
                path, missing = sweep.write_table(root)
                plan_names = {r["name"] for r in sweep.plan()}
            assert os.path.exists(path)
    finally:
        sweep.report = real
    names, ids, timings = got[0]
    assert names == ["score-s0", "hp+branch-s1"] and ids == [newest.id, hp.id] and timings is None
    assert set(missing) == plan_names - {"score-s0", "hp+branch-s1"}


class FakeProc:
    """A worker process that exits with `code` after `polls` polls."""

    def __init__(self, polls, code):
        self.left, self.code = polls, code

    def poll(self):
        if self.left > 0:
            self.left -= 1
            return None
        return self.code


def run_fake_parallel(rows, jobs, outcome, root):
    """run_parallel with fake workers: outcome[name] = (polls, exit code).
    Returns (exit code, start events [(name, running names)], tables written,
    log text)."""
    starts, tables, lines, running = [], [], [], set()

    def launch(name, root_, jobs_, extra, log_path):
        polls, code = outcome.get(name, (1, 0))
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"{name} log line\n")
        starts.append((name, set(running)))
        running.add(name)
        proc = FakeProc(polls, code)
        real_poll = proc.poll

        def poll():
            c = real_poll()
            if c is not None:
                running.discard(name)
            return c
        proc.poll = poll
        return proc

    real = sweep.write_table
    sweep.write_table = lambda root_, log=print, path=None: tables.append(path) or (path, [])
    try:
        code = sweep.run_parallel(rows, root, jobs, launch=launch, log=lines.append, poll=0)
    finally:
        sweep.write_table = real
    return code, starts, tables, "\n".join(lines)


def test_parallel_waits_for_round_0_and_caps_concurrency():
    """--jobs 2: the first row of each target (it trains the target's
    round-0 net) starts first and finishes before that target's other rows
    start; never more than 2 at once; the table is rewritten after every
    finished row."""
    with b4_plan():
        rows = sweep.projection()[0]
    outcome = {"score-s0": (5, 0), "hp-s0": (2, 0)}
    with tempfile.TemporaryDirectory() as root:
        code, starts, tables, _ = run_fake_parallel(rows, 2, outcome, root)
    assert code == 0
    names = [n for n, _ in starts]
    assert sorted(names) == sorted(r["name"] for r in rows)
    assert set(names[:2]) == {"score-s0", "hp-s0"}
    assert all(len(running) < 2 for _, running in starts)
    lead = {False: "score-s0", True: "hp-s0"}
    by = {r["name"]: r for r in rows}
    for name, running in starts:
        if name not in lead.values():
            assert lead[by[name]["hp"]] not in running and names.index(lead[by[name]["hp"]]) < names.index(name)
    assert len(tables) >= len(rows) and len(set(tables)) == 1  # one table file, rewritten


def test_parallel_rows_start_together_once_round_0_is_trained():
    """--round0 before the night: the registry has the target's round 0, so
    both seeds start at once instead of the second waiting for the first."""
    rows = sweep.projection()[0]
    with tempfile.TemporaryDirectory() as root:
        fake_run(root, sweep.row_config(rows[0]), 0)
        code, starts, _, text = run_fake_parallel(rows, 2, {"score+branch-s0": (5, 0)}, root)
    assert code == 0 and [n for n, _ in starts] == ["score+branch-s0", "score+branch-s1"] and starts[1][1] == {"score+branch-s0"}
    assert "wait" not in text
    with tempfile.TemporaryDirectory() as root:
        _, starts, _, text = run_fake_parallel(rows, 2, {"score+branch-s0": (5, 0)}, root)
    assert starts[1][1] == set() and "--round0 first" in text


def test_round0_before_the_night():
    """--round0 (tiny): trains each target's round 0 once (round 0 only)
    and exits; a second call finds it; the night's rows then reuse it."""
    with tempfile.TemporaryDirectory() as root:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sweep.main(["--tiny", "--round0", "--root", root])
            sweep.main(["--tiny", "--round0", "--root", root])
        runs = registry.runs_dir(root)
        folders = [f for f in os.listdir(runs) if os.path.isdir(os.path.join(runs, f))]
        assert len(folders) == 1 and "-score+branch-s0-r0-" in folders[0]
        assert "already trained" in out.getvalue()
        assert sweep.find_round0(sweep.row_config(sweep.tiny_rows()[1]), root).id == folders[0]


def test_parallel_guard_stop_and_crash():
    """A worker stopped by the guard (exit 3): no new rows start, the running
    one is waited for, the table is written, and the sweep exits 3 naming
    the row with its log's last lines; a crash exits 1."""
    with b4_plan():
        rows = sweep.projection()[0]
    with tempfile.TemporaryDirectory() as root:
        code, starts, tables, text = run_fake_parallel(rows, 2, {"hp-s0": (1, 3), "score-s0": (4, 0)}, root)
    assert code == 3
    assert [n for n, _ in starts] == ["score-s0", "hp-s0"]
    assert tables and "hp-s0" in text and "guard" in text and "hp-s0 log line" in text
    with tempfile.TemporaryDirectory() as root:
        code, starts, _, text = run_fake_parallel(rows, 2, {"score-s0": (1, 1), "hp-s0": (3, 0)}, root)
    assert code == 1 and len(starts) == 2 and "crash" in text


def test_parallel_projection():
    """The night's wall time with --jobs: rows list-scheduled N at a time,
    each slowed by sharing cores (no waiting: round 0 is trained before the
    night); jobs=1 is the plain sum, jobs=2 is shorter, so the sizes grow
    when time binds them (at the tests' free memory since Amendment 1:
    training no longer holds its examples in RAM); a target's other
    rows wait for its first when round 0 isn't trained."""
    n_round, n_late = sweep.fit_sizes()
    rows, _, total = sweep.projection(n_round, n_late)
    assert abs(total - sum(r["minutes"] for r in rows)) < 1e-6
    assert sweep.projection(n_round, n_late, jobs=2)[2] < total
    nr2, nl2 = sweep.fit_sizes(jobs=2)  # time-bound: 2 runs at once finish sooner
    assert nr2 >= n_round and nl2 >= n_late and (nr2, nl2) != (n_round, n_late)
    n_round, n_late = sweep.fit_sizes(free=1000.0)
    nr2, nl2 = sweep.fit_sizes(jobs=2, free=1000.0)  # time-bound: 2 at once fit more
    assert nr2 >= n_round and nl2 >= n_late and (nr2, nl2) != (n_round, n_late)
    assert sweep.projection(nr2, nl2, jobs=2, free=1000.0)[2] <= sweep.NIGHT_MIN
    # hand-made: A (score, first, 10 min) blocks B (score, 1 min); C and D (hp) run beside A
    hand = [{"name": "A", "hp": False, "minutes": 10.0}, {"name": "B", "hp": False, "minutes": 1.0},
            {"name": "C", "hp": True, "minutes": 1.0}, {"name": "D", "hp": True, "minutes": 1.0}]
    f = sweep.slowdown(2)
    assert abs(sweep.makespan(hand, 2) - 11 * f) < 1e-9
    assert abs(sweep.makespan(hand, 1) - 13.0) < 1e-9
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        sweep.main(["--plan", "--jobs", "2"])
    assert "wall time" in out.getvalue() and f"n_late {sweep.fit_sizes(jobs=2)[1]}" in out.getvalue()
    assert "worst case" in out.getvalue() and "largest training set" in out.getvalue()
    assert "--round0" in out.getvalue()


def test_sizing_free_memory():
    """Runs are sized to the memory free at plan time less MEM_MARGIN,
    split across jobs: 12 GB free, margin 2, --jobs 2 → 5 GB per run, and
    each run's rounds (self-play and largest training set) fit it under the
    peak model (one more game per group would not, unless time binds); 4 GB
    free → 1 GB per run, below the smallest round worth running, so the
    plan refuses to start (--force overrides), and so does --round0 when it
    doesn't fit (3.5 GB free); the plan prints the free memory, margin and budget, and
    the solve step's threads fit the budget."""
    margin, sweep.MEM_MARGIN = sweep.MEM_MARGIN, 2.0  # the spec's example margin
    assert abs(sweep.run_budget_gb(2, 12.0) - 5.0) < 1e-9 and abs(sweep.run_budget_gb(2, 4.0) - 1.0) < 1e-9
    rows, _, _ = sweep.projection(jobs=2, free=12.0)
    nr, nl = rows[0]["n_round"], rows[0]["n_late"]
    assert all(sweep.round_peak_gb(nl, sweep.train_examples(r, nr, nl)) <= 5.0 for r in rows)
    assert (any(sweep.round_peak_gb(nl + 1, sweep.train_examples(r, nr, nl + 1)) > 5.0 for r in rows)
            or sweep.projection(nr, nl + 1, jobs=2, free=12.0)[2] > sweep.NIGHT_MIN
            or any(sweep.round_min(r, nl + 1) > sweep.ROUND_MIN for r in rows))
    assert rows[0]["solve_threads"] * 0.75 + sweep.BASE_GB <= 5.0 or rows[0]["solve_threads"] == 1
    assert sweep.fit_sizes(jobs=2, free=4.0)[0] < sweep.MIN_N_ROUND
    calls, real = [], sweep.run_sweep
    sweep.run_sweep = lambda *a, **k: calls.append(a)
    try:
        with tempfile.TemporaryDirectory() as root:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                try:
                    sweep.main(["--free", "4", "--root", root])
                    raise AssertionError("not refused")
                except SystemExit as e:
                    assert e.code == 2
            assert "smallest worth running" in out.getvalue() and not calls
            with contextlib.redirect_stdout(io.StringIO()):
                sweep.main(["--free", "4", "--force", "--root", root])
            assert len(calls) == 1
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sweep.main(["--plan", "--jobs", "2", "--free", "12"])
        assert "12.0 GB free, less 2 GB margin, / 2 job(s) = 5.0 GB per run" in out.getvalue()
        # --round0 runs alone: refused when it doesn't fit
        assert sweep.round0_peak_gb() > sweep.run_budget_gb(1, 3.5)
        with tempfile.TemporaryDirectory() as root:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                try:
                    sweep.main(["--round0", "--free", "3.5", "--root", root])
                    raise AssertionError("not refused")
                except SystemExit as e:
                    assert e.code == 2
            assert "round 0 peaks" in out.getvalue()
    finally:
        sweep.run_sweep = real
        sweep.MEM_MARGIN = margin


def test_sizing_disk():
    """The night's disk (curriculum Amendment 1): the caches it writes
    (worst case, ROUNDS_MAX rounds per run at CACHE_BYTES per example, less
    what eviction frees: the cache folder grows at most to CACHE_CAP), each
    job's exact-example temporary cache, the training
    database's room to its cap, plus DISK_MARGIN. Below it the plan
    refuses to start (--force overrides); --plan prints it."""
    import puzzles
    rows, _, _ = sweep.projection(jobs=1, free=14.0)
    with tempfile.TemporaryDirectory() as root:
        need = sweep.disk_need_gb(rows, 1, root)
        night = sum(sweep.ROUNDS_MAX * sweep.round_examples(r, r["n_late"]) for r in rows) * sweep.CACHE_BYTES / 1e9
        want = (min(night, registry.CACHE_CAP / 1e9) + sweep.EXACT_EXAMPLES * sweep.CACHE_BYTES / 1e9
                + puzzles.MAX_GB + sweep.DISK_MARGIN)
        assert abs(need - want) < 1e-6, (need, want)
        assert sweep.disk_need_gb(rows, 2, root) > need
        calls, real, real_free = [], sweep.run_sweep, sweep.free_disk_gb
        sweep.run_sweep = lambda *a, **k: calls.append(a)
        try:
            sweep.free_disk_gb = lambda root: need - 0.5
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                try:
                    sweep.main(["--free", "14", "--root", root])
                    raise AssertionError("not refused")
                except SystemExit as e:
                    assert e.code == 2
            assert "disk" in out.getvalue() and not calls
            with contextlib.redirect_stdout(io.StringIO()):
                sweep.main(["--free", "14", "--force", "--root", root])
            assert len(calls) == 1
            sweep.free_disk_gb = lambda root: need + 0.5
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                sweep.main(["--free", "14", "--root", root])
            assert len(calls) == 2
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                sweep.main(["--plan", "--free", "14", "--root", root])
            assert "disk:" in out.getvalue()
        finally:
            sweep.run_sweep, sweep.free_disk_gb = real, real_free


def test_peak_model_matches():
    """The peak model against real runs at two sizes after Amendment 1
    (scripts/memprobe.py, scripts/tests/data/memprobe.json): every round's
    modelled peak (`round_peak_gb`: its fixed phases, the next round's
    self-play, its training) is never below its measured peak outside the
    solve step, and within 10% of the largest round measured at the same
    size and self-play (repeats at one size differ by up to 18%); every
    self-play call stays under `play_peak_gb` (the largest within 10%); every
    training phase under `peak_gb` (rounds >= 1 within 10%; round 0 trains
    one part, well below); the solve step under BASE_GB plus
    puzzles.THREAD_BYTES per thread."""
    import puzzles
    with open(os.path.join(os.path.dirname(__file__), "data", "memprobe.json"), encoding="utf-8") as f:
        runs = json.load(f)["runs"]
    assert len({r["n_round"] for r in runs}) == 2
    for run in runs:
        for r in run["rounds"]:
            model = sweep.round_peak_gb(r["next_n"] or 0, r["examples"] - sweep.EXACT_EXAMPLES)
            same = max(x["peak_gb"] for x in run["rounds"] if x["next_n"] == r["next_n"])
            assert r["peak_gb"] <= model <= 1.1 * same, (run["n_round"], r, model)
            train = sweep.peak_gb(r["examples"] - sweep.EXACT_EXAMPLES)
            assert r["train_gb"] <= train and (r["round"] == 0 or train <= 1.1 * r["train_gb"]), (r, train)
            assert r["solve_gb"] <= sweep.BASE_GB + run["threads"] * puzzles.THREAD_BYTES / 1e9, r
        play = sweep.play_peak_gb(run["n_round"])
        assert all(c["peak_gb"] <= play for c in run["selfplay"])
        assert play <= 1.1 * max(c["peak_gb"] for c in run["selfplay"]), (run["n_round"], play)


def test_parallel_dry_run_matches_sequential():
    """The plan's two seeds, tiny (the second reuses the first's round 0),
    run as worker processes with --jobs 2 give the same runs as one process
    running them in turn: equal val_mse and bench columns per run in
    runs/index.csv. The sweep process writes plan.json and sweep.log for
    the watcher, ending with the table."""
    import csv

    def index(root):
        with open(os.path.join(registry.runs_dir(root), "index.csv"), encoding="utf-8") as f:
            return {r["run"].rsplit("-", 1)[0]: {k: v for k, v in r.items() if k not in ("run", "commit")}
                    for r in csv.DictReader(f)}
    base = ["--tiny", "--no-guard", "--only", "score+branch-s0", "score+branch-s1"]
    with tempfile.TemporaryDirectory() as par, tempfile.TemporaryDirectory() as seq:
        with contextlib.redirect_stdout(io.StringIO()):
            sweep.main(base + ["--root", par, "--jobs", "2"])
            sweep.main(base + ["--root", seq])
        a, b = index(par), index(seq)
        assert os.path.exists(os.path.join(par, "logs", "score+branch-s1.log"))
        with open(os.path.join(par, "logs", "plan.json"), encoding="utf-8") as f:
            plan = json.load(f)
        assert plan["jobs"] == 2 and set(plan["rows"]) == {"score+branch-s0", "score+branch-s1"}
        assert len(plan["rows"]["score+branch-s0"]["minutes_by_round"]) == sweep.TINY_ROUNDS[1] + 1
        log = open(os.path.join(par, "logs", "sweep.log"), encoding="utf-8").read().splitlines()
        assert any(line.split(" ", 1)[1] == "started score+branch-s0 (log: " + os.path.join(par, "logs", "score+branch-s0.log") + ")"
                   for line in log)
        assert log[-1].split(" ", 1)[1].startswith("sweep finished: table ")
        datetime.datetime.fromisoformat(log[-1].split(" ", 1)[0])
    assert a == b and len(a) == 1 + 2 * sweep.TINY_ROUNDS[1], (a, b)


def test_cache_dir_from_the_environment():
    """STS_CACHE_DIR puts feature caches elsewhere (Colab: local disk while
    the registry is on Drive)."""
    old = os.environ.pop("STS_CACHE_DIR", None)
    try:
        assert registry.cache_dir("r") == os.path.join("r", "cache")
        os.environ["STS_CACHE_DIR"] = "elsewhere"
        assert registry.cache_dir("r") == "elsewhere"
    finally:
        os.environ.pop("STS_CACHE_DIR", None)
        if old is not None:
            os.environ["STS_CACHE_DIR"] = old


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
