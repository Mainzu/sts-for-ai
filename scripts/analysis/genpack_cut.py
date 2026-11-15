"""Pooled zero-shot cut for lane generated-pack-scratch (docs/research/generated-enemies.md,
"Generated training pack").

Novelty cost per start and mechanic: (net - heuristic)(mechanic) - (net - heuristic)(parent)
in HP lost (a loss costs the entry HP), from mutate_monsters.py play files. Pooled over the
held-out (or training) mechanics per start; cut = 1 - genpack / base, se by the delta method
over starts (the starts are shared by every file). With several seed pairs, the pooled value
averages the seeds per start; the seed spread (sd of per-seed cuts / sqrt(seeds)) is printed
too, and the larger se is the one the bar reads.

    genpack_cut.py --pair <base> <genpack> [--pair ...] [--ref results/mutate/gen-enemies-b1.json]
    genpack_cut.py --hp <control> <genpack> [--hp ...]   (gauntlet files: paired end HP by half, pooled)
    genpack_cut.py --wide --pair <base> <genpack> [--pair ...]   (lane wider-generators: the cut per group of
        mutate_monsters.WIDE_SPLIT and the old split, and the step-2 fail-fast line)
    genpack_cut.py --trained M1,M2,.. --pair <base> <genpack>   (lane mechanic-count-curve: training rows split
        into the mechanics the pack trained on and the rest, and the stop rule's line)
    genpack_cut.py --player product --pair <product file> <genpack file>   (lane genpack-product-depth: the
        two-turn `product` player's costs, the 10-29 bar read on the base files, the parents' HP lost and the
        stop rule's line; docs/specs/genpack-product-depth.md)
"""
import argparse
import json

import numpy as np

HELD = ["GE-AttackLoss-Damage", "GE-AttackLoss-Weak", "GE-OppCard-PlainDamage",
        "GE-OppCard-Damage", "GE-TurnEnd-Weak", "GE-TurnEnd-Frail"]


def lost(res, hp):
    return float(np.mean([hp - e if w else hp for w, e in res]))


def costs(path, net="one"):
    """{(i, floor): {mechanic: novelty cost}} over elite rows that player `net` played
    (a --two-starts file has the deep players on its first starts only)."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    mechs = [m for m in d["settings"]["mods"] if m.startswith("GE-")]
    out = {}
    for r in d["rows"]:
        if r["group"] != "elite" or net not in r["parent"]:
            continue
        gap = lambda x: lost(x[net], r["hp"]) - lost(x["heuristic"], r["hp"])  # noqa: E731
        g0 = gap(r["parent"])
        out[(r["i"], r["floor"])] = {m: gap(r["mods"][m]) - g0 for m in mechs if m in r["mods"]}
    return out, mechs


def parent_lost(path, net):
    """{(i, floor): HP lost on the parent fight} of player `net` over elite rows."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return {(r["i"], r["floor"]): lost(r["parent"][net], r["hp"]) for r in d["rows"]
            if r["group"] == "elite" and net in r["parent"]}


def pooled(c, keys, mechs):
    return np.array([np.mean([c[k][m] for m in mechs]) for k in keys])


def ms(x):
    return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x)))


def cut(b, g):
    """1 - mean(g)/mean(b), delta-method se over paired starts."""
    mb, mg = b.mean(), g.mean()
    r = mg / mb
    var = (np.var(g, ddof=1) - 2 * r * np.cov(g, b)[0, 1] + r * r * np.var(b, ddof=1)) / (mb * mb * len(b))
    return float(1 - r), float(np.sqrt(var))


def hp_cmd(pairs):
    """Paired end HP (gauntlet_protocol.end_hp), genpack minus control, by half; pooled over pairs."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    import gauntlet_protocol as gp
    pool = {"all": [], "train": [], "held_out": []}
    for c, g in pairs:
        with open(c, encoding="utf-8") as f:
            a = {r["i"]: r for r in json.load(f)["sequences"]}
        with open(g, encoding="utf-8") as f:
            b = json.load(f)["sequences"]
        d = {h: [] for h in pool}
        for r in b:
            if r["i"] in a and a[r["i"]]["cell"] == r["cell"]:
                x = gp.end_hp(r) - gp.end_hp(a[r["i"]])
                d["all"].append(x)
                d[r["half"]].append(x)
        print(f"  {g}: " + "  ".join(f"{h} {ms(np.array(v))[0]:+.2f} ({ms(np.array(v))[1]:.2f}) n {len(v)}" for h, v in d.items()))
        for h in pool:
            pool[h] += d[h]
    print(f"  POOLED over {len(pairs)}: " + "  ".join(f"{h} {ms(np.array(v))[0]:+.2f} ({ms(np.array(v))[1]:.2f}) n {len(v)}" for h, v in pool.items()))


def wide_groups(mechs):
    """{group: mechanics in `mechs`} for the wider grid (docs/specs/wider-generators.md)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    import mutate_monsters as mm
    g = {"new held-out pairs": mm.WIDE_SPLIT["held_pairs"], "whole trigger": mm.WIDE_SPLIT["whole_trigger"],
         "whole effect": mm.WIDE_SPLIT["whole_effect"], "new training": mm.WIDE_SPLIT["train"],
         "old held-out": HELD, "old training": [m for m in mm.GEN if m not in HELD]}
    return {k: [m for m in v if m in mechs] for k, v in g.items() if any(m in mechs for m in v)}


