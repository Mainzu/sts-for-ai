# STS1 human run-log datasets and models

Scope: human Slay the Spire 1 run logs as a prior or training signal for the run layer. Cards are one per source. Stars and citations are as shown on the page; "n/a" means not shown. Nothing here was downloaded; sizes come from the pages.

Note on the 77M dump: the Reddit post (lr.eu.psf.lt mirror and reddit.com) could not be fetched, so no card is written for it. Its facts below come from the Steam announcement (opened) and from papers that cite it (opened).

---

### Patch V2.2: Happy Holidays! (Mega Crit announcement of the 77M-run dump) (2020)
- **Link:** https://store.steampowered.com/news/posts/?feed=steam_community_announcements&appids=646570&appgroupname=Slay+the+Spire&enddate=1641945124 · **Venue:** Steam news (official Mega Crit post, 29 Nov 2020) · **Cited by:** n/a · **Read:** abstract (short announcement, read through a summariser)
- **Problem:** Where the largest StS1 human run archive is and what it records.
- **Method:** None. A developer-released run archive, not a model.
- **Assumes:** Official StS1 content only. Raw run-history files; the post names no schema.
- **Claims:** The archive holds "77 million DEATHS runs of Slay the Spire", meant for questions such as "card pick rates by act and winrates at Ascension 20". About 27 GB, compiled by community moderator Jake (ilikeshiny) and pinned to the #data-analysis channel of the official Discord. The post gives no license or usage terms. Later papers (Bazzaz and Cooper 2025, below) filter on a Victory flag, so wins are in the data; the word "DEATHS" is ambiguous and I did not resolve it.
- **Evaluation:** None.
- **Code:** None found (data only). Current availability of the Discord pin, Google Drive and torrent copies was not checked.
- **Fit:** partial. The only large source that records per-floor card choices (per the other cards), but the licence is unknown, which is a redistribution risk for any shipped artefact. Win/loss mix unclear.

---

### Predicting win rate and card combinations in Slay the Spire (blog, 2020)
- **Link:** https://vegasera.github.io/2020-03-03-predicting-win-rate-and-card-combinations-slay-the-spire · **Venue:** blog (VegaSera, 2020-03-03) · **Cited by:** n/a · **Read:** full text
- **Problem:** Predict whether a run is won from its final deck, relics and Ascension.
- **Method:** Random Forest, XGBoost and RidgeClassifierCV on one-hot cards and relics, after dropping leakage fields (floor reached, playtime, score). 524 features after removing Prismatic Shard runs.
- **Assumes:** Ironclad only; seeded and endless runs excluded. Used 600 of about 32,000 JSON files. Developer data at the author's request, "about 40GB with over 50 million runs".
- **Claims:** All-fail baseline 92.5% accuracy. Validation/test: Random Forest 92.88% / 92.99%; XGBoost 93.3% / 93.3%; RidgeClassifierCV 94.26% / 94.0%. Baseline varied 88% to 93% across subsets. The author says the Random Forest result was only barely above baseline.
- **Evaluation:** Filtered Ironclad subset of the developer dump; target is win/loss.
- **Code:** Colab notebook https://colab.research.google.com/drive/1zDhfoeg9uJOAC45ZHPGLhceZT6A-Psos. No license stated. Links GitHub profile VegaSera, no repo.
- **Fit:** partial. Meets the official-content and human-data constraints, but predicts outcome rather than card decisions. Its accuracy is dominated by the 92.5% base rate, which is a useful evaluation caution.

---

### StS_predict (GitHub, Zivica) (year n/a)
- **Link:** https://github.com/Zivica/StS_predict · **Venue:** GitHub · **Cited by:** 0 stars, 0 forks · **Read:** full text (README)
- **Problem:** Predict the card a player picks, and predict floors survived, from run state.
- **Method:** XGBoost classifier, ranker and regressor (src/train.py), 5-fold CV grouped by run. Value model (src/train_value.py) predicts floors survived and picks the option whose resulting state scores highest.
- **Assumes:** Ascension 15+ for the big dump (about 120k runs, Dropbox sample from the 77M post, parsed to data/big/november.json, 619 MB, not in repo). Own 52 .run files. Features: deck, upgrades, relics, HP, floor, ascension, card picks, shop buys, purges, event changes. Neow, transforms and relic effects are not captured; rebuilt deck matches real final deck for 196 of 300 checked runs.
- **Claims:**
  - Agreement with player's pick, Asc 15+, grouped CV: popularity 0.466; XGBoost classifier 0.488 (random 0.255).
  - Value model, 216,738 screens from 21,890 runs: RMSE 11.88 floors vs 12.47 for per-floor average.
  - Simulator (sts_lightspeed), Ironclad A5, 1000 seeds, 1000 combat simulations per turn, mean floor: built-in policy 17.5; random never skip 18.4; value model trained on human data 21.5 (+3.93, 95% CI +3.21 to +4.69); value model trained on simulator data 26.7 (+9.19, 95% CI +8.43 to +9.99).
  - A10 (seeds 5000–5999): human-trained gains +3.44 (+2.76 to +4.12).
