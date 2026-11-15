# Approach review 2026-11-02

Asked for by the owner on 2026-11-02 ("review the current state from a high
level, dissect each approach and say how likely it is to work, suggest 2-3
approaches likely to succeed, exercise abstract thinking"). Written by a
fresh session the owner started in the engine-next worktree (not the
session that built the series) from the output of a one-off workflow: nine analysts
(one per approach), eighteen skeptics (two per analysis), nine calibrators
who settled each verdict, three abstraction passes (mechanistic, strategic,
contrarian), six proposers of new approaches, a merger, three judges per
candidate approach, a synthesis, two skeptics on each of its key claims and
a completeness critic. 99 agents, all read-only, about 1,450 tool calls,
roughly 95 minutes. Every number below was re-derived from the primary
files by at least one skeptic; where a skeptic corrected the synthesis, the
corrected reading is what appears here. The raw output is not kept.

The snapshot is the repository at 10:30 on 2026-11-02 (main at 25291ac,
engine-next at d9327a2). Main moved at 12:13 (edb579f); the section "What
changed after the snapshot" lists what that changes.

Terms used throughout. The **gauntlet** is the 11-fight Act-1 chain with HP
carried over (scripts/gauntlet.py); **cell decks** are the pre-built decks
of the tight2 bench; the **headline setting** is the starter deck plus
simulated card rewards plus the boss-aware chooser (**sim-boss**); the
**protocol** is the sequential paired end-HP test with a clears guard
(scripts/analysis/gauntlet_protocol.py), and **--against** is its early
stop. The **leaf** is the state search scores, paused after End turn before
the next draw. **@hpb** and **@hpe** are the search-time HP prices (the
second also counts HP after the coming heal). **tight2** is the 1,226-cell
close-fight bench. The **10-29 net** (runs/2026-10-29-seed-check-r2-s1-1a789b2)
is the product's leaf. **Two-turn search** samples four next-turn hands.
**engine-next** is the rules-engine branch. The **heuristic** is the
hand-written evaluator. The **bias audit** compares a leaf's value change
against 32 play-outs when a monster's Strength or Poison is patched. A
**seed twin** is the same recipe trained with another seed. The **MDE** is
the smallest effect a read can detect.

## Where the project stands

Goal 2 (an Act-1 player that is dominant in its field) has a working
product and an internal number, and nothing yet that anyone outside the
project can read. The product is the 10-29 net under two-turn search with
@hpe0.01. On cell decks it clears 0.724 against the old champion's 0.672 on
fresh sequences 500-749 (+0.052, se 0.021; end-HP +3.01, z 4.1; results doc
"10-29 net two turns deep: confirmed"). Sequences 500-999 are an easier book
(the heuristic clears 0.632 there against 0.596 on 0-499), so only paired
differences inside one book compare. On the headline setting the one-turn
read is 0.680 over 500 sequences (results/gauntlet/net1029-hpb0.01-starter-simboss.json;
the 0.695 in manager.md was the early stop at n 200) against the
heuristic's 0.534. The run layer built in two days is the largest lever on
record: from the starter deck, skip 0.000, random rewards 0.364, simulated
rewards 0.548 (+0.184, se 0.027), the boss horizon 0.680 (+0.132, se 0.026
at 500). Removing a Strike after the first elite is worth +1.78 end-HP (se
0.83, z 2.2) and +0.038 clears at fixed 500; the simulated-removal chooser
loses that whole gain against the Strike rule (-1.41 HP, protocol fail at
n 222) because it removes an earned reward card in 24% of sequences. The
two-turn headline read (jobs 0059l7r3b39a/b, resized to 2 threads and 3 GB,
about 240 min each) is running; the survival-score arms (0059l8a/b) and
the goal-1 twin reads (b39aa, b39c1/c2) are queued behind it.

The record has one shape. Every measured gauntlet gain since 10-29 is a
change at search time or in the run layer: @hpb (+0.168 clears, 0.448 to
0.616, z 9), @hpe (+0.036 clears, +1.41 HP per hallway), two-turn search
(+0.060 clears on the tuning book, and +0.044 clears / +3.25 HP on fresh
sequences 500-749 when champion-hpe0.01-two-c.json is paired with
champion-hpb0.01-b500.json), simulated rewards (+0.184), the boss horizon
(+0.132), the Strike removal (+1.78 HP). The learned leaf is worth
something real at equal depth: +0.038 clears and +2.55 HP over the
heuristic one turn deep on 0-499, both seed twins agreeing (+0.024 and
+0.038 clears); +0.060 and +5.21 HP two turns deep on 0-249. That lead
widens to +0.146 clears and +6.7 HP on the headline setting, where each
player also picks its own cards by simulating fights with itself. But no
net trained after 10-29 has been shown to beat the 10-29 net at run level
(results doc "Re-rank of newer nets on the gauntlet": five lose or are
level; burst8 s1 is about +0.8 to +1.1 HP at one seed, an undecided read,
not a loss; most other recipes were never played on the gauntlet). The two
nets promoted on proxies read level or about 1 HP worse over seed twins,
and training took about 260 of the 575 thread-hours the job runner booked
since 10-30 (jobs/done, threads x (ended - started)). The champion's net
component ended where it started.

Goal 1 (play well on content the net never saw, custom content
first-class) has no standing number. The effects encoding beats a card-id
encoding by 0.075 on held-out elites on every seed and by +0.060 zero-shot
on Silent tier B (results/warm-start/curve.json), but an id net blind to
every Silent card still plays tier A near the heuristic, so the afterstate
itself does most of the generalising, and the effects edge is within 0.02
after 500 fine-tune games. Training on generated powers taught nothing a
bench could see (gen16 / gen128 -0.004 / -0.006; the 1-copy bench could not
see even an oracle); a 10-minute burst lifts unseen generated powers +0.014
to +0.019 and its own cards +0.03 (bar +0.04); the one combined-novelty
read (unseen Guardian plus unseen cards) is -0.131 on every seed. Depth
repairs the turn-start class: on generated turn-start powers the heuristic,
which prices those cards by formula, loses 0.047 win rate from the swap,
while the 10-29 net loses 0.260 one turn deep and 0.120 two turns deep
(the A5 analyst's re-cut of results/gen_powers/depth/*.json joined to the
bench files, per trigger class, 16 cells of 6 cards; the critic's coarser
class means agree in direction, 0.620 to 0.594 against 0.508 to 0.318 and
0.611 to 0.547). The "depth does worse on card-played powers" finding is
mostly card weakness: the heuristic itself drops 0.649 to 0.254 there.
Generated content is still power cards only; no generated monster, attack
or skill has ever been played.

The engine-next series (specs 2, 4-9 and 10 stage 1; 26 commits in one
night) made every official card and power round-trip as data, kept every
old net and game bit-identical, and made search faster (the memo: one-turn
+52%, two-turn about 1.7x). It has not moved a play number because no net
has been trained on the branch: the default layout widened (rows 92 to 131
columns, cards 60 to 82, two new piles), the four new row kinds are opt-in
by the owner's own decision (row data 2.5x otherwise), and nothing has run
against the wider columns yet.

What has held the project back is not a wrong design but four habits.
The rulers sat one level below the goal (tight2 drops HP carried, run-HP
drops clears, the cell gauntlet drops the deck, the headline drops boss
end-HP and the map), and each new ruler reversed verdicts the old one
gave, after the CPU was spent. The learning loop has no teacher above the
student (training search equals deployment search), so it could take one
step and did. Depth, the one repair that generalises, costs 115-140x
one-turn per sequence (jobs/done: 500 one-turn sequences in 2.5 min, 250
two-turn sequences in 142-178 min, both at 3 threads) and about 1.4-1.6 GB
per two-turn thread, and the project spends it uniformly. And "dominant"
has no arena: every number is an 11-fight A0 chain with one relic, while
the field reports A20 Act-1 clears with relics, potions and a map
(docs/research/sts-bots-and-runs.md), and the simulator decision has sat as
the owner's call since 11-01 while the run layer grew on our engine by
default.

## The approaches, dissected

Likelihood means: the chance that the approach, continued as the project
practises it, moves goal 1 or goal 2 measurably and durably. The band is
the calibrator's range after the skeptics. H1 is "by 2026-11-14 on this
dev machine", H2 "eventually on this design with about ten times the effort".

| Approach | Likelihood | Band | One line | Recommendation |
|---|---|---|---|---|
| A1 Core thesis: afterstate nets over effect features, trained on self-play outcomes | coin flip, 0.42 | 0.30-0.55 | the substrate is proven at run level; the effects edge is small; the loop is flat by construction | change: keep the substrate and the 10-29 net; stop recipe arms read on proxies; a stronger teacher when the loop next runs |
| A2 Play-time search: depth, the leaf objective, cheaper search | coin flip, 0.50 | 0.35-0.65 | the largest gains so far; cost 115-140x; a c retune upward is a measured loss | continue, re-aimed at cost first, then depth where fights are close |
| A3 Training-side leaf improvements | unlikely, 0.30 | 0.20-0.42 | 0 of 10 newer nets shown to beat the 10-29 net at run level; seed sd for from-scratch recipes unmeasured | change: gauntlet-only reads; fix the ruler; only a stronger-teacher arm earns a slot |
| A4 Rules-engine series (engine-next) | unlikely, 0.38 | 0.26-0.50 | expressibility proven; the net-side value undecided because nothing trained on it; memory unmeasured | change: a rows-on vs rows-off burst as its verdict; "old nets load" going forward; generator to attacks and skills; stop stages 3-5 for now |
| A5 Goal-1 programme | unlikely, 0.30 | 0.20-0.42 | training arms 0 +- 0.01; benches read on mis-ranking cells against a blind reference; depth repairs the turn-start class | change: retention on full-HP fights with a card-strength reference; a generated character and a mutated-monster bench |
| A6 Run layer | coin flip, 0.55 | 0.40-0.70 | the largest internal lever; no outside number | continue: a fitted run value; a mini-map; put the simulator question to the owner |
| A7 Measurement and process | coin flip, 0.50 | 0.38-0.62 | protocol plus confirmation works; the rest catches proxy errors one level late | change: a promotion clears its bar by one seed sd; re-rank on the headline; a goal-1 ruler |
| A8 Exact solver and solved DB | very unlikely, 0.06 | 0.03-0.12 | ground truth where the evaluator is least needed; the solve step reads about 0 HP at run level | stop the training side; keep puzzles.json as a free check |
| A9 "Dominant like Stockfish" and the simulator decision | unlikely, 0.38 | 0.25-0.50 | ingredients present or affordable; no arena; the decision is being made by default | change: an arena ladder; sts_lightspeed for parity only; one two-turn self-play round |

**A1, the core thesis.** The agent never picks a card; it picks between
afterstates scored by a small Deep Sets net over effect primitives, trained
by regression on final scores of its own one-turn play. Three parts, three
fates. The substrate (engine lists afterstates, net scores the leaf, search
picks) is proven at run level, about 0.75: the net beats its teacher, the
heuristic, at equal depth, and the held-out half's end-HP lead at two
turns (+4.90, se 1.08) is nearly the train half's (+5.51). Two cautions:
the HP price c was tuned on the same 0-499 book, and where the pieces can
be separated (burst8hp2 on 0-249) depth alone at @hpb is +0.012 clears /
+1.26 HP and the hand-written end-HP price adds +0.032 / +1.90 HP, so the
proven configuration is the net plus the search-time prices, not the net
alone. The effect features as the way to play unseen content, about 0.3:
the edge is 0.02-0.07 per fight zero-shot, vanishes after fine-tuning, and
has never been measured at two turns or at run level (the reads are now
queued, Q6). The self-play loop, about 0.1: training search equals
deployment search (one turn, limit 16, temperature 0), so after round 1
(+0.017) there is no teacher above the student; rounds 2-10 read +0.006 to
-0.003. The abstract reason: a value regressed from single outcomes of a
greedy policy learns that policy's outcome at the resolution the labels
carry; any quantity whose cost lands after the scored state and barely
varies in training (HP under a random start, a Strength stack paid next
turn) gets near-zero weight, and the simulator supplies those quantities at
decision time more cheaply than labels can teach them. Recommendation:
change, not stop. Keep the substrate, the contract, the heuristic as
reference and the 10-29 net under two-turn @hpe; stop outcome-regression
recipe arms read on fight proxies; when the loop next runs, label elite
and boss states with the two-turn product's values (or its games'
outcomes) and read only under the protocol. Cheapest decisive test: six
one-turn cell gauntlets of the ids5k and data5k r1 twins (seeds 1 / 101 /
201) @hpb0.01 with --against, about 0.3 thread-hours each; effects ahead
by 1 HP end-HP on the held-out half over 3 seeds keeps representation work
funded, a gap inside 0.4 HP pauses it. The manager's queued Q6 reads ask
the same question on the generated bench instead; both are cheap, the
gauntlet one is in the goal's unit.

