//! Relics as content (docs/specs/relics.md, docs/specs/relic-entity.md):
//! an entry of a pack's `"relics"` list or of the official
//! `content/relics.json`. A relic is held by the player in a fight with a
//! counter, and is its hooks, the powers the player starts the fight with,
//! the fights it acts in, and HP added to the fight's combat-end heal.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use crate::effects::{Effect, Target};
use crate::hooks::{Condition, Hook, Trigger};
use crate::monsters::EncounterGroup;
use crate::powers::Power;
use crate::registry::json;

/// Most relics a player holds in one fight (docs/specs/relic-entity.md).
pub const RELIC_CAP: usize = 16;

/// Most distinct relic names one process interns.
const RELIC_CAPACITY: usize = 1024;

/// A relic held in a fight, by its interned name (`relic_id`): the same
/// name has the same id for the whole process, so equal relic lists
/// compare and hash equal. Process-local: the codec writes names.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub struct RelicId(pub u16);

static RELIC_NAMES: [OnceLock<Box<str>>; RELIC_CAPACITY] = [const { OnceLock::new() }; RELIC_CAPACITY];

/// The id of a relic name (`"Burning Blood"`, `"gen:anchor"`), interned on
/// first use. Doesn't check the name is a relic.
pub fn relic_id(name: &str) -> Result<RelicId, String> {
    static INDEX: OnceLock<Mutex<HashMap<Box<str>, u16>>> = OnceLock::new();
    let mut t = INDEX.get_or_init(Default::default).lock().unwrap();
    if let Some(&i) = t.get(name) {
        return Ok(RelicId(i));
    }
    let i = t.len();
    if i >= RELIC_CAPACITY {
        return Err(format!("relic {name:?}: more than {RELIC_CAPACITY} relic names in this process"));
    }
    RELIC_NAMES[i].set(name.into()).expect("a fresh relic slot");
    t.insert(name.into(), i as u16);
    Ok(RelicId(i as u16))
}

impl RelicId {
    /// The name it was interned from.
    pub fn name(self) -> &'static str {
        RELIC_NAMES[self.0 as usize].get().expect("an interned relic id")
    }

    /// Its hooks: the ones `register_hooks` gave it, else the hooks of the
    /// relic its name names (`registry::relic`), else none.
    #[inline]
    pub fn hooks(self) -> &'static [Hook] {
        RELIC_HOOKS[self.0 as usize].get_or_init(|| crate::registry::relic(self.name()).map_or(&[], |r| r.hooks))
    }
}

