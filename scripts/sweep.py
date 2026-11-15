"""Learned-play sweep. Amendments 3-4: one config (CONFIGS; Amendment 4's
is the score target with branch rollouts, self-play greedy, temperature 0,
branches at BRANCH_GAP), with 2 seeds, each trained
through learn.py as round 0 + at least ROUNDS and at most ROUNDS_MAX
self-play rounds (the stop rule: from round ROUNDS on, a run stops once its
net clearly beats the heuristic), ranking loss on, varied setups (random
HP, 13-25-card decks) in every training game, the final round benched.
The night is sized so ROUNDS rounds fit; rounds after that may run on into
the next day (the projection prints the worst case, ROUNDS_MAX rounds).
Amendment 2's plan (target x branches = 4 configs) is CONFIGS set to all
four.

Before the night (`--round0`): the round-0 pool and validation set are
played and round 0's net trained once per target, so the night's rows all
reuse it and the seeds run side by side with --jobs 2 from the start.

Round 0 (B3b): a heuristic pool of FULL_N games per encounter group per
target type (validation stays VAL_N), generated once per type and counted
once in the night's total. Round 0's net trains on a random half of the
pool's examples (D0_SAMPLE, fixed sample and training seed), once per
target: every later run of that target (the other seed, branch twins)
reuses that round-0 run (learn.learn `round0`). While round 0 is in,
later rounds use a random sixth of the pool's examples, drawn once per
seed.

Seeds: seed s sets the training seed of rounds >= 1, offsets their spec
seeds (`round_seed`) and so also draws their pool sample, so a config's
seeds play different later games over the same round 0.

Sizing rule (projected from the rates in RATES etc., calibrated on
Amendment 3's sweep, see docs/decisions.md): every run uses the same data
sizes. The time projection takes the worst case of each of Amendment 2's
window rules: round 0 in every round's training (never retired) and
n_late games per group from round 2 (retired after round 1), plus branch
games' self-play and examples. Memory: each round's self-play and the
largest training set a run can really build (`train_examples`) fit the
peak model at each run's share of the free memory (`run_budget_gb`).
n_round (rounds before retirement) is the largest size that fits; n_late
the largest >= n_round that fits; fitting means the night's budget, each
round's self-play within ROUND_MIN and the memory model. The projection
counts each round's solve step (SOLVE_MIN, round 0's SOLVE0_MIN before
the night, as many games as the run's solve threads walk back in that
time) and the database's exact examples in training. The plan refuses to
start when the projected total exceeds the budget, when the free memory
sizes rounds below MIN_N_ROUND games per group, or when the disk can't
hold the night's caches (`disk_need_gb`), unless --force.

Guard: after each run, if on either half of the bench's tight fights its
win rate or contested ranking (point estimates) is below the random
evaluator's (RANDOM_FLOOR, docs/research/bench-baseline.md), the sweep
writes its table, prints why, and stops (exit 3). `--no-guard` (log
instead of stopping) is accepted only with `--tiny`.

Each run is one registry run per round (the last round benched); the table
(bench_compare over the last rounds' run ids, each config's mean over its
seeds, and every round's tight-fight win rate against the heuristic's)
goes to runs/sweep-<date>.md, rewritten after every run.

For the watcher (scripts/sweep_watch.py), the sweep process (not a worker)
appends timestamped lines to <root>/logs/sweep.log (rows started,
finished, exited; the sweep's end) and writes <root>/logs/plan.json (its
pid and each row's projected minutes through each round).

Split over processes (Colab: one run per session, colab/sweep.ipynb):
`--only` runs the named plan rows at the night plan's sizes, a target's
round-0 run already in the registry with the same round-0 inputs is
reused (`find_round0`), and `--table` writes the table from the newest
finished run of each row in the registry.

Parallel (`--jobs N`): rows run as N worker processes at once
(`sweep.py --only <row> --worker`, log in <root>/logs/<row>.log), the
same runs as one process would make. A target's first row trains its
round-0 net, so the target's other rows start only after it finishes.
Training is overhead-bound and leaves cores idle, so two runs at once take
far less than twice as long; the projection list-schedules the rows N at
a time, each slowed by PARALLEL_SLOWDOWN per extra job, and sizes the
night from that wall time. A worker's guard stop or crash starts no new
rows; the running ones finish, the table is written, and the sweep exits
3 or 1. The planning process fixes the free memory it sized for and
passes it to the workers (`--free`), so every row gets the same sizes.

    python scripts/sweep.py --plan          # print the projection only
    python scripts/sweep.py --round0        # before the night: round-0 pool and net
    python scripts/sweep.py                 # the overnight sweep
    python scripts/sweep.py --jobs 2        # two runs at a time, each in half the free memory
    python scripts/sweep.py --only score-s0 --root <registry>   # one run (Colab)
    python scripts/sweep.py --table --root <registry>           # table of what finished
    python scripts/sweep.py --tiny --no-guard --root <tmp>   # end-to-end dry run
"""

import argparse
import datetime
import json
import math
import os
import shutil
import subprocess
import sys
import time

import learn
import registry

ROUNDS = 6  # the stop rule's first round; the night is sized for this many
ROUNDS_MAX = 10
# (hp, branches) of each config: Amendment 4's one, score target with branch
# rollouts (Amendment 3's was (False, False)).
CONFIGS = [(False, True)]
# Amendment 4: self-play is greedy; branch rollouts give the variety, at
# decisions with an option more than BRANCH_GAP below the best.
TEMPERATURE = 0.0
BRANCH_GAP = 0.05
SEEDS = (0, 1)
ROUND_SEED_STEP = 1000  # seed s plays rounds >= 1 at spec seeds offset by s * this

