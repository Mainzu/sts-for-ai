"""Mutated monsters, stage A (docs/specs/mutated-monsters-a.md): the
gauntlet's elite and boss fights replayed from their first decision with
the enemies mutated by a patch of the start state (HP scaled, a power
added; alone, in the owner's boon + bane pairs, and one stack), played by
the heuristic, the product net one turn deep and (a subset) two turns
deep on common seeds. `read` gives per modifier the difficulty change
(heuristic and two-turn product), the one-turn net's drop beyond it
(novelty cost) and whether depth repairs it.

    .venv/Scripts/python scripts/analysis/mutate_monsters.py play --starts 200 --seeds 8 --players heuristic,one --threads 3 --out results/mutate/a.json
    .venv/Scripts/python scripts/analysis/mutate_monsters.py play --players two --two-starts 40 --two-seeds 4 --out results/mutate/a.json
    .venv/Scripts/python scripts/analysis/mutate_monsters.py read results/mutate/a.json
    .venv/Scripts/python scripts/analysis/mutate_monsters.py odds results/mutate/wide.json  # yardstick/novelty-read column 2
    .venv/Scripts/python scripts/analysis/mutate_monsters.py play --groups elite --mods gen-batch1 --net <net>@tsl1 ... --out results/mutate/gen-enemies.json
    .venv/Scripts/python scripts/analysis/mutate_monsters.py read-gen results/mutate/gen-enemies.json  # docs/specs/generated-enemies-bench.md

`play --net <path>` plays the `one` player with `<path>@hpb0.01` (an
adaptation burst, docs/specs/adaptation-curve.md); `compare <base> <burst>`
gives per modifier the burst's gain in novelty cost over the base file's
net, paired by start (the heuristic cancels: same seeds).
"""

import argparse
import collections
import hashlib
import json
import os
import sys
import time

# The engine's search recurses once per action and chance event of a line
# of play; long turns overflowed the 2 MB default thread stack (job 0975).
os.environ.setdefault("RUST_MIN_STACK", str(64 << 20))

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import bench  # noqa: E402
import bias_audit as ba  # noqa: E402
import sts  # noqa: E402

PRODUCT = "results/gauntlet/net1029-hpe0.01-two-starter-simboss.json"
NET = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt"
PLAYERS = {"heuristic": None, "one": NET + "@hpb0.01", "two": NET + "@hpe0.01", "product": NET + "@hpe0.01"}
DEEP = ("two", "product")  # the players --two-starts, --two-seeds and --two-net apply to
TWO_TURN = {"sample_k": 4, "turns": 2, "max_nodes": 400_000}
# name -> patches: ("hp", factor) scales every living monster's hp and max_hp;
# ("power", name, amount) raises that power on every living monster.
# One-sided, then the owner's pairs (ritual2 stands in for "+2 Strength per
# turn"; SharpHide is damage to the attacker per attack card played), then
# stacks of pairs. Stage B (docs/specs/mutated-monsters-b.md) adds pattern
# modifiers: DamageDown (attacks deal 4/5), WeakOnHit (Weak per unblocked
# hit), SplitHits (twice the hits at half the base).
PAIRS = {
    "metal4-hp0.85": [("power", "Metallicize", 4), ("hp", 0.85)],
    "ritual2-hp0.7": [("power", "Ritual", 2), ("hp", 0.7)],
    "sharp2-hp0.9": [("power", "SharpHide", 2), ("hp", 0.9)],
    # Retuned after the stage A read (metal4-hp0.85 came out easier than the
    # parent, sharp2-hp0.9 clearly harder): candidates nearer the parent.
    "metal4-hp0.75": [("power", "Metallicize", 4), ("hp", 0.75)],
    "sharp1-hp0.9": [("power", "SharpHide", 1), ("hp", 0.9)],
    # Owner pairs the landed engine expresses as a state patch: Thorns
    # (damage to the attacker per hit) and "+30% HP with -1 damage per hit"
    # (Strength -1).
    "thorns2-hp0.9": [("power", "Thorns", 2), ("hp", 0.9)],
    "hp1.3-str-1": [("hp", 1.3), ("power", "Strength", -1)],
    # Stage B: the owner's "Weak on hit with -20% damage".
    "weakhit1-dmg0.8": [("power", "WeakOnHit", 1), ("power", "DamageDown", 1)],
}
SPLIT = [("power", "SplitHits", 1)]
# Stacks of pairs (and split) for the stacking check (a stack's difficulty about the sum
# of its parts): the parts' patches applied in order.
STACKS = ["metal4-hp0.75+sharp1-hp0.9", "metal4-hp0.75+ritual2-hp0.7", "ritual2-hp0.7+hp1.3-str-1",
          "thorns2-hp0.9+hp1.3-str-1", "metal4-hp0.75+thorns2-hp0.9+hp1.3-str-1",
          "weakhit1-dmg0.8+split", "weakhit1-dmg0.8+thorns2-hp0.9"]
