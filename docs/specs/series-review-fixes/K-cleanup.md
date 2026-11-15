# Series review fixes, appendix K: optional cleanup

Status: idea (2026-11-02, K1-K20 are optional cleanup in the backlog (part 3), not scheduled; decisions 'Series review fixes: the cut').

Part of `docs/specs/series-review-fixes.md`. Read that file first: it has the why, what must
stay true, the decisions, the build order and how to build and check. This file holds the
group's entries, then its build step details, the pins it may change, its decisions and the
notes its checker left. Line numbers are at `d9327a2`.

## Items

These are not bugs. The review flagged them as reuse, simplification, efficiency or altitude items (review ids c01-c25), and an independent verifier re-checked each one against the code. The twenty that survived (CONFIRMED or PLAUSIBLE) are below, most worthwhile first. The five refuted ones are listed at the end so nobody redoes them. Each item must leave every check byte-identical. K8 is the one exception, and it says exactly what changes. None of these items blocks landing engine-next.

**Terms.**
- *Golden games*: the recorded games in two files, both replayed by the test `golden_trajectories` (`engine/tests/golden.rs`). `engine/tests/data/golden.txt` holds the 9,000 official games. `engine/tests/data/golden_proving.txt` holds the proving sets (`whirlwind`, `accuracy`, `wraith`, `survivor`, `hologram`, `headbutt`, `rampage`). Every game must replay byte for byte.
- *H4*: the search identity check, `cargo run --release --example two_turn_phases 100 --check <file>`. It takes 100 states from heuristic play of official elite and boss fights. It searches each one two turns deep (sample_k 4, max_nodes 400,000) and one turn deep (default config) with the engine's own `search()`. It writes every search's nodes, leaves, cuts, chosen action and option-value bits. It covers official content only: no proving cards, no packs.
- *Rule files*: the 8 engine files hashed into the solved DB's rules fingerprint, listed in `solvedb/src/fingerprint.rs`: state, cards, monsters, powers, hooks, effects, chance and character. The hash ignores comments and whitespace, so only code edits count.
- *Proving content*: cards and powers added to prove the series' new rules. The cards are in no deck pool: Whirlwind, Accuracy, Wraith Form, Caltrops, Survivor, Burst, Hologram, Headbutt, Rampage and Protect, plus their upgrades.
- *Binding*: a combat's table of bound pack (generated) content and of *variants*. A variant is a per-copy card override, such as a grown Rampage. Each variant sits in one of 4 slots and has its own card id.
- *Row kinds*: the kinds of feature rows. `triggered`, `threshold` and `held` are written by default. `static`, `countdown`, `replacement` and `pattern` are written only with `extra_rows` (opt-in), or when a net's layout lists one of them.
- *Known top*: draw-pile cards whose place the player knows (from Headbutt), plus *floaters*, which are known cards at an unknown place.

**When to do them.**
- Do them after the fix steps for groups A-G, on the code those fixes leave. Several fixes edit the same lines, and each item names them ("After ...").
- Line numbers below are at HEAD d9327a2. After the fixes, find the code by function name.
- The baseline for each byte-identity check is the build just before the cleanup step, not main.
- An item that edits code in a rule file changes the rules fingerprint. That costs nothing while engine-next is unlanded, because the branch changes the fingerprint anyway. After landing, each such edit retires the solved DB again. So do those items before landing, or batch them into one later landing.
- K8 must be done before landing or not at all.

**Engine check.** Run everything from the worktree root.
1. Before editing, record H4: `cargo run --release --example two_turn_phases 100 --check target/h4_before.txt`.
2. After editing, run `cargo test --release`. It covers the engine and solvedb, including golden games, `codec_golden` and fuzz. Every binary must report `test result: ok`.
3. Run H4 again into `target/h4_after.txt`. `cmp target/h4_before.txt target/h4_after.txt` must print nothing.
4. `git status --short engine/tests/data` must be empty: no pin gets re-recorded.

Add `-j 4` and `-- --test-threads=4` when other jobs share the machine.

**Features check** (items in `py/src`). Run everything from the worktree root. Stop any Python process that loaded `sts` from `target/pyroot` first: Windows locks a loaded `.pyd`, and `dev_sts.sh` deletes the folder before it builds.

Before the change:
```bash
PY=../../../.venv/Scripts/python.exe
bash scripts/dev_sts.sh
rm -rf target/pyroot_before && cp -r target/pyroot target/pyroot_before
PYTHONPATH="$PWD/target/pyroot_before" $PY target/features_hashes.py target/fh_before.json
PYTHONPATH="$PWD/target/pyroot_before" $PY scripts/series_check.py dump target/sc_before.npz
```
(The `rm -rf` matters: if `target/pyroot_before` already exists, `cp -r` copies into it instead of replacing it.)

Make the change, then:
```bash
bash scripts/dev_sts.sh
PYTHONPATH="$PWD/target/pyroot" $PY target/features_hashes.py target/fh_after.json
PYTHONPATH="$PWD/target/pyroot" $PY scripts/series_check.py dump target/sc_after.npz
cmp target/fh_before.json target/fh_after.json
$PY scripts/series_check.py compare target/sc_before.npz target/sc_after.npz
```
- `cmp` must print nothing.
- `compare` must end with a line starting `PASS:`.

Don't pass the three tiny nets in `scripts/tests/data/contract/` to `series_check.py dump`. They are pre-contract nets (no `schema`), and `stsnet.load` refuses them unless a converted `<name>.contract.pt` sits beside them. None is in the repo, so the dump would stop with a ValueError. `test_contract.py` below already checks their torch and Rust outputs bit for bit, through both loaders (`test_tiny_nets_unchanged`, `test_gather_net_outputs`, `test_converter_identity`). If you want nets in the dump anyway, convert copies first: copy them to `target/k_nets/`, run `PYTHONPATH="$PWD/target/pyroot_before" $PY scripts/convert_net.py target/k_nets/tiny_effects.pt target/k_nets/tiny_ids.pt target/k_nets/tiny_effects_hp.pt`, then pass the `target/k_nets/` paths to both dumps.

Then these files must pass with the new module, each run as `PYTHONPATH="$PWD/target/pyroot" $PY <file>`:
- `py/tests/test_sts.py` (checks `py/tests/data/golden_rows.npz` byte for byte)
- `py/tests/test_content_pack.py`
- `scripts/tests/test_contract.py` (contract pins and the tiny nets)
- `scripts/tests/test_net.py` (TRAIN_PIN)
- `scripts/tests/test_content_selfplay.py` (ARRAYS_PIN)
- `scripts/tests/test_threshold_rows.py`
- `scripts/tests/test_granting.py`
- `scripts/tests/test_lookahead.py` (`lookahead_off_names.json`, `lookahead_rows.npz`)
- `scripts/tests/test_rates.py` (rate columns; `test_generated_copy_same_columns` covers the per-state card path with rates)
- `scripts/tests/test_curriculum.py` (`curriculum_pins.json` digests; the slowest and most memory-hungry of these, so run it when no heavy job runs)

Finally `git status --short py/tests/data scripts/tests/data` must be empty.

series_check and `golden_rows.npz` cover only the default row kinds and official content. The script below also covers the opt-in kinds, a net layout, the rate and lookahead columns, generated (pack) cards and grown Rampage variants. Save it as `target/features_hashes.py`. It was checked against the Python API and the pack parser at HEAD, not run:

