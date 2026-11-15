//! Search + heuristic throughput by thread count, for comparing builds.
//! `cargo run --release --example search_speed`

use std::time::Instant;
use sts_engine::agent::SearchAgent;
use sts_engine::monsters::EncounterGroup;
use sts_engine::runner::{group_specs, play_many};
use sts_engine::search::{Heuristic, SearchConfig};

fn main() {
    let mut specs = Vec::new();
    for g in [EncounterGroup::Hallway, EncounterGroup::Elite, EncounterGroup::Boss] {
        specs.extend(group_specs(g, 200, 5, 7));
    }
    for threads in [1, 2, 4, 8, 16] {
        let t = Instant::now();
        let r = play_many(&specs, || SearchAgent::new(Heuristic, SearchConfig::default()), threads, false);
        let secs = t.elapsed().as_secs_f64();
        let score: f64 = r.iter().map(|x| x.score).sum();
        println!("{threads:2} threads: {:7.1} games/s (score sum {score:.4})", specs.len() as f64 / secs);
    }
}
