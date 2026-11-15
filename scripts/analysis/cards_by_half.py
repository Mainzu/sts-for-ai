"""yardstick-cards step 1: the zero-shot card cost against training size.

For each net with cell-gauntlet files on both books (0-499 and --first 500),
pair it with the heuristic's file on the same sequences and take, per half
(train / held-out cells), the mean paired end-HP and clears edge. A net's
value is the mean of its two books; each size's row is the mean over its
seeds with se = sd / sqrt(seeds). A file with fewer than 500 sequences
(a job still writing it) counts as missing. "gap" is the train edge minus the held-out
edge (the cards rung's zero-shot number, cause/unseen-cards-half-edge).

    python scripts/analysis/cards_by_half.py [--root <main checkout>]
"""
import argparse
import json
import math
import re
from pathlib import Path

from gauntlet_protocol import end_hp

SEQUENCES = 500
BOOKS = {"": "heuristic-bcbb0e.json", "-b500": "heuristic-b500.json"}
GROUPS = [
    ("effects 5k", r"rerank-2026-10-31-data5k-s\d+-r1-\w+-hpb0\.01"),
    ("effects 20k", r"rerank-2026-10-31-data20k-s\d+-r1-\w+-hpb0\.01"),
    ("effects 40k", r"rerank-2026-10-31-data40k-s\d+-r1-\w+-hpb0\.01"),
    ("ids 5k", r"rerank-2026-1[01]-\d\d-ids5k-s\d+-r1-\w+-hpb0\.01"),
    ("product recipe", r"net1029(s101|s201)?-hpb0\.01"),
]


def load(p):
    return {r["i"]: r for r in json.loads(p.read_text(encoding="utf-8"))["sequences"]}


def edges(net, heur):
    """{half: (end-HP edge, clears edge)} over the sequences both hold."""
    out = {}
    for half in ("train", "held_out"):
        ks = [k for k in net if k in heur and net[k]["half"] == half and net[k]["cell"] == heur[k]["cell"]]
        dh = [end_hp(net[k]) - end_hp(heur[k]) for k in ks]
        dc = [float(net[k]["cleared"]) - float(heur[k]["cleared"]) for k in ks]
        out[half] = (sum(dh) / len(dh), sum(dc) / len(dc))
    return out


def mean_se(xs):
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, float("nan")
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


# ---- step 1b: strata, by card, two-turn files, generated bench by trigger ----

STRATA = ("train", "held-out", "held-out DF")  # DF: the deck holds Demon Form
STRATA_GROUPS = GROUPS + [("burst8 (transfer)", r"rerank-2026-11-01-burst8-s\d+-\w+-hpb0\.01")]
TWO_TURN = ["net1029-hpe0.01-two-a", "net1029-hpe0.01-two-c",
            "champion-hpe0.01-two-a", "champion-hpe0.01-two-b", "champion-hpe0.01-two-c"]
ONE_TURN_NET = ["net1029-hpb0.01", "net1029-hpb0.01-b500"]
STARTER = {"Strike", "Defend", "Bash"}
GEN_BENCH = "data/bench/gen_powers12c3.json"
GEN_FILES = {"heuristic": "heuristic-elite_boss.json",
             "net1029": "2026-10-29-seed-check-r2-s1-1a789b2-elite_boss.json"}


def base(card):
    return card.rstrip("+")


