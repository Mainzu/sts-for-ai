//! The Act 1 potions written as pack data (`content/packs/act1-potions.json`,
//! docs/specs/potions.md step 5) and Sacred Bark (`act1-relics.json`): each
//! potion against its game class (the decompiled `potions/<Class>.java`,
//! named per test), its written amounts against its potency, and Bark's
//! doubling.

use sts_engine::effects::Effect;
use sts_engine::potions::Rarity;
use sts_engine::registry::{bind_power, load_pack, potion, potions_named, relics_named, Binding};
use sts_engine::*;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

/// The Ironclad pack first: its pool is what the discovery potions draw from.
fn load() {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
}

/// A fight against `e` at `hp` of `max_hp`, holding `potions` (by game
/// name) and Sacred Bark when `bark`.
fn fight_at(e: Encounter, hp: i16, max_hp: i16, potions: &[&str], bark: bool) -> CombatState {
    load();
    let relics = if bark { relics_named(&["gen:Sacred Bark"]).unwrap() } else { vec![] };
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), hp, max_hp, e, &relics, &mut Rng::new(3));
    let names: Vec<String> = potions.iter().map(|p| format!("gen:{p}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    s.give_potions(&potions_named(&refs).unwrap()).unwrap();
    s
}

fn fight(potion: &str, bark: bool) -> CombatState {
    fight_at(Encounter::JawWorm, 50, 80, &[potion], bark)
}

/// Uses the potion in slot 0 (at monster 0 when it takes a target).
fn drink(s: &mut CombatState) {
    let a = *s.legal_actions().iter().find(|a| matches!(a, Action::UsePotion { slot: 0, .. })).expect("the potion is usable");
    s.step(a, &mut Rng::new(1)).unwrap();
}

/// A fight after drinking `potion`.
fn drunk(potion: &str, bark: bool) -> CombatState {
    let mut s = fight(potion, bark);
    drink(&mut s);
    s
}

/// Ends the turn with nothing played: the monsters act, then turn 2 starts.
fn next_turn(s: &mut CombatState) {
    let mut rng = Rng::new(12);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert!(!s.is_over());
    assert_eq!(s.stage, Stage::PlayerTurn);
}

fn pack_power(s: &CombatState, id: &str) -> Power {
    bind_power(&s.binding, id).unwrap().1
}

fn play(s: &mut CombatState, name: &str) {
    let c = CardId::from_name(name).unwrap();
    if s.hand.count(c) == 0 {
        s.hand.add(c, 1);
    }
    s.player.energy = s.player.energy.max(3);
    let target = if c.def().targeted() { Some(0) } else { None };
    s.step(Action::Play { card: c, target }, &mut Rng::new(13)).unwrap();
}

const ALL: [&str; 32] = [
    "Blood Potion",
    "Elixir",
    "Heart of Iron",
    "Block Potion",
    "Dexterity Potion",
    "Energy Potion",
    "Explosive Potion",
    "Fire Potion",
    "Strength Potion",
    "Swift Potion",
    "Weak Potion",
    "Fear Potion",
    "Flex Potion",
    "Speed Potion",
    "Regen Potion",
    "Ancient Potion",
    "Liquid Bronze",
    "Essence of Steel",
    "Duplication Potion",
    "Cultist Potion",
    "Blessing of the Forge",
    "Fruit Juice",
    "Gambler's Brew",
    "Fairy in a Bottle",
    "Liquid Memories",
    "Smoke Bomb",
    "Distilled Chaos",
    "Attack Potion",
    "Skill Potion",
    "Power Potion",
    "Entropic Brew",
    "Snecko Oil",
];

#[test]
fn every_potion_loads_with_its_rarity_and_potency() {
    load();
    use Rarity::*;
    // (name, the class's PotionRarity, its getPotency()).
    let want = [
        ("Blood Potion", Common, 20),
        ("Elixir", Uncommon, 0),
        ("Heart of Iron", Rare, 6),
        ("Block Potion", Common, 12),
        ("Dexterity Potion", Common, 2),
        ("Energy Potion", Common, 2),
        ("Explosive Potion", Common, 10),
        ("Fire Potion", Common, 20),
        ("Strength Potion", Common, 2),
        ("Swift Potion", Common, 3),
        ("Weak Potion", Common, 3),
        ("Fear Potion", Common, 3),
        ("Flex Potion", Common, 5),
        ("Speed Potion", Common, 5),
        ("Regen Potion", Uncommon, 5),
        ("Ancient Potion", Uncommon, 1),
        ("Liquid Bronze", Uncommon, 3),
        ("Essence of Steel", Uncommon, 4),
        ("Duplication Potion", Uncommon, 1),
        ("Cultist Potion", Rare, 1),
        ("Blessing of the Forge", Common, 0),
        ("Fruit Juice", Rare, 5),
        ("Gambler's Brew", Uncommon, 0),
        ("Fairy in a Bottle", Rare, 30),
        ("Liquid Memories", Uncommon, 1),
        ("Smoke Bomb", Rare, 0),
        ("Distilled Chaos", Uncommon, 3),
        ("Attack Potion", Common, 1),
        ("Skill Potion", Common, 1),
        ("Power Potion", Common, 1),
        // EntropicBrew.java's getPotency() (3) isn't read: its loop reads
        // the potion slots, so Sacred Bark doesn't change it; 0 here.
        ("Entropic Brew", Rare, 0),
        ("Snecko Oil", Rare, 5),
    ];
    assert_eq!(want.map(|(n, ..)| n), ALL);
    for (name, rarity, potency) in want {
        let p = potion(&format!("gen:{name}")).unwrap_or_else(|| panic!("{name} loaded"));
        assert_eq!((p.rarity, p.potency), (rarity, potency), "{name}");
    }
}

#[test]
fn potency_matches() {
    // Each potion's written amounts equal its potency; Blood Potion's share
    // 1/5 is potency 20 percent; potency 0 writes no amount.
    load();
    for name in ALL {
        let p = potion(&format!("gen:{name}")).unwrap();
        let amounts: Vec<i16> = p
            .effects()
            .filter_map(|e| match *e {
                Effect::Apply { amount, .. } | Effect::ApplyPack { amount, .. } | Effect::PlainDamage { amount, .. } => Some(amount),
                Effect::Block(n) | Effect::GainMaxHp(n) => Some(n),
                Effect::GainEnergy(n) => Some(n as i16),
                Effect::Draw(n) => Some(n as i16),
                // Liquid Memories' count is its potency.
                Effect::Pick { n, free: true, .. } => Some(n as i16),
                Effect::PlayTop { n, .. } => Some(n as i16),
                Effect::Discover { copies, .. } => Some(copies as i16),
                Effect::HealOf(a) => {
                    assert_eq!((a.base, 100 * a.k % a.per), (0, 0), "{name}: a whole percent");
                    Some(100 * a.k / a.per)
                }
                _ => None,
            })
            .collect();
        if p.potency == 0 {
            assert!(amounts.is_empty(), "{name}: potency 0 writes no amount, got {amounts:?}");
        } else {
            assert!(!amounts.is_empty() && amounts.iter().all(|&n| n == p.potency), "{name}: amounts {amounts:?}, potency {}", p.potency);
        }
    }
}

#[test]
fn blood_potion() {
    // BloodPotion.java: heal (int)(maxHealth * (potency / 100.0F)), potency 20.
    let mut s = fight_at(Encounter::JawWorm, 40, 80, &["Blood Potion"], false);
    drink(&mut s);
    assert_eq!(s.player.hp, 56, "16 at 80 max HP");
    let mut s = fight_at(Encounter::JawWorm, 40, 75, &["Blood Potion"], false);
    drink(&mut s);
    assert_eq!(s.player.hp, 55, "15 at 75 max HP");
    // Sacred Bark: potency 40, 32 at 80.
    let mut s = fight_at(Encounter::JawWorm, 40, 80, &["Blood Potion"], true);
    drink(&mut s);
    assert_eq!(s.player.hp, 72);
    assert!(s.player.potions.is_empty(), "used up");
}

#[test]
fn elixir() {
    // Elixir.java: ExhaustAction(false, true, true), any number of cards in
    // hand, none allowed; potency 0, so Sacred Bark leaves it as it is.
    for bark in [false, true] {
        let mut s = fight("Elixir", bark);
        let n = s.hand.len();
        drink(&mut s);
        let Action::Choose(c) = s.legal_actions()[0] else { panic!("Elixir picks") };
        s.step(Action::Choose(c), &mut Rng::new(1)).unwrap();
        let Action::Choose(d) = s.legal_actions()[0] else { panic!("still picking") };
        s.step(Action::Choose(d), &mut Rng::new(1)).unwrap();
        s.step(Action::Done, &mut Rng::new(1)).unwrap();
        assert_eq!((s.hand.len(), s.exhaust().len()), (n - 2, 2), "bark {bark}");
        assert_eq!(s.stage, Stage::PlayerTurn);
    }
}

#[test]
fn heart_of_iron() {
    // HeartOfIron.java: Metallicize potency 6.
    assert_eq!(drunk("Heart of Iron", false).player.powers.get(Power::Metallicize), 6);
    assert_eq!(drunk("Heart of Iron", true).player.powers.get(Power::Metallicize), 12);
}

#[test]
fn block_potion() {
    // BlockPotion.java: GainBlockAction(player, potency 12): raw, no
    // Dexterity or Frail.
    let mut s = fight("Block Potion", false);
    s.player.powers.add(Power::Dexterity, 2);
    s.player.powers.add(Power::Frail, 2);
    drink(&mut s);
    assert_eq!(s.player.block, 12);
    assert_eq!(drunk("Block Potion", true).player.block, 24);
}

#[test]
fn dexterity_and_strength_potions() {
    // DexterityPotion.java, StrengthPotion.java: potency 2.
    assert_eq!(drunk("Dexterity Potion", false).player.powers.get(Power::Dexterity), 2);
    assert_eq!(drunk("Dexterity Potion", true).player.powers.get(Power::Dexterity), 4);
    assert_eq!(drunk("Strength Potion", false).player.powers.get(Power::Strength), 2);
    assert_eq!(drunk("Strength Potion", true).player.powers.get(Power::Strength), 4);
}

#[test]
fn energy_and_swift_potions() {
    // EnergyPotion.java: GainEnergyAction(2); SwiftPotion.java: draw 3.
    let s = fight("Energy Potion", false);
    assert_eq!(drunk("Energy Potion", false).player.energy, s.player.energy + 2);
    assert_eq!(drunk("Energy Potion", true).player.energy, s.player.energy + 4);
    let n = fight("Swift Potion", false).hand.len();
    assert_eq!(drunk("Swift Potion", false).hand.len(), n + 3);
    assert_eq!(drunk("Swift Potion", true).hand.len(), n + 5, "the draw pile holds 5 after the opening hand");
}

#[test]
fn fire_potion() {
    // FirePotion.java: DamageInfo(player, 20, THORNS) to the target: no
    // Strength or Vulnerable, and no Curl Up (it reacts to NORMAL damage).
    let mut s = fight_at(Encounter::TwoLouse, 50, 80, &["Fire Potion"], false);
    for m in &mut s.monsters[..2] {
        (m.hp, m.max_hp) = (40, 40);
    }
    s.player.powers.add(Power::Strength, 5);
    s.monsters[0].powers.add(Power::Vulnerable, 2);
    let curl = s.monsters[0].powers.get(Power::CurlUp);
    assert!(curl > 0, "a louse curls up");
    drink(&mut s);
    assert_eq!((s.monsters[0].hp, s.monsters[1].hp), (20, 40));
    assert_eq!((s.monsters[0].block, s.monsters[0].powers.get(Power::CurlUp)), (0, curl), "no Curl Up");
    let mut s = fight_at(Encounter::JawWorm, 50, 80, &["Fire Potion"], true);
    let hp = s.monsters[0].hp;
    drink(&mut s);
    assert_eq!(s.monsters[0].hp, hp - 40, "Sacred Bark");
}

#[test]
fn explosive_potion() {
    // ExplosivePotion.java: DamageAllEnemiesAction(null, the pure matrix of
    // 10, NORMAL): unmodified, and with no owner, no Curl Up.
    let mut s = fight_at(Encounter::TwoLouse, 50, 80, &["Explosive Potion"], false);
    for m in &mut s.monsters[..2] {
        (m.hp, m.max_hp) = (40, 40);
    }
    s.player.powers.add(Power::Strength, 5);
    s.monsters[1].powers.add(Power::Vulnerable, 2);
    drink(&mut s);
    assert_eq!((s.monsters[0].hp, s.monsters[1].hp), (30, 30));
    assert_eq!((s.monsters[0].block, s.monsters[1].block), (0, 0), "no Curl Up");
    let mut s = fight_at(Encounter::TwoLouse, 50, 80, &["Explosive Potion"], true);
    for m in &mut s.monsters[..2] {
        (m.hp, m.max_hp) = (40, 40);
    }
    drink(&mut s);
    assert_eq!((s.monsters[0].hp, s.monsters[1].hp), (20, 20), "Sacred Bark");
}

#[test]
fn weak_and_fear_potions() {
    // WeakenPotion.java, FearPotion.java: 3 Weak / 3 Vulnerable on the target.
    assert_eq!(drunk("Weak Potion", false).monsters[0].powers.get(Power::Weak), 3);
    assert_eq!(drunk("Weak Potion", true).monsters[0].powers.get(Power::Weak), 6);
    assert_eq!(drunk("Fear Potion", false).monsters[0].powers.get(Power::Vulnerable), 3);
    assert_eq!(drunk("Fear Potion", true).monsters[0].powers.get(Power::Vulnerable), 6);
}

#[test]
fn flex_and_speed_potions() {
    // SteroidPotion.java (Flex): Strength and LoseStrength 5; SpeedPotion.java:
    // Dexterity and LoseDexterity 5 (a debuff), lost at the turn's end.
    let mut s = drunk("Flex Potion", false);
    assert_eq!(s.player.powers.get(Power::Strength), 5);
    next_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Strength), 0);
    let mut s = drunk("Speed Potion", false);
    let lose = pack_power(&s, "LoseDexterity");
    assert_eq!((s.player.powers.get(Power::Dexterity), s.player.powers.get(lose)), (5, 5));
    next_turn(&mut s);
    assert_eq!((s.player.powers.get(Power::Dexterity), s.player.powers.get(lose)), (0, 0));
    let mut s = drunk("Speed Potion", true);
    assert_eq!((s.player.powers.get(Power::Dexterity), s.player.powers.get(lose)), (10, 10), "Sacred Bark");
    next_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Dexterity), 0);
    // A debuff: Artifact stops LoseDexterity, so the Dexterity stays.
    let mut s = fight("Speed Potion", false);
    s.player.powers.add(Power::Artifact, 1);
    drink(&mut s);
    assert_eq!((s.player.powers.get(Power::Dexterity), s.player.powers.get(lose), s.player.powers.get(Power::Artifact)), (5, 0, 0));
    // LoseStrengthPower is a debuff too: Artifact stops Flex's LoseStrength,
    // so the Strength is kept past the turn's end.
    let mut s = fight("Flex Potion", false);
    s.player.powers.add(Power::Artifact, 1);
    drink(&mut s);
    assert_eq!((s.player.powers.get(Power::Strength), s.player.powers.get(Power::LoseStrength), s.player.powers.get(Power::Artifact)), (5, 0, 0));
    next_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Strength), 5);
}

