//! A compact, decodable encoding of a combat state: the solved-position
//! database's keys and rows.
//!
//! `encode` takes the state apart by naming every field, so a new field is a
//! compile error here until it is encoded. `decode(encode(s)) == s`, so two
//! different states never share bytes. Piles are (card, count) lists, empty
//! monster slots are skipped, numbers are LEB128 varints (signed ones
//! zigzagged), and the codec version comes first.

use crate::cards::{CardId, NUM_OFFICIAL_CARDS};
use crate::chance::{ChanceEvent, OrderThen};
use crate::character::Character;
use crate::monsters::{Ascension, Monster, MonsterKind, MAX_ASCENSION, NUM_OFFICIAL_MONSTERS};
use crate::powers::{Powers, NUM_OFFICIAL_POWERS, NUM_POWERS};
use crate::potions::{potion_id, Potions, POTION_CAP};
use crate::relics::{relic_id, Relics, RELIC_CAP};
use crate::registry::{changed_copy, copy_of, is_changed, order_key, Binding, Overrides, VARIANT_BASE};
use crate::effects::{Effect, PickKind, Types};
use crate::state::{Action, CombatState, CostRolls, FreeMarks, TurnCosts, Owed, OwedKind, OWED_CAP, Hand, InPlay, Pick, Pile, PileN, PileRef, Piles, Player, Queued, Run, Stage, Top, TopQueue, HAND_LIMIT, MAX_MONSTERS, PILE_RUN_CAP, TOP_QUEUE_CAP};

/// Bumped on any change to the byte format.
pub const CODEC_VERSION: u8 = 1;

/// Every official monster kind, in code order: `MONSTER_KINDS[k.0 as usize] == k`.
pub const MONSTER_KINDS: [MonsterKind; NUM_OFFICIAL_MONSTERS] = {
    let mut a = [MonsterKind::None; NUM_OFFICIAL_MONSTERS];
    let mut i = 0;
    while i < NUM_OFFICIAL_MONSTERS {
        a[i] = MonsterKind(i as u8);
        i += 1;
    }
    a
};

/// Most changed copies one encoded state names: their bytes are
/// `VARIANT_BASE + rank`.
pub const MAX_CHANGED: usize = 256 - VARIANT_BASE;

/// The changed copies a state names (piles, the card in play, the cards
/// waiting to be played), in pile order: a copy's rank here is its byte
/// less `VARIANT_BASE` (docs/specs/sparse-piles.md), as the variant ids'
/// were.
pub fn changed_ranks(s: &CombatState) -> Vec<CardId> {
    let mut v: Vec<CardId> = s.all_piles().iter().flat_map(|p| p.iter().map(|(c, _)| c)).filter(|&c| is_changed(c)).collect();
    v.extend(s.top_queue.iter().map(|q| q.card).filter(|&c| is_changed(c)));
    if let Stage::PlayingCard { card, .. } = s.stage {
        if is_changed(card) {
            v.push(card);
        }
    }
    v.sort_by_key(|&c| order_key(c));
    v.dedup();
    assert!(v.len() <= MAX_CHANGED, "codec: a state naming {} changed copies, more than {MAX_CHANGED} (MAX_CHANGED)", v.len());
    v
}

/// A card's byte: an official card's id, a changed copy's `VARIANT_BASE +
/// rank` in `ranks` (`changed_ranks`). Encodable states hold no others.
fn card_byte(ranks: &[CardId], c: CardId) -> u8 {
    if is_changed(c) {
        let i = ranks.iter().position(|&x| x == c).expect("codec: a changed copy the state names");
        return (VARIANT_BASE + i) as u8;
    }
    u8::try_from(c.0).unwrap_or_else(|_| panic!("codec: card id {} has no byte", c.0))
}

/// The card a byte names: an official card, or the changed copy at its
/// rank in `ranks`.
fn byte_card(ranks: &[CardId], b: u8) -> Option<CardId> {
    let i = b as usize;
    if i < NUM_OFFICIAL_CARDS {
        Some(CardId(b as u16))
    } else {
        ranks.get(i.checked_sub(VARIANT_BASE)?).copied()
    }
}

struct Writer {
    out: Vec<u8>,
    ranks: Vec<CardId>,
}

impl Writer {
    fn u(&mut self, mut v: u64) {
        while v >= 0x80 {
            self.out.push(v as u8 | 0x80);
            v >>= 7;
        }
        self.out.push(v as u8);
    }

    fn i(&mut self, v: i64) {
        self.u(((v << 1) ^ (v >> 63)) as u64);
    }

    fn byte(&mut self, b: u8) {
        self.out.push(b);
    }

    /// A pick: 0 for none, else 1 + its kind, picks left, exact.
    fn pick(&mut self, p: Option<Pick>) {
        match p {
            None => self.byte(0),
            Some(p) => {
                self.byte(1 + p.kind as u8);
                self.byte(p.left);
                // `free` in bit 1, a type filter in bit 2 (its mask follows),
                // so every other pick encodes as before; a `CopyInHand`
                // pick (kind byte 9) ends with its copies.
                let of = p.of != Types::ALL;
                self.byte(p.exact as u8 | (p.free as u8) << 1 | (of as u8) << 2);
                if of {
                    self.byte(p.of.0);
                }
                if p.kind == PickKind::CopyInHand {
                    self.byte(p.copies);
                }
            }
        }
    }

    /// `None` as 0, `Some(k)` as k + 1.
    fn opt(&mut self, v: Option<u8>) {
        match v {
            None => self.byte(0),
            Some(k) => {
                assert!(k < u8::MAX, "slot {k} out of range");
                self.byte(k + 1);
            }
        }
    }

    fn card(&mut self, c: CardId) {
        self.byte(card_byte(&self.ranks, c));
    }

    fn pile(&mut self, p: PileRef<'_>) {
        let kinds: Vec<(CardId, u8)> = p.iter().collect();
        self.u(kinds.len() as u64);
        for (c, n) in kinds {
            self.card(c);
            self.byte(n);
        }
    }

    fn powers(&mut self, p: &Powers) {
        let mask = p.iter().fold(0u64, |m, (w, _)| m | 1 << w as u32);
        self.u(mask);
        for (_, a) in p.iter() {
            self.i(a as i64);
        }
        self.u(p.just_applied_mask());
    }

    fn monster(&mut self, m: &Monster) {
        // The level is the state's (section 18).
        let Monster { kind, hp, max_hp, block, powers, moves, rolled_damage, escaped, ascension: _ } = m;
        self.byte(kind.0);
        self.i(*hp as i64);
        self.i(*max_hp as i64);
        self.i(*block as i64);
        self.powers(powers);
        self.byte(moves[0]);
        self.byte(moves[1]);
        self.i(*rolled_damage as i64);
        self.byte(*escaped as u8);
    }
}

