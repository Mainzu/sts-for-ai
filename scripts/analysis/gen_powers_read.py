"""Generated powers, first check (docs/specs/registry-lite.md step 6): the
champion (seed-check r2 s1) against the heuristic on held-out tight2 cells
whose deck holds an official power card from check 9 (Metallicize, Demon
Form), and on paired twins with that card swapped for a generated test-split
power card (gen_content.py pack, seed 1, 128 powers). Paired by cell: lead
on generated minus lead on original.

    .venv/Scripts/python scripts/analysis/gen_powers_read.py build
    .venv/Scripts/python scripts/analysis/gen_powers_read.py read --threads 6 --out results/gen_powers/first-check.json

Training arms (docs/specs/gen-training-arms.md): a 12-fight bench, each
net's results saved once, then arms read against a control, net against
net, paired by cell and seed index:

    .venv/Scripts/python scripts/analysis/gen_powers_read.py build --seeds 12 --bench data/bench/gen_powers12.json
    .venv/Scripts/python scripts/analysis/gen_powers_read.py play --bench data/bench/gen_powers12.json --nets runs/<id> ...
    .venv/Scripts/python scripts/analysis/gen_powers_read.py arms --bench data/bench/gen_powers12.json --control lean-thr --arms lean-gen16 lean-gen128

Adaptation burst (docs/specs/adaptation-burst.md): the burst nets (`play`
first, champion included) against the champion, the burst's own cards
(target) against the other generated cards and the original fights:

    .venv/Scripts/python scripts/analysis/gen_powers_read.py burst --bench data/bench/gen_powers12c3.json --arms burst8 --out results/gen_powers/burst8.json
"""

import argparse
import glob
import json
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import selfplay  # noqa: E402

BENCH = "data/bench/gen_powers.json"
PACK = "data/bench/gen_powers_pack.json"
CHAMPION = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt"
POWERS = {"Metallicize": 1, "Demon Form": 3}  # check-9 cards of Power type, and their costs
SEEDS = 4  # fights per cell (tight2 has 20 per cell; the first 4)
PICK_SEED = 6


def build(seeds=SEEDS, path=BENCH, copies=1, first=0, pick_seed=PICK_SEED):
    pack = json.load(open(PACK, encoding="utf-8"))
    _, h = selfplay.load_content(PACK)
    life = {p["id"]: p["lifetime"] for p in pack["powers"]}
    test = sorted((c for c in pack["cards"] if c["split"] == "test"), key=lambda c: c["id"])
    by_cost = {}
    for c in test:
        by_cost.setdefault(c["cost"], []).append(c)
    held = json.load(open("data/bench/tight2.json", encoding="utf-8"))["halves"]["held_out"]
    cells = {}
    for s in held:
        cells.setdefault(s["cell"], []).append(s)
    rng = random.Random(pick_seed)
    out = []
    for cell in sorted(cells):
        fights = cells[cell][first:first + seeds]
        deck = fights[0]["deck"]
        kinds = sorted({x.rstrip("+") for x in deck} & set(POWERS))
        if not kinds:
            continue
        kind = rng.choice(kinds)
        # copies > 1: Strikes, then Defends, become more copies of the swapped
        # card in both sets, so the card is drawn and matters in more fights
        extra = copies - sum(x.rstrip("+") == kind for x in deck)
        for base in ("Strike", "Defend"):
            while extra > 0 and base in deck:
                deck = list(deck)
                deck[deck.index(base)] = kind
                extra -= 1
        # Same cost if the pack has one; the generator prices no test card at
        # 3, so Demon Form's twin is the dearest there is (2).
        cost = max(c for c in by_cost if c <= POWERS[kind])
        card = rng.choice(by_cost[cost])
        gdeck = [f"gen:{card['id']}" if x.rstrip("+") == kind else x for x in deck]
        info = {"swapped": kind, "copies": sum(x.rstrip("+") == kind for x in deck), "gen_card": card["id"],
                "gen_cost": card["cost"], "orig_cost": POWERS[kind], "lifetime": life[card["power"]],
                "triggers": sorted({json.dumps(hk["trigger"], sort_keys=True) for hk in
                                    next(p for p in pack["powers"] if p["id"] == card["power"])["hooks"]
                                    if hk["effects"] != ["RemoveSelf"]}),  # not the this-turn lifetime hook
                "priced": card["value_per_energy"] is not None}
        for s in fights:
            out.append({**s, "set": "original", "deck": deck, **info})
            out.append({**s, "set": "generated", "deck": gdeck, **info})
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"set": "gen_powers", "version": 1, "pack": PACK, "content_hash": h,
                   "source": f"tight2 held_out, "
                             + (f"first {seeds} fights" if first == 0 else f"fights {first}-{first + seeds - 1}")
                             + " per cell"
                             + (f", pick seed {pick_seed}" if pick_seed != PICK_SEED else "")
                             + (f", swapped card at {copies} copies" if copies > 1 else ""), "fights": out}, f, indent=1)
    n = len(out) // (2 * seeds)
    print(f"{n} cells, {len(out)} fights -> {path} (pack {h})")


