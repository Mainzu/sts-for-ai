"""Paired depth test (Next 4): one-turn search vs two-turn search on the same
tight2 fights, heuristic evaluator (or `--evaluator`, a net), reported by fight type, plus how often
the two-turn tree hits its node cap.

`--policy` picks the second arm: `two` (plain two-turn search, in Rust);
`fallback` (two-turn, but one-turn's choice wherever the two-turn tree
cut); `guard` (fallback, and one-turn's choice kept unless two-turn values
another option above it by more than `--margin`); `topk` (fallback, but
two-turn may only pick among one-turn's `--top-k` best options). The
guarded arms play in Python, one process per thread, and count `outside`:
decisions where two-turn's own best option lies outside one-turn's top
`--top-k` (where `topk` and `fallback` can differ).

    python scripts/analysis/depth_paired.py --per-cell 8 --threads 6 --out results/depth/paired.json

Fights: the first `--per-cell` specs of every cell in the chosen half and
groups. Every arm plays the same fights (paired). The cut probe replays
`--probe` fights with one-turn search and runs the two-turn search on every
`--probe-every`-th decision, recording nodes and cuts.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import action_text  # noqa: E402
import bench  # noqa: E402
import sts  # noqa: E402


def fights(half, groups, per_cell, encounters=None, bench_set="tight2"):
    d = json.load(open(f"data/bench/{bench_set}.json", encoding="utf-8"))["halves"][half]
    taken = {}
    out = []
    for s in d:
        if s["group"] in groups and (not encounters or s["encounter"] in encounters)                 and taken.get(s["cell"], 0) < per_cell:
            taken[s["cell"]] = taken.get(s["cell"], 0) + 1
            out.append(s)
    return out


def probe(specs, two, every, ev):
    rows = []
    for s in specs:
        c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"],
                       ascension=s.get("ascension", 0))
        k = 0
        while not c.is_over() and c.turn() <= TURN_LIMIT:
            if k % every == 0:
                t = time.time()
                r = sts.search(c, ev.evaluator, features=ev.features, **two)
                rows.append({"nodes": r["nodes"], "cuts": r["cuts"], "s": time.time() - t})
            c.step(sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)["action"])
            k += 1
    return rows


TURN_LIMIT = sts.PLAY_TURN_LIMIT  # as play's turn limit: a combat still running is a loss
_EV = {}  # per worker process


def guarded_fight(job):
    """One fight under the fallback / guard / topk policy: {won, score, turns,
    decisions, cut, override, outside, hp_start, hp_end, nodes} (nodes: every
    search's tree nodes summed; cut: decisions that fell back on a
    cut; override: decisions where two-turn's choice replaced one-turn's;
    outside: uncut decisions whose two-turn best is outside one-turn's top
    `top_k`). `top_k` 0 lets two-turn pick any option. `seed_per_turn`: the
    two-turn sample seed is the combat turn's, not the decision's, so every
    search of a turn re-samples the same luck (docs/specs/line-seed.md).
    `step_line` (an optional 8th field): when the two-turn tree had no cut,
    play its whole principal line (`line`) before searching again; each
    stepped action is a decision, the later ones run no one-turn search
    (docs/specs/line-step.md). `record` (an optional 9th field) adds
    `actions`: every action played, in order, as action text
    (docs/specs/two-turn-round.md); the result is otherwise unchanged.
    `scores` (an optional 10th field, with `record`) adds `scores`, one entry
    per played action: for an action that a search chose, {options (each
    option's actions as text), one (one-turn values), two (two-turn values,
    None where the tree cut), pick (the option index played)}; for a later
    action of a stepped principal line, {"line": True}
    (docs/specs/explorer-v2.md)."""
    s, two, margin, evaluator, top_k, k_count, seed_per_turn = job[:7]
    step_line = job[7] if len(job) > 7 else False
    record = job[8] if len(job) > 8 else False
    want_scores = record and len(job) > 9 and job[9]
    check_step_line(step_line, seed_per_turn, top_k, margin)
    if evaluator not in _EV:
        _EV[evaluator] = bench.load_evaluator(evaluator)
    ev = _EV[evaluator]
    c = start_combat(s)
    hp_start = c.player_hp()
    n = cut = over = outside = 0
    played, scored = [], []

    def step(a, info=None):
        if record:
            played.append(action_text.encode_action(a))
        if want_scores:
            scored.append(info or {"line": True})
        c.step(a)

    def info(r1, v1, v2, pick):
        if not want_scores:
            return None
        return {"options": [[action_text.encode_action(a) for a in acts] for acts, _ in r1["options"]],
                "one": [float(v) for v in v1], "two": None if v2 is None else [float(v) for v in v2], "pick": int(pick)}

    # `two["rerun"]` = {k, below}: where the tree is uncut and under `below`
    # nodes, search again with k sampled hands and use that tree unless it
    # cut (docs/research/hands-where-small.md, the adaptive rule).
    rerun = two.get("rerun")
    two = {key: v for key, v in two.items() if key != "rerun"}
    reruns = nodes = 0
    while not c.is_over() and c.turn() <= TURN_LIMIT:
        seed = decision_seed(s["seed"], c.turn(), n, seed_per_turn)
        d = decide(c, ev, two, rerun, seed, top_k, k_count, margin)
        r1, r2, v1, v2, pick, b2 = d["r1"], d["r2"], d["v1"], d["v2"], d["pick"], d["b2"]
        reruns += d["reran"]
        nodes += d["nodes"]
        if d["cut"]:
            cut += 1
            n += 1
            step(planned(d, step_line)[0], info(r1, v1, None, pick))
            continue
        outside += d["outside"]
        over += d["over"]
        for m, a in enumerate(planned(d, step_line)):
            if c.is_over():
                break
            step(a, info(r1, v1, v2, pick) if m == 0 else None)
            n += 1
    won = c.is_over() and c.won()
    out = {"won": won, "score": c.score() if c.is_over() else 0.0, "turns": c.turn(),
           "decisions": n, "cut": cut, "override": over, "outside": outside,
           "hp_start": hp_start, "hp_end": c.player_hp(), "nodes": nodes}
    if rerun:
        out["reruns"] = reruns
    if record:
        out["actions"] = played
    if want_scores:
        out["scores"] = scored
    return out


def start_combat(s):
    """A fight's Combat: from its deck and encounter, or (a mutate_monsters.py start,
    docs/specs/genpack-product-depth.md) from `state`, hex state bytes played with
    `seed`, with `powers` ([slot, power, n]) added to monsters after decoding."""
    if "state" in s:
        c = sts.Combat.decode(bytes.fromhex(s["state"]), s["seed"])
        for slot, power, n in s.get("powers", []):
            c = c.with_monster_power(slot, power, n)
        return c
    return sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"],
                      ascension=s.get("ascension", 0))


def decision_seed(fight_seed, turn, n, seed_per_turn):
    """The two-turn sample seed of a decision: the fight's seed with the
    combat turn (`seed_per_turn`) or the decision count n."""
    return (fight_seed * 1009 + (turn if seed_per_turn else n)) % 2**64


def decide(c, ev, two, rerun, seed, top_k, k_count, margin):
    """One decision of `guarded_fight`'s policy at `c`: {r1, r2 (the one- and
    two-turn searches), v1, v2 (their root values; v2 None where the tree
    cut), pick (the option index played), b2 (two-turn's choice, after
    `top_k`), cut, outside, over (as guarded_fight counts them), reran, nodes
    (every search's tree nodes)}."""
    r1 = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)
    r2 = sts.search(c, ev.evaluator, features=ev.features, seed=seed, **two)
    reran = False
    nodes = r1["nodes"] + r2["nodes"]
    if rerun and r2["cuts"] == 0 and r2["nodes"] < rerun["below"]:
        reran = True
        r3 = sts.search(c, ev.evaluator, features=ev.features, seed=seed, **{**two, "sample_k": rerun["k"]})
        nodes += r3["nodes"]
        if r3["cuts"] == 0:
            r2 = r3
    v1 = [v for _, v in r1["options"]]
    v2 = [v for _, v in r2["options"]]
    assert len(v1) == len(v2), "one- and two-turn search list different root options"
    # Each search's own pick: the first best option, as np.argmax, unless the
    # evaluator's tie break (`@tb1`, docs/specs/finish-faster-tiebreak.md)
    # chose among exactly equal ones.
    b1, b2 = picked(r1), picked(r2)
    top = np.argsort(-np.array(v1), kind="stable")
    out = {"r1": r1, "r2": r2, "v1": v1, "v2": None, "pick": b1, "b2": b2, "cut": r2["cuts"] > 0, "outside": False,
           "over": False, "reran": reran, "nodes": nodes}
    if out["cut"]:
        return out
    out["v2"], out["outside"] = v2, b2 not in top[:k_count]
    if top_k:
        b2 = max(top[:top_k], key=lambda i: v2[i])
    out["b2"] = b2
    if b2 != b1 and v2[b2] - v2[b1] > margin:
        out["pick"], out["over"] = b2, True
    return out


