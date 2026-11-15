# Playing well on unseen mechanics — prior art

Scan (2026-10-30), run by the manager. Step 1 (the
interview) is skipped; the answers come from `docs/manager.md` goals,
`docs/research/big-picture-2026-10-30.md` and the results doc. The earlier
scan, `docs/research/learned-play-and-generalisation.md` (2026-10-24),
covered how to train a value net with search; this one covers what that
scan left open.

## First principles

- **Wanted:** a combat AI whose win rate on content it never trained on
  (new cards, new powers, new enemies, and above all new *mechanics*) stays
  close to its win rate on training content. Today nets keep a lead on
  unseen cards built from known primitives, but lose it when an unseen boss
  meets unseen cards (Guardian -0.13), and effects features beat card ids
  only zero-shot.
- **Inputs per decision:** a combat state (player, hand, draw/discard piles
  with unknown order, enemies with intents and powers); every card and
  power is described by effect primitives, not text. **Output:** an action,
  picked by expectimax search (one turn, chance nodes for draws) over a
  learned or heuristic leaf value.
- **Second question:** two-turn search with a heuristic or net leaf loses
  to one-turn search (-0.05 held-out; partly a node-cap artefact). Is that
  a known effect of deeper search with a noisy evaluator and chance nodes?

Constraints:
- CPU only (one consumer machine), no GPU — **hard** (machine).
- Content described by primitives in a Rust rules engine; new content is
  added as data plus, for a new mechanic, engine code — **hard** (code).
- Custom content must be first class: a modder's new character or
  mechanic should not need a retrain from scratch — **hard** (owner goal 1).
- Small nets (MLP over pooled entity features), Python training — **soft**.
- Exact-solver labels for short fights — **soft** (the lean loop may drop
  them).
- Fixed-length feature vector per entity — **assumed**.

## Search plan

The 2026-10-24 scan already carded ~150 papers on unseen cards (MTG,
Hearthstone, Dominion), general game playing, entity sets, new actions,
ProcGen and language grounding. This scan skips those and takes the gaps
(one scout each, told to skip papers already carded there):

1. `search-pathology` — when deeper search hurts: evaluator error vs
   depth, chance nodes and sampling at them, node caps and partial trees.
2. `diversity-scaling` — how generalisation scales with the number of
   distinct training tasks, levels or content kinds (ProcGen level-count
   curves, task diversity in multi-task and meta-RL). Feeds the coverage
   pilot (4 / 10 / 21 card kinds).
3. `compositional-primitives` — systematic generalisation to new
   combinations of known primitives and to genuinely new primitives
   (compositional RL, modular nets, BabyAI-style benchmarks).
4. `test-time-adaptation` — adapting to new content just before play:
   short fine-tuning or self-play on the new content, test-time training,
   meta-RL; how much play it needs.
5. `ai-playtesting-new-content` (outside the field) — agents that playtest
   newly designed game content (card balance, level testing, mod testing)
   and how they cope with content they weren't trained on.

## Search

Five scouts opened 40 papers (31 full text, 9 abstract only); cards are in
`docs/research/unseen-mechanics/cards/`. I re-read seven shortlisted papers
against their full text (arXiv HTML, through a fetch agent that quotes
verbatim where it can). Two of the seven cards needed a correction, both
minor: Ash & Adams' λ 0.6 / σ 0.01 is one figure's setting, not a general
default, and their numbers are validation accuracy; Raventós' text also
mentions a 2^6 boundary that conflicts with its own 2^14-2^15 caption.
Caveat: long pages were truncated, so some table numbers come from the
fetch tool's summary; those are marked "(summary)".

## Shortlist (verified)

