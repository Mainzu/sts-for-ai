//! Pile speed probe for docs/specs/sparse-piles.md. Standalone, no crates:
//!   rustc -C opt-level=3 -C target-cpu=native docs/specs/sparse-piles-probe.rs -o target/pile_probe.exe
//!   target/pile_probe.exe
//! (`target/` is the workspace build dir: `cargo clean` or deleting the .exe/.pdb removes it.)
//!
//! Layouts:
//!   A  today: ids [u8; 40], counts [u8; 40], n (81 bytes), order = id
//!   B  ids [u16; 40] handles, counts [u8; 40], n (121 bytes); order = handle for a
//!      plain copy, a table-read u64 key for a parameterised one (handle >= PARAM)
//!   B10  as B with capacity 10 (the hand)
//!   C  inline value key [u32; 40] (base u16 | params u16), counts, n (201 bytes)
//!   D  dense [u8; 256] counts (the pre-sparse-state layout, reference)
//! State proxy: 4 piles + filler so layout A totals 744 bytes (today's CombatState);
//! the other layouts carry the same filler, so their size difference is the piles'.

use std::hash::{Hash, Hasher};
use std::hint::black_box;
use std::time::Instant;

#[derive(Default)]
struct Fx(u64);
const FX_K: u64 = 0xf135_7aea_2e62_a9c5;
impl Fx {
    fn add(&mut self, w: u64) {
        self.0 = (self.0 ^ w).wrapping_mul(FX_K);
    }
}
impl Hasher for Fx {
    fn write(&mut self, bytes: &[u8]) {
        let mut ch = bytes.chunks_exact(8);
        for c in &mut ch {
            self.add(u64::from_le_bytes(c.try_into().unwrap()));
        }
        let r = ch.remainder();
        if !r.is_empty() {
            let mut b = [0u8; 8];
            b[..r.len()].copy_from_slice(r);
            self.add(u64::from_le_bytes(b) ^ (r.len() as u64) << 59);
        }
    }
    fn write_u8(&mut self, i: u8) { self.add(i as u64) }
    fn write_u16(&mut self, i: u16) { self.add(i as u64) }
    fn write_u32(&mut self, i: u32) { self.add(i as u64) }
    fn write_u64(&mut self, i: u64) { self.add(i) }
    fn write_usize(&mut self, i: usize) { self.add(i as u64) }
    fn finish(&self) -> u64 { self.0.rotate_left(26) }
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn below(&mut self, n: u32) -> u32 { (self.next() % n as u64) as u32 }
}

const PARAM: u16 = 0x8000;
/// Order keys of parameterised handles (a static table, read without a lock).
static mut ORD: [u64; 4096] = [0; 4096];
#[inline]
fn ord16(h: u16) -> u64 {
    if h < PARAM { (h as u64) << 48 } else { unsafe { ORD[(h - PARAM) as usize] } }
}

trait Id: Copy + Eq + Hash + Default + std::fmt::Debug {
    fn ord(self) -> u64;
    fn from_card(c: u32) -> Self;
}
impl Id for u8 {
    #[inline] fn ord(self) -> u64 { self as u64 }
    fn from_card(c: u32) -> u8 { c as u8 }
}
impl Id for u16 {
    #[inline] fn ord(self) -> u64 { ord16(self) }
    fn from_card(c: u32) -> u16 { c as u16 }
}
impl Id for u32 {
    #[inline] fn ord(self) -> u64 { self as u64 }
    fn from_card(c: u32) -> u32 { c }
}

trait PileOps: Copy + Default + Eq + Hash {
    type I: Id;
    fn count(&self, c: Self::I) -> u8;
    fn add(&mut self, c: Self::I, n: u8);
    fn remove(&mut self, c: Self::I, n: u8);
    fn len(&self) -> usize;
    fn nth(&self, i: usize) -> Self::I;
    fn for_each(&self, f: impl FnMut(Self::I, u8));
}

