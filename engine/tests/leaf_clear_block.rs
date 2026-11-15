//! The leaf clear block (docs/specs/leaf-clear-block.md): with
//! `leaf_clear_block`, an end-of-turn leaf is scored with the player's
//! block at 0, as the next StartTurn sets it.

mod common;

use common::*;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::search::{search, Evaluator, Heuristic, SearchConfig};
use sts_engine::*;

/// Records every state it scores; scores by the heuristic.
struct Record(Vec<CombatState>);

impl Evaluator for Record {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        self.0.extend_from_slice(states);
        Heuristic.evaluate(states)
    }
}

/// Jaw Worm (random moves after its first) at 100 HP, a hand of Defends
/// and a Strike, a mixed draw pile; one turn already played, so the next
/// EndTurn waits on the worm's roll with the block left after its attack.
fn setup() -> CombatState {
    let mut s = vs(&[K::JawWorm], &["Defend", "Defend", "Defend", "Strike"], Some(100));
    s.set_draw(Pile::from_cards(&[card("Strike"), card("Strike"), card("Defend"), card("Defend"), card("Defend"), card("Strike")]));
    s.apply_action(Action::EndTurn).expect("end turn");
    let mut rng = Rng::new(7);
    while !s.awaiting_action() {
        s.resolve_chance(&mut rng);
    }
    s.hand = Hand::from_cards(&[card("Defend"), card("Defend"), card("Defend"), card("Strike")]);
    s
}

fn leaves(cfg: &SearchConfig) -> Vec<CombatState> {
    let mut rec = Record(Vec::new());
    search(&setup(), &mut rec, cfg);
    rec.0
}

#[test]
fn leaf_clear_block_scores_without_block() {
    let off = leaves(&SearchConfig::default());
    assert!(off.iter().any(|t| !t.is_over() && t.player.block > 0), "some leaf keeps leftover block");
    let on = leaves(&SearchConfig { leaf_clear_block: true, ..SearchConfig::default() });
    assert!(on.iter().all(|t| t.is_over() || t.player.block == 0), "every leaf scored at block 0");
    let cleared: Vec<_> = off
        .into_iter()
        .map(|mut t| {
            if !t.is_over() {
                t.player.block = 0;
            }
            t
        })
        .collect();
    assert_eq!(on, cleared, "the same leaves, only block changed");
}

/// A pre-draw hook's Block (docs/specs/turn-start-draw.md) belongs to the
/// new turn: once the leaf is past the turn's reset (the draw pending, or
/// the next decision reached when the draw is certain), the clear leaves
/// the block alone and `@tsl1` (post-draw hooks only there) doesn't add it
/// again.
#[test]
fn leaf_clear_block_keeps_pre_draw_block() {
    use sts_engine::monsters::EncounterGroup;
    use sts_engine::registry::{bind, load_pack, relics_named};
    load_pack(r#"{"version": 2, "powers": [
{"id": "LcbPreBlock", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"Block": 5}]}]}
], "relics": [{"id": "Lcb Pre Block", "rarity": "common", "powers": [{"power": "LcbPreBlock", "amount": 1}]}]}"#)
    .unwrap();
    let names: Vec<String> = starter_deck().iter().map(|&c| c.def().name.to_string()).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let (ids, b) = bind(&refs).unwrap();
    let relics = relics_named(&["gen:Lcb Pre Block"]).unwrap();
    let cfg = SearchConfig { leaf_clear_block: true, turn_start_leaf: true, ..SearchConfig::default() };
    // Cultist rolls no move. With 5 cards left to draw 5 the draw is
    // certain (leaves at the next decision); with a deeper pile it is
    // pending (leaves at the draw).
    for (deep, stage) in [(false, Stage::PlayerTurn), (true, Stage::TurnStarted)] {
        let mut s = CombatState::new_with(Character::Ironclad, &ids, &b, 80, 80, &[K::Cultist], EncounterGroup::Hallway, &relics, &mut Rng::new(3));
        if deep {
            s.set_draw(Pile::from_cards(&[card("Strike"), card("Strike"), card("Defend"), card("Defend"), card("Defend"), card("Strike"), card("Bash")]));
        }
        let mut rec = Record(Vec::new());
        search(&s, &mut rec, &cfg);
        let next: Vec<_> = rec.0.iter().filter(|t| !t.is_over() && t.turn == 2).collect();
        assert!(!next.is_empty() && next.iter().all(|t| t.stage == stage), "leaves at {stage:?}");
        assert!(next.iter().all(|t| t.player.block == 5), "the pre-draw Block counted once at {stage:?}");
    }
}
