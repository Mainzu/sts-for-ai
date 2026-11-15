//! The game's caps the engine used to lack
//! (docs/research/build-plans-2026-11-14/engine-caps.md, C1): block 999 for
//! every creature (`AbstractCreature.addBlock`), energy 999
//! (`EnergyPanel.addEnergy`), and power amounts within their row's `cap`
//! (Strength and Dexterity 999, Poison 9999).

use sts_engine::codec::{decode, encode};
use sts_engine::*;

fn fight(enc: Encounter) -> CombatState {
    let mut s = CombatState::new(&starter_deck(), 80, 80, enc, &mut Rng::new(3));
    s.player.energy = 3;
    s
}

fn play(s: &mut CombatState, name: &str, target: Option<u8>) {
    let c = CardId::from_name(name).unwrap();
    s.hand.add(c, 1);
    s.step(Action::Play { card: c, target }, &mut Rng::new(1)).unwrap();
}

#[test]
fn block_stops_at_999() {
    let mut s = fight(Encounter::Cultist);
    s.player.block = 995;
    play(&mut s, "Defend", None);
    assert_eq!(s.player.block, 999);
    play(&mut s, "Defend", None);
    assert_eq!(s.player.block, 999);
}

#[test]
fn energy_goes_past_127_and_stops_at_999() {
    let mut s = fight(Encounter::Cultist);
    s.player.energy = 126;
    play(&mut s, "Bloodletting", None);
    play(&mut s, "Bloodletting", None);
    assert_eq!(s.player.energy, 130);
    assert_eq!(decode(&encode(&s)), s);
    s.player.energy = 998;
    play(&mut s, "Bloodletting", None);
    assert_eq!(s.player.energy, 999);
    // Small values encode as before (a zigzag varint).
    let mut t = fight(Encounter::Cultist);
    t.player.energy = 3;
    assert_eq!(decode(&encode(&t)), t);
}

#[test]
fn powers_stop_at_their_cap() {
    let mut s = fight(Encounter::Cultist);
    s.player.powers.add(Power::Strength, 998);
    play(&mut s, "Flex", None);
    assert_eq!(s.player.powers.get(Power::Strength), 999);
    // Poison: 9999.
    let mut s = CombatState::new(&Character::Silent.starter_deck(), 70, 70, Encounter::Cultist, &mut Rng::new(3));
    s.player.energy = 3;
    s.monsters[0].powers.add(Power::Poison, 9997);
    play(&mut s, "Deadly Poison", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Poison), 9999);
}
