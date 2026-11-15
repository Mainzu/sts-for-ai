# Relics as content (building block R1, with the combat-end heal)

Status: closed (2026-11-10, built and in use; owner-led; 8f81bd3b confirmed, 7c9035f6 marked built; As built: docs/research/act1-relics-potions.md "R1 as built"; decisions "Relics as content (R1), spec decisions").

## Outcome

A relic is a content entry that a fight can be given: the player starts the
fight holding the relic's powers, and a relic (or a card) can raise the HP
the player heals when the fight is won. This loads the 21 relics the
inventory calls writable plus Red Skull's grant, and moves Burning Blood from
character code into a relic entry, with every existing fight, read and net
unchanged.

**How it moves the goals.** Goal 1 (custom content as data): a designer
writes a relic as a list of starting powers, with the vocabulary cards and
monsters already use. Goal 2 / Act 1 (`decision/act1-finish`): 23 of the 141
Act 1 relics load and play from files (21 writable, Red Skull, Burning
Blood). We'll know by `act1-relics-potions.md` showing them loaded with a
test each, and by the series checks holding (golden identical,
`series_check` PASS, `series_speed` at most 10% slower).

**Non-goals** (owner, 2026-11-10):
- **No run-layer change.** The gauntlet doesn't hold, hand out or pass
  relics (the inventory's R2: start list, elite drop, chests, shop, Neow,
  events). That goes in together with the headline change once Act 1's
  content is mostly done. Nothing in this spec changes a headline read.
- No relic decisions by the AI (picking, skipping); no new net input column.
- Potions (P1, P2) are a separate spec.
- The relics blocked on other atoms (R3-R47) stay blocked. Meat on the
  Bone and Black Blood need a heal condition or a heal that replaces the
  starter's; they come later on top of this heal amount.
- The Silent's Ring of the Snake stays character code.

## Behavior

### The relic entry

A content pack may have a `"relics"` list beside `"powers"` and `"cards"`.
An entry:

| Field | Meaning | Default |
|---|---|---|
| `"id"` | The relic's name (the game's, e.g. `"Bag of Marbles"`). | required |
| `"rarity"` | `starter`, `common`, `uncommon`, `rare`, `boss`, `shop` or `event`. Data for later drops; no behaviour now. | required |
| `"powers": [{"power": <name>, "amount": <n>}, ...]` | Powers the player holds at fight start, official or from the same pack (the `start_powers` form monsters use). | `[]` |
| `"fights": [<kind>, ...]` | The fights it acts in: any of `hallway`, `elite`, `boss`. Given to a fight of another kind, it does nothing. | all three |
| `"win_heal": <n>` | HP added to the fight's combat-end heal. | 0 |

A turn-1-only effect is a pack power whose `OwnerTurnStart` hook ends with
`RemoveSelf`. Turn 1's `OwnerTurnStart` runs after the opening draw and the
block reset, which is where the game's "at the start of combat" relic
effects land (they queue after the opening draw): Anchor's block lasts the
turn, Bag of Preparation's 2 cards join the opening hand, Mark of Pain's
Wounds go into the draw pile at random places with the existing
`AddCard` effect.

Load errors (each a message naming the relic): a missing `id` or `rarity`,
an unknown rarity or fight kind, an empty `fights`, a power that is neither
official nor loaded, a repeated id, a negative `win_heal`.

Official relics live in `content/relics.json` (compiled in like
`content/powers.json`, with the `official_files()` check that the file
equals what the code writes). It holds one entry now, Burning Blood
(`starter`, `win_heal` 6). Pack relics are named `gen:<id>` as pack cards
are.

### The combat-end heal

The fight holds its heal amount, `win_heal` (an `i16` on the combat
state). At fight start it is the character's starter relic's `win_heal`
(Ironclad: Burning Blood, 6; Silent: 0) plus each given relic's that acts
in this fight. A new effect `WinHeal { amount }` adds to it during the
fight (the general effect the owner named: the Defect's Self Repair, for
one; usable in any card or hook). On a won fight the player heals
`win_heal`, capped at max HP, as today; no-death mode still has no heal.

Every reader of the heal reads the state's amount instead of the
character's constant: the fight's end (`state.rs`), the search bounds
(`bound.rs`), the heuristic, the net's value input (`net.rs`), and
Python's `win_heal` column and leaf values (`py/src/lib.rs`). So the net
values a raised heal through the input it already has.

**Bounds stay valid.** The exact solver's upper bound on final HP uses
`win_heal`; a card or hook still to come could raise it. Where any card the
state holds (any pile, in play) or any power on the player has a `WinHeal`
effect, the bound caps the heal at max HP instead (looser, still an upper
bound). With none (every state today), the bound is unchanged.

