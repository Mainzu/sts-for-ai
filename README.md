# sts-for-ai

A home-made copy of Slay the Spire 1's combat, written in Rust, and an AI
that plays it by looking ahead. One hobbyist started it on 23 October 2026
and steered it. From 29 October, Claude sessions ran most of the day-to-day
research: they planned and ran the experiments and recorded each decision
with its reasons. From 3 November they also wrote down their odds of
success before each short research project. The project ran for 23 days,
to 14 November.

The [showcase](https://mainzu.github.io/sts-for-ai/showcase/) tells the
whole story with charts. [showcase/llms.md](showcase/llms.md) is the same
page as plain text.

## What it can do

- **It beats the Act 1 boss in about 4 runs of 5 on the project's own
  test.** The test is eleven Act 1 fights in a row with the Ironclad's
  starter deck and 80 HP. There is one campfire before the boss and no
  relics except Burning Blood, no potions, shops or events. After each won
  fight it picks one of three cards, or none. One loss ends the run. Over
  1,000 seeded runs the AI beat the boss in 807. On the 500 runs held back
  to check its settings, it beat the boss in 78 of every 100, give or take
  about 2.
  This is the best player as of 5 November, looking two turns ahead.
- **It has played the real game.** Through a mod, a version of the AI
  whose net was trained on the real Act 1 cards played Ironclad runs of the
  real Slay the Spire on 14 November, from the start of each run through
  Act 1. At Ascension 0 it beat
  the Act 1 boss in 22 of the 24 runs that reached the boss. At Ascension
  20, with the last version of its run rules (how it handles the map,
  campfires and card picks) and a guard that always takes a move that wins
  the fight outright, it beat the boss in 18 of the 28 runs that reached
  it.

## Why it is interesting

- **It picks where to end up, not which card to play.** The engine lists
  every move, works out where each one leads, and a scoring function picks
  the best place to be. See [docs/concept.md](docs/concept.md).
- **Cards are data.** Each card is written in a content file as a
  combination of a small set of effects. Every random event in a fight is
  explicit, so the search can see each one and sample its outcomes.
- **It was tested on things it had never seen.** Cards held out of
  training, a second character (the Silent), made-up powers and monsters
  with changed mechanics. The aim is an AI that copes with new content the
  way a player copes with a mod.
- **The research was run by AI sessions, and graded.** Every short research
  project they ran wrote down its chance of success before it started. 55
  of them closed in 11 days. None of the ten long shots worked, about half
  of the even bets did, and most of the likely ones did. The showcase's
  verdict section has the rest.

## What it found

Most findings come from the project's own Act 1 test. The showcase has the
measurement behind each one.

- **Thinking deeper beat training harder.** The same net won 340 of 500
  runs looking one turn ahead and 417 looking two turns ahead. More
  training did not help. Self-play stopped improving after one round, and
  80,000 training games did no better than 40,000.
- **HP at the boss is worth most where that boss has a cliff.** The
  Guardian is beaten 0.07 of the time from 30 HP and 0.88 from 70 HP.
  Slime Boss is almost safe from 50 HP.
- **An elite costs more than it pays, when it pays no relic.** In the test,
  an elite gives one card offer and no relic. Swapping every elite for a
  hard hallway fight raised the share of runs won from 0.720 to 0.920, in
  50 runs.
- **At the last campfire, just rest.** An AI that played 64 trial boss
  fights for each choice upgraded a card in only 2 runs of 50 and gained
  nothing.
- **The run you draw decides more than the player.** Of 500 runs, 200 were
  won by all three players, even the hand-written one, and 36 were lost by
  all three.
- **New numbers are free; new mechanics cost.** Bigger numbers on familiar
  effects cost the net almost nothing. Of ten real cards it never trained
  on, only Demon Form hurt it, because its Strength arrives next turn, just
  past where a one-turn search looks. Scoring the position after the next
  turn's start fixed that without any training.

## Try it

Developed and tested on Windows only. You need Rust, Python 3.13 and Git.

**Build** the engine as a Python module:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install maturin numpy
cd py && ../.venv/Scripts/maturin develop --release
```

maturin finds `.venv` at the repository root and installs the `sts` module
there. Run the commands below from the repository root (`cd ..` after the
build).

**Watch a combat.** The hand-written player fights Slime Boss and prints
each turn, with the score of every option it considered:

```bash
.venv/Scripts/python scripts/replay.py --encounter slime_boss --agent search --seed 3
```

**Step through the AI's runs in your browser.** The nets need PyTorch. The
explorer replays saved test runs turn by turn as the net played them, and
lets you take over at any decision:

```bash
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python scripts/explore.py
```

Then open http://127.0.0.1:8765.

**Run the best player** on one run of the Act 1 test (it needs PyTorch,
installed in the step above). The current best player's settings are in
`configs/product.json`, and the command below uses them. It writes the run
to `results/gauntlet/`, and `scripts/gauntlet.py read <file a> <file b>`
compares two result files run by run. The [gauntlet
manual](docs/gauntlet.md) explains every option.

<details>
<summary>The command</summary>

```bash
.venv/Scripts/python scripts/gauntlet.py play "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01@tsl1@lcb1" --two-turn --line-seed --step-line --start starter --rewards sim --sim-boss --chooser "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01@lcb1" --sequences 1
```

</details>

**A taste of the Python module:**

```python
import sts
c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], "jaw_worm", seed=1)
print(c.render())                       # HP, the monster's intent, the hand and the piles
c.step(sts.search_action(c, "heuristic"))   # the hand-written player makes one move
games = sts.run("search", sts.make_specs("boss", 100), threads=4)   # 100 boss fights
print(sum(g["won"] for g in games), "of 100 won")
```

The [Python API page](docs/python-api.md) lists the rest.

**Checks**, for anyone changing the code:

```bash
cargo test                      # includes the golden trajectories (engine/tests/golden.rs)
cargo test -p sts-py            # the py crate isn't a default member (feature pins)
cargo test --release --test fuzz -- --ignored
cargo run --release --example bench
.venv/Scripts/python py/tests/test_sts.py
.venv/Scripts/python scripts/eval.py
```

## Where to go next

- **The story, with charts:** the
  [showcase](https://mainzu.github.io/sts-for-ai/showcase/)
  ([showcase/index.html](showcase/index.html) in this repository), or as
  text [showcase/llms.md](showcase/llms.md).
  [showcase/llms-full.md](showcase/llms-full.md) adds every real-game fight,
  a line for each thing tried, and the statistics.
- **How the engine and the AI work:** [docs/concept.md](docs/concept.md).
- **Adding cards, monsters, relics and mechanics:**
  [docs/extending.md](docs/extending.md) and
  [docs/generated-content.md](docs/generated-content.md).
- **Using the tools:** the [Act 1 test (gauntlet)](docs/gauntlet.md),
  [training](docs/training.md), [value nets and the generalisation
  tests](docs/nets.md), the [bench, exact puzzles and ladder](docs/bench.md),
  the [job queue](docs/job-queue.md), [playing the real
  game](docs/real-game.md) and the [Python API](docs/python-api.md).
- **What was tried, and why:** [docs/decisions.md](docs/decisions.md)
  records the project's decisions in order, [docs/research/](docs/research/) holds
  the write-ups of experiments and reviews, and
  [docs/backlog.md](docs/backlog.md) lists ideas not yet run.
- **How the AI sessions ran the project:**
  [docs/operating.md](docs/operating.md), [docs/roles/](docs/roles/) and
  [docs/lanes/](docs/lanes/). [AGENTS.md](AGENTS.md) holds the working
  rules every session reads.
- **Every doc, and where the current facts live:**
  [docs/README.md](docs/README.md).

## About this public copy

This is the public copy of the project, published so that anyone can pick
the work up without rediscovering what was already tried. It includes the
two nets that matter: the best player's net
(`runs/2026-10-29-seed-check-r2-s1-1a789b2`) and the net that played the
real game (`runs/2026-11-10-packnet40k-s201-r1-91c8ae0`). It also includes
the result files behind the showcase's headline numbers. The tools make
`jobs/`, `models/` and the rest of `results/` as they run.

The feature specs are here too: `SPEC.md` (the first one) and
`docs/specs/`, each a plan for one feature, with its checks and what was
built. Some internal files are not here: the owner's idea tracker (the
`ideas#<n>` references), the daily digests, the raw datasets, most run
folders, and the Claude skills the sessions used.

