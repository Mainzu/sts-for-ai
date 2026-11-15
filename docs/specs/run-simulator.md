# Run simulator: whole Act 1 runs outside the fights

Status: confirmed (2026-11-15, by the owner, queued for a build in a new session; written with the owner from docs/research/sts-ai-prior-art.md "Run simulator: options"; supersedes the R2 draft docs/specs/run-layer-relics.md, with its session's agreement; nothing built).

Research: `docs/research/sts-ai-prior-art.md` ("Run simulator: options"
and its synthesis), the four raw designs in
`docs/research/sts-ai-prior-art/run-sim-designs.md`, decisions "Run
simulator: our own design, sts_lightspeed a lead, options weighed first
(owner, 2026-11-15, provisional)". Jar notes on relics from the relics
session: `docs/research/relics-jar-2026-11-15.md` (780b7fc3), and the
`run_parts` map in `docs/research/act1-coverage.json`, which says per relic
what is loaded and what waits on the run layer.

## Outcome

`sts.RunSim` plays whole Ironclad Act 1 runs at any Ascension level,
everything outside a fight (Neow, map, ? rooms, card, gold, potion and
relic rewards, chests, rest sites, events, shops, the out-of-combat relics),
with the game's own rules and random numbers, so that run decisions can
later be tuned or learned on many simulated runs and every logged real run
can be replayed and compared step by step.

**How it moves the goals, and how we'll know.** Goal 2: every strong StS
bot found its run-layer strength on a full-run simulator (the survey's
"Where we trail" 1), and ours has none; the simulator is the precondition
for the run decision maker the owner put after gold, shops and events
(backlog 83). We'll know it works when the log replay reproduces the
logged runs (maps, encounters, rewards, Neow, events) seed for seed where
the game's streams allow, and a whole simulated A20 run plays to the boss
with today's rules. Goal 1: run content (events, relic run parts, shops,
Neow, reward tables) is data in one closed, worded vocabulary, so a custom
or generated event loads like an official one; we'll know when an event
written only as data, with no code, plays and passes its tests.

**Non-goals** (the owner, 2026-11-15): Acts 2-4 and the boss relic (the
run ends when the Act 1 boss dies, before its rewards); characters other
than Ironclad; a run decision maker or any chooser beyond today's bridge
rules and the sim card chooser; moving the headline setting to simulated
runs; pricing carried resources (potions, gold) in fights.

## Behaviour

### The run state and what the agent sees

- `engine/src/runsim/` holds the run's rules. The run state holds only
  what a player can know: act, floor, HP, max HP, gold, deck (cards with
  upgrades and flags such as the bottled flag), relics with counters,
  potions, the map with its symbols (an unvisited ? stays ?), the current
  node, the screen and its options, the boss's name, and the event pools
  and ramps a player could infer. It holds no RNG, like the combat state
  (`engine/src/state.rs`).
- The game's random streams live beside the state, in a chance source,
  never in it. Things the game rolls ahead and hides (the act's monster
  and elite lists, the shuffled relic pools) live in that source too, and
  a planner never reads them.
- **The simulator speaks CommunicationMod.** `RunSim.state()` returns a
  dict in the shape of CommunicationMod's `game_state` for the current
  screen (`screen_type`, `screen_state`, `choice_list`, `map`, `deck`,
  `relics`, `potions`, `gold`, `current_hp`, `max_hp`, `floor`, `act`,
  `ascension_level`, `seed`, `room_type`), and `RunSim.command(text)`
  takes CommunicationMod commands (`choose N`, `proceed`, `confirm`,
  `skip`, `leave`, `return`). So today's out-of-fight decisions drive
  simulated runs unchanged: `scripts/real_game_run.py`'s functions
  (`event_command(gs)`, `map_command(gs, choices)`,
  `reward_command(gs, card_done)`, `rest_command(gs, choices)`,
  `boss_relic_command(gs, choices)`, `grid_command(gs, choices)`) and the
  screens `real_game.Bridge.outside` handles inline (chest, hand
  select, shop room, game over). Card picks use the sim card chooser:
  skip and each offered card scored by trial fights against the next
  floor's pool and the act's boss (`gauntlet.sim_score` over fights played
  by `ladder.play_bench` with the chooser's net, as `Bridge.card_pick`
  does), called without a live game. The bridge needs no rewrite to share
  any of this. A
  command the screen doesn't allow is an error naming the screen and the
  command.
