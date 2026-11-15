//! Piles and power blocks against dense references (spec sparse-state):
//! the results must not depend on how a pile or power block stores its
//! entries, and equal contents must make equal (and equal-hashing) values.

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use sts_engine::cards::NUM_CARDS;
use sts_engine::powers::{Powers, NUM_POWERS};
use sts_engine::state::{deck_fits, entries_needed, Piles, Run, MADE_ROOM, PILES_INLINE, PILE_RUN_CAP};
use sts_engine::{CardId, CombatState, Encounter, Pile, PileRef, Power, Rng};

fn hash_of<T: Hash>(x: &T) -> u64 {
    let mut h = DefaultHasher::new();
    x.hash(&mut h);
    h.finish()
}

/// Card ids spread over the whole id range (official, generated slots,
/// variants), 30 of them, so a pile never needs more than 30 entries.
fn id_pool() -> Vec<CardId> {
    (0..30).map(|i| CardId((i * (NUM_CARDS - 1) / 29) as u16)).collect()
}

/// A dense pile: a count per card id.
#[derive(Clone)]
struct Dense([u8; NUM_CARDS]);

impl Dense {
    fn check(&self, p: PileRef<'_>) {
        let entries: Vec<(CardId, u8)> = (0..NUM_CARDS).filter(|&i| self.0[i] > 0).map(|i| (CardId(i as u16), self.0[i])).collect();
        assert_eq!(p.iter().collect::<Vec<_>>(), entries, "iter");
        let len: usize = self.0.iter().map(|&n| n as usize).sum();
        assert_eq!(p.len(), len, "len");
        assert_eq!(p.is_empty(), len == 0, "is_empty");
        for i in 0..NUM_CARDS {
            assert_eq!(p.count(CardId(i as u16)), self.0[i], "count of {i}");
        }
        let mut k = 0;
        for (c, n) in &entries {
            for _ in 0..*n {
                assert_eq!(p.nth(k), *c, "nth({k})");
                k += 1;
            }
        }
    }
}

#[test]
fn pile_ops() {
    let pool = id_pool();
    let mut rng = Rng::new(7);
    for round in 0..200 {
        let start: Vec<CardId> = (0..rng.below(15)).map(|_| pool[rng.below(pool.len() as u32) as usize]).collect();
        let mut p = Pile::from_cards(&start);
        let mut d = Dense([0; NUM_CARDS]);
        for c in &start {
            d.0[c.0 as usize] += 1;
        }
        d.check(p.view());
        for _ in 0..60 {
            let c = pool[rng.below(pool.len() as u32) as usize];
            match rng.below(4) {
                0 | 1 => {
                    let n = 1 + rng.below(3) as u8;
                    p.add(c, n);
                    d.0[c.0 as usize] += n;
                }
                2 => {
                    let have = d.0[c.0 as usize];
                    if have > 0 {
                        let n = 1 + rng.below(have as u32) as u8;
                        p.remove(c, n);
                        d.0[c.0 as usize] -= n;
                    }
                }
                _ => {
                    // remove to zero
                    let have = d.0[c.0 as usize];
                    p.remove(c, have);
                    d.0[c.0 as usize] = 0;
                }
            }
            d.check(p.view());
        }
        // add_pile / remove_pile
        let other_cards: Vec<CardId> = (0..rng.below(10)).map(|_| pool[rng.below(pool.len() as u32) as usize]).collect();
        let other = Pile::from_cards(&other_cards);
        let before = p;
        p.add_pile(&other);
        for c in &other_cards {
            d.0[c.0 as usize] += 1;
        }
        d.check(p.view());
        p.remove_pile(&other);
        for c in &other_cards {
            d.0[c.0 as usize] -= 1;
        }
        d.check(p.view());
        assert_eq!(p, before, "add_pile then remove_pile, round {round}");
        p.clear();
        assert_eq!(p, Pile::default());
        Dense([0; NUM_CARDS]).check(p.view());
    }
}

