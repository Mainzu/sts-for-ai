//! The next turn's start draw, as a range (docs/specs/draw-knowledge.md
//! item 2): `CombatState::next_draw`. Read by the net's encoder and tests
//! only; no rule, search or agent path calls it.

use super::*;

/// The player's hooks that draw at a turn's start.
fn is_start_draw(t: Trigger) -> bool {
    matches!(t, Trigger::OwnerTurnStart | Trigger::OwnerTurnStartPostDraw | Trigger::CombatStart | Trigger::CombatStartPreDraw)
}

impl CombatState {
    /// How many cards the next turn's start draws (the turn's draw, its
    /// pre- and post-draw hooks' draws, and the draws of the cards drawn),
    /// as `(min, max)`, capped by the hand's space (`HAND_LIMIT`) but not
    /// by the cards left (the discard still grows; known cards are always
    /// in the draw pile).
    ///
    /// During the player's turn it counts as if the turn ended now: the
    /// cards kept (retained, or Runic Pyramid's) take hand space, the
    /// ethereal cards' exhausts owe their draws (Dark Embrace), and the
    /// turn-end relic hooks move their counters. A range comes from play:
    /// with a turn-start draw hook whose condition isn't `Always`, every
    /// count of further plays from none to the cards in hand is tried
    /// (Pocketwatch: `min` with many plays, `max` with few), card-type
    /// conditions of the play hooks taken as met. A range also comes from
    /// chance: a `CardDrawn` draw hook (Evolve) on an unknown card adds to
    /// `max` only. A future turn-end keep choice makes the kept cards a
    /// range: `min` with the most kept, `max` with the fewest.
    ///
    /// Not counted: draws between now and the next turn's start (Runic
    /// Cube, Centennial Puzzle in the monsters' turn, Gremlin Horn); the
    /// plays the energy allows (the cards in hand bound them); retained
    /// cards still playable count as kept.
    pub fn next_draw(&self) -> (u8, u8) {
        match self.stage {
            Stage::Over { .. } => (0, 0),
            Stage::TurnStarted => {
                let main = match self.pending {
                    Some(ChanceEvent::Draw { n }) => n as u32,
                    _ => 0,
                };
                let mut q = self.clone();
                let mut ctr = self.counters();
                q.finish(&mut ctr, main, false)
            }
            Stage::StartTurn | Stage::RelicOffer { .. } => {
                let mut q = self.clone();
                let mut ctr = self.counters();
                let main = self.main_draw(self.turn, self.owed_draw as u32);
                q.finish(&mut ctr, main, true)
            }
            // The player's turn: as if it ended now.
            Stage::PlayerTurn | Stage::PlayingCard { .. } | Stage::UsingPotion { .. } | Stage::RelicPick { .. } if self.turn >= 1 => {
                self.after_turn_end(true, true)
            }
            // End Turn paused before the hand went (parts 1, 3, 4): the
            // turn-end hooks ran.
            Stage::EndingTurn { part } if part != 2 => self.after_turn_end(true, false),
            // The hand is already the kept one (the monsters' turn, before
            // turn 1, End Turn's part 2).
            _ => self.after_turn_end(false, false),
        }
    }

    /// The relics' counters, to project.
    fn counters(&self) -> Vec<i16> {
        (0..self.player.relics.len()).map(|i| self.player.relics.counter(i)).collect()
    }

    /// The turn's own draw on turn `turn` with `owed` owed to it: the base,
    /// the relics' extra, turn 1's extra, at least the innate cards.
    fn main_draw(&self, turn: u16, owed: u32) -> u32 {
        let mut n = DRAW_PER_TURN as u32 + self.relic_draw() as u32 + owed;
        if turn == 1 {
            n += self.character.first_turn_draw() as u32;
            let innate: u32 = self.draw().iter().filter(|(c, _)| self.binding.def(*c).innate).map(|(_, k)| k as u32).sum();
            n = n.max(innate);
        }
        n
    }

    /// The count from the turn's end on: `hand_left` while the hand is not
    /// yet discarded, `plays` while more cards can still be played.
    fn after_turn_end(&self, hand_left: bool, plays: bool) -> (u8, u8) {
        let ranged = plays && self.has_conditional_start_draw();
        let most = if ranged { self.hand.len() } else { 0 };
        let (mut lo, mut hi) = (u8::MAX, 0u8);
        for k in 0..=most {
            let (a, b) = self.after_plays(k as u8, hand_left, plays);
            lo = lo.min(a);
            hi = hi.max(b);
        }
        (lo, hi)
    }

