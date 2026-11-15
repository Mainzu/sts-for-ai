# Earlier Slay the Spire AIs: what to borrow, where we lead (prior-art survey)

Started 2026-11-15 with the owner. The owner asked for every StS AI before
ours: what they do that could improve or streamline our work, and what we
already do better than most. The earlier scan
(`docs/research/sts-bots-and-runs.md`, 2026-11-01) covered SpireBench,
sts-ironclad-agent and AIVAT; this one is wider and looks for practices to
borrow, not only a yardstick.

## First principles

- **Wanted:** concrete practices from earlier StS agents (StS1, StS2, LLM
  agents) that would raise the product's play or cut machine time or code,
  each with its evidence; and a fair comparison of where our design leads.
- **Areas (owner):** combat play (search, value net), the run layer (map,
  card picks, rest sites, shops, events, potions), machine time (simulator
  speed, games per answer, training cost), and new content (goal 1: cards,
  powers, enemies never trained on).
- **Streamline means (owner):** fewer CPU-hours per answer and less code to
  keep in step; not fewer process steps, not less work per content item.
- **Where we stand:** Act 1 Ironclad engine checked against the real game
  (10,521 of 10,562 chance-free steps predicted right over all live
  records); product = two-turn expectimax over a ~190k-parameter value net
  on effect primitives; headline gauntlet 0.834 Act 1 clears (A0,
  simulated); real game: A0 Act 1 boss beaten in 22 of 27 runs, A20 in 18
  of 33 (run rules 5 with fight guard 1), with a fixed-rule run layer.
- **Constraints:**
  - CPU only, one dev machine (**hard**: the machine).
  - Content is checked against the game's own code; sts_lightspeed and the
    wiki are leads (**hard**: `decision/parity-source`).
  - Changes are judged on the headline gauntlet protocol (**hard**:
    `yardstick/protocol`, `docs/direction.md`).
  - Goal 1 weighs 0.8 of development: an idea that only works on official
    content counts for goal 2 only (**hard**: direction.md).
  - No language model in the loop (**hard**: the owner, this survey).
  - Chance is averaged exactly where feasible, sampled only where not
    (**hard**: direction.md "Exact before sampling").
  - Holding a potion is worth nothing for now (**hard**: decisions
    "Potions, spec decisions (owner, 2026-11-11)").
  - Human run logs, outside MIT code and a lasting hand-written run layer
    are allowed if the evidence shows they pay (**soft**: the owner, this
    survey).
  - Our Rust engine stays the one simulator (**assumed**).
  - The agent must not see the game's hidden random state (**hard** in
    effect: decisions "Step 4: Python bindings, features, replay": option
    states get an RNG derived from the combat's, "so stepping them can't
    peek";
    `docs/research/learned-play-and-generalisation.md` "no peeking").

## Search

Nine angles, one paper scout each (cards in `sts-ai-prior-art/cards/`):
`sts1-rule-bots`, `sts-simulators-search`, `sts-rl-agents`,
`sts-human-data`, `sts-academic`, `sts2-agents`, `sts-llm-agents`, and two
outside the field, `ccg-unseen-cards` (Hearthstone, MTG, LoCM, Dominion
agents on unseen cards) and `backgammon-engines` (TD-Gammon, GNU
Backgammon, wildbg; the design ours follows). The scouts opened 99
sources. Most StS AI work lives in GitHub repos and blogs, not papers, and
the scouts missed much of it, so a census agent then searched
slaythespire.dev/projects and GitHub and found 34 more projects
(`cards/census.md`), among them the two strongest honest bots (silverbot,
Spire Mentor).

Verified by hand (full text): sts-ironclad-agent's README, student and
combat-engine READMEs and eight of its docs (evaluation, status, fight
decomposition, search entry, RNG gate, history, training lessons; the
Chinese design plans through a reader agent); Doron Singer's dev.to parts
3 and 6-11 (full Markdown through the dev.to API); the READMEs of
silverbot, sts_lightspeed, AlphaStS, bottled_ai (win rates), StS_predict
and sts2-lightspeed; GNU Backgammon's manual pages on move filters and
pruning nets; arXiv 2407.05879 (MTG, Table II); arXiv 2611.12088 (sts2ai,
abstract and Table 5); Epoch's SpireClimb page. Seven claims the
recommendations rest on then went to one skeptic each, who checked the
outside source and this repo's decisions, backlog and claims. One claim
was refuted (the move filter has been tried here), five held with
corrections, one (clairvoyance) held only after narrowing.

