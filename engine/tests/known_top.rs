//! The known top of the draw pile (docs/specs/known-top.md): Headbutt,
//! drawing a known top, a card put at a random spot under the top card (a
//! floater; docs/specs/draw-knowledge.md item 1) at the game's odds, and
//! the codec.

mod common;

use common::*;
use sts_engine::chance::{ChanceEvent, ChanceOutcomes};
use sts_engine::codec;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::*;

/// Headbutt picks Bash from the discard pile; Wild Strike then puts a
/// Wound at a random spot under it. Draw pile: Strike, Defend, Bash (known
/// on top), Wound (a floater with Bash certainly above it).
fn with_floater() -> CombatState {
    let mut s = vs(&[K::JawWorm], &["Headbutt", "Wild Strike"], Some(100));
    s.set_draw(Pile::from_cards(&[card("Strike"), card("Defend")]));
    s.set_discard(Pile::from_cards(&[card("Bash")]));
    play(&mut s, "Headbutt", Some(0));
    assert_eq!(s.legal_actions(), vec![Action::Choose(card("Bash"))].into_iter().filter(|a| s.is_legal(*a)).collect::<Vec<_>>());
    s.apply_action(Action::Choose(card("Bash"))).unwrap();
    assert_eq!(s.top.known().collect::<Vec<_>>(), vec![card("Bash")]);
    play(&mut s, "Wild Strike", Some(0));
    assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(card("Wound"), 1)]);
    assert_eq!(s.draw().len(), 4);
    s
}

/// The listed outcomes of drawing `n` now, as (sorted hand names, probability).
fn draws(s: &CombatState, n: u8) -> Vec<(Vec<&'static str>, f64)> {
    let mut t = s.clone();
    t.hand = Hand::default();
    t.pending = Some(ChanceEvent::Draw { n });
    let Some(ChanceOutcomes::Listed(v)) = t.chance_outcomes(100) else { panic!("listed") };
    let mut out: Vec<(Vec<&str>, f64)> = v
        .into_iter()
        .map(|(p, u)| {
            let mut h: Vec<&str> = u.hand.iter().flat_map(|(c, k)| std::iter::repeat_n(c.name(), k as usize)).collect();
            h.sort();
            (h, p)
        })
        .collect();
    out.sort_by(|a, b| a.0.cmp(&b.0));
    out
}

#[test]
fn headbutt_puts_the_choice_on_top() {
    let mut s = vs(&[K::JawWorm], &["Headbutt"], Some(100));
    s.set_draw(Pile::from_cards(&[card("Strike"), card("Defend"), card("Defend")]));
    s.set_discard(Pile::from_cards(&[card("Bash"), card("Anger")]));
    play(&mut s, "Headbutt", Some(0));
    s.apply_action(Action::Choose(card("Anger"))).unwrap();
    assert_eq!(s.monsters[0].hp, 91);
    assert_eq!(s.draw().count(card("Anger")), 1);
    // Drawing 1: the known card, for sure.
    let d = draws(&s, 1);
    assert_eq!(d, vec![(vec!["Anger"], 1.0)]);
    // Drawing 2: Anger, then one of the rest at random.
    let d = draws(&s, 2);
    assert_eq!(d.len(), 2);
    assert!(d.iter().all(|(h, _)| h.contains(&"Anger")));
    assert!((d.iter().map(|x| x.1).sum::<f64>() - 1.0).abs() < 1e-12);
}

#[test]
fn floater_odds_match_the_game() {
    // addToRandomSpot: the Wound goes under Bash, at any of 3 places below
    // it: Bash first for sure, then {Wound, Strike, Defend} alike.
    let s = with_floater();
    let d = draws(&s, 1);
    assert_eq!(d, vec![(vec!["Bash"], 1.0)]);
    let d = draws(&s, 2);
    let want = [(vec!["Bash", "Defend"], 1.0 / 3.0), (vec!["Bash", "Strike"], 1.0 / 3.0), (vec!["Bash", "Wound"], 1.0 / 3.0)];
    assert_eq!(d.len(), 3);
    for ((h, p), (wh, wp)) in d.iter().zip(want.iter()) {
        assert_eq!(h, wh);
        assert!((p - wp).abs() < 1e-12, "{h:?} {p} vs {wp}");
    }
    let (bash, wound) = (card("Bash"), card("Wound"));
    assert_draw_odds_match(&s, &[bash], &[card("Strike"), card("Defend")], &[PileOp::RandomSpot(wound)]);
}

