# Existing Slay the Spire bots and agents: cards

Scout angle: existing StS bots, simulators and agents, with reported win rates, Ascension, character, run counts and how card rewards and pathing are decided.

Read levels: "full text" means the paper's full text was read. "page" means a web page or README was read through WebFetch, which returns a model-written summary, so exact numbers should be checked against the source before reuse.

Opened: 8. Full text: 1 (SpireBench). Dropped: decapitate-the-spire PyPI page (failed to load; the page returned an error message only). Not opened but seen in the index: sts-rl-agent (jialeiv), STS2FableBot, AutoClad, scumthespire, STS-AI-Master, conquer-the-spire, and others listed on slaythespire.dev/projects.

---

### sts-ironclad-agent (project page on slaythespire.dev, year not stated)
- **Link:** https://slaythespire.dev/projects/sts-ironclad-agent/ · **Code:** https://github.com/destire-mio/sts-ironclad-agent · **Venue:** community project index · **Cited by:** not checked · **Read:** page
- **Problem:** A20 Ironclad bot that wins the original game.
- **Method:** One frozen network makes every out-of-combat decision. Simulator search plays combat. A teacher policy trained in the simulator was distilled into a student that plays the real game.
- **Assumes:** Ironclad only, A20. Simulator-to-game parity is incomplete; the repo includes a checker for it. Game version not stated.
- **Claims:** "50.1% Heart win rate over 501 runs in the original game, with a 95% interval of 45.7–54.5%." Evaluation uses fresh seed blocks the agent never trained on.
- **Evaluation:** 501 runs on unseen seed blocks, A20 Ironclad, win = Heart kill.
- **Code:** github.com/destire-mio/sts-ironclad-agent, MIT, Python, listed as active.
- **Fit:** good. It is the closest result to our target setting (A20 Ironclad, original game, learned net plus simulator search). It breaks on card rewards and pathing: the page does not say how the network makes those choices.

---

### Bottled AI (GitHub README, xaved88/bottled_ai)
- **Link:** https://github.com/xaved88/bottled_ai/ · **Venue:** GitHub, MIT · **Cited by:** 80 stars, 20 forks (at read time) · **Read:** page
- **Problem:** Full-run StS bot without learning, for several characters.
- **Method:** Hand-built priority lists for card, boss-relic and upgrade picks, some with conditions. In combat it simulates the outcomes of different card orders and plays the highest-scoring sequence, weighing about 40 values.
- **Assumes:** Needs the game with Communication Mod and several Steam Workshop mods (BaseMod, StSLib, ModTheSpire, Communication Mod). Python 3.11.8 or later.
- **Claims:** "The Watcher strategy has a 52% win rate, described as its current best." No win rates by Ascension, no per-character breakdown, no run count on the README. It links to docs/winrates.md, which was not read. The index page says "20-52% winrate depending on character at A20" (from a dev.to post, secondhand; not checked).
- **Evaluation:** Live game through CommunicationMod. Run count and measurement method not stated on the page. Per the SpireBench paper (below), BottledAI cleared 0.20 acts per run at A20 Ironclad, all in Act 1.
- **Code:** github.com/xaved88/bottled_ai, MIT, 725 commits.
- **Fit:** partial. Good as a non-learned baseline and for the card-reward and pathing rules it uses. Breaks on the constraint of a headless yardstick: it needs the real game, which is not installed. Its win-rate numbers are not reproducible here.

---

### sts_lightspeed (GitHub README, gamerpuppy/sts_lightspeed)
- **Link:** https://github.com/gamerpuppy/sts_lightspeed (WebFetch on the GitHub URL; the search had only found a libhunt mirror) · **Venue:** GitHub, MIT · **Cited by:** not checked · **Read:** page
- **Problem:** Fast, RNG-accurate C++17 StS simulator, with tree search.
- **Method:** Tree search that finds the best result when the RNG state is known. A planned feature would search possible outcomes without that knowledge.
- **Assumes:** C++17, built with gcc (author used CLion and mingw64 on Windows 10). Combat can be loaded from save files; outside-combat progress listed without a completion claim. Stated coverage: all enemies, all relics, all Ironclad cards, all colorless cards.
- **Claims:** "1M random playouts in 5 seconds on 16 threads." The README gives no win rates, Ascension, run counts, or card-reward and pathing rules.
- **Evaluation:** Random playout throughput only. No agent evaluation in the README.
- **Code:** github.com/gamerpuppy/sts_lightspeed, MIT.
- **Fit:** good as the simulator base for a headless yardstick; it is also the simulator used by spire-agent (below). Partial for the win-rate question: no agent results here.

