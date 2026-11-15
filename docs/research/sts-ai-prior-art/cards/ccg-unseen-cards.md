# CCG AI prior art: playing or valuing cards unseen in training

Scope: non-StS collectible and strategy card game AIs (MTG, Hearthstone, LOCM, Yu-Gi-Oh, Dominion). Eight papers or resources were opened. Seven were read in full text; Cardsformer was read at abstract and landing-page level only.

Search notes: OpenAlex keyword search and citation lookups were used alongside web search. The following were found but not opened, so they have no card:
- AAMAS 2025 extended abstract, "Integrating LLMs with RL for Generalization in Strategic Card Games" (Xia et al.). Its PDF returned binary through WebFetch. Search snippet only: a fine-tuned T5 turns card tokens into descriptions; Hearthstone; zero-shot on new cards; up to 50% unseen cards in one test deck. LLM in the loop, so it is out for play time.
- Chaos Cards (AIIDE 2020, grammar-based card generation with meta-based evaluation). The AAAI PDF returned a bot-check page.
- SPELLS (2025, MTG latent power prediction, thesis PDF). Returned binary.
- UrzaGPT (arXiv 2508.08382). LoRA-tuned LLM for MTG card selection; search snippet says 66.2% vs 43% zero-shot GPT-4o. Not opened, and LLM-based.
- Hybrid information sources for card representations (IEEE ICDMW 2018), DTCard (Applied Sciences 2026, trick-taking games), Mastering Strategy Card Game (Hearthstone) with Improved Techniques (arXiv 2303.05197). Not opened.

---

### Learning With Generalised Card Representations for "Magic: The Gathering" (2024)
- **Link:** https://arxiv.org/abs/2407.05879 (HTML: https://arxiv.org/html/2407.05879v1) · **Venue:** IEEE Conference on Games 2024 (DOI 10.1109/cog60054.2024.10645602) · **Cited by:** 7 (OpenAlex) · **Read:** full text
- **Problem:** MTG draft pick prediction with one-hot card encodings (CPR, Siamese) cannot score cards that were not in training. Which card representation generalises to new cards?
- **Method:** Siamese network with triplet loss (margin 1, Euclidean). Card encoder is 4 FC layers of 1024; deck encoder is 6 conv layers; shared 512-dim head. Card inputs compared: one-hot (302), random 1024, image autoencoder (32 or 1024), numerical/categorical features plus sentence-transformer embedding of card text (1306), 16-dim usage meta from 17Lands, and combinations.
- **Assumes:** Pick-level human data (about 100M picks over 14 sets; 80/20 split per dataset). Top-1 accuracy of matching the human pick. The meta vector (pick and win rate) only exists for cards with usage history. Compute not reported.
- **Claims:** Table II, trained only on NEO, top-1 accuracy (NEO test / unseen sets): one-hot 67.80% / NaN; random 1024 67.87% / 23.79%; image 32 65.93% / 28.69%; image 1024 68.09% / 31.10%; meta 64.73% / 42.14%; features 67.76% / 33.57%; features+meta 68.07% / 34.74%; features+image1024 67.81% / 35.59%; features+meta+image1024 68.00% / 42.87%. Transfer (Table III): pre-trained on other sets, BRO 55.44%; after tuning on BRO, BRO 62.27%. The authors say pre-training does not raise peak accuracy but adapts faster. Tuning on NEO causes forgetting on other sets.
- **Evaluation:** The held-out "unseen sets" are not named in the text, and the number of unseen-set test decisions is not stated. Second protocol: hold out BRO and train on the other sets.
- **Code:** none found (data sources only: 17Lands, DraftSim).
- **Fit:** partial. Clear evidence that feature and text encodings generalise where one-hot cannot, and that usage statistics help a lot on unseen cards. But the task is drafting, not play, and the best unseen-card variant depends on meta data that a brand-new card would not have.