/// The state's bytes: about 60-120 for a typical state.
pub fn encode(s: &CombatState) -> Vec<u8> {
    let CombatState {
        player,
        monsters,
        hand,
        free_in_hand,
        turn_costs,
        cost_rolls,
        owed,
        owed_late,
        piles: _,
        top_queue,
        top,
        turn,
        stage,
        pending,
        deferred_block,
        block_broken,
        created,
        removed,
        character,
        start_hp,
        cards_played_this_turn,
        card_hp_losses,
        unfired_exhausts,
        owed_draw,
        unfired_draws,
        unfired_curse_draws,
        times_lost_hp,
        win_heal,
        escaped,
        boss_fight,
        no_death,
        binding: _,
        offer,
        won_healed: _,
        dealt,
        turn_ending,
        monsters_acting,
        allies_at_move,
        intent_hidden,
        bottled,
        ascension,
    } = s;
    debug_assert!(bottled.iter().all(Option::is_none), "codec: a state before turn 1's opening hand");
    // Set only inside End Turn and the monsters' turn: never seen at rest.
    debug_assert!(!turn_ending, "codec: a state inside End Turn");
    debug_assert!(!monsters_acting, "codec: a state inside the monsters' turn");
    // Set only for pack monsters (`Allies`), which aren't encoded.
    debug_assert!(*allies_at_move == 0, "codec: a pack monster's allies count");
    // Generated content (registry-lite) has no stable encoding: a binding
    // or a pack monster's kind names process-local registry entries.
    // Variants are written by value.
    assert!(!s.has_generated(), "codec: a state with generated content (a registry binding or a pack monster) can't be encoded");
    // An open offer counts as generated content (`has_generated`).
    debug_assert!(offer.is_empty());
    let mut w = Writer { out: Vec::with_capacity(128), ranks: changed_ranks(s) };
    w.byte(CODEC_VERSION);
    w.byte(match character {
        Character::Ironclad => 0,
        Character::Silent => 1,
    });
    w.byte(*no_death as u8);

    let Player { hp, max_hp, block, energy, powers, relics, potions } = player;
    w.i(*hp as i64);
    w.i(*max_hp as i64);
    w.i(*block as i64);
    w.i(*energy as i64);
    w.powers(powers);

    let empty = Monster::default();
    let mask = monsters.iter().enumerate().filter(|(_, m)| **m != empty).fold(0u8, |m, (i, _)| m | 1 << i);
    w.byte(mask);
    for m in monsters.iter().filter(|m| **m != empty) {
        w.monster(m);
    }

    for p in [hand.view(), s.draw(), s.discard(), s.exhaust()] {
        w.pile(p);
    }
    w.u(*turn as u64);
    match *stage {
        Stage::PlayerTurn => w.byte(0),
        // An X-cost card's X > 0 takes tag 7, a pick, replay or copy tag 8
        // (every field), so every other encoding is unchanged.
        Stage::PlayingCard { card, target, next, hit, x, more } => {
            let full = more != InPlay::default();
            w.byte(if full { 8 } else if x == 0 { 1 } else { 7 });
            w.card(card);
            w.opt(target);
            w.byte(next);
            w.byte(hit);
            if x != 0 || full {
                w.byte(x);
            }
            if full {
                w.byte(more.replays);
                // `exhaust` (a card Havoc plays) in bit 1, `queued` in bit 2;
                // the exhaust-save roll in bits 3 (rolled) and 4 (saved).
                let save = match more.save {
                    None => 0,
                    Some(false) => 8,
                    Some(true) => 24,
                };
                w.byte(more.copy as u8 | (more.exhaust as u8) << 1 | (more.queued as u8) << 2 | save);
                w.pick(more.pick);
            }
        }
        // A potion in use (potions spec): tag 9, the potion by name.
        Stage::UsingPotion { potion, target, next, hit, pick } => {
            w.byte(9);
            let name = potion.name().as_bytes();
            w.u(name.len() as u64);
            w.out.extend_from_slice(name);
            w.opt(target);
            w.byte(next);
            w.byte(hit);
            w.pick(pick);
        }
        // A relic's open pick (fight-vocabulary spec): tag 10, its place in
        // the relic list and hook, the effect to resume at, the count.
        Stage::RelicPick { relic, hook, next, hit, pick } => {
            w.byte(10);
            w.byte(relic);
            w.byte(hook);
            w.byte(next);
            w.byte(hit);
            w.pick(pick);
        }
        // A relic's offer before the opening draw (colorless-cards spec
        // step 6): tag 11, its place in the relic list and hook, the effect
        // to resume at, the pick.
        Stage::RelicOffer { relic, hook, next, pick } => {
            w.byte(11);
            w.byte(relic);
            w.byte(hook);
            w.byte(next);
            w.pick(pick);
        }
        Stage::MonsterRolls { next } => {
            w.byte(2);
            w.byte(next);
        }
        // End Turn paused for owed work (blocked-relics spec step 5): tag
        // 12, the part it goes on at.
        Stage::EndingTurn { part } => {
            w.byte(12);
            w.byte(part);
        }
        // The monsters' turn paused at a pick (only pack monsters' `BlockAlly`
        // pauses it, and pack monsters aren't encoded): tag 13.
        Stage::MonsterActing { slot, next } => {
            w.byte(13);
            w.byte(slot);
            w.byte(next);
        }
        Stage::StartTurn => w.byte(3),
        Stage::TurnStarted => w.byte(4),
        Stage::Over { won } => w.byte(5 + won as u8),
    }
    match *pending {
        None => w.byte(0),
        Some(ChanceEvent::Draw { n }) => {
            w.byte(1);
            w.byte(n);
        }
        Some(ChanceEvent::MonsterMove { slot }) => {
            w.byte(2);
            w.byte(slot);
        }
        Some(ChanceEvent::RandomTarget { amount }) => {
            w.byte(3);
            w.i(amount as i64);
        }
        Some(ChanceEvent::RandomExhaust) => w.byte(4),
        // A random-target `PlainDamage` (ironclad-last-four spec): tag 12.
        Some(ChanceEvent::PlainHit { amount }) => {
            w.byte(12);
            w.i(amount as i64);
        }
        Some(ChanceEvent::AllyBlock { slot }) => {
            w.byte(5);
            w.byte(slot);
        }
        // `PlayTop`'s next card (act1-singles spec): tag 6.
        Some(ChanceEvent::TakeTop { exhaust }) => {
            w.byte(6);
            w.byte(exhaust as u8);
        }
        // A cost roll (sparse-piles spec): tag 7, its card in section 14.
        Some(ChanceEvent::RandomCost) => w.byte(7),
        // Madness's pick (colorless-cards spec step 5): tag 8.
        Some(ChanceEvent::RandomZeroCost) => w.byte(8),
        // Mummified Hand's and Warped Tongs' picks (blocked-relics spec
        // step 5): tags 9 and 10.
        Some(ChanceEvent::RandomFreeTurn) => w.byte(9),
        Some(ChanceEvent::RandomUpgrade) => w.byte(10),
        // The exhaust-save roll (blocked-relics spec step 7): tag 11.
        Some(ChanceEvent::ExhaustSave { queued }) => {
            w.byte(11);
            w.byte(queued as u8);
        }
        // Frozen Eye's order (tag 13: what waits, 0 nothing, 1 a draw and
        // its count, 2 `PlayTop` and whether it exhausts) and owed spot
        // (tag 14, its card).
        Some(ChanceEvent::Order { then }) => {
            w.byte(13);
            match then {
                OrderThen::Nothing => w.byte(0),
                OrderThen::Draw(n) => {
                    w.byte(1);
                    w.byte(n);
                }
                OrderThen::TakeTop { exhaust } => {
                    w.byte(2);
                    w.byte(exhaust as u8);
                }
            }
        }
        Some(ChanceEvent::InsertAt { card }) => {
            w.byte(14);
            w.card(card);
        }
        // Runic Dome's reveal of whether a hidden monster attacks (tag 15)
        // and its rolled amount (tag 16), each with the slot.
        Some(ChanceEvent::IntentClass { slot }) => {
            w.byte(15);
            w.byte(slot);
        }
        Some(ChanceEvent::RolledAmount { slot }) => {
            w.byte(16);
            w.byte(slot);
        }
        Some(ChanceEvent::Offer { .. }) => unreachable!("an open offer counts as generated content"),
        Some(ChanceEvent::RandomPotion { .. }) => unreachable!("a pending random potion counts as generated content"),
        Some(ChanceEvent::MakeRandom { .. }) => unreachable!("a pending MakeRandom roll counts as generated content"),
    }
    let mask = deferred_block.iter().enumerate().filter(|(_, &b)| b != 0).fold(0u8, |m, (i, _)| m | 1 << i);
    w.byte(mask);
    for &b in deferred_block.iter().filter(|&&b| b != 0) {
        w.i(b as i64);
    }
    w.u(*created as u64);
    w.u(*removed as u64);
    w.i(*start_hp as i64);
    w.byte(*cards_played_this_turn);
    w.byte(*card_hp_losses);
    // Optional trailer sections, only when there is anything to say, so
    // every other encoding is unchanged: 1, what is known of the draw
    // pile's order (the known count may be 0 when only floaters under the
    // top are known: draw-knowledge spec item 1); 2, the per-copy variants
    // the card ids name; 3, the exhaust-trigger counters.
    if !top.is_empty() {
        w.byte(1);
        w.byte(top.n_known() as u8);
        for c in top.known() {
            w.card(c);
        }
        // Oldest first (their order matters, `Top`); within a run of equal
        // `above` (whose order can't) in byte order, so the bytes don't
        // depend on card id numbering.
        let mut floaters: Vec<(u8, u8)> = top.floaters().map(|(c, a)| (card_byte(&w.ranks, c), a)).collect();
        for run in floaters.chunk_by_mut(|x, y| x.1 == y.1) {
            run.sort_unstable();
        }
        w.u(floaters.len() as u64);
        for (c, a) in floaters {
            w.byte(c);
            w.byte(a);
        }
    }
    // 2, the changed copies the card bytes name, by value, when each is
    // grown damage at its base's own level (as the variants were); any
    // other changed copy moves them all to section 13.
    let damage_only = w.ranks.iter().all(|&c| copy_of(c).is_some_and(|(b, o)| o.damage.is_some() && o.cost.is_none() && o.level == b.def().level));
    if damage_only && !w.ranks.is_empty() {
        w.byte(2);
        w.byte(w.ranks.len() as u8);
        for c in w.ranks.clone() {
            let (base, o) = copy_of(c).expect("a changed copy");
            w.card(base);
            w.i(o.damage.expect("grown damage") as i64);
        }
    }
    // 3, the exhaust-trigger counters (exhaust-triggers spec).
    if *unfired_exhausts != 0 || *owed_draw != 0 {
        w.byte(3);
        w.byte(*unfired_exhausts);
        w.byte(*owed_draw);
    }
    // 4, the draw-trigger counter (draw-triggers spec).
    if *unfired_draws != 0 {
        w.byte(4);
        w.byte(*unfired_draws);
    }
    // 5, the HP-loss counter (cost-changes spec).
    if *times_lost_hp != 0 {
        w.byte(5);
        w.byte(*times_lost_hp);
    }
    // 6, the combat-end heal when it differs from the character's (relics
    // spec): every state with the default heal encodes as before.
    if *win_heal != character.win_heal() {
        w.byte(6);
        w.i(*win_heal as i64);
    }
    // 7, the relics held (relic-entity spec), by name, each with its
    // counter: only when any is held.
    if !relics.is_empty() {
        w.byte(7);
        w.u(relics.len() as u64);
        for (id, c) in relics.iter() {
            let name = id.name().as_bytes();
            w.u(name.len() as u64);
            w.out.extend_from_slice(name);
            w.i(c as i64);
        }
    }
    // 8, the potions held (potions spec), by name in the held order: only
    // when any is held.
    if !potions.is_empty() {
        w.byte(8);
        w.u(potions.len() as u64);
        for id in potions.iter() {
            let name = id.name().as_bytes();
            w.u(name.len() as u64);
            w.out.extend_from_slice(name);
        }
    }
    // 9, the hand cards that cost 0 this turn (act1-singles spec): only
    // when any is marked.
    if !free_in_hand.is_empty() {
        w.byte(9);
        w.byte(free_in_hand.len() as u8);
        let mut ids: Vec<u8> = free_in_hand.iter().map(|c| card_byte(&w.ranks, c)).collect();
        ids.sort_unstable();
        for b in ids {
            w.byte(b);
        }
    }
    // 10, the player escaped (act1-singles spec): only when set.
    if *escaped {
        w.byte(10);
    }
    // 11, the boss-fight mark (act1-singles spec): only when set.
    if *boss_fight {
        w.byte(11);
    }
    // 12, the cards `PlayTop` took, waiting to be played (act1-singles
    // spec): only while any waits.
    if !top_queue.is_empty() {
        w.byte(12);
        w.byte(top_queue.len() as u8);
        for q in top_queue.iter() {
            w.card(q.card);
            w.opt(q.target);
            w.byte(q.x);
            w.byte(q.exhaust as u8);
        }
    }
    // 13, changed copies other than grown damage at their base's level
    // (docs/specs/sparse-piles.md), all of them in place of section 2.
    if !damage_only && !w.ranks.is_empty() {
        w.byte(13);
        w.byte(w.ranks.len() as u8);
        for c in w.ranks.clone() {
            let (base, o) = copy_of(c).expect("a changed copy");
            w.card(base);
            w.byte(o.level);
            w.byte(o.damage.is_some() as u8 | (o.cost.is_some() as u8) << 1);
            if let Some(d) = o.damage {
                w.i(d as i64);
            }
            if let Some(c) = o.cost {
                w.byte(c as u8);
            }
        }
    }
    // 14, the hand cards waiting for a cost roll (sparse-piles spec), in
    // roll order with their marks: only while any waits.
    if !cost_rolls.is_empty() {
        w.byte(14);
        w.byte(cost_rolls.len() as u8);
        for (c, marked) in cost_rolls.iter() {
            w.card(c);
            w.byte(marked as u8);
        }
    }
    // 15, the random work hooks owe (blocked-relics spec step 5), in
    // order: each entry's kind (bit 7: it waits for a relic's hook), its
    // count. Only while any is owed; owed `MakeRandom` rolls count as
    // generated content.
    if !owed.is_empty() {
        w.byte(15);
        w.byte(owed.iter().count() as u8);
        for e in owed.iter() {
            let kind = match e.kind {
                OwedKind::ZeroCost => 0,
                OwedKind::FreeTurn => 1,
                OwedKind::Upgrade => 2,
                OwedKind::Draw => 3,
                OwedKind::Hit { .. } => 4,
                OwedKind::Insert { .. } => 5,
                OwedKind::Top { .. } => unreachable!("a late take is written in section 21"),
                OwedKind::Make { .. } => unreachable!("owed MakeRandom rolls count as generated content"),
            };
            w.byte(kind | (e.wait as u8) << 7);
            w.byte(e.n);
            // A hit's amount follows its count.
            if let OwedKind::Hit { amount } = e.kind {
                w.i(amount as i64);
            }
            // An owed spot's card (Frozen Eye) too.
            if let OwedKind::Insert { card } = e.kind {
                w.card(card);
            }
        }
    }
    // 16, the blocks broken whose hooks haven't fired (blocked-relics spec
    // step 7): a slot mask, then each count. Only while any waits.
    if *block_broken != [0; MAX_MONSTERS] {
        w.byte(16);
        w.byte(block_broken.iter().enumerate().filter(|(_, &n)| n != 0).fold(0u8, |m, (i, _)| m | 1 << i));
        for &n in block_broken.iter().filter(|&&n| n != 0) {
            w.byte(n);
        }
    }
    // 17, the HP the latest damage effect took, while a card, potion or
    // move that may read it goes on (`Quantity::HpDealt`).
    if *dealt != 0 {
        w.byte(17);
        w.i(*dealt as i64);
    }
    // 18, the ascension level (docs/specs/ascension.md): only above 0, so
    // every A0 state encodes as before. Every monster holds the state's.
    debug_assert!(monsters.iter().all(|m| m.kind == MonsterKind::None || m.ascension == *ascension), "codec: a monster at another level than its combat");
    if ascension.0 != 0 {
        w.byte(18);
        w.byte(ascension.0);
    }
    // 19, the Curse draws whose `CardDrawn` hooks haven't fired (Fire
    // Breathing, docs/specs/draw-triggers.md): only when nonzero.
    if *unfired_curse_draws != 0 {
        w.byte(19);
        w.byte(*unfired_curse_draws);
    }
    // 20, Runic Dome's hidden intents (`CombatState::intent_hidden`): a
    // slot mask, then each slot's bits. Only when any is set.
    if *intent_hidden != [0; MAX_MONSTERS] {
        w.byte(20);
        w.byte(intent_hidden.iter().enumerate().filter(|(_, &b)| b != 0).fold(0u8, |m, (i, _)| m | 1 << i));
        for &b in intent_hidden.iter().filter(|&&b| b != 0) {
            w.byte(b);
        }
    }
    // 21, the takes a power's hook owes behind the turn start (Mayhem,
    // `owed_late`), in order: each entry's kind (6 `Top`, 7 `Top` that
    // exhausts), its count. Only while any is owed.
    if !owed_late.is_empty() {
        w.byte(21);
        w.byte(owed_late.iter().count() as u8);
        for e in owed_late.iter() {
            let OwedKind::Top { exhaust } = e.kind else { unreachable!("owed_late holds takes only") };
            w.byte(6 + exhaust as u8);
            w.byte(e.n);
        }
    }
    // 22, the hand cards that cost 1 or more this turn, below their cost
    // (Enlightenment, `turn_costs`): their count, then each copy's card and
    // cost this turn, by card then cost. Only when any is marked.
    if !turn_costs.is_empty() {
        w.byte(22);
        w.byte(turn_costs.len() as u8);
        let mut marks: Vec<(u8, u8)> = turn_costs.iter().map(|(c, v)| (card_byte(&w.ranks, c), v)).collect();
        marks.sort_unstable();
        for (b, v) in marks {
            w.byte(b);
            w.byte(v);
        }
    }
    w.out
}

