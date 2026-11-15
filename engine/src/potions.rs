//! Potions as content (docs/specs/potions.md): an entry of a pack's
//! `"potions"` list or of the official `content/potions.json`. The player
//! holds up to `POTION_CAP` of them in a fight, as a list kept in one fixed
//! order (by name), so holding the same potions is one state whatever order
//! they came in.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use crate::effects::Effect;
use crate::hooks::Condition;
use crate::registry::json;

/// Most potions a player holds in one fight: the game's 3 slots plus
/// Potion Belt's 2 (docs/specs/potions.md).
pub const POTION_CAP: usize = 5;

/// Most distinct potion names one process interns.
const POTION_CAPACITY: usize = 1024;

/// A potion, by its interned name (`potion_id`): the same name has the same
/// id for the whole process. Process-local: the codec writes names.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub struct PotionId(pub u16);

static POTION_NAMES: [OnceLock<Box<str>>; POTION_CAPACITY] = [const { OnceLock::new() }; POTION_CAPACITY];

/// The id of a potion name (`"Fire Potion"`, `"gen:fire"`), interned on
/// first use. Doesn't check the name is a potion.
pub fn potion_id(name: &str) -> Result<PotionId, String> {
    static INDEX: OnceLock<Mutex<HashMap<Box<str>, u16>>> = OnceLock::new();
    let mut t = INDEX.get_or_init(Default::default).lock().unwrap();
    if let Some(&i) = t.get(name) {
        return Ok(PotionId(i));
    }
    let i = t.len();
    if i >= POTION_CAPACITY {
        return Err(format!("potion {name:?}: more than {POTION_CAPACITY} potion names in this process"));
    }
    POTION_NAMES[i].set(name.into()).expect("a fresh potion slot");
    t.insert(name.into(), i as u16);
    Ok(PotionId(i as u16))
}

static POTION_SPECS: [OnceLock<Option<&'static PotionSpec>>; POTION_CAPACITY] = [const { OnceLock::new() }; POTION_CAPACITY];

impl PotionId {
    /// The name it was interned from.
    pub fn name(self) -> &'static str {
        POTION_NAMES[self.0 as usize].get().expect("an interned potion id")
    }

    /// Its spec: the potion its name names (`registry::potion`), looked up
    /// once. `None` for a name that names no loaded potion.
    pub fn spec(self) -> Option<&'static PotionSpec> {
        *POTION_SPECS[self.0 as usize].get_or_init(|| crate::registry::potion(self.name()).map(|s| &*Box::leak(Box::new(s))))
    }
}

/// The potions a player holds in a fight, sorted by name, copies kept
/// (docs/specs/potions.md). A fixed array, as states are cloned in search;
/// empty for a fight without potions.
#[derive(Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct Potions {
    n: u8,
    ids: [PotionId; POTION_CAP],
}

impl Potions {
    pub fn len(&self) -> usize {
        self.n as usize
    }

    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    /// Adds a potion at its place in the order; more than `POTION_CAP` is
    /// an error naming it.
    pub fn insert(&mut self, id: PotionId) -> Result<(), String> {
        if self.len() >= POTION_CAP {
            return Err(format!("potion {:?}: the player would hold more than {POTION_CAP} potions (POTION_CAP)", id.name()));
        }
        let n = self.len();
        let at = self.ids[..n].iter().position(|p| p.name() > id.name()).unwrap_or(n);
        self.ids.copy_within(at..n, at + 1);
        self.ids[at] = id;
        self.n += 1;
        Ok(())
    }

    /// Removes the potion at `i` (the later ones move up).
    pub fn remove(&mut self, i: usize) -> PotionId {
        assert!(i < self.len(), "potion index {i} out of range");
        let (id, n) = (self.ids[i], self.len());
        self.ids.copy_within(i + 1..n, i);
        self.n -= 1;
        self.ids[self.len()] = PotionId::default();
        id
    }

    /// The potion at `i`.
    #[inline]
    pub fn id(&self, i: usize) -> PotionId {
        assert!(i < self.len(), "potion index {i} out of range");
        self.ids[i]
    }

