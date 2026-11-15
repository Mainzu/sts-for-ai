"""Generated power mechanics (docs/specs/registry-lite.md, step 4): a content
pack of N generated powers, each with one power card that grants it.

    python scripts/gen_content.py --seed 1 --powers 200 --out data/content/gen-s1.json

A power is 1-2 hooks built from existing atoms (trigger, condition, 1-2
effects) plus one of four lifetimes: permanent; this turn (a sibling
OwnerTurnEnd -> RemoveSelf hook); used up (RemoveSelf in the hook); wearing
down (ReduceSelf(1) in the hook). Its card costs 1-3 and grants 1-3 stacks
to the player.

Split by mechanic: a power's keys are its (trigger, effect kind) pairs. Every
pair an official training power has is train; of the rest, a fixed hash puts
about a quarter in test, and turn start -> +Strength (Demon Form's pairing)
is always test. A power draws all its pairs from one side, so no test pair
appears in any train power or official training power. The split doesn't
depend on the seed.

Budget: the heuristic's value change from playing a cost-0 copy of the card
(mean over a fixed set of turn-1 states), divided by the card's cost, must
lie in the range the official power cards span the same way (`official_range`).
The heuristic prices only the hook patterns its `hook_rates` reads; a power
it can't price (gain within UNPRICED of 0, or negative with a draw or energy
effect, as Brutality) is kept as "unpriced" with cost 1-2; a power priced
below zero otherwise is redrawn.

Validity: no hook can fire itself (OwnerLostHp with a self HP loss); draw
and energy only at turn start, draw also on the owner's card plays (1 per
stack); never energy on card plays (with draw, an endless turn).
"""

import argparse
import hashlib
import json
import os
import random
import sys

import numpy as np

import sts

VERSION = 2  # content-file version: OwnerTurnStart runs before the turn's draw (docs/specs/turn-start-draw.md)
UNPRICED = 0.01
TEST_SHARE = 4  # one key in TEST_SHARE goes to test
FORCED_TEST = ("OwnerTurnStart", "Apply:Strength")

TRIGGERS = {
    "OwnerTurnStart": "OwnerTurnStart",
    "OwnerTurnEnd": "OwnerTurnEnd",
    "CardPlayed:Owner": {"CardPlayed": {"by": "Owner"}},
    "OwnerLostHp:Card": {"OwnerLostHp": {"from": "Card"}},
    "OwnerLostHp:Attack": {"OwnerLostHp": {"from": "Attack"}},
    "OwnerLostHp:Any": {"OwnerLostHp": {"from": "Any"}},
}
# Effect kind -> (per-stack amount range, builder). Ranges follow the
# official hook amounts per stack (Metallicize 3-4 block, Combust 5 damage).
EFFECTS = {
    "Block": ((1, 4), lambda a: {"Block": a}),
    "Draw": ((1, 1), lambda a: {"Draw": a}),
    "GainEnergy": ((1, 1), lambda a: {"GainEnergy": a}),
    "LoseHp": ((1, 2), lambda a: {"LoseHp": a}),
    "PlainDamage": ((1, 5), lambda a: {"PlainDamage": {"amount": a, "target": "AllOpponents"}}),
    "Damage": ((1, 4), lambda a: {"Damage": {"amount": a, "hits": 1, "target": "AllOpponents"}}),
    "Apply:Strength": ((1, 1), lambda a: {"Apply": {"power": "Strength", "amount": a, "target": "Me"}}),
    "Apply:Dexterity": ((1, 1), lambda a: {"Apply": {"power": "Dexterity", "amount": a, "target": "Me"}}),
    "Apply:Vulnerable": ((1, 1), lambda a: {"Apply": {"power": "Vulnerable", "amount": a, "target": "AllOpponents"}}),
    "Apply:Weak": ((1, 1), lambda a: {"Apply": {"power": "Weak", "amount": a, "target": "AllOpponents"}}),
}
# (trigger, effect kind) pairs of the official powers training games hold
# (player cards in the training pool, and the Act-1 training monsters').
OFFICIAL_TRAIN_PAIRS = {
    ("OwnerTurnEnd", "LoseHp"),             # Combust
    ("OwnerTurnEnd", "PlainDamage"),        # Combust
    ("OwnerTurnStart", "LoseHp"),           # Brutality
    ("OwnerTurnStart", "Draw"),             # Brutality
    ("OwnerLostHp:Card", "Apply:Strength"),  # Rupture
    ("OwnerTurnEnd", "Apply:Strength"),     # Ritual, Lose Strength
    ("OwnerTurnEnd", "Block"),              # Metallicize (Lagavulin)
    ("OwnerLostHp:Attack", "Block"),        # Curl Up
    ("CardPlayed:Opponent", "Apply:Strength"),  # Enrage
}
LIFETIMES = ("permanent", "this_turn", "used_up", "wearing_down")
COST_RANGE = (1, 3)
STACKS_RANGE = (1, 3)

