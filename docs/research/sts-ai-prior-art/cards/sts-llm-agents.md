# LLM-based Slay the Spire agents and benchmarks: cards

Scout angle: LLM agents and benchmarks for StS, hobby bots, failure analyses.
Language models are yardsticks only; none of these cards is a design for our loop.

### SpireClimb: Slay the Spire 1 and 2 at maximum difficulty (2026)
- **Link:** https://epoch.ai/publications/ai-systems-are-improving-rapidly-at-slay-the-spire-and-its-sequel and https://epoch.ai/benchmarks/spireclimb · **Venue:** Epoch AI (benchmark page and launch analysis; launch dated October 14, 2026 per search snippet, not on the page) · **Cited by:** n/a · **Read:** full text (both web pages)
- **Problem:** Can LLM agents beat StS1 (all Acts, Ascension 20 with The Heart at max, and Ascension 0 base) and StS2 (Ascension 10) through the game's graphical interface?
- **Method:** Single-agent visual computer-use harness "based on Inspect ReAct", screenshots at 1280x720 (StS1), mouse and keyboard actions, action queue up to eight, web search restricted to the StS wiki, notes that persist across context compaction (triggered at 300,000 tokens), max reasoning setting. "15 independent single-shot attempts" per character on fixed seeds, all content unlocked.
- **Assumes:** Visual input only, no game API or mod; StS1 Ironclad, Silent, Defect, Watcher; StS2 frozen at v0.107.1; win rate is the metric; the final score averages the two games with equal weight.
- **Claims:** StS1 Ascension 0 win rates (publication table): GPT-6 Astra 98%, GPT-6.1 Sol 97%, Claude Opus 5.5 93%, GPT-6 Sol 92%, Claude Sonnet 5.5 83%, Claude Fable 5.1 65%, GPT-6 Luna 25%; top human line 100%. StS1 Ascension 20 Heart: GPT-6.1 Sol 20%, GPT-6 Astra 17%, GPT-6 Sol 2%, all Claude models and GPT-6 Luna 0%; top human line 85%. Per character, GPT-6.1 Sol at A20 Heart: Watcher 33%, Ironclad 27%, Defect 20%, Silent 0%. The benchmark page's 2026-11-05 fix (Neow bonus bug) moved GPT-6 Astra from "16.7%" to "33.3%" and GPT-6.1 Sol from "20%" to "18.3%" at that setting. StS2 Ascension 10: GPT-6 Astra 35%, GPT-6.1 Sol 29%, GPT-6 Sol 13%, Claude Opus 5.5 7%; top human line 95%. Cost and time per run are not reported. The page gives no per-decision failure taxonomy beyond "interface mistakes still occur".
- **Evaluation:** Inspect-based harness with fixed seeds; 60 StS1 runs (4 characters x 15) and 75 StS2 runs. Samples with save-scumming are excluded (under 0.1%). Human baselines from spirebird.com and sts-stats.
- **Code:** none found (no repo or dataset linked on either page)
- **Fit:** partial. Good yardstick for StS1 Ironclad at A20 Heart with a per-character breakdown, but it measures pixel-level computer use, not a state-based decision loop, and reports no cost or failure taxonomy. Note the model names in the tables are as the page states them; an aggregator headline of "98%" for A20 is not on the Epoch page (its 98% is at Ascension 0).

