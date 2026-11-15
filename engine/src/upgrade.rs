//! Card upgrades as data (docs/specs/card-upgrades.md): a card's entry says
//! what each upgrade changes, as paths to its numbers and keywords. Level 0
//! and 1 are a card's id pair; level 2 and up are per-copy variants
//! (`registry::Overrides::level`).

use crate::cards::CardId;
use crate::effects::{Amount, Effect};

/// Highest level any card reaches (a byte); `max_level: null` means this.
pub const LEVEL_CAP: u8 = 255;

/// An upgrade's number change, an expression of `n`, the level being
/// reached: a sum of products of integer constants and `n`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Expr(Vec<Vec<Factor>>);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Factor {
    Const(i64),
    N,
}

impl Expr {
    pub fn constant(k: i64) -> Expr {
        Expr(vec![vec![Factor::Const(k)]])
    }

    /// Integer constants, `n`, `+` and `*` with the usual precedence;
    /// spaces anywhere. Nothing else (no parentheses, `-`, `/` or names).
    pub fn parse(s: &str) -> Result<Expr, String> {
        let bad = || format!("upgrade expression {s:?}: only integers, n, + and * are allowed");
        let mut terms = Vec::new();
        for term in s.split('+') {
            let mut factors = Vec::new();
            for f in term.split('*') {
                let f = f.trim();
                factors.push(match f {
                    "n" => Factor::N,
                    _ if !f.is_empty() && f.bytes().all(|b| b.is_ascii_digit()) => Factor::Const(f.parse().map_err(|_| bad())?),
                    _ => return Err(bad()),
                });
            }
            terms.push(factors);
        }
        Ok(Expr(terms))
    }

    /// As an entry writes it: a bare number for a constant, else the
    /// expression as a string.
    pub fn write(&self) -> String {
        if let [t] = &self.0[..] {
            if let [Factor::Const(k)] = t[..] {
                return k.to_string();
            }
        }
        let f = |f: &Factor| if let Factor::Const(k) = f { k.to_string() } else { "n".to_string() };
        let terms: Vec<String> = self.0.iter().map(|t| t.iter().map(f).collect::<Vec<_>>().join(" * ")).collect();
        format!("{:?}", terms.join(" + "))
    }

    /// The value at level `n`.
    pub fn at(&self, n: i64) -> i64 {
        self.0
            .iter()
            .map(|t| t.iter().map(|f| if let Factor::Const(k) = *f { k } else { n }).fold(1i64, i64::saturating_mul))
            .fold(0i64, i64::saturating_add)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Keyword {
    Exhaust,
    Ethereal,
    Innate,
    Retain,
}

impl Keyword {
    pub const ALL: [Keyword; 4] = [Keyword::Exhaust, Keyword::Ethereal, Keyword::Innate, Keyword::Retain];

    pub fn name(self) -> &'static str {
        match self {
            Keyword::Exhaust => "exhaust",
            Keyword::Ethereal => "ethereal",
            Keyword::Innate => "innate",
            Keyword::Retain => "retain",
        }
    }
}

/// Which effect list of a card: the on-play row is row 0, a conditional
/// row `r` is row `r + 1`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Section {
    Row(usize),
    TurnEnd,
    Exhausted,
}

/// One number or keyword of a card entry.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Path {
    Cost,
    Keyword(Keyword),
    /// A number inside effect `i` of `section`: the effect's pack name
    /// (`Damage`) and its field (`amount`, `amount.k`; empty for a
    /// bare-number effect such as `Block`).
    Number { section: Section, i: usize, effect: String, field: String },
}

