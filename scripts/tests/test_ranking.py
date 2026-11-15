"""Tests for the ranking loss (every config since Amendment 2).
Run with `python scripts/tests/test_ranking.py` or pytest."""

import os
import sys
import tempfile

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import registry  # noqa: E402
import selfplay  # noqa: E402
import stsnet  # noqa: E402
import train  # noqa: E402

CONFIG = {"name": "tiny", "sample_seed": 5, "search": {"limit": selfplay.LIMIT}}


def rank_case(pred):
    """Two decisions. Decision 0: option 0 (value 1.0, deterministic), option
    1 (value 0.6, chance: two outcomes with p 0.5 plus a finished outcome
    worth 0.2 with p 0.0 here), option 2 (value 0.2). Decision 1: option 0
    (0.9) and option 1 (0.3). Examples: decision states (option -1) and
    afterstates; `pred` gives the net's output per example."""
    decision = torch.tensor([0, 0, 0, 0, 0, 1, 1, 1])
    option = torch.tensor([-1, 0, 1, 1, 2, -1, 0, 1])
    prob = torch.tensor([0.0, 1.0, 0.5, 0.5, 1.0, 0.0, 1.0, 1.0])
    const = torch.zeros(8)
    rank = torch.tensor([1.0, 1.0, 0.6, 0.6, 0.2, 0.9, 0.9, 0.3])
    return train.ranking_loss(torch.tensor(pred), decision, option, prob, const, rank)


def test_ranking_loss_zero_when_ordered_positive_when_flipped():
    ordered = rank_case([1.5, 1.0, 0.8, 0.4, 0.1, 0.0, 0.7, 0.2])  # option means 1.0 > 0.6 > 0.1; 0.7 > 0.2
    assert float(ordered) == 0.0
    flipped = rank_case([1.5, 1.0, 0.8, 0.4, 0.1, 0.0, 0.2, 0.7])  # decision 1's pair flipped
    assert float(flipped) > 0.0
    # A chance option is ranked by its expected value, not by one outcome:
    # outcome 1.4 alone beats option 0's 1.0, but its mean 0.8 doesn't.
    assert float(rank_case([1.5, 1.0, 1.4, 0.2, 0.1, 0.0, 0.7, 0.2])) == 0.0


def test_ranking_loss_counts_finished_outcomes():
    """A finished outcome isn't an example (search scores it exactly); its
    probability-weighted score is added to its option's value."""
    decision = torch.tensor([0, 0])
    option = torch.tensor([0, 1])
    prob = torch.tensor([1.0, 0.5])  # option 1's other outcome (p 0.5) ends the combat
    rank = torch.tensor([0.5, 1.0])
    pred = torch.tensor([0.9, 0.6])
    lost = torch.tensor([0.0, 0.0])  # it's a loss: option 1 is worth 0.3 < 0.9, flipped
    assert float(train.ranking_loss(pred, decision, option, prob, lost, rank)) > 0
    won = torch.tensor([0.0, 1.0])  # a win at score 2: 0.3 + 1.0 > 0.9, in order
    assert float(train.ranking_loss(pred, decision, option, prob, won, rank)) == 0.0


def test_ranking_examples_from_stored_games():
    """With labels, each sampled decision's examples carry their decision,
    option, outcome probability and the option's search value, in order;
    an option's listed outcome probabilities sum to at most 1 (finished
    outcomes aren't examples), and every label is the game's final score."""
    specs, groups = selfplay.make_specs(2, 11, selfplay.train_deck)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        ds, results = registry.selfplay(specs, groups, CONFIG, root=root, keep_states=True)
        on = registry.examples(ds, "effects", root=root, labels={"afterstates": True})
    assert on.decision is not None and (on.decision >= 0).all()
    assert (np.diff(on.decision) >= 0).all()  # each decision's examples are contiguous
    first = on.decision == 0
    assert on.option[first][0] == -1  # the decision state itself
    rng = np.random.default_rng(CONFIG["sample_seed"])
    n = len(results[0]["states"])
    i = sorted(rng.choice(n, min(n, selfplay.STATES_PER_GAME), replace=False))[0]
    vals = [v for _, v in results[0]["values"][i]]
    for o, r in zip(on.option[first][1:], on.rank_value[first][1:]):
        assert abs(r - vals[o]) < 1e-6
    sums = {}
    for d, o, p in zip(on.decision, on.option, on.prob):
        if o >= 0:
            sums[(d, o)] = sums.get((d, o), 0.0) + p
    assert sums and all(0 < p <= 1 + 1e-5 for p in sums.values())
    scores = np.array([r["score"] for r in results])
    assert (np.abs(on.target[:, None] - scores[None, :]).min(1) < 1e-5).all()


def test_batches_keep_decisions_whole():
    """With ranking on, training batches never split a decision's examples."""
    decision = np.repeat(np.arange(300), np.random.default_rng(0).integers(1, 9, 300))
    order = train.decision_order(decision, np.random.default_rng(1))
    assert sorted(order.tolist()) == list(range(len(decision)))
    for idx in train.decision_batches(decision, order, 64):
        ds_in = set(decision[idx].tolist())
        for d in ds_in:
            assert (decision[idx] == d).sum() == (decision == d).sum()


def test_learn_with_ranking():
    """A tiny run with no switches trains round 0 on inert ranking fields and
    round 1 on the net's search order, and saves nets that load back."""
    import learn
    cfg = {"name": "smoke-3", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 21, "val_seed": 22,
           "search": {"limit": selfplay.LIMIT}, "seed": 0, "rounds": {"n": 1, "every": 100},
           "switches": {}}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        runs = learn.learn(cfg, root=root, log=lambda *_: None)
        assert len(runs) == 2
        for run in runs:
            model, norm, meta = stsnet.load(run.model_path)
            assert not model.hp_loss and meta["switches"] == cfg["switches"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
