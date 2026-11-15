"""Position finder and solved-position database tools (docs/specs/exact-solver.md).

- The finder walks real games back from the end: each decision with at
  least 2 options, from the last one backward, is solved exactly
  (`sts.solve`), and the walk stops at the first unsolvable one. Each game
  gets one `SolveStore` over the shared database, so later decisions on the
  played path come back as hits. Every solved decision becomes a
  `positions` row (its state in `states`) under the walk's source.
- Registry dump: every game (main and branch) of a run's datasets, with the
  run id as source; `--export` also writes `datasets/puzzles-<run>.jsonl`.
  Nothing is written in the registry itself.
- Bench puzzle set (`bench`): search + heuristic plays the tight specs on
  fresh seeds, pass after pass, until each half has PUZZLES_PER_HALF games
  with a puzzle; one puzzle per game (seeded pick) goes into
  data/bench/puzzles.json, exported from the database's `bench` positions
  in the decisions file's row format. Built once; `--rebuild` redoes it.
- `db --stats` prints the database's size, rows per rules version (full and
  trivial), bytes per table and cost spread; `db --evict` applies the size
  cap (other rules versions first, then the cheapest rows), which every run
  also does at its end. `db --compact` moves trivial rows (every line
  loses, or every option tied) that no puzzle points at to value-only rows
  and compacts the file: once per database written before exact-solver
  Amendment 1, by hand, with nothing else using it. `db --repair-costs`
  rebuilds costs the old summing rule broke (above `--max-nodes`, or
  negative) from the rows' children (docs/decisions.md, "Solved-state
  cost"): once per database written before that fix, by hand.

    python scripts/puzzles.py --run <run id> [--export] [--threads N]
    python scripts/puzzles.py bench [--rebuild] [--per-half N]
    python scripts/puzzles.py db --stats | --evict | --compact | --repair-costs
"""

import argparse
import ctypes
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import bench_decisions
import bench_sets
import registry
import sts
import stsnet

ROOT = registry.ROOT
DB_PATH = os.path.join(ROOT, "db", "solved.sqlite")
LIMIT = bench_sets.LIMIT
MAX_NODES = 1_000_000
MIN_NODES = 1_000
MAX_GB = 5
# Threads: one solve at the 1M budget peaks near 0.75 GB (step 7), so the
# default 6 is capped to what fits in free memory minus a margin.
THREADS = 6
THREAD_BYTES = 0.75e9
MEM_MARGIN = 2e9
# Bench puzzle set. Calibration plays cell i on seeds 5,000,000 + i * 100,000
# (at most 1,600 per cell), so 9,000,000 starts cell 40's block: puzzle seeds
# skip its used part and stay in the block's unused rest, disjoint from
# calibration, the tight specs' own seeds (3,000,000+) and the fresh-seed
# check's (50,000,000+). Seed of spec i, half h, pass p: puzzle_seed(p, h, i).
PUZZLE_SEED = 9_000_000
SEED_SKIP = 10_000
PASS_SEEDS = 2_000  # per pass, 1,000 per half (610 / 550 specs)
MAX_PASSES = 45  # keeps every seed under 9,100,000
PUZZLES_PER_HALF = 1_000
PUZZLE_PATH = os.path.join(bench_sets.BENCH, "puzzles.json")
BENCH_SOURCE = "bench"


class _MemStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_bytes():
    st = _MemStatus()
    st.dwLength = ctypes.sizeof(st)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullAvailPhys


