# Series review fixes, group F: Python tooling

Status: idea (2026-11-02, F1-F4 are in the backlog (part 3), not scheduled; decisions 'Series review fixes: the cut').

Part of `docs/specs/series-review-fixes.md`. Read that file first: it has the why, what must
stay true, the decisions, the build order and how to build and check. This file holds the
group's entries, then its build step details, the pins it may change, its decisions and the
notes its checker left. Line numbers are at `d9327a2`.

## Findings

### F1. Replaying a record whose option values name a grown Rampage crashes

- **Severity:** medium · **Reach:** tooling · **New on this branch:** yes · **Review:** v05, reported #9; verifier CONFIRMED (ran a throwaway engine test)
- **Where:** `scripts/registry.py:282-284` in `replay` and `scripts/registry.py:288-296` in `_decode_values`; `scripts/action_text.py:109-125` in `decode_action` (the pick at 119-120, the stale message at 124; `NotSupported`'s docstring at 29-30, the module docstring's override bullet at 11-13). The same binding-blind replay of stored text: `scripts/bench_decisions.py:122` in `replay`, `scripts/bench_probes.py:83` in `build`, `scripts/analysis/pattern_value_error.py:123` in `sample_games`. Callers that abort: `scripts/registry.py:347` in `examples` (the training cache build) and `scripts/puzzles.py:144` in `record_states`. Writer side (correct): `py/src/lib.rs:1444-1458` in `result_dict`.

