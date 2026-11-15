//! The last four Ironclad cards (docs/specs/ironclad-last-four.md; game
//! facts in docs/research/ironclad-last-four-2026-11-14.md, read from the
//! jar's `cards/red/*` classes): Battle Trance (a `Draw` replacement that
//! cancels, the pack power No Draw), Reaper (`Quantity::HpDealt`, and a
//! card's heals still running after the hit that won the fight), Dual
//! Wield (a pick's type filter `of`, `PickKind::CopyInHand`) and
//! Juggernaut (`Trigger::OwnerGainedBlock`, a `PlainDamage` on
//! `Target::RandomOpponent` owed until the card in play has run).

use sts_engine::codec::{decode, encode};
use sts_engine::registry::{bind, load_pack, relics_named};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

fn id(name: &str) -> CardId {
    CardId::from_name(name).unwrap()
}

/// A combat with the cards `deck` (pack cards as `gen:` names) all in
/// hand, the relics `relics` (pack names), 10 energy, 50 of 80 HP, empty
/// piles, every monster at 100 HP with no block or powers.
fn setup(deck: &[&str], relics: &[&str], enc: Encounter) -> (CombatState, Vec<CardId>) {
    load_pack(PACK).unwrap();
    load_pack(RELICS).unwrap();
    let (ids, b) = bind(deck).unwrap();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, enc, &relics_named(&refs).unwrap(), &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 10;
    s.player.hp = 50;
    for m in s.monsters.iter_mut().filter(|m| m.alive()) {
        m.hp = 100;
        m.max_hp = 100;
        m.block = 0;
        m.powers = Default::default();
    }
    (s, ids)
}

fn play(s: &mut CombatState, card: CardId, seed: u64) {
    let target = if s.binding.def(card).targeted() { Some(0) } else { None };
    s.step(Action::Play { card, target }, &mut Rng::new(seed)).unwrap();
}

/// The pack powers' stacks on the player, summed (No Draw is the only one
/// these tests give).
fn gen_stacks(s: &CombatState) -> i16 {
    Power::GEN.iter().map(|&p| s.player.powers.get(p)).sum()
}

// ---- Battle Trance (`BattleTrance.use`: DrawCardAction(magicNumber), then
// ApplyPowerAction(NoDrawPower); `DrawCardAction.update` ends at once while
// the player has "No Draw", before the pile checks and the shuffle) ----

#[test]
fn battle_trance_loads_as_the_game() {
    load_pack(PACK).unwrap();
    for name in ["gen:Battle Trance", "gen:Battle Trance+"] {
        let (ids, b) = bind(&[name]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty, d.exhaust), (0, sts_engine::cards::CardType::Skill, false), "{name}");
    }
}

#[test]
fn battle_trance_draws_then_no_more_draws_this_turn() {
    for (name, n) in [("gen:Battle Trance", 3), ("gen:Battle Trance+", 4)] {
        for seed in 0..4 {
            let (mut s, ids) = setup(&[name, "Pommel Strike"], &[], Encounter::JawWorm);
            s.set_draw(Pile::from_cards(&[id("Defend"); 8]));
            play(&mut s, ids[0], seed);
            assert_eq!(s.hand.count(id("Defend")) as usize, n, "{name}: its own draw goes through");
            assert_eq!(gen_stacks(&s), 1, "{name}: No Draw held");
            play(&mut s, ids[1], seed);
            assert_eq!(s.hand.count(id("Defend")) as usize, n, "{name}: Pommel Strike draws nothing");
            assert_eq!(s.draw().len(), 8 - n);
            assert_eq!(s.monsters[0].hp, 100 - 9, "{name}: Pommel Strike still hits");
        }
    }
}

