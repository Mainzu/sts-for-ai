//! Every content element has its words in `content/wording.json`
//! (docs/specs/element-wording.md): each name `registry::element_names()`
//! lists has an entry, the file names nothing else, every element the
//! content files use is listed, and every monster `code` has its text.

use std::collections::BTreeSet;
use std::path::Path;
use sts_engine::registry::{element_names, json, json::Value};

const WORDING: &str = include_str!("../../content/wording.json");

/// The entry at `family` / `name` (a second part, `CardPlayed.Owner`, reads
/// one level deeper).
fn entry<'a>(w: &'a Value, family: &str, name: &str) -> Option<&'a Value> {
    let mut v = w.get(family)?;
    for part in name.split('.') {
        v = v.get(part)?;
    }
    Some(v)
}

fn keys(v: &Value) -> Vec<&str> {
    match v {
        Value::Obj(kv) => kv.iter().map(|(k, _)| k.as_str()).collect(),
        _ => vec![],
    }
}

/// A `"Name"` or `{"Name": fields}` value.
fn variant(v: &Value) -> Option<(&str, Option<&Value>)> {
    match v {
        Value::Str(s) => Some((s, None)),
        Value::Obj(kv) if kv.len() == 1 => Some((kv[0].0.as_str(), Some(&kv[0].1))),
        _ => None,
    }
}

