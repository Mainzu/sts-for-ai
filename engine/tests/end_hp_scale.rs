//! The end-HP bonus prices a share of the HP bar, not a fixed HP (ideas#75):
//! c is quoted at 80 max HP, so at 80 nothing changes and at 160 an HP is
//! worth half as much.

use sts_engine::search::{end_hp_scale, SearchConfig};
use sts_engine::*;

fn won(hp: i16, max_hp: i16, start: i16) -> CombatState {
    let mut s = CombatState::new(&starter_deck(), start, max_hp, Encounter::ALL[0], &mut Rng::new(1));
    s.player.hp = hp;
    s.stage = Stage::Over { won: true };
    s
}

#[test]
fn scale_is_exactly_one_at_80() {
    assert_eq!(end_hp_scale(&won(60, 80, 70)), 1.0);
    assert_eq!(end_hp_scale(&won(60, 160, 70)), 0.5);
}

#[test]
fn finished_prices_a_share_of_the_bar() {
    let cfg = SearchConfig { end_hp_price: 0.01, ..SearchConfig::default() };
    // At 80 max HP: the unscaled formula, bit for bit.
    let a = won(60, 80, 70);
    let base = a.score() as f32;
    assert_eq!(cfg.finished(&a), base + 0.01 * (base / 2.0).clamp(0.0, 1.0) * -10.0);
    // The same share of the bar lost at 160 max HP (20 HP) costs the same bonus.
    let b = won(120, 160, 140);
    let bb = b.score() as f32;
    let bonus_a = cfg.finished(&a) - base;
    let bonus_b = cfg.finished(&b) - bb;
    let (fa, fb) = ((base / 2.0).clamp(0.0, 1.0), (bb / 2.0).clamp(0.0, 1.0));
    assert!((bonus_a / fa - bonus_b / fb).abs() < 1e-6, "{bonus_a} vs {bonus_b}");
}
