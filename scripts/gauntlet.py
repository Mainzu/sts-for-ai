"""Act-1 gauntlet (docs/specs/gauntlet.md): seeded chains of 11 fights with
HP carried from fight to fight (the engine adds Burning Blood's heal on a
win; a rest site before the boss heals 30% of max HP). Goal 2's headline
number: the Act clear rate, paired between two agents by sequence.

    .venv/Scripts/python scripts/gauntlet.py play heuristic --sequences 200 --threads 6
    .venv/Scripts/python scripts/gauntlet.py play runs/<net>/model.pt@hpb0.01 --sequences 200 --threads 6 [--two-turn [--one-turn-floors 3] [--line-seed [--step-line]]]
    .venv/Scripts/python scripts/gauntlet.py play <player> --rewards {skip,random,sim} [--start {cell,starter}] [--sim-boss] [--chooser <player>]
    .venv/Scripts/python scripts/gauntlet.py play <player> --rewards vrun --fit results/gauntlet/<file>.json [--fit-first 250 --fit-n 250]
    .venv/Scripts/python scripts/gauntlet.py play <net> --rewards value [--value-hands 4] [--chooser <net>]
    .venv/Scripts/python scripts/gauntlet.py play <player> ... --rest sim  (heal or upgrade before the boss)
    .venv/Scripts/python scripts/gauntlet.py play <player> ... --remove {strike,sim}  (one removal after the first elite)
    .venv/Scripts/python scripts/gauntlet.py play <player> ... --elites {skip,hp} [--elite-hp 40]  (a hard hallway instead of an elite)
    .venv/Scripts/python scripts/gauntlet.py play <player> ... --against results/gauntlet/<control>.json [--vary remove]  (stops when the protocol decides)
    .venv/Scripts/python scripts/gauntlet.py read results/gauntlet/<a>.json results/gauntlet/<b>.json

Card rewards (docs/specs/card-rewards.md): after each won fight before the
boss, 3 seeded offers from the half's pool; a chooser adds one card or none.
"""

import argparse
import hashlib
import json
import os
import re
import sys

# The engine's search recurses once per action and chance event of a line
# of play; long turns overflowed the 2 MB default thread stack (job 0975).
os.environ.setdefault("RUST_MIN_STACK", str(64 << 20))

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "analysis"))

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "gauntlet")
GAUNTLET_SEED = 20261101
SEED_BASE = 9 * 10**15  # clear of tight2 (2e15), the ladder (7e15) and run-HP blocks
EASY = ("cultist", "jaw_worm", "two_louse", "small_slimes")
HARD = ("large_slime", "lots_of_slimes", "three_louse", "two_fungi_beasts", "exordium_thugs",
        "exordium_wildlife", "looter")
ELITES = ("gremlin_nob", "lagavulin", "three_sentries")
BOSSES = ("slime_boss", "hexaghost", "the_guardian")
SHAPE = ("easy",) * 3 + ("hard",) * 2 + ("elite",) + ("hard",) * 2 + ("elite",) + ("hard",) + ("boss",)
POOLS = {"easy": EASY, "hard": HARD, "elite": ELITES, "boss": BOSSES}
GROUP = {"easy": "hallway", "hard": "hallway", "elite": "elite", "boss": "boss"}
# settings fields a read --against a control may test (--vary); seed and shape pick the sequences and must match
VARY = ("price", "two_turn", "one_turn_floors", "line_seed", "step_line", "rest", "rewards", "start", "sim_boss",
        "chooser", "fit", "rest_choice", "remove", "elites", "elite_hp", "elite_offers", "mid_rest", "value_hands",
        "pack", "pack_picks", "ascension")
REST = 0.3
MAX_HP = 80


def run_max_hp(ascension=0):
    """The Ironclad run's max HP at an ascension level (80 at A0, 75 at A20)."""
    if not ascension:
        return MAX_HP
    import sts
    return sts.run_start("ironclad", ascension)["max_hp"]
HALVES = ("train", "held_out")


def pack_hard(pack):
    """(replaces {official HARD name: gen:<id>}, added [gen:<id>]) of a pack's
    hallway encounters (docs/specs/gauntlet-pack-encounters.md); None
    without any."""
    encs = [e for e in (pack or {}).get("encounters", []) if e.get("group") == "hallway"]
    if not encs:
        return None
    rep, add = {}, []
    for e in encs:
        name = e["id"].lower().replace(" ", "_")
        if name in HARD:
            rep[name] = "gen:" + e["id"]
        else:
            add.append("gen:" + e["id"])
    return rep, add


def hard_swap(i, k, enc, prev, hard, n_official):
    """A hard floor's official draw `enc` with a pack's hallway encounters:
    on stream (i, 2000 + k), an added one with probability added / (added +
    the floor's official pool), else the official one or its pack version."""
    if hard is None:
        return enc
    rep, add = hard
    pool = [e for e in add if e != prev]
    rng = np.random.default_rng([GAUNTLET_SEED, i, 2000 + k])
    if pool and rng.random() < len(add) / (len(add) + n_official):
        return pool[int(rng.integers(len(pool)))]
    return rep.get(enc, enc)


def sequences(n, first=0, cells=None, pack=None):
    """Sequences first..first+n-1: half, deck cell and 11 fights each; a
    pack's hallway encounters join the hard floors (pack_hard)."""
    hard = pack_hard(pack)
    if cells is None:
        import ladder
        cells = ladder.pool_cells()
    by_half = {h: [c for c in cells if c["half"] == h] for h in HALVES}
    out = []
    for i in range(first, first + n):
        rng = np.random.default_rng([GAUNTLET_SEED, i])
        half = HALVES[i % 2]
        cell = by_half[half][int(rng.integers(len(by_half[half])))]
        fights, prev, drawn, elites = [], None, None, set()
        for k, kind in enumerate(SHAPE):
            pool = [e for e in POOLS[kind] if e != drawn and e not in elites]
            enc = drawn = pool[int(rng.integers(len(pool)))]
            if kind == "hard":
                enc = hard_swap(i, k, enc, prev, hard, len(pool))
            if kind == "elite":
                elites.add(enc)
            fights.append({"kind": kind, "group": GROUP[kind], "encounter": enc, "seed": SEED_BASE + i * 100 + k})
            prev = enc
        out.append({"i": i, "half": half, "cell": cell["cell"], "deck": cell["deck"],
                    "character": cell["character"], "fights": fights})
    return out


def rest(hp, max_hp=MAX_HP):
    return min(max_hp, hp + int(REST * max_hp))


def base_name(name):
    """A card name without its level marks (sts.base_name: `Bash+` ->
    `Bash`, `gen:Searing Blow+3` -> `gen:Searing Blow`)."""
    import sts
    return sts.base_name(name)


def upgrade(deck, name):
    """`deck` with its first `name` upgraded once (`Bash` -> `Bash+`,
    `gen:Searing Blow+` -> `gen:Searing Blow+2`; sts.upgrade_name)."""
    import sts
    d = list(deck)
    d[d.index(name)] = sts.upgrade_name(name)
    return d


