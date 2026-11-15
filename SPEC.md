# sts-for-ai — demo spec

A fast Slay the Spire 1 combat engine in Rust, exposed to Python, built so an
agent chooses between **resulting states**, not between card names. Cards are
data built from effect primitives, and every random event is explicit. The
agent searches the current turn, averaging over small random events and
stopping at large ones, and scores the states it reaches with an evaluator
that sees only effect-based features, never card ids.

The model is backgammon engines (TD-Gammon, GNU Backgammon): score the
position after each move, and take the expectation over chance.

The demo's question: **does a feature-based evaluator handle cards it never
saw in training, where an id-based one can't?** Raw strength comes second.

## Scope

**In**
- Ironclad, Act 1 combat only (Ascension 0). Relic: Burning Blood only.
- Cards (base and upgraded): Strike, Defend, Bash, Anger, Body Slam, Clash,
  Cleave, Clothesline, Iron Wave, Pommel Strike, Shrug It Off, Thunderclap,
  Twin Strike, Wild Strike, Heavy Blade, Perfected Strike, Sword Boomerang,
  Bloodletting, Hemokinesis, Pummel, Uppercut, Inflame, Flex, Carnage.
  Status: Wound. (Cards that make you choose another card, or put cards on
  top of the draw pile, are out.)
- Powers/statuses as the cards and monsters need: Strength, Dexterity,
  Vulnerable, Weak, Frail, Block, Ritual, Curl Up, Angry, Enrage,
  Metallicize, Artifact, Spore Cloud, Flex's temporary Strength.
- Monsters:
  - Hallway: Cultist, Jaw Worm, Red Louse, Green Louse, Acid Slime (S/M),
    Spike Slime (S/M), Fungi Beast, Looter.
  - Elites: Gremlin Nob, Lagavulin, 3 Sentries.
  - Boss: Slime Boss (including the split). Added 2026-10-30, by name
    only (`Encounter::ADDED`, not in `ALL` or any bench set): Hexaghost
    (with the Burn status card) and The Guardian (Mode Shift, Sharp Hide).
- Monster move rules and values from the StS wiki. `sts_lightspeed` (C++) is
  a behaviour reference only. Copy no code from it.

**Out**: map, rewards, shops, events, potions, other relics, other
characters, Acts 2–4, Ascension, the real game's RNG streams, whole-turn
moves (one option = one card play; whole turns are a later experiment).

## Engine

```
engine/   Rust lib: state, effect primitives, content, chance, search
py/       PyO3 crate built with maturin → Python module `sts`
scripts/  Python: self-play data, training, eval, replay
```

### State

- `CombatState` is plain data deriving `Clone, Eq, Hash`. No `Rc`, no trait
  objects. Cloning must be cheap; search does it constantly.
- **The draw pile is a multiset, not an ordered list.** The player knows
  what is in the draw pile but not its order, so drawing is a uniform draw
  from that multiset. This is equivalent to the real game for in-scope cards
  and makes peeking impossible by construction. (Wild Strike's Wound just
  joins the multiset.)
- Monster slots are fixed for the whole combat. Dead monsters keep their
  slot, and Slime Boss's split fills fixed slots.

### Cards as data

A card is `cost + flags (exhaust, ethereal, unplayable, targeted) +
Vec<Effect>`. Effect primitives include `Damage{amount, hits, target}`,
`Block`, `Draw`, `GainEnergy`, `LoseHp`, `Apply{power, amount, target}`,
`AddCard{card, pile}`, and one primitive per odd card (`DamageFromBlock`
for Body Slam, `StrengthMultiplier` for Heavy Blade, `PerStrikeBonus` for
Perfected Strike, `OnlyAttacksInHand` for Clash, `ReturnToHand` for Anger…).
Upgrades are a second definition, not code. Monster moves use the same
primitives, and monster intents are shown from them.

### Chance

The engine runs deterministically until it needs a player decision or a
random event. At a random event it **pauses at a chance node**:

- Chance events: draw (from the multiset), random target (Sword Boomerang),
  monster move roll. Shuffling is not an event, because the pile is
  unordered.
- `chance_outcomes(limit)` lists the distinct outcomes with probabilities
  if there are at most `limit` of them, else reports "large".
- `resolve_chance(rng)` samples one outcome and continues.
- EndTurn resolves the hand discard and the monsters' moves (whose damage
  is already known from their intents), then pauses at the next-intent roll
  or the new draw. So a state paused there already shows the HP lost this
  turn.

### Actions and options

- `Action = Play { card: CardId, target: Option<Slot> } | EndTurn`.
  `CardId` is card kind + upgraded flag. An untargeted card has no target.