static RELIC_HOOKS: [OnceLock<&'static [Hook]>; RELIC_CAPACITY] = [const { OnceLock::new() }; RELIC_CAPACITY];

static RELIC_POTION_POTENCY: [OnceLock<i16>; RELIC_CAPACITY] = [const { OnceLock::new() }; RELIC_CAPACITY];

impl RelicId {
    /// Its `potion_potency`: the one `register_potion_potency` gave it,
    /// else that of the relic its name names, else 1.
    #[inline]
    pub fn potion_potency(self) -> i16 {
        *RELIC_POTION_POTENCY[self.0 as usize].get_or_init(|| crate::registry::relic(self.name()).map_or(1, |r| r.potion_potency))
    }
}

static RELIC_POTION_SLOTS: [OnceLock<i16>; RELIC_CAPACITY] = [const { OnceLock::new() }; RELIC_CAPACITY];

impl RelicId {
    /// Its `potion_slots`: the one `register_potion_slots` gave it, else
    /// that of the relic its name names, else 0.
    #[inline]
    pub fn potion_slots(self) -> i16 {
        *RELIC_POTION_SLOTS[self.0 as usize].get_or_init(|| crate::registry::relic(self.name()).map_or(0, |r| r.potion_slots))
    }
}

static RELIC_DRAW_PER_TURN: [OnceLock<i16>; RELIC_CAPACITY] = [const { OnceLock::new() }; RELIC_CAPACITY];

impl RelicId {
    /// Its `draw_per_turn`: the one `register_draw_per_turn` gave it, else
    /// that of the relic its name names, else 0.
    #[inline]
    pub fn draw_per_turn(self) -> i16 {
        *RELIC_DRAW_PER_TURN[self.0 as usize].get_or_init(|| crate::registry::relic(self.name()).map_or(0, |r| r.draw_per_turn))
    }
}

static RELIC_RULES: [OnceLock<RelicRules>; RELIC_CAPACITY] = [const { OnceLock::new() }; RELIC_CAPACITY];

impl RelicId {
    /// Its rules (`x_bonus`, `keeps_energy`, `plays_per_turn`,
    /// `keeps_hand`): the ones `register_rules` gave it, else those of the
    /// relic its name names, else none.
    #[inline]
    pub fn rules(self) -> RelicRules {
        *RELIC_RULES[self.0 as usize].get_or_init(|| crate::registry::relic(self.name()).map_or(RelicRules::default(), |r| r.rules))
    }
}

/// Gives relic `id` these rules for the process (as
/// `register_potion_potency`).
pub fn register_rules(id: RelicId, r: RelicRules) -> Result<(), String> {
    if *RELIC_RULES[id.0 as usize].get_or_init(|| r) != r {
        return Err(format!("relic {:?}: its rules differ from the ones this name already has in this process", id.name()));
    }
    Ok(())
}

static RELIC_HEAL_SCALE: [OnceLock<(i16, i16)>; RELIC_CAPACITY] = [const { OnceLock::new() }; RELIC_CAPACITY];

impl RelicId {
    /// Its `heal_scale` (numerator, denominator): the one
    /// `register_heal_scale` gave it, else that of the relic its name
    /// names, else (1, 1).
    #[inline]
    pub fn heal_scale(self) -> (i16, i16) {
        *RELIC_HEAL_SCALE[self.0 as usize].get_or_init(|| crate::registry::relic(self.name()).map_or((1, 1), |r| r.heal_scale))
    }
}

/// Gives relic `id` this `heal_scale` for the process (as
/// `register_potion_potency`).
pub fn register_heal_scale(id: RelicId, k: (i16, i16)) -> Result<(), String> {
    if *RELIC_HEAL_SCALE[id.0 as usize].get_or_init(|| k) != k {
        return Err(format!("relic {:?}: its heal_scale differs from the one this name already has in this process", id.name()));
    }
    Ok(())
}

/// Gives relic `id` this `draw_per_turn` for the process (as
/// `register_potion_potency`).
pub fn register_draw_per_turn(id: RelicId, n: i16) -> Result<(), String> {
    if *RELIC_DRAW_PER_TURN[id.0 as usize].get_or_init(|| n) != n {
        return Err(format!("relic {:?}: its draw_per_turn differs from the one this name already has in this process", id.name()));
    }
    Ok(())
}

/// Gives relic `id` these `potion_slots` for the process (as
/// `register_potion_potency`).
pub fn register_potion_slots(id: RelicId, n: i16) -> Result<(), String> {
    if *RELIC_POTION_SLOTS[id.0 as usize].get_or_init(|| n) != n {
        return Err(format!("relic {:?}: its potion_slots differ from the ones this name already has in this process", id.name()));
    }
    Ok(())
}

/// Gives relic `id` this `potion_potency` for the process (as
/// `register_hooks`): a different one is an error naming the relic.
pub fn register_potion_potency(id: RelicId, k: i16) -> Result<(), String> {
    if *RELIC_POTION_POTENCY[id.0 as usize].get_or_init(|| k) != k {
        return Err(format!("relic {:?}: its potion_potency differs from the one this name already has in this process", id.name()));
    }
    Ok(())
}

/// Gives relic `id` these hooks for the process (a fight built from its
/// spec). A name keeps one set of hooks: a different set is an error
/// naming the relic.
pub fn register_hooks(id: RelicId, hooks: &'static [Hook]) -> Result<(), String> {
    let held = RELIC_HOOKS[id.0 as usize].get_or_init(|| hooks);
    if *held != hooks {
        return Err(format!("relic {:?}: its hooks differ from the ones this name already has in this process", id.name()));
    }
    Ok(())
}

/// The relics a player holds in a fight, in order, each with its counter
/// (docs/specs/relic-entity.md). A fixed array, as states are cloned in
/// search; empty for a fight without relics.
#[derive(Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct Relics {
    n: u8,
    ids: [RelicId; RELIC_CAP],
    counters: [i16; RELIC_CAP],
}