#[test]
fn battle_trance_own_draw_shuffles_but_not_later_ones() {
    let (mut s, ids) = setup(&["gen:Battle Trance", "Pommel Strike"], &[], Encounter::JawWorm);
    s.set_draw(Pile::from_cards(&[id("Defend")]));
    s.set_discard(Pile::from_cards(&[id("Strike"); 4]));
    play(&mut s, ids[0], 3);
    // One off the draw pile, then a shuffle and two more.
    assert_eq!((s.hand.count(id("Defend")), s.hand.count(id("Strike"))), (1, 2));
    assert_eq!((s.draw().len(), s.discard().len(), s.discard().count(ids[0])), (2, 1, 1), "Battle Trance alone in the discard");
    // Empty the draw pile into the discard: Pommel Strike's draw would
    // shuffle; under No Draw nothing moves.
    s.set_draw(Pile::default());
    s.set_discard(Pile::from_cards(&[id("Strike"); 2]));
    play(&mut s, ids[1], 3);
    assert_eq!((s.draw().len(), s.discard().len()), (0, 3), "no shuffle: Pommel Strike joins the discard");
}

#[test]
fn battle_trance_cancels_evolve_draws() {
    let (mut s, ids) = setup(&["gen:Evolve", "gen:Battle Trance"], &[], Encounter::JawWorm);
    play(&mut s, ids[0], 1);
    s.set_draw(Pile::from_cards(&[id("Dazed"); 6]));
    play(&mut s, ids[1], 1);
    // Three Dazed drawn; Evolve asks for three more after No Draw arrived.
    assert_eq!((s.hand.count(id("Dazed")), s.draw().len()), (3, 3));
    assert_eq!(s.stage, Stage::PlayerTurn);
}

#[test]
fn artifact_blocks_no_draw() {
    let (mut s, ids) = setup(&["gen:Battle Trance", "Pommel Strike"], &[], Encounter::JawWorm);
    s.player.powers.add(Power::Artifact, 1);
    s.set_draw(Pile::from_cards(&[id("Defend"); 8]));
    play(&mut s, ids[0], 1);
    assert_eq!((gen_stacks(&s), s.player.powers.get(Power::Artifact)), (0, 0));
    play(&mut s, ids[1], 1);
    assert_eq!(s.hand.count(id("Defend")), 4, "Pommel Strike draws");
}

#[test]
fn no_draw_ends_with_the_turn() {
    let (mut s, ids) = setup(&["gen:Battle Trance"], &[], Encounter::JawWorm);
    s.set_draw(Pile::from_cards(&[id("Defend"); 10]));
    play(&mut s, ids[0], 1);
    s.hand = Hand::default();
    s.step(Action::EndTurn, &mut Rng::new(2)).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((gen_stacks(&s), s.hand.len()), (0, 5), "next turn draws 5");
}

// ---- Reaper (`Reaper.use`: VampireDamageAllEnemiesAction; per monster
// `lastDamageTaken = min(damage after block, currentHealth)`, summed, then
// HealAction of the total if above 0, kept by clearPostCombatActions) ----

#[test]
fn reaper_loads_as_the_game() {
    load_pack(PACK).unwrap();
    for name in ["gen:Reaper", "gen:Reaper+"] {
        let (ids, b) = bind(&[name]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty, d.exhaust), (2, sts_engine::cards::CardType::Attack, true), "{name}");
    }
}

#[test]
fn reaper_heals_the_hp_it_took() {
    // 4 (5) at a slime with 3 block and one with 2 HP: 1 (2) + 2.
    for (name, dmg, heal) in [("gen:Reaper", 4, 3), ("gen:Reaper+", 5, 4)] {
        let (mut s, ids) = setup(&[name], &[], Encounter::SmallSlimes);
        s.monsters[0].block = 3;
        s.monsters[1].hp = 2;
        play(&mut s, ids[0], 1);
        assert_eq!((s.monsters[0].hp, s.monsters[1].hp), (100 - (dmg - 3), 0), "{name}");
        assert_eq!(s.player.hp, 50 + heal, "{name}");
        assert_eq!(s.exhaust().count(ids[0]), 1, "{name}: exhausts");
        assert_eq!(s.dealt, 0, "{name}: nothing kept once the card is done");
    }
}