**What goes wrong.** A game record (one line of a dataset's `games.jsonl.gz`, written by `registry.records`) stores each decision's action as text. When the game was played with `values=True` (`registry.play` always passes it), the record also stores each decision's option values: the search's root options, each a list of equivalent legal actions with its score. On this branch a played Rampage becomes a variant: a per-copy card named by its overrides, `Rampage{damage=13/combat}`, which only its own combat holds, in a slot of its binding (the per-combat table that maps the reserved card ids to generated cards and variants). `result_dict` names value actions through each decision's own state (`let b = r.trajectory.get(i).map_or(&spec.binding, |(s, _)| &s.binding);`, lib.rs:1453), so records contain `Rampage{damage=13/combat}@0` (play the grown copy) and `Choose:Rampage{damage=13/combat}` (a Headbutt or Hologram pick that offers it).

`replay` decodes the recorded actions with `action_text.decode_in(c, s)` (registry.py:273). `decode_in` finds text that only a combat can name (a `gen:` card or a variant) among that combat's legal actions. But `replay` decodes the values with the binding-blind `decode_action` unless the deck holds a `gen:` card: `gen = any(c.startswith(action_text.GEN) for c in game["deck"])` (283), then `return [([decode_action(a) for a in acts], v) for acts, v in options]` (294). For a play text, `decode_action` raises `NotSupported(f"{text!r}: per-copy overrides are not supported until spec 8")` (action_text.py:124). That message is stale: spec 8 is built. For a pick text it calls `sts.Action.choose(p["candidate"])` (line 120), which raises `ValueError: unknown card "Rampage{damage=13/combat}"`, because `CardId::from_name` (cards.rs:615) knows only official names. Nothing catches either error. So `registry.examples` aborts the whole cache build, and `puzzles.record_states` fails on the game. `bench_decisions.replay` and `bench_probes.build` also step stored prefixes through `decode_action`. No bench set holds Rampage today, so those two are latent.

Reach: Rampage and Headbutt are proving cards (cards.rs:544-547), and `class_cards` (cards.rs:645-646) keeps them out of every training and bench pool, so the standard pipeline doesn't meet this. Any deck that names them does, because `sts.Combat`, `sts.run` and `registry.selfplay` accept any official card. Content packs can't trigger it: only an official card can grow (`variant_index` returns None for a generated base, registry.rs:52-54). `finetune.py:178` and `curve.py:93` replay games recorded without values (`finetune.games` calls `sts.run` without `values=True`), so they are not affected. `registry.py` is unchanged from main; main had no variants, so override text could not appear in a real record there.

**Reproduce.** This sequence is deterministic and becomes the test. Use deck `["Rampage"] + ["Headbutt"] * 4`, encounter `jaw_worm`, seed 1. The deck has five cards, so the opening hand is the whole deck whatever the seed. Step these actions, taking each from `c.legal_actions()` by its `action_text.encode_action` text:
1. `Rampage@0` (8 damage; the played copy becomes `Rampage{damage=13/combat}` in the discard pile)
2. `Headbutt@0` (9 damage, then a pick from the discard pile; Headbutt is still in play, so the grown copy is the only candidate)
3. `Choose:Rampage{damage=13/combat}` (the pick puts it on top of the draw pile)
4. `End` (Jaw Worm always opens with Chomp, 11 damage)
5. `Rampage{damage=13/combat}@0` (turn 2 draws the known top first)

The legal actions at each decision are:
- decision 0: `Headbutt@0`, `Rampage@0`, `End`
- decision 1: `Headbutt@0`, `End`
- decision 2: only the pick
- decision 3: `Headbutt@0`, `End`
- decision 4: `Headbutt@0`, `Rampage{damage=13/combat}@0`, `End`

Before each step, record one option per legal action with value 0.0: `vals.append([([a], 0.0) for a in legal])`. Make the record with `registry.records([("jaw_worm", deck, 1)], [0], [res])`, where `res = {"actions": acts, "values": vals, "won": c.won(), "hp_start": 80, "hp_end": c.player_hp(), "turns": c.turn(), "score": c.score()}`. `records` needs exactly these keys.
- Expected: `registry.replay(rec)["values"]` equals `vals`.
- Actual: `ValueError: unknown card "Rampage{damage=13/combat}"` at decision 2 (the pick). If decoding got past it, the play value at decision 4 would raise `NotSupported(... until spec 8)`.
- `bench_decisions.replay({"deck": deck, "encounter": "jaw_worm", "seed": 1, "actions": "|".join(texts)})` and `bench_probes.build(bench_probes.probe("variant", "", deck, "jaw_worm", "End", "End", prefix=texts))` raise the same ValueError at the pick.

Through the real tools: `specs = [("cultist", selfplay.STARTER + ["Rampage"] * 3, 0)]`, then `res = sts.run("search", specs, record=True, values=True)`. The verifier's engine replay of this spec (default search settings, as `sts.run` uses) found 3 decisions whose options offer the grown copy as a play. `registry.replay(registry.records(specs, [0], res)[0])` then raises NotSupported.

**Fix.** Decode every stored text through `decode_in`, with the combat at that point, the same way recorded actions already are.
1. `registry.replay`: delete the `gen = ...` line (283) and always pass the state: `out["values"] = [_decode_values(d, st) for d, st in zip(game["values"], states)]`.
2. `_decode_values(options, state)`, with `state` now required:
   ```python
   def _decode_values(options, state):
       """One decision's recorded option values with their actions decoded in
       `state`, that decision's combat: generated cards and variants (a grown
       Rampage) are named only within their combat (`action_text.decode_in`)."""
       return [([action_text.decode_in(state, a) for a in acts], v) for acts, v in options]
   ```
   This drops the `state.options(sp.LIMIT)` table. Every value action is legal at its decision. An option lists every legal action that leads to the same afterstate (`OptionScore`, engine/src/search.rs:94-96), built from `legal_actions()` (engine/src/options.rs:53-73), so `decode_in` finds it. Official text falls through `decode_in` to `decode_action` (one extra parse), so official records give the same objects as today. Generated decks no longer call `options()`, which applied every action and resolved its chance events. `decode_in` returns the same `sts.Action` objects as the old table did: both come from the state's legal actions, named through its binding. So `_sample_afterstates`' check that the value actions equal `s.options(LIMIT)`'s (selfplay.py:390) still holds, and cache arrays don't change.
3. `bench_decisions.replay` (line 122): `c.step(action_text.decode_in(c, a))`; `action_text` is already imported (line 28). `bench_probes.build` (line 83): the same change, plus `import action_text` with the other imports (lines 26-28). `analysis/pattern_value_error.py:123`: `c.step(action_text.decode_in(c, a))`; `action_text` is imported locally at line 103.
4. `action_text.decode_action`: raise `NotSupported` for both variant forms, with a message that points at `decode_in`. NotSupported subclasses ValueError, so existing `except ValueError` callers still catch it.
   - Between line 118 and line 119 (`if kind == "choose":`), add `if kind == "choose" and "{" in p["candidate"]: raise NotSupported(f"{text!r}: a variant is named only within its combat; decode it with decode_in(combat, text)")`.
   - Replace line 124's message with `f"{text!r}: a card with per-copy overrides (a variant) is named only within its combat; decode it with decode_in(combat, text)"`.
   - `NotSupported`'s docstring (line 30): "A reserved action form replayed before its spec is built, or a variant decoded without its combat (`decode_in` takes those)."
   - Module docstring (lines 11-13): add that a pick of a variant (`Choose:Card{...}`) replays the same way.

Keep the aliases `registry.decode_action` and `bench_decisions.decode_action`: test_contract.py:511-512 checks that the aliases are the `action_text` functions.

Rejected alternative: take the state path only when a value text contains `{`. That keeps two decoders and the costly `options()` call.

Don't rename or drop variant text when writing records: the text form is the documented contract (decisions.md:2106-2108, "replayed by `decode_in` among the legal actions (picks of a variant too)"). Don't make `decode_action` guess a variant's card id either: the id depends on which variants that state holds.

**Test first.** Add `scripts/tests/test_contract.py::test_variant_records_replay` after `test_records_roundtrip`. It fails today with the ValueError from `registry.replay`:
```python
def test_variant_records_replay():
    """A record whose actions and option values name a grown Rampage (a
    variant only its combat holds) replays through registry.replay,
    bench_decisions.replay and bench_probes.build."""
    import action_text as at
    import bench_probes
    import registry
    deck = ["Rampage"] + ["Headbutt"] * 4  # five cards: the whole deck is the opening hand
    texts = ["Rampage@0", "Headbutt@0", "Choose:Rampage{damage=13/combat}", "End", "Rampage{damage=13/combat}@0"]
    c = sts.Combat(deck, "jaw_worm", seed=1)
    acts, vals = [], []
    for t in texts:
        legal = c.legal_actions()
        assert t in [at.encode_action(a) for a in legal], (t, legal)
        vals.append([([a], 0.0) for a in legal])  # one option per legal action
        acts.append(next(a for a in legal if at.encode_action(a) == t))
        c.step(acts[-1])
    res = {"actions": acts, "values": vals, "won": c.won(), "hp_start": 80, "hp_end": c.player_hp(),
           "turns": c.turn(), "score": c.score()}
    rec, = registry.records([("jaw_worm", deck, 1)], [0], [res])
    rp = registry.replay(rec)
    assert rp["actions"] == acts
    assert [[(list(x), v) for x, v in d] for d in rp["values"]] == [[(list(x), v) for x, v in d] for d in vals]
    d = {"deck": deck, "encounter": "jaw_worm", "seed": 1, "actions": "|".join(texts)}
    assert bench_decisions.replay(d).encode() == c.encode()
    p = bench_probes.probe("variant", "a grown copy", deck, "jaw_worm", "End", "End", prefix=texts)
    assert bench_probes.build(p).encode() == c.encode()
```
`c.encode()` works here: `Binding::is_empty` (registry.rs:139-141) looks only at generated slots, and the codec writes variants by value. In `test_records_roundtrip`, change line 504's list to `[("Choose:#0", "inline options"), ("Potion:1@0", "no spec"), ("Strike{cost=0/turn}@0", "decode_in"), ("Choose:Rampage{damage=13/combat}", "decode_in")]`. Today the new pick case raises a plain ValueError, not NotSupported, and the override case says "spec 8".

**Must stay unchanged.** Only Python scripts change. golden.txt's 9,000 games, codec_golden.txt, series_check, the contract pins, H4 and the rules fingerprint are untouched. These must keep passing unchanged:
- `scripts/tests/test_registry.py` (live and cached arrays equal)
- `scripts/tests/test_content_selfplay.py`: GAMES_PIN, ARRAYS_PIN, and `test_dataset_with_content_records_hash_and_replays`, the generated-deck cache build that used the `options()` table
- `test_contract.py::test_fixed_silent_set` and the rest of `test_records_roundtrip`
- `scripts/tests/test_bench.py`: `test_replay_reproduces_decision_states`, `test_probe_reference_orders_match_expected`, `test_bench_unchanged` (byte-identical quick bench)
- `scripts/tests/test_branches.py`, `scripts/tests/test_puzzles.py`, and the digests in `test_curriculum.py`
- every other suite that replays official records (`test_hp_loss`, `test_setups`, `test_survival_score`, `test_ranking`, `test_rounds`), since official text decodes to the same objects

No data file is rewritten (data/bench/decisions.json, reference.json, fixed_silent.json, datasets, caches). The only expectation that changes is line 504's message substring, plus its new case.

### F2. `sts.run(forced=...)` matches a forced generated card by its raw slot id, not its name

- **Severity:** low · **Reach:** content packs · **New on this branch:** no (already on main) · **Review:** v07, cut by the 15 cap; verifier CONFIRMED (ran a throwaway engine test)
- **Where:** `py/src/lib.rs:1614` in `run` and `py/src/lib.rs:1487-1499` in `Forced::act` (the check is at 1491); the `Forced` struct at 1478-1484 (`prefix: &'a [Action]` at 1480) and `play_all` at 1513; compare `py/src/lib.rs:297-305` in `Combat::step` (the name check at 298-303). Slot order: `engine/src/registry.rs:356-453` in `bind` (slots go by first appearance, 367-369 and 447-450).

**What goes wrong.** A Python action (`sts.Action`, in Rust `PyAction(Action, Option<&'static str>)`, lib.rs:122-128) carries a name when its card is a generated card or a variant. Such a card id is only a slot in one combat's binding (the per-combat table of generated cards and variants). `bind` gives generated cards their slots in order of first appearance in the deck list. So two decks that list the same generated cards in a different order give the same raw id to different cards.

`Combat.step` checks the name against its own binding (`if !b.is_bound(card) || b.def(card).name != name {`, line 300) and refuses with "... is not in this combat's slot (take actions from this combat)". `run` throws the names away: `let forced: Option<Vec<Vec<Action>>> = forced.map(|f| f.into_iter().map(|p| p.into_iter().map(|a| a.0).collect()).collect());` (1614). `Forced::act` then accepts a forced action when `s.legal_actions().contains(&a)` (1491), which compares raw ids only. So an action taken from one game, forced on another game that binds a different card at that id, silently plays the other card.

Python can't build a named action by name: `sts.Action("gen:x")` and a variant name both raise, and `sts.Action` has no pickling. So these actions always come from some combat's `legal_actions`, options or run records. Today's callers force each game's own recorded actions, so none of them is affected: `registry.selfplay`'s branch games (registry.py:224-226) and `scripts/tests/test_progress.py`. Main drops the name the same way (main's lib.rs:1548). The branch only adds Choose and variant actions to the same unchecked path. Variant slots go by value, so a variant mismatch needs a forced action from a game that holds a different set of variants at that decision.

