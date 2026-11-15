"""Rung 4 check (docs/specs/rung4-check.md): the pre-check's statistics on
hand-made numbers, its play-out seeds, and rung 4's labels (on the
curriculum tests' pinned dataset, with a hand-made play-out cache).

    python scripts/tests/test_rung4.py
"""

import hashlib
import os
import shutil
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import learn  # noqa: E402
import rung4  # noqa: E402
from test_curriculum import LEARN_CFG, dataset_ids, fixture_root  # noqa: E402


def test_band():
    assert [rung4.band(d) for d in (0, 1, 2, 3, 4, 5, 6, 30)] == ["1", "1", "2", "3", "4-5", "4-5", "6+", "6+"]


def test_playout_stats():
    """σ² is the mean per-position play-out variance (n - 1); err² takes the
    play-out mean's own noise (σ²_i / K) out of the squared net error; the
    ending's bias is mean(ending - play-out mean)."""
    scores = np.array([[0.0, 2.0, 0.0, 2.0], [1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 2.0, 2.0]])
    endings = np.array([2.0, 1.0, 0.0])
    values = np.array([1.5, 1.0, 0.5])
    s = rung4.playout_stats(endings, values, scores)
    var = scores.var(axis=1, ddof=1)  # 4/3, 0, 4/3
    assert np.isclose(s["sigma2"][0], var.mean())
    m = scores.mean(axis=1)  # 1, 1, 1
    assert np.isclose(s["ending_minus_playout"][0], (endings - m).mean())
    err = (values - m) ** 2 - var / 4  # 0.25 - 1/3, 0, 0.25 - 1/3
    assert np.isclose(s["err2"][0], err.mean())
    assert s["n"] == 3
    for k in ("sigma2", "err2", "ending_minus_playout"):
        assert s[k][1] <= s[k][0] <= s[k][2]


def test_pick_k():
    """The largest K in 4..16 whose play-outs fit the budget; None when not
    even 4 fit."""
    assert rung4.pick_k(1000, 10.0, budget_s=3600) == 16  # 16k play-outs: 1,600 s
    assert rung4.pick_k(76_000, 200.0, budget_s=3600) == 9  # 9 x 76k / 200 = 3,420 s
    assert rung4.pick_k(76_000, 85.0, budget_s=3600) == 4
    assert rung4.pick_k(76_000, 80.0, budget_s=3600) is None


def test_seeds_distinct():
    """Play-out seeds: their own range from PLAYOUT_SEED, distinct per
    (dataset slot, example, play-out), the same for the same triple."""
    a = rung4.playout_seeds(0, np.array([0, 1, 5]), 16)
    b = rung4.playout_seeds(1, np.array([0, 1, 5]), 16)
    assert a.shape == (3, 16) and len(set(a.ravel()) | set(b.ravel())) == 96
    assert a.min() == rung4.PLAYOUT_SEED and (rung4.playout_seeds(0, np.array([5]), 4) == a[2:, :4]).all()
    assert b.max() < 2 ** 63


def test_weighted_item1():
    """Item 1 weighted by each band's share of all the dataset's valued
    rung-5 examples: a sample that over-represents a band whose endings
    run low still averages to the population's mean."""
    sample = np.array(["1"] * 4 + ["2"] * 4)
    diff = np.array([-1.0, -1.0, -1.0, -1.0, 0.5, 0.5, 0.25, 0.75])
    pop = np.array(["1"] * 1 + ["2"] * 3)  # band 1 is a quarter of the population
    w = rung4.weighted_item1(diff, sample, pop)
    assert np.isclose(w[0], 0.25 * -1.0 + 0.75 * 0.5)
    assert w[1] <= w[0] <= w[2]
    assert np.isclose(rung4.weighted_item1(diff, sample, np.array(["2"]))[0], 0.5)  # a band absent from the population weighs 0


def gate_halves(train, held_out):
    return {"halves": {"train": {"lead": train}, "held_out": {"lead": held_out}}}