def lead_by(fights, base, net, key):
    """{value of key: {cells, heur, net, lead, se}} with cell-level se."""
    out = {}
    for v in sorted({key(f) for f in fights}):
        cells = {}
        for i, f in enumerate(fights):
            if key(f) == v:
                cells.setdefault(f["cell"], []).append((base[i], net[i]))
        a = np.array([np.mean(x, 0) for x in cells.values()])
        d = a[:, 1] - a[:, 0]
        out[v] = {"cells": len(a), "heur": float(a[:, 0].mean()), "net": float(a[:, 1].mean()),
                  "lead": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None}
    return out


def paired(fights, base, net, key):
    """{value: {cells, heur_diff, lead_diff, se}}: generated minus original per cell."""
    per = {}
    for i, f in enumerate(fights):
        per.setdefault((key(f), f["cell"]), {}).setdefault(f["set"], []).append((base[i], net[i]))
    out = {}
    for v in sorted({k for k, _ in per}):
        h, d = [], []
        for (k, _), sets in per.items():
            if k != v:
                continue
            g, o = np.mean(sets["generated"], 0), np.mean(sets["original"], 0)
            h.append(g[0] - o[0])
            d.append((g[1] - g[0]) - (o[1] - o[0]))
        h, d = np.array(h), np.array(d)
        se = lambda x: float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else None  # noqa: E731
        out[v] = {"cells": len(d), "heur_diff": float(h.mean()), "heur_se": se(h),
                  "lead_diff": float(d.mean()), "se": se(d)}
    return out


def load_bench(path, limit=0):
    """(bench dict, its fights: the first `limit` cells' only, if set), with
    the bench's pack loaded."""
    b = json.load(open(path, encoding="utf-8"))
    _, h = selfplay.load_content(b["pack"])
    assert h == b["content_hash"], (h, b["content_hash"])
    fights = b["fights"]
    if limit:
        keep = set(sorted({f["cell"] for f in fights})[:limit])
        fights = [f for f in fights if f["cell"] in keep]
    return b, fights


def read(args):
    b = json.load(open(args.bench, encoding="utf-8"))
    _, h = selfplay.load_content(b["pack"])
    assert h == b["content_hash"], (h, b["content_hash"])
    fights = b["fights"][:args.limit * 2 * SEEDS] if args.limit else b["fights"]
    search = {"limit": bench.LIMIT, "threads": args.threads}
    t = time.time()
    base = [float(r["won"]) for r in bench.run_specs(fights, search=search)]
    print(f"heuristic {np.mean(base):.3f} ({time.time() - t:.0f}s)", flush=True)
    t = time.time()
    net = [float(r["won"]) for r in bench.run_specs(fights, ev=bench.load_evaluator(args.champion), search=search)]
    print(f"champion {np.mean(net):.3f} ({time.time() - t:.0f}s)", flush=True)
    gen = [i for i, f in enumerate(fights) if f["set"] == "generated"]
    gsub = ([fights[i] for i in gen], [base[i] for i in gen], [net[i] for i in gen])
    summary = {
        "by_set_group": lead_by(fights, base, net, lambda f: f"{f['set']} {f['group']}"),
        "by_set": lead_by(fights, base, net, lambda f: f["set"]),
        "paired_all": paired(fights, base, net, lambda f: "all"),
        "paired_group": paired(fights, base, net, lambda f: f["group"]),
        "paired_swapped": paired(fights, base, net, lambda f: f["swapped"]),
        "generated_by_lifetime": lead_by(*gsub, lambda f: f["lifetime"]),
        "generated_by_trigger": lead_by(*gsub, lambda f: " + ".join(f["triggers"])),
        "generated_by_priced": lead_by(*gsub, lambda f: "priced" if f["priced"] else "unpriced"),
    }
    for name, tab in summary.items():
        print(f"== {name}")
        for k, r in tab.items():
            se = f"{r['se']:.3f}" if r["se"] is not None else "-"
            if "lead_diff" in r:
                print(f"  {k:40s} cells {r['cells']:4d} heur gen-orig {r['heur_diff']:+.3f} "
                      f"lead gen-orig {r['lead_diff']:+.3f} (se {se})")
            else:
                print(f"  {k:40s} cells {r['cells']:4d} heur {r['heur']:.3f} net {r['net']:.3f} "
                      f"lead {r['lead']:+.3f} (se {se})")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"champion": args.champion, "bench": BENCH, "content_hash": h, "summary": summary,
                   "won": {"heuristic": base, "champion": net}}, f, indent=1)


