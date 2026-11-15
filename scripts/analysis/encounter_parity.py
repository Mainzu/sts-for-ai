"""Parity replay of two versions of one encounter (docs/research/act1-inventory.md,
"Thugs parity replay"): every floor of the given headline gauntlet files
that met either version is rebuilt (the deck the sequence brought, its
arrival HP) and played on both versions on common seeds, one turn deep, so
only the encounter differs. Pack fights are split by the monsters drawn
(read from the starting board), which tells a harder draw (the pack's extra
slot options) from a harder copy of a shared monster.

    .venv/Scripts/python scripts/analysis/encounter_parity.py play --files a.json b.json \\
        --pack content/packs/act1-monsters.json --a exordium_thugs --b "gen:Exordium Thugs" --out results/parity/thugs.json
    .venv/Scripts/python scripts/analysis/encounter_parity.py read results/parity/thugs.json
"""

import argparse
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gauntlet  # noqa: E402

PLAYER = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpb0.01"


def floor_decks(rows, settings, seqs, names):
    """One entry per floor of `rows` whose encounter is in `names`: the deck
    brought to it (start deck plus every pick before it), arrival HP and
    the floor's own seed."""
    import sts
    out = []
    for r in rows:
        s = seqs[r["i"]]
        deck = list(sts.starter_deck(s["character"])) if settings.get("start") == "starter" else list(s["deck"])
        for k, f in enumerate(r["floors"]):
            if f["encounter"] in names:
                out.append({"i": r["i"], "floor": k, "from": f["encounter"], "character": s["character"],
                            "deck": list(deck), "hp": int(f["hp_start"]), "seed": gauntlet.SEED_BASE + r["i"] * 100 + k})
            deck += [f["took"]] if f.get("took") else []
            deck += [x["took"] for x in f.get("extra", []) if x.get("took")]
    return out


def drawn(enc, deck, seed, character):
    """The monster names on the starting board of `enc` at `seed`."""
    import sts
    board = sts.Combat(deck, enc, seed=seed, character=character).render()
    return sorted(re.findall(r"^\s*\[\d+\]\s+(.+?)\s+HP\s", board, re.M))


def play_cmd(args):
    import ladder
    import selfplay
    selfplay.load_content(args.pack)
    decks = []
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            src = json.load(f)
        seqs = {s["i"]: s for s in gauntlet.sequences(max(r["i"] for r in src["sequences"]) + 1, 0,
                                                       ladder.pool_cells())}
        for d in floor_decks(src["sequences"], src["settings"], seqs, {args.a, args.b}):
            decks.append({**d, "file": path})
    if args.limit:
        decks = decks[:args.limit]
    specs, meta = [], []
    for n, d in enumerate(decks):
        for j in range(args.seeds):
            seed = d["seed"] + 1000 * j  # j = 0 is the floor's own seed
            for enc in (args.a, args.b):
                specs.append({"encounter": enc, "deck": d["deck"], "seed": seed, "hp": d["hp"],
                              "character": d["character"], "group": "hallway"})
                meta.append((n, j, enc, drawn(enc, d["deck"], seed, d["character"])))
    print(f"{len(decks)} floors, {len(specs)} fights", flush=True)
    res = ladder.play_bench(specs, args.player, args.threads)
    fights = [{"deck": n, "j": j, "enc": enc, "monsters": mon, "won": bool(r["won"]),
               "lost": d_hp - (r["hp_end"] if r["won"] else 0)}
              for (n, j, enc, mon), r, d_hp in zip(meta, res, (s["hp"] for s in specs))]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"settings": {"files": args.files, "pack": args.pack, "a": args.a, "b": args.b,
                                "player": args.player, "seeds": args.seeds},
                   "decks": [{k: d[k] for k in ("file", "i", "floor", "from", "hp")} for d in decks],
                   "fights": fights}, f, indent=0)
    print(args.out)


def mean_se(x):
    x = np.asarray(x, float)
    return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else 0.0


def read_cmd(args):
    with open(args.out, encoding="utf-8") as f:
        d = json.load(f)
    a, b = d["settings"]["a"], d["settings"]["b"]
    fights = d["fights"]
    by = {}
    for x in fights:
        by.setdefault((x["deck"], x["j"]), {})[x["enc"]] = x
    pairs = [v for v in by.values() if a in v and b in v]
    print(f"{len(d['decks'])} floors x {d['settings']['seeds']} seeds; player {d['settings']['player']}")
    for name, sel in (("all", lambda v: True),) + tuple(
            (f"from {src}", (lambda s: lambda v: d["decks"][v[a]["deck"]]["from"] == s)(src))
            for src in sorted({x["from"] for x in d["decks"]})):
        sub = [v for v in pairs if sel(v)]
        if not sub:
            continue
        la, lb = mean_se([v[a]["lost"] for v in sub]), mean_se([v[b]["lost"] for v in sub])
        dl = mean_se([v[b]["lost"] - v[a]["lost"] for v in sub])
        dw = mean_se([v[b]["won"] - v[a]["won"] for v in sub])
        print(f"{name} ({len(sub)} pairs): HP lost {a} {la[0]:.2f} ({la[1]:.2f}), {b} {lb[0]:.2f} ({lb[1]:.2f}); "
              f"b - a {dl[0]:+.2f} ({dl[1]:.2f}); wins b - a {dw[0]:+.3f} ({dw[1]:.3f})")
    print("\nHP lost by the monsters drawn (each version alone, all fights):")
    for enc in (a, b):
        groups = {}
        for x in fights:
            if x["enc"] == enc:
                groups.setdefault(" + ".join(x["monsters"]), []).append(x)
        for k, xs in sorted(groups.items(), key=lambda g: -len(g[1])):
            m, se = mean_se([x["lost"] for x in xs])
            print(f"  {enc:22s} {k:40s} n {len(xs):5d}  lost {m:6.2f} ({se:.2f})  deaths {1 - np.mean([x['won'] for x in xs]):.3f}")
    print("\nSlot 2 alone (the monster that is not a louse or a medium slime):")
    for enc in (a, b):
        groups = {}
        for x in fights:
            if x["enc"] == enc:
                rest = [m for m in x["monsters"] if not re.search(r"Louse|Slime \(M\)", m)] or ["-"]
                groups.setdefault(" + ".join(rest), []).append(x["lost"])
        for k, xs in sorted(groups.items()):
            m, se = mean_se(xs)
            print(f"  {enc:22s} {k:20s} n {len(xs):5d}  lost {m:6.2f} ({se:.2f})")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("--files", nargs="+", required=True, help="headline gauntlet files whose floors give decks and HP")
    p.add_argument("--pack", required=True, help="content pack holding the pack version")
    p.add_argument("--a", required=True, help="first encounter name (e.g. the official one)")
    p.add_argument("--b", required=True, help="second encounter name (e.g. gen:<pack id>)")
    p.add_argument("--player", default=PLAYER)
    p.add_argument("--seeds", type=int, default=6)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--limit", type=int, default=0, help="first N floors only (smoke)")
    p.add_argument("--out", required=True)
    r = sub.add_parser("read")
    r.add_argument("out")
    args = ap.parse_args(argv)
    (play_cmd if args.cmd == "play" else read_cmd)(args)


if __name__ == "__main__":
    main()
