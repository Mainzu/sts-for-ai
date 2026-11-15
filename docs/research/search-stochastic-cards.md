# Prior art: search and learned play in stochastic card games (2026-10-31)

Started by manager run 5cbfc037. Why now: our strongest player is
two-turn search over a learned or heuristic value (+0.06 wins over
one-turn on held-out elites and bosses), but it is ~145x slower than
one-turn play, and training the net on its choices (distillation, ranking
target) lost -0.03 on elites over 3 seeds. Depth also looks like a repair
for mechanics the net mis-prices (Guardian gap closed, unseen power cards
gain most). Goal 2 needs a stronger player and a teacher stronger than its
student; this scan asks how other fields get both.

## First principles

- Wanted: the highest win rate per CPU-second in a single-player combat
  against scripted, partly random monsters, and a training loop whose
  teacher beats its student.
- Per decision: the full state (hand, draw pile contents but not order,
  discard, HP, powers, monster intents for this turn) -> one option (play
  a card with targets, or end turn). A turn is several decisions; chance
  enters at draws, shuffles and the monsters' next moves.
- Constraints:
  - **hard**: CPU only (one consumer machine, a few heavy jobs at
    once); a perfect simulator is available (our Rust engine); content can
    be generated or new (goal 1), so nothing may rely on a fixed card list.
  - **hard**: the draw order is hidden; the deck's contents are known.
  - **soft**: one-turn play stays cheap enough for self-play data (tens of
    thousands of games per round).
  - **assumed**: search depth is counted in player turns, with chance
    sampled (sample_k = 4 draws per next turn); the value net scores
    leaves; training targets are the net's own option ranking plus
    win/score.

## Search

Eight angles, one paper-scout each (cards in
`docs/research/search-stochastic-cards/cards/`): chance nodes in MCTS and
expectimax; expert iteration and search distillation; determinization
and hidden information; card-game bots (StS, Hearthstone, LoCM,
Dominion); backgammon and shallow expectimax; search with noisy values;
where to spend search (metareasoning, ranking and selection, from
operations research); search on top of a learned blueprint (Hanabi,
poker, rollout policy improvement). About 66 sources opened, ~64 carded.
I opened 7 myself (Rubin 2026, sts-rl-agent, Tesauro & Galperin, ExIt,
TDLeaf (abstract page only), "Surprising difficulty of search",
V-MCTS); the numbers I checked held. Two cards needed corrections:
sts-rl-agent's card left out the page's own reason for its failed
distillation (below), and the backgammon card had no authors for
Tesauro & Galperin and TDLeaf (Baxter, Tridgell, Weaver). TDLeaf's
"2-ply beats 1-ply by 0.25 ppg, 24% of moves differ" is from the card
only.

**A suspicion checked on our side.** sts-rl-agent says its six attempts
to distil MCTS combat into a net all failed because "the MCTS teacher
effectively sees the future draw order". Our two-turn search does not:
the draw pile is a multiset (`state::Pile`) and `resolve_chance` draws
from it with the search's own `sample_rng`, never the game's RNG
(`engine/src/chance.rs`, `engine/src/search.rs`). So our depth gain is
not clairvoyance.

## Shortlist and fit

Hard constraints: CPU only; perfect simulator; new or generated content;
hidden draw order. Each cell: meets / adapt / breaks.