#[test]
fn regen_potion() {
    // RegenPotion.java / RegenPower: at the turn's end heal its amount, then
    // one less.
    let mut plain = fight_at(Encounter::JawWorm, 30, 80, &["Regen Potion"], false);
    let mut s = plain.clone();
    drink(&mut s);
    let regen = pack_power(&s, "Regen");
    assert_eq!(s.player.powers.get(regen), 5);
    next_turn(&mut plain);
    next_turn(&mut s);
    assert_eq!(s.player.hp - plain.player.hp, 5);
    assert_eq!(s.player.powers.get(regen), 4);
    assert!(fight("Regen Potion", false).can_heal(), "a held Regen Potion can heal");
    assert_eq!(drunk("Regen Potion", true).player.powers.get(regen), 10, "Sacred Bark");
}

#[test]
fn ancient_potion_and_liquid_bronze() {
    // AncientPotion.java: Artifact 1; LiquidBronze.java: Thorns 3.
    assert_eq!(drunk("Ancient Potion", false).player.powers.get(Power::Artifact), 1);
    assert_eq!(drunk("Ancient Potion", true).player.powers.get(Power::Artifact), 2);
    let mut plain = fight("Liquid Bronze", false);
    let mut s = plain.clone();
    drink(&mut s);
    assert_eq!(s.player.powers.get(Power::Thorns), 3);
    next_turn(&mut plain);
    next_turn(&mut s);
    assert_eq!(plain.monsters[0].hp - s.monsters[0].hp, 3, "Jaw Worm's Chomp takes 3 back");
    assert_eq!(drunk("Liquid Bronze", true).player.powers.get(Power::Thorns), 6);
}