# Calibrated on Amendment 1's sweep (results/sweep-2026-10-25.log, the
# self-play search learn.SELFPLAY_SEARCH): games per second over all threads,
# full-HP mixed encounters; the second key is no-death mode (switch 6). Net
# rates are Rust inference (spec rust-inference): the Python-inference
# calibration (net 11 / 6, tight fights 10) times the speed-up
# scripts/inference_speed.py measured on the dev machine, median of 5
# interleaved runs (2026-10-25: 7.6x / 12.6x / 4.8x), rounded down.
# Amendment 4: recalibrated on Amendment 3's sweep (varied setups, 2 runs
# at once; logs/score-s*.log, 2026-10-26): round 0's pool 238 games/s, net
# rounds ~200 games/s (median of 20 rounds), so heuristic 225 and net 200.
# No-death rates (switch 6, not run on varied setups) are Amendment 3's
# estimates: the full-HP rates times its measured varied-setup slowdown
# (heuristic 0.75, net 0.42).
RATES = {("heuristic", False): 225.0, ("heuristic", True): 75.0, ("net", False): 200.0, ("net", True): 31.0}
# Tight fights v2 (tight2.json, 24,520 fights; runs/tight2/rescore.json,
# 2026-10-29, on a loaded machine): median of 19
# nets 118 fights/s, the heuristic 158, rounded down.
TIGHT_RATE_NET = 100.0  # tight fights, one-turn search, net (sets the monotone thinning)
TIGHT_RATE_HEUR = 150.0  # the same, search + heuristic: once per run
# Training seconds per example (early stopping included), score / HP net.
# Score: 0.9e-3 measured in Amendment 3's sweep (2 runs at once), rounded up;
# since curriculum Amendment 1 both x 2.9 (HP: 2.0e-3 in RAM, scaled, not
# measured): training reads memory-mapped caches, 2.9x slower once they
# exceed the file cache, as at night sizes here.
TRAIN_S_PER_EXAMPLE = {False: 2.9e-3, True: 5.8e-3}
# The solve step (curriculum): seconds per game walked back on
# puzzles.THREADS threads, fewer taking proportionally longer. Measured
# 2026-10-27 on 18 games each over the real database (3 threads, scaled):
# 3.5 for a net round's games, 2.4 for round 0's heuristic pool (the bench
# set's build: 3.0). That database was full of earlier solves to hit; the
# curriculum's own db/train.sqlite starts empty. Re-measured 2026-10-27 on
# round 0's solve step over it (99 games in 20 min, 6 threads, with a cargo
# build sharing the CPU): 12.2.
SOLVE_S_PER_GAME = 12.0
# A solve step's length (curriculum spec: ~15 min per round, ~60 min for
# round 0's pool); its games (`solve_games`) follow from the run's solve
# threads, which its memory budget sets.
SOLVE_MIN = 15.0
SOLVE0_MIN = 60.0
ROUND0_EXAMPLES = 7  # per game: sampled states, no afterstates
# Fractions of round 0's examples: round 0's own training, and later rounds'
# while round 0 is in (learn.py `d0_sample`).
D0_SAMPLE = {"round0": 0.5, "later": 1 / 6}
ROUND_EXAMPLES = 37  # per game from round 1, with the options' afterstates (ranking); 38.3 measured with varied setups, 35.6 without
# Branch rollouts (switch 7): self-play takes 1.42x as long (B2's; 1.23x and
# 1.52x measured at temperature 0 on varied setups, 2026-10-26); a branch
# game's examples come only from after its branch point: 0.73 of a main
# game's (measured then; 96% of games get a branch).
BRANCH_SELFPLAY = 1.42
BRANCH_EXAMPLES = 0.73
# Per run of ROUNDS_CAL rounds (Amendment 1's), minutes outside self-play and
# training: the bench, the monotone and heuristic tight-fight runs,
# replaying and encoding datasets. The monotone run (MONO_MIN) is per
# round; the rest per run.
OVERHEAD_MIN = {False: 9.5, True: 14.0}
ROUNDS_CAL = 3
GROUPS = 3
TIGHT_FIGHTS = 24_520
FULL_N = 20_000  # round 0's pool: games per encounter group (60k games per target)
VAL_N = 1000  # validation games per encounter group (today's)
ROUND_MIN = 20.0
# A round's tight fights (the monotone check and the gate) play every seed
# at today's rate: thinning to fit 2 min would leave 7 of 20 seeds a cell,
# widening the gate's interval past tight fights v2's 0.012.
MONO_MIN = 5.0
MONO_MIN_CAL = 2.0  # the monotone minutes inside OVERHEAD_MIN's calibration
NIGHT_MIN = 8 * 60.0
# Each run's slowdown per extra parallel job (--jobs): runs share cores in
# their self-play and bench phases. An assumption for --jobs 2 until a real
# parallel night calibrates it.
PARALLEL_SLOWDOWN = 0.15
# Random evaluator on the tight fights (bench-baseline.md): win rate and
# contested ranking per half.
RANDOM_FLOOR = {"held_out": {"win": 0.178, "ranking.contested": 0.744},
                "train": {"win": 0.184, "ranking.contested": 0.701}}


class GuardStop(Exception):
    """A run ranked below the random evaluator."""


def config_name(hp, branches):
    return ("hp" if hp else "score") + ("+branch" if branches else "")


def plan():
    """[{name, hp, branches, seed}]: CONFIGS x SEEDS, seed-major."""
    return [{"name": f"{config_name(hp, br)}-s{s}", "hp": hp, "branches": br, "seed": s}
            for s in SEEDS for hp, br in CONFIGS]