def wide_cmd(pairs):
    """Per group: base and genpack pooled novelty cost, gain and cut, per seed pair and pooled;
    per mechanic in the held-out groups; the fail-fast line (genpack new held-out pooled cost under 1 HP)."""
    files = [(costs(b), costs(g)) for b, g in pairs]
    mechs = set(files[0][0][1]) & set.intersection(*[set(g[1]) for _, g in files])
    keys = sorted(set.intersection(*[set(b[0]) & set(g[0]) for b, g in files]))
    print(f"{len(keys)} elite starts shared by all files; novelty cost beyond parent in HP, mean (se) over starts")
    out = {}
    for title, ms_ in wide_groups(mechs).items():
        B = np.mean([pooled(b[0], keys, ms_) for b, _ in files], axis=0)
        G = np.mean([pooled(g[0], keys, ms_) for _, g in files], axis=0)
        c, se = cut(B, G)
        out[title] = {"base": ms(B), "genpack": ms(G), "cut": (c, se), "n": len(ms_)}
        print(f"  {title:18s} ({len(ms_):2d}) base {ms(B)[0]:+.2f} ({ms(B)[1]:.2f}) genpack {ms(G)[0]:+.2f} ({ms(G)[1]:.2f})"
              f" gain {ms(B - G)[0]:+.2f} ({ms(B - G)[1]:.2f}) cut {c:.2f} ({se:.2f})")
    for title in ("new held-out pairs", "whole trigger", "whole effect"):
        for m in wide_groups(mechs).get(title, []):
            bm = np.mean([[b[0][k][m] for k in keys] for b, _ in files], axis=0)
            gm = np.mean([[g[0][k][m] for k in keys] for _, g in files], axis=0)
            c, se = cut(bm, gm)
            print(f"    {m:26s} base {ms(bm)[0]:+.2f} ({ms(bm)[1]:.2f}) genpack {ms(gm)[0]:+.2f} ({ms(gm)[1]:.2f}) cut {c:.2f} ({se:.2f})")
    h = out.get("new held-out pairs")
    if h:
        print(f"  fail-fast: genpack new held-out pooled cost {h['genpack'][0]:+.2f} ({h['genpack'][1]:.2f}) HP; "
              f"under 1 HP (the grid already reaches them): {h['genpack'][0] < 1}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pair", nargs=2, action="append", metavar=("BASE", "GENPACK"))
    ap.add_argument("--hp", nargs=2, action="append", metavar=("CONTROL", "GENPACK"))
    ap.add_argument("--wide", action="store_true", help="the wider grid's groups (lane wider-generators)")
    ap.add_argument("--gate", action="store_true", help="with --wide or --player: exit 1 when the fail-fast fires (a job's --check)")
    ap.add_argument("--trained", default=None,
                    help="comma list: the pack's training mechanics; the other non-held rows are reported apart")
    ap.add_argument("--ref", default="results/mutate/gen-enemies-b1.json",
                    help="the 10-29 net's file (the 10-29 bar); with --player other than one, the base files")
    ap.add_argument("--player", default="one", help="the files' player to read (one; product: two turns deep)")
    a = ap.parse_args(argv)
    if a.hp:
        return hp_cmd(a.hp)
    if a.wide:
        out = wide_cmd(a.pair)
        h = out.get("new held-out pairs")
        if a.gate and (h is None or h["genpack"][0] < 1):
            raise SystemExit(1)
        return out
    files = [(costs(b, a.player), costs(g, a.player)) for b, g in a.pair]
    mechs = files[0][0][1]
    train = [m for m in mechs if m not in HELD]
    groups = [("held-out", HELD), ("training", train)]
    if a.trained:
        tr = a.trained.split(",")
        assert set(tr) <= set(train), set(tr) - set(train)
        groups = [("held-out", HELD), ("trained", tr), ("neither", [m for m in train if m not in tr])]
    keys = sorted(set.intersection(*[set(b[0]) & set(g[0]) for b, g in files]))
    print(f"{len(keys)} elite starts shared by all files; cost in HP, mean (se) over starts")
    acc = {}
    for title, ms_ in groups:
        bs, gs, cuts = [], [], []
        for (b, _), (g, _) in files:
            bs.append(pooled(b, keys, ms_))
            gs.append(pooled(g, keys, ms_))
            cuts.append(cut(bs[-1], gs[-1]))
        for (bp, gp), bb, gg, (c, se) in zip(a.pair, bs, gs, cuts):
            print(f"  {title:9s} {gp}: base {ms(bb)[0]:+.2f} ({ms(bb)[1]:.2f}) genpack {ms(gg)[0]:+.2f} ({ms(gg)[1]:.2f})"
                  f" gain {ms(bb - gg)[0]:+.2f} ({ms(bb - gg)[1]:.2f}) cut {c:.2f} ({se:.2f})")
        B, G = np.mean(bs, axis=0), np.mean(gs, axis=0)
        c, se = cut(B, G)
        spread = float(np.std([x for x, _ in cuts], ddof=1) / np.sqrt(len(cuts))) if len(cuts) > 1 else 0.0
        print(f"  {title:9s} POOLED over {len(files)} seed(s): base {ms(B)[0]:+.2f} ({ms(B)[1]:.2f}) genpack "
              f"{ms(G)[0]:+.2f} ({ms(G)[1]:.2f}) cut {c:.2f} (starts se {se:.2f}, seed spread {spread:.2f})")
        acc[title] = (G, c, max(se, spread))
    if a.player == "one":
        R = pooled(costs(a.ref)[0], keys, HELD)
    else:  # the base player is the 10-29 net at this depth
        R = np.mean([pooled(b[0], keys, HELD) for b, _ in files], axis=0)
    G = acc["held-out"][0]
    d = ms(R - G)
    print(f"  10-29 bar: 10-29 net held-out {ms(R)[0]:+.2f} ({ms(R)[1]:.2f}) against genpack pooled "
          f"{ms(G)[0]:+.2f} ({ms(G)[1]:.2f}): genpack better by {d[0]:+.2f} ({d[1]:.2f})")
    for m in HELD:
        bm = np.mean([[b[0][k][m] for k in keys] for b, _ in files], axis=0)
        gm = np.mean([[g[0][k][m] for k in keys] for _, g in files], axis=0)
        c, se = cut(bm, gm)
        print(f"    {m:26s} base {ms(bm)[0]:+.2f} ({ms(bm)[1]:.2f}) genpack {ms(gm)[0]:+.2f} ({ms(gm)[1]:.2f}) cut {c:.2f} ({se:.2f})")
    hc, hse = acc["held-out"][1:]
    print(f"  held-out cut {hc:.2f} (se {hse:.2f}): 0.4 at 2 se {'holds' if hc - 2 * hse >= 0.4 else 'fails'}; "
          f"10-29 bar {'holds' if d[0] >= -2 * d[1] else 'fails'}; under 0.2: {hc < 0.2}")
    if a.player != "one":
        B = np.mean([pooled(b[0], keys, HELD) for b, _ in files], axis=0)
        par = np.mean([[parent_lost(g, a.player)[k] - parent_lost(b, a.player)[k] for k in keys] for b, g in a.pair],
                      axis=0)
        pm, pse = ms(-par)
        print(f"  parents: genpack minus base HP lost {-pm:+.2f} ({pse:.2f}), i.e. genpack ends {pm:+.2f} HP "
              f"(within -1.5: {pm >= -1.5})")
        ok = hc - 2 * hse >= 0.4 and pm >= -1.5
        v = ("fail-fast (base held-out cost under 1.0 HP)" if ms(B)[0] < 1.0 else
             "go" if ok and len(files) >= 3 else "fail" if hc < 0.2 or hc < 2 * hse else
             "between" if len(files) >= 3 else "go so far (seeds 101 and 201 decide)" if ok else "between")
        print(f"  genpack-product-depth stop rule: base held-out cost {ms(B)[0]:+.2f} ({ms(B)[1]:.2f}), "
              f"cut {hc:.2f} (se {hse:.2f}): {v}")
        if a.gate and v.startswith("fail-fast"):
            raise SystemExit(1)
        return {"verdict": v, "base": ms(B), "cut": (hc, hse), "parent": (pm, pse)}
    if a.trained:
        v = "go" if hc - 2 * hse >= 0.6 else "fail" if hc < 0.4 else "between"
        print(f"  mechanic-count-curve stop rule: held-out cut {hc:.2f} (se {hse:.2f}): {v} "
              "(go: 0.6 or more at 2 se; fail: under 0.4; between: a seed-101 learn decides)")


if __name__ == "__main__":
    main()
