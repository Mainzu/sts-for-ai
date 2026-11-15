# Distil two-turn search into the net through the ranking term

Status: closed (2026-10-31, decisions "Distillation closed"; built as learn.py's `teacher` key, off by default).

## Why (goal 2, and how we'll know)

Every self-play round so far has a one-turn teacher: the playing net's
one-turn search orders a decision's options, and the ranking term teaches
the next net that order. That teacher is no stronger than the student.
Job 0044b measured a stronger one: two-turn search with the champion's net
at the leaves (the fallback player: one-turn's choice where the tree was
cut) beats one-turn net play by +0.055 (se 0.013) on held-out elites and
bosses, and it changes one-turn's pick at 12.7% of decisions (depth-pilot
doc "Net leaves with the fallback player"). But two-turn play costs ~145x
one-turn's time per decision, too slow to play every fight. This spec puts
its knowledge into the net instead: on a sample of decisions from a
round's self-play games, it re-searches the state two turns deep and uses
those option values in the ranking term in place of the one-turn ones. The
existing exact-label rung already swaps `rank_value` per decision the same
way (`learn.ladder`), so no new loss is needed.

How we'll know: three nets `lean-distil-s{1,101,201}`, paired against
`lean-thr-s{1,101,201}` (same configs, seeds and shared round 0; the only
difference is the teacher), at r2, one-turn search, on `tight2` per fight
type and `tight_bosses` per boss. Adopt as default if elites + bosses gain
>= +0.03 on both halves (MDE ~0.03 per half for 3 shared-round-0 seeds on
~1,100 elite+boss cells), with hallways no worse than -0.015. Direct
check: on 0044b's held-out fights, how often the new nets' one-turn pick
equals the two-turn pick where they differed for lean-thr (agreement
should rise). If the gain is real, ladder-test the best net against the
champion.

## Behavior

