"""Tests for teacher sizing (learned-play step 1). Run with
`python scripts/tests/test_teacher.py` or with pytest."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import bench_decisions  # noqa: E402
import teacher_sizing  # noqa: E402


def test_first_setting_is_the_agents():
    assert teacher_sizing.SETTINGS[0] == {"limit": bench.LIMIT, "sample_k": 0, "turns": 1}


def test_default_search_matches_bench():
    """With the agents' settings the sized search picks and values exactly as
    the bench's own heuristic search."""
    decisions = bench_decisions.load_decisions()
    rows = bench_decisions.load_reference()["halves"]["train"][::50]
    ds = [decisions["train"][r["index"]] for r in rows]
    ev = bench.load_evaluator("heuristic")
    assert bench.search_decisions(ev, ds, rows) == bench.search_decisions(ev, ds, rows, teacher_sizing.SETTINGS[0])


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
