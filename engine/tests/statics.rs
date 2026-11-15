//! Static modifiers as data (docs/specs/static-modifiers.md): the static
//! rows equal the hard-coded fast path, Accuracy and an HP-threshold static
//! (`OwnerHpAtMostHalf`, a pack power: Red Skull was it until it became real
//! Strength, docs/specs/red-skull-strength.md), and the debuff countdowns as
//! `RoundEnd` hooks.

mod common;

use common::*;
use sts_engine::hooks::{hooks, statics, Trigger};
use sts_engine::registry::{bind_power, load_pack};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::state::{Stage, Who, MAX_MONSTERS};
use sts_engine::*;

/// A pack power with Red Skull's old static: +1 damage dealt per hit per
/// stack while its owner's HP is at most half.
const HALF_PACK: &str = r#"{"version": 2, "powers": [
{"id": "StaticsHalfHp", "debuff": false, "hooks": [], "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 1, "num": 1, "den": 1, "condition": "OwnerHpAtMostHalf"}], "replacements": []}
]}"#;

/// `s` with the HP-threshold pack power bound; returns that power.
fn bind_half(s: &mut CombatState) -> Power {
    load_pack(HALF_PACK).unwrap();
    let (b, p) = bind_power(&s.binding, "StaticsHalfHp").unwrap();
    s.binding = b;
    p
}

/// A small deterministic generator for the powers the check varies.
fn pick(rng: &mut Rng, lo: i16, hi: i16) -> i16 {
    lo + rng.below((hi - lo + 1) as u32) as i16
}

#[test]
fn statics_table_matches_fast_path() {
    let mut rng = Rng::new(11);
    let (mut checked, mut block_checked) = (0, 0);
    let encs = [Encounter::JawWorm, Encounter::Cultist, Encounter::TwoLouse, Encounter::GremlinNob, Encounter::SlimeBoss];
    for seed in 0..200u64 {
        let mut s = fresh(encs[seed as usize % encs.len()], seed);
        let half = bind_half(&mut s);
        for step in 0..30 {
            if s.is_over() {
                break;
            }
            let mut t = s.clone();
            for who in [Who::Player].into_iter().chain((0..MAX_MONSTERS as u8).map(Who::Monster)) {
                let p = match who {
                    Who::Player => &mut t.player.powers,
                    Who::Monster(i) => &mut t.monsters[i as usize].powers,
                };
                for (power, lo, hi) in [
                    (Power::Strength, -3, 5),
                    (Power::Dexterity, -2, 3),
                    (Power::Weak, 0, 1),
                    (Power::Vulnerable, 0, 1),
                    (Power::Frail, 0, 1),
                    (Power::Accuracy, 0, 4),
                    (half, 0, 3),
                ] {
                    let n = pick(&mut rng, lo, hi);
                    p.add(power, n - p.get(power));
                }
            }
            t.player.hp = pick(&mut rng, 1, t.player.max_hp);
            if step % 3 == 0 {
                t.stage = Stage::PlayingCard { card: card(if step % 2 == 0 { "Shiv" } else { "Strike" }), target: Some(0), next: 0, hit: 0, x: 0, more: Default::default() };
            }
            for slot in t.living_slots().collect::<Vec<_>>() {
                for base in [0, 1, 5, 6, 13] {
                    let m = Who::Monster(slot as u8);
                    for (a, b) in [(Who::Player, m), (m, Who::Player)] {
                        assert_eq!(t.attack_damage(a, b, base), t.interpret_attack_damage(a, b, base), "{a:?}->{b:?} base {base} seed {seed}");
                        checked += 1;
                    }
                }
            }
            for name in ["Defend", "Defend+"] {
                let mut u = t.clone();
                u.stage = Stage::PlayerTurn;
                u.pending = None;
                u.hand = Hand::from_cards(&[card(name)]);
                u.player.energy = 3;
                u.player.block = 0;
                let want = u.interpret_block(if name == "Defend" { 5 } else { 8 });
                play(&mut u, name, None);
                assert_eq!(u.player.block, want, "{name} seed {seed}");
                block_checked += 1;
            }
            let acts = s.legal_actions();
            let a = acts[rng.below(acts.len() as u32) as usize];
            s.step(a, &mut rng).unwrap();
        }
    }
    assert!(checked > 20_000 && block_checked > 2_000, "{checked} {block_checked}");
}

#[test]
fn accuracy_adds_to_shivs_only() {
    let mut s = vs(&[K::JawWorm], &["Accuracy", "Shiv", "Strike"], Some(100));
    play(&mut s, "Accuracy", None);
    assert_eq!(s.player.powers.get(Power::Accuracy), 4);
    play(&mut s, "Shiv", Some(0));
    assert_eq!(s.monsters[0].hp, 92);
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].hp, 86);
    // With Strength 2 and Weak: floor((4 + 4 + 2) × 3/4) = 7.
    let mut s = vs(&[K::JawWorm], &["Shiv"], Some(100));
    s.player.powers.add(Power::Accuracy, 4);
    s.player.powers.add(Power::Strength, 2);
    s.player.powers.add(Power::Weak, 1);
    play(&mut s, "Shiv", Some(0));
    assert_eq!(s.monsters[0].hp, 93);
    assert!(sts_engine::card_sets::get("proving").unwrap().contains(&card("Accuracy")) && card("Shiv+").def().has_tag(sts_engine::cards::Tag::Shiv));
}

#[test]
fn half_hp_static_adds_at_half_hp() {
    for (hp, dmg) in [(40, 9), (41, 6)] {
        let mut s = vs(&[K::JawWorm], &["Strike"], Some(100));
        let half = bind_half(&mut s);
        s.player.max_hp = 80;
        s.player.hp = hp;
        s.player.powers.add(half, 3);
        play(&mut s, "Strike", Some(0));
        assert_eq!(s.monsters[0].hp, 100 - dmg, "hp {hp}");
    }
}

#[test]
fn vulnerable_weak_frail_have_round_end_hooks() {
    for p in [Power::Vulnerable, Power::Weak, Power::Frail] {
        assert!(hooks(p).iter().any(|h| h.trigger == Trigger::RoundEnd), "{p:?}");
        assert_eq!(statics(p).len(), 1, "{p:?}");
    }
    for p in [Power::Strength, Power::Dexterity] {
        assert!(hooks(p).is_empty() && statics(p).len() == 1, "{p:?}");
    }
}

#[test]
fn countdowns_are_round_end_hooks() {
    // Applied by the player: one stack off at the round's end.
    let mut s = vs(&[K::JawWorm], &["Bash"], Some(100));
    play(&mut s, "Bash", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 2);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 1);
    // Applied by a monster during its turn: skips that round, then counts down.
    let mut s = vs(&[K::JawWorm], &[], Some(100));
    s.player.powers.add(Power::Weak, 2);
    s.player.powers.set_just_applied(Power::Weak);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Weak), 2);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Weak), 1);
}
