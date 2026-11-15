# Sampled-draw leaf

Status: closed (2026-11-03, built through step 3, the screen failed so step 4 did not run; results doc "Sampled-draw leaf screen"; decisions "Lane cheap-depth closed").

Lane `cheap-depth`, approach 2 of `docs/research/approach-review-2026-11-02.md`
("Sampled-draw leaf"). Status: built through step 3; the screen failed (results doc "Sampled-draw leaf screen"), so step 4 does not run.

## Outcome

One-turn search scores each end-of-turn leaf after the next hand is drawn:
at an `EndTurn` leaf it samples k draws (common random numbers across
sibling options), plays out the monsters' turn and the player's turn-start
hooks up to the next decision, and scores those hand-in-view states with
the net. Played as the player setting `@dl<k>`.

**How it moves goal 2, and how we'll know.** Two-turn search is the
product's largest gain (+0.154 clears and +6.1 end-HP over one turn on the
headline, fact measurement/headline@two-turn) but costs about 115-140x
one turn per sequence (fact how/two-turn-search), which keeps it out of
the reward chooser and makes two-turn self-play expensive. The net fits
post-draw decision states far better than paused end-of-turn states, and
two-turn's gain sits where the next hand decides. If a draw leaf recovers
a real part of that gain at a few times one-turn's cost, depth becomes
affordable in the chooser and in data generation. We'll know from the
lane's measure: the one-turn cell gauntlet read `--against` the one-turn
control (protocol, end-HP and clears) and the wall-time ratio, after a
near-free puzzle screen. Turn-start hooks firing inside the leaf also
touch goal 1's measured novelty class (fact cause/novelty-is-horizon).

Non-goals: no second-turn tree (that is two-turn search); no change to
two-turn play or the product; heuristic and Python-callable evaluators get
no draw leaf (the setting lives on the Rust net evaluator); no training on
draw-leaf games in this spec; the bias-audit leaf-value comparison of the
review's step A is left out (the audit file keeps no state bytes; the
puzzle regret measures the same leaf at the decision level, exactly).

## Behavior