### Orak: a benchmark of 12 video games, one of them Slay the Spire (2025; ICLR 2026)
- **Link:** https://arxiv.org/html/2506.03610v2 · **Venue:** arXiv; ICLR 2026 (per search result) · **Cited by:** not checked · **Read:** full text (HTML fetch truncated at Appendix C; the StS setup appendix was not read)
- **Problem:** A multi-game benchmark for LLM agents, with StS as the strategy-genre game.
- **Method:** Game state (class, deck, hand, health, relics, energy, enemy intents and statuses, current floor) goes in as text. Actions are play card, end turn, select card reward. Default agent is a "reflection-planning" agent. Scores are normalized by the maximum game score.
- **Assumes:** Text state by default; the paper tests a text-only and a text-plus-image modality. Scores are normalized, not raw floor counts.
- **Claims:** Table 3 (default agents, normalized): Human (Novice) 52.9±23.2; Gemini-2.5-pro 51.9±31.9; GPT-5 26.2±19.4; DeepSeek-R1 24.9±17.1; GPT-4o 23.6±22.1; o3-mini 15.0±0.0; Claude-3.7 15.0±0.0; Qwen2.5-72B 9.0±5.3; Llama-3.3-70B 5.0±0.0; GPT-4o-mini 3.3±2.9. Table 4 (GPT-4o, StS): zero-shot 24.7±9.2, reflection 41.3±19.6, planning 35.3±9.2, reflection-planning 36.0±25.5. Table 6 modality: Gemini-2.5-pro text 51.9±31.9 vs both 26.2±19.4; Claude-3.7 text 15.0±0.0 vs both 9.7±4.6; GPT-4o 23.6±22.1 in both. Text was equal or better for every model listed. The paper gives no error analysis for StS.
- **Evaluation:** StS within Orak's MCP-based game servers; metric is floors reached and whether the final boss is defeated, reported normalized.
- **Code:** https://github.com/krafton-ai/Orak, MIT license (per repo page). The README does not describe the StS integration, game version, or Ascension settings.
- **Fit:** partial. Useful for the "text beats image" finding and for a novice-human baseline, but the setup (game version, character, Ascension) is not stated in the main text, and results are normalized.

### Large Language Models May Not Be Human-Level Players, But They Can Be Testers (2024)
- **Link:** https://arxiv.org/html/2410.02829v1 · **Venue:** arXiv (CC BY 4.0; authors per search snippet: Chang Xiao and Brenda Yang) · **Cited by:** not checked · **Read:** full text
- **Problem:** Can LLM agents, rather than players, measure game difficulty, with StS as one of the games?
- **Method:** StS state read as text through CommunicationMod (stdin/stdout) with a Python interface. The LLM names the next card and its target; a script sends it back as if it were human input. Compared against a random agent and a rule-based expert AI (open-source spirecomm).
- **Assumes:** StS1 (version not stated), Ironclad, fixed deck; two deck strengths (average and stronger); Act 1 and Act 2 boss fights, 20 trials per agent per boss.
- **Claims:** Table 2, average remaining HP and correlation r with human win rate. Act 1: Random 12.717 (r 0.231); GPT-3.5 ZS 8.650 (0.471); GPT-3.5 CoT 19.917 (0.513); GPT-4 ZS 22.550 (0.657); GPT-4 CoT 36.733 (0.871); rule-based 32.400 (0.742). Act 2: Random 2.733 (0.287); GPT-3.5 ZS 0.267 (0.208); GPT-3.5 CoT 3.617 (0.395); GPT-4 ZS 4.250 (0.479); GPT-4 CoT 17.583 (0.710); rule-based 16.133 (0.482). With an average deck, LLMs had "a win rate of less than 5%" against bosses; a stronger deck raised the average to 65%. The rule-based expert's documented win rate is 80%. GPT-3.5 ZS is worse than random in Act 2. No cost or time reported.
- **Evaluation:** Ironclad bosses in Acts 1 and 2, 20 trials per cell; correlation with human difficulty. Wordle is the second game.
- **Code:** none for the authors' code. Dependencies: spirecomm (no license stated), a Wordle solver (no license stated).
- **Fit:** good. StS1 with CommunicationMod text state and a rule-based expert baseline, which is the closest published comparison to our rule-bot comparison. Results are from 2024 models and average-HP metrics, not win rates, and the paper's rule-based expert is spirecomm, not our engine.

