# Cards: general game playing and rule-conditioned agents

Angle: GGP/GDL, Ludii, GVGAI, agents conditioned on rule or card text, cross-game transfer of value functions.
Scout date: 2026-10-24. Opened: 12 papers (5 read in full text, 7 read at abstract or landing-page level).
"Cited by" is the OpenAlex count of the record named in the card, or "not checked".

---

### Learning With Generalised Card Representations for "Magic: The Gathering" (2024)
- **Link:** https://arxiv.org/abs/2407.05879 (HTML: https://arxiv.org/html/2407.05879v1) · **Venue:** arXiv 2407.05879 (page marks IEEE 2024) · **Cited by:** not checked · **Read:** full text
- **Problem:** Drafting models built on one-hot card IDs cannot score a card outside the training pool. The authors want card representations that generalise to unseen cards.
- **Method:** Siamese card and deck encoders trained with triplet loss (margin 1, Euclidean distance) into a 512-dim tanh embedding. The card encoder is 4 fully connected layers of 1024; the deck encoder is 6 conv layers plus an output layer. Representations compared: random vectors, one-hot, image-autoencoder latents, hand-coded numerical and categorical features plus a sentence-transformer embedding of card text (1306 inputs), and 16 usage statistics.
- **Assumes:** Discrete picks. Supervised on about 100 million human picks across 14 sets, split 80/20. Top-1 accuracy. No game simulation and no outcome signal.
- **Claims:** Unseen-card top-1 accuracy (NEO-only training, averaged over unseen sets, Table II): Random 23.79%, Features 33.57%, Meta 42.14%, Features+Meta 34.74%, Features+Meta+Image 1024 42.87%, one-hot NaN (cannot represent unseen cards). Transfer (pretrained with BRO held out): 55.44% on BRO. Abstract: "predict 55% of human choices on completely unseen cards."
- **Evaluation:** Offline top-1 match between the human pick and the card closest to the deck embedding, on 17Lands and DraftSim MTG data. Reproducible as an offline held-out test on card feature vectors.
- **Code:** none found
- **Fit:** partial. Feature-based card encoding (including text) generalises to unseen cards, which is the property we need. But the target is imitation of human picks, not play strength or value regression on outcomes.

### Transfer of Fully Convolutional Policy-Value Networks Between Games and Game Variants (2021)
- **Link:** https://arxiv.org/abs/2102.12375 (HTML v1: https://arxiv.org/html/2102.12375v1) · **Venue:** arXiv preprint, later TMLR 2023 (see the TMLR card) · **Cited by:** 6 (OpenAlex W3132202707) · **Read:** full text
- **Problem:** Reuse AlphaZero-style policy-value networks across Ludii variants and across distinct games, without retraining from scratch.
- **Method:** Fully convolutional ResConv network with global pooling (Polygames ResConvConvLogitPoolModelV2: 10 residual blocks, 6 conv layers per block, hidden channels twice the state channels). Channels are matched by heuristic rules. Direct state channels carry over; containers map by order; piece-presence channels match by exact name or by Zhang-Shasha tree edit distance on ludeme trees; action channels match by type.
- **Assumes:** Grid boards, discrete turns, two-player zero-sum, AlphaZero-style self-play. Fine-tuning baseline is 20 hours of target-side training.
- **Claims:** 150 ordered variant pairs across 9 games. Zero-shot win % against a target-trained model, 300 games per pair: Breakthrough Square8 to Square10 77.00%; Hexagon6 to Hexagon8 39.67%; Diagonal Hex 9x9 to 13x13 100.00%; Konane 8x8 to 10x10 94.00%; Hex 7x7 to 19x19 91.67%; Minishogi to Shogi 97.00%; Gomoku to Connect6 36.67%; Diagonal Hex to Hex mostly 0.00%. The paper says zero-shot win percentages "tend to be below 50%" for large-to-small transfer. Fine-tuning shows negative transfer in "a small number of cases"; Diagonal Hex to Hex shows "a high degree of negative transfer."
- **Evaluation:** Ludii board games. 300 games per pair in the target domain against a target-trained model. Reproducible with the Ludii and Polygames setup.
- **Code:** Polygames at https://github.com/facebookincubator/Polygames (linked in a footnote). Channel-mapping code was not released in v1 (promised after review). License not checked.
- **Fit:** partial. Shows zero-shot transfer when the input and output encodings share semantics, with a hand-written mapping between games. The matching is per channel and tied to grid boards, so it does not transfer to card text directly. The idea of semantic matching carries over.

