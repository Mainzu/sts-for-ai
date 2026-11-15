"""Seed check (spec folded: git show b076af5:docs/specs/seed-check.md): the night rounds' windows, the
database cut (on a toy database with the real schema) and the verdict on
hand-made fights.

    python scripts/tests/test_seed_check.py
"""

import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import learn  # noqa: E402
import round_check  # noqa: E402
import seed_check  # noqa: E402
import sts  # noqa: E402


def test_round_window_r10():
    w = seed_check.round_window(seed_check.night_run(10))
    assert w["parts"] == round_check.PARTS and w["val"] == round_check.VAL
    assert w["samples"] == {} and w["db_rows"] == 3_501_061 and w["round"] == 10


def test_round_window_r2():
    w = seed_check.round_window(seed_check.night_run(2))
    assert w["parts"] == [("b51c304673cb", 2), ("47199f1023e9", 1), ("2bad7e15394f", 0)]
    assert w["samples"] == {"2bad7e15394f": (1 / 6, learn.D0_SAMPLE_SEED + 1 + 1000)}
    assert w["db_rows"] == 2_846_734


def toy_db(path):
    """A database with the real schema (sts.SolvedDb's): states 1..6,
    positions on states 2, 4, 6, three trivial rows."""
    db = sts.SolvedDb(path)
    del db
    con = sqlite3.connect(path)
    (v,), = con.execute("select id from versions")
    for i in range(1, 7):
        con.execute("insert into states (id, version, key_hash, state, value, cost, turns_left, solved_at) "
                    "values (?, ?, ?, ?, ?, 1, 0, ?)", (i, v, 100 + i, bytes([i]), i / 10, 1000 + i))
    for j, s in enumerate((2, 4, 6)):
        con.execute("insert into positions (state, source, spec, prefix, step, horizon, gap) "
                    "values (?, 'src', ?, '', 0, 1, 0.0)", (s, f"spec{j}"))
    for h in range(3):
        con.execute("insert into trivial values (?, ?, ?, 0.0, 1, 0)", (v, h, h))
    con.commit()
    con.close()


def rows(path, sql):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_cut_db_cuts():
    tmp = tempfile.mkdtemp()
    try:
        src, dst = os.path.join(tmp, "src.sqlite"), os.path.join(tmp, "dst.sqlite")
        toy_db(src)
        seed_check.cut_db(src, dst, 4)
        q = "select * from states order by id"
        assert rows(dst, q) == [r for r in rows(src, q) if r[0] <= 4]
        assert [r[0] for r in rows(dst, "select state from positions order by state")] == [2, 4]
        q = "select * from trivial order by key_hash"
        assert rows(dst, q) == rows(src, q) and len(rows(dst, q)) == 3
        try:  # a cut that doesn't reach db_rows stops
            seed_check.cut_db(src, dst, 9)
            raise AssertionError("no stop")
        except SystemExit:
            pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_cut_db_leaves_source():
    tmp = tempfile.mkdtemp()
    try:
        src = os.path.join(tmp, "src.sqlite")
        toy_db(src)
        con = sqlite3.connect(src)
        con.execute("pragma wal_checkpoint(truncate)")
        con.close()
        before = hashlib.sha256(open(src, "rb").read()).hexdigest()
        seed_check.cut_db(src, os.path.join(tmp, "dst.sqlite"), 3)
        assert hashlib.sha256(open(src, "rb").read()).hexdigest() == before
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


CELLS = {"train": [0, 0, 1, 1, 2, 2], "held_out": [0, 0, 1, 1, 2, 2]}
HEUR = {"train": [0, 1, 0, 1, 0, 1], "held_out": [0, 1, 0, 1, 0, 1]}


def leads(per_seed):
    return {s: {h: v["lead"] for h, v in learn.gate(r, HEUR, CELLS)["halves"].items()} for s, r in per_seed.items()}


def verdict(per_seed):
    avg = learn.gate(seed_check.averaged(list(per_seed.values())), HEUR, CELLS)
    return seed_check.holds_up(leads(per_seed), avg)


def test_holds_up():
    win = [1, 1, 1, 1, 1, 0]  # beats the heuristic in every cell but one fight
    good = {"1": {"train": win, "held_out": win}, "2": {"train": [1, 1, 1, 1, 1, 1], "held_out": win}}
    assert verdict(good)["holds"]
    # one seed's held-out lead at 0: fails, though the average still clears 0
    bad = {**good, "3": {"train": win, "held_out": HEUR["held_out"]}}
    v = verdict(bad)
    assert not v["every_seed_held_out_above"] and not v["holds"]
    # the averaged train interval reaches 0: fails
    flat = {s: {"train": HEUR["train"] if s != "2" else [1, 1, 0, 1, 0, 1], "held_out": win} for s in good}
    v = verdict(flat)
    assert v["every_seed_held_out_above"] and not v["averaged_above"] and not v["holds"]


def test_averaged_gate():
    """Averaging each fight over seeds, then `learn.gate`, equals the per-cell
    computation done by hand."""
    rng = np.random.default_rng(3)
    per_seed = [{h: rng.integers(0, 2, 6).tolist() for h in CELLS} for _ in range(3)]
    g = learn.gate(seed_check.averaged(per_seed), HEUR, CELLS)
    for h in CELLS:
        x = np.array([r[h] for r in per_seed], float).mean(axis=0) - np.array(HEUR[h], float)
        cell = x.reshape(3, 2).mean(axis=1)
        w = 1.959964 * cell.std(ddof=1) / np.sqrt(3)
        assert np.allclose(g["halves"][h]["lead"], [cell.mean(), cell.mean() - w, cell.mean() + w], atol=1e-6)


def test_rung_mismatch():
    want = {"search": 1000, "outcome": 500, "exact": 200, "exact_drawn": 9000}
    assert seed_check.rung_mismatch({**want, "exact": 202, "exact_drawn": 1}, want) == {}
    assert seed_check.rung_mismatch({**want, "search": 1011}, want) == {"search": (1011, 1000)}


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
    print("ok")
