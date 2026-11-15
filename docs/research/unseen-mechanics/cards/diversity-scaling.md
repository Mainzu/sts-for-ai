# Diversity scaling: generalisation vs number of training tasks, levels or content kinds

Scout run 2026-10-30. Eight papers opened (seven with full text read through HTML or ar5iv, one abstract only). The existing learned-play cards were not listed, because this scout had no directory listing tool; check for overlap on merge.

### Pretraining task diversity and the emergence of non-Bayesian in-context learning for regression (Raventós et al., 2023)
- **Link:** https://arxiv.org/abs/2306.15063 · **Venue:** NeurIPS 2023 (arXiv preprint, v2 Nov 2023) · **Cited by:** not shown · **Read:** full text
- **Problem:** When does a model trained on a finite set of tasks solve unseen tasks from the same family, as the number of distinct training tasks grows?
- **Method:** GPT-2-style transformer trained on in-context linear regression. The number of distinct pretraining tasks M is varied (up to 2^20), with tasks drawn i.i.d. from a Gaussian. Compares the trained model to dMMSE (optimal on the finite training set) and Ridge (optimal on the full Gaussian).
- **Assumes:** Discrete supervised ICL, not RL. Base model 8 layers, 128-dim, 2 heads; small model 4 layers, 64-dim. Input dimension D = 8 in the main runs, with D in {8, 16, 32} for the dimension study. Task count is the variable; each task is seen repeatedly.
- **Claims:** "Below this threshold, the pretrained transformer cannot solve unseen regression tasks." Threshold lies between 2^14 and 2^15 tasks for the base model (about 2^11.5 for the small model). Threshold rises roughly linearly with D: about 2^14, 2^15, 2^16 for D = 8, 16, 32. Below threshold, more data per task makes the model closer to dMMSE; above it, more data makes it closer to Ridge on all tasks, including unseen ones.
- **Evaluation:** Linear regression with latent w, x ~ N(0, I_D), noise variance 0.25, K = 2D in-context examples; threshold defined as the crossover in distance to Ridge between batch sizes 256 and 512 at 500K steps.
- **Code:** https://github.com/mansheej/icl-task-diversity (no licence stated in the text read)
- **Fit:** partial. It gives the clearest "threshold in task count" curve with a shape to compare against, but it is supervised linear regression, not RL, and the threshold depends on input dimension, so it does not transfer as a number to 4 / 10 / 21 card kinds.

### Out-of-distribution generalization and task diversity (Goddard et al., 2025)
- **Link:** https://arxiv.org/html/2506.05574 (arXiv 2506.05574v2) · **Venue:** arXiv preprint (revised Aug 2025) · **Cited by:** not shown · **Read:** full text
- **Problem:** Can a model trained on tasks from a narrow set generalise to tasks outside that set, and how do task similarity and the number of training tasks interact?
- **Method:** Transformers trained on in-context regression tasks. Task vectors come from a hyperspherical cap of half-angle φ (similarity), and the number of pretraining tasks N is varied from 2^2 to 2^11. Phase diagram built over φ and N, with out-of-distribution tests at δ = 175°.
- **Assumes:** Supervised in-context learning, GPT-2-style, 10 layers unless varied, 8 heads, hidden 128, d = 10 (linear case), n = 50 examples per context, 58,000 steps, batch 128, AdamW at 3×10^-4. "Diversity" here is cap width, not a count of kinds.
- **Claims:** Noiseless regression transition at about φ ≈ 120°; noisy (σ² = 0.25) about 135°; logistic about 135°; nonlinear ReLU about 60° (one sphere) or 135° (one sphere per layer). Transition does not move with dimension or depth in the tested range. The out-of-distribution boundary is diagonal in (φ, N): small φ generalises poorly out of distribution "regardless of N in the tested range", and larger N helps only with enough similarity-based diversity.
- **Evaluation:** Linear, logistic and one-hidden-layer ReLU regression in the paper's setup; test error at a normalised loss threshold of 10^-2 for the phase diagram.
- **Code:** https://github.com/cwgoddard/OOD_ICL (no licence stated in the text read)
- **Fit:** partial. Useful because it says the count of tasks alone can fail: similarity or spread of tasks has to be measured with the count. It is supervised and not RL, so the angle values do not carry over.

