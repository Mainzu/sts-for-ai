# StS simulators and search agents: cards

Angle: StS simulators (sts_lightspeed and forks, other headless engines) and the search agents built on them.
Read method: GitHub README and source files fetched via raw.githubusercontent.com or the GitHub page, and blog/dev.to posts via WebFetch. For source files and posts, the "Read" line gives "full text" only where the fetched content covered the relevant file or post. Where the content came back as a model-produced summary of the page, the card says so in Assumes or Claims. Quoted code expressions are as they appear in the fetched summary of the source file, not verified line by line.

Target was 8. Opened 11 sources (10 papers' worth of cards plus one extra file, listed as separate cards below).

---

### sts_lightspeed README (2020-2024, undated in fetch)
- **Link:** https://github.com/gamerpuppy/sts_lightspeed · **Venue:** GitHub · **Cited by:** n/a (stars not shown in fetch; RelatedRepos listing indexed earlier showed about 64, possibly stale) · **Read:** full text (README)
- **Problem:** A standalone C++17 simulator and tree-search tool for the original Slay the Spire.
- **Method:** Engine plus console simulator, plus a tree search that "uses knowledge of the game's RNG state" (described as giving the "best result"). A tree search without RNG knowledge is listed as planned, not implemented.
- **Assumes:** CPU, C++17, gcc. Implemented scope: "all enemies, all relics, all Ironclad cards, and all colorless cards", and "Everything outside of combat / all acts" (corrected by Opus on 2026-11-15: the README lists this under Implementation Progress, not as unimplemented; the only planned item is search without RNG knowledge). Save-file loading supported only for loading into combat. Built against json and pybind11 submodules.
- **Claims:** "Designed to be 100% RNG accurate*" (asterisk has no footnote in the README). Speed: "1M random playouts in 5s with 16 threads" (no CPU model given). No win-rate or floor results in the README.
- **Evaluation:** None in the README. Fidelity testing against the real game: not covered in the README.
- **Code:** https://github.com/gamerpuppy/sts_lightspeed (license: LICENSE.md linked; type not stated in fetch)
- **Fit:** partial. Good as the reference for a C++ StS1 engine with RNG-aware search and a throughput number, but its fidelity claim is unsupported in the README and the search sees RNG (cheat, see next card), which breaks the "chance averaged exactly" constraint.

---

### BattleScumSearcher2.cpp (sts_lightspeed, src/sim/search) (undated)
- **Link:** https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/sim/search/BattleScumSearcher2.cpp · **Venue:** GitHub (source) · **Cited by:** n/a · **Read:** full text (source file, via WebFetch summary of the file)
- **Problem:** Per-turn combat search inside sts_lightspeed for Slay the Spire.
- **Method:** UCB-style MCTS. Each step restarts at the root, copies the root `BattleContext`, walks down by `selectBestEdgeToSearch` (maximizes `evaluateEdge`), expands all legal child edges at a leaf and picks one uniformly at random, then runs a uniform-random playout to a terminal outcome. Backprop adds the evaluation to every node on the path, including the root. Exploitation term is normalized by the best-minus-min action value range.
- **Assumes:** Discrete actions only (PLAYER_NORMAL: playable cards, potions, END_TURN; CARD_SELECT options per card type). The searcher's own RNG is `randGen`, seeded with `bc.seed+bc.floorNum`. Actions run on a copied `BattleContext`, so any RNG state inside it is copied too. Inputs: a `BattleContext` (game state, seeded).
- **Claims:** No deduplication or transposition table; "Equivalent states reached by different orders are searched separately." No time limit: `search(int64_t simulations)` is a fixed simulation count. Playout = uniform random legal actions until outcome decided; if a state has no legal actions it calls `assert(false)`. Source-level notes from the summary: `bestActionValue` initialized to `std::numeric_limits<double>::min()` (smallest positive double, possibly a bug if values go negative); average computed as `evaluationSum / (count+1)` (the `+1` looks unintended). Exploration constant `explorationParameter = 3*sqrt(2)` (about 4.24).
- **Evaluation:** `evaluateEndState` (default; callers may pass their own `EvalFnc`). Victory: `100 * (35 + bc.player.curHp + potionScore - (bc.turn * 0.01))`, `potionScore = bc.potionCount * 4`. Defeat: damage dealt to non-minion monsters scaled by 10, minus 1 per living monster, minus 0.2 per wasted energy (skipped for Three Shapes and Four Shapes), plus 0.03 per card drawn, plus half the potion score, plus 0.2 per turn survived. No block, debuffs or card-level features.
- **Code:** https://github.com/gamerpuppy/sts_lightspeed (license not confirmed)
- **Fit:** partial. Shows the evaluator's feature set (HP, potions, monster count, energy waste) and the plain-MCTS design with no dedup. Breaks the constraints: the search copies RNG state (so it sees future draws if the copied context holds the seed), no chance averaging, and the evaluator uses no block or debuff features.

---

### BattleScumSearcher2.h (sts_lightspeed, include/sim/search) (undated)
- **Link:** https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/include/sim/search/BattleScumSearcher2.h · **Venue:** GitHub (source) · **Cited by:** n/a · **Read:** full text (source file, via WebFetch summary)
- **Problem:** Class interface for the same MCTS searcher as the card above.
- **Method:** `struct BattleScumSearcher2` with `Node {int64 simulationCount; double evaluationSum; vector<Edge> edges}` and `Edge {Action action; Node node}` (tree owned by value). Root held as `unique_ptr<const BattleContext>`. Constructor `BattleScumSearcher2(const BattleContext&, EvalFnc = &evaluateEndState)`, public `search(int64_t simulations)` and `step()`. Debug helpers `printSearchTree`, `printSearchStack`.
- **Assumes:** A `BattleContext` as the root; `EvalFnc` is `std::function<double(const BattleContext&)>`. No max depth or pruning thresholds given.
- **Claims:** Structural facts only; no performance numbers in this file.
- **Evaluation:** None in the file (the default evaluator body is in the .cpp; see previous card).
- **Code:** https://github.com/gamerpuppy/sts_lightspeed (license not confirmed)
- **Fit:** partial. Useful as the interface for a pluggable evaluator (matches our "value net replaces heuristic" idea at the API level), but it has the same RNG and dedup issues.

---

### ScumSearchAgent2.cpp (sts_lightspeed, src/sim/search) (undated)
- **Link:** https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/sim/search/ScumSearchAgent2.cpp · **Venue:** GitHub (source) · **Cited by:** n/a · **Read:** full text (source file, via WebFetch summary)
- **Problem:** Turn-by-turn combat agent that wraps BattleScumSearcher2 and commits moves.
- **Method:** Repeatedly builds a fresh searcher from the real `bc`, runs `search(simulationCount)` (boss uses `bossSimulationMultiplier * simulationCountBase`), tracks the best outcome sequence by player HP, executes up to `stepsWithSolution` steps from the stored winning line if it ends with positive HP, else walks the root by most-visited child and executes up to `stepsNoSolution` steps. Then re-searches from the real state.
- **Assumes:** Single-battle context, fixed simulation counts (no wall clock). Real game state advances via `a.execute(bc)` on the same `bc`.
- **Claims:** Constants (`simulationCountBase`, `stepsWithSolution`, `stepsNoSolution`) are not in this file, so no values. Possible loop issue noted: if `stepThroughSearchTree` finds no edges it takes no action and the outer loop can re-search without changing state (not verified).
- **Evaluation:** None in this file. The sts-rl-agent card below reports results for this stock MCTS combat.
- **Code:** https://github.com/gamerpuppy/sts_lightspeed (license not confirmed)
- **Fit:** partial. Shows the commit-and-re-search loop, which is the sort of per-turn control we would use. Whether the searcher sees future draws is not settled by this file; the sts-rl-agent README says the teacher does.

---

### sts-rl-agent (Jialeiv) README (2025-2026, undated in fetch)
- **Link:** https://github.com/Jialeiv/sts-rl-agent (also https://huggingface.co/Jialeiv/sts-rl-agent) · **Venue:** GitHub / Hugging Face · **Cited by:** n/a · **Read:** full text (README via raw.githubusercontent)
- **Problem:** Whether a learned non-combat policy on top of the stock sts_lightspeed MCTS combat bot raises floors, and whether combat can be distilled into a network.
- **Method:** Non-combat (map, card rewards, shops, campfires, events): MLP `[128,128]` (about 100k parameters) scoring each legal candidate from a 412-dim observation plus 368-dim candidate descriptor, trained from scratch with REINFORCE. Combat: stock ScumSearch MCTS (BattleScumSearcher2). Six negative results on distilling combat (behavior cloning, DAgger, REINFORCE fine-tune, attention scorer, value net with 1-ply lookahead, PUCT).
- **Assumes:** Ironclad A0 only, simulator-supplied combat. Budgets are simulation counts, no wall clock: MCTS @2000 and @50000 (unclear whether per move or per combat). Hardware: trainer uses 12 workers, "~10 min on a laptop, 12 cores". Python 3.12, `make -j4`.
- **Claims (quoted from README, as fetched):**
  - Headline table (A0 Ironclad, 50 fixed held-out seeds): heuristics + MCTS@2000: avg floor 22.8, win 2%; heuristics + MCTS@50000: 31.2, 6%; learned policy + MCTS@2000: 38.5, 4%; learned policy + MCTS@50000: 42.5, 14%.
  - "~11 floors" = 42.5 minus 31.2 at @50000; 15.7 floors at @2000.
  - Behavior cloning: imitation accuracy 0.59, floor ~12. Value net with 1-ply lookahead: floor ~8, worse than no lookahead. PUCT "loses to blind rollouts" at 100 simulations (26.7 vs 33).
  - README states the teacher "effectively sees the future" (draw order): stated reason imitation fails.
  - Single runs, no confidence intervals. The table predates a combat-rules patch and was not remeasured.
- **Evaluation:** 50 fixed held-out seeds (`eval/eval_seeds_50.txt`), A0 Ironclad, one checkpoint `weights/armG_model_G128x128_15k.pt`.
- **Code:** https://github.com/Jialeiv/sts-rl-agent (license not checked)
- **Fit:** good. Gives the only measured A0 Ironclad floor/win numbers for a stock sts_lightspeed MCTS at two budgets, and documents the draw-order cheat effect on distillation. Breaks constraints: the teacher sees future draws (not chance-averaged), and its combat is not a learned value net over effect primitives.

---

### AutoClad (benmuth) README (undated)
- **Link:** https://github.com/benmuth/AutoClad · **Venue:** GitHub · **Cited by:** 2 stars (shown on page; 0 forks, 0 watchers) · **Read:** full text (GitHub page via WebFetch summary)
- **Problem:** Train neural network agents for Slay the Spire combat via supervised learning, with a long-term goal of "Ascension 20 Ironclad".
- **Method:** Forks sts_lightspeed. Generate battle scenarios (`randomize_scenarios.py` randomizes HP, deck and RNG seeds), run SimpleAgent as the baseline, extract state-action pairs from snapshots, train a network to imitate it, export TorchScript for C++ inference.
- **Assumes:** Jaw Worm encounters only (current scope). Inputs are snapshot state-action pairs; RNG treatment beyond randomized seeds not described.
- **Claims:** None. "Currently focused on benchmarking different approaches"; no win rates, floors or timings given. Tree search listed as a planned data source, not implemented.
- **Evaluation:** Jaw Worm scenarios from randomized base scenarios.
- **Code:** https://github.com/benmuth/AutoClad (license file linked but type not stated in fetch)
- **Fit:** partial. Shows the imitation-from-simple-agent pipeline on sts_lightspeed snapshots. Very small scope and no results, so little to measure against.

---

### sts2-lightspeed (yizhang-dream) README (2026, undated)
- **Link:** https://github.com/yizhang-dream/sts2-lightspeed · **Venue:** GitHub · **Cited by:** 1 star (shown; 0 forks, 0 watchers, 2 commits) · **Read:** full text (README via WebFetch summary)
- **Problem:** RNG-faithful C++ engine for Slay the Spire 2 (not StS1), with MCTS battle search, full-run RL environment and Python bindings. Unofficial, not affiliated with MegaCrit.
- **Method:** MCTS described as a structural port of BattleScumSearcher2: UCB playouts, progressive bias, transposition dedup, balanced root sampling. Per-node state snapshots and buffer reuse added. REINFORCE trainer in Python.
- **Assumes:** C++20, no external deps (nlohmann/json vendored), optional pybind11. "Every random stream is seeded and consumed in the game's order." Run-level determinism check: `run determinism <seed>`. Budgets: 2000 simulations per battle in the full-run example (300 and 500 in others).
- **Claims (as stated):** "~21 µs per MCTS simulation single-threaded (bench-tuned build, desktop CPU)". Full run at 2000 simulations per battle: "~1.5 s". A 12-process worker pool sustains "~3.3 runs/second at that budget". CPU model not named. Replay-parity gate: 65 recorded real-game positions replayed step by step, requires zero field diffs (`tools/parity_batch.sh`, wired into CI). Fields compared and capture method not listed. Mean floors "fall off a cliff at A8/A9" (qualitative). No win rates in the README.
- **Evaluation:** Replay-parity gate on 65 recorded positions; `search bench` on that corpus at 2000 simulations.
- **Code:** https://github.com/yizhang-dream/sts2-lightspeed (MIT)
- **Fit:** partial. Best fidelity-testing design among the sources (recorded real-game positions, zero-diff gate in CI) and a speed figure per simulation. But it is StS2, and its search reads seeded RNG, which the README does not clarify for chance nodes.

---

### AlphaStS devlog part 3, "Good models finish last" (Doron Singer, dev.to) (2024-2025, undated in fetch)
- **Link:** https://dev.to/doronsinger/part-3-good-models-finish-last-2n6a · **Venue:** dev.to blog · **Cited by:** n/a · **Read:** full text (post via WebFetch summary)
- **Problem:** Card-reward picking for a Silent agent (the post does not cover search).
- **Method:** Logistic regression over 113 cards (first model, "glorified tier list"), then a larger model (308 input features, 128-wide state encoder, 32-wide card encoder, about 202,000 parameters) trained to predict human picks among three rewards plus skip.
- **Assumes:** Dataset of 334 own A20 runs (41% win rate), then a 77-million-run database with 34,210 Silent runs and 358,870 card-pick decisions (A20 win rate 1.5%).
- **Claims:** Offline accuracy 53.5% (larger model), 55.8% with card ID embeddings. In-game on 50 seeds (beat expert / lost / tied, rank): embeddings 55.8% offline, 12/23/15, 4th; mechanical features only 53.5%, 16/16/18, 1st; embeddings plus propensity 52.3%, 15/22/13, 3rd; propensity only 49.5%, 14/21/15, 2nd. Better offline prediction did not give better in-game play. The best learned model still lost to the hand-crafted bottled AI card list.
- **Evaluation:** 50 seeds, in-game vs an expert baseline.
- **Code:** none found
- **Fit:** poor for search. Relevant only as a warning that offline fit to human choices did not track in-game strength. It does not touch combat search or chance.

---

### AlphaStS devlog part 6, "What not to consider" (Doron Singer, dev.to) (undated in fetch)
- **Link:** https://dev.to/doronsinger/part-6-what-not-to-consider-54g5 · **Venue:** dev.to blog · **Cited by:** n/a · **Read:** full text (post via WebFetch summary)
- **Problem:** Why a clone-and-rollback search agent for StS (Silent, per the series) underperforms bottled_ai's BFS on floors.
- **Method:** AlphaStS: clone a game state, simulate ahead, roll back. Search with a handcrafted state evaluator at the horizon; dominance pruning; a 512-state breadth cap added (by an AI assistant, per the post) for speed. Draw RNG makes deep lookahead "not really feasible in most fights", so a heuristic scores the horizon.
- **Assumes:** Silent character; per-decision wall-clock budgets (500 ms handcrafted; 5 s hallway / 20 s boss). Post does not say whether search sees future draws or treats them as chance. No state dedup or caching mentioned beyond dominance pruning.
- **Claims (as fetched):** Dominance pruning "eliminated 90-94% of the game states that were being considered earlier: a 10x speedup." Expert BFS (bottled_ai, "simple BFS search capped at 11,000 states"): avg floor 34.0, 26% wins. AlphaStS + handcrafted 500 ms: 19.3 floors, 0%. Same at 5 s/20 s: 24.0, 0%. Dominance-pruned direct search 5 s/20 s: 28.7, 2 of 30 wins (6.7%). Speed: bottled_ai 15 steps/s; AlphaStS + handcrafted 237 steps/s (215 after fix); AlphaStS + learned evaluator 147 steps/s. Learned evaluator (MLP 638→256→128→1, 89K samples from 30 games) at 3 s/10 s, 5 seeds: 31.2 floors; at 5 s/20 s, 30 games: 27.2 vs 28.8 handcrafted.
- **Evaluation:** Floor and win rate over fixed seeds (30 games in the larger test, 5 seeds in one case); Silent.
- **Code:** none found
- **Fit:** partial. Concrete evidence that breadth caps and per-state rollback search lose to a plain BFS with a cap of 11,000 states, and that pruning gave 10x. The post does not state the RNG treatment, which is the question we need answered.

---

### mini-spire (Rob Pitkin) blog post (undated in fetch)
- **Link:** https://rhp.bearblog.dev/mini-spire/ · **Venue:** blog · **Cited by:** n/a · **Read:** full text (post via WebFetch summary)
- **Problem:** Combat-only RL environment for StS: a C++ recreation with Python Gymnasium-style bindings.
- **Method:** No search. Maskable PPO (Stable-Baselines3, about 15k parameters) on a flat 45-float observation and 7 discrete actions (6 cards + end turn), with action masking.
- **Assumes:** Ironclad starter deck, one fight against Jaw Worm only. Map generation and state persistence between fights are long-term goals. Design described as modular for more enemies.
- **Claims:** Random policy won about 52% of fights. About 90% wins at roughly 50k training steps; stopped losing by about 80k. 1 million timesteps. "~145k steps/sec with a single environment" on a 2020 M1 MacBook Pro CPU; about 4,300 env steps/sec during training (about four minutes for 1M steps). Engine fidelity to the real game: not described. RNG handling: not described.
- **Evaluation:** Jaw Worm single fight, win rate.
- **Code:** https://github.com/rob-pitkin/mini-spire (license not stated in the post)
- **Fit:** partial. Useful as a throughput reference for a small C++ StS combat env with a Gymnasium-style API. No fidelity check and no search, so it does not meet the fidelity or search parts of our constraints.

---

### conquer-the-spire (utilforever) README (2019, from repo page)
- **Link:** https://github.com/utilforever/conquer-the-spire · **Venue:** GitHub · **Cited by:** 39 stars (shown; 5 forks, 3 watchers, 26 commits on master, 4 open issues) · **Read:** full text (README via WebFetch summary)
- **Problem:** Slay the Spire simulator in C++17 covering all three characters (Ironclad, Silent, Defect), with console and GUI program, C++ and Python API.
- **Method:** Simulator only. RL listed as planned: "Connecting with PyTorch C++ API" and "Applying DQN and so on." No search described.
- **Assumes:** macOS 10.14+, Ubuntu 18.04+, Windows (VS 2017+), WSL. Scope includes colorless, status and curse cards, monsters, elites, bosses, events, relics, potions, merchants and Ascension.
- **Claims:** None. No benchmarks, win rates or training results. Fidelity to the real game not described. RNG not described.
- **Evaluation:** None given.
- **Code:** https://github.com/utilforever/conquer-the-spire (MIT, copyright 2019 Chris Ohk and Gyojun Youn)
- **Fit:** poor for search, partial as an engine reference (multi-character coverage). No fidelity or RNG claims to check.

---

## Not opened or not found (for the next review)

- **ScumTheSpire** (https://github.com/cn4750/scumthespire): HTTP 404 on WebFetch. Not opened. A name from a search result; may be a scum/seed tool, unverified.
- **bottled_ai** (xaved88): repo not found by search. Its approach is described second-hand in the AlphaStS part 6 post (simple BFS, cap 11,000 states, commits to full-turn plans). Not opened directly. (Correction: it exists at github.com/xaved88/bottled_ai; see `sts1-rule-bots.md`.)
- **sts-ironclad-agent**, and any patched sts_lightspeed inside it: search returned only unrelated "STS" projects. Not found. (Correction: it exists at github.com/destire-mio/sts-ironclad-agent, MIT; read by hand for the report.)
- **JonJac/sts_lightspeed** fork (https://gh.r-mj.com/JonJac/sts_lightspeed): seen in a search snippet only; not opened.
- **Reddit**: no r/slaythespire thread surfaced. A LibHunt page cited a Reddit post about sts_lightspeed having Ironclad and MCTS "similar to pasha's" (not opened).
- **Fidelity testing for sts_lightspeed** against the real game: the README is silent, and no separate fidelity report was found. Only sts2-lightspeed has a documented parity gate (65 positions).
- **Carleton honours project** and ceur-ws.org Vol-3926 paper7: seen in results, not opened (probably the other angle's academic scope).

## Summary of cross-cutting points for this angle

- **Cheating (seeded RNG visible to search):** sts_lightspeed's tree search is described as using RNG state knowledge; the sts-rl-agent README says the stock teacher "effectively sees the future". No source here averages draw chance exactly.
- **Dedup:** BattleScumSearcher2 has none (per source summary). sts2-lightspeed's port adds transposition dedup. AlphaStS relies on dominance pruning (90-94% of states removed).
- **Rollouts:** uniform random in BattleScumSearcher2.
- **Budgets:** fixed simulation counts (2000, 50000 for stock MCTS; 2000 per battle for sts2-lightspeed) or wall-clock per decision (AlphaStS 500 ms to 20 s).
- **Measured results on A0 Ironclad (StS1):** only the sts-rl-agent table (MCTS@50000: floor 31.2, 6% win; with a learned non-combat layer: 42.5, 14%). Single runs, 50 seeds.

Sources:
- [sts_lightspeed README](https://github.com/gamerpuppy/sts_lightspeed)
- [BattleScumSearcher2.cpp](https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/sim/search/BattleScumSearcher2.cpp)
- [BattleScumSearcher2.h](https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/include/sim/search/BattleScumSearcher2.h)
- [ScumSearchAgent2.cpp](https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/sim/search/ScumSearchAgent2.cpp)
- [sts-rl-agent README](https://github.com/Jialeiv/sts-rl-agent)
- [AutoClad](https://github.com/benmuth/AutoClad)
- [sts2-lightspeed](https://github.com/yizhang-dream/sts2-lightspeed)
- [AlphaStS part 3](https://dev.to/doronsinger/part-3-good-models-finish-last-2n6a)
- [AlphaStS part 6](https://dev.to/doronsinger/part-6-what-not-to-consider-54g5)
- [mini-spire](https://rhp.bearblog.dev/mini-spire/)
- [conquer-the-spire](https://github.com/utilforever/conquer-the-spire)
