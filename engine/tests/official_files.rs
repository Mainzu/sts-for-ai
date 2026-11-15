//! The official content files (`content/*.json`, runtime registry stage 4).

use sts_engine::registry::{load_pack, official_files};

#[test]
fn files_are_canonical() {
    let committed = [
        include_str!("../../content/cards.json"),
        include_str!("../../content/powers.json"),
        include_str!("../../content/monsters.json"),
        include_str!("../../content/relics.json"),
    ];
    for ((name, text), file) in official_files().iter().zip(committed) {
        assert!(file.replace("\r\n", "\n") == *text, "content/{name} differs from what export_content writes");
    }
}

#[test]
fn official_fields_refused_in_packs() {
    let card = |extra: &str| {
        format!("{{\"version\": 1, \"cards\": [{{\"id\": \"of_card\", \"cost\": 1, \"type\": \"Skill\", {extra}, \"effects\": [{{\"Block\": 5}}]}}]}}")
    };
    for (extra, field) in [("\"class\": \"Ironclad\"", "class"), ("\"held_out\": false", "held_out"), ("\"proving\": true", "proving")] {
        let e = load_pack(&card(extra)).unwrap_err();
        assert!(e.contains(field) && e.contains("official"), "{field}: {e}");
    }
    let monster = "{\"version\": 1, \"monsters\": [{\"id\": \"of_mon\", \"code\": \"louse\", \"hp\": [10, 12], \"moves\": [{\"name\": \"Hit\", \"effects\": [{\"Damage\": {\"amount\": 5, \"hits\": 1, \"target\": \"Opponent\"}}]}], \"pattern\": [{\"when\": [], \"then\": {\"Move\": 0}}]}]}";
    let e = load_pack(monster).unwrap_err();
    assert!(e.contains("code") && e.contains("official"), "{e}");
}

use sts_engine::registry::{parse_official, OFFICIAL_FILES};

#[test]
fn file_order_checked() {
    let [cards, powers, monsters, encounters] = OFFICIAL_FILES;
    let lines = |t: &str| t.lines().map(str::to_string).collect::<Vec<_>>();
    // Two cards swapped (Strike and Defend, entries 1 and 2 of the file).
    let mut c = lines(cards);
    c.swap(1, 2);
    let e = parse_official([&c.join("\n"), powers, monsters, encounters]).err().expect("swapped cards refused");
    assert!(e.contains("Defend"), "{e}");
    // A power missing (the last entry, keeping the JSON valid).
    let mut p = lines(powers);
    let n = p.len();
    p.remove(n - 2);
    let last = p.len() - 2;
    p[last] = p[last].trim_end_matches(',').to_string();
    let e = parse_official([cards, &p.join("\n"), monsters, encounters]).err().expect("missing power refused");
    assert!(e.contains("powers") && e.contains("29"), "{e}");
    // A monster with a wrong id.
    let m = monsters.replacen("\"id\": \"Jaw Worm\"", "\"id\": \"Jaw Wurm\"", 1);
    let e = parse_official([cards, powers, &m, encounters]).err().expect("wrong monster id refused");
    assert!(e.contains("Jaw Wurm"), "{e}");
    // A code name on the wrong monster.
    let m = monsters.replacen("{\"id\": \"Cultist\"", "{\"id\": \"Cultist\", \"code\": \"louse\"", 1);
    let e = parse_official([cards, powers, &m, encounters]).err().expect("misplaced code refused");
    assert!(e.contains("Cultist") && e.contains("code"), "{e}");
    // Two encounters swapped (entries 1 and 2 of the file).
    let mut n = lines(encounters);
    n.swap(1, 2);
    let e = parse_official([cards, powers, monsters, &n.join("\n")]).err().expect("swapped encounters refused");
    assert!(e.contains("jaw_worm") && e.contains("Cultist"), "{e}");
    // An encounter naming an unknown monster.
    let n = encounters.replacen("[\"Jaw Worm\"]", "[\"Jaw Wurm\"]", 1);
    let e = parse_official([cards, powers, monsters, &n]).err().expect("unknown monster refused");
    assert!(e.contains("Jaw Wurm"), "{e}");
}