- **Evaluation:** sts_lightspeed simulator, Ironclad A5 and A10, with a built-in combat bot. The README notes the simulator-trained model was tested on the same combat bot it learned from. "Neither model is ready to give a human card advice."
- **Code:** https://github.com/Zivica/StS_predict. No license shown.
- **Fit:** partial. The only opened source that tests a human-data value model inside a simulator policy with CIs. Breaks our constraints in that the simulator is sts_lightspeed, not our engine, and the sim-trained model beat the human-trained one.

---

### slay-the-spire-hypergraph (BLOG_POST.md) (year n/a)
- **Link:** https://github.com/adithyap/slay-the-spire-hypergraph/blob/master/BLOG_POST.md · **Venue:** GitHub (blog post in repo) · **Cited by:** n/a · **Read:** full text (blog post)
- **Problem:** Predict an Ironclad/Silent/Defect/Watcher run's win from its card and relic inventory; card synergies via hypergraph network.
- **Method:** Heuristics (deck length, relic count, inventory size); Random Forest (100 trees, depth 12); XGBoost (150 trees, depth 5); L2 logistic regression on multi-hot cards; Deep MLP; Pairwise GCN; HGNN (multi-edge message passing); Set Transformer.
- **Assumes:** 12,524 unique runs after dedup (Ironclad 5,556; Silent 4,254; Defect 1,709; Watcher 1,005). Sources: Mega Crit dump batches (Asc 0–20), community repos user1–user17, jorbotz (curated Asc 20), card metadata from t22000t. Ironclad benchmark split 4,444 train / 1,112 test. Parquet fields not listed on the page.
- **Claims (Ironclad test):**

  | Model | ROC-AUC | Accuracy | F1 (wins) |
  |---|---|---|---|
  | Deck Length Only | 0.7142 | 81.7% | 0.239 |
  | Relic Count Only | 0.9206 | 85.9% | 0.531 |
  | Inventory Size | 0.9235 | 86.1% | 0.543 |
  | Random Forest | 0.9370 | 85.3% | 0.451 |
  | XGBoost | 0.9424 | 89.2% | 0.691 |
  | Logistic Regression | 0.9601 | 90.2% | 0.744 |
  | Deep MLP | 0.9553 | 90.4% | 0.753 |
  | Pairwise GCN | 0.9549 | 90.1% | 0.770 |
  | HGNN | 0.9525 | 89.8% | 0.739 |
  | Set Transformer | 0.9508 | 89.4% | 0.735 |

  The authors note relic count scores highly because end-of-run inventory tracks survival, so it is leaky. A conditional-drafting test is evaluated separately on the page; numbers not captured.
- **Evaluation:** 1,112-run Ironclad test split, end-of-run inventory as input.
- **Code:** https://github.com/adithyap/slay-the-spire-hypergraph (runs_processed.parquet, models/, scripts/pick_evaluator.py). No license stated. Underlying archives' terms not described.
- **Fit:** partial. Human and official data, and a parquet is in the repo, but the target is outcome from end-of-run state, which leaks, so it does not score decisions.

---

