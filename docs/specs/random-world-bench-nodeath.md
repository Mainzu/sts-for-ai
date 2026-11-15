# Random-world bench step 4: worlds in no-death mode (lane random-world-bench)

Status: closed (2026-11-09, built 77c28299; read: less than additive; decisions "Lane random-world-bench closed"; kb measurement/random-world@nodeath).

**Outcome:** a queued, resumable job plays the parent fight, every
generated mechanic alone and the k-item worlds on one shared set of
official Act 1 elite starts in the engine's no-death mode, where HP lost
is never capped; its read job gives the charter's verdict (go, additive or
open) per k without the HP cap deciding it.

**How it moves goal 1, and how we'll know.** The pilot (docs/research/random-world-bench.md,
"Step 3") showed raw costs compound for both players (+30% at k 8) but
could not say whether the net's cost beyond the heuristic does: dead
fights cap HP lost, which biased the read toward additive, and capping the
prediction biases it toward go. With no cap the paired read is unbiased.
If the cost beyond the heuristic compounds at k 4 or 8, random content
breaks the net in a way the per-mechanic benches can't see and goal 1's
next work is there; if it adds up, the per-mechanic benches and bursts
extrapolate to random worlds. The read's table says which.

Non-goals: card items; the adapted column (charter step 5); real-play
deaths (no-death play is a measuring device: the players minimise HP
lost without a death cliff).

## Behaviour

`scripts/analysis/random_world.py`, two new subcommands (the pilot's
`play`, `read` and `check` stay):

- `nd-play --worlds N --ks 2,4,8 --side M --starts 50 --seeds 4 --threads
  T --out results/mutate/rw-nodeath.json`: starts are the first `--starts`
  of the base file's elite rows permuted by `default_rng([20261109, 4])`
  (no eligibility filter: nothing caps). Each start is built as
  `mutate_monsters.start_state` does, with `no_death=True`, on its first
  `--seeds` bench seeds (as the pilot). Cells, in order: the parent (no
  items), each of the 24 generated mechanics alone, then the worlds (items
  as the pilot's `items(w, k, pool)`: main worlds 0..N-1 on the 21-mechanic
  pool, side worlds 1000.. on all 24). Each cell plays the heuristic and
  the base file's net @hpb0.01 and stores `[won, hp_end]` per start and
  seed (`hp_end` may be below 0). The file is written after each cell; a
  rerun skips finished cells (`--resumable`). Gen pack hash checked against
  the base file's.
- `nd-read <file> [--write] [--check]`: per world, per start and seed,
  cost = (net loss - net parent loss) - (heuristic loss - heuristic parent
  loss), loss = start HP - hp_end, from the file's own parent; S = the same
  summed over the world's items' single cells. Same table, g, verdict and
  `--check` rule as `read` (go if g > 2 se at k 4 or 8; additive if g <
  -2 se at every k; else open; check passes on go or additive with at
  least 10 worlds per k), plus per k the share of games ending at or below
  0 HP (net / heuristic) and of turn-limit losses. Writes
  `results/mutate/<stem>-table.md` with `--write`.

Edge cases: a turn-limit loss (`won` false) keeps its HP lost and is
counted; a k larger than the pool exits with the pool size.

## Decisions taken

Decisions "random-world-bench: no-death worlds for step 4".

## Verification

- `test_nd_world_stats`: toy file where each single costs the net 2 HP
  more than the heuristic and the world costs the sum: interaction 0;
  world at twice the sum reads g > 0.
- `test_nd_resume`: a cell already in the file isn't replayed (plan
  minus done).
- Real: `nd-play --worlds 1 --ks 2 --starts 2 --seeds 2` runs, a second
  run plays nothing, `nd-read` prints a table; a no-death game can end
  below 0 HP (checked on the run's k 2 or a forced low start HP).

## Build steps

1. Code and tests; check: tests pass, the small real run as above.
2. Queue `nd-play` (40 main worlds, 10 side, k 2/4/8, 50 starts x 4 seeds)
   and `nd-read --write --check`.
