# Big-picture review, 2026-11-12

The `big-picture-review` workflow (run `wf_a60e78c4-7a7`, 19 agents: six
lenses, a synthesis, two skeptics per key claim), started by the navigator
at 15:50 on its daily date wake. The analysts' full output stays in the
run's transcript; this file keeps the synthesis, the skeptics' corrections
and what the navigator did with each direction. Where a skeptic corrected
a claim, the corrected claim is the one written here.

## Diagnosis

- **Goal 2.** The product has not changed since 2026-11-03
  (`configs/product.json`, `product/net`). About 865 of 1,550 booked
  thread-hours ran after that and nothing was adopted for goal 2. The
  candidates of that stretch read about +1 to +1.6 HP and no clears,
  under the headline's detectable difference between nets (about 2.5 HP
  or 0.06 clears at 500 sequences, `cause/headline-pairing-weak`).
- **What the goal-2 ruler credits.** On the matched reads of official
  content, almost all of the end-HP gain is HP left on sequences both
  players clear: the all-content twin two turns deep +1.41 (0.45) =
  +0.09 from clear flips + 1.32 left on shared clears, +0.014 clears
  (about 1 se); one turn deep +1.69 = -0.01 + 1.70; the SharpHide-stage-B
  net two turns deep +1.08 = 0.01 + 1.07. Most of that HP is saved inside
  the boss fight. A real effect splits differently (two turns over one:
  +6.14 = 3.68 from flips + 2.45 left). Not every candidate fits: the
  SharpHide net one turn deep (+2.47) has 1.09 from flips and +0.040
  clears. Whether HP left after the Act 1 boss is worth anything depends
  on the act transition's heal (full below Ascension 5, 75% of missing HP
  at A5+, from sts_lightspeed and memory; not yet checked against the
  decompiled code, `decision/parity-source`).
- **Fight play.** Depth has stopped paying on the floor-9 elites at the
  power tested (three turns -0.75 (0.81) HP on only 48 fights, rollout
  leaf +0.67 (0.31) worse, 16 hands 0.34 (0.16)). That does not show in-
  fight play at its plateau: the endgame regret 0.0063 comes from
  puzzles inside the search's own two turns (on the 34 puzzles three or
  more turns from the end regret is about 4x higher, few puzzles), depth
  was never probed on bosses, and the second turn still adds +0.083
  Hexaghost wins at fixed HP. Most run deaths are at the boss (140 of
  193), most of them entering under 60 HP after about 31 HP lost at the
  two elites.
- **Goal 1.** The working method is from-scratch training on a broad
  generated pool: the 18-mechanic recipe cut unseen enemy pairings 0.76
  over three seeds (`measurement/genpack-transfer@three-seeds`), and one
  seed of the wide recipe (58 training mechanics over 9 triggers and 12
  effects) cuts the new held-out pairs 0.94 (0.04) and a whole held-out
  trigger 0.91 against pack-net-scratch (0916, read early; the lane's
  read 0921 is pending). Every one of those mechanics is a single
  (trigger, effect) hook, and "unseen" means an unseen pairing of atoms
  whose input columns other content trains. The player side had an
  earlier, weaker try (gen-training-arms, 16 and 128 generated powers, 3
  seeds, 10-31: no transfer, gen128 -0.006 (0.010) wins), then bursts and
  zero-shot reads; never the from-scratch broad pool. The heuristic is a
  shared offset in the enemy-side cut (it cancels in the gain); the
  "blind to 84%" figure belongs to player-side generated cards.
- **The machine.** Jobs book about 31% of the machine's threads (1,550 thread-hours
  over 13.1 days); the runner's measured idle at job starts has a median
  of 10 logical CPUs. The two-heavy-slot cap with mostly 3-thread jobs
  books at most about 37.5%, so the `cpu` metric is red by construction
  (111 of 118 steward runs). The fixes (sparse feature cache, control-arm
  cache, admission) were filed by three reviews as work "a lane worker
  builds while its lane waits", and none was built.

- **0929 and 0930 are not stalled.** `jobs.py`'s stall check reads only
  the job log's age (`log_age_min`); `mutate_monsters.py`'s product mode
  writes progress to `<out>.partial` (666 of 938 fights each at 16:09).
  Their 130-minute estimate is about 2.3x too low; both should end about
  17:35.

## Key claims and the skeptics' verdicts

1. **Overstated.** Goal 2's adopted gains came from several kinds of
   change: search, objective and chooser changes (HP price +0.168 on
   cells, sim rewards +0.184, boss horizon +0.132, two turns +0.154 on the
   screening book and +0.086 held out), and one training gain (the 10-29
   net). Changes that added foresight failed about as often as they paid
   (vrun, three turns, rollout leaf, sampled-draw leaf, the turn-start
   leaf on the headline, the value chooser). "Simulation pays 6 of 6" is
   wrong; "nothing adopted since 11-03" holds.
2. **Overstated.** The corrected form is the paragraph "What the goal-2
   ruler credits" above.
3. **Overstated.** The corrected form is the paragraph "Fight play" above.
4. **Overstated.** The corrected form is the last part of the paragraph
   "Goal 1" above (single-hook, enemy side, the earlier player-side try).