### Rule Synergy Analysis using LLMs: State of the Art and Implications (2025)
- **Link:** https://arxiv.org/html/2508.19484v1 · **Venue:** arXiv (cs.CL, 27 Aug 2025) · **Cited by:** not checked · **Read:** full text
- **Problem:** Can an LLM read card descriptions alone and classify pairwise synergy, without any implementation?
- **Method:** Static classification of every card pair as +1 (positive), -1 (negative) or 0 (none), using only card text. Metric is macro-averaged F1; includes a fine-tuned GPT-4o-mini.
- **Assumes:** Card text only, no playable implementation; one 75-card set (Ironclad-like cards per the examples, not stated); 5,625 pairs.
- **Claims:** Table II (avg F1 / accuracy / invalid response): GPT-4o-mini 0.47 / 0.68 / 0%; GPT-4o-mini fine-tuned 0.51 / 0.79 / 0%; GPT-4o 0.56 / 0.81 / 0%; Gemini 1.0 Pro 0.33 / 0.42 / 2.2%; Gemini 1.5 Flash 0.51 / 0.76 / 15.0%. Class counts: positive 947 (16.8%), none 4,553 (81%), negative 125 (2.2%). Negative-synergy F1 "remained consistently low, with values of 0.17 or below across all models tested."
- **Evaluation:** 75 cards x 75 pairs, labelled dataset.
- **Code:** https://github.com/iambb5445/Language-based-Synergy-Detection (dataset, fine-tuning examples, source); license not stated.
- **Fit:** partial. Directly on "how LLMs read unseen card text" (the static read is a card-to-card relation, not a play decision), and the negative-synergy failure is a concrete warning about text-only reading. Labels are class-imbalanced and not derived from play.

### AgenticSTS: a bounded-memory testbed for long-horizon LLM agents (2026)
- **Link:** https://arxiv.org/html/2607.02255 (PDF: https://arxiv.org/pdf/2607.02255) · **Venue:** arXiv · **Cited by:** not checked · **Read:** full text (first 100,000 of 122,410 characters)
- **Problem:** Does bounded memory with typed prompt layers and triggered skills let an LLM agent get further in StS2?
- **Method:** Each decision gets a freshly composed prompt from five typed layers: protocol, state schemas and action formats, game rules, episodic summaries, and triggered strategic skills (with a four-level write gate). No raw cross-decision transcript. Four model tiers (fast, strategic, analysis, evolution). Combat keeps at most three messages per round.
- **Assumes:** Slay the Spire 2 (v0.103.1 headline, v0.103.3 for competitors); one character (Silent) in the headline; a text state interface via a mod-like API (not stated in detail); a fixed A0 setting.
- **Claims:** Fixed A0, N=10 per cell: no scaffold 3/10 wins (mean score 70.4); prompt only 4/10 (69.6); hand skills 6/10 (85.5); template skills 6/10 (83.3); skills plus episodes 6/10 (82.1). Fisher exact p≈0.37 for 3/10 vs 6/10, which the paper calls directional. Median run about 80 min wall-clock (IQR 37–109) with 67 strategic LLM calls (IQR 27–105); competitors at 9.9 and 8.5 minutes per floor versus 2.3 for the authors' agent. Competitors STS2MCP 0/5 (mean floor 17.6), CharTyr 0/5 (mean floor 5.6). Qwen 0/5 and DeepSeek 0/5 cross-backbone (N=5). Failure notes: invalid_action interface errors compound into early deaths; a 43-damage hit and a 36-damage Maelstrom in boss fights.
- **Evaluation:** StS2 A0, 50-game balanced subset; archive of 298 trajectories.
- **Code:** https://github.com/AlayaLab/AgenticSTS. License per directory on the repo page: Apache-2.0 for `AgenticSTS/`, AGPL-3.0 for `AgenticSTS-Mod/`, CC-BY-4.0 for `AgenticSTS-Data/`. Data at https://huggingface.co/datasets/ShandaAI/AgenticSTS-trajectories.
- **Fit:** partial. Strong on cost and time per decision and on memory and skill ablations, but on StS2 and with no simulator-as-tool. Useful for the question of whether a skills layer helps a learned or rule agent.

