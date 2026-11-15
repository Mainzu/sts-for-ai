# Registry-lite: generated power mechanics at runtime

Status: closed (2026-10-31, built and in use; merged 0e0046a; decisions "Registry-lite spec confirmed"). Reserved generated slots in use today (engine/src/registry.rs, now 40 card / 24 power slots).

## Why (goal 1)

Goal 1 is an AI that plays well on content it has never seen. Today the
held-out gap sits in *power mechanics*, chiefly Demon Form (turn start ->
+Strength: -0.172 on boss cells, 39 cells), not in unseen cards built from
known parts (+0.007 without Demon Form). Official Ironclad content has
about 14 hook powers, so neither training nor testing can cover the space
of trigger x condition x effect x lifetime combinations, and no held-out
set is big enough to read generalisation by mechanic. This spec lets
generated powers (and the power cards that grant them) exist at runtime
without editing the Rust tables. **How we'll know it moved goal 1:** its
end-to-end check measures the champion against the heuristic on decks
holding generated power cards whose (trigger, effect) pairing no training
power has; a later spec trains with 0 / 16 / 128 generated powers and
reads that lead (and the official only-c9 / Demon Form cells). If the
champion already matches the heuristic on generated powers, the official
gap is Demon-Form-specific and the training arms shrink (review's first
check).

## Outcome

A content pack (JSON) of generated powers and power cards loads into the
engine at runtime; decks name its cards; combats, search, the heuristic,
the effects-mode encoder and self-play all handle them like official
content; with no pack loaded every golden game, pin and fingerprint is
bit-identical.

Non-goals: monster content, generated attacks/skills (only power cards in
the lite version), new atoms (effects, triggers, conditions), the full
`runtime-registry` (spec 10: all content as files), the exact solver and
solved DB on generated content, ids-mode support beyond "unknown", the
training arms themselves (next spec, configs only).

## Behavior

**Content pack.** `{"version": 1, "powers": [...], "cards": [...]}`.
A power: `{"id": "gp017", "hooks": [{"trigger": ..., "condition": ...,
"effects": [...]}], "debuff": false}` using only existing atoms
(`Trigger`, `Condition`, `Effect` from hooks.rs / effects.rs, serialised
by variant name with fields). A card: `{"id": "gc017", "cost": 1,
"type": "Power", "effects": [{"Apply": {"power": "gp017", "amount": 2,
"target": "Me"}}], "exhaust": false, "ethereal": false}`. Decks name a
generated card as `"gen:gc017"`. Loading is append-only per process
(`sts.load_content(path or str) -> content hash`); a second load of an id
already present with a different definition is an error; definitions are
leaked to `'static` and never change after load.

**Slots, bound per combat.** The engine gets `G_POWER = 8` reserved power
kinds (`Gen0..Gen7`, after today's 21, so 29 of the 32 the just-applied
mask allows) and `G_CARD = 8` reserved card kinds (16 ids with the `+`
twin, which plays as the base). `Combat::new` collects the deck's
generated cards and the generated powers they grant (transitively), binds
each to a slot in order of first appearance, and stores the binding
(`[u16; 8]` registry indices for each, `u16::MAX` = free) in
`CombatState`. Over 8 of either is an error naming the deck. The
dispatcher, `hooks(p)`, card `def(c)`, `is_debuff`, the heuristic's
`hook_rates` and `bound.rs` look a generated slot up through the binding.
A combat's binding never changes, so search, clones and chance children
share it. Different combats (and threads) can bind different powers to
the same slot: the registry is read-only after load, so no lock is taken
in play.

**Not supported with a binding (errors, not silent):** `codec` encode
(so solved-DB writes and the exact solver refuse such states), ids-mode
features (generated slots map to the `unknown` power/card column, which
is what ids mode does today for unseen content; allowed, but warned
once). Datasets record setup (deck names) and actions, plus the pack's
content hash in their meta; replay refuses a dataset whose pack hash isn't
loaded.