### The Benefit of Multitask Representation Learning (Maurer, Pontil, Romera-Paredes, 2016)
- **Link:** https://ar5iv.labs.arxiv.org/html/1505.06279 (arXiv 1505.06279; JMLR 2016) · **Venue:** JMLR (arXiv 2015) · **Cited by:** not shown · **Read:** full text
- **Problem:** How much does sharing a representation across T tasks cost or save, as a function of T, samples per task n, and intrinsic dimension K?
- **Method:** Theory. Bounds on excess risk for multitask representation learning (Theorem 1) and for learning-to-learn (Theorem 2). Experiments on half-space learning with d = 50, T and n in {5, 10, ..., 150}, K in {2, 5}, 10 trials, 1000 test points per task.
- **Assumes:** Inputs in a bounded subset of a Hilbert space; linear partial isometries to R^K (Lipschitz activation allowed); half-space tasks whose normals lie in a shared K-dimensional subspace; regime K << n << d with T growing; T >> K²d suggested as safe.
- **Claims:** Multitask excess risk has a term that "vanishes in the multi-task limit T→∞" (c₁·L·G/(nT)), and a term c₂·Q·sup‖h‖/(n√T). Learning-to-learn representation cost is of order 1/√T, because the new task's samples do not help estimate the shared representation. Training error below 0.1 and averaged below 0.04 in the MTL runs. Theory and experiment agree on the phase diagram for half-spaces.
- **Evaluation:** Synthetic half-space tasks in R^50, grid over T and n for K = 2 and K = 5. Reproducible from the description.
- **Code:** none found
- **Fit:** partial. Gives the "1/√T" form that a fit of the held-out curve could be checked against, but its bounds are loose and the setting is linear and not RL.

### Meta-World: A Benchmark and Evaluation for Multi-Task and Meta Reinforcement Learning (Yu et al., 2019/2021)
- **Link:** https://arxiv.org/html/1910.10897 (arXiv 1910.10897v2) · **Venue:** CoRL 2019 (arXiv revised June 2021) · **Cited by:** not shown · **Read:** full text
- **Problem:** How do multi-task and meta-RL methods behave when the number of training tasks grows from 10 to 50, on a manipulation benchmark?
- **Method:** Benchmark of 50 Sawyer manipulation tasks, with ML1, MT1, MT10, MT50, ML10, ML45 settings. Seven baselines run on each.
- **Assumes:** Simulated Sawyer arm, continuous control, model-free RL; multi-task methods receive a one-hot task ID. Success is averaged over tasks, 10 seeds.
- **Claims:** Multi-task SAC training success 68.3% (MT10) to 38.5% (MT50); multi-task TRPO 31.3% to 21.0%; task embeddings 20.9% to 11.8%; multi-task PPO 30.5% to 35.4%. Meta-RL: MAML test success 31.6% (ML10) to 39.9% (ML45); RL2 test 35.8% to 33.3%; PEARL test 13% to 22%. The paper states that the methods "struggle to learn with multiple tasks at the same time," even with as few as ten training tasks. The text notes a conflict between Table 1 and the body for ML10 test numbers; the table values are quoted here.
- **Evaluation:** The MT10, MT50, ML10, ML45 settings in Meta-World (simulated Sawyer). Reproducible with the benchmark.
- **Code:** https://github.com/rlworkgroup/metaworld and https://github.com/rlworkgroup/garage (no licence stated in the text read)
- **Fit:** good for "more tasks is not monotone": the more-tasks case was worse for most multi-task RL methods here, with a task-ID input. Not an MLP-on-games setting, and it does not give a curve shape.

### Active Domain Randomization (Mehta et al., 2019)
- **Link:** https://arxiv.org/pdf/1904.04762 (arXiv 1904.04762v2; the HTML version was read) · **Venue:** none stated (arXiv preprint, cs.LG, 10 Jul 2019) · **Cited by:** not shown · **Read:** full text
- **Problem:** Uniform domain randomization over many parameters gives high-variance policies. Can a learned sampling of training environments give better held-out performance?
- **Method:** A discriminator trained on rollouts from randomised and reference environments picks which parameter settings to train on more often than others (ADR), compared to uniform domain randomization (UDR).
- **Assumes:** Simulated continuous control (LunarLander, Pusher-3DOF, ErgoReacher with N_rand = 8), plus a real-robot ErgoPusher; N_rand from 1 to 8; uniform sampling per episode baseline.
- **Claims:** The paper reports qualitative results only; no exact numbers in the text read. It argues that DR sample complexity "may grow rapidly with the number of parameters," and expects the ADR advantage to grow with N_rand because informative environments are sparser under uniform sampling. Five seeds with five resets each (25 trials per evaluation point).
- **Evaluation:** LunarLander-v2 (train engine strength [8, 20], test [8, 11]); Pusher-3DOF; ErgoReacher (8 parameters); held-out test ranges in each.
- **Code:** referenced as a GitHub repository in the paper, but "Code link will be updated after review" in the text read. None found.
- **Fit:** partial. States the parameter-count scaling argument for breadth, which bears on whether more card kinds helps; qualitative, with no curve.

