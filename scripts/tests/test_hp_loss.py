"""Tests for learned-play switch 6 (no-death HP-loss target): the no-death
simulation, HP-lost labels, the histogram head (Amendment 1) and the
external formula. Run with `python scripts/tests/test_hp_loss.py` or pytest."""

import os
import sys
import tempfile

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import registry  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import stsnet  # noqa: E402

TURN_LIMIT = 50
CONFIG = {"name": "tiny-nd", "sample_seed": 5, "search": {"limit": selfplay.LIMIT}, "no_death": True}


def t(*xs):
    return [torch.tensor(x, dtype=torch.float32) for x in xs]


def onehot(lost, won=True):
    return torch.from_numpy(selfplay.hp_target(0, {"won": won, "hp_end": -lost}))[None]


def test_no_death_combat_goes_negative_and_ends_at_the_turn_limit():
    """A player who only ends turns keeps playing below 0 HP; the combat ends
    as a loss after the turn limit. Normal play ends at 0 HP."""
    deck = sts.starter_deck("ironclad")
    c = sts.Combat(deck, "jaw_worm", seed=3, hp=5, no_death=True)
    lowest = 5
    while not c.is_over():
        c.step(sts.Action())
        lowest = min(lowest, c.player_hp())
    assert lowest < 0 and not c.won() and c.turn() == TURN_LIMIT and c.score() == 0.0
    n = sts.Combat(deck, "jaw_worm", seed=3, hp=5)
    while not n.is_over():
        n.step(sts.Action())
    assert n.player_hp() == 0 and not n.won() and n.turn() < TURN_LIMIT
    # sts.run: a no-death win keeps the HP left, which may be negative.
    r = sts.run("search", [("jaw_worm", deck, s) for s in range(20)], hp=3, no_death=True)
    assert all(x["won"] or x["turns"] == TURN_LIMIT for x in r)
    assert any(x["won"] and x["hp_end"] < 0 for x in r)


def test_win_heal_matches_the_engine():
    for ch in ("ironclad", "silent"):
        c = sts.Combat(sts.starter_deck(ch), "cultist", seed=1, character=ch)
        b = sts.Features("effects").encode([c], heuristic=True)
        assert b["win_heal"][0] == c.win_heal == {"ironclad": 6, "silent": 0}[ch]
        assert c.character == ch
    # A relic's win_heal (Black Blood's 6) adds to the state's, which labels read.
    sts.load_content('{"version": 1, "relics": [{"id": "py_win_heal_12", "rarity": "rare", "win_heal": 12}]}')
    c = sts.Combat(sts.starter_deck("ironclad"), "cultist", seed=1, relics=["gen:py_win_heal_12"])
    assert c.win_heal == 6 + 12
    assert selfplay.label_heal(c, {}) == c.win_heal == sts.Features("effects").encode([c], heuristic=True)["win_heal"][0]
    assert selfplay.label_heal(c, {"no_death": True}) == 0
    # A result's `healed` (the HP the win actually gave) wins over the plan.
    assert selfplay.label_heal(c, {"healed": 3}) == 3
    r = sts.run("search", [("cultist", sts.starter_deck("ironclad"), s) for s in range(4)], hp=78)
    assert all(x["healed"] == 6 or (x["hp_end"] == 80 and 0 <= x["healed"] < 6) for x in r if x["won"])
    assert all(x["healed"] == 0 and x["hp_end"] == 0 for x in r if not x["won"])


def test_with_player_hp():
    c = sts.Combat(sts.starter_deck("ironclad"), "cultist", seed=1, hp=50)
    d = c.with_player_hp(20)
    assert (d.player_hp(), c.player_hp()) == (20, 50)
    assert d.encode() != c.encode() and sts.Combat.decode(d.encode()).player_hp() == 20


