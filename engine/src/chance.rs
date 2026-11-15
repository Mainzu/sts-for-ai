//! Chance nodes. When the rules hit a random event with more than one
//! possible result, the state pauses with `pending` set. The outcomes can be
//! listed with probabilities (when there are few) or one can be sampled.

use crate::monsters::MoveId;
use crate::rng::{enumerate, Chance, Rng};
use crate::effects::Effect;
use crate::hooks::Replaced;
use crate::cards::CardId;
use crate::state::{CombatState, Hand, PileRef, Queued, Run, Stage, Who, HAND_LIMIT};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum ChanceEvent {
    /// The player draws `n` cards (reshuffling the discard pile if needed).
    Draw { n: u8 },
    /// The monster in `slot` picks its next move.
    MonsterMove { slot: u8 },
    /// One hit of `amount` on a uniformly random living enemy: damage for
    /// Sword Boomerang, a power for Bouncing Flask (whichever random-target
    /// effect the card in play is resolving).
    RandomTarget { amount: i16 },
    /// One uniformly random card in hand (by copies) is exhausted (True Grit).
    RandomExhaust,
    /// The monster in `slot` gives its move's `BlockAlly` to a uniformly
    /// random other living monster, then rolls its next move.
    AllyBlock { slot: u8 },
    /// The draw pile's top card goes to the queue of cards to play, with a
    /// uniformly random living enemy as its target when it takes one
    /// (`Effect::PlayTop`; docs/specs/act1-singles.md).
    TakeTop { exhaust: bool },
    /// A `Discover` shows `k` different cards of pool `pool` (of type `ty`
    /// when given), every combination alike (docs/specs/discovery.md).
    Offer { pool: u8, ty: Option<crate::cards::CardType>, k: u8 },
    /// One `MakeRandom` roll: a card of pool `pool` (of type `ty` when
    /// given), every card alike, made as the effect says; `up` when the
    /// card in play is upgraded and the effect matches its level.
    MakeRandom { pool: u8, ty: Option<crate::cards::CardType>, pile: crate::effects::PileKind, zero_cost: bool, free: bool, up: bool },
    /// One potion of potion pool `pool` goes into an empty slot: its
    /// rarity by the 65/25/10 roll, then one of that rarity alike
    /// (`ObtainRandomPotions`; docs/specs/act1-singles.md section 5).
    RandomPotion { pool: u8 },
    /// The first copy waiting in `CombatState::cost_rolls` gets cost 0, 1,
    /// 2 or 3 for the combat, alike (the game's `cardRandomRng.random(3)`;
    /// docs/specs/sparse-piles.md).
    RandomCost,
    /// One hand card picked by `CombatState::zero_cost_choices`'s weights
    /// costs 0 for the combat (`Effect::ZeroCostRandom`, Madness).
    RandomZeroCost,
    /// One hand card picked by `CombatState::free_turn_choices`'s weights
    /// costs 0 this turn (`Effect::ZeroCostRandomTurn`, Mummified Hand).
    RandomFreeTurn,
    /// One hand copy picked by `CombatState::upgrade_choices`'s weights is
    /// upgraded (`Effect::UpgradeRandom`, Warped Tongs).
    RandomUpgrade,
    /// A played card that would exhaust goes to the discard pile instead,
    /// with `CombatState::exhaust_save_chance` (relics' `exhaust_save`:
    /// Strange Spoon; docs/specs/blocked-relics.md step 7). `queued`: the
    /// card is the front of the queue of cards to play, unplayed; else the
    /// card in play.
    ExhaustSave { queued: bool },
    /// `amount` non-attack damage on a uniformly random living enemy: a
    /// `PlainDamage` with `Target::RandomOpponent` (Juggernaut's hit, owed
    /// by its hook).
    PlainHit { amount: i16 },
}

/// Where the draw pile's next card comes from (`CombatState::top_cards`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum TopPick {
    /// Nothing is known: a card by counts.
    Plain,
    /// A copy of the floater entry with nothing above it
    /// (`Top::floaters_on_top`).
    Floater(u8),
    /// The known head.
    Head,
    /// Only floaters are known: a card that is none of them.
    Unknown,
}

#[derive(Clone, Debug)]
pub enum ChanceOutcomes {
    /// Every distinct resulting state with its probability (summing to 1),
    /// each run forward to its next decision or chance event.
    Listed(Vec<(f64, CombatState)>),
    /// More distinct outcomes than the limit.
    Large,
}

/// Every `k`-element subset of `0..n`, as sorted indices.
fn combinations(n: usize, k: usize) -> Vec<Vec<usize>> {
    fn rec(start: usize, n: usize, k: usize, cur: &mut Vec<usize>, out: &mut Vec<Vec<usize>>) {
        if cur.len() == k {
            out.push(cur.clone());
            return;
        }
        for i in start..n {
            cur.push(i);
            rec(i + 1, n, k, cur, out);
            cur.pop();
        }
    }
    let mut out = Vec::new();
    rec(0, n, k, &mut Vec::new(), &mut out);
    out
}

