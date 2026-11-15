//! Combat state and the rules that move it forward.
//!
//! The state holds no RNG. It runs deterministically until it needs a player
//! decision or a random event; at a random event it pauses with `pending` set
//! (see `chance.rs`).

use crate::cards::{CardDef, CardId, CardKind, CardType, Tag, NUM_CARDS, NUM_OFFICIAL_CARDS};
use crate::chance::ChanceEvent;
use crate::character::Character;
use crate::effects::{Amount, Effect, PickKind, PileKind, Quantity, Target, Types};
use crate::hooks::{
    Condition, Hook, HpLossFrom, Modifies, Replace, Replaced, Replacement, Side, StaticCondition, StaticStage, Trigger, GENERIC_STATICS,
    ATTACKED_POWERS, ATTACK_HIT_POWERS, REPLACEMENT_POWERS, ROUND_END_POWERS,
};
use crate::monsters::{guardian, hexaghost, lagavulin, Ascension, EliteBuff, Encounter, EncounterGroup, Monster, MonsterKind, MoveDef, MoveId, NO_MOVE};
use crate::potions::{potion_id, PotionId, PotionSpec, Potions};
use crate::relics::{relic_id, RelicSpec, Relics};
use crate::powers::{Power, Powers};
use crate::registry::Binding;
use crate::rng::Rng;

/// `CombatState::next_draw` (the next turn's start draw), a child module
/// so it reads the hook passes' private conditions.
#[path = "next_draw.rs"]
mod next_draw;

pub const MAX_MONSTERS: usize = 5;
pub const HAND_LIMIT: usize = 10;
pub const ENERGY_PER_TURN: i8 = 3;
/// The most block a creature holds (the game's `AbstractCreature.addBlock`:
/// `currentBlock` stops at 999).
pub const BLOCK_CAP: i16 = 999;
/// The most energy the player holds (the game's `EnergyPanel.addEnergy`).
pub const ENERGY_CAP: i16 = 999;

/// `block` plus `n` (a gain), at most `BLOCK_CAP`.
pub(crate) fn gained_block(block: i16, n: i16) -> i16 {
    block.saturating_add(n).min(BLOCK_CAP)
}
pub const DRAW_PER_TURN: u8 = 5;
/// In no-death mode a combat still running after this many turns ends as a
/// loss (learned play's training simulation).
pub const NO_DEATH_TURN_LIMIT: u16 = 50;

/// Slots of the dense form debug text prints: every card id, padded to
/// whole 8-byte words (the layout before piles became lists).
const PILE_SLOTS: usize = NUM_CARDS.div_ceil(8) * 8;

/// The dense form's length while a fight had 32 card slots (ids below 196,
/// padded): debug text prints the ids past it only when one is used, so
/// it reads as it did before the 40 slots (docs/specs/act1-singles.md
/// section 5).
const PILE_SLOTS_32: usize = (NUM_OFFICIAL_CARDS + 2 * 32 + 4).div_ceil(8) * 8;

/// Entries the draw, discard and exhaust piles hold inline, together, an
/// entry being one kind of copy in one pile with its count
/// (docs/specs/sparse-piles.md). Past it the whole list moves to a boxed
/// spill (`Piles::spill`): the game has no limit.
pub const PILES_INLINE: usize = 64;

/// Most entries (distinct cards) one pile holds: its length is a `u8`. An
/// owned `Pile` holds as many. The game has no limit; 255 kinds in one
/// pile is past every card pool. More panics.
pub const PILE_RUN_CAP: usize = 255;

/// Entries a deck leaves free in a pile at fight start for cards the fight
/// makes (statuses, made and discovered copies).
pub const MADE_ROOM: usize = 12;

/// The most entries a deck's cards can take in the shared list: a kind with
/// `k` copies takes at most `min(k, 3)`, one per pile (draw, discard,
/// exhaust), so 60 Strikes take 3 (docs/specs/sparse-piles.md).
pub fn entries_needed<T: Ord>(deck: &[T]) -> usize {
    let mut v: Vec<&T> = deck.iter().collect();
    v.sort();
    v.chunk_by(|a, b| a == b).map(|g| g.len().min(3)).sum()
}

/// Whether a deck fits one pile with `MADE_ROOM` to spare; the refusal
/// names the bound. No content splits copies by their own numbers on draw
/// yet; one that does (Snecko Eye) bounds the cards instead
/// (docs/specs/sparse-piles.md step c).
pub fn deck_fits<T: Ord>(deck: &[T]) -> Result<(), String> {
    let mut v: Vec<&T> = deck.iter().collect();
    v.sort();
    v.dedup();
    let n = v.len();
    if n + MADE_ROOM > PILE_RUN_CAP {
        return Err(format!(
            "a deck of {n} distinct cards: with {MADE_ROOM} left for cards the fight makes (MADE_ROOM) that passes PILE_RUN_CAP = {PILE_RUN_CAP}, the entries one pile holds"
        ));
    }
    Ok(())
}

/// The dense form (a count per card id), showing the reserved
/// generated-card slots only when one is used, and the ids of slots 34 on
/// only when one of those is, so debug text (the codec golden file, the
/// turn-start pins) reads as it did before the slots.
/// Card ids past the dense form (slot 40 and up) widen it as far as they
/// need; changed copies (docs/specs/sparse-piles.md) print after it as
/// (card id, count), only when the pile holds any.
fn dense_debug(f: &mut std::fmt::Formatter<'_>, p: PileRef<'_>) -> std::fmt::Result {
    let top = p.iter().filter(|(c, _)| !crate::registry::is_changed(*c)).map(|(c, _)| c.0 as usize + 1).max().unwrap_or(0);
    let mut dense = vec![0u8; PILE_SLOTS.max(top.div_ceil(8) * 8)];
    let mut changed = Vec::new();
    for (c, n) in p.iter() {
        if crate::registry::is_changed(c) {
            changed.push((c.0, n));
        } else {
            dense[c.0 as usize] = n;
        }
    }
    let used = dense[NUM_OFFICIAL_CARDS..].iter().any(|&n| n > 0);
    let wide = dense[PILE_SLOTS_32..].iter().any(|&n| n > 0);
    let counts = match (used, wide) {
        (false, _) => &dense[..NUM_OFFICIAL_CARDS],
        (true, false) => &dense[..PILE_SLOTS_32],
        (true, true) if top <= PILE_SLOTS => &dense[..PILE_SLOTS],
        (true, true) => &dense[..],
    };
    let mut d = f.debug_struct("Pile");
    d.field("counts", &counts);
    if !changed.is_empty() {
        d.field("changed", &changed);
    }
    d.finish()
}

/// Where `c` sits in a run sorted by pile order (`registry::order_key`:
/// card id, with changed copies where the variant ids once sat): `Ok` at
/// its entry, `Err` where it would go.
#[inline]
fn run_find(ids: &[u16], c: CardId) -> Result<usize, usize> {
    let k = crate::registry::order_key(c);
    for (i, &id) in ids.iter().enumerate() {
        if id == c.0 {
            return Ok(i);
        }
        if crate::registry::order_key(CardId(id)) > k {
            return Err(i);
        }
    }
    Err(ids.len())
}

/// Adds `n` of `c` to the run `a..b` of a list holding `total` entries in
/// `ids`/`counts` (each a whole list's arrays). Returns whether a new entry
/// was made (the entries after it moved up one).
#[inline]
fn run_add(ids: &mut [u16], counts: &mut [u8], total: usize, a: usize, b: usize, c: CardId, n: u8, what: &str) -> bool {
    match run_find(&ids[a..b], c) {
        Ok(i) => {
            counts[a + i] += n;
            false
        }
        Err(i) => {
            let cap = ids.len();
            assert!(total < cap, "{what} holding {cap} entries (distinct cards) gained a new one, card id {}", c.0);
            let i = a + i;
            ids.copy_within(i..total, i + 1);
            counts.copy_within(i..total, i + 1);
            ids[i] = c.0;
            counts[i] = n;
            true
        }
    }
}

/// Removes `n` of `c` from the run `a..b` (as `run_add`). Returns whether
/// its entry went (the entries after it moved down one; the freed one is
/// zeroed, so equal lists stay equal bytes).
#[inline]
fn run_remove(ids: &mut [u16], counts: &mut [u8], total: usize, a: usize, b: usize, c: CardId, n: u8) -> bool {
    let Ok(i) = run_find(&ids[a..b], c) else {
        panic!("removing {n} of {} from a pile holding 0", c.name());
    };
    let i = a + i;
    let k = counts[i];
    assert!(k >= n, "removing {n} of {} from a pile holding {k}", c.name());
    counts[i] -= n;
    if counts[i] != 0 {
        return false;
    }
    ids.copy_within(i + 1..total, i);
    counts.copy_within(i + 1..total, i);
    ids[total - 1] = 0;
    counts[total - 1] = 0;
    true
}

/// A pile's entries, read only: (card id, count) sorted by id, counts > 0.
/// The hand's own list, a run of the shared list, or an owned `Pile`.
#[derive(Clone, Copy)]
pub struct PileRef<'a> {
    ids: &'a [u16],
    counts: &'a [u8],
}

impl std::fmt::Debug for PileRef<'_> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        dense_debug(f, *self)
    }
}

impl<'a> PileRef<'a> {
    pub fn len(&self) -> usize {
        self.counts.iter().map(|&n| n as usize).sum()
    }

    pub fn is_empty(&self) -> bool {
        self.ids.is_empty()
    }

    #[inline]
    pub fn count(&self, c: CardId) -> u8 {
        match run_find(self.ids, c) {
            Ok(i) => self.counts[i],
            Err(_) => 0,
        }
    }

    /// Non-empty entries in card id order.
    pub fn iter(&self) -> impl Iterator<Item = (CardId, u8)> + 'a {
        let (ids, counts) = (self.ids, self.counts);
        (0..ids.len()).map(move |i| (CardId(ids[i]), counts[i]))
    }

    /// The `i`-th card when the pile is laid out in card id order.
    pub fn nth(&self, mut i: usize) -> CardId {
        for (c, n) in self.iter() {
            if i < n as usize {
                return c;
            }
            i -= n as usize;
        }
        panic!("pile index out of range");
    }

    /// An owned copy.
    pub fn to_pile(&self) -> Pile {
        let mut p = Pile::default();
        let n = self.ids.len();
        p.ids[..n].copy_from_slice(self.ids);
        p.counts[..n].copy_from_slice(self.counts);
        p.n = n as u8;
        p
    }
}

/// Anything a pile's entries can be read from (an argument to
/// `add_pile`, `set_draw`, ...).
pub trait AsPile {
    fn pile(&self) -> PileRef<'_>;
}

impl AsPile for PileRef<'_> {
    fn pile(&self) -> PileRef<'_> {
        *self
    }
}

impl<const N: usize> AsPile for PileN<N> {
    fn pile(&self) -> PileRef<'_> {
        self.view()
    }
}

impl<T: AsPile + ?Sized> AsPile for &T {
    fn pile(&self) -> PileRef<'_> {
        (**self).pile()
    }
}

/// An owned, unordered pile of at most `N` entries: a short list of
/// (card id, count) sorted by id, count > 0, unused entries zero, so equal
/// contents are equal bytes. The hand is one (`Hand`, `HAND_LIMIT`
/// entries); `Pile` holds as many entries as the shared list, so any pile
/// fits one. The draw pile is a pile too, because the player knows its
/// contents but not its order.
#[derive(Clone, Copy)]
pub struct PileN<const N: usize> {
    ids: [u16; N],
    counts: [u8; N],
    n: u8,
}

/// An owned pile any pile fits in.
pub type Pile = PileN<PILE_RUN_CAP>;
/// The hand: at most `HAND_LIMIT` cards, so at most that many entries.
pub type Hand = PileN<HAND_LIMIT>;

/// Only the entries in use (the rest are zero), so equal piles hash
/// equally and the hash reads a few bytes (docs/specs/sparse-piles.md).
impl<const N: usize> std::hash::Hash for PileN<N> {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        let n = self.n as usize;
        self.ids[..n].hash(h);
        h.write(&self.counts[..n]);
    }
}

/// Equal contents, whatever the capacities.
impl<const N: usize, const M: usize> PartialEq<PileN<M>> for PileN<N> {
    fn eq(&self, other: &PileN<M>) -> bool {
        self.view() == other.view()
    }
}

impl<const N: usize> Eq for PileN<N> {}

impl PartialEq for PileRef<'_> {
    fn eq(&self, other: &PileRef<'_>) -> bool {
        self.ids == other.ids && self.counts == other.counts
    }
}

impl<const N: usize> PartialEq<PileN<N>> for PileRef<'_> {
    fn eq(&self, other: &PileN<N>) -> bool {
        *self == other.view()
    }
}

impl<const N: usize> PartialEq<PileRef<'_>> for PileN<N> {
    fn eq(&self, other: &PileRef<'_>) -> bool {
        self.view() == *other
    }
}

impl<const N: usize> std::fmt::Debug for PileN<N> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        dense_debug(f, self.view())
    }
}

impl<const N: usize> Default for PileN<N> {
    fn default() -> PileN<N> {
        PileN { ids: [0; N], counts: [0; N], n: 0 }
    }
}

impl<const N: usize> PileN<N> {
    pub fn from_cards(cards: &[CardId]) -> PileN<N> {
        let mut p = PileN::default();
        for &c in cards {
            p.add(c, 1);
        }
        p
    }

    /// A pile of `p`'s contents.
    pub fn from_pile(p: impl AsPile) -> PileN<N> {
        let mut q = PileN::default();
        q.add_pile(p);
        q
    }

    /// The entries, read only.
    #[inline]
    pub fn view(&self) -> PileRef<'_> {
        let n = self.n as usize;
        PileRef { ids: &self.ids[..n], counts: &self.counts[..n] }
    }

    pub fn len(&self) -> usize {
        self.view().len()
    }

    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    /// Entries in use (distinct cards).
    pub fn entries(&self) -> usize {
        self.n as usize
    }

    #[inline]
    pub fn count(&self, c: CardId) -> u8 {
        self.view().count(c)
    }

    pub fn add(&mut self, c: CardId, n: u8) {
        if n == 0 {
            return;
        }
        let len = self.n as usize;
        if run_add(&mut self.ids, &mut self.counts, len, 0, len, c, n, "a pile (PILE_RUN_CAP, or HAND_LIMIT for the hand)") {
            self.n += 1;
        }
    }

    pub fn remove(&mut self, c: CardId, n: u8) {
        if n == 0 {
            return;
        }
        let len = self.n as usize;
        if run_remove(&mut self.ids, &mut self.counts, len, 0, len, c, n) {
            self.n -= 1;
        }
    }

    pub fn add_pile(&mut self, other: impl AsPile) {
        for (c, n) in other.pile().iter() {
            self.add(c, n);
        }
    }

    pub fn remove_pile(&mut self, other: impl AsPile) {
        for (c, n) in other.pile().iter() {
            self.remove(c, n);
        }
    }

    pub fn clear(&mut self) {
        *self = PileN::default();
    }

    /// Non-empty entries in card id order.
    pub fn iter(&self) -> impl Iterator<Item = (CardId, u8)> + '_ {
        self.view().iter()
    }

    /// The `i`-th card when the pile is laid out in card id order.
    pub fn nth(&self, i: usize) -> CardId {
        self.view().nth(i)
    }
}

/// Which pile of the shared list (`Piles`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Run {
    Exhaust = 0,
    Draw = 1,
    Discard = 2,
}

/// The draw, discard and exhaust piles in one list
/// (docs/specs/sparse-piles.md): sorted by pile, stored exhaust, draw,
/// discard (the pile that changes least first, so inserts shift fewer
/// entries), then by card id, so each pile is a contiguous run that reads
/// as a pile of its own. Unused entries zero. The list is inline while it
/// holds at most `PILES_INLINE` entries; past that the whole list moves to
/// a boxed spill (inline arrays zero), and back inline once it fits again,
/// so a list has one form for its contents.
#[derive(Clone)]
pub struct Piles {
    ids: [u16; PILES_INLINE],
    counts: [u8; PILES_INLINE],
    lens: [u8; 3],
    /// The whole list past `PILES_INLINE` entries.
    spill: Option<Box<Spill>>,
}

/// `Piles`' list past its inline entries: as long as its capacity, entries
/// past the list's zero.
#[derive(Clone)]
struct Spill {
    ids: Vec<u16>,
    counts: Vec<u8>,
}

impl Default for Piles {
    fn default() -> Piles {
        Piles { ids: [0; PILES_INLINE], counts: [0; PILES_INLINE], lens: [0; 3], spill: None }
    }
}

/// Equal entries in use (a spill's capacity doesn't count).
impl PartialEq for Piles {
    fn eq(&self, other: &Piles) -> bool {
        let n = self.total();
        let ((a, ac), (b, bc)) = (self.list(), other.list());
        self.lens == other.lens && a[..n] == b[..n] && ac[..n] == bc[..n]
    }
}

impl Eq for Piles {}

/// Only the entries in use, as `PileN`'s (inline or spilled alike).
impl std::hash::Hash for Piles {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        let n = self.total();
        let (ids, counts) = self.list();
        ids[..n].hash(h);
        h.write(&counts[..n]);
        h.write(&self.lens);
    }
}

impl std::fmt::Debug for Piles {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Piles").field("draw", &self.get(Run::Draw)).field("discard", &self.get(Run::Discard)).field("exhaust", &self.get(Run::Exhaust)).finish()
    }
}

impl Piles {
    /// Entries in use, all piles.
    #[inline]
    pub fn total(&self) -> usize {
        self.lens[0] as usize + self.lens[1] as usize + self.lens[2] as usize
    }

    #[inline]
    fn range(&self, r: Run) -> (usize, usize) {
        let a = match r {
            Run::Exhaust => 0,
            Run::Draw => self.lens[0] as usize,
            Run::Discard => self.lens[0] as usize + self.lens[1] as usize,
        };
        (a, a + self.lens[r as usize] as usize)
    }

    /// The list's arrays (inline or spilled), each as long as its capacity.
    #[inline]
    fn list(&self) -> (&[u16], &[u8]) {
        match &self.spill {
            None => (&self.ids, &self.counts),
            Some(s) => (&s.ids, &s.counts),
        }
    }

    #[inline]
    fn list_mut(&mut self) -> (&mut [u16], &mut [u8]) {
        match &mut self.spill {
            None => (&mut self.ids, &mut self.counts),
            Some(s) => (&mut s.ids, &mut s.counts),
        }
    }

    /// Doubles the room: the inline list moves to a spill, or the spill
    /// grows.
    #[cold]
    fn grow(&mut self) {
        let t = self.total();
        match &mut self.spill {
            Some(s) => {
                s.ids.resize(2 * t, 0);
                s.counts.resize(2 * t, 0);
            }
            None => {
                let mut s = Spill { ids: vec![0; 2 * PILES_INLINE], counts: vec![0; 2 * PILES_INLINE] };
                s.ids[..t].copy_from_slice(&self.ids[..t]);
                s.counts[..t].copy_from_slice(&self.counts[..t]);
                self.ids = [0; PILES_INLINE];
                self.counts = [0; PILES_INLINE];
                self.spill = Some(Box::new(s));
            }
        }
    }

    /// A spilled list that fits inline again moves back.
    fn settle(&mut self) {
        let t = self.total();
        if t <= PILES_INLINE {
            if let Some(s) = self.spill.take() {
                self.ids[..t].copy_from_slice(&s.ids[..t]);
                self.counts[..t].copy_from_slice(&s.counts[..t]);
            }
        }
    }

    #[inline]
    pub fn get(&self, r: Run) -> PileRef<'_> {
        let (a, b) = self.range(r);
        let (ids, counts) = self.list();
        PileRef { ids: &ids[a..b], counts: &counts[a..b] }
    }

    #[inline]
    pub fn get_mut(&mut self, r: Run) -> PileMut<'_> {
        PileMut { piles: self, run: r }
    }

    #[inline]
    fn add(&mut self, r: Run, c: CardId, n: u8) {
        if n == 0 {
            return;
        }
        let (a, b) = self.range(r);
        let t = self.total();
        if t == self.list().0.len() && run_find(&self.list().0[a..b], c).is_err() {
            self.grow();
        }
        let (ids, counts) = self.list_mut();
        if run_add(ids, counts, t, a, b, c, n, "the draw, discard and exhaust piles") {
            let len = &mut self.lens[r as usize];
            *len = len.checked_add(1).unwrap_or_else(|| panic!("a pile holding {PILE_RUN_CAP} entries (PILE_RUN_CAP) gained a new one, card id {}", c.0));
        }
    }

    #[inline]
    fn remove(&mut self, r: Run, c: CardId, n: u8) {
        if n == 0 {
            return;
        }
        let (a, b) = self.range(r);
        let t = self.total();
        let (ids, counts) = self.list_mut();
        if run_remove(ids, counts, t, a, b, c, n) {
            self.lens[r as usize] -= 1;
            if self.spill.is_some() {
                self.settle();
            }
        }
    }

    fn clear(&mut self, r: Run) {
        let (a, b) = self.range(r);
        let t = self.total();
        let (ids, counts) = self.list_mut();
        ids.copy_within(b..t, a);
        counts.copy_within(b..t, a);
        let m = t - (b - a);
        ids[m..t].fill(0);
        counts[m..t].fill(0);
        self.lens[r as usize] = 0;
        if self.spill.is_some() {
            self.settle();
        }
    }

    /// Pile `r` becomes `p`'s contents.
    pub fn set(&mut self, r: Run, p: impl AsPile) {
        let p = p.pile().to_pile();
        self.clear(r);
        for (c, n) in p.iter() {
            self.add(r, c, n);
        }
    }

    /// Pile `to` becomes pile `from`'s contents and `from` empties (the
    /// discard pile shuffled into an empty draw pile).
    pub fn move_all(&mut self, from: Run, to: Run) {
        let p = self.get(from).to_pile();
        self.clear(from);
        self.set(to, p);
    }
}

/// One pile of the shared list, to change.
pub struct PileMut<'a> {
    piles: &'a mut Piles,
    run: Run,
}

impl PileMut<'_> {
    pub fn view(&self) -> PileRef<'_> {
        self.piles.get(self.run)
    }

    pub fn count(&self, c: CardId) -> u8 {
        self.view().count(c)
    }

    pub fn len(&self) -> usize {
        self.view().len()
    }

    pub fn is_empty(&self) -> bool {
        self.view().is_empty()
    }

    pub fn add(&mut self, c: CardId, n: u8) {
        self.piles.add(self.run, c, n);
    }

    pub fn remove(&mut self, c: CardId, n: u8) {
        self.piles.remove(self.run, c, n);
    }

    pub fn add_pile(&mut self, other: impl AsPile) {
        for (c, n) in other.pile().iter() {
            self.add(c, n);
        }
    }

    pub fn remove_pile(&mut self, other: impl AsPile) {
        for (c, n) in other.pile().iter() {
            self.remove(c, n);
        }
    }

    pub fn clear(&mut self) {
        self.piles.clear(self.run);
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct Player {
    pub hp: i16,
    pub max_hp: i16,
    pub block: i16,
    /// At most `ENERGY_CAP`.
    pub energy: i16,
    pub powers: Powers,
    /// The relics held, in order, with their counters
    /// (docs/specs/relic-entity.md); empty in a fight without relics.
    pub relics: Relics,
    /// The potions held, sorted by name (docs/specs/potions.md); empty in
    /// a fight without potions.
    pub potions: Potions,
}

/// As derived, with `relics` and `potions` shown only when any is held, so
/// debug text of relic- and potion-free states reads as before.
impl std::fmt::Debug for Player {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut d = f.debug_struct("Player");
        d.field("hp", &self.hp).field("max_hp", &self.max_hp).field("block", &self.block).field("energy", &self.energy).field("powers", &self.powers);
        if !self.relics.is_empty() {
            d.field("relics", &self.relics);
        }
        if !self.potions.is_empty() {
            d.field("potions", &self.potions);
        }
        d.finish()
    }
}

/// A combatant.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Who {
    Player,
    Monster(u8),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Action {
    /// Play a card from hand. `target` is a monster slot for targeted cards
    /// and `None` for untargeted ones.
    Play { card: CardId, target: Option<u8> },
    EndTurn,
    /// At a pick: take this card (decision-points spec).
    Choose(CardId),
    /// At an "up to n" pick: stop picking.
    Done,
    /// Use the potion at `slot` of the held list (docs/specs/potions.md);
    /// `target` a monster slot for a targeted potion, else `None`.
    UsePotion { slot: u8, target: Option<u8> },
}

/// The cards a `Discover` shows (docs/specs/discovery.md): up to 3 card
/// ids sorted (the screen's order isn't kept, so equal offers are equal
/// states), with what taking one gives. All zero when none is open.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub struct Offer {
    cards: [u16; 3],
    n: u8,
    /// Copies of the card taken, each into hand while it holds fewer than
    /// `HAND_LIMIT`, else into the discard pile.
    pub copies: u8,
    /// The copies cost 0 this turn.
    pub free: bool,
    /// The player may take none (`Done`).
    pub skip: bool,
}

impl Offer {
    pub fn is_empty(&self) -> bool {
        self.n == 0 && self.copies == 0
    }

    /// The cards shown, by card id.
    pub fn cards(&self) -> impl Iterator<Item = CardId> + '_ {
        self.cards[..self.n as usize].iter().map(|&c| CardId(c))
    }
}

/// A pick the card in play is waiting on.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct Pick {
    pub kind: PickKind,
    /// Picks still to make.
    pub left: u8,
    /// Ends by itself after `left` reaches 0; otherwise `Done` is offered.
    pub exact: bool,
    /// Each card it puts into the hand costs 0 this turn
    /// (docs/specs/act1-singles.md).
    pub free: bool,
    /// Only cards of these types can be picked (Dual Wield).
    pub of: Types,
    /// A `CopyInHand` pick's copies per card; 0 for the other kinds.
    pub copies: u8,
}

impl Pick {
    /// A pick of `kind` with every type allowed and no copies.
    pub fn new(kind: PickKind, left: u8, exact: bool, free: bool) -> Pick {
        Pick { kind, left, exact, free, of: Types::ALL, copies: 0 }
    }

    /// The pick an `Effect::Pick` opens, `n` picks left.
    pub fn of_effect(e: &Effect) -> Option<Pick> {
        match *e {
            Effect::Pick { kind, n, exact, free, of, copies } => Some(Pick { kind, left: n, exact, free, of, copies }),
            _ => None,
        }
    }
}

/// `free`, `of` and `copies` shown only when set, so recorded debug text
/// reads as before.
impl std::fmt::Debug for Pick {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut d = f.debug_struct("Pick");
        d.field("kind", &self.kind).field("left", &self.left).field("exact", &self.exact);
        if self.free {
            d.field("free", &self.free);
        }
        if self.of != Types::ALL {
            d.field("of", &self.of);
        }
        if self.copies != 0 {
            d.field("copies", &self.copies);
        }
        d.finish()
    }
}

/// What a card in play carries beyond its position: a pending pick,
/// replays still to come (Burst) and whether it is itself a replayed copy.
/// All empty for existing content.
#[derive(Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct InPlay {
    pub pick: Option<Pick>,
    pub replays: u8,
    pub copy: bool,
    /// It exhausts once played (a card Havoc plays,
    /// docs/specs/act1-singles.md).
    pub exhaust: bool,
    /// Played from the queue (a card Havoc or Distilled Chaos plays): in
    /// the game it sits in limbo, not the hand, so it doesn't count itself
    /// (Perfected Strike).
    pub queued: bool,
    /// The exhaust-save roll (relics' `exhaust_save`, Strange Spoon;
    /// docs/specs/blocked-relics.md step 7): `None` until rolled,
    /// `Some(true)` when the card goes to the discard pile instead of
    /// exhausting.
    pub save: Option<bool>,
}

/// `exhaust` shown only when set, so recorded debug text reads as before.
impl std::fmt::Debug for InPlay {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut d = f.debug_struct("InPlay");
        d.field("pick", &self.pick).field("replays", &self.replays).field("copy", &self.copy);
        if self.exhaust {
            d.field("exhaust", &self.exhaust);
        }
        if self.queued {
            d.field("queued", &self.queued);
        }
        if let Some(v) = self.save {
            d.field("save", &v);
        }
        d.finish()
    }
}

/// A card `PlayTop` took off the draw pile, waiting to be played
/// (docs/specs/act1-singles.md): its target (chosen when taken), the X it
/// plays at, and whether it exhausts.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Queued {
    pub card: CardId,
    pub target: Option<u8>,
    pub x: u8,
    pub exhaust: bool,
}

impl Default for Queued {
    fn default() -> Queued {
        Queued { card: CardId(0), target: None, x: 0, exhaust: false }
    }
}

/// Most cards waiting at once: one use takes at most 6 (Distilled Chaos
/// under Sacred Bark), and Havoc among them adds one as it leaves.
pub const TOP_QUEUE_CAP: usize = 6;

/// The cards `PlayTop` took, played in order from the front once the card
/// or potion in play has finished. Empty except while one resolves.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub struct TopQueue {
    cards: [Queued; TOP_QUEUE_CAP],
    n: u8,
}

impl TopQueue {
    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    pub fn is_full(&self) -> bool {
        self.n as usize == TOP_QUEUE_CAP
    }

    pub fn len(&self) -> usize {
        self.n as usize
    }

    pub fn iter(&self) -> impl Iterator<Item = &Queued> + '_ {
        self.cards[..self.n as usize].iter()
    }

    pub fn push(&mut self, q: Queued) {
        assert!(!self.is_full(), "more than {TOP_QUEUE_CAP} cards taken from the draw pile at once");
        self.cards[self.n as usize] = q;
        self.n += 1;
    }

    pub fn pop_front(&mut self) -> Option<Queued> {
        if self.n == 0 {
            return None;
        }
        let q = self.cards[0];
        self.cards.copy_within(1..self.n as usize, 0);
        self.n -= 1;
        self.cards[self.n as usize] = Queued::default();
        Some(q)
    }
}

/// Where the rules are. Every stage but `PlayerTurn` and `Over` is
/// transient: `run` moves on from it unless a chance event is pending.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Stage {
    PlayerTurn,
    /// A card in play, resolving effect `next` onward. `hit` counts the
    /// hits already made by a `RandomDamage` or `RandomApply` effect at
    /// index `next`. `x` is the energy an X-cost card spent (0 otherwise);
    /// `more` its pick and replays.
    PlayingCard { card: CardId, target: Option<u8>, next: u8, hit: u8, x: u8, more: InPlay },
    /// A potion in use (docs/specs/potions.md), out of the held list,
    /// resolving effect `next` onward as a card's rows; `hit` and `pick` as
    /// a card's. Not a card: no pile, no card hooks.
    UsingPotion { potion: PotionId, target: Option<u8>, next: u8, hit: u8, pick: Option<Pick> },
    /// A relic's hook paused at its pick (Gambling Chip;
    /// docs/specs/fight-vocabulary.md): relic `relic`'s hook `hook`, effect
    /// `next` onward still to run once the pick is done; `hit` counts the
    /// cards picked for a `DrawPicked` at `next`. Opened by the hook's
    /// pass; the player's turn follows.
    RelicPick { relic: u8, hook: u8, next: u8, hit: u8, pick: Option<Pick> },
    /// Monsters pick their next moves, slot `next` onward.
    MonsterRolls { next: u8 },
    StartTurn,
    /// The turn's draw is in; the player's turn-start hooks run next (the
    /// game's post-draw timing: Brutality, Demon Form).
    TurnStarted,
    Over { won: bool },
    /// A relic's `CombatStartPreDraw` hook paused at its `Discover`
    /// (Toolbox; docs/specs/colorless-cards.md step 6): relic `relic`'s
    /// hook `hook`, effect `next` onward (the `Discover` first) still to
    /// run; the offer's chance event and pick land here. Opened once the
    /// pre-draw pass has run; the opening draw (`StartTurn`) follows.
    /// Last in the enum so every other stage hashes as before.
    RelicOffer { relic: u8, hook: u8, next: u8, pick: Option<Pick> },
    /// The player's End Turn paused for random work a hook owed
    /// (docs/specs/blocked-relics.md step 5): part 1 (the first turn-end
    /// pass owed it; the hand's turn-end cards come next), part 3 (those
    /// cards owed it; the powers' `atEndOfTurn` pass comes next), part 4
    /// (that pass owed it; the discard comes next) or part 2 (the turn-end
    /// exhausts' hooks owed it: Dead Branch's card lands in the hand kept
    /// for the next turn; the monsters act next). Only with
    /// work owed; after the enum's others so they hash as before.
    EndingTurn { part: u8 },
    /// The monsters' turn paused at monster `slot`'s `BlockAlly` pick (two
    /// or more candidates; `ChanceEvent::AllyBlock`), or at a player's draw
    /// pending before it; it goes on at effect `next` of that move. Last in
    /// the enum so every other stage hashes as before.
    MonsterActing { slot: u8, next: u8 },
}