- **Fights are handed back.** Entering a monster, elite or boss room
  returns a fight to play: encounter, deck, HP, max HP, relics with
  counters, potions, ascension level and a fight seed. Python plays it with
  any player the gauntlet can use (heuristic, one-turn net, the two-turn
  product), then calls `RunSim.fight_result(...)` with what the fight
  changed: won or lost, HP at the end, max HP (Feed), potions left, relic
  counters, and each thief that escaped with the gold it carried off. A
  lost fight ends the run. Burning Blood's heal and other end-of-fight
  relics are applied by the engine's fight as today; the run takes the HP
  after them.
- The run ends when the Act 1 boss dies (`state()` shows `GAME_OVER` with
  victory) or the player dies. Its record holds seed, level, floors
  reached, HP, max HP, gold, deck, relics, potions, each decision with its
  options and pick, each fight's start and end, and the rules mode.

### Chance

- Every random procedure is written once against a chance trait with four
  sources:
  - **game**: the jar's own `Random` (libGDX RandomXS128 with a call
    counter, every call form) and `java.util.Random` for the game's
    `Collections.shuffle(list, new java.util.Random(rng.randomLong()))`,
    as the game's 13 streams with their seeds (monster, event, merchant,
    card, treasure, relic and potion for the whole run; map with seed+act;
    monster HP, AI, shuffle, card-random and misc reseeded each floor with
    seed+floor). Seed-exact.
  - **sample**: the engine's own fast RNG, for volume.
  - **exact**: lists every outcome with its probability where a site has
    few (a card reward's rarity roll, which room a ? becomes, which event
    an event room holds, a chest's size, a relic tier, an event's coin
    flip), extending `engine/src/rng.rs`'s `enumerate()` with a cap on
    outcomes per site and in total; a site over the cap is sampled and
    says so (map generation is never enumerated).
  - **observed**: takes the outcome the real game showed (the bridge's
    shadow run and the log replay), and checks that it is one the
    simulator lists with probability above 0.