fn binom(n: usize, k: usize) -> f64 {
    (0..k).fold(1.0, |acc, i| acc * (n - i) as f64 / (i + 1) as f64)
}

/// Distinct multisets drawn when drawing `n` from `draw`, reshuffling
/// `discard` into it once `draw` runs out, with their probabilities.
/// `None` if there are more than `limit`. The cards drawn go to the hand,
/// so `n` is at most `HAND_LIMIT` and each outcome fits a `Hand`.
pub fn draw_outcomes(draw: PileRef<'_>, discard: PileRef<'_>, n: usize, limit: usize) -> Option<Vec<(Hand, f64)>> {
    let k = draw.len();
    // Past the draw pile's size, all of it is drawn and the rest comes from the reshuffled discard.
    let (base, src, m) = if n <= k { (Hand::default(), draw, n) } else { (Hand::from_pile(draw), discard, n - k) };
    let kinds: Vec<_> = src.iter().collect();
    let mut suffix = vec![0usize; kinds.len() + 1];
    for i in (0..kinds.len()).rev() {
        suffix[i] = suffix[i + 1] + kinds[i].1 as usize;
    }
    let denom = binom(src.len(), m);
    let mut out = Vec::new();

    #[allow(clippy::too_many_arguments)]
    fn rec(
        kinds: &[(crate::cards::CardId, u8)],
        suffix: &[usize],
        i: usize,
        left: usize,
        cur: &mut Hand,
        weight: f64,
        denom: f64,
        limit: usize,
        out: &mut Vec<(Hand, f64)>,
    ) -> bool {
        if left == 0 {
            if out.len() == limit {
                return false;
            }
            out.push((*cur, weight / denom));
            return true;
        }
        if suffix[i] < left {
            return true;
        }
        let (c, have) = kinds[i];
        for x in 0..=(have as usize).min(left) {
            cur.add(c, x as u8);
            let ok = rec(kinds, suffix, i + 1, left - x, cur, weight * binom(have as usize, x), denom, limit, out);
            cur.remove(c, x as u8);
            if !ok {
                return false;
            }
        }
        true
    }

    let mut cur = base;
    rec(&kinds, &suffix, 0, m, &mut cur, 1.0, denom, limit, &mut out).then_some(out)
}

impl CombatState {
    /// Exact distribution of the next move for the monster in `slot`.
    /// Cached per (kind, level, slot, move history, allies bit), which is
    /// all a pattern reads (`monsters::PatCond`; `tests/monsters.rs::ai_reads_only_moves`).
    pub fn move_distribution(&self, slot: usize) -> Vec<(MoveId, f64)> {
        use std::cell::RefCell;
        use std::collections::HashMap;
        type Key = (crate::monsters::MonsterKind, crate::monsters::Ascension, u8, [MoveId; 2], bool);
        thread_local! {
            static CACHE: RefCell<HashMap<Key, Vec<(MoveId, f64)>, crate::fxhash::FxBuild>> = RefCell::new(HashMap::default());
        }
        let m = &self.monsters[slot];
        let key = (m.kind, m.ascension, slot as u8, m.moves, crate::monsters::allies_bit(self, slot));
        if let Some(v) = CACHE.with(|c| c.borrow().get(&key).cloned()) {
            return v;
        }
        let ai = m.def().ai;
        let v = enumerate(|c| ai(self, slot, c));
        CACHE.with(|c| c.borrow_mut().insert(key, v.clone()));
        v
    }

    pub(crate) fn request_monster_move(&mut self, slot: usize) {
        let dist = self.move_distribution(slot);
        if let [(m, _)] = dist[..] {
            self.set_monster_move(slot, m);
        } else {
            self.pending = Some(ChanceEvent::MonsterMove { slot: slot as u8 });
        }
    }

    /// The block the move monster `slot` just ran gives an ally, if any.
    pub(crate) fn ally_block_owed(&self, slot: usize) -> Option<i16> {
        let mv = self.monsters[slot].intent_def()?;
        mv.effects.iter().find_map(|e| if let Effect::BlockAlly(n) = *e { Some(n) } else { None })
    }

    /// Monster `slot`'s `BlockAlly` (its move on show, still running at the
    /// pick) goes to `to` (the game's `addBlock`: nothing modifies it); the
    /// monsters' turn goes on at its `Stage::MonsterActing`.
    pub(crate) fn give_ally_block(&mut self, slot: usize, to: usize) {
        let n = self.ally_block_owed(slot).unwrap_or(0);
        self.monsters[to].block = crate::state::gained_block(self.monsters[to].block, n);
    }