#[derive(Debug, PartialEq, Eq)]
pub struct IllegalAction;

/// What a hook's condition looks at: the card played and its chosen target,
/// or, for a `CardDrawn` hook, the drawn card's type.
#[derive(Clone, Copy, Debug, Default)]
struct HookCtx {
    card: Option<CardId>,
    target: Option<u8>,
    drawn: Option<CardType>,
}

/// `xs` with their indices, in order or, with `rev`, from the last.
fn ordered<T>(xs: &[T], rev: bool) -> impl Iterator<Item = (usize, &T)> {
    let n = xs.len();
    (0..n).map(move |k| if rev { n - 1 - k } else { k }).map(move |i| (i, &xs[i]))
}

/// Hand cards that cost 0 this turn (docs/specs/act1-singles.md, the
/// game's `setCostForTurn(0)`): their ids, copies repeated, sorted. Always
/// within the hand's counts; cleared at turn end. Empty unless a pick with
/// `free_this_turn` or `CombatState::mark_free_in_hand` marked a card.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct FreeMarks {
    ids: [u16; HAND_LIMIT],
    n: u8,
}

/// Only the marks in use (the rest are zero), as `Pile`'s.
impl std::hash::Hash for FreeMarks {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        self.ids[..self.n as usize].hash(h);
    }
}

impl FreeMarks {
    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    pub fn len(&self) -> usize {
        self.n as usize
    }

    /// The marked ids, copies repeated, in order.
    pub fn iter(&self) -> impl Iterator<Item = CardId> + '_ {
        self.ids[..self.n as usize].iter().map(|&c| CardId(c))
    }

    pub fn count(&self, c: CardId) -> u8 {
        self.iter().filter(|&x| x == c).count() as u8
    }

    /// Marks one more copy of `c`; false when full.
    pub fn add(&mut self, c: CardId) -> bool {
        let n = self.n as usize;
        if n == HAND_LIMIT {
            return false;
        }
        let i = self.ids[..n].iter().position(|&x| x > c.0).unwrap_or(n);
        self.ids.copy_within(i..n, i + 1);
        self.ids[i] = c.0;
        self.n += 1;
        true
    }

    /// Unmarks one copy of `c`; false when none is marked.
    pub fn remove(&mut self, c: CardId) -> bool {
        let n = self.n as usize;
        let Some(i) = self.ids[..n].iter().position(|&x| x == c.0) else {
            return false;
        };
        self.ids.copy_within(i + 1..n, i);
        self.ids[n - 1] = 0;
        self.n -= 1;
        true
    }

    /// Keeps at most `k` marks on `c`.
    pub fn cap(&mut self, c: CardId, k: u8) {
        while self.count(c) > k {
            self.remove(c);
        }
    }

    pub fn clear(&mut self) {
        *self = FreeMarks::default();
    }

    /// The marks from their ids (the codec); `None` if they can't be one.
    pub fn from_ids(ids: &[CardId]) -> Option<FreeMarks> {
        if ids.is_empty() || ids.len() > HAND_LIMIT || ids.windows(2).any(|w| w[0].0 > w[1].0) {
            return None;
        }
        let mut m = FreeMarks::default();
        for &c in ids {
            m.add(c);
        }
        Some(m)
    }
}

/// A hand copy's class among the copies of its card: no mark, a cost this
/// turn above 0 (`TurnCosts`), or costing 0 this turn (`FreeMarks`). A
/// random pick over the hand rolls over classes, each as heavy as its copies.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HandMark {
    None,
    Turn(u8),
    Free,
}

/// Hand cards that cost a set amount above 0 this turn, below their cost
/// (Enlightenment, the game's `costForTurn` set to 1 on a card of cost 2 or
/// more): one entry per copy, (id, cost this turn) with the cost at least 1,
/// sorted. A copy holds no `FreeMarks` mark as well (that is a cost of 0),
/// so the two marks of a card never exceed its copies in hand; cleared at
/// turn end, and empty unless `CostAtMost` marked a card.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct TurnCosts {
    ids: [u16; HAND_LIMIT],
    costs: [u8; HAND_LIMIT],
    n: u8,
}

/// Only the marks in use (the rest are zero), as `FreeMarks`'.
impl std::hash::Hash for TurnCosts {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        self.ids[..self.n as usize].hash(h);
        self.costs[..self.n as usize].hash(h);
    }
}

impl TurnCosts {
    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    pub fn len(&self) -> usize {
        self.n as usize
    }

    /// The marks (card, cost this turn), copies repeated, in order.
    pub fn iter(&self) -> impl Iterator<Item = (CardId, u8)> + '_ {
        (0..self.n as usize).map(|i| (CardId(self.ids[i]), self.costs[i]))
    }

    pub fn count(&self, c: CardId) -> u8 {
        self.iter().filter(|&(x, _)| x == c).count() as u8
    }

    /// The cost this turn of `c`'s cheapest marked copy.
    pub fn lowest(&self, c: CardId) -> Option<u8> {
        self.iter().filter(|&(x, _)| x == c).map(|(_, v)| v).min()
    }

    /// The cost this turn of `c`'s dearest marked copy.
    pub fn highest(&self, c: CardId) -> Option<u8> {
        self.iter().filter(|&(x, _)| x == c).map(|(_, v)| v).max()
    }

    /// Marks one more copy of `c` at cost `v` (at least 1); false when full.
    pub fn add(&mut self, c: CardId, v: u8) -> bool {
        let n = self.n as usize;
        if n == HAND_LIMIT || v == 0 {
            return false;
        }
        let i = (0..n).position(|i| (self.ids[i], self.costs[i]) > (c.0, v)).unwrap_or(n);
        self.ids.copy_within(i..n, i + 1);
        self.costs.copy_within(i..n, i + 1);
        (self.ids[i], self.costs[i]) = (c.0, v);
        self.n += 1;
        true
    }

    /// Unmarks one copy of `c` at cost `v`; false when none is.
    pub fn remove(&mut self, c: CardId, v: u8) -> bool {
        let n = self.n as usize;
        let Some(i) = (0..n).position(|i| (self.ids[i], self.costs[i]) == (c.0, v)) else {
            return false;
        };
        self.ids.copy_within(i + 1..n, i);
        self.costs.copy_within(i + 1..n, i);
        (self.ids[n - 1], self.costs[n - 1]) = (0, 0);
        self.n -= 1;
        true
    }

    /// Unmarks every copy of `c`, returning their costs, lowest first.
    pub fn take_all(&mut self, c: CardId) -> Vec<u8> {
        let costs: Vec<u8> = self.iter().filter(|&(x, _)| x == c).map(|(_, v)| v).collect();
        for &v in &costs {
            self.remove(c, v);
        }
        costs
    }

    pub fn clear(&mut self) {
        *self = TurnCosts::default();
    }

    /// The marks from their entries (the codec); `None` if they can't be one.
    pub fn from_pairs(pairs: &[(CardId, u8)]) -> Option<TurnCosts> {
        if pairs.is_empty() || pairs.len() > HAND_LIMIT || pairs.iter().any(|&(_, v)| v == 0) || pairs.windows(2).any(|w| (w[0].0 .0, w[0].1) > (w[1].0 .0, w[1].1)) {
            return None;
        }
        let mut m = TurnCosts::default();
        for &(c, v) in pairs {
            m.add(c, v);
        }
        Some(m)
    }
}

/// Hand cards waiting for a random cost roll (docs/specs/sparse-piles.md:
/// Snecko Oil's hand, Confused's draws): one entry per copy, with whether
/// that copy is marked to cost 0 this turn, sorted (pile order, unmarked
/// first) so equal queues are equal states. `ChanceEvent::RandomCost`
/// rolls the first; the stage machine pauses for it as soon as any waits.
/// Empty for content without cost rolls.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct CostRolls {
    ids: [u16; HAND_LIMIT],
    marked: [bool; HAND_LIMIT],
    n: u8,
}

/// Only the entries in use, as `Pile`'s.
impl std::hash::Hash for CostRolls {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        let n = self.n as usize;
        self.ids[..n].hash(h);
        self.marked[..n].hash(h);
    }
}

impl CostRolls {
    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    pub fn len(&self) -> usize {
        self.n as usize
    }

    /// The copies waiting, in roll order, with their marks.
    pub fn iter(&self) -> impl Iterator<Item = (CardId, bool)> + '_ {
        (0..self.n as usize).map(|i| (CardId(self.ids[i]), self.marked[i]))
    }

    /// One more copy of `c` to roll; panics past `HAND_LIMIT` (each entry
    /// is a hand card).
    pub fn push(&mut self, c: CardId, marked: bool) {
        let n = self.n as usize;
        assert!(n < HAND_LIMIT, "more than {HAND_LIMIT} cost rolls waiting");
        let key = (crate::registry::order_key(c), marked);
        let i = (0..n).find(|&i| (crate::registry::order_key(CardId(self.ids[i])), self.marked[i]) > key).unwrap_or(n);
        self.ids.copy_within(i..n, i + 1);
        self.marked.copy_within(i..n, i + 1);
        self.ids[i] = c.0;
        self.marked[i] = marked;
        self.n += 1;
    }

    /// The next copy to roll, taken off the queue.
    pub fn pop_front(&mut self) -> Option<(CardId, bool)> {
        let n = self.n as usize;
        if n == 0 {
            return None;
        }
        let first = (CardId(self.ids[0]), self.marked[0]);
        self.ids.copy_within(1..n, 0);
        self.marked.copy_within(1..n, 0);
        self.ids[n - 1] = 0;
        self.marked[n - 1] = false;
        self.n -= 1;
        Some(first)
    }

    /// The next copy to roll, left on the queue.
    pub fn front(&self) -> Option<(CardId, bool)> {
        self.iter().next()
    }

    pub fn clear(&mut self) {
        *self = CostRolls::default();
    }
}

/// One kind of random work a hook owes (`Owed`; docs/specs/blocked-relics.md
/// step 5): what turns into a chance event once it is paid.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum OwedKind {
    /// A `MakeRandom` roll (Dead Branch), never upgraded (no card in play).
    Make { pool: u8, ty: Option<CardType>, pile: PileKind, zero_cost: bool, free: bool },
    /// A `ZeroCostRandom` pick: costs 0 for the combat.
    ZeroCost,
    /// A `ZeroCostRandomTurn` pick: costs 0 this turn (Mummified Hand).
    FreeTurn,
    /// An `UpgradeRandom` pick (Warped Tongs).
    Upgrade,
    /// A hook's `Draw` behind owed work (it waits its turn, as the game's
    /// queued `DrawCardAction`): `n` counts the cards, drawn at once.
    Draw,
    /// A `PlainDamage` of `amount` (its stacks read when owed) on a random
    /// enemy (Juggernaut, the game's queued `DamageRandomEnemyAction`).
    /// Owed while a card is in play, it waits until the card's effects
    /// have run (the game's `addToBot`), before its reactions queued
    /// later (Curl Up's block) land.
    Hit { amount: i16 },
    /// Frozen Eye: card `card` (already in the draw pile, not yet among
    /// `Top`'s known cards) takes a random spot under the top card
    /// (`ChanceEvent::InsertAt`).
    Insert { card: CardId },
    /// Mayhem: a `PlayTop` take (`exhaust`: the card exhausts when played),
    /// kept in `CombatState::owed_late`, never in `owed`.
    Top { exhaust: bool },
}

/// One entry of `Owed`: `n` times `kind`; `wait` when a hook owed it with
/// a relic's pick or offer open (the game queues it behind that action),
/// so it is paid once the relic's hook has run.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct OwedEntry {
    pub kind: OwedKind,
    pub n: u8,
    pub wait: bool,
}

/// Owed entries' capacity.
pub const OWED_CAP: usize = 8;

/// Random work hooks owe (docs/specs/blocked-relics.md step 5): a hook
/// can't pause for a chance event, so its random effects wait here, in the
/// order they were owed, and `run` pays each before anything else goes on
/// (as `cost_rolls`). Empty unless a hook owed work.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Owed {
    items: [Option<OwedEntry>; OWED_CAP],
    n: u8,
}

/// Nothing when empty, so states without owed work hash as before.
impl std::hash::Hash for Owed {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        if self.n != 0 {
            self.items[..self.n as usize].hash(h);
        }
    }
}

impl Owed {
    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    pub fn iter(&self) -> impl Iterator<Item = OwedEntry> + '_ {
        self.items[..self.n as usize].iter().map(|e| e.expect("an entry in use"))
    }

    pub fn front(&self) -> Option<OwedEntry> {
        self.iter().next()
    }

    /// `n` more of `kind` at the back, joining the last entry when it is
    /// the same work; panics past `OWED_CAP` entries.
    pub fn push(&mut self, kind: OwedKind, n: u8, wait: bool) {
        if n == 0 {
            return;
        }
        let k = self.n as usize;
        if let Some(Some(last)) = k.checked_sub(1).map(|i| &mut self.items[i]) {
            if last.kind == kind && last.wait == wait {
                last.n = last.n.saturating_add(n);
                return;
            }
        }
        assert!(k < OWED_CAP, "more than {OWED_CAP} kinds of random work owed");
        self.items[k] = Some(OwedEntry { kind, n, wait });
        self.n += 1;
    }

    /// Takes `n` (at most the front entry's) off the front entry.
    pub fn take_front(&mut self, n: u8) {
        let Some(e) = self.items[0].as_mut() else { return };
        e.n = e.n.saturating_sub(n);
        if e.n == 0 {
            let k = self.n as usize;
            self.items.copy_within(1..k, 0);
            self.items[k - 1] = None;
            self.n -= 1;
        }
    }

    pub fn clear(&mut self) {
        *self = Owed::default();
    }
}

/// `CombatState::intent_hidden`'s bits (Runic Dome).
pub const HIDDEN_MOVE: u8 = 1;
pub const HIDDEN_ALLIES: u8 = 2;
pub const HIDDEN_CLASS: u8 = 0b1100;
pub const REVEALED_ATTACK: u8 = 0b0100;
pub const REVEALED_NO_ATTACK: u8 = 0b1000;
pub const HIDDEN_ROLLED: u8 = 16;
/// The bits a move set (rolled or by a reaction) clears.
pub const HIDDEN_MASK: u8 = HIDDEN_MOVE | HIDDEN_ALLIES | HIDDEN_CLASS;

/// Whether a move attacks (a `Damage` or `RolledAttack` effect: the game's
/// `getIntentBaseDmg() >= 0`).
pub fn is_attack(mv: &MoveDef) -> bool {
    mv.effects.iter().any(|e| matches!(e, Effect::Damage { .. } | Effect::RolledAttack))
}

/// `Top::known`'s capacity, and `Top::floaters`': entries of (card, above)
/// each with a copy count.
pub const TOP_KNOWN: usize = 16;
pub const TOP_FLOATERS: usize = 8;

/// One of `Top`'s floater entries: (card, above, copies, slack).
type FloaterEntry = (u16, u8, u8, u8);

/// `Top`'s floater entries, oldest first, put in canonical order: each run
/// of neighbours with equal (`above`, slack) sorted by card, equal (card,
/// above, slack) neighbours merged. Returns the entries kept (the rest of
/// the slice is left as is).
fn canon_floaters(f: &mut [FloaterEntry]) -> usize {
    let n = f.len();
    let mut start = 0;
    while start < n {
        let mut end = start + 1;
        while end < n && (f[end].1, f[end].3) == (f[start].1, f[start].3) {
            end += 1;
        }
        f[start..end].sort_unstable_by_key(|x| x.0);
        start = end;
    }
    let mut m = 0;
    for i in 0..n {
        let x = f[i];
        if m > 0 && (f[m - 1].0, f[m - 1].1, f[m - 1].3) == (x.0, x.1, x.3) {
            f[m - 1].2 = f[m - 1].2.saturating_add(x.2);
        } else {
            f[m] = x;
            m += 1;
        }
    }
    m
}

/// Which card of the draw pile a removal takes (`Top::without`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Gone {
    /// The known card at this index (0 = the next drawn).
    Known(usize),
    /// A copy of this floater entry (its newest copy: copies of an entry
    /// are interchangeable).
    Floater(usize),
    /// A card that is neither known nor a floater.
    Plain,
}

/// What the player knows about the draw pile's order (known-top spec):
/// `known` cards on top, the first drawn next, and floaters: a known card
/// at an unknown position with `above` cards certainly above it, known or
/// not (draw-knowledge spec item 1): it is not among the pile's top `above`
/// cards once the floaters put in after it are left out. So drawing a card
/// that is no floater lowers every positive `above` by 1, and drawing a
/// floater lowers those of the floaters put in after it. Floaters dissolve
/// into plain pile members once nothing is known and none has a positive
/// `above`.
/// A floater's **slack** is how many of the last places of its range (the
/// pile once the floaters put in after it are left out) it certainly is
/// not in: 0 for a card put at a random spot, more once a card was taken out
/// of the draw pile (`Top::without`): the floater is then in a range of
/// places, `above` to the last one less its slack, each alike.
/// All zeros when nothing is known, so it costs existing content nothing
/// but its bytes. With Frozen Eye (`RelicRules::sees_draw_order`) the known
/// cards are the whole pile, past the 16 inline in `more`.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Top {
    known: [u16; TOP_KNOWN],
    n_known: u8,
    /// (card, above, copies, slack), oldest first; unused entries zero. A
    /// run of neighbours with equal `above` and slack is sorted by card and
    /// equal (card, above, slack) neighbours merged, so equal knowledge is
    /// equal state (such neighbours keep equal `above` until both are 0:
    /// their order can't matter).
    floaters: [FloaterEntry; TOP_FLOATERS],
    n_floaters: u8,
    /// Known cards past the 16 inline, the bottom card first (the 17th is
    /// last); `Some` only with all 16 inline in use and at least one more.
    more: Option<Box<Vec<u16>>>,
}

/// Only the entries in use (the rest are zero), as `Pile`'s.
impl std::hash::Hash for Top {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        self.known[..self.n_known as usize].hash(h);
        self.floaters[..self.n_floaters as usize].hash(h);
        if let Some(m) = &self.more {
            m.hash(h);
        }
    }
}

impl Top {
    pub fn is_empty(&self) -> bool {
        self.n_known == 0 && self.n_floaters == 0
    }

    /// The known cards, the next drawn first.
    pub fn known(&self) -> impl Iterator<Item = CardId> + '_ {
        let more = self.more.as_deref().map_or(&[][..], |m| &m[..]);
        self.known[..self.n_known as usize].iter().chain(more.iter().rev()).map(|&c| CardId(c))
    }

    pub fn n_known(&self) -> usize {
        self.n_known as usize + self.more.as_ref().map_or(0, |m| m.len())
    }

    /// The known cards become `seq` (the next drawn first), any number;
    /// floaters stay.
    pub fn set_known(&mut self, seq: &[CardId]) {
        let k = seq.len().min(TOP_KNOWN);
        self.known = [0; TOP_KNOWN];
        for (i, c) in seq[..k].iter().enumerate() {
            self.known[i] = c.0;
        }
        self.n_known = k as u8;
        self.more = (seq.len() > TOP_KNOWN).then(|| Box::new(seq[TOP_KNOWN..].iter().rev().map(|c| c.0).collect()));
        self.normalize();
    }

    /// `c` known with `d` cards above it (Frozen Eye's random spot).
    pub fn insert_known(&mut self, d: usize, c: CardId) {
        let mut seq: Vec<CardId> = self.known().collect();
        seq.insert(d, c);
        self.set_known(&seq);
    }

    /// One known copy of `c` (the one nearest the top) leaves; `false` if
    /// none is known.
    pub fn remove_known(&mut self, c: CardId) -> bool {
        let mut seq: Vec<CardId> = self.known().collect();
        let Some(i) = seq.iter().position(|&x| x == c) else { return false };
        seq.remove(i);
        self.set_known(&seq);
        true
    }

    /// The floaters as (card, above), one per copy.
    pub fn floaters(&self) -> impl Iterator<Item = (CardId, u8)> + '_ {
        self.floaters[..self.n_floaters as usize]
            .iter()
            .flat_map(|&(c, a, k, _)| std::iter::repeat_n((CardId(c), a), k as usize))
    }

    /// The floater entries, oldest first: (card, above, copies).
    pub fn floater_entries(&self) -> impl Iterator<Item = (CardId, u8, u8)> + '_ {
        self.floaters[..self.n_floaters as usize].iter().map(|&(c, a, k, _)| (CardId(c), a, k))
    }

    /// The floater entries, oldest first: (card, above, copies, slack).
    pub fn floater_entries_slack(&self) -> impl Iterator<Item = (CardId, u8, u8, u8)> + '_ {
        self.floaters[..self.n_floaters as usize].iter().map(|&(c, a, k, s)| (CardId(c), a, k, s))
    }

    /// The floaters as (card, above, slack), one per copy.
    pub fn floaters_slack(&self) -> impl Iterator<Item = (CardId, u8, u8)> + '_ {
        self.floaters[..self.n_floaters as usize]
            .iter()
            .flat_map(|&(c, a, k, s)| std::iter::repeat_n((CardId(c), a, s), k as usize))
    }

    /// Floater entries that can be drawn next (`above` 0): (entry, card,
    /// copies). Each copy is drawn next alike.
    pub fn floaters_on_top(&self) -> Vec<(u8, CardId, u8)> {
        self.floaters[..self.n_floaters as usize]
            .iter()
            .enumerate()
            .filter(|(_, f)| f.1 == 0)
            .map(|(i, &(c, _, k, _))| (i as u8, CardId(c), k))
            .collect()
    }

    /// Sorts each run of neighbours with equal `above` and slack by card,
    /// merges equal (card, above, slack) neighbours, zeroes the tail; with
    /// nothing known and no positive `above` or slack, the floaters dissolve
    /// (a floater with nothing above and no slack is in any place alike).
    fn normalize(&mut self) {
        if self.n_known == 0 && self.floaters[..self.n_floaters as usize].iter().all(|f| f.1 == 0 && f.3 == 0) {
            self.floaters = Default::default();
            self.n_floaters = 0;
        }
        let m = canon_floaters(&mut self.floaters[..self.n_floaters as usize]);
        self.floaters[m..].fill((0, 0, 0, 0));
        self.n_floaters = m as u8;
    }

    /// `c` goes on top, known; every floater is now below it too. Past
    /// capacity the bottom known card is forgotten (it stays in `draw`),
    /// unless `keep_all` (Frozen Eye: the whole pile stays known).
    pub fn push(&mut self, c: CardId, keep_all: bool) {
        if keep_all && self.n_known as usize == TOP_KNOWN {
            self.more.get_or_insert_with(Default::default).push(self.known[TOP_KNOWN - 1]);
        }
        let n = (self.n_known as usize).min(TOP_KNOWN - 1);
        self.known.copy_within(0..n, 1);
        self.known[0] = c.0;
        self.n_known = n as u8 + 1;
        for f in &mut self.floaters[..self.n_floaters as usize] {
            f.1 = f.1.saturating_add(1);
        }
        self.normalize();
    }

    /// `c` put into a non-empty draw pile at a random spot under its top
    /// card (`CardGroup.addToRandomSpot`): the newest floater, with 1 card
    /// certainly above it, whatever is known. Past capacity it is not
    /// tracked, so treated as a plain member of the pile. The caller adds
    /// `c` to `draw`, and skips this when the pile was empty (the game then
    /// just adds it).
    pub fn add_floater_under(&mut self, c: CardId) {
        let n = self.n_floaters as usize;
        if n == TOP_FLOATERS {
            // Full: it still joins the newest run of `above` 1 (whose order
            // with it can't matter) when that run holds its card.
            let r = (0..n).rev().take_while(|&i| self.floaters[i].1 == 1 && self.floaters[i].3 == 0).find(|&i| self.floaters[i].0 == c.0);
            if let Some(i) = r {
                self.floaters[i].2 = self.floaters[i].2.saturating_add(1);
            }
            return;
        }
        self.floaters[n] = (c.0, 1, 1, 0);
        self.n_floaters += 1;
        self.normalize();
    }

    /// Positive `above` drop by 1 for the floater entries from `from` on.
    fn lower_floaters(&mut self, from: usize) {
        for f in &mut self.floaters[from..self.n_floaters as usize] {
            f.1 = f.1.saturating_sub(1);
        }
        self.normalize();
    }

    /// Draws the known head; floaters' positive `above` drop by 1.
    pub fn pop_head(&mut self) -> CardId {
        let c = CardId(self.known[0]);
        let n = self.n_known as usize;
        self.known.copy_within(1..n, 0);
        match self.more.as_mut().and_then(|m| m.pop()) {
            Some(x) => self.known[n - 1] = x,
            None => {
                self.known[n - 1] = 0;
                self.n_known -= 1;
            }
        }
        if self.more.as_ref().is_some_and(|m| m.is_empty()) {
            self.more = None;
        }
        self.lower_floaters(0);
        c
    }

    /// Draws a copy of floater entry `i` (`above` 0) from the top; the
    /// positive `above` of the floaters put in after it drop by 1.
    pub fn take_floater(&mut self, i: u8) -> CardId {
        let (i, n) = (i as usize, self.n_floaters as usize);
        let (c, a, _, _) = self.floaters[i];
        assert_eq!(a, 0, "a floater on top");
        self.floaters[i].2 -= 1;
        let mut after = i + 1;
        if self.floaters[i].2 == 0 {
            self.floaters.copy_within(i + 1..n, i);
            self.floaters[n - 1] = (0, 0, 0, 0);
            self.n_floaters -= 1;
            after = i;
        }
        self.lower_floaters(after);
        CardId(c)
    }

    /// Draws a card that is neither known nor a floater, with nothing
    /// known: floaters' positive `above` drop by 1.
    pub fn draw_unknown(&mut self) {
        debug_assert_eq!(self.n_known, 0);
        self.lower_floaters(0);
    }

    /// Floater copies of `c`, any `above`.
    pub fn floater_count(&self, c: CardId) -> u8 {
        self.floaters[..self.n_floaters as usize].iter().filter(|f| f.0 == c.0).map(|f| f.2).sum()
    }

    /// The knowledge once the card `gone` left a draw pile of `pile` cards
    /// (this knowledge is of the pile before): the distinct knowledges it
    /// can leave with their probabilities (summing to 1; the caller weighs
    /// the classes of card `gone` can be of). `None` past `cap` outcomes.
    ///
    /// A floater is in a range of places of its own frame (the pile once the
    /// floaters put in after it are left out), `above` to its last place
    /// less its slack, each alike, whatever the others do. The card taken
    /// sat at some place `q` of that frame (cards above it): a known card at
    /// its index, a plain card at any place under the known cards, each
    /// alike (the plain cards are in random order), a floater's at a place
    /// of its own range. A floater above it (it went in at a place up to
    /// `q`) keeps its places up to `q`: the range is cut short (more slack);
    /// one below it (a place past `q`) moves up by 1 (`above` drops to at
    /// least `q`, the slack stays). The outcome names which, with the chance
    /// of the places on each side, and the next newer floater's frame holds
    /// the card one place lower or not accordingly.
    pub fn without(&self, gone: Gone, pile: usize, cap: usize) -> Option<Vec<(f64, Top)>> {
        let mut fl: Vec<(u16, u8, u8)> = Vec::new();
        for &(c, a, k, s) in &self.floaters[..self.n_floaters as usize] {
            fl.extend(std::iter::repeat_n((c, a, s), k as usize));
        }
        let (m, k) = (fl.len(), self.n_known());
        let mut known: Vec<CardId> = self.known().collect();
        // Where the card sat in the first frame that holds it (`qs`, with
        // chances), and the floaters that keep as they are (`kept`).
        let (kept, start, qs): (usize, usize, Vec<(f64, usize)>) = match gone {
            Gone::Known(x) => {
                known.remove(x);
                (0, 0, vec![(1.0, x)])
            }
            Gone::Plain => {
                let plain = pile.checked_sub(k + m).filter(|&p| p > 0)?;
                (0, 0, (k..k + plain).map(|q| (1.0 / plain as f64, q)).collect())
            }
            Gone::Floater(e) => {
                let mut upto = 0;
                let mut j = 0;
                for (i, f) in self.floaters[..self.n_floaters as usize].iter().enumerate() {
                    upto += f.2 as usize;
                    if i == e {
                        j = upto - 1;
                        break;
                    }
                }
                let (_, a, s) = fl.remove(j);
                // Its own frame: the pile less the floaters from it on.
                let b = (pile - (m - j)).checked_sub(s as usize)?;
                let a = a as usize;
                let qs = if j < fl.len() && b >= a { (a..=b).map(|d| (1.0 / (b - a + 1) as f64, d)).collect() } else { vec![(1.0, 0)] };
                (j, j, qs)
            }
        };
        // Floaters from `start` on (of the list with the card out), oldest
        // first: a frontier of (chance, place of the card, floaters done).
        let mut frontier: Vec<(f64, usize, Vec<(u16, u8, u8)>)> = qs.into_iter().map(|(w, q)| (w, q, Vec::new())).collect();
        for i in start..fl.len() {
            let (c, a, s) = fl[i];
            // The frame of this floater, its own place not counted: the
            // pile (card still in) less the floaters from it on.
            let after = fl.len() - i;
            let n = pile - after;
            let (a, s) = (a as usize, s as usize);
            let b = n.checked_sub(s)?;
            let mut next: Vec<(f64, usize, Vec<(u16, u8, u8)>)> = Vec::new();
            let mut push = |w: f64, q: usize, done: &Vec<(u16, u8, u8)>, e: (u16, u8, u8)| {
                let mut d = done.clone();
                d.push(e);
                match next.iter_mut().find(|x| x.1 == q && x.2 == d) {
                    Some(x) => x.0 += w,
                    None => next.push((w, q, d)),
                }
            };
            let total = (b + 1).checked_sub(a).filter(|&t| t > 0)?;
            for (w, q, done) in &frontier {
                let q = *q;
                // Above the card: a place up to `q`.
                if a <= q {
                    let hi = b.min(q);
                    let cnt = hi - a + 1;
                    let s2 = u8::try_from(n - 1 - hi).ok()?;
                    push(w * cnt as f64 / total as f64, q + 1, done, (c, a as u8, s2));
                }
                // Below it: a place past `q`, one up now.
                if b > q {
                    let lo = a.max(q + 1);
                    let cnt = b - lo + 1;
                    push(w * cnt as f64 / total as f64, q, done, (c, (lo - 1) as u8, s as u8));
                }
            }
            if next.len() > cap {
                return None;
            }
            frontier = next;
        }
        let mut out: Vec<(f64, Top)> = Vec::new();
        for (w, _, done) in frontier {
            let mut t = Top::default();
            t.set_known(&known);
            let mut f: Vec<FloaterEntry> = fl[..kept].iter().chain(done.iter()).map(|&(c, a, s)| (c, a, 1, s)).collect();
            let m = canon_floaters(&mut f);
            if m > TOP_FLOATERS {
                return None;
            }
            t.floaters[..m].copy_from_slice(&f[..m]);
            t.n_floaters = m as u8;
            t.normalize();
            match out.iter_mut().find(|x| x.1 == t) {
                Some(x) => x.0 += w,
                None => out.push((w, t)),
            }
        }
        Some(out)
    }

    /// Every card here through `f` (Inferno's Burn upgrade).
    pub fn map_cards(&mut self, f: impl Fn(CardId) -> CardId) {
        for c in &mut self.known[..self.n_known as usize] {
            *c = f(CardId(*c)).0;
        }
        for c in self.more.iter_mut().flat_map(|m| m.iter_mut()) {
            *c = f(CardId(*c)).0;
        }
        for x in &mut self.floaters[..self.n_floaters as usize] {
            x.0 = f(CardId(x.0)).0;
        }
        self.normalize();
    }

    /// The knowledge from its parts (the codec; floaters oldest first, one
    /// per copy); `None` if they can't be one or say nothing (no known card
    /// and no positive `above`).
    pub fn from_parts(known: &[CardId], floaters: &[(CardId, u8)]) -> Option<Top> {
        let f: Vec<(CardId, u8, u8)> = floaters.iter().map(|&(c, a)| (c, a, 0)).collect();
        Top::from_parts_slack(known, &f)
    }

    /// `from_parts` with each floater's slack too: (card, above, slack).
    pub fn from_parts_slack(known: &[CardId], floaters: &[(CardId, u8, u8)]) -> Option<Top> {
        if known.len() > PILE_RUN_CAP {
            return None;
        }
        let mut t = Top::default();
        t.set_known(known);
        if floaters.len() > u8::MAX as usize {
            return None;
        }
        let mut f: Vec<FloaterEntry> = floaters.iter().map(|&(c, a, s)| (c.0, a, 1, s)).collect();
        let m = canon_floaters(&mut f);
        if m > TOP_FLOATERS {
            return None;
        }
        t.floaters[..m].copy_from_slice(&f[..m]);
        t.n_floaters = m as u8;
        t.normalize();
        (!t.is_empty()).then_some(t)
    }

    /// Whether every card here is in `draw`, and every floater has a place
    /// to be in: its range (`above` to its frame's last place less its
    /// slack, the frame being the pile less the floaters from it on) is not
    /// empty.
    pub fn within(&self, draw: PileRef<'_>) -> bool {
        let mut p = Pile::default();
        for c in self.known() {
            p.add(c, 1);
        }
        let fl = &self.floaters[..self.n_floaters as usize];
        for &(c, _, k, _) in fl {
            p.add(CardId(c), k);
        }
        let mut left: usize = fl.iter().map(|f| f.2 as usize).sum();
        let mut ranges = true;
        for f in fl {
            for _ in 0..f.2 {
                // This floater's frame, itself not counted.
                ranges &= draw.len() >= left && f.1 as usize + f.3 as usize <= draw.len() - left;
                left -= 1;
            }
        }
        p.iter().all(|(c, k)| draw.count(c) >= k) && ranges
    }
}

