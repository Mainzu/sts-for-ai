//! A fast non-cryptographic hasher (Fx-style multiply-rotate) for in-memory
//! tables whose order nothing reads: search's state tables and the net
//! evaluator's layer cache. Not for anything stored or compared across runs.

use std::hash::{BuildHasherDefault, Hasher};

/// `HashMap<K, V, FxBuild>`.
pub type FxBuild = BuildHasherDefault<FxHasher>;

#[derive(Default)]
pub struct FxHasher(u64);

const FX_K: u64 = 0xf135_7aea_2e62_a9c5;

impl FxHasher {
    fn add(&mut self, w: u64) {
        self.0 = (self.0 ^ w).wrapping_mul(FX_K);
    }
}

impl Hasher for FxHasher {
    fn write(&mut self, bytes: &[u8]) {
        let mut chunks = bytes.chunks_exact(8);
        for c in &mut chunks {
            self.add(u64::from_le_bytes(c.try_into().unwrap()));
        }
        let rest = chunks.remainder();
        if !rest.is_empty() {
            let mut b = [0u8; 8];
            b[..rest.len()].copy_from_slice(rest);
            self.add(u64::from_le_bytes(b) ^ (rest.len() as u64) << 59);
        }
    }
    fn write_u8(&mut self, i: u8) {
        self.add(i as u64);
    }
    fn write_u16(&mut self, i: u16) {
        self.add(i as u64);
    }
    fn write_u32(&mut self, i: u32) {
        self.add(i as u64);
    }
    fn write_u64(&mut self, i: u64) {
        self.add(i);
    }
    fn write_usize(&mut self, i: usize) {
        self.add(i as u64);
    }
    fn finish(&self) -> u64 {
        // The multiply leaves the low bits weak; hashbrown also reads the top 7.
        self.0.rotate_left(26)
    }
}
