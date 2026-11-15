"""Tests for curriculum labels (docs/specs/curriculum.md). Step 1's pins hold
today's (v5) example builds and training loss, so later steps can show what
they leave unchanged. Run with `python scripts/tests/test_curriculum.py`.

The pinned datasets (scripts/tests/data/curriculum/datasets) and digests
(curriculum_pins.json) were written before the curriculum work by
`python scripts/tests/test_curriculum.py --pin --datasets`; `--pin` alone
rewrites only the digests and losses. Rerun either only for an intended
change to what they pin (step 3 added the label-input fields and weights)."""

import hashlib
import gc
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import learn  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import train  # noqa: E402
from stsnet import Dataset  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
FIXTURE = os.path.join(DATA, "curriculum")
PINS = os.path.join(DATA, "curriculum_pins.json")
# The pinned datasets: a score dataset whose games have search values (as
# self-play rounds record them) and a switch 6 (no-death) one.
CONFIGS = {
    "score": {"name": "pin-score", "sample_seed": 5, "search": {"limit": selfplay.LIMIT}},
    "hp": {"name": "pin-hp", "sample_seed": 6, "search": {"limit": selfplay.LIMIT}, "no_death": True},
}
# Each dataset's examples under learn.labels of round 0, round >= 1 and validation.
LEARN_CFG = {"score": {}, "hp": {"switches": {"hp_loss": True}}}
ROUNDS = {"r0": 0, "r1": 1, "val": None}


def make_datasets(root):
    """{kind: dataset id} of the pinned datasets, played into `root`."""
    out = {}
    for i, (kind, config) in enumerate(CONFIGS.items()):
        specs, groups = selfplay.make_specs(2, 31 + i, selfplay.varied_deck, hp_fn=selfplay.varied_hp)
        out[kind], _ = registry.selfplay(specs, groups, config, root=root)
    return out


def fixture_root():
    """A temporary registry root holding a copy of the pinned datasets."""
    d = tempfile.mkdtemp()
    shutil.copytree(os.path.join(FIXTURE, "datasets"), os.path.join(d, "datasets"))
    return d


def dataset_ids():
    with open(PINS, encoding="utf-8") as f:
        return json.load(f)["datasets"]


def digest(ds):
    """{field: sha256 prefix} of every array an example set holds."""
    from stsnet import Dataset
    out = {"n": len(ds)}
    for k in Dataset.FIELDS + Dataset.EXTRA:
        v = getattr(ds, k)
        if v is not None:
            out[k] = f"{v.dtype}{list(v.shape)}:" + hashlib.sha256(v.tobytes()).hexdigest()[:16]
    return out


def builds(root, ids):
    """{kind: {round: digest}} of the example builds as training loads them."""
    return {kind: {name: digest(learn.load_examples(LEARN_CFG[kind], ids[kind], rnd, root=root))
                   for name, rnd in ROUNDS.items()}
            for kind in CONFIGS}


def losses(root, ids):
    """{case: (first epoch's mean training loss, val loss) as float hex} of
    one epoch of train.train on the pinned examples: score with and without
    the ranking term, and switch 6 with it."""
    out = {}
    cases = {"score": ("score", 0.0), "score_rank": ("score", learn.RANK_WEIGHT), "hp_rank": ("hp", learn.RANK_WEIGHT)}
    epochs = train.EPOCHS
    train.EPOCHS = 1
    try:
        for name, (kind, rank) in cases.items():
            cfg = LEARN_CFG[kind]
            tr = registry.examples(ids[kind], "effects", root=root, labels=learn.labels(cfg, 1))
            tr.weight = np.ones(len(tr), np.float32)  # explicit weight 1: the weighted loss path
            val = registry.examples(ids[kind], "effects", root=root, labels=learn.labels(cfg, None))
            curves = {}
            train.train("effects", tr, val, 0, lambda *_: None, curves, rank_weight=rank, hp_loss=learn.hp_loss(cfg))
            out[name] = [float(curves["train"][0]).hex(), float(curves["val"][0]).hex()]
    finally:
        train.EPOCHS = epochs
    return out


def pin(datasets=False):
    """Rewrites the pinned digests and losses; `datasets` also replays new
    fixture datasets (otherwise the committed pre-change ones stay)."""
    if datasets or not os.path.exists(PINS):
        shutil.rmtree(FIXTURE, ignore_errors=True)
        ids = make_datasets(FIXTURE)
    else:
        ids = dataset_ids()
    root = fixture_root()
    try:
        pins = {"datasets": ids, "builds": builds(root, ids), "losses": losses(root, ids)}
    finally:
        shutil.rmtree(root, ignore_errors=True)
    with open(PINS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pins, f, indent=1, sort_keys=True)
        f.write("\n")


def pinned(key):
    with open(PINS, encoding="utf-8") as f:
        return json.load(f)[key]


def test_old_dataset_builds():
    """The pinned (pre-curriculum) score dataset builds the same examples as
    before, for round 0, round >= 1 and validation."""
    root = fixture_root()
    try:
        got = builds(root, dataset_ids())["score"]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert got == pinned("builds")["score"], got


def test_chunked_build_same():
    """A cache built one game per chunk equals one built in a single chunk
    (decision ids and ragged offsets carried across chunks)."""
    import stsnet
    root = fixture_root()
    try:
        ds = dataset_ids()["score"]
        labels = learn.labels(LEARN_CFG["score"], 1)
        chunk = registry.CHUNK
        built = []
        for n in (chunk, 1):
            registry.CHUNK = n
            shutil.rmtree(registry.cache_dir(root), ignore_errors=True)
            d = registry.examples(ds, "effects", root=root, labels=labels)
            built.append({k: np.array(getattr(d, k)) for k in stsnet.Dataset.FIELDS + stsnet.Dataset.EXTRA
                          + stsnet.Dataset.CODEC if getattr(d, k) is not None})
            del d
            gc.collect()
        registry.CHUNK = chunk
        a, b = built
        assert a.keys() == b.keys()
        for k in a:
            assert a[k].dtype == b[k].dtype and np.array_equal(a[k], b[k]), k
    finally:
        registry.CHUNK = chunk
        shutil.rmtree(root, ignore_errors=True)