**Features (effects mode).** A generated power's hooks become rows exactly
as an official power's do (`power_rows`, `granted_rows`), and a generated
card's vector is computed from its def (cached per registry index). No new
columns: `TargetHas` conditions and every vocabulary list keep iterating
official powers and cards only, so no column is added and every pin stays.
Generated powers may not be `TargetHas` targets (generator rule).

**Generator** (`scripts/gen_content.py --seed S --powers N --out pack.json`):
- Triggers: `OwnerTurnStart`, `OwnerTurnEnd`, `CardPlayed{by: Owner}`,
  `CardPlayed{by: Opponent}`, `OwnerLostHp{Card|Attack|Any}`.
- Conditions: `Always` (most), `CardType(Attack|Skill|Power)` on
  `CardPlayed` triggers.
- Effects (1-2 per hook): Block, Draw, GainEnergy, LoseHp (self),
  PlainDamage {AllOpponents}, Damage {AllOpponents},
  Apply {Strength | Dexterity to Me; Vulnerable | Weak to AllOpponents},
  with per-stack amounts drawn from the official per-stack range of that
  effect (+-1 noise).
- Lifetime (one of four, as `generated-cards.md`): permanent; this turn
  (`OwnerTurnEnd -> RemoveSelf` sibling hook); used up (`RemoveSelf` in the
  hook); wearing down (`ReduceSelf(1)`).
- Validity: no hook can fire itself (`OwnerLostHp` with a self `LoseHp`;
  `CardPlayed` effects can't play cards, so they're safe); `Draw` and
  `GainEnergy` on `CardPlayed` capped at 1 per stack (no infinite turns
  past the turn limit); stacks granted 1-3.
- Budget: each power card gets cost 1-3 and an amount such that its
  heuristic `hook_rates` value per energy lies within the official power
  cards' range (min..max of Inflame, Metallicize, Combust, Brutality,
  Rupture, Demon Form, Flex... measured in step 4), so nothing is absurd
  either way.
- **Split by mechanic.** Each power's key is its set of (trigger, effect
  kind) pairs. Keys are hashed into train / test (25% test); a test power
  shares no key pair with any train power *or* any official training
  power (so turn start -> +Strength is test, like Demon Form). The pack
  records each power's split.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Engine play, no pack | Bit-identical games | `engine/tests/golden.rs` (golden.txt unchanged), `codec.rs` golden, all engine tests |
| Rules fingerprint / rules version | Unchanged with no pack; reserved slots excluded from `content_tables` | `solvedb/tests/fingerprint.rs` (value unchanged), `scripts/registry.py` rules version unchanged (golden.txt) |
| Feature encoder, both modes | Identical batches and columns | `py/tests/test_sts.py` golden_rows, `test_contract.py` pins, `test_lookahead.py`, `test_threshold*` |
| Saved nets | Load and score identically | `test_contract.py` tiny-net outputs, `test_net.py` TRAIN_PIN |
| Heuristic | Same values on official content | golden games (heuristic plays them? if not, `heuristic` unit tests) plus a new test: hook_rates of a generated copy of Demon Form equals Demon Form's |
| Search / threads | A bound combat searches like an unbound one | new test: a generated copy of Demon Form (same hooks) plays the same game as Demon Form, seed for seed, in one-turn and two-turn search |
| Self-play / learn.py / pools | Unchanged without a `content` key | `test_setups`, `test_net` pool disjointness |
| Performance | Play within 3% of main with no pack | `scripts/bench.py` timing on tight2 (one-turn, heuristic) |

## When in doubt

Prefer bit-identical old behaviour over generality; prefer an error over a
silent fallback for generated content.

## Scope

May change: `engine/src` (new `registry.rs`; powers.rs, cards.rs, hooks.rs,
state.rs, heuristic.rs, bound.rs, codec.rs refusal), `py/src` (load API,
deck names, features lookup), `solvedb/src/fingerprint.rs` (exclude
reserved slots only), `scripts/gen_content.py`, `scripts/selfplay.py`
pools (`content` option), `scripts/learn.py` (config key `content`,
`content_share`), new bench set and read script, tests, README, docs.
Formats: datasets' meta gains `content_hash`; a new pack format.

