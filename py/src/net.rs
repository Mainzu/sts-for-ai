//! `stsnet.ValueNet`'s forward pass over an encoded `Batch`, so search can
//! score leaves with a trained net without Python (see
//! docs/specs/rust-inference.md). Weights come from the net's PyTorch state
//! dict at construction; the maths follows `ValueNet.forward` but may sum in
//! a different order (play agreement is what's checked, not bit parity).

use std::collections::HashMap;

use sts_engine::fxhash::FxBuild;
use sts_engine::search::ScoreRule;
use sts_engine::state::{CombatState, MAX_MONSTERS};

use crate::features::{Batch, ENTITIES};

/// Index of the "alive" flag in a monster vector (`stsnet.ALIVE`).
const ALIVE: usize = 0;

/// A linear layer, weights stored transposed ([in][out]) so the inner loop
/// runs over contiguous outputs.
struct Linear {
    w: Vec<f32>,
    b: Vec<f32>,
    n_in: usize,
    n_out: usize,
    /// The activation's slope below zero: 0 is ReLU, else LeakyReLU
    /// (`stsnet.ACTS`; set by `Net::new`).
    slope: f32,
}

impl Linear {
    /// From torch's `weight` [out, in] and `bias` [out].
    fn new(w: &[f32], shape: &[usize], b: &[f32]) -> Result<Linear, String> {
        let &[n_out, n_in] = shape else { return Err(format!("weight shape {shape:?} is not 2-D")) };
        if b.len() != n_out || w.len() != n_out * n_in {
            return Err(format!("weight {shape:?} and bias [{}] don't match", b.len()));
        }
        let mut t = vec![0.0; w.len()];
        for o in 0..n_out {
            for i in 0..n_in {
                t[i * n_out + o] = w[o * n_in + i];
            }
        }
        Ok(Linear { w: t, b: b.to_vec(), n_in, n_out, slope: 0.0 })
    }

    /// `out = x W^T + b`, then the activation (ReLU, or LeakyReLU with
    /// `slope`) when `relu`.
    fn apply(&self, x: &[f32], out: &mut [f32], relu: bool) {
        out.copy_from_slice(&self.b);
        for (i, &xi) in x.iter().enumerate() {
            if xi == 0.0 {
                continue; // post-ReLU inputs are often zero
            }
            let row = &self.w[i * self.n_out..(i + 1) * self.n_out];
            for (o, &w) in out.iter_mut().zip(row) {
                *o += xi * w;
            }
        }
        if relu && self.slope == 0.0 {
            for o in out.iter_mut() {
                *o = o.max(0.0);
            }
        } else if relu {
            for o in out.iter_mut() {
                if *o < 0.0 {
                    *o *= self.slope;
                }
            }
        }
    }
}

/// Two ReLU layers (`stsnet.mlp` with three sizes).
struct Mlp2(Linear, Linear);

impl Mlp2 {
    fn apply(&self, x: &[f32], hidden: &mut Vec<f32>, out: &mut [f32]) {
        hidden.resize(self.0.n_out, 0.0);
        self.0.apply(x, hidden, true);
        self.1.apply(hidden, out, true);
    }
}

/// Per-dimension normaliser: `(x - mean) / std`, as `mean` and `1 / std`.
struct Norm {
    mean: Vec<f32>,
    inv: Vec<f32>,
}

impl Norm {
    fn new(mean: Vec<f32>, std: Vec<f32>) -> Norm {
        Norm { mean, inv: std.iter().map(|s| 1.0 / s).collect() }
    }

    fn apply(&self, x: &[f32], out: &mut [f32]) {
        for (((o, &x), &m), &k) in out.iter_mut().zip(x).zip(&self.mean).zip(&self.inv) {
            *o = (x - m) * k;
        }
    }
}

/// What the head's output means.
pub enum Head {
    /// One logit; the score is `2 * sigmoid`.
    Score,
    /// Logits of a histogram over HP lost; `bin_rep` is the HP lost each bin
    /// stands for (`stsnet.BIN_REP`), the last two bins never win. `rule`
    /// turns the histogram into a score (`external_score`).
    Histogram { bin_rep: Vec<f32>, rule: ScoreRule },
}

