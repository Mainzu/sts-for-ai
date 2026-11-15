"""Decision diff (rates artifact hunt, 2026-10-31): where do a lean-thr net
and its lean-rates twin (same seed, one config key apart) choose
differently on The Guardian?

Fights: `tight_bosses` Guardian specs (both halves by default) whose deck
holds no Demon Form, first `--per-cell` per cell. For each pair
`--pairs thr.pt:rates.pt`, the thr net plays every fight with one-turn
search; at every decision the rates net and the heuristic search the same
state. Rows where the two nets' first actions differ record the context
(Guardian mode and powers, intent, player HP / energy / block, the
rates encoder's `turns_left_est`), each player's first action and card
type, its whole-turn plan, and each net's value gap (its own best minus
its value of the other net's first action).

Reading: a kind of disagreement that the heuristic sides with thr on, and
that recurs, is where the rates net's cost comes from.

    python scripts/analysis/decision_diff.py --pairs runs/<thr>/model.pt:runs/<rates>/model.pt ... --threads 3 --out results/probes/decision_diff-guardian.json
"""

import argparse
import collections
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import sts  # noqa: E402

TURN_LIMIT = sts.PLAY_TURN_LIMIT
_EV = {}
_TYPES = {}


def ev(spec):
    if spec not in _EV:
        _EV[spec] = bench.load_evaluator(spec)
    return _EV[spec]


def card_type(name):
    """attack / skill / power / status, read from the encoder's type columns."""
    if name is None:
        return "end_turn"
    if name not in _TYPES:
        f = sts.Features("effects")
        try:
            row = f.encode([sts.Combat([name] * 6, "cultist", seed=1, hp=80, character="ironclad")])["cards"][0]
            _TYPES[name] = next(t for t in ("attack", "skill", "power", "status") if row[f.card_names.index("type_" + t)] > 0)
        except Exception:
            _TYPES[name] = "other"
    return _TYPES[name]


def fights(per_cell, halves, encounter="the_guardian", exclude=("Demon Form",)):
    out = []
    for half in halves:
        taken = {}
        for s in json.load(open("data/bench/tight_bosses.json", encoding="utf-8"))["halves"][half]:
            if (s["encounter"] == encounter and not any(c.startswith(exclude) for c in s["deck"])
                    and taken.get(s["cell"], 0) < per_cell):
                taken[s["cell"]] = taken.get(s["cell"], 0) + 1
                out.append({**s, "half": half})
    return out


def monster_context(c):
    """Guardian's line from the render: powers in brackets, intent, block."""
    line = c.render().splitlines()[1]
    powers = {}
    m = re.search(r"\[([^\[\]]*)\]\s*$", line)
    if m:
        for part in m.group(1).split(","):
            bits = part.strip().rsplit(" ", 1)
            if len(bits) == 2 and bits[1].lstrip("-").isdigit():
                powers[bits[0]] = int(bits[1])
            elif bits[0]:
                powers[bits[0]] = 1
    intent = re.search(r"intent: (.*?)\s+\[", line) or re.search(r"intent: (.*)$", line)
    hp = re.search(r"HP (\d+)/", line)
    blk = re.search(r"Block (\d+)", line)
    mode = "defensive" if "SharpHide" in powers else "offensive"
    return {"mode": mode, "powers": powers, "intent": intent.group(1).strip() if intent else None,
            "hp": int(hp.group(1)) if hp else None, "block": int(blk.group(1)) if blk else None,
            "to_shift": powers.get("ModeShift")}


def player_context(c):
    head = c.render().splitlines()[0]
    g = lambda k: int(re.search(k + r" (\d+)", head).group(1))  # noqa: E731
    return {"hp": c.player_hp(), "block": g("Block"), "energy": g("Energy"), "turn": c.turn()}


def plan(option):
    return [None if a.is_end_turn else a.card for a in option[0]]


def first(option):
    a = option[0][0]
    return None if a.is_end_turn else a.card


def value_of_first(options, card, target):
    vs = [v for acts, v in options if (None if acts[0].is_end_turn else acts[0].card) == card and acts[0].target == target]
    return max(vs) if vs else None