MODS = {
    "hp0.8": [("hp", 0.8)], "hp1.25": [("hp", 1.25)],
    "str1": [("power", "Strength", 1)], "str2": [("power", "Strength", 2)],
    "metal3": [("power", "Metallicize", 3)], "ritual2": [("power", "Ritual", 2)], "sharp2": [("power", "SharpHide", 2)],
    **PAIRS,
    "thorns2": [("power", "Thorns", 2)],
    # Stage B one-sided; split is itself the owner's trade (more hits, less each).
    "weakhit1": [("power", "WeakOnHit", 1)], "dmg0.8": [("power", "DamageDown", 1)],
    "split": SPLIT,
    "metal4-hp0.85+sharp2-hp0.9": PAIRS["metal4-hp0.85"] + PAIRS["sharp2-hp0.9"],
    **{k: [p for part in k.split("+") for p in {**PAIRS, "split": SPLIT}[part]] for k in STACKS},
}

# Stat-only control ladder for the generated enemies bench, smallest change
# first (ties in `gen_table` go to the earlier entry).
LADDER = {
    "c-hp0.8": [("hp", 0.8)], "c-hp1.25": [("hp", 1.25)], "c-str1": [("power", "Strength", 1)],
    "c-hp1.5": [("hp", 1.5)], "c-str2": [("power", "Strength", 2)],
    "c-hp1.25-str1": [("hp", 1.25), ("power", "Strength", 1)], "c-hp2": [("hp", 2.0)],
    "c-str3": [("power", "Strength", 3)], "c-hp1.5-str2": [("hp", 1.5), ("power", "Strength", 2)],
    "c-hp2-str3": [("hp", 2.0), ("power", "Strength", 3)],
}

# Generated enemies bench (docs/specs/generated-enemies-bench.md): the 24
# mechanics are every (trigger, effect) pair below on a monster owner except
# the four official training monsters hold (gen_content.OFFICIAL_TRAIN_PAIRS:
# Ritual, Metallicize, Curl Up, Enrage). Each is a pack power `GE-<t>-<e>`
# (one hook, condition Always, 1 per stack) given to every living monster
# as a ("pack", id, stacks) patch: 1 stack on the per-card and per-hit
# triggers, on Strength and the debuffs; Block 4, Damage 3, PlainDamage 3 on
# the turn triggers.
GEN_TRIGGERS = {
    "TurnStart": "OwnerTurnStart", "TurnEnd": "OwnerTurnEnd",
    "OppCard": {"CardPlayed": {"by": "Opponent"}}, "AttackLoss": {"OwnerLostHp": {"from": "Attack"}},
}
GEN_EFFECTS = {
    "Strength": {"Apply": {"power": "Strength", "amount": 1, "target": "Me"}},
    "Block": {"Block": 1},
    "Damage": {"Damage": {"amount": 1, "hits": 1, "target": "AllOpponents"}},
    "PlainDamage": {"PlainDamage": {"amount": 1, "target": "AllOpponents"}},
    **{d: {"Apply": {"power": d, "amount": 1, "target": "AllOpponents"}} for d in ("Weak", "Vulnerable", "Frail")},
}
GEN_OFFICIAL = {("TurnEnd", "Strength"), ("TurnEnd", "Block"), ("AttackLoss", "Block"), ("OppCard", "Strength")}
GEN_TURN_STACKS = {"Block": 4, "Damage": 3, "PlainDamage": 3}


def _gen():
    out = {}
    for t in GEN_TRIGGERS:
        for e in GEN_EFFECTS:
            if (t, e) not in GEN_OFFICIAL:
                k = GEN_TURN_STACKS.get(e, 1) if t.startswith("Turn") else 1
                out[f"GE-{t}-{e}"] = [("pack", f"GE-{t}-{e}", k)]
    return out


GEN = _gen()

# Wider grid (docs/specs/wider-generators.md): five more triggers (a
# trigger word, or (trigger, condition)) and five more effects; the old 24
# keep their names, powers and stacks. Pairs an official power's hook holds
# stay out: the old four and Enrage, Sharp Hide, Thorns, WeakOnHit.
WIDE_TRIGGERS = {
    "RoundEnd": "RoundEnd", "Attacked": "OwnerAttacked", "AttackHit": "OwnerAttackHit",
    "OppAttack": ({"CardPlayed": {"by": "Opponent"}}, {"CardType": "Attack"}),
    "OppSkill": ({"CardPlayed": {"by": "Opponent"}}, {"CardType": "Skill"}),
}
WIDE_EFFECTS = {
    "StrDown": {"Apply": {"power": "Strength", "amount": -1, "target": "AllOpponents"}},
    "DexDown": {"Apply": {"power": "Dexterity", "amount": -1, "target": "AllOpponents"}},
    "Artifact": {"Apply": {"power": "Artifact", "amount": 1, "target": "Me"}},
    "Wound": {"AddCard": {"card": "Wound", "n": 1, "pile": "Discard"}},
    "Dazed": {"AddCard": {"card": "Dazed", "n": 1, "pile": "Draw"}},
}
ALL_TRIGGERS = {**GEN_TRIGGERS, **WIDE_TRIGGERS}
ALL_EFFECTS = {**GEN_EFFECTS, **WIDE_EFFECTS}
WIDE_OFFICIAL = GEN_OFFICIAL | {("OppSkill", "Strength"), ("OppAttack", "PlainDamage"),
                                ("Attacked", "PlainDamage"), ("AttackHit", "Weak")}
TURN_TRIGGERS = ("TurnStart", "TurnEnd", "RoundEnd")
WHOLE_TRIGGER, WHOLE_EFFECT = "Attacked", "Wound"


