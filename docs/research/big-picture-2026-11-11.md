# Big-picture review, 2026-11-11

The `big-picture-review` workflow (run `wf_2b643c12-8da`, 19 agents: six
lenses, a synthesis, two skeptics per key claim), started by the navigator
at 15:25 after generated-pack-scratch's go. The analysts' full output stays
in the run's transcript; this file keeps the synthesis, the skeptics'
corrections and what the navigator did with each direction. Where a
skeptic corrected a claim, the corrected claim is the one written here.

## Diagnosis

- **Goal 2.** All of the product's strength came in one stretch, 10-29 to
  11-03: the learned leaf, the HP price at the leaves (@hpb, then @hpe), the
  second turn of search, the simulated card chooser and its boss term. The
  headline has stood at 0.834 clears on 0-499 (0.780 on 500-999) since. What
  paid let a decision see consequences it could not see before; a later
  step on the same axis mostly did not (third turn, rollout leaf, leaf
  repairs, label changes, more rounds). The levers with measured headroom
  are in the run layer (the chooser's horizon and own boss, elites, relics),
  which waits for Act 1's content under the owner's Avoid item and
  "Headline card pool and choosers after Act 1".
- **Goal 1.** One strong result: a net trained from scratch on 18
  generated enemy mechanics cut the zero-shot cost of 6 unseen pairings by
  0.76 over three seeds, carried to bosses, stacks and an unseen host
  (`measurement/genpack-transfer@three-seeds`). All of it is new
  combinations of seen triggers and effects. A trigger or effect that no
  training content holds is an untrained input column; nobody has measured,
  in a designed read, what such an atom costs a net trained on a generated
  grid.
- **What holds the project back** is cost per answer and the supply of
  ready work, not raw machine time: booked job threads averaged 3.9
  since 11-03 (6.1 since 11-10), with about 3.9 more cores busy outside jobs
  (sessions, compiles). The runner's waits were mostly for a heavy slot (108
  jobs) rather than memory (39 jobs), and memory waits come partly from
  `mem_gb` set above real peaks (median peak 0.55 of the reservation).

## Key claims and the skeptics' verdicts

All six came back **overstated**; the corrected forms:

1. Every goal-2 gain adopted let a decision see consequences it could not
   see before; some were new mechanisms, some extended one (@hpe over @hpb
   +0.036 clears, the boss term +0.132). Since 11-03 refinements that add no
   new consequence have been flat or negative on official play.
2. The product's fight play is near what more search with the same leaf
   reaches, where measured (exact endgames: regret 0.0063 at its 4 hands;
   floor-9 elites: three turns -0.75 (0.81) HP, underpowered). 140 of 193
   deaths are at the boss; Guardian and Slime Boss deaths are entry-HP
   losses, Hexaghost (half the boss deaths) is lost inside the fight.
