"""Self-play data for the value nets. Search + heuristic plays seeded
combats; from each game we keep a few decision states plus the paused state
after each kept EndTurn/divergent action (the kind of state search asks the
evaluator to score), all labelled with that game's final score.

Every state is encoded twice, `effects` and `ids`, so both nets train on
exactly the same states.

    python scripts/selfplay.py            # writes data/*.npz (cached)
"""

import math
import os
import time

import numpy as np

import sts
import stsnet
from stsnet import Dataset

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
GROUPS = ["hallway", "elite", "boss"]
STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
HELD_OUT = ["Twin Strike", "Iron Wave", "Thunderclap", "Pommel Strike", "Uppercut"]
HELD_OUT_ALL = set(HELD_OUT) | {n + "+" for n in HELD_OUT}
TRAIN_POOL = [n for n in sts.deck_card_names() if n not in HELD_OUT_ALL]
# Every card and power the id net may know: what Ironclad training games can
# hold. Cards: the training pool plus the statuses monsters add. Powers: all
# but Poison (Silent only) and the powers only check 9's held-out cards grant
# (Demon Form, Rage; Metallicize stays, Lagavulin has it).
STATUSES = ["Wound", "Slimed", "Dazed"]
KNOWN_CARDS = sorted(set(TRAIN_POOL) | set(STARTER) | set(STATUSES), key=sts.all_card_names().index)
KNOWN_POWERS = [p for p in sts.power_names() if p not in ("Poison", "DemonForm", "Rage")]
STATES_PER_GAME = 6
LIMIT = 16
# Bumped when the feature format changes, so cached data/ files are rebuilt.
FORMAT = "rows"
# Switch 6 (no-death HP-loss target): HP-lost labels are capped here, and a
# no-death combat that hits the engine's turn limit is labelled with the cap.
HP_CAP = 150.0
# Varied setups (learned-play Amendment 3): every training game starts at a
# whole HP drawn uniformly over these fractions of max HP (at least 1), with
# the starter deck plus a uniform number of training-pool cards in this range.
VARIED = {"hp": [0.1, 1.0], "extra_cards": [3, 15]}


# A feature mode with these suffixes turns the monster lookahead columns
# (docs/specs/monster-lookahead.md), the power-rate columns
# (docs/specs/rate-features.md) and the start-HP column
# (docs/specs/start-hp.md) on, in this order; `learn.feature_mode`.
LOOKAHEAD = "+lookahead"
RATES = "+rates"
START = "+start"
# Encoder value flags, last: card damage and block as the game shows them
# and the exhaust pile's counts as 0 (docs/specs/shown-card-numbers.md). A
# net trained on them saves `shown_numbers` / `exhaust_hidden` in its meta.
SHOWN = "+shown"
XHID = "+xhid"


def split_flags(mode):
    """(the mode without them, shown numbers on, exhaust hidden on): the
    encoder value flags of a feature mode such as "effects+start+shown+xhid"."""
    xhid = mode.endswith(XHID)
    mode = mode[:-len(XHID)] if xhid else mode
    shown = mode.endswith(SHOWN)
    return (mode[:-len(SHOWN)] if shown else mode), shown, xhid


def split_mode(mode):
    """(card repr, lookahead on, rates on, start HP on) of a feature mode
    such as "effects+lookahead+rates+start" (value flags: `split_flags`)."""
    mode = split_flags(mode)[0]
    start = mode.endswith(START)
    mode = mode[:-len(START)] if start else mode
    rates = mode.endswith(RATES)
    mode = mode[:-len(RATES)] if rates else mode
    look = mode.endswith(LOOKAHEAD)
    return (mode[:-len(LOOKAHEAD)] if look else mode), look, rates, start


def features(mode):
    repr_, look, rates, start = split_mode(mode)
    _, shown, xhid = split_flags(mode)
    flags = {k: True for k, on in (("shown_numbers", shown), ("exhaust_hidden", xhid)) if on}
    if repr_ == "ids":
        return sts.Features(repr_, known_cards=KNOWN_CARDS, known_powers=KNOWN_POWERS, lookahead=look, rates=rates,
                            start_hp=start, **flags)
    return sts.Features(repr_, lookahead=look, rates=rates, start_hp=start, **flags)


