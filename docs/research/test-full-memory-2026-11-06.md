# test-full-memory: what held the suite's memory (2026-11-06)

Lane `lane/test-full-memory`. The suite run file by file (0206) passed but
peaked at 8.5-9.3 GB in three files; per-test job 0208 reserved 9.5 GB and
never started beside ~3 GB free.

## Per-test peaks (job 0295)

`test_full.py --cap-gb 1.7 --per-test` on the three files (each test in its
own process, killed at 1.7 GB; jobs/done/0295-test-full.json, its log's
table). Over the cap:

| test | peak before kill | time |
|---|---|---|
| test_solve::test_solve_matches_brute_force | 2.21 GB | 0.1 min |
| test_exact_only::test_exact_only_arms | 1.76 GB | 6.4 min |
| test_curriculum::test_exact_split | 1.72 GB | 4.0 min |
| test_curriculum::test_exact_share | 1.71 GB | 3.9 min |

Under it: test_solve's other two at 1.44-1.48 GB, every other test at
0.56 GB or less. A file's peak (8-9 GB) is far above its tests' peaks: one
process keeps each test's fixtures and the allocator's freed memory, so the
per-test numbers, not the file numbers, say what to cut.

## Why

- **The curriculum fixture database (test_exact_only, test_curriculum).**
  `fill_db` solves 110 roots at 20k nodes with every solved state kept
  (`min_nodes=0`). Only 36 roots solve, but a failed solve still stores the
  subtrees it finished: the database held 380,605 decision rows, 37,163 of
  them from the solved roots. The exact tests then build examples from all
  rows (cap 10^9, or every id): ~800k `Combat` states (1.3 KB each) plus
  their features. The fixture alone was small (0.22 GB): the examples made
  the peak.
- **The solver's table (test_solve).** One failing 50k-node solve on a
  tail position took the process from 0.28 to 1.42 GB; the same state at
  5k / 20k nodes adds 0.06 / 0.42 GB: about 21 KB per node. The recorded
  game set (all 1160 tight specs) is only ~0.1 GB. `tails()` solves at
  50k nodes, the brute force runs 8 solves at once at 100k nodes.

## Changes (checks unchanged)

- `fill_db` stores a root only when it solves within `max_nodes` (same 36
  roots, 37k rows, fixture 18 s instead of 66 s).
- test_solve: `TAIL_NODES` 50k -> 20k; brute force 100k -> 5k nodes (still
  30 tiny cases).

Per test at `--cap-gb 1.5`, all pass: exact_only_arms 0.80 GB (0.5 min),
exact_split 0.92, exact_share 0.64, brute force 1.07, groups_like_search
0.74, store_and_db 0.72.

## What it changes beyond the tests

21 KB per solver node is large: a solve step at 1M nodes would need ~20 GB
if it ran to its budget. Not measured here: how close the training
rounds' solve steps (`learn.solve_step`, `puzzles.find`) and other solver
users run to their budgets; if they do, their memory, not only their time,
limits running them beside other jobs. Fact `measurement/solver-memory-per-node`.

Next: job 0303, the full suite from this commit (stop check: exit 0 with
the max peak under 4 GB).

## The full suite after the cuts (job 0303, 2026-11-07)

`jobs/done/0303-test-full.json`, log `logs/jobs/0303-test-full.log`, pin
adce563, 4 threads, 2.2 GB reserved; it started at once beside the role
sessions (0208, at 9.5 GB, never did).

- Peak: max 1.77 GB (test_ladder), then test_puzzles 1.69, test_survival_score
  1.20, test_sweep 1.18; the former holders test_solve 1.08, test_curriculum
  1.08, test_exact_only 0.80 GB (0206: 8.3-9.3 GB). test_rounds 2.09 -> 0.96 GB.
  Against the goal's 9.8 GB: under the 4 GB done bar by a wide margin.
- Wall time 169 min (0206: 145, estimate 130). Slower per file, not more
  work: test_rounds 19.2 -> 30.8 min, test_branches 7.4 -> 17.2, test_sweep
  46 -> 53, while 0278 (3 threads) and the yardstick-cards bursts ran
  beside it; 0206 ran on a quieter machine. test_sweep is 53 of the 169
  minutes and now leaves the default run (below): about 116 min.
- Exit 1, both in test_jobs.py, neither about memory:
  - `test_pin` expected `runs/index.csv` skip-worktree in a snapshot; since
    b68ac7b (06 Nov, after 0206's pin) the real `.gitignore` the test copies
    ignores that file, so the scratch repo never tracks it. A stale
    expectation; fixed (c80a395), test passes.
  - `test_idle_gate` (before 5.89 idle cores, during 4.16, needs a drop of
    3): four busy-loop processes took only 1.7 cores, because the machine
    was already loaded (0278, 0304 and the suite's own pytest). It measures
    the machine, not the code; it passed in 0206. Left as is: it fails only
    beside other heavy load, and a load-aware version would test less.

Changes at the close: `scripts/test_full.py` leaves `test_sweep.py` out of
the default run (`NOT_DEFAULT`; decisions "test_sweep out of the default
test set", 2026-11-01), runnable with `--per-test` or pytest by hand. The
filler line's `--mem-gb 4` can come down to 2.5 (max 1.77 + margin): the
steward's file, told in `jobs/roles.log`.