#[test]
fn essence_of_steel() {
    // EssenceOfSteel.java: PlatedArmor 4: block 4 at the turn's end, one less
    // when an attack takes HP.
    let mut plain = fight("Essence of Steel", false);
    let mut s = plain.clone();
    drink(&mut s);
    let plated = pack_power(&s, "PlatedArmor");
    assert_eq!(s.player.powers.get(plated), 4);
    next_turn(&mut plain);
    next_turn(&mut s);
    assert_eq!(s.player.hp - plain.player.hp, 4, "4 block against Chomp's 11");
    assert_eq!(s.player.powers.get(plated), 3);
    assert_eq!(drunk("Essence of Steel", true).player.powers.get(plated), 8);
}

#[test]
fn heart_of_iron_blocks_at_turn_end() {
    // MetallicizePower: block at the turn's end.
    let mut plain = fight("Heart of Iron", false);
    let mut s = plain.clone();
    drink(&mut s);
    next_turn(&mut plain);
    next_turn(&mut s);
    assert_eq!(s.player.hp - plain.player.hp, 6);
}

#[test]
fn duplication_potion() {
    // DuplicationPotion.java / DuplicationPower: the next card is played
    // twice; the power ends with the round.
    let mut s = drunk("Duplication Potion", false);
    let dup = pack_power(&s, "Duplication");
    assert_eq!(s.player.powers.get(dup), 1);
    let hp = s.monsters[0].hp;
    play(&mut s, "Strike");
    assert_eq!(hp - s.monsters[0].hp, 12, "Strike twice");
    assert_eq!(s.player.powers.get(dup), 0);
    let hp = s.monsters[0].hp;
    play(&mut s, "Strike");
    assert_eq!(hp - s.monsters[0].hp, 6, "then once");
    // Sacred Bark: 2, two cards replayed; unused, one goes each round.
    let mut s = drunk("Duplication Potion", true);
    assert_eq!(s.player.powers.get(dup), 2);
    next_turn(&mut s);
    assert_eq!(s.player.powers.get(dup), 1);
}