#[test]
fn reaper_all_blocked_heals_nothing() {
    let (mut s, ids) = setup(&["gen:Reaper"], &[], Encounter::SmallSlimes);
    s.monsters[0].block = 10;
    s.monsters[1].block = 4;
    play(&mut s, ids[0], 1);
    assert_eq!(s.player.hp, 50);
}

#[test]
fn reaper_heals_after_killing_the_last_enemy() {
    let (mut s, ids) = setup(&["gen:Reaper"], &[], Encounter::JawWorm);
    s.monsters[0].hp = 3;
    play(&mut s, ids[0], 1);
    assert!(s.won());
    assert_eq!(s.player.hp, 50 + s.win_heal + 3, "Burning Blood's heal and Reaper's 3");
}

#[test]
fn magic_flower_scales_reapers_heal() {
    // 3 healed becomes round(4.5) = 5, also after the win.
    let (mut s, ids) = setup(&["gen:Reaper"], &["Magic Flower"], Encounter::SmallSlimes);
    s.monsters[0].block = 3;
    s.monsters[1].hp = 2;
    play(&mut s, ids[0], 1);
    assert_eq!(s.player.hp, 55);
    let (mut s, ids) = setup(&["gen:Reaper"], &["Magic Flower"], Encounter::JawWorm);
    s.monsters[0].hp = 3;
    play(&mut s, ids[0], 1);
    assert!(s.won());
    assert_eq!(s.player.hp, 50 + s.win_heal_scaled() + 5);
}

#[test]
fn a_thorns_reply_doesnt_change_reapers_count() {
    // Thorns answers each hit with its own damage on the player, run inside
    // Reaper's damage: the heal is still 4 + 4.
    let (mut s, ids) = setup(&["gen:Reaper"], &[], Encounter::SmallSlimes);
    s.monsters[0].powers.add(Power::Thorns, 3);
    play(&mut s, ids[0], 1);
    assert_eq!(s.player.hp, 50 - 3 + 8);
}

#[test]
fn dealt_round_trips_in_the_codec() {
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(3));
    let plain = encode(&s);
    s.dealt = 7;
    let bytes = encode(&s);
    assert_ne!(bytes, plain);
    assert_eq!(decode(&bytes), s);
    s.dealt = 0;
    assert_eq!(encode(&s), plain, "0 writes nothing");
}

// ---- Dual Wield (`DualWield.use`: DualWieldAction(magicNumber 1, +1);
// only ATTACK or POWER cards in hand count (`isDualWieldable`); one such
// card is copied without a screen; past 10 cards `MakeTempCardInHandAction`
// sends a copy to the discard pile) ----

fn pick_of(s: &CombatState) -> Vec<CardId> {
    s.legal_actions().into_iter().filter_map(|a| if let Action::Choose(c) = a { Some(c) } else { None }).collect()
}

#[test]
fn dual_wield_loads_as_the_game() {
    load_pack(PACK).unwrap();
    for name in ["gen:Dual Wield", "gen:Dual Wield+"] {
        let (ids, b) = bind(&[name]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty, d.exhaust, d.targeted()), (1, sts_engine::cards::CardType::Skill, false, false), "{name}");
    }
}

#[test]
fn dual_wield_picks_an_attack_or_a_power_and_copies_it() {
    for (name, copies) in [("gen:Dual Wield", 1), ("gen:Dual Wield+", 2)] {
        let (mut s, ids) = setup(&[name, "Bash", "Inflame", "Defend", "Defend"], &[], Encounter::JawWorm);
        play(&mut s, ids[0], 1);
        let mut can = pick_of(&s);
        can.sort();
        let mut want = vec![id("Bash"), id("Inflame")];
        want.sort();
        assert_eq!(can, want, "{name}: no Skill to pick");
        assert!(!s.legal_actions().contains(&Action::Done), "{name}: exactly one");
        s.step(Action::Choose(id("Inflame")), &mut Rng::new(1)).unwrap();
        assert_eq!(s.stage, Stage::PlayerTurn, "{name}");
        assert_eq!((s.hand.count(id("Inflame")), s.hand.count(id("Bash")), s.hand.count(id("Defend"))), (1 + copies, 1, 2), "{name}");
        assert_eq!((s.discard().len(), s.created), (1, copies as u16), "{name}: Dual Wield alone in the discard; copies are made cards");
    }
}

