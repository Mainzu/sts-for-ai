"""Depth probe (docs/specs/depth-probe.md): the headline control's decisive
fights (floor-9 elites that lost 15+ HP, bosses entered at 50-69 HP; the other
floor-9 elites, or all of them, as an outcome-blind check) replayed by the two-turn product (`two`, should reproduce the file), by the
same guarded player three turns deep (`three`) and by the rollout player
(`rollout`); `read` pairs two files per fight.

    python scripts/analysis/depth_probe.py play --kind elite --arm three --limit 40 --threads 3 --out results/depth_probe/three-elite.json
    python scripts/analysis/depth_probe.py read results/depth_probe/two-elite.json results/depth_probe/three-elite.json
    python scripts/analysis/depth_probe.py read results/depth_probe/three-elite.json   # against the control's own columns
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import gauntlet  # noqa: E402

FILE = "results/gauntlet/net1029-hpe0.01-two-line-step-starter-simboss-a.json"
PLAYER = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01"
ELITE_FLOOR, BOSS_FLOOR = 8, len(gauntlet.SHAPE) - 1
ELITE_LOST, BOSS_BAND = 15, (50, 69)
KINDS = ("elite", "elite-rest", "elite-all", "boss", "all")
REFUSE = ("remove", "rest_choice", "elites", "elite_offers", "mid_rest")


def select(rows, settings, seqs, kind, limit=None, starter=None):
    """[(i, k, spec, row floor)] of the decisive fights of `kind`, in
    sequence order. `starter(character)` gives the start deck when the file
    starts from the starter (default sts.starter_deck)."""
    for key in REFUSE:
        if key in settings:
            raise SystemExit(f"the file's settings hold {key!r}: its decks or fights differ from this rebuild")
    out = []
    for r, k in ((r, k) for r in sorted(rows, key=lambda r: r["i"])
                 for k in (range(len(r["floors"])) if kind == "all" else [BOSS_FLOOR if kind == "boss" else ELITE_FLOOR])):
        if len(r["floors"]) <= k:
            continue
        f = r["floors"][k]
        if kind == "elite" and f["hp_start"] - f["hp_end"] < ELITE_LOST:
            continue
        if kind == "elite-rest" and f["hp_start"] - f["hp_end"] >= ELITE_LOST:
            continue
        if kind == "boss" and not BOSS_BAND[0] <= f["hp_start"] <= BOSS_BAND[1]:
            continue
        s = seqs[r["i"]]
        if settings.get("start") == "starter":
            if starter is None:
                import sts
                starter = sts.starter_deck
            deck = list(starter(s["character"]))
        else:
            deck = list(s["deck"])
        deck += [g["took"] for g in r["floors"][:k] if g.get("took")]
        spec = {"encounter": f["encounter"], "deck": deck, "seed": gauntlet.SEED_BASE + r["i"] * 100 + k,
                "hp": f["hp_start"], "character": s["character"], "group": s["fights"][k]["group"]}
        out.append((r["i"], k, spec, f))
        if limit and len(out) >= limit:
            break
    return out


def row(i, k, spec, f, res):
    keep = ("cut", "decisions", "nodes", "override", "overrides", "playouts", "reruns", "seconds", "turns")
    return {"i": i, "floor": k, "encounter": spec["encounter"], "hp_start": spec["hp"], "won_obs": bool(f["won"]),
            "hp_end_obs": f["hp_end"], "won": bool(res["won"]), "hp_end": int(res["hp_end"]) if res["won"] else 0,
            **{x: res[x] for x in keep if x in res}}


def write(path, settings, fights):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"settings": settings, "fights": fights}, fh, indent=1)
    os.replace(tmp, path)


def play_cmd(a):
    with open(a.file, encoding="utf-8") as fh:
        d = json.load(fh)
    rows = d["sequences"]
    seqs = {s["i"]: s for s in gauntlet.sequences(max(r["i"] for r in rows) + 1)}
    picks = select(rows, d["settings"], seqs, a.kind, a.limit)
    specs = [p[2] for p in picks]
    settings = {"file": a.file, "kind": a.kind, "arm": a.arm, "limit": a.limit, "player": a.player}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    if a.arm == "rollout":
        import bench
        import rollout_probe
        settings.update(n=a.n, seed=a.seed)
        done = {}
        if os.path.exists(a.out):
            with open(a.out, encoding="utf-8") as fh:
                old = json.load(fh)
            if old["settings"] == settings:
                done = {(r["i"], r["floor"]): r for r in old["fights"]}
        ev = bench.load_evaluator(a.player)
        fights = []
        for i, k, spec, f in picks:
            if (i, k) not in done:
                done[(i, k)] = row(i, k, spec, f, rollout_probe.play_rollout(spec, ev, a.n, a.threads, a.seed))
                print(f"{len(done)} / {len(picks)}: sequence {i} {spec['encounter']} won {done[(i, k)]['won']}",
                      flush=True)
            fights.append(done[(i, k)])
            write(a.out, settings, fights)
        return
    import bench
    import depth_paired
    turns = 2 if a.arm == "two" else 3
    max_nodes = 400_000 if a.arm == "two" else a.max_nodes
    settings.update(turns=turns, max_nodes=max_nodes, sample_k=a.sample_k)
    two = {"limit": bench.LIMIT, "turns": turns, "sample_k": a.sample_k, "max_nodes": max_nodes}
    if a.rerun_k:
        if a.arm != "two":
            raise SystemExit("--rerun-k goes with --arm two")
        two["rerun"] = {"k": a.rerun_k, "below": a.rerun_below}
        settings.update(rerun_k=a.rerun_k, rerun_below=a.rerun_below)
    t0 = time.perf_counter()
    res = depth_paired.run_guarded(specs, two, -1.0, a.player, a.threads, partial=a.out + ".partial",
                                   seed_per_turn=True, step_line=True)
    settings["seconds"] = round(time.perf_counter() - t0, 1)
    write(a.out, settings, [row(i, k, spec, f, r) for (i, k, spec, f), r in zip(picks, res)])


def lost(r):
    return r["hp_start"] - r["hp_end"]


def observed(a):
    """A probe file's control columns as a file of their own (the two-turn
    product's play, which the `two` arm reproduces)."""
    return {"fights": [{**r, "won": r["won_obs"], "hp_end": r["hp_end_obs"], "decisions": 0, "cut": 0}
                       for r in a["fights"]]}


