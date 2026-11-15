# Variance reduction for agent strength measurement: cards

Scout angle: variance reduction for measuring agent strength in high-variance games (AIVAT/DIVAT, duplicate formats, control variates, common random numbers, SPRT). Eight papers opened, all eight with full text (HTML). Citation counts come from OpenAlex where the work was in the OpenAlex results; "not checked" otherwise.

---

### AIVAT: A New Variance Reduction Technique for Agent Evaluation in Imperfect Information Games (2018)
- **Link:** https://arxiv.org/html/1612.06915 (arXiv 1612.06915v2; AAAI 2018 proceedings: https://ojs.aaai.org/index.php/AAAI/article/view/11481) · **Venue:** AAAI 2018 (the arXiv page itself names no venue) · **Cited by:** 15 (OpenAlex, W2562174057) · **Read:** full text
- **Problem:** Evaluating agents whose outcomes come from chance and randomized strategies needs many samples, which is costly for human opponents.
- **Method:** An unbiased estimator: a base value (importance-sampled over imaginary observations that share opponent reach probabilities) plus MIVAT-style chance correction terms E[u(a)] − u(o) and action correction terms that compare the expected value before a player's choice with the value after it. Any heuristic value function u_h can be used.
- **Assumes:** Imperfect-information game with a set P_a of players (including chance) whose strategies are known; the rest may be unknown. Opponent reach probabilities must match within each state partition. The value function can be arbitrary; better values only reduce variance, unbiasedness holds regardless. Outcomes are chip counts or game payoffs.
- **Claims:** Unbiased (Lemma 1, Theorem 1). Leduc self-play, chip-count std 3.513, AIVAT with P_a={p_c,x} std 0.00643 ("about 99.8%" reduction); Leduc dissimilar strategies, chip-count std 5.761, AIVAT std 1.437, mean 0.69050 vs true 0.69358. No-limit hold'em self-play: chip-count std 25.962, MIVAT 21.293, MIVAT+IOx 16.073, AIVAT 8.095 ("about 68.8%" reduction). No-limit dissimilar strategies: chip-count std 26.308, AIVAT 8.301 (about 68%). Abstract: "more than a factor of 10" fewer hands; the body says about threefold std reduction, ten times less data.
- **Evaluation:** Heads-up Leduc hold'em and heads-up no-limit Texas hold'em, self-play and dissimilar-strategy matchups, with exact true values for Leduc.
- **Code:** none found (not checked)
- **Fit:** partial. The estimator needs known action distributions for every agent we want to correct, and a value function queried from a net or heuristic. Our bots' policies and our value nets would have to meet both; the paper's gains are for two-player hidden-information games, and the Slay the Spire setting is single-player with seeded randomness, which the paper does not cover.

---

### AV-AIVAT: 74x Cheaper Agent Evaluation with Certified Anytime-Valid Stopping in Imperfect-Information Games (2026)
- **Link:** https://arxiv.org/html/2608.06362 · **Venue:** arXiv preprint (Aug 2026; authors Boning Li, Yu Chen, Longbo Huang) · **Cited by:** 0 (OpenAlex, W7201853435) · **Read:** full text (first 100,000 of 154,691 characters; the rest was not read)
- **Problem:** Deciding that one agent beats another needs many games; a fixed budget overspends or stops too early, and a naive stop-at-first-favourable-look breaks the stated error level.
- **Method:** Combines AIVAT with confidence sequences valid under continuous monitoring (AsympCS, and an exact Empirical-Bernstein CS, EB-CS). The value model may be refit during evaluation, but the correction for hand t uses a value fixed before hand t is observed.
- **Assumes:** Correction nodes have a known conditional action distribution, and the decision to correct is fixed before the action is observed. The value function for hand t is measurable with respect to earlier data. EB-CS exact validity needs a declared almost-sure bound on corrected payoffs; in HUNL that bound is data-derived, so only the Leduc result is exact. AsympCS needs a conditional Lindeberg condition and a nondegenerate limiting variance; its tuning was set on a calibration split and frozen.
- **Claims:** HUNL, 15 runs (71,439 paired hands): variance ratio raw to AIVAT median 54.4x (range 24.2–86.0x). AsympCS stopping-time ratio at ±1 BB, 95% level: median 74.17x (range 54.53–97.62x). EB-CS ratio at ±1 BB: median 1.365x (range 1.235–1.556x, 14 evaluable runs). At ±0.5 BB all 15 raw AsympCS streams were censored at 4,028–5,000 hands; the AIVAT AsympCS median was 56.5 hands (range 42.5–71). Leduc (exact truth): variance ratio 8.08x; across 400 replications EB-CS excluded the exact mean in 2 raw streams and 0 AIVAT streams.
- **Evaluation:** LLM agents heads-up no-limit hold'em, 15 configurations with paired hands; Leduc hold'em for exact checks.
- **Code:** none found (the paper says a release protocol publishes the corrected prefix and settings; not checked)
- **Fit:** partial. The stopping idea fits our job (decide early when a comparison is clear), and the variance ratios are the most recent measured numbers. But the 74x is measured in hands to reach a precision target on a two-player game; it does not carry over to single-player fights. The method needs the same known-policy and value-function inputs as AIVAT.