def net_out(net, bench_path, limit=0):
    """Where `play` saves a net's results on a bench; a player string's
    settings (`.pt@hpb0.01@tsl1`) join the name (`-hpb0.01-tsl1`)."""
    net, at, settings = net.partition(".pt@")
    net = net + ".pt" if at else net
    rid = os.path.basename(os.path.dirname(net)) if net.endswith(".pt") else os.path.basename(net.rstrip("/\\"))
    rid += "-" + settings.replace("@", "-") if at else ""
    tag = os.path.splitext(os.path.basename(bench_path))[0] + (f"-limit{limit}" if limit else "")
    return os.path.join("results", "gen_powers", "arms", tag, f"{rid}.json")


def play(args):
    """Each net's per-fight won on the bench, saved once per net."""
    b, fights = load_bench(args.bench, args.limit)
    search = {"limit": bench.LIMIT, "threads": args.threads}
    for net in args.nets:
        out = net_out(net, args.bench, args.limit)
        if os.path.exists(out):
            print(f"{out} exists, skipped", flush=True)
            continue
        model = net if net.endswith(".pt") or ".pt@" in net else os.path.join(net, "model.pt")
        t = time.time()
        won = [float(r["won"]) for r in bench.run_specs(fights, ev=bench.load_evaluator(model), search=search)]
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"net": model, "bench": args.bench, "content_hash": b["content_hash"], "won": won}, f)
        print(f"{out}: {np.mean(won):.3f} ({time.time() - t:.0f}s)", flush=True)


def arm_diff(fights, ctrl, arm, key):
    """{slice: {cells, diff, se, per_seed}}: arm minus control; per seed
    index, the mean over cells of the per-cell mean difference; then the
    mean over seeds, with se from the seed means' spread. `ctrl` / `arm`:
    one won list per seed index, aligned with `fights`; `key(f)` names a
    fight's slice (None: left out)."""
    out = {}
    for v in sorted({k for k in map(key, fights) if k is not None}):
        per_seed, cells = [], set()
        for c, a in zip(ctrl, arm):
            by = {}
            for i, f in enumerate(fights):
                if key(f) == v:
                    by.setdefault(f["cell"], []).append(a[i] - c[i])
            cells |= set(by)
            per_seed.append(float(np.mean([np.mean(x) for x in by.values()])))
        m = np.array(per_seed)
        out[v] = {"cells": len(cells), "diff": float(m.mean()),
                  "se": float(m.std(ddof=1) / np.sqrt(len(m))) if len(m) > 1 else None, "per_seed": per_seed}
    return out


ARM_SEEDS = ("s1", "s101", "s201")
ARM_SLICES = {
    "set": lambda f: f["set"],
    "original_swapped": lambda f: f["swapped"] if f["set"] == "original" else None,
    "generated_group": lambda f: f["group"] if f["set"] == "generated" else None,
    "generated_lifetime": lambda f: f["lifetime"] if f["set"] == "generated" else None,
    "generated_trigger": lambda f: " + ".join(f["triggers"]) if f["set"] == "generated" else None,
}


def arm_won(name, bench_path, limit=0):
    """One won list per seed index of run name `name`'s r2 nets."""
    out = []
    for s in ARM_SEEDS:
        run = sorted(glob.glob(f"runs/2026-1*-{name}-{s}-r2-*"))[-1]
        with open(net_out(run, bench_path, limit), encoding="utf-8") as f:
            out.append(json.load(f)["won"])
    return out


def arms(args):
    _, fights = load_bench(args.bench, args.limit)
    ctrl = arm_won(args.control, args.bench, args.limit)
    res = {}
    for name in args.arms:
        a = arm_won(name, args.bench, args.limit)
        res[name] = {sl: arm_diff(fights, ctrl, a, k) for sl, k in ARM_SLICES.items()}
        print(f"== {name} minus {args.control}")
        for sl, tab in res[name].items():
            for v, r in tab.items():
                se = f"{r['se']:.3f}" if r["se"] is not None else "-"
                seeds = " ".join(f"{x:+.3f}" for x in r["per_seed"])
                print(f"  {sl:20s} {str(v)[:44]:44s} cells {r['cells']:4d} {r['diff']:+.3f} (se {se})  [{seeds}]")
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"bench": args.bench, "control": args.control, "arms": res}, f, indent=1)


