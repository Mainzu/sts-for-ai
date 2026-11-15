# Depth probe: decisive headline fights replayed deeper

Status: closed (2026-11-04, no go (rollout leaf +0.67 HP worse on 498 elites, three turns under the bar); decisions "Lane depth-headroom closed (2026-11-04)").

## Outcome

`scripts/analysis/depth_probe.py` replays the headline control's decisive
fights (floor-9 elites that lost 15+ HP, bosses entered at 50-69 HP) with
the two-turn product, three-turn search and the rollout player, and reads
paired HP lost and wins per fight, so the `depth-headroom` lane can go or
stop.

**How it moves goal 2 and how we'll know.** Search depth is the strongest
lever found so far (+0.154 clears from one to two turns,
`measurement/headline@two-turn`), and three-turn search, rollout leaves and
two-turn choosers are paused until a probe shows headroom. If three turns
or rollouts recover 1.5 HP or more per decisive fight over two turns
(paired, 2 se), that family becomes a product candidate on the headline;
if not, it closes on this laptop and the depth budget goes to the run
layer. The read is the number.

Non-goals: a new search, a faster three-turn tree, a fallback other than
the guarded player's (a cut decision plays the one-turn choice, as two
turns do today); playing whole sequences.

## Behaviour

- **Fights.** From a headline gauntlet file (`--file`, the control
  `net1029-hpe0.01-two-line-step-starter-simboss-a.json`), `--kind elite`
  takes floor index 8 where `hp_start - hp_end >= 15` (a loss has hp_end 0,
  so it counts); `--kind boss` takes floor index 10 entered at 50-69 HP.
  `--kind elite-rest` takes the other floor-9 elites (lost under 15) and
  `--kind elite-all` every floor-9 elite: outcome-blind sets, since a
  replay looks better on fights picked for the control's bad outcome
  (decision "depth-headroom: outcome-blind elite reads").
  Rows in sequence order, first `--limit` of them. The deck is the start
  deck (the character's starter for `start: starter`, else the cell deck)
  plus every non-null `took` of the floors before; encounter, seed
  (`SEED_BASE + i * 100 + k`), group and HP are the file's. Files whose
  settings change decks or fights in ways the rebuild can't follow
  (removal, rest choice, elite paths, extra elite offers, mid rest) are
  refused.
- **Arms** (`--arm`): `two` = the product's two-turn player
  (`ladder.play_two_turn` with line seed and step line), which should
  reproduce the file's own result on every fight; `three` = the same guarded
  player at `turns 3` (`--max-nodes`, default 400 000 as two turns);
  `rollout` = `rollout_probe.play_rollout` with the product net as policy
  (`--n` rollouts per action, default 16). Player: the product net
  `@hpe0.01` (`--player`).
- **Output** `--out` JSON: `settings` and `fights`, one row per fight
  `{i, floor, encounter, hp_start, won_obs, hp_end_obs, won, hp_end}` plus
  the arm's counters (`cut`, `decisions`, `override` for two/three;
  `overrides`, `playouts` for rollout; `seconds`). Resumable: two and three
  keep a `.partial` line file (run_guarded); rollout skips fights already in
  `--out` and rewrites it after each fight.
- **`read <a> [<b>]`** (each may join files with `+`, their fights merged): pairs by (i, floor); prints n, mean HP lost b - a with
  se, wins b - a with se, cut share per file, and per file how many fights
  reproduce the control (same won and hp_end). With one file, its own
  control columns stand as `a` (the two-turn product's play, which the
  `two` arm reproduces), so the two-turn arm needn't be played again.

## Pilot (2026-11-04, 3 elites, main's sts)

- `two` reproduced the control on 3 of 3 (won and hp_end), ~4 s per fight
  at one thread.
- `rollout` (n 16): ~7 s per fight at 3 threads (~0.35 thread-minutes).
- `three` at 400 000 nodes: ~2 thread-minutes per fight, 24% of decisions
  cut (and so played one turn deep); at 1 600 000 nodes: ~5 thread-minutes,
  13% cut, ~1.6 GB per fight process (3 at once ~4.9 GB, under the
  charter's 5 GB bound). The jobs use 1 600 000.
- Sizing (lane cap 12 thread-hours, anchor ~4.2): rollouts on all 237
  decisive elites (~1.4 thread-hours), three turns on the first 48 (~4
  thread-hours, paired se about 1.5 HP at the pilot's spread, so a screen:
  only a gain near 3 HP clears 2 se). Bosses wait for the elite read.

**Fits with:** `boss_replay.rebuild` and its tests stay as they are (the
probe has its own rebuild for any floor); `depth_paired.run_guarded`,
`ladder.play_two_turn` and `rollout_probe.play_rollout` are called, not
changed.

**When in doubt:** prefer reusing the existing players over new search code.

## Scope

New `scripts/analysis/depth_probe.py`, new `scripts/tests/test_depth_probe.py`,
results under `results/depth_probe/`, results docs. Off limits: the engine,
`gauntlet.py`, `ladder.py`, `depth_paired.py`, `rollout_probe.py`.

## Verification

- `test_depth_probe.py` (fake rows, no engine play): elite and boss
  selection (the 15 HP rule with a loss, the 50-69 band, `--limit` order),
  deck rebuild (starter plus earlier tooks only; a took on the fight's own
  floor or later is not in the deck), seed and HP, refused settings; `read`
  pairing and the reproduction count on hand-made files.
- End to end: `--arm two --kind elite --limit 3` reproduces the control's
  won and hp_end on all 3 fights.

## Build steps

1. The script and its tests; the end-to-end reproduction check (minutes).
2. Pilot (long run, queued): three-turn and rollout on a few elites to
   size `--limit` and `--max-nodes` under the 5 GB and 4 thread-hour bounds;
   then the elite and boss jobs.
