//! Card values from the StS wiki (slaythespire.wiki.gg), base and upgraded.

mod common;
use common::*;
use sts_engine::*;

const W: Encounter = Encounter::JawWorm;

fn hp_after(hand: &[&str], plays: &[&str]) -> i16 {
    let mut s = with_hand(W, hand, 40);
    for p in plays {
        let target = card(p).def().targeted().then_some(0);
        play(&mut s, p, target);
    }
    s.monsters[0].hp
}

#[test]
fn strike_deals_6_and_upgraded_9() {
    assert_eq!(hp_after(&["Strike"], &["Strike"]), 34);
    assert_eq!(hp_after(&["Strike+"], &["Strike+"]), 31);
}

#[test]
fn strike_costs_1_and_goes_to_discard() {
    for name in ["Strike", "Strike+"] {
        let mut s = with_hand(W, &[name], 40);
        play(&mut s, name, Some(0));
        assert_eq!(s.player.energy, 2);
        assert!(s.hand.is_empty());
        assert_eq!(s.discard().count(card(name)), 1);
    }
}

#[test]
fn defend_blocks_5_and_upgraded_8() {
    for (name, block) in [("Defend", 5), ("Defend+", 8)] {
        let mut s = with_hand(W, &[name], 40);
        play(&mut s, name, None);
        assert_eq!(s.player.block, block);
        assert_eq!(s.player.energy, 2);
    }
}

#[test]
fn bash_deals_8_applies_2_vulnerable() {
    let mut s = with_hand(W, &["Bash"], 40);
    play(&mut s, "Bash", Some(0));
    assert_eq!(s.monsters[0].hp, 32);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 2);
    assert_eq!(s.player.energy, 1);
}

#[test]
fn bash_upgraded_deals_10_applies_3_vulnerable() {
    let mut s = with_hand(W, &["Bash+"], 40);
    play(&mut s, "Bash+", Some(0));
    assert_eq!(s.monsters[0].hp, 30);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 3);
    assert_eq!(s.player.energy, 1);
}

#[test]
fn vulnerable_multiplies_damage_by_1_5_rounded_down() {
    // Bash's own hit isn't boosted; the next Strike is: 6 × 1.5 = 9, 9 × 1.5 = 13.
    assert_eq!(hp_after(&["Bash", "Strike"], &["Bash", "Strike"]), 40 - 8 - 9);
    assert_eq!(hp_after(&["Bash", "Strike+"], &["Bash", "Strike+"]), 40 - 8 - 13);
}

#[test]
fn strength_adds_before_vulnerable() {
    // Wiki example: Strike with 2 Strength on a Vulnerable target deals 12.
    let mut s = with_hand(W, &["Strike"], 40);
    s.player.powers.add(Power::Strength, 2);
    s.monsters[0].powers.add(Power::Vulnerable, 1);
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].hp, 28);
}

#[test]
fn weak_attacker_deals_75_percent_rounded_down() {
    let mut s = with_hand(W, &["Strike"], 40);
    s.player.powers.add(Power::Weak, 1);
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].hp, 36); // 6 × 0.75 = 4.5 → 4
}

#[test]
fn block_absorbs_damage_first() {
    let mut s = with_hand(W, &["Strike"], 40);
    s.monsters[0].block = 4;
    play(&mut s, "Strike", Some(0));
    assert_eq!((s.monsters[0].block, s.monsters[0].hp), (0, 38));
}

#[test]
fn shrug_it_off_blocks_then_draws_1() {
    for (name, block) in [("Shrug It Off", 8), ("Shrug It Off+", 11)] {
        let mut s = with_hand(W, &[name], 40);
        s.set_draw(Pile::from_cards(&[card("Strike"), card("Defend")]));
        play(&mut s, name, None);
        assert_eq!(s.player.block, block);
        // Two possible draws: the state waits at a chance node mid-card.
        assert_eq!(s.pending, Some(ChanceEvent::Draw { n: 1 }));
        let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!() };
        assert_eq!(v.len(), 2);
        for (p, t) in &v {
            assert!((p - 0.5).abs() < 1e-12);
            assert!(t.awaiting_action());
            assert_eq!(t.hand.len(), 1);
            assert_eq!(t.discard().count(card(name)), 1);
        }
    }
}

