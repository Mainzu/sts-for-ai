# Solver bounds: solve the decisions a long fight blocks

Status: closed (2026-10-28, built and in use; decisions "Solver bounds as built (provisional, 2026-10-28)"; curriculum solve step, puzzles.solve_dataset bounds=True).

## Outcome

The exact solver proves an option can't beat the best one, without solving
it, whenever that option's best possible score is no higher. That lets it
solve the decisions that stop the curriculum's walks today, and walk on to
the decisions one, two and three turns earlier in the same games, which the
training database is missing.

**Why.** The curriculum night's solve steps (`runs/slow-solves-2026-10-28.md`):
of 1,500 walked games, 1,484 stopped before their start and 1,057 (70%)
stopped at their **last** decision, giving no position at all. The typical
stop: one option wins now; another (usually End turn) leads into the rest of
a long fight that 1M nodes can't finish (each turn's draw has hundreds to
thousands of outcomes; one failed attempt can take ~25 min). So the
database keeps only positions with short futures. The exact-only experiment
(`docs/research/learned-play-results.md`, 2026-10-28) shows what that costs:
nets trained on it pick well on its own kind of position (regret 0.006 one
turn out) and badly on the bench games' positions (0.047-0.060), which every
evaluator finds harder.

**Non-goals:** pruning at random events (expectations still need every
outcome); bounds in distribution solves; rebuilding the bench puzzle set
(it stays exact: its option values never carry bounds); the `cost` column
overflow seen 2026-10-28 (separate); healing content itself.

## Behavior

### The bound

- **`upper_bound(state)`** (engine): the highest final score still
  possible from `state`. A won fight scores `2 - max(0, start_hp - hp) /
  100` with the end-of-fight heal (Burning Blood) included, so the bound is
  that score at the highest HP the player could end on:
  `min(max_hp', hp + heal_left + win_heal)`, where `max_hp'` is the max HP
  the player could reach. A finished fight's bound is its score.
- **`heal_left(state)`** (owner's precondition): the total HP the player
  could still gain in this fight, from every source left: cards in any pile
  and in hand, powers on the player, potions, relics, end-of-turn and
  end-of-fight effects, capped at max HP. Sources that can repeat
  (a power healing every turn, a card that returns) count at their most.
  Max HP gains count the same way for `max_hp'`. Generated cards never heal:
  as in the original game, healing cards can't be created mid-fight (the
  owner's rule for this engine too, 2026-10-28), so `heal_left` counts only
  cards already in the fight. When card generation arrives, its pools
  exclude healing cards, and a test checks that no generation pool holds a
  card whose effects `heal_left` counts.
- **Kept honest by the compiler:** `heal_left` classifies every `Effect`,
  `Power` and (later) potion and relic variant in exhaustive matches with no
  wildcard arm, so adding healing content doesn't compile until its bound is
  written. Today no in-fight effect heals: `heal_left` is 0 everywhere and
  the bound is the score of winning at the current HP (plus Burning Blood).

### Pruning (value solves only, opt-in)

- `SolveConfig.bounds` (binding: `sts.solve(..., bounds=True)`), default
  off: every caller keeps today's exact option values unless it asks.
- At a decision, finished children are taken first (they cost nothing).
  After each child's exact value, if the best so far is within `TIE` of
  `upper_bound` of the decision itself, the remaining children are skipped:
  none can do better. Before opening a child, it is skipped if its own
  `upper_bound` is at or below the best so far.
- The decision's value is exact (its best option's), and so are its
  turns left. A skipped option is **bounded**: its value is reported as its
  `upper_bound`, flagged, and is at most the decision's value. Nothing
  bounded is stored as a state's value: only exact values enter the table
  and the database.
- Random events are unchanged: every outcome is solved.
- Distribution solves ignore `bounds` (pruned options would have no
  distribution).

### Storage

- A decision row's options carry the bounded flag (options blob version
  bump; older blobs read as all exact). `lookup` / `fetch` return each
  option as `(actions, value, bounded)`; `solve`'s result gains `bounded`
  (a flag per option).
- A solve without `bounds` never answers its root from a stored row with
  bounded options: it solves the root again (as distribution solves already
  do for value-only rows). Hits below the root need only the state's value,
  which is exact either way.
- `is_trivial`: "all options tied" needs every option exact.

### Where bounds are used

