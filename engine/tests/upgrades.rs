//! Card upgrades as data (docs/specs/card-upgrades.md, building block C6).

mod common;

use sts_engine::registry::{bind, load_pack, parse_official, OFFICIAL_FILES};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");
const OLD_CARDS: &str = include_str!("data/cards_before_upgrades.json");
const OLD_PACK: &str = include_str!("data/act1_ironclad_before_upgrades.json");
const PACK_DUMP: &str = "tests/data/act1_ironclad_dump.txt";

/// The official cards file loads to the definitions the file before the
/// upgrade format gave, field by field.
#[test]
fn upgrade_format_matches_old_cards() {
    let [_, powers, monsters, encounters] = OFFICIAL_FILES;
    let old = parse_official([OLD_CARDS, powers, monsters, encounters]).unwrap();
    let new = parse_official(OFFICIAL_FILES).unwrap();
    assert_eq!(old.cards.len(), new.cards.len());
    for (a, b) in old.cards.iter().zip(&new.cards) {
        assert_eq!(common::card_dump(a), common::card_dump(b));
    }
}

/// The act1-ironclad pack's cards, every name the pack before the upgrade
/// format held, bound alone, play as that pack's did (the dump written from
/// it, `STS_WRITE_DUMP=1` rewrites it).
#[test]
fn pack_upgrades_match_old_pack() {
    load_pack(PACK).unwrap();
    let v = sts_engine::registry::json::parse(OLD_PACK).unwrap();
    let mut lines = Vec::new();
    for c in v.get("cards").unwrap().items() {
        let name = format!("gen:{}", c.get("id").unwrap().str().unwrap());
        let (ids, b) = bind(&[name.as_str()]).unwrap();
        lines.push(common::card_dump(b.def(ids[0])));
    }
    let text = lines.join("\n") + "\n";
    if std::env::var("STS_WRITE_DUMP").is_ok() {
        std::fs::write(PACK_DUMP, &text).unwrap();
    }
    let want = std::fs::read_to_string(PACK_DUMP).unwrap().replace("\r\n", "\n");
    for (a, b) in want.lines().zip(text.lines()) {
        assert_eq!(a, b);
    }
    assert_eq!(want.lines().count(), text.lines().count());
}

#[test]
fn upgrade_expressions() {
    use sts_engine::upgrade::Expr;
    let e = Expr::parse("n + 3").unwrap();
    assert_eq!((1..=4).map(|n| e.at(n)).collect::<Vec<_>>(), [4, 5, 6, 7]);
    assert_eq!(Expr::parse("2*n+1").unwrap().at(1), 3);
    assert_eq!(Expr::parse(" 2 * n * n + n + 7 ").unwrap().at(2), 17);
    for bad in ["(n)", "n/2", "m", "", "n +", "-1", "n - 1", "2n"] {
        assert!(Expr::parse(bad).is_err(), "{bad:?} parsed");
    }
}

#[test]
fn upgrade_paths() {
    use sts_engine::upgrade::Path;
    for p in ["cost", "exhaust", "effects.0.Damage.amount", "effects.1.Block", "rows.0.effects.2.ScaledDamage.amount.k", "turn_end.0.Damage.amount", "exhausted.0.GainEnergy"] {
        assert_eq!(Path::parse(p).unwrap().write(), p);
    }
    for bad in ["costs", "effects", "effects.x.Damage.amount", "rows.0.1.Damage", "effects.0"] {
        assert!(Path::parse(bad).is_err(), "{bad:?} parsed");
    }
}

fn pack(cards: &str) -> String {
    format!("{{\"version\": 1, \"cards\": [{cards}]}}")
}

fn def_of(name: &str) -> &'static sts_engine::cards::CardDef {
    let (ids, b) = bind(&[name]).unwrap_or_else(|e| panic!("{name}: {e}"));
    b.def(ids[0])
}

fn damage(d: &sts_engine::cards::CardDef) -> i16 {
    sts_engine::state::card_damage(d)
}

