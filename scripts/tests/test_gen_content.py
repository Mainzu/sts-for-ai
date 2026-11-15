"""Tests for the generated-content generator (docs/specs/registry-lite.md,
step 4): seeded determinism, validity rules, the train / test split by
(trigger, effect kind) pair, the budget, and 200 powers x 20 heuristic
fights with no engine error and under 1% stalls. Run with
`python scripts/tests/test_gen_content.py` (plain asserts; every `test_*`
function runs) or with pytest. About 10 s."""

import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gen_content as gc  # noqa: E402
import sts  # noqa: E402

N = 200
_PACK = {}


def pack(seed=1):
    if seed not in _PACK:
        _PACK[seed] = gc.generate(seed, N)
    return _PACK[seed]


def effect_kind(e):
    if isinstance(e, str):
        return e
    (k, v), = e.items()
    return f"Apply:{v['power']}" if k == "Apply" else k


def trigger_key(t):
    if isinstance(t, str):
        return t
    (k, v), = t.items()
    return f"{k}:{next(iter(v.values()))}"


def main_hooks(p):
    """The power's hooks without the "this turn" RemoveSelf sibling."""
    return [h for h in p["hooks"] if h["effects"] != ["RemoveSelf"]]


def test_same_seed_same_bytes():
    a = gc.dumps(pack(1))
    assert gc.dumps(gc.generate(1, N)) == a
    assert gc.dumps(pack(2)) != a


def test_pack_loads():
    h = sts.load_content(gc.dumps(pack(1)))
    assert isinstance(h, str) and h


def test_validity_rules():
    for p in pack(1)["powers"]:
        assert 1 <= len(main_hooks(p)) <= 2, p
        keys = set()
        for h in main_hooks(p):
            t = trigger_key(h["trigger"])
            kinds = [effect_kind(e) for e in h["effects"] if effect_kind(e) not in ("RemoveSelf", "ReduceSelf")]
            assert 1 <= len(kinds) <= 2, p
            for k in kinds:
                assert gc.allowed(t, k), (t, k)
                keys.add((t, k))
                if k in ("Draw", "GainEnergy"):
                    amt = next(v for e in h["effects"] if effect_kind(e) == k for v in e.values())
                    assert amt == 1, p  # one per stack
                if t.startswith("OwnerLostHp"):
                    assert k != "LoseHp", p  # would fire itself
                if t.startswith("CardPlayed"):
                    assert k != "GainEnergy", p
            for e in h["effects"]:  # generated powers never apply generated powers
                if effect_kind(e).startswith("Apply:"):
                    assert e["Apply"]["power"] in ("Strength", "Dexterity", "Vulnerable", "Weak"), e
        assert keys == {tuple(k) for k in p["keys"]}, p
        assert p["lifetime"] in gc.LIFETIMES
        if p["lifetime"] == "this_turn":
            assert {"trigger": "OwnerTurnEnd", "condition": "Always", "effects": ["RemoveSelf"]} in p["hooks"]


def test_cards_grant_their_power():
    pk = pack(1)
    assert len(pk["cards"]) == len(pk["powers"]) == N
    for p, c in zip(pk["powers"], pk["cards"]):
        assert c["type"] == "Power" and gc.COST_RANGE[0] <= c["cost"] <= gc.COST_RANGE[1]
        (eff,) = c["effects"]
        assert eff["Apply"]["power"] == p["id"] and eff["Apply"]["target"] == "Me"
        assert gc.STACKS_RANGE[0] <= eff["Apply"]["amount"] <= gc.STACKS_RANGE[1]
        assert c["split"] == p["split"]


def test_split_by_mechanic():
    pk = pack(1)
    train_pairs = {tuple(k) for p in pk["powers"] if p["split"] == "train" for k in p["keys"]}
    test_pairs = {tuple(k) for p in pk["powers"] if p["split"] == "test" for k in p["keys"]}
    assert not train_pairs & test_pairs
    assert not test_pairs & gc.OFFICIAL_TRAIN_PAIRS
    assert all(gc.split_of(k) == "train" for k in gc.OFFICIAL_TRAIN_PAIRS)
    assert gc.split_of(("OwnerTurnStart", "Apply:Strength")) == "test"  # Demon Form's pairing
    n_test = sum(p["split"] == "test" for p in pk["powers"])
    assert 0.15 * N <= n_test <= 0.35 * N, n_test
    # the split is a property of the pair, not of the seed
    other = {tuple(k): p["split"] for p in pack(2)["powers"] for k in p["keys"]}
    assert all(other[k] == "test" for k in test_pairs if k in other)


def test_arm_packs():
    """The training arms' packs (docs/specs/gen-training-arms.md): seed 2 at
    19 / 176 powers holds 16 / 128 train cards, and the small one is a
    prefix of the big one."""
    small, big = gc.generate(2, 19), gc.generate(2, 176)
    assert sum(c["split"] == "train" for c in small["cards"]) == 16
    assert sum(c["split"] == "train" for c in big["cards"]) == 128
    assert big["powers"][:19] == small["powers"] and big["cards"][:19] == small["cards"]


def test_budget_in_official_range():
    pk = pack(1)
    lo, hi = pk["budget"]["lo"], pk["budget"]["hi"]
    assert 0 < lo < hi
    off = pk["budget"]["official"]
    assert abs(off["Demon Form"]["gain"] / 3 - lo) < 1e-6 or lo < off["Demon Form"]["gain"] / 3
    priced = [c for c in pk["cards"] if c["value_per_energy"] is not None]
    assert len(priced) >= N // 10
    for c in priced:
        assert lo - 1e-9 <= c["value_per_energy"] <= hi + 1e-9, c
        assert abs(c["gain"] / c["cost"] - c["value_per_energy"]) < 1e-5
    for c in pk["cards"]:
        if c["value_per_energy"] is None:
            assert c["cost"] in (1, 2) and (abs(c["gain"]) < gc.UNPRICED or c["gain"] < 0), c
    # recompute a few prices from scratch
    for p, c in list(zip(pk["powers"], pk["cards"]))[:5]:
        g = gc.price_power(p["hooks"], c["effects"][0]["Apply"]["amount"])
        assert abs(g - c["gain"]) < 1e-5, (g, c)


def test_heuristic_fights_no_errors_few_stalls():
    pk = pack(1)
    sts.load_content(gc.dumps(pk))
    train = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "data", "bench", "tight2.json"),
                           encoding="utf-8"))["halves"]["train"]
    rng = random.Random(0)
    starter = sts.starter_deck("ironclad")
    specs = [(s["encounter"], starter + ["gen:" + c["id"]], s["seed"], s["hp"])
             for c in pk["cards"] for s in rng.sample(train, 20)]
    res = sts.run("search", specs, threads=4, record=True)
    assert len(res) == N * 20
    stalls = sum(r["turns"] > 100 for r in res)
    assert stalls < 0.01 * len(res), stalls
    played = sum(any((a.card or "").startswith("gen:") for a in r["actions"]) for r in res)
    print(f"    {len(res)} fights: {stalls} stalls, won {sum(r['won'] for r in res) / len(res):.3f}, "
          f"generated card played in {played / len(res):.0%}")
    assert played > 0.2 * len(res)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, f in tests:
        f()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
