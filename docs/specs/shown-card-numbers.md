# Shown card numbers and the exhaust pile hidden (two feature flags)

Status: closed (2026-11-10, built and in use; flags @sn1/@xh1 (shown_numbers, exhaust_hidden); decisions 'Shown card numbers and exhaust hidden as built'; lane closed fail 2026-11-10).

Lane `shown-card-numbers` step 1 (charter `lane/shown-card-numbers`;
evidence `docs/research/pile-prices-2026-11-09.md`). Confirmed on the
owner's behalf, 2026-11-10.

**How it moves the goals.** Goal 2: today's nets price a card in the piles
at about 0.2 correlation with its played-out worth; the zero-shot reads
showed card numbers as the game shows them (+0.060 on attack pairs with
Strength or Weak) and the exhaust pile hidden (+0.024 on all pairs) lift
that without training. Goal 1: shown numbers follow from the rules, so a
generated attack's shown damage comes free on any pack. We'll know from
step 2's play read (cell gauntlet, `--against` the one-turn control, by
stratum); this spec only makes the flags exist and match the zero-shot
scripts.

## Outcome

Two encoder flags, off by default, reachable from a player string, that
reproduce `results/probes/pile-prices/scripts/zs.py`'s `shown()` and
`zs_noex.py`'s `noex()` inside the Rust encoder, so search plays with them.

Non-goals: training with the flags (a later lane); any other card number
(status cards, Hemokinesis, expression damage, Vulnerable on the target).

## Behaviour

- **shown numbers** (`@sn1`): for every card entry of a state, after its
  cached vector is copied: where the card's `hits_*` column is > 0, its
  `damage_*` column becomes `max(0, d + Strength x hits)`, then
  `floor(x 0.75)` when the player's Weak > 0 (the whole total, as zs.py);
  for single, all and random damage. Where `block` > 0 it becomes
  `max(0, b + Dexterity)`, then `floor(x 0.75)` under Frail (zs.py's order:
  the floor before the clamp; equal for these inputs). Strength, Dexterity,
  Weak and Frail are the player's powers in that state. Applies to every
  pile, generated cards too. Effects mode only (ids mode has no such
  columns: the flag does nothing there).
- **exhaust hidden** (`@xh1`): the exhaust pile's card counts are written
  as 0 (entries stay, so the layout is unchanged).
- Both off: the encoding is bit-identical to today's.
- Wiring: `Encoder::with_shown_numbers` / `with_exhaust_hidden`;
  `sts.Features(..., shown_numbers=False, exhaust_hidden=False)` and
  `NetEvaluator` config keys of the same names;
  `stsnet.rust_evaluator(..., shown_numbers=False, exhaust_hidden=False)`;
  `bench.player_settings` accepts `@sn1` and `@xh1` (only the value 1),
  each at most once. A gauntlet read of an arm against the plain control
  declares `--vary price`.

## Fits with

- Golden file and `rules_version`: unchanged (no engine rule touched);
  `cargo test` pins it.
- Old nets and players without the flags: identical scores
  (`series_check` PASS; Rust test: flags off equals today's batch).
- Speed with both off: the encoder within +10% (build step 4).
- `how/player-strings` fact and README's player-string list gain the two
  settings.

When in doubt: prefer matching zs.py exactly over matching the game.

## Scope

`py/src/features.rs`, `py/src/lib.rs` (Features and NetEvaluator config),
`scripts/stsnet.py` (`rust_evaluator`), `scripts/bench.py`
(`player_settings`), their tests, README's player-string lines, the parity script
`scripts/shown_numbers_parity.py`. Off limits: the engine
crate, net architecture, training code, stored nets.

## Verification

- Rust unit tests (features.rs): a state with Strength 2 and Weak holding
  Twin Strike and Defend under Dexterity 1 and Frail gets the zs.py values;
  flags off equals the plain batch; exhaust hidden zeroes only pile-3
  counts.
- Python test (`scripts/tests/test_bench.py` or nearby): `@sn1@xh1` parses;
  `@sn2` refused.
- Parity (end to end): `scripts/shown_numbers_parity.py` encodes `pairs.jsonl`'s states with
  the Rust flags and with zs.py's numpy transforms: arrays equal, and the
  correlations 0.218 (attack pairs with Strength or Weak, shown), 0.203
  (all, hidden) and 0.221 (all, both) within 0.005.

## Build steps

1. Encoder flags + Rust tests (features.rs). Check: `cargo test -p sts`
   (the py crate's tests) green, golden test green.
2. Python wiring (lib.rs, stsnet.py, bench.py, README) + parse test. Check:
   maturin build into the worktree's own target, parse test green.
3. Parity script. Check: its printout within 0.005 and arrays equal.
4. Speed and identity with both off: `series_check` dump/compare (old
   module against this build, the 10-29 net) PASS; `series_speed` times
   engine-only binaries (`bench.exe`, `search_speed.exe`) and this change
   leaves the engine crate untouched, so the encoder's own time stands in
   (`fixed_states()`, encode and `NetEvaluator.score`, best of 7,
   interleaved old/new) within +10%.