#[test]
fn dual_wield_copies_its_only_candidate_at_once() {
    // Two copies of one card: the game opens the screen, with one outcome.
    for (name, copies) in [("gen:Dual Wield", 1), ("gen:Dual Wield+", 2)] {
        let (mut s, ids) = setup(&[name, "Strike", "Strike", "Defend"], &[], Encounter::JawWorm);
        play(&mut s, ids[0], 1);
        assert_eq!(s.stage, Stage::PlayerTurn, "{name}: no pick");
        assert_eq!(s.hand.count(id("Strike")), 2 + copies, "{name}");
    }
}

#[test]
fn dual_wield_with_only_skills_does_nothing() {
    let (mut s, ids) = setup(&["gen:Dual Wield+", "Defend", "Shrug It Off"], &[], Encounter::JawWorm);
    play(&mut s, ids[0], 1);
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((s.hand.len(), s.created), (2, 0));
}

#[test]
fn dual_wield_past_a_full_hand_copies_go_to_the_discard_pile() {
    // Dual Wield+ with 9 other cards: one copy fits, one is discarded.
    let mut deck = vec!["gen:Dual Wield+", "Bash"];
    deck.extend(["Strike"; 8]);
    let (mut s, ids) = setup(&deck, &[], Encounter::JawWorm);
    play(&mut s, ids[0], 1);
    s.step(Action::Choose(id("Bash")), &mut Rng::new(1)).unwrap();
    assert_eq!((s.hand.len(), s.hand.count(id("Bash")), s.discard().count(id("Bash"))), (10, 2, 1));
}

#[test]
fn dual_wield_copies_keep_level_and_a_free_mark() {
    // An upgraded card's copies are upgraded; a card costing 0 this turn
    // (every copy marked) gives marked copies (`makeStatEquivalentCopy`
    // keeps `costForTurn`).
    let (mut s, ids) = setup(&["gen:Dual Wield", "Bash+", "Strike"], &[], Encounter::JawWorm);
    assert!(s.mark_free_in_hand(id("Bash+")));
    play(&mut s, ids[0], 1);
    s.step(Action::Choose(id("Bash+")), &mut Rng::new(1)).unwrap();
    assert_eq!((s.hand.count(id("Bash+")), s.free_in_hand.count(id("Bash+"))), (2, 2));
    assert_eq!(s.cost_of(id("Bash+")), 0);
    // Strike unmarked: its copy isn't either.
    let (mut s, ids) = setup(&["gen:Dual Wield", "Bash", "Strike"], &[], Encounter::JawWorm);
    play(&mut s, ids[0], 1);
    s.step(Action::Choose(id("Strike")), &mut Rng::new(1)).unwrap();
    assert_eq!((s.hand.count(id("Strike")), s.free_in_hand.count(id("Strike"))), (2, 0));
}

#[test]
fn a_typed_copy_pick_round_trips_in_the_codec() {
    use sts_engine::effects::{PickKind, Types};
    use sts_engine::state::{InPlay, Pick};
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(3));
    s.hand = Hand::from_cards(&[id("Strike"), id("Bash"), id("Defend")]);
    let pick = Pick { of: Types::of(&[sts_engine::cards::CardType::Attack, sts_engine::cards::CardType::Power]), copies: 2, ..Pick::new(PickKind::CopyInHand, 1, true, false) };
    s.stage = Stage::PlayingCard { card: id("Strike"), target: None, next: 1, hit: 0, x: 0, more: InPlay { pick: Some(pick), ..Default::default() } };
    let bytes = encode(&s);
    assert_eq!(decode(&bytes), s);
    let mut c = pick_of(&s);
    c.sort();
    let mut want = vec![id("Strike"), id("Bash")];
    want.sort();
    assert_eq!(c, want, "Defend isn't an Attack or a Power");
    // Every type allowed, no copies: the encoding of before.
    let plain = Pick::new(PickKind::DiscardFromHand, 1, true, false);
    s.stage = Stage::PlayingCard { card: id("Strike"), target: None, next: 1, hit: 0, x: 0, more: InPlay { pick: Some(plain), ..Default::default() } };
    assert_eq!(decode(&encode(&s)), s);
}