def meta_vocab(mode):
    """The `known_*` vocabularies of `features(mode)`, for a net's meta. The
    effects net keeps the full row vocabularies (primitives, not names)."""
    v = features(mode).vocab
    return {"known_" + k: v[k] for k in ("cards", "powers", "triggers", "conditions", "effects")}


def train_deck(rng):
    return STARTER + list(rng.choice(TRAIN_POOL, 5))


def varied_deck(rng):
    """Starter + VARIED["extra_cards"] (3-15, uniform) training-pool cards."""
    lo, hi = VARIED["extra_cards"]
    return STARTER + list(rng.choice(TRAIN_POOL, int(rng.integers(lo, hi + 1))))


def varied_held_out_deck(rng):
    """Starter + VARIED["extra_cards"] cards from the whole Ironclad pool
    (check 9's cards included), at least 2 of them held out by check 6 or
    check 9: the cell gauntlet's held-out kind of deck, drawn on other seeds
    (lane yardstick-cards step 2). Demon Form, drawn in about 27% of such
    decks, replaces the first extra card in DEMON_FORM_SHARE of the rest, so
    about 40% of the decks hold it."""
    lo, hi = VARIED["extra_cards"]
    pool = sts.deck_card_names() + sts.held_out_card_names()
    held = HELD_OUT_ALL | set(sts.held_out_card_names())
    n = int(rng.integers(lo, hi + 1))
    while True:
        extra = list(rng.choice(pool, n))
        if sum(c in held for c in extra) >= 2:
            break
    if not any(sts.base_name(c) == "Demon Form" for c in extra) and rng.random() < DEMON_FORM_SHARE:
        extra[0] = "Demon Form+" if rng.random() < 0.5 else "Demon Form"
    return STARTER + extra


DEMON_FORM_SHARE = 0.2


def full_pool_deck(rng):
    """Starter + VARIED["extra_cards"] cards uniform over the whole Ironclad
    pool, the held-out cards of checks 6 and 9 included (lane
    all-content-net, docs/specs/all-content-net.md)."""
    lo, hi = VARIED["extra_cards"]
    pool = sts.deck_card_names() + sts.held_out_card_names()
    return STARTER + list(rng.choice(pool, int(rng.integers(lo, hi + 1))))


def with_bosses(specs, groups, bosses):
    """`specs` with the boss group's encounters taken from `bosses` in turn;
    decks, seeds and HP unchanged; an unknown name raises."""
    for e in bosses:
        sts.Combat(STARTER, e, seed=0)
    b, j, out = GROUPS.index("boss"), 0, []
    for s, g in zip(specs, groups):
        if g == b:
            s, j = (bosses[j % len(bosses)], *s[1:]), j + 1
        out.append(s)
    return out


def pack_pool_deck(cards):
    """`full_pool_deck` with `cards` (a loaded pack's gen:<id> names) in its
    pool (lane pack-net-scratch, docs/specs/pack-learn.md)."""
    pool = sts.deck_card_names() + sts.held_out_card_names() + list(cards)

    def deck(rng):
        lo, hi = VARIED["extra_cards"]
        return STARTER + list(rng.choice(pool, int(rng.integers(lo, hi + 1))))
    return deck


def pack_cards(pack):
    """Deck names (gen:<id>) of every card of a pack, upgrades included."""
    names = []
    for c in pack.get("cards", []):
        names.append("gen:" + c["id"])
        if "upgrade" in c:
            names.append("gen:" + c["id"] + "+")
    return names


PACK_ENC_SEED = 0x9ac4


def with_pack_encounters(specs, groups, packs):
    """`specs` with the packs' encounters joined to their groups: on a
    stream of its own per spec, an added one (no official encounter of that
    id) with probability added / (added + official in the group), else the
    official draw or its pack version (a pack encounter whose id names it),
    as gauntlet.pack_hard does; decks, seeds and HP unchanged."""
    added, rep = {}, {}
    for pack in packs:
        for e in pack.get("encounters", []):
            name, g = e["id"].lower().replace(" ", "_"), GROUPS.index(e["group"])
            if name in sts.encounter_names():
                rep[name] = "gen:" + e["id"]
            else:
                added.setdefault(g, []).append("gen:" + e["id"])
    official = {g: sum(sts.encounter_group(n) == name for n in sts.encounter_names()) for g, name in enumerate(GROUPS)}
    out = []
    for s, g in zip(specs, groups):
        enc, pool = s[0], added.get(g, [])
        rng = np.random.default_rng([PACK_ENC_SEED, int(s[2])])
        if pool and rng.random() < len(pool) / (len(pool) + official[g]):
            enc = pool[int(rng.integers(len(pool)))]
        else:
            enc = rep.get(enc, enc)
        out.append((enc, *s[1:]))
    return out


