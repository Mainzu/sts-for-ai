"""Tests for the value-net plumbing. Run with `python scripts/tests/test_net.py`
(plain asserts; every `test_*` function runs) or with pytest."""

import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import stsnet  # noqa: E402

STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def some_states(n=6):
    """A few decision states from greedy play, with different piles."""
    out = []
    c = sts.Combat(STARTER + ["Pommel Strike", "Cleave"], "two_louse", seed=3)
    while not c.is_over() and len(out) < n:
        out.append(c.clone())
        c.step(sts.greedy_action(c))
    return out


def tiny_dataset(mode):
    enc = sts.Features(mode)
    states = some_states()
    ds = stsnet.Dataset.from_batches([enc.encode(states)], np.linspace(0, 2, len(states), dtype=np.float32))
    return enc, states, ds


def test_dataset_gather_matches_encode():
    enc, states, ds = tiny_dataset("effects")
    idx = np.array([4, 1, 3])
    got = ds.batch(idx)
    want = enc.encode([states[i] for i in idx])
    for k in ("player", "monsters"):
        assert np.array_equal(got[k], want[k]), k
    # Card rows: same multiset per (state, pile), order may differ.
    for b in range(len(idx)):
        g = sorted(map(tuple, np.c_[got["card_pile"][got["card_state"] == b], got["cards"][got["card_state"] == b], got["card_count"][got["card_state"] == b]]))
        w = sorted(map(tuple, np.c_[want["card_pile"][want["card_state"] == b], want["cards"][want["card_state"] == b], want["card_count"][want["card_state"] == b]]))
        assert g == w
    assert np.allclose(got["target"], ds.target[idx])


def power_states():
    """Decision states whose cards and entities carry hook rows (Demon Form,
    Combust and Rupture cards; Cultist's Ritual; the player's own powers)."""
    out = []
    c = sts.Combat(STARTER + ["Demon Form", "Combust", "Rupture", "Bloodletting"], "cultist", seed=2)
    while not c.is_over() and len(out) < 8:
        out.append(c.clone())
        c.step(sts.greedy_action(c))
    return out


def rows_by_owner(b, s):
    """State `s`'s rows as a sorted list of (owner, row): owner is the entity,
    or the owning card's (pile, features) for card rows."""
    out = []
    for r in np.nonzero(b["row_state"] == s)[0]:
        if b["row_entity"][r] >= 0:
            owner = ("entity", int(b["row_entity"][r] - s * sts.ENTITIES))
        else:
            k = b["row_card"][r]
            owner = ("card", int(b["card_pile"][k]), tuple(b["cards"][k]))
        out.append((owner, tuple(b["rows"][r])))
    return sorted(out)


def test_dataset_gather_keeps_rows():
    enc = sts.Features("effects")
    states = power_states()
    want_all = enc.encode(states)
    assert (want_all["row_entity"] >= 0).any() and (want_all["row_card"] >= 0).any()
    ds = stsnet.Dataset.from_batches([want_all], np.zeros(len(states), np.float32))
    idx = np.array([5, 0, 3, 7])
    got = ds.batch(idx)
    want = enc.encode([states[i] for i in idx])
    for b in range(len(idx)):
        assert rows_by_owner(got, b) == rows_by_owner(want, b)
    # Every row points into its own state.
    rc = got["row_card"]
    assert np.array_equal(got["card_state"][rc[rc >= 0]], got["row_state"][rc >= 0])


def test_rows_reach_the_net():
    """Pooled rows feed the card and entity vectors: changing one row
    changes the output; reordering rows doesn't."""
    enc = sts.Features("effects")
    states = power_states()
    ds = stsnet.Dataset.from_batches([enc.encode(states)], np.zeros(len(states), np.float32))
    norm = stsnet.Normalizer.fit(ds)
    torch.manual_seed(0)
    model = stsnet.ValueNet(enc.dims)
    b = enc.encode(states)
    with torch.no_grad():
        y = model(norm.tensors(b))
        perm = np.random.default_rng(0).permutation(len(b["row_state"]))
        b2 = dict(b, rows=b["rows"][perm], row_card=b["row_card"][perm], row_entity=b["row_entity"][perm],
                  row_state=b["row_state"][perm])
        assert torch.allclose(y, model(norm.tensors(b2)), atol=1e-5)
        for which in ("row_entity", "row_card"):
            r = int(np.nonzero(b[which] >= 0)[0][0])
            b3 = dict(b, rows=b["rows"].copy())
            b3["rows"][r] += 3.0
            s = b["row_state"][r]
            assert not torch.isclose(model(norm.tensors(b3))[s], y[s]), which


