"""Random-world bench (docs/specs/random-world-bench.md, lane
random-world-bench): worlds of k generated enemy mechanics stacked on the
official Act 1 elites, read paired against the sum of the same items'
single costs on the same starts and seeds (the base file,
results/mutate/gen-enemies-b1.json).

    .venv/Scripts/python.exe scripts/analysis/random_world.py check --starts 3
    .venv/Scripts/python.exe scripts/analysis/random_world.py play --worlds 20 --ks 2,4,8 --side 10 --threads 3 --out results/mutate/rw-pilot.json
    .venv/Scripts/python.exe scripts/analysis/random_world.py read results/mutate/rw-pilot.json [--write] [--check]
    .venv/Scripts/python.exe scripts/analysis/random_world.py nd-play --worlds 40 --side 10 --out results/mutate/rw-nodeath.json
    .venv/Scripts/python.exe scripts/analysis/random_world.py nd-read results/mutate/rw-nodeath.json [--write] [--check]

nd-play / nd-read (step 4, docs/specs/random-world-bench-nodeath.md): the
parent, each mechanic alone and the worlds, all in no-death mode on one
shared start set, so HP lost is never capped.

Cost per start and seed: the net's HP-lost change from the parent minus the
heuristic's. S: the same summed over the world's items played one at a
time (the base file). g = cost - 1.5 S per world; go if g > 2 se at k 4 or
8, additive if g < -2 se at every k, else open.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

SEED = 20261109
BENCH_SEED = 20261103  # mutate_monsters' per-start seeds
SIDE_OFFSET = 1000
COLLAPSE = ("GE-OppCard-Weak", "GE-OppCard-Vulnerable", "GE-AttackLoss-Vulnerable")
BASE = "results/mutate/gen-enemies-b1.json"
MIN_WORLDS = 10
FEW_STARTS = 10


def gen_names():
    sys.path.insert(0, os.path.dirname(__file__))
    import mutate_monsters as mm  # noqa: E402  (loads sts)
    return list(mm.GEN)


def pools(names):
    """(main pool, side pool): the side pool is every generated mechanic."""
    return [m for m in names if m not in COLLAPSE], list(names)


def items(w, k, pool):
    """World w's first k items: nested in k (one permutation per world)."""
    if k > len(pool):
        raise SystemExit(f"k {k} is larger than the pool ({len(pool)} mechanics)")
    perm = np.random.default_rng([SEED, w]).permutation(len(pool))
    return [pool[j] for j in perm[:k]]


def loss(row, arr):
    return np.array([row["hp"] - h for _, h in arr], float)


def predicted_loss(row, its):
    """The net's parent loss plus the items' raw single costs (base seeds' means)."""
    par = loss(row, row["parent"]["one"]).mean()
    return par + sum(loss(row, row["mods"][m]["one"]).mean() - par for m in its)


def eligible(rows, its):
    """Elite rows the singles predict the net survives with all items."""
    return [r for r in rows if r["group"] == "elite" and predicted_loss(r, its) < r["hp"]]


def choose(w, k, elig, n):
    perm = np.random.default_rng([SEED, w, k]).permutation(len(elig))
    return [elig[j] for j in perm[:n]]


def single_sum(row, its, s):
    """Per seed (first s): the items' summed single costs beyond the heuristic."""
    tot = np.zeros(s)
    for m in its:
        q = row["mods"][m]
        tot += (loss(row, q["one"][:s]) - loss(row, row["parent"]["one"][:s])) \
            - (loss(row, q["heuristic"][:s]) - loss(row, row["parent"]["heuristic"][:s]))
    return tot


