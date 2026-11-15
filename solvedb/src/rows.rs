//! Row blobs: distributions and per-option values, little-endian.

use std::cell::OnceCell;
use sts_engine::codec::{changed_ranks, decode_action_in, encode_action_in, try_decode};
use sts_engine::registry::is_changed;
use sts_engine::{Action, CardId};
use sts_engine::solve::{Distribution, SolvedOption};

fn put_dist(d: &Distribution, out: &mut Vec<u8>) {
    out.extend(d.loss.to_le_bytes());
    out.extend((d.wins.len() as u16).to_le_bytes());
    for &(k, p) in &d.wins {
        out.extend(k.to_le_bytes());
        out.extend(p.to_le_bytes());
    }
}

struct Reader<'a> {
    b: &'a [u8],
    at: usize,
}

impl Reader<'_> {
    fn take<const N: usize>(&mut self) -> Option<[u8; N]> {
        let v = self.b.get(self.at..self.at + N)?.try_into().ok()?;
        self.at += N;
        Some(v)
    }

    fn f64(&mut self) -> Option<f64> {
        Some(f64::from_le_bytes(self.take()?))
    }

    fn u16(&mut self) -> Option<u16> {
        Some(u16::from_le_bytes(self.take()?))
    }

    fn u8(&mut self) -> Option<u8> {
        Some(self.take::<1>()?[0])
    }

    fn dist(&mut self) -> Option<Distribution> {
        let loss = self.f64()?;
        let n = self.u16()?;
        let mut wins = Vec::with_capacity(n as usize);
        for _ in 0..n {
            wins.push((self.u16()?, self.f64()?));
        }
        Some(Distribution { loss, wins })
    }
}

/// A distribution's blob: P(loss), then (HP lost, probability) pairs.
pub fn dist_blob(d: &Distribution) -> Vec<u8> {
    let mut out = Vec::with_capacity(10 + 10 * d.wins.len());
    put_dist(d, &mut out);
    out
}

pub fn dist_from_blob(b: &[u8]) -> Distribution {
    let mut r = Reader { b, at: 0 };
    let d = r.dist().filter(|_| r.at == b.len());
    d.expect("corrupt distribution blob")
}

/// The changed copies the state `root` (codec bytes) names, in rank order:
/// what its options' card bytes from `VARIANT_BASE` on name
/// (docs/specs/sparse-piles.md). Decoded only when an option needs it.
struct Ranks<'a> {
    root: &'a [u8],
    ranks: OnceCell<Vec<CardId>>,
}

impl Ranks<'_> {
    fn get(&self) -> &[CardId] {
        self.ranks.get_or_init(|| try_decode(self.root).map(|s| changed_ranks(&s)).unwrap_or_default())
    }
}

fn names_changed(a: Action) -> bool {
    matches!(a, Action::Play { card, .. } | Action::Choose(card) if is_changed(card))
}

/// The per-option blob of the state `root` (its codec bytes): each option's
/// actions, exact value and (when computed) distribution. A changed copy is
/// written as its rank byte in `root`, as a variant's id was.
pub fn options_blob(root: &[u8], opts: &[SolvedOption]) -> Vec<u8> {
    let ranks = Ranks { root, ranks: OnceCell::new() };
    let mut out = Vec::new();
    out.extend((opts.len() as u16).to_le_bytes());
    for o in opts {
        out.push(o.actions.len() as u8);
        for &a in &o.actions {
            encode_action_in(if names_changed(a) { ranks.get() } else { &[] }, a, &mut out);
        }
        out.extend(o.value.to_le_bytes());
        match &o.dist {
            // 2: an upper bound (solver bounds); older blobs have only 0 and 1.
            None if o.bounded => out.push(2),
            None => out.push(0),
            Some(d) => {
                out.push(1);
                put_dist(d, &mut out);
            }
        }
    }
    out
}

/// The options `options_blob` wrote for the state `root` (its codec bytes).
pub fn options_from_blob(root: &[u8], b: &[u8]) -> Vec<SolvedOption> {
    let ranks = Ranks { root, ranks: OnceCell::new() };
    let read = |b: &[u8]| -> Option<Vec<SolvedOption>> {
        let mut r = Reader { b, at: 0 };
        let n = r.u16()?;
        let mut opts = Vec::with_capacity(n as usize);
        for _ in 0..n {
            let k = r.u8()?;
            let mut actions = Vec::with_capacity(k as usize);
            for _ in 0..k {
                // A card byte from VARIANT_BASE on is a rank (encodable
                // states hold no pack cards).
                let card = r.b.get(r.at + 1).copied().unwrap_or(0);
                let rank = matches!(r.b.get(r.at), Some(1 | 2)) && card as usize >= sts_engine::registry::VARIANT_BASE;
                actions.push(decode_action_in(if rank { ranks.get() } else { &[] }, r.b, &mut r.at)?);
            }
            let value = r.f64()?;
            let (dist, bounded) = match r.u8()? {
                0 => (None, false),
                2 => (None, true),
                _ => (Some(r.dist()?), false),
            };
            opts.push(SolvedOption { actions, value, dist, bounded });
        }
        (r.at == b.len()).then_some(opts)
    };
    read(b).expect("corrupt options blob")
}

#[cfg(test)]
mod tests {
    use super::*;
    use sts_engine::state::Action;

    /// Solver bounds: a bounded option keeps its flag, and a blob written
    /// before them (flag bytes 0 and 1 only) reads as all exact.
    #[test]
    fn bounded_round_trip() {
        let opt = |value, dist, bounded| SolvedOption { actions: vec![Action::EndTurn], value, dist, bounded };
        let d = Distribution { loss: 0.25, wins: vec![(3, 0.75)] };
        let opts = vec![opt(1.5, None, false), opt(1.75, None, true), opt(1.2, Some(d), false)];
        let back = options_from_blob(&[], &options_blob(&[], &opts));
        assert_eq!(back.iter().map(|o| o.bounded).collect::<Vec<_>>(), vec![false, true, false]);
        assert_eq!(back.iter().map(|o| o.value).collect::<Vec<_>>(), vec![1.5, 1.75, 1.2]);
        assert!(back[2].dist.is_some());
        let old = options_blob(&[], &[opt(1.5, None, false)]);
        assert_eq!(*old.last().unwrap(), 0);
        assert!(!options_from_blob(&[], &old)[0].bounded);
    }
}