def decks(n=2 * SEQUENCES):
    """{sequence i: deck} for both books."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import gauntlet
    return {s["i"]: s["deck"] for s in gauntlet.sequences(n)}


def stratum(rec, deck):
    if rec["half"] == "train":
        return "train"
    return "held-out DF" if any(base(c) == "Demon Form" for c in deck) else "held-out"


def load_union(g, names):
    out = {}
    for n in names:
        out.update(load(g / f"{n}.json"))
    return out


def complete_nets(g, names, pat):
    """[{i: rec}] per net whose two books are both complete."""
    nets = []
    for b0 in sorted(n for n in names if re.fullmatch(pat, n)):
        files = [b0 + b for b in BOOKS]
        if all(f in names and len(load(g / f"{f}.json")) >= SEQUENCES for f in files):
            nets.append(load_union(g, files))
    return nets


def strata_row(nets, ref, dk):
    """{stratum: [HP edge, se over sequences, se over nets, clears edge, se over sequences, se over nets, n]}."""
    out = {}
    for s in STRATA:
        ks = sorted(k for k in ref if all(k in n for n in nets) and stratum(ref[k], dk[k]) == s)
        row = []
        for f in (end_hp, lambda r: float(r["cleared"])):
            per_seq = [sum(f(n[k]) - f(ref[k]) for n in nets) / len(nets) for k in ks]
            per_net = [sum(f(n[k]) - f(ref[k]) for k in ks) / len(ks) for n in nets]
            m, se_seq = mean_se(per_seq)
            row += [m, se_seq, mean_se(per_net)[1]]
        out[s] = row + [len(ks)]
    return out


def ols_robust(X, y):
    """OLS coefficients with HC1 robust se."""
    import numpy as np
    X, y = np.asarray(X, float), np.asarray(y, float)
    inv = np.linalg.pinv(X.T @ X)
    beta = inv @ X.T @ y
    e = y - X @ beta
    n, p = X.shape
    cov = inv @ (X.T @ (X * (e ** 2)[:, None])) @ inv * n / max(n - p, 1)
    return beta, np.sqrt(np.diag(cov))


def by_card(heur, nets, dk, min_decks=20):
    """{card: ((heur b, se), (nets b, se), (nets minus heur b, se), decks)}: end-HP regressed on the
    copies of each non-starter card held by at least min_decks sequences, with the book and the
    deck's upgrade count as covariates."""
    ks = sorted(k for k in heur if all(k in n for n in nets))
    counts = []
    for k in ks:
        c = {}
        for card in dk[k]:
            if base(card) not in STARTER:
                c[base(card)] = c.get(base(card), 0) + 1
        counts.append(c)
    cards = sorted({x for c in counts for x in c if sum(1 for d in counts if x in d) >= min_decks})
    X = [[1.0, float(k >= SEQUENCES), float(sum(card.endswith("+") for card in dk[k]))] + [c.get(x, 0) for x in cards]
         for c, k in zip(counts, ks)]
    yh = [end_hp(heur[k]) for k in ks]
    yn = [sum(end_hp(n[k]) for n in nets) / len(nets) for k in ks]
    fits = [ols_robust(X, y) for y in (yh, yn, [a - b for a, b in zip(yn, yh)])]
    return {x: tuple((float(b[3 + j]), float(se[3 + j])) for b, se in fits) + (sum(1 for d in counts if x in d),)
            for j, x in enumerate(cards)}


def gen_by_trigger(root):
    """Generated-power bench, one turn deep: 10-29 net minus heuristic wins, mean over cells
    (se over cells); generated fights by trigger, original fights by the swapped card."""
    fights = json.loads((root / GEN_BENCH).read_text(encoding="utf-8"))["fights"]
    d = root / "results" / "gen_powers" / "depth"
    h, n = (json.loads((d / GEN_FILES[k]).read_text(encoding="utf-8")) for k in ("heuristic", "net1029"))
    assert h["idx"] == n["idx"]
    rows = {}
    for i, a, c in zip(h["idx"], h["one"], n["one"]):
        f = fights[i]
        key = ("generated", " + ".join(f["triggers"])) if f["set"] == "generated" else ("original", f["swapped"])
        rows.setdefault(key, {}).setdefault(f["cell"], []).append(c - a)
    out = {}
    for key, cells in sorted(rows.items()):
        m, se = mean_se([sum(v) / len(v) for v in cells.values()])
        out[key] = (m, se, len(cells), sum(len(v) for v in cells.values()))
    return out


