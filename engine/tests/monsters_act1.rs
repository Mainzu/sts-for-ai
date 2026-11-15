//! Act 1 monsters beyond step 1: values, move rules and powers, from
//! slaythespire.wiki.gg (Ascension 0).

mod common;
use common::*;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::monsters::*;
use sts_engine::*;

/// The player just ends turns: no cards, lots of HP. Monster 0 is `kind`
/// at `hp` doing `history[0]` next.
fn doing(kind: K, hp: i16, history: [MoveId; 2]) -> CombatState {
    let mut s = vs(&[kind], &[], Some(hp));
    s.player.hp = 500;
    s.player.max_hp = 500;
    s.monsters[0].moves = history;
    s
}

fn hp_loss_on_end_turn(s: &mut CombatState) -> i16 {
    let before = s.player.hp;
    end_turn(s);
    before - s.player.hp
}

fn sorted_dist(kind: K, history: [MoveId; 2]) -> Vec<(MoveId, f64)> {
    let mut d = doing(kind, 50, history).move_distribution(0);
    d.sort_by_key(|&(m, _)| m);
    d
}

fn approx(d: &[(MoveId, f64)], expect: &[(MoveId, f64)]) {
    assert_eq!(d.len(), expect.len(), "{d:?} vs {expect:?}");
    for ((m, p), (em, ep)) in d.iter().zip(expect) {
        assert_eq!(m, em, "{d:?} vs {expect:?}");
        assert!((p - ep).abs() < 1e-9, "{d:?} vs {expect:?}");
    }
}

// ---- HP ranges and setup ----

#[test]
fn hp_ranges_and_rolled_values() {
    let ranges = [
        (K::RedLouse, 10, 15),
        (K::GreenLouse, 11, 17),
        (K::AcidSlimeS, 8, 12),
        (K::AcidSlimeM, 28, 32),
        (K::AcidSlimeL, 65, 69),
        (K::SpikeSlimeS, 10, 14),
        (K::SpikeSlimeM, 28, 32),
        (K::SpikeSlimeL, 64, 70),
        (K::FungiBeast, 22, 28),
        (K::Looter, 44, 48),
        (K::GremlinNob, 82, 86),
        (K::Lagavulin, 109, 111),
        (K::Sentry, 38, 42),
        (K::SlimeBoss, 140, 140),
    ];
    for (kind, lo, hi) in ranges {
        assert_eq!((kind.def().hp_min, kind.def().hp_max), (lo, hi), "{}", kind.def().name);
    }
    let mut seen_hp = std::collections::HashSet::new();
    for seed in 0..2000 {
        let s = fresh(Encounter::ThreeLouse, seed);
        for m in &s.monsters[..3] {
            let (lo, hi) = if m.kind == K::RedLouse { (10, 15) } else { (11, 17) };
            assert!((lo..=hi).contains(&m.hp));
            assert!((5..=7).contains(&m.rolled_damage), "bite {}", m.rolled_damage);
            assert!((3..=7).contains(&m.powers.get(Power::CurlUp)));
            seen_hp.insert((m.kind, m.hp, m.rolled_damage, m.powers.get(Power::CurlUp)));
        }
        for &(enc, kinds) in &[
            (Encounter::GremlinNob, &[K::GremlinNob][..]),
            (Encounter::Lagavulin, &[K::Lagavulin][..]),
            (Encounter::SlimeBoss, &[K::SlimeBoss][..]),
            (Encounter::ThreeSentries, &[K::Sentry, K::Sentry, K::Sentry][..]),
        ] {
            let s = fresh(enc, seed);
            for (i, &k) in kinds.iter().enumerate() {
                let m = &s.monsters[i];
                assert_eq!(m.kind, k);
                assert!((k.def().hp_min..=k.def().hp_max).contains(&m.hp));
            }
        }
    }
    // Every combination of the extremes shows up.
    for k in [K::RedLouse, K::GreenLouse] {
        for bite in [5, 7] {
            for curl in [3, 7] {
                assert!(seen_hp.iter().any(|&(kk, _, b, c)| kk == k && b == bite && c == curl));
            }
        }
    }
}