Off limits: existing atoms' semantics, existing column names or order,
the codec format for unbound states, `golden.txt`, saved nets, `db/`,
monster content.

## Decisions taken (also in docs/decisions.md, provisional)

- Per-combat binding of 8 + 8 reserved slots (over: widening ids to u16
  with sorted inline lists, spec 10's plan, which re-pins everything and
  slows clones; over: one global slot table per process, which caps a
  training run at 11 generated powers).
- Power cards only; grants to Me only. Attacks/skills and debuffs on
  monsters later.
- No new feature columns; ids mode maps generated content to unknown.
- Split by (trigger, effect-kind) pair, 25% test, official pairs count as
  train.

## Outside assumptions

None beyond the code; the budget range comes from our own heuristic.

## Verification

Tests first (step 1, pass on unchanged code where they test old
behaviour): golden, codec, fingerprint value, contract pins (already
exist). New:
- `engine/tests/registry.rs`: load a pack with a copy of Demon Form
  (`gp_df`) and a card `gen:gc_df` (cost 3, grants 1); a combat with it in
  place of Demon Form plays the identical game (actions, HP, turns) for 20
  seeds x 3 encounters with the heuristic; nine generated cards in one
  deck is an error; redefining an id is an error; encode of a bound state
  errors.
- `py/tests/test_registry.py`: the same copy through Python, effects-mode
  rows of the copy equal Demon Form's rows; ids mode maps it to unknown;
  a dataset with a pack hash refuses replay without the pack.
- `scripts/tests/test_gen_content.py`: seeded determinism; validity
  rules; no test key pair in train or official training powers; every
  card's budget in range; 200 powers x 20 heuristic fights each, stall
  rate < 1%.

End to end (step 6, long run): `data/bench/gen_powers.json`: the 300
held-out tight2 cells whose deck holds a check-9 power card, with that
card swapped for a generated *test* power card of the same cost (and the
original kept as a paired control set); champion (r2 s1) vs heuristic,
4 seeds per cell, paired lead on generated vs on the original cards, by
fight type. MDE ~0.04.

## Don't guard

Generated monster powers, upgrades of generated cards, pack versioning
beyond `version: 1`, more than 8 slots, performance of bound combats.

## Build steps

0. Inventory every reader of `Power::ALL`, `NUM_POWERS`, `CardId::all()`,
   `NUM_CARDS`, `hooks(`, `def(` (about 40 sites) and note for each:
   official-only or must see slots. Check: the list in this file's
   addendum.
1. Tests that pin today (golden, codec, fingerprint, contract) run green
   on main; write the new tests (they fail). Check: suites green.
2. Engine: `registry.rs` (pack parse, append-only table), reserved slots,
   `Binding` in `CombatState`, lookups through it in dispatch, `def`,
   `is_debuff`, heuristic, bound; codec refusal. Check: golden.txt
   unchanged, engine tests green, `registry.rs` tests green, timing within
   3%.
3. Python: `sts.load_content`, `gen:` deck names, features lookups and
   per-index card-vector cache, ids-mode unknown, fingerprint excludes
   slots. Check: test_sts, test_contract, test_lookahead, threshold tests,
   test_registry green; fingerprint value unchanged.
4. `gen_content.py` with validity, budget and split; measure the official
   budget range. Check: test_gen_content green.
5. `selfplay.py` / `learn.py` key `content` (+ `content_share`, the share
   of decks that hold 1-2 generated train cards); dataset meta hash.
   Check: test_setups, test_net green; a 200-game smoke run.
6. **Long run (~1 h):** bench set + read script; champion vs heuristic.
   Read and write results ("Generated powers, first check").
Then: training-arms spec (0 / 16 / 128 generated train powers, 3 seeds).

