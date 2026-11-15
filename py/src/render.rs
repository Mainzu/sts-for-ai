//! Text view of a combat.

use std::fmt::Write;

use sts_engine::agent::intent_damage;
use sts_engine::chance::ChanceEvent;
use sts_engine::powers::Powers;
use sts_engine::registry::Binding;
use sts_engine::state::{Action, CombatState, PileRef, Stage, MAX_MONSTERS};

pub fn action_name(a: Action) -> String {
    match a {
        Action::EndTurn => "EndTurn".to_string(),
        Action::Play { card, target: Some(t) } => format!("{} -> slot {t}", card.name()),
        Action::Play { card, target: None } => card.name().to_string(),
        Action::Choose(card) => format!("Choose {}", card.name()),
        Action::Done => "Done".to_string(),
        Action::UsePotion { slot, target: Some(t) } => format!("Potion {slot} -> slot {t}"),
        Action::UsePotion { slot, target: None } => format!("Potion {slot}"),
    }
}

/// A combat's powers, a generated slot by its registry id.
fn powers(p: &Powers, b: &Binding) -> String {
    let v: Vec<String> = b
        .powers_in_play()
        .iter()
        .filter(|&&k| p.get(k) != 0)
        .map(|&k| match b.power_id(k) {
            Some(id) => format!("{id} {}", p.get(k)),
            None => format!("{k:?} {}", p.get(k)),
        })
        .collect();
    if v.is_empty() {
        String::new()
    } else {
        format!("  [{}]", v.join(", "))
    }
}

pub fn pile(p: PileRef<'_>, b: &Binding) -> String {
    let name = |c: sts_engine::CardId| if c.is_official() { c.name() } else { b.def(c).name };
    let v: Vec<String> =
        p.iter().map(|(c, n)| if n == 1 { name(c).to_string() } else { format!("{} x{n}", name(c)) }).collect();
    if v.is_empty() {
        "-".to_string()
    } else {
        v.join(", ")
    }
}

pub fn render(s: &CombatState) -> String {
    let p = &s.player;
    let mut out = String::new();
    let status = match s.stage {
        Stage::Over { won: true } => "  WON".to_string(),
        Stage::Over { won: false } => "  LOST".to_string(),
        _ => String::new(),
    };
    let _ = writeln!(
        out,
        "Turn {}  HP {}/{}  Block {}  Energy {}{}{status}",
        s.turn,
        p.hp,
        p.max_hp,
        p.block,
        p.energy,
        powers(&p.powers, &s.binding)
    );
    // Held potions, by list position (the action's slot): only when held,
    // so a potion-free board reads as before (docs/specs/potions.md).
    if !p.potions.is_empty() {
        let v: Vec<String> = p.potions.iter().enumerate().map(|(i, q)| format!("{i}:{}", q.name())).collect();
        let _ = writeln!(out, "Potions {}", v.join(", "));
    }
    for slot in 0..MAX_MONSTERS {
        let m = &s.monsters[slot];
        if !m.alive() {
            continue;
        }
        let intent = match s.shown_intent(slot) {
            None if s.move_hidden(slot) => format!("hidden ({})", intent_damage(s, slot)),
            Some(mv) => {
                let dmg = intent_damage(s, slot);
                if dmg > 0 { format!("{} ({dmg})", mv.name) } else { mv.name.to_string() }
            }
            None => "?".to_string(),
        };
        let _ = writeln!(
            out,
            "  [{slot}] {}  HP {}/{}  Block {}  intent: {intent}{}",
            m.def().name,
            m.hp,
            m.max_hp,
            m.block,
            powers(&m.powers, &s.binding)
        );
    }
    let _ = writeln!(out, "Hand: {}", pile(s.hand.view(), &s.binding));
    let _ = write!(out, "Draw {} | Discard {} | Exhaust {}", s.draw().len(), s.discard().len(), s.exhaust().len());
    if let Some(e) = s.pending {
        let what = match e {
            ChanceEvent::Draw { n } => format!("draw {n}"),
            ChanceEvent::MonsterMove { slot } => format!("move roll for slot {slot}"),
            ChanceEvent::RandomTarget { amount } => format!("random hit of {amount}"),
            ChanceEvent::PlainHit { amount } => format!("random non-attack hit of {amount}"),
            ChanceEvent::RandomExhaust => "random exhaust from hand".into(),
            ChanceEvent::AllyBlock { slot } => format!("ally pick for slot {slot}'s block"),
            ChanceEvent::TakeTop { .. } => "the draw pile's top card to play".into(),
            ChanceEvent::Order { .. } => "the draw pile's new order".into(),
            ChanceEvent::InsertAt { .. } => "a card's spot in the draw pile".into(),
            ChanceEvent::IntentClass { slot } => format!("whether slot {slot}'s hidden move attacks"),
            ChanceEvent::RolledAmount { slot } => format!("slot {slot}'s rolled attack amount"),
            ChanceEvent::Offer { k, .. } => format!("{k} cards offered"),
            ChanceEvent::RandomPotion { .. } => "random potion".into(),
            ChanceEvent::RandomCost => "random cost for a card in hand".into(),
            ChanceEvent::RandomZeroCost => "random hand card to cost 0".into(),
            ChanceEvent::RandomFreeTurn => "random hand card to cost 0 this turn".into(),
            ChanceEvent::RandomUpgrade => "random hand card upgraded".into(),
            ChanceEvent::ExhaustSave { .. } => "exhaust save roll".into(),
            ChanceEvent::MakeRandom { .. } => "random card made".into(),
            ChanceEvent::DrawInstance { .. } => "which copy leaves the draw pile".into(),
            ChanceEvent::TakeRandom { .. } => "random cards taken from the draw pile".into(),
        };
        let _ = write!(out, "\n(paused at chance event: {what})");
    }
    out
}