/// The shared list (docs/specs/sparse-piles.md): three piles in one list
/// read and change as three piles of their own, a single pile may take
/// entries past the old 40, the list moves to its spill past
/// `PILES_INLINE` entries and back, and equal contents are equal,
/// equal-hashing values whatever order they were built in.
#[test]
fn shared_piles_ops() {
    // Wider than `id_pool`: up to 100 distinct cards in one pile.
    let pool: Vec<CardId> = (0..100).map(|i| CardId((i * (NUM_CARDS - 1) / 99) as u16)).collect();
    let runs = [Run::Draw, Run::Discard, Run::Exhaust];
    let mut rng = Rng::new(13);
    let mut spilled = 0;
    for round in 0..200 {
        let mut p = Piles::default();
        let mut d = [Dense([0; NUM_CARDS]), Dense([0; NUM_CARDS]), Dense([0; NUM_CARDS])];
        for _ in 0..300 {
            let k = rng.below(3) as usize;
            let c = pool[rng.below(pool.len() as u32) as usize];
            match rng.below(5) {
                0 | 1 => {
                    let n = 1 + rng.below(3) as u8;
                    p.get_mut(runs[k]).add(c, n);
                    d[k].0[c.0 as usize] += n;
                }
                2 => {
                    let have = d[k].0[c.0 as usize];
                    if have > 0 {
                        let n = 1 + rng.below(have as u32) as u8;
                        p.get_mut(runs[k]).remove(c, n);
                        d[k].0[c.0 as usize] -= n;
                    }
                }
                3 if rng.below(20) == 0 => {
                    p.get_mut(runs[k]).clear();
                    d[k] = Dense([0; NUM_CARDS]);
                }
                4 if rng.below(20) == 0 && d[0].0.iter().all(|&n| n == 0) => {
                    p.move_all(Run::Discard, Run::Draw);
                    d[0] = d[1].clone();
                    d[1] = Dense([0; NUM_CARDS]);
                }
                _ => {}
            }
            for (k, r) in runs.iter().enumerate() {
                d[k].check(p.get(*r));
            }
            spilled += (p.total() > PILES_INLINE) as usize;
        }
        // The same contents built pile by pile in another order are equal.
        let mut q = Piles::default();
        for &k in &[2usize, 0, 1] {
            q.set(runs[k], p.get(runs[k]).to_pile());
        }
        assert_eq!(p, q, "round {round}");
        assert_eq!(hash_of(&p), hash_of(&q), "round {round}");
        assert_eq!(p.clone(), p);
    }
    assert!(spilled > 1000, "the list passes PILES_INLINE often ({spilled} steps)");
    // One pile alone may use more than 40 entries.
    let mut p = Piles::default();
    for &c in &pool {
        p.get_mut(Run::Exhaust).add(c, 1);
    }
    assert_eq!(p.get(Run::Exhaust).iter().count(), pool.len());
}

/// Test 6 (docs/research/build-plans-2026-11-14/engine-caps.md): the
/// shared list passes `PILES_INLINE` entries and comes back, equal (and
/// equal-hashing) to a list built without passing it.
#[test]
fn shared_piles_past_inline() {
    let runs = [Run::Draw, Run::Discard, Run::Exhaust];
    let mut p = Piles::default();
    for i in 0..PILES_INLINE + 40 {
        p.get_mut(runs[i % 3]).add(CardId(i as u16), 1);
    }
    assert_eq!(p.total(), PILES_INLINE + 40);
    for i in 0..PILES_INLINE + 40 {
        assert_eq!(p.get(runs[i % 3]).count(CardId(i as u16)), 1);
    }
    let mut q = Piles::default();
    for i in 0..PILES_INLINE + 40 {
        let r = runs[i % 3];
        if r == Run::Exhaust || i < 20 {
            q.get_mut(r).add(CardId(i as u16), 1);
        } else {
            p.get_mut(r).remove(CardId(i as u16), 1);
        }
    }
    assert!(p.total() < PILES_INLINE);
    assert_eq!(p, q);
    assert_eq!(hash_of(&p), hash_of(&q));
    assert_eq!(format!("{p:?}"), format!("{q:?}"));
}

#[test]
#[should_panic(expected = "PILE_RUN_CAP")]
fn one_pile_overflow_panics() {
    let mut p = Pile::default();
    for i in 0..=PILE_RUN_CAP {
        p.add(CardId(i as u16), 1);
    }
}

/// The fight-start bound is on entries: a kind takes at most one per pile.
#[test]
fn entries_needed_counts_a_kind_once_per_pile() {
    let (a, b) = (CardId(0), CardId(1));
    assert_eq!(entries_needed(&[a; 60]), 3);
    assert_eq!(entries_needed(&[a, a, b]), 3);
    assert_eq!(entries_needed::<CardId>(&[]), 0);
}

/// `n` distinct cards (fewer when the loaded cards run out).
fn distinct_deck(n: usize) -> Vec<CardId> {
    CardId::all().filter(|c| !c.is_status()).take(n).collect()
}

/// The fight-start bound: as many distinct cards as one pile holds, less
/// `MADE_ROOM`.
#[test]
fn deck_past_one_pile_is_refused() {
    let room = PILE_RUN_CAP - MADE_ROOM;
    deck_fits(&(0..room).collect::<Vec<_>>()).unwrap();
    let e = deck_fits(&(0..=room).collect::<Vec<_>>()).unwrap_err();
    assert!(e.contains(&format!("{} distinct cards", room + 1)) && e.contains("PILE_RUN_CAP"), "{e}");
}