3. One turn deep, deck-matched reads cost 17-42x less wall time than
   unmatched ones and have 2.1-3.5x lower paired variance (they skip the
   chooser's trial fights); two turns deep the saving nearly disappears
   (0.48x time, 1.27-1.63x sd). The project already uses them for one-turn
   fighter questions (`decision/matched-reads`).
4. The CPU is not saturated by booked jobs, but the binding limits are the
   two-heavy-slot cap, the supply of ready work and reservations above real
   peaks, more than memory; other processes on the machine hold several GB. The `cpu` health
   metric counts booked threads only, so its red says little.
5. Goal 1's cut is transfer to unseen pairings of seen atoms. Unseen atoms
   were measured only on older nets (WeakOnHit's untrained trigger +1.74
   (0.34) HP one turn deep, cut 78% by a SharpHide net; new-atom cards that
   land inside the turn cost nothing). `wider-generators`' whole held-out
   trigger and effect (Attacked, Wound, per its spec on the lane branch) are
   trained elsewhere on purpose (Flame Barrier, status cards), so they read
   "seen elsewhere, new on an enemy", not a brand-new primitive; under
   one-hot names a brand-new primitive cannot transfer zero-shot at all.
6. Training pays where content is new to the old net (the 31-card pack,
   unseen generated pairings); recipe changes on known content are null
   within noise; a single-seed tight2 gate passes a null recipe 13-18% of
   the time.

## Directions (the synthesis' ranking) and what the navigator did

1. **Memory hygiene** (idle sessions, rust-analyzer in role sessions): the
   steward's and the launcher's domain, noted in `jobs/roles.log` for the
   steward; `cause/memory-holds-bursts` re-set from two fresh measurements
   (1.05 GB free at 14:45, 3.62 GB at 15:25).
2. **Pick book for matched reads**: block 1000-1499 queued (job 0895, lane
   main, the one-turn control unmatched); blocks to 2999 follow if it runs
   in its estimate. Lowers the matched floor from about 1.0-1.3 HP toward
   0.5 for fighter questions on both goals.
3. **wider-generators before step 3**: charter amended (decisions "After
   the big-picture review of 2026-11-11"): the spec states for each held-out
   atom whether official or player content trains its column, a step-2b
   column ablation on the generated-pack seed-1 net measures how much of the
   0.76 cut rides on the atom's name, and the step-3 learn lists the row
   kinds it turns on. Whole-atom rows stay descriptive.
4. **Control-arm cache in mutate_monsters** (about 30 thread-h of identical
   heuristic arms replayed): tooling, backlog entry 59, for a lane worker
   while its lane waits on CPU.
5. **Generated-pack nets at product depth**: the ready charter
   `genpack-product-depth` (backlog 60, merging 52), with the probes of this
   run as evidence (below).
6. **Sparse feature cache in learn.py**: tooling, backlog entry 61; it pays
   once from-scratch learns are the recipe (53's step 3, 60's seeds).
7. **Chooser noise and own boss**: the re-scores are 55 (`chooser-noise`);
   the own-boss exception is the owner's to make (the Avoid item); listed in
   roles.log for the digest as a notice, not a question.
8. **Luck correction, read side first**: `lane/luck-corrected-labels`
   re-set so the read-sd ratio is step 1's main result.
9. **Offline stronger-teacher check**: folded into 40's step 1 (root values
   against outcomes are the same data).
10. **Hexaghost three-turn probe**: stays parked (10, `hexaghost-headroom`);
    8.2 GB peak against 2-4 GB free.

**Stop doing (adopted where they don't contradict an owner decision):** no
goal-2 lane whose only change is labels, an input column or a leaf number on
official content (`decision/no-goal2-training-arms` already); no more
in-fight search refinement on elites and endgames; no unmatched one-turn
headline reads for fighter questions; no single-seed recipe acceptance.
Not adopted: "no more bursts on the frozen net for later ticks". This run's
probe 0890 found the 5k bursts carry their later-ticks value to unseen
generated powers as well as the from-scratch twins do (+0.078 against
+0.076 wins), so `card-later-ticks-burst` finishes its queue on the record.
Not adopted either: changing goal 1's standing number
(`decision/goal1-yardstick` is the owner's).

## This run's probes (navigator, 2026-11-11)

**gen-powers-later-ticks (0890) and genpack-gen-powers (0891)**, control
re-run 0893 (the 10-29 net @tsl1 at today's pin, identical to the 11-07
file on all 7,824 fights). Each net @tsl1 minus the 10-29 net @tsl1 on the
generated-power bench's elite and boss fights, mean over cells (se over
cells), wins:

| nets | generated recurring (OwnerTurnStart/End, 34 cells) | other generated (52) | Demon Form originals (44) | Metallicize originals (42) |
|---|---|---|---|---|
| all-content twins 40k s1, s101 | +0.076 (0.028) | -0.001 (0.019) | +0.029 (0.021) | +0.070 (0.024) |
| all-content 20k s1 | +0.069 (0.035) | -0.022 (0.021) | -0.021 (0.026) | +0.071 (0.027) |
| all-content 5k s1 | +0.049 (0.025) | -0.008 (0.022) | +0.004 (0.022) | -0.004 (0.039) |
| fslt 5k bursts s1-s3 | +0.078 (0.018) | +0.021 (0.013) | +0.008 (0.017) | +0.060 (0.020) |
| generated-pack nets s1, s101, s201 | +0.060 (0.026) | -0.004 (0.019) | -0.003 (0.019) | +0.063 (0.022) |

Every one of the ten nets gains on the generated recurring powers (+0.03
to +0.09 per net); none gains on the other generated powers. The 10-29
net @tsl1 sits -0.049 (0.040) wins below the heuristic on OwnerTurnStart
powers and -0.072 (0.052) on OwnerTurnEnd, so these nets close that gap.
Read: a net that learned a power's later ticks from games (from scratch
with the power in its pool, or a 5k burst) carries the value through the
effect inputs to recurring powers no game held. The Demon Form sanity
slice is small on this bench (wins, low-HP fights), where the cells showed
+2.7 to +3.3 HP. Both probe rules pass: 0890 (+0.04 at 2 se) and 0891
(+0.04 at 2 se, other generated not below -0.03). One turn deep, wins only.
