//! Vulnerable and NoBlock a monster applies skip their first round end only
//! once the player's turn has ended (the game's `turnHasEnded &&
//! isSourceMonster`; docs/research/build-plans-2026-11-14/monster-debuff-skip.md,
//! live run 77): Spore Cloud from a Fungi Beast the player's card kills ticks
//! at that round's end; one the monsters' turn kills (Poison, Thorns) is held
//! back. Weak and Frail from a monster skip whatever the turn.

use sts_engine::monsters::{fungi_beast, gremlin_nob};
use sts_engine::registry::{bind, load_pack, relics_named};
use sts_engine::*;

const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

/// Two Fungi Beasts (Spore Cloud 2) at `hp0` and 50 HP, both showing Grow,
/// the player at 80 HP with the starter deck and these pack relics.
fn fungi(hp0: i16, relics: &[&str]) -> CombatState {
    load_pack(RELICS).unwrap();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let deck: Vec<&str> = starter_deck().iter().map(|&c| c.def().name).collect();
    let (ids, b) = bind(&deck).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 80, 80, Encounter::TwoFungiBeasts, &relics_named(&refs).unwrap(), &mut Rng::new(5));
    for (m, hp) in s.monsters.iter_mut().zip([hp0, 50]) {
        m.hp = hp;
        m.moves[0] = fungi_beast::GROW;
    }
    s
}

/// Ends the turn: the monsters act, then the next turn starts.
fn next_turn(s: &mut CombatState) {
    let mut rng = Rng::new(12);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert_eq!(s.stage, Stage::PlayerTurn);
}

fn vulnerable(s: &CombatState) -> (i16, bool) {
    (s.player.powers.get(Power::Vulnerable), s.player.powers.just_applied(Power::Vulnerable))
}

#[test]
fn spore_cloud_from_a_card_kill_ticks() {
    // Run 77: the player's Strike kills a Fungi Beast while the other lives.
    let mut s = fungi(5, &[]);
    let strike = CardId::from_name("Strike").unwrap();
    s.hand.add(strike, 1);
    s.step(Action::Play { card: strike, target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert!(!s.monsters[0].alive());
    assert!(!s.turn_has_ended());
    assert_eq!(vulnerable(&s), (2, false));
    next_turn(&mut s);
    assert_eq!(vulnerable(&s), (1, false));
}

#[test]
fn spore_cloud_in_the_monsters_turn_is_held_back() {
    // Poison at the monsters' turn start kills it.
    let mut s = fungi(3, &[]);
    s.monsters[0].powers.add(Power::Poison, 5);
    next_turn(&mut s);
    assert!(!s.monsters[0].alive());
    assert_eq!(vulnerable(&s), (2, false));
    // Thorns on its Bite.
    let mut s = fungi(3, &[]);
    s.monsters[0].moves[0] = fungi_beast::BITE;
    s.player.powers.add(Power::Thorns, 5);
    next_turn(&mut s);
    assert!(!s.monsters[0].alive());
    assert_eq!(vulnerable(&s), (2, false));
}

#[test]
fn spore_cloud_at_the_players_turn_end_or_start_ticks() {
    // Combust at the player's turn end, before the discard: the game's
    // `turnHasEnded` is still false.
    let mut s = fungi(3, &[]);
    s.player.powers.add(Power::Combust, 1);
    s.player.powers.add(Power::CombustDamage, 5);
    next_turn(&mut s);
    assert!(!s.monsters[0].alive());
    assert_eq!(vulnerable(&s), (1, false));
    // Mercury Hourglass at the player's turn start: its damage resolves
    // after the game clears the flag.
    let mut s = fungi(3, &["Mercury Hourglass"]);
    next_turn(&mut s);
    assert!(!s.monsters[0].alive());
    assert_eq!(vulnerable(&s), (2, false));
    next_turn(&mut s);
    assert_eq!(vulnerable(&s), (1, false));
}

#[test]
fn a_monster_move_still_holds_vulnerable_back() {
    // Gremlin Nob's Skull Bash: Vulnerable 2, still 2 at the next turn.
    load_pack(RELICS).unwrap();
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::GremlinNob, &mut Rng::new(3));
    s.monsters[0].moves[0] = gremlin_nob::SKULL_BASH;
    next_turn(&mut s);
    assert_eq!(vulnerable(&s), (2, false));
    assert!(!s.turn_has_ended());
}