def default_threads():
    """THREADS, capped to (free memory - margin) / per-thread peak, at least 1."""
    return max(1, min(THREADS, int((free_bytes() - MEM_MARGIN) // THREAD_BYTES)))


def spec_key(identity):
    """The `positions` row's spec: canonical JSON of the game's identity."""
    return json.dumps(identity, sort_keys=True, separators=(",", ":"))


def _dist(d):
    loss, wins = d
    return {"loss": loss, "wins": [[k, p] for k, p in wins]}


def walk(states, actions, db, source, spec, max_nodes=MAX_NODES, min_nodes=MIN_NODES, distribution=False,
         bounds=False):
    """One game's solved decisions, in step order: from the last decision
    back to the first unsolvable one, skipping decisions with fewer than 2
    options. `states[k]` is the state before `actions[k]`. Each is recorded
    in `db` under `source` / `spec`. Per puzzle: `step`, `actions` (the
    prefix, encoded as `bench_decisions.encode_action`), `options`
    ([[actions], value] or [[actions], value, distribution]), `gap` (best
    minus second best), `horizon` (the last decision's turn minus this
    one's), `nodes`, `hits`. `bounds`: solve with solver bounds
    (docs/specs/solver-bounds.md); a skipped option's value is an upper
    bound, so `gap` is then a lower bound."""
    store = sts.SolveStore(min_nodes=min_nodes, db=db)
    enc = [registry.encode_action(a) for a in actions]
    last_turn = states[-1].turn() if states else 0
    out = []
    for k in range(len(states) - 1, -1, -1):
        c = states[k]
        if len(c.options(LIMIT)) < 2:
            continue
        r = sts.solve(c, max_nodes=max_nodes, distribution=distribution, store=store, bounds=bounds)
        if r is None:
            break
        values = sorted((o[1] for o in r["options"]), reverse=True)
        gap = values[0] - values[1]
        horizon = last_turn - c.turn()
        prefix = "|".join(enc[:k])
        store.add_position(c, source, spec, prefix, k, horizon, gap)
        opts = [[[registry.encode_action(a) for a in o[0]], o[1]] + ([_dist(o[2])] if len(o) > 2 else [])
                for o in r["options"]]
        out.append({"step": k, "actions": prefix, "options": opts, "gap": gap, "horizon": horizon,
                    "nodes": r["nodes"], "hits": r["hits"]})
    out.reverse()
    return out


def record_states(game):
    """(states, actions) of a registry game record; no-death records are refused."""
    if game.get("no_death"):
        raise ValueError("no-death game records can't be solved (their values aren't the real game's)")
    r = registry.replay(game)
    return r["states"], r["actions"]


def find(games, db, source, threads=None, log=None, **kw):
    """`walk` over many games on a thread pool, results in game order (so
    the output doesn't depend on the thread count). `games`: [(identity,
    states, actions)], identity being the game's spec as a JSON-able dict.
    `threads` None: `default_threads()`. `log`: a progress line per game
    walked."""
    from concurrent.futures import as_completed
    from progress import Progress

    def one(g):
        identity, states, actions = g
        return walk(states, actions, db, source, spec_key(identity), **kw)
    p = Progress(f"solve {source}", len(games), log)
    with ThreadPoolExecutor(threads or default_threads()) as pool:
        futures = [pool.submit(one, g) for g in games]
        for _ in as_completed(futures):
            p.update()
    p.close()
    return [f.result() for f in futures]


def play(specs):
    """Search + heuristic (the calibration agent) games on bench specs
    (dicts with encounter, deck, seed, hp, character), recorded."""
    by = {}
    for i, s in enumerate(specs):
        by.setdefault((s["hp"], s["character"]), []).append(i)
    out = [None] * len(specs)
    for (hp, ch), idx in sorted(by.items()):
        res = sts.run("search", [(specs[i]["encounter"], specs[i]["deck"], specs[i]["seed"]) for i in idx],
                      limit=LIMIT, hp=hp, character=ch, record=True, **stsnet.job_threads({}))
        for i, r in zip(idx, res):
            out[i] = r
    return out


def dataset_games(ds, root=ROOT, limit=None):
    """[(identity, states, actions)] for a dataset's games (main and branch)
    in game order, the first `limit` of them (all when None)."""
    out = []
    for i, g in enumerate(registry.iter_games(ds, root)):
        if limit is not None and i >= limit:
            break
        states, actions = record_states(g)
        identity = {"dataset": ds, "game": i, **{k: g[k] for k in ("character", "encounter", "deck", "hp", "seed")}}
        if "branch_at" in g:
            identity.update(branch_at=g["branch_at"], branch_of=g["branch_of"])
        out.append((identity, states, actions))
    return out


def run_games(run_id, root=ROOT):
    """[(identity, states, actions)] for every game of a run's datasets."""
    with open(os.path.join(registry.runs_dir(root), run_id, "run.json"), encoding="utf-8") as f:
        datasets = json.load(f)["datasets"]
    return [g for ds in datasets for g in dataset_games(ds, root)]


def solve_dataset(ds, db, root=ROOT, games=None, **kw):
    """The curriculum's solve step: the first `games` games of dataset `ds`
    walked back into `db` with solver bounds (unless `bounds=False`),
    positions sourced to `ds`. Returns (games walked, puzzles)."""
    kw.setdefault("bounds", True)
    gs = dataset_games(ds, root, games)
    found = find(gs, db, ds, **kw)
    return len(gs), sum(len(p) for p in found)


def dump_run(run_id, db_path=DB_PATH, root=ROOT, export=False, max_gb=MAX_GB, **kw):
    """Every solved decision of a run's games into the database under the run
    id; with `export`, also as `datasets/puzzles-<run>.jsonl` (one puzzle per
    line, with its game's identity). Returns the number of puzzles."""
    games = run_games(run_id, root)
    db = sts.SolvedDb(db_path, max_gb=max_gb)
    found = find(games, db, run_id, **kw)
    db.evict()
    if export:
        path = os.path.join(registry.datasets_dir(root), f"puzzles-{run_id}.jsonl")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for (identity, _, _), puzzles in zip(games, found):
                for p in puzzles:
                    f.write(json.dumps({**identity, **p}, sort_keys=True) + "\n")
    return sum(len(p) for p in found)


def puzzle_seed(p, h, i):
    assert p < MAX_PASSES and i < PASS_SEEDS // 2
    return PUZZLE_SEED + SEED_SKIP + p * PASS_SEEDS + h * (PASS_SEEDS // 2) + i


def bench_identity(half, i, s):
    """A bench game's identity: the decisions file's spec fields plus its half."""
    return {"half": half, "spec": i, **{k: s[k] for k in ("encounter", "deck", "hp", "seed", "character", "family",
                                                         "group")}}


def build_set(db, out=PUZZLE_PATH, per_half=PUZZLES_PER_HALF, tight=None, threads=None, max_nodes=MAX_NODES,
              min_nodes=MIN_NODES):
    """Plays seed passes over each half's tight specs until it has `per_half`
    games with at least one puzzle (games in spec order, pass by pass), picks
    one puzzle per game uniformly (seeded), and writes them to `out` from the
    database's `bench` positions. `tight`: {half: specs}, default the bench's
    tight set. Returns {half: passes played}."""
    tight = tight if tight is not None else bench_sets.load_set("tight")
    rows_at_start = db.rows
    picked, passes = {}, {}
    for h, (half, specs) in enumerate(tight.items()):
        got, p = [], 0
        while len(got) < per_half:
            if p >= MAX_PASSES:
                raise RuntimeError(f"{half}: {len(got)} games with a puzzle after {p} passes")
            fresh = [{**s, "seed": puzzle_seed(p, h, i)} for i, s in enumerate(specs)]
            games = [(bench_identity(half, i, s), r["states"], r["actions"])
                     for i, (s, r) in enumerate(zip(fresh, play(fresh)))]
            found = find(games, db, BENCH_SOURCE, threads=threads, max_nodes=max_nodes, min_nodes=min_nodes,
                         distribution=True)
            rng = np.random.default_rng(PUZZLE_SEED + 1_000 * h + p)
            for (identity, _, _), ps in zip(games, found):
                if ps and len(got) < per_half:
                    got.append((identity, ps[int(rng.integers(len(ps)))]))
            p += 1
        picked[half], passes[half] = got, p
    by_key = {(r["spec"], r["step"]): r for r in db.positions(BENCH_SOURCE)}
    halves = {}
    for half, got in picked.items():
        halves[half] = []
        for identity, puzzle in got:
            r = by_key[(spec_key(identity), puzzle["step"])]
            options = [[[bench_decisions.encode_action(a) for a in o[0]], o[1]] + ([_dist(o[2])] if len(o) > 2 else [])
                       for o in r["options"]]
            assert [o[:2] for o in options] == [o[:2] for o in puzzle["options"]], "database row disagrees with solve"
            row = {k: v for k, v in identity.items() if k != "half"}
            row.update(step=r["step"], actions=r["prefix"], options=options, gap=r["gap"], horizon=r["horizon"])
            halves[half].append(row)
    head = {"version": bench_sets.VERSION, "set": "tight", "agent": "search", "evaluator": "heuristic",
            "limit": LIMIT, "per_half": per_half, "seed": PUZZLE_SEED, "seed_skip": SEED_SKIP,
            "pass_seeds": PASS_SEEDS, "max_nodes": max_nodes, "min_nodes": min_nodes, "passes": passes,
            "db_rows_at_start": rows_at_start, "fingerprint": db.fingerprint}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bench_decisions.dump_rows(out, head, halves)
    return passes


def load_puzzles(path=PUZZLE_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["halves"]


def print_stats(db):
    st = db.stats()
    print(f"size {st['bytes'] / 1e6:.1f} MB (file {st['file_bytes'] / 1e6:.1f} MB), positions {st['positions']}")
    for vid, fp, rows, current, trivial in st["versions"]:
        print(f"  version {vid} {fp[:16]}{' (current)' if current else ''}: {rows} rows, {trivial} trivial")
    print("  bytes per table: " + ", ".join(f"{t} {b / 1e6:.1f} MB" for t, b in st["tables"]))
    print("  cost quantiles: " + ", ".join(f"{q:g}: {c}" for q, c in st["cost_quantiles"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", choices=["db", "bench"],
                    help="db: database commands (--stats, --evict, --compact, --repair-costs); bench: build the bench puzzle set")
    ap.add_argument("--run", help="registry run id to dump into the database")
    ap.add_argument("--export", action="store_true", help="also write datasets/puzzles-<run>.jsonl")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--evict", action="store_true")
    ap.add_argument("--compact", action="store_true", help="db: move trivial rows to value-only rows, then compact")
    ap.add_argument("--repair-costs", action="store_true",
                    help="db: rebuild costs above --max-nodes or negative from the rows' children")
    ap.add_argument("--rebuild", action="store_true", help="bench: rebuild data/bench/puzzles.json")
    ap.add_argument("--per-half", type=int, default=PUZZLES_PER_HALF)
    ap.add_argument("--out", default=PUZZLE_PATH)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--root", default=ROOT, help="registry root (default: the repository)")
    ap.add_argument("--max-gb", type=float, default=MAX_GB)
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--max-nodes", type=int, default=MAX_NODES)
    ap.add_argument("--min-nodes", type=int, default=MIN_NODES)
    ap.add_argument("--distribution", action="store_true", help="also solve each option's outcome distribution")
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    if args.command == "db":
        db = sts.SolvedDb(args.db, max_gb=args.max_gb)
        if args.evict:
            print(db.evict())
        if args.compact:
            print(db.compact())
        if args.repair_costs:
            print(db.repair_costs(args.max_nodes))
        if args.stats or not (args.evict or args.compact or args.repair_costs):
            print_stats(db)
    elif args.command == "bench":
        if os.path.exists(args.out) and not args.rebuild:
            print(f"{args.out} exists; --rebuild to redo it")
            return 0
        t = time.time()
        db = sts.SolvedDb(args.db, max_gb=args.max_gb)
        passes = build_set(db, args.out, per_half=args.per_half, threads=args.threads, max_nodes=args.max_nodes,
                           min_nodes=args.min_nodes)
        db.evict()
        print(f"{args.out}: {args.per_half} per half, passes {passes}, {time.time() - t:.0f}s")
        print_stats(db)
    elif args.run:
        t = time.time()
        n = dump_run(args.run, args.db, root=args.root, export=args.export, max_gb=args.max_gb, threads=args.threads,
                     max_nodes=args.max_nodes, min_nodes=args.min_nodes, distribution=args.distribution)
        print(f"{args.run}: {n} puzzles in {time.time() - t:.0f}s")
        print_stats(sts.SolvedDb(args.db, max_gb=args.max_gb))
    else:
        ap.error("give --run <run id> or the db command")
    return 0


if __name__ == "__main__":
    sys.exit(main())
