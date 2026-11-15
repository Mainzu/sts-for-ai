# sts-for-ai

A Slay the Spire 1 combat engine (Ironclad and Silent, Act 1) in Rust, built for
search and learning: agents choose between resulting states, cards are
data built from effect primitives, and every random event is explicit.
See [docs/concept.md](docs/concept.md) and [docs/decisions.md](docs/decisions.md).


## Start here

This is the public copy of a hobby project: 23 days (23 October to 14
November 2026) of building this engine and of research run largely by AI roles
(Claude sessions with fixed jobs: a steward, a navigator that opens short
research "lanes", lane workers, a curator), with the owner steering. It is
published so that anyone can pick the work up without rediscovering what was
already tried.

- **The shortest way in:** [showcase/llms.md](showcase/llms.md), the project's
  showcase page as plain text: what was built, what was found, every number
  with the test it was measured on. [showcase/index.html](showcase/index.html)
  is the same page with charts. [showcase/llms-full.md](showcase/llms-full.md)
  adds every real-game fight, a line for each thing tried, and the
  statistics behind the page.
- **Where it stands:** the best player is the 29 October net searching two
  turns deep (`configs/product.json`); the net that played the real game is
  `runs/2026-11-10-packnet40k-s201-r1-91c8ae0`. Both nets and the result files
  behind the showcase's headline numbers are included (`runs/`, `results/`).
- **Run the best player** on one run of the Act 1 test (after the Build steps
  below, plus `pip install torch`), with the flags `configs/product.json` and
  the headline result files use:

  ```bash
  .venv/Scripts/python scripts/gauntlet.py play "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01@tsl1@lcb1" --two-turn --line-seed --step-line --start starter --rewards sim --sim-boss --chooser "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01@lcb1" --sequences 1
  ```

  `jobs/`, `models/` and most of `results/` are made by the tools as they run.
- **What was tried and why:** [docs/decisions.md](docs/decisions.md) (every
  decision with its reasons, in order), [docs/research/](docs/research/)
  (write-ups of experiments and reviews), [docs/backlog.md](docs/backlog.md)
  (ideas not yet run, each with its odds and cheapest probe), and
  [docs/claims/](docs/claims/) (short sourced facts: measurements, causes,
  how things work).
- **How the AI roles worked:** [docs/operating.md](docs/operating.md),
  [docs/roles/](docs/roles/), [docs/lanes/](docs/lanes/) and
  `scripts/roles.py`; [AGENTS.md](AGENTS.md) holds the repo's working rules and
  gotchas.

Not included: the feature specs (`docs/specs/` and `SPEC.md`; documents link
to them, and the decisions log records what each one decided), the owner's
idea tracker (`ideas#<n>` references), the daily digests, raw datasets and
most run folders, and the Claude skills the roles use (`kb`, `spec`, `build`,
`curate`). `docs/claims/` is a read-only archive: its seals and source hashes
refer to the private repository. Commit hashes cited in the docs are from the
private history; this repository starts from a single commit. Developed and
tested on Windows only.

Licensed under the MIT license ([LICENSE](LICENSE)). Map icons in
`showcase/rooms/` are from Slay the Spire, by Mega Crit.

## Build

```bash
python -m venv .venv
.venv/Scripts/python -m pip install maturin numpy
cd py && ../.venv/Scripts/maturin develop --release
```

maturin finds `.venv` at the repository root and installs the `sts` module
there.

## Checks

```bash
cargo test                      # includes the golden trajectories (engine/tests/golden.rs)
cargo test -p sts-py            # the py crate isn't a default member (feature pins)
cargo test --release --test fuzz -- --ignored
cargo run --release --example bench
.venv/Scripts/python py/tests/test_sts.py
.venv/Scripts/python scripts/eval.py
```

## Value nets and the generalisation test (check 6)

```bash
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python scripts/tests/test_net.py
.venv/Scripts/python scripts/generalise.py
```

`generalise.py` plays self-play data into `data/`, trains both nets into
`models/value_effects.pt` and `models/value_ids.pt` (both cached; `--retrain`
ignores saved models), then prints the MSE and win-rate tables. Load a net
for search:

```python
import sys; sys.path.insert(0, "scripts")
import stsnet, sts
model, norm, meta = stsnet.load("models/value_effects.pt")
sts.search_action(c, stsnet.rust_evaluator(model, norm, meta))   # scored in Rust
sts.search_action(c, stsnet.Evaluator(model, norm), features=stsnet.features_for(meta))  # PyTorch
```

