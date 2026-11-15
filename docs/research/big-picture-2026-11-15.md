# Big-picture review, 2026-11-15

The saved `big-picture-review` workflow (run `wf_52de7421-501`, 19 agents:
six lenses, one synthesis, two skeptics per key claim), run by the
navigator on the 3-day cadence (`owner/reviews`). Raw output: the run's
journal under the session's `subagents/workflows/` folder (not in the repo).
This file keeps the synthesis as the skeptics left it; where a skeptic
corrected a claim, the corrected form is the one stated.

## Diagnosis

Goal 2 rose fast and then flattened. From 10-29 to 11-03 headline clears
went from 0.534 (one-turn heuristic) to 0.834 on sequences 0-499 (0.780 on
500-999). The rise came from changes to what the search and the chooser
count or how far they look: the HP price at the leaf (+0.168 clears), the
sim chooser (+0.184), the chooser's boss horizon (+0.155), the second search
turn (+0.120) (`measurement/search-time-gains`). Smaller pricing flags
followed on 11-13 (`@tsl1`, `@lcb1`, product read 0986). Before that
window the trained net itself was the largest single gain (+0.146 clears
over the heuristic one turn deep). Retraining on the same content has added
nothing at run level since; training on new content has (the pack nets
+4.57 (1.19) HP, +0.097 (0.030) clears two turns deep on the 31-card pack,
`decision/no-goal2-training-arms`, decisions "pns-two-turn-seeds read").

The pattern underneath: the project is limited by what it counts. Every
adopted gain fixed a miscount, and the largest open errors are still
miscounts, in two places.

- **In the ruler (claim held).** The gate statistic, paired end HP
  (`scripts/analysis/gauntlet_protocol.py` `end_hp`: the boss floor's
  `hp_end` on a clear, else 0), pays 1:1 for HP left after the Act 1 boss.
  The game heals to full at A0 and heals 75% of the missing HP at A5 and
  above (`docs/research/ascension-act1-2026-11-14.md`,
  `dungeonTransitionSetup`), so a point of HP left is worth 0 at A0 and
  about 0.25 at A20. Recent leads were mostly that currency: the
  all-content twin's +1.41 (0.45) HP is +0.09 from clear flips and +1.32
  from the 393 sequences both players clear. Not every lead: the SharpHide
  net one turn deep (+2.47) had 44% from flips and +0.040 clears. HP left
  on shared clears still signals fight skill; it is the 1:1 price that is
  wrong.
- **In the run layer (claim overstated).** 59 of the product's 84 deaths
  on the headline are at the boss, 49 of them arriving under 60 HP; elites
  cost 30.5 HP per run against 7.9 for the hallways. The chooser's trial
  fights are short (8 per part, one turn deep, a random boss). But the
  research record puts arrival HP's causal share at 0.87, and two
  boss-aware choosers read level, so "the chooser is the keystone" is a
  hypothesis; its noise was never measured (backlog 55). The real game
  differs: 7 of 10 A20 boss losses entered at 66-77 HP (Hexaghost damage
  races), so the gauntlet's low-HP story does not carry over.

## Key claims and what the skeptics left

1. *Adopted goal-2 gains came from what search and chooser count* (overstated):
   direction holds; "every" and "all by 11-03" do not (11-13 flags; the
   net itself before 10-29); "nothing since" holds only for the same
   content.
2. *End HP counts HP the game gives back* (holds, both skeptics): worth 0
   at A0, about 0.25 per point at A20; the A20 mix of flips and shared HP
   is not measured yet.
3. *The ruler can't see what remains between nets* (overstated): at A0
   between nets the paired sd is 20.6-23.9 HP (175 pairs), and a true
   +1.5 HP passes the SPRT capped at 500 about 0.22 of the time. But
   content-trained nets read +2.7 to +4.7 HP on the pack headline and four
   passed; at a true +2.5 HP the pass rate is 0.38-0.66. A one-seed
   headline se is about 1.2x the printed one, not 2x (the 2x is for
   cells). The final round is a content-and-setting change, the kind the
   ruler has detected; its A20 power waits for 1017-1019.
4. *Runs are lost on decks the chooser built* (overstated): numbers hold,
   the mechanism and "every widening paid" do not (see above).
5. *The machine is 75% idle; slots bind* (overstated): booked threads are
   28% of the machine's threads over 24 h, but the runner's own idle readings
   show the CPU near saturated by work outside the queue. The scarce pieces
   are memory, ready work and policy holds; more heavy slots
   would gain little. Prior record agrees (`queue-throughput`: backfill
   recovers 0.0-1.1 of 19.8 idle-pending hours).
