# learn-memory (lane `lane/learn-memory`)

Goal: a from-scratch `learn.py` run on 40k games per group fits beside the
sessions (peak 3.5 GB or less), same examples, minutes per round within
15%.

## Step 1: where the 40k-game peak comes from (read, no CPU; 2026-11-09)

The charter's premise is out of date. Its "1.25 GB + 12.8 KB per example
while concatenating the training set" is curriculum step 7's model
(decisions "Memory (step 7 ...)", 2026-10-27, before Amendment 1). Since
Amendment 1 (`aa7f9e5`, the same day) `learn.training_set` returns a
`stsnet.DatasetView` over the memory-mapped feature caches: per example
it holds only indices, labels and weights. The model in code
(`sweep.py`, `TRAIN_BASE_GB` 1.43 + `PEAK_BYTES` 200 per example) and the
measured rounds (`scripts/tests/data/memprobe.json`, `runs`) put training
at 1.07-1.51 GB up to 502k examples. Round 0 of `allcontent40k` trains on
about 417k examples (815 batches of 512, `logs/jobs/0583-learn.log`): its
training phase should sit near 1.5 GB, not 6. So the stop rule of step 1
("the cache's stored form can't be trained from without a full decode")
does not apply: it already is trained from without a decode.

What does grow with the pool is round 0's self-play. `registry.selfplay`
held every game's results (actions and per-decision option values as
Python objects) in one list, then built a second list of JSON-able records
from them, and only then wrote the dataset. In `memprobe.json` the pool's
phases grow with its size: self-play 1.49 GB at 9,000 games, 2.29 at
24,000; the write 1.73 and 2.96 GB (about 80 KB per game). 0583's pool is
120,000 games (40,000 per group), played inside the job (its log:
"dataset 3fb9b7e51fe2 (train, round 0): 120000 games, 762s"), and the job
peaked at 6.03 GB (`jobs/done/0583-learn.json`). The pool is the
suspect; the other phases are bounded (cache build streams in 500-game
chunks, <= 1.79 GB; tight fights <= 2.0; the solve step is off with
`solve_games0` 0).

Step 2 is therefore the pool, not the training set: `selfplay(...,
keep_results=False)` (what `learn.dataset` now asks for) plays a chunk of
200 games, turns it into records and writes them to the gzip file at
once, hashing the same lines on the way; the folder is renamed to the
dataset id at the end. Same bytes and id as before
(`test_streamed_selfplay_writes_the_same_dataset`). Rounds >= 1 with
branches keep the old path (their main games' results pick the branch
points; 1,048 games per group).

## Step 3/4: the measurement

`scripts/memprobe.py --config configs/allcontent40k-s101.json --n0 40000
--epochs 1` runs round 0 of the real config (validation set, the
120,000-game pool, labels, the training set with round 0's 0.5 sample and
the exact examples from a copy of `db/train.sqlite`, one epoch) with
every phase's peak commit sampled. Because the pool's config and rules
version (7042d1d6a6149ba0) equal 0583's, the probe's pool must have the
same `games_sha256` as `datasets/3fb9b7e51fe2`: the same examples, so
the same nets, without a second learn (the charter's "5k-game learn with
and without": not needed when the data are byte-identical).

## Step 3/4 read: 0732-memprobe (2026-11-09)

`jobs/done/0732-memprobe.json` (round 0 of `allcontent40k-s101` at
40,000 games per group, one epoch, pinned af91db3, 26 minutes):

- **Same examples.** The pool `2358a3d3825a` has `games_sha256`
  dc3ed9ec... (120,000 games, rules version 7042d1d6a6149ba0), equal to
  `datasets/3fb9b7e51fe2`'s from 0583: the streamed write produces the
  same bytes, so the training set and the net are today's.
- **Peak commit by phase** (GB, `memprobe.json` and its samples): pool
  (play + write) 0.92 (before step 2 the pool held its games twice; at
  24,000 games it already took 2.96), training set 0.87, training 1.01,
  and the **solve step 3.72**: the run's peak, over the 3.5 GB bar, in a
  step that solves 0 games (`solve_games0` 0) and took 43 s.
- **Why the solve step.** `puzzles.dataset_games(ds, limit)` called
  `registry.load_games`, which decodes the whole pool into a list, and
  only then cut it to `limit`, so a 0-game solve step held all 120,000
  games at once (0583's log shows the same 33 s "0 games" step). Fixed:
  it reads `registry.iter_games` and stops at the limit, same output
  (`test_dataset_games_decodes_only_its_limit`). Re-measured by hand on
  the probe's pool with the fix: the solve step takes 0.0 s and the
  process peaks at 0.25 GB commit. Round 0's peak at 40k games is
  therefore the training phase's **1.01 GB** commit.
- **Working set against commit.** The job runner recorded `peak_gb`
  6.06, and the samples show a 6.52 GB working set during training while
  commit stays at 1.01. The difference is the memory-mapped feature cache
  (`cache/2358a3d3825a-...`, 7.9 GB on disk; round 0 samples half of it):
  file-backed pages that Windows drops under pressure and reads back,
  not memory that would push other processes into the page file. So the
  runner's `peak_gb` (working set of the job's tree) overstates what a
  learn needs; 0583's 6.03 GB, the number this lane started from, was
  measured the same way and was probably part mapped cache. A learn's
  `mem_gb` can be set from commit (about 1.5 GB at 40k games); with
  little free memory an epoch reads the cache from disk instead of RAM,
  which costs minutes, not paging.
- **Minutes.** The pool played in 813 s on 4 threads against 0583's 762 s
  on 6 (fewer thread-seconds per game); the solve step drops from 33-43 s
  to 0; the training code is unchanged (the change touches only the
  pool's write and the solve step's read), so minutes per round are not
  slower. No second learn was run: the data are byte-identical, so the
  nets are the same (the charter's "nets level" holds by construction).

Checkpoint `peak-40k` passed: peak commit 1.01 GB (3.5 GB bar) and the
same `games_sha256`. The lane's stop rule reads go.
