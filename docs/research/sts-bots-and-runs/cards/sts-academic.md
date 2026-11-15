# Slay the Spire academic papers (scout cards)

Angle: academic papers and theses on Slay the Spire and roguelike deckbuilders.
Opened 10 papers: 7 with full text, 3 from abstract only (ACM and IEEE pages were closed or paywalled). That is 2 over the target of 8, because three abstract-only reads were cheap and the failed fetches left gaps.

Not cards (checked and dropped):
- Learning Game-Playing Agents with Generative Code Optimization (arXiv 2508.19506): Atari only, Slay the Spire mentioned in related work.
- Edinburgh UG4 thesis "Exploring Different Deck Building Algorithms in Slay the Spire" (project-archive.inf.ed.ac.uk/ug4/20233951/ug4_proj.pdf): WebFetch failed (PDF over the 10 MB limit). Not opened. It may hold the MCTS-in-battle and card-reward work the search hinted at.
- diva-portal thesis on ML for map paths (diva2:1565751, FULLTEXT02.pdf): WebFetch returned binary PDF and the Read tool needs poppler, which is not installed. Not opened. It is the closest academic item on pathing; its university is not read.
- Carleton honours project on direct policy search for StS combat: no page found; the carleton.ca link returned 404.
- Springer LNCS "Exploring the Impact of Randomness in Roguelike Deck-Building Games" (10.1007/978-3-031-46775-2_9, Nam and Rerkjirattikal, Thammasat): redirects to a login page. OpenAlex has no abstract. Metadata only.

### SpireBench: Evaluating Long-Horizon Strategic Play of Agentic Models with Slay the Spire (2026)
- **Link:** https://arxiv.org/html/2610.12596 (abs: https://arxiv.org/abs/2610.12596) · **Venue:** arXiv preprint (no peer-review venue stated; Lowe and Keemink) · **Cited by:** 0 (OpenAlex) · **Read:** full text
- **Problem:** Measuring long-horizon strategic play of LLM agents in full Slay the Spire, where whether a run survives depends on it. Existing agent benchmarks are short.
- **Method:** LLM agents act through tool calls in the unmodified game via CommunicationModPlus. One conversation per floor, cached system prompt with rules and a cross-run memory bank. Route planning per act and forecasts of act survival.
- **Assumes:** Ironclad, Ascension 20, 10 fresh held-out seeds. The game is the commercial build; the version is not stated in what I read. Scoring is mean acts cleared (0 to 4).
- **Claims:** Baselines: pick-first 0.00, pick-random 0.00, BottledAI 0.20. Human telemetry (Mega Crit, 206,082 runs): all players 0.73, 1000+ hour players 0.92, runs after an earlier Heart kill 1.24. Streamers 2.52 to 3.06. Top LLMs: 1.60 (Claude Fable 5.1 max), 1.50 (GPT-6 Astra max), 1.30 (Claude Opus 5 max), 1.10 (GPT-5.6 Sol max). Top three win about 90% of Act 1 runs (streamers 85 to 92%), 40 to 50% of Act 2 runs (streamers 65 to 78%). Mean acts cleared correlates with the Artificial Analysis Intelligence Index, Pearson r = 0.82, Spearman 0.89 (30 model-effort points). Top four models hold a median 90% of max HP at the Act 1 boss; streamers 53%.
- **Evaluation:** The SpireBench harness (tool-call agent, 10 seeds, Ironclad A20). Reproducing it would need the game and CommunicationMod.
- **Code:** none found. The paper names a fork, CommunicationModPlus, with no link or license.
- **Fit:** good for (a), an outside yardstick with human and streamer numbers at Act 1 win rate and acts cleared. Poor for (b): it is an LLM harness, not a search or value-net design, and it gives no run-level choice ablation of our kind.