# Official power cards priced the same way (cost-0 copies), and their real costs.
OFFICIAL_CARDS = {
    "Inflame": (1, [{"Apply": {"power": "Strength", "amount": 2, "target": "Me"}}]),
    "Metallicize": (1, [{"Apply": {"power": "Metallicize", "amount": 3, "target": "Me"}}]),
    "Combust": (1, [{"Apply": {"power": "Combust", "amount": 1, "target": "Me"}},
                    {"Apply": {"power": "CombustDamage", "amount": 5, "target": "Me"}}]),
    "Brutality": (0, [{"Apply": {"power": "Brutality", "amount": 1, "target": "Me"}}]),
    "Rupture": (1, [{"Apply": {"power": "Rupture", "amount": 1, "target": "Me"}}]),
    "Demon Form": (3, [{"Apply": {"power": "DemonForm", "amount": 2, "target": "Me"}}]),
}
PRICE_DECK = ["Strike", "Strike", "Defend", "Bash"]  # plus the card: all five in the opening hand
PRICE_STATES = [(e, hp, seed) for e in ("cultist", "jaw_worm", "gremlin_nob", "lagavulin", "slime_boss", "three_sentries")
                for hp in (30, 60) for seed in (1, 2)]


def allowed(trigger, effect):
    """Validity rules for one (trigger, effect kind) pair."""
    if trigger.startswith("OwnerLostHp") and effect == "LoseHp":
        return False  # the hook would fire itself
    if effect == "GainEnergy":
        return trigger == "OwnerTurnStart"
    if effect == "Draw":
        return trigger in ("OwnerTurnStart", "CardPlayed:Owner")
    return True


def _hash(s):
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


def split_of(pair):
    """'train' or 'test' for a (trigger, effect kind) pair; seed-independent."""
    if pair == FORCED_TEST:
        return "test"
    if pair in OFFICIAL_TRAIN_PAIRS:
        return "train"
    return "test" if _hash("|".join(pair)) % TEST_SHARE == 0 else "train"


def all_pairs():
    return [(t, e) for t in TRIGGERS for e in EFFECTS if allowed(t, e)]


def power_pairs(power):
    return sorted({tuple(p) for p in power["keys"]})


# ---- pricing ----

_FEATURES = None


def _features():
    global _FEATURES
    if _FEATURES is None:
        _FEATURES = sts.Features("effects")
    return _FEATURES


def gain(card_name):
    """Mean heuristic value change from playing `card_name` on PRICE_STATES."""
    f = _features()
    g = []
    for enc, hp, seed in PRICE_STATES:
        c = sts.Combat(PRICE_DECK + [card_name], enc, seed=seed, hp=hp)
        before = float(f.encode([c], heuristic=True)["heuristic"][0])
        c.step(next(a for a in c.legal_actions() if a.card == card_name))
        g.append(float(f.encode([c], heuristic=True)["heuristic"][0]) - before)
    return float(np.mean(g))


def _probe_id(obj):
    return "probe_" + hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def official_range():
    """(lowest, highest) value per energy of the official power cards the
    heuristic prices (gain above UNPRICED, cost >= 1)."""
    cards = [{"id": _probe_id(eff), "cost": 0, "type": "Power", "effects": eff} for _, eff in OFFICIAL_CARDS.values()]
    sts.load_content(json.dumps({"version": VERSION, "powers": [], "cards": cards}))
    per = {}
    for (name, (cost, _)), c in zip(OFFICIAL_CARDS.items(), cards):
        g = gain("gen:" + c["id"])
        per[name] = (g, cost)
    priced = [g / cost for g, cost in per.values() if cost >= 1 and g > UNPRICED]
    return min(priced), max(priced), per


def price_power(hooks, stacks):
    """Heuristic gain of a cost-0 card granting `stacks` of a power with `hooks`."""
    power = {"id": _probe_id(hooks), "debuff": False, "hooks": hooks}
    card = {"id": _probe_id([hooks, stacks]), "cost": 0, "type": "Power",
            "effects": [{"Apply": {"power": power["id"], "amount": stacks, "target": "Me"}}]}
    sts.load_content(json.dumps({"version": VERSION, "powers": [power], "cards": [card]}))
    return gain("gen:" + card["id"])


# ---- sampling ----

