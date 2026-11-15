//! State codec: every reachable state round-trips, and the byte format
//! doesn't change by accident.
//!
//! - Re-record the golden encodings (only on an intended format or content
//!   change, with `CODEC_VERSION` bumped for a format change):
//!   `CODEC_GOLDEN_RECORD=1 cargo test --test codec golden`.

use std::fmt::Write;
use sts_engine::agent::{random_action, Agent, SearchAgent};
use sts_engine::cards::{class_cards, CardId};
use sts_engine::codec::{self, decode, decode_action, encode, encode_action, try_decode, CODEC_VERSION};
use sts_engine::search::{Heuristic, SearchConfig};
use sts_engine::*;

const GOLDEN: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data/codec_golden.txt");

/// A deck: the starter, plus 6 random class cards on odd seeds.
fn deck(character: Character, seed: u64) -> Vec<CardId> {
    let mut d = character.starter_deck();
    if seed % 2 == 1 {
        let pool: Vec<CardId> = class_cards(character.class()).collect();
        let mut rng = Rng::new(seed ^ 0xdec0);
        for _ in 0..6 {
            d.push(pool[rng.below(pool.len() as u32) as usize]);
        }
    }
    d
}

/// States of one game: each decision, each action's result before chance
/// (chance-paused and mid-card states), and those results' listed outcomes.
fn game_states(character: Character, enc: Encounter, seed: u64, search: bool, out: &mut Vec<CombatState>) {
    let mut rng = Rng::new(seed);
    let mut agent_rng = Rng::new(seed ^ 0xa6e7);
    let hp = character.max_hp();
    let mut s = CombatState::new_as(character, &deck(character, seed), hp, hp, enc, &mut rng);
    let mut agent = SearchAgent::new(Heuristic, SearchConfig { limit: 4, max_nodes: 2_000, ..SearchConfig::default() });
    while !s.is_over() {
        out.push(s.clone());
        for a in s.legal_actions() {
            let mut t = s.clone();
            t.apply_action(a).unwrap();
            out.push(t.clone());
            if let Some(ChanceOutcomes::Listed(v)) = t.chance_outcomes(8) {
                out.extend(v.into_iter().map(|(_, u)| u));
            }
        }
        let a = if search { agent.act(&s, &mut agent_rng) } else { random_action(&s, &mut agent_rng).unwrap() };
        s.step(a, &mut rng).unwrap();
    }
    out.push(s);
}

#[test]
fn codec_roundtrip() {
    const N: usize = 100_000;
    let mut states = Vec::new();
    let mut seed = 0u64;
    while states.len() < N {
        for character in Character::ALL {
            for enc in Encounter::ALL {
                // One game in 8 by search, the rest random.
                game_states(character, enc, seed, seed % 8 == 0, &mut states);
            }
        }
        seed += 1;
    }
    let (mut total, mut max) = (0usize, 0usize);
    let (mut mid_card, mut paused, mut over, mut silent, mut no_death) = (0, 0, 0, 0, 0);
    for (i, s) in states.iter_mut().enumerate() {
        // Some no-death states too: the flag is part of the state.
        if i % 50 == 0 {
            s.no_death = true;
            no_death += 1;
        }
        let b = encode(s);
        assert_eq!(b[0], CODEC_VERSION);
        let back = decode(&b);
        assert_eq!(&back, s, "state {i} doesn't round-trip");
        assert_eq!(encode(&back), b);
        assert!(try_decode(&b[..b.len() - 1]).is_none(), "a truncated encoding decodes");
        total += b.len();
        max = max.max(b.len());
        mid_card += matches!(s.stage, Stage::PlayingCard { .. }) as usize;
        paused += s.pending.is_some() as usize;
        over += s.is_over() as usize;
        silent += (s.character == Character::Silent) as usize;
    }
    eprintln!(
        "codec_roundtrip: {} states, bytes mean {:.1} max {max}; mid-card {mid_card}, chance-paused {paused}, over {over}, silent {silent}",
        states.len(),
        total as f64 / states.len() as f64
    );
    assert!(mid_card > 100 && paused > 1_000 && over > 100 && silent > N / 4 && no_death > 100);
}