**Reproduce.** Load this pack with `sts.load_content(json.dumps(ATTACKS))`. It is complete and valid for `registry::load_pack`: `parse_card` (registry.rs:734-766) needs `cost` and `type`, and the flags it doesn't get default to false; `Damage` takes `amount` and `target`, with `hits` defaulting to 1 (registry.rs:604-611).
```json
{"version": 1, "cards": [
  {"id": "fa_light", "cost": 1, "type": "Attack", "effects": [{"Damage": {"amount": 3, "target": "Opponent"}}]},
  {"id": "fa_heavy", "cost": 1, "type": "Attack", "effects": [{"Damage": {"amount": 20, "target": "Opponent"}}]}]}
```
Deck A is `["gen:fa_light", "gen:fa_heavy", "Strike", "Defend", "Defend"]`. Deck B is the same with the two generated cards swapped. Both use encounter `jaw_worm` and seed 1. Both decks bind to the same raw id list (slot 0, slot 1, Strike, Defend, Defend), so their openings are identical, and five cards means the opening hand is the whole deck. Take `light_a = next(x for x in sts.Combat(A, "jaw_worm", seed=1).legal_actions() if x.card == "gen:fa_light")` and run `sts.run("greedy", [("jaw_worm", B, 1)], forced=[[light_a]], record=True)`.
- Expected: `ValueError` ("a forced action was not legal in its game"). `sts.Combat(B, "jaw_worm", seed=1).step(light_a)` refuses the same action ("... is not in this combat's slot").
- Actual: the call returns with `actions[0].card == "gen:fa_heavy"`, so B plays its 20-damage card. In the verifier's engine test the monster went from 42 to 22 HP instead of 39.

**Fix.** Use one name check for both ways an action gets into a combat. Add this helper after `act` (lib.rs:139-144):
```rust
/// Whether `a`'s name (a generated card or a variant) is the card `b`
/// holds at its id; an action without a name always is.
fn named_in(a: PyAction, b: &Binding) -> bool {
    match (a.0, a.1) {
        (Action::Play { card, .. } | Action::Choose(card), Some(name)) => b.is_bound(card) && b.def(card).name == name,
        _ => true,
    }
}
```
- `Combat::step` (298-303): replace the `if let` block with this; the message is unchanged:
  ```rust
  if !named_in(action, &self.s.binding) {
      let name = action.1.unwrap_or_default();
      return Err(err(format!("{name:?} is not in this combat's slot (take actions from this combat)")));
  }
  ```
