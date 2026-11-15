# Act 1 inventory: monsters and Ironclad cards against the engine

Step 1 of `lane/act1-content` (2026-11-06, lane worker). A code read at
main 6ef16f9, no engine change. Sources: `engine/src/monsters.rs`
(kinds, encounters, `has_code`), `engine/src/cards.rs` and the `sts`
module's card lists, `engine/src/registry.rs` (what `load_pack` accepts:
`parse_effect`, `monster_effect`, `parse_monster`, `parse_hook`),
`engine/src/effects.rs`, `hooks.rs`, `powers.rs`, and the round-trip tests
`engine/tests/packs.rs` (every official card and power) and
`engine/tests/monster_packs.rs` (13 of 18 official monsters). The game's
side (moves, AI, card text) is from the game's rules as I know them; step 2
checks every number against the wiki and sts_lightspeed before a pack file
is written, and step 3 loads each "writable" card in a test, so a
"writable" here is a reading of the vocabulary, not yet a load.

Three classes:
- **present**: the engine has it today (and whether its pack form loads:
  "writable" if the round-trip tests load it, "blocked" if its behaviour is
  partly code);
- **writable**: missing, and its fight behaviour can be written today as a
  pack entry with the existing building blocks;
- **blocked**: missing (or present as code), and a named building block is
  missing.

## Counts

The current counts are in docs/INDEX.md "Act 1 coverage". The table that
stood here was step 1's reading at 6ef16f9 (git history keeps it).
Encounters are a third kind and are data. The game's Act 1 has 20; all
20 load (the INDEX count). They come from 21 entries: 17 in
`content/encounters.json` and 4 in `act1-monsters.json` (Blue Slaver,
Gremlin Gang, Red Slaver, and Exordium Thugs again, in full with the
slavers in its second slot). Exordium Thugs is in both files, so 17 + 4
entries cover 20 encounters.

## Monsters

Present and writable today (the round trip loads and plays them, 13):
Cultist, Jaw Worm, Acid Slime S/M/L, Spike Slime S/M/L, Fungi Beast,
Looter, Gremlin Nob, Sentry, Slime Boss.

Present, behaviour partly in code (`monsters::has_code`, 5):

| Monster | What is code | Missing building block |
|---|---|---|
| Red Louse, Green Louse | Bite damage (5-7) and Curl Up (3-7) rolled per monster at combat start (`louse::setup`) | M1 rolled values |
| Lagavulin | wakes when it loses HP while asleep, then Stunned and loses Metallicize (`state.rs` 1597) | M2 move switch on an event |
| Hexaghost | Divider's damage from the player's HP when it is chosen (`divider_damage`); Inferno upgrades every Burn | M3 amount from the opponent's HP; M4 upgrade cards in piles |
| The Guardian | Mode Shift: after losing its threshold of HP it switches to Defensive (block 20, Close Up), the threshold grows by 10 (`state.rs` 1587) | M2 move switch on an event (with a growing counter) |

Loaded from `content/packs/act1-monsters.json` (7):