struct Reader<'a> {
    b: &'a [u8],
    at: usize,
}

impl Reader<'_> {
    fn byte(&mut self) -> Option<u8> {
        let v = *self.b.get(self.at)?;
        self.at += 1;
        Some(v)
    }

    fn u(&mut self) -> Option<u64> {
        let mut v = 0u64;
        for shift in (0..64).step_by(7) {
            let b = self.byte()?;
            v |= ((b & 0x7f) as u64) << shift;
            if b < 0x80 {
                return Some(v);
            }
        }
        None
    }

    fn i(&mut self) -> Option<i64> {
        let v = self.u()?;
        Some((v >> 1) as i64 ^ -((v & 1) as i64))
    }

    fn i16(&mut self) -> Option<i16> {
        i16::try_from(self.i()?).ok()
    }

    /// An official card or a changed copy's rank byte, as read (`CardId`
    /// of the byte; ranks are resolved once the trailer is read); never a
    /// generated slot.
    fn card(&mut self) -> Option<CardId> {
        let c = self.byte()? as usize;
        (c < NUM_OFFICIAL_CARDS || c >= VARIANT_BASE).then_some(CardId(c as u16))
    }

    /// A pick written by `Writer::pick`.
    fn pick(&mut self) -> Option<Option<Pick>> {
        Some(match self.byte()? {
            0 => None,
            k => {
                // 7 is `Offered`, never written (an open offer isn't encoded).
                let kind = match k {
                    8 => PickKind::HandToTop,
                    9 => PickKind::CopyInHand,
                    k => *[PickKind::DiscardFromHand, PickKind::ReturnFromDiscard, PickKind::DiscardToTop, PickKind::ExhaustFromHand, PickKind::ReturnFromExhaust, PickKind::UpgradeFromHand].get(k as usize - 1)?,
                };
                let left = self.byte()?;
                let flags = self.byte()?;
                if flags > 7 {
                    return None;
                }
                let of = if flags & 4 != 0 {
                    match self.byte()? {
                        m if m == 0 || m & !Types::ALL.0 != 0 || m == Types::ALL.0 => return None,
                        m => Types(m),
                    }
                } else {
                    Types::ALL
                };
                let copies = if kind == PickKind::CopyInHand { self.byte()? } else { 0 };
                Some(Pick { kind, left, exact: flags & 1 != 0, free: flags & 2 != 0, of, copies })
            }
        })
    }

    fn opt(&mut self) -> Option<Option<u8>> {
        Some(match self.byte()? {
            0 => None,
            k => Some(k - 1),
        })
    }

    /// A pile of at most `N` entries (`None` past that).
    fn pile<const N: usize>(&mut self) -> Option<PileN<N>> {
        let mut p = PileN::<N>::default();
        for _ in 0..self.u()? {
            let c = self.card()?;
            let n = self.byte()?;
            if p.count(c) == 0 && p.entries() == N {
                return None;
            }
            p.add(c, n);
        }
        Some(p)
    }

    fn powers(&mut self) -> Option<Powers> {
        let mask = self.u()?;
        if mask >> NUM_OFFICIAL_POWERS != 0 {
            return None;
        }
        let mut amounts = [0i16; NUM_POWERS];
        for (i, a) in amounts.iter_mut().enumerate() {
            if mask & 1 << i != 0 {
                *a = self.i16()?;
            }
        }
        let just_applied = self.u()?;
        Some(Powers::from_parts(amounts, just_applied))
    }

    fn monster(&mut self) -> Option<Monster> {
        let kind = *MONSTER_KINDS.get(self.byte()? as usize)?;
        Some(Monster {
            kind,
            hp: self.i16()?,
            max_hp: self.i16()?,
            block: self.i16()?,
            powers: self.powers()?,
            moves: [self.byte()?, self.byte()?],
            rolled_damage: self.i16()?,
            escaped: self.byte()? != 0,
            ascension: Ascension(0),
        })
    }
}

