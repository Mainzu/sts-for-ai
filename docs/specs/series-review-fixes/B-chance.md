# Series review fixes, group B: chance and turn order

Status: confirmed (2026-11-02, B1 and B2 are in the generator-hardening bundle, unbuilt; B3 is in the backlog; decisions 'Series review fixes: the cut').

Part of `docs/specs/series-review-fixes.md`. Read that file first: it has the why, what must
stay true, the decisions, the build order and how to build and check. This file holds the
group's entries, then its build step details, the pins it may change, its decisions and the
notes its checker left. Line numbers are at `d9327a2`.

## Findings

### B1. A draw that a hook or a turn-end effect asks for is lost, made late, or crashes

- **Severity:** high · **Reach:** content packs, including the generated packs the training configs load · **New on this branch:** partly (mechanisms 1-5 below exist on main through hooks packs could already write; the branch adds `turn_end` draws, the `OwnerAttacked`/`RoundEnd` routes and the known-top drop, case 3) · **Review:** CONFIRMED (the verifier ran the turn-start, Whirlwind, monster and `turn_end` cases in debug and release; the stranded draw, the known-top drop and the draw on play were traced against HEAD's code while checking this spec but not run, so their tests come first)
- **Where:** `engine/src/chance.rs:147` `request_draw` (the overwrite at 156 and 162; the known-top replacement at 155; `top_draw_states` clears `pending` at 235); `engine/src/state.rs:961` `run_hooks_with`; `state.rs:766-771` (`run`, the `TurnStarted` stage); `state.rs:703-730` (`run`, a finished card: `card_resolved` at 704, then `finish_card` at 707); `state.rs:833` `end_turn` (the player's `OwnerTurnEnd` hooks at 834, the cards' `turn_end` effects 837-847, the hand discard 848-857, `debug_assert!` at 882); `state.rs:1034-1037` `do_effect` (`Effect::Draw`, `debug_assert_eq!` at 1035); `engine/src/registry.rs:674` `parse_hook` (its effect check at 706), `716-718` `runs_outside_a_card`, `734` `parse_card` (its `turn_end` check at 746-748); `engine/src/rng.rs:43` (`Rng::below`); `engine/src/heuristic.rs:278-279`.

**What goes wrong.** A chance event is a random event with more than one possible result (a draw from a mixed pile, a monster's move roll). The state holds no RNG: when the rules reach one, they set `pending` and stop until a caller resolves it (`resolve_chance` samples it; `chance_outcomes` lists the results for search). Only `run()` stops for it: its loop is `while self.pending.is_none()`, checked between a card's effects and between stages. Code that does several things in a row never looks at `pending`: `run_hooks_with` (every hook of one trigger, every effect of a hook; a hook is a power's rule that runs effects when its trigger fires), `end_turn` (the player's turn-end hooks, the cards' `turn_end` effects, the hand discard, then the monsters' turn-start hooks, moves and turn-end hooks, and the round-end hooks) and `card_resolved` (the hooks that run after a card's effects). A `Draw` in any of them calls `request_draw`. If the draw's result is certain (one kind of card, the whole pile, or known cards on top), it draws at once; if not, it sets `pending` and the draw waits until the rules next stop. Five things follow.

1. **Lost or stranded draws.** `request_draw` never looks at `pending`. A second request in the same pass either overwrites the waiting one (`None => self.pending = Some(ChanceEvent::Draw { n: n as u8 }),`, lines 156 and 162), so the first draw is lost, or, if its own result is certain, draws at once while the first keeps waiting with a count that no longer fits. When that certain draw emptied the draw and discard piles, `resolve_chance` reshuffles an empty discard pile and calls `rng.below(0)`, whose `u64::MAX % n` (rng.rs:43) panics in both profiles (division by zero is always checked), and `chance_outcomes` lists no outcome at all. With a known top (spec 7: cards the player knows are on top of the draw pile, e.g. after Headbutt), a certain second request takes line 155, `Some(mut v) => *self = v.pop().expect("one outcome").1,`, which replaces the whole state with a copy whose `pending` was cleared (`top_draw_states`, line 235): the first draw is dropped.
2. **Turn-end draws land in the wrong hand.** A pack card's `turn_end` effects and the player's `OwnerTurnEnd` hooks run before the hand is discarded (state.rs:834-857). A certain draw puts the card in the hand and it is discarded with it; an uncertain one waits until `end_turn` hands over to `run()` after the monsters' turn, so the card lands in the next hand. The rule depends on what the pile holds (verifier, release: next hand 5 with a one-kind pile, 6 with a mixed one; debug panics first, see 3).
3. **Debug panic after a monster's move.** A draw a hook asks for during a monster's move (the player's `OwnerAttacked` hook, which fires on every hit even when block absorbs it, or an `OwnerLostHp` hook from `Attack`) is still waiting after the move, and `debug_assert!(self.pending.is_none(), "monster moves must not wait on chance");` (state.rs:882) fires. In release the wait itself is harmless (the hand is already discarded, so the card goes to the next hand either way), but each later hit's request overwrites it (1): against The Guardian's Whirlwind (4 hits) the player gets 1 card instead of 4.
4. **A monster's Draw.** A pack power applied to a monster (`Apply` with `"target": "Opponent"`) runs its hooks with the monster as the actor. `Effect::Draw` then meets `debug_assert_eq!(actor, Who::Player);` (state.rs:1035): debug panics, release calls `request_draw`, which draws for the player. Nothing says which is meant.
5. **After-card draws can draw the card just played.** When a card's effects are done, `run` calls `card_resolved` (the player's `OwnerLostHp`-from-`Card` and `CardPlayed`-by-`Owner` hooks, then the monsters' after-card hooks) and then `finish_card`, which puts the card into its pile, with no check of `pending` between them (state.rs:704-707). A certain draw from those hooks happens before the card reaches the discard pile, an uncertain one after it. So when that draw has to reshuffle the discard pile (the draw pile holds fewer cards than it draws), the uncertain draw can bring back the card just played and the certain one can't. (Found while re-reading the code for this spec, not in the review's evidence; its test shows it before you change anything.)

Official content reaches none of this: Brutality, the only official `Draw` hook, asks once, at turn start, after the turn's own draw has resolved, and Burn's `turn_end` only deals damage. Generated content does. `scripts/gen_content.py` writes `Draw` only under `OwnerTurnStart` and `CardPlayed:Owner` (`allowed()`). In `data/bench/gen_powers_pack.json` the 5 `OwnerTurnStart` Draw powers are all in the train split (the pair is an official train pair) and the 7 `CardPlayed:Owner` Draw powers are all in the test split (the pair hashes to test). `selfplay.content_deck` adds 1-2 generated power cards to half the decks (`content_share` 0.5). So the `lean-gen*` configs (train split) reach mechanism 1: Brutality (in `TRAIN_POOL`) plus one turn-start Draw power, or two such powers, lose a draw. The `lean-oracle*` configs (`content_split: "test"`, the bench pack) and test-split evaluation reach mechanism 1 (two `CardPlayed:Owner` Draw powers) and mechanism 5. Already on main: 1 without the known top, and 2 to 5 through packs' `OwnerTurnEnd`, `OwnerLostHp` and `CardPlayed` hooks and `Apply` to an opponent. Added by the branch: `turn_end` on pack cards (spec 10 stage 1, commit 1a51035; main's `bind` gave generated cards `turn_end: &[]`), packs' `OwnerAttacked` and `RoundEnd` triggers (same commit), and the known-top path at chance.rs:155 (spec 7).

**Reproduce.** Every case uses one pack, loaded with `registry::load_pack`; put it in `engine/tests/packs.rs` as a raw-string constant `B1_PACK` (the parser in registry.rs accepts every entry as written):

```json
{"version": 1,
 "powers": [
  {"id": "b1_turn_one", "hooks": [{"trigger": "OwnerTurnStart", "effects": [{"Draw": 1}]}]},
  {"id": "b1_turn_two", "hooks": [{"trigger": "OwnerTurnStart", "effects": [{"Draw": 2}]}]},
  {"id": "b1_play_two", "hooks": [{"trigger": {"CardPlayed": {"by": "Owner"}}, "effects": [{"Draw": 2}]}]},
  {"id": "b1_play_one", "hooks": [{"trigger": {"CardPlayed": {"by": "Owner"}}, "effects": [{"Draw": 1}]}]},
  {"id": "b1_hit", "hooks": [{"trigger": "OwnerAttacked", "effects": [{"Draw": 1}]}]},
  {"id": "b1_foe", "hooks": [{"trigger": "OwnerTurnStart", "effects": [{"Draw": 1}]}]}
 ],
 "cards": [
  {"id": "b1_turn_one_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "b1_turn_one", "amount": 1, "target": "Me"}}]},
  {"id": "b1_turn_two_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "b1_turn_two", "amount": 1, "target": "Me"}}]},
  {"id": "b1_play_two_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "b1_play_two", "amount": 1, "target": "Me"}}]},
  {"id": "b1_play_one_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "b1_play_one", "amount": 1, "target": "Me"}}]},
  {"id": "b1_hit_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "b1_hit", "amount": 1, "target": "Me"}}]},
  {"id": "b1_foe_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "b1_foe", "amount": 1, "target": "Opponent"}}]}
 ]}
```

`bound_combat(deck, hand)` (packs.rs) binds `deck` (`registry::bind`: the binding is the per-combat table that maps reserved card and power slots to generated content; power slots fill in deck order, and hooks run in slot order, official powers first), starts a combat vs a Jaw Worm at 100 HP (player 80 HP), puts the listed deck positions in hand, empties the draw and discard piles and sets 3 energy. Play the cost-0 power cards with `Action::Play { card, target: None }` (`b1_foe_card` targets: `target: Some(0)`). Test mechanics: `packs.rs` has no `mod common`, so name cards with `CardId::from_name("Strike").unwrap()` and end the turn with `s.step(Action::EndTurn, &mut Rng::new(7)).unwrap()`; call `load_pack(B1_PACK).unwrap()` at the top of each test (loading the same pack again is a no-op); set the draw and discard piles after playing the power cards, because a power card's own play already fires the `CardPlayed` hooks (with the empty piles of `bound_combat` they draw nothing). "Mixed" means a draw pile of 6 Strikes and 6 Defends; "EndTurn" means `s.step(Action::EndTurn, &mut Rng::new(7))`.

1. *Two turn-start draws.* Deck and hand: `gen:b1_turn_one_card`, `gen:b1_turn_two_card`; play both; mixed draw pile; EndTurn. The turn's 5 leave 7 cards of both kinds, so Draw 1 waits and Draw 2 overwrites it. Expected hand 8 (5 + 1 + 2); actual 7.
2. *Stranded draw.* Deck and hand: `gen:b1_turn_one_card`, `gen:b1_turn_two_card`, Strike, Defend; play the two power cards; draw pile 5 Bash. EndTurn discards Strike and Defend; the turn's draw takes the 5 Bash (certain); then Draw 1 (Strike or Defend) waits and Draw 2 takes both at once. Expected hand 7 (5 Bash, 1 Strike, 1 Defend); actual: panic "attempt to calculate the remainder with a divisor of zero" in `Rng::below` when the stranded Draw 1 is sampled.
3. *Known top.* Deck and hand: `gen:b1_play_two_card`, `gen:b1_play_one_card`, Headbutt; play the two power cards; draw pile Strike, Defend; discard pile Bash; play Headbutt on slot 0, then `Action::Choose(Bash)` (Bash is now known on top). Headbutt's after-card hooks ask for 2 (Bash, then Strike or Defend: waits) and then 1 (Bash: certain, replaces the state). Expected: `pending` None, hand Bash, Strike, Defend; actual: hand Bash only.
4. *Hits during a monster's move.* Bind `gen:b1_hit_card` and start `CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::TheGuardian, &mut Rng::new(1))`: with a one-card deck the opening hand is that card and energy is 3. Play it; mixed draw pile; `s.monsters[0].set_move(sts_engine::monsters::guardian::WHIRLWIND)` (4 hits of 5); EndTurn. Expected hand 9 (4 + 5); release 6; debug panics at state.rs:882.
5. *A monster's draw.* Deck and hand: `gen:b1_foe_card`; play it on slot 0 (`target: Some(0)`); mixed draw pile; EndTurn. Release: hand 6 (the Jaw Worm's turn-start Draw draws for the player, then the turn's 5), which is the behaviour this fix keeps; debug panics at state.rs:1035. (The verifier used an `OwnerTurnEnd` hook; this case uses `OwnerTurnStart` because part 5 of the fix refuses `OwnerTurnEnd` draws.)
6. *Draw on play.* Deck and hand: `gen:b1_play_one_card`, Bash; play the power card; draw pile empty, discard pile Strike, Defend; play Bash on slot 0 with `apply_action` (no sampling), so the draw waits (`pending == Some(ChanceEvent::Draw { n: 1 })`). `s.chance_outcomes(16)`: expected 2 outcomes (Strike or Defend in hand, Bash in the discard pile in both); actual 3, one with Bash back in hand (p = 1/3).
7. *Turn-end draws.* `load_pack` accepts a card `{"id": "bad4", "cost": 0, "type": "Status", "unplayable": true, "turn_end": [{"Draw": 1}]}` and a power `{"id": "bad5", "hooks": [{"trigger": "OwnerTurnEnd", "effects": [{"Draw": 1}]}]}` (each as its own `{"version": 1, ...}` pack); such a card held at EndTurn behaves as in mechanism 2.

**Fix.** Five parts.
1. `request_draw` (chance.rs:147): before anything else, fold a waiting draw into this one. The rest of the function stays as it is, so the cap by hand space and cards left, the known-top path and `draw_outcomes` all see the sum:
```rust
// A draw still waiting (asked for where the rules don't stop: a hook
// pass, a monster's move) and this one are one draw of both counts.
let n = match self.pending {
    Some(ChanceEvent::Draw { n: k }) => {
        self.pending = None;
        n.saturating_add(k)
    }
    _ => n,
};
debug_assert!(self.pending.is_none(), "a draw asked for while {:?} waits", self.pending);
```
   This is exact: with nothing between them, drawing n and then m deals the same cards as drawing n + m. Without a known top, `draw_outcomes` takes a uniform set of the draw pile and reshuffles the discard pile only once the draw pile runs out, at the same point either way. With a known top, `top_draw_states` and `resolve_chance` draw card by card from the top, so n then m is the same sequence as n + m. The second draw's cap (hand space and cards left after the first) is `min(n + m, space, cards)` either way. Only `request_draw` sets a Draw event, and a monster roll or random hit is never pending while code runs (`run` stops on them at once; random hits are refused in hooks), so a draw is the only event there is to fold. If the summed count caps to 0 (the hand filled meanwhile), the function returns with the waiting draw dropped, which is right. Replace the doc comment with: "Draws `n` (capped by hand space and cards left), together with a draw still waiting from earlier in the same pass (a hook pass, a monster's turn): the two are one draw of both counts. Pauses only when the result is uncertain."
2. state.rs:882: let a waiting draw through:
```rust
// A hook's draw during the move (the player's OwnerAttacked) is made when
// end_turn hands over to run, before the monsters roll.
debug_assert!(matches!(self.pending, None | Some(ChanceEvent::Draw { .. })), "monster moves wait on no chance but a draw");
```
3. state.rs:1034-1037: `Effect::Draw(n) => self.request_draw(n),` with the comment "the player draws, whoever runs it (as with `GainEnergy` and `AddCard`): a monster's Draw hook from a pack draws for the player". Release behaviour doesn't change. Alternative: a monster's Draw does nothing (`if actor == Who::Player`); no need, and it would change release behaviour.
4. `run`, a finished card (state.rs:703-730): run the after-card hooks once, then let the loop stop for their draw before `finish_card`. `hit` is 0 whenever a card reaches its end (every step to the next effect resets it, and `Choose`/`Done` keep the 0 the pick arm set), so split the `None` arm on it:
```rust
// Past the last effect: the after-card hooks run once (`hit` 1 marks
// them done), and a draw they ask for is made before the card goes to
// its pile, as a certain draw is.
None if hit == 0 => {
    self.stage = Stage::PlayingCard { card, target, next, hit: 1, x, more };
    if self.card_resolved(card, target) {
        return;
    }
}
None => {
    // today's body from `self.finish_card(card, more.copy);` on
    // (lines 707-729), unchanged
}
```
   The loop matches the stage again after the hooks, so the second arm reads `card` and `more` as the hooks left them: a replay a hook asked for (`more.replays`) and a card a hook grew (`grow_damage` rewrites the stage's card) are both seen. The second point is E1's fix for this arm (E1: the stale card id read before the hooks). C1, E1 and E2 also edit this arm: whichever lands second applies its change to the arm as it then stands and keeps the re-read. Add to `Stage::PlayingCard`'s doc that past the last effect `hit` is 1 once the after-card hooks have run (a draw they asked for may then be waiting). No codec change (`hit` is already written in tags 1, 7 and 8); nothing else reads `hit` (the golden dump prints it, but official content never stops here: no official after-card hook draws). What changes, for packs only: a state waiting on such a draw is at `Stage::PlayingCard` instead of `Stage::PlayerTurn`, so the heuristic no longer reads it as "the monsters have acted" (heuristic.rs:278-279 gave it block 0 and full energy, which was wrong), and the features show the card in the in-play pile until the draw is made. Alternative: a `resolved` flag in `InPlay` (codec tag 8 would have to carry it).
5. Loader (registry.rs): refuse `Draw` where the hand is discarded before an uncertain draw could be made. In `parse_card`, right after the `turn_end` check at 746-748: `if turn_end.iter().any(|e| matches!(e, Effect::Draw(_))) { return Err("Draw can't run at turn end: the hand is discarded before an uncertain draw is made".into()); }`. In `parse_hook`'s effect loop (after the `runs_outside_a_card` check at 706; `trigger` is already in scope): `if trigger == Trigger::OwnerTurnEnd && matches!(e, Effect::Draw(_)) { return Err("Draw can't run in an OwnerTurnEnd hook: the hand is discarded before an uncertain draw is made".into()); }` (a monster-held one would be harmless, but the loader can't know who will hold a power). `gen_content.py` never writes these (`allowed()` keeps Draw to `OwnerTurnStart` and `CardPlayed:Owner`); no committed pack (`data/**/*.json`) and no official card or power has one (official `turn_end`: Burn, Burn+, which deal damage). Extend `runs_outside_a_card`'s doc comment: Draw runs outside a card too, but not at the player's turn end (see `parse_card`, `parse_hook`). The D-group fixes edit the same parser functions; add these checks to the functions as they then stand. Alternative: give `end_turn` a stop between the player's turn-end part and the hand discard (a new `Stage`); it keeps the atom and also covers leftover (c) below, but touches the codec, the golden dump and every `match` on `Stage`.

Do not: fold only when both requests are uncertain (cases 2 and 3 come from a certain second request); make hook draws always wait, even certain ones (Brutality's certain draws would become chance events: Brutality is in `deck_cards()`, the pool H4's decks draw from, and in `TRAIN_POOL`, so H4 searches and training games holding Brutality would change; no golden deck holds it); sample inside `request_draw` (the state holds no RNG, and search needs the outcomes listed).

Leave as is, and say so in the decisions entry (all packs only):
- (a) A waiting draw is made after the rest of its pass, so later effects in the same pass change what it draws: `AddCard` to `Hand` can make it take the hand past 10 (`HAND_LIMIT`), since its count was capped when asked; `AddCard` to `Draw` or `Discard` adds cards it may draw (in the game the draw comes first). `gen_content.py` writes no `AddCard`. Optional hardening: cap again where the draw is made (`resolve_chance`'s Draw arm and both Draw arms of `chance_outcomes`).
- (b) A draw asked for during the monsters' turn is made at its end, so a reshuffle in it can include status cards (Slimed, Dazed, Burn) that a later monster move put into the discard pile.
- (c) Part 5 refuses only the direct routes. A `Draw` in a hook that the player's turn-end effects set off still lands in the hand about to be discarded when certain, and in the next hand when uncertain: an `OwnerLostHp` hook fired by a held Burn's damage, Combust's HP loss or a pack `OwnerTurnEnd` hook's `LoseHp`/`PlainDamage`/`Damage` to the player; an `OwnerAttacked` hook fired by such a `Damage`; a monster-held `OwnerLostHp`/`OwnerDied` Draw hook fired by Combust's damage. `gen_content.py` never puts Draw under those triggers. The complete fix is the `end_turn` stop named as part 5's alternative.

**Test first.** In `engine/tests/packs.rs`, after `const B1_PACK` (add a helper `fn mixed() -> Pile` that returns 6 Strikes and 6 Defends):
- `turn_start_draws_add_up`: case 1; `assert_eq!(s.hand.len(), 8)` (today 7).
- `a_certain_draw_never_strands_a_pending_one`: case 2; asserts the hand equals 5 Bash, 1 Strike, 1 Defend (today: panic in `Rng::below`).
- `known_top_draws_in_one_hook_pass_add_up`: case 3; after `s.apply_action(Action::Choose(bash))`, asserts `s.pending == None` and `s.hand == Pile::from_cards(&[bash, strike, defend])` (today Bash only).
- `each_hit_on_the_player_draws`: case 4; `assert_eq!(s.hand.len(), 9)` (today 6 in release; panic at state.rs:882 in debug).
- `a_monsters_draw_hook_draws_for_the_player`: case 5; `assert_eq!(s.hand.len(), 6)`. Release passes today; run it in a debug build to see it fail (panic at state.rs:1035): `cargo test -p sts-engine --test packs a_monsters_draw_hook_draws_for_the_player`. After the fix it needs parts 2 and 3 both to pass in debug.
- `a_draw_on_play_is_made_before_the_card_reaches_its_pile`: case 6; asserts `s.pending == Some(ChanceEvent::Draw { n: 1 })`, then `let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!() };`, `v.len() == 2`, and for every outcome `t.hand.count(bash) == 0`, `t.discard.count(bash) == 1`, `t.hand.len() == 1` (today 3 outcomes).
- `packs_refuse_what_play_cant_run`: add case 7's two packs as rows `("a draw at turn end", ...)` and `("a draw in a turn-end hook", ...)` (today both load).
- `the_bench_pack_still_loads`: `load_pack(&std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/../data/bench/gen_powers_pack.json")).unwrap()).unwrap();`, so the refusals never reject what the generator writes (passes today; the pack also carries extra keys such as `keys`, `lifetime`, `split`, so the test guards the D-group parser changes too).

**Must stay unchanged.** golden.txt (9,000 seeded games; its hash is the registry's rules version), every set in golden_proving.txt, codec_golden.txt, the contract pins, series_check and H4 (`two_turn_phases 100 --check`): byte-identical, since official content never asks for a second draw in one pass and never draws after a card, at turn end or from a monster (the split arm of part 4 runs the same steps in the same order for every official card). Existing tests keep passing, in particular `cards_powers.rs::brutality_loses_1_hp_and_draws_1_at_turn_start_after_the_draw`, `packs.rs::every_official_card_round_trips` and `every_official_power_round_trips` (no official `turn_end` or `OwnerTurnEnd` draw), `known_top.rs`, `chance.rs` and `decisions.rs`. Games with generated packs change on purpose (see the owner decision on datasets); `scripts/gen_content.py`'s pricing (`gain`) is unaffected (a power card's own play draws from empty piles there, and no monster turn is played).

### B2. A split or Close Up set during or after the monster's own move is overwritten by the end-of-turn roll

- **Severity:** medium · **Reach:** content packs, including the generated packs training loads; proving content (Caltrops) · **New on this branch:** no (already on main through generated `OwnerLostHp` hooks; the branch adds the Thorns/Caltrops route and packs' `OwnerAttacked` and `RoundEnd` hooks, none of which exist on main) · **Review:** CONFIRMED (the verifier ran it at HEAD and compared main's code)
- **Where:** `engine/src/state.rs:906` in `end_turn` (`self.stage = Stage::MonsterRolls { next: 0 };`, unconditional); `state.rs:732-742` in `run` (`Stage::MonsterRolls`; `if self.monsters[slot].alive() { self.request_monster_move(slot); }` at 738-740); `state.rs:1513-1560` `lost_hp` (`m.set_move(guardian::CLOSE_UP);` at 1543; `if split != NO_MOVE && m.intent() != split && 2 * m.hp <= m.max_hp { m.set_move(split); }` at 1557-1558); `engine/src/monsters.rs:448-449` (Slime Boss pattern) and `516-524` (Guardian pattern); `engine/src/agent.rs:65-75` `intent_known`; `engine/src/heuristic.rs:288` (reads a split intent as splitting); `docs/decisions.md:1909-1912`.

**What goes wrong.** A monster's intent is the move it uses next (`moves[0]`; `moves[1]` is the one before; `set_move(x)` makes them `[x, old moves[0]]`). `lost_hp` makes some monsters react to losing HP: a large slime or the Slime Boss at half HP or less switches its intent to its split move, and The Guardian, once Mode Shift runs out, switches to Close Up and gains 20 block. When the HP is lost on the player's turn or at the monsters' turn start (poison), the monster then uses the reaction as its move. But `end_turn` lets every monster move and then always enters `Stage::MonsterRolls { next: 0 }`, where `run` rolls a new move for every living monster from its pattern (rows read on the move history, `monsters.rs`). If the HP was lost during or after the monster's own move (Thorns hitting back during its attack; a player's hook that damages every enemy when the player loses HP; round-end damage), `lost_hp` has already put the reaction into `moves[0]`, and the roll overwrites it: no pattern row keeps a split, and The Guardian's row `LastMove(CLOSE_UP) -> ROLL_ATTACK` reads Close Up as already used. The game keeps the reaction: the reaction's SetMoveAction is queued after the move's own move-setting action (from the decompiled source as the verifier remembers it, not re-checked; decisions.md:1909 says "probably").

The verifier's runs (debug): the Slime Boss at 72/140 Slams, Thorns 3 takes it to 69, `lost_hp` sets SPLIT, and the roll makes moves [GOOP_SPRAY, SPLIT]: it Goop Sprays (+3 Slimed) instead of splitting, and with Thorns as its only HP loss it never splits (12 more turns, HP 57). The Guardian reaching Mode Shift during its Whirlwind keeps the 20 block but gets moves [ROLL_ATTACK, CLOSE_UP]: no Close Up, no Sharp Hide 3, and it attacks a turn early. Acid and Spike Slime (L) crossing half HP during their own attack make a normal move instead of splitting.

decisions.md:1909-1912 says only proving content (Caltrops) causes it; that is wrong. `scripts/gen_content.py` makes `OwnerLostHp:Attack/Any -> PlainDamage/Damage AllOpponents` powers (16 in `data/bench/gen_powers_pack.json`, 12 of them train split, e.g. `gp1_012`: 3 damage to every enemy whenever the player loses HP to an attack, wearing down by 1 each time), the gen_powers bench sets put such cards into slime fights (gen_powers.json: 8 slime_boss and 24 large_slime fights; gen_powers12.json: 24 and 72), and main's `end_turn`, `lost_hp` and MonsterRolls are the same code. Packs can also apply Thorns or write `OwnerAttacked`/`RoundEnd` hooks (branch).

**Reproduce.** (Thorns, Caltrops' power, stands in for every route.)
1. `doing(K::SlimeBoss, 140, [slime_boss::SLAM, slime_boss::PREPARING])` (monsters_act1.rs helper; player at 500 HP), `s.monsters[0].hp = 72`, `s.player.powers.add(Power::Thorns, 3)`, `end_turn(&mut s)` (tests/common). Expected: boss HP 69, intent SPLIT; a second `end_turn` splits it into Spike Slime (L) in slot 0 and Acid Slime (L) in slot 1, both at 69 HP. Actual: intent GOOP_SPRAY.
2. `guardian_fight(&[])` (act1_bosses.rs helper: The Guardian at 240 HP, player at 900), `s.monsters[0].set_move(guardian::WHIRLWIND)`, Mode Shift set to 3 (`s.monsters[0].powers.clear(Power::ModeShift)`, then `.add(Power::ModeShift, 3)`), Thorns 3 on the player, `end_turn`. Expected: HP 237, Mode Shift 0, block 11 (20 minus three Thorns hits that block absorbs), intent CLOSE_UP; a second `end_turn` gives Sharp Hide 3 and intent ROLL_ATTACK. Actual: intent ROLL_ATTACK after the first, and Sharp Hide stays 0.
3. Generated route: a pack `B2_PACK` = `{"version": 1, "powers": [{"id": "b2_retort", "hooks": [{"trigger": {"OwnerLostHp": {"from": "Attack"}}, "effects": [{"PlainDamage": {"amount": 3, "target": "AllOpponents"}}]}]}], "cards": [{"id": "b2_retort_card", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "b2_retort", "amount": 1, "target": "Me"}}]}]}`; bind `gen:b2_retort_card`, start `CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::SlimeBoss, &mut Rng::new(1))` (the one-card deck leaves the card in hand at 3 energy, piles empty); play it; boss HP 72, `s.monsters[0].moves = [slime_boss::SLAM, slime_boss::PREPARING]`; `s.step(Action::EndTurn, &mut Rng::new(7))` (Slam takes the player to 45, the hook takes the boss to 69). Expected and actual as in 1.

**Fix.** Skip the roll for a monster whose reaction is still to come. In state.rs, next to `lost_hp` (`MonsterKind`, `guardian`, `NO_MOVE` and `Power` are already imported):
```rust
/// Whether the monster in `slot` still has to use the move `lost_hp` set
/// for it: a slime's split (using it replaces the slime) or The Guardian's
/// Close Up (using it gives Sharp Hide). At the end-of-turn roll this means
/// it lost the HP after its own move (Thorns, a hook during a monster's
/// move or at round end); the roll keeps the move, as the game runs the
/// reaction's SetMoveAction after the move's own.
pub fn reaction_pending(&self, slot: usize) -> bool {
    let m = &self.monsters[slot];
    let split = m.def().split_move;
    (split != NO_MOVE && m.intent() == split)
        || (m.kind == MonsterKind::TheGuardian && m.intent() == guardian::CLOSE_UP && m.powers.get(Power::SharpHide) == 0)
}
```
In `run`'s MonsterRolls arm (state.rs:738): `if self.monsters[slot].alive() && !self.reaction_pending(slot) { self.request_monster_move(slot); }`. In `agent::intent_known` (agent.rs:71-72), count a kept reaction as known in both MonsterRolls arms: `slot < k as usize || s.reaction_pending(slot)` and `slot < next as usize || s.reaction_pending(slot)`, and add to its doc that a reaction kept through the roll is known. Then the heuristic and the lookahead features don't roll a kept split forward while an earlier slot's roll (or a waiting draw, B1) is pending. `reaction_pending` is safe on any slot (an empty slot's kind `None` has `split_move` NO_MOVE).

Why this is exact for official content: a slime that used its split was replaced by its children (who start with NO_MOVE), so a split intent at the roll was set after its move; a Guardian that used Close Up this turn holds Sharp Hide 3 from it (only Twin Slam clears it), while one whose Close Up came after its move holds none (offensive mode never has Sharp Hide). Skipping the roll leaves moves [reaction, move used]. The game's history would be [reaction, rolled], but nothing reads `moves[1]` after a split (the slime is gone) or after Close Up (its row reads only `LastMove(CLOSE_UP)`), and the slime and Guardian rows that the lookahead walks from [reaction, x] never depend on x. The heuristic already treats an intent equal to the split move as splitting (heuristic.rs:288). At combat start every intent is NO_MOVE, so the first rolls are unchanged.

Do not: add a `LastMove(SPLIT) -> SPLIT` pattern row (the heuristic's and the lookahead's move walks would change for every state whose intent is a split, moving series_check and H4, and a row can't tell The Guardian's two cases apart: its moves are [CLOSE_UP, x] in both); re-run `lost_hp`'s rule after the roll (that rolls first: an extra chance event per large slime whose results are thrown away, and a shifted RNG).

Left open (say so in decisions), packs only: Lagavulin's stun set after its own move (an asleep Lagavulin losing HP at round end through a pack hook) is still rolled over, because its state can't tell "stun set, not used" from "stun used"; a Guardian given Sharp Hide by a pack before its Mode Shift runs out after its move has its Close Up rolled over, and one whose Sharp Hide a pack takes to 0 after it used Close Up uses Close Up again. The general fix, if wanted later: `end_turn` records the move each monster used; a monster whose intent changed after it moved gets a bit in a new `CombatState` field that MonsterRolls reads and clears (written as codec trailer section 3 only when non-zero, and shown in `Debug` only when non-zero, so existing encodings and codec_golden.txt stay the same).

Docs: replace decisions.md:1909-1912 ("Known divergence (optional finding, not fixed): ... Only proving content (Caltrops) can cause it.") with: "Known divergence, fixed by the series review fixes (B2): a split or Close Up that `lost_hp` sets after the monster's own move is kept through the end-of-turn roll (`CombatState::reaction_pending`). The note's reach was wrong: generated `OwnerLostHp` damage-all powers (gen_content.py; 16 in data/bench/gen_powers_pack.json) reach it in training, as do packs' Thorns, `OwnerAttacked` and `RoundEnd` hooks. Still open (packs only): Lagavulin's stun set after its own move, and a Guardian whose Sharp Hide a pack changes." Keep the next sentence (lines 1913-1914, a monster killed mid-move).

**Test first.**
- `engine/tests/monsters_act1.rs::a_split_set_during_its_own_slam_survives_the_roll`: case 1; asserts `(hp, intent) == (69, slime_boss::SPLIT)` after the first `end_turn` (fails today: intent GOOP_SPRAY), then `(kind, hp)` of slots 0 and 1 are `(K::SpikeSlimeL, 69)` and `(K::AcidSlimeL, 69)` after the second.
- `engine/tests/act1_bosses.rs::close_up_set_during_its_own_whirlwind_survives_the_roll`: case 2; asserts `(hp, ModeShift, block, intent) == (237, 0, 11, guardian::CLOSE_UP)`, then `(SharpHide, intent) == (3, guardian::ROLL_ATTACK)` (fails today: intent ROLL_ATTACK at the first assert). `guardian` is already imported at line 92.
- `engine/tests/packs.rs::a_generated_retort_split_survives_the_roll`: case 3 with `const B2_PACK`; same asserts as case 1, with `MonsterKind::SpikeSlimeL` / `MonsterKind::AcidSlimeL` (fails today). Import `sts_engine::monsters::slime_boss`.
- `engine/tests/lookahead.rs::a_kept_reaction_counts_as_known_while_others_roll`: `vs(&[MonsterKind::JawWorm, MonsterKind::SlimeBoss], &[], None)` (Jaw Worm 40 HP, boss 140, player 80), Jaw Worm `moves = [CHOMP, NO_MOVE]` (its next roll is random), boss HP 72 and moves [SLAM, PREPARING], Thorns 3 on the player; `s.apply_action(Action::EndTurn).unwrap()` (no sampling) stops with `pending == Some(ChanceEvent::MonsterMove { slot: 0 })`; assert the boss's intent is SPLIT, `!intent_known(&s, 0)` (control: the Jaw Worm's roll is pending, true today and after) and `intent_known(&s, 1)` (fails today). Imports: `use sts_engine::monsters::{slime_boss, CHOMP, NO_MOVE};` (`intent_known` and `ChanceEvent` are already imported).

**Must stay unchanged.** golden.txt byte-identical: no golden deck has a source of monster HP loss after a monster's move (Thorns is Caltrops, proving content; poison ticks at the monsters' turn start, before any move; Combust is in no golden pool and acts at the player's turn end), and The Guardian isn't in `Encounter::ALL`, the golden encounters. golden_proving.txt: only `proving-wraith:silent:large_slime:*` and `proving-wraith:silent:slime_boss:*` may change (Caltrops; possibly none do); re-record and check that nothing else moved (medium slimes have no split, so `exordium_wildlife`, `small_slimes` and `lots_of_slimes` stay). codec_golden.txt, contract pins, series_check, H4: unchanged (no format change; their states hold no Thorns and no generated content; H4's boss fights are Slime Boss only, with `deck_cards()` decks). Existing tests keep passing: `act1_bosses.rs::guardian_defensive_mode_then_back_with_a_higher_threshold` (Close Up used, Sharp Hide 3, rolls Roll Attack), the split tests in monsters_act1.rs (`slime_boss_splits_into_spike_and_acid_large_with_its_hp`, `large_slime_splits_at_half_hp_into_two_mediums_with_its_hp`, `split_children_dont_act_on_the_turn_they_appear`), `patterns.rs`, `threshold.rs`, `lookahead.rs`, `chance.rs` (`paused_roll` resolves at `StartTurn`, not through MonsterRolls).

### B3. Past 8 cards shuffled under a known top, the extra card is never drawn before the known cards

- **Severity:** medium · **Reach:** content packs (official cards only through a contrived Headbutt line; Headbutt is proving content) · **New on this branch:** yes · **Review:** CONFIRMED (the verifier ran it)
- **Where:** `engine/src/state.rs:277-284` `Top::add_floater` (`if self.n_known == 0 || self.n_floaters as usize == TOP_FLOATERS { return; }`); `state.rs:205-356` (`Top`: `TOP_FLOATERS` 207, `floaters` 219-221, `floaters()` 239-241, `floaters_on_top` 244-255, `sort_floaters` 257-259, `push` 263-272, `pop_head` 288-303, `take_floater` 306-312, `map_cards` 315-323, `from_parts` 326-342, `within` 345-355); `state.rs:1049-1055` in `do_effect` (`AddCard` to `Draw`); `engine/src/chance.rs:169-178` `top_draw_choices` (`v.push(((self.draw.len() - f) as f64 / n, None));` at 177) and `chance.rs:331-343` (`resolve_chance`'s sampler); `engine/src/codec.rs:228-233` (today `w.byte(floaters.len() as u8)` at 229) and `437-440` (today `(0..r.byte()?)` at 439); `engine/tests/golden.rs:132` (the dump prints `floaters()` per copy); `docs/decisions.md:1989-1992`.

**What goes wrong.** The known top (spec 7) is what the player knows about the draw pile's order: `known` cards on top (Headbutt puts one there; the first is the head) and floaters, known cards shuffled in at an unknown place (Wild Strike's Wound), each with `above`, the number of known cards certainly above it. Every card in `top` is also counted in `draw`. While anything is known, the next card is a floater with `above` 0 with probability (its copies)/N, else the head (`top_draw_choices`; N = the draw pile's size): the game's exact odds as long as every shuffled-in card is a floater. The floater table has 8 entries, one per card, so 8 Wounds fill it. A 9th card still goes into `draw` (`self.draw.add(card, n)`, state.rs:1050), but `add_floater` drops it, so it becomes an untracked card, which the model treats as certainly below every known card: the head's share `self.draw.len() - f` includes it. With Bash known on top of 9 shuffled-in Wounds, the engine gives Bash first 0.2 (the game: 0.1) and Bash within 9 draws 1.0 (0.9); the sampler agrees (0.2004 over 20,000 samples). In general the head comes first with (N-8)/N instead of (N-k)/N for k > 8. Search and the solver use these odds.

decisions.md:1989-1992 calls the cap "unreachable with in-scope content". That was true when spec 7 was built; spec 10 stage 1 (1a51035) then put `AddCard` (any official card, `n` up to 255, to `Draw`) into packs, in card effects, hooks and `turn_end`, and the `DiscardToTop` pick into pack cards' effects (picks are refused in hooks and at turn end), and nothing checks against `TOP_FLOATERS`. `gen_content.py` writes neither `AddCard` nor `Pick`.

**Reproduce.** Official cards, no pack: `vs(&[K::JawWorm], &hand, Some(300))` with `hand` = `["Headbutt"]` plus 9 × `"Wild Strike"` (`vs` from tests/common; 10 cards, the hand limit), discard pile Bash, energy 10; play Headbutt on slot 0, `Action::Choose(Bash)` (Bash known on top), then Wild Strike 9 times on slot 0 (the Jaw Worm ends at 183 HP). Draw pile: Bash and 9 Wounds. `s.top.floaters().count()`: expected 9, actual 8. `draws(&s, 1)` (known_top.rs helper: the listed outcomes of drawing 1): expected Bash 0.1, Wound 0.9; actual 0.2, 0.8. Pack route: after Headbutt, one play of `{"id": "v28_shuffle9", "cost": 0, "type": "Skill", "effects": [{"AddCard": {"card": "Wound", "n": 9, "pile": "Draw"}}]}` does the same.

**Fix.** Count copies: a floater entry becomes (card, above, copies), one entry per distinct (card, above), so copies of one card share an entry and the 8 entries count distinct pairs. Copies with equal `above` are interchangeable, so a count loses nothing (`floaters_on_top` already adds them up).
- `Top::floaters: [(u8, u8, u8); TOP_FLOATERS]`, `n_floaters` = entries in use. Doc: (card, above, copies), one entry per distinct (card, above), sorted by (card, above), unused entries zero, so equal knowledge is equal state. `TOP_FLOATERS`'s doc: distinct (card, above) entries, each with a copy count. The derives (`Clone, Copy, Debug, Default, PartialEq, Eq, Hash`) stay.
- Replace `sort_floaters` with a private `normalize()`: sort entries by (card, above), merge equal pairs (add their copies), zero the tail, set `n_floaters`. Call it where `sort_floaters` is called now (`push`, `add_floater`, `pop_head`, `map_cards`, `from_parts`): `push` and `pop_head` can make two entries equal (`above` capped at `n_known`, or dropping to 0), and so can `map_cards` (Inferno turning Burn into Burn+, a variant renumbered). `push`, `pop_head` and `map_cards` otherwise stay as they are (they touch `f.1` and `x.0`).
- `add_floater(c)`: nothing known → return; an entry (c, 0) exists → one more copy (`saturating_add`: copies never exceed the draw pile's own u8 count); else a free entry → insert (c, 0, 1) and normalize; else (8 distinct pairs) keep today's rule: not tracked.
- `take_floater(c)`: the (c, 0) entry loses a copy; when its copies reach 0, remove the entry, keeping the order.
- `floaters()`: still one (card, above) per copy, in the same order (`flat_map` with `std::iter::repeat_n`): the codec and the golden dump read it, so their bytes stay the same.
- `floaters_on_top()`: the `above`-0 entries as (card, copies), in card order (entries are unique per pair and sorted, so this is today's order); `resolve_chance` walks this order, so keep it and proving-headbutt replays the same.
- `from_parts(known, floaters)`: takes the per-copy list the codec writes and merges equal pairs (`checked_add` on copies, `None` on overflow); `None` past 8 distinct pairs or for an `above` beyond `known.len()`, and still `None` for an empty or over-long `known`. It must no longer reject a list longer than 8.
- `within(draw)`: add each entry's copies, counting per card in `usize` (not with `Pile::add`, whose u8 count would overflow and panic in debug past 255; this function is the check, so it must return false, not panic).
- Codec: write and read the floater count as a varint: codec.rs:229 `w.byte(floaters.len() as u8)` becomes `w.u(floaters.len() as u64)`, and codec.rs:439 `(0..r.byte()?)` becomes `(0..r.u()?)` (a short input still fails on the first missing byte). Below 128 it is the same single byte as today, so every existing encoding is unchanged, and more than 255 copies can't wrap. `CODEC_VERSION` stays 1.

A sketch of the changed parts:
```rust
pub fn floaters(&self) -> impl Iterator<Item = (CardId, u8)> + '_ {
    self.floaters[..self.n_floaters as usize].iter().flat_map(|&(c, a, k)| std::iter::repeat_n((CardId(c), a), k as usize))
}
pub fn floaters_on_top(&self) -> Vec<(CardId, u8)> {
    self.floaters[..self.n_floaters as usize].iter().filter(|f| f.1 == 0).map(|&(c, _, k)| (CardId(c), k)).collect()
}
fn normalize(&mut self) {
    let n = self.n_floaters as usize;
    self.floaters[..n].sort_unstable_by_key(|&(c, a, _)| (c, a));
    let mut m = 0;
    for i in 0..n {
        let f = self.floaters[i];
        if m > 0 && (self.floaters[m - 1].0, self.floaters[m - 1].1) == (f.0, f.1) {
            self.floaters[m - 1].2 = self.floaters[m - 1].2.saturating_add(f.2);
        } else {
            self.floaters[m] = f;
            m += 1;
        }
    }
    self.floaters[m..].fill((0, 0, 0));
    self.n_floaters = m as u8;
}
pub fn add_floater(&mut self, c: CardId) {
    if self.n_known == 0 { return; }
    let n = self.n_floaters as usize;
    if let Some(f) = self.floaters[..n].iter_mut().find(|f| (f.0, f.1) == (c.0, 0)) {
        f.2 = f.2.saturating_add(1);
        return;
    }
    if n == TOP_FLOATERS { return; } // a 9th distinct pair: not tracked
    self.floaters[n] = (c.0, 0, 1);
    self.n_floaters += 1;
    self.normalize();
}
pub fn take_floater(&mut self, c: CardId) {
    let n = self.n_floaters as usize;
    let i = self.floaters[..n].iter().position(|f| (f.0, f.1) == (c.0, 0)).expect("a floater on top");
    self.floaters[i].2 -= 1;
    if self.floaters[i].2 == 0 {
        self.floaters.copy_within(i + 1..n, i);
        self.floaters[n - 1] = (0, 0, 0);
        self.n_floaters -= 1;
    }
}
pub fn from_parts(known: &[CardId], floaters: &[(CardId, u8)]) -> Option<Top> {
    if known.is_empty() || known.len() > TOP_KNOWN { return None; }
    let mut t = Top { n_known: known.len() as u8, ..Top::default() };
    for (i, c) in known.iter().enumerate() { t.known[i] = c.0; }
    for &(c, a) in floaters {
        if a as usize > known.len() { return None; }
        let n = t.n_floaters as usize;
        match t.floaters[..n].iter_mut().find(|f| (f.0, f.1) == (c.0, a)) {
            Some(f) => f.2 = f.2.checked_add(1)?,
            None if n == TOP_FLOATERS => return None,
            None => { t.floaters[n] = (c.0, a, 1); t.n_floaters += 1; }
        }
    }
    t.normalize();
    Some(t)
}
pub fn within(&self, draw: &Pile) -> bool {
    let mut need = [0usize; PILE_SLOTS];
    for c in self.known() { need[c.0 as usize] += 1; }
    for &(c, _, k) in &self.floaters[..self.n_floaters as usize] { need[c as usize] += k as usize; }
    need.iter().enumerate().all(|(i, &k)| k <= draw.count(CardId(i as u8)) as usize)
}
```

`CombatState` grows by 8 bytes (`Top` 34 → 42; `two_turn_phases` and `bench` print the size, but not into the H4 check file). Past 8 distinct pairs (9 different cards, or one card at 9 different depths, shuffled in under a known top: packs; official cards can't reach it in practice, since it would take 9 Wild Strikes interleaved with 8 Headbutts in one turn with the top still known) the extra card stays untracked, as today. Update decisions.md:1989-1992 ("Fixed-capacity inline arrays (known 16, floaters 8; ... unreachable with in-scope content).") to: "Fixed-capacity inline arrays (known 16; floaters 8 distinct (card, above) entries, each with a copy count). Past capacity the bottom known card is forgotten, and a card of a 9th distinct pair is not tracked: the model treats it as certainly below every known card, so the known head is drawn first more often than in the game. Reachable with packs (`AddCard` to `Draw`, spec 10 stage 1); official cards can't reach it in practice." Alternatives: also raise `TOP_FLOATERS` (+3 bytes per entry in every state); evict the entry with the largest `above` first (a smaller error).

Do not: dissolve the known top on overflow (the spec rejected that, rules-engine-upgrade.md:285-288, because it changes the game's odds, and it errs far more than one untracked card when untracked cards sit under the head); raise `TOP_FLOATERS` alone (each copy would still take an entry); change `floaters()` to yield counted entries without changing its readers (codec, golden dump).

**Test first.** In `engine/tests/known_top.rs`:
- `nine_shuffled_wounds_keep_the_games_odds`: the official line above; asserts `(s.draw.len(), s.top.floaters().count()) == (10, 9)`, `draws(&s, 1)` = `[(["Bash"], 0.1), (["Wound"], 0.9)]` (within 1e-12), and `codec::decode(&codec::encode(&s)) == s`. Optional: `draws(&s, 9)` holds Bash with 0.9 (today 1.0). Fails today on the floater count.
- `copies_of_a_floater_share_an_entry`: `use sts_engine::state::Top;` `let mut t = Top::from_parts(&[bash], &[]).unwrap();` (`from_parts` returns an `Option`), `add_floater(wound)` 9 times → `floaters_on_top() == vec![(wound, 9)]`; `push(strike)`, one more `add_floater(wound)` → `vec![(wound, 1)]`; `pop_head() == strike` → `vec![(wound, 10)]`; `t == Top::from_parts(&[bash], &[(wound, 0); 10]).unwrap()`. Fails today at the first assert ([(Wound, 8)]).

**Must stay unchanged.** golden.txt (no known top: Headbutt is proving content); golden_proving.txt, proving-headbutt included (its deck holds one Wild Strike, so its games stay far below 8 floaters, and `floaters()` and the sampling order are the same; a moved line is a bug in the change, not a re-record); codec_golden.txt (no known top: it holds no `top:` field); the codec bytes of every state with fewer than 128 floater copies; series_check (features read only `known()`, `n_known()` and `is_empty()`); H4 (no Headbutt in its decks); `known_top.rs`'s existing tests (`headbutt_puts_the_choice_on_top`, `floater_odds_match_the_game`, `sampled_draws_follow_the_same_odds`, `floaters_dissolve_when_known_runs_out`, `codec_round_trips_top`, `headbutt_with_empty_discard_skips_the_pick`, `inferno_upgrades_known_burns`); `decisions.rs::codec_round_trips_picks_and_replays`; the fuzz invariant `s.top.within(&s.draw)` (tests/common/mod.rs:74).

## Build step details

- **Step B-0 (no code; once, before the first edit of group B, or reuse the fix spec's baseline if one exists).** Record the search baseline at HEAD: `cargo run --release --example two_turn_phases 100 --check <scratch>/h4_before.txt` (any path outside the repository; takes minutes). Expected: "wrote <file>". The check file holds only search results (nodes, leaves, cuts, action, value bits), not the state size, so B3's size change can't move it.
- **Step B-1: B1 parts 1-3 (draws add up, the monster-move assert, a monster's Draw).** Files: `engine/src/chance.rs` (`request_draw` and its doc comment), `engine/src/state.rs` (assert at 882, `Effect::Draw` arm at 1034-1037). About 15 changed lines. Tests in `engine/tests/packs.rs`: `const B1_PACK`, helper `mixed()`, `turn_start_draws_add_up`, `a_certain_draw_never_strands_a_pending_one`, `known_top_draws_in_one_hook_pass_add_up`, `each_hit_on_the_player_draws`, `a_monsters_draw_hook_draws_for_the_player` (write them first and see them fail as the spec says). Acceptance: `cargo test --release -p sts-engine --test packs` → all pass; `cargo test -p sts-engine --test packs each_hit_on_the_player_draws` and `cargo test -p sts-engine --test packs a_monsters_draw_hook_draws_for_the_player` (debug build) → 1 passed each; `cargo test --release -p sts-engine --test golden --test cards_powers --test chance --test known_top` → all pass; `git diff --exit-code engine/tests/data` → exit 0.
- **Step B-2: B1 part 4 (an after-card hook's draw is made before the card reaches its pile).** File: `engine/src/state.rs` (`run`'s card-finished arm, lines 703-730; `Stage::PlayingCard` doc). About 12 changed lines. If C1, E1 or E2 already changed this arm, apply the split to the arm as it then stands and keep reading `card` and `more` from the stage after the hooks. Test: `packs.rs::a_draw_on_play_is_made_before_the_card_reaches_its_pile` (fails before the edit: 3 outcomes). Acceptance: `cargo test --release -p sts-engine --test packs --test decisions --test golden --test fuzz` → all pass; `git diff --exit-code engine/tests/data` → exit 0.
- **Step B-3: B1 part 5 (packs refuse Draw at turn end) and B1's decisions text.** Files: `engine/src/registry.rs` (`parse_card` after line 748, `parse_hook`'s effect loop after line 706, `runs_outside_a_card` doc), `docs/decisions.md` (the fix spec's entry for the series review fixes; create it at the end of the file if no earlier step did). Decisions text to add: "Draws asked for where the rules don't stop (a hook pass, a monster's move, the after-card hooks): a draw still waiting joins the next one in the same pass (`request_draw`), exact because nothing comes between them; the after-card hooks run once (`hit` 1 past the last effect) and their draw is made before the card goes to its pile; a monster's `Draw` draws for the player; packs refuse `Draw` in a card's `turn_end` and in `OwnerTurnEnd` hooks (the hand is discarded before an uncertain draw is made). Left as is (packs only): (a) a waiting draw is made after the rest of its pass, so later `AddCard`s in it change what it draws (to Hand: the hand can pass 10); (b) a draw asked for during the monsters' turn is made at its end, so its reshuffle can include status cards a later monster move discarded; (c) a Draw in a hook that the player's turn-end effects set off (`OwnerLostHp`, `OwnerAttacked`, `OwnerDied`, through Burn, Combust or a pack's `OwnerTurnEnd` effects) lands in the hand about to be discarded when certain and in the next hand when uncertain; the full fix is a stop in `end_turn` before the hand discard." About 10 code lines. Tests: two rows in `packs.rs::packs_refuse_what_play_cant_run`, new `packs.rs::the_bench_pack_still_loads`. Acceptance: `cargo test --release -p sts-engine --test packs --test registry` → all pass.
- **Step B-4: B2 (keep a reaction set after the monster's own move).** Files: `engine/src/state.rs` (`reaction_pending` next to `lost_hp`, MonsterRolls arm at 738), `engine/src/agent.rs` (`intent_known` lines 71-72 and its doc), `engine/tests/data/golden_proving.txt` (re-recorded), `docs/decisions.md` (lines 1909-1912). About 15 code lines. Tests: `monsters_act1.rs::a_split_set_during_its_own_slam_survives_the_roll`, `act1_bosses.rs::close_up_set_during_its_own_whirlwind_survives_the_roll`, `packs.rs::a_generated_retort_split_survives_the_roll` (with `const B2_PACK`), `lookahead.rs::a_kept_reaction_counts_as_known_while_others_roll`. Acceptance: `cargo test --release -p sts-engine --test monsters_act1 --test act1_bosses --test packs --test lookahead --test threshold --test patterns --test chance` → all pass; `GOLDEN_RECORD=1 cargo test --release -p sts-engine --test golden golden_trajectories`, then `git diff --exit-code engine/tests/data/golden.txt` → exit 0, and `git diff -U0 engine/tests/data/golden_proving.txt | grep -E '^[-+]proving' | grep -vE '^[-+]proving-wraith:silent:(large_slime|slime_boss):'` → no output (the allowed lines may also not change at all); then `cargo test --release -p sts-engine --test golden` → pass.
- **Step B-5: B3 (counted floater entries).** Files: `engine/src/state.rs` (`Top`: field, `TOP_FLOATERS` doc, `normalize` replacing `sort_floaters`, `floaters`, `floaters_on_top`, `add_floater`, `take_floater`, `from_parts`, `within`; `push`/`pop_head`/`map_cards` call `normalize`), `engine/src/codec.rs` (floater count as a varint, lines 229 and 439), `docs/decisions.md` (1989-1992). About 70 changed lines. Tests: `known_top.rs::nine_shuffled_wounds_keep_the_games_odds`, `known_top.rs::copies_of_a_floater_share_an_entry`. Acceptance: `cargo test --release -p sts-engine --test known_top --test codec --test decisions --test fuzz --test golden` → all pass; `git diff --exit-code engine/tests/data` → exit 0 (proving-headbutt must not move; if it does, the change has a bug).
- **Step B-6: group check (no code).** `cargo test --release` → every engine and solvedb test passes; `cargo test -p sts-engine --test packs` (debug build) → all pass (catches the new debug assertions); `cargo run --release --example two_turn_phases 100 --check <scratch>/h4_after.txt && cmp target/h4_head.txt <scratch>/h4_after.txt` (`target/h4_head.txt` is the main file's step 0 file) → no output (identical searches); `bash scripts/dev_sts.sh`, then series_check against the main file's step 0 baseline: `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe scripts/series_check.py dump <scratch>/new.npz` with that baseline's `--cards` and nets (the main file's "How to build and check"), then `../../../.venv/Scripts/python.exe scripts/series_check.py compare target/sc_head.npz <scratch>/new.npz` → PASS. Don't add Caltrops to `--cards` (B2 changes those games on purpose), and don't pass the tiny nets in `scripts/tests/data/contract`: they are pre-contract, and `stsnet.load` refuses them. Then `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe scripts/tests/test_gen_content.py` and the same for `scripts/tests/test_lookahead.py` and `scripts/tests/test_content_selfplay.py` → pass.

## Pins for this group

- **golden.txt:** byte-identical after every step (its hash is the registry's rules version).
- **golden_proving.txt:**
  - B2 may change only `proving-wraith:silent:large_slime:*` and `proving-wraith:silent:slime_boss:*` lines (possibly none). These are Caltrops games where Thorns takes a large slime or the Slime Boss to half HP during its own attack: the split is now kept.
  - Every other line stays byte-identical, including proving-headbutt (which B3 must not move) and every set under B1 (proving-survivor's Burst replays run through the split arm of B1 part 4 in the same order).
- **codec_golden.txt:** byte-identical. Codec bytes of every existing state are unchanged: B3 writes the floater count as a varint, which is the same single byte below 128. `CODEC_VERSION` stays 1.
- **Contract pins (scripts/tests/contract_pins.py and the pins re-recorded in 662b6c6), series_check (heuristic, contract nets, old feature columns), H4 (`two_turn_phases 100 --check`) and test_content_selfplay's GAMES_PIN/ARRAYS_PIN:** unchanged (official content only).
- **Rules fingerprint (solvedb/src/fingerprint.rs):** changes, because state.rs and chance.rs are edited (no test pins its value). This is expected: the branch already changed it. registry.rs, agent.rs and codec.rs are not fingerprinted.
- **Not pinned, but changing on purpose:**
  - Play with generated packs changes under B1 and B2 (see the owner decision on datasets).
  - For packs only, a state waiting on an after-card hook's draw sits at `Stage::PlayingCard` (hit 1) instead of `Stage::PlayerTurn`: its heuristic value (no longer "monsters acted") and its features (the card in the in-play pile) change.
  - The debug-only panics at state.rs:882 and 1035 are gone.
  - `CombatState` grows by 8 bytes (B3; printed by `two_turn_phases` and `bench`).

## Decisions for this group

**Generated-content datasets recorded before B1 and B2 may not replay the same.** B1 (lost draws, draws on play) and B2 (kept splits and Close Up) change how games with generated packs play; official-only play doesn't change, so golden.txt, whose hash is the only rules version `scripts/registry.py` checks, stays the same. 31 of the 215 datasets under the main checkout's `datasets/` carry a `content_hash` in their `manifest.json`. For them, `registry.find` will still reuse a dataset whose config, parent model and rules version match, and `registry.examples` rebuilds features by replaying games from seed and actions when no cache exists; `registry.replay` copies the recorded outcome instead of checking it. A game that hit one of these paths plays differently from that point on replay, and may meet an action that is no longer legal or silently give different states. Scores on the gen_powers* bench sets recorded before the fix are not comparable for the fights these paths reach. The same applies to any other group's fix that changes generated play.
Options: (a) land the fixes; make `registry.replay` compare the replayed final score, won and hp_end with the recorded `outcome` and raise on a mismatch, so a diverging game fails loudly; keep using existing feature caches; re-record a generated dataset only when a job needs to replay it. (b) Re-record all 31 now (machine time, the project's bottleneck). (c) Build spec 10 stage 2 first (versions that hash loaded packs, plus a generated-rules epoch), so the guard retires exactly these datasets.
Recommendation: (a), and note the landing commit in manager.md, so later runs know which generated datasets and bench scores predate it.

## Notes the checker left

Nothing blocks a builder. Three things remain uncertain. (1) The game-order claims behind B1 part 4 (a CardPlayed draw comes before the card reaches its pile) and B2 (the reaction's SetMoveAction runs after the move's own) come from memory of the decompiled source and were not re-checked. The project's own note agrees for B2. (2) B1 part 5 refuses only the direct turn-end Draw routes. The indirect route stays open and is documented as leave-as-is (c), packs only; closing it needs the end_turn stop (a new Stage). (3) If C1, E1 or E2 land before B1 part 4, the builder must merge part 4 into the arm as it then stands. Part 4's re-read of the stage after the hooks must be kept.
