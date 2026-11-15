# Luck-corrected labels, step 1 (lane luck-corrected-labels)

Status: closed (2026-11-11, step 1 read failed both reads; decisions "Lane luck-corrected-labels closed"; luck logging kept, step 2 not run).

Charter: `lane/luck-corrected-labels`. This spec covers step 1: the
engine logs each game's luck, and a read measures how much of the label
spread it removes (on training games, 1a) and of a paired read's spread
(on cell sequences, 1b). Step 2 (training on corrected labels) gets its
own spec once 1a passes its fail-fast.

## How it moves the goals, and how we'll know

Goal 1's number is how few games a net needs to learn new content; for a
power that pays past the search horizon (Demon Form's later ticks) that is
1.6k-5k games per group today (`measurement/later-ticks-count@burst5k`).
A training label is the fight's final score, and much of its spread is
luck drawn after the labelled decision. If the correction removes a share
f of the label noise, a burst needs about (1 - f) of the games for the
same signal. Step 1a measures f on the games step 2 would train on; under
50% on Demon Form decks the lane stops there (one cheap read, no
training). Step 1b measures the same correction on paired reads, which
would cut the CPU of goal 1's benches (a read sd ratio at most 0.75 is
filed as a tool either way).

## Outcome

`sts.run` can log, per decision, the luck the game drew after it, and a
dataset of the ycards-net-g1600 recipe's games carries those terms; a
script reports the share of label noise they remove.

Non-goals: training on corrected labels (step 2); two-turn games (the
stepped player runs in Python per turn); luck before the first decision
(no row precedes it).

## Behaviour

**Luck term.** At every chance event after a decision (a draw, which
includes a reshuffle; a monster's move roll; a random target; a random
exhaust; an ally's random block), with V the luck net:

    delta = V(state after the outcome drawn) - mean over outcomes of V(state after it)

"State after" is the state run on to its next decision, next chance
event or the end (what `chance_outcomes` lists and `resolve_chance`
reaches). V is the raw luck net (no prices) on a running state and the
engine's `score()` on a finished one. The mean is exact (probability
weighted) over the listed outcomes when there are at most `luck_limit`
(default 64) distinct ones; otherwise it is the plain mean of
`luck_samples` (default 16) outcomes sampled with an RNG of the logger's
own, seeded from the game's seed, so it never touches the game's RNG.
Either way E[delta | everything before the event] = 0 for any V, so a
corrected label keeps the label's expectation.

**Per decision.** `luck[i]` is the sum of delta over the events between
decision i's action and decision i+1 (or the end). A row labelled at
decision i (its state, or the paused state its divergent option reached)
gets the corrected label `score - sum(luck[i:])`.

**The game is unchanged.** Logging uses only clones and its own RNG, so a
game with `luck=` plays the same actions to the same result as without.

**sts.run(..., luck=<NetEvaluator>, luck_limit=64, luck_samples=16):**
every result dict gets `luck`, one float per decision (recorded or not).
`luck` with a priced evaluator or a score rule other than the engine's,
or with `forced`, raises.

**Dataset (1a).** `two_turn_games.dataset(..., luck=<player>)` (one-turn
depth only) passes the luck net and stores `luck` in each record; the
config gains `"luck": {"net": <player>, "limit": 64, "samples": 16}` only
when given, so existing datasets still match. `registry.replay` passes
`luck` through.