impl Head {
    /// The final-score formula this head's scores are on (search scores
    /// finished combats with the same one).
    pub fn rule(&self) -> ScoreRule {
        match self {
            Head::Score => ScoreRule::Engine,
            Head::Histogram { rule, .. } => *rule,
        }
    }
}

/// A trained `ValueNet`.
pub struct Net {
    norm_player: Norm,
    norm_monster: Norm,
    norm_card: Norm,
    norm_row: Norm,
    row: Mlp2,
    card: Mlp2,
    monster: Mlp2,
    player: Linear,
    head: (Linear, Linear, Linear),
    pub head_kind: Head,
    width: usize,
    row_width: usize,
    /// Pile slots in the head's input (from its width; a net saves its own
    /// pile list).
    pub n_piles: usize,
}

/// Per-thread buffers, reused across calls.
#[derive(Default, Clone)]
pub struct Scratch {
    card_rows: Vec<f32>,
    ent_rows: Vec<f32>,
    input: Vec<f32>,
    hidden: Vec<f32>,
    out: Vec<f32>,
    x: Vec<f32>,
    h1: Vec<f32>,
    h2: Vec<f32>,
    /// Layer outputs of the hook rows and cards met in this `forward` call,
    /// by their raw input bits (docs/specs/net-leaf-cache.md).
    row_cache: LayerCache,
    card_cache: LayerCache,
    key: Vec<u32>,
}

/// Outputs of one layer stack, each stored once: input bits -> its offset in
/// `vals`. The same input bits always give the same output, so a hit is exact.
#[derive(Default, Clone)]
struct LayerCache {
    index: HashMap<Box<[u32]>, usize, FxBuild>,
    vals: Vec<f32>,
}

impl LayerCache {
    fn clear(&mut self) {
        self.index.clear();
        self.vals.clear();
    }

    /// Offset of `key`'s output (`width` floats): the stored one, or a new one
    /// `f` computes.
    fn get(&mut self, key: &[u32], width: usize, f: impl FnOnce(&mut [f32])) -> usize {
        if let Some(&at) = self.index.get(key) {
            return at;
        }
        let at = self.vals.len();
        self.vals.resize(at + width, 0.0);
        f(&mut self.vals[at..]);
        self.index.insert(key.into(), at);
        at
    }
}

fn set_bits(key: &mut Vec<u32>, parts: &[&[f32]]) {
    key.clear();
    for p in parts {
        key.extend(p.iter().map(|x| x.to_bits()));
    }
}

/// A tensor from the state dict: values and shape.
pub type Tensor = (Vec<f32>, Vec<usize>);

impl Net {
    /// From a `ValueNet` state dict, the normaliser's `(mean, std)` per key
    /// (`player`, `monsters`, `cards`, `rows`) and the encoder's dimensions
    /// (`player`, `monster`, `card`, `row`), which the weights must fit.
    /// `slope` is the hidden activation's slope below zero (0: ReLU).
    pub fn new(
        state: &HashMap<String, Tensor>,
        norm: HashMap<String, (Vec<f32>, Vec<f32>)>,
        dims: [usize; 4],
        head_kind: Head,
        slope: f32,
    ) -> Result<Net, String> {
        let lin = |name: &str| -> Result<Linear, String> {
            let get = |k: String| state.get(&k).ok_or_else(|| format!("state dict has no {k:?}"));
            let (w, shape) = get(format!("{name}.weight"))?;
            let (b, _) = get(format!("{name}.bias"))?;
            Linear::new(w, shape, b).map(|l| Linear { slope, ..l }).map_err(|e| format!("{name}: {e}"))
        };
        let mut norm = norm;
        let mut nrm = |k: &str, dim: usize| -> Result<Norm, String> {
            let (m, s) = norm.remove(k).ok_or_else(|| format!("normaliser has no {k:?}"))?;
            if m.len() != dim || s.len() != dim {
                return Err(format!("normaliser {k:?} has {} dims, features have {dim}", m.len()));
            }
            Ok(Norm::new(m, s))
        };
        let [dp, dm, dc, dr] = dims;
        let net = Net {
            norm_player: nrm("player", dp)?,
            norm_monster: nrm("monsters", dm)?,
            norm_card: nrm("cards", dc)?,
            norm_row: nrm("rows", dr)?,
            row: Mlp2(lin("row.0")?, lin("row.2")?),
            card: Mlp2(lin("card.0")?, lin("card.2")?),
            monster: Mlp2(lin("monster.0")?, lin("monster.2")?),
            player: lin("player.0")?,
            head: (lin("head.0.0")?, lin("head.0.2")?, lin("head.1")?),
            width: 0,
            row_width: 0,
            n_piles: 0,
            head_kind,
        };
        let (w, rw) = (net.player.n_out, net.row.1.n_out);
        let out = match &net.head_kind {
            Head::Score => 1,
            Head::Histogram { bin_rep, .. } => bin_rep.len(),
        };
        let fits = net.row.0.n_in == dr
            && net.card.0.n_in == dc + rw
            && net.monster.0.n_in == dm + rw
            && net.player.n_in == dp + rw
            && net.card.1.n_out == w
            && net.monster.1.n_out == w
            && net.head.0.n_in >= 3 * w
            && (net.head.0.n_in - 3 * w) % w == 0
            && net.head.2.n_out == out;
        if !fits {
            return Err("the state dict's layer sizes don't fit the features or head".to_string());
        }
        let n_piles = (net.head.0.n_in - 3 * w) / w;
        Ok(Net { width: w, row_width: rw, n_piles, ..net })
    }