- `RunSim.outcomes(command)` gives, for a planner, the weighted list of
  next observations after a command, from the exact source with the
  hidden lists resampled from what a player has seen; never from the live
  game streams. Nothing in this spec plays from it; it exists so a later
  decision maker can average exactly (`docs/direction.md` "Exact before
  sampling").
- **Seed-exact where checkable** (the owner): the map, ? room types, event
  picks, monster and elite lists, boss, Neow, card, gold, potion and relic
  rewards, chests, shops and event outcomes follow the game's streams.
  Two kinds of roll can't be: rolls the game itself leaves unseeded
  (`MathUtils.random`, `new Random()`; for example Neow's drawback curse
  and Shining Light), and rolls on a persistent stream that a fight also
  draws from (potionRng, used in combat by Entropic Brew and Alchemize).
  The first come from a separate stream seeded from the run seed; after
  the second, the stream is marked disturbed. Both are checked by
  distribution, and the replay never counts them as seed-exact misses.

### The game's quirks: one switch

`RunSim(..., rules="game")` (default) copies the jar exactly, bugs
included. `rules="consistent"` fixes every quirk on this list at once, and
nothing else; each run records which mode it used, and a test checks each
quirk in both modes:

1. Map: `MapGenerator.getCommonAncestor` orders nodes by `node1.x <
   node2.y` (x against y). Consistent: x against x.
2. ? rooms: the event room picks its event from a copy of eventRng that is
   never written back, so the next ? room's type roll reuses the float
   this event's shrine-or-event roll used. Consistent: the pick advances
   eventRng.
3. Unseeded rolls (`MathUtils.random`, `new Random()`): game mode draws
   them from the separate unseeded stream above. Consistent: from the
   floor's miscRng, so they replay with the seed.
4. Special one-time event eligibility: FaceTrader is allowed in Exordium
   though its rule names other acts (and other eligibility slips the
   event steps find). Consistent: the rule as each check evidently
   intends.
5. Shop rarity draws on cardRng (`rollRarity` ignores its argument), so a
   shop visit shifts later card rewards. Consistent: the shop draws on
   merchantRng.

A quirk a later step finds joins this list in the same commit, with its
two-mode test.

### Ascension

The simulator takes any level 0-20 and applies each Act 1 run-level
Ascension effect the jar has (a build step lists them by scanning the jar's
run-level classes for `ascensionLevel` checks: more elites at A1+, starting
HP and max HP, Ascender's Bane, potion slots, shop prices, event variants
at A15+, and whatever else the scan finds). Run-start values already in
the engine (`docs/specs/ascension.md`: at A20 75 max HP, 68 HP, 2 potion
slots; Ascender's Bane from A10) are reused, not duplicated. Tests check A0 and A20
against logged runs at both levels.

### Run content as data

- Files: `content/run/*.json`, a folder of its own, so the combat pack
  loaders (`real_game.load_packs`, the explorer's glob of
  `content/packs/*.json`) never read them, the installed `sts` never needs
  a swap before run content lands, and no combat pack's hash changes.
  - `content/run/act1.json`: the act's tables: room-type chances, the
    elite multiplier, encounter list rules (weak and strong lists, their
    exclusions), reward tables (card rarity per room with the rare
    offset, gold ranges, potion drop rule, relic tier odds, chest
    sizes), rest-site options, the boss list.
  - `content/run/act1-events.json`: the reachable Act 1 events (11 in
    Exordium's list, 6 shrines, and the special one-time events eligible
    in Act 1; 25 in all by the jar reading, to be confirmed by the event
    steps).
  - `content/run/act1-neow.json` and `content/run/act1-shop.json`.
  - `content/run/act1-run-relics.json`: the run parts of Act 1 relics,
    keyed by relic id (the R2 draft's 45 relics plus the run parts of the
    12 with both parts); `RELIC_KEYS` stays combat-only. A relic's combat
    part stays in `content/packs/act1-relics.json`.
- The vocabulary is closed and worded: run effects (gain or lose gold, HP,
  max HP; heal by an amount or a fraction; add, remove, upgrade, transform
  or duplicate cards, picked or random, by type or tag; obtain a relic or
  potion by name or by tier roll; lose a potion; start a fight with a
  reward; open a reward; go to another screen; leave; set a flag or
  counter; a random choice on a named stream with listed outcomes), run
  conditions (gold, HP, max HP, a relic held, a card type or tag in the
  deck, ascension, act, floor, a flag), and run quantities for amounts
  (max HP, HP, gold, deck count by type, floor, ascension, a counter).
  Each atom is listed in `registry::element_names()` under its own family
  (`run_effect`, `run_condition`, `run_quantity`, `run_screen`) with words
  in `content/wording.json`, and `engine/tests/wording.rs` walks
  `content/run/*.json` as it walks the packs.
- An event is a small screen machine: screens, each with options, an
  option's conditions (the game's disabled options), and its effects,
  including random outcomes on the stream the jar uses, in the jar's call
  order. Ascension variants are rows by level, like a monster's
  `ascension` rows.
- A mechanic the vocabulary can't say gets a named primitive in the
  engine, referenced from data (fidelity wins, the owner): for example
  Match and Keep's pairs game, Bonfire Elementals' outcome by the offered
  card's rarity. Each primitive is listed and worded like an atom.
- A custom or generated event, relic run part, shop item or Neow option is
  a row in the same files' format, loaded by `RunSim(..., content=[paths])`
  on top of the official ones.

### The bridge

- **Shop screens are logged** (run rules 6): the bridge opens each shop,
  records its stock and prices, and leaves without buying, as it walks
  past today. It is the only change to what the bot does.
- **A shadow simulator** runs beside each live run: it starts from the
  run's seed and level, follows the game with the observed chance source,
  plays no part in any decision, and writes each first mismatch per kind
  (map, encounter, reward, event, shop, Neow, state field) to
  `results/real-game/<stamp>/shadow.jsonl`. A crash in the shadow logs one
  line and turns the shadow off for that run; it never stops the run.

### Failure cases

- A content row with an unknown atom, a missing field or a bad stream name
  fails to load, naming the file, the row and the key; nothing from that
  file loads.
- An event the simulator meets with no data (not yet extracted) ends the
  simulated run with an error naming the event; it is never skipped or
  guessed.
- A command that isn't legal on the screen is an error; `state()` is
  unchanged by it.
- `fight_result` for a fight that isn't pending is an error.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| The gauntlet (`scripts/gauntlet.py`) and its reads | untouched: the simulator is a new path beside it; the headline and one-turn controls and final-round's pinned jobs replay as before | `git diff` of `scripts/gauntlet.py` empty at each landing; `scripts/tests/test_gauntlet.py` |
| The real-game bridge (`scripts/real_game.py`, `real_game_run.py`) | the bot makes the same decisions; the only change is run rules 6 (open and log shops); the shadow only logs | new `test_rules_give_the_same_commands_on_recorded_states` (step 0) over a frozen sample of recorded states; `scripts/tests/test_real_game*.py` |
| Combat and the packs | golden unchanged; the installed `sts` keeps loading main's `content/packs/` (run content is in `content/run/`) | `cargo test --test golden`; `engine/tests/relics.rs`, `potions` tests |
| Relic counters through fights | fights take relics as `sts.Combat(..., relics=[(name, counter)])` and the counters a fight changes come back out | `engine/tests/act1_relics.rs`; new `runsim_fight_round_trips_relic_counters` (step 16) |
| Wording | every atom has words, no stale words, every used atom listed, now including `content/run/` | `engine/tests/wording.rs` extended (step 5) |
| Explorer and reports (`scripts/explore.py`, `scripts/real_game_report.py`) | same output; run records go to new files | `scripts/tests/test_explore.py`, `test_real_game_report.py`; the report reads `RULES_FROM` for rules 6 |
| Act 1 coverage (`docs/research/act1-coverage.json`, `scripts/docs_index.py`) | what "loads" means for a relic's combat part is unchanged; a relic's run part is tracked in the `run_parts` map | the pre-commit hook; `docs_index.py --write` |
| Engine RNG (`engine/src/rng.rs`) | `Rng`, `below()` and every combat stream unchanged; the game's Random is a new type beside it | `engine/tests/determinism.rs`, `chance.rs`, golden |
| Names | no Rust type named `Run` in scope with `state::Run`; the Python class is `sts.RunSim`, beside the existing function `sts.run` | review |

## When in doubt

Prefer the jar's behaviour over the wiki or sts_lightspeed; prefer a named
primitive over a row that only approximates; prefer leaving the gauntlet
and the bridge untouched over sharing code with them.

## Scope

May change: a new Rust module `engine/src/runsim/` (and its `pub mod`
line in `engine/src/lib.rs`) and its tests; the
registry's element list and the wording file (new families only); the
Python bindings (a new `RunSim` class; `fight_result` fields); new
content files under `content/run/`; `docs/research/act1-coverage.json`
(its `run_parts` map: an entry per relic run part, updated as each is
built) and `scripts/docs_index.py` (to count it); new
scripts `scripts/runsim.py` (driver and choosers' glue),
`scripts/runsim_fixture.py` (log fixtures), `scripts/runsim_replay.py`
(log replay) and `scripts/oracle/` (jjs scripts that write test vectors
from the jar); test data under `engine/tests/data/runsim/` and
`scripts/tests/data/runsim/`; in `scripts/real_game_run.py` and
`scripts/real_game.py` only the shop logging (rules 6) and the shadow;
`scripts/real_game_report.py`'s rules table; docs (this spec, the README,
`docs/concept.md`'s "where things live").

Off limits: `scripts/gauntlet.py` and its record format; the combat
engine's rules, its RNG and every combat stream; `content/packs/*` (run
parts never go there); the codec; the net's inputs;
`py/src/features.rs`; the job runner; every decision the bridge makes
except opening shops.

Outside the repo: none. The jar and its decompiled copies stay out of git
(scratch output of `scripts/oracle/` goes under `results/oracle/`, removed
by its `--clean`).

## Decisions taken (also in docs/decisions.md, provisional)

1. The game's run rules are in Rust (`engine/src/runsim/`, `sts.RunSim`);
   choosers, drivers, the bridge adapter and reports are in Python
   (owner, 2026-11-15: it would end in Rust either way).
2. The simulator speaks CommunicationMod (`state()` in `game_state` shape,
   `command()` takes its commands), so today's rules drive it unchanged.
3. Seed-exact where checkable; unseeded and fight-disturbed rolls by
   distribution (owner).
4. One quirk switch, `rules = game | consistent`, over a listed set
   (owner).
5. Every Ascension level 0-20 (owner).
6. One spec for all of Act 1; the R2 draft folds in (owner; agreed with
   the relics session).
7. Run content in `content/run/*.json`; relic run parts keyed by relic id;
   coverage gets a run status (the relics session's layout, moved out of
   `content/packs/` so no combat loader or explorer listing reads it).
8. Fights are handed back to Python; the fight result carries HP, max HP,
   potions, relic counters and thieves' gold.
9. The run ends when the Act 1 boss dies, before its rewards.
10. The boss comes from the game's rule with a profile that has seen all
    three Act 1 bosses (the list shuffled); an option names the unseen
    bosses for other profiles.

## Outside assumptions (each checked by an early test)

| Assumption | Expected | Checked by |
|---|---|---|
| The jar's `Random` is RandomXS128 (xorshift128+, seeded through murmur3) plus a call counter, as decompiled | identical outputs for every call form | `runsim_random_matches_jar` (step 1), vectors from the jar through `jjs.exe` |
| `jjs.exe` (Nashorn, in the game's JRE) runs a script with `desktop-1.0.jar` on the classpath | runs headless, prints vectors | step 1 |
| The logs' `map` field lists every Act 1 node with its symbol and edges | 90 seeds (in 70 `states.jsonl` files; a file can hold several runs), 90 maps | `runsim_fixture.py` counts (step 2) |
| The engine's JSON parser (`registry.rs`) holds numbers as f64 | 64-bit values (seeds, `randomLong` outputs) lose precision, so every fixture writes them as decimal strings, parsed with `str::parse::<i64>` | steps 1 and 2 |
| The owner's profile has seen all three Act 1 bosses | the logged boss equals the shuffled pick for each seed | `runsim_boss_matches_logged` (step 4) |
| Card pools follow `CardLibrary`'s order for the Ironclad | logged card offers equal the simulated ones on undisturbed floors | `runsim_card_rewards_match_logged` (step 7) |
| CommunicationMod's `game_state` keys per screen (its `GameStateConverter`) | `real_game_run.py`'s functions accept simulated states | `runsim_state_drives_bridge_rules` (step 6) |
| A fight in our engine never draws on the game's run streams; only the game's own fight does (potionRng) | divergences after such fights are classified, not counted | the replay's report (step 17) |

## Verification

Tests written first, named, with their inputs and expected outputs:

- `test_rules_give_the_same_commands_on_recorded_states` (step 0): a
  frozen sample of 300 recorded out-of-fight states (no `combat_state`;
  every out-of-fight screen kind but card rewards) from runs played under
  today's run rules (5: the `run_rules` field, or `RULES_FROM` by start
  time where it's missing), each with the command the bridge sent; driving
  `Bridge.outside` with a fake send (its `card_done` rebuilt from the
  run's earlier states) gives the same command. Card rewards are left out:
  they run the net, and the sim chooser covers them. Passes on the
  unchanged code.
- `runsim_random_matches_jar`: for seeds {0, 1, 42, 2^63-1, a logged
  seed}, the first 200 outputs of each call form (int range, a-b, float,
  float range, long, boolean p, randomLong, the counter-restoring
  constructor, both shuffles) equal the jar's.
- `runsim_map_matches_logged`: for all 90 logged seeds, the Act 1 map's
  nodes, edges and symbols equal the log (? before reveal); in consistent
  mode, the quirk-1 seeds differ only where the bug fires.
- `runsim_monster_lists_match_logged`, `runsim_boss_matches_logged`: each
  logged hallway, elite and boss encounter equals the simulated list's
  entry for its floor.
- `runsim_card_rewards_match_logged`, `runsim_gold_potion_relic_match_logged`,
  `runsim_question_rooms_match_logged`, `runsim_neow_matches_logged`: per
  logged floor, the offer equals the simulated one on undisturbed streams.
- Per event and per relic run part: a test from the decompiled class
  (each option's outcomes with their probabilities, at A0 and A15+), plus
  the logged screens where the event was seen.
- `runsim_quirks_both_modes`: each listed quirk gives the game's result in
  game mode and the fixed one in consistent mode.
- `runsim_leak`: two runs with equal observations and different seeds
  give identical `state()`, legal commands and `outcomes()` lists.
- `runsim_fight_round_trips_relic_counters`: Pen Nib, Nunchaku, Girya
  counters go into the fight and come back changed as the fight changed
  them; a Looter that escapes with gold takes it from the run, one killed
  returns it.

Checks for every step (AGENTS.md forbids full suites): the step's own
tests, `cargo test --test golden`, and the bridge's tests
`scripts/tests/test_real_game*.py` (pytest through the system Python, as
`docs/operating.md` "Machine limits" says). That set is this build's
baseline before step 0.

End-to-end: `python scripts/runsim_replay.py` replays every logged run and
prints, per procedure, seed-exact matches, distribution-only checks and
first divergences, with zero support failures (no logged outcome the
simulator called impossible); and `python scripts/runsim.py play --level
20 --runs 20 --player one-turn` plays 20 whole A20 runs to the boss or a
death with today's rules and the sim card chooser, with no error, writing
`results/runsim/<stamp>.jsonl` (`--clean` removes them).

## Don't guard

Acts 2-4 content, other characters, the boss relic and boss rewards,
profiles other than "all bosses seen" or a given unseen list, modded
games, daily runs and custom modes, StS2, run-layer speed (fights decide
CPU), threading inside `RunSim` (Python drives many runs), saving and
loading a simulated run mid-way.

## Build steps

Each step's check passes before the next starts. Sizes are estimates;
several steps exceed ~50 lines because one jar procedure is one unit.

0. **Pin the bridge's decisions.** From runs under run rules 5, pair each
   out-of-fight state with the command sent next (by order within a run
   folder, from `log.txt`'s `send:` lines; drop retries after a refused
   command, which repeat the screen), and freeze 300 of them, every
   out-of-fight screen kind but card rewards, into
   `scripts/tests/data/runsim/bridge_commands.json`; add
   `test_rules_give_the_same_commands_on_recorded_states` driving
   `Bridge.outside` with a fake send. Build the bridge as its tests do
   (`real_game.Bridge.__new__(real_game.Bridge)`, then set the fields
   `outside` reads, for example `scripts/tests/test_real_game.py`
   `test_card_choice_in_a_fight_takes_the_first`: `run`, `card_done`,
   `errors`, `act1_only`, the output, and stubs for `end_run` and
   `stop_run`), so no `sts`, packs or net load. Check: passes on today's
   code.
   (Python ~120 lines, data ~0.5 MB or trimmed.)
1. **The game's Random.** `engine/src/runsim/jrandom.rs` (RandomXS128 with
   the counter, every call form, `java.util.Random`, both shuffles) and
   `pub mod runsim;` in `engine/src/lib.rs`;
   `scripts/oracle/random_vectors.js` run with the game's `jjs.exe` writes
   `engine/tests/data/runsim/random_vectors.json`, 64-bit values as
   decimal strings (`java.lang.Long.toString`). Check:
   `runsim_random_matches_jar` (`engine/tests/runsim_random.rs`). (Rust
   ~250, JS ~80.)
2. **Log fixtures.** `scripts/runsim_fixture.py` reads
   `results/real-game/*/states.jsonl` (main's checkout, by absolute path,
   from a worktree), splits each file into runs by seed, and writes a
   compact fixture per run (seed as a string, level, map, Neow screen, per
   floor: room type, encounter, offers, rewards, event screens and picks,
   rest choices, chests, boss) to `engine/tests/data/runsim/real_runs.json`.
   Check: 90 seeds from 70 files, 90 Act 1 maps, 24 distinct Act 1 events
   plus Neow, sizes printed. (Python ~200.)
3. **Map.** `MapGenerator`, `RoomTypeAssigner` and the act's map step in
   Rust, chances from `content/run/act1.json`; quirk 1 in both modes.
   Check: `runsim_map_matches_logged` on 90 of 90. **Stop point:** if maps
   don't match, the seed-exact decision is revisited before going on.
   (Rust ~500.)
4. **Streams, monster lists, boss.** The 13 streams with their seeds and
   per-floor reseeding; weak, strong and elite lists with exclusions; the
   boss rule with the profile option. Check:
   `runsim_monster_lists_match_logged`, `runsim_boss_matches_logged`.
   (Rust ~300.)
5. **Vocabulary and loader.** `content/run/` loader, the run atoms in
   `element_names()` with words, `wording.rs` walking `content/run/`,
   load errors naming file, row and key. Check: wording test; a malformed
   row's error test. (Rust ~400, JSON words ~150.)
6. **The run machine and `sts.RunSim`.** Run state, screens, commands in
   CommunicationMod form, `state()` in `game_state` shape, fights handed
   back, `fight_result`, rest sites (heal 30% with the game's rounding,
   smith), treasure rooms, the run's end and record. Check:
   `runsim_state_drives_bridge_rules` (real_game_run.py's functions drive
   a run to the boss with a stub fight player, card rewards skipped);
   illegal-command test.
   **Stop point:** the observation contract is fixed here. (Rust ~800,
   Python tests ~150.)
7. **Rewards.** Card rewards (rarity with the rare offset, room tables,
   the Ironclad pool in `CardLibrary` order, duplicates redraw the card
   only, the upgrade roll), gold, potion drops (with the drop-chance
   ramp), elite relic tiers and pools, chests. Quirk 5. Check:
   `runsim_card_rewards_match_logged`,
   `runsim_gold_potion_relic_match_logged`. (Rust ~400, JSON ~100.)
8. **? rooms and event picks.** The type roll with its ramps, the event
   pick from the eligible pools, the shrine chance; quirks 2 and 4.
   Check: `runsim_question_rooms_match_logged`. (Rust ~250.)
9. **The exact chance source and `outcomes()`.** Enumeration with caps
   per site and in total; the leak test. Check: `runsim_leak`; rarity and
   ? outcomes sum to 1 and match sampling. (Rust ~250.)
10. **Neow.** `act1-neow.json`, the categories and drawbacks, its rng;
    quirk 3 for its curse. Check: `runsim_neow_matches_logged`. (JSON
    ~150, Rust ~100.)
11. **Ascension.** A jar scan lists every Act 1 run-level `ascensionLevel`
    check; each becomes a row or a rule. Check: A0 and A20 logged runs
    replay through steps 3-10 at their level. (Rust ~100, JSON ~50.)
12. **Events, Exordium list (11).** One row set and one test per event,
    extracted from its decompiled class; named primitives where needed.
    Check: each event's test; logged screens. (JSON ~600, Rust ~150,
    tests ~300; one fork per event, one after another.)
13. **Shrines (6) and the eligible one-time events.** As step 12. Check:
    as step 12; the event step's count confirms 25 reachable or corrects
    it (the logs show 24 distinct Act 1 events plus Neow).
14. **Shops.** `act1-shop.json` (2 attacks, 2 skills, 1 power, 2
    colorless, 3 relics, 3 potions, prices with the A16 rule, sale,
    removal cost); the bridge's run rules 6 (open, log, leave) and its
    `RULES_FROM` entry. Check: shop tests from the decompiled classes;
    `test_rules_give_the_same_commands_on_recorded_states` still passes
    except shop rooms, which now open and leave. (JSON ~100, Rust ~250,
    Python ~40.)
15. **Relic run parts.** `act1-run-relics.json`: the R2 draft's 45 relics
    and the run parts of the 12 with both, by their blocks (max HP, rest
    sites, card rewards, deck edits, pickup effects, counters), each from
    the relics session's jar notes and the class; each relic's entry in
    `act1-coverage.json`'s `run_parts` map updated when its run part is
    built (Girya's rest-site Lift sets the counter its combat part reads;
    Ectoplasm blocks every gold gain), and `docs_index.py` counting the
    map. Check: one test per relic; the pre-commit hook. (JSON ~400, Rust ~300, tests ~400;
    one fork per block, one after another.)
16. **What a fight carries back.** Thieves' gold (escaped Looters and
    Muggers take what they stole; a kill returns it), max HP, potions,
    relic counters through `fight_result`. Check:
    `runsim_fight_round_trips_relic_counters`. (Rust ~150, Python ~50.)
17. **Log replay.** `scripts/runsim_replay.py` replays every logged run
    with the game source, switching a stream to observed where it is
    disturbed, and reports per procedure. Check: the end-to-end replay
    report; zero support failures. (Python ~300.)
18. **The driver.** `scripts/runsim.py play` with today's rules
    (`real_game_run.py`, `Bridge.outside`'s inline screens), the sim
    card chooser (`gauntlet.sim_score` over `ladder.play_bench` trial
    fights, as `Bridge.card_pick` does) and a gauntlet player for
    fights; records and `--clean`. Check: the 20-run A20 end-to-end.
    **Long run** (~15-30 min at one turn deep; nothing after it needs its
    result). (Python ~250.)
19. **Shadow in the bridge.** The shadow run beside each live run,
    `shadow.jsonl`, crash-safe. Check: a FakeGame flow and a replay of
    recorded states log no false mismatches; the bridge's tests pass.
    **Stop point:** the live loop must be paused (hold file) to load the
    new controller code. (Python ~200.)