impl Relics {
    pub fn len(&self) -> usize {
        self.n as usize
    }

    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    /// Adds a relic after the others; more than `RELIC_CAP` is an error
    /// naming it.
    pub fn push(&mut self, id: RelicId, counter: i16) -> Result<(), String> {
        if self.len() >= RELIC_CAP {
            return Err(format!("relic {:?}: the player would hold more than {RELIC_CAP} relics (RELIC_CAP)", id.name()));
        }
        self.ids[self.len()] = id;
        self.counters[self.len()] = counter;
        self.n += 1;
        Ok(())
    }

    /// Each held relic and its counter, in order.
    pub fn iter(&self) -> impl Iterator<Item = (RelicId, i16)> + '_ {
        self.ids[..self.len()].iter().copied().zip(self.counters[..self.len()].iter().copied())
    }

    /// The relic at `i`.
    #[inline]
    pub fn id(&self, i: usize) -> RelicId {
        assert!(i < self.len(), "relic index {i} out of range");
        self.ids[i]
    }

    /// The counter of the relic at `i`.
    pub fn counter(&self, i: usize) -> i16 {
        assert!(i < self.len(), "relic index {i} out of range");
        self.counters[i]
    }

    pub fn set_counter(&mut self, i: usize, v: i16) {
        assert!(i < self.len(), "relic index {i} out of range");
        self.counters[i] = v;
    }
}

impl std::fmt::Debug for Relics {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_list().entries(self.iter().map(|(id, c)| (id.name(), c))).finish()
    }
}

/// A relic's rarity (data for later drops; no behaviour now).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Rarity {
    Starter,
    Common,
    Uncommon,
    Rare,
    Boss,
    Shop,
    Event,
}

impl Rarity {
    pub const ALL: [Rarity; 7] = [Rarity::Starter, Rarity::Common, Rarity::Uncommon, Rarity::Rare, Rarity::Boss, Rarity::Shop, Rarity::Event];

    /// The name the files use (`"common"`).
    pub fn name(self) -> &'static str {
        match self {
            Rarity::Starter => "starter",
            Rarity::Common => "common",
            Rarity::Uncommon => "uncommon",
            Rarity::Rare => "rare",
            Rarity::Boss => "boss",
            Rarity::Shop => "shop",
            Rarity::Event => "event",
        }
    }
}

/// The fight kinds a relic's or a potion's `fights` names, in the files' words.
pub const FIGHT_KINDS: [(&str, EncounterGroup); 3] =
    [("hallway", EncounterGroup::Hallway), ("elite", EncounterGroup::Elite), ("boss", EncounterGroup::Boss)];

/// The keys a relic entry may carry; any other is a load error.
pub const RELIC_KEYS: [&str; 20] = [
    "id", "rarity", "powers", "fights", "win_heal", "hooks", "counter", "potion_potency", "potion_slots", "draw_per_turn", "x_bonus", "keeps_energy",
    "plays_per_turn", "keeps_hand", "heal_scale", "exhaust_save", "sees_draw_order",
    "hides_intents", "no_potions", "bottles",
];

