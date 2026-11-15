"""Mutated cards (docs/specs/mutated-cards.md, yardstick-cards step 3): the
gauntlet's elite and boss fights replayed with one official card of the
deck swapped for a pack variant (the owner's boon + bane pairs), played by
the heuristic and the product net one turn deep (plain leaf and @tsl1) on
common seeds. Each modifier is read against its parent's pack copy, so
only the numbers differ; `read` gives per modifier the win and HP-lost
change and the novelty cost (net minus heuristic), by fight type.

    .venv/Scripts/python scripts/analysis/mutate_cards.py play --starts 200 --seeds 8 --players heuristic,one,tsl --threads 3 --out results/mutate/cards-a.json
    .venv/Scripts/python scripts/analysis/mutate_cards.py read results/mutate/cards-a.json
    .venv/Scripts/python scripts/analysis/mutate_cards.py pack --out data/bench/mutated_cards_pack.json
    .venv/Scripts/python scripts/analysis/mutate_cards.py adapted results/mutate/cards-a.json results/mutate/cards-adapt-inflame-turn1-s*.json

`adapted` (docs/specs/cards-adapted-column.md): burst nets' reads (`play
--net`) against the zero-shot file on the same starts and seeds.
"""

import argparse
import copy
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import bench  # noqa: E402
import bias_audit as ba  # noqa: E402
import mutate_monsters as mm  # noqa: E402
import sts  # noqa: E402

CARDS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "content", "cards.json")
PLAYERS = {"heuristic": None, "one": mm.NET + "@hpb0.01", "tsl": mm.NET + "@hpb0.01@tsl1",
           # the projected leaf (docs/specs/projected-leaf.md): @tsl1 plus k projected ticks
           "pl2": mm.NET + "@hpb0.01@tsl1@pl2", "pl3": mm.NET + "@hpb0.01@tsl1@pl3"}
NOVELTY = ("one", "tsl", "pl2", "pl3")
PROJECTED = ("pl2", "pl3")
CONTROL = "bash-c1-d5"


def _apply(power, amount):
    return {"Apply": {"power": power, "amount": amount, "target": "Me"}}


# name -> (parent card, the variant's changed fields). Fixed before the
# first read (the spec's table); the plain control's parts land inside the turn.
MODS = {
    CONTROL: ("Bash", {"cost": 1, "effects": [{"Damage": {"amount": 5, "hits": 1, "target": "Opponent"}},
                                              {"Apply": {"power": "Vulnerable", "amount": 2, "target": "Opponent"}}]}),
    "inflame-turn1": ("Inflame", {"effects": [_apply("DemonForm", 1)]}),
    "df-c2-s1": ("Demon Form", {"cost": 2, "effects": [_apply("DemonForm", 1)]}),
    "metal-c0-a2": ("Metallicize", {"cost": 0, "effects": [_apply("Metallicize", 2)]}),
    "metal-c2-a5": ("Metallicize", {"cost": 2, "effects": [_apply("Metallicize", 5)]}),
    "combust-d8-l2": ("Combust", {"effects": [_apply("Combust", 2), _apply("CombustDamage", 8)]}),
    "combust-c0-d3": ("Combust", {"cost": 0, "effects": [_apply("Combust", 1), _apply("CombustDamage", 3)]}),
}


def copy_id(card):
    return card.replace(" ", "") + "~copy"


def official_cards():
    with open(CARDS_FILE, encoding="utf-8") as f:
        return {c["id"]: c for c in json.load(f)["cards"]}


def pack(mods=None):
    """The generated pack: each parent's copy (the official id, cost, type
    and effects) and each modifier's variant (the copy with its fields)."""
    off = official_cards()
    mods = list(MODS) if mods is None else mods
    cards = {}
    for m in mods:
        parent, change = MODS[m]
        if parent not in off:
            raise SystemExit(f"modifier {m}: parent {parent!r} is not in content/cards.json")
        base = {"id": copy_id(parent), **{k: copy.deepcopy(off[parent][k]) for k in ("cost", "type", "effects")}}
        cards[base["id"]] = base
        cards[m] = {**copy.deepcopy(base), **copy.deepcopy(change), "id": m}
    return {"version": 1, "powers": [], "cards": list(cards.values())}


def swapped(deck, card, new):
    """`deck` with every `card` (not its upgrade) named `new`."""
    return [new if x == card else x for x in deck]


def start(spec, deck, seed):
    c = sts.Combat(deck, spec["encounter"], seed=seed, hp=spec["hp"], character=spec["character"])
    while not c.is_over() and not c.awaiting_action():
        c.advance()
    return c


