"""Tests for the warm-start workflow (docs/specs/warm-start.md): widening a
net to new columns, fine-tuning through the registry. Run with
`python scripts/tests/test_warm_start.py` (plain asserts; every `test_*`
function runs) or with pytest."""

import json
import os
import shutil
import sys
import tempfile

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import contract_pins as pins  # noqa: E402
import finetune  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import stsnet  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
IDS_NET = os.path.join(ROOT, "models", "value_ids.pt")
EFFECTS_NET = os.path.join(ROOT, "models", "value_effects.pt")
TOL = 1e-5


def tiny_net(mode):
    """An untrained net on `selfplay.features(mode)`'s layout, its
    normaliser fitted on the fixed state set."""
    meta = {"card_repr": mode, **selfplay.meta_vocab(mode)}
    feats = stsnet.features_for(meta)
    torch.manual_seed(0)
    model = stsnet.ValueNet(feats.dims).eval()
    states = pins.fixed_states()
    norm = stsnet.Normalizer.fit(stsnet.Dataset.from_batches([feats.encode(states)], [0.0] * len(states)))
    return model, norm, {**meta, **stsnet.layout_of(meta)}


def nets():
    return [("tiny effects", *tiny_net("effects")), ("tiny ids", *tiny_net("ids")),
            ("value_ids", *stsnet.load(IDS_NET))]


def scores(model, norm, meta, states):
    with torch.no_grad():
        torch_out = stsnet.score_of(model, norm.tensors(stsnet.features_for(meta).encode(states))).numpy()
    rust_out = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(states))
    return torch_out, rust_out


def test_widen_identity():
    """Widened to the Silent vocabulary, every net scores old content as
    before (torch and Rust within TOL), each through its own encoder. An
    ids net's Silent states aren't old content: their cards leave
    `id_unknown` for zero-weight columns of their own."""
    states = pins.fixed_states()
    iron = [s for s in states if s.character == "ironclad"]
    for name, model, norm, meta in nets():
        w, wn, wm = stsnet.widen(model, norm, meta, finetune.vocab_for(meta))
        same = states if meta["card_repr"] == "effects" else iron
        for a, b in zip(scores(model, norm, meta, same), scores(w, wn, wm, same)):
            assert np.abs(a - b).max() <= TOL, (name, float(np.abs(a - b).max()))
        if meta["card_repr"] == "ids":
            assert len(wm["columns"]["cards"]) > len(meta["columns"]["cards"]), name


def test_widen_new_columns_inert():
    """New columns have zero weights: setting their normalised inputs to 5
    leaves the widened ids net's outputs unchanged; old columns keep the
    saved normaliser and new ones take the given statistics."""
    model, norm, meta = stsnet.load(IDS_NET)
    new_meta = finetune.vocab_for(meta)
    layout = stsnet.layout_of(new_meta)
    stats = stsnet.Normalizer({k: (np.full(len(c), 0.25, np.float32), np.full(len(c), 3.0, np.float32))
                               for k, c in layout["columns"].items()})
    w, wn, wm = stsnet.widen(model, norm, meta, new_meta, stats)
    states = pins.fixed_states()[::5]
    t = wn.tensors(stsnet.features_for(wm).encode(states))
    with torch.no_grad():
        before = stsnet.score_of(w, t).numpy()
        for path, cols in wm["columns"].items():
            new = [i for i, c in enumerate(cols) if c not in meta["columns"][path]]
            t[path][..., new] = 5.0
            m, s = wn.stats[path]
            old = [cols.index(c) for c in meta["columns"][path]]
            assert np.array_equal(m[old], norm.stats[path][0]) and np.array_equal(s[old], norm.stats[path][1]), path
            assert np.all(m[new] == 0.25) and np.all(s[new] == 3.0), path
        after = stsnet.score_of(w, t).numpy()
    assert np.abs(after - before).max() <= 1e-6


def test_widen_known_top():
    """A five-pile net widened to today's piles scores a state with a known
    top card (Headbutt) as before: the next_draw slot copies draw's head
    weights. Its row kinds stay its own."""
    c = sts.Combat(["Headbutt"] * 10, "jaw_worm", seed=1)
    c.step(sts.Action("Headbutt", 0))
    c.step(sts.Action("Headbutt", 0))
    c.step(c.legal_actions()[0])
    for name, model, norm, meta in nets():
        meta = {**meta, "piles": ["hand", "draw", "discard", "exhaust", "playing"]}
        if model.n_piles != 5:
            continue
        w, wn, wm = stsnet.widen(model, norm, meta, finetune.vocab_for(meta))
        assert "next_draw" in wm["piles"] and wm["row_kinds"] == stsnet.layout_of(meta)["row_kinds"], name
        for a, b in zip(scores(model, norm, meta, [c]), scores(w, wn, wm, [c])):
            assert np.abs(a - b).max() <= TOL, (name, float(np.abs(a - b).max()))