```python
# target/features_hashes.py OUT.json: run from the worktree root, once per module
# (PYTHONPATH=target/pyroot_before, then target/pyroot), then cmp the two outputs.
import json, os, sys
sys.path[:0] = [os.path.abspath("scripts"), os.path.abspath("scripts/tests")]
import sts, selfplay, contract_pins

gen, _ = selfplay.load_content("data/bench/gen_powers_pack.json")
apply_me = lambda p: [{"Apply": {"power": p, "amount": 2, "target": "Me"}}]
sts.load_content(json.dumps({"version": 1, "powers": [
    {"id": "k_static", "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 2},
                                   {"modifies": "BlockGained", "stage": "Multiply", "num": 3, "den": 2}]},
    {"id": "k_repl", "replacements": [{"event": "DamageTaken", "action": {"Cap": 3}, "then": [{"ReduceSelf": 1}]}],
     "hooks": [{"trigger": "RoundEnd", "effects": [{"ReduceSelf": 1}]}]}],
    "cards": [{"id": "kc_static", "cost": 0, "type": "Skill", "effects": apply_me("k_static")},
              {"id": "kc_repl", "cost": 0, "type": "Skill", "effects": apply_me("k_repl")}]}))

states = list(contract_pins.fixed_states())
extras = [["Accuracy", "Wraith Form", "Caltrops", "Burst", "Survivor", "Hologram"],
          ["Headbutt", "Rampage", "Rampage+", "Whirlwind", "Body Slam", "Heavy Blade"],
          ["gen:kc_static", "gen:kc_repl"] + ["gen:" + c["id"] for c in gen["cards"][:2]]]
for i, extra in enumerate(extras):
    for ch in ("ironclad", "silent"):
        c = sts.Combat(sts.starter_deck(ch) + extra, "jaw_worm", seed=i + 1, character=ch)
        for _ in range(40):
            if c.is_over():
                break
            states.append(c.clone())
            c.step(sts.greedy_action(c))

enc = {"effects": sts.Features("effects"),
       "extra": sts.Features("effects", extra_rows=True),
       "layout": sts.Features("effects", row_kinds=["triggered", "held", "pattern"]),
       "rates": sts.Features("effects", rates=True, lookahead=True, start_hp=True, extra_rows=True),
       "ids": sts.Features("ids")}
out = {k: contract_pins.batch_hashes(f.encode(states)) for k, f in enc.items()}
out["n_states"] = len(states)
with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=1, sort_keys=True)
```
The ids encoder prints one warning that it sees generated cards as unknown. That is expected. If `selfplay.load_content` refuses the generated pack, an A-G fix to the loader (D4) broke it. Training configs use that pack, so fix that regression first; it isn't a K problem.

### K1. Floor a replacement's result inside `replaced()`  (from review id c16; CONFIRMED)
- **Where:** `engine/src/state.rs:1445` (`replaced`) and its only three callers:
  - `take_damage` at :1482-1486: `.unwrap_or(0)`, then `dmg.max(0)` twice.
  - `lose_hp` at :1498: `.unwrap_or(0).max(0)`.
  - `apply_power` at :1619-1623: `Some(a) if a > 0 => a * amount.signum(), _ => return`.
- **What:** All three callers treat the replaced amount as a size, where 0 or below means nothing happens. Each one writes that rule itself, in a different shape. Today each caller already treats `Some(n)` with n ≤ 0 exactly like `None`: no block absorbed and no HP lost, or the debuff cancelled. That includes negative pack amounts when no replacement row applies. So moving the rule into `replaced` is byte-identical.
- **Change:** Do this after D5, which changes the arithmetic in `replaced` and may clamp it. Keep whatever D5 wrote.
  1. End `replaced` with `(n > 0).then_some(n)` instead of `Some(n)`. Its doc comment should say that `None` means the event was cancelled or its amount ended at 0 or below. Move `lose_hp`'s comment ("a replacement can't turn HP loss into healing") there.
  2. Drop the callers' clamps:
     - `take_damage`: `let absorbed = dmg.min(*block);` and `let lost = dmg - absorbed;`.
     - `lose_hp`: `let n = self.replaced(who, Replaced::HpLoss, n).unwrap_or(0);`.
     - `apply_power`: `let amount = if debuff { let Some(a) = self.replaced(dst, Replaced::DebuffApplied, amount.abs()) else { return }; a * amount.signum() } else { amount };`.
  3. K1 adds only this one test, on the amount after all rows have run. Don't add a floor per row or on the input: `Cap` compares against the running amount, and every `Cancel` row runs its `then` effects (Artifact's stack loss) whatever the amount. If D5 put a clamp inside the loop, leave that clamp as D5 wrote it.
- **Worth it because:** The caller of a new `Replaced` event would have to remember its own clamp. This branch already missed it twice, and review caught both (decisions.md:2309 and 2347-2349): a replaced HP loss below 0 would have healed, and a DebuffApplied replacement could leave a negative debuff. The change is about 10 lines.
- **Check:** Engine check, including `cargo test --release -p sts-engine --test replacements --test packs` (Intangible, Artifact, pack replacements) and the golden `wraith` proving set.

### K2. Debuff countdowns follow `is_duration_debuff`  (from review id c07; CONFIRMED)
- **Where:** `engine/src/hooks.rs:257`, in `hooks`: `Power::Vulnerable | Power::Weak | Power::Frail => COUNTDOWN,`. Compare `engine/src/powers.rs:128`, `is_duration_debuff`, which lists the same three powers.
- **What:** On main, the round-end countdown (`Powers::end_of_round`) ran for every power where `is_duration_debuff()` was true. The branch moved the countdown into the hooks table and wrote the three powers out by hand. `is_duration_debuff` still decides Artifact blocking (through `is_debuff`) and the just-applied skip (state.rs:1632). No test ties the two lists together.
- **Change:** Replace the arm, in the same place, with a guarded one: `p if p.is_duration_debuff() => COUNTDOWN,`. The arms after it (Intangible, WraithForm, Thorns, Burst, `_`) are not duration debuffs, so every power gets the same slice as before. Leave `INTANGIBLE` (:204) and `COUNTDOWN` (:218) as two constants. They are byte-identical, but merging them would only lose Intangible's doc comment.
- **Worth it because:** Suppose someone adds a new official duration debuff to `is_duration_debuff` only. Today Artifact would block it and it would get the skip flag, but it would silently never count down, and every test would still pass. After the change it counts down, and `round_end_and_replacement_lists_match_the_tables` fails until `ROUND_END_POWERS` lists it, which is the reminder you want. The fix is one line.
- **Check:** Engine check, including `cargo test --release -p sts-engine --test replacements --test statics`: `round_end_and_replacement_lists_match_the_tables` (replacements.rs), and `vulnerable_weak_frail_have_round_end_hooks` and `countdowns_are_round_end_hooks` (statics.rs). `hooks()` returns the same slice for every power, so countdown feature rows and `power_json` can't change.

### K3. One static interpreter behind `interpret_attack_damage` and `interpret_block`  (from review id c06; CONFIRMED)
- **Where:**
  - `engine/src/state.rs:1367` (`interpret_attack_damage`) and `:1398` (`interpret_block`), about 25 lines each.
  - The liveness rule, `if stage == StaticStage::Add { stacks != 0 } else { stacks > 0 }`, is written at :1378 and :1403.
  - It appears a third time as a feature value in `py/src/features.rs:1069` (`static_row`, Multiply arm: `if stacks > 0 { st.num as f32 / st.den as f32 - 1.0 } else { 0.0 }`).
- **What:** Both functions run the same pipeline:
  - the liveness rule;
  - the filter on `modifies`, stage and `static_holds` (block checks `static_holds` inside the loop instead of in the filter, with the same result);
  - the add, `num += (amount × stacks) × den`;
  - the multiply;
  - one final `(num.max(0) / den) as i16`.

  The only real difference is that block floors `num` at 0 before each multiply, because Frail scales the adds' total floored at 0. That difference matters only when a multiply's `num` is negative, and pack statics can have one: `parse_static` refuses only `den <= 0`. Block reads `self.player.powers`, which is `self.powers(Who::Player)`.