### Towards a General Transfer Approach for Policy-Value Networks (TMLR 2023)
- **Link:** https://mlanthology.org/tmlr/2023/soemers2023tmlr-general · OpenReview: https://openreview.net/forum?id=vJcTm2v9Ku · **Venue:** Transactions on Machine Learning Research (TMLR), 2023 · **Cited by:** not checked · **Read:** abstract (landing page only; the OpenReview PDF was not opened)
- **Problem:** Transfer trained policy-value networks between Ludii games with different board sizes, shapes and rules. The authors also argue for benchmarks with domain-specific description languages.
- **Method:** Per the landing page, "a simple baseline approach for transferring fully convolutional policy-value networks" that guide AlphaZero-like search, between any pair of games in Ludii. The mechanism is not described on the page. The page notes that DSL task information could make zero-shot transfer achievable.
- **Assumes:** Ludii board games, which are described in a DSL. No hidden information.
- **Claims:** "various cases of highly successful zero-shot transfer." No numbers on the page.
- **Evaluation:** Ludii, which has more than 1000 games. The number of pairs is not on the page.
- **Code:** https://github.com/DennisSoemers/Transfer-DNNs-Ludii-Polygames (listed on the landing page; not opened, license not checked)
- **Fit:** partial. Same line of work as the 2021 card, in its later form. Read the PDF before relying on any numbers.

### Biasing MCTS with Features for General Games (2019)
- **Link:** https://arxiv.org/abs/1903.08942 (HTML: https://arxiv.org/html/1903.08942) · **Venue:** arXiv 1903.08942 (no venue on the page) · **Cited by:** 0 (OpenAlex arXiv record W4288411100) · **Read:** full text
- **Problem:** Learn a cheap, interpretable policy over game-agnostic features that biases MCTS, without deep networks or hand-tuned per-game features.
- **Method:** Linear softmax policy over binary pattern features. Each pattern tests positions (off-board, empty, friendly, enemy) at relative walks and recommends an action. Trained by expert iteration: MCTS visit counts are the targets, with cross-entropy, L2 regularisation and SGD. Features grow by combining co-active pairs during self-play. The authors also prune to the 15 largest-weight features.
- **Assumes:** Two-player Ludii board games. Discrete turns. 5 s thinking time per move and a 100-move limit, C_puct = sqrt(2). Up to 200 self-play games per checkpoint.
- **Claims:** Qualitatively, Biased MCTS significantly outperforms UCT in Breakthrough, Fanorona, Hex 11x11, Othello and Teeko. A greedy linear agent with no search reaches "a win percentage of 40%" against UCT in Breakthrough and Teeko after 200 self-play games. Hand-crafted Yavalath features (three features, weights +3000 and -1000) reach 93% against UCT, with a 30x iteration reduction. Exact curves appear only in figures. Transfer between games is not evaluated and is listed as future work.
- **Evaluation:** Ten variants of nine Ludii games. 200 games per checkpoint, 95% confidence intervals, ties counted as half a win.
- **Code:** none found on the page
- **Fit:** partial. The pattern features (a condition plus a recommended action) are close in spirit to effect primitives, and the feature-growth step is a way to find interactions. But the paper does not test transfer, uses search targets rather than outcome regression, and has no value net.

### General game learning using knowledge transfer (2007)
- **Link:** https://ijcai.org/Abstract/07/107 · **Venue:** IJCAI 2007 · **Cited by:** 104 (OpenAlex W2106953752) · **Read:** abstract. The PDF on the Stone lab mirror failed with a certificate error.
- **Problem:** Transfer RL value knowledge between general games whose state spaces differ.
- **Method:** Value-function transfer. General features are extracted from the state space of a previous game and matched to the state space of a new game. The matching uses game-tree lookahead structure as features.
- **Assumes:** GGP games in GDL, with a reinforcement learner on the target game. The abstract does not state more.
- **Claims (abstract only, no numbers):** Transfer "learns superior policies faster than a reinforcement learner that does not use knowledge transfer." Lookahead-feature transfer can also exploit an opponent's weaknesses faster than a learner using minimax against the same opponent.
- **Evaluation:** Not on the abstract page.
- **Code:** none found
- **Fit:** partial. Lookahead-based features are a cross-game representation that could carry over. But the claim is faster learning on the target game, not zero-shot play, and there are no numbers in the abstract.