---

### Spire Agent (GitHub README, AttemorySystem/spire-agent)
- **Link:** https://github.com/AttemorySystem/spire-agent · **Venue:** GitHub, MIT · **Cited by:** not checked · **Read:** page
- **Problem:** Autonomous LLM-plus-search agent for Ironclad and Defect in the real game.
- **Method:** Deterministic checks first. Three agents own map, build and combat. Build picks search a graph of expert winning-deck templates taken from Baalorlord's published run archive; the LLM handles unresolved cases. Combat is MCTS on sts_lightspeed. Map gates use simulations of upcoming fights; an LLM ranks the remaining routes.
- **Assumes:** Python, uv, C++ sts_lightspeed built with CMake. Targets Linux and macOS; Windows untested. Real game with mods needed to play live.
- **Claims:** "Ironclad, Ascension 20 Heart: In a recent 12-run sample, the average final floor was 38.6. Six runs reached Act 3, and two reached Act 4." Multiple A20H wins for both Ironclad and Defect, with video. Defect evaluation "ongoing." Run selection and measurement not described beyond sample size.
- **Evaluation:** A20 Heart, Ironclad, 12-run sample. Replay logs feed a frozen evaluation set; changes are promoted only if the benchmark improves without regression.
- **Code:** github.com/AttemorySystem/spire-agent, MIT.
- **Fit:** good. Its card-reward and pathing design (template search plus simulation-gated routes) is a direct comparison for our run-level question. It breaks on the headless constraint for live evaluation, and the 12-run sample is too small to place against a yardstick.

---

### SpirePilot (web page, spirepilot.com)
- **Link:** https://www.spirepilot.com/ · **Venue:** project page (Steam Workshop mod link) · **Cited by:** n/a · **Read:** page
- **Problem:** Advertises move-by-move review of uploaded A20 Ironclad Heart fights.
- **Method:** Not described on the page. The page is a promotional page for "Heart Reviews · Ironclad A20".
- **Assumes:** Players install the mod and opt in to upload fights. The page does not say whether it targets the original game or Slay the Spire 2.
- **Claims:** No win rates on the page. Leaderboard shows "Loading…" with a minimum-runs filter.
- **Evaluation:** None on the page.
- **Code:** none found; the only link is the Steam Workshop mod page (id 3811056891).
- **Fit:** poor. No agent method, no numbers, no code. Kept only as a pointer to a community data source for human-played A20 Ironclad Heart fights.

---

### SpireBench: Evaluating Long-Horizon Strategic Play of Agentic Models with Slay the Spire (2026, arXiv 2610.12596)
- **Link:** https://arxiv.org/html/2610.12596v1 · **Venue:** arXiv preprint · **Cited by:** not checked · **Read:** full text (first 100,000 of 278,518 characters; the appendix on card rewards was not reached)
- **Problem:** Benchmark for LLM agents on long-horizon play in the original StS1 (not StS2).
- **Method:** Harness is a fork of CommunicationMod. Each model plays through tool calls. Each act it plans a route; after each floor it writes notes. Cross-run memory banks were tested.
- **Assumes:** Ironclad at Ascension 20, live game through the fork. Models run at their highest reasoning setting. Reskinning the game's names was tested.
- **Claims:** "Claude Fable 5.1 (max): 1.60 mean acts cleared; act win rates 90%, 50%, 20%, 0%." "GPT-6 Astra (max): 1.50; 90%, 50%, 10%, 0%." "Claude Opus 5 (max): 1.30; 90%, 40%, 0%, 0%." "GPT-5.6 Sol (max): 1.10; 70%, 20%, 10%, 10%. Sol is the only model that killed the Heart, once." Baselines: first or random option cleared 0 acts. "BottledAI, a symbolic agent, cleared 0.20 acts, all of them Act 1." Human average from Mega Crit telemetry (206,082 runs) is 0.73 acts; top streamers about 2.5–3.1 acts.
- **Evaluation:** Each cohort (one model, one configuration) plays 10 held-out seeds. 20 LLMs. Scored by acts cleared (0–4), act win rates and final floor. Note: the Epoch article below says 15 attempts per model per character; the two sources disagree on the count and need checking against the paper's own tables.
- **Code:** none linked in the text read. It links to CommunicationMod and Bottled AI repositories.
- **Fit:** partial. Best source here for a yardstick in the original game at A20 with an act-level scoring system and a Bottled AI baseline. Breaks on the headless constraint: all tests are live-game LLM runs, so the numbers are not reproducible in our simulator. The card-reward result is in an appendix not read: the paper says model card picks show "little correlation with model strength."