    /// Each held potion, in order.
    pub fn iter(&self) -> impl Iterator<Item = PotionId> + '_ {
        self.ids[..self.len()].iter().copied()
    }
}

impl std::fmt::Debug for Potions {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_list().entries(self.iter().map(PotionId::name)).finish()
    }
}

/// A potion's rarity (data for later drops; no behaviour now).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Rarity {
    Common,
    Uncommon,
    Rare,
}

impl Rarity {
    pub const ALL: [Rarity; 3] = [Rarity::Common, Rarity::Uncommon, Rarity::Rare];

    /// The name the files use (`"common"`).
    pub fn name(self) -> &'static str {
        match self {
            Rarity::Common => "common",
            Rarity::Uncommon => "uncommon",
            Rarity::Rare => "rare",
        }
    }
}

/// The keys a potion entry may carry; any other is a load error.
pub const POTION_KEYS: [&str; 7] = ["id", "rarity", "potency", "effects", "rows", "trigger", "fights"];

/// A potion as loaded: its effects in the card row format, row 0 the
/// `effects` (`Always`), then the `rows` with their conditions. A pack
/// power its effects apply is an `ApplyPack` of its registry index.
#[derive(Clone, Debug, PartialEq)]
pub struct PotionSpec {
    pub rarity: Rarity,
    /// The game's number (`getPotency()`); 0 for none (Elixir).
    pub potency: i16,
    pub rows: Vec<(Condition, Vec<Effect>)>,
    /// `Some(OwnerDied)` for a potion that fires as the player would die
    /// and is never drunk by hand (Fairy in a Bottle;
    /// docs/specs/would-die.md); `None` for a drinkable one.
    pub trigger: Option<crate::hooks::Trigger>,
    /// The fight kinds it can be drunk in, as `relics::FIGHT_KINDS` flags
    /// (the file's `fights`, default every kind; Smoke Bomb's hallway and
    /// elite).
    pub fights: u8,
}

impl PotionSpec {
    /// Every effect, row by row.
    pub fn effects(&self) -> impl Iterator<Item = &Effect> {
        self.rows.iter().flat_map(|(_, es)| es)
    }

    /// Whether it can be drunk in a fight of `group`.
    pub fn usable_in(&self, group: crate::monsters::EncounterGroup) -> bool {
        crate::relics::FIGHT_KINDS.iter().enumerate().any(|(i, (_, g))| *g == group && self.fights & 1 << i != 0)
    }

    /// A targeted potion needs a chosen enemy (the card rule).
    pub fn targeted(&self) -> bool {
        self.rows.iter().any(|(c, effects)| {
            matches!(c, Condition::TargetIntendsAttack | Condition::TargetHas(_) | Condition::TargetLacks(_) | Condition::TargetDied)
                || effects.iter().any(|e| e.target() == Some(crate::effects::Target::Opponent))
        })
    }

    /// Effect `i` counting through every row, or `None` past the last (as
    /// `CardDef::effect_at`).
    pub fn effect_at(&self, i: usize) -> Option<crate::cards::EffectAt> {
        let mut start = 0;
        for (condition, effects) in &self.rows {
            let end = start + effects.len();
            if i < end {
                return Some(crate::cards::EffectAt { effect: effects[i - start], condition: *condition, row_start: i == start, row_end: end });
            }
            start = end;
        }
        None
    }
}

/// A potion's effect at multiple `k` (Sacred Bark): every amount times
/// `k`, a pack power's amount, random hits' amounts and a pick's count too
/// (Liquid Memories returns 2). `k` 1 leaves it.
pub fn scaled_effect(e: Effect, k: i16) -> Effect {
    match e {
        _ if k == 1 => e,
        Effect::Pick { kind, n, exact, free, of, copies } => Effect::Pick { kind, n: n.saturating_mul(k as u8), exact, free, of, copies },
        Effect::PlayTop { n, exhaust } => Effect::PlayTop { n: n.saturating_mul(k as u8), exhaust },
        Effect::ApplyPack { power, amount, target } => Effect::ApplyPack { power, amount: amount * k, target },
        Effect::RandomDamage { amount, hits } => Effect::RandomDamage { amount: amount * k, hits },
        Effect::RandomApply { power, amount, hits } => Effect::RandomApply { power, amount: amount * k, hits },
        e => e.scaled(k),
    }
}