### SAG-Agent: long-horizon reasoning in strategy games via dynamic knowledge graphs (2025)
- **Link:** https://arxiv.org/html/2510.15259 (PDF: https://arxiv.org/pdf/2510.15259) · **Venue:** arXiv · **Cited by:** not checked · **Read:** full text
- **Problem:** Long-horizon play in StS and another strategy game from screenshots, with procedural memory.
- **Method:** Pixel-level perception: CLIP ViT-B/32 features, SAM segmentation, template matching for clicks, GPT-4o for reasoning. Procedural memory has four tables (Objects, Skill, Action Clusters, MCTS). A state-action graph merges states at cosine similarity 0.95 and forms similarity edges at 0.88. Skill selection samples the graph first, then a VLM-guided UCT/MCTS selector.
- **Assumes:** Screen input only; StS at Ascension 0, Ironclad; game version not stated; episodes end on character death or at 500 steps.
- **Claims:** Three episodes, mean ± SD. SAG-Agent: floor 15.67±0.47, score 104.00±5.89, cost 2.15±0.04. BottomUp: floor 14.33±1.15, score 91.33±9.61. GPT-4o (zero-prior): floor 1.00, score 5.00. Cost is stated as "average tokens per 100 steps converted to USD" with no units in the table. A hyperparameter setting (0.99, 0.90) reached floor 12 and score 70 at 392.55 s per step versus 158.34 s for the default.
- **Evaluation:** StS A0 Ironclad, three episodes per method, plus one other strategy game.
- **Code:** none found in the paper. The arXiv license applies to the paper only.
- **Fit:** poor for the constraints. Pixel perception and GPT-4o in the loop; the graph and skill-memory ideas do not map to a state-based engine. Kept as a prior-art reference for "memory of which skills work".

### Claude Plays Slay the Spire 2, and What It Says About AI in Science (2026 blog)
- **Link:** https://ndwang.github.io/blog/2026/claude-plays-slay-the-spire · **Venue:** personal blog · **Cited by:** n/a · **Read:** full text
- **Problem:** What does a Claude-driven StS2 agent get wrong, and how does it read unseen card text and mechanics?
- **Method:** A custom mod serializes full game state to JSON at each decision point; Claude gets a rules system prompt and returns actions by tool use (not computer use). Persistent and per-run knowledge bases.
- **Assumes:** StS2 (released March 2026 per post); Necrobinder (Sonnet 4.6 and Opus 4.6) and Ironclad (Opus 4.6).
- **Claims:** Necrobinder: four games, never beat the Act 1 boss. Ironclad (Opus 4.6): cleared Act 1, reached deep into Act 2, died to the Act 2 sandworm "in four turns." Cost: "$100 on Claude API credits." No per-decision cost or time; no human or bot comparison.
- **Evaluation:** Single author's runs; no benchmark.
- **Failure analyses:** Did not understand that summon sets Osty's HP as defence and offence; split of damage between Osty and player unclear; doom timing (enemies attack before doom triggers) inconsistent. Boss: declined Frantic Escape (which increases the sandpit timer) and ended turns instead; tested the zero-timer state and died. Card picks: refused to add cards in Act 1 by applying a "lean deck" heuristic that fits poorly early. Reward loop: reopened the same card reward repeatedly. Sequencing: correctly stacked Vulnerable, a strength potion, and a double-attack card.
- **Code:** mod https://github.com/ndwang/sts2-ai-mod; agent https://github.com/ndwang/ClaudePlaysSTS2. Licenses not checked.
- **Fit:** partial. Good concrete list of what an LLM misreads (summons, doom, lean-deck heuristic in Act 1). StS2 and a single author, so no statistics.