### LearnTheSpire (GitHub, kaijchang) (2018)
- **Link:** https://github.com/kaijchang/LearnTheSpire · **Venue:** GitHub · **Cited by:** n/a · **Read:** full text (README)
- **Problem:** Predict which card the player picks from the options offered.
- **Method:** Feed-forward TensorFlow network; cards as 1×234 vectors (card_name_to_vector.py); 100 epochs. Architecture details not given.
- **Assumes:** Local game saves on Windows or macOS (scraped by get_training_data.py). Per-character training files (Ironclad, Silent, Defect). Sample log 2018-11-19: 37 Ironclad, 1 Defect, 4 Silent runs. Only card identity as input; no deck state.
- **Claims:** Ironclad: "79.49526906013489%" agreement with the human pick after 100 epochs, final training loss about 20.55. Training and test sets are the same. Author reports near-100% at 500 epochs, which likely reflects overfitting.
- **Evaluation:** One player's local data; same-set train/test.
- **Code:** https://github.com/kaijchang/LearnTheSpire. MIT.
- **Fit:** partial. Shows per-card pick imitation is learnable from one player's data, but the metric is not held out and the data is tiny. MIT licence is a usable point. Not a deck-aware model.

---

### Part 3: Good Models Finish Last (dev.to, Doron Singer) (year n/a)
- **Link:** https://dev.to/doronsinger/part-3-good-models-finish-last-2n6a · **Venue:** blog (dev.to) · **Cited by:** n/a · **Read:** full text (read through a summariser)
- **Problem:** Does predicting human card picks better produce a better bot in StS1?
- **Method:** Four card-pick models run as the same agent over 50 seeds against a cloned expert (the post's "spirecomm" harness; not verified); card ID embeddings; mechanical features only; embeddings with propensity weighting; propensity weighting alone.
- **Assumes:** Main data is the 77M dump: 34,210 Silent runs, 358,870 card-pick decisions, A20 win rate 1.5%. 308 state features (25 card, 161 relic flags, 22 game parameters incl. floor, HP percentage, act, boss ID). Also 334 own A20 runs (41% win rate) and 53 Silent A20H runs from Jorbs (about 60%). Silent only.
- **Claims:**
  - Offline accuracy on human picks, in-game rank, beat/lost/tied vs expert:
    - Embeddings: 55.8%, 4th, 12/23/15
    - Mechanical features: 53.5%, 1st, 16/16/18
    - Embeddings + propensity: 52.3%, 3rd
    - Propensity: 49.5%, 2nd
  - Central claim: better human-pick accuracy does not mean better play; human picks carry systematic biases. The best learned model still lost to the hand-crafted bottled AI tier list.
- **Evaluation:** 50 seeds, same agent, cloned expert. Game-in-loop, not an offline engine.
- **Code:** none found; no license stated.
- **Fit:** good for the question "does human data pay". It measures imitation accuracy and play separately and finds they diverge. Breaks constraints in that its agent runs in the real game through a communication harness, not our engine.

---

### sts-card-choice-analysis (GitHub, brent-smith-4) (year n/a; 2019 game)
- **Link:** https://github.com/brent-smith-4/sts-card-choice-analysis · **Venue:** GitHub · **Cited by:** n/a · **Read:** full text (README)
- **Problem:** Effect of card-reward choices on floors gained and victory.
- **Method:** Dagster + PySpark + Delta Lake ETL (bronze runs, silver picks and card offers with was_picked, gold tables). Per-card logistic regression (analysis/win_rate_modeling.py; the notebook that uses it is listed as unfinished). LightGBM for floor progression is mentioned only in the About text.
- **Assumes:** Standard runs only. Python 3.13+, JDK 17, local run. Raw data gitignored (not shipped). README gives the dump as "~77 million runs"; About says "7 million player runs across 5000+ jason.gz files". Not reconciled.
- **Claims:** None measured. No accuracy, AUC, coefficients or sample sizes given. Status "In progress".
- **Evaluation:** None reported.
- **Code:** https://github.com/brent-smith-4/sts-card-choice-analysis. No license file.
- **Fit:** partial. Its field list is the most explicit of the set: card reward choices made and declined per floor, HP, relic and gold history, outcome, character, ascension. Nothing measured.

---

### rrenaud/slay_analysis (GitHub, rrenaud) (year n/a; 2020 logs)
- **Link:** https://github.com/rrenaud/slay_analysis · **Venue:** GitHub · **Cited by:** 0 stars, 0 forks, 11 commits · **Read:** full text (README; notebooks not opened)
- **Problem:** Exploratory analysis of run logs, limited to Defect.
- **Method:** log_preprocessor.py builds per-fight deck info; Jupyter notebooks (slay_analysis.ipynb, DataExploration.ipynb). Links to model output pages with no metrics in the fetched text.
- **Assumes:** Defect only. Needs Monthly_20_10 and Monthly_2020_11 datasets from Google Drive, extracted to raw_logs/. Ships cards_2020_11_14.json and relics_2020_11_14.json (fields not described).
- **Claims:** None measured.
- **Evaluation:** None.
- **Code:** https://github.com/rrenaud/slay_analysis. No license shown.
- **Fit:** poor. A pointer to the Google Drive monthly log files, not a model; Defect only.

---

### jorbotz (GitHub, mlucy) (year n/a; 2019 runs)
- **Link:** https://github.com/mlucy/jorbotz · **Venue:** GitHub · **Cited by:** 0 stars, 1 watcher, 24 commits · **Read:** full text (README and repo summary)
- **Problem:** A card picker trained on one player's (Jorb's) runs.
- **Method:** Logistic regression (logistic.model, train.py). Pipeline: reformat_run.py, vectorize.py, train.py, play.py, run_all.sh. No instructions in README.
- **Assumes:** One player; 2019SpireRuns folder. Sample .run file has about 58 per-run fields, including card_choices, master_deck, path_taken, floor_reached, current_hp_per_floor, gold_per_floor, relics, victory, score, ascension_level.
- **Claims:** None measured. win_rate appears only as a sample field name.
- **Evaluation:** None.
- **Code:** https://github.com/mlucy/jorbotz. No license stated.
- **Fit:** partial. Its sample field list is the clearest example of per-floor HP, path and card-choice logging. Single player; no metrics.