#[test]
fn action_codec_round_trips() {
    let s = CombatState::new(&starter_deck(), 80, 80, Encounter::LotsOfSlimes, &mut Rng::new(3));
    let mut bytes = Vec::new();
    let actions = s.legal_actions();
    for &a in &actions {
        encode_action(a, &mut bytes);
    }
    let mut at = 0;
    for &a in &actions {
        assert_eq!(decode_action(&bytes, &mut at), Some(a));
    }
    assert_eq!(at, bytes.len());
}

/// The 20 golden states: varied games' states, by seed.
fn golden_states() -> Vec<CombatState> {
    let mut out = Vec::new();
    for (i, enc) in Encounter::ALL.iter().cycle().take(20).enumerate() {
        let character = Character::ALL[i % 2];
        let mut states = Vec::new();
        game_states(character, *enc, 1_000 + i as u64, false, &mut states);
        out.push(states[states.len() * (i + 1) / 21].clone());
    }
    out
}

fn hex(b: &[u8]) -> String {
    b.iter().fold(String::new(), |mut s, x| {
        write!(s, "{x:02x}").unwrap();
        s
    })
}

fn unhex(s: &str) -> Vec<u8> {
    (0..s.len()).step_by(2).map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap()).collect()
}

/// The committed encodings decode to the same states they were recorded
/// from (compared by their full debug text, which doesn't depend on the
/// rules), so a format change fails here.
#[test]
fn codec_golden() {
    if std::env::var("CODEC_GOLDEN_RECORD").is_ok() {
        let mut text = String::new();
        for s in golden_states() {
            writeln!(text, "{}\n{:?}", hex(&encode(&s)), s).unwrap();
        }
        std::fs::write(GOLDEN, text).unwrap();
        return;
    }
    let text = std::fs::read_to_string(GOLDEN).expect("golden encodings recorded");
    let lines: Vec<&str> = text.lines().collect();
    assert_eq!(lines.len(), 40);
    for pair in lines.chunks(2) {
        let s = decode(&unhex(pair[0]));
        assert_eq!(format!("{s:?}"), pair[1]);
        assert_eq!(hex(&encode(&s)), pair[0]);
    }
}

/// A pending draw past the hand's room isn't a state (its cards would
/// overflow the 10-entry hand, docs/specs/sparse-piles.md): it decodes to
/// `None`, never a later panic.
#[test]
fn draw_past_the_hand_does_not_decode() {
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(3));
    let room = 10 - s.hand.len() as u8;
    s.pending = Some(ChanceEvent::Draw { n: room });
    assert!(try_decode(&encode(&s)).is_some());
    s.pending = Some(ChanceEvent::Draw { n: room + 1 });
    assert!(try_decode(&encode(&s)).is_none());
}

/// Five grown Rampages (past the old 4 variants) encode in section 2 as
/// ranks 0-4 and round-trip (docs/specs/sparse-piles.md).
#[test]
fn five_grown_copies_round_trip() {
    use sts_engine::registry::{changed_copy, Overrides};
    let rampage = CardId::from_name("Rampage").unwrap();
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(3));
    let mut ids = Vec::new();
    for k in 1..=5 {
        let c = changed_copy(rampage, rampage.def(), Overrides { damage: Some(8 + 5 * k), level: 0, cost: None }).unwrap();
        s.discard_mut().add(c, 1);
        ids.push(c);
    }
    let b = encode(&s);
    assert_eq!(decode(&b), s);
    assert_eq!(codec::changed_ranks(&s), ids, "rank order is damage order");
    // Section 2 with 5 copies, bytes 144..149 in the discard pile.
    assert!(b.windows(2).any(|w| w == [2, 5]), "section 2 holds the 5 copies");
    for i in 0..5u8 {
        assert!(b.windows(2).any(|w| w == [144 + i, 1]), "rank byte {} in a pile", 144 + i);
    }
}