### Opus 4.6 builds a playable Slay the Spire CLI (METR note, 2026-03-03)
- **Link:** https://metr.org/notes/2026-03-03-balatro-sts-cli/ · **Venue:** METR research note · **Cited by:** n/a · **Read:** full text
- **Problem:** Can an agent build a playable CLI version of Slay the Spire and Balatro? (A capability probe, not a play benchmark.)
- **Method:** Opus 4.6 writes the CLI game under a ReAct-style loop, 60 million token budget, 64k context, max reasoning, internet access, Inspect summary compaction at 75%.
- **Assumes:** StS (version not stated); starting character only (one of four); no Ascension levels; no unlocks.
- **Claims:** One StS run plus two playthroughs by the author; the author reached and defeated the final boss "using some cheats". Token totals: 25,999,380 tokens (173,485 input; 25,357,081 cache read; 277,138 cache write; 191,676 output), about $20. Wall-clock not reported. A later update (2026-07-27) says a deeper review found "moderate problems" and deliverables "look worse and worse upon deeper examination".
- **Failure analysis (of the built game, not play):** Headbutt and Flame Barrier effects wrong; damage numbers not updated for buffs and debuffs; Slimes split at the wrong time; Time Eater does not eat time; shop lets a card be removed twice and shows 6 cards instead of 7; floor numbering starts at 0; missing potions and events; Neow bonuses wrong.
- **Evaluation:** Not a benchmark; a fidelity check on a model-built simulator.
- **Code:** none; links to a METR inspect-agents scaffold repo.
- **Fit:** partial. Relevant to our rule-verification question: an LLM-written simulator had many rule errors, which is a reason to keep the engine checked against the real game. Not a play result.

### Engineer's Slay the Spire bot driven by Claude Haiku (news write-up, 2024)
- **Link:** https://gigazine.net/gsc_news/en/20240506-slay-the-spire-llm-bot (links to the original write-up on community.aws) · **Venue:** GIGAZINE news article (English) · **Cited by:** n/a · **Read:** full text (news article; the original write-up was not opened)
- **Problem:** How far does a quick hobby build get, and where does an LLM bot break?
- **Method:** Game state data passed to Claude Haiku (via Amazon Bedrock) to choose the next action; the state-extraction code was generated by Amazon Q. Planned move to Claude Opus for long-term strategy. The interface (CommunicationMod or a direct API) is not described.
- **Assumes:** Game version and character not named; "over 200 cards" and "over 50 enemies and events" per the article.
- **Claims:** Bot "reached the second of the three bosses." Floors, wins and Ascension not reported. Working "within three hours" of starting the project. Cost not reported.
- **Evaluation:** Anecdotal single run; no benchmark.
- **Failure modes:** Ran autonomously for a while then crashed; a bug let a card select an invalid target (handled by an exception path); system prompt design unsatisfying; the author noted Amazon Q may suit understanding and debugging better than play.
- **Code:** none given.
- **Fit:** poor. No quantitative result and no interface detail; useful only as a sense of how far a quick hobby build gets (second boss, Haiku).

### MiniSTS: a simplified Python Slay the Spire battle testbed (repo, GPL-3.0)
- **Link:** https://github.com/iambb5445/MiniSTS · **Venue:** GitHub repo (by Bateni and co-authors, linked from their 2024 and 2025 papers) · **Cited by:** n/a · **Read:** abstract (repo landing page; no full text)
- **Problem:** A headless testbed for combat rules, cards, and game-playing agents, including LLMs.
- **Method:** Python battle loop: energy, draw, play, end turn, enemy intents; block, status effects, exhaust, ethereal, innate, X-cost, status cards (Wound, Dazed, Burn). Cards are composed from actions, targets, and status effects, with a `CardRepo` factory. Agents include a `ChatGPTBot` (OpenAI API, chain-of-thought option), human input, random, and backtracking bots. No map or progression.
- **Assumes:** Single battle; Python; headless; requires your own OpenAI token in `auth.py`.
- **Claims:** None reported on the repo page.
- **Evaluation:** `evaluation/evaluate_bot.py` runs batch comparisons of bots across scenarios.
- **Code:** https://github.com/iambb5445/MiniSTS, GPL-3.0 (license name only on the page; full text not read).
- **Fit:** partial. A small, rule-complete combat testbed in Python with a card-composition DSL close to our effect primitives, but it is not Act 1 Ironclad and has no run layer. GPL-3.0 would constrain reuse of code.