def _wide():
    out = {}
    for t in ALL_TRIGGERS:
        for e in ALL_EFFECTS:
            name = f"GE-{t}-{e}"
            if (t, e) in WIDE_OFFICIAL or name in GEN:
                continue
            k = GEN_TURN_STACKS.get(e, 1) if t in TURN_TRIGGERS else 1
            out[name] = [("pack", name, k)]
    return out


WIDE = _wide()


def _wide_split():
    """The new 76's split: whole trigger, whole effect, held-out pairs (sha256 % 4 == 0), train."""
    s = {"whole_trigger": [], "whole_effect": [], "held_pairs": [], "train": []}
    for m in WIDE:
        _, t, e = m.split("-")
        if t == WHOLE_TRIGGER:
            s["whole_trigger"].append(m)
        elif e == WHOLE_EFFECT:
            s["whole_effect"].append(m)
        elif int(hashlib.sha256(m.encode()).hexdigest(), 16) % 4 == 0:
            s["held_pairs"].append(m)
        else:
            s["train"].append(m)
    return s


WIDE_SPLIT = _wide_split()
GEN_ALL = {**GEN, **WIDE}
# First batch: per trigger, the first two mechanics by sha256 of the name.
GEN_BATCH1 = [m for t in GEN_TRIGGERS for m in sorted((x for x in GEN if x.split("-")[1] == t),
                                                    key=lambda x: hashlib.sha256(x.encode()).hexdigest())[:2]]
# Fickle enemy, first form (docs/specs/fickle-enemy.md): during the
# player's turn the monster names a card type, each card of it played gives
# the monster 1 Strength; at the monster's turn start the type moves on
# Attack -> Power -> Skill -> Attack and the ended type costs it n HP
# (Attack, Skill) or heals it n (Power), n = 5% of its max HP rounded up,
# fixed at patch time. `FE-<T>` opens on type T. Powers `FE-<T>-<n>`, one
# per n because stacks scale every amount of a hook.
FICKLE_TYPES = ["Attack", "Power", "Skill"]
FICKLE_MAX_N = 20
FICKLE = {f"FE-{t}": [("fickle", t)] for t in FICKLE_TYPES}
# "parent": no patch, the unmodified fight (a burst rehearsing its parents).
ALL = {**MODS, **LADDER, **GEN_ALL, **FICKLE, "parent": []}


def gen_power(m):
    """Mechanic `m`'s pack power: one hook, its trigger (and condition), its effect at 1 per stack."""
    t = ALL_TRIGGERS[m.split("-")[1]]
    trigger, cond = t if isinstance(t, tuple) else (t, "Always")
    return {"id": m, "debuff": False, "statics": [], "replacements": [],
            "hooks": [{"trigger": trigger, "condition": cond, "effects": [ALL_EFFECTS[m.split("-")[2]]]}]}


def gen_pack():
    """The mechanics' pack powers (the old 24, then the wider grid's 76) as content-pack JSON text."""
    return json.dumps({"version": 1, "powers": [gen_power(m) for m in GEN_ALL]}, sort_keys=True)


def fickle_n(max_hp):
    """The fickle HP amount: 5% of `max_hp`, rounded up."""
    return (max_hp * 5 + 99) // 100