---

### Heuristic Pathologies and Further Variance Reduction via Uncertainty Propagation in the AIVAT Family of Techniques (2026)
- **Link:** https://arxiv.org/html/2605.14261 · **Venue:** arXiv preprint (May 2026; Juho Kim, Tuomas Sandholm) · **Cited by:** 0 (OpenAlex, W7161304085) · **Read:** full text
- **Problem:** A heuristic value function fitted to the evaluation data can produce fake low variance and fake significance (win and loss both significant on the same data).
- **Method:** Propagates the uncertainty of the heuristic into each AIVAT-style estimate (variance c(z)ᵀΣc(z)) and averages estimates with inverse-variance weights.
- **Assumes:** Estimates are i.i.d.; weights independent of the data for unbiasedness (in general bias about Cov(w, v̂)/E[w]); heuristic outputs uncorrelated in the simplified form. The heuristic must be fixed before the evaluation data is observed. Action probabilities unknown in the Pluribus case, so only MIVAT is used there.
- **Claims:** Pluribus data, 10,000 hands, MIVAT-GPR, inverse-variance weighting vs uniform: standard error 75 vs 99 mbb/h (about 24.5% lower; "roughly a 43.0% reduction in hands"). Estimated IVW bias about 3 mbb/h, 10-fold CV with 1,000 hands per training subsample. MIVAT-BR and MIVAT-ARDR: standard error 74 vs 83 mbb/h, but estimated bias about 80 mbb/h, so those IVW estimates are not reliably unbiased. The authors concede the unbiasedness guarantee may have to be given up.
- **Evaluation:** Pluribus poker logs (10,000 hands); not reproducible without the logs.
- **Code:** none found (not checked)
- **Fit:** partial. The warning is directly useful: do not fit the value net on the same fights you then score. The weighting idea costs unbiasedness, which we may not want for a release number. Two-player poker data only.

---

### Seeding for Success: Skill and Stochasticity in Tabletop Games (2025)
- **Link:** https://arxiv.org/pdf/2503.02686 (read via the arXiv HTML route: https://arxiv.org/html/2503.02686) · **Venue:** arXiv preprint (the PubID line credits IEEE 2024) · **Cited by:** not checked · **Read:** full text
- **Problem:** Measuring how much randomness in a game shapes results, and whether mirrored seeds reduce the noise in comparing players or agents.
- **Method:** Mirrored seeds: each seed is played twice with the two players swapped, so each player takes each seat on the same starting state. The mirrored pair is correlated, so it is not a Binomial(2, p) sample.
- **Assumes:** Two-player game; identical agents (the derivation); draws are ignored for simplicity; each agent plays from every seat, otherwise first-player advantage confounds the comparison.
- **Claims:** Table I, 500 mirrored seed pairs (1,000 games) vs 1,000 single seeds (1,000 games), per-game variance (max 0.250): Dots and Boxes 0.247 single vs 0.247 mirrored; Dominion 0.249 vs 0.243; Hearts 0.222 vs 0.196; Poker 0.249 vs 0.113 (95% interval 6.2% vs 3.5%). Most games narrow the 95% CI by only about 0.1–0.4%. The variance reductions are post hoc upper bounds. The paper's text and Figure 2 caption disagree on the seed count (200 vs 100).
- **Evaluation:** 15 tabletop games; Table I shows the per-game numbers above. Poker is the one game where mirroring matters most.
- **Code:** none found (not checked)
- **Fit:** good for the seed design. Mirroring is the paired-seed idea applied to two sides; the single-player analog is the same seeded fight run with two bots, which we can do since we control seeds. The gain is game-specific (small except in poker), so we should measure it on our fights rather than assume it.

