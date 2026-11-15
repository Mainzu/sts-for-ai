# Finish-faster tie break (spec, lane finish-faster-tiebreak step 1)

Status: closed (2026-11-09, built, off by default, read fail: decisions "Lane finish-faster-tiebreak closed"; measurement/finish-faster-tiebreak@replay).

**Outcome:** a search option, off by default, that breaks exact value ties
toward the line that ends the fight sooner and then toward lower enemy HP,
so easy fights take fewer turns and two-turn reads cost less CPU.

**Goals.** Machine time, which feeds goal 2: the two-turn product's reads
(each about 3.5 thread-h per 250 sequences) are the project's main CPU
spend, and easy-fight turns are a real share of them (playing floors 1-3
one turn deep saved about 30% of the wall time,
`measurement/mixed-depth@headline`). The option changes only which of
several exactly-equal options is played, so strength should stay level.
We'll know from step 2's replay (search nodes and turns per fight with and
without it; kill-fast under 3% of nodes cut) and step 3's 250-sequence read
on `yardstick/cost-savers` (level end HP and clears, wall time cut).

Non-goals: any epsilon (near-ties stay as they are); a change to option
values; training with the option.

## Behaviour

- `SearchConfig::tie_break: bool` (default false). Off, search is
  bit-identical to today: values, options, `action`, `line`, node counts.
- On, every node also carries two keys, backed up with its value:
  - **finish**: an exact won node scores the state's turn counter at the
    win; a lost exact node and every leaf score the horizon (root turn +
    turns searched), later than any win inside it. Lower is better.
  - **enemy HP**: the summed HP of living monsters (0 at a win). Lower is
    better. The engine clears every monster's block at the end of the
    player's turn (`CombatState::end_turn`), so no monster block survives
    that reset and the key is HP alone; content that keeps monster block
    over the reset must add that kept block here. Read at the leaf, so
    damage taken while the monsters act (Poison's tick) counts.
  - A chance node's keys are the probability-weighted means of its
    children's; a decision node takes the keys of the child it picks.
- Picks (each decision's back-up, the root `action`, each step of `line`):
  highest value; on an exactly equal value, lower finish; then lower enemy
  HP; still equal, the first in order, as today.
- Player setting `@tb1` (`scripts/bench.py`), `tie_break` in the
  `NetEvaluator` config (`stsnet.rust_evaluator`) and in `Prices`
  (`py/src/lib.rs`), shared by ensemble members, as `@lcb1` is.

**Fits with:** golden and `series_check` (identical with it off); the
`@lcb1`/`@tsl1` settings (unchanged, combinable); option values (never
changed by the flag, test below); line step (uses the same pick).

**When in doubt:** prefer leaving today's pick over a new rule.

**Scope:** `engine/src/search.rs`, `py/src/lib.rs` (Prices and config),
`scripts/bench.py`, `scripts/stsnet.py`, tests under `engine/tests/` and
`scripts/tests/`, README player-setting line,
`scripts/analysis/depth_paired.py` (the two-turn policy picks each search's
own root option, `picked`, instead of `np.argmax`, so the tie break acts at
the root; identical with it off, since search keeps the first best; every
fight also reports its search `nodes`), `scripts/analysis/depth_probe.py`
(kind `all`: every floor; `read` adds nodes and turns by fight type), `content/wording.json` only
if the wording test asks. Off limits: the score, the evaluator, any default.

## Verification

- `engine/tests/tie_break.rs`: with an evaluator scoring every leaf 2.0 (a
  won exact node at full HP also scores 2.0), a kill now beats a tied
  option that ends the turn; with an evaluator scoring every leaf 1.0, the
  option leaving lower enemy HP wins; in both the option values equal the
  off run's.
- `scripts/tests/test_tie_break.py`: `@tb1` parses; bad forms refuse; a
  `NetEvaluator` with `tie_break` keeps option values.
- End to end: `cargo test` (golden), `series_check` PASS with the flag
  off (checkpoint tiebreak-off-identical).

Step 2 (replay): `depth_probe.py play --kind all --arm two --limit 330`
(sequences 0-29, every floor) with the product, `@tb1` off and on; the
off arm must reproduce the control file; `read off on` gives `nodes_cut`.

## Build steps

1. Engine option and tests (the checks above). 2. Python plumbing,
`@tb1`, its test. Mode in-session, current model.