def step1b(root):
    g = root / "results" / "gauntlet"
    names = {p.name[:-5] for p in g.glob("*.json")}
    dk = decks()
    heur = load_union(g, [f[:-5] for f in BOOKS.values()])
    one = load_union(g, ONE_TURN_NET)
    for ref_label, ref in (("the heuristic", heur), ("the one-turn 10-29 net", one)):
        print(f"\n### By stratum, both books, paired edge over {ref_label}\n")
        print("| nets | n | " + " | ".join(f"{s}: HP (se seq / nets), clears (se seq / nets)" for s in STRATA) + " |")
        print("|---|---|---|---|---|")
        for label, pat in STRATA_GROUPS:
            nets = complete_nets(g, names, pat)
            if nets:
                r = strata_row(nets, ref, dk)
                print(f"| {label} | {len(nets)} | " + " | ".join(
                    f"{r[s][0]:+.2f} ({r[s][1]:.2f} / {r[s][2]:.2f}), {r[s][3]:+.3f} ({r[s][4]:.3f} / {r[s][5]:.3f})"
                    for s in STRATA) + " |")
        print("\nsequences per stratum:", {s: sum(1 for k in ref if stratum(ref[k], dk[k]) == s) for s in STRATA})
    print("\n### Two-turn cell files by stratum (each on its own sequences; se over sequences)\n")
    print("| file | against | " + " | ".join(f"{s}: HP, clears, n" for s in STRATA) + " |")
    print("|---|---|---|---|---|")
    for f in TWO_TURN:
        for ref_label, ref in (("heuristic", heur), ("one-turn 10-29", one)):
            r = strata_row([load(g / f"{f}.json")], ref, dk)
            print(f"| {f} | {ref_label} | " + " | ".join(
                f"{r[s][0]:+.2f} ({r[s][1]:.2f}), {r[s][3]:+.3f} ({r[s][4]:.3f}), {r[s][6]}" for s in STRATA) + " |")
    prod = complete_nets(g, names, GROUPS[-1][1])
    print(f"\n### By card: end-HP on the copies of each non-starter card ({len(prod)} product-recipe nets, both "
          "books; covariates book and upgrade count; HC1 se)\n")
    print("| card | decks | heuristic | product nets | nets minus heuristic |")
    print("|---|---|---|---|---|")
    for card, (hh, nn, dd, k) in sorted(by_card(heur, prod, dk).items(), key=lambda x: x[1][2][0]):
        print(f"| {card} | {k} | {hh[0]:+.2f} ({hh[1]:.2f}) | {nn[0]:+.2f} ({nn[1]:.2f}) | {dd[0]:+.2f} ({dd[1]:.2f}) |")
    print("\nDemon Form copy, nets minus heuristic, per net group:")
    for label, pat in STRATA_GROUPS:
        nets = complete_nets(g, names, pat)
        if nets:
            dd = by_card(heur, nets, dk)["Demon Form"][2]
            print(f"- {label} ({len(nets)} nets): {dd[0]:+.2f} ({dd[1]:.2f})")
    print("\n### Generated-power bench, one turn deep: 10-29 net minus heuristic wins (se over cells)\n")
    print("| set | trigger or swapped card | net minus heuristic | cells | fights |")
    print("|---|---|---|---|---|")
    for (s, key), (m, se, c, nf) in gen_by_trigger(root).items():
        print(f"| {s} | {key} | {m:+.3f} ({se:.3f}) | {c} | {nf} |")


# ---- lane turn-start-leaf: the flag's read (docs/specs/turn-start-leaf.md) ----

TSL_FILES = ["net1029-hpb0.01-tsl1", "net1029-hpb0.01-tsl1-b500"]
TSL_GEN = "results/gen_powers/arms/gen_powers12c3/2026-10-29-seed-check-r2-s1-1a789b2{}.json"