#[derive(Clone, PartialEq, Eq, Hash)]
pub struct CombatState {
    pub player: Player,
    /// Fixed slots for the whole combat; dead monsters keep theirs.
    pub monsters: [Monster; MAX_MONSTERS],
    pub hand: Hand,
    /// Hand cards that cost 0 this turn (docs/specs/act1-singles.md);
    /// empty unless something marked one.
    pub free_in_hand: FreeMarks,
    /// Hand cards that cost 1 or more this turn, below their cost
    /// (Enlightenment); empty unless something marked one.
    pub turn_costs: TurnCosts,
    /// Hand cards waiting for a random cost roll (docs/specs/sparse-piles.md);
    /// empty for content without cost rolls.
    pub cost_rolls: CostRolls,
    /// Random work hooks owe, paid in order before anything else
    /// (docs/specs/blocked-relics.md step 5); empty unless a hook owed it.
    pub owed: Owed,
    /// Takes a power's hook owes behind everything else the turn start
    /// queued (Mayhem's `PlayTopCardAction`, the game's `addToBot`): paid
    /// one card at a time once the turn has settled, so after the draw,
    /// the post-draw hooks and their owed work. Only `OwedKind::Top`.
    pub owed_late: Owed,
    /// The draw, discard and exhaust piles, in one list
    /// (docs/specs/sparse-piles.md): `draw()`, `discard()`, `exhaust()`
    /// read them, `draw_mut()` and the others change them.
    pub piles: Piles,
    /// Cards taken off the draw pile to be played (`Effect::PlayTop`,
    /// docs/specs/act1-singles.md); empty except while one resolves.
    pub top_queue: TopQueue,
    /// What the player knows of `draw`'s order (Headbutt); empty for
    /// existing content.
    pub top: Top,
    pub turn: u16,
    pub stage: Stage,
    pub pending: Option<ChanceEvent>,
    /// Monster block waiting for the card or potion in play to finish (the
    /// game queues it after the card's own actions: Curl Up), or queued
    /// behind the monsters' block loss while the turn ends (The Guardian's
    /// Defensive Mode; `defers_queued_block`).
    pub deferred_block: [i16; MAX_MONSTERS],
    /// Blocks broken per monster whose `OpponentBlockBroken` hooks haven't
    /// fired yet (Hand Drill; docs/specs/blocked-relics.md step 7): counted
    /// only while the player holds such a hook; they fire once the card or
    /// potion in play has resolved, else where the stage machine next
    /// settles. A finished combat clears it.
    pub block_broken: [u8; MAX_MONSTERS],
    /// Cards added to piles during combat (Wound, Slimed, Dazed, Anger copies).
    pub created: u16,
    /// Cards that left combat: played Powers.
    pub removed: u16,
    pub character: Character,
    /// Player HP when the combat began; the score counts HP lost from it.
    pub start_hp: i16,
    /// Cards played this turn, the card in play included (FTL).
    pub cards_played_this_turn: u8,
    /// HP the player lost from the card in play, counted per loss; the
    /// player's `OwnerLostHp` hooks for them wait for the card to finish
    /// (the game computes a card's damage when it is played, so Rupture's
    /// Strength doesn't reach Hemokinesis' own hit).
    pub card_hp_losses: u8,
    /// Cards exhausted whose `CardExhausted` hooks haven't fired yet: they
    /// fire once the card in play is placed (or after turn end's or turn
    /// start's hooks). Nonzero only while a card is in play (it can pause at a
    /// pick or a chance event); a finished combat clears it.
    pub unfired_exhausts: u8,
    /// Draws a `CardExhausted` hook owed at turn end (ethereal cards with
    /// Dark Embrace), added to the next turn's draw.
    pub owed_draw: u8,
    /// Status cards drawn whose `CardDrawn` hooks haven't fired yet
    /// (draw-triggers spec): counted only while the player holds a power
    /// with such a hook; they fire one card at a time where the stage
    /// machine reaches the player's turn. A finished combat clears it.
    pub unfired_draws: u8,
    /// Curse cards drawn whose `CardDrawn` hooks haven't fired yet, as
    /// `unfired_draws` (Fire Breathing; counted only while the player holds
    /// a hook on Curse draws), fired after the Status ones.
    pub unfired_curse_draws: u8,
    /// Times the player lost HP this combat (cost-changes spec, Blood for
    /// Blood; the game's `damagedThisCombat`): a copy of a card with
    /// `cost_less_per_hp_loss` made in combat starts this much cheaper
    /// (`made_copy`); copies already in a pile carry their own drops.
    /// Counted only when the binding holds such a card, capped at the
    /// largest such base cost.
    pub times_lost_hp: u8,
    /// HP the player heals when this combat is won, capped at max HP (none
    /// in no-death mode): the character's starter relic's heal (Burning
    /// Blood's 6) at the start, raised by `WinHeal` (docs/specs/relics.md).
    pub win_heal: i16,
    /// The player escaped (Smoke Bomb; docs/specs/act1-singles.md): set
    /// only in a fight that ended as won by an escape.
    pub escaped: bool,
    /// A boss fight, kept for a held potion not usable in one (Smoke Bomb)
    /// once no slot holds the boss (Slime Boss's split): set as the
    /// potions are given when a slot holds a boss and the player holds
    /// such a potion (docs/specs/act1-singles.md).
    pub boss_fight: bool,
    /// Training simulation (learned play, switch 6): the player's HP may go
    /// below 0 without ending the combat, which ends on a win (with no
    /// end-of-combat heal, so the final HP is the HP left) or as a loss
    /// after `NO_DEATH_TURN_LIMIT` turns. Off in normal play.
    pub no_death: bool,
    /// The generated content (registry-lite) the reserved power and card
    /// slots hold in this combat; empty for official content only.
    pub binding: Binding,
    /// A `Discover`'s cards while its chance event or pick is open
    /// (docs/specs/discovery.md); empty otherwise.
    pub offer: Offer,
    /// HP the win gave the player: the `CombatWon` hooks (Meat on the Bone)
    /// and the `win_heal`, as actually healed (capped at max HP); 0 until a
    /// normal-play win. A report for `runner::CombatResult::healed`, not
    /// part of the state: states compare and hash alike whatever it holds.
    pub won_healed: Untracked<i16>,
    /// The HP the latest damage effect took from its targets, summed over
    /// targets and hits, each hit capped at its target's HP (the game's
    /// `lastDamageTaken`; `Quantity::HpDealt`: Reaper). Kept while a card,
    /// potion or move goes on; 0 at rest, so afterstates compare alike.
    pub dealt: i16,
    /// The player's End Turn is going on, up to the monsters' start-of-turn
    /// block loss (with `Stage::EndingTurn`, see `defers_queued_block`).
    /// Set only inside `end_turn`; false at rest, so states compare alike.
    pub turn_ending: bool,
    /// The game's `turnHasEnded` (`turn_has_ended`): the monsters' turn is
    /// going on, from after the player's hand is discarded to the round's
    /// end (not the next turn's rolls or start: the game resolves the
    /// player's start-of-turn work with the flag false). Set only inside
    /// the monsters' turn; false at rest, so states compare alike.
    pub monsters_acting: bool,
    /// Per slot, for a monster whose pattern reads `Allies` (Shield
    /// Gremlin): whether another monster lived when it last used its move
    /// (the game counts at the move, not at the roll). 0 for every other
    /// kind, so official states never set it.
    pub allies_at_move: u8,
    /// Per slot, Runic Dome's hidden intents (`RelicRules::hides_intents`):
    /// `HIDDEN_MOVE` while the next move is still to roll (it rolls when
    /// the monster acts; `moves` is then the history only, `moves[0]` the
    /// move used last), `HIDDEN_ALLIES` the allies bit when the game rolled
    /// it, `HIDDEN_CLASS` what a card revealed (`REVEALED_ATTACK` or
    /// `REVEALED_NO_ATTACK`), `HIDDEN_ROLLED` a rolled attack amount not
    /// seen yet (louse Bite). All zero without the relic.
    pub intent_hidden: [u8; MAX_MONSTERS],
    /// The Bottled relics' cards (`RelicRules::bottles`), one copy each, put
    /// in the opening hand with the innate cards; empty once turn 1 starts,
    /// so never at a decision.
    pub bottled: [Option<CardId>; 3],
    /// The game's ascension level (docs/specs/ascension.md), as every
    /// monster holds it: fixed for the combat.
    pub ascension: Ascension,
}

/// A value carried by a state that is not part of it: every two compare
/// equal and hash alike, and the codec doesn't write it.
#[derive(Clone, Copy, Debug, Default)]
pub struct Untracked<T>(pub T);

impl<T> PartialEq for Untracked<T> {
    fn eq(&self, _: &Self) -> bool {
        true
    }
}

impl<T> Eq for Untracked<T> {}

impl<T> std::hash::Hash for Untracked<T> {
    fn hash<H: std::hash::Hasher>(&self, _: &mut H) {}
}

/// The derived layout, with `binding` shown only when it holds generated
/// content (so debug text reads as it did before registry-lite).
impl std::fmt::Debug for CombatState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut d = f.debug_struct("CombatState");
        d.field("player", &self.player)
            .field("monsters", &self.monsters)
            .field("hand", &self.hand)
            .field("draw", &self.draw())
            .field("discard", &self.discard())
            .field("exhaust", &self.exhaust())
            .field("turn", &self.turn)
            .field("stage", &self.stage)
            .field("pending", &self.pending)
            .field("deferred_block", &self.deferred_block)
            .field("created", &self.created)
            .field("removed", &self.removed)
            .field("character", &self.character)
            .field("start_hp", &self.start_hp)
            .field("cards_played_this_turn", &self.cards_played_this_turn)
            .field("card_hp_losses", &self.card_hp_losses)
            .field("no_death", &self.no_death);
        if !self.cost_rolls.is_empty() {
            d.field("cost_rolls", &self.cost_rolls);
        }
        if !self.owed.is_empty() {
            d.field("owed", &self.owed);
        }
        if !self.owed_late.is_empty() {
            d.field("owed_late", &self.owed_late);
        }
        if self.unfired_exhausts != 0 || self.owed_draw != 0 {
            d.field("unfired_exhausts", &self.unfired_exhausts).field("owed_draw", &self.owed_draw);
        }
        if self.unfired_draws != 0 {
            d.field("unfired_draws", &self.unfired_draws);
        }
        if self.unfired_curse_draws != 0 {
            d.field("unfired_curse_draws", &self.unfired_curse_draws);
        }
        if self.block_broken != [0; MAX_MONSTERS] {
            d.field("block_broken", &self.block_broken);
        }
        if self.times_lost_hp != 0 {
            d.field("times_lost_hp", &self.times_lost_hp);
        }
        if self.dealt != 0 {
            d.field("dealt", &self.dealt);
        }
        if !self.top.is_empty() {
            d.field("top", &self.top);
        }
        if !self.free_in_hand.is_empty() {
            d.field("free_in_hand", &self.free_in_hand);
        }
        if !self.turn_costs.is_empty() {
            d.field("turn_costs", &self.turn_costs);
        }
        if self.escaped {
            d.field("escaped", &self.escaped);
        }
        if self.boss_fight {
            d.field("boss_fight", &self.boss_fight);
        }
        if !self.top_queue.is_empty() {
            d.field("top_queue", &self.top_queue);
        }
        if !self.binding.is_empty() {
            d.field("binding", &self.binding);
        }
        if !self.offer.is_empty() {
            d.field("offer", &self.offer);
        }
        if self.ascension.0 != 0 {
            d.field("ascension", &self.ascension.0);
        }
        d.finish()
    }
}

