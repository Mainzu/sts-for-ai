# Big-picture review 2026-11-03

Run by navigator a5cb4157 at 13:55-14:30 after the headline control moved to the
stepped player (0.834 clears, `measurement/headline@two-turn`) and the
cheap-depth lane closed (workflow `big-picture-review`: six analysts, a
synthesis, two skeptics on each of six key claims; 19 agents). Raw output
kept in the session; this file holds the navigator's reading, the synthesis
and every skeptic verdict as its corrected claim.

## Navigator's reading

- **The skeptics cut the synthesis's one-mechanism story.** The leaf's
  flatness is real (Strength under-priced 3-6x, Poison 1.5-25x and
  non-monotone, `results/probes/bias_audit*.json`) but it is not shown to be
  horizon-shaped, and it is not shown to cause the elite HP leak: two-turn
  search cuts the HP lost on the two elite floors by only 0.5-1.6 of 14-17 HP,
  a right-sized Strength price (@esp0.04) saved none and lost clears, and the
  heuristic leaks as much. So the "horizon-complete leaf" (direction 4) is a
  CPU-minutes screen in the backlog, not a lane, and the depth-headroom lane's
  elite probe is the test that decides whether combat depth has headroom
  left.
- **The CPU story is a sizing policy, not memory.** Booked threads were
  63/48/34% of the threads on 10-31 to 11-02 with a job running 91-100% of minutes;
  the runner refused on memory twice in 282 starts, while both heavy slots
  were full with a heavy job waiting 71-78% of each day, booking 6 threads
  (two 3-thread jobs). A 6-thread two-turn job peaked 5.4 GB. Decision: lane
  jobs are sized at 4-6 threads when memory fits (the owner's cores rule
  allows all cores while they are away); two heavy jobs at once stays.
- **The headline ruler is coarse and its pairing is weak between nets.**
  MDE at 500 sequences is 0.047 clears / 1.6 HP for same-net variants and
  0.06-0.07 / 2.5 HP between nets; 0.005 clears would need 44k-80k
  sequences. Pairing buys ~1.2x between nets on the headline (corr of clears
  0.3-0.5, paired end-HP sd 20) against ~4x on cell decks (0.8, sd 9),
  because the sim chooser diverges the decks after floor 1. The cheapest
  repair is a deck-matched read (replay the control's recorded picks into
  the candidate's run; Python only, first check 0.5 thread-h): top backlog
  candidate, opens when a lane closes. End-HP is already the protocol's
  tested quantity with clears as the guard, so no rule changes.
- **The plain control's half swing (0.852 vs 0.756) is not replayed.** Both
  skeptics found no code channel (same command, module, sequences and
  schema, 5 minutes apart; no engine swap in the window); one calls it
  chance, one an unexplained reproducible weakness of the plain player on
  250-499. Either way the stepped file is the control and a 4 CPU-h replay
  decides nothing we act on.
- **Training.** "No training gain" is about post-10-29 arms: the 10-29 net
  itself is a +0.146 clears training gain over the heuristic at equal depth,
  and most later arms were never read at run level (tight2 killed them, and
  tight2 ranks nets wrongly for run level). `decision/training-stops` stands.
  The two-turn round, the one arm with a stronger teacher, ended during this
  review: the raw logs show protocol fails at n 120 (s1, 0.640 clears), n 119
  (s101, 0.587) and n 179 (the one-turn control arm, 0.610) against the
  one-turn control's 0.680. The two-turn-round lane reads it (why the
  fine-tune hurts, per the reading rules); on its `done:` the lane closes and
  the outcome-label family closes on this dev machine, with ideas #70, #67, #65,
  #50 parked for good.
