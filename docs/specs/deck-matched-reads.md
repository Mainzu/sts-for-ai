# Deck-matched reads

Status: closed (2026-11-04, built and in use; gauntlet.py play --match; decisions "Deck-matched reads built; boss-replay score not adopted"; a one-turn screen tool only, decisions "Deck-matched reads stay a one-turn screen tool").

Lane `cheaper-reads`, step 1 (decision "Lane cheaper-reads opened").

## Outcome

`gauntlet.py play --match <file>` replays another gauntlet file's recorded
choices (card picks, the extra elite picks, the rest choice, the removal)
into this run wherever that file has one, so a read of a new fighter
against that file varies only the fighter and the paired end-HP sd falls.

How it moves goal 2 and how we'll know: every goal-2 verdict on the
headline costs ~500 sequences two turns deep (~5-10 thread-h) and mostly
ends open, because the sim chooser diverges the two players' decks after
floor 1 (`cause/headline-pairing-weak`: paired end-HP sd 20-22 between
nets, identical decks in 0-3 of 250). If matching the picks brings the sd
toward 12, a +1.5 HP effect decides near n 130 instead of running open
at 500: each fighter read gets 2-4x cheaper. We know from the first check:
two known nets one turn deep, matched to the one-turn control's picks on
sequences 0-249, against today's unmatched sd 20.2-21.7 for the same pairs.

Non-goals: matching path choices (`--elites skip|hp` stays the candidate's
own); reading a chooser change (a matched read holds the control's picks,
so it can't see one; chooser reads stay unmatched); changing the protocol.

## Behavior

- `--match FILE`: FILE is a gauntlet result file. Its seed and shape must
  equal this run's, and so must every choice setting (rewards, sim_boss,
  chooser, fit, rest_choice, remove, elite_offers, elites, elite_hp,
  mid_rest, start, rest); fighter settings (price, two_turn,
  one_turn_floors, line_seed, step_line) and the player may differ.
  Otherwise refuse, naming each field.
- After floor k, a sequence whose row in FILE has floor k with an offer
  takes FILE's offer and took (same offers by construction: `offer()`
  depends only on sequence, floor and j); an extra elite pick j takes
  FILE's `extra[j-1]`; the boss floor's rest takes FILE's `rest`
  ("heal" = heal); floor REMOVE_FLOOR's removal takes FILE's `removed`.
  The floor row gets `"matched": true` when its card pick came from FILE.
- Where FILE has no record (its sequence died earlier, or isn't in FILE),
  the run's own chooser decides, as today. While FILE covers a floor the
  two decks are equal, so a recorded name is always in the deck.
- A matched sequence runs no chooser fights for that floor (cheaper too).
- `settings["match"] = FILE`. `setting_diff` ignores `match` (it pins
  choices, not play), so `--against FILE` works without `--vary`; a rerun
  into an existing `--out` with another `--match` is refused like any
  settings change.

## Fits with

- `run()` without hooks or with today's hooks: rows unchanged
  (existing tests `test_deck_grows`, `test_rest_hook_run`,
  `test_remove_hook_run`, `test_elite_offers`).
- `--against` refusals and `--vary` (`test_against_refuses_other_settings`).
- Files without `match` keep matching (absent field).

## When in doubt

Prefer refusing a mismatched match file over playing a silently odd read.

## Scope

`scripts/gauntlet.py` (play options, a hook wrapper), its tests, README /
`how/gauntlet-read`, results doc for the check. Off limits: engine, `py/`,
`ladder.py`, the protocol code, other scripts' formats.

## Decisions

- Matching lives in `gauntlet.py play` as a hook wrapper, not in `run()`
  (run stays a plain floor loop).
- `match` is not compared by `setting_diff` (reversible: add it to VARY
  later if it ever needs declaring).

## Verification

Tests (fake ladder, no CPU):
- `test_match_replays_picks`: a run with a take-first chooser recorded,
  then a run with a take-last chooser wrapped by the match of the first
  rows: same took on every floor, `matched` true, the fallback chooser
  never asked.
- `test_match_falls_back`: the recorded file lost at floor 3; the matched
  run (no loss) uses FILE's picks on floors 0-2 and its own chooser after.
- `test_match_rest_remove`: recorded rest name and removal replayed.
- `test_match_cli`: `--match` writes `settings.match`, works with
  `--against` the same file without `--vary`; a file with other rewards is
  refused naming `rewards`; a fighter field (`--two-turn`) may differ.

End-to-end (the lane's first check, a queued job, ~1-2 thread-h): two nets
one turn deep, `--match` and `--against` the one-turn control
(`results/gauntlet/net1029-hpb0.01-starter-simboss.json`), sequences
0-249: rerank-burst8hp2-s1 (unmatched mean -5.6, sd 20.6) and
net1029-s101 (same recipe, other seed; -1.4, sd 20.6). Go if the paired
end-HP sd falls toward 12; fail if it stays above ~18.

## Build steps

1. Hook wrapper + `--match` option + the four tests (in-session).
2. Queue the check (two jobs, one turn, 3 threads) with read notes.