def world_stats(world, by_key):
    """cost, S and deaths of one played world, per start and seed pooled."""
    cost, S, dn, dh, dp = [], [], [], [], []
    for (i, f), net, heur in zip(world["starts"], world["res"]["one"], world["res"]["heuristic"]):
        row = by_key[(i, f)]
        s = len(net)
        par_n, par_h = loss(row, row["parent"]["one"][:s]), loss(row, row["parent"]["heuristic"][:s])
        cost += list((loss(row, net) - par_n) - (loss(row, heur) - par_h))
        S += list(single_sum(row, world["items"], s))
        dn += [not w for w, _ in net]
        dh += [not w for w, _ in heur]
        raw = par_n + sum(loss(row, row["mods"][m]["one"][:s]) - par_n for m in world["items"])
        dp += list(raw >= row["hp"])
    return {"cost": float(np.mean(cost)), "S": float(np.mean(S)), "deaths_net": float(np.mean(dn)),
            "deaths_heur": float(np.mean(dh)), "deaths_pred": float(np.mean(dp)), "n_starts": len(world["starts"])}


def mean_se(xs):
    xs = np.asarray(xs, float)
    return float(xs.mean()), float(xs.std(ddof=1) / np.sqrt(len(xs))) if len(xs) > 1 else float("inf")


def summarise(stats):
    """stats: [(pool, k, world stats)] -> {(pool, k): row of the table}."""
    out = {}
    for pool, k in sorted({(p, k) for p, k, _ in stats}):
        ws = [s for p, kk, s in stats if p == pool and kk == k]
        c = np.array([s["cost"] for s in ws])
        S = np.array([s["S"] for s in ws])
        out[(pool, k)] = {"worlds": len(ws), "cost": mean_se(c), "S": mean_se(S), "inter": mean_se(c - S),
                          "g": mean_se(c - 1.5 * S), "ratio": float(c.mean() / S.mean()) if S.mean() else None,
                          "deaths_net": float(np.mean([s["deaths_net"] for s in ws])),
                          "deaths_heur": float(np.mean([s["deaths_heur"] for s in ws])),
                          "deaths_pred": float(np.mean([s["deaths_pred"] for s in ws])),
                          "few_starts": sum(s["n_starts"] < FEW_STARTS for s in ws)}
    return out


def verdict(table, pool="main"):
    ks = sorted(k for p, k in table if p == pool)
    g = {k: table[(pool, k)]["g"] for k in ks}
    if any(k in (4, 8) and m > 2 * se for k, (m, se) in g.items()):
        return "go"
    if ks and all(m < -2 * se for m, se in g.values()):
        return "additive"
    return "open"


def check_passes(table, pool="main"):
    ks = [k for p, k in table if p == pool]
    return bool(ks) and verdict(table, pool) != "open" and all(table[(pool, k)]["worlds"] >= MIN_WORLDS for k in ks)


def table_text(table):
    f = lambda ms: f"{ms[0]:+.2f} ({ms[1]:.2f})"  # noqa: E731
    lines = ["| pool | k | worlds | cost | S (sum of singles) | cost - S | g = cost - 1.5 S | ratio | deaths net / heur / pred | few-start worlds |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for (pool, k), t in sorted(table.items()):
        ratio = f"{t['ratio']:.2f}" if t["ratio"] is not None else "-"
        lines.append(f"| {pool} | {k} | {t['worlds']} | {f(t['cost'])} | {f(t['S'])} | {f(t['inter'])} | {f(t['g'])} | "
                     f"{ratio} | {t['deaths_net']:.2f} / {t['deaths_heur']:.2f} / {t['deaths_pred']:.2f} | {t['few_starts']} |")
    lines.append("")
    lines += [f"verdict ({p}): {verdict(table, p)}" for p in sorted({p for p, _ in table})]
    return "\n".join(lines)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_cmd(args):
    done = load(args.file)
    base = load(done["settings"]["base"])
    by_key = {(r["i"], r["floor"]): r for r in base["rows"]}
    stats = [(w["pool"], w["k"], world_stats(w, by_key)) for w in done["worlds"]]
    table = summarise(stats)
    text = table_text(table)
    print(text)
    if args.write:
        out = os.path.splitext(args.file)[0] + "-table.md"
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# {os.path.basename(args.file)}\n\n{text}\n")
        print(out)
    if args.check:
        return 0 if check_passes(table) else 1
    return 0


# ---- engine play ----

def engine(base):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.path.dirname(__file__))
    import bias_audit as ba  # noqa: E402
    import mutate_monsters as mm  # noqa: E402
    import sts  # noqa: E402
    got = sts.load_content(mm.gen_pack())
    if got != base["settings"]["gen_pack"]:
        raise SystemExit(f"gen pack hash {got} differs from the base file's {base['settings']['gen_pack']}")
    mm.PLAYERS["one"] = base["settings"]["net"] + "@hpb0.01"
    with open(base["settings"]["product"], encoding="utf-8") as f:
        specs = {(s["i"], s["floor"]): s for s in ba.fights(json.load(f), 100000)}
    return mm, sts, specs