    /// Head outputs [B, out] (logits) for a batch.
    pub fn forward(&self, b: &Batch, s: &mut Scratch) -> Vec<f32> {
        let (w, rw, n) = (self.width, self.row_width, b.n);
        let (dp, dm, dc, dr) = (self.norm_player.mean.len(), self.norm_monster.mean.len(), self.norm_card.mean.len(), self.norm_row.mean.len());

        // Hook rows: ψ per row, summed into their card or entity.
        let n_rows = b.row_card.len();
        let n_cards = b.card_count.len();
        s.card_rows.clear();
        s.card_rows.resize(n_cards * rw, 0.0);
        s.ent_rows.clear();
        s.ent_rows.resize(n * ENTITIES * rw, 0.0);
        s.input.resize(dr, 0.0);
        s.row_cache.clear();
        s.card_cache.clear();
        for r in 0..n_rows {
            let dst = match (b.row_card[r], b.row_entity[r]) {
                (c, _) if c >= 0 => &mut s.card_rows[c as usize * rw..(c as usize + 1) * rw],
                (_, e) if e >= 0 => &mut s.ent_rows[e as usize * rw..(e as usize + 1) * rw],
                _ => continue,
            };
            let raw = &b.rows[r * dr..(r + 1) * dr];
            set_bits(&mut s.key, &[raw]);
            let (input, hidden) = (&mut s.input, &mut s.hidden);
            let at = s.row_cache.get(&s.key, rw, |psi| {
                self.norm_row.apply(raw, input);
                self.row.apply(input, hidden, psi);
            });
            for (d, &p) in dst.iter_mut().zip(&s.row_cache.vals[at..at + rw]) {
                *d += p;
            }
        }

        // Head input per state: piles (n_piles x w), monster sum, monster max, player.
        let n_piles = self.n_piles;
        let xw = n_piles * w + 3 * w;
        s.x.clear();
        s.x.resize(n * xw, 0.0);
        s.out.resize(w, 0.0);

        // Cards: φ(card, its rows) x count, summed per (state, pile).
        s.input.resize(dc + rw, 0.0);
        for c in 0..n_cards {
            let (raw, rows) = (&b.cards[c * dc..(c + 1) * dc], &s.card_rows[c * rw..(c + 1) * rw]);
            set_bits(&mut s.key, &[raw, rows]);
            let (input, hidden) = (&mut s.input, &mut s.hidden);
            let phi = s.card_cache.get(&s.key, w, |out| {
                self.norm_card.apply(raw, &mut input[..dc]);
                input[dc..].copy_from_slice(rows);
                self.card.apply(input, hidden, out);
            });
            let at = b.card_state[c] as usize * xw + b.card_pile[c] as usize * w;
            let k = b.card_count[c];
            for (d, &v) in s.x[at..at + w].iter_mut().zip(&s.card_cache.vals[phi..phi + w]) {
                *d += v * k;
            }
        }

        // Monsters: ρ per live slot, summed and max-pooled (outputs are
        // non-negative, so dead slots' zeros never change the max).
        s.input.resize(dm + rw, 0.0);
        for i in 0..n {
            for slot in 0..MAX_MONSTERS {
                let m = &b.monsters[(i * MAX_MONSTERS + slot) * dm..(i * MAX_MONSTERS + slot + 1) * dm];
                if m[ALIVE] <= 0.0 {
                    continue;
                }
                self.norm_monster.apply(m, &mut s.input[..dm]);
                let e = (i * ENTITIES + 1 + slot) * rw;
                s.input[dm..].copy_from_slice(&s.ent_rows[e..e + rw]);
                self.monster.apply(&s.input, &mut s.hidden, &mut s.out);
                let at = i * xw + n_piles * w;
                let (sum, max) = s.x[at..at + 2 * w].split_at_mut(w);
                for ((sm, mx), &v) in sum.iter_mut().zip(max.iter_mut()).zip(&s.out) {
                    *sm += v;
                    *mx = mx.max(v);
                }
            }
        }

        // Player: one layer over (player, its rows).
        s.input.resize(dp + rw, 0.0);
        for i in 0..n {
            self.norm_player.apply(&b.player[i * dp..(i + 1) * dp], &mut s.input[..dp]);
            let e = i * ENTITIES * rw;
            s.input[dp..].copy_from_slice(&s.ent_rows[e..e + rw]);
            let at = i * xw + (n_piles + 2) * w;
            self.player.apply(&s.input, &mut s.x[at..at + w], true);
        }

        // Head.
        let (h0, h1, h2) = &self.head;
        let n_out = h2.n_out;
        let mut y = vec![0.0; n * n_out];
        s.h1.resize(h0.n_out, 0.0);
        s.h2.resize(h1.n_out, 0.0);
        for i in 0..n {
            h0.apply(&s.x[i * xw..(i + 1) * xw], &mut s.h1, true);
            h1.apply(&s.h1, &mut s.h2, true);
            h2.apply(&s.h2, &mut y[i * n_out..(i + 1) * n_out], false);
        }
        y
    }

