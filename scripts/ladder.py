"""Champion ladder (docs/specs/champion-ladder.md): one champion, and a
sequential test (SPRT) that plays a candidate against it on fresh paired
tight2 fights until it decides; a pass that holds on the held-out card half
promotes the candidate.

    .venv/Scripts/python scripts/ladder.py test runs/<net>/model.pt --threads 6
    .venv/Scripts/python scripts/ladder.py status

State lives in `results/ladder/`: `champion.json` (missing: the heuristic),
`tests/<id>.json` (one per finished test, every pair included) and
`log.jsonl` (one summary line per test).
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import bench_sets  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "ladder")
LADDER_OFFSET = 5 * 10**15  # tight2's test seeds (2e15 + ...) moved to 7e15 + ...
SEEDS_PER_BLOCK = 5
BLOCKS_PER_TEST = 4  # a block is ~6,130 fights; the cap needs 3 (ladder-v2 spec)
LADDER_SLOTS = 8  # tests rotate over this many first blocks
SEED_SPACING = 100_000  # tight2's cells' first seeds are this far apart
ORDER_SEED = 20261030
BATCH = 500
ALPHA = BETA = 0.05
UPPER = math.log((1 - BETA) / ALPHA)
LOWER = math.log(BETA / (1 - ALPHA))
MIN_FIGHTS = 200
D1 = 0.01
CAP = 16_000
HELD_OUT_FLOOR = -0.005
HEURISTIC = "heuristic"
RUNHP_BLOCK0 = 6000  # every run-HP run's first block (seed offset 30,000), clear of the ladder's: candidates share fights
HP_BANDS = {"hallway": (0.7, 1.0), "elite": (0.4, 1.0), "boss": (0.4, 1.0)}  # start HP, share of max
DEATH_PENALTY = 30
HP_SEED = 20261101
HALVES = ("train", "held_out")
GROUPS = ("hallway", "elite", "boss")


def pool_cells():
    """Every tight2 cell of both halves with its first test seed."""
    sets = bench_sets.load_set("tight2")
    cells = {}
    for h in HALVES:
        for s in sets[h]:
            k = (h, s["cell"])
            if k not in cells or s["seed"] < cells[k]["seed0"]:
                cells[k] = {"half": h, "cell": s["cell"], "group": s["group"], "encounter": s["encounter"],
                            "deck": s["deck"], "hp": s["hp"], "character": s["character"], "seed0": s["seed"]}
    return [cells[k] for k in sorted(cells)]


def block(b, cells=None):
    """Block b's fights in test order: SEEDS_PER_BLOCK fresh seeds per cell,
    shuffled within each stratum (half x fight type), interleaved so every
    prefix keeps each stratum's share within one fight."""
    cells = pool_cells() if cells is None else cells
    if (b + 1) * SEEDS_PER_BLOCK > SEED_SPACING:
        raise ValueError(f"block {b} would reuse the next cell's seeds")
    rng = np.random.default_rng([ORDER_SEED, b])
    strata = {}
    for c in cells:
        for k in range(b * SEEDS_PER_BLOCK, (b + 1) * SEEDS_PER_BLOCK):
            spec = {key: c[key] for key in ("half", "cell", "group", "encounter", "deck", "hp", "character")}
            spec["seed"] = c["seed0"] + LADDER_OFFSET + k
            strata.setdefault((c["half"], c["group"]), []).append(spec)
    keys = sorted(strata)
    for key in keys:
        strata[key] = [strata[key][i] for i in rng.permutation(len(strata[key]))]
    total = sum(len(v) for v in strata.values())
    taken = {key: 0 for key in keys}
    out = []
    for n in range(1, total + 1):
        key = max(keys, key=lambda k: (len(strata[k]) * n / total - taken[k], -keys.index(k)))
        out.append(strata[key][taken[key]])
        taken[key] += 1
    return out


def llr(n, s, q, d1=D1):
    """Normal-form SPRT log-likelihood ratio after n pairs with sum s and sum
    of squares q (as sprt_replay.sprt_paths)."""
    mean = s / n
    var = max(q / n - mean ** 2, 1e-6)
    return n * d1 / var * (mean - d1 / 2)