[docs/claims/](docs/claims/) holds the project's short sourced facts:
measurements, causes, decisions in force and how things work, one JSON
file per fact. [kb](https://github.com/Mainzu/kb) reads them. Install it
as a Claude Code plugin (`/plugin marketplace add Mainzu/kb`, then
`/plugin install kb@mainzu`), or clone it at the tag this copy was sealed
with and run it from the root of this repository:

```bash
git clone https://github.com/Mainzu/kb ../kb && git -C ../kb checkout v0.2.0
KB_READONLY=1 python -I ../kb/skills/kb/kb.py render
```

`kb render` prints the current state. `kb find <words>` and `kb get <key>`
look facts up; `get` is instant, while `render`, `list` and `check` hash
every source and take a minute or two. With `KB_READONLY=1` kb writes
nothing: no usage log under `.claude/` and no cache in `.git/`. `kb check`
may still run the shell check commands some facts carry.

The facts were re-sealed for this copy, but more than half still show as
suspect or unchecked. Most cite run results, job records or documents that
aren't published here (`missing:` or `not here (ignored)` in `kb check`),
and the rest depend on those facts. A fact marked clean was checked against
files in this copy.

Commit hashes in the docs and in the facts come from the private history;
this repository starts from a single commit.

Licensed under the MIT license ([LICENSE](LICENSE)). Map icons in
`showcase/rooms/` are from Slay the Spire, by Mega Crit.