- **Run layer.** Same order as depth, not larger: random to sim +0.184, sim to
  sim-boss +0.132 at n 500, one-turn to two-turn +0.154. Card rewards are
  already inside the headline; the omitted decisions (removal, rest, path,
  relics) carry measured levers of about +0.04 clears / +1.5-1.8 HP each, two
  failed choosers (winner's curse over 6-9 options at 16 sims) and no relic
  data. The run-decisions lane stands; the "mini-run" headline (an elite
  payoff and one path choice, designed before the next candidate batch) and
  a margin rule for the sim choosers go to the backlog.
- **Goal 1.** The generated-powers bench cannot separate "depth generalises"
  from "the generated cards are weak": heuristic, ids net and effects net all
  land at 0.39-0.41 under two-turn search, and the reference heuristic prices
  14% of the test powers. Not every goal-1 read was blind (check 9 and the
  oracle arm used content-aware nets), but the bench's cells and card
  pricing come from the heuristic. The goal1-yardstick charter is amended:
  the product is subject and reference (novelty cost = informed minus
  zero-shot, after a short burst); the heuristic is a floor, never the
  reference.
- **Arena.** Decided today in "Navigator's first defaults" (level 1 on this
  engine; level 2 waits for StS1). The review adds one exploration check: does
  the strongest outside bot (sts-ironclad-agent, 50.1% A20 Heart over 501
  runs) peek at the draw order; if so its number is not comparable with a
  no-peek player.

## Diagnosis (synthesis)

The six analyses agree on more than they disagree, and the agreement is the
diagnosis. Against goal 2, the project stands at 0.834 clears on an 11-fight
Act-1 gauntlet, up from 0.534 for the hand heuristic, and every step of that
chain came from one kind of change: handing the player, at decision time,
information its value net could not learn from its own one-turn self-play
(the price of HP, the second turn, the deck's future, the boss ahead).
Fifteen-plus training arms moved per-fight proxies by 0-0.02, four passed a
gate, and (the synthesis said) all four were reversed by a better ruler; no
net trained after 2026-10-29 beats the 10-29 net at run level, and that net
is a first-week recipe. The synthesis read the mechanism as one: with the
teacher equal to the student, the leaf is a cache of its own one-turn
outcomes, so anything that pays after the pause point is under-priced 4-6x,
and that under-pricing is both goal 2's HP leak on won elite fights (78% of
pre-boss HP lost on floors 6 and 9 while winning them 97-99%) and goal 1's
novelty cost. Goal 1 then stands better than its lack of a number suggests:
the simulator plus two-turn search is what generalises, the effects encoding
only buys graceful failure at zero shot, and every goal-1 bench so far was
read against a reference blind to most of the content. What has been holding
the project back is not the scarcity of CPU but how it is spent: the machine
was 63%, 48%, 34% and 10% booked on the last four days, a lane's
job-to-read-to-next-job link costs 2-3 hours of wall time regardless of CPU,
and Claude's code time has gone into reads that fit one wake-up rather than
into the drivers, the variance cuts and the run layer that would double what
each CPU-hour buys. The ladder of effect sizes (recipe about 0, evaluator
+0.04-0.06, horizon +0.06-0.15, HP price +0.17, deck +0.18-0.36) points one
level higher than anything built: which fights to take, relics and a path,
which is goal 2's remaining headroom, the only route to a number comparable
with outside bots, and the owner's headless full-game subgoal. The project's
next phase is therefore mostly code (drivers, pairing, the run layer,
generator breadth) with CPU reserved for a handful of decisive reads. (The
skeptic verdicts below correct several of these statements; the navigator's
reading above is what stands.)

## Key claims and skeptic verdicts

**Claim 1.** Every durable strength gain came from supplying information at
decision time, and no training change has moved run-level play since
2026-10-29.
- Skeptic 1: **overstated.** Since the 10-29 net, every gain on the run-level
  ruler came from the search side (HP price, two-turn depth +0.124 to +0.154,
  sim rewards +0.184, boss horizon +0.132 to +0.155) and none of the ~8
  post-10-29 nets read at run level beats the 10-29 net. But the 10-29 net is
  itself a training gain of +0.146 over the heuristic; of the ladder's 4
  passes one stands (the 10-29 net), one reversed (burst8hp2), two are level
  or unread (burst8 s1/s101); training does move run-level play, newer nets
  lose 0.06-0.15 clears; most arms were never read at run level because
  tight2 killed them first; training proper took ~272 of 677 thread-hours
  (~370 only if ladder and bench reads count).
- Skeptic 2: **overstated.** Same correction; adds that depth and the chooser
  pay more with the net than with the heuristic (not a search-only story),
  that ~0.03 recipe effects (the solve step) are unresolved, and that the
  +0.168 HP-price figure is burst8hp2 on cells, not the 10-29 net on the
  headline.

**Claim 2.** The leaf's error is a horizon error, under-pricing 4-6x effects
that pay after the one-turn pause, and this one mechanism is both goal 2's
HP leak and goal 1's novelty cost.
- Skeptic 1: **overstated (refuted).** The leaf responds weakly and
  inconsistently to Strength (ratio 0.17-0.27), Poison (0.04-0.65,
  non-monotone, per-state sign agreement 53-65%) and to current HP (an
  already-paid quantity, 10-100x under in hallways), so the flatness is not
  specific to post-pause effects. Two-turn repairs the novelty cost of
  turn-start effects, Poison and SharpHide but not card-played generated
  powers (-0.156) or Silent tier-A decks. For goal 2, two-turn recovers only
  1.6 and 0.5 HP of the 17 and 14 HP lost per elite and a right-sized
  Strength price lost -0.020 clears; the HP leak is not shown to be the
  horizon error (depth-headroom lane).
- Skeptic 2: **overstated.** Strength about 3-6x (~3x on elites), Poison
  1.5-25x, on both nets. Whether the bias is horizon or training coverage is
  untested (no two-turn audit). The link to the HP leak fails three tests:
  the net that under-prices more clears more; @esp0.04 saved no elite HP;
  depth cuts elite loss by 0.5-1.6 HP while the heuristic loses as much or
  more. Boss clears rise ~0.012 per HP over 30-80 (0.007 over 60-80, one-turn
  replay player); HP pricing and deck choice are separately measured levers
  of comparable size.

**Claim 3.** The machine is half idle and memory-capped, the project's own
drivers are the cause, and most of the speed-up costs zero CPU.
- Skeptic 1: **overstated.** Booked 63/48/34% holds (actual CPU use lower
  still); the cause is the runner's heavy-slot cap of 2 with 3-6-thread jobs
  (both slots full with a heavy job waiting 71-78% of each day, booking 6-12
  threads); today the queue ran empty 320 of 861 minutes. Memory is not the
  cap (2 memory waits in 282 starts; 6 threads two-turn peaks 5.4 GB).
  0067/0068's pace drop is the elite-to-boss boundary in spec order, not
  test-full. The speed-up is zero-CPU: raise heavy slots or threads per job
  keep the queue fed; the heuristic cache (~3 min
  per learn job) and the gauntlet block size are smaller and untested.
- Skeptic 2: **overstated.** Same; adds that logical threads overstate the cores,
  so the share overstates capacity, the runner's own idle readings
  show real use below booked, the heuristic tight-fight recompute is at most
  ~6% of booked thread-minutes, the one-turn gauntlet's thread scaling rests
  on one minute-resolution pair, and contention on 0068's first chunk was
  ~1.4x, not 2x. Lane latency (0066 read 2h38m after it ended; wakes and a
  cancel refused; 0075 pinned pre-fix and sure to fail) is verified.

**Claim 4.** The headline ruler cannot see Stockfish-sized increments, the
move to the headline setting broke the pairing, and the plain control's half
swing is chance, not code.
- Skeptic 1: **holds.** MDE 0.047-0.062 clears (1.6-2.4 HP) at 500; 0.005
  clears needs 44k-77k sequences at 8.5 thread-h per 500. Twins' clears
  correlate 0.73-0.82 on cells vs 0.27-0.47 on the headline, paired end-HP sd
  9-11 vs 20-22, identical decks in 0-3 of 250. Half swing: the only |z| > 2
  among 40 files' half splits, spread over all five blocks, concentrated at
  the boss; no engine swap in the window, a mid-run script change would have
  crashed the job, search is deterministic. Reads as a chance property of
  that sequence set under this deterministic player. "Both unpinned" alone
  does not establish it.
- Skeptic 2: **overstated** on one word. Numbers reproduce; the SPRT mostly
  ends open at the 500 cap (48% for a true +1.0 HP on the level pair, 85%
  with diverging decks). Pairing "weakened" (~1.2x left between nets, ~2x for
  same-net flag variants), not broke. The half swing has no code channel but
  at z 2.7 with deterministic search it is an unexplained, reproducible
  weakness of the plain player on 250-499, not established chance.

**Claim 5.** Goal 1's generalisation lives in the simulator plus depth; the
encoding helps only zero-shot; every goal-1 bench was read against a
reference blind to the content.
- Skeptic 1: **overstated (refuted).** Two-turn shrinks the effects edge on
  unseen cards from +0.059 to +0.017 and heuristic, ids and effects all
  converge at 0.39-0.41; consistent with depth generalising but
  indistinguishable from "the generated cards are weak and nobody
  generalises" (depth helps the heuristic only +0.02, so it repairs the nets'
  leaves). The encoding helps zero-shot and at low data (5k games), fading
  at 30k. Check 9 and the oracle arm used content-aware references; the real
  weakness is that the cells and the generator's pricing come from a
  heuristic blind on 37 of 43 test powers.
