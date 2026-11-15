"""Tests for the position finder and puzzle tools (scripts/puzzles.py). Run
with `python scripts/tests/test_puzzles.py` or with pytest."""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench_decisions  # noqa: E402
import bench_sets  # noqa: E402
import puzzles  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402

# Small budgets keep the tests quick; the walk's rules don't depend on it.
TEST_NODES = 20_000
TINY_RUN = {"name": "smoke", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 21, "val_seed": 22,
            "search": {"limit": selfplay.LIMIT}, "seed": 0, "switches": {}, "rounds": {"n": 0}}
_GAMES = []


def games(n=60):
    """(identity, states, actions) of search + heuristic games on the first
    n tight train specs."""
    if not _GAMES:
        specs = bench_sets.load_set("tight")["train"][:n]
        for i, (s, r) in enumerate(zip(specs, puzzles.play(specs))):
            identity = {"spec": i, **{k: s[k] for k in ("character", "encounter", "deck", "hp", "seed")}}
            _GAMES.append((identity, r["states"], r["actions"]))
    return _GAMES


def db_path(d, name="solved.sqlite"):
    return os.path.join(d, name)


def decisions(states):
    """Indices of decisions with at least 2 options."""
    return [k for k, c in enumerate(states) if len(c.options(puzzles.LIMIT)) >= 2]


def tree_hashes(root):
    """{relative path: sha256} of every file under root."""
    out = {}
    for d, _, names in os.walk(root):
        for n in names:
            p = os.path.join(d, n)
            with open(p, "rb") as f:
                out[os.path.relpath(p, root)] = hashlib.sha256(f.read()).hexdigest()
    return out


def test_finder_walk_back():
    """Puzzles are contiguous from the last decision backward (single-option
    decisions skipped) and stop at the first unsolvable one; a no-death
    record is refused."""
    stopped = skipped = 0
    with tempfile.TemporaryDirectory() as d:
        db = sts.SolvedDb(db_path(d))
        for identity, states, actions in games()[:30]:
            found = puzzles.walk(states, actions, db, "test", puzzles.spec_key(identity), max_nodes=TEST_NODES)
            dec = decisions(states)
            steps = [p["step"] for p in found]
            assert steps == dec[len(dec) - len(steps):], (steps, dec)
            if len(steps) < len(dec):
                stopped += 1
                assert sts.solve(states[dec[len(dec) - len(steps) - 1]], max_nodes=TEST_NODES) is None
            if steps:
                skipped += sum(1 for k in range(steps[0], len(states)) if k not in dec)
            last_turn = states[-1].turn()
            for p in found:
                c = states[p["step"]]
                assert p["actions"] == "|".join(puzzles.registry.encode_action(a) for a in actions[:p["step"]])
                assert p["horizon"] == last_turn - c.turn() >= 0
                vals = sorted((o[1] for o in p["options"]), reverse=True)
                assert len(vals) >= 2 and abs(p["gap"] - (vals[0] - vals[1])) < 1e-12
    assert stopped > 0 and skipped > 0, (stopped, skipped)
    try:
        puzzles.record_states({"no_death": True, "character": "ironclad", "encounter": "cultist",
                               "deck": selfplay.STARTER, "hp": None, "seed": 1, "actions": [],
                               "outcome": {"score": 0, "won": False, "hp_start": 80, "hp_end": 0}})
    except ValueError:
        pass
    else:
        raise AssertionError("a no-death record must be refused")


