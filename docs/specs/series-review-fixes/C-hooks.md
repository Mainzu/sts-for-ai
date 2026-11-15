# Series review fixes, group C: hook effects

Status: confirmed (2026-11-02, C1-C5 are in the generator-hardening bundle, unbuilt; decisions 'Series review fixes: the cut').

Part of `docs/specs/series-review-fixes.md`. Read that file first: it has the why, what must
stay true, the decisions, the build order and how to build and check. This file holds the
group's entries, then its build step details, the pins it may change, its decisions and the
notes its checker left. Line numbers are at `d9327a2`.

## Findings

### C1. A ReplayCard hook re-arms on its own replayed copy, so play never ends

- **Severity:** medium · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED (review item v02; the verifier ran a throwaway test in debug and release)
- **Where:** `engine/src/state.rs:1076-1080` in `do_effect` (the `Effect::ReplayCard` arm; its comment is line 1075). Related: `engine/src/state.rs:703-730` in `run` (the `None =>` arm: `card_resolved` at 704, `finish_card` at 707, then the copy restart: `self.cards_played_this_turn += 1;` at 716, `let more = InPlay { pick: None, replays: replays - 1, copy: true };` at 717, `if self.card_played(card, target) {` at 719); `engine/src/state.rs:940` in `card_resolved`; `engine/src/state.rs:913-923` in `card_played`; `engine/src/state.rs:606` in `apply_action` (the only call of `owner_plays_card`); `engine/src/effects.rs:117-119` (the `ReplayCard` doc); `engine/src/registry.rs:674-718` (`parse_hook`, `runs_outside_a_card`).

**What goes wrong.** A hook is one row of a power: a trigger, a condition and effects. `ReplayCard` in a hook asks for the card in play to be played once more after it resolves (Burst). The arm is

```rust
Effect::ReplayCard => {
    if let Stage::PlayingCard { ref mut more, .. } = self.stage {
        more.replays += 1;
    }
}
```