/// Searing Blow at levels 0-4: 12 + n(n+7)/2 (wiki; sts_lightspeed's
/// SEARING_BLOW), bound by name and played.
#[test]
fn searing_blow_levels() {
    load_pack(PACK).unwrap();
    let names = ["gen:Searing Blow", "gen:Searing Blow+", "gen:Searing Blow+2", "gen:Searing Blow+3", "gen:Searing Blow+4"];
    let (ids, b) = bind(&names).unwrap();
    let got: Vec<i16> = ids.iter().map(|&c| damage(b.def(c))).collect();
    assert_eq!(got, [12, 16, 21, 27, 34]);
    assert_eq!(b.def(ids[3]).name, "gen:Searing Blow+3");
    assert_eq!(b.def(ids[3]).level, 3);
    // Bound alone and played.
    let (ids, b) = bind(&["gen:Searing Blow+3"]).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 3;
    s.monsters[0].hp = 100;
    s.monsters[0].block = 0;
    s.monsters[0].powers = Default::default();
    s.apply_action(Action::Play { card: ids[0], target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 73);
    // Its levels stop where the damage leaves the engine's range.
    assert_eq!(b.def(ids[0]).max_level, 252);
    assert!(bind(&["gen:Searing Blow+252"]).is_ok());
    assert!(bind(&["gen:Searing Blow+253"]).is_err());
}

#[test]
fn cost_floor_keywords_and_match_level() {
    load_pack(PACK).unwrap();
    load_pack(&pack(
        r#"{"id": "UpFree", "cost": 0, "type": "Skill", "effects": [{"Block": 3}], "upgrade": {"cost": -1, "effects.0.Block": "2*n+1"}, "max_level": 3},
           {"id": "UpWound", "cost": 1, "type": "Skill", "effects": [{"AddCard": {"card": "Wound", "n": 1, "pile": "Discard", "match_level": true}}], "upgrade": {}}"#,
    ))
    .unwrap();
    let d = def_of("gen:UpFree+");
    assert_eq!((d.cost(), d.effects[0]), (0, sts_engine::effects::Effect::Block(6)));
    assert_eq!(def_of("gen:UpFree+3").effects[0], sts_engine::effects::Effect::Block(3 + 3 + 5 + 7));
    assert!(bind(&["gen:UpFree+4"]).is_err(), "past max_level");
    // Limit Break exhausts at level 0, not at level 1.
    assert!(def_of("gen:Limit Break").exhaust);
    assert!(!def_of("gen:Limit Break+").exhaust);
    // Anger adds Anger, Anger+ adds Anger+; a card with no upgrade added
    // with the flag stays itself; Immolate+ (no flag) adds a plain Burn.
    let added = |d: &sts_engine::cards::CardDef| {
        d.all_effects().find_map(|e| if let sts_engine::effects::Effect::AddCard { card, .. } = *e { Some(card.name()) } else { None }).unwrap()
    };
    assert_eq!(added(common::card("Anger").def()), "Anger");
    assert_eq!(added(common::card("Anger+").def()), "Anger+");
    assert_eq!(added(def_of("gen:UpWound+")), "Wound");
    assert_eq!(added(def_of("gen:Immolate+")), "Burn");
    // True Grit keeps its separate upgrade entry.
    assert_eq!(def_of("gen:True Grit+").max_level, 1);
    assert!(def_of("gen:True Grit+").name.ends_with("True Grit+"));
}

#[test]
fn load_errors_name_the_card() {
    let cases = [
        (r#"{"id": "LeBadPath", "cost": 1, "type": "Skill", "effects": [{"Block": 3}], "upgrade": {"effects.0.Damage.amount": 1}}"#, "LeBadPath"),
        (r#"{"id": "LeBadExpr", "cost": 1, "type": "Skill", "effects": [{"Block": 3}], "upgrade": {"effects.0.Block": "n/2"}}"#, "LeBadExpr"),
        (r#"{"id": "LeLowCost", "cost": -3, "type": "Skill", "effects": [{"Block": 3}]}"#, "LeLowCost"),
        (r#"{"id": "LeXCost", "cost": -1, "type": "Skill", "effects": [], "upgrade": {"cost": -1}}"#, "LeXCost"),
        (r#"{"id": "LeBoth", "cost": 0, "type": "Skill", "x_cost": true, "unplayable": true, "effects": []}"#, "LeBoth"),
        (r#"{"id": "LeUnplayable", "cost": -2, "type": "Status", "effects": [{"Block": 3}]}"#, "LeUnplayable"),
        (r#"{"id": "LeUnplayableClash", "cost": -2, "type": "Status", "playable_if": {"HandAll": "Attack"}, "effects": []}"#, "LeUnplayableClash"),
        (r#"{"id": "LePower", "cost": 1, "type": "Power", "exhaust": true, "effects": []}"#, "LePower"),
        (r#"{"id": "LeTwice", "cost": 1, "type": "Skill", "effects": [{"Block": 3}], "upgrade": {"effects.0.Block": 3}}, {"id": "LeTwice+", "cost": 1, "type": "Skill", "effects": [{"Block": 6}]}"#, "LeTwice"),
        (r#"{"id": "LeMax", "cost": 1, "type": "Skill", "effects": [{"Block": 3}], "max_level": 2}, {"id": "LeMax+", "cost": 1, "type": "Skill", "effects": [{"Block": 6}]}"#, "LeMax"),
        (r#"{"id": "LeRange", "cost": 1, "type": "Skill", "effects": [{"Block": 30000}], "upgrade": {"effects.0.Block": 3000}, "max_level": 2}"#, "LeRange"),
        (r#"{"id": "LeRange255", "cost": 1, "type": "Skill", "effects": [{"Block": 30000}], "upgrade": {"effects.0.Block": 1000}, "max_level": 255}"#, "LeRange255"),
        (r#"{"id": "LeMatch", "cost": 1, "type": "Skill", "effects": [{"AddCard": {"card": "Anger", "n": 1, "pile": "Discard", "match_level": true}}]}"#, "LeMatch"),
    ];
    for (entry, id) in cases {
        let e = load_pack(&pack(entry)).expect_err(id);
        assert!(e.contains(id), "{id}: {e}");
    }
}

#[test]
fn cost_sentinels() {
    let w = common::card("Whirlwind").def();
    assert!((w.cost(), w.x_cost(), w.unplayable()) == (0, true, false));
    let wound = common::card("Wound").def();
    assert!((wound.cost(), wound.x_cost(), wound.unplayable()) == (0, false, true));
    load_pack(&pack(r#"{"id": "CsOldX", "cost": 0, "type": "Skill", "x_cost": true, "effects": []}, {"id": "CsOldU", "cost": 1, "type": "Status", "unplayable": true, "effects": []}"#))
        .unwrap();
    assert!(def_of("gen:CsOldX").x_cost() && def_of("gen:CsOldX").cost() == 0);
    assert!(def_of("gen:CsOldU").unplayable() && def_of("gen:CsOldU").cost() == 0);
}

#[test]
fn names() {
    use sts_engine::registry::{base_name, upgrade_name};
    load_pack(PACK).unwrap();
    assert_eq!(upgrade_name("Bash").unwrap().as_deref(), Some("Bash+"));
    assert_eq!(upgrade_name("Bash+").unwrap(), None);
    assert_eq!(upgrade_name("Wound").unwrap(), None);
    assert_eq!(upgrade_name("Burn").unwrap(), None, "a status takes no general upgrade");
    assert_eq!(upgrade_name("gen:Flame Barrier").unwrap().as_deref(), Some("gen:Flame Barrier+"));
    assert_eq!(upgrade_name("gen:Searing Blow+").unwrap().as_deref(), Some("gen:Searing Blow+2"));
    assert_eq!(upgrade_name("gen:Searing Blow+2").unwrap().as_deref(), Some("gen:Searing Blow+3"));
    assert_eq!(upgrade_name("gen:True Grit").unwrap().as_deref(), Some("gen:True Grit+"));
    assert_eq!(base_name("gen:Searing Blow+12"), "gen:Searing Blow");
    assert_eq!(base_name("Bash+"), "Bash");
    assert_eq!(base_name("Bash"), "Bash");
    // Every official and pack name keeps the base the old `rstrip("+")` gave.
    let v = sts_engine::registry::json::parse(OLD_PACK).unwrap();
    let pack_names = v.get("cards").unwrap().items().iter().map(|c| format!("gen:{}", c.get("id").unwrap().str().unwrap())).collect::<Vec<_>>();
    for n in sts_engine::registry::official_card_names().iter().cloned().chain(pack_names) {
        assert_eq!(base_name(&n), n.trim_end_matches('+'), "{n}");
    }
}

/// Amendment 1: an entry names its unique upgrade (`successor`), any id;
/// `gen:X+` and the successor's own id are the same card.
#[test]
fn successor_names_the_upgrade() {
    load_pack(&pack(
        r#"{"id": "PrA", "cost": 1, "type": "Skill", "effects": [{"Block": 3}], "successor": "PrA Sharp"},
           {"id": "PrA Sharp", "cost": 0, "type": "Skill", "effects": [{"Draw": 2}]}"#,
    ))
    .unwrap();
    let (ids, b) = bind(&["gen:PrA", "gen:PrA+", "gen:PrA Sharp"]).unwrap();
    assert_eq!(ids[1], ids[2], "one card, one id");
    assert_eq!(ids[1].0, ids[0].0 + 1, "the slot's level-1 id");
    let d = b.def(ids[1]);
    assert_eq!((d.name, d.cost(), d.level, d.max_level), ("gen:PrA+", 0, 1, 1));
    assert_eq!(d.effects[0], sts_engine::effects::Effect::Draw(2));
    assert_eq!(sts_engine::registry::upgrade_name("gen:PrA").unwrap().as_deref(), Some("gen:PrA+"));
    assert_eq!(sts_engine::registry::upgrade_name("gen:PrA Sharp").unwrap(), None);
}

#[test]
fn successor_load_errors() {
    let cases = [
        (r#"{"id": "SeMissing", "cost": 1, "type": "Skill", "effects": [], "successor": "SeNowhere"}"#, "SeMissing"),
        (r#"{"id": "SeTwiceA", "cost": 1, "type": "Skill", "effects": [], "successor": "SeShared"}, {"id": "SeTwiceB", "cost": 1, "type": "Skill", "effects": [], "successor": "SeShared"}, {"id": "SeShared", "cost": 1, "type": "Skill", "effects": []}"#, "SeShared"),
        (r#"{"id": "SeChain", "cost": 1, "type": "Skill", "effects": [], "successor": "SeChain2"}, {"id": "SeChain2", "cost": 1, "type": "Skill", "effects": [], "successor": "SeChain3"}, {"id": "SeChain3", "cost": 1, "type": "Skill", "effects": []}"#, "SeChain2"),
        (r#"{"id": "SeUp", "cost": 1, "type": "Skill", "effects": [], "successor": "SeUp2"}, {"id": "SeUp2", "cost": 1, "type": "Skill", "effects": [{"Block": 1}], "upgrade": {"effects.0.Block": 1}}"#, "SeUp2"),
        (r#"{"id": "SeMaxS", "cost": 1, "type": "Skill", "effects": [], "successor": "SeMaxS2"}, {"id": "SeMaxS2", "cost": 1, "type": "Skill", "effects": [], "max_level": 1}"#, "SeMaxS2"),
        (r#"{"id": "SeBoth", "cost": 1, "type": "Skill", "effects": [{"Block": 1}], "upgrade": {"effects.0.Block": 1}, "successor": "SeBoth2"}, {"id": "SeBoth2", "cost": 1, "type": "Skill", "effects": []}"#, "SeBoth"),
        (r#"{"id": "SeMax", "cost": 1, "type": "Skill", "effects": [], "successor": "SeMax2", "max_level": 2}, {"id": "SeMax2", "cost": 1, "type": "Skill", "effects": []}"#, "SeMax"),
    ];
    for (entry, id) in cases {
        let e = load_pack(&pack(entry)).expect_err(id);
        assert!(e.contains(id), "{id}: {e}");
    }
}
