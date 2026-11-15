"""Tests for the survival score (docs/specs/survival-score.md): switch 6's
HP-lost labels in normal self-play (deaths are real, the end-of-combat heal
counted once), the `no_death` config key and the `survive` score rule. Run
with `python scripts/tests/test_survival_score.py` or pytest."""

import os
import sys
import tempfile

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import learn  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import stsnet  # noqa: E402
import train  # noqa: E402

NORMAL = {"name": "tiny-normal", "sample_seed": 5, "search": {"limit": selfplay.LIMIT}}
NO_DEATH = dict(NORMAL, name="tiny-nd", no_death=True)
HEAL = sts.Combat(sts.starter_deck("ironclad"), "cultist").win_heal


def stored_games(config, specs):
    """Plays `specs` into a temporary registry; the replayed games."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        ds, _ = registry.selfplay(specs, [0] * len(specs), config, root=root)
        return [registry.replay(g) for g in registry.load_games(ds, root)]


def labelled(game):
    """`sample_states` on one replayed game with switch 6's labels:
    (states, targets, outcomes)."""
    extra = {}
    states, target, _ = selfplay.sample_states([game], [0], np.random.default_rng(0), {"hp_loss": True}, extra)
    return states, np.array(target), np.array(extra["outcome"])


def test_normal_mode_labels():
    """In normal play `hp_end` already holds Burning Blood's heal: a won
    game's label is the HP lost before it, hp - (hp_end - heal), floored at
    0, so the formula (which adds the heal back, capped at max HP) lands on
    the real end HP. A death is a non-win (the turn-limit bin)."""
    deck = sts.starter_deck("ironclad")
    won = [r for r in stored_games(NORMAL, [("jaw_worm", deck, s) for s in range(6)]) if r["won"]]
    assert won and "no_death" not in won[0]
    checked = 0
    for r in won:
        states, target, outcome = labelled(r)
        for s, tg, out in zip(states, target, outcome):
            lost = s.player_hp() - (r["hp_end"] - HEAL)
            want = min(max(lost, 0), selfplay.HP_CAP)
            assert out == want, (out, want)
            assert tg.argmax() == stsnet.bin_index(want) and tg.sum() == 1
            if lost >= 0:  # the formula's end HP is the real (healed, capped) end HP
                assert min(s.player_hp() - want + HEAL, 80) == r["hp_end"]
                checked += 1
    assert checked
    # Capped heal: a game ending at max HP still lands on max HP.
    assert min(78 - selfplay.hp_label(78, {"won": True, "hp_end": 80}, HEAL) + HEAL, 80) == 80
    # A death in normal play: the turn-limit bin, outcome the cap.
    dead = [r for r in stored_games(NORMAL, [("gremlin_nob", deck, s, 3) for s in range(3)]) if not r["won"]]
    assert dead
    _, target, outcome = labelled(dead[0])
    assert (target.argmax(1) == stsnet.TURN_LIMIT_BIN).all() and (outcome == selfplay.HP_CAP).all()


def test_no_death_labels_unchanged():
    """No-death games (no heal in that mode) keep today's labels: the HP
    lost is hp - hp_end, and the replay says the game was no-death."""
    specs, _ = selfplay.make_specs(1, 41, selfplay.train_deck)
    games = stored_games(NO_DEATH, specs)
    assert all(g["no_death"] for g in games)
    for r in (g for g in games if g["won"]):
        states, _, outcome = labelled(r)
        for s, out in zip(states, outcome):
            assert out == min(s.player_hp() - r["hp_end"], selfplay.HP_CAP)
    # The label functions' defaults are today's no-death formulas.
    assert selfplay.hp_label(30, {"won": True, "hp_end": 10}) == 20
    assert selfplay.hp_target(30, {"won": True, "hp_end": 10}).argmax() == stsnet.bin_index(20)


def test_real_score_normal_mode():
    """A finished normal-mode combat is already healed by the engine: its
    real score is the engine's; no-death keeps adding the heal."""
    deck = sts.starter_deck("ironclad")
    seed, res = next((s, r) for s in range(50)
                     for r in sts.run("search", [("jaw_worm", deck, s)], record=True, limit=selfplay.LIMIT)
                     if r["won"] and r["hp_end"] < 80)
    c = sts.Combat(deck, "jaw_worm", seed=seed)
    for a in res["actions"]:
        c.step(a)
    assert c.won() and c.player_hp() == res["hp_end"]
    assert selfplay.real_score(c, 80, HEAL, no_death=False) == c.score()
    assert selfplay.real_score(c, 80, HEAL) == 2 - max(80 - (c.player_hp() + HEAL), 0) / 100