- Skeptic 2: **overstated.** Same; adds that the two-turn effects-vs-ids level
  is one seed pair (noise ~0.02), that the bench's "original" cells hold
  check-9 held-out cards (Demon Form, Metallicize at 3 copies) the net never
  trained on, so "the heuristic beats the net on known content" is not shown;
  depth's gain is not content-specific overall (+0.109 generated vs +0.104
  original) and is larger for the ids net; content-specific only for powers
  that pay after the leaf (turn-start minus card-played +0.274, replicated).
  Generated content so far: 128 power cards, 170/179 hooks "Always".

**Claim 6.** The run layer is the largest lever on record and the headline
omits the decisions where it lives, so goal 2's headroom and the
outside-comparable arena are the same build.
- Skeptic 1: **overstated.** Run layer and search are levers of the same
  size (sim vs random +0.184, boss horizon +0.13-0.16; two-turn +0.154, HP
  bonus +0.168 on cells); the repo ranks them both ways. Card rewards are
  inside the 0.834 headline; the omitted decisions have no measured lever
  yet beyond removal +0.038 at 1.9 se and an elite-skip upper bound. 62 of
  83 deaths are at the boss and move with both depth and deck. Level 1
  overlaps the run-layer build but is mostly combat-engine content (relics,
  potions, Ascension, ~40 cards); the field's unit (A20 Heart, four acts) is
  not the gauntlet's.