### Object-Model Transfer in the General Video Game Domain (2016)
- **Link:** https://doi.org/10.1609/aiide.v12i1.12870 · PDF: https://ojs.aaai.org/index.php/AIIDE/article/view/12870/12718 (PDF not readable through the fetch tool) · **Venue:** AIIDE 2016, poster papers · **Cited by:** 5 (OpenAlex W4312354311; a duplicate record W2522413982 shows 9) · **Read:** abstract
- **Problem:** Train video game agents when data is limited, by transferring knowledge from games already known to unfamiliar GVGAI games.
- **Method:** Split each game into objects, learn one model per object type, and transfer the object models from known games to help learning in new games. Abstract-level detail only.
- **Assumes:** GVGAI, a 2D arcade framework. Timing and determinism are not stated on the page.
- **Claims:** "Experiments show that the approach improves prediction accuracy over a comparable control." No numbers on the page.
- **Evaluation:** Not on the page; the PDF was not readable.
- **Code:** none found
- **Fit:** partial. Factoring a game into typed components and transferring per-component models is structurally close to per-card effect primitives. No numbers are available without the PDF.

### General Board Game Concepts (2021)
- **Link:** https://arxiv.org/abs/2107.01078 (HTML v1: https://arxiv.org/html/2107.01078v1) · **Venue:** arXiv 2107.01078 (also an IEEE CoG 2021 record in OpenAlex) · **Cited by:** 22 (OpenAlex arXiv record W4205287490) · **Read:** abstract
- **Problem:** Shared ideas across general board games (rules, controls, playing areas) are under-explored, so the paper formalises them as "game concepts."
- **Method:** Concepts are defined at three levels: the game, the moves, and the states. They are implemented in the Ludii ludeme representation. The abstract lists possible uses, including transfer of AI learning between games, but gives no method for that.
- **Assumes:** Ludii board games.
- **Claims:** None quantitative on the page.
- **Evaluation:** None on the page.
- **Code:** none found on the page
- **Fit:** poor. A shared concept vocabulary could describe cards by concept, but there is no method or evaluation.

### Grounding Language to Entities and Dynamics for Generalization in Reinforcement Learning (EMMA, 2021)
- **Link:** https://arxiv.org/abs/2101.07393 (HTML v2: https://arxiv.org/html/2101.07393v2) · **Venue:** ICML 2021 (per the arXiv comment) · **Cited by:** not checked · **Read:** full text
- **Problem:** Zero-shot generalisation to unseen games where free-text manuals define entity roles and dynamics, with no prior text-to-observation links.
- **Method:** EMMA. A frozen pretrained BERT-base encodes the manual sentences. Each entity's symbol embedding attends over the description keys and values, giving a text-conditioned entity representation placed on the grid. Three recent observations are concatenated. The policy is a 2x2 conv layer followed by a 3-layer FC network, trained with PPO (Adam, learning rate 5e-5).
- **Assumes:** Grid-world Messenger. Discrete actions. 12 entities and 1320 possible games. Split: 44 train, 32 validation and 32 test games. Results are mean ± std over three seeds.
- **Claims:** Unseen test win rates (Table 2). S1-Test: Emma 85±1.4, BAM 66±1.5, txt2π 2.5±1.7, G-ID 18±8.2. S2-Test: Emma 85±0.6, BAM 41±1.7. S3-Test (five entities, one distractor description): Emma 10±0.8, BAM 2.7±0.9. The table also has an O-Map row (97±0.3, 87±1.8, 80±1.5); I did not confirm what that baseline is. Robustness on S2 test: Append (extra descriptor) 78±3.9 vs BAM 36±1.7; Delete 33±2.3 vs 17±2.0; Synonyms 75±3.4 vs 8.5±1.0.
- **Evaluation:** Messenger, a grid environment. Test games never assign a training role to the entity. Reproducible from the stated split and the code.
- **Code:** https://github.com/ahjwang/messenger-emma (license not checked)
- **Fit:** partial. Grounding text to entities generalises to unseen game configurations, and the synonym and distractor tests are close to paraphrased card text. But it needs per-entity text and PPO on a grid, and the paper reports no compute budget.

### Cardsformer: Grounding Language to Learn a Generalizable Policy in Hearthstone (2023)
- **Link:** https://ebooks.iospress.nl/doi/10.3233/FAIA230581 · **Venue:** ECAI 2023, Frontiers in Artificial Intelligence and Applications vol. 372, pp. 2720–2727 · **Cited by:** not checked · **Read:** abstract (guest access shows only the abstract and metadata)
- **Problem:** Hearthstone agents struggle with card effects written in natural language, and their policies do not generalise through that language.
- **Method:** A Prediction Model trained on offline trajectories predicts state transitions from card descriptions. A Policy Model is designed to generalise to unseen cards. No architecture is given on the page.
- **Assumes:** Hearthstone. Offline trajectories. The dataset size and source are not given.
- **Claims:** "significantly improves data efficiency," and outperforms the state of the art, including when the deck contains untrained cards. No numbers on the page.
- **Evaluation:** Not on the page. The abstract names PyStone as the Hearthstone code base used in the experiments.
- **Code:** The abstract says the code is public and that PyStone is released as an open benchmark. No link appears on the page. Page licence: CC BY-NC 4.0.
- **Fit:** good on topic. It is a card-description-conditioned policy that aims at unseen cards. No numbers are available without the full text.