    /// Monster `slot` rolls its next move (its `BlockAlly` was given in the
    /// monsters' turn).
    pub(crate) fn request_roll(&mut self, slot: usize) {
        self.request_monster_move(slot)
    }

    /// One random-target hit; pauses only while more than one enemy lives.
    pub(crate) fn request_random_hit(&mut self, amount: i16) {
        let two = {
            let mut living = self.living_slots();
            (living.next(), living.next())
        };
        match two {
            (None, _) => {}
            (Some(slot), None) => self.random_hit(slot, amount),
            _ => self.pending = Some(ChanceEvent::RandomTarget { amount }),
        }
    }

    /// One random-target `PlainDamage`; pauses only while more than one
    /// enemy lives.
    pub(crate) fn request_plain_hit(&mut self, amount: i16) {
        let two = {
            let mut living = self.living_slots();
            (living.next(), living.next())
        };
        match two {
            (None, _) => {}
            (Some(slot), None) => self.plain_hit(slot, amount),
            _ => self.pending = Some(ChanceEvent::PlainHit { amount }),
        }
    }

    /// Exhausts one random card in hand; pauses only while the hand holds
    /// two distinct cards.
    pub(crate) fn request_random_exhaust(&mut self) {
        let two = {
            let mut it = self.hand.iter();
            (it.next(), it.next())
        };
        match two {
            (None, _) => {}
            (Some((c, _)), None) => self.exhaust_from_hand(c),
            _ => self.pending = Some(ChanceEvent::RandomExhaust),
        }
    }

    /// The hand cards `ZeroCostRandom` picks from, with the copies of each
    /// it may pick: copies costing above 0 this turn (unmarked), else, when
    /// none does, the marked copies of cards costing above 0 (the game's
    /// `costForTurn > 0`, else `cost > 0`). X-cost and unplayable cards
    /// never qualify.
    pub(crate) fn zero_cost_choices(&self) -> Vec<(CardId, u8)> {
        let costs = |c: CardId| {
            let d = self.binding.def(c);
            !d.x_cost() && !d.unplayable() && self.unmarked_cost(c) > 0
        };
        let all: Vec<(CardId, u8)> = self.hand.iter().filter(|&(c, _)| costs(c)).collect();
        let turn: Vec<(CardId, u8)> =
            all.iter().map(|&(c, n)| (c, n - self.free_in_hand.count(c).min(n))).filter(|&(_, n)| n > 0).collect();
        if turn.is_empty() { all } else { turn }
    }

    /// Makes one random qualifying hand card cost 0 for the combat; pauses
    /// only while two distinct cards qualify.
    pub(crate) fn request_zero_cost(&mut self) {
        let choices = self.zero_cost_choices();
        match choices.len() {
            0 => {}
            1 => self.zero_cost(choices[0].0),
            _ => self.pending = Some(ChanceEvent::RandomZeroCost),
        }
    }

    /// One qualifying copy of `c` costs 0 for the combat: a marked copy
    /// only when every copy is marked (the second tier).
    fn zero_cost(&mut self, c: CardId) {
        let marked = self.free_in_hand.count(c) >= self.hand.count(c);
        self.set_combat_cost(c, 0, marked);
    }

    /// The hand cards `ZeroCostRandomTurn` picks from, with the copies of
    /// each it may pick: unmarked copies costing above 0 this turn (the
    /// game's `cost > 0 && costForTurn > 0 && !freeToPlayOnce`), with no
    /// fallback. X-cost and unplayable cards never qualify.
    pub(crate) fn free_turn_choices(&self) -> Vec<(CardId, u8)> {
        self.hand
            .iter()
            .filter(|&(c, _)| {
                let d = self.binding.def(c);
                !d.x_cost() && !d.unplayable() && self.unmarked_cost(c) > 0
            })
            .map(|(c, n)| (c, n - self.free_in_hand.count(c).min(n)))
            .filter(|&(_, n)| n > 0)
            .collect()
    }

    /// Marks one random qualifying hand card to cost 0 this turn; pauses
    /// only while two distinct cards qualify.
    pub(crate) fn request_free_turn(&mut self) {
        let choices = self.free_turn_choices();
        match choices.len() {
            0 => {}
            1 => {
                self.mark_free_in_hand(choices[0].0);
            }
            _ => self.pending = Some(ChanceEvent::RandomFreeTurn),
        }
    }

    /// The hand copies `UpgradeRandom` picks from: each card a general
    /// upgrade can raise (`PickKind::UpgradeFromHand`'s test: not a
    /// status, not at its max level), its unmarked and its marked copies
    /// apart (`marked`), with their counts.
    pub(crate) fn upgrade_choices(&self) -> Vec<(CardId, bool, u8)> {
        let mut out = Vec::new();
        for (c, n) in self.hand.iter() {
            if !crate::registry::general_upgrade(self.binding.def(c)) {
                continue;
            }
            let m = self.free_in_hand.count(c).min(n);
            if n > m {
                out.push((c, false, n - m));
            }
            if m > 0 {
                out.push((c, true, m));
            }
        }
        out
    }