Scout quality: of 14 cards checked against their sources, 3 were wrong
(sts_lightspeed's README lists everything outside combat as implemented,
not planned; sts-ironclad-agent and bottled_ai exist although two scouts
reported them "not found"), and the census found 34 projects the scouts
never reached. For hobby fields like this one, the GitHub CLI and the
community project index are the sources that work; paper indexes are not.

## The field at a glance

Strongest reported results, by what plays the fights. "Foresight" means
the combat search reads the game's hidden random state (draw order, enemy
move rolls), which a human can't.

| Agent | Combat | Foresight | Run layer | Best result | Runs |
|---|---|---|---|---|---|
| sts-ironclad-agent (StS1, MIT) | sts_lightspeed MCTS, 32k simulations a round, 384k at bosses | **yes**: the live bridge imports the game's 6 combat RNG streams and pile order and searches on that copy | rules + value tables, distilled into one net (11195-384-1) by cloning 3,000 teacher games + 2 DAgger rounds | A20 Ironclad Heart **50.1%** [45.7, 54.5], real game | 501 |
| silverbot (StS1, MIT, sts_lightspeed fork) | expectimax MCTS with chance nodes, heuristic rollouts | no | transformer over candidate tokens, PPO, 512 games per iteration | A20 Heart **18.6% ± 2.4%**, A0 ~83% (simulated) | 1,000 / 600 |
| Spire Mentor (StS2, MIT, Rust) | MCTS with a learned playout net, 8,000 simulations | no | PPO policy | A10 14.0% in its own engine, **8.8%** in the game's engine (measured by sts2ai) | 2,000 |
| sts2ai (StS2, GPL-2.0) | none: one 6.6M-parameter transformer pass per action | no | same net | A10 8.05% (5 characters), A0 80.2% | 12,800 |
| sts-rl-agent (StS1, MIT) | stock sts_lightspeed MCTS | yes | REINFORCE MLP (~100k) | A0 14%, floor 42.5 (MCTS@50000) | 50 |
| bottled_ai (StS1, MIT) | BFS over its own turn simulation, cap 11,000 paths | no | per-strategy priority lists | Ironclad 20% (CI 8.9-31.1), Watcher 52%; Ascension not stated | ~50 each |
| Doron Singer's agent (StS1 Silent, on AlphaStS) | BFS + dominance pruning + learned evaluator | yes (bug kept on purpose) | pick model, cloned from bottled_ai | 0-15% wins A0, Act 1 about half | 20-30 |
| STS2FableBot (StS2, MIT) | depth-first turn search on the visible board | no | DP routes, hand-scored drafts | A0 20.7% (CI 16-25), real game | 343 |
| LLM agents | the model | no | the model | SpireClimb: best 20% A20 Heart (15 attempts per character); SpireBench: top models 90% Act 1 at A20 (10 seeds) | 10-15 |
| **ours** | two-turn expectimax over an effect-primitive value net | no | fixed rules + sim chooser for card picks | A20 Act 1 boss beaten 18 of 33 (55% ± 9), A0 22 of 27, real game | 33 / 27 |

Human reference points at A20 Act 1 (SpireBench, from Mega Crit's
telemetry): all players 47%, 1000+ hour players 54%, streamers 85-92%.

## Where we already lead