### Analysis of Uncertainty in Procedural Maps in Slay the Spire (2025)
- **Link:** https://arxiv.org/html/2504.03918 (arXiv 2504.03918; FDG 2025, Graz) · **Venue:** FDG '25 · **Cited by:** 0 (OpenAlex) · **Read:** full text
- **Problem:** Do winning runs take more uncertain map paths, and do higher-skill players choose more uncertain paths?
- **Method:** Path entropy H = −Σ p log p over location encounter probabilities by act. Each run's played path is normalized between the min and max of all paths on its map, then divided by path length. Welch's t-test, alpha 0.05.
- **Assumes:** Public log release of 77 million runs (2020), filtered to ascension, Ironclad, 20,000 random runs. Encounter probabilities from the Slay the Spire Fandom Wiki. Game version not stated. Log base for entropy not stated (values match base 2). Maps regenerated with a third-party oracle; mismatched runs dropped (count not reported).
- **Claims:** Victory vs defeat, normalized entropy: all acts t = −64.63, p < 0.001; Act 1 t = −1.14, p = 0.25 (not significant); Act 2 t = −39.70; Act 3 t = −87.78 (both p < 0.001). Lower (ascension ≤10) vs higher (>10): Act 2 t = 11.36, Act 3 t = 13.89 (p < 0.001), Act 1 t = 1.93, p = 0.053. Entropy values per encounter: Act 1 first three monsters 2; Act 1 later monsters 3.265; elites 1.58 then 1; boss 1.58; shop 0; rest 0.
- **Evaluation:** Historical run logs. Reproducing needs the public logs and the map oracle (github.com/Ru5ty0ne/sts_map_oracle, third party).
- **Code:** none from the authors. Third-party map oracle linked only.
- **Fit:** good for (b), pathing. It gives a risk-by-act statistic from real play and says Act 1 path entropy does not separate runs. It has no agent or design method.

### AgenticSTS: A Bounded-Memory Testbed for Long-Horizon LLM Agents (2026)
- **Link:** https://arxiv.org/html/2607.02255 (abs: https://arxiv.org/abs/2607.02255) · **Venue:** arXiv (Cheng et al., Alaya Lab) · **Cited by:** 0 (OpenAlex) · **Read:** full text
- **Problem:** Can LLM agent memory be a bounded, typed interface, and does it help in Slay the Spire 2?
- **Method:** Five typed memory layers (protocol, schemas, game knowledge, episodic summaries, triggered skills). Per decision the agent sees typed slots; a per-run Strategic Thread summarizes deck choices. Median run has 67 strategic LLM calls.
- **Assumes:** Slay the Spire 2, Silent only, ascension ladder A0 to A10. Score 100 for a win, otherwise floor + (52/3)·bosses.
- **Claims:** Fixed A0, 10 games per cell: no scaffold 3/10 wins (mean score 70.4); hand skills 6/10 (85.5); full stack 6/10 (82.1). Fisher exact p ≈ 0.37, the authors call it directional. Pooled scaffolded vs not: 18/30 vs 7/20, p ≈ 0.148. Cross-backbone (N=5 per cell): Qwen 3.6-27B 0/5 wins, mean score 14.6 to 26.9; DeepSeek V4-Pro 0/5, 41.3 to 33.8. External: Mega Crit reports a 16% player-side A0 win rate across 240M community runs (not a matched baseline).
- **Evaluation:** The AgenticSTS harness on the StS2 testbed. Trajectories are on Hugging Face (ShandaAI/AgenticSTS-trajectories, 298 trajectories).
- **Code:** https://github.com/AlayaLab/AgenticSTS, no license stated in the paper. Trajectories: no license stated.
- **Fit:** partial for (a). Its yardstick is StS2, not StS1, so the numbers do not transfer directly. Poor for (b): LLM memory, not value nets or search.

### Orak: A Foundational Benchmark for Training and Evaluating LLM Agents on Diverse Video Games (2025, v3 April 2026)
- **Link:** https://arxiv.org/html/2506.03610 (arXiv 2506.03610; Park, Kim, Choi et al., Krafton) · **Venue:** arXiv (CC BY 4.0) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** A multi-game benchmark for LLM agents, with Slay the Spire as one game.
- **Method:** Reflection-planning agent with memory at each step. Actions: play a card, end turn, select a card reward after combat. Metric: floors reached, normalized by max game score.
- **Assumes:** Slay the Spire via BaseMod, Mod the Spire and CommunicationMod. Averages over 3 to 20 trials per game. Character choice and step limits are not in the text I read.
- **Claims:** Table 3 normalized scores (mean ± std): Gemini-2.5-pro 51.9 ± 31.9; GPT-4o 23.6 ± 22.1; GPT-5 26.2 ± 19.4; DeepSeek-R1 24.9 ± 17.1; Claude-3.7 15.0 ± 0.0; Human (novice) 52.9 ± 23.2. Most open-weight models score 0.0 (Llama-3.2-1B, 3B, Minitron 4B and 8B, Qwen-2.5-3B). Table 4: GPT-4o zero-shot 24.7 ± 9.2, reflection 41.3 ± 19.6, planning 35.3 ± 9.2, reflection-planning 36.0 ± 25.5.
- **Evaluation:** The Orak StS environment. Reproducing it needs the mods and a model API.
- **Code:** https://github.com/krafton-ai/Orak. License not stated in the visible text.
- **Fit:** partial for (a). It gives a novice-human reference (52.9 ± 23.2) on the same normalized scale. The normalization is not defined in the visible text, so check before comparing. Poor for (b).