def test_model_output_shape_and_range():
    for mode in ("effects", "ids"):
        enc, states, ds = tiny_dataset(mode)
        norm = stsnet.Normalizer.fit(ds)
        model = stsnet.ValueNet(enc.dims)
        with torch.no_grad():
            y = model(norm.tensors(enc.encode(states)))
        assert y.shape == (len(states),)
        assert torch.all((y >= 0) & (y <= 2))


def test_normalizer_constant_dims_finite():
    enc, states, ds = tiny_dataset("ids")
    norm = stsnet.Normalizer.fit(ds)
    t = norm.tensors(enc.encode(states))
    for k in ("player", "monsters", "cards", "rows"):
        assert torch.isfinite(t[k]).all(), k


def test_normalizer_stats_chunked():
    """The normalizer's mean / std, accumulated in chunks (no float64 copy
    of a whole training set), equal numpy's over the whole array."""
    rng = np.random.default_rng(0)
    x = (rng.normal(3.0, 2.0, (10_007, 5)) * [1, 10, 0, 1e3, 1]).astype(np.float32)
    m, s = stsnet.Normalizer.moments(x, chunk=1000)
    assert np.allclose(m, x.mean(0, dtype=np.float64), rtol=1e-9, atol=1e-9)
    want = x.std(0, dtype=np.float64)
    want[want < 1e-6] = 1.0
    assert np.allclose(s, want, rtol=1e-7) and s[2] == 1.0
    m0, s0 = stsnet.Normalizer.moments(np.zeros((0, 3), np.float32))
    assert (m0 == 0).all() and (s0 == 1).all()


def test_dead_monster_slots_ignored():
    enc, states, ds = tiny_dataset("effects")
    norm = stsnet.Normalizer.fit(ds)
    model = stsnet.ValueNet(enc.dims)
    b = enc.encode(states[:1])
    b2 = {k: v.copy() for k, v in b.items()}
    dead = b["monsters"][0, :, 0] == 0
    assert dead.any()
    b2["monsters"][0, dead, 1:] = 123.0  # garbage in empty slots
    with torch.no_grad():
        assert torch.allclose(model(norm.tensors(b)), model(norm.tensors(b2)))


def test_evaluator_inside_search():
    enc, states, ds = tiny_dataset("effects")
    norm = stsnet.Normalizer.fit(ds)
    model = stsnet.ValueNet(enc.dims)
    calls = []
    ev = stsnet.Evaluator(model, norm)

    def counted(batch):
        calls.append(batch["player"].shape[0])
        return ev(batch)

    r = sts.search(states[0], counted, features=enc)
    assert len(calls) == 1 and calls[0] == r["leaves"]
    assert r["action"] in states[0].legal_actions()
    res = sts.run("search", sts.make_specs("hallway", 4, seed=7), evaluator=ev, features=enc, threads=4)
    assert len(res) == 4 and all(isinstance(x["won"], bool) for x in res)


def test_save_load_round_trip(tmp=None):
    import tempfile

    # The net is built for its meta's encoder (the contract's `save` refuses
    # a net whose widths don't match it).
    meta = {"card_repr": "ids", "known_cards": ["Strike", "Defend", "Bash"]}
    enc, states = stsnet.features_for(meta), some_states()
    ds = stsnet.Dataset.from_batches([enc.encode(states)], np.linspace(0, 2, len(states), dtype=np.float32))
    norm = stsnet.Normalizer.fit(ds)
    model = stsnet.ValueNet(enc.dims)
    path = os.path.join(tempfile.mkdtemp(), "m.pt")
    stsnet.save(path, model, norm, meta)
    m2, n2, meta = stsnet.load(path)
    b = enc.encode(states)
    with torch.no_grad():
        assert torch.allclose(model(norm.tensors(b)), m2(n2.tensors(b)))
    assert meta["card_repr"] == "ids" and meta["known_cards"] == ["Strike", "Defend", "Bash"]
    f = stsnet.features_for(meta)
    assert f.card_repr == "ids"