    /// Upgrades one random qualifying hand copy; pauses only while two
    /// distinct copies qualify.
    pub(crate) fn request_upgrade_random(&mut self) {
        let choices = self.upgrade_choices();
        match choices.len() {
            0 => {}
            1 => self.upgrade_copy(choices[0].0, choices[0].1),
            _ => self.pending = Some(ChanceEvent::RandomUpgrade),
        }
    }

    fn exhaust_from_hand(&mut self, c: CardId) {
        self.hand_remove(c, 1);
        self.exhaust_card(c, 1);
    }

    /// `amount` non-attack damage on the monster in `slot`, as a
    /// `PlainDamage` deals it (the game's THORNS hit: no Strength, Weak or
    /// Vulnerable, block absorbs it).
    fn plain_hit(&mut self, slot: usize, amount: i16) {
        self.do_effect(Who::Player, &Effect::PlainDamage { amount, target: crate::effects::Target::Opponent }, Some(slot as u8));
        self.check_over();
    }

    fn random_hit(&mut self, slot: usize, amount: i16) {
        let effect = match self.stage {
            Stage::PlayingCard { card, next, .. } => self.binding.def(card).effect_at(next as usize).map(|at| at.effect),
            Stage::UsingPotion { potion, next, .. } => potion.spec().and_then(|p| p.effect_at(next as usize)).map(|at| at.effect),
            _ => None,
        };
        match effect {
            Some(Effect::RandomApply { power, .. }) => self.apply_power(Who::Player, Who::Monster(slot as u8), power, amount),
            _ => {
                // The hits add up from the effect's first (its count is
                // raised as each is asked for).
                let first = matches!(self.stage, Stage::PlayingCard { hit: 1, .. } | Stage::UsingPotion { hit: 1, .. } | Stage::RelicPick { hit: 1, .. });
                let before = if first { 0 } else { self.dealt };
                let took = self.attack(Who::Player, Who::Monster(slot as u8), amount);
                self.dealt = before.saturating_add(took);
            }
        }
        self.check_over();
    }

    /// Draws `n` (capped by hand space and cards left); pauses only when the
    /// result is uncertain. A draw already pending in this pass takes these
    /// cards too (Gremlin Horn on two deaths from one Cleave draws 2;
    /// docs/specs/fight-vocabulary.md).
    pub(crate) fn request_draw(&mut self, n: u8) {
        // The player's `Draw` replacements (No Draw) act on this request
        // only, before any pending draw is taken: a draw requested before
        // the power arrived (Battle Trance's own) still resolves.
        let Some(n) = self.replaced(Who::Player, Replaced::Draw, n as i16) else { return };
        let n = n.clamp(0, u8::MAX as i16) as u8;
        let k = match self.pending {
            Some(ChanceEvent::Draw { n: k }) => {
                self.pending = None;
                k as usize
            }
            _ => 0,
        };
        let space = HAND_LIMIT.saturating_sub(self.hand.len());
        let (d, dd) = (self.draw().len(), self.discard().len());
        // The game's `onShuffle` (DrawCardAction): this request against the
        // piles as they are once the pending `k` are drawn, capped by the
        // hand's space. It shuffles when it needs more than the draw pile
        // (some card left in either pile), and again when it needs more
        // than both with a non-empty discard (the follow-up draw's check).
        let part = (n as usize).min(space.saturating_sub(k));
        let (d2, dd2) = if k <= d { (d - k, dd) } else { ((d + dd).saturating_sub(k), 0) };
        let shuffles = (part > d2 && d2 + dd2 > 0) as u8 + (part > d2 + dd2 && dd2 > 0) as u8;
        for _ in 0..shuffles {
            self.fire_shuffled();
        }
        let n = (k + n as usize).min(space).min(d + dd);
        if n == 0 {
            return;
        }
        if !self.top.is_empty() {
            match self.top_draw_states(n, 1) {
                Some(mut v) => *self = v.pop().expect("one outcome").1,
                None => self.pending = Some(ChanceEvent::Draw { n: n as u8 }),
            }
            return;
        }
        match draw_outcomes(self.draw(), self.discard(), n, 1) {
            Some(v) => self.apply_draw(&v[0].0),
            None => self.pending = Some(ChanceEvent::Draw { n: n as u8 }),
        }
    }

    /// `PlayTop`'s next card (docs/specs/act1-singles.md): the discard pile
    /// is reshuffled in when the draw pile is empty, then the top card is
    /// taken at once when it and its target are certain, else `TakeTop`
    /// pauses. The caller checks some card is left in either pile.
    pub(crate) fn request_take_top(&mut self, exhaust: bool) {
        if self.draw().is_empty() {
            // PlayTopCardAction's EmptyDeckShuffleAction (`onShuffle`).
            self.fire_shuffled();
            self.piles.move_all(Run::Discard, Run::Draw);
        }
        let cards = self.top_cards();
        if cards.len() == 1 {
            let (_, c, pick) = cards[0];
            let targets = self.top_targets(c);
            if targets.len() == 1 {
                self.take_top(c, pick, targets[0], exhaust);
                return;
            }
        }
        self.pending = Some(ChanceEvent::TakeTop { exhaust });
    }