#[test]
fn encounters_roll_their_listed_monsters() {
    use std::collections::HashSet;
    let medium = [K::AcidSlimeM, K::SpikeSlimeM];
    let louse = [K::RedLouse, K::GreenLouse];
    for enc in Encounter::ALL {
        let mut seen = HashSet::new();
        for seed in 0..200 {
            let kinds = enc.roll_monsters(&mut Rng::new(seed));
            assert!(!kinds.is_empty() && kinds.len() <= 5);
            seen.insert(kinds.clone());
            match enc {
                Encounter::TwoLouse => assert!(kinds.len() == 2 && kinds.iter().all(|k| louse.contains(k))),
                Encounter::ThreeLouse => assert!(kinds.len() == 3 && kinds.iter().all(|k| louse.contains(k))),
                Encounter::SmallSlimes => assert!(
                    kinds == [K::SpikeSlimeM, K::AcidSlimeS] || kinds == [K::AcidSlimeM, K::SpikeSlimeS]
                ),
                Encounter::LargeSlime => assert!(kinds == [K::AcidSlimeL] || kinds == [K::SpikeSlimeL]),
                Encounter::ExordiumThugs => {
                    assert!(louse.contains(&kinds[0]) || medium.contains(&kinds[0]));
                    assert!([K::Cultist, K::Looter].contains(&kinds[1]));
                }
                Encounter::ExordiumWildlife => {
                    assert!([K::FungiBeast, K::JawWorm].contains(&kinds[0]));
                    assert!(louse.contains(&kinds[1]) || medium.contains(&kinds[1]));
                }
                _ => {}
            }
        }
        let variants = match enc {
            Encounter::SmallSlimes | Encounter::LargeSlime => 2,
            Encounter::TwoLouse => 4,
            Encounter::ThreeLouse | Encounter::ExordiumThugs | Encounter::ExordiumWildlife => 8,
            _ => 1,
        };
        assert_eq!(seen.len(), variants, "{}", enc.name());
        assert_eq!(Encounter::from_name(enc.name()), Some(enc));
    }
}

// ---- Lice ----

#[test]
fn louse_bite_uses_rolled_damage_grow_and_spit_web() {
    let mut s = doing(K::RedLouse, 15, [louse::BITE, NO_MOVE]);
    s.monsters[0].rolled_damage = 6;
    assert_eq!(hp_loss_on_end_turn(&mut s), 6);
    let mut s = doing(K::RedLouse, 15, [louse::OTHER, NO_MOVE]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 3);
    let mut s = doing(K::GreenLouse, 15, [louse::OTHER, NO_MOVE]);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Weak), 2);
}

#[test]
fn louse_odds_75_bite_25_other_no_move_three_times() {
    for kind in [K::RedLouse, K::GreenLouse] {
        approx(&sorted_dist(kind, [NO_MOVE, NO_MOVE]), &[(louse::BITE, 0.75), (louse::OTHER, 0.25)]);
        approx(&sorted_dist(kind, [louse::BITE, louse::OTHER]), &[(louse::BITE, 0.75), (louse::OTHER, 0.25)]);
        approx(&sorted_dist(kind, [louse::BITE, louse::BITE]), &[(louse::OTHER, 1.0)]);
        approx(&sorted_dist(kind, [louse::OTHER, louse::OTHER]), &[(louse::BITE, 1.0)]);
    }
}