def test_config_checks():
    """`no_death` (top level, with switch 6): absent or true forces no-death
    self-play as before; false keeps normal self-play."""
    seen = []
    find = registry.find
    registry.find = lambda gen, **kw: seen.append(gen) or "ds"
    try:
        base = {"name": "x", "n_train": 2, "n_val": 1, "train_seed": 1, "val_seed": 2,
                "switches": {"hp_loss": True}}
        for cfg, want in ((base, True), (dict(base, no_death=True), True), (dict(base, no_death=False), False),
                          ({k: v for k, v in base.items() if k != "switches"}, False)):
            seen.clear()
            assert learn.dataset(cfg, "train", log=lambda *_: None) == "ds"
            assert bool(seen[0].get("no_death")) == want, (cfg, seen[0])
            assert learn.no_death(cfg) == want
    finally:
        registry.find = find


SURVIVE = {"kind": "survive", "c": 1.0, "w": 2.0}


def one_hot(*bins):
    """[len(bins), N_BINS] histograms, all mass on each given bin."""
    p = torch.zeros(len(bins), stsnet.N_BINS)
    p[torch.arange(len(bins)), torch.tensor(bins)] = 1.0
    return p


def scalars(*rows):
    """(hp, start_hp, max_hp, heal) tensors from (hp, start, max, heal) rows."""
    return tuple(torch.tensor(c, dtype=torch.float32) for c in zip(*rows))


def old_external_score(p, hp, start_hp, max_hp, heal, tau=None):
    """Today's (engine rule) formula, written out: the reference the
    default must keep to the bit."""
    win = stsnet._win(hp, tau)
    hp, start_hp, max_hp, heal = (x.unsqueeze(1) for x in (hp, start_hp, max_hp, heal))
    end = torch.minimum(hp - torch.from_numpy(stsnet.BIN_REP) + heal, max_hp)
    return (p * win * (2 - torch.relu(start_hp - end) / 100)).sum(1)


def tiny_hp_net(rule=None):
    torch.manual_seed(3)
    model = stsnet.ValueNet(selfplay.features("effects").dims, hp_loss=True)
    if rule is not None:
        model.score_rule = rule
    return model.eval()


def test_engine_rule_default():
    """An HP-loss net without a `score` rule scores exactly as today, and
    `rule=None` / the engine rule give today's formula bit for bit."""
    torch.manual_seed(0)
    p = torch.softmax(torch.randn(6, stsnet.N_BINS), 1)
    hp, start, mx, heal = scalars((50, 70, 80, 6), (5, 80, 80, 6), (78, 78, 80, 6), (30, 40, 80, 0),
                                  (1, 60, 80, 6), (80, 80, 80, 6))
    want = old_external_score(p, hp, start, mx, heal)
    for rule in (None, {"kind": "engine"}):
        assert torch.equal(stsnet.external_score(p, hp, start, mx, heal, rule=rule), want)
    assert torch.equal(stsnet.external_score(p, hp, start, mx, heal, 2.0), old_external_score(p, hp, start, mx, heal, 2.0))
    assert stsnet.score_rule(None) is None and stsnet.score_rule({"kind": "engine"}) is None
    assert getattr(tiny_hp_net(), "score_rule", None) is None