### LeDeepChef: Deep Reinforcement Learning Agent for Families of Text-Based Games (2019; AAAI 2020)
- **Link:** https://arxiv.org/abs/1909.01646 · AAAI record: https://doi.org/10.1609/aaai.v34i05.6228 · **Venue:** arXiv 2019; AAAI 2020 · **Cited by:** 38 (OpenAlex AAAI record W2996887765) · **Read:** abstract
- **Problem:** One RL agent for a family of text games that share a theme but differ in layout, objects and recipe, so it generalises to unseen games in the family.
- **Method:** Actor-critic. Action-space pruning uses ideas from hierarchical RL and a module trained on a recipe database.
- **Assumes:** TextWorld text games. Discrete text actions.
- **Claims:** Entered in the First TextWorld Problems challenge. "outperformed all but one competitor on the final test set." No score on the page.
- **Evaluation:** The First TextWorld Problems test set. Split details are not on the page.
- **Code:** none found
- **Fit:** partial. Shows family-level generalisation through a shared structure and a knowledge module. No numbers, and the domain is text games.

### Evaluating Generalisation in General Video Game Playing (2020)
- **Link:** https://arxiv.org/abs/2005.11247 (HTML v1: https://arxiv.org/html/2005.11247v1) · **Venue:** IEEE CoG 2020 (per OpenAlex; the page does not name the venue) · **Cited by:** 3 (OpenAlex W3026659457) · **Read:** full text
- **Problem:** Measure how much A2C-style agents generalise to unseen levels of GVGAI games when trained on very few levels.
- **Method:** Three A2C variants: standard, with global average pooling (GAP), and with PopArt reward normalisation. RGB pixel input, 50M frames per game, no reward clipping. Final weights are evaluated zero-shot on unseen levels. Three seeds, 20 evaluations per level.
- **Assumes:** Pixel observations. 2D arcade games: Aliens, Zelda, Missile Command, Seaquest. Missile Command is deterministic. Training uses one or two levels.
- **Claims:** Aliens, trained on lvl0+lvl1: A2C 0.44, GAP 0.46, PopArt 0.37 (average win rate across five levels). Seaquest, trained on lvl0+lvl3: A2C and GAP 1.00, PopArt 0.74. Zelda, trained on lvl0+lvl1: all agents 0.00 to 0.01. Main finding: "stochasticity improves the generalisation, but too much can cause the algorithms to fail to learn the training levels." The paper also finds that higher scores do not mean winning.
- **Evaluation:** GVGAI levels lvl0 to lvl4 for each of the four games. Reproducible as a held-out-level protocol.
- **Code:** none found
- **Fit:** partial. Gives a protocol for training on few instances and testing on unseen ones, and a warning that score and win rate can diverge. It uses pixels rather than rules and does not cover value nets or card games.

### Instruction-Driven Game Engine: A Poker Case Study (2024)
- **Link:** https://arxiv.org/abs/2410.13441 · **Venue:** EMNLP 2024 demo (per the arXiv comment) · **Cited by:** 1 (OpenAlex arXiv record W4403579733) · **Read:** abstract
- **Problem:** Create and run new game variants from natural-language rule descriptions, with precise state computation.
- **Method:** An LLM is given free-form game descriptions and trained with next-state prediction, where it predicts the game state after each player action. A curriculum raises the difficulty over training. How the agent plays is not stated on the abstract.
- **Assumes:** Poker variants. LLM-based.
- **Claims:** The engine supports "a wide range of poker variants" from natural-language input. No numbers on the page.
- **Evaluation:** Not on the page.
- **Code:** none found
- **Fit:** poor. It is a rule-description-conditioned engine built on an LLM. That does not fit CPU-only training of a value net, but it marks the rule-text end of the spectrum.

---

## Not carded

- Xia et al., Hearthstone AAMAS 2025 extended abstract (https://aamas.csc.liv.ac.uk/Proceedings/aamas2025/pdfs/p2795.pdf). The PDF fetch returned raw compressed bytes and no text. Not opened for a card. It is a possible lead for the T5 card-text encoder with RL, and a retry through another route may work.
- Banerjee and Stone 2007 PDF, Braylan and Miikkulainen 2016 PDF: fetch failed. Only the abstract pages were read (cards above).
