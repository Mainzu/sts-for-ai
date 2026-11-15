#![allow(dead_code)]

use sts_engine::monsters::Monster;
use sts_engine::state::{HAND_LIMIT, MAX_MONSTERS};
use sts_engine::*;

pub fn card(name: &str) -> CardId {
    CardId::from_name(name).unwrap_or_else(|| panic!("no card {name}"))
}

pub fn fresh(enc: Encounter, seed: u64) -> CombatState {
    CombatState::new(&starter_deck(), 80, 80, enc, &mut Rng::new(seed))
}

/// Player turn with exactly `hand`, empty other piles, 3 energy, and
/// monster 0 at `hp` with no block.
pub fn with_hand(enc: Encounter, hand: &[&str], hp: i16) -> CombatState {
    let mut s = fresh(enc, 1);
    let cards: Vec<_> = hand.iter().map(|n| card(n)).collect();
    s.hand = Hand::from_cards(&cards);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 3;
    s.monsters[0].hp = hp;
    s.monsters[0].max_hp = hp;
    s.monsters[0].block = 0;
    s
}

/// Player turn with exactly `hand`, empty other piles, 3 energy, and fresh
/// monsters of `kinds` (each at its kind's minimum HP unless `hp` is given)
/// in slots 0.., with no moves yet.
pub fn vs(kinds: &[MonsterKind], hand: &[&str], hp: Option<i16>) -> CombatState {
    let mut s = with_hand(Encounter::Cultist, hand, 1);
    s.monsters = Default::default();
    for (i, &k) in kinds.iter().enumerate() {
        s.monsters[i] = Monster::new(k, hp.unwrap_or(k.def().hp_min));
    }
    s
}

pub fn play(s: &mut CombatState, name: &str, target: Option<u8>) {
    s.apply_action(Action::Play { card: card(name), target }).expect("legal play");
}

/// Ends the turn and samples chance with a fixed seed.
pub fn end_turn(s: &mut CombatState) {
    s.step(Action::EndTurn, &mut Rng::new(7)).expect("end turn");
}

pub fn total_cards(s: &CombatState) -> usize {
    s.hand.len() + s.draw().len() + s.discard().len() + s.exhaust().len()
}

/// Invariants checked after every step of the fuzz run.
pub fn check_invariants(s: &CombatState, deck_size: usize) {
    let p = &s.player;
    assert!(0 <= p.hp && p.hp <= p.max_hp, "player hp {} / {}", p.hp, p.max_hp);
    assert!(p.energy >= 0, "energy {}", p.energy);
    assert!(p.block >= 0);
    for m in &s.monsters[..MAX_MONSTERS] {
        assert!(0 <= m.hp && m.hp <= m.max_hp, "monster hp {} / {}", m.hp, m.max_hp);
        assert!(m.block >= 0);
    }
    assert!(s.hand.len() <= HAND_LIMIT);
    let expected = deck_size + s.created as usize - s.removed as usize;
    // A card paused at a pick is in play, in no pile (a replayed copy is
    // no card of its own), and its bookkeeping may still be pending.
    let (in_play, at_pick) = match s.stage {
        sts_engine::state::Stage::PlayingCard { more, .. } => ((!more.copy) as usize, more.pick.is_some()),
        _ => (0, false),
    };
    assert_eq!(total_cards(s) + in_play, expected, "card count not conserved");
    assert!(s.top.within(s.draw()), "known top not in the draw pile");
    if !at_pick {
        assert_eq!(s.deferred_block, [0; MAX_MONSTERS], "Curl Up block left pending");
        assert_eq!(s.card_hp_losses, 0, "Rupture triggers left pending");
    }
    assert!(s.turn <= 200, "combat ran past 200 turns");
    assert!(s.is_over() || s.awaiting_action(), "stopped mid-resolution: {:?}", s.stage);

    let actions = s.legal_actions();
    for (i, a) in actions.iter().enumerate() {
        assert!(!actions[..i].contains(a), "duplicate action {a:?}");
        if let Action::Play { card, target } = *a {
            assert_eq!(s.binding.def(card).targeted(), target.is_some(), "target mismatch for {}", s.binding.def(card).name);
        }
        let mut t = s.clone();
        assert!(t.apply_action(*a).is_ok(), "legal action {a:?} failed to apply");
    }
    assert_eq!(actions.is_empty(), s.is_over());
}

/// Every field of a card definition that plays, one line (upgrades-as-data
/// spec: the rewritten files must load to equal definitions). Cost through
/// what every cost reader sees.
pub fn card_dump(d: &sts_engine::cards::CardDef) -> String {
    format!(
        "{} class={:?} cost={} x={} unpl={} ty={:?} exhaust={} ethereal={} playable_if={:?} innate={} tags={} retain={} less_per_hp={} effects={:?} rows={:?} turn_end={:?} exhausted={:?}",
        d.name,
        d.class,
        d.cost(),
        d.x_cost(),
        d.unplayable(),
        d.ty,
        d.exhaust,
        d.ethereal,
        d.playable_if,
        d.innate,
        d.tags,
        d.retain,
        d.cost_less_per_hp_loss,
        d.effects,
        d.rows,
        d.turn_end,
        d.exhausted
    )
}