/// What a held relic changes in the combat's rules (docs/specs/blocked-relics.md
/// step 1); the game's relics check these by name where they act.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct RelicRules {
    /// Added to an X card's X when it resolves, not paid (Chemical X's 2).
    pub x_bonus: i16,
    /// Unspent energy carries into the next turn (Ice Cream).
    pub keeps_energy: bool,
    /// No card is playable once this many were played this turn; 0 is no
    /// limit (Velvet Choker's 6).
    pub plays_per_turn: i16,
    /// The hand isn't discarded at turn end (Runic Pyramid): retained and
    /// kept cards stay, ethereal ones exhaust, cards that act at turn end
    /// (Burn) go to the discard pile as they are played.
    pub keeps_hand: bool,
    /// A played card that would exhaust (not a Power, not a replayed copy)
    /// goes to the discard pile instead with chance numerator /
    /// denominator, rolled before its exhaust (Strange Spoon's [1, 2]: the
    /// game's `UseCardAction`, `cardRandomRng.randomBoolean()`; the file's
    /// `exhaust_save`, docs/specs/blocked-relics.md step 7). A save fires no
    /// `CardExhausted` hooks. Each held relic rolls alone; (0, 0) is none.
    pub exhaust_save: (i16, i16),
    /// The player sees the draw pile in its order (Frozen Eye): every
    /// shuffle is a chance event over the pile's orders, and a card put in
    /// at a random spot one over its spots, so `Top` knows the whole pile.
    pub sees_draw_order: bool,
    /// Enemy intents are hidden (Runic Dome): a monster's next move is
    /// rolled when it acts, from its history and allies when the game
    /// rolled it (`CombatState::intent_hidden`).
    pub hides_intents: bool,
    /// The player can't obtain potions (Sozu: the game's `hasRelic("Sozu")`
    /// in ObtainPotionAction, EntropicBrew.use and the other callers): an
    /// `ObtainRandomPotions` gives none.
    pub no_potions: bool,
    /// One card of this type, chosen outside the fight, starts every fight
    /// in the opening hand as an innate card does (Bottled Flame, Lightning,
    /// Tornado: the card's `inBottle*` flag, which `CardGroup.initializeDeck`
    /// puts on top with the innate cards). The relic's counter names it: its
    /// place in the fight's deck plus 1 (0: none chosen).
    pub bottles: Option<crate::cards::CardType>,
}

/// A relic as loaded.
#[derive(Clone, Debug, PartialEq)]
pub struct RelicSpec {
    pub rarity: Rarity,
    /// Official powers the player starts with, with amounts.
    pub powers: Vec<(Power, i16)>,
    /// Pack powers (registry indices) the player starts with, with amounts.
    pub gen_powers: Vec<(u16, i16)>,
    /// The fight kinds it acts in, as `FIGHT_KINDS` flags (bit i for entry i).
    pub fights: u8,
    /// HP added to the fight's combat-end heal.
    pub win_heal: i16,
    /// The counter the fight starts it at (the file's `counter`, default
    /// 0; a caller may set another).
    pub counter: i16,
    /// Its hooks, run for the player before the player's powers' hooks
    /// (docs/specs/relic-entity.md): the `powers` shorthand as a first
    /// `CombatStart` hook applying each to the player in order, then the
    /// file's `hooks`. `powers` and `gen_powers` keep the shorthand's list
    /// (the writer, the power-cap check).
    pub hooks: &'static [Hook],
    /// What a potion with potency above 0 is multiplied by while the
    /// player holds it (Sacred Bark's 2; the file's `potion_potency`,
    /// default 1, docs/specs/potions.md).
    pub potion_potency: i16,
    /// Potion slots it adds while the player holds it (Potion Belt's 2;
    /// the file's `potion_slots`, default 0, docs/specs/act1-singles.md
    /// section 5).
    pub potion_slots: i16,
    /// Cards it adds to every turn's draw while the player holds it (Snecko
    /// Eye's 2: the game's `masterHandSize += 2`; the file's
    /// `draw_per_turn`, default 0, docs/specs/sparse-piles.md).
    pub draw_per_turn: i16,
    /// Its rules (the file's `x_bonus`, `keeps_energy`, `plays_per_turn`,
    /// `keeps_hand`; default none).
    pub rules: RelicRules,
    /// What the player's heals are multiplied by while the player holds it,
    /// as (numerator, denominator), rounded half up (Magic Flower's [3, 2]:
    /// the game's `onPlayerHeal`; the file's `heal_scale`, default [1, 1],
    /// docs/specs/blocked-relics.md step 4). The monsters' heals are not.
    pub heal_scale: (i16, i16),
}