#[test]
fn curl_up_blocks_after_the_first_unblocked_nonlethal_hit_once() {
    // Twin Strike: both hits land before the Curl Up block (queued after the card).
    let mut s = vs(&[K::RedLouse], &["Twin Strike", "Strike"], Some(15));
    s.monsters[0].powers.add(Power::CurlUp, 4);
    play(&mut s, "Twin Strike", Some(0));
    assert_eq!(s.monsters[0].hp, 5);
    assert_eq!(s.monsters[0].block, 4);
    assert_eq!(s.monsters[0].powers.get(Power::CurlUp), 0);
    play(&mut s, "Strike", Some(0));
    assert_eq!((s.monsters[0].block, s.monsters[0].hp), (0, 3)); // no second curl
    // Fully blocked damage doesn't trigger it.
    let mut s = vs(&[K::GreenLouse], &["Strike"], Some(15));
    s.monsters[0].powers.add(Power::CurlUp, 4);
    s.monsters[0].block = 10;
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::CurlUp), 4);
    // A lethal hit doesn't either (and the combat is won).
    let mut s = vs(&[K::GreenLouse], &["Strike"], Some(6));
    s.monsters[0].powers.add(Power::CurlUp, 4);
    play(&mut s, "Strike", Some(0));
    assert!(s.won());
}

// ---- Slimes ----

#[test]
fn acid_slime_moves() {
    for (kind, spit, slimed, tackle, weak) in [(K::AcidSlimeM, 7, 1, 10, 1), (K::AcidSlimeL, 11, 2, 16, 2)] {
        let mut s = doing(kind, 60, [acid_slime::CORROSIVE_SPIT, NO_MOVE]);
        assert_eq!(hp_loss_on_end_turn(&mut s), spit);
        assert_eq!(s.discard().count(card("Slimed")) + s.hand.count(card("Slimed")) + s.draw().count(card("Slimed")), slimed);
        let mut s = doing(kind, 60, [acid_slime::TACKLE, NO_MOVE]);
        assert_eq!(hp_loss_on_end_turn(&mut s), tackle);
        let mut s = doing(kind, 60, [acid_slime::LICK, NO_MOVE]);
        assert_eq!(hp_loss_on_end_turn(&mut s), 0);
        assert_eq!(s.player.powers.get(Power::Weak), weak);
    }
    let mut s = doing(K::AcidSlimeS, 10, [acid_slime::S_TACKLE, NO_MOVE]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 3);
    let mut s = doing(K::AcidSlimeS, 10, [acid_slime::S_LICK, NO_MOVE]);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Weak), 1);
}

#[test]
fn acid_slime_odds() {
    use acid_slime::*;
    for kind in [K::AcidSlimeM, K::AcidSlimeL] {
        approx(&sorted_dist(kind, [NO_MOVE, NO_MOVE]), &[(CORROSIVE_SPIT, 0.3), (TACKLE, 0.4), (LICK, 0.3)]);
        // No Tackle twice in a row.
        approx(&sorted_dist(kind, [TACKLE, NO_MOVE]), &[(CORROSIVE_SPIT, 0.3 + 0.2), (LICK, 0.3 + 0.2)]);
        // No third Spit or Lick.
        approx(&sorted_dist(kind, [CORROSIVE_SPIT, CORROSIVE_SPIT]), &[(TACKLE, 0.4 + 0.15), (LICK, 0.3 + 0.15)]);
        approx(&sorted_dist(kind, [LICK, LICK]), &[(CORROSIVE_SPIT, 0.3 + 0.12), (TACKLE, 0.4 + 0.18)]);
    }
    // Small: either first, then alternates.
    approx(&sorted_dist(K::AcidSlimeS, [NO_MOVE, NO_MOVE]), &[(S_LICK, 0.5), (S_TACKLE, 0.5)]);
    approx(&sorted_dist(K::AcidSlimeS, [S_LICK, NO_MOVE]), &[(S_TACKLE, 1.0)]);
    approx(&sorted_dist(K::AcidSlimeS, [S_TACKLE, S_LICK]), &[(S_LICK, 1.0)]);
}

