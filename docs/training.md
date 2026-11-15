# Training runs and fine-tuning

A training run lets the search play games, trains a value net on their
outcomes, and repeats with the new net (self-play). This page covers the
training script, the registry that records every run, and fine-tuning an
existing net on new content.

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