`stsnet.rust_evaluator` gives an `sts.NetEvaluator`: the same net's forward
pass in Rust (`py/src/net.rs`), run inside every search thread without
Python's lock. The bench, self-play rounds, `generalise.py` and
`transfer.py` search with it; `stsnet.Evaluator` (PyTorch) stays for static
values over encoded batches (the bench's prediction metric) and for custom
callables, which `sts.run` still accepts (they run on `stsnet.NET_THREADS`
threads).

Search can also score leaves with the mean of several nets: give
`bench.load_evaluator` (and so `--evaluator` in `bench.py`, `ladder.py` and
`depth_paired.py`) paths joined by `+`, as in `a.pt+b.pt+c.pt`
(decisions "Ensemble evaluator: no change at two turns").

Nets are saved under the contract (`docs/specs/rules-engine-upgrade.md`,
spec 1): `stsnet.save` writes `schema` 1, the column names per input path,
the row kinds and the pile names, and loading has the encoder write each
batch in the net's own column order, so a net keeps loading bit-identical
after columns are reordered, appended or removed. A newer schema is refused.
A net saved before the contract (no `schema`) loads through the converted
file beside it, `<name>.contract.pt`, and is refused when that file is
missing.

Row kinds (`sts.ROW_KINDS`): `triggered` (card effects, hook powers and
the hooks a card or intent grants), `threshold` (a monster's "once it has
lost N more HP" switch, condition `HpLostReaches` with N in
`condition_param`: The Guardian's Mode Shift and the large slimes' split,
from the read-only `engine/src/threshold.rs`) and `held` (a card's effects
while held at turn end: Burn, scalar `damage_plain_self`). A net drops the
kinds and columns it wasn't saved with, so nets saved before a kind existed
encode bit-identically (`test_old_layout_unchanged`). Feature caches are
keyed by the full layout (`registry.layout_tag`), so a feature change
rebuilds them.

Monster lookahead (`docs/specs/monster-lookahead.md`, off by default):
`sts.Features(..., lookahead=True)` adds to each monster, after its
`intent_*` block, `intent_pending` (its shown intent is still to roll),
`look_rate_damage` / `look_rate_hits` (per round over its next 4 moves) and
`next1_*` / `next2_*` (the expected effects of its next two moves), from
its AI rolled forward over its move history (`agent::lookahead`). A config
turns it on with `"lookahead": true` (feature mode `effects+lookahead`); a
saved net whose monster columns name these columns gets them on when it
loads. Encoding with it on costs about 3x the encoder's time.

Power rates (`docs/specs/rate-features.md`, off by default):
`sts.Features(..., rates=True)` adds to the player and each monster the
heuristic's per-turn sums of its hook powers (`agent::hook_rates`) as
`rate_<field>` (block, strength, self_loss, damage_all, draw, ...), and
`rate_strength_x_turns` / `rate_block_x_turns` (times the heuristic's
rounds-left estimate); the player also gets `turns_left_est`, and each card
(effects mode) `grant_rate_<field>` for the powers it applies to its user.
Generated powers get rates through their binding. A config turns it on with
`"rates": true` (feature mode `effects+rates`, after `+lookahead` when both
are on); a saved net whose player columns name them gets them on when it
loads. Encoding with it on costs about 7x the encoder's time (the
rounds-left estimate runs the heuristic).

Start HP (`docs/specs/start-hp.md`, off by default):
`sts.Features(..., start_hp=True)` ends the player path with `start_hp`,
the HP the combat started at (the score counts HP lost from it). A config
turns it on with `"start_hp": true` (feature mode `...+start`, the last
suffix); a saved net whose player columns name it gets it on when it loads.

Convert old nets with:

```bash
.venv/Scripts/python scripts/convert_net.py models/*.pt runs/*/model.pt
```

It writes `<name>.contract.pt` beside each net (never over the original or
an existing converted file), only after the converted net's outputs on the
fixed state set equal the original's bit for bit in both passes. It refuses
anything but the `rows` layout, nets whose input widths don't match their
vocabularies, and heuristic-correction and quantile-HP nets (`stsnet`
refuses those anyway); it exits 1 when it refused any.

Speed, Python vs Rust on the same specs:

```bash
.venv/Scripts/python scripts/inference_speed.py --hp-net <run>/model.pt
```

## Silent transfer test (check 8)

```bash
.venv/Scripts/python scripts/transfer.py
```

Uses the two nets from `generalise.py` unchanged (trained on Ironclad only)
on Silent games: tier A decks (cards built from primitives Ironclad uses,
gated) and tier B (Poison, reported). Labelled Silent data is cached in
`data/silent_*`.

## Fine-tuning on new content (warm start)

```bash
.venv/Scripts/python scripts/finetune.py --from models/value_effects.pt --config configs/finetune-silent.json
.venv/Scripts/python scripts/tests/test_warm_start.py
```

`stsnet.widen` carries a net over to a wider vocabulary (an ids net gains
the Silent cards' and Poison's columns, with zero weights; old columns
keep their weights and normaliser). `finetune.py` trains it on Silent
search + heuristic games with half of each batch replayed from the
Ironclad training specs, validates on Silent plus Ironclad games, and
writes a registry run whose `run.json` names its `parent` (path, sha256).
`"start": "fresh"` trains a new effects net on the Silent games only.
Games are registry datasets (sizes nest: the first k per group of one
stored dataset); encoded sets are cached as `cache/warm-*.npz`.

Adaptation burst (`docs/specs/adaptation-burst.md`): `content` may be
`{"pack": ..., "cards": [...]}`, generated power cards from a pack. Then
the games are Ironclad varied setups with 1-2 of those cards in every
deck, played by the parent net (`"player": "heuristic"` for the
heuristic), and validation and replay use Ironclad varied setups too; the
parent must be an effects net and keeps its vocabularies. Example:
`configs/burst8-s1.json`; read with `gen_powers_read.py burst`.

Two-turn round (decisions "Two-turn round spec confirmed"): a config may
carry `"source": {"kind": "two-turn" | "one-turn", "player": <player
string>}` instead of `content`. Its games are `scripts/two_turn_games.py`'s:
elite and boss fights on varied training decks at HP 40-100% of max,
played by that player two turns deep (the stepped fallback player of
`depth_paired`, actions recorded, a resumable partial file under `cache/`)
or one turn deep (`sts.run` search with the player's evaluator), stored as
a registry dataset with real-outcome labels and no search values; the
Ironclad validation and replay pool are the `varied` kind. `games` and
`n_val` count per group. `scripts/two_turn_round.py arm --config C --from
<parent> --against <control> --out <file>` fine-tunes and then reads the
run one turn deep (`@hpb0.01`) on the cell gauntlet with the protocol,
printing the run id and verdict. Example: `configs/twoturn-s1.json`
(control arm: `configs/oneturn-ctl-s1.json`).

`scripts/curve.py [--starts warm_effects,warm_ids,fresh_effects] [--threads N]`
runs the learning curve: each start fine-tuned at 0 / 500 / 2,000 / 10,000
Silent games over 3 seeds, scored on Silent MSE and the Silent tight set
(plus Ironclad MSE and tight2's train half for forgetting, and stall
counts). Cells are cached under `results/warm-start/cells`, so a rerun
or a second process with other starts resumes; the gate and table go to
`results/warm-start/curve.json` (exit 1 when the gate fails). Results:
`docs/research/learned-play-results.md`, "Warm start on Silent".

## Granting a held-out power (check 9)

```bash
.venv/Scripts/python scripts/granting.py
```

Uses the two nets from `generalise.py` (trained without Metallicize, Demon
Form, Rage, Go for the Eyes and FTL) and a reference effects net trained the
same way with those cards in the pool (`models/value_reference.pt`, cached;
`--retrain` rebuilds it). At every decision where a held-out card is
playable, each net's search scores the options; the gate compares each net's
gain from playing the card with the reference net's (result in
`docs/decisions.md`).

