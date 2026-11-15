//! Check 4: random-combat throughput and clone cost on one thread.
//! `cargo run --release --example bench`

use std::hint::black_box;
use std::time::Instant;
use sts_engine::agent::RandomAgent;
use sts_engine::monsters::EncounterGroup;
use sts_engine::runner::{group_specs, play};
use sts_engine::*;

fn main() {
    // The encounter mix: every group, starter and starter + 5 decks.
    let mut specs = Vec::new();
    for g in [EncounterGroup::Hallway, EncounterGroup::Elite, EncounterGroup::Boss] {
        specs.extend(group_specs(g, 20_000, 5, 1));
    }
    let t = Instant::now();
    let mut wins = 0;
    for spec in &specs {
        wins += play(spec, &mut RandomAgent, false).won as usize;
    }
    let secs = t.elapsed().as_secs_f64();
    let per_min = specs.len() as f64 / secs * 60.0;
    println!("random combats: {} in {secs:.2} s = {per_min:.0} per minute ({wins} won)", specs.len());

    let s = CombatState::new(&starter_deck(), 80, 80, Encounter::SlimeBoss, &mut Rng::new(3));
    let n = 1_000_000;
    let t = Instant::now();
    for _ in 0..n {
        black_box(black_box(&s).clone());
    }
    let ns = t.elapsed().as_nanos() as f64 / n as f64;
    println!("clone: {ns:.1} ns ({} bytes)", std::mem::size_of::<CombatState>());

    assert!(per_min >= 100_000.0, "check 4: need >= 100,000 random combats per minute");
    assert!(ns < 1000.0, "check 4: clone must take under 1 µs");
    println!("check 4: pass");
}
