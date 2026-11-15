# Boss-replay score

Status: closed (2026-11-04, built, not adopted: sd ratios 1.17-1.28 under the 1.4x bar; decisions "Deck-matched reads built; boss-replay score not adopted"; kb measurement/boss-replay-score@one-turn).

Lane `cheaper-reads`, step 2 (decision "Lane cheaper-reads opened").

## Outcome

`boss_replay.py play --hp arrival --seeds 8` replays each boss-reaching
sequence's boss fight k times from its arrival state (deck, HP, boss) on
common seeds, and `boss_replay.py pair <a> <b>` scores each sequence by its
mean replay result (0 if it died earlier), so a read can measure whether
that score pairs two players more tightly than one real boss fight.

How it moves goal 2 and how we'll know: most headline deaths are at the
boss (62 of 83) and one boss fight is a coin flip per sequence; averaging
k replays removes that flip from the sequence score. If the paired sd of
mean boss win falls 1.4x or more against the paired sd of clears, a
headline verdict needs about half the sequences. We know from `pair` on
the one-turn files of step 1 (two nets against the control, unmatched and
matched).

Non-goals: a new protocol (adoption is a decision after the read);
replaying other floors.

## Behavior

- `--hp arrival`: each deck plays at its own arrival HP (`hp_obs`);
  settings record `"hp": "arrival"`; rows hold `won: {"arrival": [0/1 per
  seed]}` and `hp_end: [per seed]` (0 on a loss). Replay seed 0 is the
  boss floor's own seed, as in the sweep. The HP sweep is unchanged.
- `pair a b`: both arrival-mode replay files; each names its gauntlet file.
  Over the sequences both gauntlet files hold: per sequence, cleared (0/1)
  and end HP from the gauntlet rows, replay win (mean over seeds) and
  replay end HP (mean) from the replay rows, 0 for a sequence with no
  replay row (died before the boss). Prints n, mean b-a and paired sd of
  each, and sd(clears) / sd(replay win) and sd(end HP) / sd(replay end HP).
  Refuses sweep-mode files.

## Fits with

Sweep mode, its rows and `read` (`test_deck_rebuild`, `test_seeds_common`,
`test_read_curves`, `test_resume`).

## Scope

`scripts/analysis/boss_replay.py`, its tests, README's boss-replay
paragraph, the results doc. Off limits: gauntlet.py, engine, ladder.

## Verification

- `test_arrival_mode`: fake play; each deck plays at its hp_obs with
  `seeds` common seeds, rows hold won and hp_end lists.
- `test_pair_scores`: two hand-made gauntlet + replay files; pair's
  numbers equal a hand computation (a died-early sequence scores 0).
- End-to-end: queued replays (one turn, 8 seeds) for the control and the
  step-1 files, read with `pair`; adopt at a 1.4x sd cut.

## Build steps

1. Arrival mode, `pair`, the two tests (in-session).
2. Queue the replays; read.
