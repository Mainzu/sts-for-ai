//! Registry-lite (docs/specs/registry-lite.md): generated powers and power
//! cards loaded from a JSON content pack at runtime, and bound per combat to
//! the reserved slots (`Power::GEN`, card ids from `NUM_OFFICIAL_CARDS`).
//!
//! Loading is append-only and definitions never change once loaded, so play
//! reads them without a lock. A generated card's effects may apply generated
//! powers; their slots depend on the combat's binding, so `bind` makes one
//! card definition per (card, power slots) and keeps it for reuse.

use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use crate::cards::{CardClass, CardDef, CardId, CardKind, CardType, Row, Tag, NUM_OFFICIAL_CARDS, UNPLAYABLE, X_COST};
use crate::effects::{Amount, CostRoll, Effect, PickKind, PileKind, Quantity, Target, Types};
use crate::hooks::{
    Condition, Hook, HpLossFrom, Modifies, Replace, Replaced, Replacement, Side, Static, StaticCondition, StaticStage, Trigger,
};
use crate::monsters::{
    no_setup, pattern_ai, slots_needed, Encounter, EncounterDef, EncounterGroup, EncounterSlot, Monster, MonsterDef, MonsterKind, MoveDef,
    MoveId, PatCond, PatPick, PatternRow, MAX_ASCENSION, NO_MOVE, NUM_OFFICIAL_ENCOUNTERS, NUM_OFFICIAL_MONSTERS,
};
use crate::rng::Rng;
use crate::powers::{Power, NUM_OFFICIAL_POWERS};
use crate::potions::{parse_official_potions, parse_potion, PotionSpec};
use crate::relics::{official_relic_json, parse_official_relics, parse_relic, RelicSpec};
use crate::upgrade::{Change, Expr, Parts, Path, Section, Upgrade, LEVEL_CAP};
use crate::state::{deck_fits, MAX_MONSTERS};

/// Generated-card slots whose ids are the ones before card ids widened
/// (docs/specs/pack-slots.md, docs/specs/sparse-piles.md): slots 0-39 keep
/// them; slot 40 and up continue from `NUM_CARD_IDS`. A fight binds as many
/// as it needs, up to `MAX_CARD_SLOTS`.
pub const CARD_SLOTS: usize = 40;
/// Reserved generated-power slots per combat (`Power::GEN`).
pub const POWER_SLOTS: usize = 24;
/// Card slots below the changed copies' place in pile order: their ids are
/// the ones before the slots widened, kept so stored encodings read the same.
const LOW_SLOTS: usize = 8;
/// Changed copies (a copy with its own numbers for the combat,
/// docs/specs/sparse-piles.md) sort in a pile where the 4 variant ids
/// `VARIANT_BASE..+4` once sat, after slot 7 and before slot 8, and the
/// codec writes them as `VARIANT_BASE + rank`. Those 4 ids stay unused:
/// pile order decides seeded draws, so moving them would change the golden
/// games, the rules version and the solved DB's replays.
pub const VARIANT_BASE: usize = NUM_OFFICIAL_CARDS + 2 * LOW_SLOTS;
/// Card ids below slot 40's: official, slots 0-39 and the 4 unused ids.
pub const NUM_CARD_IDS: usize = NUM_OFFICIAL_CARDS + 2 * CARD_SLOTS + 4;
/// The first changed copy's card id; plain card ids sit below it.
pub const PARAM_BASE: u16 = 0x8000;
/// Most generated-card slots a fight binds: their ids fill up to `PARAM_BASE`.
pub const MAX_CARD_SLOTS: usize = CARD_SLOTS + (PARAM_BASE as usize - NUM_CARD_IDS) / 2;

/// The card id of a generated-card slot (its base; the next id is its `+`).
pub const fn slot_card(slot: usize) -> CardId {
    let i = if slot < LOW_SLOTS {
        NUM_OFFICIAL_CARDS + 2 * slot
    } else if slot < CARD_SLOTS {
        VARIANT_BASE + 4 + 2 * (slot - LOW_SLOTS)
    } else {
        NUM_CARD_IDS + 2 * (slot - CARD_SLOTS)
    };
    CardId(i as u16)
}

/// The generated-card slot holding card id `c` (`None` for an official
/// card, the unused ids or a changed copy).
pub const fn card_slot(c: CardId) -> Option<usize> {
    let i = c.0 as usize;
    if i < NUM_OFFICIAL_CARDS {
        None
    } else if i < VARIANT_BASE {
        Some((i - NUM_OFFICIAL_CARDS) / 2)
    } else if i < VARIANT_BASE + 4 {
        None
    } else if i < NUM_CARD_IDS {
        Some(LOW_SLOTS + (i - VARIANT_BASE - 4) / 2)
    } else if i < PARAM_BASE as usize {
        Some(CARD_SLOTS + (i - NUM_CARD_IDS) / 2)
    } else {
        None
    }
}

/// Whether card id `c` is a changed copy (`PARAM_BASE` and up).
#[inline]
pub const fn is_changed(c: CardId) -> bool {
    c.0 >= PARAM_BASE
}

/// A copy's own numbers, replacing its card's (lifetime: the combat).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub struct Overrides {
    /// The card's damage number (every `Damage` effect's amount), when it
    /// has grown (Rampage); `None` keeps the level's own numbers.
    pub damage: Option<i16>,
    /// The copy's level: its base's (0 or 1, the id pair's) or 2 and up.
    pub level: u8,
    /// Its energy cost for the combat (Snecko Oil, Confused: the game's
    /// `card.cost` set in combat; docs/specs/sparse-piles.md); `None` keeps
    /// the level's own cost.
    pub cost: Option<i8>,
}

/// A changed copy: its base (the id pair's id of the level it grew from),
/// that base's definition in its fight (a pack card's slot id names
/// different cards in different fights), its own numbers, its definition
/// (built once) and its place in pile order.
struct ChangedDef {
    base: CardId,
    base_def: usize,
    overrides: Overrides,
    def: &'static CardDef,
    ord: u64,
}

/// Most changed copies a process can hold (ids `PARAM_BASE..`).
pub const CHANGED_CAPACITY: usize = (u16::MAX - PARAM_BASE) as usize + 1;
const CHANGED_CHUNK: usize = 4096;

/// Every changed copy this process has met, append-only, in chunks
/// allocated as they fill: read without a lock.
static CHANGED: [OnceLock<Box<[OnceLock<ChangedDef>]>>; CHANGED_CAPACITY / CHANGED_CHUNK] =
    [const { OnceLock::new() }; CHANGED_CAPACITY / CHANGED_CHUNK];

fn changed_cell(i: usize) -> &'static OnceLock<ChangedDef> {
    let chunk = CHANGED[i / CHANGED_CHUNK].get_or_init(|| (0..CHANGED_CHUNK).map(|_| OnceLock::new()).collect());
    &chunk[i % CHANGED_CHUNK]
}

#[inline]
fn changed_def(c: CardId) -> &'static ChangedDef {
    debug_assert!(is_changed(c));
    changed_cell((c.0 - PARAM_BASE) as usize).get().expect("an interned changed copy")
}

/// (base id, its definition's address, overrides): equal keys are the same
/// copy, so equal copies get one card id.
type ChangedKey = (CardId, usize, Overrides);

fn changed_table() -> &'static Mutex<HashMap<ChangedKey, CardId>> {
    static T: OnceLock<Mutex<HashMap<ChangedKey, CardId>>> = OnceLock::new();
    T.get_or_init(Mutex::default)
}

thread_local! {
    /// The table's entries this thread has used, so a lookup takes no lock.
    static CHANGED_SEEN: RefCell<HashMap<ChangedKey, CardId>> = RefCell::new(HashMap::new());
}

/// A changed copy's place in pile order: where the variant ids sat, then
/// by value (base, level, damage), so a pile's order is the same in every
/// process whatever order it interned its copies in.
fn changed_ord(base: CardId, o: Overrides) -> u64 {
    let damage = o.damage.map_or(0, |d| 1 + (d as i32 + 32768) as u64);
    let cost = o.cost.map_or(0, |c| 1 + c.clamp(0, 14) as u64);
    (VARIANT_BASE as u64) << 48 | (base.0 as u64) << 32 | (o.level as u64) << 24 | damage << 4 | cost
}

/// A card's place in pile order (docs/specs/sparse-piles.md): a plain card
/// by its id, a changed copy where the variant ids once sat, by value.
#[inline]
pub fn order_key(c: CardId) -> u64 {
    if is_changed(c) { changed_def(c).ord } else { (c.0 as u64) << 48 }
}

/// The card id of card `base` (definition `b`, its binding's) with
/// overrides, interned on first use; `base` itself when the overrides are
/// its own numbers (a copy that plays alike is the same copy). At level 2
/// and up `base` is the id pair's level-1 id and the definition is its
/// upgrade applied to that level, named `X+<level>`. Panics past
/// `CHANGED_CAPACITY`, naming it.
pub fn changed_copy(base: CardId, b: &'static CardDef, mut o: Overrides) -> Result<CardId, String> {
    // The definition at the copy's level (an upgrade applied past the id
    // pair), then only differences from it are kept.
    let leveled = if o.level > b.level {
        let p = b.upgrade.apply(&b.parts(), b.level, o.level).map_err(|e| format!("{}: {e}", b.name))?;
        let stem = b.name.strip_suffix('+').unwrap_or(b.name);
        Some(b.with_parts(&p, Box::leak(format!("{stem}+{}", o.level).into_boxed_str()), o.level))
    } else {
        None
    };
    let own = leveled.as_ref().unwrap_or(b);
    if o.damage == Some(crate::state::card_damage(own)) {
        o.damage = None;
    }
    // X-cost and unplayable cards keep their cost (the game rolls only a
    // cost of 0 or more).
    if o.cost == Some(own.cost()) || own.x_cost() || own.unplayable() {
        o.cost = None;
    }
    if o.damage.is_none() && o.cost.is_none() && o.level == b.level {
        return Ok(base);
    }
    let key = (base, b as *const CardDef as usize, o);
    if let Some(c) = CHANGED_SEEN.with(|m| m.borrow().get(&key).copied()) {
        return Ok(c);
    }
    let mut t = changed_table().lock().unwrap();
    if let Some(&c) = t.get(&key) {
        drop(t);
        CHANGED_SEEN.with(|m| m.borrow_mut().insert(key, c));
        return Ok(c);
    }
    let i = t.len();
    assert!(i < CHANGED_CAPACITY, "the process holds {CHANGED_CAPACITY} changed copies (CHANGED_CAPACITY) and met a new one");
    let mut def = leveled.unwrap_or(CardDef { ..*b });
    let mut marks = Vec::new();
    if let Some(damage) = o.damage {
        let effects: Vec<Effect> = def
            .effects
            .iter()
            .map(|&e| match e {
                Effect::Damage { hits, target, .. } => Effect::Damage { amount: damage, hits, target },
                e => e,
            })
            .collect();
        def = CardDef { effects: leak(effects), ..def };
        marks.push(format!("damage={damage}/combat"));
    }
    if let Some(cost) = o.cost {
        def.cost_code = cost;
        marks.push(format!("cost={cost}/combat"));
    }
    if !marks.is_empty() {
        def.name = Box::leak(format!("{}{{{}}}", def.name, marks.join(",")).into_boxed_str());
    }
    let c = CardId(PARAM_BASE + i as u16);
    let entry = ChangedDef { base, base_def: key.1, overrides: o, def: Box::leak(Box::new(def)), ord: changed_ord(base, o) };
    let _ = changed_cell(i).set(entry);
    t.insert(key, c);
    drop(t);
    CHANGED_SEEN.with(|m| m.borrow_mut().insert(key, c));
    Ok(c)
}

/// A changed copy's base and overrides (`None` for any other card): the
/// base is the id pair's id of the level it grew from (its level-1 id at
/// level 2 and up).
pub fn copy_of(c: CardId) -> Option<(CardId, Overrides)> {
    is_changed(c).then(|| {
        let d = changed_def(c);
        (d.base, d.overrides)
    })
}

/// How many changed copies this process holds (of `CHANGED_CAPACITY`).
pub fn changed_copies() -> usize {
    changed_table().lock().unwrap().len()
}

const FREE: u16 = u16::MAX;
/// Most generated powers, and card definitions (one per card x power slots),
/// a process can hold.
const CAPACITY: usize = 4096;

/// The registry entries a combat's reserved slots hold: generated power
/// indices and card definition indices, `FREE` after the last (slots fill
/// from 0). Interned (`Binding::slots`), so a state carries an index.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Slots {
    pub powers: [u16; POWER_SLOTS],
    /// The card slots bound, in slot order (as many as the fight binds).
    pub cards: Vec<u16>,
}

const EMPTY_SLOTS: Slots = Slots { powers: [FREE; POWER_SLOTS], cards: Vec::new() };
static NO_SLOT_SET: Slots = EMPTY_SLOTS;

/// Slot sets per chunk of `SLOT_SETS`.
const SLOT_CHUNK: usize = 4096;
/// Most distinct slot sets a process can bind. Most combats whose deck
/// holds pack or generated cards bind a new one (about 0.9 a game on the
/// pack learn's decks), so a 120k-game self-play round needs over 100k.
pub const SLOT_SET_CAPACITY: usize = 1 << 20;
/// `Binding::slots` for no generated power or card.
const NO_SLOTS: u32 = u32::MAX;

/// Every slot set this process has bound, append-only, in chunks allocated
/// as they fill: `Binding::slots` indexes it, read without a lock.
static SLOT_SETS: [OnceLock<Box<[OnceLock<Slots>]>>; SLOT_SET_CAPACITY.div_ceil(SLOT_CHUNK)] =
    [const { OnceLock::new() }; SLOT_SET_CAPACITY.div_ceil(SLOT_CHUNK)];

fn slot_cell(i: usize) -> &'static OnceLock<Slots> {
    let chunk = SLOT_SETS[i / SLOT_CHUNK].get_or_init(|| (0..SLOT_CHUNK).map(|_| OnceLock::new()).collect());
    &chunk[i % SLOT_CHUNK]
}

static SLOT_INDEX: OnceLock<Mutex<HashMap<Slots, u32>>> = OnceLock::new();

/// How many distinct slot sets this process has bound (of
/// `SLOT_SET_CAPACITY`).
pub fn slot_sets_bound() -> usize {
    SLOT_INDEX.get().map_or(0, |t| t.lock().unwrap().len())
}

/// The interned index of a slot set (`NO_SLOTS` for the empty one).
fn intern_slots(s: &Slots) -> Result<u32, String> {
    if *s == EMPTY_SLOTS {
        return Ok(NO_SLOTS);
    }
    let mut t = SLOT_INDEX.get_or_init(Mutex::default).lock().unwrap();
    if let Some(&i) = t.get(s) {
        return Ok(i);
    }
    let i = t.len();
    if i >= SLOT_SET_CAPACITY {
        return Err("registry full (slot sets)".into());
    }
    let _ = slot_cell(i).set(s.clone());
    t.insert(s.clone(), i as u32);
    Ok(i as u32)
}

/// Which registry entries a combat's reserved slots hold: an interned slot
/// set (`slots`) for the generated powers and cards. Small, as states are
/// cloned in search. Changed copies need no binding: their card ids are
/// interned process-wide by value (`changed_copy`).
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct Binding {
    /// Index into `SLOT_SETS`, `NO_SLOTS` for no generated power or card.
    slots: u32,
    /// Bound generated powers (slots `0..n_powers`).
    n_powers: u8,
    /// Whether a bound power has an after-block replacement row (derived
    /// from the slots; the damage path skips those passes without one,
    /// docs/specs/after-block.md).
    after_block: bool,
}

impl Default for Binding {
    fn default() -> Binding {
        Binding { slots: NO_SLOTS, n_powers: 0, after_block: false }
    }
}

impl std::fmt::Debug for Binding {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = self.slot_set();
        f.debug_struct("Binding").field("powers", &s.powers).field("cards", &s.cards).finish()
    }
}

impl Binding {
    /// The generated powers and cards bound.
    #[inline]
    pub fn slot_set(&self) -> &'static Slots {
        if self.slots == NO_SLOTS {
            &NO_SLOT_SET
        } else {
            slot_cell(self.slots as usize).get().expect("interned slot set")
        }
    }

    /// A binding of these slots.
    fn of(s: &Slots) -> Result<Binding, String> {
        let n = s.powers.iter().take_while(|&&x| x != FREE).count();
        let after_block = s.powers[..n]
            .iter()
            .any(|&i| POWERS[i as usize].get().expect("bound power").replacements.iter().any(|r| r.event.after_block()));
        Ok(Binding { slots: intern_slots(s)?, n_powers: n as u8, after_block })
    }

    /// Whether `c` names a card this combat can hold: official, a bound
    /// generated slot, or an interned changed copy of one of those whose
    /// base has the same definition here.
    pub fn is_bound(&self, c: CardId) -> bool {
        let i = c.0 as usize;
        if is_changed(c) {
            let Some(d) = changed_cell((c.0 - PARAM_BASE) as usize).get() else { return false };
            return self.is_bound(d.base) && self.def(d.base) as *const CardDef as usize == d.base_def;
        }
        i < NUM_OFFICIAL_CARDS || card_slot(c).is_some_and(|k| k < self.slot_set().cards.len())
    }
    pub fn is_empty(&self) -> bool {
        self.slots == NO_SLOTS
    }

    /// Whether a bound power has an after-block replacement row (no
    /// official power has one).
    #[inline]
    pub fn has_after_block(&self) -> bool {
        self.after_block
    }

    /// Every power a combat with this binding can hold: the official ones,
    /// then the bound slots (slots fill from 0).
    #[inline]
    pub fn powers_in_play(&self) -> &'static [Power] {
        &Power::ALL_WITH_SLOTS[..NUM_OFFICIAL_POWERS + self.n_powers as usize]
    }

    #[inline]
    /// A card's definition: the official files for official cards, the bound
    /// definition for a reserved slot (base and `+` alike).
    pub fn def(&self, c: CardId) -> &'static CardDef {
        if (c.0 as usize) < NUM_OFFICIAL_CARDS {
            return c.def();
        }
        if is_changed(c) {
            return changed_def(c).def;
        }
        let k = card_slot(c).expect("a card id");
        let cards = &self.slot_set().cards;
        assert!(k < cards.len(), "card slot {} is not bound in this combat", c.0);
        let i = cards[k];
        let b = CARD_DEFS[i as usize].get().expect("bound card definition");
        // A slot's second id is its card at level 1.
        if c.0 & 1 == 1 { b.up } else { b.def }
    }

    #[inline]
    /// A power's hooks: the official files for official powers, the bound
    /// generated power's for a reserved slot.
    pub fn hooks(&self, p: Power) -> &'static [Hook] {
        match self.generated(p) {
            None => crate::hooks::hooks(p),
            Some(g) => g.hooks,
        }
    }

    #[inline]
    /// A power's static modifier rows (a generated power's as loaded).
    pub fn statics(&self, p: Power) -> &'static [crate::hooks::Static] {
        match self.generated(p) {
            None => crate::hooks::statics(p),
            Some(g) => g.statics,
        }
    }

    #[inline]
    /// A power's replacement rows (a generated power's as loaded).
    pub fn replacements(&self, p: Power) -> &'static [crate::hooks::Replacement] {
        match self.generated(p) {
            None => crate::hooks::replacements(p),
            Some(g) => g.replacements,
        }
    }

    #[inline]
    /// A power's fields beside its rows, official or bound generated, as
    /// its data row gives them.
    pub fn rules(&self, p: Power) -> &'static PowerRules {
        match self.generated(p) {
            None => &official().powers[p as usize].rules,
            Some(g) => &g.rules,
        }
    }

    #[inline]
    /// Whether applying `amount` of `p` is a debuff (Artifact blocks it).
    pub fn is_debuff(&self, p: Power, amount: i16) -> bool {
        self.rules(p).is_debuff(amount)
    }

    #[inline]
    /// The card type a power forbids its owner to play (`forbids`;
    /// Entangled).
    pub fn forbids(&self, p: Power) -> Option<CardType> {
        self.rules(p).forbids
    }

    /// The card type whose cost a power caps while held, and the cap
    /// (`sets_cost`; Corruption).
    pub fn sets_cost(&self, p: Power) -> Option<(CardType, i8)> {
        self.rules(p).sets_cost
    }

    /// The powers in play that may carry a card rule or a `block_loss` (`forbids`,
    /// `sets_cost`, `exhausts_played`): the official ones whose rows have
    /// one (none today), then the bound generated slots.
    pub fn rule_powers(&self) -> impl Iterator<Item = Power> + '_ {
        official().rule_powers.iter().copied().chain(self.powers_in_play()[NUM_OFFICIAL_POWERS..].iter().copied())
    }

    /// The powers in play that may have a `CardDrawn` hook: the official
    /// ones whose rows have one (none today), then the bound generated
    /// slots.
    pub fn draw_hook_powers(&self) -> impl Iterator<Item = Power> + '_ {
        official().draw_hook_powers.iter().copied().chain(self.powers_in_play()[NUM_OFFICIAL_POWERS..].iter().copied())
    }

    /// How many HP losses a combat counts (`CombatState::times_lost_hp`):
    /// the largest base cost among the bound cards that cost less per HP
    /// loss, 0 when none is bound (official content).
    pub fn hp_loss_cap(&self) -> u8 {
        let s = self.slot_set();
        // Changed copies keep their base's cost (grown damage) or an
        // upgrade's, which the slot's two levels bound.
        let slot_defs = s.cards.iter().flat_map(|&i| {
            let b = CARD_DEFS[i as usize].get().expect("bound card definition");
            [b.def, b.up]
        });
        slot_defs.filter(|d| d.cost_less_per_hp_loss).map(|d| d.cost() as u8).max().unwrap_or(0)
    }

    /// The most block a power's owner loses at their turn start
    /// (`block_loss`; Barricade 0).
    pub fn block_loss(&self, p: Power) -> Option<i16> {
        self.rules(p).block_loss
    }

    /// The card type a power exhausts when its owner plays one
    /// (`exhausts_played`; Corruption).
    pub fn exhausts_played(&self, p: Power) -> Option<CardType> {
        self.rules(p).exhausts_played
    }

    /// The card type whose unplayable cards a power lets its owner play
    /// (`plays_unplayable`; Blue Candle).
    pub fn plays_unplayable(&self, p: Power) -> Option<CardType> {
        self.rules(p).plays_unplayable
    }

    /// The registry id of a bound slot's power or card (`None` for official
    /// content or a free slot).
    pub fn power_id(&self, p: Power) -> Option<&'static str> {
        self.generated(p).map(|g| g.id)
    }

    fn generated(&self, p: Power) -> Option<&'static GenPower> {
        let k = p as usize;
        if k < NUM_OFFICIAL_POWERS {
            return None;
        }
        let i = self.slot_set().powers[k - NUM_OFFICIAL_POWERS];
        assert!(i != FREE, "power slot {p:?} is not bound in this combat");
        Some(POWERS[i as usize].get().expect("bound power"))
    }
}

struct GenPower {
    id: &'static str,
    hooks: &'static [Hook],
    rules: PowerRules,
    statics: &'static [Static],
    replacements: &'static [Replacement],
}

/// When a power that lands fresh skips its first round end
/// (`just_applied`: no tick and no hooks until then).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct SkipsFirstRound {
    /// When a monster applies it (Weak, Frail: the game's `justApplied`
    /// for a monster source, whatever the turn).
    pub from_monster: bool,
    /// When a monster applies it after the player's turn has ended
    /// (Vulnerable, NoBlock: the game's `turnHasEnded && isSourceMonster`;
    /// `CombatState::turn_has_ended`). Applied during the player's turn
    /// (Spore Cloud on a Fungi Beast the player's card kills), it ticks.
    pub from_monster_after_turn_end: bool,
    /// When a monster gains it (Ritual's first turn).
    pub on_monster: bool,
}

/// A power's fields beside its hooks, statics and replacements, official
/// or pack, as its data row gives them.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct PowerRules {
    /// Applying it is a debuff (Artifact blocks it).
    pub debuff: bool,
    /// Applying a negative amount is a debuff too (Strength, Dexterity).
    pub debuff_if_negative: bool,
    /// The engine's own amount can go below 0: Strength, Dexterity. The
    /// game's `canGoNegative` also marks Focus (no engine power) and Wraith
    /// Form, but the engine stores WraithForm with the opposite sign to the
    /// game (the game's -n is the engine's +n, its hook applying Dexterity
    /// -1 per stack), so its engine amount never goes negative and it has
    /// no flag. Without it a negative application
    /// is the game's `ReducePowerAction`: floored at 0, nothing when not
    /// held, no debuff and no `OwnerApplied` hooks.
    pub can_go_negative: bool,
    pub skips_first_round: SkipsFirstRound,
    /// A monster holding it attacks with `n` times the hits at the base
    /// divided by `n`, rounded down, before Strength (Split Hits: 2).
    /// Official powers only: `state::attack_shape` has no binding.
    pub attack_shape: Option<u8>,
    /// Cards of this type can't be played while the owner holds the power
    /// (Entangled: Attack).
    pub forbids: Option<CardType>,
    /// While held, the owner's cards of this type cost at most this much
    /// (Corruption: Skill 0); X-cost and unplayable cards are unchanged.
    pub sets_cost: Option<(CardType, i8)>,
    /// While held, a card of this type the owner plays exhausts (Corruption:
    /// Skill).
    pub exhausts_played: Option<CardType>,
    /// While held, the owner's unplayable cards of this type can be played,
    /// at cost 0 (Blue Candle: Curse; Medical Kit: Status).
    pub plays_unplayable: Option<CardType>,
    /// The most block its owner loses at the start of their turn while
    /// holding it (Barricade's 0 keeps all; Calipers' 15); the fewest of
    /// the held powers' wins. Read for the player.
    pub block_loss: Option<i16>,
    /// The amount stays within `-cap..=cap` when applied (the game's
    /// `stackPower` and `reducePower` caps: Strength, Dexterity and
    /// Shackled 999, Plated Armor 999, Poison 9999).
    pub cap: Option<i16>,
}

impl PowerRules {
    /// Whether applying `amount` is a debuff.
    #[inline]
    pub fn is_debuff(&self, amount: i16) -> bool {
        self.debuff || (self.debuff_if_negative && amount < 0)
    }

    fn has_card_rule(&self) -> bool {
        self.forbids.is_some()
            || self.sets_cost.is_some()
            || self.exhausts_played.is_some()
            || self.plays_unplayable.is_some()
            || self.block_loss.is_some()
    }
}

/// A generated power as loaded (compared on reload).
#[derive(Clone, Debug, PartialEq)]
struct PowerSpec {
    hooks: Vec<Hook>,
    rules: PowerRules,
    statics: Vec<Static>,
    replacements: Vec<Replacement>,
}

/// A generated card as loaded: each row's effects with every generated
/// power left as `Power::GEN[0]` and named in `gen` (same index); row 0 is
/// the on-play row (`Always`).
#[derive(Clone, Debug, PartialEq)]
struct CardSpec {
    /// Raw: `X_COST`, `UNPLAYABLE` or the energy cost.
    cost: i8,
    ty: CardType,
    exhaust: bool,
    ethereal: bool,
    retain: bool,
    innate: bool,
    playable_if: Option<Condition>,
    cost_less_per_hp_loss: bool,
    tags: u8,
    rows: Vec<(Condition, Vec<Effect>, Vec<Option<String>>)>,
    turn_end: Vec<Effect>,
    exhausted: Vec<Effect>,
    other_played: Vec<Effect>,
    plays_per_turn: u8,
    /// The entry's `upgrade` block (with its `match_level` effects).
    upgrade: Option<Upgrade>,
    /// The entry's `max_level` (`LEVEL_CAP` for `null`).
    max_level: Option<u8>,
    /// `max_level: null`: the card upgrades as far as its numbers fit.
    no_limit: bool,
    /// The entry that is this card at level 1 (a unique upgrade).
    successor: Option<String>,
}