def run(seqs, play, max_hp=MAX_HP, reward=None, rest_hook=None, remove_hook=None, path_hook=None,
        elite_offers=1, mid_rest=None, starts=None):
    """Plays `seqs` floor by floor: `play(specs)` returns {won, hp_start,
    hp_end} per spec, all still-alive sequences' floor k in one call.
    Returns per sequence its floors played. `reward(k, items)`, if given, is
    called after each non-boss floor k with (sequence, HP, deck) of every
    sequence that won it and returns (offer, took) for each; a taken card
    joins that sequence's deck, and the floor row records offer and took.
    `rest_hook(items)`, if given, is called before the boss with the same
    items and returns per sequence None (heal) or a card name to upgrade
    instead (docs/specs/rest-site.md); the boss row records it as "rest".
    `remove_hook(items)`, if given, is called after floor REMOVE_FLOOR's
    reward and returns per sequence None (keep) or a card name to remove
    (docs/specs/card-removal.md); that floor's row records it as "removed".
    `path_hook(k, items)`, if given, is called at each elite floor k with the
    same items and returns per sequence True (fight the elite) or False
    (fight `alt_fight`'s hard hallway instead, docs/specs/elite-skip.md);
    the row records "path" as "elite" or "hallway".
    Mini-run (docs/specs/mini-run.md): after a won elite fight (not a
    skipped one) `reward(k, items, j)` runs again for j = 1..elite_offers-1,
    the row's "extra" lists those (offer, took); `mid_rest` K heals by
    rest() after floor K is won, before its reward, recorded as "mid_rest".
    `starts` ({i: (hp, max HP)}, docs/specs/ascension.md) starts sequence i
    there instead of at `max_hp`."""
    top = {s["i"]: starts[s["i"]][1] if starts else max_hp for s in seqs}
    hp = {s["i"]: starts[s["i"]][0] if starts else max_hp for s in seqs}
    floors = {s["i"]: [] for s in seqs}
    deck = {s["i"]: list(s["deck"]) for s in seqs}
    alive = list(seqs)
    for k in range(len(SHAPE)):
        if not alive:
            break
        choice, path = {}, {}
        if SHAPE[k] == "boss" and rest_hook is not None:
            choice = dict(zip([s["i"] for s in alive],
                              rest_hook([(s, hp[s["i"]], list(deck[s["i"]])) for s in alive])))
        if SHAPE[k] == "elite" and path_hook is not None:
            path = dict(zip([s["i"] for s in alive],
                            path_hook(k, [(s, hp[s["i"]], list(deck[s["i"]])) for s in alive])))
        specs = []
        for s in alive:
            f = s["fights"][k]
            if path.get(s["i"]) is False:
                f = {**f, "encounter": alt_fight(s["i"], k, s["fights"][k - 1]["encounter"]), "group": "hallway"}
            if f["kind"] == "boss":
                if choice.get(s["i"]) is None:
                    hp[s["i"]] = rest(hp[s["i"]], top[s["i"]])
                else:
                    deck[s["i"]] = upgrade(deck[s["i"]], choice[s["i"]])
            specs.append({"encounter": f["encounter"], "deck": list(deck[s["i"]]), "seed": f["seed"], "hp": hp[s["i"]],
                          "character": s["character"], "group": f["group"]})
        res = play(specs)
        nxt = []
        for s, spec, r in zip(alive, specs, res):
            won = bool(r["won"])
            floors[s["i"]].append({"encounter": spec["encounter"], "hp_start": spec["hp"],
                                   "hp_end": int(r["hp_end"]) if won else 0, "won": won})
            if s["i"] in choice:
                floors[s["i"]][-1]["rest"] = choice[s["i"]] or "heal"
            if s["i"] in path:
                floors[s["i"]][-1]["path"] = "elite" if path[s["i"]] else "hallway"
            if won:
                hp[s["i"]] = min(top[s["i"]], int(r["hp_end"]))
                if k == mid_rest:
                    hp[s["i"]] = rest(hp[s["i"]], top[s["i"]])
                    floors[s["i"]][-1]["mid_rest"] = hp[s["i"]]
                nxt.append(s)
        if reward is not None and SHAPE[k] != "boss" and nxt:
            for s, r in zip(nxt, reward(k, [(s, hp[s["i"]], list(deck[s["i"]])) for s in nxt])):
                offer, took = r[0], r[1]  # (offer, took[, extra row fields])
                floors[s["i"]][-1].update({"offer": list(offer), "took": took, **(r[2] if len(r) > 2 else {})})
                if took is not None:
                    deck[s["i"]].append(took)
            paid = [s for s in nxt if SHAPE[k] == "elite" and path.get(s["i"]) is not False]
            for j in range(1, elite_offers):
                if not paid:
                    break
                for s, r in zip(paid, reward(k, [(s, hp[s["i"]], list(deck[s["i"]])) for s in paid], j)):
                    floors[s["i"]][-1].setdefault("extra", []).append({"offer": list(r[0]), "took": r[1]})
                    if r[1] is not None:
                        deck[s["i"]].append(r[1])
        if remove_hook is not None and k == REMOVE_FLOOR and nxt:
            for s, name in zip(nxt, remove_hook([(s, hp[s["i"]], list(deck[s["i"]])) for s in nxt])):
                floors[s["i"]][-1]["removed"] = name
                if name is not None:
                    deck[s["i"]] = remove(deck[s["i"]], name)
        alive = nxt
    return [{"i": s["i"], "half": s["half"], "cell": s["cell"], "floors": floors[s["i"]],
             "cleared": len(floors[s["i"]]) == len(SHAPE) and floors[s["i"]][-1]["won"]} for s in seqs]


# settings a --match file must share: they make the choices it records (docs/specs/deck-matched-reads.md)
MATCH_FIELDS = ("pack", "pack_picks", "rewards", "sim_boss", "chooser", "fit", "value_hands", "rest_choice", "remove", "elite_offers", "elites",
                "elite_hp", "mid_rest", "start", "rest")


def matched(rows, reward=None, rest_hook=None, remove_hook=None):
    """Wraps run()'s hooks so each sequence takes the choices recorded in the
    gauntlet rows `rows` (card picks, extra elite picks, the rest choice, the
    removal) where they hold one, and asks the wrapped hook for the rest;
    a matched card pick's floor row gets "matched": True
    (docs/specs/deck-matched-reads.md). Returns (reward, rest_hook, remove_hook)."""
    rec = {r["i"]: r["floors"] for r in rows}

    def floor(s, k):
        f = rec.get(s["i"], [])
        return f[k] if k < len(f) else {}

    def split(items, get, hook):
        got = [get(it) for it in items]
        ask = [it for it, g in zip(items, got) if g is None]
        rest = iter(hook(ask) if ask else [])
        return [next(rest) if g is None else g[0] for g in got]

    def get_pick(k, j):
        def get(it):
            f = floor(it[0], k)
            if j == 0:
                return ((f["offer"], f["took"], {"matched": True}),) if "offer" in f else None
            x = f.get("extra", [])
            return ((x[j - 1]["offer"], x[j - 1]["took"]),) if j <= len(x) else None
        return get

    def get_rest(it):
        f = floor(it[0], len(SHAPE) - 1)
        return (None if f["rest"] == "heal" else f["rest"],) if "rest" in f else None

    def get_removed(it):
        f = floor(it[0], REMOVE_FLOOR)
        return (f["removed"],) if "removed" in f else None
    return (reward and (lambda k, items, j=0: split(items, get_pick(k, j), lambda a: reward(k, a, j))),
            rest_hook and (lambda items: split(items, get_rest, rest_hook)),
            remove_hook and (lambda items: split(items, get_removed, remove_hook)))