1. **Exact chance, honest information.** Our search lists small chance
   events (up to 16 outcomes) with their probabilities and averages them
   exactly, samples only EndTurn's new hand, and cannot see the hidden
   RNG (state holds none; `engine/src/state.rs`). The best-known number in
   the field, sts-ironclad-agent's 50.1%, is played with foresight; so is
   anything built on stock sts_lightspeed (its README: "knowing the state
   of the game's rng"). Doron Singer measured what foresight is worth on 8
   of his fights: hallway HP lost 12 with it, 90 without. Honest search
   exists elsewhere too (silverbot, Spire Mentor), and silverbot arrived at
   the same information-set pile we use (unknown region kept sorted, known
   top), but none of them averages chance exactly; they sample.
2. **A learned leaf that beats a hand-written one inside search.** Two
   turns deep, our net leaf beats the heuristic leaf by +0.060 clears and
   +5.21 HP on sequences 0-249 (`measurement/leaf-vs-heuristic`); the
   one-turn net even beats the heuristic leaf searched two turns deep, by
   +5.41 HP (`measurement/depth-anchor@headline`). Elsewhere learned guidance mostly
   lost: sts-rl-agent's policy/value PUCT lost to blind rollouts at equal
   budget (26.7 vs 33 floors), sts-ironclad-agent's learned PUCT prior lost
   (16 vs 20 wins at 6.31x the time), Doron's learned evaluator tied his
   hand-written one (27.2 vs 28.8 floors), AscensionAI's learned policy won
   44% of bosses where a 1-ply replay search won 75-88% (its project
   page). silverbot still rolls out a heuristic.
3. **New content (goal 1): no one else tries.** Every other StS agent reads
   cards by identity (silverbot: "identity + upgrade count"; sts-rl-agent
   and sts-ironclad-agent: card vocab files; spirecomm and bottled_ai:
   priority lists by name). Our effects net prices unseen official cards
   +3.02 HP over the ids control, and broad generated training cuts 0.76 of
   the cost of held-out mechanic pairings (`cause/unseen-cards-encoding`,
   `measurement/genpack-transfer@three-seeds`). The nearest outside
   evidence (MTG drafting, arXiv 2407.05879) falls from 67.8% on known
   cards to 33.6% on unseen sets with card features; one-hot can't score
   unseen cards at all.
4. **Content as data, checked against the jar.** All other engines
   hard-code content in C++, Java, C# or Python. Ours loads it from files
   through the registry, and every Act 1 card, relic and monster is checked
   against the decompiled game (`decision/parity-source`). Only silverbot
   (decompiled-source audit, divergence treated as a crash) checks as
   strictly; sts-ironclad-agent's parity status is "INCOMPLETE",
   sts2-lightspeed's CI replays 65 positions but its script exits 0 on
   diffs, and sts_lightspeed publishes no check.
5. **Measurement.** Paired SPRT on 500 sequences with a confirm block, MDE
   gates before a run, seed-sd measured. Only sts-ironclad-agent (2,000 and
   1,000-game seed blocks, fresh seeds, bootstrap CIs) and silverbot
   (matched seeds, McNemar) are as careful; most others report 20-50 runs
   with no interval, and Doron documents being misled by 5-seed reads.
6. **An exact solver as ground truth.** No other StS project has one.

## Where we trail

1. **The run layer, by the field's own numbers.** Every strong bot learned
   or tuned its run layer on a full-run simulator, over thousands of games:
   silverbot (PPO, 512 games per iteration), sts-rl-agent (a learned
   out-of-combat layer took floors from 31.2 to 42.5, where 25x the MCTS
   budget took them from 22.8 to 31.2), sts-ironclad-agent (out-of-combat
   arms and the boss budget took Heart wins from 7.6% to 50%). Ours is
   fixed rules plus the sim chooser, tuned on about 33 real-game runs a
   day, with no map, gold, shop or event model in the simulator.
2. **Scope.** Act 1 only; the others play all acts.
3. **Strength at A20 Act 1.** Our 55% (± 9) sits with 1000+ hour humans
   (54%) and above bottled_ai (SpireBench: 20%), below the top LLM agents
   (90% of 10) and sts-ironclad-agent (about 89% in its simulator, with
   foresight). Ten of our 15 A20 losses are at the boss, eight of them
   Hexaghost (1 of 9 beaten).
4. **CPU per fight.** The product spends about 12 thread-seconds a fight
   (2.25 thread-minutes per 11-fight sequence). sts-ironclad-agent plays a
   whole A20 run in about a core-minute, Spire Mentor takes ~112 ms per
   combat decision, sts2ai 21-27 ms.
5. **Carried resources.** The others put a constant price on what a fight
   leaves behind: sts_lightspeed's evaluator counts a potion as 4 HP
   (`100 * (35 + HP + 4 * potions)`), silverbot scores "potions kept" and
   gold, sts-ironclad-agent prices thief gold at about 10 gold per HP. Ours
   prices none, by the owner's decision, and the live bot drank a Blood
   Potion at 73 of 78 HP (run 81, backlog 83).

## Already tried here (don't re-propose)

The skeptics found these borrowings already measured in this repo:

- **GNU Backgammon's move filter** (search only the top few moves deeper):
  two-turn's pick among one-turn's top 3 scored +0.005 (0.009) against the
  fallback player, and restricting turn 2 to the top-3 root options saved
  only ~3% of nodes, because different first plays reach the same
  end-of-turn states and the search already merges them (decisions "Top-3
  two-turn player: no change", "Selective two-turn search: fails its first
  check"). The variant that saves nodes, turn 2 under the K best
  end-of-turn states (end_k), reached 2.4x at 90% agreement and failed its
  rule; it sits unmerged on a branch.
- Truncated Monte Carlo rollouts (Tesauro and Galperin): rollout leaf +0.67
  HP lost (`measurement/rollout-leaf@elites`).
- More samples at EndTurn: 16 hands vs 4, -0.34 HP at 1.6x
  (`measurement/hands16@elite-replay`); more depth: three turns on elites
  (`cause/depth-saturated`).
- Distilling search into the net (sts-rl-agent's six failures): our
  distillation of two-turn values closed (decisions "Distillation closed").
- A fitted run-value chooser for card picks (StS_predict's approach): lost
  to the sim chooser, -0.044 clears (`measurement/vrun-chooser@headline`).
- Luck-corrected reads (AIVAT): worse, sd ratio 1.41.

## Candidates to borrow: fit table

Constraint columns: CPU, jar (content checked against the game's code),
goal 1 (general beyond official content), exact (chance averaged where
feasible), owner (fits the owner's recorded decisions).

| # | Practice (source) | CPU | jar | goal 1 | exact | owner | Size | Rating |
|---|---|---|---|---|---|---|---|---|
| A | Frozen real-game parity corpus as a test (sts2-lightspeed; silverbot treats any divergence as a crash) | meets | meets | meets | meets | meets | S | likely |
| B | Build the run simulator from sts_lightspeed's out-of-combat code as the reference, checked against the jar (silverbot did this) | meets | meets (lead + jar check) | adaptable | meets | **open owner decision** | L | likely for speed of building |
| C | Learned run policy over candidate tokens (silverbot; sts-ironclad-agent's student; sts-rl-agent) | meets | n/a | adaptable (effect vectors in place of card ids) | n/a | after B | M-L | even |
| D | Failure-driven training allocation: weight training fights by where runs are lost (sts2ai: +3.6 points on Regent, mixed on Silent) | meets | n/a | meets | n/a | meets the training rule (new data) | S-M | even |
| E | More samples or depth at the boss only (sts-ironclad-agent's 12x boss budget) | meets | n/a | meets | meets | meets | S | long shot |
| F | Constant price for potions kept (sts_lightspeed: 4 HP each) | meets | n/a | adaptable | meets | **breaks** "holding a potion is worth nothing for now" | S | even |
| G | Fighter benchmark against humans on the same fight starts, rebuilt from Mega Crit's 77M-run dump (Doron's method on his own 150 games) | meets | n/a | official only | n/a | allowed | M | long shot |

Notes per row:

- **A.** Live records hold ~10.5k candidate steps, but only as raw views in
  `states.jsonl` (~20 MB a run, gitignored); predictions aren't stored, so
  a step is rebuilt from the view before it, the action and the view after
  (`Combat.from_view` plus a step, compared with `real_game.compare`).
  2,000 frozen steps come to ~0.5 MB gzipped. Every rule fix then runs
  against real-game behaviour, not only against golden.txt, and new live
  bugs become corpus entries instead of hand-copied views like
  `RUN78_VIEW`. Backlog 86 (chance steps) extends it: the observed outcome
  must be one the engine lists with probability > 0. Backlog 12
  (parity-harness-level0, closed 2026-11-13 as answered by the bridge's
  live fidelity number) was a check against sts_lightspeed; this one
  replays the real game's own behaviour, and keeps it after the live runs
  move on.
- **B.** sts_lightspeed (MIT, 109 stars) implements map generation,
  rewards, shops, Neow and campfires (Map.cpp 20 KB, Shop.cpp 9 KB,
  Neow.cpp 4 KB), with events folded into a 114 KB GameContext.cpp that
  still carries TODOs (Colosseum, Necronomicon, Prayer Wheel rewards).
  sts-ironclad-agent carries a `sim_patch/` tree of ~500 files of
  alignment patches and parity tests on it, so the jar check stays. The
  owner's order (backlog 83: run decision maker after gold, shops and
  events) and the open simulator decision (decisions "Card-rewards spec
  confirmed (owner away, 2026-11-02)": building on sts_lightspeed is "the
  owner's call") govern it; "Navigator's first defaults (on the owner's
  behalf, 2026-11-03)" rejects sts_lightspeed as a play or training engine,
  which this isn't.
- **C.** silverbot embeds every visible item and every legal choice as a
  token, so new choice types need embeddings, not new heads. Its card
  tokens are identities; ours would carry effect vectors. sts-ironclad-agent's
  lesson: the student matched the teacher on 92-94% of map, card and rest
  choices but only 72-75% of shop and multi-card choices, and lost 4.6
  points; the teacher's quality is what counts.
- **D.** The final-round lane trains at A20 now; Hexaghost is 8 of 15
  losses. Allocating training fights by loss share is new data, which the
  owner's training rule allows. sts2ai's evidence is one character
  consistent, one not.
- **E.** The boss node cap is rarely hit (0-3%, `measurement/cut-share@400k`),
  so the lever would be samples or depth at the boss, not nodes. The
  source itself is saturated: Act 2 boss 74.5/79.5/81.5% at 3x/12x/24x, the
  Heart flat; Doron's doubled boss budget helped as often as it hurt.
  Three turns at bosses was turned down here as undetectable on 77
  Hexaghost fights.
- **F.** One constant in the leaf. Cheapest probe: replay run 81's floor-16
  decision with potions held x 4 HP and see whether the Blood Potion drops
  below Bash+. It conflicts with an owner decision, so it is a framing
  (below), not a recommendation.
- **G.** The dump has no licence anywhere (archive.org copy, 27.1 GB). Deck
  rebuilds miss Neow cards and relic transforms (StS_predict matched the
  final deck in 196 of 300 runs), there is no skill label, and
  `potions_floor_usage` doesn't name the potion. Human data has also lost
  every head-to-head with simulation here: StS_predict's simulator-trained
  pick model gained +9.19 floors over the built-in, its human-trained one
  +3.93; sts-ironclad-agent's imitation of Baalorlord's picks (higher
  agreement) won fewer games; Doron's best human-pick imitator played
  worst.

## Alternative framings

1. **Borrow the run simulator rather than design it.** Today the run layer
   waits for gold, shops and events to be built from the jar. The framing:
   port sts_lightspeed's out-of-combat code (MIT) as the first draft of
   each piece, then check it against the jar the way content is checked.
   It changes `decision/parity-source` only in order (lead first, jar
   check second, as for monsters and relics already). It loses nothing the
   jar check doesn't catch. It enables simulated full Act 1 runs, which is
   where every strong bot found most of its strength (B, then C).
2. **Price carried resources now, at a constant.** Today holding a potion
   is worth nothing until a run prices carrying it. The framing: a constant
   per potion kept (4 HP, sts_lightspeed's value) in every leaf until the
   run layer replaces it with a measured value. It loses the purity of the
   per-fight score; it enables the live bot to keep potions for the boss.
3. **Use the field's Act 1 column as goal 2's outside ruler now.** The
   field reports full runs, but SpireBench and sts-ironclad-agent's stage
   table give A20 Act 1 numbers: humans 47%, 1000+ hour players 54%,
   streamers 85-92%, top LLM agents 90%, sts-ironclad-agent ~89% (with
   foresight). Our real-game A20 Act 1 boss rate (55% ± 9) is directly on
   that scale. Nothing to build; it needs more real-game runs per setting
   to narrow the interval. It loses full-run comparability, which needs
   Acts 2-4.

## Recommendation

- **Now, inside the standing grants: A**, the frozen real-game parity
  corpus. It is small (a rebuild script, one test, ~0.5 MB of data), meets
  every constraint, catches regressions against the real game while Act 1
  content keeps landing, and turns future live bugs into data instead of
  hand-written tests (less code). Its check is borrowed: zero diffs, and
  unlike sts2-lightspeed the test must actually fail on a diff.
- **For the owner: framing 1 (B, then C)**. The field's clearest lesson is
  that the run layer, learned or tuned on a full-run simulator, carried the
  strong bots; it is goal 2's largest gap and the owner's own order puts
  it after gold, shops and events, which framing 1 makes faster to build.
  The owner's answer (2026-11-15): not a direct port; design the run
  simulator for this project's needs, improve on sts_lightspeed, and weigh
  other options first. That study is the next section.
- **For the navigator, optional: D** as an input to the final-round lane's
  A20 training, judged on the protocol like any recipe change.
- E and G lost: E's source is saturated and our cap isn't binding; G has no
  licence, weak reconstruction, and human data lost to simulation in every
  test found. F waits on the owner (framing 2).

## Run simulator: options (owner, 2026-11-15)

The owner prefers not to port sts_lightspeed: its out-of-combat code was
written by hand, before coding agents, for seed-exact play, with every
event a C++ case inside one 114 KB file. The simulator should be designed
for what this project needs and improve on it (decisions "Run simulator:
our own design, sts_lightspeed a lead, options weighed first", provisional).
A design workflow gave four designers one approach each, then three judges
(goal fit, cost and code, risk) scored all four. The raw designs and scores
are in `sts-ai-prior-art/run-sim-designs.md`.

**The needs** they were weighed against: run content as data, so custom
and generated events, relics, shop items and Neow options load like
official ones (goal 1); many cheap simulated A20 Act 1 runs (goal 2); the
jar decides; the agent sees only what a player sees; small chance averaged
exactly; little code, shared with the real-game bridge; fits the R2 draft
(`docs/specs/run-layer-relics.md`) and backlog 83's order.

**Facts checked by hand.** The live records hold 90 runs, each with its
seed and Act 1 map, and 34 distinct events, but no shop screen (the bot
walks past shops). The game's JRE ships `jjs.exe` (Nashorn), so the jar's
own `Random` and `MapGenerator` can be called from a script with no
compile step. The registry rejects unknown keys, so where a relic's `run`
part lives must be settled with the R2 session before either side builds.
Fights decide CPU: a Python run layer is about 1-5% of a run whose fights
are played one turn deep and under 0.3% two turns deep (a Rust one far
less), and becomes most of the cost only if fights are settled by a
value-net estimate (designers' estimates).

| Design | Idea | Goal fit | Cost and code | Risk | Mean |
|---|---|---|---|---|---|
| A. Registry content (Rust) | run vocabulary and events as data in the Rust registry, one Rust run machine | **9** | 6 | 6 | 7.0 |
| B. Jar as oracle | the game's own Java code headless, as referee or simulator | 8 | 4 | 4.5 | 5.5 |
| C. Thin, shared with the bridge (Python) | one run interface, two backends (simulator, real game), Python for clarity | 7 | **8** | **7** | **7.3** |
| D. Abstract model first | distributions from the jar's tables, exact only where a decision changes | 6.5 | 7 | 5.5 | 6.3 |

**Where all four agree**, and where each improves on sts_lightspeed:

- Content is rows in one closed, worded run vocabulary (gain or lose
  gold, HP, max HP; add, remove, upgrade, transform cards; obtain a relic
  or potion; start a fight; open a reward; conditions on gold, HP, relics,
  ascension), with events as small screen machines in data. Only the map
  generator and the RNG are code. Each jar class becomes one row plus one
  test, which Claude Code workers can extract in parallel and a program
  can check.
- Every random procedure is written once against a chance interface with
  swappable sources: the game's own RNG (seed-exact replay of logged
  runs), fast sampling (volume), exact enumeration where outcomes are few
  (a card reward's rarity roll, which event a ? room holds, a coin flip),
  and the outcome the game showed (the bridge). sts_lightspeed can only
  roll its seeded streams, and its search reads them.
- Hidden information stays out of the state by construction: the run
  state holds no RNG, outcomes roll when they become visible, and a leak
  test checks that two runs with equal observations and different seeds
  give the agent identical choices.
- The simulator and the bridge share one decision interface, so the run
  policy, logs and reports are written once; `real_game_run.py`'s rules
  become one chooser behind it.
- Seed-exact only where it is cheap and checkable (map, monster lists,
  boss, Neow, ? rolls); distribution-checked elsewhere, and rolls that
  combat disturbs (shuffleRng, potionRng after a fight) are never counted
  as seed-exact misses.
- Fidelity is measured all the time: log replay over every recorded run,
  with a support check (the logged outcome must be one the simulator lists
  with probability above 0), and a shadow simulator beside each live run
  that logs the first mismatch.

**The split is where the interpreter lives.** A puts it in Rust next to
the combat registry: one loader for all content, Rust planners can call
it, but every logic change costs a maturin build and a `.pyd` swap. C puts
it in Python: no build per event or rule, it fits the R2 draft (already
Python on the gauntlet's run state), and it is checkable today. Its weak
point is a second content loader, which goal 1 doesn't want. B's fatal
flaw (two judges): headless execution of the game's event classes is
untested and tangled with UI singletons, and the jar can only roll, never
list outcomes; its probe idea survives as a check. D's statistics against
thin logs can't catch the small rule errors decisions exploit; its
log-statistics step and its "exact only where a decision changes" rule
survive.

**Synthesis (recommended): the game's rules in Rust, the decisions in
Python, as in combat.** A first draft put the interpreter in Python and
moved it to Rust later; the owner pointed out it will end in Rust either
way, and the reasons for Python first don't hold up:

- *Build cost per change* (the cost judge's main point): work is checked
  with debug `cargo test`, and the release build and `.pyd` swap happen
  once per landing (AGENTS.md); packs load at runtime through
  `registry::load_pack`, so a new event or table row needs no rebuild at
  all. Only a new atom does, as in combat.
- *Fit with the R2 draft*: the draft is unbuilt, and design A already
  showed R2's relics resting on a Rust run state.
- *Checkable today*: the first probe (the game's `Random` and the map
  against the 90 logged maps) is a `cargo test` over a fixture just as
  easily.

Python first would write the interpreter twice, run a second parity
migration, and keep two content loaders in between. So:

- Rust (`engine/src/run/`): the run state, the chance sources (game RNG,
  sampling, exact enumeration extending `rng.rs`'s `enumerate()`,
  observed), the map generator, rewards, and the interpreter of the run
  vocabulary, parsed in the registry (the `run` key on pack entries, atoms
  in `registry::element_names()`, words in `content/wording.json`), behind
  an `sts.Run` binding like `sts.Combat`. Rust planners can call it.
- Python: the choosers and run policies (where fast iteration pays, and
  where the sim chooser already lives), the bridge adapter that turns a
  CommunicationMod view into run state (as `Combat.from_view` does for
  fights), experiment drivers (`gauntlet.run()` over `sts.Run`) and
  reports.
- Fights are a slot: two turns deep, one turn deep, or the value net's
  estimate at the fight's start, so run-layer learning isn't held to
  two-turn fight speed; headline reads stay two turns deep.
- Choosers read an option's effect rows, not the game's words: a custom
  event they have never seen is priced from what it does, and the Golden
  Idol class of loss (run 52, word matching) goes away.

Build order, each step landing something a program checks:

1. Probes, no CPU, one session: the game's `Random` in Rust checked
   against the jar through `jjs`, then the Rust map generator against all
   90 logged Act 1 maps (a fixture extracted from `states.jsonl`; seed-exact
   or not); and the log statistics (rarities by room, gold per reward,
   potion drops, ? outcomes, event counts) next to the jar's tables.
2. Settle the `run` key with the R2 session; vocabulary in the registry;
   the interpreter core with its chance sources; today's gauntlet as a
   fixed-line act file whose reads replay byte-identical (the first gate).
3. R2's relics, gold and max HP built on that core instead of a run state
   of its own.
4. The bridge on the shared interface (the game's outcomes as the chance
   source), its rules as a chooser, a shadow simulator beside each live
   run, and a rules bump that opens and logs shop screens.
5. Act 1 proper: map, ? rooms, encounter lists, rewards, rest, chest,
   boss relic, with log replay and the support check.
6. Events, Neow and shops as data, one row and one test per jar class.
7. Then, in the owner's order (backlog 83), the run decision maker on
   simulated runs.

Estimated size: ~3k lines of Rust, ~1k of Python (bindings use, bridge
adapter, choosers), ~2-3k lines of JSON data and ~1.5k lines of tests for
Act 1 (designers' estimates, A and C).
sts_lightspeed's out-of-combat C++ is ~150 KB.

## Checks borrowed from the literature

- **Parity corpus (A):** recorded real-game steps replayed with zero field
  diffs, and a test that fails on any diff (sts2-lightspeed's script exits
  0 on diffs: the known failure case).
- **Own-engine numbers overstate:** Spire Mentor reports 14.0% at A10 in its
  own engine and won 8.8% on the same 2,000 games in the game's engine.
  Report each headline gain beside the real-game record when one exists,
  and expect the real number lower.
- **Stage death table** (sts-ironclad-agent): death rate among runs that
  reach each stage (Act 1 path, Act 1 boss, ...), as the standard loss
  breakdown for real-game runs.
- **Win-rate intervals** (bottled_ai): about 1,000 runs for ± 3 points;
  at 33 runs ± 9. Size real-game batches to the effect they must show.
- **Distillation cost** (sts-ironclad-agent, for C): student vs teacher on
  paired seeds, -4.6 points (CI -8.2 to -1.0); agreement by decision type
  (92-94% map, card, rest; 72-75% shop and multi-card select).
- **Pruning bar** (GNU Backgammon's pruning nets): a speed-only pruning
  passes when fewer than 1% of decisions change.

## Not applicable, and why

- **MCTS on the real RNG** (stock sts_lightspeed, sts-ironclad-agent,
  CombatSolver): plays with foresight.
- **Random-rollout MCTS in place of expectimax** (silverbot, Spire Mentor):
  our rollout leaf lost; Doron found MCTS level with BFS at a matched budget.
- **Root move filter** (GNU Backgammon): tried here, ~3% of nodes saved.
- **Dominance pruning** (Doron, 90-94% of states removed): his gain came
  from counting states before merging duplicates, which we never did; his
  cross-draw subtree dominance never fired; and "more HP is never worse"
  fails on custom content.
- **Human pick imitation and human-data value models:** lost to simulation
  in every test found (above).
- **Per-card priority lists** (spirecomm, bottled_ai): by card name, so
  useless on generated content.
- **LLM agents and card-text embeddings** (Cardsformer, DraftFM): a language
  model in the loop or at import; our effect primitives are exact.
- **Wall-clock search budgets** (Doron): made his results irreproducible;
  we use node caps.
- **A bigger boss node cap:** the cap binds on 0-3% of boss searches.
- **AlphaZero per fight** (AlphaStS trains a net per fight description):
  no transfer; our bursts already adapt per mechanic with replay.
- **Zero-search policy nets** (sts2ai, 6.6M parameters, A10 level with
  Spire Mentor's search): trained on two GPU servers with several hundred
  simulator processes, which the dev machine doesn't have, and search is where
  our gains come from (`measurement/search-time-gains`).
