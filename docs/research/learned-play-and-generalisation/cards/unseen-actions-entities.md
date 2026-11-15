# Cards: generalisation to unseen actions and entities via structured representations

Angle: action embeddings for new actions, set/entity encoders, compositional generalisation in RL, object-centric value functions.
Papers opened: 12 (9 with readable full text, 3 abstract only: Cardsformer, Headless-AD, AGLO). Cited-by counts are OpenAlex values where I retrieved them, otherwise "not checked".

---

### Generalization to New Actions in Reinforcement Learning (2020)
- **Link:** https://arxiv.org/abs/2011.01928 (full text read via https://arxiv.org/html/2011.01928) · **Venue:** ICML 2020 (PMLR 119:4661-4672) · **Cited by:** 14 (OpenAlex) · **Read:** full text (first 100k of 124k chars; appendix not read)
- **Problem:** Zero-shot generalisation of a policy to action sets containing actions never seen in training, with no retraining.
- **Method:** Two stage. A hierarchical VAE turns each action's separately collected "action observations" (trajectories, images) into a latent c_i. The policy scores each action with a utility f[c_i, f(s)] and takes a softmax over the candidate actions. Trained with PPO; training action subsets of size m are resampled per episode.
- **Assumes:** Episodic, discrete action sets; fixed split of actions 2:1:1 (train/val/test); action observations are supplied as input; representation dim 16 (Grid World) or 128 (CREATE, Shape Stacking); PPO with Adam.
- **Claims:** No exact numeric table for the main comparison (results are bar charts in Fig. 4; 5 seeds, 8 for Grid World). Text: "reasonable task success" on 3 unseen CREATE tasks, no numbers. Fine-tuning on CREATE Push: from scratch about 3 million env steps to match zero-shot performance; discrete fine-tuning over 1 million steps. Degrades as test actions move further from training actions.
- **Evaluation:** Grid World (4^5 = 1,024 five-step skills, lava and subgoal); Recommender (10,000 products); CREATE (2,111 tools, 12 tasks, hybrid selection + placement); Shape Stacking (810 shapes).
- **Code:** https://github.com/clvrai/new-actions-rl (licence not checked)
- **Fit:** partial. The candidate-scoring structure (shared scorer over a variable action set) matches a per-card-play choice, but the key input, action observations gathered separately from the task, has no StS counterpart; card effect primitives already play that role, and the paper has no numbers to compare against.

---

### Deep Sets for Generalization in RL (2020)
- **Link:** https://arxiv.org/abs/2003.09443 (full text via https://arxiv.org/html/2003.09443v1) · **Venue:** arXiv preprint (venue not checked) · **Cited by:** not checked · **Read:** full text
- **Problem:** Language-goal RL in a 2D world where the number of objects differs between training and test, and goals are out of distribution.
- **Method:** Object-wise permutation-invariant network (Deep Sets style) with gated attention: a goal-derived attention vector gates each object's features; per-object outputs are summed; a final net gives the policy or Q-value. Language goals are encoded by an LSTM (100-d).
- **Assumes:** Discrete goal set from a grammar (256 achievable goals, test goals held out); 3 objects sampled per episode out of 32 object types; continuous 2D physics; 10 seeds for the main comparison.
- **Claims:** Trained at N=3, tested up to N=10: "maintains a reasonable performance on the training set for up to N=10", generalisation "drops quickly" as N grows (no numbers given in text). MA (their model) "significantly outperforms" flat concatenation and flat attention, p < 2·10^-3 from epoch 600 (success rates only in Fig. 2). Relational extension, reward F1: train 1 obj 0.98 ± 0.01, 2 objs 0.92 ± 0.02; test 0.94 ± 0.04, 0.97 ± 0.02 (2-object test set has two examples).
- **Evaluation:** Procedurally generated 2D "Playground" world, object count N varied at test, held-out natural-language goals; per-goal success over 30 evaluations.
- **Code:** none found on the page.
- **Fit:** partial. Shows that a sum-over-entities scorer handles a varying number of entities, which is the card-hand/deck-size case. It is not a card game, reports no headline numbers in text, and the entities are spatial objects.

---