def tsl(root):
    """The 10-29 net @hpb0.01 with the turn-start leaf against the plain
    leaf, both books by stratum (se over sequences), the charter's go rule,
    and the generated bench by trigger (flag minus plain wins, se over cells)."""
    g = root / "results" / "gauntlet"
    dk = decks()
    plain, flag = load_union(g, ONE_TURN_NET), load_union(g, TSL_FILES)
    r = strata_row([flag], plain, dk)
    print("### Turn-start leaf minus plain leaf, both books (se over sequences)\n")
    print("| stratum | n | end-HP | clears | identical sequences |")
    print("|---|---|---|---|---|")
    for st in STRATA:
        ks = [k for k in plain if k in flag and stratum(plain[k], dk[k]) == st]
        same = sum(1 for k in ks if end_hp(flag[k]) == end_hp(plain[k]) and flag[k]["cleared"] == plain[k]["cleared"])
        print(f"| {st} | {r[st][6]} | {r[st][0]:+.2f} ({r[st][1]:.2f}) | {r[st][3]:+.3f} ({r[st][4]:.3f}) | {same} |")
    df, ho, tr = r["held-out DF"], r["held-out"], r["train"]
    go = df[0] >= 3 and df[0] >= 2 * df[1] and tr[0] >= -1 and ho[0] >= -1
    print(f"\ncharter: {'go' if go else 'fail'} (Demon Form decks {df[0]:+.2f} at {df[0] / df[1] if df[1] else 0.0:.1f} se; "
          f"train {tr[0]:+.2f}, held-out {ho[0]:+.2f})")
    fights = json.loads((root / GEN_BENCH).read_text(encoding="utf-8"))["fights"]
    p_won, f_won = (json.loads((root / TSL_GEN.format(x)).read_text(encoding="utf-8"))["won"] for x in ("", "-tsl1"))
    assert len(p_won) == len(f_won) == len(fights)
    for groups in (("elite", "boss"), ("hallway", "elite", "boss")):
        rows = {}
        for f, a, c in zip(fights, p_won, f_won):
            if f["group"] in groups:
                key = ("generated", " + ".join(f["triggers"])) if f["set"] == "generated" else ("original", f["swapped"])
                rows.setdefault(key, {}).setdefault(f["cell"], []).append(c - a)
        print(f"\n### Generated bench, {' + '.join(groups)}: flag minus plain wins, one turn deep (se over cells)\n")
        print("| set | trigger or swapped card | flag minus plain | cells | fights |")
        print("|---|---|---|---|---|")
        for (st, key), cells in sorted(rows.items()):
            m, se = mean_se([sum(v) / len(v) for v in cells.values()])
            print(f"| {st} | {key} | {m:+.3f} ({se:.3f}) | {len(cells)} | {sum(len(v) for v in cells.values())} |")


LT_TWINS = r"rerank-2026-11-08-allcontent40k-s(1|101)-r1-\w+-hpb0\.01-tsl1"
LT_DATA = r"rerank-2026-10-31-data40k-s(1|101)-r1-\w+-hpb0\.01-tsl1"


def seed_of(name):
    return re.search(r"-s(\d+)-", name).group(1)


def paired_row(a_nets, b_nets, ref, dk):
    """strata_row for a minus b, net by net (same seeds), strata from `ref`."""
    out = {}
    for s in STRATA:
        ks = sorted(k for k in ref if all(k in n for n in a_nets + b_nets) and stratum(ref[k], dk[k]) == s)
        row = []
        for f in (end_hp, lambda r: float(r["cleared"])):
            pairs = list(zip(a_nets, b_nets))
            per_seq = [sum(f(a[k]) - f(b[k]) for a, b in pairs) / len(pairs) for k in ks]
            per_net = [sum(f(a[k]) - f(b[k]) for k in ks) / len(ks) for a, b in pairs]
            m, se_seq = mean_se(per_seq)
            row += [m, se_seq, mean_se(per_net)[1]]
        out[s] = row + [len(ks)]
    return out