/// A level-2 official copy isn't grown damage: section 13 (in place of 2)
/// carries every changed copy.
#[test]
fn level_two_copy_round_trips_in_section_13() {
    use sts_engine::registry::{changed_copy, is_changed, Overrides};
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(3));
    let up = CardId::from_name("Strike+").unwrap();
    let c = changed_copy(up, up.def(), Overrides { damage: None, level: 2, cost: None }).unwrap();
    assert!(is_changed(c));
    let rampage = CardId::from_name("Rampage").unwrap();
    let r = changed_copy(rampage, rampage.def(), Overrides { damage: Some(13), level: 0, cost: None }).unwrap();
    s.discard_mut().add(c, 2);
    s.discard_mut().add(r, 1);
    let b = encode(&s);
    assert_eq!(decode(&b), s);
    assert_eq!(hex(&encode(&decode(&b))), hex(&b));
    // The trailer ends with section 13: both copies by value, in rank order.
    let mut tail = vec![13u8, 2];
    for c in codec::changed_ranks(&s) {
        let (base, o) = sts_engine::registry::copy_of(c).unwrap();
        tail.extend([base.0 as u8, o.level, o.damage.is_some() as u8]);
        if let Some(d) = o.damage {
            tail.push((d as u8) << 1); // zigzag of a small positive number
        }
    }
    assert!(b.ends_with(&tail), "{} ends with {tail:?}", hex(&b));
}

/// B8 of docs/research/build-plans-2026-11-14/colorless-powers.md: takes a
/// power's hook owes behind the turn start (`owed_late`) survive the codec.
#[test]
fn owed_late_takes_round_trip() {
    use sts_engine::state::OwedKind;
    let mut rng = Rng::new(3);
    let mut s = CombatState::new_as(Character::Ironclad, &deck(Character::Ironclad, 2), 80, 80, Encounter::JawWorm, &mut rng);
    while s.pending.is_some() {
        s.resolve_chance(&mut rng);
    }
    assert!(s.owed_late.is_empty());
    let plain = encode(&s);
    s.owed_late.push(OwedKind::Top { exhaust: false }, 2, false);
    s.owed_late.push(OwedKind::Top { exhaust: true }, 1, false);
    let bytes = encode(&s);
    assert_eq!(&bytes[..plain.len()], &plain[..], "an appended section");
    assert_eq!(decode(&bytes), s);
}

/// A6 of docs/research/build-plans-2026-11-14/colorless-piles.md: cards that
/// cost less this turn (`turn_costs`) survive the codec, in a section after
/// the others that a state without any doesn't have.
#[test]
fn turn_costs_round_trip() {
    let mut rng = Rng::new(3);
    let mut s = CombatState::new_as(Character::Ironclad, &deck(Character::Ironclad, 2), 80, 80, Encounter::JawWorm, &mut rng);
    while s.pending.is_some() {
        s.resolve_chance(&mut rng);
    }
    assert!(s.turn_costs.is_empty());
    let plain = encode(&s);
    let cards: Vec<CardId> = s.hand.iter().map(|(c, _)| c).collect();
    assert!(cards.len() >= 2);
    assert!(s.turn_costs.add(cards[0], 1));
    s.free_in_hand.add(cards[1]);
    let bytes = encode(&s);
    assert_ne!(bytes, plain);
    assert_eq!(decode(&bytes), s);
    // A mark on a card the hand doesn't hold, or a cost of 0, doesn't decode.
    let mut bad = bytes.clone();
    let last = bad.len() - 1;
    bad[last] = 0;
    assert!(try_decode(&bad).is_none());
    // Two marks on one card with one copy: not a state.
    let mut two = s.clone();
    if two.hand.count(cards[0]) == 1 {
        two.turn_costs.add(cards[0], 2);
        assert!(try_decode(&encode(&two)).is_none());
    }
}