- **Change:** Do this after C5 and D5, which both change these two functions, and after G1, which makes `statics_table_matches_fast_path` compare the fast path with the rows again.
  1. Write one private `fn interpret(&self, base: i16, passes: &[(Who, Modifies, StaticStage)], floor_before_multiply: bool) -> i16` that holds the loop. For each pass, in order: for each power in `self.binding.powers_in_play()`, read `self.powers(who).get(p)`, apply the liveness rule, then apply the matching statics. On a multiply, first set `num = num.max(0)` when the flag is on. Keep D5's arithmetic exactly as D5 left it.
  2. `interpret_attack_damage` passes `[(src, DamageDealt, Add), (dst, DamageTaken, Add), (src, DamageDealt, Multiply), (dst, DamageTaken, Multiply)]` and `false`.
  3. `interpret_block` passes `[(Who::Player, BlockGained, Add), (Who::Player, BlockGained, Multiply)]` and `true`.
  4. Keep both public names as these one-line wrappers. They are called by `attack_damage` (:1320), `gain_block` (:1601), `tests/statics.rs:56` and `:68`, and `tests/packs.rs:175`.
  5. Put the liveness rule in one public function in hooks.rs: `impl StaticStage { pub fn live(self, stacks: i16) -> bool { match self { StaticStage::Add => stacks != 0, StaticStage::Multiply => stacks > 0 } } }`. Call it from `interpret`. Switch `features.rs:1069` to it in K-step 6 with the other features edits, not here. That way this step needs no module rebuild. Inside the Multiply arm, `st.stage.live(stacks)` is the same `stacks > 0`.
  6. Keep whatever C5 passes to `static_holds`. If C5 gave `static_holds` a second `Who` (the attacker, for `CardInPlayTagged`), add that as a parameter of `interpret`. Pass `src` from `interpret_attack_damage`, and whatever C5 passes from `interpret_block` (presumably `Who::Player`).
- **Worth it because:** Today any change to the static pipeline has to be made twice. Commit 1a51035 made the same edit in both functions, and 662b6c6 deleted a third copy of the liveness rule after it had drifted. A fix made in one interpreter and not the other would show only with generic or generated statics (Accuracy, Red Skull, pack powers). About 25 lines are duplicated.
- **Check:**
  - Engine check, including `cargo test --release -p sts-engine --test statics --test packs` (`statics_table_matches_fast_path`, `accuracy_adds_to_shivs_only`, `negative_generated_add_static_counts`, `generated_block_multiply_rounds_once_with_frail`). The golden `accuracy` proving set stays unchanged.
  - For extra certainty: a throwaway test that keeps the two old bodies and compares them with the new code. Run it over the random walk in `tests/statics.rs` plus a pack static with a negative multiply `num`, then delete it.

### K4. Move the card-in-play cursor in place  (from review id c13; CONFIRMED)
- **Where:** `engine/src/state.rs`. Whole rebuilds `self.stage = Stage::PlayingCard { card, target, next, hit, x, more }` appear at:
  - :631 and :637, in `apply_action` (Choose and Done), where only `more.pick` changes;
  - :682, :687, :689, :695 and :698, in `run`, where the cursor moves (:695 also sets the pick).

  The full destructures that feed them are at :612, :635 and :679.
- **What:** Seven sites rebuild the whole stage to change one or two fields. Main had four of these sites, with four fields. The branch added `x` and `more` to each and added three more sites.
- **Change:** Do this after E1, which re-reads the card in `run()`'s None arm and in `apply_action`. Also do it after D4 if D4 changes the cursor arithmetic (`next + 1`, `at.row_end as u8`).
  1. Add two private helpers on `CombatState`, `fn set_cursor(&mut self, next: u8, hit: u8)` and `fn set_pick(&mut self, pick: Option<Pick>)`. Each writes through `if let Stage::PlayingCard { .. } = &mut self.stage`, the way `ReplayCard` (:1077) and `grow_damage` already do. Outside a card they do nothing. None of the seven sites can be outside one: Choose and Done are legal only at a pick, and `run`'s sites sit inside its `PlayingCard` arm.
  2. Use them at the seven sites:
     - Choose binds only `more` (`let Stage::PlayingCard { more, .. } = self.stage else { unreachable!(..) }`) and ends with `self.set_pick(...)`.
     - Done needs no destructure: `self.set_pick(None)`.
     - In `run` the arm still binds every field: the None arm reads `card`, `target`, `x` and `more`.
     - The Pick arm becomes `self.set_cursor(next + 1, 0); self.set_pick(pick);`.
  3. Keep the two fresh constructions at :605 (a play) and :718 (a replayed copy).

  Nothing writes `self.stage` between each site's read and its rebuild: `condition_holds` and `pick_source` take `&self`, Choose moves only piles and the known top, and the `run` arms write the stage before `request_random_hit` / `do_effect`. So the stage ends up the same.
- **Worth it because:** A new `PlayingCard` field has to be threaded through 7 rebuilds, 2 constructions and 3 destructures. The compiler flags each literal, but a site filled with a default (say `x: 0`) would silently break something like a copy keeping its X. No runtime difference.
- **Check:** Engine check, including `cargo test --release -p sts-engine --test decisions --test amounts --test overrides --test known_top` (picks, Burst, X cost, Rampage, Headbutt) and the golden proving sets.

### K5. One per-card encoding cache, built by one function  (from review id c02; CONFIRMED)
- **Where:** `py/src/features.rs`:
  - :425-430, four parallel fields: `card_vecs`, `card_rows`, `card_held`, `card_kind_rows`;
  - :483-486, their init;
  - :499-511, `cache_cards` (official cards; `new` and `with_rates` call it);
  - :1396-1417, the pile closure, which builds the same four values per state for generated slots and variant ids, then falls back to the caches;
  - `card_dim` at :1232.
- **What:** Both places make the same four calls: `card_vec`, `card_hook_rows(..).concat()`, `card_held_rows` and `card_kind_rows` (the last three are empty in ids mode). Official cards pass `(c, c.def(), &Binding::default())`; the per-state path passes `(c, bd.def(c), bd)`.
- **Change:**
  1. Add `#[derive(Clone, Debug, Default)] struct CardCache { vec: Vec<f32>, rows: Vec<f32>, held: Vec<f32>, kind_rows: (Vec<f32>, Vec<u8>) }`. `Encoder` derives Clone and Debug, so the struct needs them.
  2. Add one `fn card_cache(&self, c: CardId, d: &CardDef, bd: &Binding, kinds: bool) -> CardCache`. In effects mode it fills `rows` and `held`, and fills `kind_rows` only when `kinds` is true. In ids mode all three stay empty.
  3. The encoder keeps one `cards: Vec<CardCache>` in place of the four fields.
  4. `cache_cards` maps `CardId::all()` through it with `kinds = true`, collects, then assigns `self.cards`. Official kind rows stay cached whatever `extra_rows` is, because `with_extra_rows` doesn't re-cache.
  5. The pile closure calls it for non-official ids: `let generated = (!c.is_official()).then(|| self.card_cache(c, bd.def(c), bd, self.extra_rows));`, then `let cc = generated.as_ref().unwrap_or(&self.cards[c.0 as usize]);`. Passing `kinds = self.extra_rows` is K16's first half. The later `if self.extra_rows && ...` test stays.
  6. `card_dim` reads `self.cards[0].vec.len()`.
