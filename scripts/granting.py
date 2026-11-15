"""Check 9: can the agent value granting a power it never saw, when that
power is built from triggers, conditions and effects it has seen?

Nets: the effects and ids nets from check 6 (trained without check 9's
held-out cards: Metallicize, Demon Form, Rage, Go for the Eyes, FTL) and a
reference effects net trained the same way on a pool that includes them.

Test decisions: every decision of search + heuristic games, on decks holding
at least 2 held-out cards, where a held-out card is playable. At each one,
each net's search scores the options; a held-out card's gain is its best
option's score minus the best option that doesn't play it. Pass: over
Metallicize, Demon Form, Rage and Go for the Eyes, the mean absolute
difference from the reference net's gain is >= 20% lower for the effects net
than for the ids net. FTL (a condition no training card uses) is reported,
not gated. Also reported: how often each net's search plays the held-out
card when the reference net's does, and Search win rate / HP lost on those
decks. Exits 1 if the bar isn't met.

    python scripts/granting.py [--retrain] [--n-games 300]
"""

import argparse
import os
import sys
import time

import numpy as np
import torch

import generalise
import selfplay
import stsnet
import sts
import train

GROUPS = selfplay.GROUPS
HELD9 = set(sts.held_out_card_names())
GATED = ["Metallicize", "Demon Form", "Rage", "Go for the Eyes"]
REPORTED = ["FTL"]
REF_POOL = selfplay.TRAIN_POOL + sorted(HELD9, key=sts.all_card_names().index)
REF_PATH = os.path.join(train.MODELS, "value_reference.pt")


def base(name):
    return sts.base_name(name)


def ref_train_deck(rng):
    """Starter + 5 cards from the training pool plus check 9's held-out cards."""
    return selfplay.STARTER + list(rng.choice(REF_POOL, 5))


def check9_deck(rng):
    """Starter + 5 cards from the same pool, at least 2 of them held out."""
    while True:
        extra = list(rng.choice(REF_POOL, 5))
        if sum(c in HELD9 for c in extra) >= 2:
            return selfplay.STARTER + extra


def gains(options, cards):
    """{card: best score of an option playing it − best score of an option
    that doesn't} for each card in `cards`; `options` is search's
    [(actions, value)]."""
    out = {}
    for c in cards:
        with_c = [v for acts, v in options if any(a.card == c for a in acts)]
        without = [v for acts, v in options if not any(a.card == c for a in acts)]
        if with_c and without:
            out[c] = max(with_c) - max(without)
    return out


def mad(x, ref):
    return float(np.mean(np.abs(np.asarray(x) - np.asarray(ref))))


def passes(effects_mad, ids_mad):
    return effects_mad <= 0.8 * ids_mad


def load_reference(retrain):
    """The reference effects net, trained like check 6's effects net (same
    seeds, sizes and budget) on decks that may hold check 9's cards."""
    if not retrain and os.path.exists(REF_PATH):
        return stsnet.load(REF_PATH)
    tr = selfplay.generate("train_ref", 10000, 1, ref_train_deck, modes=("effects",))["effects"]
    va = selfplay.generate("val_ref", 1000, 2, ref_train_deck, modes=("effects",))["effects"]
    t = time.perf_counter()
    model, norm, hist = train.train("effects", tr, va)
    print(f"trained reference net in {time.perf_counter() - t:.0f}s")
    meta = {"card_repr": "effects", **selfplay.meta_vocab("effects"), "held_out": selfplay.HELD_OUT,
            "held_out_check9": [], "val_mse": min(hist), "format": selfplay.FORMAT}
    os.makedirs(train.MODELS, exist_ok=True)
    stsnet.save(REF_PATH, model, norm, meta)
    return stsnet.load(REF_PATH)


def decisions(specs):
    """(state, playable held-out card names) for every recorded decision of
    search + heuristic games where a held-out card is playable."""
    out = []
    for r in sts.run("search", specs, record=True, limit=selfplay.LIMIT):
        for s in r["states"]:
            cards = {a.card for a in s.legal_actions() if a.card in HELD9}
            if cards:
                out.append((s, cards))
    return out


