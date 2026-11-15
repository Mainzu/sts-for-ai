"""Pack cards zero-shot read (docs/specs/act1-cards-zero-shot.md): each base
card of a pack file, three copies in tight2's held-out elite and boss decks
(Strikes, then Defends, swapped), against the same fight without it; per card
and leaf, (net - heuristic) with the card minus the same without it, paired
by cell, in wins and end HP.

    .venv/Scripts/python scripts/analysis/pack_cards_read.py play --players heuristic --threads 3
    .venv/Scripts/python scripts/analysis/pack_cards_read.py play --players runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpb0.01
    .venv/Scripts/python scripts/analysis/pack_cards_read.py table
"""

import argparse
import json
import os
import re
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import selfplay  # noqa: E402

PACK = "content/packs/act1-ironclad.json"
TIGHT2 = "data/bench/tight2.json"
OUT_DIR = "results/pack_cards/act1"
NET = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpb0.01"
GROUPS = ("elite", "boss")
SEEDS = 3
COPIES = 3
WITHOUT = "without"
TS_POWERS = {"Demon Form", "Brutality", "gen:Berserk"}  # powers with a turn-start hook
# Written before any fight (the charter's classes).
PREDICTION = {
    **{c: "in-turn: level" for c in ("Disarm", "Ghostly Armor", "Intimidate", "Searing Blow", "Seeing Red",
                                     "Shockwave", "Bludgeon", "Feed", "Impervious", "Offering")},
    "Berserk": "turn-start: costs on plain, open on tsl1",
    **{c: "status later: open" for c in ("Power Through", "Reckless Charge", "Immolate")},
    **{c: "unreadable trigger: open" for c in ("Double Tap", "Flame Barrier")},
    **{c: "new atoms (C1): level" for c in ("True Grit", "Burning Pact", "Second Wind", "Sever Soul",
                                            "Fiend Fire", "Exhume")},
}


def base_cards(pack):
    return [c["id"] for c in pack["cards"] if not c["id"].endswith("+")]


def fights(held, cards, seeds=SEEDS, copies=COPIES, groups=GROUPS):
    """The read's fights: per elite/boss cell its first `seeds` fights, as
    set `without` and once per card with `copies` Strikes, then Defends,
    turned into the card."""
    cells = {}
    for s in held:
        if s["group"] in groups:
            cells.setdefault(s["cell"], []).append(s)
    out = []
    for cell in sorted(cells):
        for k, s in enumerate(cells[cell][:seeds]):
            out.append({**s, "set": WITHOUT, "k": k})
            for card in cards:
                deck, n = list(s["deck"]), 0
                for base in ("Strike", "Defend"):
                    while n < copies and base in deck:
                        deck[deck.index(base)] = "gen:" + card
                        n += 1
                assert n == copies, (cell, card)
                out.append({**s, "deck": deck, "set": card, "k": k})
    return out


def turn_start(deck):
    return bool({x.rstrip("+") for x in deck} & TS_POWERS)


def hand_cards(state):
    line = next(x for x in str(state).splitlines() if x.startswith("Hand:"))
    names = [x.strip() for x in line[5:].split(",") if x.strip()]
    return {n.rsplit(" x", 1)[0] if n.rsplit(" x", 1)[-1].isdigit() else n for n in names}


def play_stats(states, actions, card):
    """(turns the card was in hand at a decision, turns it was played)."""
    name = "gen:" + card
    in_hand = played = 0
    pat = re.compile(rf"Action\({re.escape(name)}\+?( ->|\))")
    held = done = False
    for st, a in zip(states, actions):
        held |= any(h.rstrip("+") == name for h in hand_cards(st))
        done |= bool(pat.match(str(a)))
        if a.is_end_turn:
            in_hand += held
            played += done
            held = done = False
    return in_hand + held, played + done


def player_name(p):
    if p == "heuristic":
        return p
    net, at, settings = p.partition(".pt@")
    rid = os.path.basename(os.path.dirname(net + ".pt" if at else p))
    return rid + ("-" + settings.replace("@", "-") if at else "")