impl CardSpec {
    fn gens(&self) -> impl Iterator<Item = &String> {
        self.rows.iter().flat_map(|(_, _, g)| g.iter().flatten())
    }

    /// Every row's effects.
    fn effects(&self) -> Vec<Effect> {
        self.rows.iter().flat_map(|(_, e, _)| e.iter().copied()).collect()
    }

    fn parts(&self) -> Parts {
        Parts {
            cost: self.cost,
            keywords: [self.exhaust, self.ethereal, self.innate, self.retain],
            rows: self.rows.iter().map(|(_, e, _)| e.clone()).collect(),
            turn_end: self.turn_end.clone(),
            exhausted: self.exhausted.clone(),
        }
    }

    fn with_parts(&self, p: Parts) -> CardSpec {
        let [exhaust, ethereal, innate, retain] = p.keywords;
        let rows = self.rows.iter().zip(p.rows).map(|((c, _, g), e)| (*c, e, g.clone())).collect();
        CardSpec { cost: p.cost, exhaust, ethereal, innate, retain, rows, turn_end: p.turn_end, exhausted: p.exhausted, ..self.clone() }
    }

    /// Every level the entry's upgrade reaches applies (paths name its
    /// numbers, numbers stay in range). With `max_level: null` the card
    /// upgrades as far as its numbers stay in range (Searing Blow: 252).
    fn checked(mut self) -> Result<CardSpec, String> {
        if let Some(u) = &self.upgrade {
            let top = self.max_level.unwrap_or(1);
            if top == 0 {
                return Err("max_level 0 with an upgrade block".into());
            }
            let mut p = self.parts();
            for n in 1..=top {
                if let Err(e) = u.step(&mut p, n) {
                    if !self.no_limit || n == 1 {
                        return Err(e);
                    }
                    self.max_level = Some(n - 1);
                    break;
                }
            }
        }
        Ok(self)
    }
}

/// The id of the entry that is card `id` at level 1: its `successor`, or
/// (an older file) an entry `X+` beside an `X` with neither an upgrade
/// block nor a successor. `has` says whether an id is loaded.
fn plus_id(id: &str, s: &CardSpec, has: &dyn Fn(&str) -> bool) -> Option<String> {
    if let Some(n) = &s.successor {
        return Some(n.clone());
    }
    let p = format!("{id}+");
    (s.upgrade.is_none() && has(&p)).then_some(p)
}

/// A card entry's level-1 definition and its max level: `plus` is its
/// successor entry when it has one (a unique upgrade, max level 1); else
/// the entry's upgrade block at level 1; else the entry itself (no
/// upgrade, max level 0).
fn levels(id: &str, s: &CardSpec, plus: Option<&CardSpec>) -> Result<(CardSpec, u8), String> {
    if s.successor.is_some() && s.upgrade.is_some() {
        return Err(format!("card {id:?}: an upgrade block and a successor both"));
    }
    match (plus, &s.upgrade) {
        (Some(_), Some(_)) => Err(format!("card {id:?}: an upgrade block and an {:?} entry both", format!("{id}+"))),
        (Some(p), None) => match s.max_level {
            Some(m) if m != 1 => Err(format!("card {id:?}: max_level {m} with a successor (its one upgrade)")),
            _ => Ok((p.clone(), 1)),
        },
        (None, Some(u)) => {
            let p = u.apply(&s.parts(), 0, 1).map_err(|e| format!("card {id:?}: {e}"))?;
            Ok((s.with_parts(p), s.max_level.unwrap_or(1)))
        }
        (None, None) => match s.max_level {
            Some(m) if m != 0 => Err(format!("card {id:?}: max_level {m} without an upgrade")),
            _ => Ok((s.clone(), 0)),
        },
    }
}

/// A bound pack card: its level-0 and level-1 definitions (the slot's two
/// ids; the same definition for a card without an upgrade).
struct BoundCard {
    def: &'static CardDef,
    up: &'static CardDef,
    /// The pack entry's id (without `gen:`).
    id: &'static str,
    /// Whether the slot's first id is the card at level 0.
    at_level_0: bool,
}

/// A pack monster as loaded (compared on reload): split children resolved
/// to kinds.
#[derive(Clone, Debug, PartialEq)]
struct MonsterSpec {
    hp: (i16, i16),
    start_block: i16,
    start_powers: Vec<(Power, i16)>,
    /// Pack start powers, as registry power indices.
    gen_powers: Vec<(u16, i16)>,
    moves: Vec<(String, Vec<Effect>)>,
    pattern: Vec<(Vec<PatCond>, PatPick)>,
    split: Option<(MoveId, [MonsterKind; 2])>,
    rolled_attack: Option<(i16, i16)>,
    rolled_powers: Vec<(Power, i16, i16)>,
    /// The monster at higher ascension levels (docs/specs/ascension.md):
    /// (the level its row applies from, the spec with every row up to it
    /// applied), ascending.
    levels: Vec<(u8, MonsterSpec)>,
    /// The `ascension` rows as the content file writes them (empty for none).
    rows: RowsText,
}

/// The rows' text, written back but not compared: a pack reloaded with its
/// keys in another order (`selfplay.load_content` sorts them) is the same
/// pack; `levels` compares what they mean.
#[derive(Clone, Debug, Default)]
struct RowsText(String);

impl PartialEq for RowsText {
    fn eq(&self, _: &Self) -> bool {
        true
    }
}

/// A monster's definition from its spec, with its levels' definitions.
fn def_of_spec(s: &MonsterSpec, name: &'static str, setup: fn(&mut Monster, &mut Rng)) -> MonsterDef {
    let moves: Vec<MoveDef> = s.moves.iter().map(|(n, es)| MoveDef { name: Box::leak(n.clone().into_boxed_str()), effects: leak(es.clone()) }).collect();
    let pattern: Vec<PatternRow> = s.pattern.iter().map(|(when, then)| PatternRow { when: leak(when.clone()), then: *then }).collect();
    let (split_move, split_into) = s.split.unwrap_or((NO_MOVE, [MonsterKind::None; 2]));
    let levels: Vec<(u8, &'static MonsterDef)> = s.levels.iter().map(|(from, l)| (*from, &*Box::leak(Box::new(def_of_spec(l, name, setup))))).collect();
    MonsterDef {
        name,
        hp_min: s.hp.0,
        hp_max: s.hp.1,
        moves: leak(moves),
        ai: pattern_ai,
        pattern: leak(pattern),
        start_block: s.start_block,
        start_powers: leak(s.start_powers.clone()),
        gen_powers: leak(s.gen_powers.clone()),
        setup,
        split_move,
        split_into,
        rolled_attack: s.rolled_attack,
        rolled_powers: leak(s.rolled_powers.clone()),
        levels: leak(levels),
        ascension_rows: Box::leak(s.rows.0.clone().into_boxed_str()),
    }
}

/// Pack monsters a process can hold: kinds `NUM_OFFICIAL_MONSTERS..=254`.
const MONSTER_CAPACITY: usize = 255 - NUM_OFFICIAL_MONSTERS;
static MONSTER_DEFS: [OnceLock<&'static MonsterDef>; MONSTER_CAPACITY] = [const { OnceLock::new() }; MONSTER_CAPACITY];

/// A pack monster's definition (`MonsterKind::def` for non-official kinds).
pub fn monster_def(k: MonsterKind) -> &'static MonsterDef {
    MONSTER_DEFS[k.0 as usize - NUM_OFFICIAL_MONSTERS].get().expect("a loaded pack monster")
}

/// Pack encounters a process can hold: `NUM_OFFICIAL_ENCOUNTERS..=254`.
const ENCOUNTER_CAPACITY: usize = 255 - NUM_OFFICIAL_ENCOUNTERS;
static ENCOUNTER_DEFS: [OnceLock<&'static EncounterDef>; ENCOUNTER_CAPACITY] = [const { OnceLock::new() }; ENCOUNTER_CAPACITY];

/// A pack encounter's definition (`Encounter::def` for non-official ones).
pub fn encounter_def(e: Encounter) -> &'static EncounterDef {
    ENCOUNTER_DEFS[e.0 as usize - NUM_OFFICIAL_ENCOUNTERS].get().expect("a loaded pack encounter")
}

/// A loaded pack encounter by its name `gen:<id>`.
pub fn pack_encounter(name: &str) -> Option<Encounter> {
    let id = name.strip_prefix("gen:")?;
    table().lock().unwrap().encounters.get(id).map(|(e, _)| *e)
}

static POWERS: [OnceLock<GenPower>; CAPACITY] = [const { OnceLock::new() }; CAPACITY];
static CARD_DEFS: [OnceLock<BoundCard>; CAPACITY] = [const { OnceLock::new() }; CAPACITY];

/// A card of a pool (docs/specs/discovery.md): an official card, or a pack
/// entry by id (its slot differs per fight), with its type.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PoolCard {
    pub official: Option<CardId>,
    pub pack: Option<&'static str>,
    pub ty: CardType,
}

/// A list the game draws random cards from (docs/extending.md "Pool or
/// set"): a class's in-combat pool, as a pack's `pools` names it.
#[derive(Debug)]
pub struct PoolDef {
    pub name: &'static str,
    pub cards: &'static [PoolCard],
}

/// Pools a process can hold (`Effect::Discover` names one by a byte).
const POOL_CAPACITY: usize = 255;
static POOL_DEFS: [OnceLock<PoolDef>; POOL_CAPACITY] = [const { OnceLock::new() }; POOL_CAPACITY];

thread_local! {
    /// The pools a pack being loaded may name, by index: the loaded ones,
    /// then its own (`load_pack` sets them while it parses).
    static POOL_NAMES: RefCell<Vec<String>> = const { RefCell::new(Vec::new()) };
}

/// Clears `POOL_NAMES` when `load_pack` returns, whichever way.
struct PoolNamesGuard;

impl Drop for PoolNamesGuard {
    fn drop(&mut self) {
        POOL_NAMES.with(|p| p.borrow_mut().clear());
    }
}

/// Loaded pool `i`.
pub fn pool_def(i: u8) -> Option<&'static PoolDef> {
    POOL_DEFS.get(i as usize)?.get()
}

/// `MakeRandom`'s pool `"Class"` in a relic's hook: the player's class
/// pool, the loaded pool named as the fight's character (Dead Branch, the
/// game's `returnTrulyRandomCardInCombat`; docs/specs/blocked-relics.md
/// step 5). Never a loaded pool's index (`POOL_CAPACITY` is below it).
pub const CLASS_POOL: u8 = u8::MAX;

/// The pool `pool` names in a fight of `character`: itself, or for
/// `CLASS_POOL` the loaded pool named as the character (`None` when none is).
pub fn fight_pool(pool: u8, character: crate::character::Character) -> Option<u8> {
    if pool != CLASS_POOL {
        return Some(pool);
    }
    (0..POOL_CAPACITY).map_while(|i| POOL_DEFS[i].get()).position(|p| p.name.eq_ignore_ascii_case(character.name())).map(|i| i as u8)
}

#[derive(Default)]
struct Table {
    /// Generated power id -> (index, its spec as loaded, for redefinition checks).
    powers: HashMap<String, (u16, PowerSpec)>,
    cards: HashMap<String, CardSpec>,
    /// Pack monster id -> (its kind, its spec as loaded).
    monsters: HashMap<String, (MonsterKind, MonsterSpec)>,
    /// Pack encounter id -> (its handle, its definition as loaded).
    encounters: HashMap<String, (Encounter, EncounterDef)>,
    /// Pack relic id (without `gen:`) -> its spec as loaded.
    relics: HashMap<String, RelicSpec>,
    /// Pack potion id (without `gen:`) -> its spec as loaded.
    potions: HashMap<String, PotionSpec>,
    /// Successor id -> the card it is the level-1 of.
    successor_of: HashMap<String, String>,
    /// (card id, the slots its generated powers sit in, whether an `X+`
    /// entry upgrades it, whether the deck holds it at level 0) -> card
    /// definition index.
    defs: HashMap<(String, Vec<u16>, bool, bool), u16>,
    n_defs: usize,
    /// Pools by index: (name, card names as loaded).
    pools: Vec<(String, Vec<String>)>,
}

fn table() -> &'static Mutex<Table> {
    static T: OnceLock<Mutex<Table>> = OnceLock::new();
    T.get_or_init(Mutex::default)
}

fn leak<T>(v: Vec<T>) -> &'static [T] {
    Box::leak(v.into_boxed_slice())
}

/// Loads a content pack (JSON). Append-only: an id already loaded with the
/// same definition is skipped, with another definition is an error (nothing
/// from the pack is loaded then). Returns the pack's content hash (FNV-1a of
/// its text).
pub fn load_pack(text: &str) -> Result<u64, String> {
    let v = json::parse(text)?;
    let version = file_version(&v).map_err(|e| format!("content pack: {e}"))?;
    let mut t = table().lock().unwrap();
    // Pools (docs/specs/discovery.md): names first, so this pack's powers,
    // cards and potions may name its own; their cards are checked below.
    let mut pools: Vec<(String, Vec<String>)> = Vec::new();
    match v.get("pools") {
        None => {}
        Some(json::Value::Obj(kv)) => {
            for (name, list) in kv {
                let cards: Vec<String> = list
                    .items()
                    .iter()
                    .map(|c| c.str().map(str::to_string).ok_or_else(|| format!("pool {name:?}: a card name, got {c:?}")))
                    .collect::<Result<_, _>>()?;
                if let Some(c) = cards.iter().enumerate().find(|(i, c)| cards[..*i].contains(c)).map(|(_, c)| c) {
                    return Err(format!("pool {name:?}: {c:?} twice"));
                }
                match t.pools.iter().find(|(n, _)| n == name) {
                    Some((_, c)) if *c == cards => {}
                    Some(_) => return Err(format!("pool {name:?} redefined")),
                    None if pools.iter().any(|(n, _)| n == name) => return Err(format!("pool {name:?} twice in the pack")),
                    None => pools.push((name.clone(), cards)),
                }
            }
        }
        Some(x) => return Err(format!("pools: expected an object of name: [cards], got {x:?}")),
    }
    if t.pools.len() + pools.len() > POOL_CAPACITY {
        return Err("registry full (pools)".into());
    }
    let _pool_names = PoolNamesGuard;
    POOL_NAMES.with(|p| *p.borrow_mut() = t.pools.iter().chain(&pools).map(|(n, _)| n.clone()).collect());
    // The pack's new powers by name, in order (their indices once
    // committed): a hook may apply one named later in the pack.
    let mut new_ids: Vec<&str> = Vec::new();
    for p in v.get("powers").map(json::Value::items).unwrap_or(&[]) {
        let id = p.get("id").and_then(json::Value::str).ok_or("power without an id")?;
        if !t.powers.contains_key(id) && !new_ids.contains(&id) {
            new_ids.push(id);
        }
    }
    let pack_power = |name: &str| -> Option<u16> {
        t.powers.get(name).map(|(i, _)| *i).or_else(|| new_ids.iter().position(|&i| i == name).map(|j| (t.powers.len() + j) as u16))
    };
    let mut parsed = Vec::new();
    for p in v.get("powers").map(json::Value::items).unwrap_or(&[]) {
        let id = p.get("id").and_then(json::Value::str).ok_or("power without an id")?.to_string();
        let spec = parse_power(p, &pack_power, version).map_err(|e| format!("power {id:?}: {e}"))?;
        if spec.rules.attack_shape.is_some() {
            return Err(format!("power {id:?}: attack_shape is for official powers only (state::attack_shape reads no binding)"));
        }
        parsed.push((id, spec));
    }
    let mut powers = Vec::new();
    for (id, spec) in parsed {
        match t.powers.get(&id) {
            Some((_, s)) if *s == spec => {}
            Some(_) => return Err(format!("generated power {id:?} redefined")),
            None if powers.iter().any(|(i, _): &(String, _)| *i == id) => return Err(format!("power {id:?} twice in the pack")),
            None => powers.push((id, spec)),
        }
    }
    let known = |t: &Table, powers: &[(String, PowerSpec)], name: &str| {
        t.powers.contains_key(name) || powers.iter().any(|(i, _)| i == name)
    };
    let mut cards = Vec::new();
    for c in v.get("cards").map(json::Value::items).unwrap_or(&[]) {
        let id = c.get("id").and_then(json::Value::str).ok_or("card without an id")?.to_string();
        let spec = parse_card(c, version).map_err(|e| format!("card {id:?}: {e}"))?;
        if let Some(name) = spec.gens().find(|n| !known(&t, &powers, n)) {
            return Err(format!("card {id:?} applies unknown power {name:?}"));
        }
        match t.cards.get(&id) {
            Some(s) if *s == spec => {}
            Some(_) => return Err(format!("generated card {id:?} redefined")),
            None if cards.iter().any(|(i, _): &(String, _)| *i == id) => return Err(format!("card {id:?} twice in the pack")),
            None => cards.push((id, spec)),
        }
    }
    // A successor is an entry of the same pack, named by one card, with no
    // upgrade of its own; an older file's `X+` entry is the upgrade of `X`
    // (loaded before or in this pack). Every base's levels check out.
    let in_pack = |n: &str| cards.iter().find(|(i, _)| i == n).map(|(_, s)| s);
    for (id, spec) in &cards {
        if let Some(n) = &spec.successor {
            let succ = in_pack(n).ok_or_else(|| format!("card {id:?}: its successor {n:?} is not an entry of the pack"))?;
            let namers = cards.iter().filter(|(_, s)| s.successor.as_deref() == Some(n.as_str())).count() + t.successor_of.contains_key(n) as usize;
            if namers > 1 {
                return Err(format!("card {n:?}: the successor of two cards"));
            }
            if succ.upgrade.is_some() || succ.successor.is_some() || succ.max_level.is_some() {
                return Err(format!("card {n:?}: a successor has no upgrade, successor or max_level of its own"));
            }
        }
        let has = |n: &str| in_pack(n).is_some() || t.cards.contains_key(n);
        // `X+` names a card's level 1: no other entry may take that id.
        if (spec.upgrade.is_some() || spec.successor.as_ref().is_some_and(|n| *n != format!("{id}+"))) && has(&format!("{id}+")) {
            return Err(format!("card {id:?}: an entry {:?} beside its upgrade (the name of its level 1)", format!("{id}+")));
        }
        let plus = plus_id(id, spec, &has).and_then(|p| in_pack(&p).or_else(|| t.cards.get(&p)));
        levels(id, spec, plus)?;
        if let Some(base) = id.strip_suffix('+').and_then(|b| t.cards.get(b)) {
            if base.successor.is_none() && base.upgrade.is_none() {
                levels(id.strip_suffix('+').unwrap(), base, Some(spec))?;
            }
        }
    }
    // Monsters: a split child is official or loaded before its parent
    // (an earlier pack, or earlier in this one), so splits can't loop.
    let mut monsters: Vec<(String, MonsterKind, MonsterSpec)> = Vec::new();
    for m in v.get("monsters").map(json::Value::items).unwrap_or(&[]) {
        let id = m.get("id").and_then(json::Value::str).ok_or("monster without an id")?.to_string();
        let resolve = |name: &str| -> Option<MonsterKind> {
            let gen = name.strip_prefix("gen:")?;
            t.monsters.get(gen).map(|(k, _)| *k).or_else(|| monsters.iter().find(|(i, _, _)| i == gen).map(|(_, k, _)| *k))
        };
        // A pack power loaded before, or earlier in this pack (its index
        // once committed, in order after the loaded ones).
        let power = |name: &str| -> Option<u16> {
            t.powers.get(name).map(|(i, _)| *i).or_else(|| powers.iter().position(|(i, _)| i == name).map(|j| (t.powers.len() + j) as u16))
        };
        let spec = parse_monster(m, &resolve, &power).map_err(|e| format!("monster {id:?}: {e}"))?;
        // Slots of a split tree; children from this pack aren't defined yet.
        fn slots(k: MonsterKind, pending: &[(String, MonsterKind, MonsterSpec)]) -> usize {
            match pending.iter().find(|(_, pk, _)| *pk == k) {
                Some((_, _, sp)) => sp.split.map_or(1, |(_, [a, b])| slots(a, pending) + slots(b, pending)),
                None => slots_needed(k),
            }
        }
        let n = spec.split.map_or(1, |(_, [a, b])| slots(a, &monsters) + slots(b, &monsters));
        if n > MAX_MONSTERS {
            return Err(format!("monster {id:?}: its splits need {n} slots, more than {MAX_MONSTERS}"));
        }
        match t.monsters.get(&id) {
            Some((_, s)) if *s == spec => {}
            Some(_) => return Err(format!("pack monster {id:?} redefined")),
            None if monsters.iter().any(|(i, _, _)| *i == id) => return Err(format!("monster {id:?} twice in the pack")),
            None => {
                let i = t.monsters.len() + monsters.len();
                if i >= MONSTER_CAPACITY {
                    return Err("registry full (monsters)".into());
                }
                monsters.push((id, MonsterKind((NUM_OFFICIAL_MONSTERS + i) as u8), spec));
            }
        }
    }
    // Encounters: monsters by their official game names or `gen:<id>` of a
    // pack monster loaded before or earlier in this pack.
    let mut encounters: Vec<(String, Encounter, EncounterDef)> = Vec::new();
    for e in v.get("encounters").map(json::Value::items).unwrap_or(&[]) {
        let resolve = |name: &str| -> Option<MonsterKind> {
            match name.strip_prefix("gen:") {
                Some(gen) => t.monsters.get(gen).map(|(k, _)| *k).or_else(|| monsters.iter().find(|(i, _, _)| i == gen).map(|(_, k, _)| *k)),
                None => official().monsters.iter().position(|d| d.name == name).filter(|&j| j > 0).map(|j| MonsterKind(j as u8)),
            }
        };
        fn slots(k: MonsterKind, pending: &[(String, MonsterKind, MonsterSpec)]) -> usize {
            match pending.iter().find(|(_, pk, _)| *pk == k) {
                Some((_, _, sp)) => sp.split.map_or(1, |(_, [a, b])| slots(a, pending) + slots(b, pending)),
                None => slots_needed(k),
            }
        }
        let (id, group, ss) = parse_encounter(e, &resolve, &|k| slots(k, &monsters))?;
        let def = EncounterDef { name: "", group, slots: ss };
        match t.encounters.get(&id) {
            Some((_, d)) if d.group == def.group && d.slots == def.slots => {}
            Some(_) => return Err(format!("pack encounter {id:?} redefined")),
            None if encounters.iter().any(|(i, _, _)| *i == id) => return Err(format!("encounter {id:?} twice in the pack")),
            None => {
                let i = t.encounters.len() + encounters.len();
                if i >= ENCOUNTER_CAPACITY {
                    return Err("registry full (encounters)".into());
                }
                encounters.push((id, Encounter((NUM_OFFICIAL_ENCOUNTERS + i) as u8), def));
            }
        }
    }
    // Relics: official powers, or pack powers loaded before or in this pack.
    let mut relics: Vec<(String, RelicSpec)> = Vec::new();
    for r in v.get("relics").map(json::Value::items).unwrap_or(&[]) {
        let power = |name: &str| -> Option<u16> {
            t.powers.get(name).map(|(i, _)| *i).or_else(|| powers.iter().position(|(i, _)| i == name).map(|j| (t.powers.len() + j) as u16))
        };
        let (id, spec) = parse_relic(r, &official_power, Some(&power), version)?;
        match t.relics.get(&id) {
            Some(s) if *s == spec => {}
            Some(_) => return Err(format!("pack relic {id:?} redefined")),
            None if relics.iter().any(|(i, _)| *i == id) => return Err(format!("relic {id:?} twice in the pack")),
            None => relics.push((id, spec)),
        }
    }
    // Potions: official powers, or pack powers loaded before or in this
    // pack (docs/specs/potions.md).
    let mut potions: Vec<(String, PotionSpec)> = Vec::new();
    // `ObtainRandomPotions` draws from this pack's potions.
    let pack_potions = crate::potions::PackPotions::set(v.get("potions").map(json::Value::items).unwrap_or(&[]));
    for p in v.get("potions").map(json::Value::items).unwrap_or(&[]) {
        let power = |name: &str| -> Option<u16> {
            t.powers.get(name).map(|(i, _)| *i).or_else(|| powers.iter().position(|(i, _)| i == name).map(|j| (t.powers.len() + j) as u16))
        };
        let (id, spec) = parse_potion(p, Some(&power))?;
        match t.potions.get(&id) {
            Some(s) if *s == spec => {}
            Some(_) => return Err(format!("pack potion {id:?} redefined")),
            None if potions.iter().any(|(i, _)| *i == id) => return Err(format!("potion {id:?} twice in the pack")),
            None => potions.push((id, spec)),
        }
    }
    drop(pack_potions);
    // A pool's cards: official, or pack entries loaded before or in this
    // pack, each with its type.
    let mut pool_cards: Vec<Vec<PoolCard>> = Vec::new();
    for (name, list) in &pools {
        let mut out = Vec::new();
        for c in list {
            let card = match CardId::from_name(c) {
                Some(id) => PoolCard { official: Some(id), pack: None, ty: id.def().ty },
                None => {
                    let spec = t.cards.get(c).or_else(|| cards.iter().find(|(i, _)| i == c).map(|(_, s)| s));
                    let spec = spec.ok_or_else(|| format!("pool {name:?}: {c:?} is not a loaded card"))?;
                    PoolCard { official: None, pack: Some(Box::leak(c.clone().into_boxed_str())), ty: spec.ty }
                }
            };
            out.push(card);
        }
        pool_cards.push(out);
    }
    // Nothing is committed until every check has passed.
    if t.powers.len() + powers.len() > CAPACITY {
        return Err("registry full".into());
    }
    for (id, kind, spec) in monsters {
        let def = def_of_spec(&spec, Box::leak(format!("gen:{id}").into_boxed_str()), no_setup);
        let _ = MONSTER_DEFS[kind.0 as usize - NUM_OFFICIAL_MONSTERS].set(Box::leak(Box::new(def)));
        t.monsters.insert(id, (kind, spec));
    }
    for (id, spec) in powers {
        let i = t.powers.len();
        if i >= CAPACITY {
            return Err("registry full".into());
        }
        let gp = GenPower {
            id: Box::leak(id.clone().into_boxed_str()),
            hooks: leak(spec.hooks.clone()),
            rules: spec.rules,
            statics: leak(spec.statics.clone()),
            replacements: leak(spec.replacements.clone()),
        };
        let _ = POWERS[i].set(gp);
        t.powers.insert(id, (i as u16, spec));
    }
    for (id, spec) in cards {
        if let Some(n) = &spec.successor {
            t.successor_of.insert(n.clone(), id.clone());
        }
        t.cards.insert(id, spec);
    }
    for (id, e, mut def) in encounters {
        def.name = Box::leak(format!("gen:{id}").into_boxed_str());
        let _ = ENCOUNTER_DEFS[e.0 as usize - NUM_OFFICIAL_ENCOUNTERS].set(Box::leak(Box::new(def.clone())));
        crate::monsters::mark_boss_kinds(&def);
        t.encounters.insert(id, (e, def));
    }
    for (id, spec) in relics {
        t.relics.insert(id, spec);
    }
    for (id, spec) in potions {
        t.potions.insert(id, spec);
    }
    for ((name, list), cards) in pools.into_iter().zip(pool_cards) {
        let i = t.pools.len();
        let _ = POOL_DEFS[i].set(PoolDef { name: Box::leak(name.clone().into_boxed_str()), cards: leak(cards) });
        t.pools.push((name, list));
    }
    Ok(fnv1a(text.as_bytes()))
}

