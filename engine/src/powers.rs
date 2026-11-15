//! Powers (buffs and debuffs) as a fixed array of amounts, one per kind.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum Power {
    Strength,
    Dexterity,
    Vulnerable,
    Weak,
    Frail,
    Ritual,
    /// Gains this much block the first time it takes unblocked, non-lethal
    /// attack damage, then is removed (lice).
    CurlUp,
    /// Gains this much Strength whenever the player plays a Skill (Gremlin Nob).
    Enrage,
    /// Gains this much block at the end of its owner's turn.
    Metallicize,
    /// Negates the next this-many debuffs.
    Artifact,
    /// On death, applies this much Vulnerable to the player (Fungi Beast).
    SporeCloud,
    /// Loses this much Strength at the end of the player's turn (Flex).
    LoseStrength,
    /// At the start of its turn, a monster loses this much HP (ignoring
    /// block), then Poison drops by 1.
    Poison,
    // The player's power cards (triggers and conditions, step 5).
    /// At the end of the player's turn, lose this much HP (one per Combust
    /// played; the damage is `CombustDamage`).
    Combust,
    /// At the end of the player's turn, deal this much non-attack damage to
    /// every enemy (the sum of the Combusts played).
    CombustDamage,
    /// At the start of the player's turn, after the draw: lose this much HP
    /// and draw this many cards.
    Brutality,
    /// Gains this much Strength whenever the player loses HP from a card.
    Rupture,
    /// Gains this much Strength at the start of the player's turn.
    DemonForm,
    /// Gains this much block whenever the player plays an Attack; removed at
    /// the end of the turn.
    Rage,
    // Act-1 bosses (The Guardian).
    /// HP The Guardian can still lose before it switches to Defensive mode
    /// (`CombatState::lost_hp`).
    ModeShift,
    /// The player takes this much damage after each Attack they play.
    SharpHide,
    // Static modifiers as data (rules-engine spec 4), proving content.
    /// The player's Shivs deal this much more damage (Accuracy).
    Accuracy,
    /// This much more attack damage while the owner's HP is at most half
    /// (the Red Skull relic as a power; no card grants it).
    RedSkull,
    // Replacement hooks (rules-engine spec 5), proving content.
    /// Damage and HP loss the owner takes become at most 1; one stack off
    /// per round (Wraith Form).
    Intangible,
    /// Loses this much Dexterity at the end of the player's turn (Wraith Form).
    WraithForm,
    /// Deals this much non-attack damage to whoever attacks the owner, per
    /// hit (Caltrops).
    Thorns,
    // Decision points (rules-engine spec 6), proving content.
    /// The next this-many Skills played this turn are played twice (Burst).
    Burst,
    // Monster modifiers for the mutated-monsters bench (stage B), proving
    // content: no official card or monster has them.
    /// The owner's attack damage is multiplied by 4/5 while it has stacks
    /// (once, not per stack, like Weak).
    DamageDown,
    /// Each attack hit of the owner that makes its target lose HP applies
    /// this much Weak to the target (unblocked hits only).
    WeakOnHit,
    /// A monster's attacks land as twice the hits at half the base damage,
    /// rounded down (before Strength).
    SplitHits,
    // Reserved slots for generated powers (registry-lite): what a slot does
    // comes from the combat's binding (`registry::Binding`).
    Gen0,
    Gen1,
    Gen2,
    Gen3,
    Gen4,
    Gen5,
    Gen6,
    Gen7,
    Gen8,
    Gen9,
    Gen10,
    Gen11,
    Gen12,
    Gen13,
    Gen14,
    Gen15,
    Gen16,
    Gen17,
    Gen18,
    Gen19,
    Gen20,
    Gen21,
    Gen22,
    Gen23,
}

impl Power {
    pub const ALL: [Power; 30] = [
        Power::Strength,
        Power::Dexterity,
        Power::Vulnerable,
        Power::Weak,
        Power::Frail,
        Power::Ritual,
        Power::CurlUp,
        Power::Enrage,
        Power::Metallicize,
        Power::Artifact,
        Power::SporeCloud,
        Power::LoseStrength,
        Power::Poison,
        Power::Combust,
        Power::CombustDamage,
        Power::Brutality,
        Power::Rupture,
        Power::DemonForm,
        Power::Rage,
        Power::ModeShift,
        Power::SharpHide,
        Power::Accuracy,
        Power::RedSkull,
        Power::Intangible,
        Power::WraithForm,
        Power::Thorns,
        Power::Burst,
        Power::DamageDown,
        Power::WeakOnHit,
        Power::SplitHits,
    ];