**A2, play-time search.** The player lists every afterstate, scores each
with the net, and in the product looks one turn further with four sampled
hands and the HP prices on top. This family holds the project's largest
gains (the two prices about +0.20 clears together; depth +0.060 on the
tuning book, +0.044 on the fresh book, +3 to +3.6 end-HP). On where
depth's gain lands, the skeptics corrected both the analyst and the
synthesis: on the tight boss bench (fights calibrated to be close) depth
wins +0.118 per fight (1,480 fights, se 0.018 clustered by cell); in the
gauntlet's own unit the gain lands before the boss (more sequences reach
it, 3-4 HP richer), and at matched entry HP the nets' two-turn boss win is
no higher than one-turn's (champion, 30-60 HP entries: about 0.44 vs 0.49,
n 216 / 230; only the heuristic pair shows a clean +0.06). So whether more
depth at the boss would pay is open, not shown. What limits depth is cost:
115-140x one-turn per sequence, 4-5 GB per 3-thread job, and the one cheap
candidate, raising c, is a measured loss (10-29 net @hpb0.02 vs 0.01:
-0.032 clears, se 0.010; c 0.005 level). Mixed depth (floors 1-3 one turn
deep) is level with full depth on the cell gauntlet (end-HP -0.02, se 0.05)
at 57% of the wall time and is now the screening default; the headline
setting has not been checked. Likelihood 0.5 that a further search-time
change clears +0.02 clears or +1 HP on the headline at affordable CPU.
Abstract reason: search-time gain is (how many decisions are close within
the horizon) x (how wrong the leaf is on them), and each extra turn
multiplies cost by about 100x while the mass of close decisions it newly
reaches shrinks; uniform depth is the wrong shape for an exponential cost.
Recommendation: continue, re-aimed at cost (commit to the searched line,
the sampled-draw leaf, the memo merge, mixed depth), then spend the saving
where fights are close. Cheapest decisive test for more depth: replay from
results/gauntlet/net1029-hpe0.01-two-a.json the floor-9 elites where the
product lost 15+ HP and the bosses entered at 50-69 HP, three players on
common seeds (two-turn product, three-turn, a two-turn-rollout leaf),
elites first, one thread per fight, stop after 4 thread-hours; 2 HP saved
per elite or +0.05 boss wins justifies a selective-depth spec, under 1 HP
closes three-turn and rollout leaves for goal 2.