#[test]
fn spike_slime_moves_and_odds() {
    use spike_slime::*;
    for (kind, dmg, slimed, frail) in [(K::SpikeSlimeM, 8, 1, 1), (K::SpikeSlimeL, 16, 2, 2)] {
        let mut s = doing(kind, 60, [FLAME_TACKLE, NO_MOVE]);
        assert_eq!(hp_loss_on_end_turn(&mut s), dmg);
        assert_eq!(s.created as u8, slimed);
        let mut s = doing(kind, 60, [LICK, NO_MOVE]);
        end_turn(&mut s);
        assert_eq!(s.player.powers.get(Power::Frail), frail);
        approx(&sorted_dist(kind, [NO_MOVE, NO_MOVE]), &[(FLAME_TACKLE, 0.3), (LICK, 0.7)]);
        approx(&sorted_dist(kind, [FLAME_TACKLE, FLAME_TACKLE]), &[(LICK, 1.0)]);
        approx(&sorted_dist(kind, [LICK, LICK]), &[(FLAME_TACKLE, 1.0)]);
    }
    let mut s = doing(K::SpikeSlimeS, 12, [S_TACKLE, NO_MOVE]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 5);
    approx(&sorted_dist(K::SpikeSlimeS, [S_TACKLE, S_TACKLE]), &[(S_TACKLE, 1.0)]);
}

#[test]
fn large_slime_splits_at_half_hp_into_two_mediums_with_its_hp() {
    for (kind, child, split) in [(K::AcidSlimeL, K::AcidSlimeM, acid_slime::SPLIT), (K::SpikeSlimeL, K::SpikeSlimeM, spike_slime::SPLIT)] {
        let mut s = vs(&[kind], &["Strike", "Strike", "Strike"], Some(66));
        s.player.hp = 500;
        s.monsters[0].moves = [0, NO_MOVE];
        play(&mut s, "Strike", Some(0)); // 60
        assert_ne!(s.monsters[0].intent(), split);
        play(&mut s, "Strike", Some(0)); // 54
        play(&mut s, "Strike", Some(0)); // 48: not yet half
        assert_ne!(s.monsters[0].intent(), split);
        s.monsters[0].hp = 34;
        s.hand = Hand::from_cards(&[card("Strike")]);
        s.player.energy = 1;
        play(&mut s, "Strike", Some(0)); // 28 <= 33: split
        assert_eq!(s.monsters[0].intent(), split);
        let before = s.player.hp;
        end_turn(&mut s);
        assert_eq!(s.player.hp, before, "splitting does no damage");
        for slot in [0, 1] {
            let m = &s.monsters[slot];
            assert_eq!((m.kind, m.hp, m.max_hp), (child, 28, 28));
            assert_ne!(m.intent(), NO_MOVE, "children roll a move");
        }
    }
}

#[test]
fn split_children_dont_act_on_the_turn_they_appear() {
    let mut s = doing(K::AcidSlimeL, 30, [acid_slime::SPLIT, acid_slime::TACKLE]);
    s.monsters[0].max_hp = 69;
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert!(s.monsters[0].alive() && s.monsters[1].alive());
}

#[test]
fn lethal_damage_does_not_split() {
    let mut s = vs(&[K::SpikeSlimeL], &["Strike"], Some(6));
    s.monsters[0].max_hp = 64;
    s.monsters[0].moves = [spike_slime::LICK, NO_MOVE];
    play(&mut s, "Strike", Some(0));
    assert!(s.won());
}

// ---- Fungi Beast ----

