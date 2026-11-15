//! Check 5: strength table. `cargo run --release --example eval [-- N [sample_k [turns]]]`
//! N combats per encounter group (default 500), starter and starter + 5;
//! search settings default to `SearchConfig::default()`.

use std::time::Instant;
use sts_engine::agent::{GreedyAgent, RandomAgent, SearchAgent};
use sts_engine::monsters::EncounterGroup;
use sts_engine::runner::{default_threads, group_specs, play_many, summarize};
use sts_engine::search::{Heuristic, SearchConfig};

fn main() {
    let n: usize = std::env::args().nth(1).map_or(500, |a| a.parse().expect("N"));
    let sample_k: u32 = std::env::args().nth(2).map_or(0, |a| a.parse().expect("sample_k"));
    let turns: u8 = std::env::args().nth(3).map_or(1, |a| a.parse().expect("turns"));
    let cfg = SearchConfig { sample_k, turns, ..SearchConfig::default() };
    let threads = default_threads();
    let groups = [("hallway", EncounterGroup::Hallway), ("elite", EncounterGroup::Elite), ("boss", EncounterGroup::Boss)];
    println!("{n} combats per group, {threads} threads");
    println!("{:<8} {:<8} {:>8} {:>9} {:>7}", "group", "agent", "win %", "HP lost", "secs");
    let mut table = Vec::new();
    for (gname, g) in groups {
        let specs = group_specs(g, n, 5, 1);
        for agent in ["random", "greedy", "search"] {
            let t = Instant::now();
            let results = match agent {
                "random" => play_many(&specs, || RandomAgent, threads, false),
                "greedy" => play_many(&specs, || GreedyAgent, threads, false),
                _ => play_many(&specs, || SearchAgent::new(Heuristic, cfg.clone()), threads, false),
            };
            let (win, lost) = summarize(&results);
            println!("{gname:<8} {agent:<8} {:>8.1} {lost:>9.1} {:>7.1}", win * 100.0, t.elapsed().as_secs_f64());
            table.push((gname, agent, win, lost));
        }
    }
    let get = |g: &str, a: &str| table.iter().find(|r| r.0 == g && r.1 == a).map(|r| (r.2, r.3)).unwrap();
    let mut pass = true;
    for (g, _) in groups {
        let (gw, gl) = get(g, "greedy");
        let (rw, rl) = get(g, "random");
        if !(gw > rw || (gw == rw && gl < rl)) {
            println!("FAIL: greedy doesn't beat random on {g}");
            pass = false;
        }
    }
    let (sw, _) = get("boss", "search");
    let (gw, _) = get("boss", "greedy");
    if (sw - gw) * 100.0 < 15.0 {
        println!("FAIL: search beats greedy on boss win rate by {:.1} points (need 15)", (sw - gw) * 100.0);
        pass = false;
    }
    let (_, sl) = get("hallway", "search");
    let (_, gl) = get("hallway", "greedy");
    if sl > 0.8 * gl {
        println!("FAIL: search hallway HP lost {sl:.1} vs greedy {gl:.1} (need <= {:.1})", 0.8 * gl);
        pass = false;
    }
    println!("check 5: {}", if pass { "pass" } else { "FAIL" });
    if !pass {
        std::process::exit(1);
    }
}