def play_decks(spec, decks, seeds, player, threads):
    """[(won, hp_end)] per seed for each deck, `player` a PLAYERS key."""
    name = PLAYERS[player]
    ev = bench.load_evaluator(name) if name else None
    kw = {"limit": bench.LIMIT, "threads": threads}
    if ev is not None:
        kw.update(evaluator=ev.evaluator, features=ev.features)
    res = sts.play_on([start(spec, d, s) for d in decks for s in seeds], **kw)
    n = len(seeds)
    return [[(bool(r["won"]), int(r["hp_end"])) for r in res[k * n:(k + 1) * n]] for k in range(len(decks))]


def resolve_net(pattern):
    """`pattern` itself without glob characters, else its one match."""
    if not glob.has_magic(pattern):
        return pattern
    hits = sorted(glob.glob(pattern))
    if len(hits) != 1:
        raise SystemExit(f"--net {pattern}: {len(hits)} matches {hits}, need exactly one")
    return hits[0].replace("\\", "/")


def play_cmd(args):
    if args.net:
        net = resolve_net(args.net)
        PLAYERS["one"] = net + "@hpb0.01"
        PLAYERS["tsl"] = net + "@hpb0.01@tsl1"
        for a in PROJECTED:
            PLAYERS[a] = net + "@hpb0.01@tsl1@" + a
    players = args.players.split(",")
    mods = args.mods.split(",") if args.mods else list(MODS)
    unknown = [m for m in mods if m not in MODS] + [p for p in players if p not in PLAYERS]
    if unknown:
        raise SystemExit(f"unknown {unknown}; modifiers {list(MODS)}, players {list(PLAYERS)}")
    sts.load_content(json.dumps(pack()))  # the full pack, as every read and burst loads it
    done = {"settings": {"product": args.product, "seeds": args.seeds, "starts": args.starts, "mods": mods,
                         "net": PLAYERS["one"][:-len("@hpb0.01")]}, "rows": []}
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            done = json.load(f)
        done["settings"]["mods"] = [m for m in MODS if m in set(done["settings"]["mods"]) | set(mods)]
    with open(args.product, encoding="utf-8") as f:
        specs = ba.fights(json.load(f), 100000)
    rows = {(r["i"], r["floor"], r["card"]): r for r in done["rows"]}
    t0 = time.perf_counter()
    for card in dict.fromkeys(MODS[m][0] for m in mods):
        cmods = [m for m in mods if MODS[m][0] == card]
        chosen = [s for s in specs if card in s["deck"]][:args.starts]
        for n, spec in enumerate(chosen):
            key = (spec["i"], spec["floor"], card)
            row = rows.get(key)
            if row is None:
                row = {k: spec[k] for k in ("i", "floor", "encounter", "group", "hp")}
                row.update({"card": card, "official": {}, "parent": {}, "mods": {}})
                done["rows"].append(row)
                rows[key] = row
            for m in cmods:
                row["mods"].setdefault(m, {})
            todo = [p for p in players if p not in row["parent"] or any(p not in row["mods"][m] for m in cmods)]
            if not todo:
                continue
            decks = [spec["deck"], swapped(spec["deck"], card, "gen:" + copy_id(card))]
            decks += [swapped(spec["deck"], card, "gen:" + m) for m in cmods]
            seeds = [int(x) for x in np.random.default_rng([20261107, spec["i"], spec["floor"]]).integers(2**62, size=args.seeds)]
            for p in todo:
                res = play_decks(spec, decks, seeds, p, args.threads)
                row["official"][p], row["parent"][p] = res[0], res[1]
                for m, r in zip(cmods, res[2:]):
                    row["mods"][m][p] = r
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            with open(args.out, "w", encoding="utf-8", newline="\n") as f:
                json.dump(done, f)
            print(f"{card}: {n + 1} / {len(chosen)} starts, {time.perf_counter() - t0:.0f} s", flush=True)
    print(args.out)