def test_writer_checks_lengths():
    """A part missing an array's rows is refused, and nothing is left."""
    import stsnet
    root = fixture_root()
    try:
        ds = dataset_ids()["score"]
        d = registry.examples(ds, "effects", root=root, labels=learn.labels(LEARN_CFG["score"], 1))
        path = os.path.join(root, "bad")
        w = stsnet.DatasetWriter(path)
        w.append(d.take(np.arange(3)))
        w._write("target", np.zeros(1, np.float32))
        try:
            w.close()
            raise AssertionError("not refused")
        except ValueError as e:
            assert "different lengths" in str(e)
        assert not os.path.exists(path) and not os.path.exists(w.tmp)
        del d
        gc.collect()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_hp_loss_unchanged():
    """Switch 6's examples (histogram targets, HP-lost outcomes, ranking
    fields) are the pinned v5 ones."""
    root = fixture_root()
    try:
        got = builds(root, dataset_ids())["hp"]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert got == pinned("builds")["hp"], got


def test_weight_one_identity():
    """One epoch of training on the pinned examples gives today's training
    and validation loss to the bit (score with and without the ranking
    term, switch 6 with it). From step 2 every value-loss weight is 1 here."""
    root = fixture_root()
    try:
        got = losses(root, dataset_ids())
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert got == pinned("losses"), got


def test_value_weight():
    """The value loss is the batch mean of weight x per-example loss (MSE,
    or switch 6's cross-entropy): weight 1 is the plain mean to the bit, a
    weight-0 example adds nothing, a weight-2 one counts twice; no weights
    (None) is weight 1."""
    g = torch.Generator().manual_seed(0)
    pred, y = torch.randn(8, generator=g), torch.randn(8, generator=g)
    logp = torch.log_softmax(torch.randn(8, 5, generator=g), 1)
    hist = torch.softmax(torch.randn(8, 5, generator=g), 1)
    w = torch.tensor([1, 0, 2, 1, 0, 1, 3, 1], dtype=torch.float32)
    for hp, a, b in ((False, pred, y), (True, logp, hist)):
        per = -(b * a).sum(1) if hp else (a - b) ** 2
        plain = train.cross_entropy(a, b) if hp else ((a - b) ** 2).mean()
        assert train.value_loss(a, b, None, hp).item() == plain.item()
        assert train.value_loss(a, b, torch.ones(8), hp).item() == plain.item()
        want = float((w.double() * per.double()).sum() / 8)
        assert abs(train.value_loss(a, b, w, hp).item() - want) < 1e-6, hp
        moved = a.clone()
        moved[1] = moved[1] + 10  # a weight-0 example's prediction doesn't matter
        assert train.value_loss(moved, b, w, hp).item() == train.value_loss(a, b, w, hp).item()


def test_cache_ingredients():
    """A v6 cache holds each example's label inputs (search number, kind,
    played, distance, codec bytes), and the labels are applied when it's
    loaded: a later exact-value source (here a stub lookup) changes labels
    on the next load without rebuilding the cache."""
    import sts
    root = fixture_root()
    try:
        ds_id = dataset_ids()["score"]
        cfg = LEARN_CFG["score"]
        plain = learn.load_examples(cfg, ds_id, 1, root=root)
        path = registry.cache_path(ds_id, "effects", root, learn.labels(cfg, 1))
        assert os.path.isdir(path) and f"-{registry.CACHE_VERSION}" in path
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(cfg, 1))
        n = len(raw)
        assert raw.codec_len.shape == (n,) and raw.codec_len.min() > 0
        codes = [raw.codec_bytes(i) for i in range(n)]
        assert all(sts.Combat.decode(c).encode() == c for c in codes[:50])
        dec = raw.option == -1
        assert (raw.kind[dec] == 0).all() and (raw.played[dec] == 1).all()
        assert np.array_equal(raw.search[dec], raw.rank_value[dec])  # a decision's best option value
        assert (raw.distance >= 0).all()
        for i in np.flatnonzero(~dec):  # an afterstate takes its decision's distance
            first = np.flatnonzero(raw.decision == raw.decision[i])[0]
            assert raw.distance[i] == raw.distance[first]
        assert set(np.unique(raw.kind[~dec])) <= {1, 2, 3}
        # Every decision has exactly one played option, whose afterstates are played.
        assert np.array_equal(plain.target, raw.outcome)  # rung 5 only: labels are the outcomes
        mtime = os.path.getmtime(path)
        played = np.flatnonzero(raw.played == 1)[:5]
        planted = {codes[i]: 0.5 + 0.01 * k for k, i in enumerate(played)}
        orig = registry.load_games
        registry.load_games = lambda *a, **k: (_ for _ in ()).throw(AssertionError("cache rebuilt"))
        try:
            got = learn.load_examples(cfg, ds_id, 1, root=root,
                                      exact=lambda cs: [(planted[c], None) if c in planted else None for c in cs])
        finally:
            registry.load_games = orig
        assert os.path.getmtime(path) >= mtime
        want = raw.outcome.copy()
        for i, c in enumerate(codes):  # equal states share a value
            if c in planted:
                want[i] = np.float32(planted[c])
        assert np.array_equal(got.target, want)
        assert got.codec is None  # dropped after labelling: training doesn't keep the bytes
        # The same through a real database filled after the cache was built.
        solved = fill_db(root, codes, raw.distance)
        assert solved
        registry.load_games = lambda *a, **k: (_ for _ in ()).throw(AssertionError("cache rebuilt"))
        try:
            got = learn.load_examples(cfg, ds_id, 1, root=root, exact=learn.db_lookup(learn.open_db(cfg, root)))
        finally:
            registry.load_games = orig
        hit = np.array([c in solved for c in codes])
        assert np.array_equal(got.target[hit], np.array([solved[c][0] for c in codes if c in solved], np.float32))
        assert np.array_equal(got.target[~hit], raw.outcome[~hit])
    finally:
        shutil.rmtree(root, ignore_errors=True)


