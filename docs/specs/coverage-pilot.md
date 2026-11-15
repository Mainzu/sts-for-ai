# Coverage pilot (confirmed, 2026-10-30)

Status: closed (2026-10-31, read: decisions "Coverage pilot read").

## Why (goal 1)

Goal 1 is play on content the net never trained on. The big-picture
review's open question: does held-out play scale with how much content
training covers? If it does, generated content (runtime registry +
generated cards, with new mechanics) moves ahead of the fidelity specs in
the queue; if the curve is flat, more training content won't buy goal 1
and the effort goes to features and search instead. We'll know from the
held-out half's lead over the heuristic on tight2 fights, per fight type,
as the training pool grows from 4 to 10 to all 21 non-starter card kinds.

## Outcome and non-goals

Outcome: a three-point curve (3 seeds each) of held-out lead against
training card kinds. Non-goals: generated cards, mechanic-removal arms
(next, if the curve isn't flat), Silent transfer, new metrics.

## Behaviour

- Config key `train_pool`: base card names; training decks (every round)
  draw their 3-15 extra cards from those kinds and their upgrades only
  (`selfplay.pool_deck`). Validation keeps the full pool. The key enters
  the training dataset's config, so pools never mix.
- Configs `configs/cover{4,10,21}-s{1,101,201}.json`: the lean config
  (no solve step) with a fresh 5,000-per-group round-0 pool (`train_seed`
  1000 + seed), round 1 self-play, judged at round 1. Starter kinds
  (Strike, Defend, Bash) are always in; the other kinds are a random
  subset per seed (seeded in the config writer; listed in each config).
  The subset changes with the seed, so seed sd includes subset luck: that
  is the effect we want (coverage in expectation, not one lucky subset).
- Fewer kinds means each kind is seen more often (same games): the pilot
  asks breadth against depth at fixed data.

## Fits with

Configs without `train_pool` build the same dataset configs as before
(`test_setups.test_train_pool_restricts_training_decks`).
When in doubt: prefer the reused validation set over a restricted one.

## Scope

`scripts/selfplay.py`, `scripts/learn.py` (dataset config),
`scripts/tests/test_setups.py`, `configs/cover*.json`, docs.

## Verification and MDE

`test_setups.py` passes. Each job ends with round 1's round.json. MDE on
the held-out half overall, 3 vs 3 seeds: 2.8 x 0.0076 x sqrt(2/3) ~
0.017 (plus subset luck, so measure the seed sd per arm and report it);
per fight type ~0.04-0.05. Read: held-out lead (and train lead, which is
also partly unseen for the small pools) per arm and fight type; the
cover21 arm against the lean arm tells the cost of the smaller pool.

## Build steps

1. `pool_deck`, the `train_pool` key, test. Check: test_setups passes.
2. (Long run, ~40 min each, 6 threads) nine jobs; then the curve into
   `docs/research/learned-play-results.md` "Coverage pilot" and the
   queue decision under "For the owner".