def decide(ds, d1=D1, cap=CAP, start=(0, 0.0, 0.0)):
    """Steps the SPRT through pair outcomes `ds` from state `start` (n, sum,
    sum of squares). Returns ("pass" | "fail" | None, state); the state
    stops at the deciding pair, or at the cap ("cap")."""
    n, s, q = start
    for d in ds:
        n, s, q = n + 1, s + d, q + d * d
        if n >= MIN_FIGHTS:
            v = llr(n, s, q, d1)
            if v >= UPPER:
                return "pass", (n, s, q)
            if v <= LOWER:
                return "fail", (n, s, q)
        if n >= cap:
            return "cap", (n, s, q)
    return None, (n, s, q)


def final_verdict(verdict, held_out_lead):
    """The SPRT's verdict after the held-out rule: a pass needs counted
    held-out pairs with a lead of at least HELD_OUT_FLOOR."""
    if verdict == "cap":
        return "inconclusive"
    if verdict == "pass" and (held_out_lead is None or held_out_lead < HELD_OUT_FLOOR):
        return "pass-held-out-fail"
    return verdict


def lead_by(pairs, key, value=lambda p: p["cand"] - p["champ"]):
    """{stratum: {n, cells, lead, lo, hi}} of `value` per pair, intervals
    over cells."""
    out = {}
    for p in pairs:
        out.setdefault(key(p), {}).setdefault((p["half"], p["cell"]), []).append(value(p))
    res = {}
    for k, cells in sorted(out.items()):
        m = np.array([np.mean(v) for v in cells.values()])
        d = [x for v in cells.values() for x in v]
        half = 1.96 * m.std(ddof=1) / math.sqrt(len(m)) if len(m) > 1 else float("nan")
        res[k] = {"n": len(d), "cells": len(m), "lead": float(np.mean(d)),
                  "lo": float(np.mean(d) - half), "hi": float(np.mean(d) + half)}
    return res


_EVALUATORS = {}


def play_bench(specs, player, threads):
    """{won, hp_start, hp_end} of `player` (a net path or "heuristic") on
    specs, one-turn search with the agents' settings."""
    import bench
    if player != HEURISTIC and player not in _EVALUATORS:
        _EVALUATORS[player] = bench.load_evaluator(player)
    ev = _EVALUATORS.get(player)
    return [{"won": bool(r["won"]), "hp_start": r["hp_start"], "hp_end": r["hp_end"]}
            for r in bench.run_specs(specs, ev=ev, search={"limit": bench.LIMIT, "threads": threads})]


TWO_TURN = {"turns": 2, "sample_k": 4, "max_nodes": 400_000}  # the fallback two-turn player (decisions "Two-turn player: fallback")


def play_two_turn(specs, player, threads, partial=None, seed_per_turn=False, step_line=False, content=None):
    """{won, hp_start, hp_end} of net `player` under the fallback two-turn
    player (depth_paired's guarded fight, one-turn's choice where the tree
    cut), one process per thread; `partial` keeps finished fights for a rerun;
    `seed_per_turn`: one sample seed per combat turn (docs/specs/line-seed.md);
    `step_line`: play each uncut tree's principal line (docs/specs/line-step.md);
    `content`: a pack file each worker loads first (docs/specs/gauntlet-pack-offers.md)."""
    import bench
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "analysis"))
    import depth_paired
    res = depth_paired.run_guarded(specs, {"limit": bench.LIMIT, **TWO_TURN}, -1.0, player, threads, partial,
                                   seed_per_turn=seed_per_turn, step_line=step_line, content=content)
    return [{"won": bool(r["won"]), "hp_start": r["hp_start"], "hp_end": r["hp_end"]} for r in res]


def as_result(x):
    """A play result as {won, hp_start, hp_end}; a bare win bit (test fakes)
    leaves the HP fields None."""
    return x if isinstance(x, dict) else {"won": bool(x), "hp_start": None, "hp_end": None}


def player_files(p):
    """The net files of a player spec: `a.pt`, `a.pt+b.pt` (an ensemble), with
    an optional `@hpb<c>` setting after them (bench.split_player)."""
    base = p.partition("@")[0]
    return [base] if os.path.exists(base) else base.split("+")


def player_key(p):
    """A player's identity for caches: its files' hashes plus any setting."""
    return [file_sha(f) for f in player_files(p)] + ([p.partition("@")[2]] if "@" in p else [])