def bench_seeds(spec, n_base, s):
    return [int(x) for x in np.random.default_rng([BENCH_SEED, spec["i"], spec["floor"]]).integers(2**62, size=n_base)][:s]


def start_state(sts, spec, no_death):
    """mutate_monsters.start_state with the no-death switch."""
    c = sts.Combat(spec["deck"], spec["encounter"], seed=spec["seed"], hp=spec["hp"], character=spec["character"],
                   no_death=no_death)
    while not c.is_over() and not c.awaiting_action():
        c.advance()
    return c


def play_starts(mm, sts, specs, keys, patches, s, n_base, player, threads, no_death=False):
    """[[(won, hp_end)] per seed] per start key, all starts in one play_on."""
    import bench  # noqa: E402
    name = mm.PLAYERS[player]
    ev = bench.load_evaluator(name) if name else None
    kw = {"limit": bench.LIMIT, "threads": threads}
    if ev is not None:
        kw.update(evaluator=ev.evaluator, features=ev.features)
    games = []
    for key in keys:
        c = start_state(sts, specs[key], True) if no_death else mm.start_state(specs[key])
        v = mm.variant(c, patches)
        games += [v.with_seed(x) for x in bench_seeds(specs[key], n_base, s)]
    res = sts.play_on(games, **kw)
    return [[[bool(r["won"]), int(r["hp_end"])] for r in res[j * s:(j + 1) * s]] for j in range(len(keys))]


def plan(base, worlds, ks, side, n_starts):
    main, side_pool = pools(gen_names())
    rows = base["rows"]
    out = []
    for pool_name, pool, ids in (("main", main, range(worlds)), ("side", side_pool, range(SIDE_OFFSET, SIDE_OFFSET + side))):
        for w in ids:
            for k in ks:
                its = items(w, k, pool)
                elig = eligible(rows, its)
                ch = choose(w, k, elig, n_starts)
                out.append({"w": w, "pool": pool_name, "k": k, "items": its, "eligible": len(elig),
                            "starts": [[r["i"], r["floor"]] for r in ch]})
    return out


def play_cmd(args):
    base = load(args.base)
    n_base = base["settings"]["seeds"]
    ks = [int(x) for x in args.ks.split(",")]
    done = {"settings": {"base": args.base, "net": base["settings"]["net"], "gen_pack": base["settings"]["gen_pack"],
                         "starts": args.starts, "seeds": args.seeds, "seed": SEED}, "worlds": []}
    if os.path.exists(args.out):
        done = load(args.out)
    have = {(w["pool"], w["w"], w["k"]) for w in done["worlds"]}
    todo = [c for c in plan(base, args.worlds, ks, args.side, args.starts) if (c["pool"], c["w"], c["k"]) not in have]
    mm, sts, specs = engine(base)
    t0 = time.perf_counter()
    for n, cell in enumerate(todo):
        keys = [tuple(x) for x in cell["starts"]]
        patches = [p for m in cell["items"] for p in mm.ALL[m]]
        cell["res"] = {p: play_starts(mm, sts, specs, keys, patches, args.seeds, n_base, p, args.threads)
                       for p in ("heuristic", "one")}
        done["worlds"].append(cell)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        tmp = args.out + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(done, f)
        os.replace(tmp, args.out)
        print(f"{n + 1} / {len(todo)}: {cell['pool']} world {cell['w']} k {cell['k']} "
              f"({len(keys)} of {cell['eligible']} eligible starts), {time.perf_counter() - t0:.0f} s", flush=True)
    print(args.out)
    return 0