#[test]
fn certain_draw_does_not_pause() {
    let mut s = with_hand(W, &["Shrug It Off"], 40);
    s.set_draw(Pile::from_cards(&[card("Strike"), card("Strike")]));
    play(&mut s, "Shrug It Off", None);
    assert!(s.awaiting_action());
    assert_eq!(s.hand.count(card("Strike")), 1);
}

#[test]
fn costs_and_targets_gate_legality() {
    let mut s = with_hand(W, &["Bash", "Defend"], 40);
    s.player.energy = 1;
    assert!(!s.is_legal(Action::Play { card: card("Bash"), target: Some(0) }));
    assert!(!s.is_legal(Action::Play { card: card("Defend"), target: Some(0) }));
    assert!(s.is_legal(Action::Play { card: card("Defend"), target: None }));
    s.player.energy = 2;
    assert!(!s.is_legal(Action::Play { card: card("Bash"), target: None }));
    assert!(!s.is_legal(Action::Play { card: card("Bash"), target: Some(1) })); // empty slot
    assert!(s.is_legal(Action::Play { card: card("Bash"), target: Some(0) }));
}

#[test]
fn duplicate_cards_give_one_action() {
    let s = with_hand(W, &["Strike", "Strike", "Strike", "Defend", "Defend"], 40);
    let a = s.legal_actions();
    assert_eq!(
        a,
        vec![
            Action::Play { card: card("Strike"), target: Some(0) },
            Action::Play { card: card("Defend"), target: None },
            Action::EndTurn,
        ]
    );
}

#[test]
fn killing_blow_wins_and_burning_blood_heals_6() {
    let mut s = with_hand(W, &["Strike"], 5);
    s.player.hp = 50;
    play(&mut s, "Strike", Some(0));
    assert!(s.won());
    assert_eq!(s.monsters[0].hp, 0);
    assert_eq!(s.player.hp, 56);
    assert_eq!(s.discard().count(card("Strike")), 1);

    let mut s = with_hand(W, &["Strike"], 5);
    s.player.hp = 78;
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.player.hp, 80); // capped at max HP
}

#[test]
fn win_scores_2_minus_hp_lost_after_burning_blood() {
    // From 80/80: 10 lost, 6 healed back, so 4 lost: 2 - 4/100.
    let mut s = with_hand(W, &["Strike"], 5);
    s.player.hp = 70;
    play(&mut s, "Strike", Some(0));
    assert!((s.score() - 1.96).abs() < 1e-12);
    // 6 or fewer lost heals back in full.
    let mut s = with_hand(W, &["Strike"], 5);
    s.player.hp = 74;
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.score(), 2.0);
    // Max HP doesn't matter, only HP lost from the start.
    let mut s = CombatState::new(&starter_deck(), 50, 100, W, &mut Rng::new(1));
    s.hand = Hand::from_cards(&[card("Strike")]);
    s.player.energy = 3;
    s.player.hp = 40;
    s.monsters = Default::default();
    s.monsters[0] = sts_engine::monsters::Monster::new(MonsterKind::JawWorm, 5);
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.player.hp, 46);
    assert!((s.score() - 1.96).abs() < 1e-12);
    // A loss scores 0.
    let mut s = with_hand(W, &["Defend"], 40);
    s.player.hp = 1;
    while !s.is_over() {
        end_turn(&mut s);
    }
    assert!(!s.won());
    assert_eq!(s.score(), 0.0);
}

#[test]
fn heuristic_ignores_max_hp() {
    // Silent has no end-of-combat heal, so max HP can't cap anything.
    let deck = Character::Silent.starter_deck();
    let a = CombatState::new_as(Character::Silent, &deck, 50, 70, W, &mut Rng::new(2));
    let mut b = a.clone();
    b.player.max_hp = 100;
    let (ea, eb) = (sts_engine::heuristic::estimate(&a), sts_engine::heuristic::estimate(&b));
    assert_eq!(ea, eb);
}

#[test]
fn card_names_round_trip() {
    for c in CardId::all() {
        if !c.is_status() {
            assert_eq!(CardId::from_name(c.name()), Some(c));
            assert_eq!(c.upgraded(), c.name().ends_with('+'));
        }
    }
}