    /// The reserved generated-power slots, in slot order.
    pub const GEN: [Power; crate::registry::POWER_SLOTS] = [
        Power::Gen0, Power::Gen1, Power::Gen2, Power::Gen3, Power::Gen4, Power::Gen5,
        Power::Gen6, Power::Gen7, Power::Gen8, Power::Gen9, Power::Gen10, Power::Gen11,
        Power::Gen12, Power::Gen13, Power::Gen14, Power::Gen15, Power::Gen16, Power::Gen17,
        Power::Gen18, Power::Gen19, Power::Gen20, Power::Gen21, Power::Gen22, Power::Gen23,
    ];

    /// Official powers, then the reserved slots: every power a state can hold.
    pub const ALL_WITH_SLOTS: [Power; NUM_POWERS] = {
        let mut a = [Power::Strength; NUM_POWERS];
        let mut i = 0;
        while i < NUM_POWERS {
            a[i] = if i < NUM_OFFICIAL_POWERS { Power::ALL[i] } else { Power::GEN[i - NUM_OFFICIAL_POWERS] };
            i += 1;
        }
        a
    };

    /// Debuffs that lose one stack at the end of each round (the
    /// counterfactual reader's countdown; play reads each power's row).
    pub fn is_duration_debuff(self) -> bool {
        matches!(self, Power::Vulnerable | Power::Weak | Power::Frail)
    }
}

/// Official powers (`Power::ALL`); the codec and every name list use these.
pub const NUM_OFFICIAL_POWERS: usize = Power::ALL.len();
/// Official powers plus the reserved slots: the state's size.
pub const NUM_POWERS: usize = NUM_OFFICIAL_POWERS + Power::GEN.len();
const _: () = assert!(NUM_POWERS <= 64, "Powers' held mask is 64 bits");

/// Powers one creature holds inline (a census of 1.04M search states saw 6
/// on the player, 4 on a monster). The game has no limit (an `ArrayList`):
/// past these, the first `KEPT_INLINE` entries stay inline and the rest
/// live in an interned tail.
pub const POWERS_INLINE: usize = 12;

/// Entries kept inline once a creature holds more than `POWERS_INLINE`
/// powers: the last two inline entries hold the tail's handle.
const KEPT_INLINE: usize = POWERS_INLINE - 2;

/// `just_applied` marks a power that skips its next end-of-round tick and
/// whose hooks don't fire until then: a debuff a monster put on the player
/// during the monster turn, or Ritual on the turn a monster gains it.
///
/// The amounts are a short list sorted by power, amount != 0, unused
/// entries zero; `held` has one bit per held power, so a power's entry is
/// the number of held powers below it. Past `POWERS_INLINE` held powers,
/// the entries from `KEPT_INLINE` on are a list interned process-wide by
/// value (as `Binding`'s slot sets), its handle in the last two inline
/// entries: `Powers` keeps its size, `Copy` and 4-byte alignment. Equal
/// contents are equal bytes (derived `Eq`/`Hash`), and the size doesn't
/// grow with the number of powers that exist.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Default)]
pub struct Powers {
    amounts: [i16; POWERS_INLINE],
    /// Held powers (amount != 0), power `p` at bit `p`, as two words like
    /// `just_applied`.
    held: [u32; 2],
    /// One bit per power, as two words: a `u64` would align the whole
    /// block to 8 bytes and slow `CombatState::clone` (measured).
    pub(crate) just_applied: [u32; 2],
}

