# Mini-run setting: an elite payoff and a mid-act rest on the gauntlet

Status: closed (2026-11-04, built and in use; 8faa860; a probe setting, not the headline: decisions "Run layer after run-decisions: the headline setting stays, the mini-run stays a probe setting").

How it moves goal 2: the run-decisions lane prices run-level choices (rest
or upgrade, fight or skip an elite, path) in end-HP on the gauntlet. On
the headline setting an elite pays nothing, so skipping every elite is
worth +14.0 HP (`measurement/elite-skip@headline`) and no path rule can be
adopted (`decision/no-path-rule`); its only rest sits right before the
boss, where upgrading is worth about 0 HP (`measurement/rest-probe@headline`).
This spec adds the two pieces that make those choices two-sided, as flags
that leave every existing file valid: an elite win pays a second card
offer, and a rest site heals mid-act. We'll know it worked when the
one-turn control on the new setting is played (500 sequences) and the
elite-skip read against it gives a number that can go either way: skip
loses cards now, so its +14 HP ceiling shrinks or turns negative. A probe
that passes there (+1.5 HP, gauntlet protocol) is a rule the run layer can
adopt; whether the setting becomes the headline is the navigator's call.

## Outcome and non-goals

Outcome: `gauntlet.py play ... --elite-offers 2 --mid-rest 5` plays the
mini-run setting, and the lane's elite probes run on it.

Non-goals: relics, potions, gold, shops, a branching map (the path choice
stays elite-or-hallway at each elite floor, the existing `--elites` hook);
a rest chooser for the mid-act rest (it heals; `--rest sim` keeps acting
only before the boss); changing the headline setting or its control.

## Behavior

- `--elite-offers N` (default 1): after a won elite fight (not a skipped
  one, `path` = hallway), the reward hook runs N times on that floor. Offer
  j = 0 is today's offer; offer j >= 1 is drawn from
  `rng([GAUNTLET_SEED, i, 1000 + k, j])`, independent of the player and of
  earlier picks, so every player sees the same offers. The chooser sees the
  deck with the earlier picks added. The floor row keeps `offer`/`took` for
  j = 0 and adds `extra: [{offer, took}, ...]` for j >= 1. Without a reward
  hook (`--rewards skip`) the flag changes nothing but the settings label.
- `--mid-rest K` (default off): after floor K is won, before its reward,
  HP heals by `rest()` (30% of max HP, capped); the floor row records
  `mid_rest: <HP after the heal>`. Healing before the reward means the sim
  chooser scores the next floor at the HP it will start at. K must be a
  non-boss floor below the boss's.
- Settings: `elite_offers` and `mid_rest` appear in a file's settings only
  when not at their defaults, so older files keep matching; both join
  `VARY`, so a read can test the setting itself against the old control.
- Mini-run values: `--elite-offers 2 --mid-rest 5` (a rest right after
  the first elite, the "elite then campfire" route): the first elite is
  cheap in HP, the second (floor 8, three floors before the boss) is not,
  so one setting prices both kinds of elite.

## Fits with

- `run()` without the new arguments: unchanged rows (existing
  test_hp_carries, test_skip_reproduces, test_path_hook_run).
- The removal hook at floor 5 runs after the extra offers (its deck holds
  them); the boss rest is unchanged (test_rest_hook_run).
- `--against` refuses a control whose `elite_offers`/`mid_rest` differ
  unless `--vary` names them (test_against_refuses_other_settings pattern).

## When in doubt

Prefer the existing hooks' shapes and row fields over new structures.

## Scope

`scripts/gauntlet.py` (`run`, `offer`, `chooser` and its hooks' offer
index, `play_cmd`, `main`), `scripts/tests/test_gauntlet.py`, the results
doc and `docs/decisions.md`. Off limits: the engine, `ladder.py`, the
protocol, the yardstick and product facts.

## Decisions taken

- Elite payoff is a second card offer, not a relic or max HP: the engine
  has no relics and takes max HP from the character; a card is a payoff the
  sim chooser already prices (starter skip 0.000 vs sim 0.548 clears,
  `measurement/rewards@starter`). Alternatives: max HP +N after an elite
  (engine change), a relic as a starting power (engine change; the relic
  subgoal).
- Mid-act rest after floor 5, heal only. Alternatives: before the second
  elite (makes skipping it rarely right), a rest chooser there (the rest
  probe on this setting, a later step once the elite read is in).

## Verification

- test_elite_offers: a fake chooser that takes the first card: with N = 2
  each won elite floor adds two cards (the second from offer j = 1, distinct
  from j = 0's draw by its own rng), hallway floors add one; a skipped elite
  (path hook False) adds one; N = 1 gives today's rows exactly.
- test_mid_rest: with K = 5 floor 6 starts at `rest(hp_end of floor 5)`,
  the row records `mid_rest`, and the reward hook at floor 5 sees the healed
  HP; without it rows are unchanged.
- test_against_refuses_other_settings extended: a control without
  `elite_offers` is refused unless `--vary elite_offers`.
- End to end: the control job (below) writes 500 sequences with settings
  `elite_offers: 2, mid_rest: 5`, and rows hold `extra` on won elite floors.

## Build steps

1. Flags, run() changes and the three tests (one commit). Check: the
   gauntlet suite passes.
2. Queue (long runs, one turn, `runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpb0.01`,
   headline setting `--start starter --rewards sim --sim-boss` plus
   `--elite-offers 2 --mid-rest 5`, sequences 0-499, 3 threads):
   (a) the control, all 500; (b) after (a), `--elites skip --against (a)
   --vary elites` (the elite ceiling on the new setting); (c) after (a),
   `--elites hp --elite-hp 40 --against (a) --vary elites --vary elite_hp`.
   Each ~15-40 min. Read: (a) against the old one-turn control with
   `gauntlet.py read` (what the setting changes: clears, HP at the boss,
   deaths by floor); (b) and (c) by the protocol at fixed n.