---

### When Does Pairing Seeds Reduce Variance? Evidence from a Multi-Agent Economic Simulation (2025/2026)
- **Link:** https://arxiv.org/html/2512.24145 · **Venue:** arXiv preprint (cs.LG; v3 dated 31 Jan 2026; author Udit Sharma) · **Cited by:** not checked · **Read:** full text
- **Problem:** Comparing two systems on a seeded, learning-based simulator is noisy; does evaluating both under shared seeds reduce variance, and when?
- **Method:** Paired evaluation: same seed for both regimes, average the within-seed differences. Var(Δ̂_pair) = Var(Δ̂_ind) − (2/n)·Cov(Y(1,s), Y(0,s)). SE_pair = SE_ind × √(1 − 2ρσ₁σ₀/(σ₁²+σ₀²)); effective sample size r_eff = r·(σ₁²+σ₀²)/(σ₁²+σ₀²−2ρσ₁σ₀), which is about r/(1−ρ) when σ₁²≈σ₀².
- **Assumes:** Outcomes square-integrable; seeds fully determine all randomness; seeds independent across pairs; fixed compute budget (one pair = two runs). Gains need non-negative seed-level correlation ρ; at ρ≈0 pairing equals independent evaluation; negative ρ can make pairing worse.
- **Claims:** Case study: 22 paired seeds (44 runs), TaxAI-style economy. Seed-level correlations for final metrics: ρ(GDP)=0.917 and ρ(Wealth Gini)=0.681 under the GDP objective; the GDP–Gini objective gives ρ=0.993 and 0.963; the Gini objective gives 0.951 and 0.910. Wealth Gini effect −0.039 with paired 95% CI [−0.052, −0.027] vs independent [−0.097, 0.018]. The paper reports no p-values and no numeric ESS values.
- **Evaluation:** Extended learning-based economic simulator with a UBI tax instrument; 22 paired seeds.
- **Code:** none found (not checked)
- **Fit:** good. The rule "measure the seed-level correlation first; pairing only helps when it is positive" is what we need to check on our own fights. The paper's ESS formula gives a direct way to convert a measured ρ into a run-count saving. Not a game paper, so the numbers are not transferable.

---

### Empirically Evaluating Multiagent Learning Algorithms (2008 manuscript; arXiv 2014)
- **Link:** https://arxiv.org/html/1401.8074 · **Venue:** arXiv (Zawadzki, Lipson, Leyton-Brown, UBC; manuscript dated 15 Nov 2008) · **Cited by:** not checked · **Read:** full text (first 100,000 of 143,485 characters; the rest was not read)
- **Problem:** Past multiagent learning experiments were too small to say which algorithm really performs well; the paper asks how to evaluate many runs under a fixed CPU budget.
- **Method:** Testbed MALT. Chooses more game instances and algorithms over more runs per match. Describes each match by the empirical distribution of a metric across runs. Bootstrap confidence intervals from one experiment (subsample half the data with replacement, about 2,500 repeats, 95% percentile intervals). KS test (α=0.05) for distribution differences; a visual stochastic-dominance check on quantile functions.
- **Assumes:** Two-player repeated bimatrix games with rewards normalised to [0, 1]; no stochastic games; each match run once; stratifying on game instances is not needed for the variance of summary statistics (Appendix A).
- **Claims:** 600 game instances, 11 algorithms, 72,600 matches, each run once; 100,000 iterations per run, last 10,000 recorded; 143 GB of data and "about a third of a CPU-year". Validation: a reimplementation differed from the original on 3 of 10 instances (KS test, α=0.05).
- **Evaluation:** GAMUT generators and 2×2 games (D13); not a Slay the Spire style benchmark, but a worked example of CPU-budgeted study design.
- **Code:** MALT (not checked)
- **Fit:** partial. The bootstrap-from-one-experiment method and the stance "more instances over more runs" fit a fixed CPU budget. Its setting (repeated matrix games, 2008 era) does not match ours, and it does not give a variance-reduction technique.

---