def later_ticks(root):
    """Lane from-scratch-later-ticks step 1: data40k s1/s101 r1 (the twins'
    configs without deck_pool all) and the all-content twins, @hpb0.01@tsl1
    on both cell books, against the 10-29 net @tsl1 and twins minus data40k
    seed by seed; the charter's branch (se the larger over sequences and nets)."""
    g = root / "results" / "gauntlet"
    dk = decks()
    names = {p.name[:-5] for p in g.glob("*.json")}
    ref = load_union(g, TSL_FILES)
    by_seed = {}
    for label, pat in (("twins", LT_TWINS), ("data40k", LT_DATA)):
        for b0 in sorted(n for n in names if re.fullmatch(pat, n)):
            files = [b0 + b for b in BOOKS]
            if all(f in names and len(load(g / f"{f}.json")) >= SEQUENCES for f in files):
                by_seed.setdefault(label, {})[seed_of(b0)] = load_union(g, files)
    seeds = sorted(set(by_seed.get("twins", {})) & set(by_seed.get("data40k", {})), key=int)
    print(f"seeds with both nets complete on both books: {seeds}\n")
    if not seeds:
        return
    tw = [by_seed["twins"][s] for s in seeds]
    da = [by_seed["data40k"][s] for s in seeds]
    rows = {"data40k minus 10-29": strata_row(da, ref, dk), "twins minus 10-29": strata_row(tw, ref, dk),
            "twins minus data40k": paired_row(tw, da, ref, dk)}
    print("| comparison | stratum | n | end-HP (se seq, se nets) | clears (se seq, se nets) |")
    print("|---|---|---|---|---|")
    for lab, r in rows.items():
        for st in STRATA:
            x = r[st]
            print(f"| {lab} | {st} | {x[6]} | {x[0]:+.2f} ({x[1]:.2f}, {x[2]:.2f}) | {x[3]:+.3f} ({x[4]:.3f}, {x[5]:.3f}) |")
    for s in seeds:
        r = paired_row([by_seed["twins"][s]], [by_seed["data40k"][s]], ref, dk)["held-out DF"]
        d = strata_row([by_seed["data40k"][s]], ref, dk)["held-out DF"]
        print(f"\nseed {s}, Demon Form decks: twins minus data40k {r[0]:+.2f} ({r[1]:.2f}); data40k minus 10-29 {d[0]:+.2f} ({d[1]:.2f})")

    def z(x):
        se = max(x[1], x[2]) if x[2] == x[2] else x[1]
        return x[0] / se if se else 0.0
    td, dr = rows["twins minus data40k"]["held-out DF"], rows["data40k minus 10-29"]["held-out DF"]
    if z(td) >= 2 and abs(z(dr)) < 2:
        branch = "pool (step 2)"
    elif z(dr) >= 2 and z(td) < 2:
        branch = "recipe (stop and close)"
    else:
        branch = "between (step 2, twins minus data40k as its reference)"
    print(f"\nbranch: {branch} (twins minus data40k on Demon Form decks {td[0]:+.2f} at {z(td):.1f} se; "
          f"data40k minus 10-29 {dr[0]:+.2f} at {z(dr):.1f} se)")


LT_DOSES = {"5k": ("allcontent5k", "data5k"), "20k": ("allcontent20k", "data20k")}