/// The state `bytes` encode, or `None` if they aren't this codec version's
/// encoding of a state.
pub fn try_decode(bytes: &[u8]) -> Option<CombatState> {
    let mut r = Reader { b: bytes, at: 0 };
    if r.byte()? != CODEC_VERSION {
        return None;
    }
    let character = match r.byte()? {
        0 => Character::Ironclad,
        1 => Character::Silent,
        _ => return None,
    };
    let no_death = r.byte()? != 0;
    let player =
        Player { hp: r.i16()?, max_hp: r.i16()?, block: r.i16()?, energy: i16::try_from(r.i()?).ok()?, powers: r.powers()?, relics: Relics::default(), potions: Potions::default() };
    let mut monsters = [Monster::default(); MAX_MONSTERS];
    let mask = r.byte()?;
    for (i, m) in monsters.iter_mut().enumerate() {
        if mask & 1 << i != 0 {
            *m = r.monster()?;
        }
    }
    let hand = r.pile::<HAND_LIMIT>()?;
    let (draw, discard, exhaust) = (r.pile::<PILE_RUN_CAP>()?, r.pile::<PILE_RUN_CAP>()?, r.pile::<PILE_RUN_CAP>()?);
    let mut piles = Piles::default();
    piles.set(Run::Draw, draw);
    piles.set(Run::Discard, discard);
    piles.set(Run::Exhaust, exhaust);
    let turn = u16::try_from(r.u()?).ok()?;
    let stage = match r.byte()? {
        0 => Stage::PlayerTurn,
        1 => Stage::PlayingCard { card: r.card()?, target: r.opt()?, next: r.byte()?, hit: r.byte()?, x: 0, more: InPlay::default() },
        8 => {
            let (card, target, next, hit, x) = (r.card()?, r.opt()?, r.byte()?, r.byte()?, r.byte()?);
            let (replays, copy) = (r.byte()?, r.byte()?);
            let pick = r.pick()?;
            if copy > 31 || copy & 24 == 16 {
                return None;
            }
            let save = (copy & 8 != 0).then_some(copy & 16 != 0);
            let more = InPlay { pick, replays, copy: copy & 1 != 0, exhaust: copy & 2 != 0, queued: copy & 4 != 0, save };
            if more == InPlay::default() {
                return None;
            }
            Stage::PlayingCard { card, target, next, hit, x, more }
        }
        7 => {
            let (card, target, next, hit) = (r.card()?, r.opt()?, r.byte()?, r.byte()?);
            match r.byte()? {
                0 => return None,
                x => Stage::PlayingCard { card, target, next, hit, x, more: InPlay::default() },
            }
        }
        9 => {
            let len = usize::try_from(r.u()?).ok()?;
            let name = std::str::from_utf8(r.b.get(r.at..r.at.checked_add(len)?)?).ok()?;
            r.at += len;
            // A potion this process knows (a pack potion's pack loaded).
            let potion = potion_id(name).ok()?;
            potion.spec()?;
            Stage::UsingPotion { potion, target: r.opt()?, next: r.byte()?, hit: r.byte()?, pick: r.pick()? }
        }
        10 => Stage::RelicPick { relic: r.byte()?, hook: r.byte()?, next: r.byte()?, hit: r.byte()?, pick: r.pick()? },
        11 => Stage::RelicOffer { relic: r.byte()?, hook: r.byte()?, next: r.byte()?, pick: r.pick()? },
        12 => match r.byte()? {
            part @ 1..=4 => Stage::EndingTurn { part },
            _ => return None,
        },
        13 => Stage::MonsterActing { slot: r.byte()?, next: r.byte()? },
        2 => Stage::MonsterRolls { next: r.byte()? },
        3 => Stage::StartTurn,
        4 => Stage::TurnStarted,
        5 => Stage::Over { won: false },
        6 => Stage::Over { won: true },
        _ => return None,
    };
    let pending = match r.byte()? {
        0 => None,
        // A draw puts its cards in the hand: no more than it has room for.
        1 => {
            let n = r.byte()?;
            if hand.len() + n as usize > HAND_LIMIT {
                return None;
            }
            Some(ChanceEvent::Draw { n })
        }
        2 => Some(ChanceEvent::MonsterMove { slot: r.byte()? }),
        3 => Some(ChanceEvent::RandomTarget { amount: r.i16()? }),
        4 => Some(ChanceEvent::RandomExhaust),
        5 => Some(ChanceEvent::AllyBlock { slot: r.byte()? }),
        7 => Some(ChanceEvent::RandomCost),
        8 => Some(ChanceEvent::RandomZeroCost),
        9 => Some(ChanceEvent::RandomFreeTurn),
        10 => Some(ChanceEvent::RandomUpgrade),
        12 => Some(ChanceEvent::PlainHit { amount: r.i16()? }),
        11 => Some(ChanceEvent::ExhaustSave {
            queued: match r.byte()? {
                0 => false,
                1 => true,
                _ => return None,
            },
        }),
        6 => Some(ChanceEvent::TakeTop {
            exhaust: match r.byte()? {
                0 => false,
                1 => true,
                _ => return None,
            },
        }),
        13 => Some(ChanceEvent::Order {
            then: match r.byte()? {
                0 => OrderThen::Nothing,
                1 => OrderThen::Draw(r.byte()?),
                2 => OrderThen::TakeTop {
                    exhaust: match r.byte()? {
                        0 => false,
                        1 => true,
                        _ => return None,
                    },
                },
                _ => return None,
            },
        }),
        14 => Some(ChanceEvent::InsertAt { card: r.card()? }),
        15 => Some(ChanceEvent::IntentClass { slot: r.byte().filter(|&k| (k as usize) < MAX_MONSTERS)? }),
        16 => Some(ChanceEvent::RolledAmount { slot: r.byte().filter(|&k| (k as usize) < MAX_MONSTERS)? }),
        _ => return None,
    };
    let mut deferred_block = [0i16; MAX_MONSTERS];
    let mask = r.byte()?;
    for (i, b) in deferred_block.iter_mut().enumerate() {
        if mask & 1 << i != 0 {
            *b = r.i16()?;
        }
    }
    let s = CombatState {
        player,
        monsters,
        hand,
        free_in_hand: FreeMarks::default(),
        turn_costs: TurnCosts::default(),
        cost_rolls: CostRolls::default(),
        owed: Owed::default(),
        owed_late: Owed::default(),
        piles,
        top_queue: TopQueue::default(),
        turn,
        stage,
        pending,
        deferred_block,
        block_broken: [0; MAX_MONSTERS],
        created: u16::try_from(r.u()?).ok()?,
        removed: u16::try_from(r.u()?).ok()?,
        character,
        start_hp: r.i16()?,
        cards_played_this_turn: r.byte()?,
        card_hp_losses: r.byte()?,
        unfired_exhausts: 0,
        unfired_draws: 0,
        unfired_curse_draws: 0,
        times_lost_hp: 0,
        win_heal: character.win_heal(),
        escaped: false,
        boss_fight: false,
        owed_draw: 0,
        no_death,
        binding: Binding::default(),
        offer: Default::default(),
        top: Top::default(),
        won_healed: Default::default(),
        dealt: 0,
        turn_ending: false,
        monsters_acting: false,
        allies_at_move: 0,
        intent_hidden: [0; MAX_MONSTERS],
        bottled: [None; 3],
        ascension: Ascension(0),
    };
    let mut s = s;
    // Optional trailer sections, in order: 1 the known top, 2 the variants,
    // 3 the exhaust-trigger counters, ... 7 the relics, 8 the potions, 9
    // the marked hand cards, 10 the escape, 11 the boss-fight mark, 12 the
    // cards waiting to be played, 13 the changed copies other than grown
    // damage, 14 the cards waiting for a cost roll, 15 the owed work, 16
    // the blocks broken.
    let mut last = 0;
    // The changed copies sections 2 or 13 define, in rank order.
    let mut changed: Vec<CardId> = Vec::new();
    while r.at < bytes.len() {
        let tag = r.byte()?;
        if tag <= last {
            return None;
        }
        last = tag;
        match tag {
            1 => {
                let known: Vec<_> = (0..r.byte()?).map(|_| r.card()).collect::<Option<_>>()?;
                let floaters: Vec<_> = (0..r.u()?).map(|_| Some((r.card()?, r.byte()?))).collect::<Option<_>>()?;
                s.top = Top::from_parts(&known, &floaters)?;
            }
            2 => {
                let n = r.byte()? as usize;
                if n == 0 || n > MAX_CHANGED {
                    return None;
                }
                for _ in 0..n {
                    let (base, damage) = (r.card()?, i16::try_from(r.i()?).ok()?);
                    if !base.is_official() {
                        return None;
                    }
                    let c = changed_copy(base, base.def(), Overrides { damage: Some(damage), level: base.def().level, cost: None }).ok()?;
                    changed.push(c);
                }
            }
            3 => {
                (s.unfired_exhausts, s.owed_draw) = (r.byte()?, r.byte()?);
                if (s.unfired_exhausts, s.owed_draw) == (0, 0) {
                    return None;
                }
            }
            4 => {
                s.unfired_draws = r.byte()?;
                if s.unfired_draws == 0 {
                    return None;
                }
            }
            5 => {
                s.times_lost_hp = r.byte()?;
                if s.times_lost_hp == 0 {
                    return None;
                }
            }
            6 => {
                s.win_heal = r.i16()?;
                if s.win_heal == s.character.win_heal() || s.win_heal < 0 {
                    return None;
                }
            }
            7 => {
                let n = r.u()?;
                if n == 0 || n > RELIC_CAP as u64 {
                    return None;
                }
                for _ in 0..n {
                    let len = usize::try_from(r.u()?).ok()?;
                    let name = std::str::from_utf8(r.b.get(r.at..r.at.checked_add(len)?)?).ok()?;
                    r.at += len;
                    // A relic this process knows (a pack relic's pack loaded).
                    crate::registry::relic(name)?;
                    s.player.relics.push(relic_id(name).ok()?, r.i16()?).ok()?;
                }
            }
            8 => {
                let n = r.u()?;
                if n == 0 || n > POTION_CAP as u64 {
                    return None;
                }
                let mut last = "";
                for _ in 0..n {
                    let len = usize::try_from(r.u()?).ok()?;
                    let name = std::str::from_utf8(r.b.get(r.at..r.at.checked_add(len)?)?).ok()?;
                    r.at += len;
                    // A potion this process knows (a pack potion's pack
                    // loaded), written in the held order.
                    let id = potion_id(name).ok()?;
                    id.spec()?;
                    if id.name() < last {
                        return None;
                    }
                    last = id.name();
                    s.player.potions.insert(id).ok()?;
                }
            }
            // Section 13 (changed copies other than grown damage) holds
            // every copy; never beside section 2.
            13 if changed.is_empty() => {
                let n = r.byte()? as usize;
                if n == 0 || n > MAX_CHANGED {
                    return None;
                }
                let mut damage_only = true;
                for _ in 0..n {
                    let base = r.card()?;
                    if !base.is_official() {
                        return None;
                    }
                    let level = r.byte()?;
                    let flags = r.byte()?;
                    if flags > 3 {
                        return None;
                    }
                    let damage = if flags & 1 != 0 { Some(i16::try_from(r.i()?).ok()?) } else { None };
                    let cost = if flags & 2 != 0 { Some(i8::try_from(r.byte()?).ok().filter(|c| (0..=3).contains(c))?) } else { None };
                    damage_only &= damage.is_some() && cost.is_none() && level == base.def().level;
                    // A level 2 and up copy grows from its pair's level-1 id;
                    // one at its base's level must differ from it.
                    if (level >= 2 && base.def().level != 1) || (level < 2 && level != base.def().level) {
                        return None;
                    }
                    let o = Overrides { damage, level, cost };
                    // Only numbers that differ from the copy's level (else
                    // the bytes would re-encode otherwise).
                    let c = changed_copy(base, base.def(), o).ok()?;
                    if copy_of(c) != Some((base, o)) {
                        return None;
                    }
                    changed.push(c);
                }
                if damage_only {
                    return None;
                }
            }
            14 => {
                let n = r.byte()? as usize;
                if n == 0 || n > HAND_LIMIT {
                    return None;
                }
                let mut read = Vec::with_capacity(n);
                for _ in 0..n {
                    let c = r.card()?;
                    let marked = match r.byte()? {
                        0 => false,
                        1 => true,
                        _ => return None,
                    };
                    s.cost_rolls.push(c, marked);
                    read.push((c, marked));
                }
                // In roll order, as written.
                if s.cost_rolls.iter().ne(read.iter().copied()) {
                    return None;
                }
            }
            17 => {
                s.dealt = r.i16()?;
                if s.dealt <= 0 {
                    return None;
                }
            }
            18 => {
                let a = r.byte()?;
                if a == 0 || a > MAX_ASCENSION {
                    return None;
                }
                s.ascension = Ascension(a);
                for m in s.monsters.iter_mut().filter(|m| m.kind != MonsterKind::None) {
                    m.ascension = s.ascension;
                }
            }
            19 => {
                s.unfired_curse_draws = r.byte()?;
                if s.unfired_curse_draws == 0 {
                    return None;
                }
            }
            20 => {
                let mask = r.byte()?;
                if mask == 0 || mask >> MAX_MONSTERS != 0 {
                    return None;
                }
                for i in 0..MAX_MONSTERS {
                    if mask & 1 << i != 0 {
                        let b = r.byte()?;
                        // Only the defined bits, a class only with the move hidden.
                        if b == 0 || b >> 5 != 0 || (b & crate::state::HIDDEN_CLASS == crate::state::HIDDEN_CLASS) || (b & !crate::state::HIDDEN_ROLLED != 0 && b & crate::state::HIDDEN_MOVE == 0) {
                            return None;
                        }
                        s.intent_hidden[i] = b;
                    }
                }
            }
            21 => {
                let n = r.byte()? as usize;
                if n == 0 || n > OWED_CAP {
                    return None;
                }
                let mut owed = Owed::default();
                for _ in 0..n {
                    let (b, k) = (r.byte()?, r.byte()?);
                    let kind = match b {
                        6 => OwedKind::Top { exhaust: false },
                        7 => OwedKind::Top { exhaust: true },
                        _ => return None,
                    };
                    if k == 0 {
                        return None;
                    }
                    owed.push(kind, k, false);
                }
                // As written: no two neighbours the same work (they join).
                if owed.iter().count() != n {
                    return None;
                }
                s.owed_late = owed;
            }
            22 => {
                let n = r.byte()? as usize;
                let pairs: Vec<_> = (0..n).map(|_| Some((r.card()?, r.byte()?))).collect::<Option<_>>()?;
                s.turn_costs = TurnCosts::from_pairs(&pairs)?;
                // Marks only copies in hand, one mark a copy.
                if s.turn_costs.iter().any(|(c, _)| s.turn_costs.count(c) + s.free_in_hand.count(c) > s.hand.count(c)) {
                    return None;
                }
            }
            16 => {
                let mask = r.byte()?;
                if mask == 0 || mask >> MAX_MONSTERS != 0 {
                    return None;
                }
                for (i, n) in s.block_broken.iter_mut().enumerate() {
                    if mask & 1 << i != 0 {
                        *n = r.byte()?;
                        if *n == 0 {
                            return None;
                        }
                    }
                }
            }
            15 => {
                let n = r.byte()? as usize;
                if n == 0 || n > OWED_CAP {
                    return None;
                }
                let mut owed = Owed::default();
                for _ in 0..n {
                    let (b, k) = (r.byte()?, r.byte()?);
                    let kind = match b & 0x7f {
                        0 => OwedKind::ZeroCost,
                        1 => OwedKind::FreeTurn,
                        2 => OwedKind::Upgrade,
                        3 => OwedKind::Draw,
                        4 => OwedKind::Hit { amount: r.i16()? },
                        5 => OwedKind::Insert { card: r.card()? },
                        _ => return None,
                    };
                    if k == 0 {
                        return None;
                    }
                    owed.push(kind, k, b & 0x80 != 0);
                }
                // As written: no two neighbours the same work (they join).
                if owed.iter().count() != n {
                    return None;
                }
                s.owed = owed;
            }
            12 => {
                let n = r.byte()? as usize;
                if n == 0 || n > TOP_QUEUE_CAP {
                    return None;
                }
                for _ in 0..n {
                    let (card, target, x) = (r.card()?, r.opt()?, r.byte()?);
                    let exhaust = match r.byte()? {
                        0 => false,
                        1 => true,
                        _ => return None,
                    };
                    s.top_queue.push(Queued { card, target, x, exhaust });
                }
            }
            9 => {
                let ids: Vec<_> = (0..r.byte()?).map(|_| r.card()).collect::<Option<_>>()?;
                s.free_in_hand = FreeMarks::from_ids(&ids)?;
                // Marks only copies in hand.
                if s.free_in_hand.iter().any(|c| s.free_in_hand.count(c) > s.hand.count(c)) {
                    return None;
                }
            }
            // Only a fight won by the escape.
            10 if s.stage == (Stage::Over { won: true }) => s.escaped = true,
            11 => s.boss_fight = true,
            _ => return None,
        }
    }
    // Rank bytes become the changed copies they name: in pile order, each
    // named at least once, none past the list.
    if changed.windows(2).any(|w| order_key(w[0]) >= order_key(w[1])) {
        return None;
    }
    let s = resolve_ranks(&s, &changed)?;
    if changed_ranks(&s) != changed {
        return None;
    }
    // A cost roll waits only for hand copies: marked ones for marked
    // copies, unmarked for unmarked; the roll's event, only with one waiting.
    for (c, _) in s.cost_rolls.iter() {
        let (marked, all) = s.cost_rolls.iter().filter(|&(x, _)| x == c).fold((0u8, 0u8), |(m, a), (_, k)| (m + k as u8, a + 1));
        let marks = s.free_in_hand.count(c);
        if marked > marks || all - marked > s.hand.count(c) - marks {
            return None;
        }
    }
    if s.pending == Some(ChanceEvent::RandomCost) && s.cost_rolls.is_empty() {
        return None;
    }
    // Every card id names a card this state holds.
    let held = |p: PileRef<'_>| p.iter().all(|(c, _)| s.binding.is_bound(c));
    let in_play = match s.stage {
        Stage::PlayingCard { card, .. } => s.binding.is_bound(card),
        // The relic and its hook exist, and the hook's effects run on from `next`.
        Stage::RelicPick { relic, hook, next, .. } => {
            (relic as usize) < s.player.relics.len()
                && s.player.relics.id(relic as usize).hooks().get(hook as usize).is_some_and(|h| {
                    next as usize <= h.effects.len() && !matches!(h.effects.get(next as usize), Some(Effect::Pick { .. }))
                })
        }
        Stage::RelicOffer { relic, hook, next, .. } => {
            (relic as usize) < s.player.relics.len()
                && s.player.relics.id(relic as usize).hooks().get(hook as usize).is_some_and(|h| next as usize <= h.effects.len())
        }
        _ => true,
    };
    // A queued card is held and its target a slot (act1-singles spec).
    let queued = s.top_queue.iter().all(|q| s.binding.is_bound(q.card) && q.target.is_none_or(|t| (t as usize) < MAX_MONSTERS));
    if !s.all_piles().into_iter().all(held) || !in_play || !s.top.within(s.draw()) || !queued {
        return None;
    }
    (r.at == bytes.len()).then_some(s)
}

