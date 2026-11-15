# Learned play and generalisation in StS combat — prior art

## First principles

Wanted: a learned evaluator that makes search **play better** than search +
the hand-written heuristic (win rate, HP lost), on training cards and on
unseen cards, while keeping the effect-feature net's generalisation lead over
an id-feature net.

Per decision: in = one combat state (player, ≤5 monsters with intents, piles
as multisets of cards described by effect primitives); out = one option
(card + target, or EndTurn). The evaluator maps a state → expected final
score (0 for a loss, 2 − HP lost/100 for a win).

Today: one-turn expectimax over afterstates, leaves at large chance events;
value nets (Deep Sets, ~185k params) trained by supervised regression on
final outcomes of search + heuristic games. They predict unseen cards 50%
better than an id net, but search with them plays no better than the
heuristic.

Constraints:
- **hard**: CPU only (no GPU), runs of hours / overnight at most.
- **hard**: no peeking — agent decisions only use what the player knows.
- **hard**: generalisation is the goal; card/power identity must not be
  required to play well.
- **soft**: afterstate search with explicit chance nodes (current design).
- **soft**: cards as effect primitives (hand-written), powers as hooks
  (spec in progress).
- **assumed**: one-turn search depth; supervised targets from game outcomes;
  Deep Sets architecture; single-combat scope (no run-level decisions).

## Search

12 angles, one scout each: afterstates and backgammon, expert iteration on a
small budget, collectible card game AI, StS and deckbuilders, unseen actions
and entities, general game playing, imperfect-information search, ADP
post-decision states (operations research), value targets, CPU evaluation
nets (chess/shogi engines), generalisation over procedural content, text and
program representations of game content. About 150 cards in
`learned-play-and-generalisation/cards/` (some papers carded by several
scouts). I opened 9 sources myself (below). None of the scout claims I
checked needed correcting; TreeStrap stays abstract-only (its PDF never
decoded), and the AAMAS 2025 card was confirmed from a saved PDF copy.

## Shortlist (verified)