impl Path {
    /// `cost`, a keyword, `effects.<i>.<Effect>[.<field>]`,
    /// `rows.<r>.effects.<i>...`, `turn_end.<i>...` or `exhausted.<i>...`.
    pub fn parse(s: &str) -> Result<Path, String> {
        let parts: Vec<&str> = s.split('.').collect();
        let bad = || format!("upgrade path {s:?} names no number or keyword of a card");
        let index = |p: &str| p.parse::<usize>().map_err(|_| bad());
        if let [one] = parts[..] {
            if one == "cost" {
                return Ok(Path::Cost);
            }
            return Keyword::ALL.into_iter().find(|k| k.name() == one).map(Path::Keyword).ok_or_else(bad);
        }
        let (section, rest) = match parts[..] {
            ["effects", i, ref rest @ ..] => ((Section::Row(0), index(i)?), rest),
            ["rows", r, "effects", i, ref rest @ ..] => ((Section::Row(index(r)? + 1), index(i)?), rest),
            ["turn_end", i, ref rest @ ..] => ((Section::TurnEnd, index(i)?), rest),
            ["exhausted", i, ref rest @ ..] => ((Section::Exhausted, index(i)?), rest),
            _ => return Err(bad()),
        };
        let [effect, field @ ..] = rest else { return Err(bad()) };
        Ok(Path::Number { section: section.0, i: section.1, effect: effect.to_string(), field: field.join(".") })
    }

    pub fn write(&self) -> String {
        match self {
            Path::Cost => "cost".into(),
            Path::Keyword(k) => k.name().into(),
            Path::Number { section, i, effect, field } => {
                let s = match section {
                    Section::Row(0) => format!("effects.{i}"),
                    Section::Row(r) => format!("rows.{}.effects.{i}", r - 1),
                    Section::TurnEnd => format!("turn_end.{i}"),
                    Section::Exhausted => format!("exhausted.{i}"),
                };
                if field.is_empty() { format!("{s}.{effect}") } else { format!("{s}.{effect}.{field}") }
            }
        }
    }
}

/// What an upgrade does to one path.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Change {
    /// A number: this is added at each upgrade, `n` the level reached.
    Add(Expr),
    /// A keyword: its value from level 1 on.
    Set(bool),
}

/// A card's upgrade: its changes, and the `AddCard` effects whose added
/// card takes the played card's level (`match_level`).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Upgrade {
    pub changes: Vec<(Path, Change)>,
    pub match_level: Vec<(Section, usize)>,
}

/// The parts of a card an upgrade changes. `cost` is the raw cost (-1 X,
/// -2 unplayable).
#[derive(Clone, Debug, PartialEq)]
pub struct Parts {
    pub cost: i8,
    pub keywords: [bool; 4],
    pub rows: Vec<Vec<Effect>>,
    pub turn_end: Vec<Effect>,
    pub exhausted: Vec<Effect>,
}

impl Parts {
    fn section(&mut self, s: Section) -> Option<&mut Vec<Effect>> {
        match s {
            Section::Row(r) => self.rows.get_mut(r),
            Section::TurnEnd => Some(&mut self.turn_end),
            Section::Exhausted => Some(&mut self.exhausted),
        }
    }

    pub fn keyword(&self, k: Keyword) -> bool {
        self.keywords[k as usize]
    }
}