#[test]
fn fungi_beast_moves_odds_and_spore_cloud() {
    use fungi_beast::*;
    let mut s = doing(K::FungiBeast, 25, [BITE, NO_MOVE]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 6);
    let mut s = doing(K::FungiBeast, 25, [GROW, NO_MOVE]);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 3);
    approx(&sorted_dist(K::FungiBeast, [NO_MOVE, NO_MOVE]), &[(BITE, 0.6), (GROW, 0.4)]);
    approx(&sorted_dist(K::FungiBeast, [BITE, BITE]), &[(GROW, 1.0)]);
    approx(&sorted_dist(K::FungiBeast, [GROW, BITE]), &[(BITE, 1.0)]);
    // Spore Cloud 2: killing it applies 2 Vulnerable. Applied in the
    // player's turn (the game's `turnHasEnded` false), it ticks at that
    // round's end (live run 77).
    let mut s = vs(&[K::FungiBeast, K::FungiBeast], &["Strike"], Some(6));
    assert_eq!(s.monsters[0].powers.get(Power::SporeCloud), 2);
    s.monsters[1].hp = 100;
    s.monsters[1].max_hp = 100;
    s.monsters[1].moves = [GROW, NO_MOVE];
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.player.powers.get(Power::Vulnerable), 2);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Vulnerable), 1, "applied in the player's turn: ticks at the round's end");
}

// ---- Looter ----

#[test]
fn looter_mugs_twice_then_lunges_or_smoke_bombs_then_escapes() {
    use looter::*;
    let mut s = doing(K::Looter, 46, [MUG, NO_MOVE]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 10);
    assert_eq!(s.monsters[0].intent(), MUG);
    approx(&sorted_dist(K::Looter, [MUG, MUG]), &[(LUNGE, 0.5), (SMOKE_BOMB, 0.5)]);
    approx(&sorted_dist(K::Looter, [LUNGE, MUG]), &[(SMOKE_BOMB, 1.0)]);
    approx(&sorted_dist(K::Looter, [SMOKE_BOMB, MUG]), &[(ESCAPE, 1.0)]);
    let mut s = doing(K::Looter, 46, [LUNGE, MUG]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 12);
    let mut s = doing(K::Looter, 46, [SMOKE_BOMB, MUG]);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].block, 6);
    // Escaping ends the combat when it was the last monster: a win.
    end_turn(&mut s);
    assert!(s.monsters[0].escaped && s.won());
}

// ---- Elites ----

#[test]
fn gremlin_nob_bellows_then_enrages_on_skills() {
    use gremlin_nob::*;
    let s = fresh(Encounter::GremlinNob, 1);
    assert_eq!(s.monsters[0].intent(), BELLOW);
    let mut s = doing(K::GremlinNob, 84, [BELLOW, NO_MOVE]);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::Enrage), 2);
    s.hand = Hand::from_cards(&[card("Defend"), card("Strike")]);
    s.player.energy = 3;
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 0);
    play(&mut s, "Defend", None);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 2);
    let mut s = doing(K::GremlinNob, 84, [BULL_RUSH, BELLOW]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 14);
    let mut s = doing(K::GremlinNob, 84, [SKULL_BASH, BELLOW]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 6);
    assert_eq!(s.player.powers.get(Power::Vulnerable), 2);
    approx(&sorted_dist(K::GremlinNob, [BELLOW, NO_MOVE]), &[(BULL_RUSH, 0.67), (SKULL_BASH, 0.33)]);
    approx(&sorted_dist(K::GremlinNob, [BULL_RUSH, BULL_RUSH]), &[(SKULL_BASH, 1.0)]);
}

#[test]
fn lagavulin_sleeps_three_turns_then_attacks_attacks_siphons() {
    use lagavulin::*;
    let mut s = fresh(Encounter::Lagavulin, 4);
    s.player.hp = 500;
    s.player.max_hp = 500;
    s.hand = Hand::default();
    s.set_draw(Pile::default());
    let m = &s.monsters[0];
    assert_eq!((m.block, m.powers.get(Power::Metallicize), m.intent()), (8, 8, SLEEP));
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.monsters[0].block, 8, "Metallicize while asleep");
    assert_eq!(s.monsters[0].intent(), SLEEP);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.monsters[0].intent(), WAKE);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.monsters[0].powers.get(Power::Metallicize), 0, "wakes on its third turn");
    assert_eq!(s.monsters[0].block, 0);
    assert_eq!(s.monsters[0].intent(), ATTACK);
    assert_eq!(hp_loss_on_end_turn(&mut s), 18);
    assert_eq!(hp_loss_on_end_turn(&mut s), 18);
    assert_eq!(s.monsters[0].intent(), SIPHON_SOUL);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.player.powers.get(Power::Strength), -1);
    assert_eq!(s.player.powers.get(Power::Dexterity), -1);
    assert_eq!(s.monsters[0].intent(), ATTACK);
}