6. *Goal 1's blind case was never measured* (overstated): RoundEnd's cost
   was measured zero-shot (+2.48 (0.18) HP) and after training (+2.26,
   +2.30): a blind element whose value outlasts the leaf costs about 2.5
   HP and training doesn't repair it; a shared unknown trigger slot is
   bought back by a burst; a fresh row kind taught Hexaghost nothing in
   1600 games. What is unmeasured is a burst that widens the vocabulary to
   a column no net trained (backlog 73) and the audit of which elements
   are blind (72).

## Stop doing (as the review left it)

- Treating HP left after the boss as full-price currency in gate reads.
  At A20 a run's value at Act 2 entry is about clear x (0.75 x max HP +
  0.25 x HP left); report HP left as a descriptive column.
- Queueing goal-2 reads whose predicted effect is below what the read can
  detect at its sequence and seed count.
- Hand-priced leaf forecasts (strength from hits, projected growth, debuff
  durations, counterfactual prices): 0 for 9. Change a leaf only to fix a
  provable miscount (as `@wc1` does).
- More depth, hands or rollouts on official elites for goal 2.
- More seeds and grid variants inside the single-hook generator grammar
  after wide-recipe-confirm's seeds-go (the yardstick there is down to
  about 1 HP).
- Filing throughput fixes in reviews without building them.
- Several rules-version moves a day (four on 11-14): batch fidelity fixes
  so controls are re-recorded once.

## Directions, ranked by the synthesis, with the navigator's reading

1. **Re-register the final round's gate before step 7** (0 CPU for the
   rule): report the A20 Act-2-entry value V beside end HP; size step 7
   for power. Navigator: the owner's level rule (`docs/direction.md`,
   end HP and clears) stays; V is reported on every A20 read, and step 7's
   size is decided from the A20 sd when 1017/1018 land (backlog 90).
2. **Throughput fixes**: CACHE_CAP 10 -> 30 GB, sparse or in-RAM cache
   (66(a)), control-pick reuse in `--against` reads (exact where the run
   state is identical). Navigator: skeptic 5 cuts the slot part; 66's
   memory items and pick reuse stand, waiting for a second slot; 89
   (gated chains) is the cheaper first step under one lane.
3. **Blind-element audit, then column zeroing** (goal 1, minutes of code,
   about 2 thread-h): backlog 72 and the probe sheet's column-zeroing.
   Navigator: the audit joins final-round as optional step 4(c), code
   only; turning more row kinds on stays out of the round (an untested
   input in the one pre-registered run) and becomes the goal-1 base
   candidate after it.
4. **Shared-seed, long-fight chooser** (goal 2): needs the owner to lift
   the Avoid item for run-level decisions; its first check, the
   chooser-noise count (backlog 55, about 0.3 thread-h), is a ruler fix
   and needs no lift.
5. **Calibrate the simulator against the real game** (0 CPU): when 1019
   and 1020 land, compare clears, boss wins per arrival and boss-entry HP
   per boss with the real-game A20 records (0.545 Act 1, median boss
   entry 59.5 HP). The navigator does this read (wakes on 1019 and 1020).
6. **Fresh-atom experiment with the row kinds on** (goal 1, about 20
   thread-h): backlog 73, after the audit.
7. **Distance axis on goal 1**: the random-world k=8 re-read with the wide
   net (1-2 thread-h), multi-hook powers (68), Silent zero-shot re-read.
8. **Boss-only deeper search and potion pricing at the boss**: depth was
   closed on elites only; potions are under the Avoid item.

## For the owner (the review's recommendations that only the owner can make)

- Whether the Avoid item for run-level decision work (card picks, potion
  holding) lifts now that most Act 1 content loads.
- Whether adoption reads run at product depth: the review measured a
  two-turn headline sequence at about 4x a one-turn one (the one-turn rule
  assumed far more), and one-turn gains reach the product at 0.2-0.46x.
- Whether a fixed-seed real-game A20 ladder gets machine time.

## Open questions the review left

- The A20 paired sd, same net and between nets (1017-1019 decide it).
- Whether a learn with the static, countdown and replacement row kinds on
  fits in the dev machine's memory.
- Whether the pack nets' +0.097 clears on real content come from card
  valuation inside the chooser's trial fights more than from fight play.