---

### SpireClimb / Epoch AI (web article, Oct 14, 2026)
- **Link:** https://epoch.ai/publications/ai-systems-are-improving-rapidly-at-slay-the-spire-and-its-sequel · **Venue:** Epoch AI publication · **Cited by:** n/a · **Read:** page
- **Problem:** Tests frontier models on StS1 and StS2 at maximum difficulty, through the graphical interface.
- **Method:** Single-agent visual computer-use harness (Inspect ReAct). Models could take notes to persist across compaction and could consult the StS wiki.
- **Assumes:** Graphical game, not a headless simulator. StS2 pinned at v0.107.1; StS1 version not given. Four StS1 characters: Ironclad, Silent, Defect, Watcher.
- **Claims (StS1):** Ascension 0: "GPT-6 Astra 98%, GPT-6.1 Sol 97%, Claude Opus 5.5 93%, GPT-6 Sol 92%, Claude Sonnet 5.5 83%, Claude Fable 5.1 65%, GPT-6 Luna 25%." Ascension 20 Heart: "GPT-6.1 Sol 20%, GPT-6 Astra 17%, GPT-6 Sol 2%, others 0%." By character at A20 Heart, Sol: Watcher 33%, Ironclad 27%, Defect 20%, Silent 0%. Astra: Silent 7% (1 of 15). Top human players reportedly reach at least 80% at max difficulty; the chart reference line for StS1 A20 Heart is 85%.
- **Evaluation:** 15 independent single-shot attempts per model, per character, per game, on a fixed set of arbitrary seeds, 90% confidence intervals shown.
- **Code:** none. Links to the SpireClimb benchmark page and Inspect ReAct.
- **Fit:** partial. Gives a human-reference line (85% A20 Heart) and per-character Ascension 20 numbers with run counts, which is what we need for yardsticks. Breaks on the headless constraint and on decisions: it measures whole-run play through the screen, not card-reward or pathing rules.

---

### slaythespire.dev project index (web page, 42 projects)
- **Link:** https://slaythespire.dev/projects/ · **Venue:** community index of StS bots, simulators and tools · **Cited by:** n/a · **Read:** page
- **Problem:** Catalogue of StS1 and StS2 bots, simulators and tools.
- **Method:** Table of 42 projects, with name, game, and a one-line description. The index marks bot win rates as reported by each project, not independently verified.
- **Assumes:** Mixed StS1 and StS2. Index excludes game interfaces, modding foundations and research benchmarks.
- **Claims (as reported by the index, not verified):**
  - sts-ironclad-agent (StS1): "50.1% Heart win rate over 501 runs" (A20 Ironclad).
  - sts-rl-agent (StS1, jialeiv): "A0 Ironclad with a learned policy and MCTS in combat. 14% wins and floor 42.5 average on 50 held-out seeds, versus 6% and 31.2 for heuristics."
  - Bottled AI (StS1): "52% win rate with its best Watcher strategy."
  - STS2FableBot (StS2): "20.7% win rate at A0 over 343 runs and 19.4% at A1 over 175 runs."
  - AgenticSTS (StS2): "3/10 wins at A0 without learned skills, 6/10 with them."
  - sts_lightspeed (StS1): "1M random playouts in 5 seconds on 16 threads."
  - Also listed: AutoClad (imitation learning on sts_lightspeed, A20 Ironclad, early), scumthespire (combat search with saved states), STS-AI-Master (RL, headless multi-process training), conquer-the-spire (C++17 simulator for Ironclad, Silent, Defect), decapitate-the-spire (headless Python clone for RL, Silent in Exordium).
- **Evaluation:** Depends on each project; not described on the index.
- **Code:** each project links its own; not checked here.
- **Fit:** good as a map of who to check next. The sts-rl-agent entry (A0, 50 held-out seeds, 14% vs 6% for a heuristic) is the nearest comparable for a learned-net plus MCTS setup and should be opened next. Its win rates are unverified until each project's README is read.

---

## Notes for the next review

- Only one source (SpireBench) gives full text. The others are README or web-page summaries from WebFetch, so their numbers are unverified.
- Two numbers conflict: SpireBench says 10 seeds per cohort; Epoch says 15 attempts per model per character. Both are for LLM agents, not bots.
- Human reference points on the same scale: Epoch's top humans at least 80% at max difficulty (85% chart line for StS1 A20 Heart); SpireBench's average human from Mega Crit telemetry clears 0.73 acts, top streamers 2.5–3.1 acts.
- Sources that were not usable: decapitate-the-spire PyPI page (failed to load), SpirePilot (no method or numbers).