STARTER_NAMES = ("Strike", "Defend", "Bash")
OFFER = 3
SIM_FIGHTS = 8
SIM_SEED_BASE = 95 * 10**14  # 9.5e15: clear of the fights' 9e15 + i * 100 + k block


def reward_pools(cells):
    """{half: sorted base names of the non-starter cards in that half's cells}."""
    out = {h: set() for h in HALVES}
    for c in cells:
        out[c["half"]] |= {base_name(n) for n in c["deck"] if base_name(n) not in STARTER_NAMES}
    return {h: sorted(v) for h, v in out.items()}


def base_ids(pack):
    """A pack's card ids that are cards of their own, in file order: not an
    entry named as another's `successor`, nor (an older file) `X+` beside
    an `X` (docs/specs/card-upgrades.md, Amendment 1)."""
    cards = (pack or {}).get("cards", [])
    ids = {c["id"] for c in cards}
    levels = {c["successor"] for c in cards if "successor" in c}
    old = {c["id"] for c in cards if c["id"].endswith("+") and c["id"][:-1] in ids}
    return [c["id"] for c in cards if c["id"] not in levels | old]


def pack_pools(pools, pack):
    """`pools` with a loaded content pack's base cards (ids without a
    trailing "+") added to every half as gen:<id> (docs/specs/gauntlet-pack-offers.md)."""
    if pack is None:
        return pools
    extra = ["gen:" + i for i in base_ids(pack)]
    return {h: sorted(set(v) | set(extra)) for h, v in pools.items()}


def pack_names(pack):
    """The pools' names of a loaded pack's base cards (gen:<id>), the cards
    --pack-picks originals bars the chooser from (docs/specs/pack-pick-split.md)."""
    return frozenset("gen:" + i for i in base_ids(pack))


def offer(i, k, pool, j=0):
    """Sequence i's offer after floor k: OFFER distinct names, independent of
    the player and of earlier choices; j >= 1 is an elite's extra offer
    (docs/specs/mini-run.md)."""
    rng = np.random.default_rng([GAUNTLET_SEED, i, 1000 + k] + ([j] if j else []))
    return [str(x) for x in rng.choice(pool, OFFER, replace=False)]


def chooser(kind, pools, sim_play=None, max_hp=MAX_HP, boss=False, unit=None, value=None, hands=1, barred=frozenset()):
    """A reward hook for run(): kind skip / random / sim (docs/specs/card-rewards.md);
    the chooser may take skip or an offered card not in `barred`; the row keeps
    the full offer (docs/specs/pack-pick-split.md);
    `boss` adds the boss pool to the sim chooser's horizon (docs/specs/sim-boss.md);
    `vrun` scores options by the run value `unit` (docs/specs/run-value-chooser.md);
    `value` by the net values `value` of start states (docs/specs/value-chooser.md)."""
    def hook(k, items, j=0):
        full = [offer(s["i"], k, pools[s["half"]], j) for s, _, _ in items]
        if not barred:
            return pick(k, items, full, j)
        took = pick(k, items, [[c for c in o if c not in barred] for o in full], j)
        return [(o, t) for o, (_, t) in zip(full, took)]

    def pick(k, items, offers, j):
        if kind == "skip":
            return [(o, None) for o in offers]
        if kind == "random":
            return [(o, o[int(np.random.default_rng([GAUNTLET_SEED, s["i"], 2000 + k]).integers(len(o)))] if o else None)
                    for (s, _, _), o in zip(items, offers)]
        if kind == "vrun":
            return vrun_choose(k, items, offers, sim_play, unit, max_hp)
        if kind == "value":
            return value_choose(k, items, offers, value, max_hp, hands)
        return sim_choose(k, items, offers, sim_play, max_hp, boss)

    def scores(k, items, j=0):
        """Per item {offer, options (None = skip, then the cards), scores (None
        for skip / random), pick}: the scores the hook chooses by, from the same
        functions (docs/specs/explorer-v2.md); options hold only the cards the
        hook may take."""
        full = [offer(s["i"], k, pools[s["half"]], j) for s, _, _ in items]
        rows = scored(k, items, [[c for c in o if c not in barred] for o in full], j)
        for r, o in zip(rows, full):
            r["offer"] = o
        return rows

    def scored(k, items, offers, j):
        if kind in ("skip", "random"):
            return [{"offer": o, "options": [None] + o, "scores": None, "pick": t}
                    for o, (_, t) in zip(offers, pick(k, items, offers, j))]
        if kind == "vrun":
            per = vrun_offer_scores(k, items, offers, sim_play, unit, max_hp)
            return [{"offer": o, "options": [None] + o, "scores": sc, "sim_scores": old, "pick": first_max(o, sc)}
                    for o, (sc, old) in zip(offers, per)]
        per = (value_offer_scores(k, items, offers, value, max_hp, hands) if kind == "value"
               else sim_offer_scores(k, items, offers, sim_play, max_hp, boss))
        return [{"offer": o, "options": [None] + o, "scores": sc, "pick": first_max(o, sc)}
                for o, sc in zip(offers, per)]
    hook.scores = scores
    return hook


def first_max(options, scores):
    """The choosers' pick: the first maximum of `scores` (index 0 = skip,
    keep or heal, so it wins ties), as the option name or None."""
    best = int(np.argmax(scores))
    return None if best == 0 else options[best - 1]


VALUE_ELITE_OFF = 70  # the elites part's seed offset (the sim chooser uses 0 and 50, vrun 90)
VALUE_HAND_STEP = 7919  # --value-hands: hand h of a start state uses seed + h x this


def value_parts(k, s, hp, max_hp=MAX_HP):
    """The value chooser's horizon after floor k (docs/specs/value-chooser.md):
    parts of (encounter, seed, hp, group): the next floor (the sim chooser's
    draw and seeds), each elite while an elite floor lies after the next floor,
    and the sequence's own boss at the post-rest HP unless the next floor is it."""
    nxt = SHAPE[k + 1]
    rng = np.random.default_rng([GAUNTLET_SEED, s["i"], 3000 + k])
    draw = [str(e) for e in rng.choice(POOLS[nxt], SIM_FIGHTS)]
    if nxt == "boss":
        draw = [s["fights"][-1]["encounter"]] * SIM_FIGHTS
    base = SIM_SEED_BASE + s["i"] * 10_000 + k * 100
    start = rest(hp, max_hp) if nxt == "boss" else hp
    parts = [[(e, base + m, start, GROUP[nxt]) for m, e in enumerate(draw)]]
    if any(SHAPE[e] == "elite" for e in range(k + 2, len(SHAPE))):
        parts.append([(e, base + VALUE_ELITE_OFF + m, hp, "elite") for m, e in enumerate(ELITES)])
    if nxt != "boss":
        parts.append([(s["fights"][-1]["encounter"], base + 90 + m, rest(hp, max_hp), "boss")
                      for m in range(SIM_FIGHTS)])
    return parts


