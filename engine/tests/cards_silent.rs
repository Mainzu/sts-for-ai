//! The Silent (Amendment 2): cards base and upgraded, Shivs, Poison, Ring of
//! the Snake. Values from slaythespire.wiki.gg.

mod common;
use common::*;
use sts_engine::cards::{class_cards, deck_cards, CardClass};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::monsters::*;
use sts_engine::state::HAND_LIMIT;
use sts_engine::*;

/// One Jaw Worm at 100 HP, `hand`, 3 energy.
fn worm(hand: &[&str]) -> CombatState {
    vs(&[K::JawWorm], hand, Some(100))
}

fn auto_play(s: &mut CombatState, name: &str) {
    let target = card(name).def().targeted().then_some(0);
    play(s, name, target);
}

/// (monster HP lost, energy spent, block gained, Weak and Poison on the monster).
fn effect_of(name: &str) -> (i16, i16, i16, i16, i16) {
    let mut s = worm(&[name]);
    auto_play(&mut s, name);
    let m = &s.monsters[0];
    (100 - m.hp, 3 - s.player.energy, s.player.block, m.powers.get(Power::Weak), m.powers.get(Power::Poison))
}

#[test]
fn simple_cards_match_the_wiki() {
    // (name, damage, cost, block, weak, poison)
    let cases: &[(&str, i16, i16, i16, i16, i16)] = &[
        ("Silent Strike", 6, 1, 0, 0, 0),
        ("Silent Strike+", 9, 1, 0, 0, 0),
        ("Silent Defend", 0, 1, 5, 0, 0),
        ("Silent Defend+", 0, 1, 8, 0, 0),
        ("Neutralize", 3, 0, 0, 1, 0),
        ("Neutralize+", 4, 0, 0, 2, 0),
        ("Sucker Punch", 7, 1, 0, 1, 0),
        ("Sucker Punch+", 9, 1, 0, 2, 0),
        ("Leg Sweep", 0, 2, 11, 2, 0),
        ("Leg Sweep+", 0, 2, 14, 3, 0),
        ("Deflect", 0, 0, 4, 0, 0),
        ("Deflect+", 0, 0, 7, 0, 0),
        ("Slice", 6, 0, 0, 0, 0),
        ("Slice+", 9, 0, 0, 0, 0),
        ("Shiv", 4, 0, 0, 0, 0),
        ("Shiv+", 6, 0, 0, 0, 0),
        ("Deadly Poison", 0, 1, 0, 0, 5),
        ("Deadly Poison+", 0, 1, 0, 0, 7),
        ("Poisoned Stab", 6, 1, 0, 0, 3),
        ("Poisoned Stab+", 8, 1, 0, 0, 4),
    ];
    for &(name, dmg, cost, block, weak, poison) in cases {
        assert_eq!(effect_of(name), (dmg, cost, block, weak, poison), "{name}");
    }
}

#[test]
fn silent_strike_and_defend_are_their_own_kinds_with_ironclad_effects() {
    for (silent, ironclad) in [("Silent Strike", "Strike"), ("Silent Defend", "Defend"), ("Silent Strike+", "Strike+")] {
        assert_ne!(card(silent), card(ironclad));
        assert_eq!(effect_of(silent), effect_of(ironclad));
        assert_eq!(card(silent).def().effects, card(ironclad).def().effects);
    }
    assert!(card("Silent Strike").def().is_strike());
}

#[test]
fn quick_slash_and_backflip_draw() {
    for (name, dmg, block, draws) in [("Quick Slash", 8, 0, 1), ("Quick Slash+", 12, 0, 1), ("Backflip", 0, 5, 2), ("Backflip+", 0, 8, 2)] {
        let mut s = worm(&[name]);
        s.set_draw(Pile::from_cards(&[card("Slice"); 4]));
        auto_play(&mut s, name);
        assert_eq!(100 - s.monsters[0].hp, dmg, "{name}");
        assert_eq!(s.player.block, block, "{name}");
        assert_eq!(s.hand.count(card("Slice")), draws, "{name}");
        assert_eq!(3 - s.player.energy, 1);
    }
}

#[test]
fn dagger_spray_hits_all_enemies_twice() {
    for (name, dmg) in [("Dagger Spray", 4), ("Dagger Spray+", 6)] {
        let mut s = vs(&[K::JawWorm, K::Cultist], &[name], Some(40));
        play(&mut s, name, None);
        assert_eq!(s.monsters[0].hp, 40 - 2 * dmg);
        assert_eq!(s.monsters[1].hp, 40 - 2 * dmg);
        assert_eq!(3 - s.player.energy, 1);
    }
    // Vulnerable counts on each hit.
    let mut s = vs(&[K::JawWorm], &["Dagger Spray"], Some(40));
    s.monsters[0].powers.add(Power::Vulnerable, 1);
    play(&mut s, "Dagger Spray", None);
    assert_eq!(s.monsters[0].hp, 40 - 12);
}