/// What a content file names, as (family, name).
#[derive(Default)]
struct Used(BTreeSet<(&'static str, String)>, BTreeSet<String>);

impl Used {
    fn add(&mut self, family: &'static str, name: &str) {
        self.0.insert((family, name.to_string()));
    }

    fn amount(&mut self, v: &Value) {
        if let Some(of) = v.get("of") {
            if let Some((q, _)) = variant(of) {
                self.add("quantity", q);
            }
        }
    }

    fn effect(&mut self, e: &Value) {
        let Some((name, f)) = variant(e) else { return };
        self.add("effect", name);
        let Some(f) = f else { return };
        for (k, family) in [("target", "target"), ("pile", "pile"), ("kind", "pick")] {
            if let Some(s) = f.get(k).and_then(Value::str) {
                self.add(family, s);
            }
        }
        self.amount(f);
        if let Value::Obj(kv) = f {
            for (_, v) in kv {
                self.amount(v);
            }
        }
    }

    fn effects(&mut self, v: Option<&Value>) {
        for e in v.map(Value::items).unwrap_or(&[]) {
            self.effect(e);
        }
    }

    /// A power's or a relic's hooks.
    fn hooks(&mut self, v: Option<&Value>) {
        for h in v.map(Value::items).unwrap_or(&[]) {
            match h.get("trigger").and_then(variant) {
                Some((t, None)) => self.add("trigger", t),
                Some((t, Some(f))) => {
                    let param = f.get("by").or_else(|| f.get("from")).and_then(Value::str).unwrap_or("?");
                    self.add("trigger", &format!("{t}.{param}"));
                }
                None => {}
            }
            if let Some((n, _)) = h.get("condition").and_then(variant) {
                self.add("condition", n);
            }
            for k in ["hp_loss_source", "acts_first", "before_hand"] {
                if h.get(k).is_some() {
                    self.add("hook_field", k);
                }
            }
            self.effects(h.get("effects"));
        }
    }

    fn file(&mut self, text: &str) {
        let v = json::parse(text).expect("a content file parses");
        for c in v.get("cards").map(Value::items).unwrap_or(&[]) {
            self.effects(c.get("effects"));
            self.effects(c.get("turn_end"));
            for r in c.get("rows").map(Value::items).unwrap_or(&[]) {
                if let Some((n, _)) = r.get("condition").and_then(variant) {
                    self.add("condition", n);
                }
                self.effects(r.get("effects"));
            }
        }
        for p in v.get("powers").map(Value::items).unwrap_or(&[]) {
            self.hooks(p.get("hooks"));
            for k in ["debuff_if_negative", "can_go_negative", "skips_first_round", "attack_shape", "block_loss"] {
                if p.get(k).is_some() {
                    self.add("power_field", k);
                }
            }
            for s in p.get("statics").map(Value::items).unwrap_or(&[]) {
                for (k, family) in [("modifies", "modifies"), ("stage", "stage")] {
                    if let Some(x) = s.get(k).and_then(Value::str) {
                        self.add(family, x);
                    }
                }
                if let Some((n, _)) = s.get("condition").and_then(variant) {
                    self.add("static_condition", n);
                }
            }
            for r in p.get("replacements").map(Value::items).unwrap_or(&[]) {
                if let Some(x) = r.get("event").and_then(Value::str) {
                    self.add("replacement_event", x);
                }
                if let Some((n, _)) = r.get("action").and_then(variant) {
                    self.add("replacement_action", n);
                }
                if r.get("upTo").is_some() {
                    self.add("replacement_rule", "upTo");
                }
                self.effects(r.get("then"));
            }
        }
        for m in v.get("monsters").map(Value::items).unwrap_or(&[]) {
            if m.get("moves").is_none() {
                continue; // an encounter's slot list, not a monster
            }
            for mv in m.get("moves").map(Value::items).unwrap_or(&[]) {
                self.effects(mv.get("effects"));
            }
            for row in m.get("pattern").map(Value::items).unwrap_or(&[]) {
                for c in row.get("when").map(Value::items).unwrap_or(&[]) {
                    if let Some((n, _)) = variant(c) {
                        self.add("pattern_condition", n);
                    }
                }
                if let Some((n, _)) = row.get("then").and_then(variant) {
                    self.add("pattern_pick", n);
                }
            }
            for k in ["rolled_attack", "rolled_powers", "ascension"] {
                if m.get(k).is_some() {
                    self.add("monster_field", k);
                }
            }
            if let Some(code) = m.get("code").and_then(Value::str) {
                self.1.insert(code.to_string());
            }
        }
        for e in v.get("encounters").map(Value::items).unwrap_or(&[]) {
            self.slots(e.get("monsters"));
        }
        for r in v.get("relics").map(Value::items).unwrap_or(&[]) {
            if let Some(x) = r.get("rarity").and_then(Value::str) {
                self.add("relic_rarity", x);
            }
            self.hooks(r.get("hooks"));
            for k in r.get("fights").map(Value::items).unwrap_or(&[]) {
                if let Some(x) = k.str() {
                    self.add("fight_kind", x);
                }
            }
        }
        for p in v.get("potions").map(Value::items).unwrap_or(&[]) {
            if let Some(x) = p.get("rarity").and_then(Value::str) {
                self.add("potion_rarity", x);
            }
            self.effects(p.get("effects"));
            for r in p.get("rows").map(Value::items).unwrap_or(&[]) {
                if let Some((n, _)) = r.get("condition").and_then(variant) {
                    self.add("condition", n);
                }
                self.effects(r.get("effects"));
            }
        }
    }

    fn slots(&mut self, v: Option<&Value>) {
        for s in v.map(Value::items).unwrap_or(&[]) {
            if let Value::Obj(kv) = s {
                if let Some(opts) = s.get("one_of") {
                    self.add("encounter_slot", "one_of");
                    for o in opts.items() {
                        self.slots(Some(o));
                    }
                } else if s.get("draw").is_some() {
                    self.add("encounter_slot", "draw");
                } else {
                    let ks: Vec<&str> = kv.iter().map(|(k, _)| k.as_str()).collect();
                    self.add("encounter_slot", &ks.join("+"));
                }
            }
        }
    }
}

#[test]
fn every_element_has_wording() {
    let w = json::parse(WORDING).expect("content/wording.json parses");
    let names = element_names();
    let mut errors = Vec::new();
    for (family, list) in &names {
        for n in list {
            if entry(&w, family, n).is_none() {
                errors.push(format!("add wording for {family} {n} to content/wording.json"));
            }
        }
        // nothing stale: every key in the family is a listed element
        let tops: BTreeSet<&str> = list.iter().map(|n| n.split('.').next().unwrap()).collect();
        for k in w.get(family).map(keys).unwrap_or_default() {
            if !tops.contains(k) {
                errors.push(format!("content/wording.json words {family} {k}, which registry::element_names() doesn't list"));
            }
        }
    }
    let families: BTreeSet<&str> = names.iter().map(|(f, _)| *f).collect();
    for k in keys(&w) {
        if !families.contains(k) && !["version", "_about", "code_monster", "code_power"].contains(&k) {
            errors.push(format!("content/wording.json has a family {k} registry::element_names() doesn't know"));
        }
    }

    // every element the content files use is listed (so it is worded above)
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("content");
    let mut used = Used::default();
    let mut files: Vec<_> = ["cards.json", "powers.json", "monsters.json", "encounters.json", "relics.json", "potions.json"].iter().map(|f| root.join(f)).collect();
    let mut packs: Vec<_> = std::fs::read_dir(root.join("packs")).expect("content/packs").map(|e| e.unwrap().path()).collect();
    packs.sort();
    files.extend(packs.into_iter().filter(|p| p.extension().is_some_and(|x| x == "json")));
    for f in &files {
        used.file(&std::fs::read_to_string(f).unwrap());
    }
    assert!(used.0.len() > 40, "the walk found only {} elements: did the content format change?", used.0.len());
    for (family, n) in &used.0 {
        let listed = names.iter().any(|(f, l)| f == family && l.contains(&n.as_str()));
        if !listed {
            errors.push(format!(
                "content uses {family} {n}: list it in registry::element_names() and word it in content/wording.json"
            ));
        }
    }
    for code in &used.1 {
        if entry(&w, "code_monster", code).is_none() {
            errors.push(format!("add code_monster {code} (the behaviour held in engine code) to content/wording.json"));
        }
    }
    assert!(errors.is_empty(), "{}", errors.join("\n"));
}
