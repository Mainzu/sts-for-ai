# Series review fixes, group A: training pipeline and features

Status: closed (2026-11-02, built and in use; A1 built in 5109ba8 (part 1 of series-review-fixes.md); A2-A5 stay in the backlog, unbuilt).

Part of `docs/specs/series-review-fixes.md`. Read that file first: it has the why, what must
stay true, the decisions, the build order and how to build and check. This file holds the
group's entries, then its build step details, the pins it may change, its decisions and the
notes its checker left. Line numbers are at `d9327a2`.

## Findings

### A1. Fine-tune trains on row kinds that its saved net drops

- **Severity:** high · **Reach:** official pipeline · **New on this branch:** yes (commit 662b6c6 added the row-kind override to `widen`; `scripts/finetune.py` is unchanged from main) · **Review:** CONFIRMED (reported #1)
- **Where:** `scripts/finetune.py:222-223` in `finetune` (the training set and both validation sets are encoded with the pre-widen `meta` built at line 216); `scripts/finetune.py:226` (`stsnet.widen`), `:229` (the replay pool is encoded with the widened `meta`), `:240` (`run.save_model` → `stsnet.save` → `layout_of` saves the widened `meta`'s layout); `scripts/stsnet.py:923` in `widen`.

**What goes wrong.** Some terms first:
- A saved net's *layout* is what it reads: the column names for each path, its row kinds and its pile slots (`stsnet.layout_of`, stsnet.py:813-819).
- *Row kinds* are the categories of feature rows the encoder writes (`ROW_KINDS`, `py/src/features.rs:80`):
  - `triggered`: card and power hook rows.
  - `threshold`: a monster's HP threshold, such as The Guardian's Mode Shift or the large-slime and Slime Boss splits.
  - `held`: a card's effect while it is held at turn end, such as Burn.
  - `static`, `countdown`, `replacement` and `pattern`: opt-in kinds, off by default (decisions "Series row kinds are opt-in").
- At use time the encoder drops every row kind that a net's saved list lacks. This happens in `keeps()` at `py/src/features.rs:985-987` and in the gather's `keep_kind` (computed in `set_layout` at features.rs:648-650, applied at features.rs:1287).
- `stsnet.widen` carries a trained net (the *parent*) over to a wider layout for fine-tuning.
- The *replay pool* is games from the parent's own training distribution. They are mixed into each training batch so the net keeps what it knew.

Here is the chain:
1. Line 216, `meta = kept_vocab(pmeta) if gen else vocab_for(pmeta)`, copies only `card_repr` and the `known_*` vocabularies. It copies no layout keys.
2. So `stsnet.features_for(meta)` builds an encoder with today's default kinds `["triggered", "threshold", "held"]` (the first `BASE_KINDS` = 3 entries of `ROW_KINDS`; features.rs:80 and :96), and `layout_of(meta)["row_kinds"]` falls back to that list. Line 222 (`train_ds = encoded(new_ds, k, meta, root, log)`) and line 223 (both validation sets) are encoded with those three kinds.
3. Line 226 then widens. On this branch `widen` replaces the new layout's kinds with the parent's: `new = {**new, "row_kinds": list(old["row_kinds"])}` (stsnet.py:923).
4. Parents saved before threshold and held rows existed list only `["triggered"]`. Two such parents are in use:
   - `models/value_effects.pt`, the `warm_effects` parent at `scripts/curve.py:60`.
   - The 2026-10-29 champion, `runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt` in the main checkout. It is the parent of the 0059 burst fine-tunes (for example `jobs/done/0059b1-finetune.json` runs `scripts/finetune.py --from` that file).

   Both `.pt` files have no `schema`, so `stsnet.load` reads their `.contract.pt` files, and those pickles hold `row_kinds ['triggered']` (and five piles).
5. So the replay pool (line 229) and the saved net (line 240) use one kind, while train and validation use three. Nothing in between filters rows by kind: `train.train` takes the sets as given.

The result: bench, gauntlet, ladder and in-search evaluation (`stsnet.load` → `features_for`, or `rust_evaluator` → `sts.NetEvaluator`) never give the net the threshold and held rows it was trained on. Those rows occur in boss fights, slime fights and with Burn. The best epoch and the `val_mse` saved with the run were measured on inputs the deployed net never receives. No error is raised.

On main, `widen` had no row-kind line, so it returned the new layout's kinds and the data and the saved layout agreed. Main's 0059b1 fine-tune of the champion (`runs/2026-11-01-burst8-s1-d4b65b6/model.pt`, parent the champion) saved `[triggered, threshold, held]`.

**Reproduce.** No games are needed. Save this as a scratch file and run it from the worktree root as `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe <file>` (branch module built by `bash scripts/dev_sts.sh`):
```python
import sys; sys.path.insert(0, "scripts")
import finetune, stsnet
model, norm, pmeta = stsnet.load("models/value_effects.pt")   # reads value_effects.contract.pt
print(pmeta["row_kinds"])                                      # ['triggered']
meta = finetune.vocab_for(pmeta)
print(stsnet.layout_of(meta)["row_kinds"])                     # ['triggered', 'threshold', 'held']: train + validation
print(stsnet.widen(model, norm, pmeta, meta)[2]["row_kinds"])  # ['triggered']: replay pool + saved net
```
Expected: one list for train, validation, replay and the saved net. Actual: two lists. End to end, any warm `finetune.finetune` from such a parent trains on three kinds and saves `row_kinds ['triggered']`.

The snippet shows the mechanism only. After the fix its last line still prints `['triggered']`, because `vocab_for` names no kinds and widen then keeps the parent's; the fix is that `finetune` names the kinds before it encodes anything. The end-to-end check is the second test below.

**Fix.** The owner chooses which kinds a fine-tune uses (owner decision A1; (b) is recommended). Step 1 and the layout guard in step 2 are the same for both choices and can be built before the decision:
1. In `stsnet.widen` (stsnet.py:908-975), keep the parent's kinds only when `new_meta` names none. When `new_meta` names kinds, use them, but refuse to drop any of the parent's kinds, just as widen already refuses a dropped column. Replace line 923 with:
   ```python
   if not new_meta.get("row_kinds"):
       new = {**new, "row_kinds": list(old["row_kinds"])}
   dropped = [k for k in old["row_kinds"] if k not in new["row_kinds"]]
   if dropped:
       raise ValueError(f"widen: the new layout drops row kinds {dropped}")
   ```
   (`layout_of(new_meta)` already returns `new_meta["row_kinds"]` when it names them, stsnet.py:818.) Replace the docstring's last sentence (stsnet.py:919-921, "The row kinds stay the old net's: ...") with: "The row kinds are `new_meta`'s when it names them (refused if they drop one of the old net's), otherwise the old net's: a row of a kind the net never read would pass through its trained row layers and change its scores, so only a caller that trains on new kinds names them."
2. In `finetune.finetune` (finetune.py:201-243):
   - Warm branch, right after line 216, name the kinds before anything is encoded:
     - (b), recommended:
       ```python
       today = stsnet.layout_of(meta)["row_kinds"]  # the encoder's defaults: triggered, threshold, held
       meta["row_kinds"] = today + [k for k in stsnet.layout_of(pmeta)["row_kinds"] if k not in today]
       ```
       That is today's defaults plus any kind the parent opted into.
     - (a): `meta["row_kinds"] = list(stsnet.layout_of(pmeta)["row_kinds"])`.

     `meta` is a fresh dict from `vocab_for` / `kept_vocab`, so this doesn't touch `pmeta`. Don't put the kinds into `vocab_for` or `kept_vocab` themselves: tests call `widen` with their output and expect no named kinds (`test_warm_start.py::test_widen_known_top`, and `test_finetune_gen.py::test_effects_vocab_unchanged` compares `layout_of(kept_vocab(meta))` with `layout_of(meta)`).
   - Just before line 222, save `data_layout = stsnet.layout_of(meta)`. Right after the widen at line 226, add:
     ```python
     if stsnet.layout_of(meta) != data_layout:
         raise ValueError("finetune: the widened net's layout differs from the layout its sets were encoded in")
     ```
     This stops the sets and the saved net from diverging again. Row columns don't depend on row kinds (`row_names`, features.rs:778-787), and widen's columns and piles come from `layout_of(new_meta)`, so after step 1 the two layouts are equal.
3. Docs:
   - In docs/decisions.md, "Series row kinds are opt-in", lines 2341-2342 read "`stsnet.widen` keeps a parent's own row kinds." Replace that sentence with: "`stsnet.widen` keeps a parent's own row kinds unless the caller names kinds, and never drops one (refused). `finetune.py` names [(b) today's defaults plus the parent's opt-in kinds | (a) the parent's own kinds] and encodes its training, validation and replay sets with them, so the saved net reads what it was trained on."
   - Under (b), also fix finetune.py's docstring at lines 20-22 ("An effects parent keeps its vocabularies (the cards bind to reserved power slots), so nothing widens."). Its vocabularies don't widen, but its row kinds become today's defaults plus its own opt-ins, so a parent saved before threshold and held rows gains those two.

Two wrong fixes to avoid:
- Don't delete line 923 outright. `vocab_for` and `kept_vocab` never name kinds, so widen would return today's defaults. A parent that opted into extra kinds would lose them on every widen, which breaks the confirmed decision, and `test_widen_known_top` (test_warm_start.py:107) fails because it asserts the kinds are kept.
- Don't overwrite `meta["row_kinds"]` after `widen` in finetune.py. The saved list would match by hand, but `widen` would still silently return a layout other than the one it was given.

**Test first.** Both tests go in `scripts/tests/test_warm_start.py`. Add `EFFECTS_NET = os.path.join(ROOT, "models", "value_effects.pt")` next to `IDS_NET` (line 25). `models/` is a junction to the main checkout's, so both nets exist in the worktree.
- `test_widen_takes_named_row_kinds` (no games). It fails today at the third assert (`widen` replaces the named kinds with the parent's `['triggered']`):
  ```python
  def test_widen_takes_named_row_kinds():
      """widen keeps the old net's row kinds when the new meta names none,
      takes named ones, and refuses to drop one."""
      model, norm, meta = stsnet.load(IDS_NET)
      assert meta["row_kinds"] == ["triggered"]
      new = finetune.vocab_for(meta)
      assert stsnet.widen(model, norm, meta, new)[2]["row_kinds"] == ["triggered"]
      kinds = ["triggered", "threshold", "held"]
      assert stsnet.widen(model, norm, meta, {**new, "row_kinds": kinds})[2]["row_kinds"] == kinds
      try:
          stsnet.widen(model, norm, meta, {**new, "row_kinds": ["threshold", "held"]})
      except ValueError as e:
          assert "drops" in str(e)
      else:
          raise AssertionError("a dropped row kind was accepted")
  ```
- `test_finetune_trains_on_saved_layout` (tiny games, like `test_finetune_tiny`). It fails today: the train and validation layouts list three kinds, the saved one lists one.
  ```python
  def test_finetune_trains_on_saved_layout():
      """Every set a warm fine-tune encodes (train, two validation sets,
      replay) is in the layout its saved net reads."""
      root = tempfile.mkdtemp(prefix="warm-layout-")
      seen, real = [], finetune.encoded

      def spy(ds, k, meta, *a, **kw):
          seen.append(stsnet.layout_of(meta))
          return real(ds, k, meta, *a, **kw)

      finetune.encoded = spy
      try:
          cfg = {"name": "tiny-layout", "content": "both", "games": 10, "top": 20, "game_seed": 7, "seed": 0,
                 "epochs": 1, "n_val": 5, "pool": 10}
          run = finetune.finetune(EFFECTS_NET, cfg, root=root, log=lambda *a: None, threads=4)
          _, _, m = stsnet.load(run.model_path)
          assert len(seen) == 4 and all(x == stsnet.layout_of(m) for x in seen)
          assert m["row_kinds"] == ["triggered", "threshold", "held"]  # under (a): ["triggered"]
      finally:
          finetune.encoded = real
          shutil.rmtree(root, ignore_errors=True)
  ```
  `finetune.finetune` looks `encoded` up in its module globals at call time, so the patch reaches all four calls (line 222, line 223 twice, line 229).

**Must stay unchanged.**
- This is a Python-only change: no engine or encoder file changes. So golden.txt, codec_golden.txt, series_check, the contract pins and H4 can't move.
- The six existing `test_warm_start.py` tests pass unchanged. They call `widen` with `vocab_for`, which names no kinds, and `test_widen_known_top` checks that the kinds are kept in that case. `test_finetune_tiny` (ids parent, `['triggered']`) asserts columns and the normaliser, not kinds.
- `scripts/tests/test_finetune_gen.py` passes unchanged (`kept_vocab` isn't touched).
- `scripts/tests/test_curve.py` passes unchanged; its `test_curve_quick` fine-tunes value_effects through the changed path.

What changes, on purpose:
- A fine-tune saved after the fix lists the kinds it trained on. Under (b), a `['triggered']` parent gives `[triggered, threshold, held]`, the same list main saved. Under (a), it gives `['triggered']`.
- The encoded-set caches `cache/warm-<ds>-<k>-<key>.npz` are keyed by the layout (finetune.py:165-167):
  - Under (b), for a parent whose kinds are among today's defaults, the train and both validation caches keep their keys. The replay pool's cache gets a new key and is rebuilt once for a `['triggered']` parent (a three-kind parent's replay key is unchanged).
  - Under (a), for a `['triggered']` parent, the train and both validation caches get new keys and are rebuilt once; the replay pool keeps its key.

### A2. next_draw_size ignores hand space taken by retained cards

Built 2026-11-15 with draw-knowledge item 2 (`CombatState::next_draw`).

- **Severity:** medium · **Reach:** content packs (the column alone is also wrong with official proving content, Protect, or with 6+ Brutality stacks) · **New on this branch:** yes · **Review:** CONFIRMED (reported #10)
- **Where:** `py/src/features.rs:1572-1591` in `next_draw_size`. It feeds the `next_draw_size` player column at `py/src/features.rs:1332` and the known-top split in `encode_one` at `py/src/features.rs:1446-1459`. Engine reference: `engine/src/chance.rs:147-149` in `request_draw`; `engine/src/state.rs:848-857` in `end_turn`; `HAND_LIMIT` at `engine/src/state.rs:21`.

**What goes wrong.** Some terms first:
- The *known top* (spec 7) is the cards the player knows are on top of the draw pile. Headbutt puts them there, and so does a pack card's `DiscardToTop` pick.
- The encoder splits the known top into two piles: `next_draw` (known cards the next turn's draw will take) and `known_later` (the rest). It splits at k = `next_draw_size(s)`, and it also writes k as a player column.
- *Retain* (spec 8; official proving card Protect, or a pack card with `"retain": true`) keeps a card in hand at turn end.

`next_draw_size` adds up the base draw (5), the Silent's first-turn extra before turn 1, and each turn-start `Draw` hook times its stacks (Brutality is the only official one). It stops there. The engine, however:
- caps every draw by hand space: `let space = HAND_LIMIT.saturating_sub(self.hand.len()); let n = (n as usize).min(space).min(self.draw.len() + self.discard.len());` (chance.rs:148-149, `HAND_LIMIT = 10`);
- keeps retained cards in hand at turn end: `if self.binding.def(card).retain { self.hand.add(card, n); }` (state.rs:850-851).

So with r retained cards, the next turn draws at most 10 − r, but the features use k. Two things go wrong:
1. The column overstates the draw.
2. When the known cards outnumber 10 − r, the line `if i < k { next.add(c, 1) } else { later.add(c, 1) }` (line 1456) files cards in `next_draw` that the next turn won't draw.

The docs disagree with the code:
- The umbrella spec says "At the EndTurn leaf it is exact" (`docs/specs/rules-engine-upgrade.md:272`).
- The spec 7 decision defines k without hand space (`docs/decisions.md:2010-2013`), but it was written before Retain existed.

With official cards only, the split can't go wrong. Each Headbutt leaves the hand as it adds one known card, draws take known cards first, and Protect is the only retained card, so retained plus known cards stay within 10. A pack can break that: `DiscardToTop` with n > 1, or a card that adds retained cards to the hand (`AddCard` of Protect to `Hand`). No net has been trained on these columns yet. Old nets fold `next_draw` and `known_later` into `draw` and don't read the column.

**Reproduce.**
1. The column, with official cards only:
   - `c = sts.Combat(["Protect"] * 10, "jaw_worm", seed=1)`, then `c.step(sts.Action())` to end turn 1.
   - Five Protects stay in hand and turn 2 draws the other five, so `c.piles()["hand"] == {"Protect": 10}` and `c.piles()["draw"] == {}`.
   - Encode with `f = sts.Features()`. `dict(zip(f.player_names, f.encode([c])["player"][0]))["next_draw_size"]` is 5, but the next turn draws 0. Expected 0.
2. The split, with this pack (complete and valid for `sts.load_content` / `registry::load_pack`: version 1, no powers, card fields `id`, `cost`, `type`, `effects`; `AddCard` takes an official card name, `n` and `pile`; `Pick` takes `kind` and `n`, `exact` defaults to true):
   ```json
   {"version": 1, "cards": [
     {"id": "a2_fill", "cost": 0, "type": "Skill", "effects": [{"AddCard": {"card": "Protect", "n": 8, "pile": "Hand"}}]},
     {"id": "a2_dig", "cost": 0, "type": "Skill", "effects": [{"Pick": {"kind": "DiscardToTop", "n": 3}}]}]}
   ```
   - Deck `["gen:a2_fill", "gen:a2_dig", "Strike", "Strike", "Strike"]`, encounter `"jaw_worm"`, seed 1, Ironclad. The deck has five cards and the Ironclad draws 5 on turn 1, so turn 1 draws all of them whatever the shuffle.
   - Play `sts.Action("Strike", 0)` three times (energy 3 → 0).
   - Play `gen:a2_fill` (cost 0): 8 Protects join the hand (it holds only `gen:a2_dig` then, so all 8 fit).
   - Play `gen:a2_dig` and pick Strike three times with `sts.Action.choose("Strike")`.
   - Now the hand is 8 Protects, and the draw pile is 3 Strikes, all known on top.
   - Encode with `sts.Features()`. Actual: `next_draw_size` 5, the `next_draw` pile (index `sts.PILES.index("next_draw")`) holds 3 Strikes, `known_later` holds none. Expected: 2, then 2 Strikes, then 1 Strike.
   - Then end the turn with `c.step(sts.Action())`. The engine draws 2 (hand space 10 − 8), so `c.piles()["hand"] == {"Protect": 8, "Strike": 2}` and `c.piles()["draw"] == {"Strike": 1}`. This is the reference the features must match.

   A generated card can't be named in `sts.Action(...)` (it is refused, `test_action_from_another_combat_refused`); play pack cards by picking the legal action whose `card` is `"gen:<id>"`.

**Fix.**
- In `next_draw_size`, cap k by the hand space the next turn starts with: the hand limit less the cards in hand that Retain keeps. This is "as if the turn ended now"; at the EndTurn leaf the hand holds exactly those cards. Replace the final `k` (line 1590) with:
  ```rust
  let kept: usize = s.hand.iter().filter(|&(c, _)| s.binding.def(c).retain).map(|(_, n)| n as usize).sum();
  k.min(HAND_LIMIT.saturating_sub(kept))
  ```
  (`Pile::iter` yields `(CardId, u8)`, state.rs:109; `Binding::def` handles official, generated and variant cards.)
- Add `HAND_LIMIT` to the import at features.rs:68: `use sts_engine::state::{CombatState, Pile, Stage, Who, DRAW_PER_TURN, HAND_LIMIT, MAX_MONSTERS};`.
- Docs:
  - In the doc comment (features.rs:1572-1574), add: "capped by the hand space the next turn starts with: 10 less the cards in hand that Retain keeps (the engine caps every draw by hand space)".
  - Make the same addition to the spec 7 features line in `docs/decisions.md:2010-2013`, after "times stacks".
  - Qualify the umbrella spec's "At the EndTurn leaf it is exact" (rules-engine-upgrade.md:272) with "when the piles hold enough cards".

Leave out a cap by cards left (draw + discard). Mid-turn, the discard pile still grows before the next draw (the hand's other cards go there at turn end), and the net reads both pile sizes anyway. The split can't depend on it either, because known cards are always in the draw pile.

Don't cap by the whole hand (`s.hand.len()`). Non-retained cards leave the hand at turn end, so every ordinary state would read a smaller draw and every pinned encoding would move.

An alternative: one engine helper used by both `request_draw` and the features would keep the two in step. It would edit a fingerprinted engine file (chance.rs) for no rules change, so it isn't needed here.

**Test first.** Build first with `bash scripts/dev_sts.sh`.
- `py/tests/test_sts.py::test_next_draw_size_counts_retained_cards` (reproduction 1). It is 5 today:
  ```python
  def test_next_draw_size_counts_retained_cards():
      """next_draw_size is capped by the hand space Retain leaves: ten
      Protects held leave no room to draw."""
      c = sts.Combat(["Protect"] * 10, "jaw_worm", seed=1)
      c.step(sts.Action())
      assert c.piles()["hand"] == {"Protect": 10} and c.piles()["draw"] == {}
      f = sts.Features()
      row = dict(zip(f.player_names, f.encode([c])["player"][0]))
      assert row["next_draw_size"] == 0
  ```
- `py/tests/test_content_pack.py::test_known_top_split_counts_retained_cards` (reproduction 2). Name the pack `RETAIN_PACK`; `PACK` is taken. Today the three feature values are 5, 3 and 0:
  ```python
  RETAIN_PACK = {"version": 1, "cards": [
      {"id": "a2_fill", "cost": 0, "type": "Skill", "effects": [{"AddCard": {"card": "Protect", "n": 8, "pile": "Hand"}}]},
      {"id": "a2_dig", "cost": 0, "type": "Skill", "effects": [{"Pick": {"kind": "DiscardToTop", "n": 3}}]}]}


  def test_known_top_split_counts_retained_cards():
      """Eight retained Protects leave room for 2 of the 3 known Strikes:
      next_draw holds 2, known_later 1, as the engine then draws."""
      sts.load_content(json.dumps(RETAIN_PACK))
      c = sts.Combat(["gen:a2_fill", "gen:a2_dig", "Strike", "Strike", "Strike"], "jaw_worm", seed=1)
      for _ in range(3):
          c.step(sts.Action("Strike", 0))
      play_power(c, "gen:a2_fill")
      play_power(c, "gen:a2_dig")
      for _ in range(3):
          c.step(sts.Action.choose("Strike"))
      assert c.piles()["hand"] == {"Protect": 8} and c.piles()["draw"] == {"Strike": 3}
      f = sts.Features()
      b = f.encode([c])
      row = dict(zip(f.player_names, b["player"][0]))
      assert (row["next_draw_size"], row["known_top"]) == (2, 3)
      count = lambda p: float(b["card_count"][b["card_pile"] == sts.PILES.index(p)].sum())  # noqa: E731
      assert (count("next_draw"), count("known_later")) == (2, 1)
      c.step(sts.Action())
      assert c.piles()["hand"] == {"Protect": 8, "Strike": 2} and c.piles()["draw"] == {"Strike": 1}
  ```
  `play_power(c, name)` (test_content_pack.py:43-45) steps the first legal action whose `card` is `name`.

**Must stay unchanged.**
- The engine isn't touched, so golden.txt, codec_golden.txt, H4 and the rules fingerprint can't move.
- series_check stays PASS: old nets don't list `next_draw_size` and fold both new piles into `draw`.
- These must stay byte-identical: `py/tests/data/golden_rows.npz` (`test_sts.py::test_golden_features_unchanged`), the contract pins (`scripts/tests/test_contract.py`, `contract_pins.fixed_states`), TRAIN_PIN (`scripts/tests/test_net.py:364`), ARRAYS_PIN (`scripts/tests/test_content_selfplay.py:32`) and `scripts/tests/data/curriculum_pins.json`. Their states hold no retained card: Protect is proving content, in no deck pool. `py/tests/golden.py` gives two of its eight decks one Brutality+ each, so k is at most 6 there.
- If a pin moves, look at the moved states. A state with 6+ Brutality stacks changes legitimately (k is capped at 10): re-record that pin and say why. Any other moved state means the fix is wrong.
- `test_known_top_piles` keeps `(known_top, next_draw_size) == (1, 5)` (its hand holds three Headbutts, none retained).

### A3. Default features leave no trace of powers encoded only by opt-in rows

- **Severity:** low · **Reach:** content packs; official proving content (Accuracy, Wraith Form) · **New on this branch:** yes · **Review:** CONFIRMED (cut by the 15 cap)
- **Where:** `py/src/features.rs:791-794` in `Encoder::powers`; `py/src/features.rs:898` in `Encoder::effects`; `py/src/features.rs:946-948` in `power_rows`; `py/src/features.rs:985-987` in `keeps`. Stale comments at `scripts/tests/test_contract.py:74-75` in `test_modifier_list`. The decision is at `docs/decisions.md:2322-2345` ("Series row kinds are opt-in", confirmed by the owner).

**What goes wrong.** Some terms first:
- In *effects mode* (the default card representation), a power gets a column only if it is one of the six built-in modifiers (`MODIFIER_POWERS`, features.rs:146-147). Every other power is described by rows.
- The row kinds `static`, `countdown` (RoundEnd hooks), `replacement` and `pattern` are *opt-in*. They are written only with `sts.Features(..., extra_rows=True)` or for a layout that lists one. The owner confirmed this to save memory.

With the defaults, a power whose only rows are of those kinds gets no input at all:
- `powers()` skips it before choosing a column: `if self.repr == CardRepr::Effects && !is_modifier(k) { continue; }`. It doesn't even count in `power_unknown`.
- `effects()` drops a card's or intent's `Apply` of it (line 898).
- `power_rows` skips `RoundEnd` hooks (line 948).
- `keeps()` turns off kinds 3 and up unless `extra_rows` is set.

Today this covers (`test_modifier_list` shows these are the only official powers that are neither modifiers nor hook powers, apart from ModeShift, which threshold rows encode):
- Accuracy and Red Skull (one static each, hooks.rs:305-306).
- Intangible (one RoundEnd countdown and two replacements, hooks.rs:204 and 279-282; Wraith Form grants it).
- Any pack power built only from statics, replacements or RoundEnd hooks. Spec 10 loads these.

So a default net reads Accuracy's card as a 1-cost Power that does nothing, and Wraith Form as only its Dexterity −1 per turn row. One exception: a monster holding Red Skull at half HP or less shows it in its `intent_damage` column, but no official monster holds Red Skull.

The decision names memory as the cost but not this consequence. The comments at test_contract.py:74-75 ("Accuracy and Red Skull: static rows only", "Intangible: replacement and countdown rows only") read as if rows encoded these powers, which a default encoder no longer does. The normal pipeline never meets these powers: proving cards are in no deck pool, and `scripts/gen_content.py` writes only hook powers with non-RoundEnd triggers.

**Reproduce.** `rows_of` is the helper at `py/tests/test_sts.py:315-320`.
- Accuracy:
  - `c = sts.Combat(["Accuracy"] * 10, "jaw_worm", seed=1, character="silent")`, then `c.step(sts.Action("Accuracy"))`. The player now holds Accuracy 4.
  - With `f = sts.Features()`, `"power_Accuracy" not in f.player_names`, and `rows_of(f.encode([c]), f.row_names, entity=0)` is `[]`.
  - With `sts.Features(extra_rows=True)`, the player has one static row (`static_add` 4).
- Wraith Form: deck `["Wraith Form"] * 5 + ["Caltrops+"] * 5`, Silent (it draws 7, so at least two Wraith Forms are in hand). After `c.step(sts.Action("Wraith Form"))`, the default player rows hold only WraithForm's `OwnerTurnEnd` Dexterity −1 row. Nothing shows Intangible.

**Fix.** Text only, because the behaviour is the confirmed design:
1. Replace `scripts/tests/test_contract.py:74-75` with:
   ```python
   # Accuracy and Red Skull: only static rows; Intangible: only replacement and countdown rows.
   # Those kinds are opt-in (decisions "Series row kinds are opt-in"), so a default
   # encoder writes nothing for these three powers.
   ```
   While in this file, fix the `test_row_kinds_and_piles` docstring at lines 100-102. It says "no parent piles yet", but the test asserts two (`PILE_PARENTS`), and it omits `pattern`, which line 103 asserts. New text: "Row kinds: triggered, then threshold and held (threshold-and-held-rows spec), static and countdown (static-modifiers), replacement (replacement-hooks), pattern (monster-patterns); piles in the head's slot order; next_draw and known_later fold into draw (known-top)."
2. In docs/decisions.md, opt-in entry, after "...the warm-start curve can opt in." (line 2338), add: "Consequence: with the kinds off, a power encoded only by them gets no input in a default batch (no column, no row; a card applying it reads as its other effects): Accuracy, Red Skull, Intangible, and any pack power built only from statics, replacements or RoundEnd hooks. Content that relies on such powers needs a net that opts in."
3. In docs/extending.md:111-115 ("Structure is vocabulary too"), after "written only for a net whose layout lists one", add: ", so a power encoded only by those kinds (Accuracy, Red Skull, Intangible, or a pack power made only of statics, replacements or RoundEnd hooks) is invisible to every other net".

Not recommended now:
- Writing opt-in rows by default for powers without a column. That changes default encodings and revisits a confirmed decision, so it is the owner's call if generated content starts using static-only or replacement-only powers.
- A one-time stderr warning like `IDS_WARNED` (features.rs:136 and 1336-1338) when a default encoder meets such a power. It is cheap but optional.

**Test first.** No failing test: nothing in the code is wrong. Add `py/tests/test_sts.py::test_default_kinds_hide_static_only_powers` to pin the documented behaviour. It passes before and after, and fails if someone changes the default without updating the docs:
```python
def test_default_kinds_hide_static_only_powers():
    """Decisions "Series row kinds are opt-in": a power encoded only by
    opt-in kinds (Accuracy: one static) has no column and no row by default."""
    c = sts.Combat(["Accuracy"] * 10, "jaw_worm", seed=1, character="silent")
    c.step(sts.Action("Accuracy"))
    f = sts.Features()
    assert "power_Accuracy" not in f.player_names
    assert rows_of(f.encode([c]), f.row_names, entity=0) == []
    x = sts.Features(extra_rows=True)
    assert len(rows_of(x.encode([c]), x.row_names, entity=0)) == 1
```

**Must stay unchanged.** Everything: this is comments, docs and one new test. No pin moves.

### A4. Training caches round fractional opt-in row values to float16

- **Severity:** low · **Reach:** future change (only when a pipeline opts into the extra row kinds) · **New on this branch:** partly (the float16 cast is from main; the fractions it rounds are new) · **Review:** CONFIRMED (cut by the 15 cap)
- **Where:** `scripts/stsnet.py:215` in `Dataset.from_batches`: `parts["rows"].append(b["rows"][rorder].astype(np.float16))` (cards at :210). The fractional writers are `py/src/features.rs:1007` in `pattern_rows` (`out.push(p as f32)`), `:1039` in `replacement_row` and `:1069` in `static_row` (both `num as f32 / den as f32 - 1.0`). The assumption is stated at `docs/decisions.md:225`.

**What goes wrong.** Every training cache stores row values as float16: learn.py:919/936, selfplay.py:440, curve.py:100, finetune.py:182 and registry.py:353 all go through `from_batches`. The stated reason is "Card rows are stored as float16 (small integers, exact)". Training reads the values back as float32 through `Dataset.batch` (or `DatasetView.batch`), while search (`sts.NetEvaluator`) encodes rows live in float32.

Before this branch, every row and card value was a small integer, and card vectors still are. The opt-in row kinds write fractions, though:
- a pattern row's `condition_param` is the move's probability;
- replacement and static rows write `num/den − 1`.

float16 rounds these by up to about 2.4e-4 for values in [0.5, 1). For Jaw Worm after Chomp, Thrash 0.409375 becomes 0.409423828125 and Bellow 0.590625 becomes 0.5908203125. The official static factors (−0.25, 0.5) are exact. A pack factor such as 2/3 is not; `registry.rs` only requires den > 0.

So a net trained on such a cache sees slightly different inputs at search time. The cache-equals-live check `scripts/tests/test_net.py::test_dataset_gather_keeps_rows` would fail with `extra_rows=True` on a state with a non-dyadic value, such as the Jaw Worm state below. Its own Cultist `power_states` would still pass, since their opt-in values are exact (pattern probability 1, Vulnerable's 0.5). No pipeline opts in today: no script passes `extra_rows`, and no saved net lists the extra kinds.

**Reproduce.** From the worktree root with the branch module (`PYTHONPATH="$PWD/target/pyroot"`):
```python
import sys; sys.path.insert(0, "scripts")
import numpy as np, sts, stsnet
f = sts.Features("effects", extra_rows=True)
b = f.encode([sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], "jaw_worm", seed=1)])
ds = stsnet.Dataset.from_batches([b], [0.0])
print(np.abs(ds.batch([0])["rows"] - b["rows"]).max())   # ~1.95e-4; 0.0 with sts.Features("effects")
```
With one state, `from_batches` keeps the row order (stable sort by state), so the two arrays line up.

**Fix.** Document now. Change the code when a pipeline first opts in.
- Now:
  - Add a comment at stsnet.py:215: float16 is exact for the default row kinds (small integers); the opt-in kinds' fractions (pattern probabilities, static and replacement multipliers) round by up to about 2.4e-4.
  - In docs/decisions.md, opt-in entry, extend the "How a net opts in" sentence (lines 2339-2341): a pipeline that opts in either accepts float16 rounding of pattern probabilities and pack multipliers, or stores rows as float32.
- Later, when opting in:
  - Give `Dataset.from_batches` a `rows_dtype` argument (default `np.float16`). The cache builder passes `np.float32` when its encoder writes an opt-in kind (`feats.extra_rows`).
  - Decide the dtype per cache, never per batch. `DatasetWriter._write` refuses a dtype change between parts (stsnet.py:361-362), so switching per batch would fail a long cache build midway.
  - `Dataset.subset` (stsnet.py:263-266) rebuilds through `from_batches`: pass `rows_dtype=self.rows.dtype` so a float32 dataset stays float32.
  - Keep one rows dtype per training set, and refuse a mix. `Dataset.concat` (stsnet.py:164-188) silently upcasts a float16/float32 mix to float32 (memory). `DatasetView._flat` (stsnet.py:461-475) allocates its output in the dtype of the first part it reads, so a float32 part gathered after a float16 one is rounded back to float16 without an error.
  - Alternative: round the three fractional values onto the float16 grid inside the encoder. Cache and live then agree at no memory cost, but the opt-in values change and `test_pattern_rows`' sum-to-1 tolerance (1e-6) would need loosening (the Jaw Worm pair would sum to 1.000244).

**Test first.** None for the doc change. With the later code change: extend `scripts/tests/test_net.py::test_dataset_gather_keeps_rows` with an `extra_rows=True` encoder on the Jaw Worm state above, the dataset built with `rows_dtype=np.float32`, compared through the file's `rows_by_owner`. It fails today because that argument doesn't exist and float16 differs.

**Must stay unchanged.** Everything (a comment and docs). With the later change, caches of the default kinds stay float16 and byte-identical: TRAIN_PIN, ARRAYS_PIN and `scripts/tests/data/curriculum_pins.json` must not move.

### A5. Threshold-granted powers get no static, countdown or replacement rows

- **Severity:** low · **Reach:** future change · **New on this branch:** yes (the extra row kinds are new; `threshold_rows` is the same as on main) · **Review:** PLAUSIBLE (cut by the 15 cap)
- **Where:** `py/src/features.rs:1151-1158` in `threshold_rows`. Compare the intent path at `py/src/features.rs:1385-1387` in `encode_one` (`granted_kind_rows`) and the card path at `:1439-1442` (`card_kind_rows`, when `extra_rows` is on). The threshold source is `engine/src/threshold.rs:19-40` (`GUARDIAN_SHIFT`, `threshold`).

**What goes wrong.** Some terms first:
- A *threshold row* tells the net "when this monster has lost N more HP, these effects happen". Examples: The Guardian's Mode Shift, the large slimes' split.
- *Granted rows* are the rows of a power that a card, an intent or a threshold applies.

With `extra_rows` on, a power applied by a card or an intent gets its hook rows plus its static, countdown and replacement rows (`granted_kind_rows`). `threshold_rows` writes the threshold row and then calls `granted_rows_if(t.effects, Some(cond), &s.binding, out)`. That goes through `power_rows`, which writes hook rows only and skips RoundEnd hooks; nothing calls `granted_kind_rows`. So a power granted by a threshold would lose its static and replacement rows, and a RoundEnd countdown would be dropped entirely.

No state shows this today:
- The only threshold effects are `GUARDIAN_SHIFT` (`Block`, then `Apply SharpHide 3`) and the split moves (`[Effect::Split]`).
- Sharp Hide has one `CardPlayed` hook and no statics, no replacements and no RoundEnd hook.
- Packs can define neither monsters nor new rows for an official power (`load_pack` reads only `powers` and `cards`).

It appears only after a future change, for example a monster that gains Strength, Artifact or Intangible at an HP threshold.

**Reproduce.** Not reachable with current content, which is why the verifier rated it PLAUSIBLE. The test below makes the precondition checkable.

**Fix.** A comment and a tripwire test now; no feature change.
- Extend the doc comment on `threshold_rows` (features.rs:1151-1152) to: "A monster's `threshold` rows: the threshold's effects, then the hooks of hook powers they apply, all under `HpLostReaches`. Only hook rows: a threshold that applied a power with statics, replacements or a `RoundEnd` hook would need those rows written under the threshold's condition first (none does; `engine/tests/threshold.rs::threshold_powers_have_hook_rows_only` fails when one does)."
- Don't just call `granted_kind_rows(t.effects, ...)` from `threshold_rows`. A static row writes the static's own condition (features.rs:1058-1059), a replacement row writes `Always` (:1027) and a countdown row its hook's condition, so those rows would read as an unconditional grant rather than "after N more HP lost". Encoding them properly needs a design decision about where `HpLostReaches` goes, once such a threshold exists.

**Test first.** Add `engine/tests/threshold.rs::threshold_powers_have_hook_rows_only`. The file already has `use sts_engine::effects::Effect;` and `use sts_engine::threshold::{threshold, GUARDIAN_SHIFT};`. The test passes today; it is a tripwire that fails when a future threshold applies such a power, pointing here:
```rust
#[test]
fn threshold_powers_have_hook_rows_only() {
    use sts_engine::codec::MONSTER_KINDS;
    use sts_engine::hooks::{hooks, replacements, statics, Trigger};
    use sts_engine::monsters::NO_MOVE;
    let mut lists = vec![GUARDIAN_SHIFT];
    for &k in MONSTER_KINDS.iter() {
        let d = k.def();
        if d.split_move != NO_MOVE {
            lists.push(d.moves[d.split_move as usize].effects);
        }
    }
    for effects in lists {
        for e in effects {
            if let Effect::Apply { power, .. } | Effect::RandomApply { power, .. } = *e {
                assert!(statics(power).is_empty() && replacements(power).is_empty(), "{power:?}");
                assert!(hooks(power).iter().all(|h| h.trigger != Trigger::RoundEnd), "{power:?}");
            }
        }
    }
}
```

**Must stay unchanged.** Everything. This is a comment in py/src and an engine test; no fingerprinted file is edited.

## Build step details

The three steps are independent. A-2 and A-3 can go first; in A-1, the widen change and the layout guard are must-fix whatever the decision, and only the line naming the kinds in finetune.py waits for the A1 choice. Before any `bash scripts/dev_sts.sh`, check that no Python process from this worktree is still using target/pyroot's `sts` (Windows locks the loaded .pyd, and the script deletes target/pyroot first). Run every Python check from the worktree root as `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe <file>`.

- **Step A-1: fine-tune data and saved net share one layout (A1).** It needs the owner's A1 choice; (b) is recommended.
  - Files:
    - `scripts/stsnet.py`, in `widen`: replace line 923 with the named-kinds / no-drop block, and replace the docstring's last sentence (lines 919-921).
    - `scripts/finetune.py`, in `finetune`: after line 216, name the kinds ((b) or (a)); before line 222, save `data_layout`; after line 226, raise `ValueError` if `stsnet.layout_of(meta) != data_layout`. Under (b), fix the docstring at lines 20-22 ("so nothing widens").
    - `docs/decisions.md`: replace the widen sentence at lines 2341-2342 of "Series row kinds are opt-in".
  - Tests: `scripts/tests/test_warm_start.py::test_widen_takes_named_row_kinds` and `::test_finetune_trains_on_saved_layout` (plus the `EFFECTS_NET` constant). Both fail before the fix.
  - Size: about 20 changed lines plus about 45 test lines.
  - Acceptance:
    - No Rust file changes. Build with `bash scripts/dev_sts.sh` only if `target/pyroot` is missing or was built before HEAD.
    - `scripts/tests/test_warm_start.py` prints `<name>: ok` per test and ends with `8 passed`.
    - `scripts/tests/test_finetune_gen.py` prints `ok <name>` for 6 tests and exits 0. It prints no total, and its `__main__` block sits above `test_hp_weight_targets`, so that test runs only under pytest (pre-existing).
    - `scripts/tests/test_curve.py` prints `<name>: ok` per test and ends with `7 passed` (`test_curve_quick` fine-tunes value_effects through the changed code; a few minutes).

- **Step A-2: next_draw_size capped by retained cards' hand space (A2).**
  - Files:
    - `py/src/features.rs`: `next_draw_size` (lines 1572-1591: the cap and its doc comment); add `HAND_LIMIT` to the import at line 68.
    - `docs/decisions.md`: the spec 7 features line at 2010-2013.
    - `docs/specs/rules-engine-upgrade.md:272`: qualify "At the EndTurn leaf it is exact" with "when the piles hold enough cards".
  - Tests: `py/tests/test_sts.py::test_next_draw_size_counts_retained_cards` and `py/tests/test_content_pack.py::test_known_top_split_counts_retained_cards` (with `RETAIN_PACK`). Both fail before the fix.
  - Size: about 10 changed lines plus about 35 test lines.
  - Acceptance:
    - `bash scripts/dev_sts.sh`, then `py/tests/test_sts.py` ends with `23 passed`, including `test_golden_features_unchanged` and `test_known_top_piles`.
    - `py/tests/test_content_pack.py` ends with `10 passed`.
    - `scripts/tests/test_contract.py` ends with `24 passed`; `scripts/tests/test_net.py` ends with `18 passed` (TRAIN_PIN); `scripts/tests/test_content_selfplay.py` prints `ok` for its 5 tests and exits 0 (ARRAYS_PIN; no total line).
    - `git status --short py/tests/data scripts/tests/data` prints nothing, so no pin was re-recorded.

- **Step A-3: document the opt-in consequences and add a threshold tripwire (A3, A4, A5).**
  - Files:
    - `scripts/tests/test_contract.py`: the comment at 74-75 and the `test_row_kinds_and_piles` docstring at 100-102.
    - `docs/decisions.md`: in the opt-in entry, the A3 consequence after line 2338 and the A4 float16 note in "How a net opts in" (2339-2341).
    - `docs/extending.md`: one clause at 111-115.
    - `scripts/stsnet.py`: a comment at line 215.
    - `py/src/features.rs`: the doc comment on `threshold_rows` (1151-1152).
  - Tests: `py/tests/test_sts.py::test_default_kinds_hide_static_only_powers` (pins the documented behaviour; passes before and after) and `engine/tests/threshold.rs::threshold_powers_have_hook_rows_only` (tripwire; passes today).
  - Size: about 25 changed lines plus about 35 test lines.
  - Acceptance:
    - `cargo test --release -p sts-engine --test threshold` reports `test result: ok. 4 passed`.
    - `bash scripts/dev_sts.sh`, then `py/tests/test_sts.py` ends with `24 passed` (with A-2 in; `23 passed` without it).
    - `scripts/tests/test_contract.py` ends with `24 passed`.

## Pins for this group

**Expected to change:** none of the recorded pins, golden sets or fingerprints. Group A edits none of the 8 fingerprinted engine files (state, cards, monsters, powers, hooks, effects, chance, character); its engine edit is a new test in engine/tests/threshold.rs.

Behaviour changes that have no pin:
- **A1:** fine-tuned nets saved after the fix list the row kinds they trained on. Under (b), a `['triggered']` parent gives `[triggered, threshold, held]`, as main saved them; under (a) it gives `['triggered']`. Encoded-set caches (`cache/warm-<ds>-<k>-<key>.npz`, keyed by layout) rebuild once:
  - under (b), only the replay pool's cache, for a `['triggered']` parent; train and validation keep their keys;
  - under (a), the train and both validation caches; the replay pool keeps its key.
- **A2:** `next_draw_size` and the `next_draw` / `known_later` split change only for states that hold retained cards (Protect, or pack cards with `retain`) or whose turn-start draw exceeds 10 (6+ Brutality stacks).

**Must stay byte-identical:**
- `engine/tests/data/golden.txt` (9,000 games) and `golden_proving.txt`.
- `engine/tests/data/codec_golden.txt`.
- series_check PASS: old nets read neither `next_draw_size` nor the new piles.
- H4: `cargo run --release --example two_turn_phases 100 --check <file>`.
- `py/tests/data/golden_rows.npz`.
- The contract pins (`scripts/tests/data/contract/*`, checked by `scripts/tests/test_contract.py`).
- `scripts/tests/data/lookahead_rows.npz` (monster arrays only, so A2 can't reach it) and `lookahead_off_names.json`.
- TRAIN_PIN (`scripts/tests/test_net.py:364`).
- ARRAYS_PIN (`scripts/tests/test_content_selfplay.py:32`).
- `scripts/tests/data/curriculum_pins.json`.
- The solvedb rules fingerprint.

If an A2 change moves a feature pin, inspect the moved states. A state with 6+ Brutality stacks changes legitimately (k is capped at 10): re-record that pin and state why. Any other moved state means the fix is wrong.

## Decisions for this group

**A1: which row kinds a warm fine-tune trains on and saves.**

Why this is expensive to reverse: every fine-tune saved afterwards carries the choice. Runs made on either side of a switch read different inputs, so they can't be compared or pooled without re-running them, and machine time is the project's bottleneck.

Not part of the choice: either way, `finetune.py` will encode train, validation and replay with exactly the layout it saves, and `widen` will accept named kinds but refuse to drop one. That part is a must-fix and can be built before the decision.

- **(b) Recommended: today's default kinds (triggered, threshold, held) plus any kind the parent opted into.**
  - A fine-tune of a parent saved before threshold and held rows learns and keeps those rows. Such parents are `models/value_effects.pt` (curve.py's warm_effects parent) and the 2026-10-29 champion (`runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt`, parent of the 0059 burst fine-tunes).
  - This is exactly what main's fine-tunes did, in all four sets: the 0059b1 burst arm `runs/2026-11-01-burst8-s1-d4b65b6` saved `[triggered, threshold, held]`.
  - It is also what the threshold-and-held-rows spec intended: "New nets trained after the change save the new kinds and columns" (`docs/specs/threshold-and-held-rows.md:108-109`).
  - The confirmed sentence "stsnet.widen keeps a parent's own row kinds" stays true: widen still keeps them when the caller names none, and finetune's list always contains them.
  - Cost: before training, the widened net reads threshold and held rows its parent never saw. Its first-epoch scores on boss and slime states differ from the parent's, as they did on main.
- **(a) The parent's own kinds.**
  - The widened net starts as its parent on every state (within float tolerance, as `test_widen_identity` checks).
  - But fine-tunes of old parents never learn from Mode Shift, slime-split or Burn rows.
  - New fine-tunes differ in inputs from main's 0059 arms, which confounds any comparison of burst results across the branch landing.
  - Fine-tunes main already made (three kinds) and new ones (one kind) would also sit side by side in the registry under the same config. `curve.py`'s `find_run` (curve.py:205-223) reuses a run by config, parent sha256 and rules version, and none of these records the row kinds.

Recommendation: (b).

## Notes the checker left

The only open choice in group A is A1's (a)/(b): which row kinds a fine-tune names, in one line of finetune.py after line 216, plus the matching docs wording. Everything else in A1 (the widen change, the layout guard, both tests apart from the expected kinds list in the second) can be built now. Outside group A, for the tests group (G): when scripts/tests/test_finetune_gen.py is run directly, test_hp_weight_targets never runs, because the file's `if __name__ == "__main__"` block (lines 122-126) comes before that test's definition (line 129). It runs only under pytest.