### LLMs May Not Be Human-Level Players, But They Can Be Testers: Measuring Game Difficulty with LLM Agents (2024; ACM HCI 2025)
- **Link:** https://arxiv.org/html/2410.02829v1 (arXiv 2410.02829; Xiao and Yang, Adobe Research and Columbia) · **Venue:** arXiv v1; the journal version is Proc. ACM HCI, doi 10.1145/3748634 · **Cited by:** 2 (OpenAlex, HCI version) · **Read:** full text (arXiv v1)
- **Problem:** Can LLM agents measure game difficulty even when they play worse than humans?
- **Method:** Zero-shot (ZS) and chain-of-thought (CoT) LLM agents on boss fights; difficulty = Pearson correlation between the agent's remaining HP and the human boss win rate.
- **Assumes:** Original StS, fixed Ironclad with a "well-balanced, representative deck". Mods: BasicMod and CommunicationMod, Python interface. 20 trials per agent per boss, Acts 1 and 2 bosses. Human reference: developer data, "75 million+ runs". Boss count and per-boss n not stated.
- **Claims:** Act 1 r (avg HP vs human win rate): Random 0.231; GPT-3.5 ZS 0.471; GPT-3.5 CoT 0.513; GPT-4 ZS 0.657; GPT-4 CoT 0.871; rule-based expert AI 0.742 (all p < 0.001 except Random p = 0.075). Act 2: GPT-4 CoT 0.710; expert AI 0.482. Avg HP Act 1: GPT-4 CoT 36.733, expert AI 32.400. Under an average-strength deck, LLMs won less than 5% of boss fights; a stronger deck raised the average to 65%. The expert AI is cited at "80% win rate in defeating all bosses" from its docs.
- **Evaluation:** Boss fights, Ironclad, 20 trials per agent per boss, correlated with developer-released boss win rates.
- **Code:** none linked by the authors. Baseline: github.com/ForgottenArbiter/spirecomm (no license stated in the text).
- **Fit:** partial for (a). It gives per-act boss correlations with human data, which is a yardstick of sorts, but the game version is pre-2026 and unstated and the deck is fixed. Partial for (b): boss difficulty, not card or path choice.

### Rule Synergy Analysis using LLMs: State of the Art and Implications (2025; arXiv 2508.19484)
- **Link:** https://arxiv.org/html/2508.19484 · **Venue:** arXiv (Bateni, Pratt, Whitehead; UC Santa Cruz) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** Can LLMs predict pairwise card-rule synergy statically, without a playable build?
- **Method:** Pairwise classification of 75 StS cards: 5,625 pairs labeled +1, −1 or 0. The paper tests several LLMs on this label set.
- **Assumes:** One StS card set (75 cards). Labels' source is not stated (human, LLM or simulation). No label validation reported.
- **Claims:** Class counts: positive 947 (16.8%), none 4,553 (81%), negative 125 (2.2%). Model accuracy: GPT-4o 0.81, GPT-4o-mini 0.68, fine-tuned GPT-4o-mini 0.79, Gemini 1.5 Flash 0.76, Gemini 1.0 Pro 0.42. GPT-4o macro F1 0.56. The paper says LLMs do well on non-synergy pairs and struggle with positive and especially negative synergies.
- **Evaluation:** The 5,625-pair synergy set, scored with accuracy and macro F1.
- **Code:** https://github.com/iambb5445/Language-based-Synergy-Detection. No license stated.
- **Fit:** partial for (b), card evaluation. The label set is a possible ground truth for synergy, but its labels are unvalidated and its source is unstated. Do not treat it as a truth table without checking.