def value_choose(k, items, offers, value, max_hp=MAX_HP, hands=1):
    """Each option (skip, or one offered card added) scored by the sum over
    value_parts of the mean of `value(specs)` (net values of start states,
    each averaged over `hands` dealt hands); the same states for every
    option; ties go to skip (then to the earlier card). One call for all."""
    return [(o, first_max(o, sc)) for o, sc in zip(offers, value_offer_scores(k, items, offers, value, max_hp, hands))]


def value_offer_scores(k, items, offers, value, max_hp=MAX_HP, hands=1):
    """value_choose's scores: per item, skip's then each offered card's."""
    specs, shape = [], []
    for (s, hp, deck), o in zip(items, offers):
        parts = value_parts(k, s, hp, max_hp)
        shape.append([len(p) for p in parts])
        for d in [deck] + [deck + [c] for c in o]:
            for p in parts:
                for e, seed, start, group in p:
                    specs += [{"encounter": e, "deck": d, "seed": seed + VALUE_HAND_STEP * h, "hp": start,
                               "character": s["character"], "group": group} for h in range(hands)]
    v = np.asarray(value(specs) if specs else [], np.float64)
    out, j = [], 0
    for o, lens in zip(offers, shape):
        scores = []
        for _ in range(len(o) + 1):
            score = 0.0
            for n in lens:
                score += float(v[j:j + n * hands].mean())
                j += n * hands
            scores.append(score)
        out.append(scores)
    return out


def net_values(player, threads=1):
    """value(specs) for value_choose: the static value of each spec's start
    state (`sts.Combat`, opening hand dealt) under net `player`'s `.pt` file;
    its `@` settings act at search leaves and are dropped."""
    import bench
    import sts
    import stsnet
    import torch
    base = bench.player_settings(player)[0]
    if not base.endswith(".pt"):
        raise SystemExit(f"--rewards value needs a net (.pt) chooser, not {player}")
    torch.set_num_threads(max(1, threads))
    model, norm, meta = stsnet.load(base)
    feats, ev = stsnet.features_for(meta), stsnet.Evaluator(model, norm)

    def value(specs):
        out = []
        for b in range(0, len(specs), 4096):
            cs = [sts.Combat(sp["deck"], sp["encounter"], seed=sp["seed"], hp=sp["hp"], character=sp["character"],
                             ascension=sp.get("ascension", 0))
                  for sp in specs[b:b + 4096]]
            out.append(np.asarray(ev(feats.encode(cs, heuristic=True)), np.float64))
        return np.concatenate(out)
    return value


def sim_choose(k, items, offers, sim_play, max_hp=MAX_HP, boss=False):
    """Each option (skip, or one offered card added) scored by SIM_FIGHTS
    one-turn fights against the next floor's pool at the HP that fight would
    start at (after the rest before the boss); the same encounters and seeds
    for every option. Score = mean won x (1 + 0.01 x end HP); the best is
    taken, ties go to skip (then to the earlier card). All sequences'
    option fights go to sim_play in one call. With `boss` (and the next
    floor not the boss) each option also gets SIM_FIGHTS fights against the
    boss pool at the post-rest HP, and its score is the sum of both means."""
    return [(o, first_max(o, sc)) for o, sc in zip(offers, sim_offer_scores(k, items, offers, sim_play, max_hp, boss))]


def sim_offer_scores(k, items, offers, sim_play, max_hp=MAX_HP, boss=False):
    """sim_choose's scores: per item, skip's then each offered card's."""
    decks = [[deck] + [deck + [c] for c in o] for (_, _, deck), o in zip(items, offers)]
    return sim_scores(k, items, decks, sim_play, max_hp, boss)


def sim_fights(k, items, decks, sim_play, max_hp=MAX_HP, boss=False, streams=((3000, 0), (4000, 50)), bosses=None):
    """The option fights behind sim_scores: per item, per deck in
    `decks[item]`, per horizon part (the next floor, then the boss part if
    `boss` and the next floor isn't the boss), that part's SIM_FIGHTS
    results {won, hp_start, hp_end}, the same encounters and seeds for every
    deck. `streams` gives the (encounter stream, seed offset) of the two
    parts, so other choosers on the same floor draw other fights. `bosses`
    (per item) replaces a boss part's pool draw by that encounter
    (docs/specs/run-value-chooser.md: the sequence's own boss)."""
    nxt = SHAPE[k + 1]
    horizon = [(nxt,) + streams[0]] + ([("boss",) + streams[1]] if boss and nxt != "boss" else [])
    specs = []
    for n, ((s, hp, _), ds) in enumerate(zip(items, decks)):
        fights = []
        for kind, stream, off in horizon:
            rng = np.random.default_rng([GAUNTLET_SEED, s["i"], stream + k])
            start = rest(hp, max_hp) if kind == "boss" else hp
            draw = [str(e) for e in rng.choice(POOLS[kind], SIM_FIGHTS)]
            if kind == "boss" and bosses is not None:
                draw = [bosses[n]] * SIM_FIGHTS
            fights += [(e, SIM_SEED_BASE + s["i"] * 10_000 + k * 100 + off + m, start, GROUP[kind])
                       for m, e in enumerate(draw)]
        for d in ds:
            for e, seed, start, group in fights:
                specs.append({"encounter": e, "deck": d, "seed": seed,
                              "hp": start, "character": s["character"], "group": group})
    res = sim_play(specs) if specs else []
    out, j = [], 0
    for ds in decks:
        per_deck = []
        for _ in ds:
            parts = []
            for _ in horizon:
                parts.append(res[j * SIM_FIGHTS:(j + 1) * SIM_FIGHTS])
                j += 1
            per_deck.append(parts)
        out.append(per_deck)
    return out


def sim_score(parts):
    """The sim chooser's score of one option: per part mean won x (1 + 0.01 x end HP), summed."""
    return sum(float(np.mean([bool(r["won"]) * (1 + 0.01 * float(r["hp_end"] or 0)) for r in rs])) for rs in parts)


def sim_scores(k, items, decks, sim_play, max_hp=MAX_HP, boss=False, streams=((3000, 0), (4000, 50))):
    """sim_choose's scoring over option decks: per item, the score of each
    deck in `decks[item]` on the same horizon fights (sim_fights)."""
    return [[sim_score(parts) for parts in per_deck]
            for per_deck in sim_fights(k, items, decks, sim_play, max_hp, boss, streams)]


VRUN_STREAMS = ((3000, 0), (7000, 90))  # the sim chooser's next-floor fights; a boss part of its own


def vrun_choose(k, items, offers, sim_play, unit, max_hp=MAX_HP):
    """Run-value chooser (docs/specs/run-value-chooser.md): the sim
    chooser's next-floor fights plus 8 fights against the sequence's own
    boss, each option scored by `unit.score` (P(reach the boss at h) x
    P(win | h, deck)); ties go to skip. Returns (offer, took, {"took_sim":
    the old score's pick on the same fights})."""
    return [(o, first_max(o, sc), {"took_sim": first_max(o, old)})
            for o, (sc, old) in zip(offers, vrun_offer_scores(k, items, offers, sim_play, unit, max_hp))]