| source | what it shows | CPU | sim | new content | hidden draws | size for us |
|---|---|---|---|---|---|---|
| Rubin 2026, LoCM unsound search (arXiv 2609.06816) | sampled-world search over a policy+value net lifts the net from 26.8% to 51.35% vs the champion (10,000 certified games); a random card pool every game; deeper search didn't help, beam width did; sampled worlds saturate at ~32; 4x data +8 points | meets (GPU box, but inference only) | meets | meets | meets | nothing to adopt; evidence for what we do |
| sts-rl-agent (HF, Jialeiv) | StS A0: MCTS combat + learned non-combat 14% vs 6% wins over 50 seeds; six distillations of MCTS combat failed (imitation accuracy capped at 0.44) | meets | meets | breaks (fixed card list) | breaks (teacher saw draws) | yardstick only |
| Expert Iteration, Anthony et al. 2017 | the apprentice only reaches its expert (wins just over half vs the MCTS it imitated); progress comes from putting the apprentice back inside search; cost-sensitive targets (tree policy) beat chosen-move targets at equal prediction error | adapt | meets | adapt | breaks | medium |
| Tesauro & Galperin 1996 (arXiv 2501.05407) | one rollout-improvement step over a learned base cuts its error 2.5-6.6x; candidates are pruned statistically before expensive evaluation | meets | meets | meets | meets | the idea is our fallback / top-k already |
| "Surprising difficulty of search in MBRL" 2026 (arXiv 2601.21306) | search on a learned value amplifies over-estimation of uncovered actions; the minimum over a value ensemble fixes it | meets | adapt | meets | meets | small (needs an ensemble evaluator) |
| Miłoś et al. 2019, ensembles in planning | mean + k*std of a value ensemble inside a tree, big gains in sparse tasks; k tuned per domain | meets | meets | meets | meets | small |
| V-MCTS 2022 (arXiv 2210.12628) | stop searching when the policy stops moving: 71% vs 75% win at about half the search | meets | meets | meets | meets | small-medium |
| Adaptive lookahead, Rosenberg et al. 2022 | pick depth per state from the value estimate; needs a value-error bound | adapt | meets | meets | meets | medium |
| Monte Carlo *-minimax 2013 | sample c chance outcomes, prune on top; 1-25 samples used, no general rule | meets | meets | meets | meets | ours already |

## Alternative framings

1. **The product is "net + search at play time", not "a net that plays
   alone".** Every strong result here keeps search at decision time
   (Rubin, TD-Gammon's 2-ply, Hearthstone, poker); distillation into a
   searchless net is the weak link in ExIt and failed in StS
   (sts-rl-agent) and for us. What changes: train the net to be a better
   *leaf* (lower noise, less over-estimation) and measure the two-turn
   player as the product. What the goal loses: nothing; one-turn play
   for self-play data stays as it is.
2. **Spend depth only where it changes the move.** A cheap gate
   (one-turn's top-2 value gap, or V-MCTS's "policy stopped moving")
   picks which decisions get two-turn search. That could make the
   two-turn player cheap enough to *play self-play games*, so the value
   net learns from the stronger player's outcomes (ExIt's actual loop),
   rather than from rankings of single decisions.
3. **Change the distillation target, not the teacher.** ExIt and
   Gumbel MuZero say cost-sensitive targets (search values per option,
   tree policy) beat hard choices; our ranking term is closer to a hard
   choice. Lowest priority: distillation is closed and the other two
   framings don't need it.

None adopted; listed for the owner.

## Recommendation

Under framing 1, the simplest option is a **seed-net ensemble as the
leaf evaluator**: average the value of the champion and its two seed
twins (`runs/2026-10-29-seed-check-r2-s1/s101/s201`, same recipe) at
every leaf. No training; inference 3x, small next to two-turn search's
145x. Two sources expect it to reduce search's over-estimation
(Surprising difficulty; Miłoś), and an average of seed nets also cuts
the seed-luck noise we keep measuring (sd ~0.010-0.013). It was proposed
and never built three times here (decisions ~line 622, manager archive,
review 10-30). Check: ladder the one-turn ensemble against the champion;
then two-turn ensemble vs two-turn champion on held-out elites and
bosses (paired, fallback player). After that, framing 2's gate, measured
offline first.

## Checks borrowed from the literature

- Rubin's PIMC properties as a sample-size check: run the same decision
  with two independent sample sets (two `seed`s) and count how often the
  chosen option differs. A high rate at sample_k 4 means two-turn search
  is under-sampled (Rubin saturates at ~32 worlds). sample_k has only
  been compared on the old heuristic teacher's regret, never on wins.
- ExIt's student-vs-teacher match: when a net is trained from a search
  player, report its win rate against that player, per round.
- V-MCTS's trade curve: win rate against the share of decisions given
  two-turn search, for any gate.

## Not applicable, and why

- ReBeL, DeepStack, CFR, depth-limited solving: two-player zero-sum
  beliefs over an opponent; our only hidden thing is nature's shuffle.
- Stochastic MuZero: learns a chance model; we have the exact one.
- alpha-mu: needs an exact perfect-information solver at every leaf.
- Belief mixing (public vs private): no opponent to leak to.
- Bayesian / Thompson tree search with learned uncertainty: its own
  paper found learned uncertainty too poor to help.
- Hearthstone value nets on card embeddings: a fixed 483-card list.
