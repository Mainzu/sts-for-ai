//! Listed chance outcomes are a proper distribution and match sampling.

mod common;
use common::*;
use std::collections::HashMap;
use sts_engine::chance::draw_outcomes;
use sts_engine::monsters::*;
use sts_engine::monsters::MonsterKind;
use sts_engine::*;

const SAMPLES: usize = 100_000;

/// Listed probabilities sum to 1 and every outcome's sampled frequency is
/// within 5 standard errors of it.
fn check_against_sampling(s: &CombatState) {
    let Some(ChanceOutcomes::Listed(listed)) = s.chance_outcomes(10_000) else { panic!("not listed") };
    let total: f64 = listed.iter().map(|x| x.0).sum();
    assert!((total - 1.0).abs() < 1e-9, "sum {total}");
    for (i, a) in listed.iter().enumerate() {
        assert!(listed[i + 1..].iter().all(|b| b.1 != a.1), "duplicate outcome state");
    }
    let mut counts: HashMap<CombatState, usize> = HashMap::new();
    let mut rng = Rng::new(42);
    for _ in 0..SAMPLES {
        let mut t = s.clone();
        t.resolve_chance(&mut rng);
        *counts.entry(t).or_default() += 1;
    }
    assert_eq!(counts.len(), listed.len(), "sampled an unlisted outcome");
    for (p, state) in &listed {
        let f = *counts.get(state).unwrap_or(&0) as f64 / SAMPLES as f64;
        let se = (p * (1.0 - p)).max(0.0).sqrt() / (SAMPLES as f64).sqrt();
        assert!((f - p).abs() <= 5.0 * se + 1e-4, "listed {p}, sampled {f}");
    }
}

fn paused_draw(draw: &[&str], discard: &[&str], n: u8) -> CombatState {
    let mut s = with_hand(Encounter::JawWorm, &[], 40);
    s.set_draw(Pile::from_cards(&draw.iter().map(|c| card(c)).collect::<Vec<_>>()));
    s.set_discard(Pile::from_cards(&discard.iter().map(|c| card(c)).collect::<Vec<_>>()));
    s.pending = Some(ChanceEvent::Draw { n });
    s
}

#[test]
fn opening_hand_draw_matches_sampling() {
    let starter: Vec<&str> = starter_deck().iter().map(|c| c.name()).collect();
    let s = paused_draw(&starter, &[], 5);
    check_against_sampling(&s);
    // Strike + Defend + Bash = 5 with Defend 0..=4, Bash 0..=1: 5 + 5 = 10 multisets.
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(100) else { panic!() };
    assert_eq!(v.len(), 10);
}

#[test]
fn draw_with_reshuffle_matches_sampling() {
    let s = paused_draw(&["Strike", "Bash"], &["Strike", "Defend", "Defend", "Shrug It Off", "Strike+"], 4);
    check_against_sampling(&s);
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(100) else { panic!() };
    for (_, t) in &v {
        // Both draw-pile cards are always drawn; the discard became the draw pile.
        assert_eq!(t.hand.count(card("Bash")), 1);
        assert!(t.hand.count(card("Strike")) >= 1);
        assert!(t.discard().is_empty());
        assert_eq!(t.draw().len(), 3);
    }
}

#[test]
fn jaw_worm_move_roll_matches_sampling() {
    for history in [[CHOMP, NO_MOVE], [BELLOW, CHOMP], [THRASH, CHOMP], [THRASH, THRASH]] {
        let mut s = with_hand(Encounter::JawWorm, &[], 40);
        s.monsters[0].moves = history;
        s.pending = Some(ChanceEvent::MonsterMove { slot: 0 });
        s.stage = Stage::StartTurn; // as after a monster turn
        s.set_draw(Pile::from_cards(&[card("Strike"); 5])); // certain draw: no second pause
        check_against_sampling(&s);
    }
}

#[test]
fn large_draws_report_large() {
    let starter: Vec<&str> = starter_deck().iter().map(|c| c.name()).collect();
    let s = paused_draw(&starter, &[], 5);
    assert!(matches!(s.chance_outcomes(9), Some(ChanceOutcomes::Large)));
    assert!(matches!(s.chance_outcomes(10), Some(ChanceOutcomes::Listed(_))));
    assert!(draw_outcomes(s.draw(), s.discard(), 5, 9).is_none());
}

#[test]
fn no_pending_event_lists_nothing() {
    let s = fresh(Encounter::Cultist, 3);
    assert!(s.awaiting_action());
    assert!(s.chance_outcomes(16).is_none());
}