    /// The top card's kinds with integer weights (the chance of each is its
    /// weight over their sum) and where each comes from (draw-knowledge
    /// spec item 1). From the newest floater entry to the oldest: one with
    /// nothing above it is on top, when no newer one is, with chance copies
    /// / (the pile's size less every floater put in after it: those went in
    /// under the top). What is left is the known head's, or with only
    /// floaters known, spread evenly over the cards that are no floater.
    pub(crate) fn top_cards(&self) -> Vec<(u64, CardId, TopPick)> {
        if self.top.is_empty() {
            return self.draw().iter().map(|(c, k)| (k as u64, c, TopPick::Plain)).collect();
        }
        let n = self.draw().len() as u64;
        let entries: Vec<(CardId, u8, u8)> = self.top.floater_entries().collect();
        // Newest first: each free entry's (entry, card, copies, denominator).
        let mut free = Vec::new();
        let mut newer = 0u64;
        for (i, &(c, a, k)) in entries.iter().enumerate().rev() {
            if a == 0 {
                free.push((i as u8, c, k as u64, n - newer));
            }
            newer += k as u64;
        }
        // Free entry j's weight: its copies, times (d - k) of each newer one,
        // times d of each older one; the rest: the product of (d - k).
        let mut w: Vec<u64> = Vec::with_capacity(free.len() + 1);
        for (j, &(_, _, k, _)) in free.iter().enumerate() {
            let mut x = k;
            for (l, &(_, _, k2, d2)) in free.iter().enumerate() {
                if l < j {
                    x *= d2 - k2;
                } else if l > j {
                    x *= d2;
                }
            }
            w.push(x);
        }
        let mut rest: u64 = free.iter().map(|&(_, _, k, d)| d - k).product();
        if free.is_empty() {
            rest = n;
        }
        let mut v = Vec::new();
        match self.top.known().next() {
            Some(head) => {
                for (&(i, c, _, _), &x) in free.iter().zip(&w) {
                    v.push((x, c, TopPick::Floater(i)));
                }
                if rest > 0 {
                    v.push((rest, head, TopPick::Head));
                }
            }
            None => {
                let m = n - entries.iter().map(|e| e.2 as u64).sum::<u64>();
                for (&(i, c, _, _), &x) in free.iter().zip(&w) {
                    v.push((x * m, c, TopPick::Floater(i)));
                }
                for (c, k) in self.draw().iter() {
                    let r = k as u64 - self.top.floater_count(c) as u64;
                    if r > 0 {
                        v.push((r * rest, c, TopPick::Unknown));
                    }
                }
            }
        }
        v
    }

    /// One of `top_cards`' entries, by weight.
    fn sample_top(cards: &[(u64, CardId, TopPick)], rng: &mut Rng) -> (CardId, TopPick) {
        let total: u64 = cards.iter().map(|x| x.0).sum();
        let mut r = match u32::try_from(total) {
            Ok(t) => rng.below(t) as u64,
            Err(_) => ((rng.unit() * total as f64) as u64).min(total - 1),
        };
        for &(w, c, pick) in cards {
            if r < w {
                return (c, pick);
            }
            r -= w;
        }
        unreachable!("weights sum to the total")
    }

    /// Takes the top card `c` off the draw pile as `top_cards` named it.
    fn pop_top(&mut self, c: CardId, pick: TopPick) {
        match pick {
            TopPick::Plain => {}
            TopPick::Floater(i) => {
                self.top.take_floater(i);
            }
            TopPick::Head => {
                self.top.pop_head();
            }
            TopPick::Unknown => self.top.draw_unknown(),
        }
        self.draw_mut().remove(c, 1);
    }

    /// A taken card's possible targets, equally likely: each living enemy
    /// for a card that targets one (the game picks it at use), else none.
    fn top_targets(&self, c: CardId) -> Vec<Option<u8>> {
        if self.binding.def(c).targeted() {
            self.living_slots().map(|s| Some(s as u8)).collect()
        } else {
            vec![None]
        }
    }

    /// Takes `c` off the draw pile into the queue (`pick` as `top_cards`
    /// said), its X the energy now.
    fn take_top(&mut self, c: CardId, pick: TopPick, target: Option<u8>, exhaust: bool) {
        self.pop_top(c, pick);
        let x = if self.binding.def(c).x_cost() { self.player.energy.clamp(0, u8::MAX as i16) as u8 } else { 0 };
        self.top_queue.push(Queued { card: c, target, x, exhaust });
    }