#[test]
fn sampled_draws_follow_the_same_odds() {
    let s = with_floater();
    let mut rng = Rng::new(5);
    let (mut wound_first, mut wound_in_two) = (0, 0);
    let n = 20_000;
    for _ in 0..n {
        let mut t = s.clone();
        t.hand = Hand::default();
        t.pending = Some(ChanceEvent::Draw { n: 1 });
        t.resolve_chance(&mut rng);
        wound_first += t.hand.count(card("Wound")) as usize;
        t.pending = Some(ChanceEvent::Draw { n: 1 });
        t.resolve_chance(&mut rng);
        wound_in_two += t.hand.count(card("Wound")) as usize;
    }
    assert_eq!(wound_first, 0, "never the next draw");
    let f = wound_in_two as f64 / n as f64;
    assert!((f - 1.0 / 3.0).abs() < 0.015, "{f}");
}

#[test]
fn floaters_dissolve_once_nothing_is_above_them() {
    // Bash is drawn first; then nothing is known and the Wound has nothing
    // certainly above it: a plain member of the pile.
    let mut s = with_floater();
    s.hand = Hand::default();
    s.pending = Some(ChanceEvent::Draw { n: 1 });
    s.resolve_chance(&mut Rng::new(1));
    assert_eq!(s.hand.count(card("Bash")), 1);
    assert!(s.top.is_empty(), "nothing known, so the Wound is a plain member");
    assert_eq!(s.draw().count(card("Wound")), 1);
}

/// Wild Strike into a pile with nothing known: the Wound is never the
/// next draw (the engine once let it be, 1 in n+1), and every later draw
/// has the game's odds.
#[test]
fn wild_strike_wound_goes_under_an_unknown_top() {
    let unknown = [card("Strike"), card("Defend"), card("Bash"), card("Defend")];
    let mut s = vs(&[K::JawWorm], &["Wild Strike"], Some(100));
    s.set_draw(Pile::from_cards(&unknown));
    play(&mut s, "Wild Strike", Some(0));
    assert_eq!((s.top.n_known(), s.top.floaters().collect::<Vec<_>>()), (0, vec![(card("Wound"), 1)]));
    assert!(engine_draw_odds(&s, 1).iter().all(|(h, _)| !h.contains(&card("Wound"))));
    assert_draw_odds_match(&s, &[], &unknown, &[PileOp::RandomSpot(card("Wound"))]);
    assert_eq!(codec::decode(&codec::encode(&s)), s);
    // Sampled: never first.
    for seed in 0..200 {
        let mut t = s.clone();
        t.hand = Hand::default();
        t.pending = Some(ChanceEvent::Draw { n: 1 });
        t.resolve_chance(&mut Rng::new(seed));
        assert_eq!(t.hand.count(card("Wound")), 0, "seed {seed}");
    }
}

/// Two Wild Strikes, then Headbutt puts Bash on top, then a third: the
/// floaters' cards-above counts follow, and the odds stay the game's.
#[test]
fn wild_strikes_around_a_headbutt_keep_the_games_odds() {
    let unknown = [card("Strike"), card("Defend"), card("Defend")];
    let (wound, bash) = (card("Wound"), card("Bash"));
    let mut s = vs(&[K::JawWorm], &["Wild Strike", "Wild Strike", "Wild Strike", "Headbutt"], Some(300));
    s.player.energy = 10;
    s.set_draw(Pile::from_cards(&unknown));
    s.set_discard(Pile::from_cards(&[bash]));
    play(&mut s, "Wild Strike", Some(0));
    play(&mut s, "Wild Strike", Some(0));
    assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(wound, 1), (wound, 1)]);
    play(&mut s, "Headbutt", Some(0));
    s.apply_action(Action::Choose(bash)).unwrap();
    assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(wound, 2), (wound, 2)]);
    play(&mut s, "Wild Strike", Some(0));
    assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(wound, 2), (wound, 2), (wound, 1)], "oldest first");
    let ops = [PileOp::RandomSpot(wound), PileOp::RandomSpot(wound), PileOp::Top(bash), PileOp::RandomSpot(wound)];
    assert_draw_odds_match(&s, &[], &unknown, &ops);
    assert_eq!(codec::decode(&codec::encode(&s)), s);
}