**Codec.** A new optional trailing field (tag 6, after tags 2-5) holds
`win_heal` when it differs from the character's default. Every state today
encodes to the same bytes, so the solved DB's keys and stored datasets are
unchanged. A state with a pack relic's pack power holds generated content
and isn't encoded, as with pack cards.

### Giving relics to a fight

- `sts.Combat(deck, encounter, ..., relics=None)` and
  `sts.Combat.versus(deck, monsters, ..., relics=None, group="hallway")`
  take relic names (`"Burning Blood"`, `"gen:Vajra"`). The fight's kind
  comes from the encounter's group; `versus` has no encounter, so it takes
  `group`.
- `sts.run` takes `"relics"` as an optional key of a dict spec (beside
  `encounter`, `deck`, `seed`, `hp`).
- The starter relic is always held and is not named: giving
  `"Burning Blood"` again adds its heal again (as holding two would).
- The relics' powers are added to the player at construction, after the
  monsters' (each pack power bound after the deck's and the monsters', as
  `bind_monsters` does; more than the slots allow is an error naming the
  relic). Then turn 1 starts, so their turn-start hooks fire on turn 1.
- An unknown relic name is an error naming it.
- Each relic is a set of starting powers: once the fight starts it holds
  powers, not relics. A fight with no relics given is the fight today, byte
  for byte.

### The relics written

In a new pack `content/packs/act1-relics.json` (shared relics aren't the
Ironclad's; its pack powers are its own, e.g. `RelicEnergy`, not the
Ironclad pack's Berserk), each as the inventory's row says:

- Starting powers: Vajra (Strength 1), Oddly Smooth Stone (Dexterity 1),
  Bronze Scales (Thorns 3), Clockwork Souvenir (Artifact 1), Gremlin Visage
  (Weak 1 on the player), Red Skull (the official `RedSkull` static,
  inexact as the inventory notes), Sling of Courage (Strength 2, elite
  only), Thread and Needle (a Plated Armor pack power, 4).
- Turn-1 hooks: Lantern (+1 energy), Bag of Preparation (draw 2), Anchor
  (10 block), Bag of Marbles (Vulnerable 1 to all enemies), Ancient Tea Set
  (+2 energy; whoever builds the fight gives it only after a rest).
- Every turn or on a trigger: Mercury Hourglass (3 to all enemies at turn
  start), Brimstone (Strength 2 to the player, 1 to all enemies, at turn
  start), Charon's Ashes (3 to all enemies on exhaust), Strike Dummy (+3
  damage on Strike cards), Centennial Puzzle (draw 3 on the first HP loss),
  Runic Cube (draw 1 on each HP loss).
- Energy relics: Slaver's Collar (+1 energy each turn, elite and boss
  only), Philosopher's Stone (+1 energy each turn; Strength 1 to all
  enemies on turn 1), Mark of Pain (+1 energy each turn; 2 Wounds into the
  draw pile on turn 1).

That is the inventory's 21 writable relics plus Red Skull (22 entries;
build step 5 recounts them against its table). The energy relics whose downside is out of combat
(Fusion Hammer, Cursed Key, Busted Crown, Ectoplasm, Sozu, Coffee Dripper)
and Girya and the Bottled relics stay "out-of-combat part blocked": not
written, since a relic entry without its downside would be a different
relic.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden fights and the rules version | `engine/tests/data/golden.txt` byte-identical; `rules_version()` unchanged | existing golden test |
| Codec and the solved DB | every state without relics encodes to the same bytes; tag 6 round-trips | existing codec round-trip tests; new `codec_win_heal_roundtrip` |
| Search bounds and the exact solver | bound unchanged with no `WinHeal` anywhere; still an upper bound with one | existing bound tests; new `bound_with_win_heal_card` |
| Net features and value input | same widths; same values on golden states (heal input 6 for the Ironclad) | new `features_unchanged_on_golden` (step 1, passes on unchanged code) |
| Python fights and runs | same results for fixed seeds with no relics | new pytest `test_no_relics_unchanged` (step 1) |
| Pinned jobs and snapshots | untouched; the landing records `jobs.py impact sts` and `impact scripts` | landing note |
| Content wording and the explorer | every new element (`WinHeal`, the relic fields, fight kinds) worded; the explorer lists relics | `engine/tests/wording.rs`; explorer smoke test |
| Pack loading | packs without `relics` load as today; the Act 1 Ironclad and monster packs unchanged | existing pack tests |
| The gauntlet | untouched (no relics anywhere in it) | none needed: no file in scope |

## When in doubt

Prefer acting as the game does over a smaller change (owner, 2026-11-10),
and prefer an unchanged existing fight over anything else.

## Scope

May change: the engine's registry (relic kind, official relics file),
combat state and construction, effects (`WinHeal`), the codec's optional
fields, the bounds, the heuristic's and net's heal reads, the runner's
`GameSpec`; the Python binding's fight constructors and `sts.run` spec
keys; `content/relics.json`, `content/packs/act1-relics.json`,
`content/wording.json`; the explorer's content listing; tests; docs
(`docs/extending.md` relic section, `act1-relics-potions.md` status,
facts).

