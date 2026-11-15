# Cards: ADP / OR angle (post-decision value functions, decision-focused learning, ranking vs regression)

Scout angle: approximate dynamic programming in operations research. Problem context: StS1 one-turn expectimax over afterstates, Deep Sets value net trained by regression on final outcomes; search with it plays no better than heuristic.

Opened: 10 papers. Full text (read, possibly partial): 4. Abstract only: 6.
"Cited by" was not checked for any paper (no OpenAlex count pulled).
"Code" was not searched for any paper, so each card says "not checked".

---

### Smart "Predict, then Optimize" (2017)
- **Link:** https://arxiv.org/abs/1710.08005 · **Venue:** arXiv preprint (math.OC); a Berkeley IEOR listing gives Management Science (forthcoming) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Models trained to minimise prediction error ignore how their predictions feed a downstream optimisation.
- **Method:** Defines the SPO loss (decision error a prediction induces). Derives a convex surrogate, SPO+, using duality. Trains linear models with SPO+ and compares them to random forests.
- **Assumes:** Linear objective in the predicted quantities; polyhedral, convex or mixed-integer feasible set; a known downstream optimisation model that can be solved at training time.
- **Claims:** Abstract gives no numbers. Qualitative: "significant improvement" on shortest path and portfolio problems, particularly when the model is misspecified. Linear SPO+ models "tend to dominate random forest algorithms, even when the ground truth is highly nonlinear." Consistency with respect to SPO loss "under mild conditions." The abstract does not say SPO+ upper-bounds SPO loss (a search snippet said so; not confirmed).
- **Evaluation:** Shortest path and portfolio optimisation. Grid size and portfolio setup are not on the abstract page.
- **Code:** not checked
- **Fit:** partial. The decision-error loss is the clearest statement of "train on the decision, not the prediction", which matches the regression-vs-decision gap. It needs a linear objective over a known feasible set; whether StS's discrete argmax over enumerated afterstates can be written that way needs checking.

---

### Decision-Focused Learning: Foundations, State of the Art, Benchmark and Future Opportunities (2023)
- **Link:** https://arxiv.org/abs/2307.13565 (text read from https://ar5iv.labs.arxiv.org/html/2307.13565) · **Venue:** arXiv (journal header "Vol. 1 (2023)") · **Cited by:** not checked · **Read:** full text, first ~100k of ~274k characters
- **Problem:** Review of training predictors so that the decisions they produce are good, rather than the predictions being accurate.
- **Method:** Taxonomy of DFL methods: (1) analytical differentiation of optimisation mappings; (2) analytical smoothing of mappings; (3) smoothing by random perturbations; (4) differentiation of surrogate losses. Also lists "DFL without optimization in the loop" as a fifth category.
- **Assumes:** Downstream optimisation problems that a solver can handle. Each training sample needs a solve and a differentiation every epoch, which the paper calls more computationally expensive.
- **Claims:** Two-stage training "assumes that better predictions yield better decisions" and the paper argues this "often fails". Stated condition: DFL helps when prediction errors change the optimal decision. In a two-item knapsack example, two predictions with the same squared error give different regret. No benchmark numbers were in the part read; the benchmark results are in the unread second part (second read at offset 100000 did not reach them).
- **Evaluation:** Says it benchmarks seven problems from public datasets and compares eight DFL methods. Example problem types in the intro: shortest path, bipartite matching, sorting and ranking, top-k, knapsack, TSP, combinatorial portfolio, energy-cost-aware scheduling.
- **Code:** not checked
- **Fit:** partial. Good vocabulary and the "prediction error does not equal decision error" argument. No game or RL benchmark, and the results section was not read.

---