/// Parses one entry: its id and spec. `pack` names a pack power loaded
/// before or earlier in this pack (`None` for the official file, which may
/// name official powers only). Errors name the potion.
pub fn parse_potion(v: &json::Value, pack: Option<&dyn Fn(&str) -> Option<u16>>) -> Result<(String, PotionSpec), String> {
    let id = v.get("id").and_then(json::Value::str).ok_or("potion without an id")?.to_string();
    let err = |x: String| format!("potion {id:?}: {x}");
    if let json::Value::Obj(kv) = v {
        if let Some((k, _)) = kv.iter().find(|(k, _)| !POTION_KEYS.contains(&k.as_str())) {
            return Err(err(format!("unknown key {k:?} (known: {POTION_KEYS:?})")));
        }
    } else {
        return Err(err("an entry must be an object".into()));
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
    let potency = match v.get("potency") {
        None => 0,
        Some(p) => p.int().filter(|n| (0..=i16::MAX as i64).contains(n)).ok_or_else(|| err(format!("potency must be an integer 0 or more, got {p:?}")))? as i16,
    };
    let none: &dyn Fn(&str) -> Option<u16> = &|_| None;
    let pack_power = pack.unwrap_or(none);
    let row = |es: Option<&json::Value>| -> Result<Vec<Effect>, String> {
        // `Escape` is the user's here (Smoke Bomb), not a card's.
        let items = es.map(json::Value::items).unwrap_or(&[]);
        let escape = |e: &json::Value| e.str() == Some("Escape");
        let rest = json::Value::Arr(items.iter().filter(|e| !escape(e)).cloned().collect());
        let (mut effects, mut gen) = crate::registry::card_effects(Some(&rest))?;
        for (i, _) in items.iter().enumerate().filter(|(_, e)| escape(e)) {
            effects.insert(i, Effect::Escape);
            gen.insert(i, None);
        }
        effects
            .into_iter()
            .zip(gen)
            .map(|(e, g)| match g {
                None => Ok(e),
                Some(g) => match (e, pack_power(&g)) {
                    (Effect::Apply { amount, target, .. }, Some(pi)) => Ok(Effect::ApplyPack { power: pi, amount, target }),
                    _ => Err(format!("applies {g:?}, not a loaded pack power in an Apply")),
                },
            })
            .collect()
    };
    let mut rows = vec![(Condition::Always, row(v.get("effects")).map_err(err)?)];
    for r in v.get("rows").map(json::Value::items).unwrap_or(&[]) {
        let condition = crate::registry::condition(r.get("condition")).map_err(err)?;
        if let Condition::CounterIs(_) | Condition::CounterAtMost(_) = condition {
            return Err(err(format!("a row's condition {condition:?} reads a relic's counter: a potion has none")));
        }
        rows.push((condition, row(r.get("effects")).map_err(err)?));
    }
    if rows.iter().all(|(_, es)| es.is_empty()) {
        return Err(err("no effects".into()));
    }
    if rows.iter().flat_map(|(_, es)| es).any(|e| matches!(e, Effect::MakeRandom { .. })) {
        return Err(err("MakeRandom runs only while a card resolves (colorless-cards spec)".into()));
    }
    // A potion with a trigger runs inside the HP loss that would kill the
    // player: one row of heals, nothing that pauses.
    let trigger = match v.get("trigger") {
        None => None,
        Some(t) if t.str() == Some("OwnerDied") => {
            if rows.len() > 1 {
                return Err(err("a potion with a trigger has effects only, no rows".into()));
            }
            if let Some(e) = rows[0].1.iter().find(|e| !matches!(e, Effect::Heal(_) | Effect::HealOf(_))) {
                return Err(err(format!("a potion with trigger OwnerDied heals only (it runs as the player would die), not {e:?}")));
            }
            Some(crate::hooks::Trigger::OwnerDied)
        }
        Some(t) => return Err(err(format!("trigger must be \"OwnerDied\" (the only trigger a potion takes), got {t:?}"))),
    };
    let fights = crate::relics::parse_fights(v.get("fights")).map_err(err)?;
    // A fight knows only whether it is a boss fight (any slot holds a
    // boss kind), and a potion is held back only there: `fights` names
    // hallway and elite (`FIGHT_KINDS` bits 0 and 1), boss optional.
    if fights & 3 != 3 {
        return Err(err("fights names hallway and elite together, boss optional (a fight tells only a boss fight from the rest)".into()));
    }
    Ok((id, PotionSpec { rarity, potency, rows, trigger, fights }))
}

/// Parses the official potions file: every entry, ids unique, official
/// powers only.
pub fn parse_official_potions(text: &str) -> Result<Vec<(String, PotionSpec)>, String> {
    let v = json::parse(text)?;
    crate::registry::file_version(&v).map_err(|e| format!("potions: {e}"))?;
    let mut out: Vec<(String, PotionSpec)> = Vec::new();
    for e in v.get("potions").map(json::Value::items).unwrap_or(&[]) {
        let (id, spec) = parse_potion(e, None)?;
        if out.iter().any(|(i, _)| *i == id) {
            return Err(format!("potion {id:?} twice in the file"));
        }
        out.push((id, spec));
    }
    Ok(out)
}

/// Potion slots a player has with no relic (Ascension 0); a held relic's
/// `potion_slots` adds to them (Potion Belt's 2).
pub const BASE_POTION_SLOTS: usize = 3;
/// The ascension level from which the player has one slot fewer (the
/// game's `AbstractPlayer`, A11).
pub const FEWER_SLOTS_FROM: u8 = 11;

/// The rarity roll of a random potion, out of 100 (the game's
/// `returnRandomPotion`: common below 65, uncommon below 90, else rare).
pub const RARITY_WEIGHTS: [u32; 3] = [65, 25, 10];

/// A potion pool (docs/extending.md "Pool or set"): the list the game
/// draws a random potion from, by rarity (`Rarity::ALL` order). An
/// `ObtainRandomPotions` names one by its index (`potion_pool`).
#[derive(Debug)]
pub struct PotionPool {
    /// The pack potion ids left out (`except`), as the file wrote them.
    pub except: &'static [&'static str],
    pub by_rarity: [&'static [PotionId]; 3],
}

impl PotionPool {
    /// Every potion it gives with its chance: its rarity's weight, shared
    /// alike among that rarity's potions.
    pub fn outcomes(&self) -> impl Iterator<Item = (PotionId, f64)> + '_ {
        self.by_rarity.iter().zip(RARITY_WEIGHTS).flat_map(|(ps, w)| ps.iter().map(move |&p| (p, w as f64 / 100.0 / ps.len() as f64)))
    }

    /// One potion as the game draws it: the rarity roll, then one of that
    /// rarity alike.
    pub fn sample(&self, rng: &mut crate::rng::Rng) -> PotionId {
        let mut roll = rng.below(100);
        let mut r = 0;
        while roll >= RARITY_WEIGHTS[r] {
            roll -= RARITY_WEIGHTS[r];
            r += 1;
        }
        let ps = self.by_rarity[r];
        ps[rng.below(ps.len() as u32) as usize]
    }

    /// Every potion, rarity by rarity.
    pub fn potions(&self) -> impl Iterator<Item = PotionId> + '_ {
        self.by_rarity.iter().flat_map(|ps| ps.iter().copied())
    }
}