fn fnv1a(b: &[u8]) -> u64 {
    b.iter().fold(0xcbf29ce484222325u64, |h, &x| (h ^ x as u64).wrapping_mul(0x100000001b3))
}

/// A pack card name (after `gen:`) as (the entry it is a level of, the
/// level): `X` is level 0, `X+` level 1 (of `X` when the pack has `X`; an
/// `X+` entry alone is its own card), `X+<n>` level n >= 2.
fn pack_level<'a>(t: &'a Table, name: &str) -> Option<(&'a str, u8)> {
    let key = |n: &str| t.cards.get_key_value(n).map(|(k, _)| k.as_str());
    // A successor's own id is its base at level 1 (one card, one id).
    if let Some(base) = t.successor_of.get(name).and_then(|b| key(b)) {
        return Some((base, 1));
    }
    if let Some(base) = name.strip_suffix('+').and_then(key) {
        return Some((base, 1));
    }
    if let Some(k) = key(name) {
        return Some((k, 0));
    }
    let (base, n) = name.rsplit_once('+')?;
    if !n.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let n: u8 = n.parse().ok().filter(|&n| n >= 2)?;
    Some((key(base)?, n))
}

/// The card definition index of pack card `id` (an entry, at its levels 0
/// and 1) with the generated powers it applies bound after those in `b`
/// (`n_powers` of them; more than `POWER_SLOTS` is an error). `at_level_0`:
/// the fight holds the card at level 0 (else its first id plays as level 1
/// too). Made on first use, then shared by key.
fn card_def_index(t: &mut Table, b: &mut Slots, n_powers: &mut usize, id: &str, at_level_0: bool) -> Result<u16, String> {
    let spec = t.cards[id].clone();
    let plus = plus_id(id, &spec, &|n| t.cards.contains_key(n));
    let (up_spec, max_level) = levels(id, &spec, plus.as_ref().and_then(|p| t.cards.get(p)))?;
    let mut slots = Vec::new();
    for g in spec.gens().chain(up_spec.gens()) {
        let pi = t.powers[g].0;
        let slot = match b.powers[..*n_powers].iter().position(|&x| x == pi) {
            Some(s) => s,
            None => {
                if *n_powers == POWER_SLOTS {
                    return Err(format!("deck has more than {POWER_SLOTS} generated powers"));
                }
                b.powers[*n_powers] = pi;
                *n_powers += 1;
                *n_powers - 1
            }
        };
        slots.push(slot as u16);
    }
    let n_powers = *n_powers;
    let has_plus = plus.is_some();
    let key = (id.to_string(), slots, has_plus, at_level_0);
    if let Some(&d) = t.defs.get(&key) {
        return Ok(d);
    }
    let d = t.n_defs;
    if d >= CAPACITY {
        return Err("registry full".into());
    }
    // A generated power's effect names its slot in this binding.
    let bound = |effects: &[Effect], gen: &[Option<String>]| -> Vec<Effect> {
        effects
            .iter()
            .zip(gen)
            .map(|(&e, g)| {
                let slot = |g: &String| {
                    let pi = t.powers[g].0;
                    Power::GEN[b.powers[..n_powers].iter().position(|&x| x == pi).unwrap()]
                };
                match (e, g) {
                    (Effect::Apply { amount, target, .. }, Some(g)) => Effect::Apply { power: slot(g), amount, target },
                    (Effect::RandomApply { amount, hits, .. }, Some(g)) => Effect::RandomApply { power: slot(g), amount, hits },
                    (e, _) => e,
                }
            })
            .collect()
    };
    let make = |spec: &CardSpec, name: String, level: u8, upgrade: &'static Upgrade| -> &'static CardDef {
        let (_, on_play, on_play_gen) = &spec.rows[0];
        let rows: Vec<Row> = spec.rows[1..]
            .iter()
            .map(|(condition, effects, gen)| Row { condition: *condition, effects: leak(bound(effects, gen)) })
            .collect();
        Box::leak(Box::new(CardDef {
            name: Box::leak(name.into_boxed_str()),
            class: CardClass::Colorless,
            cost_code: spec.cost,
            ty: spec.ty,
            exhaust: spec.exhaust,
            ethereal: spec.ethereal,
            playable_if: spec.playable_if,
            innate: spec.innate,
            tags: spec.tags,
            retain: spec.retain,
            cost_less_per_hp_loss: spec.cost_less_per_hp_loss,
            effects: leak(bound(on_play, on_play_gen)),
            rows: leak(rows),
            turn_end: leak(spec.turn_end.clone()),
            exhausted: leak(spec.exhausted.clone()),
            other_played: leak(spec.other_played.clone()),
            plays_per_turn: spec.plays_per_turn,
            level,
            max_level,
            upgrade,
        }))
    };
    let upgrade: &'static Upgrade = Box::leak(Box::new(spec.upgrade.clone().unwrap_or_default()));
    let def = make(&spec, format!("gen:{id}"), 0, upgrade);
    let up = if max_level == 0 { def } else { make(&up_spec, format!("gen:{id}+"), 1, upgrade) };
    let def = if at_level_0 { def } else { up };
    let _ = CARD_DEFS[d].set(BoundCard { def, up, id: Box::leak(id.to_string().into_boxed_str()), at_level_0 });
    t.n_defs += 1;
    t.defs.insert(key, d as u16);
    Ok(d as u16)
}

/// Card names (official, or `gen:<id>`) to card ids, with generated cards
/// and the generated powers they apply bound to reserved slots in order of
/// first appearance. More than `MAX_CARD_SLOTS` cards or `POWER_SLOTS` powers is an error,
/// as is a deck one pile can't hold (`state::deck_fits`).
pub fn bind(names: &[&str]) -> Result<(Vec<CardId>, Binding), String> {
    deck_fits(names)?;
    let mut t = table().lock().unwrap();
    let mut b = EMPTY_SLOTS;
    let (mut n_powers, mut n_cards) = (0usize, 0usize);
    let mut card_slot: HashMap<String, usize> = HashMap::new();
    let mut ids = Vec::with_capacity(names.len());
    // (index in `ids`, level) of the names at level 2 and up (variants).
    let mut wanted: Vec<(usize, u8)> = Vec::new();
    // Pack cards the deck holds at level 0: a slot of a card held only
    // upgraded never holds its level 0 (upgrades only go up), so its first
    // id plays as level 1 too (the HP-loss counter's cap reads both).
    let at_level_0: std::collections::HashSet<String> =
        names.iter().filter_map(|n| pack_level(&t, n.strip_prefix("gen:")?)).filter(|&(_, l)| l == 0).map(|(id, _)| id.to_string()).collect();
    for &name in names {
        let Some(gen_name) = name.strip_prefix("gen:") else {
            ids.push(CardId::from_name(name).ok_or_else(|| format!("unknown card {name:?}"))?);
            continue;
        };
        let (id, level) = pack_level(&t, gen_name).ok_or_else(|| format!("unknown generated card {name:?}"))?;
        let id = id.to_string();
        let id = id.as_str();
        let at = |slot: usize| CardId(slot_card(slot).0 + level.min(1) as u16);
        let spec = t.cards[id].clone();
        let plus = plus_id(id, &spec, &|n| t.cards.contains_key(n));
        let (_, max_level) = levels(id, &spec, plus.as_ref().and_then(|p| t.cards.get(p)))?;
        if level > max_level {
            return Err(format!("generated card {name:?}: {id:?} upgrades to level {max_level} at most"));
        }
        if level >= 2 {
            wanted.push((ids.len(), level));
        }
        if let Some(&slot) = card_slot.get(id) {
            ids.push(at(slot));
            continue;
        }
        if n_cards == MAX_CARD_SLOTS {
            return Err(format!("deck has more than {MAX_CARD_SLOTS} generated cards (MAX_CARD_SLOTS)"));
        }
        let di = card_def_index(&mut t, &mut b, &mut n_powers, id, at_level_0.contains(id))?;
        b.cards.push(di);
        card_slot.insert(id.to_string(), n_cards);
        ids.push(at(n_cards));
        n_cards += 1;
    }
    // The pool cards the deck's `Discover`s can offer, after the deck's
    // (docs/specs/discovery.md).
    let mut by_slot: Vec<(&String, &usize)> = card_slot.iter().collect();
    by_slot.sort_by_key(|&(_, &k)| k);
    let deck_effects: Vec<Effect> = by_slot.into_iter().flat_map(|(id, _)| t.cards[id].effects()).collect();
    add_discovered(&mut t, &mut b, deck_effects)?;
    // Pack powers the deck's powers apply from their hooks, after the deck's.
    let n_powers = b.powers.iter().take_while(|&&x| x != FREE).count();
    for i in 0..n_powers {
        let pi = b.powers[i];
        add_applied(&mut b, pi)?;
    }
    // The pool cards those powers' hooks can make (docs/specs/blocked-relics.md
    // step 5), and the powers those cards bring.
    let n_powers = b.powers.iter().take_while(|&&x| x != FREE).count();
    let made = power_pool_effects(&b.powers[..n_powers]);
    if add_discovered(&mut t, &mut b, made)? {
        let n = b.powers.iter().take_while(|&&x| x != FREE).count();
        for i in n_powers..n {
            let pi = b.powers[i];
            add_applied(&mut b, pi)?;
        }
    }
    drop(t);
    let binding = Binding::of(&b)?;
    // Levels 2 and up: changed copies of the slot's level-1 id.
    for &(j, level) in &wanted {
        let base = ids[j];
        ids[j] = changed_copy(base, binding.def(base), Overrides { damage: None, level, cost: None })?;
    }
    Ok((ids, binding))
}

/// Binds every pack card the `Discover` effects in `effects` can offer
/// (their pools, filtered by type) at level 0, after the cards in `s`,
/// with the generated powers they apply; and so on for the `Discover`s of
/// the cards bound (docs/specs/discovery.md). A card already bound at level
/// 0 keeps its slot; one bound only at level 1 keeps it with its level 0
/// added. More than `MAX_CARD_SLOTS` cards is an error. Returns whether `s`
/// changed.
fn add_discovered(t: &mut Table, s: &mut Slots, effects: Vec<Effect>) -> Result<bool, String> {
    let mut todo: Vec<&'static str> = Vec::new();
    let mut queue = effects;
    let mut changed = false;
    // In order: the deck's cards, then each pool's, as they come.
    while !queue.is_empty() {
        let e = queue.remove(0);
        let (Effect::Discover { pool, ty, .. } | Effect::MakeRandom { pool, ty, .. }) = e else { continue };
        let p = pool_def(pool).expect("a loaded pool");
        todo.extend(p.cards.iter().filter(|c| ty.is_none_or(|ty| c.ty == ty)).filter_map(|c| c.pack));
        while !todo.is_empty() {
            let id = todo.remove(0);
            let n_cards = s.cards.len();
            let mut n_powers = s.powers.iter().take_while(|&&x| x != FREE).count();
            let at = (0..n_cards).find(|&k| CARD_DEFS[s.cards[k] as usize].get().is_some_and(|c| c.id == id));
            match at {
                Some(k) if CARD_DEFS[s.cards[k] as usize].get().is_some_and(|c| c.at_level_0) => continue,
                Some(k) => s.cards[k] = card_def_index(t, s, &mut n_powers, id, true)?,
                None => {
                    if n_cards == MAX_CARD_SLOTS {
                        return Err(format!("the fight would bind more than {MAX_CARD_SLOTS} generated cards, pool cards included (MAX_CARD_SLOTS)"));
                    }
                    let di = card_def_index(t, s, &mut n_powers, id, true)?;
                    s.cards.push(di);
                }
            }
            changed = true;
            queue.extend(t.cards[id].effects());
        }
    }
    Ok(changed)
}

/// The `MakeRandom`s in the hooks of pack powers `powers` (their pools'
/// cards are bound with the fight).
fn power_pool_effects(powers: &[u16]) -> Vec<Effect> {
    powers
        .iter()
        .filter_map(|&pi| POWERS[pi as usize].get())
        .flat_map(|g| g.hooks.iter().flat_map(|h| h.effects))
        .filter(|e| matches!(e, Effect::MakeRandom { .. }))
        .copied()
        .collect()
}

/// `b` with the pool cards the `Discover`s and `MakeRandom`s in `effects`
/// can offer or make bound (`add_discovered`) and the pack powers those
/// apply: for the potions and relics a fight is given.
/// Then, until nothing more is bound, the pool cards every bound pack
/// power's hooks can make (a power a relic's or potion's hook applies,
/// or one a made card brings: docs/specs/blocked-relics.md step 5).
fn bind_discovered(b: &Binding, effects: Vec<Effect>) -> Result<Binding, String> {
    let mut t = table().lock().unwrap();
    let mut s = b.slot_set().clone();
    let bound = |s: &Slots| s.powers.iter().take_while(|&&x| x != FREE).count();
    let mut queue = effects;
    queue.extend(power_pool_effects(&s.powers[..bound(&s)]));
    loop {
        let before = s.clone();
        add_discovered(&mut t, &mut s, queue)?;
        let mut i = 0;
        while i < bound(&s) {
            let pi = s.powers[i];
            add_applied(&mut s, pi)?;
            i += 1;
        }
        if s == before {
            break;
        }
        queue = power_pool_effects(&s.powers[..bound(&s)]);
    }
    drop(t);
    if s == *b.slot_set() {
        return Ok(*b);
    }
    Ok(Binding::of(&s)?)
}

/// The cards pool `pool` offers in a fight bound by `b`, only those of type
/// `ty` when given, sorted by card id: an official card as it is, a pack
/// entry at its slot's level-0 id (bound with what discovers:
/// `add_discovered`). Cached per (slot set, pool, type).
pub fn pool_cards(b: &Binding, pool: u8, ty: Option<CardType>) -> std::rc::Rc<[CardId]> {
    thread_local! {
        static CACHE: RefCell<HashMap<(u32, u8, Option<CardType>), std::rc::Rc<[CardId]>>> = RefCell::new(HashMap::new());
    }
    let key = (b.slots, pool, ty);
    if let Some(v) = CACHE.with(|c| c.borrow().get(&key).cloned()) {
        return v;
    }
    let s = b.slot_set();
    let p = pool_def(pool).expect("a loaded pool");
    let mut v: Vec<CardId> = p
        .cards
        .iter()
        .filter(|c| ty.is_none_or(|ty| c.ty == ty))
        .map(|c| match (c.official, c.pack) {
            (Some(id), _) => id,
            (None, Some(id)) => {
                let k = (0..s.cards.len())
                    .find(|&k| CARD_DEFS[s.cards[k] as usize].get().is_some_and(|d| d.id == id && d.at_level_0))
                    .unwrap_or_else(|| panic!("pool {:?}: card {id:?} isn't bound at level 0 in this fight", p.name));
                slot_card(k)
            }
            (None, None) => unreachable!("a pool card is official or a pack entry"),
        })
        .collect();
    v.sort();
    let v: std::rc::Rc<[CardId]> = v.into();
    CACHE.with(|c| c.borrow_mut().insert(key, v.clone()));
    v
}

/// Whether a card can take a general upgrade (the rest site, Armaments):
/// below its max level and not a status or a curse.
pub fn general_upgrade(d: &CardDef) -> bool {
    !d.is_status_or_curse() && d.level < d.max_level
}

/// What one general upgrade makes of card `c` in a combat bound by `b`:
/// a level-0 copy becomes its pair's level-1 id; a copy at level 1 or a
/// changed copy becomes a changed copy one level up (a grown damage number
/// kept). `None` if it can't be upgraded.
pub fn upgraded(b: &Binding, c: CardId) -> Option<CardId> {
    let d = b.def(c);
    if !general_upgrade(d) {
        return None;
    }
    match copy_of(c) {
        Some((base, o)) => {
            // Level 0 grows to the pair's level-1 id; past it, the same base.
            let (to, mut up) = if o.level == 0 { (CardId(base.0 + 1), Overrides { level: 1, ..o }) } else { (base, Overrides { level: o.level + 1, ..o }) };
            // An upgrade that changes the card's cost resets a cost for the
            // combat to the new one (the game's `upgradeBaseCost`,
            // cards/AbstractCard.java 710-720 in aeubanks/sts); otherwise it
            // stays.
            // A card that costs less per HP loss moves its combat cost by the
            // upgrade's change instead, floored at 0 (BloodForBlood.upgrade:
            // a cost below 4 becomes cost - 1), so it keeps its drops.
            if let Some(v) = o.cost {
                let own = |c: CardId, level: u8| changed_copy(c, b.def(c), Overrides { level, ..Overrides::default() }).ok().map(|x| b.def(x).cost());
                let (was, now) = (own(base, o.level)?, own(to, up.level)?);
                if d.cost_less_per_hp_loss {
                    up.cost = Some((v + now - was).max(0));
                } else if was != now {
                    up.cost = None;
                }
            }
            changed_copy(to, b.def(to), up).ok()
        }
        None if c.0 & 1 == 0 => Some(CardId(c.0 + 1)),
        None => changed_copy(c, d, Overrides { damage: None, level: d.level + 1, cost: None }).ok(),
    }
}

/// A card name with its level marks off: `Bash+` and `gen:Searing Blow+12`
/// are `Bash` and `gen:Searing Blow`.
pub fn base_name(name: &str) -> &str {
    if let Some(b) = name.strip_suffix('+') {
        return b;
    }
    match name.rsplit_once('+') {
        Some((b, n)) if !n.is_empty() && n.bytes().all(|x| x.is_ascii_digit()) => b,
        _ => name,
    }
}

/// The name one general upgrade makes of the card `name` (official or
/// `gen:`), or `None` if it can't be upgraded.
pub fn upgrade_name(name: &str) -> Result<Option<String>, String> {
    let (ids, b) = bind(&[name])?;
    let d = b.def(ids[0]);
    if !general_upgrade(d) {
        return Ok(None);
    }
    let base = base_name(name);
    Ok(Some(match d.level {
        0 if ids[0].is_official() => CardId(ids[0].0 + 1).name().to_string(),
        0 => format!("{base}+"),
        l => format!("{base}+{}", l + 1),
    }))
}

/// Monster names (an official monster's game name, e.g. `Jaw Worm`, or
/// `gen:<id>` for a loaded pack monster) to kinds, for
/// `CombatState::new_vs`: 1 to `MAX_MONSTERS` of them, their slots
/// (splits included) at most `MAX_MONSTERS`.
pub fn monster_kinds(names: &[&str]) -> Result<Vec<MonsterKind>, String> {
    if names.is_empty() || names.len() > MAX_MONSTERS {
        return Err(format!("a combat takes 1 to {MAX_MONSTERS} monsters, got {}", names.len()));
    }
    let t = table().lock().unwrap();
    let kinds = names.iter().map(|&n| monster_kind(&t, n).ok_or_else(|| format!("unknown monster {n:?}"))).collect::<Result<Vec<_>, _>>()?;
    let n: usize = kinds.iter().map(|&k| slots_needed(k)).sum();
    if n > MAX_MONSTERS {
        return Err(format!("these monsters need {n} slots with their splits, more than {MAX_MONSTERS}"));
    }
    Ok(kinds)
}

/// Binds registry power `pi` after those in `b`: one already bound keeps its
/// slot, a new one takes the next free slot; more than `POWER_SLOTS` is an error.
fn add_power(b: &mut Slots, pi: u16) -> Result<(), String> {
    let n = b.powers.iter().take_while(|&&x| x != FREE).count();
    if b.powers[..n].contains(&pi) {
        return Ok(());
    }
    if n == POWER_SLOTS {
        return Err(format!("the deck and monsters have more than {POWER_SLOTS} generated powers"));
    }
    b.powers[n] = pi;
    add_applied(b, pi)
}

/// Binds the pack powers that registry power `pi`'s hooks apply, and theirs.
fn add_applied(b: &mut Slots, pi: u16) -> Result<(), String> {
    let Some(g) = POWERS[pi as usize].get() else { return Ok(()) };
    for e in g.hooks.iter().flat_map(|h| h.effects) {
        if let Effect::ApplyPack { power, .. } = *e {
            add_power(b, power)?;
        }
    }
    Ok(())
}

/// `b` with loaded pack power `id` bound (as `bind_monsters` binds a pack
/// monster's start power), and the slot power holding it: for a pack power
/// given to a monster of a live combat (the generated enemies bench).
pub fn bind_power(b: &Binding, id: &str) -> Result<(Binding, Power), String> {
    let pi = table().lock().unwrap().powers.get(id).map(|(i, _)| *i).ok_or_else(|| format!("unknown power {id:?}"))?;
    let mut s = b.slot_set().clone();
    add_power(&mut s, pi)?;
    let nb = if s == *b.slot_set() { *b } else { Binding::of(&s)? };
    Ok((nb, nb.slot_of(pi)))
}

/// `deck` with the pack start powers of these monsters, and of their split
/// children, bound after the deck's: a power the deck already binds keeps
/// its slot, a new one takes the next free slot (deck slots never move).
/// More than `POWER_SLOTS` pack powers in all is an error.
pub fn bind_monsters(deck: &Binding, kinds: &[MonsterKind]) -> Result<Binding, String> {
    fn add(b: &mut Slots, k: MonsterKind) -> Result<(), String> {
        if k == MonsterKind::None {
            return Ok(());
        }
        let d = k.def();
        // Every level's, so a fight's binding doesn't depend on its level.
        for l in std::iter::once(d).chain(d.levels.iter().map(|(_, l)| *l)) {
            for &(pi, _) in l.gen_powers {
                add_power(b, pi)?;
            }
            for e in l.moves.iter().flat_map(|m| m.effects) {
                if let Effect::ApplyPack { power: pi, .. } = *e {
                    add_power(b, pi)?;
                }
            }
        }
        if d.split_move != NO_MOVE {
            for c in d.split_into {
                add(b, c)?;
            }
        }
        Ok(())
    }
    let mut b = deck.slot_set().clone();
    for &k in kinds {
        add(&mut b, k)?;
    }
    if b == *deck.slot_set() {
        return Ok(*deck);
    }
    // The pool cards the monsters' pack powers' hooks can make.
    bind_discovered(&Binding::of(&b)?, Vec::new())
}

impl Binding {
    /// The slot power holding registry power `pi` (a pack monster's start
    /// power); panics when it isn't bound (`bind_monsters` was skipped).
    pub fn slot_of(&self, pi: u16) -> Power {
        let i = self.slot_set().powers[..self.n_powers as usize].iter().position(|&x| x == pi);
        Power::GEN[i.expect("a pack monster's power is not bound in this combat (call registry::bind_monsters)")]
    }
}

fn official_monster(name: &str) -> Option<MonsterKind> {
    (1..NUM_OFFICIAL_MONSTERS).map(|i| MonsterKind(i as u8)).find(|k| k.def().name == name)
}

fn monster_kind(t: &Table, name: &str) -> Option<MonsterKind> {
    match name.strip_prefix("gen:") {
        Some(id) => t.monsters.get(id).map(|(k, _)| *k),
        None => official_monster(name),
    }
}

// ---- pack parsing ----

/// A monster move's effect: a card effect that runs outside a card, or
/// `Split` / `Escape`; no generated power, no power-only, player-only
/// (`Draw`, `GainEnergy`) or code-rolled one.
fn monster_effect(v: &json::Value, power: &dyn Fn(&str) -> Option<u16>) -> Result<Effect, String> {
    match v.str() {
        Some("Split") => return Ok(Effect::Split),
        Some("Escape") => return Ok(Effect::Escape),
        _ => {}
    }
    if let Ok(("BlockAlly", f)) = variant(v) {
        let n = int(f, "BlockAlly")?;
        if !(0..=999).contains(&n) {
            return Err(format!("BlockAlly {n} out of range"));
        }
        return Ok(Effect::BlockAlly(n as i16));
    }
    let (e, g) = parse_effect(v)?;
    if matches!(e, Effect::RandomizeCost(_)) {
        return Err("RandomizeCost is the player's (a card, potion or hook), not a monster move's".into());
    }
    if let Some(g) = g {
        let (Effect::Apply { amount, target, .. }, Some(pi)) = (e, power(&g)) else {
            return Err(format!("a monster move uses generated power {g:?} other than in an Apply of a loaded pack power"));
        };
        return Ok(Effect::ApplyPack { power: pi, amount, target });
    }
    if !runs_outside_a_card(&e) || matches!(
        e,
        Effect::GrowDamage(_) | Effect::ReplayCard | Effect::RemoveSelf | Effect::ReduceSelf(_) | Effect::Draw(_) | Effect::GainEnergy(_)
            | Effect::SetCounter(_) | Effect::AddCounter(_)
    ) {
        return Err(format!("{e:?} can't be a monster move's effect"));
    }
    Ok(e)
}

fn move_ref(v: Option<&json::Value>, n: usize, what: &str) -> Result<MoveId, String> {
    let i = int(v, what)?;
    if i < 0 || i as usize >= n {
        return Err(format!("{what}: move {i} out of range (0..{n})"));
    }
    Ok(i as MoveId)
}

fn pattern_condition(c: &json::Value, n: usize) -> Result<PatCond, String> {
    let (name, f) = variant(c)?;
    Ok(match name {
        "FirstTurn" => PatCond::FirstTurn,
        "Allies" if f.is_none() => PatCond::Allies,
        "Allies" => return Err("Allies takes no value".into()),
        "LastMove" => PatCond::LastMove(move_ref(f, n, "LastMove")?),
        "LastTwo" => PatCond::LastTwo(move_ref(f, n, "LastTwo")?),
        "Window" => {
            let [a, b] = f.map(json::Value::items).unwrap_or(&[]) else { return Err("Window must be [last, before]".into()) };
            let opt = |x: &json::Value| if *x == json::Value::Null { Ok(NO_MOVE) } else { move_ref(Some(x), n, "Window") };
            PatCond::Window(opt(a)?, opt(b)?)
        }
        "Slot" => {
            let k = int(f, "Slot")?;
            if !(0..MAX_MONSTERS as i64).contains(&k) {
                return Err(format!("Slot {k} out of range"));
            }
            PatCond::Slot(k as u8)
        }
        "RollBelow" => {
            let k = int(f, "RollBelow")?;
            if !(0..=100).contains(&k) {
                return Err(format!("RollBelow {k} out of range"));
            }
            PatCond::RollBelow(k as u8)
        }
        x => return Err(format!("pattern condition {x:?} not supported")),
    })
}

fn pattern_pick(v: &json::Value, n: usize) -> Result<PatPick, String> {
    let (name, f) = variant(v)?;
    let field = |k: &str| f.and_then(|f| f.get(k));
    Ok(match name {
        "Move" => PatPick::Move(move_ref(f, n, "Move")?),
        "Chance" => {
            let p = match field("p") {
                Some(json::Value::Num(p)) if *p > 0.0 && *p < 1.0 => *p,
                x => return Err(format!("Chance p must be in (0, 1), got {x:?}")),
            };
            PatPick::Chance { p, yes: move_ref(field("yes"), n, "Chance yes")?, no: move_ref(field("no"), n, "Chance no")? }
        }
        x => return Err(format!("pattern pick {x:?} not supported")),
    })
}

fn parse_monster(
    v: &json::Value,
    resolve: &dyn Fn(&str) -> Option<MonsterKind>,
    power: &dyn Fn(&str) -> Option<u16>,
) -> Result<MonsterSpec, String> {
    parse_monster_as(v, resolve, power, false)
}

/// The top-level monster fields an `ascension` row may change.
const ASCENSION_FIELDS: [&str; 7] = ["hp", "start_block", "start_powers", "rolled_attack", "rolled_powers", "moves", "pattern"];

