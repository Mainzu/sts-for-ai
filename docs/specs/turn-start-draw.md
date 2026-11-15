# Turn start before and after the draw

Status: closed (2026-11-10, built and in use; d386cb2..de888ed; as built: docs/extending.md "Turn start"; decisions "Turn start before and after the draw, spec decisions").

## Outcome

A turn-start hook runs where the real game runs it: before the turn's draw
(the game's `atStartOfTurn` and `atTurnStart`) or after it (the game's
`atStartOfTurnPostDraw`), including the game's different order on turn 1,
so nets learn in the game's environment.

**Why.** The engine has one turn-start trigger, `OwnerTurnStart`, run after
the draw. That is right for Demon Form and Brutality and wrong for every
turn-start relic, Berserk, Flame Barrier's removal and Poison on its owner.
The two sides differ when a hook adds cards to the hand (hand space for the
draw), to the draw pile (drawn this turn or not) or to the discard pile
(shuffled back during the draw), reads the hand, or ends the fight before
the draw; and pre-draw effects become part of the plain search leaf, which
stops at the draw. Damage, block, energy and buffs land the same either
way.

**How it moves the goals.** Act 1 (`decision/act1-finish`): relics and
powers act at the game's time. Goal 1: generated turn-start powers act at
the game's time too. Nothing on official content changes: the headline,
golden, rules version and every net stay as they are.

**Non-goals** (owner, 2026-11-10): new pre-draw content (Next Turn Block,
Happy Flower, Horn Cleat, Nightmare, ...): this spec only moves existing
entries; any change to what `@tsl1` does (its code follows the new trigger
names and nothing else); a new net input column (decision below); a
front-of-queue field for hooks (see "Turn 1").

## The game's order (the parity source for this spec)

From the game's own code, two decompiles on GitHub that agree
(`Li-Binghui/MySlayTheSpire` and `aeubanks/sts`,
`com/megacrit/cardcrawl/rooms/AbstractRoom.java` and
`actions/GameActionManager.java`; read 2026-11-10; the game isn't installed,
`decision/parity-source`):

- **Turn 2 on** (`GameActionManager`, around line 446): turn-start relics,
  turn-start cards, turn-start powers and orbs run (most queue their
  actions); block is lost (unless Barricade, Blur, Calipers); the turn's
  `DrawCardAction` is queued; then the post-draw relics and post-draw powers
  run. So turn-start hooks resolve after the block loss and before the
  draw; post-draw hooks after the draw.
- **Turn 1** (`AbstractRoom.update`, around line 255): energy and the
  pre-draw combat relics, the opening `DrawCardAction`, then the
  start-of-combat relics, then turn-start relics, post-draw relics,
  turn-start cards and turn-start powers. A hook that adds to the back of
  the queue (Mercury Hourglass, Happy Flower, Berserk, Flame Barrier's
  removal) resolves after the opening draw; one that pushes to the front
  (Brimstone's Strength, Lantern's energy) resolves before it.
- Pre-draw vs post-draw, by the game's classes: pre-draw are the relics'
  `atTurnStart` and the powers' `atStartOfTurn` (Berserk, Flame Barrier's
  removal, Poison, Next Turn Block, Infinite Blades, ...); post-draw are
  `atTurnStartPostDraw` relics (Pocketwatch, Warped Tongs, Gambling Chip)
  and `atStartOfTurnPostDraw` powers (Demon Form, Brutality, Draw Card Next
  Turn). sts_lightspeed's `Player.cpp` 490-700 groups them the same way.

## Behavior

### Two triggers

| Trigger | Runs | Game's name |
|---|---|---|
| `OwnerTurnStart` | the owner's turn start, **before** the draw | `atStartOfTurn` / `atTurnStart` |
| `OwnerTurnStartPostDraw` (new) | the owner's turn start, **after** the draw | `atStartOfTurnPostDraw` / `atTurnStartPostDraw` |

