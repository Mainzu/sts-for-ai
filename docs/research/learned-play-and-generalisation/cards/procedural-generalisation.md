# Cards: procedural generalisation in RL (scout lane: procedural-generalisation)

Problem frame for fit notes: a one-turn expectimax agent with a learned value net over card effect primitives, trained on outcomes from search + heuristic. Constraints: CPU only (16 cores), training runs of hours at most, no peeking at hidden information, generalisation to unseen cards is the goal.

Numbers marked "(ar5iv extract)" were read from the ar5iv HTML rendering through a fetch tool, not copied from the PDF; spot-check before quoting them in a test or a write-up.

---

### Quantifying Generalization in Reinforcement Learning (2019)
- **Link:** https://arxiv.org/abs/1812.02341 · **Venue:** arXiv preprint (v3, rev. 14 Jul 2019); no peer-reviewed venue on the page · **Cited by:** 328 (OpenAlex, work record) · **Read:** full text (ar5iv extract)
- **Problem:** Training and testing on the same environment instances measures memorisation, not generalisation. Needs a train/test split of procedurally generated levels.
- **Method:** CoinRun (pixel platformer). Train PPO on a fixed set of N levels, test on fresh levels. Sweeps N, architecture (Nature-CNN vs IMPALA-CNN), and regularisers (L2, dropout, batchnorm, data augmentation, stochasticity).
- **Assumes:** discrete actions; 64x64 RGB observations; PPO with 8 workers, gamma 0.999, Adam lr 5e-4; 256M steps (most curves); 3-5 seeds per point; test set size not stated.
- **Claims:** IMPALA-CNN, 256M steps, 5 seeds (ar5iv extract): at 100 levels, train 99.39±0.08 / test 66.58±1.91; at 500 levels, train 99.16±0.19 / test 80.25±1.07; at 16000 levels, train 98.04±0.17 / test 97.77±0.68; unbounded, train 98.11±0.26 / test 98.29±0.16. Nature-CNN at 500 levels: train 97.85±0.46 / test 70.54±0.62. L2 most effective at w=1e-4 (sweep 0 to 2.5e-4). Dropout most effective at p=0.1 with "smaller impact" than L2. Batchnorm gives "a significant performance boost" (no number in text). Test performance measured over 10,000 episodes per data point.
- **Evaluation:** CoinRun, levels indexed by seed. Reproduce as: train on seeds 0..N-1, report return on held-out seeds, sweep N. The unbounded set uses about 2M unique levels, with no test seed in training.
- **Code:** https://github.com/openai/coinrun (paper says environment code is there; training code not explicitly released; licence not checked) · **Fit:** partial. Gives the cleanest held-out-seed protocol and a train-test gap-versus-N curve, which is the control a learned net needs. Breaks: pixel observations and 256M-step PPO are far beyond an hours-long CPU budget, and the content is not structured like card effects.

---

### Assessing Generalization in Deep Reinforcement Learning (2018; v2 2019)
- **Link:** https://arxiv.org/abs/1810.12282 · **Venue:** arXiv preprint (v2 15 Mar 2019); a search snippet says ICLR 2019, not confirmed on the page · **Cited by:** 114 (OpenAlex) · **Read:** full text (ar5iv extract)
- **Problem:** Deep RL methods are compared on inconsistent generalisation setups; need a controlled benchmark that separates in-distribution from out-of-distribution performance.
- **Method:** Six classic simulated tasks (CartPole, MountainCar, Acrobot, Pendulum, HalfCheetah, Hopper), each with physical parameters varied. Three variants per env: D (fixed defaults), R (uniform box around defaults), E (extreme boxes at the box vertices). Train on D/R/E, test on D/R/E, giving 9 train/test cells. Metrics: Default = DD, Interpolation = RR, Extrapolation = geometric mean of DR, DE, RE.
- **Assumes:** continuous state, mostly continuous control; 15,000 training episodes; 1,000 test episodes; A2C, PPO, EPOpt-A2C/PPO, RL2 (feed-forward or recurrent); 5 runs.
- **Claims:** Table 2, averaged over envs (% success, mean±SD over 5 runs, ar5iv extract): A2C FF Default 78.14±6.07 / Interp 76.63±1.48 / Extrap 63.72±2.08; PPO FF 78.22±1.53 / 70.57±6.67 / 48.37±3.21; EPOpt-PPO FF 85.40±8.05 / 85.15±6.59 / 59.26±5.81; RL2-A2C RC 45.79±6.67 / 46.32±4.71 / 33.54±4.64. Conclusion: vanilla algorithms generalise better than EPOpt and RL2.
- **Evaluation:** The six modified envs above. Reproduce as: a parameter-box split with a fixed default and a widened test box, scored separately for interpolation and extrapolation.
- **Code:** https://github.com/sunblaze-ucb/rl-generalization (linked on the paper; licence not checked) · **Fit:** partial. The default/interpolation/extrapolation split is a template for "seen card set / nearby unseen cards / far unseen cards", and the run cost is small. Breaks: low-dimensional physics rather than discrete card effects, and it has no decision-quality control like a heuristic baseline.