- `run`: delete line 1614. Line 1615 `let forced = forced.as_deref();` then gives `Option<&[Vec<PyAction>]>`.
- `play_all` (1513): `forced: Option<&[Vec<PyAction>]>`. `Forced` (1480): `prefix: &'a [PyAction]`. `&forced[i]` at 1527 still coerces.
- `Forced::act` (1489-1494): `if let Some(&a) = self.prefix.get(self.k) { self.k += 1; if named_in(a, &s.binding) && s.legal_actions().contains(&a.0) { self.forced_last = true; return a.0; } ...`. The `bad` branch is as today.
- `PyAction` is `Copy` plain data (a frozen pyclass, so `Sync`), so passing `&[Vec<PyAction>]` into `py.detach` and the scoped threads compiles as `&[Vec<Action>]` did.
- Docs:
  - `PyAction`'s comment (122-125): "`step` and `run`'s `forced` check the name against the combat's binding".
  - `Forced`'s comment (1475-1477): "an illegal forced action, or one naming a card its game holds at another id, sets `bad`".
  - `run`'s doc (1581-1583): forced actions must come from that game's own states (its `legal_actions`, options or recorded actions).
- Optionally widen the error at 1654 to "a forced action was not legal in its game, or named a card that game holds elsewhere". Keep the word "forced": `scripts/tests/test_branches.py:60` checks it.

Don't remap the name to the other game's slot. That silently forces a different action than the caller passed, and `Combat.step` refuses instead of remapping. Don't check against the spec's starting binding either: variants appear mid-game, so the check needs the state at that decision, which is `s` in `Forced::act`.

**Test first.** Add `py/tests/test_content_pack.py::test_forced_action_from_another_combat_refused` (new, next to `test_action_from_another_combat_refused`), with `ATTACKS` as a module-level constant. Today the second run returns and plays `gen:fa_heavy`, so the test fails with "forced gen:fa_light from deck A; deck B played gen:fa_heavy". The first run is a control that passes before and after the fix:
```python
ATTACKS = {"version": 1, "cards": [
    {"id": "fa_light", "cost": 1, "type": "Attack", "effects": [{"Damage": {"amount": 3, "target": "Opponent"}}]},
    {"id": "fa_heavy", "cost": 1, "type": "Attack", "effects": [{"Damage": {"amount": 20, "target": "Opponent"}}]}]}


def test_forced_action_from_another_combat_refused():
    """`sts.run(forced=...)` checks a generated card's name against the
    game's own binding, as `Combat.step` does: two decks that list the same
    generated cards in another order bind them to swapped slots."""
    sts.load_content(json.dumps(ATTACKS))
    a_deck = ["gen:fa_light", "gen:fa_heavy", "Strike", "Defend", "Defend"]
    b_deck = ["gen:fa_heavy", "gen:fa_light", "Strike", "Defend", "Defend"]

    def light(deck):
        return next(x for x in sts.Combat(deck, "jaw_worm", seed=1).legal_actions() if x.card == "gen:fa_light")
    r = sts.run("greedy", [("jaw_worm", b_deck, 1)], forced=[[light(b_deck)]], record=True)[0]
    assert r["actions"][0].card == "gen:fa_light"
    try:
        r = sts.run("greedy", [("jaw_worm", b_deck, 1)], forced=[[light(a_deck)]], record=True)[0]
    except ValueError as e:
        assert "forced" in str(e), e
    else:
        raise AssertionError(f"forced gen:fa_light from deck A; deck B played {r['actions'][0].card}")
```

**Must stay unchanged.** Only `py/src/lib.rs` changes, and it is not one of the fingerprint files: golden, codec, series_check, the contract pins and H4 are untouched. These must keep passing:
- `scripts/tests/test_branches.py`: forced openings reproduce the game; an empty `forced` leaves the output unchanged; an illegal forced action is an error.
- `scripts/tests/test_progress.py::test_chunked_play_is_identical`
- `py/tests/test_content_pack.py` (including `test_action_from_another_combat_refused`, which goes through the new `Combat::step` check) and `py/tests/test_sts.py` (illegal actions in `Combat.step`)

Branch-game datasets from `registry.selfplay` stay byte-identical: their forced actions are their own, so the check always passes. No pins change.

### F3. No test guards the naming of variant actions in `sts.run`, `sts.solve` and the solved database

- **Severity:** low · **Reach:** future change · **New on this branch:** yes · **Review:** sw_tests_3, cut by the 15 cap; verifier CONFIRMED (ran a throwaway engine test)
- **Where:**
  - `py/src/lib.rs:1444-1458` (option values) and `1465` (recorded actions) in `result_dict`
  - `py/src/lib.rs:1352` in `solve`, `1220-1221` in `PySolvedDb::fetch` and `1240-1241` in `PySolvedDb::positions`; all three go through `options_py` (1088-1100)
  - the panic these lines avoid: `engine/src/registry.rs:160` in `Binding::def`
  - the claim: `docs/decisions.md:2288` ("each with a test"), with the bullet at 2295-2297, and the spec 8 bullet at 2225-2227

**What goes wrong.** Nothing is wrong at HEAD, but a regression would pass every suite. Two review fixes name actions through each state's own binding (the per-combat table of generated cards and variants). A variant is a per-copy card, such as a grown Rampage, `Rampage{damage=13/combat}`, that only its combat holds.
- 662b6c6, in `result_dict`: recorded actions go through `let pa = act(a, &s.binding);` (1465), and values through `let b = r.trajectory.get(i).map_or(&spec.binding, |(s, _)| &s.binding);` (1453).
- 1a51035, for `options_py`'s callers: `options_py(py, &r.options, false, &s.binding)` (1352); `fetch` and `positions` use the binding decoded from the row's bytes (`sts_engine::codec::decode(&b).binding`, 1220 and 1240).

