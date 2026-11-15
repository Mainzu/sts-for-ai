"""Tests for the exact-only experiment (docs/specs/exact-only.md), on the
curriculum tests' fixture database.

    python scripts/tests/test_exact_only.py
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np  # noqa: E402

import exact_only  # noqa: E402
import learn  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import test_curriculum as tc  # noqa: E402

_ROOT = []


def fixture_db():
    """A registry root holding the curriculum fixture's solved database."""
    if not _ROOT:
        root = tc.fixture_root()
        raw = registry.examples(tc.dataset_ids()["score"], "effects", root=root, labels=learn.labels({}, 1))
        tc.fill_db(root, [raw.codec_bytes(i) for i in range(len(raw))], raw.distance)
        _ROOT.append(root)
    return learn.db_path(_ROOT[0])


def solved_value(x):
    """A state's exact value: its score when over, else its best option's."""
    if x.is_over():
        return x.score()
    return max(v for _, v in sts.solve(x, max_nodes=1_000_000)["options"])


def test_exact_only_arms():
    """A: the non-dull decision rows' states with their exact values (weight
    1) and their afterstates ranking-only (weight 0). B: A plus each option's
    state paused at a random event, valued at the option's exact value (the
    expectation over that event's outcomes) with weight 1."""
    path = fixture_db()
    db = sts.SolvedDb(path)
    ids = db.decision_ids().tolist()
    rows = db.fetch(ids)
    keep = [not learn.dull([o[1] for o in opts], [any(a.is_end_turn for a in o[0]) for o in opts])
            for _, _, opts in rows]
    a = exact_only.build(db, ids, False)
    dec = a.option == -1
    assert dec.sum() == sum(keep)
    assert np.allclose(a.target[dec], [v for (_, v, _), k in zip(rows, keep) if k])
    assert (a.weight[dec] == 1).all() and (a.weight[~dec] == 0).all()
    b = exact_only.build(db, ids, True)
    leaves = [x for (code, _, opts), k in zip(rows, keep) if k
              for (_, _, outs), o in zip(sts.Combat.decode(code).options(1), opts)
              for _, x in outs if not x.is_over() and not x.awaiting_action()]
    assert leaves and (b.option == -1).sum() == sum(keep) + len(leaves)
    assert len(b) == len(a) + len(leaves) and (b.weight[b.option == -1] == 1).all()
    checked = 0
    for (code, _, opts), k in zip(rows, keep):
        if not k or checked >= 12:
            continue
        s = sts.Combat.decode(code)
        for (_, kind, outs), o in zip(s.options(selfplay.LIMIT), opts):
            if kind == "chance":  # the paused state's value is the expectation over its listed outcomes
                assert abs(sum(p * solved_value(x) for p, x in outs) - o[1]) < 1e-6
                checked += 1
    assert checked


def test_held_out_split():
    path = fixture_db()
    a, turns = exact_only.select_rows(path, n=50)
    b, _ = exact_only.select_rows(path, n=50)
    assert all((a[k] == b[k]).all() for k in a)
    assert not set(a["train"]) & set(a["held_out"]) and len(a["train"])
    import sqlite3
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    hashes = dict(con.execute("select id, key_hash from states where options is not null"))
    assert all(hashes[i] % exact_only.HOLD == 0 for i in a["held_out"])
    assert all(hashes[i] % exact_only.HOLD != 0 for i in a["train"])
    assert all(turns[i] <= 3 for k in a for i in a[k])
    half = len(a["train"]) // 2
    assert all(turns[i] >= 1 for i in a["train"][:half]) and all(turns[i] == 0 for i in a["train"][half:])


def test_regret_table():
    rows = [{"horizon": 1, "options": [["a", 1.0], ["b", 0.5], ["End", 0.5]]},
            {"horizon": 1, "options": [["a", 1.2], ["b", 1.0], ["End", 0.0]]},
            {"horizon": 2, "options": [["a", 0.4], ["b", 0.4]]}]  # dull: skipped
    t = exact_only.regret_table(rows, {"heuristic": [1, 0, 0], "net": [0, 1, 1]})
    assert set(t["net"]) == {1}
    assert t["heuristic"][1]["n"] == 2 and abs(t["heuristic"][1]["regret"][0] - 0.25) < 1e-9
    assert abs(t["net"][1]["regret"][0] - 0.1) < 1e-9
    assert abs(t["net"][1]["vs"][0] - (-0.15)) < 1e-9 and t["heuristic"][1]["vs"] is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    try:
        for t in tests:
            t()
            print("ok ", t.__name__)
    finally:
        for r in _ROOT:
            shutil.rmtree(r, ignore_errors=True)
    print(len(tests), "passed")