- Skeptic 2: **overstated (refuted)** in the same way; against a fixed chooser
  the net chooser is worth 0.09-0.12 at one turn; with the product player
  the fighter's measured share exceeds the chooser's; no current number is
  comparable with the field's 50.1%.

## Stop doing (synthesis, as corrected)

- Training arms with a teacher no stronger than the student; the two-turn
  round was the exception and its arms fail (read pending).
- Reading tight2 or the ladder as a success signal; playing tight2 inside
  every training round.
- Unpaired or cross-book reads (0-499 vs 500-999 differ by 0.036 for the
  heuristic); two-turn headline SPRTs for effects under 1.5 HP; extending an
  open read past 500 hoping for a verdict.
- Replaying the plain control's second half.
- Engine fidelity stages that measure nothing for random content until a
  measured novelty cost names the missing atom (mutated monsters stage B is
  the trigger for stage 3).
- Flat constant hand prices on future-turn effects; per-mechanic rate
  columns; Hexaghost-specific play fixes.
- Letting 0075 test-full run (pinned pre-fix, sure to fail): cancel refused
  for the lane worker and the navigator by the permission classifier; the
  steward or the owner.
- Calling any number "dominant" or writing it in the field's unit before
  level 1 exists.

## Directions (synthesis rank, navigator's disposition)