/// Applies an `ascension` row's change `p` to `t`: an object changes an
/// object field by field (a one-key object naming another variant replaces
/// it) and a list item by item, keyed by index; anything else replaces.
fn patch(t: &mut json::Value, p: &json::Value) -> Result<(), String> {
    use json::Value::{Arr, Obj};
    match (t, p) {
        (Obj(tv), Obj(pv)) if !(tv.len() == 1 && pv.len() == 1 && tv[0].0 != pv[0].0) => {
            for (k, x) in pv {
                match tv.iter_mut().find(|(key, _)| key == k) {
                    Some((_, y)) => patch(y, x)?,
                    None => tv.push((k.clone(), x.clone())),
                }
            }
        }
        (Arr(tv), Obj(pv)) => {
            for (k, x) in pv {
                let i: usize = k.parse().map_err(|_| format!("a list changes by item index, got {k:?}"))?;
                let n = tv.len();
                patch(tv.get_mut(i).ok_or_else(|| format!("item {i} of a list of {n}"))?, x)?;
            }
        }
        (t, p) => *t = p.clone(),
    }
    Ok(())
}

/// A `[min, max]` range of `what`, `0 <= min <= max`.
fn range(v: &json::Value, what: &str) -> Result<(i16, i16), String> {
    let [lo, hi] = v.items() else { return Err(format!("{what} must be [min, max]")) };
    let r = (int(Some(lo), what)?, int(Some(hi), what)?);
    if r.0 < 0 || r.0 > r.1 || r.1 > i16::MAX as i64 {
        return Err(format!("bad {what} range {r:?}"));
    }
    Ok((r.0 as i16, r.1 as i16))
}

/// `official`: an entry of `content/monsters.json`: it may carry `code`,
/// and its split children resolve only through `resolve` (earlier entries
/// of the file). `power` finds a pack start power's registry index (none
/// for official content). Its `ascension` rows each give the monster from
/// a level up (docs/specs/ascension.md), parsed as the entry with every
/// row up to it applied.
fn parse_monster_as(
    v: &json::Value,
    resolve: &dyn Fn(&str) -> Option<MonsterKind>,
    power: &dyn Fn(&str) -> Option<u16>,
    official: bool,
) -> Result<MonsterSpec, String> {
    let mut spec = parse_monster_level(v, resolve, power, official)?;
    let Some(rows) = v.get("ascension") else { return Ok(spec) };
    let json::Value::Arr(items) = rows else { return Err("ascension must be a list of rows".into()) };
    let mut at = v.clone();
    if let json::Value::Obj(kv) = &mut at {
        kv.retain(|(k, _)| k != "ascension");
    }
    let mut last = 0;
    for r in items {
        let json::Value::Obj(kv) = r else { return Err("an ascension row must be an object".into()) };
        let from = int(r.get("from"), "ascension row from")?;
        if from <= last || from > MAX_ASCENSION as i64 {
            return Err(format!("ascension row from {from}: levels rise from 1 to {MAX_ASCENSION}"));
        }
        last = from;
        let err = |e: String| format!("ascension from {from}: {e}");
        for (k, x) in kv.iter().filter(|(k, _)| k != "from") {
            if !ASCENSION_FIELDS.contains(&k.as_str()) {
                return Err(err(format!("field {k:?} doesn't change by level (one of {ASCENSION_FIELDS:?})")));
            }
            match at.get(k).is_some() {
                true => {
                    let json::Value::Obj(kv) = &mut at else { unreachable!() };
                    patch(&mut kv.iter_mut().find(|(key, _)| key == k).unwrap().1, x).map_err(err)?;
                }
                false => {
                    let json::Value::Obj(kv) = &mut at else { unreachable!() };
                    kv.push((k.clone(), x.clone()));
                }
            }
        }
        let l = parse_monster_level(&at, resolve, power, official).map_err(err)?;
        // A state's move ids and split slots hold at every level.
        if l.moves.len() != spec.moves.len() || l.split != spec.split {
            return Err(err("a level keeps the monster's moves count and split".into()));
        }
        spec.levels.push((from as u8, l));
    }
    spec.rows = RowsText(json::write(rows));
    Ok(spec)
}

/// One level's monster (`parse_monster_as` without the `ascension` rows).
fn parse_monster_level(
    v: &json::Value,
    resolve: &dyn Fn(&str) -> Option<MonsterKind>,
    power: &dyn Fn(&str) -> Option<u16>,
    official: bool,
) -> Result<MonsterSpec, String> {
    let code = official && v.get("code").is_some();
    if !official && v.get("code").is_some() {
        return Err("field \"code\" is for official content only".into());
    }
    let rolled_attack = v.get("rolled_attack").map(|r| range(r, "rolled_attack")).transpose()?;
    let mut rolled_powers = Vec::new();
    for p in v.get("rolled_powers").map(json::Value::items).unwrap_or(&[]) {
        let name = p.get("power").and_then(json::Value::str).ok_or("rolled power without a power")?;
        let pw = official_power(name).ok_or_else(|| format!("rolled power {name:?}: an official power"))?;
        let (lo, hi) = range(p.get("amount").unwrap_or(&json::Value::Null), "rolled power amount")?;
        rolled_powers.push((pw, lo, hi));
    }
    let [lo, hi] = v.get("hp").map(json::Value::items).unwrap_or(&[]) else { return Err("hp must be [min, max]".into()) };
    let hp = (int(Some(lo), "hp min")? as i16, int(Some(hi), "hp max")? as i16);
    if hp.0 < 1 || hp.0 > hp.1 {
        return Err(format!("bad hp range {hp:?}"));
    }
    let (mut start_powers, mut gen_powers) = (Vec::new(), Vec::new());
    for p in v.get("start_powers").map(json::Value::items).unwrap_or(&[]) {
        let name = p.get("power").and_then(json::Value::str).ok_or("start power without a power")?;
        let amount = int(p.get("amount"), "start power amount")? as i16;
        match (official_power(name), power(name)) {
            (Some(o), _) => start_powers.push((o, amount)),
            (None, Some(i)) => gen_powers.push((i, amount)),
            (None, None) => return Err(format!("start power {name:?} is not official nor a loaded pack power")),
        }
    }
    let mut moves = Vec::new();
    for m in v.get("moves").map(json::Value::items).unwrap_or(&[]) {
        let name = m.get("name").and_then(json::Value::str).ok_or("move without a name")?.to_string();
        let effect = |e: &json::Value| match e.str() {
            // Rolled at the start (`rolled_attack`), or set by code (Hexaghost's Divider).
            Some("RolledAttack") if rolled_attack.is_some() || code => Ok(Effect::RolledAttack),
            Some("RolledAttack") => Err("RolledAttack needs the monster's rolled_attack range".to_string()),
            _ => monster_effect(e, power),
        };
        let effects = m.get("effects").map(json::Value::items).unwrap_or(&[]).iter().map(effect).collect::<Result<Vec<_>, _>>()?;
        moves.push((name, effects));
    }
    let n = moves.len();
    if n == 0 || n >= NO_MOVE as usize {
        return Err(format!("{n} moves (1 to {} allowed)", NO_MOVE - 1));
    }
    let mut pattern = Vec::new();
    for r in v.get("pattern").map(json::Value::items).unwrap_or(&[]) {
        let when = r.get("when").map(json::Value::items).unwrap_or(&[]).iter().map(|c| pattern_condition(c, n)).collect::<Result<Vec<_>, _>>()?;
        pattern.push((when, pattern_pick(r.get("then").ok_or("pattern row without a then")?, n)?));
    }
    // A code-backed official monster may end on a condition (Hexaghost's
    // cycle always matches one row).
    if !code && !pattern.last().is_some_and(|(when, _)| when.is_empty()) {
        return Err("the pattern's last row must have no conditions (a monster always picks a move)".into());
    }
    let split = match v.get("split") {
        None => None,
        Some(sp) => {
            let mv = move_ref(sp.get("move"), n, "split move")?;
            let [a, b] = sp.get("into").map(json::Value::items).unwrap_or(&[]) else {
                return Err("split into must name two monsters".into());
            };
            let kind = |x: &json::Value| -> Result<MonsterKind, String> {
                let name = x.str().ok_or("a split child must be a name")?;
                if official { resolve(name) } else { official_monster(name).or_else(|| resolve(name)) }.ok_or_else(|| format!("split child {name:?} is neither official nor loaded before it"))
            };
            Some((mv, [kind(a)?, kind(b)?]))
        }
    };
    if split.is_none() && moves.iter().any(|(_, es)| es.contains(&Effect::Split)) {
        return Err("a move splits but the monster has no split".into());
    }
    let start_block = match v.get("start_block") {
        None => 0,
        b => int(b, "start_block")? as i16,
    };
    Ok(MonsterSpec { hp, start_block, start_powers, gen_powers, moves, pattern, split, rolled_attack, rolled_powers, levels: Vec::new(), rows: RowsText::default() })
}

fn official_power(name: &str) -> Option<Power> {
    Power::ALL.into_iter().find(|p| format!("{p:?}") == name)
}

fn target(v: Option<&json::Value>) -> Result<Target, String> {
    match v.and_then(json::Value::str) {
        Some("Me") => Ok(Target::Me),
        Some("Opponent") => Ok(Target::Opponent),
        Some("AllOpponents") => Ok(Target::AllOpponents),
        Some("Attacker") => Ok(Target::Attacker),
        Some("RandomOpponent") => Ok(Target::RandomOpponent),
        x => Err(format!("bad target {x:?}")),
    }
}

fn card_type(s: Option<&str>) -> Result<CardType, String> {
    match s {
        Some("Attack") => Ok(CardType::Attack),
        Some("Skill") => Ok(CardType::Skill),
        Some("Power") => Ok(CardType::Power),
        Some("Status") => Ok(CardType::Status),
        Some("Curse") => Ok(CardType::Curse),
        x => Err(format!("bad card type {x:?}")),
    }
}

fn tag(s: &str) -> Result<Tag, String> {
    Tag::ALL.into_iter().find(|t| format!("{t:?}") == s).ok_or_else(|| format!("bad tag {s:?}"))
}

fn amount(v: Option<&json::Value>, what: &str) -> Result<Amount, String> {
    let v = v.ok_or_else(|| format!("{what}: missing"))?;
    if let Some(n) = v.int() {
        return Ok(Amount::constant(n as i16));
    }
    let of = match v.get("of").map(variant).transpose()? {
        None => None,
        Some(("OwnBlock", _)) => Some(Quantity::OwnBlock),
        Some(("OwnStrength", _)) => Some(Quantity::OwnStrength),
        Some(("OwnMaxHp", _)) => Some(Quantity::OwnMaxHp),
        Some(("DrawPileSize", _)) => Some(Quantity::DrawPileSize),
        Some(("HpDealt", _)) => Some(Quantity::HpDealt),
        Some(("EnergySpent", _)) => Some(Quantity::EnergySpent),
        Some(("CardsTagged", f)) => Some(Quantity::CardsTagged(tag(f.and_then(json::Value::str).ok_or("CardsTagged without a tag")?)?)),
        Some(("HandCards", f)) => Some(Quantity::HandCards { except: except(f)? }),
        Some(("CardsOfType", f)) => Some(Quantity::CardsOfType(card_type(f.and_then(json::Value::str))?)),
        Some((x, _)) => return Err(format!("bad quantity {x:?}")),
    };
    let base = int(v.get("base"), "amount base")? as i16;
    // `k`: a whole number, or a fraction written "a/b" (kept in lowest terms).
    let (k, per) = match v.get("k") {
        None => (0, 1),
        Some(x) => match (x.int(), x.str()) {
            (Some(n), _) => (n as i16, 1),
            (None, Some(f)) => fraction(f).ok_or_else(|| format!("{what}: k {f:?} is not a whole number or a fraction a/b"))?,
            _ => return Err(format!("{what}: k {x:?} is not a whole number or a fraction \"a/b\"")),
        },
    };
    Ok(Amount { base, k, per, of })
}

/// `"a/b"` as `(a, b)` in lowest terms, sign on top; `None` if it isn't two
/// integers or `b` is 0.
fn fraction(f: &str) -> Option<(i16, i16)> {
    let (a, b) = f.split_once('/')?;
    let (a, b) = (a.trim().parse::<i16>().ok()?, b.trim().parse::<i16>().ok()?);
    let (a, b) = crate::effects::lowest(a as i32, b as i32)?;
    Some((i16::try_from(a).ok()?, i16::try_from(b).ok()?))
}

/// The optional `except` card type of `HandCards` and `ExhaustHand`.
fn except(f: Option<&json::Value>) -> Result<Option<CardType>, String> {
    f.and_then(|f| f.get("except")).map(|t| card_type(t.str())).transpose()
}

fn official_card(v: Option<&json::Value>) -> Result<CardId, String> {
    let name = v.and_then(json::Value::str).ok_or("expected a card name")?;
    CardId::from_name(name).ok_or_else(|| format!("unknown card {name:?}"))
}

pub(crate) fn condition(v: Option<&json::Value>) -> Result<Condition, String> {
    condition_of(v, false)
}

/// A condition; `Applying` only with `applying` (an `OwnerApplied` hook's:
/// docs/specs/act1-singles.md).
fn condition_of(v: Option<&json::Value>, applying: bool) -> Result<Condition, String> {
    Ok(match v.map(variant).transpose()? {
        None | Some(("Always", _)) => Condition::Always,
        Some(("CardType", f)) => Condition::CardType(card_type(f.and_then(json::Value::str))?),
        Some(("TargetIntendsAttack", _)) => Condition::TargetIntendsAttack,
        Some(("TargetHas", f)) => {
            let p = f.and_then(json::Value::str).ok_or("TargetHas without a power")?;
            Condition::TargetHas(official_power(p).ok_or_else(|| format!("TargetHas: {p:?} is not an official power"))?)
        }
        Some(("CardsPlayedThisTurnBelow", f)) => Condition::CardsPlayedThisTurnBelow(int(f, "CardsPlayedThisTurnBelow")? as u8),
        Some(("HandAll", f)) => Condition::HandAll(card_type(f.and_then(json::Value::str))?),
        Some(("OwnerHpAtMostHalf", _)) => Condition::OwnerHpAtMostHalf,
        Some(("CounterIs", f)) => Condition::CounterIs(int(f, "CounterIs")? as i16),
        Some(("OwnerBlockIs", f)) => Condition::OwnerBlockIs(int(f, "OwnerBlockIs")? as i16),
        Some(("Applying", _)) if !applying => return Err("condition Applying is an OwnerApplied hook's only".into()),
        Some(("Applying", f)) => {
            let p = f.and_then(json::Value::str).ok_or("Applying without a power")?;
            Condition::Applying(official_power(p).ok_or_else(|| format!("Applying: {p:?} is not an official power"))?)
        }
        Some(("HandNone", f)) => Condition::HandNone(card_type(f.and_then(json::Value::str))?),
        Some(("TargetLacks", f)) => {
            let p = f.and_then(json::Value::str).ok_or("TargetLacks without a power")?;
            Condition::TargetLacks(official_power(p).ok_or_else(|| format!("TargetLacks: {p:?} is not an official power"))?)
        }
        Some(("ApplyingDebuff", _)) if !applying => return Err("condition ApplyingDebuff is an OwnerApplied hook's only".into()),
        Some(("ApplyingDebuff", _)) => Condition::ApplyingDebuff,
        Some(("TargetDied", _)) => Condition::TargetDied,
        Some(("CounterAtMost", f)) => Condition::CounterAtMost(int(f, "CounterAtMost")? as i16),
        Some(("NotFirstTurn", _)) => Condition::NotFirstTurn,
        Some((x, _)) => return Err(format!("condition {x:?} not supported in a content pack")),
    })
}

/// A hook's `"condition"`: one condition, or a list of two that must both
/// hold (docs/specs/fight-vocabulary.md), at most one of them with a number
/// (the net row has one `condition_param`).
fn hook_conditions(v: Option<&json::Value>, applying: bool) -> Result<(Condition, Condition), String> {
    let Some(json::Value::Arr(list)) = v else {
        return Ok((condition_of(v, applying)?, Condition::Always));
    };
    let [a, b] = list.as_slice() else {
        return Err(format!("a hook's condition list holds two conditions, not {}", list.len()));
    };
    let (a, b) = (condition_of(Some(a), applying)?, condition_of(Some(b), applying)?);
    if condition_has_number(a) && condition_has_number(b) {
        return Err(format!("a hook's two conditions may carry one number between them, not two ({a:?}, {b:?})"));
    }
    Ok((a, b))
}

/// The condition carries a number (a net row's `condition_param`).
pub fn condition_has_number(c: Condition) -> bool {
    matches!(c, Condition::CardsPlayedThisTurnBelow(_) | Condition::CounterIs(_) | Condition::OwnerBlockIs(_) | Condition::CounterAtMost(_))
}

/// `power`: a pack power's registry index by name (none for official content).
/// A content file's `"version"`: 1 (`OwnerTurnStart` means after the draw)
/// or 2 (`OwnerTurnStart` before the draw, `OwnerTurnStartPostDraw` after;
/// docs/specs/turn-start-draw.md). Anything else is an error.
pub(crate) fn file_version(v: &json::Value) -> Result<u8, String> {
    match v.get("version").and_then(json::Value::int) {
        Some(1) => Ok(1),
        Some(2) => Ok(2),
        x => Err(format!("version must be 1 or 2, not {x:?}")),
    }
}

/// The file version official content is written in.
pub const CONTENT_VERSION: u8 = 2;

/// The keys a content power may carry: its structure; the rules it sets on
/// its owner's cards (each worded under `power_rule` in
/// `content/wording.json` and written as a `rule` row for the net,
/// docs/specs/card-rules.md); and the generator's metadata, which play
/// ignores. Any other key is a load error.
pub const POWER_STRUCTURE_KEYS: [&str; 5] = ["id", "debuff", "hooks", "statics", "replacements"];
pub const POWER_RULE_KEYS: [&str; 4] = ["forbids", "sets_cost", "exhausts_played", "plays_unplayable"];
/// The keys that set how applying a power works and how its owner attacks
/// (`PowerRules`) and how much block its owner keeps, each worded under `power_field` in
/// `content/wording.json`; the net reads none of them.
pub const POWER_FIELD_KEYS: [&str; 6] = ["debuff_if_negative", "can_go_negative", "skips_first_round", "attack_shape", "block_loss", "cap"];
/// The keys a hook row may carry beside its trigger, condition and
/// effects, each worded under `hook_field`.
pub const HOOK_FIELD_KEYS: [&str; 3] = ["hp_loss_source", "acts_first", "before_hand"];
pub const POWER_META_KEYS: [&str; 3] = ["split", "keys", "lifetime"];

fn parse_power(p: &json::Value, power: &dyn Fn(&str) -> Option<u16>, version: u8) -> Result<PowerSpec, String> {
    if let json::Value::Obj(kv) = p {
        let known = |k: &str| {
            POWER_STRUCTURE_KEYS.contains(&k) || POWER_RULE_KEYS.contains(&k) || POWER_FIELD_KEYS.contains(&k) || POWER_META_KEYS.contains(&k)
        };
        if let Some((k, _)) = kv.iter().find(|(k, _)| !known(k)) {
            return Err(format!("unknown power key {k:?}"));
        }
    }
    let hooks =
        p.get("hooks").map(json::Value::items).unwrap_or(&[]).iter().map(|h| parse_hook(h, power, version)).collect::<Result<Vec<_>, _>>()?;
    let statics = p.get("statics").map(json::Value::items).unwrap_or(&[]).iter().map(parse_static).collect::<Result<Vec<_>, _>>()?;
    let replacements =
        p.get("replacements").map(json::Value::items).unwrap_or(&[]).iter().map(parse_replacement).collect::<Result<Vec<_>, _>>()?;
    // Any card type (Blue Candle's Curse, Medical Kit's Status).
    let playable_type = |field: &str, f: &json::Value| -> Result<CardType, String> {
        card_type(f.str()).map_err(|_| format!("{field} {f:?}: Attack, Skill, Power, Status or Curse"))
    };
    let forbids = p.get("forbids").map(|f| playable_type("forbids", f)).transpose()?;
    let sets_cost = match p.get("sets_cost") {
        None => None,
        Some(f) => {
            let ty = playable_type("sets_cost type", f.get("type").unwrap_or(&json::Value::Null))?;
            let cost = int(f.get("cost"), "sets_cost cost")?;
            if !(0..=9).contains(&cost) {
                return Err(format!("sets_cost cost {cost}: 0 to 9"));
            }
            Some((ty, cost as i8))
        }
    };
    let exhausts_played = p.get("exhausts_played").map(|f| playable_type("exhausts_played", f)).transpose()?;
    let plays_unplayable = p.get("plays_unplayable").map(|f| playable_type("plays_unplayable", f)).transpose()?;
    let flag = |v: Option<&json::Value>, field: &str| -> Result<bool, String> {
        match v {
            None => Ok(false),
            Some(x) => x.bool().ok_or_else(|| format!("{field} {x:?}: true or false")),
        }
    };
    let skips_first_round = match p.get("skips_first_round") {
        None => SkipsFirstRound::default(),
        Some(f) => {
            let json::Value::Obj(kv) = f else {
                return Err(format!("skips_first_round {f:?}: an object with from_monster, from_monster_after_turn_end, on_monster"));
            };
            if let Some((k, _)) = kv.iter().find(|(k, _)| !["from_monster", "from_monster_after_turn_end", "on_monster"].contains(&k.as_str())) {
                return Err(format!("skips_first_round key {k:?}: from_monster, from_monster_after_turn_end or on_monster"));
            }
            SkipsFirstRound {
                from_monster: flag(f.get("from_monster"), "skips_first_round from_monster")?,
                from_monster_after_turn_end: flag(f.get("from_monster_after_turn_end"), "skips_first_round from_monster_after_turn_end")?,
                on_monster: flag(f.get("on_monster"), "skips_first_round on_monster")?,
            }
        }
    };
    let attack_shape = match p.get("attack_shape") {
        None => None,
        Some(f) => {
            let n = int(f.get("split"), "attack_shape split")?;
            if !(2..=4).contains(&n) {
                return Err(format!("attack_shape split {n}: 2 to 4"));
            }
            Some(n as u8)
        }
    };
    let block_loss = match p.get("block_loss") {
        None => None,
        Some(f) => {
            let n = int(Some(f), "block_loss")?;
            if !(0..=999).contains(&n) {
                return Err(format!("block_loss {n}: 0 to 999"));
            }
            Some(n as i16)
        }
    };
    let cap = match p.get("cap") {
        None => None,
        Some(f) => {
            let n = int(Some(f), "cap")?;
            if !(1..=i16::MAX as i64).contains(&n) {
                return Err(format!("cap {n}: 1 to {}", i16::MAX));
            }
            Some(n as i16)
        }
    };
    let rules = PowerRules {
        debuff: flag(p.get("debuff"), "debuff")?,
        debuff_if_negative: flag(p.get("debuff_if_negative"), "debuff_if_negative")?,
        can_go_negative: flag(p.get("can_go_negative"), "can_go_negative")?,
        skips_first_round,
        attack_shape,
        forbids,
        sets_cost,
        exhausts_played,
        plays_unplayable,
        block_loss,
        cap,
    };
    Ok(PowerSpec { hooks, rules, statics, replacements })
}

fn parse_static(v: &json::Value) -> Result<Static, String> {
    let modifies = match v.get("modifies").and_then(json::Value::str) {
        Some("DamageDealt") => Modifies::DamageDealt,
        Some("DamageTaken") => Modifies::DamageTaken,
        Some("BlockGained") => Modifies::BlockGained,
        x => return Err(format!("bad static modifies {x:?}")),
    };
    let stage = match v.get("stage").and_then(json::Value::str) {
        Some("Add") => StaticStage::Add,
        Some("Multiply") => StaticStage::Multiply,
        x => return Err(format!("bad static stage {x:?}")),
    };
    let condition = match v.get("condition").map(variant).transpose()? {
        None | Some(("Always", _)) => StaticCondition::Always,
        Some(("CardInPlayTagged", f)) => StaticCondition::CardInPlayTagged(tag(f.and_then(json::Value::str).ok_or("CardInPlayTagged without a tag")?)?),
        Some(("OwnerHpAtMostHalf", _)) => StaticCondition::OwnerHpAtMostHalf,
        Some(("Holds", f)) => {
            let side = match f.and_then(|f| f.get("side")).and_then(json::Value::str) {
                Some("Owner") => Side::Owner,
                Some("Opponent") => Side::Opponent,
                x => return Err(format!("Holds: side must be Owner or Opponent, got {x:?}")),
            };
            let p = f.and_then(|f| f.get("power")).and_then(json::Value::str).ok_or("Holds without a power")?;
            StaticCondition::Holds { side, power: official_power(p).ok_or_else(|| format!("Holds: {p:?} is not an official power"))? }
        }
        Some((x, _)) => return Err(format!("bad static condition {x:?}")),
    };
    let n = |k: &str, d: i64| v.get(k).and_then(json::Value::int).unwrap_or(d) as i16;
    if n("den", 1) <= 0 {
        return Err("a static's den must be positive".into());
    }
    Ok(Static { modifies, stage, amount: n("amount", 0), num: n("num", 1), den: n("den", 1), condition })
}

fn parse_replacement(v: &json::Value) -> Result<Replacement, String> {
    let event = match v.get("event").and_then(json::Value::str) {
        Some("DamageTaken") => Replaced::DamageTaken,
        Some("HpLoss") => Replaced::HpLoss,
        Some("DebuffApplied") => Replaced::DebuffApplied,
        Some("DealtAfterBlock") => Replaced::DealtAfterBlock,
        Some("TakenAfterBlock") => Replaced::TakenAfterBlock,
        Some("AttackedAfterBlock") => Replaced::AttackedAfterBlock,
        Some("HpLossLast") => Replaced::HpLossLast,
        Some("Draw") => Replaced::Draw,
        x => return Err(format!("bad replacement event {x:?}")),
    };
    let action = match variant(v.get("action").ok_or("replacement without an action")?)? {
        ("Cancel", _) => Replace::Cancel,
        ("Cap", f) => Replace::Cap(int(f, "Cap")? as i16),
        ("Add", f) => Replace::Add(int(f, "Add")? as i16),
        ("Multiply", f) => {
            let (num, den) = (int(f.and_then(|f| f.get("num")), "Multiply num")? as i16, int(f.and_then(|f| f.get("den")), "Multiply den")? as i16);
            if den <= 0 {
                return Err("a replacement's Multiply den must be positive".into());
            }
            Replace::Multiply(num, den)
        }
        ("AtLeast", f) => {
            let n = int(f, "AtLeast")? as i16;
            if n < 1 {
                return Err("a replacement's AtLeast must be at least 1".into());
            }
            Replace::AtLeast(n)
        }
        (x, _) => return Err(format!("bad replacement action {x:?}")),
    };
    let up_to = match v.get("upTo") {
        None => None,
        Some(f) => {
            let n = f.int().ok_or("a replacement's upTo is a number")?;
            if n < 0 {
                return Err("a replacement's upTo must be at least 0".into());
            }
            Some(n as i16)
        }
    };
    let power = match v.get("power") {
        None => None,
        Some(f) => {
            if event != Replaced::DebuffApplied {
                return Err(format!("only a DebuffApplied replacement names a power, not {event:?}"));
            }
            let p = f.str().ok_or("a replacement's power is a name")?;
            Some(official_power(p).ok_or_else(|| format!("replacement power: {p:?} is not an official power"))?)
        }
    };
    let mut then = Vec::new();
    for e in v.get("then").map(json::Value::items).unwrap_or(&[]) {
        match parse_effect(e)? {
            (e @ (Effect::RemoveSelf | Effect::ReduceSelf(_)), None) => then.push(e),
            _ => return Err("a replacement's `then` takes RemoveSelf / ReduceSelf only".into()),
        }
    }
    Ok(Replacement { event, power, up_to, action, then: leak(then) })
}