/// A Wound into an empty draw pile is just its card: the game's
/// `addToRandomSpot` adds it, nothing above it.
#[test]
fn wild_strike_into_an_empty_pile() {
    let mut s = vs(&[K::JawWorm], &["Wild Strike"], Some(100));
    play(&mut s, "Wild Strike", Some(0));
    assert!(s.top.is_empty());
    assert_eq!(s.draw().count(card("Wound")), 1);
    assert_eq!(engine_draw_odds(&s, 1), vec![(vec![card("Wound")], 1.0)]);
}

/// `PlayTop` (Havoc's take of the top card) never takes a card put at a
/// random spot with nothing known.
#[test]
fn take_top_never_takes_a_random_spot_card() {
    let unknown = [card("Strike"), card("Defend"), card("Bash")];
    let mut s = vs(&[K::JawWorm], &["Wild Strike"], Some(100));
    s.set_draw(Pile::from_cards(&unknown));
    play(&mut s, "Wild Strike", Some(0));
    let mut t = s.clone();
    t.pending = Some(ChanceEvent::TakeTop { exhaust: false });
    let Some(ChanceOutcomes::Listed(v)) = t.chance_outcomes(100) else { panic!("listed") };
    assert_eq!(v.len(), 3, "one per original card");
    assert!((v.iter().map(|x| x.0).sum::<f64>() - 1.0).abs() < 1e-12);
    for (p, u) in &v {
        assert!((p - 1.0 / 3.0).abs() < 1e-12);
        assert_eq!(u.draw().count(card("Wound")), 1, "the Wound stays");
        assert_eq!(u.draw().len(), 3);
    }
}

#[test]
fn codec_round_trips_top() {
    let s = with_floater();
    let b = codec::encode(&s);
    assert_eq!(codec::decode(&b), s);
    // Without a known top the bytes are today's: no trailer.
    let mut t = s.clone();
    t.top = Default::default();
    t.draw_mut().remove(card("Wound"), 1);
    assert!(codec::encode(&t).len() < b.len());
    assert_eq!(codec::decode(&codec::encode(&t)), t);
}

#[test]
fn headbutt_with_empty_discard_skips_the_pick() {
    let mut s = vs(&[K::JawWorm], &["Headbutt+"], Some(100));
    play(&mut s, "Headbutt+", Some(0));
    assert_eq!((s.monsters[0].hp, s.top.is_empty()), (88, true));
}

#[test]
fn inferno_upgrades_known_burns() {
    use sts_engine::monsters::hexaghost;
    let mut s = vs(&[K::Hexaghost], &["Headbutt"], Some(300));
    s.set_discard(Pile::from_cards(&[card("Burn")]));
    play(&mut s, "Headbutt", Some(0));
    s.apply_action(Action::Choose(card("Burn"))).unwrap();
    assert_eq!(s.top.known().collect::<Vec<_>>(), vec![card("Burn")]);
    s.monsters[0].set_move(hexaghost::INFERNO);
    end_turn(&mut s);
    // The known Burn became Burn+ with the draw pile's copy and was drawn
    // first; the reshuffled discard pile brought Inferno's three Burn+.
    assert!(s.top.is_empty());
    assert_eq!((s.hand.count(card("Burn+")), s.hand.count(card("Burn"))), (4, 0));
}

/// Nine Wounds put under a known Bash: each is a floater under it, so
/// Bash comes first for sure, then the Wounds.
#[test]
fn nine_wounds_under_a_known_bash() {
    let mut hand = vec!["Headbutt"];
    hand.extend(std::iter::repeat_n("Wild Strike", 9));
    let mut s = vs(&[K::JawWorm], &hand, Some(300));
    s.set_discard(Pile::from_cards(&[card("Bash")]));
    s.player.energy = 10;
    play(&mut s, "Headbutt", Some(0));
    s.apply_action(Action::Choose(card("Bash"))).unwrap();
    for _ in 0..9 {
        play(&mut s, "Wild Strike", Some(0));
    }
    assert_eq!(s.monsters[0].hp, 183);
    assert_eq!((s.draw().len(), s.top.floaters().count()), (10, 9));
    assert_eq!(draws(&s, 1), vec![(vec!["Bash"], 1.0)]);
    let d = draws(&s, 9);
    assert_eq!(d.len(), 1);
    assert!(d[0].0.contains(&"Bash"));
    assert_eq!(codec::decode(&codec::encode(&s)), s);
}