    /// Scores in [0, 2] of `states` from their head outputs `y`.
    pub fn scores(&self, y: &[f32], states: &[&CombatState]) -> Vec<f32> {
        match &self.head_kind {
            Head::Score => y.iter().map(|&v| 2.0 / (1.0 + (-v).exp())).collect(),
            Head::Histogram { bin_rep, rule } => {
                let nb = bin_rep.len();
                let mut p = vec![0.0; nb];
                states.iter().zip(y.chunks(nb)).map(|(s, logits)| {
                    softmax(logits, &mut p);
                    external_score(&p, bin_rep, *rule, s)
                }).collect()
            }
        }
    }
}

fn softmax(x: &[f32], out: &mut [f32]) {
    let m = x.iter().fold(f32::NEG_INFINITY, |a, &b| a.max(b));
    let mut sum = 0.0;
    for (o, &v) in out.iter_mut().zip(x) {
        *o = (v - m).exp();
        sum += *o;
    }
    for o in out.iter_mut() {
        *o /= sum;
    }
}

/// `stsnet.external_score`: a bin wins when the HP lost it stands for is
/// below the current HP (never the last two bins, >= 150 and turn limit);
/// its end HP is healed by the end-of-combat heal and capped at max HP. A
/// winning bin scores 2 - HP lost since the start / 100 (engine rule) or
/// c + w x end HP / 100 (survive rule).
pub fn external_score(p: &[f32], bin_rep: &[f32], rule: ScoreRule, s: &CombatState) -> f32 {
    let (hp, start, max, heal) = (s.player.hp as f32, s.start_hp as f32, s.player.max_hp as f32, s.win_heal_scaled() as f32);
    let winnable = bin_rep.len() - 2;
    let wins = p[..winnable].iter().zip(bin_rep).filter(|&(_, &rep)| hp - rep > 0.0);
    match rule {
        ScoreRule::Engine => wins.map(|(&q, &rep)| q * (2.0 - (start - (hp - rep + heal).min(max)).max(0.0) / 100.0)).sum(),
        ScoreRule::Survive { c, w } => wins.map(|(&q, &rep)| q * (c + w * (hp - rep + heal).min(max) / 100.0)).sum(),
    }
}
