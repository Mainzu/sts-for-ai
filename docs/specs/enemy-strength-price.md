# Enemy-Strength price at the leaves

Status: closed (2026-11-01, read: decisions "Enemy-Strength price fails at run level").

## Why (goal 2, and goal 1)

The HP bonus (`@hpb0.01`) made the champion level with the heuristic over
an Act-1 run, but it feeds Gremlin Nob: Nob gains Strength for every skill
the player plays, and the bonus buys block now while one-turn search
leaves Nob's extra Strength to the net, which under-prices it. Skills per
Nob fight: heuristic 1.32, bare net 1.68, champion + bonus 2.28 (4.13 at
c 0.04); Nob wins at 70 HP 0.994 / 0.983 / 0.972 / 0.833
(`nob_probe.py`, results doc "Act-1 gauntlet"). First-elite deaths in the
gauntlet: 12 vs the heuristic's 1. The heuristic already prices this
(`HookRates::strength_per_skill`, Strength as two turns' damage).

A search-time price on Strength enemies hold is the same kind of fix as
the HP bonus: no training, read on fixed nets with no training luck
(review 2026-11-01b direction 4). It prices a primitive (Strength), not an
encounter, so it carries to custom monsters that scale (Ritual, Enrage,
any generated Strength gain): that's the goal-1 link. How we'll know: Nob
wins and skills per Nob fight move to the heuristic's, then gauntlet
clears rise over the champion + bonus.

## Outcome

A player setting `@esp<k>` that subtracts `k x clamp(score / 2, 0, 1) x
(sum of living monsters' Strength)` from each leaf score, alone or with
`@hpb<c>` (`<net>.pt@hpb0.01@esp0.02`). Off by default: nothing re-pins.

Non-goals: learning the price (that's what the survival-score arms test),
other monster powers (Vulnerable, Weak, Ritual's rate), a per-encounter
price, two-turn tuning (read later if the one-turn read passes).

## Behavior

- The term uses the leaf's own monster Strength, not a change from the
  root: every option at one decision shares a root, so ranking is the
  same, and a Strength-down card (Disarm-like) earns a credit.
- Monsters at 0 HP (dead) count 0. Negative Strength counts as negative.
- The `clamp(score / 2)` factor matches the HP bonus (a position with no
  win chance doesn't care about Strength).
- `@esp` with a survive score net is refused, like `@hpb` (it would price
  future HP twice with the survival head).
- Setting order in a spec string: `@hpb` first, then `@esp`; either may be
  absent. Anything else after `.pt` is an error naming the spec.

## Fits with

- HP bonus: `@hpb<c>` alone scores bit-identically to today (existing test
  in `py/src/lib.rs` "hp_bonus" and `py/tests/test_hp_bonus.py`; the
  latter's `test_player_spec` already fails on main for an unrelated
  reason, see decisions "Survival score": leave it as is).
- Ensembles (`a.pt+b.pt`): members carry their own prices; an ensemble
  string with `@` stays refused (as today).
- `bench.split_player`, `bench.load_evaluator`, `ladder.py`, `gauntlet.py`,
  `nob_probe.py` take player specs: they pass the string through, so they
  need no change beyond `load_evaluator` parsing.
- The champion file (`results/ladder/champion.json`) is unchanged.

## When in doubt

Prefer the HP bonus's exact pattern (a field next to `hp_bonus`, applied in
the same places) over a general "prices" framework.

## Scope

May change: `py/src/lib.rs` (PyNet config key `enemy_strength_price`, the
NetEval member tuple, the add-bonus function, its Rust test),
`scripts/stsnet.py` (`rust_evaluator` kw), `scripts/bench.py` (spec
parsing), Python tests, README player-spec lines. Off limits: the engine
crate (`engine/src`), features and encoders, training code, the heuristic,
the solved DB.

## Decisions taken (manager; reversible)

- Absolute leaf Strength, not change from fight start (no start-Strength
  field exists; ranking is the same within a search).
- Same win-chance factor as the HP bonus.

## Verification

1. Rust test next to the hp_bonus one: on the existing leaf states plus a
   Gremlin Nob state with +3 Strength, `score = net + hp term - k x
   clamp(net/2) x strength_sum`, within 1e-6; k 0 is bit-identical to
   today.
2. Python test: `load_evaluator("<test net>.pt@hpb0.01@esp0.02")` builds;
   `@esp0` scores bit-identically to `@hpb0.01`; `@esp` on a survive net
   raises; a bad suffix raises naming the spec.
3. End-to-end: `nob_probe.py --players <champ>@hpb0.01 <champ>@hpb0.01@esp0.01
   ...@esp0.02 ...@esp0.04` runs and prints skills per fight.

## The experiment (pre-registered)

- Step A, `nob_probe.py` (180 Nob fights at 70 HP): k = 0.01 / 0.02 / 0.04
  with `@hpb0.01`. A k **qualifies** if Nob wins >= 0.985 and skills per
  fight <= 1.8. None qualifies: record that a Strength price doesn't fix
  the Nob regression and stop.
- Step B, the qualifying k with the fewest skills: gauntlet 500 sequences
  (0-499), paired with `...hpb0.01-bd6d62.json`. **Pass:** clears >= +0.03
  and >= 2 se. Then run-HP (no worse than champion by > 1 HP) and the
  ladder (lead >= -0.005) before promotion. Between 0 and +0.03: run
  sequences 500-999 and pool; pass at >= +0.02 and >= 2 se pooled.
- Noise: gauntlet se ~0.016 per 500 paired sequences; Nob-only effect on
  clears is at most ~0.02 (12 first-elite and ~16 second-elite Nob deaths
  per 500), so the gauntlet pass needs gains elsewhere too (other
  monsters that gain Strength: the Cultist's Ritual, the Guardian, the
  louse's Grow); a Nob-only fix reads as "between". The price may also
  cost where Strength doesn't matter much: read deaths per encounter.

## Don't guard

Strength on the player (not priced here); monsters with huge Strength
(clamp not needed: the factor is bounded by the score).

## Build steps

1. Rust: config key `enemy_strength_price` (f32, default 0) on PyNet;
   member tuple gains it; apply with the HP bonus; Rust test (1). Build the
   wheel, swap the `.pyd` per AGENTS.md. Check: `cargo test` for the py
   crate's new test, and `@hpb0.01` scores unchanged on a saved state.
2. Python: `rust_evaluator(..., enemy_strength_price=0.0)`,
   `load_evaluator` parses `@hpb<c>@esp<k>`; tests (2); README line.
   Check: test file passes; `nob_probe.py` smoke with `--threads 2` on 4
   fights (add a `--limit` if missing).
3. Step A (~10 min on 4 threads), then step B as a job (~10 min).
