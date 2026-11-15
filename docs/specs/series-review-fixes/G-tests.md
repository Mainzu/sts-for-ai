# Series review fixes, group G: tests that can't fail

Status: idea (2026-11-02, G1-G4 are in the backlog (part 3), not scheduled; decisions 'Series review fixes: the cut').

Part of `docs/specs/series-review-fixes.md`. Read that file first: it has the why, what must
stay true, the decisions, the build order and how to build and check. This file holds the
group's entries, then its build step details, the pins it may change, its decisions and the
notes its checker left. Line numbers are at `d9327a2`.

## Findings

### G1. statics_table_matches_fast_path mostly compares the row interpreter with itself

- **Severity:** low · **Reach:** future change · **New on this branch:** yes · **Review:** CONFIRMED by three verifiers, each of which replayed the test's exact sampling (review ids sw_tests_1, sw_core_4, sw_rules_2; cut by the 15 cap)
- **Where:** `engine/tests/statics.rs:18-79` in `statics_table_matches_fast_path` (the power ranges at :41-42, the attack assert at :56, the block check at :68-70, the count assert at :78). The routing that now sends almost every one of its checks to the interpreter: `engine/src/state.rs:1319-1321` in `attack_damage` and `:1600-1601` in `gain_block`. A second tautology: `engine/tests/packs.rs:174-175` in `negative_generated_add_static_counts`. Docs that cite the test as the check: `docs/decisions.md:1815-1819` and `:2300-2306`, `docs/extending.md:67-69`, and the comment at `engine/src/hooks.rs:295-297` (G2 rewrites that comment).

**What goes wrong.** The engine computes attack damage and card block in two ways. The *fast path* is hard-coded arithmetic for the five built-in modifiers: Strength, Weak and Vulnerable in `attack_damage`, Dexterity and Frail in `gain_block`. The *row interpreter* (`interpret_attack_damage`, state.rs:1367; `interpret_block`, :1398) reads every power's *static rows* through the combat's binding: `hooks::statics` for official powers, the pack's rows for generated ones. A static row is a `hooks::Static`, meaning "while this power exists, change this number". This test is the check the docs name for "the two agree".

Commit 662b6c6 changed the routing. `attack_damage` now hands the whole computation to the interpreter when either side holds a power in `GENERIC_STATICS` (Accuracy, Red Skull) or a *generated power* (a power from a content pack, bound into one of the reserved slots `Power::GEN`): `if self.generic_powers().any(|p| ps.get(p) != 0 || pd.get(p) != 0) { return self.interpret_attack_damage(src, dst, base); }`. `gain_block` does the same for the player: `if self.generic_powers().any(|g| p.get(g) != 0) { n = self.interpret_block(base); }`. But the test still sets `(Power::Accuracy, 0, 4)` and `(Power::RedSkull, 0, 3)` on the player and on every monster slot at every step. So an attack check reaches the fast path only when all four values are 0, and a block check only when the player's two are 0.

As a result, `assert_eq!(t.attack_damage(a, b, base), t.interpret_attack_damage(a, b, base), ...)` compares the interpreter with itself on 39,510 of its 39,630 attack checks. Only 120 checks reach the fast path. They come from 12 power setups and cover 18 of the 36 combinations of attacker Strength (−3..5), attacker Weak and target Vulnerable. The block check compares `interpret_block` with itself on 6,894 of its 7,286 checks. `assert!(checked > 20_000 && block_checked > 2_000, ...)` counts those comparisons too, so it would pass with no fast-path check at all.

Two kinds of bug now get through:
- a fast-path change confined to the combinations the 120 checks don't hit;
- any interpreter change that only shows while Accuracy or Red Skull is held. In those states nothing independent is compared, because the fast path never runs there.

Before 662b6c6 the fast path always ran and added Accuracy and Red Skull on top (`git show cfeb931:engine/src/state.rs`), so every check compared two implementations. The docs still describe that. `packs.rs:174-175` is a pure tautology too: the monster holds a generated power, so both sides of the assert are the interpreter. The assert just before it (`== 8`, :173) is the real check. The engine computes no wrong result today: the review's copies of both paths matched the engine on every check.

**Reproduce.** Each of these one-line planted bugs in `engine/src/state.rs` should make the test fail, but it passes. Copy the file aside first and copy it back after each one (build steps, "Before any step").
1. Fast-path bug: in `attack_damage` (state.rs:1324), change `if ps.get(Power::Weak) > 0 {` to `if ps.get(Power::Weak) > 0 && ps.get(Power::Strength) < 3 {`. This ignores Weak when the attacker has Strength 3 or more. Run `cargo test --release -p sts-engine --test statics -- statics_table_matches_fast_path`. Expected: fails. Actual: passes. In the 120 fast-path checks, an attacker with Weak only ever has Strength −1 or 1 (−2, −1, 0 or 2 when the target is also Vulnerable). Other tests, such as the golden games, may catch this particular bug. The point is that the test named as the check does not.
2. Interpreter bug: in `interpret_attack_damage`, swap the two `for` loops at state.rs:1370-1392 and leave the body as it is:
   ```rust
   for &p in powers {
       for (who, what, stage) in [
           (src, Modifies::DamageDealt, StaticStage::Add),
           (dst, Modifies::DamageTaken, StaticStage::Add),
           (src, Modifies::DamageDealt, StaticStage::Multiply),
           (dst, Modifies::DamageTaken, StaticStage::Multiply),
       ] {
           // the old body, unchanged: stacks, live, `continue`, the statics loop
       }
   }
   ```
   Powers now apply in `Power` order, and each add is scaled by the `den` built so far, so Accuracy's and Red Skull's adds (powers 21 and 22) land after the Weak and Vulnerable multiplies (powers 3 and 2). Strength (power 0) still comes first, so a state without Accuracy or Red Skull gives the same numbers. Expected: fails. Actual: `statics_table_matches_fast_path` passes, because whenever Accuracy or Red Skull is nonzero both sides of its assert are the interpreter. The review saw 0 mismatches in this test, while comparing the mutant with an unmutated copy of the interpreter over the same 39,630 checks flags 4,378. (`accuracy_adds_to_shivs_only` in the same file does fail: it gets 8 instead of 7.)

