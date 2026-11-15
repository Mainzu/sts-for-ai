//! Permanent database of exactly solved combat states (exact solver spec).

pub mod db;
pub mod fingerprint;
mod rows;

pub use db::{is_trivial, DbStore, Position, PositionRow, SolvedDb};
pub use fingerprint::fingerprint;

/// 64-bit FNV-1a: the database's key hash of a state's bytes.
pub fn fnv1a(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x0100_0000_01b3);
    }
    h
}

/// 32-bit FNV-1a: a trivial row's second hash, which confirms a key-hash
/// match without the state's bytes (Amendment 1).
pub fn fnv1a32(bytes: &[u8]) -> u32 {
    let mut h: u32 = 0x811c_9dc5;
    for &b in bytes {
        h ^= b as u32;
        h = h.wrapping_mul(0x0100_0193);
    }
    h
}