| Monster | Moves and AI | Built in |
|---|---|---|
| Blue Slaver | Stab 12; Rake 7 + Weak 1; 60% Stab (roll 40 or more), no move three times running | step 2 (RollBelow and LastTwo rows, as the lice) |
| Fat Gremlin | Smash 4 + Weak 1, every turn | step 2 |
| Sneaky Gremlin | Puncture 9, every turn | step 2 |
| Gremlin Wizard | Charging twice, Ultimate Blast 25, then three Chargings per Blast | step 2, with copied moves (two Charging/Blast ids per cycle position, as Hexaghost's cycle is written) |
| Red Slaver | Stab 13; Scrape 8 + Vulnerable 1; Entangle once (the player can't play Attacks that turn) | block M7, pack power Entangled; the once-only rule with copied moves after Entangle |
| Mad Gremlin | Scratch 4; Angry 1 (gains Strength when attacked) | block M5, pack power Angry |
| Shield Gremlin | Protect: 7 block to a random other monster; Shield Bash 6 when alone | block M6, a random-ally target and a pattern condition "allies alive" |

Encounters are data since block E1 (`content/encounters.json`, and a pack's
`encounters` key; section "Block E1"). Gremlin Gang (4 of Mad, Mad,
Sneaky, Sneaky, Fat, Fat, Shield, Wizard), Red Slaver and the full
Exordium Thugs (second slot Cultist, Blue or Red Slaver, or Looter) are
pack encounters in `act1-monsters.json` alongside Blue Slaver (M6+M7
step 4; section "Blocks M6 and M7 as built").

## Ironclad cards

Present (35; every official card round-trips as a pack entry,
`every_official_card_round_trips`): Strike, Defend, Bash, Anger, Body
Slam, Clash, Cleave, Clothesline, Flex, Headbutt, Heavy Blade, Iron Wave,
Perfected Strike, Pommel Strike, Shrug It Off, Sword Boomerang,
Thunderclap, Twin Strike, Wild Strike (16 of 20 commons); Bloodletting,
Carnage, Combust, Dropkick, Hemokinesis, Inflame, Metallicize, Pummel,
Rage, Rampage, Rupture, Spot Weakness, Uppercut, Whirlwind (14 of 36
uncommons); Brutality, Demon Form (2 of 16 rares). Six of them are outside
the Ironclad training pool: Metallicize, Demon Form and Rage are held out
(check 9), Whirlwind, Headbutt and Rampage are proving content.

Loaded from `content/packs/act1-ironclad.json` (16, step 3; the table
says how each is written):

| Card | How it is written |
|---|---|
| Disarm | Apply Strength -2 to the opponent; exhaust |
| Flame Barrier | Block 12; a generated power: OwnerAttacked -> PlainDamage to Attacker, OwnerTurnStart -> RemoveSelf (Thorns that expires) |
| Ghostly Armor | Block 10; ethereal |
| Intimidate | Apply Weak 1 to AllOpponents; exhaust |
| Power Through | AddCard Wound x2 to Hand; Block 15 |
| Reckless Charge | Damage 7; AddCard Dazed to Draw |
| Searing Blow | Damage 12 (the base and one upgrade as two entries; its repeated upgrades need C6) |
| Seeing Red | GainEnergy 2; exhaust |
| Shockwave | Apply Weak 3 and Vulnerable 3 to AllOpponents; exhaust |
| Berserk | Apply Vulnerable 2 to Me; a generated power: OwnerTurnStart -> GainEnergy 1 |
| Bludgeon | Damage 32 |
| Double Tap | a generated power as Burst for Attacks: OwnerPlaysCard, CardType Attack -> ReplayCard, ReduceSelf 1; removed at turn end |
| Feed | Damage 10; exhaust; its max-HP gain is a carried resource, off in measured fights (charter) |
| Immolate | Damage 21 to AllOpponents; AddCard Burn to Discard |
| Impervious | Block 30; exhaust |
| Offering | LoseHp 6; GainEnergy 2; Draw 3; exhaust |

Blocked when step 1 read them (24); 18 are loaded from
`act1-ironclad.json` since (True Grit and Armaments with their + entries),
6 are still missing (Warcry, Battle Trance, Dual Wield, Barricade,
Juggernaut, Reaper):

| Card | Building block |
|---|---|
| True Grit, Burning Pact, Second Wind, Sever Soul, Fiend Fire, Exhume | **loaded** by C1 exhaust a card other than the one in play (a pick or by type or all from hand; an exhaust pile; Exhume returns from it) |
| Corruption | **loaded** by C1 and C5 |
| Dark Embrace, Feel No Pain, Sentinel | **loaded** by C2 a trigger "a card is exhausted" (useful only with C1) |
| Evolve, Fire Breathing | **loaded** by C3 a trigger "a card is drawn", with a type condition |
| Entrench, Limit Break | **loaded** by C4 Block and Apply amounts that read a quantity (own block, own Strength) |
| Blood for Blood | **loaded** by C5 a cost that changes in combat (by a counter, by type, for a turn) |
| Infernal Blade | **loaded** 2026-11-12: `Discover` with offer 1 (docs/specs/discovery.md) and the free-this-turn mark |
| Armaments | **loaded** by C6 upgrade a card in combat (and an upgrade link for pack cards) |
| Warcry | **loaded** by C7 a pick from hand to the top of the draw pile (`Pick` kind `HandToTop`, docs/specs/colorless-cards.md step 4) |
| Havoc | C8 play the top card of the draw pile (and exhaust it, C1); **loaded** since docs/specs/act1-singles.md (`PlayTop` with exhaust; `act1_singles.rs` `havoc`) |
| Battle Trance | C9 a replacement on draws ("no more draws this turn") |
| Dual Wield | C10 copy a picked card in hand |
| Barricade | C12 block kept at the start of the turn |
| Juggernaut | C13 a trigger "owner gains block", with random-target damage in a hook (hooks refuse RandomDamage) |
| Reaper | C14 healing, by the unblocked damage dealt |

## Missing building blocks, ordered by entries unblocked

| Block | Unblocks | Entries |
|---|---|---|
| C1 exhaust another card (pick, by type, all; exhaust pile) (built) | True Grit, Burning Pact, Second Wind, Sever Soul, Fiend Fire, Exhume, Havoc (with C8), Corruption (with C5); gives C2's three their trigger | 6 alone, 8 with partners |
| C2 trigger "card exhausted" (built) | Dark Embrace, Feel No Pain, Sentinel | 3 (after C1) |
| C5 cost changes in combat (built) | Blood for Blood; Corruption, Infernal Blade with partners | 1 alone, 3 with partners |
| M2 move switch on an event (a monster hook that sets its next move, with a counter) | Lagavulin, The Guardian | 2 |
| M1 rolled values per monster | Red Louse, Green Louse | 2 |
| C3 trigger "card drawn" (built) | Evolve, Fire Breathing | 2 |
| C4 Block/Apply amounts from a quantity (built) | Entrench, Limit Break | 2 |
| C6 upgrade in combat (and pack upgrade links) (built) | Armaments; with M3, Hexaghost; Searing Blow's repeats | 1-2 |
| E1 encounters as data (built) | Gremlin Gang, Blue Slaver, Red Slaver, Exordium Thugs' slavers | 4 encounters |
| M3 amount from the opponent's HP | Hexaghost (with C6/M4) | 1 |
| M5 non-official powers on monsters (built) | Mad Gremlin | 1 |
| M6 random-ally target and "allies alive" (built) | Shield Gremlin | 1 |
| M7 card-play restriction (built) | Red Slaver | 1 |
| C7, C9, C10, C12, C13, C14 | Warcry, Battle Trance, Dual Wield, Barricade, Juggernaut, Reaper | 1 each |
| C8, C11 (built) | Havoc, Infernal Blade | 1 each |

Two notes on the counts:
- The five present monsters blocked by code play correctly today; their
  block matters only for loading them from files (runtime-registry's stage
  4 removes the Rust tables, so stage 4 must either keep their code or
  build M1 and M2 first). This is the one place where this inventory and
  that lane's next stage meet.
- An upgraded card is a second pack entry ("Bloodletting+" is a separate
  definition, `cards.rs`); packs have no upgrade link (registry-lite's
  out-of-scope list), so the run layer cannot upgrade a pack card at a rest
  site. Fights are unaffected: each missing card is written as two entries.
  (Superseded by C6, 2026-11-10: a pack card entry now carries `upgrade`
  and `max_level`, and the rest site upgrades pack cards through
  `sts.upgrade_name`. Only cards whose upgrade changes more than numbers
  keep a second entry, linked by `successor`, such as True Grit+ and
  Armaments+. See "Block C6 as built".)

## What it changes for the lane

Step 1's plan; steps 2 and 3 and blocks C1-C6, C8, C11, E1 and M5-M7
are built since (sections below). The open blocks are in the table above.

- Step 2 (monsters) can start with the four writable ones: Blue Slaver,
  Fat, Sneaky and Wizard gremlins as pack files with a test each. Red
  Slaver, Mad and Shield gremlins wait for M7, M5 and M6, and the full
  Gremlin Gang (and its headline re-rank) waits for E1 and those three.
- Step 3 (cards) can write 16 cards now (32 entries with upgrades). The
  biggest single block is C1 (exhaust another card): with C2 it unblocks 9
  of the 24 blocked cards, the archetype of Ironclad's exhaust deck.
- Each block is a goal-1 spec candidate (the charter: a card that can't be
  written names a building block); building them waits for stage 4.

## Step 2: the four writable monsters as pack data

Lane worker, 2026-11-06. The four writable missing monsters are pack
entries in `content/packs/act1-monsters.json` (outside the three official
files, so the rules version doesn't change), loaded and played in
`engine/tests/act1_packs.rs`. No engine edit.

| Monster | HP | Moves | Order | Sources agree? |
|---|---|---|---|---|
| Blue Slaver | 46-50 | Stab 12; Rake 7 + Weak 1 | roll 40 or more and not Stab twice running: Stab; else Rake unless Rake twice running; else Stab | yes (wiki, sts_lightspeed `MonsterSpecific.cpp` and `MonsterIds.h`) |
| Fat Gremlin | 13-17 | Smash 4 + Weak 1 | every turn | yes |
| Sneaky Gremlin | 10-14 | Puncture 9 | every turn | yes |
| Gremlin Wizard | 23-25 | Charging (nothing); Ultimate Blast 25 | Charging twice, Blast on turn 3, then three Chargings per Blast | no, on two points (below) |

Two mismatches on the Gremlin Wizard, both settled by
`decision/parity-source` (values from the wiki; behaviour from
sts_lightspeed where it covers it, the wiki where it doesn't):
- **HP**: the wiki gives 23-25, sts_lightspeed 21-25. The pack uses the
  wiki's 23-25 as the rule says, but the wiki is the likelier one to be
  wrong: its own Ascension 7 range, 22-26, is the base plus one at both
  ends, as for every other gremlin, which fits 21-25 and not 23-25. A
  one-number change if a better source turns up.
- **First cycle**: sts_lightspeed starts the charge counter at 0 (three
  Chargings before the first Blast, on turn 4); the wiki's pattern says
  two Chargings and Blast on turn 3, and its patch note "Asc 17 Gremlin
  Wizard no longer attacks a turn early" fits a game counter that starts
  at 1. The pack follows the wiki: sts_lightspeed doesn't cover this
  point correctly, by every other source, so the wiki decides it. The
  decision is in `docs/decisions.md` ("Gremlin Wizard's first Blast on
  turn 3").

What the tests check (all pass): the HP ranges; against a player who only
ends the turn, the move on show and the HP it takes each turn (Puncture 9
and Smash 4 every turn; the Wizard 0, 0, 25, then 0, 0, 0, 25 twice);
the Blue Slaver over 400 seeds of 10 moves: only Stab 12 and Rake 7,
never one move three times running, the first move Stab 238 of 400
(240 expected), Stab 0.542 of all moves against the rule's exact 0.541;
and the greedy agent with the starter deck wins against each one alone on
10 seeds.

Left for later steps: these four fight only in tests and through
`Combat.versus` until encounters are data (E1); Gremlin Gang also needs
the Mad and Shield gremlins (M5, M6), and the Red Slaver needs M7. The
gremlins' escape when a Gremlin Leader dies (Act 2) isn't written.

## Step 3: the sixteen writable Ironclad cards as pack data

Lane worker, 2026-11-06. The 16 missing writable cards and their upgrades
(32 entries) are in `content/packs/act1-ironclad.json`, with three
generated powers (FlameBarrier, Berserk, DoubleTap); outside the official
files, so the rules version doesn't change. Loaded and played in
`engine/tests/act1_cards.rs` (10 tests, all pass). No engine edit.

Every number is from the wiki's Ironclad card list (fetched 2026-11-06)
and checked against sts_lightspeed (`include/constants/Cards.h` for costs,
exhaust and ethereal; `src/combat/BattleContext.cpp` for effects). They
agree on every value except two gaps in sts_lightspeed, settled by
`decision/parity-source` (the wiki decides where sts_lightspeed doesn't
cover a point correctly):
- **Disarm+**: sts_lightspeed applies -2 Strength for both; the wiki and
  the card text say 2(3). The pack uses -3.
- **Seeing Red**: missing from sts_lightspeed's exhaust list; the wiki
  says Exhaust. The pack exhausts it.

| Card | Cost | Entry (base / upgraded) |
|---|---|---|
| Disarm | 1 | Strength -2 / -3 to the enemy; exhaust (Artifact cancels it, tested) |
| Flame Barrier | 2 | Block 12 / 16; FlameBarrier 4 / 6: each hit on the owner deals that much back, removed at the owner's turn start |
| Ghostly Armor | 1 | Block 10 / 13; ethereal |
| Intimidate | 0 | Weak 1 / 2 to all enemies; exhaust |
| Power Through | 1 | 2 Wounds to hand; Block 15 / 20 |
| Reckless Charge | 0 | Damage 7 / 10; a Dazed into the draw pile |
| Searing Blow | 2 | Damage 12 / 16 (only the first upgrade; repeats need C6) |
| Seeing Red | 1 / 0 | Gain 2 energy; exhaust |
| Shockwave | 2 | Weak and Vulnerable 3 / 5 to all enemies; exhaust |
| Berserk | 0 | Vulnerable 2 / 1 on self; Berserk 1: gain 1 energy at each turn start |
| Bludgeon | 3 | Damage 32 / 42 |
| Double Tap | 1 | DoubleTap 1 / 2: the next 1 / 2 Attacks this turn are played twice |
| Feed | 1 | Damage 10 / 12; exhaust (the max-HP gain is a carried resource, off by the charter) |
| Immolate | 2 | Damage 21 / 28 to all enemies; a Burn into the discard pile |
| Impervious | 2 | Block 30 / 40; exhaust |
| Offering | 0 | Lose 6 HP; gain 2 energy; draw 3 / 5; exhaust |

What the tests check: each entry's cost, type, exhaust and ethereal flags
against a table copied from the wiki; each card played alone, with its
damage, block, powers, energy, draws and the cards it adds or exhausts
(Immolate, Intimidate and Shockwave against two slimes); Ghostly Armor
exhausted at the turn's end in hand; Berserk's energy on the next two
turns (4 each); Flame Barrier's damage back on the Jaw Worm's Chomp and
its removal at the next turn; Double Tap(+) doubling the next 1 (2)
Strikes and not a Defend, gone at the turn's end. A greedy player with
the starter deck plus 8 new entries (4 decks covering all 32) beats a Jaw
Worm in 40 of 40 seeds. A mutation check (Flame Barrier+ 5, Offering+
draw 4) fails the two tests that cover them.

Left for later steps:
- **Eight generated cards per deck.** `registry::SLOTS` is 8: a deck binds
  at most 8 distinct pack cards and 8 generated powers. Fights in tests
  stay under it; a run deck holding more than 8 of the new entries (base
  and upgraded count separately) can't be bound. This is the next limit
  for these cards in the run layer, beside the missing upgrade link
  (registry-lite's out-of-scope list).
- The 24 blocked cards wait for their building blocks (C1 first).

## Block C1: exhaust another card (six cards as pack data)

Lane worker, 2026-11-06 (spec `docs/specs/exhaust-cards.md`). The engine
gained the vocabulary to exhaust cards other than the one in play: picks
`ExhaustFromHand` and `ReturnFromExhaust` (a card holding a
`ReturnFromExhaust` pick is never a candidate: the game's "not Exhume",
stated by mechanic), `ExhaustHand` (all, or all but a type),
`ExhaustRandom` (a chance event, `RandomExhaust`, while the hand holds more
than one distinct card), `ScaledBlock` and the quantity `HandCards`. Every
exhaust goes through one engine function, so C2's trigger has one place to
go. True Grit, Burning Pact, Second Wind, Sever Soul, Fiend Fire, Exhume
and their upgrades (12 entries) are in `content/packs/act1-ironclad.json`;
outside the official files, so golden and the rules version don't change.

Numbers: from the wiki's Ironclad card list, checked against sts_lightspeed
(`BattleContext.cpp`, `Actions.cpp`): True Grit Block 7 / 9 with a random
exhaust / a chosen one; Burning Pact choose one, draw 2 / 3; Second Wind
block 5 / 7 per non-Attack exhausted (block computed once, Dexterity and
Frail apply); Sever Soul exhausts non-Attacks then deals 16 / 22; Fiend
Fire 7 / 10 per card exhausted, exhausts itself; Exhume costs 1 / 0, skips
Exhume copies, nothing with a full hand. No disagreement between the two
sources.

Checks (C1 build): `engine/tests/exhaust.rs` 9 pass (the spec's
verification list); all cargo tests pass, golden identical; a mutation
check (Second Wind+ 6, Exhume's exclusion off) fails 2 tests;
`series_check` PASS on 3,104 states (heuristic and product net
bit-identical, every old feature column equal). The net features grew by
six effect columns and three player columns, all zero on existing content
(checked on golden's states and the lookahead rows before re-pinning the
Python pins). `series_speed` (main cf6ca7a against the C1 build, interleaved,
medians, other jobs running): H2 search 1 thread -1.8%, 16 threads +5.9%
over 9 pairs; H1 random combats and clone within noise (5 pairs); under
the +10% bar. Python suites touching features, nets and packs pass on the
branch build (14 files); `scripts/tests/test_render.py` checks the render
names the chance event.

Counts after C1: Ironclad cards missing and blocked 24 -> 18 (missing and
writable-and-written 16 + 6 = 22). The 18 left: Corruption (C5), Dark
Embrace, Feel No Pain, Sentinel (C2, next), Evolve, Fire Breathing (C3),
Entrench, Limit Break (C4), Blood for Blood (C5), Infernal Blade (C5,
C11), Armaments (C6), Warcry (C7), Havoc (C8; its exhaust is now there),
Battle Trance (C9), Dual Wield (C10), Barricade (C12), Juggernaut (C13),
Reaper (C14).

Step-4 sanity (jobs 0301 on main cf6ca7a, 0302 on the C1 build 828b955; the
product on 20 headline sequences, `results/gauntlet/c1-sanity-old.json` and
`-new.json`): identical per sequence, floor by floor (encounter, HP at start
and end, offer, pick); 20 of 20 clear on both. C1 adds pack-only content and
zero-valued columns, so this is the expected result: checkpoint c1-built
passed. Landed with an sts swap (the rebased commit's engine and py sources
equal 828b955's, so its snapshot wheel was installed).

## Block M5: pack powers on pack monsters (the Mad Gremlin)

Lane worker, 2026-11-06 (spec `docs/specs/monster-pack-powers.md`).

Sources for the Mad Gremlin (Ascension 0; higher ascensions for the
record):

| Point | Wiki (slaythespire.wiki.gg, "Mad Gremlin", "Angry") | sts_lightspeed (master: `MonsterIds.h`, `MonsterSpecific.cpp`, `Monster.cpp`) | Game (decompiled `AngryPower`, `AbstractMonster.damage`) | Pack |
|---|---|---|---|---|
| HP | 20-24 (A7+: 21-25) | `{{20,24},{21,25}}` | - | 20-24 |
| Scratch | 4 (A2+: 5) | `attackPlayerHelper(bc, asc2 ? 5 : 4)`, every turn | - | 4, every turn |
| Angry | 1 (A17+: 2) | `buff<MS::ANGRY>(asc17 ? 2 : 1)` | - | 1 |
| Angry's trigger | "Upon receiving attack damage, gains X Strength." | `Monster::attacked`: Strength += Angry on every attack hit, before block (a fully blocked hit counts) | `onAttacked` after `decrementBlock`: `damageAmount > 0` and the type is neither HP_LOSS nor THORNS | attack HP loss (`OwnerLostHp {from: Attack}`) |

One disagreement, on the trigger: sts_lightspeed gains Strength on a
fully blocked hit; the wiki says "receiving attack damage" and the game's
own code (decompiled `AngryPower.onAttacked`, which `AbstractMonster.damage`
calls with the damage left after block) needs unblocked damage. As for the
Gremlin Wizard (`docs/decisions.md`, "Gremlin Wizard's first Blast on turn
3"), sts_lightspeed covers the point but every other source says it covers
it wrongly, so the pack follows the wiki and the game: unblocked attack
damage only, which is the engine's attack HP loss (Thorns-like damage and
Poison are not attacks). It matters only when a Mad Gremlin has block
(Shield Gremlin's Protect in Gremlin Gang, or a 0-damage hit), so not in a
lone fight. The wiki's fandom host refused the fetch (HTTP 402); the
wiki.gg copy was read instead. The decompiled game source is a public
GitHub copy (`Li-Binghui/MySlayTheSpire`, `powers/AngryPower.java` and
`monsters/AbstractMonster.java`).

What the block adds: a pack monster's `start_powers` may name a pack
power (loaded by an earlier pack or earlier in the same pack); the
monster's definition keeps them apart (`MonsterDef.gen_powers`, registry
indices). `registry::bind_monsters` binds them, and those of split
children, after the deck's powers: deck slots never move, a power the deck
already holds shares its slot, more than 8 in all is an error
(`Combat.versus` raises `ValueError`; `new_vs` calls it and panics only
for a caller that skipped the check). The Mad Gremlin and the power Angry
are in `content/packs/act1-monsters.json`. Moves that apply a pack power
are still refused (M5b).

Checks (M5 build): `engine/tests/monster_powers.rs` 7 pass (the spec's
list; the Mad Gremlin takes three Strikes to Strength 3 and then Scratches
for 7); `cargo test --release` at the root 325 pass, 0 fail, golden
identical; mutations (Angry 2; the monsters' powers put before the deck's)
fail 1 and 2 tests. `series_check` PASS on 3,104 states (heuristic and
the product net bit-identical, every column equal) between the branch
base 1ad4938 and the M5 build. Python suites on the branch build, no
re-pin: 217 pass over 19 files (py/tests test_sts, test_content_pack;
scripts/tests contract, lookahead, rates, start_hp, warm_start,
content_selfplay, net, registry, mutate_monsters, gen_content, rust_net,
product, gauntlet, render, versus with the new Mad Gremlin and slot-error
test, gen_powers_read, curriculum); `test_net_search_does_not_leak_threads`
failed once only because the run set `RAYON_NUM_THREADS`, and passes
without it on both builds. `series_speed` (base against M5, 7 interleaved
pairs, other jobs running; search at 1 and 4 threads, not 16, to keep to
the 4-thread cap): random combats +3.9%, clone -0.3%, search 1 thread
+6.2%, 4 threads +5.5% (positive is faster); within noise, under the +10%
bar.

Counts after M5: Act 1 monsters missing and blocked 3 -> 2 (Red Slaver,
M7; Shield Gremlin, M6); missing and written 4 -> 5.

## Block C2: exhaust triggers (three cards as pack data)

Lane worker, 2026-11-07 (spec `docs/specs/exhaust-triggers.md`). A power
hook `CardExhausted` (fires once the card in play is placed, once with the
count of cards exhausted) and a card field `exhausted` (effects when that
copy is exhausted: `GainEnergy` and `Block` only). Dark Embrace, Feel No
Pain, Sentinel and their upgrades (6 entries) and the powers `DarkEmbrace`
and `FeelNoPain` are in `content/packs/act1-ironclad.json`.

Source check (sts_lightspeed, read by a web-fetch agent from the main
session; the wiki pages returned HTTP 402, so this check has no wiki
numbers):
- `BattleContext::triggerAndMoveToExhaustPile`: Dark Embrace queues
  `DrawCards(stacks)` at the bottom of the queue; Feel No Pain queues
  `GainBlock(stacks)` at the bottom, from the raw power amount, not through
  `calculateCardBlock`, so Frail doesn't apply (whether
  `Player::gainBlock` adds Dexterity is unverified; the engine follows the
  game's GainBlockAction: raw, as every hook's block); Sentinel calls
  `player.gainEnergy(up ? 3 : 2)` at once (its comment says the game adds
  it at the bottom; no difference inside one card).
- Numbers: Dark Embrace cost 2 / 1, `BuffPlayer DARK_EMBRACE 1` with no
  upgrade branch (draw 1 either way); Feel No Pain cost 1, amount 3 / 4;
  Sentinel cost 1, block 5 / 8 through `calculateCardBlock` (Dexterity
  applies), energy 2 / 3. The pack entries match.
- Order: a played exhaust card goes through `onAfterUseCard` to
  `triggerAndMoveToExhaustPile`, others to the discard pile, before the
  queued draw or block runs, so the card is placed before the triggers
  fire (the spec's order). At turn end, `discardAtEndOfTurn` queues the
  ethereal exhausts on top, before the hand's discard; Dark Embrace's draw
  is queued behind the discard and the end-of-turn action, so the drawn
  card stays in hand into the next turn, and Feel No Pain's block lands
  before the monsters' turn. The engine adds that draw to the next turn's
  draw (the spec's named approximation).

No disagreement between the pack entries and the source.

Steps 4 and 5 (lane worker, 2026-11-07). Features: the `CardExhausted`
trigger is one more trigger column, and a card's `exhausted` effects are
a held row with that trigger, both in the full layout only. On golden's
states the one new column is zero everywhere and every old column is
equal, so golden rows, the contract pins, the lookahead names and
`test_net`'s training hash were re-pinned (as for C1); the product net's
stored layout gathers the same names on both builds. `series_check` (main
against the C2 build): PASS, 3,104 states, the heuristic and the product
net bit-identical. `series_speed` (interleaved, medians, other jobs
running): a first pass of 7 pairs read search -10.9% at 1 thread and
-13.0% at 16 under heavy load (16-thread runs ranging 576 to 1,532
games/s); a second pass of 9 pairs read +1.7% and -2.5%, under the +10%
bar; random combats +12.5% and clone +12.7% (noise the other way). The
engine's extra work is a zero check per card and per turn start. Mutation
check: dropping per-stack scaling fails three `exhaust_triggers` tests;
firing inline inside `exhaust_card` fails `dark_embrace_draws_after_the_card`.
Engine suites (all but solve) pass after the rebase on main; Python suites
touching features, nets and packs pass on the branch build (test_hp_bonus'
`test_player_spec` and three `test_ladder` end-to-end tests fail on the old
build too: this worktree has no `runs/` data). End to end (step 3's test):
greedy with the six pack cards beats Jaw Worm 40 of 40; a trigger power was
held at an exhaust in 15 of 40.

Sanity (jobs 0422 on main fcb8e28, 0423 on the C2 build 3296495; the
product on 20 headline sequences, `results/gauntlet/c2-sanity-old.json`
and `-new.json`): identical per sequence, floor by floor; 20 of 20 clear
on both. Checkpoint c2-built passed.

Counts after C2: Ironclad cards missing and blocked 18 -> 15 (written as
pack entries 22 -> 25). The 15 left: Corruption (C5), Evolve, Fire
Breathing (C3), Entrench, Limit Break (C4), Blood for Blood (C5), Infernal
Blade (C5, C11), Armaments (C6), Warcry (C7), Havoc (C8), Battle Trance
(C9), Dual Wield (C10), Barricade (C12), Juggernaut (C13), Reaper (C14).

Review (spec-reviewer, fresh context): two must-fix, both fixed. A card
that ends the combat left `unfired_exhausts` nonzero in the finished state
(official Pummel killing the Jaw Worm: the codec wrote the new tag, so an
official encoding changed); `check_over` now clears both counters, and
`a_finished_combat_holds_no_unfired_exhausts` fails without that. The
firing after turn-start hooks had no test; added
`turn_start_exhausts_fire_after_the_turn_start_hooks` (a pack power whose
turn-start hook exhausts the hand, with Feel No Pain: 5 exhausted, 15
block, counters clear). After the fix: engine suites pass, `series_check`
PASS again on the final wheel (3,104 states), re-pinned Python suites
pass. The sanity pair ran before the fix; the fix touches only finished
states, after the last decision, so it can't change play. Left open
(optional): no test that a monster holding a `CardExhausted` power never
fires it (true by construction); the writer's `CardExhausted` output is
never read back from a pack power (official powers only are written).

## Block S1: more pack cards and powers per fight

Lane worker, 2026-11-07 (spec `docs/specs/pack-slots.md`). The first of the
big-picture review's steps between today's packs and a deck or character
made of data: a fight held at most 8 pack cards and 8 pack powers
(`SLOTS = 8`), so the 25 Ironclad cards written as pack entries could not
share a deck beyond 8. Now `CARD_SLOTS = 32` and `POWER_SLOTS = 24`
(`Power::GEN` is `Gen0`..`Gen23`, 54 powers in all, 10 left under the
64-bit held mask). Card ids of slots 0-7 (128-143) and of the 4 variants
(144-147) are where they were, so no stored encoding changes; slots 8-31
take ids 148-195 (`registry::slot_card`, `card_slot`).

Checks: engine suites (all but solve) pass, golden identical; a variant
state's codec bytes are pinned (`variant_state_bytes_are_pinned`, passes
on main and on S1); the limits are tested at 32/33 cards and 24/25 powers,
deck and monster powers counted together; the sparse powers test's pool
now follows `POWER_CAP` (every third of 54 powers is 18, more than a
creature holds). End to end: greedy plays one deck of the 32 step-3 entries
and one of the pack's 25 base cards (C1, C2, step 3), each with the
starter deck, to an end against a Jaw Worm on 20 seeds each (40 of 40 won).
`series_check` (main against the S1 wheel): PASS on 3,104 states, the
heuristic and the product net bit-identical.

`series_speed` (main f6c9a41's engine against S1, interleaved), not yet
read: two passes (7 and 9 pairs) ran beside two 3-thread family jobs and
cargo builds (job 0435's snapshot among them), and the old build alone
ranged 201 to 583 games/s at 1 thread and 612 to 1,652 at 16. The tool's
medians read search -13.3% (1 thread) and -19.4% (16 threads) on the second
pass, -0.9% and -19.1% on the first; the median of the per-pair ratios
reads about -1% and -8%. Clone is about 5% slower on both passes (23.8 to
25.0 ns), the size of the wider binding (40 to 120 bytes in a 744-byte
state). The bar (+10%) needs a pass with no build running beside it;
landing waits for it. If it still reads over, the spec's step 4 interns the
slot arrays. Sanity: job 0435 plays the product on the 20 headline
sequences on the S1 build, read against 0423's `c2-sanity-new.json`.

Also fixed: the curriculum digests and `ARRAYS_PIN` had been stale since
C2's landing (4 Python tests failing on main). Every pinned array was
equal except `rows`, and `rows` gives the old pin back with C2's trigger
column dropped (zero on these states); re-pinned.

Review (spec-reviewer, fresh context): no must-fix; every slot-id site
goes through the helpers, the codec reader refuses ids 148-195 as it
refuses the other slots. Open: a deck of 32 pack entries and 9 distinct
official cards binds and then panics on the pile limit (`PILE_CAP = 40`
distinct ids, `state.rs`), a crash rather than a `ValueError` from Python;
the limit is older than S1, but S1 makes it reachable from a pack deck.
Next: `bind` refuses more than `PILE_CAP` distinct ids, with a test. A
creature holding more than `POWER_CAP` (12) distinct powers panics too
(older, not reproduced).

Fixed (a316373): `bind` refuses a deck of more than `PILE_CAP` (40)
distinct card ids with "deck has N distinct cards, more than 40"
(`refuses_more_distinct_cards_than_a_pile_holds`: 32 pack entries and 8
official cards bind, a ninth official card fails). Ids a fight creates
later (upgrades, statuses) can still reach the pile limit; that is older
than S1 and not guarded. Engine suites (all but solve) pass.

Sanity read, job 0435 (the product on 20 headline sequences, S1 build)
against 0423's `c2-sanity-new.json` (the C2 build): identical on all 20
sequences, floor by floor (encounters, HP, offers, picks). Official play
is unchanged by S1, as predicted.

Speed: queued as job 0454 (main a35376e's examples against a316373's, 25
interleaved pairs, admitted only with 14 idle cores so none of our jobs
runs beside it).

Speed read, job 0454 (ran alone, 13:14-13:17): search at 1 thread -12.4%
on the medians (621 to 552 games/s; median of per-pair ratios 0.858,
range 0.78 to 1.08), 16 threads -4.9% (0.932), clone -3.9%, random
combats +11%. Over the +10% bar at 1 thread, so the spec's step 4 ran.
Why the 120-byte binding cost more than its share of a clone: every hook
pass (`run_hooks_scaled`) copied the whole binding, and search clones the
state at each node.

Step 4 (36587d4): the power and card slot arrays move into an append-only
interned table (`registry::Slots`, `SLOT_SETS`, read without a lock, like
the variants); the binding keeps the slot-set index, the count of bound
powers and the variants by value: 12 bytes, smaller than main's 40. Equal
slot sets get one index in a process, so equality and hashing of states
hold within it; the codec never wrote the slots, so stored bytes don't
change. Debug text of a bound binding prints the arrays as before.

Speed read, job 0455 (ran alone, 13:36-13:40; main a35376e against
36587d4, 25 pairs): search at 1 thread -7.6% (621 to 574 games/s;
per-pair median 0.923, range 0.88 to 1.13), 16 threads +0.7% (1.018),
clone 7% faster (20.9 to 19.5 ns), random combats +8.6%. **Pass** (at
most 10% slower). Open: search_speed plays official content only, where
the binding is always empty and now smaller than main's, yet 1-thread
search stays about 8% slower on both 5-pair and 25-pair reads; the cause
isn't the binding's size (candidates: the 54-power and 196-id constants
in loops or code layout). Not profiled: under the bar, and the next
block that touches the hot path should look first.

Checks on the step-4 wheel: engine suites (all but solve) pass;
`series_check` (main's module against the step-4 wheel) PASS on 3,104
states, the heuristic and the product net bit-identical; Python pack
suites (`test_content_pack`, `test_versus`, `test_registry`,
`test_gen_content`, `test_pack_cards_read`, `test_content_selfplay`,
`test_mutate_monsters`): 50 passed, 1 skipped.

## Block C4: Block and Apply amounts from a quantity (two cards as pack data)

Lane worker's build, 2026-11-07 (spec `docs/specs/quantity-amounts.md`).
Two effects size block and a power by `ScaledDamage`'s `Amount`
(`base + k × quantity`), resolved when they run: `BlockOf(Amount)` gains
the block as is (no Dexterity or Frail; nothing at 0 or less), and
`ApplyOf { power, amount, target }` resolves the amount and then takes
`Apply`'s path (nothing at 0; a negative Strength is a debuff that
Artifact cancels). `Effect::scaled` multiplies both `base` and `k`. The
registry reads and writes them through `amount` and `amount_json`; a
pack's `ApplyOf` of a pack power is refused at load (decisions "act1-content
C4 build"). Entrench, Entrench+, Limit Break and Limit Break+ are in
`content/packs/act1-ironclad.json`. Their numbers are the ones the spec
checked against sts_lightspeed (Entrench cost 2 / 1, double the block;
Limit Break cost 1, exhaust / no exhaust, double the Strength).

Checks: `quantity_amounts` 7 pass (7 block with 2 Dexterity and Frail
doubles to 14, 0 stays 0, a negative amount gains nothing; Strength 3 -> 6,
-2 -> -4, 0 leaves no power entry, Artifact 1 with -2 cancels; Limit Break
exhausts and Limit Break+ is discarded; `scaled` and `target`; the pack's
entries and a card holding both effects with other quantities round-trip
through `card_json`). Engine suites (all but solve): 42 files, 326 pass,
golden identical. End to end: greedy plays a third deck, the four C4
entries with the starter deck, and the base-card deck now holds 27 (with
Entrench and Limit Break): 60 of 60 won against a Jaw Worm.

Features: two scalars, `block_of_k` and `apply_of_k` (the `base` goes in
`block` and in the power's column, as `Block` and `Apply`). On golden's
states, the lookahead rows, the curriculum builds and the content_selfplay
arrays every old column is equal and the new ones are zero, so golden rows,
contract pins and tiny nets, lookahead names and rows, the curriculum
digests, `ARRAYS_PIN` and `TRAIN_PIN` were re-pinned (as for C1 and C2).
Python suites on the C4 wheel: 147 passed, 1 skipped (pack, features, net
and contract suites), and 106 more passed (gauntlet, product, rates,
render, rust_net, start_hp, warm_start). `series_check` (main's module
against the C4 wheel): PASS on 3,104 states, the heuristic and the product
net bit-identical.

Open: `series_speed` (spec step 4) hasn't run yet. The engine's hot path
gains two match arms in `do_effect` and two in the heuristic's deck sum;
official content never reaches them. A monster's `BlockOf` in a hook
while a card is in play gains at once, not after the card as `Block` does
(Curl Up's rule); no content does this, and the spec's "Don't guard"
doesn't name it.

Counts after C4: Ironclad cards missing and blocked 15 -> 13 (written as
pack entries 25 -> 27). The 13 left: Corruption (C5), Evolve, Fire
Breathing (C3), Blood for Blood (C5), Infernal Blade (C5, C11), Armaments
(C6), Warcry (C7), Havoc (C8), Battle Trance (C9), Dual Wield (C10),
Barricade (C12), Juggernaut (C13), Reaper (C14).

Review (spec-reviewer, fresh context): no must-fix. Scope, game numbers
and every verification item checked; the re-pinned arrays compared column
by column against main's (golden_rows, lookahead_rows: the old arrays plus
zero columns; curriculum datasets unchanged; `GAMES_PIN` unchanged).
Open, not needed by any content today: an `ApplyOf` of an official power
with hooks (Metallicize, say) records only `apply_of_k` in the effects
layout, as the grant rows match `Apply` only (`py/src/features.rs`); no
test for the load refusal of `ApplyOf` on a pack power; power hooks using
the new effects aren't counted by `hook_rates` or the turn-start list.

Speed read, job 0461 (ran alone, 14:31-14:35; main 9841ce3's engine, S1
interned, against C4 f4d8d33, 25 pairs): search at 1 thread -9.0% on the
medians (649 to 591 games/s), per-pair median 0.941 (range 0.73 to 1.15);
16 threads -1.1% (0.974; one pair at 0.36, outside load); clone 6% faster,
random combats +1.5%. **Pass**, close to the bar. Suspicious: official
content never reaches C4's two new match arms, so the cost is likely code
layout or inlining in `do_effect` and the heuristic, and it stacks on S1's
-7.6%: about -13% at 1 thread against the engine before S1 (0.923 x 0.941).
Next: one direct read, a35376e's engine against C4, to measure the sum; if
it is over 10%, profile `search_speed` on both before the next block.

Speed sum, job 0462 (ran alone, 14:37-14:41; a35376e's engine, before
S1, against C4 f4d8d33, 25 pairs): search at 1 thread -8.5% on the
medians (639 to 584 games/s), per-pair median 0.909 with every pair
slower (0.82 to 0.95); 16 threads -1.9% (0.980); clone 7% faster, random
combats +8%. Under the bar, so no fix is owed. C4 adds about nothing on
its own (0461's -9% against the S1 build was mostly baseline noise); the
~9% at 1 thread is S1's and real. Jobs run at 2-6 threads, where the
16-thread read (-2%) suggests the cost is smaller, but untested. Worth a
profile (`search_speed` at 1 thread on a35376e and on main) in the next
block that touches the search path; not a lane step of its own.

Struck by 0571 (2026-11-08, "E1 speed re-read (0570, 0571)" below): the
~9% was the tool's fixed run order; with the order swapped the sum reads
about -3% (se 5%), and no profile is owed.

## Block G1: pack cards in the gauntlet's offers

Lane worker's build, 2026-11-07 (spec `docs/specs/gauntlet-pack-offers.md`,
built 369d0f2). `gauntlet.py play --pack <file>` loads a content pack in
the main process and in the two-turn workers (`ladder.play_two_turn(...,
content=)`, passed to `depth_paired.run_guarded`), and adds the pack's base
cards as `gen:<id>` to both halves' reward pools: with act1-ironclad's 27
base cards the pools grow from 21 (train) and 31 (held-out) to 48 and 58,
and offers stay uniform. The setting is recorded as `"pack": "<file>@<content
hash>"` (absent without the flag, so every older file keeps matching), joins
`VARY` and `MATCH_FIELDS`, and needs `--rewards` other than `skip`.

Checks: `test_gauntlet.py` 40 pass (new: the pools with and without a pack;
the setting, the refusal without offers, an `--against` across the pack
setting refused without `--vary pack` and accepted with it, a `gen:` pick
taken; `play_two_turn` hands `content` to `run_guarded`). End to end with
the act1-ironclad pack: the heuristic on 6 headline sequences (`--start
starter --rewards sim --sim-boss`) took 25 `gen:` cards in 60 picks and played
them in later floors; the product two turns deep on the boss floor
(`--one-turn-floors 10`), 2 sequences, finished with `gen:` cards in its
decks, so the workers loaded the pack.

Re-rank reads, queued at 369d0f2 (each `--against` its own control `--vary
pack`, at fixed n): 0463 the one-turn net (500 sequences, control 0.680
clears), 0464 the heuristic (500, control 0.534), 0465 the product (sequences
0-249, control 0.834 on 0-499). Results below when they finish.

### G1 re-rank read (0463, 0464, 0465)

Lane worker's read, 2026-11-07. Each player with the act1-ironclad pack in
the offers against its own control on the same sequences (`gauntlet.py
read`; per-sequence counts from the files' `floors`). 0466 plays the
product's sequences 250-499 into the same file and becomes the reported
product read at n 500; the numbers here for the product are n 250.

| Player | n | Clears control | Clears pack | Change (se) | Train | Held-out |
|---|---|---|---|---|---|---|
| heuristic (0464) | 500 | 0.534 | 0.428 | -0.106 (0.029) | -0.100 | -0.112 |
| one-turn net (0463) | 500 | 0.680 | 0.522 | -0.158 (0.028) | -0.208 | -0.108 |
| product (0465) | 250 | 0.836 | 0.684 | -0.152 (0.035) | -0.168 | -0.136 |
| product (0465 + 0466) | 500 | 0.834 | 0.684 | -0.150 (0.025) | -0.172 | -0.128 |

0466 (2026-11-08) adds the product's sequences 250-499; the n-500 row is
the reported product read. Sequences 250-499 alone change by -0.148, as
0-249 did. Paired over all 500 sequences (clears per sequence from the six
files): the product's lead over the one-turn net moves +0.008 (se 0.033),
so the lead holds; the product's drop beyond the heuristic's is -0.044
(0.037) and the one-turn net's -0.052 (0.037): both about 1.2-1.4 se, a
lead only, and alike for the two depths. Product deaths: Hexaghost 29 ->
60, Slime Boss 5 -> 18, Gremlin Nob 6 -> 14, The Guardian 28 -> 37.

- **The order holds** on the pack setting: heuristic 0.428 < one-turn 0.522
  < product 0.684 (on sequences 0-249: one-turn 0.552, product 0.684).
- **The product's lead over the one-turn net holds:** 0.148 (0.031) on the
  control setting, 0.132 (0.034) with the pack, a change of -0.016 (0.045)
  paired on sequences 0-249. The depth gain does not lean on familiar
  content; the product's ranking stands on Act 1's card pool.
- **Every player loses about 0.1-0.16 clears, the heuristic too.** The
  one-turn net's drop beyond the heuristic's is -0.052 (0.037), 1.4 se: a
  lead for a goal-1 cost of unseen cards on the net, not a result. Most of
  the loss is shared by a player with no learned card values, so it sits
  in the offers and the picks, not in how the net plays the new cards.
- **Why (the offers):** the pools grow from 21/31 to 48/58 with uniform
  offers, so a sequence sees about half as many of the original cards. The
  loss falls with the number of original cards a sequence was offered:
  one-turn net -0.44 (5-9 offered, n 36), -0.22 (10-14, n 234), -0.08
  (15-19, n 197), +0.17 (20-24, n 30); the heuristic -0.29, -0.19, +0.02,
  0.00. The sim chooser still takes 3.1-3.6 pack cards per sequence (skips
  rise only 1.31 -> 1.42 for the one-turn net), judging each card on the
  next floor and the boss one turn deep.
- **No single card carries it.** Sequences holding any pack card lose about
  as much as the mean; the worst holder groups across the three players
  are setup and exhaust cards whose value comes after the sim's horizon
  or from synergy: Feel No Pain (-0.31 to -0.42), Burning Pact (-0.29 to
  -0.47), True Grit (-0.22 to -0.37), Second Wind, Berserk (one-turn net
  -0.30, product -0.33), Dark Embrace. Bludgeon, Shockwave and Double Tap
  holders lose least (about -0.05 to -0.10).
- **Where:** deaths move to the elites and bosses. One-turn net: Three
  Sentries 11 -> 24, Lagavulin 11 -> 24, The Guardian 47 -> 67, Hexaghost
  42 -> 60; the product: Hexaghost 14 -> 27, Slime Boss 2 -> 10, Gremlin
  Nob 1 -> 7. Hallway deaths barely move.

What it changes: checkpoint cards-rerank passes (the order holds and the
product's lead holds). The pack setting is a harder setting, not a test of
the net alone: a pack read of a player should be read against the
heuristic's change on the same setting. The 1.4 se net-specific drop and
the setup-card holders are goal-1 leads for the generated-enemies and
adaptation work (an adapted net on the pack cards would test the first);
the sim chooser's one-floor horizon misvaluing setup cards is a chooser
lead. Next block: E1 (encounters as data), the largest left by entries (4
encounters; with M6 and M7 it completes the Gremlin Gang and both
slavers, the monsters kind).

## Block E1: encounters as data

Built 2026-11-07/08 (spec `docs/specs/encounters-as-data.md`, steps 1-4;
step 5's speed read is the queued series_speed job, read below when it
ends).

- `Encounter` is a one-byte handle (`Encounter(u8)`) with the 17 official
  encounters as consts in the old enum's order; pack encounters take 17
  and up in load order. `name()`, `group()` and `roll_monsters` read the
  definition: official ones from `content/encounters.json` (compiled in,
  checked against the consts by `parse_official`), pack ones from the
  registry.
- A slot is a monster name (official game name or `gen:<id>`), `{"one_of":
  [[...], ...]}` (one `rng.below(n)`, the chosen list expands in place) or
  `{"draw": k, "from": [...]}` (k without replacement, the gremlin spawn);
  left to right, depth first, the old code's draw order.
- Pack checks: unique id, redefinition as for monsters, group, known
  monsters, non-empty `one_of`, 1 <= k <= the list, at most 5 slots for
  any roll (splits counted), at least one monster; unknown keys refused.
- Python: `sts.Combat(deck, "gen:<id>")` and `sts.run` specs take pack
  encounter names; `sts.encounter_group(name)`; `encounter_names()` stays
  the official 15.
- Checks: `official_rolls_frozen` (17 encounters x seeds 0-999: same kinds,
  same number of draws), the file round trip, `pack_encounter_plays`,
  `pack_encounter_refusals`, `draw_without_replacement` (4,000 seeds, each
  of 8 positions within 4 se of half); golden identical; engine suites
  (all but solve) pass; `series_check` PASS against main's `sts` (3104
  states, heuristic and the product net bit-identical).
- Outside assumption (spec): the Blue Slaver encounter is one Blue Slaver,
  a hallway fight; the Gremlin Gang rule (4 drawn without replacement from
  the 8) is what the `draw` node does. Not re-checked against
  sts_lightspeed's encounter tables in this build (no copy in the repo);
  the rule as the spec gives it is kept.

### E1 speed read (0492)

Lane worker's read, 2026-11-08. `series_speed` main f872674's engine
(target/speed-e1/old) against E1 b17e059 (target/speed-e1/new), 25 pairs,
12:24-12:27 (two other jobs started during it: runs 3 on read about 30%
lower on both builds at 16 threads).

| Check | Medians | Per-pair ratio median (q1-q3) | Pairs new faster |
|---|---|---|---|
| random combats/min | +11.3% | 1.103 (1.063-1.126) | 20 of 25 |
| search 1 thread | -9.9% | 0.910 (0.871-0.957) | 2 of 25 |
| search 16 threads | -1.9% | 1.007 (0.968-1.075) | 15 of 25 |

Under the 10% bar, so the spec check passes as written, but at its bar,
and the shape matches 0462's exactly (1 thread about -9% in nearly every
pair, 16 threads flat, random combats +8-11%). An E1 change that slows
search by 9% would not speed random combats by 10%; the shape fits a
position effect instead. The tool ran the builds in a fixed order (old
first), and `search_speed.exe` runs 1 thread after 16 threads, so the new
build's 1-thread search always started right after the old build's
16-thread search, and the old build's random combats right after the new
build's 16-thread search of the run before: whichever build follows a
16-thread burn is slower, plausibly the dev machine's turbo budget spent.

`series_speed` now swaps the order on every other run and prints the
per-run ratio median (9f26511). Re-reads queued: 0570 (the same E1 pair)
and 0571 (0462's pair, a35376e against C4) after it. Checkpoint
e1-encounters waits on 0570: 1 thread within about -3% means E1 costs
nothing and 0462's "S1's and real" line is in doubt until 0571 reads.

### E1 speed re-read (0570, 0571)

Lane worker's read, 2026-11-08. `series_speed` at 9f26511 (order swapped
every other run, 25 runs each): 0570 the same E1 pair as 0492 (14:04-14:08),
0571 0462's pair, a35376e before S1 against C4 f4d8d33 (14:09-14:12). Both
ran alone on the queue. Ratios are new over old per run, split by which
build ran first (13 runs old first, 12 new first), with the geometric mean
over all 25 and its standard error.

| Check | Pair | Old first | New first | All: median | All: geo-mean (se) |
|---|---|---|---|---|---|
| search 1 thread | E1 (0570) | 0.879 | 1.126 | 1.006 | 1.019 (0.041) |
| search 16 threads | E1 (0570) | 1.001 | 0.937 | 0.982 | 1.025 (0.058) |
| random combats/min | E1 (0570) | 1.128 | 0.930 | 1.029 | 1.001 (0.042) |
| search 1 thread | S1+C4 (0571) | 0.886 | 1.131 | 0.962 | 0.975 (0.052) |
| search 16 threads | S1+C4 (0571) | 1.017 | 1.048 | 1.041 | 0.981 (0.036) |
| random combats/min | S1+C4 (0571) | 1.111 | 0.922 | 0.978 | 0.993 (0.031) |

- **The position effect is real and about 12% each way.** At 1 thread the
  build that runs first is about 12% faster (0.88 old first, 1.13 new
  first, in both pairs); for random combats the build that runs second is
  about 11% faster. 0492 and 0462 ran old first every time, which gives
  their -9% at 1 thread and +8-11% random exactly. With the order swapped
  the two halves cancel.
- **E1 costs nothing:** 1 thread +0.6% (median), +1.9% (geo-mean, se 4%);
  random +0.1%. Checkpoint **e1-encounters passes**; no profile owed.
- **S1's "~9% and real" is struck:** the S1+C4 sum reads 1 thread -3.8%
  (median), -2.5% (geo-mean, se 5%), random -0.7%, 16 threads -1.9%: within
  noise of zero and far under the bar. The profile owed under Block C4's
  speed sum is dropped.
- For the tool: a single-pair read has se about 4-5% at 25 runs, so the 10%
  bar is about two se; a cost of 3-5% is below what one read can show.
  Future speed reads use the swapped order (now the default) and read the
  per-run ratio median.

## Blocks M6 and M7: groundwork for the spec

Lane worker's code reading, 2026-11-08 (at 8dea1c1), for one spec covering
Shield Gremlin (M6) and Red Slaver (M7), after which Gremlin Gang, Red
Slaver and the full Exordium Thugs become pack encounters. What the spec
has to settle:

- **Random ally target (M6).** Targets are `Me`, `Opponent`,
  `AllOpponents` and `Attacker` (`effects.rs` 48-58); every non-`Me`
  target of a monster goes to the player (`state.rs` `targets()`), and
  `Effect::Block` always goes to the actor. Monster moves run in
  `end_turn`'s loop and must not wait on chance (`debug_assert` at
  `state.rs` ~1037), while the only random-target chance event is
  player-card-only (`chance.rs` `random_hit`, which reads
  `Stage::PlayingCard`). Choices: make the monster turn resumable at a
  chance node (true to the game, which picks at execution with aiRng;
  the largest change), or roll the ally with the move in
  `Stage::MonsterRolls` (joint move-and-target outcomes in
  `chance_outcomes`; the pick can name an ally that dies before the
  move, and then falls back to self, as the game's action does with no
  ally). One rng stream: a new roll shifts later draws only in fights
  that hold the monster, so official games and golden stay unchanged.
- **"Allies alive" condition (M6).** Pattern conditions read only kind,
  slot and move history (`monsters.rs` `Ai` doc; `ai_reads_only_moves`);
  `chance.rs` `move_distribution` and `heuristic.rs` `RateKey` cache on
  `(kind, slot, moves)`. A living-allies condition must add an allies bit
  to both keys, or be computed outside the cache.
- **Entangle (M7).** No card-play restriction exists in the hook
  vocabulary; `can_play` (`state.rs` 799) is the one place to check it
  (Clash's `only_attacks_in_hand` sat there; since spec `card-rules` it is Clash's `playable_if` condition). Monster moves refuse to
  apply pack powers (`registry.rs` `monster_effect`, 816-818), so a pack
  Entangled needs that opened too. An official Entangled power instead
  would shift the `Gen*` power discriminants (`powers.rs`: Gen slots
  follow `Power::ALL`), the codec masks and goldens, and add a net
  column; a pack power with a "can't play cards of type X" atom avoids
  all of that and is the goal-1 shape. It expires like Rage
  (`OwnerTurnEnd` -> `RemoveSelf`), applied on the monster's turn so it
  covers the player's next turn. "Once" stays written with copied moves.
- **Tests to extend:** `engine/tests/act1_packs.rs` (the pack's monsters),
  `engine/tests/encounters.rs` (`draw_without_replacement` already draws
  4 of 8), `engine/tests/monsters.rs` `ai_reads_only_moves`, golden and
  `series_check` and `series_speed` (with the swapped-order tool).

## Blocks M6 and M7 as built

Lane worker, 2026-11-08 (spec `docs/specs/m6-m7-monsters.md`, commits
1a1d3c9..step 4). Shield Gremlin, Red Slaver and the pack power Entangled
are in `content/packs/act1-monsters.json`, with the pack encounters Gremlin
Gang (4 drawn from Mad, Mad, Sneaky, Sneaky, Fat, Fat, Shield, Wizard), Red
Slaver and Exordium Thugs (slot 1 a louse or a medium slime; slot 2
Cultist, a Blue or Red Slaver, or Looter, a third each). The official
`exordium_thugs` keeps its official-only slots.

Monster tally now: all 7 Act 1 monsters the engine lacked load from the
pack (missing 7 -> 0); the 5 code-backed ones (lice, Lagavulin, Hexaghost,
The Guardian) stay as they were. Act 1's hallway encounters are all
present (the three above as pack entries).

Building blocks added (goal 1: any author can now use them):
- pattern condition `"Allies"` (another monster alive); the move caches
  key on it only for kinds whose pattern reads it;
- move effect `{"BlockAlly": n}` (block to a random other living monster,
  itself when none), picked as chance event `AllyBlock` at `MonsterRolls`;
- pack power field `"forbids": "Attack" | "Skill" | "Power"`;
- monster moves may `Apply` a loaded pack power (`Effect::ApplyPack`).

Values and sources: Stab 13, Scrape 8 + 1 Vulnerable, Protect 7, Shield
Bash 6 confirmed in sts_lightspeed `MonsterSpecific.cpp`; HP (12-15,
46-50) from the wiki (sts_lightspeed's HP table wasn't read). Red Slaver's
thresholds (Entangle on 75 or more, Stab after it on 50 or more) came from
a summary of sts_lightspeed's `getMoveForRoll`, not a verbatim read. A second fetch
(review, 2026-11-08) gave the same 75 and 50, again as a summary; the
wiki page refuses automated reads (HTTP 402). The review recalled the
game's Java as `num >= 55` for Stab after Entangle (unverified); the pack
keeps 50 until a verbatim source settles it (a 5-point shift of one
branch's odds).
sts_lightspeed never sets `usedEntangle` in the code read; the pack follows
the game (Entangle once). sts_lightspeed's Shield Gremlin picks Protect,
and once Protect runs with one monster left it stays on Shield Bash; the
pack writes that as rows `[FirstTurn] -> Protect; [LastMove Bash] ->
Bash; [Allies] -> Protect; [] -> Bash` (the game's `getMove` always opens
with Protect, on itself when alone).

Deviations, recorded:
- The net has no column for `BlockAlly` or `ApplyPack` (`py/src/features.rs`;
  the layout stays): it can't see a Protect or Entangle intent. A
  follow-up for whoever trains on these encounters.
- The codec refuses states with pack content, so `AllyBlock` (tag 5) never
  reaches it.

Checks: `tests/ally_blocks.rs` (allies_condition, block_ally_outcomes,
entangled_forbids_attacks, forbids_unknown_type_is_a_load_error,
allies_with_a_value_is_a_load_error, from the review),
`tests/act1_packs.rs` (m6_m7_values_as_the_wiki, red_slaver_pattern over
400 seeds, m6_m7_encounters_load_and_play); full engine suite passes;
golden identical; `series_check` PASS against main's `sts` (3104 states,
heuristic and the product net bit-identical). The speed read is the queued
series_speed job, read below when it ends.

Landed 2026-11-08 on main with an `sts` swap (the pack's new vocabulary
needs it: `test_versus.py` and `test_render.py` load the pack; both pass on
the new module). `jobs.py impact sts`: none; `impact scripts`: none.

### M6+M7 speed read (0580)

Lane worker's read, 2026-11-08. `series_speed` of main 2021533's engine
(old) against M6+M7 c575ce4 (new), 25 runs, order swapped every other run
(13 old first, 12 new first), 16:19-16:23; the job ran alone on the queue
(0581 and 0577 started after it ended). Ratios new over old per run.

| Check | Old first | New first | All: median | All: geo-mean (se) |
|---|---|---|---|---|
| search 1 thread | 0.897 | 1.105 | 0.952 | 1.000 (0.033) |
| search 16 threads | 0.982 | 1.007 | 0.990 | 0.991 (0.037) |
| random combats/min | 1.077 | 0.906 | 1.012 | 1.001 (0.024) |

- **M6+M7 costs nothing measurable on official paths.** The 1-thread
  median reads -4.8%, but the geo-mean is +0.0% (se 3%) and the two halves
  show the same ~10% position effect as 0570/0571, cancelling; 16 threads
  -1.0%, random +1.2%. All within the -10% bar: checkpoint
  **m6-m7-monsters passes**; no profile of `request_roll`/`allies_bit`
  owed.
- The 1-thread median sitting 5 points under the geo-mean is the median of
  a two-humped sample (old-first ~0.90, new-first ~1.10); with 13 old-first
  runs against 12 the median falls in the lower hump. The geo-mean is the
  better single number for this tool; the bar stays on the median as
  written.

## Block G2: pack encounters in the gauntlet's hard floors

Lane worker's build, 2026-11-08 (spec folded here, built d078201). The
monsters kind is complete (all 7 missing Act 1 monsters load from the pack,
checks above; speed read 0580 passes), so its headline re-rank is next.

- `gauntlet.py play --pack <file>`: a pack's encounters with `group`
  `hallway` join the hard floors as `gen:<id>`. One whose id, lowercased
  with spaces as `_`, is an official hard name replaces it (`Exordium
  Thugs`); the others are added. With act1-monsters the hard pool is the
  game's ten: Blue Slaver, Gremlin Gang, Red Slaver, Exordium Thugs (pack)
  and large_slime, lots_of_slimes, three_louse, two_fungi_beasts,
  exordium_wildlife, looter.
- Each hard floor draws its official encounter as before, then a second
  stream `[GAUNTLET_SEED, i, 2000 + k]` swaps in an added one with
  probability added / (added + the floor's official pool), not the previous
  floor's: 1/10 each. Easy, elite and boss floors and about 70% of hard
  floors equal the pack-less control, so paired reads stay tight.
- Without a pack, or with a card-only pack, sequences are bit-identical
  (sha256 of sequences 0-999 at 350ab46f before and after). `--pack` needs
  `--rewards` only when the pack has no hallway encounters.
- Not covered: `alt_fight` (elite skips) and the analysis scripts that
  rebuild sequences (`boss_replay.py`, `explore.py`, ...) keep the official
  pool; for a pack file they rebuild its hard floors wrong (bosses and
  elites are right). The sim and value choosers still imagine the next
  hard floor from the official pool (`gauntlet.py` value_parts and
  sim_fights draw `POOLS["hard"]`), so with a pack their picks plan for
  slightly the wrong fights (review, optional; unmeasured).
- Checks: `test_gauntlet.py` 46 pass (new: sequences unchanged without a
  pack, the 10-name pool at 1/10 within 4 se over 2,000 sequences with
  every other floor matching, a pack of encounters needs no offers). End
  to end: the heuristic on 6 headline sequences fought all four pack
  encounters; the product two turns deep on sequence 2 fought Blue Slaver,
  Gremlin Gang and Red Slaver (died to The Guardian).

Re-rank reads queued at d078201 (each `--against` its own control `--vary
pack`, fixed n): 0598 the heuristic (500), 0599 the one-turn net (500),
0600 the product (sequences 0-249; the lane's cap leaves about 10 cpu-h).
Checkpoint monsters-rerank passes if the order heuristic < one-turn <
product holds and the product's lead over the one-turn net holds within 2
se paired.

### G2 re-rank, heuristic read (0598)

`gauntlet.py read` of `results/gauntlet/g2-heuristic-starter-simboss-pack-monsters.json`
against `results/gauntlet/heuristic-starter-simboss.json` (500 sequences,
fixed n; the protocol "fail" only says the pack makes the gauntlet harder,
which is expected).

- Clears 0.478 against 0.534: -0.056 (se 0.021); train -0.052 (0.028),
  held-out -0.060 (0.031). Paired end HP -2.43 overall.
- The swap works as built: the 42 sequences that drew no pack encounter
  match the control floor for floor (0 differences); the 458 that drew one
  carry the whole effect (clears -0.061, se 0.023; end HP -2.65, se 0.59).
- Per hard encounter (HP lost per fight; death rate): Exordium Thugs (pack)
  8.7; 4.2%, Gremlin Gang 7.4; 3.8%, Red Slaver 5.7; 2.2%, Blue Slaver 5.3;
  1.2%, against the old ones from lots_of_slimes 6.7; 2.1% and wildlife 4.4;
  3.2% down to looter 0.6; 0.4%. The new monsters sit at the hard end of the
  hallway pool, not outside it. The pack's Thugs cost 8.7 against 6.1 for
  the official `exordium_thugs` in the control (different arrival HP and
  draws; not a like-for-like check of the pack's Thugs).
- Deaths move earlier: 28 at the new encounters, and elites take more
  (Nob 38 against 25, Lagavulin 30 against 19) from the lower HP the
  harder hallways leave, while boss deaths fall (120 against 134) because
  fewer runs reach the boss.

This is one of three reads; checkpoint monsters-rerank waits on 0599 (one-turn
net) and 0600 (product, 0-249). Read script: per-sequence pairing as above
(swap vs none split by any `gen:` floor).

### G2 re-rank, one-turn net read (0599)

The 10-29 net @hpb0.01 (one turn), `results/gauntlet/g2-net1029-hpb0.01-starter-simboss-pack-monsters.json`
against its control `results/gauntlet/net1029-hpb0.01-starter-simboss.json`
(500 sequences, fixed n; the protocol "fail" again only says the pack makes
the gauntlet harder). Same per-sequence pairing as the heuristic read.

- Clears 0.632 against 0.680: -0.048 (se 0.020); train -0.040 (0.029),
  held-out -0.056 (0.027). Paired end HP -2.90 (0.63).
- The swap works as built again: the 36 sequences without a pack encounter
  match the control floor for floor; the 464 with one carry the effect
  (clears -0.052, se 0.021; end HP -3.12, se 0.68).
- The net pays what the heuristic pays: per sequence, the net's cost minus
  the heuristic's is +0.008 clears (se 0.028) and -0.47 end HP (se 0.81).
  So the unseen monsters (no Protect or Entangle intent column) cost the
  net no extra: no goal-1 lead here. On the pack the net leads the
  heuristic by +0.154 clears (se 0.027) and +6.2 end HP (se 1.0), as
  against +0.146 on the control: the order heuristic < one-turn holds.
- Per hard encounter (HP lost per fight; death rate): Exordium Thugs (pack)
  8.5; 2.5%, Gremlin Gang 6.4; 1.9%, Red Slaver 3.5; 0.8%, Blue Slaver 2.9;
  0.8%, against the old lots_of_slimes 5.3; 2.5% and wildlife 3.6; 1.4%.
  The net loses about as much HP as the heuristic to the Thugs (8.5 against
  8.7) and the Gang (6.4 against 7.4) but dies half as often there, and
  halves the Slavers' cost (3.5 and 2.9 against 5.7 and 5.3). The pack's
  Thugs again cost more than the control's official `exordium_thugs` (5.7).
- Deaths move to the elites, as for the heuristic: Lagavulin 18 against 11,
  Sentries 20 against 11; boss deaths are level (104 against 107).

Checkpoint monsters-rerank waits on 0600 (product, sequences 0-249).

### G2 re-rank, product read (0600) and checkpoint monsters-rerank

The product (10-29 net @hpe0.01, `--two-turn --line-seed --step-line`),
`results/gauntlet/g2-net1029-hpe0.01-two-line-step-starter-simboss-pack-monsters.json`
against the headline control `results/gauntlet/net1029-hpe0.01-two-line-step-starter-simboss-a.json`
(sequences 0-249, fixed n; 211 min against an estimate of 185, beside
other jobs; the protocol "fail" again only says the pack makes the
gauntlet harder). Same per-sequence pairing as the two reads above; the
one-turn files are cut to sequences 0-249 for the paired comparisons.

- Clears 0.756 against 0.836: -0.080 (se 0.024); train -0.112 (0.036),
  held-out -0.048 (0.032). Paired end HP -3.78 (0.83).
- The swap works as built: the 19 sequences without a pack encounter match
  the control floor for floor; the 231 with one carry the effect (clears
  -0.087, se 0.026).
- The product pays what the one-turn net pays: on sequences 0-249 the
  one-turn net's cost is also -0.080 (se 0.028; on 0-499 it was -0.048, so
  the first half is the harder one), and the product's cost minus the
  net's is +0.000 clears (se 0.039), -0.24 end HP (1.08). Two turns of
  search buy nothing extra against the new monsters, and lose nothing.
- **Lead over the one-turn net**: +0.148 clears (se 0.034), +6.60 end HP
  (1.17) on the pack, against +0.148 (0.031), +6.84 (1.21) on the control:
  the lead holds unchanged. Train +0.096 (0.053), held-out +0.200 (0.044).
- **Order** on sequences 0-249 with the pack: heuristic 0.504 < one-turn
  0.608 < product 0.756. Checkpoint monsters-rerank **passes**.
- Per hard encounter (HP lost per fight; death rate): Exordium Thugs (pack)
  6.1; 1.7%, Gremlin Gang 4.6; 0.7%, Red Slaver 2.9; 0.9%, Blue Slaver 2.6;
  0.0%, against the old lots_of_slimes 4.4; 1.6%, large_slime 2.8; 0.0%,
  wildlife 2.3; 1.0%, looter 0.0; 0.8%. The new monsters sit at the hard end
  of the pool, as for both other players.
- Deaths: Gremlin Nob 7 against 1 on the control, the Guardian 21 against
  17, Hexaghost 15 against 14; 5 deaths at the new encounters. The lower HP
  the harder hallways leave shows at the Nob first.
- **Open (parity):** the pack's Exordium Thugs cost more than the
  official `exordium_thugs` in the control for all three players (heuristic
  8.7 against 6.1, one-turn 8.5 against 5.7, product 6.1 against 3.2). Arrival HP and
  draws differ, so this is not a like-for-like check, but a gap of about 3
  HP in the same direction three times suggests the pack's Thugs are a
  harder group than the official one. A one-encounter replay of both on
  the same decks would settle it (not run: the lane is at its cap).

What it means for the lane: the real Act 1 hallways, written as data,
cost every player the same and open no zero-shot gap for the net or the
search, so the monsters kind is done with its checks recorded. The lane
closes at its CPU-hour cap with the cards kind unfinished (C3 card drawn
and C5 cost changes not built).

### Thugs parity replay (0676)

Lane worker, 2026-11-09 (`scripts/analysis/encounter_parity.py`,
`results/parity/thugs-net1029-hpb0.01.json`). Every Thugs floor of the
one-turn net's pack file (242, pack Thugs) and of its control (342, official
`exordium_thugs`) rebuilt with the deck and arrival HP it had, and played
one turn deep (the 10-29 net @hpb0.01) on both versions, 6 seeds each:
3,504 pairs.

- Both versions on the same decks: HP lost official 5.57 (0.12), pack
  8.85 (0.17), pack minus official +3.28 (0.15), wins -0.009 (0.002). The
  same from either file's decks (+3.34 and +3.20), so the gap is not a
  deck or arrival-HP effect.
- Split by the monster in slot 2: Cultist official 3.73 (0.19) against
  pack 3.65 (0.23), Looter 7.23 (0.15) against 7.01 (0.18): level within
  1 se. The pack's own slot-2 options cost Blue Slaver 14.33 (0.36) and
  Red Slaver 17.59 (0.54), drawn about a third of the time between them.
  Each pairing of slot 1 with Cultist or Looter is level too (the largest
  gap, Cultist + Green Louse, 3.75 against 3.22, under 1 se pooled).
- So the ~3 HP the three G2 reads saw is the Slavers the real game's
  Exordium Thugs can hold (MonsterHelper's humanoid slot: Cultist, a
  Slaver or Looter) and the official-only `exordium_thugs` lacks; the
  pack's shared monsters play as the official ones. No pack bug, parity
  closed. A Slaver next to a medium slime is the hardest hallway pair in
  the pool (Red Slaver + Acid Slime (M) 22.9 HP, deaths 0.089).

## Block C3 as built: draw triggers (two cards as pack data)

Lane worker, 2026-11-09 (spec `docs/specs/draw-triggers.md`; built
f47a9e3, e26b176). A power hook `CardDrawn` with condition `CardType
Status` fires once per Status card its owner draws, one card at a time,
where the stage machine next reaches the player's turn. A counter
(`unfired_draws`) holds the Status cards still to fire; it counts only
while the player holds a pack power with such a hook, so official states
and encodings never change (codec tag 4 only when nonzero). Evolve (1 / 2)
and Fire Breathing (6 / 10) load from `content/packs/act1-ironclad.json`.

Source check (spec step 1). sts_lightspeed `CardManager::draw`
(src/combat/CardManager.cpp, master, read 2026-11-09): per Status drawn,
`addToBot(DrawCards(evolve))` and `addToBot(DamageAllEnemy(fireBreathing))`;
per Curse, only the Fire Breathing hit. `Actions::DamageAllEnemy` calls
`Monster::damage` with the raw amount: no Strength, Weak or Vulnerable;
block absorbs it; it never calls `Monster::attacked`, so Angry, Curl Up,
Malleable and Thorns don't react. The engine's `PlainDamage` matches: it
goes through `take_damage` with `HpLossFrom::Any`, so the Mad Gremlin's
Angry (attack HP loss) doesn't see it either.

- Mismatch with the spec: its firing rules say each Fire Breathing hit
  "is seen by per-hit hooks such as Angry". In the game and in the engine
  it isn't (the damage isn't attack damage). The per-card firing still
  matters for hooks on any HP loss and for the hit count against block,
  so the decision stands; the spec line is wrong.
- Curse draws don't fire Fire Breathing (the engine has no Curse type,
  spec non-goal).

Checks: `tests/draw_triggers.rs` (every_entry_loads_as_the_source,
evolve_draws_per_status, evolve_full_hand_draws_nothing_more,
evolve_chains, fire_breathing_hits_per_status, no_trigger_without_draw,
drawn_by_a_card_fires_after_it, load_refuses_what_cant_fire_per_card,
the_counter_round_trips, greedy_plays_decks_of_them_to_an_end, and from
the review dark_embrace_draws_count, chance_outcomes_with_evolve); full
engine suite passes; golden identical. End to end: greedy with the
starter deck plus Evolve, Fire Breathing, Reckless Charge, Power Through
and Wild Strike beats Three Sentries 40 of 40; a Status was drawn with a
trigger power held in 34 of 40.

Features (step 3): the `CardDrawn` trigger column joins the full layout
only. On golden's states every old column is equal and the new one zero,
so golden rows, contract pins and tiny nets and the lookahead names were
re-pinned (as for C2). test_sts, test_content_pack, test_contract,
test_lookahead on the C3 wheel: 61 passed. `series_check` (main 687bff4's
module against the C3 wheel): PASS on 3,104 states, the heuristic and the
product net bit-identical.

Step 4: `series_speed` 0682 passes (below). Sanity (jobs 0686 on main
687bff4, 0687 on the C3 build e26b176; the product on 20 headline
sequences, `results/gauntlet/c3-sanity-old.json` and `-new.json`; 0683 and
0684 were re-added as these at 2.2 GB): identical per sequence, floor by
floor; 20 of 20 clear on both. Checkpoint c3-built passed.

Review (spec-reviewer, fresh context): three must-fix, all test gaps, all
fixed (the code was right on every path). The "counted only while held"
check was vacuous (the turn drains the counter after a whole card), now
read at a pause inside a card; mutation: dropping the guard fails it
(golden doesn't see that mutation, against the spec's wording). Added
`dark_embrace_draws_count` (C2's draws count) and
`chance_outcomes_with_evolve` (listed outcomes sum to 1 and no state at
the player's turn holds unfired draws, listed and 200 sampled). The
scaled-firing mutation fails `fire_breathing_hits_per_status`. Open,
unverified and older than C3: `request_draw` overwrites a pending `Draw`
(two `Draw` hooks in one firing could lose a draw), and the heuristic's
`PlayerTurn` with a pending `Draw` resets block and energy; Evolve reaches
both more often. The spec's "no decision point with the counter nonzero"
means the player's turn (a pick inside a card may see it, as in the game).

Counts after C3: Ironclad cards missing and blocked 13 -> 11
(written as pack entries 27 -> 29). The 11 left: Corruption (C5),
Blood for Blood (C5), Infernal Blade (C5, C11), Armaments (C6), Warcry
(C7), Havoc (C8), Battle Trance (C9), Dual Wield (C10), Barricade (C12),
Juggernaut (C13), Reaper (C14).

### C3 speed read (0682)

Lane worker's read, 2026-11-09. `series_speed` of main 687bff4's engine
(old) against C3 e26b176 (new), 25 runs, order swapped every other run (13
old first, 12 new first), 16:19-16:22; it ran alone on the queue. Ratios
new over old per run.

| Check | Old first | New first | All: median | All: geo-mean (se) |
|---|---|---|---|---|
| search 1 thread | 0.907 | 1.024 | 0.955 | 0.951 (0.030) |
| search 16 threads | 0.978 | 0.993 | 0.984 | 0.997 (0.016) |
| random combats/min | 1.064 | 0.978 | 1.024 | 1.035 (0.019) |

- **Within the -10% bar on all three**: the speed part of checkpoint
  c3-built passes. The 1-thread read is the weakest (-4.5% median, -4.9%
  geo-mean, se 3%), and its halves show the ~10-point position effect of
  0570/0571/0580 again (old-first low, new-first high); their average,
  -3.4%, is under 1.5 se from zero. The only new work on official paths
  is one check per draw (`holds_draw_hook`, a scan of the pack powers in
  play, empty on official content); no profile owed.

## Block C5: cost changes, source check (spec `docs/specs/cost-changes.md`)

Lane worker, 2026-11-09, build step 1. Costs re-checked verbatim in
sts_lightspeed's `include/constants/Cards.h` (`getEnergyCost`, master):
`BLOOD_FOR_BLOOD` returns `upgraded ? 3 : 4`; `CORRUPTION` (with
`BARRICADE`) returns `upgraded ? 2 : 3`. Both agree with wiki.gg and the
pack entries (Blood for Blood 4 / 3, Attack, 18 / 22 damage; Corruption
3 / 2, Power). The four entries are in `content/packs/act1-ironclad.json`;
the tests (`engine/tests/cost_changes.rs`) compile against stubs (the new
fields parse and change nothing) and fail only on the missing behaviour.
Known difference kept from the spec: an Exhumed Blood for Blood counts
the HP losses from while it was exhausted (sts_lightspeed's
`CardManager::onTookDamage` skips the exhaust pile).

## Block C5 as built: cost changes in combat (two cards as pack data)

Lane worker, 2026-11-09 (spec `docs/specs/cost-changes.md`; built 9dcfbdb,
ecc2cc2, f1590d4, ff7c502). `CombatState::cost_of` gives a card's cost
in play: its base cost, less one per HP loss for a card with
`cost_less_per_hp_loss` (floored at 0), then capped by a held power's
`sets_cost` for the card's type; X-cost and unplayable cards are
unchanged. Legality, the energy spent and the greedy agent read it. A
counter `times_lost_hp` counts the player's HP-loss events, only up to
the largest base cost of a bound card with the field (0 for official
content, so official states and encodings never change; codec tag 5
only when nonzero; part of the hash). A power's `exhausts_played` names
a card type that exhausts when played, through `exhaust_card`, so C2's
triggers fire. Blood for Blood (4 / 3) and Corruption (3 / 2) load from
`content/packs/act1-ironclad.json`.

Checks: `tests/cost_changes.rs` (every_entry_loads_as_the_source,
blood_for_blood_costs_less_per_loss, counter_capped_and_off_without_card,
corruption_skills_cost_zero_and_exhaust, corruption_leaves_x_and_unplayable,
second_corruption_changes_nothing, load_refuses_bad_rules,
entries_round_trip, the_counter_round_trips,
greedy_plays_decks_of_them_to_an_end); 52 engine suites pass; golden
identical. Greedy with the C5 cards beats Jaw Worm 40 of 40; Blood for
Blood played below base cost in 36 of 36 plays, Corruption exhausting a
Skill in 40 of 40. Mutation (legality on the base cost) fails
blood_for_blood_costs_less_per_loss. Features: one card column
`cost_less_per_hp_loss`, full layout only; on golden's states every old
column is equal and the new one zero; re-pins as for C3; the product
net's gathered layout is unchanged (59 card columns). `series_check`:
PASS on 3,104 states. Review (spec-reviewer): two test gaps fixed (an
unblocked monster hit counts as a loss; the counter is in the hash).

Step 4: `series_speed` 0741 passes (below). Sanity (jobs 0742 on main
a3b81b0, 0743 on the C5 build d0127a6; the product on 20 headline
sequences, `results/gauntlet/c5-sanity-old.json` and `-new.json`):
identical per sequence, floor by floor, settings identical; 20 of 20
clear on both. Checkpoint c5-built passed.

Counts after C5: Ironclad cards missing and blocked 11 -> 9 (written as
pack entries 29 -> 31). The 9 left: Infernal Blade (C11, with "costs 0 this
turn" for one card, a spec non-goal of C5), Armaments (C6), Warcry
(C7), Havoc (C8), Battle Trance (C9), Dual Wield (C10), Barricade (C12),
Juggernaut (C13), Reaper (C14).

### C5 speed read (0741)

Lane worker's read, 2026-11-09. `series_speed` of main a3b81b0's engine
(old) against C5 d0127a6 (new), 25 runs, order swapped every other run
(13 old first, 12 new first), 21:49-21:54; no other queue job ran. Ratios
new over old per run.

| Check | Old first | New first | All: median | All: geo-mean (se) |
|---|---|---|---|---|
| search 1 thread | 0.966 | 1.071 | 1.001 | 0.977 (0.031) |
| search 16 threads | 0.945 | 0.924 | 0.930 | 0.939 (0.032) |
| random combats/min | 1.015 | 0.949 | 0.992 | 1.018 (0.029) |

- **Within the -10% bar on all three**: the speed part of checkpoint
  c5-built passes.
- The 16-thread read is the weakest (-7.0% median, -6.1% geo-mean, about
  2 se) and, unlike the 1-thread read, both halves agree, so it may be
  real rather than the position effect. C3's read of the same check was
  -1.6%. The new work on official paths is `cost_of` at each legality
  check and the counter's cap test on each HP loss (cap 0 on official
  content). Single-thread search, the same code per game, shows nothing,
  so a per-game cost would have to appear only under 16 threads; machine
  load from other work (not queue jobs) is the likelier cause. Not
  profiled; the next block's speed read shows whether it stays.

## Block C6 as built: card upgrades as data (Armaments, Searing Blow's repeats)

Owner-led session, 2026-11-10 (spec `docs/specs/card-upgrades.md`; built
3e2bcc8, 12ab5e8, 44e9d6a, 4095723, 18e9663, 228cea5 on
`lane/act1-content`). A card entry says what an upgrade changes:
`"upgrade": {<path>: <change>}` (a number's change added at each level, a
constant or an expression of `n`; a keyword set from level 1; cost floored
at 0) and `"max_level"` (default 1; `null` as far as the numbers fit).
`content/cards.json` is now 65 entries for the 64 kinds (FTL keeps an `X+`
entry: its upgrade changes a row condition's number) and
`act1-ironclad.json` 34 entries (True Grit and Armaments keep `X+`
entries); both load to the definitions the old files gave, field by field
(`upgrades.rs` pinning tests on fixture copies). X cost and Unplayable are
costs -1 / -2 behind `CardDef::cost()`, `x_cost()`, `unplayable()`; old
flags and `X` / `X+` pairs still load. Level 0 and 1 are a card's id pair
(for pack cards a slot's two ids, so `gen:X+` now shares `gen:X`'s slot);
level 2 and up are per-copy variants (`Overrides` gains a level), named
`X+<n>`. A general upgrade raises a card one level, never a status.
Armaments (cost 1, Skill, Block 5, upgrade one card in hand; one distinct
candidate is upgraded at once) and Armaments+ (every card in hand) load from
the pack, checked against wiki.gg and sts_lightspeed (`Cards.h`,
`BattleContext.cpp`, `Actions.cpp`, `CardInstance.cpp`). `sts.upgrade_name`
and `sts.base_name` serve the run layer: the rest site upgrades pack cards
(`gen:Searing Blow+` -> `gen:Searing Blow+2`).

Checks: engine suites all pass (new: `upgrades.rs`, `upgrades_old_pack.rs`,
`armaments.rs`); golden identical, `rules_version()` unchanged. Searing
Blow at levels 0-4 deals 12, 16, 21, 27, 34 (12 + n(n+7)/2). Features: new
columns `pick_upgrade`, `upgrade_hand` (cards, rows, monster intents) and
`pick_upgrade_from_hand` (player); before re-pinning, every old column was
equal to main's build on the 3,104 fixed states (effects, ids, lookahead)
and content_selfplay's round-0 arrays, the new ones zero; re-pinned as C4
(golden_rows, contract pins and tiny nets, lookahead names and rows,
curriculum digests with datasets unchanged, ARRAYS_PIN, TRAIN_PIN;
GAMES_PIN unchanged). Python suites on the C6 wheel: 144 passed, 1 skipped,
plus 127 passed in the re-pin set. `series_check`: PASS on 4,228 states
(fixed states plus starter decks with Anger, Body Slam, Rampage, Whirlwind,
FTL), heuristic and the product net bit-identical. End to end: `gauntlet.py
play heuristic --start starter --rewards sim --rest sim --pack
content/packs/act1-ironclad.json`, 6 sequences: sequence 3's rest site
upgrades `gen:Shockwave`. Review (spec-reviewer): no must-fix; one optional
finding fixed (an explicit `max_level: 255` past the number range loaded
silently).

Deviations from the spec, each recorded in docs/decisions.md:
- Searing Blow's damage leaves i16 at level 253, so `max_level: null` means
  "as far as the numbers fit" (Searing Blow: 252), not 255.
- The level-2 `match_level` test was dropped: `AddCard` names official
  cards only, and no official card goes past level 1.
- A pack card the deck holds only upgraded builds its level-0 id as level
  1, so Blood for Blood+'s HP-loss counter keeps its cap of 3.
- The gauntlet's `upgradable()` keeps the old rule for official cards
  (their `+` must be in `sts.deck_card_names()`), so official rest choices
  are unchanged. Found on the way: held-out `check9` cards (Metallicize and
  the rest) are never upgraded at the rest site, before and after C6.
- Armaments+ never upgrades a status (wiki); sts_lightspeed's
  `UpgradeAllCardsInHand` would upgrade a Burn in hand.

Amendment 1 (owner, 2026-11-10; built the same day): a unique upgrade is
named by its base, `"successor": "<id>"`, instead of being found by the
name `X+`; FTL, True Grit and Armaments use it. Load errors for a missing,
shared or chained successor. Engine suites pass; `series_check` PASS
again on 4,228 states; gauntlet offers unchanged (32 base cards).

### C6 speed read (0790)

`series_speed` of main 3feb230's engine (old, `target/speed-c6/old`)
against C6 4095723 (new; official paths unchanged since), 25 runs, order
swapped every other run, 4 threads booked, queue busy alongside. Per-run
ratio medians, new over old: random combats/min +0.6%, search 1 thread
-1.1%, search 16 threads +1.3% (medians of the runs: +1.9%, -2.5%,
+1.5%). Within the -10% bar on all three: the speed check passes.

Counts after C6: Ironclad cards missing and blocked 9 -> 8 (written as
pack entries 31 -> 32). The 8 left: Infernal Blade (C11, with C5), Warcry
(C7), Havoc (C8), Battle Trance (C9), Dual Wield (C10), Barricade (C12),
Juggernaut (C13), Reaper (C14).

## Pack-pick split read (0627-0630, lane pack-pick-split)

Headline setting with the act1-ironclad pack offered and `--pack-picks
originals` (the chooser may take only original cards or skip), sequences
0-499, read against each player's pack file (g1) and its plain control
(`docs/specs/pack-pick-split.md`).

| player | plain | pack (g1) | originals only | vs pack | vs plain | share of the drop recovered |
|---|---|---|---|---|---|---|
| heuristic | 0.534 | 0.428 | 0.304 | -0.124 (se 0.025) | -0.230 (0.028) | -1.17 |
| one-turn net @hpb0.01 | 0.680 | 0.522 | 0.382 | -0.140 (0.027) | -0.298 (0.029) | -0.89 |

Share recovered = (originals - pack) / (plain - pack). Both players lose
more, not less, when barred from the pack cards: the stop rule's fail
(both under a quarter), and by a wide margin. HP at the boss on sequences
that reach it in both files: heuristic 50.8 vs 56.2, net 55.8 vs 61.0.
Train and held-out move the same way (vs plain: heuristic -0.276 /
-0.184, net -0.388 / -0.208).

Why: the pack drop is dilution, and the pack cards the chooser takes
make up part of it rather than causing it. Picks per sequence:

| player | file | picks | originals | pack | originals offered |
|---|---|---|---|---|---|
| heuristic | plain | 8.03 | 8.03 | 0 | 28.9 |
| heuristic | pack | 7.87 | 4.78 | 3.09 | 14.1 |
| heuristic | originals only | 5.98 | 5.98 | 0 | 13.6 |
| net | plain | 8.48 | 8.48 | 0 | 29.4 |
| net | pack | 8.20 | 4.76 | 3.44 | 14.2 |
| net | originals only | 6.26 | 6.26 | 0 | 13.9 |

Barred from the pack cards the chooser takes about 1.2-1.5 more originals
than it did in the pack file (ones it had passed over for a pack card),
but about 2 fewer cards in all: the decks reach the mid-act elites
thinner. The extra deaths sit on floor 9 (heuristic 132 vs 73 in the pack
file, net 84 vs 56), at Lagavulin (54 vs 23; 37 vs 24), Three Sentries
(47 vs 32; 34 vs 24) and Gremlin Nob (40 vs 23; 24 vs 14); boss deaths
barely move (heuristic 165 vs 178, net 176 vs 151). So the cards the sim
chooser takes from the pack, Feel No Pain and the other late-paying
holders included, are worth about 0.12-0.14 clears against what it would
take or skip instead: no chooser error of the size the lane looked for
shows on the real pool. The pack read is the harder headline, and goal
2's gain on it is in fighting the new cards (and in offers with more
originals, which is the pool's choice, not the player's).

Caveat: "originals only" changes two things at once, which pack cards are
taken and how many cards are taken at all. A chooser that took the best
original even when it scores below skip would separate them; it was not
run: if the pack picks were the error, barring them would have given
clears back, and it took 0.12-0.14 away, so the charter's question is
answered either way.

## Turn-start timing (2026-11-10, owner-led session)

Spec `docs/specs/turn-start-draw.md` (the behavior is in
`docs/extending.md` "Turn start"). The engine's one turn-start trigger, run after the draw,
became two, at the game's times (decompiled `AbstractRoom.java` ~255,
`GameActionManager.java` ~446):

- **Pre-draw** (`OwnerTurnStart`, the game's `atStartOfTurn`): Berserk's
  energy and Flame Barrier's removal (`content/packs/act1-ironclad.json`,
  now version 2: the word stayed, its time moved before the draw), Poison
  (official; it only ever sits on monsters, which are unchanged).
- **Post-draw** (`OwnerTurnStartPostDraw`, the game's
  `atStartOfTurnPostDraw`): Demon Form and Brutality (official
  `content/powers.json`; unchanged in effect, they ran after the draw
  before).
- Monsters run both triggers in one pass at their turn start, as before:
  every monster fight is unchanged. On turn 1 the player's post-draw hooks
  run, then the pre-draw ones, after the opening draw, as the game's
  back-of-queue hooks do; `turn1_pre_draw` makes turn 1 like the others.
- Generated content (`scripts/gen_content.py`, now version 2): its
  `OwnerTurnStart` powers (the Brutality-like `LoseHp` and `Draw`
  templates among them) run before the draw. Saved packs are version 1 and
  play as they did (`engine/tests/turn_start_pins.rs`).
- Official fights are unchanged: golden identical, `series_check` PASS on
  3,609 states with Demon Form and Brutality, `@tsl1` pinned on them.

## Card rules for the net (2026-11-10, owner-led session)

Spec `docs/specs/card-rules.md` (behavior in `docs/extending.md` "Card
rules"). Entangled's `forbids`, Corruption's `sets_cost` and
`exhausts_played`, and Clash's play condition (now `playable_if`
`HandAll(Attack)` instead of the Clash-only `only_attacks_in_hand`) are
readable by the net as `rule` rows when extra rows are on, and the
explorer words all four. Fights play as before; today's nets read
byte-identical inputs (`series_check` PASS, the product net bit-identical;
`only_attacks_in_hand` kept as a legacy column for layouts that name it).

## Havoc loaded (2026-11-13, act1-singles session)

Spec `docs/specs/act1-singles.md` step 4 built C8: the effect `PlayTop`
(the game's `PlayTopCardAction`) takes the draw pile's top cards into a
queue, each with a random living target chosen when taken, and plays them
free once the card or potion in play has finished; `exhaust` exhausts
each (Havoc). Havoc (cost 1, Havoc+ 0) loads from
`content/packs/act1-ironclad.json`, checked in `engine/tests/act1_singles.rs`
`havoc`. Blocked Ironclad cards 8 -> 7: Infernal Blade (C11, with C5;
the P3 session's), Warcry (C7), Battle Trance (C9), Dual Wield (C10),
Barricade (C12), Juggernaut (C13), Reaper (C14).

## Warcry loaded (2026-11-13, colorless-cards step 4)

Spec `docs/specs/colorless-cards.md` step 4 built C7: the pick kind
`HandToTop` (the game's `PutOnDeckAction`) puts the chosen hand card on
top of the draw pile as a known top; with at most `n` cards of one kind in
hand they go at once, with an empty hand nothing. Warcry (cost 0, Skill,
exhaust; Draw 1, then HandToTop 1; Warcry+ draws 2) loads from
`content/packs/act1-ironclad.json` and joins the Ironclad pool, checked
against `cards/red/Warcry.java` in `engine/tests/colorless.rs`. Infernal
Blade loaded earlier (discovery). Blocked Ironclad cards 7 -> 5: Battle
Trance (C9), Dual Wield (C10), Barricade (C12), Juggernaut (C13), Reaper
(C14).