def test_survive_formula():
    """Survive: a winnable bin scores c + w x min(hp - rep + heal, max) / 100,
    a non-win bin 0. Spec cases: hp 50, rep 10, heal 6, max 80 -> 1.92;
    hp 78, rep 0 -> capped at 80 -> 2.6; turn-limit mass, or a bin whose HP
    lost reaches the current HP -> 0. Start HP plays no part."""
    p = one_hot(10, 0, stsnet.TURN_LIMIT_BIN, 10, 10)
    hp, start, mx, heal = scalars((50, 70, 80, 6), (78, 78, 80, 6), (50, 70, 80, 6), (10, 70, 80, 6),
                                  (50, 20, 80, 6))
    got = stsnet.external_score(p, hp, start, mx, heal, rule=SURVIVE).tolist()
    want = [1 + 2 * 46 / 100, 1 + 2 * 80 / 100, 0.0, 0.0, 1 + 2 * 46 / 100]
    assert np.allclose(got, want, atol=1e-6), got
    # c and w are the rule's.
    half = stsnet.external_score(one_hot(10), *scalars((50, 70, 80, 6)), rule={"kind": "survive", "c": 0.5, "w": 1.0})
    assert abs(half.item() - (0.5 + 46 / 100)) < 1e-6
    # Defaults c 1.0, w 2.0; unknown kinds refused.
    assert stsnet.score_rule({"kind": "survive"}) == SURVIVE
    for bad in ({"kind": "nope"}, {"kind": "survive", "c": 1.0, "w": 2.0, "x": 1}):
        try:
            stsnet.score_rule(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} should be refused")
    # score_of uses the net's rule.
    model = tiny_hp_net(SURVIVE)
    t = {"hp": torch.tensor([50.0]), "start_hp": torch.tensor([70.0]), "max_hp": torch.tensor([80.0]),
         "win_heal": torch.tensor([6.0])}
    model.forward = lambda _t: torch.log(one_hot(10))
    assert abs(stsnet.score_of(model, t).item() - 1.92) < 1e-6


def test_real_score_survive():
    """A finished normal-mode combat under survive: c + w x its (already
    healed) HP / 100 when won, else 0; survive with no-death is refused."""
    deck = sts.starter_deck("ironclad")
    seed, res = next((s, r) for s in range(50)
                     for r in sts.run("search", [("jaw_worm", deck, s)], record=True, limit=selfplay.LIMIT)
                     if r["won"])
    c = sts.Combat(deck, "jaw_worm", seed=seed)
    for a in res["actions"]:
        c.step(a)
    assert abs(selfplay.real_score(c, 80, HEAL, no_death=False, rule=SURVIVE) - (1 + 2 * c.player_hp() / 100)) < 1e-9
    try:
        selfplay.real_score(c, 80, HEAL, no_death=True, rule=SURVIVE)
    except ValueError:
        pass
    else:
        raise AssertionError("survive with no-death should be refused")


def test_score_config_checks():
    """`score` survive needs switch 6 in normal self-play and isn't
    combined with hp_weight; labels carry the rule only when it's survive
    (the engine rule keeps today's label dicts, so today's caches)."""
    base = {"name": "x", "switches": {"hp_loss": True}, "no_death": False, "score": dict(SURVIVE)}
    learn.check_score(base)
    learn.check_score({"name": "x"})
    learn.check_score({"name": "x", "score": {"kind": "engine"}})
    for bad in ({k: v for k, v in base.items() if k != "switches"},
                dict(base, hp_weight=2.0),
                {k: v for k, v in base.items() if k != "no_death"}):
        try:
            learn.check_score(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} should be refused")
    assert learn.score_rule(base) == SURVIVE and learn.score_rule({"name": "x"}) is None
    assert learn.labels(base, 1) == {"afterstates": True, "hp_loss": True, "score_rule": SURVIVE}
    plain = {k: v for k, v in base.items() if k != "score"}
    assert learn.labels(plain, 1) == {"afterstates": True, "hp_loss": True}


def test_ranking_uses_rule():
    """The ranking term's scores for a survive net are the survive formula
    with the win step smoothed (RANK_TAU); an engine net's are today's."""
    torch.manual_seed(1)
    pred = torch.log_softmax(torch.randn(4, stsnet.N_BINS), 1)
    hp, start, mx, heal = scalars((50, 70, 80, 6), (5, 80, 80, 6), (78, 78, 80, 6), (30, 40, 80, 0))
    x = {"hp": hp, "start_hp": start, "max_hp": mx, "win_heal": heal}
    got = train.rank_score(pred, x, True, SURVIVE)
    want = stsnet.external_score(pred.exp(), hp, start, mx, heal, train.RANK_TAU, rule=SURVIVE)
    assert torch.equal(got, want)
    assert not torch.allclose(got, old_external_score(pred.exp(), hp, start, mx, heal, train.RANK_TAU))
    assert torch.equal(train.rank_score(pred, x, True, None), old_external_score(pred.exp(), hp, start, mx, heal,
                                                                                  train.RANK_TAU))
    plain = torch.randn(4)
    assert torch.equal(train.rank_score(plain, x, False, None), plain)