def test_histogram_bins():
    """1-HP bins up to 30, wider bins up to 150, one bin for >= 150 and a
    turn-limit bin; every HP lost lands in the bin whose range holds it."""
    assert stsnet.N_BINS == len(stsnet.BIN_REP) == len(stsnet.BIN_LOW) + 1 == 47
    for lost in (0, 1, 29, 30, 34, 35, 59, 60, 69, 149, 150, 400):
        b = stsnet.bin_index(lost)
        assert stsnet.BIN_LOW[b] <= lost and (b + 1 == len(stsnet.BIN_LOW) or lost < stsnet.BIN_LOW[b + 1])
    assert [stsnet.bin_index(h) for h in range(30)] == list(range(30))
    assert stsnet.BIN_REP[stsnet.bin_index(12)] == 12 and stsnet.BIN_REP[stsnet.bin_index(31)] == 32.5
    t_ = selfplay.hp_target(40, {"won": False, "hp_end": -3})
    assert t_.sum() == 1 and t_[stsnet.TURN_LIMIT_BIN] == 1


def test_net_histogram_sums_to_one():
    states = sts.run("search", [("cultist", sts.starter_deck("ironclad"), 4)], record=True)[0]["states"]
    f = sts.Features("effects")
    b = f.encode(states, heuristic=True)
    model = stsnet.ValueNet(f.dims, hp_loss=True)
    norm = stsnet.Normalizer.fit(stsnet.Dataset.from_batches([b], np.zeros(len(states))))
    with torch.no_grad():
        h = stsnet.histogram(model, norm.tensors(b))
    assert h.shape == (len(states), stsnet.N_BINS) and (h >= 0).all()
    assert torch.allclose(h.sum(1), torch.ones(len(states)))


def test_win_probability_is_the_mass_below_hp():
    rng = np.random.default_rng(3)
    p = torch.from_numpy(rng.dirichlet(np.ones(stsnet.N_BINS), 4).astype(np.float32))
    for h in (1, 7, 30, 35, 60, 80):
        hp = torch.full((4,), float(h))
        below = torch.tensor([float(stsnet.BIN_REP[b]) < h and b < stsnet.N_BINS - 2 for b in range(stsnet.N_BINS)])
        assert torch.allclose(stsnet.win_probability(p, hp), p[:, below].sum(1))
    # The >= 150 and turn-limit bins never win.
    assert float(stsnet.win_probability(onehot(200), torch.tensor([500.0]))) == 0.0
    assert float(stsnet.win_probability(onehot(0, won=False), torch.tensor([80.0]))) == 0.0


def test_spread_below_hp_wins_above_loses():
    hp, start, mx, heal = t([40.0], [80.0], [80.0], [6.0])
    below = (onehot(5) + onehot(20)) / 2
    above = (onehot(45) + onehot(100)) / 2
    assert float(stsnet.win_probability(below, hp)) == 1.0
    assert float(stsnet.win_probability(above, hp)) == 0.0
    assert float(stsnet.external_score(above, hp, start, mx, heal)) == 0.0
    # All win: score = 2 - mean(HP lost after the heal) / 100.
    lost = np.array([80 - (40 - 5 + 6), 80 - (40 - 20 + 6)])
    assert abs(float(stsnet.external_score(below, hp, start, mx, heal)) - float((2 - lost / 100).mean())) < 1e-6


def won_game():
    """A search + heuristic game won on full HP after losing some HP."""
    deck = sts.starter_deck("ironclad")
    for seed in range(200):
        r = sts.run("search", [("jaw_worm", deck, seed)], record=True, limit=selfplay.LIMIT)[0]
        if r["won"] and 80 - r["hp_end"] > 10:
            return deck, seed, r
    raise AssertionError("no won game found")


def test_formula_on_a_one_bin_case_equals_the_engines_score():
    """Deterministic case: replaying a won game in no-death mode gives the HP
    left before the heal; a histogram with all its mass in the bin of the
    HP lost from a state (a 1-HP bin) reproduces the engine's score after
    Burning Blood's heal."""
    deck, seed, r = won_game()
    c = sts.Combat(deck, "jaw_worm", seed=seed, no_death=True)
    hps = []
    for a in r["actions"]:
        hps.append(c.player_hp())
        c.step(a)
    assert c.won()
    end = c.player_hp()
    assert end + c.win_heal >= r["hp_end"]  # the engine healed (up to max HP)
    hp_s = next(h for h in hps if 0 < h - end < 30)
    hp, start, mx, heal = t([hp_s], [80.0], [80.0], [6.0])
    assert abs(float(stsnet.external_score(onehot(hp_s - end), hp, start, mx, heal)) - r["score"]) < 1e-6
    assert selfplay.hp_label(hp_s, {"won": True, "hp_end": end}) == hp_s - end


