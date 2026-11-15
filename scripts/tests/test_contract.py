"""Tests for the contract with the net (docs/decisions.md "Contract as built"): feature
batches and tiny pre-contract nets' outputs on the fixed state set stay as
pinned by contract_pins.py. Run with `python scripts/tests/test_contract.py`
(plain asserts; every `test_*` function runs) or with pytest."""

import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import bench_decisions  # noqa: E402
import contract_pins as pins  # noqa: E402
import golden  # noqa: E402  (contract_pins puts py/tests on the path)
import stsnet  # noqa: E402


def test_fixed_silent_set():
    """500 Silent decisions per standard Silent half, each replaying to a
    live state with at least two options."""
    fs = bench_decisions.load_fixed_silent()
    assert {h: len(r) for h, r in fs.items()} == {"silent_a": 500, "silent_b": 500}
    for half in fs.values():
        for d in half:
            c = bench_decisions.replay(d)
            assert d["character"] == "silent" and not c.is_over() and len(c.options(16)) >= 2, d


def test_encode_unchanged():
    """Features without `columns` encode golden.py's states byte for byte as
    golden_rows.npz, and the whole fixed set as pinned."""
    want = np.load(golden.PATH)
    got = golden.encode()
    assert set(got) == set(want.files)
    for k in want.files:
        assert got[k].dtype == want[k].dtype and got[k].tobytes() == want[k].tobytes(), k
    p = pins.load_pins()
    assert p["states"] == len(pins.fixed_states())
    assert pins.batches() == p["batches"]


def test_old_layout_unchanged():
    """A net saved with the layout of before threshold and held rows (full
    vocabularies, `row_kinds` ["triggered"]) gets the same batches on the
    fixed set as then, byte for byte."""
    with open(pins.OLD_LAYOUT, encoding="utf-8") as f:
        old = json.load(f)
    states = pins.fixed_states()
    for mode in pins.MODES:
        got = pins.batch_hashes(pins.old_layout_features(mode, old[mode]["layout"]).encode(states))
        assert got == old[mode]["batches"], mode


def test_tiny_nets_unchanged():
    """The tiny pre-contract nets give the pinned outputs, torch and Rust,
    bit for bit."""
    want = np.load(pins.OUTPUTS)
    got = pins.outputs()
    assert set(got) == set(want.files)
    for k in want.files:
        assert got[k].tobytes() == want[k].tobytes(), k


def test_modifier_list():
    """Effects mode gives a power a dimension by the explicit modifier list,
    which is exactly today's powers without hooks, less those effects mode
    doesn't encode yet (batches: test_encode_unchanged); ids mode keeps every
    power."""
    # The Guardian's damage-until-shift counter: no dimension; encoded as threshold rows.
    # Accuracy and Red Skull: static rows only (static-modifiers spec).
    # Intangible: replacement and countdown rows only (replacement-hooks spec).
    unencoded = ["ModeShift", "Accuracy", "RedSkull", "Intangible"]
    # Damage Down and Split Hits (mutated-monsters stage B) are modifier columns.
    assert sts.MODIFIER_POWERS == ["Strength", "Dexterity", "Vulnerable", "Weak", "Frail", "Artifact",
                                   "DamageDown", "SplitHits"]
    assert sorted(sts.MODIFIER_POWERS) == sorted(p for p in sts.power_names()
                                                 if p not in sts.hook_power_names() and p not in unencoded)
    eff = [n for n in sts.Features("effects").player_names if n.startswith("power_")]
    assert eff == [f"power_{p}" for p in sts.MODIFIER_POWERS] + ["power_unknown"]
    ids = [n for n in sts.Features("ids").player_names if n.startswith("power_")]
    assert ids == [f"power_{p}" for p in sts.power_names()] + ["power_unknown"]


def test_ids_names():
    """Ids card columns are `id_<name>` (no table position), then
    `id_unknown`, then the draw position columns; a status card's upgraded
    slot, which shares its name, is `id_<name>+`. Every path's names are
    distinct (the gather matches by name)."""
    names = sts.all_card_names()
    want = [f"id_{c}" + ("+" if c in names[:i] else "") for i, c in enumerate(names)] + ["id_unknown", "draw_position", "draw_above"]
    assert sts.Features("ids").card_names == want
    assert {"id_Wound+", "id_Slimed+", "id_Dazed+"} <= set(want)
    for mode in pins.MODES:
        for names in columns_of(sts.Features(mode)).values():
            assert len(set(names)) == len(names), mode