#[test]
fn blade_dance_and_cloak_and_dagger_add_shivs_to_hand() {
    for (name, shivs, block) in [("Blade Dance", 3, 0), ("Blade Dance+", 4, 0), ("Cloak and Dagger", 1, 6), ("Cloak and Dagger+", 2, 6)] {
        let mut s = worm(&[name]);
        auto_play(&mut s, name);
        assert_eq!(s.hand.count(card("Shiv")), shivs, "{name}");
        assert_eq!(s.player.block, block, "{name}");
        assert_eq!(s.created, shivs as u16);
        assert_eq!(3 - s.player.energy, 1);
    }
    // Shivs are 0-cost attacks that exhaust.
    let mut s = worm(&["Blade Dance"]);
    play(&mut s, "Blade Dance", None);
    for _ in 0..3 {
        play(&mut s, "Shiv", Some(0));
    }
    assert_eq!(s.monsters[0].hp, 88);
    assert_eq!(s.exhaust().count(card("Shiv")), 3);
    assert_eq!(s.player.energy, 2);
}

#[test]
fn shivs_past_the_hand_limit_go_to_discard() {
    let mut hand = vec!["Silent Defend"; HAND_LIMIT - 2];
    hand.push("Blade Dance+");
    let mut s = worm(&hand);
    play(&mut s, "Blade Dance+", None);
    // Blade Dance left the hand: 8 Defends + room for 2 Shivs; the other 2 go to discard.
    assert_eq!(s.hand.len(), HAND_LIMIT);
    assert_eq!(s.hand.count(card("Shiv")), 2);
    assert_eq!(s.discard().count(card("Shiv")), 2);
}

#[test]
fn poison_ticks_at_the_monster_turn_start_ignoring_block_then_drops() {
    let mut s = worm(&["Deadly Poison"]);
    s.player.hp = 500;
    s.player.max_hp = 500;
    play(&mut s, "Deadly Poison", Some(0));
    s.monsters[0].block = 20; // cleared before the tick anyway; Poison ignores block
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, 95);
    assert_eq!(s.monsters[0].powers.get(Power::Poison), 4);
    for (hp, left) in [(91, 3), (88, 2), (86, 1), (85, 0)] {
        s.hand = Hand::default();
        end_turn(&mut s);
        assert_eq!((s.monsters[0].hp, s.monsters[0].powers.get(Power::Poison)), (hp, left));
    }
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, 85, "no Poison left");
}

#[test]
fn poison_stacks_and_kills_before_the_monster_acts() {
    let mut s = vs(&[K::JawWorm], &["Deadly Poison", "Poisoned Stab"], Some(5));
    play(&mut s, "Deadly Poison", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Poison), 5);
    s.monsters[0].moves = [CHOMP, NO_MOVE];
    let hp = s.player.hp;
    end_turn(&mut s);
    assert!(s.won(), "Poison 5 kills a 5 HP Jaw Worm before it attacks");
    assert_eq!(s.player.hp, (hp + 6).min(s.player.max_hp), "this test state is an Ironclad one");

    let mut s = vs(&[K::JawWorm], &["Deadly Poison", "Poisoned Stab"], Some(50));
    play(&mut s, "Deadly Poison", Some(0));
    play(&mut s, "Poisoned Stab", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Poison), 8);
    assert_eq!(s.monsters[0].hp, 44);
}

#[test]
fn poison_does_not_trigger_curl_up_but_wakes_lagavulin_and_splits_slimes() {
    // Curl Up reacts to attacks only.
    let mut s = vs(&[K::RedLouse], &["Deadly Poison"], Some(15));
    s.player.hp = 500;
    s.player.max_hp = 500;
    s.monsters[0].powers.add(Power::CurlUp, 4);
    let curl = 4;
    play(&mut s, "Deadly Poison", Some(0));
    s.monsters[0].moves = [louse::OTHER, NO_MOVE];
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, 10);
    assert_eq!(s.monsters[0].powers.get(Power::CurlUp), curl);

    // Lagavulin: the HP loss wakes it, stunned for this turn.
    let mut s = vs(&[K::Lagavulin], &["Deadly Poison"], Some(110));
    s.monsters[0].moves = [lagavulin::SLEEP, NO_MOVE];
    play(&mut s, "Deadly Poison", Some(0));
    let hp = s.player.hp;
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, 105);
    assert_eq!(s.monsters[0].powers.get(Power::Metallicize), 0);
    assert_eq!(s.player.hp, hp, "stunned: no attack");
    assert_eq!(s.monsters[0].intent(), lagavulin::ATTACK);

    // A large slime pushed to half HP by Poison splits that turn.
    let mut s = vs(&[K::SpikeSlimeL], &["Deadly Poison"], Some(36));
    s.monsters[0].max_hp = 64;
    s.monsters[0].moves = [spike_slime::LICK, NO_MOVE];
    play(&mut s, "Deadly Poison", Some(0));
    end_turn(&mut s);
    for slot in [0, 1] {
        let m = &s.monsters[slot];
        assert_eq!((m.kind, m.hp), (K::SpikeSlimeM, 31));
    }
}

