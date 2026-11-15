//! Using a potion in a fight (docs/specs/potions.md, step 3): the action,
//! its legality, the potion-use stage and what a use is not (a card play).

use sts_engine::potions::PotionId;
use sts_engine::registry::{load_pack, potions_named, relics_named, Binding};
use sts_engine::*;

/// Test potions (this binary's own names). Fire Potion is the game's THORNS
/// damage; Block Potion's block is raw; Elixir exhausts any number of cards
/// in hand; Regen applies a pack power that heals at turn end.
const PACK: &str = r#"{"version": 2, "powers": [
{"id": "PuRegen", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{"Heal": 1}]}]}
], "potions": [
{"id": "pu-fire", "rarity": "common", "potency": 20, "effects": [{"PlainDamage": {"amount": 20, "target": "Opponent"}}]},
{"id": "pu-block", "rarity": "common", "potency": 12, "effects": [{"Block": 12}]},
{"id": "pu-elixir", "rarity": "uncommon", "effects": [{"Pick": {"kind": "ExhaustFromHand", "n": 10, "exact": false}}]},
{"id": "pu-regen", "rarity": "uncommon", "potency": 5, "effects": [{"Apply": {"power": "PuRegen", "amount": 5, "target": "Me"}}]},
{"id": "pu-heal", "rarity": "common", "potency": 5, "effects": [{"Heal": 5}]},
{"id": "pu-kill", "rarity": "common", "potency": 999, "effects": [{"PlainDamage": {"amount": 999, "target": "Opponent"}}]},
{"id": "pu-hits", "rarity": "common", "potency": 3, "effects": [{"RandomDamage": {"amount": 1, "hits": 3}}]},
{"id": "pu-swift", "rarity": "common", "potency": 3, "effects": [{"Draw": 3}]}
], "relics": [
{"id": "pu-count", "rarity": "common", "hooks": [{"trigger": "OwnerPlaysCard", "condition": "Always", "effects": [{"AddCounter": 1}]}]}
]}"#;

fn load() {
    load_pack(PACK).unwrap();
}

fn fight_vs(e: Encounter, relics: &[&str], potions: &[&str]) -> CombatState {
    load();
    let relics = relics_named(relics).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 30, 80, e, &relics, &mut Rng::new(3));
    s.give_potions(&potions_named(potions).unwrap()).unwrap();
    s
}

fn fight(potions: &[&str]) -> CombatState {
    fight_vs(Encounter::JawWorm, &[], potions)
}

fn uses(s: &CombatState) -> Vec<Action> {
    s.legal_actions().into_iter().filter(|a| matches!(a, Action::UsePotion { .. })).collect()
}

fn held(s: &CombatState) -> Vec<&'static str> {
    s.player.potions.iter().map(PotionId::name).collect()
}