// ---- Juggernaut (`Juggernaut.use`: ApplyPowerAction(JuggernautPower 5,
// +2); `JuggernautPower.onGainedBlock`: when above 0, addToBot
// DamageRandomEnemyAction(THORNS of its amount), the target rolled when
// it runs; `addBlock` calls it for the player only) ----

#[test]
fn juggernaut_loads_as_the_game() {
    load_pack(PACK).unwrap();
    for name in ["gen:Juggernaut", "gen:Juggernaut+"] {
        let (ids, b) = bind(&[name]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty), (2, sts_engine::cards::CardType::Power), "{name}");
    }
}

#[test]
fn juggernaut_hits_on_each_block_gain() {
    for (name, n) in [("gen:Juggernaut", 5), ("gen:Juggernaut+", 7)] {
        let (mut s, ids) = setup(&[name, "Defend", "Defend"], &[], Encounter::JawWorm);
        play(&mut s, ids[0], 1);
        play(&mut s, ids[1], 1);
        assert_eq!((s.player.block, s.monsters[0].hp), (5, 100 - n), "{name}");
        play(&mut s, ids[2], 1);
        assert_eq!(s.monsters[0].hp, 100 - 2 * n, "{name}: once per gain");
    }
}

#[test]
fn juggernauts_hit_is_flat_damage_that_block_absorbs() {
    // Strength and the target's Vulnerable don't touch a THORNS hit; its
    // block does. Two stacks hit for 10 once.
    let (mut s, ids) = setup(&["gen:Juggernaut", "gen:Juggernaut", "Defend"], &[], Encounter::JawWorm);
    s.player.powers.add(Power::Strength, 3);
    s.monsters[0].powers.add(Power::Vulnerable, 2);
    s.monsters[0].block = 4;
    play(&mut s, ids[0], 1);
    play(&mut s, ids[1], 1);
    play(&mut s, ids[2], 1);
    assert_eq!((s.monsters[0].block, s.monsters[0].hp), (0, 100 - 6));
}

#[test]
fn no_hit_for_a_gain_of_zero() {
    // Entrench at 0 block gains nothing: no hit.
    let (mut s, ids) = setup(&["gen:Juggernaut", "gen:Entrench"], &[], Encounter::JawWorm);
    play(&mut s, ids[0], 1);
    play(&mut s, ids[1], 1);
    assert_eq!(s.monsters[0].hp, 100);
    // At 4 block it doubles: a gain of 4, one hit.
    s.player.block = 4;
    s.hand.add(ids[1], 1);
    play(&mut s, ids[1], 1);
    assert_eq!((s.player.block, s.monsters[0].hp), (8, 95));
}

#[test]
fn juggernaut_lands_after_the_cards_damage_before_curl_up_block() {
    // Iron Wave gains block (the hit is queued behind its damage), hits
    // and sets off Curl Up, whose block is queued behind the hit
    // (research skeptic check: the hit isn't reduced by Curl Up).
    let (mut s, ids) = setup(&["gen:Juggernaut", "Iron Wave"], &[], Encounter::JawWorm);
    s.monsters[0].powers.add(Power::CurlUp, 7);
    play(&mut s, ids[0], 1);
    play(&mut s, id("Iron Wave"), 1);
    assert_eq!((s.monsters[0].hp, s.monsters[0].block), (100 - 5 - 5, 7));
}