/// A number field of an effect, in its engine type.
pub enum Num<'a> {
    I16(&'a mut i16),
    I8(&'a mut i8),
    U8(&'a mut u8),
    /// A fraction's bottom (`amount.per`): at least 1.
    Per(&'a mut i16),
    /// A true / false field (`CostAtMost.combat`): an upgrade sets it
    /// (`Change::Set`), never adds to it.
    Bool(&'a mut bool),
}

impl Num<'_> {
    fn get(&self) -> i64 {
        match self {
            Num::I16(x) | Num::Per(x) => **x as i64,
            Num::I8(x) => **x as i64,
            Num::U8(x) => **x as i64,
            Num::Bool(x) => **x as i64,
        }
    }

    /// Sets a true / false field; false for a number.
    fn set_flag(&mut self, b: bool) -> bool {
        match self {
            Num::Bool(x) => {
                **x = b;
                true
            }
            _ => false,
        }
    }

    /// Sets the value if it fits the field's type.
    fn set(&mut self, v: i64) -> bool {
        match self {
            Num::I16(x) => i16::try_from(v).map(|v| **x = v).is_ok(),
            Num::I8(x) => i8::try_from(v).map(|v| **x = v).is_ok(),
            Num::U8(x) => u8::try_from(v).map(|v| **x = v).is_ok(),
            Num::Per(x) => i16::try_from(v).ok().filter(|&v| v >= 1).map(|v| **x = v).is_some(),
            // Not a number: only `Change::Set` writes it.
            Num::Bool(_) => false,
        }
    }
}

/// An effect's name in a content pack (`ApplyPack` writes as `Apply`).
pub fn effect_name(e: &Effect) -> &'static str {
    match e {
        Effect::Damage { .. } => "Damage",
        Effect::PlainDamage { .. } => "PlainDamage",
        Effect::CapHp { .. } => "CapHp",
        Effect::ScaledDamage { .. } => "ScaledDamage",
        Effect::RandomDamage { .. } => "RandomDamage",
        Effect::RandomApply { .. } => "RandomApply",
        Effect::RolledAttack => "RolledAttack",
        Effect::Block(_) => "Block",
        Effect::BlockAlly(_) => "BlockAlly",
        Effect::BlockOf(_) => "BlockOf",
        Effect::ScaledBlock { .. } => "ScaledBlock",
        Effect::ExhaustHand { .. } => "ExhaustHand",
        Effect::ExhaustRandom => "ExhaustRandom",
        Effect::ZeroCostRandom => "ZeroCostRandom",
        Effect::ZeroCostRandomTurn => "ZeroCostRandomTurn",
        Effect::UpgradeRandom => "UpgradeRandom",
        Effect::CostAtMost { .. } => "CostAtMost",
        Effect::TakeRandomFromDraw { .. } => "TakeRandomFromDraw",
        Effect::Draw(_) => "Draw",
        Effect::RandomizeCost(_) => "RandomizeCost",
        Effect::GainEnergy(_) => "GainEnergy",
        Effect::LoseHp(_) => "LoseHp",
        Effect::LoseHpOf(_) => "LoseHpOf",
        Effect::ApplyAsMonster { .. } => "ApplyAsMonster",
        Effect::AddCopy { .. } => "AddCopy",
        Effect::Heal(_) => "Heal",
        Effect::GainMaxHp(_) => "GainMaxHp",
        Effect::HealOf(_) => "HealOf",
        Effect::WinHeal(_) => "WinHeal",
        Effect::Apply { .. } | Effect::ApplyPack { .. } => "Apply",
        Effect::ApplyOf { .. } => "ApplyOf",
        Effect::AddCard { .. } => "AddCard",
        Effect::Split => "Split",
        Effect::Escape => "Escape",
        Effect::RemoveSelf => "RemoveSelf",
        Effect::ReduceSelf(_) => "ReduceSelf",
        Effect::Pick { .. } => "Pick",
        Effect::PlayTop { .. } => "PlayTop",
        Effect::ReplayCard => "ReplayCard",
        Effect::GrowDamage(_) => "GrowDamage",
        Effect::UpgradeHand => "UpgradeHand",
        Effect::UpgradeAll => "UpgradeAll",
        Effect::ShuffleDiscardIntoDraw => "ShuffleDiscardIntoDraw",
        Effect::RemoveDebuffs => "RemoveDebuffs",
        Effect::DrawPicked => "DrawPicked",
        Effect::SetCounter(_) => "SetCounter",
        Effect::AddCounter(_) => "AddCounter",
        Effect::Discover { .. } => "Discover",
        Effect::MakeRandom { .. } => "MakeRandom",
        Effect::ObtainRandomPotions { .. } => "ObtainRandomPotions",
    }
}

/// `field` of an amount: `base`, `k` and `per`; an empty field is the base of a
/// constant amount (written as a bare number).
fn amount_field<'a>(a: &'a mut Amount, field: &str) -> Option<Num<'a>> {
    match field {
        "base" => Some(Num::I16(&mut a.base)),
        "k" => Some(Num::I16(&mut a.k)),
        "per" if a.of.is_some() => Some(Num::Per(&mut a.per)),
        "" if a.of.is_none() => Some(Num::I16(&mut a.base)),
        _ => None,
    }
}

