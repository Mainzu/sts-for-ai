# Ladder v2: cached champion, fresh blocks per test, fixed-n leads, run-HP mode

Status: closed (2026-11-01, built with amendment 1; ladder promotions stopped 2026-11-02, decisions "Next re-ranked from the approach review (owner away, 2026-11-02)").

## Outcome

Make the ladder's numbers trustworthy and cheaper, and add a second
yardstick that scores HP lost at run-like starting HP, so product
candidates (including two-turn players later) can be judged on what wins
runs, not only on near-death survival.

How it moves the goals: goal 2's product test is the ladder. Today every
test replays the champion on the same first fights (tests 0002-0020 share
one 500-pair prefix where the champion wins 0.544 vs 0.521 long-run), and
leads are read where the SPRT stopped, which inflates them. Caching the
champion halves a test's CPU, fresh blocks remove the shared draw, and a
fixed-n lead gives an unbiased size. The run-HP mode answers the review's
top open question: does the champion lose more HP than the heuristic at
real HP? We'll know from two reads: replaying test 0004 to 6,000 pairs on
fresh blocks (does its -0.026 shrink toward -0.01?), and the run-HP first
check (rule below).

Non-goals: the informative fight book (later), two-turn ladder play,
changing the SPRT's d1, floor or promotion rule, re-reading old tests.

## Behaviour

1. **Champion cache.** The champion side's outcomes are deterministic
   (verified: identical across tests 0002-0020). `run_test` keeps them in
   `<root>/cache/<key>.json`, key = sha256 of (player identity, sts module
   file sha256, search limit, mode). Player identity: "heuristic", or each
   net file's sha256 (ensembles: the joined list). Entries are by seed:
   `[won, hp_start, hp_end]`. A batch plays the champion only on seeds
   missing from the cache; the file is rewritten (temp file + rename)
   after each batch. Candidates are never cached. A rebuilt `sts` module
   misses the cache (safe).
2. **Block offset per test.** A test's id is reserved when it starts (an
   exclusive `tests/<id>.pending` file, removed at the end; a crashed test
   leaves its id unused). Its first block is `(id - 1) x BLOCKS_PER_TEST`
   (4 blocks; one block is 6,130 fights, the cap 16,000 needs 3).
   `--start-block` overrides. Test 0001 in an empty root still starts at
   block 0, so the existing tests' fixtures keep their seeds. A block whose
   seed offset k would reach 100,000 (the cell seed spacing) raises.
   Old test files stay readable: missing new fields read as absent.
3. **Fixed-n continuation.** `--fixed-n N`: after the SPRT decides (or
   caps), play on to N pairs. Extra pairs are recorded with `counted:
   false`; the SPRT verdict, promotion and `lead` use counted pairs as
   now. The record gains `fixed: {n, lead, by_half, by_type}` over the
   first N pairs, and `report` prints it. Without the flag nothing
   changes.
4. **Run-HP mode.** `ladder.py runhp <candidate> [--against heuristic]
   --pairs N`: same cells, fresh seeds (blocks from `RUNHP_BLOCK0` = 6,000
   on, 4 per run-HP id, ids in `<root>/runhp/`), start HP drawn per seed:
   hallways 70-100% of max HP, elites and bosses 40-100% (uniform,
   integer, from a generator seeded by the fight's seed). Each player's HP
   lost per fight = hp_start - hp_end on a win, hp_start + 30 on a loss.
   Pair score = opponent's HP lost - candidate's HP lost (positive: the
   candidate is better). No SPRT, no promotion. Writes
   `<root>/runhp/<id>.json` (every pair) and a line to
   `<root>/runhp/log.jsonl`. Report: mean pair score with a cell-clustered
   95% interval, by half, by type and both; each player's mean HP lost and
   win rate; the win-lead; the paired sd of the score and the correlation
   between the two players' HP lost. The opponent's results use the cache.

## Fits with

- Existing `test_ladder.py` tests pass unchanged (seeds, order, SPRT,
  floor, held-out rule, refusals, end to end).
- `results/ladder/champion.json`, `log.jsonl` and `tests/*.json` keep their
  formats (fields only added). `ladder.py status` reads old lines.
- `bench.run_specs` / `load_evaluator`: used, not changed.
- README "Champion ladder" lines updated for the new flags and mode.

## When in doubt

Prefer leaving the SPRT path exactly as it is over sharing code with the
run-HP mode.

## Scope

May change: `scripts/ladder.py`, `scripts/tests/test_ladder.py`, README's
ladder section, this spec, decisions. Off limits: `bench.py`, engine,
`bench_sets.py`, the tight2 bench file, champion promotion rules.

## Decisions taken

- HP bands 70-100% hallways, 40-100% elites/bosses; death penalty 30 HP
  (review's proposal). Tunable constants, reported in each record.
- Run-HP is fixed-n, not sequential: its question is a size, not a
  pass/fail.
- Cache keyed on the sts module's file hash, not the rules fingerprint:
  the heuristic's agent code isn't in the rules fingerprint.

## Outside assumptions

- Engine play is deterministic per (spec, player, limit) regardless of
  thread count and batch: checked by the cache test playing a block twice.

## Verification

1. `test_start_block`: ids 1 / 2 / 21 start at blocks 0 / 4 / 80; seeds of
   two tests' first blocks are disjoint; k >= 100,000 raises.
2. `test_champion_cache`: two fake-play tests with the same start block:
   the second never calls play for the champion, outcomes equal; a cached
   real-play block of 30 fights equals fresh play (determinism, 2 threads).
3. `test_fixed_n`: a fake play that decides in < 1,000 pairs with
   `fixed_n=1500`: 1,500 pairs recorded, counted equals the SPRT's n,
   `fixed.lead` equals the hand mean of the first 1,500.
4. `test_old_record_report`: `report` on a record without `fixed` works.
5. `test_runhp_draw_and_score`: draw bands per group, deterministic per
   seed; HP lost and pair score on hand cases (win 50->40 = 10, loss from
   50 = 80).
6. `test_runhp_fake`: a fake-play run of 300 pairs writes its file and
   log line and reports clustered intervals.
7. End to end: `runhp` with the champion vs the heuristic, 120 pairs, 2
   threads.

Don't guard: concurrent writers of one cache file (last write wins; the
entries are identical), cache files edited by hand.

## Build steps

1. Tests 1, 4 and the old suite on unchanged code (1 fails until step 2);
   id reservation and start block.
2. Champion cache (test 2).
3. Fixed-n continuation (test 3).
4. Run-HP mode (tests 5-7), README.

Build plan: 4 steps, in-session (this fork), on Opus. No stop points.

## Amendment 1 (2026-11-01): slots, and shared run-HP fights

Found in self-review after step 4: with a fresh first block for every id,
no two tests ever play the same champion fights, so the cache would never
be hit; and run-HP candidates on different blocks can't be compared with
each other. Changes:
- Ladder tests rotate over 8 slots: first block = ((id - 1) mod 8) x 4
  (`LADDER_SLOTS`). Consecutive tests use different draws; after 8 tests
  the champion's results for every slot are cached. Test
  `test_start_block`: ids 1 / 2 / 9 / 21 start at 0 / 4 / 0 / 16.
- Every run-HP run starts at block `RUNHP_BLOCK0` (no id offset), so all
  candidates play the same fights and the opponent is played once. Test
  `test_runhp_fake`: a second run never plays the opponent and scores the
  same.
