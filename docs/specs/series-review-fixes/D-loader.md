# Series review fixes, group D: pack loader validation

Status: confirmed (2026-11-02, D1-D7 (D7 widened to pack hooks) are in the generator-hardening bundle, unbuilt; decisions 'Series review fixes: the cut').

Part of `docs/specs/series-review-fixes.md`. Read that file first: it has the why, what must
stay true, the decisions, the build order and how to build and check. This file holds the
group's entries, then its build step details, the pins it may change, its decisions and the
notes its checker left. Line numbers are at `d9327a2`.

## Findings

### D1. Search ignores the node cap inside a long pick from a pack card

- **Severity:** medium · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED; the verifier ran a throwaway test (review id v06, reported #6)
- **Where:** `engine/src/search.rs:235-239` in `Tree::expand` (the node-cap exemption for picks). The fix goes in the same function's decision branch, `search.rs:259-270`, plus the comments at `search.rs:36` (the `max_nodes` doc comment) and `:236-237`. Related:
  - `engine/src/state.rs:623-626` in `apply_action`: a DiscardToTop choice pushes the card onto the known top.
  - `engine/src/state.rs:263-272` in `Top::push`.
  - `engine/src/state.rs:538-546` in `legal_actions`: the options at a pick.
  - `engine/src/registry.rs:650-658` in `parse_effect`: a pack `Pick` takes any `n`, any kind and either value of `exact`.
  - Docs that state the wrong bound: `docs/specs/rules-engine-upgrade.md:24` and `:213-220`, `docs/extending.md:94-97`, `docs/decisions.md:1937-1938`.

**What goes wrong.** Search (`search::search`, a depth-limited expectimax) builds a tree of states. Once the tree holds `SearchConfig.max_nodes` nodes (the node cap, default 50,000), every further unexpanded state becomes a leaf that the evaluator scores. A state paused at a pick is exempt from the cap. A pick is a card that pauses so the player can choose cards (`Effect::Pick`, answered with `Action::Choose` / `Done`). The exemption exists so that no evaluator ever scores a half-resolved card:

`} else if self.nodes.len() >= self.cfg.max_nodes && s.pick().is_none() {`, with the comment "the subtree is bounded, see the decision-points spec".

The docs say the transposition cache bounds that subtree. (The transposition cache is the memo that merges equal states.) The claimed bound is that sequential picks collapse to sub-multisets of the hand, about 1,024 at most. That holds only for DiscardFromHand.

A DiscardToTop pick moves a card from the discard pile onto the top of the draw pile, where its position is known (the known top). Each choice runs `self.top.push(c)`, which puts the card in front of the cards already known. `Top` derives `PartialEq`, `Eq` and `Hash`, so states that differ only in that order are different states. So n picks from d distinct discard cards make d!/(d-n)! distinct states. Every one of them is still at a pick, so the cap never stops them.

ReturnFromDiscard ignores order, but it ranges over sub-multisets of the discard pile, up to the hand's free space. That also passes 1,024 once the discard pile holds more than about 10 distinct cards (counted, not run).

A pack can carry any `Pick`: `n: int(field("n"), "Pick n")? as u8`, with any kind and either `exact`. Search passes every leaf to the evaluator in one `evaluate` call, so memory grows with the number of leaves too. Official content is safe: Headbutt, Survivor and Hologram each pick one card, and they are proving cards (`CardDef.proving`: kept out of every deck pool).

**Reproduce.** The verifier measured this in a debug build. Search is deterministic, so release gives the same counts.
- Pack: `{"version": 1, "cards": [{"id": "d1_top5", "cost": 0, "type": "Skill", "effects": [{"Pick": {"kind": "DiscardToTop", "n": 5}}]}]}`.
- Deck: `["gen:d1_top5", "Strike", "Defend", "Bash", "Anger", "Clash", "Cleave", "Flex", "Inflame", "Pommel Strike", "Twin Strike"]`. Get the ids with `let ids = bind(&deck).unwrap().0;`. Binding the same deck again gives the same ids.
- Build the state with `engine/tests/packs.rs`'s `bound_combat(&deck, &[0])`: Ironclad against a Jaw Worm at 100 HP, 3 energy, only the pick card in hand, and empty draw and discard piles. Then set `s.discard = Pile::from_cards(&ids[1..])`, which puts 10 distinct cards in the discard pile.
- Run `search(&s, &mut eval, &SearchConfig { max_nodes: 1_000, ..SearchConfig::default() })`.
- Expected: about 1,000 nodes plus a small overshoot.
- Actual: 36,559 nodes and 30,241 leaves (10·9·8·7·6 orders, plus the EndTurn leaf). The node count follows from the shape alone: 5,861 pick nodes, plus 457 after-pick states expanded before the cap (2 nodes each), plus 29,783 cut leaves, plus 1.
- With n = 6 and the default cap, one search makes 209,637 nodes against a cap of 50,000.

The verifier projects about 5.6 GB at n = 8. An "any number" pick (`"exact": false` with a large n, the natural way to write a Scry-like card) over 10 distinct cards needs more than this machine's 16 GB. The search values stay correct; the time and memory don't. Don't put n ≥ 7 in a test, because the test also runs before the fix.

**Fix.** Keep the exemption, so a pick is still never a leaf, but give a pick only one child once the cap is reached.
- In `Tree::expand`'s decision branch (`search.rs:259-270`), compute `let past_cap = self.nodes.len() >= self.cfg.max_nodes;` before the loop.
- When `past_cap` is true, expand only the first action of `s.legal_actions()`:
  ```rust
  for a in s.legal_actions().into_iter().take(if past_cap { 1 } else { usize::MAX }) {
  ```

Why this is safe:
- In that branch, a state past the cap is always a pick. Any other state past the cap was already cut to a leaf at line 235, and a state at a pick never has a pending chance event.
- A pick always has at least one `Choose`. A pick only starts or continues while its source pile is non-empty (`state.rs:630` and `:694`). `legal_actions` lists one `Choose` per distinct candidate in card id order, with `Done` last (`state.rs:538-546`).
- The first action is also the greedy agent's choice at a pick (`agent.rs:199-201`).
- Past the cap, each pick costs one chain: at most n decision nodes, then one cut leaf. The states that were already being expanded when the cap was reached still finish their loops, but each of their remaining children costs only one such chain. So the overshoot grows with depth × options × n, not factorially. For the reproduction it is about 1,100 nodes in all (counted by hand). Below the cap nothing changes.
- The root's options come from `search()`'s own loop (`search.rs:293-302`), not from `expand`, so an agent standing at a pick still gets a value for every choice.

Leave `cuts` (the count of states cut to leaves by the cap) as it is: options skipped at a pick are not leaves. Rewrite the comment at `search.rs:236-237` to say what happens now. Extend the `max_nodes` doc comment at `search.rs:36` ("Past this many nodes, unexpanded states become leaves") with: "a state at a pick is still expanded, along its first option only".

Then fix the docs:
- In `rules-engine-upgrade.md:24` (the "Multi-pick cost" row) and `:213-220`, and in `extending.md:94-97`, say two things:
  - Past the node cap, a pick is still expanded (never a leaf), but only along its first option.
  - The transposition cache does not bound picks: DiscardToTop keeps order, and ReturnFromDiscard ranges over the discard pile.
  
  `extending.md:37-39` ("always expanded, never leaves") stays true.
- In `docs/decisions.md`, add a line that supersedes lines 1937-1938 to this fix spec's entry; don't rewrite the old entry. The fix spec's entry is a new `## ...` section at the end of the file (after line 2352). Create it if an earlier step hasn't.
- Leave alone `engine/examples/two_turn_phases.rs`'s own copy of the tree (line 87). That copy is used only for timing; its `--check` output comes from the real `search`.

Alternatives:
- Refuse long picks at load. Rejected: 10 distinct cards already give 30,240 orders at n = 5, and capping n removes atoms the engine supports.
- A separate pick budget. Rejected: one more setting for the same effect.

Don't make a pick past the cap a leaf: that breaks the spec's rule and `decisions.rs::search_never_scores_a_pick`. Don't make the known top order-free either: the order is real game state.

**Test first.** `engine/tests/packs.rs::a_long_pick_stays_within_the_node_cap`.
- Add `use sts_engine::search::{search, Evaluator, SearchConfig};`.
- Copy `NoPickLeaves` from `engine/tests/decisions.rs:125-133`. It is an evaluator that asserts `s.pick().is_none()` for every state it receives and returns zeros.
- Use the setup under Reproduce, then:
  ```rust
  let cfg = SearchConfig { max_nodes: 1_000, ..SearchConfig::default() };
  let r = search(&s, &mut NoPickLeaves, &cfg);
  assert!(r.nodes <= 2 * cfg.max_nodes, "{} nodes", r.nodes);
  assert!(s.is_legal(r.action));
  ```
- Today the first assert fails with 36,559 nodes.
- Optional second case: card `d1_any`, `{"Pick": {"kind": "DiscardToTop", "n": 99, "exact": false}}`, with the first 7 of the cards above in the discard pile. Today it makes 22,742 nodes at cap 1,000.

**Must stay unchanged.**
- H4 (`two_turn_phases 100 --check`) stays byte-identical. Its states come from heuristic play of `runner::group_specs` decks (the starter plus `deck_cards()`). Those exclude proving cards, so no search there meets a pick.
- golden.txt (9,000 games) and golden_proving.txt are played by the random agent, not by search.
- codec_golden.txt and the codec round trip search only starter plus `class_cards` decks, which have no proving cards.
- `decisions.rs::search_never_scores_a_pick` and `search_completes_picks_past_the_node_cap` still pass. They check legality and that no pick is scored, not node counts.
- `py/tests/test_sts.py::test_decision_actions` (`sts.run("search", ...)` with Survivor) still passes. It checks only that games run.
- No pin changes. `search.rs` is not one of the fingerprinted rule files.

### D2. An X-cost pack card with a nonzero cost spends more energy than the player has

- **Severity:** medium · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED; the verifier ran a throwaway test (review id v18, reported #15)
- **Where:** `engine/src/registry.rs:754` and `:759` in `parse_card`: the cost and `x_cost` are read separately and never compared. Related:
  - `engine/src/state.rs:601-602` in `apply_action`.
  - `state.rs:663` in `can_play`.
  - `engine/src/cards.rs:214-215`: the convention.
  - `registry.rs:425` and `:434` in `bind`, which copy both fields into the `CardDef` unchanged.

**What goes wrong.** An X-cost card (`CardDef.x_cost`, like Whirlwind) spends all current energy, and the amount spent is X (`Quantity::EnergySpent`). The engine's convention (cards.rs:214-215, decisions.md:1758-1763) is that such a card's `cost` stays 0. Playing a card runs:

`let x = if d.x_cost { std::mem::take(&mut self.player.energy).max(0) as u8 } else { 0 };`, then `self.player.energy -= d.cost;`

The loader accepts any `cost` together with `"x_cost": true`.
- A pack X card costing 1 takes all energy as X and then 1 more, so energy goes to -1. `can_play` only checks `d.cost <= self.player.energy`, so every 0-cost card is illegal for the rest of the turn.
- The same card is illegal at 0 energy, where Whirlwind is legal.
- With `"cost": -1` (the game's own X marker, which a pack author copying game data might use), the player keeps 1 energy after spending all of it.
- A negative cost on a normal card adds energy on every play. No official card has a negative cost: statuses cost 0 and set `unplayable`.

Nothing panics. The codec refuses states with a registry binding, so no encoding is affected.

**Reproduce.**
- Pack: `{"version": 1, "cards": [{"id": "d2_x1", "cost": 1, "type": "Attack", "x_cost": true, "effects": [{"ScaledDamage": {"amount": {"base": 0, "k": 5, "of": "EnergySpent"}, "target": "Opponent"}}]}]}`. `load_pack` returns Ok.
- Bind `["gen:d2_x1", "Shiv"]` and build `bound_combat(&deck, &[0, 1])` (3 energy, Jaw Worm at 100 HP). Play the X card at monster 0.
- Expected, as with Whirlwind at cost 0: energy 0, 15 damage, and the Shiv still playable.
- Actual: energy -1, X = 3 (the Worm is left at 85 HP), and `legal_actions()` is `[EndTurn]`.
- Variant with `"cost": -1`: energy is 1 after the play.

**Fix.** In `parse_card`, refuse two things:
- a negative cost, with an error such as "a card's cost can't be negative";
- `x_cost: true` with any cost other than 0, with an error that names the rule, such as "an X-cost card's cost is 0: playing it spends all energy as X".

Put both checks where the `CardSpec` is built (`registry.rs:753-766`), using the parsed cost and the parsed `x_cost` flag.

Every official card costs 0 or more, and Whirlwind and Whirlwind+ cost 0 with `x_cost`, so their `card_json` round trips still load.

Don't change `apply_action` or `can_play` to special-case X cards: the convention exists so that no cost reader needs a case (decisions.md:1758-1763). Don't clamp energy at 0 either: that hides the bad card.

Out of scope: a negative `GainEnergy` effect can also take energy below 0. No official card has one, and it may be what a pack means, so leave it.

**Test first.** `engine/tests/packs.rs::packs_refuse_costs_play_cant_pay`. Write it as a list of complete packs, like `packs_refuse_what_play_cant_run` (`packs.rs:231-240`), giving each pack its own card id:
- the pack under Reproduce (`d2_x1`);
- the same card with `"cost": -1` (id `d2_xneg`);
- `{"version": 1, "cards": [{"id": "d2_neg", "cost": -1, "type": "Skill", "effects": [{"Block": 5}]}]}`.

Assert `load_pack(pack).is_err()` for each. All three load today. Control, which must load before and after: the X card with `"cost": 0` (id `d2_x0`).

**Must stay unchanged.**
- `packs.rs::every_official_card_round_trips` still passes: Whirlwind and Whirlwind+ load.
- No engine rule changes, so golden, codec, H4, series_check and every pin are untouched.
- `registry.rs` is not fingerprinted.
- `scripts/gen_content.py` writes costs 0 to 3 without `x_cost`, so generated packs still load.

### D3. Packs can build ScaledDamage shapes that the features and the heuristic can't read

- **Severity:** medium (features) / low (heuristic) · **Reach:** content packs · **New on this branch:** yes · **Review:** both parts CONFIRMED (review ids sw_py_2 and v15; cut by the review's 15-finding cap). For sw_py_2 the verifier ran a throwaway engine test with the encoder's arithmetic copied in; the Python encoder itself was not run. For v15 the verifier read the code only.
- **Where:**
  - `engine/src/registry.rs:485-499` in `amount` and `:621-628` in `parse_effect`: no shape check.
  - `py/src/features.rs:839-852` in `Encoder::effects`: the form columns. Also `:825` there, which writes the legacy columns only when `hits == Amount::constant(1)`.
  - `engine/src/heuristic.rs:89-103` in `deck_output`: `_ => (0.0, 0.0)` at line 103.
  - Related:
    - `engine/src/effects.rs:82-85`: the rule "At most one of the two reads a quantity".
    - `engine/tests/amounts.rs:91-98`: checks that rule for official cards only.
    - `py/src/features.rs:1421-1423`: X is taken as the current energy for every card in a pile.
    - `engine/src/state.rs:1214-1219`: `resolve` ignores `k` when `of` is `None`.

**What goes wrong.** `Effect::ScaledDamage { amount, hits, target }` deals `amount` per hit, `hits` times. Each of the two is an `Amount`: `base + k × quantity`, where the quantity is one of OwnBlock, OwnStrength, EnergySpent (an X card's X) or CardsTagged(tag). The engine plays any shape. Two consumers only understand the shapes official cards use.

1. The features (the net's inputs, built in py/src/features.rs) write the total damage as one form, `expr_base + expr_k × quantity`, with a one-hot quantity column. The code assumes one side is constant:

   `match (amount.of, hits.of) { (q @ Some(_), _) => (amount.base * hits.base, amount.k * hits.base, q), (None, q) => ... }`

   If both sides read a quantity, the hits' quantity and k are dropped. Example: an X card with amount `{base 2, k 1, OwnStrength}` and hits `{base 0, k 1, EnergySpent}`. It encodes as expr_base 0 and expr_k 0 with the Strength flag, which reads as zero damage. The engine deals (2 + 2S) per hit, X times: 24 at Strength 3 and X = 3. Hook rows and the card's own CardPlayed row have no `expr_value` column (the resolved total) to fall back on.

   `CardsTagged` with a tag other than Strike has no quantity column (`// No content counts another tag yet: no column.`), so `expr_k` multiplies nothing the net can see.

   Found while checking this spec (from the code, not run): an amount object with `k` but no `of`, such as `"hits": {"base": 1, "k": 2}`, loads as `Amount { base: 1, k: 2, of: None }`. The engine reads it as the constant 1, because `resolve` returns `base` when `of` is `None`. The encoder's `(None, q)` arm writes `expr_k = amount.base × hits.k` with no quantity column. It also skips the legacy columns, because `hits != Amount::constant(1)`.

2. The heuristic (the hand-written evaluator, `heuristic::estimate`) prices a card's damage in `deck_output` with four arms. They copy the cards ScaledDamage replaced (Heavy Blade, Perfected Strike, Body Slam) plus Whirlwind. Every other shape scores 0: `_ => (0.0, 0.0)`. A pack card `{"ScaledDamage": {"amount": 10, "hits": 2, ...}}` therefore adds no damage, while the same card written as `Damage` adds about (10 + Strength) × 2.

One more case, found while re-reading for this spec; the review did not run it. A card without `x_cost` that reads EnergySpent always plays with X = 0, because `apply_action` sets `x` to 0 for it. The features value it with X = current energy: `let x = if k == 4 { s.stage_x() } else { s.player.energy.max(0) as i16 };` (features.rs:1422). In a hook or a turn_end effect, X is the X of whatever card happens to be in play, or 0.

The one-quantity rule is documented (effects.rs:84, decisions.md:1752) and tested for official cards, but `load_pack` never checks it.

**Reproduce.** All of these load today (`load_pack` returns Ok):
- `{"version": 1, "cards": [{"id": "d3_both", "cost": 0, "type": "Attack", "x_cost": true, "effects": [{"ScaledDamage": {"amount": {"base": 2, "k": 1, "of": "OwnStrength"}, "hits": {"base": 0, "k": 1, "of": "EnergySpent"}, "target": "Opponent"}}]}]}`. The verifier measured that at Strength 3 and X = 3 it takes the Jaw Worm from 100 to 76 HP, while the encoder's arithmetic gives (0, 0, OwnStrength).
- `{"version": 1, "powers": [{"id": "d3_hook2", "hooks": [{"trigger": "OwnerTurnEnd", "effects": [{"ScaledDamage": {"amount": {"base": 2, "k": 1, "of": "OwnStrength"}, "hits": {"base": 1, "k": 1, "of": "OwnBlock"}, "target": "AllOpponents"}}]}]}]}`. It is encoded as 2 + 1 × Strength, so the (1 + Block) hit count is lost.
- `{"version": 1, "cards": [{"id": "d3_shiv", "cost": 1, "type": "Attack", "effects": [{"ScaledDamage": {"amount": {"base": 0, "k": 3, "of": {"CardsTagged": "Shiv"}}, "target": "Opponent"}}]}]}`. It gets expr_k 3 with no quantity column.
- `{"version": 1, "cards": [{"id": "d3_nox", "cost": 1, "type": "Attack", "effects": [{"ScaledDamage": {"amount": 5, "hits": {"base": 0, "k": 1, "of": "EnergySpent"}, "target": "Opponent"}}]}]}`. It has no `x_cost`, so it deals 0 hits, while the features say 5 × energy.
- `{"version": 1, "powers": [{"id": "d3_hookx", "hooks": [{"trigger": "OwnerTurnEnd", "effects": [{"ScaledDamage": {"amount": 5, "hits": {"base": 0, "k": 1, "of": "EnergySpent"}, "target": "AllOpponents"}}]}]}]}`.
- `{"version": 1, "cards": [{"id": "d3_kno", "cost": 1, "type": "Attack", "effects": [{"ScaledDamage": {"amount": 5, "hits": {"base": 1, "k": 2}, "target": "Opponent"}}]}]}`. Play deals 5; the form says 5 + 10 with no quantity.

Heuristic: load the cards `{"id": "d3_t10", "cost": 1, "type": "Attack", "effects": [{"ScaledDamage": {"amount": 10, "hits": 2, "target": "Opponent"}}]}` and `{"id": "d3_d10", "cost": 1, "type": "Attack", "effects": [{"Damage": {"amount": 10, "hits": 2, "target": "Opponent"}}]}`. `heuristic::estimate(&bound_combat(&["gen:d3_t10"], &[0]))` differs from the same call with `gen:d3_d10`. The two should be equal.

**Fix.** Two parts, built as separate steps.

(a) Load rules in `registry.rs`. This is the cause: the loader lets packs build shapes that the documented rule forbids, or that no consumer reads.
1. In `parse_effect`'s `"ScaledDamage"` arm, parse amount and hits into locals, so they don't shadow the `amount` function. Refuse a shape where both read a quantity:
   ```rust
   "ScaledDamage" => {
       let a = amount(field("amount"), "ScaledDamage amount")?;
       let h = field("hits").map_or(Ok(Amount::constant(1)), |h| amount(Some(h), "ScaledDamage hits"))?;
       if a.of.is_some() && h.of.is_some() {
           return Err("ScaledDamage: at most one of amount and hits reads a quantity".into());
       }
       (Effect::ScaledDamage { amount: a, hits: h, target: target(field("target"))? }, None)
   }
   ```
2. In `amount`, refuse `CardsTagged` with any tag other than `Tag::Strike`, because the features have no column for another tag. Add a column when content needs one.
3. In `amount`, refuse a nonzero `k` when there is no `of`, with an error such as "k needs of; write a constant as a number". `amount_json` writes constants as plain numbers, so round trips are unaffected.
4. Refuse EnergySpent outside an X-cost card's own play:
   - in `parse_card`, refuse when `x_cost` is false and any row (the on-play row or a conditional row) reads EnergySpent;
   - in `parse_card`, refuse EnergySpent in `turn_end`;
   - in `parse_hook`, refuse it in hook effects.
   
   One helper serves all three checks:
   ```rust
   fn reads_x(e: &Effect) -> bool {
       matches!(e, Effect::ScaledDamage { amount, hits, .. }
           if amount.of == Some(Quantity::EnergySpent) || hits.of == Some(Quantity::EnergySpent))
   }
   ```

After (a), the form `(base, k, q)` describes amount × hits exactly as the engine resolves them, for every shape a pack can load. Two things fall outside the form: the engine clamps the hit count to 0..=255, and the attack pipeline floors each hit at 0. So features.rs needs no code change. Update its two comments (lines 839 and 851) to say the loader guarantees the shape.

Every official shape passes:
- Body Slam (OwnBlock), Heavy Blade (OwnStrength) and Perfected Strike (the Strike tag) each read one quantity in the amount, with constant hits.
- Whirlwind (an X card) reads EnergySpent in the hits.

Add the four rules to README.md's pack section.

(b) Heuristic fallback (recommended, low severity). Replace `_ => (0.0, 0.0)` at heuristic.rs:103 with a general estimate. Keep the four existing arms exactly as they are, so official estimates stay bit-identical: no official card reaches the fallback.
```rust
_ => {
    let est = |a: Amount| match a.of {
        None => a.base as f32,
        Some(q) => a.base as f32 + a.k as f32 * match q {
            Quantity::OwnStrength => strength,
            Quantity::OwnBlock => 6.0, // the Body Slam arm's "roughly one block card's block"
            Quantity::EnergySpent => ENERGY_PER_TURN as f32,
            Quantity::CardsTagged(Tag::Strike) => strikes,
            Quantity::CardsTagged(_) => 0.0, // refused at load by (a)
        },
    };
    let targets = if target == Target::AllOpponents { living.max(1) as f32 } else { 1.0 };
    ((est(amount) + strength).max(0.0) * est(hits).max(0.0) * targets, 0.0)
}
```
Add `Amount` to the `crate::effects` import. `Tag`, `ENERGY_PER_TURN`, `strength`, `strikes` and `living` are already in scope.

For a constant × constant shape, `est` returns `base` itself, and the multiplications run in the Damage arm's order. So such a card is priced bit-identically to the same card written as `Damage`.

This doesn't conflict with the owner's rule that the heuristic stays blind to new row kinds through the series (rules-engine-upgrade.md:685-691). ScaledDamage isn't a row kind, and official estimates don't move. If the manager prefers to keep the heuristic blind, skip (b) and note the limit in README.md's pack section.

Alternative: add feature columns, one for a hits quantity and one per other tag. That changes the default vocabulary and re-pins TRAIN_PIN, ARRAYS_PIN, golden_rows, the contract pins, the lookahead names and the curriculum digests, which isn't worth it before content needs it. Don't patch the encoder to guess at two-sided shapes; refuse them.

**Test first.**
- `engine/tests/packs.rs::packs_refuse_scaled_damage_the_features_cant_read`: the six packs under Reproduce, each with its own id. Assert `load_pack(..).is_err()` for each. All six load today.
- For part (b), `engine/tests/packs.rs::heuristic_prices_a_constant_scaled_attack_like_damage`:
  - load the two heuristic cards in one pack;
  - `let est = |n: &str| sts_engine::heuristic::estimate(&bound_combat(&[n], &[0]));`
  - `assert_eq!(est("gen:d3_t10"), est("gen:d3_d10"))`.
  
  This fails today because the ScaledDamage card adds 0 damage.

**Must stay unchanged.**
- These still pass: `every_official_card_round_trips`, `every_official_power_round_trips` (no official hook uses ScaledDamage), `generated_attack_and_pick_play` (pk_slam, OwnBlock), and the `amounts.rs` tests.
- series_check PASS: the heuristic and the contract nets bit-identical, every feature column equal.
- Golden, codec and H4 are untouched: no rule changes, and the heuristic's existing arms are unchanged.
- `scripts/gen_content.py` writes no ScaledDamage, so generated packs and their prices are unchanged.
- No pin changes.

### D4. The pack parser accepts misspelled keys and wrong JSON types, and wraps out-of-range numbers

- **Severity:** low · **Reach:** content packs · **New on this branch:** partly · **Review:** CONFIRMED; the verifier ran throwaway tests (review id v16; cut by the 15-finding cap)
- **On main already:** string flags read as false; Damage hits and amount wrapped; a non-array effects or hooks value read as empty; a misspelled hook condition read as Always; the u8 effect cursor.
- **New on this branch:** the same pattern in every key the branch added: Amount `k` and `of`, `rows` and row conditions, `tags`, the new flags, Pick `n`, random hits, and static and replacement numbers. The branch also made rows reachable from packs.
- **Where:** `engine/src/registry.rs`, the pack parser:
  - `amount`: `:498`, `k: v.get("k").and_then(json::Value::int).unwrap_or(0) as i16`; the plain-number amount at `:488`.
  - `parse_static`: `:546-550`.
  - `parse_replacement`: `:562-565` and `:574`.
  - `parse_effect`: `:606-607`, `:613-619`, `:630`, `:635`, `:648`, `:657`, `:660` and `:663`.
  - `parse_power`: `:521-525`.
  - `parse_hook`: `:701`.
  - `card_effects`: `:723`.
  - `parse_card`: `:735` (flags), `:738` (rows), `:750` (tags), `:754` (cost).
  - `condition`: `:515`.
  - `load_pack`: `:301` and `:315`.
  - The JSON reader: `json::Value::items` (`:950-955`) reads a non-array as `&[]`, and `get` (`:944-949`) matches keys exactly, so unknown keys are ignored.

  Where it bites: in `run`, a card's effects are walked with a u8 cursor (`Stage::PlayingCard { next: u8, .. }`). The cursor is set at `engine/src/state.rs:682` (`next: at.row_end as u8`) and advanced with `next + 1` at `:687`, `:695` and `:698`.

**What goes wrong.** The parser reads optional keys with `get(..).and_then(..).unwrap_or(default)`, so a misspelled key, or a value of the wrong JSON type, silently becomes the default. Lists are read with `items()`, so a non-list becomes an empty list. Numbers are cut to their field's type with `as`, which wraps. `load_pack` returns Ok, and the card or power differs from what the pack says. A card with more than 255 effects in its play rows overflows the u8 cursor. registry-lite.md:127-128 asks to "prefer an error over a silent fallback for generated content".

**Reproduce.** The verifier ran these; each loads with Ok today. The 256-effect release behaviour is read from the code, not run.

| Pack fragment | Loads as / does |
|---|---|
| ScaledDamage amount `{"base": 14, "K": 2, "of": "OwnStrength"}` | k becomes 0: deals 17 at Strength 3, where Heavy Blade deals 23 |
| `"rows": {...}` (an object) | 0 rows |
| `"tags": "Strike"` | no tags, so not a Strike |
| `"exhaust": "true"` | exhaust false |
| Damage `"hits": 256` | 0 hits, no damage |
| Pick `"n": 256` | n 0, so the pick is skipped |
| static `"den": 65537` | den 1 (the `den > 0` check runs after the cast) |
| Damage `"amount": 40000` | amount -25536 |
| row key `"conditon"` | condition Always, so the row always runs |
| 256 effects in `effects` | debug panics with "attempt to add with overflow" at state.rs:698. Release wraps `next` to 0 and plays the card from effect 0 again, over and over: a hang unless an effect ends the combat |
| 200 on-play effects plus a never-true row of 100 | `row_end` 300 is cut to 44, so effects 44-199 run again and again: a 1000-HP Jaw Worm died from a card that should deal 200; with zero-damage effects the play never ends (a hang in debug and release) |

**Fix.** Three steps, all in `registry.rs`. Keep the engine's small JSON reader: the engine has no dependencies by design.

1. Numbers.
   - Add `fn num<T: TryFrom<i64>>(v: Option<&json::Value>, what: &str) -> Result<T, String>`. It reads a required integer with `int`, converts it with `T::try_from`, and returns an error naming the field when the value doesn't fit.
   - Add `fn opt_num<T: TryFrom<i64>>(v: Option<&json::Value>, default: i64, what: &str) -> Result<T, String>`:
     - a missing key gives `default`;
     - a present value that isn't an integer is an error;
     - an out-of-range value is an error.
   - Use them at every `int(..)? as ..` and every `.and_then(json::Value::int).unwrap_or(..) as ..`. These are the 22 sites:
     - i16 fields: the Damage, PlainDamage, RandomDamage, RandomApply and Apply amounts; Block; LoseHp; ReduceSelf; GrowDamage; Amount `base` and `k` and the plain-number amount; static `amount`, `num` and `den`; Cap; Add; Multiply `num` and `den`.
     - u8 fields: Damage `hits` (default 1); RandomDamage and RandomApply `hits`; Draw; AddCard `n` (default 1); Pick `n`; CardsPlayedThisTurnBelow.
     - i8 fields: `cost` and GainEnergy.

     The `Effect`, `Static`, `Replace` and `Condition` field types let Rust infer `T` where the value goes straight into a constructor.
   - In `parse_static`, check `den > 0` on the converted value. That comparison doesn't fix the type, so annotate it: `let den: i16 = opt_num(v.get("den"), 1, "static den")?;`.
   - In `parse_card`, refuse a card whose play rows (the on-play row plus the conditional rows) hold more than 255 effects in total. With at most 255, `row_end` and every `next + 1` fit the u8 cursor. Hooks and `turn_end` run in plain `for` loops (state.rs:840 and 972), so they have no cursor and need no cap.
2. Lists and flags.
   - Add `fn list<'a>(v: Option<&'a json::Value>, what: &str) -> Result<&'a [json::Value], String>`: a missing key gives an empty list, an array gives its items, and anything else (`null` included) is an error.
   - Add `fn opt_bool(v: Option<&json::Value>, default: bool, what: &str) -> Result<bool, String>`.
   - Use `list` for `powers`, `cards`, `hooks`, `statics`, `replacements`, `then`, `effects`, `rows`, `tags` and `turn_end`.
   - Use `opt_bool` for the seven card flags, a power's `debuff` and Pick's `exact`.
   - Remove `json::Value::items` once nothing uses it. The `json` module is private, so leaving it in would only give a dead-code warning.
3. Unknown keys.
   - Add `fn only(v: &json::Value, keys: &[&str], what: &str) -> Result<(), String>`. It refuses a value that isn't an object, and any object key not in `keys`. Refusing non-objects matters for card rows: both of a row's keys are optional, so `"rows": [5]` would otherwise still load as an empty `Always` row.
   - Call it on these 16 kinds of structural object:
     - amount objects (`base`, `k`, `of`), after the plain-number check in `amount`;
     - card rows (`condition`, `effects`);
     - hooks (`trigger`, `condition`, `effects`);
     - trigger fields when present: CardPlayed (`by`) and OwnerLostHp (`from`);
     - statics (`modifies`, `stage`, `amount`, `num`, `den`, `condition`);
     - replacements (`event`, `action`, `then`);
     - Multiply (`num`, `den`);
     - the field objects of Damage (`amount`, `hits`, `target`), PlainDamage (`amount`, `target`), ScaledDamage (`amount`, `hits`, `target`), RandomDamage (`amount`, `hits`), RandomApply (`power`, `amount`, `hits`), AddCard (`card`, `n`, `pile`), Pick (`kind`, `n`, `exact`) and Apply (`power`, `amount`, `target`).
     
     The eight effect field objects can share one call at the top of `parse_effect`, through a `match name` that gives each effect's allowed keys.
   - Don't check card, power or pack objects. `scripts/gen_content.py` writes metadata there: pack `seed` and `budget`; power `split`, `keys` and `lifetime`; card `power`, `split`, `gain` and `value_per_energy`. `data/bench/gen_powers_pack.json` holds those keys, and recorded datasets carry its text hash, so the generator's format can't change. The review's suggestion to "refuse unknown keys", applied everywhere, would refuse every generated pack.
   - Say in README.md's pack section (lines 212-220) what is checked:
     - Card, power and pack objects may carry keys the engine doesn't read (the generator keeps its bookkeeping there), and the engine ignores them. So a misspelled key at that level (a card flag, `rows`, `hooks`, `statics`) is silently missing.
     - Every object inside them (rows, hooks, triggers, statics, replacements, effects and amounts) refuses unknown keys.
     - Every number, list and flag must have the right JSON type and fit its field.

Alternative for step 3: also check card, power and pack objects, against the engine's keys plus the generator's metadata names. That catches a misspelled card flag, but it ties the engine to the generator's bookkeeping. Optional: make `only` refuse duplicate keys too (today `get` takes the first one).

**Test first.** Three tests in `engine/tests/packs.rs`, one per step. Each is a list of complete packs that must all be refused, in the style of `packs_refuse_what_play_cant_run` (`packs.rs:231-240`). An example of a complete pack: `{"version": 1, "cards": [{"id": "d4n_hits", "cost": 0, "type": "Attack", "effects": [{"Damage": {"amount": 5, "hits": 256, "target": "Opponent"}}]}]}`.

Give every pack its own ids. The registry is process-wide and append-only, so a reused id would be refused as "redefined", which is the wrong reason. Every pack below loads today.
- `packs_refuse_bad_numbers` (step 1):
  - Damage `"hits": 256` (`d4n_hits`)
  - Pick `"n": 256` (`d4n_pick`)
  - static `"den": 65537` (`d4n_den`)
  - Damage `"amount": 40000` (`d4n_amt`)
  - `{"Draw": -1}` (`d4n_draw`; loads as Draw 255 today)
  - Damage `"hits": "2"` (`d4n_hstr`)
  - amount `{"base": 14, "k": "2", "of": "OwnStrength"}` (`d4n_kstr`)
  - a card with 256 `{"Block": 1}` effects (`d4n_many`; build it with `vec![r#"{"Block": 1}"#; 256].join(", ")`)
  - a card with 200 on-play `{"Block": 1}` effects plus `"rows": [{"condition": {"CardsPlayedThisTurnBelow": 0}, "effects": [...100 × {"Block": 1}...]}]` (`d4n_rows`)
- `packs_refuse_bad_lists_and_flags` (step 2):
  - `"rows": {"condition": "Always", "effects": [{"Block": 1}]}` (`d4t_rows`)
  - `"tags": "Strike"` (`d4t_tags`)
  - `"exhaust": "true"` (`d4t_exh`)
  - `"effects": {"Block": 1}` (`d4t_eff`)
  - Pick `{"kind": "DiscardFromHand", "n": 1, "exact": "false"}` (`d4t_exact`)
  - a power with `"hooks": {"trigger": "OwnerTurnEnd", "effects": [{"Block": 1}]}` (`d4t_hooks`)
- `packs_refuse_unknown_keys` (step 3):
  - amount `{"base": 14, "K": 2, "of": "OwnStrength"}` (`d4k_k`)
  - a row `{"conditon": {"CardsPlayedThisTurnBelow": 1}, "effects": [{"Block": 5}]}` (`d4k_row`)
  - a row given as `5` (`d4k_rownum`)
  - a hook `{"trigger": {"CardPlayed": {"by": "Owner"}}, "conditon": {"CardType": "Attack"}, "effects": [{"Block": 1}]}` (`d4k_hook`)
  - a static `{"modifies": "DamageDealt", "stage": "Multiply", "num": 1, "dne": 2}` (`d4k_den`)
  - Damage `{"amount": 5, "hit": 3, "target": "Opponent"}` (`d4k_hit`)
  - plus a control that must load both before and after: `{"version": 1, "seed": 7, "powers": [{"id": "d4k_meta_p", "split": "train", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{"Block": 1}]}]}], "cards": [{"id": "d4k_meta_c", "cost": 1, "type": "Power", "split": "train", "gain": 0.1, "value_per_energy": null, "effects": [{"Apply": {"power": "d4k_meta_p", "amount": 1, "target": "Me"}}]}]}`

**Must stay unchanged.**
- Every pack that loads today with exact keys, the right types and in-range values still loads, and `load_pack` returns the same content hash (FNV-1a of the text). That covers:
  - `packs.rs`'s round trips, PACK and FIX_PACK;
  - `engine/tests/registry.rs`'s PACK and its `gp_n{i}` / `gc_n{i}` pack;
  - `py/tests/test_content_pack.py`;
  - generated packs with metadata keys: `scripts/tests/test_gen_content.py`, `scripts/tests/test_content_selfplay.py` and `data/bench/gen_powers_pack.json`.
- `card_json` and `power_json` write exactly the keys the parser reads, with in-range official values.
- No rule changes: golden, codec, H4, series_check and every pin are untouched. `registry.rs` is not fingerprinted.

### D5. Static and replacement arithmetic overflows i16 on large pack values

- **Severity:** low · **Reach:** content packs · **New on this branch:** yes. Statics and replacements are new. The fast path's final `as i16`, which the fix also clamps, was on main. · **Review:** CONFIRMED; the verifier ran a throwaway test (review id v17; cut by the 15-finding cap)
- **Where:**
  - `engine/src/state.rs:1384` and `:1393` in `interpret_attack_damage`; `:1412` and `:1422` in `interpret_block`; `:1471-1472` in `replaced`.
  - `py/src/features.rs:1068` in `Encoder::static_row`.
  - The loader takes any value: `registry.rs:546-550` in `parse_static` and `:562-565` in `parse_replacement`.
  - Related sites of the same kind, found while re-reading (not run):
    - `state.rs:1217` in `resolve` (new on the branch);
    - `state.rs:1322` and `:1332` in `attack_damage` (on main);
    - `py/src/features.rs:840-842` in `Encoder::effects` (new);
    - `py/src/features.rs:1563` in `expr_value` (new).

**What goes wrong.** A static is a power's modifier row on damage dealt, damage taken or block gained (`hooks::Static`, stage Add or Multiply). A replacement is a row that cancels or changes an event's amount (`hooks::Replacement`). Statics are read at play time by the row interpreter (`interpret_attack_damage`, `interpret_block`), which runs whenever a side holds a generic or generated static power. Replacements are read by `replaced`.

The interpreter keeps the damage as a fraction num/den in i32, but it multiplies the Add term in i16 first: `StaticStage::Add => num += (st.amount * stacks) as i32 * den,`. It ends with `(num.max(0) / den) as i16`, which wraps above 32,767. `replaced` adds in i16 (`Replace::Add(k) => n += k,`) and cuts its i32 product with `as i16`.

Release builds have no overflow checks; that covers the wheels and `cargo test --release`. There the value wraps, often to a negative number that `take_damage` floors at 0, so a bigger multiplier deals no damage. Debug builds panic on the i16 multiply and add. An `as` cast never panics, so a wrapping cast gives the same wrong value in both profiles. The features' opt-in static rows also compute `(st.amount * stacks) as f32` in i16.

Official content never gets close: its statics are Add 1 and Multiply 3/4 or 3/2, and its replacements are Cancel and Cap 1. Only pack values trigger it.

**Reproduce.** The verifier ran these in a debug build. Each pack power was granted by a 0-cost Skill, then Strike (6 damage) hit a 100-HP Jaw Worm built with `bound_combat`.
- Static `{"modifies": "DamageDealt", "stage": "Multiply", "num": 10000, "den": 1}` on the player: `attack_damage` returns -5536 and the Worm stays at 100 HP. With 5000 it returns 30000 and kills.
- Static `{"modifies": "DamageDealt", "stage": "Add", "amount": 1000}` at 40 stacks: debug panics with "attempt to multiply with overflow" at state.rs:1384; release deals 0.
- Replacement `{"event": "DamageTaken", "action": {"Multiply": {"num": 10000, "den": 1}}}` on the monster: Strike deals 0.
- Replacement `{"event": "DamageTaken", "action": {"Add": 32767}}` on the monster: debug panics with "attempt to add with overflow" at state.rs:1471; release deals 0.

Expected in each case: the damage saturates at 32,767 and kills the Worm.

**Fix.** Compute in a wider type and clamp once at the end, keeping the single floor division (the review found that rounding correct).
- `interpret_attack_damage` and `interpret_block`:
  - Start with `let (mut num, mut den) = (base as i64, 1i64);`.
  - Add: `num = num.saturating_add((st.amount as i64 * stacks as i64).saturating_mul(den));`.
  - Multiply: `num = num.saturating_mul(st.num as i64); den = den.saturating_mul(st.den as i64);`. In `interpret_block`, keep Frail's floor: `num = num.max(0).saturating_mul(st.num as i64)`.
  - End with `(num.max(0) / den).min(i16::MAX as i64) as i16`.
  - `den` stays positive, because the loader refuses den ≤ 0.
- `replaced`:
  - `Replace::Add(k) => n = n.saturating_add(k)`.
  - `Replace::Multiply(num, den) => n = (n as i32 * num as i32 / den as i32).clamp(i16::MIN as i32, i16::MAX as i32) as i16`. A product of two i16 values fits in i32.
  - Clamp to the i16 range, not to 0. The callers already floor at 0 or cancel at 0 (`take_damage`, `lose_hp`, `apply_power`), and a chain of rows can pass through a negative amount today. (The review suggested 0..=i16::MAX; that would change such chains.)
- `attack_damage` (the fast path for official-only combats): `let mut num = base as i32 + ps.get(Power::Strength) as i32;` and `(num.max(0) / den).min(i16::MAX as i32) as i16`. Then the fast path and the interpreter agree at the extremes too.
- `resolve`: `(a.base as i32 + a.k as i32 * self.quantity(actor, q) as i32).clamp(i16::MIN as i32, i16::MAX as i32) as i16`. A pack ScaledDamage with k = 1000 at 50 block overflows there today.
- features.rs:
  - `StaticStage::Add => ("static_add", st.amount as f32 * stacks as f32)`.
  - In `Encoder::effects`, compute the expr form in f32: `(amount.base as f32 * hits.base as f32, amount.k as f32 * hits.base as f32, q)`, and the other arm the same way. Then `add("expr_base", base)` and `add("expr_k", k)` without a cast. f32 holds these small integers exactly, so official values stay bit-identical.
  - In `expr_value` (line 1563), make the EnergySpent arm clamp like `resolve`: `(a.base as i32 + a.k as i32 * x as i32).clamp(i16::MIN as i32, i16::MAX as i32) as i16`. Then the feature agrees with what play deals.

Optional: sites of the same kind. None is reachable from official content. Make each saturating in one line if the line budget allows.
- On main already:
  - `gain_block`'s fast path: `n += p.get(Power::Dexterity)` (state.rs:1603), `n = n.max(0) * 3 / 4` (1605) and `*self.block_mut(w) += n.max(0)` (1609).
  - `apply_power`'s `amount.abs()` (1620; it overflows at -32768).
  - `Effect::scaled` (effects.rs:127-138): a hook's amount × stacks. Its `k as u8` and `k as i8` also cut stacks above 255 or 127.
  - `Powers::add` (powers.rs:179).
  - The hook arithmetic in `run_hooks_with`: `n * stacks` at state.rs:976, 979 and 982.
  - `do_effect`'s `GainEnergy`: `self.player.energy += n` (state.rs:1038, i8).
- Found while checking this spec:
  - `take_damage` and `lose_hp`: `(*hp - lost).max(floor)` (state.rs:1489, 1502) overflows in no-death mode. There the player's HP can already be as low as -16,384, so the next hit above 16,383 overflows. This becomes reachable once the fix stops huge damage from wrapping to 0. Use `hp.saturating_sub(lost).max(floor)`.
  - `amount * hits as i16` for RandomApply rows (py/src/features.rs:1082 and 1101) and in the heuristic's Poison arm (engine/src/heuristic.rs:111).
  - `attack_damage(..) * hits as i16` (engine/src/agent.rs:57).
  - `replaced`'s Multiply truncates toward zero, while hooks.rs:78 documents "rounded down". The two differ only for a negative running amount. `(n as i32 * num as i32).div_euclid(den as i32)` would match the doc.

Alternative: only range-limit the values at load. Not enough: stacks and several statics still multiply. Don't keep `as i16` on a wider product; that cast is the bug.

**Test first.** `engine/tests/packs.rs::huge_static_and_replacement_values_saturate`, with one pack:
```
{"version": 1,
 "powers": [
  {"id": "d5_mul", "statics": [{"modifies": "DamageDealt", "stage": "Multiply", "num": 10000, "den": 1}]},
  {"id": "d5_add", "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 1000}]},
  {"id": "d5_badd", "statics": [{"modifies": "BlockGained", "stage": "Add", "amount": 1000}]},
  {"id": "d5_rmul", "replacements": [{"event": "DamageTaken", "action": {"Multiply": {"num": 10000, "den": 1}}}]},
  {"id": "d5_radd", "replacements": [{"event": "DamageTaken", "action": {"Add": 32767}}]}],
 "cards": [
  {"id": "d5_mul_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "d5_mul", "amount": 1, "target": "Me"}}]},
  {"id": "d5_add_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "d5_add", "amount": 40, "target": "Me"}}]},
  {"id": "d5_badd_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "d5_badd", "amount": 40, "target": "Me"}}]},
  {"id": "d5_rmul_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "d5_rmul", "amount": 1, "target": "Opponent"}}]},
  {"id": "d5_radd_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "d5_radd", "amount": 1, "target": "Opponent"}}]},
  {"id": "d5_slam", "cost": 0, "type": "Attack", "effects": [{"ScaledDamage": {"amount": {"base": 0, "k": 1000, "of": "OwnBlock"}, "target": "Opponent"}}]}]}
```
- For each of `gen:d5_mul_card`, `gen:d5_add_card`, `gen:d5_rmul_card` and `gen:d5_radd_card`:
  - bind `[card, "Strike"]` and build `bound_combat(&deck, &[0, 1])`;
  - play the card, with target `Some(0)` when `s.binding.def(id).targeted()` (the two replacement cards target the monster);
  - play Strike at monster 0;
  - assert `s.monsters[0].hp == 0`.
- For `gen:d5_badd_card`: use deck `[card, "Defend"]`, play both, and assert `s.player.block == i16::MAX`.
- For `gen:d5_slam`: build `bound_combat(&["gen:d5_slam"], &[0])`, set `s.player.block = 50`, play it at monster 0, and assert the Worm is at 0 HP.

What happens today:
- In release, every case leaves the Worm at 100 HP (or gives 0 block).
- In debug, the Add, block-Add, replacement-Add and d5_slam cases panic on overflow (state.rs:1384, 1412, 1471 and 1217).
- The two Multiply cases don't panic in either profile, because an `as` cast never panics. They leave the Worm at 100 HP.

Run the test in both profiles.

Python: `py/tests/test_content_pack.py::test_static_add_column_does_not_wrap`:
```python
def test_static_add_column_does_not_wrap():
    sts.load_content(json.dumps({"version": 1,
        "powers": [{"id": "gp_d5add", "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 1000}]}],
        "cards": [{"id": "gc_d5add", "cost": 0, "type": "Skill",
                   "effects": [{"Apply": {"power": "gp_d5add", "amount": 40, "target": "Me"}}]}]}))
    c = sts.Combat(DECK + ["gen:gc_d5add"], "cultist", seed=1)
    play_power(c, "gen:gc_d5add")
    f = sts.Features(extra_rows=True)
    b = f.encode([c])
    col = b["rows"][b["row_entity"] == 0][:, f.row_names.index("static_add")]
    assert 40000.0 in col, col
```
Entity 0 is the player of state 0. Today the value is -25536.

**Must stay unchanged.**
- golden.txt and golden_proving.txt byte-identical; codec_golden.txt.
- H4 identical: in-range values compute the same in i32 or i64.
- `statics.rs::statics_table_matches_fast_path`.
- packs.rs's `negative_generated_add_static_counts`, `generated_block_multiply_rounds_once_with_frail` and the debuff replacement tests.
- fuzz.
- series_check PASS. The static rows are opt-in and outside the check's row kinds, and the f32 expr form is equal on official values.
- `state.rs` is a fingerprinted rule file, so the rules fingerprint changes. That is expected on this branch, and nothing stores the value: `solvedb/tests/fingerprint.rs` recomputes it, and `content_tables_pinned` is unaffected. The optional sites in effects.rs and powers.rs are fingerprinted files too; that changes nothing further.

### D6. A pack power named like an official power loads but can never be applied

- **Severity:** low · **Reach:** content packs · **New on this branch:** no (already on main; the branch added statics, replacements and RandomApply to the same path) · **Review:** CONFIRMED; the verifier ran a throwaway test (review id v19; cut by the 15-finding cap)
- **Where:** `engine/src/registry.rs:301-309` in `load_pack`, which stores a pack power under any id. Related:
  - `:661-669` in `parse_effect`: `Apply` looks the name up among the official powers first. `RandomApply` at `:633-640` does the same.
  - `official_power` at `:457-459`, which compares the name with each official power's Rust Debug name.

**What goes wrong.** A pack card names the power it applies by id, and `parse_effect` tries the official powers first:

`match official_power(p) { Some(power) => (Effect::Apply { power, amount, target }, None), None => (Effect::Apply { power: Power::GEN[0], amount, target }, Some(p.to_string())), }`

Suppose a pack defines a power whose id equals an official power's name ("Weak", "Strength", "DemonForm", ...). Then:
- every card that names it gets the official power;
- the pack power is never listed among the card's generated powers;
- `bind` never gives it a slot (`bind` puts a combat's generated cards and powers into reserved slots, which is called the binding);
- its hooks, statics and replacements never run.

`load_pack` accepts this silently, although its own contract says an id loaded again "with another definition is an error".

**Reproduce.**
- Pack: `{"version": 1, "powers": [{"id": "Weak", "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 5}]}], "cards": [{"id": "d6_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "Weak", "amount": 2, "target": "Me"}}]}]}`. `load_pack` returns Ok.
- Bind `["gen:d6_card", "Strike"]`, play the card, then play Strike at the Jaw Worm.
- Actual: the player holds official Weak 2, Strike deals 4 (6 × 0.75), and the binding's power slots stay free.
- Control: the same power under id `d6_weak`, with a card that applies it, binds `Gen0`, and Strike deals 16 (6 + 2 × 5).

**Fix.** In `load_pack`, right after reading a power's `id` (`registry.rs:302`), refuse the power when `official_power(&id).is_some()`. The error should say the id is an official power's name.

Alternative: let the pack power shadow the official one. Rejected: it would change what every official card naming that power does.

**Test first.** `engine/tests/packs.rs::a_pack_power_cant_take_an_official_name`: `assert!(load_pack(r#"{"version": 1, "powers": [{"id": "Weak", "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 5}]}]}"#).is_err())`. This returns Ok today.

**Must stay unchanged.**
- Every pack in the repo uses non-official ids and still loads:
  - the round trip's `rt_pow_*`;
  - gen_content.py's `gp{seed}_{i:03d}` and `probe_<hash>`;
  - the Python tests' `gp_df` and `gp_m{i}`;
  - engine/tests/registry.rs's `gp_df` and `gp_n{i}`;
  - packs.rs's `pk_*` and `fx_*`.
- No rule changes and no pins.

### D7. GrowDamage on a pack card loads but never grows the card

- **Severity:** low · **Reach:** content packs · **New on this branch:** yes · **Review:** CONFIRMED; the verifier ran a throwaway test (review id v20; cut by the 15-finding cap)
- **Where:**
  - `engine/src/registry.rs:721-732` in `card_effects`, which refuses only RemoveSelf, ReduceSelf and ReplayCard on a card (`:725`).
  - `:52-55` in `variant_index`: `if !base.is_official() { return None; }`.
  - `engine/src/state.rs:1114-1120` in `grow_damage`: `let Some(idx) = crate::registry::variant_index(...) else { return };`.
  - `registry.rs:746` in `parse_card`, which refuses GrowDamage only in `turn_end`.
  - Docs:
    - `docs/decisions.md:2256-2259` ("A generated card can't grow (variants need an official base)");
    - `docs/decisions.md:2252-2255`, which says every official card loads back;
    - `README.md:212-220`, which says the same;
    - the header doc of `engine/tests/packs.rs` (lines 1-3).

**What goes wrong.** GrowDamage (Rampage: the card's damage grows for the rest of the combat) works by turning the copy in play into a variant. A variant is an official card with per-copy overrides, interned process-wide and held in the binding's variant slots. `variant_index` only makes variants of official cards. A pack card is always generated, so `grow_damage` returns at `else { return }` and the card keeps its damage.

The loader accepts the effect, and `card_json(Rampage)` round-trips field by field. The features write `grow_damage = 5` (py/src/features.rs:897) for a card that never grows. Nothing errors or warns.

**Reproduce.** The verifier ran this.
- Load the entry that `registry::card_json("d7_rampage", CardId::from_name("Rampage").unwrap().def())` writes: a cost 1 Attack with effects `[{"Damage": {"amount": 8, "hits": 1, "target": "Opponent"}}, {"GrowDamage": 5}]`. `load_pack` returns Ok.
- Bind `["gen:d7_rampage"]` in `bound_combat`, play it at the Jaw Worm, move the copy from the discard pile back to the hand, and play it again.
- Actual: 8 damage, then 8 again, with no variant held (`s.binding.n_variants() == 0`).
- Official Rampage, run the same way: 8, then 13, with one variant held.

**Fix.** Refuse GrowDamage on pack cards.
- In `card_effects` (registry.rs:725), refuse `Effect::GrowDamage(_)`. Give it its own message: a generated card can't grow yet, because variants need an official base.
- `card_effects` also reads `turn_end`, so the `|| matches!(e, Effect::GrowDamage(_))` at :746 becomes redundant. Drop it.
- Leave GrowDamage allowed in power hooks. There it grows the card in play, which works for official cards. A generated card in play still doesn't grow; say so in the doc line.
- Update `packs.rs::every_official_card_round_trips`:
  - for a card whose `all_effects()` holds `Effect::GrowDamage(_)` (Rampage and Rampage+), assert that `load_pack` refuses its entry, count it, and skip the bind;
  - every other card round-trips as today;
  - end with `assert_eq!((n, refused), (CardId::all().count() - 2, 2))`;
  - add `use sts_engine::effects::Effect;` (`sts_engine::*` doesn't re-export it).
- Update the docs:
  - README.md:219-220: every card loads back "but Rampage and Rampage+, which packs refuse until a generated card can grow".
  - packs.rs's header doc: the same exception.
  - Add a line to this fix spec's decisions entry, superseding the round-trip claim at decisions.md:2252-2255.

This doesn't take the owner's open decision. decisions.md:2256-2259 leaves letting generated cards grow to spec 10 stages 2-5. The refusal only turns a silent no-op into an error, as registry-lite.md:127-128 asks, and it is one line to undo.

Alternative: let generated cards grow, with variants keyed by the registry's definition index instead of an official CardId, kept in value order across processes. That is spec 10 stage 2+ work.

**Test first.**
- `engine/tests/packs.rs::a_pack_card_cant_grow`: `load_pack` of `{"version": 1, "cards": [<card_json("d7_rampage", Rampage's def)>]}` returns an error. It returns Ok today.
- The updated `every_official_card_round_trips` also fails today, because Rampage loads.

**Must stay unchanged.**
- Official Rampage plays exactly as today. That covers golden_proving.txt's `rampage` set, `engine/tests/overrides.rs` and `packs.rs::a_replayed_copys_grown_variant_is_dropped`.
- Every other official card still round-trips.
- Changed on purpose: the round-trip test's count, and the README, packs.rs header and decisions claims.
- No pins.

## Build step details

The two baselines are recorded once, at the main file's step 0, before any edit of the spec. Don't record them again before this group's first step: that would overwrite `target/sc_head.npz` with a dump made after steps 3-6, and a later compare couldn't see what those steps changed. Step 0 records them this way:
- H4: `cargo run --release -p sts-engine --example two_turn_phases -- 100 --check target/h4_head.txt`.
- series_check:
  - `bash scripts/dev_sts.sh`, then `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe scripts/series_check.py dump target/sc_head.npz --cards "Body Slam,Heavy Blade,Perfected Strike,Whirlwind" models/value_effects.contract.pt models/value_ids.contract.pt models/value_reference.contract.pt`.
  - `--cards` must come right after the output path, and the net paths after it.
  - Compare later builds against this HEAD file, not against the shared .venv module. The .venv holds main's build, which lacks the branch's columns (expr_*), and `compare` checks only columns present in the old file. So a .venv baseline would skip exactly the columns step 5 changes. Without net paths, `dump` checks no nets at all.

Steps 2, 3, 4, 6, 7 and 8 edit `engine/src/registry.rs`; step 5 edits `engine/src/state.rs` and `py/src/features.rs`. Do the steps in this order. Their test packs use in-range values and exact keys, so earlier steps' tests stay valid as later steps add checks, and each refusal test fails before its own step.

1. **D1: bound picks past the node cap.**
   - Files:
     - `engine/src/search.rs`: `Tree::expand`'s decision branch (259-270), the comment at 236-237 and the `max_nodes` doc comment at 36.
     - `docs/specs/rules-engine-upgrade.md`: line 24 and 213-220.
     - `docs/extending.md`: 94-97.
     - `docs/decisions.md`: start this fix spec's entry at the end of the file if no earlier group has, with a line superseding 1937-1938.
   - Test: `engine/tests/packs.rs::a_long_pick_stays_within_the_node_cap`.
   - Acceptance:
     - `cargo test --release -p sts-engine --test packs a_long_pick` → 1 passed. Before the change it fails with 36,559 nodes; after it, about 1,100.
     - `cargo test --release -p sts-engine --test decisions` → all pass.
     - `cargo run --release -p sts-engine --example two_turn_phases -- 100 --check target/h4_d1.txt && cmp target/h4_head.txt target/h4_d1.txt` → no output, exit 0.
2. **D2 + D6: refuse costs play can't pay, and official power names.**
   - Files:
     - `engine/src/registry.rs`: `parse_card` and `load_pack`.
     - `README.md` pack section: an X-cost card costs 0, costs can't be negative, and pack power ids can't be official power names.
   - Tests: `packs.rs::packs_refuse_costs_play_cant_pay` (with the `d2_x0` control), `packs.rs::a_pack_power_cant_take_an_official_name`.
   - Acceptance: `cargo test --release -p sts-engine --test packs --test registry` → all pass, including `every_official_card_round_trips` and `every_official_power_round_trips`.
3. **D3 (a): ScaledDamage shape rules at load.**
   - Files:
     - `engine/src/registry.rs`: the `parse_effect` ScaledDamage arm, `amount` (the Strike-only tag and k-needs-of rules), `parse_card`, `parse_hook`, and a new `reads_x` helper.
     - `py/src/features.rs`: the comments at 839 and 851 only.
     - `README.md` pack section: the four shape rules.
   - Test: `packs.rs::packs_refuse_scaled_damage_the_features_cant_read` (six packs, `d3_kno` included).
   - Acceptance: `cargo test --release -p sts-engine --test packs --test amounts` → all pass.
4. **D7: refuse GrowDamage on pack cards.**
   - Files:
     - `engine/src/registry.rs`: `card_effects` at 725; drop the redundant check at 746.
     - `README.md`: 219-220.
     - `engine/tests/packs.rs`: header doc, lines 1-3.
     - `docs/decisions.md`: this fix spec's entry, superseding 2252-2255's round-trip claim.
   - Tests: new `packs.rs::a_pack_card_cant_grow`; updated `packs.rs::every_official_card_round_trips` (Rampage and Rampage+ refused and counted; import `sts_engine::effects::Effect`).
   - Acceptance:
     - `cargo test --release -p sts-engine --test packs` → all pass.
     - `cargo test --release -p sts-engine --test overrides --test golden` → all pass (official Rampage unchanged; golden and golden_proving identical).
5. **D5: saturating damage, block and replacement arithmetic.**
   - Files:
     - `engine/src/state.rs`: `interpret_attack_damage`, `interpret_block`, `replaced`, `attack_damage`, `resolve`; the optional sites if wanted.
     - `py/src/features.rs`: `static_row` at 1068, the expr form at 840-842, `expr_value` at 1563.
   - Tests: `packs.rs::huge_static_and_replacement_values_saturate`, `py/tests/test_content_pack.py::test_static_add_column_does_not_wrap`.
   - Acceptance:
     - `cargo test -p sts-engine --test packs huge_` (debug profile: no overflow panic) → 1 passed.
     - `cargo test --release` (engine and solvedb, the workspace's default members) → all pass, including golden, golden proving, codec, statics and fuzz.
     - `cargo run --release -p sts-engine --example two_turn_phases -- 100 --check target/h4_d5.txt && cmp target/h4_head.txt target/h4_d5.txt` → identical.
     - `bash scripts/dev_sts.sh`, then `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe py/tests/test_content_pack.py` → ends with "N passed".
     - series_check, with the same `--cards` and nets as the baseline:
       - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe scripts/series_check.py dump target/sc_d5.npz --cards "Body Slam,Heavy Blade,Perfected Strike,Whirlwind" models/value_effects.contract.pt models/value_ids.contract.pt models/value_reference.contract.pt`;
       - then `../../../.venv/Scripts/python.exe scripts/series_check.py compare target/sc_head.npz target/sc_d5.npz` → a line starting "PASS:" (3 nets).
6. **D4 step 1: checked number conversions and the 255-effect cap.**
   - Files: `engine/src/registry.rs`: new `num` and `opt_num` helpers, all 22 `as` cast sites, the `den` check on the converted value, and the cap in `parse_card`.
   - Test: `packs.rs::packs_refuse_bad_numbers`.
   - Acceptance: `cargo test --release -p sts-engine --test packs --test registry` → all pass.
7. **D4 step 2: lists and flags must have the right JSON type.**
   - Files: `engine/src/registry.rs`: new `list` and `opt_bool` helpers; remove `json::Value::items`.
   - Test: `packs.rs::packs_refuse_bad_lists_and_flags`.
   - Acceptance: `cargo test --release -p sts-engine --test packs --test registry` → all pass.
8. **D4 step 3: unknown keys refused inside structural objects.**
   - Files:
     - `engine/src/registry.rs`: a new `only` helper that also refuses non-objects; 16 kinds of object, with the eight effect field objects through one keyed call in `parse_effect`.
     - `README.md`: what is and isn't checked.
   - Test: `packs.rs::packs_refuse_unknown_keys`, including the row-given-as-a-number pack and the metadata control pack that must load.
   - Acceptance:
     - `cargo test --release -p sts-engine --test packs --test registry` → all pass.
     - `bash scripts/dev_sts.sh`, then with `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe`: `scripts/tests/test_gen_content.py` and `py/tests/test_content_pack.py` → each ends with "N passed".
     - The same Python with `-c "import sts; print(sts.load_content('data/bench/gen_powers_pack.json'))"` → prints a 16-hex-digit hash, no error.
     - `scripts/tests/test_content_selfplay.py` → an "ok" line per test and no traceback (it prints no "passed" line).
9. **D3 (b), optional (low): the heuristic prices every ScaledDamage shape a pack can load.**
   - Files: `engine/src/heuristic.rs`: replace `_ => (0.0, 0.0)` at 103 only; add `Amount` to the `crate::effects` import.
   - Test: `packs.rs::heuristic_prices_a_constant_scaled_attack_like_damage`.
   - Acceptance:
     - `cargo test --release` → all pass.
     - H4 again (`--check target/h4_d3b.txt`, `cmp` against `target/h4_head.txt`) → identical. The heuristic is H4's evaluator.
     - Rebuild with `bash scripts/dev_sts.sh`, dump `target/sc_d3b.npz` as in step 5 and compare with `target/sc_head.npz` → "PASS:" (heuristic bit-identical on official content).
     - `scripts/tests/test_gen_content.py` → "N passed". The generator prices cards with the heuristic, and same seed must still give the same bytes.

Final check after the last step:
- `cargo test --release` → all pass.
- `cargo test -p sts-engine --test packs` in the debug profile → all pass, with no overflow panic.
- The H4 cmp and the series_check compare against the HEAD baselines → identical / PASS.
- `py/tests/test_sts.py` (includes `test_decision_actions`) and the four Python files above → pass.

## Pins for this group

No recorded pin, golden set or fingerprint pin changes in group D.

These must stay byte-identical after every step:
- engine/tests/data/golden.txt (9,000 games; its hash is the registry's rules version).
- golden_proving.txt (every proving set, `rampage` included).
- codec_golden.txt.
- solvedb's `content_tables_pinned` (0x5a922915c8ae26dd).
- The H4 check file (`two_turn_phases 100 --check`), compared against `target/h4_head.txt` recorded at HEAD.
- series_check against a HEAD-built baseline (`target/sc_head.npz`): heuristic and contract nets bit-identical, every feature column equal (branch-only columns such as expr_* included).
- The contract pins (scripts/tests/data/contract/pins.json), golden_rows, TRAIN_PIN, ARRAYS_PIN, the lookahead names and the curriculum digests.
- The content hash that `load_pack` returns for every pack that still loads (it is FNV-1a of the text).

Expected changes:
- The rules fingerprint value changes in the D5 step, because engine/src/state.rs is one of the 8 fingerprinted rule files. If the optional D5 sites in effects.rs or powers.rs are done, those are fingerprinted too, which changes nothing further.
  - No test stores that value: solvedb/tests/fingerprint.rs recomputes it.
  - The solved DB is already retired on this branch.
  - The edits in D1 (search.rs), D3 (registry.rs, heuristic.rs, features.rs comments), D4, D6 and D7 (registry.rs) don't touch fingerprinted files.
- One test expectation changes on purpose: engine/tests/packs.rs::every_official_card_round_trips (D7). Rampage and Rampage+ are refused; every other official card still round-trips.
- Doc claims change:
  - The pick bound: rules-engine-upgrade.md:24 and 213-220, extending.md:94-97, and a decisions line superseding 1937-1938.
  - The round-trip claim: README.md:219-220, packs.rs's header doc, and a decisions line superseding 2252-2255.
  - README's pack section gains:
    - X-cost cards cost 0, and costs can't be negative;
    - official power names are refused as pack power ids;
    - the ScaledDamage shape rules;
    - GrowDamage on pack cards is refused;
    - strict keys and types inside structural objects, but not at card, power or pack level.

## Decisions for this group

None in group D.

Every fix is one of three kinds:
- a loader refusal;
- a search rule that applies only to picks past the node cap;
- local integer arithmetic made saturating.

Each one reverts with one commit, and none changes official play, recorded data or a pin.

Three calls look like owner decisions but are the manager's under the standing grants (cheap to reverse):
1. D7: refusing GrowDamage on pack cards means card_json(Rampage) no longer loads.
   - It doesn't decide the owner's open question of letting generated cards grow (spec 10 stages 2-5, decisions.md:2256-2259). It only turns a silent no-op into an error.
   - The review's verifier (v20) leaned the other way: it saw the round-trip goal as the owner's and suggested only a doc line. Spec 10 stage 1 was confirmed by the manager, so the manager can choose. Recommended: refuse.
2. D3: packs can no longer load several shapes, and the features gain no new columns:
   - two-sided ScaledDamage;
   - CardsTagged other than Strike;
   - EnergySpent outside an X-cost card's play;
   - an amount object with k but no of.
   
   This keeps the default feature vocabulary and every Python pin unchanged, and adding columns later stays possible. D3 (b), the heuristic fallback, is optional: skip it if the manager reads the owner's "heuristic stays blind through the series" rule as covering new atoms, not just row kinds.
3. D4 step 3: card, power and pack objects stay unchecked, so a misspelled card flag or a misspelled `hooks`/`statics`/`rows` key still loads silently. Checking them would mean listing the generator's metadata names in the engine. Recommended: leave them unchecked, as specified, and say so in the README.

## Notes the checker left

Earlier series_check runs on this branch report "4 contract nets", but no file or commit names the fourth. The steps pass the three contract nets under models/ (value_effects.contract.pt, value_ids.contract.pt and value_reference.contract.pt, through the models junction), so the PASS line will say 3 nets. The tiny nets in scripts/tests/data/contract can't be used: they are pre-contract (no schema, and no .contract.pt beside them), so stsnet.load refuses them. If the manager names the fourth net before step 0, add it to every dump.