Before these fixes, `act` called `card_name` (lib.rs:63-65), which calls `Binding::def` on a variant id that the spec's starting binding (or an empty one) doesn't hold. Then `assert!(v != FREE, "variant card {} is not held in this combat", c.0);` (registry.rs:160) panics, in release too, and Python gets a pyo3 `PanicException`.

Neither commit added a Python test, and Rust tests can't reach `py/src/lib.rs`. The only Python test with Rampage (`py/tests/test_sts.py::test_variant_cards`, line 489) steps a Combat by hand. The record runs in `test_content_pack.py` and `test_gen_content.py` hold only generated cards, which the spec's binding names the same way. decisions.md:2288 says every cross-review fix has a test, but the record/values bullet (2295-2297) names none.

Corrections to the review evidence:
- (a) The generated-card half of the 1a51035 fix can't be reached. The solver keys every state by its codec bytes (`let key = encode(&s);`, engine/src/solve.rs:376, and `encode(root)` at 576). `codec::encode` asserts on any generated binding (`assert!(binding.is_empty(), ...)`, codec.rs:132). So `sts.solve` never gets as far as naming actions for generated content, and the solved database never holds it. The test covers variants only. `Binding::is_empty` looks only at generated slots, so states holding variants encode and solve.
- (b) A regression that only sets line 1453's `b` to `&spec.binding` doesn't panic: `act_in` (131-136) names an id the binding doesn't hold `"<unbound>"`. So the test must compare names, not only check that nothing raises.
- (c) With starter + 3 Rampage, natural play doesn't reliably meet the grown copy. The verifier found that jaw_worm seeds 0-2 never play or offer it. gremlin_nob, large_slime and slime_boss at seed 0 play it, and cultist seed 0 offers it at 3 decisions without playing it. The test below forces a fixed opening instead, so the variant appears whatever the search prefers, and its solve is a few nodes. Solving a mid-fight elite or boss state from natural play is not guaranteed to fit a node budget.