def vrun_offer_scores(k, items, offers, sim_play, unit, max_hp=MAX_HP):
    """vrun_choose's scores: per item (run-value scores, the sim score on
    the same fights), each skip's then each offered card's."""
    decks = [[deck] + [deck + [c] for c in o] for (_, _, deck), o in zip(items, offers)]
    bosses = [s["fights"][-1]["encounter"] for s, _, _ in items]
    out = []
    for (s, hp, _), boss, per_deck in zip(items, bosses,
                                         sim_fights(k, items, decks, sim_play, max_hp, True, VRUN_STREAMS, bosses)):
        out.append(([unit.score(k, hp, boss, parts, max_hp) for parts in per_deck],
                    [sim_score(parts) for parts in per_deck]))
    return out


REMOVE_FLOOR = 5  # after the first elite's reward: a shop proxy (docs/specs/card-removal.md)


def remove_strike(items):
    """Removal rule: the first Strike (or Strike+), else keep."""
    return [next((c for c in deck if base_name(c) == "Strike"), None) for _, _, deck in items]


def remove_sim(k, items, sim_play, max_hp=MAX_HP, boss=False):
    """Removal chooser: keep, or remove the first copy of one of the deck's
    distinct names, each option scored as sim_choose scores (on its own
    fights: streams 5000 / 6000, offsets 70 / 80); ties keep."""
    return [first_max(ns, sc) for ns, sc in remove_scores(k, items, sim_play, max_hp, boss)]


def remove_scores(k, items, sim_play, max_hp=MAX_HP, boss=False):
    """remove_sim's options and scores: per item (the deck's distinct names,
    [keep's score, then each name's removal's])."""
    names = [list(dict.fromkeys(deck)) for _, _, deck in items]
    decks = [[deck] + [remove(deck, n) for n in ns] for (_, _, deck), ns in zip(items, names)]
    return list(zip(names, sim_scores(k, items, decks, sim_play, max_hp, boss, ((5000, 70), (6000, 80)))))


def remove(deck, name):
    """`deck` without its first `name`."""
    d = list(deck)
    del d[d.index(name)]
    return d


def alt_fight(i, k, prev):
    """The hard hallway sequence i fights at elite floor k when it skips the
    elite (docs/specs/elite-skip.md): drawn from HARD minus the previous
    floor's encounter, from (i, k) only, so every player meets the same one."""
    pool = [e for e in HARD if e != prev]
    return pool[int(np.random.default_rng([GAUNTLET_SEED, i, 5000 + k]).integers(len(pool)))]


def path_skip(k, items):
    """Path rule: never fight an elite (the ceiling of a path choice here)."""
    return [False] * len(items)


def path_hp(threshold):
    """Path rule: fight the elite at `threshold` HP or more, else the hallway."""
    return lambda k, items: [hp >= threshold for _, hp, _ in items]


REST_FIGHTS = 16


def upgradable(deck):
    """Distinct names in `deck` with an upgrade, in first-occurrence order:
    an official card whose `+` is a deck card (sts.deck_card_names, as
    before upgrades as data: held-out cards are never upgraded here), a pack
    card that a general upgrade raises (below its max level, no status)."""
    import sts
    names = set(sts.deck_card_names())

    def can(c):
        if c.startswith("gen:"):
            return sts.upgrade_name(c) is not None
        return not c.endswith("+") and c + "+" in names
    return [c for c in dict.fromkeys(deck) if can(c)]


def rest_choose(items, sim_play, max_hp=MAX_HP, fights=REST_FIGHTS, margin=0.0):
    """Rest-site chooser (docs/specs/rest-site.md): heal, or upgrade one of
    the deck's upgradable cards, each option scored by REST_FIGHTS one-turn
    fights against the sequence's own boss on the same seeds, as sim_choose
    scores (first maximum: heal wins ties). With margin z > 0 the best
    upgrade must beat heal by z standard errors of its paired per-seed score
    difference, else heal (the winner's-curse guard; decisions "Rest probe:
    64 fights and a 2-se margin"). Returns per item None (heal) or the name
    to upgrade."""
    return [rest_pick(names, per, fights, margin) for names, per in rest_scores(items, sim_play, max_hp, fights)]


def rest_pick(names, per, fights=REST_FIGHTS, margin=0.0):
    """rest_choose's pick from one item's rest_scores: None (heal) or a name."""
    if not names:
        return None
    best = int(np.argmax([float(x.mean()) for x in per]))
    if best and margin > 0:
        d = per[best] - per[0]
        if d.mean() <= margin * d.std(ddof=1) / np.sqrt(fights):
            best = 0
    return None if best == 0 else names[best - 1]


def rest_scores(items, sim_play, max_hp=MAX_HP, fights=REST_FIGHTS):
    """rest_choose's options and per-seed scores: per item (upgradable
    names, [heal's array, then each upgrade's]); no names: ([], [])."""
    specs, opts = [], []
    for s, hp, deck in items:
        names = upgradable(deck)
        o = [(rest(hp, max_hp), deck)] + [(hp, upgrade(deck, n)) for n in names] if names else []
        boss = s["fights"][-1]["encounter"]
        base = SIM_SEED_BASE + s["i"] * 10_000 + 1000
        for h, d in o:
            specs += [{"encounter": boss, "deck": d, "seed": base + m, "hp": h,
                       "character": s["character"], "group": "boss"} for m in range(fights)]
        opts.append(names)
    res = sim_play(specs) if specs else []
    out, j = [], 0
    for names in opts:
        per = []
        for _ in range(len(names) + 1 if names else 0):
            rs = res[j * fights:(j + 1) * fights]
            per.append(np.array([bool(r["won"]) * (1 + 0.01 * float(r["hp_end"] or 0)) for r in rs]))
            j += 1
        out.append((names, per))
    return out


def rest_label(rest, fights=REST_FIGHTS, margin=0.0):
    """The settings' rest_choice label of --rest / --rest-fights / --rest-margin
    (the defaults keep the older label "sim")."""
    return rest + (f"-f{fights}-m{margin:g}" if (fights, margin) != (REST_FIGHTS, 0.0) else "")


def parse_rest_label(label):
    """(fights, margin) of a rest_choice label ("sim" or "sim-f<k>-m<z>")."""
    if label == "sim":
        return REST_FIGHTS, 0.0
    m = re.fullmatch(r"sim-f(\d+)-m([^-]+)", label)
    if not m:
        raise ValueError(f"unknown rest_choice {label!r}")
    return int(m.group(1)), float(m.group(2))


