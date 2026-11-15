//! Options (distinct choices with their outcomes) and search over them.

mod common;
use common::*;
use sts_engine::agent::{Agent, GreedyAgent, SearchAgent};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::options::Outcome;
use sts_engine::search::{search, Heuristic, SearchConfig};
use sts_engine::*;

fn total_prob(o: &Outcome) -> f64 {
    match o {
        Outcome::Deterministic(_) | Outcome::Divergent(_) => 1.0,
        Outcome::Chance(v) => v.iter().map(|x| x.0).sum(),
    }
}

#[test]
fn options_cover_every_legal_action_once() {
    let s = vs(&[K::JawWorm, K::Cultist], &["Strike", "Strike", "Strike", "Defend", "Bash"], None);
    let opts = s.options(16);
    let mut seen: Vec<Action> = opts.iter().flat_map(|o| o.actions.clone()).collect();
    let n = seen.len();
    seen.dedup();
    assert_eq!(seen.len(), n, "an action appears in two options");
    let mut legal = s.legal_actions();
    legal.sort_by_key(|a| format!("{a:?}"));
    seen.sort_by_key(|a| format!("{a:?}"));
    assert_eq!(seen, legal);
    // Strike ×2 targets, Defend, Bash ×2 targets, EndTurn.
    assert_eq!(opts.len(), 6);
}

#[test]
fn identical_afterstates_are_merged() {
    // Body Slam with no block deals 0: hitting slot 0 or slot 1 leaves the same state.
    let s = vs(&[K::JawWorm, K::JawWorm], &["Body Slam"], Some(40));
    let opts = s.options(16);
    let slam: Vec<_> = opts.iter().filter(|o| o.actions.iter().any(|a| matches!(a, Action::Play { .. }))).collect();
    assert_eq!(slam.len(), 1, "both targets should merge into one option");
    assert_eq!(slam[0].actions.len(), 2);
    assert!(matches!(slam[0].outcome, Outcome::Deterministic(_)));
}

#[test]
fn small_chance_is_listed_and_sums_to_one() {
    // Sword Boomerang: 3 hits on 2 targets → hit splits 3/0, 2/1, 1/2, 0/3.
    let s = vs(&[K::JawWorm, K::JawWorm], &["Sword Boomerang"], Some(40));
    let opts = s.options(16);
    let o = opts.iter().find(|o| o.actions[0] != Action::EndTurn).unwrap();
    let Outcome::Chance(v) = &o.outcome else { panic!("expected listed chance, got {:?}", o.outcome) };
    assert_eq!(v.len(), 4);
    let mut ps: Vec<f64> = v.iter().map(|x| x.0).collect();
    ps.sort_by(f64::total_cmp);
    let want = [0.125, 0.125, 0.375, 0.375];
    for (p, w) in ps.iter().zip(want) {
        assert!((p - w).abs() < 1e-9, "{ps:?}");
    }
    for o in &opts {
        assert!((total_prob(&o.outcome) - 1.0).abs() < 1e-9);
    }
}

#[test]
fn large_events_are_divergent() {
    // Draw 2 from a pile of 8 distinct cards: 28 pairs > limit 16.
    let mut s = vs(&[K::JawWorm], &["Pommel Strike+"], Some(40));
    let pile = ["Strike", "Defend", "Bash", "Anger", "Cleave", "Flex", "Inflame", "Pummel"];
    s.set_draw(Pile::from_cards(&pile.iter().map(|c| card(c)).collect::<Vec<_>>()));
    let opts = s.options(16);
    let pommel = opts.iter().find(|o| o.actions[0] != Action::EndTurn).unwrap();
    let Outcome::Divergent(paused) = &pommel.outcome else { panic!("expected divergent, got {:?}", pommel.outcome) };
    assert!(paused.pending.is_some(), "divergent state pauses at the event");
    // With a big enough limit the same draw is listed.
    let opts = s.options(100);
    let pommel = opts.iter().find(|o| o.actions[0] != Action::EndTurn).unwrap();
    assert!(matches!(pommel.outcome, Outcome::Chance(ref v) if v.len() == 28));
}

