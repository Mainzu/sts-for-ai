# Blocks M6 and M7: Shield Gremlin, Red Slaver and their encounters as pack data

Status: closed (2026-11-08, built and in use; 4769a62d; decisions "Blocks M6 and M7: ally block at MonsterRolls; Entangled as a pack power"; checkpoint m6-m7-monsters passed 55a7f8e0).

Lane act1-content (charter `lane/act1-content`), groundwork in
`docs/research/act1-inventory.md#Blocks M6 and M7: groundwork for the spec`.
Confirmed under the mandate (lane worker, 2026-11-08).

## How this moves goal 1 or goal 2, and how we'll know

Goal 1 asks for content written as data with first-class custom content.
Three building blocks a data author lacks today land here: a move that gives
block to a random ally, a pattern condition on living allies, and a power
that forbids a card type (any author's "can't play X" debuff). With them the
last two missing Act 1 monsters and the last three Act 1 hallway encounters
(Gremlin Gang, Red Slaver, the full Exordium Thugs) load from files, which
is the lane's stop rule for the monster kind. We'll know by the measure the
charter names: the monster counts in the inventory (missing 2 -> 0), each
new entry loaded, played and checked against the wiki and sts_lightspeed in
tests, and the series checks (golden identical, series_check PASS,
series_speed at most +10%).

## Outcome

Shield Gremlin and Red Slaver are pack monsters in
`content/packs/act1-monsters.json`, Entangled is a pack power there, and the
pack adds the encounters Gremlin Gang, Red Slaver and Exordium Thugs (full);
official content, golden games and official fights are unchanged.

Non-goals: Gremlin Leader's gremlins (Act 2), ascension values (the pack is
A0 like the rest), monster block landing mid-turn (see the deviation below),
replacing the official `exordium_thugs` (it keeps official monsters only),
gauntlet or training use of the new encounters (a later step), relics.

## Behavior

