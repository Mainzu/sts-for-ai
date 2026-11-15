# Test-time adaptation: cards

Scout angle: fast adaptation to new tasks or content (fine-tuning vs zero-shot, test-time training, meta-RL, continual RL with replay, choosing what to play during adaptation). Eight papers opened, all from arXiv HTML (full text).

### On the Effectiveness of Fine-tuning Versus Meta-reinforcement Learning (2022, revised 2023)
- **Link:** https://arxiv.org/abs/2206.03271 · **Venue:** arXiv (no venue named; v2 revised 16 Feb 2023) · **Cited by:** not checked · **Read:** full text
- **Problem:** Do meta-RL methods (RL2, Reptile, PEARL) adapt better to new tasks than plain multi-task pretraining followed by fine-tuning?
- **Method:** Compares MT pretraining + full-parameter fine-tuning against Reptile, RL2 and PEARL on Procgen (CoinRun), RLBench (11 tasks, 5 splits) and Atari (10 train, 5 test games). Fine-tuning uses vanilla PPO, RainbowDQN or C2F-ARM.
- **Assumes:** Test tasks are truly different from training tasks. Procgen: up to 10,000 training levels, 20 held-out test levels, 100M pretraining steps, PPO with IMPALA encoder. Fine-tuning budget 2M env steps per Procgen test level, 100K env steps per Atari test game. RLBench measured in compute time (about 9 h per test task per seed). Network sizes not stated in the main text.
- **Claims:** "when meta-RL methods are tested on truly different tasks, multi-task pretraining followed by fine-tuning performs equally well or better." Procgen: fine-tuning gives the best adaptation in sample efficiency and final performance across all training-set sizes; RL2-PPO "does not improve on unseen levels" (average training-level reward at 100/1,000/10,000 levels: MT-PPO 9.7/8.0/7.5, RL2-PPO 4.7/7.7/7.8, Reptile-PPO 9.5/5.8/5.3). RLBench: with 0 demonstrations MT fine-tuning is about as good as Reptile and better than PEARL and from-scratch on all 5 test tasks. Atari: from-scratch training is competitive; the authors attribute this to low transfer between games. Forgetting is not measured directly; the authors hypothesise that fine-tuning keeps useful skills and forgets others. The paper does not state how many fine-tuning steps convergence needs.
- **Evaluation:** Procgen CoinRun with held-out levels; RLBench 11-task leave-one-out; ALE 10 train / 5 test games. Reproducible at the level of "pretrain on N levels, fine-tune 2M steps on one held-out level."
- **Code:** none found (project site https://sites.google.com/berkeley.edu/finetune-vs-metarl; no repo linked in the paper; the paper says code is in supplementary material)
- **Fit:** partial. It supports "fine-tune the pretrained model" over meta-learning, but its budgets (2M and 100K env steps, PPO/Rainbow with large encoders) are far above minutes of CPU time, and it gives no forgetting measure.

### Fast Adaptation with Behavioral Foundation Models (2025)
- **Link:** https://arxiv.org/abs/2504.07896 · **Venue:** arXiv preprint (Apr 2025); the search listing also says RLJ vol. 6 and RLC 2025, not confirmed on the arXiv page · **Cited by:** not checked · **Read:** full text
- **Problem:** Zero-shot policies from behavioral foundation models (BFMs) are often suboptimal; can a few tens of episodes of adaptation close the gap?
- **Method:** Two latent-space adapters. ReLA is an off-policy actor-critic that trains a residual critic (2-layer MLP, 64 hidden units) and updates the latent z with the pretrained actor frozen. LoLA is actor-only: fixed-horizon on-policy rollouts with a frozen terminal value, a Gaussian over z with trainable mean and fixed diagonal covariance, and a leave-one-out baseline.
- **Assumes:** Continuous control in DeepMind Control (Pointmass, Walker, Cheetah, Quadruped) and HumEnv humanoid, 64 tasks in 5 domains. Base BFMs: FB, HILP, PSM, FB-CPR. Adaptation reported over 300 episodes with 5 seeds and 50 evaluation episodes; headline gains appear within a few tens of episodes. Reward is a task reward given at test time.
- **Claims:** "10-40% improvement over their zero-shot performance in a few tens of episodes." LoLA: about 10% on DMC and about 40% on HumEnv within 20 episodes. LoLA is described as monotonic across domains; actor-critic methods (ReLA included) show an initial performance drop, attributed to critic distribution shift. Action-space fine-tuning "completely unlearn[s] in a few steps" for FB-CPR.
- **Evaluation:** DMC 64-task suite (Pointmass 7, Walker 4, Cheetah 4, Quadruped 4) plus HumEnv 45 tasks. Reproducible as "zero-shot policy, then 20-300 episodes of latent search."
- **Code:** none from the authors; they used Meta's metamotivo repo for FB and FB-CPR (https://github.com/facebookresearch/metamotivo). Paper is CC BY 4.0.
- **Fit:** partial. The idea of searching a small latent (not the whole net) and the warning about the initial drop fit the constraint of small nets. But the setting is continuous control with a reward given at test time, and the budgets are episodes in simulators, not a sparse-reward card game.

### Prioritized Level Replay (2021)
- **Link:** https://arxiv.org/abs/2010.03934 · **Venue:** ICML 2021 (keyword on arXiv page; PMLR v139) · **Cited by:** not checked · **Read:** full text
- **Problem:** Deep RL overfits to the training levels, and uniform sampling of levels ignores what the current policy can still learn. Which training level should be replayed next?
- **Method:** After each episode on level i, score S_i = time-averaged |GAE| (the L1 value loss from TD errors). Sample replays by rank-based priority P_S ∝ (1/rank)^(1/β) mixed with a staleness term P_C ∝ c − C_i via ρ, plus a Bernoulli choice between a replayed and a new level. Hyperparameters: β = 0.1, ρ = 0.1 (Procgen), ρ = 0.3 (MiniGrid).
- **Assumes:** Procedurally generated levels with a finite or large set of seeds (Procgen easy 200 levels, hard 500, MiniGrid 3,000–6,000). PPO-style on-policy learner, with GAE and a value function. Score signal is the policy's own value error, so the policy must already be learning on the level.
- **Claims:** Normalized mean test return (Procgen easy, 100 test episodes): Uniform 100.0±4.5, PLR 128.3±5.8, UCB-DrAC + PLR 176.4±6.1. Per-game gains are uneven (BigFish 3.7 to 10.9; Dodgeball 1.7 to 1.8 for PLR, 10.3 for UCB-DrAC+PLR). MiniGrid normalized test return: Uniform 100.0±2.5%, PLR 124.3±4.7%. Budgets: Procgen easy 25M env steps, 10 runs; Procgen hard 200M steps, 5 runs. No budget stated for MiniGrid.
- **Evaluation:** Procgen easy (16 games) and hard, MiniGrid (MultiRoom-N4-Random, ObstructedMazeGamut-Easy and -Medium). Test on held-out levels.
- **Code:** https://github.com/facebookresearch/level-replay · license not stated in the paper (arXiv perpetual non-exclusive license for the paper itself)
- **Fit:** partial. It is the clearest answer in this batch to "what to play next," since it scores levels by the learner's own value error. But its numbers come from 25M-200M steps of PPO, and it targets generalisation across levels, not adaptation to one new mechanic.

### Experience Replay for Continual Learning (CLEAR) (2018, rev. 2019)
- **Link:** https://arxiv.org/abs/1811.11682 · **Venue:** arXiv (the search listing also gives NeurIPS 2019; not confirmed on the arXiv page) · **Cited by:** not checked · **Read:** full text
- **Problem:** Catastrophic forgetting when tasks arrive one after another in RL, where training on all tasks together is not possible.
- **Method:** Actor-critic on a 50-50 mix of new and replayed experience, with V-trace off-policy correction (IMPALA style). Replayed data also gets behavioural cloning: KL penalty on the policy (weight 0.01) and L2 penalty on the value (weight 0.005). Reservoir sampling fills the buffer, capped at half of the frames trained on.
- **Assumes:** Sequential tasks with no task labels needed at test. Distributed IMPALA-style actors on CPUs with a single learner; "shallower IMPALA-style" network; hardware not stated. Frames in the hundreds of millions (900M-frame sequence).
- **Claims:** DMLab cumulative final performance (explore / rooms_collect / rooms_keys): Sequential without CLEAR 17.99 / 5.01 / 10.87; CLEAR (50-50) 31.40 / 8.00 / 18.13; separate training 29.24 / 8.79 / 19.91; simultaneous training 32.35 / 8.81 / 20.56. Buffer size: 5M-frame buffer (about 1 in 200 experiences) shows "slight forgetting." Atari: CLEAR beats Progress & Compress on Krull (8845 vs 7025), Hero (8106 vs 3433), Ms. Pacman (1223 vs 925), but loses on Beam Rider, Star Gunner, Space Invaders.
- **Evaluation:** DMLab three-task cycle plus a probe task (natlab_varying_map_randomized); six-game Atari sequence from Progress & Compress. Three runs per experiment.
- **Code:** none found in the paper (arXiv licence only)
- **Fit:** partial. The replay-plus-behavioural-cloning recipe is the right shape for "warm-start without forgetting," but it is written for many-frame distributed training, not minutes of CPU on a small net. Use it as a mechanism, not as a budget.

### On Warm-Starting Neural Network Training (2019, rev. 2020; NeurIPS 2020)
- **Link:** https://arxiv.org/abs/1910.08475 · **Venue:** NeurIPS 2020 (search listing; the arXiv page names no venue) · **Cited by:** not checked · **Read:** full text
- **Problem:** Does warm-starting from the previous round's weights generalise worse than fresh random initialisation when new data arrives in batches?
- **Method:** Empirical study, plus "Shrink, Perturb, Repeat": at each round set each parameter θ ← λθ_prev + p, with Gaussian noise p of scale σ and 0 < λ < 1.
- **Assumes:** Supervised learning, not RL. Datasets CIFAR-10, CIFAR-100, SVHN (ResNet-18; MLP), IMDB (RNN). SGD and Adam. Sequential data in rounds (two rounds: 50% then 100%; online batches of 1,000). Not studied: RL, non-stationary rewards.
- **Claims:** Validation accuracy, random init vs warm start, two rounds (Table 1): CIFAR-10 ResNet SGD 56.2 vs 51.7, Adam 78.0 vs 74.4; CIFAR-100 ResNet SGD 18.2 vs 15.5, Adam 41.4 vs 35.0; SVHN ResNet SGD 89.4 vs 87.5, Adam 93.6 vs 93.5. Training accuracy is unaffected. Shrink-Perturb: in CIFAR-10 online with ResNet, λ = 0.6 and σ = 0.01 matched random-init accuracy while training faster; pre-training transfer λ = 0.3, σ = 0.0001 was at least as good as the better of warm start and random init. Shrinking only the last layer did not close the gap.
- **Evaluation:** CIFAR-10/100, SVHN, IMDB, rounds of new data. Reproducible as "train, then retrain on a new batch from warm weights, compare with fresh."
- **Code:** none linked (arXiv licence only). A reproduction study exists (listed on paperswithcode) and reports the gap and the shrink-perturb fix in some settings, with some results not reproduced.
- **Fit:** partial. It is the direct test of our warm-start-vs-fresh question, and the shrink-perturb recipe is a cheap way to avoid the gap. But it is supervised, with no RL, and the shrink values are for image models, so they must be re-measured on our net.

### Test-Time Training with Self-Supervision for Generalization under Distribution Shifts (2019, v3 2020)
- **Link:** https://arxiv.org/abs/1909.13231 · **Venue:** arXiv (no venue named on the page) · **Cited by:** not checked · **Read:** full text
- **Problem:** A model trained on clean data fails on shifted test inputs. Can it adapt to each unlabeled test input at test time?
- **Method:** Joint training with a rotation-prediction auxiliary head. At test time, the shared feature extractor is updated on the rotation loss with augmented copies of one image: 10 SGD steps at lr 0.001, no momentum or weight decay; the adapted parameters are discarded afterwards. TTT-Online keeps parameters across a shuffled stream with one gradient step per image. Group Normalization replaces BatchNorm.
- **Assumes:** Image classification with a fixed self-supervised task that is non-trivial and aligned with the main loss. Cost is roughly 2 × batch size × iterations of a forward pass. Gradient alignment between the main and auxiliary losses is the stated condition for a step to help (theory: smooth convex main loss, positive inner product).
- **Claims:** CIFAR-10-C level 5 error (%): original test set baseline 8.9, TTT 7.9, TTT-Online 8.2; Gaussian noise baseline 50.5, TTT 45.6, TTT-Online 25.8; pixelation baseline 55.8, TTT-Online 18.1. ImageNet-C level 5 accuracy (ResNet-18), Gaussian noise: baseline 1.3, TTT-Online 26.3. Correlation between gradient alignment and error improvement across 75 corrupted test sets: 0.93 (standard), 0.89 (online). TTT did not help on airplane images, where black borders give a shortcut for rotation.
- **Evaluation:** CIFAR-10-C, CIFAR-10.1, ImageNet-C, VID-Robust. Reproducible on CIFAR-10-C noise levels.
- **Code:** project site https://test-time-training.github.io/ (linked by the authors; no licence stated in the paper; arXiv licence CC0)
- **Fit:** partial. The "adapt per input with a few gradient steps and a self-supervised loss" pattern is the test-time idea itself, and the alignment criterion is a cheap check on whether adaptation will help. But it is supervised image classification, and the auxiliary task would need to be designed for our game state.

### Fast Adaptation to New Environments via Policy-Dynamics Value Functions (2020)
- **Link:** https://arxiv.org/abs/2007.02879 · **Venue:** ICML 2020 (per search listing; arXiv page lists ICML only as a keyword) · **Cited by:** not checked · **Read:** full text
- **Problem:** Find a good policy in an environment with unseen dynamics from one short episode, with no further training.
- **Method:** Train PPO policies on each training environment. Learn a dynamics embedding (Transformer on the first N_d transitions) and a policy embedding (Transformer on full trajectories). Fit a quadratic value function W(s0, z_π, z_d). At test time, run a pretrained policy for N_d steps to infer z_d, then pick the policy embedding that maximises W by a closed-form top-singular-vector solution. No parameter updates.
- **Assumes:** Continuous MuJoCo-style control with varying dynamics. Inference budget N_d = 1 step (Spaceship, Swimmer), 2 (Ant-wind), 4 (Ant-legs). Training: 15 train and 5 held-out environments (Ant-wind: 16 total, 4 held out). Results averaged over 10 evaluation runs per environment and 5 seeds.
- **Claims:** Outperforms RL2, MAML, PPO_dyn and PPO_all "on most unseen-dynamics test environments"; on Spaceship and Swimmer it is sometimes comparable to PPO_env trained directly on the test environments. Exact numbers are only in Figures 4 and 5, not as text, so none are quoted here.
- **Evaluation:** Spaceship (custom 2D), Swimmer-v3 (water current), Ant-v3 (wind; limb lengths). Reproducible as "pick a policy from a library using one short probe episode."
- **Code:** https://github.com/rraileanu/policy-dynamics-value-functions · licence not stated
- **Fit:** partial. It is the zero-or-near-zero-update option: choose from a library after a short probe, which suits a minutes budget. But it needs a library of policies trained per environment, and its evaluation is continuous control, not a card game.

### Replay-enhanced Continual Reinforcement Learning (RECALL) (2023)
- **Link:** https://arxiv.org/abs/2311.11557 · **Venue:** arXiv preprint, Nov 2023 (an OpenReview review is linked; no conference named) · **Cited by:** not checked · **Read:** full text
- **Problem:** Replay fixes forgetting in supervised continual learning but fails in continual RL, even with a perfect memory. Two causes given: reward scale (old high-reward tasks dominate value updates) and offline-on-replay distribution shift.
- **Method:** PopArt-style adaptive target normalisation with a separate scale and shift per task head; a KL policy-distillation term (λ = 10, chosen from {0.01, 0.1, 1, 10, 100}) that keeps the actor close to the stored old policies on replayed states; a 50-50 new/replayed buffer; best-return exploration. Base algorithm: SAC with multi-head actor and critic.
- **Assumes:** Sequences of robotic tasks with reward scales that differ between tasks; task identity is known (multi-head). 1M env steps per task, SAC exploration of 10k steps, batch 128, buffer 10^6 per task, 5 seeds with 90% bootstrapped CIs.
- **Claims:** Continual World pairwise (100 sequences): average success on second tasks 0.44 (perfect memory) to 0.85 (RECALL); first-task forgetting 0.02 vs -0.02. CW3 average performance: RECALL 0.92, ClonEx 0.84, PackNet 0.70, EWC 0.63, perfect memory 0.49, fine-tuning 0.31. CW3 forgetting (lower is better): RECALL -0.02, fine-tuning 0.56. CW20: RECALL 0.90 average, -0.04 forgetting.
- **Evaluation:** Continual World CW3, CW6, CW10, CW20 (Meta-World-style robotic manipulation), 1M steps per task.
- **Code:** none linked (arXiv CC BY-NC-SA 4.0)
- **Fit:** partial. The reward-scale diagnosis matters for us if a new card's reward is on a different scale from the old ones. But the method is SAC with multi-head nets and 1M steps per task, far above a minutes budget.

## Notes for the reviewer
- Eight papers opened, all with full text from arXiv HTML. Citation counts were not checked; the field is shown as "not checked."
- I could not list the existing cards folder (`docs/research/learned-play-and-generalisation/cards/`) with the Read tool, which only reads files. I checked against the three titles you named and did not compare the other cards. Please check for overlap.
- The Meta-World numbers were not verified (search listings disagreed); not carded.