#[test]
fn copies_of_a_floater_share_an_entry() {
    use sts_engine::state::Top;
    let (bash, wound, strike) = (card("Bash"), card("Wound"), card("Strike"));
    let mut t = Top::from_parts(&[bash], &[]).unwrap();
    for _ in 0..9 {
        t.add_floater_under(wound);
    }
    assert_eq!(t.floaters().collect::<Vec<_>>(), vec![(wound, 1); 9]);
    t.push(strike, false);
    t.add_floater_under(wound);
    assert_eq!(t.pop_head(), strike);
    // Oldest first: the nine, then the newest, now on top.
    assert_eq!(t.floaters_on_top(), vec![(1, wound, 1)]);
    let mut parts = vec![(wound, 1); 9];
    parts.push((wound, 0));
    assert_eq!(t, Top::from_parts(&[bash], &parts).unwrap());
    // Drawing the newest leaves the older ones' card above them.
    t.take_floater(1);
    assert_eq!(t.floaters().collect::<Vec<_>>(), vec![(wound, 1); 9]);
    // Only floaters with something certainly above them: still knowledge.
    let u = Top::from_parts(&[], &[(wound, 1)]).unwrap();
    assert_eq!(u.n_known(), 0);
    // Nothing known and nothing above: says nothing.
    assert_eq!(Top::from_parts(&[], &[(wound, 0)]), None);
}

/// The engine's states after a uniformly random copy of `c` left the draw
/// pile (the hand emptied again), with their chances.
fn engine_remove(s: &CombatState, c: CardId) -> Vec<(f64, CombatState)> {
    let mut t = s.clone();
    t.hand = Hand::default();
    t.pending = Some(ChanceEvent::DrawInstance { card: c });
    let Some(ChanceOutcomes::Listed(v)) = t.chance_outcomes(100_000) else { panic!("listed") };
    v.into_iter()
        .map(|(p, mut u)| {
            u.hand = Hand::default();
            (p, u)
        })
        .collect()
}