_FILLED = []  # the database fill_db built once per test run (its folder)


def fill_db(root, codes, distance, max_nodes=20_000):
    """Puts into `root` a database of the decision states among `codes`
    (codec bytes) at distance <= 1 solved with every solved state kept
    (built once per test run, then copied); returns {bytes: (value, option
    values)} of the examples found there, as a fresh handle reads them.
    A root is solved into the database only when it fits `max_nodes`: a
    failed solve still stores its finished subtrees, which made 90% of the
    rows (380k of them) and held the exact tests' memory over 1.7 GB."""
    import sts
    if not _FILLED:
        _FILLED.append(tempfile.mkdtemp())
        db = sts.SolvedDb(os.path.join(_FILLED[0], "train.sqlite"))
        seen = set()
        for i in np.flatnonzero(np.asarray(distance) <= 1):
            c = codes[i]
            if c in seen:
                continue
            seen.add(c)
            try:
                if sts.solve(sts.Combat.decode(c), max_nodes=max_nodes) is not None:
                    sts.solve(sts.Combat.decode(c), max_nodes=max_nodes, store=sts.SolveStore(min_nodes=0, db=db))
            except ValueError:
                continue  # not at a decision
        del db
    shutil.copytree(_FILLED[0], os.path.join(root, "db"), dirs_exist_ok=True)
    db = sts.SolvedDb(learn.db_path(root))
    return {c: e for c, e in zip(codes, db.lookup(codes)) if e is not None}


def db_rows(root):
    import sts
    st = sts.SolvedDb(learn.db_path(root)).stats()
    return sum(v[2] + v[4] for v in st["versions"])  # full and trivial rows