## Generated content

```bash
.venv/Scripts/python scripts/gen_content.py --seed 1 --powers 200 --out data/content/gen-s1.json
```

Writes a content pack (`docs/specs/registry-lite.md`) of generated powers,
each with one power card (`gen:<card id>` in a deck; load the pack with
`sts.load_content`). A power is 1-2 hooks of existing triggers, conditions
and effects plus one of four lifetimes (permanent, this turn, used up,
wearing down); its card costs 1-3 and grants 1-3 stacks. Each power is
`train` or `test` by its (trigger, effect kind) pairs: official training
pairs are train, about a quarter of the rest are test (turn start ->
+Strength, Demon Form's pairing, always is), and a test power shares no
pair with any train power. Budget: the heuristic's value from playing the
card, per energy, lies in the official power cards' range (0.092 Demon
Form to 0.253 Combust); powers the heuristic can't price (about 3 in 4)
get cost 1-2 and are marked unpriced. Same seed, same bytes. Tests:
`scripts/tests/test_gen_content.py` (~10 s).

A pack can hold more than the generator writes (`docs/decisions.md`
"Content packs carry every atom"): any card type (`Attack`, `Skill`,
`Power`, `Status`) with every flag (`exhaust`, `ethereal`, `retain`,
`x_cost`, `innate`, `unplayable`), a play condition (`playable_if`,
Clash's `{"HandAll": "Attack"}`; a version-1 file says
`only_attacks_in_hand`), `tags`, conditional `rows` and `turn_end` effects, and powers with `hooks`,
`statics` and `replacements`, using every effect, trigger and condition the
engine has. `sts_engine::registry::card_json` / `power_json` write any
official card or power as a pack entry; `engine/tests/packs.rs` loads every
one back unchanged.