- **Worth it because:** Each new per-card table means about six edits, split across two copies; the branch's fourth table touched seven places. The copies agree today. But no test catches drift in kind rows between the official path and the generated/variant path: `py/tests/test_content_pack.py` compares a generated Demon Form with the official one only with default Features. Grown Rampage copies take the per-state path, so official play depends on it too.
- **Check:** Features check. The `extra` and `rates` encoders over the pack and Rampage states cover kind rows on the per-state path and the `with_rates` re-cache.

### K6. Derive the opt-in kind list and the static condition names  (from review id c04; CONFIRMED)
- **Where:**
  - `py/src/features.rs:98`: `EXTRA_KINDS`, a hand copy of `ROW_KINDS[BASE_KINDS..]` (:80 and :96). It is used only at `py/src/lib.rs:448` and imported at lib.rs:36. It is not exported to Python.
  - `py/src/features.rs:297-299` (the static entries of `condition_names`) and :303-309 (`static_condition_name`).
- **What:** Two pairs of lists that must agree, and agree today. The encoder itself defines the opt-in kinds as those at index `BASE_KINDS` or later (`n_kinds` :603, `keeps` :986).
- **Change:**
  1. Make `BASE_KINDS` pub and delete `EXTRA_KINDS`. In lib.rs, import `BASE_KINDS` instead and test `ROW_KINDS[BASE_KINDS..].contains(&k.as_str())`. Fix the doc comment at features.rs:585, which names `EXTRA_KINDS`.
  2. In `condition_names`, build the static entries through the function: `v.extend(Tag::ALL.iter().map(|&t| static_condition_name(StaticCondition::CardInPlayTagged(t))))`, then `v.push(static_condition_name(StaticCondition::OwnerHpAtMostHalf))`. Same strings, same order.