/// One `{"Variant": fields}` or `"Variant"` value: (name, fields).
fn variant(v: &json::Value) -> Result<(&str, Option<&json::Value>), String> {
    if let Some(s) = v.str() {
        return Ok((s, None));
    }
    match v {
        json::Value::Obj(kv) if kv.len() == 1 => Ok((kv[0].0.as_str(), Some(&kv[0].1))),
        _ => Err(format!("expected a variant, got {v:?}")),
    }
}

fn int(v: Option<&json::Value>, what: &str) -> Result<i64, String> {
    v.and_then(json::Value::int).ok_or_else(|| format!("{what}: expected an integer"))
}

/// An effect; for `Apply` of a generated power, the power as `GEN[0]` and its id.
fn parse_effect(v: &json::Value) -> Result<(Effect, Option<String>), String> {
    let (name, f) = variant(v)?;
    let field = |k: &str| f.and_then(|f| f.get(k));
    let n = |what: &str| int(f, what);
    Ok(match name {
        "Damage" => (
            Effect::Damage {
                amount: int(field("amount"), "Damage amount")? as i16,
                hits: field("hits").and_then(json::Value::int).unwrap_or(1) as u8,
                target: target(field("target"))?,
            },
            None,
        ),
        "PlainDamage" => {
            (Effect::PlainDamage { amount: int(field("amount"), "PlainDamage amount")? as i16, target: target(field("target"))? }, None)
        }
        // A random target is a `PlainDamage`'s only (the game's
        // `DamageRandomEnemyAction`; Sword Boomerang's attack is
        // `RandomDamage`).
        _ if f.is_some_and(|f| f.get("target").and_then(json::Value::str) == Some("RandomOpponent")) => {
            return Err(format!("target RandomOpponent on {name}: only PlainDamage takes it"));
        }
        "CapHp" => {
            let k = |key: &str, d: i64| field(key).map(|v| int(Some(v), &format!("CapHp {key}"))).unwrap_or(Ok(d));
            let (amount, num, den) = (k("amount", 0)?, k("num", 0)?, k("den", 1)?);
            if den <= 0 || num < 0 || amount < 0 || (amount == 0 && num == 0) {
                return Err(format!("CapHp: amount {amount} + num {num} / den {den} needs den above 0, amounts not below 0 and a cap above 0"));
            }
            (Effect::CapHp { amount: amount as i16, num: num as i16, den: den as i16, target: target(field("target"))? }, None)
        }
        "Block" => (Effect::Block(n("Block")? as i16), None),
        "BlockOf" => (Effect::BlockOf(amount(f, "BlockOf")?), None),
        "ScaledBlock" => (
            Effect::ScaledBlock { amount: int(field("amount"), "ScaledBlock amount")? as i16, times: amount(field("times"), "ScaledBlock times")? },
            None,
        ),
        "ExhaustHand" => (Effect::ExhaustHand { except: except(f)? }, None),
        "ExhaustRandom" => (Effect::ExhaustRandom, None),
        "ZeroCostRandom" => (Effect::ZeroCostRandom, None),
        "ZeroCostRandomTurn" => (Effect::ZeroCostRandomTurn, None),
        "UpgradeRandom" => (Effect::UpgradeRandom, None),
        "CostAtMost" => {
            let cost = int(field("cost"), "CostAtMost cost")?;
            if !(0..=9).contains(&cost) {
                return Err(format!("CostAtMost cost {cost}: 0 to 9"));
            }
            let combat = field("combat").map_or(Ok(false), |v| v.bool().ok_or("CostAtMost combat: expected true or false"))?;
            (Effect::CostAtMost { cost: cost as i8, combat }, None)
        }
        "Draw" => (Effect::Draw(n("Draw")? as u8), None),
        "RandomizeCost" => (
            Effect::RandomizeCost(match f.and_then(json::Value::str) {
                Some("Hand") => CostRoll::Hand,
                Some("Drawn") => CostRoll::Drawn,
                x => return Err(format!("RandomizeCost takes \"Hand\" or \"Drawn\", not {x:?}")),
            }),
            None,
        ),
        "GainEnergy" => (Effect::GainEnergy(n("GainEnergy")? as i8), None),
        "LoseHp" => (Effect::LoseHp(n("LoseHp")? as i16), None),
        "LoseHpOf" => (Effect::LoseHpOf(amount(f, "LoseHpOf")?), None),
        "AddCopy" => {
            let pile = match field("pile").and_then(json::Value::str) {
                Some("Draw") => PileKind::Draw,
                Some("Discard") => PileKind::Discard,
                Some("Hand") => PileKind::Hand,
                x => return Err(format!("bad pile {x:?}")),
            };
            let n = field("n").map_or(Ok(1), |v| int(Some(v), "AddCopy n"))?;
            if !(1..=10).contains(&n) {
                return Err(format!("AddCopy n {n}: 1 to 10"));
            }
            (Effect::AddCopy { n: n as u8, pile }, None)
        }
        "Heal" => (Effect::Heal(n("Heal")? as i16), None),
        "GainMaxHp" => (Effect::GainMaxHp(n("GainMaxHp")? as i16), None),
        "HealOf" => (Effect::HealOf(amount(f, "HealOf")?), None),
        "WinHeal" => (Effect::WinHeal(n("WinHeal")? as i16), None),
        "ReduceSelf" => (Effect::ReduceSelf(n("ReduceSelf")? as i16), None),
        "RemoveSelf" => (Effect::RemoveSelf, None),
        "ScaledDamage" => (
            Effect::ScaledDamage {
                amount: amount(field("amount"), "ScaledDamage amount")?,
                hits: field("hits").map_or(Ok(Amount::constant(1)), |h| amount(Some(h), "ScaledDamage hits"))?,
                target: target(field("target"))?,
            },
            None,
        ),
        "RandomDamage" => (
            Effect::RandomDamage { amount: int(field("amount"), "RandomDamage amount")? as i16, hits: int(field("hits"), "RandomDamage hits")? as u8 },
            None,
        ),
        "RandomApply" => {
            let p = field("power").and_then(json::Value::str).ok_or("RandomApply without a power")?;
            let (amount, hits) = (int(field("amount"), "RandomApply amount")? as i16, int(field("hits"), "RandomApply hits")? as u8);
            match official_power(p) {
                Some(power) => (Effect::RandomApply { power, amount, hits }, None),
                None => (Effect::RandomApply { power: Power::GEN[0], amount, hits }, Some(p.to_string())),
            }
        }
        "AddCard" => {
            let pile = match field("pile").and_then(json::Value::str) {
                Some("Draw") => PileKind::Draw,
                Some("Discard") => PileKind::Discard,
                Some("Hand") => PileKind::Hand,
                x => return Err(format!("bad pile {x:?}")),
            };
            (Effect::AddCard { card: official_card(field("card"))?, n: field("n").and_then(json::Value::int).unwrap_or(1) as u8, pile }, None)
        }
        "Pick" => {
            let kind = match field("kind").and_then(json::Value::str) {
                Some("DiscardFromHand") => PickKind::DiscardFromHand,
                Some("ReturnFromDiscard") => PickKind::ReturnFromDiscard,
                Some("DiscardToTop") => PickKind::DiscardToTop,
                Some("ExhaustFromHand") => PickKind::ExhaustFromHand,
                Some("ReturnFromExhaust") => PickKind::ReturnFromExhaust,
                Some("UpgradeFromHand") => PickKind::UpgradeFromHand,
                Some("HandToTop") => PickKind::HandToTop,
                Some("CopyInHand") => PickKind::CopyInHand,
                x => return Err(format!("bad pick kind {x:?}")),
            };
            let free = field("free_this_turn").and_then(json::Value::bool).unwrap_or(false);
            if free && !matches!(kind, PickKind::ReturnFromDiscard | PickKind::ReturnFromExhaust | PickKind::CopyInHand) {
                return Err(format!("Pick free_this_turn: only a pick into the hand (ReturnFromDiscard, ReturnFromExhaust, CopyInHand), not {kind:?}"));
            }
            // `of`: the card types it may pick, every type when absent.
            let of = match field("of") {
                None => Types::ALL,
                Some(v) => {
                    let types = v.items().iter().map(|t| card_type(t.str())).collect::<Result<Vec<_>, _>>()?;
                    if types.is_empty() {
                        return Err("Pick of: at least one card type".into());
                    }
                    Types::of(&types)
                }
            };
            let copies = match (kind, field("copies")) {
                (PickKind::CopyInHand, c) => match c.map(|c| int(Some(c), "Pick copies")).transpose()?.unwrap_or(1) {
                    c @ 1..=255 => c as u8,
                    c => return Err(format!("Pick copies {c}: 1 to 255")),
                },
                (_, None) => 0,
                (_, Some(_)) => return Err(format!("Pick copies: only a CopyInHand pick's, not {kind:?}'s")),
            };
            (Effect::Pick { kind, n: int(field("n"), "Pick n")? as u8, exact: field("exact").and_then(json::Value::bool).unwrap_or(true), free, of, copies }, None)
        }
        "ReplayCard" => (Effect::ReplayCard, None),
        "GrowDamage" => (Effect::GrowDamage(n("GrowDamage")? as i16), None),
        "UpgradeHand" => (Effect::UpgradeHand, None),
        "UpgradeAll" => (Effect::UpgradeAll, None),
        "ShuffleDiscardIntoDraw" => (Effect::ShuffleDiscardIntoDraw, None),
        "RemoveDebuffs" => (Effect::RemoveDebuffs, None),
        "DrawPicked" => (Effect::DrawPicked, None),
        "PlayTop" => {
            let n = int(field("n"), "PlayTop n")?;
            if !(1..=crate::state::TOP_QUEUE_CAP as i64).contains(&n) {
                return Err(format!("PlayTop n {n}: 1 to {}", crate::state::TOP_QUEUE_CAP));
            }
            (Effect::PlayTop { n: n as u8, exhaust: field("exhaust").and_then(json::Value::bool).unwrap_or(false) }, None)
        }
        "ObtainRandomPotions" => (crate::potions::parse_obtain_random(f)?, None),
        "Discover" => {
            let name = field("pool").and_then(json::Value::str).ok_or("Discover without a pool")?;
            // While a pack loads, its own pools too; else (one card parsed
            // alone: `card_level`) the loaded ones.
            let pool = POOL_NAMES
                .with(|p| p.borrow().iter().position(|n| n == name))
                .or_else(|| (0..POOL_CAPACITY).map_while(|i| POOL_DEFS[i].get()).position(|p| p.name == name))
                .ok_or_else(|| format!("Discover: unknown pool {name:?} (a pool loaded before or in this pack)"))?;
            let ty = match field("type").and_then(json::Value::str) {
                None => None,
                Some(t @ ("Attack" | "Skill" | "Power")) => Some(card_type(Some(t))?),
                Some(t) => return Err(format!("Discover: type {t:?} (Attack, Skill or Power)")),
            };
            let num = |k: &str, default: i64, lo: i64, hi: i64| -> Result<u8, String> {
                let n = field(k).map_or(Ok(default), |v| v.int().ok_or_else(|| format!("Discover {k}: expected an integer")))?;
                if (lo..=hi).contains(&n) { Ok(n as u8) } else { Err(format!("Discover {k} {n}: {lo} to {hi}")) }
            };
            let flag = |k: &str| field(k).map_or(Ok(false), |v| v.bool().ok_or_else(|| format!("Discover {k}: expected true or false")));
            let (offer, copies) = (num("offer", 3, 1, 3)?, num("copies", 1, 1, 5)?);
            (Effect::Discover { pool: pool as u8, ty, offer, copies, free: flag("free")?, skip: flag("skip")? }, None)
        }
        "MakeRandom" => {
            let name = field("pool").and_then(json::Value::str).ok_or("MakeRandom without a pool")?;
            // "Class": the player's class pool, found per fight (a relic's hook only).
            let pool = if name == "Class" {
                CLASS_POOL as usize
            } else {
                POOL_NAMES
                    .with(|p| p.borrow().iter().position(|n| n == name))
                    .or_else(|| (0..POOL_CAPACITY).map_while(|i| POOL_DEFS[i].get()).position(|p| p.name == name))
                    .ok_or_else(|| format!("MakeRandom: unknown pool {name:?} (a pool loaded before or in this pack)"))?
            };
            let ty = match field("type").and_then(json::Value::str) {
                None => None,
                Some(t @ ("Attack" | "Skill" | "Power")) => Some(card_type(Some(t))?),
                Some(t) => return Err(format!("MakeRandom: type {t:?} (Attack, Skill or Power)")),
            };
            let pile = match field("pile").and_then(json::Value::str) {
                Some("Hand") => PileKind::Hand,
                Some("Draw") => PileKind::Draw,
                x => return Err(format!("MakeRandom pile {x:?}: Hand or Draw")),
            };
            let n = amount(field("n"), "MakeRandom n")?;
            if n.of.is_none() && !(1..=10).contains(&n.base) {
                return Err(format!("MakeRandom n {}: 1 to 10", n.base));
            }
            let flag = |k: &str| field(k).map_or(Ok(false), |v| v.bool().ok_or_else(|| format!("MakeRandom {k}: expected true or false")));
            let e = Effect::MakeRandom { pool: pool as u8, ty, n, pile, zero_cost: flag("zero_cost")?, free: flag("free")?, match_level: flag("match_level")? };
            (e, None)
        }
        "SetCounter" => (Effect::SetCounter(n("SetCounter")? as i16), None),
        "AddCounter" => (Effect::AddCounter(n("AddCounter")? as i16), None),
        "Apply" => {
            let p = field("power").and_then(json::Value::str).ok_or("Apply without a power")?;
            let amount = int(field("amount"), "Apply amount")? as i16;
            let target = target(field("target"))?;
            match official_power(p) {
                Some(power) => (Effect::Apply { power, amount, target }, None),
                None => (Effect::Apply { power: Power::GEN[0], amount, target }, Some(p.to_string())),
            }
        }
        "ApplyAsMonster" => {
            let p = field("power").and_then(json::Value::str).ok_or("ApplyAsMonster without a power")?;
            let power = official_power(p).ok_or_else(|| format!("ApplyAsMonster of a pack power ({p:?}) is not supported"))?;
            (Effect::ApplyAsMonster { power, amount: int(field("amount"), "ApplyAsMonster amount")? as i16, target: target(field("target"))? }, None)
        }
        "ApplyOf" => {
            let p = field("power").and_then(json::Value::str).ok_or("ApplyOf without a power")?;
            let power = official_power(p).ok_or_else(|| format!("ApplyOf of a pack power ({p:?}) is not supported"))?;
            (Effect::ApplyOf { power, amount: amount(field("amount"), "ApplyOf amount")?, target: target(field("target"))? }, None)
        }
        x => return Err(format!("effect {x:?} not supported in a content pack")),
    })
}

fn parse_hook(v: &json::Value, power: &dyn Fn(&str) -> Option<u16>, version: u8) -> Result<Hook, String> {
    parse_hook_of(v, power, version, false)
}

/// A hook of a power, or with `relic` of a relic (docs/specs/relic-entity.md):
/// only a relic's hooks may change its counter, and only a power's may
/// act on its own stacks.
pub(crate) fn parse_hook_of(v: &json::Value, power: &dyn Fn(&str) -> Option<u16>, version: u8, relic: bool) -> Result<Hook, String> {
    let (t, tf) = variant(v.get("trigger").ok_or("hook without a trigger")?)?;
    let side = |f: Option<&json::Value>| match f.and_then(|f| f.get("by")).and_then(json::Value::str) {
        Some("Owner") => Ok(Side::Owner),
        Some("Opponent") => Ok(Side::Opponent),
        x => Err(format!("bad side {x:?}")),
    };
    let trigger = match t {
        // A version-1 file's turn start ran after the draw.
        "OwnerTurnStart" if version == 1 => Trigger::OwnerTurnStartPostDraw,
        "OwnerTurnStart" => Trigger::OwnerTurnStart,
        "OwnerTurnStartPostDraw" if version == 1 => {
            return Err("trigger OwnerTurnStartPostDraw needs a version-2 file (in version 1, OwnerTurnStart is after the draw)".into())
        }
        "OwnerTurnStartPostDraw" => Trigger::OwnerTurnStartPostDraw,
        "OwnerTurnEnd" => Trigger::OwnerTurnEnd,
        "CardPlayed" => Trigger::CardPlayed { by: side(tf)? },
        "OwnerLostHp" => Trigger::OwnerLostHp {
            from: match tf.and_then(|f| f.get("from")).and_then(json::Value::str) {
                Some("Attack") => HpLossFrom::Attack,
                Some("Card") => HpLossFrom::Card,
                Some("Any") => HpLossFrom::Any,
                x => return Err(format!("bad HP loss source {x:?}")),
            },
        },
        "OwnerDied" => Trigger::OwnerDied,
        "RoundEnd" => Trigger::RoundEnd,
        "OwnerAttacked" => Trigger::OwnerAttacked,
        "OwnerPlaysCard" => Trigger::OwnerPlaysCard,
        "OwnerAttackHit" => Trigger::OwnerAttackHit,
        "CardExhausted" => Trigger::CardExhausted,
        "CardDrawn" => Trigger::CardDrawn,
        "OwnerBloodied" => Trigger::OwnerBloodied,
        "OwnerUnbloodied" => Trigger::OwnerUnbloodied,
        "CombatStartPreDraw" => Trigger::CombatStartPreDraw,
        "CombatStart" => Trigger::CombatStart,
        "OpponentDied" => Trigger::OpponentDied,
        "CombatWon" => Trigger::CombatWon,
        "OwnerApplied" => Trigger::OwnerApplied,
        "Shuffled" => Trigger::Shuffled,
        "OwnerUsedPotion" => Trigger::OwnerUsedPotion,
        "OpponentBlockBroken" => Trigger::OpponentBlockBroken,
        "OwnerHandEmpty" => Trigger::OwnerHandEmpty,
        "OwnerGainedBlock" => Trigger::OwnerGainedBlock,
        x => return Err(format!("trigger {x:?} not supported in a content pack")),
    };
    let (condition, also) = hook_conditions(v.get("condition"), trigger == Trigger::OwnerApplied)?;
    if also != Condition::Always && matches!(trigger, Trigger::CardExhausted | Trigger::CardDrawn) {
        return Err(format!("a {trigger:?} hook takes one condition, not two"));
    }
    if trigger == Trigger::CardExhausted && condition != Condition::Always {
        return Err(format!("a CardExhausted hook's condition must be Always (it fires once for every card exhausted), not {condition:?}"));
    }
    // Status and Curse draws are counted for their hooks (a hook on both is
    // two hooks: Fire Breathing); `Always` is the drawn card's cost roll
    // only (Confused, docs/specs/sparse-piles.md).
    if trigger == Trigger::CardDrawn && !matches!(condition, Condition::CardType(CardType::Status | CardType::Curse) | Condition::Always) {
        return Err(format!("a CardDrawn hook's condition must be CardType Status or Curse (only those draws are counted) or Always (a RandomizeCost Drawn), not {condition:?}"));
    }
    if trigger == Trigger::Shuffled && !relic {
        return Err("a Shuffled hook is a relic's (the game's onShuffle)".into());
    }
    let mut effects = Vec::new();
    for e in v.get("effects").map(json::Value::items).unwrap_or(&[]) {
        let (mut e, g) = parse_effect(e)?;
        if let Some(g) = g {
            // An Apply of a pack power loaded before or anywhere in this pack.
            let (Effect::Apply { amount, target, .. }, Some(pi)) = (e, power(&g)) else {
                return Err(format!("a generated power's hook applies {g:?}, not a loaded pack power in an Apply"));
            };
            e = Effect::ApplyPack { power: pi, amount, target };
        }
        // A Shuffled hook runs inside a draw's request: nothing that draws
        // or moves cards.
        if trigger == Trigger::Shuffled && !matches!(e, Effect::Block(_) | Effect::GainEnergy(_) | Effect::SetCounter(_) | Effect::AddCounter(_)) {
            return Err(format!("a Shuffled hook gains block or energy or changes a counter only (it runs inside a draw), not {e:?}"));
        }
        if trigger == Trigger::CombatWon && !matches!(e, Effect::Heal(_) | Effect::HealOf(_) | Effect::SetCounter(_) | Effect::AddCounter(_)) {
            return Err(format!("a CombatWon hook heals or changes a counter only (the fight is over), not {e:?}"));
        }
        // It may run after the potion ended the fight (only a queued heal
        // survives the game's `clearPostCombatActions`).
        if trigger == Trigger::OwnerUsedPotion && !matches!(e, Effect::Heal(_) | Effect::HealOf(_) | Effect::SetCounter(_) | Effect::AddCounter(_)) {
            return Err(format!("an OwnerUsedPotion hook heals or changes a counter only (it may run once the potion ended the fight), not {e:?}"));
        }
        // A relic's OwnerDied hook runs inside the HP loss that would kill
        // the player: it can only save (docs/specs/would-die.md).
        if relic && trigger == Trigger::OwnerDied && !matches!(e, Effect::Heal(_) | Effect::HealOf(_) | Effect::SetCounter(_) | Effect::AddCounter(_)) {
            return Err(format!("a relic's OwnerDied hook heals or changes a counter only (it runs as the player would die), not {e:?}"));
        }
        // A relic's hook may pick at the fight's start or after the turn's
        // draw (Gambling Chip): the pick opens once the pass has run.
        let relic_pick = relic && matches!(trigger, Trigger::CombatStart | Trigger::OwnerTurnStartPostDraw) && matches!(e, Effect::Pick { .. });
        // A relic's offer before the opening draw (Toolbox): it opens once
        // the pre-draw pass has run (`Stage::RelicOffer`).
        let relic_offer = relic && trigger == Trigger::CombatStartPreDraw && matches!(e, Effect::Discover { .. });
        // Random work a hook owes waits for `run` to pay it (Dead Branch,
        // Mummified Hand, Warped Tongs; docs/specs/blocked-relics.md step 5).
        if let Effect::MakeRandom { match_level: true, .. } = e {
            return Err("MakeRandom match_level in a hook (no card in play to match)".into());
        }
        if !relic && matches!(e, Effect::MakeRandom { pool: CLASS_POOL, .. }) {
            return Err("MakeRandom pool \"Class\" is a relic's hook's (the fight's character picks the pool)".into());
        }
        let owed = matches!(
            e,
            Effect::MakeRandom { .. } | Effect::ZeroCostRandom | Effect::ZeroCostRandomTurn | Effect::UpgradeRandom
                | Effect::PlainDamage { target: Target::RandomOpponent, .. }
                | Effect::PlayTop { .. }
        );
        // A hook's take waits behind the turn start's work (Mayhem), and
        // is paid once the turn settles: not in a hook whose turn or
        // fight ends before that.
        if matches!(e, Effect::PlayTop { .. })
            && matches!(trigger, Trigger::OwnerTurnEnd | Trigger::RoundEnd | Trigger::OwnerDied | Trigger::CombatWon | Trigger::OwnerUsedPotion)
        {
            return Err(format!("{e:?} in a hook of {trigger:?}: only a hook of a trigger that leaves the turn open may play the top card"));
        }
        if !runs_outside_a_card(&e) && !relic_pick && !relic_offer && !owed {
            return Err(format!("{e:?} can't run in a hook (only while a card resolves)"));
        }
        if !relic && matches!(e, Effect::SetCounter(_) | Effect::AddCounter(_)) {
            return Err(format!("{e:?} changes a relic's counter: only a relic's hook may use it"));
        }
        if relic && matches!(e, Effect::RemoveSelf | Effect::ReduceSelf(_)) {
            return Err(format!("{e:?} acts on a power's stacks: a relic's hook can't use it"));
        }
        if trigger == Trigger::CardExhausted && matches!(e, Effect::ExhaustHand { .. }) {
            return Err(format!("{e:?} can't be in a CardExhausted hook (it would exhaust again)"));
        }
        if trigger == Trigger::CardDrawn && matches!(e, Effect::ExhaustHand { .. }) {
            return Err(format!("{e:?} can't be in a CardDrawn hook (only Draw may follow a draw's reaction)"));
        }
        let rolls_drawn = trigger == Trigger::CardDrawn && condition == Condition::Always;
        if rolls_drawn != (e == Effect::RandomizeCost(CostRoll::Drawn)) {
            return Err(format!("RandomizeCost Drawn is a CardDrawn hook's with condition Always, and such a hook has only it, not {e:?}"));
        }
        effects.push(e);
    }
    draw_picked_follows_a_pick(&effects)?;
    if effects.iter().filter(|e| matches!(e, Effect::Pick { .. })).count() > 1 {
        return Err("a relic's hook picks at most once".into());
    }
    let hp_loss = match v.get("hp_loss_source") {
        None => HpLossFrom::Card,
        Some(f) => {
            let from = match f.str() {
                Some("Card") => HpLossFrom::Card,
                Some("Any") => HpLossFrom::Any,
                _ => return Err(format!("hp_loss_source {f:?}: Card or Any")),
            };
            if !effects.iter().any(|e| matches!(e, Effect::LoseHp(_))) {
                return Err("hp_loss_source on a hook without a LoseHp effect".into());
            }
            from
        }
    };
    // The game queues a turn-end pass's work: `acts_first` puts the hook's
    // ahead of what the pass queued before it (`addToTop`).
    let first = match v.get("acts_first") {
        None => false,
        Some(f) => f.bool().ok_or_else(|| format!("acts_first {f:?}: true or false"))?,
    };
    if first && !matches!(trigger, Trigger::OwnerTurnEnd | Trigger::RoundEnd) {
        return Err(format!("acts_first on a {trigger:?} hook (only OwnerTurnEnd and RoundEnd hooks are queued in one pass)"));
    }
    // The stage of the player's End Turn (`Hook::before_hand`): a relic's
    // turn-end hook is the game's `onPlayerEndTurn`, before the hand's
    // turn-end cards; a power's is `atEndOfTurn`, after them, unless its
    // row says `before_hand` (`atEndOfTurnPreEndTurnCards`).
    let before_hand = match v.get("before_hand") {
        None => relic && trigger == Trigger::OwnerTurnEnd,
        Some(f) => f.bool().ok_or_else(|| format!("before_hand {f:?}: true or false"))?,
    };
    if v.get("before_hand").is_some() && trigger != Trigger::OwnerTurnEnd {
        return Err(format!("before_hand on a {trigger:?} hook (only OwnerTurnEnd hooks act in End Turn's stages)"));
    }
    Ok(Hook { trigger, condition, also, effects: leak(effects), hp_loss, first, before_hand })
}

/// Effects that pause or step a card in play (picks, random hits) run only
/// while a card resolves, not from a hook or at turn end.
fn runs_outside_a_card(e: &Effect) -> bool {
    !matches!(
        e,
        Effect::Pick { .. }
            | Effect::RandomDamage { .. }
            | Effect::RandomApply { .. }
            | Effect::ExhaustRandom
            | Effect::ZeroCostRandom
            | Effect::ZeroCostRandomTurn
            | Effect::UpgradeRandom
            | Effect::PlayTop { .. }
            | Effect::Discover { .. }
            | Effect::MakeRandom { .. }
            | Effect::ObtainRandomPotions { .. }
            | Effect::PlainDamage { target: Target::RandomOpponent, .. }
    )
}

/// A card row's effects and the generated powers they name.
pub(crate) fn card_effects(v: Option<&json::Value>) -> Result<(Vec<Effect>, Vec<Option<String>>), String> {
    let (mut effects, mut gen) = (Vec::new(), Vec::new());
    for e in v.map(json::Value::items).unwrap_or(&[]) {
        if let Some(m) = e.get("AddCard").and_then(|f| f.get("match_level")) {
            m.bool().ok_or("AddCard match_level: expected true or false")?;
        }
        let (e, g) = parse_effect(e)?;
        if matches!(e, Effect::RemoveSelf | Effect::ReduceSelf(_) | Effect::ReplayCard | Effect::SetCounter(_) | Effect::AddCounter(_) | Effect::RandomizeCost(CostRoll::Drawn)) {
            return Err("RemoveSelf / ReduceSelf / ReplayCard / SetCounter / AddCounter / RandomizeCost Drawn on a card".into());
        }
        if matches!(e, Effect::MakeRandom { pool: CLASS_POOL, .. }) {
            return Err("MakeRandom pool \"Class\" on a card (only a relic's hook names it)".into());
        }
        effects.push(e);
        gen.push(g);
    }
    draw_picked_follows_a_pick(&effects)?;
    Ok((effects, gen))
}

