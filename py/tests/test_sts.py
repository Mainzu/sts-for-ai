"""Tests for the `sts` Python module. Run with `python py/tests/test_sts.py`
(plain asserts; every `test_*` function runs) or with pytest."""

import numpy as np
import sts

STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def play_greedy(c, limit=500):
    for _ in range(limit):
        if c.is_over():
            return
        c.step(sts.greedy_action(c))
    raise AssertionError("combat did not end")


def test_round_trip():
    c = sts.Combat(STARTER, "jaw_worm", seed=1)
    assert not c.is_over() and c.player_hp() == 80
    acts = c.legal_actions()
    assert len(acts) == len(set(acts))
    assert acts[-1].is_end_turn and sts.action_name(acts[-1]) == "EndTurn"
    names = [sts.action_name(a) for a in acts]
    assert any(n.startswith("Strike -> slot 0") for n in names) or "Strike" not in c.piles()["hand"]
    assert sts.Action("Defend") == sts.Action("Defend", None)
    try:
        c.step(sts.Action("Carnage"))
        raise AssertionError("illegal action accepted")
    except ValueError:
        pass
    play_greedy(c)
    assert c.is_over() and isinstance(c.won(), bool)
    assert 0 <= c.player_hp() <= 80
    assert c.legal_actions() == []
    assert "HP" in c.render()


def test_options():
    c = sts.Combat(STARTER + ["Pommel Strike", "Sword Boomerang"], "two_louse", seed=4)
    for _ in range(6):
        if c.is_over():
            break
        opts = c.options(16)
        seen = []
        for actions, kind, outcomes in opts:
            assert kind in ("deterministic", "chance", "divergent")
            assert abs(sum(p for p, _ in outcomes) - 1.0) < 1e-9
            if kind != "chance":
                assert len(outcomes) == 1
            seen += actions
        assert sorted(map(repr, seen)) == sorted(map(repr, c.legal_actions()))
        c.step(sts.greedy_action(c))


def test_determinism():
    def trace(seed):
        c = sts.Combat(STARTER, "slime_boss", seed=seed)
        out = []
        while not c.is_over():
            a = sts.search_action(c, "heuristic")
            out.append(repr(a))
            c.step(a)
        return out, c.player_hp(), c.render()

    assert trace(3) == trace(3)
    specs = sts.make_specs("elite", 12, extra=5, seed=2)
    assert specs == sts.make_specs("elite", 12, extra=5, seed=2)
    r1 = sts.run("search", specs)
    r2 = sts.run("search", specs, threads=1)
    assert [(r["won"], r["hp_end"], r["turns"]) for r in r1] == [(r["won"], r["hp_end"], r["turns"]) for r in r2]
    a = sts.Combat(STARTER, "cultist", seed=9)
    b = a.clone()
    play_greedy(a)
    play_greedy(b)
    assert a.render() == b.render()


def test_feature_shapes():
    enc = sts.Features()
    d = enc.dims
    c = sts.Combat(STARTER + ["Anger", "Wild Strike"], "lots_of_slimes", seed=5)
    while not c.is_over():
        f = enc.encode([c])
        assert f["player"].shape == (1, d["player"]) and f["player"].dtype == np.float32
        assert f["monsters"].shape == (1, 5, d["monster"])
        n = f["cards"].shape[0]
        assert f["cards"].shape == (n, d["card"])
        assert f["card_count"].shape == (n,) and f["card_pile"].shape == (n,) and f["card_state"].shape == (n,)
        assert (f["card_state"] == 0).all() and f["card_pile"].max(initial=0) < len(sts.PILES)
        piles = c.piles()
        assert f["card_count"].sum() == sum(sum(p.values()) for p in piles.values())
        c.step(sts.greedy_action(c))
    # A batch of several states keeps them apart.
    cs = [sts.Combat(STARTER, e, seed=1) for e in ("cultist", "three_louse", "slime_boss")]
    f = enc.encode(cs)
    assert f["player"].shape[0] == 3 and set(f["card_state"].tolist()) == {0, 1, 2}
    assert len(enc.player_names) == d["player"] and len(enc.monster_names) == d["monster"]
    assert len(enc.card_names) == d["card"] and len(enc.row_names) == d["row"]
    assert f["rows"].shape == (len(f["row_card"]), d["row"]) and f["rows"].dtype == np.float32
    assert len(f["row_entity"]) == len(f["row_state"]) == len(f["row_card"])


def card_row(enc, name, known_cards=None):
    """Feature vector of one card, read back from a combat holding it in hand."""
    deck = [name] * 10
    c = sts.Combat(deck, "cultist", seed=1)
    f = enc.encode([c])
    hand = f["card_pile"] == sts.PILES.index("hand")
    rows = f["cards"][hand]
    assert len(rows) == 1
    return rows[0]


