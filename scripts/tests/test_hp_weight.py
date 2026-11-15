"""Tests for the `hp_weight` config key (docs/specs/hp-weight.md): HP lost
weighted in the outcome labels. Run with
`python scripts/tests/test_hp_weight.py` or pytest."""

import os
import sys
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import learn  # noqa: E402


def examples(outcome, option=None, decision=None, prob=None, opt_const=None):
    f = lambda x: None if x is None else np.asarray(x, np.float32)  # noqa: E731
    i = lambda x: None if x is None else np.asarray(x, np.int64)  # noqa: E731
    return types.SimpleNamespace(outcome=f(outcome), target=f(outcome), option=i(option), decision=i(decision),
                                 prob=f(prob), opt_const=f(opt_const))


def test_off_leaves_examples_alone():
    d = examples([0.0, 1.9])
    assert learn.weigh_hp(d, {}) is d
    assert d.outcome.tolist() == np.float32([0.0, 1.9]).tolist()


def test_outcomes():
    # A win losing L HP scores 2 - L/100; weighted: 2 - w L / 100, floored
    # at WIN_FLOOR so a win stays above a loss (0).
    got = learn.hp_scale(np.float32([0.0, 2.0, 1.9, 1.5, 1.2]), 3.0)
    want = [0.0, 2.0, 1.7, 0.5, learn.WIN_FLOOR]
    assert np.allclose(got, want, atol=1e-6), got
    assert learn.hp_scale(np.float32([1.9]), 1.0).tolist() == np.float32([1.9]).tolist()


def test_targets_and_outcomes_weighed():
    d = learn.weigh_hp(examples([0.0, 1.9, 1.8]), {"hp_weight": 2.0})
    assert np.allclose(d.outcome, [0.0, 1.8, 1.6]) and np.allclose(d.target, d.outcome)


def test_opt_const():
    # Decision 0: option 0 is a chance option with two unfinished outcomes
    # of mass 0.25 each and finished wins of mass 0.5 at score 1.9
    # (const 0.95); option 1 unfinished (const 0). The decision row
    # (option -1) is left alone.
    d = examples([1.9] * 4, option=[-1, 0, 0, 1], decision=[0, 0, 0, 0], prob=[0, 0.25, 0.25, 1.0],
                 opt_const=[0, 0.95, 0.95, 0])
    d = learn.weigh_hp(d, {"hp_weight": 3.0})
    assert np.allclose(d.opt_const, [0, 0.85, 0.85, 0]), d.opt_const


def test_unsupported_combinations():
    for extra in ({"switches": {"hp_loss": True}}, {"teacher": {}}, {"rung4": {"k": 2}}):
        try:
            learn.check_hp_weight({"hp_weight": 2.0, **extra})
        except ValueError:
            continue
        raise AssertionError(f"hp_weight with {extra} accepted")
    learn.check_hp_weight({"hp_weight": 2.0})
    learn.check_hp_weight({})


def test_round0_must_match():
    learn.check_round0({"hp_weight": 2.0}, {"hp_weight": 2.0})
    learn.check_round0({}, {})
    for a, b in (({"hp_weight": 2.0}, {}), ({}, {"hp_weight": 2.0})):
        try:
            learn.check_round0(a, b)
        except ValueError:
            continue
        raise AssertionError("round 0 with other HP weight accepted")


def test_smoke_learn():
    """A tiny two-round run with hp_weight: its examples carry the weighted
    outcomes (round 0 exactly: label scale 0), the unweighted load of the
    same dataset differs only on wins, and a reused round 0 of another
    weight is refused."""
    import json
    import tempfile
    import registry
    import selfplay
    cfg = {"name": "smoke-hpw", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 71, "val_seed": 72,
           "search": {"limit": selfplay.LIMIT}, "seed": 0, "rounds": {"n": 1, "temperature": 0.05, "every": 100},
           "switches": {}, "hp_weight": 3.0}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:  # mapped caches
        runs = learn.learn(cfg, root=root, log=lambda *_: None)
        r0 = json.load(open(os.path.join(runs[0].path, "round.json")))
        assert r0["label_scale"]["per_dataset"][r0["new_dataset"]] == 0.0
        full = {**cfg, **learn.label_settings(cfg)}
        w = learn.load_examples(full, r0["new_dataset"], 0, root=root)
        raw = learn.load_examples({k: v for k, v in full.items() if k != "hp_weight"}, r0["new_dataset"], 0, root=root)
        o, ow = np.asarray(raw.outcome), np.asarray(w.outcome)
        assert np.allclose(ow, learn.hp_scale(o, 3.0)) and np.allclose(np.asarray(w.target), ow)
        assert (ow[o > 0] < o[o > 0]).any() or (o[o > 0] == 2).all()
        del w, raw
        assert registry.Run(runs[0].path)._read("config.json")["hp_weight"] == 3.0
        try:
            learn.learn({k: v for k, v in cfg.items() if k != "hp_weight"}, root=root, log=lambda *_: None,
                        round0=runs[0])
        except ValueError:
            pass
        else:
            raise AssertionError("round 0 of another weight reused")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t_ in tests:
        t_()
        print("ok ", t_.__name__)
    print(len(tests), "passed")