impl RelicSpec {
    /// Whether it acts in a fight of `group`.
    pub fn acts_in(&self, group: EncounterGroup) -> bool {
        FIGHT_KINDS.iter().enumerate().any(|(i, (_, g))| *g == group && self.fights & 1 << i != 0)
    }
}

/// A `fights` key's fight kinds as `FIGHT_KINDS` flags (a relic's "acts
/// in", a potion's "usable in"); every kind when it is left out.
pub fn parse_fights(f: Option<&json::Value>) -> Result<u8, String> {
    let Some(f) = f else { return Ok((1 << FIGHT_KINDS.len()) - 1) };
    if !matches!(f, json::Value::Arr(_)) {
        return Err(format!("fights must be a list of fight kinds, got {f:?}"));
    }
    let items = f.items();
    if items.is_empty() {
        return Err("fights is empty (leave it out for every fight)".into());
    }
    let mut bits = 0u8;
    for k in items {
        let name = k.str().unwrap_or("");
        let i = FIGHT_KINDS
            .iter()
            .position(|(n, _)| *n == name)
            .ok_or_else(|| format!("unknown fight kind {k:?} (known: {:?})", FIGHT_KINDS.map(|(n, _)| n)))?;
        bits |= 1 << i;
    }
    Ok(bits)
}