/// `s` with every card read as a byte (`Reader::card`) resolved by
/// `byte_card` against `ranks`; `None` if a byte names no card.
fn resolve_ranks(s: &CombatState, ranks: &[CardId]) -> Option<CombatState> {
    let f = |c: CardId| byte_card(ranks, u8::try_from(c.0).ok()?);
    let pile = |p: PileRef<'_>| -> Option<Pile> {
        let mut q = Pile::default();
        for (c, n) in p.iter() {
            q.add(f(c)?, n);
        }
        Some(q)
    };
    let mut t = s.clone();
    t.hand = Hand::from_pile(pile(s.hand.view())?);
    t.set_draw(pile(s.draw())?);
    t.set_discard(pile(s.discard())?);
    t.set_exhaust(pile(s.exhaust())?);
    if !s.top.is_empty() {
        let known: Vec<CardId> = s.top.known().map(f).collect::<Option<_>>()?;
        let floaters: Vec<(CardId, u8)> = s.top.floaters().map(|(c, a)| Some((f(c)?, a))).collect::<Option<_>>()?;
        t.top = Top::from_parts(&known, &floaters)?;
    }
    if !s.free_in_hand.is_empty() {
        let mut ids: Vec<CardId> = s.free_in_hand.iter().map(f).collect::<Option<_>>()?;
        ids.sort();
        t.free_in_hand = FreeMarks::from_ids(&ids)?;
    }
    if !s.turn_costs.is_empty() {
        let mut marks: Vec<(CardId, u8)> = s.turn_costs.iter().map(|(c, v)| Some((f(c)?, v))).collect::<Option<_>>()?;
        marks.sort();
        t.turn_costs = TurnCosts::from_pairs(&marks)?;
    }
    let mut rolls = CostRolls::default();
    for (c, marked) in s.cost_rolls.iter() {
        rolls.push(f(c)?, marked);
    }
    t.cost_rolls = rolls;
    let mut q = TopQueue::default();
    for x in s.top_queue.iter() {
        q.push(Queued { card: f(x.card)?, ..*x });
    }
    t.top_queue = q;
    if let Stage::PlayingCard { card, .. } = &mut t.stage {
        *card = f(*card)?;
    }
    if let Some(ChanceEvent::InsertAt { card }) = &mut t.pending {
        *card = f(*card)?;
    }
    if s.owed.iter().any(|e| matches!(e.kind, OwedKind::Insert { .. })) {
        let mut owed = Owed::default();
        for e in s.owed.iter() {
            let kind = match e.kind {
                OwedKind::Insert { card } => OwedKind::Insert { card: f(card)? },
                k => k,
            };
            owed.push(kind, e.n, e.wait);
        }
        t.owed = owed;
    }
    Some(t)
}