**Reproduce.** Add the test below. Copy lib.rs aside first (`cp py/src/lib.rs target/lib.rs.keep`; `/target` is gitignored). Then mutate one line at a time, rebuild with `bash scripts/dev_sts.sh`, and run the test:
1. Line 1465 to `let pa = act(a, &spec.binding);` (main's code): `sts.run` raises `PanicException: variant card 144 is not held in this combat` while it names the forced pick of the grown copy (decision 2). Natural play hits it too: `sts.run("search", [("gremlin_nob", STARTER + ["Rampage"] * 3, 0)], record=True)`; the verifier's replay plays the grown copy at decision 13.
2. Line 1453 to `let b = &spec.binding;` (an unused-variable warning only): `sts.run` returns, but decision 4's option values name the grown copy `"<unbound>"`, so the `x in legal` assertion fails.
3. Line 1352's `&s.binding` to `&Binding::default()`: `sts.solve` raises PanicException.
4. Line 1221's or 1241's `&binding` to `&Binding::default()`: `db.fetch` or `db.positions` raises PanicException.

Under each mutation, every existing engine, solvedb and Python test still passes (verifier). Restore with `cp target/lib.rs.keep py/src/lib.rs` and rebuild.

**Fix.** Add the test below. Name it in decisions.md: append `(py/tests/test_sts.py::test_variant_actions_named)` to the bullet at 2295-2297 and to the one at 2225-2227.

How the opening works. The deck is Rampage + 4 Headbutt against jaw_worm, seed 1. Five cards means every turn's hand is the whole deck.
- Turn 1: Rampage deals 8, and the copy becomes `Rampage{damage=13/combat}` in the discard pile (state.rs:1114-1146). Headbutt deals 9. Its pick offers only the grown copy, because a pick is offered whenever its pile is non-empty (state.rs:693-694 and 538-547), and puts it on top. Then End; Jaw Worm opens with Chomp (monsters.rs:278-286).
- Turn 2 draws the grown copy first.
- Forced decisions record no option values (`Forced::last_options` returns None, runner.rs:114), so the values check reads decision 4: the search's first own decision, whose hand holds the grown copy.
- Jaw Worm has 40-44 HP (monsters.rs:545-546). After turn 1's 17 damage it has 23-27 HP and no block, so any three attacks kill it on turn 2. A bounded solve from there finds the win on its first line and skips the other root options. Skipped options are still listed and named (`bounded`).
- The database part follows `scripts/tests/test_solve.py::test_binding_store_and_db`. The handle is reopened after the writes because `decision_ids` and `fetch` see the rows the handle found at open (solvedb/src/db.rs:349-353).

Optional, found while checking (not a review finding): `sts.solve` on a combat that holds generated content raises PanicException from the codec assert above, not a ValueError. `Combat.encode` refuses such combats cleanly (lib.rs:393-398), and `learn.solve_step` refuses content configs up front (learn.py:780-782). A guard right after `combat.need_action()?;` (lib.rs:1334) would match `Combat.encode`: `if !combat.s.binding.is_empty() { return Err(err("a combat with generated content can't be solved (it has no state encoding)")); }`. No test depends on the panic.

**Test first.** Add `py/tests/test_sts.py::test_variant_actions_named` (new, after `test_variant_cards`):
```python
def test_variant_actions_named():
    """Recorded actions and option values (`sts.run`), `sts.solve` options
    and solved-DB rows (`fetch`, `positions`) name a grown Rampage through
    that state's binding, as `legal_actions` does."""
    import os
    import tempfile
    grown = "Rampage{damage=13/combat}"
    deck = ["Rampage"] + ["Headbutt"] * 4  # five cards: every turn's hand is the whole deck
    c = sts.Combat(deck, "jaw_worm", seed=1)
    # Turn 1: Rampage grows, Headbutt's pick puts the grown copy on top, end
    # the turn; turn 2 draws it.
    forced = []
    for take in (lambda a: a.card == "Rampage", lambda a: a.card == "Headbutt",
                 lambda a: a.kind == "choose", lambda a: a.is_end_turn):
        forced.append(next(a for a in c.legal_actions() if take(a)))
        c.step(forced[-1])
    assert forced[2].card == grown and any(a.card == grown for a in c.legal_actions())
    # Forced decisions record no values; decision 4 is the search's own.
    r, = sts.run("search", [("jaw_worm", deck, 1)], record=True, values=True, forced=[forced])
    assert r["actions"][:4] == forced and r["states"][4].encode() == c.encode()
    for s, a, d in zip(r["states"], r["actions"], r["values"]):
        legal = s.legal_actions()
        assert a in legal, (a, legal)
        assert all(x in legal for acts, _ in d for x in acts), (d, legal)
    assert any(x.card == grown for acts, _ in r["values"][4] for x in acts), r["values"][4]
    sol = sts.solve(c, max_nodes=200_000, bounds=True)
    assert sol is not None
    acts = [x for o in sol["options"] for x in o[0]]
    assert set(acts) == set(c.legal_actions()) and any(x.card == grown for x in acts)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = os.path.join(tmp, "solved.sqlite")
        db = sts.SolvedDb(path)
        store = sts.SolveStore(min_nodes=0, db=db)
        first = sts.solve(c, max_nodes=200_000, bounds=True, store=store)
        assert store.add_position(c, "variant", "{}", "", 0, 0, 0.0)
        db = sts.SolvedDb(path)  # decision_ids and fetch see the rows a handle found at open
        rows = db.positions("variant")
        assert len(rows) == 1 and rows[0]["options"] == first["options"]
        (_, _, opts), = [row for row in db.fetch(db.decision_ids().tolist()) if row[0] == c.encode()]
        assert [(list(a), v) for a, v, _ in opts] == [(list(a), v) for a, v in first["options"]]
        del store, db  # closes the connections so the folder can go
```
This test is a guard, so it passes at HEAD. It also passes before and after F2: the forced actions come from this game's own states, so F2's name check accepts them. Check once that it fails under each mutation in Reproduce. Don't write it as a Rust test, which can't reach `result_dict` or `options_py`. Don't rely on natural play with STARTER + 3 Rampage against jaw_worm: those games never involve the grown copy.

**Must stay unchanged.** Only a test and docs change; with the optional solve guard, one refusal in `solve` too. No data or pin changes.

### F4. `GOLDEN_DUMP` can't print a proving-set game, though the golden check tells you to

- **Severity:** low · **Reach:** tooling · **New on this branch:** yes · **Review:** sw_tests_6, cut by the 15 cap; verifier CONFIRMED (read the code and git history; ran nothing)
- **Where:** `engine/tests/golden.rs:240-249` in `dump`. The key it can't read is made at `golden.rs:216` in `golden_trajectories` and printed by the assert at 231-237. `play_proving` is at 151-155 and `play_game` at 145-149 (`deck_for` at 59-73); `PROVING` (7 sets) at 43-51; `Character::from_name` is at `engine/src/character.rs:25-27`. The module doc (lines 9-10) and dump's doc (240) show only the pool form.

**What goes wrong.** The golden check (golden.rs) replays 9,000 seeded random-agent games, stored in golden.txt as `<character>:<encounter>:<seed> <hash>`. Since this branch it also replays 4,200 proving-set games: one fixed deck per rules-engine spec, the starter deck plus that spec's cards, stored in golden_proving.txt as `proving-<set>:<character>:<encounter>:<seed> <hash>`. When games differ, the check prints the first failing key in check order (pool games, then `PROVING` sets in order, each over `Encounter::ALL` and seeds 0-39). It then says `print it with GOLDEN_DUMP={} and diff against the old code` (233).

`dump()` splits the key on `:` and runs `let character = Character::from_name(parts[0]).expect("character");` (245). For a proving key, `parts[0]` is `"proving-rampage"`, so it panics with "character". It also always calls `print!("{}", play_game(character, enc, seed));` (248). `play_game` builds the pool deck: `deck_for` gives the starter for even seeds, and the starter plus 5 pool picks for odd seeds. It never builds `play_proving`'s starter plus set cards with a fresh `Rng::new(seed)`. So stripping the prefix by hand dumps a different game.

So when a change alters only a proving set, the "dump and diff against the old code" check can't be done. That has already happened once: 1a51035's rampage re-record changed 103 proving-rampage lines and nothing else in the golden data, the first being `proving-rampage:ironclad:cultist:12` (now golden_proving.txt line 3613). Main has no proving keys; they arrived in fee56fe on this branch.

**Reproduce.** `GOLDEN_DUMP=proving-rampage:ironclad:cultist:12 cargo test --release -p sts-engine --test golden dump -- --nocapture`.
- Expected: the dump of that game (the starter plus Rampage, Rampage, Rampage+, Protect, Protect+ against Cultist, seed 12). Its fnv1a hash is that key's line in golden_proving.txt (`bf3ac0bb9a24efde`).
- Actual: a panic with `character` at golden.rs:245. With the prefix stripped (`GOLDEN_DUMP=ironclad:cultist:12`), it prints the plain starter-deck game (seed 12 is even), not the proving game.

**Fix.** Make one function map a golden key to the game the check hashes, and call it from `dump()`:
```rust
/// The game a golden key names, played as the check plays it:
/// `<character>:<encounter>:<seed>` or `proving-<set>:<character>:<encounter>:<seed>`.
fn game_of_key(k: &str) -> String {
    let (set, rest) = match k.strip_prefix("proving-") {
        Some(r) => r.split_once(':').map(|(s, rest)| (Some(s), rest)).unwrap_or_else(|| panic!("bad key {k:?}")),
        None => (None, k),
    };
    let parts: Vec<&str> = rest.split(':').collect();
    assert_eq!(parts.len(), 3, "key {k:?}: [proving-<set>:]<character>:<encounter>:<seed>");
    let character = Character::from_name(parts[0]).unwrap_or_else(|| panic!("key {k:?}: no character {:?}", parts[0]));
    let enc = Encounter::from_name(parts[1]).unwrap_or_else(|| panic!("key {k:?}: no encounter {:?}", parts[1]));
    let seed: u64 = parts[2].parse().unwrap_or_else(|_| panic!("key {k:?}: bad seed"));
    match set {
        None => play_game(character, enc, seed),
        Some(name) => {
            let &(_, ch, extra) = PROVING.iter().find(|p| p.0 == name).unwrap_or_else(|| panic!("key {k:?}: no proving set {name:?}"));
            assert_eq!(ch, character, "key {k:?}: set {name} plays {}", ch.name());
            play_proving(ch, extra, enc, seed)
        }
    }
}
```
`dump()` becomes `let Ok(spec) = std::env::var("GOLDEN_DUMP") else { return }; print!("{}", game_of_key(&spec));`. Update the module doc (lines 9-10) and dump's doc (240) to show both forms, for example `GOLDEN_DUMP=proving-rampage:ironclad:cultist:12`. `Character` derives `Copy, Debug, PartialEq` (character.rs:6), so the destructuring and `assert_eq!` compile.

Alternative: also build every key in `golden_trajectories` through `game_of_key`, so the check and the dump can't drift apart. With the test below this isn't needed.

Don't change the key format in golden_proving.txt: that means re-recording 4,200 lines for a test helper. Don't strip the prefix and call `play_game` either: that prints the wrong deck.

**Test first.** Add `engine/tests/golden.rs::every_key_form_replays_its_game`. The name must not contain "dump", so the documented `--test golden dump` filter still runs only `dump`.
```rust
/// Every key form the check reports replays through `game_of_key` to its
/// recorded hash (seeds 0 and 1 of every pool and proving key).
#[test]
fn every_key_form_replays_its_game() {
    if std::env::var("GOLDEN_RECORD").is_ok() {
        return; // golden_trajectories is rewriting the files
    }
    let mut n = 0;
    for (k, &h) in &load() {
        if matches!(k.rsplit(':').next(), Some("0" | "1")) {
            assert_eq!(fnv1a(&game_of_key(k)), h, "{k}");
            n += 1;
        }
    }
    assert_eq!(n, 2 * (Character::ALL.len() + PROVING.len()) * Encounter::ALL.len()); // 2 * (2 + 7) * 15 = 270
}
```
Write it in this order:
1. Move dump's current parsing into `game_of_key` unchanged (pool keys only, `play_game`).
2. Add the test. It now panics with "character" at the first proving key it meets.
3. Add the proving branch. The test passes.

**Must stay unchanged.** golden.txt (9,000 lines; its hash is the registry's rules version) and golden_proving.txt (4,200 lines) stay byte-identical, with no re-record. `golden_trajectories` passes untouched. Only a test file changes; golden.rs is not a fingerprint file, so there is no effect on engine source, the fingerprint, the codec, series_check, the contract pins or H4. No pins change.

## Build step details

- **Step 0: build the module once.** Check that no Python process of this worktree is using `target/pyroot` (`tasklist //FI "IMAGENAME eq python.exe"`). Then run `bash scripts/dev_sts.sh`; it ends with "sts built into .../target/pyroot". This makes target/pyroot match HEAD. An older build could name actions differently.
- **Step F1: decode stored action text through `decode_in`** (fixes F1).
  - Files: `scripts/registry.py` (`replay`, `_decode_values`); `scripts/action_text.py` (`decode_action`'s variant pick and message at 119/124, `NotSupported`'s docstring, the module docstring's override bullet); `scripts/bench_decisions.py:122` (`replay`); `scripts/bench_probes.py:83` (`build`, plus `import action_text`); `scripts/analysis/pattern_value_error.py:123`.
  - Test: `scripts/tests/test_contract.py`, the new `test_variant_records_replay` and line 504's list (expect "decode_in", add the `Choose:Rampage{damage=13/combat}` case).
  - Size: about 20 changed lines, Python only, so no rebuild. Acceptance, from the worktree root:
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'scripts/tests'); import test_contract as t; t.test_variant_records_replay(); t.test_records_roundtrip(); t.test_fixed_silent_set(); print('ok')"` prints `ok`. Before the fix it raises `ValueError: unknown card "Rampage{damage=13/combat}"`.
  - Run `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe scripts/tests/test_registry.py`, then the same command for `scripts/tests/test_content_selfplay.py`, `scripts/tests/test_branches.py` and `scripts/tests/test_puzzles.py`. Each runs to the end with no failure, so GAMES_PIN and ARRAYS_PIN hold and the generated-deck cache build works.
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'scripts/tests'); import test_bench as t; t.test_replay_reproduces_decision_states(); t.test_probe_reference_orders_match_expected(); t.test_bench_unchanged(); print('ok')"` prints `ok`.
  - `git status --short data/ scripts/tests/data/` shows no changes.
- **Step F2: check forced actions' names against each game's binding** (fixes F2).
  - Files: `py/src/lib.rs`:
    - a new `named_in` helper after `act`
    - `Combat::step` (298-303) uses it, with the same message
    - delete line 1614, so `run` keeps the `PyAction`s
    - `play_all` (1513) takes `Option<&[Vec<PyAction>]>`, and `Forced::prefix` (1480) is `&'a [PyAction]`
    - `Forced::act` (1491) checks `named_in(a, &s.binding) && s.legal_actions().contains(&a.0)` and returns `a.0`
    - doc comments at 122-125, 1475-1477 and 1581-1583
  - Test: `py/tests/test_content_pack.py` (the `ATTACKS` pack and `test_forced_action_from_another_combat_refused`).
  - Size: about 20 changed lines. Acceptance:
  - With no Python process of this worktree using `target/pyroot`, `bash scripts/dev_sts.sh` ends with "sts built into .../target/pyroot".
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe py/tests/test_content_pack.py` ends with "N passed" and no failure. Before the fix the new test fails with "forced gen:fa_light from deck A; deck B played gen:fa_heavy".
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe scripts/tests/test_branches.py` passes.
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'scripts/tests'); import test_progress as t; t.test_chunked_play_is_identical(); print('ok')"` prints `ok`.
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe py/tests/test_sts.py` ends with "N passed".
- **Step F3: regression test for variant naming in run, solve and the solved DB** (fixes F3).
  - Files: `py/tests/test_sts.py` (new `test_variant_actions_named`, the forced Rampage + 4 Headbutt opening against jaw_worm, seed 1); `docs/decisions.md` (name the test in the bullets at 2225-2227 and 2295-2297). No code change, unless the optional solve guard is taken.
  - Acceptance:
  - `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'py/tests'); import test_sts as t; t.test_variant_actions_named(); t.test_variant_cards(); print('ok')"` prints `ok`.
  - One-time mutation check. First copy lib.rs aside: `cp py/src/lib.rs target/lib.rs.keep`. Don't use `git checkout py/src/lib.rs` to restore: it would also discard F2's lib.rs changes if they aren't committed. Apply one mutation at a time, rebuild with `bash scripts/dev_sts.sh`, run the test, then restore with `cp target/lib.rs.keep py/src/lib.rs`:
    - (1) lib.rs:1465 to `let pa = act(a, &spec.binding);`: the test raises PanicException "variant card 144 is not held in this combat" from `sts.run`.
    - (2) lib.rs:1453 to `let b = &spec.binding;`: the test fails on the `x in legal` assertion; the names read `<unbound>`.
    - (3) lib.rs:1352, `&s.binding` to `&Binding::default()`: `sts.solve` raises PanicException.
    - (4) Optional: lib.rs:1221 or 1241, `&binding` to `&Binding::default()`: `db.fetch` or `db.positions` raises PanicException.
    - After the last restore, rebuild once more. `git diff py/src/lib.rs` should then show only F2's changes, or nothing if F2 is committed.
  - `grep -c "test_variant_actions_named" docs/decisions.md` prints 2.