---

### Leveraging Procedural Generation to Benchmark Reinforcement Learning (Procgen, 2019/2020)
- **Link:** https://arxiv.org/abs/1912.01588 · **Venue:** ICML 2020 (PMLR v119, cobbe20a, per search result); arXiv 2019, v2 Jul 2020 · **Cited by:** 196 (OpenAlex, arXiv-DOI record) · **Read:** full text (ar5iv extract)
- **Problem:** Need a benchmark that measures both sample efficiency and generalisation with controllable level distributions.
- **Method:** 16 procedurally generated games with shared 15-action discrete space and 64x64x3 observations. Generalisation runs train on a finite set of levels and test on the full level distribution. Normalised score per game: (R - R_min)/(R_max - R_min).
- **Assumes:** discrete actions; PPO; "easy" and "hard" difficulty (hard is default); 500 training levels for hard, 200 for easy (defaults); 200M steps (hard), 25M steps (easy); 3-4 seeds per figure.
- **Claims (ar5iv extract):** Larger models significantly improve sample efficiency and generalisation; the Nature-CNN almost completely fails to train. Agents need up to about 10,000 levels to close the generalisation gap (summary of the paper's scaling study; not verified verbatim). Headline metric is mean normalised return. Exact scores are only in figures.
- **Evaluation:** Procgen games CoinRun, StarPilot, CaveFlyer, Dodgeball, FruitBot, Chaser, Miner, Jumper, Leaper, Maze, BigFish, Heist, Climber, Plunder, Ninja, BossFight. Reproduce as: train on N seeds, test on held-out seeds, normalise per game.
- **Code:** https://github.com/openai/procgen (licence not checked) · **Fit:** partial. The normalisation and the N-levels protocol are reusable as reporting conventions. Breaks: costs about 24 GPU-hours per env at the default setting, and the content is pixel-based games.

---

### A Survey of Zero-shot Generalisation in Deep Reinforcement Learning (2021 arXiv; JAIR 2023)
- **Link:** https://arxiv.org/abs/2111.09794 · **Venue:** arXiv (v6 Jan 2023); JAIR vol. 76, pp. 201–264 (2023) per search result · **Cited by:** 191 (OpenAlex) · **Read:** full text, partial (ar5iv sections 3–4 only; methods section not reached)
- **Problem:** No shared formalism for zero-shot generalisation (ZSG) in deep RL, and no clear benchmark or evaluation practice.
- **Method:** Survey. Gives a unifying formalism and terminology, categorises benchmarks and methods, and critiques the field.
- **Assumes:** not applicable (survey).
- **Claims (quoted or paraphrased from the paper):** "taking a purely procedural content generation approach to benchmark design is not conducive to progress in ZSG." PCG-only benchmarks allow evaluation only across training-set sizes; they recommend combining PCG with controllable factors of variation. Held-out seeds "should be the standard evaluation protocol in RL," though this only tests weak generalisation. "A gap of zero doesn't necessarily imply good performance," since a random policy can score zero. Report the gap alongside test performance, not instead of it. Name MiniHack and NLE for non-visual generalisation; CausalWorld as the one env that tests all variation types at once.
- **Evaluation:** None (survey). Its protocol recommendations are the usable part.
- **Code:** none (survey) · **Fit:** good as a checklist for protocol design (held-out seeds, reporting the gap, stating the protocol). It does not give controls beyond a random-policy reference, and it does not cover card-like discrete content.

---

### What Does a ProcGen Generalization Gap Measure? Action Rules, Residual Entropy, and the Missing Random Floor (2026 preprint)
- **Link:** https://arxiv.org/abs/2609.32532 · **Venue:** arXiv preprint (v1 26 Sep 2026, v2 2 Oct 2026); single author; not peer-reviewed · **Cited by:** 0 (OpenAlex) · **Read:** abstract (arXiv abstract page)
- **Problem:** A generalisation gap (train return minus held-out return) is reported without a reference point, and the test-time action rule is often unstated.
- **Method:** Measure a uniform-random policy's return on the same levels under the same harness as the "random floor". Compares sampled vs argmax test-time actions. Also audits twelve ProcGen codebases.
- **Assumes:** PPO, eight ProcGen envs, 8M steps with 16 parallel envs (three extended to 25M, unnamed on the page); discrete actions.
- **Claims (as on the abstract page, with conditions):** miner's sampled policy scores "5.1x the floor on held-out levels"; miner's argmax policy "scores below it in every run". Greedy evaluation "places two environments significantly below the floor". Raw policy entropy flags six of eight envs as converged, but 32–66% of that entropy lies on actions with identical effects. Against the floor, five of eight sampled policies are clearly above it on held-out levels; heist is not distinguishable from it. Nine of twelve audited codebases sample test-time actions without an explicit choice.
- **Evaluation:** ProcGen eight-env subset, PPO, held-out levels. Reproduce as: random-policy floor on the same held-out seeds, with the action rule stated.
- **Code:** none found (page links only the PDF, HTML and TeX) · **Fit:** good for the control design (a random-policy floor and an explicit action rule). Caveats: single-author, unreviewed, and ProcGen-only.

---

### Grounding Language to Entities and Dynamics for Generalization in Reinforcement Learning (2021)
- **Link:** https://arxiv.org/abs/2101.07393 (PMLR v139 hanjie21a) · **Venue:** ICML 2021 · **Cited by:** 15 (OpenAlex, arXiv-DOI record) · **Read:** full text (ar5iv extract)
- **Problem:** Zero-shot generalisation to unseen games whose entities and dynamics are described only by free-text manuals, with no pre-given text-to-observation mapping.
- **Method:** Messenger environment with EMMA (entity mapper with multimodal attention), trained with PPO from environment rewards alone. Compared against G-ID, Mean-BOS, BAM, txt2π, and an oracle O-Map.
- **Assumes:** 10x10 grid; 12 entities, 3 roles, 3 movement types; 1,320 possible games, split 44 train / 32 validation / 32 test; step limits 4 (S1), 64 (S2), 128 (S3); PPO lr 5e-5; 3 seeds. Training used a single RTX 2080 GPU for up to 12 h (S1), 48 h (S2), 72 h (S3).
- **Claims (ar5iv extract, test games, mean±SD over 3 seeds):** S1: EMMA 85±1.4, O-Map 97±0.3, BAM 66±1.5, G-ID 18±8.2, txt2π 2.5±1.7; S2: EMMA 85±0.6, O-Map 87±1.8, BAM 41±1.7; S3: EMMA 10±0.8, O-Map 80±1.5. Random agent wins 7.8% (S1), 2.1% (S2), 1.6% (S3). Under synonym substitution on S2, EMMA won 75% vs BAM 8.5%. Evaluation games never contain a message or goal assignment seen in training.
- **Evaluation:** Messenger, with held-out combinations of entity-role-dynamics. Reproduce as: a train/val/test split over game configurations, with a random-agent floor and an oracle upper bound.
- **Code:** https://github.com/ahjwang/messenger-emma (licence not checked) · **Fit:** good on the problem shape (unseen entities defined by text, held-out combinations, oracle and random controls, robustness tests with synonyms). Breaks: relies on a learned text encoder and multi-hour GPU training, and it is grid-based, not card play.

---

### Prioritized Level Replay (2020 arXiv; v4 2021)
- **Link:** https://arxiv.org/abs/2010.03934 · **Venue:** arXiv preprint (v4 12 Jun 2021); venue not on the page · **Cited by:** 32 (OpenAlex, arXiv-DOI record) · **Read:** full text (ar5iv extract)
- **Problem:** With a finite budget of training levels, which level to sample next to get better test-time generalisation.
- **Method:** Scores each level by its estimated learning potential (TD-error based), with rank prioritisation (beta = 0.1) and a staleness term (rho = 0.1 for Procgen, 0.3 for MiniGrid). Sampling is a training-data choice, not a change to the policy network.
- **Assumes:** PPO with GAE; Procgen easy with N_train = 200 and 25M steps, hard with 500 levels and 200M steps; MiniGrid with 3,000-6,000 levels; 10 seeds (easy), 5 (hard), 3-4 (MiniGrid).
- **Claims (ar5iv extract, normalised mean test return):** Procgen easy: Uniform 100.0±4.5; TSCL Window 103.0±3.6; mixreg 113.8±2.8; UCB-DrAC 129.8±8.2; PLR 128.3±5.8; UCB-DrAC+PLR 176.4±6.1. PLR alone significant on 10 of 16 games. Procgen hard: Uniform 100.0±2.0; PLR 135.0±6.1; UCB-DrAC+PLR 182.9±8.2. MiniGrid: Uniform 100.0±2.5; PLR 124.3±4.7. The text's "28%" gain does not match the table's 36%; the table is what the paper prints.
- **Evaluation:** Procgen (16 games), MiniGrid. Test levels drawn from the full distribution, 100 test episodes per game (easy). Welch t-test at p = 0.05.
- **Code:** https://github.com/facebookresearch/level-replay (licence not checked) · **Fit:** partial. A training-sampling method that claims generalisation gains under a fixed level budget. Breaks: it needs many PPO seeds at 25M+ steps per game, and combat outcomes have no level-replay analogue without a redesign.

---

### Learning Action Representations for Reinforcement Learning (ICML 2019)
- **Link:** https://arxiv.org/abs/1902.00183 (PMLR v97 chandak19a) · **Venue:** ICML 2019 · **Cited by:** 71 (OpenAlex, arXiv-DOI record) · **Read:** full text (ar5iv extract, first ~100k of ~111k chars)
- **Problem:** Large finite discrete action sets, where the agent has to generalise across actions it has not tried.
- **Method:** Policy is split into a policy over a low-dimensional learned action space (PG-RA), plus a mapping f̂ back to actions. Representations are learned from observed (s, a, s') transitions with a supervised negative log-likelihood of the taken action, not from reward.
- **Assumes:** discrete actions up to 2^12 in the Maze domain; 1,498 tutorial items and 1,843 software tools in recommender MDPs built from click logs; the representation loss needs no rewards.
- **Claims (ar5iv extract, no numeric returns in text):** Maze: standard actor-critic degrades as the action count grows (2^4, 2^8, 2^12), while PG-RA variants stay strong. Tutorial and Software MDPs: PG-RA reaches up to 2x (tutorials) and 3x (software) the return of standard actor-critic. Maze setup: 10% action noise, episodes capped at 150 steps, reward 100 at the goal. Recommender setup: only 5% of items carry reward. The paper does not test held-out actions, so its "generalise to unseen actions" claim is untested.
- **Evaluation:** Simulated maze; two click-log recommender MDPs. Reproduce as: a discrete-action MDP with a per-action embedding and a held-out action split (the paper does not run one).
- **Code:** none found · **Fit:** partial. The representation idea (score actions through their effect features, not IDs) is directly relevant to unseen cards, but this paper gives no held-out-action evidence and no numbers in the text.

---

### Cardsformer: Grounding Language to Learn a Generalizable Policy in Hearthstone (ECAI 2023)
- **Link:** https://ebooks.iospress.nl/doi/10.3233/FAIA230581 · **Venue:** ECAI 2023, FAIA vol. 372, pp. 2720–2727 · **Cited by:** 4 (OpenAlex) · **Read:** abstract only (the PDF route returned a binary file that the tool could not read)
- **Problem:** Hearthstone card effects are written in natural language. Agents need a policy that generalises to cards not seen in training.
- **Method (abstract):** A prediction model trained offline on trajectories to predict state transitions from card descriptions, plus a policy model meant to handle unseen cards. Encoder and architecture not accessed.
- **Assumes:** Hearthstone (PyStone) with offline trajectories.
- **Claims (abstract only):** "better data efficiency and state-of-the-art results", including when the deck contains untrained cards. No numbers accessed.
- **Evaluation:** Not accessed. Abstract says PyStone is released as an open benchmark.
- **Code:** abstract says code is public; no URL on the page · **Fit:** good on the problem match (card text, unseen cards, offline transition prediction). Numbers and protocol unverified, so treat it as a lead and fetch the PDF before relying on it.

---

### Learning With Generalised Card Representations for "Magic: The Gathering" (CoG 2024)
- **Link:** https://arxiv.org/abs/2407.05879 · **Venue:** IEEE Conference on Games 2024 (per arXiv listing) · **Cited by:** 4 (OpenAlex, arXiv-DOI record) · **Read:** full text (arXiv HTML v1)
- **Problem:** Represent MTG cards so a model can handle cards it has never seen, for predicting human draft picks.
- **Method:** Compares card encodings: one-hot IDs, random vectors, autoencoded images (32 and 1024 dims), 17Lands meta statistics (16), hand-coded features (1306, including a sentence-transformer text embedding), and combinations. Trained on the NEO set (302 unique cards), tested on a held-out NEO split and averaged over unseen sets.
- **Assumes:** supervised top-1 prediction of human picks (not game outcomes). Transfer experiments: about 75M training samples and 2,990 unique cards; each dataset split 80/20; BRO held out as the "new release".
- **Claims (Table II, NEO-only training, top-1 accuracy):** NEO test: one-hot 67.80%, Features 67.76%, Features+Meta+Image1024 68.00%. Unseen sets: Random 23.79%, Image1024 31.10%, Meta 42.14%, Features 33.57%, Features+Meta 34.74%, Features+Meta+Image1024 42.87%. Table III: pre-trained model on seen-set hold-out 66.49%, BRO (unseen) 55.44%, after tuning on BRO 62.27%. Random baseline about 0.22. Abstract: "55%" of human choices on completely unseen cards.
- **Evaluation:** Supervised pick prediction on NEO and BRO (17Lands / DraftSim data). Reproduce as: train on some expansions, test on a held-out expansion, with a random baseline.
- **Code:** none found · **Fit:** partial. Shows a held-out-expansion protocol for unseen cards and that the encoding choice changes unseen-card accuracy a lot (23.79% to 42.87%). It measures prediction accuracy, not play strength, so it does not test decisions.

---

### Towards Modern Card Games with Large-Scale Action Spaces Through Action Representation (CoG 2022)
- **Link:** https://arxiv.org/abs/2206.12700 · **Venue:** IEEE CoG 2022 (per arXiv comment) · **Cited by:** 2 (OpenAlex, arXiv-DOI record) · **Read:** abstract only
- **Problem:** Axie Infinity has a huge action space that generic RL struggles with.
- **Method (abstract):** Learns action representations jointly with strategy; evaluates a fixed-size subset of feasible actions chosen via those representations.
- **Assumes:** Axie Infinity card game; large discrete action space.
- **Claims (abstract only):** better sample efficiency and the best overall win rate among three compared methods. No numbers on the page.
- **Evaluation:** Not accessed. Whether unseen cards or actions were tested is not stated on the page.
- **Code:** none found · **Fit:** partial. Card-game action reduction via representations, but it is abstract-only with no held-out or unseen-card evidence, so the match to generalisation is unverified.

---

### Generalization in Reinforcement Learning with Selective Noise Injection and Information Bottleneck (NeurIPS 2019)
- **Link:** https://arxiv.org/abs/1910.12911 · **Venue:** NeurIPS 2019 · **Cited by:** 88 (OpenAlex, arXiv-DOI record) · **Read:** full text (ar5iv extract)
- **Problem:** RL overfits to a limited set of training levels. Standard supervised regularisers (dropout, batchnorm) do not transfer cleanly to RL.
- **Method:** Selective Noise Injection (SNI) applies noise regularisers in a way that limits harm to the gradient; IBAC (a VIB-style information bottleneck) with SNI. Argues that RL differs from supervised learning because the training data depends on the model and the early regime is low-data and non-stationary.
- **Assumes:** CoinRun with 500 fixed training levels; MultiRoom with random layouts of 1-3 rooms, 30 seeds; weight decay 1e-4 (both envs); IBAC beta 1e-6 (MultiRoom), 1e-4 (CoinRun); dropout p = 0.2.
- **Claims (ar5iv extract):** "most previously proposed regularizers decreased performance relative to the baseline, with Batch Normalization worst." IBAC with SNI "significantly outperforms the new baseline"; lambda = 0.5 beats lambda = 1. MultiRoom success: IBAC-SNI 43% and 21% on two- and three-room layouts (ordering inferred, not stated); other agents under 3% on two-room, none on three-room. Exact CoinRun test numbers are only in figures.
- **Evaluation:** CoinRun (500 levels, test on new levels of highest difficulty; test count not stated); MultiRoom (random layouts, 30 seeds). Reproduce as: a fixed train set of 500 levels, held-out test levels, and a regulariser sweep.
- **Code:** https://github.com/microsoft/IBAC-SNI (linked; licence not checked) · **Fit:** partial. Useful as a caution that dropout/batchnorm can hurt when the training signal depends on the model. The paper's mechanism is RL-specific, so it applies less directly to a value net trained by supervised regression, and its evidence is pixel-based.

---

### MiniHack the Planet: A Sandbox for Open-Ended Reinforcement Learning Research (NeurIPS 2021 Datasets & Benchmarks)
- **Link:** https://arxiv.org/abs/2109.13202 · **Venue:** NeurIPS 2021 Datasets and Benchmarks · **Cited by:** 20 (OpenAlex, arXiv-DOI record) · **Read:** full text (ar5iv extract, first ~100k of ~135k chars)
- **Problem:** Need a sandbox where task variation and randomness can be controlled inside NetHack, to test generalisation.
- **Method:** Levels written in NetHack's des-file format; underspecified placements (monsters, objects) are resolved by the engine each episode. Layout commands (MAZEWALK, RANDOM_CORRIDORS), dice notation, and shuffled arrays add procedural structure.
- **Assumes:** discrete grid; 44 navigation envs and skill-acquisition envs with a 75-action space; NLE backend; IMPALA via TorchBeast; median over at least five seeds.
- **Claims (ar5iv extract, qualitative):** KeyRoom-Random-S5 is solved by all baselines; KeyRoom-Random-S15 by none. PAIRED improves zero-shot performance on MultiRoom-N2-Extreme (no figure given). The methodology section recommends training on a limited number of seeds and testing on held-out seeds, but the reported experiments train and test on the full level distribution.
- **Evaluation:** MiniHack navigation and skill tasks. Reproduce as: a des-file level with a fixed set of seeds held out for test.
- **Code:** https://github.com/facebookresearch/minihack (licence not confirmed in the fetched text) · **Fit:** partial. A controllable-randomness template for procedural content, but the paper does not run the held-out-seed split it recommends, and its training uses IMPALA on GPU-scale budgets.

---

## Seen in search, not opened (no cards)
- Dijujin et al., "Inductive Biases for Zero-shot Systematic Generalization in Language-informed RL" (arXiv 2501.15270; OpenAlex W4409718414; ML journal 2025). Language-grounded entities on BabyAI. Only the search snippet was seen.
- Löffler et al., "Environment Generation for Zero-Shot Compositional RL" (arXiv 2201.08896) and Raileanu & Fergus, "Decoupling Value and Policy for Generalization in RL" (arXiv 2102.10330). Both appeared in OpenAlex results only.