Off limits: `scripts/gauntlet.py` and every run-layer script; configs,
yardsticks and controls; the net's input columns (count and meaning); the
Act 1 Ironclad and monster packs; the codec's existing encodings.

## Decisions taken (provisional; `docs/decisions.md`)

- Relics reach fights only through the fight constructors and `sts.run`
  for now; the run layer gets them with the headline change after Act 1
  (owner).
- The combat-end heal is a general amount the fight holds, raised by
  relics and by a `WinHeal` effect, read by every heal reader (owner:
  Meat on the Bone and Self Repair do it too, and the net must value it).
- A fight's kind for a relic's `fights` comes from the encounter's group;
  `versus` takes `group` (owner).
- Shared relics sit in their own pack, `act1-relics.json`.

## Outside assumptions

- The game applies "at the start of combat" relic effects after the opening
  draw (the opening `DrawCardAction` is queued before
  `applyStartOfCombatLogic`); sts_lightspeed's `BattleContext` order agrees.
  Checked by build step 5's Bag of Preparation and Mark of Pain tests
  against the inventory rows (hand of 7; Wounds not in the opening hand).
- A `Draw` from an `OwnerLostHp` hook during the monsters' turn draws
  (Centennial Puzzle, Runic Cube): the inventory's open check, run in
  step 5 first.

## Verification

Written first (step 1, passing on unchanged code):
- `features_unchanged_on_golden`: feature arrays of the golden states hashed
  and pinned.
- `test_no_relics_unchanged`: `sts.run` with the search agent on 20 fixed
  specs; results pinned.

Then:
- `codec_win_heal_roundtrip`: a state with `win_heal` 10 encodes with tag
  6 and decodes equal; one with 6 encodes as before.
- `bound_with_win_heal_card`: a hand holding a `WinHeal` card; the bound is
  at least the solved value.
- `relic_load_errors`: each load error above, with its message.
- One fight test per written relic: its effect at the first decision and
  on turn 2 (e.g. Lantern 4 energy then 3; Anchor 10 block then 0; Bag of
  Preparation 7 cards; Sling of Courage Strength 2 in an elite, none in a
  hallway; Mark of Pain 2 Wounds in the draw pile, none in hand).
- `burning_blood_from_data`: the heal on a won fight is 6, from
  `content/relics.json`; `relics=["Burning Blood"]` heals 12.
- End-to-end: `sts.run` over the 11 official hallway encounters with
  `relics=["gen:Vajra", "gen:Anchor"]` plays to the end and takes less HP
  on average than without (a sanity check, not a measurement), and the
  series checks hold.

## Don't guard

Two copies of one pack relic (allowed, the powers stack); relic rarity
(stored, unused); relics on monsters; a relic given to a fight of a kind
it skips (it does nothing, no warning).

## Build steps

1. **Pinning tests** on unchanged code: `features_unchanged_on_golden`,
   `test_no_relics_unchanged`; decisions into `docs/decisions.md`. Check:
   both pass.
2. **The heal amount.** `win_heal` on the combat state, set from the
   character; every reader switched; codec tag 6; `WinHeal` effect with its
   wording; the bounds rule. Check: golden identical, codec and bound tests,
   wording test, step 1's tests.
3. **The relic kind.** `relics` in packs and `content/relics.json` (Burning
   Blood), the starter relic named by the character and its `win_heal`
   read from data; load errors; wording for the fields. Check:
   `relic_load_errors`, `burning_blood_from_data` (heal half), official
   files check, golden identical.
4. **Giving relics.** The constructors' `relics` (and `group` on
   `versus`), `sts.run`'s key, `GameSpec`, binding the relic powers, the
   fight filter. Check: `burning_blood_from_data` (two copies), a pack-relic
   fight test, step 1's tests, `series_check`, `series_speed`.
5. **The relics written**, with the two open checks first (Draw from a
   hook in the monsters' turn; the opening-draw order), one test each; the
   count against the inventory's table. Check: every relic test; the
   end-to-end run.
6. **Explorer and docs.** The explorer lists relics (words from
   `wording.json`); `extending.md` relic section; `act1-relics-potions.md`
   marks each written relic loaded; facts (`measurement/act1-cards@files`
   kin for relics, `lane/act1-content/step`). Check: explorer smoke test,
   wording test.

No step runs long (the slowest is the series checks, minutes).

## Build plan

6 steps, forks (one per step; steps 2-4 in order, 5 after 4, 6 last), on
Opus. Stop point: step 2's bounds rule, if the exact solver's tests show
the looser bound costs speed on states with a `WinHeal` card (none exist in
today's content, so it can't touch existing runs).