def test_effects_vs_ids():
    eff = sts.Features("effects")
    ids = sts.Features("ids")
    # Every card id + unknown by default.
    assert ids.dims["card"] == len(sts.all_card_names()) + 3, "id_unknown and the draw position columns"
    strike, strike_up = card_row(eff, "Strike"), card_row(eff, "Strike+")
    i = eff.card_names.index("damage_single")
    assert strike[i] == 6 and strike_up[i] == 9
    assert strike[eff.card_names.index("cost")] == 1
    # Twin Strike: 2 hits of 5.
    twin = card_row(eff, "Twin Strike")
    assert twin[i] == 10 and twin[eff.card_names.index("hits_single")] == 2
    # Ids: one-hot, distinct for Strike and Strike+.
    a, b = card_row(ids, "Strike"), card_row(ids, "Strike+")
    assert a.sum() == 1 and b.sum() == 1 and (a != b).any()
    # A card outside known_cards lands in the unknown slot; effects ignore known_cards.
    ids_k = sts.Features("ids", known_cards=["Defend"])
    u = card_row(ids_k, "Strike")
    assert u[ids_k.card_names.index("id_unknown")] == 1 and u.sum() == 1
    eff_k = sts.Features("effects", known_cards=["Defend"])
    assert (card_row(eff_k, "Strike") == strike).all()
    try:
        sts.Features("names")
        raise AssertionError("bad card_repr accepted")
    except ValueError:
        pass


def test_unknown_power():
    c = sts.Combat(["Bash"] * 10, "jaw_worm", seed=1)
    c.step(sts.Action("Bash", 0))  # Vulnerable 2 on the Jaw Worm
    full = sts.Features()
    vul = full.monster_names.index("power_Vulnerable")
    unk = full.monster_names.index("power_unknown")
    m = full.encode([c])["monsters"][0, 0]
    assert m[vul] == 2 and m[unk] == 0
    # Known powers are the dimensions, in the order given; the rest are unknown.
    part = sts.Features(known_powers=["Weak", "Strength"])
    assert part.player_names[-3:] == ["power_Weak", "power_Strength", "power_unknown"]
    pu = part.monster_names.index("power_unknown")
    m = part.encode([c])["monsters"][0, 0]
    assert "power_Vulnerable" not in part.monster_names and m[pu] == 2
    one = sts.Features(known_powers=["Strength"])
    assert c.features(known_powers=["Strength"])["monsters"][0, 0, one.monster_names.index("power_unknown")] == 2
    # A card applying a power outside known_powers encodes it as unknown too.
    bash_full = card_row(full, "Bash")
    bash_part = card_row(part, "Bash")
    vi = full.card_names.index("apply_opponent_Vulnerable")
    ui = full.card_names.index("apply_opponent_unknown")
    assert bash_full[vi] == 2 and bash_full[ui] == 0
    assert bash_part[part.card_names.index("apply_opponent_unknown")] == 2
    try:
        sts.Features(known_powers=["Telekinesis"])
        raise AssertionError("unknown power name accepted")
    except ValueError:
        pass


def test_python_evaluator():
    enc = sts.Features()
    hp = enc.monster_names.index("hp")
    calls = []

    def make(sign):
        def ev(batch):
            calls.append(batch["player"].shape[0])
            return sign * batch["monsters"][:, :, hp].sum(axis=1)
        return ev

    # A hand with both an attack and Defend.
    for seed in range(50):
        c = sts.Combat(STARTER, "jaw_worm", seed=seed)
        hand = c.piles()["hand"]
        if "Defend" in hand and ("Strike" in hand or "Bash" in hand):
            break
    calls.clear()
    r = sts.search(c, make(-1.0), features=enc)
    assert len(calls) == 1 and calls[0] == r["leaves"] > 0
    assert r["action"].card in ("Strike", "Bash")
    best = max(v for _, v in r["options"])
    assert any(r["action"] in acts and v == best for acts, v in r["options"])
    calls.clear()
    a = sts.search_action(c, make(1.0), features=enc)
    assert len(calls) == 1
    assert a.card not in ("Strike", "Bash")
    # Errors in the evaluator surface as Python exceptions.
    def bad(batch):
        raise RuntimeError("boom")
    try:
        sts.search_action(c, bad)
        raise AssertionError("evaluator error swallowed")
    except RuntimeError:
        pass
    try:
        sts.search_action(c, lambda b: [0.0])
        raise AssertionError("wrong length accepted")
    except ValueError:
        pass


def test_run_and_record():
    specs = sts.make_specs("hallway", 10, extra=5, seed=1)
    assert len(specs) == 10 and all(len(s) == 3 for s in specs)
    for agent in ("random", "greedy", "search"):
        res = sts.run(agent, specs)
        assert len(res) == 10
        assert all(set(r) >= {"won", "hp_start", "hp_end", "turns", "score", "encounter"} for r in res)
    res = sts.run("greedy", specs[:2], record=True)
    states, actions = res[0]["states"], res[0]["actions"]
    assert len(states) == len(actions) > 0
    f = sts.Features().encode(states)
    assert f["player"].shape[0] == len(states)
    # A Python evaluator through the runner, across threads.
    enc = sts.Features()
    seen = []
    res = sts.run("search", specs[:4], evaluator=lambda b: (seen.append(1), np.zeros(b["player"].shape[0]))[1], features=enc, threads=4)
    assert len(res) == 4 and len(seen) > 0
    # Card pool restricts the extra cards.
    specs = sts.make_specs("hallway", 20, extra=5, seed=1, card_pool=["Cleave"])
    extras = {c for _, deck, _ in specs for c in deck} - {"Strike", "Defend", "Bash"}
    assert extras == {"Cleave"}