#[test]
fn duplication_lasts_until_the_rounds_end() {
    // DuplicationPower.atEndOfRound (not atEndOfTurn): the stack goes once
    // the monsters have acted. Dead Branch's card for an ethereal Dazed
    // pauses End Turn before the monsters (`Stage::EndingTurn` part 2):
    // there the player's turn has ended and Duplication is still 1.
    load();
    let relics = relics_named(&["gen:Dead Branch"]).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &relics, &mut Rng::new(3));
    s.give_potions(&potions_named(&["gen:Duplication Potion"]).unwrap()).unwrap();
    drink(&mut s);
    let dup = pack_power(&s, "Duplication");
    s.hand = Hand::from_cards(&[CardId::from_name("Dazed").unwrap()]);
    s.apply_action(Action::EndTurn).unwrap();
    assert_eq!(s.stage, Stage::EndingTurn { part: 2 });
    assert_eq!((s.player.hp, s.player.powers.get(dup)), (50, 1), "the turn ended, the round didn't");
    let mut rng = Rng::new(12);
    s.advance(&mut rng);
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((s.player.hp, s.player.powers.get(dup)), (39, 0), "Chomp, then the round's end");
}

#[test]
fn cultist_potion() {
    // CultistPotion.java: Ritual 1 (player-controlled: Strength at the
    // player's turn end).
    let mut s = drunk("Cultist Potion", false);
    assert_eq!(s.player.powers.get(Power::Ritual), 1);
    next_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Strength), 1);
    let mut s = drunk("Cultist Potion", true);
    next_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Strength), 2);
}

