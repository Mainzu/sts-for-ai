# Big-picture review 2026-11-02

Run 01:45-02:00 2026-11-02 by the manager (workflow `big-picture-review`:
6 analysts, a synthesis, 12 skeptics on 6 key claims; 19 agents). Ran
after the two-turn `@hpe` gauntlet pass and the Silent read (results doc,
sections of 00:15-01:45). The raw output is not kept; this file holds what
survived the skeptics.

## Manager's reading (read this first)

1. **Where the product stands.** Two-turn search with the champion net and
   `@hpe0.01` clears 0.676 of the 500 gauntlet sequences: +0.060 over the
   one-turn champion with the HP bonus, +0.080 over the one-turn heuristic.
   Every measured step from the bare net (0.448, -0.148 against the
   heuristic) to the product is a search-time change: the HP bonus
   (+0.168, z 9.2), then depth with the end-HP fix (+0.060). Depth's gain
   is HP kept and elites survived: per boss arrival both players win
   about 0.76.
2. **What the net is worth at run level is unmeasured, and that is the
   week's most important open number.** The skeptics rejected "all of the
   lead came from search": no net from before the post-10-29 training has
   played the gauntlet, and the heuristic has never played it two turns
   deep. The anchor job for the second (0059l7r3b1) **failed in 30 s** on a
   nets-only guard in `gauntlet.py` and nobody noticed for 15 minutes.
   Fixed (f5188b8) and requeued as two halves (0059l7r3b3/b4), with a
   one-turn gauntlet of the 10-29 net (0059l7r3b2) in front. If the
   heuristic two turns deep lands near 0.65-0.68, the learned net adds
   little at run level and training arms pause; near 0.60, the net is
   worth improving.
3. **tight2 is not a goal-2 yardstick.** On the same pair (champion with
   and without the HP bonus) tight2 reads -0.0012 over 6,000 pairs and the
   gauntlet +0.168 clears. Gauntlet end-HP (HP left after the boss, 0 on a
   death) agrees in sign with every significant clears difference (11 of
   16 pairs) and needs about 2.5x fewer sequences (range 1.4-3.9), but it
   reads weak on a player that over-prices HP (c = 0.04: clears z -7.3,
   end-HP z -4.4), so it needs a clears guard. Caveats: one net, one
   sequence seed, shared arms; the gauntlet itself (fixed deck, no rewards,
   Ironclad) is assumed, not shown, to stand for goal 2.
4. **The pattern behind the week.** What moved play fixed a bias in what
   search optimises or sees (HP price, floored finish score, horizon);
   most CPU went to cutting noise in labels and evaluators, which never
   moved play. The skeptics softened "winners are always far beyond
   noise": several real effects sat at 2-3.5 se and were dropped by a bar
   or as redundant, and depth itself first looked like a loss until a bug
   was fixed. The lesson kept: look for an unmeasured objective or an
   implementation bias before adding seeds.