- **By-action deduplication:** card instances carry no per-copy state, so
  the same `CardId` on the same target always gives the same result.
  `legal_actions()` lists each distinct action once (three Strikes and two
  live monsters → two actions). A targeted card with one live monster gives
  one action.
- **Afterstate deduplication:** different actions whose deterministic
  results are equal (by `Eq`) are merged into one option.
- `options()` returns each distinct option as one of:
  `Deterministic(state)`, `Chance([(prob, state)])` (small, listed), or
  `Divergent(paused_state)` (large: search stops here).

### Python API

```python
import sts
c = sts.Combat(deck=["Strike", "Defend", "Bash+", ...], encounter="jaw_worm", seed=1)
c.legal_actions()          # distinct actions
c.options(limit=16)        # [(action, kind, [(prob, Combat)])]
c.step(action)             # apply; random events are sampled
c.is_over(), c.won(), c.player_hp()
c.features(card_repr="effects" | "ids")   # dict of numpy arrays, see below
c.render()                 # text view of the board
sts.action_name(action)    # "Bash+ -> slot 1", "EndTurn"
sts.search_action(c, evaluator, limit=16, sample_k=0)
sts.greedy_action(c); sts.random_action(c, seed)
```

`features()` returns: player vector (HP, max HP, block, energy, powers),
monsters `[5, M]` (HP, block, powers, intent as primitives), and each pile
(hand, draw, discard, exhaust) as a list of per-card vectors. With
`card_repr="effects"` a card vector is its cost, flags and effect-primitive
amounts. With `card_repr="ids"` it is a one-hot card id, with an "unknown"
slot for unseen cards. Powers are one dimension per power kind plus an
`unknown` dimension in both modes (see Amendment 1).

## Agents

- **Random**: a uniformly random legal action.
- **Greedy**: hand-written single-card heuristic (kill if possible, block
  incoming damage, else most damage per energy).
- **Search**: depth-limited expectimax over the current turn. Deterministic
  and small-chance options are expanded (averaging over listed outcomes).
  Divergent options and EndTurn become leaves scored by the evaluator.
  States seen twice in one search reuse their score (transposition cache via
  `Hash`). `sample_k > 0` instead samples k outcomes at divergent nodes and
  keeps searching, for comparing deeper lookahead.
- **Evaluators** (score in [0, 2] = won × (1 + HP left / max HP)):
  - Heuristic: hand-written formula over the effect features.
  - Learned, effect features: a small PyTorch value net. Each pile is
    encoded by summing per-card vectors through a shared layer ("Deep
    Sets": order-free and any pile size), then an MLP gives the score.
  - Learned, id features: the same net fed `card_repr="ids"`. This is the
    control for the generalisation test.
  Learned nets run in Python. Search calls them in batches (all leaves of
  one search at once) to keep the Python cost down.

No GPU on this machine: training is PyTorch on CPU (16 cores) with small
nets. Self-play runs in Rust on all cores.

## Generalisation test

- **Held-out cards:** Twin Strike, Iron Wave, Thunderclap, Pommel Strike,
  Uppercut. Each is a new combination of primitives that training cards
  already use (multi-hit, damage + block, AoE + Vulnerable, damage + draw,
  Weak + Vulnerable).
- Training data: games played by Search + heuristic evaluator with decks
  drawn only from the other cards. Target: final combat score.
- Test set: games whose decks contain held-out cards.

## Checks (all runnable by a program)

1. `cargo test`: one test per card and monster move with values from the
   wiki (damage, block, debuffs, upgrades, move-pattern rules), plus chance
   tests: listed outcome probabilities sum to 1 and match sampled
   frequencies within tolerance over 100k samples.
2. Fuzz: 100,000 random-agent combats over all encounters with no panic,
   and after every step: 0 ≤ HP ≤ max HP, energy ≥ 0, card counts conserved
   across piles (except added/exhausted cards), combat ends within 200 turns,
   `legal_actions()` has no duplicates, every legal action applies, and
   untargeted cards never list a target.
3. Determinism: same seed and same actions → identical final state.
4. Speed (release, one thread): ≥ 100,000 random combats per minute, and
   `clone()` under 1 µs on a typical state.
5. Strength, `scripts/eval.py`: 500 seeded combats per group (hallway /
   elite / boss), decks = starter and starter + 5 random in-scope cards.
   Prints win rate and mean HP lost per agent. Pass: greedy beats random,
   Search + heuristic beats greedy on boss win rate by ≥ 15 points and on
   hallway HP lost by ≥ 20%.
6. Generalisation, `scripts/generalise.py`: train both learned nets on the
   same data and report value-prediction error (MSE vs. final score) on
   training-card games and on held-out-card games. Pass: on held-out-card
   games, the effect-feature net's error is ≥ 20% lower than the id-feature
   net's. Also report Search win rate with each net on held-out decks
   (reported, not gated).
7. Python: the maturin wheel installs, and all scripts run end to end.

## Demo deliverable

- `python scripts/eval.py`: strength table.
- `python scripts/generalise.py`: the generalisation table.
- `python scripts/replay.py --encounter slime_boss --agent search --seed 3`:
  turn-by-turn log showing the options considered and their scores.

## Build order

1. Engine core: state, multiset draw pile, effect primitives, chance nodes,
   starter cards, Cultist and Jaw Worm, random agent. Checks 1–3 for this
   subset.
2. The rest of the cards, monsters and powers. Checks 1–3 in full.
3. Options, deduplication, greedy, Search + heuristic. Checks 4–5.
4. PyO3 bindings, features, replay. Check 7.
5. Self-play data, both learned nets, batched search with a Python
   evaluator. Check 6.

## Amendment 1 (2026-10-23)

Corrects a claim about never-seen powers. The agent still decides well while
a power it doesn't know is active (for example one put on it by an enemy or
a scenario): the engine applies the power's effects, so they already show in
every afterstate it compares, and the unknown token is the same across
those options. What it can't do is value an option whose main effect is
*granting* an unknown power (when to play such a power card), because there
only the token differs. Only change: `features()` maps any power without
its own dimension to the `unknown` dimension instead of failing. Lands in
step 4.

