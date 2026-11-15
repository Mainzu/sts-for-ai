# Random-world bench: the world sampler and its paired read (lane step 2)

Status: closed (2026-11-09, built 2a3cc033, scripts/analysis/random_world.py; pilot read in docs/research/random-world-bench.md; decisions "Lane random-world-bench closed").

**Outcome:** a queued, resumable job plays worlds of k generated enemy
mechanics stacked on the official Act 1 elites, and a read job says, per
k, whether their cost to the net beyond the heuristic adds up or
compounds, against the sum of the same items' single costs on the same
starts and seeds.

**How it moves goal 1, and how we'll know.** Goal 1 is play on randomly
generated content; every bench so far holds one novelty at a time, so the
per-mechanic numbers say nothing about a fight with several. If costs add
(g below 0 at 2 se at every k), goal 1's random-content cost is the sum of
per-mechanic costs and the per-mechanic benches and bursts extrapolate; if
they compound at k 4 or 8 (g above 0 at 2 se), random content breaks the
design and the next work is there. The read job's table says which.

Non-goals: card items (they join after their singles are measured on these
starts and seeds; decisions "random-world-bench: paired read on the
singles"); the adapted column (charter step 5); two turns deep; bosses.

## Behaviour

`scripts/analysis/random_world.py`:

- `play --worlds N --ks 2,4,8 --starts 50 --seeds 4 --threads T --out
  results/mutate/rw-pilot.json` (base file `results/mutate/gen-enemies-b1.json`,
  `--base` to change). For world w (0..N-1): the items are the first k of a
  permutation of the 21-mechanic pool (the 24 generated mechanics minus
  OppCard-Weak, OppCard-Vulnerable and AttackLoss-Vulnerable) drawn with
  `default_rng([20261109, w])`, so k 2 is inside k 4 inside k 8. Its starts:
  the base file's elite starts whose predicted net loss (parent loss + the
  items' summed raw single costs, 16-seed means) is below the start HP,
  permuted by `default_rng([20261109, w, k])`, the first `--starts`; fewer
  eligible than `--starts`: all of them, recorded. Each start plays the
  variant with all k items' patches (`mutate_monsters.variant`, every
  living monster) on the start's first `--seeds` bench seeds
  (`default_rng([20261103, i, floor])`), heuristic and the base file's net
  @hpb0.01. The gen pack's hash must equal the base file's (else exit with
  the two hashes). The file is written after each (world, k); a rerun skips
  finished (world, k) cells, so the job is `--resumable`. `--side` adds
  worlds drawn from all 24 mechanics (world ids offset by 1000, its own
  rows).
- `read <file> [--check]`: per k (main pool; side pool apart), over
  worlds: mean and se of cost_w (net HP-lost change from the parent minus
  the heuristic's, per start and seed, from the parent rows in the base
  file), of S_w (the items' single costs on the same starts and seeds,
  from the base file), of the interaction cost_w - S_w and of g_w =
  cost_w - 1.5 S_w; the ratio mean cost / mean S; deaths per k (net and
  heuristic, world and summed-singles prediction). Verdict per the
  charter's stop rule: **go** if g > 2 se at k 4 or 8; **additive** if
  g < -2 se at every k; else **open**. Writes the table to
  `results/mutate/<stem>-table.md` with `--write`. `--check` exits 0 when the
  verdict is go or additive and every k has at least 10 worlds, 1 otherwise
  (the decisive read's check).
- `check --starts 3`: replays the parent and one single on the first
  starts of world 0 at the play settings and exits 1 unless they equal the
  base file's results (the pairing's precondition).

Edge cases: a world whose item set has fewer eligible starts than 10 is
kept but flagged in the table; a k larger than the pool exits with the
pool size.

## Fits with

- `mutate_monsters.py`: used, not changed (`variant`, `start_state`,
  `play_variants`, `GEN`, `gen_pack`, `PLAYERS`); `test_mutate_monsters.py`
  keeps passing.
- `results/mutate/gen-enemies-b1.json`: read only.
- The job queue: plain `jobs.py add --resumable`; no change to `jobs.py`
  or `family.py`.

**When in doubt:** prefer recording more per world (items, starts, raw
results) over computing in `play`; the read derives everything.

## Scope

May change: `scripts/analysis/random_world.py` (new),
`scripts/tests/test_random_world.py` (new), this lane's results doc,
`docs/decisions.md`. Off limits: the engine, `mutate_monsters.py`,
`family.py`, `jobs.py`, the base file.

## Decisions taken

- A standalone script instead of a `family.py` family: a family is built
  around burst nets and their reads; this bench has no burst until
  step 5, and a resumable job with a read `--check` gives the same
  session-free table (decisions "random-world-bench: sampler as a
  standalone script").

## Outside assumptions

- The engine replays the base file's games bit-identically (checked
  2026-11-09 on 6 starts, parent and GE-OppCard-Damage, both players: 0
  mismatches); `check` re-tests it before each pilot.

## Verification

Tests (`scripts/tests/test_random_world.py`, no engine play):
- `test_items_nested`: world 3's k 2 items are the first 2 of its k 4, those
  the first 4 of its k 8; no collapse mechanic in the main pool; side
  worlds may hold them.
- `test_items_deterministic`: same world id, same items across calls.
- `test_eligible_starts`: on a toy base (3 starts, hp 50; parent loss 10;
  raw single costs 35 and 10 on start 0, 1 and 1 on the others), items
  {a, b} keep starts 1, 2 and drop start 0.
- `test_read_additive_and_go`: toy worlds where cost_w = S_w read
  additive with g < 0; cost_w = 2 S_w read go at k 4; mixed noise reads
  open; `--check` exit codes follow.
End to end: `check --starts 3` exits 0; `play --worlds 2 --ks 2 --starts 3
--seeds 2` then `read` prints a table with 2 worlds at k 2.

Don't guard: base file layout changes (one fixed file); thread counts.

## Build steps

1. Tests and pure parts (items, eligible starts, read math, verdict); check:
   the tests pass.
2. `play` and `check` on the engine; check: the end-to-end commands above.
3. Queue the pilot (20 worlds, k 2/4/8, side 10 worlds) and its read with
   `--check` (charter step 3; about 0.6 thread-h main, 0.3 side).