---

### Are You Lucky or Skilled? An Analysis of Elements of Randomness in Slay the Spire (IEEE CoG, 2023)
- **Link:** https://api.openalex.org/works/doi:10.1109/COG57401.2023.10333231 (DOI 10.1109/CoG57401.2023.10333231) · **Venue:** IEEE Conference on Games 2023 · **Cited by:** 2 (OpenAlex) · **Read:** abstract (OpenAlex record; PDF at aeau.github.io was unreadable binary)
- **Problem:** How randomness in the game relates to player skill.
- **Method:** Data clustering into three skill groups: Winners, Low skill losers, High skill losers.
- **Assumes:** Subset of the developer dump (per a second paper's summary).
- **Claims:** "people who succeeded in beating the game, had an increased amount of randomness in the form of cards by a factor of 1.82". Skilled players "embrace it more than lower skilled players."
- **Evaluation:** Developer-dump subset; clustering analysis, no predictive model.
- **Code:** none found.
- **Fit:** partial. Descriptive statistics on card randomness by skill; not a policy or model.

---

### Analysis of Uncertainty in Procedural Maps in Slay the Spire (arXiv 2504.03918, Bazzaz and Cooper, 2025)
- **Link:** https://arxiv.org/html/2504.03918v1 · **Venue:** arXiv (FDG 2025 per search snippets) · **Cited by:** n/a · **Read:** full text (arXiv HTML)
- **Problem:** Entropy of map locations and how it differs by outcome and skill.
- **Method:** Map oracle reconstructs maps from seeds; location entropy from wiki probability tables; Welch t-tests.
- **Assumes:** Ironclad, Ascension mode; excludes trial, daily, beta, endless and chosen-seed runs. 20,000 runs sampled from the 77M dump. Fields used: Victory, Ascension level, Seed, Path taken. No card-pick data analysed. Paper does not report how many runs were dropped on map mismatch.
- **Claims:**
  - Normalized entropy, victory vs defeat: all acts t = −64.63 (p < 0.001); Act 1 t = −1.14 (p = 0.25, not significant); Act 2 t = −39.70; Act 3 t = −87.78.
  - Skill (levels ≤10 vs >10): all acts t = 14.12; Act 1 t = 1.93 (p = 0.053).
  - Location entropies (bits): Act 1 first three monster encounters 2; rest of monster encounters 3.265; first elite 1.58; boss 1.58; shop 0; rest sites 0.
- **Evaluation:** 20,000 Ironclad Ascension runs.
- **Code:** none stated.
- **Fit:** partial. Confirms the dump records paths and seeds; no card picks, no model trained on humans. Useful for map-level statistics only.

---

### MaT1g3R/Slay-the-Spire-data (GitHub) (year n/a)
- **Link:** https://github.com/MaT1g3R/Slay-the-Spire-data · **Venue:** GitHub · **Cited by:** 12 stars, 0 forks, 11 commits · **Read:** full text (README and repo summary)
- **Problem:** Report generator over StS1 run-history folders, plus a set of small human run sets.
- **Method:** analyze/analyze.py takes a run-history folder and writes reports. No model.
- **Assumes:** Python 3.10; "Run history plus" Steam mod recommended (untested without it). Data from streamer vmService and other streamers with permission.
- **Claims:** None measured. Sets: 200-run rotating sample; "Lose all gold for max HP" sample; 50 Bad Silent games; panacea108 Ironclad sample; Robit (50 Defect runs). Total run count, field list, and whether card picks, HP per floor, paths or combat logs are included were not stated.
- **Evaluation:** None.
- **Code:** https://github.com/MaT1g3R/Slay-the-Spire-data. Apache-2.0. Data sets stored under results/.
- **Fit:** partial. Permissive licence and small human sets that are in the repo. Field coverage not confirmed.

---

### spire-ai (GitHub, andrewshooman) (year n/a)
- **Link:** https://github.com/andrewshooman/spire-ai · **Venue:** GitHub · **Cited by:** n/a · **Read:** full text (README and repo summary)
- **Problem:** Self-learning StS1 bot that learns choice weights from its own and others' runs.
- **Method:** REINFORCE on choice weights (card picks and skips, path, rest vs smith, shop, boss relics); evolution strategies for planner combat parameters; whole-turn planner (planner.py). Optional LLM (Ollama) for events, Neow, boss relics and coaching.
- **Assumes:** Windows; Python 3.11+; Communication Mod with ModTheSpire, BaseMod. Expert data: 565 A20 runs from the vmService Slay-the-Spire-data set (Ironclad 157, Silent 156, Defect 156, Watcher 96), imported at weight 0.1 for card picks and boss relics, not rest choices. Combat is not learned from human runs.
- **Claims:** No performance figures reported on the page (no win rate or boss-kill rate).
- **Evaluation:** Explore and bench runs on fixed seeds, run in the real game.
- **Code:** https://github.com/andrewshooman/spire-ai. No license stated.
- **Fit:** partial. A working example of human runs as a low-weight prior with combat kept separate. Optional LLM use conflicts with the no-LM constraint; the LLM is not required for the core picks.

---

### Slay-I (fight predictor) (GitHub, alexdriedger; project summary page) (year n/a)
- **Link:** https://slaythespire.dev/projects/slay-i/ (repo: https://github.com/alexdriedger/SlayTheSpireFightPredictor) · **Venue:** community project page (slaythespire.dev) · **Cited by:** n/a · **Read:** abstract (summary page; repo not opened)
- **Problem:** Predict damage taken in a fight; score card picks by damage saved.
- **Method:** Neural network in a Jupyter notebook; architecture not stated.
- **Assumes:** Over 325,000 fights. Whether these are human or simulated fights, and the recorded fields, are not stated.
- **Claims:** None measured reported.
- **Evaluation:** None reported.
- **Code:** https://github.com/alexdriedger/SlayTheSpireFightPredictor. License not stated. Dormant per the summary; shipped as a Steam Workshop mod.
- **Fit:** poor to partial. A fight-damage model could be a combat prior, but its provenance is unknown and it has no metrics.

---

## Not opened (for the next review)
- Reddit "77 million runs, an STS metrics dump" (r/slaythespire, 12 Nov 2020). reddit.com was blocked and the lr.eu.psf.lt mirror failed with an SSL error. Its hosting (Google Drive, Internet Archive, torrent) and the "27GB / 90GB raw JSON / 77GB SQLite" counts come from search snippets only.
- Edinburgh UG4 project (project-archive.inf.ed.ac.uk/ug4/20233951/ug4_proj.pdf): PDF exceeded the fetch size limit.
- Carleton University honours project (service.scs.carleton.ca/node/6275): found in search, not opened.
- Out of scope (StS2, not StS1): Spire Codex, STS Tracker, Scry, Untapped, MetaBot, sts2-advisor, sts2-card-advisor, STS2FableBot, spirescope.
- Tools that read StS1 .run files, not opened: itsseanl/stsRunViewer, casey-c/spiretool.