/// A change to the draw pile, for `game_draw_odds`.
#[derive(Clone, Copy, Debug)]
pub enum PileOp {
    /// `CardGroup.addToRandomSpot`: an empty pile takes the card, else it
    /// goes in at index `random(size - 1)`, 0..=size-1 alike (the top is
    /// the last index), so under the top card.
    RandomSpot(CardId),
    /// `addToTop` (Headbutt, Warcry): the card goes on top.
    Top(CardId),
    /// A uniformly random copy of this kind leaves the pile (Secret
    /// Technique, Violence: the model of docs/specs/colorless-cards.md).
    Remove(CardId),
}

/// The game's chance of each next `k` cards drawn (sorted), from a draw
/// pile whose `known` cards sit on top (`known[0]` drawn next) over
/// `unknown` in random order (every order alike), after `ops` in turn.
/// By enumeration: keep `unknown` small.
pub fn game_draw_odds(known: &[CardId], unknown: &[CardId], ops: &[PileOp], k: usize) -> Vec<(Vec<CardId>, f64)> {
    fn perms(v: &mut Vec<CardId>, i: usize, out: &mut Vec<Vec<CardId>>) {
        if i == v.len() {
            out.push(v.clone());
            return;
        }
        for j in i..v.len() {
            v.swap(i, j);
            perms(v, i + 1, out);
            v.swap(i, j);
        }
    }
    fn walk(pile: Vec<CardId>, ops: &[PileOp], p: f64, k: usize, out: &mut std::collections::BTreeMap<Vec<CardId>, f64>) {
        match ops.first() {
            None => {
                let mut h: Vec<CardId> = pile[pile.len() - k..].to_vec();
                h.sort();
                *out.entry(h).or_default() += p;
            }
            Some(&PileOp::Top(c)) => {
                let mut t = pile;
                t.push(c);
                walk(t, &ops[1..], p, k, out);
            }
            Some(&PileOp::Remove(c)) => {
                let at: Vec<usize> = (0..pile.len()).filter(|&i| pile[i] == c).collect();
                assert!(!at.is_empty(), "a copy to remove");
                for &i in &at {
                    let mut t = pile.clone();
                    t.remove(i);
                    walk(t, &ops[1..], p / at.len() as f64, k, out);
                }
            }
            Some(&PileOp::RandomSpot(c)) if pile.is_empty() => walk(vec![c], &ops[1..], p, k, out),
            Some(&PileOp::RandomSpot(c)) => {
                let n = pile.len();
                for at in 0..n {
                    let mut t = pile.clone();
                    t.insert(at, c);
                    walk(t, &ops[1..], p / n as f64, k, out);
                }
            }
        }
    }
    let mut orders = Vec::new();
    perms(&mut unknown.to_vec(), 0, &mut orders);
    let mut out = std::collections::BTreeMap::new();
    for o in &orders {
        // Bottom first: the unknown cards, then the known ones, the next
        // drawn last.
        let mut pile = o.clone();
        pile.extend(known.iter().rev());
        walk(pile, ops, 1.0 / orders.len() as f64, k, &mut out);
    }
    out.into_iter().collect()
}

/// The engine's chance of each next `k` cards drawn (sorted) from `s`'s
/// draw pile, listed (`k` at most the draw pile's size).
pub fn engine_draw_odds(s: &CombatState, k: u8) -> Vec<(Vec<CardId>, f64)> {
    assert!(k as usize <= s.draw().len());
    let mut t = s.clone();
    t.hand = Hand::default();
    t.pending = Some(ChanceEvent::Draw { n: k });
    let Some(ChanceOutcomes::Listed(v)) = t.chance_outcomes(100_000) else { panic!("listed") };
    let mut out = std::collections::BTreeMap::new();
    for (p, u) in v {
        let mut h: Vec<CardId> = u.hand.iter().flat_map(|(c, n)| std::iter::repeat_n(c, n as usize)).collect();
        h.sort();
        *out.entry(h).or_default() += p;
    }
    out.into_iter().collect()
}

/// `engine_draw_odds` equals `game_draw_odds` for every `k` up to the draw
/// pile's size.
pub fn assert_draw_odds_match(s: &CombatState, known: &[CardId], unknown: &[CardId], ops: &[PileOp]) {
    assert_mixture_odds_match(&[(1.0, s.clone())], known, unknown, ops)
}

/// `assert_draw_odds_match` for the states a chance event left (each with its
/// chance, all of one pile size): the mixture of their odds equals the
/// game's (which copy left is the event's, not the player's to see).
pub fn assert_mixture_odds_match(states: &[(f64, CombatState)], known: &[CardId], unknown: &[CardId], ops: &[PileOp]) {
    let len = states[0].1.draw().len();
    let size = |at: usize, op: &PileOp| if matches!(op, PileOp::Remove(_)) { at - 1 } else { at + 1 };
    assert_eq!(len, ops.iter().fold(known.len() + unknown.len(), size), "the pile the model describes");
    assert!(states.iter().all(|(_, s)| s.draw().len() == len));
    for k in 1..=len {
        let g = game_draw_odds(known, unknown, ops, k);
        let mut e: std::collections::BTreeMap<Vec<CardId>, f64> = Default::default();
        for (w, s) in states {
            for (h, p) in engine_draw_odds(s, k as u8) {
                *e.entry(h).or_default() += w * p;
            }
        }
        assert_eq!(e.keys().collect::<Vec<_>>(), g.iter().map(|x| &x.0).collect::<Vec<_>>(), "draw {k}: hands");
        for ((h, p), (_, q)) in e.iter().zip(&g) {
            assert!((p - q).abs() < 1e-9, "draw {k}: {h:?} engine {p} game {q}");
        }
    }
}
