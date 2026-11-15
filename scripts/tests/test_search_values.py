"""Recorded search values (`sts.run(values=True)`, the ranking term's order)
and labels by round: real outcomes only (Amendments 1 and 2).
Run with `python scripts/tests/test_search_values.py` or with pytest."""

import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import registry  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import stsnet  # noqa: E402

CONFIG = {"name": "tiny", "sample_seed": 5, "search": {"limit": selfplay.LIMIT}}


def tiny():
    return selfplay.make_specs(2, 11, selfplay.train_deck)


def test_run_records_the_searchs_option_values():
    """`run(values=True)` gives, per decision, the options and values the
    agent's search computed: the same as `search` on that state (one-turn
    search without sampling is deterministic), and the chosen action is in
    the best option."""
    specs, _ = tiny()
    res = sts.run("search", specs, record=True, values=True, limit=selfplay.LIMIT)
    n = 0
    for r in res:
        assert len(r["values"]) == len(r["actions"]) == len(r["states"])
        for s, a, vals in zip(r["states"], r["actions"], r["values"]):
            ref = sts.search(s, limit=selfplay.LIMIT)
            assert [list(acts) for acts, _ in vals] == [list(acts) for acts, _ in ref["options"]]
            np.testing.assert_allclose([v for _, v in vals], [v for _, v in ref["options"]])
            best = max(range(len(vals)), key=lambda i: vals[i][1])
            assert a in vals[best][0]
            n += 1
    assert n > 0


def test_run_default_output_unchanged():
    specs, _ = tiny()
    for r in sts.run("search", specs[:2], record=True, limit=selfplay.LIMIT):
        assert "values" not in r
    for r in sts.run("search", specs[:2], limit=selfplay.LIMIT):
        assert "values" not in r and "states" not in r


def test_labels_by_round():
    """Round 0 (heuristic games) gets inert ranking fields only; from round 1
    the options' afterstates join for the ranking term; validation labels
    are real outcomes; a leftover switch 1 key changes nothing."""
    import learn
    for cfg in ({"switches": {}}, {"switches": {"search_values": True, "ranking": True}}):
        assert learn.labels(cfg, 0) == {"rank": True}
        assert learn.labels(cfg, 1) == learn.labels(cfg, 3) == {"afterstates": True}
        assert learn.labels(cfg, None) is None
    hp = {"switches": {"hp_loss": True}}
    assert learn.labels(hp, 0) == {"rank": True, "hp_loss": True} and learn.labels(hp, None) == {"hp_loss": True}
    assert learn.labels(hp, 1) == {"afterstates": True, "hp_loss": True}


def test_afterstate_labels_are_real_outcomes():
    """From round 1, every example (decision states and the options'
    afterstates) is labelled with its game's real score; the search values
    only order the options."""
    import learn
    specs, groups = tiny()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        ds, results = registry.selfplay(specs, groups, CONFIG, root=root)
        off = registry.examples(ds, "effects", root=root)
        on = registry.examples(ds, "effects", root=root, labels=learn.labels({}, 1))
    assert len(on) > len(off) and (on.option >= 0).any()
    np.testing.assert_array_equal(on.target, on.outcome)
    scores = np.array([r["score"] for r in results], np.float32)
    assert np.isin(on.target, scores).all() and learn.label_scale(on) == 0.0


def test_round_0_labels_are_real_outcomes():
    """No heuristic in labels: on heuristic-teacher games, round 0's labels
    equal the real outcomes exactly (the game's score,
    or with switch 6 the HP lost to the end of its no-death game), the same
    as with every switch off, and the ranking fields are inert."""
    import learn
    specs, groups = tiny()
    for hp in (False, True):
        cfg = {"switches": {"hp_loss": True} if hp else {}}
        gen = {**CONFIG, **({"no_death": True} if hp else {})}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
            ds, results = registry.selfplay(specs, groups, gen, root=root)
            on = registry.examples(ds, "effects", root=root, labels=learn.labels(cfg, 0))
            off = registry.examples(ds, "effects", root=root, labels={"hp_loss": True} if hp else None)
        np.testing.assert_array_equal(on.target, off.target)
        assert (on.option == -1).all() and len(set(on.decision)) == len(on)
        if hp:
            # A one-hot of the real HP lost: exactly its bin (the cap's two
            # bins: >= 150 or the turn limit); read back as expected HP lost,
            # off only by the wide bins' rounding.
            assert (on.target.sum(1) == 1).all() and ((on.target == 0) | (on.target == 1)).all()
            capped = on.outcome == selfplay.HP_CAP
            hot = on.target.argmax(1)
            assert (hot[~capped] == [stsnet.bin_index(x) for x in on.outcome[~capped]]).all()
            assert np.isin(hot[capped], [stsnet.N_BINS - 2, stsnet.TURN_LIMIT_BIN]).all()
            assert learn.label_scale(on) <= 5.0
        else:
            np.testing.assert_array_equal(on.target, on.outcome)
            scores = np.array([r["score"] for r in results], np.float32)
            assert np.isin(on.target, scores).all()
            assert learn.label_scale(on) == 0.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")


def test_search_line_key():
    """docs/specs/line-step.md: `search` also returns the principal line,
    which starts with the chosen action."""
    specs, _ = tiny()
    r = sts.run("search", specs[:1], record=True, limit=selfplay.LIMIT)[0]
    s = r["states"][0]
    one = sts.search(s, limit=selfplay.LIMIT)
    assert one["line"][0] == one["action"]
    two = sts.search(s, limit=selfplay.LIMIT, turns=2, sample_k=2, max_nodes=2000, seed=3)
    assert two["line"][0] == two["action"]
    assert len(two["line"]) >= 1