## Amendment 2 (2026-10-23)

Adds a transfer test: nets trained only on Ironclad games play the Silent.

**Scope added**
- Silent: 70 HP, relic Ring of the Snake (draw 2 extra cards on turn 1).
  `Combat(character="ironclad" | "silent", ...)`.
- Silent starter: 5 Strike, 6 Defend, Neutralize. Survivor is replaced by a
  Defend for now (it needs a discard choice). Silent's Strike and Defend are
  their own card kinds with the same effects as Ironclad's, as in the game:
  new ids for the id net, identical vectors for the effect net.
- Tier A cards (new combinations of primitives Ironclad training uses):
  Neutralize, Sucker Punch, Leg Sweep, Quick Slash, Backflip, Deflect,
  Slice, Dagger Spray, Blade Dance, Cloak and Dagger, and the Shiv they
  create (0 cost, 4 damage, exhaust).
- Tier B cards (Poison, which grants enemies a power Ironclad training never
  sees): Deadly Poison, Poisoned Stab, Bouncing Flask. Poison power: at the
  start of its turn the monster loses HP equal to its Poison, then Poison
  drops by 1.
- Values from slaythespire.wiki.gg, base and upgraded.

**Check 8, `scripts/transfer.py`**
- Uses the two nets from check 6 unchanged (trained on Ironclad only).
- Test games: Silent starter + 5 random cards, all encounter groups.
  Tier A decks draw from tier A only; tier B decks draw from tiers A and B.
- Tier A (gated): value-prediction error (MSE vs. final score). Pass: the
  effect-feature net's error is ≥ 20% lower than the id-feature net's.
- Reported, not gated: tier B errors, and Search win rate and mean HP lost
  with each net and with the heuristic evaluator, for both tiers.
- Engine checks 1–3 extend to the new cards, Poison and the Silent starter
  (per-card wiki tests, fuzz over Silent decks, determinism).

**Step 6** (after step 5): Silent content, Poison, Ring of the Snake,
character selection, then check 8.

## Amendment 3 (2026-10-23) · built 6115cef