def summary(rows, mods):
    """Per modifier: per player the win and HP-lost change from the parent
    copy (paired by start); the novelty contrasts (net minus heuristic) in
    both; and the copy minus official check."""
    out = {}
    for m in mods:
        rs_m = [r for r in rows if m in r["mods"]]
        s = {}
        for p in PLAYERS:
            rs = [r for r in rs_m if p in r["parent"] and p in r["mods"][m]]
            if rs:
                o = lambda r, x: mm.outcome(x, r["hp"])  # noqa: E731
                s[p] = {"n": len(rs),
                        "win": ba.mean_se([o(r, r["mods"][m][p])[0] - o(r, r["parent"][p])[0] for r in rs]),
                        "lost": ba.mean_se([o(r, r["mods"][m][p])[1] - o(r, r["parent"][p])[1] for r in rs]),
                        "copy_win": ba.mean_se([o(r, r["parent"][p])[0] - o(r, r["official"][p])[0] for r in rs]),
                        "win_parent": float(np.mean([o(r, r["parent"][p])[0] for r in rs]))}
        for a in NOVELTY:
            rs = [r for r in rs_m if all(p in r["parent"] and p in r["mods"][m] for p in (a, "heuristic"))]
            if rs:
                d = {k: [(mm.outcome(r["mods"][m][a], r["hp"])[k] - mm.outcome(r["parent"][a], r["hp"])[k])
                         - (mm.outcome(r["mods"][m]["heuristic"], r["hp"])[k] - mm.outcome(r["parent"]["heuristic"], r["hp"])[k])
                         for r in rs] for k in (0, 1)}
                s["novelty_" + a] = {"n": len(rs), "win": ba.mean_se(d[0]), "lost": ba.mean_se(d[1])}
        for a in PROJECTED:  # the projection's change in novelty cost: (pl - tsl)(mod) - (pl - tsl)(parent)
            rs = [r for r in rs_m if all(p in r["parent"] and p in r["mods"][m] for p in (a, "tsl"))]
            if rs:
                d = {k: [(mm.outcome(r["mods"][m][a], r["hp"])[k] - mm.outcome(r["parent"][a], r["hp"])[k])
                         - (mm.outcome(r["mods"][m]["tsl"], r["hp"])[k] - mm.outcome(r["parent"]["tsl"], r["hp"])[k])
                         for r in rs] for k in (0, 1)}
                s["vs_tsl_" + a] = {"n": len(rs), "win": ba.mean_se(d[0]), "lost": ba.mean_se(d[1])}
        out[m] = s
    return out


def pooled(s):
    """Per net: the mean novelty cost (wins, HP lost) over the power-parent
    pairs, se over pairs, and the plain control's beside it."""
    out = {}
    for a in NOVELTY:
        k = "novelty_" + a
        pairs = [m for m in s if m != CONTROL and k in s[m]]
        if pairs:
            out[a] = {"pairs": len(pairs), "win": ba.mean_se([s[m][k]["win"][0] for m in pairs]),
                      "lost": ba.mean_se([s[m][k]["lost"][0] for m in pairs]),
                      "control": s[CONTROL][k] if CONTROL in s and k in s[CONTROL] else None}
    return out


def read_cmd(args):
    with open(args.out, encoding="utf-8") as f:
        d = json.load(f)
    rows, mods = d["rows"], d["settings"]["mods"]
    fmt = lambda v, w=".3f": f"{v[0]:+{w}} ({v[1]:{w}})" if v else "-"  # noqa: E731
    out = {}
    for title, rs in [("all", rows)] + [(g, [r for r in rows if r["group"] == g]) for g in sorted({r["group"] for r in rows})]:
        s = summary(rs, mods)
        print(f"\n{title}: win change from the parent copy (se), paired by start; HP lost change after /")
        print(f"{'modifier':16s} {'n':>4s} {'heuristic':>22s} {'one-turn net':>22s} {'tsl net':>22s} "
              f"{'novelty one-heur':>22s} {'novelty tsl-heur':>22s}")
        for m, v in s.items():
            cell = lambda x: f"{fmt(x['win'])} / {x['lost'][0]:+.1f}" if x else "-"  # noqa: E731
            n = max([v[p]["n"] for p in PLAYERS if p in v], default=0)
            print(f"{m:16s} {n:4d} " + " ".join(f"{cell(v.get(p)):>22s}" for p in
                  ("heuristic", "one", "tsl", "novelty_one", "novelty_tsl")))
        for a in PROJECTED:
            vs = {m: v["vs_tsl_" + a] for m, v in s.items() if "vs_tsl_" + a in v}
            if vs:
                print(f"  {a} minus tsl, change from the parent (wins / HP lost, se): " + "; ".join(
                    f"{m} {fmt(x['win'])} / {fmt(x['lost'], '.2f')}" for m, x in vs.items()))
                print(f"  novelty {a}-heur: " + "; ".join(f"{m} {cell(v.get('novelty_' + a))}" for m, v in s.items()))
        print("  copy minus official, wins: " + "; ".join(
            f"{m} " + " / ".join(fmt(v[p]["copy_win"]) for p in PLAYERS if p in v) for m, v in s.items()))
        pl = pooled(s)
        for a, v in pl.items():
            c = v["control"]
            print(f"  pooled novelty {a} over {v['pairs']} pairs (se over pairs): wins {fmt(v['win'])}, "
                  f"HP lost {fmt(v['lost'], '.2f')}; plain control wins {fmt(c['win']) if c else '-'}, "
                  f"HP lost {fmt(c['lost'], '.2f') if c else '-'}")
        out[title] = {"mods": s, "pooled": pl}
    return out