A pack can also hold `monsters` (`docs/decisions.md` "Runtime registry
stage 3 spec"): HP
range, moves (any effect that runs outside a card, plus `Split` and
`Escape`), pattern rows that pick moves by index, start block, official
start powers and a split into official or earlier-loaded monsters.
`sts.Combat.versus(deck, ["gen:<id>", "Jaw Worm"], seed)` fights them; a
state holding one has no codec bytes. `registry::monster_json` writes an
official monster as a pack entry; the 13 without code-only behaviour (all
but the lice, Lagavulin, Hexaghost and The Guardian) load back unchanged
and play the same games (`engine/tests/monster_packs.rs`).

Official content is data too (`docs/specs/official-content-files.md`):
`content/cards.json` (64 card kinds in `CardId` order, one entry each with
its upgrade as data, or an `X` / `X+` pair for an upgrade that changes how
the card works; 128 card ids), `content/powers.json`
(30 powers in `Power::ALL` order) and `content/monsters.json` (kinds 1-18)
are in the pack format, compiled into the engine and parsed by the pack
parser on first use; there are no Rust tables behind them. Adding or
changing official content is a file edit, then `cargo run -p sts-engine
--example export_content` to rewrite the files in canonical form (a test
fails on a non-canonical file). Card names carry their level: `Bash` and
`Bash+` are a card's two ids, `gen:Searing Blow+3` a level-3 copy
(`docs/specs/card-upgrades.md`; `sts.upgrade_name`, `sts.base_name`).
Official-only fields: a card's `class`;
a monster's `code` (`louse`, `lagavulin`, `hexaghost`, `guardian`), which
attaches its code-driven behaviour; packs using them are refused (and the
retired pool flags `held_out` and `proving`, which the official loader
ignores in an older file). The files count as rules: editing them changes
the solved DB's fingerprint.

Card sets (the lists we choose for training and testing; a *pool* is a
list the game itself draws from, `docs/extending.md` "Pool or set") are
named in `configs/card-sets.json`
(`docs/specs/card-sets.md`), not card fields: each set is a list of base
card names (a name brings its `+` card), used in card order. `ironclad`
is `deck_cards()` / `sts.deck_card_names()`, `silent` is
`class_cards(Silent)` / `sts.class_card_names("silent")`, `check9` is
`held_out_cards()` / `sts.held_out_card_names()`, and `proving` holds the
rules-engine proving cards; `sts.card_set(name)` and
`sts.card_set_names()` read any set. Editing a set changes training
sets only: it is not in the solved DB's fingerprint or the golden games.

Training with it (`learn.py` config keys): `content`, a pack's path or
`{"seed": S, "powers": N}` (generated at run start), and `content_share`,
the share of training decks (varied setups, rounds 0 and later) that get 1-2
of the pack's *train* power cards (`content_split: "test"` gives them the
test cards instead: the oracle arm); validation decks stay official. Without
them (or at share 0) datasets are unchanged byte for byte. A content
dataset's config and manifest carry the pack's `content_hash`, each round's
run folder holds the pack (`content.json`) and its round.json the hash, and
replaying the dataset refuses (`registry.ContentError`) until that pack is
loaded (`selfplay.load_content`). States with generated cards have no codec
bytes, so they take no exact labels, and the solve step refuses such a
config unless `solve_games` and `solve_games0` are 0 (the lean recipe's).
Tests: `scripts/tests/test_content_selfplay.py` (~20 s).

Mutated monsters, stage A (spec folded into the results doc "Mutated monsters,
stage A" sections and decisions of that name):
`scripts/analysis/mutate_monsters.py play --starts 200 --seeds 8 --players
heuristic,one[,two] --out results/mutate/<name>.json` replays the gauntlet's
elite and boss fights from their first decision with the enemies mutated by
a patch of the start state (HP x0.8 / x1.25, Strength, Metallicize, Ritual,
SharpHide; the owner's boon + bane pairs; one stack), common seeds per
start, played by the heuristic, the product net one turn deep and (a
subset) two turns deep; `read` gives per modifier the difficulty change,
the one-turn net's drop beyond it (novelty cost) and whether depth repairs
it. `--mods a,b` plays a subset of the modifiers (new files, or more
modifiers into an existing one).

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

## Learned play: training runs and the registry

```bash
.venv/Scripts/python scripts/learn.py --config configs/baseline.json [--bench]
.venv/Scripts/python scripts/tests/test_registry.py
.venv/Scripts/python scripts/bench_compare.py <run id> <run id> results/baseline/heuristic.json
```

`learn.py` self-plays into `datasets/<id>/` (game records: setup, every
action, the search's value for every root option of every decision,
outcome, plus a manifest with the engine commit, the rules version =
hash of the golden trajectories, and the generating config; id = manifest
hash; never overwritten), encodes them by replay into `cache/<id>-<format>.npz`
(disposable, 10 GB cap, oldest evicted; a dataset from other rules is
refused), trains, and writes an immutable `runs/<date>-<config>-<hash>/`
(config, commit, dataset ids, model, training curves, bench results) with a
line in `runs/index.csv`. A config reuses a dataset already generated with
the same settings. `datasets/`, `cache/` and `runs/` are gitignored except
`runs/index.csv` and `runs/sweep-*.md`. See `scripts/registry.py`.

Every config plays self-play rounds 0..N (`"rounds": {"n", "temperature",
"every", "min"}`, defaults 3, 0.05, 1, none; learned-play Amendments 1-3). Every
label is a game's real outcome (no heuristic or search value in any label).
Round 0: search + heuristic plays, and the net trains on those games. Round
k >= 1: search + round k-1's net plays fresh seeds, picking options by
softmax over their values (`sts.run(..., explore=t)`), and a fresh net
trains on its games and round k-1's, plus round 0's while round 0 is in.
Round 0 leaves for good from the round after a net reaches the heuristic:
its tight-fight win rate (one-turn search, every `every`-th tight spec) at
or above search + heuristic's by point estimate on both halves (the
heuristic measured once per config). From then on the window is the last 2
rounds and each round plays `n_late` games per group (default `n_round`).
With `d0_sample` ({"round0": f, "later": g}, the sweep's setting) round 0's
games are a large heuristic pool: round 0's net trains on a random fraction
f of its examples (drawn across all games, fixed seed, training seed
`round0_seed`), and while round 0 is in, later rounds use a fraction g
drawn once per `round_seed`, the same in every round.
Validation is always heuristic games labelled with real outcomes. Each round
is its own run (`<name>-r<k>`) with `round.json`: datasets, the window
(datasets, `round0_in`), parent run, val MSE, the label scale check (per
training dataset, |mean label - mean real outcome|; a warning over 0.1, or
10 HP with switch 6), from round 1 the tight-fight win rate of the round's
net and its comparison with the heuristic per half (`heuristic`), and from
round 2 the monotone check (ok unless a half's interval lies wholly below
the previous round's), and from round 1 the deciding gate (`gate`: the
net's 95% interval wholly above the heuristic's, per half and on both).
Score configs take curriculum labels (`docs/specs/curriculum.md`): exact
values from the solved-position database, else inside the playing net's
trusted zone 0.8 x its search value + 0.2 x the outcome, else the outcome;
`round.json` adds the net's puzzle regret per horizon and its frontier
(`trusted`), the database's rows after the round's solve step (`db_rows`)
and how many training examples took each rung (`rungs`: exact, search,
outcome, ranking only, exact drawn from the database).
With `min` (Amendment 3's stop rule), a run stops after the first round
from `min` on whose gate is met, else at round `n`; only the final round is
benched with `--bench`. `n_round` (optional) sets the games per group of
rounds >= 1 (default `n_train`).

Every self-play and validation game starts at a random HP, uniform over
10-100% of max HP (whole HP, at least 1), with the starter deck plus 3-15
random training-pool cards (`selfplay.VARIED`; `"setups": "varied"`, the
default; `"fixed"` plays the older full-HP starter + 5 decks). The dataset
config records it, so datasets of the old setups are never reused.
`sts.run` takes 4-field specs `(encounter, deck, seed, hp)` for this; game
records store each game's HP and replay uses it. The bench is unchanged.
Varied setups slow self-play (heuristic ~0.77x, net ~0.43x: bigger decks
have more options) and raise the examples per game slightly (~38 with
afterstates instead of ~36) and their size (~5.8 KB instead of ~4.7 KB).

The ranking loss is part of every config (Amendment 2): from round 1 a
pairwise hinge (weight `learn.RANK_WEIGHT` = 1.0) over each sampled
decision's options makes their predicted values (probability-weighted over
outcomes) order like the playing net's search values, never the
heuristic's (round 0's examples carry inert ranking fields). Every root
option's afterstate the search scored becomes an example too (~34 examples
per game instead of ~7), labelled with the game's real outcome. Training
batches keep each decision's examples together.
Every round self-plays with one search setting, `learn.SELFPLAY_SEARCH`
(one turn, limit 16: the agents' search; at one turn `sample_k` changes
no game).

Switches (`"switches"` in a config, all off when absent):
- `hp_loss` (switch 6, `configs/hp_loss.json`): self-play runs in no-death
  mode (`sts.run(..., no_death=True)`, `sts.Combat(..., no_death=True)`: HP
  may go below 0, a combat ends on a win, with no end-of-combat heal, or as
  a loss after 50 turns). The net predicts a histogram over the HP lost
  from a state to the end (`stsnet.N_BINS` = 47 bins: 1 HP wide to 30, 5
  wide to 60, 10 wide to 150, one for >= 150, one for the turn limit;
  cross-entropy, so validation loss is a cross-entropy, not an MSE), and
  search scores it with a fixed formula (`stsnet.external_score`): P(win) =
  the mass of the bins below the current HP, each winning bin's end HP
  healed before scoring, score = P(win) x (2 - expected HP lost when
  winning / 100). Labels are one-hots of the real HP lost; the ranking term
  uses the formula's score.
  A config may also carry `"score": {"kind": "survive", "c": 1.0, "w": 2.0}`
  (with `"no_death": false`): the net saves that `score_rule`, and a
  winning bin then scores c + w x its end HP / 100 in Python and Rust
  alike (`@sc<c>` overrides c at play time; not with `@hpb`). No net in
  use carries a survive rule.
- `branches` (switch 7): from round 1, each self-play game may get one
  branch game. The branch point is a decision with an option the playing
  net's search valued below the decision's best by more than the
  exploration temperature (one picked uniformly, then one such option);
  the branch replays the main game up to there (`sts.run(...,
  forced=[actions per spec])`), forces that option and plays on with the
  same search. Its examples come only from after the forced action, with
  its own outcome; main games' labels are unchanged. Measured with the
  effects net: 96% of games get a branch, and self-play takes ~1.4x as
  long (a branch replays its opening without searching).

### The sweep

`scripts/sweep.py` plans and runs a set of `learn.py` configs overnight
(`--plan` projects time, memory and disk; `--round0` builds the shared
round-0 pool; `--jobs N` runs plan rows in parallel; `--tiny --no-guard
--root <tmp>` is a dry run), with `scripts/sweep_watch.py` beside it and
the table in `runs/sweep-<date>.md`; `colab/sweep.ipynb` runs one plan row
per Colab session. Not part of current work: nets are judged on the
headline setting (`yardstick/headline-setting`). Options: `sweep.py
--help`; tests: `scripts/tests/test_sweep.py`.

## Facts (kb)

The project's current facts (the product, the yardstick, measurements,
decisions in force, causes, how parts work) live in `docs/claims/`, one
sealed file per fact, written only through `kb` (`~/.claude/skills/kb/`;
spec `docs/specs/kb-adoption.md`). A session gets STATUS.md (suspect and
pinned facts, an index of keys) at start; `kb find` / `kb get` look a fact
up, `kb set ... --from <files or keys>` records one, `kb check` lists facts
whose sources changed. The product player is promoted only with
`scripts/product.py set` (registry `configs/product.json`, fact
`product/net`); `results/ladder/champion.json` is the tight2 ladder's
state, not the product. Spec states are line 3 of each spec
(`scripts/spec_status.py`).

