//! Seeded PRNG, the `Chance` interface random procedures are written against,
//! and an enumerator that turns such a procedure into its exact distribution.

/// xoshiro256** seeded through splitmix64. Small, fast and `Clone`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Rng {
    s: [u64; 4],
}

fn splitmix(x: &mut u64) -> u64 {
    *x = x.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut z = *x;
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    z ^ (z >> 31)
}

impl Rng {
    pub fn new(seed: u64) -> Rng {
        let mut x = seed;
        let mut s = [0; 4];
        for v in &mut s {
            *v = splitmix(&mut x);
        }
        Rng { s }
    }

    pub fn next_u64(&mut self) -> u64 {
        let result = self.s[1].wrapping_mul(5).rotate_left(7).wrapping_mul(9);
        let t = self.s[1] << 17;
        self.s[2] ^= self.s[0];
        self.s[3] ^= self.s[1];
        self.s[1] ^= self.s[2];
        self.s[0] ^= self.s[3];
        self.s[2] ^= t;
        self.s[3] = self.s[3].rotate_left(45);
        result
    }

    /// Uniform in `0..n`, unbiased. `n` must be > 0.
    pub fn below(&mut self, n: u32) -> u32 {
        let n = n as u64;
        let zone = u64::MAX - (u64::MAX % n);
        loop {
            let x = self.next_u64();
            if x < zone {
                return (x % n) as u32;
            }
        }
    }

    /// Uniform in `[0, 1)`.
    pub fn unit(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }
}

/// Source of randomness for game procedures (monster AI, random targets).
/// Written against this trait, a procedure can be sampled with an `Rng`
/// or listed exactly with [`enumerate`].
pub trait Chance {
    /// Uniform in `0..n`.
    fn below(&mut self, n: u32) -> u32;
    /// True with probability `p`.
    fn chance(&mut self, p: f64) -> bool;
}

impl Chance for Rng {
    fn below(&mut self, n: u32) -> u32 {
        Rng::below(self, n)
    }
    fn chance(&mut self, p: f64) -> bool {
        self.unit() < p
    }
}

/// Replays one path of choices; extends the path with choice 0 past its end.
struct Replay<'a> {
    path: &'a mut Vec<u32>,
    arity: &'a mut Vec<u32>,
    pos: usize,
    prob: f64,
}

impl Replay<'_> {
    fn pick(&mut self, n: u32) -> u32 {
        if self.pos == self.path.len() {
            self.path.push(0);
            self.arity.push(n);
        }
        let c = self.path[self.pos];
        self.pos += 1;
        c
    }
}

impl Chance for Replay<'_> {
    fn below(&mut self, n: u32) -> u32 {
        let c = self.pick(n);
        self.prob /= n as f64;
        c
    }
    fn chance(&mut self, p: f64) -> bool {
        if self.pick(2) == 0 {
            self.prob *= p;
            true
        } else {
            self.prob *= 1.0 - p;
            false
        }
    }
}

/// Exact distribution of a random procedure: runs it once per path through
/// its random calls and sums the probability of equal results. The procedure
/// must make the same calls whenever it gets the same answers.
pub fn enumerate<T: PartialEq>(mut f: impl FnMut(&mut dyn Chance) -> T) -> Vec<(T, f64)> {
    let mut out: Vec<(T, f64)> = Vec::new();
    let mut path = Vec::new();
    let mut arity = Vec::new();
    loop {
        let mut r = Replay { path: &mut path, arity: &mut arity, pos: 0, prob: 1.0 };
        let v = f(&mut r);
        let (pos, p) = (r.pos, r.prob);
        path.truncate(pos);
        arity.truncate(pos);
        if p > 0.0 {
            match out.iter_mut().find(|(o, _)| *o == v) {
                Some((_, q)) => *q += p,
                None => out.push((v, p)),
            }
        }
        // Next path, odometer style.
        loop {
            let Some(last) = path.last_mut() else { return out };
            let i = arity.len() - 1;
            if *last + 1 < arity[i] {
                *last += 1;
                break;
            }
            path.pop();
            arity.pop();
        }
    }
}
