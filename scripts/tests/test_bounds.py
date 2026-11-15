"""Tests for solver bounds (docs/specs/solver-bounds.md).

    python scripts/tests/test_bounds.py
"""

import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np  # noqa: E402
import torch  # noqa: E402

import bench  # noqa: E402
import bench_decisions  # noqa: E402
import learn  # noqa: E402
import sts  # noqa: E402
import train  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
EPS = 1e-9


def puzzle_states(every=10):
    rows = [r for h in bench.load_puzzles()["halves"].values() for r in h][::every]
    return [bench_decisions.replay(r) for r in rows]


def test_upper_bound_holds():
    """Every exactly solved state's value is at most its upper bound: the
    bench puzzles, their options' finished and unfinished afterstates, and
    rows of the bench games' solved tails; a finished combat's bound is its
    score; no state can heal (no healing content yet)."""
    checked = 0
    for c in puzzle_states():
        r = sts.solve(c, max_nodes=1_000_000)
        if r is None:
            continue
        assert max(o[1] for o in r["options"]) <= c.upper_bound() + EPS
        assert not c.can_heal()
        for (_, _, outs), (_, v) in zip(c.options(10**7), r["options"]):
            for _, x in outs:
                if x.is_over():
                    assert abs(x.upper_bound() - x.score()) < EPS
            assert v <= max(x.upper_bound() for _, x in outs) + EPS
        checked += 1
    db = sts.SolvedDb(os.path.join(ROOT, "db", "solved.sqlite"))
    ids = db.decision_ids()  # this build's rules version only: empty after a fingerprint change
    n = min(2000, len(ids))
    rows = db.fetch([int(i) for i in np.random.default_rng(1).choice(ids, n, replace=False)]) if n else []
    for code, value, opts in rows:
        assert value <= sts.Combat.decode(code).upper_bound() + EPS
    assert checked > 100 and len(rows) == n


def test_heal_left_exhaustive():
    """`Effect::heals` lists every Effect variant with no catch-all arm."""
    src = open(os.path.join(ROOT, "engine", "src", "bound.rs"), encoding="utf-8").read()
    body = src[src.index("pub fn heals"):src.index("/// Whether playing")]
    assert "_ =>" not in body and "_=>" not in body
    effects = open(os.path.join(ROOT, "engine", "src", "effects.rs"), encoding="utf-8").read()
    enum = effects[effects.index("pub enum Effect {"):]
    enum = enum[:enum.index("\n}")]
    variants = set(re.findall(r"^\s{4}([A-Z]\w*)", enum, re.M))
    assert variants and all(f"Effect::{v}" in body for v in variants), variants - set(re.findall(r"Effect::(\w+)", body))


def test_bounds_sound():
    """On puzzles both solves finish, the bounded solve's decision value and
    exact options equal the exact solve's; each bounded option's exact value
    is at most its bound, the bound at most the decision's value."""
    bounded = 0
    for c in puzzle_states():
        a = sts.solve(c, max_nodes=1_000_000)
        b = sts.solve(c, max_nodes=1_000_000, bounds=True)
        if a is None or b is None:
            continue
        assert not any(a["bounded"]) and len(b["bounded"]) == len(b["options"])
        va, vb = max(o[1] for o in a["options"]), max(o[1] for o in b["options"])
        assert abs(va - vb) < EPS
        for oa, ob, f in zip(a["options"], b["options"], b["bounded"]):
            assert list(oa[0]) == list(ob[0])
            if f:
                assert oa[1] <= ob[1] + EPS and ob[1] <= vb + EPS
                bounded += 1
            else:
                assert abs(oa[1] - ob[1]) < EPS
    assert bounded > 0


def test_bounds_store():
    """A bounded root row keeps its flags in the database (fetch, lookup);
    an unbounded solve of that root solves it again, all options exact; a
    bounded solve takes the stored row."""
    c = next(c for c in puzzle_states() if any((sts.solve(c, max_nodes=200_000, bounds=True) or {"bounded": []})["bounded"]))
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, "t.sqlite")
        db = sts.SolvedDb(path)
        r = sts.solve(c, max_nodes=200_000, bounds=True, store=sts.SolveStore(min_nodes=0, db=db))
        del db
        db = sts.SolvedDb(path)
        found = db.lookup([c.encode()])[0]
        assert found is not None and found[2] == r["bounded"] and any(found[2])
        (code, value, opts), = [row for row in db.fetch(db.decision_ids().tolist()) if row[0] == c.encode()]
        assert [o[2] for o in opts] == r["bounded"] and all(len(o) == 3 for o in opts)
        again = sts.solve(c, max_nodes=1_000_000, store=sts.SolveStore(min_nodes=0, db=db))
        assert again["nodes"] > 0 and not any(again["bounded"])
        hit = sts.solve(c, max_nodes=1_000_000, bounds=True, store=sts.SolveStore(min_nodes=0, db=db))
        assert hit["nodes"] == 0 and hit["bounded"] == r["bounded"]
        del db
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_dull_bounded():
    assert learn.dull([1.0, 1.0, 0.5], [False, False, True])
    assert not learn.dull([1.0, 1.0, 0.5], [False, False, True], [False, True, False])


def test_ranking_bounded():
    """(exact, bounded) pairs only when the exact value is at or above the
    bound; (bounded, bounded) never; the one-sided value term is 0 under
    the bound and grows above it."""
    def loss(rank, bounded, y):
        n = len(rank)
        return float(train.ranking_loss(torch.tensor(y), torch.zeros(n, dtype=torch.long), torch.arange(n),
                                         torch.ones(n), torch.zeros(n), torch.tensor(rank),
                                         torch.tensor(bounded, dtype=torch.int8)))
    # exact 1.0 vs bounded 1.0 (tie): paired, out of order costs
    assert loss([1.0, 1.0], [0, 1], [0.5, 0.9]) > 0 and loss([1.0, 1.0], [0, 1], [0.9, 0.5]) == 0
    # exact 0.8 vs bounded 1.0: unknown order, not paired
    assert loss([0.8, 1.0], [0, 1], [0.5, 0.9]) == 0
    # two bounded: not paired; a bounded option is never the better one
    assert loss([1.0, 0.5], [1, 1], [0.1, 0.9]) == 0 and loss([1.0, 0.5], [1, 0], [0.1, 0.9]) == 0
    # exact pairs as before
    assert loss([1.0, 0.5], [0, 0], [0.1, 0.9]) > 0
    t = torch.tensor([1.0, 1.0, 1.0])
    v = train.value_loss(torch.tensor([0.5, 1.5, 1.5]), t, None, False, torch.tensor([1, 1, 0], dtype=torch.int8))
    assert abs(float(v) - (0 + 0.25 + 0.25) / 3) < 1e-6


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