def players(settings, threads=1, cells=None):
    """How a result file's `settings` play (docs/specs/explorer-v2.md): a
    namespace with run()'s `play` and hooks (reward, rest_hook, remove_hook,
    path_hook, elite_offers, mid_rest), the score functions the hooks choose
    by (offer_scores(k, items, j), rest_scores(items), remove_scores(items);
    each per item {options, scores, pick}, scores None for a rule), and the
    pack (pack_path, pack_hash: the settings' hash, pack_now: the file's
    hash today; None without a pack). play_cmd builds its run from this, so
    a file and its settings play the same."""
    import types
    import ladder
    if cells is None:
        cells = ladder.pool_cells()
    player, two = settings["player"], settings.get("two_turn", False)
    floors1 = settings.get("one_turn_floors", 0)
    line_seed, step_line = settings.get("line_seed", False), settings.get("step_line", False)
    rewards, boss = settings.get("rewards", "skip"), settings.get("sim_boss", False)
    chooser_player = settings.get("chooser") or player
    ns = types.SimpleNamespace(pack_path=None, pack_hash=None, pack_now=None)
    # Every fight, trial fights included, at the run's ascension level
    # (docs/specs/ascension.md); absent at 0.
    ns.ascension = asc = settings.get("ascension", 0)
    # The choosers project rests and HP at the run's max HP (75 at A20).
    ns.max_hp = max_hp = run_max_hp(asc)

    def at_level(specs):
        return [{**s, "ascension": asc} for s in specs] if asc else specs

    def at_level_values(value):
        return (lambda specs: value(at_level(specs))) if asc else value
    pack = None
    if settings.get("pack"):
        import selfplay
        ns.pack_path, _, ns.pack_hash = settings["pack"].rpartition("@")
        pack, ns.pack_now = selfplay.load_content(ns.pack_path)

    def play(specs):
        specs = at_level(specs)
        floor = (specs[0]["seed"] - SEED_BASE) % 100  # one call plays one floor of every live sequence
        if two and floor >= floors1:
            return ladder.play_two_turn(specs, player, threads, seed_per_turn=line_seed,
                                        step_line=step_line, content=ns.pack_path)
        return ladder.play_bench(specs, player, threads)
    ns.play = play
    sim_play = lambda specs: ladder.play_bench(at_level(specs), chooser_player, threads)  # noqa: E731
    fight_sim = lambda specs: ladder.play_bench(at_level(specs), player, threads)  # noqa: E731
    ns.reward = None
    ns.offer_scores = None
    ns.offer = None  # offer(k, seq, j): the cards sequence `seq` is offered after floor k (no choice made)
    if rewards != "skip":
        offer_pools = pack_pools(reward_pools(cells), pack)
        ns.offer = lambda k, s, j=0: offer(s["i"], k, offer_pools[s["half"]], j)  # noqa: E731
        unit = None
        if rewards == "vrun":
            import run_value_unit
            fit = settings["fit"]
            unit = run_value_unit.RunValue(run_value_unit.load_fit(fit["file"], fit["first"], fit["n"]))
        ns.reward = chooser(rewards, offer_pools, sim_play, max_hp=max_hp, boss=boss, unit=unit,
                            value=at_level_values(net_values(chooser_player, threads)) if rewards == "value" else None,
                            hands=settings.get("value_hands", 1),
                            barred=pack_names(pack) if settings.get("pack_picks") == "originals" else frozenset())
        ns.offer_scores = ns.reward.scores
    ns.rest_hook = ns.rest_scores = None
    if "rest_choice" in settings:
        fights, margin = parse_rest_label(settings["rest_choice"])
        ns.rest_hook = lambda items: rest_choose(items, fight_sim, max_hp, fights=fights, margin=margin)

        def rest_scored(items):
            out = []
            for names, per in rest_scores(items, fight_sim, max_hp, fights=fights):
                out.append({"options": [None] + names, "scores": [float(x.mean()) for x in per] or None,
                            "pick": rest_pick(names, per, fights, margin)})
            return out
        ns.rest_scores = rest_scored
    ns.remove_hook = ns.remove_scores = None
    remove_kind = settings.get("remove", "none")
    if remove_kind == "strike":
        ns.remove_hook = remove_strike
        ns.remove_scores = lambda items: [{"options": [None] + list(dict.fromkeys(deck)), "scores": None, "pick": t}
                                          for (_, _, deck), t in zip(items, remove_strike(items))]
    elif remove_kind == "sim":
        ns.remove_hook = lambda items: remove_sim(REMOVE_FLOOR, items, fight_sim, max_hp, boss=boss)
        ns.remove_scores = lambda items: [{"options": [None] + names, "scores": sc, "pick": first_max(names, sc)}
                                          for names, sc in remove_scores(REMOVE_FLOOR, items, fight_sim, max_hp, boss=boss)]
    elites = settings.get("elites", "fight")
    ns.path_hook = path_skip if elites == "skip" else (path_hp(settings["elite_hp"]) if elites == "hp" else None)
    ns.elite_offers = settings.get("elite_offers", 1)
    ns.mid_rest = settings.get("mid_rest")
    return ns


def tag(player, two_turn):
    base = "heuristic" if player == "heuristic" else (
        os.path.basename(os.path.dirname(player.partition("@")[0])) or "net")
    extra = player.partition("@")[2]
    h = hashlib.sha256(player.encode()).hexdigest()[:6]
    return f"{base}{'-' + extra if extra else ''}{'-two' if two_turn else ''}-{h}"


def resolve_player(player):
    """`player` with a glob in its net path (before any `@`) replaced by its one match, so a
    read can be queued before the learn that names its run folder (as mutate_monsters --net)."""
    path, at, tail = player.partition("@")
    if "*" not in path:
        return player
    import glob
    hits = glob.glob(path)
    if len(hits) != 1:
        raise SystemExit(f"player {path}: {len(hits)} matches, want 1: {hits}")
    return hits[0].replace(os.sep, "/") + at + tail