**A3, training-side leaf improvements.** Keep the search fixed and change
what the net trains on. None of the ten nets trained after 10-29 is shown
to beat the 10-29 net on the one-turn gauntlet (best burst8 s1 +0.82 HP,
se 0.55, undecided; the rest -0.5 to -2.7 HP), and the two promoted on
tight2 and run-HP read level or about 1 HP worse. Every arm that moved a
proxy supplied information the leaf state lacks (start HP, a power's
per-turn worth), and search supplied the same information more cheaply.
Two things soften the "closed" verdicts. The run-level seed sd of about
0.4 HP rests on four twin pairs that share one round 0 (a point estimate
nearer 0.25 HP with an interval that admits 0.6-0.7); on tight2 the seed sd
roughly doubles when each seed has a fresh round 0, so run-level seed noise
for data40k, data80k and cover21 may be larger than 0.4 HP and is
unmeasured. The lean vs lean-thr gap (+1.47 HP, se 0.46, same round 0 and
seed) cannot be read as seed noise, because threshold rows change the
feature layout and the s1 tight2 read agrees in sign; two one-turn plays
(lean s101 r2, lean-thr s101 r2) decide which reading holds. Also the
"solve step costs HP" reading does not survive a like-for-like pairing
(lean s1 vs the three 10-29 twins: -0.51 / +0.07 / -0.15 HP). Likelihood
0.3. Abstract reason: a supervised evaluator trained on outcome labels can
exceed its label generator by about one step, because regression averages
the generator's per-decision noise; after that it learns no more than the
generator's play distribution and the label's horizon show, and nothing a
selector reading a different unit from the goal can see. Recommendation:
change how the side is run. Every goal-2 training read on the protocol
with --against, one turn to screen and two turns to confirm; fix the ruler
first (play lean s101 and lean-thr s101, about 25 min each); admit an arm
only when it names a measured bias and an expected run-level effect above
the MDE; the one live mechanism is a stronger teacher (fine-tune the
10-29 net on two-turn @hpe values or outcomes of 50-100k of its own
decisions, 2 seeds). The survival arms keep their pre-registered rule
(docs/specs/survival-score.md "The experiment": run-HP against lean-hpw2
and lean-thr, >= 1.0 HP per fight on 2 seeds) and get a one-turn gauntlet
read beside it, against net1029-hpb0.01.json with the bonus controls and
nob_probe; the gauntlet read is the one that says whether the design
matters for goal 2.

**A4, the rules-engine series.** engine-next turns amounts, statics,
replacements, decision points, a known top card, per-copy variants,
monster patterns and content packs into data the engine interprets. As
engineering it did what it promised (eight specs in one night, every
official card and power round-trips, bit-identical on 4,703 states,
search faster than before the series). It has not moved a play number,
and the honest reason is that no net has been trained on the branch, not
that no net could read the rows: the default layout widened (rows 92 to
131, cards 60 to 82, piles next_draw and known_later); only the four new
row kinds are opt-in, and the owner confirmed that opt-in on 11-02 for
memory reasons. The net-side thesis (a net prices an unseen mechanic from
its rows) is therefore undecided rather than refuted: the zero-shot record
on the existing encoding is mixed (effects +0.075 held-out elites, +0.060
Silent tier B; the generated-power arms were read on a blind bench; check
9 is noise-dominated), and the warm-start curve can resolve a 0.03 effect
(paired intervals about 0.015 wide). Landing is cheap in time (fast-forward,
golden.txt byte-identical) but the state grew 1,028 to 1,268 bytes and no
peak-memory number exists for two-turn search on the branch, while
two-turn jobs are memory-bound; and engine-next.md warns that a post-merge
training run compared against pre-merge nets gets the wider columns, a
confound any branch training must control for. Likelihood 0.38. Abstract
reason: the series builds two capacities and the project scores them as
one. Capacity to express content (the simulator can hold a new card, power
or monster so search can look through it) is proven by construction and
already paid a by-product. Capacity for the net to read content is
unproven in either direction, because the series' own rule kept every net
unchanged and nothing has been trained since. Recommendation: change, not
stop. Run the rows-on vs rows-off burst as the series' net-side verdict
before any further "the net reads the atoms" spec; for future content
specs relax "bit-identical" to the contract's "old nets load", retraining
only when a content set changes and reading it under the protocol; spend
the next build effort on the two pieces that need code and
little CPU (extend gen_content.py to attacks and skills; a mutated-monster
bench from spec 9's pattern rows); stop stages 3-5 and entity-shape until
a bench or content needs them; measure two-turn peak memory on the branch
module, then land. The owner's four runtime-registry questions have
low-regret answers: stage 1 then 2 now, stage 3 when a monster bench needs
it; keep the Rust tables as the source with files checked equal; one
registry per process until a generated character needs more than 8 slots
(see approach 4 below); question 4 is answered by the memo (speed
recovered without a sparse state). Cheapest decisive test: on the branch's
own module (PYTHONPATH=target/pyroot, no merge), fine-tune the 10-29 net
twice with the burst recipe on 4,000 champion-played games holding 3
copies of the series' proving cards (Wraith Form, Caltrops, Accuracy,
Headbutt, Rampage), once with extra_rows on and once off, 3 seeds each,
read paired by fight on a 3-copy bench: a contrast of +0.02 at 2 se says
the rows carry value, under +0.01 says they are simulator data only.

**A5, the goal-1 programme.** Five things were tried: the effects
encoding, held-out checks against the heuristic, generated powers through
registry-lite, training-side arms, and depth as a repair. Every
training-side arm came out at 0 +- 0.01 on 3 seeds; the burst missed its
+0.04 bar twice; and nearly every read sat on tight2 cells where the
heuristic beats the product one turn deep (0.620 vs 0.508 on the
originals) against a reference blind on 84% of generated powers, so card
strength was read as player skill. The one real positive is depth on the
turn-start class (the per-class swap costs above); the card-played
negative is card weakness. No generated or mutated monster exists; the
Guardian case says gaps compound. Likelihood 0.3 that the programme as
practised reaches goal 1 in the owner's horizon. Abstract reason: a
learned leaf is a cache of payoffs it watched land inside its horizon, and
this cache was filled by a one-turn player, so the net inherits a one-turn
horizon twice (in what it watched and in how far it looks); novel content
has no entry in that cache by definition, and neither does a known
mechanic whose payoff falls past the horizon, so the error on new content
is a horizon error that only the simulator (search, play-outs, a
simulation price) can repair, and the representation decides only whether
the cache misses gracefully (effects) or collapses (ids). Recommendation:
change the programme, keep the goal. Stop content-share arms, per-mechanic
columns, bursts judged on tight2 and raw swapped-card win rates; define the
headline as retention of the net's lead over a card-strength reference on
full-HP, run-like fights (the generated character and the mutated-monster
bench below); run the burst-plus-depth pairing and the effects-vs-ids
reads; ask the owner the bundles-versus-atoms question (decision 1).
Cheapest decisive test: publish the per-class table (both players, both
depths, both benches, the heuristic's swap cost beside the net's, with the
pairing method stated) from the existing results/gen_powers/depth files;
then the burst-plus-depth pairing on cells where the heuristic's swap cost
is within 0.10, about 1.5 hours in a two-turn slot.

**A6, the run layer.** After each won fight the chooser scores three card
offers by simulating the next floor and the boss with the combat player;
removal and path choice are being added as flags. From the starter deck:
random picks 0.364, the sim chooser 0.548, the boss horizon 0.680, both
halves agreeing; the Strike rule +1.78 HP (z 2.2) at fixed 500, the
simulated-removal chooser closed; the rest-site chooser failed (-1.22 HP,
winner's curse at 16 sims per option); the elite-skip flag (fight a
hallway instead of an elite, always or under an HP threshold) is built and
reads next. One claim from the panel did not survive its skeptics and is
dropped: "about half of the card-pick gain is the net recognising cards it
trained on". The held-out half's offer pool is the train pool plus 10
strong held-out cards (only 32% of its offers are held-out cards), the
net-over-heuristic half gap is already present on fixed decks, and the
net picks unseen cards at least as often as they are offered; a clean
seen-vs-unseen read needs offers drawn from held-out-only pools of matched
strength. What does hold: the net's lead widens from +0.038 to +0.146
clears when each player also chooses, but no arm crosses the net player
with the heuristic chooser, so "the run layer multiplies the player" and
"better picks plus better play" cannot yet be told apart. Nothing here
produces a number comparable outside (no map, relics, potions, Ascension
or Acts 2-4). The paired noise of the headline setting depends on where a
decision sits: about 18-23 HP per sequence for decisions that diverge decks
from floor 1, about 4 HP for a pre-boss choice (the panel's estimate from
the arm files; treat as approximate). Likelihood 0.55 (about 0.75 as an
internal lever, about 0.35 as a path to "dominant"). Abstract reason:
clears are set by the deck and the HP you bring, both decided outside
combat, so a chooser that simulates run decisions with the combat player
compounds whatever that player is worth; and because the game it plays is
internal, every number measures distance from its own baselines, never
distance from "dominant". Recommendation: continue with four changes. Fit
the run value (approach 3 below) and make it the choosers' unit; report
every chooser gain split train / held-out and build any learned chooser on
held-out offers; after removal and elite-skip, stop adding one flag at a
time and build a 2-3 route mini-map, because the single-rest,
single-removal shape is out of levers above 1 HP; put the simulator
question to the owner with a recommendation (decision 2). Cheapest
decisive test: two one-turn headline jobs with the players crossed (the net
plays, the heuristic chooses; the mirror), --against the headline file,
read split by half, about 30-60 min each.