## Job queue

Long runs go through a queue so the CPU never waits for a person or a
session to start the next one (`scripts/jobs.py`, state in `jobs/`,
gitignored; spec `docs/specs/lanes-runner.md`; the job-queue spec is folded
into this section and `docs/decisions.md`):

```
.venv/Scripts/python scripts/jobs.py add --threads 8 --estimate-min 120 [--lane run] -- .venv/Scripts/python -u scripts/curve.py --threads 8
.venv/Scripts/python scripts/jobs.py status
.venv/Scripts/python scripts/jobs.py run      # the runner; one at a time (jobs/runner.pid)
.venv/Scripts/python scripts/jobs.py wait     # exits on the next end (0) or failure/stall/suspect/parked/waiting (1)
.venv/Scripts/python scripts/jobs.py kill <id> --reason "hung"   # the runner ends the job's whole tree
.venv/Scripts/python scripts/jobs.py first <id>                  # start it next: reservation now, first in its lane
.venv/Scripts/python scripts/jobs.py set <id> [--lane L] [--after a,b] [--if-passed a,b] [--on-fail park|cancel]
.venv/Scripts/python scripts/jobs.py unpark <id>
.venv/Scripts/python scripts/jobs.py estimate <id> <minutes> [--reason "pace: 119 / 200"]   # pending or running
.venv/Scripts/python scripts/jobs.py verdict <id> pass|fail [--reason "..."]
.venv/Scripts/python scripts/jobs.py pins     # snapshots, the jobs pinned to them, their wheels
.venv/Scripts/python scripts/jobs.py unpin <commit>
.venv/Scripts/python scripts/jobs.py impact sts|scripts   # exit 1 if unpinned jobs would be hit
```

A family of reads (bursts, their reads, a table with a pass rule, follow-up
reads) is queued as one chain with `scripts/family.py queue
configs/families/<name>.json [--dry-run]`; `family.py table <file>` prints
its result and verdict from the files (docs/specs/session-free-reads.md).
A pack of generated enemy mechanics (`configs/packs/<name>.json`) queues
the same way: one joint burst per arm and seed, the zero-shot bench read
if missing, the bench reads, and a table whose per-net guard decides the
pack's net, written to `results/packs/<name>.json` only when one passes
(docs/specs/pack-adapt-pipeline.md).

To watch the roles and the queue, `python scripts/dashboard.py [--port 8766]`
serves a read-only page on http://127.0.0.1:8766 (health, running sessions
and jobs, recent role runs, lanes, what the navigator waits for, a
zoomable timeline; each role session
readable as a transcript; every done job
on `/queue`, paged and filtered); Ctrl+C stops it.

**Admission.** A job starts when its heavy slot fits (2 slots; a light
job takes none, a heavy job of 2 threads or fewer half a slot), the
runner's jobs' threads plus this one fit 14, the system's idle CPU covers
its threads (runs started by hand count as busy), the running jobs'
reserved memory (`--mem-gb`, or the measured `peak_gb` when higher) plus
this job's fit total memory minus 1 GB, and free memory (the smaller of
free RAM and commit headroom) is `--mem-gb` + 1 GB. When none of the
runner's jobs runs, commit headroom (RAM plus pagefile) alone counts, so
one job always runs, paging if it must. So `--mem-gb` is a
reservation: set it to the job's peak. The runner samples each running
job's process-tree working set every poll and keeps the largest as
`peak_gb` (shown by `status`); `add` warns, and records `mem_gb_low`,
when `--mem-gb` is below the last peak of the same script and first
argument. A job that can never start (threads above 14, `--mem-gb` + 1
above total memory, a broken job file) is moved to done as refused. Jobs
get `OMP_NUM_THREADS`, `RAYON_NUM_THREADS` and `STS_JOB_THREADS` set to
`--threads`, and still pass `--threads` to scripts that take it; Rust
searches that name no thread count use `STS_JOB_THREADS` (Rust
`default_threads`, Python `stsnet.job_threads`) instead of every core.