#[test]
fn big_decks_that_fit_play() {
    let strikes = vec![CardId::from_name("Strike").unwrap(); 60];
    let s = CombatState::new(&strikes, 80, 80, Encounter::ALL[0], &mut Rng::new(1));
    assert_eq!(s.hand.len() + s.draw().len(), 60);
    // Every distinct card: past the old 52 (64 entries less MADE_ROOM).
    let deck = distinct_deck(PILE_RUN_CAP - MADE_ROOM);
    assert!(deck.len() > PILES_INLINE, "{}", deck.len());
    let s = CombatState::new(&deck, 80, 80, Encounter::ALL[0], &mut Rng::new(1));
    assert_eq!(s.hand.len() + s.draw().len(), deck.len());
    // Played on random actions, the piles stay past PILES_INLINE entries
    // (exhausted kinds add entries) and the codec round-trips them.
    let mut past = 0;
    for seed in 0..5 {
        let mut rng = Rng::new(seed);
        let mut s = CombatState::new(&deck, 999, 999, Encounter::ALL[seed as usize], &mut rng);
        for _ in 0..300 {
            if s.is_over() {
                break;
            }
            let acts = s.legal_actions();
            s.step(acts[rng.below(acts.len() as u32) as usize], &mut rng).unwrap();
            assert_eq!(sts_engine::codec::decode(&sts_engine::codec::encode(&s)), s);
            past += (s.piles.total() > PILES_INLINE) as usize;
        }
    }
    assert!(past > 20, "{past} steps past PILES_INLINE");
}

#[test]
fn powers_ops() {
    // Every other power, over the whole range: past the 12 held inline.
    let pool: Vec<Power> = (0..NUM_POWERS).step_by(2).map(|i| Power::ALL_WITH_SLOTS[i]).collect();
    let mut rng = Rng::new(11);
    for _ in 0..200 {
        let mut p = Powers::default();
        let mut amounts = [0i16; NUM_POWERS];
        let mut flags = 0u64;
        for _ in 0..60 {
            let w = pool[rng.below(pool.len() as u32) as usize];
            let i = w as usize;
            match rng.below(6) {
                0 | 1 => {
                    let n = rng.below(7) as i16 - 3;
                    p.add(w, n);
                    amounts[i] += n;
                }
                2 => {
                    // add to exactly zero
                    let n = -amounts[i];
                    p.add(w, n);
                    amounts[i] = 0;
                }
                3 => {
                    p.clear(w);
                    amounts[i] = 0;
                    flags &= !(1 << i);
                }
                4 => {
                    p.set_just_applied(w);
                    flags |= 1 << i;
                }
                _ => {
                    p.clear_round_flags();
                    for (j, a) in amounts.iter().enumerate() {
                        if *a > 0 {
                            flags &= !(1 << j);
                        }
                    }
                }
            }
            for (j, a) in amounts.iter().enumerate() {
                let q = Power::ALL_WITH_SLOTS[j];
                assert_eq!(p.get(q), *a, "get {q:?}");
                assert_eq!(p.just_applied(q), flags & 1 << j != 0, "just_applied {q:?}");
            }
            assert_eq!(p.just_applied_mask(), flags);
            assert!(p == Powers::from_parts(amounts, flags), "one form per contents");
        }
    }
}

#[test]
fn equal_contents_equal_states() {
    let pool = id_pool();
    let mut rng = Rng::new(3);
    for _ in 0..100 {
        // The same multiset reached by different orders, with detours
        // through extra cards that are removed again.
        let cards: Vec<CardId> = (0..rng.below(20)).map(|_| pool[rng.below(pool.len() as u32) as usize]).collect();
        let a = Pile::from_cards(&cards);
        let mut rev = cards.clone();
        rev.reverse();
        let mut b = Pile::default();
        let extra: Vec<CardId> = (0..5).map(|_| pool[rng.below(pool.len() as u32) as usize]).collect();
        for c in &extra {
            b.add(*c, 2);
        }
        for c in &rev {
            b.add(*c, 1);
        }
        for c in &extra {
            b.remove(*c, 2);
        }
        assert_eq!(a, b);
        assert_eq!(hash_of(&a), hash_of(&b));
        assert_eq!(format!("{a:?}"), format!("{b:?}"));
    }
    let pool: Vec<Power> = Power::ALL_WITH_SLOTS.to_vec();
    for _ in 0..100 {
        let set: Vec<(Power, i16)> = (0..rng.below(20)).map(|_| (pool[rng.below(pool.len() as u32) as usize], rng.below(9) as i16 - 4)).collect();
        let mut a = Powers::default();
        for &(w, n) in &set {
            a.add(w, n);
        }
        let mut b = Powers::default();
        let detour: Vec<Power> = (0..4).map(|_| pool[rng.below(pool.len() as u32) as usize]).collect();
        for &w in &detour {
            b.add(w, 5);
        }
        for &(w, n) in set.iter().rev() {
            b.add(w, n);
        }
        for &w in &detour {
            b.add(w, -5);
        }
        assert_eq!(a, b);
        assert_eq!(hash_of(&a), hash_of(&b));
        assert_eq!(format!("{a:?}"), format!("{b:?}"));
    }
}