/// Each `DrawPicked` comes right after a `Pick` in its list
/// (docs/specs/fight-vocabulary.md).
fn draw_picked_follows_a_pick(effects: &[Effect]) -> Result<(), String> {
    for (i, e) in effects.iter().enumerate() {
        if *e == Effect::DrawPicked && !(i > 0 && matches!(effects[i - 1], Effect::Pick { .. })) {
            return Err("DrawPicked comes right after a Pick in the same row".into());
        }
    }
    Ok(())
}

/// The indices of `match_level: true` AddCard effects in an effect list.
fn match_levels(v: Option<&json::Value>) -> Vec<usize> {
    let on = |e: &json::Value| e.get("AddCard").and_then(|f| f.get("match_level")).and_then(json::Value::bool) == Some(true);
    v.map(json::Value::items).unwrap_or(&[]).iter().enumerate().filter(|(_, e)| on(e)).map(|(i, _)| i).collect()
}

/// An entry's `upgrade` block: paths to their changes.
fn parse_upgrade(v: &json::Value) -> Result<Vec<(Path, Change)>, String> {
    let json::Value::Obj(kv) = v else { return Err("upgrade: expected an object of path: change".into()) };
    kv.iter()
        .map(|(k, c)| {
            let path = Path::parse(k)?;
            let change = match &path {
                Path::Keyword(_) => Change::Set(c.bool().ok_or_else(|| format!("upgrade {k:?}: a keyword takes true or false"))?),
                // A true / false field of an effect (`CostAtMost.combat`).
                _ if c.bool().is_some() => Change::Set(c.bool().expect("checked")),
                _ => match (c.int(), c.str()) {
                    (Some(n), _) => Change::Add(Expr::constant(n)),
                    (_, Some(e)) => Change::Add(Expr::parse(e)?),
                    _ => return Err(format!("upgrade {k:?}: a number takes an integer or an expression of n")),
                },
            };
            Ok((path, change))
        })
        .collect::<Result<Vec<_>, String>>()
        .map(|mut v| {
            // Key order carries no meaning (packs pass through sorted JSON).
            v.sort_by_key(|(p, _)| p.write());
            v
        })
}

/// Fields only the official content files may use.
const OFFICIAL_CARD_FIELDS: [&str; 1] = ["class"];

/// Pool flags older official files carry: the official loader ignores them
/// (pools are `configs/card-sets.json`), packs refuse them as official-only.
const OLD_POOL_FIELDS: [&str; 2] = ["held_out", "proving"];

fn parse_card(v: &json::Value, version: u8) -> Result<CardSpec, String> {
    parse_card_as(v, false, version)
}

/// The keys a content card may carry: its structure; the rules it sets on
/// play (each worded under `card_rule` in `content/wording.json` and read by
/// the net, as a column or a `rule` row, docs/specs/card-rules.md); and the
/// generator's metadata, which play ignores. `only_attacks_in_hand` is
/// version 1's form of `playable_if`. Any other key is a load error.
pub const CARD_STRUCTURE_KEYS: [&str; 21] = [
    "id", "cost", "type", "class", "exhaust", "ethereal", "retain", "innate", "tags", "effects", "rows", "turn_end", "exhausted",
    "upgrade", "max_level", "successor", "x_cost", "unplayable", "held_out", "proving", "other_played",
];
pub const CARD_RULE_KEYS: [&str; 3] = ["cost_less_per_hp_loss", "playable_if", "plays_per_turn"];
pub const CARD_META_KEYS: [&str; 4] = ["gain", "power", "split", "value_per_energy"];
const OLD_CLASH_KEY: &str = "only_attacks_in_hand";

/// `official`: an entry of `content/cards.json`, which may use the
/// official-only fields.
fn parse_card_as(v: &json::Value, official: bool, version: u8) -> Result<CardSpec, String> {
    if let Some(k) = OFFICIAL_CARD_FIELDS.into_iter().chain(OLD_POOL_FIELDS).find(|k| !official && v.get(k).is_some()) {
        return Err(format!("field {k:?} is for official content only"));
    }
    if let json::Value::Obj(kv) = v {
        let known = |k: &str| {
            CARD_STRUCTURE_KEYS.contains(&k) || CARD_RULE_KEYS.contains(&k) || CARD_META_KEYS.contains(&k) || k == OLD_CLASH_KEY
        };
        if let Some((k, _)) = kv.iter().find(|(k, _)| !known(k)) {
            return Err(format!("unknown card key {k:?}"));
        }
    }
    // Clash's condition: `playable_if` from version 2, the old flag before.
    let playable_if = match (version, v.get(OLD_CLASH_KEY), v.get("playable_if")) {
        (1, _, Some(_)) => return Err("playable_if needs a version-2 file (version 1 says only_attacks_in_hand)".into()),
        (1, old, None) => old.and_then(json::Value::bool).unwrap_or(false).then_some(Condition::HandAll(CardType::Attack)),
        (_, Some(_), _) => {
            return Err("only_attacks_in_hand is version 1's form: a version-2 file says playable_if: {\"HandAll\": \"Attack\"}".into())
        }
        (_, None, c) => c.map(|c| condition(Some(c))).transpose()?,
    };
    let flag = |k: &str| v.get(k).and_then(json::Value::bool).unwrap_or(false);
    let (effects, gen) = card_effects(v.get("effects"))?;
    let mut rows = vec![(Condition::Always, effects, gen)];
    let mut matches: Vec<(Section, usize)> = match_levels(v.get("effects")).into_iter().map(|i| (Section::Row(0), i)).collect();
    for (j, r) in v.get("rows").map(json::Value::items).unwrap_or(&[]).iter().enumerate() {
        let (effects, gen) = card_effects(r.get("effects"))?;
        rows.push((condition(r.get("condition"))?, effects, gen));
        matches.extend(match_levels(r.get("effects")).into_iter().map(|i| (Section::Row(j + 1), i)));
    }
    matches.extend(match_levels(v.get("turn_end")).into_iter().map(|i| (Section::TurnEnd, i)));
    let upgrade = match v.get("upgrade") {
        Some(u) => Some(Upgrade { changes: parse_upgrade(u)?, match_level: matches }),
        None if !matches.is_empty() => return Err("match_level without an upgrade block".into()),
        None => None,
    };
    let max_level = match v.get("max_level") {
        None => None,
        Some(json::Value::Null) => Some(LEVEL_CAP),
        Some(m) => Some(m.int().and_then(|m| u8::try_from(m).ok()).ok_or("max_level: an integer 0 to 255, or null")?),
    };
    let (turn_end, turn_end_gen) = card_effects(v.get("turn_end"))?;
    if turn_end_gen.iter().any(Option::is_some) {
        return Err("a card's turn_end applies a generated power (not supported)".into());
    }
    if let Some(e) = turn_end.iter().find(|e| !runs_outside_a_card(e) || matches!(e, Effect::GrowDamage(_) | Effect::AddCopy { .. })) {
        return Err(format!("{e:?} can't run at turn end (only while a card resolves)"));
    }
    let (exhausted, exhausted_gen) = card_effects(v.get("exhausted"))?;
    if let Some(e) = exhausted
        .iter()
        .zip(&exhausted_gen)
        .find(|(e, g)| g.is_some() || !matches!(e, Effect::GainEnergy(_) | Effect::Block(_) | Effect::AddCard { .. } | Effect::AddCopy { .. }))
    {
        return Err(format!("{:?} can't be a card's exhausted effect (GainEnergy, Block, AddCard and AddCopy only)", e.0));
    }
    // While held, each other card played (Pain): effects that need no card
    // in play and no chance event.
    let (other_played, other_gen) = card_effects(v.get("other_played"))?;
    if other_gen.iter().any(Option::is_some) {
        return Err("a card's other_played applies a generated power (not supported)".into());
    }
    if let Some(e) = other_played.iter().find(|e| !runs_outside_a_card(e) || matches!(e, Effect::GrowDamage(_) | Effect::AddCopy { .. })) {
        return Err(format!("{e:?} can't be a card's other_played effect (it runs while another card is played)"));
    }
    // `AddCopy` names the card it is on: only where the engine knows it.
    if let Some((_, e, _)) = rows.iter().find(|(_, e, _)| e.iter().any(|e| matches!(e, Effect::AddCopy { .. }))) {
        return Err(format!("AddCopy in a card's play effects {e:?} (exhausted only)"));
    }
    let plays_per_turn = match v.get("plays_per_turn") {
        None => 0,
        Some(n) => match n.int() {
            Some(n @ 1..=99) => n as u8,
            _ => return Err(format!("plays_per_turn {n:?}: 1 to 99")),
        },
    };
    let mut tags = 0;
    for t in v.get("tags").map(json::Value::items).unwrap_or(&[]) {
        tags |= tag(t.str().ok_or("a tag must be a string")?)?.bit();
    }
    // X cost and Unplayable are negative costs; older files say them with flags.
    let mut cost = int(v.get("cost"), "card cost")?;
    match (flag("x_cost"), flag("unplayable")) {
        (true, true) => return Err("x_cost and unplayable both (a card can't be both)".into()),
        (true, false) => cost = X_COST as i64,
        (false, true) => cost = UNPLAYABLE as i64,
        (false, false) => {}
    }
    if cost < UNPLAYABLE as i64 || cost > i8::MAX as i64 {
        return Err(format!("cost {cost}: an energy cost, -1 (X) or -2 (unplayable)"));
    }
    let ty = card_type(v.get("type").and_then(json::Value::str))?;
    if cost == UNPLAYABLE as i64 && (rows.iter().any(|(_, e, _)| !e.is_empty()) || playable_if.is_some()) {
        return Err("an unplayable card with on-play effects or a play condition (they never apply)".into());
    }
    if ty == CardType::Power && flag("exhaust") {
        return Err("a Power with exhaust (a played Power never goes to a pile)".into());
    }
    (CardSpec {
        cost: cost as i8,
        ty,
        exhaust: flag("exhaust"),
        ethereal: flag("ethereal"),
        retain: flag("retain"),
        innate: flag("innate"),
        playable_if,
        cost_less_per_hp_loss: flag("cost_less_per_hp_loss"),
        tags,
        rows,
        turn_end,
        exhausted,
        other_played,
        plays_per_turn,
        upgrade,
        max_level,
        no_limit: matches!(v.get("max_level"), Some(json::Value::Null)),
        successor: match v.get("successor") {
            None => None,
            Some(s) => Some(s.str().ok_or("successor: expected an entry id")?.to_string()),
        },
    })
    .checked()
}

// ---- official content (content/*.json, runtime registry stage 4) ----

/// The official content files, compiled in.
pub const OFFICIAL_FILES: [&str; 4] = [
    include_str!("../../content/cards.json"),
    include_str!("../../content/powers.json"),
    include_str!("../../content/monsters.json"),
    include_str!("../../content/encounters.json"),
];

/// The official relics file, compiled in (docs/specs/relics.md).
pub const OFFICIAL_RELICS: &str = include_str!("../../content/relics.json");

/// The official relics in file order, parsed on first use (a bad file is a
/// build bug: it panics naming the entry).
pub fn official_relics() -> &'static [(String, RelicSpec)] {
    static R: OnceLock<Vec<(String, RelicSpec)>> = OnceLock::new();
    R.get_or_init(|| parse_official_relics(OFFICIAL_RELICS).unwrap_or_else(|e| panic!("content/relics.json: {e}")))
}

/// A relic by name: official by its game name (`"Burning Blood"`), a
/// loaded pack relic as `gen:<id>`.
pub fn relic(name: &str) -> Option<RelicSpec> {
    match name.strip_prefix("gen:") {
        Some(id) => table().lock().unwrap().relics.get(id).cloned(),
        None => official_relics().iter().find(|(i, _)| i == name).map(|(_, s)| s.clone()),
    }
}

/// Relics by name (`relic`), in order, each with its name; an unknown name
/// is an error naming it.
pub fn relics_named(names: &[&str]) -> Result<Vec<(String, RelicSpec)>, String> {
    names.iter().map(|&n| relic(n).map(|r| (n.to_string(), r)).ok_or_else(|| format!("unknown relic {n:?}"))).collect()
}

/// `b` with these relics' pack start powers bound after `b`'s (as
/// `bind_monsters` binds a pack monster's): a power already bound keeps
/// its slot. More than `POWER_SLOTS` pack powers in all, or more than
/// `RELIC_CAP` relics, is an error naming the relic. The pool cards a
/// hook's `Discover` can offer, or its (or its start powers' hooks')
/// `MakeRandom` can make, are bound as a potion's (`bind_discovered`); a
/// `"Class"` pool is `character`'s (`fight_pool`).
pub fn bind_relics<'a>(
    b: &Binding,
    relics: impl IntoIterator<Item = &'a (String, RelicSpec)>,
    character: crate::character::Character,
) -> Result<Binding, String> {
    let mut s = b.slot_set().clone();
    let mut discovers = Vec::new();
    for (i, (name, r)) in relics.into_iter().enumerate() {
        if i >= crate::relics::RELIC_CAP {
            return Err(format!("relic {name:?}: the player would hold more than {} relics (RELIC_CAP)", crate::relics::RELIC_CAP));
        }
        for &(pi, _) in &r.gen_powers {
            add_power(&mut s, pi).map_err(|e| format!("relic {name:?}: {e}"))?;
        }
        // The pack powers its hooks apply (and theirs).
        for e in r.hooks.iter().flat_map(|h| h.effects) {
            if let Effect::ApplyPack { power, .. } = *e {
                add_power(&mut s, power).map_err(|e| format!("relic {name:?}: {e}"))?;
            }
        }
        discovers.extend(r.hooks.iter().flat_map(|h| h.effects).filter_map(|e| match *e {
            Effect::Discover { .. } => Some(*e),
            Effect::MakeRandom { pool, ty, n, pile, zero_cost, free, match_level } => {
                fight_pool(pool, character).map(|pool| Effect::MakeRandom { pool, ty, n, pile, zero_cost, free, match_level })
            }
            _ => None,
        }));
        let start_powers: Vec<u16> = r.gen_powers.iter().map(|&(pi, _)| pi).collect();
        discovers.extend(power_pool_effects(&start_powers));
    }
    // The pool cards a hook's `Discover` can offer (Toolbox).
    let b = if s == *b.slot_set() { *b } else { Binding::of(&s)? };
    bind_discovered(&b, discovers)
}

/// The loaded pack relics as `gen:<id>`, sorted.
pub fn pack_relic_names() -> Vec<String> {
    let mut v: Vec<String> = table().lock().unwrap().relics.keys().map(|k| format!("gen:{k}")).collect();
    v.sort();
    v
}

/// The official potions file, compiled in (docs/specs/potions.md).
pub const OFFICIAL_POTIONS: &str = include_str!("../../content/potions.json");

/// The official potions in file order, parsed on first use (a bad file is
/// a build error the tests name).
pub fn official_potions() -> &'static [(String, PotionSpec)] {
    static P: OnceLock<Vec<(String, PotionSpec)>> = OnceLock::new();
    P.get_or_init(|| parse_official_potions(OFFICIAL_POTIONS).unwrap_or_else(|e| panic!("content/potions.json: {e}")))
}

/// A potion by name: official by its game name (`"Fire Potion"`), a loaded
/// pack potion as `gen:<id>`.
pub fn potion(name: &str) -> Option<PotionSpec> {
    match name.strip_prefix("gen:") {
        Some(id) => table().lock().unwrap().potions.get(id).cloned(),
        None => official_potions().iter().find(|(i, _)| i == name).map(|(_, s)| s.clone()),
    }
}

/// Potions by name (`potion`), in the given order, each with its name; an
/// unknown name, or more than `POTION_CAP`, is an error naming it.
pub fn potions_named(names: &[&str]) -> Result<Vec<(String, PotionSpec)>, String> {
    if let Some(n) = names.get(crate::potions::POTION_CAP) {
        return Err(format!("potion {n:?}: the player would hold more than {} potions (POTION_CAP)", crate::potions::POTION_CAP));
    }
    names.iter().map(|&n| potion(n).map(|p| (n.to_string(), p)).ok_or_else(|| format!("unknown potion {n:?}"))).collect()
}

/// `b` with the pack powers these potions apply (and theirs) bound after
/// `b`'s: a power already bound keeps its slot. A potion with
/// `ObtainRandomPotions` brings every potion of its pool, bound alike, so
/// one it makes works (docs/specs/act1-singles.md section 5). More than
/// `POWER_SLOTS` pack powers in all is an error naming the potion.
pub fn bind_potions<'a>(b: &Binding, potions: impl IntoIterator<Item = &'a (String, PotionSpec)>) -> Result<Binding, String> {
    let mut all: Vec<(String, PotionSpec)> = potions.into_iter().cloned().collect();
    let mut i = 0;
    while i < all.len() {
        let pools: Vec<u8> = all[i].1.effects().filter_map(|e| if let Effect::ObtainRandomPotions { pool } = *e { Some(pool) } else { None }).collect();
        for pool in pools {
            for id in crate::potions::potion_pool(pool).potions() {
                if !all.iter().any(|(n, _)| n == id.name()) {
                    let spec = potion(id.name()).ok_or_else(|| format!("potion {:?}: its pool's {:?} is not loaded", all[i].0, id.name()))?;
                    all.push((id.name().to_string(), spec));
                }
            }
        }
        i += 1;
    }
    let mut s = b.slot_set().clone();
    let mut discovers = Vec::new();
    for (name, p) in &all {
        for e in p.effects() {
            if let Effect::ApplyPack { power, .. } = *e {
                add_power(&mut s, power).map_err(|e| format!("potion {name:?}: {e}"))?;
            }
        }
        discovers.extend(p.effects().filter(|e| matches!(e, Effect::Discover { .. })).copied());
    }
    let b = if s == *b.slot_set() { *b } else { Binding::of(&s)? };
    bind_discovered(&b, discovers)
}

/// The loaded pack potions as `gen:<id>`, sorted.
pub fn pack_potion_names() -> Vec<String> {
    let mut v: Vec<String> = table().lock().unwrap().potions.keys().map(|k| format!("gen:{k}")).collect();
    v.sort();
    v
}

/// An official power's definition as the files give it.
#[derive(Clone, Debug, PartialEq)]
pub struct OfficialPower {
    pub hooks: &'static [Hook],
    pub statics: &'static [Static],
    pub replacements: &'static [Replacement],
    pub rules: PowerRules,
}

/// Every official definition, loaded from the files by the pack parser:
/// cards in `CardId` order, powers in `Power::ALL` order, monsters by kind
/// (`None` built in at 0), encounters by handle.
pub struct Official {
    pub cards: Vec<CardDef>,
    pub powers: Vec<OfficialPower>,
    pub monsters: Vec<MonsterDef>,
    pub encounters: Vec<EncounterDef>,
    /// Official powers with a card rule (`forbids`, `sets_cost`,
    /// `exhausts_played`), so the hot checks scan only these.
    pub rule_powers: Vec<Power>,
    /// Official powers with a `CardDrawn` hook.
    pub draw_hook_powers: Vec<Power>,
    /// Official powers with an `attack_shape`, and its split.
    pub shape_powers: Vec<(Power, u8)>,
}

/// The official definitions, parsed from the compiled-in files on first use.
/// A bad file is a build bug: it panics naming the entry.
pub fn official() -> &'static Official {
    static O: OnceLock<Official> = OnceLock::new();
    O.get_or_init(|| parse_official(OFFICIAL_FILES).unwrap_or_else(|e| panic!("content files: {e}")))
}

/// The official card names in `CardId` order, read from the cards file's
/// ids alone, so name lookups during the load don't recurse into it.
pub fn official_card_names() -> &'static [String] {
    static N: OnceLock<Vec<String>> = OnceLock::new();
    N.get_or_init(|| {
        let v = json::parse(OFFICIAL_FILES[0]).unwrap_or_else(|e| panic!("content/cards.json: {e}"));
        let layout = official_layout(v.get("cards").map(json::Value::items).unwrap_or(&[])).unwrap_or_else(|e| panic!("content/cards.json: {e}"));
        layout.into_iter().flat_map(|g| g.names).collect()
    })
}

/// One card kind's place in the official cards file: its entry, the entry
/// of its `+` id when the file has one (a unique upgrade, or an older
/// file's second entry), and the pair's two names.
struct OfficialPair {
    entry: usize,
    plus: Option<usize>,
    names: [String; 2],
}

/// The official cards file's entries as id pairs, in order: an entry `X`
/// followed by `X+` (or by `X` again, an older file's status card) is a
/// pair of entries; any other entry is both ids, `X` and `X+` when it has
/// an upgrade block, else `X` twice.
fn official_layout(items: &[json::Value]) -> Result<Vec<OfficialPair>, String> {
    let id = |i: usize| items[i].get("id").and_then(json::Value::str).ok_or_else(|| format!("cards entry {i} without an id"));
    let mut out = Vec::new();
    let mut i = 0;
    while i < items.len() {
        let x = id(i)?.to_string();
        let next = if i + 1 < items.len() { Some(id(i + 1)?) } else { None };
        // A successor is the next entry; its card is named `X+` like any
        // level 1.
        if let Some(s) = items[i].get("successor") {
            if s.str() != next {
                return Err(format!("card {x:?}: its successor {s:?} must be the next entry"));
            }
            out.push(OfficialPair { entry: i, plus: Some(i + 1), names: [x.clone(), format!("{x}+")] });
            i += 2;
        } else if next == Some(&format!("{x}+")) || next == Some(&x) {
            out.push(OfficialPair { entry: i, plus: Some(i + 1), names: [x, next.unwrap().to_string()] });
            i += 2;
        } else {
            let second = if items[i].get("upgrade").is_some() { format!("{x}+") } else { x.clone() };
            out.push(OfficialPair { entry: i, plus: None, names: [x, second] });
            i += 1;
        }
    }
    Ok(out)
}

/// The ids of a file's entries, in order (no other parsing).
fn entry_ids(text: &str, key: &str) -> Result<Vec<String>, String> {
    let v = json::parse(text)?;
    v.get(key)
        .map(json::Value::items)
        .unwrap_or(&[])
        .iter()
        .enumerate()
        .map(|(i, e)| e.get("id").and_then(json::Value::str).map(str::to_string).ok_or_else(|| format!("{key} entry {i} without an id")))
        .collect()
}

/// An official name as its handle's variant name: letters and digits only,
/// lower case.
fn handle_name(id: &str) -> String {
    id.chars().filter(|c| c.is_ascii_alphanumeric()).map(|c| c.to_ascii_lowercase()).collect()
}

/// Parses and checks the four official files' texts (cards, powers,
/// monsters, encounters): entry counts and order against the handles,
/// unique ids, and every check a pack
/// gets.
pub fn parse_official(files: [&str; 4]) -> Result<Official, String> {
    let [cards_text, powers_text, monsters_text, encounters_text] = files;
    // Powers.
    let v = json::parse(powers_text)?;
    let version = file_version(&v).map_err(|e| format!("powers: {e}"))?;
    let items = v.get("powers").map(json::Value::items).unwrap_or(&[]);
    if items.len() != NUM_OFFICIAL_POWERS {
        return Err(format!("powers: {} entries, {NUM_OFFICIAL_POWERS} expected", items.len()));
    }
    let mut powers = Vec::new();
    for (p, e) in Power::ALL.into_iter().zip(items) {
        let id = e.get("id").and_then(json::Value::str).unwrap_or("");
        if id != format!("{p:?}") {
            return Err(format!("powers: entry {id:?} where {p:?} belongs"));
        }
        let s = parse_power(e, &|_| None, version).map_err(|err| format!("power {id:?}: {err}"))?;
        powers.push(OfficialPower { hooks: leak(s.hooks), statics: leak(s.statics), replacements: leak(s.replacements), rules: s.rules });
    }
    let rule_powers = Power::ALL.into_iter().filter(|&p| powers[p as usize].rules.has_card_rule()).collect();
    let draw_hook_powers =
        Power::ALL.into_iter().filter(|&p| powers[p as usize].hooks.iter().any(|h| h.trigger == Trigger::CardDrawn)).collect();
    let shape_powers = Power::ALL.into_iter().filter_map(|p| powers[p as usize].rules.attack_shape.map(|n| (p, n))).collect();
    // Cards: names first (a card can add another), then definitions.
    let v = json::parse(cards_text)?;
    let cards_version = file_version(&v).map_err(|e| format!("cards: {e}"))?;
    let items = v.get("cards").map(json::Value::items).unwrap_or(&[]);
    let layout = official_layout(items)?;
    let ids: Vec<String> = layout.iter().flat_map(|g| g.names.clone()).collect();
    for (i, id) in ids.iter().enumerate() {
        let Some(&kind) = CardKind::ALL.get(i / 2) else { break };
        // An upgrade is `<base>+`; a status card's upgrade slot repeats its name.
        let base = if i % 2 == 1 && *id != ids[i - 1] {
            id.strip_suffix('+').filter(|b| *b == ids[i - 1]).ok_or_else(|| format!("cards: entry {id:?} where {kind:?}'s upgrade belongs"))?
        } else {
            id
        };
        if handle_name(base) != handle_name(&format!("{kind:?}")) {
            return Err(format!("cards: entry {id:?} where {kind:?} belongs"));
        }
        if ids[..i].contains(id) && !(i % 2 == 1 && *id == ids[i - 1]) {
            return Err(format!("cards: {id:?} twice"));
        }
    }
    if ids.len() != NUM_OFFICIAL_CARDS {
        return Err(format!("cards: {} ids, {NUM_OFFICIAL_CARDS} expected", ids.len()));
    }
    let mut cards = Vec::new();
    for g in &layout {
        let [id, plus_id] = &g.names;
        let parsed = |j: usize, id: &str| -> Result<(CardSpec, CardClass), String> {
            let err = |x: String| format!("card {id:?}: {x}");
            let e = &items[j];
            let s = parse_card_as(e, true, cards_version).map_err(err)?;
            if let Some(g) = s.gens().next() {
                return Err(err(format!("applies unknown power {g:?}")));
            }
            let class = match e.get("class").and_then(json::Value::str) {
                Some("Ironclad") => CardClass::Ironclad,
                Some("Silent") => CardClass::Silent,
                Some("Colorless") => CardClass::Colorless,
                x => return Err(err(format!("bad class {x:?}"))),
            };
            Ok((s, class))
        };
        let (s, class) = parsed(g.entry, id)?;
        let plus = g.plus.map(|j| parsed(j, plus_id)).transpose()?;
        // An older file's status card names its second entry as the first.
        let (up, up_class, max_level) = match &plus {
            Some((p, c)) if plus_id == id => (p.clone(), *c, 0),
            Some((p, c)) => (levels(id, &s, Some(p))?.0, *c, 1),
            None => {
                let (p, m) = levels(id, &s, None)?;
                (p, class, m)
            }
        };
        let upgrade: &'static Upgrade = Box::leak(Box::new(s.upgrade.clone().unwrap_or_default()));
        for (level, (name, s, class)) in [(id, s, class), (plus_id, up, up_class)].into_iter().enumerate() {
            let mut rows = s.rows.into_iter();
            let (_, on_play, _) = rows.next().expect("the on-play row");
            let rows: Vec<Row> = rows.map(|(condition, effects, _)| Row { condition, effects: leak(effects) }).collect();
            cards.push(CardDef {
                name: Box::leak(name.clone().into_boxed_str()),
                class,
                cost_code: s.cost,
                ty: s.ty,
                exhaust: s.exhaust,
                ethereal: s.ethereal,
                playable_if: s.playable_if,
                innate: s.innate,
                tags: s.tags,
                retain: s.retain,
                cost_less_per_hp_loss: s.cost_less_per_hp_loss,
                effects: leak(on_play),
                rows: leak(rows),
                turn_end: leak(s.turn_end),
                exhausted: leak(s.exhausted),
                other_played: leak(s.other_played),
                plays_per_turn: s.plays_per_turn,
                level: level as u8,
                max_level,
                upgrade,
            });
        }
    }
    // Monsters: kinds 1-18 in order; split children are earlier kinds.
    let ids = entry_ids(monsters_text, "monsters")?;
    if ids.len() != NUM_OFFICIAL_MONSTERS - 1 {
        return Err(format!("monsters: {} entries, {} expected", ids.len(), NUM_OFFICIAL_MONSTERS - 1));
    }
    let v = json::parse(monsters_text)?;
    let mut monsters = vec![MonsterDef {
        name: "None",
        hp_min: 0,
        hp_max: 0,
        moves: &[],
        ai: pattern_ai,
        pattern: leak(vec![PatternRow { when: &[], then: PatPick::Move(NO_MOVE) }]),
        start_block: 0,
        start_powers: &[],
        gen_powers: &[],
        setup: no_setup,
        split_move: NO_MOVE,
        split_into: [MonsterKind::None; 2],
        rolled_attack: None,
        rolled_powers: &[],
        levels: &[],
        ascension_rows: "",
    }];
    for (i, (id, e)) in ids.iter().zip(v.get("monsters").map(json::Value::items).unwrap_or(&[])).enumerate() {
        let kind = MonsterKind(i as u8 + 1);
        let err = |x: String| format!("monster {id:?}: {x}");
        if handle_name(id) != handle_name(&format!("{kind:?}")) {
            return Err(format!("monsters: entry {id:?} where {kind:?} belongs"));
        }
        let code = e.get("code").and_then(json::Value::str);
        if code != crate::monsters::code_name(kind) {
            return Err(err(format!("code {code:?}, the engine has {:?}", crate::monsters::code_name(kind))));
        }
        let resolve = |name: &str| ids[..i].iter().position(|x| x == name).map(|j| MonsterKind(j as u8 + 1));
        let s = parse_monster_as(e, &resolve, &|_| None, true).map_err(err)?;
        monsters.push(def_of_spec(&s, Box::leak(id.clone().into_boxed_str()), crate::monsters::setup_for(code)));
    }
    // Encounters: handles 0-16 in order, monsters by their game names.
    let v = json::parse(encounters_text)?;
    let items = v.get("encounters").map(json::Value::items).unwrap_or(&[]);
    if items.len() != NUM_OFFICIAL_ENCOUNTERS {
        return Err(format!("encounters: {} entries, {NUM_OFFICIAL_ENCOUNTERS} expected", items.len()));
    }
    let resolve = |name: &str| ids.iter().position(|x| x == name).map(|j| MonsterKind(j as u8 + 1));
    fn split_slots(defs: &[MonsterDef], k: MonsterKind) -> usize {
        let d = &defs[k.0 as usize];
        if d.split_move == NO_MOVE {
            1
        } else {
            split_slots(defs, d.split_into[0]) + split_slots(defs, d.split_into[1])
        }
    }
    let mut encounters = Vec::new();
    for (i, e) in items.iter().enumerate() {
        let handle = Encounter(i as u8);
        let (id, group, slots) = parse_encounter(e, &resolve, &|k| split_slots(&monsters, k))?;
        if handle_name(&id) != handle_name(&format!("{handle:?}")) {
            return Err(format!("encounters: entry {id:?} where {handle:?} belongs"));
        }
        encounters.push(EncounterDef { name: Box::leak(id.into_boxed_str()), group, slots });
    }
    Ok(Official { cards, powers, monsters, encounters, rule_powers, draw_hook_powers, shape_powers })
}