def test_row_kinds_and_piles():
    """Row kinds: triggered, then threshold and held (threshold-and-held-rows
    spec), static and countdown (static-modifiers), replacement (replacement-hooks); piles in the
    head's slot order; no parent piles yet."""
    assert sts.ROW_KINDS == ["triggered", "threshold", "held", "static", "countdown", "replacement", "pattern", "rule", "relic", "potion"]
    # Known top (spec 7): two piles that fold into `draw` for older nets.
    assert sts.PILES == ["hand", "draw", "discard", "exhaust", "playing", "next_draw", "known_later"]
    assert sts.PILE_PARENTS == {"next_draw": "draw", "known_later": "draw"}


PATHS = ("player", "monsters", "cards", "rows")


def columns_of(f):
    """A Features' column names per path, as `columns` takes them."""
    return dict(zip(PATHS, (f.player_names, f.monster_names, f.card_names, f.row_names)))


def assert_same(got, want, skip=()):
    assert set(got) == set(want)
    for k in want:
        if k not in skip:
            assert got[k].dtype == want[k].dtype and got[k].shape == want[k].shape, k
            assert got[k].tobytes() == want[k].tobytes(), k


def reordered(mode):
    """A vocabulary order that reorders columns: triggers reversed in
    effects mode (row columns), cards reversed in ids mode (card columns)."""
    if mode == "effects":
        return {"known_triggers": sts.trigger_names()[::-1]}
    # Distinct names: `known_cards` are names, and a status card's two
    # slots share one (its upgraded slot never occurs in a state).
    return {"known_cards": list(dict.fromkeys(sts.all_card_names()))[::-1]}


def test_gather_reorder():
    """An encoder whose vocabulary order differs writes, given the first
    encoder's `columns`, the first encoder's batch byte for byte."""
    states = pins.fixed_states()
    for mode in pins.MODES:
        a = sts.Features(mode)
        b_plain = sts.Features(mode, **reordered(mode))
        assert columns_of(b_plain) != columns_of(a), mode
        b = sts.Features(mode, **reordered(mode), columns=columns_of(a))
        assert columns_of(b) == columns_of(a) and b.dims == a.dims, mode
        assert_same(b.encode(states), a.encode(states))


def test_gather_append():
    """An encoder with one more effect scalar than the net writes the net's
    batch byte for byte."""
    states = pins.fixed_states()
    a = sts.Features("effects", known_effects=sts.effect_names()[1:])
    b = sts.Features("effects", columns=columns_of(a))
    assert b.dims == a.dims and b.dims != sts.Features("effects").dims
    assert_same(b.encode(states), a.encode(states))


def test_gather_removed():
    """A net column the encoder lacks reads 0; the rest are as before."""
    states = pins.fixed_states()[:300]
    a = sts.Features("effects")
    cols = columns_of(a)
    cols["player"] = cols["player"][:3] + ["gone"] + cols["player"][3:]
    cols["rows"] = cols["rows"] + ["gone_too"]
    b = sts.Features("effects", columns=cols)
    want, got = a.encode(states), b.encode(states)
    assert got["player"][:, 3].tobytes() == np.zeros(len(states), np.float32).tobytes()
    assert np.delete(got["player"], 3, axis=1).tobytes() == want["player"].tobytes()
    assert len(want["rows"]) > 0 and (got["rows"][:, -1] == 0).all()
    assert got["rows"][:, :-1].tobytes() == want["rows"].tobytes()
    assert_same(got, want, skip=("player", "rows"))


# The row kinds a default encoder writes (the opt-in kinds off).
DEFAULT_KINDS = ["triggered", "threshold", "held"]


def test_row_kind_drop():
    """With a test-only row kind injected (every row written again as a
    `test` row), a net that doesn't list it gets today's batch."""
    states = pins.fixed_states()
    today = sts.Features("effects").encode(states)
    inj = sts.Features("effects", test_inject=True)
    assert inj.row_kinds == DEFAULT_KINDS + ["test"]
    both = inj.encode(states)
    assert len(both["rows"]) == 2 * len(today["rows"]) > 0
    net = sts.Features("effects", test_inject=True, row_kinds=DEFAULT_KINDS, piles=sts.PILES)
    assert_same(net.encode(states), today)