| Source | What it shows | Fit to us |
|---|---|---|
| Tesauro, *Temporal Difference Learning and TD-Gammon* (CACM 1995) [link](https://bkgm.com/articles/tesauro/tdl.html) | Errors on similar candidate positions are "highly correlated" and cancel when comparing moves. TD self-play "greatly surpassed" supervised training on expert games (Neurogammon). Adding 2-ply search (v2.0) cut losses against a top human. | Our nets only need to rank sibling afterstates, so MSE on absolute score is the wrong yardstick. Self-play beat imitation. |
| Tesauro & Galperin, *On-line Policy Improvement using Monte-Carlo Search* (NIPS 1996) [arXiv 2501.05407](https://arxiv.org/html/2501.05407v1) | Rollouts of a base policy = one step of policy iteration. Equity loss per move cut 2.5–3.9× with full rollouts and 3.5–6.6× with rollouts truncated at 7–11 steps and scored by the net. "No guarantees" on the size of the gain. | We have an exact, fast simulator, so truncated rollouts are cheap for the engine. |
| Jaśkowski, *Mastering 2048 with Delayed Temporal Coherence Learning…* (arXiv 1604.05085) | CPU only: afterstate values learned by TD from the agent's own play, expectimax at play time. Depth matters: 1-ply 324,710 → 2-ply 457,079 → 3-ply 511,759 average score. Its n-tuple nets "do not generalize too well". | Closest structural match (afterstates, chance, expectimax, CPU). Depth beyond one move is worth a lot; table-style features don't generalise. |
| Goodman, *Re-determinizing ISMCTS in Hanabi* (arXiv 1902.06075) | Value net trained on **search node values** (mean child score, nodes with ≥ 50 visits), used as the leaf evaluator, then retrained on that search's games, 3 iterations. Search + learned eval beat eval alone in every cell (e.g. 3 players: 21.0 vs 20.0) at 40 ms/move on one vCPU. Round 3 needed wider exploration to improve. | Search-backed targets plus iteration, at CPU scale, with hidden information handled honestly. |
| Veness et al., *Bootstrapping from Game Tree Search* (NIPS 2009) [page](https://papers.nips.cc/paper/3722-bootstrapping-from-game-tree-search), abstract only | Update the evaluator toward deep-search values at **all** tree nodes, not one. From random weights and self-play alone, a linear chess evaluator reached master level online. | Our search already computes every option's value: free training targets. |
| Jialeiv, *sts-rl-agent* (GitHub README) [link](https://github.com/Jialeiv/sts-rl-agent) | StS combat: value net + 1-ply lookahead reached floor ~8, "worse than no lookahead". Imitating MCTS failed because its rollouts "use the true future draw order". PUCT with half-trained nets lost to blind rollouts ("half-trained networks mislead the tree"). | A direct warning in our exact game. Our multiset draw pile already rules out the peeking teacher. |
| Doron, *Part 7: Diminishing Returns* (dev.to) [link](https://dev.to/doronsinger/part-7-diminishing-returns-38me) | StS search agent: wall-clock budgets made reruns of the same seeds vary (average floor 28.2 vs 20.6); fixed iteration budgets gave identical games. | Evaluate with node budgets, never time. |
| Xia et al., *Integrating LLMs with RL for Generalization in Strategic Card Games* (AAMAS 2025, extended abstract) [pdf](https://aamas.csc.liv.ac.uk/Proceedings/aamas2025/pdfs/p2795.pdf) | Hearthstone: frozen fine-tuned T5 card embeddings, self-play with Monte Carlo returns, a latent world-model auxiliary loss. Test decks with up to 50% unseen cards; win rate against tree-search levels 0/1/2: 96/76/68% (Cardsformer 82/68/48%). No game counts or variance. | Self-play, not imitation, with cards described by content generalised to unseen cards. Thin evidence. |
| Bertram et al., *Learning With Generalised Card Representations for MTG* (CoG 2024) [arXiv 2407.05879](https://arxiv.org/html/2407.05879v1) | Pick prediction on unseen sets: random 23.79%, hand features 33.57%, all combined 42.87%; on seen cards every representation is about 68%. | Representation only matters off-distribution, the same pattern as our check 6. Measures picks, not play. |

### Fit table

| Approach | CPU, hours | No peeking | Keeps generalisation | Size of change |
|---|---|---|---|---|
| Search-backed value targets (TreeStrap, Goodman) | **breaks** with a heuristic teacher (wrong scale); meets with the net as teacher | meets | meets (same features) | small: keep option values, new target |
| Iterate: retrain on search + net games (Goodman, TD-Gammon) | meets (3–5 rounds of today's pipeline) | meets | meets | small–medium: a loop script |
| Truncated rollouts scored by the net (Tesauro & Galperin) | adaptable (the cost is Python net calls) | meets | meets | medium |
| Deeper search (`sample_k`, 2 turns) (2048) | meets | meets | meets | none: built, untested |
| Ranking loss over sibling afterstates (TD-Gammon's correlated errors) | meets | meets | meets | small |
| Full AlphaZero / Stochastic MuZero | breaks (GPU scale) | meets | meets | large |
| Text / T5 card embeddings (Xia, Cardsformer) | adaptable (encode once) | meets | adaptable (replaces primitives) | large, new dependency |

## Alternative framings

1. **Rank, don't regress.** The agent only compares siblings. Train on
   decision quality (ranking or regret among one decision's options)
   instead of absolute final score. Loses: a calibrated score for reports.
   Enables: a loss that matches how the net is used.
2. **Learn a correction to the heuristic, not a replacement.** Net output =
   heuristic + learned residual. Where the net knows nothing, play falls
   back to the heuristic instead of below it (the sts-rl-agent failure).
   Loses: nothing measured. Enables: a safe first iteration.
3. **Buy depth instead of evaluation.** Try `sample_k > 0` or two-turn
   search with the heuristic first; in 2048, going from 1 to 2 ply added
   41%. Loses: speed per decision. Enables: a stronger teacher for 1 and 2.

## Recommendation

> **Correction (2026-10-24):** TreeStrap's and Goodman's search values are
> on the outcome scale (game results, or an evaluator trained on them). Our
> heuristic teacher's are not, so heuristic search values must not be mixed
> into value targets; use real outcomes, and the net's own search values
> from the first self-play round. See learned-play Amendment 1.

An **expert-iteration-lite loop with search-backed targets**, starting from
framing 2 and measuring decisions directly:

1. Targets: for each decision in self-play, every option's expectimax value
   (already returned by `sts.search`), mixed with the final outcome
   (λ-style), instead of the outcome alone. That is TreeStrap/Goodman on our
   search, and gives each state a low-noise label for free.
2. The net predicts a residual on top of the heuristic; the loss adds a
   ranking term over each decision's options.
3. Iterate: play with search + the current net, retrain, 3–5 rounds. Plan
   for some exploration in the search's choice (Goodman needed it in
   round 3).
4. Gate on play, not MSE: search + net beats search + heuristic at an equal
   node budget, on training and held-out decks, and keeps the
   effects-vs-ids gap.

Why the others lost: full AlphaZero/MuZero needs GPU-scale self-play; text
encoders replace the primitive design this project is testing; truncated
rollouts are a good later step but cost many Python net calls per decision;
deeper search is worth a quick measurement (framing 3) but doesn't fix the
evaluator.

## Checks borrowed from the literature

- **Monotone iterations** (Goodman): each round's search + new net is at
  least as strong as the search that generated its data.
- **Regret per decision on a fixed position set** (Tesauro & Galperin's
  equity loss per move): grade each agent's choice against an expensive
  oracle (deep search or many rollouts) on ~1,000 saved decision states,
  training and held-out. Report beside win rate.
- **Ranking accuracy among siblings** (TD-Gammon): the fraction of option
  pairs a net orders the same way as the oracle. That is what search
  needs, not MSE.
- **Lookahead must not hurt** (sts-rl-agent): search + net ≥ greedy on the
  net ≥ no lookahead; fail loudly if adding search lowers win rate.
- **Fixed node budgets, identical reruns** (Doron): every evaluation uses
  node budgets and seeds; rerunning one configuration gives identical
  results.
- **Held-out split with an id control** (Bertram; already check 6): keep it
  for every new net.

## Not applicable, and why

- AlphaZero / MuZero / Gumbel MuZero at full scale: GPU-weeks.
- Stochastic MuZero's learned model: we have an exact, fast simulator.
- CFR / ReBeL / depth-limited solving: built for two-player zero-sum games;
  StS combat is a single-agent stochastic problem.
- Fixes for PIMC strategy fusion: the unordered draw pile already removes
  the hidden-order "teacher sees the future" problem.
- n-tuple networks (2048): fast, but their authors say they don't
  generalise.
- LLM card encoders (T5, Cardsformer): a different bet from effect
  primitives, with a new dependency; revisit only if primitives stop
  scaling.
