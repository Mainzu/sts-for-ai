# The evaluation bench, exact puzzles and the champion ladder

These tools compare players on fixed sets of fights and positions. The
bench plays the same fights for every player. The exact puzzles are
positions where a solver has worked out the true value of every move. The
champion ladder pits a new net against the current champion.

## Evaluation bench

```bash
.venv/Scripts/python scripts/bench_sets.py      # regenerates data/bench/ (deterministic)
.venv/Scripts/python scripts/bench_sets.py --recalibrate   # also reruns tight-fight calibration (~15 min)
.venv/Scripts/python scripts/bench_sets.py --calibrate-silent   # Silent tight fights (tight_silent.json, ~2 h on 8 threads)
.venv/Scripts/python scripts/tests/test_bench.py
```

`data/bench/standard.json` (starter + 5 random cards; halves `train`,
`held_out`, `silent_a`, `silent_b`) and `data/bench/families.json` (matchup
deck families vs every encounter; halves `train`, `held_out`) hold the bench's
combat specs. `data/bench/tight_silent.json` (halves `silent_a`, `silent_b`:
check 8's tier decks per encounter at the Silent's calibrated ~50% start HP,
from `calibration_silent.json`; encounters no HP makes tight stay short) is
the warm-start learning curve's win-rate set. `data/bench/tight.json` is the families' specs at each cell's
calibrated start HP from `data/bench/calibration.json`: the HP where search +
heuristic wins about 50% of that (family, half, encounter), found by bisection.
Cells no HP brings near 50% (won even at 1 HP, lost at full HP, or a win rate
that jumps past 50% in one HP) are listed there as excluded. Calibration only
reruns with `--recalibrate`. See `SPEC.md` Amendment 5 (evaluation bench).

```bash
.venv/Scripts/python scripts/bench_decisions.py   # decisions.json; reference.json if stale (~5 min)
```

`data/bench/decisions.json` holds 1,000 decision states per tight-fight half
(spec plus the action prefix that reaches it; `bench_decisions.replay(d)`
rebuilds the state). `data/bench/reference.json` scores every option of each
with a deeper search (2 turns, 8 samples at large random events, averaged over
3 seeds) and flags contested decisions (best minus worst option >= 0.05).

`data/bench/fixed_silent.json` (`bench_decisions.py --fixed-silent`) holds 500
Silent decisions per standard Silent half, stored the same way. With
`py/tests/golden.py`'s states and `decisions.json` it is the fixed state set
that net-identity checks use (`docs/decisions.md "Contract as built"`):
`scripts/tests/test_contract.py` checks today's feature batches and tiny
pre-contract nets' outputs on it against `scripts/tests/data/contract/`
(`scripts/tests/contract_pins.py` rewrites those pins).

```bash
.venv/Scripts/python scripts/bench.py --evaluator heuristic --out results/heuristic.json
.venv/Scripts/python scripts/bench.py --evaluator models/value_effects.pt --out results/effects.json
.venv/Scripts/python scripts/bench_compare.py results/*.json [--set tight] [--half held_out]
```

`bench.py` scores one evaluator (`heuristic`, a saved net, or
`module:callable`) per set half: prediction (static-value MSE vs final score;
none for the heuristic), decision quality at the saved decisions (regret vs
the reference, ranking accuracy over option pairs the reference separates by
>= 0.05; on all, contested and uncapped decisions) and playing strength (win
rate, HP lost) on the tight fights and the standard set, plus each half's gap
from `train`, all with 95% intervals. Reruns give identical files. About 40 s
for the heuristic and 3.5 min for a net. For scale: a random leaf evaluator
searched through still ranks ~70% of contested pairs right, since search
scores wins and deaths exactly.

The results also hold the representation checks (`scripts/bench_probes.py`):
the pass rate on 15 minimal-pair probes (hand-built states where two first
actions differ in one strategic fact, ordered by the reference search), and
an aliasing audit: saved decisions whose feature vectors match exactly but
whose reference values differ by more than 0.05 (effects features, and a
net's own), with the worst boards rendered.

### Exact puzzles

```bash
.venv/Scripts/python scripts/puzzles.py bench [--rebuild]   # data/bench/puzzles.json (~3 h, 6 threads)
.venv/Scripts/python scripts/puzzles.py --run <run id> [--export]   # a run's games' tails into the database
.venv/Scripts/python scripts/puzzles.py db --stats | --evict
.venv/Scripts/python scripts/explore.py [--port 8765]   # http://127.0.0.1:8765 (read-only): gauntlet, mutate and boss-replay files replayed turn by turn as the net played them (take over at any decision), content, bench puzzles; database and comparison nets picked in the page
```

The exact solver (`engine/src/solve.rs`, `sts.solve`) gives each option's
true expected score from a position: best play at every decision, every
random event fully listed, to the end of combat. Past its node budget (1M
by default) it reports unsolvable rather than an estimate. Solved states
worth keeping (cost >= 1,000 nodes) go into a permanent SQLite database,
`db/solved.sqlite` (gitignored; crate `solvedb`, states stored as decodable
bytes from `engine/src/codec.rs`, rows retired when the rules fingerprint
changes, capped at 5 GB). Curriculum training keeps its own,
`db/train.sqlite`, filled only by its runs' solve steps, so nets never
train on the bench puzzles' tails.

`puzzles.py` walks real games back from their last decision, solving each
one until the first that doesn't fit the budget. `data/bench/puzzles.json`
holds one such puzzle per game for 1,000 tight-fight games per half (search
+ heuristic on fresh seeds), with every option's exact value and outcome
distribution. `bench.py`'s `puzzles` set scores an evaluator's one-turn
search there: accuracy (picks an exactly best option), regret against the
exact best, ranking of option pairs, on all and contested (gap >= 0.05)
puzzles and per horizon (turns before the game's end). It reads only the
file, so it adds about a second. Results: `docs/research/exact-puzzles.md`.

## Champion ladder

`scripts/ladder.py` (`docs/specs/champion-ladder.md`, `ladder-v2.md`)
plays a candidate net against the champion (`results/ladder/champion.json`)
on paired tight2 fights under a sequential test, and `ladder.py runhp`
scores HP lost at run-like start HP against `--against`. Neither ranks nets
for the product (`decision/no-proxy-promotion`); results go to
`results/ladder/`. Options: `ladder.py --help`.