def test_stalled_flag_and_exports():
    """A combat still running past PLAY_TURN_LIMIT turns is lost and flagged
    `stalled` (its hp_end is the HP left); MAX_MONSTERS is the slot count."""
    assert sts.MAX_MONSTERS == len(sts.Combat(["Strike"], "cultist").monster_numbers())
    deck = ["Defend"] * 10
    r = sts.run("greedy", [("jaw_worm", deck, 1), ("jaw_worm", sts.starter_deck("ironclad"), 1)], hp=20000)
    assert [x["stalled"] for x in r] == [True, False]
    assert r[0]["turns"] == sts.PLAY_TURN_LIMIT + 1 and not r[0]["won"]
    p = sts.play_on([sts.Combat(deck, "jaw_worm", seed=1, hp=20000)], limit=4)[0]
    assert p["stalled"] and p["turns"] > sts.PLAY_TURN_LIMIT


def test_golden_features_unchanged():
    """States encode byte for byte as the build that recorded
    py/tests/data/golden_rows.npz (the rows format)."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import golden
    want = np.load(golden.PATH)
    got = golden.encode()
    assert set(got) == set(want.files)
    for k in want.files:
        assert got[k].dtype == want[k].dtype and got[k].shape == want[k].shape, k
        assert got[k].tobytes() == want[k].tobytes(), k


SILENT = sts.starter_deck("silent")


def test_silent_combat():
    assert sts.character_names() == ["ironclad", "silent"]
    assert sorted(SILENT) == sorted(["Silent Strike"] * 5 + ["Silent Defend"] * 6 + ["Neutralize"])
    c = sts.Combat(SILENT, "jaw_worm", seed=2, character="silent")
    assert c.character == "silent" and c.player_hp() == 70
    assert sum(c.piles()["hand"].values()) == 7, "Ring of the Snake"
    play_greedy(c)
    assert 0 <= c.player_hp() <= 70
    pool = sts.class_card_names("silent")
    assert "Blade Dance" in pool and "Shiv" not in pool and "Strike" not in pool
    assert set(sts.deck_card_names()).isdisjoint(pool), "Ironclad pool has no Silent cards"
    specs = sts.make_specs("hallway", 6, extra=5, seed=1, character="silent")
    assert all(d[:12] == specs[0][1][:12] for _, d, _ in specs)
    assert all(set(d[12:]) <= set(pool) for _, d, _ in specs)
    res = sts.run("search", specs, character="silent")
    assert all(r["hp_start"] == 70 for r in res)
    # Ironclad specs are unchanged by the character argument's default.
    assert sts.make_specs("elite", 8, seed=3) == sts.make_specs("elite", 8, seed=3, character="ironclad")


def test_new_content_and_layout():
    f = sts.Features()
    # Effects mode: modifier powers are dimensions; hook powers (Poison) are rows.
    assert "power_Poison" not in f.player_names and "power_Strength" in f.player_names
    assert "apply_opponent_Poison" not in f.card_names
    # Blade Dance: add_hand and the Shivs' damage.
    bd = card_row(f, "Blade Dance")
    assert bd[f.card_names.index("add_hand")] == 3 and bd[f.card_names.index("added_damage")] == 12
    # Silent Strike encodes like Strike in effects mode; ids gives it its own id.
    assert (card_row(f, "Silent Strike") == card_row(f, "Strike")).all()
    assert card_row(sts.Features("ids"), "Silent Strike")[-1] == 0
    try:
        sts.Features(layout="full")
        raise AssertionError("dropped layout argument accepted")
    except TypeError:
        pass


def test_amount_expression_columns():
    """Amount expressions (docs/specs/amount-expressions.md): the legacy
    primitive columns from the expression, the form, and the value now
    (turn 1: 3 energy, no block, no Strength)."""
    f = sts.Features()
    n = f.card_names

    def cols(name, *keys):
        r = card_row(f, name)
        return [float(r[n.index(k)]) for k in keys]

    assert cols("Body Slam", "damage_from_block", "expr_k", "expr_q_block", "expr_value", "damage_single") == [1, 1, 1, 0, 0]
    assert cols("Heavy Blade", "strength_mult_base", "strength_mult", "expr_base", "expr_k", "expr_q_strength",
                "expr_value") == [14, 3, 14, 2, 1, 14]
    # Ten Perfected Strikes in the deck, all in hand and draw: 6 + 2 x 10.
    assert cols("Perfected Strike", "per_strike_base", "per_strike", "expr_q_strike", "expr_value", "is_strike") ==         [6, 2, 1, 26, 1]
    assert cols("Whirlwind", "x_cost", "cost", "expr_base", "expr_k", "expr_q_energy", "expr_all", "expr_value",
                "damage_all") == [1, 0, 0, 5, 1, 1, 15, 0]
    assert "Whirlwind" not in sts.deck_card_names() and "Whirlwind" not in sts.held_out_card_names()


def rows_of(b, names, entity=None, card=None, patterns=False):
    """`{name: value}` (non-zero only) for each row of an entity or card
    entry; a monster's `pattern` rows only with `patterns`."""
    sel = b["row_entity"] == entity if entity is not None else b["row_card"] == card
    rows = [{names[i]: float(x) for i, x in enumerate(r) if x} for r in b["rows"][sel]]
    return rows if patterns else [r for r in rows if "trigger_Pattern(Next)" not in r]


