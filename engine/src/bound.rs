//! Upper bounds on a combat's final score (docs/specs/solver-bounds.md).
//! A won combat scores `2 - HP lost / 100`, HP lost counted after the
//! end-of-combat heal, so without in-fight healing the best still possible
//! is winning now at the current HP. The exact solver skips an option whose
//! bound can't beat the best option already solved.
//!
//! The player's HP rises only through effects, so `Effect::heals` lists
//! every variant with no catch-all arm: healing content doesn't compile
//! until it is classified there. Cards created mid-fight are checked like
//! the rest (`AddCard` is followed), as are the player's powers, the pack
//! powers their hooks apply, and a monster's pack power that puts a healing
//! power on the player.

use std::collections::HashSet;

use crate::cards::CardId;
use crate::effects::Effect;
use crate::registry::Binding;
use crate::powers::Power;
use crate::effects::Target;
use crate::state::{CombatState, Stage};

impl Effect {
    /// Whether the effect can raise the player's HP or max HP.
    pub fn heals(&self) -> bool {
        match self {
            Effect::Damage { .. }
            | Effect::PlainDamage { .. }
            | Effect::CapHp { .. }
            | Effect::ScaledDamage { .. }
            | Effect::RandomDamage { .. }
            | Effect::RandomApply { .. }
            | Effect::RolledAttack
            | Effect::Block(_)
            | Effect::BlockAlly(_)
            | Effect::ScaledBlock { .. }
            | Effect::BlockOf(_)
            | Effect::ExhaustHand { .. }
            | Effect::ExhaustRandom
            | Effect::ZeroCostRandom
            | Effect::ZeroCostRandomTurn
            | Effect::UpgradeRandom
            | Effect::CostAtMost { .. }
            | Effect::TakeRandomFromDraw { .. }
            | Effect::Draw(_)
            | Effect::RandomizeCost(_)
            | Effect::GainEnergy(_)
            | Effect::LoseHp(_)
            | Effect::LoseHpOf(_)
            | Effect::Apply { .. }
            | Effect::ApplyAsMonster { .. }
            | Effect::AddCopy { .. }
            | Effect::ApplyPack { .. }
            | Effect::ApplyOf { .. }
            | Effect::AddCard { .. }
            | Effect::Split
            | Effect::Escape
            | Effect::RemoveSelf
            | Effect::ReduceSelf(_)
            | Effect::Pick { .. }
            | Effect::PlayTop { .. }
            | Effect::ReplayCard
            | Effect::GrowDamage(_)
            | Effect::UpgradeHand
            | Effect::UpgradeAll
            | Effect::ShuffleDiscardIntoDraw
            | Effect::RemoveDebuffs
            | Effect::DrawPicked
            | Effect::SetCounter(_)
            | Effect::AddCounter(_)
            // What it offers is checked by the card (`card_heals`).
            | Effect::Discover { .. }
            | Effect::MakeRandom { .. }
            // What it gives is checked by the potion (`effect_heals`).
            | Effect::ObtainRandomPotions { .. } => false,
            Effect::Heal(_) | Effect::HealOf(_) | Effect::WinHeal(_) | Effect::GainMaxHp(_) => true,
        }
    }
}

/// Whether playing `card` (or a card it adds, or a power it applies) can heal.
fn card_heals(card: CardId, b: &Binding, seen: &mut HashSet<CardId>) -> bool {
    if !seen.insert(card) {
        return false;
    }
    let d = b.def(card);
    d.all_effects().chain(d.turn_end).any(|e| match *e {
        Effect::AddCard { card, .. } => card_heals(card, b, seen),
        Effect::Discover { pool, ty, .. } | Effect::MakeRandom { pool, ty, .. } => {
            crate::registry::pool_cards(b, pool, ty).iter().any(|&c| card_heals(c, b, seen))
        }
        Effect::Apply { power, .. } | Effect::ApplyOf { power, .. } | Effect::RandomApply { power, .. } => power_heals(power, b, &mut HashSet::new()),
        _ => e.heals(),
    })
}

/// Whether a hook of `p`, or of a pack power its hooks apply (transitively),
/// heals.
fn power_heals(p: Power, b: &Binding, seen: &mut HashSet<Power>) -> bool {
    if !seen.insert(p) {
        return false;
    }
    b.hooks(p).iter().flat_map(|h| h.effects).any(|e| match *e {
        Effect::ApplyPack { power, .. } => power_heals(b.slot_of(power), b, seen),
        Effect::MakeRandom { pool, ty, .. } => crate::registry::pool_cards(b, pool, ty).iter().any(|&c| card_heals(c, b, &mut HashSet::new())),
        _ => e.heals(),
    })
}