def pool_deck(kinds):
    """A `varied_deck` drawing its extra cards from `kinds` (base names) and
    their upgrades only (coverage pilot, docs/specs/coverage-pilot.md)."""
    pool = [c for c in TRAIN_POOL if sts.base_name(c) in kinds]

    def deck(rng):
        lo, hi = VARIED["extra_cards"]
        return STARTER + list(rng.choice(pool, int(rng.integers(lo, hi + 1))))
    return deck


# Generated content (docs/specs/registry-lite.md step 5): packs loaded in
# this process, by their config value's JSON; PACK_TEXTS: the exact text
# loaded, by content hash (docs/specs/runtime-registry.md stage 2: the store).
_PACKS = {}
PACK_TEXTS = {}


def load_content(content):
    """(pack, content hash) of a config's `content`: a pack file's path, or
    {"seed", "powers"} generated here (scripts/gen_content.py). The pack is
    loaded into the engine once per process."""
    import json
    key = json.dumps(content, sort_keys=True)
    if key not in _PACKS:
        if isinstance(content, dict):
            import gen_content
            pack = gen_content.generate(int(content["seed"]), int(content["powers"]))
        else:
            with open(content, encoding="utf-8") as f:
                pack = json.load(f)
        text = json.dumps(pack, sort_keys=True)
        h = sts.load_content(text)
        PACK_TEXTS[h] = text
        _PACKS[key] = (pack, h)
    return _PACKS[key]


def content_cards(pack, split):
    """The deck names of a pack's power cards of one split ("train" / "test")."""
    return ["gen:" + c["id"] for c in pack["cards"] if c["split"] == split]


def content_deck(deck_fn, cards, share):
    """`deck_fn`'s decks, a `share` of them with 1-2 of `cards` added (drawn
    after the deck, so with share 0 it is `deck_fn` itself)."""
    if share <= 0:
        return deck_fn

    def deck(rng):
        d = deck_fn(rng)
        if rng.random() < share:
            d = d + list(rng.choice(cards, int(rng.integers(1, 3))))
        return d
    return deck


def max_hp(character="ironclad"):
    """The character's starting (max) HP."""
    return sts.Combat(STARTER, "jaw_worm", character=character).player_hp()


def varied_hp(rng, top=None):
    """A whole HP uniform over VARIED["hp"] of `top` (default the
    Ironclad's max HP), at least 1."""
    top = max_hp() if top is None else top
    lo, hi = VARIED["hp"]
    return int(rng.integers(max(1, math.ceil(lo * top)), max(1, round(hi * top)) + 1))


def low_hp_fn(share, lo, hi):
    """An `hp_fn` that starts a `share` of games at a whole HP uniform over
    [lo, hi] and the rest at `varied_hp` (the low-HP slice, lean-loop spec).
    One extra draw per spec, so its specs differ from `varied_hp`'s."""
    def hp(rng, top=None):
        return int(rng.integers(lo, hi + 1)) if rng.random() < share else varied_hp(rng, top)
    return hp


def held_out_deck(rng):
    """Starter + 5 cards from the whole pool with at least 2 held-out ones."""
    pool = sts.deck_card_names()
    while True:
        extra = list(rng.choice(pool, 5))
        if sum(c in HELD_OUT_ALL for c in extra) >= 2:
            return STARTER + extra


def make_specs(n_per_group, seed, deck_fn, character="ironclad", hp_fn=None, ascension=0):
    """`n_per_group` specs per encounter group; encounters and combat seeds
    from `sts.make_specs`, decks from `deck_fn`. With `hp_fn` (varied
    setups), each spec gets a fourth field, its starting HP `hp_fn(rng)`,
    drawn from the same generator right after its deck. At an `ascension`
    level the decks hold the run start's additions (Ascender's Bane from
    A10) and the HP is drawn of that level's max HP (docs/specs/ascension.md);
    the draws are the same as at A0."""
    rng = np.random.default_rng(seed)
    adds, top = [], None
    if ascension:
        rs = sts.run_start(character, ascension)
        adds, top = list(rs["deck_adds"]), rs["max_hp"]
    specs, groups = [], []
    for g, name in enumerate(GROUPS):
        for enc, _, s in sts.make_specs(name, n_per_group, extra=0, seed=seed * 10 + g, character=character):
            deck = deck_fn(rng)
            if adds:
                deck = list(deck) + adds
            specs.append((enc, deck, s) if hp_fn is None else (enc, deck, s, hp_fn(rng, top)))
            groups.append(g)
    return specs, groups


