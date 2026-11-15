"""Tests for the generated-power bench read (docs/specs/gen-training-arms.md):
`build` with defaults still writes the first check's bench, `--seeds 12`
keeps its cells and cards, and the arms pairing (arm minus control by cell,
then over seed indices). Run with
`python scripts/tests/test_gen_powers_read.py` or pytest. About 10 s."""

import json
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "analysis"))
os.chdir(ROOT)  # the bench names its pack and source by repo-relative paths
import gen_powers_read as gpr  # noqa: E402


def built(seeds):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bench.json")
        gpr.build(seeds, path)
        with open(path, encoding="utf-8") as f:
            return json.load(f)


def test_default_build_is_the_first_checks_bench():
    with open(gpr.BENCH, encoding="utf-8") as f:
        assert built(gpr.SEEDS) == json.load(f)


def test_twelve_fights_keep_cells_and_cards():
    four, twelve = built(4), built(12)

    def cards(b):
        return {(f["cell"], f["set"]): (tuple(f["deck"]), f["gen_card"]) for f in b["fights"]}
    assert cards(four) == cards(twelve)
    per = {}
    for f in twelve["fights"]:
        per[(f["cell"], f["set"])] = per.get((f["cell"], f["set"]), 0) + 1
    assert set(per.values()) == {12}
    first = {(f["cell"], f["set"], f["seed"]) for f in four["fights"]}
    assert first <= {(f["cell"], f["set"], f["seed"]) for f in twelve["fights"]}


def test_arm_diff_pairs_by_cell_then_seed():
    fights = [{"cell": c, "set": "generated"} for c in ("a", "a", "b", "c")]
    ctrl = [[0, 0, 1, 1], [1, 1, 0, 0]]
    arm = [[1, 0, 1, 1], [1, 1, 1, 1]]
    # seed 1: a +0.5, b 0, c 0 -> 1/6; seed 2: a 0, b +1, c +1 -> 2/3
    r = gpr.arm_diff(fights, ctrl, arm, lambda f: f["set"])["generated"]
    assert r["cells"] == 3
    assert np.allclose(r["per_seed"], [1 / 6, 2 / 3])
    assert np.isclose(r["diff"], (1 / 6 + 2 / 3) / 2)
    assert np.isclose(r["se"], np.std([1 / 6, 2 / 3], ddof=1) / np.sqrt(2))
    assert gpr.arm_diff(fights, ctrl, arm, lambda f: None) == {}


def test_burst_contrast():
    """Target minus other generated cards, per seed and pooled over cells
    (adaptation-burst spec, test 5); originals stay a slice of their own."""
    cards = [("a", "generated", "T"), ("a", "generated", "T"), ("b", "generated", "T"),
             ("c", "generated", "O"), ("d", "generated", "O"), ("a", "original", "T")]
    fights = [{"cell": c, "set": s, "gen_card": g, "group": "hallway"} for c, s, g in cards]
    ctrl = [[0, 0, 0, 0, 0, 1]] * 2
    arm = [[1, 0, 1, 0, 1, 1], [1, 1, 0, 0, 0, 0]]
    # seed 1: target a .5, b 1 -> .75; other c 0, d 1 -> .5. seed 2: target a 1, b 0 -> .5; other 0
    r = gpr.burst_contrast(fights, ctrl, arm, {"T"})
    assert np.allclose(r["per_seed"], [0.25, 0.5])
    # pooled cells: target a .75, b .5; other c 0, d .5
    assert np.isclose(r["target"], 0.625) and np.isclose(r["other"], 0.25)
    assert np.isclose(r["contrast"], 0.375)
    assert np.isclose(r["se"], np.hypot(0.125, 0.25))
    part = gpr.arm_diff(fights, ctrl, arm, gpr.burst_slices({"T"})["part"])
    assert np.allclose(part["original"]["per_seed"], [0, -1]) and set(part) == {"target", "other", "original"}


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