def card_entry(b, name, f):
    """Index of the hand entry holding card `name` (one-hot id via a lookup)."""
    want = card_row(f, name)
    hand = np.flatnonzero(b["card_pile"] == sts.PILES.index("hand"))
    return next(int(i) for i in hand if (b["cards"][i] == want).all())


def test_power_rows_are_hooks_times_stacks():
    f = sts.Features()
    n = f.row_names
    # Lagavulin starts with Metallicize 8: one row, turn end → 8 block.
    b = f.encode([sts.Combat(STARTER, "lagavulin", seed=1)])
    assert rows_of(b, n, entity=1) == [{"trigger_OwnerTurnEnd": 1, "condition_Always": 1, "grant_own": 1, "block": 8}]
    assert (b["row_state"] == 0).all()
    # Poison 5 on a Jaw Worm: turn start → lose 5 HP, then one stack fewer.
    c = sts.Combat(["Deadly Poison"] * 10, "jaw_worm", seed=1, character="silent")
    c.step(sts.Action("Deadly Poison", 0))
    b = f.encode([c])
    assert rows_of(b, n, entity=1) == [
        {"trigger_OwnerTurnStart": 1, "condition_Always": 1, "grant_own": 1, "lose_hp": 5, "reduce_self": 1}]
    # Rage 3 on the player: two hooks, the first conditional.
    c = sts.Combat(["Rage"] * 10, "jaw_worm", seed=1)
    c.step(sts.Action("Rage"))
    b = f.encode([c])
    assert rows_of(b, n, entity=0) == [
        {"trigger_CardPlayed(Owner)": 1, "condition_CardType(Attack)": 1, "grant_own": 1, "block": 3},
        {"trigger_OwnerTurnEnd": 1, "condition_Always": 1, "grant_own": 1, "remove_self": 1}]
    # Two Rages: the stacks double the amounts, not the remove.
    c.step(sts.Action("Rage"))
    assert rows_of(f.encode([c]), n, entity=0)[0]["block"] == 6
    # A second state in the batch: its entities are offset by ENTITIES.
    b = f.encode([c, sts.Combat(STARTER, "lagavulin", seed=1)])
    assert rows_of(b, n, entity=sts.ENTITIES + 1)[0]["block"] == 8
    assert set(b["row_state"][b["row_entity"] == sts.ENTITIES + 1].tolist()) == {1}


def test_static_rows():
    """Static modifiers (docs/specs/static-modifiers.md): an entity's
    modifiers write `static` rows and their countdowns `RoundEnd` rows, beside
    the power dimensions; a card applying one grants them. Old row kinds
    alone (the pre-series list) leave none of them."""
    f = sts.Features(extra_rows=True)
    n = f.row_names
    c = sts.Combat(["Inflame"] * 5 + ["Clothesline"] * 5, "jaw_worm", seed=1)
    c.step(sts.Action("Inflame"))
    b = f.encode([c])
    assert rows_of(b, n, entity=0) == [
        {"trigger_Static(DamageDealt)": 1, "condition_Always": 1, "grant_own": 1, "static_add": 2}]
    c.step(sts.Action("Clothesline", 0))
    m = rows_of(f.encode([c]), n, entity=1)
    assert m == [{"trigger_RoundEnd": 1, "condition_Always": 1, "grant_own": 1, "reduce_self": 1},
                 {"trigger_Static(DamageDealt)": 1, "condition_Always": 1, "grant_own": 1, "static_mult": -0.25}]
    # Bash: its play row, then Vulnerable's two rows granted to the opponent.
    b = f.encode([sts.Combat(["Bash"] * 10, "jaw_worm", seed=1)])
    bash = card_entry(b, "Bash", f)
    assert rows_of(b, n, card=bash)[1:] == [
        {"trigger_RoundEnd": 1, "condition_Always": 1, "grant_opponent": 1, "reduce_self": 1},
        {"trigger_Static(DamageTaken)": 1, "condition_Always": 1, "grant_opponent": 1, "static_mult": 0.5}]
    old = sts.Features()  # the opt-in kinds off: today's default
    ob = old.encode([c])
    new_triggers = [i for i, x in enumerate(old.row_names) if x == "trigger_RoundEnd" or x.startswith("trigger_Static(")]
    assert len(ob["rows"]) > 0 and not ob["rows"][:, new_triggers].any()
    assert len(ob["rows"]) < len(f.encode([c])["rows"])
    # A layout listing one opt-in kind turns them on and keeps only that one:
    # Bash's cached card rows and the Jaw Worm's lose their countdown rows.
    part = sts.Features(row_kinds=["triggered", "threshold", "held", "static"])
    assert part.extra_rows
    pb = part.encode([sts.Combat(["Bash"] * 10, "jaw_worm", seed=1)])
    assert rows_of(pb, part.row_names, card=card_entry(pb, "Bash", part))[1:] == [
        {"trigger_Static(DamageTaken)": 1, "condition_Always": 1, "grant_opponent": 1, "static_mult": 0.5}]
    assert rows_of(part.encode([c]), part.row_names, entity=1) == [
        {"trigger_Static(DamageDealt)": 1, "condition_Always": 1, "grant_own": 1, "static_mult": -0.25}]
    assert sts.hook_power_names() == ["Ritual", "CurlUp", "Enrage", "Metallicize", "SporeCloud", "LoseStrength",
                                      "Poison", "Combust", "CombustDamage", "Brutality", "Rupture", "DemonForm",
                                      "Rage", "SharpHide", "RedSkull", "WraithForm", "Thorns", "Burst", "WeakOnHit"]
    assert "Static(BlockGained)" in sts.trigger_names() and "OwnerHpAtMostHalf" in sts.condition_names()