def check_cmd(args):
    """Replay the parent and world 0's first item on its first starts; exit 1 on any difference."""
    base = load(args.base)
    n_base = base["settings"]["seeds"]
    cell = plan(base, 1, [2], 0, args.starts)[0]
    mm, sts, specs = engine(base)
    by_key = {(r["i"], r["floor"]): r for r in base["rows"]}
    keys = [tuple(x) for x in cell["starts"]]
    m = cell["items"][0]
    bad = 0
    for p in ("heuristic", "one"):
        for patches, pick in (([], lambda r: r["parent"][p]), (mm.ALL[m], lambda r: r["mods"][m][p])):
            got = play_starts(mm, sts, specs, keys, patches, args.seeds, n_base, p, args.threads)
            for key, g in zip(keys, got):
                want = [list(x) for x in pick(by_key[key])[:args.seeds]]
                if g != want:
                    bad += 1
                    print(f"differs: {key} {p} {'parent' if not patches else m}: {g} != {want}")
    print(f"check: {len(keys)} starts x {args.seeds} seeds, parent and {m}, {bad} differences")
    return 1 if bad else 0


# ---- step 4: no-death worlds (docs/specs/random-world-bench-nodeath.md) ----

ND_STARTS_SEED = 4


def nd_starts(rows, n):
    """One shared start set: the first n elite rows of a fixed permutation."""
    elite = [r for r in rows if r["group"] == "elite"]
    perm = np.random.default_rng([SEED, ND_STARTS_SEED]).permutation(len(elite))
    return [[elite[j]["i"], elite[j]["floor"]] for j in perm[:n]]


def nd_plan(names, worlds, ks, side):
    """Cells in play order: the parent, each mechanic alone, then the worlds."""
    main, side_pool = pools(names)
    cells = [{"kind": "parent", "pool": "-", "w": -1, "k": 0, "items": []}]
    cells += [{"kind": "single", "pool": "-", "w": -1, "k": 1, "items": [m]} for m in names]
    for pool_name, pool, ids in (("main", main, range(worlds)), ("side", side_pool, range(SIDE_OFFSET, SIDE_OFFSET + side))):
        for w in ids:
            for k in ks:
                cells.append({"kind": "world", "pool": pool_name, "w": w, "k": k, "items": items(w, k, pool)})
    return cells


def nd_key(c):
    return (c["kind"], c["pool"], c["w"], c["k"], tuple(c["items"]))


def nd_todo(cells, done_cells):
    have = {nd_key(c) for c in done_cells}
    return [c for c in cells if nd_key(c) not in have]


def nd_world_stats(done):
    """[(pool, k, stats)] per world cell, paired on the file's own parent and singles."""
    H = np.array(done["start_hp"], float)[:, None]
    cells = done["cells"]
    parent = next(c for c in cells if c["kind"] == "parent")
    single = {c["items"][0]: c for c in cells if c["kind"] == "single"}

    def loss(cell, p):
        return H - np.array([[h for _, h in r] for r in cell["res"][p]], float)

    def won(cell, p):
        return np.array([[w for w, _ in r] for r in cell["res"][p]], bool)

    pn, ph = loss(parent, "one"), loss(parent, "heuristic")
    out = []
    for c in cells:
        if c["kind"] != "world" or any(m not in single for m in c["items"]):
            continue
        ln, lh = loss(c, "one"), loss(c, "heuristic")
        sn = sum(loss(single[m], "one") - pn for m in c["items"])
        sh = sum(loss(single[m], "heuristic") - ph for m in c["items"])
        out.append((c["pool"], c["k"], {
            "cost": float(((ln - pn) - (lh - ph)).mean()), "S": float((sn - sh).mean()),
            "deaths_net": float((ln >= H).mean()), "deaths_heur": float((lh >= H).mean()),
            "deaths_pred": float((pn + sn >= H).mean()), "n_starts": len(done["starts"]),
            "stalls_net": float((~won(c, "one")).mean()), "stalls_heur": float((~won(c, "heuristic")).mean()),
            "raw_net": float((ln - pn).mean()), "pred_net": float(sn.mean())}))
    return out