/// The monster in slot 0 (of `kinds`) about to roll after `history`; the
/// next draw is certain so the roll is the only event.
fn paused_roll(kinds: &[MonsterKind], history: [MoveId; 2]) -> CombatState {
    let mut s = vs(kinds, &[], None);
    s.monsters[0].moves = history;
    s.pending = Some(ChanceEvent::MonsterMove { slot: 0 });
    s.stage = Stage::StartTurn;
    s.set_draw(Pile::from_cards(&[card("Strike"); 5]));
    s
}

#[test]
fn act1_move_rolls_match_sampling() {
    use MonsterKind as K;
    let cases: &[(K, [MoveId; 2])] = &[
        (K::RedLouse, [NO_MOVE, NO_MOVE]),
        (K::GreenLouse, [louse::BITE, louse::BITE]),
        (K::AcidSlimeS, [NO_MOVE, NO_MOVE]),
        (K::AcidSlimeM, [acid_slime::TACKLE, NO_MOVE]),
        (K::AcidSlimeL, [acid_slime::LICK, acid_slime::LICK]),
        (K::SpikeSlimeM, [NO_MOVE, NO_MOVE]),
        (K::SpikeSlimeL, [spike_slime::LICK, spike_slime::FLAME_TACKLE]),
        (K::FungiBeast, [fungi_beast::BITE, fungi_beast::BITE]),
        (K::FungiBeast, [fungi_beast::BITE, fungi_beast::GROW]),
        (K::Looter, [looter::MUG, looter::MUG]),
        (K::GremlinNob, [gremlin_nob::BULL_RUSH, gremlin_nob::BELLOW]),
    ];
    for &(kind, history) in cases {
        let s = paused_roll(&[kind], history);
        check_against_sampling(&s);
    }
}

#[test]
fn random_target_hit_matches_sampling() {
    use MonsterKind as K;
    let mut s = vs(&[K::JawWorm, K::Cultist, K::FungiBeast], &["Sword Boomerang+"], Some(30));
    s.player.powers.add(Power::Strength, 1);
    play(&mut s, "Sword Boomerang+", None);
    assert_eq!(s.pending, Some(ChanceEvent::RandomTarget { amount: 3 }));
    check_against_sampling(&s);
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!() };
    assert_eq!(v.len(), 3);
    for (p, t) in &v {
        assert!((p - 1.0 / 3.0).abs() < 1e-12);
        let total: i16 = t.monsters[..3].iter().map(|m| 30 - m.hp).sum();
        assert_eq!(total, 4, "first hit with Strength 1");
        assert_eq!(t.pending, Some(ChanceEvent::RandomTarget { amount: 3 }), "next hit pauses too");
    }
    assert!(matches!(s.chance_outcomes(2), Some(ChanceOutcomes::Large)));
}

#[test]
fn random_target_stops_pausing_when_one_enemy_is_left() {
    use MonsterKind as K;
    let mut s = vs(&[K::JawWorm, K::Cultist], &["Sword Boomerang"], Some(30));
    s.monsters[1].hp = 3;
    s.monsters[1].max_hp = 3;
    play(&mut s, "Sword Boomerang", None);
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!() };
    // Hit the Cultist: it dies, the other two hits go to the Jaw Worm with no pause.
    let (_, killed) = v.iter().find(|(_, t)| !t.monsters[1].alive()).unwrap();
    assert!(killed.awaiting_action());
    assert_eq!(killed.monsters[0].hp, 24);
}

#[test]
fn bouncing_flask_bounce_matches_sampling() {
    use MonsterKind as K;
    let mut s = vs(&[K::JawWorm, K::Cultist, K::FungiBeast], &["Bouncing Flask"], Some(30));
    play(&mut s, "Bouncing Flask", None);
    assert_eq!(s.pending, Some(ChanceEvent::RandomTarget { amount: 3 }));
    check_against_sampling(&s);
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!() };
    assert_eq!(v.len(), 3);
    for (p, t) in &v {
        assert!((p - 1.0 / 3.0).abs() < 1e-12);
        let total: i16 = t.monsters[..3].iter().map(|m| m.powers.get(Power::Poison)).sum();
        assert_eq!(total, 3, "first bounce");
        assert!(t.monsters[..3].iter().all(|m| m.hp == 30), "poison only, no damage");
    }
}

#[test]
fn ring_of_the_snake_opening_draw_matches_sampling() {
    let deck: Vec<&str> = Character::Silent.starter_deck().iter().map(|c| c.name()).collect();
    let s = paused_draw(&deck, &[], 7);
    check_against_sampling(&s);
}
