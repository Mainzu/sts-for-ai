# Adaptation burst on generated powers

Status: closed (2026-11-01, read: results doc "Adaptation burst, 3 seeds" and "Burst control"; confirmed by the manager role).

## Outcome

Measure whether a short fine-tune of the champion on games holding a few
new generated powers (an adaptation burst) makes it play those powers
better on the 3-copy generated-power bench, without losing strength on
everything else.

How it moves goal 1: prior art says no fixed net handles a new primitive
zero-shot (`docs/research/unseen-mechanics.md`), so custom content will be
handled by a short burst of training on the new mechanic. This spec builds
the burst and its first measurement. If the burst lifts its own powers'
cells clearly, goal 1's metric becomes "CPU minutes of burst to recover the
lead on new content", and later work (shrink-perturb, which fights to
replay, features for new primitives) has a yardstick. If even a
concentrated burst moves nothing, the nets can't learn these powers from
games at this size, and goal-1 work moves to features first.

Non-goals: picking fights by value error, shrink-perturb, bursts on
official cards, changing `learn.py`'s recipe, two-turn play on the whole
bench.

## Behaviour

- `scripts/finetune.py` gets a second kind of `content`: a dict
  `{"pack": <pack path>, "cards": [<card ids>]}`. Its games are Ironclad
  training decks (`selfplay.train_deck`) with 1-2 of those generated cards
  added to every deck (`selfplay.content_deck`, share 1.0), the pack loaded
  into the engine first. String kinds (`silent_a`, `silent_b`, `both`) keep
  their exact behaviour and dataset config hashes.
- Player for the new games: `player` key, `"net"` (default for dict
  content) plays search with the parent net as evaluator; `"heuristic"`
  plays search with the heuristic, as the Silent kinds do. Why net by
  default: the heuristic can price only ~25% of generated powers, so its
  games might rarely play the new card. String kinds keep the heuristic.
  The dataset config records the player (and the parent's sha256 when the
  net plays).
- Validation: the content's own validation games (game seed + 1) plus
  Ironclad validation games, as now. Replay: the Ironclad pool, as now
  (share 0.5).
- An effects parent needs no widening for generated cards (they bind to
  reserved power slots); `vocab_for` must leave an effects net's
  vocabularies unchanged for dict content.
- A dict content whose card id isn't in the pack fails before any play,
  naming the id.

## The experiment

- Targets: the 8 test-split generated cards with the most fights on
  `data/bench/gen_powers12c3.json` (gc1_082, gc1_050, gc1_095, gc1_111,
  gc1_069, gc1_127, gc1_011, gc1_024; check the order from the bench and
  take the top 8 by generated-set fights, ties by id).
- Burst: champion `runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt`,
  3 seeds (`seed` 1 / 101 / 201, one shared game set), `games` per group
  from the smoke step's timing so one burst's play takes <= ~40 min on 4
  threads (start from 1000), default lr and epochs.
- Read (new `gen_powers_read.py burst` subcommand, or `arms` with a
  `--powers` filter): play the 3 burst nets on the 3-copy bench (`play`),
  then per seed, paired with the champion by fight:
  - **target** = burst minus champion on target cards' generated fights;
  - **other** = the same on the other 35 generated cards' fights;
  - **original** = the same on the original (unswapped) fights;
  - contrast = target - other, mean over seeds, se from per-cell spread.
- Rule (pre-registered): contrast >= +0.04 and >= 2 se, and original >=
  -0.015: the burst works; write the minutes per burst and plan the next
  goal-1 step on it (minutes curve, shrink-perturb, two-turn read of the
  target boss cells). Contrast under +0.02: the burst doesn't teach these
  powers at this size; one rerun at 4x games before calling it. Between:
  report, run 2 more seeds. The other-power gain alone is transfer and is
  reported but not judged.
- MDE: the oracle's se on all 43 powers was 0.009 over 3 seeds; on 8 the
  target se is ~0.009 x sqrt(43/8) ~ 0.02, so +0.04 is about 2 se. A
  concentrated burst should beat the oracle's diluted +0.013 by much more
  if it works at all.

## Fits with