/// The number `field` names in `e`, if `e` is the effect `name`.
pub fn number<'a>(e: &'a mut Effect, name: &str, field: &str) -> Option<Num<'a>> {
    if effect_name(e) != name {
        return None;
    }
    // An amount-typed field: `amount`, `amount.base`, `amount.k`, `amount.per`.
    let sub = |f: &str, of: &str| -> Option<String> {
        if f == of {
            Some(String::new())
        } else {
            f.strip_prefix(of).and_then(|r| r.strip_prefix('.')).map(str::to_string)
        }
    };
    match e {
        Effect::Damage { amount, hits, .. } | Effect::RandomDamage { amount, hits } | Effect::RandomApply { amount, hits, .. } => match field {
            "amount" => Some(Num::I16(amount)),
            "hits" => Some(Num::U8(hits)),
            _ => None,
        },
        Effect::PlainDamage { amount, .. } | Effect::Apply { amount, .. } | Effect::ApplyPack { amount, .. } => {
            (field == "amount").then_some(Num::I16(amount))
        }
        Effect::ScaledDamage { amount, hits, .. } => match (sub(field, "amount"), sub(field, "hits")) {
            (Some(f), _) => amount_field(amount, &f),
            (_, Some(f)) => amount_field(hits, &f),
            _ => None,
        },
        Effect::ScaledBlock { amount, times } => match field {
            "amount" => Some(Num::I16(amount)),
            f => amount_field(times, &sub(f, "times")?),
        },
        Effect::BlockOf(a) | Effect::HealOf(a) => amount_field(a, field),
        Effect::ApplyOf { amount, .. } => amount_field(amount, &sub(field, "amount")?),
        Effect::MakeRandom { n, .. } => amount_field(n, &sub(field, "n")?),
        Effect::Block(n) | Effect::LoseHp(n) | Effect::Heal(n) | Effect::WinHeal(n) | Effect::GainMaxHp(n) | Effect::GrowDamage(n) | Effect::ReduceSelf(n) => {
            field.is_empty().then_some(Num::I16(n))
        }
        Effect::Draw(n) => field.is_empty().then_some(Num::U8(n)),
        Effect::GainEnergy(n) => field.is_empty().then_some(Num::I8(n)),
        Effect::AddCard { n, .. } => (field == "n").then_some(Num::U8(n)),
        Effect::CostAtMost { cost, combat } => match field {
            "cost" => Some(Num::I8(cost)),
            "combat" => Some(Num::Bool(combat)),
            _ => None,
        },
        Effect::TakeRandomFromDraw { n, .. } => (field == "n").then_some(Num::U8(n)),
        Effect::Pick { n, copies, .. } => match field {
            "n" => Some(Num::U8(n)),
            "copies" => Some(Num::U8(copies)),
            _ => None,
        },
        _ => None,
    }
}