def test_replacement_rows():
    """Replacement hooks (docs/specs/replacement-hooks.md): Artifact's row on a
    Sentry, Wraith Form's granted rows, Thorns' `OwnerAttacked` row."""
    f = sts.Features(extra_rows=True)
    n = f.row_names
    b = f.encode([sts.Combat(STARTER, "three_sentries", seed=1)])
    assert {"trigger_Replace(DebuffApplied)": 1, "condition_Always": 1, "grant_own": 1, "reduce_self": 1,
            "replace_cancel": 1, "replace_stacks": 1} in rows_of(b, n, entity=1)
    c = sts.Combat(["Wraith Form"] * 5 + ["Caltrops+"] * 5, "jaw_worm", seed=1, character="silent")
    b = f.encode([c])
    wf = rows_of(b, n, card=card_entry(b, "Wraith Form", f))
    assert wf[1:] == [
        {"trigger_OwnerTurnEnd": 1, "condition_Always": 1, "grant_me": 1, "apply_me_Dexterity": -1},
        {"trigger_RoundEnd": 1, "condition_Always": 1, "grant_me": 1, "reduce_self": 1},
        {"trigger_Replace(DamageTaken)": 1, "condition_Always": 1, "grant_me": 1, "replace_cap": 1, "replace_stacks": 2},
        {"trigger_Replace(HpLoss)": 1, "condition_Always": 1, "grant_me": 1, "replace_cap": 1, "replace_stacks": 2}]
    ct = rows_of(b, n, card=card_entry(b, "Caltrops+", f))
    assert ct[1:] == [{"trigger_OwnerAttacked": 1, "condition_Always": 1, "grant_me": 1, "damage_plain": 5}]
    assert "Intangible" not in sts.hook_power_names() and "Replace(HpLoss)" in sts.trigger_names()
    assert not sts.Features().extra_rows and sts.Features(row_kinds=list(sts.ROW_KINDS)).extra_rows


