# Series review fixes, group E: variants and codec

Status: building (2026-11-02, E4 built in 81f823c; E1/E2 wait on D7 (bundle, unbuilt); E3, E5, E6 stay in the backlog; decisions 'Series review fixes: the cut').

Part of `docs/specs/series-review-fixes.md`. Read that file first: it has the why, what must
stay true, the decisions, the build order and how to build and check. This file holds the
group's entries, then its build step details, the pins it may change, its decisions and the
notes its checker left. Line numbers are at `d9327a2`.

## Findings

### E1. A hook that grows the card in play leaves run() and apply_action holding a stale card id

- **Severity:** medium · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED (review item v01, reported #7; the verifier reproduced symptoms (a)-(c) below with a throwaway test, debug build)
- **Where:** `engine/src/state.rs:703-729` in `CombatState::run` (the `None` arm: `card_resolved` at 704, `finish_card` at 707, the replays read at 709-712, the replayed copy at 713-721); related: `engine/src/state.rs:605-606` in `apply_action`, `engine/src/state.rs:995-998` in `condition_holds`, `engine/src/state.rs:1141-1144` in `grow_damage`, `engine/src/state.rs:1189-1204` `renumber_variant`, `engine/src/registry.rs:152-166` `Binding::def` (the `assert!` at 160). Line numbers are at HEAD b2c322a; that commit only added a file under docs/research, so they equal d9327a2's.

**What goes wrong.** Some terms first. A *variant* is a copy of an official card with its own damage number, named like `Rampage{damage=13/combat}`. A combat keeps up to 4 variants in its *binding* (the per-combat table that maps reserved card ids to generated cards and to variants), at card ids 144-147 (`registry::VARIANT_BASE` = 144), sorted by value (base card id, then damage). `Effect::GrowDamage(k)` (Rampage's second effect) turns the card in play into the variant with damage + k: `grow_damage` writes the new id into the stage (`*card = id`, state.rs:1142). Inserting or dropping a variant renumbers the others: `hold_variant` and `drop_unused_variants` call `renumber_variant`, which also rewrites the stage's card. A *hook* is an effect list a power runs when its trigger fires. A *content pack* is a JSON file of generated powers and cards loaded by `registry::load_pack`. Its power hooks may contain `GrowDamage`: `parse_hook` refuses only what `runs_outside_a_card` refuses (Pick, RandomDamage, RandomApply) and hooks that apply a generated power (registry.rs:703-718).

`run()` copies `card` out of `self.stage` at the top of each loop iteration (state.rs:679). In the `None` arm (the card's own effects are done) it calls `self.card_resolved(card, target)`. That runs the player's `OwnerLostHp{Card}` hooks, the player's `CardPlayed{by: Owner}` hooks and each monster's after-card hooks. When one of them does `GrowDamage`, the stage's card id changes, but the arm keeps using its copy. `self.finish_card(card, more.copy);` (707) files the old id into a pile, and the replayed copy starts with it (`self.stage = Stage::PlayingCard { card, target, next: 0, hit: 0, x, more };` at 718, then `self.card_played(card, target)` at 719). `check_over` (807) reads the card from the stage again; this arm does not. `apply_action` has the same pattern: `if self.owner_plays_card(card, target) || self.card_played(card, target)` (606). An `OwnerPlaysCard` hook can grow the card, and `card_played` then builds the hook context from the old id. The hook context's card is read in exactly one place, `condition_holds`: `Condition::CardType(ty) => ctx.card.is_some_and(|card| self.binding.def(card).ty == ty)` (998). The old id still names a card of the same base (renumbering stays within one base card), so the type is right, unless the old id's slot was freed. Then `Binding::def` hits `assert!(v != FREE, "variant card {} is not held in this combat", c.0);` (registry.rs:160). That is an `assert!`, so it panics in release builds too.

What a builder will see: (a) the growth is lost and a slot leaks: with a `CardPlayed{by: Owner}` `GrowDamage 3` hook, Strike is filed as a plain Strike while `Strike{damage=9/combat}` stays in the binding with no card holding it, so equal positions compare and hash unequal; (b) a card is filed as another variant of its base (a Rampage that should become `Rampage{16}` is filed as the `Rampage{14}` another copy holds, and `Rampage{16}` stays unheld; the card count is unchanged, so no invariant notices); (c) a panic, "variant card 145 is not held in this combat", when a hook shrinks a copy onto a value another copy already holds and the copy's old slot was the top one. A random-play run with an `OwnerPlaysCard` `GrowDamage` pack power (review item v09) hit this panic about once per 105,000-114,000 combats.

Official content never triggers this: no official hook has `GrowDamage`, and `scripts/gen_content.py` never writes it. Corrections to the original report: no encoded bytes are affected, because `codec::encode` refuses any state with a pack binding (`assert!(binding.is_empty(), ...)` at codec.rs:132), so these states are never encoded; only in-process `==` and hashing differ. "Four leftovers block a real Rampage" is wrong: every `grow_damage` ends with `drop_unused_variants`.

**Reproduce.** All in `engine/tests/packs.rs`. That file has no `mod common`, so there is no `card()` helper: name cards with `CardId::from_name("Strike").unwrap()`. Its helper `with_power(deck, hand)` (packs.rs:157) loads `FIX_PACK`, binds `deck`, plays the deck's first card (a cost-0 pack Skill that applies a pack power to the player) and then sets the hand to the named official cards and the energy to 3. The combat is the Ironclad at 80 HP against a Jaw Worm at 100 HP with no block. Append these entries to `FIX_PACK`'s `"powers"` list (add a comma after the `fx_shrug` entry, packs.rs:143):

```json
  {"id": "fx_grow3", "hooks": [{"trigger": {"CardPlayed": {"by": "Owner"}}, "effects": [{"GrowDamage": 3}]}]},
  {"id": "fx_shrink5", "hooks": [{"trigger": {"CardPlayed": {"by": "Owner"}}, "condition": {"CardType": "Attack"}, "effects": [{"GrowDamage": -5}]}]},
  {"id": "fx_shrink5_first", "hooks": [{"trigger": "OwnerPlaysCard", "condition": {"CardType": "Attack"}, "effects": [{"GrowDamage": -5}]}]}
```

and to its `"cards"` list (add a comma after `fx_sap_card`, packs.rs:152):

```json
  {"id": "fx_grow3_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_grow3", "amount": 1, "target": "Me"}}]},
  {"id": "fx_shrink5_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_shrink5", "amount": 1, "target": "Me"}}]},
  {"id": "fx_shrink5_first_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_shrink5_first", "amount": 1, "target": "Me"}}]}
```

(Checked against the parser: a string trigger such as `"OwnerPlaysCard"` and the one-key objects both go through `registry::variant`; negative integers already load in FIX_PACK. The pack card itself can't grow: a generated base returns before any variant is made.)

1. `with_power(&["gen:fx_grow3_card"], &["Strike"])`, then play Strike on monster 0. Expected: the Jaw Worm is at 94; the discard pile holds card 144 once and no plain Strike; `s.binding.variant_of(CardId(144)) == Some((strike, Overrides { damage: 9 }))`; `s.binding.n_variants() == 1`. Actual: the discard holds a plain Strike, and `Strike{9}` is bound with no holder.
2. `with_power(&["gen:fx_shrink5_card"], &["Rampage", "Rampage"])`, then play Rampage on monster 0 twice. Each play hits for 8, grows to 13 by its own effect, and the hook takes it back to 8. Expected: the discard pile holds card 144 twice, `variant_of(CardId(144)) == Some((rampage, Overrides { damage: 8 }))`, `n_variants() == 1`, the Jaw Worm at 84. Actual: the second play panics with "variant card 145 is not held in this combat" (from `finish_card`'s `self.binding.def(card)`, state.rs:786). The first play is filed right only by coincidence.
3. `with_power(&["gen:fx_shrink5_first_card"], &[])`, then build the layout by hand (the fields and functions are public): `s.binding.variants[0] = registry::variant_index(rampage, registry::Overrides { damage: 8 }).unwrap()`, `s.binding.variants[1] = registry::variant_index(rampage, registry::Overrides { damage: 13 }).unwrap()`, `s.discard.add(CardId(144), 1)` (another copy holds Rampage{8}), `s.hand = Pile::from_cards(&[CardId(145)])`, and `s.monsters[0].powers.add(Power::Enrage, 1)` (Enrage's hook, hooks.rs:179, has trigger `CardPlayed{by: Opponent}` and condition `CardType(Skill)`, and runs in `card_played` before the card's effects). Play card 145 on monster 0. Expected: the play hook shrinks it to 8 before it hits, so the Jaw Worm is at 92; Enrage does not fire (`s.monsters[0].powers.get(Power::Strength) == 0`); afterwards `n_variants() == 2` (the card grew back to 13 by its own effect and went to the discard pile). Actual: panic in `condition_holds`, called from `card_played`, with "variant card 145 is not held in this combat".

**Fix.** Two edits in `engine/src/state.rs`; `apply_action` then needs no change.
1. In `run()`'s `None` arm, read the card and its replays from the stage right after `card_resolved` returns `false`, and use that id for `finish_card`, the replayed copy and `card_played`. Replace lines 707-712 (`self.finish_card(card, more.copy);` and the `let replays = match self.stage {...};` block after it) with:
   ```rust
   // Read again: the hooks may have grown the card (a new variant id,
   // others renumbered) or asked for a replay.
   let (card, replays) = match self.stage {
       Stage::PlayingCard { card, more: m, .. } => (card, m.replays),
       _ => (card, 0),
   };
   self.finish_card(card, more.copy);
   ```
   `finish_card` doesn't touch the stage, so reading `replays` before it gives the same value as after. `more` in `more.copy` is still the one destructured at the top of the iteration; `copy` can't change during the card (only line 717 sets it). Lines 713-729 stay as they are and now use the fresh `card`, so a replayed copy starts as the card the hooks grew (before, it started from the stale id).
2. In `condition_holds`, read the card in play from the stage, so every hook condition sees the card as it is now. Every place that builds a context with a card sets it to the card in play (state.rs:648, 681, 914, 939; the only other one, 1437, sets `card: None`), and only `grow_damage` and the variant bookkeeping it calls change the stage's card, so this changes nothing unless a hook changed the id:
   ```rust
   // The card in play as it is now: a hook may have grown it into another
   // variant id (and freed the old one) since `ctx` was made.
   Condition::CardType(ty) => ctx.card.is_some_and(|c| {
       let card = match self.stage {
           Stage::PlayingCard { card, .. } => card,
           _ => c,
       };
       self.binding.def(card).ty == ty
   }),
   ```
   This covers `apply_action`'s `card_played` after an `OwnerPlaysCard` hook, the monsters' hooks in `card_resolved` after a player hook, and later hooks within one `run_hooks_with` call. It is the same rule `static_holds` already uses (`CardInPlayTagged` reads the stage, state.rs:1352).

Alternative: re-read the card in `apply_action` and rebuild the context in `card_played`, `card_resolved` and `run_hooks_with` (more edits, same effect). Don't refuse `GrowDamage` in pack hooks at load time instead: spec 10 (decisions.md:2238-2245, "Content packs carry every atom") lets pack powers take every effect but the monster-only ones, and the stale-id pattern would stay for any later effect that changes the card in play. Don't soften the `assert!` in `Binding::def`: it is what exposes the wrong filing.

Merge notes: C1 (group C, ReplayCard re-arming on copies) works on the same replay path (state.rs:713-719 and `do_effect`'s `ReplayCard`); if its fix also edits this arm, keep both changes (E1 only changes which id the arm uses). C3 (group C) may make `GrowDamage` in hooks scale by the power's stacks; these tests apply every power with amount 1, so their numbers don't change either way.

**Test first.** In `engine/tests/packs.rs`, three tests that fail on the current code (the first by assertion, the other two by panic). `packs.rs` already has `use sts_engine::registry::{self, ...}` and `use sts_engine::*` (`CardId`, `Pile`, `Power`, `Action`):

```rust
#[test]
fn a_card_grown_by_a_hook_is_filed_as_its_variant() {
    let strike = CardId::from_name("Strike").unwrap();
    let v0 = CardId(registry::VARIANT_BASE as u8);
    let mut s = with_power(&["gen:fx_grow3_card"], &["Strike"]);
    s.apply_action(Action::Play { card: strike, target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 94);
    // Filed as Strike{9}, the variant the hook made: no plain Strike, no unheld slot.
    assert_eq!((s.discard.count(strike), s.discard.count(v0), s.binding.n_variants()), (0, 1, 1));
    assert_eq!(s.binding.variant_of(v0), Some((strike, registry::Overrides { damage: 9 })));
}

#[test]
fn a_card_shrunk_onto_a_held_value_is_filed_there() {
    let rampage = CardId::from_name("Rampage").unwrap();
    let v0 = CardId(registry::VARIANT_BASE as u8);
    let mut s = with_power(&["gen:fx_shrink5_card"], &["Rampage", "Rampage"]);
    // Each play: 8 damage, its own GrowDamage makes it 13, the hook takes it back to 8.
    for _ in 0..2 {
        s.apply_action(Action::Play { card: rampage, target: Some(0) }).unwrap();
    }
    assert_eq!((s.discard.count(v0), s.binding.n_variants(), s.monsters[0].hp), (2, 1, 84));
    assert_eq!(s.binding.variant_of(v0), Some((rampage, registry::Overrides { damage: 8 })));
}

#[test]
fn monster_hooks_see_the_card_a_play_hook_grew() {
    let rampage = CardId::from_name("Rampage").unwrap();
    let (v0, v1) = (CardId(registry::VARIANT_BASE as u8), CardId(registry::VARIANT_BASE as u8 + 1));
    let mut s = with_power(&["gen:fx_shrink5_first_card"], &[]);
    // Rampage{8} (another copy, in the discard pile) and Rampage{13} (in hand).
    s.binding.variants[0] = registry::variant_index(rampage, registry::Overrides { damage: 8 }).unwrap();
    s.binding.variants[1] = registry::variant_index(rampage, registry::Overrides { damage: 13 }).unwrap();
    s.discard.add(v0, 1);
    s.hand = Pile::from_cards(&[v1]);
    // Enrage: a monster hook with a CardType(Skill) condition, run when the player plays a card.
    s.monsters[0].powers.add(Power::Enrage, 1);
    s.apply_action(Action::Play { card: v1, target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 92, "the play hook shrank it to 8 before it hit");
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 0, "Enrage saw an Attack");
    // It grew back to 13 by its own effect and went to the discard pile.
    assert_eq!((s.binding.n_variants(), s.discard.count(v0), s.discard.count(v1)), (2, 1, 1));
}
```

The first two tests check edit 1, the third checks edit 2 (with only edit 1 it still panics in `condition_holds`).

**Must stay unchanged.** Official play: golden.txt's 9,000 games and golden_proving.txt (including the `rampage` set) replay byte-identical (`cargo test --release -p sts-engine --test golden`); H4 searches byte-identical (record `cargo run --release -p sts-engine --example two_turn_phases -- 100 --check target/h4_before.txt` before the change, the same with `target/h4_after.txt` after, then `cmp target/h4_before.txt target/h4_after.txt`); every existing test in packs.rs, overrides.rs, decisions.rs, hooks.rs and registry.rs, and the quick fuzz, pass. Untouched by this fix: codec_golden.txt, series_check, the contract pins. The rules fingerprint value changes because state.rs is a rule file; that is expected on this branch, and no test pins the value.

### E2. A grown variant stays in the binding after its card leaves play (a Power card, or a replayed copy when the combat ends)

- **Severity:** medium (the Power-card path splits search transpositions; the combat-end path alone is low) · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED (review items sw_core_3 and v04, reported #8; both reproduced with throwaway tests, debug build)
- **Where:** `engine/src/state.rs:723-728` in `CombatState::run` (the drop after a card resolves; one line lower once E1's edit is in); `engine/src/state.rs:777-795` in `finish_card` (no pile for a copy at 787, `removed += 1` for a Power at 788-789); `engine/src/state.rs:798-816` `check_over` (`finish_card` at 808, `Stage::Over` at 814); `engine/src/state.rs:1170-1187` `drop_unused_variants`.

**What goes wrong.** Terms: a *variant* is a copy of an official card with its own damage number (`Rampage{damage=13/combat}`), held in one of 4 slots of the combat's *binding* (the per-combat table of reserved card ids), card ids 144-147. The rule from spec 8 (decisions.md:2092, "a variant no copy holds is dropped") keeps equal positions equal states. `drop_unused_variants` (state.rs:1170) does it, and counts a pile or the card in play as a holder. A *replayed copy* is the extra play a replay power makes (Burst; `InPlay::copy`); it goes to no pile. `CombatState` derives `PartialEq` and `Hash` over every field, the binding included.

`finish_card` puts most cards in a pile, but two kinds go nowhere: a replayed copy (`if copy {` at 787) and a non-copy Power card (`} else if d.ty == CardType::Power { self.removed += 1;` at 788-789). After a card finishes, `run()` drops unused variants only for a copy: `if more.copy && self.binding.n_variants() > 0 { self.drop_unused_variants(); }` (726). When the combat ends while a card is in play, `check_over` calls `self.finish_card(card, more.copy)` (808) and sets `Stage::Over { won }` (814) without any drop. So:
1. A pack hook (`OwnerPlaysCard`, or `CardPlayed{by: Owner}`) with `GrowDamage` turns an official Power card in play into a variant (Inflame's damage number is 0, since `card_damage` returns 0 for a card with no `Damage` effect, so +1 makes `Inflame{damage=1/combat}`). Inflame is then removed from the combat, and its variant stays listed with no holder.
2. A pack power that replays Attacks (like `fx_double_tap` in packs.rs) makes a Rampage copy that grows to 18, and the combat ends in that copy's after-card hooks (a monster's Sharp Hide kills the player, or a pack hook kills the last monster). The finished state lists `Rampage{18}` with no holder.

How it shows: the same position reached by two move orders (a transposition) compares and hashes unequal. The search memo (search.rs `Index::find`, line 149: hash, then `==`) stores it twice, `CombatState::options()` (which merges equal afterstates, options.rs:3-6) lists two options instead of one, and under a node cap the search can cut off differently. Measured: from one state, "Defend then Inflame" and "Inflame then Defend" reach equal piles, HP, powers and counters, but the first lists `[Defend{1}, Inflame{1}]` and the second `[Defend{1}]`. There is no wrong value and no panic, and no codec or solved-database effect: every trigger needs a generated power, and `codec::encode` refuses any state with a pack binding (codec.rs:132). A leftover doesn't pile up: the next `grow_damage` anywhere (which ends with `drop_unused_variants`) or a finished replayed copy frees it, so the original report's "stays until a full table forces a drop" is wrong. Official content reaches neither path: no official hook has `GrowDamage`, official Burst replays only Skills (none of which grows), and every other way a card leaves a pile moves it into another pile or into play (checked: state.rs and chance.rs pile removals).

**Reproduce.** In `engine/tests/packs.rs`, with the helper `with_power` (Ironclad 80 HP against a Jaw Worm at 100 HP, 3 energy; it plays the deck's first card, a cost-0 pack Skill that applies the power to the player). Append to `FIX_PACK`'s `"powers"` (after E1's entries):

```json
  {"id": "fx_grow1_first", "hooks": [{"trigger": "OwnerPlaysCard", "effects": [{"GrowDamage": 1}]}]}
```

and to its `"cards"`:

```json
  {"id": "fx_grow1_first_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_grow1_first", "amount": 1, "target": "Me"}}]}
```

1. `with_power(&["gen:fx_grow1_first_card"], &["Inflame"])`, play Inflame (no target). Expected: the player's Strength is 2 and `s.binding.n_variants() == 0`. Actual: `n_variants() == 1` (`Inflame{1}`, no holder).
2. Two states, each from `with_power(&["gen:fx_grow1_first_card"], &["Inflame", "Defend"])`: play Defend then Inflame in one, Inflame then Defend in the other (both untargeted, by their official ids). Expected: the two states are `==`. Actual: unequal (the first still lists `Inflame{1}`).
3. `with_power(&["gen:fx_dt_card"], &["Rampage"])` (an existing pack power: replay the next Attack once), then `s.monsters[0].powers.add(Power::SharpHide, 3)` and `s.player.hp = 4`; play Rampage on monster 0. Sharp Hide's hook (hooks.rs:222, `PlainDamage 1` times its stacks) runs after the card resolves. Rampage hits 8 and grows to 13, and Sharp Hide hits the player for 3 (4 to 1); the copy hits 13 and grows to 18, and Sharp Hide kills the player. Expected: `s.is_over() && !s.won()` and `n_variants() == 1` (only the original's 13, in the discard pile). Actual: `n_variants() == 2`.

**Fix.** Drop unused variants once a card has left play, at the two places a card leaves play with no `grow_damage` after it (both in `engine/src/state.rs`):
1. In `run()`'s `None` arm, else branch (723-728 at HEAD: `self.stage = Stage::PlayerTurn;`, the two-line comment and the `if more.copy && ...` drop), drop whenever the combat holds variants, not only after a copy:
   ```rust
   self.stage = Stage::PlayerTurn;
   // A card that went to no pile (a replayed copy, a Power card) may have
   // been the only holder of its variant: drop it now it has left play.
   if self.binding.n_variants() > 0 {
       self.drop_unused_variants();
   }
   ```
2. In `check_over`, after `self.stage = Stage::Over { won };` (814) and before `true`, add:
   ```rust
   // The card in play has left play (see run()): drop a variant only it held.
   if self.binding.n_variants() > 0 {
       self.drop_unused_variants();
   }
   ```
   It must come after the stage change, because `drop_unused_variants` counts the card in play as a holder.

For a card that went to a pile the drop finds nothing to do, and an official-only combat has variants only when it holds Rampage, all of them held, so official play is unchanged (the extra calls change no state). Don't drop inside `finish_card`: the stage still names the card there, so its own variant counts as held. Alternative: drop only when `more.copy` or the card is a Power (same result, more code). With E1's edit in place, `finish_card` and the drop see the fresh card id.

Guard (same step): in `engine/tests/common/mod.rs` `check_invariants`, after the card-count assertion, assert that every listed variant is held (`Stage` and `CardId` come from `use sts_engine::*`, already there):
```rust
// Every listed variant is held by a pile or the card in play.
for j in 0..s.binding.n_variants() {
    let id = CardId((sts_engine::registry::VARIANT_BASE + j) as u8);
    let in_play = matches!(s.stage, Stage::PlayingCard { card, .. } if card == id);
    assert!(in_play || [&s.hand, &s.draw, &s.discard, &s.exhaust].iter().any(|p| p.count(id) > 0), "variant slot {j} held by no card");
}
```
Only the fuzz calls `check_invariants`, and its decks hold only official and proving cards (Rampage included), so this passes before and after; it guards later changes.

**Test first.** In `engine/tests/packs.rs`, both fail on the current code by assertion:
```rust
#[test]
fn a_grown_power_card_leaves_no_variant() {
    let card = |name: &str| CardId::from_name(name).unwrap();
    let mut s = with_power(&["gen:fx_grow1_first_card"], &["Inflame"]);
    s.apply_action(Action::Play { card: card("Inflame"), target: None }).unwrap();
    // Inflame{damage=1/combat} left combat (a Power card): no slot stays behind.
    assert_eq!((s.player.powers.get(Power::Strength), s.binding.n_variants()), (2, 0));
    // The same position by two move orders is one state.
    let both = |first: &str, second: &str| {
        let mut s = with_power(&["gen:fx_grow1_first_card"], &["Inflame", "Defend"]);
        for name in [first, second] {
            s.apply_action(Action::Play { card: card(name), target: None }).unwrap();
        }
        s
    };
    assert_eq!(both("Defend", "Inflame"), both("Inflame", "Defend"));
}

#[test]
fn a_copy_that_ends_the_combat_leaves_no_variant() {
    let mut s = with_power(&["gen:fx_dt_card"], &["Rampage"]);
    s.monsters[0].powers.add(Power::SharpHide, 3);
    s.player.hp = 4;
    // Rampage hits 8 and grows to 13, Sharp Hide takes the player to 1; the
    // copy hits 13 and grows to 18, and Sharp Hide kills the player.
    s.apply_action(Action::Play { card: CardId::from_name("Rampage").unwrap(), target: Some(0) }).unwrap();
    assert!(s.is_over() && !s.won());
    assert_eq!(s.binding.n_variants(), 1, "only the original's 13, in the discard pile");
}
```
The existing `a_replayed_copys_grown_variant_is_dropped` must still pass.

**Must stay unchanged.** As for E1: golden.txt and golden_proving.txt byte-identical, H4 byte-identical, existing engine tests and the quick fuzz pass. Untouched: codec_golden.txt, series_check, contract pins. The rules fingerprint value changes (state.rs), as expected on this branch.

### E3. Variant interning: decode adds variants before it validates, and a full table silently stops cards growing

- **Severity:** low · **Reach:** crafted bytes (content packs too, slowly) · **New on this branch:** yes · **Review:** CONFIRMED (review item v09, cut by the 15-finding cap; reproduced with a throwaway test)
- **Where:** `engine/src/codec.rs:442-455` in `try_decode` (trailer section 2: `s.binding.variants[i] = variant_index(base, Overrides { damage })?;` at 449, before the order check at 451-454, the holder checks at 459-467 and the length check at 468); `engine/src/registry.rs:52-78` `variant_index` (the cap at 60-63; `CAPACITY` = 4096 at 94, shared with generated powers and card definitions); `engine/src/state.rs:1120` in `grow_damage`; `engine/src/codec.rs:472-474` `decode`; callers of `decode`: `py/src/lib.rs:1220` and `py/src/lib.rs:1240` (the solve store's `fetch` and `positions`)

**What goes wrong.** Terms: a *variant* is a copy of an official card with its own damage number. Its definition is made once per process and kept: `registry::variant_index(base, Overrides { damage })` *interns* it (adds it to one table shared by the whole process, append-only, so play reads definitions without a lock) and returns its index; a combat's *binding* stores those indices. The table holds at most 4,096 entries: `let i = t.len(); if i >= CAPACITY { return None; }` (registry.rs:60-63). The *codec* writes a state as bytes for the solved-state database; its optional *trailer section 2* lists the state's variants as (base card, damage) pairs.

Three defects:
1. `try_decode` interns every listed pair before it checks anything else (codec.rs:449). Bytes it then refuses (pairs out of order, a card id no pair defines, a junk byte after the trailer) still leave their pairs in the table. In a fresh process, 4,096 such refused decodes fill it.
2. With a full table, `grow_damage` silently does nothing: `let Some(idx) = crate::registry::variant_index(base, crate::registry::Overrides { damage: damage + k }) else { return };` (state.rs:1120). From then on the process plays Rampage differently from a fresh process (measured damage per play: 8, 13, 18, 23, 28, 28, 28, ... where values already met still grow; in a process whose table filled before any Rampage play: 8, 8, 8, ...), so the same setup and seed give different games. A valid encoding that names a variant the full process hasn't met fails to decode: `decode` panics with "not an encoded combat state of this codec version" (codec.rs:473), and the solve store's `fetch` and `positions` (py/src/lib.rs:1220, 1240) call `decode`, so Python gets a `PanicException`. (`Combat.decode` uses `try_decode` and raises `ValueError` (py/src/lib.rs:404), but it interns first too.)
3. `try_decode` accepts a listed variant no card holds (for example `Strike{damage=999/combat}` on a state with no such card). Its holder check (codec.rs:459-467) goes one way only: every card id must name a listed variant, but not every listed variant must be held by a card. The engine never writes such a state (a variant no card holds is dropped; for official content this always held, and E2 fixes the pack paths), and the decoded state is unequal to the same position without it.

Reach: official content never comes close (53,640 random combats with Rampage decks added 7 entries; Rampage is a proving card, in no deck pool). Pack powers with a `GrowDamage` hook add entries slowly (about 1,730 entries, to about 1,850 in all, after about 324,000 random combats with three such powers); `scripts/gen_content.py` never writes `GrowDamage`. Crafted or corrupt bytes fill the table every time. The interning order itself is harmless: encodings name variants by value and slots are ordered by value, so table indices never leave the process.

**Reproduce.** In one process: take a valid encoding of a state with no trailer, `codec::encode(&vs(&[K::JawWorm], &["Strike"], Some(100)))`. For `d` in 0..5,000 append `[2, 1, Strike's card id]`, then `d` as the codec writes a signed number (zigzag `z = (d << 1) ^ (d >> 63)`, then LEB128: 7 bits per byte, high bit set on every byte but the last), then a junk byte `0xFF` (read as a trailer tag, refused by the loop's `_ => return None`). `try_decode` refuses each one (correct), but on the current code each adds `(Strike, d)` until the table is full. Then play Rampage from a hand of one Rampage against a Jaw Worm at 30,000 HP, putting the grown copy back in hand after each play. Expected damage: 8, 13, 18, ... (+5 a play). Actual: 8, 8, 8, ... (the table is full before the first grow). Separately: encode a state after Rampage has grown (the discard holds `Rampage{13}`), remove that card from the discard, and encode again (`encode` writes the listed variants whether or not a card holds them). Expected: `try_decode` refuses it. Actual: it decodes.

**Fix.**
1. In `try_decode` (codec.rs), check every variant pair without interning, and intern only after the whole state passed every check.
   - Right after `let mut s = s;` (427) and before `let mut last = 0;`, add:
     ```rust
     // Section 2's (base card, damage) pairs, interned only once the whole
     // state has passed every check: the table is process-wide and capped.
     let mut variants = [(CardId(0), 0i16); VARIANTS];
     let mut n_variants = 0;
     ```
   - Replace the body of the `2 => { ... }` arm (443-454) with:
     ```rust
     let n = r.byte()? as usize;
     if n == 0 || n > VARIANTS {
         return None;
     }
     for v in &mut variants[..n] {
         let (base, damage) = (r.card()?, i16::try_from(r.i()?).ok()?);
         // `r.card` also takes variant ids; a variant's base is official.
         if !base.is_official() {
             return None;
         }
         *v = (base, damage);
     }
     // Strictly increasing by value (base card, then damage): the order
     // `registry::variant_key` gives, checked without interning.
     let key = |(c, d): (CardId, i16)| (c.0, d);
     if variants[..n].windows(2).any(|w| key(w[0]) >= key(w[1])) {
         return None;
     }
     n_variants = n;
     ```
     (The old `let key = crate::registry::variant_key;` goes. Tags must strictly increase, so section 2 is read at most once.)
   - Replace the tail (459-468: the `held` closure, the `in_play` bool, the `if` and `(r.at == bytes.len()).then_some(s)`) with:
     ```rust
     // Every card id names an official card or a listed variant, and every
     // listed variant is held by a pile or the card in play.
     let named = |c: CardId| c.is_official() || (VARIANT_BASE..VARIANT_BASE + n_variants).contains(&(c.0 as usize));
     let in_play = match s.stage {
         Stage::PlayingCard { card, .. } => Some(card),
         _ => None,
     };
     let piles = [&s.hand, &s.draw, &s.discard, &s.exhaust];
     if !piles.iter().all(|p| p.iter().all(|(c, _)| named(c))) || !in_play.map_or(true, named) || !s.top.within(&s.draw) {
         return None;
     }
     let held = |id: CardId| in_play == Some(id) || piles.iter().any(|p| p.count(id) > 0);
     if !(0..n_variants).all(|j| held(CardId((VARIANT_BASE + j) as u8))) {
         return None;
     }
     // (E5's pick check goes here.)
     if r.at != bytes.len() {
         return None;
     }
     // Only now: the table is process-wide and capped, so refused bytes must
     // add nothing to it. `None` here means this process's table is full.
     for (i, &(base, damage)) in variants[..n_variants].iter().enumerate() {
         s.binding.variants[i] = variant_index(base, Overrides { damage })?;
     }
     Some(s)
     ```
     Keep every check before the interning loop: that order is what makes refused bytes intern nothing. (The borrow checker accepts it either way: the pile references and `s.binding` are different fields.) The `r.at` check can't fail after the trailer loop (the loop runs until the end), but it is kept as the current code has it. `Binding::is_bound` is no longer used here; py/src/lib.rs still uses it. Optionally reword `try_decode`'s doc comment to "... encoding of a state the engine can be in".
2. In `grow_damage`, separate the two reasons `variant_index` returns `None`. Replace state.rs:1120 with:
   ```rust
   // A generated card can't grow (variants need an official base).
   if !base.is_official() {
       return;
   }
   let idx = crate::registry::variant_index(base, crate::registry::Overrides { damage: damage + k })
       .expect("registry: the process-wide variant table is full");
   ```
   A generated card still doesn't grow (D7 in group D is about that limitation; if D7's fix changes it, merge on these lines). A full table now stops play with a clear panic instead of silently changing it. The early return also moves the `damage + k` addition after it for generated cards.

Keep `variant_index` returning `None` on a full table: `try_decode` must never panic (`Combat.decode` turns `None` into `ValueError`). Raising `CAPACITY` alone is not a fix: refused bytes would still fill the table. Alternatives: a larger cap for variants only (their own constant instead of the shared `CAPACITY`), worth it only if a generator starts writing `GrowDamage` hooks; refusing decoded bases without their own `GrowDamage` (it doesn't close the hole: valid crafted bytes can still name any Rampage damage, and valid bytes are still interned); per-combat variant definitions with no shared table (a state-representation change, spec 10's). Optional: `fetch` and `positions` in py/src/lib.rs could use `try_decode` and raise a Python error. Docs: decisions.md:2084 ("interned process-wide") can add "a full table is an error"; decisions.md:2086 still says "sorted by interned index", stale since the review fix that orders slots by value (decisions.md:2216-2220), and can be corrected in passing.

**Test first.**
- New file `engine/tests/variant_table.rs`. It must be its own test binary, because it fills the process-wide table; don't add other tests to it. It fails on the current code at "play 1" (8 instead of 13):
  ```rust
  //! The process-wide variant table: bytes the decoder refuses add nothing
  //! to it, and a full table stops play instead of changing it.
  mod common;
  use common::*;
  use sts_engine::codec::{encode, try_decode};
  use sts_engine::monsters::MonsterKind as K;
  use sts_engine::registry::{variant_index, Overrides};
  use sts_engine::*;

  /// `v` as the codec writes a signed number: zigzag, then LEB128.
  fn signed(v: i64, out: &mut Vec<u8>) {
      let mut z = ((v << 1) ^ (v >> 63)) as u64;
      while z >= 0x80 {
          out.push(z as u8 | 0x80);
          z >>= 7;
      }
      out.push(z as u8);
  }

  #[test]
  fn refused_bytes_intern_nothing_and_a_full_table_fails_loudly() {
      let base = encode(&vs(&[K::JawWorm], &["Strike"], Some(100)));
      for d in 0..5_000 {
          let mut b = base.clone();
          b.extend([2, 1, card("Strike").0]);
          signed(d, &mut b);
          b.push(0xFF);
          assert!(try_decode(&b).is_none());
      }
      // Rampage still grows by 5 on every play.
      let mut s = vs(&[K::JawWorm], &["Rampage"], Some(30_000));
      let mut c = card("Rampage");
      for k in 0..10i16 {
          let hp = s.monsters[0].hp;
          s.player.energy = 3;
          s.apply_action(Action::Play { card: c, target: Some(0) }).unwrap();
          assert_eq!(hp - s.monsters[0].hp, 8 + 5 * k, "play {k}");
          c = s.discard.iter().next().unwrap().0;
          s.discard.remove(c, 1);
          s.hand.add(c, 1);
      }
      // Fill the table: a copy that can't grow now stops play.
      for d in 0..5_000i16 {
          let _ = variant_index(card("Strike"), Overrides { damage: 10_000 + d });
      }
      let r = std::panic::catch_unwind(|| {
          let mut t = vs(&[K::JawWorm], &["Rampage+"], Some(100));
          play(&mut t, "Rampage+", Some(0));
      });
      assert!(r.is_err(), "a full table must stop play, not leave Rampage+ at 8");
  }
  ```
  (No profile sets `panic = "abort"`, so `catch_unwind` works under `--release`. The panic happens after `variant_index` released its lock, so nothing is poisoned.)
- `engine/tests/overrides.rs::a_listed_variant_no_card_holds_is_refused` (overrides.rs already has `worm`, `variant`, `codec` and the common helpers). Fails on the current code at the second assertion:
  ```rust
  #[test]
  fn a_listed_variant_no_card_holds_is_refused() {
      let mut s = worm(&["Rampage"]);
      play(&mut s, "Rampage", Some(0));
      let v13 = variant(&s, "Rampage", 13).unwrap();
      assert!(codec::try_decode(&codec::encode(&s)).is_some());
      // `encode` still lists Rampage{13}; no card holds it now.
      s.discard.remove(v13, 1);
      assert!(codec::try_decode(&codec::encode(&s)).is_none());
  }
  ```
- Guard, added before the src change and run on the current code first: in `engine/tests/common/mod.rs` `check_invariants` (next to E2's guard), every state round-trips through the codec:
  ```rust
  // The codec round-trips every state the engine reaches (bound generated
  // content has no encoding; `is_empty` ignores variants, so Rampage states count).
  if s.binding.is_empty() {
      assert_eq!(sts_engine::codec::try_decode(&sts_engine::codec::encode(s)).as_ref(), Some(s), "codec round trip");
  }
  ```
  The fuzz decks include the proving cards (Rampage, Survivor, Burst, Hologram, Headbutt and others), so this checks the stricter decoder still takes every state the engine reaches. If it fails on the current code, stop and report: that is a separate bug (G4's verifier round-tripped 151,641 proving-card states without a failure, so none is expected). G4 (group G) asks for codec coverage of the same shapes; if its fix already put this round trip in `check_invariants`, don't add it twice.

**Must stay unchanged.** `encode` is untouched, so every encoding stays byte-identical and `CODEC_VERSION` stays 1: codec_golden.txt and `codec_roundtrip` (`cargo test --release -p sts-engine --test codec`), the codec tests in overrides.rs, decisions.rs, known_top.rs and amounts.rs, and the fuzz with the round-trip guard all pass. golden.txt and golden_proving.txt stay byte-identical (`grow_damage` behaves the same while the table has room). Untouched: series_check, contract pins, H4. The rules fingerprint value changes (state.rs), as expected on this branch.

### E4. The rules fingerprint doesn't hash engine/src/registry.rs, which now holds rules for official play

- **Severity:** low · **Reach:** future change · **New on this branch:** yes · **Review:** CONFIRMED (review item v10, cut by the 15-finding cap; checked by reading, no code run)
- **Where:** `solvedb/src/fingerprint.rs:18-27` `RULE_FILES`; the unhashed rules: `engine/src/registry.rs:24` (`pub const VARIANTS: usize = 4;`) and `engine/src/registry.rs:65-72` in `variant_index` (`Effect::Damage { hits, target, .. } => Effect::Damage { amount: o.damage, hits, target },` at 69); their hashed users `engine/src/state.rs:1156` in `hold_variant` and `engine/src/cards.rs:166` (`NUM_CARDS`); the lookup `solvedb/src/db.rs:917-925` (`DbStore::lookup` by `encode(s)` at 921); the docs that list the hashed files: `docs/engine-next.md:80-82` and `docs/specs/exact-solver.md:124-127`

**What goes wrong.** The *solved-state database* (crate `solvedb`) stores exact values of states, keyed by their codec bytes under a *rules fingerprint*: a hash of the rule files' code (comments and whitespace stripped), the content tables' name order and `CODEC_VERSION` (`fingerprint_of`, fingerprint.rs:144). A rules edit is meant to change the fingerprint, so old rows stop being served. `RULE_FILES` hashes 8 files (state, cards, monsters, powers, hooks, effects, chance, character), not registry.rs. Before this branch registry.rs held only generated content, which the codec refuses, so no stored row could depend on it. Now it holds two rules of official play. `VARIANTS` decides whether a Rampage copy can grow when four variants are held (`if n == crate::registry::VARIANTS { return None; }`, state.rs:1156). `variant_index`'s override decides what a grown copy deals (registry.rs:69). An edit to either changes the true value of some Rampage states while the fingerprint, the content tables and the codec bytes stay the same: the trailer writes variants by value, and raising `VARIANTS` to 8 even leaves the pile size the same (`PILE_SLOTS` = `NUM_CARDS` rounded up to 8 = 152), so every existing encoding stays byte-identical and nothing prompts a `CODEC_VERSION` bump. `DbStore` would then serve the old rows with no error.

Reach: it needs a future edit to registry.rs alone, and a database holding Rampage states (Rampage is a proving card, in no deck or bench pool). Example: with `VARIANTS = 4`, a state holding `Rampage{13}`, `{18}`, `{23}` and `{28}` (one copy each) and a base Rampage+ to play can't grow the Rampage+ (it stays at 8); with 8 slots it grows to 16, so its true value differs.

**Reproduce.** Change registry.rs:24 to `pub const VARIANTS: usize = 8;` and rebuild: `solvedb::fingerprint::fingerprint()` returns the same value as before.

**Fix.** Hash registry.rs. In `solvedb/src/fingerprint.rs` add `("registry", include_str!("../../engine/src/registry.rs")),` as the last entry of `RULE_FILES` and change its type to `[(&str, &str); 9]`. Update the two docs that list the files: `docs/engine-next.md:80-82` ("The 8 files in `solvedb/src/fingerprint.rs` (`state`, `cards`, `monsters`, `powers`, `hooks`, `effects`, `chance`, `character`)") to "The 9 files ... `character`, `registry`)", and `docs/specs/exact-solver.md:125-126` (the same list) by adding `registry`. `fingerprint_tracks_rules` loops over `RULE_FILES`, so it checks the new file with no edit; checked: registry.rs has no multi-line string literal, so that test's comment-and-newline rewrite can't change its stripped code.

Cost: every later edit to registry.rs, the pack loader included, retires the solved rows too. That is acceptable: the solved database is retired at every fingerprint change and refilled once after the series (decisions.md:498), and spec 10's later stages put more official content behind registry.rs. Alternative: move `VARIANTS` and the variant-definition code (`variant_index`'s effect rewrite) into cards.rs, which is hashed, and leave registry.rs out. A pack-loader edit then keeps the rows, but the next official rule added to registry.rs slips through again, and the test below would need `registry` on its allow list.

**Test first.** `solvedb/tests/fingerprint.rs::rule_files_cover_the_modules_they_use` (the file already imports `RULE_FILES` and `strip_code`): every engine module a rule file names through `crate::` is a rule file too, or is on a short list of modules that hold no rules. It fails on the current code with "state.rs uses crate::registry, which the fingerprint doesn't hash":
```rust
/// Every engine module a rule file calls into is hashed too, or holds no
/// rules: an edit there would otherwise change play while the fingerprint,
/// and the solved rows under it, stay the same.
#[test]
fn rule_files_cover_the_modules_they_use() {
    // Machinery, like solve.rs (also unhashed): the sampler and the exact
    // enumerator (rng), a hash function (fxhash).
    const NOT_RULES: [&str; 2] = ["rng", "fxhash"];
    for (name, src) in RULE_FILES {
        let code = strip_code(src);
        for (at, _) in code.match_indices("crate::") {
            let m: String = code[at + "crate::".len()..].chars().take_while(|&c| c.is_alphanumeric() || c == '_').collect();
            assert!(
                RULE_FILES.iter().any(|(n, _)| *n == m) || NOT_RULES.contains(&m.as_str()),
                "{name}.rs uses crate::{m}, which the fingerprint doesn't hash"
            );
        }
    }
}
```
Checked by grep: today the 8 files name `cards`, `chance`, `character`, `effects`, `hooks`, `monsters`, `powers`, `state`, `registry`, `rng` and `fxhash` (no grouped `use crate::{...}` imports, which would give an empty name); registry.rs itself names only `cards`, `effects`, `hooks` and `powers`, so the test passes once registry.rs is added.

**Must stay unchanged.** `content_tables_pinned` (0x5a922915c8ae26dd) and `CODEC_VERSION` (1). The fingerprint value changes, which this branch already does; nothing pins it (data/bench/puzzles.json records the fingerprint it was made under, 39bfc65e541f073d, already stale; bench.py only copies it into results). Engine behaviour, golden files, codec bytes, H4, series_check and all pins: untouched. As before, don't point main's `db/` at this worktree. Mention the change in the decisions.md entry that records this batch of fixes.

### E5. The codec's tag-8 decoder accepts picks the engine never makes; play then wraps or panics

- **Severity:** low · **Reach:** crafted bytes · **New on this branch:** yes · **Review:** CONFIRMED (review item v08, cut by the 15-finding cap; reproduced in debug and release builds)
- **Where:** `engine/src/codec.rs:362-377` in `try_decode` (stage tag 8: `Some(Pick { kind, left: r.byte()?, exact: r.byte()? != 0 })` at 369; the only check, `if more == InPlay::default() || copy > 1 { return None; }`, at 373); related: `engine/src/state.rs:504-512` `pick_source`, `engine/src/state.rs:694` (where the engine makes a pick), `engine/src/state.rs:629-630` (`Choose`); crash sites `engine/src/agent.rs:201` (`greedy_action`), `engine/src/search.rs:325` (`search`, `options[best]`), `py/src/lib.rs:1372` (`random_action`)

**What goes wrong.** Terms: a *pick* is a card in play paused for the player to choose cards (Survivor: discard one from hand; Hologram: return one from the discard pile; Headbutt: put one from the discard pile on top of the draw pile), stored as `Pick { kind, left, exact }` in the stage's `InPlay`. The codec writes a card in play that has a pick, replays or a copy flag under stage tag 8. The engine makes a pick only when there is something to pick: `let pick = (n > 0 && self.pick_source(kind).is_some()).then_some(Pick { kind, left: n, exact });` (state.rs:694), and after each `Choose` it keeps the pick only on the same condition (630). `pick_source` is `None` when the pile is empty, and for `ReturnFromDiscard` when the hand is full (`HAND_LIMIT` = 10). While paused at a pick no chance event is pending (`run()` reaches a `Pick` effect only with `pending` empty, and nothing sets `pending` while paused).

The tag-8 decoder checks none of this. It accepts `left == 0`, an `exact` byte other than 0 or 1 (non-canonical: it re-encodes differently), a pick whose pile can give nothing, and a pick with a chance event pending. Then:
- With `left == 0`, the first `Choose` runs `p.left -= 1;` (629): a debug build panics ("attempt to subtract with overflow"); a release build wraps to 255, so an exact pick makes the player discard the whole hand.
- With nothing to pick from, `awaiting_action()` is true but `legal_actions()` is empty, which breaks the fuzz invariant `actions.is_empty() == s.is_over()`. `greedy_action` panics at `return s.legal_actions()[0];` (agent.rs:201), `search` at `options[best].actions[0]` (search.rs:325), and Python's `sts.random_action` at `.expect("awaiting an action")` (py/src/lib.rs:1372); Python's `sts.greedy_action` goes through agent.rs:201.

Only hand-made or corrupt bytes reach this: every real caller decodes bytes `encode` wrote from engine states, but `Combat.decode` and the explorer (127.0.0.1, scripts/explore.py) accept typed hex. decisions.md:1981 lists "the tag-8 decoder accepts some non-canonical bytes" as optional, not done; that covers the exact byte, not the rest.

**Reproduce.** `silent_vs_worm(&["Survivor", "Strike", "Defend"])` (engine/tests/decisions.rs:15, a Jaw Worm at 100 HP), then play Survivor: the state is paused at a `DiscardFromHand` pick with `left` 1 and `exact` true. `codec::encode` writes any stage without checking it, so build each bad state as a struct and encode it:
1. the same stage with `Pick { left: 0, ..p }`;
2. the real pick with `s.hand = Pile::default()`;
3. the real pick with `s.pending = Some(ChanceEvent::Draw { n: 1 })`;
4. the exact byte set to 2: encode the stage with `exact: true` and with `exact: false`, find the one byte where the two encodings differ, and set it to 2 in the first;
5. Hologram: `vs(&[K::JawWorm], &["Hologram"], Some(100))` with `discard = [Strike]`, play Hologram (a `ReturnFromDiscard` pick), then set the hand to 10 Defends.
Expected: `codec::try_decode` returns `None` for each, and `Some` for the real pick. Actual: all of them decode.

**Fix.** In `try_decode`, refuse what the engine never writes:
1. In the tag-8 branch, replace line 369 (inside the `k => { ... }` arm, after `let kind = ...;`) with:
   ```rust
   let (left, exact) = (r.byte()?, r.byte()?);
   // As the engine makes them: something left to pick, exact 0 or 1.
   if left == 0 || exact > 1 {
       return None;
   }
   Some(Pick { kind, left, exact: exact == 1 })
   ```
2. In the tail E3 wrote, at the line marked `// (E5's pick check goes here.)` (after the two holder checks, before the `r.at` check and the interning loop), add:
   ```rust
   // A pick the engine could be paused at: its pile has a card to take
   // (a full hand takes nothing back) and no chance event is pending.
   if let Some(p) = s.pick() {
       if s.pending.is_some() || s.pick_source(p.kind).is_none() {
           return None;
       }
   }
   ```
   and make `pick_source` (state.rs:504) `pub(crate)`, so the codec reuses the engine's rule instead of copying it.
Not the fix: guarding `greedy_action`, `search`, `random_action` or `p.left -= 1`; they are right for every state the engine can be in. Docs: decisions.md:1981's optional item is then done.

**Test first.** `engine/tests/decisions.rs::codec_refuses_picks_the_engine_never_makes` (decisions.rs already imports `codec`, `InPlay`, `Pick`, `Stage`, `K`, the common helpers, and `sts_engine::*`, which brings `ChanceEvent`, `CombatState` and `Pile`). It fails on the current code at the "nothing left to pick" assertion:
```rust
#[test]
fn codec_refuses_picks_the_engine_never_makes() {
    let mut s = silent_vs_worm(&["Survivor", "Strike", "Defend"]);
    play(&mut s, "Survivor", None);
    let Stage::PlayingCard { card: c, target, next, hit, x, more } = s.stage else { panic!("at a pick") };
    let p = more.pick.expect("at a pick");
    let with_pick = |p: Pick| {
        let mut t = s.clone();
        t.stage = Stage::PlayingCard { card: c, target, next, hit, x, more: InPlay { pick: Some(p), ..more } };
        t
    };
    let decodes = |t: &CombatState| codec::try_decode(&codec::encode(t)).is_some();
    assert!(decodes(&s), "the real pick");
    assert!(!decodes(&with_pick(Pick { left: 0, ..p })), "nothing left to pick");
    let mut t = s.clone();
    t.hand = Pile::default();
    assert!(!decodes(&t), "an empty hand to discard from");
    let mut t = s.clone();
    t.pending = Some(ChanceEvent::Draw { n: 1 });
    assert!(!decodes(&t), "a chance event pending at a pick");
    let (a, b) = (codec::encode(&with_pick(Pick { exact: true, ..p })), codec::encode(&with_pick(Pick { exact: false, ..p })));
    let i = a.iter().zip(&b).position(|(x, y)| x != y).unwrap();
    let mut bad = a.clone();
    bad[i] = 2;
    assert!(codec::try_decode(&bad).is_none(), "an exact byte of 2");
    let mut h = vs(&[K::JawWorm], &["Hologram"], Some(100));
    h.discard = Pile::from_cards(&[card("Strike")]);
    play(&mut h, "Hologram", None);
    assert!(h.pick().is_some());
    h.hand = Pile::from_cards(&[card("Defend"); 10]);
    assert!(!decodes(&h), "a full hand takes nothing back");
}
```

**Must stay unchanged.** `encode` is untouched: codec_golden.txt, `codec_roundtrip`, `codec_round_trips_picks_and_replays` and the other codec tests pass, and `CODEC_VERSION` stays 1. With E3's round-trip guard in `check_invariants`, the fuzz (Silent decks hold Survivor and Burst; Ironclad decks hold Hologram and Headbutt) checks that every pick the engine makes still decodes. Golden files, H4, series_check and pins: untouched. The rules fingerprint value changes (state.rs, `pub(crate)`), as expected on this branch.

### E6. slots_are_ordered_by_value can't catch the bug it guards

- **Severity:** low · **Reach:** future change (a test that can't fail) · **New on this branch:** yes · **Review:** CONFIRMED (review item sw_tests_2, cut by the 15-finding cap; the verifier reverted the rule in a copy and ran the binary 30 times)
- **Where:** `engine/tests/overrides.rs:98-108` `slots_are_ordered_by_value`; the rule it guards, `engine/src/state.rs:1159-1160` in `hold_variant`; the intern order, `engine/src/registry.rs:60` in `variant_index`; the doc that names this test as the guard, `docs/decisions.md:2216-2222`

**What goes wrong.** Terms: a combat keeps its *variants* (copies of an official card with their own damage number, like `Rampage{damage=13/combat}`) in 4 slots at card ids 144-147. `registry::variant_index` *interns* each variant: it gives it the next index in a table shared by the whole process (`let i = t.len();`, registry.rs:60), so indices follow the order this process first met each variant. Slots must be ordered by value (base card id, then damage: `registry::variant_key`), not by index; otherwise the same state can encode to different bytes, or fail to decode, in another process. `hold_variant` does this today: `let j = vs[..n].iter().position(|&v| crate::registry::variant_key(v) > key).unwrap_or(n);` (1160). Before commit 1a51035 it compared indices: `position(|&v| v > idx)`.

The test plays Rampage+ (grows to 16) and then Rampage (grows to 13) and checks that Rampage's variant is in slot 0. It catches the old rule only if this process interns (Rampage+, 16) before (Rampage, 13). Tests in one binary share the process, and four tests that sort before it by name each play Rampage first: `a_full_slot_table_still_grows_the_copy_that_frees_its_slot`, `codec_round_trips_variants`, `copies_at_the_same_damage_are_one_key` and `rampage_grows_its_own_copy`. With `--test-threads=1` (name order) they always run first; in parallel runs they usually win the race (26 of 30 runs). Then (Rampage, 13) has the lower index, index order equals value order, and the test passes with the bug back in. `variants_are_canonical` can't tell either (it plays both orders in one process). decisions.md:2221 names this test as the guard. (`golden_trajectories` would still flag a revert through the `rampage` proving set, but only as "behaviour changed".)

**Reproduce.** Change state.rs:1160 to `let j = vs[..n].iter().position(|&v| v > idx).unwrap_or(n);` (the unused `key` on 1159 gives only a warning), then run `cargo test --release -p sts-engine --test overrides -- --test-threads=1`: every test passes. Run alone (`-- slots_are_ordered_by_value`) it fails. Revert the line by hand afterwards.

**Fix.** Rewrite the test so it makes its own intern order, whatever other tests do: intern Rampage+'s target variant before Rampage's, at damage numbers no other test reaches (Rampage reaches 1013 only after 201 plays, Rampage+ 1016 after 126), and check that precondition. Start from two copies placed in the slots by value:
```rust
#[test]
fn slots_are_ordered_by_value() {
    // This process meets Rampage+{1016} before Rampage{1013} (numbers no
    // other test reaches, so whatever ran first), yet Rampage's variant
    // takes slot 0: the order is the cards' own, the same in every process.
    let (r, rp) = (card("Rampage"), card("Rampage+"));
    let index = |c: CardId, damage: i16| sts_engine::registry::variant_index(c, sts_engine::registry::Overrides { damage }).unwrap();
    let (hi, lo) = (index(rp, 1016), index(r, 1013));
    assert!(hi < lo, "Rampage+{{1016}} interned first");
    let mut s = worm(&[]);
    s.monsters[0].hp = 9_999;
    s.monsters[0].max_hp = 9_999;
    s.binding.variants[0] = index(r, 1008);
    s.binding.variants[1] = index(rp, 1008);
    s.hand = Pile::from_cards(&[CardId(VARIANT_BASE as u8), CardId(VARIANT_BASE as u8 + 1)]);
    s.player.energy = 5;
    for base in ["Rampage+", "Rampage"] {
        let c = variant(&s, base, 1008).unwrap();
        s.apply_action(Action::Play { card: c, target: Some(0) }).unwrap();
    }
    let slot = |i: usize| s.binding.variant_of(CardId((VARIANT_BASE + i) as u8)).unwrap();
    assert_eq!(slot(0), (r, sts_engine::registry::Overrides { damage: 1013 }));
    assert_eq!(slot(1), (rp, sts_engine::registry::Overrides { damage: 1016 }));
}
```
Traced under both rules. Value rule: Rampage+{1008} grows to 1016 and lands after Rampage{1008}; Rampage{1008} then grows to 1013, takes slot 1 ahead of Rampage+{1016}, and its old slot is dropped, so the slots end [Rampage{1013}, Rampage+{1016}]. Old index rule: the four entries are interned in the order Rampage+{1016}, Rampage{1013}, Rampage{1008}, Rampage+{1008} (the table is append-only, so other threads can only shift the indices, not reorder them); Rampage+{1016} has the lowest index, goes to slot 0 and stays there, so the test fails however the other tests ran. (`worm`, `variant`, `card`, `Pile`, `CardId`, `Action`, `VARIANT_BASE` are already in scope in overrides.rs.) Alternative: move the test to its own test binary (a fresh process) with the same precondition check; that costs one more release test binary to link with fat LTO. Optionally update decisions.md:2221's description of the test.

**Test first.** The rewritten `engine/tests/overrides.rs::slots_are_ordered_by_value` passes on the current code, and with the `hold_variant` line reverted to the old rule it fails in every mode: alone, with the whole binary in parallel, and with `--test-threads=1`.

**Must stay unchanged.** Only a test changes: engine code, golden files, codec bytes, H4, series_check and every pin are untouched. Every other test in overrides.rs passes.

## Build step details

- **Step 1: E1 + E2. Read the card in play again after hooks; drop variants when a card leaves play.** Files: `engine/src/state.rs` (run()'s `None` arm, `condition_holds`, `check_over`; about 20 lines). Tests: `engine/tests/packs.rs` (4 powers and 4 cards appended to `FIX_PACK`: fx_grow3, fx_shrink5, fx_shrink5_first, fx_grow1_first and their `_card`s; 5 tests: `a_card_grown_by_a_hook_is_filed_as_its_variant`, `a_card_shrunk_onto_a_held_value_is_filed_there`, `monster_hooks_see_the_card_a_play_hook_grew`, `a_grown_power_card_leaves_no_variant`, `a_copy_that_ends_the_combat_leaves_no_variant`) and `engine/tests/common/mod.rs` (the variant-held invariant in `check_invariants`). Acceptance: (a) before editing src: record H4 with `cargo run --release -p sts-engine --example two_turn_phases -- 100 --check target/h4_before.txt`; `cargo test --release -p sts-engine --test packs` shows the 5 new tests failing (two of them panic with "variant card 145 is not held in this combat") and every other packs test passing; `cargo test --release -p sts-engine --test fuzz` passes with the new invariant. (b) after: `cargo test --release -p sts-engine --test packs --test overrides --test decisions --test hooks --test registry --test golden --test fuzz` all pass, and `cargo run --release -p sts-engine --example two_turn_phases -- 100 --check target/h4_after.txt && cmp target/h4_before.txt target/h4_after.txt` prints nothing and exits 0. Find the E2 lines by their text: E1's edit moves everything below line 707 down by one.
- **Step 2: E3. The decoder validates before it interns; a full variant table stops play.** Files: `engine/src/codec.rs` (`try_decode`: two locals before the trailer loop, the section-2 arm, the tail; about 35 lines), `engine/src/state.rs` (`grow_damage`, the `let Some(idx) = ... else { return };` line; about 6 lines). Tests: new `engine/tests/variant_table.rs` (its own binary, one test), `engine/tests/overrides.rs::a_listed_variant_no_card_holds_is_refused`, and the codec round trip in `engine/tests/common/mod.rs` `check_invariants` (skip it if G4's fix already added the same check). Acceptance: (a) add the round-trip guard first and run `cargo test --release -p sts-engine --test fuzz` on the step-1 code: it passes (if not, stop and report a separate bug); the two new tests fail (variant_table at "play 1", the overrides test at its second assertion). (b) after: `cargo test --release -p sts-engine --test variant_table --test overrides --test codec --test decisions --test known_top --test amounts --test packs --test fuzz --test golden` all pass, and `git diff --stat engine/tests/data` is empty.
- **Step 3: E5. The tag-8 decoder refuses picks the engine never makes.** Files: `engine/src/codec.rs` (the tag-8 arm; the pick check in the tail, after step 2's two holder checks and before the `r.at` check and the interning loop; about 12 lines), `engine/src/state.rs` (`pick_source` becomes `pub(crate)`). Test: `engine/tests/decisions.rs::codec_refuses_picks_the_engine_never_makes`. Acceptance: the new test fails before the src edit (at "nothing left to pick"); after, `cargo test --release -p sts-engine --test decisions --test codec --test fuzz` all pass.
- **Step 4: E4. The rules fingerprint hashes registry.rs.** Files: `solvedb/src/fingerprint.rs` (one entry added to `RULE_FILES`, type `[(&str, &str); 9]`), `docs/engine-next.md:80-82` and `docs/specs/exact-solver.md:125-126` (add `registry` to the listed files; engine-next.md says 9 files). Test: `solvedb/tests/fingerprint.rs::rule_files_cover_the_modules_they_use`. Acceptance: before the src edit, `cargo test --release -p solvedb --test fingerprint` fails with "state.rs uses crate::registry, which the fingerprint doesn't hash"; after, it reports 4 passed, and `cargo test --release -p solvedb` passes.
- **Step 5: E6. slots_are_ordered_by_value no longer depends on intern order.** Files: `engine/tests/overrides.rs` (test only); optionally `docs/decisions.md:2221`. Acceptance: `cargo test --release -p sts-engine --test overrides` passes. Mutation check (after steps 1-3): in `hold_variant`, change the line `let j = vs[..n].iter().position(|&v| crate::registry::variant_key(v) > key).unwrap_or(n);` (state.rs:1160 at HEAD; some lines lower after steps 1-3, so find it by its text) to `let j = vs[..n].iter().position(|&v| v > idx).unwrap_or(n);`; then `cargo test --release -p sts-engine --test overrides` and `cargo test --release -p sts-engine --test overrides -- --test-threads=1` must both report `slots_are_ordered_by_value` FAILED (an unused-variable warning for `key` is expected). Revert that one line by hand, not with `git checkout`, so steps 1-3 are kept: `git diff engine/src/state.rs` shows only their changes.
- **Final check:** `cargo test --release` at the worktree root: every engine and solvedb test passes; `git diff --stat engine/tests/data` is empty (golden.txt, golden_proving.txt and codec_golden.txt unchanged); and H4 once more, `cargo run --release -p sts-engine --example two_turn_phases -- 100 --check target/h4_final.txt && cmp target/h4_before.txt target/h4_final.txt` prints nothing. No Python module rebuild is needed: py/ is untouched and official play and features are unchanged. Record the batch in docs/decisions.md the way the project records each review's fixes (one entry, like "Cross-spec review of the series branch" at 2283), including that the fingerprint now hashes registry.rs.

## Pins for this group

No recorded pin, golden set or pinned fingerprint changes. These must stay byte-identical:
- golden.txt (9,000 games) and golden_proving.txt (including the `rampage` set), checked with `cargo test --release -p sts-engine --test golden`. The new drops in run() and check_over change no official state: an official-only combat's variants are always held when a card leaves play (only Rampage grows, Burst replays only Skills, and every pile move keeps the card in some pile).
- codec_golden.txt and every encoding: `encode` is untouched and `CODEC_VERSION` stays 1. The stricter decoder refuses only bytes the engine never writes.
- H4 (`two_turn_phases 100 --check`): recorded before step 1, compared after step 1 and again after the last step (E1 and E2 touch run(), condition_holds and check_over; H4's fights hold no variants and no pack content).
- `content_tables_pinned` (0x5a922915c8ae26dd).
- series_check, the contract pins (test_contract.py), TRAIN_PIN, ARRAYS_PIN, golden_rows, lookahead names and curriculum digests. No feature or Python code changes, so none of these needs re-running.

Expected to change: the rules fingerprint value. E4 adds registry.rs to RULE_FILES, and E1, E2, E3 and E5 edit state.rs, a rule file. Nothing pins the value (data/bench/puzzles.json only records the old one, 39bfc65e541f073d), and this branch already changes it (the solved DB is retired and refilled after the series).

Behaviour that changes on purpose, for pack content and crafted bytes only:
- A card grown by a hook is filed as its variant, and a replayed copy starts as that variant (E1).
- Hook conditions read the card in play as it is now (E1; same result as before unless a hook changed the id).
- A variant no card holds is dropped when its card leaves play or the combat ends (E2).
- try_decode refuses more bytes the engine never writes, and interns nothing for refused bytes (E3, E5).
- A full variant table panics instead of silently stopping growth (E3).

No recorded data moves with these changes: no dataset, pack or script in the repo uses GrowDamage (scripts/gen_content.py never writes it; no .json or .py file contains it), and no Python test decodes hand-made state bytes.

## Decisions for this group

None. One timing note for the manager, not the owner: E4's choice (hash all of engine/src/registry.rs, which I recommend, or move the variant rules into cards.rs) costs nothing to change until the solved database is refilled after the series. After that refill, changing which files the fingerprint hashes retires the refilled rows again (CPU-hours to refill), so settle it before the refill. E3's "a full variant table panics" is cheap to reverse and pack-only, so it is the manager's call, not the owner's.

## Notes the checker left

- Not one of the verified findings, so these are the manager's call. A hook that shrinks a grown card back to its base's value files it as a variant (Rampage{damage=8/combat}), a different card id from the base Rampage, though the two play the same. So equal positions can still differ by id. E1's second test expects this current behaviour. If the manager decides `grow_damage` should map "damage == the base's damage" back to the base card, that test's expected id changes from 144 to plain Rampage.
- `damage + k` in grow_damage is i16 arithmetic. Extreme pack values, or a crafted decoded variant near i16::MAX, overflow it: a panic in debug builds, a silent wrap in release. D7's verifier recorded this as an aside, and no group owns it. E3's edit makes generated cards return before the addition, but official bases still reach it.
- Optional, not done: py/src/lib.rs `fetch` and `positions` still call `decode`, which panics. With a full variant table, a valid row naming an unseen variant becomes a PanicException rather than a Python error.
- Coordination with other groups' fixes, which the builder can act on. C1 edits only `do_effect`'s ReplayCard arm, not run()'s card-finished arm. C3 may scale GrowDamage by stacks, which leaves E's tests unaffected. D7 doesn't touch grow_damage; the main file's build step 17 makes its `damage + k` saturating, and E3 keeps that. G4 adds its round trips to engine/tests/codec.rs, not to check_invariants, so E3's guard isn't duplicated.
