//! Exploration for self-play rounds (learned-play switch 4): a search agent
//! may pick its option by softmax over the root option values.

use sts_engine::agent::{softmax_pick, SearchAgent};
use sts_engine::heuristic::Heuristic;
use sts_engine::monsters::EncounterGroup;
use sts_engine::rng::Rng;
use sts_engine::runner::{group_specs, play};
use sts_engine::search::SearchConfig;

#[test]
fn temperature_zero_picks_the_top_option() {
    let mut rng = Rng::new(1);
    assert_eq!(softmax_pick(&[0.1, 0.5, 0.3], 0.0, &mut rng), 1);
    // Ties: the first best, as search picks.
    assert_eq!(softmax_pick(&[0.2, 0.7, 0.7], 0.0, &mut rng), 1);
}

#[test]
fn softmax_picks_follow_their_probabilities() {
    let values = [1.0f32, 1.05, 0.9, 1.1];
    let temp = 0.05f32;
    let w: Vec<f64> = values.iter().map(|&v| ((v - 1.1) / temp).exp() as f64).collect();
    let total: f64 = w.iter().sum();
    let mut counts = [0usize; 4];
    let mut rng = Rng::new(7);
    let n = 10_000;
    for _ in 0..n {
        counts[softmax_pick(&values, temp, &mut rng)] += 1;
    }
    for (i, &c) in counts.iter().enumerate() {
        let p = w[i] / total;
        let f = c as f64 / n as f64;
        // 4 standard errors of a binomial share over 10k draws.
        let tol = 4.0 * (p * (1.0 - p) / n as f64).sqrt() + 1e-9;
        assert!((f - p).abs() <= tol, "option {i}: {f:.4} vs {p:.4}");
    }
}

#[test]
fn exploring_agent_plays_legal_games_and_off_is_unchanged() {
    let specs = group_specs(EncounterGroup::Hallway, 20, 5, 3);
    for spec in &specs {
        let mut plain = SearchAgent::new(Heuristic, SearchConfig::default());
        let mut off = SearchAgent::new(Heuristic, SearchConfig::default());
        off.explore = 0.0;
        let a = play(spec, &mut plain, true);
        let b = play(spec, &mut off, true);
        assert_eq!(a.score, b.score);
        assert_eq!(a.trajectory.iter().map(|t| t.1).collect::<Vec<_>>(), b.trajectory.iter().map(|t| t.1).collect::<Vec<_>>());
        let mut hot = SearchAgent::new(Heuristic, SearchConfig::default());
        hot.explore = 0.5;
        let c = play(spec, &mut hot, true);
        assert!(c.turns > 0);
    }
}