def test_hp_labels_are_capped_and_the_turn_limit_gets_the_cap():
    assert selfplay.hp_label(30, {"won": True, "hp_end": -200}) == selfplay.HP_CAP
    assert selfplay.hp_label(30, {"won": False, "hp_end": -5}) == selfplay.HP_CAP


def test_hp_label_scale():
    """The scale check reads a histogram label as its expected HP lost."""
    import learn
    s = [sts.Combat(selfplay.STARTER, "cultist", seed=1)] * 2
    tg = [selfplay.hp_target(20, {"won": True, "hp_end": 10}), selfplay.hp_target(30, {"won": True, "hp_end": 0})]
    ds = stsnet.Dataset.from_batches([selfplay.features("effects").encode(s)], tg, extra={"outcome": [10.0, 30.0]})
    # 30 lost lands in the bin [30, 35), read as 32.5.
    assert abs(learn.label_scale(ds) - abs((10 + 32.5) / 2 - 20)) < 1e-6


def test_hp_labels_from_stored_no_death_games():
    """A no-death dataset replays in no-death mode; its states are labelled
    with a one-hot of the HP lost to the end of their game."""
    specs, groups = selfplay.make_specs(2, 41, selfplay.train_deck)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        ds, results = registry.selfplay(specs, groups, CONFIG, root=root, keep_states=True)
        games = registry.load_games(ds, root)
        assert all(g["no_death"] for g in games)
        for g, r in zip(games, results):
            rp = registry.replay(g)
            assert [s.player_hp() for s in rp["states"]] == [s.player_hp() for s in r["states"]]
            assert rp["hp_end"] == r["hp_end"]
        on = registry.examples(ds, "effects", root=root, labels={"hp_loss": True})
    assert on.hp is not None and on.target.shape == (len(on), stsnet.N_BINS)
    assert ((on.target == 0) | (on.target == 1)).all() and (on.target.sum(1) == 1).all()
    # Each label is the bin of the example's real HP lost (the cap: >= 150
    # or the turn limit).
    hot = on.target.argmax(1)
    capped = on.outcome == selfplay.HP_CAP
    assert (hot[~capped] == [stsnet.bin_index(x) for x in on.outcome[~capped]]).all()
    assert np.isin(hot[capped], [stsnet.N_BINS - 2, stsnet.TURN_LIMIT_BIN]).all()
    # Every outcome is some game's HP lost from the state's HP (or the cap).
    ends = np.array([r["hp_end"] for r in results if r["won"]], np.float32)
    lost = on.hp[:, None] - ends[None, :]
    assert (np.isclose(on.outcome[:, None], np.minimum(lost, selfplay.HP_CAP)).any(1) | capped).all()


def test_learn_with_hp_loss():
    """A tiny run with switch 6 (and the ranking loss, always on) trains
    histogram nets (round 1 on no-death games played by round 0's net)
    whose evaluator scores states in [0, 2] and drives search."""
    import learn
    cfg = {"name": "smoke-6", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 51, "val_seed": 52,
           "search": {"limit": selfplay.LIMIT}, "seed": 0, "rounds": {"n": 1, "every": 100},
           "switches": {"hp_loss": True}}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        run = learn.learn(cfg, root=root, log=lambda *_: None)[-1]
        model, norm, meta = stsnet.load(run.model_path)
        man = registry.load_manifest(meta["datasets"]["train"][0], root)
        rnd = run._read("round.json")
    assert model.hp_loss and man["config"]["no_death"] and man["config"]["round"] == 1
    assert rnd["label_scale"]["tolerance"] == 10.0
    feats = stsnet.features_for(meta)
    ev = stsnet.Evaluator(model, norm)
    states = sts.run("search", [("cultist", sts.starter_deck("ironclad"), 4)], record=True)[0]["states"]
    v = ev(feats.encode(states, heuristic=True))
    assert v.shape == (len(states),) and ((v >= 0) & (v <= 2)).all()
    assert sts.search(states[0], ev, features=feats, limit=selfplay.LIMIT)["action"] is not None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t_ in tests:
        t_()
        print("ok ", t_.__name__)
    print(len(tests), "passed")
