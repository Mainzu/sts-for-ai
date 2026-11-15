"""Tests for the Rust net evaluator (`sts.NetEvaluator`, built by
`stsnet.rust_evaluator`) against the PyTorch net. Run with
`python scripts/tests/test_rust_net.py` (plain asserts; every `test_*`
function runs) or with pytest."""

import os
import sys
import tempfile

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import stsnet  # noqa: E402

MODELS = os.path.join(os.path.dirname(__file__), "..", "..", "models")

_states = None


def stored_states(n=2000):
    """~n decision states from recorded greedy games: every encounter group,
    Ironclad and Silent, starter and extra-card decks."""
    global _states
    if _states is None:
        out = []
        for ch in ("ironclad", "silent"):
            for g in ("hallway", "elite", "boss"):
                specs = sts.make_specs(g, 24, seed=11, character=ch)
                for r in sts.run("greedy", specs, record=True, character=ch):
                    out += r["states"]
        rng = np.random.default_rng(0)
        _states = [out[i] for i in sorted(rng.choice(len(out), min(n, len(out)), replace=False))]
    return _states


def ranks(x):
    r = np.empty(len(x))
    r[np.argsort(x, kind="stable")] = np.arange(len(x))
    return r


def agree(rust, torch_):
    """Rank correlation and mean absolute difference."""
    return np.corrcoef(ranks(rust), ranks(torch_))[0, 1], float(np.abs(rust - torch_).mean())


def check_wiring(name):
    model, norm, meta = stsnet.load(os.path.join(MODELS, name))
    states = stored_states()
    feats = stsnet.features_for(meta)
    want = stsnet.Evaluator(model, norm)(feats.encode(states, heuristic=True))
    got = stsnet.rust_evaluator(model, norm, meta).score(states)
    rho, mad = agree(got, want)
    assert rho >= 0.99 and mad < 0.01, (name, rho, mad)
    return feats, states


def test_rust_net_wiring():
    """Score and ids-features nets: Rust and torch agree on stored states,
    some of which carry hook rows."""
    feats, states = check_wiring("value_effects.pt")
    b = feats.encode(states)
    assert (b["row_card"] >= 0).any() and (b["row_entity"] >= 0).any()
    check_wiring("value_ids.pt")


def saved_net(mode, hp_loss=False):
    """A fresh net of one kind, saved by `stsnet.save` and loaded back."""
    feats = sts.Features(mode)
    states = stored_states()[:200]
    ds = stsnet.Dataset.from_batches([feats.encode(states)], np.zeros(len(states), np.float32))
    model = stsnet.ValueNet(feats.dims, hp_loss=hp_loss)
    path = os.path.join(tempfile.mkdtemp(), "m.pt")
    stsnet.save(path, model, stsnet.Normalizer.fit(ds), {"card_repr": mode})
    return stsnet.load(path), states


def test_saved_nets_load_into_rust():
    for mode, hp in (("effects", False), ("ids", False), ("effects", True)):
        (model, norm, meta), states = saved_net(mode, hp)
        got = stsnet.rust_evaluator(model, norm, meta).score(states)
        want = stsnet.Evaluator(model, norm)(stsnet.features_for(meta).encode(states, heuristic=True))
        assert got.shape == (len(states),) and np.abs(got - want).max() < 1e-3, (mode, hp)


def test_rust_hp_net_wiring():
    """An HP-histogram net with a sharpened head (a fresh one's histograms
    are near uniform): histograms and scores agree with torch."""
    (model, norm, meta), _ = saved_net("effects", hp_loss=True)
    with torch.no_grad():
        model.head[1].weight.mul_(30)
    states = stored_states()
    batch = stsnet.features_for(meta).encode(states, heuristic=True)
    ev = stsnet.rust_evaluator(model, norm, meta)
    with torch.no_grad():
        want_p = stsnet.histogram(model, norm.tensors(batch)).numpy()
    logits = ev.score(states, raw=True)
    got_p = np.exp(logits - logits.max(1, keepdims=True))
    got_p /= got_p.sum(1, keepdims=True)
    assert np.abs(got_p - want_p).max() < 1e-3
    rho, mad = agree(ev.score(states), stsnet.Evaluator(model, norm)(batch))
    assert rho >= 0.99 and mad < 0.01, (rho, mad)


def fixed_histogram(p):
    """A Rust HP net whose histogram is `p` for every state."""
    (model, norm, meta), _ = saved_net("effects", hp_loss=True)
    with torch.no_grad():
        model.head[1].weight.zero_()
        logp = np.where(p > 0, np.log(np.maximum(p, 1e-30)), -1e4)  # exp(-1e4) is exactly 0
        model.head[1].bias.copy_(torch.from_numpy(logp.astype(np.float32)))
    return stsnet.rust_evaluator(model, norm, meta)


def one_bin(k):
    p = np.zeros(stsnet.N_BINS)
    p[k] = 1
    return p