### DraftFM: A Foundation Model for Day-Zero Drafting in Magic: The Gathering (2026)
- **Link:** https://arxiv.org/abs/2608.19568 (HTML: https://arxiv.org/html/2608.19568) · **Venue:** arXiv preprint, no peer review stated (posted 20 Aug 2026) · **Cited by:** 0 (OpenAlex, SSRN-record ID) · **Read:** full text
- **Problem:** Draft a new MTG set before any draft logs exist ("day-zero"), using only the public card list.
- **Method:** Frozen 775-dim card vector: 391 structured Scryfall features plus a frozen 384-dim bge-small-en-v1.5 embedding of type line and rules text (card name removed). Shared card encoder 775→512→256; pool encoder with 4 learned queries via cross-attention; scorer; softmax over pack. Cross-entropy with label smoothing 0.05; AdamW, lr 1e-3.
- **Assumes:** Public card data only (no set identity, no usage stats, no images or prices). Pick data from 17Lands: 60 files, 32 sets, 169,932,378 picks. Model has 1,637,999 parameters.
- **Claims:** Withheld three full expansions (BRO, FDN, MSH; 12,571,237 picks, 296,224 drafts). Top-1 agreement for the d=256 model: BRO 50.83%, FDN 60.37%, MSH 56.67%, mean 55.96%. Chance at the opening pick is about 7%. Training took 3.02 hours (hardware not stated). The three held-out sets were also used to choose width, so these are development results.
- **Evaluation:** Leave-whole-set-out on MSH, FDN, BRO. Baselines are cited from other settings and are not directly comparable. The author quotes Bertram et al. 2024a at 55.44% on BRO with usage stats, and feature-only models at 33.6–35.6% on unseen sets.
- **Code:** GitHub repository mentioned for a forecast artifact; licence not stated in the visible text.
- **Fit:** partial. The most direct evidence for a new-expansion setting with frozen, precomputable card features. The task is drafting, and a frozen text encoder is used (not an LLM at play time). The input recipe (structured fields plus frozen text embedding) transfers as an idea, not as a play method.

### Cardsformer: Grounding Language to Learn a Generalizable Policy in Hearthstone (2023)
- **Link:** https://doi.org/10.3233/FAIA230581 (landing: https://ebooks.iospress.nl/doi/10.3233/FAIA230581) · **Venue:** ECAI 2023, FAIA vol. 372, pp. 2720–2727 · **Cited by:** 5 (OpenAlex) · **Read:** abstract only (publisher landing page; full PDF not reachable)
- **Problem:** Hearthstone agents cannot generalise their policy to cards whose effects are given only in natural-language text.
- **Method:** Two models. A Prediction Model learns state transitions from offline trajectories using card descriptions. A Policy Model is meant to generalise to unseen cards. A search snippet names a pretrained MPNet encoder for card text, but I did not confirm that on a page I could read.
- **Assumes:** Hearthstone, offline trajectories, card descriptions as text input. Dataset size, RL algorithm and encoder details were not visible.
- **Claims:** Abstract only: "significantly improves data efficiency and outperforms the state-of-the-art in Hearthstone even when there are untrained cards in the deck." No numbers were visible on the page I could read.
- **Evaluation:** Hearthstone decks with untrained cards. Abstract says code is released along with an open benchmark called PyStone. Exact protocol not visible.
- **Code:** abstract says code is public (PyStone); no link on the page I read. Licence not found.
- **Fit:** partial. The text-to-policy idea is the closest match to our problem (new effects described by text, a policy that transfers). Language-model embeddings must be precomputed; that is acceptable only with a frozen encoder at play time. Read the PDF before relying on any numbers.