**A7, measurement and the operating process.** The stack of rulers plus
the machinery that spends CPU. The gauntlet protocol with a fresh-book
confirmation is the first ruler in the goal's unit and it works: the net
swap replicated on 500-749, and the depth verdict also has a fresh-book
read (the +0.044 / +3.25 HP pairing above). Everything else is weaker than
the analyst wrote: the headline setting carries about 3x less information
per sequence and no standing player has been re-ranked there; the seed
discipline let burst8hp2 through on a bar it passed by 0.19 HP against a
seed spread of about 2 HP (results doc line 1867), and the next ruler
reversed it 28 hours later; early stop carries about 0.02 clears of
optimism (sim-boss +0.155 at n 200, +0.132 at n 500); goal 1 has no ruler. Throughput is fine (about half of the machine's
threads booked, reads within 0.3 h of a job ending) and is not where the
risk sits. Likelihood 0.5. Abstract reason: a ruler that drops one stage
of the objective ranks near-copies right and recipe changes wrong,
because a recipe change trades the dropped quantity against the kept one;
a guard built on that ruler inherits the blindness, so the process catches
its proxy errors one level late and pays twice, in thread-hours and in
verdicts that stand on a tuning book until someone pays for the fresh-book
read. Recommendation: keep the protocol, the twins rule and the
confirmation book; a pass must clear its bar by at least one seed sd of
the ruler it is read on; re-rank the standing players on the headline
setting before building verdicts on it; give goal 1 a standing number this
week; read a protocol "fail" as "not 1.5 HP better" and record the fixed-n
gap beside every verdict; pre-chain jobs with --against so the runner works
a day unattended. Cheapest decisive test: play the standing
players (heuristic, 10-29 net, burst8hp2, data40k, data80k, lean-thr,
cover21; one turn @hpb0.01) on the headline setting with --against, about
3-4 thread-hours in all; the same order as the cell re-rank settles the
goal-2 ruler, a flipped order means the week's verdicts were read on the
wrong population.

**A8, the exact solver and solved database.** Solve small endgames
exactly, store them under a rules fingerprint, use the values as labels
and as a yardstick. The solver is correct and the net can fit its values,
but nothing downstream moved play: 77.6% of puzzles are horizon 0 where
one-turn search is already exact, two-turn search reaches horizon 1
(regret 0.006), the decisions that change outcomes sit four or more turns
out, exact-only nets play -0.11 to -0.22, more exact labels hurt held-out
play, and at run level the no-solve-step lean net is level with the
solve-step recipe's three twins (-0.51 / +0.07 / -0.15 HP). Whether exact
labels in round 0 matter is not cleanly separated by any run-level read.
The step cost 70% of a round's wall time; the database has held 0 rows
under the live fingerprint since 10-30; sts.solve panics on generated
content. Likelihood 0.06. Abstract reason: ground truth that is cheap to
compute is cheap because the position is already nearly decided, so it
arrives exactly where the evaluator is least needed; and a cache keyed on
the whole rule set cannot serve a project whose goal is to change the
rules constantly. Recommendation: stop the training side, keep the free
bench. solve_games 0 by default when learn.py is next touched; do not
build ideas#72; drop the post-series refill unless a consumer appears;
mark test_bounds skipped with a reason; archive db/ after the owner's OK
(decision 7); keep data/bench/puzzles.json as a regression check; send
ground-truth questions that matter for runs to sampled play-outs on
mid-fight states, the method that found the biases. Cheapest decisive
test: lean s101 and s201 r2 on the cell gauntlet (two one-turn plays)
against the three 10-29 twins; under +0.5 HP for the solve-step nets closes
the question for rounds 1-2.

**A9, the strategic frame.** "Copy Stockfish's recipe and call the result
dominant." The ingredients that transferred are the ones that widen what
the player optimises over (a priced currency, the next turn, the deck, the
boss); the learned leaf matters and its value shows only when read on the
outer unit. What is missing is the arena: every number is an A0 11-fight
chain, the field's numbers are A20 full runs, and the simulator decision is
being made by default. The sts_lightspeed route cannot deliver a number in
the field's unit from today's engine: it holds about 35 of 75 Ironclad
cards, A0 monster values only, no Slavers or Gremlin Gang, no curses, and
stock lightspeed exposes no per-decision battle loop to Python (the panel's
reading of its sources; unverified by a build). A 20k-game two-turn
self-play round is roughly one overnight slot, so the one Stockfish
ingredient never tried as Stockfish uses it (the product as teacher) is
affordable once. Likelihood 0.38. Abstract reason: a strength recipe
borrowed from a game with one horizon, one objective and an existing arena
was applied to a game with nested horizons (turn, fight, act), a carried
resource (HP) and no arena; "dominant" is a property of an arena, not of a
player, so until the arena and its setting are chosen every strength number
is in a unit no one outside can read. Recommendation: change. Write an
arena ladder into manager.md (Arena 0: our gauntlet against an
outside-designed fixed chooser; Arena 1: a stated headless Act-1 setting on
our engine with a map, common relics, potions and Ascension knobs; Arena
2: the real game through a mod bridge); time-box a lightspeed build (the
ucrt64 toolchain is present) to a floor-and-ceiling number and an A0
parity harness, never a play or training engine; keep one two-turn
self-play round as the last training test of this phase. Cheapest
decisive test: port BottledAI's Ironclad card-pick priority list (MIT, data
not code) as a fixed chooser with the heuristic in combat and read the
product against it under the protocol; a wide win says the remaining
problem is the arena, a level read says play still has to grow.

## The patterns behind the record

These are the structural reasons behind the verdicts, stated so they stay
true if the details change. They are what the owner asked for as abstract
thinking, and they predict which future approaches will work.

**1. The ruler sits one level below the goal, and a guard built on it
inherits the blindness.** Each yardstick dropped one stage of the
objective: tight2 drops HP carried between fights, run-HP drops clears, the
cell gauntlet drops the deck, the headline drops boss end-HP and the map.
Such a ruler ranks near-copies (one net under different search settings)
right and recipe changes (a different net) wrong, because a recipe change
trades the dropped quantity against the kept one; and a pre-registered bar
read on it passes exactly what the next ruler reverses. Evidence: data80k
is the best newer net on tight2 and fourth on the gauntlet (-1.86 HP, se
0.52); the ladder read the HP bonus at -0.0012 while the gauntlet read
+0.168; burst8hp2 passed its run-HP bar by 0.19 HP and was reversed 28
hours later; sim-boss read +0.155 at the early stop and +0.132 at 500; 163
of 340 headline clears (48%) end the boss under 30 HP, which the gauntlet
scores at zero. Implication: read every goal-2 change on the protocol,
require a pass to clear its bar by one seed sd, re-rank standing players
whenever the headline moves, and prefer changes whose value does not
depend on the gauntlet's shape (budget pricing, horizon, deck value,
cheaper simulation) over constants tuned to it.

**2. The leaf is a snapshot cache filled by its own one-turn play; the
simulator supplies what it cannot see.** The net regresses final scores of
games played by a greedy one-turn policy from a state paused before its
own turn-start hooks fire. Anything whose cost lands after that state and
barely varies in training (HP from a random start, a Strength stack paid
next turn, Poison ticks, a turn-start power) gets near-zero weight; and
because training search equals deployment search there is no teacher above
the student, so more or cleaner labels of the same kind change the loss,
not the play. Evidence: nets priced hallway HP at 1/10 to 1/100 of the
label price and @hpb fixed it with no training; bias-audit ratios 0.25 /
0.27 (Strength) and 0.65 / 0.17 (Poison) on the champion, 0.17 / 0.18 and
0.04 / 0.08 on the 10-29 net; round 1 +0.017 then flat; rung-4 labels
+0.002; data 40k to 80k +0.003; depth +0.060; Silent Poison +0.32; the
turn-start swap cost 0.260 falling to 0.120 under depth. The twist that
matters: the 10-29 net prices Strength and Poison worse than burst8hp2 and
beats it by +3.01 HP, and a correct-sized flat Strength price (@esp0.04)
fixed Nob and lost -0.020 clears. So the audit's mis-priced quantities are
not what separates nets at run level today, and the one leaf-side price
tried (a flat constant at one turn) is the only member of its class that
has been tested; the survival arms are the first fair test of the class.
Implication: stop label, data, coverage, ensemble and per-mechanic arms as
goal-2 levers; the training change with a base rate is a stronger teacher
(data from the two-turn product); leaf-side time inputs are goal-1
experiments admitted by the audit and read on Silent Poison and turn-start
cells, never promoted on the audit alone.