#[test]
fn blessing_of_the_forge() {
    // BlessingOfTheForge.java: ArmamentsAction(true), every card in hand
    // upgraded; potency 0.
    for bark in [false, true] {
        let s = drunk("Blessing of the Forge", bark);
        assert!(s.hand.len() > 0);
        // The starter's cards all upgrade.
        assert!(s.hand.iter().all(|(c, _)| c.upgraded()), "bark {bark}: {:?}", s.hand.iter().map(|(c, n)| (c.def().name, n)).collect::<Vec<_>>());
    }
}

#[test]
fn sacred_bark() {
    // SacredBark.java: AbstractPotion.getPotency doubles with the relic;
    // Fire Potion 40 with it, 20 without; Elixir (potency 0) unchanged.
    for (bark, dealt) in [(false, 20), (true, 40)] {
        let mut s = fight("Fire Potion", bark);
        let hp = s.monsters[0].hp;
        assert_eq!(s.potion_multiplier(), if bark { 2 } else { 1 });
        drink(&mut s);
        assert_eq!(hp - s.monsters[0].hp, dealt);
    }
    let s = fight("Elixir", true);
    assert_eq!(s.potion_scale(s.player.potions.id(0)), 1);
    load();
    assert_eq!(sts_engine::registry::relic("gen:Sacred Bark").unwrap().potion_potency, 2);
}