def file_sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def cache_path(root, player, mode="win"):
    """The champion cache file of `player` (ladder-v2): keyed by the player's
    file hashes, the loaded sts module's hash, the search limit and the mode,
    so a rebuilt engine or a retrained net misses."""
    import bench
    import sts
    ident = HEURISTIC if player == HEURISTIC else player_key(player)
    pyd = [os.path.join(os.path.dirname(sts.__file__), n) for n in sorted(os.listdir(os.path.dirname(sts.__file__)))
           if n.endswith(".pyd") or n.endswith(".so")]
    key = hashlib.sha256(json.dumps([ident, [file_sha(p) for p in pyd], bench.LIMIT, mode]).encode()).hexdigest()
    return os.path.join(root, "cache", key[:16] + ".json")


def cached_play(play, specs, player, path):
    """`play(specs, player)` with results by seed kept in the file `path`:
    only seeds missing from it are played, then the file is rewritten."""
    cache = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                cache = json.load(f)["results"]
        except (ValueError, KeyError):  # a torn file: replay what's missing
            cache = {}
    todo = [s for s in specs if str(s["seed"]) not in cache]
    if todo:
        for s, r in zip(todo, play(todo, player)):
            r = as_result(r)
            cache[str(s["seed"])] = [r["won"], r["hp_start"], r["hp_end"]]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"  # one per process: two tests may write at once
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"player": player, "results": cache}, f)
        os.replace(tmp, path)
    return [dict(zip(("won", "hp_start", "hp_end"), cache[str(s["seed"])])) for s in specs]


def champion(root=ROOT):
    p = os.path.join(root, "champion.json")
    if not os.path.exists(p):
        return {"player": HEURISTIC, "since": None, "test": None}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def same_player(a, b):
    norm = lambda p: p if p == HEURISTIC else (os.path.normcase(os.path.abspath(p.partition("@")[0])), p.partition("@")[2])  # noqa: E731
    return norm(a) == norm(b)


def start_block(tid):
    """A test's first block (ladder-v2): consecutive tests use different
    draws, rotating over LADDER_SLOTS slots so the champion's cached results
    are reused."""
    return (int(tid) - 1) % LADDER_SLOTS * BLOCKS_PER_TEST


def reserve_id(folder):
    """The next test id in `folder`, held by an exclusive `<id>.pending`
    file until the test writes `<id>.json` (a crash leaves the id unused)."""
    os.makedirs(folder, exist_ok=True)
    while True:
        ids = [int(n.split(".")[0]) for n in os.listdir(folder) if n.split(".")[0].isdigit()]
        tid = f"{max(ids, default=0) + 1:04d}"
        try:
            open(os.path.join(folder, tid + ".pending"), "x").close()
            return tid
        except FileExistsError:
            continue