### Policy Architectures for Compositional Generalization in Control (2022)
- **Link:** https://arxiv.org/abs/2203.05960 (full text via https://arxiv.org/html/2203.05960v1) · **Venue:** arXiv; listed on icml.cc 2022 virtual site in search results (not verified) · **Cited by:** not checked · **Read:** full text
- **Problem:** Goal-conditioned control where the number of entities and the mix of entity goals change; needs a policy that extrapolates to more entities and to novel goal combinations.
- **Method:** Entity-Factored MDP: reward and dynamics invariant to permuting entity-subgoal pairs, so optimal policy and Q are permutation invariant (Prop. 1). Deep Sets policy pi = rho(sum_i phi(y_i)), y_i = concat(u, e_i, g_i); Self-Attention variant is a Transformer encoder with no positional encoding, outputs summed, then an MLP. MLP baseline zero-pads to test size.
- **Assumes:** Fixed per-entity feature vectors; discrete entity count per episode; RL via DDPG + HER (third-party implementation), plus imitation experiments.
- **Claims:** Stitching: Deep Set 48% on 2-Switch + 2-Push (trained on 2-Switch alone reaches 100%); Self-Attention 60% on Push + Stack; MLP "above 35%" on its training tasks, 5% on Push + Stack. Extrapolation: MLP succeeds only at N-Switch trained and fails above 3 switches; Deep Set exceeds Oracle on 6-Switch; Self-Attention poor on 1-Push, 1-Switch. Intro claims "more than 4x" faster learning and "greater than 15x" higher generalisation success (figures only). Imitation on 3-Push, 5,000 demos: MLP near zero, Self-Attention near 100%.
- **Evaluation:** Simulated Fetch manipulation (cubes, switches). Train N=3, test N in {1..6} for N-Push and N-Switch; N-Switch + N-Push trained at N=2, tested at 1..3.
- **Code:** none linked (project video site only).
- **Fit:** good for the question "does an entity-set policy extrapolate in entity count?" It reports the MLP failing to extrapolate and set-based policies succeeding, under a fixed per-entity feature format. Breaks on the CPU/hours constraint only if RL is needed at scale (not measured here).

---

### Deep Sets (2017)
- **Link:** https://arxiv.org/abs/1703.06114 (read via https://ar5iv.labs.arxiv.org/html/1703.06114, first 100k of 127k chars) · **Venue:** NeurIPS 2017 (from memory, not fetched) · **Cited by:** not checked · **Read:** full text (ar5iv; partial read)
- **Problem:** Learn functions on sets that are invariant to permutation and accept variable-size inputs.
- **Method:** f(X) = rho(sum_{x in X} phi(x)), with phi and rho learned networks. Theorem 2: for a countable element universe, a permutation-invariant f has this sum-decomposable form. Uncountable case proven only for fixed set size (conjectured in general). Equivariant layer: sigma(lambda I x + gamma maxpool(x) 1).
- **Assumes:** Countable domain for the theorem; fixed-size or variable-size sets; sum pooling independent of order and count.
- **Claims:** Point clouds (ModelNet40, 9,843 train / 2,468 test): 90 ± 0.3% with 5,000 points, 82 ± 2% with 100 points. Outlier detection (CelebA, sets of 16 images): finds outlier in 75% of test sets vs about 6.3% for a non-equivariant baseline. Sum of digits: trained on sets up to 10 items, tested up to 100 (accuracy in figure only). Population statistics: DeepSets scales past N = 2^14 (figure only).
- **Evaluation:** Sum of digits (MNIST sets), population statistics (Gaussian entropy, MI), point clouds, red-shift clusters, image tagging, outlier detection.
- **Code:** none linked on the page.
- **Fit:** good as the baseline architecture: one net handles any hand or deck size, and sum-pooling does not depend on order. It does not address generalisation to unseen entity types; the sum-decomposition only handles unseen counts.

---