#[test]
fn potion_potency_guard() {
    // 0 is not a multiple; the official writer keeps a non-default one.
    let e = load_pack(r#"{"version": 2, "relics": [{"id": "pp-zero", "rarity": "boss", "potion_potency": 0}]}"#).unwrap_err();
    assert!(e.contains("pp-zero") && e.contains("potion_potency"), "{e}");
    load();
    let bark = sts_engine::registry::relic("gen:Sacred Bark").unwrap();
    assert!(sts_engine::relics::official_relic_json("Sacred Bark", &bark).contains("\"potion_potency\": 2"));
}

#[test]
fn sacred_bark_alone_changes_nothing() {
    // Without potions, a fight with Sacred Bark plays as one without it
    // (the relic baseline pin leaves Bark out for this reason).
    for e in [Encounter::JawWorm, Encounter::TwoLouse, Encounter::GremlinNob] {
        let mut a = fight_at(e, 50, 80, &[], false);
        let mut b = fight_at(e, 50, 80, &[], true);
        let (mut ra, mut rb) = (Rng::new(5), Rng::new(5));
        for _ in 0..200 {
            if a.is_over() {
                break;
            }
            let acts = a.legal_actions();
            assert_eq!(acts, b.legal_actions(), "{e:?}");
            let act = acts[ra.below(acts.len() as u32) as usize];
            rb.below(acts.len() as u32);
            a.step(act, &mut ra).unwrap();
            b.step(act, &mut rb).unwrap();
            a.advance(&mut ra);
            b.advance(&mut rb);
            assert_eq!((a.player.hp, a.player.block, a.hand, a.monsters), (b.player.hp, b.player.block, b.hand, b.monsters), "{e:?}");
        }
        assert_eq!(a.is_over(), b.is_over());
    }
}

/// FruitJuice.java: `increaseMaxHp(potency, true)`, potency 5
/// (docs/specs/fight-vocabulary.md step 5).
#[test]
fn fruit_juice() {
    let s = |hp, bark| {
        let mut s = fight_at(Encounter::JawWorm, hp, 80, &["Fruit Juice"], bark);
        drink(&mut s);
        (s.player.hp, s.player.max_hp)
    };
    assert_eq!(s(80, false), (85, 85));
    assert_eq!(s(50, false), (55, 85));
    assert_eq!(s(80, true), (90, 90));
    let mut f = fight_at(Encounter::JawWorm, 50, 80, &["Fruit Juice"], false);
    assert!(f.can_heal(), "a held Fruit Juice can still raise HP");
    drink(&mut f);
    assert!(!f.can_heal());
}

/// A fight against Jaw Worm (Chomp 11 first) at `hp` of `max_hp`, holding
/// `potions` and `relics` (by game name).
fn fight_holding(hp: i16, max_hp: i16, potions: &[&str], relics: &[&str]) -> CombatState {
    load();
    let gen = |v: &[&str]| v.iter().map(|p| format!("gen:{p}")).collect::<Vec<String>>();
    let (pn, rn) = (gen(potions), gen(relics));
    let rr: Vec<&str> = rn.iter().map(String::as_str).collect();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), hp, max_hp, Encounter::JawWorm, &relics_named(&rr).unwrap(), &mut Rng::new(3));
    let pr: Vec<&str> = pn.iter().map(String::as_str).collect();
    s.give_potions(&potions_named(&pr).unwrap()).unwrap();
    s
}