    /// The count after `k` more plays, then the turn's end.
    fn after_plays(&self, k: u8, hand_left: bool, plays: bool) -> (u8, u8) {
        let mut ctr = self.counters();
        let mut q = self.clone();
        q.cards_played_this_turn = self.cards_played_this_turn.saturating_add(k);
        if plays {
            for _ in 0..k {
                q.relic_counter_pass(&mut ctr, |t| matches!(t, Trigger::CardPlayed { by: Side::Owner } | Trigger::OwnerPlaysCard), true);
            }
            q.relic_counter_pass(&mut ctr, |t| t == Trigger::OwnerTurnEnd, false);
        }
        let mut owed = self.owed_draw as u32;
        if hand_left {
            // The hand at the turn's end (`end_turn_hand`'s tests).
            let keeps_hand = self.player.relics.iter().any(|(id, _)| id.rules().keeps_hand);
            let mut kept = Hand::default();
            for (c, n) in self.hand.iter() {
                let d = self.binding.def(c);
                if d.retain || (!d.ethereal && keeps_hand && d.turn_end.is_empty()) {
                    kept.add(c, n);
                } else if d.ethereal {
                    let ctx = HookCtx { card: Some(c), ..HookCtx::default() };
                    owed += n as u32 * q.hook_draws(&mut ctr, |t| t == Trigger::CardExhausted, ctx, false);
                }
            }
            q.hand = kept;
        }
        // The next turn as it starts.
        q.turn = self.turn + 1;
        q.cards_played_this_turn = 0;
        q.player.powers.just_applied = [0; 2];
        let binding = q.binding;
        for &p in binding.powers_in_play() {
            if q.player.powers.get(p) != 0
                && binding.hooks(p).iter().any(|h| h.trigger == Trigger::OwnerTurnEnd && h.effects.contains(&Effect::RemoveSelf))
            {
                q.player.powers.clear(p);
            }
        }
        let mut pre = 0;
        if q.turn == 1 {
            pre += q.hook_draws(&mut ctr, |t| t == Trigger::CombatStartPreDraw, HookCtx::default(), false);
        } else {
            pre += q.hook_draws(&mut ctr, |t| t == Trigger::OwnerTurnStart, HookCtx::default(), false);
        }
        let main = self.main_draw(q.turn, owed + pre);
        q.finish(&mut ctr, main, true)
    }

    /// The post-draw hooks' draws added to `main` (on turn 1 the fight's
    /// start and the turn-start hooks, which wait for the opening draw),
    /// capped by the hand's space, then the drawn cards' own draws; on a
    /// projected state. `replace_main`: `main` goes through `Replaced::Draw`
    /// (a request still to make).
    fn finish(&mut self, ctr: &mut [i16], main: u32, replace_main: bool) -> (u8, u8) {
        let q = self;
        let main = if replace_main {
            q.replaced(Who::Player, Replaced::Draw, main.min(i16::MAX as u32) as i16).map_or(0, |n| n.max(0) as u32)
        } else {
            main
        };
        let mut total = main;
        if q.turn == 1 {
            total += q.hook_draws(ctr, |t| t == Trigger::CombatStart, HookCtx::default(), true);
        }
        total += q.hook_draws(ctr, |t| t == Trigger::OwnerTurnStartPostDraw, HookCtx::default(), true);
        if q.turn == 1 {
            total += q.hook_draws(ctr, |t| t == Trigger::OwnerTurnStart, HookCtx::default(), true);
        }
        let space = HAND_LIMIT.saturating_sub(q.hand.len()) as u32;
        let d = total.min(space);
        let (lo, hi) = q.drawn_draws(d, space);
        (lo.min(u8::MAX as u32) as u8, hi.min(u8::MAX as u32) as u8)
    }

    /// `d` drawn, plus the draws of `CardDrawn` hooks (Evolve on a Status):
    /// a known card's to both, an unknown card's to the most only while
    /// cards meeting the hook remain (the draw pile's unknown part, then
    /// past it the discard pile).
    fn drawn_draws(&mut self, d: u32, space: u32) -> (u32, u32) {
        if !self.has_draw_hook(|t| t == Trigger::CardDrawn) {
            return (d, d);
        }
        let mut ctr = self.counters();
        let known: Vec<CardId> = self.top.known().collect();
        let mut on = |s: &mut CombatState, c: CardId| {
            let ctx = HookCtx { drawn: Some(s.binding.def(c).ty), ..HookCtx::default() };
            s.hook_draws(&mut ctr, |t| t == Trigger::CardDrawn, ctx, false)
        };
        // The fewest: known positions only.
        let mut lo = d;
        let mut i = 0;
        while i < lo.min(known.len() as u32) {
            lo = (lo + on(self, known[i as usize])).min(space);
            i += 1;
        }
        // The most: each unknown position takes the unused card that draws
        // the most.
        let mut unknown = self.draw().to_pile();
        for &c in &known {
            unknown.remove(c, 1);
        }
        let mut later = self.discard().to_pile();
        let in_draw = self.draw().len() as u32;
        let mut hi = d;
        let mut i = 0;
        while i < hi {
            let extra = if (i as usize) < known.len() {
                on(self, known[i as usize])
            } else {
                let from = if i < in_draw { &mut unknown } else { &mut later };
                let best = from.iter().map(|(c, _)| (on(self, c), c)).max_by_key(|&(n, _)| n);
                match best {
                    Some((n, c)) => {
                        from.remove(c, 1);
                        n
                    }
                    None => 0,
                }
            };
            hi = (hi + extra).min(space);
            i += 1;
        }
        (lo, hi)
    }