def planned(d, step_line):
    """The actions `guarded_fight` plays after decision `d` (`decide`'s): the
    one-turn pick's first action where the two-turn tree cut; with
    `step_line`, the tree's whole principal line when two-turn's choice is the
    pick (line[0] is that option's first action; at margin 0 a tie keeps
    one-turn's choice, pick != b2, and plays the single step: spec-reviewer
    must-fix); else the pick's first action. The real-game bridge plays the
    same (docs/specs/real-game-bridge.md)."""
    if not d["cut"] and step_line and d["pick"] == d["b2"]:
        return list(d["r2"]["line"])
    return [d["r1"]["options"][d["pick"]][0][0]]


def picked(r):
    """The index of the root option holding search result `r`'s action."""
    return next(i for i, (acts, _) in enumerate(r["options"]) if r["action"] in acts)


def _load_content(content):
    """A pack each worker loads: a config's content (selfplay.load_content), or a list
    of content-pack JSON texts (mutate_monsters.py's generated and fickle packs)."""
    if isinstance(content, list):
        for text in content:
            sts.load_content(text)
        return
    import selfplay
    selfplay.load_content(content)


def check_step_line(step_line, seed_per_turn, top_k, margin):
    """`step_line` plays the tree's own best path, so it needs the per-turn
    seed (that is what makes it the committed-line player) and a pick that
    is that path's first action (no top_k restriction, no margin)."""
    if step_line and (not seed_per_turn or top_k or margin > 0):
        raise ValueError("step_line needs seed_per_turn, top_k 0 and margin <= 0 (docs/specs/line-step.md)")


