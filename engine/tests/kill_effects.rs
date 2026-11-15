//! Cards whose effect waits on a kill (`Condition::TargetDied`), against
//! the jar: Feed (`Feed.use`: FeedAction(m, damage, magicNumber 3, +1
//! upgraded); `FeedAction.update` deals the damage, then, when the target
//! `isDying || currentHealth <= 0`, is not `halfDead` and has no `Minion`
//! power, `player.increaseMaxHp(n, true)`: max HP up by n and `heal(n)`,
//! in the same action, so before `endBattle` when it wins the fight).

use sts_engine::registry::{bind, load_pack, relics_named};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

/// A combat with the pack cards `deck` all in hand, the pack relics
/// `relics`, no combat-end heal, 10 energy, 50 of 80 HP, empty piles,
/// every monster at 100 HP with no block or powers.
fn setup(deck: &[&str], relics: &[&str], enc: Encounter) -> (CombatState, Vec<CardId>) {
    load_pack(PACK).unwrap();
    load_pack(RELICS).unwrap();
    let names: Vec<String> = deck.iter().map(|c| format!("gen:{c}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let (ids, b) = bind(&refs).unwrap();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, enc, &relics_named(&refs).unwrap(), &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 10;
    s.player.hp = 50;
    s.win_heal = 0;
    for m in s.monsters.iter_mut().filter(|m| m.alive()) {
        m.hp = 100;
        m.max_hp = 100;
        m.block = 0;
        m.powers = Default::default();
    }
    (s, ids)
}

fn play(s: &mut CombatState, card: CardId) {
    s.step(Action::Play { card, target: Some(0) }, &mut Rng::new(1)).unwrap();
}

#[test]
fn feed_without_a_kill_only_deals_damage() {
    for (name, dmg) in [("Feed", 10), ("Feed+", 12)] {
        let (mut s, ids) = setup(&[name], &[], Encounter::JawWorm);
        play(&mut s, ids[0]);
        assert_eq!(s.monsters[0].hp, 100 - dmg, "{name}");
        assert_eq!((s.player.hp, s.player.max_hp), (50, 80), "{name}");
    }
}

#[test]
fn feed_kill_raises_max_hp_and_heals_as_much() {
    for (name, n) in [("Feed", 3), ("Feed+", 4)] {
        let (mut s, ids) = setup(&[name], &[], Encounter::SmallSlimes);
        s.monsters[0].hp = 5;
        play(&mut s, ids[0]);
        assert!(!s.monsters[0].alive() && !s.is_over(), "{name}");
        assert_eq!((s.player.hp, s.player.max_hp), (50 + n, 80 + n), "{name}");
        assert_eq!(s.exhaust().count(ids[0]), 1, "{name}: exhausts");
    }
}

#[test]
fn feed_blocked_short_of_the_kill_gains_nothing() {
    let (mut s, ids) = setup(&["Feed"], &[], Encounter::SmallSlimes);
    s.monsters[0].hp = 5;
    s.monsters[0].block = 6;
    play(&mut s, ids[0]);
    assert_eq!(s.monsters[0].hp, 1);
    assert_eq!((s.player.hp, s.player.max_hp), (50, 80));
}

#[test]
fn feed_kill_that_wins_raises_max_hp_before_the_combat_end_relics() {
    // At 40 of 80, Meat on the Bone would heal 12; Feed's kill first makes
    // it 43 of 83, above half, so the game's `onVictory` check fails.
    let (mut s, ids) = setup(&["Feed"], &["Meat on the Bone"], Encounter::JawWorm);
    s.player.hp = 40;
    s.monsters[0].hp = 5;
    play(&mut s, ids[0]);
    assert!(s.won());
    assert_eq!((s.player.hp, s.player.max_hp), (43, 83));
}

#[test]
fn magic_flower_scales_feeds_heal_not_its_max_hp() {
    // `increaseMaxHp` heals through `onPlayerHeal`: 3 becomes round(4.5) = 5,
    // also on the kill that wins.
    for enc in [Encounter::SmallSlimes, Encounter::JawWorm] {
        let (mut s, ids) = setup(&["Feed"], &["Magic Flower"], enc);
        s.monsters[0].hp = 5;
        play(&mut s, ids[0]);
        assert_eq!((s.player.hp, s.player.max_hp), (55, 83), "{enc:?}");
    }
}