/// The state `bytes` encode. Panics on bytes that aren't an encoding.
pub fn decode(bytes: &[u8]) -> CombatState {
    try_decode(bytes).expect("not an encoded combat state of this codec version")
}

/// An action's bytes, for the database's per-option action groups.
/// Tags: 0 EndTurn, 1 Play, 2 Choose (the card), 3 Done, 4 UsePotion (the
/// slot, then the target). A changed copy can't be written without its
/// state: `encode_action_in`.
pub fn encode_action(a: Action, out: &mut Vec<u8>) {
    encode_action_in(&[], a, out)
}

/// `encode_action` for an action of a state whose `changed_ranks` are
/// `ranks`: a changed copy as its rank byte.
pub fn encode_action_in(ranks: &[CardId], a: Action, out: &mut Vec<u8>) {
    let mut w = Writer { out: Vec::new(), ranks: Vec::new() };
    match a {
        Action::EndTurn => w.byte(0),
        Action::Play { card, target } => {
            w.byte(1);
            w.byte(card_byte(ranks, card));
            w.opt(target);
        }
        Action::Choose(card) => {
            w.byte(2);
            w.byte(card_byte(ranks, card));
        }
        Action::Done => w.byte(3),
        Action::UsePotion { slot, target } => {
            w.byte(4);
            w.byte(slot);
            w.opt(target);
        }
    }
    out.extend(w.out);
}

