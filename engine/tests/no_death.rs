//! No-death mode (learned play's training simulation): HP goes below 0
//! without ending the combat, which ends on a win or at the turn limit.

mod common;

use common::*;
use sts_engine::state::NO_DEATH_TURN_LIMIT;
use sts_engine::*;

/// A player at `hp` who only ends turns against a Jaw Worm.
fn idle_until_over(no_death: bool, hp: i16) -> (CombatState, i16) {
    let mut s = fresh(Encounter::JawWorm, 3);
    s.player.hp = hp;
    s.no_death = no_death;
    let mut lowest = hp;
    while !s.is_over() {
        end_turn(&mut s);
        lowest = lowest.min(s.player.hp);
        if no_death && s.player.hp < 0 {
            assert!(s.is_over() || s.awaiting_action() || s.pending.is_some(), "the combat goes on below 0 HP");
        }
    }
    (s, lowest)
}

#[test]
fn normal_play_ends_at_zero_hp() {
    let (s, lowest) = idle_until_over(false, 5);
    assert!(!s.won());
    assert_eq!(s.player.hp, 0);
    assert_eq!(lowest, 0);
}

#[test]
fn no_death_goes_negative_and_ends_at_the_turn_limit() {
    let (s, lowest) = idle_until_over(true, 5);
    assert!(lowest < 0, "HP went below 0");
    assert!(s.is_over() && !s.won(), "a combat nobody wins ends as a loss");
    assert_eq!(s.turn, NO_DEATH_TURN_LIMIT);
    assert_eq!(s.score(), 0.0);
}

#[test]
fn no_death_win_keeps_the_hp_left_without_healing() {
    let mut s = with_hand(Encounter::JawWorm, &["Strike"], 1);
    s.no_death = true;
    s.player.hp = -10;
    play(&mut s, "Strike", Some(0));
    assert!(s.won());
    assert_eq!(s.player.hp, -10, "no Burning Blood heal in no-death mode");
}

#[test]
fn hp_loss_hooks_fire_below_zero() {
    let mut s = with_hand(Encounter::Cultist, &["Rupture", "Bloodletting"], 100);
    s.no_death = true;
    s.player.hp = 2;
    play(&mut s, "Rupture", None);
    play(&mut s, "Bloodletting", None);
    assert_eq!(s.player.hp, -1);
    assert!(!s.is_over());
    assert_eq!(s.player.powers.get(Power::Strength), 1, "Rupture still reacts to HP lost below 0");
}

struct EndsTurns;

impl sts_engine::agent::Agent for EndsTurns {
    fn act(&mut self, _: &CombatState, _: &mut Rng) -> Action {
        Action::EndTurn
    }
}

#[test]
fn normal_play_stops_a_stalled_combat_at_the_play_turn_limit() {
    use sts_engine::runner::{play_from, PLAY_TURN_LIMIT};
    let mut s = fresh(Encounter::JawWorm, 3);
    s.player.hp = 30_000; // outlives the limit while only ending turns
    let r = play_from(s, &mut Rng::new(1), &mut Rng::new(2), &mut EndsTurns, false, 30_000);
    assert!(!r.won && r.hp_end == 0, "a stalled combat is lost: hp_end 0, as on a death");
    assert_eq!(r.healed, 0);
    assert_eq!(r.turns, PLAY_TURN_LIMIT + 1, "stopped as turn {} began", PLAY_TURN_LIMIT + 1);
    assert_eq!(r.score, 0.0);
}