def burst_slices(targets):
    """The burst read's slices: target / other generated cards, originals."""
    def part(f):
        if f["set"] == "original":
            return "original"
        return "target" if f["gen_card"] in targets else "other"
    return {"part": part,
            "target_group": lambda f: f["group"] if part(f) == "target" else None,
            "other_group": lambda f: f["group"] if part(f) == "other" else None}


def cell_means(fights, ctrl, arm, keep):
    """Per cell (fights with keep(f)), the mean over seeds and fights of arm
    minus control."""
    by = {}
    for c, a in zip(ctrl, arm):
        for i, f in enumerate(fights):
            if keep(f):
                by.setdefault(f["cell"], []).append(a[i] - c[i])
    return np.array([np.mean(x) for x in by.values()])


def burst_contrast(fights, ctrl, arm, targets):
    """Target minus other generated cards: per seed, and pooled with an se
    from the per-cell spread of each side (cells taken as independent)."""
    part = burst_slices(targets)["part"]
    per = arm_diff(fights, ctrl, arm, part)
    t, o = (cell_means(fights, ctrl, arm, lambda f, v=v: part(f) == v) for v in ("target", "other"))
    se = lambda x: x.std(ddof=1) / np.sqrt(len(x))  # noqa: E731
    return {"contrast": float(t.mean() - o.mean()), "se": float(np.hypot(se(t), se(o))),
            "target": float(t.mean()), "target_se": float(se(t)), "other": float(o.mean()), "other_se": float(se(o)),
            "per_seed": [a - b for a, b in zip(per["target"]["per_seed"], per["other"]["per_seed"])]}


def burst_runs(name):
    """The burst's run dirs, one per seed index that was run, and its target cards."""
    runs = [sorted(g)[-1] for s in ARM_SEEDS if (g := glob.glob(f"runs/2026-1*-{name}-{s}-*"))]
    with open(os.path.join(runs[0], "config.json"), encoding="utf-8") as f:
        return runs, set(json.load(f)["content"]["cards"])


def burst(args):
    _, fights = load_bench(args.bench, args.limit)
    with open(net_out(args.champion, args.bench, args.limit), encoding="utf-8") as f:
        champ = json.load(f)["won"]
    res = {}
    for name in args.arms:
        runs, targets = burst_runs(name)
        arm = []
        for r in runs:
            with open(net_out(r, args.bench, args.limit), encoding="utf-8") as f:
                arm.append(json.load(f)["won"])
        ctrl = [champ] * len(arm)
        res[name] = {"runs": runs, "targets": sorted(targets), "contrast": burst_contrast(fights, ctrl, arm, targets),
                     **{sl: arm_diff(fights, ctrl, arm, k) for sl, k in burst_slices(targets).items()}}
        c = res[name]["contrast"]
        print(f"== {name} minus champion: target - other {c['contrast']:+.3f} (se {c['se']:.3f})  "
              f"[{' '.join(f'{x:+.3f}' for x in c['per_seed'])}]")
        for sl in burst_slices(targets):
            for v, r in res[name][sl].items():
                se = f"{r['se']:.3f}" if r["se"] is not None else "-"
                print(f"  {sl:14s} {v:10s} cells {r['cells']:4d} {r['diff']:+.3f} (se {se})  "
                      f"[{' '.join(f'{x:+.3f}' for x in r['per_seed'])}]")
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"bench": args.bench, "champion": args.champion, "bursts": res}, f, indent=1)


DEPTH_SLICES = {
    "group": lambda f: f["group"],
    "encounter": lambda f: f["encounter"],
    "trigger": lambda f: " + ".join(f["triggers"]),
    "lifetime": lambda f: f["lifetime"],
}