#[test]
fn lagavulin_woken_by_hp_damage_is_stunned_and_loses_metallicize() {
    use lagavulin::*;
    // Damage absorbed by its block doesn't wake it.
    let mut s = vs(&[K::Lagavulin], &["Strike", "Bash"], Some(110));
    s.monsters[0].block = 8;
    s.monsters[0].moves = [SLEEP, NO_MOVE];
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].intent(), SLEEP);
    play(&mut s, "Bash", Some(0));
    assert_eq!(s.monsters[0].intent(), STUNNED);
    assert_eq!(s.monsters[0].powers.get(Power::Metallicize), 0);
    s.player.hp = 500;
    s.player.max_hp = 500;
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.monsters[0].block, 0);
    assert_eq!(s.monsters[0].intent(), ATTACK);
}

/// Waking takes 8 Metallicize off, floored at 0 (`changeState("OPEN")`'s
/// `ReducePowerAction`), by HP loss or at its third Sleep turn: a burning
/// elite's extra stays, and less than 8 goes to 0, never below.
#[test]
fn lagavulin_waking_takes_eight_metallicize_off_floored() {
    use lagavulin::*;
    let mut s = vs(&[K::Lagavulin], &["Bash"], Some(110));
    s.monsters[0].block = 0;
    s.monsters[0].moves = [SLEEP, NO_MOVE];
    s.monsters[0].powers.add(Power::Metallicize, 4);
    play(&mut s, "Bash", Some(0));
    assert_eq!(s.monsters[0].intent(), STUNNED);
    assert_eq!(s.monsters[0].powers.get(Power::Metallicize), 4, "12 - 8, by HP loss");
    for (extra, left) in [(4, 4), (-5, 0)] {
        let mut s = vs(&[K::Lagavulin], &[], Some(110));
        s.player.hp = 500;
        s.player.max_hp = 500;
        s.monsters[0].moves = [WAKE, SLEEP];
        s.monsters[0].powers.add(Power::Metallicize, extra);
        hp_loss_on_end_turn(&mut s);
        assert_eq!(s.monsters[0].intent(), ATTACK);
        assert_eq!(s.monsters[0].powers.get(Power::Metallicize), left, "{} - 8 at its third turn", 8 + extra);
    }
}

/// The burning elite's buff, Act 1 (`MonsterRoomElite.applyEmeraldEliteBuff`):
/// Strength 2, Metallicize 4, or max HP +25% rounded and healed as much.
#[test]
fn burning_elite_buffs_every_monster() {
    let fight = |b: EliteBuff| {
        CombatState::new_with_turn1(
            Character::Ironclad,
            &starter_deck(),
            &Default::default(),
            80,
            80,
            &[K::Sentry, K::Sentry, K::Sentry],
            EncounterGroup::Elite,
            &[],
            false,
            Default::default(),
            Some(b),
            &mut Rng::new(3),
        )
    };
    let plain = CombatState::new_with_turn1(Character::Ironclad, &starter_deck(), &Default::default(), 80, 80, &[K::Sentry, K::Sentry, K::Sentry], EncounterGroup::Elite, &[], false, Default::default(), None, &mut Rng::new(3));
    let (st, me, hp) = (fight(EliteBuff::Strength), fight(EliteBuff::Metallicize), fight(EliteBuff::MaxHp));
    for i in 0..3 {
        let p = &plain.monsters[i];
        assert_eq!(st.monsters[i].powers.get(Power::Strength), 2);
        assert_eq!(me.monsters[i].powers.get(Power::Metallicize), 4);
        let up = (p.max_hp + 2) / 4;
        assert_eq!((hp.monsters[i].max_hp, hp.monsters[i].hp), (p.max_hp + up, p.hp + up));
        assert_eq!(hp.monsters[i].powers.get(Power::Artifact), p.powers.get(Power::Artifact));
    }
}