    /// Whether the player holds a turn-start draw hook whose condition
    /// isn't `Always` (play may change the count).
    fn has_conditional_start_draw(&self) -> bool {
        let draws = |h: &Hook| is_start_draw(h.trigger) && h.effects.iter().any(|e| matches!(e, Effect::Draw(_))) && (h.condition != Condition::Always || h.also != Condition::Always);
        (0..self.player.relics.len()).any(|i| self.player.relics.id(i).hooks().iter().any(draws))
            || self.binding.powers_in_play().iter().any(|&p| self.player.powers.get(p) > 0 && self.binding.hooks(p).iter().any(draws))
    }

    /// Whether the player holds a `Draw` hook on a trigger `fires` takes.
    fn has_draw_hook(&self, fires: impl Fn(Trigger) -> bool) -> bool {
        let draws = |h: &Hook| fires(h.trigger) && h.effects.iter().any(|e| matches!(e, Effect::Draw(_)));
        (0..self.player.relics.len()).any(|i| self.player.relics.id(i).hooks().iter().any(draws))
            || self.binding.powers_in_play().iter().any(|&p| self.player.powers.get(p) > 0 && self.binding.hooks(p).iter().any(draws))
    }

    /// A relic hook's condition, its relic's counter projected in `ctr`.
    fn relic_holds(&self, ctr: &[i16], i: usize, c: Condition, ctx: HookCtx) -> bool {
        self.relic_condition_holds(ctr[i], c, ctx)
    }

    /// The relics' counter effects of hooks on a trigger `fires` takes, in
    /// list order; `any_card`: other conditions taken as met (a play to
    /// come, its card unknown).
    fn relic_counter_pass(&self, ctr: &mut [i16], fires: impl Fn(Trigger) -> bool, any_card: bool) {
        for i in 0..self.player.relics.len() {
            for h in self.player.relics.id(i).hooks().iter().filter(|h| fires(h.trigger)) {
                let holds = |c| match c {
                    Condition::CounterIs(_) | Condition::CounterAtMost(_) => self.relic_holds(ctr, i, c, HookCtx::default()),
                    _ if any_card => true,
                    c => self.relic_holds(ctr, i, c, HookCtx::default()),
                };
                if !holds(h.condition) || !holds(h.also) {
                    continue;
                }
                for e in h.effects {
                    match *e {
                        Effect::SetCounter(n) => ctr[i] = n,
                        Effect::AddCounter(n) => ctr[i] = ctr[i].saturating_add(n),
                        _ => {}
                    }
                }
            }
        }
    }

    /// The draws of the player's hooks on a trigger `fires` takes, relics
    /// first in list order (by 1, their counters moved in `ctr`), then
    /// powers (by stacks), as `run_hooks_scaled` runs them. `requests`:
    /// each draw is its own request, through `Replaced::Draw`.
    fn hook_draws(&mut self, ctr: &mut [i16], fires: impl Fn(Trigger) -> bool, ctx: HookCtx, requests: bool) -> u32 {
        let mut total = 0u32;
        let mut add = |s: &mut CombatState, n: i32| {
            let n = n.clamp(0, i16::MAX as i32) as i16;
            let n = if requests { s.replaced(Who::Player, Replaced::Draw, n).unwrap_or(0) } else { n };
            total += n.max(0) as u32;
        };
        for i in 0..self.player.relics.len() {
            for h in self.player.relics.id(i).hooks().iter().filter(|h| fires(h.trigger)) {
                if !self.relic_holds(ctr, i, h.condition, ctx) || !self.relic_holds(ctr, i, h.also, ctx) {
                    continue;
                }
                for e in h.effects {
                    match *e {
                        Effect::SetCounter(n) => ctr[i] = n,
                        Effect::AddCounter(n) => ctr[i] = ctr[i].saturating_add(n),
                        Effect::Draw(n) => add(self, n as i32),
                        _ => {}
                    }
                }
            }
        }
        let binding = self.binding;
        for &p in binding.powers_in_play() {
            let stacks = self.player.powers.get(p);
            if stacks <= 0 || self.player.powers.just_applied(p) {
                continue;
            }
            for h in binding.hooks(p).iter().filter(|h| fires(h.trigger)) {
                if !self.condition_holds(Who::Player, h.condition, ctx) || !self.condition_holds(Who::Player, h.also, ctx) {
                    continue;
                }
                for e in h.effects {
                    if let Effect::Draw(n) = *e {
                        add(self, n as i32 * stacks as i32);
                    }
                }
            }
        }
        total
    }
}