def test_decision_actions():
    """Decision points (docs/specs/decision-points.md): a Survivor pick as
    actions, their text, the pending-pick columns, and whole games."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    import action_text
    c = sts.Combat(["Survivor"] + ["Silent Strike"] * 9, "jaw_worm", seed=1, character="silent")
    c.step(sts.Action("Survivor"))
    acts = c.legal_actions()
    assert [a.kind for a in acts] == ["choose"] and acts[0].card == "Silent Strike"
    assert action_text.encode_action(acts[0]) == "Choose:Silent Strike"
    assert action_text.decode_action("Choose:Silent Strike") == acts[0] == sts.Action.choose("Silent Strike")
    assert action_text.decode_action("Done") == sts.Action.done() and sts.Action.done().kind == "done"
    f = sts.Features()
    row = dict(zip(f.player_names, f.encode([c])["player"][0]))
    assert (row["awaiting_action"], row["pick_discard_from_hand"], row["pick_left"]) == (1, 1, 1)
    c.step(acts[0])
    assert c.legal_actions()[-1].is_end_turn
    deck = sts.starter_deck("silent")
    specs = [(enc, deck + ["Survivor", "Burst", "Survivor+"], s) for enc, s in (("jaw_worm", 1), ("cultist", 2))]
    for agent in ("search", "greedy", "random"):
        res = sts.run(agent, specs, character="silent")
        assert all(r["turns"] > 0 for r in res), agent
    game = sts.starter_deck("silent", variant="game")
    assert game.count("Survivor") == 1 and sorted(sts.starter_deck("silent", "default")) == sorted(deck)


def test_known_top_piles():
    """Known top (docs/specs/known-top.md): Headbutt's card goes to the
    `next_draw` pile and the scalars count it; a net listing only the old
    piles reads it in `draw`."""
    c = sts.Combat(["Headbutt"] * 10, "jaw_worm", seed=1)
    c.step(sts.Action("Headbutt", 0))  # nothing in the discard pile: no pick
    c.step(sts.Action("Headbutt", 0))
    acts = c.legal_actions()
    assert [a.kind for a in acts] == ["choose"] and acts[0].card == "Headbutt"
    c.step(acts[0])
    f = sts.Features()
    b = f.encode([c])
    nd = sts.PILES.index("next_draw")
    assert [float(x) for x in b["card_count"][b["card_pile"] == nd]] == [1.0]
    row = dict(zip(f.player_names, b["player"][0]))
    assert (row["known_top"], row["next_draw_size"], row["next_draw_max"]) == (1, 5, 5)
    old = sts.Features(piles=["hand", "draw", "discard", "exhaust", "playing"])
    ob = old.encode([c])
    assert set(ob["card_pile"].tolist()) <= {0, 1, 2, 3, 4}
    assert ob["card_count"][ob["card_pile"] == 1].sum() == b["card_count"][(b["card_pile"] == 1) | (b["card_pile"] == nd)].sum()


def test_next_draw_size_counts_retained_cards():
    """A2 (docs/specs/series-review-fixes/A-training.md): 10 Protect, all
    retained, fill the next hand: the next turn draws none."""
    c = sts.Combat(["Protect"] * 10, "jaw_worm", seed=1)
    c.step(next(a for a in c.legal_actions() if a.is_end_turn))
    while c.turn() < 2 and not c.is_over():
        c.step(next(a for a in c.legal_actions() if a.is_end_turn))
    assert c.next_draw() == (0, 0)
    f = sts.Features()
    row = dict(zip(f.player_names, f.encode([c])["player"][0]))
    assert (row["next_draw_size"], row["next_draw_max"]) == (0, 0)


def test_draw_positions():
    """Draw-knowledge item 3: each known card is an entry at its place
    (1 = drawn next), a floater an entry with the cards certainly above it;
    a layout without the position columns gets the merged entries."""
    v = sts.Combat(STARTER, "jaw_worm", seed=1).view()
    v["player"]["energy"] = 9
    v.update(hand={"Headbutt": 2, "Wild Strike": 1}, draw={"Defend": 5}, discard={"Bash": 1, "Strike": 1})
    c = sts.Combat.from_view(v, seed=1)
    for pick in ("Bash", "Strike"):
        c.step(next(a for a in c.legal_actions() if a.card == "Headbutt"))
        c.step(next(a for a in c.legal_actions() if a.kind == "choose" and a.card == pick))
    c.step(next(a for a in c.legal_actions() if a.card == "Wild Strike"))
    f = sts.Features("ids")
    b = f.encode([c])
    pos, above = f.card_names.index("draw_position"), f.card_names.index("draw_above")
    ids = [n[3:] for n in f.card_names]
    entries = [(ids[int(r[:pos].argmax())], int(r[pos]), int(r[above]), int(n), sts.PILES[p] if p < len(sts.PILES) else p)
               for r, n, p in zip(b["cards"], b["card_count"], b["card_pile"])]
    assert ("Strike", 1, 0, 1, "next_draw") in entries and ("Bash", 2, 0, 1, "next_draw") in entries, entries
    assert ("Wound", 0, 1, 1, "draw") in entries, entries
    assert ("Defend", 0, 0, 5, "draw") in entries, entries
    names = [n for n in f.card_names if n not in ("draw_position", "draw_above")]
    old = sts.Features("ids", columns={"player": f.player_names, "monsters": f.monster_names, "cards": names, "rows": f.row_names})
    ob = old.encode([c])
    draw = sts.PILES.index("draw")
    assert ob["card_count"][ob["card_pile"] == draw].sum() == 6, "the Wound merged into the draw pile's entries"
    assert len(ob["card_count"][ob["card_pile"] == draw]) == 2


def test_pattern_rows():
    """Monster patterns (docs/specs/monster-patterns.md): a Jaw Worm showing
    Chomp has one `Pattern(Next)` row per possible next move (Chomp can't
    repeat: Bellow or Thrash), their
    probabilities summing to 1; a Cultist's next move is certain."""
    f = sts.Features(extra_rows=True)
    n = f.row_names
    b = f.encode([sts.Combat(STARTER, "jaw_worm", seed=1)])
    rows = [r for r in rows_of(b, n, entity=1, patterns=True) if "trigger_Pattern(Next)" in r]
    assert len(rows) == 2 and abs(sum(r["condition_param"] for r in rows) - 1) < 1e-6  # Bellow or Thrash
    b = f.encode([sts.Combat(STARTER, "cultist", seed=1)])
    rows = [r for r in rows_of(b, n, entity=1, patterns=True) if "trigger_Pattern(Next)" in r]
    assert rows == [{"trigger_Pattern(Next)": 1, "condition_Always": 1, "condition_param": 1, "grant_own": 1,
                     "damage_single": 6, "hits_single": 1}]