It adds a replay whenever a card is in play and never looks at `more.copy`, the flag that marks the card in play as a replayed copy (a copy costs nothing, counts as played and goes to no pile). When a card's effects run out, `run` calls `card_resolved`. That runs the player's `OwnerLostHp { from: Card }` hooks for HP the card cost, then the player's `CardPlayed { by: Owner }` hooks, then each monster's damaging after-card hooks. `run` then reads `replays`. If it is above 0, `run` starts a copy, adds 1 to `cards_played_this_turn` and calls `card_played` (the monsters' `CardPlayed { by: Opponent }` hooks) for the copy. So a `ReplayCard` hook under `CardPlayed { by: Owner }` fires again for each copy and adds a new replay every time, and so does a monster's `CardPlayed { by: Opponent }` hook. The card replays itself without end. Only `OwnerPlaysCard` skips copies, because `owner_plays_card` runs only from `apply_action`. The pack loader (`parse_hook`) accepts `ReplayCard` under any trigger, and nothing bounds the loop unless the same hook also uses up its power (Burst's `ReduceSelf(1)`). In a debug build `cards_played_this_turn` (a `u8`) overflows at state.rs:716 and panics. In release `apply_action` never returns, so `Combat.step`, `sts.run`, search and the solver hang. Official content can't reach this: the only official `ReplayCard` is Burst's, under `OwnerPlaysCard`.

**Reproduce.** Load this pack with `registry::load_pack` (it loads as written):

```json
{"version": 1,
 "powers": [
  {"id": "c1_echo", "hooks": [{"trigger": {"CardPlayed": {"by": "Owner"}}, "condition": {"CardType": "Attack"}, "effects": ["ReplayCard"]}]},
  {"id": "c1_mirror", "hooks": [{"trigger": {"CardPlayed": {"by": "Opponent"}}, "condition": {"CardType": "Attack"}, "effects": ["ReplayCard"]}]}
 ],
 "cards": [
  {"id": "c1_echo_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "c1_echo", "amount": 1, "target": "Me"}}]},
  {"id": "c1_mirror_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "c1_mirror", "amount": 1, "target": "Opponent"}}]}
 ]}
```

Build the combat with `bound_combat(deck, hand)` from `engine/tests/packs.rs:67`. It binds the deck and sets up an Ironclad at 80/80 HP against a Jaw Worm at 100 HP with no block. The hand is given as deck indices, the draw and discard piles are empty, and the player has 3 energy. A card is targeted when one of its effects targets `Opponent` (`CardDef::targeted`), so `c1_mirror_card` is played on `Some(0)` and `c1_echo_card` with `None`.

- **Case A (the player's hook).** Deck `["gen:c1_echo_card", "Strike"]`, hand `&[0, 1]`. Play `gen:c1_echo_card` (target `None`), then `Strike` on `Some(0)`.
  - Expected: the Strike and one copy. The monster ends at 88, `cards_played_this_turn == 3`, `stage == Stage::PlayerTurn`, and the discard pile holds one Strike.
  - Actual: 17 Strikes. The monster ends at 0, the combat is won, and `cards_played_this_turn == 18`.
- **Case B (the monster's hook).** Deck `["gen:c1_mirror_card", "Strike"]`, hand `&[0, 1]`. Play `gen:c1_mirror_card` on `Some(0)`, which puts `c1_mirror` on the monster, then `Strike` on `Some(0)`. Expected and actual are the same as in case A.

The test uses Attack-conditioned hooks because the loop then ends when the monster dies. An unconditioned hook with Defend has no exit: release hangs and debug panics at state.rs:716.

**Fix.** In `do_effect`'s `ReplayCard` arm, add a replay only when the card in play is not itself a copy:

```rust
// Burst: one more play of the card in play once it resolves. A replayed
// copy is never replayed again (the game's replay powers skip copies).
Effect::ReplayCard => {
    if let Stage::PlayingCard { ref mut more, .. } = self.stage {
        if !more.copy {
            more.replays = more.replays.saturating_add(1);
        }
    }
}
```

Every replay power in the game skips copies (Burst, Double Tap and Echo Form check `purgeOnUse`). Say the same in the `Effect::ReplayCard` doc (effects.rs:117-118), for example: "In a hook: the card in play is played once more after it resolves (Burst). A replayed copy is never replayed again, so this does nothing while a copy is in play." The guard bounds every trigger at once: hooks that fire during a copy can't add replays, so only the original play can, and each copy uses one up. `saturating_add` stays because one original play can still fire many `ReplayCard` hooks (a monster's `OwnerAttacked` hook fires once per hit); it only keeps a debug build from panicking on the `u8`. Keep the loader as it is. Spec 10 wants packs to carry every trigger, and with the guard every pairing plays and ends.

- Alternative: refuse `ReplayCard` at load unless the trigger is `OwnerPlaysCard` (the game's only replay timing). It refuses packs that load today and leaves the engine unguarded.
- Don't make `OwnerPlaysCard` fire for copies.
- Don't add a replay cap or depth counter as a `CombatState` field. The state is hashed, compared and encoded.

**Test first.** Add to `engine/tests/packs.rs` (it already has `use sts_engine::*;`, which brings `Stage`, `Action`, `CardId` and `Rng`; it does not use `tests/common`):

```rust
const C1_PACK: &str = r#"<the pack above>"#;

#[test]
fn a_replayed_copy_is_not_replayed_again() {
    load_pack(C1_PACK).unwrap();
    let strike = CardId::from_name("Strike").unwrap();
    // Case A: the player's CardPlayed-by-Owner hook; case B: the monster's CardPlayed-by-Opponent hook.
    for (power_card, target) in [("gen:c1_echo_card", None), ("gen:c1_mirror_card", Some(0))] {
        let deck = [power_card, "Strike"];
        let card = bind(&deck).unwrap().0[0];
        let mut s = bound_combat(&deck, &[0, 1]);
        s.apply_action(Action::Play { card, target }).unwrap();
        s.apply_action(Action::Play { card: strike, target: Some(0) }).unwrap();
        assert_eq!(s.monsters[0].hp, 88, "{power_card}: the Strike and one copy");
        assert_eq!(s.cards_played_this_turn, 3, "{power_card}");
        assert_eq!(s.stage, Stage::PlayerTurn, "{power_card}");
        assert_eq!(s.discard.count(strike), 1, "{power_card}");
    }
}
```

On the current code it fails (HP 0, 18 cards); it doesn't hang, in debug or release.

**Must stay unchanged.** Burst never reaches a copy (its hook is `OwnerPlaysCard`, which copies never fire), and its replay is added while the original is in play, so it reads the same. These stay identical:
- `golden.txt` (9,000 games) and `golden_proving.txt` (its `survivor` set holds Burst and Burst+).
- `codec_golden.txt`.
- The tests in `decisions.rs` (`burst_replays_next_skill`, `burst_replays_survivor_with_two_picks`, `codec_round_trips_picks_and_replays`) and `packs.rs::a_replayed_copys_grown_variant_is_dropped`.
- series_check, the contract pins and H4.

No pin changes. The rules fingerprint moves because of the code edit in state.rs (a rule file); the fingerprint strips comments, so the effects.rs doc edit alone would not move it. The branch already moves it.

### C2. A hook's attack fires OwnerAttacked hooks again and can recurse until the stack overflows

- **Severity:** medium · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED (review item sw_rules_1; the verifier ran a throwaway test, crashing cases in child processes)
- **Where:** `engine/src/state.rs:1425-1440` in `attack` (`let hooked = ...` at 1431, the `if` at 1432, `run_hooks_with` at 1438); related: `engine/src/state.rs:983` in `run_hooks_with` (hook effects go to `do_effect`), `engine/src/state.rs:1012-1032` in `do_effect` (the `Damage` arm at 1014, `ScaledDamage` at 1021-1024 and `RolledAttack` at 1028-1032 call `deal`), `engine/src/state.rs:1086-1102` in `deal`, `engine/src/chance.rs:140` in `random_hit` (the only other caller of `attack`), `engine/src/hooks.rs:47-50` (`Trigger::OwnerAttacked` and its doc), `engine/src/hooks.rs:208` (Thorns), `engine/src/registry.rs:674-718` (`parse_hook`), `docs/extending.md:74` (the pack-author description of `OwnerAttacked`).

**What goes wrong.** `attack` deals one attack hit (Strength, Weak, Vulnerable and the static rows apply, then replacements, then block). It then runs the target's `OwnerAttacked` hooks (the trigger "my owner was hit by an attack", used by Thorns) on every hit, blocked or not. It never asks where the hit came from, so a hit made by a hook counts too.

Take a pack power whose `OwnerAttacked` hook holds `Damage` or `ScaledDamage` aimed at its own owner (`"target": "Me"`), or at `Attacker` while the other side holds a power like it. It attacks again from inside its own hook: `run_hooks_with` → `do_effect` → `deal` → `attack` → `run_hooks_with` → and so on. Nothing guards against re-entry. With a pack bound, `hooked` is always true (`!self.binding.is_empty()`), so the recursion ends only when the player dies or every monster dies.

A hit can do 0 damage: Weak on an amount of 1 (3/4 rounds down to 0), a `DamageTaken` `Cancel` replacement, or an amount of 0. A 0 hit never kills. In no-death mode (training's simulation, where the player's HP may go below 0), `player_dead()` is always false (state.rs:820). Either way the recursion never ends, and the process aborts with a stack overflow (Windows 0xC00000FD). That is a hard abort, not a panic, so it also kills a Python process that uses `sts`.

In the game, damage from a power is Thorns-type, and `onAttacked` reactions ignore it; decisions.md:312 maps that type to `PlainDamage`. The engine's official Thorns, Sharp Hide and Combust use `PlainDamage` (non-attack damage, which never calls `attack`), so official content can't reach this.

**Reproduce.** Pack (loads as written; a hook with no `condition` gets `Always`):

```json
{"version": 1,
 "powers": [{"id": "c2_spite", "hooks": [{"trigger": "OwnerAttacked", "effects": [{"Damage": {"amount": 1, "target": "Me"}}]}]}],
 "cards": [
  {"id": "c2_curse", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "c2_spite", "amount": 1, "target": "Opponent"}}]},
  {"id": "c2_self", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "c2_spite", "amount": 1, "target": "Me"}}]}
 ]}
```

Use `bound_combat` from `engine/tests/packs.rs:67` (Ironclad 80/80 against a Jaw Worm at 100 HP with no block).

- **Case A (the monster holds the power).** Deck `["gen:c2_curse", "Strike"]`, hand `&[0, 1]`. Set `s.monsters[0].hp = 20` and `max_hp = 20`. Play `gen:c2_curse` on `Some(0)`, then `Strike` on `Some(0)`.
  - Expected: 6 from the Strike, then the hook hits the monster once for 1. The monster ends at 13 and the combat keeps running.
  - Actual: each of the hook's own hits fires it again until the monster is at 0, and the combat is won.
- **Case B (the player holds the power).** Deck `["gen:c2_self"]`, hand `&[0]`. Set `s.player.hp = 20`. Play `gen:c2_self` (target `None`), then `s.step(Action::EndTurn, &mut Rng::new(7))`. The Jaw Worm always opens with Chomp, 11 damage (monsters.rs:279, 548); packs.rs's Intangible test relies on the same.
  - Expected: 20 − 11 − 1 = 8.
  - Actual: the player hits itself down to 0 and loses.

Both cases end on the current code because every hit costs HP. The same setups overflow the stack with Weak 1 on the monster in case A (`s.monsters[0].powers.add(Power::Weak, 1)` after the curse), or with `s.no_death = true` in case B.

**Fix.** Treat a hook's hits as reactions, as the game does. They still go through the attack pipeline (Strength, Weak, Vulnerable, statics, replacements, block, `OwnerLostHp { from: Attack }`), but they fire no `OwnerAttacked` hooks. All in state.rs unless named:
- `fn do_effect(&mut self, actor: Who, e: &Effect, chosen: Option<u8>, from_hook: bool)`. Pass `false` at its calls in `run` (699: `self.do_effect(Who::Player, &e, target, false)`) and `end_turn` (841 and 876), and `true` in `run_hooks_with` (983: `(e, ..) => self.do_effect(owner, &e.scaled(stacks), ctx.target, true)`). There are no other callers.
- In `do_effect`, the `Damage` and `ScaledDamage` arms pass `from_hook` to `deal`; `RolledAttack` (a monster's move) passes `false`.
- `fn deal(&mut self, actor: Who, target: Target, chosen: Option<u8>, base: i16, hits: u8, from_hook: bool)` calls `self.attack(actor, dst, base, from_hook)`.
- `pub(crate) fn attack(&mut self, src: Who, dst: Who, base: i16, from_hook: bool)` runs the hooks only for a hit that isn't a hook's: `if hooked && !from_hook && !self.player_dead() && self.living_slots().next().is_some()`. Extend its comment (1428-1429): a hook's own hits (`from_hook`) are reactions and fire none.
- `engine/src/chance.rs:140` (`random_hit`, a card's random hits): `_ => self.attack(Who::Player, Who::Monster(slot as u8), amount, false),`.

Update the docs. `Trigger::OwnerAttacked` (hooks.rs:47-49) becomes: every attack hit on the owner from a card (played, or held at turn end) or a monster's move, blocked or not, after block and HP loss, unless the combat is over; a hook's own hits are reactions and don't fire it, so hooks can't attack each other forever. Add to `Effect::Damage` (effects.rs:77): in a hook it is a reaction, still dealt through the attack pipeline, but it fires no `OwnerAttacked` hooks. Change docs/extending.md:74 the same way ("every attack hit on its owner from a card or a monster's move"). Record the rule in docs/decisions.md (see the build steps). With this change, no hook can make an `OwnerAttacked` hook fire, so this trigger can't recurse at all. A chain through `OwnerLostHp` still needs HP lost at every step.

- Alternative: skip only hits made by an `OwnerAttacked` hook (pass `h.trigger == Trigger::OwnerAttacked` as the flag). It is narrower, but an `OwnerAttacked` → `OwnerLostHp` → `OwnerAttacked` loop then ends only through HP loss.
- Don't rewrite pack `Damage` as `PlainDamage` at load: that drops Strength and Vulnerable.
- Don't add a depth counter or a "hook running" flag to `CombatState`.

Not covered by this fix (found while checking; not a verified finding; listed under unresolved): `take_damage` (state.rs:1480-1493) works out `lost` (1486) before it applies the HP floor (1489), so it reports HP lost even at the no-death floor (`i16::MIN / 2`); `lose_hp` (1496-1507) reports only what was actually lost. An `OwnerLostHp` hook that damages its own owner therefore recurses once per HP point, without a practical end in no-death mode. The generator never emits such a hook (its `Damage` targets only `AllOpponents`, and `allowed()` refuses `OwnerLostHp` with `LoseHp`), but the loader doesn't refuse one.

**Test first.** In `engine/tests/packs.rs`:

```rust
const C2_PACK: &str = r#"<the pack above>"#;

/// Case A: the monster holds c2_spite at 20 HP (optionally Weak 1) and takes a
/// Strike. Returns its HP and whether the combat is over.
fn c2_monster(weak: bool) -> (i16, bool) {
    load_pack(C2_PACK).unwrap();
    let deck = ["gen:c2_curse", "Strike"];
    let curse = bind(&deck).unwrap().0[0];
    let mut s = bound_combat(&deck, &[0, 1]);
    s.monsters[0].hp = 20;
    s.monsters[0].max_hp = 20;
    s.apply_action(Action::Play { card: curse, target: Some(0) }).unwrap();
    if weak {
        s.monsters[0].powers.add(Power::Weak, 1);
    }
    s.apply_action(Action::Play { card: CardId::from_name("Strike").unwrap(), target: Some(0) }).unwrap();
    (s.monsters[0].hp, s.is_over())
}

/// Case B: the player holds c2_spite at 20 HP and ends the turn into Chomp (11).
fn c2_player(no_death: bool) -> (i16, bool) {
    load_pack(C2_PACK).unwrap();
    let deck = ["gen:c2_self"];
    let card = bind(&deck).unwrap().0[0];
    let mut s = bound_combat(&deck, &[0]);
    s.player.hp = 20;
    s.no_death = no_death;
    s.apply_action(Action::Play { card, target: None }).unwrap();
    s.step(Action::EndTurn, &mut Rng::new(7)).unwrap();
    (s.player.hp, s.is_over())
}

#[test]
fn a_hooks_hit_fires_no_owner_attacked_hooks() {
    assert_eq!(c2_monster(false), (13, false), "the Strike's 6, then one hit of 1");
    assert_eq!(c2_player(false), (8, false), "Chomp's 11, then one hit of 1");
    // 0-damage hits and no-death mode: one hit, no recursion. Keep these after
    // the two above: on the old code those fail first, so these never run (on
    // the old code they overflow the stack and abort the whole test binary).
    assert_eq!(c2_monster(true), (14, false), "the hook's hit is 0 under Weak");
    assert_eq!(c2_player(true), (8, false), "no-death mode");
}
```

On the current code the first assert fails with `(0, true)`.

**Must stay unchanged.** Official hooks never call `attack` (they use `PlainDamage`), and hits from cards, monster moves and random hits pass `from_hook = false`. These stay identical:
- `golden.txt` and `golden_proving.txt` (its `wraith` set holds Caltrops' Thorns).
- `codec_golden.txt`.
- `replacements.rs` (`caltrops_hits_back_every_hit`, `attacker_dying_mid_move_stops_its_hits`, `round_end_and_replacement_lists_match_the_tables`) and the Sharp Hide tests in `act1_bosses.rs` (`sharp_hide_hits_after_the_card_for_attacks_only`, `sharp_hide_spares_a_card_that_kills_its_owner`).
- series_check, the contract pins and H4.

No pin changes. No pack in `data/` holds an `OwnerAttacked` hook. `data/bench/gen_powers_pack.json` does hold 28 player hooks with `Damage` on `AllOpponents` (turn start, turn end, `CardPlayed { by: Owner }`, `OwnerLostHp`); after the fix their hits skip the monsters' `OwnerAttacked` scan, but no monster ever holds an `OwnerAttacked` power (Thorns is player-only and the generator grants its powers only to the player), so recorded generated-content games replay the same. Their `OwnerLostHp { from: Attack }` reactions (Curl Up) still fire as before.

### C3. AddCard, ScaledDamage and GrowDamage in a hook ignore the power's stacks; a monster's ScaledDamage hook fires before the card

- **Severity:** medium · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED (review item v14; the verifier read the code and ran nothing)
- **Where:** `engine/src/effects.rs:126-138` in `Effect::scaled` (the `e => e,` arm at 136) and `engine/src/hooks.rs:233-236` in `Hook::after_card`; related: `engine/src/state.rs:983` in `run_hooks_with`, `engine/src/state.rs:917` in `card_played` and `:945` in `card_resolved` (where `after_card` decides the timing), `py/src/features.rs:950` and `:969` (the net's hook rows call the same `scaled`), `engine/src/state.rs:703-719` in `run` (the extra defect below: `finish_card` at 707, the copy restart at 718).

**What goes wrong.** A power's stacks are its count on its owner, and a hook's amounts are per stack. hooks.rs:2-3, hooks.rs:156-158 ("Amounts are multiplied by the stacks the power had when the hook fired") and decisions.md:304 all say so. `run_hooks_with` handles a few effects itself and runs every other one as `self.do_effect(owner, &e.scaled(stacks), ctx.target)`. `Effect::scaled` multiplies Damage, PlainDamage, Block, Draw, GainEnergy, LoseHp and Apply, and passes everything else through `e => e` unchanged. So in a hook these three effects use their written numbers whatever the stacks:
- `AddCard { n }`: n copies of a card into a pile.
- `ScaledDamage { amount }`: an attack whose amount can read the state, `base + k × quantity`.
- `GrowDamage(k)`: the card in play's damage grows by k for the combat.

Separately, `Hook::after_card` decides that a monster's `CardPlayed { by: Opponent }` hook that deals damage fires after the player's card resolves (Sharp Hide: Iron Wave's block comes first). It checks only `matches!(e, Effect::Damage { .. } | Effect::PlainDamage { .. })`, so the same hook written with `ScaledDamage` fires before the card.

The feature rows use the same `scaled`, so the net agrees with play; both are wrong against the documented rule. Main's pack parser could express none of these effects. Spec 10 (pack-every-atom) made them legal in pack hooks without updating `scaled` or `after_card`. No official hook holds `AddCard`, `ScaledDamage` or `GrowDamage` (every table in hooks.rs checked), and no pack in `data/` does either.

**Reproduce.** Pack (loads as written; an integer `amount` for `ScaledDamage` is a constant, and `hits` defaults to 1):

```json
{"version": 1,
 "powers": [
  {"id": "c3_blades", "hooks": [
    {"trigger": "OwnerTurnEnd", "effects": [{"ScaledDamage": {"amount": 2, "target": "AllOpponents"}}]},
    {"trigger": "OwnerTurnStart", "effects": [{"AddCard": {"card": "Shiv", "n": 1, "pile": "Hand"}}]}]},
  {"id": "c3_grow", "hooks": [{"trigger": "OwnerPlaysCard", "condition": {"CardType": "Attack"}, "effects": [{"GrowDamage": 2}]}]},
  {"id": "c3_hide", "hooks": [{"trigger": {"CardPlayed": {"by": "Opponent"}}, "condition": {"CardType": "Attack"}, "effects": [{"ScaledDamage": {"amount": 3, "target": "Opponent"}}]}]},
  {"id": "c3_late_grow", "hooks": [{"trigger": {"CardPlayed": {"by": "Owner"}}, "condition": {"CardType": "Attack"}, "effects": [{"GrowDamage": 2}]}]}
 ],
 "cards": [
  {"id": "c3_blades_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "c3_blades", "amount": 3, "target": "Me"}}]},
  {"id": "c3_grow_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "c3_grow", "amount": 3, "target": "Me"}}]},
  {"id": "c3_hide_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "c3_hide", "amount": 1, "target": "Opponent"}}]},
  {"id": "c3_late_grow_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "c3_late_grow", "amount": 1, "target": "Me"}}]}
 ]}
```

Use `bound_combat` from `engine/tests/packs.rs:67` (Ironclad 80/80 against a Jaw Worm at 100 HP with no block, empty piles, 3 energy).

- **(a)** Deck `["gen:c3_blades_card"]`, hand `&[0]`. Play it (target `None`; 3 stacks on the player), then `s.step(Action::EndTurn, &mut Rng::new(7))`.
  - Expected: the turn-end hook deals 2 × 3 = 6, so the monster ends at 94, and the next turn starts with `hand.count(Shiv) == 3` (the piles are empty, so nothing else is drawn).
  - Actual: the monster ends at 98, with 1 Shiv.
- **(b)** Deck `["gen:c3_grow_card", "Strike"]`, hand `&[0, 1]`. Play the power card (3 stacks of an `OwnerPlaysCard` hook, which fires before the card's effects), then `Strike` on `Some(0)`.
  - Expected: the Strike grows by 2 × 3 before it hits and deals 12, so the monster ends at 88. The discard pile then holds a variant: a copy with its own damage number, kept in a slot of the binding (the per-combat table of reserved card and power slots). Here `s.binding.variant_of(card) == Some((Strike, registry::Overrides { damage: 12 }))`, where `card` is the discard pile's only card.
  - Actual: 8 damage, and the variant has damage 8.
- **(c)** Deck `["gen:c3_hide_card", "Iron Wave"]`, hand `&[0, 1]`. Play `gen:c3_hide_card` on `Some(0)`; the player has 0 block. Then play `Iron Wave` on `Some(0)`.
  - Expected, as Sharp Hide: Iron Wave's 5 block comes first, then the 3 damage, so the player keeps 80 HP with block 2.
  - Actual: 77 HP, block 5.

**Fix.**
- In `Effect::scaled` (effects.rs), add three arms before `e => e`:

  ```rust
  // Hits stay, like Damage's.
  Effect::ScaledDamage { amount, hits, target } => {
      Effect::ScaledDamage { amount: Amount { base: amount.base * k, k: amount.k * k, of: amount.of }, hits, target }
  }
  // Clamped: the features call this with any non-zero stacks, negative ones too.
  Effect::AddCard { card, n, pile } => Effect::AddCard { card, n: n.saturating_mul(k.clamp(0, u8::MAX as i16) as u8), pile },
  Effect::GrowDamage(n) => Effect::GrowDamage(n * k),
  ```

  Don't copy Draw's `n * k as u8` for `AddCard`: `features.rs` calls `scaled` with negative stacks (`entity_power_rows` skips only 0) and with a card's Apply amount (`granted_rows`), where `k as u8` wraps and the product can overflow a `u8`. In play, hooks only fire with stacks above 0, so the clamp changes nothing there.
- Leave `ReplayCard` unscaled on purpose: one replay per firing, and Burst uses up one stack per replay. `RemoveSelf` and `ReduceSelf` act on the power. Say both in `scaled`'s doc, and list the three new effects there.
- In `Hook::after_card` (hooks.rs:235), add `Effect::ScaledDamage { .. }` to the `matches!`.
- The features follow by themselves, because they call the same `scaled`. Don't special-case these effects in `run_hooks_with`: the net would then disagree with play.

**Extra defect found while checking (not in the review; confirmed by reading the code, and its test below fails on the current code).** (b) uses `OwnerPlaysCard` for a reason. A `GrowDamage` hook that fires inside `card_resolved` loses its growth; that covers a `CardPlayed { by: Owner }` hook, an `OwnerLostHp { from: Card }` hook and a monster's after-card hook. `run` copies `card` out of the stage at the top of the loop (state.rs:679), `card_resolved` then changes the stage's card to the grown variant, and `run` calls `self.finish_card(card, more.copy)` (state.rs:707) with the old id. So:
- the base card goes to the discard pile;
- the variant stays in the binding with no card holding it, a leaked slot that breaks spec 8's "a variant no copy holds is dropped". The binding is part of the state, so two otherwise equal games then compare, hash and encode differently;
- if the card in play was already a variant that another copy also holds, the discard gets the old variant instead of the grown one;
- a replayed copy (state.rs:718) also plays the old id.

Hooks that fire before or during the card's effects are fine, because the loop reads the stage again on its next pass. Fix it in the same step: right after the `card_resolved` call (state.rs:704-706), read the card in play again, and use it for `finish_card` and the copy restart:

```rust
if self.card_resolved(card, target) {
    return;
}
// Read again: a hook in `card_resolved` may have grown the card in play.
let card = match self.stage {
    Stage::PlayingCard { card, .. } => card,
    _ => card,
};
self.finish_card(card, more.copy);
```

Official hooks never grow a card, so official play reads the same.

**Test first.** All three tests fail on the current code. Add `use sts_engine::effects::{Amount, Effect, PileKind, Quantity, Target};` to `engine/tests/packs.rs`, and the pack above as `const C3_PACK: &str = r#"..."#;`.

```rust
#[test]
fn hook_amounts_scale_with_stacks() {
    load_pack(C3_PACK).unwrap();
    let (shiv, strike) = (CardId::from_name("Shiv").unwrap(), CardId::from_name("Strike").unwrap());
    // The rule itself.
    assert_eq!(Effect::AddCard { card: shiv, n: 1, pile: PileKind::Hand }.scaled(3), Effect::AddCard { card: shiv, n: 3, pile: PileKind::Hand });
    let sd = |amount| Effect::ScaledDamage { amount, hits: Amount::constant(1), target: Target::Opponent };
    assert_eq!(sd(Amount::of(2, 1, Quantity::OwnBlock)).scaled(3), sd(Amount::of(6, 3, Quantity::OwnBlock)));
    assert_eq!(Effect::GrowDamage(2).scaled(3), Effect::GrowDamage(6));
    // (a) 3 stacks: 2 x 3 damage at turn end, 1 x 3 Shivs at the next turn start.
    let deck = ["gen:c3_blades_card"];
    let card = bind(&deck).unwrap().0[0];
    let mut s = bound_combat(&deck, &[0]);
    s.apply_action(Action::Play { card, target: None }).unwrap();
    s.step(Action::EndTurn, &mut Rng::new(7)).unwrap();
    assert_eq!((s.monsters[0].hp, s.hand.count(shiv)), (94, 3));
    // (b) 3 stacks of +2 before the card's effects: the Strike deals 12 and is kept at 12.
    let deck = ["gen:c3_grow_card", "Strike"];
    let card = bind(&deck).unwrap().0[0];
    let mut s = bound_combat(&deck, &[0, 1]);
    s.apply_action(Action::Play { card, target: None }).unwrap();
    s.apply_action(Action::Play { card: strike, target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 88);
    let held: Vec<(CardId, u8)> = s.discard.iter().collect();
    assert_eq!(held.len(), 1);
    assert_eq!(s.binding.variant_of(held[0].0), Some((strike, registry::Overrides { damage: 12 })));
}

#[test]
fn a_monsters_scaled_damage_hook_fires_after_the_card() {
    load_pack(C3_PACK).unwrap();
    let deck = ["gen:c3_hide_card", "Iron Wave"];
    let ids = bind(&deck).unwrap().0;
    let mut s = bound_combat(&deck, &[0, 1]);
    s.apply_action(Action::Play { card: ids[0], target: Some(0) }).unwrap();
    assert_eq!((s.player.hp, s.player.block), (80, 0));
    s.apply_action(Action::Play { card: ids[1], target: Some(0) }).unwrap();
    assert_eq!((s.player.hp, s.player.block), (80, 2), "Iron Wave's 5 block, then the hook's 3");
}

#[test]
fn a_card_grown_by_a_late_hook_keeps_its_growth() {
    load_pack(C3_PACK).unwrap();
    let strike = CardId::from_name("Strike").unwrap();
    let deck = ["gen:c3_late_grow_card", "Strike"];
    let card = bind(&deck).unwrap().0[0];
    let mut s = bound_combat(&deck, &[0, 1]);
    s.apply_action(Action::Play { card, target: None }).unwrap();
    s.apply_action(Action::Play { card: strike, target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 94, "it grows after it hit");
    assert_eq!(s.discard.count(strike), 0);
    let held: Vec<(CardId, u8)> = s.discard.iter().collect();
    assert_eq!(held.len(), 1);
    assert_eq!(s.binding.variant_of(held[0].0), Some((strike, registry::Overrides { damage: 8 })));
    assert_eq!(s.binding.n_variants(), 1);
}
```

The `(80, 2)` in the second test are the same numbers as `act1_bosses.rs::sharp_hide_hits_after_the_card_for_attacks_only`. The third test fails on the current code because the discard pile holds the base Strike; it needs the re-read, not the `scaled` arms.

**Must stay unchanged.** No official hook holds these effects or grows a card. Official monster `CardPlayed { by: Opponent }` hooks use `Apply` (Enrage) or `PlainDamage` (Sharp Hide). These stay identical:
- `golden.txt` and `golden_proving.txt` (including the `rampage` and `survivor` sets).
- `codec_golden.txt`.
- series_check (every old feature column of official content), the contract pins, `golden_rows.npz` and the other Python pins, and H4.

`decisions.rs` (Burst), `overrides.rs` (Rampage, including `a_full_slot_table_still_grows_the_copy_that_frees_its_slot`), `act1_bosses.rs` (Sharp Hide), `hooks.rs` (`metallicize_block_scales_with_stacks`) and `packs.rs::a_replayed_copys_grown_variant_is_dropped` pass unchanged. What changes on purpose: the feature rows of pack hooks that hold `AddCard`, `ScaledDamage` or `GrowDamage`. No pin, test pack or pack in `data/` has such hooks (`gen_powers_pack.json`'s hooks hold only Apply, RemoveSelf, ReduceSelf, Block, Damage, PlainDamage, Draw, LoseHp and GainEnergy).

### C4. CardsPlayedThisTurnBelow counts one card too few in a hook that fires outside a card

- **Severity:** medium · **Reach:** content packs · **New on this branch:** partly (the line is main's; this branch's loader is the first to let a hook carry the condition) · **Review:** CONFIRMED (review item v12; the verifier ran a throwaway test)
- **Where:** `engine/src/state.rs:1005-1006` in `condition_holds`; related: `engine/src/state.rs:834` in `end_turn` (the player's `OwnerTurnEnd` hooks, no card in play), `engine/src/state.rs:749` in `run` (the counter resets only at the player's turn start), `engine/src/registry.rs:699` in `parse_hook` (hooks now use the shared `condition()` parser), `engine/src/cards.rs:508-509` (FTL, the only official user), `engine/src/hooks.rs:99` (the variant), `docs/decisions.md:311` (the rule).

**What goes wrong.** `condition_holds` evaluates the condition as

```rust
// Cards played before the one in play (the counter includes it).
Condition::CardsPlayedThisTurnBelow(n) => self.cards_played_this_turn.saturating_sub(1) < n,
```

That is right for a card row (FTL's draw: the counter already counts FTL) and for hooks that fire while a card is in play. Outside a card there is no card in play to subtract, but the code still subtracts 1, so the condition sees one card fewer than were played. Every hook that fires while no card is in play therefore fires at count ≤ n instead of count < n:
- the player's `OwnerTurnEnd` hooks, which `end_turn` runs with `HookCtx::default()`;
- `RoundEnd` hooks;
- the monsters' turn-start and turn-end hooks;
- hooks that fire during the monsters' moves, such as the player's `OwnerAttacked` and `OwnerLostHp` hooks when a monster attacks.

Because of `saturating_sub`, 0 cards and 1 card also look the same. The player's `OwnerTurnStart` hooks are fine (the counter is reset to 0 first), and so are hooks that fire while a card is in play. On main, packs could put only `Always` or `CardType` on a hook; spec 10 gave hooks the shared condition parser, which exposed this line.

**Reproduce.** Pack (loads as written):

```json
{"version": 1,
 "powers": [{"id": "c4_few", "hooks": [{"trigger": "OwnerTurnEnd", "condition": {"CardsPlayedThisTurnBelow": 3}, "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]}]}],
 "cards": [{"id": "c4_few_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "c4_few", "amount": 1, "target": "Me"}}]}]}
```

Use `bound_combat` from `engine/tests/packs.rs:67` with deck `["gen:c4_few_card", "Defend", "Defend"]` and hand `&[0, 1, 2]` (two Defends). Play `gen:c4_few_card`, then Defend, then Defend (3 cards, all with target `None`), then `s.step(Action::EndTurn, &mut Rng::new(7))`.
- Expected: "fewer than 3 cards this turn" is false, so the player has 0 Strength.
- Actual: Strength 1, because 3 − 1 = 2 < 3.

Control: a fresh combat with hand `&[0, 1]`, where only the power card and one Defend are played (2 cards). Both versions give Strength 1.

**Fix.** Subtract the card in play only while a card is in play:

```rust
// Cards played this turn before the card in play, if one is in play (the
// counter includes it from the moment it leaves the hand).
Condition::CardsPlayedThisTurnBelow(n) => {
    let in_play = matches!(self.stage, Stage::PlayingCard { .. }) as u8;
    self.cards_played_this_turn.saturating_sub(in_play) < n
}
```

Test the stage, not `ctx.card`. While a card is still counted, `card_resolved` runs the `OwnerLostHp { from: Card }` hooks with a default context, and `attack` gives the monsters' `OwnerAttacked` hooks `card: None`; both still need the 1 subtracted. The stage is `PlayerTurn` whenever `end_turn` runs its hooks, and `PlayingCard` for every hook that fires during a card (the `OwnerPlaysCard` and `CardPlayed` hooks, `card_resolved`, a random hit's chance event). A replayed copy is counted when it starts, so during the copy the condition reads "cards before this copy", like a real play. Add a doc line on `Condition::CardsPlayedThisTurnBelow` (hooks.rs:99): fewer than n cards were played this turn before the card in play; outside a card, fewer than n cards this turn. Amend the rule at decisions.md:311 the same way. Don't drop the `- 1` everywhere: FTL would change, and the golden games with it.

**Test first.** In `engine/tests/packs.rs`:

```rust
const C4_PACK: &str = r#"<the pack above>"#;

#[test]
fn cards_played_below_counts_every_card_outside_a_card() {
    load_pack(C4_PACK).unwrap();
    let defend = CardId::from_name("Defend").unwrap();
    let deck = ["gen:c4_few_card", "Defend", "Defend"];
    let card = bind(&deck).unwrap().0[0];
    // (Defends played, Strength after the turn end): 3 cards is not "fewer than 3"; 2 cards is.
    for (defends, strength) in [(2usize, 0i16), (1, 1)] {
        let hand: Vec<usize> = (0..=defends).collect();
        let mut s = bound_combat(&deck, &hand);
        s.apply_action(Action::Play { card, target: None }).unwrap();
        for _ in 0..defends {
            s.apply_action(Action::Play { card: defend, target: None }).unwrap();
        }
        assert_eq!(s.cards_played_this_turn as usize, 1 + defends);
        s.step(Action::EndTurn, &mut Rng::new(7)).unwrap();
        assert_eq!(s.player.powers.get(Power::Strength), strength, "{} cards played", 1 + defends);
    }
}
```

On the current code the 3-card case gives Strength 1, so the test fails.

**Must stay unchanged.** FTL's row is evaluated only while FTL is in play (the stage is `PlayingCard`), so it reads exactly as before. These stay identical: `golden.txt`, `golden_proving.txt`, `codec_golden.txt`, `cards_conditional.rs` (`ftl_draws_only_while_fewer_than_3_or_4_cards_were_played_before_it`, `cards_played_this_turn_resets_at_turn_start`), series_check (the features encode the condition's name and n, not its value), the contract pins and H4. No pin changes.

### C5. CardInPlayTagged checks who holds the static, not who attacks

- **Severity:** medium · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED (review item v13; the verifier ran a throwaway test)
- **Where:** `engine/src/state.rs:1347-1362` in `static_holds` (the `CardInPlayTagged` arm at 1351-1353); related: `engine/src/state.rs:1367-1394` in `interpret_attack_damage` (it reads `DamageTaken` rows with `who = dst`, lines 1372 and 1374, and calls `static_holds(who, ..)` at 1382), `engine/src/state.rs:1408` in `interpret_block`, `engine/src/hooks.rs:127` (the doc), `engine/src/registry.rs:528-551` in `parse_static`.

**What goes wrong.** A static is a "while the power exists, change this number" row. It has a `modifies` (`DamageDealt`, `DamageTaken` or `BlockGained`), an add per stack or a multiply, and a condition. The condition `CardInPlayTagged(tag)` should hold when "the attack comes from a card in play carrying the tag" (hooks.rs:127; Accuracy makes Shivs deal more). `static_holds(owner, c)` checks

```rust
matches!(self.stage, Stage::PlayingCard { card, .. } if owner == Who::Player && self.binding.def(card).has_tag(t))
```

where `owner` is the power's holder. For a `DamageDealt` row the holder is the attacker, so Accuracy works. For a `DamageTaken` row the holder is the target, and two things go wrong:
- (a) A monster that holds the row never meets the condition, so the player's Shiv gets no bonus.
- (b) A player who holds the row meets the condition whenever a tagged card is in play, even when the hit comes from a monster's hook. A monster's after-card `Damage` hook runs in `card_resolved`, while the Shiv is still in play.

The loader accepts any `modifies` with any condition, and any side holding a generated power goes through `interpret_attack_damage` (state.rs:1319). Official content puts `CardInPlayTagged` only on Accuracy (a player's `DamageDealt` row), so official play never reaches this.

**Reproduce.** Pack (loads as written):

```json
{"version": 1,
 "powers": [
  {"id": "c5_mark", "statics": [{"modifies": "DamageTaken", "stage": "Add", "amount": 1, "condition": {"CardInPlayTagged": "Shiv"}}]},
  {"id": "c5_spikes", "hooks": [{"trigger": {"CardPlayed": {"by": "Opponent"}}, "condition": {"CardType": "Attack"}, "effects": [{"Damage": {"amount": 2, "target": "Opponent"}}]}]}
 ],
 "cards": [
  {"id": "c5_mark_foe", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "c5_mark", "amount": 2, "target": "Opponent"}}]},
  {"id": "c5_mark_me", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "c5_mark", "amount": 3, "target": "Me"}}]},
  {"id": "c5_spikes_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "c5_spikes", "amount": 1, "target": "Opponent"}}]}
 ]}
```

Use `bound_combat` from `engine/tests/packs.rs:67` (Ironclad 80/80 against a Jaw Worm at 100 HP with no block).

- **(a)** Deck `["gen:c5_mark_foe", "Shiv"]`, hand `&[0, 1]`. Play `gen:c5_mark_foe` on `Some(0)` (2 stacks on the monster), then `Shiv` on `Some(0)`.
  - Expected: 4 + 2 = 6 damage, so the monster ends at 94.
  - Actual: 4 damage (96).
- **(b)** Deck `["gen:c5_mark_me", "gen:c5_spikes_card", "Shiv"]`, hand `&[0, 1, 2]`. Play `gen:c5_mark_me` with target `None` (3 stacks on the player). Play `gen:c5_spikes_card` on `Some(0)`; it gives the monster an after-card hook that hits the player for 2 attack damage whenever an Attack is played (it doesn't fire for the Skill itself). Record `s.player.hp`, then play `Shiv` on `Some(0)`.
  - Expected: the monster's hook hits for 2.
  - Actual: 5, that is 2 plus 3, because a Shiv is in play.

**Fix.** Give `static_holds` the attacker: `pub fn static_holds(&self, owner: Who, src: Who, c: StaticCondition) -> bool`. Here `src` is whoever makes the attack; for block rows, whoever gains the block.
- `CardInPlayTagged(t)` becomes `src == Who::Player && matches!(self.stage, Stage::PlayingCard { card, .. } if self.binding.def(card).has_tag(t))`.
- `OwnerHpAtMostHalf` keeps reading `owner`.
- In `interpret_attack_damage` (1382), call `self.static_holds(who, src, st.condition)`. In `interpret_block` (1408), call `self.static_holds(Who::Player, Who::Player, st.condition)`.
- Rewrite the hooks.rs:127 doc: the attacker is the player and the card in play carries the tag (Accuracy: Shivs); on a `DamageTaken` row, hits the owner takes from such a card; on a `BlockGained` row, block gained while such a card is in play.

`static_holds` has no caller outside state.rs (engine, solvedb and py/ checked). Don't special-case `DamageTaken` inside `interpret_attack_damage`: the defect is the condition's rule.

One case stays open, and it is not part of this finding (see unresolved). A player's own hook hit while a tagged card is in play still counts as coming from the card, for example a pack `CardPlayed { by: Owner }` → `Damage` hook during a Shiv. Closing it needs the hit's origin (C2's `from_hook`) inside the damage computation. `attack` could call a private variant of `attack_damage` that takes it, so the public `attack_damage(src, dst, base)` that agent.rs, heuristic.rs and the tests call can stay as it is.

**Test first.** In `engine/tests/packs.rs`:

```rust
const C5_PACK: &str = r#"<the pack above>"#;

#[test]
fn card_in_play_tagged_reads_the_attacker() {
    load_pack(C5_PACK).unwrap();
    let shiv = CardId::from_name("Shiv").unwrap();
    // (a) 2 stacks on the monster: the player's Shiv deals 4 + 1 x 2.
    let deck = ["gen:c5_mark_foe", "Shiv"];
    let card = bind(&deck).unwrap().0[0];
    let mut s = bound_combat(&deck, &[0, 1]);
    s.apply_action(Action::Play { card, target: Some(0) }).unwrap();
    s.apply_action(Action::Play { card: shiv, target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 94);
    // (b) 3 stacks on the player: the monster's after-card hit (2) is not the Shiv's attack.
    let deck = ["gen:c5_mark_me", "gen:c5_spikes_card", "Shiv"];
    let ids = bind(&deck).unwrap().0;
    let mut s = bound_combat(&deck, &[0, 1, 2]);
    s.apply_action(Action::Play { card: ids[0], target: None }).unwrap();
    s.apply_action(Action::Play { card: ids[1], target: Some(0) }).unwrap();
    let hp = s.player.hp;
    s.apply_action(Action::Play { card: shiv, target: Some(0) }).unwrap();
    assert_eq!(hp - s.player.hp, 2);
}
```

On the current code it gives 96 and 5, so the test fails.

**Must stay unchanged.** For Accuracy (a `DamageDealt` row on the player) the holder is also the attacker, so every official number stays. These stay identical:
- `golden.txt` and `golden_proving.txt` (its `accuracy` set).
- `codec_golden.txt`.
- `statics.rs` (`statics_table_matches_fast_path`, `accuracy_adds_to_shivs_only`, `red_skull_adds_at_half_hp`) and `packs.rs::generated_static_and_replacement_apply`.
- series_check (static rows carry the condition's name, not its value: features.rs:306), the contract pins and H4.

No pin changes.

## Build step details

Run everything from the worktree root in Git Bash. Each step: write its test(s) first and see them fail (`cargo test --release -p sts-engine --test packs <test name>`), then make the fix.

- **Step 0: baselines, before any group C edit.**
  - These are the main file's step 0 baselines, recorded once before any edit of the spec; don't record them again here.
  - H4: `target/h4_head.txt` (`cargo run --release --example two_turn_phases 100 --check target/h4_head.txt`; `--check` writes, it doesn't compare). Step 5 compares against it.
  - series_check: `target/sc_head.npz`, dumped from this worktree's module built at HEAD, with the cards and nets the main file's "How to build and check" names. Not from the shared venv's `sts`: that is main's build, which lacks the branch's columns, and compare checks only the old file's columns.
- **Step 1: C1.** Copies are never replayed.
  - Files: `engine/src/state.rs` (`do_effect`'s `ReplayCard` arm, about 4 lines) and `engine/src/effects.rs` (`ReplayCard` doc).
  - Test: `engine/tests/packs.rs::a_replayed_copy_is_not_replayed_again`. Before the fix it fails with HP 0 and 18 cards (no hang).
  - Acceptance: `cargo test --release -p sts-engine --test packs --test decisions --test golden`. Expected: all pass, the new test included.
- **Step 2: C2.** A hook's hits fire no `OwnerAttacked` hooks.
  - Files (about 20 lines): `engine/src/state.rs` (a `from_hook` parameter on `do_effect` and its 4 calls at 699, 841, 876 and 983, on `deal` and on `attack`; `RolledAttack` passes `false`), `engine/src/chance.rs:140` (`random_hit` passes `false`), `engine/src/hooks.rs` (`OwnerAttacked` doc), `engine/src/effects.rs` (`Damage` doc), `docs/extending.md:74`.
  - Test: `engine/tests/packs.rs::a_hooks_hit_fires_no_owner_attacked_hooks`. Keep the Weak and no-death asserts after the two plain ones: on the old code the first assert fails `(0, true)` before the cases that would overflow the stack.
  - Acceptance: `cargo test --release -p sts-engine --test packs --test replacements --test act1_bosses --test golden`. Expected: all pass.
- **Step 3: C3, plus the stale-card re-read found while checking it.**
  - Files (about 15 lines): `engine/src/effects.rs` (`scaled`: arms for `ScaledDamage`, `AddCard` (clamped and saturating) and `GrowDamage`, plus the doc), `engine/src/hooks.rs` (`after_card` takes `ScaledDamage`), `engine/src/state.rs` (`run` reads the card in play again right after `card_resolved`, before `finish_card`).
  - Tests: `engine/tests/packs.rs::hook_amounts_scale_with_stacks`, `a_monsters_scaled_damage_hook_fires_after_the_card` and `a_card_grown_by_a_late_hook_keeps_its_growth` (add `use sts_engine::effects::{Amount, Effect, PileKind, Quantity, Target};`).
  - Acceptance: `cargo test --release -p sts-engine --test packs --test decisions --test overrides --test act1_bosses --test hooks --test golden`. Expected: all pass. (The features change is checked once in Step 5.)
- **Step 4: C4 and C5.**
  - Files (about 20 lines): `engine/src/state.rs` (`condition_holds` subtracts only while a card is in play; `static_holds` takes `src`, with the calls in `interpret_attack_damage` and `interpret_block` updated) and `engine/src/hooks.rs` (doc lines on `CardsPlayedThisTurnBelow` and `CardInPlayTagged`).
  - Tests: `engine/tests/packs.rs::cards_played_below_counts_every_card_outside_a_card` and `card_in_play_tagged_reads_the_attacker`.
  - Acceptance: `cargo test --release -p sts-engine --test packs --test cards_conditional --test statics --test golden`. Expected: all pass.
- **Step 5: group check.**
  - `cargo test --release` (engine and solvedb, full fuzz included). Expected: all pass.
  - `cargo run --release --example two_turn_phases 100 --check target/h4_after.txt`, then `cmp target/h4_head.txt target/h4_after.txt`. Expected: no output (the files are identical).
  - `bash scripts/dev_sts.sh` (builds this branch's module into `target/pyroot`; never touches the shared venv).
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe scripts/series_check.py dump target/sc_new.npz --cards "Body Slam,Heavy Blade,Perfected Strike,Whirlwind" models/value_effects.contract.pt models/value_ids.contract.pt models/value_reference.contract.pt` (the baseline's cards and nets; check the printed module path is under `target/pyroot`), then `../../../.venv/Scripts/python.exe scripts/series_check.py compare target/sc_head.npz target/sc_new.npz`. Expected: a line starting `PASS:` (3 nets). If it fails, the cause is C3's `scaled` arms (the only feature-side change).
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe py/tests/test_content_pack.py` (expected last line `9 passed`) and `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe py/tests/test_sts.py` (checks the `golden_rows.npz` pin; expected last line `N passed`, 22 tests today, no traceback).
  - Docs: add one docs/decisions.md entry (in the style of "Cross-spec review of the series branch") listing: a replayed copy is never replayed again (C1); a hook's hits are reactions that fire no `OwnerAttacked` hooks (C2); hook `AddCard`, `ScaledDamage` and `GrowDamage` scale with stacks and a monster's `ScaledDamage` after-card hook fires after the card, and a card grown by a hook in `card_resolved` keeps its growth (C3); `CardsPlayedThisTurnBelow` counts every card played this turn outside a card (C4, and amend decisions.md:311); `CardInPlayTagged` reads the attacker (C5); and the open items (C5's own-hook case, the no-death `OwnerLostHp` self-damage loop). Check `docs/extending.md:74` was updated in Step 2.
  - Commit only once all of the above pass.

## Pins for this group

None of the recorded pins may change; each stays byte-identical:
- engine/tests/data/golden.txt, all 9,000 games. Its sha256 prefix is the registry's rules version, 7042d1d6a6149ba0 (scripts/registry.py rules_version(); checked at HEAD).
- engine/tests/data/golden_proving.txt, all 7 proving sets (whirlwind, accuracy, wraith with Caltrops' Thorns, survivor with Burst, hologram, headbutt, rampage).
- engine/tests/data/codec_golden.txt.
- solvedb's content-table pin, 0x5a922915c8ae26dd (solvedb/tests/fingerprint.rs:58). No card, power, monster or move is added.
- series_check: the heuristic and every old feature column on the fixed state set.
- Python pins: scripts/tests/data/contract/pins.json and the tiny nets, py/tests/data/golden_rows.npz, scripts/tests/data/lookahead_off_names.json and lookahead_rows.npz, TRAIN_PIN (scripts/tests/test_net.py), GAMES_PIN and ARRAYS_PIN (scripts/tests/test_content_selfplay.py), scripts/tests/data/curriculum_pins.json.
- The H4 two_turn_phases --check output.

Two things are expected to change:
- The rules fingerprint, solvedb::fingerprint(). Code edits in state.rs, effects.rs, hooks.rs and chance.rs move it (it strips comments, so doc-only edits don't). No test pins its value, and the branch already changes it, which retires the solved DB at landing as planned.
- On purpose (C3): the feature rows of pack hooks that hold AddCard, ScaledDamage or GrowDamage now scale with stacks. No pin, test pack or data/ pack contains such a hook.

## Decisions for this group

None. Every group C fix changes engine rules for content packs only, and each is a few lines to revert. No recorded data, net or pack in data/ uses the changed behaviour: no pack in data/ holds ReplayCard, OwnerAttacked, AddCard, ScaledDamage, GrowDamage, CardsPlayedThisTurnBelow or CardInPlayTagged (gen_powers_pack.json's hooks use only OwnerTurnStart, OwnerTurnEnd, CardPlayed by Owner and OwnerLostHp triggers, Always or CardType conditions, and no statics). Its 28 player Damage hooks are touched by C2 only in that their hits skip the monsters' OwnerAttacked scan, and no monster ever holds an OwnerAttacked power, so recorded games replay the same. Two rule choices follow the game, so they need no ruling: a replayed copy is never replayed again (C1), and a hook's hits are Thorns-type reactions that fire no OwnerAttacked hooks (C2). The manager confirms the fix spec as usual.

## Notes the checker left

1. C5's open case is not fixed here. A player's own hook hit made while a tagged card is in play still counts as coming from that card, for example a pack CardPlayed { by: Owner } -> Damage hook firing during a Shiv. That hit gets Accuracy's bonus, or a monster's CardInPlayTagged DamageTaken bonus. It is reachable with data/bench/gen_powers_pack.json, which has 3 CardPlayed-by-Owner Damage hooks, together with Accuracy (a Silent card). Nobody checked whether recorded generated-content games ever pair them; if they do, a fix changes those games. Suggested fix after C2: `attack` passes `from_hook` to a private damage helper, and CardInPlayTagged also requires that the hit is not a hook's. The public `attack_damage(src, dst, base)` keeps its signature. This needs its own verified finding and test.
2. A no-death OwnerLostHp self-damage loop is not covered. `take_damage` (state.rs:1486-1492) computes `lost` before the HP floor, so it reports HP lost even at the no-death floor. An OwnerLostHp hook that damages its own owner then recurses once per HP point and never stops in no-death mode; it is about 16k levels deep even before the floor. Computing `lost` after the floor, as `lose_hp` does, plays the same for official content but doesn't bound the depth by itself. A real fix needs a rule, for example that a hook's hit doesn't fire its own power's OwnerLostHp hooks. That is the manager's call. Only hand-written packs reach it: the generator can't emit such a hook, but the loader accepts one.
3. Optional cleanup, not required: Effect::scaled's existing Draw arm (`n * k as u8`) has the same wrap and overflow risk for negative or large stacks in the features that the new AddCard arm avoids. Clamping it the same way changes nothing for official content.
4. Optional hardening, not required: `cards_played_this_turn += 1` (state.rs:604 and 716) can still overflow a u8 in a debug build if one play gets about 250 replays, for example a monster's OwnerAttacked -> ReplayCard hook hit by a pack attack with 250 hits. `saturating_add` costs nothing and changes no official play.
5. Earlier series_check runs on this branch compared four contract nets, but the repo doesn't record which four. The steps pass the three contract nets under `models/` that the main file's step 0 baseline holds; the fourth stays unknown.