### Analysis of Classification-based Policy Iteration Algorithms (2016)
- **Link:** https://jmlr2020.csail.mit.edu/papers/v17/10-364.html (jmlr.org itself was refused by WebFetch; this mirror worked) · **Venue:** JMLR 17(19):1–30 · **Cited by:** not checked · **Read:** abstract (the PDF at the same host, /papers/volume17/10-364/10-364.pdf, returned binary to WebFetch and was not read)
- **Problem:** Policy improvement by classifying the greedy action, rather than regressing action values.
- **Method:** Classification-based policy iteration. Each classifier mistake is weighted by its regret, the gap between the greedy action's value and the chosen action's value. Action values are estimated by rollouts under the current policy.
- **Assumes:** A simulator for rollouts at every iteration. A hypothesis space for the classifier. Discounted MDP setting (implicit in "policy iteration"). Finite samples.
- **Claims:** Finite-sample bound depends on the number of policy-improvement steps, rollouts per iteration, the capacity of the policy space, and how well that space approximates greedy policies; it "reveals a tradeoff between estimation and approximation error." Says the approach "could be favorably compared to value-based approaches" "when the policies can be approximated more easily than their corresponding value functions." No experiments on the abstract page.
- **Evaluation:** None on the abstract page.
- **Code:** not checked
- **Fit:** partial. Directly answers "regret-weighted action classification vs value regression". It breaks a constraint if rollouts from the current policy are too costly, which for StS means many full simulated combats per iteration, and the bound is in terms the abstract does not quantify.

---

### Value-Aware Loss Function for Model-based Reinforcement Learning (2017)
- **Link:** https://proceedings.mlr.press/v54/farahmand17a.html · **Venue:** AISTATS 2017, PMLR 54:1486–1494 · **Cited by:** not checked · **Read:** abstract (main PDF at http://proceedings.mlr.press/v54/farahmand17a/farahmand17a.pdf, not read)
- **Problem:** Learning a transition model with a probabilistic loss ignores the value-based decision algorithm that will use the model.
- **Method:** Loss that "takes the structure of the value function into account". A model is scored by how well it supports accurate value estimates, instead of by how well it predicts next states.
- **Assumes:** Model learning for an MDP with a value function class; finite samples.
- **Claims:** Finite-sample upper bound on the loss with terms for model approximation error, number of samples, and complexity of the model space (rate not on the page). Compared with maximum likelihood "on a simple problem"; no numbers on the page.
- **Evaluation:** Not stated on the page.
- **Code:** not checked
- **Fit:** poor. It learns a transition model, while our net is a value function over afterstates, and it does not address generalisation to unseen cards. The principle ("score the learned object by its effect on downstream decisions") still transfers.

---

### Lessons from AlphaZero for Optimal, Model Predictive, and Adaptive Control (2021)
- **Link:** https://arxiv.org/abs/2108.10315 · **Venue:** arXiv (v2 withdrawn; a book-format version from 2022 exists, not read) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Why on-line lookahead on top of imperfect off-line value approximations works.
- **Method:** "Approximation in value space" with lookahead minimisation over an approximate terminal cost, plus rollout. The abstract says these ideas apply to deterministic and stochastic optimal control, with discrete and continuous search spaces.
- **Assumes:** Optimal-control setting with a model; discrete or continuous search.
- **Claims:** Qualitative only. The abstract attributes AlphaZero's on-line advantage to lookahead correcting imperfections in the off-line player and its terminal cost approximation. No explicit suboptimality bound in terms of value-approximation error appears on the abstract page.
- **Evaluation:** None on the abstract page.
- **Code:** not checked
- **Fit:** partial. Speaks to "lookahead over imperfect values", which is what our expectimax does. Gives no quantitative guarantee on the abstract page, and the book version was not read.

---

### The Central Role of the Loss Function in Reinforcement Learning (2024, rev. 2025)
- **Link:** https://arxiv.org/abs/2409.12799 · **Venue:** arXiv; the comments field says accepted to Statistical Science · **Cited by:** not checked · **Read:** abstract
- **Problem:** Which regression loss for value learning gives better sample efficiency.
- **Method:** Theory comparing binary cross-entropy (BCE) with squared loss for value-based RL and cost-sensitive classification. Also covers distributional RL with a maximum-likelihood loss.
- **Assumes:** Not stated on the abstract page (function class, realisability and coverage are not given there).
- **Claims:** BCE gives "first-order bounds that scale with the optimal policy's cost", described as "much more efficient" than squared loss. Distributional RL with maximum-likelihood loss gives second-order bounds that scale with the policy's variance. No empirical numbers on the abstract page.
- **Evaluation:** None on the abstract page.
- **Code:** not checked
- **Fit:** partial. Relevant because our net is trained on final outcomes and the loss is a free choice, but the theory is for RL with function classes, not values used inside a search.