### Causal Reinforcement Learning for Complex Card Games: A Magic The Gathering Benchmark (2026)
- **Link:** https://arxiv.org/abs/2605.06066 (HTML: https://arxiv.org/html/2605.06066v1) · **Venue:** arXiv preprint (7 May 2026), no peer review listed · **Cited by:** 1 (OpenAlex) · **Read:** full text (appendices truncated in fetch)
- **Problem:** Benchmark for causal RL in MTG combining sequential decisions, hidden information and masked actions.
- **Method:** Gymnasium environment with Stable-Baselines3 PPO. CGFA-PPO adds per-factor critic heads, learnable mixture weights, a residual gate and a calibration loss over a hand-written structural causal model.
- **Assumes:** Fixed pool of 56 Standard 2025 cards, 60-card decks, five archetypes. Observation vector 3,077-dim; 478 masked discrete actions in 16 categories.
- **Claims:** In-distribution win rates (2 seeds), PPO vs CGFA-PPO: Azorius Control 20.6% vs 25.6%; Boros Convoke 57.2% vs 53.3%; Dimir Midrange 52.2% vs 50.0%; Domain Ramp 20.6% vs 12.2%; Mono-Red Aggro 67.8% vs 70.6%. Transfer gap (in-distribution minus held-out): PPO −4.7 pp, CGFA-PPO −4.3 pp. The authors say CGFA-PPO does not uniformly beat PPO. Full protocol is 10^6 steps per opponent and 7 seeds; headline results use 2 seeds and 30 episodes per opponent.
- **Evaluation:** Leave-one-out cross-archetype transfer (hold out an opponent archetype). Unseen cards are not tested.
- **Code:** anonymous link (https://anonymous.4open.science/r/mtg-causal-rl-E927); no licence stated.
- **Fit:** poor for unseen cards: the card pool is fixed, and generalisation is across opponents. Useful as a reference for how a benchmark with a masked action space and a flat observation vector was reported.

### Learning to Beat ByteRL: Exploitability of Collectible Card Game Agents (2024)
- **Link:** https://arxiv.org/abs/2404.16689 (HTML: https://arxiv.org/html/2404.16689v1) · **Venue:** Adaptive and Learning Agents workshop (ALA 2024) · **Cited by:** 1 (OpenAlex) · **Read:** full text
- **Problem:** How exploitable is ByteRL, a state-of-the-art LOCM agent trained by Optimistic Smooth Fictitious Play? Can a learned best response beat it?
- **Method:** Behaviour cloning of ByteRL from about 125k self-play matches (about 3.5M state-action pairs), with pass actions filtered out. Best BC network is then fine-tuned with PPO (RLlib) on fixed deck pools of 32 to 1024 decks.
- **Assumes:** LOCM v1.5: 120 cards generated per game, 30 draft rounds, each card at most twice per deck. Battle stage only; ByteRL drafts.
- **Claims:** Best BC agent: 42.4% win rate against ByteRL over 1000 matches. Filtering pass actions: improved win rate by almost 7% (BC experiments). RL fine-tuning, average win rate by pool size (32/64/128/256/512/1024): BC pretrain 0.904 / 0.822 / 0.803 / 0.801 / 0.734 / 0.542; no pretrain 0.812 / 0.780 / 0.812 / 0.720 / 0.533 / 0.418 (five seeds).
- **Evaluation:** LOCM battle stage, varying pool size. Card-level generalisation is not tested. The per-game random card generation is the relevant setting for us, but the paper does not measure it.
- **Code:** none found in the paper. Related engines it cites: github.com/acatai/Strategy-Card-Game-AI-Competition and github.com/ronaldosvieira/gym-locm (licences not stated).
- **Fit:** partial. Shows that LOCM's per-game random card pools already force generalisation over card sets, and that pool size drives performance. It gives no unseen-card numbers.

### Improving Hearthstone AI by Combining MCTS and Supervised Learning Algorithms (2018)
- **Link:** https://arxiv.org/abs/1808.04794 (HTML: https://arxiv.org/html/1808.04794) · **Venue:** arXiv preprint (IEEE CIG 2018 version, DOI 10.1109/cig.2018.8490368 in OpenAlex) · **Cited by:** 55 (OpenAlex, CIG DOI record) · **Read:** full text
- **Problem:** Raise MCTS strength and lower its cost in Hearthstone using supervised value models.
- **Method:** Skip-gram word2vec on card text (embedding size 10, "more than 16 dimensions gave negligible improvements"; paragraph vectors also mentioned). State vector of 750 elements. Dense value network (256, 128, 64; tanh) used for early termination of simulations and to update MCTS statistics.
- **Assumes:** Hearthstone (SabberStone engine, about 10K full games per second). Training data: over 3.5M samples from MCTS bot games across 400 decks; iterated with 3,000 games per iteration, dataset capped at 1M samples (FIFO), 64 iterations. Hardware not reported.
- **Claims:** Validation accuracy 0.76 (preliminary value net); 0.775 (P1) and 0.794 (P2) after iterated learning, one deck pair only. Baseline plain MCTS: 73.5% (P1) and 26.5% (P2) at 0.5 s. Heuristics improved P1 by up to 9 points. Per-configuration table entries were unreadable in the fetch.
- **Evaluation:** Two decks only (ZooWarlock vs CubeWarlock), 500 games per configuration vs plain MCTS at 0.5 s and 1 s per move. The paper does not test cards unseen in training. It also reports a small set of games against human players.
- **Code:** none found.
- **Fit:** poor for unseen cards: no held-out cards. Useful as a reference point for word2vec on card text as a card embedding, and for a value net used inside search.

### YGO Agent (sbl1996/ygo-agent), Yu-Gi-Oh! RL platform (no paper)
- **Link:** https://github.com/sbl1996/ygo-agent (README read) · **Venue:** GitHub project, no paper · **Cited by:** n/a · **Read:** full text (README only; code not inspected)
- **Problem:** RL agents for Yu-Gi-Oh! on a fast environment (envpool + ygopro-core, gym interface).
- **Method:** Actor-learner training (cleanba.py, JAX since April 2024), with optional card-embedding file. Card text is converted to text and an LLM generates embeddings, which are stored in a file named embed{n}.pkl, where n is the number of cards in scripts/code_list.txt. Embeddings can be skipped.
- **Assumes:** Supported cards listed in a code list. Decks of supported cards "can be used, but errors may also occur due to the complexity of the game." A new card needs a new embedding file or a code-list extension. I did not confirm the "999" option that search snippets mentioned; the README did not show it.
- **Claims:** Single GTX 1650: about 1,000 steps per second. After 50 iterations (204,800 steps), eval_win_rate 0.9844 vs a random strategy. Against a model trained for "over 100M games", the 50-iteration model won 3.125% of 128 games (1.56% as first player, 4.69% as second). README also states a step gap of "nearly 60,000 times."
- **Evaluation:** Self-play and evaluation against random and a larger trained model. No held-out cards test.
- **Code:** https://github.com/sbl1996/ygo-agent · licence not stated in the README.
- **Fit:** partial. Practical example of a precomputed LLM-generated card-text embedding table used at play time as a lookup, so it does not put an LLM in the loop at play time. But it does not test unseen cards, and fresh cards need a regenerated table.

### Provincial: A kingdom-adaptive AI for Dominion (2014, practitioner page)
- **Link:** https://graphics.stanford.edu/~mdfisher/DominionAI.html · **Venue:** personal project page by Matthew Fisher (2014) · **Cited by:** n/a · **Read:** full text (web page)
- **Problem:** Strong Dominion AI for a given kingdom (set of 10 supply cards), with human-readable strategies.
- **Method:** Non-neural. A strategy is a buy menu (ordered card-count pairs) plus thresholds for Estates, Duchies and Provinces. Play uses a look-ahead heuristic with per-card parameters. Trained by generational competitive co-evolution (5 leaders, pool of 100, 32 generations).
- **Assumes:** Kingdom-specific training; about 40,000 games per second on an eight-core machine; training on a new kingdom takes "several minutes."
- **Claims:** On a sample of about 1,000 kingdoms, about five were "complex"; Wharf appeared in a top-three strategy in 28 of 30 kingdoms at normal cost, 18 of 30 at cost 6; a hypothetical Plunder in 3 of 30, rising to 10 of 30 after a buff. Page quote on untrained kingdoms: "it will make essentially random play decisions resulting in very poor performance"; "At present Provincial has to train a different strategy for each new kingdom."
- **Evaluation:** Tournaments of about 10,000 games per matchup; the page reports strategy frequencies, not held-out-card tests.
- **Code:** downloadable code and executables on the page; the page states "© 2014 Matthew Fisher. All rights reserved." No open licence.
- **Fit:** poor. It is the explicit anti-pattern for us: no generalisation to unseen kingdoms, and it has to be retrained per set. Worth citing as the non-learning baseline in Dominion.

---

## Cross-cutting notes for the survey

- **Card encodings that transferred:** text plus structured fields (Bertram 2024; DraftFM 2026). Card-text embeddings precomputed once per card (Cardsformer per abstract; Świechowski 2018 uses word2vec but tests no unseen cards). Id-only embeddings (one-hot, or a card-id table as in ygo-agent) cannot score unseen cards at all.
- **Usage statistics help a lot on unseen cards** in Bertram 2024 (33.57% to 34.74% to 42.87% with meta and image), but a brand-new card has no meta, so that gain is not available to us.
- **Held-out protocols in this angle:** leave-whole-expansion-out (DraftFM: BRO, FDN, MSH), train-on-other-sets-test-on-unseen (Bertram), leave-out-opponent-archetype (MTG causal RL), untrained-cards-in-deck (Cardsformer, abstract only). Of the papers I could read in full, only Bertram 2024 and DraftFM 2026 report numeric accuracy on unseen cards or sets. Neither is a play-time win rate.
- **LLM constraint:** UrzaGPT and the AAMAS 2025 T5 work use LLMs in the loop; ygo-agent uses an LLM only offline to generate a card-text table. Bertram and DraftFM use frozen sentence/text encoders (not LLMs), precomputed per card.
- **Gaps:** I found no peer-reviewed play-time CCG agent that reports win rates on held-out cards with a numeric protocol that I could read in full. The LOCM literature (ByteRL, procedurally generated 120-card pools per game) is the closest structural match to randomly generated content, but it does not test unseen cards.