def test_pile_fold():
    """With a test-only pile (parent: draw) holding the draw pile's cards, a
    net not listing it sees those cards in its draw slot: today's batch."""
    states = pins.fixed_states()
    for mode in pins.MODES:
        today = sts.Features(mode).encode(states)
        inj = sts.Features(mode, test_inject=True, row_kinds=DEFAULT_KINDS)
        assert inj.piles == sts.PILES + ["test"] and inj.dims["piles"] == len(sts.PILES) + 1
        got = inj.encode(states)
        draw = today["card_pile"] == sts.PILES.index("draw")
        assert draw.any() and (got["card_pile"][draw] == len(sts.PILES)).all()
        assert (got["card_pile"][~draw] == today["card_pile"][~draw]).all()
        net = sts.Features(mode, test_inject=True, row_kinds=DEFAULT_KINDS, piles=sts.PILES)
        assert net.dims["piles"] == len(sts.PILES)
        assert_same(net.encode(states), today)
    # A pile neither listed nor with a listed parent is refused.
    try:
        sts.Features("effects", piles=["hand", "draw", "discard", "exhaust"])
        raise AssertionError("unlisted pile without a parent accepted")
    except ValueError as e:
        assert "playing" in str(e)


def test_gather_net_outputs():
    """Both forward passes read the gathered batch as the net's own: a tiny
    net loaded through a reordered encoder with its `columns` gives the
    pinned outputs bit for bit, torch and Rust."""
    states = pins.fixed_states()
    want = np.load(pins.OUTPUTS)
    for name, mode, _ in pins.NETS:
        model, norm, meta = stsnet.load_pre_contract(pins.net_path(name))
        # The default row kinds: listing the opt-in ones would turn them on.
        meta = {**meta, **reordered(mode), "columns": columns_of(stsnet.features_for(meta)),
                "row_kinds": sts.Features(mode).row_kinds, "piles": sts.PILES}
        b = stsnet.features_for(meta).encode(states, heuristic=True)
        with torch.no_grad():
            got = stsnet.score_of(model, norm.tensors(b)).numpy().astype(np.float32)
        assert got.tobytes() == want[f"{name}/torch"].tobytes(), name
        rust = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(states), np.float32)
        assert rust.tobytes() == want[f"{name}/rust"].tobytes(), name


def test_pile_count_from_net():
    """A net whose features have one more pile slot builds and scores in
    both passes (the pile count comes from the net, not sts.PILES)."""
    states = pins.fixed_states()[:50]
    feats = sts.Features("effects", test_inject=True, row_kinds=["triggered"])
    torch.manual_seed(0)
    model = stsnet.ValueNet(feats.dims, width=8, row_width=4)
    b = feats.encode(states)
    ds = stsnet.Dataset.from_batches([b], np.zeros(len(states), np.float32))
    norm = stsnet.Normalizer.fit(ds)
    with torch.no_grad():
        t = stsnet.score_of(model, norm.tensors(b)).numpy()
    assert model.n_piles == len(sts.PILES) + 1
    weights = {k: v.detach().numpy().astype(np.float32) for k, v in model.state_dict().items()}
    try:
        sts.NetEvaluator(weights, norm.state_dict(), {"card_repr": "effects"})
        raise AssertionError("pile count mismatch accepted")
    except ValueError as e:
        assert "pile slots" in str(e)
    # The Rust pass has no test_inject: check it against the torch pass with
    # an encoder whose pile list is one longer (the extra slot stays empty).
    piles = sts.PILES + ["spare"]
    ev = sts.NetEvaluator(weights, norm.state_dict(), {"card_repr": "effects", "piles": piles})
    b2 = sts.Features("effects", piles=piles).encode(states)
    with torch.no_grad():
        t2 = stsnet.score_of(model, norm.tensors(b2)).numpy()
    assert np.allclose(np.asarray(ev.score(states)), t2, atol=1e-5)
    assert t.shape == t2.shape


def test_tiny_nets_are_pre_contract():
    """The pinned nets are saved the old way: `rows` format, no schema."""
    for name, mode, hp in pins.NETS:
        d = torch.load(pins.net_path(name), weights_only=False)
        assert d["meta"] == {"card_repr": mode, "format": "rows"} and "schema" not in d, name
        assert d.get("hp_loss", False) == hp, name


