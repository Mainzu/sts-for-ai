//! docs/specs/fight-vocabulary.md step 6: `DrawPicked` and a relic's pick.
//! Gambler's Brew (`potions/GamblersBrew.java`) and Gambling Chip
//! (`relics/GamblingChip.java`), both `GamblingChipAction`: discard any
//! number of cards from hand, then draw that many.

use sts_engine::agent::{greedy_action, Agent, SearchAgent};
use sts_engine::codec::{decode, encode};
use sts_engine::registry::{load_pack, potions_named, relics_named, Binding};
use sts_engine::search::{Heuristic, SearchConfig};
use sts_engine::*;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

fn load() {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
}

fn with_brew() -> CombatState {
    load();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &[], &mut Rng::new(3));
    s.give_potions(&potions_named(&["gen:Gambler's Brew"]).unwrap()).unwrap();
    s
}

fn with_relics(relics: &[&str], seed: u64) -> CombatState {
    load();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &relics_named(&refs).unwrap(), &mut Rng::new(seed))
}

/// The first `Choose` on offer.
fn choose_first(s: &mut CombatState) {
    let a = *s.legal_actions().iter().find(|a| matches!(a, Action::Choose(_))).expect("a card to pick");
    s.step(a, &mut Rng::new(5)).unwrap();
}

fn done(s: &mut CombatState) {
    s.step(Action::Done, &mut Rng::new(6)).unwrap();
}

#[test]
fn gamblers_brew() {
    // Discard 2 of 5, draw 2: 5 in hand, 2 more in the discard pile.
    let mut s = with_brew();
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    assert!(s.pick().is_some());
    choose_first(&mut s);
    choose_first(&mut s);
    assert_eq!(s.hand.len(), 3);
    done(&mut s);
    assert_eq!((s.hand.len(), s.discard().len(), s.draw().len()), (5, 2, 3));
    assert_eq!(s.stage, Stage::PlayerTurn);
    // Done with none picked draws none.
    let mut s = with_brew();
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    done(&mut s);
    assert_eq!((s.hand.len(), s.draw().len()), (5, 5));
    // An empty hand: nothing to pick, nothing drawn.
    let mut s = with_brew();
    s.set_discard(s.hand);
    s.hand = Hand::default();
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!((s.hand.len(), s.stage), (0, Stage::PlayerTurn));
}

#[test]
fn draw_picked_follows_a_pick() {
    load();
    let e = load_pack(r#"{"version": 2, "potions": [{"id": "dp-bad", "rarity": "common", "effects": [{"Draw": 1}, "DrawPicked"]}]}"#).unwrap_err();
    assert!(e.contains("right after a Pick"), "{e}");
    let e = load_pack(r#"{"version": 2, "powers": [{"id": "dp-bad-power", "hooks": [{"trigger": "OwnerTurnStartPostDraw", "condition": "Always", "effects": [{"Pick": {"kind": "DiscardFromHand", "n": 1, "exact": false}}]}]}]}"#)
        .unwrap_err();
    assert!(e.contains("can't run in a hook"), "a power's hook can't pick: {e}");
}

#[test]
fn gambling_chip() {
    // Turn 1, after Bag of Preparation's 2: the pick is open before any play.
    let mut s = with_relics(&["Bag of Preparation", "Gambling Chip"], 11);
    assert_eq!(s.hand.len(), 7);
    assert!(matches!(s.stage, Stage::RelicPick { pick: Some(_), .. }), "{:?}", s.stage);
    assert!(s.legal_actions().iter().all(|a| matches!(a, Action::Choose(_) | Action::Done)));
    assert_eq!(s.player.relics.counter(1), 1);
    // The open pick's state round-trips through the codec.
    assert!(decode(&encode(&s)) == s);
    choose_first(&mut s);
    choose_first(&mut s);
    choose_first(&mut s);
    assert!(decode(&encode(&s)) == s);
    done(&mut s);
    assert_eq!((s.hand.len(), s.discard().len()), (7, 3));
    assert_eq!(s.stage, Stage::PlayerTurn);
    // Turn 2 has none.
    let mut rng = Rng::new(12);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert_eq!(s.stage, Stage::PlayerTurn);
    // Without it, turn 1 is the player's at once; a relic-free state's
    // bytes don't carry the new stage tag.
    let plain = with_relics(&["Bag of Preparation"], 11);
    assert_eq!(plain.stage, Stage::PlayerTurn);
}

#[test]
fn agents_finish_a_fight_with_the_chip_and_the_brew() {
    for seed in 0..3 {
        let mut s = with_relics(&["Gambling Chip"], seed);
        s.give_potions(&potions_named(&["gen:Gambler's Brew"]).unwrap()).unwrap();
        let mut rng = Rng::new(seed);
        while !s.is_over() && s.turn <= 50 {
            let a = greedy_action(&s);
            s.step(a, &mut rng).unwrap();
        }
        assert!(s.is_over(), "greedy, seed {seed}");
        let mut s = with_relics(&["Gambling Chip"], seed);
        s.give_potions(&potions_named(&["gen:Gambler's Brew"]).unwrap()).unwrap();
        let mut agent = SearchAgent::new(Heuristic, SearchConfig::default());
        let mut agent_rng = Rng::new(seed ^ 0x5eed);
        while !s.is_over() && s.turn <= 50 {
            let a = agent.act(&s, &mut agent_rng);
            s.step(a, &mut rng).expect("the agent chose a legal action");
        }
        assert!(s.won(), "search, seed {seed}");
    }
}