/// Most potion pools one process holds (an index is a byte).
const POTION_POOL_CAPACITY: usize = 255;

static POTION_POOLS: [OnceLock<PotionPool>; POTION_POOL_CAPACITY] = [const { OnceLock::new() }; POTION_POOL_CAPACITY];

/// Potion pool `i` (`ObtainRandomPotions { pool }`).
pub fn potion_pool(i: u8) -> &'static PotionPool {
    POTION_POOLS[i as usize].get().expect("a made potion pool")
}

/// The index of the pool of these potions, made on first use: the same
/// lists give the same index (a pack loaded twice), as names are interned.
fn intern_pool(except: Vec<String>, by_rarity: [Vec<PotionId>; 3]) -> Result<u8, String> {
    static INDEX: OnceLock<Mutex<Vec<(Vec<String>, [Vec<PotionId>; 3])>>> = OnceLock::new();
    let mut t = INDEX.get_or_init(Default::default).lock().unwrap();
    if let Some(i) = t.iter().position(|(e, r)| *e == except && *r == by_rarity) {
        return Ok(i as u8);
    }
    let i = t.len();
    if i >= POTION_POOL_CAPACITY {
        return Err(format!("more than {POTION_POOL_CAPACITY} potion pools in this process"));
    }
    let pool = PotionPool {
        except: Box::leak(except.iter().map(|s| &*Box::leak(s.clone().into_boxed_str())).collect::<Vec<_>>().into_boxed_slice()),
        by_rarity: by_rarity.clone().map(|v| &*Box::leak(v.into_boxed_slice())),
    };
    POTION_POOLS[i].set(pool).expect("a fresh potion pool slot");
    t.push((except, by_rarity));
    Ok(i as u8)
}

