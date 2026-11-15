# Rules engine upgrade (umbrella)

Status: umbrella (2026-10-26, specs 1, 2, 4-9 built 2026-10-30..11-02; spec 10 is runtime-registry.md (stages 1-4 built 2026-11-06); spec 3 entity-shape not built).

This file is the **umbrella**: the
model, the contract and the checks. The build is a **series of specs**,
each finished with `/spec` into its own file and built and tested on its
own (see "The series"). `generated-cards` depends on the series.
Reviewed against the code 2026-10-26: the must-fix
gaps are folded in below; the rest are open questions at the end.

## The series

Dependency order. Each spec has its own proving content, golden rule and
net impact; "fingerprint" says whether it retires the solver database.

| # | Spec | Changes | Proving content | Golden | Nets | Fingerprint |
|---|---|---|---|---|---|---|
| 1 | `contract` (built 2026-10-30, branch `contract`) | named columns, schema version, per-name normaliser, exact reload by gather, row kinds and named pile slots in the vocabulary, keyed specs with defaults, reserved `Choose` / `Done` / `UsePotion` record encodings, a play encoding that carries per-copy overrides | a net saved under the contract reloads bit-identical (torch and Rust) after a column reorder and after an append; `scripts/convert_net.py` converts a known pre-contract layout into a contract net, checked bit-identical on the curriculum's final net; records round-trip | identical | guarantee starts here | no |
| – | `warm-start` | scripts only (own draft) | Silent as built, baseline curve | – | – | no |
| 2 | `amount-expressions` (built 2026-11-02, branch `engine-next`; decisions "Amount expressions built") | `base + k × quantity`, card tags; Body Slam, Heavy Blade, Perfected Strike re-expressed; X-cost keyword | the re-expressed cards, an X-cost card | identical | load as-is (the odd-primitive columns stay, computed from the expression, so old nets stay exact) | yes |
| 3 | `entity-shape` (moved after spec 5; decisions "Static modifiers spec confirmed and built") | one feature path for player, monsters, cards (scalars, rows, position) | none new | identical | load as-is (batch format only: `stsnet.py` and `py/src/net.rs` both read it, through an adapter to an old net's player / monster / card paths; a shared entity path in the net is a later training experiment, not part of the series) | no |
| 4 | `static-modifiers` (built 2026-11-02, branch `engine-next`; same decision) | Strength, Dexterity, Vulnerable, Weak, Frail as rows; conditional statics; debuff countdowns as `RoundEnd` hooks; the damage pipeline's order | Accuracy; a Red Skull-style conditional | identical | load as-is (modifier dimensions stay beside the new rows, which are a row kind old nets don't see) | yes |
| 5 | `replacement-hooks` (built 2026-11-02, branch `engine-next`; decisions "Replacement hooks spec confirmed and built") | prevention / replacement kind (cancel an event, or change its amount: add, multiply, cap); Artifact rewritten; damage events carry their source; `OwnerAttacked` trigger, attacker target | Wraith Form (Intangible), Caltrops | identical | load as-is (Artifact keeps its dimension; replacement rows are a row kind old nets don't see) | yes |
| 6 | `decision-points` (built 2026-11-02, branch `engine-next`; decisions "Decision points spec confirmed and built") | `Choose` / `Done`, in-card decision pause (always expanded), engine-owned kinds: discard from hand, pick from the discard pile; replaying the card in play | Survivor; Burst (the next Skill is played again) | identical (the default Silent starter keeps the Defend stand-in; the real starter is a named variant) | load as-is | yes |
|   | *Multi-pick cost:* the transposition cache does not bound picks (DiscardToTop and HandToTop keep order; ReturnFromDiscard ranges over the discard pile), and the draw after is a divergent leaf. Past the node cap a pick is still expanded (never a leaf) but only along its first option (draw-knowledge item 4). A large draw *before* a pick in the same card is still a leaf; such states carry the pending decision in the features (see Decision points). | | | | |
| 7 | `known-top` (built 2026-11-02, branch `engine-next`; decisions "Known top spec confirmed and built") | the prefix, deterministic prefix draws, floaters (a card shuffled in under a known top); Scry's reveal node reserved | Headbutt | identical (prefix empty for existing content) | load as-is (two new named piles; a net without them sees their cards in the draw pile, today's view) | yes |
|   | *Encoding:* the prefix is bucketed by draw turn, not summed with positions: a **next draw** pile (the first k cards, k = next turn's draw size) and a **known later** pile, index kept as a scalar for boundary ties. Order inside a hand is irrelevant, so Headbutt's one card and Frozen Eye's twenty encode the same way, and the next hand sits where the EndTurn leaf needs it. | | | | |
| 8 | `per-copy-overrides` (built 2026-11-02 after spec 9, branch `engine-next`; decisions "Per-copy overrides spec confirmed and built") | (kind, overrides) pile keys with lifetimes and flags; the state representation for open-ended content | Rampage; a self-Retain card | identical | load as-is (Rampage's growth is an effect row read through the damage number; Retain a new flag column) | yes |
| 9 | `monster-patterns` (built 2026-11-02 before spec 8, branch `engine-next`; decisions "Monster patterns spec confirmed and built") | pattern rows, reactions as hooks, `Spawn`; migrate the 15 encounters | the roster | identical: patterns make today's random calls in today's order, by construction (see Monsters); no fallback | load as-is (pattern rows are a row kind old nets don't see) | yes |
| 10 | `runtime-registry` (stage 1 `pack-every-atom` built 2026-11-02; stages 2-5 drafted in `runtime-registry.md`, owner's call) | content from data files at startup, read-only after; the fingerprint and the registry's rules version hash the loaded content | every card, power and monster as a file; tier A is data only | identical | none | yes (content leaves the hashed Rust files) |

Deferred as additive atoms with no format impact: counters in rows (no
in-scope power has one), death replacement and the downed state,
`RerollIntent`, `EndPlayerTurn`, facing, Scry's reveal node. Deferred, not
claimed additive: decisions a power's hook raises (Well-Laid Plans'
turn-end Retain choice), which sit inside EndTurn's resolution, a search
leaf.

**No spec in the series trains a net.** Each spec's net check: every net
saved under the contract (spec 1 or later; the first are warm-start's
Silent baseline nets) loads, and on a fixed state set (the golden states
and the bench's decisions) gives bit-identical outputs, per forward pass
(torch, Rust), on every state whose encoding for that net the spec
doesn't change. With row kinds and named piles in the vocabulary (the
contract), that is every state without content the spec adds or
re-expresses. Pre-contract nets are outside the guarantee; the ones
with a known layout are converted into it once.
The net-side proof is one `warm-start` learning-curve run (a fine-tune,
not a retrain) once the proving cards exist, after spec 8; monster
pattern rows get theirs when a hidden-intent or new-monster case needs it.

Order notes: specs 6-9 change the state shape. The solver database is
retired at every "yes" in the fingerprint column; nothing in the series
reads it, so it refills once from registry games after the series, and
the bench's exact puzzle values stay valid while existing content plays
identically. **Recorded games replay from setup and actions** (registry
datasets, which the registry refuses once its rules version, the golden
hash, changes; the bench's decisions, reference and puzzles; the round-0
pools; warm-start's replay mixing), so they stay usable only while the
golden games are identical: that is why spec 6 keeps the Silent stand-in
starter and spec 9 keeps today's random calls.
The registry is last because every earlier spec defines a row format the
files must express. Contract rule: **removing a column is allowed** (old
nets read zeros for it and degrade only on the affected content); only a
rename or a meaning change is a break. Spec 2 doesn't use it: the
odd-primitive columns stay, computed from the expression.

## Outcome

Every way StS changes its own rules is expressible as data the net can read,
and cards and powers can be added at runtime, so new content (official,
hand-made or generated) needs no new engine logic. A **new mechanic** (a
new effect, trigger, condition, keyword or target) is an engine update plus
a vocabulary append, after which every existing net still loads and the
cost of teaching it the mechanic is measured (`warm-start`).

**The engine takes data only. No scripting.** Content is rows the engine
interprets; the engine's vocabulary of atoms is closed and small, and every
control-flow shape (when, if, repeat, choose) is an atom or a decision-point
kind the engine owns.

## The model (see the rules-model map in `docs/concept.md`)

Three kinds of ability, each with a lifetime:
- **Triggered** ("when X, do Y"): today's hooks.
- **Static / continuous** ("while it exists, change this number"): today's
  built-in modifiers (Strength, Dexterity, Vulnerable, Weak, Frail), a fixed
  list the net can't generalise across.
- **Replacement / prevention** ("if X would happen, do Y instead"): missing.

## Gaps to close

- **Replacement and prevention hooks:** modify or cancel an event before it
  applies (HP loss, damage, a debuff being applied, a card being exhausted);
  a modification adds to, multiplies or caps the amount. Content to prove
  it: Intangible (Wraith Form: damage, and per the wiki HP loss, becomes at
  most 1, a cap); Artifact rewritten as one.
- **Card replay:** Burst and Double Tap play the next card again (the game
  queues a copy): a triggered replay of the card in play, not a
  replacement. Its rules come from the game's code at spec 6's interview:
  energy, `CardPlayed` hooks, the cards-played count FTL reads, a target
  that died, a decision inside the replayed card.
- **A second number per power:** a counter or charges besides the stacks,
  with conditions that read it and effects that change it. Content: a
  Pen Nib-style counter; Panache if still wanted. **Never a bare number
  to the net:** a general-purpose count means something different per
  power, which the net could only learn per power kind. The counter is
  encoded inside the row that reads it, as (current value, threshold,
  effects), so the net reads progress toward that row firing ("7 of 10
  attacks, then double damage"), the way condition parameters already
  work. Cards need none of this: a card's own numbers describe it.
- **Per-copy card state as overrides of the card's own numbers** (the
  game's per-instance base damage, base block, magic number and cost):
  Rampage and Glass Knife change their damage, Streamline and Madness
  their cost, Genetic Algorithm its block, Ritual Dagger its damage.
  Not a count of plays: Armaments upgrading a Rampage mid-fight changes
  the increment and keeps the accumulated damage. Cards keep no identity:
  the pile key becomes (card kind, overrides), overrides usually empty, so
  two Rampages at the same damage are one key and the by-action rule,
  `Eq`, `Hash`, dedup and the codec (counts per key) keep working. The
  net needs no new column: a card's vector already carries its damage,
  block and cost, so a Rampage at 23 damage simply reads 23. Rampage's
  growth (a new effect scalar) and Retain (a new flag column) are
  additive: an old net drops both and reads Rampage through its damage.
- **Static modifiers as data:** "while it exists, multiply or add to a
  quantity (damage dealt, damage taken, block gained)" with an optional
  condition, so Strength, Vulnerable and the rest become rows the net can
  generalise across, and conditional statics work. Content: Accuracy (a
  static on a card class: Shivs), a Red Skull-style "+3 Strength while
  HP ≤ 50%". Rows carry their stage in the damage pipeline (format
  decisions below).
- **Attacked trigger and the attacker target:** Caltrops (Thorns) fires on
  every attack hit, blocked or not (the game's `onAttacked`), but
  `OwnerLostHp` fires only on unblocked HP loss the owner survives, and no
  hook event carries who caused it. So damage events carry their source,
  with a new trigger `OwnerAttacked` and the attacker as a target (spec 5).
- **Keywords:** Retain; X-cost (spend all current energy, the amount read
  by the card's effects: a card property plus an effect source, not a
  decision).
- **Debuff countdowns as hooks:** Vulnerable, Weak and Frail's countdown
  written as `ReduceSelf(1)` on a new `RoundEnd` trigger (after every
  monster's turn-end hooks, where `end_of_round` runs today), so a new
  countdown debuff needs no engine code. Not the owner's turn end: the
  player's fires before the monsters act, so player debuffs would expire a
  round early. The `just_applied` skip (a debuff a monster applies skips
  the round it lands in) becomes data too: a condition the countdown row
  checks, cleared at `RoundEnd` after the countdowns.
- **Runtime registry:** cards and powers beyond the static tables,
  registered once at startup and read-only after (`Clone` stays cheap).
  Reopens the "static Rust tables" decision for both. It needs a state
  representation that isn't sized by compile-time tables, and versions
  that see data files (format decisions below).

## Proving set: Silent, tier B

The official cards to add, each needing exactly one new atom (exact list to
be reviewed against the wiki at the interview):

| Card | Atom it proves |
|---|---|
| Wraith Form | replacement that caps an amount (Intangible: damage, and per the wiki HP loss, becomes at most 1) |
| Burst | card replay (the next Skill is played again) |
| Accuracy | static modifier on a card class |
| Caltrops | `OwnerAttacked` trigger (every attack hit, blocked or not), the attacker as source and target |
| a self-Retain card (e.g. Watcher's Protect) | keyword. Not Well-Laid Plans: its Retain is a choice at turn end raised by a power, a decision the series doesn't build |
| Survivor (in the game's Silent starter; the default starter keeps the Defend stand-in) | `Choose` decision point, discard from hand |
| Headbutt (Ironclad common, out today) | `Choose` from the discard pile; the known top prefix |
| Rampage (Ironclad, out today) | per-copy card state: the card's own damage changes in play |

Silent already has bench halves, a starter and datasets, so each card lands
in a learning curve (`warm-start`): "the net never saw Intangible; how many
games until it values Wraith Form?"

## Decision points

Today `Action = Play { card, target } | EndTurn`. The game has more kinds of
player decision than that, and their formats sit in game records, the
bench's decision files and the solver database, so the shape is fixed here
even where the content is out of scope.

- **A choice is a decision between changes to apply.** Every option, play
  or choose, is "apply these rows", and the player picks among the
  resulting states (the afterstate principle). A decision point is a
  **descriptor** (what for: play, discard, exhaust, upgrade, copy, move to
  the draw pile's top, use) and a list of **candidates**, each a label and
  the rows it applies. Data generates the candidates from a **source**
  (hand, draw pile, discard pile, exhaust pile, potion slots, or an inline
  list of row sets for Wish-, Discovery- and potion-card-style choices)
  with an optional **filter**, reusing the existing conditions (card type,
  cost, upgradable, not the card itself). Search, solver and bench already
  do "apply, then score", so `Choose` adds nothing to them.
- **What can be picked, in the game:** a card in hand (Survivor, Prepared,
  True Grit+, Armaments, Dual Wield, Warcry); a card in the discard pile
  (Hologram, Headbutt); in the draw pile (Seek); in the exhaust pile
  (Exhume); an inline option (Discovery, the Attack/Skill/Power potions,
  Wish); an enemy (targets, folded into play); a potion. A random roll
  before the pick (Discovery's three cards) is a chance node; the pick is
  the decision.
- **Count rule as single picks.** "Exactly one", "up to N" and "any
  number" (Gambling Chip) are all a sequence of single `Choose` picks plus
  a `Done` option, one ply each, so a set-valued action over a 10-card
  hand never appears. The count rule only decides when `Done` is offered.
  Candidates from a pile are a multiset, so three Strikes are one option
  and pick order merges (the by-action rule today).
- **Play then target is two decisions pre-combined.** Nothing happens
  between choosing the card and choosing its target, so they stay one option
  (fewer plies, same tree; afterstate dedup already merges equal results).
  The model names target as a decision; the API keeps folding it.
- **`Action` gains `Choose(candidate)`** and a reserved
  **`UsePotion { slot, target }`**. The action encodings in the registry's
  records and in `bench_decisions.encode_action` cover both; the solver's
  root grouping treats `Choose` options like play options.
- **A card can pause at a decision**, like the existing mid-card chance
  pause (`Stage::PlayingCard { next }`), and the codec encodes the pending
  descriptor and candidates. Decision points inside a card are **always
  expanded, never leaves**, so no evaluator ever scores a half-resolved
  card. Past the node cap a pick is still expanded, but only along its
  first option (draw-knowledge item 4): the transposition cache does not
  bound picks (DiscardToTop and HandToTop keep order; ReturnFromDiscard
  ranges over the discard pile). A draw after the picks is a divergent
  leaf.
- **A large draw before the pick is still a leaf.** When a chance node
  inside the same card comes before its pick and is divergent (Acrobatics:
  draw 3, then discard 1), search stops there, so the evaluator does score
  a card whose decision is still to come, as it already scores a card
  paused at a large mid-card draw. The features carry the pending decision
  (its kind, picks left, the card in play) so those states read
  differently; "never a leaf" holds for the decision node itself.
- **Decisions come from cards only.** One a power's hook raises
  (Well-Laid Plans at turn end, Tools of the Trade at turn start) would sit
  inside EndTurn's resolution, which search scores as a leaf; it is
  deferred.
- **Silent's starter keeps the stand-in.** Survivor is in the game's Silent
  starter and every Silent game starts from the starter, so making it the
  default would change every Silent golden game and every recorded Silent
  game (datasets, the bench's Silent halves, warm-start's baseline).
  Spec 6 adds Survivor as a card and the real starter as a named variant (a
  keyed spec field from spec 1); switching the default is one later
  re-baseline (golden re-recorded, Silent calibration and the warm-start
  baseline re-measured), decided after the tier-B curves.
- **The engine owns a closed set of decision-point kinds**; data names the
  kind, its descriptor and its filter. Survivor needs engine work once for
  "discard from hand"; Prepared, Gambling Chip-style and every later discard
  choice are then data.
- **Potions:** format reserved, nothing implemented (out of scope).
- **Out of scope:** new state kinds (Defect's orbs) and card-choice content
  beyond Survivor and Headbutt. The entity shape below is what keeps them
  a later vocabulary entry.

## Known top of the draw pile

The draw pile is a multiset by design (no hidden order to peek at), which
is why cards that put a card on top of it are out today. Headbutt (an
Ironclad common), Warcry-style "hand to top" and Scry need it, so the
state gains a field here, keeping the no-peeking property:

- **Known top prefix.** The draw pile is an ordered list of cards the
  player knows are on top, then the multiset below. Draw takes from the
  prefix first, then uniformly from the multiset. The prefix is player
  knowledge, so it is part of `Eq`/`Hash`, the codec (a new field: the
  codec's compile check catches it) and features: **bucketed by draw
  turn**, a *next draw* pile (the first k cards, k = next turn's draw
  size) and a *known later* pile, with the index as a scalar for ties at
  the boundary. Summing position-tagged vectors into one pile would blur
  which card comes next; order inside a hand is irrelevant, so buckets
  lose nothing that matters. The heuristic reads it all as draw pile, and
  so does a net trained before spec 7 (named pile slots, see the
  contract), which is today's view.
  **k comes from the engine**, computed from the state at encoding time
  (never stored): the base draw plus every turn-start Draw hook present
  (Brutality; Predator as a delayed one-shot power, turn start → Draw 2
  then `RemoveSelf`; Ring of the Snake's turn-1 extra) minus any draw
  reduction. At the EndTurn leaf it is exact, since EndTurn resolves the
  monsters' actions before pausing at the draw; mid-turn it is "the draw
  size if the turn started now". Mid-turn draws (Pommel Strike) shrink
  the prefix and the buckets follow. k is also a named player scalar
  (*next draw size*), so the net values Predator from the number too; the
  heuristic's cards-per-turn already includes extra draws.
- **Headbutt and hand-to-top** push onto the prefix; no chance involved.
  Headbutt (Ironclad) is the prefix's proving card.
- **Scry n** is a new chance-event kind: an ordered sample of n from the
  multiset is revealed into the prefix, then single discards plus `Done`.
  Ordered samples multiply fast, so at the search's limit of 16 a Scry is
  usually divergent (a leaf, like a big draw); the exact solver enumerates
  it fully. Reserved here; built when a Scry card comes in.
- **Random insertion into the draw pile** (Wild Strike's Wound) with a
  non-empty prefix: the player doesn't learn where it went, and
  dissolving the prefix would change the game's odds, not only the
  player's knowledge (review, 2026-10-26). The information principle
  gives the exact model: the inserted card becomes a **floater**, a known
  card at an unknown position, carrying `above`, the number of known
  cards certainly above it (the review's levels, one integer per floater;
  the pile stays plain data, a sorted multiset of (card, above)).
  - Insert (Wild Strike): a floater with `above` 0, uniform over the whole
    pile.
  - Push (Headbutt, hand-to-top): every floater's `above` rises by 1; the
    pushed card is above them all.
  - Draw: only floaters with `above` 0 can be on top. With f of them and
    N cards in the pile, the top is one of them with probability f / N
    (a chance node over their kinds), else the known head; after the head
    is drawn every positive `above` drops by 1. Not drawn, they stay
    uniform over the remaining positions, so the rule is exact.
  - Once no known cards remain in the pile, every floater (all at `above`
    0) is a multiset member: today's Wild Strike behaviour, so golden games
    are unchanged. (While known cards remain, a floater at `above` 0 may
    sit above or below them, so it stays a floater.)
  - Features: floaters encode in the unknown draw pile, which is what they
    are to the next hand.
  No hidden state, the game's odds kept. When the whole pile is visible
  (Frozen Eye, below) the position is rolled and known instead.
- A reshuffle happens only when the pile is empty, so the prefix is empty
  then too.
- **Consequences.** A draw from the prefix is deterministic, so after a
  Headbutt the next draw is partly known and EndTurn has fewer outcomes
  (today a one-kind pile already draws without a chance node; the prefix
  generalises that). **Frozen Eye** (relics are out of scope; the format
  carries it) is the prefix covering the whole pile: a reshuffle becomes
  one chance node over the pile's permutations (divergent for search,
  enumerable for the solver), every draw after it is deterministic, and
  EndTurn branches only on monster rolls, so a second turn of search gets
  cheap. The net reads it as the next-draw and known-later piles.

## Monsters

- **Already entities:** scalars (HP, block, slot), rows (hook powers, the
  intent's effect rows), a position; identity not encoded. Amount
  expressions apply to moves. Per-copy overrides apply to a monster's own
  move numbers (Book of Stabbing's growing stabs, Spiker's thorns). The
  slime split generalises to a `Spawn { kind, slot rule }` effect
  (Reptomancer, Darklings, Bronze Orbs). Monsters make no decisions.
- **The gap: move selection is Rust.** Every monster's AI is a hand-written
  function with chance calls, plus hand-coded reactions (Lagavulin waking,
  slimes splitting, Looter escaping), so a new monster is tier B by
  construction. The wiki describes nearly every monster the same way:
  moves with weights and roll thresholds, repeat limits, opening
  sequences, phases, reactions. As data: a **move pattern** of (move,
  weight, conditions) rows, conditions such as turn number, last moves,
  HP band and phase, plus a reroll rule; reactions as triggered hooks
  (`OwnerLostHp` with "HP ≤ half" → split). A new monster is then data.
- **For the net:** it sees only the current intent today. With the
  pattern as rows it also sees what the monster can do next and how
  likely (the heuristic already averages the next four moves), so a new
  monster with a familiar pattern is understood from its rows, like a
  card. Generated monsters need this too.
- **Cost, and how it's kept at zero:** golden trajectories replay sampled
  games, so a data-driven AI that makes a different sequence of random
  calls changes every golden game even at identical odds, and with them
  every recorded game: registry datasets, the bench's decisions,
  reference and puzzles and the round-0 pools all replay from setup and
  actions, and the registry refuses them once the rules version (the
  golden hash) changes. So the pattern interpreter makes today's random
  calls in today's order (encounter, HP and setup rolls included): each AI
  today is a 0..99 roll, then re-roll `chance(p)` calls when a repeat
  limit blocks the move, which a pattern can state in that form. One
  source (the data) drives both listing and sampling.
- **The pattern format is today's call shape** (owner, 2026-10-26: no
  distributional fallback; the data must give the same result with the
  same RNG). Every one of the 15 AIs is either a fixed sequence over the
  move history (Cultist, Lagavulin, Looter, Sentries) or one `below(100)`
  roll into threshold bands, where a band blocked by a repeat limit falls
  to one `chance(p)` pick between two moves (Jaw Worm, Gremlin Nob, the
  slimes). So a pattern is an ordered list of rows (conditions, move),
  the first matching row fires; a row may read *the roll*, which is made
  lazily, once, the first time a row needs it (Jaw Worm's first turn makes
  no call); a row's repeat limit names its alternative as a `chance(p)`
  pair. Today's calls in today's order then hold by construction, and the
  golden test proves it. A future monster with a different roll shape has
  no recorded games to protect and gets a new row kind, not a fallback.
  What doesn't fit rows (Slime Boss's split placement) stays a named
  engine reaction the data references. Setup rolls (louse damage, Curl
  Up, encounter composition) are `Setup` rows run in slot order, which is
  `new_as`'s order today.
- **Move history and monster state.** `moves` is a two-deep window of
  *executed* moves: `moves[0]` is the intent on show (the move about to be
  executed, or just executed when the pattern runs to pick the next),
  `moves[1]` the one before; `NO_MOVE` fills the window at combat start,
  so "first turn" is `moves[0] == NO_MOVE`. Picking shifts the window
  (`set_move`). Every repeat limit in the roster reads at most two ("not
  three in a row" is "the last two were X"), and the fixed sequences read
  the window plus `NO_MOVE` (Lagavulin: last two Sleep → Wake; last Sleep
  → Sleep; last two Attack → Siphon Soul; else Attack, in that order), so
  the window stays two deep. Beyond it, the pattern reads the combat
  turn, the owner's HP and powers, allies alive, and one monster scalar
  `phase` (the game's own per-monster byte; Awakened One, Darklings,
  Gremlin Leader), a named column to the net. Conditions, closed: first
  turn, last move, last two moves, turn below / above, HP below a
  fraction, phase, allies alive, slot (the Sentries' first move: slot 1
  opens with Beam). Reactions need `SetIntent` (Lagavulin
  waking, the split) and `SetPhase`. Migrate all 15 encounters in spec 9
  (the umbrella's option (a); decided 2026-10-26).
- **Checked against the whole game** (2026-10-26, against sts_lightspeed,
  which reimplements every monster through the Heart with a two-entry
  `moveHistory`; the game's decompiled code was not read). The two-deep
  window holds for every monster: every check is the last move, the move
  before it, both, either of the two, or "no move yet". The full game adds
  conditions, not depth:
  - *Already in the 15:* the Sentries' first move depends on the slot
    (slot 1 opens with Beam, `engine/src/monsters.rs`), so the closed list
    has **slot** for spec 9 itself (Darklings use it too).
  - *Move before last* (Champ's Execute, Chosen's Hex, Spire Shield's and
    Spear's 3-move cycles) and *either of the last two* (Nemesis's
    Scythe): both inside the window.
  - *Turn modulo or equal:* Champ (Taunt every 4th turn), Corrupt Heart
    (Buff every 3rd), Collector (Mega Debuff on turn 3); Giant Head's
    "from turn 4" is turn above. All read the combat turn, which works
    since none of them is spawned mid-fight.
  - *Other entities' state:* the player's powers (Spire Growth checks
    Constricted), an ally's missing HP (Mystic heals the Centurion),
    allies by tag (Gremlin Leader, in the table below).
  - *`phase` as a counter or flag:* one byte per monster is enough
    (sts_lightspeed keeps one such value per monster's AI): used-once
    flags (Red Slaver's Entangle, Bronze Orb's Stasis, Writhing Mass's
    Implant, Time Eater's Haste), phase flags (Champ, Awakened One) and
    counters (Gremlin Wizard's charge to 3, Hexaghost's place in its
    7-move cycle, Spiker's buff count, Bronze Automaton's Boost/Flail
    alternation). Hexaghost's Divider damage is a move number (a per-copy
    override), not AI state. Where `phase` counts toward a threshold, the
    row that reads it carries (phase, threshold), as the counter rule
    says; conditions gain *phase at least n* and effects `AddPhase` beside
    `SetPhase`.
  - Ascension checks are out of scope (Ascension 0).

## Check against exceptional encounters

Six later encounters, checked against the model (2026-10-26). All fit with
six new atoms and no format change:

| Encounter | Mechanic | In the model |
|---|---|---|
| Gremlin Leader | summons gremlins over the fight | pattern conditioned on a quantity "living monsters tagged minion" (tags on monsters); `Spawn` with a random kind from a set (chance node) into empty slots; `OwnerDied` → kill tagged minions |
| Darkling | revives unless all three are down at once | **death replacement**: `OwnerDied`, condition "another Darkling alive" → become *downed* (monster scalar: in its slot, not targetable, doesn't act, not alive for the win rule) with a turn-start revive hook at half HP; the last one's condition fails, so it dies for real and the win rule ("no living monster") ends the combat |
| Writhing Mass | intent changes when hit | `OwnerLostHp` → `RerollIntent`: a move roll as a chance node inside card resolution (the mid-card pause draws already use); visible at once, so the information principle holds |
| Awakened One | revives once | the same death replacement with a one-shot condition: full HP, phase 2, `RemoveSelf`; the pattern conditions on phase |
| Time Eater | ends your turn every 12 cards | the counter design's test: a cross-turn counter on Time Warp, in its row as "7 of 12, then `EndPlayerTurn` + Strength"; `EndPlayerTurn` flags the turn to end when the card in play resolves |
| Spire Shield and Spear | facing; +50% damage from behind | player scalar *facing* (a slot) set by a `CardPlayed`-with-target hook → `SetFacing`; a conditional static modifier with the position-relative condition "player faces me" |

New atoms: death replacement with the downed state, `Spawn` with a random
kind, monster tags, `RerollIntent`, `EndPlayerTurn`, facing with
`SetFacing` and "player faces me". The two state additions (downed, facing)
are entity scalars.

## Information principle

A random event is rolled at the moment its outcome becomes visible to the
player, so no hidden value ever sits in the state and `Eq`/`Hash` stay
"what the player knows". The draw pile already works this way (order is
rolled at the draw). Two more cases it covers:

- **Known top prefix:** a revealed card moves from "rolled at the draw" to
  known; nothing else changes.
- **Runic Dome** (relic: intents hidden; out of scope, format carried by a
  spec field): the monster's move roll is deferred from the start of the
  player's turn to the moment the monster acts. EndTurn then pauses at the
  roll before the monsters act, so this turn's incoming damage is inside
  the divergent leaf and the evaluator estimates it from the monster's
  **move pattern rows** (which makes those rows required, not only a
  generalisation aid). Move history stays visible (the player sees the
  attack), so repeat limits and phases condition on known state, and the
  deferred roll has exactly the distribution of the early one.

## Format decisions to fix now

Named columns and an additive vocabulary make most additions safe later.
These replace an existing encoding or change what a state key means, so
each is fixed by the spec named, before any content uses it:

- **Amounts as expressions, not primitives.** Every amount that reads
  something is its own primitive today (Body Slam reads block, Heavy Blade
  Strength, Perfected Strike the Strike count, X-cost the energy spent,
  Rampage its own damage). The row format carries `base + k × quantity`,
  quantity from a closed vocabulary (own block, Strength, energy spent,
  cards in hand, cards with a tag, stacks; one quantity per amount, no
  nesting), so the net reads "damage = 1 × block". Still data. Migrating
  those primitives later would be a schema break. The old primitives'
  columns (`damage_from_block`, `strength_mult*`, `per_strike*`) stay,
  computed from the expression, so nets that read them stay exact
  (owner, 2026-10-26: they are training-pool cards). **The net reads
  both halves** (owner, 2026-10-26): the damage column carries the value
  resolved against the state at encoding time (block, Strength, energy as
  they are now; a snapshot, per the information principle), and `base`,
  `k` and a one-hot of the quantity sit beside it as columns of their
  own (as built: the value is its own column, `expr_value`, so old nets'
  inputs on the re-expressed cards stay exact). The value is useful from the first game; the form lets the net
  learn that the card scales, which a card-alone embedding can't recover
  from the value (Deep Sets embeds each card before it sees the player's
  scalars). The legacy columns are this form for three quantities. The
  same encoding applies to monster moves once spec 9 uses expressions.
- **Override entries with a lifetime, flags included.** Per-copy state is
  (field, value, lifetime): Enlightenment sets cost this turn, Well-Laid
  Plans gives Retain to chosen cards. Lifetime is in the key format from
  the start.
- **Card tags.** Perfected Strike counts cards tagged Strike, Accuracy
  affects Shivs. Conditions and filters reference tags a card carries as
  data, never names.
- **Named spec fields and action encodings** (spec 1). Game specs are
  positional tuples (encounter, deck, seed, hp) in records, bench files and
  the solver's positions table; they become keyed with defaults, so
  potions, relics, a starter variant or a starting known prefix are a field
  each. `Choose`, `Done` and `UsePotion` get record encodings before any
  content uses them, and a play names its card key, not only its name:
  records and bench files write a play as `"Rampage@1"` and the codec as a
  card id, but two Rampages at different damage are different actions, so
  the play encoding carries the overrides.
- **The damage pipeline's order** (spec 4, used by spec 5): base, adds
  (Strength, Accuracy), multiplies (Weak ×3/4, Vulnerable ×3/2), round down
  once, replacements on the amount (Intangible's cap), then block. Today's
  integer math is this order, so the golden games hold; rows carry their
  stage.
- **State representation for open-ended content** (spec 8's interview,
  before spec 10). Piles are `[u8; NUM_CARDS]` per card id, card ids are
  `u8` (106 of 256 used), each entity's powers are `[i16; NUM_POWERS]` with
  a `u32` just-applied mask (19 of 32 used; the proving set adds about
  six), and definitions are `&'static` tables. Per-copy keys, a runtime
  registry and generated content outgrow all four. The replacement keeps
  `Clone` cheap (check 4) and `Eq`/`Hash` canonical; direction to test:
  piles and powers as sorted fixed-capacity inline lists of (key, count),
  no heap, with `u16` ids. Decided with it: where the registry lives (one
  per process, set once, or a handle states point to), since cargo runs
  tests as parallel threads of one process and `generated-cards` wants
  content per run.
- **Content in the versions** (spec 10). The fingerprint hashes the
  compiled-in rule files (`solvedb/src/fingerprint.rs`) and the registry's
  rules version is the golden hash; neither sees a data file, and new
  cards aren't in golden decks. From spec 10 both also hash the loaded
  content, or a data edit leaves stale exact values and silently wrong
  replays.

Safe to add later, because the design absorbs them: new chance-event
kinds (the `Chance` trait replays every path), new targets and triggers
(vocabulary), new entity kinds (entity shape), relics and potions
(entities).

## Contract with the net (decided 2026-10-26)

- **Named input dimensions.** Every input column has a name: vocabulary
  entries and the scalars that are positional today (player, monster and
  card properties). A saved net stores its names and per-name normaliser
  statistics. Loading maps by name (`warm-start`'s loader), so reordering
  and appending never break a net.
- **Exact reload by gather.** For inference the loader picks the current
  batch's columns in the saved net's order and drops the ones it doesn't
  know, so the first layer sees exactly the inputs it was trained on.
  Permuting or zero-padding the weights instead isn't bit-identical:
  floating-point addition depends on order, and a different inner width
  changes how the math library splits the sum. The wider, zero-padded
  layer is for fine-tuning only (`warm-start`), where a tolerance applies.
  Bit identity is per forward pass: torch against torch, Rust
  (`py/src/net.rs`) against Rust; the two already differ by about 1e-6.
- **Structural additions are vocabulary too**, not only columns:
  - *Row kinds.* A net pools every row of a card or entity, and an unknown
    trigger still counts (as `trigger_unknown`), so rows a format change
    adds (spec 4's modifier and countdown rows, spec 5's replacement rows,
    spec 9's pattern rows) would change an old net's output on nearly
    every state. Each row has a kind; a net's meta lists the kinds it was
    trained with, and rows of other kinds are dropped before its row
    layer. Within a known kind, new content with an unknown trigger still
    shows as `trigger_unknown` (Amendment 1).
  - *Power dimensions.* Today a power loses its dimension once it has
    hooks (`is_hook_power` in `py/src/features.rs`); the dimension set is
    fixed by the vocabulary instead, so Strength, Dexterity, Vulnerable,
    Weak, Frail and Artifact keep theirs beside their new rows.
  - *Named pile slots.* The head reads one pooled slot per pile
    (`NUM_PILES` in `scripts/stsnet.py`, checked in `py/src/net.rs`), so a
    new pile changes its width. Head slots are mapped by pile name, and a
    pile a net doesn't know folds into its parent (next draw and known
    later into draw).
- **Nets saved under the contract always load.** The guarantee starts at
  spec 1: a net whose meta carries column names and a schema version loads
  through every later spec. Nets from before the contract (today's
  `models/*.pt`, the registry's runs, the curriculum's nets) get no
  promise; spec 1 ships `scripts/convert_net.py` instead (owner,
  2026-10-26): it maps a known pre-contract layout version (today's
  positional columns are a known order per cache version) to names and
  saves a contract net, checked bit-identical on the fixed set against
  the original for the curriculum's final net. That net is the Ironclad
  parent for the post-series learning curve, at no training cost (check
  at the interview that Headbutt and Rampage are not in its training
  pool; if they are, the Ironclad curve uses a held-out card). A **schema
  version** changes only on a rename or a meaning change of an existing
  column; a major version, if ever, is the one case that may drop nets.
- **Entity shape.** Player, monsters and cards (and later orbs, potions)
  are encoded through one path: scalars (for a card: cost, type, flags,
  with per-copy overrides already applied), rows (hook powers' hooks × stacks,
  static modifiers as rows, a card's effect rows), and a position (a
  monster's slot; for a card its pile, with the known top prefix split
  into next-draw and known-later piles, plus its index for ties). A new entity kind is
  then a vocabulary entry, not a new array in the batch. This is one
  feature-format change (spec 3); both forward passes read it, an old net
  through an adapter to its own paths.
- **Feature rows gain vocabulary** (replacement triggers, counter
  conditions, static-modifier rows, new targets, keywords).

## Must stay true

In every spec, unless its row in the series table says otherwise:

- Existing content plays step-for-step identically (golden trajectories),
  so recorded games stay replayable. No exception: spec 9's pattern
  format reproduces today's random calls by construction.
- Speed: check 4 still passes and the spec's harnesses in "Speed checks"
  are within budget; `CombatState` stays plain data with cheap `Clone`,
  `Eq`, `Hash`.
- The heuristic's estimates are bit-identical on every state of the fixed
  set (as triggers-and-conditions checked on 12,007 states): it is the
  bootstrap player, the calibrator and the reference builder (owner,
  2026-10-26).
- Every net saved under the contract loads and gives bit-identical
  outputs (per forward pass, by gather) on every state of the fixed set
  whose encoding for that net the spec doesn't change. Pre-contract nets
  get a best-effort import only.
- The solver database is retired at each fingerprint change in the table
  and refilled once after the series; the bench's exact puzzle values stay
  valid while existing content plays identically.

## Speed checks

Most specs move work into search's inner loop (rows read where a field
was read) or enlarge the state (prefix, floaters, override keys), and the
sweep and curriculum size their nights from measured games/s, so each
spec measures before and after. Four harnesses, all existing or a count;
a spec adds no new one:

- **H1, check 4** (`engine/examples/bench.rs`): random combats per minute
  and clone time, one thread. Keeps its absolute floor (100,000 per
  minute, clone under 1 µs) on top of the relative rule.
- **H2, search** (`engine/examples/search_speed.rs`): search + heuristic
  games/s at 1 and 16 threads over its 600 fixed specs. Golden identity
  makes this a fair comparison: the games before and after are the same
  games, so games/s compares equal work.
- **H3, net** (`scripts/inference_speed.py`, Rust evaluator): self-play
  and tight-fight games/s with a net: the encoder plus the forward pass.
- **H4, nodes**: nodes visited per root decision on the fixed state set,
  a count, not a time. On existing content it must be identical in every
  spec: a transposition key that stopped matching (spec 8's override
  keys, spec 7's empty prefix) shows up here before it shows in a rate.

Method: same machine, no other session running, before and after the
spec on the same inputs, median of 5 interleaved runs (as
`inference_speed.py` does; rates vary ~2x under other load, which is why
single runs don't count). Both numbers go in the spec's as-built entry in
`docs/decisions.md`.

Budget (defaults, tunable): per spec no harness it lists regresses more
than **10%** (median against median); over the whole series H1 and H2
stay within **25%** of the pre-series numbers; H4 identical on existing
content. A spec over budget doesn't ship until it's back under or the
owner accepts the number in `docs/decisions.md`. Two structural guards
that keep the budgets reachable: an empty prefix, an empty floater list
and an empty override set must cost nothing in clone, hash and equality
(no allocation for existing content), and a content lookup in the inner
loop stays an index, never a name.

| # | Spec | Where speed is at risk | Harnesses |
|---|---|---|---|
| 1 | `contract` | the gather per batch; column names in the encoder | H3 |
| 2 | `amount-expressions` | expressions resolved in the damage pipeline | H1, H2 |
| 3 | `entity-shape` | one feature path, the adapter for old nets | H3 |
| 4 | `static-modifiers` | Strength, Dexterity, Vulnerable, Weak, Frail read as rows where a dimension was read: every damage and block computation scans rows. The series' highest risk; if the rows cost it, the dimension stays the fast path and the rows are the data | H1, H2 |
| 5 | `replacement-hooks` | every damage event asks its replacement hooks | H1, H2 |
| 6 | `decision-points` | the tree grows for content with decisions; existing content must not | H2, H4 (H4 also recorded on Survivor as the decision baseline) |
| 7 | `known-top` | prefix and floaters in the state (clone, hash, eq); prefix draws as chance outcomes | H1 (clone), H2, H4 |
| 8 | `per-copy-overrides` | (kind, overrides) pile keys: hash, eq, and the transposition cache's hit rate; the encoder reads overrides | H1 (clone), H2, H3, H4 |
| 9 | `monster-patterns` | move selection interprets rows each monster turn | H1, H2 |
| 10 | `runtime-registry` | content from files must index the same way; startup load | H1, H2, startup under **1 s** (default) |

After the series, the solver refill is timed once on the puzzle set
against the pre-series solve times (same positions), since the solver
steps the same inner loop.

## Open questions for the interviews

- Event order when several replacements apply to one event (the game's
  order for in-scope content; a rule for generated content).
- (Decided: built-in modifiers keep their own dimensions beside the rows,
  so old nets load unaffected.)
- The exact proving cards (above, unverified against the wiki), including
  the self-Retain card.
- Calibrated Silent tight fights for the bench (on the default, stand-in
  starter).
- Card replay's rules (Burst, spec 6), from the game's code: energy,
  `CardPlayed` hooks, the cards-played count, a target that died, a
  decision inside the replayed card.

From the 2026-10-26 review (answered parts are in the body above):

- **The heuristic and new atoms**: answered (owner, 2026-10-26). The
  heuristic stays blind to new row kinds through the series; it reads
  existing content through the primitives and dimensions that stay, so
  its bit-identical check holds. It learns a row kind only when content
  using it enters the round-0 pool, as its own step then, not in the
  series. Each spec's interview records "proving atoms reach round-0
  content: no".
- **What the net reads of an amount expression**: answered (owner,
  2026-10-26), both halves; see "Format decisions to fix now".
- **Speed beyond check 4**: answered (2026-10-26), see "Speed checks":
  four existing harnesses, 10% per spec, 25% over the series, node counts
  identical on existing content.
- **A baseline for Headbutt and Rampage**: answered (owner, 2026-10-26).
  Spec 1 ships a converter for known pre-contract layouts, checked
  bit-identical on the curriculum's final net; see "Contract with the
  net".
- **Spec 9's fallback and what patterns need**: answered (owner,
  2026-10-26). No fallback; the pattern format is today's call shape, the
  move window stays two deep, `phase` is the one new monster scalar; see
  "Monsters". Checked against the whole game the same day: two deep holds
  for every monster; the closed condition list has slot, already for the
  Sentries, and later monsters add move-before-last, either-of-two, turn
  modulo, the player's powers, an ally's HP and `phase` as a counter
  ("Checked against the whole game" under "Monsters").
- **Per-spec checklist**: answered (owner, 2026-10-26); see "Per-spec
  checklist".

## Per-spec checklist

Each spec's Tests section copies this list and marks an item n/a with a
reason:

1. Golden trajectories identical (hash); the dump prints new fields only
   when set (it builds its text by hand, so hashes hold).
2. Fuzz invariants, extended as the spec needs: card conservation across
   the prefix, floaters, overrides and Retain; no duplicate `Choose`
   candidates; `Done` always reachable; every legal action applies.
3. Determinism and codec round-trip of every new state field; the
   fingerprint changes exactly when the series table says so.
4. The heuristic bit-identical on the fixed state set.
5. Contract nets bit-identical by gather on every encoding the spec
   doesn't change; the batch snapshot for unchanged columns.
6. Bench byte-identity: existing evaluators on existing sets write the
   same files (covers the encoder and search cheaply).
7. Speed, per the "Speed checks" table.
8. Proving content: a unit test per atom against the wiki text, plus new
   golden games recorded with it.
9. Registry datasets and bench files still replay (rules version
   unchanged).