def label_heal(s, r):
    """The end-of-combat heal inside game `r`'s `hp_end`: the HP the win
    actually gave (`healed`: Meat on the Bone and a heal capped at max HP
    included); none in a no-death game (that mode doesn't heal). A result
    without `healed` (written before it) falls back to state `s`'s planned
    `win_heal`."""
    if r.get("no_death"):
        return 0
    return r["healed"] if "healed" in r else s.win_heal


def hp_lost(hp, r, heal=0):
    """HP lost from a state at `hp` to the end of won game `r`, before the
    end-of-combat heal `heal` (`label_heal`) that `hp_end` holds. A normal
    game's loss is floored at 0 (when the heal was capped at max HP it
    overstates the loss by up to the heal, but the formula's end HP,
    capped again, is still the real one); no-death losses are as before."""
    if not heal:
        return hp - r["hp_end"]
    return max(hp - (r["hp_end"] - heal), 0)


def hp_label(hp, r, heal=0):
    """Switch 6: HP lost from a state at `hp` to the end of its game `r`
    (`hp_lost`), capped at HP_CAP; HP_CAP when the game was lost (a death,
    or the turn limit)."""
    if not r["won"]:
        return HP_CAP
    return min(hp_lost(hp, r, heal), HP_CAP)


def hp_target(hp, r, heal=0):
    """Switch 6's label of a state at `hp` in game `r`: a one-hot histogram
    (stsnet bins) of the HP lost to the end (`hp_lost`), or of the
    turn-limit bin when the game was lost (a death, or the turn limit)."""
    out = np.zeros(stsnet.N_BINS, np.float32)
    out[stsnet.bin_index(hp_lost(hp, r, heal)) if r["won"] else stsnet.TURN_LIMIT_BIN] = 1.0
    return out


def real_score(c, start_hp, heal, no_death=True, rule=None):
    """A finished combat's score as normal play would give it. No-death: 0
    when HP ended at 0 or below (or at the turn limit), else
    2 - HP lost after the end-of-combat heal / 100. Normal play: the engine
    has already healed and scored it (`c.score()`). Under a survive `rule`
    (stsnet.score_rule; normal play only, ValueError with no-death): a win
    scores c + w x its healed HP / 100, a loss 0."""
    if rule is not None:
        if no_death:
            raise ValueError("the survive score rule needs normal self-play (no_death false)")
        return rule["c"] + rule["w"] * c.player_hp() / 100 if c.won() else 0.0
    if not no_death:
        return c.score()
    hp = c.player_hp()
    if not c.won() or hp <= 0:
        return 0.0
    return 2 - max(start_hp - (hp + heal), 0) / 100


def pick_branches(results, temp, rng):
    """Switch 7's branch points for recorded games (results need `values`):
    [(game index, decision index, forced action)]. A decision qualifies when
    one of its options is valued below its best by more than `temp` (the
    branch gap, Amendment 4; it was the exploration temperature, so
    exploration would rarely play it); per game, one
    qualifying decision is picked uniformly and one such option uniformly.
    A game with no qualifying decision gets no branch."""
    out = []
    for gi, r in enumerate(results):
        cands = []
        for i, vals in enumerate(r["values"]):
            if vals:
                best = max(v for _, v in vals)
                far = [acts for acts, v in vals if v < best - temp]
                if far:
                    cands.append((i, far))
        if cands:
            i, far = cands[rng.integers(len(cands))]
            out.append((gi, i, far[rng.integers(len(far))][0]))
    return out


def first_sampled(r):
    """The first decision a game's examples may come from: after the forced
    action of a branch game (`branch_at`), else its first."""
    return r.get("branch_at", -1) + 1