/// Reads one action written by `encode_action` from `bytes` at `*at`.
pub fn decode_action(bytes: &[u8], at: &mut usize) -> Option<Action> {
    decode_action_in(&[], bytes, at)
}

/// `decode_action` for an action of a state whose `changed_ranks` are
/// `ranks`.
pub fn decode_action_in(ranks: &[CardId], bytes: &[u8], at: &mut usize) -> Option<Action> {
    let mut r = Reader { b: bytes, at: *at };
    let card = |r: &mut Reader| byte_card(ranks, r.byte()?);
    let a = match r.byte()? {
        0 => Action::EndTurn,
        1 => Action::Play { card: card(&mut r)?, target: r.opt()? },
        2 => Action::Choose(card(&mut r)?),
        3 => Action::Done,
        4 => Action::UsePotion { slot: r.byte()?, target: r.opt()? },
        _ => return None,
    };
    *at = r.at;
    Some(a)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn monster_kinds_in_code_order() {
        for (i, k) in MONSTER_KINDS.iter().enumerate() {
            assert_eq!(k.0 as usize, i);
        }
    }

    #[test]
    fn varints_round_trip() {
        for v in [0i64, 1, -1, 63, -64, 64, 300, -300, i16::MIN as i64, i16::MAX as i64, u16::MAX as i64] {
            let mut w = Writer { out: Vec::new(), ranks: Vec::new() };
            w.i(v);
            let mut r = Reader { b: &w.out, at: 0 };
            assert_eq!(r.i(), Some(v));
            assert_eq!(r.at, w.out.len());
        }
    }
}