def tiny_trained(meta, hp=False, steps=20):
    """A tiny net trained a few steps on the fixed set under `meta`'s
    features (random targets), with its normaliser."""
    states = pins.fixed_states()
    feats = stsnet.features_for(meta)
    b = feats.encode(states, heuristic=True)
    ds = stsnet.Dataset.from_batches([b], np.zeros(len(states), np.float32))
    norm = stsnet.Normalizer.fit(ds)
    torch.manual_seed(1)
    model = stsnet.ValueNet(feats.dims, width=8, row_width=4, hp_loss=hp)
    t = norm.tensors(b)
    target = torch.rand(len(states)) * 2
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    for _ in range(steps):
        opt.zero_grad()
        loss = ((stsnet.score_of(model, t) - target) ** 2).mean()
        loss.backward()
        opt.step()
    return model.eval(), norm


def both_passes(model, norm, meta, states):
    b = stsnet.features_for(meta).encode(states, heuristic=True)
    with torch.no_grad():
        t = stsnet.score_of(model, norm.tensors(b)).numpy().astype(np.float32)
    r = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(states), np.float32)
    return t, r


def test_save_load_identity():
    """A tiny net trained under the contract, saved and loaded, gives the
    same outputs bit for bit on the fixed set, torch and Rust; the file
    holds the schema, its layout (normaliser aligned) and, for an HP net,
    its bin_rep."""
    import tempfile
    states = pins.fixed_states()
    metas = [({"card_repr": "effects", **reordered("effects")}, False), ({"card_repr": "ids"}, False),
             ({"card_repr": "effects"}, True)]
    for meta, hp in metas:
        model, norm = tiny_trained(meta, hp)
        before = both_passes(model, norm, meta, states)
        path = os.path.join(tempfile.mkdtemp(), "m.pt")
        stsnet.save(path, model, norm, meta)
        d = torch.load(path, weights_only=False)
        assert d["schema"] == stsnet.SCHEMA == 1
        assert d["columns"] == columns_of(stsnet.features_for(meta))
        assert d["row_kinds"] == DEFAULT_KINDS and d["piles"] == sts.PILES
        for k in PATHS:
            assert len(d["norm"][k][0]) == len(d["norm"][k][1]) == len(d["columns"][k]), k
        assert ("bin_rep" in d) == hp and (not hp or d["bin_rep"] == stsnet.BIN_REP.tolist())
        model2, norm2, meta2 = stsnet.load(path)
        assert {k: meta2[k] for k in stsnet.LAYOUT_KEYS} == {k: d[k] for k in stsnet.LAYOUT_KEYS}
        after = both_passes(model2, norm2, meta2, states)
        for x, y in zip(before, after):
            assert x.tobytes() == y.tobytes(), meta


def test_saved_bin_rep_used():
    """Loading an HP-histogram net scores with its saved bin_rep, in both
    passes, not the code's constant."""
    import tempfile
    states = pins.fixed_states()[:200]
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta, hp=True, steps=2)
    path = os.path.join(tempfile.mkdtemp(), "m.pt")
    stsnet.save(path, model, norm, meta)
    d = torch.load(path, weights_only=False)
    d["bin_rep"] = [x + 3.0 for x in d["bin_rep"]]
    torch.save(d, path)
    model2, norm2, meta2 = stsnet.load(path)
    shifted = both_passes(model2, norm2, meta2, states)
    model.bin_rep = np.asarray(d["bin_rep"], np.float32)
    want = both_passes(model, norm, meta, states)
    for x, y in zip(shifted, want):
        assert x.tobytes() == y.tobytes()
    del model.bin_rep
    base = both_passes(model, norm, meta, states)
    assert not np.array_equal(shifted[0], base[0]) and not np.array_equal(shifted[1], base[1])


def test_schema_refuses_newer():
    """A net saved under a later schema is refused, naming both versions."""
    import tempfile
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta, steps=1)
    path = os.path.join(tempfile.mkdtemp(), "m.pt")
    stsnet.save(path, model, norm, meta)
    d = torch.load(path, weights_only=False)
    d["schema"] = stsnet.SCHEMA + 1
    torch.save(d, path)
    try:
        stsnet.load(path)
        raise AssertionError("newer schema accepted")
    except ValueError as e:
        assert f"schema {stsnet.SCHEMA + 1}" in str(e) and f"schema {stsnet.SCHEMA}" in str(e), e