**Fix.** Change only `engine/tests/statics.rs`, `engine/tests/packs.rs` and one line of `docs/decisions.md`. Do not change the engine.
1. Imports in `engine/tests/statics.rs`: add `use std::collections::HashSet;` and `use sts_engine::cards::Tag;`, and change line 8 to `use sts_engine::hooks::{hooks, statics, Trigger, GENERIC_STATICS};`. `Stage`, `Who` and `MAX_MONSTERS` are already imported (line 10); `CombatState`, `Power`, `Pile`, `Rng` and `Encounter` come from `sts_engine::*`; `fresh`, `card` and `play` from `common`. (`CombatState::powers` is public, state.rs:1282.)
2. Add two reference functions. They write out the documented pipeline (decisions.md:1806-1814, the spec-4 entry: base, every add, the multiplies, round down once, never below 0) for the seven powers the test sets:
   ```rust
   /// Attack damage as the spec-4 pipeline writes it out, for the seven
   /// powers this file sets: base + Strength, + Accuracy while the player
   /// attacks with a Shiv in play, + Red Skull while the attacker is at half
   /// HP or below; then Weak x3/4 and Vulnerable x3/2; rounded down once,
   /// never below 0.
   fn want_damage(s: &CombatState, src: Who, dst: Who, base: i16) -> i16 {
       let (ps, pd) = (s.powers(src), s.powers(dst));
       let (hp, max) = match src {
           Who::Player => (s.player.hp, s.player.max_hp),
           Who::Monster(i) => (s.monsters[i as usize].hp, s.monsters[i as usize].max_hp),
       };
       let shiv = src == Who::Player
           && matches!(s.stage, Stage::PlayingCard { card, .. } if s.binding.def(card).has_tag(Tag::Shiv));
       let mut num = (base + ps.get(Power::Strength)) as i32;
       if shiv {
           num += ps.get(Power::Accuracy) as i32;
       }
       if 2 * hp <= max {
           num += ps.get(Power::RedSkull) as i32;
       }
       let mut den = 1;
       if ps.get(Power::Weak) > 0 {
           num *= 3;
           den *= 4;
       }
       if pd.get(Power::Vulnerable) > 0 {
           num *= 3;
           den *= 2;
       }
       (num.max(0) / den) as i16
   }

   /// Card block the same way (the player's powers): base + Dexterity, then
   /// Frail x3/4 of a total floored at 0; never below 0.
   fn want_block(s: &CombatState, base: i16) -> i16 {
       let p = &s.player.powers;
       let mut n = base + p.get(Power::Dexterity);
       if p.get(Power::Frail) > 0 {
           n = n.max(0) * 3 / 4;
       }
       n.max(0)
   }
   ```
   (The `card` binding in the `matches!` pattern shadows `common::card` inside the guard, as in golden.rs's `dump_state`; that compiles.)
3. Replace `statics_table_matches_fast_path` with this. The sampling changes in two lines only (`let generic` and the line after `pick`); every `pick` call still happens, so `s` plays exactly today's games and the totals stay 39,630 and 7,286. With `step % 4 < 2`, Shiv steps 0, 12 and 24 and Strike steps 9 and 21 can hold Accuracy, while Shiv steps 6 and 18 and Strike steps 3, 15 and 27 run on the fast path, so Accuracy is checked with a Shiv and with a non-Shiv in play.
   ```rust
   #[test]
   fn statics_table_matches_fast_path() {
       let mut rng = Rng::new(11);
       let (mut checked, mut block_checked, mut fast, mut block_fast) = (0, 0, 0, 0);
       let (mut combos, mut block_combos) = (HashSet::new(), HashSet::new());
       let encs = [Encounter::JawWorm, Encounter::Cultist, Encounter::TwoLouse, Encounter::GremlinNob, Encounter::SlimeBoss];
       for seed in 0..200u64 {
           let mut s = fresh(encs[seed as usize % encs.len()], seed);
           for step in 0..30 {
               if s.is_over() {
                   break;
               }
               // Accuracy and Red Skull on half the steps: a side holding one
               // takes the row interpreter, so the other half runs the fast
               // path. Every draw is still made, so the games are today's.
               let generic = step % 4 < 2;
               let mut t = s.clone();
               for who in [Who::Player].into_iter().chain((0..MAX_MONSTERS as u8).map(Who::Monster)) {
                   let p = match who {
                       Who::Player => &mut t.player.powers,
                       Who::Monster(i) => &mut t.monsters[i as usize].powers,
                   };
                   for (power, lo, hi) in [
                       (Power::Strength, -3, 5),
                       (Power::Dexterity, -2, 3),
                       (Power::Weak, 0, 1),
                       (Power::Vulnerable, 0, 1),
                       (Power::Frail, 0, 1),
                       (Power::Accuracy, 0, 4),
                       (Power::RedSkull, 0, 3),
                   ] {
                       let n = pick(&mut rng, lo, hi);
                       let n = if generic || !GENERIC_STATICS.contains(&power) { n } else { 0 };
                       p.add(power, n - p.get(power));
                   }
               }
               t.player.hp = pick(&mut rng, 1, t.player.max_hp);
               if step % 3 == 0 {
                   t.stage = Stage::PlayingCard { card: card(if step % 2 == 0 { "Shiv" } else { "Strike" }), target: Some(0), next: 0, hit: 0, x: 0, more: Default::default() };
               }
               for slot in t.living_slots().collect::<Vec<_>>() {
                   for base in [0, 1, 5, 6, 13] {
                       let m = Who::Monster(slot as u8);
                       for (a, b) in [(Who::Player, m), (m, Who::Player)] {
                           let want = want_damage(&t, a, b, base);
                           assert_eq!(t.interpret_attack_damage(a, b, base), want, "rows: {a:?}->{b:?} base {base} seed {seed} step {step}");
                           assert_eq!(t.attack_damage(a, b, base), want, "attack_damage: {a:?}->{b:?} base {base} seed {seed} step {step}");
                           checked += 1;
                           let (pa, pb) = (t.powers(a), t.powers(b));
                           if GENERIC_STATICS.iter().all(|&g| pa.get(g) == 0 && pb.get(g) == 0) {
                               fast += 1;
                               combos.insert((pa.get(Power::Strength), pa.get(Power::Weak), pb.get(Power::Vulnerable)));
                           }
                       }
                   }
               }
               for name in ["Defend", "Defend+"] {
                   let base = if name == "Defend" { 5 } else { 8 };
                   let mut u = t.clone();
                   u.stage = Stage::PlayerTurn;
                   u.pending = None;
                   u.hand = Pile::from_cards(&[card(name)]);
                   u.player.energy = 3;
                   u.player.block = 0;
                   let want = want_block(&u, base);
                   assert_eq!(u.interpret_block(base), want, "rows: {name} seed {seed} step {step}");
                   // Decided before play: the player holds no GENERIC_STATICS power.
                   let p = u.player.powers;
                   if GENERIC_STATICS.iter().all(|&g| p.get(g) == 0) {
                       block_fast += 1;
                       block_combos.insert((p.get(Power::Dexterity), p.get(Power::Frail), base));
                   }
                   play(&mut u, name, None);
                   assert_eq!(u.player.block, want, "{name} seed {seed} step {step}");
                   block_checked += 1;
               }
               let acts = s.legal_actions();
               let a = acts[rng.below(acts.len() as u32) as usize];
               s.step(a, &mut rng).unwrap();
           }
       }
       eprintln!("statics_table_matches_fast_path: {checked} attacks ({fast} fast path), {block_checked} blocks ({block_fast} fast path)");
       assert!(checked > 20_000 && block_checked > 2_000, "{checked} {block_checked}");
       assert!(fast > 10_000 && block_fast > 1_000, "fast path: {fast} attacks, {block_fast} blocks");
       assert_eq!((combos.len(), block_combos.len()), (36, 24), "Strength x Weak x Vulnerable, Dexterity x Frail x card on the fast path");
   }
   ```
   What the asserts mean: every check now compares two implementations with the written-out pipeline (the rows, and what play uses); about 45% of the checks run the fast path (estimate by reading: about 17,000-18,000 attacks and 3,300-3,600 blocks); and every Strength/Weak/Vulnerable combination (9 x 2 x 2 = 36) and every Dexterity/Frail/card combination (6 x 2 x 2 = 24) reaches the fast path. The official-only combats here have no generated powers, so "no `GENERIC_STATICS` power on either side" is exactly the engine's fast-path condition.
4. Delete `engine/tests/packs.rs:174-175` (the interpreter-against-interpreter assert). Keep the `== 8` assert on :173.
5. Add one line to the docs/decisions.md entry for this fix spec. No such entry exists yet: if no other group has added it, add it at the end of the file (the file is a log, newest last). Suggested text: "statics_table_matches_fast_path compared the interpreter with itself on 99.7% of attacks after the cross-spec fix; it now checks the fast path and the rows against the written-out pipeline, with Accuracy and Red Skull on half the steps, and asserts 10,000+ fast-path attacks covering every Strength/Weak/Vulnerable combination (packs.rs's interpreter-against-itself assert removed)." Leave the spec-4 entry as history. extending.md:67-69 is true again after this fix and needs no edit. G2 covers the hooks.rs comment.

Alternative: expose the fast path as its own public function and compare it with the interpreter on states without Accuracy or Red Skull. That edits `engine/src/state.rs`, one of the rules-fingerprint files, and still leaves Accuracy and Red Skull states with nothing independent to compare against. Do NOT restore the hybrid fast path that added Accuracy and Red Skull on top of the hard-coded code: 662b6c6 removed it because it mishandled negative generated adds and generated block multiplies under Frail (decisions.md:2300-2302). Do NOT just lower the thresholds or keep counting tautological checks.

**Test first.** `engine/tests/statics.rs::statics_table_matches_fast_path`, rewritten as above. The engine is correct today, so the rewritten test passes on unchanged code (by reading: `want_damage` and `want_block` equal both the interpreter and the fast path for these seven powers). Here "fails first" means it must fail with each planted bug from Reproduce, which today's version lets through. The test stops at its first mismatch: bug 1 fails an `attack_damage:` assert on the first fast check where the attacker holds Weak and Strength 3 or more (about one fast attacker draw in six); bug 2 fails a `rows:` assert on the first Accuracy or Red Skull check where Weak or Vulnerable changes the rounding. Copy `state.rs` back after each.

**Must stay unchanged.** The engine is unchanged, so all of these stay byte-identical: golden.txt's 9,000 games, golden_proving.txt, codec_golden.txt, series_check, the contract pins, H4 `two_turn_phases --check`, and the rules fingerprint. The test's totals must stay exactly 39,630 attacks and 7,286 blocks: three verifiers measured these with today's sampling (debug builds; release gives the same games), and a different total means a random draw was dropped or added. No pin changes.

### G2. GENERIC_STATICS is a hand-kept list that no test derives

- **Severity:** low · **Reach:** future change · **New on this branch:** yes · **Review:** CONFIRMED by reading (review id v24; cut by the 15 cap)
- **Where:** `engine/src/hooks.rs:295-298`, `pub const GENERIC_STATICS: [Power; 2] = [Power::Accuracy, Power::RedSkull];`. It is read by `generic_powers` (`engine/src/state.rs:1338-1340`), which gates the fast path in `attack_damage` (:1319) and `gain_block` (:1600). The pattern to copy is `engine/tests/replacements.rs:13-22`, `round_end_and_replacement_lists_match_the_tables`.

**What goes wrong.** `GENERIC_STATICS` lists the *official* powers (the 27 in `Power::ALL`, as opposed to generated ones) whose static rows the fast path does not hard-code. A side holding one of them sends the computation to the row interpreter (see G1 for both terms). The list is typed by hand. `hooks::statics` (hooks.rs:308-320) has rows for exactly the five built-ins plus Accuracy and Red Skull, so the list is right today.

Suppose a later edit gives another official power a static row and forgets the list (for example Byrd Flight as `mult(DamageTaken, 1, 2)`). Then every attack where neither side holds Accuracy, Red Skull or a generated power takes the fast path, which silently ignores the new row: a Strike into Flight deals 6 instead of 3. (For block, every play by a player holding none of them.) Meanwhile `interpret_attack_damage`, `interpret_block` and the opt-in static feature rows include it: `py/src/features.rs:973` writes `bd.statics(p)` for every held power when the static row kind is on. So the engine and what the net reads would disagree.

Nothing would fail. The other three hand lists (`ROUND_END_POWERS`, `ATTACKED_POWERS`, `REPLACEMENT_POWERS`) are each compared with a list that replacements.rs:13-22 derives from their tables, and two of their comments say so (hooks.rs:266, 270). No test mentions `GENERIC_STATICS`:
- `statics_table_matches_fast_path` sets only seven fixed powers.
- `packs.rs::every_official_power_round_trips` only compares each official power's rows with the rows it gets back from a generated slot; it computes no damage.
- The golden games replay on the fast path, so they would hide the change instead of flagging it.

Packs can't trigger this, because a pack power always takes a generated slot, and generated slots are always in `generic_powers`.

**Reproduce.** In `engine/src/hooks.rs`, add the arm `Power::Thorns => STRENGTH,` to `statics()`, before the `_ => &[],` arm (after it, the arm never matches). Thorns now has an "add 1 damage dealt per stack" row. Take a player holding Thorns 3 and no Accuracy or Red Skull: `attack_damage(Who::Player, Who::Monster(0), 6)` gives 6 on the fast path, while `interpret_attack_damage` gives 9. Run `cargo test --release -p sts-engine`. Expected: a failure naming the list. By reading, nothing fails: no test references `GENERIC_STATICS`; the Thorns tests in replacements.rs have monsters attack a player holding Thorns, and a `DamageDealt` row only counts for the attacker; the 'wraith' golden set (Caltrops, no Accuracy) replays on the fast path, and the 'accuracy' set never holds Thorns. Copy hooks.rs back afterwards: it is a rules-fingerprint file.

**Fix.** Add a test to `engine/tests/statics.rs` (G1 already adds `GENERIC_STATICS` to the hooks import):
```rust
#[test]
fn generic_statics_list_matches_the_table() {
    // The five built-ins `attack_damage` / `gain_block` hard-code.
    let fast = [Power::Strength, Power::Dexterity, Power::Weak, Power::Vulnerable, Power::Frail];
    let generic: Vec<Power> = Power::ALL.into_iter().filter(|&p| !statics(p).is_empty() && !fast.contains(&p)).collect();
    assert_eq!(generic, GENERIC_STATICS, "an official power with a static row must join hooks::GENERIC_STATICS (or the fast path must handle it)");
}
```
`Power::ALL` lists Accuracy (index 21) before RedSkull (22), so the derived list equals the constant today; a new entry must be listed in `Power::ALL` order. The existing `vulnerable_weak_frail_have_round_end_hooks` (statics.rs:112-121) already pins each built-in at exactly one row (`statics(p).len() == 1`), and G1's rewritten test checks those rows' values, so a changed or extra built-in row is caught there.

Rewrite the comment at hooks.rs:295-297 to say what the list means since 662b6c6, and that it is checked. Suggested text:
```rust
/// The official powers with static rows besides the five built-ins
/// (Strength, Dexterity, Weak, Vulnerable, Frail) that `attack_damage` /
/// `gain_block` hard-code: a side holding one of these, or a generated
/// power, takes the row interpreter for the whole computation (a test
/// checks this list against `statics`).
```
Change `///` comment lines only.

Alternatives: building the array in a `const fn` that scans `statics` puts more code in a fingerprinted rules file to get what one test gives. Computing the list per attack at run time defeats the fast path, which exists for speed. Do NOT drop the fast path. Optional, not required: one line in docs/extending.md's "Statics are rows" bullet saying an official power with other static rows joins `hooks::GENERIC_STATICS`; the test's message already says so.

**Test first.** `engine/tests/statics.rs::generic_statics_list_matches_the_table`. It passes on HEAD because the derived list is `[Accuracy, RedSkull]`. With the planted Thorns arm it fails, with the derived list `[Accuracy, RedSkull, Thorns]` on the left.

**Must stay unchanged.** Everything. The hooks.rs edit is comment-only, and the rules fingerprint strips comments (`solvedb/src/fingerprint.rs::strip_code`; `solvedb/tests/fingerprint.rs::fingerprint_tracks_rules` asserts that a `///` line and other comments don't count), so the fingerprint and the solved DB stay valid. Check that the diff of `engine/src/hooks.rs` from this step shows only `///` lines (build step 2). No pins change.

### G3. ai_reads_only_moves can't fail behind the move-distribution cache

- **Severity:** low · **Reach:** future change · **New on this branch:** yes. The test is the same as on main; the cache that empties it came on the branch in commit 06fc5c0. · **Review:** CONFIRMED by reading (review id v11; cut by the 15 cap)
- **Where:** `engine/tests/monsters.rs:157-218` in `ai_reads_only_moves` (the hand-typed `KINDS` at :163-182, the assert at :211). The cache is in `engine/src/chance.rs:90-109` in `move_distribution` (key at :101, hit at :102-104), and its doc comment (:90-92) names this test as the guard. The same rule backs `engine/src/heuristic.rs:164-215` (`rate_terms`, the `RATE_TERMS` cache, `damage_rate`). Docs relying on the test: `docs/decisions.md:1728-1731`, and `:1740-1741` already notes that its kind list is typed by hand.

**What goes wrong.** A monster's AI (`monsters::Ai`, monsters.rs:47-52) picks its next move. For every kind it is `pattern_ai` (monsters.rs:104-133), which reads the kind's pattern rows (its move rules written as table rows), the last two moves, the slot and the random roll. The engine assumes an AI reads nothing else. Commit 06fc5c0 made `move_distribution` (the probabilities of a monster's next move) cache its answer in a per-thread table under exactly that key: `let key = (m.kind, slot as u8, m.moves); if let Some(v) = CACHE.with(|c| c.borrow().get(&key).cloned()) { return v; }`.

The test builds a state `s`, then `t = s.clone()` with different HP, max HP, block, rolled damage, powers, allies, turn and player, keeping the same key. It then asserts `assert_eq!(s.move_distribution(slot), t.move_distribution(slot), ...)`. The left call runs first and fills the cache (or hits an entry an earlier call made: `fresh(Encounter::Cultist, 1)` has already cached Cultist, slot 0, `[NO_MOVE, NO_MOVE]`). The right call hits that entry and returns a clone of it without running the AI on `t`. So the assert compares a Vec with its own clone and can never fail. On main there was no cache, so the same test compared two AI runs.

Today's AIs obey the rule, so no result is wrong yet. But the planned pattern conditions (docs/specs/rules-engine-upgrade.md:381-386: turn below/above, HP below a fraction, phase, allies alive) all read state outside the key, and decisions.md:1716-1718 kept the AI signature open for such reads. When one of them lands, this test stays green. Meanwhile these callers would use whichever state first filled the key on that thread:
- the chance listing (chance.rs:284);
- `request_monster_move` (chance.rs:111-118), which sets a one-outcome move without rolling;
- the heuristic damage rate (heuristic.rs:175, itself cached per key in `RATE_TERMS`);
- the lookahead (agent.rs:140);
- the pattern feature rows (py/src/features.rs:995).

Sampled play (chance.rs:354-358) runs the AI on the real state, so it could pick moves the listing lacks.

**Reproduce.** Plant an HP-reading condition at `engine/src/monsters.rs:110`: change `FirstTurn => m.intent() == NO_MOVE,` to `FirstTurn => m.intent() == NO_MOVE || m.hp < 10,`. Now `t`, whose monster has HP 7, gets the opening move for every move history from the kinds whose pattern starts with a `FirstTurn` row (for example Cultist, Jaw Worm and Gremlin Nob), while `s` (HP 40) does not. Run `cargo test --release -p sts-engine --test monsters -- ai_reads_only_moves`. Expected: fails. Actual: passes. Copy monsters.rs back afterwards: it is a rules-fingerprint file.

**Fix.** Change only `engine/tests/monsters.rs`. Call the AI itself on both states, as `traced` already does in `engine/tests/patterns.rs:34-41`, and keep one check on the cache. Replace the test with this (the lines that build `s` and `t` are today's :191-210, unchanged):
```rust
/// `monsters::Ai`'s rule, which `chance::move_distribution` and
/// `heuristic::damage_rate` cache on: an AI reads only its monster's kind,
/// slot and move history. Every kind, slot and move pair gives the same
/// distribution when everything else changes. The AI is called directly:
/// `move_distribution` would answer `t` from the entry `s` cached.
#[test]
fn ai_reads_only_moves() {
    use sts_engine::codec::MONSTER_KINDS;
    use sts_engine::rng::enumerate;
    use sts_engine::state::MAX_MONSTERS;
    let base = fresh(Encounter::Cultist, 1);
    let mut checked = 0;
    for kind in MONSTER_KINDS.into_iter().filter(|&k| k != MonsterKind::None) {
        let ai = kind.def().ai;
        let n = kind.def().moves.len() as MoveId;
        let ids: Vec<MoveId> = std::iter::once(NO_MOVE).chain(0..n).collect();
        for slot in 0..MAX_MONSTERS {
            for &a in &ids {
                for &b in &ids {
                    let mut s = base.clone();
                    s.monsters = Default::default();
                    s.monsters[slot] = Monster::new(kind, 40);
                    s.monsters[slot].moves = [a, b];
                    let mut t = s.clone();
                    let m = &mut t.monsters[slot];
                    m.hp = 7;
                    m.max_hp = 90;
                    m.block = 12;
                    m.rolled_damage = 6;
                    m.powers.add(Power::Strength, 3);
                    m.powers.add(Power::Weak, 2);
                    m.powers.add(Power::Vulnerable, 1);
                    for other in (0..MAX_MONSTERS).filter(|&o| o != slot) {
                        t.monsters[other] = Monster::new(MonsterKind::JawWorm, 30 + other as i16);
                    }
                    t.turn += 5;
                    t.player.hp -= 20;
                    t.player.block = 9;
                    t.player.powers.add(Power::Strength, 2);
                    let want = enumerate(|c| ai(&s, slot, c));
                    assert_eq!(enumerate(|c| ai(&t, slot, c)), want, "{kind:?} slot {slot} moves {:?}", [a, b]);
                    // The cache, keyed (kind, slot, moves), gives the AI's own answer.
                    assert_eq!(t.move_distribution(slot), want, "cached: {kind:?} slot {slot} moves {:?}", [a, b]);
                    checked += 1;
                }
            }
        }
    }
    assert!(checked > 1000);
}
```
Notes:
- `sts_engine::rng::enumerate` is public (rng.rs:117) and returns `Vec<(MoveId, f64)>`, the same type as `move_distribution`.
- The second assert is a real check of the cache key: if the key ever lost `slot`, Sentry's slot-1 call would hit slot 0's entry (Bolt) while the AI on `s` says Beam, and it fails.
- Iterating `codec::MONSTER_KINDS` without `MonsterKind::None` gives today's 18 kinds in today's order, so `checked` is unchanged. Unlike the hand-typed `KINDS`, it stays complete: a new `MonsterKind` is a compile error in codec.rs's exhaustive `kind_listed` match, whose comment says to add it to `MONSTER_KINDS`, and a kind missing there can't be decoded. `patterns.rs::tables_match_old_ais` already iterates it. This settles the optional note at decisions.md:1740-1741.
- Optional, comment-only: the `monsters::Ai` doc (monsters.rs:47-51) could name `chance::move_distribution`'s cache next to `heuristic::damage_rate`. monsters.rs is a fingerprint file; `///` lines don't change the fingerprint (check as in G2).

Alternatives: a public uncached function or a cache reset in `engine/src/chance.rs` edits a rules-fingerprint file for a test's sake. A `debug_assert!` that re-runs the AI on every cache hit is off in the release builds the project tests with, and it would slow debug runs. Do NOT remove or narrow the cache.

**Test first.** `engine/tests/monsters.rs::ai_reads_only_moves`, rewritten. It passes on today's code, because every AI reads only the key. With the planted HP condition it fails early at its first assert: Cultist, slot 0, moves `[INCANTATION, NO_MOVE]` (printed `[0, 255]`). There `s` gives Dark Strike and `t` gives Incantation.

**Must stay unchanged.** Everything; this is a test-only change. No pins change.

### G4. The codec round trip never meets proving cards, so the series' new state shapes are not fuzzed

- **Severity:** low · **Reach:** future change · **New on this branch:** yes · **Review:** CONFIRMED with a run of the same checks on proving decks (review id sw_tests_4; cut by the 15 cap)
- **Where:**
  - `engine/tests/codec.rs:17-28` in `deck`: `let pool: Vec<CardId> = class_cards(character.class()).collect();` at :21. It is used by `game_states` (:30-52) for `codec_roundtrip` (:54-95) and `golden_states` (:112-122).
  - `engine/src/cards.rs:645-647`, `class_cards`, which leaves proving cards out (`... && !c.def().proving`). This is pinned by `engine/tests/amounts.rs:106-116`, `proving_cards_in_no_pool`.
  - `engine/tests/fuzz.rs:13-27` adds proving cards to its decks, but its `check_invariants` (`engine/tests/common/mod.rs:55-92`) never encodes a state or lists outcomes.

**What goes wrong.** *Proving cards* are cards the series added to exercise new engine features: Whirlwind, Hologram, Headbutt, Rampage and Protect (Ironclad class), and Accuracy, Wraith Form, Caltrops, Survivor and Burst (Silent), at cards.rs:528-550. They are the only content that produces the series' new state shapes:
- an X-cost card in play with X > 0, which the codec writes as stage tag 7;
- a card in play with a pick, replays or a replayed copy (stage tag 8);
- a *known top* of the draw pile (cards known to be on top, for example put there by Headbutt) with *floaters* (cards shuffled in under it whose position is uncertain);
- *variants*: per-copy cards such as Rampage at 13 damage. They are held in four slots of the *binding* (the per-combat table that maps card ids to cards) at reserved ids starting at `registry::VARIANT_BASE` (144 today).

The known top and the variants are written as optional *trailer sections* at the end of an encoding: section 1 is the known top, section 2 the variants (`engine/src/codec.rs:219-244`, read back at `:428-458`).

`codec_roundtrip` is the randomized test that checks every reachable state: it must decode equal, re-encode to the same bytes, and have its encoding refused when cut by one byte. It builds decks from `class_cards` only. The review replayed its generator: 102,376 states, and not one has any of these shapes. They are round-tripped only by four hand-built single-feature tests, which check decode equality (two also compare lengths); none re-encodes or cuts the bytes:
- `amounts.rs:78` `x_survives_codec_round_trip`;
- `decisions.rs:107` `codec_round_trips_picks_and_replays`;
- `known_top.rs:119` `codec_round_trips_top` (a known top, no variants);
- `overrides.rs:73` `codec_round_trips_variants` (variants, no known top).

No test encodes a state that carries both trailer sections, or a top whose variant was renumbered. (`renumber_variant`, state.rs:1189-1204, moves a variant to a new id when a lower-valued variant takes a slot below it or a lower slot is freed; the top is updated at :1198.) So a codec, top or variant regression that only shows on combined states passes `cargo test`.

Nothing is wrong today. The review ran the same checks on 151,641 states from decks with proving cards: every one round-tripped, re-encoded identically and refused truncation, and the listed outcomes summed to 1 and matched sampling. Two corrections to the original finding:
- In the review's proving decks, random play reached no tag-7 state and no floater, so tag 7 needs a hand-built state. (The decks below add Wild Strike, so floaters may appear; they are counted, not asserted.)
- States with a content pack bound can't be encoded by design (`encode` asserts `binding.is_empty()`, codec.rs:132), so packs stay out of this test.

**Reproduce.**
1. Counting: in `codec_roundtrip`, count states with a tag-8 stage, a non-empty `s.top`, or `s.binding.n_variants() > 0`. By the review's replay, all three counts are 0.
2. A regression the suite misses: in `try_decode`, change the line `if tag <= last {` (codec.rs:432 at HEAD; find it by its text, since group E's decoder fixes may move it) to `if last != 0 {`, so the decoder refuses any second trailer section. Run `cargo test --release -p sts-engine`. Expected: a failure. By reading, everything passes, because no Rust test (engine or solvedb) encodes a state with both a known top and variants. Copy the file back afterwards.
3. The combined state the tests should cover. The review built it by hand, and every step round-tripped:
   - Setup: one Jaw Worm at 200 HP; hand Rampage, Rampage, Headbutt, Headbutt, Wild Strike; draw pile Strike, Defend; energy 9.
   - Play a Rampage: its copy grows to 13 and goes to the discard pile (id 144).
   - Move that copy to hand and play it: it grows to 18 and holds slot 0 (still id 144).
   - Play Headbutt and choose the 18: the known top is [18].
   - Play Wild Strike: a Wound floater lands under the top.
   - Play the other Rampage: it grows to 13, which sorts before 18, so it takes slot 0 and the 18 on top is renumbered from `VARIANT_BASE` to `VARIANT_BASE + 1` (ids 144 and 145 at HEAD).
   - Play Headbutt again: the card pauses at its pick, so the state has a tag-8 stage and both trailer sections.
   - Choose the 13: the known top becomes [13, 18], and the floater's `above` count is 1.
   - Drawing 2 now lists {13, Wound} at 0.25 and {13, 18} at 0.75.

**Fix.** Change only `engine/tests/codec.rs`.
1. Make `game_states` take the deck: `fn game_states(character: Character, deck: &[CardId], enc: Encounter, seed: u64, search: bool, out: &mut Vec<CombatState>)`, with `CombatState::new_as(character, deck, hp, hp, enc, &mut rng)` inside. `codec_roundtrip` passes `&deck(character, seed)` and `golden_states` passes `&deck(character, 1_000 + i as u64)`, exactly as today (`deck` uses its own `Rng`), so their states stay the same, and so would a future re-record of codec_golden.txt.
2. In `game_states`, before keeping a `Listed(v)` set of outcomes, assert that their probabilities sum to 1 within 1e-9, the tolerance `engine/tests/chance.rs:18` uses:
   ```rust
   if let Some(ChanceOutcomes::Listed(v)) = t.chance_outcomes(8) {
       let sum: f64 = v.iter().map(|x| x.0).sum();
       assert!((sum - 1.0).abs() < 1e-9, "listed outcomes sum to {sum}");
       out.extend(v.into_iter().map(|(_, u)| u));
   }
   ```
   If this fails on today's states, report it as a new defect; don't loosen the tolerance.
3. Move the per-state checks of `codec_roundtrip` into a helper that takes a label, so a failure still names its state:
   ```rust
   /// Encodes `s` and checks the bytes: the version first, decoding to an
   /// equal state that encodes to the same bytes, refused when cut by one
   /// byte. Returns the length.
   fn round_trips(s: &CombatState, what: &str) -> usize {
       let b = encode(s);
       assert_eq!(b[0], CODEC_VERSION, "{what}");
       let back = decode(&b);
       assert_eq!(&back, s, "{what} doesn't round-trip");
       assert_eq!(encode(&back), b, "{what} re-encodes differently");
       assert!(try_decode(&b[..b.len() - 1]).is_none(), "{what}: a truncated encoding decodes");
       b.len()
   }
   ```
   In `codec_roundtrip`, keep the `no_death` tweak, then `let n = round_trips(s, &format!("state {i}")); total += n; max = max.max(n);` and the other stats as today.
4. Add the decks, with `mod common; use common::*;` at the top of codec.rs (for `vs`, `card` and `play`; no name clashes with codec.rs's own items) and `use sts_engine::registry::{Overrides, VARIANT_BASE};`:
   ```rust
   /// The starter plus every proving card of the class (base and upgraded),
   /// and Wild Strike for the Ironclad (its Wound under a Headbutt top is a
   /// floater): decks that reach the series' state shapes.
   fn proving_deck(character: Character) -> Vec<CardId> {
       let mut d = character.starter_deck();
       d.extend(CardId::all().filter(|c| c.def().proving && c.def().class == character.class()));
       if character == Character::Ironclad {
           d.push(card("Wild Strike"));
       }
       d
   }
   ```
5. Add `codec_roundtrip_proving_decks`: random play only, seeds from 0 upward over `Character::ALL` x `Encounter::ALL`, until there are 50,000 states:
   ```rust
   #[test]
   fn codec_roundtrip_proving_decks() {
       let mut states = Vec::new();
       let mut seed = 0u64;
       while states.len() < 50_000 {
           for character in Character::ALL {
               let d = proving_deck(character);
               for enc in Encounter::ALL {
                   game_states(character, &d, enc, seed, false, &mut states);
               }
           }
           seed += 1;
       }
       let (mut tag8, mut top, mut variants, mut both, mut floaters) = (0, 0, 0, 0, 0);
       for (i, s) in states.iter().enumerate() {
           round_trips(s, &format!("proving state {i}"));
           tag8 += matches!(s.stage, Stage::PlayingCard { more, .. } if more != Default::default()) as usize;
           let (t, v) = (!s.top.is_empty(), s.binding.n_variants() > 0);
           top += t as usize;
           variants += v as usize;
           both += (t && v) as usize;
           floaters += s.top.floaters().next().is_some() as usize;
       }
       eprintln!("codec_roundtrip_proving_decks: {} states; tag-8 {tag8}, top {top}, variants {variants}, top and variants {both}, floaters {floaters}", states.len());
       assert!(tag8 > 100 && top > 100 && variants > 100 && both > 0, "the proving decks no longer reach the new shapes");
   }
   ```
   (`more != Default::default()` is exactly the codec's tag-8 condition. Floaters are printed, not asserted.)
6. Add `codec_round_trips_combined_trailers`, the sequence from Reproduce step 3. Assert the top and the slots after the renumber before that step's round trip, so a lost top update fails at the assert:
   ```rust
   #[test]
   fn codec_round_trips_combined_trailers() {
       let (v0, v1) = (CardId(VARIANT_BASE as u8), CardId(VARIANT_BASE as u8 + 1));
       let rampage = |damage| Some((card("Rampage"), Overrides { damage }));
       let mut s = vs(&[MonsterKind::JawWorm], &["Rampage", "Rampage", "Headbutt", "Headbutt", "Wild Strike"], Some(200));
       s.draw = Pile::from_cards(&[card("Strike"), card("Defend")]);
       s.player.energy = 9;
       play(&mut s, "Rampage", Some(0));
       assert_eq!(s.binding.variant_of(v0), rampage(13));
       s.discard.remove(v0, 1);
       s.hand.add(v0, 1);
       s.apply_action(Action::Play { card: v0, target: Some(0) }).unwrap();
       assert_eq!(s.binding.variant_of(v0), rampage(18));
       play(&mut s, "Headbutt", Some(0));
       s.apply_action(Action::Choose(v0)).unwrap();
       play(&mut s, "Wild Strike", Some(0));
       round_trips(&s, "after Wild Strike");
       play(&mut s, "Rampage", Some(0));
       assert_eq!(s.top.known().collect::<Vec<_>>(), vec![v1], "the 18 on top was renumbered");
       assert_eq!((s.binding.variant_of(v0), s.binding.variant_of(v1)), (rampage(13), rampage(18)));
       round_trips(&s, "after the renumber");
       play(&mut s, "Headbutt", Some(0));
       assert!(matches!(s.stage, Stage::PlayingCard { more, .. } if more.pick.is_some()));
       assert!(!s.top.is_empty() && s.binding.n_variants() == 2);
       round_trips(&s, "at the pick");
       let mut tag7 = s.clone();
       tag7.stage = Stage::PlayingCard { card: card("Whirlwind"), target: None, next: 0, hit: 0, x: 2, more: Default::default() };
       round_trips(&tag7, "tag 7 with both trailer sections");
       s.apply_action(Action::Choose(v0)).unwrap();
       assert_eq!(s.top.known().collect::<Vec<_>>(), vec![v0, v1]);
       assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(card("Wound"), 1)]);
       round_trips(&s, "after the choice");
       let mut t = s.clone();
       t.hand = Pile::default();
       t.pending = Some(ChanceEvent::Draw { n: 2 });
       let Some(ChanceOutcomes::Listed(v)) = t.chance_outcomes(100) else { panic!("drawing 2 isn't listed") };
       let held = |c: CardId| v.iter().filter(|(_, u)| u.hand.count(c) > 0).map(|(p, _)| p).sum::<f64>();
       for (c, want) in [(v0, 1.0), (card("Wound"), 0.25), (v1, 0.75)] {
           assert!((held(c) - want).abs() < 1e-12, "{c:?} drawn with {} not {want}", held(c));
       }
       for (_, u) in &v {
           round_trips(u, "a draw-2 outcome");
       }
   }
   ```
   Both choices are `Action::Choose(v0)`: the first time v0 is the 18, the second time (after the renumber) the 13. Don't use the `draws()` helper from known_top.rs: `CardId::name()` returns "<generated>" for both variants, so it can't tell them apart.

Do NOT add proving cards to `deck()`'s pool for every caller: `codec_roundtrip`'s states would change, and the next codec_golden.txt re-record would mix a content change into a format change. Do NOT put proving cards into `class_cards`: they stay out of every training pool, as `amounts.rs::proving_cards_in_no_pool` pins. Do NOT re-record codec_golden.txt.

**Test first.** `engine/tests/codec.rs::codec_round_trips_combined_trailers` and `engine/tests/codec.rs::codec_roundtrip_proving_decks`. The codec is correct today, so both pass on HEAD; if either fails on HEAD with no planted bug, that is a new codec, top or variant defect: stop and report it with the failing state instead of weakening the test. With the planted decoder bug from Reproduce step 2, both fail: the combined test panics in `decode` ("not an encoded combat state of this codec version") at its first round trip, after Wild Strike; the proving-deck test at its first state holding both sections. If you instead delete the line `self.top.map_cards(|c| if c == a { b } else { c });` in `renumber_variant` (state.rs:1198), the combined test fails at its top assert right after the renumber (it finds `[v0]`). Copy both source files back afterwards.

**Must stay unchanged.** The engine is unchanged. codec_golden.txt must stay byte-identical and `codec_golden` must pass. `codec_roundtrip` must print the same stats line before and after (same decks and seeds). Golden, golden_proving, series_check, the contract pins, H4 and the fingerprint are untouched. The codec test binary gains about 50,000 states of random play, which takes seconds in release. No pins change.

## Build step details

**Before any step.**
- Work in the worktree root (`.claude/worktrees/engine-next`). Rust checks are `cargo test --release` (engine + solvedb). Release builds use fat LTO, so each rebuild after a planted bug takes a minute or more; `-p sts-engine --test <name>` builds and runs one test binary.
- Prefer starting from a clean tree (other groups' changes committed) and note that commit as BASE, so the diff checks below show only this group's edits.
- Planted bugs (the proofs that a new test can fail): before editing an engine file, `mkdir -p target/planted && cp engine/src/<f>.rs target/planted/<f>.rs.orig` (target/ is gitignored). Afterwards `cp target/planted/<f>.rs.orig engine/src/<f>.rs && cmp target/planted/<f>.rs.orig engine/src/<f>.rs`. Never restore with `git checkout` or `git restore`: another group's uncommitted edits to the same file would be lost. state.rs, hooks.rs and monsters.rs are rules-fingerprint files.
- Find each planted line by its text; the line numbers are HEAD's (b2c322a).
- Interactions with other groups: C5 may change `static_holds` for `CardInPlayTagged`; official Accuracy is a DamageDealt row on the attacker, so its values and G1's `want_damage` stay right. E3/E5 edit `try_decode`, which can move the G4 planted line. If the optional cleanups are picked: K c06 (one interpreter) must keep the names `interpret_attack_damage` / `interpret_block` that G1 calls; K c18 (a non-Vec return from `move_distribution`) needs `.to_vec()` in G3's second assert; K c11 (dropping tag 7) would change the codec format and take G4's tag-7 case with it.

**Step 1, G1: rewrite `statics_table_matches_fast_path`.** Files: `engine/tests/statics.rs` (imports `HashSet`, `Tag`, `GENERIC_STATICS`; reference functions `want_damage` / `want_block`; the rewritten test as given), `engine/tests/packs.rs` (delete :174-175), `docs/decisions.md` (the G1 line, in this fix spec's entry; create the entry at the end of the file if no other group has). Non-test lines: 1 (docs).
- Acceptance: `cargo test --release -p sts-engine --test statics -- statics_table_matches_fast_path --nocapture 2>&1 | grep '^statics_table_matches_fast_path:'` prints `39630 attacks (F fast path), 7286 blocks (B fast path)` with F above 10,000 (estimate 17,000-18,000) and B above 1,000 (estimate 3,300-3,600). The totals must be exactly 39630 and 7286; a different total means a random draw was dropped or added. `cargo test --release -p sts-engine --test statics` and `--test packs` pass.
- Proof it can fail: back up `engine/src/state.rs`. Plant bug 1 (`if ps.get(Power::Weak) > 0 && ps.get(Power::Strength) < 3 {` in `attack_damage`), rerun the statics command: it fails on an `attack_damage:` assert. Restore. Plant bug 2 (swap the two `for` loops in `interpret_attack_damage`, body unchanged), rerun: it fails on a `rows:` assert. Restore and `cmp`.

**Step 2, G2: check `GENERIC_STATICS` against the table.** Files: `engine/tests/statics.rs` (new `generic_statics_list_matches_the_table`), `engine/src/hooks.rs` (the doc comment at :295-297 only). Non-test lines: about 5 comment lines.
- Acceptance: `cargo test --release -p sts-engine --test statics -- generic_statics_list_matches_the_table` passes.
- Proof it can fail: back up hooks.rs, add the arm `Power::Thorns => STRENGTH,` to `statics()` before `_ => &[],`; the test fails with `[Accuracy, RedSkull, Thorns]` against `[Accuracy, RedSkull]`. Restore and `cmp`.
- Fingerprint check: `git diff -U0 BASE -- engine/src/hooks.rs | grep -E '^[-+][^-+]' | grep -vE '^[-+]\s*///'` prints nothing (only doc-comment lines changed; the rules fingerprint strips comments).

**Step 3, G3: call the AI directly in `ai_reads_only_moves`.** Files: `engine/tests/monsters.rs` (the rewritten test as given: `enumerate` over `kind.def().ai` on `s` and `t`, the cache checked against it, kinds from `codec::MONSTER_KINDS` without `None`, the doc comment naming both caches). Non-test lines: 0.
- Acceptance: `cargo test --release -p sts-engine --test monsters -- ai_reads_only_moves` passes.
- Proof it can fail: back up `engine/src/monsters.rs`, change `FirstTurn => m.intent() == NO_MOVE,` to `FirstTurn => m.intent() == NO_MOVE || m.hp < 10,`. The test fails at Cultist slot 0 moves [0, 255]. Restore and `cmp`.

**Step 4, G4: proving decks and a combined state in the codec tests.** Files: `engine/tests/codec.rs` only (`mod common; use common::*;`, the registry import, `game_states` takes the deck, the listing-sum assert, `round_trips`, `proving_deck`, `codec_roundtrip_proving_decks`, `codec_round_trips_combined_trailers`). Non-test lines: 0.
- Before editing, save the baseline: `cargo test --release -p sts-engine --test codec -- codec_roundtrip --exact --nocapture 2>&1 | grep '^codec_roundtrip:' > target/planted/codec_roundtrip.before`. After editing, the same command must print the identical line (`diff` against the saved file).
- `cargo test --release -p sts-engine --test codec -- --nocapture` passes and prints the `codec_roundtrip_proving_decks:` counts (tag-8, top and variants each > 100; top and variants > 0). If a new test fails on HEAD with no planted bug, stop: it is a new defect to report, not a threshold to lower.
- `git diff --exit-code engine/tests/data/codec_golden.txt` exits 0.
- Proof it can fail: back up `engine/src/codec.rs`, change `if tag <= last {` in `try_decode` to `if last != 0 {`. Both new tests fail (`decode` panics). Optionally confirm the gap: with that bug, every other engine test still passes. Restore and `cmp`. Optionally also back up state.rs and delete the `self.top.map_cards(...)` line in `renumber_variant`: the combined test fails at its top assert after the renumber. Restore and `cmp`.

**Step 5, the whole group.**
- `cargo test --release` (engine and solvedb) passes.
- `git diff --stat BASE -- engine/src` lists only `engine/src/hooks.rs` (comment lines) from this group.
- No planted text is left: `grep -nE 'Strength\) < 3|m\.hp < 10|last != 0|Thorns => STRENGTH' engine/src/*.rs` prints nothing, and every `target/planted/*.orig` matches its source file (`cmp`).
- In this fix spec's docs/decisions.md entry, next to G1's line, add one line each (suggested): G2 "GENERIC_STATICS is now checked against hooks::statics (statics.rs generic_statics_list_matches_the_table)." G3 "ai_reads_only_moves called move_distribution, whose cache answered the changed state from the first state's entry; it now runs each kind's AI on both states (kinds from codec::MONSTER_KINDS) and checks the cache against it." G4 "The codec round trip also runs 50,000 states from proving decks (picks, known tops, variants) and a hand-built state with both trailer sections, a renumbered top and tag 7; listed outcomes are checked to sum to 1."

## Pins for this group

None. No engine code changes in this group. The only edit under engine/src is a doc comment on GENERIC_STATICS in engine/src/hooks.rs, and the rules fingerprint strips comments (solvedb/src/fingerprint.rs::strip_code; solvedb/tests/fingerprint.rs::fingerprint_tracks_rules asserts this).

These must stay byte-identical:
- engine/tests/data/golden.txt (the 9,000 games) and golden_proving.txt;
- engine/tests/data/codec_golden.txt (don't set CODEC_GOLDEN_RECORD; golden_states keeps today's decks);
- series_check (heuristic, contract nets and old feature columns), the contract pins, and H4 `two_turn_phases --check`;
- the rules fingerprint, and with it the solved DB.

Two printed outputs must also stay exactly as they are. The rewritten statics test must still visit 39,630 attack and 7,286 block checks (it keeps every random draw). codec_roundtrip's stats line must be the same before and after (same decks and seeds).

The planted bugs used to prove the new tests can fail touch engine/src/state.rs, hooks.rs and monsters.rs (all rules-fingerprint files) and engine/src/codec.rs. Each must be copied back from its backup before moving on (never via git checkout), or the fingerprint and the golden games change.

## Decisions for this group

None. All four fixes change only tests, one hooks.rs doc comment and the decisions log, and each is cheap to undo. Two choices are made in the entries and need no owner decision: G1 checks the engine against the pipeline written out in the test, rather than exposing the fast path as an engine function, which keeps the rules files and the fingerprint untouched; G4 adds a separate proving-deck round trip rather than changing the existing deck pool, which keeps codec_golden.txt's generator stable.

## Notes the checker left

Nothing blocks a builder. Some numbers were estimated by reading, not by running: G1's fast-path counts (about 17,000-18,000 attacks and 3,300-3,600 blocks, against thresholds of 10,000 and 1,000) and G4's proving-deck shape counts (expected in the hundreds to thousands, against thresholds of 100, 100, 100 and 1). If a threshold fails on HEAD with no planted bug, print the counts and check the sampling code first. Don't lower a threshold without saying why in the decisions entry. Whether random play with the new proving decks reaches floaters is unknown, so it is printed but not asserted.