    /// Draws the top card `c` (`pick` as `top_cards` named it) into hand.
    fn draw_top_one(&mut self, c: CardId, pick: TopPick) {
        self.pop_top(c, pick);
        self.hand.add(c, 1);
        self.count_drawn(Hand::from_cards(&[c]).view());
    }

    /// Every distinct state after drawing `n` with a known top (card by card
    /// while something is known, then `draw_outcomes`), with probabilities;
    /// `None` past `limit`. Not run forward.
    fn top_draw_states(&self, n: usize, limit: usize) -> Option<Vec<(f64, CombatState)>> {
        fn rec(s: CombatState, n: usize, p: f64, limit: usize, out: &mut Vec<(f64, CombatState)>) -> bool {
            let push = |q: f64, t: CombatState, out: &mut Vec<(f64, CombatState)>| match out.iter().position(|(_, u)| *u == t) {
                Some(i) => {
                    out[i].0 += q;
                    true
                }
                None if out.len() == limit => false,
                None => {
                    out.push((q, t));
                    true
                }
            };
            if n == 0 {
                return push(p, s, out);
            }
            if s.top.is_empty() {
                let Some(v) = draw_outcomes(s.draw(), s.discard(), n, limit) else { return false };
                for (pile, q) in v {
                    let mut t = s.clone();
                    t.apply_draw(&pile);
                    if !push(p * q, t, out) {
                        return false;
                    }
                }
                return true;
            }
            let cards = s.top_cards();
            let total: u64 = cards.iter().map(|x| x.0).sum();
            for (w, c, pick) in cards {
                let mut t = s.clone();
                t.draw_top_one(c, pick);
                if !rec(t, n - 1, p * w as f64 / total as f64, limit, out) {
                    return false;
                }
            }
            true
        }
        let mut out = Vec::new();
        let mut s = self.clone();
        s.pending = None;
        rec(s, n, 1.0, limit, &mut out).then_some(out)
    }

    fn apply_draw(&mut self, drawn: &Hand) {
        if drawn.len() <= self.draw().len() {
            self.draw_mut().remove_pile(drawn);
        } else {
            let mut rest = *drawn;
            rest.remove_pile(self.draw());
            self.piles.move_all(Run::Discard, Run::Draw);
            self.draw_mut().remove_pile(&rest);
        }
        self.hand.add_pile(drawn);
        self.count_drawn(drawn.view());
    }