def play(args):
    pack, h = selfplay.load_content(args.pack)
    cards = args.cards or base_cards(pack)
    with open(TIGHT2, encoding="utf-8") as f:
        held = json.load(f)["halves"]["held_out"]
    fs = fights(held, cards, args.seeds)
    if args.limit:
        keep = set(sorted({f["cell"] for f in fs})[:args.limit])
        fs = [f for f in fs if f["cell"] in keep]
    search = {"limit": bench.LIMIT, "threads": args.threads}
    os.makedirs(args.out_dir, exist_ok=True)
    for p in args.players:
        out = os.path.join(args.out_dir, player_name(p) + ".json")
        if os.path.exists(out):
            print(f"{out} exists, skipped", flush=True)
            continue
        ev = None if p == "heuristic" else bench.load_evaluator(p)
        only = [i for i, f in enumerate(fs) if "@tsl1" not in p or turn_start(f["deck"])]
        won, hp = [None] * len(fs), [None] * len(fs)
        in_hand, played = [None] * len(fs), [None] * len(fs)
        t = time.time()
        for s in [WITHOUT] + list(cards):  # one set at a time keeps recorded states small
            idx = [i for i in only if fs[i]["set"] == s]
            res = bench.run_specs([fs[i] for i in idx], ev=ev, record=ev is None, search=search)
            for i, r in zip(idx, res):
                won[i], hp[i] = float(r["won"]), float(r["hp_end"])
                if ev is None and s != WITHOUT:
                    in_hand[i], played[i] = play_stats(r["states"], r["actions"], s)
            print(f"  {s}: {len(idx)} fights ({time.time() - t:.0f}s)", flush=True)
        rec = {"player": p, "pack": args.pack, "content_hash": h, "seeds": args.seeds, "limit": args.limit,
               "keys": [[f["cell"], f["set"], f["k"]] for f in fs],
               "groups": [f["group"] for f in fs], "won": won, "hp_end": hp}
        if ev is None:
            rec.update(in_hand=in_hand, played=played)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rec, f)
        print(f"{out}: {len(only)} fights ({time.time() - t:.0f}s)", flush=True)


def paired(keys, groups, heur, net, card):
    """{all|elite|boss: {cells, d, se}}: per cell, mean over seeds of
    (net - heur) on `card`'s set minus the same on `without`."""
    per = {}
    for (cell, s, _), g, a, b in zip(keys, groups, heur, net):
        if s in (card, WITHOUT):
            per.setdefault(cell, {"g": g}).setdefault(s, []).append(b - a)
    out = {}
    for part in ("all",) + GROUPS:
        d = np.array([np.mean(v[card]) - np.mean(v[WITHOUT]) for v in per.values()
                      if card in v and (part == "all" or v["g"] == part)])
        out[part] = {"cells": len(d), "d": float(d.mean()) if len(d) else None,
                     "se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None}
    return out


def table(args):
    load = lambda n: json.load(open(os.path.join(args.out_dir, n + ".json"), encoding="utf-8"))  # noqa: E731
    heur, plain, tsl = load("heuristic"), load(player_name(args.net)), load(player_name(args.net + "@tsl1"))
    keys = heur["keys"]
    assert plain["keys"] == keys == tsl["keys"]
    groups = heur["groups"]
    leaves = {"plain": plain, "tsl1": {m: [p if t is None else t for p, t in zip(plain[m], tsl[m])]
                                       for m in ("won", "hp_end")}}
    cards = [c for c in dict.fromkeys(s for _, s, _ in keys) if c != WITHOUT]
    rows = {}
    for card in cards:
        ih = sum(x for (_, s, _), x in zip(keys, heur["in_hand"]) if s == card)
        pl = sum(x for (_, s, _), x in zip(keys, heur["played"]) if s == card)
        rows[card] = {"prediction": PREDICTION.get(card), "heur_play_rate": pl / ih if ih else None,
                      "in_hand_turns": ih,
                      **{f"{leaf}_{m}": paired(keys, groups, heur[m], r[m], card)
                         for leaf, r in leaves.items() for m in ("won", "hp_end")}}
        w = rows[card]["tsl1_won"]["all"]
        rows[card]["costs_tsl1"] = w["se"] is not None and w["d"] < -2 * w["se"]
        w = rows[card]["plain_won"]["all"]
        rows[card]["costs_plain"] = w["se"] is not None and w["d"] < -2 * w["se"]
    out = os.path.join(args.out_dir, "table.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"net": args.net, "content_hash": heur["content_hash"], "seeds": heur["seeds"], "rows": rows},
                  f, indent=1)
    fmt = lambda r: f"{r['d']:+.3f} ({r['se']:.3f})" if r["se"] is not None else "-"  # noqa: E731
    print("| card | prediction | heur plays | wins plain | wins tsl1 | HP plain | HP tsl1 | "
          "wins tsl1 elite | wins tsl1 boss |")
    print("|---|---|---|---|---|---|---|---|---|")
    for card, r in rows.items():
        rate = f"{r['heur_play_rate']:.2f}" if r["heur_play_rate"] is not None else "-"
        print(f"| {card}{' *' if r['costs_tsl1'] else ''} | {r['prediction']} | {rate} | "
              f"{fmt(r['plain_won']['all'])} | {fmt(r['tsl1_won']['all'])} | {fmt(r['plain_hp_end']['all'])} | "
              f"{fmt(r['tsl1_hp_end']['all'])} | {fmt(r['tsl1_won']['elite'])} | {fmt(r['tsl1_won']['boss'])} |")
    print(f"-> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("play", "table"))
    ap.add_argument("--pack", default=PACK)
    ap.add_argument("--cards", nargs="+", default=None, help="play: these base cards only")
    ap.add_argument("--players", nargs="+", default=[])
    ap.add_argument("--net", default=NET, help="table: the plain player; its @tsl1 twin is the second leaf")
    ap.add_argument("--seeds", type=int, default=SEEDS)
    ap.add_argument("--limit", type=int, default=0, help="play: first N cells only (smoke)")
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    {"play": play, "table": table}[args.cmd](args)


if __name__ == "__main__":
    main()
