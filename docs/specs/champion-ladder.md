# Champion ladder with sequential testing

Status: closed (2026-11-02, built 2026-10-30, scripts/ladder.py; no longer ranks nets for the product, decisions "Headline re-rank"; amended by ladder-v2).

Written by the manager (2026-10-30); Next 3, parameters
from `docs/research/big-picture-2026-10-30.md` ("Sequential testing") and
`scripts/analysis/sprt_replay.py`.

**How this moves the goals.** Goal 2 (a Stockfish-strength player) needs
a strength measure that a training-seed fluke can't fake and that costs
minutes, not an evening: fishtest's pattern, one champion that every new
net must beat in paired fights under a sequential test (SPRT). Today every
recipe question is a fixed-size bench run read against a 0.02 bar, two
passes so far were seed luck, and nothing keeps the best net found. With a
ladder, a lucky-good seed becomes the champion we keep, and each later
experiment answers "does this beat the best we have?" with a controlled
false-pass rate. It also serves goal 1: the stop rule requires the held-out
card half not to lose. We'll know it works when the first tests (round-2
retrains against the heuristic) stop in the predicted ~1-6k fights with
verdicts that match the bench (all three nets pass against the heuristic
on train cards; boss_lead and seed-check numbers).

## Outcome

`scripts/ladder.py`: one champion (starting at the heuristic), a `test`
command that plays a candidate against it on fresh paired fights until an
SPRT decides, logs every test, and promotes on a pass; and the first three
tests run.

Non-goals: ensembles as one player (a later spec: a Rust evaluator averaging
nets); several champions per character or per card pool; Silent cells; the
new bosses (`tight_bosses`) in the fight pool; using the ladder inside the
training loop; changing bench sets.

## Behavior

- **Fight pool.** Every tight2 cell in both halves (1,226 cells: hallway,
  elite, boss), with fresh seeds: the cell's first tight2 seed plus
  `LADDER_OFFSET` 5e15 (so 7e15 + ...), plus k for k = 0, 1, 2, .... These
  are disjoint from every bench and calibration range (tight2 2e15,
  silent 3-4e15, bosses 5-6e15 + up to 148 cells x 1e5).
- **Order.** Blocks of `SEEDS_PER_BLOCK` 5 seeds per cell (~6,130 fights);
  block b uses k in [5b, 5b+5). Inside a block, fights are shuffled within
  each stratum (half x fight type, 6 strata) by a seeded RNG, then
  interleaved so every prefix keeps each stratum's share of the block
  within one fight (largest-remainder). The order depends only on the
  block number and `ORDER_SEED`, so two tests see the same fights in the
  same order (comparable, and replayable).