### Learned card-pick model vs human picks (hobby write-up, Silent A20)
- **Link:** https://dev.to/doronsinger/part-3-good-models-finish-last-2n6a · **Venue:** DEV Community blog (part 3; year not shown on page) · **Cited by:** n/a · **Read:** full text
- **Problem:** Can a learned model pick cards better than a hand-made tier list, and does learning from human picks help?
- **Method:** No LLM in the loop; a logistic-regression tier list (114 parameters over 113 cards) against a pick-prediction network (state encoder 308 features to 128; card encoder 25 features to 32; about 202,000 parameters) trained on human picks with opportunity cost.
- **Assumes:** StS1 Silent, Ascension 20, spirecomm interface; training data from a 77-million-run database (358,870 card-pick decisions from 34,210 Silent runs, A20 win rate 1.5%).
- **Claims:** Offline accuracy and in-game results, same 50 seeds: card ID embeddings 55.8% offline, 12 wins / 23 losses / 15 ties vs expert, 4th in game; mechanical features only 53.5%, 16/16/18, 1st; embeddings with propensity weighting 52.3%, 15/22/13, 3rd; propensity weighting 49.5%, 14/21/15, 2nd. Better prediction of human picks led to worse in-game performance; the author attributes this to systematic biases in human picks. Per-decision cost or time not reported.
- **Evaluation:** 50 seeds, expert baseline is the bottled-AI tier list (no numbers given).
- **Code:** none in the article.
- **Fit:** partial. Not an LLM result, but it is a concrete card-pick failure analysis (human-pick bias, rare-card correlation, win labels confounded by play quality) that matches our card-pick problem.

## Not carded (opened, out of angle or overlapping)

- **Automaton Media article (Japanese, 2026-10-14)** on a study of 20 LLMs at Ascension 20 with 10 seeds, 10 runs per model. It is coverage of SpireBench (arXiv 2610.12596), which we have already read; the press piece was opened, not the paper, so SpireBench is not carded here. Its numbers, for a cross-check against SpireBench Section 4 (secondary, unverified): Act 1 pass 90% for GPT-6 Astra, Claude Fable 5.1, Claude Opus 5; Act 2 pass 50% (Astra, Fable 5.1), 40% (Opus 5); Act 3 pass 20% (Fable 5.1), 10% (Astra, GPT-5.6 Sol); final boss kill 10% (GPT-5.6 Sol), others 0%. Human comparison (Mega Crit data, about 206,000 runs): Act 1 47%, Act 2 15%, Act 3 7%, final boss 4%. Elite fights per Act 1 boss run: 1.96 (all humans), 2.6 (veterans), 1.25 (LLMs). Rest sites: 68% of LLM choices were rest vs 23% (all humans) and 9% (veterans). Card-reward skip after combat: 8% (LLM) vs 23% (human).
- **Language-Driven Play (Bateni and Whitehead, FDG 2024, ACM)**: the ACM page returned HTTP 403 to WebFetch; not read. Title and venue from a bibliography entry and a Crossref record.
- **ceur-ws Vol-3926 paper7 (PDF)**: the fetch returned unreadable binary; not read. Its link annotations point to the MiniSTS repo and to Bateni; the paper's title is unknown.
- **Orak GitHub** is merged into the Orak card above.
- **Not run in this pass:** OpenAlex and Semantic Scholar keyword and citation-graph searches (Semantic Scholar is rate-limited per the sources note). This pass relied on web search and the cited pages.
