# Value chooser (lane value-chooser)

Status: closed (2026-11-06, built and in use; gauntlet.py --rewards value; decisions "Lane value-chooser closed"; use per kb decision/value-chooser-use).

**Goals.** Goal 2: under the one-turn rule the headline read (own card
picks) is the dearest read left, 12-33 min per 500 sequences, nearly all of
it the sim chooser's option fights (`measurement/cost@gauntlet`). A chooser
that scores each option by the fighting net's value of fight start states,
with no fights played, would make every headline read (goal 2's, and goal
1's own-pick reads) a few minutes. We'll know from one paired read on the
headline setting against the one-turn control (`lane/value-chooser`'s
measure): level by `yardstick/cost-savers` at a third of the wall time or
less is a go.

## Outcome

`gauntlet.py play <net> --rewards value` picks cards by the net's static
value of start states; non-goals: weights between fight types (sum of part
means, as `--sim-boss`), a learned run value (`--rewards vrun` exists), the
two-turn product.

## Behavior

- For each option (skip, or one offered card added), the chooser builds
  `sts.Combat(deck, encounter, seed, hp)` start states (the opening hand is
  dealt at construction) for three parts and scores the option by the sum
  of the parts' mean net values:
  1. the next floor: the sim chooser's own draw (stream 3000, 8 encounters
     and seeds, as `sim_fights`), at the current HP (post-rest HP if the
     next floor is the boss);
  2. the elites: each of `ELITES` once, at the current HP, while an elite
     floor lies after the next floor (k + 1 < last elite index); the seeds
     from a stream of their own;
  3. the sequence's own boss (`fights[-1]`) at the post-rest HP, unless the
     next floor is the boss (part 1 then is that boss, 8 seeds).
  The same states for every option. Ties go to skip, then the earlier card.
- `--value-hands K` (default 1): each start state is averaged over K dealt
  hands (seeds `seed + 7919 x h`, h = 0..K-1). Recorded in settings as
  `value_hands` only when not 1, so the default's files keep matching.
- The value net is `--chooser`, else the player; its `.pt` path without the
  `@` settings (they act at search leaves, not on a start state). A
  heuristic or a two-turn-only chooser is refused with a message.
- `--rewards value` with `--sim-boss` is refused (the boss is always in).
- `run_value` records per floor what it took, as for sim; nothing else.
- Read: `scripts/analysis/value_chooser_read.py <run> <control>` prints,
  on all paired sequences and on those where neither file took Demon Form:
  n, end-HP difference and clears difference with se, each file's Demon
  Form take rate (sequences that took it), and pick agreement (floors both
  files reached with the same offer: share with the same `took`), plus the
  two jobs' wall time if `--jobs a,b` names their records.

**Fits with:** `chooser`/`sim_choose`/`vrun_choose` keep their picks
(`test_sim_choose`, `test_sim_boss`, `test_chooser_player` unchanged);
older result files keep matching (settings unchanged at the defaults);
`--against ... --vary rewards` reads the control.

**When in doubt:** prefer the sim chooser's conventions (streams, ties,
settings fields) over new ones.

**Scope:** `scripts/gauntlet.py`, a new `scripts/analysis/value_chooser_read.py`,
`scripts/tests/test_gauntlet.py`, this spec, the results doc. Off limits:
engine, `py/`, the sim and vrun choosers' behaviour.

**Decisions:** part 2's elites at the current HP and part weights 1:1:1
(the charter's first cut); one hand by default (the dealt-hands fallback is
the flag).

**Outside assumptions:** a start state's net value ranks decks: measured
before the spec on the control's 5391 played fights (value vs. outcome
score corr 0.55 hallway, 0.78 elite, 0.55 boss); boss values are too
pessimistic (146 of 447 boss starts read under 0.25, half of them won), so
the boss part may carry less signal than the sim chooser's.

**Verification:** tests first: `test_value_choose` (a fake value function
that rewards one card name: the chooser takes it; a flat one: skip),
`test_value_parts` (the parts' encounters and HPs: elites present before
floor 7, absent after; the boss at post-rest HP; next floor boss gives one
part), `test_value_settings` (`value_hands` only when not 1; `--sim-boss`
refused). End to end: `gauntlet.py play <net>@hpb0.01 --start starter
--rewards value --sequences 4` runs and writes picks.

**Don't guard:** generated-content decks (cells are official cards).

## Build steps

1. Tests above, then `value_choose` + `--rewards value` + `--value-hands`
   in `gauntlet.py` (check: the tests and the fits-with tests pass).
2. `value_chooser_read.py` (check: it reads the control against itself as
   zeros and 100% agreement).
3. Queue (long runs): the value chooser one turn deep on the headline
   setting, sequences 0-499, fixed n, and the dealt-hands arm at K = 4.