def test_variant_cards():
    """Per-copy overrides (docs/specs/per-copy-overrides.md): a grown
    Rampage is a variant named by its overrides; its action text replays
    through `decode_in`; its card vector reads its own damage."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    import action_text
    c = sts.Combat(["Rampage"] * 10, "jaw_worm", seed=1)
    c.step(sts.Action("Rampage", 0))
    c.step(sts.Action("Rampage", 0))
    assert c.piles()["discard"] == {"Rampage{damage=13/combat}": 2}
    c.step(next(a for a in c.legal_actions() if a.is_end_turn))
    while not any(a.card == "Rampage{damage=13/combat}" for a in c.legal_actions()):
        c.step(next(a for a in c.legal_actions() if a.is_end_turn))
    a = next(a for a in c.legal_actions() if a.card == "Rampage{damage=13/combat}")
    text = action_text.encode_action(a)
    assert text == "Rampage{damage=13/combat}@0"
    assert action_text.decode_in(c, text) == a
    f = sts.Features()
    b = f.encode([c])
    dmg = sorted(float(r[f.card_names.index("damage_single")]) for r in b["cards"][b["card_pile"] == 0])
    assert 13.0 in dmg
    grow = [float(r[f.card_names.index("grow_damage")]) for r in b["cards"][b["card_pile"] == 0]]
    assert set(grow) == {5.0}
    assert "retain" in f.card_names


def test_granting_card_rows():
    f = sts.Features()
    n = f.row_names
    c = sts.Combat(["Demon Form"] * 5 + ["Spot Weakness"] * 5, "jaw_worm", seed=1)
    b = f.encode([c])
    df = rows_of(b, n, card=card_entry(b, "Demon Form", f))
    # The card's own (empty) play row, then Demon Form's hook granted to its user.
    assert df[0] == {"trigger_CardPlayed(Owner)": 1, "condition_Always": 1, "grant_own": 1}
    assert df[1] == {"trigger_OwnerTurnStart": 1, "condition_Always": 1, "grant_me": 1, "apply_me_Strength": 2}
    # Once played, the player's own power has the same row, marked own.
    c.step(sts.Action("Demon Form"))
    own = rows_of(f.encode([c]), n, entity=0)
    assert own == [{"trigger_OwnerTurnStart": 1, "condition_Always": 1, "grant_own": 1, "apply_me_Strength": 2}]
    # Spot Weakness: one conditional row, its effect the Strength gain
    # (Strength's static row is an opt-in kind, off by default).
    sw = rows_of(b, n, card=card_entry(b, "Spot Weakness", f))
    assert sw == [{"trigger_CardPlayed(Owner)": 1, "condition_TargetIntendsAttack": 1, "grant_own": 1,
                   "apply_me_Strength": 3}]
    # With the opt-in kinds, Strength's static row follows, granted to its user.
    fx = sts.Features(extra_rows=True)
    bx = fx.encode([sts.Combat(["Demon Form"] * 5 + ["Spot Weakness"] * 5, "jaw_worm", seed=1)])
    assert rows_of(bx, fx.row_names, card=card_entry(bx, "Spot Weakness", fx)) == sw + [
        {"trigger_Static(DamageDealt)": 1, "condition_Always": 1, "grant_me": 1, "static_add": 3}]
    # Deadly Poison grants Poison's hook to the opponent; FTL's condition carries its number.
    c = sts.Combat(["Deadly Poison"] * 5 + ["FTL+"] * 5, "jaw_worm", seed=1)
    b = f.encode([c])
    dp = rows_of(b, n, card=card_entry(b, "Deadly Poison", f))
    assert dp[1] == {"trigger_OwnerTurnStart": 1, "condition_Always": 1, "grant_opponent": 1, "lose_hp": 5,
                     "reduce_self": 1}
    ftl = rows_of(b, n, card=card_entry(b, "FTL+", f))
    assert ftl[1] == {"trigger_CardPlayed(Owner)": 1, "condition_CardsPlayedThisTurnBelow": 1,
                      "condition_param": 4, "grant_own": 1, "draw": 1}
    # The Cultist's Incantation intent grants Ritual to itself.
    b = f.encode([sts.Combat(STARTER, "cultist", seed=1)])
    assert rows_of(b, n, entity=1) == [
        {"trigger_OwnerTurnEnd": 1, "condition_Always": 1, "grant_me": 1, "apply_me_Strength": 3}]
    # Every card row points at a card entry of its own state.
    b = f.encode([c, sts.Combat(STARTER + ["Combust"], "cultist", seed=2)])
    cr = b["row_card"] >= 0
    assert (b["card_state"][b["row_card"][cr]] == b["row_state"][cr]).all()
    assert ((b["row_card"] >= 0) != (b["row_entity"] >= 0)).all()


def test_unknown_vocab():
    full = sts.Features()
    assert full.vocab["triggers"] == sts.trigger_names() and full.vocab["effects"] == sts.effect_names()
    assert full.vocab["conditions"] == sts.condition_names()
    # A vocabulary without OwnerTurnStart: Demon Form's row lands in trigger_unknown.
    trig = [t for t in sts.trigger_names() if t != "OwnerTurnStart"]
    cond = [x for x in sts.condition_names() if x != "TargetIntendsAttack"]
    eff = [e for e in sts.effect_names() if e != "remove_self"]
    f = sts.Features(known_triggers=trig, known_conditions=cond, known_effects=eff)
    assert f.vocab["triggers"] == trig and f.dims["row"] == full.dims["row"] - 3
    n = f.row_names
    assert "trigger_OwnerTurnStart" not in n and "remove_self" not in n
    c = sts.Combat(["Demon Form"] * 5 + ["Spot Weakness"] * 5, "jaw_worm", seed=1)
    b = f.encode([c])
    assert rows_of(b, n, card=card_entry(b, "Demon Form", f))[1]["trigger_unknown"] == 1
    assert rows_of(b, n, card=card_entry(b, "Spot Weakness", f))[0]["condition_unknown"] == 1
    # The vocabulary order is the dimension order.
    rev = sts.Features(known_triggers=list(reversed(sts.trigger_names())))
    assert rev.row_names[0] == "trigger_" + sts.trigger_names()[-1]
    for kw in ("known_triggers", "known_conditions", "known_effects"):
        try:
            sts.Features(**{kw: ["Telekinesis"]})
            raise AssertionError(f"unknown name accepted in {kw}")
        except ValueError:
            pass


def test_ids_power_ids():
    held = ["Metallicize", "DemonForm", "Rage"]
    known = [p for p in sts.power_names() if p not in held]
    ids = sts.Features("ids", known_powers=known)
    assert "power_DemonForm" not in ids.player_names and "power_Combust" in ids.player_names
    assert [n for n in sts.Features("ids").player_names if n.startswith("power_")][:-1] == ["power_" + p for p in sts.power_names()]
    c = sts.Combat(["Demon Form"] * 10, "lagavulin", seed=1)
    c.step(sts.Action("Demon Form"))
    b = ids.encode([c])
    p = b["player"][0]
    assert p[ids.player_names.index("power_unknown")] == 2
    # Lagavulin's Metallicize is held out too: unknown on the monster.
    assert b["monsters"][0, 0, ids.monster_names.index("power_unknown")] == 8
    # Ids mode has no rows.
    assert b["rows"].shape == (0, ids.dims["row"]) and len(b["row_card"]) == 0
    # Known hook powers get their own id dimension.
    c = sts.Combat(STARTER, "cultist", seed=1)
    c.step(sts.Action())
    m = ids.encode([c])["monsters"][0, 0]
    assert m[ids.monster_names.index("power_Ritual")] == 3


# Today's pools, pinned (spec card-sets): engine/tests/card_sets.rs holds
# the same lists.
POOL_IRONCLAD = [
    "Strike", "Strike+", "Defend", "Defend+", "Bash", "Bash+", "Shrug It Off", "Shrug It Off+",
    "Anger", "Anger+", "Body Slam", "Body Slam+", "Clash", "Clash+", "Cleave", "Cleave+",
    "Clothesline", "Clothesline+", "Iron Wave", "Iron Wave+", "Pommel Strike", "Pommel Strike+",
    "Thunderclap", "Thunderclap+", "Twin Strike", "Twin Strike+", "Wild Strike", "Wild Strike+",
    "Heavy Blade", "Heavy Blade+", "Perfected Strike", "Perfected Strike+", "Sword Boomerang",
    "Sword Boomerang+", "Bloodletting", "Bloodletting+", "Hemokinesis", "Hemokinesis+", "Pummel",
    "Pummel+", "Uppercut", "Uppercut+", "Inflame", "Inflame+", "Flex", "Flex+", "Carnage",
    "Carnage+", "Spot Weakness", "Spot Weakness+", "Dropkick", "Dropkick+", "Combust", "Combust+",
    "Brutality", "Brutality+", "Rupture", "Rupture+",
]
POOL_SILENT = [
    "Silent Strike", "Silent Strike+", "Silent Defend", "Silent Defend+", "Neutralize",
    "Neutralize+", "Sucker Punch", "Sucker Punch+", "Leg Sweep", "Leg Sweep+", "Quick Slash",
    "Quick Slash+", "Backflip", "Backflip+", "Deflect", "Deflect+", "Slice", "Slice+",
    "Dagger Spray", "Dagger Spray+", "Blade Dance", "Blade Dance+", "Cloak and Dagger",
    "Cloak and Dagger+", "Deadly Poison", "Deadly Poison+", "Poisoned Stab", "Poisoned Stab+",
    "Bouncing Flask", "Bouncing Flask+",
]
POOL_CHECK9 = [
    "Go for the Eyes", "Go for the Eyes+", "FTL", "FTL+", "Metallicize", "Metallicize+",
    "Demon Form", "Demon Form+", "Rage", "Rage+",
]


def test_card_pools_pinned():
    assert sts.deck_card_names() == POOL_IRONCLAD
    assert sts.class_card_names("ironclad") == POOL_IRONCLAD
    assert sts.class_card_names("silent") == POOL_SILENT
    assert sts.held_out_card_names() == POOL_CHECK9


def test_card_sets():
    assert sts.card_set_names() == ["ironclad", "silent", "check9", "proving"]
    assert sts.card_set("check9") == sts.held_out_card_names()
    assert sts.card_set("ironclad") == POOL_IRONCLAD and sts.card_set("silent") == POOL_SILENT
    try:
        sts.card_set("x")
    except KeyError as e:
        assert all(n in str(e) for n in sts.card_set_names()), e
    else:
        raise AssertionError("unknown set accepted")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
