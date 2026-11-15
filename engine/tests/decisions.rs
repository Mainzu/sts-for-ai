//! Decision points (docs/specs/decision-points.md): picks inside a card
//! (Survivor, Hologram), `Choose` / `Done`, Burst's replay, the codec and
//! the search's node cap.

mod common;

use common::*;
use sts_engine::codec;
use sts_engine::effects::PickKind;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::search::{Heuristic, SearchConfig};
use sts_engine::state::{InPlay, Pick, Stage};
use sts_engine::*;

fn silent_vs_worm(hand: &[&str]) -> CombatState {
    vs(&[K::JawWorm], hand, Some(100))
}

#[test]
fn survivor_discards_the_chosen_card() {
    let mut s = silent_vs_worm(&["Survivor", "Strike", "Strike", "Defend"]);
    play(&mut s, "Survivor", None);
    assert!(s.awaiting_action() && s.pick().is_some());
    assert_eq!(s.player.block, 8);
    // One option per distinct card: Strike once, though two are held.
    assert_eq!(s.legal_actions(), vec![Action::Choose(card("Strike")), Action::Choose(card("Defend"))]);
    assert!(!s.is_legal(Action::EndTurn) && !s.is_legal(Action::Done));
    s.apply_action(Action::Choose(card("Strike"))).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((s.hand.count(card("Strike")), s.discard().count(card("Strike"))), (1, 1));
    assert_eq!(s.discard().count(card("Survivor")), 1);
}

#[test]
fn survivor_with_empty_hand_skips_the_pick() {
    let mut s = silent_vs_worm(&["Survivor+"]);
    play(&mut s, "Survivor+", None);
    assert_eq!((s.stage, s.player.block), (Stage::PlayerTurn, 11));
}

#[test]
fn up_to_pick_offers_done() {
    let mut s = silent_vs_worm(&["Strike", "Defend"]);
    let more = InPlay { pick: Some(Pick::new(PickKind::DiscardFromHand, 2, false, false)), ..Default::default() };
    s.stage = Stage::PlayingCard { card: card("Survivor"), target: None, next: 2, hit: 0, x: 0, more };
    assert_eq!(s.legal_actions().last(), Some(&Action::Done));
    s.apply_action(Action::Choose(card("Strike"))).unwrap();
    assert!(s.pick().is_some(), "one pick left");
    s.apply_action(Action::Done).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!(s.hand.count(card("Defend")), 1);
}

#[test]
fn hologram_returns_from_discard() {
    let mut s = vs(&[K::JawWorm], &["Hologram"], Some(100));
    s.set_discard(Pile::from_cards(&[card("Bash"), card("Strike")]));
    play(&mut s, "Hologram", None);
    assert_eq!(s.legal_actions(), vec![Action::Choose(card("Strike")), Action::Choose(card("Bash"))].into_iter().filter(|a| s.is_legal(*a)).collect::<Vec<_>>());
    s.apply_action(Action::Choose(card("Bash"))).unwrap();
    assert_eq!((s.hand.count(card("Bash")), s.player.block, s.exhaust().count(card("Hologram"))), (1, 3, 1));
    // Nothing in the discard pile: no pick.
    let mut s = vs(&[K::JawWorm], &["Hologram+"], Some(100));
    play(&mut s, "Hologram+", None);
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!(s.discard().count(card("Hologram+")), 1);
}

#[test]
fn burst_replays_next_skill() {
    let mut s = silent_vs_worm(&["Burst", "Silent Defend", "Silent Strike"]);
    play(&mut s, "Burst", None);
    assert_eq!(s.player.powers.get(Power::Burst), 1, "Burst doesn't replay itself");
    assert_eq!(s.discard().count(card("Burst")), 1);
    play(&mut s, "Silent Defend", None);
    assert_eq!(s.player.block, 10, "played twice");
    assert_eq!(s.player.energy, 1, "paid once");
    assert_eq!(s.cards_played_this_turn, 3, "the copy counts");
    assert_eq!(s.discard().count(card("Silent Defend")), 1, "the copy is purged");
    assert_eq!(s.player.powers.get(Power::Burst), 0);
    // An Attack isn't replayed.
    let mut s = silent_vs_worm(&["Burst", "Silent Strike"]);
    play(&mut s, "Burst", None);
    play(&mut s, "Silent Strike", Some(0));
    assert_eq!((s.monsters[0].hp, s.player.powers.get(Power::Burst)), (94, 1));
    // Gone at the end of the turn.
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Burst), 0);
}