thread_local! {
    /// The potions of the pack being loaded, (id, rarity) in file order,
    /// while `load_pack` parses its potions; `None` otherwise, so
    /// `ObtainRandomPotions` parses in a pack's potion only.
    static PACK_POTIONS: std::cell::RefCell<Option<Vec<(String, Rarity)>>> = const { std::cell::RefCell::new(None) };
}

/// Clears `PACK_POTIONS` when dropped (`load_pack` returning, whichever
/// way).
pub(crate) struct PackPotions;

impl PackPotions {
    /// Sets the pack's potions from its `"potions"` list (an entry with no
    /// id or an unknown rarity is left out: its own parse fails).
    pub(crate) fn set(entries: &[json::Value]) -> PackPotions {
        let v = entries
            .iter()
            .filter_map(|p| {
                let id = p.get("id")?.str()?;
                let r = p.get("rarity")?.str()?;
                Some((id.to_string(), Rarity::ALL.into_iter().find(|x| x.name() == r)?))
            })
            .collect();
        PACK_POTIONS.with(|p| *p.borrow_mut() = Some(v));
        PackPotions
    }
}

impl Drop for PackPotions {
    fn drop(&mut self) {
        PACK_POTIONS.with(|p| *p.borrow_mut() = None);
    }
}

/// `ObtainRandomPotions` with its fields `f` (`except`: pack potion ids):
/// its pool is the pack's potions less `except`
/// (docs/specs/act1-singles.md section 5). Outside a pack's potion, an
/// `except` naming no potion of the pack, or a rarity with no potion left
/// (the game would draw forever) is an error.
pub(crate) fn parse_obtain_random(f: Option<&json::Value>) -> Result<Effect, String> {
    let pack = PACK_POTIONS.with(|p| p.borrow().clone()).ok_or("ObtainRandomPotions is a pack potion's effect only")?;
    let mut except = Vec::new();
    if let Some(e) = f.and_then(|f| f.get("except")) {
        if !matches!(e, json::Value::Arr(_)) {
            return Err(format!("ObtainRandomPotions except: a list of potion ids, got {e:?}"));
        }
        for x in e.items() {
            let id = x.str().ok_or_else(|| format!("ObtainRandomPotions except: a potion id, got {x:?}"))?;
            if !pack.iter().any(|(i, _)| i == id) {
                return Err(format!("ObtainRandomPotions except: {id:?} is not a potion of this pack"));
            }
            except.push(id.to_string());
        }
    }
    let mut by_rarity: [Vec<PotionId>; 3] = Default::default();
    for (id, r) in pack.iter().filter(|(i, _)| !except.contains(i)) {
        by_rarity[*r as usize].push(potion_id(&format!("gen:{id}"))?);
    }
    if let Some(r) = Rarity::ALL.into_iter().find(|&r| by_rarity[r as usize].is_empty()) {
        return Err(format!("ObtainRandomPotions: no {} potion in its pool (this pack's potions less except)", r.name()));
    }
    Ok(Effect::ObtainRandomPotions { pool: intern_pool(except, by_rarity)? })
}