const TAIL_CHUNK: usize = 4096;
/// Distinct tails one process can intern (each is a list of amounts past
/// `POWERS_INLINE`; few occur, as the tail is mostly pack powers whose
/// amounts rarely change).
const TAIL_CAPACITY: usize = 1 << 22;
/// Tail `h` at `h - 1`, read without a lock (as `registry::SLOT_SETS`).
static TAILS: [OnceLock<Box<[OnceLock<&'static [i16]>]>>; TAIL_CAPACITY / TAIL_CHUNK] =
    [const { OnceLock::new() }; TAIL_CAPACITY / TAIL_CHUNK];
static TAIL_INDEX: OnceLock<Mutex<HashMap<&'static [i16], u32>>> = OnceLock::new();

fn tail_cell(i: usize) -> &'static OnceLock<&'static [i16]> {
    let chunk = TAILS[i / TAIL_CHUNK].get_or_init(|| (0..TAIL_CHUNK).map(|_| OnceLock::new()).collect());
    &chunk[i % TAIL_CHUNK]
}

/// The entries a tail handle names (none for 0).
#[cold]
#[inline(never)]
fn tail_of(h: u32) -> &'static [i16] {
    if h == 0 {
        return &[];
    }
    tail_cell(h as usize - 1).get().expect("an interned power tail")
}

/// The handle of these entries, interning them on first sight; 0 for none.
/// Memory grows with the distinct tails a process meets, never freed (as
/// changed copies).
fn intern_tail(t: &[i16]) -> u32 {
    if t.is_empty() {
        return 0;
    }
    let mut index = TAIL_INDEX.get_or_init(Mutex::default).lock().unwrap();
    if let Some(&h) = index.get(t) {
        return h;
    }
    let i = index.len();
    assert!(i < TAIL_CAPACITY, "{TAIL_CAPACITY} distinct power tails (TAIL_CAPACITY) interned in one process");
    let s: &'static [i16] = Box::leak(t.into());
    let _ = tail_cell(i).set(s);
    index.insert(s, i as u32 + 1);
    i as u32 + 1
}

/// The dense form (an amount per power), showing the reserved
/// generated-power slots only when one is used, so debug text (the codec
/// golden file) reads as it did before the slots.
impl std::fmt::Debug for Powers {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut dense = [0i16; NUM_POWERS];
        for (p, a) in self.iter() {
            dense[p as usize] = a;
        }
        let used = dense[NUM_OFFICIAL_POWERS..].iter().any(|&a| a != 0);
        let amounts = if used { &dense[..] } else { &dense[..NUM_OFFICIAL_POWERS] };
        f.debug_struct("Powers").field("amounts", &amounts).field("just_applied", &self.just_applied_mask()).finish()
    }
}

impl Powers {
    #[inline]
    pub(crate) fn held_mask(&self) -> u64 {
        self.held[0] as u64 | (self.held[1] as u64) << 32
    }

    #[inline]
    fn set_held(&mut self, m: u64) {
        self.held = [m as u32, (m >> 32) as u32];
    }

    /// The entry of `p` (held or not): the number of held powers below it.
    #[inline]
    fn rank(&self, p: Power) -> usize {
        (self.held_mask() & ((1u64 << p as u32) - 1)).count_ones() as usize
    }

    /// Held powers.
    #[inline]
    fn len(&self) -> usize {
        self.held_mask().count_ones() as usize
    }

    /// Entry `i` (below the number held), inline or in the tail.
    #[inline]
    fn entry(&self, i: usize) -> i16 {
        if i < KEPT_INLINE { self.amounts[i] } else { self.entry_past(i) }
    }

    /// Entry `i` from `KEPT_INLINE` on (out of line: `get` is inlined
    /// everywhere, and few creatures hold that many powers).
    #[inline(never)]
    fn entry_past(&self, i: usize) -> i16 {
        if self.len() <= POWERS_INLINE { self.amounts[i] } else { tail_of(self.tail_handle())[i - KEPT_INLINE] }
    }

    /// The tail's handle, past `POWERS_INLINE` held powers.
    fn tail_handle(&self) -> u32 {
        self.amounts[KEPT_INLINE] as u16 as u32 | (self.amounts[KEPT_INLINE + 1] as u16 as u32) << 16
    }

    /// Every entry, inline and tail: the path for creatures past
    /// `POWERS_INLINE` powers.
    fn entries(&self) -> Vec<i16> {
        let len = self.len();
        if len <= POWERS_INLINE {
            return self.amounts[..len].to_vec();
        }
        let mut v = self.amounts[..KEPT_INLINE].to_vec();
        v.extend_from_slice(tail_of(self.tail_handle()));
        v
    }

    /// Stores `v` as the entries (`held` is the caller's): unused inline
    /// entries zero; past `POWERS_INLINE` entries, the tail interned.
    fn set_entries(&mut self, v: &[i16]) {
        self.amounts = [0; POWERS_INLINE];
        if v.len() <= POWERS_INLINE {
            self.amounts[..v.len()].copy_from_slice(v);
            return;
        }
        self.amounts[..KEPT_INLINE].copy_from_slice(&v[..KEPT_INLINE]);
        let h = intern_tail(&v[KEPT_INLINE..]);
        self.amounts[KEPT_INLINE] = h as u16 as i16;
        self.amounts[KEPT_INLINE + 1] = (h >> 16) as u16 as i16;
    }