#[test]
fn burst_replays_survivor_with_two_picks() {
    let mut s = silent_vs_worm(&["Burst", "Survivor", "Strike", "Defend"]);
    play(&mut s, "Burst", None);
    play(&mut s, "Survivor", None);
    s.apply_action(Action::Choose(card("Strike"))).unwrap();
    // The copy plays: block again, then its own pick.
    assert_eq!(s.player.block, 16);
    assert!(matches!(s.stage, Stage::PlayingCard { more: InPlay { copy: true, pick: Some(_), .. }, .. }));
    s.apply_action(Action::Choose(card("Defend"))).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!(s.hand.len(), 0);
    assert_eq!(s.discard().count(card("Survivor")), 1);
}

#[test]
fn codec_round_trips_picks_and_replays() {
    let mut s = silent_vs_worm(&["Burst", "Survivor", "Strike", "Defend"]);
    play(&mut s, "Burst", None);
    play(&mut s, "Survivor", None);
    for _ in 0..2 {
        let b = codec::encode(&s);
        assert_eq!(codec::decode(&b), s);
        let a = s.legal_actions()[0];
        let mut out = Vec::new();
        codec::encode_action(a, &mut out);
        assert_eq!(codec::decode_action(&out, &mut 0), Some(a));
        s.apply_action(a).unwrap();
    }
    let mut out = Vec::new();
    codec::encode_action(Action::Done, &mut out);
    assert_eq!(codec::decode_action(&out, &mut 0), Some(Action::Done));
}

/// Asserts it is never asked to score a state paused at a pick.
struct NoPickLeaves;

impl sts_engine::search::Evaluator for NoPickLeaves {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        assert!(states.iter().all(|s| s.pick().is_none()), "a pick became a leaf");
        vec![0.0; states.len()]
    }
}

#[test]
fn search_never_scores_a_pick() {
    // With a 1-node cap every root child but the first is cut to a leaf:
    // Survivor's child is a pick, which must be expanded instead.
    let s = silent_vs_worm(&["Survivor", "Strike", "Defend", "Neutralize", "Silent Defend"]);
    let cfg = SearchConfig { max_nodes: 1, ..SearchConfig::default() };
    let r = sts_engine::search::search(&s, &mut NoPickLeaves, &cfg);
    assert!(s.is_legal(r.action));
}

#[test]
fn search_completes_picks_past_the_node_cap() {
    let mut s = silent_vs_worm(&["Survivor", "Strike", "Defend", "Neutralize", "Silent Defend"]);
    s.player.energy = 3;
    let cfg = SearchConfig { max_nodes: 1, ..SearchConfig::default() };
    let mut agent = sts_engine::agent::SearchAgent::new(Heuristic, cfg);
    // Any legal choice comes back, at the pick and before it.
    use sts_engine::agent::Agent;
    let a = agent.act(&s, &mut Rng::new(1));
    assert!(s.is_legal(a));
    play(&mut s, "Survivor", None);
    let a = agent.act(&s, &mut Rng::new(1));
    assert!(matches!(a, Action::Choose(_)) && s.is_legal(a));
}

#[test]
fn game_starter_variant_has_survivor() {
    let d = Character::Silent.starter_deck_variant("game").unwrap();
    assert_eq!(d.iter().filter(|&&c| c == card("Survivor")).count(), 1);
    assert_eq!(d.iter().filter(|&&c| c == card("Silent Defend")).count(), 5);
    assert_eq!(Character::Silent.starter_deck_variant("default").unwrap(), Character::Silent.starter_deck());
    assert!(Character::Silent.starter_deck_variant("nope").is_none());
}