- `test_warm_start.py`: Silent fine-tunes unchanged (their dataset config
  dicts and hashes pinned by a new test written in step 1, passing on the
  unchanged code).
- `test_gen_powers_read.py`: `arms` output unchanged on its fixture.
- `selfplay.content_deck` / `load_content`: used, not changed.
- Registry: fine-tune runs stay registry runs with `parent` in run.json.

## When in doubt

Prefer reusing `finetune.py`'s and `learn.py`'s existing pieces over new
machinery.

## Scope

May change: `scripts/finetune.py`, `scripts/analysis/gen_powers_read.py`,
their tests, new `configs/burst-*.json`, the README's fine-tune lines,
results doc and decisions. Off limits: Rust engine, `learn.py`, `selfplay.py`
behaviour, feature layouts, the bench files.

## Decisions taken

- Net player by default for generated content (above).
- Contrast against other generated powers in the same nets, not a separate
  "fine-tune without content" control arm: same nets, no extra CPU.
- One-turn play for the read; two-turn only on target boss cells if the
  rule passes (decisions "Depth repairs unseen powers: the check holds").

## Outside assumptions

- Fine-tuning from a parent with replay keeps old strength (warm-start
  spec measured it on Silent). Checked here by the original-fight term.

## Verification

1. `test_finetune_gen.py::test_string_kinds_unchanged`: the Silent kinds'
   dataset config dicts equal pinned literals (passes before the change).
2. `test_finetune_gen.py::test_gen_decks`: 50 decks of dict content with 2
   cards each hold 1-2 of the `gen:` cards on top of a train deck.
3. `test_finetune_gen.py::test_unknown_card`: a missing id raises before
   play, naming it.
4. `test_finetune_gen.py::test_effects_vocab_unchanged`: `vocab_for` on an
   effects parent's meta with dict content returns its vocabularies as they
   were.
5. `test_gen_powers_read.py::test_burst_contrast`: on a small fixture with
   known per-fight results, target / other / original and contrast come
   out as hand-computed.
6. End to end: a smoke burst (`games` 20, `pool` 200, `n_val` 20) on 2
   target cards finishes and saves a model that `gen_powers_read.py play`
   accepts.

Don't guard: pack files edited between runs (packs are hashed already),
non-effects parents with dict content (raise if seen, no support).

## Build steps

1. Tests 1 and 4 (pins on unchanged code); then dict content in
   `finetune.py` (`games` with the deck function and player; card check),
   tests 2-3 pass.
2. Smoke run (check 6), time it per game; pick `games` so a burst's play
   is <= ~40 min on 4 threads; write `configs/burst8-s1/s101/s201.json`.
3. `burst` read (test 5).
4. **Long run:** queue the 3 bursts (jobs.py, one job each; the first
   plays the games, the others reuse them, so queue s1 first), then
   `gen_powers_read.py play` on the 3-copy bench for the 3 nets, then the
   read. Steps 1-3 don't need it.

Build plan: 3 build steps + queued runs, one fork, on Opus. No stop
points expected.

## Amendment 1 (build, 2026-11-01)

- Setups: generated content's games, its Ironclad validation games and the
  replay pool use varied setups (`varied_deck` + 1-2 cards, `varied_hp`; a
  new string kind `"varied"`), not `train_deck` at full HP: the champion was
  trained on varied setups, and full-HP train-deck games are ~97% wins, so
  replaying them would shift its training distribution. String kinds are
  unchanged.
- Targets (top 8 by generated-set fights, ties by id): gc1_082, gc1_050,
  gc1_095, gc1_111, gc1_011, gc1_019, gc1_024, gc1_069 (1044 fights, 87
  cells; hallway 768, elite 204, boss 72).
- Timing (smoke, 4 threads beside two learn jobs): net play ~150 games/s;
  6000 varied heuristic pool games 38 s; ~3 s per epoch on 10k states,
  early stop by epoch 5. `games` 4000 per group (12k games, ~2,250 per
  target card, ~3x the oracle's round-0 exposure per power), pool 10000:
  one burst ~10-15 min.
- `registry.write_dataset` read `config["content"]["hash"]` for any
  content, so string kinds crashed (test_warm_start's tiny fine-tune failed
  on main since registry-lite); fixed to dict content only.