### Set Transformer: A Framework for Attention-based Permutation-Invariant Neural Networks (2019)
- **Link:** https://arxiv.org/abs/1810.00825 (read via https://ar5iv.labs.arxiv.org/html/1810.00825) · **Venue:** ICML 2019 (from memory, not fetched) · **Cited by:** not checked · **Read:** full text (ar5iv)
- **Problem:** Attention-based permutation-invariant set models that avoid quadratic cost in set size.
- **Method:** MAB (multihead attention + residual + LayerNorm + rFF, no positional encoding). SAB = MAB(X,X), O(n^2). ISAB_m uses m inducing points, O(nm). PMA_k pools with k learnable seeds. Encoder: stacked SABs or ISABs; decoder: rFF(SAB(PMA_k(Z))).
- **Assumes:** Set inputs, permutation-invariant output; training set sizes vary within task (counting, clustering) or fixed (point clouds); no RL.
- **Claims:** Amortised clustering, CIFAR-100 (n in [100, 500]): ISAB(16)+PMA ARI0 0.9210 ± 0.0055, SAB+Pooling 0.5831. Omniglot unique-character counting (train sets 6-10 images): SAB+PMA accuracy 0.6037 ± 0.0075 vs rFF+Pooling 0.4382. ModelNet40: ISAB(16)+Pooling 0.8273 / 0.8915 / 0.9040 at 100 / 1000 / 5000 points. Universal approximation claimed (proof in supplement, not read). No result on train-small, test-large.
- **Evaluation:** Max-value regression (toy), Omniglot counting, amortised clustering (synthetic 2D, CIFAR-100 VGG features), ModelNet40, CelebA set anomaly detection (1,000 sets, 7 normal + 1 anomaly).
- **Code:** none linked on the page.
- **Fit:** partial. Attention over a hand of up to about 10 cards is cheap, so the O(n^2) concern does not bind here; the attention-based entity interaction may matter for card-card synergy. No RL or extrapolation results.

---

### Deep Reinforcement Learning with a Natural Language Action Space (2016)
- **Link:** https://arxiv.org/abs/1511.04636 (read via https://ar5iv.labs.arxiv.org/html/1511.04636) · **Venue:** ACL 2016 · **Cited by:** 168 (OpenAlex, ACL record W2964179661) · **Read:** full text (ar5iv)
- **Problem:** RL when states and actions are natural language, so the feasible action set changes per state and actions are unseen strings at test time.
- **Method:** DRRN: separate state-text DNN and action-text DNN; Q(s,a) = g(h_s, h_a) with g an inner product. Each feasible action is scored by the same action-side network, so the candidate count can vary. Training backprops only through the action taken; softmax exploration over Q during training, argmax at test.
- **Assumes:** Discrete candidate action set per state (max 4 in "Saving John", max 9 in "Machine of Death"); stochastic transitions in one game; 5 independent runs; lr 0.001; discount 0.9; actions shuffled.
- **Claims:** Saving John, hidden 100, L=2: DRRN 18.7 (0.4) vs MA DQN (L=2) 7.1 (3.1), PA DQN (L=2) 7.9 (3.0). Machine of Death, hidden 100, L=2: DRRN 11.2 (0.6) vs MA DQN 5.2 (1.2). Paraphrase test (153 paraphrases, 532 state-action pairs): DRRN L=2 reward 10.5 (0.9) at hidden 100, vs 11.2 on original actions. Q-value pR^2 0.95 for DRRN on paraphrases.
- **Evaluation:** Two text games, "Saving John" and "Machine of Death" (simulators at github.com/jvking/text-games).
- **Code:** no DRRN code linked; simulators at https://github.com/jvking/text-games (licence not checked).
- **Fit:** good. Shared scorer over a variable, per-state candidate set is the structure a per-card-play value net needs, and the paraphrase test is a direct generalisation-to-new-surface-form measure. Breaks the "entity" part: no sets, and the inputs are free text, not effect primitives.

---

### Deep Reinforcement Learning in Large Discrete Action Spaces (2015)
- **Link:** https://arxiv.org/abs/1512.07679 (read via https://ar5iv.labs.arxiv.org/html/1512.07679) · **Venue:** arXiv (venue not checked) · **Cited by:** not checked · **Read:** full text (ar5iv)
- **Problem:** Discrete action sets of 10^6 or more, where enumerating actions is too costly.
- **Method:** Wolpertinger: the actor outputs a proto-action in R^n; kNN (approximate, FLANN) returns the k nearest discrete actions by L2; the critic picks the best of the k. Action embeddings are built from prior information about each action and are fixed (learning them is listed as future work).
- **Assumes:** Actions have an n-d embedding from prior info; DDPG with replay and target networks; the policy is not differentiable through the argmax; deterministic or simulated dynamics.
- **Claims:** Cart-pole swing-up with 1M discretised actions: k=1 converges; k=5,000 did not reach 100,000 steps in the same wall time. Puddle World, 2^20 = 1,048,576 actions: up to 1,250x speedup for equivalent performance. Recommender with 13,138 items: k=1 failed to learn; full action set 1.5 steps/s (exact FLANN) vs 31 steps/s for k=1. Stated limitation: performance depends on a well-structured embedding, and the critic re-ranking step compensates for poor placement.
- **Evaluation:** Discretised MuJoCo cart-pole swing-up (i^d actions), Puddle World 50x50 multi-step planning (n-step plans, n=1..20), simulated recommender (49, 835, 13,138 items).
- **Code:** no official code; an unofficial PyTorch port at https://github.com/nikhil3456/Deep-Reinforcement-Learning-in-Large-Discrete-Action-Spaces (licence not checked, not opened).
- **Fit:** poor for the StS problem. StS candidate sets are small (hand of up to about 10 cards times targets), so the scale that motivates kNN lookup does not occur. Useful only as the reference for fixed embeddings that the critic re-ranks.