/// Parses one entry of a file of `version`: its id and spec. `official`
/// names an official power; `pack` a pack power loaded before or earlier
/// in this pack (`None` for the official file, which may name official
/// powers only). Errors name the relic.
pub fn parse_relic(
    v: &json::Value,
    official: &dyn Fn(&str) -> Option<Power>,
    pack: Option<&dyn Fn(&str) -> Option<u16>>,
    version: u8,
) -> Result<(String, RelicSpec), String> {
    let id = v.get("id").and_then(json::Value::str).ok_or("relic without an id")?.to_string();
    let err = |x: String| format!("relic {id:?}: {x}");
    if let json::Value::Obj(kv) = v {
        if let Some((k, _)) = kv.iter().find(|(k, _)| !RELIC_KEYS.contains(&k.as_str())) {
            return Err(err(format!("unknown key {k:?} (known: {RELIC_KEYS:?})")));
        }
    }
    let rarity = match v.get("rarity") {
        None => return Err(err("no rarity".into())),
        Some(r) => {
            let name = r.str().ok_or_else(|| err(format!("rarity must be a name, got {r:?}")))?;
            Rarity::ALL.into_iter().find(|x| x.name() == name).ok_or_else(|| {
                err(format!("unknown rarity {name:?} (known: {:?})", Rarity::ALL.map(Rarity::name)))
            })?
        }
    };
    let (mut powers, mut gen_powers, mut applies) = (Vec::new(), Vec::new(), Vec::new());
    for p in v.get("powers").map(json::Value::items).unwrap_or(&[]) {
        let name = p.get("power").and_then(json::Value::str).ok_or_else(|| err("a power entry without a power".into()))?;
        let amount = p.get("amount").and_then(json::Value::int).ok_or_else(|| err(format!("power {name:?}: amount must be an integer")))?;
        let (amount, target) = (amount as i16, Target::Me);
        match (official(name), pack.and_then(|f| f(name))) {
            (Some(o), _) => {
                powers.push((o, amount));
                applies.push(Effect::Apply { power: o, amount, target });
            }
            (None, Some(i)) => {
                gen_powers.push((i, amount));
                applies.push(Effect::ApplyPack { power: i, amount, target });
            }
            (None, None) => {
                let what = if pack.is_some() { "official nor a loaded pack power" } else { "an official power" };
                return Err(err(format!("power {name:?} is not {what}")));
            }
        }
    }
    let fights = parse_fights(v.get("fights")).map_err(err)?;
    let win_heal = match v.get("win_heal") {
        None => 0,
        Some(h) => h.int().ok_or_else(|| err("win_heal must be an integer".into()))?,
    };
    if win_heal < 0 {
        return Err(err(format!("win_heal {win_heal} is negative")));
    }
    let counter = match v.get("counter") {
        None => 0,
        Some(c) => c.int().filter(|n| i16::try_from(*n).is_ok()).ok_or_else(|| err(format!("counter must be an integer of 16 bits, got {c:?}")))? as i16,
    };
    let potion_potency = match v.get("potion_potency") {
        None => 1,
        Some(c) => c.int().filter(|n| (1..=i16::MAX as i64).contains(n)).ok_or_else(|| err(format!("potion_potency must be an integer 1 or more, got {c:?}")))? as i16,
    };
    let potion_slots = match v.get("potion_slots") {
        None => 0,
        Some(c) => c.int().filter(|n| (0..=i16::MAX as i64).contains(n)).ok_or_else(|| err(format!("potion_slots must be an integer 0 or more, got {c:?}")))? as i16,
    };
    let draw_per_turn = match v.get("draw_per_turn") {
        None => 0,
        Some(c) => c.int().filter(|n| (0..=10).contains(n)).ok_or_else(|| err(format!("draw_per_turn must be an integer 0 to 10, got {c:?}")))? as i16,
    };
    let int_in = |k: &str, lo: i64, hi: i64| -> Result<i16, String> {
        match v.get(k) {
            None => Ok(0),
            Some(c) => c.int().filter(|n| (lo..=hi).contains(n)).map(|n| n as i16).ok_or_else(|| err(format!("{k} must be an integer {lo} to {hi}, got {c:?}"))),
        }
    };
    let flag = |k: &str| -> Result<bool, String> {
        match v.get(k) {
            None => Ok(false),
            Some(c) => c.bool().ok_or_else(|| err(format!("{k} must be true or false, got {c:?}"))),
        }
    };
    let rules = RelicRules {
        x_bonus: int_in("x_bonus", 0, 10)?,
        keeps_energy: flag("keeps_energy")?,
        plays_per_turn: int_in("plays_per_turn", 1, 99)?,
        keeps_hand: flag("keeps_hand")?,
        sees_draw_order: flag("sees_draw_order")?,
        hides_intents: flag("hides_intents")?,
        no_potions: flag("no_potions")?,
        bottles: match v.get("bottles") {
            None => None,
            Some(c) => match c.str() {
                Some("Attack") => Some(crate::cards::CardType::Attack),
                Some("Skill") => Some(crate::cards::CardType::Skill),
                Some("Power") => Some(crate::cards::CardType::Power),
                _ => return Err(err(format!("bottles must be \"Attack\", \"Skill\" or \"Power\", got {c:?}"))),
            },
        },
        exhaust_save: match v.get("exhaust_save") {
            None => (0, 0),
            Some(c) => match c.items() {
                [a, b] => match (a.int(), b.int()) {
                    (Some(a), Some(b)) if (1..=100).contains(&b) && (1..=b).contains(&a) => (a as i16, b as i16),
                    _ => return Err(err(format!("exhaust_save must be [numerator 1 to the denominator, denominator 1 to 100], got {c:?}"))),
                },
                _ => return Err(err(format!("exhaust_save must be [numerator, denominator], got {c:?}"))),
            },
        },
    };
    let heal_scale = match v.get("heal_scale") {
        None => (1, 1),
        Some(c) => match c.items() {
            [a, b] => match (a.int(), b.int()) {
                (Some(a), Some(b)) if (0..=100).contains(&a) && (1..=100).contains(&b) => (a as i16, b as i16),
                _ => return Err(err(format!("heal_scale must be [numerator 0 to 100, denominator 1 to 100], got {c:?}"))),
            },
            _ => return Err(err(format!("heal_scale must be [numerator, denominator], got {c:?}"))),
        },
    };
    let none: &dyn Fn(&str) -> Option<u16> = &|_| None;
    let hooks = v
        .get("hooks")
        .map(json::Value::items)
        .unwrap_or(&[])
        .iter()
        .map(|h| crate::registry::parse_hook_of(h, pack.unwrap_or(none), version, true))
        .collect::<Result<Vec<_>, _>>()
        .map_err(err)?;
    // The `powers` shorthand: a first `CombatStart` hook applying each to
    // the player, in the file's order (the game's `atBattleStart` relics).
    let mut hooks = hooks;
    if !applies.is_empty() {
        let effects: &'static [Effect] = Box::leak(applies.into_boxed_slice());
        hooks.insert(0, Hook { trigger: Trigger::CombatStart, condition: Condition::Always, also: Condition::Always, effects, hp_loss: crate::hooks::HpLossFrom::Card, first: false, before_hand: false });
    }
    let hooks: &'static [Hook] = if hooks.is_empty() { &[] } else { Box::leak(hooks.into_boxed_slice()) };
    Ok((id, RelicSpec { rarity, powers, gen_powers, fights, win_heal: win_heal as i16, counter, hooks, potion_potency, potion_slots, draw_per_turn, rules, heal_scale }))
}