### Language-Driven Play: Large Language Models as Game-Playing Agents in Slay the Spire (2024)
- **Link:** https://doi.org/10.1145/3649921.3650013 (open-access PDF URL in OpenAlex: https://dl.acm.org/doi/pdf/10.1145/3649921.3650013?download=true) · **Venue:** FDG 2024 · **Cited by:** 11 (OpenAlex) · **Read:** abstract only (ACM PDF returned HTTP 403)
- **Problem:** Procedural generation of game rules needs an agent that can play the game and adapt when rules change, to evaluate balance and complexity.
- **Method:** LLM general game-playing agent in StS that adjusts to altered rules. Abstract only; no method detail read.
- **Assumes:** Not read.
- **Claims:** None read.
- **Evaluation:** Not read.
- **Code:** none found.
- **Fit:** partial for (a) and (b). The aim (rule-change testing with an agent) matches the idea of using the sim to test balance. Its results are unread.

### Are You Lucky or Skilled? An Analysis of Elements of Randomness in Slay the Spire (2023)
- **Link:** https://doi.org/10.1109/cog57401.2023.10333231 · **Venue:** IEEE Conference on Games (CoG) 2023 · **Cited by:** 1 (OpenAlex) · **Read:** abstract only (closed access; metadata and an OpenAlex abstract summary)
- **Problem:** How do elements of randomness separate skill levels in StS?
- **Method:** Clustering of players into three groups: winners, low-skill losers, high-skill losers (per the OpenAlex abstract summary).
- **Assumes:** Not read; the paper's data source is not confirmed.
- **Claims:** Winners kept about 1.82 times more of the risky card types than the other groups (the summary's wording). Conclusion: more skilled players embrace randomness rather than avoid it.
- **Evaluation:** Not read.
- **Code:** none found.
- **Fit:** partial for (b), run choices under randomness. It only gives the abstract, so check the 1.82 figure before using it.

### Stack-Aware Enemy AI in a Roguelike Deck-Builder (2026)
- **Link:** https://doi.org/10.1145/3807895.3807928 · **Venue:** ACM SIGGRAPH I3D 2026 · **Cited by:** 0 (OpenAlex) · **Read:** abstract only (the OpenAlex abstract summary; ACM page not fetched)
- **Problem:** Keeping enemy AI challenging as the player improves, in a roguelike deckbuilder.
- **Method:** Lookahead agent with a persistent stack combat system, in the authors' own game "Index 1391". It is compared against a probabilistic baseline, as Slay the Spire-style games use.
- **Assumes:** Not read.
- **Claims:** Abstract says stack awareness gives "more challenging gameplay". No numbers read.
- **Evaluation:** Not read.
- **Code:** none found.
- **Fit:** poor to partial. The game is not StS and the enemy AI is not a run-level or card-choice method. Listed because it is a lookahead agent in a deckbuilder.

### Evolving Evaluation Functions for Collectible Card Game AI (2021; arXiv 2105.01115)
- **Link:** https://arxiv.org/html/2105.01115 · **Venue:** arXiv preprint (Miernik and Kowalski, University of Wroclaw) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** Which genome representation and which fitness opponent work best when evolving feature-based state evaluation functions for CCGs?
- **Method:** Three representations (Linear 20-weight vector, BinaryTree, n-ary Tree) and three fitness schemes (progressive self-play, weak opponent, strong opponent). 50 generations, population 50, elitism 5, mutation 5%.
- **Assumes:** Legends of Code and Magic (LoCM), arena mode with draft and battle phases. Not Slay the Spire. Search depth not stated.
- **Claims:** Tournament win rates: weak-op Linear 42.9%, BinaryTree 33.8%, Tree 36.2%; progressive Linear 54.8%. From-Linear seeding: Linear 58.0%, Tree 60.2%. Authors: with a limited budget, the linear representation is more reliable; with a large budget, evolve linear first, then convert to a tree.
- **Evaluation:** LoCM arena tournaments against two LoCM baselines and four 2020 CoG contestants.
- **Code:** none stated.
- **Fit:** partial for the method of learning a card-state evaluation under a deckbuilding game. Wrong game (LoCM), so the numbers do not transfer. The linear-first and self-play findings are a method note, not a yardstick.

## Summary of yardsticks (for Opus to check)
- Outside win-rate yardsticks for full StS runs: SpireBench (StS1, A20, Ironclad; human and streamer acts cleared) and the LLM agent numbers above. Only SpireBench gives a full-run figure for StS1.
- Boss-level human correlation: LLMs May Not Be Human-Level Players (StS1, Ironclad, unstated version).
- Novice human reference on a normalized score: Orak (52.9 ± 23.2).
- Randomness and path-risk statistics from 77M-run logs: Analysis of Uncertainty (Act 1 path entropy not significant).