def test_training_pools_exclude_held_out():
    import selfplay

    check9 = set(sts.held_out_card_names())
    assert not check9 & set(selfplay.TRAIN_POOL)
    assert not selfplay.HELD_OUT_ALL & set(selfplay.TRAIN_POOL)
    assert not (check9 | selfplay.HELD_OUT_ALL) & set(selfplay.KNOWN_CARDS)
    assert not {"DemonForm", "Rage"} & set(selfplay.KNOWN_POWERS)
    rng = np.random.default_rng(0)
    for _ in range(200):
        assert not check9 & set(selfplay.held_out_deck(rng))


def test_meta_vocab_round_trip():
    """A net's meta holds the vocabularies its features were built with."""
    import selfplay

    for mode in ("effects", "ids"):
        meta = selfplay.meta_vocab(mode)
        assert stsnet.features_for(dict(meta, card_repr=mode)).vocab == selfplay.features(mode).vocab


def test_net_search_does_not_leak_threads():
    """Each Rust search thread calling a net must not leave an OpenMP pool
    behind: repeated searches in one process keep the OS thread count flat
    (it grew by ~300 per run and crashed the sweep with "Cannot create
    thread"). Runs in a child process that imports through train, as
    learn.py does, so the environment is the one the sweep gets."""
    import subprocess
    child = """
import os, subprocess, sys
sys.path.insert(0, %r)
import train, stsnet, sts, selfplay
def n():
    out = subprocess.run(["powershell", "-NoProfile", "-c", f"(Get-Process -Id {os.getpid()}).Threads.Count"],
                         capture_output=True, text=True).stdout
    return int(out.strip())
model, norm, meta = stsnet.load(os.path.join(sys.path[0], "..", "models", "value_effects.pt"))
ev = stsnet.Evaluator(model, norm)
specs = [("jaw_worm", selfplay.STARTER, s) for s in range(64)]
counts = []
for _ in range(3):
    sts.run("search", specs, evaluator=ev, features=stsnet.features_for(meta))
    counts.append(n())
print(counts)
""" % os.path.join(os.path.dirname(__file__), "..")
    env = {k: v for k, v in os.environ.items() if k != "OMP_NUM_THREADS"}
    out = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr[-2000:]
    counts = eval(out.stdout.strip().splitlines()[-1])
    assert counts[-1] - counts[0] < 50, counts


def test_net_search_settings():
    """Search threads calling a net contend for Python's lock: torch runs
    each tiny call on one thread, the lock is handed over often, and net
    searches use a few runner threads, not every core (profiled: many threads
    were slower than 1)."""
    assert torch.get_num_threads() == 1
    assert sys.getswitchinterval() <= 0.001
    assert stsnet.NET_THREADS == min(4, os.cpu_count() or 1)


def test_net_runs_use_net_threads():
    """Self-play and bench runs with a Python net pass NET_THREADS; heuristic
    and Rust-net runs (the bench's net) keep every core."""
    import bench
    import registry
    seen = []
    real = sts.run
    sts.run = lambda *a, **k: seen.append(k.get("threads")) or []
    cap = os.environ.pop("STS_JOB_THREADS", None)  # a queued test run caps every unthreaded search
    try:
        model, norm, meta = stsnet.load(os.path.join(os.path.dirname(__file__), "..", "..", "models", "value_effects.pt"))
        ev = stsnet.Evaluator(model, norm)
        specs = [("jaw_worm", STARTER, 1)]
        registry.play(specs, {}, evaluator=ev, features=stsnet.features_for(meta))
        registry.play(specs, {})
        registry.play(specs, {}, evaluator=stsnet.rust_evaluator(model, norm, meta))
        spec = {"encounter": "jaw_worm", "deck": STARTER, "seed": 1, "hp": None, "character": "ironclad"}
        bench.run_specs([spec], bench.load_evaluator(os.path.join(os.path.dirname(__file__), "..", "..", "models",
                                                                   "value_effects.pt")))
        bench.run_specs([spec])
    finally:
        sts.run = real
        if cap is not None:
            os.environ["STS_JOB_THREADS"] = cap
    assert seen == [stsnet.NET_THREADS, None, None, None, None], seen