### GTO Wizard Benchmark (2026)
- **Link:** https://arxiv.org/html/2603.23660 · **Venue:** arXiv preprint (Mar 2026; Provost, Ilenic, Solinas, Beardsell, GTO Wizard) · **Cited by:** 0 (OpenAlex, W7140677459) · **Read:** full text
- **Problem:** A public, standard evaluation for LLM poker agents against a strong baseline, with luck removed from the score.
- **Method:** AIVAT scoring, reporting a "Chance Correction" (card luck) and an "Action Correction" (luck from the baseline's actions) separately; each LLM gets 5,000 hands.
- **Assumes:** Heads-up no-limit hold'em, 50/100 blinds, 200 BB stacks reset to 20,000 before each hand. The paper does not state AIVAT's assumptions (known strategies, value function) or describe a paired design.
- **Claims:** GTO Wizard AI beats Slumbot by 19.4 ± 4.1 bb/100. Abstract: AIVAT gives "equivalent statistical significance with ten times fewer hands than naive Monte Carlo evaluation"; Section 3: "a threefold reduction in standard deviation, resulting in the same statistical significance with 10 times less data." The experimental conditions behind the ten-times figure are not given.
- **Evaluation:** Heads-up no-limit hold'em, 5,000 hands per LLM; Slumbot comparison with 150,000 hands.
- **Code:** public API described (not checked)
- **Fit:** partial. Confirms AIVAT's reported size in a second, recent setting, but it is a benchmark paper with thin method detail; the ten-times figure is not reproducible from the text.

---

### Empirical Design in Reinforcement Learning (2023, v2 Oct 2024)
- **Link:** https://arxiv.org/html/2304.01315 · **Venue:** arXiv preprint (Patterson, Neumann, M. White, A. White; University of Alberta) · **Cited by:** not checked · **Read:** full text (first 100,000 of 232,156 characters; the rest was not read, including the comparison section)
- **Problem:** Many RL experiments lack the statistical evidence their claims need; the paper is a guide to sound comparisons.
- **Method:** Recommends bootstrap intervals as the default for most comparisons, after checking distributions. Warns that 5 runs is almost never enough. Separates confidence intervals (shrink with runs) from tolerance intervals (do not shrink). For hyperparameter sweeps, a bootstrapped two-stage procedure can cut runs per setting (e.g., 10 instead of 30) by resampling across configurations.
- **Assumes:** Roughly Gaussian performance for Student-t intervals; heavy-tailed performance needs bootstrap; each agent's variation comes from seeds (agent initialisation and environment stochasticity).
- **Claims:** PuddleWorld DQN: about 5% of runs have a long low-performance tail; 10 runs misjudge mean and spread; about 20 runs were enough for accurate bootstrap intervals and about 30 for the mean. Percentile bootstrap needed about 30 runs to detect differences, Bernstein up to 1,000. Student-t multipliers at α=0.05: 4.303 (n=3), 2.262 (n=10), 1.962 (n=1000). Bootstrap uses about m=10,000 resamples.
- **Evaluation:** Tabular maze (E-Sarsa, 30 agents), Mountain Car (DQN, 50 runs), PuddleWorld (DQN).
- **Code:** none found (not checked)
- **Fit:** good for the statistics. Gives the reporting rules (bootstrap, run counts, do not report standard errors) without any variance-reduction technique. Its paired-comparison advice sits in the section that was cut off, so it is not verified here.

---

## Notes for the lead (not cards)

- **Numbers check:** A search summary said AIVAT gives "85% std reduction" and "44 times fewer games". I did not find those numbers in the paper. The paper gives about 68.8% (no-limit self-play), 99.8% (Leduc self-play), and a factor of 10 in hands. Use the paper's numbers.
- **Not opened, leads only:** Fishtest's SPRT (the Stockfish test framework, FAQ at https://github.com/official-stockfish/fishtest/wiki/Fishtest-faq) is the common sequential stopping rule for engine comparisons and uses paired "pentanomial" statistics per game pair; it is not on a card because I did not open the page. Also not opened: a 2019 AAAI paper on VR-MCCFR baselines (OpenAlex W2964934024, 46 citations), which is a control-variate idea for CFR, not evaluation.
- **Duplicate formats:** The search found only secondary mentions (bridge duplication, duplicate poker). No duplicate-format paper was opened. The TU Delft bridge paper and the 1995 duplicate-tournament paper were not opened.
- **OpenAlex fetch:** the abstract text came back summarised, not raw, so the OpenAlex abstract was not used for any card.
