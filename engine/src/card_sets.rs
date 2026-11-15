//! Named card sets (`configs/card-sets.json`): the pools a training draws
//! from, the held-out set and the test sets. A training decision, not
//! content: the file isn't a rules file (not in the solved DB's
//! fingerprint or the golden games).

use std::sync::OnceLock;

use crate::cards::CardId;
use crate::registry::json;

/// The sets file, compiled in.
pub const SETS_FILE: &str = include_str!("../../configs/card-sets.json");

/// Named sets in file order, each resolved to card ids.
pub type Sets = Vec<(String, Vec<CardId>)>;

/// Parses a sets file: each set is a list of base card names; a name brings
/// its `+` card when one exists, and a set's ids come in card order
/// (`CardId::all()`), whatever order the file lists them in.
pub fn parse(text: &str) -> Result<Sets, String> {
    let v = json::parse(text)?;
    match v.get("version") {
        Some(json::Value::Num(n)) if *n == 1.0 => {}
        x => return Err(format!("card sets: version {x:?}, 1 expected")),
    }
    let Some(json::Value::Obj(sets)) = v.get("sets") else {
        return Err("card sets: no \"sets\" object".into());
    };
    let mut out = Vec::new();
    for (set, names) in sets {
        let err = |x: String| format!("card set {set:?}: {x}");
        let json::Value::Arr(names) = names else {
            return Err(err("not a list of card names".into()));
        };
        let mut members = vec![false; CardId::all().count()];
        let mut seen: Vec<&str> = Vec::new();
        for n in names {
            let n = n.str().ok_or_else(|| err("a card name must be a string".into()))?;
            if n.ends_with('+') {
                return Err(err(format!("{n:?} is an upgrade (list the base card; it brings its + card)")));
            }
            if seen.contains(&n) {
                return Err(err(format!("{n:?} twice")));
            }
            seen.push(n);
            let id = CardId::from_name(n).ok_or_else(|| err(format!("{n:?} is no official card")))?;
            members[id.0 as usize] = true;
            let up = format!("{n}+");
            if let Some(u) = CardId::from_name(&up) {
                members[u.0 as usize] = true;
            }
        }
        out.push((set.clone(), CardId::all().filter(|c| members[c.0 as usize]).collect()));
    }
    Ok(out)
}

/// The compiled-in sets, resolved on first use. A bad file is a build bug:
/// it panics naming the set and the card.
fn sets() -> &'static Sets {
    static S: OnceLock<Sets> = OnceLock::new();
    S.get_or_init(|| parse(SETS_FILE).unwrap_or_else(|e| panic!("configs/card-sets.json: {e}")))
}

/// A set's cards in card order, base and upgraded, or `None` for a name the
/// file doesn't have.
pub fn get(name: &str) -> Option<&'static [CardId]> {
    sets().iter().find(|(n, _)| n == name).map(|(_, ids)| ids.as_slice())
}

/// The sets' names, in file order.
pub fn names() -> impl Iterator<Item = &'static str> {
    sets().iter().map(|(n, _)| n.as_str())
}