    #[inline]
    pub fn get(&self, p: Power) -> i16 {
        if self.held_mask() & 1 << p as u32 == 0 {
            return 0;
        }
        self.entry(self.rank(p))
    }

    pub fn add(&mut self, p: Power, n: i16) {
        if n == 0 {
            return;
        }
        let (m, bit, i) = (self.held_mask(), 1u64 << p as u32, self.rank(p));
        if m & bit != 0 {
            // A stopgap past i16 for powers without the game's cap (their
            // row's `cap`; the game holds an int): saturate, don't wrap.
            if i >= KEPT_INLINE && m.count_ones() as usize > POWERS_INLINE {
                let mut v = self.entries();
                v[i] = v[i].saturating_add(n);
                if v[i] == 0 {
                    v.remove(i);
                    self.set_held(m & !bit);
                }
                self.set_entries(&v);
                return;
            }
            self.amounts[i] = self.amounts[i].saturating_add(n);
            if self.amounts[i] == 0 {
                self.delete(i, bit);
            }
            return;
        }
        let len = m.count_ones() as usize;
        if len >= POWERS_INLINE {
            let mut v = self.entries();
            v.insert(i, n);
            self.set_entries(&v);
        } else {
            for j in (i..len).rev() {
                self.amounts[j + 1] = self.amounts[j];
            }
            self.amounts[i] = n;
        }
        self.set_held(m | bit);
    }

    fn delete(&mut self, i: usize, bit: u64) {
        let m = self.held_mask();
        let len = m.count_ones() as usize;
        if len > POWERS_INLINE {
            let mut v = self.entries();
            v.remove(i);
            self.set_entries(&v);
        } else {
            for j in i..len - 1 {
                self.amounts[j] = self.amounts[j + 1];
            }
            self.amounts[len - 1] = 0;
        }
        self.set_held(m & !bit);
    }

    /// Removes the power entirely.
    pub fn clear(&mut self, p: Power) {
        let bit = 1u64 << p as u32;
        if self.held_mask() & bit != 0 {
            self.delete(self.rank(p), bit);
        }
        self.clear_just_applied(p);
    }

    /// Lowers it by `n`, as the game's `ReducePowerAction`: nothing when it
    /// isn't held, removed when `n` is at least its amount.
    pub fn reduce(&mut self, p: Power, n: i16) {
        let held = self.get(p);
        if held == 0 {
            return;
        }
        if n >= held {
            self.clear(p);
        } else {
            self.add(p, -n);
        }
    }

    /// Held powers (amount != 0) in power order.
    pub fn iter(&self) -> impl Iterator<Item = (Power, i16)> + '_ {
        let mut m = self.held_mask();
        (0..m.count_ones() as usize).map(move |i| {
            let p = m.trailing_zeros() as usize;
            m &= m - 1;
            (Power::ALL_WITH_SLOTS[p], self.entry(i))
        })
    }

    pub fn just_applied(&self, p: Power) -> bool {
        self.just_applied[p as usize / 32] & (1 << (p as u32 % 32)) != 0
    }

    pub fn set_just_applied(&mut self, p: Power) {
        self.just_applied[p as usize / 32] |= 1 << (p as u32 % 32);
    }

    fn clear_just_applied(&mut self, p: Power) {
        self.just_applied[p as usize / 32] &= !(1 << (p as u32 % 32));
    }

    /// Every power's `just_applied` bit, power `p` at bit `p`.
    pub fn just_applied_mask(&self) -> u64 {
        self.just_applied[0] as u64 | (self.just_applied[1] as u64) << 32
    }

    pub fn from_parts(amounts: [i16; NUM_POWERS], mask: u64) -> Powers {
        let mut p = Powers { just_applied: [mask as u32, (mask >> 32) as u32], ..Powers::default() };
        for (i, &a) in amounts.iter().enumerate() {
            p.add(Power::ALL_WITH_SLOTS[i], a);
        }
        p
    }

    /// After the round's `RoundEnd` hooks (the debuff countdowns): every
    /// power skipped this round (its hooks don't fire while `just_applied`)
    /// is skipped no longer.
    pub fn clear_round_flags(&mut self) {
        if self.just_applied == [0; 2] {
            return;
        }
        // Clearing a bit that isn't set changes nothing.
        let mut m = self.held_mask();
        let mut i = 0;
        while m != 0 {
            let p = m.trailing_zeros();
            if self.entry(i) > 0 {
                self.just_applied[p as usize / 32] &= !(1 << (p % 32));
            }
            m &= m - 1;
            i += 1;
        }
    }
}