def _inputs(ex, s, search, kind, played, distance):
    """Appends one example's label inputs (stsnet.Dataset's `search`, `kind`,
    `played`, `distance` and codec bytes) to the lists of `ex`."""
    ex["search"].append(float("nan") if search is None else search)
    ex["kind"].append(kind)
    ex["played"].append(int(played))
    ex["distance"].append(distance)
    ex["codec"].append(codec_of(s))


INPUTS = ("search", "kind", "played", "distance", "codec")


def codec_of(s):
    """The state's codec bytes; empty for a combat holding generated content,
    which the codec (and so the solved database) doesn't take."""
    try:
        return s.encode()
    except ValueError as e:
        if "generated" not in str(e):
            raise
        return b""


def sample_states(results, groups, rng, labels=None, extra=None):
    """Picks states from recorded games: (states, targets, groups); every
    label is the game's real outcome. `labels=None` labels every state with
    its game's final score. With `labels={"afterstates": True}` (results
    need `values`), each picked decision is followed by every option's
    afterstate the search scored, for the ranking term (`_sample_afterstates`).
    `labels={"hp_loss": True}` (switch 6; no-death games) labels states with
    `hp_target` histograms instead of the score (no-death or normal games). `extra`, a dict of lists,
    gets each example's real outcome label (`outcome`: the score, or
    `hp_label` with switch 6) and, with `afterstates` or `labels={"rank":
    True}`, the ranking fields of `stsnet.Dataset.EXTRA` (decision ids
    continue from the lists' length). `rank` (data whose search values may
    not be used, self-play round 0) adds no afterstates: every example is
    its own decision with option -1, so the ranking term ignores it. A
    branch game (switch 7) is sampled only after its forced action
    (`first_sampled`), with its own outcome. `extra` also gets every
    example's label inputs (`INPUTS`, see stsnet.Dataset), from which
    training computes the curriculum's labels."""
    hp = bool(labels and labels.get("hp_loss"))
    if labels and labels.get("afterstates"):
        return _sample_afterstates(results, groups, rng, extra, hp, stsnet.score_rule(labels.get("score_rule")))
    label = (lambda s, r: hp_target(s.player_hp(), r, label_heal(s, r))) if hp else (lambda s, r: r["score"])
    outcome = (lambda s, r: hp_label(s.player_hp(), r, label_heal(s, r))) if hp else (lambda s, r: r["score"])
    states, target, grp, real = [], [], [], []
    ex = {k: [] for k in INPUTS}
    for r, g in zip(results, groups):
        lo = first_sampled(r)
        n = len(r["states"]) - lo
        last = r["states"][-1].turn()
        for i in sorted(lo + rng.choice(n, min(n, STATES_PER_GAME), replace=False)):
            s, a = r["states"][i], r["actions"][i]
            vals = r["values"][i] if r.get("values") else None
            dist = last - s.turn()
            states.append(s)
            target.append(label(s, r))
            real.append(outcome(s, r))
            grp.append(g)
            _inputs(ex, s, max(v for _, v in vals) if vals else None, 0, True, dist)
            for k, (acts, kind, outs) in enumerate(s.options(LIMIT)):
                if a in acts and kind == "divergent":
                    paused = outs[0][1]
                    if not paused.is_over():
                        states.append(paused)
                        target.append(label(paused, r))
                        real.append(outcome(paused, r))
                        grp.append(g)
                        _inputs(ex, paused, vals[k][1] if vals else None, Dataset.KINDS[kind], True, dist)
    if extra is not None:
        for k, v in ex.items():
            extra.setdefault(k, []).extend(v)
        extra.setdefault("outcome", []).extend(real)
        if labels and labels.get("rank"):
            d = extra["decision"][-1] + 1 if extra.get("decision") else 0
            extra.setdefault("decision", []).extend(range(d, d + len(target)))
            for k, v in (("option", -1), ("prob", 0.0), ("opt_const", 0.0), ("rank_value", 0.0)):
                extra.setdefault(k, []).extend([v] * len(target))
    return states, target, grp