**The player's turn, turn 2 on:** turn count up, cards played reset, block
to 0, energy to 3; the player's `OwnerTurnStart` hooks; if the fight is
over, stop (no draw); the turn's draw (5, plus owed draws); the player's
`OwnerTurnStartPostDraw` hooks; then the player acts. A `Draw` from an
`OwnerTurnStart` hook adds to the turn's draw (one chance event, not two:
drawing n then 5 gives the same hands as drawing n + 5, hand limit
included).

**Turn 1, as the game does it (default):** the opening draw (5, plus
innate cards, plus the character's first-turn draw); then the player's
`OwnerTurnStartPostDraw` hooks (where the start-of-combat relics sit); then
the player's `OwnerTurnStart` hooks; then the player acts. This is the
game's order for every hook that adds to the back of the queue. The
front-of-queue ones (Brimstone, Lantern) only add Strength or energy,
which land the same on either side of the draw, so no hook needs a
front-of-queue mark today; a field for it waits for content where it
matters (decision below).

**The option** (owner's request, for a consistent order): a fight
built with `turn1_pre_draw` runs turn 1 like every other turn
(`OwnerTurnStart`, draw, `OwnerTurnStartPostDraw`). Turn 1 is played while
the fight is built, so the option is a constructor argument
(`sts.Combat(..., turn1_pre_draw=False)`, `Combat.versus(...)`, the
`sts.run` dict-spec key `turn1_pre_draw`, `GameSpec`); the state holds no
field for it and the codec doesn't change. Default off; resetting it is
leaving it out.

**Monsters** have no draw: at a monster's turn start, its hooks of either
trigger run in one pass, in power-slot order, as its `OwnerTurnStart`
hooks run today. So every monster fight is unchanged.

### Which content uses which

- `content/powers.json` (official): Demon Form and Brutality become
  `OwnerTurnStartPostDraw`; Poison stays `OwnerTurnStart` (pre-draw, as the
  game's; on monsters nothing changes, and nothing in the engine poisons
  the player).
- `content/packs/act1-ironclad.json`: Berserk and Flame Barrier stay
  `OwnerTurnStart`, which now means pre-draw, as the game's.
- `content/packs/act1-relics.json`: the start-of-combat relic powers
  (Anchor, Bag of Preparation, Bag of Marbles, Philosopher's Stone's
  Strength, Mark of Pain's Wounds) become `OwnerTurnStartPostDraw`; the
  turn-start ones (Mercury Hourglass, Brimstone, the energy relics, Lantern,
  Ancient Tea Set) stay `OwnerTurnStart`. Their tests keep passing
  unchanged (same states at every decision).
- Generated content (`scripts/gen_content.py`): its `OwnerTurnStart` stays
  the word it writes, and so now means pre-draw (owner: generated moves
  too). Its Brutality-like templates (`LoseHp`, `Draw` at turn start) are
  pre-draw from now on.

### Pack versions (old files keep their meaning)

Content files gain `"version": 2`, where the two triggers mean the above.
In a `"version": 1` file, `OwnerTurnStart` reads as
`OwnerTurnStartPostDraw` (today's meaning), and `OwnerTurnStartPostDraw` is
a load error. So every saved pack (generated packs under `runs/` and
`data/`, test data such as `engine/tests/data/*.json`) loads and plays as
it does today. Every file the repo writes from now on is version 2: the
official files (`official_files()` writes them), the Act 1 packs, the
generator (`VERSION` in `gen_content.py`) and the other pack writers
(`gen_enemy_pack.py`, `mutate_monsters.py`, `scripts/analysis/*`; each
either writes version 2 with the triggers mapped, or keeps writing
version 1, whichever leaves its output's meaning unchanged: the build
names which for each). A version other than 1 or 2 is an error.

### Readers of the trigger

Every place that reads `OwnerTurnStart` today treats both triggers as
"turn start", except where it needs the order:
- **`@tsl1`** (`turn_start_leaf`): projects the player's turn-start hooks
  still to run at the leaf. Before the turn's `OwnerTurnStart` hooks
  (a monster roll pending): both triggers, as today. Once the turn has
  started (as built, the pre-draw hooks run as the rolls finish, so a
  chance event paused at `StartTurn` or the draw pending at
  `TurnStarted`): `OwnerTurnStartPostDraw` only, so a pre-draw hook isn't
  counted twice. `@lcb1` (`leaf_clear_block`) likewise clears the block
  only before the turn's reset (review fix de888ed). Its effect filter is unchanged. On official
  content (Demon Form, Brutality) the leaf is the same as today.
- **The projected leaf** and **`hook_rates`** (`agent.rs`): both triggers
  count as once-a-turn hooks.
- **Net features** (`py/src/features.rs`): both triggers write the
  existing `OwnerTurnStart` column (owner: one column, decision below). The
  trigger list keeps its 14 names and every width.
- **Registry**: parse, `element_names()`, the official-file writer;
  `content/wording.json` words the new trigger (`engine/tests/wording.rs`).
- **Explorer**: words both from `wording.json`.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden fights, rules version | `golden.txt` byte-identical, `rules_version()` unchanged | golden test |
| Official fights, features, nets | byte-identical states and feature arrays; `series_check` PASS | `test_relic_pins.py`, `test_contract.py`, `series_check` |
| Saved version-1 packs | load and play as today | new `v1_pack_replays_unchanged` (step 1, a pinned fight on a copy of today's act1-ironclad pack, a gen-enemies pack and a generated pack with a turn-start `Draw`) |
| Monster turn start | unchanged | golden; v1 pin above |
| `@tsl1` on official content | same leaf on Demon Form and Brutality states | new `tsl1_unchanged_on_official` (step 1) |
| Relics (R1) | the 22 relic tests pass unchanged | `engine/tests/act1_relics.rs` |
| Codec, solved DB keys | encodings unchanged (no new field) | codec tests |
| Search speed | `series_speed` at most 10% slower | job (step 5) |
| Wording, explorer | every new word present | `wording.rs`, explorer tests (3 failed before this spec too) |

## When in doubt

Prefer the game's order (from its code) over a simpler one, and prefer an
unchanged official fight over anything else.

## Scope

May change: the engine's turn sequence, triggers, registry (parse, names,
pack versions, official writer), `@tsl1`, the projected leaf,
`hook_rates`, the runner's `GameSpec`; the Python binding's constructors
and `sts.run` keys; `py/src/features.rs`' trigger mapping (not its
columns); `content/powers.json`, `content/packs/act1-ironclad.json`,
`content/packs/act1-relics.json`, `content/wording.json`; the pack writers'
version and trigger words; the explorer's wording; tests; docs
(`docs/extending.md` triggers, the inventories, facts).

Off limits: the net's input columns (count and order); the codec's
encodings; `golden.txt`; configs, yardsticks and controls; the gauntlet and
run layer; saved packs and data on disk (read as version 1, never
rewritten).

## Decisions taken (provisional; `docs/decisions.md`)

- Two triggers with the game's names: `OwnerTurnStart` before the draw,
  `OwnerTurnStartPostDraw` after (owner).
- Turn 1 follows the game (post-draw hooks, then turn-start hooks, after
  the opening draw); `turn1_pre_draw` gives the consistent order (owner).
- Generated turn-start powers move to pre-draw (owner).
- Old files keep their meaning by pack version (owner).
- One net column for both triggers (owner: a separate column would mostly
  distract the net, as the exhaust pile's did; the split matters mainly to
  the rules of effects that need cards in hand).
- No front-of-queue field until a hook needs it: today's front-of-queue
  hooks only add Strength or energy.

## Outside assumptions

- The game's order above, from decompiled code (two copies agree). Checked
  by step 4's tests, each against a line of that code: Bag of Preparation
  7 cards; Mark of Pain's Wounds not in the opening hand; a pre-draw
  card-adding test hook (into the hand) leaving room for fewer drawn cards
  from turn 2 on but not on turn 1; Mercury Hourglass killing the last
  monster on turn 2 ends the fight with no draw.
- That the search's plain leaf stops at the turn's draw, after the
  monster rolls (so pre-draw effects land in it). Checked in step 3 by a
  test that a Berserk state's plain leaf holds the turn's energy, or the
  test says where the leaf stops instead, and `@tsl1`'s rule above follows
  what it finds. **Found (step 3, `plain_leaf_holds_pre_draw_energy`):**
  the plain leaf is `EndTurn` applied up to the first chance event. When
  every monster's next move is fixed (Cultist) that is the turn's draw,
  after the pre-draw hooks, and the leaf holds their energy; when a
  monster rolls its move (Jaw Worm) it is that roll, before the turn
  starts, as today. `@tsl1`'s rule above already covers both (both
  triggers at a roll, post-draw only at the draw), so it is unchanged.

## Verification

Written first (step 1, passing on unchanged code):
`v1_pack_replays_unchanged`, `tsl1_unchanged_on_official`.

Then:
- `turn_start_order`: a test pack with a pre-draw hook that adds a card to
  the hand and a post-draw hook that records the hand size; on turn 2 the
  added card takes hand space before the draw, on turn 1 it doesn't, and
  with `turn1_pre_draw` it does on turn 1 too.
- `pre_draw_draw_merges`: a pre-draw `Draw 1` gives one chance event of 6
  cards on turn 2.
- `pre_draw_kill_ends_fight`: Mercury Hourglass at 3 damage against a
  3-HP monster on turn 2: the fight is won with no draw.
- `version_rules`: version 1 reads `OwnerTurnStart` as post-draw; version 1
  with `OwnerTurnStartPostDraw` is an error; version 3 is an error.
- `monsters_one_pass`: a monster with both triggers runs them in slot
  order.
- End-to-end: the series checks hold (golden identical, `series_check`
  PASS, `series_speed` within 10%), and the act1 relic and pack tests pass.

## Don't guard

Hooks of both triggers on one power (allowed, each runs at its time); a
pre-draw hook on turn 1 that needs the front of the queue (none exist);
`turn1_pre_draw` on a fight without turn-start hooks (no effect).

## Build steps

1. **Pins** on unchanged code: `v1_pack_replays_unchanged`,
   `tsl1_unchanged_on_official`; decisions into `docs/decisions.md`.
   Check: both pass.
2. **Triggers and versions.** `OwnerTurnStartPostDraw`; pack version 2 and
   the version-1 mapping; the official files rewritten as version 2 (Demon
   Form, Brutality post-draw); wording; the explorer words. No order change
   yet (both triggers still run after the draw). Check: `version_rules`,
   golden identical, step 1's pins, wording, official files check.
3. **The order.** The player's turn as above (turn 2 on and turn 1), the
   merged pre-draw draw, the stop when a pre-draw hook ends the fight,
   `turn1_pre_draw` through the constructors and `sts.run`, monsters in one
   pass; `@tsl1`, the projected leaf, `hook_rates` and the features mapping
   follow. Check: `turn_start_order`, `pre_draw_draw_merges`,
   `pre_draw_kill_ends_fight`, `monsters_one_pass`, the leaf test, golden,
   step 1's pins, `series_check`.
4. **Content.** The Act 1 packs as version 2 (Berserk and Flame Barrier
   pre-draw; start-of-combat relic powers post-draw); the generator and
   pack writers' versions; the game-order tests from "Outside
   assumptions". Check: those tests, `act1_relics.rs`, the pack and
   generator tests.
5. **Speed and docs.** `series_speed` job (old: this spec's start commit;
   new: step 4's); `docs/extending.md` (both triggers, turn 1, the option,
   versions); `act1-relics-potions.md` and `act1-inventory.md` timing
   notes; facts (`lane/act1-content/step`). Check: `series_speed` within
   10%, wording and explorer tests.

No step runs long except step 5's speed job (about 10 minutes, queued).

## Build plan

5 steps, forks (one per step, in order), on Opus. Stop point: step 3's leaf
check, if the plain leaf doesn't stop where the spec assumes (then
`@tsl1`'s rule changes and may touch reads; ask before changing it).