Build plan: 7 steps, forks, on Opus. Build in a worktree
with its own venv (the job queue holds main's `sts`). Stop point: step 2
if the binding can't be threaded through `hooks(` without a measurable
slowdown; then decide between a thread-local binding and
widening.

## Addendum: step 0 inventory (2026-10-31)

Recommended shape for step 2: keep today's constants as the *official*
counts and add the reserved slots after them, so every "official-only"
reader keeps its range unchanged:
`NUM_OFFICIAL_POWERS = 21`, `Power::ALL` (official, unchanged),
`Power::GEN: [Power; 8]`, `NUM_POWERS = 29` (state, mask, codec);
`NUM_OFFICIAL_CARDS = 108` (the `CARDS` table, `CardId::all()`),
`NUM_CARDS = 124` (pile counts). Readers that must see slots iterate
`Power::ALL.iter().chain(Power::GEN)` (or an `all_with_slots()`), and look
a slot's hooks / def up through the combat's binding.

**Fingerprint caveat (contradiction with the spec's Fits-with row):**
`solvedb/src/fingerprint.rs` `RULE_FILES` hashes the source text of
state.rs, cards.rs, powers.rs, hooks.rs, effects.rs (comments and
whitespace stripped), so *any* code change step 2 makes there changes the
fingerprint value, slots or not. What can stay identical is
`content_tables()` (official names only) and the rules version
(golden.txt). The solved DB is already behind the current fingerprint
(2.43M rows under the pre-bosses value), so nothing
live depends on it; step 2 should check `content_tables()` unchanged and
accept a new fingerprint value, and record that in decisions.md.

| Site | What it does | Class |
|---|---|---|
| engine/src/powers.rs:91 `NUM_POWERS` | size of `Powers.amounts`, mask | must see slots (29) |
| engine/src/powers.rs:98 `amounts: [i16; NUM_POWERS]` | power storage | must see slots |
| engine/src/powers.rs:133 `end_of_round` over `Power::ALL` | just-applied clear, duration tick | must see slots (just-applied clear); `is_duration_debuff` false for slots |
| engine/src/powers.rs:79/84 `is_duration_debuff`, `is_debuff` | Artifact blocks debuffs | slots: `is_debuff` from the pack's `debuff` flag via binding (grants to Me only, so effectively false in lite) |
| engine/src/hooks.rs:127 `hooks(p)` | hook table | must see slots via binding (new `hooks_in(p, &binding)` or state method) |
| engine/src/state.rs:583/588 `run_hooks_with` over `Power::ALL`, `hooks(p)` | dispatch | must see slots via binding |
| engine/src/state.rs:931 Artifact `is_debuff` | | via binding |
| engine/src/state.rs:939 just-applied skip rule | `is_duration_debuff && src_monster`, Ritual | slots: false (no change) |
| engine/src/state.rs:29/34 `Pile.counts: [u8; NUM_CARDS]` | piles | must see slots (124) |
| engine/src/state.rs:201,260,283,303,325,328,341,394,422,475,485,618,715,718 `card.def()` | play, cost, playability, innate, turn-end, ethereal, CardType condition, strikes | must see slots via binding (state has it) |
| engine/src/chance.rs:119 `card.def().effect_at` | chance resolution of a card in play | via binding |
| engine/src/agent.rs:210,212 `card.def().cost/.ty` | agent option facts | via binding |
| engine/src/bound.rs:52 `card.def()`, :60 `hooks(p)`, :75 `Power::ALL` | heal bound | via binding (a generated power never heals in lite: no heal atom) |
| engine/src/heuristic.rs:71/73 `hook_rates` over `Power::ALL`, `hooks(p)` | heuristic power rates | must see slots via binding |
| engine/src/heuristic.rs:128,135,249 `def()` | heuristic card values | via binding |
| engine/src/cards.rs:141 `NUM_CARDS` | table size / pile size | split: `CARDS` table official (108); piles 124 |
| engine/src/cards.rs:470 `CardId::def` | static lookup | official ids only; slot ids need the binding (panic on a slot id without one) |
| engine/src/cards.rs:479 `from_name` | name lookup | official-only; `gen:` names resolved by the registry at `Combat::new` |
| engine/src/cards.rs:484 `CardId::all()` | every card id | official-only |
| engine/src/cards.rs:510 `class_cards`, :515 `held_out_cards` | pools | official-only |
| engine/src/codec.rs:231 card decode `< NUM_CARDS`, :253-256 power mask | codec | official-only on decode (keep the official bound so the format and codec golden stay); encode refuses a bound state |
| engine/src/monsters.rs, threshold.rs, chance.rs:91/234, heuristic.rs:220/312 `m.def()` | monster defs | untouched (monsters out of scope) |
| py/src/features.rs:44/49 imports, :261/264 `card_index`/`power_index` arrays | id→column | official-only columns; slots map to the `unknown` column (array sized to the new NUM_*) |
| py/src/features.rs:101 `is_hook_power` (`hooks(p)`) | row vs dimension | must see slots via binding |
| py/src/features.rs:185 `TargetHas(<Power::ALL>)` condition vocab | column names | official-only (no new columns) |
| py/src/features.rs:284-297 vocab defaults from `CardId::all()` / `Power::ALL` | vocab | official-only |
| py/src/features.rs:328-332 precomputed `card_vecs`/`card_rows`/`card_held` per `CardId::all()` | card encodings | official precomputed; slot cards computed per registry index (cache) |
| py/src/features.rs:540 `powers()` dims over `Power::ALL` | modifier dims (effects), id dims (ids) | effects: official-only (slots aren't modifiers); ids: slots add to `unknown` |
| py/src/features.rs:599,698,719,745 `card.def()` | card vectors/rows | via binding |
| py/src/features.rs:662 `power_rows` `hooks(p)` | power rows | via binding |
| py/src/features.rs:956 `entity_power_rows` over `Power::ALL` | entity rows | must see slots |
| py/src/lib.rs:96 `power(name)` | name → Power | official-only |
| py/src/lib.rs:1407 `all_card_names`, :1412 `deck_card_names`, :1418 `class_card_names`, :1440 `power_names`, :1446 `hook_power_names` | Python name lists | official-only (callers: selfplay TRAIN_POOL/KNOWN_*, bench_sets pools, granting, golden.py, test_contract, test_sts dims) |
| py/src/render.rs:19 `Power::ALL` | debug render | should see slots (show the registry id) |
| solvedb/src/fingerprint.rs:124/128 `content_tables` | fingerprint | official-only (value of `content_tables()` unchanged); see caveat |

## Addendum: step 4 (generator as built)

- Budget proxy: `hook_rates` isn't reachable from Python, so the price is
  the heuristic's value change (`Features.encode(heuristic=True)`) from
  playing a cost-0 copy of the card, mean over 24 turn-1 states (6
  encounters x HP 30/60 x 2 seeds, deck Strike x2, Defend, Bash + the card),
  divided by the cost. Official range, priced the same way: Demon Form
  0.092, Inflame 0.141, Metallicize 0.210, Combust 0.253 per energy;
  Rupture 0 (not priced in these states), Brutality negative at cost 0.
  So lo = 0.092, hi = 0.253. The heuristic prices only the patterns
  `hook_rates` reads: in a 200-power pack about 25% are priced; the rest
  (gain within 0.01 of 0, or negative with a draw/energy effect) get cost
  1-2 and `value_per_energy: null`. Per-stack amounts stay inside the
  official per-stack ranges either way.
- Triggers: `CardPlayed{by: Opponent}` is left out: a player-owned power
  with it never fires (monsters don't play cards). Draw only at turn start
  and on the owner's card plays, energy only at turn start (energy on card
  plays with draw makes an endless turn); no Draw/energy on HP-loss hooks.
- "This turn" is not drawn for powers whose hooks are all turn-start (it
  would end before firing).
- Split: 48 allowed pairs, 13 test (seed-independent hash, 1 in 4 of the
  non-official pairs, plus turn start -> +Strength); a power's split is
  drawn first (25% test) and all its pairs come from that side.
- Check: 200 powers x 20 heuristic fights (tight2 train specs, starter +
  the card): 0 stalls, no errors, the card played in 42% of fights, 3 s.