#[test]
fn end_turn_with_a_big_draw_is_divergent() {
    // Next turn draws 5 of 10 distinct cards: 252 outcomes.
    let mut s = fresh(Encounter::JawWorm, 3);
    let pile = ["Strike", "Defend", "Bash", "Anger", "Cleave", "Flex", "Inflame", "Pummel", "Clash", "Uppercut"];
    s.set_draw(Pile::from_cards(&pile.iter().map(|c| card(c)).collect::<Vec<_>>()));
    let opts = s.options(16);
    let end = opts.iter().find(|o| o.actions.contains(&Action::EndTurn)).unwrap();
    assert!(matches!(end.outcome, Outcome::Divergent(_)));
}

#[test]
fn search_returns_a_legal_action_and_scores_every_option() {
    let s = fresh(Encounter::Cultist, 5);
    let r = search(&s, &mut Heuristic, &SearchConfig::default());
    assert!(s.is_legal(r.action));
    assert_eq!(r.options.len(), s.options(SearchConfig::default().limit).len());
    for o in &r.options {
        assert!((0.0..=2.0).contains(&o.value), "value {}", o.value);
    }
    let best = r.options.iter().map(|o| o.value).fold(f32::MIN, f32::max);
    let chosen = r.options.iter().find(|o| o.actions.contains(&r.action)).unwrap();
    assert_eq!(chosen.value, best);
}

#[test]
fn search_takes_a_lethal_line() {
    // 3 energy, monster at 12 HP: Strike + Strike kills, ending the turn doesn't.
    let s = vs(&[K::JawWorm], &["Strike", "Strike", "Defend"], Some(12));
    let r = search(&s, &mut Heuristic, &SearchConfig::default());
    assert!(matches!(r.action, Action::Play { card, .. } if card == card_id("Strike")));
}

fn card_id(n: &str) -> CardId {
    card(n)
}

#[test]
fn search_is_deterministic() {
    for cfg in [SearchConfig::default(), SearchConfig { sample_k: 3, turns: 2, seed: 9, ..SearchConfig::default() }] {
        let s = fresh(Encounter::JawWorm, 11);
        let a = search(&s, &mut Heuristic, &cfg);
        let b = search(&s, &mut Heuristic, &cfg);
        assert_eq!(a.action, b.action);
        let va: Vec<f32> = a.options.iter().map(|o| o.value).collect();
        let vb: Vec<f32> = b.options.iter().map(|o| o.value).collect();
        assert_eq!(va, vb);
    }
}

#[test]
fn search_batches_leaves_into_one_call() {
    struct Counting(usize, usize);
    impl sts_engine::search::Evaluator for Counting {
        fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
            self.0 += 1;
            self.1 += states.len();
            Heuristic.evaluate(states)
        }
    }
    let s = fresh(Encounter::JawWorm, 2);
    let mut ev = Counting(0, 0);
    let r = search(&s, &mut ev, &SearchConfig::default());
    assert_eq!(ev.0, 1, "one evaluator call per search");
    assert_eq!(ev.1, r.leaves);
}

#[test]
fn agents_finish_combats() {
    let mut rng = Rng::new(1);
    for mut agent in [Box::new(GreedyAgent) as Box<dyn Agent>, Box::new(SearchAgent::new(Heuristic, SearchConfig::default()))] {
        let mut s = fresh(Encounter::Cultist, 4);
        while !s.is_over() {
            let a = agent.act(&s, &mut rng);
            s.step(a, &mut rng).unwrap();
        }
    }
}

#[test]
fn crn_siblings_share_draws() {
    use sts_engine::search::sample_rng;
    let mut a = with_hand(Encounter::Cultist, &["Strike"], 40);
    let names = ["Strike", "Defend", "Bash", "Anger", "Clothesline", "Cleave", "Iron Wave", "Pommel Strike", "Shrug It Off", "Twin Strike", "Body Slam", "Clash"];
    a.set_draw(Pile::from_cards(&names.iter().map(|n| card(n)).collect::<Vec<_>>()));
    a.pending = Some(ChanceEvent::Draw { n: 3 });
    let mut b = a.clone();
    b.player.block = 7;
    let mut hands = Vec::new();
    for i in 0..4 {
        let (mut x, mut y) = (a.clone(), b.clone());
        x.resolve_chance(&mut sample_rng(5, 2, x.turn, 0, i));
        y.resolve_chance(&mut sample_rng(5, 2, y.turn, 0, i));
        assert_eq!(x.hand, y.hand, "sample {i}: siblings drew different cards");
        hands.push(x.hand);
    }
    hands.dedup();
    assert!(hands.len() > 1, "samples should differ from each other");
}