def play(job):
    s, thr, rates = job
    c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"])
    rows, n = [], 0
    while not c.is_over() and c.turn() <= TURN_LIMIT:
        res = {}
        for name, spec in (("thr", thr), ("rates", rates), ("heuristic", "heuristic")):
            e = ev(spec)
            res[name] = sts.search(c, e.evaluator, features=e.features, limit=bench.LIMIT)
        best = {k: max(r["options"], key=lambda o: o[1]) for k, r in res.items()}
        n += 1
        a_t, a_r = best["thr"][0][0], best["rates"][0][0]
        key = lambda a: (None if a.is_end_turn else a.card, a.target)  # noqa: E731
        if key(a_t) != key(a_r):
            tl = ev(rates).features.encode([c])
            tl = float(tl["player"][0][ev(rates).features.player_names.index("turns_left_est")])
            gaps = {}
            for k, other in (("thr", a_r), ("rates", a_t)):
                v = value_of_first(res[k]["options"], *key(other))
                gaps[k] = None if v is None else float(best[k][1] - v)
            h = key(best["heuristic"][0][0])
            rows.append({
                "player": player_context(c), "monster": monster_context(c), "turns_left_est": tl,
                "thr": {"card": key(a_t)[0], "type": card_type(key(a_t)[0]), "plan": plan(best["thr"])},
                "rates": {"card": key(a_r)[0], "type": card_type(key(a_r)[0]), "plan": plan(best["rates"])},
                "heuristic": {"card": h[0], "type": card_type(h[0]), "plan": plan(best["heuristic"])},
                "heuristic_sides": "thr" if h == key(a_t) else "rates" if h == key(a_r) else "neither",
                "gap": gaps,
            })
        c.step(res["thr"]["action"])
    return {"won": bool(c.is_over() and c.won()), "turns": c.turn(), "decisions": n, "diffs": rows}


def summarise(results):
    allrows = [r for res in results.values() for f in res for r in f["diffs"]]
    dec = sum(f["decisions"] for res in results.values() for f in res)
    kinds = collections.Counter(f"{r['thr']['type']} -> {r['rates']['type']}" for r in allrows)
    by_kind = {}
    for k, cnt in kinds.most_common():
        rs = [r for r in allrows if f"{r['thr']['type']} -> {r['rates']['type']}" == k]
        by_kind[k] = {"n": cnt, "heuristic_sides": dict(collections.Counter(r["heuristic_sides"] for r in rs)),
                      "mode": dict(collections.Counter(r["monster"]["mode"] for r in rs))}
    by_mode = {}
    for mode in ("offensive", "defensive"):
        rs = [r for r in allrows if r["monster"]["mode"] == mode]
        by_mode[mode] = {"n": len(rs), "heuristic_sides": dict(collections.Counter(r["heuristic_sides"] for r in rs))}
    tl_bins = {}
    for lo, hi in ((0, 3), (3, 6), (6, 10), (10, 15), (15, 99)):
        rs = [r for r in allrows if lo <= r["turns_left_est"] < hi]
        tl_bins[f"{lo}-{hi}"] = {"n": len(rs), "heuristic_sides": dict(collections.Counter(r["heuristic_sides"] for r in rs))}
    # Who attacks: thr only, rates only, by Guardian mode and damage left to
    # Mode Shift (offensive) - "rates attacks into the shift" would show here.
    attacks = {}
    for r in allrows:
        ta, ra = r["thr"]["type"] == "attack", r["rates"]["type"] == "attack"
        if ta == ra:
            continue
        m = r["monster"]
        where = m["mode"] if m["mode"] == "defensive" else f"offensive, to_shift {'<=15' if (m['to_shift'] or 99) <= 15 else '>15'}"
        k = f"{'rates' if ra else 'thr'} attacks, {where}"
        attacks.setdefault(k, collections.Counter())[r["heuristic_sides"]] += 1
    cards = collections.Counter((r["thr"]["card"], r["rates"]["card"]) for r in allrows)
    return {
        "decisions": dec, "diffs": len(allrows), "diff_share": len(allrows) / max(dec, 1),
        "heuristic_sides": dict(collections.Counter(r["heuristic_sides"] for r in allrows)),
        "by_kind": by_kind, "by_mode": by_mode, "by_turns_left_est": tl_bins,
        "who_attacks": {k: dict(v) for k, v in sorted(attacks.items())},
        "top_card_pairs": [[f"{a} -> {b}", n] for (a, b), n in cards.most_common(15)],
        "won": {k: float(np.mean([f["won"] for f in res])) for k, res in results.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", required=True, help="thr.pt:rates.pt (the thr net plays)")
    ap.add_argument("--per-cell", type=int, default=4)
    ap.add_argument("--halves", nargs="+", default=["train", "held_out"])
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--limit-fights", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    specs = fights(args.per_cell, args.halves)
    if args.limit_fights:
        specs = specs[:args.limit_fights]
    print(f"{len(specs)} Guardian fights without Demon Form; pairs {args.pairs}", flush=True)
    results = {}
    with ProcessPoolExecutor(args.threads) as pool:
        for pair in args.pairs:
            thr, rates = pair.split(":")
            t = time.time()
            results[pair] = list(pool.map(play, [(s, thr, rates) for s in specs]))
            d = sum(len(f["diffs"]) for f in results[pair])
            print(f"{pair}: {time.time() - t:.0f}s, {d} diffs", flush=True)
    summary = summarise(results)
    print(json.dumps(summary, indent=1), flush=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"args": vars(args), "summary": summary,
               "fights": [{"spec": s, **{p: results[p][i] for p in results}} for i, s in enumerate(specs)]},
              open(args.out, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