---

### ASNets: Deep Learning for Generalised Planning (2020)
- **Link:** https://arxiv.org/abs/1908.01362 (read via https://ar5iv.labs.arxiv.org/html/1908.01362, first 100k of 196k chars; results in section 5.5 not reached) · **Venue:** JAIR 68 (2020) · **Cited by:** not checked · **Read:** full text (ar5iv, partial read)
- **Problem:** Learn one reactive policy per planning domain that transfers to much larger problems.
- **Method:** Alternating proposition and action layers (2 proposition, 3 action layers; hidden 16). Action modules (one per ground action) and proposition modules (one per ground proposition), with max-pooling per (action schema, argument position). Weights are tied per action schema and per predicate, so the same weights apply to any problem in the domain. Trained by imitation of a teacher (LRTDP with h-add, or A* with h-add) with DAgger-style rollouts.
- **Assumes:** Relational (PPDDL/PDDL) state; applicable actions via masked softmax; quantifier-free goals (conjunctions of positive literals); fixed depth; 2-hour training cap; Adam lr 10^-3, batch 64.
- **Claims:** Train/test sizes are given (e.g. Blocksworld: 25 problems of 8-10 blocks train, 30 problems of 35 or 50 blocks test). Coverage is shown in figures only; the Fig. 6 caption says all ASNet configurations except "no h." reach perfect coverage asymptotically on CosaNostra, Triangle Tireworld, and Probabilistic Blocksworld. Policy-gradient RL was "too inefficient" to train in reasonable time (their words).
- **Evaluation:** 7 domains (Triangle Tireworld, CosaNostra Pizza, Probabilistic/Exploding/Matching Blocksworld, Gold Miner, Blocksworld); 30 rollouts per probabilistic test problem; three-hour cutoff for baselines.
- **Code:** https://github.com/qxcv/asnets (licence not checked)
- **Fit:** partial. Weight tying per schema is the closest published analogue to "one card-effect primitive set, shared across all cards". It needs symbolic relational states and a teacher planner, and it is trained by imitation, similar to the current setup; no StS-like stochastic card game is evaluated.

---

### Learning With Generalised Card Representations for "Magic: The Gathering" (2024)
- **Link:** https://arxiv.org/abs/2407.05879 (full text via https://arxiv.org/html/2407.05879v1) · **Venue:** arXiv 2024; search snippet names IEEE CoG 2024 (not verified) · **Cited by:** not checked · **Read:** full text
- **Problem:** Deck building (drafting) in MTG where new card sets constantly add unseen cards; need card representations that generalise to them.
- **Method:** Siamese network with contextual preference ranking (CPR) triplet loss; cards and decks each encoded to 512-d. Card inputs compared: random 1024-d, one-hot (302), hand features plus sentence-transformer text embedding (1306), convolutional autoencoder image latents (32 or 1024), 16 meta statistics from 17Lands, and combinations.
- **Assumes:** Supervised learning from human draft picks (about 100 million picks; DraftSim M19 and 17Lands); no gameplay or RL; pre-train on all sets except BRO to simulate an unseen release.
- **Claims:** Table II (trained on NEO), top-1 accuracy: average over unseen sets: Random 23.79%, Meta 42.14%, Features 33.57%, Features + Meta + Image 1024 42.87%; NEO test: Random 67.87%, Features 67.76%. Abstract: the model "is able to predict 55% of human choices on completely unseen cards." Random guess about 0.22. Pre-training: BRO 55.44%, tuned on BRO 62.27%.
- **Evaluation:** Top-1 accuracy of predicting human picks on 80/20 splits of M19, NEO, LTR, BRO and other sets; unseen-set transfer.
- **Code:** none found on the page.
- **Fit:** partial. The clearest measured evidence in this batch that feature-based (non-ID) card representations transfer to unseen cards, with numbers. It does not test play quality or RL, so it breaks the "beats the heuristic" half of the goal.