def run_test(cand, champ=None, d1=D1, cap=CAP, threads=6, root=ROOT, promote=True, play=None, cells=None, log=print,
             first_block=None, fixed_n=0):
    """Plays `cand` against the champion (or `champ`) until the SPRT decides
    or the cap, then on to `fixed_n` pairs if more (not counted by the SPRT;
    their lead is the record's `fixed`); writes the test file and log line;
    promotes on a pass whose held-out lead clears HELD_OUT_FLOOR. Returns
    the test record."""
    champ = champion(root)["player"] if champ is None else champ
    if same_player(cand, champ):
        raise ValueError(f"candidate is the champion: {cand}")
    for p in (cand, champ):
        for part in ([] if p == HEURISTIC else player_files(p)):  # a.pt+b.pt: an ensemble
            if not os.path.exists(part):
                raise FileNotFoundError(part)
    play = play or (lambda specs, player: play_bench(specs, player, threads))
    cells = pool_cells() if cells is None else cells
    cpath = cache_path(root, champ)
    tests = os.path.join(root, "tests")
    tid = reserve_id(tests)
    b = b0 = start_block(tid) if first_block is None else first_block
    t0 = time.time()
    pairs, state, verdict, path = [], (0, 0.0, 0.0), None, []
    while verdict is None or len(pairs) < fixed_n:
        fights = block(b, cells)
        for i in range(0, len(fights), BATCH):
            batch = fights[i:i + BATCH]
            if verdict is not None:  # the fixed-n continuation: played, not counted
                batch = batch[:fixed_n - len(pairs)]
            wc = [as_result(r)["won"] for r in play(batch, cand)]
            wh = [r["won"] for r in cached_play(play, batch, champ, cpath)]
            ds = [int(a) - int(h) for a, h in zip(wc, wh)]
            n0 = state[0]
            if verdict is None:
                verdict, state = decide(ds, d1, cap, state)
            for j, (s, a, h) in enumerate(zip(batch, wc, wh)):
                pairs.append({"half": s["half"], "cell": s["cell"], "group": s["group"], "encounter": s["encounter"],
                              "seed": s["seed"], "cand": int(a), "champ": int(h), "counted": n0 + j < state[0]})
            for n in range((n0 // 100 + 1) * 100, state[0] + 1, 100):
                c = [p["cand"] - p["champ"] for p in pairs[:n]]
                path.append([n, llr(n, sum(c), sum(x * x for x in c), d1)])
            log(f"  {state[0]} pairs, lead {state[1] / state[0]:+.4f}, llr {llr(*state, d1):+.2f}, "
                f"{len(pairs)} played ({time.time() - t0:.0f}s)")
            if verdict is not None and len(pairs) >= fixed_n:
                break
        b += 1
    counted = [p for p in pairs if p["counted"]]
    halves = lead_by(counted, lambda p: p["half"])
    verdict = final_verdict(verdict, halves["held_out"]["lead"] if "held_out" in halves else None)
    promoted = verdict == "pass" and promote
    n, s, q = state
    rec = {"id": tid, "candidate": cand, "champion": champ, "verdict": verdict, "promoted": promoted,
           "pairs": n, "lead": s / n, "llr": llr(n, s, q, d1), "d1": d1, "cap": cap, "first_block": b0, "seconds": round(time.time() - t0),
           "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "by_half": halves, "by_type": lead_by(counted, lambda p: p["group"]),
           "by_half_type": {f"{h} {g}": v for (h, g), v in lead_by(counted, lambda p: (p["half"], p["group"])).items()}}
    if fixed_n:
        first = pairs[:fixed_n]
        rec["fixed"] = {"n": len(first), "lead": float(np.mean([p["cand"] - p["champ"] for p in first])),
                        "by_half": lead_by(first, lambda p: p["half"]), "by_type": lead_by(first, lambda p: p["group"])}
    with open(os.path.join(tests, tid + ".json"), "w", encoding="utf-8") as f:
        json.dump({**rec, "llr_path": path, "pairs_played": pairs}, f, indent=1)
    os.remove(os.path.join(tests, tid + ".pending"))
    with open(os.path.join(root, "log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({k: rec[k] for k in ("id", "when", "candidate", "champion", "verdict", "promoted",
                                                 "pairs", "lead", "seconds")}) + "\n")
    if promoted:
        with open(os.path.join(root, "champion.json"), "w", encoding="utf-8") as f:
            json.dump({"player": cand, "since": rec["when"], "test": tid}, f, indent=1)
    return rec


def run_hp(spec, max_hp):
    """A fight's run-HP start: uniform in its group's HP_BANDS share of
    `max_hp`, drawn from the fight's seed."""
    lo, hi = HP_BANDS[spec["group"]]
    rng = np.random.default_rng([HP_SEED, spec["seed"]])
    return int(rng.integers(math.ceil(lo * max_hp), int(hi * max_hp) + 1))


def hp_lost(r):
    """HP lost in one fight; a death costs its start HP plus DEATH_PENALTY."""
    return r["hp_start"] - r["hp_end"] if r["won"] else r["hp_start"] + DEATH_PENALTY