def _hook(rng, pairs, trigger):
    kinds = [e for t, e in pairs if t == trigger]
    n = 1 if len(kinds) < 2 or rng.random() < 0.6 else 2
    picked = rng.sample(kinds, n)
    effects, keys = [], []
    for k in picked:
        lo, hi = EFFECTS[k][0]
        effects.append(EFFECTS[k][1](rng.randint(lo, hi)))
        keys.append([trigger, k])
    condition = "Always"
    if trigger == "CardPlayed:Owner" and rng.random() < 0.5:
        condition = {"CardType": rng.choice(["Attack", "Skill", "Power"])}
    return {"trigger": TRIGGERS[trigger], "condition": condition, "effects": effects}, keys


def sample_power(rng, split):
    pairs = [p for p in all_pairs() if split_of(p) == split]
    triggers = sorted({t for t, _ in pairs})
    n_hooks = 2 if rng.random() < 0.2 and len(triggers) > 1 else 1
    hooks, keys = [], []
    for t in rng.sample(triggers, n_hooks):
        h, k = _hook(rng, pairs, t)
        hooks.append(h)
        keys += k
    lifetimes = LIFETIMES
    if all(h["trigger"] == "OwnerTurnStart" for h in hooks):
        lifetimes = tuple(x for x in LIFETIMES if x != "this_turn")  # it would end before it fires
    life = rng.choice(lifetimes)
    if life == "this_turn":
        hooks.append({"trigger": "OwnerTurnEnd", "condition": "Always", "effects": ["RemoveSelf"]})
    elif life == "used_up":
        hooks[0]["effects"].append("RemoveSelf")
    elif life == "wearing_down":
        hooks[0]["effects"].append({"ReduceSelf": 1})
    return hooks, keys, life


def _fit(rng, hooks, lo, hi):
    """(stacks, cost, gain, priced) for a power's card, or None to redraw."""
    kinds = {k for h in hooks for e in h["effects"] for k in ([e] if isinstance(e, str) else e)}
    for stacks in rng.sample(range(STACKS_RANGE[0], STACKS_RANGE[1] + 1), STACKS_RANGE[1] - STACKS_RANGE[0] + 1):
        g = price_power(hooks, stacks)
        if abs(g) < UNPRICED or (g < 0 and kinds & {"Draw", "GainEnergy"}):
            return stacks, rng.randint(1, 2), g, False
        if g < 0:
            return None
        fits = [c for c in range(COST_RANGE[0], COST_RANGE[1] + 1) if lo <= g / c <= hi]
        if fits:
            return stacks, rng.choice(fits), g, True
    return None


def generate(seed, n_powers, test_share=0.25):
    lo, hi, official = official_range()
    rng = random.Random(seed)
    powers, cards = [], []
    tries = 0
    while len(powers) < n_powers:
        tries += 1
        if tries > 50 * n_powers:
            raise RuntimeError("generator can't fill the pack; loosen the budget")
        split = "test" if rng.random() < test_share else "train"
        hooks, keys, life = sample_power(rng, split)
        fit = _fit(rng, hooks, lo, hi)
        if fit is None:
            continue
        stacks, cost, g, priced = fit
        i = len(powers)
        pid, cid = f"gp{seed}_{i:03d}", f"gc{seed}_{i:03d}"
        powers.append({"id": pid, "debuff": False, "hooks": hooks, "split": split, "keys": keys,
                       "lifetime": life})
        cards.append({"id": cid, "cost": cost, "type": "Power", "exhaust": False, "ethereal": False,
                      "effects": [{"Apply": {"power": pid, "amount": stacks, "target": "Me"}}],
                      "power": pid, "split": split, "gain": round(g, 6),
                      "value_per_energy": round(g / cost, 6) if priced else None})
    return {"version": VERSION, "seed": seed,
            "budget": {"lo": round(lo, 6), "hi": round(hi, 6), "unpriced_below": UNPRICED,
                       "official": {k: {"gain": round(g, 6), "cost": c} for k, (g, c) in official.items()}},
            "powers": powers, "cards": cards}


def dumps(pack):
    return json.dumps(pack, indent=1, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--powers", type=int, default=200)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    pack = generate(args.seed, args.powers)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(pack))
    n_test = sum(p["split"] == "test" for p in pack["powers"])
    n_priced = sum(c["value_per_energy"] is not None for c in pack["cards"])
    print(f"{len(pack['powers'])} powers ({n_test} test), {n_priced} priced; budget "
          f"{pack['budget']['lo']:.3f}-{pack['budget']['hi']:.3f} per energy -> {args.out}")


if __name__ == "__main__":
    sys.exit(main())