- **Play.** Candidate and champion each play every fight with one-turn
  search (`bench.run_specs`, the agents' settings), in batches of
  `BATCH` 500 fights. A pair's outcome is d = won_cand - won_champ.
- **Test.** Normal-form SPRT as `sprt_replay.sprt_paths`: after n pairs
  with mean m and plug-in variance s2 (floored at 1e-6), LLR = n * d1 / s2
  * (m - d1 / 2); H0 lead <= 0, H1 lead >= d1 (default 0.01); alpha =
  beta = 0.05 (bounds +-2.944); no decision before `MIN_FIGHTS` 200. The
  decision is taken at the first pair, in order, that crosses a bound;
  pairs played past it in the same batch are logged but not counted.
  Cap `--cap` 16,000 pairs: inconclusive, champion kept.
- **Held-out check.** On a pass, the held-out half's lead over the counted
  pairs must be >= -0.005, or the verdict is `pass-held-out-fail` and the
  champion is kept.
- **Promote.** A pass that clears the held-out check makes the candidate
  the champion (`results/ladder/champion.json`: path, since, test id).
  `--no-promote` runs a test without promoting (for screens).
- **Report.** Each test writes `results/ladder/tests/<id>.json` (settings,
  champion and candidate, verdict, stop n, LLR path every 100 pairs, lead
  overall and by half x fight type with cell-clustered intervals, every
  pair's spec index and both outcomes) and appends one summary line to
  `results/ladder/log.jsonl`. It prints the same summary.
- `ladder.py status`: champion, last tests.
- Failure cases: a candidate path that doesn't exist or doesn't load
  fails before any play; a candidate equal to the champion is refused; an
  interrupted test leaves no log line and no promotion (the test file is
  written at the end).

## Fits with

- `bench.run_specs`, `bench.load_evaluator`: used unchanged.
- tight2 (`data/bench/tight2.json`): read only, for cells and first seeds;
  `test_bench.py`'s set hashes pin it.
- `sprt_replay.py`: the ladder's LLR must equal `sprt_paths` on the same
  sequence (new test `test_llr_matches_replay`).
- The job queue: tests are long-ish runs (minutes to ~30 min); they go
  through `jobs.py` like any run.

## When in doubt

Prefer the replay's published parameters over new tuning; prefer a plain
script with JSON files over a database or a service.

## Scope

New `scripts/ladder.py`, `scripts/tests/test_ladder.py`, `results/ladder/`,
a README section, a results section in `docs/research/learned-play-results.md`.
Off limits: the engine, features, nets, training scripts, bench sets and
`bench.py`'s behaviour.

## Decisions taken (provisional, docs/decisions.md)

- Champion starts as the heuristic (the floor); first candidate the
  round-2 retrain seed 1, then seeds 101 and 201 against whoever is
  champion. Alternative: start from the best-measured net directly (skips
  one test but trusts a fixed-size bench pick).
- Pool weights fight types as tight2 does (73% hallway); report by type.
  Alternative: equal weight per type (fewer fights decide hallway, which
  is where nets trail at low HP; the review's calibration used tight2's
  mix, so it stays).
- Ensembles left out (they need a new evaluator).

## Outside assumptions

- The SPRT calibration from `sprt_replay.py` (false-pass 0.03-0.07, median
  stop ~2.9k pairs at H1 0.01) carries to fresh seeds of the same cells.
  Checked by the first tests' stop points (step 3).

## Verification

Tests first (`scripts/tests/test_ladder.py`, run with `python`):
- `test_seeds_fresh`: every ladder seed of blocks 0-2 is outside every seed
  in `data/bench/*.json` sets and calibration ranges; seeds unique.
- `test_order_stratified`: block 0 holds 5 fights per cell; every prefix
  of length n keeps each stratum's count within 1 of n x its share; the
  order is the same on two calls and differs between blocks.
- `test_llr_matches_replay`: on a synthetic +-1/0 sequence, the ladder's
  decision and stop index equal `sprt_replay.sprt_paths`' (MIN_FIGHTS 200).
- `test_identical_players_fail`: a fake player pair with equal outcomes
  stops with a fail at pair 200.
- `test_held_out_rule`: a synthetic pass with held-out lead -0.01 gives
  `pass-held-out-fail` and no promotion; -0.004 promotes.
- `test_end_to_end_small` (cap 600, heuristic vs a tiny contract net in
  `scripts/tests/data/contract/`): writes the test file and a log line,
  in a temporary results folder.

End to end (step 3): the three round-2 retrains through the ladder.

## Don't guard

Concurrent tests writing the same champion file (one manager runs tests,
through the queue); disk space for test files (~1 MB each).

## Build steps

1. `ladder.py` core (pool, order, SPRT stepper, held-out rule, test files,
   promotion, `status`) and the tests above. Check: `test_ladder.py`
   passes; `test_bench.py`'s `test_sets_unchanged` still passes. In-session.
2. README "Champion ladder" section. Check: the command in it runs
   (`ladder.py status`).
3. **Long run** (job queue, 6 threads): `ladder.py test` r2 s1 vs heuristic,
   then r2 s101 and r2 s201 vs the champion. Check: stops near the
   replay's predictions; verdicts and leads by type written into the results
   doc with what they say.

Build plan: 3 steps, in-session, on Opus. No stop points expected.
