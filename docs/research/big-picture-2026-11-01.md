# Big-picture review, 2026-11-01 (04:20)

Run by manager run 68e81bce after two major results: depth's novelty check
on fresh held-out bosses (+0.096, se 0.039, passes) and data scaling
flattening at 80k (+0.004 / +0.003 over 40k). Workflow
`big-picture-review`: six analysts, a synthesis, two skeptics on each of
the six key claims. Read-only. The newest review outranks the queue's
order. (Scratchpad scripts the analysts mention won't exist later.)

## Manager's reading (what changes)

- **Skeptics:** all six key claims came back "overstated", and one verdict
  on the strength-loss claim says "wrong". In every case the numbers
  reproduce from the files; the conclusions drawn from them go too far.
  What survives, claim by claim:
  - **"Imitation ceiling" (the one-turn net can't beat the policy that made
    its data).** The plateau is real for the label-side family: label,
    loss and curriculum variants of the lean loop all land within about
    ±0.01 held-out, none passes the ladder, and data gains flatten between
    40k and 80k. The *cause* is not shown. Distillation trained on a
    stronger policy (two-turn search) and was still null or negative, and
    a net trained on heuristic games beats the heuristic (+0.037, ladder
    0001), so "labels from the imitated policy" is not what holds play
    flat. Training changes do move play on slices (rates on Demon Form
    fights, effects vs ids on held-out elites, coverage 4 to 10 kinds,
    data 5k to 40k). The MSE floor is unverified: data80k s1's val MSE
    (0.1317) is already below the "floor" (0.133, measured on another
    player's positions).
  - **"Search is the only lever, and it pays most on unseen content."**
    Holds as "depth is the only recent lever that cleared noise several
    times" (clustered se are ~10% bigger than the depth doc's, no effect
    drops under 3 se). "Pays most on unseen content" is **not shown**: on
    the same tight_bosses bench, six lean r2 nets gain as much from depth
    on train as on held-out (+0.133 vs +0.129 pooled); with heuristic
    leaves the novelty split reverses (+0.050 with an unseen power vs
    +0.083 without); the check passes only through Hexaghost. The better
    reading: depth repairs short-horizon mis-pricing wherever one-turn play
    is weak (bosses, Lagavulin, the rates nets' Guardian hesitation),
    which includes but isn't specific to new content. This qualifies
    decisions "Depth repairs unseen powers: the check holds": the rule
    passed, the mechanism is not novelty as such. Depth has never been run
    on the generated-power benches, goal 1's real target.
  - **"Strength is lost valuing end-of-turn states, not in tactics or the
    endgame; exact-label work has a ~1% ceiling."** The scaling is wrong:
    the exact puzzles are one late decision per game, so 0.007 per game is
    a lower bound on endgame error, not a ceiling; contested mid-fight
    decisions show regret 0.037-0.094 each. Horizon-0 100% holds by
    construction and says nothing about mid-fight tactics. "Elites carry
    85-95% of the regret" has no source in the repo. What survives:
    exact-label work is still not worth more CPU, but because label work
    lowered MSE several times and never moved play, not because of this
    arithmetic.
  - **"The yardstick is mis-specified for goal 2."** Facts hold: 73% of
    ladder pairs are hallways (median calibrated start HP 5 / 3; over all
    cells 6 / 5), win-only, ~8.5% of pairs discordant. Two inferences
    fail. The shared champion draw is deliberate (common random numbers,
    champion-ladder spec) and shows no bias: the champion's block-0
    excess is ~1 se, no winner's curse. The Spearman -0.20 between tight
    win and HP lost is weak (p ~0.33, two duplicate files); the real
    evidence is a few nets that lose 30-40 HP per fight while tying on
    tight win. What survives: the ladder has no HP and no run-level
    signal. That is a real gap for goal 2 (it was Next F already).
  - **"Half the CPU bought reads that couldn't succeed."** Totals are
    right (~362 reserved thread-h), but most nulls were decisive reads
    (distillation, guard, ensemble, top-k, data80k, the lean recipe that
    every experiment now uses). Reads that truly couldn't succeed:
    threshold rows and the gen arms on the blind bench, ~30 thread-h
    (8%; 15% with data80k). Failed or hung jobs are a separate ~10%, and
    were double-counted. The seed arithmetic was quoted for 0.005
    effects; at 0.01, paired arms (corr ~0.9) need only 2-3 seeds.
  - **"Goal 1 is measured only on known-atom powers; the net can't learn
    what powers are worth."** Pack facts hold: 128 generated powers, all
    of type Power, 170 of 179 hooks "Always", the test split shares every
    atom with train but GainEnergy. "Can't learn" is a hypothesis, not a
    finding: the oracle spread share 0.5 over 43 powers (~1% of games per
    power) and still gained +0.064 on generated bosses on every seed. The
    adaptation burst is exactly the test that separates "too little
    exposure" from "can't learn". Demon Form is a held-out card, and rate
    features are hand-coded per mechanic, so they don't show that
    "outcome-unit information" in general moves play.
- **What I take from it.** Depth is the one lever with large repeated
  effects, and it isn't the product yet: the ladder plays one-turn. The
  biggest missing piece for goal 2 is measurement (HP at run-level start
  HP, then an Act gauntlet), and for depth it is cost (~145x one-turn per
  decision). Goal 1's two open questions are cheap to test: does a
  concentrated burst teach a power (built, queued), and does depth help on
  generated powers (never run).
- **Actions this run:**
  - Parked `0061-score-r0` (it scores data-scaling nets; that line is
    closed). `0060-learn` (lean-look s201) was already running, so it
    finishes; read lean-look only on its pre-registered Lagavulin and Nob
    slices, no third seed unless both seeds clear the bar there.
  - The adaptation burst (synthesis rank 10) was already built
    (`docs/specs/adaptation-burst.md`) and its 3 fine-tunes are queued
    (0059b1-b3, ~1 h in all), so it runs first: it's cheap and it answers
    the skeptics' "unmeasured vs unlearnable" question.
  - Forks started on rank 1 + 2 (ladder fixes: cache the champion's
    results, fixed-n effect sizes, an informative fight book with a guard
    slice; and a run-HP mode) and on rank 3 (selective two-turn search in
    Rust). Given the skeptics, the per-test block offset is optional: no
    bias from the shared draw was shown.
  - Rank 8 (re-scope the rules-engine series) stays with the owner, as
    after the 10-31b review: it reverses the series' design rule.
  - The stop list is adopted (decisions "Review 2026-11-01: stop list
    adopted"), with two trims from the skeptics: exact-label work stops
    because of the label-null record, not the "1% ceiling"; and paired
    recipe arms at 0.01 stay allowed when the pairing is measured.

## Diagnosis (synthesis)

Where the project stands. On goal 2 the best player that exists is the
10-29 champion net with the two-turn fallback search: 0.591 on held-out
elite and boss tight fights, against 0.498 for the one-turn heuristic
(depth-pilot doc). That player isn't on the ladder, and it has never been
measured on HP efficiency, on an Act, or on a full run. Potions, relics and
everything outside combat are missing, so the distance to "Stockfish-level"
can't be stated today; the reason is missing measurement, not proven lack
of strength. On goal 1, what has been measured covers only power cards
composed from known hook atoms. Even an oracle net trained on the test
powers learns them only weakly (+0.013, se 0.009, 3-copy bench). The one
thing that repaired play on unseen content is lookahead (+0.096, se 0.039,
more on fights with an unseen power; see the skeptics above).

The synthesis's underlying pattern: since 10-25 the project treated the net
as the product and search as an add-on, and measured that product with a
number (one-turn tight2 held-out lead) that barely moves: every one-turn
net trained on 20k+ games sits within -0.010 to +0.013 of the heuristic on
held-out cards across 11 arms. The one lever with z >= 4, repeated, is
search, and it does three jobs at once: goal-2 strength, goal-1 repair of
mis-priced mechanics, and the only available way to make training data
better than the net. All three run through one constraint: two-turn search
costs ~50x one-turn per fight and ~145x per decision. Cheap, selective,
deeper search is the central engineering problem.

The second structural problem is the yardstick: tight2 is 73% hallway
fights at near-death HP, scored win/loss, relative to one champion; the
training label also prices HP as almost free (score = 2 - HP lost / 100).
The project has optimised near-death survival, while runs are decided by HP
efficiency and by choices outside combat.

What held it back (synthesis): the product test is one-turn while the gain
comes from depth; positive label results weren't replicated before work was
built on them, and negative search results weren't audited (the 10-24
teacher sizing and the 50k node cap cost about five days); the process
scaled experiments rather than insight.

Points no single lens saw (synthesis): search is the improvement operator
for training as well as the play lever, so product, generalisation and
better data are one investment; leaf scoring already runs in Rust
(`py/src/net.rs`), so speed must come from a smaller tree, not inference;
the champion's lead over its own recipe siblings is tiny (ladder 0003:
-0.0002 over 4,090 pairs), so "night recipe ~0.01 better than lean" rests
on early-stopped tests; tight cells are calibrated to the heuristic, so
they lose resolution as the product gets stronger.

## Directions, ranked (synthesis)

1. **Fix the ladder instrument.** Cache the champion's outcome vector (it
   is identical in every test), report effect sizes at a fixed n rather
   than where the SPRT stopped, and add an informative fight book (fights
   ever discordant in tests 0004-0011: 23% of fights, 87% of discordant
   pairs out of sample) plus a 10-20% random guard slice reported
   separately. Halves ladder CPU and cuts SPRT length to ~0.38x. First
   check: replay test 0004 to 6,000 pairs; if its lead shrinks toward
   -0.01, stopping-point sizes were inflated. ~0.3 thread-h. Both goals.