**3. Levers compound upward: the deck and the HP budget decide clears,
and the run layer carries the combat player's worth into the run.**
Measured gain grows with the level of the decision changed (recipe about
0, evaluator +0.04 to +0.06, horizon +0.06, HP price +0.17, deck +0.18 then
+0.13), and the net's lead over the heuristic is four times larger once a
chooser picks cards by simulating with it (+0.038 on cells, +0.146 on the
headline), though the crossed arm that would separate "multiplies" from
"adds" has not been run. The HP price is a straight line through a
sigmoid: on the headline file boss win by arrival band is 0.31 / 0.44 /
0.83 / 0.87 / 0.97 / 0.99 from the 30s to the 80s (n 51-103 per band), 94
of 107 boss deaths arrive under 60 HP, a logistic fit gives dP/dHP 0.028 at
40 HP and 0.002 at 78, and the position of the jump moves with the boss
(Guardian 0.13 to 0.89 between the 40s and 50s; Slime Boss already 0.56 in
the 30s). The prior "flat price" read (run_value.py) measured dP/dHP at
each floor's median HP and compared floors, so it could not see the
variation along HP. The slope is observational (deck strength and boss
identity confound it; the cell covariate does not flatten it), so it is an
upper bound on the causal worth of an HP. Implication: read combat changes
on the headline setting; fit a run value from the roughly 30k
sequence-floors on disk and make it the choosers' unit, later the leaf's
price, keyed by (boss, HP) rather than HP alone; build a mini-map, not one
flag at a time.