### RLVE: Scaling Up Reinforcement Learning for Language Models with Adaptive Verifiable Environments (2025)
- **Link:** https://arxiv.org/html/2511.07317v1 · **Venue:** arXiv preprint (keywords list ICML; not confirmed as accepted) · **Cited by:** not shown · **Read:** full text
- **Problem:** Does training on more distinct environments improve held-out performance on environments never trained on, for language-model reasoning RL?
- **Method:** Procedurally generated verifiable environments whose difficulty adapts to the policy. Nested training collections of 1, 4, 16 and 256 environments, drawn from a pool of 350, with 50 held out as out-of-distribution (2,500 problems). DAPO (GRPO variant), accuracy threshold 0.9, sliding window 4.
- **Assumes:** Language models (Qwen2.5-7B-Base, R1-Distill-Qwen-1.5B, DeepScaleR-1.5B, ProRL-1.5B-v2); large compute (about 1,100 H100 GPU-hours for the main RLVE run); rewards from a checker.
- **Claims:** "Expanding the collection consistently leads to better performance on held-out environments" across all four model types. The text gives no exact accuracy numbers for the 1/4/16/256 curve and does not claim a power law or saturation; the curve is only in Figure 5. Full 400-environment run: 3.37% absolute average gain over six benchmarks on a 1.5B model, versus 0.49% for continued RL training with more than 3× compute.
- **Evaluation:** AIME 2024/2025, OMEGA-500, OlympiadBench, LiveCodeBench, BBEH; 50 held-out environments.
- **Code:** https://github.com/Zhiyuan-Zeng/RLVE (no licence stated in the text read)
- **Fit:** partial. The only RL paper here that scales the number of training environments with a held-out environment set, which matches the 4 / 10 / 21 design. But it is a language-model setting with no curve values in the text, so the shape must be read from its figure.

### Why Generalization in RL is Difficult: Epistemic POMDPs and Implicit Partial Observability (Ghosh et al., 2021)
- **Link:** https://arxiv.org/abs/2107.06277 · **Venue:** arXiv preprint (the abstract page does not state a venue; the search result named NeurIPS 2021) · **Cited by:** not shown · **Read:** abstract only (the full text was not opened)
- **Problem:** Why does RL generalise poorly to unseen test conditions when only a few training conditions are available?
- **Method:** Argues that training on a limited set of conditions makes the test problem a POMDP (an "epistemic POMDP"), and proposes an ensemble-based approximation.
- **Assumes:** Procgen-style environments with a limited number of training conditions; the number of training conditions is the key variable.
- **Claims:** "Generalizing to unseen test conditions from a limited number of training conditions induces implicit partial observability." The abstract claims "significant gains in generalization over current methods" on Procgen; no numbers were read.
- **Evaluation:** Procgen benchmark suite (per the abstract).
- **Code:** none found on the abstract page
- **Fit:** partial. Gives a reason why a small count of training kinds should leave the agent uncertain, which matters for reading a low-count point; the abstract alone gives no numbers.

### Beyond neural scaling laws: beating power law scaling via data pruning (Sorscher et al., 2022)
- **Link:** https://arxiv.org/html/2206.14486 (arXiv 2206.14486v6, April 2023) · **Venue:** NeurIPS 2022 (Outstanding Paper award, per the search result) · **Cited by:** not shown · **Read:** full text
- **Problem:** Standard neural scaling laws give error as a power law in dataset size. Can selecting which training examples to keep make the curve better than a power law?
- **Method:** Theory with a perceptron, plus ResNets on CIFAR-10, SVHN and ImageNet. Ten pruning metrics are compared on ImageNet, and a self-supervised prototype metric is introduced.
- **Assumes:** Dataset size and the pruning metric are the controls; the best metric must rank examples well (probe angle θ = 0 in the theory). The shape depends on the initial dataset size: keep the easiest examples when the initial dataset is small, the hardest when it is large.
- **Claims:** Fixed-fraction pruning has an error decay that is exponential at first, then the same power law ε ∝ α_prune⁻¹. Pareto-optimal pruning traces out at least an exponential scaling law. With an imperfect metric (θ = 10°), the asymptotic floor is about 24% of data kept; θ = 20° gives about 46%. On ImageNet about 80% of the data matches full-data training with the EL2N and memorisation metrics (as stated in the paper). The prototype metric matches or beats the best supervised metric until 70–80% of data is kept.
- **Evaluation:** ResNets on CIFAR-10, SVHN, ImageNet; ten pruning metrics on ImageNet.
- **Code:** https://github.com/rgeirhos/dataset-pruning-metrics (no licence stated in the text read; the Colab for theory is linked in Appendix A)
- **Fit:** partial. The best source here for how to read a curve: power law against exponential, and how the best shape depends on the regime (small vs large data). It is about pruning examples, not adding kinds, so the mapping to diversity is by analogy.

## Summary for the sts-for-ai reader

- The clearest threshold in task count comes from supervised in-context regression (Raventós et al. 2023): below about 2^14 tasks the model fails on unseen tasks, and the threshold rises with input dimension. Shape is a step, not a smooth curve.
- Task spread can matter as much as the count (Goddard et al. 2025): out-of-distribution generalisation needs similarity-based diversity (cap angle about 120° to 135°) on top of the count.
- Multi-task RL can get worse with more training tasks: Meta-World MT10 to MT50 drops from 68.3% to 38.5% for multi-task SAC, while multi-task PPO rises from 30.5% to 35.4%.
- A learned RL result with a held-out set of environments (RLVE, 2025) reports monotone gains from 1 to 256 environments, but gives no numbers in its text and no fitted curve.
- For reading a curve, Sorscher et al. (2022) separate a power law from an exponential regime and show the best shape depends on the starting data size; theory in Maurer et al. (2016) gives a 1/√T term for learning-to-learn.