def config(name, hp, branches, seed, n, n_round, n_late, every=1, rounds=None, solve=None, threads=None, solve0=None):
    """A learn.py config: round 0 at n games per group, later rounds at
    n_round (n_late after round 0 retires), varied setups; `rounds` (min,
    max) for the stop rule (default ROUNDS, ROUNDS_MAX); `solve` games per
    solve step, round 0's included unless `solve0` (default learn's);
    `threads` the solve step's threads (`solve_threads`; default the
    finder's)."""
    low, high = rounds or (ROUNDS, ROUNDS_MAX)
    switches = {}
    if hp:
        switches["hp_loss"] = True
    if branches:
        switches["branches"] = True
    return {"name": name, "mode": "effects", "n_train": n, "n_val": min(VAL_N, max(1, n // 10)), "n_round": n_round,
            "n_late": n_late, "train_seed": 1, "val_seed": 2, "round_seed": ROUND_SEED_STEP * seed,
            "d0_sample": dict(D0_SAMPLE), "round0_seed": 0,
            "search": dict(learn.SELFPLAY_SEARCH), "seed": seed, "switches": switches, "setups": "varied",
            **({"branch_gap": BRANCH_GAP} if branches else {}), **learn.label_settings({"switches": switches}),
            **({"solve_games": solve, "solve_games0": solve if solve0 is None else solve0} if solve is not None else {}),
            **({"solve_threads": threads} if threads is not None else {}),
            "rounds": {"n": high, "min": low, "temperature": TEMPERATURE, "every": every}}


def row_config(r):
    """The learn.py config of a plan row."""
    return config(r["name"], r["hp"], r["branches"], r["seed"], r["n"], r["n_round"], r["n_late"], r["every"],
                  r.get("rounds"), r.get("solve"), r.get("solve_threads"), r.get("solve0"))


def round0_min(hp, n):
    """Minutes to self-play round 0 (train + validation), shared per target type."""
    return GROUPS * (n + min(VAL_N, max(1, n // 10))) / RATES[("heuristic", hp)] / 60


# Memory: each run's budget is the memory physically free when the sweep
# plans (`free_gb`), less MEM_MARGIN for other processes,
# split across --jobs (`run_budget_gb`; curriculum spec, replacing
# Amendment 4's fixed 6.5 GB). Peak model, refit after Amendment 1
# (training from memory-mapped caches; scripts/memprobe.py,
# docs/decisions.md, scripts/tests/data/memprobe.json, two real runs at 300
# and 1,200 games per group): a round peaks at the largest of
# - its fixed phases, FIXED_GB: the tight fights (<= 2.00 GB measured), the
#   puzzle pass, a streaming cache build (<= 1.79), the solve step;
# - self-play (`play_peak_gb`): PLAY_BASE_GB (the net's search on every
#   core) plus PLAY_BYTES per main game of the round (GROUPS x n; the
#   branch games' call stays under it);
# - training (`peak_gb`): TRAIN_BASE_GB plus PEAK_BYTES per example of its
#   training set (the view holds only indices, labels and weights; the
#   mapped caches are file cache, not commit).
# Never below a measured round; within 10% of the largest round measured at
# each size (repeats at one size differ by up to 18%). The solve step peaks
# at most BASE_GB plus puzzles.THREAD_BYTES per thread (`solve_threads`
# keeps that within the budget).
BASE_GB = 1.25
FIXED_GB = 2.0
PLAY_BASE_GB = 2.29
PLAY_BYTES = 100_000
TRAIN_BASE_GB = 1.43
PEAK_BYTES = 200
EXACT_EXAMPLES = learn.EXACT_CAP
MEM_MARGIN = 1.0  # GB left free for other processes (tunable; owner, 2026-10-27: 1 GB, for more solver threads)
# The smallest later round worth running, in games per group: below it the
# plan refuses to start (tunable).
MIN_N_ROUND = 500
# Disk (Amendment 1): a v7 cache holds ~4.5 KB per example on disk
# (measured on real round caches, codec bytes included). The night needs
# its caches (`disk_need_gb`) plus DISK_MARGIN free, or the plan refuses.
CACHE_BYTES = 4600
DISK_MARGIN = 2.0  # GB (tunable)


def free_gb():
    """Physically free memory now (GlobalMemoryStatusEx), GB."""
    import puzzles
    return puzzles.free_bytes() / 1e9


def run_budget_gb(jobs=1, free=None):
    """Each run's memory: `free` (default: free now) less MEM_MARGIN, split
    across `jobs`."""
    return ((free_gb() if free is None else free) - MEM_MARGIN) / jobs


def peak_gb(examples):
    """Training's peak (the model) with a training set of `examples`
    (self-play examples; the database's exact examples are added)."""
    return TRAIN_BASE_GB + PEAK_BYTES * (examples + EXACT_EXAMPLES) / 1e9


def play_peak_gb(n):
    """A round's self-play peak at n games per group."""
    return PLAY_BASE_GB + PLAY_BYTES * GROUPS * n / 1e9


def round_peak_gb(n, examples):
    """A round's whole peak: self-play at n games per group (0: none),
    training on `examples`, or its fixed phases."""
    return max(FIXED_GB, play_peak_gb(n) if n else 0.0, peak_gb(examples))


def max_train_examples(jobs=1, free=None):
    """The largest training set (self-play examples) whose modelled peak
    fits a run's budget (0 when none does)."""
    return max(0, int((run_budget_gb(jobs, free) - TRAIN_BASE_GB) * 1e9 / PEAK_BYTES) - EXACT_EXAMPLES)


def free_disk_gb(root=registry.ROOT):
    """Free disk where the registry's caches go, GB."""
    d = registry.cache_dir(root)
    return shutil.disk_usage(d if os.path.isdir(d) else root).free / 1e9


def _dir_gb(d):
    return sum(os.path.getsize(os.path.join(p, n)) for p, _, ns in os.walk(d) for n in ns) / 1e9         if os.path.isdir(d) else 0.0


def disk_need_gb(rows, jobs, root=registry.ROOT):
    """Disk the night needs free (Amendment 1): the feature caches it
    writes, worst case (ROUNDS_MAX rounds per run at n_late), less what
    eviction frees (it keeps the cache folder under registry.CACHE_CAP, so
    the folder grows at most to the cap); each job's
    exact-example temporary cache; the training database's room to its cap
    (puzzles.MAX_GB); and DISK_MARGIN."""
    import puzzles
    night = sum(ROUNDS_MAX * round_examples(r, r["n_late"]) for r in rows) * CACHE_BYTES / 1e9
    now = _dir_gb(registry.cache_dir(root))
    caches = max(0.0, min(now + night, registry.CACHE_CAP / 1e9) - now)
    db = os.path.getsize(learn.db_path(root)) / 1e9 if os.path.exists(learn.db_path(root)) else 0.0
    return caches + jobs * EXACT_EXAMPLES * CACHE_BYTES / 1e9 + max(0.0, puzzles.MAX_GB - db) + DISK_MARGIN


def round0_peak_gb():
    """`--round0`'s peak (one process): its fixed phases (the pool's
    streaming cache build, the solve step) or training round 0 on its pool
    sample. The pool's games are stored (Amendment 3's), so they aren't
    played again; playing them afresh would peak higher (the whole pool's
    records are held: ~2.96 GB at 24,000 games)."""
    return max(FIXED_GB, peak_gb(GROUPS * FULL_N * ROUND0_EXAMPLES * D0_SAMPLE["round0"]))


def solve_threads(jobs=1, free=None):
    """Solver threads in a run's solve step: as many 1M-node solves
    (puzzles.THREAD_BYTES each) as fit its budget beside BASE_GB, at most
    puzzles.THREADS, at least 1."""
    import puzzles
    return max(1, min(puzzles.THREADS, int((run_budget_gb(jobs, free) - BASE_GB) * 1e9 // puzzles.THREAD_BYTES)))


def round_examples(row, n):
    """Examples of one later round's dataset at n games per group."""
    return GROUPS * n * ROUND_EXAMPLES * (1 + BRANCH_EXAMPLES if row["branches"] else 1.0)


def train_examples(row, n_round, n_late):
    """The largest training set a run can build (learn.learn's windows):
    round 0's later sample plus 2 rounds at n_round while round 0 is in, or
    2 rounds at n_late once it is out (n_late rounds never train with round
    0)."""
    d0 = GROUPS * row["n"] * ROUND0_EXAMPLES * D0_SAMPLE["later"]
    return max(d0 + 2 * round_examples(row, n_round), 2 * round_examples(row, n_late))


def round_min(row, n):
    """Minutes of one later round's self-play at n games per group."""
    return GROUPS * n * (BRANCH_SELFPLAY if row["branches"] else 1.0) / RATES[("net", row["hp"])] / 60


def mono_min():
    """Minutes of one round's monotone tight-fight run at `mono_every`."""
    return TIGHT_FIGHTS / mono_every() / TIGHT_RATE_NET / 60


def mono_every():
    """Tight-fight thinning so each monotone run fits MONO_MIN."""
    return max(1, math.ceil(TIGHT_FIGHTS / (TIGHT_RATE_NET * MONO_MIN * 60)))


def project(row, n_round, n_late, reuse0=False, rounds=None, cumulative=False):
    """Minutes of one run of `rounds` rounds (default ROUNDS; excluding the
    shared round-0 data), worst case: round 0's sample in every round's
    training and n_late games from round 2. `reuse0`: round 0's training is
    reused. `cumulative`: the list of minutes through rounds 0..`rounds`
    instead (the run-wide overhead counted in round 0)."""
    def train(examples):  # the database's exact examples train beside them (score target)
        return (examples + (0 if row["hp"] else EXACT_EXAMPLES)) * TRAIN_S_PER_EXAMPLE[row["hp"]] / 60

    def ex(n):
        return round_examples(row, n)
    ex0 = GROUPS * row["n"] * ROUND0_EXAMPLES
    m = OVERHEAD_MIN[row["hp"]] - ROUNDS_CAL * MONO_MIN_CAL + TIGHT_FIGHTS / mono_every() / TIGHT_RATE_HEUR / 60 + (
        0.0 if reuse0 else train(ex0 * D0_SAMPLE["round0"]) + solve_min(row, row.get("solve0", learn.SOLVE_GAMES0), row.get("solve_threads")))
    cum, prev = [m], 0
    for k in range(1, (ROUNDS if rounds is None else rounds) + 1):
        n = n_round if k == 1 else n_late
        m += (round_min(row, n) + mono_min() + solve_min(row, row.get("solve", learn.SOLVE_GAMES), row.get("solve_threads"))
              + train(ex0 * D0_SAMPLE["later"] + ex(n) + (ex(prev) if prev else 0)))
        cum.append(m)
        prev = n
    return cum if cumulative else m


def slowdown(jobs):
    """How much longer each run takes with `jobs` runs at once."""
    return 1.0 + PARALLEL_SLOWDOWN * (jobs - 1)


def leaders(rows):
    """{target (hp): name of its first row in `rows`}: that row trains the
    target's round-0 net, which the target's other rows reuse."""
    out = {}
    for r in rows:
        out.setdefault(r["hp"], r["name"])
    return out


def next_ready(pending, lead, done):
    """The first pending row that may start: a target's first row, one
    whose target's first row has finished, or any row of a target not in
    `lead` (its round 0 is already trained)."""
    return next((r for r in pending if lead.get(r["hp"]) in (None, r["name"]) or lead[r["hp"]] in done), None)


def makespan(rows, jobs, extra=None, lead=None):
    """Wall-clock minutes of `rows` run `jobs` at a time in order (each
    `minutes` + `extra[name]`, times `slowdown(jobs)`), a target's other
    rows after its first (`lead`, default `leaders(rows)`; {} when round 0
    is trained before); with jobs=1 the plain sum."""
    lead, extra, f = leaders(rows) if lead is None else lead, extra or {}, slowdown(jobs)
    t, running, done, pending = 0.0, [], set(), list(rows)
    while pending or running:
        while len(running) < jobs:
            r = next_ready(pending, lead, done)
            if r is None:
                break
            pending.remove(r)
            running.append((t + (r["minutes"] + extra.get(r["name"], 0.0)) * f, r["name"]))
        end, name = min(running)
        running.remove((end, name))
        t = end
        done.add(name)
    return t


def round0_train_min(hp, n, threads=None):
    """Minutes to solve a target's round-0 pool's tails and train its
    round-0 net on its pool sample (and the database's exact examples)."""
    examples = GROUPS * n * ROUND0_EXAMPLES * D0_SAMPLE["round0"] + (0 if hp else EXACT_EXAMPLES)
    return examples * TRAIN_S_PER_EXAMPLE[hp] / 60 + solve_min({"hp": hp}, solve_games(threads, SOLVE0_MIN), threads)


def solve_games(threads=None, minutes=SOLVE_MIN):
    """Games a solve step walks back in `minutes` on `threads` threads
    (default puzzles.THREADS), at least 1."""
    import puzzles
    return max(1, int(minutes * 60 * (threads or puzzles.THREADS) / (SOLVE_S_PER_GAME * puzzles.THREADS)))


def solve_min(row, games, threads=None):
    """Minutes of a solve step of `games` games on `threads` threads
    (default puzzles.THREADS); none for the HP target (switch 6)."""
    import puzzles
    if row["hp"]:
        return 0.0
    return games * SOLVE_S_PER_GAME * puzzles.THREADS / (threads or puzzles.THREADS) / 60


def projection(n_round=None, n_late=None, jobs=1, free=None):
    """(rows, before-the-night minutes, total minutes): round 0 (pool,
    validation and net, once per target) runs before the night
    (`--round0`), so every row reuses it and none waits for another; the
    total is the night's wall time with `jobs` runs at once (`makespan`) for
    ROUNDS rounds per run. Each row also has `minutes_max` (ROUNDS_MAX
    rounds) and `cumulative` (minutes through rounds 0..ROUNDS_MAX, for the
    watcher) and `solve_threads`. n_round and n_late default to the sizing
    rule's (`fit_sizes`) for `free` GB of free memory (default: free now)."""
    free = free_gb() if free is None else free
    if n_round is None:
        n_round, n_late = fit_sizes(jobs=jobs, free=free)
    rows = []
    for p in plan():
        threads = solve_threads(jobs, free)
        row = {**p, "n": FULL_N, "n_round": n_round, "n_late": n_late, "every": mono_every(),
               "solve_threads": threads, "solve": solve_games(threads), "solve0": solve_games(threads, SOLVE0_MIN),
               "free": free}
        row["minutes"] = project(row, n_round, n_late, reuse0=True)
        row["minutes_max"] = project(row, n_round, n_late, reuse0=True, rounds=ROUNDS_MAX)
        row["cumulative"] = project(row, n_round, n_late, reuse0=True, rounds=ROUNDS_MAX, cumulative=True)
        rows.append(row)
    targets = {r["hp"] for r in rows}
    before = sum(round0_min(hp, FULL_N) + round0_train_min(hp, FULL_N, solve_threads(1, free)) for hp in targets)
    return rows, before, makespan(rows, jobs, lead={})


def fit_sizes(budget=NIGHT_MIN, jobs=1, free=None):
    """(n_round, n_late) per the sizing rule (1 when nothing fits), for a
    night run `jobs` rows at a time with `free` GB free (default: free
    now): the night's time, each round's self-play within ROUND_MIN and
    each training set within `max_train_examples`."""
    free = free_gb() if free is None else free
    cap, mem = max_train_examples(jobs, free), run_budget_gb(jobs, free)

    def ok(nr, nl):
        if max(FIXED_GB, play_peak_gb(max(nr, nl))) > mem:
            return False
        rows, _, total = projection(nr, nl, jobs, free)
        return total <= budget and all(round_min(r, nl) <= ROUND_MIN and
                                       train_examples(r, nr, nl) <= cap for r in rows)

    def largest(lo, hi, fits):
        while lo < hi:
            mid = (lo + hi + 1) // 2
            lo, hi = (mid, hi) if fits(mid) else (lo, mid - 1)
        return lo
    n_round = largest(1, FULL_N, lambda m: ok(m, m))
    return n_round, largest(n_round, FULL_N, lambda m: ok(n_round, m))


def print_projection(rows, before, total, out=print, jobs=1):
    out(f"self-play search: {learn.SELFPLAY_SEARCH}; round 0 + {ROUNDS}-{ROUNDS_MAX} rounds per run (stop rule), "
        f"ranking loss on, varied setups")
    r0 = rows[0]
    out(f"games per group: round 0 {r0['n']}, n_round {r0['n_round']}, n_late {r0['n_late']} "
        f"(worst case: round 0 never leaves training, n_late from round 2)")
    out(f"run               target  branches  seed  every   minutes ({ROUNDS} rounds)  worst ({ROUNDS_MAX} rounds)")
    for r in rows:
        out(f"{r['name']:<17} {'hp' if r['hp'] else 'score':<7} {'on' if r['branches'] else 'off':<9} "
            f"{r['seed']:>4}  {r['every']:>5}  {r['minutes']:>18.1f}  {r['minutes_max']:>18.1f}")
    big = max(train_examples(r, r["n_round"], r["n_late"]) for r in rows)
    free = r0["free"]
    out(f"memory: {free:.1f} GB free, less {MEM_MARGIN:g} GB margin, / {jobs} job(s) = "
        f"{run_budget_gb(jobs, free):.1f} GB per run; solve steps on {r0['solve_threads']} thread(s)")
    out(f"largest training set: {big / 1e3:.0f}k examples + {EXACT_EXAMPLES / 1e3:.0f}k exact, training ~{peak_gb(big):.1f} GB; "
        f"self-play ~{play_peak_gb(max(r0['n_round'], r0['n_late'])):.1f} GB; "
        f"run peak ~{round_peak_gb(max(r0['n_round'], r0['n_late']), big):.1f} GB")
    out(f"before the night (--round0): round-0 pool, validation and net, {before:.0f} min, ~{round0_peak_gb():.1f} GB "
        f"peak (one process: {run_budget_gb(1, free):.1f} GB)")
    worst = makespan([{**r, "minutes": r["minutes_max"]} for r in rows], jobs, lead={})
    if jobs == 1:
        out(f"projected total: {total:.0f} min ({total / 60:.1f} h); worst case {worst:.0f} min ({worst / 60:.1f} h)")
    else:
        out(f"projected wall time with --jobs {jobs}: {total:.0f} min ({total / 60:.1f} h); worst case "
            f"{worst:.0f} min ({worst / 60:.1f} h); rows run {jobs} at a time, each x{slowdown(jobs):.2f} for "
            f"sharing cores")


def fast_first(rows):
    """Rows ordered cheapest first (stable), so a night cut short still has
    the fast configs."""
    return sorted(rows, key=lambda r: r["minutes"])


# A dry run's rounds (min, max): the stop rule's path at a tiny size.
TINY_ROUNDS = (1, 2)
TINY_SOLVE = 2  # games per solve step in a dry run


def tiny_rows():
    """Every run at a tiny size, for a dry run."""
    return [{**p, "n": 2, "n_round": 2, "n_late": 2, "every": 100, "minutes": 0.0, "rounds": TINY_ROUNDS,
             "solve": TINY_SOLVE, "cumulative": [0.0] * (TINY_ROUNDS[1] + 1)} for p in plan()]


def below_floor(bench):
    """Reasons a bench result is below the random evaluator (empty when not)."""
    out = []
    for half, floor in RANDOM_FLOOR.items():
        m = bench["sets"]["tight"]["halves"][half]["metrics"]
        for key, f in floor.items():
            if m.get(key) and m[key][0] < f:
                out.append(f"{half} {key} {m[key][0]:.3f} < random {f:.3f}")
    return out


def table_path(root):
    """runs/sweep-<date>.md, or -2, -3, ... when a sweep already wrote one
    that day (a table is never overwritten by a later sweep)."""
    base = os.path.join(registry.runs_dir(root), f"sweep-{datetime.date.today():%Y-%m-%d}")
    path, k = base + ".md", 2
    while os.path.exists(path):
        path, k = f"{base}-{k}.md", k + 1
    return path


# Config keys that fix round 0 (with the HP switch): runs agreeing on them
# trained the same round-0 net. The curriculum's label settings
# (learn.label_settings) are among them, so an outcome-labelled round-0 net
# (none recorded) or one with other settings is never reused; the round-0
# pool dataset doesn't depend on them and still is.
ROUND0_KEYS = ("mode", "n_train", "n_val", "train_seed", "val_seed", "d0_sample", "round0_seed", "search", "setups",
               "labels", "w_near", "exact_cap", "exact_share", "exact_leaves", "exact_split", "min_puzzles",
               "regret_max")


def finished_runs(root):
    """Registry runs with a round.json (written once their round trained)."""
    d = registry.runs_dir(root)
    if not os.path.isdir(d):
        return []
    runs = [registry.Run(os.path.join(d, n)) for n in sorted(os.listdir(d))]
    return [r for r in runs if os.path.exists(os.path.join(r.path, "round.json"))]


def created(run):
    """When a run was created, comparable across machines: run.json's stamp
    with its UTC offset (local time, Colab UTC); an older stamp without one
    is read as this machine's local time."""
    stamp = run._read("run.json").get("created")
    if not stamp:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    t = datetime.datetime.fromisoformat(stamp)
    return t if t.utcoffset() is not None else t.astimezone()


def find_round0(cfg, root):
    """The newest finished round-0 run in the registry (model saved, same
    rules version) whose round-0 inputs match `cfg`'s, else None: another
    process (Colab session) already trained this target's round 0."""
    def key(c):
        return [c.get(k) for k in ROUND0_KEYS] + [bool(c.get("switches", {}).get("hp_loss"))]
    best = None
    for run in finished_runs(root):
        if run._read("round.json").get("round") != 0 or not os.path.exists(run.model_path):
            continue
        if key(run._read("config.json")) != key(cfg):
            continue
        if run._read("run.json").get("rules_version") != registry.rules_version():
            continue
        if best is None or created(run) > created(best):
            best = run
    return best


def write_table(root, log=print, path=None):
    """Writes `path` (default a new `table_path`) from the newest finished
    final-round run (benched, round >= 1) of each plan row under `root`;
    returns (path, names of rows missing)."""
    newest = {}
    for run in finished_runs(root):
        if not run._read("round.json").get("round") or not os.path.exists(run.bench_path):
            continue
        name = run._read("config.json").get("name")
        if name not in newest or created(run) > created(newest[name]):
            newest[name] = run
    rows = []
    for r in projection()[0]:
        if r["name"] in newest:
            c = newest[r["name"]]._read("config.json")
            rows.append({**r, "n": c["n_train"], "n_round": c.get("n_round"), "n_late": c.get("n_late")})
    missing = [p["name"] for p in plan() if p["name"] not in newest]
    path = path or table_path(root)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report(rows, [newest[r["name"]].id for r in rows], None, root))
        if missing:
            f.write("\nNot run yet: " + ", ".join(missing) + "\n")
    log(f"table: {path}" + (f" (missing: {', '.join(missing)})" if missing else ""))
    return path, missing


def run_sweep(rows, root, quick=False, log=print, guard=True, write=True):
    """Trains and benches every row; returns the run ids (last rounds) and
    writes `table_path`, rewritten after every run so an
    interrupted sweep keeps the table of what finished. A row whose target
    already ran (in this process, else in the registry: `find_round0`)
    reuses that round-0 run. With
    `guard`, raises GuardStop, after writing the table, when a run is below
    the random floor; without, it only logs that. `write=False` (a
    --jobs worker): no table, the parent writes it."""
    ids, timings, round0 = [], [], {}
    path = table_path(root) if write else None
    for r in rows:
        cfg = row_config(r)
        if write:
            log(f"started {r['name']}")
        t = time.perf_counter()
        key = r["hp"]
        if key not in round0:
            found = find_round0(cfg, root)
            if found is not None:
                round0[key] = found
        runs = learn.learn(cfg, bench="quick" if quick else True, root=root, log=log, bench_last_only=True,
                           round0=round0.get(key))
        round0.setdefault(key, runs[0])
        run = runs[-1]
        ids.append(run.id)
        timings.append((time.perf_counter() - t) / 60)
        log(f"{r['name']}: run {run.id}, {timings[-1]:.1f} min (projected {r['minutes']:.1f})")
        if write:
            log(f"{r['name']}: finished")
        if write:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(report(rows[:len(ids)], ids, timings, root))
            log(f"table: {path}")
        reasons = below_floor(run._read("bench.json"))
        if reasons and not guard:
            log(f"{r['name']}: below the random floor (guard off): " + "; ".join(reasons))
        elif reasons:
            raise GuardStop(f"{r['name']} ({run.id}) is below the random evaluator: " + "; ".join(reasons))
    if write:
        log(f"sweep finished: table {path}")
    return ids, path


def train_round0(rows, root, log=print):
    """Before the night: plays each target's round-0 pool and validation set
    and trains its round-0 net (round 0 only), unless the registry already
    has it (`find_round0`). Returns {target: run}."""
    out = {}
    for hp, name in leaders(rows).items():
        r = next(r for r in rows if r["name"] == name)
        cfg = row_config(r)
        found = find_round0(cfg, root)
        if found is not None:
            log(f"round 0 ({'hp' if hp else 'score'}): already trained, {found.id}")
        else:
            t = time.perf_counter()
            found = learn.learn({**cfg, "rounds": {**cfg["rounds"], "n": 0}}, root=root, log=log)[0]
            log(f"round 0 ({'hp' if hp else 'score'}): {found.id}, {(time.perf_counter() - t) / 60:.1f} min")
        out[hp] = found
    return out


def launch_worker(name, root, jobs, extra, log_path):
    """A worker process running one plan row (`--only <row> --worker`),
    output to `log_path`."""
    f = open(log_path, "w", encoding="utf-8")
    cmd = [sys.executable, "-u", os.path.abspath(__file__), "--only", name, "--worker", "--jobs", str(jobs),
           "--root", root] + list(extra)
    proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
    proc.log_file = f
    return proc


def tail(path, n=20):
    with open(path, encoding="utf-8", errors="replace") as f:
        return "".join(f.readlines()[-n:])


def run_parallel(rows, root, jobs, extra=(), launch=launch_worker, log=print, poll=2.0):
    """Runs `rows` as worker processes, `jobs` at a time in order, a
    target's other rows after its first finishes (`next_ready`); the table
    (one file) is rewritten after every finished row. A worker exiting 3
    (guard) or otherwise non-zero (crash) starts no new rows; the running
    ones finish, the table is written, and the stop is reported with the
    tail of the row's log. Returns 0, 3 (guard) or 1 (crash)."""
    os.makedirs(os.path.join(root, "logs"), exist_ok=True)
    path = table_path(root)
    # A target whose round 0 is already in the registry (--round0) holds no row back.
    lead = {hp: name for hp, name in leaders(rows).items()
            if find_round0(row_config(next(r for r in rows if r["name"] == name)), root) is None}
    if lead:
        log("round 0 not trained yet for " + ", ".join(lead.values()) + ": its other rows wait for it (--round0 first)")
    pending, running, done, stop = list(rows), {}, set(), None
    while running or (pending and stop is None):
        while stop is None and len(running) < jobs:
            r = next_ready(pending, lead, done)
            if r is None:
                break
            pending.remove(r)
            log_path = os.path.join(root, "logs", f"{r['name']}.log")
            running[r["name"]] = (launch(r["name"], root, jobs, extra, log_path), log_path)
            log(f"started {r['name']} (log: {log_path})")
        for name, (proc, log_path) in list(running.items()):
            code = proc.poll()
            if code is None:
                continue
            del running[name]
            if getattr(proc, "log_file", None):
                proc.log_file.close()
            if code == 0:
                done.add(name)
                log(f"{name}: finished")
                write_table(root, log, path)
            elif stop is None:
                stop = (code, name, log_path)
                log(f"{name}: exited {code}; starting no new rows")
        if running:
            time.sleep(poll)
    write_table(root, log, path)
    if stop is None:
        log(f"sweep finished: table {path}")
        return 0
    code, name, log_path = stop
    why = "stopped by the random-floor guard" if code == 3 else f"crashed (exit {code})"
    log(f"sweep stopped: {name} {why}; last lines of {log_path}:\n{tail(log_path)}")
    return 3 if code == 3 else 1


def seed_means(rows, ids, root):
    """Markdown rows: per config, the mean over its finished seeds of the
    tight-fight win rate and contested ranking per half (point estimates)."""
    by = {}
    for r, i in zip(rows, ids):
        bench = registry.Run(os.path.join(registry.runs_dir(root), i))._read("bench.json") or {}
        halves = bench.get("sets", {}).get("tight", {}).get("halves", {})
        vals = [(halves.get(h, {}).get("metrics", {}).get(k) or [float("nan")])[0]
                for k in ("win", "ranking.contested") for h in ("train", "held_out")]
        by.setdefault(config_name(r["hp"], r["branches"]), []).append(vals)
    out = []
    for name, vs in by.items():
        mean = [sum(v[j] for v in vs) / len(vs) for j in range(4)]
        out.append(f"| {name} | {len(vs)} | " + " | ".join(f"{x:.3f}" for x in mean) + " |")
    return out


def chain(run_id, root):
    """The round runs of a sweep row, round 1 to its final round, from its
    final run back through `parent_run` (round 0, shared, excluded)."""
    out, rid = [], run_id
    while rid:
        run = registry.Run(os.path.join(registry.runs_dir(root), rid))
        rj = run._read("round.json") or {}
        if not rj.get("round"):
            break
        out.append(rj)
        rid = rj.get("parent_run")
    return out[::-1]


def round_rows(rows, ids, root):
    """Markdown rows: per run and round, its net's tight-fight win rate
    beside the heuristic's per half, whether round 0 was in, the gate."""
    out = []
    for r, i in zip(rows, ids):
        for rj in chain(i, root):
            halves = (rj.get("heuristic") or {}).get("halves", {})
            cells = [f"{halves[h]['net'][0]:.3f} ({halves[h]['heuristic'][0]:.3f})" if h in halves else "-"
                     for h in ("train", "held_out")]
            gate = rj.get("gate")
            out.append(f"| {r['name']} | {rj['round']} | {cells[0]} | {cells[1]} | "
                       f"{'yes' if (rj.get('window') or {}).get('round0_in') else 'no'} | "
                       f"{'-' if gate is None else ('met' if gate['met'] else 'no')} |")
    return out


def report(rows, ids, timings, root):
    import bench_compare
    results, warnings = bench_compare.load_results(ids, registry.runs_dir(root))
    lines = [f"# Learned-play sweep {datetime.date.today():%Y-%m-%d}", "",
             "| run | target | branches | seed | run id (last round) | n/group | n_round | n_late | minutes (projected) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r, i, t in zip(rows, ids, timings or [None] * len(ids)):
        minutes = "-" if t is None else f"{t:.1f}"
        lines.append(f"| {r['name']} | {'hp' if r['hp'] else 'score'} | {'on' if r['branches'] else 'off'} | "
                     f"{r['seed']} | {i} | {r['n']} | {r['n_round']} | {r['n_late']} | {minutes} ({r['minutes']:.1f}) |")
    lines += [""] + [f"warning: {w}" for w in warnings]
    lines += ["", "## mean over seeds", "", "Point estimates averaged over the finished seeds (no interval).", "",
              "| config | seeds | win train | win held-out | ranking train | ranking held-out |",
              "|---|---|---|---|---|---|"] + seed_means(rows, ids, root)
    lines += ["", "## rounds", "", "Tight-fight win rate of each round's net (the heuristic's in brackets), "
              "on the monotone check's specs.", "",
              "| run | round | win train | win held-out | round 0 in | gate |", "|---|---|---|---|---|---|"]
    lines += round_rows(rows, ids, root)
    for half in ("held_out", "train", "gap:held_out"):
        lines += ["", f"## tight / {half}", "", "```", bench_compare.table(results, "tight", half), "```"]
    lines += ["", "## representation", "", "```", bench_compare.representation_table(results), "```", ""]
    return "\n".join(lines)


def watched_log(root, rows, jobs):
    """A log function for the sweep process that also appends timestamped
    lines to <root>/logs/sweep.log, after writing <root>/logs/plan.json
    (pid, each row's projected minutes through each round, scaled for
    `jobs`; `first_round` 1 when round 0 is already trained, else round 0's
    data and training are added) for sweep_watch.py."""
    logs = os.path.join(root, "logs")
    os.makedirs(logs, exist_ok=True)
    f = slowdown(jobs)
    plan_rows = {}
    for r in rows:
        trained = find_round0(row_config(r), root) is not None
        r0 = 0.0 if trained or not r["n"] else round0_min(r["hp"], r["n"]) + round0_train_min(r["hp"], r["n"], r.get("solve_threads"))
        plan_rows[r["name"]] = {"minutes_by_round": [(m + r0) * f for m in r["cumulative"]], "first_round": int(trained)}
    with open(os.path.join(logs, "plan.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"pid": os.getpid(), "jobs": jobs, "started": datetime.datetime.now().astimezone().isoformat(
            timespec="seconds"), "rows": plan_rows}, fh, indent=1)
    path = os.path.join(logs, "sweep.log")

    def log(msg):
        print(msg, flush=True)
        stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            for line in str(msg).splitlines() or [""]:
                fh.write(f"{stamp} {line}\n")
    return log


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", action="store_true", help="print the projection and exit")
    ap.add_argument("--force", action="store_true", help="start even when the projection exceeds the budget")
    ap.add_argument("--budget", type=float, default=NIGHT_MIN, help="night budget in minutes (default 480)")
    ap.add_argument("--tiny", action="store_true", help="every run at 2 games per group, quick bench (dry run)")
    ap.add_argument("--root", default=registry.ROOT, help="registry root (datasets/, cache/, runs/)")
    ap.add_argument("--fast-first", action="store_true", help="run the cheapest runs first")
    ap.add_argument("--no-guard", action="store_true", help="with --tiny only: don't stop below the random floor")
    ap.add_argument("--only", nargs="+", metavar="RUN", help="run only these plan rows, at the plan's sizes (Colab)")
    ap.add_argument("--table", action="store_true", help="write the table from the registry's finished runs and exit")
    ap.add_argument("--jobs", type=int, default=1, help="run this many plan rows at once in worker processes")
    ap.add_argument("--free", type=float, default=None,
                    help="size for this many GB of free memory instead of what is free now (workers get the plan's)")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)  # one row of a --jobs sweep
    ap.add_argument("--round0", action="store_true",
                    help="before the night: play the round-0 pool and validation set and train round 0's net, then exit")
    ap.add_argument("--confirm", nargs="+", metavar="CONFIG", help="step A5: not built yet")
    args = ap.parse_args(argv)
    if args.confirm:
        sys.exit("--confirm is learned-play step A5 and isn't built yet")
    if args.no_guard and not args.tiny:
        print("refusing: --no-guard is only for --tiny dry runs; a real sweep always runs with the random-floor guard")
        sys.exit(2)
    if args.table:
        write_table(args.root)
        return
    free = free_gb() if args.free is None else args.free
    rows, before, total = projection(jobs=args.jobs, free=free)
    print_projection(rows, before, total, jobs=args.jobs)
    disk, need = free_disk_gb(args.root), disk_need_gb(rows, args.jobs, args.root)
    print(f"disk: {disk:.1f} GB free, the night needs {need:.1f} GB (caches, exact examples, database, "
          f"{DISK_MARGIN:g} GB margin)")
    if args.plan:
        return
    if args.tiny:
        rows = tiny_rows()
    if args.round0:
        if not args.tiny and round0_peak_gb() > run_budget_gb(1, free) and not args.force:
            print(f"refusing: round 0 peaks ~{round0_peak_gb():.1f} GB, over the {run_budget_gb(1, free):.1f} GB free "
                  f"less the margin; free memory or --force")
            sys.exit(2)
        train_round0(rows, args.root)
        return
    small = rows[0]["n_round"] < MIN_N_ROUND
    if small and not (args.tiny or args.only or args.force):
        print(f"refusing: {free:.1f} GB free sizes rounds at {rows[0]['n_round']} games per group, below the "
              f"smallest worth running ({MIN_N_ROUND}); free memory or --force")
        sys.exit(2)
    if disk < need and not (args.tiny or args.force or args.worker):
        print(f"refusing: {disk:.1f} GB of disk free, the night needs {need:.1f} GB; free disk or --force")
        sys.exit(2)
    if args.only:
        unknown = [n for n in args.only if n not in {r["name"] for r in rows}]
        if unknown:
            print(f"refusing: not in the plan: {', '.join(unknown)}")
            sys.exit(2)
        rows = [r for r in rows if r["name"] in args.only]
        print("only: " + ", ".join(f"{r['name']} ({r['minutes']:.0f} min projected on this machine)" for r in rows))
    elif not args.tiny and total > args.budget and not args.force:
        print(f"refusing: projected {total:.0f} min is over the budget of {args.budget:.0f} min (--force to start anyway)")
        sys.exit(2)
    if args.fast_first:
        rows = fast_first(rows)
        print("order: " + ", ".join(r["name"] for r in rows))
    log = print if args.worker else watched_log(args.root, rows, args.jobs)
    if args.jobs > 1 and not args.worker:
        extra = ["--tiny"] * args.tiny + ["--no-guard"] * args.no_guard + ["--free", repr(free)]
        code = run_parallel(rows, args.root, args.jobs, extra, log=log)
        if code:
            sys.exit(code)
        return
    try:
        run_sweep(rows, args.root, quick=args.tiny, log=log, guard=not args.no_guard, write=not args.worker)
    except GuardStop as e:
        log(f"sweep stopped by the random-floor guard: {e}")
        sys.exit(3)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # progress reaches a redirected log as it happens
    main()