#[test]
fn sentries_alternate_with_the_middle_one_starting_on_beam() {
    use sentry::*;
    let s = fresh(Encounter::ThreeSentries, 2);
    let intents: Vec<_> = s.monsters[..3].iter().map(|m| m.intent()).collect();
    assert_eq!(intents, [BOLT, BEAM, BOLT]);
    for m in &s.monsters[..3] {
        assert_eq!(m.powers.get(Power::Artifact), 1);
    }
    let mut s = doing(K::Sentry, 40, [BOLT, NO_MOVE]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.created, 2);
    assert_eq!(s.hand.count(card("Dazed")) + s.discard().count(card("Dazed")), 2);
    assert_eq!(s.monsters[0].intent(), BEAM);
    assert_eq!(hp_loss_on_end_turn(&mut s), 9);
    assert_eq!(s.monsters[0].intent(), BOLT);
}

#[test]
fn artifact_negates_one_debuff() {
    let mut s = vs(&[K::Sentry], &["Bash", "Uppercut"], Some(40));
    assert_eq!(s.monsters[0].powers.get(Power::Artifact), 1);
    s.player.energy = 4;
    play(&mut s, "Bash", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 0);
    assert_eq!(s.monsters[0].powers.get(Power::Artifact), 0);
    play(&mut s, "Uppercut", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Weak), 1);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 1);
}

// ---- Boss ----

#[test]
fn slime_boss_goop_prepare_slam() {
    use slime_boss::*;
    let s = fresh(Encounter::SlimeBoss, 1);
    assert_eq!((s.monsters[0].hp, s.monsters[0].intent()), (140, GOOP_SPRAY));
    let mut s = doing(K::SlimeBoss, 140, [GOOP_SPRAY, NO_MOVE]);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.created, 3);
    assert_eq!(s.monsters[0].intent(), PREPARING);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.monsters[0].intent(), SLAM);
    assert_eq!(hp_loss_on_end_turn(&mut s), 35);
    assert_eq!(s.monsters[0].intent(), GOOP_SPRAY);
}

#[test]
fn slime_boss_splits_into_spike_and_acid_large_with_its_hp() {
    let mut s = vs(&[K::SlimeBoss], &["Carnage"], Some(140));
    s.monsters[0].moves = [slime_boss::SLAM, slime_boss::PREPARING];
    s.monsters[0].hp = 89;
    play(&mut s, "Carnage", Some(0)); // 69 <= 70
    assert_eq!(s.monsters[0].intent(), slime_boss::SPLIT);
    s.player.hp = 500;
    s.player.max_hp = 500;
    assert_eq!(hp_loss_on_end_turn(&mut s), 0, "Split replaces the Slam");
    let kinds: Vec<_> = s.monsters.iter().map(|m| (m.kind, m.hp, m.max_hp)).collect();
    assert_eq!(kinds[0], (K::SpikeSlimeL, 69, 69));
    assert_eq!(kinds[1], (K::AcidSlimeL, 69, 69));
    // Each large then splits into its own slot and the lowest empty one.
    s.monsters[0].hp = 34;
    s.monsters[1].hp = 34;
    s.monsters[0].set_move(spike_slime::SPLIT);
    s.monsters[1].set_move(acid_slime::SPLIT);
    end_turn(&mut s);
    let kinds: Vec<_> = s.monsters.iter().map(|m| m.kind).collect();
    assert_eq!(kinds, [K::SpikeSlimeM, K::AcidSlimeM, K::SpikeSlimeM, K::AcidSlimeM, K::None]);
    assert!(s.monsters[..4].iter().all(|m| m.hp == 34 && m.alive()));
}
