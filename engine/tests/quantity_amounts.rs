//! Block and Apply amounts that read a quantity
//! (docs/specs/quantity-amounts.md, building block C4): `BlockOf` and
//! `ApplyOf`, with Entrench and Limit Break from
//! `content/packs/act1-ironclad.json`.

use sts_engine::cards::CardType;
use sts_engine::effects::{Amount, Effect, Quantity, Target};
use sts_engine::registry::{bind, card_json, load_pack};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");

/// (name, cost, cost upgraded, exhaust, exhaust upgraded), from
/// sts_lightspeed's card table and `doesCardExhaust` (spec "Outside
/// assumptions"); both are Skills.
const SOURCE: [(&str, i8, i8, bool, bool); 2] = [("Entrench", 2, 1, false, false), ("Limit Break", 1, 1, true, false)];

fn gen(name: &str) -> String {
    format!("gen:{name}")
}

/// A combat against a Jaw Worm at 100 HP with the pack card `name` alone
/// in hand, 10 energy, empty piles. Returns the state and the card's id.
fn setup(name: &str) -> (CombatState, CardId) {
    load_pack(PACK).unwrap();
    let (ids, b) = bind(&[&gen(name)]).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 10;
    s.player.block = 0;
    s.player.powers = Default::default();
    let m = &mut s.monsters[0];
    m.hp = 100;
    m.max_hp = 100;
    m.block = 0;
    m.powers = Default::default();
    (s, ids[0])
}

fn play(s: &mut CombatState, card: CardId) {
    s.apply_action(Action::Play { card, target: None }).unwrap();
}

#[test]
fn every_entry_loads_as_the_source() {
    load_pack(PACK).unwrap();
    for (name, cost, cost_up, exhaust, exhaust_up) in SOURCE {
        for (n, c, x) in [(name.to_string(), cost, exhaust), (format!("{name}+"), cost_up, exhaust_up)] {
            let (ids, b) = bind(&[&gen(&n)]).unwrap();
            let d = b.def(ids[0]);
            assert_eq!((d.cost(), d.ty, d.exhaust, d.ethereal), (c, CardType::Skill, x, false), "{n}");
            assert!(!d.targeted(), "{n}");
        }
    }
}

#[test]
fn block_of_doubles_block() {
    for name in ["Entrench", "Entrench+"] {
        // Raw block: Dexterity and Frail don't apply.
        let (mut s, card) = setup(name);
        s.player.block = 7;
        s.player.powers.add(Power::Dexterity, 2);
        s.player.powers.add(Power::Frail, 1);
        play(&mut s, card);
        assert_eq!(s.player.block, 14, "{name}");
        let (mut s, card) = setup(name);
        play(&mut s, card);
        assert_eq!(s.player.block, 0, "{name}");
    }
}

#[test]
fn block_of_gains_nothing_from_a_negative_amount() {
    let card = "{\"version\": 1, \"cards\": [{\"id\": \"c4_neg\", \"cost\": 0, \"type\": \"Skill\", \
        \"effects\": [{\"BlockOf\": {\"base\": -3, \"k\": -1, \"of\": \"OwnBlock\"}}]}]}";
    load_pack(card).unwrap();
    let (ids, b) = bind(&[&gen("c4_neg")]).unwrap();
    let mut t = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    t.hand = Hand::from_cards(&ids);
    t.player.block = 5;
    t.player.energy = 3;
    play(&mut t, ids[0]);
    assert_eq!(t.player.block, 5);
}

#[test]
fn apply_of_doubles_strength() {
    for name in ["Limit Break", "Limit Break+"] {
        for (before, after) in [(3, 6), (-2, -4)] {
            let (mut s, card) = setup(name);
            s.player.powers.add(Power::Strength, before);
            play(&mut s, card);
            assert_eq!(s.player.powers.get(Power::Strength), after, "{name} {before}");
        }
        // Zero stays zero: no power entry at all.
        let (mut s, card) = setup(name);
        play(&mut s, card);
        assert_eq!(s.player.powers.iter().count(), 0, "{name}");
        // A negative doubling is a debuff: Artifact cancels it.
        let (mut s, card) = setup(name);
        s.player.powers.add(Power::Strength, -2);
        s.player.powers.add(Power::Artifact, 1);
        play(&mut s, card);
        assert_eq!((s.player.powers.get(Power::Artifact), s.player.powers.get(Power::Strength)), (0, -2), "{name}");
    }
}