def test_rust_external_formula():
    """Hand-made histograms: all mass below the HP wins (score >= 1), all
    above loses (0), the turn-limit and >= 150 bins never win even at 300
    HP, and a one-bin histogram on a won game's real HP loss scores what the
    engine scored (after Burning Blood's heal)."""
    c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], "jaw_worm", seed=1)
    hp = c.player_hp()
    below = np.where(stsnet.BIN_REP < hp, 1.0, 0.0) * stsnet.WINNABLE
    assert 1 <= fixed_histogram(below / below.sum()).score([c])[0] <= 2
    above = np.where(stsnet.BIN_REP >= hp, 1.0, 0.0)
    assert fixed_histogram(above / above.sum()).score([c])[0] == 0
    big = sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], "jaw_worm", seed=1, hp=300)
    for k in (stsnet.TURN_LIMIT_BIN, stsnet.N_BINS - 2):
        assert fixed_histogram(one_bin(k)).score([big])[0] == 0, k
    checked = 0
    for r in sts.run("greedy", sts.make_specs("hallway", 12, seed=5), record=True):
        s = r["states"][0]
        max_hp = sts.Features().encode([s], heuristic=True)["max_hp"][0]
        if not r["won"] or r["hp_end"] >= max_hp:
            continue  # the heal may have been capped: HP lost before it is unknown
        lost = s.player_hp() - (r["hp_end"] - 6)  # Burning Blood heals 6
        if 0 <= lost < 30 and lost < s.player_hp():
            got = fixed_histogram(one_bin(stsnet.bin_index(lost))).score([s])[0]
            assert abs(got - r["score"]) < 1e-5, (got, r["score"], lost)
            checked += 1
    assert checked >= 3, checked


def test_rust_net_threads():
    """`sts.run` with a NetEvaluator: the same games on 1 and 16 threads; it
    also drives `sts.search_action` and agrees with the Python net's pick."""
    model, norm, meta = stsnet.load(os.path.join(MODELS, "value_effects.pt"))
    ev = stsnet.rust_evaluator(model, norm, meta)
    specs = sts.make_specs("hallway", 16, seed=3)
    runs = [sts.run("search", specs, evaluator=ev, threads=t, record=True) for t in (1, 16)]
    for a, b in zip(*runs):
        assert [str(x) for x in a["actions"]] == [str(x) for x in b["actions"]] and a["score"] == b["score"]
    c = runs[0][0]["states"][0]
    feats = stsnet.features_for(meta)
    assert sts.search_action(c, ev) == sts.search_action(c, stsnet.Evaluator(model, norm), features=feats)


def test_ensemble_evaluator():
    """A list of NetEvaluators is an ensemble: one member searches like the
    net; [a, a] like a; an empty list or a non-net member is an error; and
    `bench.load_evaluator("x.pt+x.pt")` scores like "x.pt" (the exact mean
    is pinned by the Rust test `ensemble_scores_are_the_members_mean`)."""
    import bench
    path = os.path.join(MODELS, "value_effects.pt")
    model, norm, meta = stsnet.load(path)
    ev = stsnet.rust_evaluator(model, norm, meta)
    c = stored_states()[5]
    want = sts.search(c, ev, sample_k=2, turns=2, max_nodes=3000)
    for e in ([ev], (ev, ev)):
        got = sts.search(c, e, sample_k=2, turns=2, max_nodes=3000)
        assert str(got["action"]) == str(want["action"])
        assert np.allclose([v for _, v in got["options"]], [v for _, v in want["options"]], atol=1e-6)
    for bad in ([], [ev, "heuristic"]):
        try:
            sts.search(c, bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad!r} should be refused")
    ens = bench.load_evaluator(path + "+" + path)
    one = bench.load_evaluator(path)
    assert isinstance(ens.evaluator, list) and len(ens.evaluator) == 2
    assert str(sts.search_action(c, ens.evaluator)) == str(sts.search_action(c, one.evaluator))
    batch = ens.features.encode(stored_states()[:50], heuristic=True)
    assert np.allclose(ens.static(batch), one.static(batch), atol=1e-6)
    try:
        bench.load_evaluator(path + "+" + os.path.join(MODELS, "value_ids.pt"))
    except ValueError:
        pass
    else:
        raise AssertionError("members with different features should be refused")


def test_play_matches_python():
    """Slow (~1 min): models/value_effects.pt on every 4th tight fight,
    Rust (the bench's evaluator) vs Python inference: the win-rate
    intervals overlap on both halves."""
    import bench
    import bench_sets
    path = os.path.join(MODELS, "value_effects.pt")
    model, norm, meta = stsnet.load(path)
    rs = bench.load_evaluator(path)
    assert isinstance(rs.evaluator, sts.NetEvaluator)
    py = bench.Evaluator(path, stsnet.Evaluator(model, norm), stsnet.features_for(meta), None)
    for half, specs in bench_sets.load_set("tight").items():
        specs = bench.every(specs, 4)
        (_, lo_p, hi_p), (_, lo_r, hi_r) = (
            bench.wilson(sum(r["won"] for r in bench.run_specs(specs, e)), len(specs)) for e in (py, rs))
        assert lo_p <= hi_r and lo_r <= hi_p, (half, (lo_p, hi_p), (lo_r, hi_r))


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok ", name)
            n += 1
    print(f"{n} passed")