#[test]
fn poison_death_releases_spore_cloud_and_artifact_blocks_poison() {
    let mut s = vs(&[K::FungiBeast, K::JawWorm], &["Deadly Poison"], Some(4));
    s.monsters[1].hp = 100;
    s.monsters[1].max_hp = 100;
    s.monsters[0].moves = [fungi_beast::GROW, NO_MOVE];
    s.monsters[1].moves = [BELLOW, NO_MOVE];
    play(&mut s, "Deadly Poison", Some(0));
    end_turn(&mut s);
    assert!(!s.monsters[0].alive());
    assert_eq!(s.player.powers.get(Power::Vulnerable), 2);

    let mut s = vs(&[K::Sentry], &["Deadly Poison", "Poisoned Stab"], Some(40));
    play(&mut s, "Deadly Poison", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Poison), 0);
    assert_eq!(s.monsters[0].powers.get(Power::Artifact), 0);
    play(&mut s, "Poisoned Stab", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Poison), 3);
}

#[test]
fn bouncing_flask_spreads_poison_over_random_enemies() {
    // One enemy: no chance node, all of it lands there.
    for (name, total) in [("Bouncing Flask", 9), ("Bouncing Flask+", 12)] {
        let mut s = worm(&[name]);
        play(&mut s, name, None);
        assert!(s.pending.is_none());
        assert_eq!(s.monsters[0].powers.get(Power::Poison), total);
        assert_eq!(3 - s.player.energy, 2);
    }
    // Two enemies: three 3-Poison bounces, binomial split.
    let mut s = vs(&[K::JawWorm, K::Cultist], &["Bouncing Flask"], Some(40));
    play(&mut s, "Bouncing Flask", None);
    assert_eq!(s.pending, Some(ChanceEvent::RandomTarget { amount: 3 }));
    let Some(v) = sts_engine::options::resolve_all(&s, 16) else { panic!("small") };
    let mut got: Vec<(i16, f64)> = v.iter().map(|(p, t)| (t.monsters[0].powers.get(Power::Poison), *p)).collect();
    got.sort_by_key(|x| x.0);
    let want = [(0, 0.125), (3, 0.375), (6, 0.375), (9, 0.125)];
    assert_eq!(got.len(), 4);
    for ((a, p), (b, q)) in got.iter().zip(want) {
        assert_eq!(*a, b);
        assert!((p - q).abs() < 1e-12);
    }
    for (_, t) in &v {
        assert_eq!(t.monsters[0].powers.get(Power::Poison) + t.monsters[1].powers.get(Power::Poison), 9);
        assert_eq!(t.monsters[0].hp + t.monsters[1].hp, 80, "Poison doesn't hurt until it ticks");
    }
}

#[test]
fn silent_starts_with_70_hp_ring_of_the_snake_and_no_heal() {
    let c = Character::Silent;
    assert_eq!(c.max_hp(), 70);
    let deck = c.starter_deck();
    let count = |n: &str| deck.iter().filter(|&&x| x == card(n)).count();
    assert_eq!((deck.len(), count("Silent Strike"), count("Silent Defend"), count("Neutralize")), (12, 5, 6, 1));
    let mut rng = Rng::new(3);
    let mut s = CombatState::new_as(c, &deck, 70, 70, Encounter::JawWorm, &mut rng);
    assert_eq!(s.hand.len(), 7, "Ring of the Snake: 5 + 2 on turn 1");
    s.step(Action::EndTurn, &mut rng).unwrap();
    assert_eq!(s.hand.len(), 5, "only the first turn");
    // An Ironclad combat still draws 5.
    let s = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(3));
    assert_eq!(s.hand.len(), 5);
    // No Burning Blood: winning heals nothing.
    let mut s = CombatState::new_as(c, &deck, 70, 70, Encounter::JawWorm, &mut Rng::new(3));
    s.player.hp = 60;
    s.hand = Hand::from_cards(&[card("Slice")]);
    s.monsters[0].hp = 1;
    s.monsters[0].block = 0;
    s.apply_action(Action::Play { card: card("Slice"), target: Some(0) }).unwrap();
    assert!(s.won());
    assert_eq!(s.player.hp, 60);
    assert!((s.score() - 1.90).abs() < 1e-12, "2 - 10 lost / 100");
}

#[test]
fn card_pools_by_class() {
    // Ironclad decks: the cards they were before the Silent, plus Spot
    // Weakness, Dropkick, Combust, Brutality and Rupture (triggers and
    // conditions).
    assert_eq!(deck_cards().count(), 58);
    assert!(deck_cards().all(|c| c.def().class == CardClass::Ironclad));
    let silent: Vec<&str> = class_cards(CardClass::Silent).map(|c| c.name()).collect();
    assert_eq!(silent.len(), 30, "15 Silent cards, base and upgraded");
    assert!(!silent.contains(&"Shiv"), "Shiv is colorless and never picked");
    assert_eq!(card("Shiv").def().class, CardClass::Colorless);
}