def test_net_search_results_do_not_depend_on_threads():
    """The thread count only changes speed: each game is seeded on its own."""
    model, norm, meta = stsnet.load(os.path.join(os.path.dirname(__file__), "..", "..", "models", "value_effects.pt"))
    ev, feats = stsnet.Evaluator(model, norm), stsnet.features_for(meta)
    specs = [("jaw_worm", STARTER, s) for s in range(8)]
    runs = [sts.run("search", specs, evaluator=ev, features=feats, threads=t, record=True) for t in (1, 4)]
    for a, b in zip(*runs):
        assert [str(x) for x in a["actions"]] == [str(x) for x in b["actions"]] and a["score"] == b["score"]


def test_net_search_does_not_leak_memory():
    """Each Rust search thread calling a net must not leave MKL's per-thread
    memory pool behind when it exits: repeated searches in one process keep
    the committed memory flat (it grew ~5.6 GB per tight-fight run and the
    sweep died with MemoryError). Child process importing through train, as
    learn.py does, without the environment variable set."""
    import subprocess
    child = """
import ctypes, ctypes.wintypes as w, os, sys
sys.path.insert(0, %r)
import train, stsnet, sts, selfplay
class PMC(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("faults", w.DWORD)] + [(k, ctypes.c_size_t) for k in
                ("peak_ws", "ws", "qpp", "qp", "qpnp", "qnp", "commit", "peak_commit")]
k32 = ctypes.windll.kernel32
k32.GetCurrentProcess.restype = w.HANDLE
ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD]
def commit():
    p = PMC(); p.cb = ctypes.sizeof(p)
    ctypes.windll.psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(p), p.cb)
    return p.commit / 2 ** 20
model, norm, meta = stsnet.load(os.path.join(sys.path[0], "..", "models", "value_effects.pt"))
ev = stsnet.Evaluator(model, norm)
specs = [("jaw_worm", selfplay.STARTER, s) for s in range(64)]
mb = []
for _ in range(4):
    sts.run("search", specs, evaluator=ev, features=stsnet.features_for(meta))
    mb.append(commit())
print(mb)
""" % os.path.join(os.path.dirname(__file__), "..")
    env = {k: v for k, v in os.environ.items() if k != "MKL_DISABLE_FAST_MM"}
    out = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr[-2000:]
    mb = eval(out.stdout.strip().splitlines()[-1])
    assert mb[-1] - mb[0] < 100, mb


def train_states(n_games=8):
    """Decision states from greedy play of a few seeded combats."""
    out = []
    for seed in range(n_games):
        c = sts.Combat(STARTER + ["Pommel Strike", "Cleave"], "jaw_worm", seed=seed)
        while not c.is_over():
            out.append(c.clone())
            c.step(sts.greedy_action(c))
    return out


def train_dataset(n_games=8, offset=0.0):
    states = train_states(n_games)
    target = ((np.arange(len(states)) % 7) / 3.5 + offset).clip(0, 2).astype(np.float32)
    return stsnet.Dataset.from_batches([sts.Features("effects").encode(states)], target)


def weights_hash(model):
    import hashlib
    h = hashlib.sha256()
    for k, v in sorted(model.state_dict().items()):
        h.update(k.encode())
        h.update(v.detach().numpy().tobytes())
    return h.hexdigest()[:16]


# Pinned on the code before warm-start's replay (docs/specs/warm-start.md step 2);
# re-pinned when the Act-1 bosses widened the default vocabulary (2 powers, Burn),
# and when threshold and held rows added two columns (threshold-and-held-rows spec),
# and when the rules-engine series added columns (decisions "Series row kinds
# are opt-in"), and when mutated-monsters stage B added three powers and a
# trigger (docs/specs/mutated-monsters-b.md), and when exhaust-cards (C1) added
# six effect and three player columns (docs/specs/exhaust-cards.md), and when
# exhaust triggers (C2) added the CardExhausted trigger column
# (docs/specs/exhaust-triggers.md), and when quantity amounts (C4) added the
# block_of_k and apply_of_k scalars (docs/specs/quantity-amounts.md), and
# when cost changes (C5) added the cost_less_per_hp_loss card column
# (docs/specs/cost-changes.md), and when card upgrades (C6) added the
# pick_upgrade and upgrade_hand scalars and the pick_upgrade_from_hand player
# column (docs/specs/card-upgrades.md), and when card rules added the three
# Rule(...) row trigger columns (docs/specs/card-rules.md), and when Clash's
# play condition dropped the only_attacks_in_hand card column and added the
# Rule(PlayableIf) and HandAll(...) row columns, and when Red Skull's crossing
# triggers added the OwnerBloodied and OwnerUnbloodied row trigger columns
# (docs/specs/red-skull-strength.md), and when relics as their own entity
# added the CombatStartPreDraw, CombatStart and CounterIs row columns,
# grant_relic and the relic row-only columns (docs/specs/relic-entity.md),
# and when potions added the Potion(Use) trigger and potion_potency row
# columns (docs/specs/potions.md), and when the fight vocabulary added the
# OpponentDied, CombatWon, OwnerBlockIs and Applying(...) row columns
# (docs/specs/fight-vocabulary.md), and when the after-block passes added
# four Replace(...) triggers, AmountAtMost and replace_at_least
# (docs/specs/after-block.md), and when Champion Belt added the OwnerApplied
# row trigger column (docs/specs/act1-singles.md).
TRAIN_PIN = "28200ebe851eeeb5"