def test_db_positions():
    """Walking one game twice adds no duplicate states rows, and positions
    rows only for decisions not yet recorded for that source."""
    def tail(states, max_nodes):
        n = 0
        for k in reversed(decisions(states)):
            if sts.solve(states[k], max_nodes=max_nodes) is None:
                break
            n += 1
        return n
    identity, states, actions = next(g for g in games() if 0 < tail(g[1], 2_000) < tail(g[1], TEST_NODES))
    spec = puzzles.spec_key(identity)

    def no_duplicates(p):
        # A later walk may add rows (its budget-out solve reaches further
        # through hits and keeps the subtrees it finishes), never duplicates.
        con = sqlite3.connect(p)
        try:
            n, distinct = con.execute("SELECT count(*), count(DISTINCT version || '/' || hex(state)) FROM states").fetchone()
        finally:
            con.close()
        assert n == distinct > 0
    with tempfile.TemporaryDirectory() as d:
        p = db_path(d)
        small = puzzles.walk(states, actions, sts.SolvedDb(p), "a", spec, max_nodes=2_000)
        db = sts.SolvedDb(p)
        first = db.positions("a")
        assert len(first) == len(small) > 0
        again = puzzles.walk(states, actions, db, "a", spec, max_nodes=2_000)
        assert [x["options"] for x in again] == [x["options"] for x in small]
        db = sts.SolvedDb(p)
        assert db.positions("a") == first
        no_duplicates(p)
        big = puzzles.walk(states, actions, db, "a", spec, max_nodes=TEST_NODES)
        assert len(big) > len(small)
        db = sts.SolvedDb(p)
        got = db.positions("a")
        assert got[:len(first)] == first and sorted(r["step"] for r in got) == [x["step"] for x in big]
        puzzles.walk(states, actions, db, "b", spec, max_nodes=TEST_NODES)
        db = sts.SolvedDb(p)
        assert sorted(r["state"] for r in db.positions("b")) == sorted(r["state"] for r in got)
        no_duplicates(p)


def tied(r):
    """Whether a position's options all have the same exact value."""
    values = [o[1] for o in r["options"]]
    return max(values) - min(values) <= 1e-9


def test_db_compact():
    """`db --compact` (exact-solver Amendment 1): full rows no puzzle points
    at whose options are all tied become value-only rows; lookups agree
    before and after; a puzzle keeps its full row."""
    with tempfile.TemporaryDirectory() as d:
        p = db_path(d)
        for identity, states, actions in games():
            puzzles.walk(states, actions, sts.SolvedDb(p), "a", puzzles.spec_key(identity), max_nodes=TEST_NODES)
            rows = sts.SolvedDb(p).positions("a")
            if sum(map(tied, rows)) >= 2 and not all(map(tied, rows)):
                break
        else:
            raise AssertionError("no games with tied and untied puzzles")
        keep = next(r["state"] for r in rows if tied(r))
        # Puzzles point at full rows: dropping all positions but one leaves
        # the other tied roots movable.
        con = sqlite3.connect(p)
        try:
            con.execute("DELETE FROM positions WHERE state NOT IN (SELECT id FROM states WHERE state = ?)", (keep,))
            con.commit()
        finally:
            con.close()
        states = [r["state"] for r in rows]
        before = sts.SolvedDb(p).lookup(states)
        trivial = next(v for v in sts.SolvedDb(p).stats()["versions"] if v[3])[4]
        puzzles.main(["db", "--compact", "--db", p])
        db = sts.SolvedDb(p)
        after = db.lookup(states)
        for b, a in zip(before, after):
            assert b[0] == a[0] and len(b[1]) == len(a[1])
            assert all(abs(x - y) <= 1e-9 for x, y in zip(b[1], a[1]))
        moved = len({r["state"] for r in rows if tied(r)} - {keep})
        assert next(v for v in db.stats()["versions"] if v[3])[4] == trivial + moved > trivial
        assert [r["state"] for r in db.positions("a")] == [keep]
        del db


def position_text(r):
    """A positions row as comparable text."""
    opts = [[[puzzles.registry.encode_action(a) for a in o[0]], *o[1:]] for o in r["options"]]
    return json.dumps({**r, "state": r["state"].hex(), "options": opts}, sort_keys=True)


def test_finder_threads_deterministic():
    """The finder on 50 games gives byte-identical output with 1 and 8
    threads from the same starting database (one filled by 10 games)."""
    gs = games()[:50]
    outs, positions = [], []
    with tempfile.TemporaryDirectory() as d:
        for threads in (1, 8):
            p = db_path(d, f"t{threads}.sqlite")
            puzzles.find(gs[:10], sts.SolvedDb(p), "seed", threads=1, max_nodes=TEST_NODES)
            db = sts.SolvedDb(p)
            outs.append(json.dumps(puzzles.find(gs, db, "test", threads=threads, max_nodes=TEST_NODES), sort_keys=True))
            positions.append(sorted(position_text(r) for r in sts.SolvedDb(p).positions("test")))
    assert outs[0] == outs[1]
    assert positions[0] and positions[0] == positions[1]