def test_check_verdict():
    """B - A passes when its held-out interval lies above 0 and its train
    interval's upper end reaches 0."""
    assert rung4.verdict(gate_halves([0.0, -0.01, 0.01], [0.02, 0.01, 0.03]))["passes"]
    assert rung4.verdict(gate_halves([-0.01, -0.02, 0.0], [0.02, 0.01, 0.03]))["passes"]  # train reaches 0
    v = rung4.verdict(gate_halves([0.01, 0.0, 0.02], [0.01, 0.0, 0.02]))  # held-out lower end at 0
    assert not v["passes"] and not v["better_held_out"] and v["train_not_worse"]
    v = rung4.verdict(gate_halves([-0.02, -0.03, -0.01], [0.02, 0.01, 0.03]))  # train drops
    assert not v["passes"] and v["better_held_out"] and not v["train_not_worse"]


def test_check_report():
    """The check's markdown names both arms, B - A and the verdict."""
    g = gate_halves([0.01, 0.0, 0.02], [0.02, 0.01, 0.03])
    for h in g["halves"].values():
        h.update(net=[0.5, 0.49, 0.51], heuristic=[0.5, 0.49, 0.51], cells=600)
    res = {"k": 12, "arms": {a: {"model": f"{a}.pt", "val_mse": 0.16, "train_min": 7.0, "rungs": {"outcome": 1}}
                             for a in ("A", "B")},
           "err2": {"A": [0.09, 0.08, 0.1], "B": [0.06, 0.05, 0.07]},
           "tight": {"A": g, "B": g, "B_vs_A": g}, "verdict": rung4.verdict(g), "minutes": 30.0}
    text = rung4.check_report(res)
    assert "B - A" in text and "passes" in text and "| A |" in text and "| B |" in text


def test_seeds_average():
    """Over seeds, each fight's B - A is averaged across seeds first, then
    per cell with the interval over cells, as a direct computation."""
    rng = np.random.default_rng(3)
    cells = {h: [c for c in range(30) for _ in range(4)] for h in ("train", "held_out")}
    b = [{h: list(rng.integers(0, 2, 120)) for h in cells} for _ in range(3)]
    a = [{h: list(rng.integers(0, 2, 120)) for h in cells} for _ in range(3)]
    got = rung4.seeds_average(b, a, cells)
    for h in cells:
        d = np.mean([np.array(bs[h], float) - np.array(as_[h], float) for bs, as_ in zip(b, a)], axis=0)
        m = d.reshape(30, 4).mean(axis=1)
        w = 1.959964 * m.std(ddof=1) / np.sqrt(30)
        assert np.allclose(got[h], [m.mean(), m.mean() - w, m.mean() + w], atol=1e-5)


def test_seeds_verdict():
    """Over seeds: passes when every seed's held-out B - A is above 0 and the
    seed-averaged held-out interval lies above 0, with the averaged train
    interval's upper end at 0 or above; fails otherwise."""
    def per(*held):
        return {s: {"train": [0.0, -0.01, 0.01], "held_out": [x, x - 0.01, x + 0.01]} for s, x in zip((1, 101, 201), held)}
    avg = {"train": [0.0, -0.01, 0.01], "held_out": [0.006, 0.002, 0.010]}
    assert rung4.seeds_verdict(per(0.004, 0.006, 0.008), avg)["passes"]
    v = rung4.seeds_verdict(per(0.004, 0.0, 0.008), avg)  # one seed at 0
    assert not v["passes"] and not v["every_seed_better"]
    v = rung4.seeds_verdict(per(0.004, 0.006, 0.008), {**avg, "held_out": [0.004, 0.0, 0.008]})  # average reaches 0
    assert not v["passes"] and v["every_seed_better"] and not v["better_held_out"]
    v = rung4.seeds_verdict(per(0.004, 0.006, 0.008), {**avg, "train": [-0.02, -0.03, -0.01]})  # train drops
    assert not v["passes"] and not v["train_not_worse"]