/// Parses the official relics file: every entry, ids unique, official
/// powers only.
pub fn parse_official_relics(text: &str) -> Result<Vec<(String, RelicSpec)>, String> {
    let v = json::parse(text)?;
    let version = crate::registry::file_version(&v).map_err(|e| format!("relics: {e}"))?;
    let mut out: Vec<(String, RelicSpec)> = Vec::new();
    for e in v.get("relics").map(json::Value::items).unwrap_or(&[]) {
        let (id, spec) = parse_relic(e, &|n| Power::ALL.into_iter().find(|p| format!("{p:?}") == n), None, version)?;
        if out.iter().any(|(i, _)| *i == id) {
            return Err(format!("relic {id:?} twice in the file"));
        }
        out.push((id, spec));
    }
    Ok(out)
}

/// An official relic's entry as the file writes it (one line; default
/// fields left out).
pub fn official_relic_json(id: &str, s: &RelicSpec) -> String {
    let mut f = vec![format!("\"id\": {id:?}"), format!("\"rarity\": {:?}", s.rarity.name())];
    if !s.powers.is_empty() {
        let ps: Vec<String> = s.powers.iter().map(|(p, n)| format!("{{\"power\": {:?}, \"amount\": {n}}}", format!("{p:?}"))).collect();
        f.push(format!("\"powers\": [{}]", ps.join(", ")));
    }
    if s.fights != (1 << FIGHT_KINDS.len()) - 1 {
        let ks: Vec<String> = FIGHT_KINDS.iter().enumerate().filter(|(i, _)| s.fights & 1 << i != 0).map(|(_, (n, _))| format!("{n:?}")).collect();
        f.push(format!("\"fights\": [{}]", ks.join(", ")));
    }
    if s.win_heal != 0 {
        f.push(format!("\"win_heal\": {}", s.win_heal));
    }
    if s.potion_potency != 1 {
        f.push(format!("\"potion_potency\": {}", s.potion_potency));
    }
    if s.potion_slots != 0 {
        f.push(format!("\"potion_slots\": {}", s.potion_slots));
    }
    if s.draw_per_turn != 0 {
        f.push(format!("\"draw_per_turn\": {}", s.draw_per_turn));
    }
    let r = s.rules;
    if r.x_bonus != 0 {
        f.push(format!("\"x_bonus\": {}", r.x_bonus));
    }
    if r.keeps_energy {
        f.push("\"keeps_energy\": true".into());
    }
    if r.plays_per_turn != 0 {
        f.push(format!("\"plays_per_turn\": {}", r.plays_per_turn));
    }
    if r.keeps_hand {
        f.push("\"keeps_hand\": true".into());
    }
    if r.sees_draw_order {
        f.push("\"sees_draw_order\": true".into());
    }
    if r.hides_intents {
        f.push("\"hides_intents\": true".into());
    }
    if r.no_potions {
        f.push("\"no_potions\": true".into());
    }
    if let Some(ty) = r.bottles {
        f.push(format!("\"bottles\": \"{ty:?}\""));
    }
    if s.heal_scale != (1, 1) {
        f.push(format!("\"heal_scale\": [{}, {}]", s.heal_scale.0, s.heal_scale.1));
    }
    if r.exhaust_save != (0, 0) {
        f.push(format!("\"exhaust_save\": [{}, {}]", r.exhaust_save.0, r.exhaust_save.1));
    }
    format!("{{{}}}", f.join(", "))
}
