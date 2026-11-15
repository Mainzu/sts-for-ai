# Big-picture review 2026-11-01b

Run 16:50-17:20 2026-11-01 by the manager (workflow `big-picture-review`:
6 analysts, a synthesis, 12 skeptics on 6 key claims; 19 agents). Ran after
the gauntlet first read, the start-HP arms read and depth on generated
powers (results doc, sections of 16:25-16:35). The raw output is not kept;
this file holds what survived the skeptics.

## Manager's reading (read this first)

1. **Where the product stands.** Pooled over 1,000 gauntlet sequences, the
   one-turn champion with the HP bonus clears 0.632 against the
   heuristic's 0.614: +0.018 (se 0.011), level (both halves of the
   sequences agree: +0.020 / +0.016). It wins more boss fights and dies
   more on elites, so its floors won are *lower* (-0.136, z -3.1, replicated
   on sequences 500-999 at -0.110). Skeptics confirmed every number.
2. **Depth is the strongest lever not yet in the product, but "largest"
   is not established at run level.** Two-turn gains +0.055 to +0.118 on
   held-out elites and bosses (fixed-net comparisons, z 3-17), but: the
   train half gains only +0.035; on run-HP depth saves only +0.59 HP; the
   gauntlet's deficit is Gremlin Nob, where depth's measured gain is ~0;
   and whether depth adds on top of the HP bonus is untested (0059l7r1 runs
   now). The two-turn gauntlet (0059l7r2) is the deciding read. Pass bar
   (adopted): clears >= +0.03 over the one-turn champion with the bonus on
   the same 500 sequences.
3. **Training-side work is not dead, but label work at one turn is.** The
   synthesis said only search-time changes moved strength; two skeptics
   called that wrong. Training-side changes that cleared noise: data
   scaling (+0.024 train 5k->40k), coverage (+0.035), the adaptation burst
   (+0.037 to +0.049, every seed; the only nets to pass the ladder over the
   10-29 champion), hp_weight 2 (+2.6 HP, ~10 se). What has never moved
   play: label / loss / curriculum variants (12 arms, median |effect|
   0.007, none at 2 se). The stop list stands for those.
4. **The HP gap was a missing input, not a horizon problem** (skeptics on
   claim 4): one-turn leaves are after End turn, so HP lost this turn is
   visible; what the net lacked was the start HP. Both the start-HP column
   and the bonus fix that. The "delayed value" pattern still fits Demon
   Form, Mode Shift and Nob's Enrage.
5. **Nob is a regression the bonus caused** (skills 1.32 -> 2.28 per
   fight, wins 0.994 -> 0.972). A general fix candidate is a search-time
   price on Strength enemies gain (it is a mechanic, not an encounter, so
   it carries to custom content). Read on `nob_probe.py`, then the
   gauntlet.
6. **Goal 1: new atoms may be a horizon failure.** Post-hoc slice (10
   GainEnergy cells, one net, ~12 slices looked at): net minus heuristic
   at one turn -0.300 (se 0.059) on the generated twin vs 0.000 on the
   original; depth recovers +0.150 (0.054) more there. Every GainEnergy
   power fires at turn start (by construction in `gen_content.py`), so
   "new" and "late" are confounded. Weak evidence (the pre-registered
   whole-bench read is null), but it names a clean test: an unseen atom
   that pays inside the turn against one that pays at turn start.
7. **Queue.** Memory admission made the CPU idle for ~30 min twice today
   (15:39-16:08, 16:19-16:38). Peak memory is unmeasured: a two-turn run-HP
   job uses ~4.7 GB across 6 workers (measured 16:45, free fell to 0.7 GB);
   decisions D2 measured learn rounds at 6.9-8.2 GB. So 6 GB reservations
   are not padded; what's missing is a recorded peak per job, so the
   right size is known. Two pending jobs pointed at reused log files with
   old Tracebacks (false "suspect" flags): fixed.

## Directions, re-ranked (feeds manager.md "Next")

1. **Two-turn product on the gauntlet** (0059l7r2, after 0059l7r1). Pass:
   +0.03 clears over one-turn + bonus. If it passes: an option to play
   two-turn only on elite and boss floors (most of the gain, a fraction of
   the cost), then sequences 500-999 pooled, then promotion by gauntlet.
2. **Job runner records each job's peak memory** (sum of the job tree's
   working sets, sampled each poll) and `jobs.py status` shows it; set
   `mem_gb` from the records per script. CPU-free build.
3. **Profile one two-turn decision by phase** (state copies and stepping,
   legal actions, transposition lookups, chance sampling, leaf
   evaluation). The cut probes say the leaf is only ~25% of 1.1-1.5 s per
   decision; a faster tree multiplies every depth read.
4. **Enemy-Strength price at the leaves** (Nob's Enrage, and any custom
   monster that scales): like the HP bonus, centred and scaled; tune on
   `nob_probe.py`, confirm on the gauntlet.
5. **Goal 1: separate novelty from horizon** with a novelty pack holding
   out whole atoms, one paying inside the turn and one at turn start
   (elite and boss cells, start HP >= 12); plus the Silent tight set with
   the current champion at one turn (~10 min) for a current new-character
   number.
6. **Yardsticks**: replay the 39 ladder tests under a trinomial GSPRT
   (win / loss / agree per pair) offline; the gauntlet as the promotion
   test for product players. CPU-free.
7. Survival-score arms (owner's design; 0059l8a/l8b, after the depth
   reads): they must beat the bonus controls, not the bare ones, and
   should not feed Nob.
8. Headroom anchor: heuristic two-turn on the gauntlet (~24 thread-h,
   overnight), after 0059l7r2.
9. Owner's decision (N6): the engine re-scope toward "everything as data"
   (all card types, characters, monster patterns), since today only power
   cards can be added as data.

## Stop list (adds to 2026-11-01's)

- Training arms aimed at tight2 win rate; any training arm left reads on
  run-HP or the gauntlet and names a new mechanism.
- Using floors won or tight2 alone as product decision metrics (floors
  won flips sign against clears).
- Promoting on a single candidate seed at an SPRT stop with no fixed-size
  check.
- Recomputing deterministic controls (heuristic two-turn sides) instead of
  caching them.

## What the skeptics changed

All six key claims came back "overstated" (one "wrong"): "only search
moves strength" (training-side gains exist), "heuristic two-turn beats net
one-turn" (bosses only, one encounter, Slime Boss; elites a tie), "the
product lacks its largest lever" (the largest run-level lever, the bonus,
is in it), "every gain fixed delayed value" (HP was a missing input),
"the yardsticks pointed the wrong way" (no wrong decision followed: the
bonus was promoted on run-HP), "bookkeeping, not idle time" (the waste is
idle time from memory admission). The reading above uses the corrected
versions.