#[test]
fn potion_actions() {
    // Fire Potion against two monsters: one action per living target.
    let s = fight_vs(Encounter::TwoLouse, &[], &["gen:pu-fire"]);
    assert_eq!(s.living_slots().count(), 2);
    assert_eq!(uses(&s), [Action::UsePotion { slot: 0, target: Some(0) }, Action::UsePotion { slot: 0, target: Some(1) }]);
    // Two copies give the same two (the first slot's).
    let two = fight_vs(Encounter::TwoLouse, &[], &["gen:pu-fire", "gen:pu-fire"]);
    assert_eq!(uses(&two), uses(&s));
    assert!(!two.is_legal(Action::UsePotion { slot: 1, target: Some(0) }), "a copy's own slot is not offered");
    // Untargeted: one action; a slot per distinct potion, in held order.
    let s = fight(&["gen:pu-swift", "gen:pu-block", "gen:pu-fire"]);
    assert_eq!(held(&s), ["gen:pu-block", "gen:pu-fire", "gen:pu-swift"]);
    assert_eq!(
        uses(&s),
        [Action::UsePotion { slot: 0, target: None }, Action::UsePotion { slot: 1, target: Some(0) }, Action::UsePotion { slot: 2, target: None }]
    );
    // After the card plays, before EndTurn.
    let all = s.legal_actions();
    let first = all.iter().position(|a| matches!(a, Action::UsePotion { .. })).unwrap();
    assert!(all[..first].iter().all(|a| matches!(a, Action::Play { .. })));
    assert!(all[first..all.len() - 1].iter().all(|a| matches!(a, Action::UsePotion { .. })));
    assert_eq!(*all.last().unwrap(), Action::EndTurn);
    // Wrong targets aren't legal.
    assert!(!s.is_legal(Action::UsePotion { slot: 0, target: Some(0) }));
    assert!(!s.is_legal(Action::UsePotion { slot: 1, target: None }));
    assert!(!s.is_legal(Action::UsePotion { slot: 3, target: None }));
    // Legal at 0 energy.
    let mut z = s.clone();
    z.player.energy = 0;
    assert!(z.legal_actions().iter().all(|a| !matches!(a, Action::Play { .. })));
    assert_eq!(uses(&z), uses(&s));
    // Without potions, the actions are as before.
    let mut bare = s.clone();
    bare.player.potions = Default::default();
    assert!(uses(&bare).is_empty());
    // A use takes the potion out; the turn goes on.
    let mut u = s.clone();
    u.step(Action::UsePotion { slot: 1, target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert_eq!(held(&u), ["gen:pu-block", "gen:pu-swift"]);
    assert_eq!(u.stage, Stage::PlayerTurn);
    assert_eq!(u.monsters[0].hp, s.monsters[0].hp - 20, "THORNS damage: 20, no block on the worm yet");
    // None during a pick (Elixir open).
    let mut p = fight(&["gen:pu-elixir", "gen:pu-block"]);
    assert_eq!(held(&p), ["gen:pu-block", "gen:pu-elixir"]);
    p.step(Action::UsePotion { slot: 1, target: None }, &mut Rng::new(1)).unwrap();
    assert!(p.pick().is_some());
    assert!(uses(&p).is_empty());
    assert!(!p.is_legal(Action::UsePotion { slot: 0, target: None }));
}

#[test]
fn potion_not_a_card() {
    // Block Potion with Dexterity 2 and Frail: raw 12.
    let mut s = fight_vs(Encounter::JawWorm, &["gen:pu-count"], &["gen:pu-block"]);
    s.player.powers.add(Power::Dexterity, 2);
    s.player.powers.add(Power::Frail, 2);
    s.monsters[0].powers.add(Power::Enrage, 2);
    let before = s.clone();
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!(s.player.block, before.player.block + 12);
    // Nothing a card play does: no energy, no hand change, no count, no
    // OwnerPlaysCard (the relic's counter) or monster CardPlayed hook
    // (Enrage's Strength), no pile.
    assert_eq!(s.player.energy, before.player.energy);
    assert_eq!(s.hand, before.hand);
    assert_eq!((s.discard(), s.exhaust(), s.draw()), (before.discard(), before.exhaust(), before.draw()));
    assert_eq!(s.cards_played_this_turn, before.cards_played_this_turn);
    assert_eq!(s.player.relics.counter(0), before.player.relics.counter(0));
    assert_eq!(s.monsters[0].powers.get(Power::Strength), before.monsters[0].powers.get(Power::Strength));
    // The relic does count a card play (the hook is live).
    let a = s.legal_actions().into_iter().find(|a| matches!(a, Action::Play { .. })).unwrap();
    s.step(a, &mut Rng::new(1)).unwrap();
    assert_eq!(s.player.relics.counter(0), before.player.relics.counter(0) + 1);
}

#[test]
fn potion_pick() {
    let mut s = fight(&["gen:pu-elixir"]);
    let hand = s.hand;
    let n_hand = hand.len();
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    assert!(s.player.potions.is_empty(), "the potion leaves the list first");
    let p = s.pick().expect("Elixir pauses at its pick");
    assert!(!p.exact);
    let acts = s.legal_actions();
    assert_eq!(*acts.last().unwrap(), Action::Done);
    assert!(acts[..acts.len() - 1].iter().all(|a| matches!(a, Action::Choose(_))));
    // Choose two cards, then stop.
    let Action::Choose(c) = acts[0] else { unreachable!() };
    s.step(Action::Choose(c), &mut Rng::new(1)).unwrap();
    let Action::Choose(d) = s.legal_actions()[0] else { panic!("still picking") };
    s.step(Action::Choose(d), &mut Rng::new(1)).unwrap();
    assert!(s.pick().is_some());
    s.step(Action::Done, &mut Rng::new(1)).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!(s.hand.len(), n_hand - 2);
    assert_eq!(s.exhaust().len(), 2);
    assert_eq!(s.cards_played_this_turn, 0);
    // An empty hand: the pick takes nothing and the use ends at once.
    let mut e = fight(&["gen:pu-elixir"]);
    e.hand = Default::default();
    e.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!((e.stage, e.pick()), (Stage::PlayerTurn, None));
}

#[test]
fn potion_ends_fight() {
    let mut s = fight(&["gen:pu-kill"]);
    s.step(Action::UsePotion { slot: 0, target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert_eq!(s.stage, Stage::Over { won: true });
    assert!(s.won());
    assert!(s.legal_actions().is_empty());
    assert_eq!((s.hand, s.discard()), (fight(&[]).hand, fight(&[]).discard()), "no card bookkeeping");
}

#[test]
fn potion_random_hits() {
    // Random hits step through chance events, as a card's.
    let s = fight_vs(Encounter::TwoLouse, &[], &["gen:pu-hits"]);
    let hp: i16 = s.monsters.iter().map(|m| m.hp).sum();
    assert!(s.monsters.iter().all(|m| m.block == 0));
    let mut u = s.clone();
    u.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(7)).unwrap();
    assert_eq!(u.stage, Stage::PlayerTurn);
    let after: i16 = u.monsters.iter().map(|m| m.hp).sum();
    // Curl Up's block waits for the use to finish, as for a card.
    assert_eq!(hp - after, 3, "three hits of 1");
    assert!(u.deferred_block.iter().all(|&b| b == 0), "flushed when the use ends");
    // A draw potion draws through the chance event.
    let mut d = fight(&["gen:pu-swift"]);
    let n = d.hand.len();
    d.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(7)).unwrap();
    assert_eq!(d.hand.len(), n + 3);
}

#[test]
fn codec_potion_use() {
    // Paused mid-use at Elixir's pick: round-trips.
    let mut s = fight(&["gen:pu-elixir", "gen:pu-fire"]);
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    assert!(s.pick().is_some());
    let bytes = codec::encode(&s);
    assert_eq!(codec::decode(&bytes), s);
    let Action::Choose(c) = s.legal_actions()[0] else { unreachable!() };
    s.step(Action::Choose(c), &mut Rng::new(1)).unwrap();
    assert_eq!(codec::decode(&codec::encode(&s)), s);
    // A random hit pending mid-use round-trips.
    let mut h = fight_vs(Encounter::TwoLouse, &[], &["gen:pu-hits"]);
    h.apply_action(Action::UsePotion { slot: 0, target: None }).unwrap();
    assert!(h.pending.is_some());
    assert_eq!(codec::decode(&codec::encode(&h)), h);
    // Action tag 4: slot and target.
    for a in [Action::UsePotion { slot: 0, target: None }, Action::UsePotion { slot: 4, target: Some(2) }] {
        let mut out = Vec::new();
        codec::encode_action(a, &mut out);
        assert_eq!(out[0], 4);
        let mut at = 0;
        assert_eq!(codec::decode_action(&out, &mut at), Some(a));
        assert_eq!(at, out.len());
    }
    // Potion-free actions keep their bytes.
    let mut out = Vec::new();
    codec::encode_action(Action::EndTurn, &mut out);
    codec::encode_action(Action::Done, &mut out);
    assert_eq!(out, [0, 3]);
}

#[test]
fn potion_heal_lifts_the_bound() {
    let bare = fight(&[]);
    assert!(!bare.can_heal(), "the starter deck has no heal");
    for p in ["gen:pu-regen", "gen:pu-heal"] {
        let s = fight(&[p]);
        assert!(s.can_heal(), "{p} held");
    }
    assert!(!fight(&["gen:pu-fire", "gen:pu-block"]).can_heal());
    // Used, the heal is spent (the regen power on the player still heals).
    let mut s = fight(&["gen:pu-heal"]);
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!(s.player.hp, 35);
    assert!(!s.can_heal());
}