#[test]
fn limit_break_exhausts_unless_upgraded() {
    for (name, exhausted) in [("Limit Break", true), ("Limit Break+", false)] {
        let (mut s, card) = setup(name);
        play(&mut s, card);
        assert_eq!((s.exhaust().count(card), s.discard().count(card)), (exhausted as u8, !exhausted as u8), "{name}");
    }
}

#[test]
fn scaled_and_target() {
    let a = Amount::of(1, 2, Quantity::OwnBlock);
    let b = Effect::BlockOf(a);
    assert_eq!(b.scaled(3), Effect::BlockOf(Amount::of(3, 6, Quantity::OwnBlock)));
    assert_eq!(b.target(), None);
    let ap = Effect::ApplyOf { power: Power::Strength, amount: Amount::of(0, 1, Quantity::OwnStrength), target: Target::Me };
    assert_eq!(
        ap.scaled(2),
        Effect::ApplyOf { power: Power::Strength, amount: Amount::of(0, 2, Quantity::OwnStrength), target: Target::Me }
    );
    assert_eq!(ap.target(), Some(Target::Me));
    assert!(!b.heals() && !ap.heals());
}

#[test]
fn quantity_effects_round_trip() {
    // The pack's entries, written and read back.
    load_pack(PACK).unwrap();
    for name in ["Entrench", "Entrench+", "Limit Break", "Limit Break+"] {
        let (ids, b) = bind(&[&gen(name)]).unwrap();
        let d = b.def(ids[0]);
        let rt = format!("rt_c4_{}", name.replace(' ', "_").replace('+', "_up"));
        let entry = card_json(&rt, d).unwrap();
        load_pack(&format!("{{\"version\": 1, \"cards\": [{entry}]}}")).unwrap_or_else(|e| panic!("{name}: {e}\n{entry}"));
        let (ids2, b2) = bind(&[&gen(&rt)]).unwrap();
        let d2 = b2.def(ids2[0]);
        assert_eq!((d2.effects, d2.cost(), d2.exhaust), (d.effects, d.cost(), d.exhaust), "{name}");
    }
    // One card holding both, with a constant amount and other quantities.
    let effects = "{\"BlockOf\": 4}, {\"BlockOf\": {\"base\": 2, \"k\": 3, \"of\": {\"HandCards\": {\"except\": \"Attack\"}}}}, \
        {\"ApplyOf\": {\"power\": \"Vulnerable\", \"amount\": {\"base\": 1, \"k\": 1, \"of\": \"EnergySpent\"}, \"target\": \"Opponent\"}}, \
        {\"ApplyOf\": {\"power\": \"Weak\", \"amount\": 2, \"target\": \"AllOpponents\"}}";
    load_pack(&format!("{{\"version\": 1, \"cards\": [{{\"id\": \"c4_both\", \"cost\": 1, \"type\": \"Skill\", \"effects\": [{effects}]}}]}}"))
        .unwrap();
    let (ids, b) = bind(&[&gen("c4_both")]).unwrap();
    let d = b.def(ids[0]);
    assert_eq!(
        d.effects,
        [
            Effect::BlockOf(Amount::constant(4)),
            Effect::BlockOf(Amount::of(2, 3, Quantity::HandCards { except: Some(CardType::Attack) })),
            Effect::ApplyOf { power: Power::Vulnerable, amount: Amount::of(1, 1, Quantity::EnergySpent), target: Target::Opponent },
            Effect::ApplyOf { power: Power::Weak, amount: Amount::constant(2), target: Target::AllOpponents },
        ]
    );
    let entry = card_json("c4_both_rt", d).unwrap();
    load_pack(&format!("{{\"version\": 1, \"cards\": [{entry}]}}")).unwrap_or_else(|e| panic!("{e}\n{entry}"));
    let (ids2, b2) = bind(&[&gen("c4_both_rt")]).unwrap();
    assert_eq!(b2.def(ids2[0]).effects, d.effects);
}
