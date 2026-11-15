"""Evaluation bench representation checks.

- Aliasing audit: within each saved decision, the options search chooses
  between, each keyed by its outcome states' feature vectors (with their
  probabilities). Two options of one decision with the same key but cached
  reference values more than ALIAS_GAP apart are a case the features can't
  tell apart. Siblings are compared, not states from different games: those
  never match exactly, and siblings are what search has to rank.
- Minimal-pair probes: hand-built states (deck, encounter, seed, HP and an
  action prefix, through the public API) where two first actions differ in
  one strategic fact by at least CONTESTED in reference value (pinned by the
  tests). An evaluator passes a probe when its search values order the pair
  the same way as the reference (a tie counts half).

Not built: "multi-hit into Curl Up". The engine lands Curl Up's block after
the card in play finishes (as the game does), so a multi-hit card isn't
blunted by it, and no pair was found where the reference separates the two
orders; a second AoE probe takes its place. Dropped: "a Skill into Enrage":
no deck, seed or HP tried gave a reference gap of CONTESTED (starter decks
lose to Gremlin Nob either way); the Skill-heavy family's tight fights
against Nob still cover Enrage.
"""

import numpy as np

import bench_decisions
import bench_sets
import sts

ALIAS_GAP = 0.05
ALIAS_EXAMPLES = 3

STARTER = sts.starter_deck("ironclad")
FIVE_DS = ["Strike", "Strike", "Strike", "Defend", "Defend"]


def probe(name, fact, deck, encounter, good, bad, seed=1, hp=None, prefix=()):
    return {"name": name, "fact": fact, "deck": list(deck), "encounter": encounter, "seed": seed, "hp": hp,
            "prefix": list(prefix), "good": good, "bad": bad}


# Five-card decks put the whole deck in the opening hand; a prefix that
# spends energy leaves one card's worth, so the first action excludes the
# other.
PROBES = [
    probe("lethal_now", "lethal this turn beats blocking a hit that still kills", FIVE_DS, "cultist",
          "Strike@0", "Defend", hp=8,
          prefix=["Strike@0"] * 3 + ["End"] + ["Strike@0"] * 3 + ["End", "Strike@0", "Strike@0"]),
    probe("kill_attacker_first", "killing the attacker before it acts beats hitting the other monster", FIVE_DS,
          "small_slimes", "Strike@1", "Strike@0", hp=5, prefix=["Strike@1", "Strike@0"]),
    probe("block_needed", "blocking a lethal-range hit beats attacking", ["Strike", "Strike", "Defend", "Defend", "Defend"],
          "jaw_worm", "Defend", "Strike@0", hp=8, prefix=["Strike@0", "Defend"]),
    probe("block_matches_hit", "block already equal to the incoming hit: more block is wasted", FIVE_DS,
          "small_slimes", "Strike@0", "Defend", hp=20, prefix=["Defend", "Strike@0"]),
    probe("block_no_attack", "no attack incoming: block is wasted", ["Defend", "Defend", "Defend", "Strike", "Strike"],
          "cultist", "Strike@0", "Defend", prefix=["Defend", "Defend"]),
    probe("vulnerable_before_multihit", "Vulnerable before a multi-hit card", ["Bash", "Twin Strike", "Defend", "Defend", "Defend"],
          "cultist", "Bash@0", "Twin Strike@0", hp=12),
    probe("multihit_unblocked", "a multi-hit card beats a single hit on an unblocked target",
          ["Defend", "Defend", "Strike", "Twin Strike", "Defend"], "cultist", "Twin Strike@0", "Strike@0",
          prefix=["Defend", "Defend"]),
    probe("debuff_no_artifact", "Vulnerable lands without Artifact: Bash first", ["Strike", "Strike", "Strike", "Bash", "Defend"],
          "jaw_worm", "Bash@0", "Strike@0"),
    probe("debuff_into_artifact", "Vulnerable on the Sentry whose Artifact is gone beats Bash into Artifact",
          ["Bash", "Bash", "Strike", "Twin Strike", "Strike"], "three_sentries", "Bash@1", "Bash@0", seed=3,
          prefix=["Bash@1", "End"]),
    probe("block_without_enrage", "the same block without Enrage is worth playing", STARTER, "jaw_worm",
          "Defend", "End", hp=30, prefix=["Strike@0", "Strike@0"]),
    probe("setup_while_asleep", "set up while Lagavulin sleeps", STARTER + ["Inflame"], "lagavulin",
          "Inflame", "Strike@0", seed=2, prefix=["Defend", "Defend"]),
    probe("setup_early", "an early Strength power beats one Strike", STARTER + ["Inflame"], "jaw_worm",
          "Inflame", "Strike@0", seed=2, hp=30, prefix=["Defend", "Defend"]),
    probe("aoe_on_sentries", "AoE beats a single hit on three monsters", ["Strike", "Strike", "Cleave", "Defend", "Defend"],
          "three_sentries", "Cleave", "Strike@0", prefix=["Defend", "Defend"]),
    probe("aoe_on_slimes", "AoE beats a single hit on five slimes", ["Strike", "Strike", "Cleave", "Defend", "Defend"],
          "lots_of_slimes", "Cleave", "Strike@0", hp=12, prefix=["Defend", "Defend"]),
]


