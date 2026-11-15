"""Demon Form probe (Next D, big-picture review 2026-10-31 direction 4): on
held-out boss fights whose deck holds Demon Form, how often and on which
turn does each player play it, and how much does each evaluator think
playing it is worth?

Fights: every held-out boss spec with Demon Form in its deck from
`tight_bosses` (Hexaghost, The Guardian) and `tight2` (Slime Boss), first
`--per-cell` per cell. Each player plays every fight with one-turn search.
At every decision where some option plays Demon Form (or Demon Form+), the
state is also scored by the other evaluators, giving per evaluator the
best Demon-Form option's value minus the best other option's value (the
"gain"; > 0 means that evaluator would play it now).

Reading: a net that under-plays Demon Form (later, or never, where the
heuristic plays it and wins) points to horizon or rate features; one that
over-plays it into lethal points elsewhere.

    python scripts/analysis/demon_form_probe.py --nets runs/<r2 s1>/model.pt ... --threads 6 --out results/probes/demon_form.json

Other cards: `--cards Inflame Metallicize` probes those instead (any of them
counts as "the card"); `--encounters the_guardian --halves train held_out
--exclude "Demon Form"` picks the fights (deck holds a probed card and no
excluded one).
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import sts  # noqa: E402

TURN_LIMIT = sts.PLAY_TURN_LIMIT  # as play's turn limit: a combat still running is a loss
_EV = {}  # per worker process


def is_df(card, cards=("Demon Form",)):
    return card is not None and card.startswith(tuple(cards))


def fights(per_cell, cards=("Demon Form",), exclude=(), encounters=None, halves=("held_out",)):
    out = []
    for name in ("tight_bosses", "tight2"):
        for half in halves:
            d = json.load(open(f"data/bench/{name}.json", encoding="utf-8"))["halves"][half]
            taken = {}
            for s in d:
                if (s["group"] == "boss" and any(is_df(c, cards) for c in s["deck"])
                        and not any(is_df(c, exclude) for c in s["deck"])
                        and (encounters is None or s["encounter"] in encounters)
                        and taken.get(s["cell"], 0) < per_cell):
                    taken[s["cell"]] = taken.get(s["cell"], 0) + 1
                    out.append({**s, "set": name, "half": half})
    return out


def ev(spec):
    if spec not in _EV:
        _EV[spec] = bench.load_evaluator(spec)
    return _EV[spec]


def gain(options, cards):
    """Best Demon-Form option's value minus the best other option's (None if
    one side is empty)."""
    df = [v for acts, v in options if any(is_df(a.card, cards) for a in acts)]
    other = [v for acts, v in options if not any(is_df(a.card, cards) for a in acts)]
    return float(max(df) - max(other)) if df and other else None


def play(job):
    """One fight played by `player`; at each Demon-Form decision, every
    evaluator's gain. Returns {won, score, turns, df_turns: [...]} where each
    df row is {turn, hp, played, gains: {evaluator: gain}}."""
    s, player, evaluators, cards = job
    c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"])
    rows = []
    while not c.is_over() and c.turn() <= TURN_LIMIT:
        e = ev(player)
        r = sts.search(c, e.evaluator, features=e.features, limit=bench.LIMIT)
        g = gain(r["options"], cards)
        if g is not None:
            gains = {player: g}
            for other in evaluators:
                if other != player:
                    o = ev(other)
                    gains[other] = gain(sts.search(c, o.evaluator, features=o.features, limit=bench.LIMIT)["options"], cards)
            best = max(r["options"], key=lambda o: o[1])[0]
            rows.append({"turn": c.turn(), "hp": c.player_hp(), "played": any(is_df(a.card, cards) for a in best),
                         "gains": gains})
        c.step(r["action"])
    won = c.is_over() and c.won()
    return {"won": bool(won), "score": c.score() if c.is_over() else 0.0, "turns": c.turn(), "df": rows}


def summarise(specs, res, evaluators):
    out = {}
    for p in evaluators:
        rs = res[p]
        avail = [row for r in rs for row in r["df"]]
        first = [next((row["turn"] for row in r["df"] if row["played"]), None) for r in rs]
        offered = [r for r in rs if r["df"]]
        out[p] = {
            "fights": len(rs), "won": float(np.mean([r["won"] for r in rs])),
            "fights_offered": len(offered),
            "played_share_of_offers": float(np.mean([row["played"] for row in avail])) if avail else None,
            "never_played_when_offered": float(np.mean([f is None for f, r in zip(first, rs) if r["df"]])) if offered else None,
            "first_turn_mean": float(np.mean([f for f in first if f is not None])) if any(f is not None for f in first) else None,
            "first_turn_hist": {str(t): int(sum(f == t for f in first)) for t in sorted({f for f in first if f is not None})},
            "won_if_played": float(np.mean([r["won"] for f, r in zip(first, rs) if f is not None])) if any(f is not None for f in first) else None,
            "won_if_not_played": float(np.mean([r["won"] for f, r in zip(first, rs) if f is None and r["df"]])) if any(f is None and r["df"] for f, r in zip(first, rs)) else None,
        }
    # Cross-scoring on the heuristic's own first-offer states: each
    # evaluator's gain, and agreement on "play it now".
    first_offer = [r["df"][0] for r in res[evaluators[0]] if r["df"]]
    out["gain_on_first_offer"] = {e: {"mean": float(np.mean([row["gains"][e] for row in first_offer if row["gains"].get(e) is not None])),
                                     "play_share": float(np.mean([row["gains"][e] > 0 for row in first_offer if row["gains"].get(e) is not None]))}
                                  for e in evaluators}
    by_enc = {}
    for i, s in enumerate(specs):
        by_enc.setdefault(s["encounter"], []).append(i)
    out["won_by_encounter"] = {enc: {p: float(np.mean([res[p][i]["won"] for i in idx])) for p in evaluators}
                               for enc, idx in sorted(by_enc.items())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nets", nargs="+", required=True, help="net .pt paths; the heuristic always plays first")
    ap.add_argument("--per-cell", type=int, default=4)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--limit-fights", type=int, default=0)
    ap.add_argument("--cards", nargs="+", default=["Demon Form"], help="card name prefixes probed")
    ap.add_argument("--exclude", nargs="*", default=[], help="skip decks holding any of these")
    ap.add_argument("--encounters", nargs="*", default=None)
    ap.add_argument("--halves", nargs="+", default=["held_out"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    specs = fights(args.per_cell, args.cards, args.exclude, args.encounters, args.halves)
    if args.limit_fights:
        specs = specs[:args.limit_fights]
    evaluators = ["heuristic"] + args.nets
    print(f"{len(specs)} boss fights ({' '.join(args.halves)}) with {args.cards}; players {evaluators}", flush=True)
    res = {}
    # not multiprocessing.Pool: a worker that dies (out of memory) hangs it
    with ProcessPoolExecutor(args.threads) as pool:
        for p in evaluators:
            t = time.time()
            res[p] = list(pool.map(play, [(s, p, evaluators, tuple(args.cards)) for s in specs]))
            print(f"{p}: {time.time() - t:.0f}s, won {sum(r['won'] for r in res[p])}/{len(specs)}", flush=True)
    summary = summarise(specs, res, evaluators)
    print(json.dumps(summary, indent=1), flush=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"args": vars(args), "summary": summary,
               "fights": [{"spec": s, **{p: res[p][i] for p in evaluators}} for i, s in enumerate(specs)]},
              open(args.out, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
