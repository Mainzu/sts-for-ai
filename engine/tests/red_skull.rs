//! Red Skull as real Strength (docs/specs/red-skull-strength.md), against
//! the game's decompiled code (GitHub `aeubanks/sts`): `relics/RedSkull.java`
//! (battle start, `onBloodied`, `onNotBloodied`), `characters/AbstractPlayer.java`
//! ~1458 (`damage`: bloodied at HP <= max / 2), ~1529 (`heal`: not bloodied
//! above max / 2), ~1557 (combat start: bloodied from HP, no relic call).

use sts_engine::monsters::EncounterGroup;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::registry::{bind, load_pack, relics_named};
use sts_engine::*;

const RELICS: &str = include_str!("../../content/packs/act1-relics.json");
const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const TEST: &str = r#"{"version": 2, "cards": [
{"id": "RsHurt", "cost": 0, "type": "Skill", "effects": [{"LoseHp": 30}]},
{"id": "RsHeal", "cost": 0, "type": "Skill", "effects": [{"Heal": 30}]}
], "relics": [
{"id": "rs-pre-hurt", "rarity": "common", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"LoseHp": 10}]}]}
]}"#;

/// A fight and the card ids its binding gave each name.
struct Fight {
    s: CombatState,
    cards: Vec<(String, CardId)>,
}

/// The starter deck against a Jaw Worm, the player at `hp` of 80, with Red
/// Skull or none.
fn fight(hp: i16, skull: bool) -> Fight {
    fight_holding(hp, if skull { &["gen:Red Skull"] } else { &[] })
}

/// `fight` holding these relics, in order.
fn fight_holding(hp: i16, held: &[&str]) -> Fight {
    load_pack(RELICS).unwrap();
    load_pack(IRONCLAD).unwrap();
    load_pack(TEST).unwrap();
    let mut names: Vec<String> = starter_deck().iter().map(|&c| c.def().name.to_string()).collect();
    names.extend(["Bloodletting", "Heavy Blade", "Heavy Blade+", "gen:Limit Break", "gen:RsHurt", "gen:RsHeal"].map(String::from));
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let (ids, b) = bind(&refs).unwrap();
    let relics = relics_named(held).unwrap();
    let s = CombatState::new_with(Character::Ironclad, &ids, &b, hp, 80, &[K::JawWorm], EncounterGroup::Hallway, &relics, &mut Rng::new(5));
    Fight { s, cards: names.into_iter().zip(ids).collect() }
}

/// Plays `name` (put in hand) at the worm, with energy and the worm's block
/// reset so only the card counts.
fn play(f: &mut Fight, name: &str) {
    let c = f.cards.iter().find(|(n, _)| n == name).unwrap_or_else(|| panic!("{name} not in the deck")).1;
    let s = &mut f.s;
    s.hand.add(c, 1);
    s.player.energy = 3;
    s.monsters[0].block = 0;
    let target = if s.binding.def(c).targeted() { Some(0) } else { None };
    s.step(Action::Play { card: c, target }, &mut Rng::new(6)).unwrap();
}

fn strength(f: &Fight) -> i16 {
    f.s.player.powers.get(Power::Strength)
}

#[test]
fn combat_start_at_half_or_below() {
    // RedSkull.atBattleStart: Strength if the player starts bloodied
    // (AbstractPlayer ~1557: HP <= max HP / 2), queued after the opening draw.
    let f = fight(40, true);
    assert_eq!(f.s.stage, Stage::PlayerTurn);
    assert_eq!(f.s.hand.len(), 5, "the opening draw came first");
    assert_eq!(strength(&f), 3);
    assert_eq!(strength(&fight(41, true)), 0, "above half: none");
    assert_eq!(strength(&fight(40, false)), 0, "no relic: none");
}

#[test]
fn crossing_half_in_both_directions() {
    // AbstractPlayer.damage ~1458: onBloodied once, when HP reaches max / 2;
    // heal ~1529: onNotBloodied when HP rises above it.
    let mut f = fight(42, true);
    assert_eq!(strength(&f), 0);
    play(&mut f, "Bloodletting"); // 42 -> 39: bloodied
    assert_eq!((f.s.player.hp, strength(&f)), (39, 3));
    play(&mut f, "Bloodletting"); // 36: still bloodied, no change
    assert_eq!((f.s.player.hp, strength(&f)), (36, 3));
    play(&mut f, "gen:RsHeal"); // 66: not bloodied
    assert_eq!((f.s.player.hp, strength(&f)), (66, 0));
    play(&mut f, "gen:RsHurt"); // 36: bloodied again
    assert_eq!((f.s.player.hp, strength(&f)), (36, 3));
    // Starting bloodied, the first heal above half takes the start's 3 away.
    let mut f = fight(30, true);
    assert_eq!(strength(&f), 3);
    play(&mut f, "gen:RsHeal");
    assert_eq!((f.s.player.hp, strength(&f)), (60, 0));
}

#[test]
fn heavy_blade_and_limit_break_count_it() {
    // Real Strength (StrengthPower), so Heavy Blade's multiplier counts it:
    // 14 + 3 x 3, upgraded 14 + 5 x 3; Limit Break doubles it.
    for (card, dmg) in [("Heavy Blade", 14 + 3 * 3), ("Heavy Blade+", 14 + 5 * 3)] {
        let mut f = fight(40, true);
        let before = f.s.monsters[0].hp;
        play(&mut f, card);
        assert_eq!(before - f.s.monsters[0].hp, dmg, "{card}");
    }
    let mut f = fight(40, true);
    play(&mut f, "gen:Limit Break");
    assert_eq!(strength(&f), 6);
}

#[test]
fn no_double_count() {
    // RedSkull.atBattleStart gives Strength only while not `isActive`: a
    // crossing before it (here a pre-draw HP loss, 45 -> 35) already gave
    // the 3 through onBloodied. The relic's counter is `isActive`.
    let f = fight_holding(45, &["gen:rs-pre-hurt", "gen:Red Skull"]);
    assert_eq!((f.s.player.hp, strength(&f)), (35, 3));
    assert_eq!(f.s.player.relics.counter(1), 1);
    // Started at half: active from the start, a later crossing adds none,
    // the heal above half takes the 3, the next crossing gives it back.
    let mut f = fight(40, true);
    assert_eq!((strength(&f), f.s.player.relics.counter(0)), (3, 1));
    play(&mut f, "Bloodletting");
    assert_eq!(strength(&f), 3);
    play(&mut f, "gen:RsHeal");
    assert_eq!((strength(&f), f.s.player.relics.counter(0)), (0, 0));
    play(&mut f, "gen:RsHurt");
    assert_eq!((strength(&f), f.s.player.relics.counter(0)), (3, 1));
}