def build(p):
    c = sts.Combat(p["deck"], p["encounter"], seed=p["seed"], hp=p["hp"])
    for a in p["prefix"]:
        c.step(bench_decisions.decode_action(a))
    return c


def pick_values(options, values, p):
    """(value of the option holding `good`, of the one holding `bad`)."""
    def of(a):
        return next(v for acts, v in zip(options, values) if a in acts)
    return of(p["good"]), of(p["bad"])


def reference_pair(p):
    c = build(p)
    values, _ = bench_decisions.reference_search(c)
    return pick_values(bench_decisions.options_of(c), values, p)


def evaluator_pair(p, ev):
    s = sts.search(build(p), ev.evaluator, limit=bench_sets.LIMIT, features=ev.features)
    options = [[bench_decisions.encode_action(a) for a in acts] for acts, _ in s["options"]]
    return pick_values(options, [float(v) for _, v in s["options"]], p)


def probe_results(ev):
    """{"pass": [rate, lo, hi], "probes": {name: {good, bad, ref_good, ref_bad, pass}}}."""
    rows, score = {}, 0.0
    for p in PROBES:
        g, b = evaluator_pair(p, ev)
        rg, rb = reference_pair(p)
        ok = 0.5 if g == b else float(g > b)
        score += ok
        rows[p["name"]] = {"good": round(g, 6), "bad": round(b, 6), "ref_good": round(rg, 6),
                           "ref_bad": round(rb, 6), "pass": ok}
    return {"pass": wilson(score, len(PROBES)), "probes": rows}


def wilson(k, n, z=1.959964):
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    w = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(float(x), 6) for x in (p, c - w, c + w)]


# --- aliasing ----------------------------------------------------------------

def feature_keys(features, states):
    """One hashable key per state: its player and monster vectors and its
    card and hook rows as sorted multisets (the nets are order-invariant
    over rows; a row's card index is replaced by that card's vector)."""
    b = features.encode(states)
    cards = [[] for _ in states]
    card_vec = []
    for j, s in enumerate(np.asarray(b["card_state"])):
        v = (b["cards"][j].tobytes(), float(b["card_count"][j]), int(b["card_pile"][j]))
        card_vec.append(v)
        cards[s].append(v)
    rows = [[] for _ in states]
    entities = 1 + b["monsters"].shape[1]  # row_entity is state * entities + entity
    for j, s in enumerate(np.asarray(b["row_state"])):
        k, e = int(b["row_card"][j]), int(b["row_entity"][j])
        rows[s].append((b["rows"][j].tobytes(), card_vec[k] if k >= 0 else None, e - s * entities if e >= 0 else -1))
    return [(b["player"][i].tobytes(), b["monsters"][i].tobytes(), tuple(sorted(cards[i])),
             tuple(sorted(rows[i], key=repr))) for i in range(len(states))]


def aliased_pairs(keys, values, gap=ALIAS_GAP):
    """(i, j, spread) for every pair with equal keys whose values differ by
    more than `gap`, widest spread first."""
    out = [(i, j, abs(values[i] - values[j])) for i in range(len(keys)) for j in range(i + 1, len(keys))
           if keys[i] == keys[j] and abs(values[i] - values[j]) > gap]
    return sorted(out, key=lambda t: (-t[2], t[0], t[1]))


def option_keys(features, c):
    """Per option of `c` (reference grouping): (encoded actions, key), the
    key being its outcome states' feature keys with their probabilities."""
    opts = c.options(bench_decisions.REF["limit"])
    flat = [s for _, _, outs in opts for _, s in outs]
    keys = iter(feature_keys(features, flat))
    out = []
    for acts, _, outs in opts:
        key = tuple(sorted(((round(p, 9), next(keys)) for p, _ in outs), key=repr))
        out.append(([bench_decisions.encode_action(a) for a in acts], key))
    return out


def aliasing(features, decisions, reference, name):
    """The sibling audit over every saved decision of every tight half."""
    out = {"features": name, "gap": ALIAS_GAP, "halves": {}}
    for half, rows in reference["halves"].items():
        pairs = aliased = 0
        examples = []
        for r in rows:
            c = bench_decisions.replay(decisions[half][r["index"]])
            opts = option_keys(features, c)
            values = [next(v for ro, v in zip(r["options"], r["values"]) if set(ro) & set(acts)) for acts, _ in opts]
            n = len(opts)
            pairs += n * (n - 1) // 2
            found = aliased_pairs([k for _, k in opts], values)
            aliased += len(found)
            for i, j, spread in found[:max(0, ALIAS_EXAMPLES - len(examples))]:
                examples.append({"decision": r["index"], "spread": round(spread, 6), "board": c.render(),
                                 "options": [opts[i][0], opts[j][0]], "values": [values[i], values[j]]})
        out["halves"][half] = {"decisions": len(rows), "pairs": pairs, "aliased": aliased, "examples": examples}
    return out