1. Driver and runner fixes (zero CPU): skeptics reduce this to the thread
   sizing policy (decided: 4-6 threads per lane job) plus small untested
   items (gauntlet 8-thread check 0.5 thread-h, test-full per file,
   pre-chaining). Backlog `throughput-fixes`, merged with
   `test-size-profile`.
2. Deck-matched paired reads, end-HP as the decision unit: backlog
   `deck-matched-reads`, first candidate for the next open lane (code 1-2 h,
   first check 0.5 thread-h: paired end-HP sd must fall from ~23 toward 12).
3. Two-turn round read through the bias audit: the arms failed the protocol;
   the lane reads why; the bias audit matters only on a pass. No action.
4. Horizon-complete leaf (heuristic blend or row-computed bonus at the
   one-turn leaf, screened on 448 puzzles and 300 audit states for
   CPU-minutes): backlog `horizon-leaf-screen`, screen only; the skeptics'
   verdict on claim 2 lowers its p from ~0.35 to ~0.2.
5. Depth-headroom re-aimed at HP leaked in won elites: the lane already
   runs elites first with paired HP saved; stands as chartered.
6. Run layer: elite payoff and a path choice in the gauntlet, margin rule
   for sim choosers: backlog `mini-run-headline` (design first, no CPU; a
   headline re-rank ~8 CPU-h later) and `chooser-margin-rule` (offline check
   on the removal file, then ~1-3 CPU-h) as run-decisions' follow-ups.
7. Boss replays as the sequence score: backlog `boss-replay-score`, first
   check 0.3 thread-h.
8. Goal 1 with the product as reference, masked atoms, generator breadth:
   the goal1-yardstick charter is amended (reference); masked-atom columns
   and generator breadth are the lane's spec questions.
9. Arena: decided (first defaults); the peek question is an exploration note.
10. Experiment ledger (effect, se, verdict per job): backlog
    `experiment-ledger`, code only.

## Next 48 hours

CPU: the queue is empty but for test-full (0076 running, 0075 doomed). The
lane worker is woken: two-turn-round reads 0069-0071 and files `done:`;
depth-headroom queues the elite probe (two-turn memory slot, 4-6 threads);
run-decisions queues the rest-site probe; goal1-yardstick specs under the
amended charter. Light slots: the gauntlet thread check and the boss-replay
variance check when a lane picks them up. CPU-light alongside: the
deck-matched read code, the mini-run headline design, the generator breadth
spec.

## Open questions

- Why does fine-tuning on stepped two-turn product games (and on one-turn
  games of the same specs) make the 10-29 net worse at run level, when the
  games come from a stronger player? Label scale, 1500 games per group, or
  the recipe's lost solve step: the lane's read.
- Is there combat headroom at matched state against a player stronger than
  the product on the won elite fights that leak 20+ HP (depth-headroom)?
- How much of the headline's deck divergence is in the picks (deck matching
  fixes it) versus in the fights (a counter-based RNG would)?
- The sim chooser prices options with the one-turn player while the product
  fights two turns deep; does pricing with the product's leaf change picks?
- Why did a 10-minute burst on 8 generated power cards improve play on
  official content (+0.037 on originals) when nothing else did?
- Does one-turn screening predict the two-turn product's ranking (Spearman
  over the ~8 nets with both, ~0.3 thread-h)?
- Is the -0.06 two-turn loss on fights over 10 turns noise, node cuts or
  compounding leaf error (~290 paired fights on disk in results/depth)?