def test_pre_contract_refused():
    """A pre-contract net loads only through its converted file beside it:
    without one it is refused with a message naming convert_net.py; with
    one, `load` returns the converted net. `load_pre_contract` reads the
    old file and refuses a contract net."""
    import shutil
    import tempfile
    d = tempfile.mkdtemp()
    old = os.path.join(d, "net.pt")
    shutil.copy(pins.net_path("tiny_effects.pt"), old)
    try:
        stsnet.load(old)
        raise AssertionError("pre-contract net accepted")
    except ValueError as e:
        assert "convert_net.py" in str(e) and "net.contract.pt" in str(e), e
    assert stsnet.contract_path(old) == os.path.join(d, "net.contract.pt")
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta, steps=1)
    stsnet.save(stsnet.contract_path(old), model, norm, meta)
    model2, _, meta2 = stsnet.load(old)
    assert meta2["columns"] == columns_of(sts.Features("effects"))
    for a, b in zip(model.state_dict().values(), model2.state_dict().values()):
        assert torch.equal(a, b)
    try:
        stsnet.load_pre_contract(stsnet.contract_path(old))
        raise AssertionError("contract net read as pre-contract")
    except ValueError as e:
        assert "stsnet.load" in str(e)


def test_save_refuses_mismatched_widths():
    """`save` refuses a net whose widths don't match its meta's encoder."""
    import tempfile
    model, norm = tiny_trained({"card_repr": "effects"}, steps=1)
    try:
        stsnet.save(os.path.join(tempfile.mkdtemp(), "m.pt"), model, norm, {"card_repr": "ids"})
        raise AssertionError("mismatched net saved")
    except ValueError as e:
        assert "doesn't match" in str(e), e


def copy_tiny(name):
    """A pinned tiny net copied into a fresh folder, so converting it writes
    there and never beside the pins."""
    import shutil
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), name)
    shutil.copy(pins.net_path(name), path)
    return path


def test_converter_identity():
    """Each pinned tiny net, converted: a schema-1 file beside it with
    today's column names (ids `id_<name>`, no table numbers), weights and
    normaliser unchanged, and outputs on the fixed set equal to the pins
    bit for bit, torch and Rust, loaded by the old path."""
    import re
    import convert_net
    want = np.load(pins.OUTPUTS)
    for name, mode, hp in pins.NETS:
        old = copy_tiny(name)
        conv = convert_net.convert(old, pins.fixed_states())
        assert conv == stsnet.contract_path(old) and os.path.exists(conv)
        d0, d1 = (torch.load(p, weights_only=False) for p in (old, conv))
        assert d1["schema"] == 1 and d1["columns"] == columns_of(sts.Features(mode)), name
        assert not any(re.match(r"id_\d+_", c) for c in d1["columns"]["cards"]), name
        assert d1["norm"] == d0["norm"], name
        for k, v in d0["state"].items():
            assert torch.equal(v, d1["state"][k]), (name, k)
        model, norm, meta = stsnet.load(old)
        t, r = both_passes(model, norm, meta, pins.fixed_states())
        assert t.tobytes() == want[f"{name}/torch"].tobytes(), name
        assert r.tobytes() == want[f"{name}/rust"].tobytes(), name


def test_converter_refuses():
    """Refused, with nothing written: a net whose widths don't match its
    vocabularies' encoder, a correction net, a quantile HP net, a non-`rows`
    layout, a contract net; and an existing converted file is never
    overwritten."""
    import convert_net

    def refused(path, why):
        try:
            convert_net.convert(path, pins.fixed_states()[:50])
            raise AssertionError(f"converted: {why}")
        except convert_net.Refused as e:
            assert why in str(e), (why, e)
        assert not os.path.exists(stsnet.contract_path(path)), why

    def variant(change):
        path = copy_tiny("tiny_effects.pt")
        d = torch.load(path, weights_only=False)
        change(d)
        torch.save(d, path)
        return path

    refused(variant(lambda d: d["meta"].update(known_powers=["Strength"])), "doesn't match")
    refused(variant(lambda d: d.update(correction=True)), "correction")
    refused(variant(lambda d: d.update(hp_loss=True)), "quantile")
    refused(variant(lambda d: d["meta"].update(format="flat")), "format")
    refused(variant(lambda d: d.update(schema=1)), "contract net")
    path = copy_tiny("tiny_effects.pt")
    with open(stsnet.contract_path(path), "wb") as f:
        f.write(b"keep")
    try:
        convert_net.convert(path, pins.fixed_states()[:50])
        raise AssertionError("existing converted file overwritten")
    except convert_net.Refused as e:
        assert "exists" in str(e), e
    with open(stsnet.contract_path(path), "rb") as f:
        assert f.read() == b"keep"