#[test]
fn cut_counter_counts_cap_leaves() {
    let s = fresh(Encounter::JawWorm, 11);
    let capped = search(&s, &mut Heuristic, &SearchConfig { sample_k: 2, turns: 2, max_nodes: 50, ..SearchConfig::default() });
    assert!(capped.cuts > 0);
    assert!(capped.nodes < 200, "nodes {}", capped.nodes);
    let plain = search(&with_hand(Encounter::Cultist, &["Strike", "Defend"], 40), &mut Heuristic, &SearchConfig::default());
    assert_eq!(plain.cuts, 0);
}

/// Steps `line[..k]` on a clone of `s`: every state before a step awaits an
/// action and the action is legal there (docs/specs/line-step.md).
fn step_line(s: &CombatState, line: &[Action]) -> CombatState {
    let mut t = s.clone();
    for &a in line {
        assert!(t.awaiting_action(), "line reached a state not awaiting an action");
        assert!(t.is_legal(a), "line action {a:?} illegal");
        t.apply_action(a).unwrap();
    }
    t
}

#[test]
fn principal_line_starts_with_the_action_and_is_legal() {
    let s = fresh(Encounter::Cultist, 5);
    for cfg in [SearchConfig::default(), SearchConfig { turns: 2, sample_k: 4, max_nodes: 400_000, ..SearchConfig::default() }] {
        let r = search(&s, &mut Heuristic, &cfg);
        assert_eq!(r.line[0], r.action);
        let end = step_line(&s, &r.line);
        let last = *r.line.last().unwrap();
        assert!(last == Action::EndTurn || end.pending.is_some() || end.is_over(), "line ends mid-turn: {:?}", r.line);
    }
}

#[test]
fn principal_line_matches_re_search() {
    // No draw mid-turn: re-searching from each state on the line picks the line's next action.
    let cfg = SearchConfig { turns: 2, sample_k: 4, max_nodes: 400_000, ..SearchConfig::default() };
    let starts = [
        vs(&[K::JawWorm], &["Strike", "Strike", "Defend", "Bash"], Some(40)),
        vs(&[K::JawWorm, K::Cultist], &["Strike", "Defend", "Bash", "Cleave"], Some(40)),
        vs(&[K::JawWorm], &["Strike", "Strike", "Strike", "Defend", "Defend"], Some(20)),
    ];
    let mut checked = 0;
    for s in &starts {
        let r = search(s, &mut Heuristic, &cfg);
        assert_eq!(r.cuts, 0);
        for k in 1..r.line.len() {
            let t = step_line(s, &r.line[..k]);
            let again = search(&t, &mut Heuristic, &cfg);
            assert_eq!(again.action, r.line[k], "start {s:?}: re-search at step {k} disagrees with line {:?}", r.line);
            checked += 1;
        }
    }
    assert!(checked > 0, "no line had more than one decision");
}

#[test]
fn principal_line_stops_at_chance() {
    // Sword Boomerang is a listed chance event: nothing follows it on the line.
    let s = vs(&[K::JawWorm, K::JawWorm], &["Sword Boomerang", "Strike", "Defend"], Some(40));
    let r = search(&s, &mut Heuristic, &SearchConfig { turns: 2, sample_k: 4, max_nodes: 400_000, ..SearchConfig::default() });
    let end = step_line(&s, &r.line);
    let boomerang = card_id("Sword Boomerang");
    if let Some(i) = r.line.iter().position(|a| matches!(a, Action::Play { card, .. } if *card == boomerang)) {
        assert_eq!(i, r.line.len() - 1, "actions after a chance node: {:?}", r.line);
        assert!(end.pending.is_some());
    } else {
        assert!(*r.line.last().unwrap() == Action::EndTurn || end.pending.is_some() || end.is_over());
    }
}