**Values (A0; wiki, checked against sts_lightspeed `MonsterSpecific.cpp`).**
- Shield Gremlin: HP 12-15. Protect: 7 block to a random other living
  monster (itself when none). Shield Bash: 6 damage. It opens with Protect
  (alone too: the game's getMove always sets it), picks Protect while
  another monster lived at its last move; once it rolls without one it picks
  Shield Bash for the rest of the fight (sts_lightspeed sets Shield Bash
  when Protect runs with one monster left and never rolls again).
- Red Slaver: HP 46-50. Stab 13. Scrape 8 + 1 Vulnerable. Entangle: the
  player gets Entangled 1. AI: first turn Stab; before Entangle has been
  used: roll 75 or more -> Entangle, else Scrape unless Scrape twice
  running, then Stab; after Entangle: roll 50 or more and not Stab twice
  running -> Stab, else Scrape unless Scrape twice running, else Stab.
  "Used once" is written with copied moves (Stab and Scrape after Entangle
  are separate move ids), as the inventory planned.
- Entangled (pack power, debuff): while the owner holds it, the owner
  can't play Attack cards; removed at the owner's turn end (`OwnerTurnEnd`
  -> `RemoveSelf`, as Rage). Applied on the monster's turn, it covers the
  player's next turn.

**New building blocks.**
1. Pattern condition `Allies`: holds when another monster in the fight is
   alive. `move_distribution` and the heuristic's `RateKey` cache by
   (kind, slot, moves); both keys gain an `allies` bit, set only for a
   kind whose pattern reads `Allies` (so official keys don't split).
2. Move effect `BlockAlly(n)` (pack JSON `{"BlockAlly": n}`, monster moves
   only): n block to a uniformly random other living monster not showing
   an Escape move, the actor itself when there is none (the game's
   `GainBlockRandomMonsterAction`). It lands when the move runs, before
   any later monster acts: with two or more candidates the monsters' turn
   pauses at `Stage::MonsterActing { slot, next }` with pending
   `ChanceEvent::AllyBlock { slot }` (one outcome per candidate at equal
   probability) and goes on once it resolves (amended 2026-11-15, live run
   83: the block used to land at `MonsterRolls`, after every monster had
   acted). `Allies` reads whether another monster lived when the monster
   last used its move (`CombatState::allies_at_move`; the game's
   `GremlinTsundere` counts at the move), or lives now before its first
   move.
3. Pack power field `forbids: "<card type>"` (Attack, Skill, Power): the
   owner can't play cards of that type while it has stacks. `can_play`
   checks it only when the player holds a generated power (official fights
   pay nothing).
4. Monster moves may `Apply` a pack power (today refused in
   `registry.rs` `monster_effect`); M5's start-power path is the model.

**Failure cases.** `BlockAlly` in a player card, `forbids` with an unknown
type, or `Allies` with a value are load errors with a message. A monster
whose move holds `BlockAlly` and that died before its roll gives no block.

## Fits with

- Official content and golden games: no official monster reads `Allies`,
  holds `BlockAlly` or applies a pack power, and no new stage or chance
  event appears in an official fight. Pinned by `tests/golden.rs`
  (identical) and `series_check`.
- Caches: `tests/monsters.rs::ai_reads_only_moves` extended to the allies
  bit (an `Allies` monster whose ally dies gets the other distribution
  with the same move history).
- Codec: it refuses states with pack content (`codec.rs` 123), so an
  `AllyBlock` state never reaches it; the event gets a tag (5) only to keep
  the match whole (build note, step 2: the planned round-trip test was
  dropped).
- Agent visibility (`agent.rs` 77): during `AllyBlock { slot: k }` intents
  of slots below k are new, as for `MonsterMove`.
- Pack loading: M5's Mad Gremlin and every existing pack entry load and
  play unchanged (`tests/act1_packs.rs`, `tests/monster_packs.rs`).
- Encounters: `tests/encounters.rs::draw_without_replacement` (Gremlin
  Gang draws 4 of 8).
- Speed: `series_speed` at most 10% slower (the swapped-order tool).

**When in doubt:** prefer the game's behaviour as sts_lightspeed codes it
over the wiki's prose, and the wiki over the inventory's notes.

## Scope

May change: `engine/src` (monsters pattern conditions, effects, chance,
state's `MonsterRolls` and `can_play`, registry's pack parsing and writing,
codec, agent visibility, heuristic cache key), `engine/tests`,
`content/packs/act1-monsters.json`, `docs/research/act1-inventory.md`,
`docs/registry.md` or the pack format doc if one names the vocabulary.
Formats it may change: the pack JSON vocabulary (additions only), the
codec's chance-event tags (addition only).

Off limits: official `content/*.json`, `Power::ALL` and the official power
list (no new official power), the net's input layout, `scripts/` beyond a
test that loads the pack, training and gauntlet code.

## Decisions taken (also in docs/decisions.md, on the owner's behalf)

- The ally block is rolled at `MonsterRolls`, after all monsters acted
  (alternatives: a resumable monster turn, true to the game and the
  largest change; rolling the ally with the move a turn early, which shows
  the player the target before the game would).
- Entangled is a pack power with a `forbids` field (alternative: an
  official Entangled power, which shifts the `Gen*` discriminants, codec
  masks and goldens and adds a net column).

## Outside assumptions

- sts_lightspeed's Red Slaver thresholds (75 for Entangle, 50 for Stab
  after it) came back as a summary, not verbatim; the wiki's Red Slaver
  page is the second source. Step 4's test pins the distribution; a
  mismatch between the two sources is recorded in the inventory, the game
  code (Java, `RedSlaver.getMove`, as quoted by the wiki) decides.
- sts_lightspeed never sets `usedEntangle` in what was read; the game does
  (Entangle once, wiki). The pack follows the game.

## Verification

Tests first (each step's check):
- `allies_condition`: a pack monster `[Allies] -> 0, [] -> 1` in a 2-monster
  fight picks 0; after its ally dies it picks 1; same (kind, slot, moves)
  both times.
- `block_ally_outcomes`: Shield Gremlin with three living allies: the
  outcome list after the monster turn has three states, 1/3 each, the 7
  block on a different ally in each; with one ally, no chance event and the
  ally has 7; alone, it has 7 itself.
- `entangled_forbids_attacks`: the player with Entangled 1 has no Attack in
  its legal actions, keeps Skills; at its turn end Entangled is gone.
- `red_slaver_pattern`: first move Stab; from Stab, Entangle 25%; after
  Entangle never Entangle again; post-Entangle Stab 50% unless Stab twice.
- `m6_m7_load_and_play`: Gremlin Gang (4 of 8), Red Slaver and Exordium
  Thugs (pack) load and play to the end with the heuristic agent.
End to end: the series checks (golden identical, series_check PASS,
series_speed <= +10%) at the landing.

## Don't guard

Monsters of other packs reading `Allies` with escapes; `BlockAlly` on more
than one monster in a fight beyond slot order; Entangled stacking.

## Build steps

1. `Allies` condition with both cache keys and the JSON parse/write;
   `allies_condition` and the extended `ai_reads_only_moves`. Check: the
   two tests, `cargo test --release` of monsters and patterns, golden.
2. `BlockAlly` effect, `ChanceEvent::AllyBlock` in `MonsterRolls`, codec
   tag, agent visibility; `block_ally_outcomes`.
   Check: those tests, chance and codec suites, golden.
3. `forbids` on pack powers, `can_play`, pack powers in monster moves;
   `entangled_forbids_attacks`. Check: that test, hooks/packs suites,
   golden.
4. The pack data (Shield Gremlin, Red Slaver, Entangled, three
   encounters), `red_slaver_pattern`, `m6_m7_load_and_play`, inventory
   counts and the deviation note. Check: those tests, the full
   `cargo test --release`, series_check.
5. (Long run, queued) series_speed with the swapped-order tool at the
   lane's HEAD against main; read it against the +10% bar.

Build plan: 5 steps, in-session, on Opus.