- **Step F4: GOLDEN_DUMP reads proving keys** (fixes F4).
  - Files: `engine/tests/golden.rs` only: a new `game_of_key`; `dump` uses it; the new test `every_key_form_replays_its_game`; docs at lines 9-10 and 240.
  - Size: about 35 changed lines. Acceptance:
  - `cargo test --release -p sts-engine --test golden` shows 3 passed (`golden_trajectories`, `dump`, `every_key_form_replays_its_game`).
  - `GOLDEN_DUMP=proving-rampage:ironclad:cultist:12 cargo test --release -p sts-engine --test golden dump -- --nocapture | grep -c Rampage` prints a number above 0, and the test passes. Before the fix it panics with "character".
  - `git diff --exit-code engine/tests/data` exits 0 (no re-record).
- **Order:** Step 0, then F1, F2, F3. F3's mutation check rebuilds the module, so run it after F2's lib.rs change is in place, and restore from the copy, not from git. F4 is independent and can go at any point.

## Pins for this group

No recorded pin, golden set or fingerprint changes in group F. The only expectation that changes is in a test. `scripts/tests/test_contract.py:504` expects the substring "decode_in" instead of "spec 8" for `Strike{cost=0/turn}@0`, and gains a case for `Choose:Rampage{damage=13/combat}`, because F1 rewords `action_text.decode_action`'s NotSupported message and adds the variant-pick refusal.