**Read (1a): `scripts/analysis/luck_share.py`.** Builds (or reuses) the
dataset of the ycards-net-g1600 recipe (one-turn games by the 10-29 net
@hpb0.01 on held-out decks, game seed 51, 1600 games per group) with the
10-29 net as the luck net; samples rows as `selfplay.sample_states` does
(6 decisions a game plus their paused states, seed fixed); for each row
takes the raw label y, the corrected label c and the luck net's own value
v of the row's state; and reports, per slice (Demon Form decks, other
decks; elite, boss; all):
- `noise_share` = (Var(y) - Var(c)) / the label noise variance: the
  share of label noise removed. Var(y) - Var(c) is the noise variance
  removed (each luck term has mean 0 given the state, so it is
  uncorrelated with the state's true value). The noise variance,
  E[Var(y | state)], is measured directly: 600 rows per deck slice (one
  per game, Demon Form decks and other decks) are each played on 8 times
  from their state with fresh chance seeds by the same player
  (`sts.play_on`). **The fail-fast reads this one** (decision below);
- `bound_share` = (Var(y) - Var(c)) / mean((y - v)^2), a lower bound
  needing no replays (mean((y - v)^2) is at least the noise variance for
  any v; in the smoke run half of it was the net's own error);
- `label_share` = 1 - Var(c) / Var(y), the charter's words read literally
  (it also counts the spread of the states' true values, which no
  correction removes);
- n rows, n games, and se of each share by bootstrap over games (and over
  replayed rows for the noise variance).
It writes `results/luck/luck-share-g1600.json` and prints a table.
Pass (step 2 runs): `noise_share` on Demon Form decks >= 0.50.

**Read (1b), built after 1a's job is queued:** the gauntlet's floor
results carry each fight's summed luck in HP units (100 x the score-unit
sum: one score unit is 100 HP of a won fight); a sequence's corrected
end-HP is its end-HP minus its fights' sum; the paired sd of corrected
minus the paired sd of raw on 100 one-turn cell sequences (net1029-hpb0.01
against net1029-hpb0.01-tsl1). Its details go in an amendment here.

## Fits with

- `runner::play`/`play_from`/`play_many`, `sts.run` without `luck`: bit
  for bit unchanged (every series check and the golden file); pinned by the
  existing suites and `series_check`.
- Datasets without `luck`: their configs and records unchanged; pinned by
  `scripts/tests/test_two_turn_games.py` (existing).
- A game played with `luck=` equals the plain game (actions, score):
  new test `luck_game_matches_plain` (Rust) and
  `test_run_luck_same_game` (Python).

## When in doubt

Prefer an unbiased term with more variance over a lower-variance term
with any bias.

## Scope

May change: `engine/src/runner.rs` (a luck-logging play path and the
result's `luck` field), `engine/src/chance.rs` (helpers only), `py/src/lib.rs`
(`run`'s `luck`, `luck_limit`, `luck_samples`), `scripts/two_turn_games.py`,
`scripts/registry.py` (records and replay pass `luck`),
`scripts/analysis/luck_share.py` (new), tests, this spec, results docs.
Off limits: the search, the net, features, existing dataset formats and
any default behaviour.

## Decisions (on the owner's behalf; also in docs/decisions.md)

- V is the luck net on the post-event state, not the agent's root search
  value: decision states (post-draw) and paused states are the net's own
  training rows, so it is in range; a root search per outcome would cost
  a search per listed outcome (tens per draw), over ten times the games.
- The fail-fast reads `noise_share`, not `label_share`: the charter's
  mechanism ("a burst needs 1-f of the games") is about label noise, and
  `label_share` would also count the spread of true values across
  states; its denominator is the replayed noise variance, not the
  residual around the net's value (which also holds the net's error, half
  of it in the smoke run). All three are reported. Reversible: the read
  prints all three.
- `luck_limit` 64 and `luck_samples` 16 are defaults to measure, not
  settings to choose (sampled means stay unbiased).

## Verification

Rust (`engine/src/runner.rs` tests):
- `luck_game_matches_plain`: a search game with luck logging and the
  same game without have equal trajectories and scores (3 seeds, a deck
  with a draw card).
- `luck_listed_event_has_zero_mean`: at a state with a pending listed
  event, sum over outcomes of p x delta(outcome) is 0 (to 1e-9), and the
  drawn outcome is one of the listed states.
- `luck_constant_value_is_zero_while_running`: with a constant evaluator
  every delta of an event whose outcomes all run on is 0.
Python (`py/tests` or `scripts/tests`): `test_run_luck_same_game`: same
actions and score with and without `luck=`, `len(luck) == len(actions)`.
End to end: `luck_share.py --games 20` on a smoke dataset prints the table
with finite shares.

## Don't guard

Two-turn games, forced openings, relic packs in the luck path beyond what
`sts.run` already supports.

## Build steps

1. Engine luck path (runner.rs, chance.rs helpers) and its Rust tests.
2. `sts.run(luck=...)` and the Python test.
3. Dataset `luck` (two_turn_games, registry) and `luck_share.py`; smoke
   run. Then queue the 1a job (long run: about 3200 one-turn games, about
   2-3 thread-h) with its read rule.
4. (1b, after 1a is queued) gauntlet luck columns: an amendment.

Build plan: 4 steps, in-session, on Opus.

## Amendment 1: step 1b as built (2026-11-11)

Under charter rev 2 the read-sd ratio is step 1's main result and the
lane's go (ratio at most 0.75). `scripts/analysis/luck_read.py` plays the
first 100 one-turn cell sequences (`gauntlet.sequences`, `gauntlet.run`,
the cell gauntlet's defaults) for net1029-hpb0.01 and net1029-hpb0.01-tsl1
through `bench.run_specs` with `sts.run`'s `luck` (the unpriced 10-29 net,
step 1a's limit 64 and 16 samples), and stops if any sequence's floors
differ from the player's gauntlet file (luck logging leaves the games
unchanged). Corrected end HP = end HP - 100 x the sequence's summed luck
(all its fights' decisions); the ratio is the paired sd of corrected over
raw, its se by bootstrap over sequences (2000 draws). Also reported,
descriptive: each player's unpaired end-HP sd raw and corrected, and the
paired sds where one player died against where both cleared. The gauntlet
files and `gauntlet.py` are not changed: opt-in luck columns there follow
only on a pass. Output `results/luck/luck-read-cells.json`.
