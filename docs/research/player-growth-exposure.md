# Player growth exposure (lane player-growth-exposure)

Lane charter: `lane/player-growth-exposure`. Question: does forcing a growth
power into burst games (player Ritual 0-2 at fight start) teach the value net
the later ticks that games where the player chose the power did not
(`measurement/demon-form-games@tsl1`)?

## Step 1: how often the step-2 Demon Form bursts held Demon Form (read 10:30 2026-11-10, lanes 6c4e3f06)

Method: `scripts/analysis/power_exposure.py --power DemonForm --card "Demon Form"`
over each arm's new-games dataset (`runs/2026-11-07-ycards-<arm>-s*/run.json`,
first dataset; the three seeds of an arm share it), sampling states exactly as
`finetune.encoded` does (same rng seed, chunks and `selfplay.sample_states`),
so the counts are the rows the bursts trained on. A state "holds" Demon Form
when the player's powers list it. Output:
`results/power_exposure/ycards-step2-demonform.json` (MAIN).

| arm (dataset) | DF decks: states | held, all | held, elites | held, bosses | DF games where it was played |
|---|---|---|---|---|---|
| net-g1600 (aa2d9e40ac32) | 9,641 | **8.2%** | 5.6% | 11.0% | 11.3% |
| two-g400 (48a0cf093824) | 2,369 | **32.5%** | 16.3% | 48.2% | 39.7% |
| heur-g400 (b21ca4b6b20d) | 2,349 | **51.9%** | 40.4% | 63.3% | 66.4% |

No other deck ever holds it (0 of 13,172 / 3,309 / 3,327 states). These shares
are of the bursts' own rows; training mixes them half and half with the replay
pool (`share` 0.5), where Demon Form is rare, so the share of all rows is about
half of these.

What it says:
- **The gate was real for the net's own games.** The 10-29 net played Demon
  Form in 11% of the fights whose deck held it (16% of bosses), so 92% of
  net-g1600's Demon Form-deck rows never saw the power active. Its +1.19 (0.75)
  HP @tsl1 is the arm that most fits the owner's mechanism.
- **The two-turn product's games sit at the charter's bar.** 32.5% against a
  third: the stop rule's literal reading is "just under" and the difference is
  under one binomial se (about 1 point, more with clustering by game). On
  bosses, where growth pays most, it held Demon Form in 48% of rows, and that
  arm learned exactly the first tick and nothing after it (-0.42 (0.94) HP on
  Demon Form decks @tsl1, se over nets 0.07). This already leans to "exposure
  alone does not teach later ticks", but it sits at the bar.
- **The heuristic's games had the gate wide open** (52%, 63% on bosses), but
  its nets were read on the plain leaf only (+4.98 (0.67) on Demon Form decks;
  it failed the family rule on train HP, -1.39), never @tsl1. It is the arm
  that tests the mechanism directly: if 52% exposure taught more than the
  first tick, its nets beat the 10-29 net @tsl1 on Demon Form decks.

Decision (docs/decisions.md, "player-growth-exposure step 1: the heuristic arm
read @tsl1 decides"): read heur-g400's three nets @hpb0.01@tsl1 on both cell
books (jobs below), paired against `results/gauntlet/net1029-hpb0.01-tsl1.json`
and `-tsl1-b500.json`, with `cards_by_half.complete_nets` and `strata_row`,
three nets pooled. Rule, set before the read: Demon Form decks' HP at least
+2 se (the larger of se over sequences and over nets) above zero passes step 1
(exposure teaches more than the first tick; the step-2 arms were gated: go to
step 2, the start-power patch); anything less fails it (the gate was open in
half the rows and two-g400's at a third, and the bursts learned the first tick
only: `done: fail`, exposure alone does not teach later ticks). About 0.5
cpu-h.

## Step 1 read: heur-g400 @tsl1 fails (jobs 0784-0789, read 2026-11-10 14:00, lanes 74df2700)

heur-g400's three nets @hpb0.01@tsl1 on both cell books
(`results/gauntlet/rerank-2026-11-07-ycards-heur-g400-s*-hpb0.01-tsl1*.json`),
`cards_by_half.complete_nets` + `strata_row`, paired by sequence, three nets
pooled. HP (se over sequences / over nets), clears:

| stratum | n | vs 10-29 net @tsl1 | vs heuristic |
|---|---|---|---|
| train | 500 | -1.12 (0.42 / 0.75), -0.047 | +2.55 (0.55 / 0.75) |
| other held-out | 326 | -1.53 (0.49 / 0.98), -0.040 | +3.91 (0.70 / 0.98) |
| held-out Demon Form decks | 174 | **-0.73 (0.87 / 1.06)**, -0.027 | +2.69 (1.04 / 1.06) |

Per net, Demon Form decks against the 10-29 net: s1 -2.86, s2 +0.46, s3
+0.20. s1 is worse everywhere (train -2.62, held-out -3.40), a weak seed
rather than a Demon Form effect; without it the other two sit at +0.3, still
nowhere near the bar.

**Checkpoint step1-exposure: failed** (the rule set before the read needed
+2 se above zero, about +2.1). What it says:
- On the plain leaf these nets gained +4.98 on Demon Form decks; the
  turn-start leaf, which prices the first tick with no games, takes all of
  it. So in games where the player held Demon Form in 52% of rows (63% on
  bosses), the burst still learned the first tick only, as two-g400 did at
  32.5%. Exposure was not the missing piece: removing the gate (step 2's
  start-power patch) would not teach later ticks, so step 2 and step 3 are
  not built.
- The guard is also red: train decks -1.12 HP, past the charter's -0.9.
- What did teach later ticks is a from-scratch learn at 40k games
  (backlog 49's probe twin-tsl1, +3.30 (0.95) HP @tsl1): the count or the
  start of training, not exposure inside a burst. That is 49's question.

Lane closed: `done: fail`, exposure alone does not teach later ticks.