def test_rule_saved_and_loaded():
    """The rule rides in the net's meta (`score_rule`): saved, loaded back
    onto the model, kept by `widen`; an engine net's meta has none."""
    model = tiny_hp_net(SURVIVE)
    norm = stsnet.Normalizer.fit(selfplay_dataset())
    meta = {"card_repr": "effects", **selfplay.meta_vocab("effects"), "score_rule": SURVIVE}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        path = os.path.join(d, "m.pt")
        stsnet.save(path, model, norm, meta)
        back, _, m = stsnet.load(path)
        assert back.score_rule == SURVIVE and m["score_rule"] == SURVIVE
        meta.pop("score_rule")
        stsnet.save(path, tiny_hp_net(), norm, meta)
        back, _, m = stsnet.load(path)
        assert getattr(back, "score_rule", None) is None and "score_rule" not in m


def selfplay_dataset():
    """A few encoded states, for fitting a normaliser."""
    deck = sts.starter_deck("ironclad")
    states = [sts.Combat(deck, "jaw_worm", seed=s) for s in range(4)]
    b = selfplay.features("effects").encode(states, heuristic=True)
    return stsnet.Dataset.from_batches([b], np.zeros(len(states)))



# Rust halves (step 3): the NetEvaluator's histogram rule and search's rule.

def recorded_states():
    """Decision states from a few greedy hallway and elite games: a spread of
    HP, start HP and max HP."""
    out = []
    for g in ("hallway", "elite"):
        for r in sts.run("greedy", sts.make_specs(g, 6, seed=3), record=True):
            out += r["states"]
    return out


def fixed_net(p, rule=None, **kw):
    """(Rust evaluator, model, norm, meta) of a saved HP net whose histogram
    is `p` for every state (a bias-only head), with `rule`."""
    feats = selfplay.features("effects")
    model = stsnet.ValueNet(feats.dims, hp_loss=True)
    with torch.no_grad():
        model.head[1].weight.zero_()
        logp = np.where(p > 0, np.log(np.maximum(p, 1e-30)), -1e4)  # exp(-1e4) is exactly 0
        model.head[1].bias.copy_(torch.from_numpy(logp.astype(np.float32)))
    meta = {"card_repr": "effects", **selfplay.meta_vocab("effects")}
    if rule is not None:
        model.score_rule = rule
        meta["score_rule"] = rule
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        path = os.path.join(d, "m.pt")
        stsnet.save(path, model.eval(), stsnet.Normalizer.fit(selfplay_dataset()), meta)
        model, norm, meta = stsnet.load(path)
    return stsnet.rust_evaluator(model, norm, meta, **kw), model, norm, meta


def python_scores(p, states, rule):
    """stsnet.external_score of histogram `p` on each of `states`."""
    b = selfplay.features("effects").encode(states, heuristic=True)
    hp, start, mx, heal = (torch.from_numpy(np.asarray(b[k], np.float32)) for k in stsnet.HP_SCALARS)
    pp = torch.from_numpy(np.tile(np.asarray(p, np.float32), (len(states), 1)))
    return stsnet.external_score(pp, hp, start, mx, heal, rule=rule).numpy()


def spread_histogram():
    """Mass on wins of 0-40 HP lost, a little on the turn-limit bin."""
    p = np.zeros(stsnet.N_BINS)
    for lost, q in ((0, 0.2), (3, 0.2), (8, 0.2), (20, 0.2), (40, 0.1)):
        p[stsnet.bin_index(lost)] += q
    p[stsnet.TURN_LIMIT_BIN] = 0.1
    return p