def fickle_pack():
    """The fickle powers as content-pack JSON text, with the one-type
    forms as data: Curiosity (Power cards) and FE-AttackEnrage (Attack)."""
    strength = {"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}
    played = lambda t: {"trigger": {"CardPlayed": {"by": "Opponent"}}, "condition": {"CardType": t}, "effects": [strength]}  # noqa: E731
    powers = [{"id": pid, "debuff": False, "statics": [], "replacements": [], "hooks": [played(t)]}
              for pid, t in (("Curiosity", "Power"), ("FE-AttackEnrage", "Attack"))]
    for i, t in enumerate(FICKLE_TYPES):
        nxt = FICKLE_TYPES[(i + 1) % len(FICKLE_TYPES)]
        for n in range(1, FICKLE_MAX_N + 1):
            hp = {"Heal": n} if t == "Power" else {"LoseHp": n}
            turn = {"trigger": "OwnerTurnStart", "condition": "Always",
                    "effects": [hp, {"Apply": {"power": f"FE-{nxt}-{n}", "amount": 1, "target": "Me"}}, "RemoveSelf"]}
            powers.append({"id": f"FE-{t}-{n}", "debuff": False, "statics": [], "replacements": [],
                           "hooks": [played(t), turn]})
    return json.dumps({"version": 1, "powers": powers}, sort_keys=True)


def living(c):
    """[(slot, hp, max_hp)] of Combat `c`'s living monsters."""
    return [(m["slot"], m["hp"], m["max_hp"]) for m in c.board()["monsters"]]


def with_hp_scale(c, factor):
    """A copy of Combat `c` with every living monster's hp and max_hp
    scaled by `factor` (rounded, at least 1)."""
    for slot, hp, max_hp in living(c):
        c = c.with_monster_hp(slot, max(1, int(round(hp * factor))), max(1, int(round(max_hp * factor))))
    return c


def patched(c, patches):
    """Combat `c` with official `patches` applied in order to every living monster."""
    for p in patches:
        if p[0] == "hp":
            c = with_hp_scale(c, p[1])
        else:
            for slot, _, _ in living(c):
                c = c.with_monster_power(slot, p[1], p[2])
    return c


def mutate(c, patches):
    """`c`'s bytes with `patches` applied in order to every living monster."""
    return bytes(patched(c, patches).encode())


def variant_parts(c, patches):
    """(bytes, powers) of `c` with `patches`: the official ones applied to the
    state bytes (`mutate`), then [slot, power, n] for each ("pack", id, n), `n`
    stacks of a loaded pack power on every living monster, and each fickle one."""
    m = patched(c, [p for p in patches if p[0] not in ("pack", "fickle")])
    powers = []
    for p in patches:
        if p[0] == "pack":
            powers += [[slot, p[1], p[2]] for slot, _, _ in living(m)]
        elif p[0] == "fickle":
            for slot, _, max_hp in living(m):
                n = fickle_n(max_hp)
                assert n <= FICKLE_MAX_N, max_hp
                powers.append([slot, f"FE-{p[1]}-{n}", 1])
    return bytes(m.encode()), powers


def variant(c, patches):
    """`c` (a Combat) with `patches` applied (`variant_parts`)."""
    b, powers = variant_parts(c, patches)
    v = sts.Combat.decode(b)
    for slot, power, n in powers:
        v = v.with_monster_power(slot, power, n)
    return v


def start_state(spec):
    """The fight at its first decision."""
    c = sts.Combat(spec["deck"], spec["encounter"], seed=spec["seed"], hp=spec["hp"], character=spec["character"])
    while not c.is_over() and not c.awaiting_action():
        c.advance()
    return c


def play_variants(variants, seeds, player, threads):
    """{won, hp_end} per (variant, seed) for `player` (a PLAYERS key);
    `variants` are Combats, each seed's play-out `variant.with_seed(s)`
    (as `Combat.decode(bytes, seed)` plays it)."""
    spec = PLAYERS[player]
    ev = bench.load_evaluator(spec) if spec else None
    kw = {"limit": bench.LIMIT, "threads": threads}
    if player == "two":
        kw.update(TWO_TURN)
    if ev is not None:
        kw.update(evaluator=ev.evaluator, features=ev.features)
    res = sts.play_on([v.with_seed(s) for v in variants for s in seeds], **kw)
    n = len(seeds)
    return [[(bool(r["won"]), int(r["hp_end"])) for r in res[v * n:(v + 1) * n]] for v in range(len(variants))]


def selected(specs, skip=0, groups=None):
    """(position, spec) of the starts to play: from position `skip` on, in
    `groups` (default all); positions count over every start, as in --starts."""
    return [(n, s) for n, s in enumerate(specs) if n >= skip and (not groups or s["group"] in groups)]


def resolve_net(net):
    """`net` with a glob in its path (before any `@`) replaced by its one match, so a read
    can be queued before the learn that names its run folder (docs/specs/mechanic-count-curve.md)."""
    path, at, tail = net.partition("@")
    if "*" not in path:
        return net
    import glob
    hits = glob.glob(path)
    if len(hits) != 1:
        raise SystemExit(f"--net {path}: {len(hits)} matches, want 1: {hits}")
    return hits[0].replace(os.sep, "/") + at + tail


def play_cmd(args):
    if args.net:
        args.net = resolve_net(args.net)
        PLAYERS["one"] = args.net + "@hpb0.01"
    if args.two_net:
        PLAYERS["two"] = PLAYERS["product"] = args.two_net + "@hpe0.01"
    players = args.players.split(",")
    mods = args.mods.split(",") if args.mods else list(MODS)
    if args.mods == "gen-batch1":
        mods = GEN_BATCH1 + list(LADDER)
    if args.mods == "gen-wide":
        mods = list(WIDE)
    unknown = [m for m in mods if m not in ALL]
    if unknown:
        raise SystemExit(f"unknown modifiers {unknown}; known: {list(ALL)}")
    done = {"settings": {"product": args.product, "seeds": args.seeds, "two_seeds": args.two_seeds, "mods": mods},
            "rows": []}
    if args.net:
        done["settings"]["net"] = args.net
    if args.two_net:
        done["settings"]["two_net"] = args.two_net
    if any(m in GEN_ALL for m in mods):
        done["settings"]["gen_pack"] = sts.load_content(gen_pack())
    if any(m in FICKLE for m in mods):
        done["settings"]["fickle_pack"] = sts.load_content(fickle_pack())
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            done = json.load(f)
        done["settings"]["mods"] = sorted(set(done["settings"]["mods"]) | set(mods), key=list(ALL).index)
        if any(m in GEN_ALL for m in mods):
            done["settings"]["gen_pack"] = sts.load_content(gen_pack())
        if any(m in FICKLE for m in mods):
            done["settings"]["fickle_pack"] = sts.load_content(fickle_pack())
    with open(args.product, encoding="utf-8") as f:
        product = json.load(f)
    specs = ba.fights(product, args.starts)
    rows = {(r["i"], r["floor"]): r for r in done["rows"]}
    rng = np.random.default_rng(20261103)
    t0 = time.perf_counter()
    deep = []
    for n, spec in selected(specs, args.skip, args.groups.split(",") if args.groups else None):
        key = (spec["i"], spec["floor"])
        row = rows.get(key)
        if row is None:
            row = {k: spec[k] for k in ("i", "floor", "encounter", "group", "hp")}
            row.update({"parent": {}, "mods": {}})
            done["rows"].append(row)
            rows[key] = row
        for m in mods:
            row["mods"].setdefault(m, {})
        todo = [p for p in players if (p not in row["parent"] or any(p not in row["mods"][m] for m in mods))
                and (p not in DEEP or n < args.two_starts)]
        if not todo:
            continue
        c = start_state(spec)
        variants = [sts.Combat.decode(bytes(c.encode()))] + [variant(c, ALL[m]) for m in mods]
        seeds = [int(x) for x in np.random.default_rng([20261103, spec["i"], spec["floor"]]).integers(2**62, size=args.seeds)]
        for p in [p for p in todo if p == "product"]:
            # played after the loop in one pool, resumable from a partial file
            parts = [(bytes(c.encode()), [])] + [variant_parts(c, ALL[m]) for m in mods]
            deep.append((row, mods, [{"state": b.hex(), "seed": s, "powers": pw} for b, pw in parts
                                     for s in seeds[:args.two_seeds]]))
        for p in [p for p in todo if p != "product"]:
            ss = seeds[:args.two_seeds] if p in DEEP else seeds
            res = play_variants(variants, ss, p, args.threads)
            row["parent"][p] = res[0]  # replayed with the same seeds: identical to an earlier row's
            for m, r in zip(mods, res[1:]):
                row["mods"][m][p] = r
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(done, f)
        print(f"{n + 1} / {len(specs)} starts, {time.perf_counter() - t0:.0f} s", flush=True)
    del rng
    if deep:
        play_product(deep, done, mods, args)
    print(args.out)


def play_product(deep, done, mods, args):
    """The `product` player (the two-turn product's flags: line seed, stepped line;
    docs/specs/genpack-product-depth.md) on every start in `deep` ([(row, mods,
    specs)], parent first then each mod, `two_seeds` seeds each) in one process pool
    (depth_paired.run_guarded); finished fights go to `<out>.partial` as they end
    (the progress: lines of the total printed here), so a rerun plays only the rest;
    the partial file is deleted once the rows are written."""
    import depth_paired
    specs = [s for _, _, ss in deep for s in ss]
    content = ([gen_pack()] if any(m in GEN_ALL for m in mods) else []) + \
              ([fickle_pack()] if any(m in FICKLE for m in mods) else [])
    partial = args.out + ".partial"
    print(f"product: {len(specs)} fights on {len(deep)} starts, {args.threads} threads; progress: lines of {partial}",
          flush=True)
    res = depth_paired.run_guarded(specs, {"limit": bench.LIMIT, **TWO_TURN}, -1.0, PLAYERS["product"], args.threads,
                                   partial, seed_per_turn=True, step_line=True, content=content or None)
    k = 0
    for row, ms, ss in deep:
        n = len(ss) // (len(ms) + 1)
        got = [(bool(r["won"]), int(r["hp_end"])) for r in res[k:k + len(ss)]]
        k += len(ss)
        row["parent"]["product"] = got[:n]
        for j, m in enumerate(ms):
            row["mods"][m]["product"] = got[(j + 1) * n:(j + 2) * n]
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(done, f)
    os.remove(partial)


def outcome(res, hp):
    """(win rate, mean HP lost) over seeds; a loss costs the whole entry HP."""
    return float(np.mean([w for w, _ in res])), float(np.mean([hp - e if w else hp for w, e in res]))


def summary(rows, mods):
    """Per modifier: per player the win and HP-lost change from the parent
    (paired by start, mean and se), difficulty verdict, novelty cost
    (one - heuristic contrast) and depth repair (two - one contrast)."""
    out = {}
    for m in mods:
        s = {}
        for p in ("heuristic", "one", "two"):
            rs = [r for r in rows if p in r["parent"] and p in r["mods"].get(m, {})]
            if not rs:
                continue
            dw = [outcome(r["mods"][m][p], r["hp"])[0] - outcome(r["parent"][p], r["hp"])[0] for r in rs]
            dl = [outcome(r["mods"][m][p], r["hp"])[1] - outcome(r["parent"][p], r["hp"])[1] for r in rs]
            s[p] = {"n": len(rs), "win": ba.mean_se(dw), "lost": ba.mean_se(dl),
                    "win_parent": float(np.mean([outcome(r["parent"][p], r["hp"])[0] for r in rs])),
                    "win_mod": float(np.mean([outcome(r["mods"][m][p], r["hp"])[0] for r in rs]))}
        for a, b, key in (("one", "heuristic", "novelty"), ("two", "one", "repair")):
            rs = [r for r in rows if all(p in r["parent"] and p in r["mods"].get(m, {}) for p in (a, b))]
            if rs:
                d = [(outcome(r["mods"][m][a], r["hp"])[0] - outcome(r["mods"][m][b], r["hp"])[0])
                     - (outcome(r["parent"][a], r["hp"])[0] - outcome(r["parent"][b], r["hp"])[0]) for r in rs]
                s[key] = {"n": len(rs), "win": ba.mean_se(d)}
        parts = m.split("+")
        if len(parts) > 1 and all(x in MODS for x in parts):
            for p in ("heuristic", "two"):
                rs = [r for r in rows if p in r["parent"] and all(p in r["mods"].get(x, {}) for x in [m] + parts)]
                if rs:
                    win = lambda r, x: outcome(r["mods"][x][p], r["hp"])[0] - outcome(r["parent"][p], r["hp"])[0]  # noqa: E731
                    s.setdefault("stack", {})[p] = {"n": len(rs), "sum": float(np.mean([sum(win(r, x) for x in parts) for r in rs])),
                                                    "interaction": ba.mean_se([win(r, m) - sum(win(r, x) for x in parts) for r in rs])}
        s["verdict"] = verdict(s)
        out[m] = s
    return out


def verdict(s):
    """harder / easier when the heuristic (and the two-turn product, if
    read) move the same way beyond 2 se; level when neither does; else mixed."""
    signs = []
    for p in ("heuristic", "two"):
        if p in s:
            m, se = s[p]["win"]
            signs.append(0 if abs(m) <= 2 * se else (1 if m > 0 else -1))
    if not signs:
        return "-"
    if all(x == 0 for x in signs):
        return "level"
    if all(x <= 0 for x in signs) and any(x < 0 for x in signs):
        return "harder"
    if all(x >= 0 for x in signs) and any(x > 0 for x in signs):
        return "easier"
    return "mixed"


def read_cmd(args):
    with open(args.out, encoding="utf-8") as f:
        d = json.load(f)
    rows, mods = d["rows"], d["settings"]["mods"]
    fmt = lambda v: f"{v[0]:+.3f} ({v[1]:.3f})" if v else "-"  # noqa: E731

    def table(rs, title):
        s = summary(rs, mods)
        print(f"\n{title}: {len(rs)} starts; win change from the parent (se), paired by start")
        print(f"{'modifier':30s} {'heuristic':>16s} {'one-turn net':>16s} {'two-turn':>16s} {'verdict':8s} "
              f"{'novelty one-heur':>18s} {'repair two-one':>16s}")
        for m, v in s.items():
            cells = [fmt(v[p]["win"]) if p in v else "-" for p in ("heuristic", "one", "two")]
            nov = fmt(v["novelty"]["win"]) if "novelty" in v else "-"
            rep = fmt(v["repair"]["win"]) if "repair" in v else "-"
            print(f"{m:30s} {cells[0]:>16s} {cells[1]:>16s} {cells[2]:>16s} {v['verdict']:8s} {nov:>18s} {rep:>16s}")
        print("  HP lost change (heuristic / one / two): " + "; ".join(
            f"{m} " + " / ".join(f"{v[p]['lost'][0]:+.1f}" if p in v else "-" for p in ("heuristic", "one", "two"))
            for m, v in s.items()))
        for m, v in s.items():
            for p, st in v.get("stack", {}).items():
                print(f"  stack {m} ({p}, {st['n']} starts): win change {v[p]['win'][0]:+.3f} vs sum of parts "
                      f"{st['sum']:+.3f}, interaction {fmt(st['interaction'])}")
        return s
    out = {"all": table(rows, "all")}
    for g in sorted({r["group"] for r in rows}):
        out[g] = table([r for r in rows if r["group"] == g], g)
    for e in sorted({r["encounter"] for r in rows}):
        out[e] = table([r for r in rows if r["encounter"] == e], e)
    return out


def compare(base, burst):
    """Per modifier in both files: over starts where both played `one`,
    the burst's gain in novelty cost, (one_b - one_a)(mod) - (one_b -
    one_a)(parent) in win rate (mean, se); the base's novelty cost (one -
    heuristic contrast, from base); the share of that cost the gain cuts;
    and the parents' change one_b - one_a (mean, se)."""
    a = {(r["i"], r["floor"]): r for r in base["rows"]}
    out = {}
    for m in burst["settings"]["mods"]:
        if m not in base["settings"]["mods"]:
            continue
        pairs = [(a[(r["i"], r["floor"])], r) for r in burst["rows"]
                 if (r["i"], r["floor"]) in a and "one" in r["parent"] and "one" in r["mods"].get(m, {})
                 and "one" in a[(r["i"], r["floor"])]["parent"] and "one" in a[(r["i"], r["floor"])]["mods"].get(m, {})]
        if not pairs:
            continue
        w = lambda res, r: outcome(res, r["hp"])[0]  # noqa: E731
        gain = [(w(rb["mods"][m]["one"], rb) - w(ra["mods"][m]["one"], ra)) - (w(rb["parent"]["one"], rb) - w(ra["parent"]["one"], ra))
                for ra, rb in pairs]
        par = [w(rb["parent"]["one"], rb) - w(ra["parent"]["one"], ra) for ra, rb in pairs]
        nov = summary([ra for ra, _ in pairs], [m])[m].get("novelty")
        cost = nov["win"] if nov else None
        g = ba.mean_se(gain)
        out[m] = {"n": len(pairs), "gain": g, "cost": cost, "parent": ba.mean_se(par),
                  "cut": (g[0] / -cost[0]) if cost and cost[0] < 0 else None}
    return out


def compare_cmd(args):
    with open(args.base, encoding="utf-8") as f:
        base = json.load(f)
    with open(args.burst, encoding="utf-8") as f:
        burst = json.load(f)
    out = compare(base, burst)
    fmt = lambda v: f"{v[0]:+.3f} ({v[1]:.3f})" if v else "-"  # noqa: E731
    print(f"burst {burst['settings'].get('net', '-')} against base {base['settings'].get('net', 'the 10-29 net')}; win rate, se")
    print(f"{'modifier':30s} {'starts':>6s} {'base cost':>16s} {'burst gain':>16s} {'cut':>6s} {'parent change':>16s}")
    for m, v in out.items():
        cut = f"{v['cut']:.2f}" if v["cut"] is not None else "-"
        print(f"{m:30s} {v['n']:6d} {fmt(v['cost']):>16s} {fmt(v['gain']):>16s} {cut:>6s} {fmt(v['parent']):>16s}")
    return out


def mh_terms(rows, key, player):
    """Per start the Mantel-Haenszel terms of `player` against the
    heuristic on content `key` ("parent" or a modifier): a*d/n and b*c/n,
    a, b the player's wins and losses, c, d the heuristic's."""
    num, den = [], []
    for r in rows:
        res = r["parent"] if key == "parent" else r["mods"][key]
        a = sum(w for w, _ in res[player])
        b = len(res[player]) - a
        c = sum(w for w, _ in res["heuristic"])
        d = len(res["heuristic"]) - c
        n = a + b + c + d
        num.append(a * d / n)
        den.append(b * c / n)
    return np.array(num), np.array(den)


def odds(rows, mods, player="one", boot=2000, seed=0):
    """yardstick/novelty-read's odds-ratio column: per modifier the
    start-stratified (Mantel-Haenszel) log odds ratio of `player` against
    the heuristic, modified minus parent, bootstrap se over starts (the
    same resample for both); also the parent edge itself."""
    rows = [r for r in rows if player in r["parent"]]
    pn, pd = mh_terms(rows, "parent", player)
    w = np.random.default_rng(seed).multinomial(len(rows), [1 / len(rows)] * len(rows), size=boot).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        lpar, lpar_b = np.log(pn.sum() / pd.sum()), np.log((w @ pn) / (w @ pd))
        out = {"parent": {"n": len(rows), "lor": float(lpar), "se": float(np.nanstd(lpar_b[np.isfinite(lpar_b)]))}}
        for m in mods:
            rs = [i for i, r in enumerate(rows) if player in r["mods"].get(m, {})]
            if len(rs) < len(rows):
                continue
            mn, md = mh_terms(rows, m, player)
            d, d_b = np.log(mn.sum() / md.sum()) - lpar, np.log((w @ mn) / (w @ md)) - lpar_b
            ok = np.isfinite(d_b)
            out[m] = {"n": len(rows), "lor": float(d), "se": float(np.std(d_b[ok])),
                      "informative": int(((mn + md) > 0).sum())}
    return out


def odds_cmd(args):
    with open(args.out, encoding="utf-8") as f:
        d = json.load(f)
    rows, mods = d["rows"], d["settings"]["mods"]
    if args.base:  # a burst file plays only `one`: take the heuristic's games (same seeds) from the base file
        with open(args.base, encoding="utf-8") as f:
            b = {(r["i"], r["floor"]): r for r in json.load(f)["rows"]}
        rows = [r for r in rows if (r["i"], r["floor"]) in b]
        for r in rows:
            br = b[(r["i"], r["floor"])]
            r["parent"]["heuristic"] = br["parent"]["heuristic"]
            for m in r["mods"]:
                r["mods"][m]["heuristic"] = br["mods"][m]["heuristic"]
    if args.exclude:
        lo, hi = (int(x) for x in args.exclude.split("-"))
        rows = [r for r in rows if not lo <= r["i"] <= hi]
    out = {}
    for g in sorted({r["group"] for r in rows}):
        rs = [r for r in rows if r["group"] == g]
        o = odds(rs, mods, args.player)
        out[g] = o
        print(f"\n{g}: {o['parent']['n']} starts; log odds ratio of {args.player} against the heuristic (bootstrap se)")
        print(f"  parent edge {o['parent']['lor']:+.2f} ({o['parent']['se']:.2f})")
        for m in mods:
            if m in o:
                print(f"  {m:28s} {o[m]['lor']:+.2f} ({o[m]['se']:.2f})  {o[m]['informative']} informative starts")
    return out


def gen_table(rows, mods, net="one", group="elite"):
    """The generated enemies table (docs/specs/generated-enemies-bench.md):
    per mechanic in `mods`, the heuristic's and the net's wins and HP lost,
    its control (the ladder entry, parent included, nearest in the
    heuristic's mean HP lost; "outside" when every entry is more than 2 HP
    away) and the novelty cost (net - heur)(mech) - (net - heur)(control) in
    HP lost, paired by start; then the mean and se over mechanics."""
    ladder = ["parent"] + [m for m in LADDER if m in mods]
    mechs = [m for m in mods if m in GEN_ALL or m in FICKLE]
    res = lambda r, m, p: r["parent"][p] if m == "parent" else r["mods"][m][p]  # noqa: E731
    rs = [r for r in rows if r["group"] == group and all(
        p in r["parent"] and all(p in r["mods"].get(m, {}) for m in ladder[1:] + mechs) for p in ("heuristic", net))]
    out = {"n": len(rs), "mechanics": {}}
    if not rs or not mechs:
        return out
    lost = {(m, p): np.array([outcome(res(r, m, p), r["hp"])[1] for r in rs]) for m in ladder + mechs for p in ("heuristic", net)}
    won = {(m, p): np.array([outcome(res(r, m, p), r["hp"])[0] for r in rs]) for m in ladder + mechs for p in ("heuristic", net)}
    hl = {m: float(lost[(m, "heuristic")].mean()) for m in ladder + mechs}
    for m in mechs:
        c = min(ladder, key=lambda x: (abs(hl[x] - hl[m]), ladder.index(x)))
        gap = lambda x: (lost[(x, net)] - lost[(x, "heuristic")])  # noqa: E731
        out["mechanics"][m] = {
            "control": c, "outside": abs(hl[c] - hl[m]) > 2,
            "heur_lost": hl[m], "net_lost": float(lost[(m, net)].mean()),
            "heur_win": float(won[(m, "heuristic")].mean()), "net_win": float(won[(m, net)].mean()),
            "control_heur_lost": hl[c], "cost": ba.mean_se(gap(m) - gap(c)),
            "cost_parent": ba.mean_se(gap(m) - gap("parent")),
        }
    costs = [v["cost"] for v in out["mechanics"].values()]
    out["mean"] = ba.mean_se([c for c, _ in costs])
    out["beyond_2se"] = sum(abs(c) > 2 * se for c, se in costs)
    out["fail_fast"] = out["beyond_2se"] == 0
    return out


def read_gen_cmd(args):
    with open(args.out, encoding="utf-8") as f:
        d = json.load(f)
    rows, mods = d["rows"], d["settings"]["mods"]
    out = {}
    for title, rs in [("elite", rows)] + [(e, [r for r in rows if r["encounter"] == e])
                                           for e in sorted({r["encounter"] for r in rows if r["group"] == "elite"})]:
        t = gen_table(rs, mods, args.player)
        out[title] = t
        if not t.get("mechanics"):
            continue
        print(f"\n{title}: {t['n']} starts; HP lost (a loss costs the entry HP); novelty cost = "
              f"({args.player} - heuristic)(mechanic) - (same)(control), paired by start, mean (se)")
        print(f"{'mechanic':26s} {'heur win':>8s} {'net win':>8s} {'heur lost':>9s} {'net lost':>9s} "
              f"{'control':15s} {'ctl heur':>8s} {'cost':>15s} {'vs parent':>15s}")
        for m, v in t["mechanics"].items():
            ctl = v["control"] + (" (outside)" if v["outside"] else "")
            print(f"{m:26s} {v['heur_win']:8.3f} {v['net_win']:8.3f} {v['heur_lost']:9.2f} {v['net_lost']:9.2f} "
                  f"{ctl:15s} {v['control_heur_lost']:8.2f} {v['cost'][0]:+8.2f} ({v['cost'][1]:.2f}) "
                  f"{v['cost_parent'][0]:+8.2f} ({v['cost_parent'][1]:.2f})")
        print(f"  over {len(t['mechanics'])} mechanics: mean cost {t['mean'][0]:+.2f} ({t['mean'][1]:.2f}); "
              f"{t['beyond_2se']} beyond 2 se; fail-fast (all within 2 se): {t['fail_fast']}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("--starts", type=int, default=200)
    p.add_argument("--seeds", type=int, default=8)
    p.add_argument("--players", default="heuristic,one",
                   help="comma list of heuristic, one, two, product (two turns deep with the product's line seed "
                        "and stepped line)")
    p.add_argument("--two-starts", type=int, default=40)
    p.add_argument("--two-seeds", type=int, default=4)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--product", default=PRODUCT)
    p.add_argument("--mods", default="", help="comma list of MODS or GEN names to play (default: all MODS; gen-batch1: the first 8 mechanics and the ladder; gen-wide: the wider grid's 76)")
    p.add_argument("--net", default=None, help="the `one` player's net (<net>@hpb0.01); default the 10-29 net")
    p.add_argument("--two-net", default=None, help="the `two` player's net (<net>@hpe0.01, two turns deep); default the 10-29 net")
    p.add_argument("--skip", type=int, default=0, help="play only starts from this position on")
    p.add_argument("--groups", default="", help="comma list of fight groups to play (elite, boss; default all)")
    p.add_argument("--out", required=True)
    r = sub.add_parser("read")
    r.add_argument("out")
    c = sub.add_parser("compare")
    c.add_argument("base")
    c.add_argument("burst")
    o = sub.add_parser("odds")
    o.add_argument("out")
    o.add_argument("--player", default="one")
    o.add_argument("--exclude", default=None, help="lo-hi: drop starts whose index i is in this range")
    o.add_argument("--base", default=None, help="file to take the heuristic's games from (for a burst file)")
    g = sub.add_parser("read-gen")
    g.add_argument("out")
    g.add_argument("--player", default="one")
    args = ap.parse_args(argv)
    {"play": play_cmd, "read": read_cmd, "compare": compare_cmd, "odds": odds_cmd, "read-gen": read_gen_cmd}[args.cmd](args)


if __name__ == "__main__":
    main()