/// Random sequences of random-spot inserts, cards put on top, cards taken
/// out of the pile at random and draws, over `unknown` (in random order):
/// the engine's states (a mixture: which copy left is a chance event) and
/// the game's pile orders, enumerated, give every draw's odds and the odds
/// of every next hand at the end equal.
fn random_sequences(unknown: &[CardId], inserts: &[CardId], pushes: &[CardId], cases: u32, seed: u64) {
    use std::collections::BTreeMap;
    let mut rng = Rng::new(seed);
    for case in 0..cases {
        let mut s = vs(&[K::JawWorm], &[], Some(100));
        s.set_draw(Pile::from_cards(unknown));
        // The game: each pile order (bottom first) with its chance.
        let mut orders: BTreeMap<Vec<CardId>, f64> = BTreeMap::new();
        let mut idx: Vec<usize> = (0..unknown.len()).collect();
        let mut perms = Vec::new();
        fn rec(v: &mut Vec<usize>, i: usize, out: &mut Vec<Vec<usize>>) {
            if i == v.len() {
                out.push(v.clone());
                return;
            }
            for j in i..v.len() {
                v.swap(i, j);
                rec(v, i + 1, out);
                v.swap(i, j);
            }
        }
        rec(&mut idx, 0, &mut perms);
        for p in &perms {
            *orders.entry(p.iter().map(|&i| unknown[i]).collect()).or_default() += 1.0 / perms.len() as f64;
        }
        let mut piles: Vec<(Vec<CardId>, f64)> = orders.into_iter().collect();
        let mut states: Vec<(f64, CombatState)> = vec![(1.0, s)];
        let (mut ins, mut push) = (inserts.iter(), pushes.iter());
        let mut log = Vec::new();
        for _ in 0..10 {
            let op = rng.below(4);
            let spot = if op == 0 { ins.next().copied() } else { None };
            let top = if op == 1 { push.next().copied() } else { None };
            let len = states[0].1.draw().len();
            if let Some(c) = spot {
                log.push(format!("spot {}", c.name()));
                for (_, s) in &mut states {
                    let was_empty = s.draw().is_empty();
                    s.draw_mut().add(c, 1);
                    if !was_empty {
                        s.top.add_floater_under(c);
                    }
                }
                piles = piles
                    .into_iter()
                    .flat_map(|(p, q)| {
                        let n = p.len().max(1);
                        (0..n).map(move |at| {
                            let mut t = p.clone();
                            t.insert(at.min(t.len()), c);
                            (t, q / n as f64)
                        })
                    })
                    .collect();
            } else if let Some(c) = top {
                log.push(format!("top {}", c.name()));
                for (_, s) in &mut states {
                    s.draw_mut().add(c, 1);
                    s.top.push(c, false);
                }
                for (p, _) in &mut piles {
                    p.push(c);
                }
            } else if op == 3 && len > 1 {
                // A random copy of a random kind in the pile leaves.
                let kinds: Vec<CardId> = states[0].1.draw().iter().map(|(c, _)| c).collect();
                let c = kinds[rng.below(kinds.len() as u32) as usize];
                log.push(format!("remove {}", c.name()));
                let mut next: Vec<(f64, CombatState)> = Vec::new();
                for (w, s) in &states {
                    for (p, u) in engine_remove(s, c) {
                        match next.iter_mut().find(|x| x.1 == u) {
                            Some(x) => x.0 += w * p,
                            None => next.push((w * p, u)),
                        }
                    }
                }
                states = next;
                let mut out: BTreeMap<Vec<CardId>, f64> = BTreeMap::new();
                for (p, q) in piles {
                    let k = p.iter().filter(|&&x| x == c).count();
                    for at in (0..p.len()).filter(|&at| p[at] == c) {
                        let mut t = p.clone();
                        t.remove(at);
                        *out.entry(t).or_default() += q / k as f64;
                    }
                }
                piles = out.into_iter().collect();
            } else if len > 0 {
                // Draw: the game's odds of each card, then follow one.
                let mut game: BTreeMap<CardId, f64> = BTreeMap::new();
                for (p, q) in &piles {
                    *game.entry(*p.last().unwrap()).or_default() += q;
                }
                let mut eng: BTreeMap<CardId, f64> = BTreeMap::new();
                for (w, s) in &states {
                    for (h, p) in engine_draw_odds(s, 1) {
                        *eng.entry(h[0]).or_default() += w * p;
                    }
                }
                assert_eq!(eng.keys().collect::<Vec<_>>(), game.keys().collect::<Vec<_>>(), "case {case}: {log:?}");
                for (c, p) in &eng {
                    assert!((p - game[c]).abs() < 1e-9, "case {case}: {log:?}: {} engine {p} game {}", c.name(), game[c]);
                }
                let keys: Vec<CardId> = game.keys().copied().collect();
                let c = keys[rng.below(keys.len() as u32) as usize];
                log.push(format!("draw {}", c.name()));
                let mut next: Vec<(f64, CombatState)> = Vec::new();
                for (w, s) in &states {
                    let mut t = s.clone();
                    t.hand = Hand::default();
                    t.pending = Some(ChanceEvent::Draw { n: 1 });
                    let Some(ChanceOutcomes::Listed(out)) = t.chance_outcomes(100) else { panic!("listed") };
                    for (p, mut u) in out {
                        if u.hand.count(c) == 1 {
                            u.hand = Hand::default();
                            match next.iter_mut().find(|x| x.1 == u) {
                                Some(x) => x.0 += w * p,
                                None => next.push((w * p, u)),
                            }
                        }
                    }
                }
                let total: f64 = next.iter().map(|x| x.0).sum();
                states = next.into_iter().map(|(w, s)| (w / total, s)).collect();
                let total: f64 = piles.iter().filter(|(p, _)| *p.last().unwrap() == c).map(|x| x.1).sum();
                piles = piles
                    .into_iter()
                    .filter(|(p, _)| *p.last().unwrap() == c)
                    .map(|(mut p, q)| {
                        p.pop();
                        (p, q / total)
                    })
                    .collect();
            }
        }
        // Every next hand from what is left.
        let left = states[0].1.draw().len();
        assert!(states.iter().all(|(_, s)| s.draw().len() == left), "case {case}: {log:?}");
        for k in 1..=left.min(10) {
            let mut game: BTreeMap<Vec<CardId>, f64> = BTreeMap::new();
            for (p, q) in &piles {
                let mut h = p[p.len() - k..].to_vec();
                h.sort();
                *game.entry(h).or_default() += q;
            }
            let mut eng: BTreeMap<Vec<CardId>, f64> = BTreeMap::new();
            for (w, s) in &states {
                for (h, p) in engine_draw_odds(s, k as u8) {
                    *eng.entry(h).or_default() += w * p;
                }
            }
            assert_eq!(eng.len(), game.len(), "case {case}: {log:?}: draw {k}");
            for ((h, p), (g, q)) in eng.iter().zip(&game) {
                assert_eq!(h, g, "case {case}: {log:?}: draw {k}");
                assert!((p - q).abs() < 1e-9, "case {case}: {log:?}: draw {k}: {h:?} engine {p} game {q}
{:?}", states.iter().map(|(w, s)| (*w, s.top.known().map(|c| c.name()).collect::<Vec<_>>(), s.top.floater_entries_slack().map(|(c, a, k, sl)| (c.name(), a, k, sl)).collect::<Vec<_>>(), engine_draw_odds(s, k as u8).into_iter().map(|(h, p)| (h.iter().map(|c| c.name()).collect::<Vec<_>>(), p)).collect::<Vec<_>>())).collect::<Vec<_>>());
            }
        }
        for (_, s) in &states {
            assert_eq!(codec::decode(&codec::encode(s)), *s, "case {case}: {log:?}");
        }
    }
}

/// Random sequences of random-spot inserts, cards put on top, cards taken
/// out of the pile at random and draws, each card a kind of its own: every
/// draw's odds and the odds of every next hand at the end equal an exact
/// enumeration of the game's pile.
#[test]
fn random_sequences_keep_the_games_odds() {
    let unknown = ["Strike", "Defend", "Anger"].map(card);
    let inserts = ["Wound", "Dazed", "Slimed", "Burn", "Bash+", "Anger+"].map(card);
    let pushes = ["Bash", "Clash", "Cleave"].map(card);
    random_sequences(&unknown, &inserts, &pushes, 400, 20261114);
}

/// The same with copies: the cards put in and taken out are often kinds
/// the pile holds already, so the copy that leaves can be a known card, a
/// floater or a plain one.
#[test]
fn random_sequences_with_copies_keep_the_games_odds() {
    let unknown = ["Strike", "Strike", "Defend", "Defend"].map(card);
    let inserts = ["Wound", "Strike", "Wound", "Defend", "Bash"].map(card);
    let pushes = ["Defend", "Strike", "Wound"].map(card);
    random_sequences(&unknown, &inserts, &pushes, 250, 20261115);
}

/// A Wound already in the pile and one put under the top: the plain Wound
/// can be the next draw, the new one can't, and every next hand has the
/// game's odds (the floater's card is also a plain card of the pile).
#[test]
fn a_floater_whose_card_is_also_in_the_pile() {
    let unknown = [card("Strike"), card("Wound"), card("Defend")];
    let mut s = vs(&[K::JawWorm], &["Wild Strike", "Wild Strike"], Some(300));
    s.set_draw(Pile::from_cards(&unknown));
    play(&mut s, "Wild Strike", Some(0));
    play(&mut s, "Wild Strike", Some(0));
    let wound = card("Wound");
    let first = engine_draw_odds(&s, 1);
    let p: f64 = first.iter().filter(|(h, _)| h.contains(&wound)).map(|x| x.1).sum();
    assert!((p - 1.0 / 3.0).abs() < 1e-12, "only the plain Wound: {p}");
    assert_draw_odds_match(&s, &[], &unknown, &[PileOp::RandomSpot(wound), PileOp::RandomSpot(wound)]);
}

/// Decoding refuses a floater with more cards above it than the pile
/// holds plain cards: no card could be on top.
#[test]
fn codec_refuses_a_floater_buried_past_the_pile() {
    let mut s = vs(&[K::JawWorm], &["Wild Strike"], Some(100));
    s.set_draw(Pile::from_cards(&[card("Strike")]));
    play(&mut s, "Wild Strike", Some(0));
    assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(card("Wound"), 1)]);
    let b = codec::encode(&s);
    assert_eq!(codec::decode(&b), s);
    // The same bytes over a pile of the Wound alone.
    let mut t = s.clone();
    t.draw_mut().remove(card("Strike"), 1);
    assert!(!t.top.within(t.draw()));
    assert!(codec::try_decode(&codec::encode(&t)).is_none());
}