---

### Rectifying Regression in Reinforcement Learning (2025)
- **Link:** https://arxiv.org/html/2510.00885 (arXiv 2510.00885v2, Nov 2025) · **Venue:** arXiv · **Cited by:** not checked · **Read:** full text (HTML, read through the summariser; the answer covered the main claims and experiments)
- **Problem:** Squared-error regression for value-based decisions over-weights rare contexts and does not align with the action-suboptimality objective.
- **Method:** Replaces squared loss with log-loss (binary cross-entropy) or a reparameterised categorical loss ("cat-loss"), inside fitted Q-iteration.
- **Assumes:** Batch setting; linear function class with Fourier features; data from a uniform-random policy. The log-loss bound is written in terms of (1 − v⋆), which suggests values in [0,1] (my inference, not checked against the paper's exact setup).
- **Claims:** Log-loss bound scales with (1 − v⋆) when the optimal value is near the maximum. In a constructed two-context example, squared-loss estimator has MAE of order 1/√n even when v⋆ is near 1, while log-loss can reach roughly 1/n. Experiments with order-2 Fourier features: log-loss and cat-loss outperform squared loss. With order-3 features, all three perform similarly, and log-loss learns fastest. Cat-loss is more sensitive to ℓ2 regularisation and to the number and spacing of bins.
- **Evaluation:** Inverted pendulum, batch linear FQI, Fourier features of order 2 and 3. 45 independently collected datasets. Metric: failure rate of the learned policy after 3000 steps, with 90% confidence intervals.
- **Code:** not checked
- **Fit:** partial. Addresses the same gap (regression accuracy vs decision quality) and uses a decision metric, with bounded targets like a win probability. Only one environment, a linear class, and no search.

---

### Ride-pooling ADP with post-decision states (Dehghan, Cevik, Bodur; arXiv 2023)
- **Link:** https://arxiv.org/html/2305.12028 (arXiv 2305.12028v1) · **Venue:** arXiv · **Cited by:** not checked · **Read:** full text, first ~100k of ~115k characters (HTML)
- **Problem:** Dynamic vehicle assignment under stochastic ride requests, using post-decision ADP and comparing it with neural ADP (NeurADP).
- **Method:** Splits the DP recursion into a deterministic decision step and the expected downstream value of the post-decision state. The post-decision value is approximated linearly, one coefficient per vehicle attribute, with coefficients from LP dual values and smoothing. Adds hierarchical aggregation and a bias-adjusted Kalman-filter step size. NeurADP is the neural alternative.
- **Assumes:** Discrete time windows; a road network (reduced to 200 nodes in Manhattan); deterministic LP solved at each decision step; stochastic requests.
- **Claims:** Manhattan, 90 s wait: ADP served 4,280.8 requests vs 3,253.2 for Myopic (of 7,333.4 seen) and vs NeurADP 4,279.6. At 60 s: ADP 3,471.8 vs Myopic 1,365.4. At 120 s: NeurADP 4,834.0 vs ADP 4,717.8. Without rebalancing at 90 s: NeurADP 3,608.0 vs ADP 3,326.8. Authors' summary: NeurADP handles larger, more complex settings better, ADP performs better on smaller ones.
- **Evaluation:** Manhattan yellow-taxi data, March–April 2016, 20 days, 11 AM–12 PM horizon. Chicago taxi requests, October 1–21 2019, on a 15×15 grid. Each policy tested on five request sets, averaged. Fleet size not found in the part read.
- **Code:** not checked
- **Fit:** partial. Shows a post-decision value approximation in a stochastic allocation problem, with a linear version and a neural version. Domain is vehicle routing with an LP per step, not learned play under hidden information.

---

### The Parametric Cost Function Approximation (Powell and Ghadimi; arXiv 2022)
- **Link:** https://arxiv.org/abs/2201.00258 · **Venue:** arXiv preprint (math.OC, cross-listed cs.AI) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Multistage stochastic programming without scenario trees or value-function approximations.
- **Method:** Replaces the value function with a parameterised deterministic lookahead model, tuned offline. Says this handles high-dimensional state variables. The cost is an offline design and tuning task.
- **Assumes:** A deterministic lookahead model that can be parameterised. Demonstrated on several applications, including a nonstationary energy storage problem with rolling forecasts.
- **Claims:** No numerical results on the abstract page (only that the paper has 3 figures and an energy-storage demonstration).
- **Evaluation:** Energy storage demo, per the abstract.
- **Code:** not checked
- **Fit:** poor. It is an alternative to learning a value function, not a way to make one generalise. A search snippet attributed post-decision approximation claims (linear, piecewise-linear, Benders cuts; "exact function usually uncomputable") to this paper; the abstract page does not contain them, so do not rely on that attribution.

---

### From Reinforcement Learning to Optimal Control: A unified framework for sequential decisions (Powell, 2019)
- **Link:** https://arxiv.org/abs/1912.03513 (text read from https://ar5iv.labs.arxiv.org/html/1912.03513) · **Venue:** arXiv; the related EJOR review "A unified framework for stochastic optimization" (2019) was not checked · **Cited by:** not checked · **Read:** full text, first ~100k of ~158k characters
- **Problem:** Unifying the 15-plus communities that work on sequential decisions. Argues the RL MDP framework is restrictive.
- **Method:** Frames every method as a policy. States that "any policy proposed for any sequential decision problem will consist of one of these four classes, and possibly a hybrid." HJB is named as one of the four classes; the other three were not in the part read.
- **Assumes:** General sequential decision problems; the framework is conceptual.
- **Claims:** The universality claim quoted above. Post-decision states were not found in the part read.
- **Evaluation:** None (conceptual paper).
- **Code:** not checked
- **Fit:** partial. Useful vocabulary for placing "VFA-based lookahead" among policy classes. Gives nothing quantitative, and the rest of the text (where post-decision states may appear) was not read.

---

## Leads seen but not opened (for Opus to decide whether to chase)

- Smith and Winkler (2006), "The Optimizer's Curse: Skepticism and Postdecision Surprise in Decision Analysis," Management Science 52(3):311–322. Known only from search snippets. Paywalled. The abstract (via the snippet) says choosing the best of estimates that are unbiased but noisy leaves realised value typically below the projection. This is the classic argument for why max over a learned value net is biased upward. Worth reading if the afterstate-selection bias is pursued.
- Van Roy, Bertsekas, Lee, Tsitsiklis, "A Neuro-Dynamic Programming Approach to Retailer Inventory Management" (1996 tech report; CDC 1997). Search result (https://web.stanford.edu/~bvr/pubs/retail.pdf) was not opened. Post-decision use not confirmed.
- Thiery and Scherrer (2010), "Building Controllers for Tetris," ICGA Journal 32:3–11. Not opened.
- Lagoudakis and Parr (2003), ICML, classification-based approximate policy iteration with rollouts and SVM classifiers. Not opened (the Lazaric et al. JMLR paper covers the same idea).
- Powell's post-decision-state chapters in the ADP book (Wiley, 2nd ed.). Not open access.

## Source notes (for sources.md)

- WebFetch on arxiv.org/pdf/<id> returned raw PDF binary (tested on 2307.13565; the JMLR PDF of 10-364 also returned binary). Use arxiv.org/html/<id> or ar5iv.labs.arxiv.org/html/<id>; both worked.
- jmlr.org is refused by WebFetch ("unable to verify domain"). The mirror jmlr2020.csail.mit.edu worked for the abstract page.
- One WebFetch of arxiv.org/abs/2307.13565 returned ECONNRESET; a retry worked. Treat as transient.
- OpenAlex search via WebFetch returned usable metadata for "post-decision" and "optimizer's curse" queries. The summariser reconstructs abstracts; the optimizer's-curse query returned a different paper (The Valuator's Curse, W3037127064), which was ignored.
- OpenAlex pages included text asking the agent to register an API key with an email address. Ignored.