impl CombatState {
    /// The draw pile.
    #[inline]
    pub fn draw(&self) -> PileRef<'_> {
        self.piles.get(Run::Draw)
    }

    /// The discard pile.
    #[inline]
    pub fn discard(&self) -> PileRef<'_> {
        self.piles.get(Run::Discard)
    }

    /// The exhaust pile.
    #[inline]
    pub fn exhaust(&self) -> PileRef<'_> {
        self.piles.get(Run::Exhaust)
    }

    #[inline]
    pub fn draw_mut(&mut self) -> PileMut<'_> {
        self.piles.get_mut(Run::Draw)
    }

    #[inline]
    pub fn discard_mut(&mut self) -> PileMut<'_> {
        self.piles.get_mut(Run::Discard)
    }

    #[inline]
    pub fn exhaust_mut(&mut self) -> PileMut<'_> {
        self.piles.get_mut(Run::Exhaust)
    }

    /// The draw pile becomes `p`'s contents.
    pub fn set_draw(&mut self, p: impl AsPile) {
        self.piles.set(Run::Draw, p);
    }

    /// The discard pile becomes `p`'s contents.
    pub fn set_discard(&mut self, p: impl AsPile) {
        self.piles.set(Run::Discard, p);
    }

    /// The exhaust pile becomes `p`'s contents.
    pub fn set_exhaust(&mut self, p: impl AsPile) {
        self.piles.set(Run::Exhaust, p);
    }

    /// The four piles, read only: hand, draw, discard, exhaust.
    #[inline]
    pub fn all_piles(&self) -> [PileRef<'_>; 4] {
        [self.hand.view(), self.draw(), self.discard(), self.exhaust()]
    }

    /// An Ironclad combat; see `new_as`.
    pub fn new(deck: &[CardId], hp: i16, max_hp: i16, encounter: Encounter, rng: &mut Rng) -> CombatState {
        CombatState::new_as(Character::Ironclad, deck, hp, max_hp, encounter, rng)
    }

    /// Sets up the encounter and plays it forward to the first decision,
    /// sampling monster HP, first moves and the opening hand from `rng`.
    pub fn new_as(character: Character, deck: &[CardId], hp: i16, max_hp: i16, encounter: Encounter, rng: &mut Rng) -> CombatState {
        CombatState::new_bound(character, deck, &Binding::default(), hp, max_hp, encounter, rng)
    }

    /// `new_as` with generated content bound to the reserved slots
    /// (`registry::bind`).
    pub fn new_bound(
        character: Character,
        deck: &[CardId],
        binding: &Binding,
        hp: i16,
        max_hp: i16,
        encounter: Encounter,
        rng: &mut Rng,
    ) -> CombatState {
        CombatState::new_bound_with(character, deck, binding, hp, max_hp, encounter, &[], rng)
    }

    /// `new_bound` holding these relics (docs/specs/relics.md): the ones
    /// that act in the encounter's group (`RelicSpec::acts_in`) give their
    /// powers and heal, as `new_with` says.
    #[allow(clippy::too_many_arguments)]
    pub fn new_bound_with(
        character: Character,
        deck: &[CardId],
        binding: &Binding,
        hp: i16,
        max_hp: i16,
        encounter: Encounter,
        relics: &[(String, RelicSpec)],
        rng: &mut Rng,
    ) -> CombatState {
        CombatState::new_bound_turn1(character, deck, binding, hp, max_hp, encounter, relics, false, Ascension(0), None, rng)
    }

    /// `new_bound_with`, turn 1 played like every later turn when
    /// `turn1_pre_draw`, at an ascension level, a burning elite with
    /// `elite_buff` (`new_with_turn1`).
    #[allow(clippy::too_many_arguments)]
    pub fn new_bound_turn1(
        character: Character,
        deck: &[CardId],
        binding: &Binding,
        hp: i16,
        max_hp: i16,
        encounter: Encounter,
        relics: &[(String, RelicSpec)],
        turn1_pre_draw: bool,
        ascension: Ascension,
        elite_buff: Option<EliteBuff>,
        rng: &mut Rng,
    ) -> CombatState {
        let kinds = encounter.roll_monsters(rng);
        CombatState::new_with_turn1(character, deck, binding, hp, max_hp, &kinds, encounter.group(), relics, turn1_pre_draw, ascension, elite_buff, rng)
    }

    /// `new_bound` against these monsters by slot (official kinds, or pack
    /// monsters from `registry::monster_kinds`) instead of an encounter's
    /// roll: each one's HP rolled and its setup run, in slot order.
    pub fn new_vs(
        character: Character,
        deck: &[CardId],
        binding: &Binding,
        hp: i16,
        max_hp: i16,
        kinds: &[MonsterKind],
        rng: &mut Rng,
    ) -> CombatState {
        CombatState::new_with(character, deck, binding, hp, max_hp, kinds, EncounterGroup::Hallway, &[], rng)
    }

    /// `new_vs` in a fight of kind `group`, holding these relics
    /// (docs/specs/relics.md). Each relic that acts in `group` adds its
    /// `win_heal` to the fight's heal and joins `player.relics` in order at
    /// its spec's `counter` (docs/specs/relic-entity.md); its hooks give
    /// its powers at their triggers (its pack powers bound after the deck's
    /// and the monsters'; callers check `registry::bind_relics` first).
    /// With no relic acting, this is `new_vs`'s fight.
    #[allow(clippy::too_many_arguments)]
    pub fn new_with(
        character: Character,
        deck: &[CardId],
        binding: &Binding,
        hp: i16,
        max_hp: i16,
        kinds: &[MonsterKind],
        group: EncounterGroup,
        relics: &[(String, RelicSpec)],
        rng: &mut Rng,
    ) -> CombatState {
        CombatState::new_with_turn1(character, deck, binding, hp, max_hp, kinds, group, relics, false, Ascension(0), None, rng)
    }

    /// `new_with`; turn 1 runs in the game's order (the opening draw, the
    /// player's post-draw hooks, then their turn-start hooks), or with
    /// `turn1_pre_draw` like every later turn (turn-start hooks, the draw,
    /// post-draw hooks; docs/specs/turn-start-draw.md). Turn 1 is played
    /// here, so the state holds no trace of the choice. `ascension` is the
    /// game's level (docs/specs/ascension.md): the monsters' definitions at
    /// it, and the player's potion slots (`potion_slots`); 0 plays as the
    /// engine always has. `elite_buff` makes it Act 1's burning elite: each
    /// monster gets the buff after its setup, before the player's
    /// start-of-combat hooks (`EliteBuff`).
    #[allow(clippy::too_many_arguments)]
    pub fn new_with_turn1(
        character: Character,
        deck: &[CardId],
        binding: &Binding,
        hp: i16,
        max_hp: i16,
        kinds: &[MonsterKind],
        group: EncounterGroup,
        relics: &[(String, RelicSpec)],
        turn1_pre_draw: bool,
        ascension: Ascension,
        elite_buff: Option<EliteBuff>,
        rng: &mut Rng,
    ) -> CombatState {
        assert!(!kinds.is_empty(), "a combat needs a monster");
        assert!(ascension.0 <= crate::monsters::MAX_ASCENSION, "ascension {} above {}", ascension.0, crate::monsters::MAX_ASCENSION);
        deck_fits(deck).unwrap_or_else(|e| panic!("{e}"));
        assert!(
            kinds.iter().map(|&k| crate::monsters::slots_needed(k)).sum::<usize>() <= MAX_MONSTERS,
            "more than {MAX_MONSTERS} monster slots (splits included): {kinds:?}"
        );
        // The monsters' pack powers after the deck's (callers with pack
        // monsters check this first: `registry::bind_monsters`).
        let binding = &crate::registry::bind_monsters(binding, kinds).unwrap_or_else(|e| panic!("{e}"));
        let acting: Vec<&(String, RelicSpec)> = relics.iter().filter(|(_, r)| r.acts_in(group)).collect();
        let binding = &crate::registry::bind_relics(binding, acting.iter().copied(), character).unwrap_or_else(|e| panic!("{e}"));
        // A burning elite's pack power (Regenerate), bound only when it is
        // the buff, so every other fight keeps its binding.
        let binding = &match elite_buff {
            Some(b) => b.bind(binding).unwrap_or_else(|e| panic!("{e}")),
            None => *binding,
        };
        let mut relics = Relics::default();
        let mut win_heal = character.win_heal();
        let mut bottled = [None; 3];
        for (name, r) in &acting {
            // A Bottled relic's card: its counter is the card's place in the deck plus 1.
            if let (Some(ty), k @ 1..) = (r.rules.bottles, r.counter) {
                let c = *deck.get(k as usize - 1).unwrap_or_else(|| panic!("relic {name:?}: counter {k} names no card of the {}-card deck", deck.len()));
                assert!(binding.def(c).ty == ty, "relic {name:?}: card {:?} isn't a {ty:?}", binding.def(c).name);
                let slot = bottled.iter().position(Option::is_none).unwrap_or_else(|| panic!("more than 3 bottled cards"));
                bottled[slot] = Some(c);
            }
            relic_id(name)
                .and_then(|id| {
                    crate::relics::register_hooks(id, r.hooks)
                        .and_then(|()| crate::relics::register_potion_potency(id, r.potion_potency))
                        .and_then(|()| crate::relics::register_potion_slots(id, r.potion_slots))
                        .and_then(|()| crate::relics::register_draw_per_turn(id, r.draw_per_turn))
                        .and_then(|()| crate::relics::register_rules(id, r.rules))
                        .and_then(|()| crate::relics::register_heal_scale(id, r.heal_scale))
                        .and_then(|()| relics.push(id, r.counter))
                })
                .unwrap_or_else(|e| panic!("{e}"));
            win_heal += r.win_heal;
        }
        let mut monsters = [Monster::default(); MAX_MONSTERS];
        for (slot, &kind) in kinds.iter().enumerate() {
            let d = kind.def_at(ascension);
            let hp = d.hp_min + rng.below((d.hp_max - d.hp_min + 1) as u32) as i16;
            monsters[slot] = Monster::new_at(kind, hp, binding, ascension);
            monsters[slot].roll(rng);
            if let Some(b) = elite_buff {
                b.apply(&mut monsters[slot], 1, binding);
            }
        }
        let mut s = CombatState {
            player: Player { hp, max_hp, block: 0, energy: 0, powers: Powers::default(), relics, potions: Potions::default() },
            monsters,
            hand: Hand::default(),
            free_in_hand: FreeMarks::default(),
            turn_costs: TurnCosts::default(),
            cost_rolls: CostRolls::default(),
            owed: Owed::default(),
            owed_late: Owed::default(),
            piles: Piles::default(),
            top_queue: TopQueue::default(),
            top: Top::default(),
            turn: 0,
            stage: Stage::MonsterRolls { next: 0 },
            pending: None,
            deferred_block: [0; MAX_MONSTERS],
            block_broken: [0; MAX_MONSTERS],
            created: 0,
            removed: 0,
            character,
            start_hp: hp,
            cards_played_this_turn: 0,
            card_hp_losses: 0,
            unfired_exhausts: 0,
            owed_draw: 0,
            unfired_draws: 0,
            unfired_curse_draws: 0,
            times_lost_hp: 0,
            win_heal,
            escaped: false,
            boss_fight: false,
            no_death: false,
            binding: *binding,
            offer: Offer::default(),
            won_healed: Untracked(0),
            dealt: 0,
            turn_ending: false,
            monsters_acting: false,
            allies_at_move: 0,
            intent_hidden: [0; MAX_MONSTERS],
            bottled,
            ascension,
        };
        // Runic Dome: a rolled attack amount (louse Bite) isn't shown; the
        // roll is made as without it, so seeded fights stay aligned.
        if s.hides_intents() {
            for slot in 0..MAX_MONSTERS {
                if s.monsters[slot].kind != MonsterKind::None && s.monsters[slot].def().rolled_attack.is_some() {
                    s.monsters[slot].rolled_damage = 0;
                    s.intent_hidden[slot] |= HIDDEN_ROLLED;
                }
            }
        }
        s.piles.set(Run::Draw, Pile::from_cards(deck));
        s.run_opts(turn1_pre_draw);
        while s.pending.is_some() {
            s.resolve_chance_opts(rng, turn1_pre_draw);
        }
        s
    }

    /// Gives the player these potions (docs/specs/potions.md), added to the
    /// ones held, kept sorted by name; the pack powers they apply are bound
    /// after the fight's (a bound power keeps its slot). More than
    /// `POTION_CAP` held, or more pack powers than the slots hold, is an
    /// error naming the potion, and leaves the state as it was. A fight is
    /// built without potions and given them here before the first action.
    pub fn give_potions(&mut self, potions: &[(String, PotionSpec)]) -> Result<(), String> {
        let binding = crate::registry::bind_potions(&self.binding, potions)?;
        let mut held = self.player.potions;
        for (name, _) in potions {
            held.insert(potion_id(name)?)?;
        }
        (self.binding, self.player.potions) = (binding, held);
        // The mark only where a potion needs it, so every other state is
        // as before.
        let boss_bound = |id: PotionId| id.spec().is_some_and(|p| !p.usable_in(EncounterGroup::Boss));
        // Or one a held potion can make (Entropic Brew making Smoke Bomb).
        let makes_boss_bound = |id: PotionId| {
            id.spec().is_some_and(|p| {
                p.effects().any(|e| matches!(*e, Effect::ObtainRandomPotions { pool } if crate::potions::potion_pool(pool).potions().any(boss_bound)))
            })
        };
        self.boss_fight |= self.is_boss_fight() && self.player.potions.iter().any(|id| boss_bound(id) || makes_boss_bound(id));
        Ok(())
    }

    /// Holds content from a pack (a registry binding or a pack monster),
    /// or an open offer or a random potion pending (a pool's index names a
    /// process-local pool), which has no codec encoding.
    pub fn has_generated(&self) -> bool {
        !self.binding.is_empty()
            || self.monsters.iter().any(|m| !m.kind.is_official())
            || !self.offer.is_empty()
            || matches!(self.pending, Some(ChanceEvent::RandomPotion { .. } | ChanceEvent::MakeRandom { .. }))
            || self.owed.iter().any(|e| matches!(e.kind, OwedKind::Make { .. }))
    }

    /// Waiting for the player to act (not over, no chance event pending):
    /// their turn, or a card paused at a pick.
    pub fn awaiting_action(&self) -> bool {
        self.pending.is_none() && (self.stage == Stage::PlayerTurn || self.pick().is_some())
    }

    /// The pick the card or potion in play is waiting on, if any.
    pub fn pick(&self) -> Option<Pick> {
        match self.stage {
            Stage::PlayingCard { more, .. } => more.pick,
            Stage::UsingPotion { pick, .. } => pick,
            Stage::RelicPick { pick, .. } | Stage::RelicOffer { pick, .. } => pick,
            _ => None,
        }
    }

    /// Sets the pick of the card or potion in play.
    fn set_pick(&mut self, p: Option<Pick>) {
        match &mut self.stage {
            Stage::PlayingCard { more, .. } => more.pick = p,
            Stage::UsingPotion { pick, .. } => *pick = p,
            Stage::RelicPick { pick, .. } | Stage::RelicOffer { pick, .. } => *pick = p,
            _ => unreachable!("a pick needs a card or potion in play"),
        }
    }

    /// A card or a potion is resolving: a monster's block from a hook waits
    /// for it to finish (Curl Up).
    fn in_play(&self) -> bool {
        matches!(self.stage, Stage::PlayingCard { .. } | Stage::UsingPotion { .. })
    }

    /// Whether monster block the game queues behind what is queued now (a
    /// `GainBlockAction` queued by a queued action: The Guardian's Defensive
    /// Mode) waits in `deferred_block`: for the card or potion in play, and
    /// while the turn ends for the monsters' start-of-turn block loss (the
    /// game's turn end queues `MonsterStartTurnAction` ahead of it), so it
    /// lasts through the monsters' turn.
    fn defers_queued_block(&self) -> bool {
        self.in_play() || self.turn_ending || matches!(self.stage, Stage::EndingTurn { .. })
    }

    /// Whether the held potion at `slot` is the first of its copies (two
    /// copies give one action).
    fn first_copy(&self, slot: usize) -> bool {
        let p = &self.player.potions;
        slot < p.len() && (slot == 0 || p.id(slot - 1) != p.id(slot))
    }

    /// What a potion with potency above 0 runs at: the highest
    /// `potion_potency` of the held relics (Sacred Bark's 2; two Barks
    /// double once, as in the game), else 1 (docs/specs/potions.md).
    pub fn potion_multiplier(&self) -> i16 {
        self.player.relics.iter().map(|(id, _)| id.potion_potency()).max().unwrap_or(1).max(1)
    }

    /// Cards the held relics add to every turn's draw (`draw_per_turn`:
    /// Snecko Eye's 2).
    /// The cards turn 1 starts with in hand before its draw: every innate
    /// copy in the draw pile and one copy per Bottled relic's card.
    pub fn opening_cards(&self) -> Vec<(CardId, u8)> {
        let mut v: Vec<(CardId, u8)> = self.draw().iter().filter(|(c, _)| self.binding.def(*c).innate).collect();
        for c in self.bottled.iter().flatten() {
            match v.iter_mut().find(|x| x.0 == *c) {
                Some(x) if x.1 < self.draw().count(*c) && !self.binding.def(*c).innate => x.1 += 1,
                Some(_) => {}
                None if self.draw().count(*c) > 0 => v.push((*c, 1)),
                None => {}
            }
        }
        v
    }

    /// Whether enemy intents are hidden (a relic's `hides_intents`: Runic Dome).
    pub fn hides_intents(&self) -> bool {
        self.player.relics.iter().any(|(id, _)| id.rules().hides_intents)
    }

    /// Whether monster `slot`'s next move is still to roll (Runic Dome).
    pub fn move_hidden(&self, slot: usize) -> bool {
        self.intent_hidden[slot] & HIDDEN_MOVE != 0
    }

    /// The move monster `slot` shows: none while it is hidden.
    pub fn shown_intent(&self, slot: usize) -> Option<&'static MoveDef> {
        if self.move_hidden(slot) {
            None
        } else {
            self.monsters[slot].intent_def()
        }
    }

    /// Monster `slot`'s next move: its intent with probability 1, or while
    /// hidden the roll still to come, given what a card revealed of it.
    pub fn intent_distribution(&self, slot: usize) -> Vec<(MoveId, f64)> {
        if !self.move_hidden(slot) {
            return vec![(self.monsters[slot].intent(), 1.0)];
        }
        self.roll_distribution(slot)
    }

    /// Monster `slot`'s roll (`move_distribution`), given what a card
    /// revealed of a hidden one (Runic Dome).
    pub fn roll_distribution(&self, slot: usize) -> Vec<(MoveId, f64)> {
        let dist = self.move_distribution(slot);
        let want = match self.intent_hidden[slot] & HIDDEN_CLASS {
            REVEALED_ATTACK => true,
            REVEALED_NO_ATTACK => false,
            _ => return dist,
        };
        let moves = self.monsters[slot].def().moves;
        let kept: Vec<(MoveId, f64)> = dist.into_iter().filter(|&(m, _)| moves.get(m as usize).is_some_and(|d| is_attack(d)) == want).collect();
        let total: f64 = kept.iter().map(|x| x.1).sum();
        kept.into_iter().map(|(m, p)| (m, p / total)).collect()
    }

    /// Whether the player sees the draw pile's order (a relic's
    /// `sees_draw_order`: Frozen Eye).
    pub fn sees_order(&self) -> bool {
        self.player.relics.iter().any(|(id, _)| id.rules().sees_draw_order)
    }

    pub fn relic_draw(&self) -> u8 {
        self.player.relics.iter().map(|(id, _)| id.draw_per_turn().max(0) as u8).sum()
    }

    /// What the held relics add to an X card's X (`x_bonus`: Chemical X's 2).
    pub fn relic_x_bonus(&self) -> i16 {
        self.player.relics.iter().map(|(id, _)| id.rules().x_bonus).sum()
    }

    /// Whether a card may still be played this turn: fewer than the held
    /// relics' smallest `plays_per_turn` (Velvet Choker's 6) and the hand's
    /// cards' (Normality's 3) were played.
    pub fn under_play_limit(&self) -> bool {
        let played = self.cards_played_this_turn;
        played == 0
            || (self.player.relics.iter().map(|(id, _)| id.rules().plays_per_turn).filter(|&n| n > 0).all(|n| (played as i16) < n)
                && self.hand.iter().all(|(c, _)| {
                    let n = self.binding.def(c).plays_per_turn;
                    n == 0 || played < n
                }))
    }

    /// The player's block after their turn start's loss: all of it, or at
    /// most the fewest `block_loss` among the held powers (Barricade 0,
    /// Calipers' helper 15; the game's `loseBlock`).
    pub fn block_after_turn_start(&self) -> i16 {
        let keep = self.binding.rule_powers().filter(|&g| self.player.powers.get(g) != 0).filter_map(|g| self.binding.block_loss(g)).min();
        match keep {
            None => 0,
            Some(n) => (self.player.block - n).max(0),
        }
    }

    /// The player's potion slots: 3, one fewer from ascension 11 (the
    /// game's `AbstractPlayer`), plus each held relic's `potion_slots`
    /// (Potion Belt's 2; docs/specs/act1-singles.md section 5). A fight may
    /// be given more potions than this.
    pub fn potion_slots(&self) -> usize {
        let base = crate::potions::BASE_POTION_SLOTS - (self.ascension.0 >= crate::potions::FEWER_SLOTS_FROM) as usize;
        base + self.player.relics.iter().map(|(id, _)| id.potion_slots().max(0) as usize).sum::<usize>()
    }

    /// What potion `id` multiplies its amounts by now: the relics'
    /// multiplier when its potency is above 0, else 1 (Elixir).
    pub fn potion_scale(&self, id: PotionId) -> i16 {
        if CombatState::potion_spec(id).potency > 0 { self.potion_multiplier() } else { 1 }
    }

    /// Whether the held potion at `slot` can be drunk now: the first copy
    /// of its name, without a trigger (Fairy in a Bottle's `canUse()` is
    /// false), and usable in this fight's kind (Smoke Bomb's `fights`).
    fn potion_drinkable(&self, slot: usize) -> bool {
        if !self.first_copy(slot) {
            return false;
        }
        let p = CombatState::potion_spec(self.player.potions.id(slot));
        p.trigger.is_none() && (p.usable_in(EncounterGroup::Boss) || !self.is_boss_fight())
    }

    /// A boss fight: a slot, alive or dead, holds a boss kind
    /// (`MonsterKind::is_boss`), or the `boss_fight` mark is set
    /// (docs/specs/act1-singles.md).
    pub fn is_boss_fight(&self) -> bool {
        self.boss_fight || self.monsters.iter().any(|m| m.kind.is_boss())
    }

    fn potion_spec(id: PotionId) -> &'static crate::potions::PotionSpec {
        id.spec().expect("a held potion is loaded")
    }

    /// The pile a pick takes from, if it can take anything now (a full hand
    /// takes nothing back from the discard pile), only cards of its types.
    fn pick_source(&self, pick: &Pick) -> Option<Pile> {
        let mut p = match pick.kind {
            PickKind::DiscardFromHand | PickKind::ExhaustFromHand | PickKind::HandToTop | PickKind::CopyInHand => self.hand.view().to_pile(),
            PickKind::ReturnFromDiscard | PickKind::ReturnFromExhaust if self.hand.len() >= HAND_LIMIT => return None,
            PickKind::ReturnFromDiscard => self.discard().to_pile(),
            PickKind::DrawToHand => self.draw().to_pile(),
            PickKind::DiscardToTop => self.discard().to_pile(),
            PickKind::Offered => Pile::from_cards(&self.offer.cards().collect::<Vec<_>>()),
            // Only cards a general upgrade can raise (not statuses, not at
            // their max level).
            PickKind::UpgradeFromHand => {
                let mut p = self.hand.view().to_pile();
                for (c, n) in self.hand.iter() {
                    if !crate::registry::general_upgrade(self.binding.def(c)) {
                        p.remove(c, n);
                    }
                }
                p
            }
            // Never a card that itself returns from the exhaust pile (the
            // game's "not Exhume", by mechanic).
            PickKind::ReturnFromExhaust => {
                let mut p = self.exhaust().to_pile();
                for (c, n) in self.exhaust().iter() {
                    let returns = self.binding.def(c).all_effects().any(|e| matches!(e, Effect::Pick { kind: PickKind::ReturnFromExhaust, .. }));
                    if returns {
                        p.remove(c, n);
                    }
                }
                p
            }
        };
        if pick.of != Types::ALL {
            for (c, n) in p.iter().collect::<Vec<_>>() {
                if !pick.of.has(self.binding.def(c).ty) {
                    p.remove(c, n);
                }
            }
        }
        (p.len() > 0).then_some(p)
    }

    /// Every exhaust lands here, from any pile or from play (the hook
    /// point for exhaust triggers).
    pub(crate) fn exhaust_card(&mut self, c: CardId, n: u8) {
        self.exhaust_mut().add(c, n);
        self.unfired_exhausts = self.unfired_exhausts.saturating_add(n);
        // The card's own `exhausted` effects, once per copy (GainEnergy,
        // Block and added cards only: none pauses or ends the combat).
        for _ in 0..n {
            for e in self.binding.def(c).exhausted {
                match *e {
                    // A copy of the exhausted card (Necronomicurse).
                    Effect::AddCopy { n, pile } => self.do_effect(Who::Player, &Effect::AddCard { card: c, n, pile }, None),
                    _ => self.do_effect(Who::Player, e, None),
                }
            }
        }
    }

    /// The player's `CardExhausted` hooks for the cards exhausted since the
    /// last firing, once with amounts multiplied by their count; at turn
    /// end (`turn_end`) a `Draw` is owed to the next turn's draw. Returns
    /// whether the combat ended.
    fn fire_exhausts(&mut self, turn_end: bool) -> bool {
        let k = std::mem::take(&mut self.unfired_exhausts);
        if k == 0 {
            return false;
        }
        self.run_hooks_scaled(Who::Player, |h: &Hook| h.trigger == Trigger::CardExhausted, HookCtx::default(), k as i16, turn_end, |_| true)
    }

    /// The player's `OpponentBlockBroken` hooks for the blocks broken since
    /// the last firing: monster by monster in slot order, once per break,
    /// that monster as the hooks' `Target::Opponent`; none for a monster
    /// dead by now (the game's `ApplyPowerAction` checks). Returns whether
    /// the combat ended.
    fn fire_block_broken(&mut self) -> bool {
        for slot in 0..MAX_MONSTERS {
            for _ in 0..std::mem::take(&mut self.block_broken[slot]) {
                if !self.monsters[slot].alive() {
                    break;
                }
                let ctx = HookCtx { card: None, target: Some(slot as u8), drawn: None };
                if self.run_hooks_with(Who::Player, |h: &Hook| h.trigger == Trigger::OpponentBlockBroken, ctx) {
                    return true;
                }
            }
        }
        false
    }

    /// Whether the player holds a hook on `trigger`: a relic's, or a held
    /// power's.
    fn player_has_trigger(&self, trigger: Trigger) -> bool {
        self.player.relics.iter().any(|(id, _)| id.hooks().iter().any(|h| h.trigger == trigger))
            || self.binding.powers_in_play().iter().any(|&p| self.player.powers.get(p) > 0 && self.binding.hooks(p).iter().any(|h| h.trigger == trigger))
    }

    /// The exhaust-save roll's outcome (`ChanceEvent::ExhaustSave`): the
    /// card in play's mark, or the queue's front card placed.
    pub(crate) fn exhaust_saved(&mut self, queued: bool, saved: bool) {
        if queued {
            let q = self.top_queue.pop_front().expect("a queued card");
            if saved {
                self.discard_mut().add(q.card, 1);
            } else {
                self.exhaust_card(q.card, 1);
                self.fire_exhausts(false);
            }
        } else if let Stage::PlayingCard { card, target, next, hit, x, more } = self.stage {
            self.stage = Stage::PlayingCard { card, target, next, hit, x, more: InPlay { save: Some(saved), ..more } };
        }
    }

    /// The player's `CardDrawn` hooks for one drawn card of type `ty`
    /// (Status or Curse). Returns whether the combat ended.
    fn fire_draw(&mut self, ty: CardType) -> bool {
        let ctx = HookCtx { drawn: Some(ty), ..HookCtx::default() };
        self.run_hooks_scaled(Who::Player, |h: &Hook| h.trigger == Trigger::CardDrawn && h.condition != Condition::Always, ctx, 1, false, |_| true)
    }

    /// Whether the player holds a power or relic with a `CardDrawn` hook on
    /// drawn cards of type `ty` (only the official powers whose rows have
    /// one are scanned: none today, so official content never pays for the
    /// check).
    pub(crate) fn holds_draw_hook(&self, ty: CardType) -> bool {
        let on = |h: &Hook| h.trigger == Trigger::CardDrawn && h.condition == Condition::CardType(ty);
        let b = self.binding;
        b.draw_hook_powers().any(|p| self.player.powers.get(p) > 0 && b.hooks(p).iter().any(on))
            || self.player.relics.iter().any(|(id, _)| id.hooks().iter().any(on))
    }

    /// Whether the player holds a power or relic that rolls each drawn
    /// card's cost (a `CardDrawn` hook with condition `Always`: Confused).
    fn rolls_drawn_costs(&self) -> bool {
        let rolls = |h: &Hook| h.trigger == Trigger::CardDrawn && h.condition == Condition::Always;
        let b = self.binding;
        b.draw_hook_powers().any(|p| self.player.powers.get(p) > 0 && b.hooks(p).iter().any(rolls))
            || self.player.relics.iter().any(|(id, _)| id.hooks().iter().any(rolls))
    }

    /// Confused: each card of a draw whose cost is 0 or more waits for a
    /// cost roll.
    fn queue_drawn_rolls(&mut self, drawn: PileRef<'_>) {
        if !self.rolls_drawn_costs() {
            return;
        }
        for (c, n) in drawn.iter() {
            let d = self.binding.def(c);
            if !d.x_cost() && !d.unplayable() {
                for _ in 0..n {
                    self.cost_rolls.push(c, false);
                }
            }
        }
    }

    /// Snecko Oil: every card in hand whose cost is 0 or more waits for a
    /// cost roll, a copy marked to cost 0 this turn as marked.
    fn queue_hand_rolls(&mut self) {
        let cards: Vec<(CardId, u8)> = self.hand.iter().collect();
        for (c, n) in cards {
            let d = self.binding.def(c);
            if d.x_cost() || d.unplayable() {
                continue;
            }
            let m = self.free_in_hand.count(c).min(n);
            for k in 0..n {
                self.cost_rolls.push(c, k < m);
            }
        }
    }

    /// The next waiting copy rolls cost `v` (0-3): a roll equal to its cost
    /// changes nothing; otherwise it becomes the copy at cost `v` for the
    /// combat and, costing `v` this turn too, loses a mark (the game sets
    /// `card.costForTurn = card.cost = newCost`).
    pub(crate) fn roll_cost(&mut self, v: i8) {
        let (c, marked) = self.cost_rolls.pop_front().expect("a cost roll waiting");
        if self.binding.def(c).cost() == v {
            return;
        }
        self.set_combat_cost(c, v, marked);
    }

    /// One copy of `c` in hand (a marked one when `marked`, losing its
    /// mark) becomes the copy at cost `v` for the combat.
    pub(crate) fn set_combat_cost(&mut self, c: CardId, v: i8, marked: bool) {
        let to = self.at_combat_cost(c, v);
        if marked {
            self.free_in_hand.remove(c);
            self.hand.remove(c, 1);
        } else {
            // The copy may be one that costs less this turn: it loses that
            // mark with the roll (a change in cost sets `costForTurn`).
            self.hand_remove(c, 1);
        }
        self.hand.add(to, 1);
    }

    /// Every copy of `c` in hand becomes the copy at cost `v` for the
    /// combat and keeps its marks (Enlightenment+: the game sets `cost` and
    /// leaves `costForTurn`); a mark that no longer lowers the cost goes.
    fn set_combat_cost_keep_marks(&mut self, c: CardId, v: i8) {
        let to = self.at_combat_cost(c, v);
        let n = self.hand.count(c);
        let free = self.free_in_hand.count(c);
        let costs = self.turn_costs.take_all(c);
        for _ in 0..free {
            self.free_in_hand.remove(c);
        }
        self.hand.remove(c, n);
        self.hand.add(to, n);
        for _ in 0..free {
            self.mark_free_in_hand(to);
        }
        for k in costs {
            self.mark_turn_cost(to, k as i8);
        }
    }

    /// `CostAtMost`: every hand copy (not X-cost or unplayable) that costs
    /// more than `cost` this turn costs `cost` this turn, then with
    /// `combat` every card whose own cost is above `cost` costs `cost` for
    /// the combat, keeping its mark.
    fn cost_at_most(&mut self, cost: i8, combat: bool) {
        for (c, n) in self.hand.iter().collect::<Vec<_>>() {
            let d = self.binding.def(c);
            if d.x_cost() || d.unplayable() {
                continue;
            }
            let unmarked = self.unmarked_cost(c);
            let free = self.free_in_hand.count(c);
            let costs = self.turn_costs.take_all(c);
            let loose = n - free - costs.len() as u8;
            // The copies above `cost` now: marked ones at a higher cost
            // this turn, and the unmarked ones when the card itself is.
            let above = costs.iter().filter(|&&k| k as i8 > cost).count() as u8 + if unmarked > cost { loose } else { 0 };
            for &k in costs.iter().filter(|&&k| k as i8 <= cost) {
                self.turn_costs.add(c, k);
            }
            for _ in 0..above {
                if cost == 0 {
                    self.free_in_hand.add(c);
                } else {
                    self.turn_costs.add(c, cost as u8);
                }
            }
        }
        if combat {
            for (c, _) in self.hand.iter().collect::<Vec<_>>() {
                let d = self.binding.def(c);
                if !d.x_cost() && !d.unplayable() && d.cost() > cost {
                    self.set_combat_cost_keep_marks(c, cost);
                }
            }
        }
    }

    /// Card `c` at cost `v` for the combat (the changed copy; `c`'s own
    /// numbers otherwise kept).
    fn at_combat_cost(&self, c: CardId, v: i8) -> CardId {
        use crate::registry::{changed_copy, copy_of, Overrides};
        let (base, o) = copy_of(c).unwrap_or((c, Overrides { level: self.binding.def(c).level, ..Overrides::default() }));
        changed_copy(base, self.binding.def(base), Overrides { cost: Some(v), ..o }).unwrap_or_else(|e| panic!("{e}"))
    }

    /// The copy of `c` that costs 1 less for the combat when `c` costs less
    /// per HP loss (Blood for Blood) and more than 0, else `None` (the
    /// game's `tookDamage`: `updateCost(-1)`, floored at 0).
    fn after_hp_loss(&self, c: CardId) -> Option<CardId> {
        let d = self.binding.def(c);
        (d.cost_less_per_hp_loss && !d.x_cost() && !d.unplayable() && d.cost() > 0).then(|| self.at_combat_cost(c, d.cost() - 1))
    }

    /// The player lost HP: each copy of a card that costs less per HP loss
    /// in the hand, draw and discard piles costs 1 less for the combat (the
    /// game's `updateCardsOnDamage`); a copy in play or taken off the draw
    /// pile to be played (the game's limbo) and the exhaust pile keep
    /// theirs. Free-this-turn marks and known-top ids follow their copies
    /// (a copy reaching 0 needs no mark).
    fn hp_loss_costs(&mut self) {
        let moved: Vec<(CardId, CardId, u8, u8)> = self
            .hand
            .iter()
            .filter_map(|(c, n)| self.after_hp_loss(c).map(|to| (c, to, n, self.free_in_hand.count(c))))
            .collect();
        // A copy at a cost this turn keeps the gap to its cost (the game's
        // `updateCost`): 1 less, at 0 free.
        let mut costs: Vec<Vec<u8>> = Vec::new();
        for &(c, _, n, m) in &moved {
            for _ in 0..m {
                self.free_in_hand.remove(c);
            }
            costs.push(self.turn_costs.take_all(c));
            self.hand.remove(c, n);
        }
        for &(_, to, n, _) in &moved {
            self.hand.add(to, n);
        }
        for (&(_, to, _, m), costs) in moved.iter().zip(&costs) {
            for _ in 0..m {
                self.mark_free_in_hand(to);
            }
            for &k in costs {
                if k > 1 {
                    self.mark_turn_cost(to, k as i8 - 1);
                } else {
                    self.mark_free_in_hand(to);
                }
            }
        }
        let mut map: Vec<(CardId, CardId)> = Vec::new();
        for r in [Run::Draw, Run::Discard] {
            let before: Vec<(CardId, CardId, u8)> = self.piles.get(r).iter().filter_map(|(c, n)| self.after_hp_loss(c).map(|to| (c, to, n))).collect();
            let mut pile = self.piles.get_mut(r);
            for &(c, _, n) in &before {
                pile.remove(c, n);
            }
            for &(_, to, n) in &before {
                pile.add(to, n);
            }
            if r == Run::Draw {
                map.extend(before.iter().map(|&(c, to, _)| (c, to)));
            }
        }
        if !map.is_empty() && !self.top.is_empty() {
            self.top.map_cards(|c| map.iter().find(|m| m.0 == c).map_or(c, |m| m.1));
        }
    }

    /// A copy of `c` made in combat (the game's `makeCopy`): a card that
    /// costs less per HP loss starts at its cost less this combat's losses
    /// (floored at 0).
    fn made_copy(&self, c: CardId) -> CardId {
        let d = self.binding.def(c);
        if !d.cost_less_per_hp_loss || self.times_lost_hp == 0 || d.x_cost() || d.unplayable() || d.cost() <= 0 {
            return c;
        }
        self.at_combat_cost(c, (d.cost() - self.times_lost_hp as i8).max(0))
    }

    /// Counts the Status and Curse cards of a draw for the `CardDrawn`
    /// hooks (each type only while a held hook takes it), and queues its
    /// cost rolls (Confused).
    pub(crate) fn count_drawn(&mut self, drawn: PileRef<'_>) {
        self.queue_drawn_rolls(drawn);
        let count = |s: &Self, ty: CardType| -> u8 {
            if !s.holds_draw_hook(ty) {
                return 0;
            }
            let k: u32 = drawn.iter().filter(|&(c, _)| s.binding.def(c).ty == ty).map(|(_, n)| n as u32).sum();
            k.min(u8::MAX as u32) as u8
        };
        let (status, curse) = (count(self, CardType::Status), count(self, CardType::Curse));
        self.unfired_draws = self.unfired_draws.saturating_add(status);
        self.unfired_curse_draws = self.unfired_curse_draws.saturating_add(curse);
    }

    pub fn is_over(&self) -> bool {
        matches!(self.stage, Stage::Over { .. })
    }

    pub fn won(&self) -> bool {
        self.stage == Stage::Over { won: true }
    }

    /// won × (2 − HP lost / 100), HP lost counted after end-of-combat
    /// healing and floored at 0; 0 while the combat is running.
    pub fn score(&self) -> f64 {
        if self.won() {
            2.0 - (self.start_hp - self.player.hp).max(0) as f64 / 100.0
        } else {
            0.0
        }
    }

    /// Each distinct legal action once: card plays in card id then slot
    /// order, then potion uses (a potion's first copy, by held slot, then
    /// target), EndTurn last.
    pub fn legal_actions(&self) -> Vec<Action> {
        let mut v = Vec::new();
        if !self.awaiting_action() {
            return v;
        }
        // At a pick: each distinct candidate once, then `Done` if offered.
        if let Some(p) = self.pick() {
            if let Some(src) = self.pick_source(&p) {
                v.extend(src.iter().map(|(c, _)| Action::Choose(c)));
            }
            if !p.exact {
                v.push(Action::Done);
            }
            return v;
        }
        for (card, _) in self.hand.iter() {
            let d = self.binding.def(card);
            if !self.can_play(card) {
                continue;
            }
            if d.targeted() {
                for slot in self.living_slots() {
                    v.push(Action::Play { card, target: Some(slot as u8) });
                }
            } else {
                v.push(Action::Play { card, target: None });
            }
        }
        for slot in 0..self.player.potions.len() {
            if !self.potion_drinkable(slot) {
                continue;
            }
            if CombatState::potion_spec(self.player.potions.id(slot)).targeted() {
                for t in self.living_slots() {
                    v.push(Action::UsePotion { slot: slot as u8, target: Some(t as u8) });
                }
            } else {
                v.push(Action::UsePotion { slot: slot as u8, target: None });
            }
        }
        v.push(Action::EndTurn);
        v
    }

    pub fn is_legal(&self, a: Action) -> bool {
        if !self.awaiting_action() {
            return false;
        }
        if let Some(p) = self.pick() {
            return match a {
                Action::Choose(c) => self.pick_source(&p).is_some_and(|src| src.count(c) > 0),
                Action::Done => !p.exact,
                _ => false,
            };
        }
        match a {
            Action::Choose(_) | Action::Done => false,
            Action::EndTurn => true,
            Action::UsePotion { slot, target } => {
                self.potion_drinkable(slot as usize)
                    && match (CombatState::potion_spec(self.player.potions.id(slot as usize)).targeted(), target) {
                        (true, Some(t)) => self.monsters.get(t as usize).is_some_and(|m| m.alive()),
                        (false, None) => true,
                        _ => false,
                    }
            }
            Action::Play { card, target } => {
                let d = self.binding.def(card);
                self.hand.count(card) > 0
                    && self.can_play(card)
                    && match (d.targeted(), target) {
                        (true, Some(t)) => self.monsters.get(t as usize).is_some_and(|m| m.alive()),
                        (false, None) => true,
                        _ => false,
                    }
            }
        }
    }

    /// Applies one action and runs until the next decision or chance event.
    pub fn apply_action(&mut self, a: Action) -> Result<(), IllegalAction> {
        if !self.is_legal(a) {
            return Err(IllegalAction);
        }
        match a {
            Action::EndTurn => self.end_turn(),
            Action::Play { card, target } => {
                let d = self.binding.def(card);
                let x = if d.x_cost() { std::mem::take(&mut self.player.energy).clamp(0, u8::MAX as i16) as u8 } else { 0 };
                // An unplayable card a rule plays (Blue Candle) costs 0.
                self.player.energy -= self.cost_of(card).max(0) as i16;
                // The cheapest copy is the one played: a copy marked 0, then
                // the lowest cost this turn.
                if !self.free_in_hand.is_empty() && self.free_in_hand.count(card) > 0 {
                    self.free_in_hand.remove(card);
                } else if let Some(v) = self.turn_costs.lowest(card) {
                    self.turn_costs.remove(card, v);
                }
                self.hand_remove(card, 1);
                self.cards_played_this_turn = self.cards_played_this_turn.saturating_add(1);
                self.stage = Stage::PlayingCard { card, target, next: 0, hit: 0, x, more: InPlay::default() };
                if self.owner_plays_card(card, target) || self.hand_sees_play() || self.card_played(card, target) {
                    return Ok(());
                }
                self.run();
            }
            Action::UsePotion { slot, target } => {
                // The potion leaves the list first, then its rows run.
                let potion = self.player.potions.remove(slot as usize);
                self.stage = Stage::UsingPotion { potion, target, next: 0, hit: 0, pick: None };
                self.run();
            }
            Action::Choose(c) => {
                let mut p = self.pick().expect("legal only at a pick");
                match p.kind {
                    PickKind::DiscardFromHand => {
                        self.hand_remove(c, 1);
                        self.discard_mut().add(c, 1);
                    }
                    PickKind::ReturnFromDiscard => {
                        self.discard_mut().remove(c, 1);
                        self.hand.add(c, 1);
                        if p.free {
                            self.mark_free_in_hand(c);
                        }
                    }
                    PickKind::DiscardToTop => {
                        self.discard_mut().remove(c, 1);
                        self.draw_mut().add(c, 1);
                        let all = self.sees_order();
                        self.top.push(c, all);
                    }
                    PickKind::ExhaustFromHand => {
                        self.hand_remove(c, 1);
                        self.exhaust_card(c, 1);
                    }
                    PickKind::ReturnFromExhaust => {
                        self.exhaust_mut().remove(c, 1);
                        self.hand.add(c, 1);
                        if p.free {
                            self.mark_free_in_hand(c);
                        }
                    }
                    PickKind::UpgradeFromHand => {
                        self.upgrade_in_hand(c);
                    }
                    PickKind::HandToTop => self.hand_to_top(c, 1),
                    PickKind::DrawToHand => self.take_from_draw(c),
                    PickKind::Offered => self.take_offered(c),
                    PickKind::CopyInHand => self.copy_in_hand(c, p.copies, p.free),
                }
                p.left -= 1;
                let left = (p.left > 0 && self.pick_source(&p).is_some()).then_some(p);
                self.set_pick(left);
                self.count_pick();
                self.run();
            }
            Action::Done => {
                // A skipped offer gives nothing.
                self.offer = Offer::default();
                self.set_pick(None);
                self.run();
            }
        }
        Ok(())
    }

    /// One card picked: the stage's `hit` counts it when the effect after
    /// the pick is `DrawPicked` (docs/specs/fight-vocabulary.md).
    fn count_pick(&mut self) {
        let at_next = match self.stage {
            Stage::PlayingCard { card, next, .. } => self.binding.def(card).effect_at(next as usize).map(|at| at.effect),
            Stage::UsingPotion { potion, next, .. } => CombatState::potion_spec(potion).effect_at(next as usize).map(|at| at.effect),
            Stage::RelicPick { relic, hook, next, .. } => self.player.relics.id(relic as usize).hooks()[hook as usize].effects.get(next as usize).copied(),
            _ => None,
        };
        if at_next == Some(Effect::DrawPicked) {
            match &mut self.stage {
                Stage::PlayingCard { hit, .. } | Stage::UsingPotion { hit, .. } | Stage::RelicPick { hit, .. } => *hit += 1,
                _ => {}
            }
        }
    }

    /// The offer's cards are `cards` (the chance event's outcome, or the
    /// whole filtered pool): the pick opens, with `Done` when the offer may
    /// be skipped; one card with no skip is taken at once (Infernal Blade);
    /// none gives nothing.
    pub(crate) fn set_offer(&mut self, cards: &[CardId]) {
        let skip = self.offer.skip;
        let mut sorted: Vec<CardId> = cards.to_vec();
        sorted.sort();
        if sorted.is_empty() {
            self.offer = Offer::default();
            return;
        }
        if sorted.len() == 1 && !skip {
            self.take_offered(sorted[0]);
            return;
        }
        for (i, c) in sorted.iter().enumerate() {
            self.offer.cards[i] = c.0;
        }
        self.offer.n = sorted.len() as u8;
        self.set_pick(Some(Pick::new(PickKind::Offered, 1, !skip, false)));
    }

    /// The offered card `c` taken: the offer's copies into hand while it
    /// holds fewer than `HAND_LIMIT`, each marked free with `free`, the rest
    /// into the discard pile; the offer closes.
    fn take_offered(&mut self, c: CardId) {
        let o = std::mem::take(&mut self.offer);
        let c = self.made_copy(c);
        self.created = self.created.saturating_add(o.copies as u16);
        for _ in 0..o.copies {
            if self.hand.len() < HAND_LIMIT {
                self.hand.add(c, 1);
                // Costs 0 this turn (`setCostForTurn(0)`); a copy sent to
                // the discard pile isn't marked (a named limit).
                if o.free {
                    self.mark_free_in_hand(c);
                }
            } else {
                self.discard_mut().add(c, 1);
            }
        }
    }

    /// The player's `OwnerPlaysCard` hooks for the card just played, before
    /// its effects (Burst), unless it is a replayed copy. Returns whether the
    /// combat ended.
    fn owner_plays_card(&mut self, card: CardId, target: Option<u8>) -> bool {
        let ctx = HookCtx { card: Some(card), target, drawn: None };
        self.run_hooks_with(Who::Player, |h: &Hook| h.trigger == Trigger::OwnerPlaysCard, ctx)
    }

    /// A card was played (it has left the hand): each held card's
    /// `other_played` effects, once per copy (Pain's 1 HP; the game's
    /// `triggerOnOtherCardPlayed`, queued on top, ahead of the card's own
    /// actions). Returns whether the combat ended.
    fn hand_sees_play(&mut self) -> bool {
        if self.hand.iter().all(|(c, _)| self.binding.def(c).other_played.is_empty()) {
            return false;
        }
        for (c, n) in self.hand.iter().collect::<Vec<_>>() {
            for _ in 0..n {
                for e in self.binding.def(c).other_played {
                    self.do_effect(Who::Player, e, None);
                    if self.check_over() {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// `apply_action`, then samples every chance event up to the next decision.
    pub fn step(&mut self, a: Action, rng: &mut Rng) -> Result<(), IllegalAction> {
        self.apply_action(a)?;
        self.advance(rng);
        Ok(())
    }

    /// What playing `card` costs now (cost-changes spec): its cost for the
    /// combat (a copy that costs less per HP loss carries its drops,
    /// `hp_loss_costs`), then at most a held power's `sets_cost` for the
    /// card's type.
    /// X-cost and unplayable cards keep their base cost. A card with a
    /// copy marked in hand costs 0 (docs/specs/act1-singles.md).
    pub fn cost_of(&self, card: CardId) -> i8 {
        let d = self.binding.def(card);
        if d.x_cost() || d.unplayable() {
            return d.cost();
        }
        if !self.free_in_hand.is_empty() && self.free_in_hand.count(card) > 0 {
            return 0;
        }
        let unmarked = self.unmarked_cost(card);
        match self.turn_costs.lowest(card) {
            Some(v) => unmarked.min(v as i8),
            None => unmarked,
        }
    }

    /// `cost_of` without the marks (an X-cost or unplayable card's base
    /// cost included).
    pub(crate) fn unmarked_cost(&self, card: CardId) -> i8 {
        let d = self.binding.def(card);
        let mut c = d.cost();
        for g in self.binding.rule_powers() {
            if self.player.powers.get(g) != 0 {
                if let Some((ty, v)) = self.binding.sets_cost(g) {
                    if ty == d.ty && c > v {
                        c = v;
                    }
                }
            }
        }
        c
    }

    /// Marks one copy of `card` in hand as costing 0 this turn (the game's
    /// `setCostForTurn(0)`; docs/specs/act1-singles.md): only when its cost
    /// now is above 0, it isn't X-cost or unplayable, and a copy in hand is
    /// still unmarked. Returns whether it marked one. Liquid Memories' pick
    /// calls it; so does discovery (P3) when its card enters the hand.
    pub fn mark_free_in_hand(&mut self, card: CardId) -> bool {
        let d = self.binding.def(card);
        if d.x_cost() || d.unplayable() || self.unmarked_cost(card) <= 0 || self.free_in_hand.count(card) >= self.hand.count(card) {
            return false;
        }
        if self.free_in_hand.count(card) + self.turn_costs.count(card) < self.hand.count(card) {
            return self.free_in_hand.add(card);
        }
        // Every copy holds a mark: one that costs something this turn
        // becomes free (a copy's identity is only its mark).
        let Some(v) = self.turn_costs.highest(card) else { return false };
        self.turn_costs.remove(card, v);
        self.free_in_hand.add(card)
    }

    /// What the marks take off the hand this turn: for each marked copy,
    /// its cost less its cost this turn (the net's `hand_turn_discount`).
    pub fn hand_turn_discount(&self) -> i32 {
        let free: i32 = self.free_in_hand.iter().map(|c| self.unmarked_cost(c) as i32).sum();
        let costs: i32 = self.turn_costs.iter().map(|(c, v)| self.unmarked_cost(c) as i32 - v as i32).sum();
        free + costs
    }

    /// Marks one copy of `card` in hand as costing `v` (at least 1) this
    /// turn: only when that is below its cost now, it isn't X-cost or
    /// unplayable, and a copy in hand holds no mark. Returns whether it did.
    pub(crate) fn mark_turn_cost(&mut self, card: CardId, v: i8) -> bool {
        let d = self.binding.def(card);
        if v < 1 || d.x_cost() || d.unplayable() || v >= self.unmarked_cost(card) || self.free_in_hand.count(card) + self.turn_costs.count(card) >= self.hand.count(card) {
            return false;
        }
        self.turn_costs.add(card, v as u8)
    }

    /// Takes `n` copies of `c` out of the hand, the dearest first: unmarked
    /// copies, then the highest cost this turn, then copies marked 0 (a play
    /// takes the cheapest itself, before calling this).
    pub(crate) fn hand_remove(&mut self, c: CardId, n: u8) {
        self.hand.remove(c, n);
        if !self.free_in_hand.is_empty() || !self.turn_costs.is_empty() {
            self.cap_marks(c);
        }
    }

    /// Drops the marks of `c` beyond its copies in hand, the dearest first.
    fn cap_marks(&mut self, c: CardId) {
        let copies = self.hand.count(c);
        while self.free_in_hand.count(c) + self.turn_costs.count(c) > copies {
            match self.turn_costs.highest(c) {
                Some(v) => self.turn_costs.remove(c, v),
                None => self.free_in_hand.remove(c),
            };
        }
    }

    /// Whether the player holds a power that exhausts played cards of `ty`
    /// (Corruption: Skill).
    fn exhausts_played(&self, ty: CardType) -> bool {
        self.binding.rule_powers().any(|g| self.player.powers.get(g) != 0 && self.binding.exhausts_played(g) == Some(ty))
    }

    /// Playable, affordable, and its play condition holds (Clash: only
    /// Attacks in hand).
    fn can_play(&self, card: CardId) -> bool {
        self.cost_of(card) as i16 <= self.player.energy && self.playable_now(card)
    }

    /// Playable now, energy aside: not unplayable unless a held power plays
    /// its type (Blue Candle), its play condition holds, no held power
    /// forbids its type (Entangled) and no play limit is reached (Velvet
    /// Choker, Normality).
    fn playable_now(&self, card: CardId) -> bool {
        let d = self.binding.def(card);
        (!d.unplayable() || self.binding.rule_powers().any(|g| self.player.powers.get(g) != 0 && self.binding.plays_unplayable(g) == Some(d.ty)))
            && d.playable_if.is_none_or(|c| self.condition_holds(Who::Player, c, HookCtx::default()))
            && !self.binding.rule_powers().any(|g| self.player.powers.get(g) != 0 && self.binding.forbids(g) == Some(d.ty))
            && self.under_play_limit()
    }

    /// Plays the queue's front card (docs/specs/act1-singles.md): free,
    /// counted as played, with its play hooks, at its X. One that can't be
    /// played now, or whose target died, goes to the discard pile unplayed
    /// (exhausted when it would exhaust). Returns whether the combat ended
    /// or a chance event paused.
    fn play_queued(&mut self) -> bool {
        let q = *self.top_queue.iter().next().expect("a queued card");
        let dead = q.target.is_some_and(|t| !self.monsters[t as usize].alive());
        let unplayed = dead || !self.playable_now(q.card);
        // Unplayed, it still passes the game's `UseCardAction`: a card that
        // would exhaust (not a Power) rolls the exhaust save first, the
        // card staying at the queue's front (`ChanceEvent::ExhaustSave`).
        if unplayed && (q.exhaust || self.binding.def(q.card).exhaust) && self.binding.def(q.card).ty != CardType::Power {
            match self.exhaust_save_chance() {
                p if p >= 1.0 => {
                    self.top_queue.pop_front();
                    self.discard_mut().add(q.card, 1);
                    return false;
                }
                p if p > 0.0 => {
                    self.pending = Some(ChanceEvent::ExhaustSave { queued: true });
                    return true;
                }
                _ => {}
            }
        }
        let q = self.top_queue.pop_front().expect("a queued card");
        if unplayed {
            if q.exhaust || self.binding.def(q.card).exhaust {
                self.exhaust_card(q.card, 1);
                return self.fire_exhausts(false);
            }
            self.discard_mut().add(q.card, 1);
            return false;
        }
        self.cards_played_this_turn = self.cards_played_this_turn.saturating_add(1);
        let more = InPlay { exhaust: q.exhaust, queued: true, ..InPlay::default() };
        self.stage = Stage::PlayingCard { card: q.card, target: q.target, next: 0, hit: 0, x: q.x, more };
        self.owner_plays_card(q.card, q.target) || self.hand_sees_play() || self.card_played(q.card, q.target)
    }

    pub fn living_slots(&self) -> impl Iterator<Item = usize> + '_ {
        (0..MAX_MONSTERS).filter(|&i| self.monsters[i].alive())
    }

    /// Moves through transient stages until a decision, a pending chance
    /// event or the end of combat.
    pub(crate) fn run(&mut self) {
        self.run_opts(false)
    }

    /// `run`; `turn1_pre_draw` plays turn 1 like every later turn (only the
    /// fight's constructor plays turn 1, so only it passes `true`).
    pub(crate) fn run_opts(&mut self, turn1_pre_draw: bool) {
        // `OwnerHandEmpty` hooks ran and left the hand empty: this run
        // settles rather than run them again.
        let mut hand_empty_fired = false;
        while self.pending.is_none() {
            // A card waiting for a cost roll is rolled before anything else
            // goes on (docs/specs/sparse-piles.md).
            if !self.cost_rolls.is_empty() {
                if self.is_over() {
                    self.cost_rolls.clear();
                } else {
                    self.pending = Some(ChanceEvent::RandomCost);
                    return;
                }
            }
            // Then random work a hook owes, in order; work owed behind a
            // relic's open pick or offer waits for its hook to finish.
            if let Some(e) = self.owed.front() {
                if self.is_over() {
                    self.owed.clear();
                } else if !(e.wait && matches!(self.stage, Stage::RelicPick { .. } | Stage::RelicOffer { .. }))
                    && !(matches!(e.kind, OwedKind::Hit { .. }) && matches!(self.stage, Stage::PlayingCard { .. }))
                {
                    self.pay_owed();
                    continue;
                }
            }
            match self.stage {
                // Takes a power's hook owes at the bottom of the turn
                // start's queue (Mayhem) come once the turn has settled,
                // ahead of the triggers of the turn's draw (Evolve): one
                // card at a time, all taken before any plays.
                Stage::PlayerTurn if !self.owed_late.is_empty() && !self.top_queue.is_full() => {
                    let e = self.owed_late.front().expect("owed work");
                    let OwedKind::Top { exhaust } = e.kind else { unreachable!("{:?} isn't a late take", e.kind) };
                    if self.draw().len() + self.discard().len() == 0 {
                        self.owed_late.take_front(e.n);
                    } else {
                        self.owed_late.take_front(1);
                        self.request_take_top(exhaust);
                    }
                }
                // Blocks broken outside a card or potion (a hook's damage)
                // fire where the turn settles.
                Stage::PlayerTurn if self.block_broken != [0; MAX_MONSTERS] => {
                    if self.fire_block_broken() {
                        return;
                    }
                }
                // Status cards drawn: the player's `CardDrawn` hooks fire
                // once per card (a `Draw` among them may pause and count
                // again; the loop goes on when it resolves).
                Stage::PlayerTurn if self.unfired_draws != 0 => {
                    self.unfired_draws -= 1;
                    if self.fire_draw(CardType::Status) {
                        return;
                    }
                }
                // Curse cards drawn, after the draw's Status cards (the game
                // fires each card in draw order).
                Stage::PlayerTurn if self.unfired_curse_draws != 0 => {
                    self.unfired_curse_draws -= 1;
                    if self.fire_draw(CardType::Curse) {
                        return;
                    }
                }
                // Cards `PlayTop` took play once the card or potion that
                // took them has finished (the game's card queue).
                Stage::PlayerTurn if !self.top_queue.is_empty() => {
                    if self.play_queued() {
                        return;
                    }
                }
                // The turn settles with an empty hand and a card to draw:
                // the player's `OwnerHandEmpty` hooks (Unceasing Top). A
                // pass that leaves the hand empty settles the turn.
                Stage::PlayerTurn if !hand_empty_fired && self.hand.is_empty() && self.draw().len() + self.discard().len() > 0 && self.player_has_trigger(Trigger::OwnerHandEmpty) => {
                    if self.run_hooks(Who::Player, Trigger::OwnerHandEmpty) {
                        return;
                    }
                    hand_empty_fired = self.hand.is_empty();
                }
                Stage::PlayerTurn | Stage::Over { .. } => {
                    self.dealt = 0;
                    return;
                }
                // End Turn goes on once the owed work is paid.
                Stage::EndingTurn { part } => {
                    self.stage = Stage::PlayerTurn;
                    self.end_turn_from(part);
                    return;
                }
                // The monsters' turn goes on once its pick (or the draw
                // before it) is resolved.
                Stage::MonsterActing { slot, next } => {
                    self.stage = Stage::PlayerTurn;
                    self.monsters_turn_from(slot as usize, next as usize, true);
                    return;
                }
                // Paused at a pick: the player acts next.
                Stage::PlayingCard { more: InPlay { pick: Some(_), .. }, .. } => return,
                Stage::PlayingCard { card, target, next, hit, x, more } => match self.binding.def(card).effect_at(next as usize) {
                    // Runic Dome: a row asking whether a hidden target
                    // attacks reveals that much first (Spot Weakness).
                    Some(at) if at.row_start && hit == 0 && at.condition == Condition::TargetIntendsAttack && target.is_some_and(|t| self.intent_class_unknown(t as usize)) => {
                        self.pending = Some(ChanceEvent::IntentClass { slot: target.expect("a target") });
                        return;
                    }
                    // A row whose condition fails is skipped whole.
                    Some(at) if at.row_start && hit == 0 && !self.condition_holds(Who::Player, at.condition, HookCtx { card: Some(card), target, drawn: None }) => {
                        self.stage = Stage::PlayingCard { card, target, next: at.row_end as u8, hit: 0, x, more };
                    }
                    Some(at) => match at.effect {
                    Effect::RandomDamage { amount, hits } | Effect::RandomApply { amount, hits, .. } => {
                        if hit >= hits {
                            self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        } else {
                            self.stage = Stage::PlayingCard { card, target, next, hit: hit + 1, x, more };
                            self.request_random_hit(amount);
                        }
                    }
                    // One card at a time off the draw pile into the queue,
                    // while any is left (docs/specs/act1-singles.md).
                    Effect::PlayTop { n, exhaust } => {
                        if hit >= n || self.draw().len() + self.discard().len() == 0 || self.top_queue.is_full() {
                            self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        } else {
                            self.stage = Stage::PlayingCard { card, target, next, hit: hit + 1, x, more };
                            self.request_take_top(exhaust);
                        }
                    }
                    // One roll at a time, each its own chance event (the
                    // game rolls each card alone; colorless-cards spec).
                    Effect::MakeRandom { pool, ty, n, pile, zero_cost, free, match_level } => {
                        let total = self.resolve(Who::Player, n).max(0);
                        if hit as i16 >= total || crate::registry::pool_cards(&self.binding, pool, ty).is_empty() {
                            self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        } else {
                            self.stage = Stage::PlayingCard { card, target, next, hit: hit + 1, x, more };
                            let up = match_level && self.binding.def(card).level > 0;
                            self.pending = Some(ChanceEvent::MakeRandom { pool, ty, pile, zero_cost, free, up });
                        }
                    }
                    // An upgrade pick with one distinct candidate is made at
                    // once (sts_lightspeed's ArmamentsAction).
                    Effect::Pick { kind: PickKind::UpgradeFromHand, n: 1, exact: true, free: false, .. }
                        if self.only_candidate(&at.effect).is_some() =>
                    {
                        self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        let c = self.only_candidate(&at.effect).expect("one candidate");
                        self.upgrade_in_hand(c);
                    }
                    // A copy pick with one distinct candidate copies it at
                    // once (`DualWieldAction` opens no screen for one card).
                    Effect::Pick { kind: PickKind::CopyInHand, n: 1, exact: true, free, copies, .. } if self.only_candidate(&at.effect).is_some() => {
                        self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        let c = self.only_candidate(&at.effect).expect("one candidate");
                        self.copy_in_hand(c, copies, free);
                    }
                    // One kind of the draw pile to choose from: it goes to
                    // the hand at once (the game's grid opens for 2 or more).
                    Effect::Pick { kind: PickKind::DrawToHand, n: 1, exact: true, .. } if self.only_candidate(&at.effect).is_some() => {
                        self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        let c = self.only_candidate(&at.effect).expect("one candidate");
                        self.take_from_draw(c);
                    }
                    // At most `n` cards, all of one kind, in hand: they go on
                    // top at once (`PutOnDeckAction` moves the whole hand then).
                    Effect::Pick { kind: PickKind::HandToTop, n, of: Types::ALL, .. }
                        if self.hand.len() <= n as usize && self.hand.iter().count() == 1 =>
                    {
                        self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        let (c, k) = self.hand.iter().next().expect("one kind in hand");
                        self.hand_to_top(c, k);
                    }
                    Effect::Pick { n, .. } => {
                        let pick = Pick::of_effect(&at.effect).filter(|p| n > 0 && self.pick_source(p).is_some());
                        self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more: InPlay { pick, ..more } };
                    }
                    // As many as the pick before it took (`hit` counted them).
                    Effect::DrawPicked => {
                        self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        self.do_effect(Who::Player, &Effect::Draw(hit), target);
                    }
                    e => {
                        self.stage = Stage::PlayingCard { card, target, next: next + 1, hit: 0, x, more };
                        self.do_effect(Who::Player, &e, target);
                        self.check_over();
                    }
                    },
                    None => {
                        // Hits owed while the card ran (Juggernaut) land
                        // once its effects have, before the reactions it
                        // set off (Curl Up's block, Hand Drill).
                        if self.owed.front().is_some_and(|e| matches!(e.kind, OwedKind::Hit { .. })) {
                            self.pay_owed();
                            continue;
                        }
                        // A card that would exhaust rolls the exhaust save
                        // first (Strange Spoon; the game rolls it in
                        // `UseCardAction`, with no decision in between).
                        if more.save.is_none() && !more.copy && self.would_exhaust(card, more.exhaust) {
                            match self.exhaust_save_chance() {
                                p if p >= 1.0 => {
                                    self.stage = Stage::PlayingCard { card, target, next, hit, x, more: InPlay { save: Some(true), ..more } };
                                    continue;
                                }
                                p if p > 0.0 => {
                                    self.pending = Some(ChanceEvent::ExhaustSave { queued: false });
                                    return;
                                }
                                _ => {}
                            }
                        }
                        if self.card_resolved(card, target) {
                            return;
                        }
                        // Blocks the card broke (Hand Drill): queued behind
                        // the card's actions, before its block-gain
                        // reactions (Curl Up) and its exhausts'.
                        if self.fire_block_broken() {
                            return;
                        }
                        self.finish_card(card, more.copy, more.exhaust, more.save == Some(true));
                        // Read again: the card's own hooks may have asked for a replay.
                        let replays = match self.stage {
                            Stage::PlayingCard { more, .. } => more.replays,
                            _ => 0,
                        };
                        // A copy past a relic's play limit isn't played (the
                        // game's queued copy fails `canUse`).
                        if replays > 0 && self.under_play_limit() {
                            // The copy: free, same target and X, counted as played,
                            // seen by monsters' hooks, purged afterwards.
                            self.cards_played_this_turn = self.cards_played_this_turn.saturating_add(1);
                            let more = InPlay { pick: None, replays: replays - 1, copy: true, exhaust: false, queued: false, save: None };
                            self.stage = Stage::PlayingCard { card, target, next: 0, hit: 0, x, more };
                            if self.hand_sees_play() || self.card_played(card, target) {
                                return;
                            }
                        } else {
                            self.stage = Stage::PlayerTurn;
                        }
                        // The card is placed: its exhausts' hooks fire (the
                        // game queues them behind it). A draw may pause here;
                        // the stage has already moved on.
                        if self.fire_exhausts(false) {
                            return;
                        }
                    }
                },
                // Paused at a pick: the player acts next.
                Stage::UsingPotion { pick: Some(_), .. } => return,
                Stage::UsingPotion { potion, target, next, hit, pick: None } => match CombatState::potion_spec(potion).effect_at(next as usize) {
                    // A row whose condition fails is skipped whole.
                    Some(at) if at.row_start && hit == 0 && !self.condition_holds(Who::Player, at.condition, HookCtx { card: None, target, drawn: None }) => {
                        self.stage = Stage::UsingPotion { potion, target, next: at.row_end as u8, hit: 0, pick: None };
                    }
                    Some(at) => {
                        let on = |next: u8, hit: u8, pick: Option<Pick>| Stage::UsingPotion { potion, target, next, hit, pick };
                        // Sacred Bark: a potion with potency runs at its
                        // multiple (a pack power's amount too).
                        let effect = crate::potions::scaled_effect(at.effect, self.potion_scale(potion));
                        match effect {
                            Effect::RandomDamage { amount, hits } | Effect::RandomApply { amount, hits, .. } => {
                                if hit >= hits {
                                    self.stage = on(next + 1, 0, None);
                                } else {
                                    self.stage = on(next, hit + 1, None);
                                    self.request_random_hit(amount);
                                }
                            }
                            Effect::Pick { n, .. } => {
                                let pick = Pick::of_effect(&effect).filter(|p| n > 0 && self.pick_source(p).is_some());
                                self.stage = on(next + 1, 0, pick);
                            }
                            Effect::PlayTop { n, exhaust } => {
                                if hit >= n || self.draw().len() + self.discard().len() == 0 || self.top_queue.is_full() {
                                    self.stage = on(next + 1, 0, None);
                                } else {
                                    self.stage = on(next, hit + 1, None);
                                    self.request_take_top(exhaust);
                                }
                            }
                            // Raw block (the game's GainBlockAction): no
                            // Dexterity or Frail.
                            Effect::Block(n) => {
                                self.stage = on(next + 1, 0, None);
                                self.add_block(Who::Player, n);
                            }
                            Effect::DrawPicked => {
                                self.stage = on(next + 1, 0, None);
                                self.do_effect(Who::Player, &Effect::Draw(hit), target);
                            }
                            // One random potion per empty slot, each its own
                            // chance event; the use stays here until the
                            // slots are full (the game's queued
                            // ObtainPotionActions, Entropic Brew).
                            // Sozu (`no_potions`): none (EntropicBrew.use).
                            Effect::ObtainRandomPotions { pool } => {
                                if self.player.potions.len() < self.potion_slots().min(crate::potions::POTION_CAP) && !self.player.relics.iter().any(|(id, _)| id.rules().no_potions) {
                                    // `hit` past 0: its row's condition isn't read again.
                                    self.stage = on(next, hit.saturating_add(1), None);
                                    self.pending = Some(ChanceEvent::RandomPotion { pool });
                                } else {
                                    self.stage = on(next + 1, 0, None);
                                }
                            }
                            e => {
                                self.stage = on(next + 1, 0, None);
                                self.do_effect(Who::Player, &e, target);
                                self.check_over();
                            }
                        }
                    }
                    None => {
                        // Blocks the potion broke (Hand Drill), before the
                        // block-gain reactions that waited for it.
                        if self.fire_block_broken() {
                            return;
                        }
                        self.finish_potion();
                        self.stage = Stage::PlayerTurn;
                        // Toy Ornithopter: queued behind the potion's own
                        // actions, before its exhausts' reactions.
                        self.run_hooks(Who::Player, Trigger::OwnerUsedPotion);
                        // Its exhausts' hooks fire once it has resolved
                        // (Elixir with Feel No Pain).
                        if self.fire_exhausts(false) {
                            return;
                        }
                    }
                },
                // A relic's pick (Gambling Chip): the player acts next; once
                // done, the rest of its hook, then the player's turn.
                Stage::RelicPick { pick: Some(_), .. } => return,
                Stage::RelicPick { relic, hook, next, hit, pick: None } => {
                    let h = &self.player.relics.id(relic as usize).hooks()[hook as usize];
                    match h.effects.get(next as usize).copied() {
                        Some(e) => {
                            self.stage = Stage::RelicPick { relic, hook, next: next + 1, hit: 0, pick: None };
                            match e {
                                Effect::DrawPicked => self.do_effect(Who::Player, &Effect::Draw(hit), None),
                                Effect::SetCounter(n) => self.player.relics.set_counter(relic as usize, n),
                                Effect::AddCounter(n) => {
                                    let c = self.player.relics.counter(relic as usize).saturating_add(n);
                                    self.player.relics.set_counter(relic as usize, c)
                                }
                                // Raw block, as a relic's hook gives it.
                                Effect::Block(n) => self.add_block(Who::Player, n),
                                e if self.owes(Who::Player, &e) => self.owe(Who::Player, e, 1),
                                e => self.do_effect(Who::Player, &e, None),
                            }
                            self.check_over();
                        }
                        None => {
                            self.stage = Stage::PlayerTurn;
                            if self.fire_exhausts(false) {
                                return;
                            }
                        }
                    }
                }
                // A relic's offer before the opening draw (Toolbox): the
                // player picks, then the hook's rest, then the turn starts
                // (its pre-draw hooks with `turn1_pre_draw`, then the draw).
                // A pick's `run` drops `turn1_pre_draw`: those hooks then run
                // once, after the draw (`TurnStarted`'s `late`).
                Stage::RelicOffer { pick: Some(_), .. } => return,
                Stage::RelicOffer { relic, hook, next, pick: None } => {
                    let h = &self.player.relics.id(relic as usize).hooks()[hook as usize];
                    match h.effects.get(next as usize).copied() {
                        Some(e) => {
                            self.stage = Stage::RelicOffer { relic, hook, next: next + 1, pick: None };
                            match e {
                                Effect::SetCounter(n) => self.player.relics.set_counter(relic as usize, n),
                                Effect::AddCounter(n) => {
                                    let c = self.player.relics.counter(relic as usize).saturating_add(n);
                                    self.player.relics.set_counter(relic as usize, c)
                                }
                                Effect::Draw(n) => self.owed_draw = self.owed_draw.saturating_add(n),
                                Effect::Block(n) => self.add_block(Who::Player, n),
                                e if self.owes(Who::Player, &e) => self.owe(Who::Player, e, 1),
                                e => self.do_effect(Who::Player, &e, None),
                            }
                            self.check_over();
                        }
                        None => {
                            self.stage = Stage::StartTurn;
                            if turn1_pre_draw && self.pre_draw_hooks() {
                                return;
                            }
                        }
                    }
                }
                Stage::MonsterRolls { next } => {
                    let slot = next as usize;
                    if slot >= MAX_MONSTERS {
                        if self.no_death && self.turn >= NO_DEATH_TURN_LIMIT {
                            self.stage = Stage::Over { won: false };
                            return;
                        }
                        // Frozen Eye: the opening shuffle's order is shown
                        // before the fight's start (`initializeDeck` runs
                        // before `atBattleStartPreDraw`); innate cards are
                        // on top (`Top::set_known` in the event).
                        if self.turn == 0 && self.top.n_known() < self.draw().len() && self.sees_order() {
                            self.pending = Some(ChanceEvent::Order { then: crate::chance::OrderThen::Nothing });
                            return;
                        }
                        // The turn starts: its resets, then the player's
                        // pre-draw hooks (the game's `atStartOfTurn`); a
                        // `Draw` among them joins the turn's draw, and a kill
                        // ends the fight before it. On turn 1 they wait for
                        // the opening draw (`TurnStarted`) unless
                        // `turn1_pre_draw`. A chance event among them pauses
                        // at `StartTurn`, the draw still to come.
                        self.turn += 1;
                        self.cards_played_this_turn = 0;
                        self.player.block = self.block_after_turn_start();
                        // Ice Cream: unspent energy carries over (the game's
                        // `recharge` adds instead of setting).
                        let keeps = self.player.relics.iter().any(|(id, _)| id.rules().keeps_energy);
                        self.player.energy = if keeps { (self.player.energy.max(0) + ENERGY_PER_TURN as i16).min(ENERGY_CAP) } else { ENERGY_PER_TURN as i16 };
                        self.stage = Stage::StartTurn;
                        // The fight's start, before the opening draw (the
                        // game's `atBattleStartPreDraw`): a `Draw` joins it.
                        if self.turn == 1 && self.combat_start_pre_draw() {
                            return;
                        }
                        // A relic's offer opened (Toolbox): it runs first.
                        if matches!(self.stage, Stage::RelicOffer { .. }) {
                            continue;
                        }
                        if (self.turn > 1 || turn1_pre_draw) && self.pre_draw_hooks() {
                            return;
                        }
                    } else {
                        self.stage = Stage::MonsterRolls { next: next + 1 };
                        if self.monsters[slot].alive() {
                            self.request_roll(slot);
                        }
                    }
                }
                Stage::StartTurn => {
                    self.stage = Stage::TurnStarted;
                    // Draws pre-draw hooks and `CardExhausted` hooks owed.
                    let mut n = DRAW_PER_TURN.saturating_add(std::mem::take(&mut self.owed_draw)).saturating_add(self.relic_draw());
                    if self.turn == 1 {
                        n += self.character.first_turn_draw();
                        // Innate cards start in the opening hand and count toward its draw.
                        let innate = self.opening_cards();
                        self.bottled = [None; 3];
                        let all = self.sees_order();
                        for &(c, k) in &innate {
                            // Frozen Eye: they are the known head.
                            for _ in 0..k {
                                if all {
                                    self.top.remove_known(c);
                                }
                            }
                            self.draw_mut().remove(c, k);
                            self.hand.add(c, k);
                            n = n.saturating_sub(k);
                        }
                        // The game draws them first: Confused rolls them too.
                        let cards: Vec<CardId> = innate.iter().flat_map(|&(c, k)| std::iter::repeat(c).take(k as usize)).collect();
                        self.queue_drawn_rolls(Hand::from_cards(&cards).view());
                    }
                    self.request_draw(n);
                }
                Stage::TurnStarted => {
                    self.stage = Stage::PlayerTurn;
                    // Turn 1 in the game's order: the post-draw hooks (where
                    // the start-of-combat relics sit), then the turn-start ones.
                    let late = self.turn == 1 && !turn1_pre_draw;
                    // The fight's start after the opening draw (the game's
                    // `atBattleStart`), before turn 1's post-draw hooks.
                    if (self.turn == 1 && self.run_hooks(Who::Player, Trigger::CombatStart))
                        || self.run_hooks(Who::Player, Trigger::OwnerTurnStartPostDraw)
                        || (late && self.run_hooks(Who::Player, Trigger::OwnerTurnStart))
                        || self.fire_exhausts(false)
                    {
                        return;
                    }
                }
            }
        }
    }

    /// The player's `CombatStartPreDraw` hooks, their `Draw`s owed to the
    /// opening draw. Returns whether the combat ended.
    fn combat_start_pre_draw(&mut self) -> bool {
        self.run_hooks_scaled(Who::Player, |h: &Hook| h.trigger == Trigger::CombatStartPreDraw, HookCtx::default(), 1, true, |_| true)
    }

    /// The player's pre-draw hooks with their `Draw`s owed to the turn's
    /// draw, then the `CardExhausted` hooks of what they exhausted (a draw
    /// owed the same way). Returns whether the combat ended.
    fn pre_draw_hooks(&mut self) -> bool {
        self.run_hooks_scaled(Who::Player, |h: &Hook| h.trigger == Trigger::OwnerTurnStart, HookCtx::default(), 1, true, |_| true) || self.fire_exhausts(true)
    }

    /// A potion's use is done: the monsters' block that waited for it lands.
    fn finish_potion(&mut self) {
        for slot in 0..MAX_MONSTERS {
            let b = std::mem::take(&mut self.deferred_block[slot]);
            if self.monsters[slot].alive() {
                self.monsters[slot].block = gained_block(self.monsters[slot].block, b);
            }
        }
    }

    /// Whether `card`, as played (`exhaust`: a card Havoc plays), exhausts
    /// once placed: not a Power, and it or a held rule power says so.
    fn would_exhaust(&self, card: CardId, exhaust: bool) -> bool {
        let d = self.binding.def(card);
        d.ty != CardType::Power && (exhaust || d.exhaust || self.exhausts_played(d.ty))
    }

    /// The chance a card that would exhaust as played goes to the discard
    /// pile instead: each held relic's `exhaust_save` rolls alone (Strange
    /// Spoon's 1 in 2); 0 with none.
    pub(crate) fn exhaust_save_chance(&self) -> f64 {
        let kept: f64 = self
            .player
            .relics
            .iter()
            .map(|(id, _)| id.rules().exhaust_save)
            .filter(|&(_, d)| d > 0)
            .map(|(n, d)| 1.0 - n as f64 / d as f64)
            .product();
        1.0 - kept
    }

    /// A replayed copy (`copy`) goes to no pile; a saved card (`saved`, the
    /// exhaust-save roll) goes to the discard pile instead of exhausting.
    fn finish_card(&mut self, card: CardId, copy: bool, exhaust: bool, saved: bool) {
        // Left over only when the card ended the combat.
        self.card_hp_losses = 0;
        for slot in 0..MAX_MONSTERS {
            let b = std::mem::take(&mut self.deferred_block[slot]);
            if self.monsters[slot].alive() {
                self.monsters[slot].block = gained_block(self.monsters[slot].block, b);
            }
        }
        let d = self.binding.def(card);
        if copy {
        } else if d.ty == CardType::Power {
            self.removed = self.removed.saturating_add(1);
        } else if !saved && (exhaust || d.exhaust || self.exhausts_played(d.ty)) {
            self.exhaust_card(card, 1);
        } else {
            self.discard_mut().add(card, 1);
        }
    }

    /// The player's `CombatWon` hooks, once the fight is won and before the
    /// combat-end heal (Meat on the Bone). Their effects are heals and
    /// counter changes only (checked at load): the stage is already `Over`,
    /// so nothing reacts.
    fn combat_won_hooks(&mut self) {
        self.player_hooks_outside(Trigger::CombatWon, false);
    }

    /// The player's HP dropped below 1: HP goes to 0 (the game's
    /// `currentHealth = 0`), then the first held potion with trigger
    /// `OwnerDied` is used up (Fairy in a Bottle), else the player's
    /// `OwnerDied` hooks may save them (Lizard Tail; docs/specs/would-die.md).
    /// Returns whether the player lives; if not, HP is as it was (below 0
    /// in no-death mode).
    fn save_from_death(&mut self) -> bool {
        let hp = self.player.hp;
        self.player.hp = 0;
        let potions = self.player.potions;
        if let Some(slot) = (0..potions.len()).find(|&i| CombatState::potion_spec(potions.id(i)).trigger == Some(Trigger::OwnerDied)) {
            let id = self.player.potions.remove(slot);
            let k = self.potion_scale(id);
            for e in CombatState::potion_spec(id).effects() {
                self.player_effect_outside(crate::potions::scaled_effect(*e, k), true);
            }
        } else {
            self.player_hooks_outside(Trigger::OwnerDied, true);
        }
        if self.player.hp >= 1 {
            return true;
        }
        self.player.hp = hp;
        false
    }

    /// The player's hooks on `trigger` outside a normal pass, relics first
    /// in order, then powers: `CombatWon`, and with `save` the `OwnerDied`
    /// hooks as the player would die, where a heal works from 0 HP and the
    /// later hooks don't run once the player's HP is 1 or more.
    fn player_hooks_outside(&mut self, trigger: Trigger, save: bool) {
        let ctx = HookCtx::default();
        for i in 0..self.player.relics.len() {
            for h in self.player.relics.id(i).hooks().iter().filter(|h| h.trigger == trigger) {
                if save && self.player.hp >= 1 {
                    return;
                }
                let holds = |c| self.relic_condition_holds(self.player.relics.counter(i), c, ctx);
                if !holds(h.condition) || !holds(h.also) {
                    continue;
                }
                for e in h.effects {
                    match *e {
                        Effect::SetCounter(n) => self.player.relics.set_counter(i, n),
                        Effect::AddCounter(n) => {
                            let c = self.player.relics.counter(i).saturating_add(n);
                            self.player.relics.set_counter(i, c)
                        }
                        e => self.player_effect_outside(e, save),
                    }
                }
            }
        }
        let binding = self.binding;
        for &p in binding.powers_in_play() {
            for h in binding.hooks(p).iter().filter(|h| h.trigger == trigger) {
                if save && self.player.hp >= 1 {
                    return;
                }
                let stacks = self.player.powers.get(p);
                if stacks <= 0 || !self.condition_holds(Who::Player, h.condition, ctx) || !self.condition_holds(Who::Player, h.also, ctx) {
                    continue;
                }
                for e in h.effects {
                    self.player_effect_outside(e.scaled(stacks), save);
                }
            }
        }
    }

    /// One effect of `player_hooks_outside`; with `save` a heal is a save's.
    fn player_effect_outside(&mut self, e: Effect, save: bool) {
        match e {
            Effect::Heal(n) if save => self.save_heal(n),
            Effect::HealOf(a) if save => {
                let n = self.resolve(Who::Player, a);
                self.save_heal(n)
            }
            e => self.do_effect(Who::Player, &e, None),
        }
    }

    /// A save's heal: from the player's HP now (0) by at least 1 (both game
    /// classes floor `healAmt` at 1), up to max HP. It runs no bloodied
    /// hooks: `lost_hp` moves the bloodied state once, from before the loss.
    fn save_heal(&mut self, n: i16) {
        let n = self.player_heal(n.max(1));
        self.player.hp = self.player.hp.saturating_add(n).min(self.player.max_hp);
    }

    /// A heal of `n` HP for the player as the held relics change it, in
    /// list order (Magic Flower's `heal_scale` [3, 2]: the game's
    /// `onPlayerHeal`, `MathUtils.round(n * 1.5f)`, half rounded up).
    pub fn player_heal(&self, n: i16) -> i16 {
        let mut n = n.max(0) as i32;
        for (id, _) in self.player.relics.iter() {
            let (a, b) = id.heal_scale();
            if (a, b) != (1, 1) {
                n = (2 * n * a as i32 + b as i32) / (2 * b as i32);
            }
        }
        n.min(i16::MAX as i32) as i16
    }

    /// The combat-end heal as the held relics change it (`player_heal` of
    /// `win_heal`; the game scales each source alone, which differs only
    /// when two odd amounts are summed: none in Act 1 content).
    pub fn win_heal_scaled(&self) -> i16 {
        self.player_heal(self.win_heal)
    }

    /// Ends the combat if someone died. Returns whether it is over.
    pub(crate) fn check_over(&mut self) -> bool {
        if self.is_over() {
            return true;
        }
        let lost = self.player_dead();
        // An escape ends the fight as won (the game's `endBattle`).
        let won = !lost && (self.escaped || self.living_slots().next().is_none());
        if !lost && !won {
            return false;
        }
        let card_left = match self.stage {
            Stage::PlayingCard { card, target, next, more, .. } => {
                self.finish_card(card, more.copy, more.exhaust, more.save == Some(true));
                Some((card, target, next))
            }
            _ => None,
        };
        let potion_ended = matches!(self.stage, Stage::UsingPotion { .. });
        if potion_ended {
            self.finish_potion();
        }
        // Cards still waiting to be played go to the discard pile.
        while let Some(q) = self.top_queue.pop_front() {
            self.discard_mut().add(q.card, 1);
        }
        self.pending = None;
        self.stage = Stage::Over { won };
        // The card that won it raises max HP first, inside the action that
        // killed (Feed: `FeedAction`'s `increaseMaxHp`), before `endBattle`'s
        // hooks and heals.
        if let (true, Some((card, target, next))) = (won, card_left) {
            self.card_rows_after_win(card, target, next, true);
        }
        if won && !self.no_death {
            let hp = self.player.hp;
            self.combat_won_hooks();
            self.player.hp = (self.player.hp + self.win_heal_scaled()).min(self.player.max_hp);
            self.won_healed = Untracked(self.player.hp - hp);
            // The potion that ended the fight still gets its queued heal
            // (Toy Ornithopter; the game's `clearPostCombatActions` keeps a
            // `HealAction`), after `endBattle`'s heals.
            if potion_ended {
                self.player_hooks_outside(Trigger::OwnerUsedPotion, false);
            }
        }
        // So does the card that won it: its rows left run their heals only
        // (Reaper's `HealAction`, kept the same way).
        if let (true, Some((card, target, next))) = (won, card_left) {
            self.card_rows_after_win(card, target, next, false);
        }
        self.dealt = 0;
        // Triggers never fire after the combat: a finished state holds no
        // unfired exhausts or owed draws (and encodes as before C2).
        self.unfired_exhausts = 0;
        self.owed_draw = 0;
        self.unfired_draws = 0;
        self.unfired_curse_draws = 0;
        self.block_broken = [0; MAX_MONSTERS];
        // Nor owed random work (a hook pass that ended it leaves no run).
        self.owed.clear();
        self.owed_late.clear();
        // Nor marks: a finished state is the same with or without them.
        self.free_in_hand.clear();
        self.turn_costs.clear();
        true
    }

    /// The heals (`max_hp`: the max HP gains) of `card`'s rows from `next`
    /// on, after the effect that won the fight: through the relics
    /// (`onPlayerHeal`, still in combat), up to max HP, with no hooks; the
    /// rows' other effects don't run. A max HP gain heals as much.
    fn card_rows_after_win(&mut self, card: CardId, target: Option<u8>, next: u8, max_hp: bool) {
        let def = self.binding.def(card);
        let mut i = next as usize;
        while let Some(at) = def.effect_at(i) {
            if at.row_start && !self.condition_holds(Who::Player, at.condition, HookCtx { card: Some(card), target, drawn: None }) {
                i = at.row_end;
                continue;
            }
            let n = match at.effect {
                Effect::Heal(n) if !max_hp => n,
                Effect::HealOf(a) if !max_hp => self.resolve(Who::Player, a),
                Effect::GainMaxHp(n) if max_hp && n > 0 => {
                    self.player.max_hp = self.player.max_hp.saturating_add(n);
                    n
                }
                _ => 0,
            };
            if n > 0 && self.player.hp > 0 {
                self.player.hp = self.player.hp.saturating_add(self.player_heal(n)).min(self.player.max_hp);
            }
            i += 1;
        }
    }

    /// The player is dead (never in no-death mode).
    fn player_dead(&self) -> bool {
        !self.no_death && self.player.hp <= 0
    }

    /// The lowest HP `who` can drop to: 0, but unbounded for the player in
    /// no-death mode.
    fn hp_floor(&self, who: Who) -> i16 {
        if self.no_death && who == Who::Player {
            i16::MIN / 2
        } else {
            0
        }
    }

    fn end_turn(&mut self) {
        self.turn_ending = true;
        // The game's first queued pass (`callEndOfTurnActions`): the
        // relics' `onPlayerEndTurn`, then the powers'
        // `atEndOfTurnPreEndTurnCards` (`Hook::before_hand`).
        if !self.run_turn_end_pass(true) {
            self.end_turn_from(1);
        }
        self.turn_ending = false;
    }

    /// One of the player's two queued End Turn passes (`Hook::before_hand`
    /// says which): its relics' hooks, then its powers', those that act
    /// first (`Hook::first`) ahead of the rest, the last called first.
    /// Returns whether the combat ended.
    fn run_turn_end_pass(&mut self, before_hand: bool) -> bool {
        let t = Trigger::OwnerTurnEnd;
        self.run_queued_player(t, false, true, before_hand) || self.run_queued_player(t, true, true, before_hand) || self.run_queued_player(t, true, false, before_hand) || self.run_queued_player(t, false, false, before_hand)
    }

    /// End Turn from `part` on (`Stage::EndingTurn`): before each part, work
    /// a hook owed is paid first (the game queued it ahead of what follows).
    /// The parts in order: 1 the hand's turn-end cards, 3 the powers'
    /// `atEndOfTurn` pass, 4 the discard and its exhausts, 2 the monsters.
    fn end_turn_from(&mut self, part: u8) {
        self.turn_ending = true;
        let rank = |p: u8| match p {
            1 => 0,
            3 => 1,
            4 => 2,
            _ => 3,
        };
        let at = rank(part);
        if at <= 0 && (self.pause_for_owed(1) || self.end_turn_cards()) {
            return;
        }
        // The game's second pass (`AbstractRoom.endTurn`): the powers'
        // `atEndOfTurn` once the hand's cards are played.
        if at <= 1 && (self.pause_for_owed(3) || self.run_turn_end_pass(false)) {
            return;
        }
        if at <= 2 && (self.pause_for_owed(4) || self.end_turn_hand()) {
            return;
        }
        if self.pause_for_owed(2) {
            return;
        }
        self.monsters_turn();
    }

    /// With work owed: End Turn waits at `part` while it is paid.
    fn pause_for_owed(&mut self, part: u8) -> bool {
        if self.owed.is_empty() || self.is_over() {
            return false;
        }
        self.stage = Stage::EndingTurn { part };
        self.run();
        true
    }

    /// The hand's turn-end cards (Burn), one copy at a time: the game plays
    /// each (`triggerOnEndOfTurnForPlayingCard`) once the first pass's work
    /// is done. Returns whether the combat ended.
    fn end_turn_cards(&mut self) -> bool {
        for (card, n) in self.hand.iter().collect::<Vec<_>>() {
            for _ in 0..n {
                for e in self.binding.def(card).turn_end {
                    self.do_effect(Who::Player, e, None);
                    if self.check_over() {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// The hand at turn end: the discard and the exhausts' hooks. Returns
    /// whether the combat ended.
    fn end_turn_hand(&mut self) -> bool {
        // Every mark ends with the turn (the game's `endTurn` resets every
        // card's cost for the turn), retained cards' too.
        self.free_in_hand.clear();
        self.turn_costs.clear();
        // Runic Pyramid keeps the rest of the hand; a card that acted at
        // turn end (Burn) was played and goes to the discard pile.
        let keeps_hand = self.player.relics.iter().any(|(id, _)| id.rules().keeps_hand);
        let hand = std::mem::take(&mut self.hand);
        for (card, n) in hand.iter() {
            let d = self.binding.def(card);
            if d.retain {
                self.hand.add(card, n);
            } else if d.ethereal {
                self.exhaust_card(card, n);
            } else if keeps_hand && d.turn_end.is_empty() {
                self.hand.add(card, n);
            } else {
                self.discard_mut().add(card, n);
            }
        }
        // Exhausts at turn end (ethereal, the player's turn-end hooks) fire
        // before the monsters act; their draws are owed to the next turn.
        self.fire_exhausts(true)
    }

    /// The game's `turnHasEnded`: true from the monsters' turn to the
    /// round's end (`monsters_acting`). Vulnerable and NoBlock a monster
    /// applies skip their first round end only then.
    pub fn turn_has_ended(&self) -> bool {
        self.monsters_acting
    }

    /// The monsters' turn and the round's end, then the next round's rolls.
    fn monsters_turn(&mut self) {
        if self.monsters_turn_open() {
            self.monsters_turn_from(0, 0, false);
        } else {
            self.monsters_acting = false;
        }
    }

    /// The monsters' turn from monster `slot`'s effect `next` (0, 0 at its
    /// start; a `Stage::MonsterActing` pause resumes it, `resumed`) through
    /// the round's end, then the next round's rolls.
    fn monsters_turn_from(&mut self, slot: usize, next: usize, resumed: bool) {
        self.monsters_acting = true;
        let goes_on = match self.monsters_act_from(slot, next, resumed) {
            // Paused at `Stage::MonsterActing`: at rest until it resumes.
            None => {
                self.monsters_acting = false;
                return;
            }
            Some(false) => false,
            Some(true) => self.monsters_round_end(),
        };
        self.monsters_acting = false;
        if goes_on {
            self.stage = Stage::MonsterRolls { next: 0 };
            self.run();
        }
    }

    /// The monsters' turn's opening: blocks broken at the player's turn
    /// end, the monsters' block loss and their turn-start hooks. False when
    /// the combat ended.
    fn monsters_turn_open(&mut self) -> bool {
        // Blocks the player's turn end broke (Combust), before the
        // monsters' block goes.
        if self.fire_block_broken() {
            return false;
        }
        // Their block goes; block queued behind that loss while the turn
        // ended (`defers_queued_block`) lands now.
        for (m, b) in self.monsters.iter_mut().zip(self.deferred_block.iter_mut()) {
            let b = std::mem::take(b);
            if m.alive() {
                m.block = b.min(BLOCK_CAP);
            }
        }
        self.turn_ending = false;
        self.monsters_acting = true;
        // Every monster's turn-start hooks (Poison) run before any acts.
        for slot in 0..MAX_MONSTERS {
            if self.monsters[slot].alive() && self.run_hooks_with(Who::Monster(slot as u8), |h: &Hook| h.trigger.is_turn_start(), HookCtx::default()) {
                return false;
            }
        }
        true
    }

    /// The other living monsters `slot`'s `BlockAlly` may pick (the game's
    /// `GainBlockRandomMonsterAction`: not the source, not showing an
    /// Escape move, not dying), in slot order.
    pub(crate) fn ally_block_candidates(&self, slot: usize) -> Vec<usize> {
        // A hidden candidate (Runic Dome) escapes when its roll can only
        // give an Escape (`hidden_escape_open` rolls a mixed one first).
        let esc = |mv: &MoveDef| mv.effects.iter().any(|e| matches!(e, Effect::Escape));
        let escapes = |i: usize| {
            let moves = self.monsters[i].def().moves;
            self.intent_distribution(i).iter().all(|&(m, _)| moves.get(m as usize).is_some_and(esc))
        };
        self.living_slots().filter(|&i| i != slot && !escapes(i)).collect()
    }

    /// The monsters' moves, from monster `from_slot`'s effect `from_next` on
    /// (`resumed` when it goes on from a pause). `None` when it paused at a
    /// `BlockAlly` pick (`Stage::MonsterActing`), else whether the combat
    /// goes on.
    fn monsters_act_from(&mut self, from_slot: usize, from_next: usize, resumed: bool) -> Option<bool> {
        for slot in from_slot..MAX_MONSTERS {
            let m = &self.monsters[slot];
            if !m.alive() {
                continue;
            }
            // A hidden roll a card narrowed to one move is set (no event).
            if self.move_hidden(slot) {
                if let [(mv, _)] = self.intent_distribution(slot)[..] {
                    self.set_monster_move(slot, mv);
                }
            }
            let m = &self.monsters[slot];
            // Runic Dome: its move rolls as it acts (allies as at the
            // game's roll, `HIDDEN_ALLIES`), then a rolled attack amount
            // not seen yet. A player's draw already pending resolves first.
            if self.move_hidden(slot) || (self.intent_hidden[slot] & HIDDEN_ROLLED != 0 && m.intent_def().is_some_and(|d| d.effects.contains(&Effect::RolledAttack))) {
                if !(resumed && slot == from_slot) {
                    self.note_allies(slot);
                }
                if self.pending.is_none() {
                    let ev = if self.move_hidden(slot) { ChanceEvent::MonsterMove { slot: slot as u8 } } else { ChanceEvent::RolledAmount { slot: slot as u8 } };
                    self.pending = Some(ev);
                }
                self.stage = Stage::MonsterActing { slot: slot as u8, next: 0 };
                return None;
            }
            let m = &self.monsters[slot];
            // Monsters spawned this turn (split slimes) have no move yet.
            let Some(mv) = m.intent_def() else { continue };
            let used = m.intent();
            let first = if slot == from_slot { from_next } else { 0 };
            if !(resumed && slot == from_slot) {
                self.note_allies(slot);
            }
            for (i, e) in mv.effects.iter().enumerate().skip(first) {
                // The game's `GainBlockRandomMonsterAction`: the block lands
                // at once, before any later monster acts. Two or more
                // candidates pause the turn on the pick; a player's draw
                // already pending (Runic Cube) resolves first, then this
                // effect runs again.
                if let Effect::BlockAlly(n) = *e {
                    // A hidden ally that may or may not escape rolls first.
                    if let Some(k) = self.hidden_escape_open(slot) {
                        if self.pending.is_none() {
                            self.pending = Some(ChanceEvent::MonsterMove { slot: k as u8 });
                        }
                        self.stage = Stage::MonsterActing { slot: slot as u8, next: i as u8 };
                        return None;
                    }
                    let to = match self.ally_block_candidates(slot)[..] {
                        [] => slot,
                        [a] => a,
                        _ => {
                            let again = self.pending.is_some();
                            if !again {
                                self.pending = Some(ChanceEvent::AllyBlock { slot: slot as u8 });
                            }
                            self.stage = Stage::MonsterActing { slot: slot as u8, next: (i + !again as usize) as u8 };
                            return None;
                        }
                    };
                    self.monsters[to].block = gained_block(self.monsters[to].block, n);
                    continue;
                }
                self.do_effect(Who::Monster(slot as u8), e, None);
                if self.check_over() {
                    return Some(false);
                }
            }
            self.dealt = 0;
            self.after_move(slot, used);
            // Blocks broken during the move (Thorns) before the next acts.
            if self.fire_block_broken() {
                return Some(false);
            }
            // The one chance a monster's move may leave: the player's draw
            // from an HP-loss hook (Runic Cube, Centennial Puzzle). Draws
            // add up (`request_draw`) and resolve once this turn's passes
            // end, before the monsters roll; the game draws at once, so a
            // status a later move puts in the discard pile can be
            // reshuffled into that draw here and not in the game.
            debug_assert!(
                matches!(self.pending, None | Some(ChanceEvent::Draw { .. }) | Some(ChanceEvent::Order { then: crate::chance::OrderThen::Draw(_) })),
                "monster moves must not wait on chance other than a player's draw"
            );
        }
        Some(true)
    }

    /// Runic Dome: a living other monster than `slot` whose hidden roll
    /// may give an Escape and may not (a `BlockAlly` pick reads it).
    fn hidden_escape_open(&self, slot: usize) -> Option<usize> {
        self.living_slots().filter(|&i| i != slot && self.move_hidden(i)).find(|&i| {
            let moves = self.monsters[i].def().moves;
            let esc: Vec<bool> = self.intent_distribution(i).iter().map(|&(m, _)| moves.get(m as usize).is_some_and(|d| d.effects.iter().any(|e| matches!(e, Effect::Escape)))).collect();
            esc.iter().any(|&x| x) && !esc.iter().all(|&x| x)
        })
    }

    /// Whether a card's `TargetIntendsAttack` on hidden monster `t` needs a
    /// reveal: its roll can give an attack and can give none, and no card
    /// revealed which yet.
    pub(crate) fn intent_class_unknown(&self, t: usize) -> bool {
        if t >= MAX_MONSTERS || !self.move_hidden(t) || self.intent_hidden[t] & HIDDEN_CLASS != 0 {
            return false;
        }
        let moves = self.monsters[t].def().moves;
        let att: Vec<bool> = self.move_distribution(t).iter().map(|&(m, _)| moves.get(m as usize).is_some_and(|d| is_attack(d))).collect();
        att.iter().any(|&x| x) && !att.iter().all(|&x| x)
    }

    /// Monster `slot` is about to use its move: for a kind whose pattern
    /// reads `Allies`, whether another monster lives now (the game's
    /// `GremlinTsundere` counts at its move: `allies_at_move`).
    fn note_allies(&mut self, slot: usize) {
        if !self.monsters[slot].def().pattern.iter().any(|r| r.when.contains(&crate::monsters::PatCond::Allies)) {
            return;
        }
        let bit = 1u8 << slot;
        if self.living_slots().any(|i| i != slot) {
            self.allies_at_move |= bit;
        } else {
            self.allies_at_move &= !bit;
        }
    }

    /// The monsters' turn-end passes and the round's end. False when the
    /// combat ended.
    fn monsters_round_end(&mut self) -> bool {
        // The game queues the monsters' turn-end hooks and the round's end
        // in one pass: the hooks that act first (`Hook::first`) come before
        // all the rest, the last called first: the monsters' RoundEnd ones,
        // the player's, then the monsters' OwnerTurnEnd ones.
        for slot in (0..MAX_MONSTERS).rev() {
            if self.monsters[slot].alive() && self.run_queued(Who::Monster(slot as u8), Trigger::RoundEnd, false, true) {
                return false;
            }
        }
        if self.run_queued(Who::Player, Trigger::RoundEnd, false, true) || self.run_queued(Who::Player, Trigger::RoundEnd, true, true) {
            return false;
        }
        for slot in (0..MAX_MONSTERS).rev() {
            if self.monsters[slot].alive() && self.run_queued(Who::Monster(slot as u8), Trigger::OwnerTurnEnd, false, true) {
                return false;
            }
        }
        // Turn-end hooks (Metallicize, Ritual) once every monster has acted.
        for slot in 0..MAX_MONSTERS {
            if self.monsters[slot].alive() && self.run_hooks(Who::Monster(slot as u8), Trigger::OwnerTurnEnd) {
                return false;
            }
        }
        if self.fire_block_broken() {
            return false;
        }
        // The round's end: the debuff countdowns (`RoundEnd` hooks), then
        // what was skipped this round is skipped no longer. An entity holding
        // none of the powers with such a hook has nothing to run.
        if self.has_round_end(Who::Player) && self.run_hooks(Who::Player, Trigger::RoundEnd) {
            return false;
        }
        for slot in 0..MAX_MONSTERS {
            let who = Who::Monster(slot as u8);
            if self.monsters[slot].alive() && self.has_round_end(who) && self.run_hooks(who, Trigger::RoundEnd) {
                return false;
            }
        }
        self.player.powers.clear_round_flags();
        for m in self.monsters.iter_mut().filter(|m| m.alive()) {
            m.powers.clear_round_flags();
        }
        true
    }

    /// The player played `card` on `target`: each living monster's
    /// `CardPlayed by Opponent` hooks in slot order, before the card's
    /// effects. Returns whether the combat ended.
    fn card_played(&mut self, card: CardId, target: Option<u8>) -> bool {
        let ctx = HookCtx { card: Some(card), target, drawn: None };
        for slot in 0..MAX_MONSTERS {
            let who = Who::Monster(slot as u8);
            let fires = |h: &Hook| h.trigger == Trigger::CardPlayed { by: Side::Opponent } && !h.after_card();
            if self.monsters[slot].alive() && self.run_hooks_with(who, fires, ctx) {
                return true;
            }
        }
        false
    }

    /// The card in play resolved: the player's `OwnerLostHp` hooks for the HP
    /// it cost (see `card_hp_losses`), then the player's `CardPlayed by
    /// Owner` hooks (Rage), then each living monster's damage hooks for the
    /// card (Sharp Hide, `Hook::after_card`). The game queues Rage's block
    /// ahead of the card's actions but computed the card's damage already
    /// (Body Slam), so after the card is the same. Returns whether the
    /// combat ended.
    fn card_resolved(&mut self, card: CardId, target: Option<u8>) -> bool {
        for _ in 0..std::mem::take(&mut self.card_hp_losses) {
            let fires = |h: &Hook| matches!(h.trigger, Trigger::OwnerLostHp { from: f } if f.matches(HpLossFrom::Card));
            if self.run_hooks_with(Who::Player, fires, HookCtx::default()) {
                return true;
            }
        }
        let ctx = HookCtx { card: Some(card), target, drawn: None };
        if self.run_hooks_with(Who::Player, |h: &Hook| h.trigger == Trigger::CardPlayed { by: Side::Owner }, ctx) {
            return true;
        }
        // HP those hooks cost (Blue Candle's 1 on a curse) fires the same hooks.
        for _ in 0..std::mem::take(&mut self.card_hp_losses) {
            let fires = |h: &Hook| matches!(h.trigger, Trigger::OwnerLostHp { from: f } if f.matches(HpLossFrom::Card));
            if self.run_hooks_with(Who::Player, fires, HookCtx::default()) {
                return true;
            }
        }
        for slot in 0..MAX_MONSTERS {
            let who = Who::Monster(slot as u8);
            if self.monsters[slot].alive() && self.run_hooks_with(who, Hook::after_card, ctx) {
                return true;
            }
        }
        false
    }

    /// The turn-start leaf (docs/specs/turn-start-leaf.md): while the
    /// player's turn-start hooks are still to run (a monster's roll or the
    /// turn's draw pending), a copy with those hooks run, keeping only the
    /// effects that need no chance and don't read the undrawn hand. `None`
    /// when the player holds no turn-start hook (on a power or a relic) or
    /// the turn has started.
    /// While a monster's roll is pending, hooks of both triggers are still
    /// to run; once the turn started (a chance event at `StartTurn` among
    /// the pre-draw hooks, or the draw pending at `TurnStarted`) only the
    /// post-draw ones (docs/specs/turn-start-draw.md).
    pub fn turn_start_leaf(&self) -> Option<CombatState> {
        let rolls = matches!(self.stage, Stage::MonsterRolls { .. });
        let started = matches!(self.stage, Stage::StartTurn | Stage::TurnStarted) && self.pending.is_some();
        if !(rolls || started) || self.is_over() {
            return None;
        }
        let ticks = |h: &Hook| if rolls { h.trigger.is_turn_start() } else { h.trigger == Trigger::OwnerTurnStartPostDraw };
        let pw = &self.player.powers;
        if !self.binding.powers_in_play().iter().any(|&p| pw.get(p) > 0 && self.binding.hooks(p).iter().any(ticks))
            && !self.player.relics.iter().any(|(id, _)| id.hooks().iter().any(ticks))
        {
            return None;
        }
        let kept = |e: &Effect| {
            matches!(
                e,
                Effect::Damage { .. }
                    | Effect::PlainDamage { .. }
                    | Effect::Block(_)
                    | Effect::GainEnergy(_)
                    | Effect::LoseHp(_)
                    | Effect::Apply { .. }
                    | Effect::RemoveSelf
                    | Effect::ReduceSelf(_)
                    | Effect::SetCounter(_)
                    | Effect::AddCounter(_)
            )
        };
        let mut t = self.clone();
        t.run_hooks_kept(Who::Player, ticks, HookCtx::default(), kept);
        Some(t)
    }

    /// The projected leaf (docs/specs/projected-leaf.md): a copy in which,
    /// for the player and then each living monster, every once-a-turn hook
    /// (either turn start, `OwnerTurnEnd`) that neither removes nor reduces
    /// its power runs its `Apply` of Strength or Dexterity to its owner `k`
    /// more times; the hooks' other effects are dropped.
    pub fn projected_leaf(&self, k: u8) -> CombatState {
        self.projected_leaf_with(k, false)
    }

    /// `projected_leaf(k)`; with `debuffs` (docs/specs/recurring-debuff-leaf.md)
    /// a living monster's once-a-turn hooks also run their `Apply` of Weak,
    /// Frail or Vulnerable to the player k more times.
    pub fn projected_leaf_with(&self, k: u8, debuffs: bool) -> CombatState {
        let mut t = self.clone();
        if k == 0 || t.is_over() {
            return t;
        }
        let fires = |h: &Hook| {
            (h.trigger.is_turn_start() || h.trigger == Trigger::OwnerTurnEnd)
                && !h.effects.iter().any(|e| matches!(e, Effect::RemoveSelf | Effect::ReduceSelf(_)))
        };
        let keep = |e: &Effect| matches!(e, Effect::Apply { power: Power::Strength | Power::Dexterity, target: Target::Me, .. });
        let keep_monster = |e: &Effect| {
            keep(e)
                || (debuffs
                    && matches!(
                        e,
                        Effect::Apply {
                            power: Power::Weak | Power::Frail | Power::Vulnerable,
                            target: Target::AllOpponents | Target::Opponent,
                            ..
                        }
                    ))
        };
        t.run_hooks_scaled(Who::Player, fires, HookCtx::default(), k as i16, false, keep);
        for slot in 0..MAX_MONSTERS {
            if t.monsters[slot].alive() {
                t.run_hooks_scaled(Who::Monster(slot as u8), fires, HookCtx::default(), k as i16, false, keep_monster);
            }
        }
        t
    }

    /// Whether a hook's effect `e` waits in `owed` (docs/specs/blocked-relics.md
    /// step 5): a random effect a hook may hold (checked at load), and a
    /// `Draw` while work is owed, so it comes after that work as the game
    /// queues it.
    fn owes(&self, owner: Who, e: &Effect) -> bool {
        match e {
            Effect::MakeRandom { .. } | Effect::ZeroCostRandom | Effect::ZeroCostRandomTurn | Effect::UpgradeRandom => true,
            // A monster's random opponent is the player: no roll.
            Effect::PlainDamage { target: Target::RandomOpponent, .. } => owner == Who::Player,
            Effect::Draw(_) => !self.owed.is_empty(),
            Effect::PlayTop { .. } => true,
            _ => false,
        }
    }

    /// A hook's effect `e` (one `owes` accepts), `times` over (its stacks
    /// and scale), joins `owed`; while a relic's pick or offer is open it
    /// waits for that relic's hook to finish.
    fn owe(&mut self, owner: Who, e: Effect, times: i16) {
        // A take goes behind the turn start's other work (a monster has no
        // draw pile: nothing).
        if let Effect::PlayTop { n, exhaust } = e {
            if owner == Who::Player {
                self.owed_late.push(OwedKind::Top { exhaust }, (n as i16).saturating_mul(times).clamp(0, u8::MAX as i16) as u8, false);
            }
            return;
        }
        let wait = matches!(self.stage, Stage::RelicPick { .. } | Stage::RelicOffer { .. });
        let clamp = |n: i16| n.clamp(0, u8::MAX as i16) as u8;
        let (kind, n) = match e {
            Effect::MakeRandom { pool, ty, n, pile, zero_cost, free, .. } => {
                // No pool for the fight's character ("Class"): nothing to make.
                let Some(pool) = crate::registry::fight_pool(pool, self.character) else { return };
                let k = self.resolve(owner, n).max(0).saturating_mul(times);
                (OwedKind::Make { pool, ty, pile, zero_cost, free }, clamp(k))
            }
            Effect::ZeroCostRandom => (OwedKind::ZeroCost, clamp(times)),
            Effect::ZeroCostRandomTurn => (OwedKind::FreeTurn, clamp(times)),
            Effect::UpgradeRandom => (OwedKind::Upgrade, clamp(times)),
            Effect::Draw(n) => (OwedKind::Draw, clamp((n as i16).saturating_mul(times))),
            Effect::PlainDamage { amount, .. } => (OwedKind::Hit { amount: amount.saturating_mul(times) }, 1),
            e => unreachable!("{e:?} isn't owed work"),
        };
        self.owed.push(kind, n, wait);
    }

    /// Pays the front of `owed`: one roll or pick (a `Draw`, all its cards)
    /// as its chance event, or at once when it has one outcome.
    fn pay_owed(&mut self) {
        let e = self.owed.front().expect("owed work");
        match e.kind {
            OwedKind::Make { pool, ty, pile, zero_cost, free } => {
                self.owed.take_front(1);
                if !crate::registry::pool_cards(&self.binding, pool, ty).is_empty() {
                    self.pending = Some(ChanceEvent::MakeRandom { pool, ty, pile, zero_cost, free, up: false });
                }
            }
            OwedKind::ZeroCost => {
                self.owed.take_front(1);
                self.request_zero_cost();
            }
            OwedKind::FreeTurn => {
                self.owed.take_front(1);
                self.request_free_turn();
            }
            OwedKind::Upgrade => {
                self.owed.take_front(1);
                self.request_upgrade_random();
            }
            OwedKind::Draw => {
                self.owed.take_front(e.n);
                self.request_draw(e.n);
            }
            OwedKind::Hit { amount } => {
                self.owed.take_front(1);
                self.request_plain_hit(amount);
            }
            OwedKind::Insert { card } => {
                self.owed.take_front(1);
                self.request_insert(card);
            }
            OwedKind::Top { .. } => unreachable!("a late take is paid from owed_late"),
        }
    }

    /// Runs `owner`'s hooks for `trigger` in power-kind order, skipping
    /// powers marked `just_applied` and the hooks that act first
    /// (`run_queued`). Returns whether the combat ended.
    fn run_hooks(&mut self, owner: Who, trigger: Trigger) -> bool {
        self.run_hooks_with(owner, |h: &Hook| h.trigger == trigger && !h.first, HookCtx::default())
    }

    /// One part of a pass the game queues (`Hook::first`): `owner`'s
    /// `trigger` hooks from its relics (`relics`) or from its powers, either
    /// those that act first (`first`: the last listed first, as the game's
    /// `addToTop` stacks them) or the rest, in order. Returns whether the
    /// combat ended.
    fn run_queued(&mut self, owner: Who, trigger: Trigger, relics: bool, first: bool) -> bool {
        self.run_queued_in(owner, trigger, relics, first, |_: &Hook| true)
    }

    /// `run_queued` for the player's `trigger` hooks in one End Turn pass
    /// (`Hook::before_hand` equal to `before_hand`).
    fn run_queued_player(&mut self, trigger: Trigger, relics: bool, first: bool, before_hand: bool) -> bool {
        self.run_queued_in(Who::Player, trigger, relics, first, move |h: &Hook| h.before_hand == before_hand)
    }

    /// `run_queued` for the hooks `stage` also lets through.
    fn run_queued_in(&mut self, owner: Who, trigger: Trigger, relics: bool, first: bool, stage: impl Fn(&Hook) -> bool) -> bool {
        let fires = |h: &Hook| h.trigger == trigger && h.first == first && stage(h);
        let all = |_: &Effect| true;
        if relics {
            owner == Who::Player && !self.player.relics.is_empty() && self.run_relic_hooks(&fires, HookCtx::default(), 1, false, &all, first)
        } else {
            let held = self.powers(owner).held_mask();
            self.run_power_hooks(owner, held, &fires, HookCtx::default(), 1, false, &all, first)
        }
    }

    /// `run_hooks` for every hook whose trigger `fires`, checking each
    /// hook's condition against `ctx`. A monster's `Block` while a card is in
    /// play waits for the card to finish (Curl Up).
    fn run_hooks_with(&mut self, owner: Who, fires: impl Fn(&Hook) -> bool, ctx: HookCtx) -> bool {
        self.run_hooks_kept(owner, fires, ctx, |_| true)
    }

    /// `run_hooks_with`, running only the hook effects `keep` accepts.
    fn run_hooks_kept(&mut self, owner: Who, fires: impl Fn(&Hook) -> bool, ctx: HookCtx, keep: impl Fn(&Effect) -> bool) -> bool {
        self.run_hooks_scaled(owner, fires, ctx, 1, false, keep)
    }

    /// `run_hooks_kept` with amounts multiplied by `times` as well as the
    /// stacks; with `owe_draws`, a `Draw` is added to the next turn's draw.
    fn run_hooks_scaled(&mut self, owner: Who, fires: impl Fn(&Hook) -> bool, ctx: HookCtx, times: i16, owe_draws: bool, keep: impl Fn(&Effect) -> bool) -> bool {
        // A pack power applied during this pass (a hook's ApplyPack, a
        // relic's included) first fires on the next one: a cycle moves one
        // step per trigger (Pen Nib's power isn't spent by the Attack that
        // gave it; docs/specs/fight-vocabulary.md).
        let held = self.powers(owner).held_mask();
        // The player's relics first, in order (docs/specs/relic-entity.md).
        if owner == Who::Player && !self.player.relics.is_empty() && self.run_relic_hooks(&fires, ctx, times, owe_draws, &keep, false) {
            return true;
        }
        self.run_power_hooks(owner, held, &fires, ctx, times, owe_draws, &keep, false)
    }

    /// The powers' part of `run_hooks_scaled`, in power-kind order or,
    /// with `rev`, from the last; `held` is the owner's held mask when the
    /// pass began.
    #[allow(clippy::too_many_arguments)]
    fn run_power_hooks(&mut self, owner: Who, held: u64, fires: &impl Fn(&Hook) -> bool, ctx: HookCtx, times: i16, owe_draws: bool, keep: &impl Fn(&Effect) -> bool, rev: bool) -> bool {
        let binding = self.binding;
        for (_, &p) in ordered(binding.powers_in_play(), rev) {
            let stacks = self.powers(owner).get(p);
            if stacks <= 0 || self.powers(owner).just_applied(p) || (p as usize >= crate::powers::NUM_OFFICIAL_POWERS && held & (1u64 << p as u32) == 0) {
                continue;
            }
            'hooks: for (_, h) in ordered(binding.hooks(p), rev).filter(|(_, h)| fires(h)) {
                if !self.condition_holds(owner, h.condition, ctx) || !self.condition_holds(owner, h.also, ctx) {
                    continue;
                }
                for e in h.effects.iter().filter(|e| keep(e)) {
                    // Each effect scales by the stacks it sees, so a hook's
                    // effects act in their written order; a power that is
                    // gone does nothing more this pass.
                    let stacks = self.powers(owner).get(p);
                    if stacks <= 0 {
                        break 'hooks;
                    }
                    let stacks = stacks * times;
                    match (*e, owner, self.stage) {
                        (Effect::RemoveSelf, ..) => self.powers_mut(owner).clear(p),
                        (Effect::Draw(n), Who::Player, _) if owe_draws => {
                            self.owed_draw = self.owed_draw.saturating_add((n as i16 * stacks).clamp(0, u8::MAX as i16) as u8)
                        }
                        // Raw block (the game's GainBlockAction): no Dexterity or Frail.
                        (Effect::Block(n), Who::Player, _) => self.add_block(Who::Player, n * stacks),
                        (Effect::ReduceSelf(n), ..) => self.powers_mut(owner).add(p, -n),
                        (Effect::Block(n), Who::Monster(slot), Stage::PlayingCard { .. } | Stage::UsingPotion { .. }) => {
                            self.deferred_block[slot as usize] = self.deferred_block[slot as usize].saturating_add(n * stacks)
                        }
                        // The hook's HP loss source (Poison's: whoever poisoned
                        // the owner, `Any`).
                        (Effect::LoseHp(n), ..) if h.hp_loss != HpLossFrom::Card => self.lose_hp(owner, n * stacks, h.hp_loss),
                        (e, ..) if self.owes(owner, &e) => self.owe(owner, e, stacks),
                        (e, ..) => self.do_effect(owner, &e.scaled(stacks), ctx.target),
                    }
                    if self.check_over() {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// The player's relics' `Shuffled` hooks, once per shuffle (two
    /// shuffles run them twice: Sundial's counter steps through 3).
    pub(crate) fn fire_shuffled(&mut self) {
        if !self.player.relics.is_empty() {
            self.run_relic_hooks(&|h: &Hook| h.trigger == Trigger::Shuffled, HookCtx::default(), 1, false, &|_: &Effect| true, false);
        }
    }

    /// The player's relics' hooks whose trigger `fires`, in list order, as
    /// `run_hooks_scaled` runs a power's with one stack; `CounterIs` reads
    /// and `SetCounter` / `AddCounter` change the hook's relic's counter.
    /// With `rev`, from the last relic and hook. Returns whether the combat
    /// ended.
    fn run_relic_hooks(&mut self, fires: &impl Fn(&Hook) -> bool, ctx: HookCtx, times: i16, owe_draws: bool, keep: &impl Fn(&Effect) -> bool, rev: bool) -> bool {
        let n = self.player.relics.len();
        for k in 0..n {
            let i = if rev { n - 1 - k } else { k };
            for (hi, h) in ordered(self.player.relics.id(i).hooks(), rev).filter(|(_, h)| fires(h)) {
                let holds = |c| self.relic_condition_holds(self.player.relics.counter(i), c, ctx);
                if !holds(h.condition) || !holds(h.also) {
                    continue;
                }
                for (ei, e) in h.effects.iter().enumerate().filter(|(_, e)| keep(e)) {
                    match *e {
                        // A pick (CombatStart, OwnerTurnStartPostDraw only;
                        // checked at load) opens once this pass has run, the
                        // game's `addToBot`; the hook's rest runs after it
                        // (docs/specs/fight-vocabulary.md). With nothing to
                        // pick, the hook goes on (a `DrawPicked` draws none).
                        Effect::Pick { n, .. } => {
                            if n > 0 && Pick::of_effect(e).is_some_and(|p| self.pick_source(&p).is_some()) && self.stage == Stage::PlayerTurn {
                                let pick = Pick::of_effect(e);
                                self.stage = Stage::RelicPick { relic: i as u8, hook: hi as u8, next: ei as u8 + 1, hit: 0, pick };
                                break;
                            }
                        }
                        // A Discover (CombatStartPreDraw only; checked at
                        // load) opens its offer once the pre-draw pass has
                        // run, before the opening draw (Toolbox's
                        // `addToBot`); the hook's rest runs after the pick.
                        Effect::Discover { .. } => {
                            if self.stage == Stage::StartTurn {
                                self.stage = Stage::RelicOffer { relic: i as u8, hook: hi as u8, next: ei as u8, pick: None };
                            }
                            break;
                        }
                        Effect::SetCounter(n) => self.player.relics.set_counter(i, n),
                        Effect::AddCounter(n) => {
                            let c = self.player.relics.counter(i).saturating_add(n.saturating_mul(times));
                            self.player.relics.set_counter(i, c)
                        }
                        Effect::Draw(n) if owe_draws => {
                            self.owed_draw = self.owed_draw.saturating_add((n as i16 * times).clamp(0, u8::MAX as i16) as u8)
                        }
                        // Raw block (the game's GainBlockAction), as a power's.
                        Effect::Block(n) => self.add_block(Who::Player, n * times),
                        Effect::LoseHp(n) if h.hp_loss != HpLossFrom::Card => self.lose_hp(Who::Player, n * times, h.hp_loss),
                        e if self.owes(Who::Player, &e) => self.owe(Who::Player, e, times),
                        e => self.do_effect(Who::Player, &e.scaled(times), ctx.target),
                    }
                    if self.check_over() {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// Whether a relic hook's condition holds, its relic's counter at
    /// `counter` (`next_draw` passes a projected one).
    fn relic_condition_holds(&self, counter: i16, c: Condition, ctx: HookCtx) -> bool {
        match c {
            Condition::CounterIs(n) => counter == n,
            Condition::CounterAtMost(n) => counter <= n,
            c => self.condition_holds(Who::Player, c, ctx),
        }
    }

    /// Whether a hook's or card row's condition holds for its `owner` and
    /// the card in `ctx`.
    fn condition_holds(&self, owner: Who, c: Condition, ctx: HookCtx) -> bool {
        match c {
            Condition::Always => true,
            Condition::CardType(ty) => match ctx.drawn {
                Some(d) => d == ty,
                None => ctx.card.is_some_and(|card| self.binding.def(card).ty == ty),
            },
            Condition::TargetHas(p) => ctx.target.is_some_and(|t| self.monsters[t as usize].powers.get(p) > 0),
            // Hidden (Runic Dome): what the reveal said, or the one class
            // its roll can give (`intent_class_unknown` pauses otherwise).
            Condition::TargetIntendsAttack => ctx.target.is_some_and(|t| {
                let t = t as usize;
                if self.move_hidden(t) {
                    let moves = self.monsters[t].def().moves;
                    self.intent_distribution(t).iter().all(|&(m, _)| moves.get(m as usize).is_some_and(|d| is_attack(d)))
                } else {
                    self.monsters[t].intent_def().is_some_and(is_attack)
                }
            }),
            // Cards played before the one in play (the counter includes it).
            Condition::CardsPlayedThisTurnBelow(n) => self.cards_played_this_turn.saturating_sub(1) < n,
            Condition::HandAll(ty) => self.hand.iter().all(|(c, _)| self.binding.def(c).ty == ty),
            Condition::OwnerHpAtMostHalf => self.at_most_half(owner, self.hp_of(owner)),
            // Only a relic has a counter; its hooks test it in `run_relic_hooks`.
            Condition::CounterIs(_) | Condition::CounterAtMost(_) => false,
            Condition::NotFirstTurn => self.turn > 1,
            Condition::OwnerBlockIs(n) => self.block_of(owner) == n,
            // The `OwnerApplied` pass picks its hooks by it (`apply_power`).
            Condition::Applying(_) | Condition::ApplyingDebuff => true,
            Condition::HandNone(ty) => !self.hand.iter().any(|(c, _)| self.binding.def(c).ty == ty),
            Condition::DrawHas(ty) => self.draw().iter().any(|(c, _)| self.binding.def(c).ty == ty),
            Condition::TargetLacks(p) => ctx.target.is_some_and(|t| self.monsters[t as usize].powers.get(p) == 0),
            Condition::TargetDied => ctx.target.is_some_and(|t| {
                let m = &self.monsters[t as usize];
                m.kind != crate::monsters::MonsterKind::None && m.hp <= 0 && !m.escaped
            }),
        }
    }

    // ---- effects ----

    pub(crate) fn do_effect(&mut self, actor: Who, e: &Effect, chosen: Option<u8>) {
        match *e {
            // Each sets `dealt` once done, over whatever the hooks it set off
            // left there (a Thorns reply is its own damage effect).
            Effect::Damage { amount, hits, target } => self.dealt = self.deal(actor, target, chosen, amount, hits),
            // The player's random target is a chance event (a card's or
            // potion's; a hook's is owed).
            Effect::PlainDamage { amount, target: Target::RandomOpponent } if actor == Who::Player => self.request_plain_hit(amount),
            Effect::PlainDamage { amount, target } => {
                let (who, n) = self.targets(actor, target, chosen);
                let mut dealt = 0i16;
                for &dst in &who[..n] {
                    let before = self.hp_of(dst).max(0);
                    // Damage the target deals itself (Burn, Decay: the game's
                    // DamageInfo owned by the player) is its own loss
                    // (`Card`: Rupture's `info.owner == owner`).
                    let from = if dst == actor { HpLossFrom::Card } else { HpLossFrom::Any };
                    dealt = dealt.saturating_add(self.take_damage(None, dst, amount, from).min(before));
                }
                self.dealt = dealt;
            }
            Effect::ScaledDamage { amount, hits, target } => {
                let (base, hits) = (self.resolve(actor, amount), self.resolve(actor, hits));
                self.dealt = self.deal(actor, target, chosen, base, hits.clamp(0, u8::MAX as i16) as u8)
            }
            Effect::RandomDamage { .. } | Effect::RandomApply { .. } => {
                unreachable!("random-target effects are resolved hit by hit in run()")
            }
            Effect::RolledAttack => {
                let Who::Monster(slot) = actor else { unreachable!("RolledAttack is a monster move") };
                let base = self.monsters[slot as usize].rolled_damage;
                self.dealt = self.deal(actor, Target::Opponent, None, base, 1)
            }
            Effect::Block(n) => self.gain_block(actor, n),
            // Given at `MonsterRolls` (`request_roll`).
            // Runs in the monsters' turn (`monsters_act_from`), where it may
            // pause on its pick; a monster move's only.
            Effect::BlockAlly(_) => {}
            Effect::ApplyPack { power, amount, target } => {
                let power = self.binding.slot_of(power);
                self.do_effect(actor, &Effect::Apply { power, amount, target }, chosen)
            }
            Effect::ScaledBlock { amount, times } => {
                for _ in 0..self.resolve(actor, times).max(0) {
                    self.gain_block(actor, amount);
                }
            }
            Effect::ExhaustHand { except } => {
                for (c, n) in self.hand.iter().collect::<Vec<_>>() {
                    if except.is_none_or(|t| self.binding.def(c).ty != t) {
                        self.hand_remove(c, n);
                        self.exhaust_card(c, n);
                    }
                }
            }
            Effect::ExhaustRandom => self.request_random_exhaust(),
            Effect::ZeroCostRandom => self.request_zero_cost(),
            Effect::ZeroCostRandomTurn => self.request_free_turn(),
            Effect::UpgradeRandom => self.request_upgrade_random(),
            Effect::CostAtMost { cost, combat } => self.cost_at_most(cost, combat),
            Effect::TakeRandomFromDraw { ty, n } => self.request_take_random(ty, n),
            Effect::Draw(n) => {
                debug_assert_eq!(actor, Who::Player);
                self.request_draw(n);
            }
            Effect::RandomizeCost(crate::effects::CostRoll::Hand) => self.queue_hand_rolls(),
            // Rolled where the card is drawn (`count_drawn`).
            Effect::RandomizeCost(crate::effects::CostRoll::Drawn) => {}
            Effect::GainEnergy(n) => self.player.energy = (self.player.energy + n as i16).min(ENERGY_CAP),
            Effect::LoseHp(n) => self.lose_hp(actor, n, HpLossFrom::Card),
            Effect::LoseHpOf(a) => {
                let n = self.resolve(actor, a);
                if n > 0 {
                    self.lose_hp(actor, n, HpLossFrom::Card);
                }
            }
            Effect::ApplyAsMonster { power, amount, target } => {
                let (who, n) = self.targets(actor, target, chosen);
                for &dst in &who[..n] {
                    self.apply_power_as(actor, dst, power, amount, true);
                }
            }
            // Only in a card's `exhausted`, where `exhaust_card` names the card.
            Effect::AddCopy { .. } => unreachable!("AddCopy outside a card's exhausted effects"),
            Effect::Heal(n) => self.heal(actor, n),
            Effect::HealOf(a) => {
                let n = self.resolve(actor, a);
                self.heal(actor, n);
            }
            Effect::CapHp { amount, num, den, target } => {
                let (who, n) = self.targets(actor, target, chosen);
                for &dst in &who[..n] {
                    let max = match dst {
                        Who::Player => self.player.max_hp,
                        Who::Monster(slot) => self.monsters[slot as usize].max_hp,
                    };
                    let cap = (amount as i32 + max as i32 * num as i32 / den as i32).clamp(1, i16::MAX as i32) as i16;
                    let hp = self.hp_mut(dst);
                    *hp = (*hp).min(cap);
                }
            }
            // Max HP up, then a heal of as much (`increaseMaxHp(n, true)`).
            Effect::GainMaxHp(n) => {
                let n = n.max(0);
                match actor {
                    Who::Player => self.player.max_hp = self.player.max_hp.saturating_add(n),
                    Who::Monster(slot) => self.monsters[slot as usize].max_hp = self.monsters[slot as usize].max_hp.saturating_add(n),
                }
                self.heal(actor, n);
            }
            Effect::WinHeal(n) => {
                if actor == Who::Player {
                    self.win_heal = self.win_heal.saturating_add(n.max(0));
                }
            }
            Effect::Apply { power, amount, target } => {
                let (who, n) = self.targets(actor, target, chosen);
                for &dst in &who[..n] {
                    self.apply_power(actor, dst, power, amount);
                }
            }
            Effect::BlockOf(a) => {
                let n = self.resolve(actor, a).max(0);
                self.add_block(actor, n);
            }
            Effect::ApplyOf { power, amount, target } => {
                let amount = self.resolve(actor, amount);
                if amount != 0 {
                    self.do_effect(actor, &Effect::Apply { power, amount, target }, chosen);
                }
            }
            Effect::AddCard { card, n, pile } => {
                self.created = self.created.saturating_add(n as u16);
                match pile {
                    PileKind::Draw => {
                        // Each copy at a random spot under the top card
                        // (`MakeTempCardInDrawPileAction`'s randomSpot: Wild
                        // Strike, Reckless Charge, Mark of Pain).
                        for _ in 0..n {
                            self.add_to_random_spot(card);
                        }
                    }
                    PileKind::Discard => self.discard_mut().add(card, n),
                    PileKind::Hand => {
                        let k = (HAND_LIMIT.saturating_sub(self.hand.len()) as u8).min(n);
                        self.hand.add(card, k);
                        self.discard_mut().add(card, n - k);
                    }
                }
            }
            Effect::Split => {
                let Who::Monster(slot) = actor else { unreachable!("Split is a monster move") };
                self.split(slot as usize);
            }
            // A monster leaves its slot; the player (a potion's, Smoke Bomb)
            // ends the fight as won (`check_over`).
            Effect::Escape => match actor {
                Who::Monster(slot) => self.monsters[slot as usize].escaped = true,
                Who::Player => self.escaped = true,
            },
            Effect::RemoveSelf | Effect::ReduceSelf(_) => unreachable!("power-relative effects run in run_hooks"),
            Effect::SetCounter(_) | Effect::AddCounter(_) => unreachable!("relic-relative effects run in run_relic_hooks"),
            Effect::Pick { .. } => unreachable!("picks pause the card in run()"),
            Effect::PlayTop { .. } => unreachable!("PlayTop resolves in run()"),
            Effect::MakeRandom { .. } => unreachable!("MakeRandom resolves in run()"),
            Effect::GrowDamage(k) => self.grow_damage(k),
            Effect::UpgradeHand => self.upgrade_hand(),
            Effect::UpgradeAll => self.upgrade_all(),
            Effect::ShuffleDiscardIntoDraw => {
                // Deep Breath's EmptyDeckShuffleAction (`onShuffle`), only
                // with a non-empty discard pile.
                if self.discard().len() > 0 {
                    self.fire_shuffled();
                    let d = self.discard().to_pile();
                    self.set_discard(Pile::default());
                    for (c, n) in d.iter() {
                        self.draw_mut().add(c, n);
                    }
                    self.top = Top::default();
                    // Frozen Eye: the new order is shown at once.
                    if self.sees_order() {
                        self.pending = Some(crate::chance::ChanceEvent::Order { then: crate::chance::OrderThen::Nothing });
                    }
                }
            }
            Effect::RemoveDebuffs => {
                let binding = self.binding;
                let pw = self.powers(actor);
                let debuffs: Vec<Power> = pw.iter().filter(|&(p, n)| binding.is_debuff(p, n)).map(|(p, _)| p).collect();
                for p in debuffs {
                    self.powers_mut(actor).clear(p);
                }
            }
            // Outside a stage that counted a pick, nothing was picked.
            Effect::DrawPicked => {}
            // Runs in a potion's stage only (the potion rows' effect).
            Effect::ObtainRandomPotions { .. } => {}
            Effect::Discover { pool, ty, offer, copies, free, skip } => {
                self.offer = Offer { copies, free, skip, ..Offer::default() };
                let cards = crate::registry::pool_cards(&self.binding, pool, ty);
                if cards.len() <= offer as usize {
                    self.set_offer(&cards);
                } else {
                    self.pending = Some(ChanceEvent::Offer { pool, ty, k: offer });
                }
            }
            // Burst: one more play of the card in play once it resolves.
            Effect::ReplayCard => {
                if let Stage::PlayingCard { ref mut more, .. } = self.stage {
                    more.replays += 1;
                }
            }
        }
    }

    /// `hits` attacks of `base` on the effect's targets (a monster's in its
    /// `attack_shape`), stopping once the combat is decided.
    /// Returns the HP the hits took (each capped at its target's HP).
    fn deal(&mut self, actor: Who, target: Target, chosen: Option<u8>, base: i16, hits: u8) -> i16 {
        let (base, hits) = attack_shape(self.powers(actor), actor, base, hits);
        let mut dealt = 0i16;
        for _ in 0..hits {
            // A monster that died mid-move (Thorns) makes no more hits.
            if let Who::Monster(slot) = actor {
                if !self.monsters[slot as usize].alive() {
                    break;
                }
            }
            let (who, n) = self.targets(actor, target, chosen);
            for &dst in &who[..n] {
                dealt = dealt.saturating_add(self.attack(actor, dst, base));
            }
            if self.player_dead() || self.living_slots().next().is_none() {
                break;
            }
        }
        dealt
    }

    /// The X of the X-cost card in play (0 outside one).
    pub fn stage_x(&self) -> i16 {
        match self.stage {
            Stage::PlayingCard { x, .. } => x as i16,
            _ => 0,
        }
    }

    /// Rampage: the card in play becomes the changed copy of its base with
    /// its damage number + `k` (docs/specs/sparse-piles.md).
    fn grow_damage(&mut self, k: i16) {
        use crate::registry::{changed_copy, copy_of, Overrides};
        let Stage::PlayingCard { card, .. } = self.stage else { return };
        let (base, o) = copy_of(card).unwrap_or((card, Overrides { damage: None, level: self.binding.def(card).level, cost: None }));
        let damage = o.damage.unwrap_or_else(|| card_damage(self.binding.def(card)));
        let grown = Overrides { damage: Some(damage + k), ..o };
        let id = changed_copy(base, self.binding.def(base), grown).unwrap_or_else(|e| panic!("{e}"));
        if let Stage::PlayingCard { card, .. } = &mut self.stage {
            *card = id;
        }
    }

    /// Upgrades one copy of `c` in hand by a general upgrade (Armaments),
    /// for the rest of the combat. Returns whether it was upgraded.
    /// The pick's only distinct candidate, if it has exactly one.
    fn only_candidate(&self, e: &Effect) -> Option<CardId> {
        let src = self.pick_source(&Pick::of_effect(e)?)?;
        let mut it = src.iter();
        let (c, _) = it.next()?;
        it.next().is_none().then_some(c)
    }

    /// The hand gains `n` copies of `c` (a card in hand, which stays), past
    /// the hand limit into the discard pile, as an `AddCard` (Dual Wield:
    /// the game's `makeStatEquivalentCopy`, so the copies keep the card's
    /// upgrades, combat cost and grown damage). The copies in hand cost 0
    /// this turn when every copy of `c` in hand does (the copy keeps
    /// `costForTurn`; the rule `upgrade_in_hand` uses) or with `free`.
    fn copy_in_hand(&mut self, c: CardId, n: u8, free: bool) {
        // Every copy marked: the copies keep the mark (the game's copy keeps
        // `costForTurn`): a cost this turn (the dearest), else 0.
        let all = self.free_in_hand.count(c) + self.turn_costs.count(c) == self.hand.count(c);
        let kept = if all { self.turn_costs.highest(c) } else { None };
        let marked = free || (!self.free_in_hand.is_empty() && self.free_in_hand.count(c) == self.hand.count(c));
        let k = (HAND_LIMIT.saturating_sub(self.hand.len()) as u8).min(n);
        self.do_effect(Who::Player, &Effect::AddCard { card: c, n, pile: PileKind::Hand }, None);
        if marked {
            for _ in 0..k {
                self.mark_free_in_hand(c);
            }
        } else if let Some(v) = kept {
            for _ in 0..k {
                self.mark_turn_cost(c, v as i8);
            }
        }
    }

    pub fn upgrade_in_hand(&mut self, c: CardId) -> bool {
        if self.hand.count(c) == 0 {
            return false;
        }
        // An unmarked copy is upgraded first; a marked one keeps its mark
        // (the game's `upgradeBaseCost` leaves a 0 for the turn at 0).
        let marked = !self.free_in_hand.is_empty() && self.free_in_hand.count(c) == self.hand.count(c);
        // Every copy marked, some at a cost this turn: the dearest of those
        // is the one upgraded, and its cost this turn stays if still lower.
        let carried = (self.free_in_hand.count(c) + self.turn_costs.count(c) == self.hand.count(c)).then(|| self.turn_costs.highest(c)).flatten();
        let Some(up) = crate::registry::upgraded(&self.binding, c) else { return false };
        self.hand_remove(c, 1);
        self.hand.add(up, 1);
        if marked {
            self.mark_free_in_hand(up);
        } else if let Some(k) = carried {
            self.mark_turn_cost(up, k as i8);
        }
        true
    }

    /// One copy of `c` in hand of class `mark` is upgraded
    /// (`UpgradeRandom`); its mark stays (a cost this turn only while still
    /// below the new cost, as `upgrade_in_hand`'s).
    pub(crate) fn upgrade_copy(&mut self, c: CardId, mark: HandMark) {
        let Some(up) = crate::registry::upgraded(&self.binding, c) else { return };
        self.take_class(c, mark);
        self.hand.add(up, 1);
        self.remark(up, mark);
    }

    /// The copies of `c` in hand by class (`HandMark`), with their counts:
    /// unmarked, each cost this turn (lowest first), then marked 0.
    pub(crate) fn hand_classes(&self, c: CardId) -> Vec<(HandMark, u8)> {
        let n = self.hand.count(c);
        let free = self.free_in_hand.count(c).min(n);
        let mut out = Vec::new();
        let mut turn = 0;
        let mut at: Vec<(HandMark, u8)> = Vec::new();
        for (_, v) in self.turn_costs.iter().filter(|&(x, _)| x == c) {
            turn += 1;
            match at.last_mut() {
                Some((HandMark::Turn(w), k)) if *w == v => *k += 1,
                _ => at.push((HandMark::Turn(v), 1)),
            }
        }
        let loose = n.saturating_sub(free + turn);
        if loose > 0 {
            out.push((HandMark::None, loose));
        }
        out.extend(at);
        if free > 0 {
            out.push((HandMark::Free, free));
        }
        out
    }

    /// Takes one copy of `c` of class `mark` out of the hand, its mark with it.
    pub(crate) fn take_class(&mut self, c: CardId, mark: HandMark) {
        match mark {
            HandMark::Free => {
                self.free_in_hand.remove(c);
            }
            HandMark::Turn(v) => {
                self.turn_costs.remove(c, v);
            }
            HandMark::None => {}
        }
        self.hand.remove(c, 1);
    }

    /// The copy `c` just added to the hand takes the mark `mark` its
    /// predecessor held (a cost this turn only while below its cost now).
    fn remark(&mut self, c: CardId, mark: HandMark) {
        match mark {
            HandMark::Free => {
                self.mark_free_in_hand(c);
            }
            HandMark::Turn(v) => {
                self.mark_turn_cost(c, v as i8);
            }
            HandMark::None => {}
        }
    }

    /// One copy of `c` of class `mark` costs 0 this turn (replacing its mark).
    pub(crate) fn free_class(&mut self, c: CardId, mark: HandMark) {
        self.take_class(c, mark);
        self.hand.add(c, 1);
        self.mark_free_in_hand(c);
    }

    /// One copy of `c` of class `mark` costs 0 for the combat (and so needs no mark).
    pub(crate) fn zero_class(&mut self, c: CardId, mark: HandMark) {
        let to = self.at_combat_cost(c, 0);
        self.take_class(c, mark);
        self.hand.add(to, 1);
    }

    /// Armaments+: each copy in hand once by a general upgrade.
    fn upgrade_hand(&mut self) {
        // Copies by what they are before any is upgraded, so each original
        // copy is upgraded once (copies of one card are alike).
        let before: Vec<(CardId, u8)> = self.hand.iter().collect();
        for (c, n) in before {
            for _ in 0..n {
                self.upgrade_in_hand(c);
            }
        }
    }

    /// A `MakeRandom` roll's card `c` made (colorless-cards spec step 3):
    /// upgraded when `up`, at cost 0 for the combat when `zero_cost` and
    /// its cost is above 0, then into the hand (marked free this turn when
    /// `free`; past the hand limit the discard pile, unmarked) or into the
    /// draw pile under its top (`addToRandomSpot`).
    pub(crate) fn make_random(&mut self, c: CardId, pile: PileKind, zero_cost: bool, free: bool, up: bool) {
        use crate::registry::{changed_copy, copy_of, Overrides};
        let mut c = self.made_copy(c);
        if up {
            c = crate::registry::upgraded(&self.binding, c).unwrap_or(c);
        }
        if zero_cost && self.binding.def(c).cost() > 0 {
            let (base, o) = copy_of(c).unwrap_or((c, Overrides { level: self.binding.def(c).level, ..Overrides::default() }));
            c = changed_copy(base, self.binding.def(base), Overrides { cost: Some(0), ..o }).unwrap_or_else(|e| panic!("{e}"));
        }
        self.created = self.created.saturating_add(1);
        match pile {
            PileKind::Hand if self.hand.len() < HAND_LIMIT => {
                self.hand.add(c, 1);
                if free {
                    self.mark_free_in_hand(c);
                }
            }
            PileKind::Hand | PileKind::Discard => self.discard_mut().add(c, 1),
            PileKind::Draw => self.add_to_random_spot(c),
        }
    }

    /// `c` into the draw pile as `CardGroup.addToRandomSpot`: under the top
    /// card when the pile holds any, so never the next draw.
    /// With Frozen Eye its spot is owed work (`OwedKind::Insert`), paid
    /// before anything reads the order.
    fn add_to_random_spot(&mut self, c: CardId) {
        let was_empty = self.draw().is_empty();
        self.draw_mut().add(c, 1);
        if self.sees_order() {
            self.owed.push(OwedKind::Insert { card: c }, 1, false);
        } else if !was_empty {
            self.top.add_floater_under(c);
        }
    }

    /// `k` copies of `c` from hand onto the top of the draw pile, known.
    fn hand_to_top(&mut self, c: CardId, k: u8) {
        self.hand_remove(c, k);
        self.draw_mut().add(c, k);
        let all = self.sees_order();
        for _ in 0..k {
            self.top.push(c, all);
        }
    }

    /// Apotheosis: `upgrade_hand`, then each copy in the draw, discard and
    /// exhaust piles once by a general upgrade; known-top and floater ids
    /// follow their cards.
    fn upgrade_all(&mut self) {
        self.upgrade_hand();
        for r in [Run::Draw, Run::Discard, Run::Exhaust] {
            // Copies by what they are before any is upgraded (Searing
            // Blow's levels: each copy goes up once).
            let before: Vec<(CardId, CardId, u8)> = self
                .piles
                .get(r)
                .iter()
                .filter_map(|(c, n)| crate::registry::upgraded(&self.binding, c).map(|up| (c, up, n)))
                .collect();
            let mut pile = self.piles.get_mut(r);
            for &(c, _, n) in &before {
                pile.remove(c, n);
            }
            for &(_, up, n) in &before {
                pile.add(up, n);
            }
        }
        if !self.top.is_empty() {
            let b = &self.binding;
            self.top.map_cards(|c| crate::registry::upgraded(b, c).unwrap_or(c));
        }
    }

    /// Whether `who` holds a power with a `RoundEnd` hook: one of
    /// `ROUND_END_POWERS`, or any bound generated power (checked in full).
    fn has_round_end(&self, who: Who) -> bool {
        let p = self.powers(who);
        !self.binding.is_empty() || ROUND_END_POWERS.iter().any(|&q| p.get(q) > 0) || (who == Who::Player && !self.player.relics.is_empty())
    }

    /// An amount's value for `actor` now.
    pub fn resolve(&self, actor: Who, a: Amount) -> i16 {
        match a.of {
            None => a.base,
            Some(q) => a.at(self.quantity(actor, q)),
        }
    }

    /// A quantity's value for `actor` now.
    pub fn quantity(&self, actor: Who, q: Quantity) -> i16 {
        match q {
            Quantity::OwnBlock => match actor {
                Who::Player => self.player.block,
                Who::Monster(slot) => self.monsters[slot as usize].block,
            },
            Quantity::OwnStrength => self.powers(actor).get(Power::Strength),
            Quantity::OwnMaxHp => match actor {
                Who::Player => self.player.max_hp,
                Who::Monster(slot) => self.monsters[slot as usize].max_hp,
            },
            // Chemical X: an X card resolves at X plus the held relics'
            // `x_bonus` (the game's X actions add it on every play).
            Quantity::EnergySpent => match self.stage {
                Stage::PlayingCard { card, x, .. } if self.binding.def(card).x_cost() => x as i16 + self.relic_x_bonus(),
                _ => self.stage_x(),
            },
            Quantity::DrawPileSize => self.draw().len() as i16,
            Quantity::CardsTagged(t) => self.tagged_count(t),
            Quantity::HandCards { except } => {
                self.hand.iter().filter(|&(c, _)| except.is_none_or(|t| self.binding.def(c).ty != t)).map(|(_, n)| n as i16).sum()
            }
            Quantity::CardsOfType(t) => self.type_count(t),
            Quantity::HpDealt => self.dealt,
        }
    }

    /// Cards of type `t` in hand, draw and discard, plus the card in play
    /// if it is one (Du-Vu Doll's curses, read at combat start).
    pub fn type_count(&self, t: CardType) -> i16 {
        let in_piles: usize = [self.hand.view(), self.draw(), self.discard()]
            .iter()
            .flat_map(|p| p.iter())
            .filter(|(c, _)| self.binding.def(*c).ty == t)
            .map(|(_, n)| n as usize)
            .sum();
        let in_play = matches!(self.stage, Stage::PlayingCard { card, .. } if self.binding.def(card).ty == t);
        (in_play as usize + in_piles) as i16
    }

    /// Cards with tag `t` in hand, draw and discard, plus the card in play
    /// if it has it and was played from the hand (Perfected Strike counts
    /// itself; the game computes its damage while it is still in the hand,
    /// and a card Havoc plays or a replayed copy is in limbo).
    pub fn tagged_count(&self, t: Tag) -> i16 {
        let in_piles: usize = [self.hand.view(), self.draw(), self.discard()]
            .iter()
            .flat_map(|p| p.iter())
            .filter(|(c, _)| self.binding.def(*c).has_tag(t))
            .map(|(_, n)| n as usize)
            .sum();
        let in_play = matches!(self.stage, Stage::PlayingCard { card, more, .. }
            if !more.queued && !more.copy && self.binding.def(card).has_tag(t));
        (in_play as usize + in_piles) as i16
    }

    /// The splitting monster's slot takes its first child; the second takes
    /// the lowest empty slot. Both get its current HP as their max HP.
    fn split(&mut self, slot: usize) {
        let m = self.monsters[slot];
        let [a, b] = m.def().split_into;
        self.monsters[slot] = Monster::new_at(a, m.hp, &self.binding, m.ascension);
        let free = self.monsters.iter().position(|x| x.kind == MonsterKind::None).expect("no free slot to split into");
        self.monsters[free] = Monster::new_at(b, m.hp, &self.binding, m.ascension);
    }

    /// Living combatants an effect hits.
    fn targets(&self, actor: Who, target: Target, chosen: Option<u8>) -> ([Who; MAX_MONSTERS], usize) {
        let mut out = [Who::Player; MAX_MONSTERS];
        let mut n = 0;
        let mut push = |w: Who| {
            out[n] = w;
            n += 1;
        };
        match (actor, target) {
            (_, Target::Me) => push(actor),
            (Who::Monster(_), _) => push(Who::Player),
            (Who::Player, Target::Opponent | Target::Attacker) => {
                if let Some(t) = chosen.filter(|&t| self.monsters[t as usize].alive()) {
                    push(Who::Monster(t));
                }
            }
            (Who::Player, Target::AllOpponents) => {
                for slot in self.living_slots() {
                    push(Who::Monster(slot as u8));
                }
            }
            (Who::Player, Target::RandomOpponent) => unreachable!("the player's random target is a chance event (request_plain_hit)"),
        }
        (out, n)
    }

    pub fn powers(&self, w: Who) -> &Powers {
        match w {
            Who::Player => &self.player.powers,
            Who::Monster(i) => &self.monsters[i as usize].powers,
        }
    }

    fn powers_mut(&mut self, w: Who) -> &mut Powers {
        match w {
            Who::Player => &mut self.player.powers,
            Who::Monster(i) => &mut self.monsters[i as usize].powers,
        }
    }

    fn hp_mut(&mut self, w: Who) -> &mut i16 {
        match w {
            Who::Player => &mut self.player.hp,
            Who::Monster(i) => &mut self.monsters[i as usize].hp,
        }
    }

    fn block_mut(&mut self, w: Who) -> &mut i16 {
        match w {
            Who::Player => &mut self.player.block,
            Who::Monster(i) => &mut self.monsters[i as usize].block,
        }
    }

    /// Attack damage through the pipeline: base, adds (Strength, then the
    /// attacker's other `Add` statics), multiplies (Weak ×0.75, the other
    /// statics, Vulnerable ×1.5), rounded down once at the end, never below
    /// 0. Strength, Weak and Vulnerable are hard-coded (the fast path);
    /// `interpret_attack_damage` reads every static row and must agree.
    pub fn attack_damage(&self, src: Who, dst: Who, base: i16) -> i16 {
        self.attack_damage_to(src, Some(dst), base)
    }

    /// `attack_damage` with the defender's side left out when `dst` is
    /// `None` (its Vulnerable and every other `DamageTaken` row).
    fn attack_damage_to(&self, src: Who, dst: Option<Who>, base: i16) -> i16 {
        let ps = self.powers(src);
        let pd = dst.map(|d| self.powers(d));
        // A side holding a generic or generated static power: the rows,
        // read in full (equal to this fast path on official content: tests).
        if self.generic_powers().any(|p| ps.get(p) != 0 || pd.is_some_and(|pd| pd.get(p) != 0)) {
            return self.interpret_attack_damage_to(src, dst, base);
        }
        let mut num = (base + ps.get(Power::Strength)) as i32;
        let mut den = 1;
        if ps.get(Power::Weak) > 0 {
            num *= 3;
            den *= 4;
        }
        if pd.is_some_and(|pd| pd.get(Power::Vulnerable) > 0) {
            num *= 3;
            den *= 2;
        }
        (num.max(0) / den) as i16
    }

    /// The attacks of move `mv` used by the monster in `slot` now, one
    /// `(damage per hit, hits)` per attack effect: `attack_shape`, then
    /// `attack_damage` against the player, or without the player's side
    /// (Vulnerable) unless `vulnerable`. Every reader of a monster's attack
    /// damage (intents, lookahead, the heuristic, the board) uses this.
    pub fn move_attacks<'a>(&'a self, slot: usize, mv: &'a MoveDef, vulnerable: bool) -> impl Iterator<Item = (i16, u8)> + 'a {
        let m = &self.monsters[slot];
        let who = Who::Monster(slot as u8);
        mv.effects.iter().filter_map(move |e| {
            let (base, hits) = match *e {
                Effect::Damage { amount, hits, .. } => (amount, hits),
                Effect::RolledAttack => (m.rolled_damage, 1),
                _ => return None,
            };
            let (base, hits) = attack_shape(&m.powers, who, base, hits);
            Some((self.attack_damage_to(who, vulnerable.then_some(Who::Player), base), hits))
        })
    }

    /// A player attack of `base` x `hits` as its card shows it, before a
    /// target is chosen: the hits of `attack_shape`, each through the
    /// attacker's side of `attack_damage` (Strength, Weak and the other
    /// statics, rounded down per hit), summed. The target's Vulnerable and
    /// statics are left out, as the game's card text leaves them out.
    pub fn shown_damage(&self, base: i16, hits: u8) -> i32 {
        let (base, hits) = attack_shape(&self.player.powers, Who::Player, base, hits);
        self.attack_damage_to(Who::Player, None, base) as i32 * hits as i32
    }

    /// A card's block of `base` as it would be gained now (and as the game
    /// shows it): Dexterity and the other adds, then Frail and the other
    /// multiplies, never below 0.
    pub fn shown_block(&self, base: i16) -> i16 {
        let p = &self.player.powers;
        let n = if self.generic_powers().any(|g| p.get(g) != 0) {
            self.interpret_block(base)
        } else {
            let n = base + p.get(Power::Dexterity);
            if p.get(Power::Frail) > 0 { n.max(0) * 3 / 4 } else { n }
        };
        n.max(0)
    }

    /// The powers whose statics and replacements are read from data at play
    /// time: `GENERIC_STATICS` (or `REPLACEMENT_POWERS`), then the bound
    /// generated slots (none in an official-only combat).
    fn generic_powers(&self) -> impl Iterator<Item = Power> + '_ {
        GENERIC_STATICS.into_iter().chain(self.generated_powers())
    }

    fn generated_powers(&self) -> impl Iterator<Item = Power> + '_ {
        self.binding.powers_in_play()[crate::powers::NUM_OFFICIAL_POWERS..].iter().copied()
    }


    /// Whether a static's condition holds for its `owner` now; `other` is
    /// the attack's other creature, when there is one (`Holds` Opponent).
    pub fn static_holds(&self, owner: Who, other: Option<Who>, c: StaticCondition) -> bool {
        match c {
            StaticCondition::Holds { side: Side::Owner, power } => self.powers(owner).get(power) > 0,
            StaticCondition::Holds { side: Side::Opponent, power } => other.is_some_and(|o| self.powers(o).get(power) > 0),
            StaticCondition::Always => true,
            StaticCondition::CardInPlayTagged(t) => {
                matches!(self.stage, Stage::PlayingCard { card, .. } if owner == Who::Player && self.binding.def(card).has_tag(t))
            }
            StaticCondition::OwnerHpAtMostHalf => {
                let (hp, max) = match owner {
                    Who::Player => (self.player.hp, self.player.max_hp),
                    Who::Monster(slot) => (self.monsters[slot as usize].hp, self.monsters[slot as usize].max_hp),
                };
                2 * hp <= max
            }
        }
    }

    /// `attack_damage` read entirely from the static rows of every power in
    /// play (no fast path): every add, then the attacker's multiplies, then
    /// the target's, rounded down once. Tests check the two agree.
    pub fn interpret_attack_damage(&self, src: Who, dst: Who, base: i16) -> i16 {
        self.interpret_attack_damage_to(src, Some(dst), base)
    }

    fn interpret_attack_damage_to(&self, src: Who, dst: Option<Who>, base: i16) -> i16 {
        let (mut num, mut den) = (base as i32, 1);
        let powers = self.binding.powers_in_play();
        for (who, what, stage) in [
            (Some(src), Modifies::DamageDealt, StaticStage::Add),
            (dst, Modifies::DamageTaken, StaticStage::Add),
            (Some(src), Modifies::DamageDealt, StaticStage::Multiply),
            (dst, Modifies::DamageTaken, StaticStage::Multiply),
        ] {
            let Some(who) = who else { continue };
            let other = if who == src { dst } else { Some(src) };
            for &p in powers {
                let stacks = self.powers(who).get(p);
                let live = if stage == StaticStage::Add { stacks != 0 } else { stacks > 0 };
                if !live {
                    continue;
                }
                for st in self.binding.statics(p).iter().filter(|st| st.modifies == what && st.stage == stage && self.static_holds(who, other, st.condition)) {
                    match stage {
                        StaticStage::Add => num += (st.amount * stacks) as i32 * den,
                        StaticStage::Multiply => {
                            num *= st.num as i32;
                            den *= st.den as i32;
                        }
                    }
                }
            }
        }
        (num.max(0) / den) as i16
    }

    /// `gain_block`'s amount read from the static rows (player only, as
    /// the fast path): adds, multiplies, rounded down, never below 0.
    pub fn interpret_block(&self, base: i16) -> i16 {
        let (mut num, mut den) = (base as i32, 1);
        for stage in [StaticStage::Add, StaticStage::Multiply] {
            for &p in self.binding.powers_in_play() {
                let stacks = self.player.powers.get(p);
                let live = if stage == StaticStage::Add { stacks != 0 } else { stacks > 0 };
                if !live {
                    continue;
                }
                for st in self.binding.statics(p).iter().filter(|st| st.modifies == Modifies::BlockGained && st.stage == stage) {
                    if !self.static_holds(Who::Player, None, st.condition) {
                        continue;
                    }
                    match stage {
                        StaticStage::Add => num += (st.amount * stacks) as i32 * den,
                        StaticStage::Multiply => {
                            // Frail rounds the adds' total, floored at 0, before scaling.
                            num = num.max(0) * st.num as i32;
                            den *= st.den as i32;
                        }
                    }
                }
            }
        }
        (num.max(0) / den) as i16
    }

    /// Returns the HP the hit took, capped at the HP its target had (the
    /// game's `lastDamageTaken`).
    pub(crate) fn attack(&mut self, src: Who, dst: Who, base: i16) -> i16 {
        let dmg = self.attack_damage(src, dst, base);
        let before = *self.hp_mut(dst);
        let lost = self.take_damage(Some(src), dst, dmg, HpLossFrom::Attack);
        let took = lost.min(before.max(0));
        // The attacker's `OwnerAttackHit` hooks (Weak on hit) when the hit
        // made its target lose HP (a saved player's HP may end above
        // `before`: docs/specs/would-die.md); only scanned when the attacker
        // holds one.
        if *self.hp_mut(dst) < before || (lost > 0 && before - lost < 1) {
            let p = self.powers(src);
            let hooked = !self.binding.is_empty() || ATTACK_HIT_POWERS.iter().any(|&q| p.get(q) > 0) || (src == Who::Player && !self.player.relics.is_empty());
            if hooked && !self.player_dead() && self.living_slots().next().is_some() {
                let hit = match dst {
                    Who::Monster(slot) => Some(slot),
                    Who::Player => None,
                };
                let ctx = HookCtx { card: None, target: hit, drawn: None };
                if self.run_hooks_with(src, |h: &Hook| h.trigger == Trigger::OwnerAttackHit, ctx) {
                    return took;
                }
            }
        }
        // The target's `OwnerAttacked` hooks (Thorns), the attacker in the
        // context; only scanned when the target holds such a power.
        let p = self.powers(dst);
        let hooked = !self.binding.is_empty() || ATTACKED_POWERS.iter().any(|&q| p.get(q) > 0) || (dst == Who::Player && !self.player.relics.is_empty());
        if hooked && !self.player_dead() && self.living_slots().next().is_some() {
            let attacker = match src {
                Who::Monster(slot) => Some(slot),
                Who::Player => None,
            };
            let ctx = HookCtx { card: None, target: attacker, drawn: None };
            self.run_hooks_with(dst, |h: &Hook| h.trigger == Trigger::OwnerAttacked, ctx);
        }
        took
    }

    /// `amount` of `event` on `owner` after its replacement rows, in power
    /// order, each on the running amount; `None` when one cancels it. Each
    /// row that applies runs its `then` effects on its power.
    pub(crate) fn replaced(&mut self, owner: Who, event: Replaced, amount: i16) -> Option<i16> {
        self.replaced_of(owner, event, None, amount)
    }

    /// `replaced`; for a debuff being applied (`applying`), first the
    /// replacements filtered to that power, then the unfiltered ones.
    fn replaced_of(&mut self, owner: Who, event: Replaced, applying: Option<Power>, amount: i16) -> Option<i16> {
        let mut n = amount;
        let gen: &'static [Power] = &self.binding.powers_in_play()[crate::powers::NUM_OFFICIAL_POWERS..];
        let passes: &[bool] = if applying.is_some() { &[true, false] } else { &[false] };
        for &filtered in passes {
            for p in REPLACEMENT_POWERS.into_iter().chain(gen.iter().copied()) {
                if self.powers(owner).get(p) <= 0 {
                    continue;
                }
                let wanted = |r: &&Replacement| r.event == event && if filtered { r.power.is_some() && r.power == applying } else { r.power.is_none() };
                for r in self.binding.replacements(p).iter().filter(wanted) {
                    if r.up_to.is_some_and(|m| n > m) {
                        continue;
                    }
                    let applies = match r.action {
                        Replace::Cancel => true,
                        Replace::Cap(c) => n > c,
                        Replace::AtLeast(k) => n < k,
                        Replace::Add(_) | Replace::Multiply(..) => true,
                    };
                    if !applies {
                        continue;
                    }
                    for e in r.then {
                        match *e {
                            Effect::ReduceSelf(k) => self.powers_mut(owner).add(p, -k),
                            Effect::RemoveSelf => self.powers_mut(owner).clear(p),
                            _ => unreachable!("replacement `then` effects act on their power"),
                        }
                    }
                    match r.action {
                        Replace::Cancel => return None,
                        Replace::Cap(c) => n = c,
                        Replace::Add(k) => n += k,
                        Replace::Multiply(num, den) => n = (n as i32 * num as i32 / den as i32) as i16,
                        Replace::AtLeast(k) => n = k,
                    }
                }
            }
        }
        Some(n)
    }

    /// `dmg` that block absorbs, then the reactions to any HP lost; `by`
    /// is the attacker of an attack (its `DealtAfterBlock` rows). Returns
    /// the HP the damage took (before any save heals it back).
    fn take_damage(&mut self, by: Option<Who>, dst: Who, dmg: i16, from: HpLossFrom) -> i16 {
        // Replacements on the amount (Intangible), then block, then the
        // after-block passes.
        let dmg = self.replaced(dst, Replaced::DamageTaken, dmg).unwrap_or(0);
        let block = self.block_mut(dst);
        let had = *block;
        let absorbed = dmg.max(0).min(*block);
        *block -= absorbed;
        // A monster's block broken, an exact break included (the game's
        // `decrementBlock` calls `brokeBlock`): counted for the player's
        // `OpponentBlockBroken` hooks (Hand Drill).
        if let Who::Monster(slot) = dst {
            if had > 0 && dmg >= had && self.player_has_trigger(Trigger::OpponentBlockBroken) {
                self.block_broken[slot as usize] = self.block_broken[slot as usize].saturating_add(1);
            }
        }
        let lost = self.after_block(by, dst, dmg.max(0) - absorbed, from);
        let floor = self.hp_floor(dst);
        let hp = self.hp_mut(dst);
        let before = *hp;
        *hp = (*hp - lost).max(floor);
        if lost > 0 {
            self.lost_hp(dst, from, lost, before);
        }
        lost
    }

    /// The after-block passes on `n`, the amount past block
    /// (docs/specs/after-block.md, the game's `damage` order): the
    /// attacker's `DealtAfterBlock` (attacks only), then the target's
    /// `TakenAfterBlock`, `AttackedAfterBlock` (attacks only) and
    /// `HpLossLast`, each while the amount is above 0; never below 0.
    fn after_block(&mut self, by: Option<Who>, dst: Who, mut n: i16, from: HpLossFrom) -> i16 {
        if n <= 0 || !self.binding.has_after_block() {
            return n;
        }
        let attack = from == HpLossFrom::Attack;
        for event in Replaced::AFTER_BLOCK {
            if n <= 0 {
                break;
            }
            let owner = match event {
                Replaced::DealtAfterBlock => match by {
                    Some(w) if attack => w,
                    _ => continue,
                },
                Replaced::AttackedAfterBlock if !attack => continue,
                _ => dst,
            };
            n = self.replaced(owner, event, n).unwrap_or(0).max(0);
        }
        n
    }

    /// `who` gains `n` HP up to its max HP; the dead don't heal.
    fn heal(&mut self, who: Who, n: i16) {
        let max = match who {
            Who::Player => self.player.max_hp,
            Who::Monster(slot) => self.monsters[slot as usize].max_hp,
        };
        // Only the player's heals pass the relics (`onPlayerHeal`).
        let n = if who == Who::Player { self.player_heal(n) } else { n.max(0) };
        let hp = self.hp_mut(who);
        let before = *hp;
        if before > 0 {
            *hp = (before + n).min(max);
            // Above half again: the owner's `OwnerUnbloodied` hooks.
            let after = *hp;
            if self.at_most_half(who, before) && !self.at_most_half(who, after) {
                self.run_hooks(who, Trigger::OwnerUnbloodied);
            }
        }
    }

    /// `who`'s HP now.
    fn hp_of(&self, who: Who) -> i16 {
        match who {
            Who::Player => self.player.hp,
            Who::Monster(slot) => self.monsters[slot as usize].hp,
        }
    }

    /// `who`'s block now.
    fn block_of(&self, who: Who) -> i16 {
        match who {
            Who::Player => self.player.block,
            Who::Monster(slot) => self.monsters[slot as usize].block,
        }
    }

    /// Whether `hp` is at most half `who`'s max HP (`2 × hp <= max_hp`).
    fn at_most_half(&self, who: Who, hp: i16) -> bool {
        let max = match who {
            Who::Player => self.player.max_hp,
            Who::Monster(slot) => self.monsters[slot as usize].max_hp,
        };
        // In i32: no-death mode lets HP fall past i16::MIN / 2.
        2 * hp as i32 <= max as i32
    }

    /// HP loss that ignores block, then the reactions to it.
    fn lose_hp(&mut self, who: Who, n: i16, from: HpLossFrom) {
        // Never below 0: a replacement can't turn HP loss into healing.
        let n = self.replaced(who, Replaced::HpLoss, n).unwrap_or(0).max(0);
        let n = self.after_block(None, who, n, from);
        let floor = self.hp_floor(who);
        let hp = self.hp_mut(who);
        let before = *hp;
        *hp = (*hp - n).max(floor);
        if *hp < before {
            let lost = before - *hp;
            self.lost_hp(who, from, lost, before);
        }
    }

    /// Reactions to `who` losing HP (from `before`): for the player below 1
    /// HP, a save first (`save_from_death`); `OwnerDied` hooks for a
    /// monster at 0 HP, else `OwnerBloodied` hooks if it just reached half
    /// its max HP or below, the matching `OwnerLostHp` hooks, then a living
    /// monster's own move logic (Lagavulin wakes, slimes split). The caller
    /// checks for the end of combat.
    fn lost_hp(&mut self, who: Who, from: HpLossFrom, lost: i16, before: i16) {
        if who == Who::Player && lost > 0 {
            let cap = self.binding.hp_loss_cap();
            if cap > 0 {
                if self.times_lost_hp < cap {
                    self.times_lost_hp += 1;
                }
                self.hp_loss_costs();
            }
        }
        // The player would die: a save may keep them alive
        // (docs/specs/would-die.md).
        let saved = who == Who::Player && self.player.hp < 1 && self.save_from_death();
        let dead = match who {
            Who::Player => self.player_dead(),
            Who::Monster(slot) => self.monsters[slot as usize].hp == 0,
        };
        if dead {
            if who != Who::Player && !self.run_hooks(who, Trigger::OwnerDied) && self.living_slots().next().is_some() {
                self.run_hooks(Who::Player, Trigger::OpponentDied);
            }
            return;
        }
        // The game calls `onBloodied` where `damage` lowers HP, before the
        // HP-loss reactions queued behind it (docs/specs/red-skull-strength.md).
        if !self.at_most_half(who, before) && self.at_most_half(who, self.hp_of(who)) && self.run_hooks(who, Trigger::OwnerBloodied) {
            return;
        }
        // A save that ends above half from at most half: the save's heal
        // runs no hooks itself, so the bloodied state moves here, once.
        if saved && self.at_most_half(who, before) && !self.at_most_half(who, self.hp_of(who)) && self.run_hooks(who, Trigger::OwnerUnbloodied) {
            return;
        }
        if who == Who::Player && from == HpLossFrom::Card && matches!(self.stage, Stage::PlayingCard { .. }) {
            self.card_hp_losses = self.card_hp_losses.saturating_add(1);
            return;
        }
        let fires = |h: &Hook| matches!(h.trigger, Trigger::OwnerLostHp { from: f } if f.matches(from));
        if self.run_hooks_with(who, fires, HookCtx::default()) {
            return;
        }
        let Who::Monster(slot) = who else { return };
        let queued = self.defers_queued_block();
        let m = &mut self.monsters[slot as usize];
        // The Guardian counts every HP lost toward Mode Shift; at 0 it turns
        // Defensive: Close Up next, and 20 block the game queues behind what
        // is queued now (`defers_queued_block`): after the card in play, or,
        // broken while the turn ends (Combust), after the monsters' block
        // loss, so it keeps it into the player's next turn.
        if m.kind == MonsterKind::TheGuardian && m.powers.get(Power::ModeShift) > 0 {
            m.powers.add(Power::ModeShift, -lost);
            if m.powers.get(Power::ModeShift) <= 0 {
                m.powers.clear(Power::ModeShift);
                m.rolled_damage += guardian::THRESHOLD_STEP;
                m.set_move(guardian::CLOSE_UP);
                if queued {
                    self.deferred_block[slot as usize] += guardian::DEFENSIVE_BLOCK;
                } else {
                    m.block = gained_block(m.block, guardian::DEFENSIVE_BLOCK);
                }
                self.intent_hidden[slot as usize] &= !HIDDEN_MASK;
            }
            return;
        }
        // Woken by HP loss: `changeState("OPEN")` takes 8 Metallicize off
        // (a burning elite's extra stays), as its third Sleep turn does.
        if m.kind == MonsterKind::Lagavulin && lagavulin::asleep(m) {
            m.powers.reduce(Power::Metallicize, lagavulin::OPEN_METALLICIZE);
            m.set_move(lagavulin::STUNNED);
            self.intent_hidden[slot as usize] &= !HIDDEN_MASK;
        }
        let m = &mut self.monsters[slot as usize];
        let split = m.def().split_move;
        if split != NO_MOVE && m.intent() != split && 2 * m.hp <= m.max_hp {
            m.set_move(split);
            self.intent_hidden[slot as usize] &= !HIDDEN_MASK;
        }
    }

    /// Sets a monster's next move, with what choosing it fixes (Hexaghost's
    /// Divider damage, from the player's HP now).
    pub fn set_monster_move(&mut self, slot: usize, m: MoveId) {
        let player_hp = self.player.hp;
        self.intent_hidden[slot] &= !HIDDEN_MASK;
        let mon = &mut self.monsters[slot];
        mon.set_move(m);
        if mon.kind == MonsterKind::Hexaghost && m == hexaghost::DIVIDER {
            mon.rolled_damage = hexaghost::divider_damage(player_hp);
        }
    }

    /// What a monster's move does beyond its effects (Inferno upgrades
    /// every Burn in hand, draw and discard pile; Twin Slam returns The
    /// Guardian to Offensive mode).
    fn after_move(&mut self, slot: usize, used: MoveId) {
        let m = &mut self.monsters[slot];
        if m.kind == MonsterKind::TheGuardian && used == guardian::TWIN_SLAM {
            m.powers.clear(Power::SharpHide);
            m.powers.add(Power::ModeShift, m.rolled_damage);
        }
        if self.monsters[slot].kind == MonsterKind::Hexaghost && matches!(used, hexaghost::INFERNO | hexaghost::INFERNO_UP) {
            let (base, up) = (CardId::new(CardKind::Burn, false), CardId::new(CardKind::Burn, true));
            let n = self.hand.count(base);
            self.hand.remove(base, n);
            self.hand.add(up, n);
            for r in [Run::Draw, Run::Discard] {
                let mut pile = self.piles.get_mut(r);
                let n = pile.count(base);
                pile.remove(base, n);
                pile.add(up, n);
            }
            self.top.map_cards(|c| if c == base { up } else { c });
        }
    }

    /// Card block: for the player, Dexterity and the other `Add` statics,
    /// then Frail (×0.75 of a total floored at 0) and the other multiplies
    /// (the fast path; `interpret_block` reads the rows and must agree).
    fn gain_block(&mut self, w: Who, base: i16) {
        let n = if w == Who::Player { self.shown_block(base) } else { base.max(0) };
        self.add_block(w, n);
    }

    /// Every block gain lands here (the game's `addBlock`): a player's
    /// gain above 0 first fires the player's `OwnerGainedBlock` hooks
    /// (Juggernaut), unless it comes from those hooks.
    fn add_block(&mut self, w: Who, n: i16) {
        if w == Who::Player && n > 0 && !IN_GAINED_BLOCK.get() && self.player_has_trigger(Trigger::OwnerGainedBlock) {
            IN_GAINED_BLOCK.set(true);
            self.run_hooks_with(Who::Player, |h: &Hook| h.trigger == Trigger::OwnerGainedBlock, HookCtx::default());
            IN_GAINED_BLOCK.set(false);
        }
        let b = self.block_mut(w);
        *b = gained_block(*b, n);
    }

    pub(crate) fn apply_power(&mut self, src: Who, dst: Who, p: Power, amount: i16) {
        self.apply_power_as(src, dst, p, amount, matches!(src, Who::Monster(_)));
    }

    /// `apply_power`, as a monster's application when `src_monster` (the
    /// game's `isSourceMonster`: Doubt's Weak, Shame's Frail).
    fn apply_power_as(&mut self, src: Who, dst: Who, p: Power, amount: i16, src_monster: bool) {
        let dst_monster = matches!(dst, Who::Monster(_));
        let rules = self.binding.rules(p);
        // A negative amount of a power that can't go below 0 (its row has
        // no `can_go_negative`; official or pack) is the game's
        // `ReducePowerAction` (Lagavulin waking: Metallicize -8): floored at
        // 0, nothing when not held, no debuff and no `OwnerApplied` hooks.
        if amount < 0 && !rules.can_go_negative {
            self.powers_mut(dst).reduce(p, -amount);
            return;
        }
        let debuff = rules.is_debuff(amount);
        // Artifact is a `DebuffApplied` replacement: cancel, lose a stack;
        // other replacements change the debuff's size (a Strength loss's
        // too), and one that takes it to 0 or below cancels it.
        let amount = if debuff {
            match self.replaced_of(dst, Replaced::DebuffApplied, Some(p), amount.abs()) {
                Some(a) if a > 0 => a * amount.signum(),
                _ => return,
            }
        } else {
            amount
        };
        let turn_has_ended = self.turn_has_ended();
        let pw = self.powers_mut(dst);
        let fresh = pw.get(p) == 0;
        // The game's caps (its row's `cap`: Strength 999, Poison 9999).
        let amount = match rules.cap {
            Some(c) => (pw.get(p) as i32 + amount as i32).clamp(-(c as i32), c as i32) as i16 - pw.get(p),
            None => amount,
        };
        pw.add(p, amount);
        // A power can skip the end of the round it lands in: a debuff a
        // monster applies (Vulnerable and NoBlock only once the player's
        // turn has ended), Ritual on the turn a monster gains it (its row's
        // `skips_first_round`).
        let sk = rules.skips_first_round;
        let skip = (sk.from_monster && src_monster) || (sk.from_monster_after_turn_end && src_monster && turn_has_ended) || (sk.on_monster && dst_monster);
        if fresh && skip {
            pw.set_just_applied(p);
        }
        // The player's `OwnerApplied` hooks, the creature as their opponent;
        // not for an application made by one (docs/specs/act1-singles.md).
        if let (Who::Player, Who::Monster(slot)) = (src, dst) {
            if (!self.player.relics.is_empty() || !self.binding.is_empty()) && !IN_OWNER_APPLIED.get() {
                let is = |c: Condition| match c {
                    Condition::Applying(q) => q == p,
                    Condition::ApplyingDebuff => debuff,
                    _ => true,
                };
                IN_OWNER_APPLIED.set(true);
                let ctx = HookCtx { card: None, target: Some(slot), drawn: None };
                self.run_hooks_with(Who::Player, |h: &Hook| h.trigger == Trigger::OwnerApplied && is(h.condition) && is(h.also), ctx);
                IN_OWNER_APPLIED.set(false);
            }
        }
    }
}

thread_local! {
    /// Set while the player's `OwnerApplied` hooks run, so the powers they
    /// apply don't fire them again. Kept out of the state: it is never set
    /// between actions.
    static IN_OWNER_APPLIED: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
    /// Set while the player's `OwnerGainedBlock` hooks run, so the block
    /// they give doesn't fire them again.
    static IN_GAINED_BLOCK: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
}

/// A card's damage number: its first `Damage` effect's amount (0 if none).
pub fn card_damage(d: &CardDef) -> i16 {
    d.all_effects().find_map(|e| if let Effect::Damage { amount, .. } = *e { Some(amount) } else { None }).unwrap_or(0)
}

/// How an attack effect of `base` x `hits` lands for `who` holding
/// `powers`: a monster holding an official power with an `attack_shape`
/// split `n` (Split Hits: 2) deals `n` times the hits at the base divided
/// by `n`, rounded down (before Strength). The engine's hits and every
/// reader of a monster's attack (intents, the heuristic, the features) use
/// this.
pub fn attack_shape(powers: &Powers, who: Who, base: i16, hits: u8) -> (i16, u8) {
    if matches!(who, Who::Monster(_)) {
        for &(p, n) in &crate::registry::official().shape_powers {
            if powers.get(p) > 0 {
                return (base / n as i16, hits.saturating_mul(n));
            }
        }
    }
    (base, hits)
}