/// Whether a monster's power `p` puts a healing pack power on the player.
fn gives_heal(p: Power, b: &Binding) -> bool {
    b.hooks(p).iter().flat_map(|h| h.effects).any(|e| match *e {
        Effect::ApplyPack { power, target, .. } if target != Target::Me => power_heals(b.slot_of(power), b, &mut HashSet::new()),
        _ => false,
    })
}

impl CombatState {
    /// Whether the player could still gain HP or max HP in this combat: a
    /// healing effect on a card in hand, a pile or in play (or on a card or
    /// power those bring), in a hook of a power or relic the player has, or
    /// in a potion held or in use.
    pub fn can_heal(&self) -> bool {
        let mut seen = HashSet::new();
        let in_play = match self.stage {
            Stage::PlayingCard { card, .. } => Some(card),
            _ => None,
        };
        let in_use = match self.stage {
            Stage::UsingPotion { potion, .. } => Some(potion),
            _ => None,
        };
        let piles = self.all_piles();
        piles.iter().flat_map(|p| p.iter().map(|(c, _)| c)).chain(in_play).any(|c| card_heals(c, &self.binding, &mut seen))
            || self.binding.powers_in_play().iter().any(|&p| {
                (self.player.powers.get(p) > 0 && power_heals(p, &self.binding, &mut HashSet::new()))
                    || (self.monsters.iter().any(|m| m.alive() && m.powers.get(p) > 0) && gives_heal(p, &self.binding))
            })
            // A potion-use hook (Toy Ornithopter) only while a potion is held or in use.
            || self
                .player
                .relics
                .iter()
                .flat_map(|(id, _)| id.hooks())
                .filter(|h| h.trigger != crate::hooks::Trigger::OwnerUsedPotion || !self.player.potions.is_empty() || in_use.is_some())
                .flat_map(|h| h.effects)
                .any(|e| self.effect_heals(e))
            // Held potions, and the one in use (potions spec).
            || self.player.potions.iter().chain(in_use).filter_map(|p| p.spec()).flat_map(|p| p.effects()).any(|e| self.effect_heals(e))
    }

    /// Whether an effect run by the player (a relic's hook, a potion) can
    /// heal: itself, or the card it adds or the power it applies.
    fn effect_heals(&self, e: &Effect) -> bool {
        match *e {
            Effect::ApplyPack { power, .. } => power_heals(self.binding.slot_of(power), &self.binding, &mut HashSet::new()),
            Effect::AddCard { card, .. } => card_heals(card, &self.binding, &mut HashSet::new()),
            Effect::Discover { pool, ty, .. } | Effect::MakeRandom { pool, ty, .. } => {
                let Some(pool) = crate::registry::fight_pool(pool, self.character) else { return false };
                crate::registry::pool_cards(&self.binding, pool, ty).iter().any(|&c| card_heals(c, &self.binding, &mut HashSet::new()))
            }
            Effect::Apply { power, .. } | Effect::ApplyOf { power, .. } | Effect::RandomApply { power, .. } => power_heals(power, &self.binding, &mut HashSet::new()),
            // A potion it can give heals (a pool's own `ObtainRandomPotions`,
            // the Brew in its pool, adds nothing more).
            Effect::ObtainRandomPotions { pool } => crate::potions::potion_pool(pool)
                .potions()
                .filter_map(|p| p.spec())
                .flat_map(|p| p.effects())
                .any(|e| !matches!(e, Effect::ObtainRandomPotions { .. }) && self.effect_heals(e)),
            _ => e.heals(),
        }
    }

    /// The highest final score still possible: the score of winning at the
    /// highest HP the player could end on. Without healing left that is the
    /// current HP plus the end-of-combat heal (none in no-death mode); with
    /// any healing left, full HP, which is at least the starting HP, so 2.
    /// A finished combat's bound is its score.
    pub fn upper_bound(&self) -> f64 {
        if self.is_over() {
            return self.score();
        }
        if self.can_heal() {
            return 2.0;
        }
        let hp = if self.no_death {
            self.player.hp
        } else {
            (self.player.hp + self.win_heal_scaled()).min(self.player.max_hp)
        };
        // In no-death mode a win far below 0 HP scores under a loss's 0.
        (2.0 - (self.start_hp - hp).max(0) as f64 / 100.0).max(0.0)
    }
}