def test_widen_refuses_dropped_column():
    """A new layout without one of the net's columns is refused."""
    model, norm, meta = stsnet.load(IDS_NET)
    smaller = {**finetune.vocab_for(meta)}
    smaller["known_cards"] = [c for c in smaller["known_cards"] if c != "Bash"]
    try:
        stsnet.widen(model, norm, meta, smaller)
    except ValueError as e:
        assert "drops" in str(e)
    else:
        raise AssertionError("a dropped column was accepted")


def test_determinism():
    """Search + heuristic on the same Silent specs plays the same games."""
    specs, groups = selfplay.make_specs(4, 99, finetune.DECKS["both"], character="silent")
    specs, groups = specs[:10], groups[:10]
    runs = [registry.records(specs, groups, sts.run("search", specs, record=True, limit=selfplay.LIMIT,
                                                    character="silent", threads=4), {"character": "silent"})
            for _ in range(2)]
    assert runs[0] == runs[1]


def test_finetune_tiny():
    """A tiny fine-tune of value_ids.pt writes a registry run naming its
    parent (path, sha256); its net loads, has the Silent cards' columns, and
    keeps the parent's normaliser for old columns. Sizes nest: the first k
    games per group of the stored dataset."""
    root = tempfile.mkdtemp(prefix="warm-start-")
    try:
        cfg = {"name": "tiny-ft", "content": "both", "games": 10, "top": 20, "game_seed": 7, "seed": 0,
               "epochs": 1, "n_val": 5, "pool": 10}
        log = lambda *a: None  # noqa: E731
        run = finetune.finetune(IDS_NET, cfg, root=root, log=log, threads=4)
        info = json.load(open(os.path.join(run.path, "run.json"), encoding="utf-8"))
        assert info["parent"]["sha256"] == finetune.sha256(IDS_NET)
        assert info["parent"]["path"].endswith("models/value_ids.pt")
        model, norm, meta = stsnet.load(run.model_path)
        _, pnorm, pmeta = stsnet.load(IDS_NET)
        assert "id_Neutralize" in meta["columns"]["cards"]
        for path, cols in pmeta["columns"].items():
            idx = [meta["columns"][path].index(c) for c in cols]
            assert np.array_equal(norm.stats[path][0][idx], pnorm.stats[path][0]), path
        ds = info["datasets"][0]
        games = list(finetune.first_per_group(ds, 10, root))
        assert len(games) == 30 and all(sum(g["group"] == k for g in games) == 10 for k in range(3))
        allg, seen, want = registry.load_games(ds, root), {}, []
        for g in allg:
            seen[g["group"]] = seen.get(g["group"], 0) + 1
            if seen[g["group"]] <= 10:
                want.append(g)
        assert len(allg) == 60 and games == want
        fresh = finetune.finetune(None, {**cfg, "name": "tiny-fresh", "start": "fresh"}, root=root, log=log, threads=4)
        assert "parent" not in json.load(open(os.path.join(fresh.path, "run.json"), encoding="utf-8"))
        stsnet.load(fresh.model_path)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_widen_takes_named_row_kinds():
    """widen keeps the old net's row kinds when the new meta names none,
    takes named ones, and refuses to drop one."""
    model, norm, meta = stsnet.load(IDS_NET)
    assert meta["row_kinds"] == ["triggered"]
    new = finetune.vocab_for(meta)
    assert stsnet.widen(model, norm, meta, new)[2]["row_kinds"] == ["triggered"]
    kinds = ["triggered", "threshold", "held"]
    assert stsnet.widen(model, norm, meta, {**new, "row_kinds": kinds})[2]["row_kinds"] == kinds
    try:
        stsnet.widen(model, norm, meta, {**new, "row_kinds": ["threshold", "held"]})
    except ValueError as e:
        assert "drops" in str(e)
    else:
        raise AssertionError("a dropped row kind was accepted")


def spied_finetune(cfg):
    """A tiny warm fine-tune of value_effects.pt with `cfg`'s extra keys;
    returns (the saved net's meta, the layout of every set it encoded)."""
    root = tempfile.mkdtemp(prefix="warm-layout-")
    seen, real = [], finetune.encoded

    def spy(ds, k, meta, *a, **kw):
        seen.append(stsnet.layout_of(meta))
        return real(ds, k, meta, *a, **kw)

    finetune.encoded = spy
    try:
        cfg = {"name": "tiny-layout", "content": "both", "games": 10, "top": 20, "game_seed": 7, "seed": 0,
               "epochs": 1, "n_val": 5, "pool": 10, **cfg}
        run = finetune.finetune(EFFECTS_NET, cfg, root=root, log=lambda *a: None, threads=4)
        return stsnet.load(run.model_path)[2], seen
    finally:
        finetune.encoded = real
        shutil.rmtree(root, ignore_errors=True)