def row_key(two, margin, evaluator, top_k=0, seed_per_turn=False, step_line=False):
    """The settings key of a partial row; unchanged for the default options,
    so older partial files still match."""
    return json.dumps([two, margin, evaluator] + ([top_k] if top_k else []) + (["turn"] if seed_per_turn else [])
                      + (["step"] if step_line else []), sort_keys=True)


def run_guarded(specs, two, margin, evaluator, threads, partial=None, top_k=0, k_count=3, content=None,
                seed_per_turn=False, step_line=False, record=False):
    """Guarded fights' results in spec order. With `partial` (a path), each
    fight's result is appended there as a line when it ends, and fights
    with a line for the same settings there already aren't played again.
    `content`: a pack each worker loads first (fights with generated cards);
    `seed_per_turn`, `step_line`, `record`: see `guarded_fight`."""
    check_step_line(step_line, seed_per_turn, top_k, margin)
    key = row_key(two, margin, evaluator, top_k, seed_per_turn, step_line)
    done = {}
    if partial and os.path.exists(partial):
        with open(partial, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:  # cut short when the run stopped
                    continue
                if row["key"] == key and row["i"] < len(specs) and row["spec"] == specs[row["i"]]:
                    done[row["i"]] = row["r"]
    todo = [i for i in range(len(specs)) if i not in done]
    f = None
    if partial and todo:
        f = open(partial, "a", encoding="utf-8")
        if f.tell():
            f.write("\n")  # past a line cut short (a blank line reads as cut short too)
    try:
        # not multiprocessing.Pool: a worker that dies (out of memory at a big node cap) hangs it
        init = {"initializer": _load_content, "initargs": (content,)} if content else {}
        with ProcessPoolExecutor(threads, **init) as pool:
            futures = {pool.submit(guarded_fight, (specs[i], two, margin, evaluator, top_k, k_count, seed_per_turn,
                                                   step_line, record)): i
                       for i in todo}
            for fut in as_completed(futures):
                i = futures[fut]
                done[i] = fut.result()
                if f:
                    f.write(json.dumps({"key": key, "i": i, "spec": specs[i], "r": done[i]}) + "\n")
                    f.flush()
    finally:
        if f:
            f.close()
    return [done[i] for i in range(len(specs))]


def paired(a, b):
    d = np.array(b, float) - np.array(a, float)
    return {"n": len(d), "a": float(np.mean(a)), "b": float(np.mean(b)), "diff": float(d.mean()),
            "se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--half", default="held_out")
    ap.add_argument("--groups", default="elite,boss")
    ap.add_argument("--bench", default="tight2", help="bench set in data/bench (tight_bosses for Hexaghost / Guardian)")
    ap.add_argument("--encounters", default="", help="comma list; default every encounter in the groups")
    ap.add_argument("--per-cell", type=int, default=8)
    ap.add_argument("--sample-k", type=int, default=4)
    ap.add_argument("--max-nodes", type=int, default=50_000)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--probe", type=int, default=10)
    ap.add_argument("--probe-every", type=int, default=3)
    ap.add_argument("--limit-fights", type=int, default=0, help="first N fights only (pilot)")
    ap.add_argument("--evaluator", default="heuristic", help="'heuristic' or a net's .pt path")
    ap.add_argument("--policy", default="two", choices=["two", "fallback", "guard", "topk"])
    ap.add_argument("--top-k", type=int, default=3, help="topk: options two-turn may pick from; all guarded arms count `outside` with it")
    ap.add_argument("--margin", type=float, default=0.0, help="guard: two-turn must beat one-turn's choice by more")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)  # the guarded arm saves fights beside it

    groups = args.groups.split(",")
    specs = fights(args.half, groups, args.per_cell, [e for e in args.encounters.split(",") if e], args.bench)
    groups = [g for g in groups if any(s["group"] == g for s in specs)]
    if args.limit_fights:
        specs = specs[:args.limit_fights]
    one = {"limit": bench.LIMIT, "threads": args.threads}
    two = {"limit": bench.LIMIT, "turns": 2, "sample_k": args.sample_k, "max_nodes": args.max_nodes}
    if not specs:
        sys.exit(f"no fights match {args.bench} {args.half} {args.groups} {args.encounters}")
    print(f"{len(specs)} fights ({args.half}, {args.groups}); two-turn {two}", flush=True)

    ev = bench.load_evaluator(args.evaluator)
    t = time.time()
    cut_rows = probe(specs[::max(1, len(specs) // max(1, args.probe))][:args.probe], two, args.probe_every, ev)
    cut = {"decisions": len(cut_rows), "cut_share": float(np.mean([r["cuts"] > 0 for r in cut_rows])),
           "mean_nodes": float(np.mean([r["nodes"] for r in cut_rows])),
           "mean_s": float(np.mean([r["s"] for r in cut_rows]))}
    print(f"cut probe: {cut} ({time.time() - t:.0f}s)", flush=True)

    res = {}
    for name, srch in (("one", one), ("two", {**two, "threads": args.threads})):
        t = time.time()
        if name == "two" and args.policy != "two":
            margin = args.margin if args.policy == "guard" else -1.0  # fallback: two-turn's pick unless cut
            res[name] = run_guarded(specs, two, margin, args.evaluator, args.threads, args.out + ".partial.jsonl",
                                    args.top_k if args.policy == "topk" else 0, args.top_k)
            tot = {k: sum(r[k] for r in res[name]) for k in ("decisions", "cut", "override", "outside")}
            print(f"{args.policy}: {tot}", flush=True)
        else:
            res[name] = bench.run_specs(specs, ev=None if args.evaluator == "heuristic" else ev, search=srch)
        print(f"{name}: {time.time() - t:.0f}s, won {sum(r['won'] for r in res[name])}/{len(specs)}", flush=True)

    summary = {}
    for g in groups + ["all"]:
        idx = [i for i, s in enumerate(specs) if g == "all" or s["group"] == g]
        summary[g] = {k: paired([res["one"][i][k] for i in idx], [res["two"][i][k] for i in idx])
                      for k in ("won", "score")}
    by_enc = {}
    for i, s in enumerate(specs):
        by_enc.setdefault(s["encounter"], []).append(i)
    summary["by_encounter"] = {e: paired([res["one"][i]["won"] for i in idx], [res["two"][i]["won"] for i in idx])
                               for e, idx in sorted(by_enc.items())}
    for g in groups + ["all"]:
        w = summary[g]["won"]
        print(f"{g}: one {w['a']:.3f} two {w['b']:.3f} diff {w['diff']:+.3f} (se {w['se']:.3f}, n {w['n']})")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"args": vars(args), "two": two, "cut_probe": cut, "summary": summary,
                   "fights": [{"cell": s["cell"], "group": s["group"], "encounter": s["encounter"], "seed": s["seed"],
                               "one": {k: res["one"][i][k] for k in ("won", "score", "turns")},
                               "two": {k: res["two"][i][k] for k in ("won", "score", "turns", "decisions", "cut", "override", "outside")
                                       if k in res["two"][i]}}
                              for i, s in enumerate(specs)]}, f, indent=1)
    if os.path.exists(args.out + ".partial.jsonl"):
        os.remove(args.out + ".partial.jsonl")


if __name__ == "__main__":
    main()