- **Curriculum solve step** (`puzzles.solve_dataset`, so `learn.solve_step`):
  walks with `bounds=True`. The bench build (`puzzles.py bench`) and the
  registry dump keep exact walks. A walked position's `gap` is a lower bound
  when the second best is bounded.
- **`learn.dull`**: a decision is dull only if every option but End turn is
  exact and tied at the best.
- **Training labels** (`exact_examples`, the ladder's exact rung and its
  not-played ranking): a decision state keeps its exact value. A bounded
  option's afterstates get no value label, and enter the ranking term only
  in pairs with an exact option at or above their bound ("that one is at
  least as good"); pairs of two bounded options are skipped. The ranking
  loss is already the one-sided hinge `max(0, v_worse - v_better)`, so such
  a pair is the same term. Plus a one-sided value term on a bounded
  option's afterstates: `max(0, prediction - bound)^2`, at a value
  example's weight, zero whenever the net stays under the bound.
- **Explorer:** a bounded option shows `≤ value`; a pick of one shows its
  regret as `≥ best - bound`.
- **Bench puzzles, trusted zone, gate:** unchanged.

## Verification

- `upper_bound_holds`: over the bench puzzles' positions and their walked
  tails (`db/solved.sqlite`, thousands of exactly solved states), every
  state's exact value is at most its `upper_bound`; a finished fight's
  bound equals its score; with `heal_left` 0 the bound is the score of
  winning at the current HP (Burning Blood included).
- `heal_left_exhaustive`: today's content gives 0 for every state checked;
  the match arms have no wildcard (checked by grepping the function in the
  test, so a wildcard can't slip in).
- `bounds_sound`: on positions both solves finish (bench puzzles, 1M
  nodes), the bounded solve's decision value equals the exact one; each
  exact option equals the exact solve's; each bounded option's exact value
  is at most its bound, and its bound at most the decision's value.
- `bounds_store`: a bounded row round-trips through the database with its
  flags; an unbounded solve asked at that root solves it again and returns
  all-exact options; an old blob reads as all exact.
- `ranking_bounded`: the ranking term pairs (exact, bounded) only when the
  exact value is at or above the bound, skips (bounded, bounded), and the
  one-sided value term is 0 under the bound and grows above it.
- **Measured (the check that decides use):** the night's games re-walked
  with and without bounds on a sample (the 75 games of `s0 r8` and of
  `s1 r5`, the slowest rounds): games stopping at their last decision,
  positions per game and per horizon, time per game. Results to
  `docs/research/learned-play-results.md`.

## Scope

`engine/src/solve.rs` (pruning, ordering, flags), a new bound function next
to the state (`engine/src/state.rs` or its own file), `solvedb` (blob flag,
trivial rule, root-hit rule), `py/src/lib.rs` (binding), `scripts/puzzles.py`,
`scripts/learn.py`, `scripts/train.py` (ranking pairs, one-sided term),
`scripts/explore.py` / `explore.html`, tests in each.

## Steps

1. `upper_bound` and `heal_left` with their tests. Check:
   `upper_bound_holds`, `heal_left_exhaustive`.
2. Pruning in the solver and the binding flag. Check: `bounds_sound`,
   existing solver tests unchanged with bounds off.
3. Storage flags and rules. Check: `bounds_store`, existing solvedb tests.
4. Python consumers (walk, dull, labels, training, explorer). Check:
   `ranking_bounded`, existing curriculum, explore and round tests.
5. Measure the re-walk. Stop point: review with the owner, who decides
   whether the next run walks with bounds.

## As built (2026-10-28)

- `heal_left` is a yes/no `can_heal`: with any heal source left the bound
  is 2.0 (the most a fight can score), which is sound and costs nothing
  while no content heals; amounts per source come with the first healing
  content. Powers are checked through their hooks' effects; a power that
  heals through special-case code in `state.rs` would need adding there.
- In no-death mode the bound is floored at 0 (a win far below 0 HP scores
  under a loss).
- The ladder marks bounded options ranking-only (`bounded` 2): those
  examples' targets are game outcomes, not the bound, so they get no
  one-sided value term. Exact examples' bounded afterstates (`bounded` 1)
  do, at a value example's weight, which puts the exact examples' share of
  the value weight above `exact_share` when there are any.
- An unbounded solve doesn't upgrade a stored bounded row (it solves that
  root again each time; cheap once its children are stored).
- Measured: `docs/research/learned-play-results.md`, "Solver bounds,
  measured".