def _sample_afterstates(results, groups, rng, extra=None, hp=False, rule=None):
    """The same decisions as `sample_states`, each followed by its options'
    afterstates: the options' outcome states (one for deterministic and
    divergent options, every listed outcome for chance ones; finished
    combats are skipped, search scores them exactly, and go into their
    option's `opt_const`). Every example is labelled with its game's real
    outcome (with `hp`, switch 6, the `hp_target` of the HP lost from it);
    the options' recorded search values only order them (`rank_value`).
    `rule` (switch 6's survive score rule, else None) scores the finished
    outcomes in `opt_const`."""
    states, target, grp = [], [], []
    ex = {k: [] for k in ("outcome", "decision", "option", "prob", "opt_const", "rank_value") + INPUTS}
    d = extra["decision"][-1] + 1 if extra and extra.get("decision") else 0

    def note(option, prob, const, value, outcome):
        ex["outcome"].append(outcome)
        ex["decision"].append(d)
        ex["option"].append(option)
        ex["prob"].append(prob)
        ex["opt_const"].append(const)
        ex["rank_value"].append(value)

    for r, g in zip(results, groups):
        lo = first_sampled(r)
        n = len(r["states"]) - lo
        last = r["states"][-1].turn()
        for i in sorted(lo + rng.choice(n, min(n, STATES_PER_GAME), replace=False)):
            s, vals, a = r["states"][i], r["values"][i], r["actions"][i]
            opts = s.options(LIMIT)
            assert [list(a) for a, _, _ in opts] == [list(a) for a, _ in vals], "options differ from the search's"
            heal = s.win_heal
            dist = last - s.turn()
            states.append(s)
            lh = label_heal(s, r)
            target.append(hp_target(s.player_hp(), r, lh) if hp else r["score"])
            grp.append(g)
            note(-1, 0.0, 0.0, max(v for _, v in vals), hp_label(s.player_hp(), r, lh) if hp else r["score"])
            _inputs(ex, s, max(v for _, v in vals), 0, True, dist)
            for k, ((acts, kind, outs), (_, v)) in enumerate(zip(opts, vals)):
                # In no-death mode a finished outcome is scored as real play
                # would: lost at 0 HP or below, else healed.
                nd = bool(r.get("no_death"))
                const = sum(p * (real_score(o, r["hp_start"], heal, nd, rule) if hp else o.score()) for p, o in outs if o.is_over())
                for p, o in outs:
                    if not o.is_over():
                        states.append(o)
                        target.append(hp_target(o.player_hp(), r, lh) if hp else r["score"])
                        grp.append(g)
                        note(k, p, const, v, hp_label(o.player_hp(), r, lh) if hp else r["score"])
                        _inputs(ex, o, v, Dataset.KINDS[kind], a in acts, dist)
            d += 1
    if extra is not None:
        for k, v in ex.items():
            extra.setdefault(k, []).extend(v)
    return states, target, grp


def generate(name, n_per_group, seed, deck_fn, chunk=3000, character="ironclad", modes=("effects", "ids")):
    """Plays and encodes one data set; caches `data/<name>_<mode>_<FORMAT>.npz`."""
    paths = {m: os.path.join(DATA, f"{name}_{m}_{FORMAT}.npz") for m in modes}
    if all(os.path.exists(p) for p in paths.values()):
        return {m: Dataset.load(p) for m, p in paths.items()}
    os.makedirs(DATA, exist_ok=True)
    t = time.perf_counter()
    specs, groups = make_specs(n_per_group, seed, deck_fn, character)
    rng = np.random.default_rng(seed + 12345)
    enc = {m: features(m) for m in paths}
    parts = {m: [] for m in paths}
    targets, grps = [], []
    for i in range(0, len(specs), chunk):
        res = sts.run("search", specs[i:i + chunk], record=True, limit=LIMIT, character=character,
                      **stsnet.job_threads({}))
        states, tg, gr = sample_states(res, groups[i:i + chunk], rng)
        for m in paths:
            parts[m].append(enc[m].encode(states))
        targets += tg
        grps += gr
    out = {}
    for m, p in paths.items():
        out[m] = Dataset.from_batches(parts[m], targets, grps)
        out[m].save(p)
    print(f"{name}: {len(specs)} games, {len(targets)} states, {time.perf_counter() - t:.0f}s")
    return out


def all_sets(n_train=10000, n_eval=1000):
    """Train / validation / test (a: training-pool decks) / test (b: held-out
    decks). Different seeds for each; split by game."""
    return {
        "train": generate("train", n_train, 1, train_deck),
        "val": generate("val", n_eval, 2, train_deck),
        "test_a": generate("test_a", n_eval, 3, train_deck),
        "test_b": generate("test_b", n_eval, 4, held_out_deck),
    }


if __name__ == "__main__":
    all_sets()