def adapted_summary(zero, bursts, mod, player, group=None):
    """Bursts against the zero-shot file for `mod` and `player`: per start
    the bursts' outcomes averaged over the burst files minus the zero-shot
    outcome, mean and se over starts, for the variant ("mod"), parent copy
    and official rows; the zero-shot novelty cost (player minus heuristic,
    each against the parent copy); each burst's variant-row win gain alone
    ("per_burst")."""
    o = mm.outcome
    key = lambda r: (r["i"], r["floor"], r["card"])  # noqa: E731
    zrows = {key(r): r for r in zero["rows"] if mod in r["mods"] and (group is None or r["group"] == group)}
    brows = [{key(r): r for r in b["rows"] if mod in r["mods"]} for b in bursts]
    brows = [b for b in brows if b]  # a burst file of another modifier holds none of these rows
    keys = [k for k, z in zrows.items() if player in z["mods"][mod] and player in z["parent"]
            and all(k in b and player in b[k]["mods"][mod] and player in b[k]["parent"] for b in brows)]
    out = {"n": len(keys)}
    if not keys:
        return out
    get = {"mod": lambda r: r["mods"][mod][player], "parent": lambda r: r["parent"][player],
           "official": lambda r: r["official"][player]}
    for name, g in get.items():
        d = [[float(np.mean([o(g(b[k]), b[k]["hp"])[x] for b in brows])) - o(g(zrows[k]), zrows[k]["hp"])[x]
              for k in keys] for x in (0, 1)]
        out[name] = {"win": ba.mean_se(d[0]), "lost": ba.mean_se(d[1])}
    if all("heuristic" in zrows[k]["mods"][mod] and "heuristic" in zrows[k]["parent"] for k in keys):
        ch = lambda r, p, x: o(r["mods"][mod][p], r["hp"])[x] - o(r["parent"][p], r["hp"])[x]  # noqa: E731
        d = [[ch(zrows[k], player, x) - ch(zrows[k], "heuristic", x) for k in keys] for x in (0, 1)]
        out["novelty"] = {"win": ba.mean_se(d[0]), "lost": ba.mean_se(d[1])}
    out["per_burst"] = [{"win": ba.mean_se([o(b[k]["mods"][mod][player], b[k]["hp"])[0]
                                            - o(zrows[k]["mods"][mod][player], zrows[k]["hp"])[0] for k in keys])}
                        for b in brows]
    return out


def adapted_cmd(args):
    with open(args.zero, encoding="utf-8") as f:
        zero = json.load(f)
    bursts = []
    for p in args.bursts:
        with open(p, encoding="utf-8") as f:
            bursts.append(json.load(f))
    mods = [m for m in MODS if any(m in b["settings"]["mods"] for b in bursts)]
    fmt = lambda v, w=".3f": f"{v[0]:+{w}} ({v[1]:{w}})"  # noqa: E731
    cell = lambda x: f"{fmt(x['win'])} / {x['lost'][0]:+.2f} ({x['lost'][1]:.2f})"  # noqa: E731
    out = {}
    print(f"bursts against {args.zero}: {', '.join(args.bursts)}")
    print("gain = bursts (pooled per start) minus zero-shot, paired by start: wins (se) / HP lost (se)")
    for m in mods:
        for title, g in (("all", None), ("elite", "elite"), ("boss", "boss")):
            for p in NOVELTY:
                s = adapted_summary(zero, bursts, m, p, g)
                out[f"{m}/{title}/{p}"] = s
                if not s["n"]:
                    continue
                nov = f"; zero-shot novelty {cell(s['novelty'])}" if "novelty" in s else ""
                print(f"{m:14s} {title:5s} {p:4s} n {s['n']:3d}: variant {cell(s['mod'])}; parent {cell(s['parent'])}; "
                      f"official {cell(s['official'])}{nov}; per burst variant wins "
                      + ", ".join(fmt(x["win"]) for x in s["per_burst"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("--product", default=mm.PRODUCT)
    p.add_argument("--starts", type=int, default=200, help="fights per parent card")
    p.add_argument("--seeds", type=int, default=8)
    p.add_argument("--players", default="heuristic,one,tsl")
    p.add_argument("--mods", default="")
    p.add_argument("--net", default="", help="a burst net in place of the product's (one and tsl)")
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--out", required=True)
    r = sub.add_parser("read")
    r.add_argument("out")
    k = sub.add_parser("pack")
    k.add_argument("--out", required=True)
    a = sub.add_parser("adapted")
    a.add_argument("zero", help="the zero-shot file (cards-a.json)")
    a.add_argument("bursts", nargs="+", help="burst nets' reads of the same starts (play --net)")
    args = ap.parse_args(argv)
    if args.cmd == "pack":
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(pack(), f, indent=1)
            f.write("\n")
        return args.out
    return {"play": play_cmd, "read": read_cmd, "adapted": adapted_cmd}[args.cmd](args)


if __name__ == "__main__":
    main()