def run_runhp(cand, against=HEURISTIC, n_pairs=2000, threads=6, root=ROOT, play=None, cells=None, log=print,
              first_block=None, two_turn=False):
    """Run-HP pool (ladder-v2): `cand` and `against` on the same fresh fights
    at run-like start HP, `n_pairs` pairs, scored by HP lost (pair score =
    against's loss - cand's: positive is the candidate better). No SPRT, no
    promotion. With `two_turn` the candidate (a net) plays two turns deep
    (`play_two_turn`); `against` stays one-turn. Writes runhp/<id>.json and
    runhp/log.jsonl; returns the record."""
    import selfplay
    if same_player(cand, against):
        raise ValueError(f"candidate is the opponent: {cand}")
    for p in (cand, against):
        for part in ([] if p == HEURISTIC else player_files(p)):
            if not os.path.exists(part):
                raise FileNotFoundError(part)
    play = play or (lambda specs, player: play_bench(specs, player, threads))
    play_cand = play
    if two_turn:
        if cand == HEURISTIC:
            raise ValueError("two_turn needs a net candidate")
        partial = os.path.join(root, "runhp", f"two-{hashlib.sha256(json.dumps(player_key(cand)).encode()).hexdigest()[:12] if '@' in cand else file_sha(cand)[:12]}.partial.jsonl")
        play_cand = lambda specs, player: play_two_turn(specs, player, threads, partial)  # noqa: E731
    cells = pool_cells() if cells is None else cells
    max_hp = {ch: selfplay.max_hp(ch) for ch in {c["character"] for c in cells}}
    cpath = cache_path(root, against, mode=["runhp", HP_BANDS, HP_SEED])
    folder = os.path.join(root, "runhp")
    tid = reserve_id(folder)
    b = b0 = RUNHP_BLOCK0 if first_block is None else first_block
    t0 = time.time()
    pairs = []
    while len(pairs) < n_pairs:
        fights = [{**s, "hp": run_hp(s, max_hp[s["character"]])} for s in block(b, cells)]
        for i in range(0, len(fights), BATCH):
            batch = fights[i:i + BATCH][:n_pairs - len(pairs)]
            if not batch:
                break
            rc = [as_result(r) for r in play_cand(batch, cand)]
            ro = cached_play(play, batch, against, cpath)
            for s, c, o in zip(batch, rc, ro):
                pairs.append({"half": s["half"], "cell": s["cell"], "group": s["group"], "encounter": s["encounter"],
                              "seed": s["seed"], "hp": s["hp"], "cand_won": int(c["won"]), "opp_won": int(o["won"]),
                              "cand_lost": hp_lost(c), "opp_lost": hp_lost(o), "score": hp_lost(o) - hp_lost(c)})
            log(f"  {len(pairs)} pairs, score {np.mean([p['score'] for p in pairs]):+.2f} HP "
                f"({time.time() - t0:.0f}s)")
        b += 1
    score, win = (lambda p: p["score"]), (lambda p: p["cand_won"] - p["opp_won"])
    cl, ol = np.array([p["cand_lost"] for p in pairs], float), np.array([p["opp_lost"] for p in pairs], float)
    rec = {"id": tid, "candidate": cand, "against": against, "pairs": len(pairs), "first_block": b0,
           "cand_search": "two-turn fallback " + json.dumps(TWO_TURN) if two_turn else "one-turn",
           "hp_bands": HP_BANDS, "death_penalty": DEATH_PENALTY, "seconds": round(time.time() - t0),
           "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "score": float(np.mean(ol - cl)), "score_sd": float(np.std(ol - cl, ddof=1)),
           "lost_corr": float(np.corrcoef(cl, ol)[0, 1]) if cl.std() > 0 and ol.std() > 0 else None,
           "cand_lost": float(cl.mean()), "opp_lost": float(ol.mean()),
           "cand_win": float(np.mean([p["cand_won"] for p in pairs])),
           "opp_win": float(np.mean([p["opp_won"] for p in pairs])),
           "all": lead_by(pairs, lambda p: "all", score)["all"],
           "by_half": lead_by(pairs, lambda p: p["half"], score),
           "by_type": lead_by(pairs, lambda p: p["group"], score),
           "by_half_type": {f"{h} {g}": v for (h, g), v in lead_by(pairs, lambda p: (p["half"], p["group"]), score).items()},
           "win_by_half": lead_by(pairs, lambda p: p["half"], win)}
    with open(os.path.join(folder, tid + ".json"), "w", encoding="utf-8") as f:
        json.dump({**rec, "pairs_played": pairs}, f, indent=1)
    os.remove(os.path.join(folder, tid + ".pending"))
    with open(os.path.join(folder, "log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({k: rec[k] for k in ("id", "when", "candidate", "against", "pairs", "score",
                                                 "cand_lost", "opp_lost", "cand_win", "opp_win", "seconds")}) + "\n")
    return rec