def test_rust_rules_match_python():
    """Spec tests 1-2, Rust halves: an HP net without a rule scores with the
    engine formula and names no `score_rule` in its config; a survive net
    scores c + w x end HP / 100; Rust equals stsnet.external_score."""
    p, states = spread_histogram(), recorded_states()
    assert len(states) > 50
    engine = fixed_net(p)[0]
    got = engine.score(states)
    assert np.abs(got - python_scores(p, states, None)).max() < 1e-6
    survive = fixed_net(p, SURVIVE)[0]
    got = survive.score(states)
    assert np.abs(got - python_scores(p, states, SURVIVE)).max() < 1e-6
    assert got.max() > 2.0, "survive scores reach past the engine's 2"


def test_rust_engine_config_unchanged():
    """An engine-rule net's NetEvaluator config is today's: no `score_rule`
    key, so every existing net builds the same evaluator."""
    seen = {}
    real = sts.NetEvaluator

    def spy(weights, norm, config):
        seen.update(config)
        return real(weights, norm, config)

    sts.NetEvaluator = spy
    try:
        fixed_net(spread_histogram())
    finally:
        sts.NetEvaluator = real
    assert "score_rule" not in seen and seen["hp_loss"] is True


def test_search_uses_the_nets_rule():
    """Spec test 3 (search side): with a survive net, search's option values
    are on the survive scale (all mass on 0 lost at full HP: past 2), with
    the engine rule they stay within 0..2. Finished combats are scored by
    the same rule (Rust unit test `search_scores_a_kill_with_its_rule`)."""
    p = np.zeros(stsnet.N_BINS)
    p[0] = 1.0
    c = sts.Combat(sts.starter_deck("ironclad"), "cultist", seed=1)
    eng = sts.search(c, fixed_net(p)[0])
    sur = sts.search(c, fixed_net(p, SURVIVE)[0])
    assert all(0.0 <= v <= 2.0 for _, v in eng["options"])
    assert max(v for _, v in sur["options"]) > 2.0
    assert [a for a, _ in eng["options"]] == [a for a, _ in sur["options"]]


def test_rust_rule_checks():
    """Spec test 6, Rust checks: `@hpb` (hp_bonus) with a survive net,
    an ensemble mixing rules, a survive rule on a score net are errors;
    `@sc1.5` replaces c."""
    import bench
    p = spread_histogram()
    try:
        fixed_net(p, SURVIVE, hp_bonus=0.01)
        raise AssertionError("hp_bonus with survive should fail")
    except ValueError:
        pass
    try:
        fixed_net(p, SURVIVE, enemy_strength_price=0.02)
        raise AssertionError("enemy_strength_price with survive should fail")
    except ValueError:
        pass
    try:
        fixed_net(p, SURVIVE, hp_end_bonus=0.01)
        raise AssertionError("hp_end_bonus with survive should fail")
    except ValueError as e:
        assert "hp_end_bonus" in str(e), e
    eng, sur = fixed_net(p)[0], fixed_net(p, SURVIVE)[0]
    c = sts.Combat(sts.starter_deck("ironclad"), "jaw_worm", seed=2)
    try:
        sts.search(c, [eng, sur])
        raise AssertionError("a mixed-rule ensemble should fail")
    except ValueError:
        pass
    sts.search(c, [sur, sur])  # one rule: fine
    model = stsnet.ValueNet(selfplay.features("effects").dims)
    norm = stsnet.Normalizer.fit(selfplay_dataset())
    try:
        stsnet.rust_evaluator(model.eval(), norm, {"card_repr": "effects", **selfplay.meta_vocab("effects")},
                              survive_c=1.5)
        raise AssertionError("@sc on a net without a survive rule should fail")
    except ValueError:
        pass
    # @sc1.5 through bench: c replaced, w kept.
    states = recorded_states()[:40]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        _, model, norm, meta = fixed_net(p, SURVIVE)
        path = os.path.join(d, "s.pt")
        stsnet.save(path, model, norm, meta)
        ev = bench.load_evaluator(path + "@sc1.5")
        got = ev.evaluator.score(states)
        _, model, norm, meta = fixed_net(p)  # an engine-score HP net takes both search prices
        path = os.path.join(d, "e.pt")
        stsnet.save(path, model, norm, meta)
        assert bench.load_evaluator(path + "@hpb0.01@esp0.02").evaluator.score(states).shape == (len(states),)
    want = python_scores(p, states, dict(SURVIVE, c=1.5))
    assert np.abs(got - want).max() < 1e-6


CONFIGS = os.path.join(os.path.dirname(__file__), "..", "..", "configs")


