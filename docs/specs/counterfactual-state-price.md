# Counterfactual state price (`@cf`), step 1: the price and its probe

Status: closed (2026-11-11, fail at step 1 (0 of 4 prices inside their worths), step 2 not built; decisions "Lane counterfactual-state-price closed (2026-11-11)").

Lane `lane/counterfactual-state-price` (charter: `kb get
lane/counterfactual-state-price`; backlog candidate 51). Confirmed under the
mandate (lane worker, 2026-11-11).

**Goals.** Goal 1: every zero-shot cost on record is value that keeps paying
after the leaf (Demon Form's later ticks, Ritual 2, recurring Weak), and
learning prices only the first tick (`cause/novelty-is-horizon`,
`measurement/later-ticks-count@burst5k`: 5k games a group to teach it, at a
held-out cost). A leaf price read from the engine by simulation needs no
games and works for any power, so it carries to content no net has seen. We
know by step 1 here: the term's prices of four perturbations on the
leaf-numbers probe's 167 held-out cells against their worths, no games. Only
a step-1 go builds the search flag and plays it (step 2, a later spec).

## Outcome

`CombatState::cf_price(k)` returns, in HP, the price of every persistent
element of a state (each held power of the player and of each living
monster, Strength and Weak included), found by playing the greedy policy
forward with the element and without it; a probe compares the prices of
four perturbations with their worths.

Non-goals: the search flag `@cf` (step 2, after a go); any learned part;
exact chance (samples with common seeds stand in, see Decisions).

## Behavior

`cf_prices(s, k) -> Vec<(Who, Power, amount, price_hp)>` (new module
`engine/src/cf.rs`), `cf_price(s, k) -> f32` their sum. Over (0 elements, or
`s.is_over()`): empty, 0.

For each element e (one held power on one entity) and sample i in 0..k:
- `with` = s, `without` = s with e cleared (`Powers::clear`). Both play the
  same window with `Rng::new(i)`: chance sampled (`advance`) to the next
  player decision (part 0: the rest of the current round), then the greedy
  policy (`agent::greedy_action`, picks included) to its `EndTurn`, then
  chance to the next decision or the end (part 1: one full round). A
  window stops at the end of combat.
- Each part's value in HP: (HP lost by `without` - HP lost by `with`) +
  q x (enemy HP removed by `with` - by `without`), q = HP the fight costs per
  enemy HP point = `hp_loss_estimate(s)` / living enemies' HP (0 when no HP).
  d0, d1: part 0's and part 1's means over samples.
- Rounds after the window: f = max(`turns_left_estimate(s)` - 1, 0); 0 if
  either line ended in the window. For a duration debuff (Weak,
  Vulnerable, Frail) f is at most amount - 1.
- Growth: if, at part 1's end, the owner's Strength gap (with minus
  without) is larger in size than at the start, the element grows each
  round (Ritual, Demon Form). Its first tick may land after part 1 (Ritual
  ticks after the monster's attack), so part 2 (one more greedy round) is
  played: u = d2 - d1 is the gain a round, round r after part 0 is worth
  d1 + (r - 1) u, g = max(f - 1, 0) rounds remain after part 2 (0 if a line
  ended), price = d0 + d1 + d2 + g d2 + u g(g+1)/2. Otherwise price =
  d0 + d1 x (f+1).
- k = 4 by default (a tunable number; `measurement/` gets the probe's se).

Python: `Combat.cf_prices(k=4)` returns `[(who, power, amount, price)]`
(`who` "player" or the monster slot), `Combat.cf_price(k=4)` the sum.

Probe `scripts/analysis/cf_price_probe.py run`: the leaf-numbers probe's
fights and leaves (same sets, net, `leaf_rows`' slot and worth rules), per
leaf the term's change `cf_price(edit) - cf_price(leaf)` for:
- `str-2` and `weak+1`: the probe's perturbations and worths;
- `ritual+2` (Ritual 2 on the first living monster) and `demonform+2`
  (Demon Form 2 on the player): worth = a greedy rollout to the end of the
  fight (at most 30 rounds), with and without the edit, 4 samples, same
  HP formula (enemy HP left at the cap priced at q).
Output `results/cf_price/probe.json`, a table per set (term change, worth,
`mispriced` by the probe's rule: outside half to twice the worth by 2 se),
se over fights.

## Fits with

- Search, the heuristic, the evaluator and all leaf flags: untouched (new
  module, read-only on the state). Golden and `series_check` unchanged:
  `cargo test` (golden.rs) pins it.
- `leaf_numbers_probe.py`: reused by import, not changed.
- `py/src/lib.rs`: two new methods only.

## When in doubt

Prefer the charter's plain form (one window, scaled by remaining rounds)
over extra corrections.

## Scope

May change: `engine/src/cf.rs` (new), `engine/src/lib.rs` (module line),
`engine/tests/cf_price.rs` (new), `py/src/lib.rs` (two methods),
`scripts/analysis/cf_price_probe.py` (new), this spec, the lane's results
doc. Off limits: search, heuristic, agent, state rules, net code, configs.

## Decisions (on the owner's behalf; also in docs/decisions.md)

- Policy: the greedy policy, not a one-turn heuristic search: a search per
  element per leaf would cost thousands of searches a decision; greedy is
  the engine's cheap hand-written policy. Alternative: `SearchAgent<Heuristic>`.
- Chance: k sampled windows with shared seeds, not exact: draws have too
  many outcomes to list. Alternative: `chance_outcomes` where listed.
- Worths for Ritual and Demon Form: a greedy rollout to the fight's end
  (the probe has no worth for them; it checks the term's extrapolation
  against the same policy played out). Alternative: an upper-side formula
  like Strength's, which needs the deck's hits per turn.
- "Inside the measured range": the leaf-numbers probe's rule (not
  mispriced: within half to twice the worth by 2 se, per set) and precise
  (the term's se at most a quarter of the worth, so a wide band can't pass);
  inside when every set is both. The 3-cell smoke run had se up to 20 HP. The strict charter ranges (Strength -2 +9.9 to +13,
  Weak +1 +2.2 to +2.7 as set means) are printed beside it.

## Verification

Tests first (`engine/tests/cf_price.rs`, Cultist vs Strikes and Defends):
- `no_elements_no_price`: a state with no powers gives an empty list, 0.
- `enemy_strength_costs`: Strength 3 on the Cultist prices negative; its
  size grows with the Cultist's HP (more rounds).
- `player_strength_pays`: player Strength 2 prices positive.
- `weak_is_capped`: Weak 1 on the monster prices at most Weak 3's price
  and above 0.
- `ritual_grows`: Ritual 3 on the Cultist prices below (more negative than)
  Strength 3 once remaining rounds exceed 3.
- `deterministic`: two calls give the same prices.
End-to-end: `cf_price_probe.py run --limit 3` runs and writes the table.

## Build steps (in-session)

1. `cf.rs` with the tests above; `cargo test --test cf_price` and golden pass.
2. The Python methods; build the wheel to `target/wheels` (no swap in
   main); a smoke call from the worktree's own install (`py` pyroot).
3. The probe; `--limit 3` check; queue the full probe (about 0.3 thread-h)
   pinned to the lane's HEAD with a `--check` (it decides the checkpoint
   `step1-prices`).