    /// Lists the pending event's outcomes if there are at most `limit`.
    /// `None` when no event is pending.
    pub fn chance_outcomes(&self, limit: usize) -> Option<ChanceOutcomes> {
        let ev = self.pending?;
        let mut base = self.clone();
        base.pending = None;
        let states: Vec<(f64, CombatState)> = match ev {
            ChanceEvent::Draw { n } if !self.top.is_empty() => {
                let Some(v) = self.top_draw_states(n as usize, limit) else {
                    return Some(ChanceOutcomes::Large);
                };
                v.into_iter()
                    .map(|(p, mut s)| {
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::Draw { n } => {
                let Some(v) = draw_outcomes(self.draw(), self.discard(), n as usize, limit) else {
                    return Some(ChanceOutcomes::Large);
                };
                v.into_iter()
                    .map(|(pile, p)| {
                        let mut s = base.clone();
                        s.apply_draw(&pile);
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::MonsterMove { slot } => {
                let dist = self.move_distribution(slot as usize);
                if dist.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                dist.into_iter()
                    .map(|(m, p)| {
                        let mut s = base.clone();
                        s.set_monster_move(slot as usize, m);
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::PlainHit { amount } => {
                let living: Vec<usize> = self.living_slots().collect();
                if living.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                let p = 1.0 / living.len() as f64;
                living
                    .into_iter()
                    .map(|slot| {
                        let mut s = base.clone();
                        s.plain_hit(slot, amount);
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::RandomTarget { amount } => {
                let living: Vec<usize> = self.living_slots().collect();
                if living.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                let p = 1.0 / living.len() as f64;
                living
                    .into_iter()
                    .map(|slot| {
                        let mut s = base.clone();
                        s.random_hit(slot, amount);
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::AllyBlock { slot } => {
                let slot = slot as usize;
                let others = self.ally_block_candidates(slot);
                if others.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                let p = 1.0 / others.len() as f64;
                others
                    .into_iter()
                    .map(|a| {
                        let mut s = base.clone();
                        s.give_ally_block(slot, a);
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::TakeTop { exhaust } => {
                let cards = self.top_cards();
                let n = cards.iter().map(|x| x.0).sum::<u64>() as f64;
                let mut v = Vec::new();
                for (w, c, pick) in cards {
                    let targets = self.top_targets(c);
                    for &t in &targets {
                        v.push((w as f64 / n / targets.len() as f64, c, pick, t));
                    }
                }
                if v.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                v.into_iter()
                    .map(|(p, c, pick, t)| {
                        let mut s = base.clone();
                        s.take_top(c, pick, t, exhaust);
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::Offer { pool, ty, k } => {
                let cards = crate::registry::pool_cards(&self.binding, pool, ty);
                if binom(cards.len(), k as usize) > limit as f64 {
                    return Some(ChanceOutcomes::Large);
                }
                let p = 1.0 / binom(cards.len(), k as usize);
                combinations(cards.len(), k as usize)
                    .into_iter()
                    .map(|ix| {
                        let mut s = base.clone();
                        s.set_offer(&ix.iter().map(|&i| cards[i]).collect::<Vec<_>>());
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::MakeRandom { pool, ty, pile, zero_cost, free, up } => {
                let cards = crate::registry::pool_cards(&self.binding, pool, ty);
                if cards.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                let p = 1.0 / cards.len() as f64;
                cards
                    .iter()
                    .map(|&c| {
                        let mut s = base.clone();
                        s.make_random(c, pile, zero_cost, free, up);
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::RandomPotion { pool } => {
                let pool = crate::potions::potion_pool(pool);
                if pool.potions().count() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                pool.outcomes()
                    .map(|(id, p)| {
                        let mut s = base.clone();
                        s.player.potions.insert(id).expect("an empty slot");
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::ExhaustSave { queued } => {
                let p = self.exhaust_save_chance();
                [(1.0 - p, false), (p, true)]
                    .into_iter()
                    .map(|(p, saved)| {
                        let mut s = base.clone();
                        s.exhaust_saved(queued, saved);
                        s.run();
                        (p, s)
                    })
                    .collect()
            }
            ChanceEvent::RandomCost => (0..4)
                .map(|v| {
                    let mut s = base.clone();
                    s.roll_cost(v);
                    s.run();
                    (0.25, s)
                })
                .collect(),
            ChanceEvent::RandomZeroCost => {
                let cards = self.zero_cost_choices();
                if cards.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                let total: u32 = cards.iter().map(|&(_, n)| n as u32).sum();
                cards
                    .into_iter()
                    .map(|(c, n)| {
                        let mut s = base.clone();
                        s.zero_cost(c);
                        s.run();
                        (n as f64 / total as f64, s)
                    })
                    .collect()
            }
            ChanceEvent::RandomFreeTurn => {
                let cards = self.free_turn_choices();
                if cards.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                let total: u32 = cards.iter().map(|&(_, n)| n as u32).sum();
                cards
                    .into_iter()
                    .map(|(c, n)| {
                        let mut s = base.clone();
                        s.mark_free_in_hand(c);
                        s.run();
                        (n as f64 / total as f64, s)
                    })
                    .collect()
            }
            ChanceEvent::RandomUpgrade => {
                let cards = self.upgrade_choices();
                if cards.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                let total: u32 = cards.iter().map(|&(_, _, n)| n as u32).sum();
                cards
                    .into_iter()
                    .map(|(c, marked, n)| {
                        let mut s = base.clone();
                        s.upgrade_copy(c, marked);
                        s.run();
                        (n as f64 / total as f64, s)
                    })
                    .collect()
            }
            ChanceEvent::RandomExhaust => {
                let cards: Vec<(CardId, u8)> = self.hand.iter().collect();
                if cards.len() > limit {
                    return Some(ChanceOutcomes::Large);
                }
                let total = self.hand.len() as f64;
                cards
                    .into_iter()
                    .map(|(c, n)| {
                        let mut s = base.clone();
                        s.exhaust_from_hand(c);
                        s.run();
                        (n as f64 / total, s)
                    })
                    .collect()
            }
        };
        let mut merged: Vec<(f64, CombatState)> = Vec::with_capacity(states.len());
        for (p, s) in states {
            match merged.iter_mut().find(|(_, t)| *t == s) {
                Some((q, _)) => *q += p,
                None => merged.push((p, s)),
            }
        }
        Some(ChanceOutcomes::Listed(merged))
    }

    /// Samples the pending event and runs on to the next decision or event.
    pub fn resolve_chance(&mut self, rng: &mut Rng) {
        self.resolve_chance_opts(rng, false)
    }

    /// `resolve_chance`, running on with `run_opts(turn1_pre_draw)`.
    pub(crate) fn resolve_chance_opts(&mut self, rng: &mut Rng, turn1_pre_draw: bool) {
        let Some(ev) = self.pending.take() else { return };
        match ev {
            ChanceEvent::Draw { n } => {
                for _ in 0..n {
                    // A known top or floaters: as `top_cards` weighs them.
                    if !self.top.is_empty() {
                        let (c, pick) = Self::sample_top(&self.top_cards(), rng);
                        self.draw_top_one(c, pick);
                        continue;
                    }
                    if self.draw().is_empty() {
                        self.piles.move_all(Run::Discard, Run::Draw);
                    }
                    let c = self.draw().nth(rng.below(self.draw().len() as u32) as usize);
                    self.draw_mut().remove(c, 1);
                    self.hand.add(c, 1);
                    self.count_drawn(Hand::from_cards(&[c]).view());
                }
            }
            ChanceEvent::MonsterMove { slot } => {
                let slot = slot as usize;
                let ai = self.monsters[slot].def().ai;
                let m = ai(self, slot, rng as &mut dyn Chance);
                self.set_monster_move(slot, m);
            }
            ChanceEvent::RandomTarget { amount } => {
                let living: Vec<usize> = self.living_slots().collect();
                let slot = living[rng.below(living.len() as u32) as usize];
                self.random_hit(slot, amount);
            }
            ChanceEvent::PlainHit { amount } => {
                let living: Vec<usize> = self.living_slots().collect();
                let slot = living[rng.below(living.len() as u32) as usize];
                self.plain_hit(slot, amount);
            }
            ChanceEvent::AllyBlock { slot } => {
                let slot = slot as usize;
                let others = self.ally_block_candidates(slot);
                let a = others[rng.below(others.len() as u32) as usize];
                self.give_ally_block(slot, a);
            }
            ChanceEvent::RandomCost => self.roll_cost(rng.below(4) as i8),
            // Each relic rolls alone (`exhaust_save_chance`).
            ChanceEvent::ExhaustSave { queued } => {
                let rolls: Vec<(i16, i16)> = self.player.relics.iter().map(|(id, _)| id.rules().exhaust_save).filter(|&(_, d)| d > 0).collect();
                let saved = rolls.into_iter().fold(false, |s, (n, d)| rng.below(d as u32) < n as u32 || s);
                self.exhaust_saved(queued, saved);
            }
            ChanceEvent::RandomZeroCost => {
                let cards = self.zero_cost_choices();
                let mut r = rng.below(cards.iter().map(|&(_, n)| n as u32).sum());
                let &(c, _) = cards
                    .iter()
                    .find(|&&(_, n)| {
                        if r < n as u32 {
                            return true;
                        }
                        r -= n as u32;
                        false
                    })
                    .expect("weights sum to the total");
                self.zero_cost(c);
            }
            ChanceEvent::RandomFreeTurn => {
                let cards = self.free_turn_choices();
                let mut r = rng.below(cards.iter().map(|&(_, n)| n as u32).sum());
                let &(c, _) = cards
                    .iter()
                    .find(|&&(_, n)| {
                        if r < n as u32 {
                            return true;
                        }
                        r -= n as u32;
                        false
                    })
                    .expect("weights sum to the total");
                self.mark_free_in_hand(c);
            }
            ChanceEvent::RandomUpgrade => {
                let cards = self.upgrade_choices();
                let mut r = rng.below(cards.iter().map(|&(_, _, n)| n as u32).sum());
                let &(c, marked, _) = cards
                    .iter()
                    .find(|&&(_, _, n)| {
                        if r < n as u32 {
                            return true;
                        }
                        r -= n as u32;
                        false
                    })
                    .expect("weights sum to the total");
                self.upgrade_copy(c, marked);
            }
            ChanceEvent::RandomExhaust => {
                let c = self.hand.nth(rng.below(self.hand.len() as u32) as usize);
                self.exhaust_from_hand(c);
            }
            ChanceEvent::TakeTop { exhaust } => {
                let (c, pick) = Self::sample_top(&self.top_cards(), rng);
                let targets = self.top_targets(c);
                let t = if targets.len() == 1 { targets[0] } else { targets[rng.below(targets.len() as u32) as usize] };
                self.take_top(c, pick, t, exhaust);
            }
            ChanceEvent::Offer { pool, ty, k } => {
                let mut left: Vec<CardId> = crate::registry::pool_cards(&self.binding, pool, ty).to_vec();
                let mut shown = Vec::with_capacity(k as usize);
                for _ in 0..k {
                    shown.push(left.remove(rng.below(left.len() as u32) as usize));
                }
                self.set_offer(&shown);
            }
            ChanceEvent::MakeRandom { pool, ty, pile, zero_cost, free, up } => {
                let cards = crate::registry::pool_cards(&self.binding, pool, ty);
                let c = cards[rng.below(cards.len() as u32) as usize];
                self.make_random(c, pile, zero_cost, free, up);
            }
            ChanceEvent::RandomPotion { pool } => {
                let id = crate::potions::potion_pool(pool).sample(rng);
                self.player.potions.insert(id).expect("an empty slot");
            }
        }
        self.run_opts(turn1_pre_draw);
    }

    /// Samples chance events until the next decision or the end of combat.
    pub fn advance(&mut self, rng: &mut Rng) {
        while self.pending.is_some() {
            self.resolve_chance(rng);
        }
    }
}