def test_finetune_trains_on_saved_layout():
    """Every set a warm fine-tune encodes (train, two validation sets,
    replay) is in the layout its saved net reads: today's default row
    kinds, though the parent read only triggered rows."""
    m, seen = spied_finetune({})
    assert len(seen) == 4 and all(x == stsnet.layout_of(m) for x in seen)
    assert m["row_kinds"] == ["triggered", "threshold", "held"]


def test_finetune_extra_rows():
    """`extra_rows: true` trains and saves every row kind; a `row_kinds`
    entry that names no kind is refused before any game is played."""
    m, seen = spied_finetune({"extra_rows": True})
    assert m["row_kinds"] == list(sts.ROW_KINDS) and len(sts.ROW_KINDS) == 10
    assert len(seen) == 4 and all(x == stsnet.layout_of(m) for x in seen)
    try:
        finetune.finetune(EFFECTS_NET, {"content": "both", "games": 1, "game_seed": 0, "row_kinds": ["statik"]},
                          root=tempfile.gettempdir(), log=lambda *a: None)
    except ValueError as e:
        assert "statik" in str(e)
    else:
        raise AssertionError("an unknown row kind was accepted")
    try:
        finetune.row_kinds({"extra_rows": True, "row_kinds": ["statik"]}, ["triggered"], [])
    except ValueError as e:
        assert "statik" in str(e)
    else:
        raise AssertionError("an unknown row kind was accepted beside extra_rows")


# ---- burst anchor (docs/specs/burst-anchor.md) ----

def _anchor_run(anchor=None):
    import copy
    import train
    model, norm, meta = tiny_net("effects")
    feats = stsnet.features_for(meta)
    states = pins.fixed_states()
    ds = stsnet.Dataset.from_batches([feats.encode(states)], [float(i % 3) - 1.0 for i in range(len(states))])
    start = copy.deepcopy(model)
    kw = {} if anchor is None else {"anchor": anchor}
    out, _, _ = train.train("effects", ds, ds, seed=0, log=lambda *a: None, start=(model, norm), epochs=2, lr=1e-2,
                            **kw)
    drift = sum(float(((p.detach() - p0) ** 2).sum()) for p, p0 in zip(out.parameters(), start.parameters()))
    return out, drift


def test_anchor_zero_is_unchanged():
    a, _ = _anchor_run(None)
    b, _ = _anchor_run(0.0)
    for (k, x), y in zip(a.state_dict().items(), b.state_dict().values()):
        assert torch.equal(x, y), k


def test_anchor_pulls_toward_start():
    _, free = _anchor_run(0.0)
    _, held = _anchor_run(10.0)
    assert free > 0 and held < free, (free, held)


def test_anchor_refuses_fresh():
    import train
    model, norm, meta = tiny_net("effects")
    feats = stsnet.features_for(meta)
    states = pins.fixed_states()
    ds = stsnet.Dataset.from_batches([feats.encode(states)], [0.0] * len(states))
    try:
        train.train("effects", ds, ds, log=lambda *a: None, epochs=1, anchor=0.1)
    except ValueError:
        return
    raise AssertionError("anchor without a start net was accepted")


if __name__ == "__main__":
    torch.set_num_threads(4)
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for name, fn in tests:
        fn()
        print(f"{name}: ok")
    print(f"{len(tests)} passed")


def test_finetune_keeps_legacy_columns():
    """A parent that reads `only_attacks_in_hand` (the product net; the
    column left the default layout, docs/specs/card-rules.md) passes it to
    its child: the child's meta keeps it where the parent had it, and
    `widen` accepts the child's layout (it refused before)."""
    from test_card_rules_pins import product_net
    model, norm, pmeta = stsnet.load(str(product_net()))
    for kept in (finetune.vocab_for(pmeta), finetune.kept_vocab(pmeta)):
        meta = finetune.keep_legacy_columns(kept, pmeta)
        cards = stsnet.layout_of(meta)["columns"]["cards"]
        old = stsnet.layout_of(pmeta)["columns"]["cards"]
        assert "only_attacks_in_hand" in cards
        i = old.index("only_attacks_in_hand")
        assert cards[cards.index("only_attacks_in_hand") - 1] == old[i - 1]
        stsnet.widen(model, norm, pmeta, meta)
