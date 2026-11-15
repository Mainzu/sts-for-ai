# Rest-site choice on the gauntlet: heal or upgrade

Status: closed (2026-11-02, read: decisions "Rest-site chooser closed"; `gauntlet.py play --rest sim` remains as an option).

How it moves goal 2: the gauntlet's rest before the boss always heals 30%,
but 17% of sim-boss sequences reach it at >= 56 HP (the heal is mostly
wasted) and 40% at >= 40 (median 34). A real Act-1 player upgrades a card
there when HP allows. Card rewards (+0.184) and sim-boss (+0.155) showed
deck choices are where run-level clears are; this is the next run-layer
choice (review 2026-11-02b rank 3, Next Q3). We'll know from a gauntlet
protocol read of `--rest sim` against the sim-boss headline file on the
same sequences.

## Outcome

`gauntlet.py play ... --rest sim` lets a chooser pick, at the rest site
before the boss, between healing and upgrading one card, by simulating the
known boss fight; without the flag nothing changes.

Non-goals: more rest sites, card removal, path choice, a learned chooser,
two-turn simulation in the chooser, Silent-specific upgrades (it works on
whatever `sts.deck_card_names()` lists).

## Behavior

- `run(..., rest_hook=None)`: at the boss floor, if `rest_hook` is given it
  is called once with `(sequence, HP, deck)` of every live sequence and
  returns, per sequence, `None` (heal: HP = `rest(hp)`) or a card name
  (upgrade: the first copy of that name in the deck becomes `name+`, HP
  unchanged). The boss floor's row records `"rest": "heal"` or the
  upgraded name. Without a hook: today's heal, no `"rest"` key.
- `rest_choose(items, sim_play, max_hp)`: options are heal, then each
  distinct upgradable name in the deck in first-occurrence order
  (upgradable: not ending in `+`, and `name+` in `sts.deck_card_names()`).
  Each option plays `REST_FIGHTS` = 16 one-turn fights against the
  sequence's actual boss (the real game shows it on the map), seeds
  `SIM_SEED_BASE + i*10_000 + 1000 + m` (clear of the reward chooser's
  `k*100 + off + m < 1000`), the same seeds for every option, at the
  option's HP and deck. Score = mean won x (1 + 0.01 x end HP), as the
  reward chooser; first maximum wins, so ties go to heal. No upgradable
  card: heal without simulating.
- CLI `--rest {heal,sim}` (default heal; `"rest_choice": "sim"` enters
  settings only when sim, so older files keep matching). The chooser plays
  with the same player one turn deep, like `--rewards sim`.

## Fits with

- Today's runs without `--rest`: unchanged rows and settings
  (`test_skip_reproduces`, `test_deck_grows`, `test_blocks_same_rows`).
- Reward chooser: its boss-horizon fights still assume a heal (unchanged).
- `gauntlet_protocol.end_hp`, `summary`, `read`: ignore the new key.

When in doubt: prefer matching the reward chooser's conventions over new
ones.

## Scope

`scripts/gauntlet.py`, `scripts/tests/test_gauntlet.py`, README gauntlet
lines, results/decisions docs. Off limits: the engine (Rust), the reward
chooser's behaviour, the gauntlet's sequences and shape.

## Decisions

- The rest chooser simulates the actual boss, not the boss pool (sim-boss
  uses the pool because card rewards come floors earlier; the real game
  shows the boss throughout, so both are fair).
- 16 fights per option: one decision per sequence, so ~8 options x 16 =
  ~128 one-turn boss fights, ~20% of the reward chooser's fights.

## Verification

Tests first (`test_gauntlet.py`):
- `test_rest_choose`: fake sim_play winning only decks with `Bash+`;
  starter deck at 70 HP -> picks `Bash`; specs: 16 per option, options =
  heal + Strike, Defend, Bash; heal option at rest(70) with the plain deck,
  upgrade options at 70; seeds equal across options and in
  `[SIM_SEED_BASE + i*10_000 + 1000, +1016)`; all encounters = the
  sequence's boss. A fake that wins everything -> heal (tie).
- `test_rest_hook_run`: hook upgrading `Strike` -> boss spec has HP
  unchanged and deck with exactly one `Strike+` in the first Strike's
  slot; row `"rest": "Strike"`; a hook returning None -> rest(hp) and
  `"rest": "heal"`; no hook -> no key.
- End-to-end (long, job queue): net1029 `@hpb0.01`, `--start starter
  --rewards sim --sim-boss --rest sim --against
  results/gauntlet/net1029-hpb0.01-starter-simboss.json` on 0-499, after
  the control is extended to 500. Read: protocol verdict; share of
  sequences that upgraded; per HP band at the rest.

Don't guard: decks with no upgradable cards beyond the heal path; Silent.

## Build steps

1. Tests + `rest_choose`, `run(rest_hook=)`, `--rest` (one step,
   in-session). Check: `pytest scripts/tests/test_gauntlet.py`.
2. (long) Extend the control to 500, then the `--rest sim` read, through
   the job queue.
