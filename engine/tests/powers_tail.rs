//! Powers past the inline 12 (docs/research/build-plans-2026-11-14/engine-caps.md,
//! design F): a creature holds any number of powers, as the game's
//! `ArrayList`; entries past `POWERS_INLINE` live in an interned tail.

mod common;

use common::*;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use sts_engine::codec::{decode, encode};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::powers::{Powers, NUM_POWERS, POWERS_INLINE};
use sts_engine::*;

fn hash_of<T: Hash>(t: &T) -> u64 {
    let mut h = DefaultHasher::new();
    t.hash(&mut h);
    h.finish()
}

/// `n` distinct powers in a shuffled order.
fn shuffled(rng: &mut Rng, n: usize) -> Vec<Power> {
    let mut all = Power::ALL_WITH_SLOTS.to_vec();
    for i in (1..all.len()).rev() {
        all.swap(i, rng.below(i as u32 + 1) as usize);
    }
    all.truncate(n);
    all
}

/// `p` holds exactly `dense`, and equals (and hashes as) a fresh block
/// built from it in power order.
fn check(p: &Powers, dense: &[i16; NUM_POWERS]) {
    for (i, &a) in dense.iter().enumerate() {
        assert_eq!(p.get(Power::ALL_WITH_SLOTS[i]), a, "get {:?}", Power::ALL_WITH_SLOTS[i]);
    }
    let want: Vec<(Power, i16)> = dense.iter().enumerate().filter(|(_, &a)| a != 0).map(|(i, &a)| (Power::ALL_WITH_SLOTS[i], a)).collect();
    assert_eq!(p.iter().collect::<Vec<_>>(), want, "iter in power order");
    let fresh = Powers::from_parts(*dense, 0);
    assert!(*p == fresh, "equal contents, equal values ({} held)", want.len());
    assert_eq!(hash_of(p), hash_of(&fresh));
    assert_eq!(format!("{p:?}"), format!("{fresh:?}"));
}

/// Test 1: 20 distinct powers added in mixed order, removed in another;
/// at every step the block equals a freshly built one, and back at 12 it
/// is the inline-only value again.
#[test]
fn powers_past_twelve() {
    let mut rng = Rng::new(78);
    for round in 0..50 {
        let mut p = Powers::default();
        let mut dense = [0i16; NUM_POWERS];
        let on = shuffled(&mut rng, 20);
        for (k, &w) in on.iter().enumerate() {
            let n = if k % 3 == 0 { -(k as i16) - 1 } else { k as i16 + 1 };
            p.add(w, n);
            dense[w as usize] = n;
            check(&p, &dense);
            // Changing a held entry (inline or tail) and back.
            let x = on[rng.below(k as u32 + 1) as usize];
            p.add(x, 5);
            dense[x as usize] += 5;
            if dense[x as usize] != 0 {
                check(&p, &dense);
            }
            p.add(x, -5);
            dense[x as usize] -= 5;
            check(&p, &dense);
        }
        let mut off = on.clone();
        for i in (1..off.len()).rev() {
            off.swap(i, rng.below(i as u32 + 1) as usize);
        }
        for (k, &w) in off.iter().enumerate() {
            match (round + k) % 3 {
                0 => p.clear(w),
                1 => p.add(w, -dense[w as usize]),
                _ => p.reduce(w, i16::MAX),
            }
            // `reduce` removes only a positive amount.
            if (round + k) % 3 == 2 && dense[w as usize] < 0 {
                p.clear(w);
            }
            dense[w as usize] = 0;
            check(&p, &dense);
        }
        assert!(p == Powers::default());
    }
}

/// Today's `Powers` fields, hashed as the derive did before the tail.
#[derive(Hash)]
struct Before {
    amounts: [i16; POWERS_INLINE],
    held: [u32; 2],
    just_applied: [u32; 2],
}

fn before(p: &Powers) -> Before {
    let (mut amounts, mut held) = ([0i16; POWERS_INLINE], 0u64);
    for (i, (w, a)) in p.iter().enumerate() {
        amounts[i] = a;
        held |= 1 << w as u32;
    }
    let ja = p.just_applied_mask();
    Before { amounts, held: [held as u32, (held >> 32) as u32], just_applied: [ja as u32, (ja >> 32) as u32] }
}

/// Test 3: a block within `POWERS_INLINE` powers hashes exactly as before
/// the tail existed (so every existing state's `state_hash` is unchanged).
#[test]
fn hash_unchanged_within_twelve() {
    let mut rng = Rng::new(5);
    for _ in 0..500 {
        let mut p = Powers::default();
        let k = rng.below(POWERS_INLINE as u32 + 1) as usize;
        for w in shuffled(&mut rng, k) {
            p.add(w, rng.below(9) as i16 - 4);
            if rng.below(3) == 0 {
                p.set_just_applied(w);
            }
        }
        assert_eq!(hash_of(&p), hash_of(&before(&p)));
    }
}

/// Test 2: the player holds 12 powers and plays Inflame: Strength 2, the
/// 13th, and the turn plays on. The codec round-trips states with 13+.
#[test]
fn inflame_as_the_thirteenth_power() {
    let mut s = vs(&[K::Cultist], &["Inflame", "Strike"], Some(100));
    s.set_draw(Pile::from_cards(&[card("Strike"); 10]));
    let twelve = [
        Power::Dexterity, Power::Vulnerable, Power::Ritual, Power::Metallicize, Power::Artifact, Power::Combust,
        Power::CombustDamage, Power::Brutality, Power::Rupture, Power::DemonForm, Power::Rage, Power::Thorns,
    ];
    for (i, &w) in twelve.iter().enumerate() {
        s.player.powers.add(w, i as i16 + 1);
    }
    // 13 on the monster too.
    for w in [
        Power::Strength, Power::Dexterity, Power::Vulnerable, Power::Weak, Power::Frail, Power::Ritual, Power::CurlUp, Power::Enrage,
        Power::Metallicize, Power::Artifact, Power::Poison, Power::SharpHide, Power::Thorns,
    ] {
        s.monsters[0].powers.add(w, 2);
    }
    play(&mut s, "Inflame", None);
    assert_eq!(s.player.powers.get(Power::Strength), 2);
    assert_eq!(s.player.powers.iter().count(), 13);
    for (i, &w) in twelve.iter().enumerate() {
        assert_eq!(s.player.powers.get(w), i as i16 + 1, "{w:?}");
    }
    assert_eq!(decode(&encode(&s)), s);
    play(&mut s, "Strike", Some(0));
    end_turn(&mut s);
    // Demon Form (10) adds Strength at the turn start.
    assert!(s.player.powers.get(Power::Strength) >= 12);
    assert!(s.monsters[0].powers.iter().count() >= 12);
    assert_eq!(decode(&encode(&s)), s);
}