5. **Combat headroom is unknown, not small.** The nine players' union
   clears 0.742 and 129 sequences are lost by all, but seven of the nine
   are one net with different HP prices, so that is no ceiling. Which
   sequence is drawn explains ~72% of clear variance, the player ~2%
   (interaction 26%); on a fixed-deck test that is close to built in. A
   different kind of player (rollouts to the fight's end) is needed to
   tell headroom from unwinnable decks.
6. **Throughput.** Jobs booked ~8.5 threads over 62 hours. The
   skeptics put the direct limit on the runner's 2-heavy-job cap with
   3-thread two-turn jobs (sized that way because of 3-4.4 GB peaks), not
   on refused admissions; nobody has measured how much of a two-turn
   worker's memory is the whole-state search tables.

## Directions, re-ranked (feeds manager.md "Next")

1. **Run-level value of the net** (queued): 0059l7r3b2 (10-29 net,
   one turn, `@hpb0.01`) read against
   `2026-11-01-burst8hp2-s1-9f89b6f-hpb0.01-bd6d62.json`; 0059l7r3b3/b4
   (heuristic two turns) merged and read against `heuristic-bcbb0e.json`
   and `champion-hpe0.01-two.json`. Read clears and end-HP.
2. **One measurement protocol for goal 2.** Paired gauntlet end-HP as the
   primary statistic with a clears guard (clears not significantly
   worse), sequential stop (`scripts/analysis/gsprt_replay.py`), cached
   per-sequence files; screen at one turn, confirm at two; keep sequences
   500-999 as a confirmation book (c, `@hpe`, `@esp` were tuned on 0-499).
   First check, CPU-free: replay the sequential rule over the existing
   paired files and check every verdict matches fixed-n clears (c = 0.04
   must fail).
3. **Ceiling probe with a different player: rollouts.** At each decision of
   a fatal boss fight, play each option to the fight's end 16-32 times
   with the one-turn champion and pick the best mean. 30 of the 129
   never-cleared sequences' fatal fights at the product's HP, plus 30
   cleared ones as a sanity check. Wins > 30%: real combat headroom, plan
   cheap deep search on boss floors. < 10%: combat on fixed decks is near
   its ceiling; goal-2 effort moves to deck building. ~1-2 thread-hours.
4. **Depth only where it pays.** Floors 1-3 (the easy hallways) had 0
   deaths in 1,500 fights for every player: play them one turn deep. CPU
   check first: HP lost on floors 1-3, two-turn `@hpe` vs one-turn. Later,
   hash-keyed search tables to cut memory per two-turn thread (engine code:
   coordinate with the engine-next session).
5. **Bias audit.** Generalise `hp_price_probe.py`: perturb own HP, block,
   enemy Strength, Poison, Vulnerable / Weak turns, next turn's energy,
   power stacks in real gauntlet elite and boss states; compare the leaf's
   value change with the play-out outcome change. First: enemy Strength and
   Poison, 300 states.
6. **Card rewards in the gauntlet** (first out-of-combat lever, spec
   CPU-light, no engine-next dependency). CPU-free first check: how much
   per-sequence clear variance deck features explain against the player.
7. **Goal 1.** Read 0059l7r3a9 (horizon replication). Then effects net vs
   its ids twin on the 3-copy generated bench at one turn (is it the
   features or the simulator that generalises?), then mutated monsters
   (enemies as random content are untested; unseen boss + unseen cards is
   the project's worst result, Guardian -0.131).
8. **Runner.** Admit any job that fits memory by priority, not strictly by
   file-name order; dry-run each command's arguments when queued; log
   memory refusals; a thread-hour ledger with each job's family.
9. **Only if rank 3 finds headroom:** cheap deep search (boss floors) or a
   leaf trained on two-turn / rollout *values* at scale.

Survival-score arms (0059l8a/b, the owner's design): the review says park
them (training-side copy of an HP price search already handles, 22
thread-hours, read on ladder run-HP). The manager keeps them queued but
behind ranks 1-3, so they run only when the anchor is in.

## Stop list (adds to the earlier ones)

- Judging any goal-2 candidate on tight2 or the ladder alone; tight2 stays
  a goal-1 check that held-out cards don't get worse.
- Label-quality and recipe arms (exact-label caps, rung 4, curriculum,
  ranking distillation, ensembles, ratchets, bursts > 8 cards, data past
  40k, speculative features) unless a probe first names the bias they fix.
- Sweeping constants on fixed 500-sequence grids; use sequential tests on
  cached files.
- Reporting a promotion's effect at its SPRT stopping point; report fixed-n.
- Treating the exact solver as a throughput target: the lean recipe spends
  under 2% of its time there.
- Using the exact-puzzle set to decide on depth (77% of puzzles at
  horizon 0).
- Queueing a job without a dry run of its arguments.

## What the skeptics changed

- "All of the lead came from search" -> the measured steps are search
  changes, but training's share is unmeasured (both skeptics), and the
  net's edge over the heuristic does *not* shrink with depth (+0.037 ->
  +0.032 on 0044b; Silent +0.008 -> +0.040).
- "Depth's gain sits at the boss" -> it sits in reaching the boss (per
  arrival level, 0.760 vs 0.757); easy hallways are floors 1-3, not 1-5;
  disagreement counts 47 / 17, not 45 / 15.
- "Headroom is small" -> unknown: the union is of near-copies.
- "Winners are far beyond noise, losers inside it" -> overstated: several
  real effects at 2-3.5 se were dropped by a bar or as redundant.
- "Memory limits throughput" -> the 2-heavy-slot cap was the direct
  limit 75% of the time; memory is why the cap can't simply rise.
- Two errors in the results doc, fixed: boss arrivals 445 vs 407 (not
  393 vs 368); the Silent "both reach 0.689" was a cross-half coincidence.

Open questions for the owner: the engine-next series as written (fidelity
first) or the goal-1 shortcut (all card types, characters and monsters as
data); and goal 1's standing headline number (none is tracked today).