/// Every number field of `e`, as `number` names them (for writing an
/// upgrade from two definitions).
pub fn number_fields(e: &Effect) -> Vec<&'static str> {
    let amount = |a: &Amount, of: &'static [&'static str; 4]| -> Vec<&'static str> {
        if a.of.is_none() { vec![of[0]] } else { vec![of[1], of[2], of[3]] }
    };
    match e {
        Effect::Damage { .. } | Effect::RandomDamage { .. } | Effect::RandomApply { .. } => vec!["amount", "hits"],
        Effect::PlainDamage { .. } | Effect::Apply { .. } | Effect::ApplyPack { .. } => vec!["amount"],
        Effect::ScaledDamage { amount: a, hits, .. } => {
            let mut v = amount(a, &["amount", "amount.base", "amount.k", "amount.per"]);
            v.extend(amount(hits, &["hits", "hits.base", "hits.k", "hits.per"]));
            v
        }
        Effect::ScaledBlock { times, .. } => {
            let mut v = vec!["amount"];
            v.extend(amount(times, &["times", "times.base", "times.k", "times.per"]));
            v
        }
        Effect::BlockOf(a) | Effect::HealOf(a) => amount(a, &["", "base", "k", "per"]),
        Effect::ApplyOf { amount: a, .. } => amount(a, &["amount", "amount.base", "amount.k", "amount.per"]),
        Effect::MakeRandom { n, .. } => amount(n, &["n", "n.base", "n.k", "n.per"]),
        Effect::Block(_) | Effect::LoseHp(_) | Effect::Heal(_) | Effect::WinHeal(_) | Effect::GainMaxHp(_) | Effect::GrowDamage(_) | Effect::ReduceSelf(_) | Effect::Draw(_) | Effect::GainEnergy(_) => {
            vec![""]
        }
        Effect::AddCard { .. } => vec!["n"],
        Effect::CostAtMost { .. } => vec!["cost", "combat"],
        Effect::TakeRandomFromDraw { .. } => vec!["n"],
        Effect::Pick { kind: crate::effects::PickKind::CopyInHand, .. } => vec!["n", "copies"],
        Effect::Pick { .. } => vec!["n"],
        _ => vec![],
    }
}

/// The value of `path` in `p` (keywords as 0 / 1), or `None` if it names
/// nothing there.
pub fn get(p: &mut Parts, path: &Path) -> Option<i64> {
    match path {
        Path::Cost => Some(p.cost as i64),
        Path::Keyword(k) => Some(p.keyword(*k) as i64),
        Path::Number { section, i, effect, field } => number(p.section(*section)?.get_mut(*i)?, effect, field).map(|n| n.get()),
    }
}

/// The card one upgrade of official card `c` makes when a `match_level`
/// effect adds it: its `+` id if it has an upgrade (its pair holds a
/// different name), else itself.
pub fn official_upgraded(c: CardId) -> CardId {
    let names = crate::registry::official_card_names();
    let up = CardId(c.0 | 1);
    if !c.upgraded() && names[up.0 as usize] != names[c.0 as usize] { up } else { c }
}

impl Upgrade {
    /// Applies the upgrade to level `n` (from level `n - 1`): numbers add
    /// their change at `n` (cost floored at 0), keywords take their value,
    /// and at level 1 `match_level` effects add their card's upgrade.
    /// An error names the path that fails at `n`.
    pub fn step(&self, p: &mut Parts, n: u8) -> Result<(), String> {
        for (path, change) in &self.changes {
            let fail = |why: &str| format!("upgrade path {:?} at level {n}: {why}", path.write());
            match (path, change) {
                (Path::Cost, Change::Add(e)) => {
                    if p.cost < 0 {
                        return Err(fail("an X-cost or unplayable card's cost can't change"));
                    }
                    let v = (p.cost as i64 + e.at(n as i64)).max(0);
                    p.cost = i8::try_from(v).map_err(|_| fail("cost past the engine's range"))?;
                }
                (Path::Keyword(k), Change::Set(b)) => p.keywords[*k as usize] = *b,
                // A true / false field of an effect (`CostAtMost.combat`).
                (Path::Number { section, i, effect, field }, Change::Set(b)) => {
                    let mut num = p.section(*section).and_then(|s| s.get_mut(*i)).and_then(|x| number(x, effect, field)).ok_or_else(|| fail("names no field of the card"))?;
                    if !num.set_flag(*b) {
                        return Err(fail("a number takes an amount or an expression of n"));
                    }
                }
                (Path::Number { section, i, effect, field }, Change::Add(e)) => {
                    let mut num = p.section(*section).and_then(|s| s.get_mut(*i)).and_then(|x| number(x, effect, field)).ok_or_else(|| fail("names no number of the card"))?;
                    let v = num.get().saturating_add(e.at(n as i64));
                    if !num.set(v) {
                        return Err(fail(&format!("{v} is past the engine's range")));
                    }
                }
                (Path::Keyword(_), Change::Add(_)) => return Err(fail("a keyword takes true or false")),
                (_, Change::Set(_)) => return Err(fail("a number takes an amount or an expression of n")),
            }
        }
        if n == 1 {
            for &(section, i) in &self.match_level {
                match p.section(section).and_then(|s| s.get_mut(i)) {
                    Some(Effect::AddCard { card, .. }) => *card = official_upgraded(*card),
                    _ => return Err(format!("match_level on effect {i}, which is not an AddCard")),
                }
            }
        }
        Ok(())
    }