These must stay byte-identical:
- `engine/tests/data/golden.txt` (9,000 games; its hash is the registry's rules version) and `golden_proving.txt` (4,200 games). F4 must not re-record them.
- `engine/tests/data/codec_golden.txt`.
- The rules fingerprint: no group F fix edits the 8 files listed in `solvedb/src/fingerprint.rs` (state, cards, monsters, powers, hooks, effects, chance, character).
- `scripts/series_check.py` results (heuristic and contract nets on old columns), the contract pins (`scripts/tests/data/contract`, `py/tests/data/golden_rows.npz`, `scripts/tests/data/lookahead_off_names.json`, `lookahead_rows.npz`) and TRAIN_PIN.
- `test_content_selfplay.py`'s GAMES_PIN and ARRAYS_PIN, and the `scripts/tests/data/curriculum_pins.json` digests. F1 decodes to equal action objects (`_sample_afterstates`' options check at selfplay.py:390 still holds), so cache arrays are unchanged.
- The H4 `two_turn_phases --check` searches.
- `data/bench/decisions.json`, `reference.json`, `fixed_silent.json`, `scripts/tests/data/bench_quick_heuristic.json` (`test_bench_unchanged`), and every existing dataset and cache.
- Branch-game datasets from `registry.selfplay` after F2: forced actions are each game's own, so the name check always passes.

## Decisions for this group

None. Every group F fix is internal tooling: Python scripts, the py crate and one engine test file. No pin, data file, rules fingerprint or official-content behaviour changes, so nothing here is expensive to reverse.

## Notes the checker left

Nothing blocks a builder. One caveat: this check was read-only, so the forced Rampage + 4 Headbutt sequence used by the F1 and F3 tests was traced through the engine code but not executed. The code traced: picks (state.rs:533-547, 693-694), grow_damage (state.rs:1114-1146), Jaw Worm's pattern and HP (monsters.rs:278-286, 545-546), forced decisions recording no values (runner.rs:114 with Forced::last_options), and the bounded solve (solve.rs:534-578). If the F3 solve returns None, raise max_nodes. If an opening assertion fails, print c.legal_actions() after each step and adjust the selectors, keeping two requirements: decision 2 picks the grown copy, and decision 4 (the search's first own decision) offers it.