def report_runhp(rec):
    a = rec["all"]
    lines = [f"run-HP {rec['id']}: {rec['candidate']} ({rec.get('cand_search', 'one-turn')}) vs {rec['against']}, "
             f"{rec['pairs']} pairs: score "
             f"{rec['score']:+.2f} HP [{a['lo']:+.2f}, {a['hi']:+.2f}] (positive: candidate loses less)",
             f"  HP lost: candidate {rec['cand_lost']:.2f}, opponent {rec['opp_lost']:.2f}; win "
             f"{rec['cand_win']:.3f} vs {rec['opp_win']:.3f}; score sd {rec['score_sd']:.2f}, "
             f"lost corr {rec['lost_corr'] if rec['lost_corr'] is None else round(rec['lost_corr'], 3)}"]
    for name in ("by_half", "by_type", "by_half_type", "win_by_half"):
        for k, v in rec[name].items():
            label = ("win " if name == "win_by_half" else "") + k
            lines.append(f"  {label:18s} n {v['n']:5d} cells {v['cells']:4d} "
                         f"{v['lead']:+.3f} [{v['lo']:+.3f}, {v['hi']:+.3f}]")
    return "\n".join(lines)


def report(rec):
    lines = [f"test {rec['id']}: {rec['candidate']} vs {rec['champion']}: {rec['verdict']}"
             f"{' (promoted)' if rec['promoted'] else ''}, {rec['pairs']} pairs, lead {rec['lead']:+.4f}"]
    for name in ("by_half", "by_type", "by_half_type"):
        for k, v in rec[name].items():
            lines.append(f"  {k:18s} n {v['n']:5d} cells {v['cells']:4d} lead {v['lead']:+.4f} "
                         f"[{v['lo']:+.4f}, {v['hi']:+.4f}]")
    if "fixed" in rec:
        fx = rec["fixed"]
        lines.append(f"  fixed n {fx['n']}: lead {fx['lead']:+.4f}")
        for name in ("by_half", "by_type"):
            for k, v in fx[name].items():
                lines.append(f"    {k:16s} n {v['n']:5d} cells {v['cells']:4d} lead {v['lead']:+.4f} "
                             f"[{v['lo']:+.4f}, {v['hi']:+.4f}]")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("test")
    t.add_argument("candidate")
    t.add_argument("--champion", default=None, help="default: the ladder's champion")
    t.add_argument("--h1", type=float, default=D1)
    t.add_argument("--cap", type=int, default=CAP)
    t.add_argument("--threads", type=int, default=6)
    t.add_argument("--no-promote", action="store_true")
    t.add_argument("--start-block", type=int, default=None, help="default: from the test's id")
    t.add_argument("--fixed-n", type=int, default=0, help="play on to this many pairs after the SPRT stops")
    t.add_argument("--root", default=ROOT)
    r = sub.add_parser("runhp", help="HP lost at run-like start HP, paired against --against")
    r.add_argument("candidate")
    r.add_argument("--against", default=HEURISTIC)
    r.add_argument("--pairs", type=int, default=2000)
    r.add_argument("--threads", type=int, default=6)
    r.add_argument("--start-block", type=int, default=None, help=f"default: {RUNHP_BLOCK0}, shared by every run")
    r.add_argument("--two-turn", action="store_true", help="the candidate plays the fallback two-turn player")
    r.add_argument("--root", default=ROOT)
    s = sub.add_parser("status")
    s.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    if args.cmd == "runhp":
        print(report_runhp(run_runhp(args.candidate, args.against, args.pairs, args.threads, args.root,
                                     log=lambda m: print(m, flush=True), first_block=args.start_block,
                                     two_turn=args.two_turn)))
    elif args.cmd == "test":
        rec = run_test(args.candidate, args.champion, args.h1, args.cap, args.threads, args.root,
                       promote=not args.no_promote, log=lambda m: print(m, flush=True), first_block=args.start_block, fixed_n=args.fixed_n)
        print(report(rec))
    else:
        c = champion(args.root)
        print(f"champion: {c['player']} (since {c['since']}, test {c['test']})")
        p = os.path.join(args.root, "log.jsonl")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f.readlines()[-10:]:
                    r = json.loads(line)
                    print(f"  {r['id']} {r['when']} {r['candidate']} vs {r['champion']}: {r['verdict']}, "
                          f"{r['pairs']} pairs, lead {r['lead']:+.4f}")


if __name__ == "__main__":
    main()