/// A slot list of an encounter entry.
fn encounter_slots(
    vs: &json::Value,
    monster: &dyn Fn(&json::Value) -> Result<MonsterKind, String>,
) -> Result<Vec<EncounterSlot>, String> {
    let json::Value::Arr(items) = vs else { return Err(format!("a list of slots expected, got {vs:?}")) };
    items.iter().map(|v| encounter_slot(v, monster)).collect()
}

/// One slot: a monster name, `{"one_of": [[...], ...]}` or `{"draw": k, "from": [...]}`.
fn encounter_slot(v: &json::Value, monster: &dyn Fn(&json::Value) -> Result<MonsterKind, String>) -> Result<EncounterSlot, String> {
    let json::Value::Obj(kv) = v else { return Ok(EncounterSlot::Monster(monster(v)?)) };
    let mut keys: Vec<&str> = kv.iter().map(|(k, _)| k.as_str()).collect();
    keys.sort_unstable();
    match keys.as_slice() {
        ["one_of"] => {
            let opts = v.get("one_of").map(json::Value::items).unwrap_or(&[]);
            if opts.is_empty() {
                return Err("one_of without options".into());
            }
            Ok(EncounterSlot::OneOf(opts.iter().map(|o| encounter_slots(o, monster)).collect::<Result<_, _>>()?))
        }
        ["draw", "from"] => {
            let from: Vec<MonsterKind> = v.get("from").map(json::Value::items).unwrap_or(&[]).iter().map(monster).collect::<Result<_, _>>()?;
            let k = v.get("draw").and_then(json::Value::int).ok_or("draw: a count expected")?;
            if k < 1 || k as usize > from.len() {
                return Err(format!("draw {k} from {} monsters", from.len()));
            }
            Ok(EncounterSlot::Draw { k: k as u8, from })
        }
        _ => Err(format!("a slot is a monster name, one_of or draw and from, got keys {keys:?}")),
    }
}

/// (fewest monsters, most monster slots) any roll of these slots gives,
/// `slots` per kind with its splits.
fn encounter_bounds(ss: &[EncounterSlot], slots: &dyn Fn(MonsterKind) -> usize) -> (usize, usize) {
    let mut total = (0, 0);
    for s in ss {
        let (lo, hi) = match s {
            EncounterSlot::Monster(k) => (1, slots(*k)),
            EncounterSlot::OneOf(opts) => {
                let b: Vec<(usize, usize)> = opts.iter().map(|o| encounter_bounds(o, slots)).collect();
                (b.iter().map(|x| x.0).min().unwrap_or(0), b.iter().map(|x| x.1).max().unwrap_or(0))
            }
            EncounterSlot::Draw { k, from } => {
                let mut n: Vec<usize> = from.iter().map(|&m| slots(m)).collect();
                n.sort_unstable_by(|a, b| b.cmp(a));
                (*k as usize, n[..*k as usize].iter().sum())
            }
        };
        total = (total.0 + lo, total.1 + hi);
    }
    total
}

/// Every element the content format names, by family, as the parsers above
/// accept them: the keys of `content/wording.json`, which words each one
/// (docs/specs/element-wording.md). A parameter that picks a trigger's form
/// is a second part (`CardPlayed.Owner`). A new element in a parser goes
/// here and in the wording file; `engine/tests/wording.rs` names any miss.
pub fn element_names() -> Vec<(&'static str, Vec<&'static str>)> {
    vec![
        ("effect", vec![
            "Damage", "PlainDamage", "ScaledDamage", "RandomDamage", "RandomApply", "RolledAttack", "Block", "BlockAlly",
            "BlockOf", "ScaledBlock", "ExhaustHand", "ExhaustRandom", "Draw", "RandomizeCost", "GainEnergy", "LoseHp", "Heal", "HealOf", "CapHp", "WinHeal", "GainMaxHp", "Apply", "ApplyOf",
            "AddCard", "Split", "Escape", "RemoveSelf", "ReduceSelf", "Pick", "ReplayCard", "GrowDamage",
            "UpgradeHand", "SetCounter", "AddCounter", "DrawPicked", "PlayTop", "Discover", "ObtainRandomPotions",
            "UpgradeAll", "ShuffleDiscardIntoDraw", "ZeroCostRandom", "ZeroCostRandomTurn", "UpgradeRandom", "MakeRandom", "RemoveDebuffs", "CostAtMost",
            "LoseHpOf", "ApplyAsMonster", "AddCopy",
        ]),
        ("target", vec!["Opponent", "AllOpponents", "Me", "Attacker", "RandomOpponent"]),
        ("quantity", vec!["OwnBlock", "OwnStrength", "EnergySpent", "CardsTagged", "HandCards", "OwnMaxHp", "DrawPileSize", "CardsOfType", "HpDealt"]),
        ("pick", vec!["DiscardFromHand", "ReturnFromDiscard", "DiscardToTop", "ExhaustFromHand", "ReturnFromExhaust", "UpgradeFromHand", "HandToTop", "CopyInHand"]),
        ("pick_rule", vec!["free_this_turn", "of"]),
        ("pile", vec!["Draw", "Discard", "Hand"]),
        ("cost_roll", vec!["Hand", "Drawn"]),
        ("trigger", vec![
            "OwnerTurnStart", "OwnerTurnStartPostDraw", "OwnerTurnEnd", "CardPlayed.Owner", "CardPlayed.Opponent", "OwnerLostHp.Attack",
            "OwnerLostHp.Card", "OwnerLostHp.Any", "OwnerDied", "RoundEnd", "OwnerAttacked", "OwnerPlaysCard",
            "OwnerAttackHit", "CardExhausted", "CardDrawn", "OwnerBloodied", "OwnerUnbloodied", "CombatStartPreDraw",
            "CombatStart", "OpponentDied", "CombatWon", "OwnerApplied", "Shuffled", "OwnerUsedPotion", "OpponentBlockBroken",
            "OwnerHandEmpty", "OwnerGainedBlock",
        ]),
        ("condition", vec![
            "Always", "CardType", "TargetIntendsAttack", "TargetHas", "CardsPlayedThisTurnBelow", "HandAll", "OwnerHpAtMostHalf", "CounterIs",
            "OwnerBlockIs", "Applying", "HandNone", "TargetLacks", "ApplyingDebuff", "TargetDied", "CounterAtMost", "NotFirstTurn",
        ]),
        ("static_condition", vec!["Always", "CardInPlayTagged", "OwnerHpAtMostHalf", "Holds"]),
        ("modifies", vec!["DamageDealt", "DamageTaken", "BlockGained"]),
        ("stage", vec!["Add", "Multiply"]),
        ("replacement_event", vec![
            "DamageTaken", "HpLoss", "DebuffApplied", "DealtAfterBlock", "TakenAfterBlock", "AttackedAfterBlock", "HpLossLast", "Draw",
        ]),
        ("replacement_action", vec!["Cancel", "Cap", "Add", "Multiply", "AtLeast"]),
        ("replacement_rule", vec!["upTo"]),
        ("pattern_condition", vec!["FirstTurn", "LastMove", "LastTwo", "Window", "Slot", "RollBelow", "Allies"]),
        ("pattern_pick", vec!["Move", "Chance"]),
        ("monster_field", vec!["rolled_attack", "rolled_powers", "ascension"]),
        ("encounter_slot", vec!["one_of", "draw"]),
        ("relic_rarity", vec!["starter", "common", "uncommon", "rare", "boss", "shop", "event"]),
        ("fight_kind", vec!["hallway", "elite", "boss"]),
        ("card_rule", CARD_RULE_KEYS.to_vec()),
        ("power_rule", POWER_RULE_KEYS.to_vec()),
        ("power_field", POWER_FIELD_KEYS.to_vec()),
        ("hook_field", HOOK_FIELD_KEYS.to_vec()),
        ("relic_rule", vec!["start_power", "fights", "win_heal", "counter", "potion_potency", "potion_slots", "draw_per_turn", "x_bonus", "keeps_energy",
            "plays_per_turn", "keeps_hand", "heal_scale", "exhaust_save", "sees_draw_order", "hides_intents", "no_potions", "bottles"]),
        ("potion_rarity", vec!["common", "uncommon", "rare"]),
        ("potion_rule", vec!["potency", "trigger", "fights"]),
    ]
}

/// One encounter entry: `{"id", "group", "monsters": [<slot>, ...]}`.
/// Checks the keys, the group, every monster name (`resolve`), that every
/// roll has a monster and that no roll needs more than `MAX_MONSTERS`
/// slots (`slots` per kind, splits included).
fn parse_encounter(
    e: &json::Value,
    resolve: &dyn Fn(&str) -> Option<MonsterKind>,
    slots: &dyn Fn(MonsterKind) -> usize,
) -> Result<(String, EncounterGroup, Vec<EncounterSlot>), String> {
    let id = e.get("id").and_then(json::Value::str).ok_or("encounter without an id")?.to_string();
    let err = |x: String| format!("encounter {id:?}: {x}");
    if let json::Value::Obj(kv) = e {
        if let Some((k, _)) = kv.iter().find(|(k, _)| !["id", "group", "monsters"].contains(&k.as_str())) {
            return Err(err(format!("unknown key {k:?}")));
        }
    }
    let group = match e.get("group").and_then(json::Value::str) {
        Some("hallway") => EncounterGroup::Hallway,
        Some("elite") => EncounterGroup::Elite,
        Some("boss") => EncounterGroup::Boss,
        g => return Err(err(format!("bad group {g:?}"))),
    };
    let monster = |v: &json::Value| -> Result<MonsterKind, String> {
        let n = v.str().ok_or_else(|| format!("a monster name expected, got {v:?}"))?;
        resolve(n).ok_or_else(|| format!("unknown monster {n:?}"))
    };
    let list = e.get("monsters").ok_or_else(|| err("no monsters".into()))?;
    let ss = encounter_slots(list, &monster).map_err(err)?;
    let (lo, hi) = encounter_bounds(&ss, slots);
    if lo == 0 {
        return Err(err("a roll with no monster".into()));
    }
    if hi > MAX_MONSTERS {
        return Err(err(format!("a roll can need {hi} monster slots, more than {MAX_MONSTERS}")));
    }
    Ok((id, group, ss))
}

// ---- writing pack entries (the round trip of official content) ----

fn q(s: &str) -> String {
    format!("{s:?}")
}

fn target_json(t: Target) -> String {
    q(&format!("{t:?}"))
}

fn except_json(t: Option<CardType>) -> String {
    match t {
        None => "{}".into(),
        Some(t) => format!("{{\"except\": {}}}", q(&format!("{t:?}"))),
    }
}

fn amount_json(a: Amount) -> String {
    let of = match a.of {
        None => return a.base.to_string(),
        Some(Quantity::CardsTagged(t)) => format!("{{\"CardsTagged\": {}}}", q(&format!("{t:?}"))),
        Some(Quantity::HandCards { except }) => format!("{{\"HandCards\": {}}}", except_json(except)),
        Some(Quantity::CardsOfType(t)) => format!("{{\"CardsOfType\": {}}}", q(&format!("{t:?}"))),
        Some(o) => q(&format!("{o:?}")),
    };
    let k = if a.per == 1 { a.k.to_string() } else { format!("\"{}/{}\"", a.k, a.per) };
    format!("{{\"base\": {}, \"k\": {k}, \"of\": {of}}}", a.base)
}

/// One effect as a pack value; `None` for monster-only effects.
pub fn effect_json(e: &Effect) -> Option<String> {
    Some(match *e {
        Effect::Damage { amount, hits, target } => {
            format!("{{\"Damage\": {{\"amount\": {amount}, \"hits\": {hits}, \"target\": {}}}}}", target_json(target))
        }
        Effect::PlainDamage { amount, target } => format!("{{\"PlainDamage\": {{\"amount\": {amount}, \"target\": {}}}}}", target_json(target)),
        Effect::ScaledDamage { amount, hits, target } => format!(
            "{{\"ScaledDamage\": {{\"amount\": {}, \"hits\": {}, \"target\": {}}}}}",
            amount_json(amount),
            amount_json(hits),
            target_json(target)
        ),
        Effect::RandomDamage { amount, hits } => format!("{{\"RandomDamage\": {{\"amount\": {amount}, \"hits\": {hits}}}}}"),
        Effect::RandomApply { power, amount, hits } => {
            format!("{{\"RandomApply\": {{\"power\": {}, \"amount\": {amount}, \"hits\": {hits}}}}}", q(&format!("{power:?}")))
        }
        Effect::Block(n) => format!("{{\"Block\": {n}}}"),
        Effect::BlockOf(a) => format!("{{\"BlockOf\": {}}}", amount_json(a)),
        Effect::ApplyOf { power, amount, target } => format!(
            "{{\"ApplyOf\": {{\"power\": {}, \"amount\": {}, \"target\": {}}}}}",
            q(&format!("{power:?}")),
            amount_json(amount),
            target_json(target)
        ),
        Effect::ScaledBlock { amount, times } => format!("{{\"ScaledBlock\": {{\"amount\": {amount}, \"times\": {}}}}}", amount_json(times)),
        Effect::ExhaustHand { except } => format!("{{\"ExhaustHand\": {}}}", except_json(except)),
        Effect::ExhaustRandom => q("ExhaustRandom"),
        Effect::ZeroCostRandom => q("ZeroCostRandom"),
        Effect::ZeroCostRandomTurn => q("ZeroCostRandomTurn"),
        Effect::UpgradeRandom => q("UpgradeRandom"),
        Effect::CostAtMost { cost, combat } => format!("{{\"CostAtMost\": {{\"cost\": {cost}, \"combat\": {combat}}}}}"),
        Effect::Draw(n) => format!("{{\"Draw\": {n}}}"),
        Effect::RandomizeCost(w) => format!("{{\"RandomizeCost\": \"{w:?}\"}}"),
        Effect::GainEnergy(n) => format!("{{\"GainEnergy\": {n}}}"),
        Effect::LoseHp(n) => format!("{{\"LoseHp\": {n}}}"),
        Effect::LoseHpOf(a) => format!("{{\"LoseHpOf\": {}}}", amount_json(a)),
        Effect::AddCopy { n, pile } => format!("{{\"AddCopy\": {{\"n\": {n}, \"pile\": {}}}}}", q(&format!("{pile:?}"))),
        Effect::ApplyAsMonster { power, amount, target } => format!(
            "{{\"ApplyAsMonster\": {{\"power\": {}, \"amount\": {amount}, \"target\": {}}}}}",
            q(&format!("{power:?}")),
            target_json(target)
        ),
        Effect::Heal(n) => format!("{{\"Heal\": {n}}}"),
        Effect::GainMaxHp(n) => format!("{{\"GainMaxHp\": {n}}}"),
        Effect::HealOf(a) => format!("{{\"HealOf\": {}}}", amount_json(a)),
        Effect::CapHp { amount, num, den, target } => {
            format!("{{\"CapHp\": {{\"amount\": {amount}, \"num\": {num}, \"den\": {den}, \"target\": {}}}}}", target_json(target))
        }
        Effect::WinHeal(n) => format!("{{\"WinHeal\": {n}}}"),
        Effect::Apply { power, amount, target } => format!(
            "{{\"Apply\": {{\"power\": {}, \"amount\": {amount}, \"target\": {}}}}}",
            q(&format!("{power:?}")),
            target_json(target)
        ),
        Effect::AddCard { card, n, pile } => {
            format!("{{\"AddCard\": {{\"card\": {}, \"n\": {n}, \"pile\": {}}}}}", q(card.name()), q(&format!("{pile:?}")))
        }
        Effect::RemoveSelf => q("RemoveSelf"),
        Effect::ReduceSelf(n) => format!("{{\"ReduceSelf\": {n}}}"),
        Effect::Pick { kind, n, exact, free, of, copies } => {
            let free = if free { ", \"free_this_turn\": true" } else { "" };
            let of = if of == Types::ALL {
                String::new()
            } else {
                format!(", \"of\": [{}]", of.types().iter().map(|t| q(&format!("{t:?}"))).collect::<Vec<_>>().join(", "))
            };
            let copies = if copies != 0 { format!(", \"copies\": {copies}") } else { String::new() };
            format!("{{\"Pick\": {{\"kind\": {}, \"n\": {n}, \"exact\": {exact}{free}{of}{copies}}}}}", q(&format!("{kind:?}")))
        }
        Effect::ReplayCard => q("ReplayCard"),
        Effect::GrowDamage(n) => format!("{{\"GrowDamage\": {n}}}"),
        Effect::UpgradeHand => q("UpgradeHand"),
        Effect::UpgradeAll => q("UpgradeAll"),
        Effect::ShuffleDiscardIntoDraw => q("ShuffleDiscardIntoDraw"),
        Effect::RemoveDebuffs => q("RemoveDebuffs"),
        Effect::DrawPicked => q("DrawPicked"),
        Effect::PlayTop { n, exhaust } => format!("{{\"PlayTop\": {{\"n\": {n}, \"exhaust\": {exhaust}}}}}"),
        Effect::Discover { pool, ty, offer, copies, free, skip } => {
            let ty = ty.map_or(String::new(), |t| format!(", \"type\": {}", q(&format!("{t:?}"))));
            format!(
                "{{\"Discover\": {{\"pool\": {}{ty}, \"offer\": {offer}, \"copies\": {copies}, \"free\": {free}, \"skip\": {skip}}}}}",
                q(pool_def(pool)?.name)
            )
        }
        Effect::MakeRandom { pool, ty, n, pile, zero_cost, free, match_level } => {
            let ty = ty.map_or(String::new(), |t| format!(", \"type\": {}", q(&format!("{t:?}"))));
            format!(
                "{{\"MakeRandom\": {{\"pool\": {}{ty}, \"n\": {}, \"pile\": {}, \"zero_cost\": {zero_cost}, \"free\": {free}, \"match_level\": {match_level}}}}}",
                q(if pool == CLASS_POOL { "Class" } else { pool_def(pool)?.name }),
                amount_json(n),
                q(&format!("{pile:?}"))
            )
        }
        Effect::ObtainRandomPotions { pool } => {
            let except: Vec<String> = crate::potions::potion_pool(pool).except.iter().map(|e| q(e)).collect();
            format!("{{\"ObtainRandomPotions\": {{\"except\": [{}]}}}}", except.join(", "))
        }
        Effect::SetCounter(n) => format!("{{\"SetCounter\": {n}}}"),
        Effect::AddCounter(n) => format!("{{\"AddCounter\": {n}}}"),
        Effect::ApplyPack { power, amount, target } => {
            let g = POWERS[power as usize].get()?;
            format!("{{\"Apply\": {{\"power\": {}, \"amount\": {amount}, \"target\": {}}}}}", q(g.id), target_json(target))
        }
        Effect::RolledAttack | Effect::Split | Effect::Escape | Effect::BlockAlly(_) => return None,
    })
}

fn effects_json(es: &[Effect]) -> Option<String> {
    let v: Option<Vec<String>> = es.iter().map(effect_json).collect();
    Some(format!("[{}]", v?.join(", ")))
}

/// `effects_json`, with `match_level` on the AddCard effects an upgrade
/// lists for `section`.
fn section_json(es: &[Effect], section: Section, up: Option<&Upgrade>) -> Option<String> {
    let v: Option<Vec<String>> = es
        .iter()
        .enumerate()
        .map(|(i, e)| {
            let j = effect_json(e)?;
            Some(match (e, up.is_some_and(|u| u.match_level.contains(&(section, i)))) {
                (Effect::AddCard { .. }, true) => format!("{}, \"match_level\": true}}}}", j.strip_suffix("}}").expect("an AddCard object")),
                _ => j,
            })
        })
        .collect();
    Some(format!("[{}]", v?.join(", ")))
}

/// An upgrade block and its `max_level` (written when not 1) as entry
/// fields, each after a comma.
fn upgrade_json(u: &Upgrade, max_level: u8) -> String {
    let changes: Vec<String> = u
        .changes
        .iter()
        .map(|(p, c)| {
            let v = match c {
                Change::Set(b) => b.to_string(),
                Change::Add(e) => e.write(),
            };
            format!("{}: {v}", q(&p.write()))
        })
        .collect();
    let max = match max_level {
        1 => String::new(),
        LEVEL_CAP => ", \"max_level\": null".into(),
        m => format!(", \"max_level\": {m}"),
    };
    format!(", \"upgrade\": {{{}}}{max}", changes.join(", "))
}

/// Whether a card's upgrade is data: an upgrade block, or (from an older
/// file's two entries) one the two definitions differ by.
fn data_upgrade(d0: &CardDef, d1: &CardDef) -> Option<Upgrade> {
    if !d0.upgrade.changes.is_empty() || !d0.upgrade.match_level.is_empty() {
        return Some(d0.upgrade.clone());
    }
    let same_frame = d0.class == d1.class
        && d0.ty == d1.ty
        && d0.tags == d1.tags
        && d0.playable_if == d1.playable_if
        && d0.cost_less_per_hp_loss == d1.cost_less_per_hp_loss
        && d0.rows.len() == d1.rows.len()
        && d0.rows.iter().zip(d1.rows).all(|(a, b)| a.condition == b.condition)
        && d1.name.strip_suffix('+') == Some(d0.name);
    if !same_frame {
        return None;
    }
    Upgrade::between(&d0.parts(), &d1.parts())
}

fn condition_json(c: Condition) -> String {
    match c {
        Condition::Always => q("Always"),
        Condition::CardType(t) => format!("{{\"CardType\": {}}}", q(&format!("{t:?}"))),
        Condition::TargetIntendsAttack => q("TargetIntendsAttack"),
        Condition::TargetHas(p) => format!("{{\"TargetHas\": {}}}", q(&format!("{p:?}"))),
        Condition::CardsPlayedThisTurnBelow(n) => format!("{{\"CardsPlayedThisTurnBelow\": {n}}}"),
        Condition::HandAll(t) => format!("{{\"HandAll\": {}}}", q(&format!("{t:?}"))),
        Condition::OwnerHpAtMostHalf => q("OwnerHpAtMostHalf"),
        Condition::CounterIs(n) => format!("{{\"CounterIs\": {n}}}"),
        Condition::OwnerBlockIs(n) => format!("{{\"OwnerBlockIs\": {n}}}"),
        Condition::Applying(p) => format!("{{\"Applying\": {}}}", q(&format!("{p:?}"))),
        Condition::HandNone(t) => format!("{{\"HandNone\": {}}}", q(&format!("{t:?}"))),
        Condition::TargetLacks(p) => format!("{{\"TargetLacks\": {}}}", q(&format!("{p:?}"))),
        Condition::ApplyingDebuff => q("ApplyingDebuff"),
        Condition::TargetDied => q("TargetDied"),
        Condition::CounterAtMost(n) => format!("{{\"CounterAtMost\": {n}}}"),
        Condition::NotFirstTurn => q("NotFirstTurn"),
    }
}

/// A hook's condition, or its list of two.
fn hook_conditions_json(h: &Hook) -> String {
    match h.also {
        Condition::Always => condition_json(h.condition),
        b => format!("[{}, {}]", condition_json(h.condition), condition_json(b)),
    }
}

fn trigger_json(t: Trigger) -> String {
    match t {
        Trigger::CardPlayed { by } => format!("{{\"CardPlayed\": {{\"by\": {}}}}}", q(&format!("{by:?}"))),
        Trigger::OwnerLostHp { from } => format!("{{\"OwnerLostHp\": {{\"from\": {}}}}}", q(&format!("{from:?}"))),
        t => q(&format!("{t:?}")),
    }
}

/// A card definition as a pack card with id `id` (`None` if it holds a
/// monster-only effect); a level-0 definition with an upgrade block
/// carries it.
pub fn card_json(id: &str, d: &CardDef) -> Option<String> {
    let up = (d.level == 0 && (!d.upgrade.changes.is_empty() || !d.upgrade.match_level.is_empty())).then_some(d.upgrade);
    card_entry(id, d, "", up.map(|u| (u, d.max_level)))
}