2. **Run-HP paired pool.** A ladder mode that starts fights at 40-100% of
   max HP and scores HP lost (death = start HP + 30). Play heuristic,
   champion, a data40k net and a lean-thr net at one turn, ~2,000 pairs
   each, paired against the heuristic. First check: does the champion lose
   more HP than the heuristic at run HP? ~0.5 thread-h. Goal 2.
3. **Selective two-turn search in Rust.** Expand the second turn only under
   one-turn's top-k (~3) root options; later spend the saving on a third
   turn for the top 1-2. Top-3 lost no strength (+0.005, se 0.009) and
   two-turn's best fell outside one-turn's top 3 on only 3.4% of
   decisions. First check on 200 stored elite/boss decisions: under 2x
   speedup, or picks differing on more than 5%, keeps the full fallback
   player for bosses only. Both goals.
4. **Depth on the generated-power bench.** Champion one-turn vs two-turn
   fallback on `gen_powers12c3`, generated and original sets, elites and
   bosses, paired by cell, heuristic two-turn as a no-net control; read
   (two - one) on generated minus (two - one) on original, per trigger
   family; pre-register +0.03. First check ~30 min on 4 threads on the
   worst trigger families. Goal 1.
5. **Make champion + two-turn the product and ladder it.** A two-turn
   ladder mode; judge product candidates under two-turn play with the book
   and cached champion results. First check is CPU-free: the expected lead
   and SPRT length from the existing paired files reweighted by the
   ladder's fight mix (predicted ~+0.03). Both goals.