    /// `p` at level `to`, from level `from`.
    pub fn apply(&self, p: &Parts, from: u8, to: u8) -> Result<Parts, String> {
        let mut q = p.clone();
        for n in from + 1..=to {
            self.step(&mut q, n)?;
        }
        Ok(q)
    }

    /// The upgrade that takes `a` to `b` at level 1 and that a later level
    /// repeats (numbers by their difference, keywords set), or `None` if
    /// they differ in anything else. An `AddCard` that adds the upgrade of
    /// the card the other adds is a `match_level` effect.
    pub fn between(a: &Parts, b: &Parts) -> Option<Upgrade> {
        if a.rows.len() != b.rows.len() || a.rows.iter().zip(&b.rows).any(|(x, y)| x.len() != y.len()) {
            return None;
        }
        if a.turn_end.len() != b.turn_end.len() || a.exhausted.len() != b.exhausted.len() {
            return None;
        }
        let mut up = Upgrade::default();
        if a.cost != b.cost {
            if a.cost < 0 || b.cost < 0 {
                return None;
            }
            up.changes.push((Path::Cost, Change::Add(Expr::constant((b.cost - a.cost) as i64))));
        }
        for k in Keyword::ALL {
            if a.keyword(k) != b.keyword(k) {
                up.changes.push((Path::Keyword(k), Change::Set(b.keyword(k))));
            }
        }
        let sections: Vec<(Section, &Vec<Effect>, &Vec<Effect>)> = (0..a.rows.len())
            .map(|r| (Section::Row(r), &a.rows[r], &b.rows[r]))
            .chain([(Section::TurnEnd, &a.turn_end, &b.turn_end), (Section::Exhausted, &a.exhausted, &b.exhausted)])
            .collect();
        for (section, xs, ys) in sections {
            for (i, (x, y)) in xs.iter().zip(ys).enumerate() {
                if effect_name(x) != effect_name(y) {
                    return None;
                }
                if let (Effect::AddCard { card: c, .. }, Effect::AddCard { card: d, .. }) = (x, y) {
                    if c != d {
                        if official_upgraded(*c) != *d {
                            return None;
                        }
                        up.match_level.push((section, i));
                    }
                }
                for f in number_fields(x) {
                    let (mut x, mut y) = (*x, *y);
                    let name = effect_name(&x);
                    let (Some(u), Some(v)) = (number(&mut x, name, f).map(|n| n.get()), number(&mut y, name, f).map(|n| n.get())) else {
                        return None;
                    };
                    if u != v {
                        let path = Path::Number { section, i, effect: name.to_string(), field: f.to_string() };
                        let flag = matches!(number(&mut y, name, f), Some(Num::Bool(_)));
                        up.changes.push((path, if flag { Change::Set(v != 0) } else { Change::Add(Expr::constant(v - u)) }));
                    }
                }
            }
        }
        up.changes.sort_by_key(|(p, _)| p.write());
        // Anything the changes don't cover (targets, powers, piles,
        // quantities) must already be equal.
        (up.apply(a, 0, 1).ok()? == *b).then_some(up)
    }
}