def depth(args):
    """Big-picture review 2026-11-01 rank 4: one net (or the heuristic) at
    one turn and under the fallback two-turn player on the bench's
    `--groups` fights; per cell, (two - one) on the generated twin minus
    (two - one) on the original, with an se over cells."""
    import ladder
    sys.path.insert(0, os.path.dirname(__file__))
    import depth_paired
    b, fights = load_bench(args.bench, args.limit)
    groups = args.groups.split(",")
    idx = [i for i, f in enumerate(fights) if f["group"] in groups]
    specs = [{k: fights[i][k] for k in ("character", "deck", "encounter", "hp", "seed")} for i in idx]
    net = args.nets[0]
    model = net if net == "heuristic" or net.endswith(".pt") else os.path.join(net, "model.pt")
    tag = (f"heuristic-limit{args.limit}" if args.limit else "heuristic") if net == "heuristic" \
        else os.path.basename(net_out(net, args.bench, args.limit))[:-5]
    stem = os.path.splitext(os.path.basename(args.bench))[0]
    if stem != "gen_powers12c3":  # the first depth read's files keep their names
        tag = f"{stem}-{tag}"
    out = os.path.join("results", "gen_powers", "depth", f"{tag}-{'_'.join(groups)}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if net != "heuristic" and os.path.exists(net_out(net, args.bench, args.limit)):
        with open(net_out(net, args.bench, args.limit), encoding="utf-8") as f:
            won = json.load(f)["won"]
        one = [won[i] for i in idx]
    else:
        ev = None if net == "heuristic" else bench.load_evaluator(model)
        one = [float(r["won"]) for r in bench.run_specs(specs, ev=ev, search={"limit": bench.LIMIT, "threads": args.threads})]
    t = time.time()
    rows = depth_paired.run_guarded(specs, {"limit": bench.LIMIT, **ladder.TWO_TURN}, -1.0, model, args.threads,
                                    out + ".partial.jsonl", content=b["pack"])
    print(f"two-turn: {time.time() - t:.0f}s", flush=True)
    two = [float(r["won"]) for r in rows]
    sub = [fights[i] for i in idx]
    gain = {}  # cell -> set -> [two - one]
    for f, o, w in zip(sub, one, two):
        gain.setdefault(f["cell"], {}).setdefault(f["set"], []).append(w - o)

    def contrast(keep):
        cells = [c for c in gain if keep(next(f for f in sub if f["cell"] == c and f["set"] == "generated"))]
        g = np.array([np.mean(gain[c]["generated"]) for c in cells])
        o = np.array([np.mean(gain[c]["original"]) for c in cells])
        d = g - o
        se = lambda x: float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else None  # noqa: E731
        return {"cells": len(cells), "gen": float(g.mean()), "gen_se": se(g), "orig": float(o.mean()),
                "orig_se": se(o), "contrast": float(d.mean()), "se": se(d)}

    res = {"all": contrast(lambda f: True)}
    for sl, key in DEPTH_SLICES.items():
        res[sl] = {v: contrast(lambda f, v=v, key=key: key(f) == v) for v in sorted({key(f) for f in sub})}
    tot = {k: sum(r[k] for r in rows) for k in ("decisions", "cut", "override")}
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"bench": args.bench, "net": model, "groups": groups, "idx": idx, "one": one, "two": two,
                   "decisions": tot, "read": res}, f, indent=1)
    fmt = lambda r: (f"cells {r['cells']:3d} gen {r['gen']:+.3f} orig {r['orig']:+.3f} "  # noqa: E731
                     f"contrast {r['contrast']:+.3f} (se {r['se'] if r['se'] is None else round(r['se'], 3)})")
    print(f"{out}: {tot}\n  all {fmt(res['all'])}")
    for sl in DEPTH_SLICES:
        for v, r in res[sl].items():
            print(f"  {sl:9s} {str(v)[:44]:44s} {fmt(r)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("build", "read", "play", "arms", "burst", "depth"))
    ap.add_argument("--groups", default="elite,boss", help="depth: fight groups")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--champion", default=CHAMPION)
    ap.add_argument("--limit", type=int, default=0, help="first N cells only (smoke)")
    ap.add_argument("--out", default=None, help="read: default results/gen_powers/first-check.json")
    ap.add_argument("--seeds", type=int, default=SEEDS, help="build: fights per cell")
    ap.add_argument("--bench", default=BENCH)
    ap.add_argument("--copies", type=int, default=1, help="build: copies of the swapped card per deck")
    ap.add_argument("--first", type=int, default=0, help="build: first fight index per cell (fresh fights)")
    ap.add_argument("--pick-seed", type=int, default=PICK_SEED, help="build: seed for the swapped kind and card")
    ap.add_argument("--nets", nargs="+", default=[], help="play: run dirs or model.pt files")
    ap.add_argument("--control", default="lean-thr", help="arms: control run name")
    ap.add_argument("--arms", nargs="+", default=[], help="arms: arm run names; burst: burst run names")
    args = ap.parse_args()
    if args.cmd == "read" and args.out is None:
        args.out = "results/gen_powers/first-check.json"
    if args.cmd == "build":
        build(args.seeds, args.bench, args.copies, args.first, args.pick_seed)
    else:
        {"read": read, "play": play, "arms": arms, "burst": burst, "depth": depth}[args.cmd](args)


if __name__ == "__main__":
    main()