/// `U`: hash only the entries in use (tails are zero by invariant, so equal
/// piles still hash equal); otherwise as derived (whole arrays).
#[derive(Clone, Copy, PartialEq, Eq)]
struct List<T: Id, const N: usize, const U: bool = false> { ids: [T; N], counts: [u8; N], n: u8 }
impl<T: Id, const N: usize, const U: bool> Hash for List<T, N, U> {
    fn hash<S: Hasher>(&self, h: &mut S) {
        if U {
            let n = self.n as usize;
            self.ids[..n].hash(h);
            h.write(&self.counts[..n]);
        } else {
            self.ids.hash(h);
            self.counts.hash(h);
            self.n.hash(h);
        }
    }
}
impl<T: Id, const N: usize, const U: bool> Default for List<T, N, U> {
    fn default() -> Self { List { ids: [T::default(); N], counts: [0; N], n: 0 } }
}
impl<T: Id, const N: usize, const U: bool> List<T, N, U> {
    #[inline]
    fn find(&self, c: T) -> Result<usize, usize> {
        // Equality scan first (no table reads), then the order scan for an insert.
        for i in 0..self.n as usize {
            if self.ids[i] == c { return Ok(i); }
        }
        let k = c.ord();
        for i in 0..self.n as usize {
            if self.ids[i].ord() > k { return Err(i); }
        }
        Err(self.n as usize)
    }
}
impl<T: Id, const N: usize, const U: bool> PileOps for List<T, N, U> {
    type I = T;
    #[inline]
    fn count(&self, c: T) -> u8 {
        for i in 0..self.n as usize {
            if self.ids[i] == c { return self.counts[i]; }
        }
        0
    }
    #[inline]
    fn add(&mut self, c: T, n: u8) {
        match self.find(c) {
            Ok(i) => self.counts[i] += n,
            Err(i) => {
                let len = self.n as usize;
                assert!(len < N);
                self.ids.copy_within(i..len, i + 1);
                self.counts.copy_within(i..len, i + 1);
                self.ids[i] = c;
                self.counts[i] = n;
                self.n += 1;
            }
        }
    }
    #[inline]
    fn remove(&mut self, c: T, n: u8) {
        let i = (0..self.n as usize).find(|&i| self.ids[i] == c).expect("held");
        self.counts[i] -= n;
        if self.counts[i] == 0 {
            let len = self.n as usize;
            self.ids.copy_within(i + 1..len, i);
            self.counts.copy_within(i + 1..len, i);
            self.ids[len - 1] = T::default();
            self.counts[len - 1] = 0;
            self.n -= 1;
        }
    }
    #[inline]
    fn len(&self) -> usize { self.counts[..self.n as usize].iter().map(|&n| n as usize).sum() }
    #[inline]
    fn nth(&self, mut i: usize) -> T {
        for k in 0..self.n as usize {
            let n = self.counts[k] as usize;
            if i < n { return self.ids[k]; }
            i -= n;
        }
        panic!()
    }
    #[inline]
    fn for_each(&self, mut f: impl FnMut(T, u8)) {
        for k in 0..self.n as usize { f(self.ids[k], self.counts[k]) }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct Dense { c: [u8; 256] }
impl Default for Dense { fn default() -> Self { Dense { c: [0; 256] } } }
impl PileOps for Dense {
    type I = u8;
    #[inline] fn count(&self, c: u8) -> u8 { self.c[c as usize] }
    #[inline] fn add(&mut self, c: u8, n: u8) { self.c[c as usize] += n }
    #[inline] fn remove(&mut self, c: u8, n: u8) { self.c[c as usize] -= n }
    #[inline] fn len(&self) -> usize { self.c.iter().map(|&n| n as usize).sum() }
    #[inline]
    fn nth(&self, mut i: usize) -> u8 {
        for (k, &n) in self.c.iter().enumerate() {
            if i < n as usize { return k as u8; }
            i -= n as usize;
        }
        panic!()
    }
    #[inline]
    fn for_each(&self, mut f: impl FnMut(u8, u8)) {
        for (k, &n) in self.c.iter().enumerate() { if n > 0 { f(k as u8, n) } }
    }
}

const FILL: usize = 744 - 4 * 81;
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct State<H: PileOps, P: PileOps<I = H::I>> { hand: H, draw: P, discard: P, exhaust: P, rest: [u8; FILL] }

/// Draw, discard and exhaust sharing one entry list of capacity `M`: entries
/// sorted by pile (lengths in `lens`), then by order within the pile, so each
/// pile is a contiguous run. Hashes only the entries in use.
#[derive(Clone, Copy, PartialEq, Eq)]
struct Shared<const M: usize> { ids: [u16; M], counts: [u8; M], lens: [u8; 3] }
impl<const M: usize> Default for Shared<M> {
    fn default() -> Self { Shared { ids: [0; M], counts: [0; M], lens: [0; 3] } }
}
impl<const M: usize> Hash for Shared<M> {
    fn hash<S: Hasher>(&self, h: &mut S) {
        let n = self.total();
        self.ids[..n].hash(h);
        h.write(&self.counts[..n]);
        h.write(&self.lens);
    }
}
impl<const M: usize> Shared<M> {
    #[inline] fn total(&self) -> usize { self.lens[0] as usize + self.lens[1] as usize + self.lens[2] as usize }
    #[inline]
    fn range(&self, k: usize) -> (usize, usize) {
        let s = match k { 0 => 0, 1 => self.lens[0] as usize, _ => self.lens[0] as usize + self.lens[1] as usize };
        (s, s + self.lens[k] as usize)
    }
    #[inline]
    fn count(&self, k: usize, c: u16) -> u8 {
        let (a, b) = self.range(k);
        for i in a..b { if self.ids[i] == c { return self.counts[i]; } }
        0
    }
    #[inline]
    fn add(&mut self, k: usize, c: u16, n: u8) {
        let (a, b) = self.range(k);
        for i in a..b { if self.ids[i] == c { self.counts[i] += n; return; } }
        let o = ord16(c);
        let mut i = b;
        for j in a..b { if ord16(self.ids[j]) > o { i = j; break; } }
        let t = self.total();
        assert!(t < M);
        self.ids.copy_within(i..t, i + 1);
        self.counts.copy_within(i..t, i + 1);
        self.ids[i] = c;
        self.counts[i] = n;
        self.lens[k] += 1;
    }
    #[inline]
    fn remove(&mut self, k: usize, c: u16, n: u8) {
        let (a, b) = self.range(k);
        let i = (a..b).find(|&i| self.ids[i] == c).expect("held");
        self.counts[i] -= n;
        if self.counts[i] == 0 {
            let t = self.total();
            self.ids.copy_within(i + 1..t, i);
            self.counts.copy_within(i + 1..t, i);
            self.ids[t - 1] = 0;
            self.counts[t - 1] = 0;
            self.lens[k] -= 1;
        }
    }
    #[inline]
    fn len(&self, k: usize) -> usize { let (a, b) = self.range(k); self.counts[a..b].iter().map(|&n| n as usize).sum() }
    #[inline]
    fn nth(&self, k: usize, mut i: usize) -> u16 {
        let (a, b) = self.range(k);
        for j in a..b { let n = self.counts[j] as usize; if i < n { return self.ids[j]; } i -= n; }
        panic!()
    }
    #[inline]
    fn each(&self, k: usize, mut f: impl FnMut(u16, u8)) { let (a, b) = self.range(k); for j in a..b { f(self.ids[j], self.counts[j]) } }
    fn clear(&mut self, k: usize) {
        let (a, b) = self.range(k);
        let t = self.total();
        self.ids.copy_within(b..t, a);
        self.counts.copy_within(b..t, a);
        let m = t - (b - a);
        self.ids[m..t].fill(0);
        self.counts[m..t].fill(0);
        self.lens[k] = 0;
    }
}
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct SState<H: PileOps<I = u16>, const M: usize> { hand: H, piles: Shared<M>, rest: [u8; FILL] }

/// What `turn` and `bench` need of a state: the hand, and piles 0 draw,
/// 1 discard, 2 exhaust.
trait Piles: Copy + Eq + Hash {
    type I: Id;
    type H: PileOps<I = Self::I>;
    fn new() -> Self;
    fn hand(&mut self) -> &mut Self::H;
    fn hand_ref(&self) -> &Self::H;
    fn count(&self, k: usize, c: Self::I) -> u8;
    fn add(&mut self, k: usize, c: Self::I, n: u8);
    fn remove(&mut self, k: usize, c: Self::I, n: u8);
    fn len(&self, k: usize) -> usize;
    fn nth(&self, k: usize, i: usize) -> Self::I;
    fn each(&self, k: usize, f: impl FnMut(Self::I, u8));
    fn clear(&mut self, k: usize);
}
impl<H: PileOps, P: PileOps<I = H::I>> State<H, P> {
    #[inline] fn p(&self, k: usize) -> &P { match k { 0 => &self.draw, 1 => &self.discard, _ => &self.exhaust } }
    #[inline] fn pm(&mut self, k: usize) -> &mut P { match k { 0 => &mut self.draw, 1 => &mut self.discard, _ => &mut self.exhaust } }
}
impl<H: PileOps, P: PileOps<I = H::I>> Piles for State<H, P> {
    type I = H::I;
    type H = H;
    fn new() -> Self { State { hand: H::default(), draw: P::default(), discard: P::default(), exhaust: P::default(), rest: [7; FILL] } }
    fn hand(&mut self) -> &mut H { &mut self.hand }
    fn hand_ref(&self) -> &H { &self.hand }
    #[inline] fn count(&self, k: usize, c: H::I) -> u8 { self.p(k).count(c) }
    #[inline] fn add(&mut self, k: usize, c: H::I, n: u8) { self.pm(k).add(c, n) }
    #[inline] fn remove(&mut self, k: usize, c: H::I, n: u8) { self.pm(k).remove(c, n) }
    #[inline] fn len(&self, k: usize) -> usize { self.p(k).len() }
    #[inline] fn nth(&self, k: usize, i: usize) -> H::I { self.p(k).nth(i) }
    #[inline] fn each(&self, k: usize, f: impl FnMut(H::I, u8)) { self.p(k).for_each(f) }
    fn clear(&mut self, k: usize) { *self.pm(k) = P::default() }
}
impl<H: PileOps<I = u16>, const M: usize> Piles for SState<H, M> {
    type I = u16;
    type H = H;
    fn new() -> Self { SState { hand: H::default(), piles: Shared::default(), rest: [7; FILL] } }
    fn hand(&mut self) -> &mut H { &mut self.hand }
    fn hand_ref(&self) -> &H { &self.hand }
    #[inline] fn count(&self, k: usize, c: u16) -> u8 { self.piles.count(k, c) }
    #[inline] fn add(&mut self, k: usize, c: u16, n: u8) { self.piles.add(k, c, n) }
    #[inline] fn remove(&mut self, k: usize, c: u16, n: u8) { self.piles.remove(k, c, n) }
    #[inline] fn len(&self, k: usize) -> usize { self.piles.len(k) }
    #[inline] fn nth(&self, k: usize, i: usize) -> u16 { self.piles.nth(k, i) }
    #[inline] fn each(&self, k: usize, f: impl FnMut(u16, u8)) { self.piles.each(k, f) }
    fn clear(&mut self, k: usize) { self.piles.clear(k) }
}

/// A deck of `distinct` copies (ids spread over 0..148, or param handles for a
/// fraction `param` of them), `cards` cards in all, shuffled into draw.
fn deck(rng: &mut Rng, distinct: usize, cards: usize, param: f64, wide: bool) -> Vec<u32> {
    let mut ids: Vec<u32> = Vec::new();
    while ids.len() < distinct {
        let c = if wide && (rng.next() % 1000) as f64 / 1000.0 < param {
            PARAM as u32 + rng.below(4096)
        } else {
            rng.below(148)
        };
        if !ids.contains(&c) { ids.push(c); }
    }
    (0..cards).map(|i| ids[i % distinct]).collect()
}

/// One simulated turn: draw 5 (sample + move), scan hand (legal actions), play 4
/// to discard (the last may exhaust), reshuffle when draw runs out, discard the hand.
fn turn<S: Piles>(s: &mut S, rng: &mut Rng, acc: &mut u64) {
    for _ in 0..5 {
        if s.len(0) == 0 {
            let d = *s;
            d.each(1, |c, n| s.add(0, c, n));
            s.clear(1);
            if s.len(0) == 0 { break; }
        }
        let c = s.nth(0, rng.below(s.len(0) as u32) as usize);
        s.remove(0, c, 1);
        s.hand().add(c, 1);
    }
    let mut legal = 0u64;
    s.hand_ref().for_each(|c, n| legal += n as u64 + c.ord() as u64 & 1);
    *acc += legal;
    for k in 0..4 {
        if s.hand_ref().len() == 0 { break; }
        let c = s.hand_ref().nth(rng.below(s.hand_ref().len() as u32) as usize);
        *acc += s.count(1, c) as u64;
        s.hand().remove(c, 1);
        if k == 3 && rng.below(4) == 0 { s.add(2, c, 1) } else { s.add(1, c, 1) }
    }
    let h = *s.hand_ref();
    h.for_each(|c, n| s.add(1, c, n));
    *s.hand() = S::H::default();
}

fn bench<S: Piles>(distinct: usize, cards: usize, param: f64, wide: bool) -> [f64; 4] {
    let mut rng = Rng(0x9e3779b97f4a7c15 ^ distinct as u64);
    // Start states, each a deck in draw after a few turns.
    let mut states: Vec<S> = (0..64)
        .map(|_| {
            let mut s = S::new();
            for c in deck(&mut rng, distinct, cards, param, wide) { s.add(0, S::I::from_card(c), 1); }
            s
        })
        .collect();
    let mut acc = 0u64;
    for s in states.iter_mut() { for _ in 0..3 { turn(s, &mut rng, &mut acc); } }
    let reps = 50_000;
    // Turn work.
    let t = Instant::now();
    for r in 0..reps { let s = &mut states[r & 63]; turn(s, &mut rng, &mut acc); }
    let turn_ns = t.elapsed().as_nanos() as f64 / reps as f64;
    // Clone + hash + eq (search's per-node work on whole states).
    let t = Instant::now();
    for r in 0..reps * 5 {
        let s = black_box(&states[r & 63]);
        let c = *s;
        let mut f = Fx::default();
        c.hash(&mut f);
        acc ^= f.finish();
        acc += (black_box(&c) == s) as u64;
    }
    let che_ns = t.elapsed().as_nanos() as f64 / (reps * 5) as f64;
    // Count lookups in hand and draw.
    let t = Instant::now();
    for r in 0..reps * 5 {
        let s = &states[r & 63];
        let c = S::I::from_card(rng.below(148));
        acc += s.hand_ref().count(c) as u64 + s.count(0, c) as u64;
    }
    let cnt_ns = t.elapsed().as_nanos() as f64 / (reps * 5) as f64;
    black_box(acc);
    [std::mem::size_of::<S>() as f64, turn_ns, che_ns, cnt_ns]
}

fn main() {
    // Parameterised order keys: value-derived, region after the low slots.
    for i in 0..4096u64 { unsafe { ORD[i as usize] = (164u64 << 48) | (i * 2654435761 % 4096) << 16 | i; } }
    type F = fn(usize, usize, f64, bool) -> [f64; 4];
    let cfgs: [(&str, F, f64, bool); 14] = [
        ("A", bench::<State<List<u8, 40>, List<u8, 40>>>, 0.0, false),
        ("B", bench::<State<List<u16, 40>, List<u16, 40>>>, 0.0, true),
        ("B", bench::<State<List<u16, 40>, List<u16, 40>>>, 0.3, true),
        ("B10", bench::<State<List<u16, 10>, List<u16, 40>>>, 0.0, true),
        ("B10", bench::<State<List<u16, 10>, List<u16, 40>>>, 0.3, true),
        ("C", bench::<State<List<u32, 40>, List<u32, 40>>>, 0.0, false),
        ("Au", bench::<State<List<u8, 40, true>, List<u8, 40, true>>>, 0.0, false),
        ("B10u", bench::<State<List<u16, 10, true>, List<u16, 40, true>>>, 0.0, true),
        ("B10u", bench::<State<List<u16, 10, true>, List<u16, 40, true>>>, 0.3, true),
        ("D", bench::<State<Dense, Dense>>, 0.0, false),
        ("S64", bench::<SState<List<u16, 10, true>, 64>>, 0.0, true),
        ("S64", bench::<SState<List<u16, 10, true>, 64>>, 0.3, true),
        ("S96", bench::<SState<List<u16, 10, true>, 96>>, 0.0, true),
        ("S96", bench::<SState<List<u16, 10, true>, 96>>, 0.3, true),
    ];
    let rounds: usize = std::env::args().nth(1).map_or(21, |a| a.parse().unwrap());
    for &(d, c) in &[(5, 10), (15, 25), (25, 35)] {
        let mut res: Vec<Vec<[f64; 4]>> = vec![Vec::new(); cfgs.len()];
        // Interleaved rounds, medians: the machine is shared.
        for _ in 0..rounds {
            for (k, &(_, f, p, w)) in cfgs.iter().enumerate() { res[k].push(f(d, c, p, w)); }
        }
        println!("-- {d} distinct copies, {c} cards ({rounds} interleaved rounds, medians; ratio to A)");
        let med = |v: &Vec<[f64; 4]>, j: usize| { let mut x: Vec<f64> = v.iter().map(|r| r[j]).collect(); x.sort_by(|a, b| a.partial_cmp(b).unwrap()); x[x.len() / 2] };
        let a: Vec<f64> = (1..4).map(|j| med(&res[0], j)).collect();
        for (k, &(name, _, p, _)) in cfgs.iter().enumerate() {
            let m: Vec<f64> = (1..4).map(|j| med(&res[k], j)).collect();
            println!("{name:<4} param {p:.1} size {:>4} B | turn {:6.1} ns ({:.2}) | clone+hash+eq {:6.1} ns ({:.2}) | 2 counts {:5.1} ns ({:.2})",
                res[k][0][0], m[0], m[0] / a[0], m[1], m[1] / a[1], m[2], m[2] / a[2]);
        }
    }
}
