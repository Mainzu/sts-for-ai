# Pack powers on pack monsters (block M5)

Status: closed (2026-11-06, built and in use; 6d8b28bd-a4c5fa64; decisions "Monster-pack-powers spec (M5)"; checkpoint m5-built passed 00c318d4).

Lane `act1-content`, block M5 of `docs/research/act1-inventory.md`
("Missing building blocks"). Spec by the lane worker, 2026-11-06,
confirmed under the mandate (operating.md, "Specs and builds").

## Why (goal 1)

Goal 1 is an AI that plays well on generated content, enemies included.
Today a pack monster may start only with official powers
(`engine/src/registry.rs` `parse_monster_as`: "generated powers on monsters
are not supported"), so a new enemy made of data can differ from the
official ones only in numbers and move order, the familiar parts the
record says cost the net nothing (`cause/novelty-is-horizon`). With this
block a pack enemy can carry a mechanic as data (a power with hooks,
statics or replacements), which is the first precondition of the
backlog's `generated-enemies-bench` (candidate 6, the goal-1 bench on
enemies new in kind), and it unblocks the Act 1 Mad Gremlin (its Angry is
a power no official monster holds). We'll know by: the Mad Gremlin loads
from `content/packs/act1-monsters.json` with the wiki's numbers and
plays as the game does in a test, and every existing check (golden,
series_check, the Python pins) stays identical.

## Outcome and non-goals

Outcome: a pack monster's `start_powers` may name a pack power, and the
power's hooks, statics and replacements act for that monster in a fight.

Non-goals:
- A monster **move** that applies a pack power (still refused at load).
  Move effects are static tables shared by every fight, while a pack
  power's slot depends on the fight's deck; doing it needs a resolution
  per fight. It is the next block if the enemies bench needs it (named
  M5b in the inventory).
- Pack powers on official monsters, and encounters as data (E1).
- The Gremlin Gang encounter (needs E1 and M6, M7).
- Any change to official content, golden or the rules version.

## Behaviour