def load_config(name):
    import json
    with open(os.path.join(CONFIGS, name + ".json")) as f:
        return json.load(f)


def test_lean_surv_configs():
    """The arms' configs are their lean-thr twins plus exactly switch 6,
    `no_death: false` and the survive rule (and the name); learn's checks
    accept them, and their round-0 games are the twins' (same dataset key)."""
    for s in ("s1", "s101"):
        surv, thr = load_config(f"lean-surv-{s}"), load_config(f"lean-thr-{s}")
        want = dict(thr, name=f"lean-surv-{s}", no_death=False, score=SURVIVE,
                    switches=dict(thr["switches"], hp_loss=True))
        assert surv == want, s
        learn.check_hp_weight(surv)
        learn.check_score(surv)
        assert learn.score_rule(surv) == SURVIVE
        seen = []
        find = registry.find
        registry.find = lambda gen, **kw: seen.append(gen) or "ds"
        try:
            for cfg in (surv, thr):
                for which in ("train", "val"):
                    learn.dataset(cfg, which, log=lambda *_: None)
        finally:
            registry.find = find
        assert seen[:2] == seen[2:], "round-0 games should be shared with the twin"


def test_learn_smoke_survive():
    """End to end: a tiny run with the arms' keys trains histogram nets on
    normal self-play, saves the survive rule, loads into Rust with it, and
    plays (round 1's games and the tight-fight check)."""
    cfg = {"name": "smoke-surv", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 51, "val_seed": 52,
           "search": {"limit": selfplay.LIMIT}, "seed": 0, "rounds": {"n": 1, "every": 100},
           "switches": {"hp_loss": True, "branches": True}, "no_death": False, "score": SURVIVE}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        run = learn.learn(cfg, root=root, log=lambda *_: None)[-1]
        model, norm, meta = stsnet.load(run.model_path)
        man = registry.load_manifest(meta["datasets"]["train"][0], root)
        rnd = run._read("round.json")
    assert model.hp_loss and meta["score_rule"] == SURVIVE and model.score_rule == SURVIVE
    assert "no_death" not in man["config"] and man["config"]["round"] == 1
    assert rnd["label_scale"]["tolerance"] == 10.0
    ev = stsnet.rust_evaluator(model, norm, meta)
    feats = stsnet.features_for(meta)
    states = sts.run("search", [("cultist", sts.starter_deck("ironclad"), 4)], record=True)[0]["states"]
    py = stsnet.Evaluator(model, norm)(feats.encode(states, heuristic=True))
    rs = np.asarray(ev.score(states))
    assert np.abs(py - rs).max() < 1e-5
    assert (rs >= 0).all() and (rs <= SURVIVE["c"] + SURVIVE["w"] * 80 / 100 + 1e-6).all()
    r = sts.search(states[0], ev, features=feats, limit=selfplay.LIMIT)
    assert r["action"] is not None
    games = sts.run("search", [("jaw_worm", sts.starter_deck("ironclad"), 7)], evaluator=ev, features=feats)
    assert len(games) == 1 and "won" in games[0]


def test_python_evaluator_carries_the_rule():
    """A survive net as a Python callable (`stsnet.Evaluator`) tells search
    its rule, so a kill on a won game's last decision scores on the survive
    scale, as with the Rust NetEvaluator (review finding); an engine-rule
    callable has no rule attribute."""
    p = np.zeros(stsnet.N_BINS)
    p[0] = 1.0
    ev, model, norm, meta = fixed_net(p, SURVIVE)
    feats = stsnet.features_for(meta)
    g = sts.run("search", [("cultist", sts.starter_deck("ironclad"), 0)], record=True)[0]
    assert g["won"]
    s = g["states"][-1]
    rust = sts.search(s, ev, features=feats)
    py = sts.search(s, stsnet.Evaluator(model, norm), features=feats)
    rv, pv = [v for _, v in rust["options"]], [v for _, v in py["options"]]
    assert max(rv) > 2.0
    assert np.allclose(rv, pv, atol=1e-5), (rv, pv)
    assert py["action"] == rust["action"]
    assert not hasattr(stsnet.Evaluator(fixed_net(p)[1], norm), "score_rule")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print("ok ", name)
