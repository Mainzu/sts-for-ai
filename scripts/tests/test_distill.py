"""Distillation through the ranking term (docs/specs/distill-two-turn.md):
a config's `teacher` re-searches drawn elite / boss decisions of a round's
self-play dataset two turns deep with the playing net and puts those
option values into `rank_value`.

    python scripts/tests/test_distill.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

import bench
import learn
import registry
import selfplay
import sts

CFG = {"name": "distill-t", "mode": "effects", "n_train": 3, "n_val": 1, "train_seed": 71, "val_seed": 72,
       "search": {"limit": selfplay.LIMIT}, "seed": 0, "rounds": {"n": 0, "temperature": 0.05, "every": 100},
       "switches": {}, "solve_games": 0, "solve_games0": 0}
TEACHER = {"turns": 2, "states": 6, "groups": ["elite", "boss"], "max_nodes": 400000, "sample_k": 4, "seed": 0,
           "threads": 1}
_ROUND = {}

try:  # pytest gives the tests one temp root; run as a script, __main__ below does
    import pytest

    @pytest.fixture(scope="module")
    def root(tmp_path_factory):
        return str(tmp_path_factory.mktemp("distill"))
except ImportError:
    pass


def round1(root):
    """(round-1 dataset id, the round-0 run that played it) of a tiny
    run under `root`, built once per root."""
    if root not in _ROUND:
        run0 = learn.learn(CFG, root=root, log=lambda *_: None)[0]
        ds = learn.dataset(CFG, "train", root, rnd=1, parent=run0, log=lambda *_: None)
        _ROUND[root] = (ds, run0)
    return _ROUND[root]


def examples(root, ds):
    return registry.examples(ds, "effects", root=root, labels=learn.labels(CFG, 1))


def decision_rows(d, i):
    """Rows of the decision whose state is example `i`."""
    return np.flatnonzero((d.decision == d.decision[i]) & (d.option >= 0))


def two_turn(model, d, i, t):
    ev = bench.load_evaluator(model)
    seed = (t["seed"] * 1009 + int(i)) % 2**64
    c = sts.Combat.decode(d.codec_bytes(int(i)), seed=seed)
    return sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT, turns=t["turns"],
                      sample_k=t["sample_k"], seed=seed, max_nodes=t["max_nodes"])


def test_no_teacher_changes_nothing(root):
    ds, _ = round1(root)
    plain = examples(root, ds).rank_value.copy()
    assert learn.teach(CFG, ds, 1, root=root, log=lambda *_: None) is None
    got = learn.load_examples(CFG, ds, 1, root=root).rank_value
    assert np.array_equal(plain, got)


def test_decoded_state_reproduces_one_turn_values(root):
    """The mapping: a decision's decoded state, searched one turn deep by
    the playing net, gives the recorded `rank_value` of each option row."""
    ds, run0 = round1(root)
    d = examples(root, ds)
    ev = bench.load_evaluator(run0.model_path)
    for i in np.flatnonzero(d.option == -1)[:10]:
        c = sts.Combat.decode(d.codec_bytes(int(i)), seed=0)
        vals = [v for _, v in sts.search(c, ev.evaluator, features=ev.features, **CFG["search"])["options"]]
        for j in decision_rows(d, i):
            assert abs(vals[d.option[j]] - d.rank_value[j]) < 1e-5, (i, j)


def test_teacher_labels(root):
    ds, run0 = round1(root)
    cfg = {**CFG, "teacher": TEACHER}
    rec = learn.teach(cfg, ds, 1, root=root, log=lambda *_: None)
    d = examples(root, ds)
    lab = learn.teacher_labels(cfg, ds, root)
    assert rec["drawn"] == len(lab["idx"]) > 0 and rec["searched"] + rec["cut"] == rec["drawn"]
    taught = learn.apply_teacher(examples(root, ds), lab)
    for n, i in enumerate(lab["idx"]):
        assert d.option[i] == -1 and d.group[i] in (1, 2)
        rows = decision_rows(d, i)
        assert len(set(d.option[rows].tolist())) >= 2
        r = two_turn(run0.model_path, d, i, TEACHER)
        vals = [v for _, v in r["options"]]
        if r["cuts"] > 0:  # a cut decision keeps its one-turn values
            assert lab["cut"][n]
            assert np.array_equal(taught.rank_value[rows], d.rank_value[rows])
        else:
            for j in rows:
                assert abs(taught.rank_value[j] - vals[d.option[j]]) < 1e-5
    other = np.setdiff1d(np.arange(len(d)), np.concatenate([decision_rows(d, i) for i in lab["idx"]]))
    assert np.array_equal(taught.rank_value[other], d.rank_value[other])


def test_cut_decisions_keep_one_turn_values(root):
    ds, _ = round1(root)
    cfg = {**CFG, "teacher": {**TEACHER, "max_nodes": 50}}
    rec = learn.teach(cfg, ds, 1, root=root, log=lambda *_: None)
    assert rec["cut"] > 0
    d = examples(root, ds)
    lab = learn.teacher_labels(cfg, ds, root)
    taught = learn.apply_teacher(examples(root, ds), lab)
    for n, i in enumerate(lab["idx"]):
        if lab["cut"][n]:
            rows = decision_rows(d, i)
            assert np.array_equal(taught.rank_value[rows], d.rank_value[rows])


def test_cache_and_seeded_draw(root):
    ds, _ = round1(root)
    cfg = {**CFG, "teacher": TEACHER}
    learn.teach(cfg, ds, 1, root=root, log=lambda *_: None)
    a = learn.teacher_labels(cfg, ds, root)
    real = sts.search
    sts.search = None  # a cached dataset searches nothing
    try:
        rec = learn.teach(cfg, ds, 1, root=root, log=lambda *_: None)
    finally:
        sts.search = real
    b = learn.teacher_labels(cfg, ds, root)
    assert rec["cached"]
    for k in a:
        assert np.array_equal(a[k], b[k])
    # the draw is seeded: the same decisions for the same seed, others for another
    d = examples(root, ds)
    assert np.array_equal(learn.teacher_draw(d, TEACHER), learn.teacher_draw(d, TEACHER))
    more = {**TEACHER, "states": 10**6}
    assert len(learn.teacher_draw(d, more)) >= len(a["idx"])


def test_worker_pool_matches_one_thread(root):
    """Worker processes label the same as one thread (threads aren't in the
    cache key, so the cache is moved aside between the two)."""
    ds, _ = round1(root)
    cfg = {**CFG, "teacher": TEACHER}
    learn.teach(cfg, ds, 1, root=root, log=lambda *_: None)
    a = learn.teacher_labels(cfg, ds, root)
    path = learn.teacher_path(cfg, ds, root)
    os.replace(path, path + ".one")
    try:
        rec = learn.teach({**CFG, "teacher": {**TEACHER, "threads": 2}}, ds, 1, root=root, log=lambda *_: None)
        b = learn.teacher_labels(cfg, ds, root)
    finally:
        os.replace(path + ".one", path)
    assert not rec["cached"]
    for k in a:
        assert np.array_equal(a[k], b[k])


def test_load_examples_applies_teacher(root):
    ds, _ = round1(root)
    cfg = {**CFG, "teacher": TEACHER}
    learn.teach(cfg, ds, 1, root=root, log=lambda *_: None)
    want = learn.apply_teacher(examples(root, ds), learn.teacher_labels(cfg, ds, root)).rank_value
    got = learn.load_examples(cfg, ds, 1, root=root).rank_value
    assert np.array_equal(want, got)


def test_exact_values_win(root):
    """`ladder` overwrites taught `rank_value` where the database has exact
    option values."""
    ds, _ = round1(root)
    cfg = {**CFG, "teacher": TEACHER}
    learn.teach(cfg, ds, 1, root=root, log=lambda *_: None)
    lab = learn.teacher_labels(cfg, ds, root)
    i = int(lab["idx"][0])
    d = learn.apply_teacher(examples(root, ds), lab)
    code = d.codec_bytes(i)
    rows = decision_rows(d, i)
    n_opt = int(d.option[rows].max()) + 1
    exact_vals = [0.123 + 0.01 * k for k in range(n_opt)]

    def exact(codes):
        return [(0.5, exact_vals, None) if c == code else None for c in codes]
    d = learn.ladder(d, cfg, 1, exact=exact)
    for j in rows:
        assert abs(d.rank_value[j] - exact_vals[d.option[j]]) < 1e-6


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:  # mapped caches stay open on Windows
        tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
        for name, f in tests:
            f(root)
            print(f"ok  {name}")
        print(f"{len(tests)} passed")