5. **Overstated** (one skeptic: holds; the other: overstated). The CPU
   is underused, by less than 30% suggests: jobs booked 1,550 thread-h
   over 13.1 days (4.9 threads on average), but measured load at
   job starts runs about 3 cores above booked, so real use is about
   45-50% of the logical threads. Three
   sources: about 69 h with under 8 threads booked and nothing queued (no
   work supplied); 64.6 h where the two-heavy-slot cap held a ready job
   (the most-logged wait by distinct jobs: 115, against 32 for memory and
   19 for threads); 115.5 h where a ready job waited with free slots, on
   memory reservations and free-memory checks (the 8.8 GB dense feature
   cache, other processes' memory, the measured-idle check). The `cpu`
   metric (booked share against 8 threads, `scripts/health.py`) is red
   almost by construction under the two-slot rule, so its red does not
   confirm the underuse on its own.
6. **Holds.** The STALLED flag on 0929/0930 is a false positive.

## Directions (the synthesis' ranking) and what the navigator did

1. **Goal-2 decisions on clears, sequential stopping, staged rulers.**
   Backlog 69 (`clears-statistic`), with its no-CPU first check (replay
   the protocol on end HP and clears over the recent against-reads; look
   up the act-transition heal in the decompiled code). Not a lane: goal 2
   has no candidate in flight (`decision/crossed-player-lead`,
   `decision/no-goal2-training-arms`), and a protocol change waits for
   the replay.
2. **Throughput lane, built before 11-14.** Backlog 66
   (`machine-throughput`, merging 59 and 61), ready charter for the first
   free project slot: sparse feature cache, control-arm cache, the stall
   check reading `.partial` files, a replayed slot-count change adopted
   only on the replay's evidence, `test-full` files in parallel.
3. **Row ablation (wider-generators step 2b).** `lane/wider-generators`
   amended: the lane closes only after step 2b reads on the seed-1
   generated-pack net and on the wide net. It decides 62 against 64.
4. **Player-side generated pack, from scratch.** Backlog 67
   (`player-genpack-scratch`), rated a long shot by the trade-off rule
   until a cost shows: every net reads -0.022 to +0.021 wins against the
   10-29 net on the non-recurring generated cells, and no file shows a
   net behind the heuristic there. Its no-CPU check comes first; probe
   0934 (the wide net on the bench) runs beside it.
5. **Chooser-noise check.** Stays backlog 55; goal 2, cheap, under the
   Avoid item as a ruler check.
6. **An absolute anchor for goal 1, and the first multi-hook read.**
   Backlog 68 (`multi-hook-zero-shot`), with a two-turn subsample column
   that does not lean on the heuristic; waits for a recorded wide base.
7. **Offline run-value fit.** Not taken now: run-level work waits for
   Act 1's content (direction's Avoid item); `run-value-plan` is on file.
8. **Clairvoyant headroom for elites and Hexaghost.** Not taken now; the
   depth family is closed (`decision/depth-family-closed`), and the
   corrected claim 3 points at bosses, which 10 (`hexaghost-headroom`)
   already holds as parked.
9. **Goal 2 may train on all official content (decision only).** Not
   decided: it touches "Headline card pool and choosers after Act 1", an
   owner decision (2026-11-09). A notice for the owner.
10. **Character as data.** Stays backlog 41.

The navigator's own addition from the wide-net files: no generated-pack
net has been read on the owner's yardstick rows
(`decision/goal1-yardstick`). Probe 0931-0933 (`genpack-yardstick`) reads
the wide net, pack-net-scratch s1 and the 10-29 net on them, and 65
(`wide-recipe-confirm`, seeds 101 and 201 of the wide recipe) is the ready
charter for the next free project slot.

**Stop doing (adopted where they don't contradict an owner decision):**
goal-2 fighter swaps and recipe arms on the same content; hand-set leaf
prices and run rules; depth, hand counts and rollout leaves as goal-2
strength work on elites; filing machine-wide fixes as work for a lane
that waits; replaying heuristic control arms already on file at the same
pin; treating log silence as a stall for jobs that write `.partial`
files. Not adopted yet: accepting or rejecting on clears instead of end
HP (69's replay first, `yardstick/protocol` stands); "widening the
single-hook grid is used up" (the wide net's training rows read +0.03 HP
and held-out pairs +0.25, so more single-hook width has little left to
cut one turn deep; the next width is multi-hook, 68, and the yardstick
read decides whether the grid reaches official mechanics); quoting
0.834 (already quoted as 0.78-0.81, `decision/headline-quote`).

## Open questions from the review

- The act transition's heal in the decompiled code (69).
- Does the wide net's cut survive 0918/0919 and a second seed (65), and
  any cut survive an atom with no example in the pool (62/64 via 2b)?
- How often do the sim chooser's picks flip under another trial-seed base
  (55)?
- Should goal 2's CPU share be lent to goal 1 while goal 2 has nothing
  decisive to run before Act 1's content lands? A `docs/direction.md`
  question, the owner's; a notice in the roles log.
- Can a combat run with future draws fixed and visible to search (8)?
- Does the 11-14 switch to one session free enough memory to change
  admission (re-measure then, 66 (d))?