- `SearchConfig.draw_k: u32`, default 0 (off: search unchanged, bit for
  bit). With `draw_k = k > 0`, wherever search would make a leaf of the
  state after `EndTurn` (the last searched turn: with `turns > 1` and
  `sample_k > 0` that is the last turn's `EndTurn`), it instead expands
  that state in a turns-left-0 table:
  - a finished combat scores exactly, as now;
  - a state awaiting an action is a leaf (scored by the evaluator);
  - a chance event with at most `limit` outcomes is listed exactly (as
    now); a larger one (the draw) takes k samples, weight 1/k each, with
    `sample_rng(seed, 0, turn, ord, i)`, `ord` counting sampled events
    since the `EndTurn`; nothing else about the state feeds the RNG, so
    sibling options see the same draws (common random numbers);
  - past `max_nodes` the state becomes a leaf and counts as a cut, as now.
- The principal line still stops at `EndTurn`; root option grouping,
  values of finished combats and the end-HP price are unchanged.
- Python: `stsnet.rust_evaluator(..., draw_k=0)` carries it in the net's
  prices; the evaluator's search config takes it (as `hp_end_bonus` does),
  so every path that searches with that evaluator (`sts.search`,
  `sts.run`, `sts.play_on`) uses it. Ensemble members must share it.
- Player string: `@dl<k>` after the net, e.g.
  `runs/<net>/model.pt@hpb0.01@dl4`; `bench.player_settings` parses it (an
  integer k >= 1; at most once). Caches (`ladder.player_key`) and the
  gauntlet's `--vary price` already include everything after the `@`.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| search.rs one- and two-turn search | `draw_k = 0` gives identical results | the existing cargo search tests, unchanged; new `draw_leaf_off_is_unchanged` |
| line-step / principal line | stops at `EndTurn` with or without the draw leaf | new `draw_leaf_line_stops_at_end_turn` |
| Rust net evaluator prices | `@hpb`, `@hpe`, `@esp`, `@sc` parse and price as before | existing test_bench / test_net player-setting tests |
| ladder caches, gauntlet settings | a `@dl` player never shares a cache key with the plain one | new `test_draw_leaf_player_key` |
| queued pinned jobs | a pinned job loads its snapshot's `sts`; main's `sts` is swapped only under `main-merge` after `jobs.py impact sts` | AGENTS.md gotchas |

## When in doubt

Prefer leaving plain search byte-identical over sharing code paths.

## Scope

May change: `engine/src/search.rs` (config field, draw-leaf expansion,
tests), `py/src/lib.rs` (prices field, evaluator config, ensemble check,
config constructors), `scripts/stsnet.py` (`rust_evaluator` argument),
`scripts/bench.py` (the `@dl` setting), a new
`scripts/analysis/draw_leaf_screen.py`, tests under `scripts/tests/`, the
results doc and this spec.

Off limits: game rules and the codec (the rules version must not change),
the solver and solved DB, two-turn play (`depth_paired`, `ladder.play_two_turn`),
`configs/product.json`, charters and `jobs/lanes.json`.

## Decisions taken

- The setting rides on the net evaluator (`@dl<k>`), not new keyword
  arguments on every `sts` entry point: one place, and caches and the
  gauntlet's settings comparison pick it up for free. Alternative: a
  `draw_k=` keyword on `search` / `run` / `play_on` plus gauntlet and
  ladder flags (about 3x the plumbing).
- The charter's "costs over 1.5x" is read as 1.5x one-turn's wall time on
  the same read (the lane's "deeper at the same cost"); the screen
  measures cost at k = 1, 2 and 4, so the cell read uses the largest k
  under that bar. Each read also reports the ratio to two-turn's cost.

## Outside assumptions

None outside the project. Inside it, from the review: the net values
post-draw decision states better than paused ones (held-out MSE 0.011 vs
0.092), checked indirectly by the screen's regret.

## Verification

Tests first:
- cargo `draw_leaf_off_is_unchanged`: on a mid-fight state, `draw_k = 0`
  gives the same options, values, nodes, leaves and line as the config
  without the field set (default).
- cargo `draw_leaf_scores_drawn_states`: with a recording evaluator and
  `draw_k = 2`, every evaluated leaf awaits an action and has a turn
  counter one above the root's, unless the state is finished; no
  evaluated leaf is a paused `EndTurn` afterstate.
- cargo `draw_leaf_common_draws`: two root options that both end the turn
  without playing a card reach leaves whose hands are drawn by the same k
  samples (same multiset of hands), and the same seed gives the same
  values twice.
- cargo `draw_leaf_line_stops_at_end_turn`: the line ends with `EndTurn`.
- Python `test_draw_leaf_player_settings`: `@hpb0.01@dl4` parses to
  hp_bonus 0.01 and draw_k 4; `@dl4@dl2` and `@dl0` are refused; `@dl` in
  `ladder.player_key` differs from the plain player.
- Python `test_draw_leaf_search`: `sts.search` with a net evaluator built
  with `draw_k=0` matches one built without it; with `draw_k=4` the same
  options come back with different values and more leaves.

End-to-end check: the screen (build step 3) runs on the built module and
reports regret by horizon and time per decision for plain, k = 1, 2, 4.

Don't guard: heuristic or Python evaluators with a draw leaf; `draw_k`
above about 16 (memory is the user's problem); combining `@dl` with
two-turn play.

## Build steps

1. **Draw leaf in search.rs** with the four cargo tests (written first;
   `draw_leaf_off_is_unchanged` passes on the unchanged code once the
   field exists). Check: `cargo test -p sts-engine search` green, all
   existing engine tests green.
2. **Plumbing** (lib.rs prices and config, `rust_evaluator`, `@dl` in
   bench) with the two Python tests; build the wheel into the lane
   worktree's own pyroot (no swap of main's `sts`). Check: the two tests
   and test_bench / test_net player-setting tests pass on that build.
3. **Screen (CPU minutes).** `scripts/analysis/draw_leaf_screen.py`: the
   448 horizon >= 1 puzzles (`data/bench/puzzles.json`) with the product
   net @hpb0.01 one turn, plain and @dl1 / @dl2 / @dl4: regret overall and
   by horizon (`bench.search_puzzles` / `puzzle_half`), and wall time per
   decision at 1 thread. Pass: regret falls by at least 0.01 from plain's
   at some k with cost at most 1.5x plain; else the lane's stop rule
   fails the leaf here (no cell read). Results go to the results doc.
4. **Cell read (long run, ~3-5 h at 3 threads; needs step 3's pass).**
   Land steps 1-3, swap main's `sts` under `main-merge` (impact check
   recorded), and queue `gauntlet.py play <net>@hpb0.01@dl<k> --sequences
   500 --against results/gauntlet/net1029-hpb0.01.json` on lane
   cheap-depth with its read rule in the note: pass = protocol pass
   (+1.5 HP SPRT) and wall at most 1.5x the control's; that is the lane's
   first cell read, and a fail ends the lane.

Build plan: 4 steps, in-session (lane worker), on Opus. Stop points: step
3's verdict decides whether step 4 runs.