| Paper | What it shows | Fit |
|---|---|---|
| Hallak et al. 2021, *Improve agents without retraining: parallel tree search with off-policy correction* ([2107.01715](https://arxiv.org/abs/2107.01715), code NVlabs/bcts) | Tree search over a pretrained value function can score *below* the plain policy (Atari, near-deterministic), worst at depth 1. Cause: leaves off the policy's path have noisier values, and the max over noisy values is biased upward. Fix (BCTS): subtract a penalty from root actions that leave the policy's choice, sized from leaf noise (Bellman error at depth 1); scores then rise with depth. | **Good**: the same symptom as our two-turn loss, with a cheap fix |
| Nguyen & Ramanujan 2022/24, *Lookahead pathology in MCTS* ([2212.05208](https://arxiv.org/abs/2212.05208)) | UCT with γ = 1 and large exploration gets worse with more nodes even with a perfect heuristic; γ is the main driver. Synthetic trees. | Partial: UCT, not expectimax; a caution that more search isn't always better |
| Ash & Adams 2020, *On warm-starting neural network training* ([1910.08475](https://arxiv.org/abs/1910.08475)) | Warm-starting on more data generalises worse than starting fresh (ResNet 51.7 vs 56.2; MLP 37.4 vs 39.0, validation accuracy). Shrink-perturb (θ ← λθ + noise, λ 0.3-0.6) closes the gap and keeps the speed-up. No RL. | Good for the adaptation path (cheap to try) |
| Raventós et al. 2023, task diversity and in-context regression ([2306.15063](https://arxiv.org/abs/2306.15063)) | Generalisation to unseen tasks switches on past a threshold count of distinct training tasks (2^14-2^15 for their base model, ~2^11.5 for a smaller one); the threshold rises with task dimension. | Partial: supervised toy; the lesson is that a flat curve over a short range can sit below a threshold |
| Yu et al., *Meta-World* ([1910.10897](https://arxiv.org/abs/1910.10897)) | More training tasks can lower multi-task success (SAC 68.3% on 10 tasks vs 38.5% on 50; PPO 30.5 vs 35.4). Meta-test on held-out tasks is low for every method (RL² 35.8%, MAML 31.6% on ML10). | Partial: a capacity effect to watch for in the coverage pilot |
| Schug et al. 2024, *Discovering modular solutions that generalize compositionally* ([2312.15001](https://arxiv.org/abs/2312.15001)) | A hypernetwork over shared modules generalises to unseen *combinations* of known modules if training support is compositional and connected (each module seen alongside others), and fails when a module is only seen alone. For a new task it fits a small task code with weights frozen. Supervised. | Partial: a design rule for the content generator; nothing for new primitives |
| Xiao & Yang 2024, *LLMs may not be human-level players, but they can be testers* ([2410.02829](https://arxiv.org/abs/2410.02829)) | On the real Slay the Spire (Ironclad, CommunicationMod), an agent's HP left per boss correlates with the human win rate per boss from the developer's data: GPT-4 CoT r 0.87 in Act 1, a rule-based bot 0.74 (summary; n not stated). | Partial: an outside yardstick for later (needs the real game) |

No scout found a method that generalises to a genuinely *new* primitive
without new features or new training. The compositional literature covers
new combinations of known parts only.

## What it changes for us

1. **Depth (Next 4).** Hallak's mechanism fits our two-turn loss. Two-turn
   search compares many more leaf values, mostly on states one-turn play
   would not reach, so it more often picks an option whose value is
   overestimated. The node-cap bias explained part of our loss; this can
   explain the rest. Their fix needs no new evaluator: **keep the one-turn
   choice unless the two-turn search prefers another option by more than
   a margin** (BCTS sizes the margin from leaf noise; we can sweep it).
   Borrowed check: with the right margin, results rise with depth and with
   `sample_k` instead of falling.
2. **Coverage pilot (Next 6).** Read its 4 / 10 / 21 curve with care. A
   flat curve over that short a range doesn't rule out a threshold further
   out (Raventós). If train strength falls as kinds rise, that's a
   net-capacity effect (Meta-World), not "diversity doesn't help". Report
   train and held-out per arm against log(kinds).
3. **Goal 1, new mechanics.** Nothing in the literature makes a fixed net
   handle a new primitive zero-shot. So the realistic path for custom
   content is: a new mechanic brings a new feature (engineering, as for
   Mode Shift), then a short adaptation burst from the current net. For
   the burst: warm start plus shrink-perturb (Ash & Adams); keep replaying
   old fights against forgetting (CLEAR, card); pick fights by the net's
   own value error (Prioritized Level Replay, carded 10-24). The goal-1
   metric then becomes "CPU minutes of adaptation to recover the lead on
   new content", next to zero-shot.
4. **Generator design.** Generated cards should combine primitives
   broadly, so no primitive appears only alone or only with one partner
   (Schug's connected support).

## Alternative framings (listed, not adopted)

- **Adaptation instead of zero-shot** as goal 1's bar: a modder's new
  mechanic counts as handled when a few CPU minutes of self-play recover
  most of the lead. Loses: instant play on day zero. Enables: the
  warm-start machinery we already have.
- **Depth as a guarded override** of one-turn search, not a replacement.
  Loses: nothing measured so far. Enables: depth without a better
  evaluator.

## Recommendation

Two cheap experiments, in this order:
1. **Guarded two-turn search** (Next 4): take the one-turn choice unless
   two-turn prefers another option by more than margin m; sweep m on the
   cap-400k fights, paired against one-turn. Build it in Python on
   `sts.search`'s per-option values if it returns them, else as a small
   Rust change.
2. **Adaptation-burst metric** (Next 6/7): once Mode Shift has a feature,
   measure the Guardian held-out lead after 0 / 5 / 20 CPU minutes of warm
   self-play on Guardian fights, with and without shrink-perturb.

## Checks borrowed from the literature

- BCTS: once the override is penalised, scores rise with depth; test
  two-turn at k 4 and 16 and at two cap sizes.
- Ash & Adams: warm vs fresh vs shrink-perturb on the same data, judged
  on held-out play, not training loss.
- Raventós / Meta-World: plot held-out lead against log(kinds) and watch
  train strength for a capacity drop.

## Not applicable, and why

- Meta-RL (MAML, RL², PEARL): weak on held-out tasks even in Meta-World,
  and heavy; fine-tuning beat it on new tasks (Mandi et al., card).
- LLM agents as players or testers: they break CPU-only and are slow.
  Copy their human-correlation check, not the agent.
- UCT-style MCTS: we use expectimax with chance nodes; the pathology paper
  is a caution, not a design.