#[test]
fn juggernaut_rolls_after_the_cards_damage_and_ignores_curl_up() {
    // Iron Wave kills the slime it hits: the hit's target is rolled after,
    // among the one left, so there is no roll.
    let (mut s, ids) = setup(&["gen:Juggernaut", "Iron Wave"], &[], Encounter::SmallSlimes);
    s.monsters[0].hp = 5;
    play(&mut s, ids[0], 1);
    s.apply_action(Action::Play { card: id("Iron Wave"), target: Some(0) }).unwrap();
    assert_eq!((s.pending, s.monsters[0].hp, s.monsters[1].hp), (None, 0, 95));
    // A THORNS hit isn't an attack: Curl Up doesn't answer it.
    let (mut s, ids) = setup(&["gen:Juggernaut", "Defend"], &[], Encounter::JawWorm);
    s.monsters[0].powers.add(Power::CurlUp, 7);
    play(&mut s, ids[0], 1);
    play(&mut s, ids[1], 1);
    assert_eq!((s.monsters[0].hp, s.monsters[0].block, s.monsters[0].powers.get(Power::CurlUp)), (95, 0, 7));
}

#[test]
fn juggernaut_waits_for_the_cards_pick() {
    // True Grit+: block 9, then exhaust a card: the hit comes after the pick.
    let (mut s, ids) = setup(&["gen:Juggernaut", "gen:True Grit+", "Strike", "Defend"], &[], Encounter::JawWorm);
    play(&mut s, ids[0], 1);
    play(&mut s, ids[1], 1);
    assert!(s.pick().is_some());
    assert_eq!((s.player.block, s.monsters[0].hp, s.owed.iter().count()), (9, 100, 1), "the hit is owed");
    s.step(Action::Choose(id("Strike")), &mut Rng::new(1)).unwrap();
    assert_eq!((s.monsters[0].hp, s.owed.iter().count()), (95, 0));
}

#[test]
fn juggernaut_rolls_its_target_among_living_enemies() {
    let (mut s, ids) = setup(&["gen:Juggernaut", "Defend"], &[], Encounter::SmallSlimes);
    play(&mut s, ids[0], 1);
    s.apply_action(Action::Play { card: ids[1], target: None }).unwrap();
    assert_eq!(s.pending, Some(ChanceEvent::PlainHit { amount: 5 }));
    let Some(ChanceOutcomes::Listed(out)) = s.chance_outcomes(8) else { panic!("listed") };
    assert_eq!(out.len(), 2);
    for (i, (p, t)) in out.iter().enumerate() {
        assert!((p - 0.5).abs() < 1e-9);
        assert_eq!(t.monsters[i].hp, 95);
        assert_eq!(t.monsters[1 - i].hp, 100);
        assert_eq!(t.player.block, 5);
    }
    // One enemy left: no roll.
    let (mut s, ids) = setup(&["gen:Juggernaut", "Defend"], &[], Encounter::SmallSlimes);
    s.monsters[0].hp = 0;
    play(&mut s, ids[0], 1);
    s.apply_action(Action::Play { card: ids[1], target: None }).unwrap();
    assert_eq!((s.pending, s.monsters[1].hp), (None, 95));
}

#[test]
fn metallicize_at_turn_end_sets_juggernaut_off() {
    let (mut s, ids) = setup(&["gen:Juggernaut"], &[], Encounter::JawWorm);
    play(&mut s, ids[0], 1);
    s.player.powers.add(Power::Metallicize, 3);
    s.step(Action::EndTurn, &mut Rng::new(1)).unwrap();
    assert_eq!(s.monsters[0].hp, 95);
}

#[test]
fn an_owed_hit_round_trips_in_the_codec() {
    use sts_engine::state::OwedKind;
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(3));
    s.owed.push(OwedKind::Hit { amount: 7 }, 2, false);
    assert_eq!(decode(&encode(&s)), s);
    s.owed.clear();
    s.pending = Some(ChanceEvent::PlainHit { amount: 12 });
    assert_eq!(decode(&encode(&s)), s);
}