- **Worth it because:** It closes two latent traps with five lines:
  - A kind appended to `ROW_KINDS` only would never be written for a layout that lists just that kind, and nothing would error (`set_layout` ignores names it doesn't know).
  - A change to the condition format would send Accuracy and Red Skull rows to `condition_unknown`, and no test reads those columns.
- **Check:** Features check. The vocabulary (`condition_names`, contract pins, `golden_rows.npz`) and the `layout` encoder's batch must be identical. `py/tests/test_sts.py` passes; its lines 386-387 and 420 test the switch.

### K7. `replaced()` walks the generated powers without a Vec  (from review id c21; CONFIRMED)
- **Where:** `engine/src/state.rs:1447-1448`, `let gen: Vec<Power> = self.generated_powers().collect();`. Also `generated_powers` at :1342-1344 and `generic_powers` at :1338-1340.
- **What:** The Vec exists only because `generated_powers` returns `impl Iterator + '_`, which keeps `self` borrowed while the loop calls `powers_mut`. `Binding::powers_in_play` (registry.rs:146) already returns `&'static [Power]`.
- **Change:** Do this after D5, which edits the same function.
  - `fn generated_powers(&self) -> &'static [Power] { &self.binding.powers_in_play()[crate::powers::NUM_OFFICIAL_POWERS..] }`.
  - In `replaced`: `for p in REPLACEMENT_POWERS.into_iter().chain(self.generated_powers().iter().copied())`.
  - `generic_powers` becomes `GENERIC_STATICS.into_iter().chain(self.generated_powers().iter().copied())`.

  The order and contents stay the same, because nothing in the loop changes the binding: the `then` effects touch only powers.
- **Worth it because:** Today there is one heap allocation and free per damage instance, HP loss and debuff application, in every combat with a bound generated power. Generated-power training and the generated-power bench run such combats. Official-only combats pay nothing. The change is three lines.
- **Check:** Engine check, including `cargo test --release -p sts-engine --test packs --test replacements`.

### K8. Merge codec stage tag 7 into tag 8  (from review id c11; CONFIRMED)
- **Where:**
  - `engine/src/codec.rs:161-185`, the encoder's `Stage::PlayingCard` arm. The tag choice is at :165: `w.byte(if full { 8 } else if x == 0 { 1 } else { 7 });`.
  - `engine/src/codec.rs:362-384`, the decoder's tag-8 arm (:362-377) and tag-7 arm (:378-384).
  - `engine/tests/amounts.rs:86`: `assert_eq!(codec::encode(&t).len() + 1, bytes.len());`.
  - docs/decisions.md:1760 and :1936, which describe the tags.
- **What:** Tag 7 (X > 0 and nothing else) writes card, target, next, hit and x. Tag 8 writes the same five fields, then replays, copy and pick. So tag 7's payload is a prefix of tag 8's, and each tag has its own canonicality rule. Both tags are new on this branch; main writes tags 0-6.
- **Change:** Do this after E5, which adds checks to the tag-8 decoder; keep those checks.
  1. Encoder: `let full = x != 0 || more != InPlay::default();`, then `w.byte(if full { 8 } else { 1 });`, then card, target, next and hit as now, then under `if full`: `w.byte(x)`, `more.replays`, `more.copy as u8` and the pick bytes (the code at :174-183, unchanged).
  2. Decoder: delete the tag-7 arm, so tag 7 falls to `_ => return None`. In the tag-8 arm, change the refusal to `if (x == 0 && more == InPlay::default()) || copy > 1 { return None; }`, so every state keeps exactly one encoding.
  3. Rewrite the encoder comment (:161-162): a card in play with X > 0, a pick, a replay or a copy takes tag 8 (every field); otherwise tag 1, as before.
  4. Change amounts.rs:86 to `+ 4` (x, replays, copy and the pick's 0 byte).
  5. Keep `CODEC_VERSION` at 1, although its doc says "Bumped on any change to the byte format". The only bytes that change were never written by a landed build. Say so in a line in decisions.md, next to the spec-6 tag-8 entry (:1936).
- **Worth it because:** It removes a third PlayingCard tag, and a 7-line decoder arm with its own canonicality rule, from the v1 format that solved-DB keys will use. The gain is small, and the chance lasts only until landing. Today no stored data can hold tag 7. Main has no X-cost card, and Whirlwind, the only X-cost card, is proving content. Whirlwind also never pauses mid-card: it has no pick, draw or random hit. So only hand-built states such as the amounts.rs test reach tag 7. Once engine-next lands, removing tag 7 would strictly need a `CODEC_VERSION` bump, which also means a new fingerprint. Do it before landing, or drop it.
- **Check:** `cargo test --release`.
  - `codec_golden` stays byte-identical (its states never reach tag 7), and round trips and fuzz pass.
  - amounts.rs passes with `+ 4`.
  - Golden games and H4 stay unchanged (neither uses the codec).
  - Only mid-card states with X > 0 and no pick, replay or copy change bytes: they get 3 bytes longer.

### K9. `grow_damage` as one straight sequence  (from review id c12; CONFIRMED)
- **Where:** `engine/src/state.rs:1114-1145` (`grow_damage`, one caller at :1074). It has two `hold_variant` calls (:1123, :1130), three temporary writes of the card in play (:1126, :1133, :1141), a nested match, and a final `drop_unused_variants` (:1144).
- **What:** About 30 lines doing what about 6 lines can.
- **Change:** Do this after E1, E2, E3 and D7, which touch variants and growth. Keep the code that computes `base`, `damage` and `idx`, including its early returns. Then:
  1. Set the card in play to `base`.
  2. Call `self.drop_unused_variants()`.
  3. `let id = self.hold_variant(idx).unwrap_or(card)`.
  4. Set the card in play to `id`.

  The final state is the same in every case. The slot table depends only on which variants are held: `hold_variant` inserts in `variant_key` order, the drop keeps that order, and `Top::map_cards` re-sorts floaters. The cases:
  - Free slots: the old variant is dropped if nothing else holds it, and `idx` is added.
  - Every slot full, and only this card holds its old variant: the drop frees it, and the hold succeeds.
  - Nothing droppable: nothing is renumbered, the hold fails, and `card` is still the right id. A hold that follows a drop which removed something can't fail.
  - `k = 0`: the same variant goes back into the same slot.
  - A leftover unheld variant (the E2 paths, if any remain): both versions drop it.
  - A generated base still returns early at `variant_index`, unless D7 changed that. If D7 lets generated cards grow, re-check this case against D7's code.
- **Worth it because:** It makes the most delicate variant code readable. The full-table branch came from a review fix and is the hard part to follow. No runtime difference: the common path still runs one drop. Small.
- **Check:** Engine check, including `cargo test --release -p sts-engine --test overrides` (`a_full_slot_table_still_grows_the_copy_that_frees_its_slot`, `variants_are_canonical`, `codec_round_trips_variants`, `slots_are_ordered_by_value`) and the golden `rampage` proving set.

### K10. One writer for a row's header  (from review id c01; CONFIRMED)
- **Where:** `py/src/features.rs:925-940` (`row_named`). The same 12-line header is copied at :1001-1010 (`pattern_rows`), :1020-1032 (`replacement_row`) and :1051-1064 (`static_row`). The header's width is in `row_dim` (:1245-1247) and its names are in `row_names` (:778-787).
- **What:** All four write the same header: a trigger one-hot (unknown last), a condition one-hot (unknown last), the param and a grant one-hot. Only the four inputs differ.
- **Change:** Add `fn row_head(&self, tn: &str, cn: &str, param: f32, grant: usize, out: &mut Vec<f32>)` holding the 12 lines, with `position(|x| x == tn)` and `position(|x| x == cn)`. The callers pass:
  - `row_named`: `(&trigger_name(trigger), cn, param, grant)`;
  - `pattern_rows`: `(PATTERN_TRIGGER, "Always", p as f32, OWN)`;
  - `replacement_row`: `(replace_trigger(r.event), "Always", 0.0, grant)`;
  - `static_row`: `(static_trigger(st.modifies), &static_condition_name(st.condition), 0.0, grant)`.

  The effect vector and the later `out[at + i] = x` writes stay in each caller. Optionally, write each one-hot straight into `out` (`out.resize(len + n + 1, 0.0)`, then set one index) instead of building a temporary Vec. The bytes are the same, with two fewer allocations per row.
- **Worth it because:** About 36 lines are duplicated, and a change to the header means editing four writers plus `row_dim` and `row_names`. Tests catch a width change in any copy: the opt-in row tests check every nonzero column by name, and `batch_dict` fails on a wrong width (lib.rs:472). So this is about maintenance, not silent misalignment. Small.
- **Check:** Features check.

### K11. One grant extraction for granted rows  (from review id c03; CONFIRMED)
- **Where:** `py/src/features.rs:1080-1084` (`granted_kind_rows`) and :1099-1103 (`granted_rows_if`): the same 5-line match.
- **What:** Both turn an `Apply` or `RandomApply` into (power, amount, grant) and skip every other effect. They differ only after that: `granted_rows_if` keeps powers with hooks and calls `power_rows`, while `granted_kind_rows` always calls `power_kind_rows`.
- **Change:** Move the match into a free function, `fn granted(e: &Effect) -> Option<(Power, i16, usize)>`, returning `None` for any other effect. Both callers loop over `effects.iter().filter_map(granted)` and keep their own filter. If A5 added a third grant path (threshold kind rows), use it there too. Leave `grant_rate_cols` (:556) and `effects()` (:898-912) alone: they treat applies differently on purpose.
- **Worth it because:** Small: five lines about 15 lines apart, and tests already check grants on both paths. Worth doing only together with K10.
- **Check:** Features check.

### K12. Skip the `OwnerPlaysCard` hook scan when nothing can fire  (from review id c17; PLAUSIBLE)
- **Where:** `engine/src/state.rs:647-650` (`owner_plays_card`), which runs on every play from :606. It walks every power in play (27 official at HEAD) with no guard. The guarded model is `attack` (:1430-1431, with `ATTACKED_POWERS`). The power lists live at `engine/src/hooks.rs:266-275`.
- **What:** Among official powers, only Burst has an `OwnerPlaysCard` hook. Yet every card play scans all powers for one.
- **Change:**
  1. In hooks.rs, next to `ATTACKED_POWERS`: `/// The official powers with an OwnerPlaysCard hook (a test checks the list), so a play skips the scan when the player holds none.` `pub const PLAYS_CARD_POWERS: [Power; 1] = [Power::Burst];`
  2. Add it to state.rs's `use crate::hooks::{...}` (:11-14). At the top of `owner_plays_card`: `if self.binding.is_empty() && !PLAYS_CARD_POWERS.iter().any(|&q| self.player.powers.get(q) > 0) { return false; }`. The binding clause is needed because packs can carry `OwnerPlaysCard` hooks (registry.rs:696). `Binding::is_empty` looks only at generated powers and cards, not variants, so official combats with a grown Rampage still skip. `run_hooks_with` skips powers with stacks ≤ 0, so `> 0` matches what could fire.
  3. In `engine/tests/replacements.rs`, add `PLAYS_CARD_POWERS` to the `use sts_engine::hooks::{...}` line. In `round_end_and_replacement_lists_match_the_tables`, add: `let plays: Vec<Power> = Power::ALL.into_iter().filter(|&p| hooks(p).iter().any(|h| h.trigger == Trigger::OwnerPlaysCard)).collect(); assert_eq!(plays, PLAYS_CARD_POWERS);`.
- **Worth it because:** Small and unmeasured. With two monsters, a card play runs about six 27-step hook scans; this removes one of them, perhaps 1-2% of the time spent playing a card. The rest of the extra scan cost (27 powers against main's 21) would need per-trigger lists, and the `fires` closures make those hard. To get a number, run `cargo run --release --example bench` before and after.
- **Check:** Engine check (H4 identical), including `cargo test --release -p sts-engine --test decisions --test replacements` (Burst, and the new list assertion), and the golden `survivor` proving set (Burst).

### K13. Search reuses a state's hash for its leaf and skips a dead clone  (from review id c19; PLAUSIBLE)
- **Where:** `engine/src/search.rs:227-276` (`expand`, which hashes `s` at :228) and :199-213 (`leaf`, which hashes it again at :203).
  - The cut path (:239) and the unlisted-event path (:257) call `leaf(s.clone())`, so the state is hashed twice.
  - The finished path (:233-234) clones `s` into `leaf`, which only returns `Node::Exact` and drops the clone.
- **Change:** Do this after D1, which changes the cut condition at :235.
  1. Split `leaf` in two:
     - `fn leaf_hashed(&mut self, s: CombatState, h: u64) -> usize` does the find-or-push part (:204-212).
     - `leaf(s)` keeps the `is_over` check, computes `state_hash(&s)`, then calls `leaf_hashed`.
     - `child` keeps calling `leaf` for EndTurn leaves (:223).
  2. In `expand`, the finished path becomes `self.push(Node::Exact(self.cfg.finished(&s)))`, with no clone.
  3. The cut and unlisted paths call `self.leaf_hashed(s.clone(), h)`, with the `h` from :228. That clone stays, because the leaf list and the memo each keep a copy.

  `s` can't be over at :239 or :257, because :233 already checked. Node and leaf order don't change.
- **Worth it because:** Small. It saves one ~240-step hash of a 1,268-byte state per cut or unlisted-event leaf (hundreds per capped search, against ~400k nodes), and one state copy (~50-70 ns) per distinct finished state. A few lines, no behaviour change.
- **Check:** Engine check. H4 staying byte-identical is the decisive part. Its two-turn searches (max_nodes 400,000) reach the cut path. Its one-turn searches use the default config (sample_k 0, limit 16, max_nodes 50,000), so they reach both the cut path and the unlisted-event path.

### K14. Cache `expr_value`'s column in the encoder  (from review id c23; PLAUSIBLE)
- **Where:** `py/src/features.rs:1236-1243` (`expr_value_col`), which searches `EFFECT_SCALARS` by name on every call. Its only caller is :1421, once per card entry per state.
- **Change:**
  1. Add a field `expr_value_col: Option<usize>` and set it in `Encoder::new`: `(repr == CardRepr::Effects).then(|| scalar_dim[scalar_index("expr_value")].map(|i| CARD_PROPS.len() + i)).flatten()`. Nothing changes `repr` or `scalar_dim` after `new`: `with_rates` and `set_layout` leave them alone, and the rate columns come after the effect block, so they don't move the column.
  2. Read the field at :1421 and delete the function.
  3. Optional: skip the `expr_value` scan for official cards that have no `ScaledDamage` effect (`expr_value` sums only those, so the value is 0 and nothing is written). Use a per-official-card flag filled in `cache_cards` (a field on K5's `CardCache`). Generated slots and variant ids must keep scanning, because their definition comes from the state's binding.
- **Worth it because:** Small. Each card entry pays about 29 length compares and 3 short string compares, perhaps 0.5 µs per state, a few percent of encode time at most. H3 measured self-play speed as level with before the series. The spec-2 review already listed this as optional (decisions.md:1796-1797).
- **Check:** Features check. The script's decks include Body Slam, Heavy Blade and Whirlwind, so `expr_value` is non-zero there.

### K15. One count list for known-top draws  (from review id c08; PLAUSIBLE)
- **Where:** `engine/src/chance.rs:169-179` (`top_draw_choices`, the odds as floats) and :331-343 (the known-top sampler in `resolve_chance`, the same odds as integer counts).
- **What:** The odds of the next card while the top is known are written twice. Each floater kind with nothing above it has odds count/N, and the known head gets the rest.
- **Change:** Do this after B3, which changes how floaters are stored. Build on whatever `floaters_on_top()` returns after B3.
  1. Add `fn top_draw_counts(&self) -> Vec<(usize, Option<CardId>)>`: each `floaters_on_top()` kind with its count, then `(draw.len() - f, None)`, where f is the floaters' total.
  2. `top_draw_choices` maps it to `(k as f64 / n, c)`, which gives the same floats.
  3. The sampler keeps its single `rng.below(draw.len())` call and walks the running total (`r < at`). The `None` entry ends at `draw.len()`, so it covers every `r >= f`.

  The RNG use and the results stay the same. Skip the review's second idea, which was to share the find-and-add of the `push` closure in `top_draw_states` (:199-209) with the merge loop in `chance_outcomes` (:314-320). `push` also enforces `limit`, and it would save only about 6 lines.
- **Worth it because:** Small. Only Headbutt (proving content) makes a known top, so a drift would make search's listed odds differ from self-play's sampled odds only there. `known_top.rs` pins the listed odds exactly, but the sampled odds only statistically, for one setup.
- **Check:** Engine check, including `cargo test --release -p sts-engine --test known_top` (`floater_odds_match_the_game`, `sampled_draws_follow_the_same_odds`). H4 doesn't reach a known top; the golden `headbutt` proving games show the RNG stream is unchanged.

### K16. Don't build kind rows that get dropped; count hook rows without a Vec  (from review id c24; PLAUSIBLE)
- **Where:**
  - `py/src/features.rs:1406`: the per-state path builds `card_kind_rows(d, bd)` for every generated or variant card entry, but reads it only under `if self.extra_rows` (:1439-1442).
  - `power_rows` at :946-957: it collects `hs: Vec<_>` at :948 only to loop over it and count it.
- **Change:** Build the kind rows only when `self.extra_rows` is on; this comes free with K5's `kinds` argument. In `power_rows`, loop over `bd.hooks(p).iter().filter(|h| h.trigger != Trigger::RoundEnd)` directly and count with a local `n`.
- **Worth it because:** Small, under 1 µs per state. Under the default layout, a generated card whose applied power has countdown, static or replacement rows builds and drops a few small allocations per row per state. Rampage variants apply no power and cost nothing. `hs` costs one small allocation per held hook power per entity per state.
- **Check:** Features check.

### K17. Check a monster's single move without cloning the cached distribution  (from review id c18; PLAUSIBLE)
- **Where:** `engine/src/chance.rs:93-109` (`move_distribution`, which clones the cached Vec on every hit, :102) and :111-118 (`request_monster_move`, which only checks whether there is one move).
- **Change:** Do this after G3, which changes how this cache is tested. If G3 added an uncached path (for example a function the test calls), keep it.
  1. Move the `thread_local!` CACHE out of `move_distribution` into a new private `fn with_moves<R>(&self, slot: usize, f: impl FnOnce(&[(MoveId, f64)]) -> R) -> R`:
     - Build the key as now: `(m.kind, slot as u8, m.moves)`.
     - If `!CACHE.with(|c| c.borrow().contains_key(&key))`, compute `enumerate(|c| ai(self, slot, c))` outside any borrow of the cache, then insert it with `borrow_mut`.
     - Return `CACHE.with(|c| f(&c.borrow()[&key]))`.
  2. `move_distribution` becomes `self.with_moves(slot, |d| d.to_vec())`, so the public API stays the same.
  3. `request_monster_move` uses `let one = self.with_moves(slot, |d| match d { [(m, _)] => Some(*m), _ => None });`, then sets the move or the pending event as now.

  `f` must not call back into the engine while the cache's `RefCell` is borrowed. So `chance_outcomes`, which runs states inside its loop, keeps the cloning call. Don't use `Box::leak`: the cache is per thread and worker threads are spawned per call, so it would leak per thread. Don't return `Rc` either: tests sort the result (monsters.rs:103, monsters_act1.rs:27), and agent.rs:140 stores it.
- **Worth it because:** Small: one 16-48-byte allocation and free per living monster per round, on a path that also clones states per outcome. The cache itself was already a gain over main (random combats +10%).
- **Check:** Engine check, including `cargo test --release -p sts-engine --test monsters --test patterns --test chance --test lookahead`.

### K18. One list of where card ids live  (from review id c15; PLAUSIBLE)
- **Where:**
  - `engine/src/state.rs:1174-1175`: the held check in `drop_unused_variants` (the card in play and four piles).
  - `engine/src/state.rs:1193` and :1199-1203: `renumber_variant` (four piles, the known top, the card in play).
  - `engine/src/codec.rs:459-467`: the decoder checks that every pile card and the card in play are bound, and that the top is within the draw pile.
  - Two more four-pile lists, at `engine/src/bound.rs:71-75` (`can_heal`) and `engine/src/solve.rs:276` (`representable`).
- **What:** The places that hold card ids are listed by hand in several spots. The lists agree today.
- **Change:** Add three methods on `CombatState` and use them at these sites:
  - `pub fn piles(&self) -> [&Pile; 4]` (hand, draw, discard, exhaust);
  - a private `fn piles_mut(&mut self) -> [&mut Pile; 4]`;
  - `pub fn card_in_play(&self) -> Option<CardId>`.

  Piles are count arrays, so each site keeps its own operation: a count lookup, moving a count between slots, or the all-bound check.
  - Leave Inferno's loop in `after_move` (:1584) alone. It covers hand, draw and discard on purpose (review c09).
  - Not part of this item: dropping unheld variants when a pack-grown Power card leaves play, or when the combat ends during a copy. That is E2, and it changes behaviour. If E2 added a drop somewhere, its held check can use the same helpers.
- **Worth it because:** Small. It guards against a future place that holds card ids (a new pile) being missed in one list. If that happened, the decoder and the variant drop would disagree silently.
- **Check:** Engine check, which covers the overrides, codec, solve and bound tests.

### K19. `GenPower` keeps its `PowerSpec` instead of a copy of its fields  (from review id c14; PLAUSIBLE)
- **Where:** `engine/src/registry.rs:222-228`: `GenPower` holds an id, then hooks, debuff, statics and replacements, repeating `PowerSpec` (:231-237). `load_pack` builds it field by field with four leaks (one `Box::leak`, three `leak`, :333-339). The `Binding` accessors read it (:168-219: `hooks`, `statics`, `replacements`, `is_debuff`, `power_id`, `generated`).
- **Change:** Do this after D4 and D6, which both change `load_pack`.
  1. `struct GenPower { id: &'static str, spec: PowerSpec }`, built as `GenPower { id: Box::leak(id.clone().into_boxed_str()), spec: spec.clone() }`.
  2. The accessors return `&g.spec.hooks` (and statics, replacements) and `g.spec.debuff`. `POWERS` is a static `OnceLock` array and `generated()` returns `&'static GenPower`, so `&g.spec.hooks` coerces to `&'static [Hook]`.
  3. Optionally, `Table.powers` can then keep only the index and compare a reload against `POWERS[i].get().unwrap().spec`.

  Leave `CardSpec` as it is. Folding the card flags into one shared struct would make the `CardDef` literal in `bind` (:422-440) non-exhaustive. A new `CardDef` field would then quietly take a default instead of failing to compile, and the fold also needs new derives on `CardDef` and `Row`. If you want a cheap guard on the card side (an addition here, not part of the review): destructure `CardDef` exhaustively in `same_card` (engine/tests/packs.rs:10), with `name: _, class: _, held_out: _, proving: _` (bind sets those itself) and every other field compared. Then a new flag is a compile error in the round-trip test until the test compares it.
- **Worth it because:** Small. Today a new pack power atom means editing `PowerSpec`, `GenPower`, `load_pack` and an accessor; afterwards, only `PowerSpec` and the accessor. registry.rs is not a rule file at HEAD. If E4 added it to the fingerprint files, this edit changes the fingerprint too.
- **Check:**
  - `cargo test --release -p sts-engine --test packs --test registry` (`every_official_power_round_trips`, `redefining_an_id_is_an_error`), then `cargo test --release`.
  - Rebuild the module (`bash scripts/dev_sts.sh`), then with it `py/tests/test_content_pack.py`, `scripts/tests/test_gen_content.py` and `scripts/tests/test_content_selfplay.py` pass. (`scripts/tests/test_registry.py` tests the learned-play run registry, not content packs, so it doesn't check this.)
  - Golden games stay unchanged.

### K20. Search memo Vecs grow by doubling: leave as is unless measured  (from review id c22; PLAUSIBLE)
- **Where:** `engine/src/search.rs:169-174` (`Memo.states`) and :189 (`Tree.leaves`), pushed at :207 and :272. `eval.evaluate(&tree.leaves)` at :304 takes one slice.
- **What:** Each search starts these Vecs empty and grows them by doubling. At the largest growth, the old and new buffers briefly coexist, and the states are copied once more.
- **Change:** None now. The two alternatives don't fit:
  - `Vec::with_capacity(max_nodes)` would commit max_nodes × 1,268 B (~507 MB at 400k nodes) per memo table per search. That is worse on a memory-bound machine.
  - Fixed-size chunks would suit `memo.states`, since only `Index::find` reads it, by index. They would not suit `leaves`, which the evaluator takes as one slice.

  Revisit only if a profile of a large two-turn search shows reallocation copies in `Tree::expand`.
- **Worth it because:** It isn't worth it today. Geometric growth costs at most one extra copy per stored state, and it already beats main's HashMap, which re-hashed and moved every 1,268-byte key on each growth.
- **Check:** If it is ever changed: H4 byte-identical, and `cargo run --release --example search_speed` faster.

### Checked and rejected (refuted by the verifier; don't redo)
- **c05** (`next_draw_size` re-computes `HookRates::draw`): not a pure cleanup. `hook_rates().draw` also counts `OwnerTurnEnd` Draw hooks, which packs can carry, while `next_draw_size` counts turn-start draws only (decisions.md:2010-2013). Reusing it would change the column and the next_draw / known_later split, and tie a contract feature to the heuristic. One unverified aside from the same record, for whoever fixes A2: at turn 0, `next_draw_size` doesn't subtract innate cards, though the opening draw does (state.rs:754-762).
- **c09** (`renumber_variant` repeats the Inferno card rewrite): the shared part is already one helper (`Top::map_cards`). The 3-line loops that remain run over different piles on purpose (every place that holds a variant, versus Inferno's hand, draw and discard), so a helper would remove no decision.
- **c10** (`MonsterDef.ai` is always `pattern_ai`): decisions.md:1716-1718 already considered and rejected narrowing the AI call to the move history, because future AIs need more state, such as ally counts. Dropping only the field saves one fn pointer per monster kind.
- **c20** (`Top` hashed field by field even when empty): it saves about 21 of ~240 hash steps per state. A bigger cut of the same kind (hashing only non-empty piles and non-zero powers) measured no gain and was reverted (decisions.md:2026-2028, 2137).
- **c25** (the solved-DB `fetch` / `positions` decode whole states with the GIL held): the decode is the deliberate fix that names variant cards (decisions.md:2225-2227). It costs under 1 µs per row, every caller is single-threaded, and callers then spend far more time per row.

## Build step details

Commit each step alone, once its checks pass. Run every command from the worktree root. Steps 1, 2, 3 and 5 edit code in rule files (state.rs, hooks.rs, chance.rs), so do them before engine-next lands; the solved DB is then retired only once. Step 4 is valid only before landing. Every step comes after all of groups A-G; the "Do after" lists name the fixes that touch the same code.

- K-step 1: damage pipeline (K1 c16, K3 c06, K7 c21).
  - Files: engine/src/state.rs (replaced, take_damage, lose_hp, apply_power, the two interpreters and the new private interpret, generated_powers / generic_powers), engine/src/hooks.rs (StaticStage::live). Leave py/src/features.rs:1069 for K-step 6, so this step needs no module rebuild.
  - Do after: C5, D5, G1.
  - Acceptance:
    1. Before editing: cargo run --release --example two_turn_phases 100 --check target/h4_before.txt
    2. After: cargo test --release. Expect "test result: ok" for every binary, 0 failed.
    3. cargo run --release --example two_turn_phases 100 --check target/h4_after.txt && cmp target/h4_before.txt target/h4_after.txt. Expect no output, exit 0.
    4. git status --short engine/tests/data. Expect empty.
- K-step 2: hook lists (K2 c07, K12 c17).
  - Files: engine/src/hooks.rs (the guarded COUNTDOWN arm, PLAYS_CARD_POWERS), engine/src/state.rs (the hooks import, the owner_plays_card guard), engine/tests/replacements.rs (import plus the new list assertion).
  - Do after: G2, which edits the same test function.
  - Acceptance: the engine check from step 1 (tests ok, H4 cmp silent, engine/tests/data unchanged). Also cargo test --release -p sts-engine --test replacements --test statics --test decisions, expecting ok, including the PLAYS_CARD_POWERS assertion.
- K-step 3: card in play and variants (K4 c13, K9 c12, K18 c15).
  - Files: engine/src/state.rs (apply_action, run, grow_damage, drop_unused_variants, renumber_variant, the new set_cursor / set_pick / piles / piles_mut / card_in_play), engine/src/codec.rs (the decoder's held check), engine/src/bound.rs (can_heal), engine/src/solve.rs (representable).
  - Do after: E1, E2, E3, D4, D7.
  - Acceptance: the engine check from step 1. Also cargo test --release -p sts-engine --test overrides --test decisions --test amounts --test known_top --test codec --test solve, expecting ok.
- K-step 4: codec tag merge (K8 c11).
  - Files: engine/src/codec.rs (encoder arm, decoder arms, comment), engine/tests/amounts.rs (line 86: + 1 becomes + 4), docs/decisions.md (one line next to the spec-6 tag-8 entry at :1936, saying tag 7 was merged before landing and why CODEC_VERSION stays 1).
  - Do after: E5. Only before engine-next lands; otherwise skip it.
  - Acceptance: cargo test --release, expecting all ok, with x_survives_codec_round_trip passing at + 4. git status --short engine/tests/data, expecting empty (codec_golden.txt untouched). H4 cmp, expecting no output.
- K-step 5: chance and search (K13 c19, K15 c08, K17 c18).
  - Files: engine/src/search.rs (leaf / leaf_hashed, expand), engine/src/chance.rs (top_draw_counts, top_draw_choices, the resolve_chance sampler, with_moves, move_distribution, request_monster_move).
  - Do after: B3, D1, G3.
  - Acceptance: the engine check from step 1. Also cargo test --release -p sts-engine --test known_top --test chance --test monsters --test patterns --test lookahead, expecting ok. H4 cmp target/h4_before.txt target/h4_after.txt must give no output; it is the decisive check for K13 (its two-turn searches reach the cut path; its one-turn searches, sample_k 0, reach the cut and unlisted-event paths).
- K-step 6: features encoder (K5 c02, K6 c04, K10 c01, K11 c03, K14 c23, K16 c24, and K3's features.rs:1069 call if K-step 1 added StaticStage::live).
  - Files: py/src/features.rs, py/src/lib.rs.
  - Do after: every A-G fix that edits py/src (A2, A5 and D3; A3 and D5 if their fixes touch features.rs).
  - Acceptance (PY=../../../.venv/Scripts/python.exe; no Python process may hold target/pyroot's .pyd):
    1. Before editing: write target/features_hashes.py from the Features check section. Then bash scripts/dev_sts.sh && rm -rf target/pyroot_before && cp -r target/pyroot target/pyroot_before
    2. PYTHONPATH="$PWD/target/pyroot_before" $PY target/features_hashes.py target/fh_before.json
    3. PYTHONPATH="$PWD/target/pyroot_before" $PY scripts/series_check.py dump target/sc_before.npz (no net paths: the tiny contract nets are pre-contract and stsnet.load refuses them; test_contract.py covers them).
    4. After editing: bash scripts/dev_sts.sh, then repeat 2 and 3 with target/pyroot, writing target/fh_after.json and target/sc_after.npz.
    5. cmp target/fh_before.json target/fh_after.json. Expect no output.
    6. $PY scripts/series_check.py compare target/sc_before.npz target/sc_after.npz. Expect a last line starting with "PASS:".
    7. With PYTHONPATH="$PWD/target/pyroot", these must all pass: py/tests/test_sts.py, py/tests/test_content_pack.py, scripts/tests/test_contract.py, scripts/tests/test_net.py, scripts/tests/test_content_selfplay.py, scripts/tests/test_threshold_rows.py, scripts/tests/test_granting.py, scripts/tests/test_lookahead.py, scripts/tests/test_rates.py, scripts/tests/test_curriculum.py (slowest and most memory-hungry; run it when no heavy job runs).
    8. git status --short py/tests/data scripts/tests/data. Expect empty.
- K-step 7: registry (K19 c14).
  - Files: engine/src/registry.rs (GenPower, load_pack, the Binding accessors), and optionally engine/tests/packs.rs (same_card, an exhaustive CardDef destructure).
  - Do after: D4, D6, E4.
  - Acceptance:
    - cargo test --release -p sts-engine --test packs --test registry, expecting ok, then cargo test --release, expecting all ok, and git status --short engine/tests/data empty.
    - Then bash scripts/dev_sts.sh and, with PYTHONPATH="$PWD/target/pyroot", ../../../.venv/Scripts/python.exe on py/tests/test_content_pack.py, scripts/tests/test_gen_content.py and scripts/tests/test_content_selfplay.py, expecting all passed.
- K20 (c22): no step. Revisit only if a profile of a large two-turn search shows reallocation copies in Tree::expand. The acceptance would then be: H4 cmp silent, and cargo run --release --example search_speed faster.

## Pins for this group

Expected to change:
- K8 (c11) only: engine/tests/amounts.rs x_survives_codec_round_trip asserts `+ 4` instead of `+ 1`. An X-only mid-card state now takes tag 8 and writes x, replays, copy and a pick byte of 0.
- K8 also changes the v1 bytes of mid-card states with X > 0 and no pick, replay or copy: they become 3 bytes longer. No stored data holds them. Main never wrote tag 7. codec_golden never reaches it. Official content reaches it only in hand-built states, because Whirlwind never pauses mid-card. engine/tests/data/codec_golden.txt stays byte-identical. CODEC_VERSION stays 1.
- The rules fingerprint is computed, not pinned by value. It changes for every item that edits code in a rule file: K1, K2, K3, K4, K7, K9, K12, K15, K17 and K18. Comment-only edits don't count, because the hash strips comments and whitespace. K8 doesn't change it: codec.rs isn't hashed and CODEC_VERSION stays 1. K13, the py/src items and K20 don't change it either. K19 changes it only if E4 added registry.rs to RULE_FILES. Before landing this costs nothing; after landing each such edit retires the solved DB.

Must stay byte-identical for every K item:
- engine/tests/data/golden.txt (9,000 official games) and engine/tests/data/golden_proving.txt (the seven proving sets), both via golden_trajectories;
- engine/tests/data/codec_golden.txt (codec_golden);
- solvedb content_tables_pinned;
- py/tests/data/golden_rows.npz;
- scripts/tests/data/contract/pins.json, outputs.npz and old_layout.json;
- scripts/tests/data/lookahead_off_names.json and lookahead_rows.npz;
- TRAIN_PIN (test_net.py) and ARRAYS_PIN (test_content_selfplay.py);
- scripts/tests/data/curriculum_pins.json;
- the H4 check file (two_turn_phases 100 --check);
- series_check compare PASS;
- the features before/after hash dump (target/features_hashes.py).

## Decisions for this group

None. Every item is behaviour-neutral except K8, and K8 is cheap while engine-next is unlanded. When to do K8 (before landing, or never) is the manager's call at landing time, not the owner's. Recommendation: do it in the same session that lands the branch, or drop it.

## Notes the checker left

- The target/features_hashes.py script was checked against the Python API (lib.rs), the pack parser (registry.rs) and the helper modules (selfplay.load_content, contract_pins.fixed_states / batch_hashes) at HEAD. It was not run, because this task was read-only.
- It loads data/bench/gen_powers_pack.json. That pack carries keys the parser ignores today (budget, seed, gain, split, power, value_per_energy, keys, lifetime). If the D4 fix makes the loader refuse unknown keys, D4 must keep this pack loading, since training configs use it. That is D4's job, but the sketch depends on it.
- Several K items depend on how A-G fixes turn out, and each says how to adapt: K1/K7 on D5's arithmetic in replaced, K3 on C5's static_holds signature, K9 on D7, K15 on B3's floater storage, K17 on G3's test path, K8 on E5's decoder checks. Nothing here blocks a builder.
