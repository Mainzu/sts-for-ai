# How sts-for-ai works

The idea in one line: **the agent never chooses a card; it chooses between
the game states that its options lead to, and it judges a state by what is
in it, described in effects rather than names.**

This file explains that idea and where each part lives. Exact rules and
pass bars are in `SPEC.md`; individual design calls are in
`docs/decisions.md`.

## The core concept

### 1. Choose states, not actions

At each decision the engine lists the distinct legal options (play a card on
a target, use a potion, or end the turn; during an in-card pick, choose a
candidate or finish the pick), applies each one to a copy of the game, and hands
back the **afterstate**: the game as it would be after that option. The
agent scores the afterstates and picks the best. Backgammon engines
(TD-Gammon, GNU Backgammon) work the same way.

Why this matters: anything the engine knows how to apply is already *in* the
afterstate. A power the agent has never heard of still shows its effect (the
extra block, the extra damage) in every option it compares, so the agent can
still decide well with it active. What it can't do is value an option whose
main effect is *granting* an unknown power, because there the only
difference between options is a token it doesn't understand.

### 2. One state, two kinds of information

The evaluator scores **one state at a time**. That state carries:

- **What has happened**: player HP, block, energy, powers; each monster's
  HP, block, powers and intent. After you play Strike, the monster simply
  has 6 less HP.
- **What could still happen**: every card in every pile (hand, draw,
  discard, exhaust), each described by its **effect primitives** (cost,
  damage, hits, block, draw, powers applied, cards created…) with a count.

So the effect of an option is judged by the state it produces, and the
potential of the deck is judged by the primitives of the cards still in it.
A card you just played only shows up again as a discard-pile entry, which
matters for when it comes back after a reshuffle.

Example, Blade Dance: once played, its Shivs sit in hand as ordinary
0-cost, 4-damage, exhaust cards, which the network understands. Before it's
played, it is judged by its own vector, which (with the current trained nets)
lacks the "added to hand" part.

### 3. Cards are data built from primitives

A card is a cost, some flags (exhaust, ethereal, targeted…) and a list of
effect primitives: `Damage{amount, hits, target}`, `Block`, `Draw`,
`GainEnergy`, `LoseHp`, `Apply{power, amount, target}`, `AddCard{card,
pile}`, plus amounts that read the state: `ScaledDamage{amount, hits,
target}`, whose `Amount` can read the user's block (Body Slam), their
Strength (Heavy Blade), the Strikes in the deck (Perfected Strike) or the
energy spent (Whirlwind). Monster moves use the same primitives, so intents are described
the same way.