def play_cmd(args):
    import ladder
    args.player = resolve_player(args.player)
    two = args.two_turn
    out = args.out or os.path.join(ROOT, tag(args.player, two)
                                   + (f"-ch-{tag(args.chooser, False)}" if args.chooser else "") + ".json")
    settings = {"player": args.player, "two_turn": two, "shape": list(SHAPE), "rest": REST,
                "seed": GAUNTLET_SEED}
    if args.one_turn_floors:  # absent when 0, so older files keep matching
        if not two:
            raise SystemExit("--one-turn-floors needs --two-turn")
        settings["one_turn_floors"] = args.one_turn_floors
    if args.line_seed:  # absent when off, so older files keep matching
        if not two:
            raise SystemExit("--line-seed needs --two-turn")
        settings["line_seed"] = True
    if args.step_line:  # absent when off, so older files keep matching
        if not args.line_seed:
            raise SystemExit("--step-line needs --line-seed")
        settings["step_line"] = True
    if args.rewards != "skip":  # absent at the defaults, so older files keep matching
        settings["rewards"] = args.rewards
    if args.start != "cell":
        settings["start"] = args.start
    if args.sim_boss:
        if args.rewards != "sim":
            raise SystemExit("--sim-boss needs --rewards sim")
        settings["sim_boss"] = True
    pack = None
    if args.pack:  # absent when off, so older files keep matching
        import selfplay
        pack, h = selfplay.load_content(args.pack)
        if args.rewards == "skip" and pack_hard(pack) is None:
            raise SystemExit("--pack needs --rewards: with no offers it changes nothing")
        settings["pack"] = f"{args.pack}@{h}"
    if args.ascension:  # absent at 0, so older files keep matching
        if not 0 < args.ascension <= 20:
            raise SystemExit("--ascension is 0-20")
        settings["ascension"] = args.ascension
    if args.pack_picks != "any":  # absent at the default, so older files keep matching
        if not args.pack or args.rewards == "skip":
            raise SystemExit("--pack-picks originals needs --pack and --rewards")
        settings["pack_picks"] = args.pack_picks
    if args.chooser:  # absent when off, so older files keep matching
        if args.rewards not in ("sim", "vrun", "value"):
            raise SystemExit("--chooser needs --rewards sim, vrun or value")
        settings["chooser"] = args.chooser
    if args.value_hands != 1:  # absent at the default, so older files keep matching
        if args.rewards != "value" or args.value_hands < 1:
            raise SystemExit("--value-hands needs --rewards value and a count of at least 1")
        settings["value_hands"] = args.value_hands
    if args.rewards == "vrun":
        if not args.fit:
            raise SystemExit("--rewards vrun needs --fit <gauntlet file>")
        if args.sim_boss:
            raise SystemExit("--rewards vrun always uses the sequence's boss; drop --sim-boss")
        settings["fit"] = {"file": args.fit, "first": args.fit_first, "n": args.fit_n}  # players() loads it
    if args.rest != "heal":
        # the defaults keep the older label "sim", so older files keep matching
        settings["rest_choice"] = rest_label(args.rest, args.rest_fights, args.rest_margin)
    if args.remove != "none":
        settings["remove"] = args.remove
    if args.elite_offers != 1:  # absent at the defaults, so older files keep matching
        settings["elite_offers"] = args.elite_offers
    if args.mid_rest is not None:
        if not 0 <= args.mid_rest < len(SHAPE) - 1:
            raise SystemExit("--mid-rest needs a floor before the boss")
        settings["mid_rest"] = args.mid_rest
    if args.elites != "fight":
        settings["elites"] = args.elites
        if args.elites == "hp":
            settings["elite_hp"] = args.elite_hp
    match = None
    if args.match:
        with open(args.match, encoding="utf-8") as f:
            match = json.load(f)
        ms = match["settings"]
        diff = [d for d in setting_diff(ms, settings) if d[0] in MATCH_FIELDS]
        if ms["seed"] != settings["seed"] or ms["shape"] != settings["shape"] or diff:
            raise SystemExit(f"--match {args.match} made its choices in another setting: "
                             + ", ".join([f"{k} (match {a}, this run {b})" for k, a, b in diff]
                                         or ["seed or shape"]))
        settings["match"] = args.match
    done = {}
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            old = json.load(f)
        if old["settings"] != settings:
            raise SystemExit(f"{out} holds other settings; pass --out")
        done = {r["i"]: r for r in old["sequences"]}
    cells = ladder.pool_cells()
    seqs = sequences(args.sequences, args.first, cells, pack)
    if args.start == "starter":
        import sts
        seqs = [{**s, "deck": list(sts.starter_deck(s["character"]))} for s in seqs]
    starts = None
    if args.ascension:
        # The run's start at its level: HP, max HP and the deck's Ascender's Bane.
        import sts
        rs = {ch: sts.run_start(ch, args.ascension) for ch in {s["character"] for s in seqs}}
        seqs = [{**s, "deck": list(s["deck"]) + rs[s["character"]]["deck_adds"]} for s in seqs]
        starts = {s["i"]: (rs[s["character"]]["hp"], rs[s["character"]]["max_hp"]) for s in seqs}
    todo = [s for s in seqs if s["i"] not in done]
    control = None
    if args.against:
        with open(args.against, encoding="utf-8") as f:
            control = json.load(f)
        cs = control["settings"]
        if cs["seed"] != settings["seed"] or cs["shape"] != settings["shape"]:
            raise SystemExit(f"{args.against} plays other sequences (seed or shape differs)")
        diff = [d for d in setting_diff(cs, settings) if d[0] not in args.vary]
        if diff:
            raise SystemExit(f"{args.against} was played with other settings: "
                             + ", ".join(f"{k} (control {a}, this run {b})" for k, a, b in diff)
                             + "; match them (a paired read never mixes depths: kb yardstick/screen-depth),"
                             " or pass --vary <field> for each one this read tests")
        control = {r["i"]: r for r in control["sequences"]}

    def write(protocol=None):
        rows = [done[s["i"]] for s in seqs if s["i"] in done]
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        body = {"settings": settings, "sequences": rows}
        if protocol is not None:
            body["protocol"] = protocol
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(body, f, indent=1)
        return rows

    def check():
        verdict, n = protocol_verdict([done[s["i"]] for s in seqs if s["i"] in done], control, args.d1, args.min_n)
        return {"against": args.against, "verdict": verdict, "n": n, "d1": args.d1, "min_n": args.min_n,
                **({"vary": sorted(set(args.vary))} if args.vary else {})}

    protocol = check() if control is not None else None
    if todo and (protocol is None or protocol["verdict"] == "open"):
        p = players(settings, args.threads, cells)
        hook, rest_hook, remove_hook = p.reward, p.rest_hook, p.remove_hook
        if match is not None:
            hook, rest_hook, remove_hook = matched(match["sequences"], hook, rest_hook, remove_hook)
        for b in range(0, len(todo), args.block):
            for r in run(todo[b:b + args.block], p.play, reward=hook, rest_hook=rest_hook, remove_hook=remove_hook,
                         path_hook=p.path_hook, elite_offers=p.elite_offers, mid_rest=p.mid_rest, starts=starts):
                done[r["i"]] = r
            protocol = check() if control is not None else None
            write(protocol)
            print(f"{len(done)} / {len(seqs)} sequences played"
                  + (f", protocol {protocol['verdict']} at n {protocol['n']}" if protocol else ""), flush=True)
            if protocol is not None and protocol["verdict"] != "open":
                break
    rows = write(protocol)
    print(f"{out}: {len(rows)} sequences, clear {np.mean([r['cleared'] for r in rows]):.3f}"
          + (f"; protocol vs {args.against}: {protocol['verdict']} at n {protocol['n']}" if protocol else ""))


def setting_diff(a, b):
    """The fields that change play where settings `a` and `b` differ, as
    (field, a's value, b's value); an absent field is its default (None).
    The player's net is the arm and isn't compared; its search-time settings
    after the `@` (@hpb, @hpe, @esp, @sc) are, as `price`. `match` (a
    deck-matched read's choice source) isn't a play setting either."""
    fa = {**a, "price": a["player"].partition("@")[2] or None}
    fb = {**b, "price": b["player"].partition("@")[2] or None}
    keys = sorted((set(fa) | set(fb)) - {"player", "match"})
    return [(k, fa.get(k), fb.get(k)) for k in keys if fa.get(k) != fb.get(k)]


def protocol_verdict(rows, control, d1, min_n):
    """The gauntlet protocol (decisions "Gauntlet protocol") on `rows` in
    index order against `control` ({i: row}): (verdict, n) from
    gauntlet_protocol.sprt over the sequences both hold with the same cell."""
    import gauntlet_protocol as gp
    pairs = [(r, control[r["i"]]) for r in sorted(rows, key=lambda r: r["i"])
             if r["i"] in control and control[r["i"]]["cell"] == r["cell"]]
    dh = [gp.end_hp(a) - gp.end_hp(b) for a, b in pairs]
    dc = [float(a["cleared"]) - float(b["cleared"]) for a, b in pairs]
    if len(dh) < min_n:
        return "open", len(dh)
    return gp.sprt(dh, dc, d1, min_n)