def score_decisions(nets, decs):
    """{net: [(gains dict, chosen card or None)]} per decision."""
    torch.set_num_threads(4)
    out = {}
    for name, (m, nm, meta) in nets.items():
        t = time.perf_counter()
        ev, feats = stsnet.Evaluator(m, nm), stsnet.features_for(meta)
        rows = []
        for s, cards in decs:
            r = sts.search(s, ev, features=feats, limit=selfplay.LIMIT)
            rows.append((gains(r["options"], cards), r["action"].card))
        out[name] = rows
        print(f"  {name}: {len(decs)} searches, {time.perf_counter() - t:.0f}s")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retrain", action="store_true", help="ignore the saved reference net")
    ap.add_argument("--n-games", type=int, default=300, help="combats per group")
    args = ap.parse_args()

    t0 = time.perf_counter()
    nets = {m: stsnet.load(train.model_path(m)) for m in ("effects", "ids")}
    for m, (_, _, meta) in nets.items():
        assert meta.get("format") == selfplay.FORMAT, f"{m} net is from an older format; run generalise.py --retrain"
    assert not HELD9 & set(nets["ids"][2]["known_cards"]), "the ids net knows a check 9 card"
    nets["reference"] = load_reference(args.retrain)

    specs, groups = selfplay.make_specs(args.n_games, 9, check9_deck)
    t = time.perf_counter()
    decs = decisions(specs)
    print(f"{len(specs)} games, {len(decs)} decisions with a held-out card playable ({time.perf_counter() - t:.0f}s)")
    scored = score_decisions(nets, decs)

    # Per (decision, card): each net's gain. Grouped by base card name.
    pairs = {b: {n: [] for n in nets} for b in GATED + REPORTED}
    for i, (_, cards) in enumerate(decs):
        for c in cards:
            if all(c in scored[n][i][0] for n in nets):
                for n in nets:
                    pairs[base(c)][n].append(scored[n][i][0][c])

    print("\ngain = score(play the card) - best other option, from each net's search; "
          "MAD = mean |gain - reference gain|")
    print(f"{'card':<16} {'pairs':>6} {'ref gain':>9} {'effects':>8} {'ids':>8} {'MAD eff':>8} {'MAD ids':>8} {'eff vs ids':>11}")
    pooled = {n: [] for n in nets}
    for b in GATED + REPORTED:
        p = pairs[b]
        if not p["reference"]:
            print(f"{b:<16} {0:>6}")
            continue
        e, i = mad(p["effects"], p["reference"]), mad(p["ids"], p["reference"])
        tag = "" if b in GATED else "  (reported)"
        print(f"{b:<16} {len(p['reference']):>6} {np.mean(p['reference']):>+9.4f} {np.mean(p['effects']):>+8.4f} "
              f"{np.mean(p['ids']):>+8.4f} {e:>8.4f} {i:>8.4f} {(1 - e / i) * 100:>+10.1f}%{tag}")
        if b in GATED:
            for n in nets:
                pooled[n] += p[n]
    e_mad, i_mad = mad(pooled["effects"], pooled["reference"]), mad(pooled["ids"], pooled["reference"])
    print(f"{'gated (pooled)':<16} {len(pooled['reference']):>6} {np.mean(pooled['reference']):>+9.4f} "
          f"{np.mean(pooled['effects']):>+8.4f} {np.mean(pooled['ids']):>+8.4f} {e_mad:>8.4f} {i_mad:>8.4f} "
          f"{(1 - e_mad / i_mad) * 100:>+10.1f}%")

    print("\nwhen the reference net's search plays a held-out card, how often each net's search plays it too")
    print(f"{'card':<16} {'times':>6} {'effects':>8} {'ids':>8}")
    for b in GATED + REPORTED:
        idx = [k for k, (_, ch) in enumerate(scored["reference"]) if ch in HELD9 and base(ch) == b]
        if not idx:
            print(f"{b:<16} {0:>6}")
            continue
        agree = {n: np.mean([scored[n][k][1] == scored["reference"][k][1] for k in idx]) * 100 for n in ("effects", "ids")}
        print(f"{b:<16} {len(idx):>6} {agree['effects']:>7.1f}% {agree['ids']:>7.1f}%")

    print(f"\nSearch on check 9 decks, {args.n_games} combats per group (reported, not gated)")
    wt = generalise.win_table(nets, args.n_games, specs=(specs, groups))
    print(f"{'evaluator':<10} " + " ".join(f"{g + ' win%':>12} {'HP lost':>8}" for g in GROUPS + ["all"]))
    for name, row in wt.items():
        print(f"{name:<10} " + " ".join(f"{row[g][0] * 100:>12.1f} {row[g][1]:>8.1f}" for g in GROUPS + ["all"]))

    ok = passes(e_mad, i_mad)
    print(f"\ncheck 9: gain MAD vs reference, effects {e_mad:.4f} vs ids {i_mad:.4f} "
          f"({(1 - e_mad / i_mad) * 100:.1f}% lower, need >= 20%): {'pass' if ok else 'FAIL'}")
    print(f"total {time.perf_counter() - t0:.0f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