This is what lets a learned evaluator handle a card it never saw: a new card
that is a **new combination of primitives seen in training** gets a
meaningful vector. A **primitive never active in training** (Poison, "add to
hand") doesn't: the network's weights for it never got a training signal.

#### The rules model: what powers can express

Card-game rules engines (most explicitly Magic: The Gathering's) split every
rule-changing effect into three kinds of ability, each with a lifetime.

| Kind | What it is | StS examples | Here |
|---|---|---|---|
| Triggered | "when X happens, do Y" | Metallicize, Rage, Curl Up, Poison | hooks (`engine/src/hooks.rs`): trigger + condition + effects |
| Static / continuous | changes numbers while it exists | Strength, Vulnerable, Weak, Frail | static modifier rows (`Static` in `engine/src/hooks.rs`, `statics` in `content/powers.json`), which the net sees as `static` rows. The built-in ones are still hard-coded in `attack_damage` / `gain_block` for play, with a test that keeps the code equal to the rows. Each named modifier power also keeps its own feature dimension. |
| Replacement / prevention | "if X would happen, do Y instead" | Buffer, Intangible, Artifact | replacement rows (`engine/src/hooks.rs` `Replacement`): cancel an event or change its amount (cap, add, multiply, at least); Artifact and Intangible use them, Buffer isn't in the engine yet |

| Lifetime | Example | Here |
|---|---|---|
| Permanent | Demon Form | no removal |
| Until end of turn | Rage | turn end → `RemoveSelf` |
| Used up on first use | Curl Up | `RemoveSelf` in the triggered hook |
| Wears down | Poison | `ReduceSelf(1)` each time it fires |
| Debuff countdown | Vulnerable, Weak, Frail | a `RoundEnd` hook that wears the debuff down by 1 each round (stacks = turns left) |
| Delayed one-shot ("next turn…") | Dodge and Roll | expressible: turn start → effect + `RemoveSelf` |
| Charges separate from strength | Double Tap | only when the stack count is the charge count |
| Counter that fires at a threshold | Pen Nib, Panache | on a relic: its counter and `CounterIs` (Pen Nib, `content/packs/act1-relics.json`); on a power: missing (needs a second number per power) |
| Conditional static ("while…") | Red Skull | a static row with a condition (`StaticCondition`, e.g. `OwnerHpAtMostHalf`) |

Hook effect amounts are multiplied by the power's stacks; `RemoveSelf` and
`ReduceSelf` are not. Most of these gaps were closed by the series in
`docs/specs/rules-engine-upgrade.md` (conditional statics such as Red Skull
are built). What it defers is listed there, including counters on powers
(Pen Nib, Panache) and death replacement.

### 4. Randomness is explicit, and the agent can't peek

- Every random event (drawing, monster move rolls, random targets) is a
  **chance node**. The engine pauses there and can either list the outcomes
  with their probabilities or sample one.
- Every pile is an unordered multiset, except that the draw pile can have
  a known top: cards the player knows sit on top in order (Headbutt's card,
  for example), plus floaters, which are known cards at an unknown depth
  (`Top` in `engine/src/state.rs`). Past those, drawing is a uniform pick
  from what's known to be in the pile. There is no hidden order to cheat
  with, and shuffling isn't an event at all.
- The random number generator is kept outside the game state. The state's
  equality and hash cover only what the player could know.

### 5. Search: one turn deep, stop where the future branches widely

The search agent is depth-limited **expectimax** over the current turn:

- Options with no randomness are expanded.
- Options with a few random outcomes (e.g. Pommel Strike's single draw) are
  expanded and **averaged by probability**.
- Options with many outcomes (EndTurn's new hand and new intents, big draws)
  are **leaves**: the engine runs everything already known (the monsters'
  attacks, whose damage the intents show) and pauses before the random
  part. The evaluator scores that paused state, which already shows the HP
  lost this turn.
- `sample_k > 0` instead samples a few outcomes at those points and keeps
  searching. With `turns=2` (which only takes effect when `sample_k > 0`),
  the search also looks past EndTurn into the next turn. This is the
  product's setting (`--two-turn`).

### 6. Duplicate options are merged twice

- **By action**: copies of a card carry no state of their own, so the same
  card on the same target always gives the same result. Three Strikes in
  hand against two monsters are two options, not six. Untargeted cards
  have one option.
- **By afterstate**: different actions that lead to identical states are
  merged into one option.

### 7. The score

What every evaluator predicts and every agent maximises: a loss scores 0;
a win scores **2 − HP lost / 100**, with HP lost measured after
end-of-combat healing (Burning Blood), floored at 0. Any win beats any loss;
among wins, less HP lost is better. (Amendment 3; before it, a win scored
1 + HP left / max HP.)

## Evaluators

- **Heuristic** (`engine/src/heuristic.rs`): hand-written, reads cards and
  intents only through their primitives. Estimates damage to come and the
  chance to win. Its scores are for ranking options, not predicting the
  score: search values average ~0.98 where the same games score ~1.71.
  Never use them as training targets or absolute estimates (learned-play
  Amendment 1).
- **Learned value nets** (`scripts/stsnet.py`): small (~190k parameters)
  PyTorch networks trained by supervised regression: given a mid-combat
  state from games played by search + heuristic, predict that game's final
  score. Cards are encoded with **nested Deep Sets**: hook rows (trigger,
  condition, effects) are embedded by one shared layer and summed into
  their card or their entity (player, monster); one shared layer turns each
  card into a vector, and a pile is the count-weighted sum, so order and
  pile size don't matter.
  - **effects net**: card vectors are primitive vectors plus their rows; a
    card that grants a power carries that power's hook rows; hook powers on
    an entity are rows × stacks. Modifier powers (Strength, Dexterity,
    Vulnerable, Weak, Frail, Artifact, DamageDown, SplitHits;
    `MODIFIER_POWERS` in `py/src/features.rs`) keep one dimension each plus
    `unknown`.
  - **ids net**: cards and powers are one-hot ids, with an `unknown` slot,
    and no rows. It is the control: it can't say anything about a card or
    power it never saw.

Search with the nets now plays better than with the heuristic at equal
depth (kb measurement/leaf-vs-heuristic). Training runs in self-play rounds
(the AlphaZero/TD-Gammon loop). In round 0 the net learns from games played
by search + heuristic. In each later round it learns from games played by
search with the previous round's net, and every label is the game's real
outcome (README "Learned play").

- **Exact solver** (`engine/src/solve.rs`): not an evaluator for play, but
  the measuring stick. On small endgame positions it computes every
  option's true value (best play, every random event listed, to the end of
  combat) within a node budget, or says it can't. The bench's puzzle set
  scores evaluators against those values.

## The tests of the idea

- **Held-out cards** (`scripts/generalise.py`, check 6): train both nets
  without Twin Strike, Iron Wave, Thunderclap, Pommel Strike and Uppercut
  (each a new combination of known primitives), then compare prediction
  error on decks that contain them.
- **Silent transfer** (`scripts/transfer.py`, check 8): nets trained only on
  Ironclad predict Silent games. Tier A cards are made of known primitives
  (gated); tier B uses Poison (reported only, expected to be weaker).
- **Granting a held-out power** (`scripts/granting.py`, check 9): nets
  trained without Metallicize, Demon Form, Rage, Go for the Eyes and FTL
  value playing them (the gain over the best other option) close to a
  reference net trained with them. Their powers are built from triggers,
  conditions and effects training uses; FTL's condition isn't (reported
  only).

## Where things live

| Path | What |
|---|---|
| `engine/src/state.rs` | `CombatState`, piles, actions, stepping, `legal_actions`, `score` |
| `engine/src/effects.rs` | effect primitives and how they apply |
| `content/*.json` | official content as data (cards, powers, monsters, encounters, relics, potions), compiled in and parsed by `engine/src/registry.rs` (the pack parser) |
| `engine/src/cards.rs` | card types and lookup (definitions come from `content/cards.json`) |
| `engine/src/monsters.rs` | monster, move and encounter types, and move rules (data in `content/monsters.json` and `encounters.json`) |
| `engine/src/powers.rs` | powers: stacks per kind, modifier countdowns |
| `engine/src/hooks.rs` | hook types: trigger, condition, effects (each power's hooks come from `content/powers.json`) |
| `engine/src/character.rs` | Ironclad / Silent: starter deck, HP, relic |
| `engine/src/chance.rs` | chance nodes: list or sample outcomes |
| `engine/src/rng.rs` | seeded RNG and the `Chance` interface |
| `engine/src/options.rs` | options: deterministic / chance / divergent, deduplication |
| `engine/src/search.rs` | expectimax search, `Evaluator` trait (batched) |
| `engine/src/solve.rs` | exact solver: true option values to the end of combat, or unsolvable |
| `engine/src/codec.rs` | state to compact bytes and back (the database's state format) |
| `solvedb/` | SQLite database of solved states and puzzles (`db/solved.sqlite`) |
| `engine/src/heuristic.rs` | hand-written evaluator |
| `engine/src/agent.rs` | random, greedy and search agents |
| `engine/src/runner.rs` | run many seeded combats across threads |
| `py/src/lib.rs` | Python module `sts` (PyO3) |
| `py/src/features.rs` | state → feature arrays (effects / ids, hook rows, vocabularies) |
| `scripts/eval.py` | strength table (check 5) |
| `scripts/replay.py` | turn-by-turn log with each option's score |
| `scripts/selfplay.py`, `train.py`, `stsnet.py` | data, training, the nets |
| `scripts/generalise.py`, `transfer.py`, `granting.py` | checks 6, 8 and 9 |
| `scripts/bench.py`, `puzzles.py` | evaluation bench; exact puzzles from real games' tails |

## Known limits

- **A primitive, trigger or condition never active in training** has
  untrained weights, so the nets can't value options that rely on it (a
  power built only from seen parts is fine: that is check 9). Active
  effects still show in afterstates.
- **"Add to hand"** is in the card vectors, but no Ironclad training card
  uses it, so its weights get no signal. Teaching it needs a training card
  that uses it (e.g. Power Through).
- **All losses score 0**, so when every line loses, the agent has nothing
  to tell options apart.
- **Shallow search**: one turn deep by default and two for the product
  player (`turns` in SearchConfig); the evaluator carries everything beyond
  that.
- **The nets learn the real outcomes of their own play** (search over the
  previous round's net; only round 0 learns from search + heuristic games),
  so there is no teacher stronger than the student (kb
  cause/teacher-equals-student), not optimal play.

How new content and new mechanics are meant to enter the engine and the
net (tiers, the data-only rule, the named-column contract, the series of
engine specs) is in `docs/extending.md`.

## Running it

See `README.md` for building the `sts` module into `.venv`. Common runs:

```bash
.venv/Scripts/python scripts/eval.py
.venv/Scripts/python scripts/replay.py --encounter slime_boss --agent search --seed 3
.venv/Scripts/python scripts/generalise.py
.venv/Scripts/python scripts/transfer.py
```