def read(a, b):
    """Paired read of two probe files: {n, hp_lost (b - a), se, wins, se, cut
    shares, reproduced (a's and b's fights matching the control)}."""
    ra = {(r["i"], r["floor"]): r for r in a["fights"]}
    rb = {(r["i"], r["floor"]): r for r in b["fights"]}
    keys = sorted(set(ra) & set(rb))
    dl = np.array([lost(rb[x]) - lost(ra[x]) for x in keys], float)
    dw = np.array([float(rb[x]["won"]) - float(ra[x]["won"]) for x in keys])
    se = (lambda v: float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else float("nan"))

    def cut(rs):
        dec = sum(r.get("decisions", 0) for r in rs)
        return sum(r.get("cut", 0) for r in rs) / dec if dec else None

    def repro(rs):
        return sum(r["won"] == r["won_obs"] and r["hp_end"] == r["hp_end_obs"] for r in rs)

    def cost(x):  # search nodes and turns, a and b, overall and by fight type (gauntlet.SHAPE)
        if not all("nodes" in ra[k] and "nodes" in rb[k] for k in x):
            return None
        na, nb = sum(ra[k]["nodes"] for k in x), sum(rb[k]["nodes"] for k in x)
        return {"n": len(x), "nodes_a": na, "nodes_b": nb, "nodes_cut": 1 - nb / na if na else None,
                "turns_a": sum(ra[k]["turns"] for k in x), "turns_b": sum(rb[k]["turns"] for k in x),
                "hp_lost": float(np.mean([lost(rb[k]) - lost(ra[k]) for k in x])) if x else None}

    by_type = {t: cost([k for k in keys if gauntlet.SHAPE[k[1]] == t]) for t in dict.fromkeys(gauntlet.SHAPE)}
    return {"n": len(keys), "cost": cost(keys), "cost_by_type": by_type,
            "hp_lost": float(dl.mean()) if len(keys) else None, "hp_lost_se": se(dl),
            "wins": float(dw.mean()) if len(keys) else None, "wins_se": se(dw),
            "cut_a": cut([ra[x] for x in keys]), "cut_b": cut([rb[x] for x in keys]),
            "reproduced_a": repro([ra[x] for x in keys]), "reproduced_b": repro([rb[x] for x in keys])}


def load(paths):
    """A probe file, or files joined by `+` merged into one (fights in file
    order; a fight in two files is refused)."""
    fights = []
    for path in paths.split("+"):
        with open(path, encoding="utf-8") as fh:
            fights += json.load(fh)["fights"]
    keys = [(r["i"], r["floor"]) for r in fights]
    if len(set(keys)) != len(keys):
        raise SystemExit(f"{paths}: a fight appears in more than one file")
    return {"fights": fights}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("--file", default=FILE)
    p.add_argument("--kind", choices=KINDS, required=True,
                   help="elite: floor-9 elites the control lost 15+ HP on; elite-rest: the other floor-9 elites; "
                        "elite-all: every floor-9 elite; boss: bosses entered at 50-69 HP; "
                        "all: every floor, sequences in order (--limit counts fights)")
    p.add_argument("--arm", choices=("two", "three", "rollout"), required=True)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--player", default=PLAYER)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--max-nodes", type=int, default=400_000, help="three: the tree's node cap")
    p.add_argument("--sample-k", type=int, default=4, help="two, three: sampled hands per chance node (the product: 4)")
    p.add_argument("--rerun-k", type=int, default=0,
                   help="two: where the tree is uncut and under --rerun-below nodes, search again with this many hands")
    p.add_argument("--rerun-below", type=int, default=25_000)
    p.add_argument("--n", type=int, default=16, help="rollout: rollouts per legal action")
    p.add_argument("--seed", type=int, default=0, help="rollout seed")
    p.add_argument("--out", required=True)
    r = sub.add_parser("read")
    r.add_argument("a", help="a probe file, or several joined by + (their fights merged)")
    r.add_argument("b", nargs="?", help="default: a's control columns stand as a, a as b")
    r.add_argument("--require-save", type=float, default=None,
                   help="exit 1 unless b loses at least this much less HP per fight than a (a queue check)")
    args = ap.parse_args(argv)
    if args.cmd == "play":
        play_cmd(args)
    else:
        a = load(args.a)
        if args.b is None:
            a, b = observed(a), a
        else:
            b = load(args.b)
        out = read(a, b)
        print(json.dumps(out, indent=1))
        if args.require_save is not None and not (out["hp_lost"] is not None and -out["hp_lost"] >= args.require_save):
            raise SystemExit(f"saves {-(out['hp_lost'] or 0):.2f} HP per fight, under {args.require_save}")


if __name__ == "__main__":
    main()
