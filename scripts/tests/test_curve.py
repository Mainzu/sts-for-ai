"""Tests for the learning-curve bench (scripts/curve.py, docs/specs/warm-start.md).
Run with `python scripts/tests/test_curve.py` (plain asserts; every
`test_*` function runs) or with pytest."""

import json
import os
import shutil
import sys
import tempfile

import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import curve  # noqa: E402


def row(size, pair, tier, diff, sd):
    return {"size": size, "pair": pair, "tier": tier, "mse_diff": diff, "seed_sd": sd}


def full_rows(diff, sd, sizes=(10,)):
    return [row(z, f"{a} - {b}", t, diff, sd) for z in sizes for a, b in curve.COMPARE for t in curve.TIERS]


FLOOR_OK = {"silent_a": [0.2, 0.1, 0.3], "silent_b": [0.1, 0.02, 0.2]}


def test_gate_pass():
    g = curve.gate(full_rows([-0.05, -0.08, -0.02], 0.01), FLOOR_OK, [0, 10])
    assert g["pass"] is True and not any(r["luck"] for r in g["rows"])


def test_gate_fail_on_mse():
    rows = full_rows([-0.05, -0.08, -0.02], 0.01)
    rows[1] = {**rows[1], "mse_diff": [-0.01, -0.03, 0.01]}  # interval reaches 0
    g = curve.gate(rows, FLOOR_OK, [0, 10])
    assert g["pass"] is False and sum(not r["pass"] for r in g["rows"]) == 1


def test_gate_fail_on_floor():
    g = curve.gate(full_rows([-0.05, -0.08, -0.02], 0.01), {**FLOOR_OK, "silent_b": [0.05, -0.01, 0.1]}, [0, 10])
    assert g["pass"] is False and g["floor"]["silent_b"]["pass"] is False


def test_gate_luck_flag():
    """A passing difference smaller than twice its seed sd is flagged, and
    still passes."""
    g = curve.gate(full_rows([-0.05, -0.08, -0.02], 0.03), FLOOR_OK, [0, 10])
    assert g["pass"] is True and all(r["luck"] for r in g["rows"])
    g = curve.gate(full_rows([-0.05, -0.08, -0.02], None), FLOOR_OK, [0, 10])
    assert not any(r["luck"] for r in g["rows"])


def test_gate_incomplete():
    g = curve.gate(full_rows([-0.05, -0.08, -0.02], 0.01)[:2], FLOOR_OK, [0, 10])
    assert g["pass"] is None


def test_curve_quick():
    """`curve.py --quick` writes every (start, size, seed) cell and a gate."""
    root = tempfile.mkdtemp(prefix="curve-")
    out = os.path.join(root, "out")
    try:
        code = curve.main(["--quick", "--root", root, "--out", out, "--threads", "4"])
        assert code in (0, 1)
        with open(os.path.join(out, "curve.json"), encoding="utf-8") as f:
            res = json.load(f)
        want = {(s, z, k) for s, z, k in curve.cells({**curve.DEFAULTS, **curve.QUICK}, curve.STARTS)}
        got = {(c["start"], c["size"], c["seed"]) for c in res["cells"]}
        assert got == want, (got, want)
        assert res["gate"]["pass"] in (True, False)
        assert {r["tier"] for r in res["gate"]["rows"]} == set(curve.TIERS)
        assert set(res["gate"]["floor"]) == set(curve.TIERS)
        # a second run reuses every cell (registry runs and cached metrics)
        n_runs = len(os.listdir(os.path.join(root, "runs")))
        curve.main(["--quick", "--root", root, "--out", out, "--threads", "4"])
        assert len(os.listdir(os.path.join(root, "runs"))) == n_runs
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_cached_skips_stale_cells():
    """Another process's cell is reused only when its settings equal the
    current ones: an old stand-in cell (other test-games, sorted first) is
    never picked."""
    out = tempfile.mkdtemp(prefix="curve-cells-")
    try:
        settings = {**curve.DEFAULTS, **curve.QUICK}
        stale = {**settings, "test_games": settings["test_games"] + 1}
        d = os.path.join(out, "cells")
        os.makedirs(d)
        for key, s, tag in (("0000000000000000", stale, "stale"), ("ffffffffffffffff", settings, "current")):
            cell = {"start": "warm_effects", "size": 10, "seed": 0, "tag": tag,
                    "settings": curve.cell_settings("warm_effects", 10, 0, s)}
            with open(os.path.join(d, f"warm_effects-10-s0-{key}.json"), "w", encoding="utf-8") as f:
                json.dump(cell, f)
        assert curve._cached("warm_effects", 10, 0, out, settings)["tag"] == "current"
        os.remove(os.path.join(d, "warm_effects-10-s0-ffffffffffffffff.json"))
        assert curve._cached("warm_effects", 10, 0, out, settings) is None
    finally:
        shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    torch.set_num_threads(4)
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for name, fn in tests:
        fn()
        print(f"{name}: ok")
    print(f"{len(tests)} passed")