**Lanes.** Each job has a lane (`--lane`, default `main`); shares come
from `jobs/lanes.json` (`{"lane": share}`, read each poll, over the
defaults depth 35, run 30, goal1 25, train 10, main 10, filler 0; a lane
not named has 10). A lane's use is the sum over its running jobs of the
larger of threads / 14 and reserved memory / (total - 1 GB). Each poll the
runner tries lane heads in order of lowest use / share and starts the
first that fits (one start per poll); within a lane, name order. When a
lane's head waits for memory only, a later job of that lane may start
(backfill). The top lane head that has waited 10 minutes for any reason
gets the reservation (`first` gives it at once): while a job holds it,
another starts only if it fits alongside it (slots, thread budget,
reserved memory, as if both ran), and after 30 minutes the runner logs
`waiting`, which wakes `wait`. A lane with share 0 or below is a filler
lane: its head starts only when nothing else started that poll, and `add`
refuses a filler that is neither `--resumable` nor `--estimate-min` 20 or
less.

**Conditions.** `add --after a,b` waits until those jobs have ended;
`--if-passed a,b` until they ended and passed. A waiting job doesn't
block the ones behind it. When a condition can't hold any more (an
`--if-passed` dependency failed, was cancelled or refused, or ended-unknown
without a verdict; any dependency, `--after` included, is parked or in no
folder), the job is parked (`parked`
event; `status` shows the reason) or, with `--on-fail cancel`, cancelled;
parking cascades through chains. `set` changes a pending job's lane or
conditions and keeps its id; `unpark` clears a park (the next poll decides
again, so set a verdict or change the conditions first). A job passes when
it ended `ok`, or, with `add --check "cmd"` (one string, forward slashes),
when that check exits 0: the runner runs it after an `ok` end as its own
light process (killed after 10 minutes: fail), and records the `verdict`
with the check's last output line. `verdict <id> pass|fail` sets one by
hand. Prefer two jobs joined by `--if-passed` to `bash -c "A && B"`.