def summary(a, b):
    """Paired read of two result dicts' sequences (by index)."""
    ra = {r["i"]: r for r in a["sequences"]}
    rb = {r["i"]: r for r in b["sequences"]}
    keys = sorted(set(ra) & set(rb))
    out = {}
    for h in ("all",) + HALVES:
        ks = [k for k in keys if h == "all" or ra[k]["half"] == h]
        if not ks:
            continue
        ca = np.array([ra[k]["cleared"] for k in ks], float)
        cb = np.array([rb[k]["cleared"] for k in ks], float)
        d = ca - cb
        boss = [k for k in ks if len(ra[k]["floors"]) == len(SHAPE) and len(rb[k]["floors"]) == len(SHAPE)]
        row = {"n": len(ks), "clear_a": float(ca.mean()), "clear_b": float(cb.mean()), "diff": float(d.mean()),
               "se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0,
               "floors_a": float(np.mean([sum(f["won"] for f in ra[k]["floors"]) for k in ks])),
               "floors_b": float(np.mean([sum(f["won"] for f in rb[k]["floors"]) for k in ks])),
               "boss_both": len(boss),
               "boss_hp_a": float(np.mean([ra[k]["floors"][-1]["hp_start"] for k in boss])) if boss else None,
               "boss_hp_b": float(np.mean([rb[k]["floors"][-1]["hp_start"] for k in boss])) if boss else None}
        for name, r in (("a", ra), ("b", rb)):
            by_floor, by_enc = [0] * len(SHAPE), {}
            for k in ks:
                last = r[k]["floors"][-1]
                if not last["won"]:
                    by_floor[len(r[k]["floors"]) - 1] += 1
                    by_enc[last["encounter"]] = by_enc.get(last["encounter"], 0) + 1
            row[f"deaths_floor_{name}"] = by_floor
            row[f"deaths_enc_{name}"] = dict(sorted(by_enc.items(), key=lambda x: -x[1]))
        out[h] = row
    return out


def read_cmd(args):
    with open(args.a, encoding="utf-8") as f:
        a = json.load(f)
    with open(args.b, encoding="utf-8") as f:
        b = json.load(f)
    print(f"A {a['settings']['player']}{' two-turn' if a['settings']['two_turn'] else ''}\n"
          f"B {b['settings']['player']}{' two-turn' if b['settings']['two_turn'] else ''}")
    for h, r in summary(a, b).items():
        bh = (f"{r['boss_hp_a']:.1f} / {r['boss_hp_b']:.1f} ({r['boss_both']} reach both)"
              if r["boss_hp_a"] is not None else "-")
        print(f"{h:9s} n {r['n']:4d} clear A {r['clear_a']:.3f} B {r['clear_b']:.3f} A-B {r['diff']:+.3f} "
              f"(se {r['se']:.3f})  floors won {r['floors_a']:.2f} / {r['floors_b']:.2f}  HP at boss {bh}")
        print(f"          deaths by floor A {r['deaths_floor_a']}\n                          B {r['deaths_floor_b']}")
        print(f"          deaths by encounter A {r['deaths_enc_a']}\n                              B {r['deaths_enc_b']}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("player")
    p.add_argument("--sequences", type=int, default=200)
    p.add_argument("--first", type=int, default=0)
    p.add_argument("--threads", type=int, default=6)
    p.add_argument("--two-turn", action="store_true")
    p.add_argument("--one-turn-floors", type=int, default=0,
                   help="with --two-turn: play the first N floors one turn deep (review 2026-11-02 R4)")
    p.add_argument("--line-seed", action="store_true",
                   help="with --two-turn: one sample seed per combat turn, a committed-line player (docs/specs/line-seed.md)")
    p.add_argument("--step-line", action="store_true",
                   help="with --line-seed: play each uncut tree's principal line instead of searching every decision (docs/specs/line-step.md)")
    p.add_argument("--rewards", choices=("skip", "random", "sim", "vrun", "value"), default="skip")
    p.add_argument("--value-hands", type=int, default=1, help="value: dealt hands averaged per start state")
    p.add_argument("--fit", default=None, help="vrun: gauntlet file whose sequences give P(reach the boss at h | h, floor)")
    p.add_argument("--fit-first", type=int, default=250)
    p.add_argument("--fit-n", type=int, default=250)
    p.add_argument("--start", choices=("cell", "starter"), default="cell")
    p.add_argument("--sim-boss", action="store_true", help="sim chooser also scores against the boss pool")
    p.add_argument("--chooser", default=None,
                   help="player for the sim chooser's option fights (default: the fight player; docs/specs/chooser-player.md)")
    p.add_argument("--rest", choices=("heal", "sim"), default="heal",
                   help="sim: heal or upgrade a card before the boss by simulating it (docs/specs/rest-site.md)")
    p.add_argument("--rest-fights", type=int, default=REST_FIGHTS, help="--rest sim: boss fights per option")
    p.add_argument("--rest-margin", type=float, default=0.0,
                   help="--rest sim: upgrade only if the best upgrade beats heal by this many paired standard errors")
    p.add_argument("--remove", choices=("none", "strike", "sim"), default="none",
                   help="one card removal after the first elite (docs/specs/card-removal.md)")
    p.add_argument("--elites", choices=("fight", "skip", "hp"), default="fight",
                   help="at each elite floor: fight it, skip it for a hard hallway, or skip below --elite-hp "
                        "(docs/specs/elite-skip.md)")
    p.add_argument("--elite-hp", type=int, default=40, help="--elites hp: fight the elite at this HP or more")
    p.add_argument("--elite-offers", type=int, default=1,
                   help="card offers after a won elite fight (docs/specs/mini-run.md; the mini-run uses 2)")
    p.add_argument("--mid-rest", type=int, default=None,
                   help="heal by the rest site's 30%% after floor K is won (docs/specs/mini-run.md; the mini-run uses 5)")
    p.add_argument("--ascension", type=int, default=0,
                   help="the game's ascension level (0-20) every fight is played at, with its run start "
                        "(HP, max HP, Ascender's Bane): docs/specs/ascension.md")
    p.add_argument("--pack", default=None, help="content pack file: its base cards join both halves' offers, its hallway encounters the hard floors")
    p.add_argument("--pack-picks", choices=("any", "originals"), default="any",
                   help="originals: the pack's cards are offered but the chooser may take only original cards or skip "
                        "(docs/specs/pack-pick-split.md)")
    p.add_argument("--out", default=None)
    p.add_argument("--block", type=int, default=50, help="sequences per block; the file is rewritten after each")
    p.add_argument("--match", help="gauntlet file whose recorded card picks, rest and removal choices this run "
                   "replays where it has them, so a read varies only the fighter (docs/specs/deck-matched-reads.md)")
    p.add_argument("--against", default=None, help="control file: stop when the gauntlet protocol decides")
    p.add_argument("--vary", action="append", default=[], choices=VARY,
                   help="with --against: a setting this read tests, so the control may differ in it (repeatable); "
                        "any other difference is refused")
    p.add_argument("--d1", type=float, default=1.5)
    p.add_argument("--min-n", type=int, default=50)
    r = sub.add_parser("read")
    r.add_argument("a")
    r.add_argument("b")
    args = ap.parse_args(argv)
    (play_cmd if args.cmd == "play" else read_cmd)(args)


if __name__ == "__main__":
    main()