def test_train_unchanged():
    """A fresh training without the warm-start arguments gives the same
    weights as before they existed."""
    import shutil
    import tempfile

    import train
    ds = train_dataset()
    old = train.EPOCHS
    train.EPOCHS = 2
    try:
        model, _, hist = train.train("effects", ds, ds, seed=0, log=lambda *a: None)
    finally:
        train.EPOCHS = old
    got = weights_hash(model)
    assert TRAIN_PIN is None or got == TRAIN_PIN, (got, TRAIN_PIN)
    print("train hash", got, len(ds), hist)


def test_replay_share():
    """Replay batches: every new example once per epoch, about `share` of
    each batch from the pool; a warm-started training with replay runs."""
    import shutil
    import tempfile

    import train
    rng = np.random.default_rng(0)
    for n_new, n_pool in ((5000, 20000), (3000, 1000)):
        for _ in range(2):
            chunks = train.replay_batches(n_new, n_pool, 0.5, rng)
            idx = np.concatenate(chunks)
            new = np.sort(idx[idx < n_new])
            assert np.array_equal(new, np.arange(n_new))
            assert idx.max() < n_new + n_pool
            for c in chunks[:-1]:
                assert abs((c >= n_new).mean() - 0.5) <= 0.1, (c >= n_new).mean()
    ds, pool = train_dataset(), train_dataset(4, 0.3)
    norm = stsnet.Normalizer.fit(ds)
    start = stsnet.ValueNet(sts.Features("effects").dims)
    before = weights_hash(start)
    model, n2, hist = train.train("effects", ds, ds, seed=0, log=lambda *a: None, start=(start, norm),
                                  replay=pool, epochs=2, lr=1e-4)
    assert model is start and n2 is norm and len(hist) == 2 and weights_hash(model) != before


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok ", name)
            n += 1
    print(f"{n} passed")


def test_pool_epoch_matches_whole_pool():
    """train.pool_epoch's batches hold the same examples, in the same order,
    as batches into Dataset.concat([new, pool]) with the whole pool, also
    with the pool memory-mapped from a directory and its target re-weighted
    in memory; the mapped pool's arrays stay maps."""
    import shutil
    import tempfile

    import train
    _, _, new = tiny_dataset("effects")
    root = tempfile.mkdtemp(prefix="pool-epoch-")
    try:
        path = os.path.join(root, "pool")
        w = stsnet.DatasetWriter(path)
        w.append(new)
        w.append(new)
        w.close()
        pool = stsnet.Dataset.load(path)
        pool.target = np.asarray(pool.target) * 0.5 + 0.25  # as finetune.weigh_targets: in memory
        whole = stsnet.Dataset.concat([new, pool])
        chunks = train.replay_batches(len(new), len(pool), 0.5, np.random.default_rng(3), size=4)
        ds, re = train.pool_epoch(new, pool, chunks)
        assert len(ds) < len(whole)
        for a, b in zip(chunks, re):
            x, y = whole.batch(a), ds.batch(b)
            assert x.keys() == y.keys()
            for k in x:
                assert np.array_equal(x[k], y[k]), k
        assert isinstance(pool.rows, np.memmap)
        del pool, whole, ds
    finally:
        shutil.rmtree(root, ignore_errors=True)