- Config key `teacher` (absent: today's behaviour bit for bit):
  `{"turns": 2, "states": 10000, "groups": ["elite", "boss"],
  "max_nodes": 400000, "sample_k": 4, "seed": 0}`. In each round >= 1,
  before the round trains, `learn.teach` draws up to `states` decisions
  with >= 2 options from the round's new self-play dataset, in games of
  the named groups, with a seeded draw. For each it rebuilds the decision's
  state (replay, as `registry` replays datasets), searches it with
  `turns` 2 at the given node cap, with the *playing* net (round k-1's,
  the same net whose one-turn values sit in `rank_value`) at the leaves,
  and, if the search wasn't cut, sets that decision's options'
  `rank_value` to the two-turn values. A cut decision keeps its one-turn
  values (as the fallback player does).
- Value targets are untouched (outcome / search / exact rungs as today):
  the smallest change. A value-target blend is a later arm.
- The decision states are re-searched in a pool of `threads` worker
  processes (`learn.py --threads`, default the config's), each loading the
  net once, like `depth_paired.run_guarded`.
- Teacher labels are cached per (dataset id, net run, teacher settings)
  under the dataset's folder, so a round's later windows (round k's data
  is also in round k+1's window) reuse them; datasets in a window keep the
  labels of the net that played them.
- round.json records `teacher`: states drawn, searched, cut, changed top
  pick (override share), minutes.
- Exact rung wins: a decision whose options have exact values (`ladder`)
  keeps them; teacher values apply to the rest. Lean configs have no
  exact rung (solve_games 0), so this is a rule, not a path the test arm
  takes.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| learn.py without `teacher` | identical datasets, labels and nets | `test_setups`, `test_net` TRAIN_PIN, `test_rounds` |
| Exact rung (`ladder`) | exact values win over teacher values | new test |
| Ranking term | reads `rank_value` only; unchanged | `test_rounds` |
| Generated content (registry-lite) | teacher works on content datasets (replay with the pack loaded) | new test, small pack |
| Job queue | a teacher round is one long job; log prints progress every ~5 min so the stall check stays quiet | job silence-min in the queued commands |

## When in doubt

Prefer the depth_paired fallback player's definitions (same search
settings, same cut rule) over new ones; prefer bit-identical old behaviour
without the key.

## Scope

May change: `scripts/learn.py` (`teacher` key, `teach`), a small helper
shared with `scripts/analysis/depth_paired.py` if useful, `configs/
lean-distil-s*.json`, tests (`scripts/tests/test_teacher.py`), README,
docs. Off limits: the ranking loss, value labels, search code, saved nets,
`db/`.

## Decisions (also in docs/decisions.md)

- Teacher through `rank_value` only (over: value-target blend with lambda
  0.5/1.0, the review's other arm; later if this moves play).
- Elite and boss decisions only, 10,000 per round (over: all groups,
  which spends most labels on hallways where depth measured nothing; over:
  the review's 20k, halved to keep a round's labelling near 30 min on 6
  threads: 10k x ~1.5 s / 6 = ~42 min. The count is a config number;
  measure minutes in the first run).
- Playing net as teacher leaves (over: the champion as a fixed teacher,
  which would mix two nets' values in one decision's options).
- Baseline `lean-thr-s*`: the current layout and the same round 0.

## Verification

- `scripts/tests/test_teacher.py`: no `teacher` key -> identical
  `rank_value`; with the key on a tiny round, drawn decisions are elite /
  boss with >= 2 options, values equal a direct two-turn `sts.search` of
  the replayed state, cut decisions keep one-turn values, exact values
  win, the cache returns the same labels; seeded draw is deterministic.
- Smoke: learn.py rounds 0-1 with `states` 50, a few games.
- End to end (long run): `lean-distil-s{1,101,201}` (3 x ~75 min plus
  ~2 x 42 min labelling each), then the paired read and the agreement
  check.

## Build steps

0. Read how a dataset decision maps to a replayable state (registry
   replay) and to its `rank_value` rows; note it in an addendum. Check:
   addendum.
1. Tests first (fail): test_teacher.py. Check: suites that pin old
   behaviour green.
2. `teach` + config key + cache + round.json record. Check: test_teacher,
   test_setups, test_net, test_rounds (via the queue if slow), smoke run.
3. Configs `lean-distil-s*` from `lean-thr-s*` plus `teacher`. **Long
   run:** queue them with `--round0` as lean-thr's; read per the rule
   above; write the results section and the decision.

Build plan: 4 steps, forks, Opus. Build in a worktree with its own venv
(rate-features is building in another worktree; both edit learn.py, so
whichever merges second rebases).

## Addendum: step 0 (how a decision maps to a state and its rows)

- A round-k (k >= 1) dataset's examples come from
  `registry.examples(ds, mode, labels={"afterstates": True})`, built by
  `selfplay._sample_afterstates`: per sampled decision, first the decision
  state (`option` -1, `played` 1), then one row per non-finished outcome of
  each option, `option` = the option's index in `state.options(LIMIT)`,
  which the sampler asserts is the search's option order; `rank_value` is
  the option's recorded one-turn search value (the same on every outcome
  row of an option). Every row of a decision shares `decision` (an id,
  increasing through the dataset); `group` is the game's encounter group
  (0 hallway, 1 elite, 2 boss).
- The decision state's own row holds its codec bytes (`codec_bytes(i)`,
  empty for generated content). `sts.Combat.decode(bytes, seed=...)`
  rebuilds the state (as `rung4.playouts` does); a two-turn `sts.search`
  of it lists the same root options in the same order (depth_paired
  asserts one- and two-turn search agree on the option list), so option
  `k`'s two-turn value goes onto every row with `option == k`.
- The playing net is the dataset manifest's `parent_model` (a run id under
  `runs/`), as `rung4.player` finds it.
- Where `teach` goes: `learn.learn` calls `teach(cfg, new, k, root, log)`
  for the round's new dataset after `solve_step` and before `fit`, so the
  labelling (and its minutes) is part of the round and its record goes
  into round.json; `load_examples` applies the cached labels
  (`apply_teacher`) right after `registry.examples` and before `ladder`,
  for every round >= 1 part of the window. `ladder` then overwrites
  `rank_value` wherever the database has exact option values, so exact
  values win without a special case. A part whose labels aren't cached
  yet (a resumed or reused round) is labelled on the spot.
- Decisions eligible for the draw: `option == -1` rows in the named groups
  with non-empty codec bytes whose decision has rows for >= 2 distinct
  options (the ranking term needs two). Generated-content decisions have
  no codec bytes, so they are not drawn (counted as `no_state`): a
  deviation from the "Fits with" row, which assumed replay; lean-distil
  configs have no content.
- Seeds: depth_paired seeds each decision's two-turn search with
  `(fight seed x 1009 + decision index) mod 2^64`; here a decision has no
  fight seed at hand, so it is `(teacher seed x 1009 + example index) mod
  2^64`, also the decoded combat's seed.
- Tests go in `scripts/tests/test_distill.py` (`test_teacher.py` already
  holds the teacher-sizing tests).