**Pinned code.** `add` pins the job to a snapshot of HEAD by default: a
detached, locked worktree `../sts-builds/<commit>/`
with main's data folders junctioned in (`results`, `db`, `cache`,
`datasets`, `models`, `logs`, `jobs`, `.venv`, `scripts/analysis/out`,
`runs`, and each ignored entry of `data/`, files by hard link) and its own
`sts` module in `pyroot/` (built from that commit, a few minutes when the
module changed, hard-linked from an earlier snapshot otherwise). The job
runs there with `PYTHONPATH` = its `pyroot`, so it writes results, runs and
the run index into main, and a merge, module swap or landing on main never
touches it. `add` refuses while the pinned paths (`scripts engine py
solvedb configs data/bench Cargo.toml Cargo.lock .cargo`) have uncommitted
or untracked files: commit, or use `--unpinned` (jobs that write tracked
files such as `bench_sets.py` and `puzzles.py`, jobs that write new files
directly in `data/`, runs by hand). `--pin <commit>` pins an older commit.
Snapshots are removed only by `unpin` or by the runner when no pending or
running job used one for 24 h, never by hand or by `git worktree remove`
(through a junction that would delete main's data); `unpin` refuses if the
snapshot holds anything besides its links and caches (a job's output).
`impact sts|scripts` lists the unpinned jobs a swap or merge would hit.

**Watching.** Output goes to `logs/jobs/<id>.log`. A log silent for 30
minutes is flagged `stalled`; a log tail with `Traceback`, `MemoryError`,
`memory allocation of` or `BrokenProcessPool` is flagged `suspect`.
Neither is killed: `kill` writes `jobs/running/<id>.kill` and the runner
ends the job on its next poll (status `killed`, with the reason and the
log's last lines). Each job runs in its own Windows Job Object and holds
its slot until its whole process tree is gone, worker processes included.
Jobs start through a frozen wrapper (`jobs/runner-<pid>/exec.py`) that
writes their exit code to `jobs/running/<id>.exit`, so they outlive the
runner and a restarted runner still records how an adopted job ended (it
watches only the wrapper's pid and kills with `taskkill /T`). Only a job
with no exit file (started before the wrapper existed, or whose wrapper
was killed from outside) ends as `ended-unknown`.

## Champion ladder

`scripts/ladder.py` (`docs/specs/champion-ladder.md`, `ladder-v2.md`)
plays a candidate net against the champion (`results/ladder/champion.json`)
on paired tight2 fights under a sequential test, and `ladder.py runhp`
scores HP lost at run-like start HP against `--against`. Neither ranks nets
for the product (`decision/no-proxy-promotion`); results go to
`results/ladder/`. Options: `ladder.py --help`.

## Act-1 gauntlet

Goal 2's headline number (`docs/specs/gauntlet.md`): seeded chains of 11
fights (3 easy hallways, 2 hard, an elite, 2 hard, an elite, 1 hard, a boss)
with one tight2 deck per sequence and HP carried over from 80: the engine
adds Burning Blood's 6 on a win, a rest before the boss heals 24, a loss
ends the sequence. Sequence i alternates train / held-out decks, and every
agent plays the same sequences, so two result files pair by sequence. `play`
writes `results/gauntlet/<tag>.json` (a rerun adds only missing sequences);
`read` prints each agent's clear rate, the paired difference, HP at the
boss and deaths by floor and encounter, by half too:

```
.venv/Scripts/python scripts/gauntlet.py play runs/<net>/model.pt@hpb0.01 --sequences 200 --threads 6 [--two-turn]
.venv/Scripts/python scripts/gauntlet.py read results/gauntlet/<a>.json results/gauntlet/<b>.json
```

A net player spec takes search-time settings after `.pt`, each at most
once: `@hpb<c>` (HP bonus), `@hpe<c>` (end-HP bonus, also on finished
combats; c prices one HP at 80 max HP and the same share of the HP bar at
any other, `c x 80 / max HP` per HP; not with `@hpb`; decisions "End-HP
bonus built and read", "End-HP bonus scales with max HP"), `@esp<k>`
(enemy-Strength price, `docs/specs/enemy-strength-price.md`), `@shl<k>`
(enemy Strength priced by the hits it will still land,
`docs/specs/strength-hits-price.md`), `@sc<c>` (a
survive net's c), `@tb1` (exact value ties go to the sooner win, then lower
enemy HP; values unchanged, `docs/specs/finish-faster-tiebreak.md`),
`@sn1` (card damage and block encoded as the game shows them: + Strength x
hits, x0.75 under Weak; + Dexterity, x0.75 under Frail) and `@xh1` (the
exhaust pile's counts encoded as 0; both `docs/specs/shown-card-numbers.md`),
e.g. `model.pt@hpb0.01@esp0.04`.

Leaf settings: `@dl<k>` scores end-of-turn leaves after k sampled draws;
`@tsl1` after the player's turn-start hooks that need no chance; `@lcb1`
with the player's block at 0; `@pl<k>` applies once-a-turn Strength and
Dexterity hooks k more times there, player and monsters
(`docs/specs/projected-leaf.md`); `@pd1` (only with `@pl<k>`) also
monsters' once-a-turn Weak, Frail and Vulnerable on the player
(`docs/specs/recurring-debuff-leaf.md`). Read `@sn1`/`@xh1` against a
plain control with `--vary price`.

`--two-turn --one-turn-floors 3` plays floors 1-3 one turn deep;
`--two-turn --line-seed` gives every two-turn search of a combat turn the
same sample seed, so later decisions follow the first tree's line (the
committed-line player: level or better than plain two-turn, +0.60 HP,
+0.024 clears on cells 0-249; decisions "Line seed passes";
`scripts/analysis/line_probe.py` records how a turn's two-turn cost splits
by decision index: ~60% sits in the first tree,
`results/depth/line-probe.json`); `--line-seed --step-line` plays each
uncut tree's principal line (`sts.search(...)["line"]`: the best child at
every decision up to End turn or the first chance node) instead of
searching every decision: the same decisions exactly (20 of 20 probe
fights, 526 of 526 decisions) at 0.70 of the search cost (decisions
"Line-step probe"; `line_probe.py --compare` measures agreement and the
cost ratio against the stage-1 player, `results/depth/line-step-compare.json`).
A control played without a flag needs `--vary line_seed` / `--vary
step_line` under `--against`. Card
rewards (decisions "Card rewards are a goal-2 lever"): `--rewards random|sim` offers 3
cards (seeded, from the half's pool, no upgrades) after each won fight
before the boss; `random` takes one at random, `sim` takes the option (or
skip) that scores best over 8 one-turn fights against the next floor's
pool, with common seeds. `--start starter` starts from the starter deck
instead of the cell's deck. The defaults (`skip`, `cell`) give today's
files; rows record `offer` and `took` when rewards are on. `--sim-boss`
(decisions "Sim-boss passes: new headline setting") adds 8 fights against the boss pool at the
post-rest HP to each option's sim score. `--chooser <player>`
(decisions "Crossed chooser arms read: the chooser is the larger
one-turn lever") scores the sim chooser's option fights
with another player (e.g. the heuristic) while `<player>` fights the
floors; the file records `chooser`. `--rewards vrun --fit <gauntlet
file> [--fit-first 250 --fit-n 250]` (decisions "Run-value chooser: fails,
use (b) closes for card picks")
scores each option by the run value instead of `1 + 0.01 x end HP`: the
next-floor sims' end HP priced as P(reach the boss at that HP, from the
fit file's sequences) x P(win the sequence's own boss | HP, deck) (the
boss's causal curve from `scripts/run_value_unit.py`'s `BOSS_CURVE`,
shifted to the deck's level from 8 fights against that boss); rows record
`took_sim`, the old score's pick on the same fights
(`run_value_unit.py pickrate <file>`). `--remove strike|sim`
(`docs/specs/card-removal.md`) removes one card after the first elite's
reward (a shop proxy): `strike` the first Strike, `sim` the option (or
keep) that scores best the same way; the floor-6 row records `removed`.
`--elites skip|hp [--elite-hp 40]` (decisions "Elite-skip read") fights a
hard hallway instead of an elite, always or when the HP entering the
floor is under `--elite-hp`; elite-floor rows record `path`. With no
relics an elite has no payoff here, so `skip` is the ceiling of a path
choice on this gauntlet, not a product rule.

Early stop (`docs/specs/gauntlet-early-stop.md`): `play` runs in blocks of
`--block` sequences (default 50) and rewrites the file after each.
`--against results/gauntlet/<control>.json` runs the gauntlet protocol
(decisions "Gauntlet protocol") after each block on the sequences both
files hold, and stops on pass, fail or fail-guard; the file's `protocol`
key holds the verdict and n. Report a promotion's effect at fixed n (the
confirmation book, sequences 500-999), not at the stopping point. A
control must cover the candidate's sequences, or the verdict stays open.
`--against` refuses a control played with other settings (depth,
`--one-turn-floors`, the price after the player's `@`, `--start`,
`--rewards`, `--sim-boss`, the chooser, rest, removal or elite options),
naming each difference, unless the read declares the ones it tests with
`--vary <field>` (repeatable; e.g. `--vary remove` for a removal read
against the plain headline file); the file's `protocol` key records them.

Pack cards in the offers (`docs/specs/gauntlet-pack-offers.md`): `--pack
<file>` loads a content pack (in the two-turn workers too) and adds its
base cards, as `gen:<id>`, to both halves' reward pools; offers stay
uniform. Its `hallway` encounters join the hard floors
(docs/research/act1-inventory.md "Block G2"): one named like an official
hard encounter replaces it, the others are added, all equally likely, on a
second stream so every other floor matches the pack-less sequences. A pack
without hallway encounters needs `--rewards` other than `skip`. It is recorded as
`"pack": "<file>@<content hash>"`, and a read against a pack-less control
declares `--vary pack`; `--match` refuses a file of another pack setting.

Deck-matched reads (`docs/specs/deck-matched-reads.md`): `--match <file>`
replays that file's recorded card picks (extra elite picks too), rest
choice and removal wherever it has one, so a fighter read `--against` the
same file varies only the fighter; where the file has no record (its
sequence died earlier) the run's own chooser decides. The file must share
the choice settings (rewards, chooser, rest, removal, elite options,
start); fighter settings may differ. Matched floors are marked
`"matched": true`; `match` is recorded in settings but never compared by
`--against`. A matched read can't see a chooser change.

Which read answers which question: the sim chooser picks cards by
playing fights with the fighting player, so nearly any change to the
player also changes its picks. A whole-player question (is this net, or
this setting, better?) plays each arm with its own picks, unmatched. A
fighting-only question (does it fight better on the same decks?) is a
matched read on the control's picks: the cheapest read (no chooser
fights, 2.4-4.2x lower variance one turn deep), leaning slightly toward
the control, whose decks were picked for its own play. Each arm on both
sets of picks (crossed arms, `--match` plus `--chooser`) only when a
decision needs fighting and picking split apart.

Boss replays (decisions "Boss replays: the boss curve is causal; the run
value is per boss"): `scripts/analysis/boss_replay.py
play --file <headline file>` rebuilds every boss-reaching sequence's boss
fight (its deck at the boss, boss and seed) and plays it one turn deep at
entry HP 30, 40, ..., 80 on common seeds (`--seeds 4`), so only HP varies;
`read` prints the causal P(win | HP) per boss beside the observational
curve, the per-deck step and the confound (results/boss_replay/).
`--hp arrival --seeds 8` instead replays each boss at the sequence's own
arrival HP (`docs/specs/boss-replay-score.md`), recording win and end HP
per seed; `pair <a> <b>` (two such files) prints the paired sd of clears
and end HP beside that of the mean replay score (0 for a sequence that
died before the boss).

Other `gauntlet.py play` options: `--pack-picks originals` (with --pack
and offers: pack cards are offered, the chooser takes only original cards
or skips; recorded as pack_picks); `--rewards value [--value-hands K]`
(picks by the net's static values of fight-start states, no trial fights;
train-card sequences only, decision/value-chooser-use); `--elite-offers N
--mid-rest K` (the mini-run); `--elites skip|hp --elite-hp H`; `--rest sim
--rest-fights F --rest-margin M`.

## Watch a combat

```bash
.venv/Scripts/python scripts/replay.py --encounter slime_boss --agent search --seed 3
```

## Real-game bridge

The product plays the fights of a real Slay the Spire run on this dev machine
through CommunicationMod (docs/specs/real-game-bridge.md). Start the game
with only BaseMod and CommunicationMod (your ModTheSpire lists are left as
they are; saves, preferences and `mod_lists.json` are backed up first):

```bash
.venv/Scripts/python scripts/real_game.py launch runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01@tsl1@lcb1
```

Add `--runs N` to the player tokens to have the controller play N whole
Ironclad runs by itself (`--ascension A` starts them at ascension A, 0-20;
each run's record and the report keep its level; `--act1-only` stops each
run when Act 2 starts, since the engine models Act 1 only, and closes the
game there, since CommunicationMod can't abandon a run; after a death the
next run starts in the same game. So `launch --loop <player> --runs 1000
--act1-only` plays run after run, relaunching the game only after an Act 2
stop, until `results/real-game/stop-loop` exists: the controller then
starts nothing more at the main menu and closes the game) (map, events, rewards and card picks by
`scripts/real_game_run.py`'s rules; it starts a run only while no Ironclad
save of yours exists). `results/real-game/<stamp>/status.txt` says what it
is doing (or why it handed a fight to the fallback player); `fights.jsonl`,
`decisions.jsonl`, `states.jsonl`, `runs.jsonl` and `log.txt` are the
record (gitignored, kept). The controller loads its code only at game
start: create `results/real-game/hold` to have it wait at the main menu
after the current run, then restart the game (delete the file first).
`python scripts/real_game_report.py --write` writes the record's tables
into `docs/research/real-game-runs.md`.
Backups: `%LOCALAPPDATA%/sts-for-ai/real-game-backups/` (newest 20 kept);
`scripts/real_game_launch.py restore-mod-lists` puts the mod lists back.
Name tables: `content/game_ids.json`, checked against the game's jar by
`scripts/game_ids.py check`. `Combat.view()` / `Combat.from_view()` turn a
fight into plain data and back.

## Python API (short)

```python
import sts
c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], "jaw_worm", seed=1)
c.legal_actions(); c.options(16); c.step(a); c.render()
f = sts.Features("effects")            # or "ids"; known_cards=, known_powers=, known_triggers=,
                                       # known_conditions=, known_effects= (f.vocab: the lists in use)
batch = f.encode([c])                  # player, monsters, cards, card_count, card_pile, card_state
                                       # + rows, row_card, row_entity, row_state (hook rows)
sts.search_action(c, "heuristic")      # or a callable: batch dict -> scores, or an sts.NetEvaluator
sts.search(c, "heuristic", turns=2, sample_k=4, max_nodes=50_000)  # {action, options, nodes, leaves, cuts}
                                       # cuts: states left unexpanded at max_nodes; sibling options
                                       # share sampled outcomes (common random numbers)
sts.run("search", sts.make_specs("boss", 100), threads=16)
sts.run("search", specs, record=True, values=True)  # + "values": per decision [(actions, value)]
sts.run("search", specs, forced=[[a1, a2], ...])     # each game plays its forced actions first
s = sts.Combat(sts.starter_deck("silent"), "cultist", character="silent")
sts.run("search", sts.make_specs("boss", 100, character="silent"), character="silent")
sts.solve(c, max_nodes=1_000_000, distribution=False, store=None)  # exact option values, or None
db = sts.SolvedDb("db/solved.sqlite"); store = sts.SolveStore(min_nodes=1000, db=db)
sts.Combat.decode(c.encode())          # the state as bytes and back
h = sts.load_content("pack.json")      # generated powers/cards (docs/specs/registry-lite.md); content hash
m = sts.Combat.versus(deck, ["gen:brute", "Cultist"], seed=1)  # monsters by name (official or a pack's)
g = sts.Combat(deck + ["gen:gc017"], "cultist")  # decks and run specs name them gen:<id>; at most
                                       # registry::MAX_CARD_SLOTS generated cards and
                                       # 24 (POWER_SLOTS) generated powers per combat; no encode(); ids-mode
                                       # features see them as unknown. sts.loaded_content(): hashes loaded
```