/// A content file's card entry (`entry`, from a file of `version`;
/// `official`: of `content/cards.json`) at upgrade level `level`, as the
/// engine resolves its `upgrade` block for play: an entry without the block
/// named `X+` (level 1) or `X+<n>`, its other fields as file fields.
/// `None` when the entry has no upgrade block (none, or a `successor`,
/// which is an entry of its own) or `level` is 0 or past its max level.
pub fn card_level_json(entry: &str, level: u8, official: bool, version: u8) -> Result<Option<String>, String> {
    let v = json::parse(entry)?;
    let id = v.get("id").and_then(json::Value::str).ok_or("card without an id")?;
    let s = parse_card_as(&v, official, version).map_err(|e| format!("card {id:?}: {e}"))?;
    let Some(u) = &s.upgrade else { return Ok(None) };
    if level == 0 || level > s.max_level.unwrap_or(1) {
        return Ok(None);
    }
    let up = s.with_parts(u.apply(&s.parts(), 0, level).map_err(|e| format!("card {id:?}: {e}"))?);
    // A pack power's effect holds `GEN[0]`; its id is in `gen`.
    let effects = |es: &[Effect], gen: &[Option<String>]| -> Result<String, String> {
        let v: Result<Vec<String>, String> = es
            .iter()
            .zip(gen.iter().map(Some).chain(std::iter::repeat(None)))
            .map(|(e, g)| {
                let j = effect_json(e).ok_or_else(|| format!("card {id:?}: {e:?} has no file form"))?;
                Ok(match g.and_then(Option::as_ref) {
                    Some(g) => j.replacen(&q(&format!("{:?}", Power::GEN[0])), &q(g), 1),
                    None => j,
                })
            })
            .collect();
        Ok(format!("[{}]", v?.join(", ")))
    };
    let rows: Result<Vec<String>, String> = up.rows[1..]
        .iter()
        .map(|(c, es, g)| Ok(format!("{{\"condition\": {}, \"effects\": {}}}", condition_json(*c), effects(es, g)?)))
        .collect();
    let tags: Vec<String> = Tag::ALL.iter().filter(|t| up.tags & t.bit() != 0).map(|t| q(&format!("{t:?}"))).collect();
    let name = if level == 1 { format!("{id}+") } else { format!("{id}+{level}") };
    Ok(Some(format!(
        "{{\"id\": {}, \"cost\": {}, \"type\": {}, \"exhaust\": {}, \"ethereal\": {}, \"retain\": {}, \"innate\": {}{}, \"tags\": [{}], \"effects\": {}, \"rows\": [{}], \"turn_end\": {}, \"exhausted\": {}{}{}}}",
        q(&name),
        up.cost,
        q(&format!("{:?}", up.ty)),
        up.exhaust,
        up.ethereal,
        up.retain,
        up.innate,
        up.playable_if.map(|c| format!(", \"playable_if\": {}", condition_json(c))).unwrap_or_default(),
        tags.join(", "),
        effects(&up.rows[0].1, &up.rows[0].2)?,
        rows?.join(", "),
        effects(&up.turn_end, &[])?,
        effects(&up.exhausted, &[])?,
        if up.cost_less_per_hp_loss { ", \"cost_less_per_hp_loss\": true" } else { "" },
        held_fields_json(&up.other_played, up.plays_per_turn)?,
    )))
}

/// An official card kind as entries of `content/cards.json` (`card_json`
/// with its name as id and the official-only `class`): one entry when its
/// upgrade is data or it has none, else its two definitions.
pub fn official_card_json(kind: CardKind) -> Option<Vec<String>> {
    let (d0, d1) = (CardId::new(kind, false).def(), CardId::new(kind, true).def());
    let entry = |d: &CardDef, up: Option<(&Upgrade, u8)>| card_entry(d.name, d, &format!(", \"class\": {}", q(&format!("{:?}", d.class))), up);
    if d1.name == d0.name {
        return Some(vec![entry(d0, None)?]);
    }
    match data_upgrade(d0, d1) {
        Some(u) => Some(vec![entry(d0, Some((&u, d0.max_level.max(1))))?]),
        None => {
            let base = card_entry(d0.name, d0, &format!(", \"class\": {}, \"successor\": {}", q(&format!("{:?}", d0.class)), q(d1.name)), None)?;
            Some(vec![base, entry(d1, None)?])
        }
    }
}

fn card_entry(id: &str, d: &CardDef, extra: &str, up: Option<(&Upgrade, u8)>) -> Option<String> {
    let u = up.map(|(u, _)| u);
    let tags: Vec<String> = Tag::ALL.iter().filter(|&&t| d.has_tag(t)).map(|t| q(&format!("{t:?}"))).collect();
    let rows: Option<Vec<String>> = d
        .rows
        .iter()
        .enumerate()
        .map(|(r, row)| {
            Some(format!("{{\"condition\": {}, \"effects\": {}}}", condition_json(row.condition), section_json(row.effects, Section::Row(r + 1), u)?))
        })
        .collect();
    Some(format!(
        "{{\"id\": {}, \"cost\": {}, \"type\": {}{extra}, \"exhaust\": {}, \"ethereal\": {}, \"retain\": {}, \"innate\": {}{}, \"tags\": [{}], \"effects\": {}, \"rows\": [{}], \"turn_end\": {}{}{}{}{}}}",
        q(id),
        d.cost_code,
        q(&format!("{:?}", d.ty)),
        d.exhaust,
        d.ethereal,
        d.retain,
        d.innate,
        d.playable_if.map(|c| format!(", \"playable_if\": {}", condition_json(c))).unwrap_or_default(),
        tags.join(", "),
        section_json(d.effects, Section::Row(0), u)?,
        rows?.join(", "),
        section_json(d.turn_end, Section::TurnEnd, u)?,
        if d.exhausted.is_empty() { String::new() } else { format!(", \"exhausted\": {}", effects_json(d.exhausted)?) },
        if d.cost_less_per_hp_loss { ", \"cost_less_per_hp_loss\": true" } else { "" },
        held_fields_json(d.other_played, d.plays_per_turn).ok()?,
        up.map(|(u, m)| upgrade_json(u, m)).unwrap_or_default()
    ))
}

/// The held-card fields (docs/specs/blocked-relics.md step 6), each only
/// when set, so cards without them write as before.
fn held_fields_json(other_played: &[Effect], plays_per_turn: u8) -> Result<String, String> {
    let mut out = String::new();
    if !other_played.is_empty() {
        out += &format!(", \"other_played\": {}", effects_json(other_played).ok_or("other_played has no file form")?);
    }
    if plays_per_turn > 0 {
        out += &format!(", \"plays_per_turn\": {plays_per_turn}");
    }
    Ok(out)
}

/// An encounter as a file entry (`content/encounters.json`'s format):
/// monsters by their game names (pack monsters as `gen:<id>`).
pub fn encounter_json(id: &str, d: &EncounterDef) -> String {
    fn slots(ss: &[EncounterSlot]) -> String {
        let v: Vec<String> = ss
            .iter()
            .map(|s| match s {
                EncounterSlot::Monster(k) => q(k.def().name),
                EncounterSlot::OneOf(opts) => {
                    let o: Vec<String> = opts.iter().map(|o| format!("[{}]", slots(o))).collect();
                    format!("{{\"one_of\": [{}]}}", o.join(", "))
                }
                EncounterSlot::Draw { k, from } => {
                    let f: Vec<String> = from.iter().map(|m| q(m.def().name)).collect();
                    format!("{{\"draw\": {k}, \"from\": [{}]}}", f.join(", "))
                }
            })
            .collect();
        v.join(", ")
    }
    let group = match d.group {
        EncounterGroup::Hallway => "hallway",
        EncounterGroup::Elite => "elite",
        EncounterGroup::Boss => "boss",
    };
    format!("{{\"id\": {}, \"group\": {}, \"monsters\": [{}]}}", q(id), q(group), slots(&d.slots))
}

/// An official monster as a pack monster with id `id`; `None` for one whose
/// behaviour is partly code (`monsters::has_code`) and for the empty or a
/// pack kind.
pub fn monster_json(id: &str, k: MonsterKind) -> Option<String> {
    if !k.is_official() || k == MonsterKind::None || crate::monsters::has_code(k) {
        return None;
    }
    monster_entry(id, k, "")
}

/// An official monster (kinds 1-18) as an entry of `content/monsters.json`:
/// `monster_json` with the game's name as id, and for a code-backed one its
/// official-only `code` name (which also allows `RolledAttack`).
pub fn official_monster_json(k: MonsterKind) -> Option<String> {
    if !k.is_official() || k == MonsterKind::None {
        return None;
    }
    let code = match crate::monsters::code_name(k) {
        Some(c) => format!(", \"code\": {}", q(c)),
        None => String::new(),
    };
    monster_entry(k.def().name, k, &code)
}

fn monster_entry(id: &str, k: MonsterKind, code: &str) -> Option<String> {
    let d = k.def();
    let rolled = d.rolled_attack.is_some() || !code.is_empty();
    let mid = |m: MoveId| if m == NO_MOVE { "null".to_string() } else { m.to_string() };
    let moves: Option<Vec<String>> = d
        .moves
        .iter()
        .map(|m| {
            let es: Option<Vec<String>> = m
                .effects
                .iter()
                .map(|e| match e {
                    Effect::Split => Some(q("Split")),
                    Effect::Escape => Some(q("Escape")),
                    Effect::BlockAlly(n) => Some(format!("{{\"BlockAlly\": {n}}}")),
                    Effect::ApplyPack { power, amount, target } => POWERS[*power as usize].get().map(|g| {
                        format!("{{\"Apply\": {{\"power\": {}, \"amount\": {amount}, \"target\": {}}}}}", q(g.id), target_json(*target))
                    }),
                    Effect::RolledAttack if rolled => Some(q("RolledAttack")),
                    e => effect_json(e),
                })
                .collect();
            Some(format!("{{\"name\": {}, \"effects\": [{}]}}", q(m.name), es?.join(", ")))
        })
        .collect();
    let rows: Vec<String> = d
        .pattern
        .iter()
        .map(|r| {
            let when: Vec<String> = r
                .when
                .iter()
                .map(|c| match *c {
                    PatCond::FirstTurn => q("FirstTurn"),
                    PatCond::Allies => q("Allies"),
                    PatCond::LastMove(m) => format!("{{\"LastMove\": {m}}}"),
                    PatCond::LastTwo(m) => format!("{{\"LastTwo\": {m}}}"),
                    PatCond::Window(a, b) => format!("{{\"Window\": [{}, {}]}}", mid(a), mid(b)),
                    PatCond::Slot(n) => format!("{{\"Slot\": {n}}}"),
                    PatCond::RollBelow(n) => format!("{{\"RollBelow\": {n}}}"),
                })
                .collect();
            let then = match r.then {
                PatPick::Move(m) => format!("{{\"Move\": {m}}}"),
                PatPick::Chance { p, yes, no } => format!("{{\"Chance\": {{\"p\": {p:?}, \"yes\": {yes}, \"no\": {no}}}}}"),
            };
            format!("{{\"when\": [{}], \"then\": {then}}}", when.join(", "))
        })
        .collect();
    let powers: Vec<String> = d.start_powers.iter().map(|(p, n)| format!("{{\"power\": {}, \"amount\": {n}}}", q(&format!("{p:?}")))).collect();
    let mut rolls = String::new();
    if let Some((lo, hi)) = d.rolled_attack {
        rolls += &format!(", \"rolled_attack\": [{lo}, {hi}]");
    }
    if !d.rolled_powers.is_empty() {
        let ps: Vec<String> = d.rolled_powers.iter().map(|(p, lo, hi)| format!("{{\"power\": {}, \"amount\": [{lo}, {hi}]}}", q(&format!("{p:?}")))).collect();
        rolls += &format!(", \"rolled_powers\": [{}]", ps.join(", "));
    }
    let asc = if d.ascension_rows.is_empty() { String::new() } else { format!(", \"ascension\": {}", d.ascension_rows) };
    let split = if d.split_move == NO_MOVE {
        String::new()
    } else {
        let [a, b] = d.split_into;
        format!(", \"split\": {{\"move\": {}, \"into\": [{}, {}]}}", d.split_move, q(a.def().name), q(b.def().name))
    };
    Some(format!(
        "{{\"id\": {}{code}, \"hp\": [{}, {}], \"start_block\": {}, \"start_powers\": [{}]{rolls}, \"moves\": [{}], \"pattern\": [{}]{split}{asc}}}",
        q(id),
        d.hp_min,
        d.hp_max,
        d.start_block,
        powers.join(", "),
        moves?.join(", "),
        rows.join(", ")
    ))
}

/// An official power as a pack power with id `id`: its hooks, statics,
/// replacements and fields (`PowerRules`).
pub fn power_json(id: &str, p: Power) -> Option<String> {
    let hooks: Option<Vec<String>> = crate::hooks::hooks(p)
        .iter()
        .map(|h| {
            let hp_loss = if h.hp_loss == HpLossFrom::Card { String::new() } else { format!(", \"hp_loss_source\": {}", q(&format!("{:?}", h.hp_loss))) };
            let first = if h.first { ", \"acts_first\": true" } else { "" };
            let before = if h.before_hand { ", \"before_hand\": true" } else { "" };
            Some(format!(
                "{{\"trigger\": {}, \"condition\": {}{hp_loss}{first}{before}, \"effects\": {}}}",
                trigger_json(h.trigger),
                hook_conditions_json(h),
                effects_json(h.effects)?
            ))
        })
        .collect();
    let statics: Vec<String> = crate::hooks::statics(p)
        .iter()
        .map(|s| {
            let cond = match s.condition {
                StaticCondition::Always => q("Always"),
                StaticCondition::CardInPlayTagged(t) => format!("{{\"CardInPlayTagged\": {}}}", q(&format!("{t:?}"))),
                StaticCondition::OwnerHpAtMostHalf => q("OwnerHpAtMostHalf"),
                StaticCondition::Holds { side, power } => {
                    format!("{{\"Holds\": {{\"side\": {}, \"power\": {}}}}}", q(&format!("{side:?}")), q(&format!("{power:?}")))
                }
            };
            format!(
                "{{\"modifies\": {}, \"stage\": {}, \"amount\": {}, \"num\": {}, \"den\": {}, \"condition\": {cond}}}",
                q(&format!("{:?}", s.modifies)),
                q(&format!("{:?}", s.stage)),
                s.amount,
                s.num,
                s.den
            )
        })
        .collect();
    let reps: Option<Vec<String>> = crate::hooks::replacements(p)
        .iter()
        .map(|r| {
            let action = match r.action {
                Replace::Cancel => q("Cancel"),
                Replace::Cap(n) => format!("{{\"Cap\": {n}}}"),
                Replace::Add(n) => format!("{{\"Add\": {n}}}"),
                Replace::Multiply(a, b) => format!("{{\"Multiply\": {{\"num\": {a}, \"den\": {b}}}}}"),
                Replace::AtLeast(n) => format!("{{\"AtLeast\": {n}}}"),
            };
            let power = r.power.map_or(String::new(), |p| format!(", \"power\": {}", q(&format!("{p:?}"))));
            let up_to = r.up_to.map_or(String::new(), |n| format!(", \"upTo\": {n}"));
            Some(format!("{{\"event\": {}{power}{up_to}, \"action\": {action}, \"then\": {}}}", q(&format!("{:?}", r.event)), effects_json(r.then)?))
        })
        .collect();
    let r = official().powers[p as usize].rules;
    let mut fields = String::new();
    if r.debuff_if_negative {
        fields += ", \"debuff_if_negative\": true";
    }
    if r.can_go_negative {
        fields += ", \"can_go_negative\": true";
    }
    let sk = r.skips_first_round;
    if sk != SkipsFirstRound::default() {
        let parts: Vec<&str> = [
            (sk.from_monster, "\"from_monster\": true"),
            (sk.from_monster_after_turn_end, "\"from_monster_after_turn_end\": true"),
            (sk.on_monster, "\"on_monster\": true"),
        ]
            .into_iter()
            .filter_map(|(on, s)| on.then_some(s))
            .collect();
        fields += &format!(", \"skips_first_round\": {{{}}}", parts.join(", "));
    }
    if let Some(n) = r.attack_shape {
        fields += &format!(", \"attack_shape\": {{\"split\": {n}}}");
    }
    if let Some(n) = r.block_loss {
        fields += &format!(", \"block_loss\": {n}");
    }
    if let Some(n) = r.cap {
        fields += &format!(", \"cap\": {n}");
    }
    let mut rules = String::new();
    if let Some(ty) = r.forbids {
        rules += &format!(", \"forbids\": {}", q(&format!("{ty:?}")));
    }
    if let Some((ty, cost)) = r.sets_cost {
        rules += &format!(", \"sets_cost\": {{\"type\": {}, \"cost\": {cost}}}", q(&format!("{ty:?}")));
    }
    if let Some(ty) = r.exhausts_played {
        rules += &format!(", \"exhausts_played\": {}", q(&format!("{ty:?}")));
    }
    if let Some(ty) = r.plays_unplayable {
        rules += &format!(", \"plays_unplayable\": {}", q(&format!("{ty:?}")));
    }
    Some(format!(
        "{{\"id\": {}, \"debuff\": {}{fields}, \"hooks\": [{}], \"statics\": [{}], \"replacements\": [{}]{rules}}}",
        q(id),
        r.debuff,
        hooks?.join(", "),
        statics.join(", "),
        reps?.join(", ")
    ))
}

/// The official content files as the engine's definitions write them:
/// `(file name under content/, text)` for cards, powers, monsters and
/// relics (written back from the parsed file), one
/// entry per line. `export_content` writes them; a test checks the
/// committed files equal these.
pub fn official_files() -> [(&'static str, String); 4] {
    let file = |key: &str, entries: Vec<String>| format!("{{\"version\": {CONTENT_VERSION}, \"{key}\": [\n{}\n]}}\n", entries.join(",\n"));
    let cards = CardKind::ALL.iter().flat_map(|&k| official_card_json(k).expect("an official card writes as data")).collect();
    let powers = Power::ALL.iter().map(|&p| power_json(&format!("{p:?}"), p).expect("an official power writes as data")).collect();
    let monsters = (1..NUM_OFFICIAL_MONSTERS)
        .map(|i| official_monster_json(MonsterKind(i as u8)).expect("an official monster writes as data"))
        .collect();
    let relics = official_relics().iter().map(|(id, r)| official_relic_json(id, r)).collect();
    [
        ("cards.json", file("cards", cards)),
        ("powers.json", file("powers", powers)),
        ("monsters.json", file("monsters", monsters)),
        ("relics.json", file("relics", relics)),
    ]
}

/// A minimal JSON reader for content packs (the engine has no dependencies;
/// public for `engine/tests/wording.rs`).
pub mod json {
    #[derive(Clone, Debug, PartialEq)]
    pub enum Value {
        Null,
        Bool(bool),
        Num(f64),
        Str(String),
        Arr(Vec<Value>),
        Obj(Vec<(String, Value)>),
    }

    impl Value {
        pub fn get(&self, k: &str) -> Option<&Value> {
            match self {
                Value::Obj(kv) => kv.iter().find(|(key, _)| key == k).map(|(_, v)| v),
                _ => None,
            }
        }
        pub fn items(&self) -> &[Value] {
            match self {
                Value::Arr(v) => v,
                _ => &[],
            }
        }
        pub fn str(&self) -> Option<&str> {
            match self {
                Value::Str(s) => Some(s),
                _ => None,
            }
        }
        pub fn int(&self) -> Option<i64> {
            match self {
                Value::Num(n) if n.fract() == 0.0 => Some(*n as i64),
                _ => None,
            }
        }
        pub fn bool(&self) -> Option<bool> {
            match self {
                Value::Bool(b) => Some(*b),
                _ => None,
            }
        }
    }

    /// `v` as text, on one line with `", "` and `": "` between parts (the
    /// content files' layout).
    pub fn write(v: &Value) -> String {
        match v {
            Value::Null => "null".into(),
            Value::Bool(b) => b.to_string(),
            Value::Num(n) if n.fract() == 0.0 && n.abs() < 1e15 => format!("{}", *n as i64),
            Value::Num(n) => format!("{n:?}"),
            Value::Str(s) => format!("{s:?}"),
            Value::Arr(xs) => format!("[{}]", xs.iter().map(write).collect::<Vec<_>>().join(", ")),
            Value::Obj(kv) => format!("{{{}}}", kv.iter().map(|(k, x)| format!("{k:?}: {}", write(x))).collect::<Vec<_>>().join(", ")),
        }
    }

    pub fn parse(text: &str) -> Result<Value, String> {
        let mut p = Parser { b: text.as_bytes(), i: 0 };
        let v = p.value()?;
        p.ws();
        if p.i != p.b.len() {
            return Err(format!("content pack: trailing text at byte {}", p.i));
        }
        Ok(v)
    }

    struct Parser<'a> {
        b: &'a [u8],
        i: usize,
    }

    impl Parser<'_> {
        fn ws(&mut self) {
            while self.i < self.b.len() && self.b[self.i].is_ascii_whitespace() {
                self.i += 1;
            }
        }
        fn err<T>(&self, what: &str) -> Result<T, String> {
            Err(format!("content pack: {what} at byte {}", self.i))
        }
        fn eat(&mut self, c: u8) -> Result<(), String> {
            self.ws();
            if self.b.get(self.i) == Some(&c) {
                self.i += 1;
                Ok(())
            } else {
                self.err(&format!("expected '{}'", c as char))
            }
        }
        fn value(&mut self) -> Result<Value, String> {
            self.ws();
            match self.b.get(self.i) {
                Some(b'{') => {
                    self.i += 1;
                    let mut kv = Vec::new();
                    self.ws();
                    if self.b.get(self.i) == Some(&b'}') {
                        self.i += 1;
                        return Ok(Value::Obj(kv));
                    }
                    loop {
                        self.ws();
                        let k = self.string()?;
                        self.eat(b':')?;
                        kv.push((k, self.value()?));
                        self.ws();
                        match self.b.get(self.i) {
                            Some(b',') => self.i += 1,
                            Some(b'}') => {
                                self.i += 1;
                                return Ok(Value::Obj(kv));
                            }
                            _ => return self.err("expected ',' or '}'"),
                        }
                    }
                }
                Some(b'[') => {
                    self.i += 1;
                    let mut v = Vec::new();
                    self.ws();
                    if self.b.get(self.i) == Some(&b']') {
                        self.i += 1;
                        return Ok(Value::Arr(v));
                    }
                    loop {
                        v.push(self.value()?);
                        self.ws();
                        match self.b.get(self.i) {
                            Some(b',') => self.i += 1,
                            Some(b']') => {
                                self.i += 1;
                                return Ok(Value::Arr(v));
                            }
                            _ => return self.err("expected ',' or ']'"),
                        }
                    }
                }
                Some(b'"') => Ok(Value::Str(self.string()?)),
                Some(b't') if self.b[self.i..].starts_with(b"true") => {
                    self.i += 4;
                    Ok(Value::Bool(true))
                }
                Some(b'f') if self.b[self.i..].starts_with(b"false") => {
                    self.i += 5;
                    Ok(Value::Bool(false))
                }
                Some(b'n') if self.b[self.i..].starts_with(b"null") => {
                    self.i += 4;
                    Ok(Value::Null)
                }
                Some(c) if *c == b'-' || c.is_ascii_digit() => {
                    let s = self.i;
                    while self.i < self.b.len() && matches!(self.b[self.i], b'-' | b'+' | b'.' | b'e' | b'E' | b'0'..=b'9') {
                        self.i += 1;
                    }
                    let t = std::str::from_utf8(&self.b[s..self.i]).unwrap();
                    t.parse().map(Value::Num).or_else(|_| self.err("bad number"))
                }
                _ => self.err("expected a value"),
            }
        }
        fn string(&mut self) -> Result<String, String> {
            if self.b.get(self.i) != Some(&b'"') {
                return self.err("expected a string");
            }
            self.i += 1;
            let mut out = Vec::new();
            while let Some(&c) = self.b.get(self.i) {
                self.i += 1;
                match c {
                    b'"' => return String::from_utf8(out).or_else(|_| self.err("bad UTF-8")),
                    b'\\' => {
                        let e = *self.b.get(self.i).ok_or("content pack: unterminated string")?;
                        self.i += 1;
                        out.push(match e {
                            b'n' => b'\n',
                            b't' => b'\t',
                            b'r' => b'\r',
                            b'"' | b'\\' | b'/' => e,
                            _ => return self.err("unsupported escape"),
                        });
                    }
                    _ => out.push(c),
                }
            }
            self.err("unterminated string")
        }
    }
}

#[cfg(test)]
mod slot_set_tests {
    use super::*;

    /// More slot sets than a u16 index holds (and than one chunk) intern,
    /// read back as bound, and keep their index when bound again.
    #[test]
    fn slot_sets_past_one_chunk() {
        let set = |i: usize| {
            let mut s = EMPTY_SLOTS;
            s.cards = vec![(i % 4000) as u16, (i / 4000) as u16];
            s
        };
        let ids: Vec<u32> = (0..17 * SLOT_CHUNK).map(|i| intern_slots(&set(i)).unwrap()).collect();
        for (i, &id) in ids.iter().enumerate() {
            assert_eq!(*slot_cell(id as usize).get().unwrap(), set(i));
            assert_eq!(intern_slots(&set(i)).unwrap(), id);
        }
        assert_eq!(intern_slots(&EMPTY_SLOTS).unwrap(), NO_SLOTS);
    }
}

#[cfg(test)]
mod card_level_tests {
    use super::*;

    /// Each official card's file entry at level 1, as `card_level_json`
    /// resolves it, is the engine's upgraded definition (the code's `X+`).
    #[test]
    fn official_levels_match_the_code() {
        let mut n = 0;
        for &kind in CardKind::ALL.iter() {
            let d1 = CardId::new(kind, true).def();
            for entry in official_card_json(kind).unwrap() {
                let Some(got) = card_level_json(&entry, 1, true, 2).unwrap() else { continue };
                let want = card_json(d1.name, d1).unwrap();
                let parse = |t: &str| parse_card(&json::parse(t).unwrap(), 2).unwrap();
                let (g, w) = (parse(&got), parse(&want));
                assert_eq!((g.parts(), g.ty, g.tags, g.playable_if), (w.parts(), w.ty, w.tags, w.playable_if), "{}", d1.name);
                assert!(got.starts_with(&format!("{{\"id\": {}", q(d1.name))), "{got}");
                n += 1;
            }
        }
        assert!(n > 50, "{n} official upgrades checked");
    }

    /// A pack card's level keeps its pack power's id, and levels past its
    /// max (or a card with no upgrade) are `None`.
    #[test]
    fn pack_levels() {
        let e = "{\"id\": \"cl\", \"cost\": 1, \"type\": \"Skill\", \"effects\": [{\"Apply\": {\"power\": \"cl_power\", \"amount\": 2, \"target\": \"Me\"}}], \"upgrade\": {\"effects.0.Apply.amount\": \"n\"}, \"max_level\": 3}";
        let l3 = card_level_json(e, 3, false, 2).unwrap().unwrap();
        assert!(l3.contains("\"id\": \"cl+3\"") && l3.contains("\"power\": \"cl_power\", \"amount\": 8"), "{l3}");
        assert_eq!(card_level_json(e, 4, false, 2).unwrap(), None);
        assert_eq!(card_level_json("{\"id\": \"x\", \"cost\": 0, \"type\": \"Skill\", \"effects\": [{\"Block\": 1}]}", 1, false, 2).unwrap(), None);
    }
}