- **Loading.** In a pack monster's `start_powers`, `{"power": "<name>",
  "amount": n}` names an official power as today, or a pack power by its
  id: one loaded by an earlier pack or by the same pack (the loader reads
  a pack's powers before its monsters). An unknown name is a load error
  naming the monster and the power. The monster's spec keeps official and
  pack start powers apart (pack ones as registry power indices).
- **Binding.** A fight's binding (`registry::Binding`) gains the pack
  powers of its monsters, and of their split children, after the deck's:
  a power already bound by the deck keeps its slot, a new one takes the
  next free slot. Deck slots never move, so bound card definitions (keyed
  by card and slots) stay valid. More than `SLOTS` (8) pack powers for
  deck and monsters together is an error: `registry::bind_monsters` returns
  it, and Python's `Combat(..., monsters=...)` raises `ValueError` before
  the fight is built; `CombatState::new_vs` calls it and panics only if a
  caller skipped that check.
- **Start.** `Monster::new` gives each pack start power to the monster at
  its bound slot (`Power::GEN[slot]`), as for a split child spawned later.
- **Play.** Nothing new: hooks (`run_hooks_with`), statics
  (`interpret_attack_damage`) and replacements (`replaced`) already run for
  any owner over `binding.powers_in_play()`. A hook's `Me` is the monster.
- **Features.** Nothing new: `entity_power_rows` encodes every power in
  play for each entity (effects mode). Ids mode already warns once that it
  sees pack content as unknown.
- **Codec.** Unchanged: a state with a pack monster is refused today.
- **Mad Gremlin** (the pack entry): HP 20-24, Scratch 4 every turn, start
  power Angry 1; Angry is a pack power `Angry` with one hook,
  `OwnerLostHp {from: Attack}` -> `Apply Strength 1 to Me` (scaled by
  stacks). The game's AngerPower triggers in `onAttacked` when the damage
  after block is above 0 and comes from an attack, which is the engine's
  attack HP loss. Numbers from the wiki, checked against sts_lightspeed
  (`decision/parity-source`); a disagreement is written in the inventory
  and settled by that rule.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Deck binding (`registry::bind`) | same slots and card defs for every deck | existing `engine/tests/packs.rs`, `registry.rs`; new test `deck_slots_kept` |
| Official monsters and encounters | identical fights | golden (`engine/tests/golden.rs`), `series_check` |
| Pack monsters without pack powers | load and play as before | `engine/tests/monster_packs.rs`, `act1_packs.rs` |
| Splits (`state.rs` split spawn) | children get their start powers | new test `split_child_pack_power` |
| Python `Combat(monsters=...)` | same API; new error only past 8 slots | new test in `scripts/tests/test_packs.py` (or the packs suite that holds pack monster tests) |
| Net features | identical rows on existing content | Python pins (contract, golden_rows) unchanged: no re-pin |
| Codec | refuses pack monsters as before | existing `engine/tests/codec.rs` |

## When in doubt

Prefer keeping the binding's existing slots and checks over a new
mechanism; prefer a load error over a silent drop.

## Scope

May change: `engine/src/registry.rs` (monster parsing, a monster-power
binder), `engine/src/monsters.rs` (the monster def's start powers),
`engine/src/state.rs` (`new_vs`, `Monster::new` callers), `py/src/lib.rs`
(the monsters path of `Combat`), `content/packs/act1-monsters.json` and
`content/packs/act1-ironclad.json` only if the power has to live in a
pack the monsters pack loads after (prefer the monsters pack), engine and
Python tests, `docs/research/act1-inventory.md`.

Off limits: official content (`content/*.json`), golden data, the rules
version, the codec format, feature layout (no new columns), `SLOTS`.

## Decisions taken

- Start powers only; moves applying pack powers wait (M5b). Alternatives:
  both now (a per-fight resolution of monster move tables, larger and
  touching features of intents), or a fixed slot per monster power
  (breaks with deck powers). Start powers carry any mechanic expressible
  as a power's hooks, which is what the Mad Gremlin and most bench
  enemies need; the move form is added when a bench enemy needs it.
- Monster powers bind after the deck's, sharing a slot when the same
  power is in both.

## Outside assumptions

- Mad Gremlin at Ascension 0: HP 20-24, Scratch 4, Angry 1 (wiki; checked
  against sts_lightspeed `MonsterSpecific.cpp` / `MonsterIds.h` in build
  step 1).
- AngerPower gains Strength on attack damage that got through block
  (sts_lightspeed's onAttacked path); checked in build step 1.

## Verification

Tests written first (`engine/tests/monster_powers.rs`):
1. `pack_power_start` — a test pack with power `Angry` and monster `M`
   (start Angry 1): `new_vs` against `M` gives M the power at slot 0 with 1
   stack.
2. `angry_on_attack_hp_loss` — Strike on M with no block: M's Strength
   +1; Strike fully blocked: no change; HP loss from a non-attack (a card
   that makes a monster lose HP, if one exists in the vocabulary, else
   Poison): no change.
3. `deck_slots_kept` — a deck binding two pack powers then M: deck slots
   0 and 1 unchanged, Angry at slot 2; a deck already holding Angry: one
   slot, shared.
4. `too_many_slots` — deck with 8 pack powers plus M: `bind_monsters`
   errors.
5. `split_child_pack_power` — a test splitter whose children start with
   a pack power: after the split, both children hold it.
6. `unknown_pack_power` — a monster naming an unloaded power: load error
   naming both.
7. `mad_gremlin_from_file` — load `act1-monsters.json`; Mad Gremlin's HP
   range, move and start power match the numbers above; three Strikes
   into it (no block) leave it with Strength 3, and its Scratch then hits
   for 7.
Python: `Combat(deck, monsters=["Mad Gremlin"])` plays; with a deck of 8
pack powers it raises `ValueError`.

End to end: `cargo test` all green, golden identical, `series_check` PASS
with every column equal, the Python suites touching packs and features
pass with no re-pin, `series_speed` within +10%.

Mutation check: Angry's amount 2, or deck slots shifted, fails a test.

## Don't guard

Don't check pack monster powers in the codec (it refuses pack monsters);
don't re-validate a pack power's hooks at bind (load validates them).

## Build steps

1. Sources and tests: check the Mad Gremlin's numbers and Anger's trigger
   against the wiki and sts_lightspeed (write the table row in the
   inventory); write tests 1-7, which fail on load today. Check: they
   compile and fail with the current refusal.
2. Registry and monster def: parse pack start powers; `bind_monsters`;
   `new_vs` and the split spawn use it. Check: tests 1-6 pass, all cargo
   tests pass, golden identical.
3. Pack entry and Python: Angry and Mad Gremlin in
   `content/packs/act1-monsters.json`; Python's monsters path raises the
   slot error. Check: test 7 and the Python test pass; mutation check
   fails a test.
4. Series checks: `series_check` PASS, Python pins unchanged (suites
   touching packs, features, nets), `series_speed` within +10%; the
   inventory's M5 section with counts. Check: those pass; land with an
   sts swap.

Build plan: 4 steps, in-session, on Opus. No stop
points expected: every choice above is reversible within the lane.