def later_ticks_dose(root):
    """Lane from-scratch-later-ticks step 2: per dose, allcontent<dose>-s1 r1
    minus its twin data<dose>-s1 r1 (@hpb0.01@tsl1, both cell books), paired by
    sequence, strata from the 10-29 net @tsl1; go at a dose if Demon Form decks
    are 2 se above the twin and train is within -0.9 HP."""
    g = root / "results" / "gauntlet"
    dk = decks()
    names = {p.name[:-5] for p in g.glob("*.json")}
    ref = load_union(g, TSL_FILES)
    print("| comparison | stratum | n | end-HP (se seq) | clears (se seq) |")
    print("|---|---|---|---|---|")
    verdicts = []
    for dose, (arm, twin) in LT_DOSES.items():
        a = complete_nets(g, names, rf"rerank-2026-1\d-\d\d-{arm}-s1-r1-\w+-hpb0\.01-tsl1")
        b = complete_nets(g, names, rf"rerank-2026-1\d-\d\d-{twin}-s1-r1-\w+-hpb0\.01-tsl1")
        if len(a) != 1 or len(b) != 1:
            verdicts.append(f"{dose}: not complete (arm {len(a)}, twin {len(b)})")
            continue
        rows = {f"{arm} minus {twin}": paired_row(a, b, ref, dk), f"{arm} minus 10-29": strata_row(a, ref, dk),
                f"{twin} minus 10-29": strata_row(b, ref, dk)}
        for lab, r in rows.items():
            for st in STRATA:
                x = r[st]
                print(f"| {lab} | {st} | {x[6]} | {x[0]:+.2f} ({x[1]:.2f}) | {x[3]:+.3f} ({x[4]:.3f}) |")
        p = rows[f"{arm} minus {twin}"]
        df, tr = p["held-out DF"], p["train"]
        z = df[0] / df[1] if df[1] else 0.0
        go = z >= 2 and tr[0] >= -0.9
        verdicts.append(f"{dose}: {'go' if go else 'no go'} (Demon Form decks {df[0]:+.2f} at {z:.1f} se; train {tr[0]:+.2f})")
    print()
    for v in verdicts:
        print(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--step1b", action="store_true", help="the strata, by-card, two-turn and generated-bench tables")
    ap.add_argument("--tsl", action="store_true", help="lane turn-start-leaf: the flag against the plain leaf")
    ap.add_argument("--later-ticks", action="store_true", help="lane from-scratch-later-ticks step 1: data40k against the twins")
    ap.add_argument("--later-ticks-dose", action="store_true", help="lane from-scratch-later-ticks step 2: each dose against its twin")
    a = ap.parse_args()
    if a.later_ticks_dose:
        return later_ticks_dose(Path(a.root))
    if a.later_ticks:
        return later_ticks(Path(a.root))
    if a.step1b:
        return step1b(Path(a.root))
    if a.tsl:
        return tsl(Path(a.root))
    g = Path(a.root) / "results" / "gauntlet"
    heur = {b: load(g / f) for b, f in BOOKS.items()}
    names = {p.name[:-5] for p in g.glob("*.json")}
    print("| nets | seeds | train HP | held-out HP | gap HP | train clears | held-out clears | gap clears | missing |")
    print("|---|---|---|---|---|---|---|---|---|")
    for label, pat in GROUPS:
        bases = sorted(n for n in names if re.fullmatch(pat, n))
        per_net, missing = [], []
        for base in bases:
            # a file with fewer than SEQUENCES rows is still being written
            done = {b for b in BOOKS if base + b in names and len(load(g / f"{base}{b}.json")) >= SEQUENCES}
            books = [b for b in BOOKS if b in done]
            missing += [base + b for b in BOOKS if b not in done]
            if len(books) < len(BOOKS):
                continue
            e = [edges(load(g / f"{base}{b}.json"), heur[b]) for b in books]
            v = {h: tuple(sum(x[h][i] for x in e) / len(e) for i in (0, 1)) for h in ("train", "held_out")}
            per_net.append(v)
        if not per_net:
            print(f"| {label} | 0 | | | | | | | {len(missing)} |")
            continue
        cols = []
        for i in (0, 1):
            tr = [v["train"][i] for v in per_net]
            ho = [v["held_out"][i] for v in per_net]
            for xs in (tr, ho, [a - b for a, b in zip(tr, ho)]):
                m, se = mean_se(xs)
                cols.append(f"{m:+.2f} ({se:.2f})" if i == 0 else f"{m:+.3f} ({se:.3f})")
        print(f"| {label} | {len(per_net)} | " + " | ".join(cols) + f" | {len(missing)} |")


if __name__ == "__main__":
    main()