6. **Three-turn probe.** On 50, then 300, held-out elite/boss decisions
   (`sample_agree.py` harness), three-turn picks (selective, cap 1-2M) vs
   two-turn. Under 4% overrides at 50: stop deepening, spend search effort
   on speed and leaves. ~2-5 thread-h. Both goals.
7. **Act-1 gauntlet with HP carried over** (goal 2's headline): 500-1,000
   seeded Act-1-like sequences (~10 hallways, 2-3 elites, a boss, heal at
   the end of combat), paired by seed; report Act-clear rate, HP at the
   boss, where agents die. First check: 200 sequences for heuristic and
   champion at one turn; retune if the clear rate is near 0% or 100%.
8. **Re-scope the rules-engine series toward content as data** (generated
   attack and skill cards plus a character as data; monster patterns as
   data; mechanic specs on demand; relax bit-identity of old nets to "old
   nets load"). Owner's decision (see "Manager's reading"). Goal 1.
9. **Expert iteration:** fine-tune the champion (warm start) on a few
   thousand elite/boss games *played by* champion + two-turn search,
   labelled with real outcomes; judge under two-turn play; pre-register
   +0.02 on held-out elites and bosses. ~10-30 thread-h at today's speed,
   so after rank 3. CPU-free first check: how often two-turn and one-turn
   outcomes differ on the same specs in 0044b. Both goals.
10. **Adaptation burst** (spec confirmed and built): run it with its
    pre-registered rule, and read it under two-turn play too. Goal 1.

## Stop doing (synthesis, as adopted)

- Training-side arms (labels, losses, curriculum, content share, hand
  features, data volume) judged on one-turn tight2 held-out lead or the
  Amendment 5 gate. Keep the gate only as a sanity floor.
- Data scaling past 40k games (data80k s201 stays parked).
- Exact-solver, endgame-puzzle and exact-label work; keep
  `data/bench/puzzles.json` as a regression check.
- Generated-content training arms and new hook-row columns as goal-1
  levers, until depth on generated content is read and a bench exists
  where the content decides the fight.
- Tuning the two-turn player's policy knobs (top-k pick rule, guard
  margin, sample_k, ensembles): all flat.
- Reading effect sizes where a ladder test's SPRT stopped; quoting "lean
  is ~0.01 weaker than the night recipe" as measured.
- Treating val MSE, regret or err² improvements as evidence for a
  training change.
- From-scratch 3-seed batches for questions whose expected effect is under
  twice the MDE, unless the arms are paired with a measured pairing
  correlation of 0.9 or more.
- `test_sweep` in the default test set (the job queue replaced sweep.py).
- (Not adopted, owner's call) building rules-engine specs 2-8 in order as
  a prerequisite.

## Next 48 hours (synthesis's plan; the manager's order is in docs/manager.md)

Hour 0: park 0060 and 0061 (0060 had already started, so only 0061 was
parked); record the stop list; correct manager.md's "Machine time" note (in
the lean recipe the solver costs 0% of a run and the tight fights ~34%).
Hours 0-2: forks build the ladder fixes and run-HP mode, and selective
two-turn search; read 0058 / 0059 only on Lagavulin and Nob. Hours 2-4:
run-HP first check (slot A), depth on the worst generated trigger families
(slot B), replay ladder 0004 to 6,000 pairs. Hours 4-14: selective search
speed and agreement check, then re-confirm on held-out elites and bosses
against 0044b; the full generated-depth read if its first check reached
+0.03, else champion one-turn vs two-turn at full HP scored by HP lost.
Hours 14-24: the two-turn product ladder test; the three-turn probe. Day 2:
build the Act-1 gauntlet; the rules-engine re-scope decision; the
adaptation burst; draft the expert-iteration spec. Throughout: no new
one-turn recipe arms, at most two heavy jobs.

## Open questions

- Does the 10-29 champion lose more HP than the heuristic at run-realistic
  HP, as older score-labelled nets did (5-18 more HP per fight)?
- Does depth save HP at full start HP, or mainly rescue near-death races?
  (In tight fights both players win, two-turn saves ~0 HP except on
  bosses, +1.5 HP.)
- Does depth's extra gain on unseen content hold on generated powers and
  on the Guardian, or is it mostly Demon Form on Hexaghost? (Skeptics: on
  the same bosses, train gains as much as held-out.)
- Does a third turn override two-turn on 10% or more of elite and boss
  decisions?
- Why did distilling two-turn values fail (elites -0.03) while two-turn
  play gains +0.055?
- Is the night recipe really better than lean, or is the gap a
  stopping-point artifact? A fixed-n replay settles it.
- What is goal 1's metric? Proposal: the share of the train-content lead
  that net + search keeps at each novelty distance, plus the CPU minutes
  of adaptation burst needed to recover it.
- How much of a run's outcome is combat strength rather than deckbuilding
  and pathing? If deckbuilding dominates, the gauntlet needs card-reward
  and rest-site choices soon.

## Analysts in one paragraph each

- **Results archaeology** (~35 experiments since 10-24): search changes
  gave the large effects (+0.055 to +0.118, z 4-6) once its artifacts
  were fixed; data was the steady training-side lever (~+0.01 per
  doubling to 40k, coverage 4 to 10 kinds +0.035, round 1 +0.017), then
  flat; representation helped narrowly (effects vs ids +0.075 on held-out
  elites, rates +0.12 to +0.17 on Demon Form fights); 12+ label, loss and
  curriculum variants gave nothing on play.
- **Where strength is lost:** not inside a turn (one-turn search tries
  every order and target) nor on the last turn (exact everywhere), but in
  choosing between end-of-turn states whose payoff comes later: block vs
  attack in a race, setup, focus fire; most in elites, bosses and unseen
  content. Two-turn search is positive in every slice measured. Third
  turn, potions, relics and run-level HP are unmeasured.
- **Goal 1:** the simulator (afterstates, lookahead) is content-agnostic
  and is what has repaired unseen content; the learned evaluator reading
  syntax delivered little past zero-shot MSE. The generated content
  covers a narrow corner (power cards only, conditions almost always
  "Always", no held-out atom bar GainEnergy). Shortest path to new content
  by data: cards of every type plus the character as data, and monster
  patterns as data.
- **Prior art and the Stockfish analogy:** Stockfish won through a
  throughput loop: many cheap candidates, each SPRT-tested against master
  on a book chosen to avoid draws. The ladder is already that SPRT (91% of
  pairs agree, like chess's draw rate); what's missing is cheap
  candidates. Selective deep search came first in Stockfish; NNUE came
  late, trained on search-labelled positions. Outside full-run numbers:
  humans ~85% at A20 Heart, LLM agents ~20%, bottled_ai Ironclad ~20%.
- **Throughput:** the queue keeps the CPU busy (some job 92% of the time,
  two or more 75%). A lean learn run spends ~41% in torch training, ~34%
  replaying tight2, ~5% building features, ~2% self-play, 0% in the
  solver. Two torch trainings side by side slow each other ~1.9x.
  Evaluation noise is a small share of total noise, so thinning tight2 to
  every 4th seed adds only ~4-5% to the MDE.
- **Measurement:** the tight win rate measures near-death hallway
  survival, two nets disagree on only ~8% of fights, and HP lost at real
  start HP ranks some nets differently. First metric to add: paired HP
  lost at run-realistic start HP on the ladder's cells; then chained Act-1
  gauntlets; then a Bradley-Terry ladder over fixed anchors for an
  absolute scale.

## Skeptics' verdicts (detail)

Full text in the workflow output; the points that change the reading are
in "Manager's reading" above. Extra details worth keeping:

- Ladder count: tests 0004-0020 are 17 tests (16 newer nets plus 0018, an
  ensemble that includes the champion). The SPRT tests lead 0 vs +0.01, so
  "fail" means "not shown 0.01 better", not "worse". The champion's own
  same-recipe siblings also fail (0002 -0.013, 0003 -0.0002), so the
  champion may be a lucky seed.
- Train-minus-held-out gap per arm ranges 0.008 (lean-rates r2) to
  0.024-0.027 (data40k, data80k, ids5k), not "0.015-0.020 in every arm".
- rates minus thr paired per seed at r1: +0.008 (se ~0.002), all 5 seeds
  positive; at r2 +0.005 (se ~0.006).
- `engine/src/search.rs` is exhaustive only within budgets: random events
  with more than 16 outcomes and states past the node cap become
  evaluator-scored leaves.
- Ladder thread-h is 2.15, not 1.6. 0052a finished round 2 (it was not a
  failed job).
- The 10-24 teacher-sizing "negative" was never rerun with common random
  numbers and the fallback player, so calling it an artifact is inferred.
  The guard's -0.025 was measured with heuristic leaves.