/// docs/specs/would-die.md step 2: Fairy in a Bottle (`potions/FairyPotion.java`:
/// `canUse()` false; `use` heals `(int)(maxHealth * potency / 100)`, at
/// least 1, potency 30; `AbstractPlayer.damage` uses it below 1 HP, before
/// Lizard Tail).
#[test]
fn fairy_in_a_bottle() {
    let saved = |mut s: CombatState| {
        next_turn(&mut s);
        s
    };
    // Never drunk by hand; Chomp at 5 HP: saved to 80 x 0.3, used up.
    let s = fight_holding(5, 80, &["Fairy in a Bottle"], &[]);
    assert!(!s.legal_actions().iter().any(|a| matches!(a, Action::UsePotion { .. })));
    assert!(!s.is_legal(Action::UsePotion { slot: 0, target: None }));
    assert!(s.clone().step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).is_err());
    assert!(s.can_heal(), "the bound counts the potion's heal");
    let s = saved(s);
    assert_eq!(s.player.hp, 24);
    assert!(s.player.potions.is_empty());
    // A hit that doesn't kill leaves it held.
    let s = saved(fight_holding(50, 80, &["Fairy in a Bottle"], &[]));
    assert_eq!((s.player.hp, s.player.potions.len()), (39, 1));
    // Sacred Bark: potency 60, 48 at 80.
    let s = saved(fight_holding(5, 80, &["Fairy in a Bottle"], &["Sacred Bark"]));
    assert_eq!(s.player.hp, 48);
    // Before an unused Lizard Tail: the Fairy saves, the counter stays -1.
    let s = saved(fight_holding(5, 80, &["Fairy in a Bottle"], &["Lizard Tail"]));
    assert_eq!((s.player.hp, s.player.relics.counter(0)), (24, -1));
    assert!(s.player.potions.is_empty());
    // With other potions held, only the Fairy goes.
    let s = saved(fight_holding(5, 80, &["Fire Potion", "Fairy in a Bottle"], &[]));
    assert_eq!(s.player.potions.iter().map(|p| p.name()).collect::<Vec<_>>(), ["gen:Fire Potion"]);
    // At 3 max HP, (int)(0.9) is 0: it heals 1.
    let s = saved(fight_holding(1, 3, &["Fairy in a Bottle"], &[]));
    assert_eq!(s.player.hp, 1);
    // Red Skull with Bark's 60%: from above half to above half, no
    // Strength; from at most half (its +3 at combat start) to above half,
    // the +3 goes (the game's `onBloodied` then `onNotBloodied`).
    let mut s = fight_holding(50, 80, &["Fairy in a Bottle"], &["Sacred Bark", "Red Skull"]);
    s.monsters[0].powers.add(Power::Strength, 100);
    let s = saved(s);
    assert_eq!((s.player.hp, s.player.powers.get(Power::Strength)), (48, 0));
    let mut s = fight_holding(30, 80, &["Fairy in a Bottle"], &["Sacred Bark", "Red Skull"]);
    assert_eq!(s.player.powers.get(Power::Strength), 3);
    s.monsters[0].powers.add(Power::Strength, 100);
    let s = saved(s);
    assert_eq!((s.player.hp, s.player.powers.get(Power::Strength)), (48, 0));
    // Load errors: another trigger, rows, an effect other than a heal.
    for (bad, want) in [
        (r#""trigger": "OwnerTurnStart", "effects": [{"Heal": 1}]"#, "trigger must be"),
        (r#""trigger": "OwnerDied", "effects": [{"Heal": 1}], "rows": [{"condition": "Always", "effects": [{"Heal": 1}]}]"#, "no rows"),
        (r#""trigger": "OwnerDied", "effects": [{"Block": 5}]"#, "heals only"),
    ] {
        let e = load_pack(&format!(r#"{{"version": 2, "potions": [{{"id": "fb-bad", "rarity": "rare", {bad}}}]}}"#)).unwrap_err();
        assert!(e.contains(want), "{e}");
    }
}

/// docs/specs/act1-singles.md section 4: Smoke Bomb (`potions/SmokeBomb.java`:
/// `canUse()` false when a monster in the room, dead ones included, is a
/// boss; `use` escapes and `AbstractRoom.endBattle` runs as for a win, so
/// `onVictory` (Burning Blood) and Meat on the Bone's `onTrigger` heal).
#[test]
fn smoke_bomb_escapes_a_hallway_fight_as_won() {
    // HP kept plus Burning Blood's 6; Jaw Worm keeps its HP.
    let mut s = fight("Smoke Bomb", false);
    let worm = s.monsters[0].hp;
    drink(&mut s);
    assert!(s.is_over() && s.won() && s.escaped);
    assert_eq!(s.player.hp, 56);
    assert_eq!(s.monsters[0].hp, worm);
    assert!(s.player.potions.is_empty());
    // At half HP Meat on the Bone's 12 first, then the 6.
    let mut s = fight_holding(40, 80, &["Smoke Bomb"], &["Meat on the Bone"]);
    drink(&mut s);
    assert!(s.won() && s.escaped);
    assert_eq!(s.player.hp, 58);
    // An elite fight too.
    let mut s = fight_at(Encounter::GremlinNob, 50, 80, &["Smoke Bomb"], false);
    drink(&mut s);
    assert!(s.won() && s.escaped);
    // A fight won by killing escapes nothing.
    let mut s = fight("Fire Potion", false);
    s.monsters[0].hp = 5;
    drink(&mut s);
    assert!(s.won() && !s.escaped);
}

#[test]
fn smoke_bomb_is_held_in_a_boss_fight() {
    use sts_engine::monsters::{slime_boss, MonsterKind as K};
    let usable = |s: &CombatState| s.legal_actions().iter().any(|a| matches!(a, Action::UsePotion { .. }));
    let mut s = fight_at(Encounter::SlimeBoss, 500, 500, &["Smoke Bomb"], false);
    assert!(!usable(&s) && !s.is_legal(Action::UsePotion { slot: 0, target: None }));
    // Nor after its split, where no slot holds it any more.
    s.monsters[0].hp = 70;
    s.monsters[0].set_move(slime_boss::SPLIT);
    next_turn(&mut s);
    assert!(s.monsters.iter().all(|m| m.kind != K::SlimeBoss));
    assert!(!usable(&s) && !s.is_legal(Action::UsePotion { slot: 0, target: None }));
    // The boss-fight mark keeps it, through the codec too; a fight without
    // such a potion carries no mark.
    assert!(s.boss_fight);
    assert_eq!(sts_engine::codec::decode(&sts_engine::codec::encode(&s)), s);
    assert!(!fight_at(Encounter::SlimeBoss, 50, 80, &["Fire Potion"], false).boss_fight);
    assert!(!fight("Smoke Bomb", false).boss_fight);
    // Every boss of the act, and only bosses.
    assert!([K::SlimeBoss, K::Hexaghost, K::TheGuardian].iter().all(|k| k.is_boss()));
    assert!(![K::JawWorm, K::GremlinNob, K::AcidSlimeL, K::SpikeSlimeL, K::None].iter().any(|k| k.is_boss()));
}

#[test]
fn an_escaped_state_round_trips() {
    use sts_engine::codec::{decode, encode, try_decode};
    let mut s = fight("Smoke Bomb", false);
    drink(&mut s);
    let bytes = encode(&s);
    assert_eq!(decode(&bytes), s);
    // The flag is the trailer's last byte; without it the state is a plain win.
    assert_eq!(bytes.last(), Some(&10));
    let mut plain = s.clone();
    plain.escaped = false;
    assert_eq!(encode(&plain), bytes[..bytes.len() - 1]);
    // Only a won fight carries it.
    let mut open = fight("Smoke Bomb", false);
    open.escaped = true;
    assert_eq!(try_decode(&encode(&open)), None);
}

#[test]
fn a_potion_fights_key_pairs_hallway_and_elite() {
    let bad = |f: &str| {
        let pack = format!(r#"{{"version": 2, "potions": [{{"id": "p5 fights", "rarity": "rare", "fights": {f}, "effects": ["Escape"]}}]}}"#);
        load_pack(&pack).unwrap_err()
    };
    assert!(bad(r#"["hallway"]"#).contains("hallway and elite together"));
    assert!(bad(r#"["elite", "boss"]"#).contains("hallway and elite together"));
    assert!(bad(r#"["boss"]"#).contains("hallway and elite together"));
    assert!(bad(r#"["tavern"]"#).contains("unknown fight kind"));
    assert!(bad("[]").contains("fights is empty"));
}