def test_registry_dump_is_read_only():
    """Dumping a tiny run's games into the solved-position database leaves
    every registry file (datasets, caches, runs) unchanged, and records the
    run's solved decisions under its id."""
    import learn
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as dbdir:
        [run] = learn.learn(TINY_RUN, root=root, log=lambda *_: None)
        before = tree_hashes(root)
        assert before
        n = puzzles.dump_run(run.id, db_path(dbdir), root=root, max_nodes=TEST_NODES)
        assert tree_hashes(root) == before
        assert n > 0 and len(sts.SolvedDb(db_path(dbdir)).positions(run.id)) == n


def test_registry_dump_export():
    """A tiny run's dump with --export: one jsonl line per solved decision,
    matching the database's positions for the run; db --stats runs."""
    import learn
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as dbdir:
        [run] = learn.learn(TINY_RUN, root=root, log=lambda *_: None)
        assert puzzles.main(["--run", run.id, "--export", "--db", db_path(dbdir), "--root", root,
                             "--max-nodes", str(TEST_NODES)]) == 0
        with open(os.path.join(root, "datasets", f"puzzles-{run.id}.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        got = sts.SolvedDb(db_path(dbdir)).positions(run.id)
        assert rows and len(rows) == len(got)
        assert sorted((r["dataset"], r["game"], r["step"]) for r in rows) == \
            sorted((json.loads(r["spec"])["dataset"], json.loads(r["spec"])["game"], r["step"]) for r in got)
        assert puzzles.main(["db", "--stats", "--db", db_path(dbdir)]) == 0
        assert puzzles.main(["db", "--evict", "--db", db_path(dbdir)]) == 0


def test_puzzle_set_format():
    """The bench puzzle set on a few specs per half: one puzzle per game,
    horizon >= 0, gap = best - second best, seeds from PUZZLE_SEED, and a
    rebuild from an empty database is byte-identical."""
    tight = {half: specs[:12] for half, specs in bench_sets.load_set("tight").items()}
    outs = []
    with tempfile.TemporaryDirectory() as d:
        for k in range(2):
            out = os.path.join(d, f"puzzles{k}.json")
            db = sts.SolvedDb(db_path(d, f"solved{k}.sqlite"))
            passes = puzzles.build_set(db, out, per_half=14, tight=tight, threads=4, max_nodes=TEST_NODES)
            with open(out, "rb") as f:
                outs.append(f.read())
        assert outs[0] == outs[1], "rebuild from an empty database differs"
        assert all(p >= 2 for p in passes.values()), passes  # 14 games > 12 specs: a second pass ran
        doc = json.loads(outs[0])
        assert doc["db_rows_at_start"] == 0 and doc["per_half"] == 14
        for half, rows in doc["halves"].items():
            assert len(rows) == 14
            assert len({(r["spec"], r["seed"]) for r in rows}) == 14, "one puzzle per game"
            for r in rows:
                assert r["seed"] >= puzzles.PUZZLE_SEED
                assert r["horizon"] >= 0
                values = sorted((o[1] for o in r["options"]), reverse=True)
                assert len(values) >= 2 and abs(r["gap"] - (values[0] - values[1])) < 1e-12
                assert all(len(o) == 3 and abs(o[2]["loss"] + sum(p for _, p in o[2]["wins"]) - 1) < 1e-9
                           for o in r["options"]), "distributions stored"
                c = bench_decisions.replay(r)
                assert [[bench_decisions.encode_action(a) for a in o[0]] for o in c.options(puzzles.LIMIT)] == \
                    [o[0] for o in r["options"]], "options match the replayed state's"
    print("puzzle_set_format ok")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} passed")