def test_records_roundtrip():
    """Every action form parses and formats back to the same text; reserved
    forms raise on replay; dict specs play the same games as tuple specs;
    an old record without newer keys replays unchanged."""
    import action_text as at
    import registry
    forms = ["End", "Strike", "Bash@1", "Strike+@0", "Done", "Choose:Shrug It Off", "Choose:#3", "Potion:0",
             "Potion:2@1", "Strike{cost=0/turn}", "Bash{cost=1/combat,damage=12/combat}@2"]
    for s in forms:
        assert at.format_action(at.parse_action(s)) == s, s
    assert at.format_action(at.parse_action("Bash{damage=12/combat,cost=1/combat}")) == "Bash{cost=1/combat,damage=12/combat}"
    for bad in ["", "Choose:", "Choose:#x", "Potion:", "Potion:a", "Bash@x", "Bash{}", "Bash{cost=1}", "Bash{cost"]:
        try:
            at.parse_action(bad)
            raise AssertionError(f"parsed {bad!r}")
        except at.NotSupported:
            raise AssertionError(f"{bad!r} is malformed, not reserved")
        except ValueError:
            pass
    # Built in spec 6 (decision points): `Done` and choosing a card.
    assert at.decode_action("Done") == sts.Action.done()
    assert at.decode_action("Choose:Strike") == sts.Action.choose("Strike")
    # Built in docs/specs/potions.md: a potion use by list position and target.
    assert at.decode_action("Potion:1@0") == sts.Action.potion(1, 0)
    assert at.decode_action("Potion:2") == sts.Action.potion(2)
    for s, spec in [("Choose:#0", "inline options"), ("Strike{cost=0/turn}@0", "spec 8")]:
        try:
            at.decode_action(s)
            raise AssertionError(f"replayed {s!r}")
        except at.NotSupported as e:
            assert spec in str(e), e
    # One shared module: registry and bench_decisions use the same functions.
    assert registry.encode_action is at.encode_action is bench_decisions.encode_action
    assert registry.decode_action is at.decode_action is bench_decisions.decode_action

    deck = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
    tuples = [("cultist", deck, 11), ("jaw_worm", deck, 12, 30)]
    dicts = [{"encounter": "cultist", "deck": deck, "seed": 11}, {"encounter": "jaw_worm", "deck": deck, "seed": 12, "hp": 30}]
    a = sts.run("greedy", tuples, record=True, threads=1)
    b = sts.run("greedy", dicts, record=True, threads=1)
    for x, y in zip(a, b):
        assert [at.encode_action(s) for s in x["actions"]] == [at.encode_action(s) for s in y["actions"]]
        assert (x["score"], x["hp_end"], x["turns"]) == (y["score"], y["hp_end"], y["turns"])
    for bad in [{"encounter": "cultist", "deck": deck}, {"encounter": "cultist", "deck": deck, "seed": 1, "colour": 2}]:
        try:
            sts.run("greedy", [bad])
            raise AssertionError(f"ran {bad}")
        except ValueError:
            pass

    recs = registry.records(tuples, [0, 0], a)
    for rec, r in zip(recs, a):
        old = {k: v for k, v in rec.items() if k not in ("character", "no_death") and not (k == "hp" and v is None)}
        for g in (rec, old):
            rp = registry.replay(g)
            assert [at.encode_action(s) for s in rp["actions"]] == rec["actions"]
            assert [s.encode() for s in rp["states"]] == [s.encode() for s in r["states"]]
    d = bench_decisions.load_fixed_silent()["silent_a"][0]
    old = {k: v for k, v in d.items() if k != "hp" or v is not None}
    assert bench_decisions.replay(old).encode() == bench_decisions.replay(d).encode()


def test_names_safe():
    """No card name contains a character the action text reserves, and none
    is one of the bare reserved words."""
    import action_text as at
    for name in sts.all_card_names():
        assert not any(ch in name for ch in at.RESERVED_CHARS), name
        assert name not in ("End", "Done") and not name.startswith(("Choose", "Potion")), name


if __name__ == "__main__":
    tests =[v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} passed")