def test_seeds_report():
    """The over-seeds report names each seed and the averaged B - A."""
    g = gate_halves([0.01, 0.0, 0.02], [0.02, 0.01, 0.03])
    seed = {"arms": {a: {"model": f"{a}.pt", "val_mse": 0.16, "train_min": 7.0, "rungs": {}} for a in ("A", "B")},
            "err2": {"A": [0.09, 0.08, 0.1], "B": [0.06, 0.05, 0.07]},
            "tight": {"A": g, "B": g, "B_vs_A": g}}
    avg = {"train": [0.01, 0.0, 0.02], "held_out": [0.02, 0.01, 0.03]}
    res = {"k": 12, "seeds": {"1": seed, "101": seed}, "over_seeds": {
        "B_vs_A": avg, "spread_B_vs_A": {"train": 0.002, "held_out": 0.003}, "spread_A": {"train": 0.004, "held_out": 0.005},
        "verdict": rung4.seeds_verdict({1: g_leads(g), 101: g_leads(g)}, avg)}, "minutes": 50.0}
    text = rung4.seeds_report(res)
    assert "| 1 |" in text and "| 101 |" in text and "averaged over seeds" in text and "passes" in text


def g_leads(g):
    return {h: v["lead"] for h, v in g["halves"].items()}


def labelled(cfg, root, exact=None):
    """The pinned score dataset as round 1 labels it, frontier 2 (rungs 1,
    3 and 5 all present)."""
    return learn.load_examples(cfg, dataset_ids()["score"], 1, root=root, frontier=2, exact=exact)


def planted(root):
    """An exact lookup planting one value on the first valued rung-5
    example (rung 1)."""
    d = labelled(LEARN_CFG["score"], root)
    raw = learn.registry.examples(dataset_ids()["score"], "effects", root=root,
                                  labels=learn.labels(LEARN_CFG["score"], 1))
    i = int(np.flatnonzero((d.rung == 5) & (d.weight > 0))[0])
    code = raw.codec_bytes(i)
    return (lambda cs: [(0.123, None) if c == code else None for c in cs]), i


def digest(d):
    h = hashlib.sha256()
    for a in (d.target, d.weight, d.rung):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()[:16]


# Labels of the pinned score dataset (round 1, frontier 2, one planted exact
# value) before rung 4 existed, recorded on 46ebdd0's code.
PIN_NO_RUNG4 = "3fe503865efbca81"


def test_ladder_without_rung4_unchanged():
    """A config without `rung4` labels exactly as before (targets, weights,
    rungs), and never looks for play-out caches."""
    root = fixture_root()
    saved = learn.RUNG4_DIR if hasattr(learn, "RUNG4_DIR") else None
    try:
        learn.RUNG4_DIR = os.path.join(root, "no-such-dir")
        exact, _ = planted(root)
        d = labelled(LEARN_CFG["score"], root, exact)
        assert set(np.unique(d.rung)) == {1, 3, 5}
        assert digest(d) == PIN_NO_RUNG4, digest(d)
    finally:
        if saved is not None:
            learn.RUNG4_DIR = saved
        shutil.rmtree(root, ignore_errors=True)