def save(done, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(done, f)
    os.replace(tmp, path)


def nd_play_cmd(args):
    base = load(args.base)
    n_base = base["settings"]["seeds"]
    ks = [int(x) for x in args.ks.split(",")]
    mm, sts, specs = engine(base)
    starts = nd_starts(base["rows"], args.starts)
    done = {"settings": {"base": args.base, "net": base["settings"]["net"], "gen_pack": base["settings"]["gen_pack"],
                         "starts": args.starts, "seeds": args.seeds, "seed": SEED, "no_death": True},
            "starts": starts, "start_hp": [specs[tuple(k)]["hp"] for k in starts], "cells": []}
    if os.path.exists(args.out):
        old = load(args.out)
        if old["starts"] != starts or old["settings"]["seeds"] != args.seeds:
            raise SystemExit(f"{args.out} was played on other starts or seeds")
        done = old
    keys = [tuple(k) for k in starts]
    todo = nd_todo(nd_plan(list(mm.GEN), args.worlds, ks, args.side), done["cells"])
    t0 = time.perf_counter()
    for n, cell in enumerate(todo):
        patches = [p for m in cell["items"] for p in mm.ALL[m]]
        cell["res"] = {p: play_starts(mm, sts, specs, keys, patches, args.seeds, n_base, p, args.threads, no_death=True)
                       for p in ("heuristic", "one")}
        done["cells"].append(cell)
        save(done, args.out)
        print(f"{n + 1} / {len(todo)}: {cell['kind']} {cell['pool']} world {cell['w']} k {cell['k']}, "
              f"{time.perf_counter() - t0:.0f} s", flush=True)
    print(args.out)
    return 0


def nd_table_text(stats, table):
    lines = [table_text(table), "",
             "| pool | k | net raw loss: world / summed singles | at or below 0 HP net / heur / pred | turn-limit losses net / heur |",
             "|---|---|---|---|---|"]
    for pool, k in sorted(table):
        ws = [s for p, kk, s in stats if p == pool and kk == k]
        m = lambda key: float(np.mean([s[key] for s in ws]))  # noqa: E731
        lines.append(f"| {pool} | {k} | {m('raw_net'):+.2f} / {m('pred_net'):+.2f} | {m('deaths_net'):.2f} / "
                     f"{m('deaths_heur'):.2f} / {m('deaths_pred'):.2f} | {m('stalls_net'):.2f} / {m('stalls_heur'):.2f} |")
    return "\n".join(lines)


def nd_read_cmd(args):
    stats = nd_world_stats(load(args.file))
    table = summarise(stats)
    text = nd_table_text(stats, table)
    print(text)
    if args.write:
        out = os.path.splitext(args.file)[0] + "-table.md"
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# {os.path.basename(args.file)} (no-death mode)\n\n{text}\n")
        print(out)
    if args.check:
        return 0 if check_passes(table) else 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("--worlds", type=int, default=20)
    p.add_argument("--ks", default="2,4,8")
    p.add_argument("--side", type=int, default=0, help="worlds drawn from all 24 mechanics")
    p.add_argument("--starts", type=int, default=50)
    p.add_argument("--seeds", type=int, default=4)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--base", default=BASE)
    p.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("--starts", type=int, default=3)
    c.add_argument("--seeds", type=int, default=4)
    c.add_argument("--threads", type=int, default=3)
    c.add_argument("--base", default=BASE)
    r = sub.add_parser("read")
    r.add_argument("file")
    r.add_argument("--write", action="store_true")
    r.add_argument("--check", action="store_true")
    q = sub.add_parser("nd-play")
    q.add_argument("--worlds", type=int, default=40)
    q.add_argument("--ks", default="2,4,8")
    q.add_argument("--side", type=int, default=0, help="worlds drawn from all 24 mechanics")
    q.add_argument("--starts", type=int, default=50)
    q.add_argument("--seeds", type=int, default=4)
    q.add_argument("--threads", type=int, default=3)
    q.add_argument("--base", default=BASE)
    q.add_argument("--out", required=True)
    t = sub.add_parser("nd-read")
    t.add_argument("file")
    t.add_argument("--write", action="store_true")
    t.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    return {"play": play_cmd, "check": check_cmd, "read": read_cmd, "nd-play": nd_play_cmd,
            "nd-read": nd_read_cmd}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