/// A combat's powers as `(name, amount)`, named as `render` names them.
pub fn power_list(p: &Powers, b: &Binding) -> Vec<(String, i16)> {
    b.powers_in_play()
        .iter()
        .filter(|&&k| p.get(k) != 0)
        .map(|&k| (b.power_id(k).map_or_else(|| format!("{k:?}"), str::to_string), p.get(k)))
        .collect()
}

/// The pending chance event in `render`'s words.
pub fn pending_text(s: &CombatState) -> Option<String> {
    s.pending.map(|e| match e {
        ChanceEvent::Draw { n } => format!("draw {n}"),
        ChanceEvent::MonsterMove { slot } => format!("move roll for slot {slot}"),
        ChanceEvent::RandomTarget { amount } => format!("random hit of {amount}"),
        ChanceEvent::PlainHit { amount } => format!("random non-attack hit of {amount}"),
        ChanceEvent::RandomExhaust => "random exhaust from hand".into(),
        ChanceEvent::AllyBlock { slot } => format!("ally pick for slot {slot}'s block"),
        ChanceEvent::TakeTop { .. } => "the draw pile's top card to play".into(),
        ChanceEvent::Order { .. } => "the draw pile's new order".into(),
        ChanceEvent::InsertAt { .. } => "a card's spot in the draw pile".into(),
        ChanceEvent::IntentClass { slot } => format!("whether slot {slot}'s hidden move attacks"),
        ChanceEvent::RolledAmount { slot } => format!("slot {slot}'s rolled attack amount"),
        ChanceEvent::Offer { k, .. } => format!("{k} cards offered"),
        ChanceEvent::RandomPotion { .. } => "random potion".into(),
        ChanceEvent::RandomCost => "random cost for a card in hand".into(),
        ChanceEvent::RandomZeroCost => "random hand card to cost 0".into(),
        ChanceEvent::RandomFreeTurn => "random hand card to cost 0 this turn".into(),
        ChanceEvent::RandomUpgrade => "random hand card upgraded".into(),
        ChanceEvent::ExhaustSave { .. } => "exhaust save roll".into(),
        ChanceEvent::MakeRandom { .. } => "random card made".into(),
        ChanceEvent::DrawInstance { .. } => "which copy leaves the draw pile".into(),
        ChanceEvent::TakeRandom { .. } => "random cards taken from the draw pile".into(),
    })
}