---

### Cardsformer, Hearthstone generalisable policy with card text (FAIA 2023; exact title not confirmed)
- **Link:** https://ebooks.iospress.nl/doi/10.3233/FAIA230581 (abstract page only; PDF link on page not readable) · **Venue:** IOS Press, Frontiers in Artificial Intelligence and Applications, DOI 10.3233/FAIA230581 · **Cited by:** not checked · **Read:** abstract (paywalled or PDF unreadable)
- **Problem:** Agents struggle to learn Hearthstone rules from card text and to generalise policies to cards they have not seen.
- **Method:** Two parts per abstract: a Prediction Model trained on offline trajectories that predicts state transitions from card descriptions, and a Policy Model that generalises to unseen cards. Architecture details not visible.
- **Assumes:** Hearthstone; offline trajectories for the prediction model; card text as input.
- **Claims:** Abstract only: better data efficiency and state-of-the-art performance, including decks containing untrained cards. No numbers on the visible page.
- **Evaluation:** PyStone (Hearthstone code base) described as an open benchmark; split and metrics not visible.
- **Code:** PyStone, link not on the visible page; licence not stated.
- **Fit:** good in topic (unseen cards in a card game with card text), but the method and numbers could not be checked. Do not rely on it until the PDF is read.

---

### In-Context Reinforcement Learning for Variable Action Spaces (2023)
- **Link:** https://arxiv.org/abs/2312.13327 (abstract page only) · **Venue:** arXiv (venue not checked) · **Cited by:** not checked · **Read:** abstract
- **Problem:** In-context RL transformers are tied to a fixed action space; a new action space normally means recollecting data and retraining.
- **Method:** Headless-AD, trained once, to handle discrete action spaces that differ in size, semantic content, and order. Action encoding not visible in the abstract.
- **Assumes:** Discrete action spaces; in-context adaptation.
- **Claims:** Abstract: "exhibits significant capability to generalize to action spaces it has never encountered" and outperforms specialised models on several configurations. No numbers visible.
- **Evaluation:** Bernoulli bandits, contextual bandits, and a gridworld.
- **Code:** https://github.com/corl-team/headless-ad (licence not checked)
- **Fit:** poor-partial. Bandit and gridworld tasks only, no card-like entities; the in-context pattern is worth a note if the agent adapts to new deck contents at test time.

---

### Zero-Shot Action Generalization with Limited Observations (2025)
- **Link:** https://arxiv.org/abs/2503.08867 (abstract page only) · **Venue:** arXiv 2025 · **Cited by:** 0 (OpenAlex) · **Read:** abstract
- **Problem:** Zero-shot generalisation to unseen actions in RL when only a few action observations are available (earlier methods need large datasets of these).
- **Method:** AGLO: an action representation learning module that extracts discriminative embeddings from limited observations, plus a policy module that uses these embeddings and augmented synthetic action representations.
- **Assumes:** Action observations supplied for unseen actions; discrete actions.
- **Claims:** Abstract only: "significantly outperforms state-of-the-art methods" on "multiple benchmark tasks". No numbers, benchmarks or metrics visible. Does not mention Jain et al. on the visible page.
- **Evaluation:** Not visible.
- **Code:** none linked on the page.
- **Fit:** poor-partial. It is the most recent follow-up to Jain et al. in this search, but it still needs action observations that StS does not supply, and no numbers were visible.

---

## Notes for the caller

- Search trail: OpenAlex keyword searches ("generalization new actions action embedding", "unseen actions ... generalization") and the OpenAlex citation query for Jain 2020 (W3035041226, `cites:` with search terms). The citation query mostly returned off-topic deep-RL work. The two later on-topic papers (AGLO 2025, Headless-AD 2023) came from keyword search, not from the citation graph.
- Gaps: Cardsformer's PDF and the Jain appendix were not reached. No paper here reports a "with vs without action representation" number that transfers to card play.