A win is judged by absolute HP lost, not by HP left as a fraction of max HP
(max HP doesn't change how well a combat was played).

- Score: loss = 0; win = 2 − HP lost / 100, where HP lost = start HP − HP
  after end-of-combat healing (e.g. Burning Blood), floored at 0. What the
  next combat starts with is what counts, so a loss that the relic heals back
  costs nothing, as in the game. Any win still beats any loss (HP lost < 100
  for every in-scope character), and the 0–2 scale stays.
- Engine `score()`, the heuristic evaluator's estimate, and every place that
  reports or trains on the score follow it. Check 5's table already reports
  win rate and mean HP lost and doesn't change.
- Re-run self-play, retrain both nets, and re-run checks 6 and 8 with the
  new targets. Same pass bars.

Steps: one delta step after step 6.

## Amendment 4 (2026-10-24): triggers and conditions · built 0048487

Folded from `docs/specs/triggers-and-conditions.md` (git history keeps it).

- **Hook powers as data** (`engine/src/hooks.rs`): each power kind maps to a
  const table of `Hook { trigger, condition, effects }`; the state keeps
  (power, stacks), and hook effect amounts are per stack. Triggers:
  `OwnerTurnStart`, `OwnerTurnEnd`, `CardPlayed { by: Owner | Opponent }`,
  `OwnerLostHp { from: Attack | Card | Any }`, `OwnerDied`. Conditions
  (shared with card rows): `Always`, `CardType`, `TargetIntendsAttack`,
  `TargetHas(power)`, `CardsPlayedThisTurnBelow(n)`. Ritual, Curl Up,
  Enrage, Metallicize, Spore Cloud, LoseStrength and Poison run as hooks;
  Strength, Dexterity, Vulnerable, Weak, Frail and Artifact stay built-in
  modifiers. Hooks run in power-kind order, owner before others; a hook
  that decides the combat ends it at once. Timing details are in
  `docs/decisions.md`.
- **Card rows**: a card's effects are rows (trigger, condition, effects),
  run in order, each condition checked when its row is reached. The state
  counts `cards_played_this_turn`. Clash's hand rule stays a play condition.
- **New content** (wiki values, base and upgraded): training pool Spot
  Weakness, Dropkick, Combust, Brutality (Innate upgrade), Rupture; held out
  of every training set (`held_out_cards()`, check 9 only): Metallicize,
  Demon Form, Rage, Go for the Eyes, FTL.
- **Fits with**: `engine/tests/golden.rs` replays 9000 seeded random games
  recorded on the pre-hook engine; existing content is step-for-step
  identical.
- **Features**: cards and hook powers encode as sets of rows (trigger,
  condition with an `unknown` slot each, condition parameter, effect
  vector, scaled by stacks); a card that grants a hook power carries that
  power's rows. Vocabularies replace the `base`/`full` layouts and are saved
  in the model meta. Nets are nested Deep Sets (rows → card or entity →
  pile). `card_repr="ids"` stays the control, with power ids too.
- **Check 9, `scripts/granting.py`**: at every decision where a held-out
  card is playable (search + heuristic games, decks with ≥ 2 held-out
  cards), each net's search gives the gain of playing it over the best
  other option. Pass: the effects net's mean absolute gain difference from
  a reference effects net (trained with the held-out cards) is ≥ 20% lower
  than the ids net's, over Metallicize, Demon Form, Rage and Go for the
  Eyes; FTL is reported. **Currently fails** (18.3%); see
  `docs/decisions.md`.

## Amendment 5 (2026-10-24): evaluation bench · built 5d9c3bd

Folded from `docs/specs/eval-bench.md` (git history keeps it). Usage is in
`README.md`; the first results are in `docs/research/bench-baseline.md`.

- **Outcome:** one command scores any evaluator (heuristic, saved net,
  `module:callable`) on fixed sets and reports prediction, decision quality
  and playing strength side by side, on training and held-out cards. Combat
  only; it trains nothing and changes no engine, search, score or features.
- **Sets** (`scripts/bench_sets.py`, committed under `data/bench/`):
  *standard* (starter + 5 random cards, all encounter groups; halves train,
  held_out, silent_a, silent_b), *families* (AoE, Skill-heavy, Multi-hit,
  Setup, Debuff: starter + 3 role cards + 2 shared fillers, against all 15
  encounters; the held-out version swaps only the role cards), and *tight*
  (the families at the start HP where search + heuristic wins ~50%, found by
  bisection and saved in `calibration.json`; rerun only with
  `--recalibrate`, ~15 min). Held-out = check 6's plus check 9's cards.
- **Decisions** (`scripts/bench_decisions.py`): 1,000 states per tight half,
  replayed from spec + action prefix, each option scored by a cached
  reference search (limit 32, sample_k 8, 2 turns, mean over 3 seeds;
  `reference.json`, stale-checked by the decisions file's hash).
  *Contested*: reference best − worst ≥ 0.05.
- **Metrics** (`scripts/bench.py`, `scripts/bench_compare.py`): static and
  search-value MSE against the final score; regret and pairwise ranking
  accuracy against the reference, on all, contested and uncapped
  decisions; win rate and HP lost on tight and standard sets; held-out
  minus train gaps; 95% intervals (bootstrap seed 0, Wilson). Reruns are
  byte-identical; one evaluator takes 30 s (heuristic) to ~3 min (nets).
- **Representation** (`scripts/bench_probes.py`): an aliasing audit over
  saved decisions and 15 minimal-pair probes whose order the reference
  fixes.
- **Checks:** `scripts/tests/test_bench.py` (determinism, 40–60% calibration
  on fresh seeds, reference self-regret 0 and ranking 100%, random option
  values rank at chance, planted alias flagged, probe orders, identical
  reruns).