**4. Simulation at decision time is the universal repair, and its cost
has the wrong shape.** Depth, the choosers and the HP prices all work by
asking the simulator at the moment of decision; every attempt to move that
into weights was null or reversed. The limiter is cost: each extra turn
about 100x, a turn rebuilds about four two-turn trees (3.82-4.00 decisions
per turn, cut shares 1-5%, results/depth/*.json), two-turn 115-140x
one-turn per sequence, about 1.4-1.6 GB per thread, memory caps the
machine at two two-turn jobs. Uniform depth is the wrong shape for an
exponential cost: depth is worth +0.118 on close boss fights and nothing
on floors 1-3 (mixed depth level at 57% of the time). Implication: cost
work first (commit to the searched line, the sampled-draw leaf, the memo,
mixed depth), then spend the saving where fights are close after a
matched-HP probe; cheap depth is also the only route to a stronger teacher
and a better chooser sim player.

**5. Expressibility is not valuation, and the goal-1 benches confounded
card strength with player skill.** Making a mechanic data lets the
simulator run it and search look through it; it does not make a net price
it. The series proved expressibility by construction and trained nothing,
so nothing could be measured. The goal-1 benches sat on tight2 cells where
the heuristic beats the product one turn deep and used that heuristic,
blind on 84% of generated powers, as the reference; so most negative
results are about the yardstick, and the one positive result (depth) is
legible only on the class the heuristic prices (turn-start). Zero-shot
evidence is mixed, not negative. Implication: goal-1 numbers on full-HP,
run-like fights with a card-strength reference beside them (a generated
character with near and far packs; mutated monsters with the heuristic's
own loss as the reference); one burst test of the series' rows; "old nets
load" replaces "bit-identical".

**6. Teacher equals student, and the one exit was never taken.** Round 0
is heuristic games; later rounds add a small top-up of games played by
one-turn search over the previous net at the same search settings as the
player (config: rounds temperature 0, search limit 16). The data policy is
never stronger than one-turn search over the current net, so supervised
regression on its outcomes can only re-fit that policy's value with
different noise. What was tried against this ceiling was distillation of
two-turn rankings (-0.03 on elites), which the prior-art scan names as the
known weak link; what was never tried is the plain form: generate the
games with the two-turn product player and regress on their outcomes.
Implication: one two-turn self-play round (about 20k games, an overnight
slot after the cost work) is the last training test worth running in
this phase; everything else on the training side waits for it.

**7. Variance lives in the sequence, and the yardstick decides what counts
as headroom.** Which deck and fight sequence is drawn explains about 72-76%
of clear variance, the player about 2%; 116-127 of 500 cell sequences are
lost by every player and about 200 cleared by every player, so player
comparisons are decided on about a third of sequences. Whether a sequence
is "unwinnable" is a property of the test bed's missing choices (fixed
deck, fixed path, a known boss that cannot be routed around), not of
combat: from the starter deck the run layer alone moves the "unwinnable"
share from 1.000 to 0.320. Implication: paired designs, common random
numbers, sequential tests and variance cuts (boss replays, a result cache
for run-layer reads) are the only way to see player effects; and the
combat-ceiling question cannot be answered on fixed sequences, because the
largest "combat" decision in the real game is which combats to take.

**8. The operating loop selects for work that finishes in one wake-up.**
A manager every two hours with 9-minute median jobs (jobs/done) screens
existing nets with search-time knobs very well and cannot start anything
that needs days: the engine re-scope was recommended three times and not
acted on, the simulator decision has been "not acted on" since 11-01, seven
reviews in four days re-derived the same two findings, and the champion
path returned to the 10-29 net. The same loop found every real gain of the
week and corrected its own promotions within a day, so this is a ceiling,
not a failure. Implication: charter two or three multi-day lanes with checkpoints,
pre-chain jobs, and run a review after a headline change rather
than daily.

## Approaches to try

Ranked by expected value per CPU-hour and by how decisively a first check
settles them. The first six come from the judged candidates with the
judges' fixes grafted in; the seventh and eighth are from the abstraction
passes and were not judged by the panel, so their probabilities are the
author's. On this record nothing that changes play has better than even
odds; the approaches with the best odds are the ones that make simulation
cheaper, and the ones with the best payoff if they pass are the run value
and the generated character.

### 1. Commit to the searched line: one two-turn tree per turn (p about 0.6)

**What.** The two-turn player rebuilds its whole tree after every card
play, though the tree built at the turn's first decision already holds the
best line to End turn. Stage 1, Python only: in depth_paired.py's
guarded_fight, seed the two-turn search per turn instead of per decision.
Because sample_rng is keyed by (seed, turns left, state turn, ord, i) and
not by the root (engine/src/search.rs:118), re-searching the chosen child
under the same seed rebuilds the same subtree, so this player makes the
decisions a committed-line player would, with no engine change. Stage 2,
about 30-100 lines of Rust: export the principal line from search.rs (walk
the argmax children to End turn or the first chance node), expose it in
py/src/lib.rs, and step the whole line when nothing was cut; re-search
after a chance event or a cut as today.

**Why it is likely to work.** The redundancy is measured (3.82-4.00
decisions per turn, cut shares 1-5%); the only thing lost is fresh samples
at later decisions, and two sample_k 4 seeds disagree on about 6% of
decisions. Every prior cost step delivered as promised. Honest speedup:
about 1.5-1.9x on the two-turn part (unverified; the first tree may already
be half a turn's cost under the within-turn memo), stacking with the memo
(1.7x) and mixed depth (about 1.7x), so a 250-sequence two-turn read falls
from 142-178 min toward 40-60 min. Success here is cost, not strength, and
cheap depth is what approaches 2, 6 and 7 need.

**First check.** (a) Agreement: on a few hundred held-out elite and boss
decisions, the per-turn-seed player against today's product; pass at 99%
or more agreement off cut decisions, plus a 10-minute single-thread probe
timing each two-turn search by its index within the turn. (b) Only if
agreement is under 99%: play the per-turn-seed player on sequences 0-249
against results/gauntlet/net1029-hpe0.01-two-a.json; pass = paired end-HP
within +-1.0 HP and clears within +-0.012. (c) Stage 2 row-identical to
stage 1; cost read as summed nodes and leaves (pass: committed / baseline
at most 0.65); wall time reported only, because the machine is shared.

**Cost and dependencies.** Half a day for stage 1 and the probe, a day for
stage 2 plus a build and the .pyd swap; CPU minutes for the probe, 3-4
thread-hours in one slot only if the play read is needed. Nothing outside
Python for stage 1; a small engine change for stage 2; no owner decision.
Serves goal 2 throughput and makes a two-turn chooser and two-turn
self-play nearer affordable.

### 2. Sampled-draw leaf: sample the hidden hand, fire turn-start hooks, score the concrete position (p about 0.4)

**What.** Keep the one-turn tree. At each End-turn leaf sample k = 4 draws
with the existing sample_k machinery and common random numbers, advance
through the player's turn-start hooks to the awaiting-action state, and
score that hand-in-view state with the net; no second-turn tree. About
(1 + k) one-turn leaves instead of about 200x, 1.5-2 GB per job. Plumbing:
a SearchConfig field and a Leaf branch in search.rs expand(), the knob
through lib.rs, bench.py, ladder.player_key (so caches never mix) and
gauntlet.py; about 100 lines.

**Why.** The net fits post-draw decision states far better than paused
states (held-out MSE 0.011 vs 0.092 for one net in the record), the
training set holds decision states so this leaf is in-distribution, and
two-turn's gain lands where the next hand decides (Sentries deaths 22 to
11, Nob 23 to 10, Lagavulin 20 to 14). Turn-start hooks fire inside the
leaf, which is goal 1's measured novelty class. Against: the leaf still
sits before the monster's next attack, so Strength and Poison accrual is
not extended; expect a partial recovery of two-turn's gain, which is why
the free screen comes first.

**First check.** Step A, near-free: on the 300 bias-audit states (32
cached play-outs each) compare the paused-leaf value and the mean of k = 4
sampled post-draw values against the play-outs (error and rank
correlation), and on the exact-puzzle bench at horizon 1 or more the regret
must fall by at least 0.01 from 0.0189. If neither moves, stop. Step B:
one-turn cell gauntlet @hpb0.01 --draw-leaf 4, sequences 0-499, --against
results/gauntlet/net1029-hpb0.01.json; pass = protocol pass and wall time
under 10x one-turn's 2.5 min. Step C, descriptive: the share of two-turn's
gain recovered on 0-249, with an interval; a "draw plus one monster step"
variant tells the missing hand from the missing hit.

**Cost and dependencies.** One session day on the engine-next branch
module (PYTHONPATH=target/pyroot, no merge); about 2 thread-hours under
2 GB. Serves goal 2 (depth's gain at a fraction of its cost, usable in the
chooser and as a self-play data generator) and goal 1 (the turn-start
class).

### 3. A fitted run value as the choosers' unit, then the HP price (p about 0.4)

**What.** Fit V_run = P(clear | HP, floor, boss, deck summary) on the
roughly 30k sequence-floors in the starter-setting files under
results/gauntlet (a band table or 2-knot spline in HP per floor, a
took-based deck covariate, HP lost so far as a play-luck proxy;
CPU-minutes, reusing run_value.py). Use 1, Python only: make V_run the
terminal value of the chooser's simulated next-floor fights, factored as
P(reach the boss at h) x P(win the boss | h) so the option's own boss sims
replace only the second factor and the boss is never counted twice; add a
skip-margin rule. Use 2, only after a chooser pass: the search's HP term by
floor through per-floor player strings (net@hpb<c_k>), no Rust, with a
guard that floors 1-4 end-HP does not fall against flat c, read against the
two-turn headline. Use 3, when the survival arms exist: leaf value = sum
over the histogram's bins of p(h) x V_run(HP - h).

**Why.** The curvature is in the data (boss win 0.31 to 0.99 across HP
bands; floor-8 entry 0.06 to 0.95), it transfers across players, the
chooser's unit was never varied, 34% of offers are made under 55 HP, and
the chooser costs about ten times the play it feeds. Against: the slope is
observational, chooser gains so far were deck not HP, and raising c
uniformly loses, so step 0 is a real gate. The 11-02b review proposed the
same object and the manager closed it on a test along floors, where the
curve is flat; nobody looked along HP.

**First check.** Step 0 (minutes): both the deck-adjusted curve and the raw
bands must show at least a 3x slope ratio between 45 and 75 HP at floors
5-8. Step 1: one one-turn headline gauntlet, fit on 250-499 and play 0-249
then mirror, --against results/gauntlet/net1029-hpb0.01-starter-simboss.json;
record both scores and both picks per offer; require a pick-change rate of
at least 10%; pass = protocol pass, or end-HP >= +1.0 HP at z >= 2 at fixed
500 with clears not below -0.01. Under 5% pick changes: go to the
V_run-prior-plus-32-sims form.

**Cost and dependencies.** Fit under a minute; read 16-33 min at 3 threads,
about 1 GB; half a session day. Python only, existing files, no owner
decision; refit when the product or the gauntlet's shape changes. Serves
goal 2 (the run-state value that removal, rest, path, a mini-map and a
second act need; a less noisy chooser; the unit for the survival arms'
price).

### 4. A generated character on the headline gauntlet: goal 1's standing number (p about 0.5)

**What.** On the engine-next worktree's own module: extend
scripts/gen_content.py (today Power cards only) to emit attacks, skills and
powers mutated from official parents as two packs, "near" (one number
changed) and "far" (type, cost, target changed and a hook from the
(trigger, effect) vocabulary added); a starter deck, a max HP, Burning
Blood. Add --pack, --pool pack and --max-hp to scripts/gauntlet.py. Play
four players one turn deep @hpb0.01 on the headline setting, 500
sequences, paired: the heuristic, the 10-29 net zero-shot, its ids twin,
and the 10-29 net after a 10-minute burst on the pack. Solve the 8-slot
cap first: registry SLOTS = 8 generated kinds per combat, and 90% of
headline runs take more than 5 distinct rewards, 17% more than 8; either
an official Strike/Defend/Bash starter plus an 8-kind generated pool (and
say so), or raise SLOTS on the worktree module and widen the net with zero
weights.

**Why.** The run layer is content-agnostic and carries the evaluator's
lead, so a whole character is the smallest unit on which goal 1 can be
measured at run level, at full HP where the yardstick ranks the product
right. A whole unseen character has a precedent (Silent: level one turn
deep, +0.040 two turns). Mutation from an official parent gives every
generated card a strength reference, the control every prior read lacked.
Every piece exists, and the headline gauntlet costs 16 min for 500
sequences one turn deep.

**First check.** Gate 0: the heuristic clears 0.40-0.60 of the near pack's
runs (budget set on the near pack only). Rule A: net above the heuristic
by the protocol on the generated character = pass; below by the same =
fail; between = level, run the two-turn read on 250 sequences (the Silent
precedent says one turn alone reads level). Report retention as a
difference of paired differences against Ironclad's held-out half, not a
ratio. Rule B: character burst minus a control burst of equal games on
Ironclad content, not burst minus zero-shot. Report HP lost per fight
beside clears (elites are cleared 0.99 / 0.94 at run-like HP, so a clears
gap cannot appear there), the per-trigger-class split, the chooser's skip
rate and pick distribution, and the far-minus-near gap as the measured
novelty cost.

**Cost and dependencies.** 4-6 thread-hours under 1.5 GB per job plus one
two-turn slot; 1-2 session days before 11-14 (generator, flags, a
"character" deck kind in finetune.py, the SLOTS change if taken). Depends
on the engine-next worktree module (not the merge), manager confirmation,
and the owner's bundles-versus-atoms answer for the far pack's top rung.
Serves goal 1 as the owner wrote it and tells goal 2 whether
representation work keeps a budget.

### 5. Mutated-monster bench, stage A only: the enemies rung on the bias-audit harness (p about 0.5)

**What.** Extend scripts/analysis/bias_audit.py's perturbations with
monster HP scaled (hp and max_hp by the same factor, x0.8 and x1.25; drop
Guardian states whose scaled damage crosses the Mode Shift line, sleeping
Lagavulin and lice), Strength +1/+2 at the sampled state, Metallicize 3 and
Ritual 2. Read per class: the leaf ratio for the 10-29 net; decision regret
of the one-turn product, the heuristic and the two-turn product (two-turn
only on the 100 worst states) by 32 common-seed play-outs; whole-fight
retention from the fight starts with 8 common seeds per start, (net minus
heuristic on mutated) minus the same on originals. Defer a per-combat
monster override into runtime-registry stage 3; call scaled fights "scaled
elites and bosses", not Ascension. A domain-randomisation burst only if
stage A shows a regret rise two-turn search does not halve.

**Why.** The apparatus runs end to end in 4 minutes at 0.6-0.8 GB; enemies
are the one goal-1 rung never measured; the Guardian case says gaps
compound there; the heuristic's own loss separates harder content from
worse play. Against: ratios do not track play, and max_hp is the net's
de-facto identity column, so the HP class is a representation test.

**First check.** HP class: regret rising on HP alone means "normalise or
drop max_hp". Strength and start-power classes: a regret rise of 0.05 at
one turn with two-turn recovering at least half = horizon problem, depth or
an accrual term is the fix, no training; unchanged everywhere = the leaf is
robust to stat novelty and the rung needs pattern mutation; regret up and
depth not recovering half = the burst is admitted. Zero-cost control before
any burst: run the plain burst twins through bias_audit.py; if a burst on
unperturbed games moves the ratio, the ratio is a recency artefact.

**Cost and dependencies.** 3-4 thread-hours under 1.5 GB, Python only on
main, one session half-day. Serves goal 1 (enemies) and goal 2 (what
A20-like scaling costs the product).

### 6. A result cache for run-layer reads, merged with boss replays (p about 0.8)

**What.** A run-layer decision at floor k cannot change floors before k and
the player is deterministic given the seeds: the strike-removal file is
row-identical to the headline control on floors 0-5 for 500 / 500
sequences, the rest-site file on floors 0-9 for 50 / 50, the sim-removal
file on floors 0-5 for 250 / 250. Every fight and chooser sim is seeded by
(sequence, floor) alone, so a per-player result cache in gauntlet.py keyed
by the full fight spec, like ladder.cached_play, gives the prefix saving
automatically and skips later floors where decks coincide. Add a
"reconstruct the state at floor k from a gauntlet row" helper and record
the deck per floor from now on; the same helper serves boss replays
(review 11-02b item 7) and the matched-HP probe.

**Why.** Byte-identity is deterministic; 61% of chooser offers sit on
floors 0-5. Honest savings: about 2x on one-turn removal and path reads,
about 40% on two-turn arms branched from the headline files, nothing for
choosers whose own sims are the cost. The value is cheaper two-turn
run-layer reads and the shared reconstruction piece.

**First check.** Replay strike removal through the cache from the headline
control on 0-499: every row byte-identical to the existing rmstrike file
and fights plus sim specs played at most 50% of the control's; wall time
reported, not gated.

**Cost and dependencies.** 2-3 session hours, Python only; first check
5-8 min. Uses the b39a/b files as the two-turn control once they land;
build when the mini-map is specified.

### 7. One two-turn self-play round: the product as teacher (p about 0.3, unjudged)

**What.** Generate about 20k games (or fewer, on elite and boss cells at
run-like HP) with the two-turn @hpe product player, label them with
outcomes, fine-tune the 10-29 net with the burst recipe (2 seeds), read on
the one-turn gauntlet with --against and confirm two turns deep. This is
the plain form of expert iteration; what was tried before (ranking
distillation) is the form the prior-art scan names as the known weak link.

**Why and against.** It is the only training arm aimed at the teacher
ceiling (pattern 6), and a teacher that is +0.06 clears stronger exists.
Against: the project's closest analogue (one self-play step with a
stronger generator, round 0 to 1) gave +0.017 on tight2 and then a
plateau; rung-4 play-out labels on the same states gave nothing; and a
20k-game two-turn round is an overnight slot even after the cost work.
Run it once, after approaches 1 and 2 have cut the cost, as the last
training test of this phase; a null at 2 seeds closes the outcome-label
family on this dev machine.

### 8. A hybrid leaf: the heuristic as an ensemble member (p about 0.3, unjudged)

**What.** The ensemble evaluator already averages nets
(a.pt+b.pt+c.pt). Let it take the heuristic as a member on the net's
scale, play two turns @hpe0.01 on the cell gauntlet with --against
net1029-hpe0.01-two-a.json at two or three mixing weights (2-4
thread-hours). A pass says the two evaluators carry different information
(the heuristic is horizon-complete and interaction-blind; the net is the
reverse) and justifies a residual net (target = outcome minus the
heuristic's estimate; inputs plus turns-left and per-entity rates). Against:
the heuristic's absolute values sit far below the net's (search values
about 0.98 where games score 1.71), so the blend needs the net's scale, and
the rates columns (a heuristic term as input) cost the Guardian before
depth removed that cost. Same-kind ensembles gained nothing under depth;
mixing kinds is untested.

### Cheap reads to queue beside them

Most are one-turn jobs that fit beside the two-turn slots.

1. The heuristic two-turn anchor on sequences 250-749 (about 70 min at 3
   threads, 4-5 GB): confirms the leaf's two-turn lead on a book the HP
   price was not tuned on (A1).
2. Effects vs ids at run level: six one-turn cell gauntlets of the ids5k
   and data5k r1 twins @hpb0.01 with --against, about 0.3 thread-hours each
   (A1, A5). The queued Q6 jobs (b39aa, b39c1/c2) read the same twins on
   the generated bench at one and two turns; keep both, the gauntlet one
   is in the goal's unit.
3. lean s101 r2 and lean-thr s101 r2 on the one-turn gauntlet (about 25
   min each): fixes the from-scratch seed sd and the threshold-row question
   before the survival arms inherit the layout (A3).
4. The standing players re-ranked on the headline setting with --against
   (3-4 thread-hours in all): validates the ruler the week's verdicts are
   built on (A7).
5. lean s101 and s201 r2 (solve step off) on the cell gauntlet: closes the
   solve step at run level with two plays (A8).
6. The survival arms, when they run: their pre-registered run-HP rule as
   written, plus a one-turn gauntlet of each r2 survive net --against
   net1029-hpb0.01.json with the bonus controls and nob_probe (A3, A8).
7. The rows-on vs rows-off burst on the branch module (about 2
   thread-hours): the series' net-side verdict (A4).
8. The matched-HP replay probe (floor-9 elites that lost 15+ HP, bosses
   entered at 50-69 HP; two-turn product vs three-turn vs a rollout leaf;
   elites first, one thread per fight, 4 thread-hours cap): decides whether
   deep search on decisive decisions has headroom (A2).
9. A half-day sts_lightspeed build (ucrt64 toolchain present) for a floor
   and ceiling at A0 / A20 Act 1 and an A0 parity harness on the 17
   encounters we model; no translator (A9).
10. The crossed chooser arms (net plays, heuristic chooses; the mirror) on
    the headline setting, one turn, --against (A6).

### Judged lower, and why

- Luck-adjusted reads (a control variate from how lucky each drawn hand
  was, after GNU Backgammon's rollout variance reduction): sound and
  unbiased, but 36-45% of the paired variance is the death cliff that a
  linear hand-luck term barely touches; pilot it only where it is free,
  inside the two-turn tree's existing sampled values, and expect a 15-25%
  cut, not 35%.
- Null-unroll columns (the engine runs each leaf k rounds forward under a
  null policy and the net reads the trajectory): the right shape for goal
  1, but the record says fixing this bias does not buy run-level HP; run
  it as a goal-1 experiment with the Silent Poison read first.
- Counterfactual labels (fine-tune on perturbed states labelled with
  paired play-outs): a goal-1 tool; re-centre it on quantities that differ
  between sibling afterstates (Poison, monster HP, own power stacks), since
  enemy Strength is the same in every sibling and cannot change a pick.
- A time price from the simulator at search time (the heuristic's
  future-HP-loss estimate as a term): run its offline gate on the audit
  states (with the heuristic itself as a control row), read play only under
  the product's two-turn setting; the @esp precedent and the 10-29 net
  pricing worse yet playing better cut against it.
- Paired dice (per-purpose random streams so two players face the same
  rolls): dropped as written; the Act-1 bosses roll no dice and the engine
  has no shuffles (a draw is one random index into a bag), so the boss
  noise it targets is play-by-draw interaction; the boss-replay check
  covers it.
- An oracle-gap bench (fraction of the gap to a content-aware net that the
  product closes): only with HP lost as the unit (elite wins saturate at
  run-like HP) and a same-family oracle; the premise that the generated
  bench is blind because of low HP is contradicted by the files.
- sts_lightspeed as the arena with a state translator: cut to the parity
  harness; today's engine cannot represent an A20 Act-1 fight exactly
  (Ascension scaling, the Ascender's Bane curse, three missing encounters,
  about 40 missing Ironclad cards).

## Stop or pause

- Stop training-recipe arms as goal-2 levers (label variants, curriculum
  and exact-label caps, rung-4 labels, data size beyond 20k, coverage,
  same-kind ensembles, per-mechanic columns, bursts for the product, more
  one-turn self-play rounds). Twelve-plus arms moved fits and fight proxies
  by 0 to 0.02 and the run-level unit not at all or the wrong way. Drop the
  parked data80k s201 and score-r0 jobs.
- Stop promoting or closing anything on tight2, run-HP or the ladder for
  goal 2; tight2 keeps only its goal-1 "held-out cards not worse" job.
- Stop the exact solver as a label source and the solved database as a
  maintained asset (solve_games 0 by default, no ideas#72, no post-series
  refill, test_bounds skipped with a reason); keep puzzles.json as a free
  check.
- Stop raising c and stop flat hand prices on per-turn effects as goal-2
  levers (c 0.02: -0.032 clears; @esp0.04: -0.020 clears). A
  state-dependent price belongs in the survival arms' read or in the fitted
  run value.
- Stop reading generated content as raw win rates on swapped cards against
  the heuristic on tight2 cells, and stop content-share training arms at
  scale. Every goal-1 number carries a card-strength reference on full-HP
  fights.
- Stop runtime-registry stages 3-5 and entity-shape until a bench or
  content needs them; stop requiring "bit-identical" for future content
  specs; measure two-turn peak memory before landing.
- Stop treating sts_lightspeed as a candidate play or training engine;
  build it for parity only.
- Pause three-turn search, rollout leaves and two-turn search inside the
  choosers as product candidates until the matched-HP probe shows
  headroom.
- Pause one-flag-at-a-time run-layer additions after removal and
  elite-skip; the next step is a mini-map read with the fitted run value.
- Pause simulated choosers with few samples per option (rest site, removal:
  both lost to selection noise at 16 sims over 6-9 options); a rule or a
  fitted value until a chooser can afford 64 sims or a 2-se margin.

## Decisions for the owner

1. **What goal 1 means.** (a) New bundles of the engine's known atoms (a
   new character, new cards, mutated monsters from existing triggers,
   effects and patterns), reachable with depth plus a 10-minute burst and
   measured by retention on the generated-character gauntlet; or (b)
   genuinely new atoms arriving as data with no Rust, which needs
   runtime-registry stages 2-5 plus a content-agnostic price and has no
   known zero-shot method. Recommendation: declare (a) the goal for the
   next months with the generated character as its headline, and scope (b)
   once (a) has a number.
2. **Which simulator and which arena carry goal 2, and what "dominant"
   will mean in writing.** Recommendation: keep this engine as the only
   play and training engine; adopt the arena ladder (Arena 0: our gauntlet
   against an outside-designed fixed chooser; Arena 1: a stated headless
   Act-1 setting on our engine with a map, common relics, potions and
   Ascension knobs, reported with a parity caveat; Arena 2: the real game
   through a mod bridge); allow a half-day lightspeed build for an A0
   parity harness only. Say plainly that no number in the field's unit
   exists until Arena 1 has relics, potions, a map and the roughly 40
   missing Ironclad cards.
3. **The engine-next landing and its rule.** Recommendation: measure
   two-turn peak memory on the branch module; land by fast-forward after
   the survival arms have run or been pinned to the old module; relax to
   "old nets load"; re-aim the next stage at generated attacks and skills
   plus monsters from packs; run the rows-on vs rows-off burst as the
   series' net-side verdict; take the four runtime-registry answers above.
4. **The survival-score arms (your design).** Recommendation: run them as
   queued and read them by their pre-registered run-HP rule, and add a
   one-turn gauntlet read against net1029-hpb0.01.json with the bonus
   controls and nob_probe beside it; on a gauntlet pass, a price sweep, a
   two-turn read and the fitted run value as their price; on a fail, close
   the HP-price family for training while keeping the search-time bonus.
5. **What runs next.** Recommendation: three multi-day
   lanes in this order: (1) cheap depth (commit to the line, the
   sampled-draw leaf, the memo merge), then one two-turn self-play round as
   the last training test; (2) the run value and a mini-map; (3) the
   generated-character headline and the mutated-monster bench. Everything
   else is a cheap read queued beside them.
7. **Housekeeping only you can approve.** Archive or delete db/ (about 4 GB
   under retired fingerprints), and decide whether boss end-HP (or a second
   act) enters the headline's unit before the next headline move, since 48%
   of headline clears end the boss under 30 HP and the gauntlet scores that
   HP at zero.

## Key claims and what the skeptics did to them

1. *Every measured gauntlet gain since 10-29 came from a search-time or
   run-layer change, and no net trained after 10-29 beats the 10-29 net at
   run level.* Holds, with two softenings: burst8 s1 is about +1 HP against
   the three 10-29 twins at one seed (protocol: one pass, two open), an
   undecided read; and most post-10-29 recipes were never played on the
   gauntlet, so "none beats" means "none of the eight read there is shown
   to".
2. *The run layer multiplies the combat player, and about half the
   card-pick gain is the net recognising trained cards.* First half holds
   as a widening lead (+0.038 to +0.146), with the crossed arm missing;
   second half wrong (the held-out pool is two-thirds training cards; the
   gap is pool richness and difficulty, not recognition). Dropped.
3. *Two-turn search costs 115-140x one-turn per sequence, rebuilds four
   trees per turn, and its gain on close boss fights is real; cost, not
   absence of headroom, limits depth.* Cost and tree counts hold; the boss
   gain holds in the tight bench's unit (+0.118) and not in the gauntlet's
   (at matched entry HP the nets' two-turn boss win is no higher); "cost,
   not headroom" is half-supported: cost caps the depth already measured,
   whether more depth finds more headroom is untested.
4. *The leaf under-prices per-turn effects, but a better price does not by
   itself buy clears, so leaf-side accrual fixes are goal-1 tools.*
   Overstated: one flat price at one turn failed; the class (a shaped or
   learned price, under two turns, on bosses) is untested; the survival
   arms are its first fair test.
5. *P(clear | HP at the boss) is a steep sigmoid while the leaf prices HP
   at one flat c, and the prior "flat" read measured along floors.* Holds;
   boss identity drives much of the steepness, so price by (boss, HP).
6. *Run-level seed noise is about 0.4 HP for twins but near 1 HP for
   from-scratch recipes, so single-seed closures are inside noise.*
   Overstated: the 0.4 HP figure is itself rough (four pairs sharing one
   round 0); "near 1 HP" is unmeasured and the lean vs lean-thr gap is
   confounded; the fight-level closures were 2-5 seed reads; what is
   single-seed is the gauntlet re-rank, where data80k and lean-thr would
   drop to about 2 seed-sd if the sd were 1 HP. Two cheap plays decide.

## What changed after the snapshot

Commit edb579f (12:13) on main, after the panel's reading: card removal
read (Strike +1.78 HP; the sim chooser closed); mixed depth read (level at
57% of the wall time) and adopted as the cell-gauntlet screening default,
the headline keeping full depth until checked; the headline jobs b39a/b
resized to 2 threads and 3 GB and started 12:11 (about 240 min each); the
elite-skip spec confirmed and its step 1 built (6669be1: --elites skip|hp);
the goal-1 twin reads queued (b39aa one turn, b39c1/c2 two turns, on
gen_powers12c3). Approach 6 above and the "pause one-flag-at-a-time" item
already take the elite-skip read as given; the elite-skip ceiling (always
skip) is the number that says whether a map is worth building here.

Numbers in this review that are the panel's own computations and were not
independently re-derived: the per-class swap costs (A5; the critic's
coarser means agree in direction), the headline setting's paired noise by
decision floor (A6), the share of a turn's two-turn cost in its first tree
(approach 1). Each is marked where it appears.