def test_ladder_exact():
    """An example whose state is in the database takes its exact value,
    whatever its distance from the end; the rest keep their outcome."""
    root = fixture_root()
    try:
        cfg = LEARN_CFG["score"]
        ds_id = dataset_ids()["score"]
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(cfg, 1))
        codes = [raw.codec_bytes(i) for i in range(len(raw))]
        solved = fill_db(root, codes, raw.distance)
        got = learn.load_examples(cfg, ds_id, 1, root=root, exact=learn.db_lookup(learn.open_db(cfg, root)))
        hit = np.array([c in solved for c in codes])
        assert hit.any() and (~hit).any()
        assert len(set(raw.distance[hit].tolist())) > 1, "hits at one distance only"
        for i in np.flatnonzero(hit):
            assert got.target[i] == np.float32(solved[codes[i]][0])
        assert np.array_equal(got.target[~hit], raw.outcome[~hit])
        # Round 0 (decision states only) takes rung 1 too.
        raw0 = registry.examples(ds_id, "effects", root=root, labels=learn.labels(cfg, 0))
        r0 = learn.load_examples(cfg, ds_id, 0, root=root, exact=learn.db_lookup(learn.open_db(cfg, root)))
        found = [solved.get(raw0.codec_bytes(i)) for i in range(len(raw0))]
        assert any(f is not None for f in found)
        assert np.array_equal(r0.target, np.array([o if f is None else f[0] for o, f in zip(raw0.outcome, found)],
                                                  np.float32))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_not_played_rank_exact():
    """A decision found in the database ranks its options' afterstates by
    the options' exact values; other decisions keep their search values."""
    root = fixture_root()
    try:
        cfg = LEARN_CFG["score"]
        ds_id = dataset_ids()["score"]
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(cfg, 1))
        codes = [raw.codec_bytes(i) for i in range(len(raw))]
        solved = fill_db(root, codes, raw.distance)
        got = learn.load_examples(cfg, ds_id, 1, root=root, exact=learn.db_lookup(learn.open_db(cfg, root)))
        dec = {int(raw.decision[i]): solved[codes[i]][1] for i in np.flatnonzero(raw.option == -1) if codes[i] in solved}
        assert dec
        changed = 0
        for i in np.flatnonzero(raw.option >= 0):
            opts = dec.get(int(raw.decision[i]))
            want = raw.rank_value[i] if opts is None else np.float32(opts[raw.option[i]])
            assert got.rank_value[i] == want
            changed += opts is not None
        assert changed
        assert (got.weight[got.played == 0] == 0).all()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_exact_share():
    """The database's exact examples: at most `exact_cap`, decision states
    weighing `exact_share` of the total value weight (to 1e-6), afterstates
    ranking only, and the same draw for the same seed."""
    root = fixture_root()
    try:
        ds_id = dataset_ids()["score"]
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(LEARN_CFG["score"], 1))
        fill_db(root, [raw.codec_bytes(i) for i in range(len(raw))], raw.distance)
        cfg = {**LEARN_CFG["score"], "exact_cap": 60, "exact_share": 0.25}
        train_ds, _, _ = learn.training_set(cfg, [(ds_id, 1)], root=root)
        exact = train_ds.distance == -1
        assert 0 < exact.sum() <= 60
        w = train_ds.weight.astype(np.float64)
        assert abs(w[exact].sum() / w.sum() - 0.25) < 1e-6
        assert (train_ds.weight[exact & (train_ds.option >= 0)] == 0).all()
        assert (train_ds.weight[exact & (train_ds.option == -1)] > 0).all()
        db = learn.open_db(cfg, root)
        a = learn.exact_examples(cfg, db, 1.0)
        b = learn.exact_examples(cfg, db, 1.0)
        assert digest(a) == digest(b)
        c = learn.exact_examples(cfg, db, 1.0, seed=learn.EXACT_SEED + 1)
        assert digest(a) != digest(c)
        for d in np.unique(a.decision):  # options ranked by their exact values
            m = a.decision == d
            assert (a.rank_value[m & (a.option >= 0)] <= a.target[m & (a.option == -1)][0] + 1e-6).all()
        rows = db.fetch(db.decision_ids().tolist())  # Amendment 2: dull decisions are skipped
        dull = sum(learn.dull([o[1] for o in opts], [any(a.is_end_turn for a in o[0]) for o in opts]) for _, _, opts in rows)
        # Since exact-solver Amendment 1 all-tied decisions are written to
        # `trivial`, outside decision_ids; the skip still covers "only End
        # turn worse" and databases not yet compacted.
        assert dull < len(rows)
        every = learn.exact_examples({**cfg, "exact_cap": 10**9}, db, 1.0)
        assert (every.option == -1).sum() == len(rows) - dull
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_exact_split():
    """Amendment 3: with `exact_split` 0.5 the draw takes rows at
    turns_left >= 1 and at 0 in turn, the longer side's rest last, each
    side in a fixed order per seed; training_set draws in that order, and
    with `exact_leaves` each exact option's paused state is a value example
    with that option's exact value (none from dull rows)."""
    import sqlite3
    import sts
    root = fixture_root()
    try:
        ds_id = dataset_ids()["score"]
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(LEARN_CFG["score"], 1))
        fill_db(root, [raw.codec_bytes(i) for i in range(len(raw))], raw.distance)
        path = learn.db_path(root)
        import bench
        import bench_decisions
        db = sts.SolvedDb(path)  # plus a row with a bounded option (solver bounds)
        for r in [r for h in bench.load_puzzles()["halves"].values() for r in h][::10]:
            c = bench_decisions.replay(r)
            if any(sts.solve(c, max_nodes=200_000, bounds=True, store=sts.SolveStore(min_nodes=0, db=db))["bounded"]):
                break
        del db
        db = learn.open_db(LEARN_CFG["score"], root)
        cfg = {**LEARN_CFG["score"], "exact_split": 0.5}
        order = learn.exact_order(cfg, db, path=path)
        con = sqlite3.connect(path)
        turns = dict(con.execute("select id, turns_left from states where options is not null"))
        con.close()
        far = np.array([turns[int(i)] >= 1 for i in order])
        m = min(far.sum(), (~far).sum())
        assert m > 0, "the fixture needs rows on both sides"
        assert (far[:2 * m] == np.tile([True, False], m)).all()
        assert (far[2 * m:] == far[2 * m]).all() if len(far) > 2 * m else True
        assert sorted(order.tolist()) == sorted(db.decision_ids().tolist())
        assert (learn.exact_order(cfg, db, path=path) == order).all()
        assert (learn.exact_order(cfg, db, seed=learn.EXACT_SEED + 1, path=path) != order).any()
        # the paused states: per non-dull row, one example per exact option's
        # state paused at a random event, labelled with its exact value
        want = []
        rows = db.fetch(order.tolist())
        assert any(o[2] for _, _, opts in rows for o in opts), "the fixture needs a bounded option"
        for code, _, opts in rows:
            if learn.dull([o[1] for o in opts], [any(a.is_end_turn for a in o[0]) for o in opts], [o[2] for o in opts]):
                continue
            s = sts.Combat.decode(code)
            want += [o[1] for (_, _, outs), o in zip(s.options(1), opts) if not o[2]
                     for _, x in outs if not x.is_over() and not x.awaiting_action()]
        big = {"exact_cap": 10**9}
        plain = learn.exact_examples(big, db, 1.0, ids=order)
        both = learn.exact_examples(big, db, 1.0, ids=order, leaves=True)
        assert want, "the fixture needs paused states"
        capped = learn.exact_examples({"exact_cap": 60}, db, 1.0, ids=order, leaves=True)  # paused states count
        assert 0 < len(capped) <= 60 and (capped.target == both.target[:len(capped)]).all()
        assert (both.option == -1).sum() == (plain.option == -1).sum() + len(want)
        got = sorted(both.target[both.option == -1].tolist())
        expect = sorted(plain.target[plain.option == -1].tolist() + np.float32(want).tolist())
        assert np.allclose(got, expect)
        # training_set: the split order and the paused states, under the share
        cfg = {**cfg, "exact_cap": 10**9, "exact_leaves": True, "exact_share": 0.25}
        train_ds, _, _ = learn.training_set(cfg, [(ds_id, 1)], root=root, view=False)
        exact = train_ds.distance == -1
        dec = exact & (train_ds.option == -1)
        assert dec.sum() == (both.option == -1).sum()
        # bounded afterstates' one-sided terms weigh on top of the share (solver bounds, as built)
        w = train_ds.weight.astype(np.float64)
        assert abs(w[dec].sum() / (w[dec].sum() + w[~exact].sum()) - 0.25) < 1e-6
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_exact_draw_unchanged():
    """Amendment 3: a config without `exact_leaves` / `exact_split` draws
    as Amendment 2: one fixed permutation of decision_ids, no paused
    states, and training_set's exact part equals exact_examples' own."""
    root = fixture_root()
    try:
        ds_id = dataset_ids()["score"]
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(LEARN_CFG["score"], 1))
        fill_db(root, [raw.codec_bytes(i) for i in range(len(raw))], raw.distance)
        cfg = {**LEARN_CFG["score"], "exact_cap": 60}
        db = learn.open_db(cfg, root)
        ids = db.decision_ids()
        old = ids[np.random.default_rng(learn.EXACT_SEED).permutation(len(ids))]
        assert (learn.exact_order(cfg, db, path=learn.db_path(root)) == old).all()
        a = learn.exact_examples(cfg, db, 1.0)
        assert digest(a) == digest(learn.exact_examples(cfg, db, 1.0, ids=old))
        train_ds, _, _ = learn.training_set(cfg, [(ds_id, 1)], root=root, view=False)
        exact = train_ds.distance == -1
        assert np.array_equal(train_ds.target[exact], a.target)
        assert np.array_equal(train_ds.option[exact], a.option)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def cache_peak(copies):
    """In this process: builds the score dataset's round-1 cache from its
    games repeated `copies` times; returns (process peak commit, cache
    bytes, examples)."""
    import memprobe
    root = fixture_root()
    try:
        ds = dataset_ids()["score"]
        games = registry.load_games(ds, root)
        registry.iter_games = lambda d, r=None: (g for _ in range(copies) for g in games)
        registry.CHUNK = 12
        lab = learn.labels(LEARN_CFG["score"], 1)
        d = registry.examples(ds, "effects", root, labels=lab)
        assert isinstance(d.player, np.memmap) or isinstance(d.player.base, np.memmap)
        n, size = len(d), registry._size(registry.cache_path(ds, "effects", root, lab))
        del d
        return memprobe.counters(memprobe.k32.GetCurrentProcess()).PeakPagefileUsage, size, n
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_cache_v7_streams():
    """Building a cache of N and 4N games peaks within 10% of each other
    (Amendment 1): each chunk is written as it is encoded. Each build runs
    in a fresh process, since a process's peak can't be reset. (The v6
    build peaked at 0.94 and 1.59 GB here.)"""
    import subprocess
    out = {}
    for copies in (100, 400):
        r = subprocess.run([sys.executable, __file__, "--cache-peak", str(copies)], capture_output=True, text=True,
                           check=True)
        out[copies] = json.loads(r.stdout.strip().splitlines()[-1])
    (p1, s1, n1), (p4, s4, n4) = out[100], out[400]
    assert n4 > 3.9 * n1 and s4 > 3.9 * s1 > 0, out  # the sampled states differ per copy
    assert abs(p4 - p1) <= 0.1 * p1, out