def test_rung4_labels():
    """With `rung4` {k: K}: every valued rung-5 example takes (ending + K x
    its play-out mean) / (K + 1) and rung 4; rung 1 and 3 examples,
    ranking-only weights and the rest are unchanged; a cache entry for
    another example is ignored; a missing cache, a missing example or a
    cache for another layout raises; `rung_counts` gains `playout` only
    when above 0."""
    root = fixture_root()
    saved = learn.RUNG4_DIR
    k = 12
    try:
        learn.RUNG4_DIR = os.path.join(root, "playouts")
        exact, i_exact = planted(root)
        base = labelled(LEARN_CFG["score"], root, exact)
        five = np.flatnonzero((base.rung == 5) & (base.weight > 0))
        other = int(np.flatnonzero(base.rung == 3)[0])  # a stray cache entry: ignored
        idx = np.sort(np.append(five, other))
        mean = 0.25 + 0.01 * (np.arange(len(idx)) % 50)
        ds = dataset_ids()["score"]
        rung4.save_playouts(learn.rung4_path(ds, k), idx, mean, k, len(base))
        cfg = {**LEARN_CFG["score"], "rung4": {"k": k}}
        got = labelled(cfg, root, exact)
        m = dict(zip(idx.tolist(), mean))
        want = np.array([(float(base.outcome[i]) + k * m[int(i)]) / (k + 1) for i in five], np.float64)
        assert np.array_equal(got.target[five], want.astype(got.target.dtype))
        assert (got.rung[five] == 4).all() and got.rung[i_exact] == 1
        rest = np.setdiff1d(np.arange(len(base)), five)
        assert np.array_equal(got.target[rest], base.target[rest]) and np.array_equal(got.rung[rest], base.rung[rest])
        assert np.array_equal(got.weight, base.weight)
        assert not np.array_equal(got.target, base.target)
        # rung_counts: `playout` only when above 0; an exact draw (rung None) counts as before
        c = learn.rung_counts([(got, got.rung)])
        assert c["playout"] == len(five) and c["outcome"] == 0
        assert "playout" not in learn.rung_counts([(base, base.rung), (base, None)])
        # failures: never a fallback to the endings
        for bad_cfg in ({**LEARN_CFG["score"], "rung4": {"k": 8}},):  # no cache for k 8
            try:
                labelled(bad_cfg, root, exact)
                raise AssertionError("missing cache accepted")
            except FileNotFoundError:
                pass
        keep = idx != five[0]  # one rung-5 example missing
        rung4.save_playouts(learn.rung4_path(ds, k), idx[keep], mean[keep], k, len(base))
        try:
            labelled(cfg, root, exact)
            raise AssertionError("missing example accepted")
        except ValueError:
            pass
        rung4.save_playouts(learn.rung4_path(ds, k), idx, mean, k, len(base) + 1)  # another layout
        try:
            labelled(cfg, root, exact)
            raise AssertionError("other layout accepted")
        except ValueError:
            pass
    finally:
        learn.RUNG4_DIR = saved
        shutil.rmtree(root, ignore_errors=True)


def test_fill_end_to_end():
    """`labels`' cache filling on the real window (needs the 2026-10-28
    night's datasets and db/bounds-check.sqlite): 3 examples per dataset
    at K 2, each by its own player; a rerun plays nothing; the means are
    the play-outs `playouts` gives for the same seeds."""
    import json
    import registry
    import round_check
    db = os.path.abspath("db/bounds-check.sqlite")
    if not os.path.exists(db) or not os.path.isdir(round_check.NIGHT):
        print("skipped: the night's data isn't here")
        return
    saved = learn.RUNG4_DIR, learn.db_path, os.environ.get("STS_CACHE_DIR")
    tmp = tempfile.mkdtemp()
    cache = tempfile.mkdtemp()  # the window's feature caches (3.5 GB): not main's cache/, where evict would make room
    try:
        os.environ["STS_CACHE_DIR"] = cache
        learn.RUNG4_DIR = tmp
        learn.db_path = lambda root=registry.ROOT: db
        cfg = json.load(open(os.path.join(round_check.NIGHT, "config.json")))
        parts = rung4.window(cfg)
        lines = []
        rung4.fill(parts, 2, limit=3, log=lines.append)
        assert len(os.listdir(tmp)) == 2 and any("3 to play" in x for x in lines)
        lines.clear()
        rung4.fill(parts, 2, limit=3, log=lines.append)
        assert all("0 to play" in x for x in lines if "rung-5" in x)
        for slot, (ds, _, d) in enumerate(parts):
            idx, mean, k, n = learn.rung4_playouts(ds, 2)
            assert k == 2 and n == len(d) and np.array_equal(idx, rung4.rung5(d)[:3])
            assert ((mean >= 0) & (mean <= 2.5)).all()
            model, search = rung4.player(ds)
            assert np.allclose(mean[:1], rung4.playouts(d, idx[:1], slot, 2, model, search).mean(axis=1))
    finally:
        learn.RUNG4_DIR, learn.db_path, env = saved
        if env is None:
            os.environ.pop("STS_CACHE_DIR", None)
        else:
            os.environ["STS_CACHE_DIR"] = env
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(cache, ignore_errors=True)


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
    print("ok")