def view_and_concat(root):
    """(DatasetView, in-RAM concatenation) of one round's training set over
    the score dataset as rounds 1 and 0 (round 0's half sampled), with the
    database's exact examples."""
    ds_id = dataset_ids()["score"]
    raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(LEARN_CFG["score"], 1))
    fill_db(root, [raw.codec_bytes(i) for i in range(len(raw))], raw.distance)
    del raw
    cfg = {**LEARN_CFG["score"], "exact_cap": 80}
    # samples key by dataset id, so round 0's part is a copy of the dataset
    dsdir = registry.datasets_dir(root)
    shutil.copytree(os.path.join(dsdir, ds_id), os.path.join(dsdir, "r0copy000000"))
    parts, samples = [(ds_id, 1), ("r0copy000000", 0)], {"r0copy000000": (0.5, 7)}
    v, sv, cv = learn.training_set(cfg, parts, root=root, samples=samples)
    c, sc, cc = learn.training_set(cfg, parts, root=root, samples=samples, view=False)
    assert sv == sc and cv == cc and cv["exact_drawn"] > 0
    return v, c


def test_view_batches():
    """The training view (Amendment 1) gives the same examples as the
    in-RAM concatenation: per-example arrays, batches on the same indices
    across part boundaries (round 0's sample and the exact examples
    included) and the normalizer's statistics, bit for bit."""
    import stsnet
    root = fixture_root()
    try:
        v, c = view_and_concat(root)
        assert isinstance(v, stsnet.DatasetView) and len(v) == len(c)
        for k in ("target", "group", "card_len", "row_len") + Dataset.EXTRA:
            a, b = getattr(v, k), getattr(c, k)
            assert (a is None) == (b is None), k
            assert a is None or (a.dtype == b.dtype and np.array_equal(a, b, equal_nan=True)), k
        rng = np.random.default_rng(0)
        for idx in (rng.permutation(len(c))[:300], np.arange(len(c)), np.arange(len(c) - 5, len(c)),
                    np.array([0, len(c) - 1, len(c) // 2])):
            a, b = v.batch(idx), c.batch(idx)
            assert a.keys() == b.keys()
            for k in a:
                assert a[k].dtype == b[k].dtype and np.array_equal(a[k], b[k], equal_nan=True), k
        nv, nc = stsnet.Normalizer.fit(v), stsnet.Normalizer.fit(c)
        for k in stsnet.Normalizer.KEYS:
            assert all(np.array_equal(x, y) for x, y in zip(nv.stats[k], nc.stats[k])), k
        tmp = list(v.tmp_dirs)
        assert tmp and all(os.path.isdir(t) for t in tmp)
        v.close()
        assert not any(os.path.exists(t) for t in tmp)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_mapped_same_net():
    """One round's net trained from the view equals the in-RAM
    concatenation's, bit for bit (same seed, ranking term on)."""
    root = fixture_root()
    epochs = train.EPOCHS
    train.EPOCHS = 2
    try:
        v, c = view_and_concat(root)
        val = learn.load_examples(LEARN_CFG["score"], dataset_ids()["score"], None, root=root)
        nets = []
        for ds in (v, c):
            curves = {}
            model, norm, hist = train.train("effects", ds, val, 3, lambda *_: None, curves,
                                            rank_weight=learn.RANK_WEIGHT)
            nets.append((model.state_dict(), norm.stats, curves))
        (sa, na, ca), (sb, nb, cb) = nets
        assert all(torch.equal(sa[k], sb[k]) for k in sa)
        assert ca == cb
        assert all(np.array_equal(na[k][i], nb[k][i]) for k in na for i in (0, 1))
        v.close()
    finally:
        train.EPOCHS = epochs
        shutil.rmtree(root, ignore_errors=True)


def test_train_db_not_bench():
    """Training's database is its own, never the bench puzzle build's."""
    import puzzles
    assert os.path.normcase(os.path.abspath(learn.db_path(registry.ROOT))) != os.path.normcase(os.path.abspath(puzzles.DB_PATH))


def test_exact_tmp_removed_on_error():
    """A round that fails while drawing its exact examples leaves no
    temporary cache behind (Amendment 1)."""
    import sts
    root = fixture_root()
    real = learn.exact_examples
    try:
        os.makedirs(os.path.dirname(learn.db_path(root)), exist_ok=True)
        sts.SolvedDb(learn.db_path(root))

        def fail(*a, out=None, **kw):
            os.makedirs(out + ".tmp1", exist_ok=True)  # a half-built cache
            raise RuntimeError("draw failed")
        learn.exact_examples = fail
        try:
            learn.training_set(LEARN_CFG["score"], [(dataset_ids()["score"], 1)], root=root)
            raise AssertionError("no error")
        except RuntimeError:
            pass
        assert not [n for n in os.listdir(registry.cache_dir(root)) if "exact.tmp" in n]
    finally:
        learn.exact_examples = real
        shutil.rmtree(root, ignore_errors=True)


def test_train_reads_only():
    """Building a round's examples against the database leaves its rows
    unchanged."""
    root = fixture_root()
    try:
        ds_id = dataset_ids()["score"]
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(LEARN_CFG["score"], 1))
        fill_db(root, [raw.codec_bytes(i) for i in range(len(raw))], raw.distance)
        before = db_rows(root)
        learn.training_set(LEARN_CFG["score"], [(ds_id, 1), (ds_id, 0)], root=root)
        assert db_rows(root) == before > 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_solve_step():
    """A round's solve step walks back the first `solve_games` games of its
    dataset (round 0: `solve_games0`) into the database, positions sourced
    to the dataset id, as the finder does on those games, on the config's
    `solve_threads` threads when set; switch 6 has none."""
    import puzzles
    import sts
    root = fixture_root()
    try:
        ids = dataset_ids()
        ds = ids["score"]
        rows = learn.solve_step({"solve_games": 2, "solve_games0": 3}, ds, 1, root=root, log=lambda *_: None,
                                max_nodes=20_000)
        db = sts.SolvedDb(learn.db_path(root))
        assert rows == db.rows > 0
        got = {(r["spec"], r["step"]) for r in db.positions(ds)}
        assert got and {json.loads(s)["game"] for s, _ in got} <= {0, 1}
        assert db.positions("other") == []
        games = puzzles.dataset_games(ds, root)
        assert [json.loads(puzzles.spec_key(g[0]))["game"] for g in games] == list(range(len(games))) and len(games) > 3
        ref = sts.SolvedDb(os.path.join(tempfile.mkdtemp(), "ref.sqlite"))
        found = puzzles.find(games[:2], ref, ds, max_nodes=20_000, bounds=True)  # solver bounds (solve_dataset's default)
        assert got == {(puzzles.spec_key(g[0]), p["step"]) for g, ps in zip(games[:2], found) for p in ps}
        exact = puzzles.find(games[:2], sts.SolvedDb(os.path.join(tempfile.mkdtemp(), "exact.sqlite")), ds,
                             max_nodes=20_000)
        assert sum(map(len, exact)) <= len(got)
        learn.solve_step({"solve_games": 2, "solve_games0": 3}, ds, 0, root=root, log=lambda *_: None,
                         max_nodes=20_000)
        db = sts.SolvedDb(learn.db_path(root))
        assert {json.loads(r["spec"])["game"] for r in db.positions(ds)} <= {0, 1, 2}
        seen, real = [], puzzles.find  # the sweep's `solve_threads` reaches the finder
        puzzles.find = lambda *a, **k: seen.append(k["threads"]) or real(*a, **k)
        try:
            learn.solve_step({"solve_games": 1, "solve_threads": 1}, ds, 1, root=root, log=lambda *_: None,
                             max_nodes=20_000)
            learn.solve_step({"solve_games": 1}, ds, 1, root=root, log=lambda *_: None, max_nodes=20_000)
        finally:
            puzzles.find = real
        assert seen == [1, None]
        hp_root = fixture_root()
        try:
            assert learn.solve_step(LEARN_CFG["hp"], ids["hp"], 1, root=hp_root, log=lambda *_: None) is None
            assert not os.path.exists(os.path.join(hp_root, "db"))
        finally:
            shutil.rmtree(hp_root, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_exact_draw_by_content():
    """The exact examples' draw depends on the database's content, not on
    the order its rows were written: the same games solved on 1 and 4
    threads give the same draw."""
    import puzzles
    import sts
    tmp = tempfile.mkdtemp()
    try:
        games = puzzles.dataset_games(dataset_ids()["score"], fixture_root())
        draws = []
        for threads in (1, 4):
            db = sts.SolvedDb(os.path.join(tmp, f"t{threads}.sqlite"))
            puzzles.find(games, db, "x", threads=threads, max_nodes=20_000, min_nodes=0)
            db = sts.SolvedDb(os.path.join(tmp, f"t{threads}.sqlite"))
            ex = learn.exact_examples({"exact_cap": 200}, db, 1.0)
            draws.append((ex.target.tobytes(), ex.option.tobytes(), len(db.decision_ids())))
        assert draws[0] == draws[1] and draws[0][2] > 20, [d[2] for d in draws]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_not_played_rank_only():
    """Afterstates of options not played have value weight 0 and keep their
    ranking fields (ordered by the recorded search values); decision states
    and the played option's afterstates weigh 1. Switch 6 keeps every
    weight 1 (no weights)."""
    root = fixture_root()
    try:
        ids = dataset_ids()
        ds = learn.load_examples(LEARN_CFG["score"], ids["score"], 1, root=root)
        notp = ds.played == 0
        assert notp.any() and (ds.played == 1).any()
        assert (ds.weight[notp] == 0).all() and (ds.weight[~notp] == 1).all()
        assert (ds.option[notp] >= 0).all()
        assert np.array_equal(ds.rank_value[notp], ds.search[notp])
        for d in np.unique(ds.decision):
            opts = ds.option[(ds.decision == d) & (ds.played == 1) & (ds.option >= 0)]
            assert len(set(opts.tolist())) <= 1  # one played option per decision
        r0 = learn.load_examples(LEARN_CFG["score"], ids["score"], 0, root=root)
        assert (r0.weight == 1).all()
        hp = learn.load_examples(LEARN_CFG["hp"], ids["hp"], 1, root=root)
        assert hp.weight is None
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_frontier_rule():
    """The frontier: the unbroken run of verified horizons from 0, plus 1; a
    gap or too few puzzles stops it; horizon 0 failing gives none."""
    ok, bad, few = (500, 0.0), (500, 0.02), (49, 0.0)
    assert learn.frontier({0: ok, 1: ok, 2: ok}) == 3
    assert learn.frontier({0: ok, 1: bad, 2: ok}) == 1
    assert learn.frontier({0: ok, 1: few, 2: ok}) == 1
    assert learn.frontier({0: ok, 2: ok}) == 1  # horizon 1 has no puzzles
    assert learn.frontier({0: bad, 1: ok}) is None
    assert learn.frontier({0: few}) is None
    assert learn.frontier({}) is None
    assert learn.frontier({0: (500, 0.01)}) == 1  # at regret_max is verified
    assert learn.frontier({0: (50, 0.0)}, min_puzzles=50) == 1
    assert learn.frontier({0: (500, 0.02)}, regret_max=0.05) == 1


def test_zone_skips_dull():
    """Amendment 2: dull puzzles (all options tied, or only End turn worse)
    are left out of each horizon's count and mean, and counted as tied; a
    card play worse than the rest keeps a puzzle in, even when End turn is
    worse too or best."""
    def row(h, *values, end=None):
        return {"horizon": h, "options": [[["End"] if k == end else [f"Strike@{k}"], v] for k, v in enumerate(values)]}
    rows = [row(0, 1.5, 1.5), row(0, 1.5, 1.2), row(0, 0.0, 0.0, 0.0), row(1, 2.0, 1.9), row(2, 1.0, 1.0),
            row(2, 1.4, 1.4, 1.0, end=2),  # only End turn worse: dull
            row(2, 1.4, 1.1, 1.0, end=2),  # a card worse too: kept
            row(2, 1.0, 1.0, 1.4, end=2)]  # End turn best, the cards worse: kept
    per, tied = learn.horizon_regrets(rows, [1, 1, 2, 0, 0, 2, 0, 0])
    assert per == {0: [1.5 - 1.2], 1: [0.0], 2: [0.0, 1.4 - 1.0]}
    assert tied == {0: 2, 2: 2}
    assert learn.dull([1.0, 1.0 - 1e-12], [False, False]) and not learn.dull([1.0, 0.9], [False, False])
    rows = rows[:5]
    per, tied = learn.horizon_regrets(rows, [1, 1, 2, 0, 0])
    scores = {h: (len(v), sum(v) / len(v)) for h, v in per.items()}
    assert learn.frontier(scores, min_puzzles=1, regret_max=0.25) is None  # 0.3 at horizon 0, not diluted to 0.1
    assert learn.frontier(scores, min_puzzles=1, regret_max=0.5) == 2
    assert learn.frontier(scores, min_puzzles=2, regret_max=0.5) is None  # tied puzzles don't count toward min_puzzles


def test_ladder_search():
    """Rung 3 inside the playing net's zone: a decision at distance 1 with
    frontier 2 takes 0.8 x its best value + 0.2 x outcome; at distance 3,
    the outcome; with no frontier, the outcome; the played divergent
    option's afterstate, the outcome; the played deterministic option's
    afterstate inside the zone, the blend with that option's value. Rung 1
    still wins over rung 3."""
    root = fixture_root()
    try:
        cfg = LEARN_CFG["score"]
        ds_id = dataset_ids()["score"]
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(cfg, 1))
        got = learn.load_examples(cfg, ds_id, 1, root=root, frontier=2)
        none = learn.load_examples(cfg, ds_id, 1, root=root, frontier=None)
        assert np.array_equal(none.target, raw.outcome)
        blend = (0.8 * raw.search.astype(np.float64) + 0.2 * raw.outcome.astype(np.float64)).astype(np.float32)
        dec, played = raw.option == -1, raw.played == 1
        cases = {
            "decision d1": (dec & (raw.distance == 1), blend),
            "decision d3": (dec & (raw.distance == 3), raw.outcome),
            "divergent played": (played & (raw.kind == 3) & (raw.distance <= 2), raw.outcome),
            "deterministic played": (played & (raw.kind == 1) & (raw.distance <= 2), blend),
            "not played": (raw.played == 0, raw.outcome),
        }
        for name, (m, want) in cases.items():
            assert m.any(), name
            assert np.array_equal(got.target[m], want[m]), name
        assert not np.array_equal(got.target, raw.outcome)
        cfg9 = {**cfg, "w_near": 0.9}
        g9 = learn.load_examples(cfg9, ds_id, 1, root=root, frontier=2)
        m = cases["decision d1"][0]
        want9 = (0.9 * raw.search[m].astype(np.float64) + 0.1 * raw.outcome[m].astype(np.float64)).astype(np.float32)
        assert np.array_equal(g9.target[m], want9)
        # Rung 1 wins: a planted exact value replaces the blend.
        codes = [raw.codec_bytes(i) for i in range(len(raw))]
        i = int(np.flatnonzero(m)[0])
        e = learn.load_examples(cfg, ds_id, 1, root=root, frontier=2,
                                exact=lambda cs: [(0.123, None) if c == codes[i] else None for c in cs])
        assert e.target[i] == np.float32(0.123)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_round0_no_search():
    """Round 0's examples (the heuristic's games) never take rung 3, even
    with a frontier."""
    root = fixture_root()
    try:
        cfg = LEARN_CFG["score"]
        ds_id = dataset_ids()["score"]
        raw = registry.examples(ds_id, "effects", root=root, labels=learn.labels(cfg, 0))
        got = learn.load_examples(cfg, ds_id, 0, root=root, frontier=9)
        assert np.array_equal(got.target, raw.outcome)
        # training_set never asks round 0's parts for a frontier either.
        orig = learn.dataset_frontier
        learn.dataset_frontier = lambda *a, **k: 9
        try:
            ts, _, _ = learn.training_set(cfg, [(ds_id, 0)], root=root)
        finally:
            learn.dataset_frontier = orig
        assert np.array_equal(ts.target, raw.outcome)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_frontier_per_dataset():
    """In one window, rounds k and k-1's datasets are each labelled with the
    frontier of the net that played them (its run's round.json); a dataset
    whose net recorded no trusted zone takes no rung 3. The examples per
    rung (round.json's `rungs`) count each example once."""
    root = fixture_root()
    try:
        cfg = LEARN_CFG["score"]
        src = dataset_ids()["score"]
        dsdir = registry.datasets_dir(root)
        ids = {}
        for name, front in (("a", 0), ("b", 3), ("c", None)):
            run = f"run-{name}"
            os.makedirs(os.path.join(registry.runs_dir(root), run))
            rec = {"round": 1, "trusted": None if front is None else {"frontier": front}}
            registry.Run(os.path.join(registry.runs_dir(root), run))._write("round.json", rec)
            ds = f"ds{name}0000000"[:12]
            shutil.copytree(os.path.join(dsdir, src), os.path.join(dsdir, ds))
            m = registry.load_manifest(ds, root)
            m["parent_model"] = run
            with open(os.path.join(dsdir, ds, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(m, f)
            ids[name] = (ds, front)
        for ds, front in ids.values():
            assert learn.dataset_frontier(ds, root) == front
        assert learn.dataset_frontier(src, root) is None  # heuristic games
        parts = [(ids["b"][0], 2), (ids["a"][0], 1), (ids["c"][0], 1)]
        ts, _, counts = learn.training_set(cfg, parts, root=root)
        # round.json's rung counts: every example once; rung 3 wherever a label left the outcome
        assert sum(counts.values()) == len(ts) and counts["exact"] == counts["exact_drawn"] == 0
        assert counts["ranking_only"] == int((ts.weight == 0).sum()) > 0
        assert counts["search"] >= int(((ts.target != ts.outcome) & (ts.weight > 0)).sum()) > 0  # a blend can equal the outcome
        want = Dataset.concat([learn.load_examples(cfg, ds, rnd, root=root, frontier=ids[n][1])
                               for (ds, rnd), n in zip(parts, "bac")])
        assert np.array_equal(ts.target, want.target)
        n = len(want) // 3
        assert not np.array_equal(ts.target[:n], ts.target[n:2 * n])  # frontiers 3 and 0 label differently
        raw = registry.examples(src, "effects", root=root, labels=learn.labels(cfg, 1))
        assert np.array_equal(ts.target[2 * n:], raw.outcome)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--cache-peak"]:
        print(json.dumps(cache_peak(int(sys.argv[2]))))
        sys.exit()
    if sys.argv[1:2] == ["--pin"]:
        pin(datasets="--datasets" in sys.argv)
        sys.exit()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    try:
        for t in tests:
            t()
            print("ok ", t.__name__)
    finally:
        for d in _FILLED:
            shutil.rmtree(d, ignore_errors=True)
    print(len(tests), "passed")


def test_dataset_games_decodes_only_its_limit():
    """The solve step's `dataset_games(ds, limit=n)` decodes only the first
    n games: a 0-game solve step over a 120,000-game pool held the whole
    pool (3.7 GB, lane learn-memory)."""
    import puzzles
    ds, root = dataset_ids()["score"], fixture_root()
    seen = []
    real = registry.iter_games

    def counting(*a, **kw):
        for g in real(*a, **kw):
            seen.append(1)
            yield g
    registry.iter_games = counting
    try:
        assert puzzles.dataset_games(ds, root, 0) == [] and len(seen) <= 1
        two = puzzles.dataset_games(ds, root, 2)
    finally:
        registry.iter_games = real
    assert two == puzzles.dataset_games(ds, root)[:2]
